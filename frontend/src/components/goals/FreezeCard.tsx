import React from 'react'

interface Props {
  freezes: number
  busy?: boolean
  onApply: () => void
}

// «Заморозка серии»: расходуемый щит на день без записей.
// По умолчанию применяется ко вчерашнему дню — типичный сценарий
// «вчера забыл записать, спасите серию».
export const FreezeCard: React.FC<Props> = ({ freezes, busy, onApply }) => (
  <div className="card p-[18px] mb-3 flex items-center gap-3">
    <div className="flex-1 min-w-0">
      <div className="font-display font-bold text-[15px]">Заморозка серии</div>
      <div className="text-xs text-secondary mt-1">
        Сохранит серию за вчерашний день без записей. Осталось: {freezes}.
      </div>
    </div>
    <button
      type="button"
      onClick={onApply}
      disabled={busy || freezes <= 0}
      className="btn-outline flex-shrink-0 !px-4 !py-2.5 !text-[13px] disabled:opacity-40"
    >
      Применить
    </button>
  </div>
)
