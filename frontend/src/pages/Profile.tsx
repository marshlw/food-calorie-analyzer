import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, AlertCircle, ChevronRight, ChevronDown } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { profileApi } from '../api/profile'
import { Profile as ProfileType, ProfileUpdate, WeightRecordCreate } from '../types'
import { extractErrorMessage } from '../utils/errors'
import { AppHeader } from '../components/Brand'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorAlert } from '../components/ErrorAlert'
import { ProfileForm } from '../components/profile/ProfileForm'
import { WeightChart } from '../components/profile/WeightChart'
import { WeightHistoryList } from '../components/profile/WeightHistoryList'
import { AddWeightModal } from '../components/profile/AddWeightModal'
import { ChangePasswordForm } from '../components/profile/ChangePasswordForm'

type SettingsSection = 'personal' | 'password' | null

export const Profile: React.FC = () => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [profile, setProfile] = useState<ProfileType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [openSection, setOpenSection] = useState<SettingsSection>(null)

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

  const toggleSection = (s: Exclude<SettingsSection, null>) =>
    setOpenSection((cur) => (cur === s ? null : s))

  const name = profile?.full_name || user?.full_name || 'Пользователь'
  const initial = (name || user?.email || '?').trim()[0]?.toUpperCase() || '?'

  // Строка настроек (стрелка/шеврон) из дизайна
  const SettingsRow: React.FC<{
    label: string
    onClick: () => void
    expanded?: boolean
    last?: boolean
  }> = ({ label, onClick, expanded, last }) => (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-5 py-4 text-left ${
        last ? '' : 'border-b border-divider dark:border-line-dark'
      }`}
    >
      <span className="text-sm font-medium">{label}</span>
      {expanded ? (
        <ChevronDown className="h-4 w-4 text-faint dark:text-faint-dark" />
      ) : (
        <ChevronRight className="h-4 w-4 text-faint dark:text-faint-dark" />
      )}
    </button>
  )

  return (
    <div className="max-w-md mx-auto px-5 pt-6 pb-32">
      <AppHeader />

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
        <>
          {/* Identity */}
          <div className="flex flex-col items-center text-center mb-6">
            <div className="w-[76px] h-[76px] rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-white font-display font-bold text-[28px] mb-3">
              {initial}
            </div>
            <div className="font-display font-bold text-xl tracking-tight">{name}</div>
            <div className="text-[13px] text-secondary mt-0.5">{user?.email}</div>
          </div>

          {/* Напоминание о незаполненном профиле (не блокирует работу) */}
          {!profile.height_cm && (
            <div className="card-tile p-4 mb-3 flex gap-3">
              <AlertCircle className="h-5 w-5 text-fat-text dark:text-fat-dark flex-shrink-0 mt-0.5" />
              <p className="text-sm text-secondary">
                Заполните рост и вес в «Личных данных» — это нужно для расчёта нормы калорий.
              </p>
            </div>
          )}

          {/* Ключевые цифры */}
          <div className="grid grid-cols-3 gap-2.5 mb-3">
            <div className="card-tile p-3.5 text-center">
              <div className="font-display font-bold text-xl">
                {profile.current_weight_kg != null ? profile.current_weight_kg : '—'}
              </div>
              <div className="text-[11px] text-tertiary mt-0.5">кг · вес</div>
            </div>
            <div className="card-tile p-3.5 text-center">
              <div className="font-display font-bold text-xl">
                {profile.daily_calorie_target != null
                  ? Math.round(profile.daily_calorie_target)
                  : '—'}
              </div>
              <div className="text-[11px] text-tertiary mt-0.5">ккал · норма</div>
            </div>
            <div className="card-tile p-3.5 text-center">
              <div className="font-display font-bold text-xl">
                {profile.water_target_ml != null
                  ? (profile.water_target_ml / 1000).toFixed(1)
                  : '—'}
              </div>
              <div className="text-[11px] text-tertiary mt-0.5">л · вода</div>
            </div>
          </div>

          {/* Суточная норма КБЖУ */}
          <div className="card px-5 py-[18px] mb-6">
            <div className="text-[13px] font-semibold mb-3">Суточная норма КБЖУ</div>
            <div className="grid grid-cols-3 gap-2.5">
              <div>
                <div className="flex items-center gap-1.5 text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-protein dark:bg-protein-dark" />
                  Белки
                </div>
                <div className="font-display font-bold text-base mt-1">
                  {profile.protein_target_g != null ? `${Math.round(profile.protein_target_g)} г` : '—'}
                </div>
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-fat dark:bg-fat-dark" />
                  Жиры
                </div>
                <div className="font-display font-bold text-base mt-1">
                  {profile.fat_target_g != null ? `${Math.round(profile.fat_target_g)} г` : '—'}
                </div>
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-xs text-secondary">
                  <span className="w-2 h-2 rounded-full bg-carbs dark:bg-carbs-dark" />
                  Углеводы
                </div>
                <div className="font-display font-bold text-base mt-1">
                  {profile.carbs_target_g != null ? `${Math.round(profile.carbs_target_g)} г` : '—'}
                </div>
              </div>
            </div>
            {profile.daily_calorie_target == null && (
              <p className="text-xs text-tertiary mt-3">
                Заполните рост, вес, дату рождения и активность — и нормы рассчитаются автоматически.
              </p>
            )}
          </div>

          {/* Прогресс + Запись веса */}
          <div className="flex items-center justify-between mb-3">
            <span className="section-title">Прогресс</span>
            <button
              onClick={() => setAddOpen(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-[13px] font-semibold rounded-full bg-primary-50 text-primary-500 dark:bg-chip-dark dark:text-primary-400 hover:bg-primary-100 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Запись веса
            </button>
          </div>

          <div className="mb-3">
            <WeightChart data={profile.recent_weights} />
          </div>

          {profile.recent_weights.length > 0 && (
            <div className="mb-6">
              <WeightHistoryList data={profile.recent_weights} />
            </div>
          )}

          {/* Настройки */}
          <div className="card overflow-hidden mb-4">
            <SettingsRow
              label="Личные данные"
              onClick={() => toggleSection('personal')}
              expanded={openSection === 'personal'}
            />
            {openSection === 'personal' && (
              <div className="px-5 pb-5 border-b border-divider dark:border-line-dark">
                <ProfileForm profile={profile} onSave={handleSaveProfile} />
              </div>
            )}

            <SettingsRow
              label="Смена пароля"
              onClick={() => toggleSection('password')}
              expanded={openSection === 'password'}
            />
            {openSection === 'password' && (
              <div className="px-5 pb-5 border-b border-divider dark:border-line-dark">
                <ChangePasswordForm />
              </div>
            )}

            <SettingsRow label="История анализов" onClick={() => navigate('/analysis-history')} />

            {/* Тёмная тема */}
            <div className="flex items-center justify-between px-5 py-4">
              <span className="text-sm font-medium">Тёмная тема</span>
              <button
                onClick={() => setIsDarkMode(!isDarkMode)}
                role="switch"
                aria-checked={isDarkMode}
                aria-label="Тёмная тема"
                className={`relative inline-flex h-[26px] w-[46px] items-center rounded-full transition-colors ${
                  isDarkMode ? 'bg-primary-500' : 'bg-[#d9dfeb]'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                    isDarkMode ? 'translate-x-[23px]' : 'translate-x-[3px]'
                  }`}
                />
              </button>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="w-full text-center py-3 text-sm font-semibold text-danger hover:text-danger-600 transition-colors"
          >
            Выйти из аккаунта
          </button>
        </>
      )}

      <AddWeightModal isOpen={addOpen} onClose={() => setAddOpen(false)} onSubmit={handleAddWeight} />
    </div>
  )
}
