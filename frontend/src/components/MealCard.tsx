import React from 'react'
import { MealEntry } from '../types'
import { MEAL_TYPE_META, kbjuLine } from '../utils/mealTypes'
import { capitalize as cap } from '../utils/text'
import { Trash2, Edit2 } from 'lucide-react'

interface MealCardProps {
  meal: MealEntry
  onEdit: () => void
  onDelete: () => void
  isLoading?: boolean
  // Показывать ли чип типа приёма (в сгруппированном списке он в заголовке секции)
  showTypeChip?: boolean
}

// Запись приёма пищи из дизайна Rasify: точка-маркер, название, строка КБЖУ,
// чип AI (если запись из анализа) и действия редактировать/удалить.
export const MealCard: React.FC<MealCardProps> = ({
  meal,
  onEdit,
  onDelete,
  isLoading,
  showTypeChip = false,
}) => {
  const meta = MEAL_TYPE_META[meal.meal_type]

  return (
    <div className="card-tile px-4 py-3.5 mb-2.5 flex items-center gap-3.5">
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${meta.dot}`} />

      <div className="flex-1 min-w-0">
        {showTypeChip && (
          <span className={`chip ${meta.chip} mb-1.5`}>
            <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
            {meta.label}
          </span>
        )}
        <div className="text-[15px] font-semibold truncate">{cap(meal.food_name)}</div>
        <div className="text-xs text-secondary mt-0.5">{kbjuLine(meal)}</div>
        {/* Блюда составного приёма */}
        {meal.items && meal.items.length > 1 && (
          <div className="mt-1.5 flex flex-col gap-0.5">
            {meal.items.map((item, idx) => (
              <div key={item.id ?? idx} className="flex justify-between items-baseline text-[11px]">
                <span className="text-tertiary truncate pr-2">{cap(item.food_name)}</span>
                <span className="text-tertiary flex-shrink-0">
                  {Math.round(item.weight_g)} г · {Math.round(item.calories)} ккал
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {meal.task_id && <span className="chip-ai flex-shrink-0">AI</span>}

      <div className="flex gap-1 flex-shrink-0">
        <button
          onClick={onEdit}
          disabled={isLoading}
          aria-label="Редактировать"
          className="p-1.5 rounded-lg text-faint dark:text-faint-dark hover:text-primary-500 hover:bg-primary-50 dark:hover:bg-chip-dark transition-colors disabled:opacity-50"
        >
          <Edit2 className="h-4 w-4" />
        </button>
        <button
          onClick={onDelete}
          disabled={isLoading}
          aria-label="Удалить"
          className="p-1.5 rounded-lg text-faint dark:text-faint-dark hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
