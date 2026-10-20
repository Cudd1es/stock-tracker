import importlib

import llm_agent


def test_import_without_api_key(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    importlib.reload(llm_agent)  # must not raise
    assert llm_agent._client is None


def test_ask_llm_returns_empty_on_error(monkeypatch):
    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    raise RuntimeError("x")

    monkeypatch.setattr(llm_agent, "_get_client", lambda: Boom)
    assert llm_agent.ask_llm("hi") == ""
