import React from 'react'
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom'
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

// Navigation
import { Home, BookOpen, History, User } from 'lucide-react'

const BottomNavigation: React.FC = () => {
  const location = useLocation()

  // Hide on auth pages
  if (location.pathname === '/login' || location.pathname === '/register') {
    return null
  }

  const isActive = (path: string) => {
    return location.pathname === path
  }

  const navItems = [
    { path: '/', icon: Home, label: 'Дневник' },
    { path: '/meals', icon: BookOpen, label: 'Приемы' },
    { path: '/analysis-history', icon: History, label: 'Анализы' },
    { path: '/profile', icon: User, label: 'Профиль' },
  ]

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 z-40 max-w-md mx-auto">
      <div className="flex items-center justify-around h-16">
        {navItems.map(({ path, icon: Icon, label }) => (
          <a
            key={path}
            href={path}
            className={`flex flex-col items-center justify-center w-1/4 h-full transition-colors ${
              isActive(path)
                ? 'text-primary-600 dark:text-primary-400'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <Icon className="h-6 w-6 mb-1" />
            <span className="text-xs font-medium">{label}</span>
          </a>
        ))}
      </div>
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
        <div className="bg-white dark:bg-gray-950 min-h-screen">
          <div className="max-w-md mx-auto">
            <AppRoutes />
            <BottomNavigation />
          </div>
        </div>
      </AuthProvider>
    </Router>
  )
}
