import { MealType } from '../types'

// Единые стили типов приёмов пищи (чипы с точками из дизайна Rasify)
export interface MealTypeMeta {
  label: string
  // Классы чипа (фон + текст), светлая и тёмная тема
  chip: string
  // Класс точки-маркера
  dot: string
}

export const MEAL_TYPE_META: Record<MealType, MealTypeMeta> = {
  breakfast: {
    label: 'Завтрак',
    chip: 'bg-fat-chip text-fat-text dark:bg-fat-dark/15 dark:text-fat-dark',
    dot: 'bg-fat dark:bg-fat-dark',
  },
  lunch: {
    label: 'Обед',
    chip: 'bg-primary-50 text-primary-500 dark:bg-chip-dark dark:text-primary-400',
    dot: 'bg-primary-500 dark:bg-primary-400',
  },
  dinner: {
    label: 'Ужин',
    chip: 'bg-dinner-chip text-dinner dark:bg-dinner-dark/15 dark:text-dinner-dark',
    dot: 'bg-dinner dark:bg-dinner-dark',
  },
  snacks: {
    label: 'Перекус',
    chip: 'bg-carbs-chip text-carbs-text dark:bg-carbs-dark/15 dark:text-carbs-dark',
    dot: 'bg-carbs dark:bg-carbs-dark',
  },
}

export const MEAL_TYPE_ORDER: MealType[] = ['breakfast', 'lunch', 'dinner', 'snacks']

// Короткая строка КБЖУ: «380 ккал · Б 14 · Ж 9 · У 58»
export const kbjuLine = (m: {
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
}): string =>
  `${Math.round(m.calories)} ккал · Б ${Math.round(m.protein_g)} · Ж ${Math.round(
    m.fat_g
  )} · У ${Math.round(m.carbs_g)}`
