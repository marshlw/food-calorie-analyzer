import React from 'react'
import { PROTEIN_TYPE_META } from '../utils/protein'

interface Props {
  // Съедено (г): животный / растительный
  animal: number
  plant: number
  // Общий белок — знаменатель для доли источника, когда нормы нет
  totalProtein: number
  // Суточные нормы (г); null/undefined — если профиль не заполнен
  animalGoal?: number | null
  plantGoal?: number | null
  // Заголовок над блоком (для «Приёмов»); в «Дневнике» блок вложен под «Белки»,
  // поэтому заголовок не нужен.
  heading?: string
}

// Одна мелкая шкала источника белка: подпись + факт/норма + тонкий прогресс-бар.
// barMax — знаменатель для ширины бара: норма (прогресс к цели) или общий белок
// приёма (доля источника), если нормы нет.
const MiniBar: React.FC<{
  label: string
  value: number
  goal?: number | null
  barMax?: number | null
  dotClass: string
}> = ({ label, value, goal, barMax, dotClass }) => {
  const denom = barMax ?? goal ?? 0
  const pct = denom ? Math.min((value / denom) * 100, 100) : 0
  return (
    <div>
      <div className="flex justify-between items-center text-[11px] mb-1">
        <span className="flex items-center gap-1.5 text-secondary">
          <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
          {label}
        </span>
        <span className="text-secondary tabular-nums">
          <span className="font-semibold text-ink dark:text-ink-dark">{Math.round(value)}</span>
          {goal ? ` / ${Math.round(goal)}` : ''} г
        </span>
      </div>
      <div className="h-1 rounded-full bg-track dark:bg-track-dark overflow-hidden">
        <div className={`h-1 rounded-full ${dotClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// Разбивка белка на животный/растительный (две мелкие шкалы).
// Используется под шкалой «Белки» в Дневнике, в сводке дня на Приёмах
// и в раскрытой карточке приёма.
export const ProteinBreakdown: React.FC<Props> = ({
  animal,
  plant,
  totalProtein,
  animalGoal,
  plantGoal,
  heading,
}) => {
  // Нет норм → бар показывает долю источника внутри белка приёма (композиция).
  const hasGoals = animalGoal != null || plantGoal != null
  const shareMax = hasGoals ? undefined : totalProtein

  return (
    <div className="flex flex-col gap-2">
      {heading && (
        <div className="text-[11px] font-semibold text-tertiary uppercase tracking-wide">
          {heading}
        </div>
      )}
      <MiniBar
        label={PROTEIN_TYPE_META.animal.label}
        value={animal}
        goal={animalGoal}
        barMax={shareMax}
        dotClass={PROTEIN_TYPE_META.animal.dot}
      />
      <MiniBar
        label={PROTEIN_TYPE_META.plant.label}
        value={plant}
        goal={plantGoal}
        barMax={shareMax}
        dotClass={PROTEIN_TYPE_META.plant.dot}
      />
    </div>
  )
}
