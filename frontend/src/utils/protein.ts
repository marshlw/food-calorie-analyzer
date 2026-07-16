import { ProteinType } from '../types'

// Единые подписи/стили для источника белка (животный/растительный/смешанный).
// Используются в форме приёма, дневнике, карточках и профиле.
export interface ProteinTypeMeta {
  label: string // «Животный»
  short: string // «Живот.»
  icon: string // эмодзи-маркер
  // Классы текста (свет/тёмная тема)
  text: string
  // Классы точки-маркера
  dot: string
}

export const PROTEIN_TYPE_META: Record<Exclude<ProteinType, 'unknown'>, ProteinTypeMeta> = {
  animal: {
    label: 'Животный',
    short: 'Живот.',
    icon: '🥩',
    text: 'text-rose-600 dark:text-rose-400',
    dot: 'bg-rose-500 dark:bg-rose-400',
  },
  plant: {
    label: 'Растительный',
    short: 'Раст.',
    icon: '🌱',
    text: 'text-emerald-600 dark:text-emerald-400',
    dot: 'bg-emerald-500 dark:bg-emerald-400',
  },
  mixed: {
    label: 'Смешанный',
    short: 'Смеш.',
    icon: '🍲',
    text: 'text-amber-600 dark:text-amber-400',
    dot: 'bg-amber-500 dark:bg-amber-400',
  },
}

export const PROTEIN_TYPE_ORDER: Array<Exclude<ProteinType, 'unknown'>> = [
  'animal',
  'plant',
  'mixed',
]

// Доля животного белка в «смешанном» продукте (совпадает с backend
// protein_source.MIXED_ANIMAL_SHARE) — фронт делит так же для превью.
export const MIXED_ANIMAL_SHARE = 0.5

const round1 = (v: number) => Math.round(v * 10) / 10

// Делит белок (г) на {animal, plant} по выбранному типу источника.
// unknown → оба 0 (источник не определён).
export const splitProtein = (
  proteinG: number,
  type: ProteinType
): { animal: number; plant: number } => {
  const p = proteinG || 0
  if (type === 'animal') return { animal: round1(p), plant: 0 }
  if (type === 'plant') return { animal: 0, plant: round1(p) }
  if (type === 'mixed') {
    const animal = round1(p * MIXED_ANIMAL_SHARE)
    return { animal, plant: round1(p - animal) }
  }
  return { animal: 0, plant: 0 }
}

// Восстанавливает тип источника из уже посчитанных грамм (для повторного
// открытия записи/блюда в форме): оба 0 → unknown, только животный →
// animal, только растительный → plant, оба > 0 → mixed.
export const inferProteinType = (
  animalG?: number | null,
  plantG?: number | null
): ProteinType => {
  const a = animalG || 0
  const p = plantG || 0
  if (a > 0 && p > 0) return 'mixed'
  if (a > 0) return 'animal'
  if (p > 0) return 'plant'
  return 'unknown'
}

// Нормализует product.protein_type в ProteinType (null/неизвестное → mixed:
// у продукта из справочника белок всегда куда-то отнесён).
export const productProteinType = (raw?: string | null): ProteinType => {
  if (raw === 'animal' || raw === 'plant' || raw === 'mixed') return raw
  return 'mixed'
}
