import tools.reporter as reporter


def capture_prompt(monkeypatch):
    prompts = []
    monkeypatch.setattr(reporter, "ask_llm", lambda prompt, model: prompts.append(prompt) or "brief")
    return prompts


def row(lookback):
    return {"ticker": "TSLA", "price_now": 110.0, "prev_close": 100.0, "change_pct": 10.0,
            "lookback_change_pct": lookback}


def test_summary_style_prompt(monkeypatch):
    prompts = capture_prompt(monkeypatch)
    reporter.generate_brief("m", [row(1.0)], {}, 5.0, "en", style="summary")
    assert "max 6 bullet points" in prompts[0]


def test_detailed_style_prompt(monkeypatch):
    prompts = capture_prompt(monkeypatch)
    reporter.generate_brief("m", [row(1.0)], {}, 5.0, "en", style="detailed")
    assert "one short paragraph per ticker" in prompts[0]
    assert "max 6 bullet points" not in prompts[0]


def test_lookback_in_context(monkeypatch):
    prompts = capture_prompt(monkeypatch)
    reporter.generate_brief("m", [row(3.21)], {}, 5.0, "en", lookback_days=5)
    assert "5d_change=3.21%" in prompts[0]
    reporter.generate_brief("m", [row(None)], {}, 5.0, "en", lookback_days=5)
    assert "5d_change=n/a" in prompts[1]
