import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { DiaryProvider, useDiary } from '../context/DiaryContext'
import { WeekCalendar } from '../components/WeekCalendar'
import { DayDetail } from '../components/DayDetail'
import { AnalysisFlow } from '../components/AnalysisFlow'
import { BarcodeFlow } from '../components/BarcodeFlow'
import { MealForm } from '../components/MealForm'
import { MealDetail } from '../components/MealDetail'
import { Modal } from '../components/Modal'
import { SuccessAlert } from '../components/SuccessAlert'
import { ErrorAlert } from '../components/ErrorAlert'
import { AiLimitBadge } from '../components/AiLimitBadge'
import { SegmentedTabs } from '../components/goals/SegmentedTabs'
import type { SegmentOption } from '../components/goals/SegmentedTabs'
import { PathTab } from '../components/goals/PathTab'
import { useApi } from '../hooks/useApi'
import { useAiLimit } from '../hooks/useAiLimit'
import { useGoals } from '../hooks/useGoals'
import { mealsApi } from '../api/meals'
import { MealEntry, MealEntryCreate } from '../types'
import { UPLOAD_ACCEPT } from '../utils/image'
import { AppHeader } from '../components/Brand'
import { Plus, Camera, ScanBarcode } from 'lucide-react'

type ModalKind = 'none' | 'manual' | 'edit' | 'photo' | 'barcode' | 'view'
type DiaryTab = 'calendar' | 'path'

const TABS: SegmentOption<DiaryTab>[] = [
  { value: 'calendar', label: 'Календарь' },
  { value: 'path', label: 'Путь' },
]

const DiaryInner: React.FC = () => {
  const { selectedDate, refreshDay } = useDiary()

  // Вкладка живёт в URL (?tab=path): карточка серии на «Дневнике» ведёт
  // сразу на «Путь», а назад/обновление страницы не сбрасывают выбор.
  const [searchParams, setSearchParams] = useSearchParams()
  const tab: DiaryTab = searchParams.get('tab') === 'path' ? 'path' : 'calendar'
  const setTab = (next: DiaryTab) => {
    const params = new URLSearchParams(searchParams)
    if (next === 'calendar') params.delete('tab')
    else params.set('tab', next)
    setSearchParams(params, { replace: true })
  }

  const [modal, setModal] = useState<ModalKind>('none')
  const [editing, setEditing] = useState<MealEntry | null>(null)
  const [viewing, setViewing] = useState<MealEntry | null>(null)
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [toast, setToast] = useState('')
  const { aiLimit, aiExhausted, refreshAiLimit } = useAiLimit()

  // Цели дня и серия: нужны вкладке «Путь». Записи еды/воды меняют прогресс,
  // поэтому после каждой записи цели перечитываем.
  const { goals, setGoals, isLoading: goalsLoading, refresh: refreshGoals } = useGoals()

  const close = () => {
    setModal('none')
    setEditing(null)
    setViewing(null)
    setPhotoFile(null)
    // Загрузка фото расходует лимит даже без сохранения — обновляем счётчик
    refreshAiLimit()
  }

  // Фото добавлено/удалено в просмотре: обновляем открытую карточку и день
  const handleViewedUpdated = (m: MealEntry) => {
    setViewing(m)
    refreshDay(selectedDate)
  }

  const afterWrite = async (msg: string) => {
    setToast(msg)
    await refreshDay(selectedDate)
    refreshGoals()
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
    <div className="max-w-md mx-auto px-5 pt-6 pb-32">
      <AppHeader />

      <div className="flex items-center justify-between mb-4">
        <h1 className="font-display font-bold text-2xl tracking-tight">Дневник питания</h1>
      </div>

      <SegmentedTabs
        value={tab}
        options={TABS}
        onChange={setTab}
        ariaLabel="Разделы дневника питания"
      />

      {toast && (
        <div className="mb-4">
          <SuccessAlert message={toast} onClose={() => setToast('')} />
        </div>
      )}
      {writeError && (
        <div className="mb-4">
          <ErrorAlert key={writeError} message={writeError} onClose={() => {}} />
        </div>
      )}

      {tab === 'path' ? (
        <PathTab goals={goals} goalsLoading={goalsLoading} onGoalsChanged={setGoals} />
      ) : (
        <>
          <WeekCalendar />

          <div className="flex gap-3 mb-2">
            <button
              className="btn-primary flex-1 flex items-center justify-center gap-2"
              onClick={() => setModal('manual')}
            >
              <Plus className="h-[18px] w-[18px]" /> Вручную
            </button>
            <label
              className={`btn-secondary flex-1 flex items-center justify-center gap-2 ${
                aiExhausted ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
              }`}
            >
              <Camera className="h-[18px] w-[18px]" /> Фото
              <input
                type="file"
                accept={UPLOAD_ACCEPT}
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
            {/* Сканер штрих-кода — квадратная кнопка, прижата к правому краю */}
            <button
              type="button"
              aria-label="Сканировать штрих-код"
              title="Добавить по штрих-коду"
              onClick={() => setModal('barcode')}
              className="btn-secondary flex-shrink-0 !px-3.5 flex items-center justify-center"
            >
              <ScanBarcode className="h-[20px] w-[20px]" />
            </button>
          </div>

          <AiLimitBadge aiLimit={aiLimit} />

          <DayDetail
            onEdit={(m) => {
              setEditing(m)
              setModal('edit')
            }}
            onDelete={handleDelete}
            onView={(m) => {
              setViewing(m)
              setModal('view')
            }}
            onWaterChanged={refreshGoals}
            busy={del.isLoading}
          />
        </>
      )}

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

      <Modal isOpen={modal === 'view'} onClose={close} title="Запись о еде">
        {viewing && <MealDetail meal={viewing} onUpdated={handleViewedUpdated} />}
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

      <Modal isOpen={modal === 'barcode'} onClose={close} title="Блюдо по штрих-коду">
        {modal === 'barcode' && (
          <BarcodeFlow onConfirm={handleAdd} onCancel={close} saving={add.isLoading} />
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
