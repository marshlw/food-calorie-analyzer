import React, { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Workout, WorkoutCreate, WorkoutType, Exercise } from '../types'
import { ExercisePicker } from './ExercisePicker'

interface Props {
  onSubmit: (data: WorkoutCreate) => Promise<void>
  isLoading?: boolean
  // Режим редактирования: форма предзаполняется существующей тренировкой
  initialData?: Workout
  submitLabel?: string
}

const TYPES: { value: WorkoutType; label: string }[] = [
  { value: 'strength', label: 'Силовая' },
  { value: 'cardio', label: 'Кардио' },
  { value: 'stretching', label: 'Растяжка' },
  { value: 'sport', label: 'Спорт' },
  { value: 'other', label: 'Другое' },
]

const VALID_TYPES: WorkoutType[] = ['strength', 'cardio', 'stretching', 'sport', 'other']

// Строка конструктора: одно упражнение
interface Row {
  key: number
  name: string
  duration: string // мин
  calories: string // ккал
  kcalPerMin: number | null // из справочника — для авторасчёта при смене длительности
}

let rowKey = 1
const emptyRow = (): Row => ({ key: rowKey++, name: '', duration: '', calories: '', kcalPerMin: null })

const rowFrom = (name: string, durationMin: number, calories: number): Row => ({
  key: rowKey++,
  name,
  duration: String(Math.round(durationMin * 10) / 10),
  calories: String(Math.round(calories)),
  kcalPerMin: null,
})

// Предзаполнение конструктора при редактировании тренировки
const initRows = (w?: Workout): Row[] => {
  if (w?.items && w.items.length > 0) {
    return w.items.map((i) => rowFrom(i.name, i.duration_min, i.calories_burned))
  }
  if (w) return [rowFrom(w.title, w.duration_min, w.calories_burned)]
  return [emptyRow()]
}

