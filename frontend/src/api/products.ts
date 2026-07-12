import { apiClient } from './axios'
import { Product } from '../types'

export const productsApi = {
  // Поиск продукта по (части) названия для автодополнения при добавлении
  // ингредиента. Пустой запрос вернёт продукты по алфавиту.
  search: async (query: string, limit = 20): Promise<Product[]> => {
    const response = await apiClient.get<Product[]>('/api/v1/products', {
      params: { q: query, limit },
    })
    return response.data
  },
}
