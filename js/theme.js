// =====================================================================
// MODO OSCURO
// =====================================================================
const THEME_KEY = 'cadena_custodia_theme'

function applyStoredTheme() {
  const saved = localStorage.getItem(THEME_KEY)
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const theme = saved || (prefersDark ? 'dark' : 'light')
  document.documentElement.setAttribute('data-theme', theme)
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme')
  const next = current === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', next)
  localStorage.setItem(THEME_KEY, next)
}

function initTheme() {
  const btn = document.getElementById('themeToggle')
  if (btn) btn.addEventListener('click', toggleTheme)
}

// Aplica el tema guardado lo antes posible (antes de pintar el resto de la página)
applyStoredTheme()
