# LangGraph Stock Analyzer

A React + FastAPI stock analysis application that uses LangGraph with a local Ollama model (`gpt-oss:20b`) to analyze Indian-market stocks and enrich the result with Google News RSS context.

## What it does

- Searches NSE/BSE-listed companies from a local SQLite company catalog
- Downloads recent OHLCV data for a ticker with `yfinance`
- Pulls recent stock-related headlines through Google News RSS
- Computes summary metrics including trend direction and strength
- Sends the structured snapshot to an Ollama-hosted LLM through LangGraph
- Returns a structured stock analysis report through a React UI

## Architecture

The project is split into two parts:

1. React frontend
	Located in `frontend/`

	Responsibilities:

	- company search UI
	- dropdown result selection
	- analysis trigger and result display

2. Python backend
	Located in `src/stock_analyzer/` and exposed through FastAPI in `src/stock_analyzer/api.py`

	Responsibilities:

	- NSE/BSE company lookup from a local SQLite database
	- LangGraph analysis workflow
	- Yahoo Finance price history fetches
	- Google News RSS context fetches
	- Ollama model calls

	## Project structure

	Key files and folders:

	- `frontend/` — React app
	- `src/stock_analyzer/api.py` — FastAPI endpoints
	- `src/stock_analyzer/graph.py` — LangGraph workflow
	- `src/stock_analyzer/india_symbols.db` — local NSE/BSE company catalog
	- `scripts/build_india_symbol_db.py` — rebuilds the India company database
	- `api_main.py` — backend entrypoint for Uvicorn

## How LangGraph is used

This project uses LangGraph to define a small stateful workflow in `src/stock_analyzer/graph.py`.

The graph state stores:

- `ticker`, `company_name`, `period`, `interval`, `model`
- `price_data` from market history
- `metrics` derived from the downloaded prices
- `research` from Google News RSS results
- `analysis` returned by the Ollama model

The workflow is built with `StateGraph(GraphState)` and executed in this order:

1. `search_stock_info`
2. `fetch_price_data`
3. `summarize_prices`
4. `analyze_with_llm`

In practice that means LangGraph is acting as the orchestration layer:

- It passes a shared state object from one node to the next.
- Each node adds new fields to the state instead of handling the whole pipeline at once.
- The final LLM node receives both quantitative price metrics and recent web context.

The graph starts at `START`, moves through the four nodes above, and ends at `END`. The compiled graph is then executed through `compiled_graph.invoke(initial_state)`.

## APIs and libraries called

This project does not rely on a direct paid market-data vendor API. Instead it uses a mix of local catalog data and public library-backed sources.

### Stock price data

Stock price history is fetched in `fetch_price_data` with:

```python
yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
```

That call comes from the `yfinance` library and returns a pandas DataFrame with fields such as:

- `Open`
- `High`
- `Low`
- `Close`
- `Volume`

The app then computes:

- latest close
- period change in absolute and percentage terms
- average volume
- 20-day high and low based on close
- annualized volatility from daily returns

### Web research data

Recent stock-related context is fetched in `search_stock_info` from Google News RSS feeds:

```python
feed = feedparser.parse(_google_news_rss_url(query))
```

This requests Google News RSS results for queries like:

```text
Alphabet GOOGL stock
```

The workflow keeps the following fields from each result:

- `title`
- `href`
- `body`

### LLM analysis

The final analysis is generated locally through Ollama using LangChain's Ollama client:

```python
llm = ChatOllama(model=model_name, temperature=0.2)
response = llm.invoke([HumanMessage(content=prompt)])
```

So the LLM call path is:

- LangGraph orchestrates the node execution
- `ChatOllama` sends the final prompt to your local Ollama server
- Ollama runs `gpt-oss:20b`
- the returned text is stored in `analysis`

### Company lookup data

Company lookup is focused on Indian markets and uses a local SQLite database:

- `src/stock_analyzer/india_symbols.db`

The database is built from the NSE equity list plus curated BSE fallback entries using:

- `scripts/build_india_symbol_db.py`

## Prerequisites

- Python 3.10+
- Ollama installed and running locally
- The model pulled locally:

```bash
ollama pull gpt-oss:20b
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
```

## Run backend

```bash
.venv/bin/uvicorn api_main:app --host 0.0.0.0 --port 8000
```

## Run frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Then open:

```text
http://localhost:5173
```

The frontend expects the backend to be reachable at:

```text
http://localhost:8000
```

## Build India company database

If you need to rebuild the local NSE/BSE company lookup database:

```bash
.venv/bin/python scripts/build_india_symbol_db.py
```

## Notes

Before using analysis features, ensure Ollama is serving the requested model locally:

```bash
ollama pull gpt-oss:20b
ollama serve
```

This project is for research and educational use only. It does not provide financial advice.
