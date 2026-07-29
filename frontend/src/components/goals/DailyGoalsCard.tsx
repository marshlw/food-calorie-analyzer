import React from 'react'
import { Check } from 'lucide-react'
import { GoalsToday, DailyGoalItem } from '../../types'

const GoalRow: React.FC<{ goal: DailyGoalItem }> = ({ goal }) => (
  <div
    className={`flex items-center gap-3 px-3 py-2.5 rounded-tile border ${
      goal.done
        ? 'bg-primary-50 dark:bg-chip-dark border-primary-200 dark:border-primary-800'
        : 'bg-[#f9fafc] dark:bg-surface-dark border-line dark:border-line-dark'
    }`}
  >
    <span
      className={`w-[23px] h-[23px] flex-shrink-0 rounded-full grid place-items-center border-2 ${
        goal.done
          ? 'bg-primary-500 border-primary-500'
          : 'bg-white dark:bg-card-dark border-line dark:border-line-dark'
      }`}
    >
      <Check
        className={`h-3 w-3 text-white transition-opacity ${goal.done ? 'opacity-100' : 'opacity-0'}`}
        strokeWidth={3}
      />
    </span>

    <span className="flex-1 min-w-0">
      <span className="block text-sm font-semibold">{goal.label}</span>
      <span className="block text-xs text-secondary mt-0.5">{goal.hint}</span>
    </span>

    <span
      className={`text-[11px] font-semibold flex-shrink-0 ${
        goal.done ? 'text-primary-700 dark:text-primary-400' : 'text-tertiary'
      }`}
    >
      +{goal.reward}
    </span>
  </div>
)

interface Props {
  goals: GoalsToday
}

// Карточка «Цель дня»: три задачи, прогресс и статус закрытия дня.
// Задачи закрываются автоматически по фактическим записям — ручной галочки
// нет специально: отметить «съел» не поев обесценило бы серию.
export const DailyGoalsCard: React.FC<Props> = ({ goals }) => {
  const pct = goals.total_count > 0 ? (goals.done_count / goals.total_count) * 100 : 0

  return (
    <div className="card p-[18px] mb-3">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="font-display font-bold text-[15px]">Цель дня</span>
        <span className="text-xs text-secondary">
          {goals.done_count} из {goals.total_count}
        </span>
      </div>

      <div className="h-1.5 rounded-full bg-track dark:bg-track-dark overflow-hidden mb-3.5">
        <div
          className="h-1.5 rounded-full bg-primary-500 dark:bg-primary-400 transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="flex flex-col gap-2">
        {goals.goals.map((g) => (
          <GoalRow key={g.id} goal={g} />
        ))}
      </div>

      {goals.day_closed && (
        <div className="mt-3.5 px-3.5 py-3 rounded-tile bg-primary-50 dark:bg-chip-dark flex items-center gap-2.5">
          <span className="w-[22px] h-[22px] rounded-full bg-primary-500 grid place-items-center flex-shrink-0">
            <Check className="h-3 w-3 text-white" strokeWidth={3} />
          </span>
          <span className="text-[13px] font-semibold text-primary-700 dark:text-primary-400">
            День закрыт — серия {goals.streak}. {goals.sparks} искр.
          </span>
        </div>
      )}
    </div>
  )
}
