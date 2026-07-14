import { apiClient } from './axios'
import { Exercise } from '../types'

export const exercisesApi = {
  // Поиск по справочнику упражнений (пустой запрос — весь список)
  search: async (q: string = '', limit: number = 60): Promise<Exercise[]> => {
    const response = await apiClient.get<Exercise[]>('/api/v1/exercises', {
      params: { q, limit },
    })
    return response.data
  },
}
