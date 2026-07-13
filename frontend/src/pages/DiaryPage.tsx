import React, { useState } from 'react'
import { DiaryProvider, useDiary } from '../context/DiaryContext'
import { WeekCalendar } from '../components/WeekCalendar'
import { DayDetail } from '../components/DayDetail'
import { AnalysisFlow } from '../components/AnalysisFlow'
import { MealForm } from '../components/MealForm'
import { Modal } from '../components/Modal'
import { SuccessAlert } from '../components/SuccessAlert'
import { ErrorAlert } from '../components/ErrorAlert'
import { AiLimitBadge } from '../components/AiLimitBadge'
import { useApi } from '../hooks/useApi'
import { useAiLimit } from '../hooks/useAiLimit'
import { mealsApi } from '../api/meals'
import { MealEntry, MealEntryCreate } from '../types'
import { Plus, Camera } from 'lucide-react'

type ModalKind = 'none' | 'manual' | 'edit' | 'photo'

const DiaryInner: React.FC = () => {
  const { selectedDate, refreshDay } = useDiary()
  const [modal, setModal] = useState<ModalKind>('none')
  const [editing, setEditing] = useState<MealEntry | null>(null)
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [toast, setToast] = useState('')
  const { aiLimit, aiExhausted, refreshAiLimit } = useAiLimit()

  const close = () => {
    setModal('none')
    setEditing(null)
    setPhotoFile(null)
    // Загрузка фото расходует лимит даже без сохранения — обновляем счётчик
    refreshAiLimit()
  }

  const afterWrite = async (msg: string) => {
    setToast(msg)
    await refreshDay(selectedDate)
    close()
  }

  const add = useApi<MealEntry>({ onSuccess: () => afterWrite('Приём пищи добавлен!') })
  const update = useApi<MealEntry>({ onSuccess: () => afterWrite('Запись обновлена!') })
  const del = useApi<{ status: string; deleted_id: number }>({
    onSuccess: () => afterWrite('Запись удалена!'),
  })

  // date прокидываем, чтобы запись попала на ВЫБРАННЫЙ день.
  const handleAdd = async (d: MealEntryCreate): Promise<void> => {
    await add.execute(() => mealsApi.addMeal({ ...d, date: selectedDate }))
  }

  const handleUpdate = async (d: MealEntryCreate): Promise<void> => {
    if (!editing) return
    await update.execute(() => mealsApi.updateMeal(editing.id, d))
  }

  const handleDelete = (m: MealEntry) => {
    if (window.confirm('Удалить запись?')) {
      del.execute(() => mealsApi.deleteMeal(m.id))
    }
  }

  const writeError = add.error || update.error || del.error

  return (
    <div className="max-w-md mx-auto px-4 py-6 pb-24">
      <h1 className="text-3xl font-bold mb-4">Дневник питания</h1>

      {toast && (
        <div className="mb-4">
          <SuccessAlert message={toast} onClose={() => setToast('')} />
        </div>
      )}
      {writeError && (
        <div className="mb-4">
          <ErrorAlert message={writeError} onClose={() => {}} />
        </div>
      )}

      <WeekCalendar />

      <div className="grid grid-cols-2 gap-3 mb-2">
        <button
          className="btn btn-primary flex items-center justify-center gap-2"
          onClick={() => setModal('manual')}
        >
          <Plus className="h-5 w-5" /> Вручную
        </button>
        <label
          className={`btn btn-secondary flex items-center justify-center gap-2 ${
            aiExhausted ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          }`}
        >
          <Camera className="h-5 w-5" /> Фото
          <input
            type="file"
            accept="image/*"
            className="hidden"
            disabled={aiExhausted}
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) {
                setPhotoFile(f)
                setModal('photo')
              }
              e.target.value = '' // позволяет выбрать тот же файл повторно
            }}
          />
        </label>
      </div>

      <AiLimitBadge aiLimit={aiLimit} />

      <DayDetail
        onEdit={(m) => {
          setEditing(m)
          setModal('edit')
        }}
        onDelete={handleDelete}
        busy={del.isLoading}
      />

      <Modal isOpen={modal === 'manual'} onClose={close} title="Добавить приём пищи">
        <MealForm onSubmit={handleAdd} isLoading={add.isLoading} />
      </Modal>

      <Modal isOpen={modal === 'edit'} onClose={close} title="Редактировать">
        {editing && (
          <MealForm
            initialData={editing}
            onSubmit={handleUpdate}
            isLoading={update.isLoading}
            submitLabel="Сохранить"
          />
        )}
      </Modal>

      <Modal isOpen={modal === 'photo'} onClose={close} title="Анализ по фото">
        {photoFile && (
          <AnalysisFlow
            file={photoFile}
            onConfirm={handleAdd}
            onCancel={close}
            saving={add.isLoading}
          />
        )}
      </Modal>
    </div>
  )
}

export const DiaryPage: React.FC = () => (
  <DiaryProvider>
    <DiaryInner />
  </DiaryProvider>
)
