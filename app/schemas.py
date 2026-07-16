# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, root_validator, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from datetime import date as _date  # алиас: поле MealEntryCreate.date затеняет имя date
import json
import logging

logger = logging.getLogger(__name__)


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: Literal["bearer"] = "bearer"


class AuthRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    grant_type: str = "password"
    refresh_token: Optional[str] = None

    @root_validator(pre=True)
    def validate_grant_type(cls, values):
        grant_type = values.get("grant_type", "password")
        if grant_type == "password":
            if not values.get("email"):
                raise ValueError("email is required for password grant_type")
            if not values.get("password"):
                raise ValueError("password is required for password grant_type")
        elif grant_type == "refresh_token":
            if not values.get("refresh_token"):
                raise ValueError("refresh_token is required for refresh_token grant_type")
        return values


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=120)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    # Опционально при регистрации: если заполнены, вес станет первой
    # записью в истории взвешиваний (см. main.register).
    height_cm: Optional[float] = Field(None, gt=0, lt=300)
    weight_kg: Optional[float] = Field(None, gt=0, lt=300)
    # Пол и дата рождения (возраст) — для расчёта BMR/норм калорий.
    sex: Optional[Literal["male", "female"]] = None
    birth_date: Optional[_date] = None
    # Обхваты тела (см) — попадут в первую запись веса вместе с весом.
    waist_cm: Optional[float] = Field(None, gt=0, lt=300)      # талия
    chest_cm: Optional[float] = Field(None, gt=0, lt=300)      # грудь
    hips_cm: Optional[float] = Field(None, gt=0, lt=300)       # бёдра
    shoulders_cm: Optional[float] = Field(None, gt=0, lt=300)  # плечи


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== PROFILE / WEIGHT ====================

class WeightRecordCreate(BaseModel):
    weight_kg: float = Field(..., gt=0, lt=300)
    recorded_on: Optional[_date] = None  # по умолчанию -- сегодня
    note: Optional[str] = Field(None, max_length=200)
    # Обхваты тела (см) -- все опциональны. None = не заполнять/не менять.
    waist_cm: Optional[float] = Field(None, gt=0, lt=300)      # талия
    chest_cm: Optional[float] = Field(None, gt=0, lt=300)      # грудь
    hips_cm: Optional[float] = Field(None, gt=0, lt=300)       # бёдра
    shoulders_cm: Optional[float] = Field(None, gt=0, lt=300)  # плечи


class WeightRecordUpdate(BaseModel):
    """Редактирование существующей записи замера. В отличие от upsert,
    здесь обхваты задаются явно: None очищает ранее заполненное значение
    (в форме редактирования пустое поле = убрать показатель)."""
    weight_kg: float = Field(..., gt=0, lt=300)
    recorded_on: Optional[_date] = None  # None = не менять дату записи
    note: Optional[str] = Field(None, max_length=200)
    waist_cm: Optional[float] = Field(None, gt=0, lt=300)
    chest_cm: Optional[float] = Field(None, gt=0, lt=300)
    hips_cm: Optional[float] = Field(None, gt=0, lt=300)
    shoulders_cm: Optional[float] = Field(None, gt=0, lt=300)


