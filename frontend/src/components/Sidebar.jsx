import { Link, NavLink } from 'react-router-dom'
import { MODULES } from '../config/modulesConfig'

export default function Sidebar({ open, onClose, userName }) {
  const cls = 'fixed top-0 left-0 z-50 h-full w-64 bg-slate-900 text-white transform transition-transform duration-300 ease-out lg:translate-x-0 lg:static lg:z-auto ' + (open ? 'translate-x-0' : '-translate-x-full')
  return (
    <aside className={cls}>
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500 flex items-center justify-center text-xl">🔐</div>
            <span className="font-bold text-slate-100">Gestor Lockers</span>
          </Link>
          <button type="button" onClick={onClose} className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50 lg:hidden" aria-label="Cerrar menú">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <nav className="flex-1 p-4 overflow-y-auto">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              'flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium ' +
              (isActive ? 'bg-slate-700/50 text-amber-400' : 'text-slate-300 hover:bg-slate-700/30 hover:text-white')
            }
          >
            <span className="text-lg">📊</span> Dashboard
          </NavLink>
          <p className="mt-4 mb-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Módulos</p>
          <ul className="space-y-0.5">
            {MODULES.map((mod) => (
              <li key={mod.path}>
                <NavLink
                  to={mod.path}
                  onClick={onClose}
                  className={({ isActive }) =>
                    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm ' +
                    (isActive ? 'bg-slate-700/50 text-amber-400' : 'text-slate-300 hover:bg-slate-700/30 hover:text-white')
                  }
                >
                  <span className="text-base">{mod.icon}</span>
                  <span className="truncate">{mod.title}</span>
                </NavLink>
              </li>
            ))}
          </ul>
          {userName && <p className="mt-4 px-3 py-2 text-xs text-slate-500 truncate" title={userName}>{userName}</p>}
        </nav>
      </div>
    </aside>
  )
}
