from __future__ import annotations

from pathlib import Path
import sqlite3
import json

import pandas as pd
import streamlit as st

from src.stock_analyzer.components.company_autocomplete import company_autocomplete
from src.stock_analyzer.graph import run_analysis


DB_PATH = Path(__file__).parent / "src" / "stock_analyzer" / "india_symbols.db"


@st.cache_data
def _load_symbol_catalog() -> list[dict[str, str]]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            "SELECT symbol, company_name, exchange FROM companies"
        ).fetchall()
    return [
        {"symbol": symbol, "company_name": company_name, "exchange": exchange}
        for symbol, company_name, exchange in rows
    ]


def _query_symbol_catalog(query: str, page: int = 0, page_size: int = 20) -> list[dict[str, str]]:
    normalized_query = query.strip().lower()
    if not DB_PATH.exists():
        return []

    with sqlite3.connect(DB_PATH) as connection:
        if normalized_query:
            rows = connection.execute(
                """
                SELECT symbol, company_name, exchange
                FROM companies
                WHERE lower(symbol) LIKE ? OR lower(company_name) LIKE ?
                ORDER BY
                    CASE
                        WHEN lower(symbol) = ? OR lower(company_name) = ? THEN 0
                        WHEN lower(symbol) LIKE ? THEN 1
                        WHEN lower(company_name) LIKE ? THEN 2
                        ELSE 3
                    END,
                    CASE WHEN exchange = 'BSE' THEN 1 ELSE 0 END,
                    length(company_name),
                    company_name,
                    symbol
                LIMIT ? OFFSET ?
                """,
                (
                    f"%{normalized_query}%",
                    f"%{normalized_query}%",
                    normalized_query,
                    normalized_query,
                    f"{normalized_query}%",
                    f"{normalized_query}%",
                    page_size,
                    page * page_size,
                ),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT symbol, company_name, exchange
                FROM companies
                ORDER BY
                    CASE WHEN exchange = 'BSE' THEN 1 ELSE 0 END,
                    company_name,
                    symbol
                LIMIT ? OFFSET ?
                """,
                (page_size, page * page_size),
            ).fetchall()

    return [
        {
            "symbol": symbol,
            "company_name": company_name,
            "exchange": exchange,
            "label": f"{symbol} - {company_name} ({exchange})",
        }
        for symbol, company_name, exchange in rows
    ]


def _search_symbol_options(query: str, preferred_symbol: str = "") -> list[dict[str, str]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    lowered_query = normalized_query.lower()
    options: list[dict[str, str]] = []
    seen_symbols: set[str] = set()

    for item in _load_symbol_catalog():
        symbol = (item.get("symbol") or "").strip().upper()
        short_name = (item.get("company_name") or symbol).strip()
        exchange = (item.get("exchange") or "").strip()
        if not symbol or symbol in seen_symbols:
            continue
        searchable_text = f"{symbol} {short_name} {exchange}".lower()
        if lowered_query not in searchable_text:
            continue
        seen_symbols.add(symbol)
        label = f"{symbol} - {short_name}"
        if exchange:
            label = f"{label} ({exchange})"
        symbol_lower = symbol.lower()
        company_lower = short_name.lower()
        company_words = company_lower.split()

        if company_lower == lowered_query or symbol_lower == lowered_query:
            rank = 0
        elif symbol_lower.startswith(lowered_query):
            rank = 1
        elif company_lower.startswith(lowered_query):
            rank = 2
        elif any(part.startswith(lowered_query) for part in company_words):
            rank = 3
        elif lowered_query in company_words:
            rank = 4
        else:
            rank = 5

        if symbol_lower.endswith(".ns"):
            rank -= 0.25

        if exchange == "BSE":
            rank += 1

        options.append({
            "symbol": symbol,
            "company_name": short_name,
            "label": label,
            "rank": rank,
        })

    options.sort(key=lambda option: (option["rank"], len(option["company_name"]), option["label"]))
    options = options[:15]

    for option in options:
        option.pop("rank", None)

    return options


def _find_selected_index(options: list[dict[str, str]], symbol: str) -> int:
    normalized_symbol = symbol.strip().upper()
    for index, option in enumerate(options):
        if option["symbol"] == normalized_symbol:
            return index
    return 0


def _default_selected_asset() -> dict[str, str]:
    return {"symbol": "INFY", "company_name": "Infosys Limited", "label": "INFY - Infosys Limited"}


st.set_page_config(page_title="Stock Analyzer", page_icon="SA", layout="wide")

st.title("LangGraph Stock Analyzer")
st.caption("Analyze NSE/BSE stocks with Ollama gpt-oss:20b, market price history, and Google News research context.")

with st.sidebar:
    st.header("Inputs")
    if "selected_asset" not in st.session_state:
        st.session_state.selected_asset = _default_selected_asset()
    if "company_query" not in st.session_state:
        st.session_state.company_query = st.session_state.selected_asset["company_name"]
    if "company_page" not in st.session_state:
        st.session_state.company_page = 0

    current_asset = st.session_state.selected_asset
    st.caption("Company")
    company_query = st.session_state.company_query.strip()
    page_size = 20
    company_options = _query_symbol_catalog(company_query, page=st.session_state.company_page, page_size=page_size)
    has_more = len(company_options) == page_size

    component_payload = company_autocomplete(query=company_query, results=company_options, has_more=has_more)

    if isinstance(component_payload, str):
        payload = json.loads(component_payload)
        event_type = payload.get("type")
        if event_type == "query":
            new_query = (payload.get("value") or "").strip()
            if new_query != st.session_state.company_query:
                st.session_state.company_query = new_query
                st.session_state.company_page = 0
                if new_query:
                    st.session_state.selected_asset = {
                        "symbol": "",
                        "company_name": new_query,
                        "label": new_query,
                    }
                st.rerun()
        elif event_type == "load_more":
            st.session_state.company_page += 1
            st.rerun()
        elif event_type == "select":
            symbol = (payload.get("symbol") or "").strip().upper()
            company_name_value = (payload.get("company_name") or "").strip()
            if symbol:
                exchange = ".BO" if symbol.endswith(".BO") else "NSE" if symbol.endswith(".NS") or "." not in symbol else ""
                label = f"{symbol} - {company_name_value} ({exchange})" if exchange else f"{symbol} - {company_name_value}"
                st.session_state.selected_asset = {
                    "symbol": symbol,
                    "company_name": company_name_value,
                    "label": label,
                }
                st.session_state.company_query = company_name_value
                st.session_state.company_page = 0
                current_asset = st.session_state.selected_asset
                st.rerun()

    ticker = current_asset["symbol"].strip().upper()
    company_name = current_asset["company_name"].strip() or company_query
    period = st.selectbox("Price history period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
    interval = st.selectbox("Price interval", ["1d", "1h", "1wk"], index=0)
    model = st.text_input("Ollama model", value="gpt-oss:20b")
    run_clicked = st.button("Start analysis", type="primary", use_container_width=True)

st.markdown(
    "This tool combines recent price history, simple market statistics, and Google News headlines before sending the context to your local Ollama model."
)

st.info(
    "This app is focused on Indian markets. Company lookup is driven by a local NSE/BSE symbol database, and Yahoo Finance is used for price history with exchange-specific suffix handling such as .NS and .BO."
)

if run_clicked:
    if not ticker:
        st.error("Enter a stock ticker to continue.")
    else:
        with st.spinner("Running LangGraph analysis..."):
            try:
                result = run_analysis(
                    ticker=ticker,
                    company_name=company_name,
                    period=period,
                    interval=interval,
                    model=model,
                )
            except Exception as exc:
                st.exception(exc)
            else:
                metrics = result["metrics"]
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Latest close", metrics["latest_close"])
                col2.metric("Period change %", metrics["percent_change"])
                col3.metric("20-day high", metrics["20_day_high_close"])
                col4.metric("Volatility", metrics["annualized_volatility"])

                trend_col1, trend_col2 = st.columns(2)
                trend_col1.metric("Trend direction", metrics["trend_direction"])
                trend_col2.metric("Trend strength", metrics["trend_strength"])

                price_rows = []
                for date_key, row in metrics["recent_prices"].items():
                    if hasattr(date_key, "strftime"):
                        display_date = date_key.strftime("%Y-%m-%d")
                    else:
                        display_date = str(date_key)
                    price_rows.append({"Date": display_date, **row})

                st.subheader("Trend summary")
                st.write(
                    f"The recent price data indicates a **{metrics['trend_direction'].lower()}** with **{metrics['trend_strength'].lower()}** strength. "
                    f"The latest close is {metrics['latest_close']}, compared with the 20-day SMA of {metrics['20_day_sma']} and 50-day SMA of {metrics['50_day_sma']}."
                )

                st.subheader("Analysis")
                st.write(result["analysis"])

                st.subheader("Recent price data")
                st.dataframe(pd.DataFrame(price_rows), use_container_width=True)

                st.subheader("Google News research")
                if result.get("research"):
                    for item in result["research"]:
                        title = item.get("title") or "Untitled result"
                        href = item.get("href") or ""
                        body = item.get("body") or ""
                        source = item.get("source") or "Google News"
                        st.markdown(f"**[{title}]({href})**")
                        st.caption(f"Source: {source}")
                        if body and body.lower() not in title.lower():
                            st.write(body)
                else:
                    st.info("No web research results were returned.")
