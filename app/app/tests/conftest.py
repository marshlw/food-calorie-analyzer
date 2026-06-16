import os
from pathlib import Path

# Ensure tests use a local SQLite database if no external database is configured.
test_db_path = Path(__file__).resolve().parent / "test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{test_db_path}")

from app.database import Base, configure_database, engine
import app.models  # register ORM models on Base

if test_db_path.exists():
    test_db_path.unlink()

configure_database()
Base.metadata.create_all(bind=engine)
