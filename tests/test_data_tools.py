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
