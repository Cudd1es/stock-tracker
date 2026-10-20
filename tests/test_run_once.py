import sqlite3

import pytest

import agent
import tools.storage as storage

RULES = {"tickers": ["TSLA", "AAPL"], "alert_threshold": 5.0, "schedule_time": "16:10", "news_enabled": False}


@pytest.fixture
def env(monkeypatch):
    storage.init_db()
    calls = {"brief": 0, "notify": []}

    def brief(*a, **k):
        calls["brief"] += 1
        return "brief"

    monkeypatch.setattr(agent, "generate_brief", brief)
    monkeypatch.setattr(agent, "notify", lambda method, msg, **k: calls["notify"].append(msg))
    monkeypatch.setattr(agent, "get_previous_close", lambda t: 100.0)
    monkeypatch.setattr(agent, "get_lookback_change_pct", lambda t, d: None)
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    return calls


def last_run(db):
    return sqlite3.connect(db).execute("SELECT status, note FROM runs ORDER BY id DESC LIMIT 1").fetchone()


def test_partial_run_recorded(env, monkeypatch, isolated_db):
    monkeypatch.setattr(agent, "get_intraday_price_at", lambda t, *a: 101.0 if t == "TSLA" else None)
    agent.run_once(RULES, {})
    assert last_run(isolated_db) == ("partial", "AAPL")


def test_no_data_skips_llm(env, monkeypatch, isolated_db):
    monkeypatch.setattr(agent, "get_intraday_price_at", lambda *a: None)
    agent.run_once(RULES, {})
    assert env["brief"] == 0
    assert env["notify"] == ["[DAILY BRIEF]\nNo market data available."]
    assert last_run(isolated_db) == ("no_data", None)


def test_error_recorded_and_reraised(env, monkeypatch, isolated_db):
    def boom(t):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "get_intraday_price_at", lambda *a: 101.0)
    monkeypatch.setattr(agent, "get_previous_close", boom)
    with pytest.raises(RuntimeError):
        agent.run_once(RULES, {})
    status, note = last_run(isolated_db)
    assert status == "error"
    assert "boom" in note
