import { apiClient, API_BASE_URL } from './axios'
import { AiAnalysisLimit, Task, TaskResponse } from '../types'

// Бэкенд отдаёт image_path как относительный URL вида /uploads/<file>.
// Превращаем его в абсолютный, т.к. фронтенд может работать на другом origin.
const resolveImageUrl = <T extends { image_path?: string }>(task: T): T => {
  if (task.image_path && task.image_path.startsWith('/')) {
    task.image_path = `${API_BASE_URL}${task.image_path}`
  }
  return task
}

export const tasksApi = {
  uploadImage: async (file: File): Promise<Task> => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiClient.post<Task>('/api/v1/analyze', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // Сколько AI-анализов осталось на сегодня
  getAnalysisLimit: async (): Promise<AiAnalysisLimit> => {
    const response = await apiClient.get<AiAnalysisLimit>('/api/v1/analyze/limit')
    return response.data
  },

  getTask: async (taskId: string): Promise<TaskResponse> => {
    const response = await apiClient.get<TaskResponse>(`/api/v1/task/${taskId}`)
    // Бэкенд уже возвращает распарсенный result, дополнительный парсинг не нужен.
    return resolveImageUrl(response.data)
  },

  getTasks: async (limit: number = 50, offset: number = 0): Promise<TaskResponse[]> => {
    const response = await apiClient.get<TaskResponse[]>('/api/v1/tasks', {
      params: { limit, offset },
    })
    return response.data.map(resolveImageUrl)
  },

  submitFeedback: async (
    taskId: string,
    correctFood: string,
    correctWeight: number
  ): Promise<{ status: string; id: number }> => {
    const response = await apiClient.post('/api/v1/feedback', {
      task_id: taskId,
      correct_food: correctFood,
      correct_weight: correctWeight,
    })
    return response.data
  },
}
