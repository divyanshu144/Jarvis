"""Observability tracing tests."""

from __future__ import annotations

import json
import sqlite3

from jarvis.core import tracing


def _row(db_path, table):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row


def test_new_request_id_unique():
    first = tracing.new_request_id()
    second = tracing.new_request_id()
    assert first != second
    assert len(first) >= 16


def test_start_and_finish_agent_run(tmp_path):
    db = tmp_path / "trace.db"
    request_id = tracing.new_request_id()

    tracing.start_agent_run(request_id, "hello", db_path=db)
    tracing.finish_agent_run(
        request_id,
        route="tier_cascade",
        intent="default",
        chosen_tier=1,
        chosen_model="qwen",
        tools_executed=[{"tool": "weather", "result": "sunny"}],
        final_answer="done",
        latency_ms=12.5,
        db_path=db,
    )

    row = _row(db, "agent_runs")
    assert row["request_id"] == request_id
    assert row["user_message"] == "hello"
    assert row["route"] == "tier_cascade"
    assert row["chosen_tier"] == 1
    assert row["chosen_model"] == "qwen"
    assert json.loads(row["tools_executed"])[0]["tool"] == "weather"
    assert row["final_answer"] == "done"


def test_record_tool_run_redacts_and_truncates(tmp_path):
    db = tmp_path / "trace.db"
    request_id = tracing.new_request_id()
    long_text = "x" * 3000

    tracing.record_tool_run(
        request_id,
        "web_search",
        {"api_key": "sk-ant-api03-secretvalue", "query": long_text},
        status="ok",
        result_summary=long_text,
        latency_ms=3.0,
        db_path=db,
    )

    row = _row(db, "tool_runs")
    args = json.loads(row["tool_args_json"])
    assert args["api_key"] == "[REDACTED]"
    assert "truncated" in args["query"]
    assert "truncated" in row["result_summary"]


def test_record_safety_block(tmp_path):
    db = tmp_path / "trace.db"
    tracing.record_safety_block(
        "req-1",
        "shell_exec",
        {"command": "rm -rf build"},
        "recursive force delete",
        db_path=db,
    )

    row = _row(db, "tool_runs")
    assert row["request_id"] == "req-1"
    assert row["status"] == "safety_blocked"
    assert "recursive force delete" in row["error"]


def test_tracing_failures_do_not_crash(monkeypatch):
    def fail_connect(*_, **__):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(tracing, "_connect", fail_connect)

    tracing.start_agent_run("req", "hello")
    tracing.finish_agent_run("req", error="boom")
    tracing.record_tool_run("req", "weather", {}, status="ok")
    tracing.record_safety_block("req", "shell_exec", {}, "blocked")

def test_agent_chat_generates_and_passes_request_id(monkeypatch):
    from jarvis.core.agent import Agent
    from jarvis.core.metrics import RoutingResult
    import jarvis.core.agent as agent_module

    events = []
    monkeypatch.setattr(agent_module, "new_request_id", lambda: "req-agent")
    monkeypatch.setattr(agent_module, "start_agent_run", lambda request_id, user_message: events.append(("start", request_id, user_message)))
    monkeypatch.setattr(agent_module, "finish_agent_run", lambda request_id, **kwargs: events.append(("finish", request_id, kwargs)))

    class FakeLearner:
        def is_correction(self, text):
            return False
        def corrections_context(self):
            return ""

    class FakeShort:
        def add(self, role, content):
            pass

    class FakeMemory:
        short = FakeShort()
        def working_messages(self, n=10):
            return []
        def recall_context(self, text):
            return ""
        def build_system_prompt(self, base):
            return base
        def add_turn(self, user, assistant):
            pass

    class FakeRouter:
        def route(self, user_text, system, history=None, request_id=None):
            assert request_id == "req-agent"
            return RoutingResult("answer", 1, [1], None, 4.0, user_text, chosen_model="model-x")

    class FakeMetrics:
        def log(self, result):
            pass

    agent = Agent.__new__(Agent)
    agent._learner = FakeLearner()
    agent._memory = FakeMemory()
    agent._router = FakeRouter()
    agent._metrics = FakeMetrics()
    agent._last_user_text = ""
    agent._last_response = ""

    assert agent.chat("hello") == "answer"
    assert events[0] == ("start", "req-agent", "hello")
    assert events[1][0] == "finish"
    assert events[1][1] == "req-agent"
    assert events[1][2]["chosen_tier"] == 1


