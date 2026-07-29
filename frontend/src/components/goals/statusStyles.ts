import { DayStatus } from '../../types'

/** Единый словарь оформления статусов дня: используется и точками недели
 *  на карточке серии, и кружками «Пути месяца», и легендой под ним —
 *  чтобы цвета нигде не разъезжались. */
export const DAY_STATUS_STYLE: Record<DayStatus, string> = {
  closed: 'bg-primary-500 text-white border border-primary-500',
  partial:
    'bg-primary-50 dark:bg-chip-dark text-primary-700 dark:text-primary-400 border border-primary-200 dark:border-primary-800',
  frozen: 'bg-water-chip dark:bg-water/15 text-water border border-water/30',
  missed:
    'bg-divider dark:bg-line-dark text-faint dark:text-faint-dark border border-transparent',
  future:
    'bg-transparent text-faint dark:text-faint-dark border border-dashed border-line dark:border-line-dark',
}

export const DAY_STATUS_LABEL: Record<DayStatus, string> = {
  closed: 'закрыт',
  partial: 'частично',
  frozen: 'заморозка',
  missed: 'пропуск',
  future: 'впереди',
}

/** Порядок легенды под «Путём месяца» (future в легенду не выводим —
 *  «впереди» и так очевидно по пустым кружкам). */
export const LEGEND_STATUSES: DayStatus[] = ['closed', 'partial', 'frozen', 'missed']
