import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ScanBarcode, Image as ImageIcon, Zap, ZapOff } from 'lucide-react'
import { BrowserMultiFormatReader, IScannerControls } from '@zxing/browser'
import { BarcodeFormat, DecodeHintType } from '@zxing/library'
import { barcodeApi } from '../api/barcode'
import { LoadingSpinner } from './LoadingSpinner'
import { ErrorAlert } from './ErrorAlert'
import { extractErrorMessage } from '../utils/errors'
import { BarcodeProduct, MealEntryCreate, MealType } from '../types'

const round1 = (v: number) => Math.round(v * 10) / 10

const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: 'breakfast', label: 'Завтрак' },
  { value: 'lunch', label: 'Обед' },
  { value: 'dinner', label: 'Ужин' },
  { value: 'snacks', label: 'Перекус' },
]

interface Props {
  // Сохранение выбранного продукта (родитель добавит дату выбранного дня)
  onConfirm: (data: MealEntryCreate) => Promise<void> | void
  onCancel: () => void
  saving?: boolean
}

type Phase = 'camera' | 'scanning' | 'error' | 'done'

// Доля кадра, которую занимает рамка наведения.
const FRAME_W = 0.85
const FRAME_H = 0.45

// Штрих-код распознаётся прямо в браузере из живого потока камеры — много
// кадров в секунду, поэтому смазанный кадр не мешает: декодер просто берёт
// следующий. Ограничиваем набор форматов розничными кодами еды (EAN/UPC) —
// так распознавание быстрее и без ложных срабатываний.
const buildHints = () => {
  const hints = new Map<DecodeHintType, unknown>()
  hints.set(DecodeHintType.POSSIBLE_FORMATS, [
    BarcodeFormat.EAN_13,
    BarcodeFormat.EAN_8,
    BarcodeFormat.UPC_A,
    BarcodeFormat.UPC_E,
  ])
  hints.set(DecodeHintType.TRY_HARDER, true)
  return hints
}

