import { useState, type ReactNode } from 'react'
import { CalendarCheck2, CalendarPlus, Check, Copy, X } from 'lucide-react'
import { api, type NewContractRef } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Spinner } from './ui'

function Modal({ children, onClose, label }: { children: ReactNode; onClose?: () => void; label: string }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={label}>
      <div className="modal card">
        {onClose && (
          <button className="btn btn-icon modal-close" onClick={onClose} title="Close">
            <X size={18} />
          </button>
        )}
        {children}
      </div>
    </div>
  )
}

/** Asked once, right after sign-up (and on next login for anyone who has not answered yet). */
export function SignupCalendarPrompt() {
  const { user, updateUser } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedUrl, setFeedUrl] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  if (!user || (user.calendar_pref !== 'unset' && !feedUrl)) return null

  const answer = async (choice: 'all' | 'none') => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.setCalendarPreference(choice)
      if (choice === 'all' && r.feed_url) setFeedUrl(r.feed_url)
      else updateUser({ calendar_pref: r.calendar_pref })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const finish = () => {
    setFeedUrl(null)
    updateUser({ calendar_pref: 'all' })
  }

  if (feedUrl) {
    const webcal = feedUrl.replace(/^https?:/, 'webcal:')
    return (
      <Modal label="Calendar subscription" onClose={finish}>
        <div className="modal-icon good"><CalendarCheck2 size={26} /></div>
        <h2>Your contract calendar is ready</h2>
        <p className="muted">
          Subscribe once and every contract you add, now and later, appears in your calendar with its end date, notice deadline
          and rate-check window. It refreshes automatically.
        </p>
        <a className="btn btn-primary btn-block" href={webcal}>
          <CalendarPlus size={16} /> Subscribe in my calendar app
        </a>
        <button
          className="btn btn-ghost btn-block"
          onClick={async () => {
            await navigator.clipboard.writeText(feedUrl).catch(() => undefined)
            setCopied(true)
          }}
        >
          {copied ? <><Check size={16} /> Link copied</> : <><Copy size={16} /> Copy subscription link</>}
        </button>
        <p className="muted small">
          Works with Apple Calendar and Outlook. For Google Calendar: <em>Other calendars → From URL</em>, then paste the link (this needs the
          app to be hosted online, not on localhost). Keep this link private: anyone who has it can see your contract dates.
        </p>
        <button className="btn btn-ghost btn-block" onClick={finish}>Done</button>
      </Modal>
    )
  }

  return (
    <Modal label="Add contracts to calendar">
      <div className="modal-icon"><CalendarPlus size={26} /></div>
      <h2>Add all your contracts to your calendar?</h2>
      <p className="muted">
        Welcome, {user.first_name}! MyContractIQ can put the key dates for <strong>all of your contracts</strong> (end dates, notice deadlines
        and the 60-day rate-check window) into your calendar, with reminders, and keep it up to date as you add contracts.
      </p>
      <ErrorBox message={error} />
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={() => answer('none')} disabled={busy}>Not now</button>
        <button className="btn btn-primary" onClick={() => answer('all')} disabled={busy}>
          {busy ? <Spinner /> : <><CalendarPlus size={16} /> Yes, add all my contracts</>}
        </button>
      </div>
      <p className="muted small center">You can always export dates later with “Export calendar” in the top bar.</p>
    </Modal>
  )
}

/** Asked after contracts are added. Only shown when at least one new contract has not expired. */
export function AddToCalendarPrompt({ contracts, onDone }: { contracts: NewContractRef[]; onDone: () => void }) {
  const { user } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const upcoming = contracts.filter((c) => c.upcoming)
  const skipped = contracts.length - upcoming.length
  if (!upcoming.length) return null

  const add = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.downloadCalendarFor(upcoming.map((c) => c.id))
      onDone()
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }

  const fmt = (d: string | null) =>
    d ? new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''

  return (
    <Modal label="Add to calendar" onClose={onDone}>
      <div className="modal-icon"><CalendarPlus size={26} /></div>
      <h2>
        {upcoming.length === 1 ? <>Add “{upcoming[0].name}” to your calendar?</> : <>Add {upcoming.length} new contracts to your calendar?</>}
      </h2>
      <p className="muted">
        We'll create calendar events with reminders for the end date, notice deadline and rate-check window
        {upcoming.length === 1 && upcoming[0].end_date ? ` (contract ends ${fmt(upcoming[0].end_date)})` : ''}.
      </p>
      {upcoming.length > 1 && (
        <ul className="modal-list">
          {upcoming.slice(0, 8).map((c) => (
            <li key={c.id}><span>{c.name}</span><span className="muted small">ends {fmt(c.end_date)}</span></li>
          ))}
          {upcoming.length > 8 && <li className="muted small">…and {upcoming.length - 8} more</li>}
        </ul>
      )}
      {skipped > 0 && <p className="muted small">{skipped} contract(s) skipped because they have expired or have no end date.</p>}
      {user?.calendar_pref === 'all' && (
        <p className="muted small">Your subscribed MyContractIQ calendar will also pick these up automatically.</p>
      )}
      <ErrorBox message={error} />
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={onDone} disabled={busy}>Not now</button>
        <button className="btn btn-primary" onClick={add} disabled={busy}>
          {busy ? <Spinner /> : <><CalendarPlus size={16} /> Add to calendar</>}
        </button>
      </div>
    </Modal>
  )
}
