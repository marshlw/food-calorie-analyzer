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

    # ---- Ручные нормы (для атлетов и особых рационов) ----
    # NULL = авторасчёт из веса/роста/возраста/активности; значение —
    # переопределяет расчёт везде (дневник, вода, советчик, тренировки).
    custom_calorie_target = Column(Float, nullable=True)
    custom_protein_g = Column(Float, nullable=True)
    # Ручное разделение нормы белка на животный/растительный (NULL = авторасчёт
    # из общей нормы белка по доле PROTEIN_ANIMAL_TARGET_SHARE). Сумма животного
    # и растительного не обязана точно равняться общей норме — это независимые
    # цели, которые атлет может выставить под свой рацион.
    custom_protein_animal_g = Column(Float, nullable=True)
    custom_protein_plant_g = Column(Float, nullable=True)
    custom_fat_g = Column(Float, nullable=True)
    custom_carbs_g = Column(Float, nullable=True)
    custom_water_ml = Column(Float, nullable=True)

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
    # ---- Обхваты тела (см), всё опционально ----
    # Хранятся в той же строке, что и вес: один замер на (пользователь + дата).
    # Любой из обхватов можно не заполнять — тогда он остаётся пустым и не
    # попадает в график соответствующей метрики.
    waist_cm = Column(Float, nullable=True)      # талия
    chest_cm = Column(Float, nullable=True)      # грудь
    hips_cm = Column(Float, nullable=True)       # бёдра
    shoulders_cm = Column(Float, nullable=True)  # плечи
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
    # КБЖУ/вес записи. Если запись составная (items), это СУММЫ по блюдам —
    # так вся существующая аналитика (calculate_daily_totals и т.п.) работает
    # без изменений.
    calories = Column(Float, nullable=False)
    protein_g = Column(Float, nullable=False)
    # Разделение белка записи на животный/растительный (г). Их сумма ≤ protein_g;
    # разница (если есть) — «источник не определён» (например, ручная запись без
    # указания типа или продукт вне справочника). Для составных приёмов это
    # суммы по блюдам (см. crud._meal_totals_from_items).
    protein_animal_g = Column(Float, nullable=False, default=0)
    protein_plant_g = Column(Float, nullable=False, default=0)
    fat_g = Column(Float, nullable=False)
    carbs_g = Column(Float, nullable=False)
    weight_g = Column(Float, nullable=False)
    meal_type = Column(String, default="snacks")  # breakfast, lunch, dinner, snacks
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    # Фото, добавленное пользователем вручную (абсолютный путь на диске).
    # Для записей из AI-анализа фото берётся из task.image_path.
    photo_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    daily_log = relationship("DailyLog", back_populates="entries")
    task = relationship("Task")
    items = relationship(
        "MealEntryItem",
        back_populates="meal_entry",
        cascade="all, delete-orphan",
        order_by="MealEntryItem.id",
    )

    @property
    def photo_url(self):
        """URL фото записи для фронта (раздаётся через StaticFiles /uploads).
        Приоритет: своё фото пользователя, затем фото AI-анализа."""
        from pathlib import Path
        if self.photo_path:
            return f"/uploads/{Path(self.photo_path).name}"
        if self.task_id and self.task and self.task.image_path:
            return f"/uploads/{Path(self.task.image_path).name}"
        return None

    @property
    def photo_source(self):
        """Откуда фото: 'user' — загружено вручную, 'ai' — из AI-анализа."""
        if self.photo_path:
            return "user"
        if self.task_id and self.task and self.task.image_path:
            return "ai"
        return None


class MealEntryItem(Base):
    """Блюдо внутри составного приёма пищи («гарнир + основное блюдо»).
    Итоги по приёму хранятся на MealEntry (суммируются в crud)."""

    __tablename__ = "meal_entry_items"

    id = Column(Integer, primary_key=True, index=True)
    meal_entry_id = Column(Integer, ForeignKey("meal_entries.id"), nullable=False, index=True)

    food_name = Column(String, nullable=False)
    weight_g = Column(Float, nullable=False, default=0)
    calories = Column(Float, nullable=False, default=0)
    protein_g = Column(Float, nullable=False, default=0)
    # Разделение белка блюда (г); сумма ≤ protein_g, остаток — «не определён».
    protein_animal_g = Column(Float, nullable=False, default=0)
    protein_plant_g = Column(Float, nullable=False, default=0)
    fat_g = Column(Float, nullable=False, default=0)
    carbs_g = Column(Float, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meal_entry = relationship("MealEntry", back_populates="items")


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
    items = relationship(
        "WorkoutItem",
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="WorkoutItem.id",
    )


class WorkoutItem(Base):
    """Упражнение внутри составной тренировки («жим лёжа 25 мин + становая
    25 мин»). Итоги по тренировке (duration_min, calories_burned) хранятся
    на Workout и пересчитываются в crud."""

    __tablename__ = "workout_items"

    id = Column(Integer, primary_key=True, index=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    duration_min = Column(Float, nullable=False, default=0)
    calories_burned = Column(Float, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workout = relationship("Workout", back_populates="items")


# ==================== EXERCISES (справочник упражнений) ====================

class Exercise(Base):
    """Справочник упражнений с примерным расходом калорий.
    kcal_per_min — ккал в минуту для человека ~70 кг (оценка по MET).
    Используется формой записи тренировки для авторасчёта калорий."""

    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    # Категория соответствует типам тренировок: strength|cardio|stretching|sport|other
    category = Column(String, nullable=False, default="other")
    kcal_per_min = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def kcal_per_30min(self) -> int:
        # Удобная цифра для UI: «Жим лёжа · 30 мин ≈ 180 ккал»
        return round((self.kcal_per_min or 0) * 30)


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
    # Разделение суммарного белка приёма на животный/растительный.
    total_protein_animal = Column(Float, default=0)
    total_protein_plant = Column(Float, default=0)
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
    # Разделение белка позиции на животный/растительный (г).
    protein_animal_g = Column(Float, nullable=False, default=0)
    protein_plant_g = Column(Float, nullable=False, default=0)
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

    # Источник белка продукта: "animal" (животный), "plant" (растительный)
    # или "mixed" (смешанный — часть животного, часть растительного, напр.
    # пельмени/пицца). Проставляется автоматически классификатором
    # protein_source.classify по названию при засеве базы.
    protein_type = Column(String, nullable=True, default="mixed")

    created_at = Column(DateTime(timezone=True), server_default=func.now())