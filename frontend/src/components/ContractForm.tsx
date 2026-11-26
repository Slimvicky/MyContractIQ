import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api, type ContractInput } from '../api'
import { ErrorBox, Spinner } from './ui'

export const BLANK: ContractInput = {
  name: '',
  counterparty: '',
  line_type: 'expense',
  category: 'Other',
  annual_value: 0,
  start_date: null,
  end_date: null,
  notice_days: 30,
  auto_renew: false,
  owner: '',
  scope: '',
  notes: '',
}

export default function ContractForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
  extra,
}: {
  initial: ContractInput
  submitLabel: string
  onSubmit: (c: ContractInput) => Promise<void>
  onCancel?: () => void
  extra?: ReactNode
}) {
  const [c, setC] = useState<ContractInput>(initial)
  const [categories, setCategories] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => setC(initial), [initial])
  useEffect(() => {
    api.meta().then((m) => setCategories(m.categories)).catch(() => undefined)
  }, [])

  const set = <K extends keyof ContractInput>(k: K, v: ContractInput[K]) => setC((prev) => ({ ...prev, [k]: v }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSubmit(c)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <div className="segmented" role="radiogroup" aria-label="Contract line">
        <button type="button" className={c.line_type === 'expense' ? 'active expense' : ''} onClick={() => set('line_type', 'expense')}>
          Expense line <small>We pay a vendor</small>
        </button>
        <button type="button" className={c.line_type === 'revenue' ? 'active revenue' : ''} onClick={() => set('line_type', 'revenue')}>
          Revenue line <small>A client pays us (e.g. client service agreement)</small>
        </button>
      </div>
      <div className="grid-2">
        <label>Contract name<input required value={c.name} onChange={(e) => set('name', e.target.value)} placeholder="e.g. Business internet" /></label>
        <label>{c.line_type === 'revenue' ? 'Client' : 'Vendor'}<input required value={c.counterparty} onChange={(e) => set('counterparty', e.target.value)} /></label>
      </div>
      <div className="grid-3">
        <label>
          Category
          <select value={c.category} onChange={(e) => set('category', e.target.value)}>
            {[...new Set([...categories, c.category])].map((x) => <option key={x}>{x}</option>)}
          </select>
        </label>
        <label>Annual value (USD)<input type="number" min={0} step="any" required value={c.annual_value} onChange={(e) => set('annual_value', Number(e.target.value))} /></label>
        <label>Owner<input value={c.owner} onChange={(e) => set('owner', e.target.value)} placeholder="Who manages it" /></label>
      </div>
      <div className="grid-3">
        <label>Start date<input type="date" value={c.start_date ?? ''} onChange={(e) => set('start_date', e.target.value || null)} /></label>
        <label>End / renewal date<input type="date" value={c.end_date ?? ''} onChange={(e) => set('end_date', e.target.value || null)} /></label>
        <label>Notice period (days)<input type="number" min={0} max={365} value={c.notice_days} onChange={(e) => set('notice_days', Number(e.target.value))} /></label>
      </div>
      <label className="checkbox"><input type="checkbox" checked={c.auto_renew} onChange={(e) => set('auto_renew', e.target.checked)} /> Renews automatically unless cancelled</label>
      <label>Scope<textarea rows={2} value={c.scope} onChange={(e) => set('scope', e.target.value)} placeholder="What does this contract cover? (helps the agents find overlaps and better rates)" /></label>
      <label>Notes<textarea rows={2} value={c.notes} onChange={(e) => set('notes', e.target.value)} /></label>
      {extra}
      <ErrorBox message={error} />
      <div className="form-actions">
        {onCancel && <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancel</button>}
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : submitLabel}</button>
      </div>
    </form>
  )
}
