import React, { useState } from 'react'
import { ErrorAlert } from '../ErrorAlert'
import { SuccessAlert } from '../SuccessAlert'
import { Profile, ProfileUpdate, ActivityLevel, Sex } from '../../types'

interface Props {
  profile: Profile
  onSave: (payload: ProfileUpdate) => Promise<void>
}

// Обхваты тела: ключ в payload, подпись, плейсхолдер. Все опциональны.
type MeasureKey = 'waist_cm' | 'chest_cm' | 'hips_cm' | 'shoulders_cm'
const MEASUREMENTS: { key: MeasureKey; label: string; placeholder: string }[] = [
  { key: 'waist_cm', label: 'Талия, см', placeholder: '80' },
  { key: 'chest_cm', label: 'Грудь, см', placeholder: '100' },
  { key: 'hips_cm', label: 'Бёдра, см', placeholder: '95' },
  { key: 'shoulders_cm', label: 'Плечи, см', placeholder: '115' },
]

const ACTIVITY_OPTIONS: { value: ActivityLevel; label: string }[] = [
  { value: 'sedentary', label: 'Минимальная (сидячий образ жизни)' },
  { value: 'light', label: 'Лёгкая (1–3 трен./нед.)' },
  { value: 'moderate', label: 'Средняя (3–5 трен./нед.)' },
  { value: 'active', label: 'Высокая (6–7 трен./нед.)' },
  { value: 'very_active', label: 'Очень высокая (физ. работа)' },
]

const num = (v: string): number | undefined => {
  const n = parseFloat(v)
  return isNaN(n) ? undefined : n
}

