import React from 'react'

interface SuccessAlertProps {
  message: string
  onClose?: () => void
}

export const SuccessAlert: React.FC<SuccessAlertProps> = ({ message, onClose }) => {
  React.useEffect(() => {
    if (!onClose) return
    const timer = setTimeout(onClose, 3000)
    return () => clearTimeout(timer)
  }, [onClose])

  return (
    <div className="rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 p-4">
      <p className="text-green-600 dark:text-green-400 text-sm">{message}</p>
    </div>
  )
}
