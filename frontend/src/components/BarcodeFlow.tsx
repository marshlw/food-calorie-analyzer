import React, { useEffect, useRef, useState } from 'react'
import { ScanBarcode } from 'lucide-react'
import { barcodeApi } from '../api/barcode'
import { LoadingSpinner } from './LoadingSpinner'
import { ErrorAlert } from './ErrorAlert'
import { extractErrorMessage } from '../utils/errors'
import { BarcodeProduct, MealEntryCreate, MealType } from '../types'

const round1 = (v: number) => Math.round(v * 10) / 10

const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: 'breakfast', label: 'Завтрак' },
  { value: 'lunch', label: 'Обед' },
  { value: 'dinner', label: 'Ужин' },
  { value: 'snacks', label: 'Перекус' },
]

interface Props {
  file: File
  // Сохранение выбранного продукта (родитель добавит дату выбранного дня)
  onConfirm: (data: MealEntryCreate) => Promise<void> | void
  onCancel: () => void
  saving?: boolean
}

type Phase = 'scanning' | 'error' | 'done'

// Поток «блюдо по штрих-коду»: фото кода → продукт из Open Food Facts
// (название + КБЖУ на 100 г) → выбор граммовки → расчёт КБЖУ → добавление.
export const BarcodeFlow: React.FC<Props> = ({ file, onConfirm, onCancel, saving }) => {
  const [phase, setPhase] = useState<Phase>('scanning')
  const [product, setProduct] = useState<BarcodeProduct | null>(null)
  const [error, setError] = useState('')
  const [weight, setWeight] = useState('100')
  const [mealType, setMealType] = useState<MealType>('snacks')
  const [manualCode, setManualCode] = useState('')

  // Защита от двойного запроса в React.StrictMode (dev монтирует дважды)
  const scannedFile = useRef<File | null>(null)

  const scan = async (f: File) => {
    setPhase('scanning')
    setError('')
    try {
      setProduct(await barcodeApi.scan(f))
      setPhase('done')
    } catch (e) {
      setError(extractErrorMessage(e))
      setPhase('error')
    }
  }

  useEffect(() => {
    if (scannedFile.current === file) return
    scannedFile.current = file
    scan(file)
  }, [file]) // eslint-disable-line react-hooks/exhaustive-deps

  // Ручной ввод цифр кода, если фото не распозналось
  const lookupManual = async () => {
    const code = manualCode.replace(/\D/g, '')
    if (code.length < 8) {
      setError('Введите цифры штрих-кода (минимум 8)')
      return
    }
    setPhase('scanning')
    setError('')
    try {
      setProduct(await barcodeApi.lookup(code))
      setPhase('done')
    } catch (e) {
      setError(extractErrorMessage(e))
      setPhase('error')
    }
  }

  if (phase === 'scanning') {
    return <LoadingSpinner message="Распознаём штрих-код…" />
  }

  if (phase === 'error') {
    return (
      <div className="space-y-3">
        <ErrorAlert message={error || 'Не удалось распознать штрих-код'} onClose={() => {}} />
        <button className="btn-secondary w-full" onClick={() => scan(file)}>
          Повторить
        </button>

        {/* Фолбэк: цифры кода напечатаны под штрихами на любой упаковке */}
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">
            Или введите цифры под штрих-кодом
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              inputMode="numeric"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              placeholder="4600000000000"
              className="input flex-1"
            />
            <button type="button" className="btn-primary px-4" onClick={lookupManual}>
              Найти
            </button>
          </div>
        </div>

        <button
          className="w-full py-3 text-sm font-medium text-muted dark:text-muted-dark hover:text-ink dark:hover:text-ink-dark transition-colors"
          onClick={onCancel}
        >
          Отмена
        </button>
      </div>
    )
  }

  if (phase === 'done' && product) {
    const w = parseFloat(weight) || 0
    const factor = w / 100
    const totals = {
      calories: round1(product.calories_100g * factor),
      protein: round1(product.protein_100g * factor),
      fat: round1(product.fat_100g * factor),
      carbs: round1(product.carbs_100g * factor),
    }

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault()
      if (w <= 0) {
        setError('Укажите вес порции в граммах')
        return
      }
      setError('')
      const name = product.brand ? `${product.name} (${product.brand})` : product.name
      try {
        await onConfirm({
          food_name: name.slice(0, 200),
          weight_g: round1(w),
          calories: totals.calories,
          protein_g: totals.protein,
          fat_g: totals.fat,
          carbs_g: totals.carbs,
          meal_type: mealType,
        })
      } catch {
        // Ошибку сохранения показывает родитель (ErrorAlert на странице)
      }
    }

    return (
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Карточка найденного продукта */}
        <div className="flex items-start gap-3 rounded-tile border border-line dark:border-line-dark bg-surface dark:bg-chip-dark/50 p-3">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.name}
              className="w-16 h-16 object-cover rounded-xl flex-shrink-0"
            />
          ) : (
            <div className="w-16 h-16 rounded-xl bg-primary-50 dark:bg-chip-dark flex items-center justify-center flex-shrink-0">
              <ScanBarcode className="h-7 w-7 text-primary-500" />
            </div>
          )}
          <div className="min-w-0">
            <p className="font-display font-bold text-base tracking-tight leading-tight">
              {product.name}
            </p>
            <p className="text-xs text-secondary mt-0.5">
              {[product.brand, product.quantity].filter(Boolean).join(' · ')}
            </p>
            <p className="text-[11px] text-tertiary mt-1">
              Штрих-код {product.barcode} · Open Food Facts
            </p>
          </div>
        </div>

        {/* КБЖУ на 100 г */}
        <div className="flex justify-between items-center px-4 py-2.5 rounded-tile bg-surface dark:bg-chip-dark/50 border border-line dark:border-line-dark">
          <span className="text-[13px] font-semibold text-muted dark:text-muted-dark">На 100 г</span>
          <span className="text-[13px] font-medium">
            {Math.round(product.calories_100g)} ккал · Б {round1(product.protein_100g)} · Ж{' '}
            {round1(product.fat_100g)} · У {round1(product.carbs_100g)}
          </span>
        </div>

        {/* Граммовка порции */}
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">Сколько съели, г</label>
          <input
            type="number"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            min="1"
            step="1"
            className="input"
            disabled={saving}
            autoFocus
          />
        </div>

        {/* Приём пищи */}
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">Приём пищи</label>
          <div className="grid grid-cols-4 gap-2 bg-white dark:bg-card-dark border border-line dark:border-line-dark rounded-tile p-1.5">
            {MEAL_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => setMealType(type.value)}
                className={`py-2 text-[13px] rounded-xl transition-colors ${
                  mealType === type.value
                    ? 'bg-primary-500 text-white font-semibold'
                    : 'text-muted dark:text-muted-dark font-medium hover:bg-surface dark:hover:bg-chip-dark'
                }`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>

        {/* Итог на выбранный вес */}
        <div className="flex justify-between items-center px-4 py-3 rounded-tile bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400">
          <span className="text-[13px] font-semibold">Итого · {Math.round(w)} г</span>
          <span className="text-[13px] font-bold">
            {Math.round(totals.calories)} ккал · Б {Math.round(totals.protein)} · Ж{' '}
            {Math.round(totals.fat)} · У {Math.round(totals.carbs)}
          </span>
        </div>

        {error && <p className="text-danger text-xs">{error}</p>}

        <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
          {saving ? 'Загрузка...' : 'Добавить в дневник'}
        </button>
        <button
          type="button"
          className="w-full py-3 text-sm font-medium text-muted dark:text-muted-dark hover:text-ink dark:hover:text-ink-dark transition-colors"
          onClick={onCancel}
        >
          Отмена
        </button>
      </form>
    )
  }

  return null
}
