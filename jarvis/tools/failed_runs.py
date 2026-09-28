"""CLI/operator helpers for failed JARVIS runs and reruns."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jarvis.core.agent import Agent
from jarvis.core.memory import Memory
from jarvis.core.tracing import get_agent_run_detail, list_failed_agent_runs


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + f"...[truncated {len(compact) - limit} chars]"


def _timestamp(value: Any) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(value)))
    except Exception:
        return ""


def failed_run_summary(run: dict[str, Any]) -> dict[str, Any]:
    """Return a compact failed-run view for lists."""
    return {
        "request_id": run.get("request_id", ""),
        "timestamp": _timestamp(run.get("created_at")),
        "status": run.get("status", ""),
        "error_category": run.get("error_category", ""),
        "message_preview": _preview(run.get("user_message", "")),
        "route": run.get("route", ""),
        "chosen_tier": run.get("chosen_tier"),
        "chosen_model": run.get("chosen_model", ""),
        "parent_request_id": run.get("parent_request_id", ""),
    }


def failed_run_detail(run: dict[str, Any]) -> dict[str, Any]:
    """Return a detailed but sanitized failed-run view."""
    detail = failed_run_summary(run)
    detail.update(
        {
            "user_message": run.get("user_message", ""),
            "error": run.get("error", ""),
            "intent": run.get("intent", ""),
            "latency_ms": run.get("latency_ms"),
        }
    )
    return detail


def list_failed_runs(limit: int = 20, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    runs = list_failed_agent_runs(limit=limit, db_path=db_path)
    return [failed_run_summary(run) for run in runs]


def inspect_failed_run(request_id: str, db_path: str | Path | None = None) -> dict[str, Any]:
    if not request_id:
        return {"ok": False, "error": "request_id is required."}
    run = get_agent_run_detail(request_id, db_path=db_path)
    if not run:
        return {"ok": False, "error": f"Run not found: {request_id}"}
    return {"ok": True, "run": failed_run_detail(run)}


def _default_agent() -> Agent:
    return Agent(memory=Memory())


def rerun_failed_run(
    request_id: str,
    *,
    agent_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if not request_id:
        return {"ok": False, "error": "request_id is required."}
    agent = (agent_factory or _default_agent)()
    try:
        result = agent.rerun_failed_run(request_id)
    except Exception as exc:
        return {
            "ok": False,
            "original_request_id": request_id,
            "new_request_id": getattr(agent, "_last_request_id", ""),
            "rerun_status": "failed",
            "error": str(exc),
        }

    if result.get("ok"):
        return {
            "ok": True,
            "original_request_id": request_id,
            "new_request_id": result.get("request_id", ""),
            "rerun_status": "success",
            "response": result.get("response", ""),
        }
    return {
        "ok": False,
        "original_request_id": request_id,
        "new_request_id": result.get("request_id", ""),
        "rerun_status": "failed",
        "error": result.get("error", "Rerun failed."),
    }


def _render_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and rerun failed JARVIS agent runs.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List recent failed runs.")
    list_parser.add_argument("--limit", type=int, default=20)

    show_parser = sub.add_parser("show", help="Show one failed run by request id.")
    show_parser.add_argument("request_id")

    rerun_parser = sub.add_parser("rerun", help="Rerun one failed run by request id.")
    rerun_parser.add_argument("request_id")

    args = parser.parse_args(argv)
    if args.command == "list":
        runs = list_failed_runs(limit=args.limit)
        payload: Any = {"failed_runs": runs, "count": len(runs)}
        if not runs:
            payload["message"] = "No failed runs found."
        print(_render_json(payload))
        return 0
    if args.command == "show":
        payload = inspect_failed_run(args.request_id)
        print(_render_json(payload))
        return 0 if payload.get("ok") else 1
    if args.command == "rerun":
        payload = rerun_failed_run(args.request_id)
        print(_render_json(payload))
        return 0 if payload.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
