# Stock Tracker 加固与补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复项目现存问题（仓库卫生、无测试、print 日志、无重试、调度时区、未使用的配置项、`runs` 表未写入），让项目可测试、可观测、行为与配置一致。

**Architecture:** 保持现有模块划分（`agent.py` 编排，`tools/*` 各司其职），只新增 `tools/retry.py` 一个模块和 `tests/` 目录。所有外部依赖（OpenAI、yfinance、Discord、SQLite 路径）在测试中用 `monkeypatch` 替换，测试不触网。

**Tech Stack:** Python 3.13、pytest、yfinance/pandas、schedule、openai、requests、sqlite3

**Spec:** 本计划依据会话中对代码的通读结论，以及 [CODE_REVIEW.md](../../../CODE_REVIEW.md) 中尚未修复的条目（日志、重试、测试）。

## Global Constraints

- 工作分支：`dev`；每个 Task 一个 commit，提交信息用 conventional commits（`fix:` / `feat:` / `chore:` / `test:`）。
- 测试命令统一为 `python -m pytest -q`，在项目根目录运行；测试不得发起真实网络请求，不得读写项目根目录下的 `stock_agent.db`。
- 不引入新的运行时依赖，`pytest` 只放进新建的 `requirements-dev.txt`。`schedule` 下限提升为 `>=1.2.2`（`Job.at` 支持时区参数）。
- 终端通知（`notify(method="console")`）是产品输出，继续用 `print`；其他诊断信息改为 `logging`。
- 代码风格沿用现有：小写开头的简短 docstring、`Optional[...]` 类型标注、函数内 `try/except` 返回 `None` 的容错风格。

## Review Focus

1. **非交易日 / 盘前运行**：周末或开盘前所有 ticker 取不到价格，`snapshot` 为空。期望：不调用 LLM，发出一条 `[DAILY BRIEF]\nNo market data available.`，并记录 run 状态 `no_data`。（测试加在 Task 6）
2. **Discord 超长消息**：Discord 单条 `content` 上限 2000 字符，LLM 简报可能超长。期望：截断到 2000 字符以内，结尾为 `…`，而不是 400 失败。（测试加在 Task 3）
3. **Discord 返回非 2xx**：webhook 失效时 `requests.post` 不抛异常，当前代码会误报成功。期望：判为失败，重试后仍失败则回退打印到终端。（测试加在 Task 3）
4. **interval 模式取价时刻**：interval 模式下 `run_once` 仍按 `schedule_time` 取盘中价，收盘后每次都拿同一根 K 线。期望：interval 模式取"当前时刻"的价格。（测试加在 Task 4）
5. **未设置 `OPENAI_API_KEY` 时 import**：当前 `OpenAI(api_key=None)` 在 import 时就抛异常，导致连测试都无法 import `parser`。期望：import 成功，只在实际调用时失败并返回 `""`。（测试加在 Task 1）

---

### Task 1: 仓库卫生 + 测试基础设施 + LLM 客户端延迟初始化

**Files:**
- Modify: `.gitignore`
- Create: `requirements-dev.txt`
- Modify: `requirements.txt`（`schedule` → `schedule>=1.2.2`）
- Modify: `llm_agent.py`
- Modify: `CODE_REVIEW.md`（顶部加"状态更新"小节）
- Create: `tests/__init__.py`（空）、`tests/conftest.py`、`tests/test_parser.py`、`tests/test_llm_agent.py`

**Interfaces:**
- Produces: `llm_agent._get_client() -> OpenAI`（首次调用时创建并缓存于模块级 `_client`）；`ask_llm(prompt: str, model: str = "gpt-4o") -> str` 签名不变。
- Produces: `tests/conftest.py` 中 autouse fixture `isolated_db(tmp_path, monkeypatch)`，把 `tools.storage.DB_PATH` 指向 `tmp_path / "test.db"`。

- [ ] **Step 1: 清理被跟踪的生成文件**

`.gitignore` 追加 `__pycache__/`、`*.pyc`、`*.db`、`*.db-wal`、`*.db-shm`、`.pytest_cache/`，然后：