class WeightRecordResponse(BaseModel):
    id: int
    weight_kg: float
    recorded_on: _date
    note: Optional[str] = None
    source: str
    # Обхваты тела (см); None у записей, где замер не заполняли.
    waist_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    shoulders_cm: Optional[float] = None

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=120)
    height_cm: Optional[float] = Field(None, gt=0, lt=300)
    weight_kg: Optional[float] = Field(None, gt=0, lt=300)
    sex: Optional[Literal["male", "female"]] = None
    birth_date: Optional[_date] = None
    activity_level: Optional[Literal[
        "sedentary", "light", "moderate", "active", "very_active"
    ]] = None
    # Обхваты тела (см) — все опциональны. Сохраняются в запись веса за сегодня
    # (тот же источник, что и модалка замера). None = не менять.
    waist_cm: Optional[float] = Field(None, gt=0, lt=300)      # талия
    chest_cm: Optional[float] = Field(None, gt=0, lt=300)      # грудь
    hips_cm: Optional[float] = Field(None, gt=0, lt=300)       # бёдра
    shoulders_cm: Optional[float] = Field(None, gt=0, lt=300)  # плечи
    # UX «Сохранить как новую запись?». По умолчанию True: вес/обхваты из формы
    # профиля попадают в историю (за сегодня, upsert'ом).
    save_weight_as_record: bool = True
    # Ручные нормы (для атлетов): None = не менять, 0 = вернуть авторасчёт,
    # положительное значение = установить. Подхватываются во всех формах.
    custom_calorie_target: Optional[float] = Field(None, ge=0, le=20000)
    custom_protein_g: Optional[float] = Field(None, ge=0, le=2000)
    # Ручные нормы животного/растительного белка (0 = вернуть авторасчёт).
    custom_protein_animal_g: Optional[float] = Field(None, ge=0, le=2000)
    custom_protein_plant_g: Optional[float] = Field(None, ge=0, le=2000)
    custom_fat_g: Optional[float] = Field(None, ge=0, le=2000)
    custom_carbs_g: Optional[float] = Field(None, ge=0, le=3000)
    custom_water_ml: Optional[float] = Field(None, ge=0, le=20000)


class NutritionTargets(BaseModel):
    """Суточные нормы КБЖУ, рассчитанные из веса/роста/возраста/активности."""
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    # Разделение нормы белка на животный/растительный.
    protein_animal_g: Optional[float] = None
    protein_plant_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None


class ProfileResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    height_cm: Optional[float] = None
    current_weight_kg: Optional[float] = None  # выводится из последней записи
    # Текущие обхваты тела (из последней записи истории) — для «Личных данных».
    current_waist_cm: Optional[float] = None
    current_chest_cm: Optional[float] = None
    current_hips_cm: Optional[float] = None
    current_shoulders_cm: Optional[float] = None
    sex: Optional[str] = None
    birth_date: Optional[_date] = None
    activity_level: Optional[str] = None
    recent_weights: List[WeightRecordResponse] = Field(default_factory=list)
    bmr: Optional[float] = None                 # базовый обмен веществ
    daily_calorie_target: Optional[float] = None
    # Нормы макронутриентов (по аналогии с нормой калорий)
    protein_target_g: Optional[float] = None
    # Разделение нормы белка на животный/растительный.
    protein_animal_target_g: Optional[float] = None
    protein_plant_target_g: Optional[float] = None
    fat_target_g: Optional[float] = None
    carbs_target_g: Optional[float] = None
    # Суточная норма воды (мл), считается из веса/активности.
    water_target_ml: Optional[float] = None
    # Ручные переопределения норм (NULL = соответствующая норма — авторасчёт).
    # Нужны фронту, чтобы показать, какие значения заданы вручную.
    custom_calorie_target: Optional[float] = None
    custom_protein_g: Optional[float] = None
    custom_protein_animal_g: Optional[float] = None
    custom_protein_plant_g: Optional[float] = None
    custom_fat_g: Optional[float] = None
    custom_carbs_g: Optional[float] = None
    custom_water_ml: Optional[float] = None

    class Config:
        from_attributes = True


# ==================== WATER ====================

class WaterResponse(BaseModel):
    """Состояние воды за конкретный день: сколько выпито и норма."""
    date: _date
    total_ml: float
    goal_ml: Optional[float] = None   # суточная норма (None, если нет веса)
    glass_ml: int                     # объём одного стакана


class WaterUpdate(BaseModel):
    """Изменение количества воды. amount_ml может быть отрицательным
    (убрать стакан); итог не опускается ниже нуля. По умолчанию (None)
    добавляется один стакан."""
    amount_ml: Optional[float] = None
    date: Optional[_date] = None


class TokenData(BaseModel):
    email: Optional[str] = None


class IngredientResponse(BaseModel):
    name: str = ""
    type: str = "unknown"  # protein | carb | fat | vegetable | unknown
    weight_g: float = 0
    # Источник белка ингредиента: animal | plant | mixed | unknown.
    protein_type: str = "unknown"


