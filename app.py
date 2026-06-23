from __future__ import annotations

import pandas as pd
import streamlit as st

from src.stock_analyzer.graph import run_analysis


st.set_page_config(page_title="Stock Analyzer", page_icon="SA", layout="wide")

st.title("LangGraph Stock Analyzer")
st.caption("Analyze a stock with Ollama gpt-oss:20b, market price history, and Google News research context.")

with st.sidebar:
    st.header("Inputs")
    ticker = st.text_input("Ticker", value="AAPL").strip().upper()
    company_name = st.text_input("Company name", value="Apple")
    period = st.selectbox("Price history period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
    interval = st.selectbox("Price interval", ["1d", "1h", "1wk"], index=0)
    model = st.text_input("Ollama model", value="gpt-oss:20b")
    run_clicked = st.button("Start analysis", type="primary", use_container_width=True)

st.markdown(
    "This tool combines recent price history, simple market statistics, and Google News headlines before sending the context to your local Ollama model."
)

st.info(
    "For Indian stocks, Yahoo Finance often requires exchange-specific symbols such as TCS.NS for NSE or some BSE symbols with .BO. The app will try common India suffixes automatically, but availability still depends on Yahoo Finance data."
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
