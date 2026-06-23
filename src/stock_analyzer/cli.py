from __future__ import annotations

import argparse

from src.stock_analyzer.graph import run_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze stock prices with LangGraph and Ollama.")
    parser.add_argument("--ticker", required=True, help="Ticker symbol, for example AAPL")
    parser.add_argument("--company-name", default="", help="Optional company name for web research")
    parser.add_argument("--period", default="6mo", help="yfinance period, for example 1mo, 6mo, 1y")
    parser.add_argument("--interval", default="1d", help="yfinance interval, for example 1d, 1h")
    parser.add_argument("--model", default="gpt-oss:20b", help="Ollama model name")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = run_analysis(
        ticker=args.ticker,
        company_name=args.company_name,
        period=args.period,
        interval=args.interval,
        model=args.model,
    )

    print(f"Ticker: {result['ticker']}")
    print(f"Latest close: {result['metrics']['latest_close']}")
    if result.get("research"):
        print("Recent web context:")
        for item in result["research"][:3]:
            print(f"- {item['title']} :: {item['href']}")
    print()
    print(result["analysis"])
    return 0
