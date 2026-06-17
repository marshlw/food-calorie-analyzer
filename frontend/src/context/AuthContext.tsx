import React, { createContext, useReducer, useCallback, useEffect } from 'react'
import { User, Token, AuthContextType } from '../types'
import { authApi } from '../api/auth'
import { setAuthTokens, clearAuthTokens, getAuthTokens } from '../api/axios'
import { extractErrorMessage } from '../utils/errors'

interface AuthState {
  user: User | null
  token: Token | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

type AuthAction =
  | { type: 'LOGIN_START' }
  | { type: 'LOGIN_SUCCESS'; payload: { user: User; token: Token } }
  | { type: 'LOGIN_ERROR'; payload: string }
  | { type: 'REGISTER_SUCCESS'; payload: { user: User; token: Token } }
  | { type: 'LOGOUT' }
  | { type: 'RESTORE_SESSION'; payload: { user: User; token: Token } }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_ERROR'; payload: string }

const initialState: AuthState = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
}

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case 'LOGIN_START':
      return { ...state, isLoading: true, error: null }
    case 'LOGIN_SUCCESS':
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      }
    case 'LOGIN_ERROR':
      return { ...state, isLoading: false, error: action.payload, isAuthenticated: false }
    case 'REGISTER_SUCCESS':
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      }
    case 'LOGOUT':
      return { ...initialState, isLoading: false }
    case 'RESTORE_SESSION':
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        isLoading: false,
      }
    case 'CLEAR_ERROR':
      return { ...state, error: null }
    case 'SET_ERROR':
      return { ...state, error: action.payload }
    default:
      return state
  }
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: React.ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, { ...initialState, isLoading: true })

  // Restore session from localStorage on mount
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const token = getAuthTokens()
        if (token) {
          const user = await authApi.getMe()
          dispatch({ type: 'RESTORE_SESSION', payload: { user, token } })
        } else {
          dispatch({ type: 'LOGOUT' })
        }
      } catch {
        dispatch({ type: 'LOGOUT' })
      }
    }

    restoreSession()
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    dispatch({ type: 'LOGIN_START' })
    try {
      const token = await authApi.login(email, password)
      setAuthTokens(token)
      const user = await authApi.getMe()
      dispatch({ type: 'LOGIN_SUCCESS', payload: { user, token } })
    } catch (error: any) {
      const message = extractErrorMessage(error, 'Login failed')
      dispatch({ type: 'LOGIN_ERROR', payload: message })
      throw error
    }
  }, [])

  const register = useCallback(async (
    email: string,
    password: string,
    fullName?: string,
    profile?: { height_cm?: number; weight_kg?: number }
  ) => {
    dispatch({ type: 'LOGIN_START' })
    try {
      const user = await authApi.register(email, password, fullName, profile)
      const token = await authApi.login(email, password)
      setAuthTokens(token)
      dispatch({ type: 'REGISTER_SUCCESS', payload: { user, token } })
    } catch (error: any) {
      const message = extractErrorMessage(error, 'Registration failed')
      dispatch({ type: 'LOGIN_ERROR', payload: message })
      throw error
    }
  }, [])

  const logout = useCallback(() => {
    clearAuthTokens()
    dispatch({ type: 'LOGOUT' })
  }, [])

  const clearError = useCallback(() => {
    dispatch({ type: 'CLEAR_ERROR' })
  }, [])

  const value: AuthContextType = {
    user: state.user,
    token: state.token,
    isAuthenticated: state.isAuthenticated,
    isLoading: state.isLoading,
    error: state.error,
    login,
    register,
    logout,
    clearError,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
