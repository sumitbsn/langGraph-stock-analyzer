from __future__ import annotations

import csv
import sqlite3
import time
from io import StringIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
DB_PATH = Path(__file__).resolve().parents[1] / "src" / "stock_analyzer" / "india_symbols.db"

BSE_FALLBACK_ROWS = [
    ("500325.BO", "Reliance Industries", "BSE"),
    ("500180.BO", "HDFC Bank", "BSE"),
    ("500209.BO", "Infosys Limited", "BSE"),
    ("532540.BO", "Tata Consultancy Services", "BSE"),
    ("500570.BO", "Tata Motors", "BSE"),
    ("500400.BO", "Tata Power", "BSE"),
    ("500470.BO", "Tata Steel", "BSE"),
    ("532540.BO", "Tata Consultancy Services", "BSE"),
    ("532174.BO", "ICICI Bank", "BSE"),
    ("500247.BO", "Kotak Mahindra Bank", "BSE"),
    ("500875.BO", "ITC Limited", "BSE"),
    ("532977.BO", "Bajaj Auto", "BSE"),
]


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


def parse_nse_csv(content: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    reader = csv.DictReader(StringIO(content))
    for row in reader:
        symbol = (row.get("SYMBOL") or "").strip().upper()
        company_name = (row.get("NAME OF COMPANY") or "").strip()
        if not symbol or not company_name:
            continue
        rows.append((symbol, company_name, "NSE"))
        rows.append((f"{symbol}.NS", company_name, "NSE"))
    return rows


def build_database(rows: list[tuple[str, str, str]]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DROP TABLE IF EXISTS companies")
        connection.execute(
            """
            CREATE TABLE companies (
                symbol TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                exchange TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT OR REPLACE INTO companies(symbol, company_name, exchange) VALUES (?, ?, ?)",
            rows,
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_company_name ON companies(company_name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON companies(symbol)")
        connection.commit()


def main() -> int:
    rows: list[tuple[str, str, str]] = []
    rows.extend(parse_nse_csv(fetch_text(NSE_EQUITY_URL)))
    rows.extend(BSE_FALLBACK_ROWS)

    deduped: dict[str, tuple[str, str, str]] = {symbol: (symbol, name, exchange) for symbol, name, exchange in rows}
    build_database(list(deduped.values()))
    print(f"Wrote {len(deduped)} India market symbols to {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())