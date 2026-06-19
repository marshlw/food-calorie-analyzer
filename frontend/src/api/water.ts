import { apiClient } from './axios'
import { WaterStatus } from '../types'

export const waterApi = {
  getWater: async (dateStr?: string): Promise<WaterStatus> => {
    const response = await apiClient.get<WaterStatus>('/api/v1/water', {
      params: dateStr ? { date_str: dateStr } : undefined,
    })
    return response.data
  },

  // amount_ml может быть отрицательным (убрать стакан). Без amount_ml
  // бэкенд добавит один стакан. date — день записи (по умолчанию сегодня).
  updateWater: async (amountMl?: number, dateStr?: string): Promise<WaterStatus> => {
    const response = await apiClient.post<WaterStatus>('/api/v1/water', {
      amount_ml: amountMl,
      date: dateStr,
    })
    return response.data
  },
}
