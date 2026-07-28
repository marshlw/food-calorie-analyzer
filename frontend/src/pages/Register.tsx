import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { ErrorAlert } from '../components/ErrorAlert'
import { PasswordInput } from '../components/PasswordInput'
import { RingLogo } from '../components/Brand'
import { Sex, Goal, ActivityLevel } from '../types'
import { GOAL_OPTIONS, RATE_PRESETS, DEFAULT_RATE, formatRate } from '../utils/goal'

// Уровни активности — те же значения, что в ProfileForm (см. nutrition.py).
const ACTIVITY_OPTIONS: { value: ActivityLevel; label: string }[] = [
  { value: 'sedentary', label: 'Минимальная (сидячий образ жизни)' },
  { value: 'light', label: 'Лёгкая (1–3 трен./нед.)' },
  { value: 'moderate', label: 'Средняя (3–5 трен./нед.)' },
  { value: 'active', label: 'Высокая (6–7 трен./нед.)' },
  { value: 'very_active', label: 'Очень высокая (физ. работа)' },
]

// Обхваты тела: ключ, подпись, плейсхолдер. Все опциональны.
type MeasureKey = 'waist_cm' | 'chest_cm' | 'hips_cm' | 'shoulders_cm'
const MEASUREMENTS: { key: MeasureKey; label: string; placeholder: string }[] = [
  { key: 'waist_cm', label: 'Талия, см', placeholder: '80' },
  { key: 'chest_cm', label: 'Грудь, см', placeholder: '100' },
  { key: 'hips_cm', label: 'Бёдра, см', placeholder: '95' },
  { key: 'shoulders_cm', label: 'Плечи, см', placeholder: '115' },
]

