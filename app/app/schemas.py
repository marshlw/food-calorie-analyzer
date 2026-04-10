# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class Token(BaseModel):
    access_token: str
    token_type: str


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenData(BaseModel):
    email: Optional[str] = None


class NutritionResponse(BaseModel):
    food: str = Field(..., description="Название блюда")
    weight_g: int = Field(..., ge=1, le=5000, description="Вес в граммах")
    calories: int = Field(..., ge=0, le=10000, description="Калории")
    protein_g: float = Field(..., ge=0, description="Белки, г")
    fat_g: float = Field(..., ge=0, description="Жиры, г")
    carbs_g: float = Field(..., ge=0, description="Углеводы, г")
    confidence: float = Field(..., ge=0, le=1, description="Уверенность модели")
    note: Optional[str] = Field(None, description="Комментарий")

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
    user_id: Optional[int] = None


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