// Поток «блюдо по штрих-коду»: живая камера с автораспознаванием (или загрузка
// фото) → поиск по коду в базе → выбор граммовки → расчёт КБЖУ → добавление.
export const BarcodeFlow: React.FC<Props> = ({ onConfirm, onCancel, saving }) => {
  const [phase, setPhase] = useState<Phase>('camera')
  const [product, setProduct] = useState<BarcodeProduct | null>(null)
  const [error, setError] = useState('')
  const [weight, setWeight] = useState('100')
  const [mealType, setMealType] = useState<MealType>('snacks')
  const [manualCode, setManualCode] = useState('')
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraFailed, setCameraFailed] = useState(false)
  const [torchAvailable, setTorchAvailable] = useState(false)
  const [torchOn, setTorchOn] = useState(false)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const controlsRef = useRef<IScannerControls | null>(null)
  // Защита от повторной обработки: колбэк декодера может сработать несколько раз
  const handledRef = useRef(false)

  const stopScanner = useCallback(() => {
    controlsRef.current?.stop()
    controlsRef.current = null
    setCameraReady(false)
    setTorchAvailable(false)
    setTorchOn(false)
  }, [])

  // Код распознан на клиенте → ищем продукт по цифрам в базе (Open Food Facts).
  // На бэкенд больше не шлём картинку — только готовый код через GET /barcode/{code}.
  const handleCode = useCallback(
    async (code: string) => {
      if (handledRef.current) return
      handledRef.current = true
      // Короткая вибрация — тактильное подтверждение, что код пойман
      // (navigator.vibrate есть в Android Chrome; iOS Safari его игнорирует)
      navigator.vibrate?.(80)
      stopScanner()
      setPhase('scanning')
      setError('')
      try {
        setProduct(await barcodeApi.lookup(code))
        setPhase('done')
      } catch (e) {
        setError(extractErrorMessage(e))
        setPhase('error')
      }
    },
    [stopScanner]
  )

  // Живая камера + непрерывное декодирование на фазе 'camera'.
  // Гасится при уходе с фазы/размонтировании.
  useEffect(() => {
    if (phase !== 'camera') return
    handledRef.current = false
    let cancelled = false

    const reader = new BrowserMultiFormatReader(buildHints(), {
      delayBetweenScanAttempts: 120,
      delayBetweenScanSuccess: 400,
    })

    // Просим у камеры высокое разрешение и непрерывный автофокус — это ключевое
    // для iPhone, где на дефолтном потоке фокус «плавает» и код выходит смазанным.
    const tuneTrack = async () => {
      const stream = videoRef.current?.srcObject as MediaStream | null
      const track = stream?.getVideoTracks?.()[0]
      if (!track) return
      const caps = (track.getCapabilities?.() ?? {}) as Record<string, unknown>
      try {
        const focusModes = caps.focusMode as string[] | undefined
        if (focusModes?.includes('continuous')) {
          await track.applyConstraints({
            advanced: [{ focusMode: 'continuous' } as unknown as MediaTrackConstraintSet],
          })
        }
      } catch {
        // Управление фокусом доступно не на всех устройствах — не критично
      }
      if (caps.torch) setTorchAvailable(true)
    }

    const start = async () => {
      setCameraFailed(false)
      if (!videoRef.current) return
      try {
        const controls = await reader.decodeFromConstraints(
          {
            video: {
              facingMode: { ideal: 'environment' },
              width: { ideal: 1920 },
              height: { ideal: 1080 },
            },
            audio: false,
          },
          videoRef.current,
          (result) => {
            if (result) handleCode(result.getText())
          }
        )
        if (cancelled) {
          controls.stop()
          return
        }
        controlsRef.current = controls
        setCameraReady(true)
        tuneTrack()
      } catch {
        // Нет камеры или нет разрешения — остаётся загрузка фото / ручной ввод
        if (!cancelled) setCameraFailed(true)
      }
    }

    start()
    return () => {
      cancelled = true
      controlsRef.current?.stop()
      controlsRef.current = null
    }
  }, [phase, handleCode])

  // Вспышка (torch) помогает распознать код в тени/на глянцевой упаковке
  const toggleTorch = async () => {
    const stream = videoRef.current?.srcObject as MediaStream | null
    const track = stream?.getVideoTracks?.()[0]
    if (!track) return
    try {
      await track.applyConstraints({
        advanced: [{ torch: !torchOn } as unknown as MediaTrackConstraintSet],
      })
      setTorchOn((v) => !v)
    } catch {
      // Устройство не поддерживает управление вспышкой
    }
  }

  // Загрузка фото из галереи — декодирование на сервере (фолбэк к живой камере)
  const scan = async (file: File) => {
    stopScanner()
    setPhase('scanning')
    setError('')
    try {
      setProduct(await barcodeApi.scan(file))
      setPhase('done')
    } catch (e) {
      setError(extractErrorMessage(e))
      setPhase('error')
    }
  }

  // Ручной ввод цифр кода, если сканирование не удалось
  const lookupManual = async () => {
    const code = manualCode.replace(/\D/g, '')
    if (code.length < 8) {
      setError('Введите цифры штрих-кода (минимум 8)')
      return
    }
    setPhase('scanning')
    setError('')
    try {
      setProduct(await barcodeApi.lookup(code))
      setPhase('done')
    } catch (e) {
      setError(extractErrorMessage(e))
      setPhase('error')
    }
  }

  const uploadInput = (
    <label className="btn-secondary w-full flex items-center justify-center gap-2 cursor-pointer">
      <ImageIcon className="h-[18px] w-[18px]" /> Загрузить фото штрих-кода
      <input
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) scan(f)
          e.target.value = ''
        }}
      />
    </label>
  )

  const cancelButton = (
    <button
      type="button"
      className="w-full py-3 text-sm font-medium text-muted dark:text-muted-dark hover:text-ink dark:hover:text-ink-dark transition-colors"
      onClick={onCancel}
    >
      Отмена
    </button>
  )

  if (phase === 'camera') {
    return (
      <div className="space-y-3">
        {!cameraFailed ? (
          <>
            <div className="relative overflow-hidden rounded-tile bg-black">
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                className="w-full h-64 object-cover"
              />
              {/* Рамка наведения: подсвеченное окно, фон затемнён */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div
                  className="rounded-2xl border-2 border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]"
                  style={{ width: `${FRAME_W * 100}%`, height: `${FRAME_H * 100}%` }}
                >
                  {/* Бегущая линия-«сканер», пока камера активна */}
                  {cameraReady && (
                    <div className="absolute inset-x-0 top-1/2 h-0.5 bg-red-500/80 shadow-[0_0_8px_2px_rgba(239,68,68,0.6)]" />
                  )}
                </div>
              </div>
              {/* Кнопка вспышки — если устройство её поддерживает */}
              {torchAvailable && (
                <button
                  type="button"
                  onClick={toggleTorch}
                  aria-label={torchOn ? 'Выключить вспышку' : 'Включить вспышку'}
                  className="absolute top-2 right-2 rounded-full bg-black/50 p-2 text-white backdrop-blur"
                >
                  {torchOn ? (
                    <ZapOff className="h-[18px] w-[18px]" />
                  ) : (
                    <Zap className="h-[18px] w-[18px]" />
                  )}
                </button>
              )}
              <p className="absolute bottom-2 inset-x-0 text-center text-white/90 text-xs pointer-events-none">
                {cameraReady
                  ? 'Наведите штрих-код на рамку — распознаем автоматически'
                  : 'Включаем камеру…'}
              </p>
            </div>
          </>
        ) : (
          <ErrorAlert
            message="Камера недоступна. Загрузите фото штрих-кода или введите его цифры."
            onClose={() => {}}
          />
        )}

        {uploadInput}

        {cameraFailed && (
          <div>
            <label className="block text-[13px] font-semibold mb-1.5">
              Или введите цифры под штрих-кодом
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                inputMode="numeric"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                placeholder="4600000000000"
                className="input flex-1"
              />
              <button type="button" className="btn-primary px-4" onClick={lookupManual}>
                Найти
              </button>
            </div>
          </div>
        )}

        {cancelButton}
      </div>
    )
  }

  if (phase === 'scanning') {
    return <LoadingSpinner message="Распознаём штрих-код…" />
  }

  if (phase === 'error') {
    return (
      <div className="space-y-3">
        <ErrorAlert message={error || 'Не удалось распознать штрих-код'} onClose={() => {}} />
        <button type="button" className="btn-secondary w-full" onClick={() => setPhase('camera')}>
          Сканировать ещё раз
        </button>

        {/* Фолбэк: цифры кода напечатаны под штрихами на любой упаковке */}
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">
            Или введите цифры под штрих-кодом
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              inputMode="numeric"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              placeholder="4600000000000"
              className="input flex-1"
            />
            <button type="button" className="btn-primary px-4" onClick={lookupManual}>
              Найти
            </button>
          </div>
        </div>

        {cancelButton}
      </div>
    )
  }

  if (phase === 'done' && product) {
    const w = parseFloat(weight) || 0
    const factor = w / 100
    const totals = {
      calories: round1(product.calories_100g * factor),
      protein: round1(product.protein_100g * factor),
      fat: round1(product.fat_100g * factor),
      carbs: round1(product.carbs_100g * factor),
    }

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault()
      if (w <= 0) {
        setError('Укажите вес порции в граммах')
        return
      }
      setError('')
      const name = product.brand ? `${product.name} (${product.brand})` : product.name
      try {
        await onConfirm({
          food_name: name.slice(0, 200),
          weight_g: round1(w),
          calories: totals.calories,
          protein_g: totals.protein,
          fat_g: totals.fat,
          carbs_g: totals.carbs,
          meal_type: mealType,
        })
      } catch {
        // Ошибку сохранения показывает родитель (ErrorAlert на странице)
      }
    }

    return (
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Карточка найденного продукта */}
        <div className="flex items-start gap-3 rounded-tile border border-line dark:border-line-dark bg-surface dark:bg-chip-dark/50 p-3">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.name}
              className="w-16 h-16 object-cover rounded-xl flex-shrink-0"
            />
          ) : (
            <div className="w-16 h-16 rounded-xl bg-primary-50 dark:bg-chip-dark flex items-center justify-center flex-shrink-0">
              <ScanBarcode className="h-7 w-7 text-primary-500" />
            </div>
          )}
          <div className="min-w-0">
            <p className="font-display font-bold text-base tracking-tight leading-tight">
              {product.name}
            </p>
            <p className="text-xs text-secondary mt-0.5">
              {[product.brand, product.quantity].filter(Boolean).join(' · ')}
            </p>
            <p className="text-[11px] text-tertiary mt-1">Штрих-код {product.barcode}</p>
          </div>
        </div>

        {/* КБЖУ на 100 г */}
        <div className="flex justify-between items-center px-4 py-2.5 rounded-tile bg-surface dark:bg-chip-dark/50 border border-line dark:border-line-dark">
          <span className="text-[13px] font-semibold text-muted dark:text-muted-dark">На 100 г</span>
          <span className="text-[13px] font-medium">
            {Math.round(product.calories_100g)} ккал · Б {round1(product.protein_100g)} · Ж{' '}
            {round1(product.fat_100g)} · У {round1(product.carbs_100g)}
          </span>
        </div>

        {/* Граммовка порции */}
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">Сколько съели, г</label>
          <input
            type="number"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            min="1"
            step="1"
            className="input"
            disabled={saving}
            autoFocus
          />
        </div>

        {/* Приём пищи */}
        <div>
          <label className="block text-[13px] font-semibold mb-1.5">Приём пищи</label>
          <div className="grid grid-cols-4 gap-2 bg-white dark:bg-card-dark border border-line dark:border-line-dark rounded-tile p-1.5">
            {MEAL_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => setMealType(type.value)}
                className={`py-2 text-[13px] rounded-xl transition-colors ${
                  mealType === type.value
                    ? 'bg-primary-500 text-white font-semibold'
                    : 'text-muted dark:text-muted-dark font-medium hover:bg-surface dark:hover:bg-chip-dark'
                }`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>

        {/* Итог на выбранный вес */}
        <div className="flex justify-between items-center px-4 py-3 rounded-tile bg-primary-50 dark:bg-chip-dark text-primary-500 dark:text-primary-400">
          <span className="text-[13px] font-semibold">Итого · {Math.round(w)} г</span>
          <span className="text-[13px] font-bold">
            {Math.round(totals.calories)} ккал · Б {Math.round(totals.protein)} · Ж{' '}
            {Math.round(totals.fat)} · У {Math.round(totals.carbs)}
          </span>
        </div>

        {error && <p className="text-danger text-xs">{error}</p>}

        <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
          {saving ? 'Загрузка...' : 'Добавить в дневник'}
        </button>
        <button
          type="button"
          className="w-full py-3 text-sm font-medium text-muted dark:text-muted-dark hover:text-ink dark:hover:text-ink-dark transition-colors"
          onClick={() => setPhase('camera')}
        >
          Сканировать другой продукт
        </button>
      </form>
    )
  }

  return null
}
