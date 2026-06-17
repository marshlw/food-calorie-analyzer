import { apiClient } from './axios'
import { Profile, ProfileUpdate, WeightRecord, WeightRecordCreate } from '../types'

export const profileApi = {
  getProfile: async (): Promise<Profile> => {
    const response = await apiClient.get<Profile>('/api/v1/profile')
    return response.data
  },

  updateProfile: async (payload: ProfileUpdate): Promise<Profile> => {
    const response = await apiClient.put<Profile>('/api/v1/profile', payload)
    return response.data
  },

  addWeight: async (payload: WeightRecordCreate): Promise<WeightRecord> => {
    const response = await apiClient.post<WeightRecord>('/api/v1/profile/weight', payload)
    return response.data
  },

  getWeightHistory: async (start?: string, end?: string): Promise<WeightRecord[]> => {
    const response = await apiClient.get<WeightRecord[]>('/api/v1/profile/weight-history', {
      params: start || end ? { start, end } : undefined,
    })
    return response.data
  },
}
