#  Agentic AI Stock Tracker

A minimal **Agentic AI system** that monitors selected U.S. stocks, gathers price data and news, generates daily summaries via LLM, and optionally sends alerts to Discord.

This project demonstrates how a small-scale **Agentic AI** can orchestrate data gathering, reasoning, and action — integrating LLMs, APIs, and notifications.

---

##  Features

- **Natural language configuration**  
  Describe what you want to track, e.g.  
  > “Help me check TSLA and AAPL stock prices every day at 3 PM. Notify me if there’s a price change of more than 10%, and include a news summary in English.”
- **Automated stock monitoring**  
  - Fetch real-time and historical prices via `yfinance`  
  - Compare intraday vs. previous close  
  - Store data in SQLite for persistence

- **News integration**  
  - Pulls latest headlines via Yahoo Finance  
  - Summarized by LLM into human-readable briefs

- **Alerting system**  
  - Threshold-based alerts (e.g., ±5%)  
  - Console or Discord notifications  
  - Simple to extend to email, Slack, etc.

- **LLM-powered reporting**  
  - Uses OpenAI API to generate concise, neutral summaries  
  - Multilingual (English/Chinese mixed input supported)

---

##  Project Structure

```
stock-tracker/
├── agent.py                # Main orchestration (parse -> run -> notify)
├── llm_agent.py            # Wrapper around OpenAI ChatCompletion API
├── parser.py               # LLM-powered requirement-to-config parser
├── config_example.yaml     # Example global configuration
└── tools/
    ├── data_tools.py       # Stock data fetch & change computation
    ├── reporter.py         # News fetching & LLM-based summary generation
    ├── notifier.py         # Console & Discord notifications
    └── storage.py          # SQLite database and schema management
```

---

## Installation

```bash
git clone https://github.com/Cudd1es/stock-tracker.git
cd stock-tracker
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```


---

## Configuration

### 1. Secrets (`.env`)
Create a `.env` file in the project root with all sensitive credentials:
```
OPENAI_API_KEY=sk-your-key-here
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxx/xxxx
DISCORD_MENTION_ID=your-discord-user-id
```

> **Note:** `.env` is git-ignored and will not be committed.

### 2. Global Config (`config.yaml`)
Non-sensitive settings only. See `config_example.yaml`:

```yaml
openai_model: gpt-4o
timezone: America/Toronto
defaults:
  alert_threshold: 5.0
  schedule_time: "16:30"
  notify_method: "console"
```


---

##  Usage

### Run once manually
```bash
python agent.py -s
```
or
```bash
python agent.py --single
```

Then input your natural-language requirement:
```
please enter the prompt:
latest news about AAPL and NVDA
```

Output example:
```
[DAILY BRIEF]
- AAPL 收跌0.77%，受贸易战新闻影响关注度提升。
- NVDA 收涨1.10%，银行板块下跌中表现抗跌。
摘要：两只标的均无显著波动，市场聚焦宏观消息面。
```



### Continuous scheduling (Agentic mode)

```bash
python agent.py
```

Then input your natural-language requirement:
```
please enter the prompt:
Check TSLA and AAPL every 10 minutes.
```

Output example:
```
[DAILY BRIEF]
- TSLA +2.3% …
- AAPL -1.1% …
Summary: both moved within ±10%, steady intraday.
[SCHEDULE] 10 minutes interval

...

[DAILY BRIEF]
- TSLA +2.3% …
- AAPL -1.1% …
Summary: both moved within ±10%, steady intraday.
[SCHEDULE] 10 minutes interval

```

---

## Database

SQLite file: `stock_agent.db`

Tables:
- **prices** — stores ticker, timestamp, price, and source  
- **runs** — optional logging of run status or errors

Initialize manually if needed:
```bash
python -m tools.storage
```

---

## Agentic Workflow

| Phase | Description | Implemented by                                           |
|-------|--------------|----------------------------------------------------------|
| **Observe** | Fetch prices and news | `data_tools.py`, `reporter.py`                           |
| **Plan** | Determine what to alert/report | `agent.py`                                               |
| **Act** | Save, notify, and summarize | `storage.py`, `notifier.py`, `llm_agent.py` |
| **Reflect** | LLM summarizes insights | `generate_brief()`                                       |

---

## Example: Discord Notification

When `notify_method` = `discord`, alerts are sent like:
```
<@USER_ID> [ALERT]
TSLA moved +12.5% (now 243.7)
```

---
