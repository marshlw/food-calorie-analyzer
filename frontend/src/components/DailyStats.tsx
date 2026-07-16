import React from 'react'
import { DailyLog } from '../types'
import { PROTEIN_TYPE_META } from '../utils/protein'

interface DailyStatsProps {
  log: DailyLog
}

// Одна колонка сводки: крупное число, подпись «из N …», мини-бар
const StatCol: React.FC<{
  value: number
  goal?: number | null
  caption: string
  barClass: string
}> = ({ value, goal, caption, barClass }) => {
  const pct = goal ? Math.min((value / goal) * 100, 100) : 0
  return (
    <div>
      <div className="font-display font-bold text-lg leading-none">{Math.round(value)}</div>
      <div className="text-[11px] text-tertiary mt-1 mb-2">{caption}</div>
      <div className="h-1 rounded-full bg-track dark:bg-track-dark overflow-hidden">
        <div className={`h-1 rounded-full ${barClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// «Сводка» дня из дизайна Rasify: 4 колонки (ккал/белки/жиры/углеводы) с барами.
// Одна доля белка (животный/растительный): точка, подпись, факт/норма
const ProteinSplit: React.FC<{
  metaKey: 'animal' | 'plant'
  value: number
  goal?: number | null
}> = ({ metaKey, value, goal }) => {
  const meta = PROTEIN_TYPE_META[metaKey]
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
      <span className="text-[11px] text-secondary">
        {meta.label}
        <span className="font-semibold text-ink dark:text-ink-dark ml-1">{Math.round(value)}</span>
        {goal ? <span className="text-tertiary"> / {Math.round(goal)} г</span> : ' г'}
      </span>
    </div>
  )
}

export const DailyStats: React.FC<DailyStatsProps> = ({ log }) => {
  const t = log.targets
  const animal = log.total_protein_animal ?? 0
  const plant = log.total_protein_plant ?? 0
  const undetermined = Math.max(0, Math.round(log.total_protein - animal - plant))
  const showSplit = animal > 0 || plant > 0

  return (
    <div className="card p-5 mb-3">
      <div className="grid grid-cols-4 gap-3">
        <StatCol
          value={log.total_calories}
          goal={t?.calories}
          caption={t?.calories ? `из ${Math.round(t.calories)} ккал` : 'ккал'}
          barClass="bg-primary-500 dark:bg-primary-400"
        />
        <StatCol
          value={log.total_protein}
          goal={t?.protein_g}
          caption={t?.protein_g ? `из ${Math.round(t.protein_g)} г белка` : 'г белка'}
          barClass="bg-protein dark:bg-protein-dark"
        />
        <StatCol
          value={log.total_fat}
          goal={t?.fat_g}
          caption={t?.fat_g ? `из ${Math.round(t.fat_g)} г жиров` : 'г жиров'}
          barClass="bg-fat dark:bg-fat-dark"
        />
        <StatCol
          value={log.total_carbs}
          goal={t?.carbs_g}
          caption={t?.carbs_g ? `из ${Math.round(t.carbs_g)} г углев.` : 'г углев.'}
          barClass="bg-carbs dark:bg-carbs-dark"
        />
      </div>

      {/* Разделение белка: животный / растительный (и «не указан», если есть) */}
      {showSplit && (
        <div className="mt-3 pt-3 border-t border-divider dark:border-line-dark flex flex-wrap items-center gap-x-4 gap-y-1.5">
          <span className="text-[11px] text-tertiary font-medium">Белок:</span>
          <ProteinSplit metaKey="animal" value={animal} goal={t?.protein_animal_g} />
          <ProteinSplit metaKey="plant" value={plant} goal={t?.protein_plant_g} />
          {undetermined > 0 && (
            <span className="text-[11px] text-tertiary">не указан {undetermined} г</span>
          )}
        </div>
      )}

      {t?.calories == null && (
        <p className="text-[11px] text-tertiary mt-3">
          Заполните профиль (рост, вес, возраст, активность), чтобы видеть нормы КБЖУ.
        </p>
      )}
    </div>
  )
}
