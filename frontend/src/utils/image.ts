/**
 * Нормализация фото перед отправкой на сервер.
 *
 * Зачем: камера iPhone снимает в HEIC, и Safari отдаёт этот файл как есть,
 * если accept допускает произвольные изображения, если фото выбрано через
 * «Файлы» или если страница открыта во встроенном WebView (Telegram и т.п.).
 * HEIC не понимают vision-провайдеры, а снимки с телефона вдобавок весят
 * по 5–12 МБ и почти всегда повёрнуты EXIF-тегом Orientation.
 *
 * WebKit умеет декодировать HEIC системным кодеком, поэтому перерисовка
 * через canvas даёт готовый JPEG нужного размера и в правильной ориентации
 * (браузеры применяют EXIF Orientation к <img> по умолчанию, а canvas
 * метаданные не сохраняет).
 *
 * Если конвертация не удалась — отдаём оригинал: сервер тоже умеет
 * разбирать HEIC, клиентский шаг лишь снимает с него нагрузку.
 */

// Должно совпадать с settings.MAX_IMAGE_SIZE на бэкенде
const MAX_SIDE = 1600
const JPEG_QUALITY = 0.9

// Форматы, которые принимает сервер. Явный список вместо image/* важен:
// при нём WebKit сам транскодирует HEIC в JPEG в части сценариев, а в
// приложении «Файлы» на iOS фильтр показывает только подходящие файлы.
export const UPLOAD_ACCEPT =
  'image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif'

const isHeic = (file: File): boolean =>
  /image\/(heic|heif)/i.test(file.type) || /\.(heic|heif)$/i.test(file.name)

const loadImage = (src: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Не удалось декодировать изображение'))
    img.src = src
  })

const canvasToBlob = (canvas: HTMLCanvasElement): Promise<Blob> =>
  new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Не удалось закодировать JPEG'))),
      'image/jpeg',
      JPEG_QUALITY
    )
  })

const withJpegExtension = (name: string): string =>
  `${name.replace(/\.[^./\\]+$/, '') || 'photo'}.jpg`

/**
 * Приводит выбранное фото к JPEG со стороной не больше MAX_SIDE.
 * Никогда не бросает исключение: при любой ошибке возвращает исходный файл.
 */
export const prepareImageForUpload = async (file: File): Promise<File> => {
  const objectUrl = URL.createObjectURL(file)

  try {
    const img = await loadImage(objectUrl)

    // naturalWidth/Height уже учитывают EXIF Orientation
    const width = img.naturalWidth || img.width
    const height = img.naturalHeight || img.height
    if (!width || !height) throw new Error('Пустое изображение')

    const scale = Math.min(1, MAX_SIDE / Math.max(width, height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(width * scale))
    canvas.height = Math.max(1, Math.round(height * scale))

    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas недоступен')

    // Белая подложка: у PNG с прозрачностью альфа в JPEG станет чёрной
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    const blob = await canvasToBlob(canvas)

    // Перекодированный JPEG иногда крупнее оригинала (мелкие PNG, сильно
    // сжатые JPEG). Оригинал в этом случае лучше — если он не HEIC.
    if (!isHeic(file) && blob.size >= file.size && Math.max(width, height) <= MAX_SIDE) {
      return file
    }

    return new File([blob], withJpegExtension(file.name), {
      type: 'image/jpeg',
      lastModified: Date.now(),
    })
  } catch {
    // HEIC на не-Apple браузере, повреждённый файл, нехватка памяти —
    // пусть решает сервер, он умеет декодировать те же форматы.
    return file
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}
