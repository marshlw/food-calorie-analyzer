import React, { useState } from 'react'
import { MealEntryCreate, MealEntry, MealType } from '../types'
import { ProductPicker } from './ProductPicker'

interface MealFormProps {
  initialData?: MealEntry
  onSubmit: (data: MealEntryCreate) => Promise<void>
  isLoading?: boolean
  submitLabel?: string
}

const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: 'breakfast', label: 'Завтрак' },
  { value: 'lunch', label: 'Обед' },
  { value: 'dinner', label: 'Ужин' },
  { value: 'snacks', label: 'Перекус' },
]

export const MealForm: React.FC<MealFormProps> = ({
  initialData,
  onSubmit,
  isLoading,
  submitLabel = 'Добавить',
}) => {
  const [formData, setFormData] = useState<MealEntryCreate>({
    food_name: initialData?.food_name || '',
    calories: initialData?.calories || 0,
    protein_g: initialData?.protein_g || 0,
    fat_g: initialData?.fat_g || 0,
    carbs_g: initialData?.carbs_g || 0,
    weight_g: initialData?.weight_g || 0,
    meal_type: initialData?.meal_type || 'lunch',
  })

  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.food_name.trim()) {
      newErrors.food_name = 'Название блюда обязательно'
    }
    if (formData.calories < 0) {
      newErrors.calories = 'Калории не могут быть отрицательными'
    }
    if (formData.weight_g <= 0) {
      newErrors.weight_g = 'Вес должен быть больше 0'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    try {
      await onSubmit(formData)
    } catch {
      // Error is handled by parent
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'meal_type' ? value : isNaN(+value) ? value : +value,
    }))
    if (errors[name]) {
      setErrors((prev) => {
        const { [name]: _, ...rest } = prev
        return rest
      })
    }
  }

  // Выбор продукта из базы КБЖУ подставляет название, вес и посчитанные
  // калории/белки/жиры/углеводы — пользователь может поправить их дальше вручную.
  const handleProductApply = (data: {
    food_name: string
    weight_g: number
    calories: number
    protein_g: number
    fat_g: number
    carbs_g: number
  }) => {
    setFormData((prev) => ({ ...prev, ...data }))
    setErrors({})
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Поиск продукта в базе КБЖУ */}
      <ProductPicker onApply={handleProductApply} />
      <div className="border-t border-divider dark:border-line-dark pt-4" />

      {/* Meal Type — сегментированный выбор приёма из дизайна */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Приём пищи</label>
        <div className="grid grid-cols-4 gap-2 bg-white dark:bg-card-dark border border-line dark:border-line-dark rounded-tile p-1.5">
          {MEAL_TYPES.map((type) => (
            <button
              key={type.value}
              type="button"
              onClick={() =>
                setFormData((prev) => ({ ...prev, meal_type: type.value }))
              }
              className={`py-2 text-[13px] rounded-xl transition-colors ${
                formData.meal_type === type.value
                  ? 'bg-primary-500 text-white font-semibold'
                  : 'text-muted dark:text-muted-dark font-medium hover:bg-surface dark:hover:bg-chip-dark'
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>
      </div>

      {/* Food Name */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Название блюда</label>
        <input
          type="text"
          name="food_name"
          value={formData.food_name}
          onChange={handleChange}
          placeholder="Например: куриное филе с рисом"
          className={`input ${errors.food_name ? 'border-danger' : ''}`}
        />
        {errors.food_name && <p className="text-danger text-xs mt-1">{errors.food_name}</p>}
      </div>

      {/* Weight */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Вес (г)</label>
        <input
          type="number"
          name="weight_g"
          value={formData.weight_g || ''}
          onChange={handleChange}
          placeholder="0"
          min="0"
          step="0.1"
          className={`input ${errors.weight_g ? 'border-danger' : ''}`}
        />
        {errors.weight_g && <p className="text-danger text-xs mt-1">{errors.weight_g}</p>}
      </div>

      {/* Calories */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Калории (ккал)</label>
        <input
          type="number"
          name="calories"
          value={formData.calories || ''}
          onChange={handleChange}
          placeholder="0"
          min="0"
          step="0.1"
          className={`input ${errors.calories ? 'border-danger' : ''}`}
        />
        {errors.calories && <p className="text-danger text-xs mt-1">{errors.calories}</p>}
      </div>

      {/* Protein */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Белки (г)</label>
        <input
          type="number"
          name="protein_g"
          value={formData.protein_g || ''}
          onChange={handleChange}
          placeholder="0"
          min="0"
          step="0.1"
          className="input"
        />
      </div>

      {/* Fat */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Жиры (г)</label>
        <input
          type="number"
          name="fat_g"
          value={formData.fat_g || ''}
          onChange={handleChange}
          placeholder="0"
          min="0"
          step="0.1"
          className="input"
        />
      </div>

      {/* Carbs */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">Углеводы (г)</label>
        <input
          type="number"
          name="carbs_g"
          value={formData.carbs_g || ''}
          onChange={handleChange}
          placeholder="0"
          min="0"
          step="0.1"
          className="input"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="btn-primary w-full disabled:opacity-50"
      >
        {isLoading ? 'Загрузка...' : submitLabel}
      </button>
    </form>
  )
}
