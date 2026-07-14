import React from 'react'
import { AiAnalysisLimit } from '../types'

interface Props {
  aiLimit: AiAnalysisLimit | null
}

// Счётчик оставшихся AI-анализов на сегодня (чип «✦ 3 из 5 AI» из дизайна).
export const AiLimitBadge: React.FC<Props> = ({ aiLimit }) => {
  if (!aiLimit) return null

  const exhausted = aiLimit.remaining <= 0

  return (
    <div className="flex justify-center mb-6">
      <span
        className={`chip font-medium text-xs ${
          exhausted
            ? 'bg-fat-chip text-fat-text dark:bg-fat-dark/15 dark:text-fat-dark'
            : 'bg-primary-50 text-primary-500 dark:bg-chip-dark dark:text-primary-400'
        }`}
      >
        ✦{' '}
        {exhausted
          ? 'Лимит AI-анализов на сегодня исчерпан'
          : `${aiLimit.remaining} из ${aiLimit.limit} AI`}
      </span>
    </div>
  )
}
