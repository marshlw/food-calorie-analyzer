import React from 'react'
import { BrowserRouter as Router, Routes, Route, useLocation, Link } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'

// Pages
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { Dashboard } from './pages/Dashboard'
import { DiaryPage } from './pages/DiaryPage'
import { AnalysisHistory } from './pages/AnalysisHistory'
import { TaskDetail } from './pages/TaskDetail'
import { Profile } from './pages/Profile'
import { Workouts } from './pages/Workouts'
import { Advisor } from './pages/Advisor'

// Navigation
import { Home, BookOpen, Dumbbell, User } from 'lucide-react'

// Плавающая pill-навигация из дизайна Rasify:
// Дневник · Приёмы · ✦ AI (по центру) · Тренировки · Профиль
const BottomNavigation: React.FC = () => {
  const location = useLocation()

  // Hide on auth pages
  if (location.pathname === '/login' || location.pathname === '/register') {
    return null
  }

  const isActive = (path: string) => location.pathname === path

  const linkClass = (path: string) =>
    `flex flex-col items-center gap-[3px] w-1/5 transition-colors ${
      isActive(path)
        ? 'text-primary-500 dark:text-primary-400'
        : 'text-faint dark:text-faint-dark hover:text-muted dark:hover:text-muted-dark'
    }`

  const labelClass = (path: string) =>
    `text-[10px] ${isActive(path) ? 'font-semibold' : 'font-medium'}`

  return (
    <nav
      className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 h-16 w-[calc(100%-2rem)] max-w-[26rem]
        bg-white dark:bg-card-dark border border-line dark:border-line-dark rounded-full
        shadow-nav dark:shadow-nav-dark flex items-center justify-around"
    >
      <Link to="/" className={linkClass('/')}>
        <Home className="h-[22px] w-[22px]" strokeWidth={2} />
        <span className={labelClass('/')}>Дневник</span>
      </Link>

      <Link to="/meals" className={linkClass('/meals')}>
        <BookOpen className="h-[22px] w-[22px]" strokeWidth={2} />
        <span className={labelClass('/meals')}>Приёмы</span>
      </Link>

      {/* Центральная кнопка ✦ — AI-советчик */}
      <div className="w-1/5 flex justify-center">
        <Link
          to="/advisor"
          aria-label="AI-советчик"
          className="w-[52px] h-[52px] -mt-[26px] rounded-full bg-gradient-to-br from-primary-500 to-primary-700
            flex items-center justify-center shadow-cta border-4 border-surface dark:border-surface-dark
            text-white text-xl leading-none"
        >
          ✦
        </Link>
      </div>

      <Link to="/workouts" className={linkClass('/workouts')}>
        <Dumbbell className="h-[22px] w-[22px]" strokeWidth={2} />
        <span className={labelClass('/workouts')}>Тренировки</span>
      </Link>

      <Link to="/profile" className={linkClass('/profile')}>
        <User className="h-[22px] w-[22px]" strokeWidth={2} />
        <span className={labelClass('/profile')}>Профиль</span>
      </Link>
    </nav>
  )
}

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Auth Routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/meals"
        element={
          <ProtectedRoute>
            <DiaryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workouts"
        element={
          <ProtectedRoute>
            <Workouts />
          </ProtectedRoute>
        }
      />
      <Route
        path="/advisor"
        element={
          <ProtectedRoute>
            <Advisor />
          </ProtectedRoute>
        }
      />
      <Route
        path="/analysis-history"
        element={
          <ProtectedRoute>
            <AnalysisHistory />
          </ProtectedRoute>
        }
      />
      <Route
        path="/task/:taskId"
        element={
          <ProtectedRoute>
            <TaskDetail />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="bg-surface dark:bg-surface-dark min-h-screen">
          <div className="max-w-md mx-auto">
            <AppRoutes />
            <BottomNavigation />
          </div>
        </div>
      </AuthProvider>
    </Router>
  )
}
