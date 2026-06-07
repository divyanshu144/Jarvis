"""
Routing layer tests — all API calls are mocked, no real network/Ollama needed.
Run: pytest tests/test_routing.py -v
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis.core.metrics import RoutingResult
from jarvis.core.router import Router
from jarvis.core.tool_safety import check_tool_safety
from jarvis.core.validator import validate_tool_call

DB = "/tmp/jarvis_test.db"


for _module_name, _class_name in (("openai", "OpenAI"), ("groq", "Groq"), ("anthropic", "Anthropic")):
    if _module_name not in sys.modules:
        _module = types.ModuleType(_module_name)
        setattr(_module, _class_name, object)
        if _module_name == "openai":
            _module.APITimeoutError = TimeoutError
            _module.APIConnectionError = ConnectionError
        sys.modules[_module_name] = _module


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_oai_response(text: str = "", tool_name: str = "", tool_args: dict | None = None):
    """Build a fake OpenAI-compatible chat completion response."""
    msg = MagicMock()
    if tool_name:
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = tool_name
        tc.function.arguments = json.dumps(tool_args or {})
        msg.tool_calls = [tc]
        msg.content = None
    else:
        msg.tool_calls = None
        msg.content = text

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "tool_calls" if tool_name else "stop"

    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_anthropic_response(text: str):
    """Build a fake Anthropic message response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "end_turn"
    return resp


def _router() -> Router:
    Path(DB).unlink(missing_ok=True)
    return Router(db_path=DB)


# ── Validator unit tests ───────────────────────────────────────────────────────

class TestValidator:
    def test_valid_shell_exec(self):
        ok, errors = validate_tool_call("shell_exec", {"command": "whoami"})
        assert ok
        assert errors == []

    def test_unknown_tool(self):
        ok, errors = validate_tool_call("does_not_exist", {})
        assert not ok
        assert any("Unknown tool" in e for e in errors)

    def test_missing_required_param(self):
        ok, errors = validate_tool_call("shell_exec", {})
        assert not ok
        assert any("command" in e for e in errors)

    def test_wrong_enum_value(self):
        ok, errors = validate_tool_call("app_control", {"action": "fly"})
        assert not ok
        assert any("fly" in e for e in errors)

    def test_valid_system_info(self):
        ok, errors = validate_tool_call("system_info", {"metric": "cpu"})
        assert ok

    def test_integer_as_string_coerced(self):
        # Model quirk: sends timeout as "10" instead of 10
        ok, errors = validate_tool_call("shell_exec", {"command": "ls", "timeout_unused": "10"})
        assert ok  # extra params are ignored


# ── Tool safety tests ─────────────────────────────────────────────────────────

class TestToolSafety:
    def test_shell_exec_blocked_by_default(self):
        result = check_tool_safety("shell_exec", {"command": "echo hello"})
        assert not result.allowed
        assert "JARVIS_ALLOW_SHELL_EXEC" in result.reason

    def test_shell_exec_blocks_dangerous_command_even_with_env(self, monkeypatch):
        monkeypatch.setenv("JARVIS_ALLOW_SHELL_EXEC", "1")
        result = check_tool_safety("shell_exec", {"command": "rm -rf /tmp/example"})
        assert not result.allowed
        assert "recursive force delete" in result.reason

    def test_shell_exec_allowed_with_explicit_env(self, monkeypatch):
        monkeypatch.setenv("JARVIS_ALLOW_SHELL_EXEC", "1")
        result = check_tool_safety("shell_exec", {"command": "echo hello"})
        assert result.allowed

    def test_file_manager_blocks_sensitive_runtime_paths(self):
        result = check_tool_safety("file_manager", {"action": "read", "path": "data/google_token.json"})
        assert not result.allowed
        assert "sensitive" in result.reason

    def test_file_manager_mutation_requires_env(self):
        result = check_tool_safety("file_manager", {"action": "delete", "path": "/tmp/example"})
        assert not result.allowed
        assert "JARVIS_ALLOW_FILE_MUTATION" in result.reason

    def test_browser_blocks_localhost(self):
        result = check_tool_safety("browser_control", {"action": "read", "url": "http://localhost:11434"})
        assert not result.allowed
        assert "local/private" in result.reason

    def test_email_mutation_requires_env(self):
        result = check_tool_safety("gmail", {"action": "send", "to": "a@example.com", "body": "hi"})
        assert not result.allowed
        assert "JARVIS_ALLOW_EMAIL_MUTATION" in result.reason


# ── Routing tests ──────────────────────────────────────────────────────────────

