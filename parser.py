import json
import re
from typing import Any, Dict, List

from llm_agent import ask_llm

DEFAULTS = {
    "alert_threshold": 5.0,
    "notify_method": "console",
    "schedule_time": "16:10",  # HH:MM 24h
    "report_style": "summary",  # "summary" or "detailed"
    "news_enabled": True,
    "lookback_days": 5,
    "report_language": "zh"
}

ALLOWED_NOTIFY_METHODS = [
    "console",
    "discord"
]
ALLOWED_REPORT_STYLES = [
    "summary",
    "detailed"
]

ALLOWED_LANGUAGES = [
    "en",
    "zh",
    "jp"
]

PARSER_PROMPT = """You are a strict configuration extractor for a stock-tracking agent.
User will describe monitoring requirements in natural language (possibly Chinese/English mixed).
You MUST return ONLY a valid JSON object (no extra text, no code fences) matching this schema:

{{
  "tickers": "string[]",                 // REQUIRED, 1..50 uppercase tickers, e.g., ["TSLA","AAPL"]
  "alert_threshold": "number",           // OPTIONAL, percent like 4.0 means ±4%
  "notify_method": "discord|console",      // OPTIONAL
  "schedule_time": "HH:MM",              // OPTIONAL, 24h format, e.g., "16:30"
  "report_style": "summary|detailed",    // OPTIONAL
  "news_enabled": "boolean",             // OPTIONAL
  "lookback_days": "integer"             // OPTIONAL, days to look back for trends (1..60)
  "report_language": "zh|en|jp"            // OPTIONAL, language in the report
}}

Rules:
- Normalize tickers to UPPERCASE, strip spaces, deduplicate.
- If user mentions threshold in %, convert to number (e.g., "4%" -> 4.0).
- If notify method is unclear, choose "console".
- If schedule is like "after market close", use "16:30".
- If user mentions daily, assume one run per day at "16:30".
- If missing values, omit them so the system can apply defaults.
- Return ONLY the JSON object, nothing else.

User requirement:
<<<
{requirement}
>>>"""

def _normalize_tickers(raw_tickers: List[str]) -> List[str]:
    """Uppercase, strip, deduplicate, and keep only simple alphanumerics/dots (e.g., BRK.B)."""
    seen = set()
    cleaned: List[str] = []
    for t in raw_tickers:
        if not t:
            continue
        t_up = t.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+(\.[A-Z])?", t_up):
            t_up = re.sub(r"[^A-Z0-9\.]", "", t_up)
        if t_up and t_up not in seen:
            seen.add(t_up)
            cleaned.append(t_up)
    return cleaned[:50]

def _is_valid_time(hhmm: str) -> bool:
    """Check if time is in HHMM format."""
    return bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", hhmm))

def _coerce_float(x: Any, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _coerce_int(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _apply_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """if there are values in DEFAULTS not specified, apply the default values."""
    out = dict(cfg)
    for k, v in DEFAULTS.items():
        if k not in out or out[k] in (None, "", [], {}):
            out[k] = v
    return out

def _validate_and_fix(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # tickers
    tickers = cfg.get("tickers", [])
    if not isinstance(tickers, list):
        tickers = []
    tickers = _normalize_tickers([str(t) for t in tickers])
    if not tickers:
        raise ValueError("No valid tickers parsed. Please specify at least one ticker symbol.")

    # alert_threshold
    alert = cfg.get("alert_threshold", None)
    if isinstance(alert, str) and alert.strip().endswith("%"):
        try:
            alert = float(alert.strip().rstrip("%"))
        except Exception:
            alert = None
    alert = _coerce_float(alert, DEFAULTS["alert_threshold"])
    if alert <= 0 or alert > 50:
        # keep a sane range
        alert = DEFAULTS["alert_threshold"]

    # notify_method
    notify = cfg.get("notify_method", DEFAULTS["notify_method"])
    if isinstance(notify, str):
        notify = notify.lower().strip()
    if notify not in ALLOWED_NOTIFY_METHODS:
        notify = DEFAULTS["notify_method"]

    # schedule_time
    sched = cfg.get("schedule_time", DEFAULTS["schedule_time"])
    if not isinstance(sched, str) or not _is_valid_time(sched.strip()):
        sched = DEFAULTS["schedule_time"]

    # report_style
    style = cfg.get("report_style", DEFAULTS["report_style"])
    if isinstance(style, str):
        style = style.lower().strip()
    if style not in ALLOWED_REPORT_STYLES:
        style = DEFAULTS["report_style"]

    # news_enabled
    news_enabled = cfg.get("news_enabled", DEFAULTS["news_enabled"])
    news_enabled = bool(news_enabled)

    # lookback_days
    lookback = _coerce_int(cfg.get("lookback_days", DEFAULTS["lookback_days"]), DEFAULTS["lookback_days"])
    if lookback < 1 or lookback > 60:
        lookback = DEFAULTS["lookback_days"]

    # report_language
    lang = (cfg.get("report_language", DEFAULTS["report_language"])).lower().strip()
    if lang not in ALLOWED_LANGUAGES:
        lang = DEFAULTS["report_language"]

    return {
        "tickers": tickers,
        "alert_threshold": float(alert),
        "notify_method": notify,
        "schedule_time": sched,
        "report_style": style,
        "news_enabled": news_enabled,
        "lookback_days": int(lookback),
        "report_language": lang,
    }

def parse_user_requirement(requirement_text: str, model: str = "gpt-4o") -> Dict[str, Any]:
    """
    Use LLM to parse a natural-language requirement into a structured config dict.
    """
    prompt = PARSER_PROMPT.format(requirement=requirement_text)
    raw = ask_llm(prompt, model=model).strip()

    if not raw.startswith("{"):
        match = re.search(r"\{.*\}\s*$", raw, flags=re.DOTALL)
        if match:
            raw = match.group(0)

    try:
        cfg_llm = json.loads(raw)
        if not isinstance(cfg_llm, dict):
            raise ValueError("LLM output is not a JSON object.")
    except Exception as e:
        raise ValueError(f"Failed to parse LLM JSON: {e}\nLLM raw output: {raw[:300]}")

    final_cfg = _validate_and_fix(cfg_llm)
    return final_cfg

if __name__ == "__main__":
    test_prompt = input("please enter the prompt:\n")
    cfg = parse_user_requirement(test_prompt)
    print(cfg)