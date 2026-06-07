"""
3-tier routing engine for JARVIS.

Tier 1  — Ollama qwen2.5:3b  (local, instant, free)
Tier 2  — Groq Llama 4 Scout  (cloud free, fallback)
Tier 3  — Claude Sonnet        (premium, terminal)

Routing order:
  vision/complex: keywords → Tier 3 directly
  "complex:" prefix        → Tier 3 directly
  "quick:" prefix          → Tier 1, no escalation
  everything else          → Tier 1 → Tier 2 → Tier 3
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger
from jarvis.core.metrics import RoutingResult
from jarvis.core.validator import log_failure, validate_tool_call
from jarvis.tools.registry import TOOL_DEFINITIONS, dispatch

log = get_logger(__name__)

_CAPABILITY_PHRASES = [
    "i cannot", "i don't have", "i'm unable", "as an ai",
    "i am unable", "i do not have access", "i can't access",
    "i don't have the ability",
]

_MAX_TOOL_ITERS = 8  # guard against infinite tool-call loops

# Queries where Tier 1 (qwen2.5:3b) is reliably wrong → go straight to Tier 2
_TIER2_DIRECT = re.compile(
    r"play\s+\S.+\s+by\s+\S"        # "play <song> by <artist>"
    r"|play\s+\S.+\s+on\s+spotify"  # "play <song> on spotify"
    r"|spotify.*search"              # "spotify search ..."
    r"|search.*spotify"              # "search spotify for ..."
    r"|open\s+maps?"                 # "open maps / map"
    r"|navigate\s+to\b"             # "navigate to ..."
    r"|directions?\s+to\b"          # "directions to ..."
    r"|get\s+directions"            # "get directions"
    r"|facetime\s+\S"               # "facetime <person>"
    r"|remind\s+me\b"               # "remind me to ..."
    r"|set\s+a?\s*reminder",        # "set a reminder"
    re.IGNORECASE,
)


# ── Internal attempt result ───────────────────────────────────────────────────

@dataclass
class _Attempt:
    success: bool
    response: str = ""
    escalation_reason: Optional[str] = None
    executed_tools: list[dict[str, str]] = field(default_factory=list)


# ── OpenAI-compatible tool definitions (Ollama + Groq) ───────────────────────

_OAI_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": d["name"],
            "description": d["description"],
            "parameters": d["input_schema"],
        },
    }
    for d in TOOL_DEFINITIONS
]

# Tier 1 gets a slim subset — fast local tools only (qwen2.5:3b times out with 18 tools)
_TIER1_TOOL_NAMES = {"system_control", "system_info", "weather", "timer", "clipboard", "app_control"}
_TIER1_TOOLS = [t for t in _OAI_TOOLS if t["function"]["name"] in _TIER1_TOOL_NAMES]

# Detect when Tier 2 outputs a tool call as plain text instead of invoking it
_UNEXEC_TOOL_RE = re.compile(
    r'^\s*(?:apple_music|app_control|browser_control|calendar|clipboard|code_exec'
    r'|file_manager|gmail|google_calendar|screen_vision|screenshot|shell_exec'
    r'|spotlight|system_control|system_info|timer|weather|web_search)\s*\(',
    re.IGNORECASE,
)

# Trailing confirmation questions to strip from all responses
_CONFIRM_RE = re.compile(
    r'\s*(?:Would you like[^.?!]*\?|Shall I[^.?!]*\?|Do you want[^.?!]*\?'
    r'|Should I[^.?!]*\?|Is there anything else[^.?!]*\?)\s*$',
    re.IGNORECASE,
)


def _has_capability_limit(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _CAPABILITY_PHRASES)


def _elapsed_ms(start: float) -> float:
    return (time.monotonic() - start) * 1000


_NUM_WORDS = ["First", "Second", "Third", "Fourth", "Fifth",
              "Sixth", "Seventh", "Eighth", "Ninth", "Tenth"]


def _strip_markdown(text: str) -> str:
    """Remove markdown so spoken responses sound natural."""
    # **bold** / *italic* / ***both***
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    # # Headings
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # `inline code`
    text = re.sub(r'`([^`\n]+)`', r'\1', text)
    # [link text](url) → link text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Numbered list: "1. " → "First, "
    def _num(m: re.Match) -> str:
        n = int(m.group(1))
        return (_NUM_WORDS[n - 1] + ", ") if n <= len(_NUM_WORDS) else ""
    text = re.sub(r'^\s*(\d+)\.\s+', _num, text, flags=re.MULTILINE)
    # Bullet points
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    # Collapse extra blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _strip_confirmation(text: str) -> str:
    """Remove trailing 'Would you like me to...?' confirmation questions."""
    return _CONFIRM_RE.sub('', text).strip()


def _clean(text: str) -> str:
    return _strip_confirmation(_strip_markdown(text))


def _prior_context(executed: list[dict]) -> str:
    if not executed:
        return ""
    lines = ["Tools already executed by previous tier:"]
    for e in executed:
        lines.append(f"  - {e['tool']}() → {e['result'][:120]}")
    return "\n".join(lines)


# ── Router ────────────────────────────────────────────────────────────────────

class Router:
    """Orchestrates query routing across all three tiers."""

    def __init__(
        self,
        db_path: str,
        on_tool_call: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._db = db_path
        self._on_tool_call = on_tool_call
        # Lazy-init learning engine to avoid import cycle
        self._learner: Any = None

    def _learning(self):
        if self._learner is None:
            from jarvis.core.learning import LearningEngine
            self._learner = LearningEngine(self._db)
        return self._learner

    # ── Public entry point ────────────────────────────────────────────────────

    def route(
        self,
        query: str,
        system_prompt: str,
        history: list[dict] | None = None,
    ) -> RoutingResult:
        """Route a query through the tier cascade and return a RoutingResult."""
        start = time.monotonic()
        clean = query.strip()
        lower = clean.lower()
        history = history or []

        # ── Hard routing rules ────────────────────────────────────────────────

        # Vision / screen queries → Tier 3 directly
        if any(p in lower for p in cfg.tier3_patterns):
            log.info("Router: vision keyword → Tier 3 directly")
            resp = self._tier3(clean, system_prompt, "vision_query", [], [], history)
            return RoutingResult(resp, 3, [3], "vision_query", _elapsed_ms(start), clean)

        # "complex:" prefix → Tier 3 directly
        if lower.startswith("complex:"):
            actual = clean[8:].strip()
            log.info("Router: 'complex:' prefix → Tier 3 directly")
            resp = self._tier3(actual, system_prompt, "forced_complex", [], [], history)
            return RoutingResult(resp, 3, [3], "forced_complex", _elapsed_ms(start), actual)

        # "quick:" prefix → Tier 1 only, no escalation
        if lower.startswith("quick:"):
            actual = clean[6:].strip()
            log.info("Router: 'quick:' prefix → Tier 1, no escalation")
            attempt = self._tier1(actual, system_prompt, history)
            resp = attempt.response or f"[Tier 1 unavailable: {attempt.escalation_reason}]"
            return RoutingResult(resp, 1, [1], attempt.escalation_reason, _elapsed_ms(start), actual)

        # ── Queries where Tier 1 is known-bad → skip to Tier 2 ───────────────

        if _TIER2_DIRECT.search(lower):
            log.info("Router: direct Tier 2 (action query)")
            t2 = self._tier2(clean, system_prompt, "tier2_direct", [], history)
            if t2.success:
                return RoutingResult(t2.response, 2, [2], "tier2_direct", _elapsed_ms(start), clean)
            resp = self._tier3(clean, system_prompt, "tier2_direct", [2], t2.executed_tools, history)
            return RoutingResult(resp, 3, [2, 3], "tier2_direct", _elapsed_ms(start), clean)

        # ── Learning-based tier suggestion ────────────────────────────────────

        suggested = self._learning().suggest_tier(clean)

        # ── Optimistic local-first cascade ────────────────────────────────────

        if suggested == 2:
            log.info("Router: learning → skip to Tier 2")
            t2 = self._tier2(clean, system_prompt, "learned_routing", [], history)
            if t2.success:
                self._learning().record_routing(clean, 2, True)
                return RoutingResult(t2.response, 2, [2], "learned_routing", _elapsed_ms(start), clean)

        log.info("Router: trying Tier 1 (Ollama)")
        t1 = self._tier1(clean, system_prompt, history)
        if t1.success:
            log.info(f"Router: Tier 1 succeeded in {_elapsed_ms(start):.0f}ms")
            self._learning().record_routing(clean, 1, True)
            return RoutingResult(t1.response, 1, [1], None, _elapsed_ms(start), clean)

        self._learning().record_routing(clean, 1, False)
        log.info(f"Router: Tier 1 failed ({t1.escalation_reason}) → Tier 2")
        t2 = self._tier2(clean, system_prompt, t1.escalation_reason or "unknown", t1.executed_tools, history)
        if t2.success:
            log.info(f"Router: Tier 2 succeeded in {_elapsed_ms(start):.0f}ms")
            self._learning().record_routing(clean, 2, True)
            return RoutingResult(t2.response, 2, [1, 2], t1.escalation_reason, _elapsed_ms(start), clean)

        self._learning().record_routing(clean, 2, False)
        log.info(f"Router: Tier 2 failed ({t2.escalation_reason}) → Tier 3")
        prior = t1.executed_tools + t2.executed_tools
        reason = t2.escalation_reason or t1.escalation_reason or "tier2_failed"
        resp = self._tier3(clean, system_prompt, reason, [1, 2], prior, history)
        self._learning().record_routing(clean, 3, True)
        return RoutingResult(resp, 3, [1, 2, 3], reason, _elapsed_ms(start), clean)

    # ── Tier 1 — Ollama ───────────────────────────────────────────────────────

    def _tier1(self, query: str, system_prompt: str, history: list[dict] | None = None) -> _Attempt:
        try:
            from openai import OpenAI, APITimeoutError, APIConnectionError

            client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                timeout=cfg.tier1_timeout_ms / 1000,
            )
            messages: list[dict] = [{"role": "system", "content": system_prompt}]
            messages.extend(history or [])
            messages.append({"role": "user", "content": query})
            executed: list[dict] = []
            iters = 0

            while True:
                iters += 1
                if iters > _MAX_TOOL_ITERS:
                    log.warning("Tier 1: max tool iterations reached")
                    return _Attempt(False, escalation_reason="max_iterations",
                                    executed_tools=executed)

                response = client.chat.completions.create(
                    model=cfg.tier1_model,
                    messages=messages,
                    tools=_TIER1_TOOLS,
                    tool_choice="auto",
                )
                choice = response.choices[0]
                msg = choice.message

                # No tool calls — text response
                if not msg.tool_calls:
                    text = msg.content or ""
                    if not text and executed:
                        # Small model returned empty after tool execution — use tool result directly
                        text = executed[-1]["result"]
                    if not text:
                        # Completely empty response with no tools — escalate
                        log.info("Tier 1: empty response → escalating")
                        return _Attempt(False, escalation_reason="empty_response",
                                        executed_tools=executed)
                    if _has_capability_limit(text) and not executed:
                        log.info("Tier 1: capability limit detected")
                        return _Attempt(False, escalation_reason="capability_limit")
                    return _Attempt(True, response=_clean(text), executed_tools=executed)

                # Validate + execute each tool call
                messages.append(msg)
                tool_results = []
                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        params = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        params = {}

                    valid, errors = validate_tool_call(name, params)
                    if not valid:
                        log.warning(f"Tier 1 validation failed for {name}: {errors}")
                        log_failure(self._db, name, params, errors, tier=1,
                                    raw_response=tc.function.arguments)
                        return _Attempt(False, escalation_reason="malformed_tool_call",
                                        executed_tools=executed)

                    if self._on_tool_call:
                        self._on_tool_call(name, params)
                    result = dispatch(name, params)
                    executed.append({"tool": name, "result": result})
                    log.info(f"Tier 1 executed: {name}")

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result[:1500],
                    })

                messages.extend(tool_results)

        except Exception as e:
            err = str(e)
            if "timed out" in err.lower() or "timeout" in err.lower():
                log.warning(f"Tier 1 timeout: {e}")
                return _Attempt(False, escalation_reason="timeout")
            if "connection" in err.lower() or "refused" in err.lower():
                log.warning(f"Tier 1 Ollama not reachable: {e}")
                return _Attempt(False, escalation_reason="timeout")
            log.warning(f"Tier 1 error: {e}")
            return _Attempt(False, escalation_reason="malformed_tool_call")

    # ── Tier 2 — Groq ────────────────────────────────────────────────────────

    def _tier2(
        self,
        query: str,
        system_prompt: str,
        escalation_reason: str,
        prior_tools: list[dict],
        history: list[dict] | None = None,
    ) -> _Attempt:
        try:
            from groq import Groq

            context = f"\n\n[Escalated from Tier 1. Reason: {escalation_reason}]"
            if prior_tools:
                context += f"\n{_prior_context(prior_tools)}"

            client = Groq(api_key=cfg.groq_key)
            messages: list[dict] = [{"role": "system", "content": system_prompt + context}]
            messages.extend(history or [])
            messages.append({"role": "user", "content": query})
            executed: list[dict] = []
            iters = 0

            while True:
                iters += 1
                if iters > _MAX_TOOL_ITERS:
                    log.warning("Tier 2: max tool iterations reached")
                    return _Attempt(False, escalation_reason="max_iterations",
                                    executed_tools=executed)

                response = client.chat.completions.create(
                    model=cfg.groq_model,
                    max_tokens=cfg.groq_max_tokens,
                    messages=messages,
                    tools=_OAI_TOOLS,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    timeout=cfg.tier2_timeout_ms / 1000,
                )
                choice = response.choices[0]
                msg = choice.message

                if not msg.tool_calls:
                    text = msg.content or ""
                    if not text and executed:
                        text = executed[-1]["result"]
                    if _has_capability_limit(text) and not executed:
                        return _Attempt(False, escalation_reason="capability_limit",
                                        executed_tools=executed)
                    if _UNEXEC_TOOL_RE.match(text):
                        log.warning("Tier 2: plain-text tool call detected → escalating to Tier 3")
                        return _Attempt(False, escalation_reason="unexecuted_tool_call",
                                        executed_tools=executed)
                    return _Attempt(True, response=_clean(text), executed_tools=executed)

                messages.append(msg)
                tool_results = []
                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        params = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        params = {}

                    valid, errors = validate_tool_call(name, params)
                    if not valid:
                        log.warning(f"Tier 2 validation failed for {name}: {errors}")
                        log_failure(self._db, name, params, errors, tier=2,
                                    raw_response=tc.function.arguments)
                        return _Attempt(False, escalation_reason="malformed_tool_call",
                                        executed_tools=executed)

                    if self._on_tool_call:
                        self._on_tool_call(name, params)
                    result = dispatch(name, params)
                    executed.append({"tool": name, "result": result})
                    log.info(f"Tier 2 executed: {name}")

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result[:1500],
                    })

                messages.extend(tool_results)

        except Exception as e:
            log.warning(f"Tier 2 error: {e}")
            return _Attempt(False, escalation_reason="tier2_failed")

    # ── Tier 3 — Claude ───────────────────────────────────────────────────────

    def _tier3(
        self,
        query: str,
        system_prompt: str,
        reason: str,
        tiers_tried: list[int],
        prior_tools: list[dict],
        history: list[dict] | None = None,
    ) -> str:
        context = f"\n\n[Escalated from Tier(s) {tiers_tried}. Reason: {reason}]"
        if prior_tools:
            context += f"\n{_prior_context(prior_tools)}"

        # Try Anthropic first; fall back to Groq if no credits or unavailable
        if cfg.anthropic_key:
            try:
                return self._tier3_anthropic(query, system_prompt + context, reason, history or [])
            except Exception as e:
                err_str = str(e).lower()
                if "credit" in err_str or "billing" in err_str or "balance" in err_str:
                    log.warning("Tier 3: Anthropic has no credits — falling back to Groq")
                else:
                    log.warning(f"Tier 3: Anthropic error ({e}) — falling back to Groq")

        return self._tier3_groq(query, system_prompt + context, history or [])

    def _tier3_anthropic(self, query: str, full_system: str, reason: str, history: list[dict]) -> str:
        import base64
        import anthropic
        from jarvis.core.agent import _SHOT_PATH

        client = anthropic.Anthropic(api_key=cfg.anthropic_key)

        # Build conversation history in Anthropic format
        messages: list[dict] = []
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": [{"type": "text", "text": msg["content"]}],
            })

        user_content: list[dict] = []
        if reason == "vision_query" and _SHOT_PATH.exists():
            data = base64.b64encode(_SHOT_PATH.read_bytes()).decode()
            user_content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": data},
            })
        user_content.append({"type": "text", "text": query})
        messages.append({"role": "user", "content": user_content})
        turn_text = ""
        iters = 0

        while True:
            iters += 1
            if iters > _MAX_TOOL_ITERS:
                log.warning("Tier 3 (Anthropic): max tool iterations reached")
                break

            response = client.messages.create(
                model=cfg.claude_model,
                max_tokens=cfg.claude_max_tokens,
                system=full_system,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            turn_text = ""
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    turn_text += block.text
                elif block.type == "tool_use":
                    tool_uses.append(block)

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn" or not tool_uses:
                return turn_text

            # Parallel tool execution
            def _exec_tool(tu):
                valid, errors = validate_tool_call(tu.name, tu.input)
                if not valid:
                    log.warning(f"Tier 3 validation failed for {tu.name}: {errors}")
                    log_failure(self._db, tu.name, tu.input, errors, tier=3)
                if self._on_tool_call:
                    self._on_tool_call(tu.name, tu.input)
                result = dispatch(tu.name, tu.input)
                log.info(f"Tier 3 (Anthropic) executed: {tu.name}")
                return tu.id, result

            tool_results = []
            if len(tool_uses) == 1:
                tid, result = _exec_tool(tool_uses[0])
                tool_results.append({"type": "tool_result", "tool_use_id": tid, "content": result})
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                    futures = {ex.submit(_exec_tool, tu): tu for tu in tool_uses}
                    for fut in concurrent.futures.as_completed(futures):
                        tid, result = fut.result()
                        tool_results.append({"type": "tool_result", "tool_use_id": tid, "content": result})
            messages.append({"role": "user", "content": tool_results})

        return turn_text

    def _tier3_groq(self, query: str, full_system: str, history: list[dict] | None = None) -> str:
        """Groq fallback for Tier 3 when Anthropic is unavailable."""
        import groq as groq_sdk
        client = groq_sdk.Groq(api_key=cfg.groq_key)
        messages: list[dict] = [{"role": "system", "content": full_system}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": query})
        executed: list[dict] = []
        iters = 0

        while True:
            iters += 1
            if iters > _MAX_TOOL_ITERS:
                log.warning("Tier 3 (Groq): max tool iterations reached")
                return " ".join(e["result"][:80] for e in executed) or ""

            response = client.chat.completions.create(
                model=cfg.groq_model,
                messages=messages,
                tools=_OAI_TOOLS,
                tool_choice="auto",
                max_tokens=cfg.groq_max_tokens,
            )
            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                return _clean(msg.content or "")

            messages.append(msg)
            tool_results = []
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    params = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    params = {}
                valid, errors = validate_tool_call(name, params)
                if not valid:
                    log.warning(f"Tier 3 (Groq) validation failed for {name}: {errors}")
                    log_failure(self._db, name, params, errors, tier=3, raw_response=tc.function.arguments)
                if self._on_tool_call:
                    self._on_tool_call(name, params)
                result = dispatch(name, params)
                executed.append({"tool": name, "result": result})
                log.info(f"Tier 3 (Groq) executed: {name}")
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result[:1500],
                })
            messages.extend(tool_results)

    # ── Warm-up ───────────────────────────────────────────────────────────────

    def warmup_tier1(self) -> None:
        """Fire a no-op to load qwen2.5:3b into Ollama memory on startup."""
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                timeout=15.0,
            )
            client.chat.completions.create(
                model=cfg.tier1_model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            log.info("Tier 1 warm-up complete")
        except Exception as e:
            log.warning(f"Tier 1 warm-up failed (Ollama may not be running): {e}")
