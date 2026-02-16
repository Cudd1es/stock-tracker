import yaml
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import schedule
import argparse

from parser import parse_user_requirement
from tools.data_tools import get_intraday_price_at, get_previous_close
from tools.storage import init_db, save_price
from tools.notifier import notify
from tools.reporter import fetch_news_headlines, generate_brief

def run_once(cfg_rules: dict, cfg_global: dict) -> None:
    """
    One scheduled run at target time.
    """
    # define default parameters
    default_tz = cfg_global.get("timezone", "America/Toronto")
    default_model = cfg_global.get("openai_model", "gpt-4o")
    default_language = "zh"

    tz = ZoneInfo(default_tz)
    model = default_model
    threshold = float(cfg_rules["alert_threshold"])
    language = cfg_rules.get("report_language", default_language)

    snapshot = []
    news_map = {}
    now_iso = datetime.now(tz).isoformat(timespec="seconds")

    for t in cfg_rules["tickers"]:
        time.sleep(0.3)
        # observe
        price_now = get_intraday_price_at(t, cfg_rules["schedule_time"], default_tz)
        prev_close = get_previous_close(t)
        if price_now is None or prev_close is None:
            print(f"Warning: Could not get data for ticker {t}. Skipping.")
            continue
        change_pct = ((price_now - prev_close) / prev_close * 100.0) if prev_close != 0 else 0.0
        snapshot.append({
            "ticker": t,
            "price_now": price_now,
            "prev_close": prev_close,
            "change_pct": change_pct,
        })


        # act
        # persist
        try:
            save_price(t, now_iso, price_now, "yfinance")
        except Exception as e:
            print(f"Error saving price for {t}: {e}")

        # news
        if cfg_rules.get("news_enabled", True):
            news_map[t] = fetch_news_headlines(t, topk=3)


    # alerts
    alert_lines = []
    for row in snapshot:
        if row["change_pct"] is not None and abs(row["change_pct"]) >= threshold:
            alert_lines.append(f"{row['ticker']} moved {row['change_pct']:.2f}% (now {row['price_now']:.2f})")

    # brief
    brief = generate_brief(model, snapshot, news_map, threshold, language)

    # notify
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    mention_id = os.getenv("DISCORD_MENTION_ID")
    method = cfg_rules.get("notify_method", "console")

    if alert_lines:
        notify(method, "[ALERT]\n" + "\n".join(alert_lines), discord_webhook=webhook, mention_id=mention_id)
    notify(method, "[DAILY BRIEF]\n" + brief, discord_webhook=webhook, mention_id=mention_id)

def run_scheduler(cfg_rules: dict, cfg_global: dict) -> None:
    """
    scheduled jobs according to schedule_time or interval
    """

    # define default parameters
    default_tz = cfg_global.get("timezone", "America/Toronto")
    default_language = "zh" 
    default_mode = "daily"
    default_interval = 10
    default_at_time = "9:45"

    mode = cfg_rules.get("schedule_mode", default_mode)
    tz = default_tz


    if mode == "interval":
        interval = int(cfg_rules.get("interval_minutes", default_interval))
        print(f"[SCHEDULE] {interval} minutes interval")
        schedule.every(interval).minutes.do(run_once, cfg_rules=cfg_rules, cfg_global=cfg_global)
    else:
        at_time = cfg_rules.get("schedule_time", default_at_time)
        print(f"[SCHEDULE] daily at {at_time} ({tz})")
        schedule.every().day.at(at_time).do(run_once, cfg_rules=cfg_rules, cfg_global=cfg_global)

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

    model = base_cfg.get("openai_model", "gpt-4o")
    # get user requirements
    print("please enter the prompt:")
    user_text = input().strip()

    rules = parse_user_requirement(user_text, model=model)
    print(rules)

    init_db()

    if args.single: # run for 1 round
        run_once(rules, base_cfg)
    else: # run in schedule
        run_once(rules, base_cfg)
        run_scheduler(rules, base_cfg)
