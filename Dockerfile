FROM python:3.10-slim

WORKDIR /app

# Установка системных зависимостей (для python-magic, Pillow, etc.)
RUN apt-get update && apt-get install -y \
    libmagic1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]