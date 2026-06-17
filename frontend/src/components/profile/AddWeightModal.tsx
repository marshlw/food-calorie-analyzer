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

export const AddWeightModal: React.FC<Props> = ({ isOpen, onClose, onSubmit }) => {
  const [weight, setWeight] = useState('')
  const [date, setDate] = useState(today())
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const reset = () => {
    setWeight('')
    setDate(today())
    setNote('')
    setError(null)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

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
    setSaving(true)
    setError(null)
    try {
      await onSubmit({ weight_kg: w, recorded_on: date, note: note || undefined })
      reset()
      onClose()
    } catch (err: any) {
      setError(err?.message || 'Не удалось сохранить запись')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Добавить запись веса">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

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
            placeholder="например, 75.5"
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
