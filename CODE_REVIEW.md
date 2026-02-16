# Stock Tracker 项目 Code Review

## 总体评价

这是一个结构清晰的 Agentic AI 股票追踪项目，核心思路（自然语言配置 → LLM 解析 → 定时抓取 → 报告/告警）设计得不错。代码可读性较好，模块分工合理。以下按严重程度分类列出发现的问题。

---

## Critical 问题

### 1. `.env` 中的 API Key 已泄露到 Git 历史

> [!CAUTION]
> 虽然 `.gitignore` 已包含 `.env`，但 `.env` 在之前的 commit 中已经被提交过。`OPENAI_API_KEY` 和 `DISCORD_WEBHOOK_URL` 已暴露在 git 历史中。**应立即轮换（rotate）这些密钥。**

**建议：**
- 立即在 OpenAI Dashboard 重新生成 API Key
- 重新生成 Discord Webhook URL
- 考虑用 `git filter-branch` 或 `BFG Repo-Cleaner` 从历史中移除 `.env`

### 2. `tools/` 缺少 `__init__.py`

当前 `tools/` 作为包被 import（如 `from tools.data_tools import ...`），但缺少 `__init__.py`。在某些 Python 环境下（尤其是旧版本或作为包安装时）可能导致 import 失败。

---

## Important 问题

### 3. `requirements.txt` 缺少 `requests`

[notifier.py](file:///Users/ansel/coding/antigravity_proj/stock-tracker/tools/notifier.py) 使用了 `import requests`，但 `requirements.txt` 中没有声明这个依赖。虽然 `requests` 可能被其他包间接安装，但应该显式声明。

### 4. `config.yaml` 中的 `defaults` 字段未被使用

[config.yaml](file:///Users/ansel/coding/antigravity_proj/stock-tracker/config.yaml) 定义了 `defaults` 层级：
```yaml
defaults:
  alert_threshold: 5.0
  schedule_time: "16:30"
  notify_method: "console"
```
但 [agent.py](file:///Users/ansel/coding/antigravity_proj/stock-tracker/agent.py) 中直接将整个 `base_cfg` 当作 `cfg_global` 传入，从未读取 `base_cfg["defaults"]`。这些配置实际上是"死代码"。

### 5. `send_discord()` 在 `mention_id` 为 `None` 时仍然拼接 `<@None>`

[notifier.py L5](file:///Users/ansel/coding/antigravity_proj/stock-tracker/tools/notifier.py#L4-L5) 中：
```python
def send_discord(webhook_url: str, content: str, mention_id: Optional[str] = None) -> bool:
    content = f"<@{mention_id}> " + content  # mention_id=None 时变为 "<@None> ..."
```
应该先判断 `mention_id` 是否存在。

### 6. `get_change_pct_vs_prev_close()` 重复调用 `get_previous_close()`

[agent.py L35-38](file:///Users/ansel/coding/antigravity_proj/stock-tracker/agent.py#L35-L38)：
```python
prev_close = get_previous_close(t)        # 第 1 次调用
...
change_pct = get_change_pct_vs_prev_close(t, price_now)  # 内部又调用了一次
```
而 `get_change_pct_vs_prev_close()` 内部又独立调用了 `get_previous_close()`，导致每个 ticker 对 Yahoo Finance API 发两次相同请求。浪费网络资源且增加延迟。

### 7. `reporter.py` 中 `language_dict` 缺少 KeyError 防护

[reporter.py L80](file:///Users/ansel/coding/antigravity_proj/stock-tracker/tools/reporter.py#L80)：
```python
lang_name = language_dict[language]
```
如果 `language` 不在 `language_dict` 中会直接抛出 `KeyError`。虽然上游 `parser.py` 做了校验，但作为独立函数应当自我防护。

### 8. 没有任何测试

项目中没有任何测试文件。对于涉及 LLM 解析、数据抓取、通知推送的 agent 系统，至少应有：
- `parser.py` 的 `_validate_and_fix()` 单元测试
- `notifier.py` 的 mock 测试
- `storage.py` 的 DB 操作测试

---

## Minor 问题

### 9. `storage.py` 的 DDL 解析方式脆弱

[storage.py L32](file:///Users/ansel/coding/antigravity_proj/stock-tracker/tools/storage.py#L32)：
```python
for stmt in DDL.strip().split(";\n\n"):
```
用 `";\n\n"` 分割 SQL 语句不是一种可靠的方式。若 DDL 格式稍有变化（比如多一个空行或少一个空行），拆分就会出错。建议使用 `conn.executescript(DDL)` 或者逐条 `execute` 并用更稳健的分割方式。

### 10. `llm_agent.py` 模块级初始化 OpenAI 客户端

[llm_agent.py L6-9](file:///Users/ansel/coding/antigravity_proj/stock-tracker/llm_agent.py#L6-L9)：
```python
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)
```
在模块导入时就创建了 `OpenAI` 客户端。如果 `OPENAI_API_KEY` 未设置，`client` 仍会创建但所有调用都会失败。建议加一个 early check 或者延迟初始化。

### 11. `data_tools.py` 的 `tz_localize` 逻辑可能出错

[data_tools.py L39](file:///Users/ansel/coding/antigravity_proj/stock-tracker/tools/data_tools.py#L39)：
```python
df_local = df.tz_convert(tz) if df.index.tz is not None else df.tz_localize(tz)
```
如果数据没有时区信息，直接 `tz_localize` 假设数据是目标时区，但 Yahoo Finance 返回的数据时区可能是 UTC。应该先 localize 为 UTC 再 convert。

### 12. `agent.py` 中大量的 `load_dotenv()` 调用

`load_dotenv()` 在 `agent.py` 和 `llm_agent.py` 中各调用一次。应该只在入口文件调用一次。

### 13. `README.md` 小问题

- 使用了 emoji（如 ` 🤖`），这和代码中不使用 emoji 的规范有冲突
- 安装方式使用 `venv` 但用户实际用 `conda`，可以补充 conda 安装方式
- 缺少 License 类型说明（虽然有 LICENSE 文件）

### 14. 日文语言代码错误

[reporter.py L67](file:///Users/ansel/coding/antigravity_proj/stock-tracker/tools/reporter.py#L67)：
```python
"jp": "jp-JP",
```
日文的标准语言代码应为 `ja` / `ja-JP`，不是 `jp-JP`。

---

## 架构改进建议

| 改进项 | 说明 |
|--------|------|
| **日志系统** | 用 `logging` 模块替代 `print()`，支持日志级别和文件写入 |
| **错误重试** | 网络请求（yfinance、Discord）应加 retry + backoff 机制 |
| **Graceful shutdown** | 调度器缺少信号处理，`Ctrl+C` 后数据库连接可能未正确关闭 |
| **数据库连接管理** | 每次操作都 `connect/close`，高频模式下考虑使用连接池或 keep-alive |
| **类型安全** | 考虑添加 `py.typed` 和完整类型注解，便于 IDE 支持和 mypy 检查 |

---

## 总结评分

| 维度 | 评分（满5） | 说明 |
|------|:-----------:|------|
| **功能完整性** | ⭐⭐⭐⭐ | 核心功能完整，支持多种调度模式 |
| **代码质量** | ⭐⭐⭐ | 可读性好，但有重复调用和防御不足 |
| **安全性** | ⭐⭐ | API Key 泄露需立即处理 |
| **可测试性** | ⭐⭐ | 无测试用例，函数耦合度可降低 |
| **文档** | ⭐⭐⭐⭐ | README 详细，有示例输出 |
| **可维护性** | ⭐⭐⭐ | 模块化尚可，缺日志和错误处理 |
