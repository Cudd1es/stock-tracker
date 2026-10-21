import pytest

from parser import _validate_and_fix


def test_tickers_normalized():
    cfg = _validate_and_fix({"tickers": [" tsla", "AAPL", "aapl", "brk.b"]})
    assert cfg["tickers"] == ["TSLA", "AAPL", "BRK.B"]


def test_no_tickers_raises():
    with pytest.raises(ValueError):
        _validate_and_fix({"tickers": []})


def test_threshold_percent_string():
    assert _validate_and_fix({"tickers": ["A"], "alert_threshold": "4%"})["alert_threshold"] == 4.0
    assert _validate_and_fix({"tickers": ["A"], "alert_threshold": 0})["alert_threshold"] == 5.0
    assert _validate_and_fix({"tickers": ["A"], "alert_threshold": 80})["alert_threshold"] == 5.0


def test_invalid_enums_fall_back():
    cfg = _validate_and_fix({
        "tickers": ["A"],
        "notify_method": "email",
        "report_style": "x",
        "report_language": "jp",
    })
    assert cfg["notify_method"] == "console"
    assert cfg["report_style"] == "summary"
    assert cfg["report_language"] == "zh"


def test_bad_time_falls_back():
    assert _validate_and_fix({"tickers": ["A"], "schedule_time": "9:45"})["schedule_time"] == "16:10"


def test_interval_mode():
    cfg = _validate_and_fix({"tickers": ["A"], "schedule_mode": "interval", "interval_minutes": 0})
    assert cfg["interval_minutes"] == 10
    cfg = _validate_and_fix({"tickers": ["A"], "schedule_mode": "daily", "interval_minutes": 30})
    assert cfg["interval_minutes"] == 0


def test_language_none_does_not_crash():
    assert _validate_and_fix({"tickers": ["A"], "report_language": None})["report_language"] == "zh"
