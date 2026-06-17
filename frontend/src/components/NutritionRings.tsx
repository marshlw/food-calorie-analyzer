import React from 'react'
import { CalorieRing } from './CalorieRing'
import { NutritionTargets } from '../types'

interface Props {
  totals: { calories: number; protein: number; fat: number; carbs: number }
  targets?: NutritionTargets | null
}

type RingDef = {
  label: string
  value: number
  goal?: number | null
  unit: string
  color: string
}

// Кольцо + текущее значение/норма. Если нормы нет — показываем только факт.
const Ring: React.FC<RingDef> = ({ label, value, goal, unit, color }) => {
  const rounded = Math.round(value)
  const pctText = goal ? `${Math.round((value / goal) * 100)}%` : null
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative grid place-items-center">
        <CalorieRing value={value} goal={goal ?? 0} size={64} strokeWidth={6} colorClass={color} />
        <span className="absolute text-xs font-bold">{rounded}</span>
      </div>
      <span className="text-xs font-medium">{label}</span>
      <span className="text-[11px] text-gray-500 dark:text-gray-400">
        {goal ? `${rounded} / ${Math.round(goal)} ${unit}` : `${rounded} ${unit}`}
      </span>
      {pctText && <span className="text-[10px] text-gray-400">{pctText}</span>}
    </div>
  )
}

export const NutritionRings: React.FC<Props> = ({ totals, targets }) => {
  const rings: RingDef[] = [
    {
      label: 'Калории',
      value: totals.calories,
      goal: targets?.calories,
      unit: 'ккал',
      color: 'stroke-blue-500',
    },
    {
      label: 'Белки',
      value: totals.protein,
      goal: targets?.protein_g,
      unit: 'г',
      color: 'stroke-red-500',
    },
    {
      label: 'Жиры',
      value: totals.fat,
      goal: targets?.fat_g,
      unit: 'г',
      color: 'stroke-yellow-500',
    },
    {
      label: 'Углеводы',
      value: totals.carbs,
      goal: targets?.carbs_g,
      unit: 'г',
      color: 'stroke-green-500',
    },
  ]

  return (
    <div className="grid grid-cols-4 gap-2">
      {rings.map((r) => (
        <Ring key={r.label} {...r} />
      ))}
    </div>
  )
}
