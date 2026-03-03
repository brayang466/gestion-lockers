import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { StatsProvider } from './context/StatsContext'
import Layout from './components/Layout'
import DashboardHome from './pages/DashboardHome'
import ModuleCrudPage from './components/ModuleCrudPage'

export default function App() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/dashboard/stats', { credentials: 'same-origin' })
      .then((res) => {
        if (!res.ok) throw new Error('Sesión inválida')
        return res.json()
      })
      .then((data) => {
        setStats(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-400/30" />
          <p className="text-slate-500 text-sm">Cargando dashboard...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <div className="text-center">
          <p className="text-red-600 font-medium mb-2">No se pudo cargar el dashboard</p>
          <a href="/login" className="text-amber-600 hover:underline">Volver al login</a>
        </div>
      </div>
    )
  }

  return (
    <StatsProvider value={stats}>
      <BrowserRouter basename="/dashboard">
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardHome />} />
            <Route path=":modulePath" element={<ModuleCrudPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StatsProvider>
  )
}
