import os
from pathlib import Path

# Ensure tests use a local SQLite database if no external database is configured.
test_db_path = Path(__file__).resolve().parent / "test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{test_db_path}")

# Rate limiting (брутфорс/дневной лимит AI) отключаем в тестах: TestClient ходит
# с одного "IP", и повторные register/login в разных тестах упирались бы в 429.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

# Приложение падает при запуске с плейсхолдером в SECRET_KEY (fail-fast в
# config.py) — для тестов задаём фиксированный ключ без «плейсхолдерных» слов.
os.environ.setdefault("SECRET_KEY", "unit-test-only-jwt-signing-key-af8k3n2p9q7r5s1t4u6v8w0x")

from app.database import Base, configure_database, engine
import app.models  # register ORM models on Base

if test_db_path.exists():
    test_db_path.unlink()

configure_database()
Base.metadata.create_all(bind=engine)
