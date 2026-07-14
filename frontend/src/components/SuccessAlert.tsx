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
    <div className="rounded-tile bg-carbs-chip dark:bg-carbs-dark/15 border border-carbs/30 p-4">
      <p className="text-carbs-text dark:text-carbs-dark text-sm">{message}</p>
    </div>
  )
}
