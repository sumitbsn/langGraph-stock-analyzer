from __future__ import annotations

import html
import re
from urllib.parse import quote_plus, urlparse
from typing import Any, cast

from typing_extensions import NotRequired, TypedDict

import feedparser
import pandas as pd
import yfinance as yf
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph


class GraphState(TypedDict, total=False):
    ticker: str
    company_name: NotRequired[str]
    period: NotRequired[str]
    interval: NotRequired[str]
    model: NotRequired[str]
    price_data: NotRequired[pd.DataFrame]
    metrics: NotRequired[dict[str, Any]]
    research: NotRequired[list[dict[str, str]]]
    analysis: NotRequired[str]


NEWS_HINTS = (
    "news",
    "earnings",
    "guidance",
    "forecast",
    "analyst",
    "downgrade",
    "upgrade",
    "price target",
    "revenue",
    "quarter",
    "stock",
    "shares",
)


def _clean_html_summary(summary: str) -> str:
    if not summary:
        return ""
    text = re.sub(r"<[^>]+>", " ", summary)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_google_news_source(summary: str) -> str:
    if not summary:
        return ""
    match = re.search(r"<font color=\"#6f6f6f\">([^<]+)</font>", summary)
    if not match:
        return ""
    return html.unescape(match.group(1)).strip()


def _extract_google_news_article_url(summary: str, fallback_href: str) -> str:
    if not summary:
        return fallback_href
    matches = re.findall(r'<a href="([^"]+)"', summary)
    for candidate in matches:
        if "news.google.com" not in candidate:
            return html.unescape(candidate)
    return fallback_href


def _is_relevant_result(item: dict[str, str], ticker: str, company_name: str) -> bool:
    href = item.get("href", "")
    title = item.get("title", "").lower()
    body = item.get("body", "").lower()
    parsed = urlparse(href)
    host = parsed.netloc.lower()
    company_terms = [company_name.lower(), ticker.lower()]

    if not host:
        return False

    text_blob = f"{title} {body} {href}".lower()
    has_company_reference = any(term and term in text_blob for term in company_terms)
    looks_like_news = any(keyword in text_blob for keyword in NEWS_HINTS)
    return has_company_reference or looks_like_news


def _build_google_news_queries(ticker: str, company_name: str) -> list[str]:
    subject = company_name.strip() or ticker
    return [
        f'{subject} {ticker} stock',
        f'{subject} {ticker} earnings',
        f'{ticker} shares market news',
    ]


def _google_news_rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"


def search_stock_info(state: GraphState) -> GraphState:
    company_name = state.get("company_name", "").strip()
    ticker = state.get("ticker", "").strip().upper()
    if not ticker:
        raise ValueError("Ticker is required for stock research.")
    research: list[dict[str, str]] = []
    seen_links: set[str] = set()

    for query in _build_google_news_queries(ticker, company_name):
        feed = feedparser.parse(_google_news_rss_url(query))
        for entry in feed.entries:
            raw_summary = getattr(entry, "summary", "")
            normalized = {
                "title": getattr(entry, "title", ""),
                "href": _extract_google_news_article_url(raw_summary, getattr(entry, "link", "")),
                "body": _clean_html_summary(raw_summary),
                "source": _extract_google_news_source(raw_summary),
            }
            href = normalized["href"]
            if not href or href in seen_links:
                continue
            if not _is_relevant_result(normalized, ticker, company_name):
                continue
            seen_links.add(href)
            research.append(normalized)
            if len(research) >= 5:
                return {"research": research}

    return {"research": research}


def fetch_price_data(state: GraphState) -> GraphState:
    ticker = state.get("ticker", "").strip().upper()
    if not ticker:
        raise ValueError("Ticker is required for stock price lookup.")
    period = state.get("period", "6mo")
    interval = state.get("interval", "1d")

    ticker_candidates = [ticker]
    if "." not in ticker:
        ticker_candidates.extend([f"{ticker}.NS", f"{ticker}.BO"])

    periods_to_try = [period]
    if period != "1y":
        periods_to_try.append("1y")
    if period != "3mo":
        periods_to_try.append("3mo")

    history = pd.DataFrame()
    successful_ticker = ticker
    for candidate_ticker in ticker_candidates:
        for candidate_period in periods_to_try:
            history = yf.Ticker(candidate_ticker).history(
                period=candidate_period,
                interval=interval,
                auto_adjust=False,
            )
            if not history.empty:
                successful_ticker = candidate_ticker
                break

            download_history = cast(
                pd.DataFrame,
                yf.download(
                tickers=candidate_ticker,
                period=candidate_period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
                ),
            )
            if not download_history.empty:
                if isinstance(download_history.columns, pd.MultiIndex):
                    if candidate_ticker in download_history.columns.get_level_values(-1):
                        download_history = download_history.xs(candidate_ticker, axis=1, level=-1)
                    else:
                        download_history.columns = download_history.columns.get_level_values(0)
                history = download_history
                successful_ticker = candidate_ticker
                break

        if not history.empty:
            break

    if history.empty:
        attempted = ", ".join(ticker_candidates)
        raise ValueError(
            f"No price data returned for ticker '{ticker}'. Tried: {attempted}. For Indian stocks, use the Yahoo Finance exchange suffix when needed, such as .NS for NSE or .BO for BSE."
        )

    normalized_history = cast(pd.DataFrame, history.tail(120))
    return {"ticker": successful_ticker, "price_data": normalized_history}


