import logging
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFTickerMissingError
from typing import Optional

from tools.retry import with_retry

logger = logging.getLogger(__name__)

_sleep = time.sleep

def _history(ticker: str, **kwargs) -> pd.DataFrame:
    """
    Ticker.history with retries on transient errors.
    yfinance hides exceptions by default (returning an empty frame), so they are
    switched on here; a missing-prices error is a real "no data" answer and is not retried.
    """
    hide = yf.config.debug.hide_exceptions
    yf.config.debug.hide_exceptions = False
    try:
        t = yf.Ticker(ticker)
        return with_retry(lambda: t.history(**kwargs), sleep=_sleep, give_up_on=(YFTickerMissingError,))
    except YFTickerMissingError:
        return pd.DataFrame()
    finally:
        yf.config.debug.hide_exceptions = hide

def get_previous_close(ticker: str) -> Optional[float]:
    """
       Return previous close for ticker; None if unavailable.
    """
    try:
        info = _history(ticker, period="2d", interval="1d")
        if info is None or info.empty:
            return None
        if len(info) >= 2:
            return float(info["Close"].iloc[-2])
        else:
            return float(info["Close"].iloc[-1])
    except Exception:
        logger.warning("failed to fetch previous close for %s", ticker, exc_info=True)
        return None


def get_intraday_price_at(ticker: str, target_hhmm: str, timezone_str: str = "America/Toronto") -> Optional[float]:
    """
    get today's intraday price close to target_hhmm from ticker.
    """
    try:
        tz = ZoneInfo(timezone_str)
        now_local = datetime.now(tz)
        target_h, target_m = map(int, target_hhmm.split(":"))
        target_dt = now_local.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        df = _history(ticker, period="1d", interval="1m", auto_adjust=False)
        if df is None or df.empty:
            # retry with 5m bars
            df = _history(ticker, period="5d", interval="5m", auto_adjust=False)
            if df is None or df.empty:
                return None

        df_local = df.tz_convert(tz) if df.index.tz is not None else df.tz_localize("UTC").tz_convert(tz)
        df_today = df_local[df_local.index.date == target_dt.date()]
        if df_today.empty:
            return None
        df_until = df_today[df_today.index <= target_dt]
        if df_until.empty:
            return None

        close = df_until["Close"]
        if close.ndim > 1:
            # guard against (Price, Ticker) MultiIndex columns as returned by yf.download
            close = close.iloc[:, 0]
        ret = float(close.iloc[-1])
        return ret
    except Exception:
        logger.warning("failed to fetch intraday price for %s", ticker, exc_info=True)
        return None

def get_lookback_change_pct(ticker: str, days: int) -> Optional[float]:
    """
    percent change of the latest daily close vs the close `days` trading days earlier; None if not enough data.
    """
    try:
        # `days` counts trading days; ask for enough calendar days to cover weekends and holidays
        start = date.today() - timedelta(days=int(days * 1.5) + 10)
        hist = _history(ticker, start=start, interval="1d")
        if hist is None or hist.empty or len(hist) < days + 1:
            return None
        closes = hist["Close"]
        base = float(closes.iloc[-(days + 1)])
        if base == 0:
            return None
        return (float(closes.iloc[-1]) - base) / base * 100.0
    except Exception:
        logger.warning("failed to fetch %d-day history for %s", days, ticker, exc_info=True)
        return None

def get_change_pct_vs_prev_close(ticker: str, price_now: float) -> Optional[float]:
    """
    Compute percentage change versus previous close.
    """
    prev_close = get_previous_close(ticker)
    if prev_close is None or prev_close == 0:
        return None
    return (price_now - prev_close) / prev_close * 100.0
