import React from 'react'
import { GoalReward } from '../../types'

interface Props {
  rewards: GoalReward[]
}

// «Награды»: вехи серии. Достигнутая веха остаётся достигнутой навсегда —
// сорванная серия не должна отбирать уже заработанный бейдж.
export const RewardsCard: React.FC<Props> = ({ rewards }) => {
  if (rewards.length === 0) return null

  return (
    <div className="card p-[18px] mb-3">
      <div className="font-display font-bold text-[15px] mb-3">Награды</div>

      <div className="flex flex-col gap-2">
        {rewards.map((r) => (
          <div
            key={r.code}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-tile border ${
              r.reached
                ? 'bg-primary-50 dark:bg-chip-dark border-primary-200 dark:border-primary-800'
                : 'bg-[#f9fafc] dark:bg-surface-dark border-line dark:border-line-dark'
            }`}
          >
            <span
              className={`w-[34px] h-[34px] flex-shrink-0 rounded-[10px] grid place-items-center
                font-display font-extrabold text-[13px] ${
                  r.reached
                    ? 'bg-primary-500 text-white'
                    : 'bg-track dark:bg-line-dark text-faint dark:text-faint-dark'
                }`}
            >
              {r.mark}
            </span>
            <span className="flex-1 min-w-0">
              <span
                className={`block text-[13px] font-semibold ${r.reached ? '' : 'text-secondary'}`}
              >
                {r.title}
              </span>
              <span className="block text-[11px] text-tertiary mt-0.5">{r.subtitle}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
