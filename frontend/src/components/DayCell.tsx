import React from 'react'

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

// Ячейка недельной полоски из дизайна Rasify: белая плитка с подписью дня,
// числом и мини-баром прогресса калорий. Выбранный день — синяя плитка.
// Глупый, мемоизированный.
export const DayCell = React.memo<Props>(
  ({ label, dayNum, calories, goal, hasMeals, isSelected, isToday, onClick }) => {
    const pct = goal ? Math.min((calories / goal) * 100, 100) : hasMeals ? 100 : 0

    return (
      <button
        onClick={onClick}
        className={`flex flex-col items-center gap-1 py-2.5 pb-2 rounded-cell border transition-colors ${
          isSelected
            ? 'bg-primary-500 border-primary-500 shadow-day text-white'
            : 'bg-white dark:bg-card-dark border-line dark:border-line-dark hover:border-primary-300'
        }`}
      >
        <span className={`text-[10px] ${isSelected ? 'text-white/70' : 'text-tertiary'}`}>
          {label}
        </span>
        <span
          className={`text-[15px] font-semibold ${
            !isSelected && isToday ? 'text-primary-500 dark:text-primary-400' : ''
          }`}
        >
          {dayNum}
        </span>
        <div
          className={`w-[22px] h-1 rounded-full overflow-hidden ${
            isSelected ? 'bg-white/30' : 'bg-track dark:bg-track-dark'
          }`}
        >
          <div
            className={`h-1 rounded-full ${isSelected ? 'bg-white' : 'bg-primary-500 dark:bg-primary-400'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </button>
    )
  }
)

DayCell.displayName = 'DayCell'
