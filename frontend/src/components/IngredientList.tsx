import React from 'react'
import { Ingredient, IngredientType } from '../types'

interface Props {
  ingredients: Ingredient[]
}

const TYPE_META: Record<IngredientType, { icon: string; label: string; cls: string }> = {
  protein:   { icon: '🥩', label: 'белок',  cls: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400' },
  carb:      { icon: '🍞', label: 'углевод', cls: 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400' },
  fat:       { icon: '🧈', label: 'жир',     cls: 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400' },
  vegetable: { icon: '🥦', label: 'овощ',    cls: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400' },
  unknown:   { icon: '🍽️', label: '',        cls: 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400' },
}

const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)

// Состав блюда от AI. Глупый, мемоизированный.
export const IngredientList = React.memo<Props>(({ ingredients }) => {
  if (!ingredients || ingredients.length === 0) return null

  return (
    <div>
      <p className="text-sm font-medium mb-2">Состав ({ingredients.length})</p>
      <div className="flex flex-wrap gap-2">
        {ingredients.map((ing, i) => {
          const meta = TYPE_META[ing.type] ?? TYPE_META.unknown
          return (
            <span
              key={`${ing.name}-${i}`}
              className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full ${meta.cls}`}
              title={meta.label}
            >
              <span>{meta.icon}</span>
              <span>{cap(ing.name)}</span>
              {ing.weight_g > 0 && <span className="opacity-70">· {Math.round(ing.weight_g)}г</span>}
            </span>
          )
        })}
      </div>
    </div>
  )
})

IngredientList.displayName = 'IngredientList'
