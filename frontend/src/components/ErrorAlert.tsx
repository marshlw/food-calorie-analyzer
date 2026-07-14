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
    <div className="rounded-tile bg-danger/[.07] dark:bg-danger/15 border border-danger/25 p-4 flex gap-3">
      <AlertCircle className="h-5 w-5 text-danger flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-danger text-sm">{message}</p>
      </div>
      {dismissible && (
        <button onClick={handleClose} className="text-danger hover:text-danger-600">
          ×
        </button>
      )}
    </div>
  )
}
