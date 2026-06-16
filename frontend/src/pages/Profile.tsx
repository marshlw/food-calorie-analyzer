import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { LogOut, Settings } from 'lucide-react'

export const Profile: React.FC = () => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [isDarkMode, setIsDarkMode] = useState(() => {
    return localStorage.getItem('theme') === 'dark'
  })

  useEffect(() => {
    const root = document.documentElement
    if (isDarkMode) {
      root.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDarkMode])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Профиль</h1>
      </div>

      {/* User Info */}
      <div className="card p-6 mb-6 rounded-xl">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
            {user?.email?.[0]?.toUpperCase()}
          </div>
          <div>
            <h2 className="text-xl font-semibold">{user?.full_name || 'User'}</h2>
            <p className="text-gray-600 dark:text-gray-400">{user?.email}</p>
          </div>
        </div>

        <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Зарегистрирован: {new Date(user?.created_at || '').toLocaleDateString('ru-RU')}
          </p>
        </div>
      </div>

      {/* Settings */}
      <div className="card p-4 mb-6 rounded-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Settings className="h-5 w-5 text-gray-600 dark:text-gray-400" />
            <span>Тёмная тема</span>
          </div>
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              isDarkMode ? 'bg-primary-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                isDarkMode ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Logout */}
      <button
        onClick={handleLogout}
        className="btn-danger w-full flex items-center justify-center gap-2"
      >
        <LogOut className="h-4 w-4" />
        Выход
      </button>
    </div>
  )
}
