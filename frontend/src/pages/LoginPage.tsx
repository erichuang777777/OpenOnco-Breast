import { useState } from 'react'
import { DEV_LOGIN_ENABLED } from '../config'

const ROLES = [
  { value: 'clinic_hcp',       label: 'Clinic HCP' },
  { value: 'tumor_board_hcp',  label: 'Tumor Board HCP' },
  { value: 'kb_admin',         label: 'KB Admin' },
  { value: 'auditor',          label: 'Auditor' },
]

const DEV_ACCOUNTS = [
  { email: 'admin@openonco.local',   role: 'kb_admin' },
  { email: 'doctor@openonco.local',  role: 'tumor_board_hcp' },
  { email: 'clinic@openonco.local',  role: 'clinic_hcp' },
  { email: 'auditor@openonco.local', role: 'auditor' },
]

function DevLoginPanel({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState('clinic@openonco.local')
  const [role, setRole]   = useState('clinic_hcp')
  const [busy, setBusy]   = useState(false)
  const [err, setErr]     = useState('')

  async function login(e?: { email: string; role: string }) {
    const body = e ?? { email, role }
    setBusy(true)
    setErr('')
    try {
      const res = await fetch('/auth/dev/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      })
      if (res.ok) {
        onSuccess()
      } else {
        const j = await res.json().catch(() => null)
        setErr(j?.detail?.message ?? `HTTP ${res.status}`)
      }
    } catch {
      setErr('Network error — is the backend running on :8000?')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={panelStyle}>
      <p style={{ margin: '0 0 0.75rem', fontWeight: 600, color: '#b45309' }}>
        Dev Login (SQLite only)
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <label style={labelStyle}>
          Email
          <input
            value={email}
            onChange={v => setEmail(v.target.value)}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Role
          <select value={role} onChange={v => setRole(v.target.value)} style={inputStyle}>
            {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </label>
      </div>

      <button
        onClick={() => login()}
        disabled={busy}
        style={{ ...btnStyle, marginBottom: '0.75rem', width: '100%' }}
      >
        {busy ? 'Logging in…' : 'Login as this account'}
      </button>

      <p style={{ margin: '0 0 0.4rem', fontSize: 12, color: '#6b7280' }}>Quick-login:</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
        {DEV_ACCOUNTS.map(a => (
          <button
            key={a.email}
            onClick={() => login(a)}
            disabled={busy}
            style={quickBtnStyle}
          >
            {a.role.replace('_', ' ')}
          </button>
        ))}
      </div>

      {err && <p style={{ color: '#dc2626', marginTop: '0.75rem', fontSize: 13 }}>{err}</p>}
    </div>
  )
}

export function LoginPage() {
  function handleDevSuccess() {
    window.location.href = '/'
  }

  return (
    <div style={{ fontFamily: 'sans-serif', maxWidth: 480, margin: '4rem auto', textAlign: 'center', padding: '0 1rem' }}>
      <h1 style={{ marginBottom: '0.25rem' }}>OpenOnco Hospital</h1>
      <p style={{ color: '#6b7280', marginBottom: '2rem' }}>臨床決策支援系統</p>

      <a
        href="/auth/google"
        data-testid="google-login-btn"
        style={googleBtnStyle}
      >
        使用 Google 帳號登入
      </a>

      {DEV_LOGIN_ENABLED && (
        <div style={{ marginTop: '2rem' }}>
          <DevLoginPanel onSuccess={handleDevSuccess} />
        </div>
      )}
    </div>
  )
}

// ── styles ────────────────────────────────────────────────────────────────────

const googleBtnStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '0.75rem 1.5rem',
  background: '#1e40af',
  color: '#fff',
  borderRadius: 6,
  textDecoration: 'none',
}

const panelStyle: React.CSSProperties = {
  background: '#fffbeb',
  border: '1px solid #fbbf24',
  borderRadius: 8,
  padding: '1rem',
  textAlign: 'left',
}

const labelStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '0.25rem',
  fontSize: 13,
  color: '#374151',
}

const inputStyle: React.CSSProperties = {
  padding: '0.4rem 0.5rem',
  borderRadius: 4,
  border: '1px solid #d1d5db',
  fontSize: 13,
}

const btnStyle: React.CSSProperties = {
  padding: '0.5rem 1rem',
  background: '#92400e',
  color: '#fff',
  border: 'none',
  borderRadius: 5,
  cursor: 'pointer',
  fontSize: 13,
}

const quickBtnStyle: React.CSSProperties = {
  ...btnStyle,
  background: '#6b7280',
  padding: '0.3rem 0.6rem',
  fontSize: 12,
}
