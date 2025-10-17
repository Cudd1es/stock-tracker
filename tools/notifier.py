import requests
from typing import Optional

def send_discord(webhook_url: str, content: str, mention_id: Optional[str] = None) -> bool:
    content = f"<@{mention_id}> " + content
    try:
        payload = {
            "content": content,
            "username": "stock agent bot"
        }
        requests.post(webhook_url, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Discord通知失败: {str(e)}")
        return False

def notify(method: str, message: str, discord_webhook: Optional[str], mention_id: Optional[str] = None) -> None:
    method = (method or "console").lower()
    if method == "discord" and discord_webhook:
        ok = send_discord(discord_webhook, message, mention_id)
        if not ok:
            print("[NOTIFY][discord][fail] Discord notify failed]", message)
    else:
        print("[NOTIFY][console]", message)