// =====================================================================
// ACORDEÓN
// =====================================================================
function initAccordion() {
  document.querySelectorAll('.accordion-card[data-section]').forEach((card) => {
    const header = card.querySelector('.section-header')
    const body = card.querySelector('.accordion-body')
    const chev = card.querySelector('.chev')

    header.addEventListener('click', () => {
      const isOpen = header.getAttribute('aria-expanded') === 'true'
      header.setAttribute('aria-expanded', String(!isOpen))
      body.hidden = isOpen
      if (chev) chev.setAttribute('data-lucide', isOpen ? 'chevron-down' : 'chevron-up')
      if (window.lucide) lucide.createIcons()
    })
  })
}

// =====================================================================
// TABLA DE IDENTIDAD DE INDICIOS
// =====================================================================
function initIdentidadTable() {
  document.getElementById('addIdentidadRow').addEventListener('click', () => addIdentidadRow())
  addIdentidadRow()
}

function addIdentidadRow() {
  const tpl = document.getElementById('identidadRowTpl')
  const clone = tpl.content.cloneNode(true)
  const row = clone.querySelector('tr')

  row.querySelector('.cell-hora').value = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })

  const fotoInput = row.querySelector('.cell-foto')
  const fotoName = row.querySelector('.cell-foto-name')
  fotoInput.addEventListener('change', () => {
    fotoName.textContent = fotoInput.files[0] ? fotoInput.files[0].name : '—'
  })

  row.querySelector('.row-remove').addEventListener('click', () => row.remove())

  document.getElementById('identidadBody').appendChild(row)
  if (window.lucide) lucide.createIcons()
}

// =====================================================================
// TABLA DE SERVIDORES PÚBLICOS (con firma)
// =====================================================================
function initServidoresTable() {
  document.getElementById('addServidorRow').addEventListener('click', () => addServidorRow())
  addServidorRow()
  const session = getSession()
  if (session?.user) applyUserToUI(session.user)
}

function addServidorRow() {
  const tpl = document.getElementById('servidorRowTpl')
  const clone = tpl.content.cloneNode(true)
  const row = clone.querySelector('tr')

  row.querySelector('.row-remove').addEventListener('click', () => row.remove())

  const canvas = row.querySelector('.sig-pad')
  const clearBtn = row.querySelector('.sig-clear')
  attachSignaturePad(canvas, clearBtn)

  document.getElementById('servidoresBody').appendChild(row)
}

// =====================================================================
// CHECKBOX "OTRO" EN DOCUMENTACIÓN
// =====================================================================
function initDocumentacionToggle() {
  const otroCheck = document.getElementById('docOtroCheck')
  const otroTexto = document.getElementById('docOtroTexto')
  otroCheck.addEventListener('change', () => {
    otroTexto.disabled = !otroCheck.checked
    if (!otroCheck.checked) otroTexto.value = ''
  })
}

// =====================================================================
// FIRMA DIGITAL (canvas)
// =====================================================================
function attachSignaturePad(canvas, clearBtn) {
  const ctx = canvas.getContext('2d')
  ctx.lineWidth = 1.6
  ctx.lineCap = 'round'
  ctx.strokeStyle = '#172a35'
  let drawing = false

  const getPos = (e) => {
    const rect = canvas.getBoundingClientRect()
    const point = e.touches ? e.touches[0] : e
    return { x: point.clientX - rect.left, y: point.clientY - rect.top }
  }

  const start = (e) => { drawing = true; const p = getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y) }
  const move = (e) => { if (!drawing) return; e.preventDefault(); const p = getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke() }
  const end = () => { drawing = false }

  canvas.addEventListener('mousedown', start)
  canvas.addEventListener('mousemove', move)
  window.addEventListener('mouseup', end)
  canvas.addEventListener('touchstart', start, { passive: true })
  canvas.addEventListener('touchmove', move, { passive: false })
  canvas.addEventListener('touchend', end)

  if (clearBtn) {
    clearBtn.addEventListener('click', () => ctx.clearRect(0, 0, canvas.width, canvas.height))
  }
}

// =====================================================================
// BARRA DE ACCIONES: Guardar / Exportar / Imprimir
// =====================================================================
const DRAFT_KEY = 'cadena_custodia_borrador'

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// Recolecta todo el formulario. Es async porque las fotos de indicios
// se convierten a base64 (igual que ya vienen las firmas del canvas)
// para poder mandarlas al backend en un solo JSON.
async function collectFormData() {
  const val = (id) => document.getElementById(id)?.value || ''

  const identidad = await Promise.all(
    Array.from(document.querySelectorAll('#identidadBody tr')).map(async (row) => {
      const fotoFile = row.querySelector('.cell-foto').files[0]
      return {
        identificacion: row.querySelector('.cell-id').value,
        descripcion: row.querySelector('.cell-desc').value,
        ubicacion: row.querySelector('.cell-ubic').value,
        hora: row.querySelector('.cell-hora').value,
        foto: fotoFile ? await fileToBase64(fotoFile) : null,
      }
    })
  )

  const servidores = Array.from(document.querySelectorAll('#servidoresBody tr')).map((row) => ({
    nombre: row.querySelector('.cell-nombre').value,
    institucion: row.querySelector('.cell-inst').value,
    etapa: row.querySelector('.cell-etapa').value,
    firma: row.querySelector('.sig-pad').toDataURL(),
  }))



  return {
    folio: val('folio'),
    institucion: val('institucion'),
    folioLlamado: val('folioLlamado'),
    fechaHora: val('fechaHora'),
    personaRegistro: val('personaRegistro'),
    lugarIntervencion: val('lugarIntervencion'),
    coords: currentCoords,
    motivoInicio: document.querySelector('input[name="motivo"]:checked')?.value || null,
    identidad,
    documentacion: Array.from(document.querySelectorAll('input[name="doc"]:checked')).map((c) => c.value),
    documentacionOtro: val('docOtroTexto'),
    recoleccionManual: val('recoleccionManual'),
    recoleccionInstrumental: val('recoleccionInstrumental'),
    empaqueBolsa: val('empaqueBolsa'),
    empaqueCaja: val('empaqueCaja'),
    empaqueRecipientes: val('empaqueRecipientes'),
    servidores,
    trazabilidad: [],
  }
}

function initToolbar() {
  const saveBtn = document.getElementById('btnSave')
  const statusEl = document.getElementById('footerStatus')

  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true
    const originalText = saveBtn.textContent
    saveBtn.textContent = 'Guardando...'
    statusEl.textContent = 'Guardando en el servidor...'

    try {
      const data = await collectFormData()

      // Respaldo local por si el backend no responde
      localStorage.setItem(DRAFT_KEY, JSON.stringify(data))

      const res = await fetch(`${API_BASE_URL}/api/registros`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(data),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || 'El servidor respondió con un error')
      }

      const result = await res.json()
      statusEl.textContent = `Guardado en el servidor (registro #${result.id}) — ${new Date().toLocaleTimeString('es-MX')}`
    } catch (err) {
      console.error(err)
      statusEl.textContent = 'No se pudo guardar en el servidor (se guardó una copia local). ¿Está corriendo el backend?'
    } finally {
      saveBtn.disabled = false
      saveBtn.textContent = originalText
    }
  })

  document.getElementById('btnExport').addEventListener('click', async () => {
    const data = await collectFormData()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cadena-custodia-${data.folio || 'borrador'}.json`
    a.click()
    URL.revokeObjectURL(url)
  })

  document.getElementById('btnPrint').addEventListener('click', () => window.print())
}
