#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Инициализация БД при ПЕРВОМ старте пустого тома postgres
# (docker-entrypoint-initdb.d запускает это только на чистом data-каталоге).
#
# Пароль прикладного пользователя fooduser больше НЕ хардкодится: он берётся
# из переменной окружения APP_DB_PASSWORD (секрет из .env / docker secret).
# Скрипт идемпотентен по роли (создаём, только если нет) и всегда выставляет
# актуальный пароль через ALTER ROLE.
#
# ВАЖНО: на УЖЕ инициализированной БД этот скрипт повторно не выполняется.
# Чтобы сменить пароль на живой базе — см. раздел «Ротация» в SECURITY_DB.md.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set (пароль прикладного пользователя fooduser)}"

psql -v ON_ERROR_STOP=1 -v app_pw="$APP_DB_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
-- =========================
-- EXTENSIONS
-- =========================
-- pg_trgm нужен для GIN-индексов автодополнения (поиск по products.name и
-- exercises.name идёт как ILIKE '%слово%', обычный B-tree тут бесполезен).
-- Ставим здесь, пока мы суперпользователь: прикладной fooduser может не
-- иметь права на CREATE EXTENSION. Приложение (database._ensure_trgm_indexes)
-- повторит попытку на старте, если расширения вдруг не окажется.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =========================
-- USER (пароль подставляется psql-переменной :app_pw, безопасно квотируется)
-- =========================
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fooduser') THEN
      CREATE ROLE fooduser WITH LOGIN;
   END IF;
END
$$;

ALTER ROLE fooduser WITH LOGIN PASSWORD :'app_pw';

-- =========================
-- DATABASE ACCESS
-- =========================
GRANT CONNECT ON DATABASE fooddb TO fooduser;

-- =========================
-- SCHEMA
-- =========================
GRANT USAGE, CREATE ON SCHEMA public TO fooduser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL ON TABLES TO fooduser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL ON SEQUENCES TO fooduser;

-- =========================
-- TABLE
-- =========================
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    calories DOUBLE PRECISION NOT NULL,
    protein DOUBLE PRECISION NOT NULL,
    fat DOUBLE PRECISION NOT NULL,
    carbs DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE products OWNER TO fooduser;
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);

-- =========================
-- DATA (UPSERT)
-- =========================
INSERT INTO products (name, calories, protein, fat, carbs) VALUES
('курица', 165, 31, 3.6, 0),
('куриная грудка', 165, 31, 3.6, 0),
('индейка', 135, 29, 1, 0),
('говядина', 250, 26, 15, 0),
('свинина', 290, 25, 21, 0),
('бекон', 541, 37, 42, 1.4),
('колбаса', 301, 12, 27, 2),
('лосось', 208, 20, 13, 0),
('тунец', 132, 28, 1, 0),
('креветки', 99, 24, 0.3, 0.2),
('треска', 82, 18, 0.7, 0),
('сельдь', 158, 18, 9, 0),
('рис', 130, 2.7, 0.3, 28),
('бурый рис', 123, 2.6, 1, 25),
('гречка', 110, 4, 1.3, 23),
('овсянка', 68, 2.4, 1.4, 12),
('пшено', 119, 3.5, 1, 23),
('бургер', 295, 17, 14, 30),
('пицца', 266, 11, 10, 33),
('шаурма', 250, 10, 12, 25),
('суши', 130, 6, 1, 28)
ON CONFLICT (name) DO UPDATE SET
    calories = EXCLUDED.calories,
    protein  = EXCLUDED.protein,
    fat      = EXCLUDED.fat,
    carbs    = EXCLUDED.carbs;
EOSQL

echo "init.sh: schema/role/seed applied for fooduser"
