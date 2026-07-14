import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { ErrorAlert } from '../components/ErrorAlert'
import { PasswordInput } from '../components/PasswordInput'
import { RingLogo } from '../components/Brand'

// Экран входа из дизайна Rasify: кольцо-логотип, словомарка, белая карточка.
export const Login: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState('')
  const navigate = useNavigate()
  const { login, isLoading, error, clearError } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError('')

    if (!email || !password) {
      setLocalError('Email и пароль обязательны')
      return
    }

    try {
      await login(email, password)
      navigate('/')
    } catch {
      // Error is already set by auth context
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface dark:bg-surface-dark px-6 py-10">
      <div className="w-full max-w-md">
        {/* Логотип */}
        <div className="text-center mb-9">
          <RingLogo size={64} className="mb-4 inline-block" />
          <h1 className="font-display font-extrabold text-[32px] leading-none tracking-tight mb-2.5">
            Rasify
          </h1>
          <p className="text-sm text-secondary">Умный дневник питания</p>
        </div>

        {/* Errors */}
        {(error || localError) && (
          <div className="mb-4">
            <ErrorAlert message={error || localError} onClose={clearError} />
          </div>
        )}

        {/* Карточка формы */}
        <div className="card p-7">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-[13px] font-semibold mb-1.5">Email</label>
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
              <label className="block text-[13px] font-semibold mb-1.5">Пароль</label>
              <PasswordInput
                value={password}
                onChange={setPassword}
                disabled={isLoading}
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full mt-1 disabled:opacity-50"
            >
              {isLoading ? 'Вход...' : 'Войти'}
            </button>
          </form>
        </div>

        {/* Registration Link */}
        <div className="mt-6 text-center">
          <p className="text-sm text-secondary">
            Нет аккаунта?{' '}
            <Link
              to="/register"
              className="font-semibold text-primary-500 dark:text-primary-400 hover:text-primary-700"
            >
              Зарегистрируйтесь
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
