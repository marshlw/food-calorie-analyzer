import React, { useState } from 'react'
import { Droplet, Plus, Minus } from 'lucide-react'
import { CalorieRing } from './CalorieRing'
import { useDiary } from '../context/DiaryContext'
import { waterApi } from '../api/water'
import { WaterStatus } from '../types'
import { extractErrorMessage } from '../utils/errors'

interface Props {
  water?: WaterStatus | null
}

// Трекер воды: кольцо-инфографика (в стиле колец КБЖУ) + учёт по стаканам.
// Smart: сам пишет в API и обновляет день через DiaryContext.refreshDay.
export const WaterCard: React.FC<Props> = ({ water }) => {
  const { selectedDate, refreshDay } = useDiary()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const glassMl = water?.glass_ml || 250
  const totalMl = water?.total_ml ?? 0
  const goalMl = water?.goal_ml ?? null

  const glasses = Math.round(totalMl / glassMl)
  const goalGlasses = goalMl ? Math.ceil(goalMl / glassMl) : null
  const pctText = goalMl ? Math.round((totalMl / goalMl) * 100) : null

  // Ряд «стаканов»: заполненные = выпито, до нормы (или хотя бы до выпитого).
  const dotsCount = Math.min(goalGlasses ?? glasses, 12)

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
    <div className="card p-6 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Droplet className="h-5 w-5 text-cyan-500" />
        <h3 className="text-lg font-semibold">Вода</h3>
      </div>

      <div className="flex items-center gap-5">
        {/* Кольцо-инфографика */}
        <div className="relative grid place-items-center flex-shrink-0">
          <CalorieRing
            value={totalMl}
            goal={goalMl ?? 0}
            size={88}
            strokeWidth={8}
            colorClass="stroke-cyan-500"
          />
          <div className="absolute flex flex-col items-center leading-none">
            <span className="text-xl font-bold">{glasses}</span>
            {goalGlasses != null && (
              <span className="text-[11px] text-gray-500 dark:text-gray-400">
                из {goalGlasses}
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-2xl font-bold">
            {Math.round(totalMl)}
            {goalMl != null && (
              <span className="text-base font-normal text-gray-500 dark:text-gray-400">
                {' '}
                / {Math.round(goalMl)}
              </span>
            )}
            <span className="text-sm ml-1 text-gray-500 dark:text-gray-400">мл</span>
          </p>

          {pctText != null ? (
            <p className="text-xs text-gray-400 mt-0.5">{pctText}% от нормы</p>
          ) : (
            <p className="text-xs text-gray-400 mt-0.5">
              Заполните вес и активность в профиле, чтобы видеть норму.
            </p>
          )}

          {/* Стаканчики */}
          <div className="flex flex-wrap gap-1 mt-2">
            {Array.from({ length: dotsCount }).map((_, i) => (
              <Droplet
                key={i}
                className={`h-4 w-4 ${
                  i < glasses
                    ? 'text-cyan-500 fill-cyan-500'
                    : 'text-gray-300 dark:text-gray-600'
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-4">
        <button
          className="btn btn-secondary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => change(-glassMl)}
          disabled={busy || totalMl <= 0}
        >
          <Minus className="h-4 w-4" /> Стакан
        </button>
        <button
          className="btn btn-primary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => change(glassMl)}
          disabled={busy}
        >
          <Plus className="h-4 w-4" /> Стакан
        </button>
      </div>

      <p className="text-[11px] text-gray-400 text-center mt-2">
        1 стакан = {glassMl} мл
      </p>

      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
    </div>
  )
}
