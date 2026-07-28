import React, { useState } from 'react'
import { ErrorAlert } from '../ErrorAlert'
import { SuccessAlert } from '../SuccessAlert'
import { Profile, ProfileUpdate, Goal } from '../../types'
import {
  GOAL_OPTIONS,
  RATE_PRESETS,
  DEFAULT_RATE,
  MAX_RATE_KG_PER_WEEK,
  formatRate,
  formatCalorieDelta,
} from '../../utils/goal'

interface Props {
  profile: Profile
  onSave: (payload: ProfileUpdate) => Promise<void>
}

// Форма «Цель по весу». Цель + желаемый темп + (опционально) целевой вес
// полностью определяют норму калорий и профиль БЖУ: расчёт на бэкенде
// переводит темп в суточный дефицит/профицит (1 кг ~ 7700 ккал).
export const GoalForm: React.FC<Props> = ({ profile, onSave }) => {
  const [goal, setGoal] = useState<Goal>(profile.goal ?? 'maintain')
  const [rate, setRate] = useState<string>(
    profile.goal_rate_kg_per_week != null ? String(profile.goal_rate_kg_per_week) : ''
  )
  const [targetWeight, setTargetWeight] = useState<string>(
    profile.target_weight_kg != null ? String(profile.target_weight_kg) : ''
  )
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const plan = profile.goal_plan
  const presets = goal === 'maintain' ? [] : RATE_PRESETS[goal]
  // Пустое поле темпа = дефолт для выбранной цели (его и подсвечиваем).
  const effectiveRate = rate.trim() === '' ? DEFAULT_RATE[goal] : parseFloat(rate)

  const changeGoal = (next: Goal) => {
    setGoal(next)
    // Темп сбрасываем: «0.5 кг/нед» для похудения и для набора — совсем
    // разные по безопасности величины, переносить их между целями нельзя.
    setRate('')
    if (next === 'maintain') setTargetWeight('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const rateNum = rate.trim() === '' ? 0 : parseFloat(rate)
    const targetNum = targetWeight.trim() === '' ? 0 : parseFloat(targetWeight)

    if (isNaN(rateNum) || rateNum < 0 || rateNum > MAX_RATE_KG_PER_WEEK) {
      setError(`Темп должен быть от 0 до ${MAX_RATE_KG_PER_WEEK} кг в неделю`)
      return
    }
    if (isNaN(targetNum) || targetNum < 0 || targetNum >= 300) {
      setError('Целевой вес должен быть больше 0 и меньше 300 кг')
      return
    }
    // Проверяем согласованность заранее, чтобы не сохранять заведомо
    // противоречивую пару (бэкенд такую цель примет, но прогноз не построит).
    const current = profile.current_weight_kg
    if (targetNum > 0 && current != null && goal !== 'maintain') {
      const wantsGain = targetNum > current
      if (goal === 'gain' && !wantsGain) {
        setError('Целевой вес меньше текущего — для набора он должен быть больше')
        return
      }
      if (goal === 'lose' && wantsGain) {
        setError('Целевой вес больше текущего — для похудения он должен быть меньше')
        return
      }
    }

    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      // 0 = сбросить на значение по умолчанию (дефолтный темп / без финиша)
      await onSave({
        goal,
        goal_rate_kg_per_week: goal === 'maintain' ? 0 : rateNum,
        target_weight_kg: goal === 'maintain' ? 0 : targetNum,
      })
      setSuccess('Цель сохранена — нормы пересчитаны')
    } catch (err: any) {
      setError(err?.message || 'Не удалось сохранить цель')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 pt-1">
      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}
      {success && <SuccessAlert message={success} onClose={() => setSuccess(null)} />}

      {/* Выбор цели */}
      <div className="grid grid-cols-3 gap-2">
        {GOAL_OPTIONS.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => changeGoal(o.value)}
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
        <>
          {/* Темп */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Темп {goal === 'lose' ? 'снижения' : 'набора'} веса
            </label>
            <div className="flex gap-2">
              {presets.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setRate(String(p.value))}
                  className={`flex-1 rounded-xl px-2 py-2.5 text-center border transition-colors ${
                    effectiveRate === p.value
                      ? 'border-primary-500 bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400'
                      : 'border-divider dark:border-line-dark text-secondary'
                  }`}
                >
                  <div className="text-[12px] font-semibold">{p.label}</div>
                  <div className="text-[10px] text-tertiary mt-0.5">{formatRate(p.value)}</div>
                </button>
              ))}
            </div>
            <input
              type="number"
              step="0.05"
              min="0"
              max={MAX_RATE_KG_PER_WEEK}
              className="input w-full mt-2 !py-2.5 text-sm"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
              placeholder={`свой темп, кг/нед · по умолчанию ${DEFAULT_RATE[goal]}`}
            />
          </div>

          {/* Целевой вес */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Целевой вес, кг <span className="font-normal text-tertiary">· по желанию</span>
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="300"
              className="input w-full"
              value={targetWeight}
              onChange={(e) => setTargetWeight(e.target.value)}
              placeholder={goal === 'lose' ? '70' : '80'}
            />
            <p className="text-xs text-tertiary mt-1.5">
              Нужен только для прогноза сроков — на норму калорий не влияет.
            </p>
          </div>
        </>
      )}

      {/* Что даёт текущий сохранённый план */}
      {plan && plan.goal !== 'maintain' && (
        <div className="card-tile px-4 py-3 text-[13px] space-y-1">
          <div className="flex justify-between">
            <span className="text-secondary">Поправка к норме поддержания</span>
            <span className="font-semibold">{formatCalorieDelta(plan.calorie_delta)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-secondary">Фактический темп</span>
            <span className="font-semibold">{formatRate(plan.applied_rate_kg_per_week)}</span>
          </div>
          {plan.weeks_to_goal != null && (
            <div className="flex justify-between">
              <span className="text-secondary">До цели</span>
              <span className="font-semibold">
                ~{Math.round(plan.weeks_to_goal)} нед
                {plan.eta_date
                  ? ` · до ${new Date(plan.eta_date).toLocaleDateString('ru-RU', {
                      month: 'short',
                      year: 'numeric',
                    })}`
                  : ''}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Пояснения ограничителей безопасности (пришли с бэкенда) */}
      {profile.calc_warnings?.map((w) => (
        <p key={w.code} className="text-xs text-secondary leading-relaxed">
          {w.message}
        </p>
      ))}

      <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
        {saving ? 'Сохранение…' : 'Сохранить цель'}
      </button>
    </form>
  )
}
