import { useCallback, useEffect, useState } from 'react'
import { tasksApi } from '../api/tasks'
import { AiAnalysisLimit } from '../types'

// Дневной лимит AI-анализов: сколько осталось из N на сегодня.
// refreshAiLimit() дёргаем после каждого анализа/закрытия модалки анализа.
export const useAiLimit = () => {
  const [aiLimit, setAiLimit] = useState<AiAnalysisLimit | null>(null)

  const refreshAiLimit = useCallback(() => {
    tasksApi
      .getAnalysisLimit()
      .then(setAiLimit)
      .catch(() => {
        // Не критично для UI — просто не показываем счётчик
      })
  }, [])

  useEffect(() => {
    refreshAiLimit()
  }, [refreshAiLimit])

  const aiExhausted = aiLimit !== null && aiLimit.remaining <= 0

  return { aiLimit, aiExhausted, refreshAiLimit }
}
