import pytest

import tools.storage as storage


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """point the sqlite db at a temp file so tests never touch stock_agent.db"""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    return tmp_path / "test.db"
