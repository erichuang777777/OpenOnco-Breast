import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import { AuthGuard } from './components/AuthGuard'
import { Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { PendingPage } from './pages/PendingPage'
import { PatientListPage } from './pages/PatientListPage'
import { PatientDetailPage } from './pages/PatientDetailPage'
import { PatientOncologyPage } from './pages/PatientOncologyPage'
import { BoardPage } from './pages/BoardPage'
import { DrugReqPage } from './pages/DrugReqPage'
import { AdminPage } from './pages/AdminPage'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout>
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
              element={<AuthGuard><PatientOncologyPage /></AuthGuard>}
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
        </Layout>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
