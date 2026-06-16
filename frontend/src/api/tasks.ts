import { apiClient } from './axios'
import { Task, TaskResponse } from '../types'

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

  getTask: async (taskId: string): Promise<TaskResponse> => {
    const response = await apiClient.get<TaskResponse>(`/api/v1/task/${taskId}`)
    
    // Parse result_json if available
    if (response.data.result_json) {
      try {
        response.data.result = JSON.parse(response.data.result_json)
      } catch {
        response.data.result = undefined
      }
    }
    
    return response.data
  },

  getTasks: async (limit: number = 50, offset: number = 0): Promise<TaskResponse[]> => {
    const response = await apiClient.get<TaskResponse[]>('/api/v1/tasks', {
      params: { limit, offset },
    })
    
    return response.data.map(task => {
      if (task.result_json) {
        try {
          task.result = JSON.parse(task.result_json)
        } catch {
          task.result = undefined
        }
      }
      return task
    })
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
