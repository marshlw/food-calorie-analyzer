import React from 'react'
import { DailyLog, AiAnalysisLimit } from '../types'
import { ProteinBreakdown } from './ProteinBreakdown'

// Полоса макронутриента: «Белки  81 / 130 г» + прогресс-бар
const MacroBar: React.FC<{
  label: string
  value: number
  goal?: number | null
  barClass: string
}> = ({ label, value, goal, barClass }) => {
  const pct = goal ? Math.min((value / goal) * 100, 100) : 0
  return (
    <div>
      <div className="flex justify-between text-[13px] mb-1.5">
        <span className="font-medium">{label}</span>
        <span className="text-secondary">
          {Math.round(value)}
          {goal ? ` / ${Math.round(goal)}` : ''} г
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-track dark:bg-track-dark overflow-hidden">
        <div className={`h-1.5 rounded-full ${barClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

interface Props {
  log: DailyLog
  aiLimit?: AiAnalysisLimit | null
}

// Hero-карточка дневника из дизайна Rasify: большое кольцо «ккал осталось»
// + Съедено/Цель + чип AI-лимита + полосы Белки/Жиры/Углеводы.
export const HeroCard: React.FC<Props> = ({ log, aiLimit }) => {
  const goal = log.targets?.calories ?? null
  const eaten = log.total_calories
  const remaining = goal != null ? Math.round(goal - eaten) : null
  const over = remaining != null && remaining < 0

  // Кольцо: r=56, длина окружности ≈ 351.9
  const C = 2 * Math.PI * 56
  const pct = goal ? Math.min(eaten / goal, 1) : 0

  return (
    <div className="card p-6 mb-4">
      <div className="flex items-center gap-6 mb-5">
        {/* Кольцо */}
        <div className="relative grid place-items-center flex-shrink-0">
          <svg width="132" height="132" viewBox="0 0 132 132" className="-rotate-90">
            <defs>
              <linearGradient id="heroRing" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#2b6fe3" />
                <stop offset="1" stopColor="#1e56bc" />
              </linearGradient>
              <linearGradient id="heroRingDark" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#7fa8f5" />
                <stop offset="1" stopColor="#2b6fe3" />
              </linearGradient>
            </defs>
            <circle
              cx="66"
              cy="66"
              r="56"
              strokeWidth="10"
              fill="none"
              className="stroke-track dark:stroke-track-dark"
            />
            <circle
              cx="66"
              cy="66"
              r="56"
              stroke={over ? '#c0492f' : 'url(#heroRing)'}
              strokeWidth="10"
              fill="none"
              strokeLinecap="round"
              strokeDasharray={C}
              strokeDashoffset={C * (1 - pct)}
            />
          </svg>
          <div className="absolute flex flex-col items-center leading-none">
            <span className="font-display font-extrabold text-3xl">
              {remaining != null ? Math.abs(remaining) : Math.round(eaten)}
            </span>
            <span className="text-[11px] text-secondary mt-1">
              {remaining == null ? 'ккал съедено' : over ? 'ккал сверх нормы' : 'ккал осталось'}
            </span>
          </div>
        </div>

        {/* Съедено / Цель / AI-чип */}
        <div className="flex-1 flex flex-col gap-3">
          <div>
            <div className="text-xs text-tertiary">Съедено</div>
            <div className="font-display font-bold text-lg">{Math.round(eaten)} ккал</div>
          </div>
          <div>
            <div className="text-xs text-tertiary">Цель</div>
            <div className="font-display font-bold text-lg">
              {goal != null ? `${Math.round(goal)} ккал` : '—'}
            </div>
          </div>
          {aiLimit && (
            <span className="chip-ai self-start text-xs font-medium">
              ✦ {aiLimit.remaining} из {aiLimit.limit} AI
            </span>
          )}
        </div>
      </div>

      {/* Макронутриенты */}
      <div className="flex flex-col gap-3.5">
        {/* Белки + вложенная разбивка на животный/растительный */}
        <div>
          <MacroBar
            label="Белки"
            value={log.total_protein}
            goal={log.targets?.protein_g}
            barClass="bg-protein dark:bg-protein-dark"
          />
          {(log.total_protein > 0 ||
            log.targets?.protein_animal_g != null ||
            log.targets?.protein_plant_g != null) && (
            <div className="mt-2.5 ml-1 pl-3 border-l-2 border-line dark:border-line-dark">
              <ProteinBreakdown
                animal={log.total_protein_animal ?? 0}
                plant={log.total_protein_plant ?? 0}
                totalProtein={log.total_protein}
                animalGoal={log.targets?.protein_animal_g}
                plantGoal={log.targets?.protein_plant_g}
              />
            </div>
          )}
        </div>
        <MacroBar
          label="Жиры"
          value={log.total_fat}
          goal={log.targets?.fat_g}
          barClass="bg-fat dark:bg-fat-dark"
        />
        <MacroBar
          label="Углеводы"
          value={log.total_carbs}
          goal={log.targets?.carbs_g}
          barClass="bg-carbs dark:bg-carbs-dark"
        />
      </div>

      {log.targets?.calories == null && (
        <p className="text-xs text-tertiary mt-4">
          Заполните профиль (рост, вес, возраст, активность), чтобы видеть нормы КБЖУ.
        </p>
      )}
    </div>
  )
}
