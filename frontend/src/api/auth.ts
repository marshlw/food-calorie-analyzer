import { apiClient } from './axios'
import { User, Token } from '../types'

export const authApi = {
  register: async (
    email: string,
    password: string,
    fullName?: string,
    profile?: { height_cm?: number; weight_kg?: number }
  ): Promise<User> => {
    const response = await apiClient.post<User>('/api/v1/register', {
      email,
      password,
      full_name: fullName,
      height_cm: profile?.height_cm,
      weight_kg: profile?.weight_kg,
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
}
