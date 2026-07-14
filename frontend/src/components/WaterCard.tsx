import React, { useState } from 'react'
import { Droplet, Plus, Minus } from 'lucide-react'
import { useDiary } from '../context/DiaryContext'
import { waterApi } from '../api/water'
import { WaterStatus } from '../types'
import { extractErrorMessage } from '../utils/errors'

interface Props {
  water?: WaterStatus | null
}

// Трекер воды из дизайна Rasify: иконка-капля в голубой плитке, прогресс-бар
// «1500 / 2000 мл» и круглые кнопки −/+ (один стакан).
// Smart: сам пишет в API и обновляет день через DiaryContext.refreshDay.
export const WaterCard: React.FC<Props> = ({ water }) => {
  const { selectedDate, refreshDay } = useDiary()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const glassMl = water?.glass_ml || 250
  const totalMl = water?.total_ml ?? 0
  const goalMl = water?.goal_ml ?? null
  const pct = goalMl ? Math.min((totalMl / goalMl) * 100, 100) : 0

  const change = async (deltaMl: number) => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await waterApi.updateWater(deltaMl, selectedDate)
      await refreshDay(selectedDate)
    } catch (e) {
      setError(extractErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card px-5 py-4 mb-6">
      <div className="flex items-center gap-3.5">
        {/* Иконка */}
        <div className="w-11 h-11 rounded-cell bg-water-chip dark:bg-water/15 flex items-center justify-center flex-shrink-0">
          <Droplet className="h-5 w-5 text-water" strokeWidth={2} />
        </div>

        {/* Прогресс */}
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-baseline mb-1.5">
            <span className="text-sm font-semibold">Вода</span>
            <span className="text-[13px] text-secondary">
              {Math.round(totalMl)}
              {goalMl != null ? ` / ${Math.round(goalMl)}` : ''} мл
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-track dark:bg-track-dark overflow-hidden">
            <div className="h-1.5 rounded-full bg-water" style={{ width: `${pct}%` }} />
          </div>
        </div>

        {/* Кнопки −/+ */}
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={() => change(-glassMl)}
            disabled={busy || totalMl <= 0}
            aria-label="Убрать стакан"
            className="w-9 h-9 rounded-full border border-line dark:border-line-dark text-muted dark:text-muted-dark flex items-center justify-center hover:bg-surface dark:hover:bg-chip-dark transition-colors disabled:opacity-40"
          >
            <Minus className="h-4 w-4" />
          </button>
          <button
            onClick={() => change(glassMl)}
            disabled={busy}
            aria-label="Добавить стакан"
            className="w-9 h-9 rounded-full bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400 flex items-center justify-center hover:bg-primary-100 transition-colors disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </div>

      {goalMl == null && (
        <p className="text-[11px] text-tertiary mt-2">
          Заполните вес и активность в профиле, чтобы видеть норму. 1 стакан = {glassMl} мл.
        </p>
      )}
      {error && <p className="text-xs text-danger mt-2">{error}</p>}
    </div>
  )
}
