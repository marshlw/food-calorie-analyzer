import React from 'react'

export interface SegmentOption<T extends string> {
  value: T
  label: string
}

interface Props<T extends string> {
  value: T
  options: SegmentOption<T>[]
  onChange: (value: T) => void
  ariaLabel?: string
}

// Сегментированный переключатель из дизайна Rasify: серая подложка,
// активный сегмент — белая «таблетка» с тенью.
export function SegmentedTabs<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: Props<T>): React.ReactElement {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="flex gap-1 p-1 bg-track dark:bg-line-dark rounded-cell mb-4"
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={`flex-1 py-2.5 rounded-[11px] text-[13px] transition-colors ${
              active
                ? 'bg-white dark:bg-card-dark shadow-card font-semibold'
                : 'font-medium text-secondary hover:text-ink dark:hover:text-ink-dark'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
