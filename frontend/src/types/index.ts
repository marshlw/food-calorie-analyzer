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

// Дневной лимит AI-анализов (GET /api/v1/analyze/limit)
export interface AiAnalysisLimit {
  limit: number
  used: number
  remaining: number
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

export interface NutritionTargets {
  calories?: number | null
  protein_g?: number | null
  fat_g?: number | null
  carbs_g?: number | null
}

export interface WaterStatus {
  date: string
  total_ml: number
  goal_ml?: number | null // суточная норма (null, если нет веса в профиле)
  glass_ml: number // объём одного стакана
}

export interface DailyLog {
  date: string
  total_calories: number
  total_protein: number
  total_fat: number
  total_carbs: number
  meals: MealEntry[]
  // Суточные нормы КБЖУ пользователя (для колец/сводки).
  targets?: NutritionTargets | null
  // Вода за этот день (для кольца-инфографики).
  water?: WaterStatus | null
}

// ==================== PRODUCTS (справочник КБЖУ) ====================

// Нутриенты указаны на 100 г продукта.
export interface Product {
  id: number
  name: string
  calories: number
  protein: number
  fat: number
  carbs: number
}

// ==================== PROFILE / WEIGHT ====================

export type Sex = 'male' | 'female'
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active'

export interface WeightRecord {
  id: number
  weight_kg: number
  recorded_on: string // YYYY-MM-DD
  note?: string | null
  source: string // manual | registration | profile_edit
}

export interface Profile {
  id: number
  email: string
  full_name?: string | null
  height_cm?: number | null
  current_weight_kg?: number | null
  sex?: Sex | null
  birth_date?: string | null
  activity_level?: ActivityLevel | null
  recent_weights: WeightRecord[]
  bmr?: number | null
  daily_calorie_target?: number | null
  protein_target_g?: number | null
  fat_target_g?: number | null
  carbs_target_g?: number | null
  water_target_ml?: number | null
}

export interface ProfileUpdate {
  full_name?: string
  height_cm?: number
  weight_kg?: number
  sex?: Sex
  birth_date?: string
  activity_level?: ActivityLevel
  // По умолчанию true: изменённый в форме вес уходит в историю.
  save_weight_as_record?: boolean
}

export interface WeightRecordCreate {
  weight_kg: number
  recorded_on?: string
  note?: string
}

export interface AuthContextType {
  user: User | null
  token: Token | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (
    email: string,
    password: string,
    fullName?: string,
    profile?: { height_cm?: number; weight_kg?: number }
  ) => Promise<void>
  logout: () => void
  clearError: () => void
}

// FastAPI на ошибках валидации возвращает detail как массив объектов
// вида { loc, msg, type }, поэтому тип расширен.
export interface ApiError {
  detail?: string | Array<string | { msg?: string; loc?: (string | number)[]; type?: string }>
  message?: string
}
