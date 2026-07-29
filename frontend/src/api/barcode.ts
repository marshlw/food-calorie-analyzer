import { apiClient } from './axios'
import { BarcodeProduct } from '../types'
import { prepareImageForUpload } from '../utils/image'

export const barcodeApi = {
  // Фото штрих-кода упаковки → бэкенд декодирует код и ищет продукт
  // в Open Food Facts (название + КБЖУ на 100 г).
  scan: async (file: File): Promise<BarcodeProduct> => {
    const prepared = await prepareImageForUpload(file)
    const form = new FormData()
    form.append('file', prepared)
    const response = await apiClient.post<BarcodeProduct>('/api/v1/barcode/scan', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  // Поиск по цифрам штрих-кода (ручной ввод, если фото не распозналось).
  lookup: async (code: string): Promise<BarcodeProduct> => {
    const response = await apiClient.get<BarcodeProduct>(
      `/api/v1/barcode/${encodeURIComponent(code)}`
    )
    return response.data
  },
}
