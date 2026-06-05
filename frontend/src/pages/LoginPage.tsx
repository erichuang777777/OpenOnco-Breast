export function LoginPage() {
  return (
    <div style={{ fontFamily: 'sans-serif', maxWidth: 480, margin: '4rem auto', textAlign: 'center' }}>
      <h1>OpenOnco Hospital</h1>
      <p>臨床決策支援系統</p>
      <a
        href="/auth/google"
        data-testid="google-login-btn"
        style={{
          display: 'inline-block',
          padding: '0.75rem 1.5rem',
          background: '#1e40af',
          color: '#fff',
          borderRadius: 6,
          textDecoration: 'none',
          marginTop: '1rem',
        }}
      >
        使用 Google 帳號登入
      </a>
    </div>
  )
}
