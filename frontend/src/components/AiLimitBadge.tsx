import React from 'react'
import { Sparkles } from 'lucide-react'
import { AiAnalysisLimit } from '../types'

interface Props {
  aiLimit: AiAnalysisLimit | null
}

// Счётчик оставшихся AI-анализов на сегодня (под кнопкой «Анализ фото»).
export const AiLimitBadge: React.FC<Props> = ({ aiLimit }) => {
  if (!aiLimit) return null

  const exhausted = aiLimit.remaining <= 0

  return (
    <p
      className={`flex items-center justify-center gap-1 text-xs mb-6 ${
        exhausted
          ? 'text-amber-600 dark:text-amber-400'
          : 'text-gray-500 dark:text-gray-400'
      }`}
    >
      <Sparkles className="h-3.5 w-3.5" />
      {exhausted
        ? 'Дневной лимит AI-анализов исчерпан — будет доступно завтра'
        : `AI-анализов осталось сегодня: ${aiLimit.remaining} из ${aiLimit.limit}`}
    </p>
  )
}