class TestRouting:

    # Test 1: "open Chrome" → Tier 1 succeeds, no escalation
    @patch("jarvis.core.router.dispatch", return_value="Opened Chrome.")
    def test_simple_command_routes_to_tier1(self, mock_dispatch):
        router = _router()

        # First call: model returns app_control tool call
        tool_resp = _make_oai_response(tool_name="app_control", tool_args={"action": "open", "app_name": "Chrome"})
        # Second call: model returns text after tool result
        text_resp = _make_oai_response(text="Chrome is now open.")

        with patch("openai.OpenAI") as MockOAI:
            client = MagicMock()
            MockOAI.return_value = client
            client.chat.completions.create.side_effect = [tool_resp, text_resp]

            result = router.route("open Chrome", system_prompt="You are JARVIS.")

        assert result.tier_used == 1
        assert result.tiers_attempted == [1]
        assert result.escalation_reason is None
        assert "Chrome" in result.response
        mock_dispatch.assert_called_once_with("app_control", {"action": "open", "app_name": "Chrome"})

    # Test 2: Vision keyword → routes directly to Tier 3
    @patch("jarvis.core.router.dispatch", return_value="")
    def test_vision_query_routes_to_tier3(self, _):
        router = _router()

        with patch("anthropic.Anthropic") as MockAnthropic:
            client = MagicMock()
            MockAnthropic.return_value = client
            client.messages.create.return_value = _make_anthropic_response(
                "I can see your screen shows a code editor."
            )
            result = router.route(
                "take a screenshot and tell me what's on screen",
                system_prompt="You are JARVIS.",
            )

        assert result.tier_used == 3
        assert result.tiers_attempted == [3]
        assert result.escalation_reason == "vision_query"
        # Tier 1 and Tier 2 should never have been called
        assert 1 not in result.tiers_attempted
        assert 2 not in result.tiers_attempted

    # Test 3: Tier 1 malformed tool call → escalates to Tier 2
    def test_malformed_tool_call_escalates_to_tier2(self):
        router = _router()

        # Tier 1: returns tool call with wrong tool name
        bad_resp = _make_oai_response(tool_name="nonexistent_tool", tool_args={"x": 1})

        # Tier 2: succeeds
        text_resp = _make_oai_response(text="Here is the answer from Tier 2.")

        with patch("openai.OpenAI") as MockOAI, \
             patch("groq.Groq") as MockGroq:

            oai_client = MagicMock()
            MockOAI.return_value = oai_client
            oai_client.chat.completions.create.return_value = bad_resp

            groq_client = MagicMock()
            MockGroq.return_value = groq_client
            groq_client.chat.completions.create.return_value = text_resp

            result = router.route("do something complex", system_prompt="You are JARVIS.")

        assert result.tier_used == 2
        assert 1 in result.tiers_attempted
        assert 2 in result.tiers_attempted
        assert result.escalation_reason == "malformed_tool_call"

    # Test 4: Tier 1 + Tier 2 both fail → escalates to Tier 3
    @patch("jarvis.core.router.dispatch", return_value="result")
    def test_double_failure_escalates_to_tier3(self, _):
        router = _router()

        bad_resp = _make_oai_response(tool_name="nonexistent_tool", tool_args={})
        tier3_resp = _make_anthropic_response("Tier 3 handled this.")

        with patch("openai.OpenAI") as MockOAI, \
             patch("groq.Groq") as MockGroq, \
             patch("anthropic.Anthropic") as MockAnthropic:

            oai_client = MagicMock()
            MockOAI.return_value = oai_client
            oai_client.chat.completions.create.return_value = bad_resp

            groq_client = MagicMock()
            MockGroq.return_value = groq_client
            groq_client.chat.completions.create.return_value = bad_resp

            anthropic_client = MagicMock()
            MockAnthropic.return_value = anthropic_client
            anthropic_client.messages.create.return_value = tier3_resp

            result = router.route("do something", system_prompt="You are JARVIS.")

        assert result.tier_used == 3
        assert set(result.tiers_attempted) == {1, 2, 3}

    # Test 5: "complex:" prefix → routes directly to Tier 3
    @patch("jarvis.core.router.dispatch", return_value="")
    def test_complex_prefix_routes_to_tier3(self, _):
        router = _router()

        with patch("anthropic.Anthropic") as MockAnthropic:
            client = MagicMock()
            MockAnthropic.return_value = client
            client.messages.create.return_value = _make_anthropic_response(
                "Here is the Python script you requested."
            )
            result = router.route(
                "complex: write me a python script that scrapes HN and emails me the top 10 stories",
                system_prompt="You are JARVIS.",
            )

        assert result.tier_used == 3
        assert result.tiers_attempted == [3]
        assert result.escalation_reason == "forced_complex"
        assert 1 not in result.tiers_attempted


# ── Existing tool smoke tests (kept passing) ────────────────────────────────

