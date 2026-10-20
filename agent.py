import yaml
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import schedule
import argparse
from typing import List, Optional
import logging

from parser import parse_user_requirement
from tools.data_tools import get_intraday_price_at, get_previous_close, get_lookback_change_pct
from tools.storage import init_db, save_price, record_run
from tools.notifier import notify
from tools.reporter import fetch_news_headlines, generate_brief

logger = logging.getLogger(__name__)

def setup_logging(level: str = "INFO") -> None:
    """
    configure root logging once, at program entry
    """
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

def target_time_for(cfg_rules: dict, tz: ZoneInfo) -> str:
    """
    HH:MM to price at: now for interval mode, schedule_time for daily mode.
    """
    if cfg_rules.get("schedule_mode") == "interval":
        return datetime.now(tz).strftime("%H:%M")
    return cfg_rules["schedule_time"]

def run_once(cfg_rules: dict, cfg_global: dict) -> None:
    """
    One scheduled run at target time; records the outcome in the runs table.
    """
    tz = ZoneInfo(cfg_global.get("timezone", "America/Toronto"))
    now_iso = datetime.now(tz).isoformat(timespec="seconds")
    try:
        skipped = _execute_run(cfg_rules, cfg_global, now_iso)
    except Exception as e:
        _safe_record_run(now_iso, "error", repr(e)[:500])
        raise

    if len(skipped) == len(cfg_rules["tickers"]):
        _safe_record_run(now_iso, "no_data")
    elif skipped:
        _safe_record_run(now_iso, "partial", ",".join(skipped))
    else:
        _safe_record_run(now_iso, "ok")

def _safe_record_run(run_ts: str, status: str, note: Optional[str] = None) -> None:
    try:
        record_run(run_ts, status, note)
    except Exception:
        logger.exception("failed to record run status %s", status)

def _execute_run(cfg_rules: dict, cfg_global: dict, now_iso: str) -> List[str]:
    """
    observe, persist, report and notify; returns the tickers that were skipped.
    """
    # define default parameters
    default_tz = cfg_global.get("timezone", "America/Toronto")
    default_model = cfg_global.get("openai_model", "gpt-4o")
    default_language = "zh"

    tz = ZoneInfo(default_tz)
    model = default_model
    threshold = float(cfg_rules["alert_threshold"])
    language = cfg_rules.get("report_language", default_language)
    style = cfg_rules.get("report_style", "summary")
    lookback_days = int(cfg_rules.get("lookback_days", 5))

    snapshot = []
    skipped = []
    news_map = {}
    target_hhmm = target_time_for(cfg_rules, tz)

    for t in cfg_rules["tickers"]:
        time.sleep(0.3)
        # observe
        price_now = get_intraday_price_at(t, target_hhmm, default_tz)
        prev_close = get_previous_close(t)
        if price_now is None or prev_close is None:
            logger.warning("could not get data for ticker %s, skipping", t)
            skipped.append(t)
            continue
        change_pct = ((price_now - prev_close) / prev_close * 100.0) if prev_close != 0 else 0.0
        snapshot.append({
            "ticker": t,
            "price_now": price_now,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "lookback_change_pct": get_lookback_change_pct(t, lookback_days),
        })


        # act
        # persist
        try:
            save_price(t, now_iso, price_now, "yfinance")
        except Exception:
            logger.exception("error saving price for %s", t)

        # news
        if cfg_rules.get("news_enabled", True):
            news_map[t] = fetch_news_headlines(t, topk=3)


    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    mention_id = os.getenv("DISCORD_MENTION_ID")
    method = cfg_rules.get("notify_method", "console")

    if not snapshot:
        notify(method, "[DAILY BRIEF]\nNo market data available.", discord_webhook=webhook, mention_id=mention_id)
        return skipped

    # alerts
    alert_lines = []
    for row in snapshot:
        if row["change_pct"] is not None and abs(row["change_pct"]) >= threshold:
            alert_lines.append(f"{row['ticker']} moved {row['change_pct']:.2f}% (now {row['price_now']:.2f})")

    # brief
    brief = generate_brief(model, snapshot, news_map, threshold, language, style, lookback_days)

    # notify
    if alert_lines:
        notify(method, "[ALERT]\n" + "\n".join(alert_lines), discord_webhook=webhook, mention_id=mention_id)
    notify(method, "[DAILY BRIEF]\n" + brief, discord_webhook=webhook, mention_id=mention_id)
    return skipped

def run_scheduler(cfg_rules: dict, cfg_global: dict) -> None:
    """
    scheduled jobs according to schedule_time or interval
    """

    # define default parameters
    default_tz = cfg_global.get("timezone", "America/Toronto")
    default_mode = "daily"
    default_interval = 10
    default_at_time = "09:45"

    mode = cfg_rules.get("schedule_mode", default_mode)
    tz = default_tz


    if mode == "interval":
        interval = int(cfg_rules.get("interval_minutes", default_interval))
        print(f"[SCHEDULE] {interval} minutes interval")
        schedule.every(interval).minutes.do(run_once, cfg_rules=cfg_rules, cfg_global=cfg_global)
    else:
        at_time = cfg_rules.get("schedule_time", default_at_time)
        print(f"[SCHEDULE] daily at {at_time} ({tz})")
        schedule.every().day.at(at_time, tz).do(run_once, cfg_rules=cfg_rules, cfg_global=cfg_global)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("[SCHED] stopped by user")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic AI Stock Tracker")
    parser.add_argument("-s", "--single", action="store_true",
                        help="Run once and exit (skip continuous schedule)")
    args = parser.parse_args()

    with open("config.yaml", "r") as f:
        base_cfg = yaml.safe_load(f)

    setup_logging(base_cfg.get("log_level", "INFO"))

    model = base_cfg.get("openai_model", "gpt-4o")
    # get user requirements
    print("please enter the prompt:")
    user_text = input().strip()

    rules = parse_user_requirement(user_text, model=model)
    logger.info("parsed rules: %s", rules)

    init_db()

    if args.single: # run for 1 round
        run_once(rules, base_cfg)
    else: # run in schedule
        run_once(rules, base_cfg)
        run_scheduler(rules, base_cfg)
