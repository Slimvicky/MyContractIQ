import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlarmClock, ArrowRight, Bot, CalendarPlus, CheckCircle2, FileStack, PiggyBank, RefreshCw, Sparkles, TrendingDown, TrendingUp,
} from 'lucide-react'
import { api, type Overview } from '../api'
import { useAuth } from '../auth'
import { Empty, ErrorBox, LineBadge, Metric, PageHeader, PriorityDot, Spinner } from '../components/ui'
import { daysLabel, fmtDate, money, REC_LABEL, sourceLabel } from '../format'

export default function OverviewPage() {
  const { user } = useAuth()
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [runMsg, setRunMsg] = useState<string | null>(null)

  const load = useCallback(() => {
    api.overview().then(setData).catch((e) => setError(e.message))
  }, [])
  useEffect(load, [load])

  const runAgent = async () => {
    setRunning(true)
    setRunMsg(null)
    try {
      const r = await api.runDueRateChecks()
      setRunMsg(
        r.checked.length || r.failed.length
          ? `Rate agent checked ${r.checked.length} contract(s)` + (r.failed.length ? `; ${r.failed.length} failed: ${r.failed[0].error}` : '.')
          : 'All contracts in the 60-day window already have a fresh rate check.',
      )
      load()
    } catch (e) {
      setRunMsg((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  if (error) return <ErrorBox message={error} />
  if (!data) return <div className="center-page"><Spinner label="Loading overview…" /></div>

  const m = data.metrics
  const high = data.actions.filter((a) => a.priority === 'high').length
  const pendingAgent = data.rate_check_eligible.filter((e) => !e.has_check).length

  if (m.total_contracts === 0)
    return (
      <>
        <PageHeader title={`Welcome, ${user?.first_name}`} subtitle={user?.business_name} />
        <Empty icon={<FileStack size={36} />} title="No contracts yet">
          <p className="muted">Upload your first contracts to see renewals, actions and savings here.</p>
          <Link to="/upload" className="btn btn-primary">Upload contracts</Link>
        </Empty>
      </>
    )

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle={`${user?.business_name} · ${new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}`}
        actions={
          <button className="btn btn-ghost" onClick={() => api.downloadCalendar()}>
            <CalendarPlus size={16} /> Export dates to calendar
          </button>
        }
      />

      <div className="metrics">
        <Metric label="Total contracts" value={m.total_contracts} sub={`${m.active_contracts} active · ${m.expired} expired`} icon={<FileStack size={18} />} />
        <Metric label="Actions due" value={data.actions.length} sub={`${high} high priority`} icon={<AlarmClock size={18} />} tone={high ? 'warn' : 'default'} />
        <Metric label="Renewing ≤ 60 days" value={m.expiring_60} sub={`${m.expiring_30} within 30 days`} icon={<RefreshCw size={18} />} />
        <Metric label="Annual expense" value={money(m.annual_expense, true)} sub={`${m.expense_contracts} expense contracts`} icon={<TrendingDown size={18} />} />
        <Metric label="Annual revenue" value={money(m.annual_revenue, true)} sub={`${m.revenue_contracts} revenue contracts`} icon={<TrendingUp size={18} />} tone="good" />
        <Metric label="Identified savings" value={money(m.potential_savings, true)} sub={`+ ${money(m.potential_uplift, true)} revenue uplift`} icon={<PiggyBank size={18} />} tone="accent" />
      </div>

      <div className="overview-grid">
        <section className="card actions-card">
          <div className="card-head">
            <h2><AlarmClock size={20} /> Actions due <span className="count">{data.actions.length}</span></h2>
            <Link to="/contracts" className="link">All contracts <ArrowRight size={14} /></Link>
          </div>
          {data.actions.length === 0 ? (
            <div className="all-clear"><CheckCircle2 size={22} /> You're all caught up — no actions due.</div>
          ) : (
            <ul className="action-list">
              {data.actions.map((a, i) => (
                <li key={i} className={`action action-${a.priority}`}>
                  <PriorityDot priority={a.priority} />
                  <div className="action-body">
                    <div className="action-title">{a.title}</div>
                    <div className="action-contract">
                      <Link to={`/contracts?id=${a.contract_id}`}>{a.contract_name}</Link> · {a.counterparty} <LineBadge type={a.line_type} />
                    </div>
                    <div className="muted small">{a.detail}</div>
                  </div>
                  <div className="action-due">
                    {a.due_date ? <><strong>{fmtDate(a.due_date)}</strong><small>{daysLabel(Math.round((new Date(a.due_date + 'T00:00:00').getTime() - new Date().setHours(0, 0, 0, 0)) / 86400000))}</small></> : <small>—</small>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="side-col">
          <section className="card agent-card">
            <div className="card-head">
              <h2><Bot size={20} /> Rate agent</h2>
              <span className={`pill ${data.ai_enabled ? 'pill-on' : 'pill-off'}`}>{data.ai_enabled ? 'AI web search on' : 'Offline mode'}</span>
            </div>
            <p className="muted small">
              Starts automatically 60 days before each renewal and searches the web for better rates. {data.rate_check_eligible.length} contract(s) are in the window
              {pendingAgent ? `, ${pendingAgent} not yet checked` : ''}.
            </p>
            <button className="btn btn-primary btn-block" onClick={runAgent} disabled={running || data.rate_check_eligible.length === 0}>
              {running ? <Spinner label="Searching for better rates…" /> : <><Sparkles size={16} /> Run rate agent on due contracts</>}
            </button>
            {runMsg && <div className="alert alert-info small">{runMsg}</div>}
            {!data.ai_enabled && <div className="muted small">Add OPENAI_API_KEY to the .env file to enable live web search.</div>}
          </section>

          <section className="card">
            <h3 className="card-title">Annual spend by category</h3>
            <div className="bars">
              {data.spend_by_category.slice(0, 6).map(([cat, v]) => (
                <div key={cat} className="bar-row">
                  <span className="bar-label">{cat}</span>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${(v / (data.spend_by_category[0]?.[1] || 1)) * 100}%` }} /></div>
                  <span className="bar-value">{money(v, true)}</span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>

      <section className="card">
        <div className="card-head">
          <h2><Sparkles size={20} /> Recommendations from rate comparison</h2>
          <span className="muted small">Sorted by estimated annual impact</span>
        </div>
        {data.recommendations.length === 0 ? (
          <p className="muted">No rate comparisons yet. Run the rate agent above, or from any contract's detail page.</p>
        ) : (
          <div className="rec-grid">
            {data.recommendations.map((r) => (
              <div key={r.contract_id} className={`rec rec-${r.recommendation}`}>
                <div className="rec-head">
                  <span className="rec-label">{REC_LABEL[r.recommendation]}</span>
                  <span className="rec-impact">{r.line_type === 'revenue' ? '+' : ''}{money(r.estimated_annual_impact)}<small>/yr</small></span>
                </div>
                <Link to={`/contracts?id=${r.contract_id}`} className="rec-name">{r.contract_name}</Link>
                <div className="muted small">{r.counterparty} · {money(r.annual_value)}/yr · renews {daysLabel(r.days_to_end)}</div>
                {r.runs && r.runs > 1 && (
                  <div className="small muted">Median of {r.runs} runs · range {money(r.impact_low)} – {money(r.impact_high)}</div>
                )}
                <p className="small">{r.summary}</p>
                {r.alternatives.length > 0 && (
                  <div className="small muted">Alternatives: {r.alternatives.slice(0, 3).map((a) => a.provider).join(', ')}</div>
                )}
                <div className="rec-foot small muted">{sourceLabel(r.source)} · {r.confidence} confidence · {fmtDate(r.checked_at)}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
