import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { DailyStats } from '../components/DailyStats'
import { MealForm } from '../components/MealForm'
import { AnalysisFlow } from '../components/AnalysisFlow'
import { Modal } from '../components/Modal'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { AiLimitBadge } from '../components/AiLimitBadge'
import { useApi } from '../hooks/useApi'
import { useAiLimit } from '../hooks/useAiLimit'
import { mealsApi } from '../api/meals'
import { DailyLog, MealEntryCreate } from '../types'
import { Plus, Camera, History } from 'lucide-react'

type ModalKind = 'none' | 'manual' | 'photo'

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [modal, setModal] = useState<ModalKind>('none')
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [successMessage, setSuccessMessage] = useState('')
  const { aiLimit, aiExhausted, refreshAiLimit } = useAiLimit()

  // Load daily log
  const { data: dailyLog, isLoading: isLoadingLog, execute: loadDailyLog } = useApi<DailyLog>()

  // Add meal (ручной ввод и подтверждение AI-анализа)
  const { isLoading: isAddingMeal, error: addMealError, execute: executeAddMeal } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Прием пищи добавлен!')
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

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Ваш дневник</h1>
        <p className="text-gray-600 dark:text-gray-400">
          {new Date().toLocaleDateString('ru-RU', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
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

      {/* Daily Stats */}
      {isLoadingLog ? (
        <LoadingSpinner message="Загрузка..." />
      ) : dailyLog ? (
        <DailyStats log={dailyLog} />
      ) : null}

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-3 mb-2">
        <button
          onClick={() => setModal('manual')}
          className="btn btn-primary flex items-center justify-center gap-2"
        >
          <Plus className="h-5 w-5" />
          Добавить
        </button>
        <label
          className={`btn btn-secondary flex items-center justify-center gap-2 ${
            aiExhausted ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
        >
          <Camera className="h-5 w-5" />
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

      <AiLimitBadge aiLimit={aiLimit} />

      <button
        onClick={() => navigate('/analysis-history')}
        className="btn btn-secondary w-full flex items-center justify-center gap-2 mb-6"
      >
        <History className="h-5 w-5" />
        История анализов
      </button>

      {/* Meals preview */}
      {dailyLog && dailyLog.meals.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Приемы пищи</h2>
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

      {/* Add Meal Modal (ручной) */}
      <Modal isOpen={modal === 'manual'} onClose={close} title="Добавить прием пищи">
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