export const ProfileForm: React.FC<Props> = ({ profile, onSave }) => {
  const [fullName, setFullName] = useState(profile.full_name ?? '')
  const [height, setHeight] = useState(profile.height_cm?.toString() ?? '')
  const [weight, setWeight] = useState(profile.current_weight_kg?.toString() ?? '')
  const [sex, setSex] = useState<Sex | ''>(profile.sex ?? '')
  const [birthDate, setBirthDate] = useState(profile.birth_date ?? '')
  const [activity, setActivity] = useState<ActivityLevel | ''>(profile.activity_level ?? '')
  // Обхваты предзаполняем из последней записи истории веса (recent_weights
  // отсортирован по возрастанию даты — берём последний элемент).
  const latestRecord = profile.recent_weights?.[profile.recent_weights.length - 1]
  const [measures, setMeasures] = useState<Record<MeasureKey, string>>(() => ({
    waist_cm: latestRecord?.waist_cm?.toString() ?? '',
    chest_cm: latestRecord?.chest_cm?.toString() ?? '',
    hips_cm: latestRecord?.hips_cm?.toString() ?? '',
    shoulders_cm: latestRecord?.shoulders_cm?.toString() ?? '',
  }))
  // По умолчанию изменённый вес/обхваты сохраняются как запись истории.
  const [saveAsRecord, setSaveAsRecord] = useState(true)

  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const weightChanged =
    num(weight) !== undefined && num(weight) !== (profile.current_weight_kg ?? undefined)

  const setMeasure = (key: MeasureKey, value: string) =>
    setMeasures((m) => ({ ...m, [key]: value }))

  const validate = (): string | null => {
    const h = num(height)
    const w = num(weight)
    if (h !== undefined && (h <= 0 || h >= 300)) return 'Рост должен быть больше 0 и меньше 300 см'
    if (w !== undefined && (w <= 0 || w >= 300)) return 'Вес должен быть больше 0 и меньше 300 кг'
    for (const { key, label } of MEASUREMENTS) {
      const val = num(measures[key])
      if (val !== undefined && (val <= 0 || val >= 300)) {
        return `«${label}» должно быть больше 0 и меньше 300 см`
      }
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const v = validate()
    if (v) {
      setError(v)
      return
    }
    // Отправляем только изменённые обхваты, чтобы сохранение профиля без правки
    // замеров не создавало лишнюю запись веса за сегодня.
    const changedMeasures: Partial<Record<MeasureKey, number>> = {}
    for (const { key } of MEASUREMENTS) {
      const cur = measures[key].trim()
      const orig = latestRecord?.[key]?.toString() ?? ''
      const n = num(cur)
      if (cur !== orig && n !== undefined) changedMeasures[key] = n
    }

    // Обхваты хранятся на записи веса, поэтому им нужен вес: из формы или из
    // истории. Если веса нет вовсе — сохранить замеры некуда.
    const hasWeight = num(weight) !== undefined || profile.current_weight_kg != null
    if (Object.keys(changedMeasures).length > 0 && !hasWeight) {
      setError('Чтобы сохранить замеры, сначала укажите вес')
      return
    }

    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      await onSave({
        full_name: fullName || undefined,
        height_cm: num(height),
        weight_kg: num(weight),
        sex: sex || undefined,
        birth_date: birthDate || undefined,
        activity_level: activity || undefined,
        ...changedMeasures,
        save_weight_as_record: saveAsRecord,
      })
      setSuccess('Профиль сохранён')
    } catch (err: any) {
      setError(err?.message || 'Не удалось сохранить профиль')
    } finally {
      setSaving(false)
    }
  }

  // Встраивается в раскрывающийся раздел «Личные данные» на экране Профиля
  return (
    <form onSubmit={handleSubmit} className="space-y-4 pt-1">
      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}
      {success && <SuccessAlert message={success} onClose={() => setSuccess(null)} />}

      <div>
        <label className="block text-sm font-medium mb-1">Имя</label>
        <input className="input w-full" value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">Рост, см</label>
          <input
            type="number" step="0.1" min="0" max="300" className="input w-full"
            value={height} onChange={(e) => setHeight(e.target.value)} placeholder="180"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Вес, кг</label>
          <input
            type="number" step="0.1" min="0" max="300" className="input w-full"
            value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="75"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">Пол</label>
          <select className="input w-full" value={sex} onChange={(e) => setSex(e.target.value as Sex)}>
            <option value="">—</option>
            <option value="male">Мужской</option>
            <option value="female">Женский</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Дата рождения</label>
          <input
            type="date" className="input w-full" max={new Date().toISOString().slice(0, 10)}
            value={birthDate} onChange={(e) => setBirthDate(e.target.value)}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Уровень активности</label>
        <select
          className="input w-full" value={activity}
          onChange={(e) => setActivity(e.target.value as ActivityLevel)}
        >
          <option value="">—</option>
          {ACTIVITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Обхваты тела — по желанию. Сохраняются в запись веса за сегодня. */}
      <div>
        <p className="text-xs font-semibold text-secondary mb-2">
          Замеры тела <span className="font-normal text-tertiary">· по желанию</span>
        </p>
        <div className="grid grid-cols-2 gap-3">
          {MEASUREMENTS.map((m) => (
            <div key={m.key}>
              <label className="block text-sm font-medium mb-1">{m.label}</label>
              <input
                type="number" step="0.1" min="0" max="300" className="input w-full"
                value={measures[m.key]}
                onChange={(e) => setMeasure(m.key, e.target.value)}
                placeholder={m.placeholder}
              />
            </div>
          ))}
        </div>
        {num(weight) === undefined && profile.current_weight_kg == null && (
          <p className="text-xs text-tertiary mt-2">
            Чтобы сохранить замеры, сначала укажите вес.
          </p>
        )}
      </div>

      {/* UX из ТЗ: предлагаем сохранить изменённый вес/обхваты как запись истории. */}
      {weightChanged && (
        <label className="flex items-center gap-2 text-sm text-secondary">
          <input
            type="checkbox" checked={saveAsRecord}
            onChange={(e) => setSaveAsRecord(e.target.checked)}
          />
          Сохранить новый вес как запись в истории ({new Date().toLocaleDateString('ru-RU')})
        </label>
      )}

      <button type="submit" disabled={saving} className="btn-primary w-full">
        {saving ? 'Сохранение…' : 'Сохранить'}
      </button>
    </form>
  )
}
