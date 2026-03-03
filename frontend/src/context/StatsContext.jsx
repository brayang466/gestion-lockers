import { createContext, useContext } from 'react'

const StatsContext = createContext(null)

export function StatsProvider({ value, children }) {
  return <StatsContext.Provider value={value}>{children}</StatsContext.Provider>
}

export function useStats() {
  return useContext(StatsContext)
}
