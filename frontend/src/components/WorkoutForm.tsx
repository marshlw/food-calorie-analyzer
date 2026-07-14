import React, { useState } from 'react'
import { WorkoutCreate, WorkoutType } from '../types'

interface Props {
  onSubmit: (data: WorkoutCreate) => Promise<void>
  isLoading?: boolean
}

const TYPES: { value: WorkoutType; label: string }[] = [
  { value: 'strength', label: 'Силовая' },
  { value: 'cardio', label: 'Кардио' },
  { value: 'stretching', label: 'Растяжка' },
  { value: 'sport', label: 'Спорт' },
  { value: 'other', label: 'Другое' },
]

// Форма записи тренировки (модалка «Записать» на вкладке «Тренировки»)
export const WorkoutForm: React.FC<Props> = ({ onSubmit, isLoading }) => {
  const [title, setTitle] = useState('')
  const [type, setType] = useState<WorkoutType>('strength')
  const [duration, setDuration] = useState('')
  const [calories, setCalories] = useState('')
  const [startedAt, setStartedAt] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const durationNum = parseFloat(duration)
    const caloriesNum = calories ? parseFloat(calories) : 0

    if (!title.trim()) {
      setError('Укажите название тренировки')
      return
    }
    if (!durationNum || durationNum <= 0) {
      setError('Длительность должна быть больше 0')
      return
    }
    if (caloriesNum < 0) {
      setError('Калории не могут быть отрицательными')
      return
    }

    setError('')
    try {
      await onSubmit({
        title: title.trim(),
        workout_type: type,
        duration_min: durationNum,
        calories_burned: caloriesNum,
        started_at: startedAt || undefined,
        description: description.trim() || undefined,
      })
    } catch {
      // Ошибку показывает родитель
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Тип тренировки — сегментированный выбор как в дизайне */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Тип тренировки</label>
        <div className="grid grid-cols-3 gap-2">
          {TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setType(t.value)}
              className={`py-2 text-[13px] rounded-xl transition-colors ${
                type === t.value
                  ? 'bg-primary-500 text-white font-semibold'
                  : 'text-muted dark:text-muted-dark font-medium bg-surface dark:bg-chip-dark hover:bg-primary-50'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Название</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Например: Верх тела"
          className="input"
          disabled={isLoading}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">Длительность, мин</label>
          <input
            type="number"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            placeholder="45"
            min="1"
            max="1440"
            step="1"
            className="input"
            disabled={isLoading}
          />
        </div>
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">Потрачено, ккал</label>
          <input
            type="number"
            value={calories}
            onChange={(e) => setCalories(e.target.value)}
            placeholder="320"
            min="0"
            max="10000"
            step="1"
            className="input"
            disabled={isLoading}
          />
        </div>
      </div>

      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Время начала (опц.)</label>
        <input
          type="time"
          value={startedAt}
          onChange={(e) => setStartedAt(e.target.value)}
          className="input"
          disabled={isLoading}
        />
      </div>

      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Заметка (опц.)</label>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Жим лёжа · Тяга в наклоне · Подтягивания"
          className="input"
          disabled={isLoading}
        />
      </div>

      {error && <p className="text-danger text-xs">{error}</p>}

      <button type="submit" disabled={isLoading} className="btn-primary w-full disabled:opacity-50">
        {isLoading ? 'Сохранение...' : 'Записать тренировку'}
      </button>
    </form>
  )
}
