import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react'
import { DailyLog } from '../types'
import { mealsApi } from '../api/meals'
import { startOfWeek, toISODate } from '../utils/dates'
import { extractErrorMessage } from '../utils/errors'

interface DiaryState {
  selectedDate: string // 'YYYY-MM-DD'
  weekStart: string // понедельник текущей недели
  weekLogs: Record<string, DailyLog> // кэш логов по датам
  weekStatus: 'idle' | 'loading' | 'error'
  weekError: string | null
}

type DiaryAction =
  | { type: 'SELECT_DATE'; date: string }
  | { type: 'SET_WEEK_START'; weekStart: string }
  | { type: 'WEEK_LOADING' }
  | { type: 'WEEK_LOADED'; logs: Record<string, DailyLog> }
  | { type: 'WEEK_ERROR'; error: string }
  | { type: 'INVALIDATE_DAY'; date: string; log: DailyLog }

const reducer = (s: DiaryState, a: DiaryAction): DiaryState => {
  switch (a.type) {
    case 'SELECT_DATE':
      return { ...s, selectedDate: a.date }
    case 'SET_WEEK_START':
      return { ...s, weekStart: a.weekStart }
    case 'WEEK_LOADING':
      return { ...s, weekStatus: 'loading', weekError: null }
    case 'WEEK_LOADED':
      return { ...s, weekStatus: 'idle', weekLogs: a.logs }
    case 'WEEK_ERROR':
      return { ...s, weekStatus: 'error', weekError: a.error }
    case 'INVALIDATE_DAY':
      return { ...s, weekLogs: { ...s.weekLogs, [a.date]: a.log } }
    default:
      return s
  }
}

interface DiaryCtx extends DiaryState {
  selectDate: (d: string) => void
  shiftWeek: (delta: number) => void
  reloadWeek: () => Promise<void>
  refreshDay: (date: string) => Promise<DailyLog>
}

const Ctx = createContext<DiaryCtx | null>(null)

export const DiaryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, undefined, () => {
    const now = new Date()
    return {
      selectedDate: toISODate(now),
      weekStart: toISODate(startOfWeek(now)),
      weekLogs: {},
      weekStatus: 'idle' as const,
      weekError: null,
    }
  })

  const reloadWeek = useCallback(async () => {
    dispatch({ type: 'WEEK_LOADING' })
    try {
      const logs = await mealsApi.getWeekLogs(state.weekStart)
      dispatch({ type: 'WEEK_LOADED', logs })
    } catch (e) {
      dispatch({ type: 'WEEK_ERROR', error: extractErrorMessage(e) })
    }
  }, [state.weekStart])

  // Перезагружаем неделю при смене weekStart
  useEffect(() => {
    reloadWeek()
  }, [reloadWeek])

  const refreshDay = useCallback(async (date: string) => {
    const log = await mealsApi.getDailyLog(date)
    dispatch({ type: 'INVALIDATE_DAY', date, log })
    return log
  }, [])

  const selectDate = useCallback((d: string) => dispatch({ type: 'SELECT_DATE', date: d }), [])

  const shiftWeek = useCallback(
    (delta: number) => {
      const next = new Date(state.weekStart)
      next.setDate(next.getDate() + delta * 7)
      dispatch({ type: 'SET_WEEK_START', weekStart: toISODate(next) })
    },
    [state.weekStart]
  )

  return (
    <Ctx.Provider value={{ ...state, selectDate, shiftWeek, reloadWeek, refreshDay }}>
      {children}
    </Ctx.Provider>
  )
}

export const useDiary = (): DiaryCtx => {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useDiary must be used within DiaryProvider')
  return ctx
}
