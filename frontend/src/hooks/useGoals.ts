import { useCallback, useEffect, useState } from 'react'
import { goalsApi } from '../api/goals'
import { GoalsToday } from '../types'
import { extractErrorMessage } from '../utils/errors'

/** Цели дня + серия. Используется карточкой серии на «Дневнике»
 *  и шапкой вкладки «Путь».
 *
 *  Ошибку не глотаем полностью: карточка серии второстепенна, поэтому при
 *  сбое она просто не рисуется, но текст ошибки доступен вызывающему коду. */
export const useGoals = (dateStr?: string) => {
  const [goals, setGoals] = useState<GoalsToday | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await goalsApi.getToday(dateStr)
      setGoals(data)
      setError(null)
      return data
    } catch (e) {
      setError(extractErrorMessage(e))
      return null
    } finally {
      setIsLoading(false)
    }
  }, [dateStr])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { goals, setGoals, isLoading, error, refresh }
}
