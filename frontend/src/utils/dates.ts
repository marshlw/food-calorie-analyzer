/* Утилиты для работы с датами. Неделя начинается с понедельника.
   Намеренно на нативном Date, без date-fns/dayjs (минимум зависимостей). */

export const toISODate = (d: Date): string => {
  // Локальная дата без сдвига часового пояса: toISOString() даёт UTC и может
  // «съехать» на день назад для пользователей с отрицательным offset.
  const tz = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - tz).toISOString().split('T')[0]
}

export const startOfWeek = (d: Date): Date => {
  const date = new Date(d)
  const day = (date.getDay() + 6) % 7 // Пн=0 … Вс=6
  date.setDate(date.getDate() - day)
  date.setHours(0, 0, 0, 0)
  return date
}

export const addDays = (d: Date, n: number): Date => {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

export const weekDays = (weekStart: string): string[] =>
  Array.from({ length: 7 }, (_, i) => toISODate(addDays(new Date(weekStart), i)))

export const WEEKDAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

export const formatMonthYear = (weekStart: string): string =>
  new Date(weekStart).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })

/* ---------- Месяцы (вкладка «Путь») ---------- */

// 'YYYY-MM' для даты. Локальный месяц, без сдвига часового пояса.
export const toMonthKey = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`

// Сдвиг месяца: shiftMonth('2026-01', -1) -> '2025-12'.
export const shiftMonth = (month: string, delta: number): string => {
  const [y, m] = month.split('-').map(Number)
  // День 1 обязателен: new Date(y, m, 31) при переходе в короткий месяц
  // «перепрыгнул» бы через него.
  return toMonthKey(new Date(y, m - 1 + delta, 1))
}

// Строгое сравнение месяцев без парсинга дат: '2026-02' > '2026-01'.
export const isMonthAfter = (a: string, b: string): boolean => a > b
