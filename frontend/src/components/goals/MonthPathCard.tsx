import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { GoalPath } from '../../types'
import { DAY_STATUS_STYLE, DAY_STATUS_LABEL, LEGEND_STATUSES } from './statusStyles'

const monthTitle = (month: string): string => {
  // month — 'YYYY-MM'; собираем дату явно, чтобы не зависеть от парсинга
  // неполных ISO-строк в разных движках.
  const [y, m] = month.split('-').map(Number)
  if (!y || !m) return month
  return new Date(y, m - 1, 1).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
}

interface Props {
  path: GoalPath
  onShiftMonth: (delta: number) => void
  /** Нельзя листать вперёд дальше текущего месяца. */
  canGoForward: boolean
}

// «Путь месяца»: сетка кружков по дням, вехи серии и легенда статусов.
export const MonthPathCard: React.FC<Props> = ({ path, onShiftMonth, canGoForward }) => (
  <div className="card p-[18px] mb-3">
    <div className="flex items-center justify-between mb-1">
      <button
        type="button"
        onClick={() => onShiftMonth(-1)}
        aria-label="Предыдущий месяц"
        className="p-1.5 -ml-1.5 rounded-full text-muted dark:text-muted-dark hover:bg-surface dark:hover:bg-chip-dark transition-colors"
      >
        <ChevronLeft className="h-[18px] w-[18px]" />
      </button>
      <span className="font-display font-bold text-[15px] capitalize">
        {monthTitle(path.month)}
      </span>
      <button
        type="button"
        onClick={() => onShiftMonth(1)}
        disabled={!canGoForward}
        aria-label="Следующий месяц"
        className="p-1.5 -mr-1.5 rounded-full text-muted dark:text-muted-dark hover:bg-surface dark:hover:bg-chip-dark transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
      >
        <ChevronRight className="h-[18px] w-[18px]" />
      </button>
    </div>

    <div className="text-center text-xs text-secondary mb-3.5">{path.summary}</div>

    <div className="grid grid-cols-5 gap-x-2 gap-y-3 justify-items-center">
      {path.days.map((d) => (
        <div key={d.date} className="flex flex-col items-center gap-1 h-[58px] justify-center">
          <div
            title={`${d.date} — ${DAY_STATUS_LABEL[d.status]}`}
            className={`grid place-items-center rounded-full font-display font-bold text-xs
              ${d.milestone ? 'w-[42px] h-[42px]' : 'w-[34px] h-[34px]'}
              ${DAY_STATUS_STYLE[d.status]}
              ${d.is_today ? 'ring-2 ring-primary-500 ring-offset-2 ring-offset-white dark:ring-offset-card-dark' : ''}`}
          >
            {d.day}
          </div>
          <span className="text-[9px] text-tertiary h-[11px] leading-[11px]">
            {d.milestone ?? ''}
          </span>
        </div>
      ))}
    </div>

    <div className="flex flex-wrap gap-x-3 gap-y-2 mt-3.5 pt-3 border-t border-divider dark:border-line-dark">
      {LEGEND_STATUSES.map((s) => (
        <span key={s} className="inline-flex items-center gap-1.5 text-[11px] text-secondary">
          <span className={`w-[9px] h-[9px] rounded-full ${DAY_STATUS_STYLE[s]}`} />
          {DAY_STATUS_LABEL[s]}
        </span>
      ))}
    </div>
  </div>
)
