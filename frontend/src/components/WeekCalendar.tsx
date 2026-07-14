import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useDiary } from '../context/DiaryContext'
import { weekDays, WEEKDAY_LABELS, formatMonthYear, toISODate } from '../utils/dates'
import { DayCell } from './DayCell'
import { ErrorAlert } from './ErrorAlert'

// Недельный обзор: Пн–Вс, переключение недель, прогресс калорий по дням. Smart.
export const WeekCalendar: React.FC = () => {
  const {
    weekStart,
    weekLogs,
    weekStatus,
    weekError,
    selectedDate,
    selectDate,
    shiftWeek,
    reloadWeek,
  } = useDiary()

  const days = weekDays(weekStart)
  const today = toISODate(new Date())

  return (
    <div className="mb-5">
      {/* Месяц + переключение недель */}
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => shiftWeek(-1)}
          aria-label="Предыдущая неделя"
          className="p-1.5 rounded-full text-muted dark:text-muted-dark hover:bg-white dark:hover:bg-chip-dark transition-colors"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <span className="text-[13px] text-secondary capitalize">{formatMonthYear(weekStart)}</span>
        <button
          onClick={() => shiftWeek(1)}
          aria-label="Следующая неделя"
          className="p-1.5 rounded-full text-muted dark:text-muted-dark hover:bg-white dark:hover:bg-chip-dark transition-colors"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      {weekError && (
        <div className="mb-3">
          <ErrorAlert message={weekError} onClose={() => reloadWeek()} />
        </div>
      )}

      <div className="grid grid-cols-7 gap-1.5">
        {days.map((date, i) => {
          const log = weekLogs[date]
          // Скелетон, пока неделя грузится и данных по дню ещё нет
          if (weekStatus === 'loading' && !log) {
            return (
              <div
                key={date}
                className="h-[74px] rounded-cell bg-white/60 dark:bg-card-dark animate-pulse border border-line dark:border-line-dark"
              />
            )
          }
          return (
            <DayCell
              key={date}
              label={WEEKDAY_LABELS[i]}
              dayNum={new Date(date).getDate()}
              calories={log?.total_calories ?? 0}
              goal={log?.targets?.calories ?? undefined}
              hasMeals={(log?.meals.length ?? 0) > 0}
              isSelected={date === selectedDate}
              isToday={date === today}
              onClick={() => selectDate(date)}
            />
          )
        })}
      </div>
    </div>
  )
}
