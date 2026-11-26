import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { SignupCalendarPrompt } from './components/CalendarPrompts'
import NavBar from './components/NavBar'
import { Spinner } from './components/ui'
import AboutUs from './pages/AboutUs'
import Contracts from './pages/Contracts'
import Login from './pages/Login'
import OverviewPage from './pages/Overview'
import Portfolio from './pages/Portfolio'
import Repository from './pages/Repository'
import Upload from './pages/Upload'

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading)
    return (
      <div className="center-page">
        <Spinner label="Loading…" />
      </div>
    )
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <NavBar />
        <SignupCalendarPrompt />
        <main className="container">
          <Routes>
            <Route path="/" element={<Protected><OverviewPage /></Protected>} />
            <Route path="/contracts" element={<Protected><Contracts /></Protected>} />
            <Route path="/portfolio" element={<Protected><Portfolio /></Protected>} />
            <Route path="/upload" element={<Protected><Upload /></Protected>} />
            <Route path="/repository" element={<Protected><Repository /></Protected>} />
            <Route path="/about" element={<AboutUs />} />
            <Route path="/login" element={<Login />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <footer className="footer">© {new Date().getFullYear()} MyContractIQ · Smarter contracts for small business</footer>
      </BrowserRouter>
    </AuthProvider>
  )
}