// Экран регистрации в стиле экрана входа Rasify.
export const Register: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [height, setHeight] = useState('')
  const [weight, setWeight] = useState('')
  const [sex, setSex] = useState<Sex | ''>('')
  const [birthDate, setBirthDate] = useState('')
  // Цель по весу задаётся сразу при регистрации: без неё первая же норма
  // КБЖУ будет нормой поддержания, что для большинства новых пользователей
  // не то, зачем они пришли.
  const [goal, setGoal] = useState<Goal>('maintain')
  const [rate, setRate] = useState<number | null>(null) // null = дефолт для цели
  const [targetWeight, setTargetWeight] = useState('')
  const [activity, setActivity] = useState<ActivityLevel | ''>('')
  const [measures, setMeasures] = useState<Record<MeasureKey, string>>({
    waist_cm: '',
    chest_cm: '',
    hips_cm: '',
    shoulders_cm: '',
  })
  const [localError, setLocalError] = useState('')
  const navigate = useNavigate()
  const { register, isLoading, error, clearError } = useAuth()

  const setMeasure = (key: MeasureKey, value: string) =>
    setMeasures((m) => ({ ...m, [key]: value }))

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

    // Собираем и проверяем обхваты
    const measurePayload: Partial<Record<MeasureKey, number>> = {}
    for (const { key, label } of MEASUREMENTS) {
      const raw = measures[key].trim()
      if (!raw) continue
      const val = parseFloat(raw)
      if (isNaN(val) || val <= 0 || val >= 300) {
        setLocalError(`«${label}» должно быть больше 0 и меньше 300 см`)
        return
      }
      measurePayload[key] = val
    }
    // Обхваты хранятся на записи веса — без веса их сохранить некуда.
    if (Object.keys(measurePayload).length > 0 && w === undefined) {
      setLocalError('Чтобы сохранить замеры, укажите вес')
      return
    }

    // Целевой вес нужен только для прогноза сроков; проверяем, что он не
    // противоречит выбранной цели.
    const tw = targetWeight ? parseFloat(targetWeight) : undefined
    if (tw !== undefined && (isNaN(tw) || tw <= 0 || tw >= 300)) {
      setLocalError('Целевой вес должен быть больше 0 и меньше 300 кг')
      return
    }
    if (tw !== undefined && w !== undefined && goal !== 'maintain') {
      if (goal === 'lose' && tw > w) {
        setLocalError('Целевой вес больше текущего — для похудения он должен быть меньше')
        return
      }
      if (goal === 'gain' && tw < w) {
        setLocalError('Целевой вес меньше текущего — для набора он должен быть больше')
        return
      }
    }

    try {
      await register(email, password, fullName || undefined, {
        height_cm: h,
        weight_kg: w,
        sex: sex || undefined,
        birth_date: birthDate || undefined,
        activity_level: activity || undefined,
        goal,
        goal_rate_kg_per_week:
          goal === 'maintain' ? undefined : rate ?? DEFAULT_RATE[goal],
        target_weight_kg: goal === 'maintain' ? undefined : tw,
        ...measurePayload,
      })
      navigate('/')
    } catch {
      // Error is already set by auth context
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface dark:bg-surface-dark px-6 py-10">
      <div className="w-full max-w-md">
        {/* Логотип */}
        <div className="text-center mb-8">
          <RingLogo size={56} className="mb-4 inline-block" />
          <h1 className="font-display font-extrabold text-2xl tracking-tight mb-2">
            Создать аккаунт
          </h1>
          <p className="text-sm text-secondary">Присоединяйтесь к Rasify</p>
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
              <label className="block text-[13px] font-semibold mb-1.5">
                Полное имя (опционально)
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Анна Смирнова"
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
                autoComplete="new-password"
              />
            </div>

            <div>
              <label className="block text-[13px] font-semibold mb-1.5">Подтвердите пароль</label>
              <PasswordInput
                value={confirmPassword}
                onChange={setConfirmPassword}
                disabled={isLoading}
                autoComplete="new-password"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[13px] font-semibold mb-1.5">Рост, см (опц.)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="300"
                  value={height}
                  onChange={(e) => setHeight(e.target.value)}
                  placeholder="170"
                  className="input"
                  disabled={isLoading}
                />
              </div>
              <div>
                <label className="block text-[13px] font-semibold mb-1.5">Вес, кг (опц.)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="300"
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  placeholder="62"
                  className="input"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Пол и дата рождения (возраст) — для расчёта норм калорий */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[13px] font-semibold mb-1.5">Пол (опц.)</label>
                <select
                  className="input"
                  value={sex}
                  onChange={(e) => setSex(e.target.value as Sex)}
                  disabled={isLoading}
                >
                  <option value="">—</option>
                  <option value="male">Мужской</option>
                  <option value="female">Женский</option>
                </select>
              </div>
              <div>
                <label className="block text-[13px] font-semibold mb-1.5">
                  Дата рождения (опц.)
                </label>
                <input
                  type="date"
                  className="input"
                  max={new Date().toISOString().slice(0, 10)}
                  value={birthDate}
                  onChange={(e) => setBirthDate(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Уровень активности — множитель к базовому обмену в норме калорий */}
            <div>
              <label className="block text-[13px] font-semibold mb-1.5">
                Уровень активности (опц.)
              </label>
              <select
                className="input"
                value={activity}
                onChange={(e) => setActivity(e.target.value as ActivityLevel)}
                disabled={isLoading}
              >
                <option value="">—</option>
                {ACTIVITY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Цель по весу — определяет дефицит/профицит калорий и профиль БЖУ */}
            <div>
              <p className="text-[13px] font-semibold mb-2">Ваша цель</p>
              <div className="grid grid-cols-3 gap-2">
                {GOAL_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    disabled={isLoading}
                    onClick={() => {
                      setGoal(o.value)
                      setRate(null) // темп не переносим между целями
                      if (o.value === 'maintain') setTargetWeight('')
                    }}
                    className={`rounded-2xl px-2 py-3 text-center transition-colors border ${
                      goal === o.value
                        ? 'border-primary-500 bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400'
                        : 'border-divider dark:border-line-dark text-secondary'
                    }`}
                  >
                    <div className="text-[13px] font-semibold leading-tight">{o.label}</div>
                    <div className="text-[10px] mt-1 leading-tight text-tertiary">{o.hint}</div>
                  </button>
                ))}
              </div>

              {goal !== 'maintain' && (
                <div className="mt-3 space-y-3">
                  <div className="flex gap-2">
                    {RATE_PRESETS[goal].map((p) => (
                      <button
                        key={p.value}
                        type="button"
                        disabled={isLoading}
                        onClick={() => setRate(p.value)}
                        className={`flex-1 rounded-xl px-2 py-2.5 text-center border transition-colors ${
                          (rate ?? DEFAULT_RATE[goal]) === p.value
                            ? 'border-primary-500 bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400'
                            : 'border-divider dark:border-line-dark text-secondary'
                        }`}
                      >
                        <div className="text-[12px] font-semibold">{p.label}</div>
                        <div className="text-[10px] text-tertiary mt-0.5">
                          {formatRate(p.value)}
                        </div>
                      </button>
                    ))}
                  </div>
                  <div>
                    <label className="block text-[12px] font-medium mb-1.5">
                      Целевой вес, кг <span className="font-normal text-tertiary">· опц.</span>
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="300"
                      value={targetWeight}
                      onChange={(e) => setTargetWeight(e.target.value)}
                      placeholder={goal === 'lose' ? '58' : '70'}
                      className="input"
                      disabled={isLoading}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Замеры тела — по желанию. Сохраняются в первую запись веса. */}
            <div>
              <p className="text-[13px] font-semibold mb-2">
                Замеры тела <span className="font-normal text-tertiary">· по желанию</span>
              </p>
              <div className="grid grid-cols-2 gap-3">
                {MEASUREMENTS.map((m) => (
                  <div key={m.key}>
                    <label className="block text-[12px] font-medium mb-1.5">{m.label}</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="300"
                      value={measures[m.key]}
                      onChange={(e) => setMeasure(m.key, e.target.value)}
                      placeholder={m.placeholder}
                      className="input"
                      disabled={isLoading}
                    />
                  </div>
                ))}
              </div>
              {!weight && (
                <p className="text-xs text-tertiary mt-2">
                  Чтобы сохранить замеры, укажите вес.
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full mt-1 disabled:opacity-50"
            >
              {isLoading ? 'Создание...' : 'Создать аккаунт'}
            </button>
          </form>
        </div>

        {/* Login Link */}
        <div className="mt-6 text-center">
          <p className="text-sm text-secondary">
            Уже есть аккаунт?{' '}
            <Link
              to="/login"
              className="font-semibold text-primary-500 dark:text-primary-400 hover:text-primary-700"
            >
              Войдите
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
