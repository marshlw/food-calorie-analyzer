import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { TaskResponse, TaskStatus } from '../types'
import { tasksApi } from '../api/tasks'
import { useApi } from '../hooks/useApi'
import { AppHeader } from '../components/Brand'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { ArrowLeft } from 'lucide-react'

// Точка-статус анализа (из дизайна: зелёная — успех, жёлтая — в работе, красная — ошибка)
const STATUS_DOT: Record<TaskStatus, string> = {
  success: 'bg-carbs dark:bg-carbs-dark',
  pending: 'bg-fat dark:bg-fat-dark',
  processing: 'bg-fat dark:bg-fat-dark',
  failure: 'bg-protein dark:bg-protein-dark',
}

const statusTitle = (task: TaskResponse): string => {
  switch (task.status) {
    case 'pending':
    case 'processing':
      return 'Обрабатывается…'
    case 'failure':
      return 'Не удалось распознать'
    default:
      return task.result?.food || task.result?.food_name || 'Блюдо'
  }
}

const statusMeta = (task: TaskResponse): string => {
  const dt = new Date(task.created_at).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  })
  if (task.status === 'failure') return `${dt} · попробуйте другое фото`
  if (task.status === 'success' && task.result) {
    return `${dt} · ${Math.round(task.result.calories)} ккал · ${Math.round(task.result.weight_g)} г`
  }
  return dt
}

export const AnalysisHistory: React.FC = () => {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<TaskResponse[]>([])

  const { isLoading, error, execute: loadTasks } = useApi<TaskResponse[]>({
    onSuccess: () => {},
  })

  useEffect(() => {
    const fetch = async () => {
      const data = await loadTasks(() => tasksApi.getTasks())
      setTasks(data || [])
    }
    fetch()
  }, [])

  return (
    <div className="max-w-md mx-auto px-5 pt-6 pb-32">
      <AppHeader />

      {/* Заголовок с кнопкой «назад» (открывается из Профиля) */}
      <div className="flex items-center gap-2.5 mb-5">
        <button
          onClick={() => navigate(-1)}
          aria-label="Назад"
          className="w-[38px] h-[38px] rounded-full bg-white dark:bg-chip-dark border border-line dark:border-line-dark flex items-center justify-center flex-shrink-0 text-ink dark:text-ink-dark"
        >
          <ArrowLeft className="h-[18px] w-[18px]" />
        </button>
        <div>
          <h1 className="font-display font-bold text-2xl tracking-tight">История анализов</h1>
          <p className="text-[13px] text-secondary mt-0.5">
            {tasks.length > 0 ? `Всего анализов: ${tasks.length}` : 'AI-анализы блюд по фото'}
          </p>
        </div>
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
            <div className="flex flex-col gap-2.5">
              {tasks.map((task) => (
                <button
                  key={task.id}
                  onClick={() => navigate(`/task/${task.id}`)}
                  className="card-tile p-4 w-full text-left flex items-center gap-3.5 hover:border-primary-300 transition-colors"
                >
                  {/* Превью фото */}
                  {task.image_path ? (
                    <img
                      src={task.image_path}
                      alt=""
                      className="w-14 h-14 rounded-cell object-cover flex-shrink-0 bg-track dark:bg-track-dark"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-cell bg-track dark:bg-track-dark flex-shrink-0" />
                  )}

                  <div className="flex-1 min-w-0">
                    <div
                      className={`text-[15px] font-semibold truncate ${
                        task.status !== 'success' ? 'text-secondary' : ''
                      }`}
                    >
                      {statusTitle(task)}
                    </div>
                    <div className="text-xs text-secondary mt-0.5 truncate">{statusMeta(task)}</div>
                  </div>

                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[task.status]}`}
                  />
                </button>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-secondary text-sm mb-2">История анализов пуста</p>
              <p className="text-xs text-tertiary">Начните анализ блюд на главном экране</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
