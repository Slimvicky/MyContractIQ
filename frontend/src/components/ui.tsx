import type { ReactNode } from 'react'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Loader2 } from 'lucide-react'
import type { LineType, Status } from '../api'
import { STATUS_LABEL } from '../format'

export function LineBadge({ type }: { type: LineType }) {
  return (
    <span className={`badge line-${type}`}>
      {type === 'revenue' ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      {type === 'revenue' ? 'Revenue' : 'Expense'}
    </span>
  )
}

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge status-${status}`}>{STATUS_LABEL[status]}</span>
}

export function PriorityDot({ priority }: { priority: 'high' | 'medium' | 'low' }) {
  return <span className={`priority priority-${priority}`}>{priority}</span>
}

export function Metric({
  label,
  value,
  sub,
  icon,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  icon?: ReactNode
  tone?: 'default' | 'accent' | 'warn' | 'good'
}) {
  return (
    <div className={`metric metric-${tone}`}>
      <div className="metric-top">
        <span className="metric-label">{label}</span>
        {icon && <span className="metric-icon">{icon}</span>}
      </div>
      <div className="metric-value">{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="spinner">
      <Loader2 size={16} className="spin" /> {label}
    </span>
  )
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="alert alert-error">
      <AlertTriangle size={16} /> {message}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      {children}
    </div>
  )
}
