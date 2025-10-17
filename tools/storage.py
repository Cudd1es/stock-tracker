import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path('stock_agent.db')

DDL = """
CREATE TABLE IF NOT EXISTS prices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker TEXT NOT NULL,
  ts TEXT NOT NULL,            -- ISO8601 string in local tz
  price REAL NOT NULL,
  source TEXT DEFAULT 'yfinance'
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_ts TEXT NOT NULL,
  status TEXT NOT NULL,
  note TEXT
);
"""

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db() -> None:
    conn = get_conn()
    with conn:
        for stmt in DDL.strip().split(";\n\n"):
            if stmt.strip():
                conn.execute(stmt)
    conn.close()

def save_price(ticker: str, ts_iso: str, price: float, source: str = "yfinance") -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO prices (ticker, ts, price, source) VALUES (?, ?, ?, ?)",
            (ticker, ts_iso, price, source)
        )
    conn.close()