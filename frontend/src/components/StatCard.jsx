const colorMap = {
  amber: 'bg-amber-500/10 text-amber-600 border-amber-200',
  emerald: 'bg-emerald-500/10 text-emerald-600 border-emerald-200',
  blue: 'bg-blue-500/10 text-blue-600 border-blue-200',
  violet: 'bg-violet-500/10 text-violet-600 border-violet-200',
  slate: 'bg-slate-500/10 text-slate-600 border-slate-200',
}

export default function StatCard({ label, value, sub, icon, color, delay = 0 }) {
  return (
    <div
      className="group relative bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm hover:shadow-md hover:border-slate-300/80 transition-all duration-300 ease-out overflow-hidden"
      style={{
        animation: 'slideUp 0.5s ease-out forwards',
        opacity: 0,
        animationDelay: `${delay}ms`,
        animationFillMode: 'forwards',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500 mb-0.5">{label}</p>
          <p className="text-2xl sm:text-3xl font-bold text-slate-900 tabular-nums transition-transform duration-300 group-hover:scale-105">
            {value}
          </p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <div
          className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center text-2xl border ${colorMap[color] || colorMap.slate} transition-transform duration-300 group-hover:scale-110`}
        >
          {icon}
        </div>
      </div>
    </div>
  )
}
