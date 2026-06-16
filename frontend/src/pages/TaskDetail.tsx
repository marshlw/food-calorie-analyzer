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
import { IngredientList } from '../components/IngredientList'
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

  // Префилл формы значениями анализа
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
      }
    : undefined

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold">Результат анализа</h1>
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
            <div className="card overflow-hidden mb-4 rounded-xl">
              <img
                src={task.image_path}
                alt="Анализируемое блюдо"
                className="w-full h-64 object-cover"
              />
            </div>
          )}

          {/* Status (для незавершённых) */}
          {task.status !== 'success' && (
            <div className="card p-4 mb-4 rounded-xl">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Статус</p>
              <p className="text-lg font-semibold">{getStatusLabel(task.status)}</p>
              {task.error && (
                <p className="text-red-600 dark:text-red-400 text-sm mt-2">{task.error}</p>
              )}
            </div>
          )}

          {/* Result */}
          {r && formInitial && (
            <div className="card p-4 mb-4 rounded-xl space-y-4">
              {/* Название + уверенность */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Определённое блюдо</p>
                  <p className="text-lg font-semibold">{r.food || r.food_name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">≈ {Math.round(r.weight_g)} г</p>
                </div>
                {confidencePct !== null && (
                  <span className="shrink-0 text-xs px-2 py-1 rounded-full bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400">
                    Уверенность {confidencePct}%
                  </span>
                )}
              </div>

              {/* КБЖУ сводка (что посчитал AI) */}
              <div className="grid grid-cols-4 gap-2 text-sm">
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-2">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">ккал</p>
                  <p className="font-semibold text-blue-600 dark:text-blue-400">{Math.round(r.calories)}</p>
                </div>
                <div className="bg-red-50 dark:bg-red-900/20 rounded p-2">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Белки</p>
                  <p className="font-semibold text-red-600 dark:text-red-400">{r.protein_g.toFixed(1)}</p>
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded p-2">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Жиры</p>
                  <p className="font-semibold text-yellow-600 dark:text-yellow-400">{r.fat_g.toFixed(1)}</p>
                </div>
                <div className="bg-green-50 dark:bg-green-900/20 rounded p-2">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Углев.</p>
                  <p className="font-semibold text-green-600 dark:text-green-400">{r.carbs_g.toFixed(1)}</p>
                </div>
              </div>

              {/* Состав */}
              {r.ingredients && r.ingredients.length > 0 && (
                <IngredientList ingredients={r.ingredients} />
              )}

              {/* Сохранение в дневник: редактируемые КБЖУ + выбор приёма */}
              <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
                <p className="text-sm font-medium mb-3">Добавить в дневник питания</p>
                <MealForm
                  initialData={formInitial}
                  onSubmit={handleSaveToDiary}
                  isLoading={isSaving}
                  submitLabel="Сохранить в дневник"
                />
              </div>
            </div>
          )}

          {/* Feedback */}
          {task.status === 'success' && (
            <button
              onClick={() => setShowFeedbackModal(true)}
              className="btn btn-secondary w-full flex items-center justify-center gap-2"
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
