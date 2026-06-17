import React from 'react'
import { ArrowDown, ArrowUp, Minus } from 'lucide-react'
import { WeightRecord } from '../../types'

interface Props {
  data: WeightRecord[]
}

const SOURCE_LABELS: Record<string, string> = {
  registration: 'регистрация',
  profile_edit: 'профиль',
  manual: 'вручную',
}

export const WeightHistoryList: React.FC<Props> = ({ data }) => {
  if (data.length === 0) return null

  // Сортируем по убыванию даты для списка и считаем дельту к предыдущей записи.
  const sorted = [...data].sort((a, b) => b.recorded_on.localeCompare(a.recorded_on))

  return (
    <div className="card rounded-xl divide-y divide-gray-100 dark:divide-gray-800">
      {sorted.map((rec, i) => {
        const prev = sorted[i + 1] // более ранняя по дате
        const delta = prev ? +(rec.weight_kg - prev.weight_kg).toFixed(1) : 0
        return (
          <div key={rec.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <p className="font-medium">{rec.weight_kg} кг</p>
              <p className="text-xs text-gray-500">
                {new Date(rec.recorded_on).toLocaleDateString('ru-RU', {
                  day: '2-digit',
                  month: 'long',
                  year: 'numeric',
                })}
                {rec.note ? ` · ${rec.note}` : ''}
                {` · ${SOURCE_LABELS[rec.source] ?? rec.source}`}
              </p>
            </div>
            {prev && (
              <span
                className={`flex items-center gap-1 text-sm ${
                  delta < 0
                    ? 'text-green-600 dark:text-green-400'
                    : delta > 0
                    ? 'text-red-600 dark:text-red-400'
                    : 'text-gray-400'
                }`}
              >
                {delta < 0 ? (
                  <ArrowDown className="h-3.5 w-3.5" />
                ) : delta > 0 ? (
                  <ArrowUp className="h-3.5 w-3.5" />
                ) : (
                  <Minus className="h-3.5 w-3.5" />
                )}
                {delta !== 0 ? `${Math.abs(delta)} кг` : '—'}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
