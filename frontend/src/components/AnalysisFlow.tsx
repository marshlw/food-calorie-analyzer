import React, { useEffect, useRef } from 'react'
import { useFoodAnalysis } from '../hooks/useFoodAnalysis'
import { MealForm } from './MealForm'
import { IngredientList } from './IngredientList'
import { LoadingSpinner } from './LoadingSpinner'
import { ErrorAlert } from './ErrorAlert'
import { MealEntry, MealEntryCreate } from '../types'

interface Props {
  file: File
  // Сохранение подтверждённого результата (родитель добавит дату выбранного дня)
  onConfirm: (data: MealEntryCreate) => Promise<void> | void
  onCancel: () => void
  saving?: boolean
}

// Поток AI-анализа: загрузка → анализ → редактируемое подтверждение → сохранение.
export const AnalysisFlow: React.FC<Props> = ({ file, onConfirm, onCancel, saving }) => {
  const { phase, task, error, previewUrl, analyze, reset } = useFoodAnalysis()

  // Защита от повторной загрузки одного и того же файла. React.StrictMode в dev
  // монтирует компонент дважды — без этого было бы два POST /analyze и дубль в истории.
  const analyzedFile = useRef<File | null>(null)

  useEffect(() => {
    if (analyzedFile.current === file) return
    analyzedFile.current = file
    analyze(file)
  }, [file]) // eslint-disable-line react-hooks/exhaustive-deps

  if (phase === 'uploading' || phase === 'analyzing') {
    return <LoadingSpinner message="Анализируем фото…" />
  }

  if (phase === 'error') {
    return (
      <div className="space-y-3">
        {previewUrl && (
          <img src={previewUrl} alt="Фото блюда" className="w-full h-48 object-cover rounded-lg" />
        )}
        <ErrorAlert message={error || 'Ошибка анализа'} onClose={() => {}} />
        <button className="btn btn-secondary w-full" onClick={() => analyze(file)}>
          Повторить
        </button>
        <button
          className="btn w-full"
          onClick={() => {
            reset()
            onCancel()
          }}
        >
          Отмена
        </button>
      </div>
    )
  }

  if (phase === 'done' && task?.result) {
    const r = task.result
    // Предзаполняем форму значениями AI — пользователь может всё поправить.
    const initial: MealEntry = {
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

    // Прокидываем task_id, чтобы сохранённая запись сохранила источник «AI».
    const handleSubmit = async (data: MealEntryCreate): Promise<void> => {
      await onConfirm({ ...data, task_id: task.id })
    }

    const confidencePct = typeof r.confidence === 'number' ? Math.round(r.confidence * 100) : null

    return (
      <div className="space-y-4">
        {(previewUrl || task.image_path) && (
          <img
            src={previewUrl || task.image_path}
            alt="Фото блюда"
            className="w-full h-48 object-cover rounded-lg"
          />
        )}

        {/* Шапка результата: название + уверенность */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-lg font-semibold leading-tight">{initial.food_name || 'Блюдо'}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">≈ {Math.round(r.weight_g)} г</p>
          </div>
          {confidencePct !== null && (
            <span className="shrink-0 text-xs px-2 py-1 rounded-full bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400">
              Уверенность {confidencePct}%
            </span>
          )}
        </div>

        {/* Состав от AI */}
        {r.ingredients && r.ingredients.length > 0 && <IngredientList ingredients={r.ingredients} />}

        <p className="text-xs text-gray-500 dark:text-gray-400">
          Проверьте название, выберите приём пищи и при необходимости поправьте КБЖУ перед добавлением
          в календарь.
        </p>

        {/* Редактируемые поля (название/КБЖУ/тип приёма) */}
        <MealForm
          initialData={initial}
          onSubmit={handleSubmit}
          isLoading={saving}
          submitLabel="Добавить в календарь"
        />
        <button
          className="btn w-full"
          onClick={() => {
            reset()
            onCancel()
          }}
        >
          Отклонить
        </button>
      </div>
    )
  }

  return null
}
