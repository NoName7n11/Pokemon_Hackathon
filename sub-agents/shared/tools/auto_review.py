from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import SUB_AGENTS_ROOT, read_json, resolve_specialist, write_json_atomic
from review_queue import infer_assignment


TOOLS_DIR = Path(__file__).resolve().parent
REVIEWER_PROMPT = SUB_AGENTS_ROOT / "shared" / "prompts" / "reviewer.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def active_review(specialist: Path) -> tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any], Path, Path]:
    status = read_json(specialist / "status.json")
    if status.get("review_state") != "REVIEW_REQUIRED" or not status.get("active_experiment"):
        raise ValueError(f"{specialist.name} has no pending review")
    experiment_dir = specialist / "experiments" / status["active_experiment"]
    experiment = read_json(experiment_dir / "experiment.json")
    pending = next((item for item in reversed(experiment.get("reviews", [])) if item.get("status") == "pending"), None)
    if pending is None:
        raise ValueError(f"{specialist.name}/{experiment['id']} has no pending review record")
    markdown = SUB_AGENTS_ROOT / pending["markdown"]
    review_json = SUB_AGENTS_ROOT / pending["json"]
    if not markdown.is_file() or not review_json.is_file():
        raise ValueError(f"pending review files are missing for {specialist.name}/{experiment['id']}")
    return status, experiment_dir, experiment, pending, markdown, review_json


def build_prompt(markdown: Path) -> str:
    return (
        REVIEWER_PROMPT.read_text(encoding="utf-8")
        + "\n\nYou are reviewing this pending Plan_2 review pack. Return one clear recommendation "
        + "on its own line near the top: REJECT, APPROVE_DEEP_EVALUATION, or MORE_EVIDENCE. "
        + "Then explain the reasoning briefly. Do not edit files and do not promote anything.\n\n"
        + markdown.read_text(encoding="utf-8")
    )


