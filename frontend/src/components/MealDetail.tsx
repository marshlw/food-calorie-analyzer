import React, { useRef, useState } from 'react'
import { Camera, Trash2 } from 'lucide-react'
import { MealEntry } from '../types'
import { mealsApi } from '../api/meals'
import { API_BASE_URL } from '../api/axios'
import { MEAL_TYPE_META, kbjuLine } from '../utils/mealTypes'
import { capitalize as cap } from '../utils/text'
import { extractErrorMessage } from '../utils/errors'
import { ProteinBreakdown } from './ProteinBreakdown'

interface Props {
  meal: MealEntry
  // Вызывается после загрузки/удаления фото — родитель обновляет
  // запись в состоянии (и, при желании, перезагружает день).
  onUpdated: (meal: MealEntry) => void
}

// Просмотр записи приёма пищи: фото (своё или из AI-анализа), тип приёма,
// КБЖУ, состав. Здесь же можно добавить/заменить/удалить фото.
export const MealDetail: React.FC<Props> = ({ meal, onUpdated }) => {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement | null>(null)

  const meta = MEAL_TYPE_META[meal.meal_type]
  const photoSrc = meal.photo_url ? `${API_BASE_URL}${meal.photo_url}` : null

  const handleFile = async (file: File) => {
    setBusy(true)
    setError('')
    try {
      const updated = await mealsApi.uploadMealPhoto(meal.id, file)
      onUpdated(updated)
    } catch (e) {
      setError(extractErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const handleDeletePhoto = async () => {
    if (!window.confirm('Удалить фото?')) return
    setBusy(true)
    setError('')
    try {
      const updated = await mealsApi.deleteMealPhoto(meal.id)
      onUpdated(updated)
    } catch (e) {
      setError(extractErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const recordedAt = meal.created_at
    ? new Date(meal.created_at).toLocaleString('ru-RU', {
        day: 'numeric',
        month: 'long',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null

  return (
    <div className="space-y-4">
      {/* Фото записи: своё или автоматически из AI-анализа */}
      {photoSrc ? (
        <div className="relative">
          <img
            src={photoSrc}
            alt={meal.food_name}
            className="w-full max-h-64 object-cover rounded-tile border border-line dark:border-line-dark"
          />
          <div className="absolute top-2 right-2 flex gap-1.5">
            {meal.photo_source === 'ai' && <span className="chip-ai">Фото AI-анализа</span>}
            {meal.photo_source === 'user' && (
              <button
                type="button"
                onClick={handleDeletePhoto}
                disabled={busy}
                aria-label="Удалить фото"
                className="p-1.5 rounded-lg bg-white/85 dark:bg-card-dark/85 text-danger hover:bg-danger/10 transition-colors disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="w-full py-8 rounded-tile border border-dashed border-line dark:border-line-dark text-center text-sm text-tertiary">
          У этой записи пока нет фото
        </div>
      )}

      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
        className="btn-secondary w-full flex items-center justify-center gap-2 disabled:opacity-50"
      >
        <Camera className="h-[18px] w-[18px]" />
        {busy ? 'Загрузка...' : photoSrc ? 'Заменить фото' : 'Добавить фото'}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) handleFile(f)
          e.target.value = '' // позволяет выбрать тот же файл повторно
        }}
      />

      {error && <p className="text-danger text-xs">{error}</p>}

      {/* Заголовок записи */}
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <span className={`chip ${meta.chip}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
            {meta.label}
          </span>
          {meal.task_id && <span className="chip-ai">AI</span>}
        </div>
        <div className="text-lg font-display font-bold">{cap(meal.food_name)}</div>
        <div className="text-xs text-secondary mt-0.5">
          {Math.round(meal.weight_g)} г · {kbjuLine(meal)}
        </div>
        {recordedAt && <div className="text-[11px] text-tertiary mt-1">Записано: {recordedAt}</div>}
      </div>

      {/* КБЖУ крупно */}
      <div className="grid grid-cols-4 gap-2.5 text-center px-4 py-3 rounded-tile bg-surface dark:bg-chip-dark/50 border border-line dark:border-line-dark">
        <div>
          <p className="font-display font-bold text-base">{Math.round(meal.calories)}</p>
          <p className="text-[11px] text-tertiary">ккал</p>
        </div>
        <div>
          <p className="font-display font-bold text-base text-protein dark:text-protein-dark">
            {Math.round(meal.protein_g)}
          </p>
          <p className="text-[11px] text-tertiary">белки</p>
        </div>
        <div>
          <p className="font-display font-bold text-base text-fat dark:text-fat-dark">
            {Math.round(meal.fat_g)}
          </p>
          <p className="text-[11px] text-tertiary">жиры</p>
        </div>
        <div>
          <p className="font-display font-bold text-base text-carbs dark:text-carbs-dark">
            {Math.round(meal.carbs_g)}
          </p>
          <p className="text-[11px] text-tertiary">углев.</p>
        </div>
      </div>

      {/* Разбивка белка приёма по источнику (доля животного/растительного) */}
      {((meal.protein_animal_g ?? 0) > 0 || (meal.protein_plant_g ?? 0) > 0) && (
        <div className="px-4 py-3 rounded-tile bg-surface dark:bg-chip-dark/50 border border-line dark:border-line-dark">
          <ProteinBreakdown
            heading="Белок по источнику"
            animal={meal.protein_animal_g ?? 0}
            plant={meal.protein_plant_g ?? 0}
            totalProtein={meal.protein_g}
          />
        </div>
      )}

      {/* Блюда составного приёма */}
      {meal.items && meal.items.length > 1 && (
        <div>
          <div className="text-[13px] font-semibold mb-1.5">Состав</div>
          <div className="flex flex-col gap-1">
            {meal.items.map((item, idx) => (
              <div key={item.id ?? idx} className="flex justify-between items-baseline text-xs">
                <span className="text-secondary truncate pr-2">{cap(item.food_name)}</span>
                <span className="text-tertiary flex-shrink-0">
                  {Math.round(item.weight_g)} г · {Math.round(item.calories)} ккал
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
