import { Goal } from '../types'

// Зеркало констант из app/nutrition.py. Держим отдельно, чтобы подписи целей
// и пресеты темпа не дублировались по компонентам (профиль, регистрация).

export const GOAL_OPTIONS: { value: Goal; label: string; hint: string }[] = [
  { value: 'lose', label: 'Похудеть', hint: 'дефицит калорий, больше белка' },
  { value: 'maintain', label: 'Сохранить вес', hint: 'норма = суточный расход' },
  { value: 'gain', label: 'Набрать массу', hint: 'профицит калорий и углеводов' },
]

export const GOAL_LABELS: Record<Goal, string> = {
  lose: 'Похудение',
  maintain: 'Поддержание веса',
  gain: 'Набор массы',
}

// Пресеты темпа (кг/нед) — те же значения, что в nutrition.RATE_PRESETS.
// Для набора темпы ниже: быстрее 0.5 кг/нед прибавка идёт преимущественно в жир.
export const RATE_PRESETS: Record<Exclude<Goal, 'maintain'>, { value: number; label: string }[]> = {
  lose: [
    { value: 0.25, label: 'Мягкий' },
    { value: 0.5, label: 'Умеренный' },
    { value: 0.75, label: 'Быстрый' },
  ],
  gain: [
    { value: 0.125, label: 'Мягкий' },
    { value: 0.25, label: 'Умеренный' },
    { value: 0.5, label: 'Быстрый' },
  ],
}

export const DEFAULT_RATE: Record<Goal, number> = { lose: 0.5, maintain: 0, gain: 0.25 }

export const MAX_RATE_KG_PER_WEEK = 1.5

/** «0.5 кг/нед» -> «500 г/нед»: граммы читаются легче для мелких темпов. */
export const formatRate = (rate: number): string =>
  rate >= 1 ? `${rate} кг/нед` : `${Math.round(rate * 1000)} г/нед`

/** Подпись поправки калорий: «−550 ккал» / «+275 ккал» / «без поправки». */
export const formatCalorieDelta = (delta: number): string => {
  if (!delta) return 'без поправки'
  return `${delta > 0 ? '+' : '−'}${Math.abs(Math.round(delta))} ккал`
}
