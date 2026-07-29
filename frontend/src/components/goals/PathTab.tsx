import React, { useCallback, useEffect, useState } from 'react'
import { goalsApi } from '../../api/goals'
import { GoalPath, GoalsToday } from '../../types'
import { toMonthKey, shiftMonth, isMonthAfter } from '../../utils/dates'
import { extractErrorMessage } from '../../utils/errors'
import { LoadingSpinner } from '../LoadingSpinner'
import { ErrorAlert } from '../ErrorAlert'
import { SuccessAlert } from '../SuccessAlert'
import { StreakCard } from './StreakCard'
import { DailyGoalsCard } from './DailyGoalsCard'
import { MonthPathCard } from './MonthPathCard'
import { RewardsCard } from './RewardsCard'
import { FreezeCard } from './FreezeCard'

interface Props {
  /** Цели дня приходят снаружи: та же загрузка обслуживает шапку вкладки. */
  goals: GoalsToday | null
  goalsLoading: boolean
  /** Перечитать цели дня после заморозки. */
  onGoalsChanged: (goals: GoalsToday) => void
}

// Вкладка «Путь»: серия, цель дня, путь месяца, награды и заморозки.
export const PathTab: React.FC<Props> = ({ goals, goalsLoading, onGoalsChanged }) => {
  const currentMonth = toMonthKey(new Date())
  const [month, setMonth] = useState(currentMonth)
  const [path, setPath] = useState<GoalPath | null>(null)
  const [pathLoading, setPathLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState('')
  const [freezing, setFreezing] = useState(false)

  const loadPath = useCallback(async (m: string) => {
    setPathLoading(true)
    try {
      setPath(await goalsApi.getPath(m))
      setError(null)
    } catch (e) {
      setError(extractErrorMessage(e))
    } finally {
      setPathLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPath(month)
  }, [month, loadPath])

  const handleShiftMonth = (delta: number) => {
    const next = shiftMonth(month, delta)
    if (isMonthAfter(next, currentMonth)) return // вперёд дальше текущего нельзя
    setMonth(next)
  }

  const handleFreeze = async () => {
    if (freezing) return
    setFreezing(true)
    setError(null)
    try {
      const updated = await goalsApi.useFreeze()
      onGoalsChanged(updated)
      await loadPath(month)
      setToast('Заморозка применена — серия сохранена')
    } catch (e) {
      setError(extractErrorMessage(e))
    } finally {
      setFreezing(false)
    }
  }

  if (goalsLoading && !goals) return <LoadingSpinner message="Загрузка прогресса..." />

  return (
    <div>
      {toast && (
        <div className="mb-3">
          <SuccessAlert message={toast} onClose={() => setToast('')} />
        </div>
      )}
      {error && (
        <div className="mb-3">
          {/* key — ErrorAlert прячет себя после закрытия; новый текст должен
              создать новый инстанс, иначе следующая ошибка не покажется. */}
          <ErrorAlert key={error} message={error} onClose={() => setError(null)} />
        </div>
      )}

      {goals && (
        <>
          <StreakCard goals={goals} variant="full" />
          <DailyGoalsCard goals={goals} />
        </>
      )}

      {pathLoading && !path ? (
        <LoadingSpinner message="Загрузка пути..." />
      ) : (
        path && (
          <>
            <MonthPathCard
              path={path}
              onShiftMonth={handleShiftMonth}
              canGoForward={isMonthAfter(currentMonth, month)}
            />
            <RewardsCard rewards={path.rewards} />
            <FreezeCard
              freezes={path.freezes_available}
              busy={freezing}
              onApply={handleFreeze}
            />
          </>
        )
      )}
    </div>
  )
}
