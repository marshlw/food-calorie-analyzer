/** @type {import('tailwindcss').Config} */

// Дизайн-токены Rasify (из «Rasify — дизайн», вариант 1a «Кольцо»)
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Интерфейсный текст
        sans: ["'Golos Text'", '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        // Заголовки и крупные цифры
        display: ['Manrope', "'Golos Text'", 'sans-serif'],
      },
      colors: {
        // Акцент: azure. primary-* сохранён для совместимости со старым кодом.
        primary: {
          50: '#eaf1fc',   // чипы/soft-кнопки (light)
          100: '#dbe7fb',
          200: '#c9d7f2',
          300: '#a9c2ef',
          400: '#7fa8f5',  // акцент в тёмной теме
          500: '#2b6fe3',  // основной azure
          600: '#2b6fe3',
          700: '#1e56bc',  // hover / градиент
          800: '#1a2942',
          900: '#182238',  // чипы (dark)
        },
        ink: '#0c1424',          // основной текст (light)
        'ink-dark': '#eef1f7',   // основной текст (dark)
        surface: '#f5f7fb',      // фон страницы (light)
        'surface-dark': '#0a0f1c',
        'card-dark': '#111a2d',  // карточки (dark)
        line: '#e7ebf3',         // границы карточек (light)
        'line-dark': '#1c2537',
        divider: '#f0f3f8',      // разделители строк (light)
        track: '#eef1f7',        // фон прогресс-баров (light)
        'track-dark': '#1c2537',
        muted: '#5b667d',        // вторичный текст (light)
        'muted-dark': '#8b96ad',
        faint: '#98a2b8',        // третичный текст (light)
        'faint-dark': '#5b6880',
        'chip-dark': '#182238',  // фон чипов (dark)
        // Макронутриенты
        protein: { DEFAULT: '#c4795f', dark: '#d08a6c', chip: '#f7f1e6', text: '#8a6f36' },
        fat: { DEFAULT: '#b29455', dark: '#c2a468', chip: '#f7f1e6', text: '#8a6f36' },
        carbs: { DEFAULT: '#5fa07c', dark: '#6fb28c', chip: '#eef5f0', text: '#3d7a58' },
        water: { DEFAULT: '#5e9dc9', chip: '#e9f2f9' },
        dinner: { DEFAULT: '#3d4a68', dark: '#9aa7c9', chip: '#e9edf6' },
        danger: {
          DEFAULT: '#c0492f',
          500: '#c0492f',
          600: '#a63d27',
        },
        success: {
          500: '#5fa07c',
          600: '#3d7a58',
        },
      },
      borderRadius: {
        card: '20px',   // крупные карточки
        tile: '16px',   // мелкие карточки/записи
        cell: '14px',   // ячейки недели
      },
      boxShadow: {
        card: '0 1px 2px rgba(16,24,40,.04)',
        nav: '0 8px 24px rgba(12,20,36,.10)',
        'nav-dark': '0 8px 24px rgba(0,0,0,.4)',
        cta: '0 6px 16px rgba(43,111,227,.4)',
        day: '0 4px 12px rgba(43,111,227,.3)',
      },
      animation: {
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  darkMode: 'class',
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
