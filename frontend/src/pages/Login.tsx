import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { BellRing, FileCheck2, Search, ShieldCheck } from 'lucide-react'
import { api, type Meta } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Spinner } from '../components/ui'

const EMPTY = {
  first_name: '',
  last_name: '',
  business_name: '',
  business_type: '',
  email: '',
  password: '',
  confirm_password: '',
}

export default function Login() {
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [form, setForm] = useState(EMPTY)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.meta().then(setMeta).catch(() => undefined)
  }, [])
  useEffect(() => {
    if (user) navigate(from, { replace: true })
  }, [user, from, navigate])

  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })
  const mismatch = mode === 'register' && form.confirm_password !== '' && form.password !== form.confirm_password

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (mode === 'register' && form.password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      const res = mode === 'login' ? await api.login(form.email, form.password) : await api.register(form)
      signIn(res.token, res.user)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-hero">
        <h1>
          Every contract.
          <br />
          <span className="accent-text">Every renewal.</span> Under control.
        </h1>
        <p>MyContractIQ helps small businesses track contracts, never miss a renewal, and find better rates automatically.</p>
        <ul className="auth-features">
          <li><BellRing size={18} /> Renewal and notice-deadline reminders, exported to your calendar</li>
          <li><Search size={18} /> AI agent searches the web for better rates 60 days before renewal</li>
          <li><FileCheck2 size={18} /> Portfolio review that spots overlapping and redundant contracts</li>
          <li><ShieldCheck size={18} /> Passwords salted and hashed; every action audit-logged</li>
        </ul>
      </section>

      <section className="card auth-card">
        <div className="tabs">
          <button className={`tab${mode === 'login' ? ' active' : ''}`} onClick={() => { setMode('login'); setError(null) }}>
            Log in
          </button>
          <button className={`tab${mode === 'register' ? ' active' : ''}`} onClick={() => { setMode('register'); setError(null) }}>
            Create account
          </button>
        </div>

        <form onSubmit={submit} className="form">
          {mode === 'register' && (
            <>
              <div className="grid-2">
                <label>First name<input required value={form.first_name} onChange={set('first_name')} autoComplete="given-name" /></label>
                <label>Last name<input required value={form.last_name} onChange={set('last_name')} autoComplete="family-name" /></label>
              </div>
              <label>Small business name<input required value={form.business_name} onChange={set('business_name')} autoComplete="organization" /></label>
              <label>
                Type of small business
                <select required value={form.business_type} onChange={set('business_type')}>
                  <option value="" disabled>Select industry or operating model…</option>
                  {meta &&
                    Object.entries(meta.business_types).map(([group, opts]) => (
                      <optgroup key={group} label={group}>
                        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
                      </optgroup>
                    ))}
                </select>
              </label>
            </>
          )}
          <label>Email<input required type="email" value={form.email} onChange={set('email')} autoComplete="email" /></label>
          <label>
            Password
            <input required type="password" value={form.password} onChange={set('password')} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : undefined} />
            {mode === 'register' && <small className="muted">At least 8 characters, including a letter and a number.</small>}
          </label>
          {mode === 'register' && (
            <label>
              Confirm password
              <input required type="password" value={form.confirm_password} onChange={set('confirm_password')} autoComplete="new-password" className={mismatch ? 'invalid' : ''} />
              {mismatch && <small className="error-text">Passwords do not match.</small>}
            </label>
          )}
          <ErrorBox message={error} />
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? <Spinner /> : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>
      </section>
    </div>
  )
}
