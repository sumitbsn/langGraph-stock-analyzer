from __future__ import annotations

from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.stock_analyzer.graph import run_analysis


DB_PATH = Path(__file__).resolve().parent / "india_symbols.db"


class AnalyzeRequest(BaseModel):
    ticker: str
    company_name: str = ""
    period: str = "6mo"
    interval: str = "1d"
    model: str = "gpt-oss:20b"


app = FastAPI(title="LangGraph Stock Analyzer API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def query_companies(query: str, page: int = 0, page_size: int = 20) -> list[dict[str, str]]:
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


@app.get("/api/companies")
def get_companies(
    query: str = Query(default=""),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    items = query_companies(query=query, page=page, page_size=page_size)
    return {"items": items, "has_more": len(items) == page_size}


@app.post("/api/analyze")
def analyze_stock(request: AnalyzeRequest) -> dict[str, object]:
    try:
        result = run_analysis(
            ticker=request.ticker,
            company_name=request.company_name,
            period=request.period,
            interval=request.interval,
            model=request.model,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response: dict[str, object] = {
        "ticker": result.get("ticker", request.ticker),
        "company_name": result.get("company_name", request.company_name),
        "metrics": result.get("metrics", {}),
        "analysis": result.get("analysis", ""),
        "research": result.get("research", []),
    }
    return response