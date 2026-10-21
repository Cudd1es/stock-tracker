import logging

import agent
import tools.data_tools as data_tools


def test_missing_price_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(agent, "get_intraday_price_at", lambda *a, **k: None)
    monkeypatch.setattr(agent, "get_previous_close", lambda t: 100.0)
    monkeypatch.setattr(agent, "generate_brief", lambda *a, **k: "b")
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    rules = {"tickers": ["TSLA"], "alert_threshold": 5.0, "schedule_time": "16:10", "news_enabled": False}
    with caplog.at_level(logging.WARNING):
        agent.run_once(rules, {})
    assert any(r.levelname == "WARNING" and "TSLA" in r.getMessage() for r in caplog.records)


def test_data_tools_logs_exception(monkeypatch, caplog):
    def boom(ticker):
        raise RuntimeError("network down")

    monkeypatch.setattr(data_tools.yf, "Ticker", boom)
    with caplog.at_level(logging.WARNING):
        assert data_tools.get_previous_close("TSLA") is None
    assert any(r.levelname == "WARNING" and "TSLA" in r.getMessage() for r in caplog.records)
