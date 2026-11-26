import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { CalendarPlus, FileCheck2, LogIn, LogOut } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'

const LINKS = [
  { to: '/', label: 'Overview', auth: true },
  { to: '/contracts', label: 'Contracts', auth: true },
  { to: '/portfolio', label: 'Portfolio Review', auth: true },
  { to: '/upload', label: 'Upload Contracts', auth: true },
  { to: '/repository', label: 'Repository', auth: true },
  { to: '/about', label: 'About Us', auth: false },
]

export default function NavBar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  const exportCalendar = async () => {
    setBusy(true)
    try {
      await api.downloadCalendar()
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <NavLink to={user ? '/' : '/about'} className="brand">
          <span className="brand-mark">
            <FileCheck2 size={18} />
          </span>
          <span>My<strong>Contract</strong>IQ</span>
        </NavLink>
        <nav className="nav-links">
          {LINKS.filter((l) => user || !l.auth).map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to === '/'} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="nav-right">
          {user ? (
            <>
              <button className="btn btn-ghost btn-sm" onClick={exportCalendar} disabled={busy} title="Download all key dates as a calendar file">
                <CalendarPlus size={15} /> Export calendar
              </button>
              <div className="nav-user" title={user.email}>
                <span className="avatar">{user.first_name[0]}{user.last_name[0]}</span>
                <span className="nav-user-text">
                  <span>{user.first_name} {user.last_name}</span>
                  <small>{user.business_name}</small>
                </span>
              </div>
              <button
                className="btn btn-icon"
                title="Log out"
                onClick={async () => {
                  await signOut()
                  navigate('/login')
                }}
              >
                <LogOut size={16} />
              </button>
            </>
          ) : (
            <NavLink to="/login" className="btn btn-primary btn-sm">
              <LogIn size={15} /> Log in
            </NavLink>
          )}
        </div>
      </div>
    </header>
  )
}
