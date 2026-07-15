import { apiClient } from './axios'
import { Workout, WorkoutCreate, WorkoutsResponse } from '../types'

export const workoutsApi = {
  // Тренировки за день + сводка активности + недельная полоска
  getWorkouts: async (dateStr?: string): Promise<WorkoutsResponse> => {
    const response = await apiClient.get<WorkoutsResponse>('/api/v1/workouts', {
      params: dateStr ? { date_str: dateStr } : undefined,
    })
    return response.data
  },

  addWorkout: async (payload: WorkoutCreate): Promise<Workout> => {
    const response = await apiClient.post<Workout>('/api/v1/workouts', payload)
    return response.data
  },

  updateWorkout: async (workoutId: number, payload: WorkoutCreate): Promise<Workout> => {
    const response = await apiClient.put<Workout>(`/api/v1/workouts/${workoutId}`, payload)
    return response.data
  },

  deleteWorkout: async (workoutId: number): Promise<{ status: string; deleted_id: number }> => {
    const response = await apiClient.delete(`/api/v1/workouts/${workoutId}`)
    return response.data
  },
}
