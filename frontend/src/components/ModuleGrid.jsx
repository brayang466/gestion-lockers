export default function ModuleGrid({ modules }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {modules.map((mod, i) => (
        <a
          key={mod.title}
          href={mod.href}
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
            <span className="text-sm text-slate-500 block mt-0.5">{mod.desc}</span>
          </div>
          <span className="flex-shrink-0 text-slate-300 group-hover:text-amber-500 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </span>
        </a>
      ))}
    </div>
  )
}
