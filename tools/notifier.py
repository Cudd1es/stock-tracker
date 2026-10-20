import logging
import time
import requests
from typing import Callable, Optional

from tools.retry import with_retry

logger = logging.getLogger(__name__)

DISCORD_MAX_LEN = 2000

def send_discord(webhook_url: str, content: str, mention_id: Optional[str] = None,
                 sleep: Callable[[float], None] = time.sleep) -> bool:
    if mention_id:
        content = f"<@{mention_id}> " + content
    if len(content) > DISCORD_MAX_LEN:
        content = content[:DISCORD_MAX_LEN - 1] + "…"
    payload = {
        "content": content,
        "username": "stock agent bot"
    }

    def post():
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()

    try:
        with_retry(post, sleep=sleep)
        return True
    except Exception as e:
        logger.error("discord notification failed: %s", e)
        return False

def notify(method: str, message: str, discord_webhook: Optional[str], mention_id: Optional[str] = None) -> None:
    method = (method or "console").lower()
    if method == "discord" and discord_webhook:
        ok = send_discord(discord_webhook, message, mention_id)
        if not ok:
            print("[NOTIFY][console]", message)
    else:
        print("[NOTIFY][console]", message)
