import React from 'react'
import { X } from 'lucide-react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
}

// Модальное окно в стиле bottom-sheet из дизайна Rasify: скруглённая
// карточка, полоска-грип на мобильном, заголовок Manrope.
export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null

  return (
    <>
      <div className="modal-overlay" onClick={onClose} />
      <div className="modal-content">
        <div className="card w-full sm:max-w-md m-0 sm:m-4 max-h-[92vh] flex flex-col rounded-b-none rounded-t-[28px] sm:rounded-card overflow-hidden">
          {/* Грип-полоска (как у шторки в дизайне) */}
          <div className="sm:hidden pt-3 flex justify-center">
            <div className="w-9 h-1 rounded-full bg-[#d9dfeb] dark:bg-line-dark" />
          </div>
          <div className="flex items-center justify-between px-5 pt-4 pb-3">
            <h2 className="font-display font-bold text-lg tracking-tight">{title}</h2>
            <button
              onClick={onClose}
              aria-label="Закрыть"
              className="p-1.5 rounded-full text-muted dark:text-muted-dark hover:bg-surface dark:hover:bg-chip-dark transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="px-5 pb-6 overflow-y-auto">{children}</div>
        </div>
      </div>
    </>
  )
}
