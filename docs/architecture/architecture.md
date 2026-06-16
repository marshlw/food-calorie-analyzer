# AI Healthy - System Architecture

## Overview

AI Healthy is a food recognition and nutrition analysis system that uses multiple AI models to analyze food images and extract nutritional information (calories, proteins, fats, carbohydrates).

**Key Components:**
- FastAPI REST API (Python)
- PostgreSQL database
- Celery task queue with Redis
- Multiple ML models (Gemini, DeepSeek, Ollama)
- Telegram bot for user interaction
- Redis for caching and rate limiting

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                          │
├─────────────────────────────────────────────────────────────┤
│  Telegram Bot (aiogram) │  Web Frontend (HTML/CSS)           │
└────────────┬────────────────────────────────────┬────────────┘
             │                                    │
             └────────────────┬───────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   FastAPI Server   │
                    │   (Port 8000)      │
                    ├────────────────────┤
                    │ • Authentication   │
                    │ • Task Management  │
                    │ • Meal Tracking    │
                    │ • Feedback         │
                    └──────────┬─────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
        ┌───────▼────┐ ┌──────▼────┐ ┌──────▼─────┐
        │ PostgreSQL │ │   Redis   │ │  Celery   │
        │ Database   │ │ (Cache)   │ │  Queue    │
        └────────────┘ │ (Tokens)  │ └──────┬─────┘
                       │ (Throttle)│        │
                       └──────────┘        │
                                      ┌────▼──────────┐
                                      │ ML Pipeline   │
                                      ├───────────────┤
                                      │ 1. Gemini     │
                                      │ 2. DeepSeek   │
                                      │ 3. Ollama     │
                                      │ 4. Fallback   │
                                      └───────────────┘
```

---

## Component Details

### 0. Package Layout

The backend is now exposed through the top-level `app/` package, while the real application implementation lives under `app/app/`.
This allows tests and CLI runners to import `app.main`, `app.auth`, `app.config`, etc. without changing the existing package name.

### 1. FastAPI Application (`app/main.py`)

**Purpose:** Central REST API serving all client requests

**Key Endpoints:**

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/api/v1/register` | ❌ | Register new user |
| POST | `/api/v1/login` | ❌ | Login and get tokens |
| POST | `/api/v1/token` | ❌ | Refresh access token |
| GET | `/api/v1/me` | ✅ | Get current user info |
| POST | `/api/v1/analyze` | ✅ | Submit photo for analysis |
| GET | `/api/v1/task/{id}` | ✅ | Check analysis status/result |
| POST | `/api/v1/meals/from-analysis` | ✅ | Create meal entry from analysis |
| POST | `/api/v1/feedback` | ✅ | Submit feedback on results |

**CORS Configuration:**
- Allowed origins from `settings.ALLOWED_ORIGINS`
- Supports credentials, headers, methods

---

### 2. Authentication (`app/auth.py`)

**JWT Token Structure:**

```python
{
  "sub": "user@example.com",
  "type": "access",           # or "refresh"
  "exp": 1234567890,
  "iat": 1234567800
}
```

**Token Types:**
- **Access Token:** 15 minutes expiry (for API requests)
- **Refresh Token:** 7 days expiry (to get new access token)

**Key Functions:**
- `create_access_token()` - Generate access JWT
- `create_refresh_token()` - Generate refresh JWT
- `verify_refresh_token()` - Validate refresh token
- `get_current_user()` - FastAPI dependency for protected routes
- `verify_password()` - bcrypt verification
- `get_password_hash()` - bcrypt hashing

---

### 3. ML Service (`app/ml_service.py`)

**Architecture:** Model fallback chain with rate limiting and caching

#### Model Chain:
```
┌─────────────┐      ┌──────────────┐     ┌────────────┐     ┌──────────┐
│   Gemini    │─────►│   DeepSeek   │────►│   Ollama   │────►│ Fallback │
│ (Free tier) │      │   Vision     │     │  (Local)   │     │  (Safe)  │
└─────────────┘      └──────────────┘     └────────────┘     └──────────┘
```