// Конструктор тренировки: несколько упражнений в одной записи
// («жим лёжа 25 мин 150 ккал + становая 25 мин 150 ккал»).
// С initialData работает как форма редактирования.
export const WorkoutForm: React.FC<Props> = ({
  onSubmit,
  isLoading,
  initialData,
  submitLabel = 'Записать тренировку',
}) => {
  const [rows, setRows] = useState<Row[]>(() => initRows(initialData))
  const [type, setType] = useState<WorkoutType>(initialData?.workout_type || 'strength')
  const [title, setTitle] = useState(
    // Для простой записи название совпадает с упражнением — в поле не дублируем
    initialData && initialData.items && initialData.items.length > 0 ? initialData.title : ''
  )
  const [startedAt, setStartedAt] = useState(initialData?.started_at || '')
  const [description, setDescription] = useState(initialData?.description || '')
  const [error, setError] = useState('')

  const updateRow = (key: number, patch: Partial<Row>) => {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  }

  const handleRowDuration = (row: Row, value: string) => {
    const patch: Partial<Row> = { duration: value }
    const d = parseFloat(value)
    if (row.kcalPerMin && d > 0) {
      patch.calories = String(Math.round(row.kcalPerMin * d))
    }
    updateRow(row.key, patch)
  }

  // Выбор из базы: заполняет первую пустую строку или добавляет новую
  const handleExerciseSelect = (ex: Exercise) => {
    const duration = 30
    const newRow: Row = {
      key: rowKey++,
      name: ex.name,
      duration: String(duration),
      calories: String(Math.round(ex.kcal_per_min * duration)),
      kcalPerMin: ex.kcal_per_min,
    }
    setRows((prev) => {
      const emptyIdx = prev.findIndex((r) => !r.name.trim() && !r.duration && !r.calories)
      if (emptyIdx >= 0) {
        const next = [...prev]
        next[emptyIdx] = newRow
        return next
      }
      return [...prev, newRow]
    })
    // Тип тренировки — по первому выбранному упражнению
    if (VALID_TYPES.includes(ex.category)) setType((cur) => (rows.some((r) => r.name.trim()) ? cur : ex.category))
  }

  const removeRow = (key: number) => {
    setRows((prev) => (prev.length > 1 ? prev.filter((r) => r.key !== key) : prev))
  }

  const filledRows = rows.filter((r) => r.name.trim())
  const totalMin = filledRows.reduce((s, r) => s + (parseFloat(r.duration) || 0), 0)
  const totalKcal = filledRows.reduce((s, r) => s + (parseFloat(r.calories) || 0), 0)

  const autoTitle =
    filledRows.length > 0
      ? filledRows.map((r) => r.name.trim()).join(' + ').slice(0, 190)
      : ''

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (filledRows.length === 0) {
      setError('Добавьте хотя бы одно упражнение')
      return
    }
    for (const r of filledRows) {
      const d = parseFloat(r.duration)
      if (!d || d <= 0) {
        setError(`Укажите длительность: «${r.name.trim()}»`)
        return
      }
      if ((parseFloat(r.calories) || 0) < 0) {
        setError('Калории не могут быть отрицательными')
        return
      }
    }

    setError('')
    const items = filledRows.map((r) => ({
      name: r.name.trim(),
      duration_min: parseFloat(r.duration),
      calories_burned: parseFloat(r.calories) || 0,
    }))

    const finalTitle = (title.trim() || autoTitle || 'Тренировка').slice(0, 200)

    try {
      if (items.length === 1) {
        // Простая тренировка — без вложенных позиций
        await onSubmit({
          title: finalTitle,
          workout_type: type,
          duration_min: items[0].duration_min,
          calories_burned: items[0].calories_burned,
          started_at: startedAt || undefined,
          description: description.trim() || undefined,
        })
      } else {
        await onSubmit({
          title: finalTitle,
          workout_type: type,
          duration_min: 0, // итоги пересчитает бэкенд из items
          calories_burned: 0,
          items,
          started_at: startedAt || undefined,
          description: description.trim() || undefined,
        })
      }
    } catch {
      // Ошибку показывает родитель
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Поиск в базе упражнений (~60 шт. с ккал/мин): выбор добавляет строку */}
      <ExercisePicker onSelect={handleExerciseSelect} clearOnSelect />

      {/* Конструктор упражнений */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Упражнения</label>
        <div className="flex flex-col gap-2">
          {rows.map((row, i) => (
            <div
              key={row.key}
              className="rounded-tile border border-line dark:border-line-dark bg-surface dark:bg-chip-dark/50 p-3"
            >
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="text"
                  value={row.name}
                  onChange={(e) => updateRow(row.key, { name: e.target.value, kcalPerMin: null })}
                  placeholder={`Упражнение ${i + 1} (например: Жим лёжа)`}
                  className="input flex-1 !py-2 text-sm"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => removeRow(row.key)}
                  disabled={rows.length <= 1 || isLoading}
                  aria-label="Убрать упражнение"
                  className="p-1.5 rounded-lg text-faint dark:text-faint-dark hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-30 flex-shrink-0"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    value={row.duration}
                    onChange={(e) => handleRowDuration(row, e.target.value)}
                    placeholder="мин"
                    min="1"
                    max="1440"
                    step="1"
                    className="input !py-2 text-sm"
                    disabled={isLoading}
                  />
                  <span className="text-[10px] text-tertiary ml-1">минут</span>
                </div>
                <div>
                  <input
                    type="number"
                    value={row.calories}
                    onChange={(e) => updateRow(row.key, { calories: e.target.value })}
                    placeholder="ккал"
                    min="0"
                    max="10000"
                    step="1"
                    className="input !py-2 text-sm"
                    disabled={isLoading}
                  />
                  <span className="text-[10px] text-tertiary ml-1">
                    ккал{row.kcalPerMin ? ' · авто' : ''}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, emptyRow()])}
          disabled={isLoading}
          className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary-500 dark:text-primary-400 hover:text-primary-700"
        >
          <Plus className="h-3.5 w-3.5" /> Добавить упражнение
        </button>
      </div>

      {/* Итого по тренировке */}
      {filledRows.length > 0 && (
        <div className="flex justify-between items-center px-4 py-3 rounded-tile bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400">
          <span className="text-[13px] font-semibold">
            Итого · {filledRows.length}{' '}
            {filledRows.length === 1 ? 'упражнение' : filledRows.length < 5 ? 'упражнения' : 'упражнений'}
          </span>
          <span className="text-[13px] font-bold">
            {Math.round(totalMin)} мин · {Math.round(totalKcal)} ккал
          </span>
        </div>
      )}

      {/* Тип тренировки */}
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
        <label className="block text-[13px] font-semibold mb-1.5">Название тренировки (опц.)</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={autoTitle || 'Например: Верх тела'}
          className="input"
          disabled={isLoading}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
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
            placeholder="Как прошло?"
            className="input"
            disabled={isLoading}
          />
        </div>
      </div>

      {error && <p className="text-danger text-xs">{error}</p>}

      <button type="submit" disabled={isLoading} className="btn-primary w-full disabled:opacity-50">
        {isLoading ? 'Сохранение...' : submitLabel}
      </button>
    </form>
  )
}
