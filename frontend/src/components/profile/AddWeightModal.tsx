import React, { useState } from 'react'
import { Modal } from '../Modal'
import { ErrorAlert } from '../ErrorAlert'
import { WeightRecordCreate } from '../../types'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSubmit: (payload: WeightRecordCreate) => Promise<void>
}

const today = () => new Date().toISOString().slice(0, 10)

// Обхваты тела: ключ в payload, подпись и плейсхолдер. Все опциональны.
const MEASUREMENTS: { key: 'waist_cm' | 'chest_cm' | 'hips_cm' | 'shoulders_cm'; label: string; placeholder: string }[] = [
  { key: 'waist_cm', label: 'Талия, см', placeholder: '80' },
  { key: 'chest_cm', label: 'Грудь, см', placeholder: '100' },
  { key: 'hips_cm', label: 'Бёдра, см', placeholder: '95' },
  { key: 'shoulders_cm', label: 'Плечи, см', placeholder: '115' },
]

type MeasureKey = (typeof MEASUREMENTS)[number]['key']

const emptyMeasures: Record<MeasureKey, string> = {
  waist_cm: '',
  chest_cm: '',
  hips_cm: '',
  shoulders_cm: '',
}

export const AddWeightModal: React.FC<Props> = ({ isOpen, onClose, onSubmit }) => {
  const [weight, setWeight] = useState('')
  const [date, setDate] = useState(today())
  const [note, setNote] = useState('')
  const [measures, setMeasures] = useState<Record<MeasureKey, string>>({ ...emptyMeasures })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const reset = () => {
    setWeight('')
    setDate(today())
    setNote('')
    setMeasures({ ...emptyMeasures })
    setError(null)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const setMeasure = (key: MeasureKey, value: string) =>
    setMeasures((m) => ({ ...m, [key]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const w = parseFloat(weight)
    if (isNaN(w) || w <= 0 || w >= 300) {
      setError('Вес должен быть больше 0 и меньше 300 кг')
      return
    }
    if (date > today()) {
      setError('Дата записи не может быть в будущем')
      return
    }
    // Проверяем заполненные обхваты и собираем их в payload.
    const payload: WeightRecordCreate = { weight_kg: w, recorded_on: date, note: note || undefined }
    for (const { key, label } of MEASUREMENTS) {
      const raw = measures[key].trim()
      if (!raw) continue
      const val = parseFloat(raw)
      if (isNaN(val) || val <= 0 || val >= 300) {
        setError(`«${label}» должно быть больше 0 и меньше 300 см`)
        return
      }
      payload[key] = val
    }
    setSaving(true)
    setError(null)
    try {
      await onSubmit(payload)
      reset()
      onClose()
    } catch (err: any) {
      setError(err?.message || 'Не удалось сохранить запись')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Добавить замер тела">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Вес, кг</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="300"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className="input w-full"
              placeholder="75.5"
              autoFocus
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Дата</label>
            <input
              type="date"
              value={date}
              max={today()}
              onChange={(e) => setDate(e.target.value)}
              className="input w-full"
              required
            />
          </div>
        </div>

        {/* Обхваты тела — по желанию. Пустые поля не сохраняются. */}
        <div>
          <p className="text-xs font-semibold text-secondary mb-2">
            Обхваты тела <span className="font-normal text-tertiary">· по желанию</span>
          </p>
          <div className="grid grid-cols-2 gap-3">
            {MEASUREMENTS.map((m) => (
              <div key={m.key}>
                <label className="block text-sm font-medium mb-1">{m.label}</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="300"
                  value={measures[m.key]}
                  onChange={(e) => setMeasure(m.key, e.target.value)}
                  className="input w-full"
                  placeholder={m.placeholder}
                />
              </div>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Заметка (необязательно)</label>
          <input
            type="text"
            value={note}
            maxLength={200}
            onChange={(e) => setNote(e.target.value)}
            className="input w-full"
            placeholder="например, после отпуска"
          />
        </div>

        <div className="flex gap-2 pt-2">
          <button type="button" onClick={handleClose} className="btn-secondary flex-1">
            Отмена
          </button>
          <button type="submit" disabled={saving} className="btn-primary flex-1">
            {saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
