import React, { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { MealEntryCreate, MealEntry, MealEntryItem, MealType, ProteinType } from '../types'
import { ProductPicker } from './ProductPicker'
import { PROTEIN_TYPE_META, splitProtein, inferProteinType } from '../utils/protein'

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

const round1 = (v: number) => Math.round(v * 10) / 10

// Плотность КБЖУ на 1 г — для авто-пересчёта при изменении веса блюда
interface Density {
  kcal: number
  p: number
  f: number
  c: number
}

// Строка конструктора: одно блюдо
interface Row {
  key: number
  food_name: string
  weight: string
  calories: string
  protein: string
  fat: string
  carbs: string
  density: Density | null
  // Источник белка блюда: животный/растительный/смешанный/не указан
  proteinType: ProteinType
}

let rowKey = 1

const emptyRow = (): Row => ({
  key: rowKey++,
  food_name: '',
  weight: '',
  calories: '',
  protein: '',
  fat: '',
  carbs: '',
  density: null,
  proteinType: 'unknown',
})

const rowFromValues = (
  name: string,
  weight: number,
  calories: number,
  protein: number,
  fat: number,
  carbs: number,
  proteinType: ProteinType = 'unknown'
): Row => ({
  key: rowKey++,
  food_name: name,
  weight: weight ? String(round1(weight)) : '',
  calories: String(round1(calories)),
  protein: String(round1(protein)),
  fat: String(round1(fat)),
  carbs: String(round1(carbs)),
  // Запоминаем «плотность», чтобы правка веса пересчитывала КБЖУ
  density:
    weight > 0
      ? { kcal: calories / weight, p: protein / weight, f: fat / weight, c: carbs / weight }
      : null,
  proteinType,
})

const initRows = (initialData?: MealEntry): Row[] => {
  if (initialData?.items && initialData.items.length > 0) {
    return initialData.items.map((i) =>
      rowFromValues(
        i.food_name,
        i.weight_g,
        i.calories,
        i.protein_g,
        i.fat_g,
        i.carbs_g,
        inferProteinType(i.protein_animal_g, i.protein_plant_g)
      )
    )
  }
  if (initialData) {
    return [
      rowFromValues(
        initialData.food_name,
        initialData.weight_g,
        initialData.calories,
        initialData.protein_g,
        initialData.fat_g,
        initialData.carbs_g,
        inferProteinType(initialData.protein_animal_g, initialData.protein_plant_g)
      ),
    ]
  }
  return [emptyRow()]
}

// Тип источника белка + режим авто-пересчёта веса не связаны, но при смене
// веса тип остаётся прежним — грамм белка меняется, а его «природа» нет.
const PROTEIN_CHOICES: Array<{ value: ProteinType; label: string }> = [
  { value: 'animal', label: PROTEIN_TYPE_META.animal.short },
  { value: 'plant', label: PROTEIN_TYPE_META.plant.short },
  { value: 'mixed', label: PROTEIN_TYPE_META.mixed.short },
  { value: 'unknown', label: '—' },
]

const num = (v: string): number => parseFloat(v) || 0

// Конструктор приёма пищи: несколько блюд в одной записи
// («гарнир + основное блюдо»). Блюдо можно взять из базы КБЖУ,
// добавить вручную или отредактировать позиции из AI-анализа.
export const MealForm: React.FC<MealFormProps> = ({
  initialData,
  onSubmit,
  isLoading,
  submitLabel = 'Добавить',
}) => {
  const [rows, setRows] = useState<Row[]>(() => initRows(initialData))
  const [mealType, setMealType] = useState<MealType>(initialData?.meal_type || 'lunch')
  const [mealName, setMealName] = useState(
    initialData?.items && initialData.items.length > 1 ? initialData.food_name : ''
  )
  const [error, setError] = useState('')

  const updateRow = (key: number, patch: Partial<Row>) => {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  }

  // Изменение веса: если известна плотность (блюдо из базы/AI) — пересчёт КБЖУ
  const handleWeightChange = (row: Row, value: string) => {
    const w = num(value)
    if (row.density && w > 0) {
      updateRow(row.key, {
        weight: value,
        calories: String(round1(row.density.kcal * w)),
        protein: String(round1(row.density.p * w)),
        fat: String(round1(row.density.f * w)),
        carbs: String(round1(row.density.c * w)),
      })
    } else {
      updateRow(row.key, { weight: value })
    }
  }

  // Ручная правка КБЖУ — пользователь берёт контроль, авто-пересчёт отключаем
  const handleMacroChange = (row: Row, field: 'calories' | 'protein' | 'fat' | 'carbs', value: string) => {
    updateRow(row.key, { [field]: value, density: null } as Partial<Row>)
  }

  const removeRow = (key: number) => {
    setRows((prev) => (prev.length > 1 ? prev.filter((r) => r.key !== key) : prev))
  }

  // Продукт из базы КБЖУ добавляется отдельным блюдом
  const handleProductApply = (data: {
    food_name: string
    weight_g: number
    calories: number
    protein_g: number
    fat_g: number
    carbs_g: number
    protein_type?: ProteinType
  }) => {
    const newRow = rowFromValues(
      data.food_name,
      data.weight_g,
      data.calories,
      data.protein_g,
      data.fat_g,
      data.carbs_g,
      data.protein_type ?? 'unknown'
    )
    setRows((prev) => {
      const emptyIdx = prev.findIndex((r) => !r.food_name.trim() && !num(r.weight) && !num(r.calories))
      if (emptyIdx >= 0) {
        const next = [...prev]
        next[emptyIdx] = newRow
        return next
      }
      return [...prev, newRow]
    })
    setError('')
  }

  const filledRows = rows.filter((r) => r.food_name.trim())
  // Разделение белка по каждому блюду согласно его типу источника.
  const rowSplit = (r: Row) => splitProtein(num(r.protein), r.proteinType)
  const totals = {
    weight: filledRows.reduce((s, r) => s + num(r.weight), 0),
    calories: filledRows.reduce((s, r) => s + num(r.calories), 0),
    protein: filledRows.reduce((s, r) => s + num(r.protein), 0),
    proteinAnimal: filledRows.reduce((s, r) => s + rowSplit(r).animal, 0),
    proteinPlant: filledRows.reduce((s, r) => s + rowSplit(r).plant, 0),
    fat: filledRows.reduce((s, r) => s + num(r.fat), 0),
    carbs: filledRows.reduce((s, r) => s + num(r.carbs), 0),
  }

  const autoName = filledRows.map((r) => r.food_name.trim()).join(' + ').slice(0, 190)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (filledRows.length === 0) {
      setError('Добавьте хотя бы одно блюдо')
      return
    }
    for (const r of filledRows) {
      if (num(r.weight) <= 0) {
        setError(`Укажите вес: «${r.food_name.trim()}»`)
        return
      }
      if (num(r.calories) < 0) {
        setError('Калории не могут быть отрицательными')
        return
      }
    }

    setError('')

    const items: MealEntryItem[] = filledRows.map((r) => {
      const split = rowSplit(r)
      return {
        food_name: r.food_name.trim(),
        weight_g: num(r.weight),
        calories: round1(num(r.calories)),
        protein_g: round1(num(r.protein)),
        protein_animal_g: split.animal,
        protein_plant_g: split.plant,
        fat_g: round1(num(r.fat)),
        carbs_g: round1(num(r.carbs)),
      }
    })

    const base = {
      meal_type: mealType,
      calories: round1(totals.calories),
      protein_g: round1(totals.protein),
      protein_animal_g: round1(totals.proteinAnimal),
      protein_plant_g: round1(totals.proteinPlant),
      fat_g: round1(totals.fat),
      carbs_g: round1(totals.carbs),
      weight_g: round1(totals.weight),
    }

    try {
      if (items.length === 1) {
        // Простая запись — без вложенных блюд
        await onSubmit({ ...base, food_name: items[0].food_name })
      } else {
        await onSubmit({
          ...base,
          food_name: (mealName.trim() || autoName || 'Приём пищи').slice(0, 200),
          items,
        })
      }
    } catch {
      // Error is handled by parent
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Поиск продукта в базе КБЖУ — добавляет блюдо в список */}
      <ProductPicker onApply={handleProductApply} applyLabel="Добавить блюдом" />
      <div className="border-t border-divider dark:border-line-dark pt-4" />

      {/* Meal Type — сегментированный выбор приёма из дизайна */}
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

      {/* Конструктор блюд */}
      <div>
        <label className="block text-[13px] font-semibold mb-1.5">
          Блюда {rows.length > 1 ? `· ${rows.length}` : ''}
        </label>
        <div className="flex flex-col gap-2">
          {rows.map((row, i) => (
            <div
              key={row.key}
              className="rounded-tile border border-line dark:border-line-dark bg-surface dark:bg-chip-dark/50 p-3"
            >
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="text"
                  value={row.food_name}
                  onChange={(e) => updateRow(row.key, { food_name: e.target.value })}
                  placeholder={`Блюдо ${i + 1} (например: рис отварной)`}
                  className="input flex-1 !py-2 text-sm"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => removeRow(row.key)}
                  disabled={rows.length <= 1 || isLoading}
                  aria-label="Убрать блюдо"
                  className="p-1.5 rounded-lg text-faint dark:text-faint-dark hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-30 flex-shrink-0"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="grid grid-cols-5 gap-1.5">
                <div>
                  <input
                    type="number"
                    value={row.weight}
                    onChange={(e) => handleWeightChange(row, e.target.value)}
                    placeholder="0"
                    min="0"
                    step="1"
                    className="input !py-2 !px-2 text-sm text-center"
                    disabled={isLoading}
                  />
                  <div className="text-[10px] text-tertiary text-center mt-0.5">
                    г{row.density ? ' · авто' : ''}
                  </div>
                </div>
                <div>
                  <input
                    type="number"
                    value={row.calories}
                    onChange={(e) => handleMacroChange(row, 'calories', e.target.value)}
                    placeholder="0"
                    min="0"
                    step="0.1"
                    className="input !py-2 !px-2 text-sm text-center"
                    disabled={isLoading}
                  />
                  <div className="text-[10px] text-tertiary text-center mt-0.5">ккал</div>
                </div>
                <div>
                  <input
                    type="number"
                    value={row.protein}
                    onChange={(e) => handleMacroChange(row, 'protein', e.target.value)}
                    placeholder="0"
                    min="0"
                    step="0.1"
                    className="input !py-2 !px-2 text-sm text-center"
                    disabled={isLoading}
                  />
                  <div className="text-[10px] text-center mt-0.5 text-protein dark:text-protein-dark">Б</div>
                </div>
                <div>
                  <input
                    type="number"
                    value={row.fat}
                    onChange={(e) => handleMacroChange(row, 'fat', e.target.value)}
                    placeholder="0"
                    min="0"
                    step="0.1"
                    className="input !py-2 !px-2 text-sm text-center"
                    disabled={isLoading}
                  />
                  <div className="text-[10px] text-center mt-0.5 text-fat dark:text-fat-dark">Ж</div>
                </div>
                <div>
                  <input
                    type="number"
                    value={row.carbs}
                    onChange={(e) => handleMacroChange(row, 'carbs', e.target.value)}
                    placeholder="0"
                    min="0"
                    step="0.1"
                    className="input !py-2 !px-2 text-sm text-center"
                    disabled={isLoading}
                  />
                  <div className="text-[10px] text-center mt-0.5 text-carbs dark:text-carbs-dark">У</div>
                </div>
              </div>

              {/* Источник белка блюда: животный / растительный / смешанный */}
              <div className="mt-2 flex items-center gap-2">
                <span className="text-[11px] text-tertiary flex-shrink-0">Белок:</span>
                <div className="flex gap-1 flex-wrap">
                  {PROTEIN_CHOICES.map((choice) => {
                    const active = row.proteinType === choice.value
                    const meta =
                      choice.value !== 'unknown' ? PROTEIN_TYPE_META[choice.value] : null
                    return (
                      <button
                        key={choice.value}
                        type="button"
                        onClick={() => updateRow(row.key, { proteinType: choice.value })}
                        disabled={isLoading}
                        className={`px-2 py-1 rounded-lg text-[11px] font-medium transition-colors border ${
                          active
                            ? 'bg-primary-500 text-white border-primary-500'
                            : 'border-line dark:border-line-dark text-muted dark:text-muted-dark hover:bg-white dark:hover:bg-card-dark'
                        }`}
                      >
                        {meta ? `${meta.icon} ${choice.label}` : choice.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, emptyRow()])}
          disabled={isLoading}
          className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary-500 dark:text-primary-400 hover:text-primary-700"
        >
          <Plus className="h-3.5 w-3.5" /> Добавить блюдо
        </button>
      </div>

      {/* Итого по приёму */}
      {filledRows.length > 0 && (
        <div className="px-4 py-3 rounded-tile bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400">
          <div className="flex justify-between items-center">
            <span className="text-[13px] font-semibold">
              Итого · {Math.round(totals.weight)} г
            </span>
            <span className="text-[13px] font-bold">
              {Math.round(totals.calories)} ккал · Б {Math.round(totals.protein)} · Ж{' '}
              {Math.round(totals.fat)} · У {Math.round(totals.carbs)}
            </span>
          </div>
          {(totals.proteinAnimal > 0 || totals.proteinPlant > 0) && (
            <div className="mt-1.5 flex items-center gap-3 text-[11px]">
              <span className="inline-flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${PROTEIN_TYPE_META.animal.dot}`} />
                {PROTEIN_TYPE_META.animal.label} {Math.round(totals.proteinAnimal)} г
              </span>
              <span className="inline-flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${PROTEIN_TYPE_META.plant.dot}`} />
                {PROTEIN_TYPE_META.plant.label} {Math.round(totals.proteinPlant)} г
              </span>
            </div>
          )}
        </div>
      )}

      {/* Название приёма — только для составных записей */}
      {filledRows.length > 1 && (
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">Название приёма (опц.)</label>
          <input
            type="text"
            value={mealName}
            onChange={(e) => setMealName(e.target.value)}
            placeholder={autoName || 'Например: Обед'}
            className="input"
            disabled={isLoading}
          />
        </div>
      )}

      {error && <p className="text-danger text-xs">{error}</p>}

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
