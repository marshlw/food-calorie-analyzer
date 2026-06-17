import React from 'react'

interface Props {
  value: number
  goal?: number
  size?: number
  strokeWidth?: number
  // Если задан — используется как цвет прогресса (для колец БЖУ).
  // Если не задан — поведение «калорий»: зелёный, красный при переборе.
  colorClass?: string
}

// SVG-кольцо прогресса. Глупый, мемоизированный.
export const CalorieRing = React.memo<Props>(
  ({ value, goal = 2000, size = 44, strokeWidth = 4, colorClass }) => {
    const r = (size - strokeWidth - 2) / 2
    const c = 2 * Math.PI * r
    const pct = goal > 0 ? Math.min(value / goal, 1) : 0
    const stroke = colorClass ?? (pct >= 1 ? 'stroke-red-500' : 'stroke-primary-500')

    return (
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={strokeWidth}
          fill="none"
          className="stroke-gray-200 dark:stroke-gray-700"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          className={stroke}
        />
      </svg>
    )
  }
)

CalorieRing.displayName = 'CalorieRing'
