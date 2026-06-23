import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'

const API_BASE = 'http://localhost:8000'

function AnalysisSections({ text }) {
  const sections = useMemo(() => {
    return text
      .split(/\n\s*\n/)
      .map((block) => block.trim())
      .filter(Boolean)
      .map((block) => {
        const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
        const firstLine = lines[0] || ''
        const headingMatch = firstLine.match(/^\*\*(.+?)\*\*$/)
        if (headingMatch) {
          return { heading: headingMatch[1], body: lines.slice(1) }
        }
        return { heading: '', body: lines }
      })
  }, [text])

  return (
    <div className="analysis-sections">
      {sections.map((section, index) => (
        <div key={`${section.heading}-${index}`} className="analysis-block">
          {section.heading ? <h4>{section.heading}</h4> : null}
          {section.body.map((line, lineIndex) => (
            line.startsWith('* ') ? (
              <li key={lineIndex}>{line.slice(2)}</li>
            ) : (
              <p key={lineIndex}>{line}</p>
            )
          ))}
        </div>
      ))}
    </div>
  )
}

function CompanySearch({ selected, onSelect }) {
  const [query, setQuery] = useState('')
  const [items, setItems] = useState([])
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [open, setOpen] = useState(true)
  const [loading, setLoading] = useState(false)
  const listRef = useRef(null)

  useEffect(() => {
    if (selected?.company_name) {
      setQuery(selected.company_name)
    }
  }, [selected?.company_name])

  useEffect(() => {
    setPage(0)
  }, [query])

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const params = new URLSearchParams({ query, page: String(page), page_size: '20' })
        const response = await fetch(`${API_BASE}/api/companies?${params.toString()}`, { signal: controller.signal })
        const data = await response.json()
        setItems((prev) => (page === 0 ? data.items : [...prev, ...data.items]))
        setHasMore(Boolean(data.has_more))
        setOpen(true)
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.error(error)
        }
      } finally {
        setLoading(false)
      }
    }, 180)

    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [query, page])

  const onScroll = () => {
    const element = listRef.current
    if (!element || loading || !hasMore) return
    if (element.scrollTop + element.clientHeight >= element.scrollHeight - 24) {
      setPage((current) => current + 1)
    }
  }

  const selectedLabel = useMemo(() => {
    if (!selected) return ''
    return `${selected.symbol} - ${selected.company_name} (${selected.exchange})`
  }, [selected])

  return (
    <div className="company-search">
      <label className="field-label">Company</label>
      <input
        className="company-input"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setOpen(true)
        }}
        placeholder="Type tata, infos, reliance, hdfc..."
      />
      {selectedLabel ? <div className="selected-pill">Selected: {selectedLabel}</div> : null}
      {open ? (
        <div className="dropdown" ref={listRef} onScroll={onScroll}>
          {items.map((item) => (
            <button
              key={item.symbol}
              type="button"
              className="dropdown-item"
              onClick={() => {
                onSelect(item)
                setQuery(item.company_name)
                setOpen(false)
              }}
            >
              {item.label}
            </button>
          ))}
          {loading ? <div className="dropdown-status">Loading...</div> : null}
          {!loading && !items.length ? <div className="dropdown-status">No companies found.</div> : null}
        </div>
      ) : null}
    </div>
  )
}

