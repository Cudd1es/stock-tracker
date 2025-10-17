from typing import Dict, List, Optional
import yfinance as yf
from llm_agent import ask_llm

def fetch_news_headlines(ticker: str, topk: int = 3) -> List[Dict[str, str]]:
    """
    Try yfinance's news field; return list of {title, link}.
    """
    try:
        t = yf.Ticker(ticker)
        items = t.news or []
        out = []
        for it in items[:topk]:
            title = it.get("title") or ""
            link = it.get("link") or ""
            if title:
                out.append({"title": title, "link": link})
        return out
    except Exception:
        return []

def generate_brief(model: str, snapshot: List[Dict[str, Optional[float]]], news_map: Dict[str, List[Dict[str, str]]], threshold: float) -> str:
    """
    ask llm to generate a brief report
    snapshot: list of {ticker, price_now, prev_close, change_pct}
    news_map: ticker -> list of {title, link}
    """
    lines = []
    for row in snapshot:
        t = row["ticker"]
        cp = row["change_pct"]
        pn = row["price_now"]
        pv = row["prev_close"]
        lines.append(f"{t}: now={pn:.2f}, prev_close={pv:.2f}, change={cp:.2f}%")
        news = news_map.get(t, [])
        for n in news:
            lines.append(f"  - {n['title']} ({n.get('link', '')})")
    context = "\n".join(lines)

    prompt = f"""Write a concise end-of-day style brief (max 6 bullet points) for the following tickers.
Emphasize any move beyond ±{threshold:.1f}% . Be neutral and factual. Avoid investment advice.

DATA:
{context}

Output in Chinese, use clear bullets and a one-line summary at the end.
"""
    return ask_llm(prompt, model=model)