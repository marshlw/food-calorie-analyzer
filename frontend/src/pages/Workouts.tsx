import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { AppHeader } from '../components/Brand'
import { Modal } from '../components/Modal'
import { WorkoutForm } from '../components/WorkoutForm'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { useApi } from '../hooks/useApi'
import { workoutsApi } from '../api/workouts'
import { WorkoutsResponse, Workout, WorkoutCreate, WorkoutType } from '../types'
import { toISODate, WEEKDAY_LABELS } from '../utils/dates'

// Стили чипов типов тренировок (из дизайна 3b)
const TYPE_META: Record<WorkoutType, { label: string; chip: string; dot: string }> = {
  strength: {
    label: 'Силовая',
    chip: 'bg-primary-50 text-primary-500 dark:bg-chip-dark dark:text-primary-400',
    dot: 'bg-primary-500 dark:bg-primary-400',
  },
  cardio: {
    label: 'Кардио',
    chip: 'bg-carbs-chip text-carbs-text dark:bg-carbs-dark/15 dark:text-carbs-dark',
    dot: 'bg-carbs dark:bg-carbs-dark',
  },
  stretching: {
    label: 'Растяжка',
    chip: 'bg-water-chip text-water dark:bg-water/15 dark:text-water',
    dot: 'bg-water',
  },
  sport: {
    label: 'Спорт',
    chip: 'bg-protein-chip text-protein-text dark:bg-protein-dark/15 dark:text-protein-dark',
    dot: 'bg-protein dark:bg-protein-dark',
  },
  other: {
    label: 'Другое',
    chip: 'bg-dinner-chip text-dinner dark:bg-dinner-dark/15 dark:text-dinner-dark',
    dot: 'bg-dinner dark:bg-dinner-dark',
  },
}

