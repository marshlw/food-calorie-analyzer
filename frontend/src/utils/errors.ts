import { AxiosError } from 'axios'
import { ApiError } from '../types'

/**
 * Приводит любую ошибку (в т.ч. FastAPI-валидацию с detail в виде массива
 * объектов { loc, msg, type }) к читаемой строке.
 */
export const extractErrorMessage = (
  error: unknown,
  fallback = 'Произошла ошибка'
): string => {
  const axiosError = error as AxiosError<ApiError>
  const detail = axiosError?.response?.data?.detail

  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => (typeof d === 'string' ? d : d?.msg))
      .filter(Boolean)
    if (parts.length) return parts.join(', ')
  } else if (typeof detail === 'string' && detail) {
    return detail
  }

  const message = axiosError?.response?.data?.message
  if (message) return message

  if (error instanceof Error && error.message) return error.message

  return fallback
}
