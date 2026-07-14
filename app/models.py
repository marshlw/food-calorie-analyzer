from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, JSON, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base
import logging

logger = logging.getLogger(__name__)


# ==================== ENUMS ====================

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"


class FeedbackStatus(str, enum.Enum):
    PENDING = "pending"
    USED = "used"


# ==================== USERS ====================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ---- Профиль (всё опционально, не блокирует регистрацию) ----
    # Рост меняется редко -> храним снимок прямо на пользователе.
    # Текущий вес НЕ дублируем здесь: источник правды -- последняя
    # запись в weight_records (см. crud.get_latest_weight), чтобы
    # два источника не разъезжались.
    height_cm = Column(Float, nullable=True)
    # Задел под расчёт BMR / нормы калорий (формула Миффлина-Сан-Жеора).
    sex = Column(String, nullable=True)             # "male" | "female"
    birth_date = Column(Date, nullable=True)
    activity_level = Column(String, nullable=True)  # sedentary|light|moderate|active|very_active

    meals = relationship("Meal", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user")
    daily_logs = relationship("DailyLog", back_populates="user", cascade="all, delete-orphan")
    weight_records = relationship(
        "WeightRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="WeightRecord.recorded_on",
    )
    water_logs = relationship(
        "WaterLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    workouts = relationship(
        "Workout",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# ==================== WEIGHT HISTORY ====================

class WeightRecord(Base):
    """История взвешиваний. Одна строка на (пользователь + дата):
    повторное сохранение веса за тот же день обновляет запись, а не
    плодит дубли (см. crud.upsert_weight_record). Это и есть защита
    от случайных дублей из UX «сохранить как новую запись?»."""

    __tablename__ = "weight_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    weight_kg = Column(Float, nullable=False)
    recorded_on = Column(Date, nullable=False, server_default=func.current_date())
    note = Column(String, nullable=True)
    source = Column(String, default="manual")  # manual | registration | profile_edit
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="weight_records")

    __table_args__ = (
        UniqueConstraint("user_id", "recorded_on", name="uq_weight_user_date"),
    )


# ==================== DAILY LOG ====================

class DailyLog(Base):
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False, index=True, server_default=func.current_date())

    user = relationship("User", back_populates="daily_logs")
    entries = relationship("MealEntry", back_populates="daily_log", cascade="all, delete-orphan")


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id = Column(Integer, primary_key=True, index=True)
    daily_log_id = Column(Integer, ForeignKey("daily_logs.id"), nullable=False)
    food_name = Column(String, nullable=False)
    calories = Column(Float, nullable=False)
    protein_g = Column(Float, nullable=False)
    fat_g = Column(Float, nullable=False)
    carbs_g = Column(Float, nullable=False)
    weight_g = Column(Float, nullable=False)
    meal_type = Column(String, default="snacks")  # breakfast, lunch, dinner, snacks
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    daily_log = relationship("DailyLog", back_populates="entries")
    task = relationship("Task")


# ==================== WATER LOG ====================

class WaterLog(Base):
    """Выпитая вода за день. Одна строка на (пользователь + дата): учёт
    ведётся в миллилитрах, фронт добавляет/убирает по одному стакану
    (см. utils.GLASS_ML). По аналогии с weight_records — upsert по дате,
    без дублей."""

    __tablename__ = "water_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True, server_default=func.current_date())
    total_ml = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="water_logs")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_water_user_date"),
    )


# ==================== WORKOUTS ====================

class Workout(Base):
    """Дневник тренировок (вкладка «Тренировки»). Одна строка = одна
    тренировка: тип (силовая/кардио/...), длительность и потраченные
    калории. Потраченные калории учитываются советчиком и в балансе дня."""

    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True, server_default=func.current_date())

    workout_type = Column(String, default="other")  # strength|cardio|stretching|sport|other
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    started_at = Column(String, nullable=True)      # "HH:MM" (необязательно)
    duration_min = Column(Float, nullable=False, default=0)
    calories_burned = Column(Float, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="workouts")


# ==================== MEALS ====================

class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())
    meal_type = Column(String, default="meal")
    notes = Column(Text, nullable=True)

    # 👉 добавили агрегаты (очень важно для аналитики)
    total_calories = Column(Float, default=0)
    total_protein = Column(Float, default=0)
    total_fat = Column(Float, default=0)
    total_carbs = Column(Float, default=0)

    user = relationship("User", back_populates="meals")
    items = relationship("MealItem", back_populates="meal", cascade="all, delete-orphan")


class MealItem(Base):
    __tablename__ = "meal_items"

    id = Column(Integer, primary_key=True, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False)

    food_name = Column(String, nullable=False)
    quantity_g = Column(Float, nullable=False)

    calories = Column(Float, nullable=False)
    protein_g = Column(Float, nullable=False)
    fat_g = Column(Float, nullable=False)
    carbs_g = Column(Float, nullable=False)

    source = Column(String, default="ml")  # ml / manual / corrected
    confidence = Column(Float, nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meal = relationship("Meal", back_populates="items")
    photo = relationship("Photo", uselist=False, back_populates="meal_item", cascade="all, delete-orphan")


# ==================== PHOTOS ====================

class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    meal_item_id = Column(Integer, ForeignKey("meal_items.id"), unique=True, nullable=False)

    storage_path = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)

    file_hash = Column(String, index=True, nullable=False)
    original_filename = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meal_item = relationship("MealItem", back_populates="photo")


# ==================== TASKS ====================

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_path = Column(String, nullable=False)

    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)

    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    image_hash = Column(String, index=True, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="tasks")

    @property
    def result(self):
        # TaskResponse.result читает этот атрибут; pre-валидатор схемы
        # распарсит JSON-строку. Без этого свойства result всегда был None.
        return self.result_json


# ==================== FEEDBACK ====================

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(String, ForeignKey("tasks.id"), index=True, nullable=False)
    image_path = Column(String, nullable=False)

    predicted_result = Column(JSON, nullable=True)

    corrected_food = Column(String, nullable=False)
    corrected_weight = Column(Integer, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    status = Column(SQLEnum(FeedbackStatus), default=FeedbackStatus.PENDING)


# ==================== 🔥 KBJU PRODUCTS ====================

class Product(Base):
    """
    Главная таблица нутриентов.
    Используется ML сервисом вместо хардкода.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    # название продукта (уникальное!)
    name = Column(String, unique=True, index=True, nullable=False)

    # нутриенты на 100 г
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())