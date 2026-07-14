import React from 'react'
import { Ingredient, IngredientType } from '../types'
import { capitalize as cap } from '../utils/text'

interface Props {
  ingredients: Ingredient[]
}

// Чипы состава из дизайна Rasify («Помидоры · 100 г»): цвет по типу нутриента.
const TYPE_META: Record<IngredientType, { label: string; cls: string }> = {
  protein: {
    label: 'белок',
    cls: 'bg-protein-chip text-protein-text dark:bg-protein-dark/15 dark:text-protein-dark',
  },
  carb: {
    label: 'углевод',
    cls: 'bg-carbs-chip text-carbs-text dark:bg-carbs-dark/15 dark:text-carbs-dark',
  },
  fat: {
    label: 'жир',
    cls: 'bg-fat-chip text-fat-text dark:bg-fat-dark/15 dark:text-fat-dark',
  },
  vegetable: {
    label: 'овощ',
    cls: 'bg-carbs-chip text-carbs-text dark:bg-carbs-dark/15 dark:text-carbs-dark',
  },
  unknown: {
    label: '',
    cls: 'bg-surface text-muted dark:bg-chip-dark dark:text-muted-dark',
  },
}

// Состав блюда от AI. Глупый, мемоизированный.
export const IngredientList = React.memo<Props>(({ ingredients }) => {
  if (!ingredients || ingredients.length === 0) return null

  return (
    <div>
      <p className="text-[13px] font-semibold mb-2.5">
        Состав · {ingredients.length}{' '}
        {ingredients.length === 1 ? 'ингредиент' : ingredients.length < 5 ? 'ингредиента' : 'ингредиентов'}
      </p>
      <div className="flex flex-wrap gap-2">
        {ingredients.map((ing, i) => {
          const meta = TYPE_META[ing.type] ?? TYPE_META.unknown
          return (
            <span
              key={`${ing.name}-${i}`}
              className={`inline-flex items-center gap-1 text-xs px-[11px] py-1.5 rounded-full ${meta.cls}`}
              title={meta.label}
            >
              <span>{cap(ing.name)}</span>
              {ing.weight_g > 0 && <span className="opacity-80">· {Math.round(ing.weight_g)} г</span>}
            </span>
          )
        })}
      </div>
    </div>
  )
})

IngredientList.displayName = 'IngredientList'
