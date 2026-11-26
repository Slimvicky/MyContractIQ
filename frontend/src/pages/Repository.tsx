import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDownUp, FileText, Search } from 'lucide-react'
import { api, type Contract } from '../api'
import { ErrorBox, LineBadge, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { fmtDate, money } from '../format'

type SortKey = 'name' | 'counterparty' | 'line_type' | 'category' | 'annual_value' | 'end_date' | 'status'

export default function Repository() {
  const [list, setList] = useState<Contract[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'end_date', dir: 1 })

  useEffect(() => {
    api.contracts().then(setList).catch((e) => setError(e.message))
  }, [])

  const rows = useMemo(() => {
    const term = q.toLowerCase()
    return [...(list ?? [])]
      .filter((c) => !term || `${c.name} ${c.counterparty} ${c.category} ${c.file_name ?? ''}`.toLowerCase().includes(term))
      .sort((a, b) => {
        const av = a[sort.key] ?? ''
        const bv = b[sort.key] ?? ''
        return (av < bv ? -1 : av > bv ? 1 : 0) * sort.dir
      })
  }, [list, q, sort])

  const th = (key: SortKey, label: string, cls = '') => (
    <th className={`sortable ${cls}`} onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : 1 }))}>
      {label} {sort.key === key && <ArrowDownUp size={11} />}
    </th>
  )

  return (
    <>
      <PageHeader
        title="Repository"
        subtitle={list ? `${list.length} contracts · ${list.filter((c) => c.has_file).length} with PDFs` : undefined}
        actions={
          <div className="search search-inline">
            <Search size={15} />
            <input placeholder="Search repository…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        }
      />
      <ErrorBox message={error} />
      {!list ? (
        <Spinner label="Loading…" />
      ) : (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                {th('name', 'Contract')}
                {th('counterparty', 'Vendor / client')}
                {th('line_type', 'Line')}
                {th('category', 'Category')}
                {th('annual_value', 'Annual value', 'num')}
                {th('end_date', 'End date')}
                {th('status', 'Status')}
                <th>Document</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td><Link to={`/contracts?id=${c.id}`}>{c.name}</Link></td>
                  <td>{c.counterparty}</td>
                  <td><LineBadge type={c.line_type} /></td>
                  <td className="muted">{c.category}</td>
                  <td className={`num ${c.line_type}`}>{money(c.annual_value)}</td>
                  <td>{fmtDate(c.end_date)}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>
                    {c.has_file ? (
                      <button className="btn btn-ghost btn-sm" onClick={() => api.openPdf(c.id).catch((e) => setError(e.message))} title={c.file_name ?? ''}>
                        <FileText size={14} /> View PDF
                      </button>
                    ) : (
                      <span className="muted small">No PDF</span>
                    )}
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr><td colSpan={8} className="muted center">No contracts found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
