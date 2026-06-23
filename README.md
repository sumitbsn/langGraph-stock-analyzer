# LangGraph Stock Analyzer

A minimal Python app that uses LangGraph with an Ollama model (`gpt-oss:20b`) to analyze recent stock price action and enrich the result with Google News RSS context.

## What it does

- Downloads recent OHLCV data for a ticker with `yfinance`
- Pulls recent stock-related headlines through Google News RSS
- Computes a few basic summary metrics
- Sends the structured snapshot to an Ollama-hosted LLM through LangGraph
- Returns a concise stock analysis report

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

This project does not call a direct exchange API such as Alpha Vantage or Polygon. Instead it currently uses Python libraries that fetch and normalize data for you.

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
```

## Run

```bash
python main.py --ticker AAPL --period 6mo --interval 1d
```

To include a company name in the research query:

```bash
python main.py --ticker GOOGL --company-name Alphabet
```

## UI

Run the Streamlit interface:

```bash
.venv/bin/streamlit run app.py
```

The UI lets you enter the stock ticker, optional company name, history window, and model, then starts the full LangGraph analysis flow.

UI inputs map directly into the graph state:

- ticker symbol
- optional company name for better Google News queries
- price history period
- price interval
- Ollama model name

Before running the UI, ensure Ollama is serving the requested model locally:

```bash
ollama pull gpt-oss:20b
ollama serve
```

You can also override the model:

```bash
python main.py --ticker NVDA --model gpt-oss:20b
```

## Notes

This project is for research and educational use only. It does not provide financial advice.
