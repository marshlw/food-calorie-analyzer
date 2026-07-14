import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { TaskResponse, MealEntry, MealEntryCreate } from '../types'
import { tasksApi } from '../api/tasks'
import { mealsApi } from '../api/meals'
import { useApi } from '../hooks/useApi'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { Modal } from '../components/Modal'
import { MealForm } from '../components/MealForm'
import { ingredientsToItems } from '../components/AnalysisFlow'
import { ArrowLeft, Send } from 'lucide-react'

export const TaskDetail: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [showFeedbackModal, setShowFeedbackModal] = useState(false)
  const [feedbackFood, setFeedbackFood] = useState('')
  const [feedbackWeight, setFeedbackWeight] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // Load task
  const {
    data: task,
    isLoading: isLoadingTask,
    error: loadError,
    execute: loadTask,
  } = useApi<TaskResponse>()

  // Submit feedback
  const { isLoading: isSubmittingFeedback, execute: executeSubmitFeedback } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Спасибо за обратную связь!')
      setShowFeedbackModal(false)
      setFeedbackFood('')
      setFeedbackWeight('')
    },
  })

  // Save to diary (с редактируемыми КБЖУ и выбором приёма)
  const { isLoading: isSaving, error: saveError, execute: executeSave } = useApi<MealEntry>({
    onSuccess: () => setSuccessMessage('Добавлено в дневник питания!'),
  })

  useEffect(() => {
    if (taskId) loadTask(() => tasksApi.getTask(taskId))
  }, [taskId])

  const handleSubmitFeedback = async () => {
    const weight = parseInt(feedbackWeight, 10)
    if (!taskId || !feedbackFood || !weight || weight <= 0) return
    await executeSubmitFeedback(() => tasksApi.submitFeedback(taskId, feedbackFood, weight))
  }

  // Сохранение в дневник: значения берём из формы, task_id => источник «AI»
  const handleSaveToDiary = async (data: MealEntryCreate): Promise<void> => {
    if (!taskId) return
    await executeSave(() => mealsApi.addMeal({ ...data, task_id: taskId }))
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pending':
        return '⏳ В ожидании'
      case 'processing':
        return '⚙️ Обработка'
      case 'success':
        return '✅ Успешно'
      case 'failure':
        return '❌ Ошибка'
      default:
        return status
    }
  }

  const r = task?.result
  const confidencePct = typeof r?.confidence === 'number' ? Math.round(r.confidence * 100) : null

  // Префилл формы значениями анализа: ингредиенты — редактируемые позиции
  const formInitial: MealEntry | undefined = r
    ? {
        id: 0,
        food_name: r.food || r.food_name || '',
        calories: r.calories,
        protein_g: r.protein_g,
        fat_g: r.fat_g,
        carbs_g: r.carbs_g,
        weight_g: r.weight_g,
        meal_type: 'lunch',
        created_at: '',
        items: ingredientsToItems(r),
      }
    : undefined

  return (
    <div className="max-w-md mx-auto px-5 pt-6 pb-32">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-6">
        <button
          onClick={() => navigate(-1)}
          aria-label="Назад"
          className="w-[38px] h-[38px] rounded-full bg-white dark:bg-chip-dark border border-line dark:border-line-dark flex items-center justify-center flex-shrink-0"
        >
          <ArrowLeft className="h-[18px] w-[18px]" />
        </button>
        <h1 className="font-display font-bold text-2xl tracking-tight">Результат анализа</h1>
      </div>

      {/* Alerts */}
      {successMessage && (
        <div className="mb-4">
          <SuccessAlert message={successMessage} onClose={() => setSuccessMessage('')} />
        </div>
      )}
      {(loadError || saveError) && (
        <div className="mb-4">
          <ErrorAlert message={loadError || saveError || ''} onClose={() => {}} />
        </div>
      )}

      {isLoadingTask && <LoadingSpinner message="Загрузка..." />}

      {task && !isLoadingTask && (
        <>
          {/* Image */}
          {task.image_path && (
            <div className="card overflow-hidden mb-4">
              <img
                src={task.image_path}
                alt="Анализируемое блюдо"
                className="w-full h-64 object-cover"
              />
            </div>
          )}

          {/* Status (для незавершённых) */}
          {task.status !== 'success' && (
            <div className="card p-4 mb-4">
              <p className="text-sm text-secondary mb-1">Статус</p>
              <p className="text-lg font-semibold">{getStatusLabel(task.status)}</p>
              {task.error && <p className="text-danger text-sm mt-2">{task.error}</p>}
            </div>
          )}

          {/* Result */}
          {r && formInitial && (
            <div className="card p-5 mb-4 space-y-4">
              {/* Название + уверенность */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-display font-bold text-[22px] tracking-tight leading-tight">
                    {r.food || r.food_name}
                  </p>
                  <p className="text-[13px] text-secondary mt-0.5">
                    ≈ {Math.round(r.weight_g)} г · распознано AI
                  </p>
                </div>
                {confidencePct !== null && (
                  <span className="chip-ai flex-shrink-0 font-medium">
                    ✦ Уверенность {confidencePct}%
                  </span>
                )}
              </div>

              {/* КБЖУ сводка (что посчитал AI) — цветные цифры из дизайна */}
              <div className="grid grid-cols-4 gap-2.5 text-center">
                <div>
                  <p className="font-display font-bold text-xl">{Math.round(r.calories)}</p>
                  <p className="text-[11px] text-tertiary mt-0.5">ккал</p>
                </div>
                <div>
                  <p className="font-display font-bold text-xl text-protein dark:text-protein-dark">
                    {Math.round(r.protein_g)}
                  </p>
                  <p className="text-[11px] text-tertiary mt-0.5">белки, г</p>
                </div>
                <div>
                  <p className="font-display font-bold text-xl text-fat dark:text-fat-dark">
                    {Math.round(r.fat_g)}
                  </p>
                  <p className="text-[11px] text-tertiary mt-0.5">жиры, г</p>
                </div>
                <div>
                  <p className="font-display font-bold text-xl text-carbs dark:text-carbs-dark">
                    {Math.round(r.carbs_g)}
                  </p>
                  <p className="text-[11px] text-tertiary mt-0.5">углев., г</p>
                </div>
              </div>

              {/* Сохранение в дневник: состав разобран на редактируемые блюда */}
              <div className="border-t border-divider dark:border-line-dark pt-4">
                <p className="text-[13px] font-semibold mb-3">Добавить в дневник питания</p>
                <MealForm
                  initialData={formInitial}
                  onSubmit={handleSaveToDiary}
                  isLoading={isSaving}
                  submitLabel="Добавить в дневник"
                />
              </div>
            </div>
          )}

          {/* Feedback */}
          {task.status === 'success' && (
            <button
              onClick={() => setShowFeedbackModal(true)}
              className="btn-outline w-full flex items-center justify-center gap-2"
            >
              <Send className="h-4 w-4" />
              Отправить исправление
            </button>
          )}
        </>
      )}

      {/* Feedback Modal */}
      <Modal isOpen={showFeedbackModal} onClose={() => setShowFeedbackModal(false)} title="Отправить исправление">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Правильное название</label>
            <input
              type="text"
              value={feedbackFood}
              onChange={(e) => setFeedbackFood(e.target.value)}
              placeholder="Введите правильное название"
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Правильный вес (г)</label>
            <input
              type="number"
              value={feedbackWeight}
              onChange={(e) => setFeedbackWeight(e.target.value)}
              placeholder="0"
              min="1"
              max="10000"
              step="1"
              className="input"
            />
          </div>
          <button
            onClick={handleSubmitFeedback}
            disabled={isSubmittingFeedback || !feedbackFood || !(parseInt(feedbackWeight, 10) > 0)}
            className="btn-primary w-full disabled:opacity-50"
          >
            {isSubmittingFeedback ? 'Отправка...' : 'Отправить'}
          </button>
        </div>
      </Modal>
    </div>
  )
}
