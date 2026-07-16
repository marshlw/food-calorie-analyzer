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
  // Источник белка ингредиента (по справочнику): animal | plant | mixed | unknown.
  protein_type?: ProteinType
}

// Источник белка продукта/блюда: животный, растительный или смешанный.
// 'unknown' — источник не определён (продукт вне справочника / не указан).
export type ProteinType = 'animal' | 'plant' | 'mixed' | 'unknown'

export interface AnalysisResult {
  food?: string
  food_name?: string
  calories: number
  protein_g: number
  // Разделение белка на животный/растительный (по справочнику продуктов).
  protein_animal_g?: number
  protein_plant_g?: number
  fat_g: number
  carbs_g: number
  weight_g: number
  confidence?: number
  ingredients?: Ingredient[]
}

export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snacks'

// Одно блюдо в составном приёме («гарнир + основное блюдо»)
export interface MealEntryItem {
  id?: number
  food_name: string
  weight_g: number
  calories: number
  protein_g: number
  // Разделение белка блюда (г); сумма ≤ protein_g, остаток — «не определён».
  protein_animal_g?: number
  protein_plant_g?: number
  fat_g: number
  carbs_g: number
}

export interface MealEntry {
  id: number
  food_name: string
  calories: number
  protein_g: number
  // Разделение белка записи на животный/растительный (г).
  protein_animal_g?: number
  protein_plant_g?: number
  fat_g: number
  carbs_g: number
  weight_g: number
  meal_type: MealType
  created_at: string
  // Если запись создана из AI-анализа, бэкенд возвращает связанный task_id.
  // Источник (AI/ручной) выводим из его наличия — отдельной колонки в БД нет.
  task_id?: string | null
  // Фото записи: URL (раздаётся бэкендом через /uploads) и источник —
  // 'user' (добавлено вручную) или 'ai' (фото из AI-анализа).
  photo_url?: string | null
  photo_source?: 'user' | 'ai' | null
  // Блюда составного приёма (пусто у простых записей).
  items?: MealEntryItem[]
}

export interface MealEntryCreate {
  food_name: string
  calories: number
  protein_g: number
  // Разделение белка (г). Для составного приёма пересчитает бэкенд из блюд.
  protein_animal_g?: number
  protein_plant_g?: number
  fat_g: number
  carbs_g: number
  weight_g: number
  meal_type: MealType
  // Необязательные: день записи (по умолчанию сегодня) и связь с AI-задачей.
  date?: string
  task_id?: string
  // Составной приём: итоги пересчитает бэкенд из блюд.
  items?: MealEntryItem[]
}

export interface NutritionTargets {
  calories?: number | null
  protein_g?: number | null
  // Разделение нормы белка на животный/растительный.
  protein_animal_g?: number | null
  protein_plant_g?: number | null
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
  // Разделение суммарного белка за день на животный/растительный.
  total_protein_animal?: number
  total_protein_plant?: number
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
  // Источник белка: animal | plant | mixed (null у старых записей до миграции).
  protein_type?: ProteinType | null
}

// ==================== BARCODE (Open Food Facts) ====================

// Продукт, найденный по штрих-коду упаковки. Нутриенты — на 100 г,
// пересчёт на граммовку делает клиент.
export interface BarcodeProduct {
  barcode: string
  name: string
  brand?: string | null
  quantity?: string | null // объём/вес с упаковки, например «500 g»
  calories_100g: number
  protein_100g: number
  fat_100g: number
  carbs_100g: number
  image_url?: string | null
  source: 'openfoodfacts' | 'cache'
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
  // Обхваты тела (см); null у записей, где замер не заполняли.
  waist_cm?: number | null
  chest_cm?: number | null
  hips_cm?: number | null
  shoulders_cm?: number | null
}

export interface Profile {
  id: number
  email: string
  full_name?: string | null
  height_cm?: number | null
  current_weight_kg?: number | null
  // Текущие обхваты (из последней записи истории) — для «Личных данных».
  current_waist_cm?: number | null
  current_chest_cm?: number | null
  current_hips_cm?: number | null
  current_shoulders_cm?: number | null
  sex?: Sex | null
  birth_date?: string | null
  activity_level?: ActivityLevel | null
  recent_weights: WeightRecord[]
  bmr?: number | null
  daily_calorie_target?: number | null
  protein_target_g?: number | null
  // Разделение нормы белка на животный/растительный.
  protein_animal_target_g?: number | null
  protein_plant_target_g?: number | null
  fat_target_g?: number | null
  carbs_target_g?: number | null
  water_target_ml?: number | null
  // Ручные переопределения норм (null = эта норма считается автоматически)
  custom_calorie_target?: number | null
  custom_protein_g?: number | null
  custom_protein_animal_g?: number | null
  custom_protein_plant_g?: number | null
  custom_fat_g?: number | null
  custom_carbs_g?: number | null
  custom_water_ml?: number | null
}

