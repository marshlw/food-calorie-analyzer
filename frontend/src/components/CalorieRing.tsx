import React from 'react'

interface Props {
  value: number
  goal?: number
  size?: number
}

// SVG-кольцо прогресса по калориям. Глупый, мемоизированный.
export const CalorieRing = React.memo<Props>(({ value, goal = 2000, size = 44 }) => {
  const r = (size - 6) / 2
  const c = 2 * Math.PI * r
  const pct = goal > 0 ? Math.min(value / goal, 1) : 0

  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeWidth={4}
        fill="none"
        className="stroke-gray-200 dark:stroke-gray-700"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeWidth={4}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - pct)}
        className={pct >= 1 ? 'stroke-red-500' : 'stroke-primary-500'}
      />
    </svg>
  )
})

CalorieRing.displayName = 'CalorieRing'