```bash
git rm -r --cached __pycache__ tools/__pycache__ stock_agent.db
```

Expected: `git status` 显示这些文件为 deleted（本地文件仍在）。

- [ ] **Step 2: 写失败测试**

`tests/test_llm_agent.py`:
```python
def test_import_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import importlib, llm_agent
    importlib.reload(llm_agent)  # must not raise
    assert llm_agent._client is None

def test_ask_llm_returns_empty_on_error(monkeypatch):
    import llm_agent
    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kw): raise RuntimeError("x")
    monkeypatch.setattr(llm_agent, "_get_client", lambda: Boom)
    assert llm_agent.ask_llm("hi") == ""
```

`tests/test_parser.py`（针对 `_validate_and_fix`，纯函数）：
- `test_tickers_normalized`：`{"tickers": [" tsla", "AAPL", "aapl", "brk.b"]}` → `["TSLA", "AAPL", "BRK.B"]`
- `test_no_tickers_raises`：`{"tickers": []}` → `pytest.raises(ValueError)`
- `test_threshold_percent_string`：`"4%"` → `4.0`；`0`、`80` → `5.0`
- `test_invalid_enums_fall_back`：`notify_method="email"` → `"console"`，`report_style="x"` → `"summary"`，`report_language="jp"` → `"zh"`
- `test_bad_time_falls_back`：`schedule_time="9:45"` → `"16:10"`
- `test_interval_mode`：`schedule_mode="interval", interval_minutes=0` → `10`；`schedule_mode="daily", interval_minutes=30` → `0`
- `test_language_none_does_not_crash`：`report_language=None` → `"zh"`（当前代码对 `None` 调 `.lower()` 会崩）

- [ ] **Step 3: 运行，确认失败**

Run: `python -m pytest -q`
Expected: `test_import_without_api_key` 失败（`OpenAIError`）、`test_language_none_does_not_crash` 失败（`AttributeError`）。

- [ ] **Step 4: 实现**

- `llm_agent.py`：删除模块级 `client = OpenAI(...)` 和 import 时的 warning；新增 `_client = None` 与 `_get_client()`，key 缺失时在 `_get_client()` 里抛 `RuntimeError("OPENAI_API_KEY is not set")`（被 `ask_llm` 的 `except` 吞掉并返回 `""`）。`load_dotenv()` 保留在模块顶部。
- `parser.py`：`report_language` 与 `schedule_mode` 读取改为 `str(cfg.get(...) or default).lower().strip()`。
- `CODE_REVIEW.md` 顶部加"状态更新（2026-10-20）"：#2 #3 #5 #6 #7 #9 #11 #14 已修复；#1 经核查 `.env` 未出现在 git 历史中；#8 #10 和"日志/重试"由本计划处理。

- [ ] **Step 5: 运行，确认通过**

Run: `pip install -r requirements-dev.txt && python -m pytest -q`
Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: untrack generated files, add pytest suite, lazy-init OpenAI client"
```

---

### Task 2: 用 logging 替换诊断性 print

**Files:**
- Modify: `agent.py`、`llm_agent.py`、`tools/data_tools.py`、`tools/notifier.py`、`tools/reporter.py`
- Test: `tests/test_logging.py`

**Interfaces:**
- Produces: 每个模块顶部 `logger = logging.getLogger(__name__)`；`agent.py` 新增 `setup_logging(level: str = "INFO") -> None`，在 `__main__` 最开始调用，格式 `"%(asctime)s %(levelname)s %(name)s: %(message)s"`。`config.yaml` 可选键 `log_level`。

- [ ] **Step 1: 写失败测试**

```python
def test_missing_price_logs_warning(monkeypatch, caplog):
    import agent
    monkeypatch.setattr(agent, "get_intraday_price_at", lambda *a, **k: None)
    monkeypatch.setattr(agent, "get_previous_close", lambda t: 100.0)
    monkeypatch.setattr(agent, "generate_brief", lambda *a, **k: "b")
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    rules = {"tickers": ["TSLA"], "alert_threshold": 5.0, "schedule_time": "16:10", "news_enabled": False}
    agent.run_once(rules, {})
    assert any(r.levelname == "WARNING" and "TSLA" in r.message for r in caplog.records)
