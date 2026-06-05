export function PendingPage() {
  return (
    <div style={{ fontFamily: 'sans-serif', maxWidth: 600, margin: '4rem auto', textAlign: 'center' }}>
      <h1>帳號已建立</h1>
      <p>您的帳號尚待管理員指派角色。</p>
      <p>請聯絡您的系統管理員並提供您的 Google 帳號 Email。</p>
      <a href="/auth/google">重新登入</a>
    </div>
  )
}