export interface ProfileUpdate {
  full_name?: string
  height_cm?: number
  weight_kg?: number
  sex?: Sex
  birth_date?: string
  activity_level?: ActivityLevel
  // Обхваты тела (см) — все опциональны, сохраняются в запись веса за сегодня.
  waist_cm?: number
  chest_cm?: number
  hips_cm?: number
  shoulders_cm?: number
  // По умолчанию true: изменённый в форме вес/обхваты уходят в историю.
  save_weight_as_record?: boolean
  // Ручные нормы: undefined = не менять, 0 = вернуть авторасчёт, >0 = установить
  custom_calorie_target?: number
  custom_protein_g?: number
  custom_protein_animal_g?: number
  custom_protein_plant_g?: number
  custom_fat_g?: number
  custom_carbs_g?: number
  custom_water_ml?: number
}

export interface WeightRecordCreate {
  weight_kg: number
  recorded_on?: string
  note?: string
  // Обхваты тела (см) — все опциональны.
  waist_cm?: number
  chest_cm?: number
  hips_cm?: number
  shoulders_cm?: number
}

// Редактирование записи замера. Обхваты задаются явно: null очищает
// значение (пустое поле в форме = убрать показатель).
export interface WeightRecordUpdate {
  weight_kg: number
  recorded_on?: string
  note?: string | null
  waist_cm?: number | null
  chest_cm?: number | null
  hips_cm?: number | null
  shoulders_cm?: number | null
}

// Метрики тела, доступные в графике прогресса и в форме замера.
export type BodyMetric = 'weight_kg' | 'waist_cm' | 'chest_cm' | 'hips_cm' | 'shoulders_cm'

export interface BodyMetricMeta {
  key: BodyMetric
  label: string // «Вес», «Талия», …
  short: string // короткая метка для пилюль
  unit: string  // «кг» | «см»
  color: string // цвет линии на графике
}

// Единый источник правды для подписей/цветов метрик тела.
export const BODY_METRICS: BodyMetricMeta[] = [
  { key: 'weight_kg', label: 'Вес', short: 'Вес', unit: 'кг', color: '#2b6fe3' },
  { key: 'waist_cm', label: 'Талия', short: 'Талия', unit: 'см', color: '#e0663d' },
  { key: 'chest_cm', label: 'Грудь', short: 'Грудь', unit: 'см', color: '#7c5ce6' },
  { key: 'hips_cm', label: 'Бёдра', short: 'Бёдра', unit: 'см', color: '#2ba77a' },
  { key: 'shoulders_cm', label: 'Плечи', short: 'Плечи', unit: 'см', color: '#d4a017' },
]

// ==================== WORKOUTS (вкладка «Тренировки») ====================

export type WorkoutType = 'strength' | 'cardio' | 'stretching' | 'sport' | 'other'

// Одно упражнение в составной тренировке («жим лёжа 25 мин 150 ккал»)
export interface WorkoutItem {
  id?: number
  name: string
  duration_min: number
  calories_burned: number
}

export interface Workout {
  id: number
  date: string // YYYY-MM-DD
  workout_type: WorkoutType
  title: string
  description?: string | null
  started_at?: string | null // "HH:MM"
  duration_min: number
  calories_burned: number
  created_at: string
  // Упражнения составной тренировки (пусто у простых записей).
  items?: WorkoutItem[]
}

export interface WorkoutCreate {
  title: string
  workout_type: WorkoutType
  duration_min: number
  calories_burned: number
  description?: string
  started_at?: string
  date?: string
  // Конструктор: несколько упражнений; итоги пересчитает бэкенд.
  items?: WorkoutItem[]
}

export interface WorkoutDaySummary {
  date: string
  total_calories_burned: number
  total_duration_min: number
  count: number
  base_calorie_target?: number | null
  adjusted_calorie_target?: number | null
}

export interface WorkoutWeekDay {
  date: string
  has_workout: boolean
}

export interface WorkoutsResponse {
  date: string
  workouts: Workout[]
  summary: WorkoutDaySummary
  week: WorkoutWeekDay[]
}

// Справочник упражнений: примерный расход ккал/мин (человек ~70 кг)
export interface Exercise {
  id: number
  name: string
  category: WorkoutType
  kcal_per_min: number
  kcal_per_30min: number
}

// ==================== AI-СОВЕТЧИК ====================

export interface AdvisorTip {
  title: string
  text: string
  tag: string // protein|water|calories|carbs|training|general
}

export interface AdvisorResponse {
  headline_title: string
  headline_text: string
  nutrition: AdvisorTip[]
  training: AdvisorTip[]
  generated_by: 'llm' | 'rules'
}

export interface AdvisorAskResponse {
  answer: string
  generated_by: 'llm' | 'rules'
}

// Опциональные данные профиля, заполняемые при регистрации.
export interface RegisterProfile {
  height_cm?: number
  weight_kg?: number
  sex?: Sex
  birth_date?: string // YYYY-MM-DD
  // Обхваты тела (см) — попадут в первую запись веса (нужен вес).
  waist_cm?: number
  chest_cm?: number
  hips_cm?: number
  shoulders_cm?: number
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
    profile?: RegisterProfile
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
