# agent.py
# Main orchestration: parse requirement -> schedule -> run daily

import yaml
from datetime import datetime
from zoneinfo import ZoneInfo

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

    snapshot = []
    news_map = {}
    now_iso = datetime.now(tz).isoformat(timespec="seconds")

    for t in cfg_rules["tickers"]:
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
        # persist
        save_price(t, now_iso, price_now, "yfinance")

        # news
        if cfg_rules.get("news_enabled", True):
            news_map[t] = fetch_news_headlines(t, topk=3)
            for i in news_map[t]:
                print(i["title"], i["link"])

    # alerts
    alert_lines = []
    for row in snapshot:
        if row["change_pct"] is not None and abs(row["change_pct"]) >= threshold:
            alert_lines.append(f"{row['ticker']} moved {row['change_pct']:.2f}% (now {row['price_now']:.2f})")

    # brief
    brief = generate_brief(model, snapshot, news_map, threshold)

    # notify
    with open("config.yaml", "r") as f:
        base_cfg = yaml.safe_load(f)
    webhook = (base_cfg.get("discord") or {}).get("webhook_url")
    mention_id = (base_cfg.get("discord") or {}).get("mention_id")
    method = cfg_rules.get("notify_method", "console")

    if alert_lines:
        notify(method, "[ALERT]\n" + "\n".join(alert_lines), discord_webhook=webhook, mention_id=mention_id)
    notify(method, "[DAILY BRIEF]\n" + brief, discord_webhook=webhook, mention_id=mention_id)

if __name__ == "__main__":
    with open("config.yaml", "r") as f:
        base_cfg = yaml.safe_load(f)

    # get user requirements
    print("please enter the prompt:")
    user_text = input().strip()

    rules = parse_user_requirement(user_text, model=base_cfg.get("openai_model", "gpt-4o"))
    print(rules)

    init_db()

    run_once(rules, base_cfg)