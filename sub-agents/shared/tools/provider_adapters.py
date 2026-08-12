from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderCommand:
    provider: str
    backend: str
    executable: str
    args: list[str]
    prompt_via_stdin: bool

    def display_args(self) -> list[str]:
        return [self.executable, *self.args, "<PROMPT via stdin>" if self.prompt_via_stdin else "<PROMPT>"]


def resolve_executable(command: str) -> str | None:
    return shutil.which(command)


def command_version(executable: str, timeout_seconds: int = 15) -> str | None:
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0] if output else None


def provider_status(provider_config: dict[str, Any]) -> list[dict[str, Any]]:
    statuses = []
    for name, config in provider_config.get("providers", {}).items():
        executable = resolve_executable(config["command"]) if config.get("enabled", True) else None
        statuses.append({
            "provider": name,
            "backend": config.get("backend", name),
            "configured_command": config["command"],
            "available": executable is not None,
            "executable": executable,
            "version": command_version(executable) if executable else None,
            "note": config.get("note"),
        })
    return statuses


def build_provider_command(
    provider: str,
    provider_config: dict[str, Any],
    workspace: Path,
    model: str | None = None,
) -> ProviderCommand:
    config = provider_config.get("providers", {}).get(provider)
    if config is None:
        raise ValueError(f"unknown provider: {provider}")
    if not config.get("enabled", True):
        raise ValueError(f"provider is disabled: {provider}")
    executable = resolve_executable(config["command"])
    if executable is None:
        raise ValueError(f"provider command is unavailable: {config['command']}")

    backend = config.get("backend", provider)
    if backend == "codex-cli":
        args = [
            "exec", "--cd", str(workspace), "--skip-git-repo-check",
            "--ephemeral", "--ignore-rules", "--approve-for-me",
            "--color", "never",
        ]
        if model:
            args.extend(["--model", model])
        args.append("-")
        return ProviderCommand(provider, backend, executable, args, True)

    if backend == "claude-code":
        args = [
            "--print", "--output-format", "json", "--permission-mode", "acceptEdits",
            "--tools", "Read,Edit,Write", "--no-session-persistence", "--safe-mode",
        ]
        if model:
            args.extend(["--model", model])
        return ProviderCommand(provider, backend, executable, args, True)

    if backend == "gemini-cli":
        args = [
            "--prompt", "", "--output-format", "json", "--approval-mode", "auto_edit",
            "--sandbox", "--skip-trust",
        ]
        if model:
            args.extend(["--model", model])
        return ProviderCommand(provider, backend, executable, args, True)

    raise ValueError(f"unsupported provider backend: {backend}")