```

另加 `test_data_tools_logs_exception`：让 `yf.Ticker` 抛异常，断言 `get_previous_close` 返回 `None` 且有一条 `WARNING` 日志（当前异常被静默吞掉）。

- [ ] **Step 2: 运行，确认失败** — Run: `python -m pytest tests/test_logging.py -q`，Expected: FAIL。
- [ ] **Step 3: 实现** — 把 `agent.py` 里 `Warning:`/`Error saving` 改为 `logger.warning`/`logger.exception`，`llm_agent` 的 `[LLM Error]` 改为 `logger.error`，`data_tools` 与 `reporter` 中的 `except Exception:` 加 `logger.warning("...%s", ticker, exc_info=True)`，`notifier` 失败信息改 `logger.error`。`print(rules)` 改为 `logger.info("parsed rules: %s", rules)`；`[SCHEDULE]`、`please enter the prompt:`、console 通知保持 `print`。
- [ ] **Step 4: 运行全部测试** — Run: `python -m pytest -q`，Expected: PASS。
- [ ] **Step 5: Commit** — `git commit -am "refactor: replace diagnostic prints with logging"`

---

### Task 3: 网络调用重试 + Discord 发送健壮化

**Files:**
- Create: `tools/retry.py`
- Modify: `tools/data_tools.py`、`tools/notifier.py`
- Test: `tests/test_retry.py`、`tests/test_notifier.py`

**Interfaces:**
- Produces: `with_retry(func: Callable[[], T], attempts: int = 3, base_delay: float = 1.0, sleep: Callable[[float], None] = time.sleep) -> T`。`func` 抛异常即重试，第 n 次失败后等待 `base_delay * 2 ** (n-1)`；用尽后重新抛出最后一次异常。
- Produces: `DISCORD_MAX_LEN = 2000`（`tools/notifier.py`）。

- [ ] **Step 1: 写失败测试**

`tests/test_retry.py`:
- `test_succeeds_after_failures`：前 2 次抛 `ValueError`、第 3 次返回 `"ok"` → 返回 `"ok"`，记录的 sleep 序列为 `[1.0, 2.0]`
- `test_raises_after_exhausted`：始终抛 → `pytest.raises(ValueError)`，调用次数 3

`tests/test_notifier.py`（monkeypatch `tools.notifier.requests.post`，`sleep` 置空）：
- `test_non_2xx_is_failure`：post 返回 `status_code=404`、`raise_for_status` 抛 `requests.HTTPError` → `send_discord(...) is False`，post 被调用 3 次
- `test_long_message_truncated`：`content="x"*5000, mention_id="42"` → 发出的 `payload["content"]` 长度 `<= 2000`，以 `"<@42> "` 开头、以 `"…"` 结尾
- `test_fallback_prints_to_console`：`notify("discord", "hello", discord_webhook="u")` 且发送失败 → `capsys` 输出包含 `hello`

- [ ] **Step 2: 运行，确认失败** — Run: `python -m pytest tests/test_retry.py tests/test_notifier.py -q`，Expected: FAIL（`tools.retry` 不存在；非 2xx 被当成功）。
- [ ] **Step 3: 实现**
  - `tools/retry.py` 按上述签名实现，每次失败 `logger.warning`。
  - `send_discord`：先拼 mention，再截断到 `DISCORD_MAX_LEN`（超长时取前 `DISCORD_MAX_LEN-1` 字符加 `…`）；在 `with_retry` 内调用 `requests.post(...)` 并 `resp.raise_for_status()`；最终异常时返回 `False`。`send_discord` 新增关键字参数 `sleep=time.sleep` 透传给 `with_retry`，便于测试。
  - `data_tools`：`get_previous_close` 中的 `t.history(...)`、`get_intraday_price_at` 中的两次 `yf.download(...)` 各包一层 `with_retry`；外层 `try/except` 返回 `None` 的语义不变。
- [ ] **Step 4: 运行全部测试** — Run: `python -m pytest -q`，Expected: PASS。
- [ ] **Step 5: Commit** — `git commit -am "feat: retry network calls with backoff; harden discord notifier"`

---

### Task 4: 调度器尊重时区 + interval 模式取当前价

**Files:**
- Modify: `agent.py`（`run_scheduler`、`run_once`）
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Produces: `target_time_for(cfg_rules: dict, tz: ZoneInfo) -> str`（`agent.py`）：`schedule_mode == "interval"` 时返回 `datetime.now(tz).strftime("%H:%M")`，否则返回 `cfg_rules["schedule_time"]`。`run_once` 用它替代直接读 `cfg_rules["schedule_time"]`。

- [ ] **Step 1: 确认 schedule 版本支持时区**

Run: `python -c "import schedule, inspect; print(inspect.signature(schedule.Job.at))"`
Expected: 输出包含 `tz` 参数。否则 `pip install -U "schedule>=1.2.2"`。

- [ ] **Step 2: 写失败测试**
- `test_daily_job_uses_config_timezone`：`schedule.clear()` 后，monkeypatch `agent.time.sleep` 抛 `KeyboardInterrupt` 让循环立刻退出；调用 `run_scheduler({"schedule_mode": "daily", "schedule_time": "16:30"}, {"timezone": "Asia/Tokyo"})`，断言 `schedule.jobs[0].at_time_zone` 的 `str(...)` 等于 `"Asia/Tokyo"`。
- `test_interval_mode_uses_now`：`target_time_for({"schedule_mode": "interval", "schedule_time": "16:10"}, ZoneInfo("UTC"))` 等于当前 UTC 的 `"%H:%M"`（monkeypatch `agent.datetime` 固定为 `2026-10-20 18:05 UTC` → `"18:05"`）。
- `test_daily_mode_uses_schedule_time`：daily 模式返回 `"16:10"`。

- [ ] **Step 3: 运行，确认失败** — Run: `python -m pytest tests/test_scheduler.py -q`，Expected: FAIL。
- [ ] **Step 4: 实现** — `schedule.every().day.at(at_time, tz)`；`default_at_time` 改为 `"09:45"`（`"9:45"` 会被 schedule 判为非法）；删除 `run_scheduler` 中未使用的 `default_language`；新增 `target_time_for` 并在 `run_once` 中使用。
- [ ] **Step 5: 运行全部测试** — Run: `python -m pytest -q`，Expected: PASS。
- [ ] **Step 6: Commit** — `git commit -am "fix: schedule jobs in configured timezone; interval mode prices at current time"`

---

### Task 5: 让 `report_style` 与 `lookback_days` 真正生效

**Files:**
- Modify: `tools/data_tools.py`、`tools/reporter.py`、`agent.py`
- Test: `tests/test_data_tools.py`、`tests/test_reporter.py`

**Interfaces:**
- Produces: `get_lookback_change_pct(ticker: str, days: int) -> Optional[float]`（`tools/data_tools.py`）：取 `period=f"{days + 5}d", interval="1d"` 的日线，用最近一根收盘价对比往前第 `days` 根交易日收盘价；数据不足 `days + 1` 根返回 `None`。
- Produces: `generate_brief(model, snapshot, news_map, threshold, language="zh", style="summary", lookback_days=5) -> str`。`snapshot` 每行新增键 `lookback_change_pct: Optional[float]`。
- Consumes: Task 3 的 `with_retry`。

- [ ] **Step 1: 写失败测试**

`tests/test_data_tools.py`（monkeypatch `yf.Ticker` 返回带 `history()` 的假对象，`Close` 为 pandas Series）：
- `test_lookback_change_pct`：收盘价 `[100, 101, 102, 103, 104, 110]`，`days=5` → `pytest.approx(10.0)`
- `test_lookback_insufficient_data`：只有 3 根，`days=5` → `None`

`tests/test_reporter.py`（monkeypatch `tools.reporter.ask_llm` 捕获 prompt）：
- `test_summary_style_prompt`：`style="summary"` → prompt 包含 `"max 6 bullet points"`
- `test_detailed_style_prompt`：`style="detailed"` → prompt 包含 `"one short paragraph per ticker"`，且不含 `"max 6 bullet points"`
- `test_lookback_in_context`：行 `lookback_change_pct=3.21, lookback_days=5` → prompt 包含 `"5d_change=3.21%"`；为 `None` 时包含 `"5d_change=n/a"`

- [ ] **Step 2: 运行，确认失败** — Run: `python -m pytest tests/test_data_tools.py tests/test_reporter.py -q`，Expected: FAIL。
- [ ] **Step 3: 实现** — `data_tools` 新增上述函数（`history` 包 `with_retry`）；`reporter` 按 `style` 切换 prompt 第一段（summary 保留原文；detailed 用 `"Write one short paragraph per ticker covering price move, {lookback_days}-day trend and the news, then a one-line summary."`），context 行追加 `f", {lookback_days}d_change={...}"`；`agent.run_once` 计算并写入 `lookback_change_pct`，把 `cfg_rules.get("report_style", "summary")` 和 `cfg_rules.get("lookback_days", 5)` 传给 `generate_brief`。
- [ ] **Step 4: 运行全部测试** — Run: `python -m pytest -q`，Expected: PASS。
- [ ] **Step 5: Commit** — `git commit -am "feat: honor report_style and lookback_days in briefs"`

---

### Task 6: 写入 `runs` 表 + 无数据时的处理

**Files:**
- Modify: `tools/storage.py`、`agent.py`
- Test: `tests/test_storage.py`、`tests/test_run_once.py`

**Interfaces:**
- Produces: `record_run(run_ts: str, status: str, note: Optional[str] = None) -> None`（`tools/storage.py`）。`status` 取值：`"ok"`（全部 ticker 成功）、`"partial"`（部分跳过，`note` 为逗号分隔的跳过 ticker）、`"no_data"`（全部跳过）、`"error"`（`run_once` 内未捕获异常，`note` 为 `repr(e)[:500]`，记录后重新抛出）。
- Consumes: Task 1 的 `isolated_db` fixture。

- [ ] **Step 1: 写失败测试**

`tests/test_storage.py`：`init_db()` 后 `record_run("2026-10-20T16:30:00-04:00", "ok")`，查询 `runs` 表得到 1 行，`status == "ok"`。

`tests/test_run_once.py`（monkeypatch 价格函数、`generate_brief`、`notify`、`time.sleep`；先 `init_db()`）：
- `test_partial_run_recorded`：TSLA 有价、AAPL 无价 → `runs` 最后一行 `status="partial"`、`note="AAPL"`
- `test_no_data_skips_llm`：全部无价 → `generate_brief` 未被调用；`notify` 收到 `"[DAILY BRIEF]\nNo market data available."`；`status="no_data"`
- `test_error_recorded_and_reraised`：`get_previous_close` 抛 `RuntimeError("boom")` → `pytest.raises(RuntimeError)`，`status="error"`，`note` 包含 `"boom"`

- [ ] **Step 2: 运行，确认失败** — Run: `python -m pytest tests/test_storage.py tests/test_run_once.py -q`，Expected: FAIL。
- [ ] **Step 3: 实现** — `storage.record_run` 仿照 `save_price`；`run_once` 主体包进 `try/except Exception`，收集 `skipped: list[str]`，`snapshot` 为空时直接 notify 固定文案并 return，正常结束时按 `skipped` 判定 `ok`/`partial` 并 `record_run`；`except` 分支记 `error` 后 `raise`。`record_run` 自身失败只 `logger.exception`，不影响主流程。
- [ ] **Step 4: 运行全部测试** — Run: `python -m pytest -q`，Expected: PASS。
- [ ] **Step 5: 手动冒烟（需要 `.env` 和 `config.yaml`）**

Run: `echo "check AAPL" | python agent.py -s`
Expected: 输出 `[NOTIFY][console] [DAILY BRIEF]...`，且 `sqlite3 stock_agent.db "select status from runs order by id desc limit 1"` 返回 `ok`、`partial` 或 `no_data`。

- [ ] **Step 6: Commit** — `git commit -am "feat: record run status; skip LLM when no market data"`
