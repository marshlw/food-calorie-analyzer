import React from 'react'
import { ChevronRight } from 'lucide-react'
import { GoalsToday } from '../../types'
import { DAY_STATUS_STYLE } from './statusStyles'

/** Кольцо серии: заполнение = доля закрытых дней текущей недели. */
const StreakRing: React.FC<{ size: number; progress: number; children: React.ReactNode }> = ({
  size,
  progress,
  children,
}) => {
  const stroke = size >= 80 ? 7 : 5
  const r = size / 2 - stroke / 2
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(progress, 1))

  return (
    <div
      className="relative grid place-items-center flex-shrink-0"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          fill="none"
          className="stroke-track dark:stroke-track-dark"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          className="stroke-primary-500 dark:stroke-primary-400 transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <div className="absolute flex flex-col items-center leading-none">{children}</div>
    </div>
  )
}

/** Точки недели Пн–Вс под кольцом. */
const WeekDots: React.FC<{ goals: GoalsToday }> = ({ goals }) => (
  <div className="grid grid-cols-7 gap-1.5 w-full">
    {goals.week.map((d) => (
      <div key={d.date} className="flex flex-col items-center gap-1">
        <span
          className={`text-[9px] ${
            d.is_today ? 'text-primary-500 dark:text-primary-400 font-semibold' : 'text-tertiary'
          }`}
        >
          {d.label}
        </span>
        <span
          title={d.date}
          className={`w-[22px] h-[22px] rounded-full ${DAY_STATUS_STYLE[d.status]}`}
        />
      </div>
    ))}
  </div>
)

interface Props {
  goals: GoalsToday
  /** compact — карточка-кнопка на «Дневнике», full — шапка вкладки «Путь». */
  variant?: 'compact' | 'full'
  onClick?: () => void
}

// Карточка серии из дизайна Rasify: кольцо недели с числом серии,
// подпись «N дней подряд» и точки Пн–Вс.
export const StreakCard: React.FC<Props> = ({ goals, variant = 'compact', onClick }) => {
  if (variant === 'full') {
    return (
      <div className="card p-5 mb-3 flex items-center gap-4">
        <StreakRing size={98} progress={goals.week_progress}>
          <span className="font-display font-extrabold text-3xl">{goals.streak}</span>
          <span className="text-[10px] text-tertiary mt-1">подряд</span>
        </StreakRing>

        <div className="flex-1 min-w-0 flex flex-col gap-2.5">
          <div>
            <div className="font-display font-bold text-[15px]">{goals.streak_title}</div>
            <div className="text-xs text-secondary mt-1">{goals.next_reward_hint}</div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className="chip bg-primary-50 dark:bg-chip-dark text-primary-700 dark:text-primary-400">
              Рекорд {goals.best_streak}
            </span>
            <span className="chip bg-divider dark:bg-line-dark text-secondary">
              Заморозки {goals.freezes_available}
            </span>
          </div>
        </div>
      </div>
    )
  }

  // Компактная карточка: кнопка, если задан onClick, иначе обычный блок.
  // Две явные ветки вместо динамического тега — так у TS не остаётся
  // вопросов к атрибуту type и обработчику на <div>.
  const body = (
    <>
      <div className="flex items-center gap-3">
        <StreakRing size={44} progress={goals.week_progress}>
          <span className="font-display font-extrabold text-[15px]">{goals.streak}</span>
        </StreakRing>

        <div className="flex-1 min-w-0">
          <div className="font-display font-bold text-[15px]">{goals.streak_title}</div>
          <div className="text-xs text-secondary mt-0.5 truncate">{goals.streak_hint}</div>
        </div>

        {onClick && <ChevronRight className="h-[18px] w-[18px] text-tertiary flex-shrink-0" />}
      </div>

      <WeekDots goals={goals} />
    </>
  )

  const shell = 'card w-full text-left p-4 mb-4 flex flex-col gap-3'

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${shell} hover:border-primary-300 transition-colors`}
      >
        {body}
      </button>
    )
  }

  return <div className={shell}>{body}</div>
}