class NutritionResponse(BaseModel):
    food: str = Field(..., description="Название блюда")
    weight_g: float = Field(..., ge=0.1, le=5000, description="Вес в граммах")
    calories: float = Field(..., ge=0, le=10000, description="Калории")
    protein_g: float = Field(..., ge=0, description="Белки, г")
    # Разделение белка на животный/растительный (по справочнику продуктов).
    protein_animal_g: float = Field(0, ge=0, description="Животный белок, г")
    protein_plant_g: float = Field(0, ge=0, description="Растительный белок, г")
    fat_g: float = Field(..., ge=0, description="Жиры, г")
    carbs_g: float = Field(..., ge=0, description="Углеводы, г")
    confidence: float = Field(..., ge=0, le=1, description="Уверенность модели")
    note: Optional[str] = Field(None, description="Комментарий")
    # Состав блюда от AI: нужен фронту для экрана подтверждения.
    ingredients: List[IngredientResponse] = Field(default_factory=list)

    @validator('weight_g')
    def weight_must_be_reasonable(cls, v):
        if v > 5000:
            raise ValueError('Вес более 5кг маловероятен для одного блюда')
        return v


class TaskCreate(BaseModel):
    pass


class TaskResponse(BaseModel):
    id: str
    status: str
    result: Optional[NutritionResponse] = None
    image_path: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @validator('result', pre=True)
    def parse_result_json(cls, v):
        if v and isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return None
        return v

    @validator('image_path')
    def to_image_url(cls, v):
        # Бэкенд хранит абсолютный путь на диске; наружу отдаём URL,
        # который раздаётся через StaticFiles на /uploads.
        if not v:
            return v
        from pathlib import Path
        return f"/uploads/{Path(v).name}"

    class Config:
        from_attributes = True


class TaskCreatedResponse(BaseModel):
    id: str
    status: str

    class Config:
        from_attributes = True


class AiLimitResponse(BaseModel):
    """Дневной лимит AI-анализа фото: всего / использовано / осталось."""
    limit: int
    used: int
    remaining: int


class MealItemBase(BaseModel):
    food_name: str
    quantity_g: float = Field(..., gt=0)
    calories: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    source: str = "ml"
    confidence: Optional[float] = Field(None, ge=0, le=1)
    note: Optional[str] = None


class MealItemCreate(MealItemBase):
    pass


class MealEntryItemCreate(BaseModel):
    """Одно блюдо в составном приёме («гарнир + основное блюдо»)."""
    food_name: str = Field(..., min_length=1, max_length=200)
    weight_g: float = Field(..., gt=0)
    calories: float = Field(..., ge=0)
    protein_g: float = Field(0, ge=0)
    # Разделение белка блюда (г); сумма ≤ protein_g, остаток — «не определён».
    protein_animal_g: float = Field(0, ge=0)
    protein_plant_g: float = Field(0, ge=0)
    fat_g: float = Field(0, ge=0)
    carbs_g: float = Field(0, ge=0)


class MealEntryItemResponse(MealEntryItemCreate):
    id: int

    # Старые строки (до миграции) хранят NULL в колонках разделения белка —
    # приводим их к 0, чтобы схема с типом float не падала на None.
    @validator("protein_animal_g", "protein_plant_g", pre=True)
    def _coerce_split_none(cls, v):
        return 0 if v is None else v

    class Config:
        from_attributes = True


class MealEntryCreate(BaseModel):
    food_name: str = Field(..., min_length=1, max_length=200)
    calories: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    # Разделение белка (г). Для составного приёма пересчитывается из блюд.
    protein_animal_g: float = Field(0, ge=0)
    protein_plant_g: float = Field(0, ge=0)
    fat_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    weight_g: float = Field(..., gt=0)
    meal_type: str = "snacks"
    # День записи (по умолчанию сегодня) и связь с AI-задачей анализа.
    date: Optional[_date] = None
    task_id: Optional[str] = None
    # Составной приём: несколько блюд. Если список непустой, итоги
    # (calories/weight_g/...) пересчитываются на бэкенде из блюд.
    items: List[MealEntryItemCreate] = Field(default_factory=list)


