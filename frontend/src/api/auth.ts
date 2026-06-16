import { apiClient } from './axios'
import { User, Token } from '../types'

export const authApi = {
  register: async (email: string, password: string, fullName?: string): Promise<User> => {
    const response = await apiClient.post<User>('/api/v1/register', {
      email,
      password,
      full_name: fullName,
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
