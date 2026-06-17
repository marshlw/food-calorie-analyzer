import React from 'react'
import { CalorieRing } from './CalorieRing'

interface Props {
  label: string
  dayNum: number
  calories: number
  goal?: number
  hasMeals: boolean
  isSelected: boolean
  isToday: boolean
  onClick: () => void
}

// Один день в недельной сетке. Глупый, мемоизированный.
export const DayCell = React.memo<Props>(
  ({ label, dayNum, calories, goal, hasMeals, isSelected, isToday, onClick }) => (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-1 py-2 rounded-xl transition-colors ${
        isSelected
          ? 'bg-primary-50 dark:bg-primary-900/30 ring-2 ring-primary-500'
          : 'hover:bg-gray-50 dark:hover:bg-gray-800'
      }`}
    >
      <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
      <span className={`text-sm font-semibold ${isToday ? 'text-primary-600 dark:text-primary-400' : ''}`}>
        {dayNum}
      </span>
      <div className="relative grid place-items-center">
        <CalorieRing value={calories} goal={goal} />
        <span className="absolute text-[10px] font-medium">
          {calories ? Math.round(calories) : '·'}
        </span>
      </div>
      <span className={`h-1 w-1 rounded-full ${hasMeals ? 'bg-primary-500' : 'bg-transparent'}`} />
    </button>
  )
)

DayCell.displayName = 'DayCell'
