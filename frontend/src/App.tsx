import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { AuthGuard } from './components/AuthGuard'
import { LoginPage } from './pages/LoginPage'
import { PendingPage } from './pages/PendingPage'
import { PatientListPage } from './pages/PatientListPage'
import { PatientDetailPage } from './pages/PatientDetailPage'
import { BoardPage } from './pages/BoardPage'
import { ClinicPage } from './pages/ClinicPage'
import { DrugReqPage } from './pages/DrugReqPage'
import { AdminPage } from './pages/AdminPage'

function NavBar() {
  const { user, logout } = useAuth()
  if (!user) return null
  return (
    <nav data-testid="navbar" style={{ padding: '0.5rem 1rem', background: '#1e40af', color: '#fff', display: 'flex', gap: '1rem', alignItems: 'center' }}>
      <span>OpenOnco</span>
      {(user.role === 'clinic_hcp' || user.role === 'tumor_board_hcp') && (
        <a href="/patients" style={{ color: '#fff' }} data-testid="nav-patients">患者列表</a>
      )}
      {user.role === 'tumor_board_hcp' && (
        <a href="/board" style={{ color: '#fff' }} data-testid="nav-board">腫瘤委員會</a>
      )}
      {(user.role === 'kb_admin' || user.role === 'auditor') && (
        <a href="/admin" style={{ color: '#fff' }} data-testid="nav-admin">管理</a>
      )}
      <button onClick={logout} data-testid="logout-btn" style={{ marginLeft: 'auto', cursor: 'pointer' }}>登出</button>
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NavBar />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/pending" element={<PendingPage />} />
          <Route path="/" element={<Navigate to="/patients" replace />} />
          <Route
            path="/patients"
            element={<AuthGuard><PatientListPage /></AuthGuard>}
          />
          <Route
            path="/patients/:mrn/onco"
            element={<AuthGuard><ClinicPage /></AuthGuard>}
          />
          <Route
            path="/patients/:mrn/drug-req"
            element={<AuthGuard><DrugReqPage /></AuthGuard>}
          />
          <Route
            path="/patients/:mrn"
            element={<AuthGuard><PatientDetailPage /></AuthGuard>}
          />
          <Route
            path="/board"
            element={<AuthGuard allowedRoles={['tumor_board_hcp', 'kb_admin']}><BoardPage /></AuthGuard>}
          />
          <Route
            path="/admin"
            element={<AuthGuard allowedRoles={['kb_admin', 'auditor']}><AdminPage /></AuthGuard>}
          />
          <Route path="*" element={<Navigate to="/patients" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
