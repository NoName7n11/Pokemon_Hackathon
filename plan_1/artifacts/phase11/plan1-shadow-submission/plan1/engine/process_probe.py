from __future__ import annotations

import multiprocessing
import queue
from pathlib import Path
from typing import Any


def _worker(deck_path: str, sessions: int, max_path_steps: int, output: Any) -> None:
    try:
        from plan1.engine.conformance import conformance_passes, read_deck, run_conformance

        result = run_conformance(
            read_deck(Path(deck_path)),
            session_iterations=sessions,
            max_path_steps=max_path_steps,
        )
        output.put({"ok": conformance_passes(result), "result": result.to_dict()})
    except BaseException as exc:
        output.put({"ok": False, "error": repr(exc)})


def run_process_isolation_probe(
    deck_path: Path,
    workers: int = 2,
    sessions: int = 50,
    max_path_steps: int = 600,
) -> dict[str, Any]:
    if workers < 2 or sessions < 1 or max_path_steps < 1:
        raise ValueError("workers must be at least 2 and counts must be positive")
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    processes = [
        context.Process(
            target=_worker,
            args=(str(deck_path.resolve()), sessions, max_path_steps, output),
            daemon=False,
        )
        for _ in range(workers)
    ]
    for process in processes:
        process.start()

    reports: list[dict[str, Any]] = []
    for _ in processes:
        try:
            reports.append(output.get(timeout=120))
        except queue.Empty:
            reports.append({"ok": False, "error": "worker result timed out"})
    for process in processes:
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    exit_codes = [process.exitcode for process in processes]
    ok = all(report.get("ok") for report in reports) and all(code == 0 for code in exit_codes)
    return {
        "ok": ok,
        "workers": workers,
        "sessions_per_worker": sessions,
        "max_path_steps": max_path_steps,
        "exit_codes": exit_codes,
        "reports": reports,
    }
