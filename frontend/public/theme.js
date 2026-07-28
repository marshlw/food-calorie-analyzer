// Применяем сохранённую тему ДО первого рендера, чтобы тёмная тема
// не «мигала» светлой. Вынесено из index.html в отдельный файл ради CSP:
// на проде действует script-src 'self' без 'unsafe-inline' (см. Caddyfile).
try {
  if (localStorage.getItem('theme') === 'dark') {
    document.documentElement.classList.add('dark')
  }
} catch (e) {}
