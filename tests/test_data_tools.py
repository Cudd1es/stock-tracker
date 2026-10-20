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
    monkeypatch.setattr(data_tools.yf, "download", lambda **kw: df)
    assert data_tools.get_intraday_price_at("AAPL", "10:05", "America/Toronto") == 151.0
