import React, { useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { productsApi } from '../api/products'
import { Product } from '../types'

interface AppliedProduct {
  food_name: string
  weight_g: number
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
}

interface ProductPickerProps {
  // Подставляет посчитанные КБЖУ (на выбранный вес) в родительскую форму.
  onApply: (data: AppliedProduct) => void
}

const round1 = (v: number) => Math.round(v * 10) / 10

// Считает КБЖУ продукта (нутриенты на 100 г) на заданный вес в граммах.
const scaleToWeight = (product: Product, weightG: number) => {
  const factor = weightG / 100
  return {
    calories: round1(product.calories * factor),
    protein_g: round1(product.protein * factor),
    fat_g: round1(product.fat * factor),
    carbs_g: round1(product.carbs * factor),
  }
}

// Поиск продукта из справочника КБЖУ + выбор веса → готовые КБЖУ на этот вес.
// Используется во всех местах, где можно добавить ингредиент/приём пищи
// (ручной ввод, редактирование, подтверждение AI-анализа) — компонент
// подключён внутри MealForm, общего для всех этих экранов.
export const ProductPicker: React.FC<ProductPickerProps> = ({ onApply }) => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [selected, setSelected] = useState<Product | null>(null)
  const [weight, setWeight] = useState<number>(100)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!isOpen) return
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const currentRequestId = ++requestIdRef.current
    setIsLoading(true)

    debounceRef.current = setTimeout(async () => {
      try {
        const products = await productsApi.search(query, 15)
        if (currentRequestId === requestIdRef.current) {
          setResults(products)
        }
      } catch {
        if (currentRequestId === requestIdRef.current) {
          setResults([])
        }
      } finally {
        if (currentRequestId === requestIdRef.current) {
          setIsLoading(false)
        }
      }
    }, 300)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, isOpen])

  const handleSelect = (product: Product) => {
    setSelected(product)
    setQuery(product.name)
    setIsOpen(false)
  }

  const handleClearSelection = () => {
    setSelected(null)
    setQuery('')
    setWeight(100)
  }

  const handleApply = () => {
    if (!selected) return
    const nutrition = scaleToWeight(selected, weight)
    onApply({
      food_name: selected.name,
      weight_g: weight,
      ...nutrition,
    })
  }

  const preview = selected ? scaleToWeight(selected, weight || 0) : null

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium mb-1">Найти продукт в базе</label>

      <div className="relative">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            value={query}
            onFocus={() => setIsOpen(true)}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelected(null)
              setIsOpen(true)
            }}
            onBlur={() => {
              // Небольшая задержка, чтобы клик по варианту в списке успел сработать.
              setTimeout(() => setIsOpen(false), 150)
            }}
            placeholder="Например: курица, рис, творог..."
            className="input pl-9 pr-8"
          />
          {query && (
            <button
              type="button"
              onClick={handleClearSelection}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              aria-label="Очистить"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {isOpen && (
          <div className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto card shadow-lg">
            {isLoading ? (
              <p className="p-3 text-sm text-gray-500 dark:text-gray-400">Поиск...</p>
            ) : results.length > 0 ? (
              results.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleSelect(product)}
                  className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between gap-2"
                >
                  <span className="text-sm">{product.name}</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">
                    {Math.round(product.calories)} ккал/100г
                  </span>
                </button>
              ))
            ) : (
              <p className="p-3 text-sm text-gray-500 dark:text-gray-400">Ничего не найдено</p>
            )}
          </div>
        )}
      </div>

      {selected && preview && (
        <div className="card p-3 space-y-3 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium">{selected.name}</p>
            <button
              type="button"
              onClick={handleClearSelection}
              className="text-xs text-gray-500 dark:text-gray-400 hover:underline"
            >
              Сбросить
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium mb-1">Количество, г</label>
            <input
              type="number"
              value={weight || ''}
              onChange={(e) => setWeight(Math.max(0, +e.target.value || 0))}
              min="0"
              step="1"
              className="input"
            />
          </div>

          <div className="grid grid-cols-4 gap-2 text-sm">
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-2 text-center">
              <p className="text-gray-600 dark:text-gray-400 text-xs">ккал</p>
              <p className="font-semibold text-blue-600 dark:text-blue-400">{preview.calories}</p>
            </div>
            <div className="bg-red-50 dark:bg-red-900/20 rounded p-2 text-center">
              <p className="text-gray-600 dark:text-gray-400 text-xs">Белки</p>
              <p className="font-semibold text-red-600 dark:text-red-400">{preview.protein_g}</p>
            </div>
            <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded p-2 text-center">
              <p className="text-gray-600 dark:text-gray-400 text-xs">Жиры</p>
              <p className="font-semibold text-yellow-600 dark:text-yellow-400">{preview.fat_g}</p>
            </div>
            <div className="bg-green-50 dark:bg-green-900/20 rounded p-2 text-center">
              <p className="text-gray-600 dark:text-gray-400 text-xs">Углев.</p>
              <p className="font-semibold text-green-600 dark:text-green-400">{preview.carbs_g}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleApply}
            disabled={!weight}
            className="btn-primary w-full disabled:opacity-50"
          >
            Подставить в форму
          </button>
        </div>
      )}
    </div>
  )
}
