import { useState } from 'react'
import Sidebar from './Sidebar'
import StatCard from './StatCard'
import ModuleGrid from './ModuleGrid'

const MODULES = [
  { title: 'Base de Lockers', desc: 'Listado y estado de lockers', href: '#', icon: '📦' },
  { title: 'Locker Disponibles', desc: 'Disponibles para asignar', href: '#', icon: '🔓' },
  { title: 'Base de Dotaciones', desc: 'Catálogo de dotaciones', href: '#', icon: '📋' },
  { title: 'Dotaciones Disponibles', desc: 'Stock por código y talla', href: '#', icon: '✅' },
  { title: 'Registro de Personal', desc: 'Alta y listado de personal', href: '#', icon: '👤' },
  { title: 'Personal Presupuestado', desc: 'Por área, aprobados y contratados', href: '#', icon: '📊' },
  { title: 'Registro de Asignaciones', desc: 'Asignar locker o dotación', href: '#', icon: '🔗' },
  { title: 'Historial de Retiros', desc: 'Retiros y devoluciones', href: '#', icon: '📤' },
  { title: 'Ingreso de Lockers', desc: 'Registrar nuevos lockers', href: '#', icon: '➕' },
  { title: 'Ingreso de Dotación', desc: 'Registrar nuevas dotaciones', href: '#', icon: '📥' },
]

export default function Dashboard({ stats }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const cards = [
    { label: 'Total lockers', value: stats?.lockers?.total ?? 0, sub: (stats?.lockers?.disponibles ?? 0) + ' disponibles', icon: '📦', color: 'amber', delay: 0 },
    { label: 'Dotaciones', value: stats?.dotaciones?.total ?? 0, sub: (stats?.dotaciones?.disponibles ?? 0) + ' en stock', icon: '📋', color: 'emerald', delay: 50 },
    { label: 'Personal', value: stats?.personal ?? 0, sub: 'registrados', icon: '👤', color: 'blue', delay: 100 },
    { label: 'Asignaciones', value: stats?.asignaciones ?? 0, sub: 'activas', icon: '🔗', color: 'violet', delay: 150 },
    { label: 'Retiros', value: stats?.retiros ?? 0, sub: 'en historial', icon: '📤', color: 'slate', delay: 200 },
  ]

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
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-1 animate-fade-in">Dashboard</h1>
            <p className="text-slate-500 text-sm sm:text-base mb-6 animate-fade-in" style={{ animationDelay: '50ms' }}>
              Resumen y acceso a los módulos del sistema
            </p>

            <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-8">
              {cards.map((card) => (
                <StatCard key={card.label} {...card} />
              ))}
            </section>

            <section className="animate-fade-in" style={{ animationDelay: '250ms' }}>
              <h2 className="text-lg font-semibold text-slate-800 mb-4">Módulos</h2>
              <ModuleGrid modules={MODULES} />
            </section>
          </div>
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
