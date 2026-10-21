import pandas as pd
import pytest

import tools.data_tools as data_tools


def fake_ticker(closes):
    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kw):
            return pd.DataFrame({"Close": closes})

    return FakeTicker


def test_lookback_change_pct(monkeypatch):
    monkeypatch.setattr(data_tools.yf, "Ticker", fake_ticker([100, 101, 102, 103, 104, 110]))
    assert data_tools.get_lookback_change_pct("TSLA", 5) == pytest.approx(10.0)


def test_lookback_insufficient_data(monkeypatch):
    monkeypatch.setattr(data_tools.yf, "Ticker", fake_ticker([100, 101, 102]))
    assert data_tools.get_lookback_change_pct("TSLA", 5) is None


def test_intraday_price_handles_multiindex_columns(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Toronto")
    today = datetime.now(tz).replace(hour=10, minute=0, second=0, microsecond=0)
    idx = pd.DatetimeIndex([today, today.replace(minute=1)])
    cols = pd.MultiIndex.from_tuples([("Close", "AAPL"), ("Open", "AAPL")], names=["Price", "Ticker"])
    df = pd.DataFrame([[150.0, 149.0], [151.0, 150.0]], index=idx, columns=cols)

    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kw):
            return df

    monkeypatch.setattr(data_tools.yf, "Ticker", FakeTicker)
    assert data_tools.get_intraday_price_at("AAPL", "10:05", "America/Toronto") == 151.0


def flaky_ticker(errors, closes):
    """fake Ticker whose history() raises each error in turn, then returns closes"""
    calls = []

    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kw):
            calls.append(kw)
            if len(calls) <= len(errors):
                raise errors[len(calls) - 1]
            return pd.DataFrame({"Close": closes})

    return FakeTicker, calls


def test_history_retries_transient_errors(monkeypatch):
    fake, calls = flaky_ticker([RuntimeError("timeout"), RuntimeError("timeout")], [100.0, 101.0])
    monkeypatch.setattr(data_tools.yf, "Ticker", fake)
    monkeypatch.setattr(data_tools, "_sleep", lambda s: None)
    assert data_tools.get_previous_close("TSLA") == 100.0
    assert len(calls) == 3


def test_history_missing_prices_not_retried(monkeypatch):
    from yfinance.exceptions import YFPricesMissingError

    fake, calls = flaky_ticker([YFPricesMissingError("TSLA", "")], [100.0])
    monkeypatch.setattr(data_tools.yf, "Ticker", fake)
    monkeypatch.setattr(data_tools, "_sleep", lambda s: None)
    assert data_tools.get_previous_close("TSLA") is None
    assert len(calls) == 1


def test_lookback_requests_enough_calendar_days(monkeypatch):
    from datetime import date

    fake, calls = flaky_ticker([], [100.0] * 61)
    monkeypatch.setattr(data_tools.yf, "Ticker", fake)
    data_tools.get_lookback_change_pct("TSLA", 60)
    start = calls[0]["start"]
    # 60 trading days span ~84 calendar days; leave room for holidays
    assert (date.today() - start).days >= 60 * 7 // 5 + 5
