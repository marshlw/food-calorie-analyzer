import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppHeader } from '../components/Brand'
import { HeroCard } from '../components/HeroCard'
import { MealForm } from '../components/MealForm'
import { MealDetail } from '../components/MealDetail'
import { AnalysisFlow } from '../components/AnalysisFlow'
import { BarcodeFlow } from '../components/BarcodeFlow'
import { MealCard } from '../components/MealCard'
import { Modal } from '../components/Modal'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StreakCard } from '../components/goals/StreakCard'
import { useApi } from '../hooks/useApi'
import { useAiLimit } from '../hooks/useAiLimit'
import { useAuth } from '../hooks/useAuth'
import { useGoals } from '../hooks/useGoals'
import { mealsApi } from '../api/meals'
import { DailyLog, MealEntry, MealEntryCreate } from '../types'
import { UPLOAD_ACCEPT } from '../utils/image'
import { Plus, Camera, ScanBarcode } from 'lucide-react'

type ModalKind = 'none' | 'manual' | 'edit' | 'photo' | 'barcode' | 'view'

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
  const [viewing, setViewing] = useState<MealEntry | null>(null)
  const [editing, setEditing] = useState<MealEntry | null>(null)
  const [successMessage, setSuccessMessage] = useState('')
  const { aiLimit, aiExhausted, refreshAiLimit } = useAiLimit()
  // Серия и цель дня: карточка ведёт на «Приёмы → Путь».
  const { goals, refresh: refreshGoals } = useGoals()

  // Load daily log
  const { data: dailyLog, isLoading: isLoadingLog, execute: loadDailyLog } = useApi<DailyLog>()

  // Add meal (ручной ввод и подтверждение AI-анализа)
  const { isLoading: isAddingMeal, error: addMealError, execute: executeAddMeal } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Приём пищи добавлен!')
      setModal('none')
      setPhotoFile(null)
      loadDailyLog(() => mealsApi.getDailyLog())
      refreshGoals()
      refreshAiLimit()
    },
  })

  // Update meal
  const { isLoading: isUpdatingMeal, error: updateMealError, execute: executeUpdateMeal } =
    useApi<any>({
      onSuccess: () => {
        setSuccessMessage('Запись обновлена!')
        setModal('none')
        setEditing(null)
        loadDailyLog(() => mealsApi.getDailyLog())
        refreshGoals()
      },
    })

  // Delete meal
  const { isLoading: isDeletingMeal, error: deleteMealError, execute: executeDeleteMeal } =
    useApi<any>({
      onSuccess: () => {
        setSuccessMessage('Запись удалена!')
        loadDailyLog(() => mealsApi.getDailyLog())
        refreshGoals()
      },
    })

  useEffect(() => {
    loadDailyLog(() => mealsApi.getDailyLog())
  }, [])

  const handleAddMeal = async (data: MealEntryCreate): Promise<void> => {
    await executeAddMeal(() => mealsApi.addMeal(data))
  }

  const handleEditMeal = (meal: MealEntry) => {
    setEditing(meal)
    setModal('edit')
  }

  const handleUpdateMeal = async (data: MealEntryCreate): Promise<void> => {
    if (!editing) return
    await executeUpdateMeal(() => mealsApi.updateMeal(editing.id, data))
  }

  const handleDeleteMeal = (meal: MealEntry) => {
    if (window.confirm('Удалить запись?')) {
      executeDeleteMeal(() => mealsApi.deleteMeal(meal.id))
    }
  }

  const close = () => {
    setModal('none')
    setPhotoFile(null)
    setViewing(null)
    setEditing(null)
    // Загрузка фото расходует лимит даже без сохранения — обновляем счётчик
    refreshAiLimit()
  }

  // Открыть карточку приёма (просмотр с фото и разбивкой белка)
  const openView = (meal: MealEntry) => {
    setViewing(meal)
    setModal('view')
  }

  // Фото добавлено/удалено в просмотре — обновляем открытую карточку и день
  const handleViewedUpdated = (m: MealEntry) => {
    setViewing(m)
    loadDailyLog(() => mealsApi.getDailyLog())
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

      {/* Серия: кольцо недели + точки Пн–Вс, ведёт на «Приёмы → Путь» */}
      {goals && (
        <StreakCard goals={goals} onClick={() => navigate('/meals?tab=path')} />
      )}

      {/* Alerts */}
      {successMessage && (
        <div className="mb-4">
          <SuccessAlert message={successMessage} onClose={() => setSuccessMessage('')} />
        </div>
      )}
      {(addMealError || updateMealError || deleteMealError) && (
        <div className="mb-4">
          <ErrorAlert
            message={addMealError || updateMealError || deleteMealError || ''}
            onClose={() => {}}
          />
        </div>
      )}

      {/* Hero: кольцо калорий + макронутриенты */}
      {isLoadingLog ? (
        <LoadingSpinner message="Загрузка..." />
      ) : dailyLog ? (
        <HeroCard log={dailyLog} aiLimit={aiLimit} />
      ) : null}

      {/* Действия */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={() => setModal('manual')}
          className="btn-primary flex-1 flex items-center justify-center gap-2"
        >
          <Plus className="h-[18px] w-[18px]" />
          Добавить
        </button>
        <label
          className={`btn-secondary flex-1 flex items-center justify-center gap-2 ${
            aiExhausted ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
        >
          <Camera className="h-[18px] w-[18px]" />
          Анализ фото
          <input
            type="file"
            accept={UPLOAD_ACCEPT}
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
        {/* Сканер штрих-кода — квадратная кнопка, прижата к правому краю */}
        <button
          type="button"
          aria-label="Сканировать штрих-код"
          title="Добавить по штрих-коду"
          onClick={() => setModal('barcode')}
          className="btn-secondary flex-shrink-0 !px-3.5 flex items-center justify-center"
        >
          <ScanBarcode className="h-[20px] w-[20px]" />
        </button>
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
        <div>
          {dailyLog.meals.map((meal) => (
            <MealCard
              key={meal.id}
              meal={meal}
              showTypeChip
              onView={() => openView(meal)}
              onEdit={() => handleEditMeal(meal)}
              onDelete={() => handleDeleteMeal(meal)}
              isLoading={isDeletingMeal}
            />
          ))}
        </div>
      ) : (
        !isLoadingLog && (
          <div className="text-center py-8 text-secondary text-sm">
            Записей ещё нет — добавьте первый приём пищи или сделайте фото блюда.
          </div>
        )
      )}

      {/* Просмотр приёма пищи (фото, КБЖУ, разбивка белка, состав) */}
      <Modal isOpen={modal === 'view'} onClose={close} title="Запись о еде">
        {viewing && <MealDetail meal={viewing} onUpdated={handleViewedUpdated} />}
      </Modal>

      {/* Add Meal Modal (ручной) */}
      <Modal isOpen={modal === 'manual'} onClose={close} title="Добавить приём пищи">
        <MealForm onSubmit={handleAddMeal} isLoading={isAddingMeal} />
      </Modal>

      {/* Edit Meal Modal */}
      <Modal isOpen={modal === 'edit'} onClose={close} title="Редактировать">
        {editing && (
          <MealForm
            initialData={editing}
            onSubmit={handleUpdateMeal}
            isLoading={isUpdatingMeal}
            submitLabel="Сохранить"
          />
        )}
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

      {/* Barcode Modal: камера с рамкой → продукт → граммовка → сохранить */}
      <Modal isOpen={modal === 'barcode'} onClose={close} title="Блюдо по штрих-коду">
        {modal === 'barcode' && (
          <BarcodeFlow onConfirm={handleAddMeal} onCancel={close} saving={isAddingMeal} />
        )}
      </Modal>
    </div>
  )
}
