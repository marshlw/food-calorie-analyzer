import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { TaskResponse } from '../types'
import { tasksApi } from '../api/tasks'
import { useApi } from '../hooks/useApi'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { ChevronRight } from 'lucide-react'

export const AnalysisHistory: React.FC = () => {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<TaskResponse[]>([])

  const {
    isLoading,
    error,
    execute: loadTasks,
  } = useApi<TaskResponse[]>({
    onSuccess: () => {},
  })

  useEffect(() => {
    const fetch = async () => {
      const data = await loadTasks(() => tasksApi.getTasks())
      setTasks(data || [])
    }
    fetch()
  }, [])

  const getStatusBadge = (status: string) => {
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
      case 'processing':
        return 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'
      case 'success':
        return 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
      case 'failure':
        return 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
      default:
        return 'bg-gray-50 dark:bg-gray-900/20 text-gray-700 dark:text-gray-400'
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold">История анализов</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Всего анализов: {tasks.length}
        </p>
      </div>

      {/* Errors */}
      {error && (
        <div className="mb-4">
          <ErrorAlert message={error} onClose={() => {}} />
        </div>
      )}

      {/* Loading */}
      {isLoading && <LoadingSpinner message="Загрузка анализов..." />}

      {/* Tasks List */}
      {!isLoading && (
        <>
          {tasks.length > 0 ? (
            <div className="space-y-3">
              {tasks.map((task) => (
                <button
                  key={task.id}
                  onClick={() => navigate(`/task/${task.id}`)}
                  className="card p-4 w-full text-left hover:shadow-md transition-shadow rounded-xl"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${getStatusColor(task.status)}`}>
                          {getStatusBadge(task.status)}
                        </span>
                      </div>

                      {task.result && (
                        <p className="font-semibold mb-1">
                          {task.result.food || task.result.food_name}
                        </p>
                      )}

                      {task.error && (
                        <p className="text-sm text-red-600 dark:text-red-400">{task.error}</p>
                      )}

                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {new Date(task.created_at).toLocaleString('ru-RU')}
                      </p>

                      {task.result && (
                        <div className="mt-2 flex gap-2 text-xs">
                          <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-2 py-1 rounded">
                            {task.result.calories} ккал
                          </span>
                          <span className="bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 px-2 py-1 rounded">
                            {task.result.weight_g}г
                          </span>
                        </div>
                      )}
                    </div>

                    <ChevronRight className="h-5 w-5 text-gray-400 flex-shrink-0 mt-1" />
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-600 dark:text-gray-400 mb-3">
                История анализов пуста
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-500">
                Начните анализ блюд на главном экране
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
