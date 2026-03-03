import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useStats } from '../context/StatsContext'

export default function Layout() {
  const stats = useStats()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen flex bg-slate-50">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} userName={stats?.user?.nombre} />

      <main className="flex-1 flex flex-col min-w-0 transition-all duration-300 lg:ml-64">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-4 px-4 py-3 bg-white/80 backdrop-blur-md border-b border-slate-200/80 shrink-0">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 lg:hidden transition-colors"
            aria-label="Abrir menú"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="flex-1 min-w-0" />
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline text-sm font-medium text-slate-700 truncate max-w-[140px]">
              {stats?.user?.nombre}
            </span>
            <a href="/logout" className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-600 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors">
              Cerrar sesión
            </a>
          </div>
        </header>

        <div className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </div>
      </main>

      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden backdrop-blur-sm transition-opacity"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}
    </div>
  )
}
