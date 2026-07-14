import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

// Фирменный знак Rasify (вариант 1a): незамкнутое кольцо дневной нормы
// с точкой-искрой AI. Цвет автоматически подстраивается под тему.
export const RingLogo: React.FC<{ size?: number; className?: string }> = ({
  size = 24,
  className = '',
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 64 64"
    className={`text-primary-500 dark:text-primary-400 ${className}`}
    aria-hidden="true"
  >
    <circle
      cx="32"
      cy="32"
      r="26"
      stroke="currentColor"
      strokeWidth="10"
      fill="none"
      strokeLinecap="round"
      strokeDasharray="122.5 163.4"
      transform="rotate(-90 32 32)"
    />
    <circle cx="13.6" cy="13.6" r="6" fill="currentColor" />
  </svg>
)

// Логотип + словомарка (шапка экранов)
export const BrandMark: React.FC<{ size?: number }> = ({ size = 24 }) => (
  <div className="flex items-center gap-2">
    <RingLogo size={size} />
    <span className="font-display font-extrabold text-[17px] tracking-tight">Rasify</span>
  </div>
)

// Шапка экрана: логотип слева, аватар-инициал справа (ведёт в Профиль)
export const AppHeader: React.FC<{ right?: React.ReactNode }> = ({ right }) => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const initial = (user?.full_name || user?.email || '?').trim()[0]?.toUpperCase() || '?'

  return (
    <div className="flex items-center justify-between mb-6">
      <BrandMark />
      {right ?? (
        <button
          onClick={() => navigate('/profile')}
          aria-label="Профиль"
          className="w-[34px] h-[34px] rounded-full bg-primary-50 text-primary-500 dark:bg-chip-dark dark:text-primary-400 flex items-center justify-center text-sm font-semibold"
        >
          {initial}
        </button>
      )}
    </div>
  )
}
