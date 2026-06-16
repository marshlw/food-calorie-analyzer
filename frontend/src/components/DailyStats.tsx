import React from 'react'
import { DailyLog } from '../types'
import { TrendingUp } from 'lucide-react'

interface DailyStatsProps {
  log: DailyLog
}

export const DailyStats: React.FC<DailyStatsProps> = ({ log }) => {
  const stats = [
    { label: 'Калории', value: Math.round(log.total_calories), unit: 'ккал', color: 'blue' },
    { label: 'Белки', value: log.total_protein.toFixed(1), unit: 'г', color: 'red' },
    { label: 'Жиры', value: log.total_fat.toFixed(1), unit: 'г', color: 'yellow' },
    { label: 'Углеводы', value: log.total_carbs.toFixed(1), unit: 'г', color: 'green' },
  ]

  const colorMap = {
    blue: 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400',
    red: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400',
    yellow: 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400',
    green: 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400',
  }

  return (
    <div className="card p-6 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-primary-500" />
        <h3 className="text-lg font-semibold">Сегодняшняя сводка</h3>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className={`${colorMap[stat.color as keyof typeof colorMap]} rounded-lg p-4`}
          >
            <p className="text-xs font-medium opacity-75 mb-1">{stat.label}</p>
            <p className="text-2xl font-bold">
              {stat.value}
              <span className="text-sm ml-1">{stat.unit}</span>
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
