# AI Healthy Frontend

Мобильное веб-приложение для учета питания с анализом блюд по фото.

## Технологический стек

- **React 18** - UI фреймворк
- **TypeScript** - Типизация
- **Vite** - Сборщик
- **Tailwind CSS** - Стили
- **React Router v6** - Навигация
- **Axios** - HTTP запросы
- **Lucide React** - Иконки
- **PWA** - Поддержка установки на рабочий стол

## Требования

- Node.js 16+
- npm или yarn

## Установка и запуск

### 1. Установка зависимостей

```bash
npm install
```

### 2. Конфигурация

Создайте файл `.env.local`:

```bash
cp .env.example .env.local
```

Отредактируйте `.env.local` для вашего окружения:

```env
VITE_API_URL=http://localhost:8000
```

### 3. Разработка

```bash
npm run dev
```

Откройте [http://localhost:5173](http://localhost:5173)

### 4. Сборка для production

```bash
npm run build
```

Файлы будут в папке `dist/`.

## Структура проекта

> Ниже — фактическая структура `src/` (68 файлов на момент последнего обновления этого файла),
> заметно шире, чем в первой версии фронтенда — добавились тренировки, AI-советчик, вода,
> штрих-коды и т.д.

```
src/
├── api/                    # API клиент и запросы (по одному файлу на группу эндпоинтов)
│   ├── axios.ts           # Конфигурация axios: base URL, JWT-интерцепторы, refresh-on-401
│   ├── auth.ts             # Авторизация
│   ├── profile.ts          # Профиль, вес, ручные нормы
│   ├── meals.ts            # Приёмы пищи (дневник)
│   ├── tasks.ts             # Анализы фото
│   ├── water.ts             # Вода
│   ├── workouts.ts          # Тренировки
│   ├── exercises.ts         # Справочник упражнений
│   ├── products.ts          # Поиск продуктов
│   ├── barcode.ts           # Штрих-коды
│   └── advisor.ts           # AI-советчик
├── components/              # Переиспользуемые компоненты (30 файлов), в т.ч. подпапка profile/:
│   │                         # ChangePasswordForm, WeightChart, TargetsForm, ProfileForm,
│   │                         # WeightHistoryList, AddWeightModal
│   └── ProtectedRoute.tsx, LoadingSpinner.tsx, ErrorAlert.tsx, MealCard.tsx, MealForm.tsx, ...
├── context/                 # Context API (без внешнего state-менеджера — Redux/Zustand не используются)
│   ├── AuthContext.tsx      # Авторизация
│   └── DiaryContext.tsx     # Состояние дневника питания
├── hooks/                   # Пользовательские hooks
│   ├── useAuth.ts, useLocalStorage.ts, useApi.ts, useAiLimit.ts, useFoodAnalysis.ts
├── pages/                   # Страницы приложения (11)
│   ├── Login.tsx, Register.tsx, Dashboard.tsx, MealDiary.tsx, DiaryPage.tsx,
│   │   AnalysisHistory.tsx, TaskDetail.tsx, Profile.tsx, Workouts.tsx, Advisor.tsx
├── utils/                   # errors, dates, mealTypes, text, protein
├── types/                   # TypeScript типы (index.ts)
├── styles/                  # globals.css
├── App.tsx                 # Главное приложение
└── main.tsx                 # Точка входа

public/
├── manifest.json           # PWA манифест
└── sw.js                    # Service Worker (руками написанный, без vite-plugin-pwa)
```

## Функциональность

### 🔐 Авторизация

- Регистрация нового аккаунта
- Логин с email и паролем
- Автоматическое обновление токена
- Сохранение сессии в localStorage
- Автоматический выход при 401

### 📊 Главный дашборд

- Ежедневная сводка (калории, белки, жиры, углеводы)
- Добавление приема пищи вручную
- Анализ блюд по фото с камеры/галереи
- Опрос статуса анализа в реальном времени
- Быстрое добавление результатов анализа в дневник

### 📝 Пищевой дневник

- Просмотр приемов пищи за день
- Выбор даты с date picker
- Редактирование приемов пищи
- Удаление приемов пищи
- Дневная сводка питательных веществ

### 📸 История анализов

- Список всех анализов фото
- Статус каждого анализа
- Предпросмотр результатов
- Детальный просмотр каждого анализа
- Отправка исправлений для улучшения ML модели

### 👤 Профиль

- Просмотр данных пользователя
- Переключение темы (светлая/тёмная)
- Кнопка выхода

## API Интеграция

Все запросы автоматически включают токен авторизации в заголовок `Authorization: Bearer {token}`.

При получении 401 ответа приложение автоматически:
1. Отправляет refresh token на `/api/v1/token`
2. Получает новый access token
3. Повторяет исходный запрос

### Основные endpoints

Полный и актуальный список — [сводка эндпоинтов](../api/api-endpoints-summary.md). Кратко, по
разделам фронтенда: авторизация (`register`/`login`/`token`/`me`/`change-password`), профиль и
вес (`profile`, `profile/weight*`), анализ фото (`analyze`, `analyze/limit`, `task/{id}`,
`tasks`), дневник (`meals*`, `daily-log`), вода (`water`), тренировки (`workouts*`,
`exercises`), продукты и штрих-коды (`products`, `barcode/*`), AI-советчик (`advisor`,
`advisor/ask`), обратная связь (`feedback`).

## PWA Поддержка

Приложение поддерживает установку на рабочий стол:

- **Web App Manifest** - Метаинформация приложения
- **Service Worker** - Кэширование и работа offline
- **Responsive Design** - Адаптация под разные размеры экранов
- **Touch-friendly UI** - Оптимизированный интерфейс для сенсорных устройств

Установка:
- iOS: Нажмите "Поделиться" → "На экран Домой"
- Android: Меню → "Установить приложение"
- Desktop: Нажмите на иконку установки в адресной строке браузера

## Мобильная оптимизация

- **Максимальная ширина 500px** для удобства
- **Safe Area** поддержка для устройств с notch
- **Touch-friendly** размеры кнопок (минимум 48x48px)
- **Адаптивная верстка** для всех размеров экранов
- **Темная тема** для комфорта в темноте

## Типы данных

### User
```typescript
{
  id: string
  email: string
  full_name?: string
  created_at: string
}
```

### MealEntry
```typescript
{
  id: number
  food_name: string
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
  weight_g: number
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  created_at: string
}
```

### Task
```typescript
{
  id: string
  user_id: string
  image_path: string
  status: 'pending' | 'processing' | 'success' | 'failure'
  result_json?: string
  error?: string
  created_at: string
}
```

### DailyLog
```typescript
{
  date: string
  total_calories: number
  total_protein: number
  total_fat: number
  total_carbs: number
  meals: MealEntry[]
}
```

## Разработка

### Type Checking

```bash
npm run type-check
```

### Lint

```bash
npm run lint
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8000` | URL API сервера |

## Хроме и современные браузеры

Приложение требует следующие возможности браузера:
- ES2020 JavaScript
- Fetch API
- LocalStorage
- Service Workers
- Web App Manifest

## Лицензия

MIT
