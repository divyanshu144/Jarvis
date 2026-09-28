"""Cost monitoring tests."""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from jarvis.core import costs


def _row(db_path, table="model_usage"):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row


def test_estimate_tokens_is_stable():
    assert costs.estimate_tokens("") == 0
    assert costs.estimate_tokens("abcd") == 1
    assert costs.estimate_tokens("x" * 400) == 100


def test_infer_provider_from_tier_and_model():
    assert costs.infer_provider(1, "qwen2.5:3b") == "ollama"
    assert costs.infer_provider(2, "meta-llama/llama-4-scout") == "groq"
    assert costs.infer_provider(3, "claude-sonnet-4-20250514") == "anthropic"


def test_extracts_anthropic_exact_usage():
    response = SimpleNamespace(usage=SimpleNamespace(input_tokens=123, output_tokens=45))

    usage = costs.extract_sdk_usage(response, provider="anthropic")

    assert usage is not None
    assert usage.input_tokens == 123
    assert usage.output_tokens == 45
    assert usage.total_tokens == 168
    assert usage.usage_source == "sdk_usage"


def test_extracts_openai_compatible_exact_usage():
    response = {"usage": {"prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27}}

    usage = costs.extract_sdk_usage(response, provider="groq")

    assert usage is not None
    assert usage.input_tokens == 20
    assert usage.output_tokens == 7
    assert usage.total_tokens == 27


def test_partial_or_malformed_usage_returns_none():
    assert costs.extract_sdk_usage({"usage": {"prompt_tokens": 20}}, provider="groq") is None
    assert costs.extract_sdk_usage({"usage": {"input_tokens": "bad", "output_tokens": 2}}, provider="anthropic") is None
    assert costs.extract_sdk_usage(SimpleNamespace(), provider="groq") is None


def test_estimate_cost_from_configurable_price_file(tmp_path):
    price_file = tmp_path / "prices.json"
    price_file.write_text(
        json.dumps(
            {
                "providers": {
                    "anthropic": {
                        "models": {
                            "claude-test": {
                                "input_per_million": 3.0,
                                "output_per_million": 15.0,
                            }
                        }
                    }
                }
            }
        )
    )

    cost, source = costs.estimate_cost_usd("anthropic", "claude-test", 1_000_000, 1_000_000, price_file)

    assert cost == 18.0
    assert source == "model_costs:anthropic:claude-test"


def test_local_model_costs_zero_without_price_file():
    cost, source = costs.estimate_cost_usd("ollama", "qwen2.5:3b", 1000, 1000, "/missing/prices.json")

    assert cost == 0.0
    assert source == "local_zero_cost"


def test_record_model_usage_redacts_and_persists(tmp_path):
    db = tmp_path / "costs.db"

    costs.record_model_usage(
        "req-cost",
        provider="anthropic",
        model="claude-token=secret",
        input_tokens=10,
        output_tokens=20,
        db_path=db,
    )

    row = _row(db)
    assert row["request_id"] == "req-cost"
    assert row["provider"] == "anthropic"
    assert row["model"] == "claude-token=[REDACTED]"
    assert row["input_tokens"] == 10
    assert row["output_tokens"] == 20
    assert row["total_tokens"] == 30
    assert row["pricing_source"] == "missing_price"
    assert row["usage_source"] == "estimated_chars"


def test_record_chat_usage_persists_estimated_usage(tmp_path):
    db = tmp_path / "costs.db"

    costs.record_chat_usage(
        "req-chat",
        tier=1,
        model="qwen2.5:3b",
        user_message="x" * 40,
        final_answer="y" * 80,
        db_path=db,
    )

    row = _row(db)
    assert row["request_id"] == "req-chat"
    assert row["provider"] == "ollama"
    assert row["input_tokens"] == 10
    assert row["output_tokens"] == 20
    assert row["estimated_cost_usd"] == 0.0
    assert row["usage_source"] == "estimated_chars"


def test_record_chat_usage_prefers_exact_sdk_usage(tmp_path):
    db = tmp_path / "costs.db"

    costs.record_chat_usage(
        "req-exact",
        tier=3,
        model="claude-test",
        user_message="x" * 400,
        final_answer="y" * 400,
        input_tokens=12,
        output_tokens=8,
        usage_source="sdk_usage",
        db_path=db,
    )

    row = _row(db)
    assert row["provider"] == "anthropic"
    assert row["input_tokens"] == 12
    assert row["output_tokens"] == 8
    assert row["total_tokens"] == 20
    assert row["usage_source"] == "sdk_usage"
    assert row["pricing_source"] == "missing_price"
    assert row["estimated_cost_usd"] == 0.0


def test_record_chat_usage_falls_back_when_usage_missing_or_partial(tmp_path):
    db = tmp_path / "costs.db"

    costs.record_chat_usage(
        "req-fallback",
        tier=2,
        model="meta-llama/llama-4-scout",
        user_message="x" * 40,
        final_answer="y" * 80,
        input_tokens=99,
        output_tokens=None,
        usage_source="sdk_usage",
        db_path=db,
    )

    row = _row(db)
    assert row["input_tokens"] == 10
    assert row["output_tokens"] == 20
    assert row["usage_source"] == "estimated_chars"


def test_existing_model_usage_table_gets_usage_source_migration(tmp_path):
    db = tmp_path / "old-costs.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        CREATE TABLE model_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            estimated_cost_usd REAL NOT NULL,
            pricing_source TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    costs.record_model_usage(
        "req-migrate",
        provider="ollama",
        model="qwen2.5:3b",
        input_tokens=1,
        output_tokens=1,
        usage_source="sdk_usage",
        db_path=db,
    )

    row = _row(db)
    assert row["usage_source"] == "sdk_usage"


def test_get_cost_summary_groups_recent_usage(tmp_path):
    db = tmp_path / "costs.db"
    costs.record_model_usage("a", provider="ollama", model="qwen2.5:3b", input_tokens=10, output_tokens=5, db_path=db)
    costs.record_model_usage("b", provider="ollama", model="qwen2.5:3b", input_tokens=20, output_tokens=5, db_path=db)

    summary = costs.get_cost_summary(days=7, db_path=db)

    assert summary["calls"] == 2
    assert summary["total_tokens"] == 40
    assert summary["by_model"][0]["provider"] == "ollama"
    assert summary["by_model"][0]["calls"] == 2


def test_cost_monitoring_failures_do_not_crash(monkeypatch):
    def fail_connect(*_, **__):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(costs, "_connect", fail_connect)

    costs.init_cost_monitoring()
    costs.record_model_usage("req", provider="ollama", model="qwen", input_tokens=1, output_tokens=1)
    costs.record_chat_usage("req", tier=1, model="qwen", user_message="hi", final_answer="ok")
    assert costs.get_cost_summary()["calls"] == 0