function App() {
  const [selectedCompany, setSelectedCompany] = useState(null)
  const [period, setPeriod] = useState('6mo')
  const [interval, setInterval] = useState('1d')
  const [model, setModel] = useState('gpt-oss:20b')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const runAnalysis = async () => {
    if (!selectedCompany) {
      setError('Select a company first.')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: selectedCompany.symbol,
          company_name: selectedCompany.company_name,
          period,
          interval,
          model,
        }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Analysis failed.')
      }
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <aside className="sidebar">
        <h2>Inputs</h2>
        <CompanySearch selected={selectedCompany} onSelect={setSelectedCompany} />
        <label className="field-label">Price history period</label>
        <select className="field" value={period} onChange={(event) => setPeriod(event.target.value)}>
          <option value="1mo">1mo</option>
          <option value="3mo">3mo</option>
          <option value="6mo">6mo</option>
          <option value="1y">1y</option>
          <option value="2y">2y</option>
        </select>
        <label className="field-label">Price interval</label>
        <select className="field" value={interval} onChange={(event) => setInterval(event.target.value)}>
          <option value="1d">1d</option>
          <option value="1h">1h</option>
          <option value="1wk">1wk</option>
        </select>
        <label className="field-label">Ollama model</label>
        <input className="field" value={model} onChange={(event) => setModel(event.target.value)} />
        <button className="primary-button" type="button" onClick={runAnalysis} disabled={loading}>
          {loading ? 'Running...' : 'Start analysis'}
        </button>
      </aside>
      <main className="content">
        <h1>LangGraph Stock Analyzer</h1>
        <p>Analyze NSE/BSE stocks with Ollama gpt-oss:20b, market price history, and Google News research context.</p>
        <div className="info-box">
          This app is focused on Indian markets. Company lookup is driven by a local NSE/BSE symbol database, and Yahoo Finance is used for price history with exchange-specific suffix handling such as .NS and .BO.
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        {result ? (
          <>
            <section className="metrics-grid">
              <div className="metric-card"><span>Latest close</span><strong>{result.metrics.latest_close}</strong></div>
              <div className="metric-card"><span>Period change %</span><strong>{result.metrics.percent_change}</strong></div>
              <div className="metric-card"><span>Trend</span><strong>{result.metrics.trend_direction}</strong></div>
              <div className="metric-card"><span>Strength</span><strong>{result.metrics.trend_strength}</strong></div>
              <div className="metric-card"><span>20-day high</span><strong>{result.metrics['20_day_high_close']}</strong></div>
              <div className="metric-card"><span>20-day low</span><strong>{result.metrics['20_day_low_close']}</strong></div>
              <div className="metric-card"><span>20-day SMA</span><strong>{result.metrics['20_day_sma']}</strong></div>
              <div className="metric-card"><span>50-day SMA</span><strong>{result.metrics['50_day_sma']}</strong></div>
            </section>
            <section className="panel">
              <h3>Trend summary</h3>
              <p>
                The recent price data indicates a <strong>{result.metrics.trend_direction.toLowerCase()}</strong> with
                <strong> {result.metrics.trend_strength.toLowerCase()}</strong> strength. The latest close is
                <strong> {result.metrics.latest_close}</strong>, compared with the 20-day SMA of
                <strong> {result.metrics['20_day_sma']}</strong> and 50-day SMA of
                <strong> {result.metrics['50_day_sma']}</strong>.
              </p>
            </section>
            <section className="panel">
              <h3>Analysis</h3>
              <AnalysisSections text={result.analysis} />
            </section>
            <section className="panel">
              <h3>Recent price data</h3>
              <div className="table-wrap">
                <table className="price-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Open</th>
                      <th>High</th>
                      <th>Low</th>
                      <th>Close</th>
                      <th>Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.metrics.recent_prices || {}).map(([date, row]) => (
                      <tr key={date}>
                        <td>{date}</td>
                        <td>{row.Open}</td>
                        <td>{row.High}</td>
                        <td>{row.Low}</td>
                        <td>{row.Close}</td>
                        <td>{row.Volume}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="panel">
              <h3>Google News research</h3>
              {result.research?.map((item) => (
                <div key={item.href} className="news-item">
                  <a href={item.href} target="_blank" rel="noreferrer">{item.title}</a>
                  <div className="news-source">{item.source}</div>
                  {item.body ? <p>{item.body}</p> : null}
                </div>
              ))}
            </section>
          </>
        ) : null}
      </main>
    </div>
  )
}

const root = createRoot(document.getElementById('root'))
root.render(<App />)

const style = document.createElement('style')
style.textContent = `
  :root {
    font-family: 'Segoe UI', sans-serif;
    color: #1f2937;
    background: linear-gradient(180deg, #f7f8fb 0%, #eef4ff 100%);
  }
  body { margin: 0; }
  .page { display: grid; grid-template-columns: 320px 1fr; min-height: 100vh; }
  .sidebar { background: rgba(255,255,255,0.86); padding: 24px; border-right: 1px solid #e5e7eb; backdrop-filter: blur(10px); }
  .content { padding: 32px; }
  .field-label { display: block; font-size: 0.9rem; margin: 14px 0 8px; color: #374151; }
  .field, .company-input { width: 100%; padding: 12px; border: 1px solid #d1d5db; border-radius: 10px; box-sizing: border-box; }
  .primary-button { margin-top: 18px; width: 100%; border: 0; background: #ef4444; color: white; padding: 12px; border-radius: 10px; cursor: pointer; }
  .company-search { position: relative; }
  .dropdown { margin-top: 8px; max-height: 260px; overflow-y: auto; border: 1px solid #d1d5db; border-radius: 12px; background: white; }
  .dropdown-item { width: 100%; text-align: left; border: 0; background: white; padding: 12px; cursor: pointer; border-bottom: 1px solid #f3f4f6; }
  .dropdown-item:hover { background: #f9fafb; }
  .dropdown-status { padding: 12px; color: #6b7280; }
  .selected-pill { margin-top: 8px; font-size: 0.85rem; color: #2563eb; }
  .info-box, .error-box { margin-top: 16px; padding: 16px; border-radius: 12px; }
  .info-box { background: #e8f1ff; color: #1d4ed8; }
  .error-box { background: #fee2e2; color: #b91c1c; }
  .metrics-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 24px; }
  .metric-card, .panel { background: white; border-radius: 16px; padding: 18px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06); }
  .metric-card span { display: block; color: #6b7280; font-size: 0.9rem; }
  .metric-card strong { font-size: 1.4rem; }
  .panel { margin-top: 18px; }
  .analysis-sections { display: grid; gap: 14px; }
  .analysis-block { padding: 14px; border-radius: 12px; background: #f8fafc; }
  .analysis-block h4 { margin: 0 0 8px; font-size: 1rem; }
  .analysis-block p { margin: 0 0 8px; line-height: 1.55; }
  .analysis-block li { margin-left: 18px; line-height: 1.5; }
  .table-wrap { overflow-x: auto; }
  .price-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  .price-table th, .price-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-size: 0.92rem; }
  .price-table th { color: #6b7280; font-weight: 600; background: #f8fafc; }
  .news-item { padding: 12px 0; border-bottom: 1px solid #f3f4f6; }
  .news-source { font-size: 0.85rem; color: #6b7280; margin-top: 4px; }
  @media (max-width: 960px) { .page { grid-template-columns: 1fr; } .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
`
document.head.appendChild(style)
