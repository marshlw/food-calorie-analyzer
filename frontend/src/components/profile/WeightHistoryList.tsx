import React from 'react'
import { ArrowDown, ArrowUp, Minus, Pencil } from 'lucide-react'
import { WeightRecord } from '../../types'

interface Props {
  data: WeightRecord[]
  // Нажатие на запись открывает редактирование (там же — удаление).
  onEdit?: (record: WeightRecord) => void
}

const SOURCE_LABELS: Record<string, string> = {
  registration: 'регистрация',
  profile_edit: 'профиль',
  manual: 'вручную',
}

// Обхваты тела для компактных чипов под весом.
const MEASURE_CHIPS: { key: 'waist_cm' | 'chest_cm' | 'hips_cm' | 'shoulders_cm'; label: string }[] = [
  { key: 'waist_cm', label: 'Талия' },
  { key: 'chest_cm', label: 'Грудь' },
  { key: 'hips_cm', label: 'Бёдра' },
  { key: 'shoulders_cm', label: 'Плечи' },
]

export const WeightHistoryList: React.FC<Props> = ({ data, onEdit }) => {
  if (data.length === 0) return null

  // Сортируем по убыванию даты для списка и считаем дельту к предыдущей записи.
  const sorted = [...data].sort((a, b) => b.recorded_on.localeCompare(a.recorded_on))

  return (
    <div className="card overflow-hidden divide-y divide-divider dark:divide-line-dark">
      {sorted.map((rec, i) => {
        const prev = sorted[i + 1] // более ранняя по дате
        const delta = prev ? +(rec.weight_kg - prev.weight_kg).toFixed(1) : 0
        const chips = MEASURE_CHIPS.filter((c) => rec[c.key] != null)
        const deltaBadge = prev ? (
          <span
            className={`flex items-center gap-1 text-xs font-semibold ${
              delta < 0
                ? 'text-carbs dark:text-carbs-dark'
                : delta > 0
                ? 'text-protein dark:text-protein-dark'
                : 'text-faint dark:text-faint-dark'
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
        ) : (
          <span className="text-xs text-tertiary">старт</span>
        )

        const body = (
          <>
            <div className="min-w-0 text-left">
              <p className="text-sm font-semibold">{rec.weight_kg} кг</p>
              <p className="text-[11px] text-tertiary mt-0.5">
                {new Date(rec.recorded_on).toLocaleDateString('ru-RU', {
                  day: '2-digit',
                  month: 'long',
                })}
                {rec.note ? ` · ${rec.note}` : ''}
                {` · ${SOURCE_LABELS[rec.source] ?? rec.source}`}
              </p>
              {chips.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {chips.map((c) => (
                    <span
                      key={c.key}
                      className="inline-flex items-center gap-1 rounded-full bg-surface dark:bg-chip-dark px-2 py-0.5 text-[10px] text-secondary"
                    >
                      {c.label} {rec[c.key]} см
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {deltaBadge}
              {onEdit && <Pencil className="h-3.5 w-3.5 text-faint dark:text-faint-dark" />}
            </div>
          </>
        )

        return onEdit ? (
          <button
            key={rec.id}
            type="button"
            onClick={() => onEdit(rec)}
            className="w-full flex items-start justify-between px-5 py-3.5 text-left hover:bg-surface dark:hover:bg-chip-dark transition-colors"
          >
            {body}
          </button>
        ) : (
          <div key={rec.id} className="flex items-start justify-between px-5 py-3.5">
            {body}
          </div>
        )
      })}
    </div>
  )
}
