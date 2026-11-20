/* Panel de inicio: obtiene perfil y registros directamente de Flask. */
const SESSION_KEY = 'cadena_custodia_sesion';

function getSession() {
  try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null'); }
  catch { return null; }
}
function authHeaders() {
  const s = getSession();
  return { Authorization: `Bearer ${s?.token || ''}`, Accept: 'application/json' };
}
function initials(name) {
  return (name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).map(x => x[0].toUpperCase()).join('') || '--';
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function setText(id, value, fallback = '—') {
  const el = document.getElementById(id);
  if (el) el.textContent = value || fallback;
}
function showProfileError(message) {
  setText('portalName', 'No disponible');
  setText('welcomeName', 'usuario');
  setText('profileName', 'No se pudo cargar el perfil');
  setText('profileInstitution', message);
  setText('profileRole', 'Revisa la conexión con Flask');
  setText('profileUser', '—');
}
async function apiJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) }
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    sessionStorage.removeItem(SESSION_KEY);
    location.replace('login.html');
    throw new Error('La sesión expiró. Vuelve a iniciar sesión.');
  }
  if (!response.ok) throw new Error(data.error || `Error HTTP ${response.status} al consultar ${path}`);
  return data;
}
function setDateAndGreeting() {
  const now = new Date();
  setText('currentDate', new Intl.DateTimeFormat('es-MX', { weekday:'long', day:'numeric', month:'long', year:'numeric' }).format(now).toUpperCase());
  const h = now.getHours();
  setText('greeting', h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches');
}

async function loadProfile() {
  try {
    // No se usan datos de caché como si fueran actuales: el perfil debe venir del backend.
    const user = await apiJson('/api/me');
    const name = user.nombre || user.usuario || 'Usuario';
    const avatar = initials(name);
    setText('portalAvatar', avatar); setText('profileAvatar', avatar);
    setText('portalName', name); setText('welcomeName', name.split(/\s+/)[0]);
    setText('profileName', name); setText('profileInstitution', user.institucion);
    setText('profileRole', user.cargo); setText('profileUser', user.usuario);
    const adminNav = document.getElementById('adminNav');
    if (adminNav) adminNav.hidden = !(user.permisos || []).includes('admin.access');
    const oldSession = getSession();
    if (oldSession) sessionStorage.setItem(SESSION_KEY, JSON.stringify({ ...oldSession, user }));
  } catch (error) {
    console.error('Error cargando perfil desde /api/me:', error);
    showProfileError(error.message || 'No se pudo consultar /api/me');
  }
}
async function loadRecords() {
  const container = document.getElementById('recordsList');
  if (!container) return;
  container.innerHTML = '<p class="muted">Consultando registros en la base de datos…</p>';
  try {
    const records = await apiJson('/api/registros');
    if (!Array.isArray(records)) throw new Error('La API /api/registros no devolvió una lista.');
    if (records.length === 0) {
      container.innerHTML = '<div class="activity-item"><span class="activity-icon"><i data-lucide="inbox"></i></span><div><strong>La base de datos respondió, pero no hay registros asignados a este usuario.</strong><p>Esto no es un error visual: crea y guarda un RCC o revisa en SQLite que existan registros y que el usuario actual sea su responsable vigente.</p></div></div>';
    } else {
      container.innerHTML = records.map(record => {
        const folio = escapeHtml(record.folio || `Registro #${record.id}`);
        const lugar = escapeHtml(record.lugarIntervencion || 'Lugar no especificado');
        const fecha = escapeHtml(record.fechaHora || record.creadoEn || 'Sin fecha');
        return `<a class="activity-item record-link" href="entrega-recepcion.html?registro=${encodeURIComponent(record.id)}"><span class="activity-icon"><i data-lucide="file-text"></i></span><span><strong>${folio}</strong><small>${lugar} · ${fecha}</small></span><i data-lucide="chevron-right"></i></a>`;
      }).join('');
    }
  } catch (error) {
    console.error('Error cargando registros desde /api/registros:', error);
    container.innerHTML = `<div class="activity-item"><div><strong>No se pudieron consultar los registros.</strong><p>${escapeHtml(error.message)}. Confirma que instalaste el app.py corregido y que Flask está ejecutándose en el mismo origen que el panel.</p></div></div>`;
  }
  if (window.lucide) window.lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', async () => {
  const session = getSession();
  if (!session?.token) { location.replace('login.html'); return; }
  setDateAndGreeting();
  if (window.CustodiaTheme) window.CustodiaTheme.apply();
  document.getElementById('portalLogout')?.addEventListener('click', () => {
    sessionStorage.removeItem(SESSION_KEY);
    location.replace('login.html');
  });
  document.getElementById('refreshRecords')?.addEventListener('click', loadRecords);
  await Promise.all([loadProfile(), loadRecords()]);
  if (window.lucide) window.lucide.createIcons();
});
