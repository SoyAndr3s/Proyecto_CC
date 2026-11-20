// =====================================================================
// PUNTO DE ENTRADA
// =====================================================================
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons()

  initTheme()
  initMenu()
  initAuth() // muestra login o la app según la sesión, y llama a startApp() al entrar
  initProfileView()
})

// Se ejecuta una sola vez, justo después de iniciar sesión correctamente
let appStarted = false
window.onLoginSuccess = () => {
  if (appStarted) return
  appStarted = true

  initClockAndLocation()
  initAccordion()
  initIdentidadTable()
  initServidoresTable()
  initDocumentacionToggle()
  initToolbar()

  // Si cambian de tema después de que el mapa ya existe, actualiza su estilo
  const themeBtn = document.getElementById('themeToggle')
  if (themeBtn) themeBtn.addEventListener('click', () => setTimeout(syncMapStyleWithTheme, 50))
}

// ---------------------------------------------------------------------
// Menú superior (⋮)
// ---------------------------------------------------------------------
function initMenu() {
  const menuTrigger = document.getElementById('menuTrigger')
  const menuPopover = document.getElementById('menuPopover')
  menuTrigger.addEventListener('click', (e) => {
    e.stopPropagation()
    menuPopover.hidden = !menuPopover.hidden
  })
  document.addEventListener('click', () => { menuPopover.hidden = true })
  menuPopover.addEventListener('click', (e) => e.stopPropagation())
}

// ---------------------------------------------------------------------
// Modal "Mi perfil" (solo lectura — los datos vienen del backend)
// ---------------------------------------------------------------------
function initProfileView() {
  const modal = document.getElementById('profileModal')
  document.getElementById('openProfile').addEventListener('click', () => { modal.hidden = false })
  document.getElementById('closeProfile').addEventListener('click', () => { modal.hidden = true })
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true })
}
