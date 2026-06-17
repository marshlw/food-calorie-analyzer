import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Settings, Plus, AlertCircle, Flame } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { profileApi } from '../api/profile'
import { Profile as ProfileType, ProfileUpdate, WeightRecordCreate } from '../types'
import { extractErrorMessage } from '../utils/errors'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { ProfileForm } from '../components/profile/ProfileForm'
import { WeightChart } from '../components/profile/WeightChart'
import { WeightHistoryList } from '../components/profile/WeightHistoryList'
import { AddWeightModal } from '../components/profile/AddWeightModal'

export const Profile: React.FC = () => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [profile, setProfile] = useState<ProfileType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)

  const [isDarkMode, setIsDarkMode] = useState(() => localStorage.getItem('theme') === 'dark')

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

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setProfile(await profileApi.getProfile())
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleSaveProfile = async (payload: ProfileUpdate) => {
    setProfile(await profileApi.updateProfile(payload))
  }

  const handleAddWeight = async (payload: WeightRecordCreate) => {
    await profileApi.addWeight(payload)
    await load() // перечитываем, чтобы график/история/текущий вес обновились
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Профиль</h1>
      </div>

      {/* User Info */}
      <div className="card p-6 mb-6 rounded-xl">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
            {user?.email?.[0]?.toUpperCase()}
          </div>
          <div>
            <h2 className="text-xl font-semibold">{profile?.full_name || user?.full_name || 'User'}</h2>
            <p className="text-gray-600 dark:text-gray-400">{user?.email}</p>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner />}

      {!loading && error && (
        <div className="mb-6">
          <ErrorAlert message={error} onClose={() => setError(null)} />
          <button onClick={load} className="btn-secondary w-full mt-3">
            Повторить
          </button>
        </div>
      )}

      {!loading && !error && profile && (
        <div className="space-y-6">
          {/* Напоминание о незаполненном профиле (не блокирует работу) */}
          {!profile.height_cm && (
            <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-4 flex gap-3">
              <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-700 dark:text-amber-400">
                Заполните рост и вес — это нужно для расчёта нормы калорий.
              </p>
            </div>
          )}

          {/* Сводка: текущий вес + норма калорий */}
          <div className="grid grid-cols-2 gap-3">
            <div className="card p-4 rounded-xl">
              <p className="text-xs text-gray-500 mb-1">Текущий вес</p>
              <p className="text-2xl font-bold">
                {profile.current_weight_kg != null ? `${profile.current_weight_kg} кг` : '—'}
              </p>
            </div>
            <div className="card p-4 rounded-xl">
              <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                <Flame className="h-3.5 w-3.5" /> Норма калорий
              </p>
              <p className="text-2xl font-bold">
                {profile.daily_calorie_target != null
                  ? `${profile.daily_calorie_target}`
                  : '—'}
              </p>
            </div>
          </div>

          {/* Суточные нормы БЖУ */}
          <div className="card p-4 rounded-xl">
            <p className="text-xs text-gray-500 mb-3">Суточная норма КБЖУ</p>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                <p className="text-xs text-red-600 dark:text-red-400 mb-1">Белки</p>
                <p className="text-lg font-bold">
                  {profile.protein_target_g != null ? `${profile.protein_target_g} г` : '—'}
                </p>
              </div>
              <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
                <p className="text-xs text-yellow-600 dark:text-yellow-400 mb-1">Жиры</p>
                <p className="text-lg font-bold">
                  {profile.fat_target_g != null ? `${profile.fat_target_g} г` : '—'}
                </p>
              </div>
              <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                <p className="text-xs text-green-600 dark:text-green-400 mb-1">Углеводы</p>
                <p className="text-lg font-bold">
                  {profile.carbs_target_g != null ? `${profile.carbs_target_g} г` : '—'}
                </p>
              </div>
            </div>
            {profile.daily_calorie_target == null && (
              <p className="text-xs text-gray-400 mt-3">
                Заполните рост, вес, дату рождения и активность ниже — и нормы рассчитаются автоматически.
              </p>
            )}
          </div>

          {/* График + кнопка добавления */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">Прогресс</h3>
              <button
                onClick={() => setAddOpen(true)}
                className="btn-primary flex items-center gap-1.5 !w-auto px-3 py-1.5 text-sm"
              >
                <Plus className="h-4 w-4" />
                Добавить запись
              </button>
            </div>
            <WeightChart data={profile.recent_weights} />
          </div>

          {profile.recent_weights.length > 0 && (
            <div>
              <h3 className="font-semibold mb-3">История</h3>
              <WeightHistoryList data={profile.recent_weights} />
            </div>
          )}

          {/* Форма редактирования */}
          <ProfileForm profile={profile} onSave={handleSaveProfile} />
        </div>
      )}

      {/* Settings */}
      <div className="card p-4 my-6 rounded-xl">
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

      <button
        onClick={handleLogout}
        className="btn-danger w-full flex items-center justify-center gap-2"
      >
        <LogOut className="h-4 w-4" />
        Выход
      </button>

      <AddWeightModal
        isOpen={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={handleAddWeight}
      />
    </div>
  )
}