**Key Features:**
- **Retries:** Each model retried up to 2 times on failure
- **Rate Limiting:** Thread-safe rate limiting (1.2s for Gemini/DeepSeek, 0.5s for Ollama)
- **Caching:** 24h cache by image hash (using Redis)
- **Validation:** Strict response validation for JSON structure, value ranges
- **Normalization:** Ingredient weights distributed evenly

#### Response Structure:
```json
{
  "food": "pasta carbonara",
  "weight_g": 300,
  "confidence": 0.92,
  "calories": 450,
  "protein_g": 18,
  "fat_g": 22,
  "carbs_g": 35,
  "ingredients": [
    {"name": "pasta", "type": "carb", "weight_g": 150},
    {"name": "bacon", "type": "protein", "weight_g": 75}
  ],
  "source": "gemini",           # Which model succeeded
  "models_tried": ["gemini"],   # Chain traversal log
  "processing_time_sec": 2.34   # Total time
}
```

**Important:** Fallback (when all models fail) returns with `source: "fallback"` as a **SUCCESS** result, not an error.

---

### 4. Task Queue (`app/tasks.py`)

**Purpose:** Asynchronous image analysis using Celery

**Task Lifecycle:**
```
PENDING → PROCESSING → SUCCESS
                    ↓
                   FAILURE (only on unhandled exceptions)
```

**Key Rules:**
- Status set to `PROCESSING` when task starts
- Status set to `SUCCESS` for any valid result (including fallback)
- Status set to `FAILURE` only for:
  - Unhandled exceptions in task
  - Corrupted/invalid image file
  - Critical infrastructure errors
- Image file deleted after analysis completes
- Result stored as JSON in database

---

### 5. Database Schema (`app/models.py`)

**Core Models:**

```python
class User:
    id: UUID
    email: str (unique)
    password_hash: str
    created_at: datetime

class Task:
    id: UUID
    user_id: UUID (FK → User)
    image_path: str
    status: TaskStatus (pending|processing|success|failure)
    result_json: dict
    error: str | None
    image_hash: str (MD5)
    created_at: datetime
    updated_at: datetime

class Meal:
    id: UUID
    user_id: UUID (FK → User)
    name: str
    weight_g: int
    date_logged: date
    
class Product:
    name: str (unique)
    calories: float
    protein: float
    fat: float
    carbs: float
```

---

### 6. Telegram Bot (`app/telegram_bot.py`)

**Purpose:** User interface for image submission and feedback

**Key Features:**
- Auto-registration with email format: `{user_id}@tg.local`
- Token stored in memory (lost on restart)
- Poll mechanism: checks task status every 1-5 seconds
- Accepts pending/processing/started as valid waiting states
- Status polling timeout: 40 attempts (~100 seconds)

**Main Commands:**
- `/start` - Show main menu
- `📸 Send food photo` - Start analysis
- `🔐 Authorize` - Login flow
- `📝 Register` - Registration flow
- `📊 Status` - Check auth status
- Feedback: `✅ Correct` / `❌ Incorrect`

---

### 7. API Client (`api_client.py`)

**Purpose:** Unified HTTP client with token refresh logic

**Key Methods:**
```python
client = APIClient("http://localhost:8000")
success, error = await client.register(email, password)
success, error = await client.login(email, password)
user, error = await client.get_current_user()
task, error = await client.upload_photo(file_bytes)
task, error = await client.get_task_status(task_id)
success, error = await client.submit_feedback(task_id, food, weight)
```

**Features:**
- Automatic token refresh on 401
- Proper async context management (no closed responses)
- Error messages in responses

---

## Data Flow: Image Analysis

### User submits photo:

1. **Telegram Bot** → Downloads photo → Calls `/api/v1/analyze`
2. **FastAPI** → Creates Task (status: PENDING) → Queues Celery task
3. **Celery** → Sets status: PROCESSING → Calls `ml_service.analyze_image_sync()`
4. **ML Service**:
   - Check Redis cache by image hash
   - If cached: return with source="cache"
   - Try Gemini → if fails, try DeepSeek → if fails, try Ollama
   - If all fail: return DEFAULT_FALLBACK with source="fallback"
   - Cache result for 24h
5. **Celery** → Sets status: SUCCESS, stores result_json
6. **Telegram Bot** → Polls `/api/v1/task/{id}` every 1-5 sec
7. **User** → Receives formatted result with feedback buttons

---

## Error Handling

### Model Failures:

| Scenario | Behavior | Status |
|----------|----------|--------|
| Model returns invalid JSON | Try next model | PENDING |
| Model quota exceeded | Skip, try next | PENDING |
| All models fail | Return fallback | **SUCCESS** ✅ |
| Image corrupted | Log error | FAILURE |
| Celery exception | Retry up to 3x | FAILURE |

### Authentication:

| Scenario | Response |
|----------|----------|
| Missing token | 401 Unauthorized |
| Invalid token | 401 Unauthorized |
| Expired access token | Refresh auto-triggered |
| Expired refresh token | 401 Unauthorized |
| Invalid credentials | 401 Unauthorized |

---

## Configuration (`app/config.py`)

**Key Settings:**

```python
# Database
DATABASE_URL = "postgresql://user:pass@db/ai_healthy"
REDIS_URL = "redis://redis:6379/0"

# ML Models
GEMINI_API_KEY = "..."
DEEPSEEK_API_KEY = "..."
OLLAMA_HOST = "http://ollama:11434"

# Timeouts & Limits
MODEL_RETRY_ATTEMPTS = 2
MODEL_BACKOFF_FACTOR = 2
MAX_IMAGE_SIZE = 1600  # pixels
IMAGE_QUALITY = 90     # JPEG quality 1-100

# Caching
CACHE_TTL = 86400      # 24 hours
CACHE_PREFIX = "ai_healthy"

# Auth
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = "..."
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# API
ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
```

---

## Performance Considerations

### Caching:
- Image hash (MD5) used as cache key
- 24-hour TTL reduces API calls
- Cache key includes PROMPT_VERSION for invalidation on prompt changes

### Rate Limiting:
- Gemini/DeepSeek: 1.2 seconds between calls (thread-safe)
- Ollama: 0.5 seconds between calls
- Prevents API quota violations

### Database:
- Synchronous SQLAlchemy engine (not asyncpg)
- Connection pooling enabled
- Indexes on user_id, task status, created_at

---

## Testing

**Test Modules:**

1. **test_ml_service.py** - Model fallback chain
   - Gemini success
   - Gemini fail → DeepSeek success
   - All models fail → Fallback
   - Invalid JSON → Next model
   - Result metadata

2. **test_api.py** - REST endpoints
   - Registration
   - Login & token refresh
   - Token refresh with new JWT
   - Authenticated requests
   - Endpoint structure validation

---

## Deployment

### Docker Compose Stack:

```yaml
services:
  api:
    image: ai-healthy-api
    ports: ["8000:8000"]
    depends_on: [db, redis, celery]
    
  db:
    image: postgres:15
    volumes: [pgdata:/var/lib/postgresql/data]
    
  redis:
    image: redis:7
    
  celery:
    image: ai-healthy-api
    command: celery -A app.celery_app worker
    depends_on: [db, redis]
    
  ollama:
    image: ollama/ollama
    volumes: [ollama_data:/root/.ollama]
```

---

## Future Improvements

1. **Token Storage:** Use Redis instead of memory (survive bot restarts)
2. **Rate Limiting:** Per-user API rate limits
3. **Analytics:** Track model accuracy, model usage patterns
4. **Batch Processing:** Analyze multiple photos in one request
5. **User Models:** Train custom models on user feedback
6. **Mobile App:** Native iOS/Android instead of Telegram-only
