import { useState, useRef, useCallback, useEffect } from 'react'
import { tasksApi } from '../api/tasks'
import { TaskResponse } from '../types'
import { extractErrorMessage } from '../utils/errors'

type Phase = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error'

const MAX_ATTEMPTS = 120 // ~2 минуты при шаге 1с

// Инкапсулирует загрузку фото + асинхронный поллинг задачи анализа.
export const useFoodAnalysis = () => {
  const [phase, setPhase] = useState<Phase>('idle')
  const [task, setTask] = useState<TaskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const objectUrl = useRef<string | null>(null)

  const poll = useCallback((id: string, attempts = 0) => {
    if (attempts > MAX_ATTEMPTS) {
      setError('Анализ занял слишком много времени, попробуйте снова')
      setPhase('error')
      return
    }
    tasksApi
      .getTask(id)
      .then((t) => {
        setTask(t)
        if (t.status === 'success') {
          setPhase('done')
        } else if (t.status === 'failure') {
          setError(t.error || 'Не удалось распознать блюдо')
          setPhase('error')
        } else {
          timer.current = setTimeout(() => poll(id, attempts + 1), 1000)
        }
      })
      .catch(() => {
        // Временная сетевая ошибка во время поллинга — повторяем
        timer.current = setTimeout(() => poll(id, attempts + 1), 1000)
      })
  }, [])

  const analyze = useCallback(
    async (file: File) => {
      setError(null)
      setPhase('uploading')

      // Мгновенное локальное превью, не дожидаясь сервера
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
      objectUrl.current = URL.createObjectURL(file)
      setPreviewUrl(objectUrl.current)

      try {
        const created = await tasksApi.uploadImage(file)
        setPhase('analyzing')
        poll(created.id)
      } catch (e) {
        setError(extractErrorMessage(e))
        setPhase('error')
      }
    },
    [poll]
  )

  const reset = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    if (objectUrl.current) {
      URL.revokeObjectURL(objectUrl.current)
      objectUrl.current = null
    }
    setPhase('idle')
    setTask(null)
    setError(null)
    setPreviewUrl(null)
  }, [])

  // Чистим таймер и object URL при размонтировании
  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current)
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
    }
  }, [])

  return { phase, task, error, previewUrl, analyze, reset }
}