class MealEntryResponse(BaseModel):
    id: int
    food_name: str
    calories: float
    protein_g: float
    # Разделение белка записи на животный/растительный (г).
    protein_animal_g: float = 0
    protein_plant_g: float = 0
    fat_g: float
    carbs_g: float
    weight_g: float
    meal_type: str
    created_at: datetime
    # Наличие task_id => запись создана из AI-анализа (источник на фронте).
    task_id: Optional[str] = None
    # Фото записи: URL (через StaticFiles /uploads) и источник —
    # 'user' (добавлено вручную) или 'ai' (фото из AI-анализа).
    photo_url: Optional[str] = None
    photo_source: Optional[Literal["user", "ai"]] = None
    # Блюда составного приёма (пусто у простых записей).
    items: List[MealEntryItemResponse] = Field(default_factory=list)

    # Старые строки (до миграции) хранят NULL в разделении белка → приводим к 0.
    @validator("protein_animal_g", "protein_plant_g", pre=True)
    def _coerce_split_none(cls, v):
        return 0 if v is None else v

    class Config:
        from_attributes = True


class DailyLogResponse(BaseModel):
    date: date
    total_calories: float
    total_protein: float
    # Разделение суммарного белка за день на животный/растительный.
    total_protein_animal: float = 0
    total_protein_plant: float = 0
    total_fat: float
    total_carbs: float
    meals: List[MealEntryResponse]
    # Суточные нормы КБЖУ пользователя (для колец/сводки в дневнике).
    targets: Optional[NutritionTargets] = None
    # Вода за этот день (для кольца-инфографики в дневнике).
    water: Optional[WaterResponse] = None


class AnalysisMealRequest(BaseModel):
    task_id: str
    meal_type: str = "snacks"


class MealItem(MealItemBase):
    id: int

    class Config:
        from_attributes = True


class MealBase(BaseModel):
    meal_type: str = "meal"
    notes: Optional[str] = None
    items: List[MealItemCreate] = []


class MealCreate(MealBase):
    pass


class Meal(MealBase):
    id: int
    user_id: int
    date: datetime
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float

    @validator('total_calories', 'total_protein', 'total_fat', 'total_carbs', pre=True)
    def round_totals(cls, v):
        return round(v, 1)

    class Config:
        from_attributes = True


class PhotoResponse(BaseModel):
    id: int
    storage_path: str
    thumbnail_path: Optional[str]
    original_filename: Optional[str]
    file_size: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== НОВЫЕ СХЕМЫ ДЛЯ ОБРАТНОЙ СВЯЗИ ====================

class FeedbackRequest(BaseModel):
    """Запрос на сохранение исправления от пользователя."""
    task_id: str
    correct_food: str = Field(..., min_length=1, max_length=200)
    correct_weight: int = Field(..., gt=0, le=10000)


class FeedbackResponse(BaseModel):
    """Ответ после успешного сохранения фидбека."""
    status: str
    id: int


class FeedbackListItem(BaseModel):
    """Элемент списка фидбеков для админки/обучения."""
    id: int
    task_id: str
    image_path: str
    predicted_result: Optional[Dict[str, Any]]
    corrected_food: str
    corrected_weight: int
    user_id: Optional[int]
    created_at: datetime
    status: str

    class Config:
        from_attributes = True


# ==================== 🔥 PRODUCTS (справочник КБЖУ) ====================

class ProductResponse(BaseModel):
    """Продукт из справочника КБЖУ (нутриенты указаны на 100 г)."""
    id: int
    name: str
    calories: float
    protein: float
    fat: float
    carbs: float
    # Источник белка: animal | plant | mixed. None у старых записей до миграции.
    protein_type: Optional[str] = None

    class Config:
        from_attributes = True


class BarcodeProductResponse(BaseModel):
    """Продукт, найденный по штрих-коду упаковки (Open Food Facts).
    Нутриенты указаны на 100 г — клиент пересчитывает на граммовку."""
    barcode: str
    name: str
    brand: Optional[str] = None
    quantity: Optional[str] = None
    calories_100g: float
    protein_100g: float
    fat_100g: float
    carbs_100g: float
    image_url: Optional[str] = None
    source: str = "openfoodfacts"


