import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Operations from './pages/Operations'
import History from './pages/History'
import Analytics from './pages/Analytics'
import Predictions from './pages/Predictions'
import DCA from './pages/DCA'
import Alerts from './pages/Alerts'
import Settings from './pages/Settings'
import ScenarioSimulator from './pages/ScenarioSimulator'
import TaxView from './pages/TaxView'
import Healthcheck from './pages/Healthcheck'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="operations" element={<Operations />} />
            <Route path="history" element={<History />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="predictions" element={<Predictions />} />
            <Route path="dca" element={<DCA />} />
            <Route path="alerts" element={<Alerts />} />              <Route path="settings" element={<Settings />} />
              <Route path="scenario" element={<ScenarioSimulator />} />
              <Route path="tax" element={<TaxView />} />
              <Route path="health" element={<Healthcheck />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