def test_dispatch_records_tool_run_when_request_id(monkeypatch):
    from jarvis.tools import registry

    calls = []
    monkeypatch.setitem(registry._EXECUTORS, "unit_tool", lambda **kwargs: "unit result")
    monkeypatch.setattr(registry, "check_tool_safety", lambda *_: type("Safety", (), {"allowed": True, "reason": ""})())
    monkeypatch.setattr(registry, "record_tool_run", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = registry.dispatch("unit_tool", {"api_key": "secret", "x": 1}, request_id="req-tool")

    assert result == "unit result"
    assert calls
    assert calls[0][0][0] == "req-tool"
    assert calls[0][0][1] == "unit_tool"
    assert calls[0][1]["status"] == "ok"

def test_redacts_common_free_text_secret_patterns():
    examples = [
        ("password: hunter2", "password: [REDACTED]"),
        ("token=abc123", "token=[REDACTED]"),
        ("api key is sk-ant-api03-supersecretvalue", "api key is [REDACTED]"),
        ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz", "Authorization: [REDACTED]"),
        ("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz", "OPENAI_API_KEY=[REDACTED]"),
        ("ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwxyz", "ANTHROPIC_API_KEY=[REDACTED]"),
        ("GROQ_API_KEY=gsk_abcdefghijklmnopqrstuvwxyz", "GROQ_API_KEY=[REDACTED]"),
        ("x-api-key: abcdefghijklmnop", "x-api-key: [REDACTED]"),
        ("sessionid=abcdef1234567890", "sessionid=[REDACTED]"),
    ]
    for raw, expected in examples:
        assert expected in tracing.sanitize_value(raw)


def test_sensitive_tool_outputs_are_redacted(tmp_path):
    db = tmp_path / "trace.db"
    private_output = "From: alice@example.com\nSubject: private deal\nBody: salary and personal data"

    for tool_name in ["gmail", "google_calendar", "screen_vision", "browser_control", "file_manager", "clipboard", "shell_exec"]:
        tracing.record_tool_run(
            "req-sensitive",
            tool_name,
            {"query": "private"},
            status="ok",
            result_summary=private_output,
            db_path=db,
        )

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT tool_name, result_summary FROM tool_runs ORDER BY id").fetchall()
    conn.close()

    assert rows
    for row in rows:
        summary = row["result_summary"]
        assert "redacted for privacy" in summary
        assert "alice@example.com" not in summary
        assert "salary" not in summary


def test_non_sensitive_output_is_summarized_redacted_and_truncated(tmp_path):
    db = tmp_path / "trace.db"
    output = "normal token=abc123 " + "x" * 3000
    tracing.record_tool_run(
        "req-normal",
        "weather",
        {},
        status="ok",
        result_summary=output,
        db_path=db,
    )

    row = _row(db, "tool_runs")
    assert "normal" in row["result_summary"]
    assert "truncated" in row["result_summary"]
    assert "abc123" not in row["result_summary"]
    assert "token=[REDACTED]" in row["result_summary"]


def test_prune_traces_removes_old_rows_and_keeps_recent(tmp_path):
    db = tmp_path / "trace.db"
    old = tracing.time.time() - 40 * 86400
    recent = tracing.time.time()
    conn = sqlite3.connect(str(db))
    tracing._ensure_schema(conn)
    conn.execute("INSERT INTO agent_runs(request_id, created_at) VALUES(?, ?)", ("old-agent", old))
    conn.execute("INSERT INTO agent_runs(request_id, created_at) VALUES(?, ?)", ("new-agent", recent))
    conn.execute("INSERT INTO tool_runs(request_id, tool_name, status, created_at) VALUES(?, ?, ?, ?)", ("old-agent", "weather", "ok", old))
    conn.execute("INSERT INTO tool_runs(request_id, tool_name, status, created_at) VALUES(?, ?, ?, ?)", ("new-agent", "weather", "ok", recent))
    conn.commit()
    conn.close()

    deleted = tracing.prune_traces(days_to_keep=30, db_path=db)

    conn = sqlite3.connect(str(db))
    remaining_agents = [row[0] for row in conn.execute("SELECT request_id FROM agent_runs ORDER BY request_id")]
    remaining_tools = [row[0] for row in conn.execute("SELECT request_id FROM tool_runs ORDER BY request_id")]
    conn.close()

    assert deleted["agent_runs"] == 1
    assert deleted["tool_runs"] == 1
    assert remaining_agents == ["new-agent"]
    assert remaining_tools == ["new-agent"]


def test_prune_traces_max_rows_keeps_newest(tmp_path):
    db = tmp_path / "trace.db"
    conn = sqlite3.connect(str(db))
    tracing._ensure_schema(conn)
    now = tracing.time.time()
    for idx in range(3):
        created_at = now + idx
        conn.execute("INSERT INTO agent_runs(request_id, created_at) VALUES(?, ?)", (f"agent-{idx}", created_at))
        conn.execute("INSERT INTO tool_runs(request_id, tool_name, status, created_at) VALUES(?, ?, ?, ?)", (f"tool-{idx}", "weather", "ok", created_at))
    conn.commit()
    conn.close()

    tracing.prune_traces(days_to_keep=3650, max_rows=1, db_path=db)

    conn = sqlite3.connect(str(db))
    agents = [row[0] for row in conn.execute("SELECT request_id FROM agent_runs")]
    tools = [row[0] for row in conn.execute("SELECT request_id FROM tool_runs")]
    conn.close()

    assert agents == ["agent-2"]
    assert tools == ["tool-2"]

