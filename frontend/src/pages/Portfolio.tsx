import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Layers, PiggyBank, ScanSearch } from 'lucide-react'
import { api, type Contract, type PortfolioReview } from '../api'
import { ErrorBox, Metric, PageHeader, PriorityDot, Spinner } from '../components/ui'
import { fmtDate, money, sourceLabel } from '../format'

const TYPE_LABEL: Record<string, string> = {
  redundancy: 'Redundancy',
  consolidation: 'Consolidation',
  scale_leverage: 'Scale leverage',
  underpriced_revenue: 'Under-priced revenue',
  risk: 'Risk',
}

export default function Portfolio() {
  const [review, setReview] = useState<PortfolioReview | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.portfolioLatest(), api.contracts()])
      .then(([r, cs]) => {
        setReview(r)
        setContracts(cs)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const run = async () => {
    setRunning(true)
    setError(null)
    try {
      setReview(await api.portfolioReview())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  const byId = new Map(contracts.map((c) => [c.id, c]))
  const RECENT_DAYS = 180 // keep in sync with RECENTLY_EXPIRED_DAYS in backend config
  const stillPaid = contracts.filter(
    (c) => c.status === 'expired' && (c.still_paying || c.auto_renew) && (c.days_to_end ?? -9999) >= -RECENT_DAYS,
  )
  const active = [...contracts.filter((c) => c.status !== 'expired'), ...stillPaid]
  const vendors = new Set(active.filter((c) => c.line_type === 'expense').map((c) => c.counterparty)).size
  const categories = new Set(active.filter((c) => c.line_type === 'expense').map((c) => c.category)).size

  return (
    <>
      <PageHeader
        title="Portfolio Review"
        subtitle="An AI agent reviews every contract together to find redundancies and consolidation savings that are invisible when contracts sit in silos."
        actions={
          <button className="btn btn-primary" onClick={run} disabled={running || active.length < 2}>
            {running ? <Spinner label="Analyzing portfolio…" /> : <><ScanSearch size={16} /> {review ? 'Run new review' : 'Run portfolio review'}</>}
          </button>
        }
      />
      <ErrorBox message={error} />
      {loading ? (
        <Spinner label="Loading…" />
      ) : (
        <>
          <div className="metrics metrics-4">
            <Metric label="Contracts reviewed" value={active.length} sub={stillPaid.length ? `incl. ${stillPaid.length} expired, still paid` : 'active contracts'} icon={<Layers size={18} />} />
            <Metric label="Expense vendors" value={vendors} sub={`${categories} spend categories`} />
            <Metric label="Opportunities found" value={review?.result.findings.length ?? '—'} />
            <Metric label="Estimated savings" value={review ? money(review.result.total_estimated_savings) : '—'} sub="per year" icon={<PiggyBank size={18} />} tone="accent" />
          </div>

          {stillPaid.length > 0 && (
            <div className="alert alert-info">
              Includes {stillPaid.length} recently expired contract{stillPaid.length > 1 ? 's' : ''} you're still paying for: {stillPaid.map((c) => c.counterparty).join(', ')}.
            </div>
          )}
          {!review ? (
            <div className="card muted">No review yet. {active.length < 2 ? 'Add at least two active contracts, then run' : 'Run'} a portfolio review to see recommendations.</div>
          ) : (
            <>
              <div className="card headline">
                <p>{review.result.headline}</p>
                <span className="muted small">{sourceLabel(review.source)} · {fmtDate(review.created_at)}</span>
              </div>
              <div className="findings">
                {review.result.findings.map((f, i) => (
                  <div key={i} className={`card finding finding-${f.priority}`}>
                    <div className="finding-head">
                      <span className={`badge type-${f.finding_type}`}>{TYPE_LABEL[f.finding_type]}</span>
                      <PriorityDot priority={f.priority} />
                      <span className="finding-savings">{money(f.estimated_annual_savings)}<small>/yr</small></span>
                    </div>
                    <h3>{f.title}</h3>
                    <p className="muted">{f.rationale}</p>
                    <div className="finding-action"><strong>Recommended:</strong> {f.recommended_action}</div>
                    <div className="finding-contracts">
                      {f.contract_ids.map((id) => {
                        const c = byId.get(id)
                        return c ? (
                          <Link key={id} to={`/contracts?id=${id}`} className="chip">
                            {c.name} · {money(c.annual_value, true)}
                          </Link>
                        ) : null
                      })}
                    </div>
                  </div>
                ))}
                {review.result.findings.length === 0 && <div className="card muted">No redundancies found — your portfolio looks lean.</div>}
              </div>
            </>
          )}
        </>
      )}
    </>
  )
}
