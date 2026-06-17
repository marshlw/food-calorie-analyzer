import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useDiary } from '../context/DiaryContext'
import { weekDays, WEEKDAY_LABELS, formatMonthYear, toISODate } from '../utils/dates'
import { DayCell } from './DayCell'
import { ErrorAlert } from './ErrorAlert'

// Недельный обзор: Пн–Вс, переключение недель, сумма ккал по дням. Smart.
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
    <div className="card p-4 mb-6 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => shiftWeek(-1)}
          aria-label="Предыдущая неделя"
          className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <span className="text-sm font-semibold capitalize">{formatMonthYear(weekStart)}</span>
        <button
          onClick={() => shiftWeek(1)}
          aria-label="Следующая неделя"
          className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      {weekError && (
        <div className="mb-3">
          <ErrorAlert message={weekError} onClose={() => reloadWeek()} />
        </div>
      )}

      <div className="grid grid-cols-7 gap-1">
        {days.map((date, i) => {
          const log = weekLogs[date]
          // Скелетон, пока неделя грузится и данных по дню ещё нет
          if (weekStatus === 'loading' && !log) {
            return (
              <div
                key={date}
                className="h-24 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse"
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
