import React, { useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { exercisesApi } from '../api/exercises'
import { Exercise } from '../types'

interface Props {
  // Вызывается при выборе упражнения из справочника
  onSelect: (exercise: Exercise) => void
  // Сброс выбранного упражнения (опционально)
  onClear?: () => void
  selected?: Exercise | null
  // Очищать поле после выбора (режим «добавить в конструктор»)
  clearOnSelect?: boolean
}

// Поиск упражнения в справочнике (по аналогии с ProductPicker для продуктов).
// Показывает примерный расход: «Жим лёжа · 30 мин ≈ 180 ккал».
export const ExercisePicker: React.FC<Props> = ({
  onSelect,
  onClear,
  selected = null,
  clearOnSelect = false,
}) => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Exercise[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!isOpen) return
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const currentRequestId = ++requestIdRef.current
    setIsLoading(true)

    debounceRef.current = setTimeout(async () => {
      try {
        const exercises = await exercisesApi.search(query, 60)
        if (currentRequestId === requestIdRef.current) setResults(exercises)
      } catch {
        if (currentRequestId === requestIdRef.current) setResults([])
      } finally {
        if (currentRequestId === requestIdRef.current) setIsLoading(false)
      }
    }, 250)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, isOpen])

  const handleSelect = (exercise: Exercise) => {
    setQuery(clearOnSelect ? '' : exercise.name)
    setIsOpen(false)
    onSelect(exercise)
  }

  const handleClear = () => {
    setQuery('')
    onClear?.()
  }

  return (
    <div>
      <label className="block text-[13px] font-semibold mb-1.5">
        Найти упражнение в базе
      </label>
      <div className="relative">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-faint dark:text-faint-dark" />
          <input
            type="text"
            value={query}
            onFocus={() => setIsOpen(true)}
            onChange={(e) => {
              setQuery(e.target.value)
              onClear?.()
              setIsOpen(true)
            }}
            onBlur={() => {
              // Задержка, чтобы клик по варианту в списке успел сработать
              setTimeout(() => setIsOpen(false), 150)
            }}
            placeholder="Например: жим лёжа, бег, йога..."
            className="input pl-9 pr-8"
          />
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-faint dark:text-faint-dark hover:text-muted dark:hover:text-muted-dark"
              aria-label="Очистить"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {isOpen && (
          <div className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto card shadow-nav rounded-tile">
            {isLoading ? (
              <p className="p-3 text-sm text-tertiary">Поиск...</p>
            ) : results.length > 0 ? (
              results.map((exercise) => (
                <button
                  key={exercise.id}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleSelect(exercise)}
                  className="w-full text-left px-3.5 py-2.5 hover:bg-surface dark:hover:bg-chip-dark flex items-center justify-between gap-2"
                >
                  <span className="text-sm">{exercise.name}</span>
                  <span className="text-xs text-tertiary shrink-0">
                    30 мин ≈ {exercise.kcal_per_30min} ккал
                  </span>
                </button>
              ))
            ) : (
              <p className="p-3 text-sm text-tertiary">Ничего не найдено</p>
            )}
          </div>
        )}
      </div>

      {selected && (
        <p className="text-xs text-tertiary mt-1.5">
          ≈ {Math.round(selected.kcal_per_min * 10) / 10} ккал/мин — калории посчитаются
          автоматически по длительности (оценка для ~70 кг).
        </p>
      )}
    </div>
  )
}
