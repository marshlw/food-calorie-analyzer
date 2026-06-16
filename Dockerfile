# Stage 1: Build frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Stage 2: Build backend with frontend
FROM python:3.10-slim-bullseye

WORKDIR /app

# Установка системных зависимостей (для python-magic, Pillow, etc.)
# С retry логикой для надежности при проблемах с сетью
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
    libmagic1 \
    gcc \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование backend
COPY . .

# Копирование собранного frontend из stage 1
COPY --from=frontend-builder /frontend/dist ./app/static/frontend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]