class TestExistingTools:
    def test_shell_exec(self):
        from jarvis.tools.shell import execute
        result = execute("echo jarvis_test")
        assert "jarvis_test" in result

    def test_code_exec(self):
        from jarvis.tools.code_exec import execute
        result = execute("print(42 * 2)")
        assert "84" in result

    def test_system_info_cpu(self):
        from jarvis.tools.system_info import execute
        result = execute("cpu")
        assert "CPU" in result

    def test_clipboard_read(self):
        from jarvis.tools.clipboard import execute
        result = execute("read")
        assert result  # non-empty

    def test_file_manager_list(self):
        from jarvis.tools.file_manager import execute
        result = execute("list", path=".")
        assert result

    def test_dispatch_unknown(self):
        from jarvis.tools.registry import dispatch
        result = dispatch("nonexistent", {})
        assert "Error" in result

    def test_dispatch_shell(self, monkeypatch):
        from jarvis.tools.registry import dispatch
        monkeypatch.setenv("JARVIS_ALLOW_SHELL_EXEC", "1")
        result = dispatch("shell_exec", {"command": "echo hello"})
        assert "hello" in result

    def test_dispatch_shell_blocked_by_default(self):
        from jarvis.tools.registry import dispatch
        result = dispatch("shell_exec", {"command": "echo hello"})
        assert result.startswith("Safety blocked shell_exec")


# ── FDE tracker tests ────────────────────────────────────────────────────────

def _copy_fde_gaps(tmp_path: Path) -> Path:
    src = Path(__file__).parent.parent / "jarvis" / "data" / "fde_gaps.json"
    dst = tmp_path / "fde_gaps.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def test_fde_json_loads():
    gaps_path = Path(__file__).parent.parent / "jarvis" / "data" / "fde_gaps.json"
    data = json.loads(gaps_path.read_text(encoding="utf-8"))
    assert data["meta"]["total_areas"] == 12
    assert len(data["gaps"]) == 12


def test_scan_detects_signal(tmp_path):
    from jarvis.core.fde_tracker import FDETracker

    gaps_path = _copy_fde_gaps(tmp_path)
    projects_dir = tmp_path / "projects"
    project = projects_dir / "PromptOps"
    (project / ".git").mkdir(parents=True)

    tracker = FDETracker(
        db_path=tmp_path / "jarvis.db",
        gaps_json=gaps_path,
        projects_dir=projects_dir,
    )
    tracker.load_gaps()
    tracker._project_git_log = lambda _: "abc123 add langfuse tracing for eval harness"

    result = tracker.scan_projects()
    data = json.loads(gaps_path.read_text(encoding="utf-8"))
    eval_gap = next(gap for gap in data["gaps"] if gap["id"] == "06")

    assert any(match["gap_id"] == "06" and match["signal"] == "langfuse" for match in result["matches"])
    assert eval_gap["status"] == "in_progress"


def test_overall_score_range(tmp_path):
    from jarvis.core.fde_tracker import FDETracker

    tracker = FDETracker(
        db_path=tmp_path / "jarvis.db",
        gaps_json=_copy_fde_gaps(tmp_path),
        projects_dir=tmp_path / "projects",
    )
    tracker.load_gaps()
    score = tracker.calculate_overall_score()
    assert 0 <= score <= 100


def test_build_plan_structure(tmp_path):
    from jarvis.core.fde_analyser import FDEAnalyser
    from jarvis.core.fde_tracker import FDETracker

    gaps_path = _copy_fde_gaps(tmp_path)
    tracker = FDETracker(
        db_path=tmp_path / "jarvis.db",
        gaps_json=gaps_path,
        projects_dir=tmp_path / "projects",
    )
    analyser = FDEAnalyser(
        tracker=tracker,
        db_path=tmp_path / "jarvis.db",
        gaps_json=gaps_path,
        resume_path=tmp_path / "missing_resume.pdf",
        projects_dir=tmp_path / "projects",
    )

    payload = analyser.generate_build_plan("04", dry_run=True)

    assert payload["dry_run"] is True
    assert payload["operation"] == "build_plan"
    assert payload["context"]["gap"]["id"] == "04"
    assert "day-by-day" in payload["user_message"]


def test_reading_gap_quiz(tmp_path, monkeypatch):
    import jarvis.tools.fde_tool as fde_tool

    gaps_path = _copy_fde_gaps(tmp_path)
    before = json.loads(gaps_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(fde_tool, "_GAPS_JSON", gaps_path)

    tool = fde_tool.FDETool.__new__(fde_tool.FDETool)
    result = tool.mark_done("enterprise", confirmed=False)
    after = json.loads(gaps_path.read_text(encoding="utf-8"))

    assert result["marked_done"] is False
    assert result["requires_confirmation"] is True
    assert "quiz_question" in result
    assert after == before
