import { apiClient } from './axios'
import { MealEntry, MealEntryCreate, DailyLog } from '../types'
import { weekDays } from '../utils/dates'

export const mealsApi = {
  addMeal: async (meal: MealEntryCreate): Promise<MealEntry> => {
    const response = await apiClient.post<MealEntry>('/api/v1/meals', meal)
    return response.data
  },

  addMealFromAnalysis: async (taskId: string, mealType: string): Promise<MealEntry> => {
    const response = await apiClient.post<MealEntry>('/api/v1/meals/from-analysis', {
      task_id: taskId,
      meal_type: mealType,
    })
    return response.data
  },

  updateMeal: async (mealId: number, meal: MealEntryCreate): Promise<MealEntry> => {
    const response = await apiClient.patch<MealEntry>(`/api/v1/meals/${mealId}`, meal)
    return response.data
  },

  deleteMeal: async (mealId: number): Promise<{ status: string; deleted_id: number }> => {
    const response = await apiClient.delete(`/api/v1/meals/${mealId}`)
    return response.data
  },

  // Прикрепить/заменить фото записи (multipart). Бэкенд вернёт запись
  // с обновлённым photo_url.
  uploadMealPhoto: async (mealId: number, file: File): Promise<MealEntry> => {
    const form = new FormData()
    form.append('file', file)
    const response = await apiClient.post<MealEntry>(`/api/v1/meals/${mealId}/photo`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  // Удалить добавленное вручную фото (для AI-записей photo_url
  // вернётся к фото анализа).
  deleteMealPhoto: async (mealId: number): Promise<MealEntry> => {
    const response = await apiClient.delete<MealEntry>(`/api/v1/meals/${mealId}/photo`)
    return response.data
  },

  getDailyLog: async (dateStr?: string): Promise<DailyLog> => {
    const response = await apiClient.get<DailyLog>('/api/v1/daily-log', {
      params: dateStr ? { date_str: dateStr } : undefined,
    })
    return response.data
  },

  // Недельный обзор: 7 параллельных запросов к daily-log.
  // Когда на бэкенде появится /api/v1/weekly-log, заменить тело на 1 запрос.
  getWeekLogs: async (weekStart: string): Promise<Record<string, DailyLog>> => {
    const dates = weekDays(weekStart)
    const logs = await Promise.all(dates.map((d) => mealsApi.getDailyLog(d)))
    return dates.reduce<Record<string, DailyLog>>((acc, d, i) => {
      acc[d] = logs[i]
      return acc
    }, {})
  },
}
