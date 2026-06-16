/* Types for the application */

export interface User {
  id: string
  email: string
  full_name?: string
  created_at: string
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export type TaskStatus = 'pending' | 'processing' | 'success' | 'failure'

export interface Task {
  id: string
  user_id: string
  image_path: string
  status: TaskStatus
  result_json?: string
  error?: string
  created_at: string
}

export interface TaskResponse extends Task {
  result?: AnalysisResult
}

export interface AnalysisResult {
  food?: string
  food_name?: string
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
  weight_g: number
}

export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'

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
}

export interface MealEntryCreate {
  food_name: string
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
  weight_g: number
  meal_type: MealType
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

export interface ApiError {
  detail?: string | string[]
  message?: string
}
