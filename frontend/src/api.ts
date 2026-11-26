// Typed API client for the MyContractIQ FastAPI backend.

export type LineType = 'expense' | 'revenue'
export type Status = 'active' | 'upcoming' | 'action_due' | 'expired'

export interface User {
  id: number
  first_name: string
  last_name: string
  email: string
  business_name: string
  business_type: string
}

export interface Alternative {
  provider: string
  estimated_annual_cost: number | null
  notes: string
  url: string | null
}

export interface RateResult {
  summary: string
  recommendation: 'switch' | 'renegotiate' | 'renew' | 'raise_price' | 'hold'
  confidence: 'low' | 'medium' | 'high'
  market_low: number | null
  market_high: number | null
  estimated_annual_impact: number
  alternatives: Alternative[]
  next_steps: string[]
}

export interface RateCheck {
  result: RateResult
  source: string
  trigger: string
  created_at: string
  cached?: boolean
}

export interface ContractInput {
  name: string
  counterparty: string
  line_type: LineType
  category: string
  annual_value: number
  start_date: string | null
  end_date: string | null
  notice_days: number
  auto_renew: boolean
  owner: string
  scope: string
  notes: string
}

export interface Contract extends ContractInput {
  id: number
  file_name: string | null
  has_file: boolean
  needs_review: boolean
  created_at: string
  updated_at: string
  days_to_end: number | null
  notice_deadline: string | null
  days_to_notice: number | null
  rate_window_open: boolean
  status: Status
  rate_check: RateCheck | null
}

export interface Action {
  contract_id: number
  contract_name: string
  counterparty: string
  line_type: LineType
  annual_value: number
  type: 'expired' | 'notice_deadline' | 'notice_passed' | 'rate_check' | 'recommendation' | 'review'
  priority: 'high' | 'medium' | 'low'
  due_date: string | null
  title: string
  detail: string
}

export interface Recommendation extends RateResult {
  contract_id: number
  contract_name: string
  counterparty: string
  line_type: LineType
  annual_value: number
  days_to_end: number | null
  source: string
  checked_at: string
}

export interface Overview {
  metrics: {
    total_contracts: number
    active_contracts: number
    expense_contracts: number
    revenue_contracts: number
    annual_expense: number
    annual_revenue: number
    expiring_30: number
    expiring_60: number
    expiring_90: number
    expired: number
    auto_renewing: number
    potential_savings: number
    potential_uplift: number
  }
  actions: Action[]
  recommendations: Recommendation[]
  rate_check_eligible: { id: number; name: string; days_to_end: number; has_check: boolean }[]
  spend_by_category: [string, number][]
  ai_enabled: boolean
}

export interface Finding {
  title: string
  finding_type: 'redundancy' | 'consolidation' | 'scale_leverage' | 'underpriced_revenue' | 'risk'
  contract_ids: number[]
  estimated_annual_savings: number
  rationale: string
  recommended_action: string
  priority: 'high' | 'medium' | 'low'
}

export interface PortfolioReview {
  result: { headline: string; total_estimated_savings: number; findings: Finding[] }
  source: string
  created_at: string
}

export interface Meta {
  business_types: Record<string, string[]>
  categories: string[]
  rate_check_window_days: number
}

const TOKEN_KEY = 'mycontractiq_token'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY)

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      return d
        .map((e: { loc?: string[]; msg?: string }) => `${(e.loc ?? []).slice(-1)[0] ?? ''}: ${e.msg ?? ''}`.replace(/^: /, ''))
        .join('; ')
    }
  }
  return fallback
}

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let res: Response
  try {
    res = await fetch(`/api${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the MyContractIQ server. Is the backend running?')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    if (res.status === 401 && token) {
      setToken(null)
      window.dispatchEvent(new Event('auth:expired'))
    }
    throw new ApiError(res.status, errorMessage(body, `Request failed (${res.status})`))
  }
  return res
}

async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await raw(path, init)).json() as Promise<T>
}

export const api = {
  health: () => json<{ ok: boolean; ai_enabled: boolean; model: string }>('/health'),
  meta: () => json<Meta>('/meta'),
  register: (body: Record<string, string>) =>
    json<{ token: string; user: User; welcome_email: string }>('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (email: string, password: string) =>
    json<{ token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => json('/auth/logout', { method: 'POST' }),
  me: () => json<User>('/auth/me'),

  contracts: () => json<Contract[]>('/contracts'),
  contract: (id: number) => json<Contract>(`/contracts/${id}`),
  createContract: (c: ContractInput) => json<Contract>('/contracts', { method: 'POST', body: JSON.stringify(c) }),
  updateContract: (id: number, c: ContractInput) =>
    json<Contract>(`/contracts/${id}`, { method: 'PUT', body: JSON.stringify(c) }),
  deleteContract: (id: number) => json(`/contracts/${id}`, { method: 'DELETE' }),
  attachFile: (id: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return json(`/contracts/${id}/file`, { method: 'POST', body: fd })
  },
  extract: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return json<{ fields: Partial<ContractInput>; source: string }>('/extract', { method: 'POST', body: fd })
  },
  bulkUpload: (files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    return json<{
      created: { id: number; name: string; source: string; needs_review: boolean }[]
      errors: { file: string; error: string }[]
    }>('/contracts/bulk', { method: 'POST', body: fd })
  },
  loadSample: () => json<{ created: number }>('/contracts/sample', { method: 'POST' }),

  rateCheck: (id: number, force = false) => json<RateCheck>(`/contracts/${id}/rate-check?force=${force}`, { method: 'POST' }),
  runDueRateChecks: () =>
    json<{ checked: number[]; failed: { id: number; name: string; error: string }[] }>('/rate-checks/run-due', { method: 'POST' }),
  overview: () => json<Overview>('/overview'),
  portfolioReview: () => json<PortfolioReview>('/portfolio/review', { method: 'POST' }),
  portfolioLatest: () => json<PortfolioReview | null>('/portfolio/latest'),

  // Downloads need the auth header, so they are fetched as blobs.
  downloadCalendar: async (contractId?: number) => {
    const res = await raw(contractId ? `/contracts/${contractId}/calendar.ics` : '/calendar.ics')
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url
    a.download = contractId ? `contract_${contractId}.ics` : 'mycontractiq_dates.ics'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  },
  downloadTemplate: async () => {
    const res = await raw('/templates/contracts.csv')
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url
    a.download = 'mycontractiq_template.csv'
    a.click()
  },
  openPdf: async (contractId: number) => {
    const win = window.open('', '_blank') // open synchronously so popup blockers allow it
    try {
      const res = await raw(`/contracts/${contractId}/file`)
      const url = URL.createObjectURL(new Blob([await res.blob()], { type: 'application/pdf' }))
      if (win) win.location.href = url
      else window.location.href = url
    } catch (e) {
      win?.close()
      throw e
    }
  },
}
