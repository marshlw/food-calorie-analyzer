import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { TaskResponse } from '../types'
import { tasksApi } from '../api/tasks'
import { mealsApi } from '../api/meals'
import { useApi } from '../hooks/useApi'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { Modal } from '../components/Modal'
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
  const {
    isLoading: isSubmittingFeedback,
    execute: executeSubmitFeedback,
  } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Спасибо за обратную связь!')
      setShowFeedbackModal(false)
      setFeedbackFood('')
      setFeedbackWeight('')
      loadTask(() => tasksApi.getTask(taskId!))
    },
  })

  // Add from analysis
  const {
    isLoading: isAdding,
    execute: executeAddFromAnalysis,
  } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Результат добавлен в дневник!')
      loadTask(() => tasksApi.getTask(taskId!))
    },
  })

  useEffect(() => {
    if (taskId) {
      loadTask(() => tasksApi.getTask(taskId))
    }
  }, [taskId])

  const handleSubmitFeedback = async () => {
    if (!taskId || !feedbackFood) return
    await executeSubmitFeedback(() =>
      tasksApi.submitFeedback(taskId, feedbackFood, parseFloat(feedbackWeight) || 0)
    )
  }

  const handleAddFromAnalysis = async (mealType: string) => {
    if (!taskId) return
    await executeAddFromAnalysis(() =>
      mealsApi.addMealFromAnalysis(taskId, mealType)
    )
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

      {loadError && (
        <div className="mb-4">
          <ErrorAlert message={loadError} onClose={() => {}} />
        </div>
      )}

      {/* Loading */}
      {isLoadingTask && <LoadingSpinner message="Загрузка..." />}

      {/* Task Details */}
      {task && !isLoadingTask && (
        <>
          {/* Status */}
          <div className="card p-4 mb-4 rounded-xl">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Статус</p>
            <p className="text-lg font-semibold">{getStatusLabel(task.status)}</p>
          </div>

          {/* Image Preview */}
          {task.image_path && (
            <div className="card overflow-hidden mb-4 rounded-xl">
              <img
                src={task.image_path}
                alt="Анализируемое изображение"
                className="w-full h-64 object-cover"
              />
            </div>
          )}

          {/* Analysis Result */}
          {task.result && (
            <div className="card p-4 mb-4 rounded-xl">
              <h2 className="font-semibold mb-4">Результаты анализа</h2>

              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 mb-4">
                <p className="text-sm text-gray-600 dark:text-gray-400">Определенное блюдо</p>
                <p className="text-lg font-semibold text-blue-600 dark:text-blue-400">
                  {task.result.food || task.result.food_name}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Калории</p>
                  <p className="font-semibold text-orange-600 dark:text-orange-400">
                    {task.result.calories} ккал
                  </p>
                </div>
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Вес</p>
                  <p className="font-semibold text-purple-600 dark:text-purple-400">
                    {task.result.weight_g}г
                  </p>
                </div>
                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Белки</p>
                  <p className="font-semibold text-red-600 dark:text-red-400">
                    {task.result.protein_g.toFixed(1)}г
                  </p>
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Жиры</p>
                  <p className="font-semibold text-yellow-600 dark:text-yellow-400">
                    {task.result.fat_g.toFixed(1)}г
                  </p>
                </div>
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                  <p className="text-gray-600 dark:text-gray-400 text-xs">Углеводы</p>
                  <p className="font-semibold text-green-600 dark:text-green-400">
                    {task.result.carbs_g.toFixed(1)}г
                  </p>
                </div>
              </div>

              {/* Add to Diary */}
              <div className="mt-4 space-y-2">
                <label className="block text-sm font-medium">Добавить в дневник как</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleAddFromAnalysis('breakfast')}
                    disabled={isAdding}
                    className="btn btn-secondary text-sm disabled:opacity-50"
                  >
                    🌅 Завтрак
                  </button>
                  <button
                    onClick={() => handleAddFromAnalysis('lunch')}
                    disabled={isAdding}
                    className="btn btn-secondary text-sm disabled:opacity-50"
                  >
                    🍽️ Обед
                  </button>
                  <button
                    onClick={() => handleAddFromAnalysis('dinner')}
                    disabled={isAdding}
                    className="btn btn-secondary text-sm disabled:opacity-50"
                  >
                    🌙 Ужин
                  </button>
                  <button
                    onClick={() => handleAddFromAnalysis('snack')}
                    disabled={isAdding}
                    className="btn btn-secondary text-sm disabled:opacity-50"
                  >
                    🍿 Закуска
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {task.error && (
            <div className="card p-4 mb-4 rounded-xl bg-red-50 dark:bg-red-900/20">
              <p className="text-red-600 dark:text-red-400 text-sm">{task.error}</p>
            </div>
          )}

          {/* Feedback Button */}
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
      <Modal
        isOpen={showFeedbackModal}
        onClose={() => setShowFeedbackModal(false)}
        title="Отправить исправление"
      >
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
              min="0"
              step="0.1"
              className="input"
            />
          </div>

          <button
            onClick={handleSubmitFeedback}
            disabled={isSubmittingFeedback || !feedbackFood}
            className="btn-primary w-full disabled:opacity-50"
          >
            {isSubmittingFeedback ? 'Отправка...' : 'Отправить'}
          </button>
        </div>
      </Modal>
    </div>
  )
}