def command_for(reviewer: dict[str, str], workspace: Path) -> list[str]:
    provider = reviewer["provider"].lower()
    model = reviewer.get("model") or None
    if provider == "claude":
        command = [
            "claude", "--print", "--output-format", "json", "--permission-mode", "acceptEdits",
            "--tools", "Read", "--no-session-persistence", "--safe-mode",
        ]
        if model:
            command.extend(["--model", model])
        return command
    if provider == "codex":
        command = [
            "codex", "exec", "--cd", str(workspace), "--skip-git-repo-check",
            "--ephemeral", "--ignore-rules", "--color", "never",
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")
        return command
    raise ValueError(f"unsupported reviewer provider: {provider}")


def extract_text(stdout: str) -> str:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout
    if isinstance(payload, dict):
        for key in ("result", "message", "output", "text"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    return stdout


def classify_recommendation(text: str) -> str:
    upper = text.upper()
    for line in upper.splitlines()[:20]:
        if re.search(r"\b(RECOMMENDATION|DECISION)\b", line):
            if re.search(r"\bMORE_EVIDENCE\b", line):
                return "more_evidence"
            if re.search(r"\bAPPROVE_DEEP_EVALUATION\b", line):
                return "approve_deep_evaluation"
            if re.search(r"\bREJECT\b", line):
                return "reject"
    head = "\n".join(upper.splitlines()[:12])
    if re.search(r"\bMORE_EVIDENCE\b", head):
        return "more_evidence"
    if re.search(r"\bAPPROVE_DEEP_EVALUATION\b", head):
        return "approve_deep_evaluation"
    if re.search(r"\bREJECT\b", head):
        return "reject"
    return "unclassified"


def append_markdown_review(markdown: Path, reviewer: dict[str, str], recommendation: str, text: str, output_path: Path) -> None:
    heading = f"## {reviewer['reviewer'].title()} Auto Review"
    existing = markdown.read_text(encoding="utf-8")
    if heading in existing:
        return
    clipped = text.strip()
    if len(clipped) > 5000:
        clipped = clipped[:5000] + "\n\n[review text truncated in Markdown; see audit artifact]"
    markdown.write_text(
        existing
        + f"\n\n{heading}\n\n"
        + f"Decision: {recommendation.upper()}.\n\n"
        + clipped
        + "\n\nAudit artifact: "
        + f"`{output_path.relative_to(SUB_AGENTS_ROOT).as_posix()}`.\n",
        encoding="utf-8",
    )


def run_review(args) -> int:
    specialist = resolve_specialist(args.specialist)
    status, experiment_dir, experiment, pending, markdown, review_json = active_review(specialist)
    review_pack = read_json(review_json)
    reviewer = infer_assignment(review_pack)
    if args.reviewer and args.reviewer != reviewer["reviewer"]:
        raise ValueError(f"pending review is assigned to {reviewer['reviewer']}, not {args.reviewer}")

    output_dir = experiment_dir / "reviews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{pending['stage']}-{reviewer['reviewer']}-auto-review.json"
    if output_path.exists() and not args.force:
        record = read_json(output_path)
    else:
        prompt = build_prompt(markdown)
        workspace = output_dir / f"{pending['stage']}-{reviewer['reviewer']}-workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        command = command_for(reviewer, workspace)
        completed = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.timeout_seconds,
            check=False,
        )
        text = extract_text(completed.stdout)
        recommendation = classify_recommendation(text)
        record = {
            "schema_version": 1,
            "specialist": specialist.name,
            "experiment": experiment["id"],
            "stage": pending["stage"],
            "created_at": utc_now(),
            "assigned_reviewer": reviewer,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "review_text": text,
            "recommendation": recommendation,
        }
        write_json_atomic(output_path, record)

    if record.get("returncode") != 0:
        raise ValueError(f"reviewer command failed with {record.get('returncode')}; see {output_path}")
    recommendation = str(record.get("recommendation") or "unclassified")
    append_markdown_review(markdown, reviewer, recommendation, str(record.get("review_text", "")), output_path)

    experiment = read_json(experiment_dir / "experiment.json")
    experiment.setdefault("review_history", []).append({
        "stage": pending["stage"],
        "decision": recommendation,
        "reviewer": reviewer["reviewer"],
        "reason": f"automatic AI review; see {output_path.relative_to(experiment_dir).as_posix()}",
        "at": utc_now(),
    })
    experiment.setdefault("orchestration", {}).update({
        "ai_review_state": recommendation,
        "ai_review_reviewer": reviewer["reviewer"],
        "ai_review_artifact": str(output_path.relative_to(experiment_dir)).replace("\\", "/"),
        "updated_at": utc_now(),
    })
    experiment["updated_at"] = utc_now()
    write_json_atomic(experiment_dir / "experiment.json", experiment)

    if not args.apply_gate:
        print(f"{specialist.name}/{experiment['id']}: {recommendation}")
        return 0
    if recommendation == "reject":
        reason = f"automatic {reviewer['reviewer']} review rejected candidate; see {output_path.relative_to(experiment_dir).as_posix()}"
        command = [sys.executable, str(TOOLS_DIR / "review_gate.py"), "reject", "--specialist", specialist.name, "--reason", reason]
    elif recommendation == "approve_deep_evaluation" and pending["stage"] == "screening":
        reason = f"automatic {reviewer['reviewer']} review approved deep evaluation; see {output_path.relative_to(experiment_dir).as_posix()}"
        command = [sys.executable, str(TOOLS_DIR / "review_gate.py"), "approve", "--specialist", specialist.name, "--reason", reason]
    else:
        print(f"{specialist.name}/{experiment['id']}: {recommendation}; gate left pending")
        return 0
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False)
    if completed.returncode != 0:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        return completed.returncode
    print(completed.stdout.strip())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the assigned independent AI reviewer for a pending review gate.")
    parser.add_argument("--specialist", required=True)
    parser.add_argument("--reviewer", choices=("codex", "opus"))
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--apply-gate", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        return run_review(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
