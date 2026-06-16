import React, { useState } from 'react'
import { MealEntryCreate, MealEntry, MealType } from '../types'

interface MealFormProps {
  initialData?: MealEntry
  onSubmit: (data: MealEntryCreate) => Promise<void>
  isLoading?: boolean
  submitLabel?: string
}

const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: 'breakfast', label: '🌅 Завтрак' },
  { value: 'lunch', label: '🍽️ Обед' },
  { value: 'dinner', label: '🌙 Ужин' },
  { value: 'snack', label: '🍿 Закуска' },
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
    if (formData.weight_g < 0) {
      newErrors.weight_g = 'Вес не может быть отрицательным'
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

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Meal Type */}
      <div>
        <label className="block text-sm font-medium mb-1">Тип приема</label>
        <select
          name="meal_type"
          value={formData.meal_type}
          onChange={handleChange}
          className="input"
        >
          {MEAL_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </div>

      {/* Food Name */}
      <div>
        <label className="block text-sm font-medium mb-1">Название блюда</label>
        <input
          type="text"
          name="food_name"
          value={formData.food_name}
          onChange={handleChange}
          placeholder="Например: куриное филе с рисом"
          className={`input ${errors.food_name ? 'border-red-500' : ''}`}
        />
        {errors.food_name && <p className="text-red-500 text-xs mt-1">{errors.food_name}</p>}
      </div>

      {/* Weight */}
      <div>
        <label className="block text-sm font-medium mb-1">Вес (г)</label>
        <input
          type="number"
          name="weight_g"
          value={formData.weight_g || ''}
          onChange={handleChange}
          placeholder="0"
          min="0"
          step="0.1"
          className={`input ${errors.weight_g ? 'border-red-500' : ''}`}
        />
        {errors.weight_g && <p className="text-red-500 text-xs mt-1">{errors.weight_g}</p>}
      </div>

      {/* Calories */}
      <div>
        <label className="block text-sm font-medium mb-1">Калории (ккал)</label>
        <input
          type="number"
          name="calories"
          value={formData.calories || ''}
          onChange={handleChange}
          placeholder="0"
          min="0"
          step="0.1"
          className={`input ${errors.calories ? 'border-red-500' : ''}`}
        />
        {errors.calories && <p className="text-red-500 text-xs mt-1">{errors.calories}</p>}
      </div>

      {/* Protein */}
      <div>
        <label className="block text-sm font-medium mb-1">Белки (г)</label>
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
        <label className="block text-sm font-medium mb-1">Жиры (г)</label>
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
        <label className="block text-sm font-medium mb-1">Углеводы (г)</label>
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
