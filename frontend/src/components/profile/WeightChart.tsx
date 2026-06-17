import React, { useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { TrendingDown } from 'lucide-react'
import { WeightRecord } from '../../types'

type Range = 30 | 90 | 365 | 0 // дни, 0 = всё время

const RANGES: { label: string; value: Range }[] = [
  { label: '1М', value: 30 },
  { label: '3М', value: 90 },
  { label: '1Г', value: 365 },
  { label: 'Всё', value: 0 },
]

interface Props {
  data: WeightRecord[]
}

export const WeightChart: React.FC<Props> = ({ data }) => {
  const [range, setRange] = useState<Range>(90)

  const points = useMemo(() => {
    let rows = [...data].sort((a, b) => a.recorded_on.localeCompare(b.recorded_on))
    if (range !== 0) {
      const cutoff = new Date()
      cutoff.setDate(cutoff.getDate() - range)
      rows = rows.filter((r) => new Date(r.recorded_on) >= cutoff)
    }
    return rows.map((r) => ({
      date: new Date(r.recorded_on).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
      }),
      weight: r.weight_kg,
    }))
  }, [data, range])

  if (data.length === 0) {
    return (
      <div className="card p-8 rounded-xl text-center">
        <TrendingDown className="h-10 w-10 mx-auto text-gray-400 mb-3" />
        <p className="text-gray-600 dark:text-gray-400">
          Пока нет записей веса.
        </p>
        <p className="text-sm text-gray-500 mt-1">
          Добавьте первую запись — и здесь появится график прогресса.
        </p>
      </div>
    )
  }

  return (
    <div className="card p-4 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Динамика веса</h3>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setRange(r.value)}
              className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                range === r.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {points.length === 0 ? (
        <p className="py-12 text-center text-sm text-gray-500">
          Нет записей за выбранный период.
        </p>
      ) : (
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
              <XAxis dataKey="date" fontSize={11} tickMargin={6} />
              <YAxis
                domain={['dataMin - 2', 'dataMax + 2']}
                fontSize={11}
                unit=" кг"
                width={56}
              />
              <Tooltip formatter={(v: number) => [`${v} кг`, 'Вес']} />
              <Line
                type="monotone"
                dataKey="weight"
                stroke="rgb(34 197 94)"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
