import React, { useState } from 'react'
import { ErrorAlert } from '../ErrorAlert'
import { SuccessAlert } from '../SuccessAlert'
import { Profile, ProfileUpdate } from '../../types'

interface Props {
  profile: Profile
  onSave: (payload: ProfileUpdate) => Promise<void>
}

// Одно поле нормы с подписью и пометкой «вручную/авто»
interface FieldDef {
  key: keyof Pick<
    ProfileUpdate,
    'custom_calorie_target' | 'custom_protein_g' | 'custom_fat_g' | 'custom_carbs_g' | 'custom_water_ml'
  >
  label: string
  unit: string
  max: number
  custom?: number | null // текущее ручное значение
  auto?: number | null // текущее эффективное значение (для placeholder)
  dotClass?: string
}

// Форма «Мои нормы»: ручные нормы КБЖУ и воды для атлетов.
// Пустое поле = авторасчёт из параметров тела; заполненное — приоритетная
// норма, которая подхватывается во всех формах (дневник, вода, советчик).
export const TargetsForm: React.FC<Props> = ({ profile, onSave }) => {
  const fields: FieldDef[] = [
    {
      key: 'custom_calorie_target',
      label: 'Калории',
      unit: 'ккал',
      max: 20000,
      custom: profile.custom_calorie_target,
      auto: profile.daily_calorie_target,
    },
    {
      key: 'custom_protein_g',
      label: 'Белки',
      unit: 'г',
      max: 2000,
      custom: profile.custom_protein_g,
      auto: profile.protein_target_g,
      dotClass: 'bg-protein dark:bg-protein-dark',
    },
    {
      key: 'custom_fat_g',
      label: 'Жиры',
      unit: 'г',
      max: 2000,
      custom: profile.custom_fat_g,
      auto: profile.fat_target_g,
      dotClass: 'bg-fat dark:bg-fat-dark',
    },
    {
      key: 'custom_carbs_g',
      label: 'Углеводы',
      unit: 'г',
      max: 3000,
      custom: profile.custom_carbs_g,
      auto: profile.carbs_target_g,
      dotClass: 'bg-carbs dark:bg-carbs-dark',
    },
    {
      key: 'custom_water_ml',
      label: 'Вода',
      unit: 'мл',
      max: 20000,
      custom: profile.custom_water_ml,
      auto: profile.water_target_ml,
      dotClass: 'bg-water',
    },
  ]

  // Поля предзаполняются только РУЧНЫМИ значениями; авторасчёт — в placeholder
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.key, f.custom != null ? String(f.custom) : '']))
  )
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const hasCustom = fields.some((f) => f.custom != null)

  const buildPayload = (reset = false): ProfileUpdate | null => {
    const payload: ProfileUpdate = {}
    for (const f of fields) {
      if (reset) {
        payload[f.key] = 0 // 0 = вернуть авторасчёт
        continue
      }
      const raw = values[f.key].trim()
      if (raw === '') {
        // Пустое поле: если раньше было ручное значение — сбрасываем на авто
        if (f.custom != null) payload[f.key] = 0
        continue
      }
      const n = parseFloat(raw)
      if (isNaN(n) || n < 0 || n > f.max) {
        setError(`«${f.label}»: значение от 0 до ${f.max} ${f.unit}`)
        return null
      }
      payload[f.key] = n
    }
    return payload
  }

  const submit = async (reset = false) => {
    const payload = buildPayload(reset)
    if (!payload) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      await onSave(payload)
      if (reset) {
        setValues(Object.fromEntries(fields.map((f) => [f.key, ''])))
        setSuccess('Нормы возвращены к авторасчёту')
      } else {
        setSuccess('Нормы сохранены — обновятся во всех формах')
      }
    } catch (err: any) {
      setError(err?.message || 'Не удалось сохранить нормы')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit(false)
      }}
      className="space-y-4 pt-1"
    >
      <p className="text-xs text-secondary leading-relaxed">
        Задайте собственные нормы — они заменят авторасчёт в дневнике, воде и советчике.
        Пустое поле — норма считается автоматически по вашим параметрам.
      </p>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}
      {success && <SuccessAlert message={success} onClose={() => setSuccess(null)} />}

      <div className="flex flex-col gap-3">
        {fields.map((f) => (
          <div key={f.key} className="flex items-center gap-3">
            <div className="w-[104px] flex items-center gap-1.5 text-[13px] font-medium flex-shrink-0">
              {f.dotClass && <span className={`w-2 h-2 rounded-full ${f.dotClass}`} />}
              {f.label}
            </div>
            <div className="relative flex-1">
              <input
                type="number"
                value={values[f.key]}
                onChange={(e) => setValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                placeholder={f.auto != null ? `авто · ${Math.round(f.auto)}` : 'авто'}
                min="0"
                max={f.max}
                step="1"
                className="input !py-2.5 pr-14 text-sm"
                disabled={saving}
              />
              <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-tertiary pointer-events-none">
                {f.unit}
              </span>
            </div>
            <span
              className={`text-[11px] w-[52px] text-right flex-shrink-0 ${
                f.custom != null
                  ? 'font-semibold text-primary-500 dark:text-primary-400'
                  : 'text-tertiary'
              }`}
            >
              {f.custom != null ? 'вручную' : 'авто'}
            </span>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        {hasCustom && (
          <button
            type="button"
            onClick={() => submit(true)}
            disabled={saving}
            className="btn-outline flex-1 !text-[13px] disabled:opacity-50"
          >
            Вернуть авторасчёт
          </button>
        )}
        <button type="submit" disabled={saving} className="btn-primary flex-1 disabled:opacity-50">
          {saving ? 'Сохранение…' : 'Сохранить нормы'}
        </button>
      </div>
    </form>
  )
}
