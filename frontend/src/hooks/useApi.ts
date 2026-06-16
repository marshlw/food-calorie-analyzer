import { useState, useCallback } from 'react'
import { extractErrorMessage } from '../utils/errors'

interface UseApiState<T> {
  data: T | null
  isLoading: boolean
  error: string | null
}

interface UseApiOptions {
  onError?: (error: string) => void
  onSuccess?: () => void
}

export const useApi = <T,>(options: UseApiOptions = {}) => {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    isLoading: false,
    error: null,
  })

  const execute = useCallback(
    async (apiCall: () => Promise<T>) => {
      setState({ data: null, isLoading: true, error: null })
      try {
        const result = await apiCall()
        setState({ data: result, isLoading: false, error: null })
        options.onSuccess?.()
        return result
      } catch (error: any) {
        const message = extractErrorMessage(error)

        setState({ data: null, isLoading: false, error: message })
        options.onError?.(message)
        throw error
      }
    },
    [options]
  )

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null })
  }, [])

  return {
    ...state,
    execute,
    reset,
  }
}
