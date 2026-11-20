// =====================================================================
// CONFIGURACIÓN DEL SISTEMA
// =====================================================================

// URL donde corre tu backend de Flask. En local normalmente es esta;
// cuando publiques el backend en un servidor real, cambia esto por su URL.
const API_BASE_URL = window.location.origin

// Consigue tu token gratis en https://account.mapbox.com/access-tokens/
const MAPBOX_TOKEN = 'PON_AQUpk.eyJ1IjoiZm9ydGFuZWxseSIsImEiOiJjbXRwbjB6b3kxNjFmMnhvY3h3dndzY2ZsIn0.WMPvdTmO1duwQCr3uChbrQI_TU_MAPBOX_TOKEN'

// Consigue tu Site Key gratis en https://dash.cloudflare.com/ > Turnstile
// (agrega "localhost" como dominio ahí para poder probarlo en tu máquina).
// Esta clave es pública, sí puede ir en el repositorio. La verificación
// real ahora ocurre en el backend (ver backend/.env — TURNSTILE_SECRET_KEY).
const TURNSTILE_SITE_KEY = 'PON_AQUI_TU_TURNSTILE_SITE_KEY'

// Los usuarios YA NO se definen aquí. Ahora viven en la base de datos
// del backend, con la contraseña encriptada. Para crear o editar
// usuarios, edita backend/seed_users.py y corre: python seed_users.py
