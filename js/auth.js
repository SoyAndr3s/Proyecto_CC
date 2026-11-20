// =====================================================================
// LOGIN / SESIÓN — ahora contra el backend de Flask (js/config.js:API_BASE_URL)
// =====================================================================
const SESSION_KEY = 'cadena_custodia_sesion'
let turnstileToken = null
let turnstileWidgetId = null

function getSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY)) // { token, user }
  } catch (e) {
    return null
  }
}

function setSession(session) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY)
}

// Encabezado listo para usar en cualquier fetch() protegido
function authHeader() {
  const session = getSession()
  return session?.token ? { Authorization: `Bearer ${session.token}` } : {}
}

// ---------------------------------------------------------------------
// Cloudflare Turnstile
// ---------------------------------------------------------------------
function initTurnstile() {
  const container = document.getElementById('turnstileWidget')

  if (TURNSTILE_SITE_KEY === 'PON_AQUI_TU_TURNSTILE_SITE_KEY') {
    container.innerHTML = '<p class="helper-text">Agrega tu Site Key de Cloudflare Turnstile en js/config.js para activar el captcha.</p>'
    turnstileToken = 'sin-captcha-configurado'
    return
  }

  if (!window.turnstile) {
    setTimeout(initTurnstile, 200)
    return
  }

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  turnstileWidgetId = window.turnstile.render(container, {
    sitekey: TURNSTILE_SITE_KEY,
    theme: isDark ? 'dark' : 'light',
    callback: (token) => { turnstileToken = token },
    'expired-callback': () => { turnstileToken = null },
    'error-callback': () => { turnstileToken = null },
  })
}

function resetTurnstile() {
  if (window.turnstile && turnstileWidgetId !== null) {
    window.turnstile.reset(turnstileWidgetId)
  }
  if (TURNSTILE_SITE_KEY !== 'PON_AQUI_TU_TURNSTILE_SITE_KEY') turnstileToken = null
}

// ---------------------------------------------------------------------
// Aplicar los datos del usuario logueado a la interfaz
// ---------------------------------------------------------------------
function applyUserToUI(user) {
  const initials = (user.nombre || '--').split(' ').filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('') || '--'
  document.getElementById('topAvatar').textContent = initials
  document.getElementById('topName').textContent = user.nombre || 'Sin nombre'
  document.getElementById('topRole').textContent = user.cargo || 'Sin cargo'

  const personaRegistro = document.getElementById('personaRegistro')
  if (personaRegistro) {
    personaRegistro.value = [user.nombre, user.institucion, user.cargo].filter(Boolean).join(' · ')
  }

  const firstRow = document.querySelector('#servidoresBody tr')
  if (firstRow) {
    const nombreInput = firstRow.querySelector('.cell-nombre')
    const instInput = firstRow.querySelector('.cell-inst')
    if (nombreInput && !nombreInput.value) nombreInput.value = user.nombre
    if (instInput && !instInput.value) instInput.value = [user.institucion, user.cargo].filter(Boolean).join(' — ')
  }

  document.getElementById('perfilViewNombre').textContent = user.nombre || '—'
  document.getElementById('perfilViewInstitucion').textContent = user.institucion || '—'
  document.getElementById('perfilViewCargo').textContent = user.cargo || '—'
}

function showApp(user) {
  const loginScreen = document.getElementById('loginScreen')
  const appShell = document.getElementById('appShell')
  if (loginScreen) loginScreen.hidden = true
  if (appShell) appShell.hidden = false
  applyUserToUI(user)
  if (window.onLoginSuccess) window.onLoginSuccess()
}

function showLogin() {
  const loginScreen = document.getElementById('loginScreen')
  const appShell = document.getElementById('appShell')
  if (loginScreen) loginScreen.hidden = false
  if (appShell) appShell.hidden = true
  if (!loginScreen) location.replace('login.html')
}

// ---------------------------------------------------------------------
// Login contra el backend
// ---------------------------------------------------------------------
function initAuth() {
  const form = document.getElementById('loginForm')
  const existing = getSession()
  if (!form) {
    if (existing?.user) showApp(existing.user)
    else showLogin()
    return
  }
  const errorEl = document.getElementById('loginError')
  const submitBtn = form.querySelector('.login-submit')
  initTurnstile()

  form.addEventListener('submit', async (e) => {
    e.preventDefault()

    if (!turnstileToken) {
      errorEl.textContent = 'Completa el captcha antes de continuar.'
      return
    }

    const usuario = document.getElementById('loginUsuario').value.trim()
    const password = document.getElementById('loginPassword').value

    errorEl.textContent = ''
    submitBtn.disabled = true
    submitBtn.textContent = 'Entrando...'

    try {
      const res = await fetch(`${API_BASE_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario, password, turnstileToken }),
      })
      const data = await res.json()

      if (!res.ok) {
        errorEl.textContent = data.error || 'No se pudo iniciar sesión.'
        resetTurnstile()
        return
      }

      setSession({ token: data.token, user: data.user })
      showApp(data.user)
    } catch (err) {
      console.error(err)
      errorEl.textContent = 'No se pudo conectar con el servidor. ¿Está corriendo el backend (python app.py)?'
    } finally {
      submitBtn.disabled = false
      submitBtn.textContent = 'Iniciar sesión'
    }
  })

  const logoutBtn = document.getElementById('logoutBtn')
  if (logoutBtn) logoutBtn.addEventListener('click', () => {
    clearSession()
    document.getElementById('loginPassword').value = ''
    resetTurnstile()
    showLogin()
  })

  const existingSession = getSession()
  if (existingSession?.user) {
    showApp(existingSession.user)
  } else {
    showLogin()
  }
}
