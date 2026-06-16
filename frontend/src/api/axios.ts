import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { Token } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

console.log('API Base URL:', API_BASE_URL)

let tokenRefreshPromise: Promise<Token> | null = null

const createAxiosInstance = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // Request interceptor to add auth token
  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      console.log('Request:', {
        url: config.url,
        method: config.method,
        headers: config.headers,
      })
      return config
    },
    (error) => {
      console.error('Request error:', error)
      return Promise.reject(error)
    }
  )

  // Response interceptor to handle token refresh
  instance.interceptors.response.use(
    (response) => {
      console.log('Response success:', {
        url: response.config.url,
        status: response.status,
      })
      return response
    },
    async (error: AxiosError) => {
      console.error('Response error:', {
        url: error.config?.url,
        status: error.response?.status,
        data: error.response?.data,
      })

      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true

        try {
          // If already refreshing token, wait for it
          if (tokenRefreshPromise) {
            const newToken = await tokenRefreshPromise
            originalRequest.headers.Authorization = `Bearer ${newToken.access_token}`
            return instance(originalRequest)
          }

          // Refresh token
          tokenRefreshPromise = refreshAccessToken()
          const newToken = await tokenRefreshPromise
          tokenRefreshPromise = null

          localStorage.setItem('access_token', newToken.access_token)
          localStorage.setItem('refresh_token', newToken.refresh_token)

          originalRequest.headers.Authorization = `Bearer ${newToken.access_token}`
          return instance(originalRequest)
        } catch (refreshError) {
          tokenRefreshPromise = null
          // Clear auth data and let app redirect to login
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
          return Promise.reject(refreshError)
        }
      }

      return Promise.reject(error)
    }
  )

  return instance
}

export const apiClient = createAxiosInstance()

const refreshAccessToken = async (): Promise<Token> => {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    throw new Error('No refresh token available')
  }

  const response = await axios.post<Token>(`${API_BASE_URL}/api/v1/token`, {
    grant_type: 'refresh_token',
    refresh_token: refreshToken,
  })

  return response.data
}

export const setAuthTokens = (token: Token) => {
  localStorage.setItem('access_token', token.access_token)
  localStorage.setItem('refresh_token', token.refresh_token)
}

export const clearAuthTokens = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export const getAuthTokens = (): Token | null => {
  const accessToken = localStorage.getItem('access_token')
  const refreshToken = localStorage.getItem('refresh_token')
  
  if (!accessToken || !refreshToken) {
    return null
  }

  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    token_type: 'bearer',
  }
}
