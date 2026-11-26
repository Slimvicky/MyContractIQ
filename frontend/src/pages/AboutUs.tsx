import { Link } from 'react-router-dom'
import { Bot, CalendarClock, Layers, PlugZap, ShieldCheck, Target } from 'lucide-react'
import { useAuth } from '../auth'

export default function AboutUs() {
  const { user } = useAuth()
  return (
    <div className="about">
      <section className="about-hero">
        <span className="eyebrow">About Us</span>
        <h1>Built for the businesses that keep our communities running.</h1>
        <p className="lead">
          We empower small businesses with simple, affordable tools to manage contracts, streamline operations, and connect
          essential business systems—all in one platform.
        </p>
      </section>

      <section className="card mission">
        <Target size={28} className="accent-text" />
        <div>
          <h2>Our mission</h2>
          <p>
            Our mission is to eliminate administrative complexity through smarter contract management and seamless
            integrations, allowing business owners to focus on what matters most: growing their business.
          </p>
        </div>
      </section>

      <section className="feature-grid">
        <div className="card feature">
          <CalendarClock size={22} />
          <h3>Never miss a renewal</h3>
          <p>Track end dates and notice deadlines, and export them straight to your calendar.</p>
        </div>
        <div className="card feature">
          <Bot size={22} />
          <h3>AI rate agent</h3>
          <p>From 60 days before renewal, our agent searches the web for better rates on your behalf.</p>
        </div>
        <div className="card feature">
          <Layers size={22} />
          <h3>See the whole portfolio</h3>
          <p>Expense and revenue contracts in one place, so overlaps and savings stop hiding in silos.</p>
        </div>
        <div className="card feature">
          <PlugZap size={22} />
          <h3>Bulk upload in seconds</h3>
          <p>Drop in a stack of PDFs or a spreadsheet; we read the key terms for you.</p>
        </div>
        <div className="card feature">
          <ShieldCheck size={22} />
          <h3>Secure by default</h3>
          <p>Salted, hashed passwords, a tamper-evident audit trail, and defences against prompt injection.</p>
        </div>
      </section>

      {!user && (
        <section className="cta card">
          <h2>Ready to take control of your contracts?</h2>
          <Link to="/login" className="btn btn-primary">Create a free account</Link>
        </section>
      )}
    </div>
  )
}
