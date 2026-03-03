import { Link } from 'react-router-dom'
import StatCard from '../components/StatCard'
import { useStats } from '../context/StatsContext'
import { MODULES } from '../config/modulesConfig'

const CARD_ICONS = {
  lockers: '📦',
  dotaciones: '📋',
  personal: '👤',
  asignaciones: '🔗',
  retiros: '📤',
}

export default function DashboardHome() {
  const stats = useStats()
  const cards = [
    { label: 'Total lockers', value: stats?.lockers?.total ?? 0, sub: (stats?.lockers?.disponibles ?? 0) + ' disponibles', icon: CARD_ICONS.lockers, color: 'amber', delay: 0 },
    { label: 'Dotaciones', value: stats?.dotaciones?.total ?? 0, sub: (stats?.dotaciones?.disponibles ?? 0) + ' en stock', icon: CARD_ICONS.dotaciones, color: 'emerald', delay: 50 },
    { label: 'Personal', value: stats?.personal ?? 0, sub: 'registrados', icon: CARD_ICONS.personal, color: 'blue', delay: 100 },
    { label: 'Asignaciones', value: stats?.asignaciones ?? 0, sub: 'activas', icon: CARD_ICONS.asignaciones, color: 'violet', delay: 150 },
    { label: 'Retiros', value: stats?.retiros ?? 0, sub: 'en historial', icon: CARD_ICONS.retiros, color: 'slate', delay: 200 },
  ]

  return (
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
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {MODULES.map((mod, i) => (
            <Link
              key={mod.path}
              to={mod.path}
              className="group flex items-start gap-4 p-4 rounded-xl bg-white border border-slate-200/80 shadow-sm hover:shadow-md hover:border-amber-200/80 hover:bg-amber-50/30 transition-all duration-300 ease-out"
              style={{
                animation: 'slideUp 0.5s ease-out forwards',
                opacity: 0,
                animationDelay: `${300 + i * 40}ms`,
                animationFillMode: 'forwards',
              }}
            >
              <span className="flex-shrink-0 w-11 h-11 rounded-xl bg-slate-100 group-hover:bg-amber-100 text-xl flex items-center justify-center transition-colors duration-300">
                {mod.icon}
              </span>
              <div className="min-w-0 flex-1">
                <span className="font-semibold text-slate-800 group-hover:text-amber-800 block transition-colors">
                  {mod.title}
                </span>
                <span className="text-sm text-slate-500 block mt-0.5">Listado y gestión</span>
              </div>
              <span className="flex-shrink-0 text-slate-300 group-hover:text-amber-500 transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