const formatDuration = (min: number): string => {
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}`
  return `${m} мин`
}

export const Workouts: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState(() => toISODate(new Date()))
  const [modalOpen, setModalOpen] = useState(false)
  const [toast, setToast] = useState('')

  const { data, isLoading, error, execute: load } = useApi<WorkoutsResponse>()

  const refresh = (dateStr: string) =>
    load(() => workoutsApi.getWorkouts(dateStr)).catch(() => {
      // Ошибка уже показана через error
    })

  useEffect(() => {
    refresh(selectedDate)
  }, [selectedDate]) // eslint-disable-line react-hooks/exhaustive-deps

  const add = useApi<Workout>({
    onSuccess: () => {
      setToast('Тренировка записана!')
      setModalOpen(false)
      refresh(selectedDate)
    },
  })

  const del = useApi<{ status: string }>({
    onSuccess: () => {
      setToast('Тренировка удалена')
      refresh(selectedDate)
    },
  })

  const handleAdd = async (payload: WorkoutCreate): Promise<void> => {
    await add.execute(() => workoutsApi.addWorkout({ ...payload, date: selectedDate }))
  }

  const handleDelete = (w: Workout) => {
    if (window.confirm('Удалить тренировку?')) {
      del.execute(() => workoutsApi.deleteWorkout(w.id)).catch(() => {
        // Ошибка уже показана через del.error
      })
    }
  }

  const summary = data?.summary
  const isToday = selectedDate === toISODate(new Date())
  const dateTitle = new Date(selectedDate).toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <div className="max-w-md mx-auto px-5 pt-6 pb-32">
      <AppHeader />

      {/* Заголовок + кнопка «Записать» */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="font-display font-bold text-2xl tracking-tight">Тренировки</h1>
          <p className="text-[13px] text-secondary mt-1 first-letter:capitalize">{dateTitle}</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-semibold rounded-full bg-primary-500 text-white hover:bg-primary-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" /> Записать
        </button>
      </div>

      {toast && (
        <div className="mb-4">
          <SuccessAlert message={toast} onClose={() => setToast('')} />
        </div>
      )}
      {(error || add.error || del.error) && (
        <div className="mb-4">
          <ErrorAlert message={error || add.error || del.error || ''} onClose={() => {}} />
        </div>
      )}

      {isLoading && !data && <LoadingSpinner message="Загрузка тренировок..." />}

      {data && summary && (
        <>
          {/* Сводка активности */}
          <div className="card p-5 mb-4">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <div className="font-display font-bold text-[22px]">
                  {Math.round(summary.total_calories_burned)}
                </div>
                <div className="text-[11px] text-tertiary mt-0.5">ккал потрачено</div>
              </div>
              <div className="border-x border-track dark:border-track-dark">
                <div className="font-display font-bold text-[22px]">
                  {formatDuration(summary.total_duration_min)}
                </div>
                <div className="text-[11px] text-tertiary mt-0.5">время</div>
              </div>
              <div>
                <div className="font-display font-bold text-[22px]">{summary.count}</div>
                <div className="text-[11px] text-tertiary mt-0.5">
                  {summary.count === 1 ? 'тренировка' : 'тренировки'}
                </div>
              </div>
            </div>
            {summary.adjusted_calorie_target != null && (
              <div className="mt-4 pt-3.5 border-t border-track dark:border-track-dark flex justify-between items-center gap-2">
                <span className="text-xs text-secondary">Баланс дня с учётом активности</span>
                <span className="text-[13px] font-semibold text-carbs-text dark:text-carbs-dark">
                  +{Math.round(summary.total_calories_burned)} к норме →{' '}
                  {summary.adjusted_calorie_target} ккал
                </span>
              </div>
            )}
          </div>

          {/* Неделя */}
          <div className="grid grid-cols-7 gap-1.5 mb-6">
            {data.week.map((day, i) => {
              const selected = day.date === selectedDate
              return (
                <button
                  key={day.date}
                  onClick={() => setSelectedDate(day.date)}
                  className={`rounded-cell py-2.5 pb-2 flex flex-col items-center gap-1 border transition-colors ${
                    selected
                      ? 'bg-primary-500 border-primary-500 shadow-day text-white'
                      : 'bg-white dark:bg-card-dark border-line dark:border-line-dark'
                  }`}
                >
                  <span className={`text-[10px] ${selected ? 'text-white/70' : 'text-tertiary'}`}>
                    {WEEKDAY_LABELS[i]}
                  </span>
                  <span className="text-[15px] font-semibold">
                    {new Date(day.date).getDate()}
                  </span>
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      day.has_workout
                        ? selected
                          ? 'bg-white'
                          : 'bg-primary-500 dark:bg-primary-400'
                        : 'bg-track dark:bg-track-dark'
                    }`}
                  />
                </button>
              )
            })}
          </div>

          {/* Список тренировок */}
          <div className="section-title mb-3">{isToday ? 'Сегодня' : 'Тренировки за день'}</div>
          {data.workouts.length === 0 ? (
            <div className="text-center py-8 text-secondary text-sm mb-6">
              Тренировок пока нет — нажмите «Записать», чтобы добавить первую.
            </div>
          ) : (
            <div className="flex flex-col gap-2.5 mb-6">
              {data.workouts.map((w) => {
                const meta = TYPE_META[w.workout_type] ?? TYPE_META.other
                return (
                  <div key={w.id} className="card-tile p-4">
                    <div className="flex items-center justify-between gap-2.5 mb-2">
                      <span className={`chip ${meta.chip}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                        {meta.label}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-tertiary">
                          {w.started_at ? `${w.started_at} · ` : ''}
                          {formatDuration(w.duration_min)}
                        </span>
                        <button
                          onClick={() => handleDelete(w)}
                          disabled={del.isLoading}
                          aria-label="Удалить тренировку"
                          className="p-1 rounded-lg text-faint hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                    <div className="text-[15px] font-semibold">{w.title}</div>
                    {w.description && (
                      <div className="text-xs text-secondary mt-0.5">{w.description}</div>
                    )}
                    {/* Упражнения составной тренировки */}
                    {w.items && w.items.length > 0 && (
                      <div className="mt-2 flex flex-col gap-1">
                        {w.items.map((item, idx) => (
                          <div
                            key={item.id ?? idx}
                            className="flex justify-between items-baseline text-xs"
                          >
                            <span className="text-secondary truncate pr-2">{item.name}</span>
                            <span className="text-tertiary flex-shrink-0">
                              {Math.round(item.duration_min)} мин ·{' '}
                              {Math.round(item.calories_burned)} ккал
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="flex justify-between items-center mt-2.5 pt-2.5 border-t border-divider dark:border-line-dark">
                      <span className="text-xs text-secondary">Потрачено</span>
                      <span className="text-[13px] font-bold">
                        {Math.round(w.calories_burned)} ккал
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* AI-советчик: тёмная градиентная карточка из дизайна */}
          <div className="rounded-card p-5 text-[#eef1f7] bg-gradient-to-br from-ink to-[#1a2942]">
            <span className="chip bg-primary-400/15 text-primary-400 mb-2.5">✦ AI-советчик</span>
            <div className="text-sm leading-relaxed">
              Советы по питанию и восстановлению с учётом ваших тренировок — в AI-советчике.
            </div>
            <div className="flex gap-2 mt-3.5">
              <Link
                to="/advisor"
                className="px-3.5 py-2 rounded-full bg-white/10 text-xs font-semibold hover:bg-white/20 transition-colors"
              >
                Подробнее
              </Link>
            </div>
          </div>
        </>
      )}

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Записать тренировку">
        <WorkoutForm onSubmit={handleAdd} isLoading={add.isLoading} />
      </Modal>
    </div>
  )
}
