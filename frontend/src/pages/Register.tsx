import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { ErrorAlert } from '../components/ErrorAlert'
import { UserPlus } from 'lucide-react'

export const Register: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [height, setHeight] = useState('')
  const [weight, setWeight] = useState('')
  const [localError, setLocalError] = useState('')
  const navigate = useNavigate()
  const { register, isLoading, error, clearError } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError('')

    if (!email || !password || !confirmPassword) {
      setLocalError('Email и пароль обязательны')
      return
    }

    if (password !== confirmPassword) {
      setLocalError('Пароли не совпадают')
      return
    }

    if (password.length < 8) {
      setLocalError('Пароль должен быть не менее 8 символов')
      return
    }

    const h = height ? parseFloat(height) : undefined
    const w = weight ? parseFloat(weight) : undefined
    if (h !== undefined && (isNaN(h) || h <= 0 || h >= 300)) {
      setLocalError('Рост должен быть больше 0 и меньше 300 см')
      return
    }
    if (w !== undefined && (isNaN(w) || w <= 0 || w >= 300)) {
      setLocalError('Вес должен быть больше 0 и меньше 300 кг')
      return
    }

    try {
      await register(email, password, fullName || undefined, { height_cm: h, weight_kg: w })
      navigate('/')
    } catch {
      // Error is already set by auth context
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-blue-50 dark:from-gray-900 dark:to-gray-950 px-4">
      <div className="w-full max-w-md">
        <div className="card p-8 rounded-2xl">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-full mb-4">
              <UserPlus className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold mb-2">Создать аккаунт</h1>
            <p className="text-gray-600 dark:text-gray-400">Присоединитесь к AI Healthy</p>
          </div>

          {/* Errors */}
          {(error || localError) && (
            <div className="mb-4">
              <ErrorAlert
                message={error || localError}
                onClose={clearError}
              />
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="input"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Полное имя (опционально)</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Иван Иванов"
                className="input"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Пароль</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="input"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Подтвердите пароль</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="input"
                disabled={isLoading}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium mb-1">Рост, см (опц.)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="300"
                  value={height}
                  onChange={(e) => setHeight(e.target.value)}
                  placeholder="180"
                  className="input"
                  disabled={isLoading}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Вес, кг (опц.)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="300"
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  placeholder="75"
                  className="input"
                  disabled={isLoading}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full disabled:opacity-50"
            >
              {isLoading ? 'Создание...' : 'Создать аккаунт'}
            </button>
          </form>

          {/* Login Link */}
          <div className="mt-6 text-center">
            <p className="text-gray-600 dark:text-gray-400">
              Уже есть аккаунт?{' '}
              <Link to="/login" className="text-primary-600 dark:text-primary-400 font-medium hover:underline">
                Войдите
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
