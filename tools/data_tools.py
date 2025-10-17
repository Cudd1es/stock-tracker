from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import yfinance as yf
from typing import Optional, Tuple

def get_previous_close(ticker: str) -> Optional[float]:
    """
       Return previous close for ticker; None if unavailable.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.history(period="2d", interval="1d")
        if info is None or info.empty:
            return None
        if len(info) >= 2:
            return float(info["Close"].iloc[-2])
        else:
            return float(info["Close"].iloc[-1])
    except Exception:
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
        df = yf.download(tickers=ticker, period="1d", interval="1m", auto_adjust=False, progress=False)
        if df is None or df.empty:
            # retry with 5m bars
            df = yf.download(tickers=ticker, period="5d", interval="5m", auto_adjust=False, progress=False)
            if df is None or df.empty:
                return None

        df_local = df.tz_convert(tz) if df.index.tz is not None else df.tz_localize(tz)
        df_today = df_local[df_local.index.date == target_dt.date()]
        if df_today.empty:
            return None
        df_until = df_today[df_today.index <= target_dt]
        if df_until.empty:
            return None

        ret = float(df_until["Close"].iloc[-1])
        return ret
    except Exception:
        return None

def get_change_pct_vs_prev_close(ticker: str, price_now: float) -> Optional[float]:
    """
    Compute percentage change versus previous close.
    """
    prev_close = get_previous_close(ticker)
    if prev_close is None or prev_close == 0:
        return None
    return (price_now - prev_close) / prev_close * 100.0
