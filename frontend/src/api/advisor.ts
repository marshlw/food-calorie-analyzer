import { apiClient } from './axios'
import { AdvisorResponse, AdvisorAskResponse } from '../types'

export const advisorApi = {
  // Советы дня (LLM с фолбэком на правила; бэкенд кэширует ответ)
  getAdvice: async (): Promise<AdvisorResponse> => {
    const response = await apiClient.get<AdvisorResponse>('/api/v1/advisor', {
      // LLM может думать дольше стандартных 30с axios-таймаута
      timeout: 60000,
    })
    return response.data
  },

  ask: async (question: string): Promise<AdvisorAskResponse> => {
    const response = await apiClient.post<AdvisorAskResponse>(
      '/api/v1/advisor/ask',
      { question },
      { timeout: 60000 }
    )
    return response.data
  },
}
