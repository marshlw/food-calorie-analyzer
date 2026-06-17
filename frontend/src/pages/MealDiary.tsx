import React, { useState, useEffect } from 'react'
import { DailyLog, MealEntry, MealEntryCreate } from '../types'
import { mealsApi } from '../api/meals'
import { MealCard } from '../components/MealCard'
import { MealForm } from '../components/MealForm'
import { DailyStats } from '../components/DailyStats'
import { Modal } from '../components/Modal'
import { ErrorAlert } from '../components/ErrorAlert'
import { SuccessAlert } from '../components/SuccessAlert'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { useApi } from '../hooks/useApi'
import { Calendar } from 'lucide-react'

export const MealDiary: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date()
    return today.toISOString().split('T')[0]
  })

  const [showEditModal, setShowEditModal] = useState(false)
  const [editingMeal, setEditingMeal] = useState<MealEntry | null>(null)
  const [successMessage, setSuccessMessage] = useState('')

  // Load daily log
  const {
    data: dailyLog,
    isLoading: isLoadingLog,
    error: loadError,
    execute: loadDailyLog,
  } = useApi<DailyLog>()

  // Update meal
  const {
    isLoading: isUpdating,
    execute: executeUpdate,
  } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Прием пищи обновлен!')
      setShowEditModal(false)
      setEditingMeal(null)
      loadDailyLog(() => mealsApi.getDailyLog(selectedDate))
    },
  })

  // Delete meal
  const {
    isLoading: isDeleting,
    execute: executeDelete,
  } = useApi<any>({
    onSuccess: () => {
      setSuccessMessage('Прием пищи удален!')
      loadDailyLog(() => mealsApi.getDailyLog(selectedDate))
    },
  })

  useEffect(() => {
    loadDailyLog(() => mealsApi.getDailyLog(selectedDate))
  }, [selectedDate])

  const handleEditMeal = (meal: MealEntry) => {
    setEditingMeal(meal)
    setShowEditModal(true)
  }

  const handleUpdateMeal = async (data: MealEntryCreate) => {
    if (!editingMeal) return
    await executeUpdate(() => mealsApi.updateMeal(editingMeal.id, data))
  }

  const handleDeleteMeal = async (meal: MealEntry) => {
    if (window.confirm('Вы уверены?')) {
      await executeDelete(() => mealsApi.deleteMeal(meal.id))
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Пищевой дневник</h1>
      </div>

      {/* Date Picker */}
      <div className="card p-4 mb-6 rounded-xl">
        <div className="flex items-center gap-3">
          <Calendar className="h-5 w-5 text-primary-500" />
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="flex-1 input m-0"
          />
        </div>
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
      {isLoadingLog && <LoadingSpinner message="Загрузка дневника..." />}

      {/* Daily Stats Summary (кольца КБЖУ с нормами) */}
      {dailyLog && !isLoadingLog && <DailyStats log={dailyLog} />}

      {/* Meals List */}
      {dailyLog && !isLoadingLog && (
        <>
          {dailyLog.meals.length > 0 ? (
            <div>
              <h2 className="text-lg font-semibold mb-3">Приемы пищи</h2>
              {dailyLog.meals.map((meal) => (
                <MealCard
                  key={meal.id}
                  meal={meal}
                  onEdit={() => handleEditMeal(meal)}
                  onDelete={() => handleDeleteMeal(meal)}
                  isLoading={isDeleting}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-600 dark:text-gray-400 mb-3">
                Нет приемов пищи за этот день
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-500">
                Начните с добавления первого приема на главном экране
              </p>
            </div>
          )}
        </>
      )}

      {/* Edit Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false)
          setEditingMeal(null)
        }}
        title="Редактировать прием пищи"
      >
        {editingMeal && (
          <MealForm
            initialData={editingMeal}
            onSubmit={handleUpdateMeal}
            isLoading={isUpdating}
            submitLabel="Сохранить"
          />
        )}
      </Modal>
    </div>
  )
}
