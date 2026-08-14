from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import SUB_AGENTS_ROOT, read_json, resolve_specialist, write_json_atomic


TOOLS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SUB_AGENTS_ROOT / "shared" / "continuous_config.json"
CONTINUOUS_ROOT = SUB_AGENTS_ROOT / "continuous"
CAMPAIGN_ROOT = CONTINUOUS_ROOT / "campaigns"
STATE_PATH = CONTINUOUS_ROOT / "state.json"
REPORT_PATH = CONTINUOUS_ROOT / "REPORT.md"
SCHEDULER_LOCK = CONTINUOUS_ROOT / ".scheduler.lock"
STATE_LOCK = CONTINUOUS_ROOT / ".state.lock"
STOP_PATH = CONTINUOUS_ROOT / "STOP.request"
TERMINAL_STATES = {"completed", "rejected", "failed", "cancelled"}
RUNNING_STATES = {"running_screening", "running_ai_review", "running_deep_evaluation"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def exclusive_lock(path: Path, timeout_seconds: float = 30.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor = None
    while descriptor is None:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"could not acquire lock: {path}")
            time.sleep(0.05)
    try:
        os.write(descriptor, f"pid={os.getpid()}\nstarted_at={utc_now()}\n".encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)


def empty_state() -> dict[str, Any]:
    return {"schema_version": 1, "updated_at": utc_now(), "jobs": []}


def load_state() -> dict[str, Any]:
    return read_json(STATE_PATH) if STATE_PATH.is_file() else empty_state()


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    write_json_atomic(STATE_PATH, state)


def append_report(job: dict[str, Any], event: str, detail: str) -> None:
    marker = f"<!-- {job['id']}:{len(job['history'])}:{event} -->"
    if REPORT_PATH.is_file() and marker in REPORT_PATH.read_text(encoding="utf-8"):
        return
    is_new = not REPORT_PATH.is_file() or REPORT_PATH.stat().st_size == 0
    with REPORT_PATH.open("w" if is_new else "a", encoding="utf-8") as handle:
        if is_new:
            handle.write(
                "# Continuous Specialist Research\n\n"
                "Append-only scheduler history. Automatic rejection is allowed; acceptance and "
                "submission promotion always require separate human actions.\n\n"
            )
        handle.write(
            f"{marker}\n## {utc_now()} - {job['id']}\n\n"
            f"- Specialist: `{job['specialist']}`\n"
            f"- Provider: `{job['provider']}`\n"
            f"- State: `{job['state']}`\n"
            f"- Event: `{event}`\n"
            f"- Detail: {detail}\n"
            f"- Hypothesis: {job['hypothesis']}\n\n"
        )


def transition(job: dict[str, Any], state: str, event: str, detail: str) -> None:
    record = {"at": utc_now(), "state": state, "event": event, "detail": detail}
    job["state"] = state
    job["updated_at"] = record["at"]
    job.setdefault("history", []).append(record)
    append_report(job, event, detail)
    sync_campaign_job_state(job)


def sync_campaign_job_state(job: dict[str, Any]) -> None:
    campaign_ref = job.get("campaign")
    if not isinstance(campaign_ref, dict):
        return
    relative = campaign_ref.get("path")
    hypothesis_id = campaign_ref.get("hypothesis_id")
    if not relative or not hypothesis_id:
        return
    path = CONTINUOUS_ROOT / str(relative)
    if not path.is_file():
        return
    try:
        campaign = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return
    changed = False
    for hypothesis in campaign.get("hypotheses", []):
        if hypothesis.get("id") != hypothesis_id:
            continue
        hypothesis["state"] = job["state"]
        hypothesis["job"] = job["id"]
        hypothesis["updated_at"] = job["updated_at"]
        if job["state"] in TERMINAL_STATES or job["state"] == "waiting_more_evidence":
            hypothesis["finished_at"] = job["updated_at"]
        changed = True
        break
    if changed:
        campaign["updated_at"] = utc_now()
        write_json_atomic(path, campaign)


def append_campaign_report(campaign: dict[str, Any], hypothesis: dict[str, Any], job: dict[str, Any]) -> None:
    marker = f"<!-- campaign:{campaign['specialist']}:{hypothesis['id']}:{job['id']} -->"
    if REPORT_PATH.is_file() and marker in REPORT_PATH.read_text(encoding="utf-8"):
        return
    is_new = not REPORT_PATH.is_file() or REPORT_PATH.stat().st_size == 0
    with REPORT_PATH.open("w" if is_new else "a", encoding="utf-8") as handle:
        if is_new:
            handle.write(
                "# Continuous Specialist Research\n\n"
                "Append-only scheduler history. Automatic rejection is allowed; acceptance and "
                "submission promotion always require separate human actions.\n\n"
            )
        handle.write(
            f"{marker}\n## {utc_now()} - Campaign queued {job['id']}\n\n"
            f"- Specialist: `{campaign['specialist']}`\n"
            f"- Campaign: `{campaign.get('name', campaign['specialist'])}`\n"
            f"- Hypothesis ID: `{hypothesis['id']}`\n"
            f"- Provider: `{job['provider']}`\n"
            f"- Model: `{job.get('model') or 'default'}`\n"
            f"- Mechanism: `{hypothesis['mechanism']}`\n"
            f"- Hypothesis: {hypothesis['hypothesis']}\n"
            f"- Expected effect: {hypothesis['expected_effect']}\n\n"
        )


def next_job_id(state: dict[str, Any]) -> str:
    highest = 0
    for job in state.get("jobs", []):
        if job.get("id", "").startswith("JOB-"):
            try:
                highest = max(highest, int(job["id"].split("-", 1)[1]))
            except ValueError:
                pass
    return f"JOB-{highest + 1:05d}"


def nonterminal_specialists(jobs: list[dict[str, Any]]) -> set[str]:
    return {
        job["specialist"] for job in jobs
        if job["state"] not in TERMINAL_STATES
    }


def load_campaigns() -> list[tuple[Path, dict[str, Any]]]:
    if not CAMPAIGN_ROOT.is_dir():
        return []
    campaigns = []
    for path in sorted(CAMPAIGN_ROOT.glob("*.json")):
        try:
            campaign = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if campaign.get("enabled", False):
            campaigns.append((path, campaign))
    return campaigns


def next_campaign_hypothesis(campaign: dict[str, Any]) -> dict[str, Any] | None:
    for hypothesis in campaign.get("hypotheses", []):
        if hypothesis.get("state", "pending") == "pending":
            return hypothesis
    return None


def enqueue_campaign_jobs(state: dict[str, Any], config: dict[str, Any], daily_remaining: int) -> int:
    if daily_remaining <= 0:
        return daily_remaining
    jobs = state.setdefault("jobs", [])
    busy = nonterminal_specialists(jobs)
    for path, campaign in load_campaigns():
        if daily_remaining <= 0:
            break
        specialist_name = str(campaign.get("specialist", "")).strip()
        if not specialist_name or specialist_name in busy:
            continue
        hypothesis = next_campaign_hypothesis(campaign)
        if hypothesis is None:
            continue
        status, _ = specialist_status(specialist_name)
        if status.get("state") != "READY_FOR_EXPERIMENT" or status.get("active_experiment"):
            continue
        if config.get("require_provider_authorization_per_job", True) and not campaign.get("provider_authorized", False):
            continue
        provider = campaign.get("provider") or read_json(resolve_specialist(specialist_name) / "config.json")["provider"]
        job = {
            "id": next_job_id(state),
            "specialist": specialist_name,
            "provider": provider,
            "model": campaign.get("model"),
            "hypothesis": hypothesis["hypothesis"],
            "mechanism": hypothesis["mechanism"],
            "expected_effect": hypothesis["expected_effect"],
            "provider_authorized": bool(campaign.get("provider_authorized", False)),
            "state": "queued",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "experiment": None,
            "seed": int(hypothesis.get("seed") or secrets.randbelow(2_000_000_000) + 1),
            "campaign": {
                "path": str(path.relative_to(CONTINUOUS_ROOT)).replace("\\", "/"),
                "hypothesis_id": hypothesis["id"],
            },
            "history": [],
        }
        transition(job, "queued", "campaign_enqueued", f"Campaign queued hypothesis {hypothesis['id']}.")
        jobs.append(job)
        hypothesis["state"] = "queued"
        hypothesis["job"] = job["id"]
        hypothesis["queued_at"] = utc_now()
        write_json_atomic(path, campaign)
        append_campaign_report(campaign, hypothesis, job)
        busy.add(specialist_name)
        daily_remaining -= 1
    return daily_remaining


def enqueue(args) -> int:
    specialist = resolve_specialist(args.specialist)
    config = read_json(CONFIG_PATH)
    specialist_config = read_json(specialist / "config.json")
    provider = args.provider or specialist_config["provider"]
    if config.get("require_provider_authorization_per_job", True) and not args.authorize_provider:
        raise ValueError("live provider authorization is required; add --authorize-provider")
    with exclusive_lock(STATE_LOCK):
        state = load_state()
        job = {
            "id": next_job_id(state),
            "specialist": specialist.name,
            "provider": provider,
            "model": args.model,
            "hypothesis": args.hypothesis,
            "mechanism": args.mechanism,
            "expected_effect": args.expected_effect,
            "provider_authorized": bool(args.authorize_provider),
            "state": "queued",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "experiment": None,
            "seed": args.seed if args.seed is not None else secrets.randbelow(2_000_000_000) + 1,
            "history": [],
        }
        transition(job, "queued", "enqueued", "Awaiting an available specialist slot.")
        state.setdefault("jobs", []).append(job)
        save_state(state)
    print(f"Queued {job['id']} for {specialist.name}")
    return 0


def authorize(args) -> int:
    if not args.acknowledge_source_egress:
        raise ValueError("authorization requires --acknowledge-source-egress")
    with exclusive_lock(STATE_LOCK):
        state = load_state()
        job = next((item for item in state.get("jobs", []) if item["id"] == args.job), None)
        if job is None:
            raise ValueError(f"scheduler job does not exist: {args.job}")
        if job["state"] != "awaiting_provider_authorization":
            raise ValueError(f"job is not awaiting authorization: {job['state']}")
        job["provider_authorized"] = True
        transition(
            job,
            "queued",
            "provider_authorized",
            f"Human explicitly authorized sending the isolated private source/context to {job['provider']}.",
        )
        save_state(state)
    print(f"Authorized {job['id']} for {job['provider']}; job is queued.")
    return 0


def command_for(job: dict[str, Any], phase: str) -> list[str]:
    if phase == "screening":
        command = [
            sys.executable, str(TOOLS_DIR / "orchestrate.py"), "run",
            "--specialist", job["specialist"],
            "--provider", job["provider"],
            "--hypothesis", job["hypothesis"],
            "--mechanism", job["mechanism"],
            "--expected-effect", job["expected_effect"],
            "--through", "screening",
            "--seed", str(job["seed"]),
        ]
        if job.get("model"):
            command.extend(["--model", job["model"]])
        return command
    if phase == "deep":
        return [
            sys.executable, str(TOOLS_DIR / "advance_evidence.py"),
            "--specialist", job["specialist"],
            "--seed", str(job["seed"] + 1000),
        ]
    command = [
        sys.executable, str(TOOLS_DIR / "auto_review.py"),
        "--specialist", job["specialist"],
        "--timeout-seconds", str(read_json(CONFIG_PATH).get("review_timeout_seconds", 900)),
    ]
    if read_json(CONFIG_PATH).get("auto_ai_review_apply_gate", True):
        command.append("--apply-gate")
    return command


def ai_review_decision(experiment: dict[str, Any] | None) -> str | None:
    if not experiment:
        return None
    orchestration = experiment.get("orchestration", {})
    value = orchestration.get("ai_review_state")
    return str(value) if value else None


def specialist_status(name: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    specialist = resolve_specialist(name)
    status = read_json(specialist / "status.json")
    experiment = None
    if status.get("active_experiment"):
        path = specialist / "experiments" / status["active_experiment"] / "experiment.json"
        if path.is_file():
            experiment = read_json(path)
    return status, experiment


def reconcile_waiting(job: dict[str, Any]) -> str | None:
    status, experiment = specialist_status(job["specialist"])
    if status.get("active_experiment") and job.get("experiment") is None:
        job["experiment"] = status["active_experiment"]
    if status.get("state") == "READY_FOR_EXPERIMENT" and not status.get("active_experiment"):
        if experiment is None and job.get("experiment"):
            specialist = resolve_specialist(job["specialist"])
            path = specialist / "experiments" / job["experiment"] / "experiment.json"
            experiment = read_json(path) if path.is_file() else None
        decision = experiment.get("decision") if experiment else None
        final_state = "completed" if decision == "accepted" else "rejected"
        transition(job, final_state, "experiment_closed", f"Private experiment decision: {decision or 'unknown'}.")
        return None
    if job["state"] == "waiting_screening_review" and experiment:
        orchestration = experiment.get("orchestration", {}).get("state")
        if orchestration == "PAUSED_BY_HUMAN":
            return None
        if ai_review_decision(experiment) == "more_evidence":
            transition(job, "waiting_more_evidence", "ai_review_requested_more_evidence", "Independent AI review requested trace, ablation, or measurement before deep evaluation.")
            return None
        if orchestration == "MAIN_AUTHORIZED":
            return "deep"
    return None


def experiments_started_today(state: dict[str, Any]) -> int:
    today = utc_now()[:10]
    return sum(
        1 for job in state.get("jobs", [])
        if any(record.get("event") == "screening_started" and record.get("at", "")[:10] == today for record in job.get("history", []))
    )


def provider_process_counts(
    processes: dict[str, tuple[subprocess.Popen, Any, str]],
    jobs: list[dict[str, Any]],
) -> dict[str, int]:
    jobs_by_id = {job["id"]: job for job in jobs}
    counts: dict[str, int] = {}
    for job_id in processes:
        job = jobs_by_id.get(job_id)
        if job is None:
            continue
        provider = job["provider"]
        counts[provider] = counts.get(provider, 0) + 1
    return counts


def has_worker_capacity(
    job: dict[str, Any],
    processes: dict[str, tuple[subprocess.Popen, Any, str]],
    jobs: list[dict[str, Any]],
    config: dict[str, Any],
) -> bool:
    if len(processes) >= int(config["max_parallel_specialists"]):
        return False
    limits = config.get("provider_parallel_limits", {})
    limit = int(limits.get(job["provider"], config["max_parallel_specialists"]))
    return provider_process_counts(processes, jobs).get(job["provider"], 0) < limit


def run_loop(once: bool) -> int:
    config = read_json(CONFIG_PATH)
    if not config.get("enabled", False):
        raise ValueError("continuous scheduler is disabled in continuous_config.json")
    CONTINUOUS_ROOT.mkdir(parents=True, exist_ok=True)
    STOP_PATH.unlink(missing_ok=True)
    processes: dict[str, tuple[subprocess.Popen, Any, str]] = {}
    with exclusive_lock(SCHEDULER_LOCK, timeout_seconds=0.1):
        while True:
            with exclusive_lock(STATE_LOCK):
                state = load_state()
                jobs = state.setdefault("jobs", [])

                for job_id, (process, log_handle, phase) in list(processes.items()):
                    returncode = process.poll()
                    if returncode is None:
                        continue
                    log_handle.close()
                    job = next(item for item in jobs if item["id"] == job_id)
                    status, experiment = specialist_status(job["specialist"])
                    if status.get("active_experiment"):
                        job["experiment"] = status["active_experiment"]
                    if returncode != 0:
                        final = "rejected" if status.get("state") == "READY_FOR_EXPERIMENT" else "failed"
                        transition(job, final, f"{phase}_failed", f"Process exited with {returncode}.")
                    elif phase == "screening":
                        transition(job, "waiting_screening_review", "screening_complete", "20-game smoke and 200-game screening completed; human review required.")
                    elif phase == "ai_review":
                        decision = ai_review_decision(experiment)
                        orchestration = experiment.get("orchestration", {}).get("state") if experiment else None
                        if status.get("state") == "READY_FOR_EXPERIMENT" and not status.get("active_experiment"):
                            final_decision = experiment.get("decision") if experiment else None
                            final = "completed" if final_decision == "accepted" else "rejected"
                            transition(job, final, "ai_review_closed_experiment", f"Independent AI review closed experiment as {final_decision or 'unknown'}.")
                        elif decision == "more_evidence":
                            transition(job, "waiting_more_evidence", "ai_review_requested_more_evidence", "Independent AI review requested more evidence; automatic loop paused for this experiment.")
                        elif orchestration == "MAIN_AUTHORIZED":
                            transition(job, "waiting_screening_review", "ai_review_approved_deep", "Independent AI review authorized deep evaluation.")
                        else:
                            transition(job, "waiting_screening_review", "ai_review_recorded", f"Independent AI review recorded decision: {decision or 'unknown'}.")
                    else:
                        transition(job, "waiting_final_review", "deep_evaluation_complete", "Main, 500-game confirmation, and available cross-deck evaluation completed; final human review required.")
                    del processes[job_id]

                for job in jobs:
                    if job["id"] in processes or job["state"] not in {"running_screening", "running_ai_review", "running_deep_evaluation"}:
                        continue
                    status, experiment = specialist_status(job["specialist"])
                    if status.get("state") == "REVIEW_REQUIRED" and experiment:
                        orchestration = experiment.get("orchestration", {}).get("state")
                        target = "waiting_final_review" if orchestration == "FINAL_REVIEW_REQUIRED" else "waiting_screening_review"
                        transition(job, target, "recovered_review_stop", "Recovered persisted review state after scheduler restart.")
                        continue
                    if status.get("state") == "READY_FOR_EXPERIMENT" and not status.get("active_experiment"):
                        transition(job, "rejected", "recovered_closed_experiment", "Experiment closed while scheduler was offline.")
                        continue
                    if not status.get("active_experiment") or not has_worker_capacity(job, processes, jobs, config):
                        continue
                    phase = "screening" if job["state"] == "running_screening" else ("ai_review" if job["state"] == "running_ai_review" else "deep")
                    if phase == "screening":
                        command = [
                            sys.executable, str(TOOLS_DIR / "orchestrate.py"), "resume",
                            "--specialist", job["specialist"],
                            "--provider", job["provider"],
                            "--through", "screening",
                            "--seed", str(job["seed"]),
                        ]
                        if job.get("model"):
                            command.extend(["--model", job["model"]])
                    else:
                        command = command_for(job, phase)
                    log_path = CONTINUOUS_ROOT / "logs" / f"{job['id']}-{phase}-resume.log"
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    handle = log_path.open("w", encoding="utf-8")
                    process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, text=True)
                    processes[job["id"]] = (process, handle, phase)
                    transition(job, job["state"], "process_resumed", f"PID {process.pid}; log {log_path}.")

                for job in jobs:
                    if job["state"] in ("waiting_screening_review", "waiting_final_review"):
                        phase = reconcile_waiting(job)
                        if (
                            phase is None
                            and job["state"] == "waiting_screening_review"
                            and config.get("auto_ai_review", False)
                        ):
                            status, experiment = specialist_status(job["specialist"])
                            if (
                                status.get("state") == "REVIEW_REQUIRED"
                                and experiment
                                and ai_review_decision(experiment) is None
                                and has_worker_capacity(job, processes, jobs, config)
                            ):
                                log_path = CONTINUOUS_ROOT / "logs" / f"{job['id']}-ai-review.log"
                                log_path.parent.mkdir(parents=True, exist_ok=True)
                                handle = log_path.open("w", encoding="utf-8")
                                process = subprocess.Popen(command_for(job, "ai_review"), stdout=handle, stderr=subprocess.STDOUT, text=True)
                                processes[job["id"]] = (process, handle, "ai_review")
                                transition(job, "running_ai_review", "ai_review_started", f"PID {process.pid}; log {log_path}.")
                                continue
                        if phase == "deep" and has_worker_capacity(job, processes, jobs, config):
                            log_path = CONTINUOUS_ROOT / "logs" / f"{job['id']}-deep.log"
                            log_path.parent.mkdir(parents=True, exist_ok=True)
                            handle = log_path.open("w", encoding="utf-8")
                            process = subprocess.Popen(command_for(job, "deep"), stdout=handle, stderr=subprocess.STDOUT, text=True)
                            processes[job["id"]] = (process, handle, "deep")
                            transition(job, "running_deep_evaluation", "deep_evaluation_started", f"PID {process.pid}; log {log_path}.")

                daily_remaining = int(config["max_new_experiments_per_day"]) - experiments_started_today(state)
                daily_remaining = enqueue_campaign_jobs(state, config, daily_remaining)
                busy_specialists = {
                    job["specialist"] for job in jobs
                    if job["state"] not in TERMINAL_STATES and job["state"] != "queued"
                }
                for job in jobs:
                    if len(processes) >= int(config["max_parallel_specialists"]) or daily_remaining <= 0:
                        break
                    if job["state"] != "queued" or job["specialist"] in busy_specialists:
                        continue
                    if not has_worker_capacity(job, processes, jobs, config):
                        continue
                    if not job.get("provider_authorized", False):
                        transition(
                            job,
                            "awaiting_provider_authorization",
                            "authorization_missing",
                            "Live provider source transmission is not authorized.",
                        )
                        continue
                    status, _ = specialist_status(job["specialist"])
                    if status.get("state") != "READY_FOR_EXPERIMENT" or status.get("active_experiment"):
                        continue
                    log_path = CONTINUOUS_ROOT / "logs" / f"{job['id']}-screening.log"
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    handle = log_path.open("w", encoding="utf-8")
                    process = subprocess.Popen(command_for(job, "screening"), stdout=handle, stderr=subprocess.STDOUT, text=True)
                    processes[job["id"]] = (process, handle, "screening")
                    transition(job, "running_screening", "screening_started", f"PID {process.pid}; log {log_path}.")
                    busy_specialists.add(job["specialist"])
                    daily_remaining -= 1

                save_state(state)

            if once:
                if processes:
                    while any(process.poll() is None for process, _, _ in processes.values()):
                        time.sleep(0.25)
                    once = False
                    continue
                return 0
            if STOP_PATH.exists() and not processes:
                STOP_PATH.unlink(missing_ok=True)
                return 0
            time.sleep(int(config["poll_seconds"]))


def status_command(_args) -> int:
    state = load_state()
    config = read_json(CONFIG_PATH)
    counts: dict[str, int] = {}
    active_by_provider: dict[str, int] = {}
    for job in state.get("jobs", []):
        counts[job["state"]] = counts.get(job["state"], 0) + 1
        if job["state"] in RUNNING_STATES:
            provider = job["provider"]
            active_by_provider[provider] = active_by_provider.get(provider, 0) + 1
    print(json.dumps({
        "scheduler_running": SCHEDULER_LOCK.exists(),
        "capacity": {
            "global": config["max_parallel_specialists"],
            "per_provider": config.get("provider_parallel_limits", {}),
            "active_by_provider": active_by_provider,
        },
        "counts": counts,
        **state,
    }, indent=2, ensure_ascii=True))
    return 0


def stop(_args) -> int:
    CONTINUOUS_ROOT.mkdir(parents=True, exist_ok=True)
    STOP_PATH.write_text(f"requested_at={utc_now()}\n", encoding="ascii")
    print("Graceful stop requested; running jobs will finish their current bounded process.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Persistent Plan_2 specialist research scheduler.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    enqueue_parser = subparsers.add_parser("enqueue")
    enqueue_parser.add_argument("--specialist", required=True)
    enqueue_parser.add_argument("--provider", choices=("codex", "claude", "antigravity"))
    enqueue_parser.add_argument("--model")
    enqueue_parser.add_argument("--hypothesis", required=True)
    enqueue_parser.add_argument("--mechanism", required=True)
    enqueue_parser.add_argument("--expected-effect", required=True)
    enqueue_parser.add_argument("--seed", type=int)
    enqueue_parser.add_argument("--authorize-provider", action="store_true")
    enqueue_parser.set_defaults(handler=enqueue)
    authorize_parser = subparsers.add_parser("authorize")
    authorize_parser.add_argument("--job", required=True)
    authorize_parser.add_argument("--acknowledge-source-egress", action="store_true")
    authorize_parser.set_defaults(handler=authorize)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--once", action="store_true")
    run_parser.set_defaults(handler=lambda args: run_loop(args.once))
    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(handler=status_command)
    stop_parser = subparsers.add_parser("stop")
    stop_parser.set_defaults(handler=stop)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
