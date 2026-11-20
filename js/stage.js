const SESSION_KEY = 'cadena_custodia_sesion';
const stageSession = () => { try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); } catch { return null; } };
const stageHeaders = () => ({ Authorization: `Bearer ${stageSession()?.token || ''}`, 'Content-Type': 'application/json' });
let records = [];
let usersDirectory = [];
const byId = id => document.getElementById(id);
const selectedRecord = () => records.find(r => String(r.id) === String(byId('recordSelect')?.value));

 document.addEventListener('DOMContentLoaded', async () => {
  const session = stageSession();
  if (!session?.token) { location.replace('login.html'); return; }
  if (window.CustodiaTheme) window.CustodiaTheme.apply();
  byId('stageUser').textContent = session.user?.nombre || session.user?.usuario || '';
  byId('stageLogout')?.addEventListener('click', () => { sessionStorage.removeItem(SESSION_KEY); location.replace('login.html'); });

  const form = byId('stageForm');
  const pageStage = form?.dataset.stage || document.body.dataset.stage || '';
  if (pageStage === 'entrega-recepcion') {
    if (!(session.user?.permisos || []).includes('entrega.create')) { byId('pendingTransfers').textContent = 'Tu rol no tiene permiso para confirmar entregas–recepciones.'; return; }
    await loadPendingTransfers();
    if (window.lucide) lucide.createIcons();
    return;
  }

  const fixedStage = pageStage && pageStage !== 'nuevo-movimiento';
  if (fixedStage) {
    const selector = byId('stageSelect');
    if (selector) { selector.value = pageStage; selector.disabled = true; }
    const permission = `${pageStage}.create`;
    if (!(session.user?.permisos || []).includes(permission)) {
      byId('stageMessage').textContent = 'Tu cuenta no tiene permiso para registrar esta etapa. Solicita al administrador la autorización correspondiente.';
      form.querySelectorAll('input,select,textarea,button').forEach(el => el.disabled = true);
      return;
    }
  }

  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  if (byId('stageDate')) byId('stageDate').value = now.toISOString().slice(0, 16);
  form?.addEventListener('submit', saveStage);
  byId('recordSelect')?.addEventListener('change', loadIndicios);
  byId('indicioSelect')?.addEventListener('change', loadTrace);
  byId('analysisNextStage')?.addEventListener('change', updateReceiverOptions);
  try {
    const [rr, ur] = await Promise.all([
      fetch(`${API_BASE_URL}/api/registros`, { headers: stageHeaders() }),
      fetch(`${API_BASE_URL}/api/usuarios`, { headers: stageHeaders() })
    ]);
    const [recordData, users] = await Promise.all([rr.json(), ur.json()]);
    if (!rr.ok) throw Error(recordData.error || 'No se pudieron cargar los registros.');
    if (!ur.ok) throw Error(users.error || 'No se pudo cargar el directorio de usuarios.');
    records = recordData;
    const select = byId('recordSelect');
    select.innerHTML = records.length ? '<option value="">Selecciona un registro…</option>' + records.map(r => `<option value="${r.id}">${escStage(r.folio || `Registro #${r.id}`)} — ${escStage(r.lugarIntervencion || 'RCC')}</option>`).join('') : '<option value="">No tienes indicios asignados</option>';
    usersDirectory = users;
    updateReceiverOptions();
    const q = new URLSearchParams(location.search).get('registro');
    if (q && records.some(r => String(r.id) === q)) { select.value = q; await loadIndicios(); }
  } catch (error) { byId('stageMessage').textContent = `${error.message} Verifica que el backend esté ejecutándose.`; }
  if (window.lucide) lucide.createIcons();
});

function escStage(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function updateReceiverOptions() {
  const select = byId('nextUser');
  if (!select) return;
  const previous = select.value;
  const destination = byId('analysisNextStage')?.value || '';
  let eligible = usersDirectory.filter(u => (u.permisos || []).includes('entrega.create'));
  if (byId('analysisNextStage')) {
    eligible = destination ? eligible.filter(u => (u.permisos || []).includes(`${destination}.create`)) : [];
    select.innerHTML = '<option value="">Selecciona responsable de la etapa asignada…</option>' + eligible.map(u => `<option value="${u.id}">${escStage(u.nombre || u.usuario)} — ${escStage(u.rol || u.cargo || '')}</option>`).join('');
  } else {
    select.innerHTML = '<option value="">Guardar sin transferir custodia</option>' + eligible.map(u => `<option value="${u.id}">${escStage(u.nombre || u.usuario)} — ${escStage(u.rol || u.cargo || '')}</option>`).join('');
  }
  if (eligible.some(u => String(u.id) === previous)) select.value = previous;
}

async function loadIndicios() {
  const record = selectedRecord(), select = byId('indicioSelect');
  if (!select) return;
  if (!record) { select.innerHTML = '<option value="">Primero selecciona un registro RCC…</option>'; select.disabled = true; byId('traceList').innerHTML = '<p class="muted">Selecciona un indicio.</p>'; return; }
  const items = record.indicios || [];
  select.disabled = false;
  select.innerHTML = items.length ? '<option value="">Selecciona un indicio…</option>' + items.map(i => `<option value="${i.id}">${escStage(i.identificacion || `Indicio #${i.id}`)} — ${escStage(i.descripcion || 'Sin descripción')}${i.etapaAsignada ? ` · Siguiente: ${escStage(i.etapaAsignada)}` : ''}</option>`).join('') : '<option value="">Este registro no tiene indicios asignados</option>';
  if (items.length === 1) { select.value = String(items[0].id); await loadTrace(); }
  else { byId('traceList').innerHTML = '<p class="muted">Selecciona el indicio para consultar su historial individual.</p>'; }
}

async function loadTrace() {
  const recordId = byId('recordSelect')?.value, indicioId = byId('indicioSelect')?.value, el = byId('traceList');
  if (!recordId || !indicioId || !el) { if (el) el.innerHTML = '<p class="muted">Selecciona un indicio.</p>'; return; }
  try {
    const response = await fetch(`${API_BASE_URL}/api/registros/${recordId}/movimientos?indicio_id=${encodeURIComponent(indicioId)}`, { headers: stageHeaders() });
    const data = await response.json(); if (!response.ok) throw Error(data.error || 'Sin permiso');
    el.innerHTML = data.length ? data.map(x => `<article class="activity-item"><span class="activity-icon"><i data-lucide="history"></i></span><div><strong>${escStage(x.etapa)} · ${escStage(x.actividad || 'Movimiento registrado')}</strong><p>${escStage(x.usuario)} · ${escStage(x.lugar || 'Lugar no especificado')} · ${escStage(x.observaciones || 'Sin observaciones')} · ${x.transferenciaEstado ? `Entrega: ${escStage(x.transferenciaEstado)}` : 'Sin transferencia asociada'}${x.etapa === 'analisis' && x.detalles?.solicitud ? ` · Solicitud: ${escStage(x.detalles.solicitud)}` : ''}</p></div><time>${escStage(new Date(x.fechaHora).toLocaleString('es-MX'))}</time></article>`).join('') : '<p class="muted">Todavía no hay movimientos registrados para este indicio.</p>';
  } catch (error) { el.innerHTML = `<p class="muted">${escStage(error.message)}</p>`; }
  if (window.lucide) lucide.createIcons();
}

async function saveStage(event) {
  event.preventDefault();
  const id = byId('recordSelect').value, indicioId = byId('indicioSelect')?.value, message = byId('stageMessage');
  if (!id) { message.textContent = 'Selecciona un registro RCC.'; return; }
  if (!indicioId) { message.textContent = 'Selecciona el indicio al que corresponde este movimiento.'; return; }
  const pageStage = byId('stageForm').dataset.stage;
  const body = {
    indicioId: Number(indicioId),
    etapa: pageStage && pageStage !== 'nuevo-movimiento' ? pageStage : byId('stageSelect').value,
    lugar: [byId('stagePlace')?.value, byId('stageDestination')?.value].filter(Boolean).join(' → '),
    actividad: byId('stageActivity')?.value,
    estadoEmbalaje: byId('stagePackage')?.value,
    observaciones: byId('stageNotes')?.value,
    fechaHora: byId('stageDate')?.value,
    siguienteUsuarioId: byId('nextUser')?.value || null,
    detalles: {
      solicitud: byId('analysisRequest')?.value || '', destinoEtapa: byId('analysisNextStage')?.value || '', metodo: byId('analysisMethod')?.value || '', resultado: byId('analysisResult')?.value || '',
      condicionesConservacion: byId('storageConditions')?.value || '', espacioContenedor: byId('storageSlot')?.value || ''
    }
  };
  try {
    const response = await fetch(`${API_BASE_URL}/api/registros/${id}/movimientos`, { method: 'POST', headers: stageHeaders(), body: JSON.stringify(body) });
    const data = await response.json(); if (!response.ok) throw Error(data.error || 'No se pudo guardar.');
    message.textContent = data.mensaje;
    if (body.siguienteUsuarioId) message.textContent += ' El responsable de este indicio no cambia hasta que el receptor acepte la entrega en Entrega–recepción.';
    await loadTrace();
    if (body.etapa === 'analisis') message.textContent += ' Este análisis quedó guardado como un evento independiente; puedes registrar análisis adicionales sin sobrescribirlo.';
  } catch (error) { message.textContent = error.message; }
}

async function loadPendingTransfers() {
  const container = byId('pendingTransfers');
  if (!container) return;
  container.innerHTML = '<p class="muted">Consultando entregas pendientes…</p>';
  try {
    const response = await fetch(`${API_BASE_URL}/api/transferencias/pendientes`, { headers: stageHeaders() });
    const data = await response.json(); if (!response.ok) throw Error(data.error || 'No se pudieron consultar las entregas.');
    if (!data.length) { container.innerHTML = '<p class="muted">No tienes entregas pendientes de recepción.</p>'; return; }
    container.innerHTML = data.map(t => `<article class="activity-item transfer-item"><div><strong>${escStage(t.folio || `Registro #${t.registroId}`)} · ${escStage(t.identificacion || `Indicio #${t.indicioId || ''}`)}</strong><p>Etapa: ${escStage(t.etapa)} · Entrega: ${escStage(t.entrega)} · ${escStage(t.lugar || 'Lugar no especificado')}</p><small>${escStage(new Date(t.fecha).toLocaleString('es-MX'))}</small><label>Observaciones de recepción<textarea id="transfer-note-${t.id}" rows="2"></textarea></label><div class="transfer-actions"><button type="button" data-accept="${t.id}">Aceptar recepción</button><button type="button" data-reject="${t.id}">Rechazar</button></div></div></article>`).join('');
    container.querySelectorAll('[data-accept]').forEach(btn => btn.addEventListener('click', () => resolveTransfer(btn.dataset.accept, 'aceptar')));
    container.querySelectorAll('[data-reject]').forEach(btn => btn.addEventListener('click', () => resolveTransfer(btn.dataset.reject, 'rechazar')));
  } catch (error) { container.innerHTML = `<p class="muted">${escStage(error.message)}</p>`; }
}
async function resolveTransfer(id, decision) {
  const note = byId(`transfer-note-${id}`)?.value || '';
  try {
    const response = await fetch(`${API_BASE_URL}/api/transferencias/${id}/resolver`, { method: 'POST', headers: stageHeaders(), body: JSON.stringify({ decision, observaciones: note }) });
    const data = await response.json(); if (!response.ok) throw Error(data.error || 'No se pudo resolver la entrega.');
    await loadPendingTransfers();
  } catch (error) { alert(error.message); }
}
