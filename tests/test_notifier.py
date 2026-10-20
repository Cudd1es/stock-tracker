import requests

import tools.notifier as notifier


class FakeResp:
    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def test_non_2xx_is_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: calls.append(k) or FakeResp(404))
    assert notifier.send_discord("u", "hello", sleep=lambda s: None) is False
    assert len(calls) == 3


def test_long_message_truncated(monkeypatch):
    sent = []
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: sent.append(k["json"]) or FakeResp(204))
    assert notifier.send_discord("u", "x" * 5000, mention_id="42", sleep=lambda s: None) is True
    content = sent[0]["content"]
    assert len(content) <= notifier.DISCORD_MAX_LEN
    assert content.startswith("<@42> ")
    assert content.endswith("…")


def test_fallback_prints_to_console(monkeypatch, capsys):
    monkeypatch.setattr(notifier, "send_discord", lambda *a, **k: False)
    notifier.notify("discord", "hello", discord_webhook="u")
    assert "hello" in capsys.readouterr().out


WEBHOOK = "https://discord.com/api/webhooks/1/SECRETTOKEN"


def test_http_error_does_not_log_webhook(monkeypatch, caplog):
    class LeakyResp(FakeResp):
        def raise_for_status(self):
            raise requests.HTTPError(f"404 Client Error: Not Found for url: {WEBHOOK}")

    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: LeakyResp(404))
    assert notifier.send_discord(WEBHOOK, "hi", sleep=lambda s: None) is False
    assert "SECRETTOKEN" not in caplog.text
    assert "404" in caplog.text


def test_connection_error_does_not_log_webhook(monkeypatch, caplog):
    def refuse(*a, **k):
        raise requests.ConnectionError(f"Max retries exceeded with url: {WEBHOOK}")

    monkeypatch.setattr(notifier.requests, "post", refuse)
    assert notifier.send_discord(WEBHOOK, "hi", sleep=lambda s: None) is False
    assert "SECRETTOKEN" not in caplog.text
