import { apiClient } from './axios'
import { User, Token, RegisterProfile } from '../types'

export const authApi = {
  register: async (
    email: string,
    password: string,
    fullName?: string,
    profile?: RegisterProfile
  ): Promise<User> => {
    const response = await apiClient.post<User>('/api/v1/register', {
      email,
      password,
      full_name: fullName,
      height_cm: profile?.height_cm,
      weight_kg: profile?.weight_kg,
      sex: profile?.sex,
      birth_date: profile?.birth_date,
      waist_cm: profile?.waist_cm,
      chest_cm: profile?.chest_cm,
      hips_cm: profile?.hips_cm,
      shoulders_cm: profile?.shoulders_cm,
    })
    return response.data
  },

  login: async (email: string, password: string): Promise<Token> => {
    const response = await apiClient.post<Token>('/api/v1/login', {
      email,
      password,
      grant_type: 'password',
    })
    return response.data
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/api/v1/me')
    return response.data
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await apiClient.post('/api/v1/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
}
