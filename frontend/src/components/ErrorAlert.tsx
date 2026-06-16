import React, { useState } from 'react'
import { AlertCircle } from 'lucide-react'

interface ErrorAlertProps {
  message: string
  onClose?: () => void
  dismissible?: boolean
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({ message, onClose, dismissible = true }) => {
  const [isVisible, setIsVisible] = useState(true)

  if (!isVisible) return null

  const handleClose = () => {
    setIsVisible(false)
    onClose?.()
  }

  return (
    <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-4 flex gap-3">
      <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-500 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-red-600 dark:text-red-400 text-sm">{message}</p>
      </div>
      {dismissible && (
        <button
          onClick={handleClose}
          className="text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
        >
          ×
        </button>
      )}
    </div>
  )
}
