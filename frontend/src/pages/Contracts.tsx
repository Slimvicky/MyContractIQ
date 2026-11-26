import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Bot, CalendarPlus, ExternalLink, FileText, Paperclip, Pencil, Search, Trash2 } from 'lucide-react'
import { api, type Contract } from '../api'
import ContractForm from '../components/ContractForm'
import { Empty, ErrorBox, LineBadge, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { daysLabel, fmtDate, money, REC_LABEL, sourceLabel } from '../format'

type Filter = 'all' | 'expense' | 'revenue' | 'action_due'

export default function Contracts() {
  const [params, setParams] = useSearchParams()
  const [list, setList] = useState<Contract[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const selectedId = Number(params.get('id')) || null

  const load = useCallback(() => {
    api.contracts().then(setList).catch((e) => setError(e.message))
  }, [])
  useEffect(load, [load])

  const shown = useMemo(() => {
    const term = q.toLowerCase()
    return (list ?? []).filter(
      (c) =>
        (filter === 'all' || c.line_type === filter || (filter === 'action_due' && (c.status === 'action_due' || c.status === 'expired'))) &&
        (!term || `${c.name} ${c.counterparty} ${c.category}`.toLowerCase().includes(term)),
    )
  }, [list, q, filter])

  useEffect(() => {
    if (!selectedId && shown.length) setParams({ id: String(shown[0].id) }, { replace: true })
  }, [selectedId, shown, setParams])

  const selected = list?.find((c) => c.id === selectedId) ?? null

  if (error) return <ErrorBox message={error} />
  if (!list) return <div className="center-page"><Spinner label="Loading contracts…" /></div>
  if (!list.length)
    return (
      <>
        <PageHeader title="Contracts" />
        <Empty icon={<FileText size={36} />} title="No contracts yet">
          <Link to="/upload" className="btn btn-primary">Upload contracts</Link>
        </Empty>
      </>
    )

  return (
    <>
      <PageHeader title="Contracts" subtitle="Details, renewal dates and rate checks for each contract" />
      <div className="master-detail">
        <aside className="card list-pane">
          <div className="search">
            <Search size={15} />
            <input placeholder="Search contracts…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="chips">
            {(['all', 'expense', 'revenue', 'action_due'] as Filter[]).map((f) => (
              <button key={f} className={`chip${filter === f ? ' active' : ''}`} onClick={() => setFilter(f)}>
                {f === 'all' ? 'All' : f === 'action_due' ? 'Action due' : f[0].toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
          <ul className="contract-list">
            {shown.map((c) => (
              <li key={c.id}>
                <button className={`contract-item${c.id === selectedId ? ' selected' : ''}`} onClick={() => setParams({ id: String(c.id) })}>
                  <div className="ci-top">
                    <span className="ci-name">{c.name}</span>
                    <span className={`ci-value ${c.line_type}`}>{c.line_type === 'revenue' ? '+' : '−'}{money(c.annual_value, true)}</span>
                  </div>
                  <div className="ci-bottom">
                    <span className="muted">{c.counterparty}</span>
                    <span className={`ci-days status-text-${c.status}`}>{c.end_date ? daysLabel(c.days_to_end) : '—'}</span>
                  </div>
                </button>
              </li>
            ))}
            {!shown.length && <li className="muted small pad">No matches.</li>}
          </ul>
        </aside>
        <section className="detail-pane">
          {selected ? <ContractDetail key={selected.id} c={selected} onChanged={load} onDeleted={() => { setParams({}); load() }} /> : <div className="card muted">Select a contract.</div>}
        </section>
      </div>
    </>
  )
}

function ContractDetail({ c, onChanged, onDeleted }: { c: Contract; onChanged: () => void; onDeleted: () => void }) {
  const [editing, setEditing] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const rc = c.rate_check

  const runCheck = async (force: boolean) => {
    setChecking(true)
    setError(null)
    try {
      await api.rateCheck(c.id, force)
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setChecking(false)
    }
  }

  const attach = async (file: File | undefined) => {
    if (!file) return
    try {
      await api.attachFile(c.id, file)
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (editing)
    return (
      <div className="card">
        <h2>Edit contract</h2>
        <ContractForm
          initial={c}
          submitLabel="Save changes"
          onCancel={() => setEditing(false)}
          onSubmit={async (data) => {
            await api.updateContract(c.id, data)
            setEditing(false)
            onChanged()
          }}
        />
      </div>
    )

  const windowOpens = c.end_date ? new Date(new Date(c.end_date + 'T00:00:00').getTime() - 60 * 86400000).toISOString().slice(0, 10) : null

  return (
    <>
      <div className="card">
        <div className="detail-head">
          <div>
            <div className="badges"><LineBadge type={c.line_type} /> <StatusBadge status={c.status} /> {c.needs_review && <span className="badge status-upcoming">Needs review</span>}</div>
            <h2>{c.name}</h2>
            <p className="muted">{c.line_type === 'revenue' ? 'Client' : 'Vendor'}: {c.counterparty} · {c.category}</p>
          </div>
          <div className="detail-actions">
            {c.has_file && <button className="btn btn-ghost btn-sm" onClick={() => api.openPdf(c.id).catch((e) => setError(e.message))}><ExternalLink size={14} /> Open PDF</button>}
            <label className="btn btn-ghost btn-sm"><Paperclip size={14} /> {c.has_file ? 'Replace PDF' : 'Attach PDF'}<input type="file" accept="application/pdf" hidden onChange={(e) => attach(e.target.files?.[0])} /></label>
            <button className="btn btn-ghost btn-sm" onClick={() => api.downloadCalendar(c.id)} disabled={!c.end_date}><CalendarPlus size={14} /> Add to calendar</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}><Pencil size={14} /> Edit</button>
            <button
              className="btn btn-danger btn-sm"
              onClick={async () => {
                if (confirm(`Delete "${c.name}"? This cannot be undone.`)) {
                  await api.deleteContract(c.id)
                  onDeleted()
                }
              }}
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        <div className="kv-grid">
          <div><span>Annual value</span><strong className={c.line_type}>{money(c.annual_value)}</strong></div>
          <div><span>Start date</span><strong>{fmtDate(c.start_date)}</strong></div>
          <div><span>End / renewal</span><strong>{fmtDate(c.end_date)}</strong><small>{daysLabel(c.days_to_end)}</small></div>
          <div><span>Notice deadline</span><strong>{fmtDate(c.notice_deadline)}</strong><small>{c.notice_days} days' notice</small></div>
          <div><span>Auto-renew</span><strong>{c.auto_renew ? 'Yes' : 'No'}</strong></div>
          <div><span>Owner</span><strong>{c.owner || '—'}</strong></div>
        </div>
        {c.scope && <div className="detail-block"><h4>Scope</h4><p>{c.scope}</p></div>}
        {c.notes && <div className="detail-block"><h4>Notes</h4><p>{c.notes}</p></div>}
        {c.has_file && <div className="muted small"><FileText size={13} /> {c.file_name}</div>}
      </div>

      <div className="card">
        <div className="card-head">
          <h2><Bot size={20} /> Rate comparison</h2>
          {c.rate_window_open ? <span className="pill pill-on">60-day window open</span> : <span className="pill pill-off">Window opens {fmtDate(windowOpens)}</span>}
        </div>
        <ErrorBox message={error} />
        {rc ? (
          <div className="rate-result">
            <div className="rate-top">
              <div>
                <span className={`rec-label big rec-${rc.result.recommendation}`}>{REC_LABEL[rc.result.recommendation]}</span>
                <div className="muted small">{sourceLabel(rc.source)} · {rc.result.confidence} confidence · checked {fmtDate(rc.created_at)}</div>
              </div>
              <div className="rate-impact">
                <span>{c.line_type === 'revenue' ? 'Potential uplift' : 'Potential savings'}</span>
                <strong>{money(rc.result.estimated_annual_impact)}<small>/yr</small></strong>
              </div>
            </div>
            <p>{rc.result.summary}</p>
            {(rc.result.market_low != null || rc.result.market_high != null) && (
              <p className="small">Market range: <strong>{money(rc.result.market_low)} – {money(rc.result.market_high)}</strong> per year · you {c.line_type === 'revenue' ? 'charge' : 'pay'} <strong>{money(c.annual_value)}</strong></p>
            )}
            {rc.result.alternatives.length > 0 && (
              <table className="table compact">
                <thead><tr><th>Alternative</th><th>Est. annual cost</th><th>Notes</th></tr></thead>
                <tbody>
                  {rc.result.alternatives.map((a, i) => (
                    <tr key={i}>
                      <td>{a.url ? <a href={a.url} target="_blank" rel="noreferrer noopener">{a.provider} <ExternalLink size={11} /></a> : a.provider}</td>
                      <td>{money(a.estimated_annual_cost)}</td>
                      <td className="muted">{a.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {rc.result.next_steps.length > 0 && (
              <ol className="steps">{rc.result.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
            )}
          </div>
        ) : (
          <p className="muted">
            {c.rate_window_open ? 'This contract is inside the 60-day renewal window. Run the rate agent to search for better rates.' : 'The rate agent starts automatically 60 days before renewal. You can also run it now.'}
          </p>
        )}
        <button className="btn btn-primary" onClick={() => runCheck(!!rc)} disabled={checking}>
          {checking ? <Spinner label="Searching the web for better rates…" /> : <><Bot size={16} /> {rc ? 'Re-run rate check' : 'Run rate check'}</>}
        </button>
      </div>
    </>
  )
}
