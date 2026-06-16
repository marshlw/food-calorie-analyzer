/* Types for the application */

export interface User {
  id: number
  email: string
  full_name?: string
  is_active: boolean
  created_at: string
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export type TaskStatus = 'pending' | 'processing' | 'success' | 'failure'

// Поля соответствуют схеме TaskResponse на бэкенде (app/schemas.py).
// Бэкенд НЕ возвращает result_json/user_id, а result уже распарсен.
export interface Task {
  id: string
  status: TaskStatus
  image_path?: string
  error?: string
  created_at: string
  updated_at?: string
}

export interface TaskResponse extends Task {
  result?: AnalysisResult
}

export type IngredientType = 'protein' | 'carb' | 'fat' | 'vegetable' | 'unknown'

export interface Ingredient {
  name: string
  type: IngredientType
  weight_g: number
}

export interface AnalysisResult {
  food?: string
  food_name?: string
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
  weight_g: number
  confidence?: number
  ingredients?: Ingredient[]
}

export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snacks'

export interface MealEntry {
  id: number
  food_name: string
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
  weight_g: number
  meal_type: MealType
  created_at: string
  // Если запись создана из AI-анализа, бэкенд возвращает связанный task_id.
  // Источник (AI/ручной) выводим из его наличия — отдельной колонки в БД нет.
  task_id?: string | null
}

export interface MealEntryCreate {
  food_name: string
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
  weight_g: number
  meal_type: MealType
  // Необязательные: день записи (по умолчанию сегодня) и связь с AI-задачей.
  date?: string
  task_id?: string
}

export interface DailyLog {
  date: string
  total_calories: number
  total_protein: number
  total_fat: number
  total_carbs: number
  meals: MealEntry[]
}

export interface AuthContextType {
  user: User | null
  token: Token | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName?: string) => Promise<void>
  logout: () => void
  clearError: () => void
}

// FastAPI на ошибках валидации возвращает detail как массив объектов
// вида { loc, msg, type }, поэтому тип расширен.
export interface ApiError {
  detail?: string | Array<string | { msg?: string; loc?: (string | number)[]; type?: string }>
  message?: string
}
