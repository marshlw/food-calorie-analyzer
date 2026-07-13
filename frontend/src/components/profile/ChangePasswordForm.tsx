import React, { useState } from 'react'
import { KeyRound, Check } from 'lucide-react'
import { authApi } from '../../api/auth'
import { extractErrorMessage } from '../../utils/errors'
import { PasswordInput } from '../PasswordInput'
import { ErrorAlert } from '../ErrorAlert'

export const ChangePasswordForm: React.FC = () => {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess(false)

    if (!currentPassword || !newPassword || !confirmPassword) {
      setError('Заполните все поля')
      return
    }
    if (newPassword.length < 8) {
      setError('Новый пароль должен быть не менее 8 символов')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают')
      return
    }

    setSaving(true)
    try {
      await authApi.changePassword(currentPassword, newPassword)
      setSuccess(true)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card p-6 rounded-xl">
      <h3 className="font-semibold mb-4 flex items-center gap-2">
        <KeyRound className="h-5 w-5 text-gray-600 dark:text-gray-400" />
        Смена пароля
      </h3>

      {error && (
        <div className="mb-4">
          <ErrorAlert message={error} onClose={() => setError('')} />
        </div>
      )}

      {success && (
        <div className="mb-4 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 p-3 flex items-center gap-2">
          <Check className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0" />
          <p className="text-sm text-green-700 dark:text-green-400">Пароль успешно изменён</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Текущий пароль</label>
          <PasswordInput
            value={currentPassword}
            onChange={setCurrentPassword}
            disabled={saving}
            autoComplete="current-password"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Новый пароль</label>
          <PasswordInput
            value={newPassword}
            onChange={setNewPassword}
            disabled={saving}
            autoComplete="new-password"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Подтвердите новый пароль</label>
          <PasswordInput
            value={confirmPassword}
            onChange={setConfirmPassword}
            disabled={saving}
            autoComplete="new-password"
          />
        </div>

        <button
          type="submit"
          disabled={saving}
          className="btn-primary w-full disabled:opacity-50"
        >
          {saving ? 'Сохранение...' : 'Изменить пароль'}
        </button>
      </form>
    </div>
  )
}
