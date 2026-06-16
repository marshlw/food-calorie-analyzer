import React from 'react'

interface LoadingSpinnerProps {
  fullScreen?: boolean
  message?: string
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ fullScreen, message }) => {
  if (fullScreen) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white dark:bg-gray-950 z-50">
        <div className="text-center">
          <div className="inline-block loading-spinner text-primary-500"></div>
          {message && <p className="mt-4 text-gray-600 dark:text-gray-400">{message}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-center py-8">
      <div className="loading-spinner text-primary-500"></div>
    </div>
  )
}
