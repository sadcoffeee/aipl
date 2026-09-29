import { useState } from 'react'
import * as api from '../api'
import type { User } from '../types'

export default function LoginView({ onLoggedIn }: { onLoggedIn: (user: User) => void }) {
  const [mode, setMode] = useState<'student' | 'admin'>('student')
  const [code, setCode] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function attempt(action: () => Promise<User>) {
    setBusy(true)
    setError(null)
    try {
      onLoggedIn(await action())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app login-screen">
      <div className="login-card">
        <h1>Python for biomedical data</h1>

        <nav className="tabs">
          <button
            className={mode === 'student' ? 'tab active' : 'tab'}
            onClick={() => setMode('student')}
          >
            Participant
          </button>
          <button
            className={mode === 'admin' ? 'tab active' : 'tab'}
            onClick={() => setMode('admin')}
          >
            Researcher
          </button>
        </nav>

        {mode === 'student' ? (
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void attempt(() => api.loginStudent(code))
            }}
          >
            <label className="field">
              <span>Your participation code</span>
              <input
                autoFocus
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="KVT-4F7QH2"
                autoCapitalize="characters"
              />
            </label>
            <p className="muted">You should have received one of these from researchers.</p>
            <button className="primary" disabled={busy || code.trim().length < 3}>
              {busy ? 'Checking...' : 'Start'}
            </button>
          </form>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void attempt(() => api.loginAdmin(username, password))
            }}
          >
            <label className="field">
              <span>Username</span>
              <input
                autoFocus
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button className="primary" disabled={busy || !username || !password}>
              {busy ? 'Checking...' : 'Log in'}
            </button>
          </form>
        )}

        {error && <div className="panel error login-error">{error}</div>}
      </div>
    </div>
  )
}
