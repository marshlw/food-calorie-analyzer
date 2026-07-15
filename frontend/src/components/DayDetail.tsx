import React, { useEffect, useMemo } from 'react'
import { useDiary } from '../context/DiaryContext'
import { useApi } from '../hooks/useApi'
import { mealsApi } from '../api/meals'
import { DailyLog, MealEntry, MealType } from '../types'
import { DailyStats } from './DailyStats'
import { WaterCard } from './WaterCard'
import { MealSection } from './MealSection'
import { LoadingSpinner } from './LoadingSpinner'

const ORDER: { type: MealType; title: string }[] = [
  { type: 'breakfast', title: 'Завтрак' },
  { type: 'lunch', title: 'Обед' },
  { type: 'dinner', title: 'Ужин' },
  { type: 'snacks', title: 'Перекусы' },
]

interface Props {
  onEdit: (m: MealEntry) => void
  onDelete: (m: MealEntry) => void
  onView?: (m: MealEntry) => void
  busy?: boolean
}

// Детальный вид выбранного дня с группировкой по типам приёмов. Smart.
export const DayDetail: React.FC<Props> = ({ onEdit, onDelete, onView, busy }) => {
  const { selectedDate, weekLogs } = useDiary()
  const { data, isLoading, execute } = useApi<DailyLog>()

  // Если день уже в недельном кэше — используем его, иначе подгружаем точечно.
  const cached = weekLogs[selectedDate]
  useEffect(() => {
    if (!cached) {
      execute(() => mealsApi.getDailyLog(selectedDate))
    }
  }, [selectedDate, cached]) // eslint-disable-line react-hooks/exhaustive-deps

  const log = cached ?? data

  const grouped = useMemo(() => {
    const g: Record<MealType, MealEntry[]> = {
      breakfast: [],
      lunch: [],
      dinner: [],
      snacks: [],
    }
    log?.meals.forEach((m) => g[m.meal_type]?.push(m))
    return g
  }, [log])

  if (!log && isLoading) return <LoadingSpinner message="Загрузка дня..." />
  if (!log) return null

  return (
    <div>
      <DailyStats log={log} />
      <WaterCard water={log.water} />
      {log.meals.length === 0 ? (
        <div className="text-center py-10 text-secondary text-sm">
          Нет приёмов пищи за этот день
        </div>
      ) : (
        ORDER.map(({ type, title }) => (
          <MealSection
            key={type}
            title={title}
            meals={grouped[type]}
            onEdit={onEdit}
            onDelete={onDelete}
            onView={onView}
            busy={busy}
          />
        ))
      )}
    </div>
  )
}
