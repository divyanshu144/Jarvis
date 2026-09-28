"""Tests for DPIA actions A1–A8. No network, OAuth, audio, or macOS automation."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

for _module_name, _class_name in (("openai", "OpenAI"), ("groq", "Groq"), ("anthropic", "Anthropic")):
    if _module_name not in sys.modules:
        _module = types.ModuleType(_module_name)
        setattr(_module, _class_name, object)
        if _module_name == "openai":
            _module.APITimeoutError = TimeoutError
            _module.APIConnectionError = ConnectionError
        sys.modules[_module_name] = _module

from jarvis.core import confirmation, privacy
from jarvis.core.config import Config
from jarvis.core.metrics import RoutingResult

_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("JARVIS_LOCAL_ONLY", raising=False)
    monkeypatch.delenv("JARVIS_ALLOW_SCREEN_CAPTURE", raising=False)
    confirmation.store.clear()
    yield
    confirmation.store.clear()


@pytest.fixture
def local_only(monkeypatch):
    monkeypatch.setattr(Config, "privacy_local_only", property(lambda self: True))


# ── A1: local-only mode ───────────────────────────────────────────────────────

def test_local_only_withholds_sensitive_output_from_cloud_tiers(local_only):
    from jarvis.core.router import _tool_content

    content = _tool_content("gmail", "From: boss\nSalary review attached", cloud=True)
    assert "Salary" not in content
    assert "withheld" in content


def test_local_only_keeps_sensitive_output_for_local_tier(local_only):
    from jarvis.core.router import _tool_content

    content = _tool_content("gmail", "From: boss\nSalary review attached", cloud=False)
    assert "Salary review" in content


def test_local_only_still_sends_public_web_content(local_only):
    from jarvis.core.router import _tool_content

    assert "BBC headline" in _tool_content("web_search", "BBC headline", cloud=True)


def test_cloud_tiers_get_content_when_local_only_off():
    from jarvis.core.router import _tool_content

    assert "Salary" in _tool_content("gmail", "Salary review", cloud=True)


def test_local_only_withholds_prior_tier_previews(local_only):
    from jarvis.core.router import _prior_context

    ctx = _prior_context([{"tool": "clipboard", "result": "bank pin 4321"}])
    assert "4321" not in ctx
    assert "withheld" in ctx


def test_local_only_blocks_screen_vision(local_only, monkeypatch):
    from jarvis.core.tool_safety import check_tool_safety

    monkeypatch.setenv("JARVIS_ALLOW_SCREEN_CAPTURE", "1")
    result = check_tool_safety("screen_vision", {})
    assert not result.allowed
    assert "local-only" in result.reason


def test_local_only_env_override(monkeypatch):
    monkeypatch.setenv("JARVIS_LOCAL_ONLY", "1")
    assert Config().privacy_local_only


def test_local_only_keeps_tts_off_elevenlabs(local_only, monkeypatch):
    from jarvis.core import tts

    spoken = []
    monkeypatch.setattr(Config, "tts_provider", property(lambda self: "auto"))
    monkeypatch.setattr(Config, "elevenlabs_key", property(lambda self: "el-key"))
    monkeypatch.setattr(tts, "_EL_AVAILABLE", True)
    monkeypatch.setattr(tts, "_speak_elevenlabs", lambda text: pytest.fail("ElevenLabs must not be used"))
    monkeypatch.setattr(tts, "_speak_local", lambda text, provider=None: spoken.append(text))

    tts.speak("Your 3pm is with the lawyer.")
    assert spoken == ["Your 3pm is with the lawyer."]


# ── A4: least-privilege OAuth ─────────────────────────────────────────────────

def test_oauth_scopes_are_least_privilege():
    from jarvis.tools._google_auth import SCOPES

    assert set(SCOPES) == {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/calendar.events",
    }


def test_old_broad_token_is_detected(tmp_path):
    from jarvis.tools._google_auth import token_has_excess_scopes

    token = tmp_path / "token.json"
    token.write_text(json.dumps({"scopes": ["https://www.googleapis.com/auth/gmail.modify"]}))
    assert token_has_excess_scopes(token)
    token.write_text(json.dumps({"scopes": ["https://www.googleapis.com/auth/gmail.readonly"]}))
    assert not token_has_excess_scopes(token)


def test_revoke_and_remove_token(tmp_path, monkeypatch):
    from jarvis.tools import _google_auth

    token = tmp_path / "token.json"
    token.write_text(json.dumps({"refresh_token": "1//refresh", "scopes": []}))
    sent = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=10):
        sent["url"] = req.full_url
        sent["body"] = req.data
        return _Resp()

    monkeypatch.setattr(_google_auth.urllib.request, "urlopen", fake_urlopen)
    assert _google_auth.revoke_and_remove_token(token)
    assert sent["url"] == "https://oauth2.googleapis.com/revoke"
    assert b"token=1%2F%2Frefresh" in sent["body"]
    assert not token.exists()


def test_gmail_tool_no_longer_offers_mark_read():
    from jarvis.tools import gmail

    assert "mark_read" not in gmail.DEFINITION["input_schema"]["properties"]["action"]["enum"]


# ── A5: shell/code confirmation ───────────────────────────────────────────────

@pytest.mark.parametrize(("tool", "params"), [("shell_exec", {"command": "ls"}), ("code_exec", {"code": "print(1)"})])
def test_exec_tools_require_confirmation(tool, params):
    from jarvis.core.tool_safety import requires_confirmation

    assert requires_confirmation(tool, params)
    assert confirmation.describe_action(tool, params).startswith("run ")


# ── A2 / A8: export, forget, redact existing data ────────────────────────────

def _seed_db(db: Path) -> None:
    from jarvis.core.memory import LongTermMemory
    from jarvis.core import tracing

    mem = LongTermMemory(db)
    # Insert raw rows directly, as pre-hardening code did.
    mem._conn.execute(
        "INSERT INTO conversations VALUES (?,?,?,?,?,?)",
        ("t1", time.time(), f"my key is ANTHROPIC_API_KEY={_KEY}", "pineapple noted", "", None),
    )
    mem._conn.execute("INSERT INTO user_profile VALUES ('coffee', 'oat flat white')")
    mem._conn.execute("CREATE TABLE routing_metrics (id INTEGER PRIMARY KEY, timestamp REAL, query TEXT)")
    mem._conn.execute("INSERT INTO routing_metrics (timestamp, query) VALUES (?, ?)", (time.time(), f"token={_KEY}"))
    mem._conn.commit()
    conn = tracing._connect(db)
    conn.execute(
        "INSERT INTO agent_runs (request_id, user_message, created_at) VALUES ('r1', ?, ?)",
        (f"password=hunter2 {_KEY}", time.time()),
    )
    conn.commit()
    conn.close()


def _seed_logs(log_dir: Path) -> None:
    log_dir.mkdir()
    (log_dir / "jarvis.log").write_text(
        "2026-09-01 10:00:00 [INFO] jarvis: User: email my landlord about the leak\n"
        "2026-09-01 10:00:05 [INFO] jarvis: JARVIS: Here is the draft.\n"
        "Dear Sam, the kitchen is flooded.\n"
        "2026-09-01 10:00:06 [INFO] jarvis.core.router: Tier 1 executed: gmail\n"
        f"2026-09-01 10:00:07 [INFO] jarvis.tools.shell: shell_exec: 'export ANTHROPIC_API_KEY={_KEY}'\n"
        "2026-09-01 10:00:08 [INFO] jarvis: User: <12 chars, content not logged>\n"
    )
    (log_dir / "jarvis.log.2026-08-31").write_text("2026-08-31 09:00:00 [INFO] jarvis: User: old secret plan\n")


def test_export_user_data_writes_private_json(tmp_path):
    db = tmp_path / "jarvis.db"
    _seed_db(db)

    path = privacy.export_user_data(db_path=db, out_dir=tmp_path / "exports")

    data = json.loads(path.read_text())
    assert data["tables"]["user_profile"] == [{"key": "coffee", "value": "oat flat white"}]
    assert len(data["tables"]["conversations"]) == 1
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_forget_user_data_deletes_everything(tmp_path):
    db = tmp_path / "jarvis.db"
    _seed_db(db)
    _seed_logs(tmp_path / "logs")

    counts = privacy.forget_user_data(db_path=db, chroma_path=tmp_path / "chroma", log_dir=tmp_path / "logs")

    conn = sqlite3.connect(db)
    for table in ("conversations", "user_profile", "agent_runs", "routing_metrics"):
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, table
    assert conn.execute("SELECT count(*) FROM conversations_fts WHERE conversations_fts MATCH 'pineapple'").fetchone()[0] == 0
    assert (tmp_path / "logs" / "jarvis.log").read_text() == ""
    assert not (tmp_path / "logs" / "jarvis.log.2026-08-31").exists()
    assert counts["conversations"] == 1


def test_redact_log_text_replaces_content_and_secrets():
    raw = (
        "2026-09-01 10:00:00 [INFO] jarvis: User: email my landlord about the leak\n"
        "2026-09-01 10:00:05 [INFO] jarvis: JARVIS: Here is the draft.\n"
        "Dear Sam, the kitchen is flooded.\n"
        "2026-09-01 10:00:06 [INFO] jarvis.core.router: Tier 1 executed: gmail\n"
        f"2026-09-01 10:00:07 [INFO] jarvis.tools.shell: shell_exec: 'export ANTHROPIC_API_KEY={_KEY}'\n"
        "2026-09-01 10:00:08 [INFO] jarvis: User: <12 chars, content not logged>\n"
    )
    out, changed = privacy.redact_log_text(raw)

    assert "landlord" not in out
    assert "kitchen is flooded" not in out
    assert "Here is the draft" not in out
    assert _KEY not in out
    assert "Tier 1 executed: gmail" in out
    assert "User: <12 chars, content not logged>" in out
    assert changed == 3


def test_redact_existing_data_keeps_history_but_removes_secrets(tmp_path):
    db = tmp_path / "jarvis.db"
    _seed_db(db)
    _seed_logs(tmp_path / "logs")

    counts = privacy.redact_existing_data(db_path=db, chroma_path=tmp_path / "chroma", log_dir=tmp_path / "logs")

    conn = sqlite3.connect(db)
    user_msg, assistant = conn.execute("SELECT user_msg, assistant FROM conversations").fetchone()
    assert _KEY not in user_msg and "[REDACTED]" in user_msg
    assert assistant == "pineapple noted"
    assert conn.execute("SELECT count(*) FROM conversations_fts WHERE conversations_fts MATCH 'pineapple'").fetchone()[0] == 1
    assert _KEY not in conn.execute("SELECT query FROM routing_metrics").fetchone()[0]
    assert "hunter2" not in conn.execute("SELECT user_message FROM agent_runs").fetchone()[0]
    assert conn.execute("SELECT value FROM user_profile").fetchone()[0] == "oat flat white"
    log_text = (tmp_path / "logs" / "jarvis.log").read_text()
    assert "landlord" not in log_text and _KEY not in log_text
    assert "old secret plan" not in (tmp_path / "logs" / "jarvis.log.2026-08-31").read_text()
    assert counts["conversations"] == 1


def test_privacy_cli_forget_requires_yes(capsys):
    from jarvis.tools import privacy_cli

    assert privacy_cli.main(["forget"]) == 2
    assert "--yes" in capsys.readouterr().out


# ── A3 / A7: capture indicator and temp screenshot deletion ──────────────────

def test_screenshot_tool_notifies_capture_listeners(tmp_path, monkeypatch):
    from jarvis.tools import screenshot

    shot = tmp_path / "shot.png"
    monkeypatch.setattr(screenshot, "_SHOT_PATH", shot)
    monkeypatch.setattr(screenshot.subprocess, "run", lambda *a, **k: shot.write_bytes(b"png"))
    seen = []
    monkeypatch.setattr(privacy, "_capture_listeners", [lambda: seen.append("captured")])

    assert "deleted when the request finishes" in screenshot.execute()
    assert seen == ["captured"]


def test_screen_vision_deletes_capture_after_reading(tmp_path, monkeypatch):
    from jarvis.tools import screen_vision

    shot = tmp_path / "vision.png"
    monkeypatch.setattr(screen_vision, "_SHOT_PATH", shot)
    monkeypatch.setattr(screen_vision.subprocess, "run", lambda *a, **k: shot.write_bytes(b"png"))
    monkeypatch.setattr(privacy, "_capture_listeners", [])

    class _Client:
        def __init__(self, api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return types.SimpleNamespace(content=[types.SimpleNamespace(text="A terminal window.")])

    monkeypatch.setattr(sys.modules["anthropic"], "Anthropic", _Client, raising=False)

    assert screen_vision.execute() == "A terminal window."
    assert not shot.exists()


# ── Agent: data-rights commands and screenshot cleanup ───────────────────────

def _agent(monkeypatch):
    from jarvis.core import agent as agent_module
    from jarvis.core.agent import Agent

    events: dict[str, list] = {"turns": [], "routed": [], "finish": []}
    monkeypatch.setattr(agent_module, "new_request_id", lambda: "req-now")
    monkeypatch.setattr(agent_module, "start_agent_run", lambda *a, **k: None)
    monkeypatch.setattr(agent_module, "finish_agent_run", lambda rid, **k: events["finish"].append(k))
    monkeypatch.setattr(agent_module, "record_chat_usage", lambda *a, **k: None)

    class FakeShort:
        cleared = False

        def add(self, role, content):
            pass

        def clear(self):
            FakeShort.cleared = True

    class FakeMemory:
        short = FakeShort()
        semantic = None

        def working_messages(self, n=10):
            return []

        def recall_context(self, text):
            return ""

        def build_system_prompt(self, base):
            return base

        def add_turn(self, user, assistant):
            events["turns"].append((user, assistant))

    class FakeLearner:
        def is_correction(self, text):
            return False

        def corrections_context(self):
            return ""

    class FakeRouter:
        def route(self, user_text, system, history=None, request_id=None):
            events["routed"].append(user_text)
            return RoutingResult("routed", 1, [1], None, 1.0, user_text, chosen_model="m")

    agent = Agent.__new__(Agent)
    agent._learner = FakeLearner()
    agent._memory = FakeMemory()
    agent._router = FakeRouter()
    agent._metrics = types.SimpleNamespace(log=lambda r: None)
    agent._last_user_text = ""
    agent._last_response = ""
    return agent, events, FakeShort


@pytest.mark.parametrize("text", ["export my data", "Jarvis, please export all my data."])
def test_export_command_handled_without_model(monkeypatch, tmp_path, text):
    agent, events, _ = _agent(monkeypatch)
    monkeypatch.setattr(privacy, "export_user_data", lambda: tmp_path / "export.json")

    response = agent.chat(text)

    assert str(tmp_path / "export.json") in response
    assert events["routed"] == []


def test_forget_needs_confirmation_then_deletes(monkeypatch):
    agent, events, short_cls = _agent(monkeypatch)
    calls = []
    monkeypatch.setattr(privacy, "forget_user_data", lambda semantic=None: calls.append(1) or {"conversations": 7})

    prompt = agent.chat("forget everything")
    assert "Say confirm to proceed" in prompt
    assert calls == []
    assert events["routed"] == []

    done = agent.chat("confirm")
    assert calls == [1]
    assert "deleted 7 conversations" in done
    assert short_cls.cleared
    assert events["turns"] == []  # the forget exchange itself is not written back to memory


def test_forget_cancel_deletes_nothing(monkeypatch):
    agent, _, _ = _agent(monkeypatch)
    monkeypatch.setattr(privacy, "forget_user_data", lambda semantic=None: pytest.fail("must not delete"))

    agent.chat("delete my data")
    assert agent.chat("cancel").startswith("Cancelled.")


def test_model_cannot_dispatch_privacy_forget():
    from jarvis.tools import registry

    assert "privacy" not in registry._EXECUTORS
    assert registry.dispatch("privacy", {"action": "forget"}).startswith("Error: unknown tool")


def test_agent_deletes_temp_screenshot_after_request(monkeypatch, tmp_path):
    from jarvis.core import agent as agent_module

    agent, _, _ = _agent(monkeypatch)
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"screen")
    monkeypatch.setattr(agent_module, "_SHOT_PATH", shot)

    agent.chat("what's the weather")
    assert not shot.exists()
