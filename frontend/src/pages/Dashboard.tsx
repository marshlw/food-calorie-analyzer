import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppHeader } from '../components/Brand'
import { HeroCard } from '../components/HeroCard'
import { MealForm } from '../components/MealForm'
import { AnalysisFlow } from '../components/AnalysisFlow'
import { Modal } from '../components/Modal'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { useApi } from '../hooks/useApi'
import { useAiLimit } from '../hooks/useAiLimit'
import { useAuth } from '../hooks/useAuth'
import { mealsApi } from '../api/meals'
import { DailyLog, MealEntryCreate } from '../types'
import { MEAL_TYPE_META, kbjuLine } from '../utils/mealTypes'
import { Plus, Camera } from 'lucide-react'

type ModalKind = 'none' | 'manual' | 'photo'

// Приветствие по времени суток («Добрый день, Анна» из дизайна)
const greeting = (): string => {
  const h = new Date().getHours()
  if (h < 5) return 'Доброй ночи'
  if (h < 12) return 'Доброе утро'
  if (h < 18) return 'Добрый день'
  return 'Добрый вечер'
}

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [modal, setModal] = useState<ModalKind>('none')
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [successMessage, setSuccessMessage] = useState('')
  const { aiLimit, aiExhausted, refreshAiLimit } = useAiLimit()

  // Load daily log
  const { data: dailyLog, isLoading: isLoadingLog, execute: loadDailyLog } = useApi<DailyLog>()

  // Add meal (ручной ввод и подтверждение AI-анализа)
  const { isLoading: isAddingMeal, error: addMealError, execute: executeAddMeal } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Приём пищи добавлен!')
      setModal('none')
      setPhotoFile(null)
      loadDailyLog(() => mealsApi.getDailyLog())
      refreshAiLimit()
    },
  })

  useEffect(() => {
    loadDailyLog(() => mealsApi.getDailyLog())
  }, [])

  const handleAddMeal = async (data: MealEntryCreate): Promise<void> => {
    await executeAddMeal(() => mealsApi.addMeal(data))
  }

  const close = () => {
    setModal('none')
    setPhotoFile(null)
    // Загрузка фото расходует лимит даже без сохранения — обновляем счётчик
    refreshAiLimit()
  }

  const firstName = (user?.full_name || '').trim().split(' ')[0]

  return (
    <div className="max-w-md mx-auto px-5 pt-6 pb-32">
      <AppHeader />

      {/* Приветствие */}
      <div className="mb-5">
        <h1 className="font-display font-bold text-2xl tracking-tight">
          {greeting()}
          {firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="text-[13px] text-secondary mt-1 first-letter:capitalize">
          {new Date().toLocaleDateString('ru-RU', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
          })}
        </p>
      </div>

      {/* Alerts */}
      {successMessage && (
        <div className="mb-4">
          <SuccessAlert message={successMessage} onClose={() => setSuccessMessage('')} />
        </div>
      )}
      {addMealError && (
        <div className="mb-4">
          <ErrorAlert message={addMealError} onClose={() => {}} />
        </div>
      )}

      {/* Hero: кольцо калорий + макронутриенты */}
      {isLoadingLog ? (
        <LoadingSpinner message="Загрузка..." />
      ) : dailyLog ? (
        <HeroCard log={dailyLog} aiLimit={aiLimit} />
      ) : null}

      {/* Действия */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <button
          onClick={() => setModal('manual')}
          className="btn-primary flex items-center justify-center gap-2"
        >
          <Plus className="h-[18px] w-[18px]" />
          Добавить
        </button>
        <label
          className={`btn-secondary flex items-center justify-center gap-2 ${
            aiExhausted ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
        >
          <Camera className="h-[18px] w-[18px]" />
          Анализ фото
          <input
            type="file"
            accept="image/*"
            className="hidden"
            disabled={aiExhausted}
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) {
                setPhotoFile(f)
                setModal('photo')
              }
              e.target.value = ''
            }}
          />
        </label>
      </div>

      {aiExhausted && (
        <p className="text-xs text-tertiary text-center -mt-3 mb-6">
          ✦ Дневной лимит AI-анализов исчерпан — будет доступно завтра
        </p>
      )}

      {/* Сегодня */}
      <div className="flex items-baseline justify-between mb-3">
        <span className="section-title">Сегодня</span>
        <button
          onClick={() => navigate('/meals')}
          className="text-[13px] font-medium text-primary-500 dark:text-primary-400 hover:text-primary-700"
        >
          Все приёмы
        </button>
      </div>

      {dailyLog && dailyLog.meals.length > 0 ? (
        <div className="flex flex-col gap-2.5">
          {dailyLog.meals.map((meal) => {
            const meta = MEAL_TYPE_META[meal.meal_type]
            return (
              <div key={meal.id} className="card-tile px-4 py-3.5">
                <div className="flex items-center justify-between gap-2.5 mb-2">
                  <span className={`chip ${meta.chip}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                    {meta.label}
                  </span>
                  {meal.task_id && <span className="chip-ai">AI</span>}
                </div>
                <div className="text-[15px] font-semibold">{meal.food_name}</div>
                <div className="text-xs text-secondary mt-0.5">{kbjuLine(meal)}</div>
              </div>
            )
          })}
        </div>
      ) : (
        !isLoadingLog && (
          <div className="text-center py-8 text-secondary text-sm">
            Записей ещё нет — добавьте первый приём пищи или сделайте фото блюда.
          </div>
        )
      )}

      {/* Add Meal Modal (ручной) */}
      <Modal isOpen={modal === 'manual'} onClose={close} title="Добавить приём пищи">
        <MealForm onSubmit={handleAddMeal} isLoading={isAddingMeal} />
      </Modal>

      {/* Photo analysis Modal: фото → состав → КБЖУ → выбор приёма → сохранить */}
      <Modal isOpen={modal === 'photo'} onClose={close} title="Анализ по фото">
        {photoFile && (
          <AnalysisFlow
            file={photoFile}
            onConfirm={handleAddMeal}
            onCancel={close}
            saving={isAddingMeal}
          />
        )}
      </Modal>
    </div>
  )
}
