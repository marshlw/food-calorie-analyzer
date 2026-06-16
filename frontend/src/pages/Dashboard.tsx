import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { DailyStats } from '../components/DailyStats'
import { MealForm } from '../components/MealForm'
import { Modal } from '../components/Modal'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { useApi } from '../hooks/useApi'
import { mealsApi } from '../api/meals'
import { tasksApi } from '../api/tasks'
import { DailyLog, MealEntryCreate } from '../types'
import { Plus, Camera, History } from 'lucide-react'

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [showMealModal, setShowMealModal] = useState(false)
  const [showAnalysisResult, setShowAnalysisResult] = useState(false)
  const [analysisTask, setAnalysisTask] = useState<any>(null)
  const [successMessage, setSuccessMessage] = useState('')

  // Load daily log
  const { data: dailyLog, isLoading: isLoadingLog, execute: loadDailyLog } = useApi<DailyLog>()

  // Add meal
  const {
    isLoading: isAddingMeal,
    error: addMealError,
    execute: executeAddMeal,
  } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Прием пищи добавлен!')
      setShowMealModal(false)
      loadDailyLog(() => mealsApi.getDailyLog())
    },
  })

  // Upload image
  const { isLoading: isUploading, error: uploadError, execute: executeUpload } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Анализ запущен, подождите...')
    },
  })

  // Add meal from analysis
  const {
    isLoading: isAddingFromAnalysis,
    error: analysisError,
    execute: executeAddFromAnalysis,
  } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Результат анализа добавлен в дневник!')
      setShowAnalysisResult(false)
      setAnalysisTask(null)
      loadDailyLog(() => mealsApi.getDailyLog())
    },
  })

  useEffect(() => {
    loadDailyLog(() => mealsApi.getDailyLog())
  }, [])

  const handleAddMeal = async (data: MealEntryCreate) => {
    await executeAddMeal(() => mealsApi.addMeal(data))
  }

  const handleUploadImage = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const task = await executeUpload(() => tasksApi.uploadImage(file))
      setAnalysisTask(task)
      
      // Poll for task completion
      pollTaskStatus(task.id)
    } catch {
      // Error is handled
    }
  }

  const pollTaskStatus = async (taskId: string, attempts = 0) => {
    if (attempts > 120) {
      // 2 minutes timeout
      return
    }

    try {
      const task = await tasksApi.getTask(taskId)
      setAnalysisTask(task)

      if (task.status === 'success') {
        setShowAnalysisResult(true)
        setSuccessMessage('Анализ завершен!')
      } else if (task.status === 'failure') {
        setShowAnalysisResult(false)
      } else {
        // Continue polling
        setTimeout(() => pollTaskStatus(taskId, attempts + 1), 1000)
      }
    } catch {
      // Continue polling on error
      setTimeout(() => pollTaskStatus(taskId, attempts + 1), 1000)
    }
  }

  const handleAddFromAnalysis = async (mealType: string) => {
    if (!analysisTask) return
    await executeAddFromAnalysis(() =>
      mealsApi.addMealFromAnalysis(analysisTask.id, mealType)
    )
  }

  const handleViewHistory = () => {
    navigate('/analysis-history')
  }

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Ваш дневник</h1>
        <p className="text-gray-600 dark:text-gray-400">
          {new Date().toLocaleDateString('ru-RU', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Alerts */}
      {successMessage && (
        <div className="mb-4">
          <SuccessAlert message={successMessage} onClose={() => setSuccessMessage('')} />
        </div>
      )}

      {(addMealError || uploadError || analysisError) && (
        <div className="mb-4">
          <ErrorAlert
            message={addMealError || uploadError || analysisError || ''}
            onClose={() => {}}
          />
        </div>
      )}

      {/* Daily Stats */}
      {isLoadingLog ? (
        <LoadingSpinner message="Загрузка..." />
      ) : dailyLog ? (
        <DailyStats log={dailyLog} />
      ) : null}

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <button
          onClick={() => setShowMealModal(true)}
          className="btn btn-primary flex items-center justify-center gap-2"
        >
          <Plus className="h-5 w-5" />
          Добавить
        </button>
        <label className="btn btn-secondary flex items-center justify-center gap-2 cursor-pointer">
          <Camera className="h-5 w-5" />
          Анализ фото
          <input
            type="file"
            accept="image/*"
            onChange={handleUploadImage}
            disabled={isUploading}
            className="hidden"
            capture="environment"
          />
        </label>
      </div>

      <button
        onClick={handleViewHistory}
        className="btn btn-secondary w-full flex items-center justify-center gap-2 mb-6"
      >
        <History className="h-5 w-5" />
        История анализов
      </button>

      {/* Meals List */}
      {dailyLog && dailyLog.meals.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Приемы пищи</h2>
          {/* Meals are displayed in MealDiary page, here just show preview */}
          <div className="text-center py-4 text-gray-600 dark:text-gray-400">
            <p>Всего приемов пищи: {dailyLog.meals.length}</p>
            <button
              onClick={() => navigate('/meals')}
              className="text-primary-600 dark:text-primary-400 hover:underline text-sm mt-2"
            >
              Посмотреть детали
            </button>
          </div>
        </div>
      )}

      {/* Add Meal Modal */}
      <Modal
        isOpen={showMealModal}
        onClose={() => setShowMealModal(false)}
        title="Добавить прием пищи"
      >
        <MealForm onSubmit={handleAddMeal} isLoading={isAddingMeal} />
      </Modal>

      {/* Analysis Result Modal */}
      <Modal
        isOpen={showAnalysisResult && analysisTask?.result}
        onClose={() => setShowAnalysisResult(false)}
        title="Результат анализа"
      >
        {analysisTask?.result && (
          <div className="space-y-4">
            <div className="card bg-gray-50 dark:bg-gray-800 p-4 rounded-lg">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Определенное блюдо</p>
              <p className="text-lg font-semibold">{analysisTask.result.food || analysisTask.result.food_name}</p>
            </div>

            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="text-gray-600 dark:text-gray-400">Калории</p>
                <p className="font-semibold">{analysisTask.result.calories} ккал</p>
              </div>
              <div>
                <p className="text-gray-600 dark:text-gray-400">Вес</p>
                <p className="font-semibold">{analysisTask.result.weight_g}г</p>
              </div>
              <div>
                <p className="text-gray-600 dark:text-gray-400">Белки</p>
                <p className="font-semibold">{analysisTask.result.protein_g.toFixed(1)}г</p>
              </div>
              <div>
                <p className="text-gray-600 dark:text-gray-400">Жиры</p>
                <p className="font-semibold">{analysisTask.result.fat_g.toFixed(1)}г</p>
              </div>
              <div>
                <p className="text-gray-600 dark:text-gray-400">Углеводы</p>
                <p className="font-semibold">{analysisTask.result.carbs_g.toFixed(1)}г</p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Выберите тип приема</label>
              <select
                id="mealTypeSelect"
                defaultValue="lunch"
                className="input"
              >
                <option value="breakfast">🌅 Завтрак</option>
                <option value="lunch">🍽️ Обед</option>
                <option value="dinner">🌙 Ужин</option>
                <option value="snack">🍿 Закуска</option>
              </select>
            </div>

            <button
              onClick={() => {
                const select = document.getElementById('mealTypeSelect') as HTMLSelectElement
                handleAddFromAnalysis(select.value)
              }}
              disabled={isAddingFromAnalysis}
              className="btn-primary w-full disabled:opacity-50"
            >
              {isAddingFromAnalysis ? 'Добавление...' : 'Добавить в дневник'}
            </button>
          </div>
        )}
      </Modal>

      {/* Uploading Indicator */}
      {isUploading && <LoadingSpinner fullScreen message="Загрузка и анализ фото..." />}
    </div>
  )
}
