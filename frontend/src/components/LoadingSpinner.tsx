import React from 'react'

interface LoadingSpinnerProps {
  fullScreen?: boolean
  message?: string
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ fullScreen, message }) => {
  if (fullScreen) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-surface dark:bg-surface-dark z-50">
        <div className="text-center">
          <div className="inline-block loading-spinner text-primary-500 dark:text-primary-400"></div>
          {message && <p className="mt-4 text-secondary">{message}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-3 py-8">
      <div className="loading-spinner text-primary-500 dark:text-primary-400"></div>
      {message && <p className="text-sm text-secondary">{message}</p>}
    </div>
  )
}
