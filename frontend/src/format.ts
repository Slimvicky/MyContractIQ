export const money = (n: number | null | undefined, compact = false) =>
  n == null
    ? '—'
    : new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
        notation: compact && Math.abs(n) >= 100000 ? 'compact' : 'standard',
      }).format(n)

export const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d.length === 10 ? d + 'T00:00:00' : d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

export const daysLabel = (n: number | null | undefined) => {
  if (n == null) return 'No end date'
  if (n < 0) return `${Math.abs(n)} days ago`
  if (n === 0) return 'Today'
  if (n === 1) return 'Tomorrow'
  return `in ${n} days`
}

export const STATUS_LABEL: Record<string, string> = {
  active: 'Active',
  upcoming: 'Renewing soon',
  action_due: 'Action due',
  expired: 'Expired',
}

export const REC_LABEL: Record<string, string> = {
  switch: 'Switch provider',
  renegotiate: 'Renegotiate',
  renew: 'Renew as is',
  raise_price: 'Raise price',
  hold: 'Hold',
}

export const sourceLabel = (s: string) =>
  s === 'heuristic' ? 'Rule-based estimate' : s.includes('web_search') ? 'AI + live web search' : 'AI analysis'
