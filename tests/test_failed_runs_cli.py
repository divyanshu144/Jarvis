"""Failed-runs CLI/operator helper tests."""

from __future__ import annotations

from jarvis.core import tracing
from jarvis.tools import failed_runs


def _failed_run(db, request_id="req-failed", message="token=abc123 inspect this"):
    tracing.start_agent_run(request_id, message, db_path=db)
    tracing.finish_agent_run(
        request_id,
        route="tier_cascade",
        chosen_tier=2,
        chosen_model="model-x",
        error="password=hunter2 provider failed",
        error_category="RuntimeError",
        status="failed",
        db_path=db,
    )


def test_list_failed_runs_helper(tmp_path):
    db = tmp_path / "runs.db"
    _failed_run(db)

    rows = failed_runs.list_failed_runs(limit=5, db_path=db)

    assert len(rows) == 1
    assert rows[0]["request_id"] == "req-failed"
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_category"] == "RuntimeError"
    assert rows[0]["chosen_model"] == "model-x"
    assert "abc123" not in rows[0]["message_preview"]
    assert "token=[REDACTED]" in rows[0]["message_preview"]


def test_inspect_failed_run_helper(tmp_path):
    db = tmp_path / "runs.db"
    _failed_run(db)

    payload = failed_runs.inspect_failed_run("req-failed", db_path=db)

    assert payload["ok"] is True
    run = payload["run"]
    assert run["request_id"] == "req-failed"
    assert run["route"] == "tier_cascade"
    assert run["chosen_tier"] == 2
    assert "hunter2" not in run["error"]
    assert "password=[REDACTED]" in run["error"]


def test_missing_request_id_handling():
    assert failed_runs.inspect_failed_run("")["ok"] is False
    assert failed_runs.rerun_failed_run("")["ok"] is False


def test_no_failed_runs_case(tmp_path):
    db = tmp_path / "runs.db"
    tracing.start_agent_run("req-ok", "hello", db_path=db)
    tracing.finish_agent_run("req-ok", final_answer="ok", db_path=db)

    assert failed_runs.list_failed_runs(db_path=db) == []


def test_redacted_content_remains_redacted(tmp_path):
    db = tmp_path / "runs.db"
    _failed_run(db, message="api_key=sk-ant-api03-secretsecretsecretsecret")

    payload = failed_runs.inspect_failed_run("req-failed", db_path=db)
    rendered = str(payload)

    assert "sk-ant" not in rendered
    assert "[REDACTED]" in rendered


def test_rerun_failed_run_helper_success():
    class FakeAgent:
        def rerun_failed_run(self, request_id):
            return {
                "ok": True,
                "request_id": "req-new",
                "parent_request_id": request_id,
                "response": "rerun ok",
            }

    payload = failed_runs.rerun_failed_run("req-old", agent_factory=FakeAgent)

    assert payload["ok"] is True
    assert payload["original_request_id"] == "req-old"
    assert payload["new_request_id"] == "req-new"
    assert payload["rerun_status"] == "success"


def test_rerun_failed_run_helper_failure():
    class FakeAgent:
        _last_request_id = "req-new"
        def rerun_failed_run(self, request_id):
            raise RuntimeError("rerun failed")

    payload = failed_runs.rerun_failed_run("req-old", agent_factory=FakeAgent)

    assert payload["ok"] is False
    assert payload["original_request_id"] == "req-old"
    assert payload["new_request_id"] == "req-new"
    assert payload["rerun_status"] == "failed"
    assert "rerun failed" in payload["error"]


def test_cli_list_no_failed_runs(monkeypatch, capsys):
    monkeypatch.setattr(failed_runs, "list_failed_runs", lambda limit=20: [])

    code = failed_runs.main(["list", "--limit", "3"])
    out = capsys.readouterr().out

    assert code == 0
    assert '"count": 0' in out
    assert "No failed runs found" in out
