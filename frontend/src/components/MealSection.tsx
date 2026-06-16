import React from 'react'
import { MealEntry } from '../types'
import { MealCard } from './MealCard'

interface Props {
  title: string
  meals: MealEntry[]
  onEdit: (m: MealEntry) => void
  onDelete: (m: MealEntry) => void
  busy?: boolean
}

// Одна категория приёмов пищи (Завтрак/Обед/...). Глупый, мемоизированный.
export const MealSection = React.memo<Props>(({ title, meals, onEdit, onDelete, busy }) => {
  if (meals.length === 0) return null

  const kcal = Math.round(meals.reduce((s, m) => s + m.calories, 0))

  return (
    <section className="mb-5">
      <div className="flex justify-between items-baseline mb-2">
        <h3 className="font-semibold">{title}</h3>
        <span className="text-xs text-gray-500 dark:text-gray-400">{kcal} ккал</span>
      </div>
      {meals.map((m) => (
        <MealCard
          key={m.id}
          meal={m}
          onEdit={() => onEdit(m)}
          onDelete={() => onDelete(m)}
          isLoading={busy}
        />
      ))}
    </section>
  )
})

MealSection.displayName = 'MealSection'