class GenerateDatasetResponse(BaseModel):
    """Ответ на запрос генерации датасета."""
    message: str
    count: int
    output_path: str


# ==================== WORKOUTS (вкладка «Тренировки») ====================

WorkoutType = Literal["strength", "cardio", "stretching", "sport", "other"]


class WorkoutItemCreate(BaseModel):
    """Одно упражнение в составной тренировке («жим лёжа 25 мин 150 ккал»)."""
    name: str = Field(..., min_length=1, max_length=200)
    duration_min: float = Field(..., gt=0, le=1440)
    calories_burned: float = Field(0, ge=0, le=10000)


class WorkoutItemResponse(WorkoutItemCreate):
    id: int

    class Config:
        from_attributes = True


class WorkoutCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    workout_type: WorkoutType = "other"
    # Для составной тренировки (items непустой) итоги пересчитываются
    # на бэкенде из упражнений, поэтому здесь допускаем 0.
    duration_min: float = Field(0, ge=0, le=1440)
    calories_burned: float = Field(0, ge=0, le=10000)
    description: Optional[str] = Field(None, max_length=500)
    started_at: Optional[str] = Field(None, max_length=5)  # "HH:MM"
    date: Optional[_date] = None  # по умолчанию — сегодня
    # Конструктор: несколько упражнений в одной тренировке.
    items: List[WorkoutItemCreate] = Field(default_factory=list)

    @validator("started_at")
    def validate_time(cls, v):
        if v in (None, ""):
            return None
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Время должно быть в формате HH:MM")
        return v

    @root_validator(skip_on_failure=True)
    def require_duration_or_items(cls, values):
        if not values.get("items") and not (values.get("duration_min") or 0) > 0:
            raise ValueError("Укажите длительность или добавьте хотя бы одно упражнение")
        return values


class WorkoutResponse(BaseModel):
    id: int
    date: _date
    workout_type: str
    title: str
    description: Optional[str] = None
    started_at: Optional[str] = None
    duration_min: float
    calories_burned: float
    created_at: datetime
    # Упражнения составной тренировки (пусто у простых записей).
    items: List[WorkoutItemResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkoutDaySummary(BaseModel):
    """Сводка активности за день: потрачено ккал, суммарное время, число
    тренировок + скорректированная норма калорий (норма + потраченное)."""
    date: _date
    total_calories_burned: float
    total_duration_min: float
    count: int
    base_calorie_target: Optional[float] = None
    adjusted_calorie_target: Optional[float] = None


class WorkoutWeekDay(BaseModel):
    """День недельной полоски на вкладке «Тренировки»."""
    date: _date
    has_workout: bool


class WorkoutsResponse(BaseModel):
    date: _date
    workouts: List[WorkoutResponse]
    summary: WorkoutDaySummary
    week: List[WorkoutWeekDay]


class ExerciseResponse(BaseModel):
    """Упражнение из справочника. kcal_per_min — примерный расход ккал
    в минуту (человек ~70 кг); kcal_per_30min — удобное число для UI."""
    id: int
    name: str
    category: str
    kcal_per_min: float
    kcal_per_30min: int

    class Config:
        from_attributes = True


# ==================== AI-СОВЕТЧИК ====================

class AdvisorTip(BaseModel):
    """Одна рекомендация: короткий заголовок + текст."""
    title: str
    text: str
    # Цветовая метка для фронта: protein|water|training|carbs|calories|general
    tag: str = "general"


class AdvisorResponse(BaseModel):
    """Ответ AI-советчика: «совет дня» + рекомендации по питанию и тренировкам."""
    headline_title: str
    headline_text: str
    nutrition: List[AdvisorTip] = Field(default_factory=list)
    training: List[AdvisorTip] = Field(default_factory=list)
    # llm — сгенерировано языковой моделью, rules — правила-фолбэк
    generated_by: Literal["llm", "rules"]


class AdvisorAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class AdvisorAskResponse(BaseModel):
    answer: str
    generated_by: Literal["llm", "rules"]