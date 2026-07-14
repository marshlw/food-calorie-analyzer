import React, { useEffect, useRef } from 'react'
import { useFoodAnalysis } from '../hooks/useFoodAnalysis'
import { MealForm } from './MealForm'
import { LoadingSpinner } from './LoadingSpinner'
import { ErrorAlert } from './ErrorAlert'
import { AnalysisResult, MealEntry, MealEntryItem, MealEntryCreate } from '../types'
import { capitalize as cap } from '../utils/text'

const round1 = (v: number) => Math.round(v * 10) / 10

// Превращает состав от AI в редактируемые позиции конструктора:
// КБЖУ блюда распределяется по ингредиентам пропорционально их весу,
// чтобы каждую позицию можно было менять/убирать по отдельности.
export const ingredientsToItems = (r: AnalysisResult): MealEntryItem[] => {
  const ings = (r.ingredients ?? []).filter((i) => i.name)
  if (ings.length < 2) return []

  const totalW = ings.reduce((s, i) => s + (i.weight_g || 0), 0) || r.weight_g || 0
  if (totalW <= 0) return []

  return ings.map((ing) => {
    const share = (ing.weight_g || 0) / totalW
    return {
      food_name: cap(ing.name),
      weight_g: round1(ing.weight_g || 0),
      calories: round1(r.calories * share),
      protein_g: round1(r.protein_g * share),
      fat_g: round1(r.fat_g * share),
      carbs_g: round1(r.carbs_g * share),
    }
  })
}

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
          <img src={previewUrl} alt="Фото блюда" className="w-full h-48 object-cover rounded-tile" />
        )}
        <ErrorAlert message={error || 'Ошибка анализа'} onClose={() => {}} />
        <button className="btn-secondary w-full" onClick={() => analyze(file)}>
          Повторить
        </button>
        <button
          className="w-full py-3 text-sm font-medium text-muted dark:text-muted-dark hover:text-ink dark:hover:text-ink-dark transition-colors"
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
    // Предзаполняем форму значениями AI — пользователь может всё поправить:
    // ингредиенты становятся редактируемыми позициями (добавить/убрать/
    // поменять вес — КБЖУ пересчитается).
    const initial: MealEntry = {
      id: 0,
      food_name: cap(r.food || r.food_name || ''),
      calories: r.calories,
      protein_g: r.protein_g,
      fat_g: r.fat_g,
      carbs_g: r.carbs_g,
      weight_g: r.weight_g,
      meal_type: 'lunch',
      created_at: '',
      items: ingredientsToItems(r),
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
            className="w-full h-48 object-cover rounded-tile"
          />
        )}

        {/* Шапка результата: название + уверенность */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-display font-bold text-lg tracking-tight leading-tight">
              {initial.food_name || 'Блюдо'}
            </p>
            <p className="text-xs text-secondary mt-0.5">≈ {Math.round(r.weight_g)} г · распознано AI</p>
          </div>
          {confidencePct !== null && (
            <span className="chip-ai shrink-0 font-medium">✦ Уверенность {confidencePct}%</span>
          )}
        </div>

        <p className="text-xs text-tertiary">
          Состав распознан AI и разобран на блюда ниже — уберите лишнее, поправьте вес
          (КБЖУ пересчитается) или добавьте что-то из базы перед сохранением.
        </p>

        {/* Редактируемые поля (название/КБЖУ/тип приёма) */}
        <MealForm
          initialData={initial}
          onSubmit={handleSubmit}
          isLoading={saving}
          submitLabel="Добавить в дневник"
        />
        <button
          className="w-full py-3 text-sm font-medium text-muted dark:text-muted-dark hover:text-ink dark:hover:text-ink-dark transition-colors"
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
