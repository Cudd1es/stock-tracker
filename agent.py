import yaml
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import schedule
import argparse

from parser import parse_user_requirement
from tools.data_tools import get_intraday_price_at, get_previous_close, get_change_pct_vs_prev_close
from tools.storage import init_db, save_price
from tools.notifier import notify
from tools.reporter import fetch_news_headlines, generate_brief

def run_once(cfg_rules: dict, cfg_global: dict) -> None:
    """
    One scheduled run at target time.
    """
    tz = ZoneInfo(cfg_global.get("timezone", "America/Toronto"))
    model = cfg_global.get("openai_model", "gpt-4o")
    threshold = float(cfg_rules["alert_threshold"])
    language = cfg_rules.get("report_language", "zh")

    snapshot = []
    news_map = {}
    now_iso = datetime.now(tz).isoformat(timespec="seconds")

    for t in cfg_rules["tickers"]:
        time.sleep(0.3)
        # observe
        price_now = get_intraday_price_at(t, cfg_rules["schedule_time"], cfg_global.get("timezone", "America/Toronto"))
        prev_close = get_previous_close(t)
        if price_now is None or prev_close is None:
            continue
        change_pct = get_change_pct_vs_prev_close(t, price_now)
        snapshot.append({
            "ticker": t,
            "price_now": price_now,
            "prev_close": prev_close,
            "change_pct": change_pct if change_pct is not None else 0.0
        })


        # act
        # persist
        save_price(t, now_iso, price_now, "yfinance")

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
    with open("config.yaml", "r") as f:
        base_cfg = yaml.safe_load(f)
    webhook = (base_cfg.get("discord") or {}).get("webhook_url")
    mention_id = (base_cfg.get("discord") or {}).get("mention_id")
    method = cfg_rules.get("notify_method", "console")

    if alert_lines:
        notify(method, "[ALERT]\n" + "\n".join(alert_lines), discord_webhook=webhook, mention_id=mention_id)
    notify(method, "[DAILY BRIEF]\n" + brief, discord_webhook=webhook, mention_id=mention_id)

def run_scheduler(cfg_rules: dict, cfg_global: dict) -> None:
    """
    scheduled jobs according to schedule_time or interval
    """
    mode = cfg_rules.get("schedule_mode", "daily")
    tz_name = cfg_global.get("timezone", "America/Toronto")


    if mode == "interval":
        interval = int(cfg_rules.get("interval_minutes", 10))
        print(f"[SCHEDULE] {interval} minutes interval")
        schedule.every(interval).minutes.do(run_once, cfg_rules=cfg_rules, cfg_global=cfg_global)
    else:
        at_time = cfg_rules.get("schedule_time", "9:45")
        print(f"[SCHEDULE] daily at {at_time} ({tz_name})")
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

    # get user requirements
    print("please enter the prompt:")
    user_text = input().strip()

    rules = parse_user_requirement(user_text, model=base_cfg.get("openai_model", "gpt-4o"))
    print(rules)

    init_db()

    if args.single: # run for 1 round
        run_once(rules, base_cfg)
    else: # run in schedule
        run_once(rules, base_cfg)
        run_scheduler(rules, base_cfg)
