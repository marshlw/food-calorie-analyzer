import { apiClient } from './axios'
import { GoalsToday, GoalPath } from '../types'

// «Цели»: цель дня, серия, путь месяца, награды и заморозки.
// Правила (пороги, склонения, тексты) считает бэкенд — фронт их не дублирует.
export const goalsApi = {
  // Цели дня и серия. dateStr — выбранный день (по умолчанию сегодня).
  getToday: async (dateStr?: string): Promise<GoalsToday> => {
    const response = await apiClient.get<GoalsToday>('/api/v1/goals/today', {
      params: dateStr ? { date_str: dateStr } : undefined,
    })
    return response.data
  },

  // «Путь месяца». month — 'YYYY-MM' (по умолчанию текущий месяц).
  getPath: async (month?: string): Promise<GoalPath> => {
    const response = await apiClient.get<GoalPath>('/api/v1/goals/path', {
      params: month ? { month } : undefined,
    })
    return response.data
  },

  // Потратить заморозку и спасти серию. Без даты бэкенд возьмёт вчера.
  useFreeze: async (dateStr?: string): Promise<GoalsToday> => {
    const response = await apiClient.post<GoalsToday>('/api/v1/goals/freeze', {
      date: dateStr,
    })
    return response.data
  },
}