def summarize_prices(state: GraphState) -> GraphState:
    frame = state.get("price_data")
    if frame is None:
        raise ValueError("Price data is required before summarization.")
    frame = frame.copy()
    close = frame["Close"].dropna()
    volume = frame["Volume"].dropna()

    latest_close = float(close.iloc[-1])
    first_close = float(close.iloc[0])
    absolute_change = latest_close - first_close
    percent_change = (absolute_change / first_close) * 100 if first_close else 0.0
    avg_volume = float(volume.mean()) if not volume.empty else 0.0
    high_20 = float(close.tail(20).max())
    low_20 = float(close.tail(20).min())
    daily_returns = close.pct_change().dropna()
    volatility = float(daily_returns.std() * (252 ** 0.5)) if not daily_returns.empty else 0.0
    sma_20 = float(close.tail(20).mean()) if len(close) >= 20 else latest_close
    sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else first_close

    trend_direction = "Sideways"
    if latest_close > sma_20 > sma_50 and percent_change > 3:
        trend_direction = "Uptrend"
    elif latest_close < sma_20 < sma_50 and percent_change < -3:
        trend_direction = "Downtrend"

    trend_strength = "Moderate"
    if abs(percent_change) >= 15:
        trend_strength = "Strong"
    elif abs(percent_change) < 5:
        trend_strength = "Weak"

    recent_rows = frame[["Open", "High", "Low", "Close", "Volume"]].tail(10).round(2)

    metrics = {
        "rows_analyzed": int(len(frame)),
        "latest_close": round(latest_close, 2),
        "period_start_close": round(first_close, 2),
        "absolute_change": round(absolute_change, 2),
        "percent_change": round(percent_change, 2),
        "average_volume": round(avg_volume, 2),
        "20_day_high_close": round(high_20, 2),
        "20_day_low_close": round(low_20, 2),
        "20_day_sma": round(sma_20, 2),
        "50_day_sma": round(sma_50, 2),
        "trend_direction": trend_direction,
        "trend_strength": trend_strength,
        "annualized_volatility": round(volatility, 4),
        "recent_prices": recent_rows.to_dict(orient="index"),
    }

    return {"metrics": metrics}


def analyze_with_llm(state: GraphState) -> GraphState:
    model_name = state.get("model", "gpt-oss:20b")
    llm = ChatOllama(model=model_name, temperature=0.2)

    prompt = (
        "You are a market analysis assistant. Use the provided stock price metrics to write a concise, factual analysis. "
        "Use the web research snippets only as supporting context and mention when information is based on recent headlines rather than price action. "
        "Do not claim certainty or provide financial advice. Respond with these sections: Trend, Risk, Volume, "
        "Recent Context, Levels to Watch, and Bottom Line. Include a direct statement about whether the data indicates an uptrend, downtrend, or sideways trend.\n\n"
        f"Ticker: {state.get('ticker', '')}\n"
        f"Company Name: {state.get('company_name', '')}\n"
        f"Period: {state.get('period', '6mo')}\n"
        f"Interval: {state.get('interval', '1d')}\n"
        f"Metrics: {state.get('metrics', {})}\n"
        f"Web Research: {state.get('research', [])}"
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    return {"analysis": content}



def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("search_stock_info", search_stock_info)
    graph.add_node("fetch_price_data", fetch_price_data)
    graph.add_node("summarize_prices", summarize_prices)
    graph.add_node("analyze_with_llm", analyze_with_llm)

    graph.add_edge(START, "search_stock_info")
    graph.add_edge("search_stock_info", "fetch_price_data")
    graph.add_edge("fetch_price_data", "summarize_prices")
    graph.add_edge("summarize_prices", "analyze_with_llm")
    graph.add_edge("analyze_with_llm", END)

    return graph.compile()


def run_analysis(
    ticker: str,
    company_name: str = "",
    period: str = "6mo",
    interval: str = "1d",
    model: str = "gpt-oss:20b",
) -> GraphState:
    compiled_graph = build_graph()
    initial_state: GraphState = {
        "ticker": ticker.upper(),
        "company_name": company_name,
        "period": period,
        "interval": interval,
        "model": model,
    }
    return cast(GraphState, compiled_graph.invoke(initial_state))
