import React from 'react'
import { MealEntry, MealType } from '../types'
import { Trash2, Edit2 } from 'lucide-react'

interface MealCardProps {
  meal: MealEntry
  onEdit: () => void
  onDelete: () => void
  isLoading?: boolean
}

const MEAL_TYPE_LABELS: Record<MealType, string> = {
  breakfast: '🌅 Завтрак',
  lunch: '🍽️ Обед',
  dinner: '🌙 Ужин',
  snack: '🍿 Закуска',
}

export const MealCard: React.FC<MealCardProps> = ({ meal, onEdit, onDelete, isLoading }) => {
  return (
    <div className="card p-4 mb-3">
      <div className="flex justify-between items-start mb-2">
        <div>
          <p className="font-semibold text-gray-900 dark:text-white">{meal.food_name}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {MEAL_TYPE_LABELS[meal.meal_type]}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onEdit}
            disabled={isLoading}
            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50"
          >
            <Edit2 className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          </button>
          <button
            onClick={onDelete}
            disabled={isLoading}
            className="p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4 text-red-600 dark:text-red-400" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 text-sm">
        <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-2">
          <p className="text-gray-600 dark:text-gray-400 text-xs">ккал</p>
          <p className="font-semibold text-blue-600 dark:text-blue-400">{Math.round(meal.calories)}</p>
        </div>
        <div className="bg-red-50 dark:bg-red-900/20 rounded p-2">
          <p className="text-gray-600 dark:text-gray-400 text-xs">Белки</p>
          <p className="font-semibold text-red-600 dark:text-red-400">{meal.protein_g.toFixed(1)}г</p>
        </div>
        <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded p-2">
          <p className="text-gray-600 dark:text-gray-400 text-xs">Жиры</p>
          <p className="font-semibold text-yellow-600 dark:text-yellow-400">{meal.fat_g.toFixed(1)}г</p>
        </div>
        <div className="bg-green-50 dark:bg-green-900/20 rounded p-2">
          <p className="text-gray-600 dark:text-gray-400 text-xs">Углеводы</p>
          <p className="font-semibold text-green-600 dark:text-green-400">{meal.carbs_g.toFixed(1)}г</p>
        </div>
      </div>
    </div>
  )
}
