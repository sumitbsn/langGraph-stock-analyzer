from __future__ import annotations

import csv
import json
import time
from io import StringIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

NASDAQ_LISTED_URL = "https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "src" / "stock_analyzer" / "symbols.json"


def fetch_text(url: str, retries: int = 3) -> str:
    last_error: Exception | None = None
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except (TimeoutError, URLError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def parse_pipe_file(content: str, symbol_key: str, name_key: str, exchange_name: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    reader = csv.DictReader(StringIO(content), delimiter="|")
    for row in reader:
        symbol = (row.get(symbol_key) or "").strip().upper()
        company_name = (row.get(name_key) or "").strip()
        test_issue = (row.get("Test Issue") or row.get("Test Issue ") or "").strip().upper()
        if not symbol or not company_name or symbol.startswith("FILE CREATION TIME"):
            continue
        if test_issue == "Y":
            continue
        rows.append({"symbol": symbol, "company_name": company_name, "exchange": exchange_name})
    return rows


def parse_nse_csv(content: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    reader = csv.DictReader(StringIO(content))
    for row in reader:
        symbol = (row.get("SYMBOL") or "").strip().upper()
        company_name = (row.get("NAME OF COMPANY") or "").strip()
        if not symbol or not company_name:
            continue
        rows.append({"symbol": symbol, "company_name": company_name, "exchange": "NSE"})
        rows.append({"symbol": f"{symbol}.NS", "company_name": company_name, "exchange": "NSE"})
    return rows


def dedupe_symbols(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for row in rows:
        symbol = row["symbol"]
        if symbol in seen:
            continue
        seen.add(symbol)
        deduped.append(row)
    return sorted(deduped, key=lambda item: (item["company_name"], item["symbol"]))


def main() -> int:
    rows: list[dict[str, str]] = []
    sources = [
        (NASDAQ_LISTED_URL, lambda text: parse_pipe_file(text, "Symbol", "Security Name", "NASDAQ")),
        (OTHER_LISTED_URL, lambda text: parse_pipe_file(text, "ACT Symbol", "Security Name", "NYSE")),
        (NSE_EQUITY_URL, parse_nse_csv),
    ]

    for source_url, parser in sources:
        try:
            rows.extend(parser(fetch_text(source_url)))
            print(f"Loaded symbols from {source_url}")
        except Exception as exc:
            print(f"Skipping {source_url}: {exc}")

    output_rows = dedupe_symbols(rows)
    if not output_rows:
        raise RuntimeError("No symbol rows were loaded from any source.")
    OUTPUT_PATH.write_text(json.dumps(output_rows, indent=2) + "\n")
    print(f"Wrote {len(output_rows)} symbols to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
