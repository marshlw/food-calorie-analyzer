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
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    # Опционально при регистрации: если заполнены, вес станет первой
    # записью в истории взвешиваний (см. main.register).
    height_cm: Optional[float] = Field(None, gt=0, lt=300)
    weight_kg: Optional[float] = Field(None, gt=0, lt=300)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


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


class WeightRecordResponse(BaseModel):
    id: int
    weight_kg: float
    recorded_on: _date
    note: Optional[str] = None
    source: str

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    height_cm: Optional[float] = Field(None, gt=0, lt=300)
    weight_kg: Optional[float] = Field(None, gt=0, lt=300)
    sex: Optional[Literal["male", "female"]] = None
    birth_date: Optional[_date] = None
    activity_level: Optional[Literal[
        "sedentary", "light", "moderate", "active", "very_active"
    ]] = None
    # UX «Сохранить как новую запись?». По умолчанию True: вес из формы
    # профиля попадает в историю (за сегодня, upsert'ом).
    save_weight_as_record: bool = True


class NutritionTargets(BaseModel):
    """Суточные нормы КБЖУ, рассчитанные из веса/роста/возраста/активности."""
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None


class ProfileResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    height_cm: Optional[float] = None
    current_weight_kg: Optional[float] = None  # выводится из последней записи
    sex: Optional[str] = None
    birth_date: Optional[_date] = None
    activity_level: Optional[str] = None
    recent_weights: List[WeightRecordResponse] = Field(default_factory=list)
    bmr: Optional[float] = None                 # базовый обмен веществ
    daily_calorie_target: Optional[float] = None
    # Нормы макронутриентов (по аналогии с нормой калорий)
    protein_target_g: Optional[float] = None
    fat_target_g: Optional[float] = None
    carbs_target_g: Optional[float] = None
    # Суточная норма воды (мл), считается из веса/активности.
    water_target_ml: Optional[float] = None

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


class NutritionResponse(BaseModel):
    food: str = Field(..., description="Название блюда")
    weight_g: float = Field(..., ge=0.1, le=5000, description="Вес в граммах")
    calories: float = Field(..., ge=0, le=10000, description="Калории")
    protein_g: float = Field(..., ge=0, description="Белки, г")
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


class MealEntryCreate(BaseModel):
    food_name: str
    calories: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    weight_g: float = Field(..., gt=0)
    meal_type: str = "snacks"
    # День записи (по умолчанию сегодня) и связь с AI-задачей анализа.
    date: Optional[_date] = None
    task_id: Optional[str] = None


class MealEntryResponse(BaseModel):
    id: int
    food_name: str
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    weight_g: float
    meal_type: str
    created_at: datetime
    # Наличие task_id => запись создана из AI-анализа (источник на фронте).
    task_id: Optional[str] = None

    class Config:
        from_attributes = True


class DailyLogResponse(BaseModel):
    date: date
    total_calories: float
    total_protein: float
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


class GenerateDatasetResponse(BaseModel):
    """Ответ на запрос генерации датасета."""
    message: str
    count: int
    output_path: str