from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base
import logging
logger = logging.getLogger(__name__)

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meals = relationship("Meal", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user")


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())
    meal_type = Column(String, default="meal")  # breakfast, lunch, dinner, snack
    notes = Column(Text, nullable=True)

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
    source = Column(String, default="ml")  # ml, manual, corrected
    confidence = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meal = relationship("Meal", back_populates="items")
    photo = relationship("Photo", uselist=False, back_populates="meal_item", cascade="all, delete-orphan")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    meal_item_id = Column(Integer, ForeignKey("meal_items.id"), unique=True, nullable=False)
    storage_path = Column(String, nullable=False)  # relative path
    thumbnail_path = Column(String, nullable=True)
    file_hash = Column(String, index=True, nullable=False)  # SHA256 of processed image
    original_filename = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meal_item = relationship("MealItem", back_populates="photo")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    result_json = Column(Text, nullable=True)  # JSON string of NutritionResponse
    error = Column(Text, nullable=True)
    image_hash = Column(String, index=True, nullable=True)  # for cache lookup
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="tasks")