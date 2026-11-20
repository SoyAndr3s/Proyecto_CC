// =====================================================================
// MAPBOX + GEOLOCALIZACIÓN
// =====================================================================
let map = null
let marker = null
let currentCoords = null // { lat, lng }

function initClockAndLocation() {
  document.getElementById('fechaHora').value = formatNow()
  document.getElementById('btnRelocate').addEventListener('click', requestLocation)
  requestLocation()
}

function formatNow() {
  const now = new Date()
  return now.toLocaleString('es-MX', {
    day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function requestLocation() {
  const coordsText = document.getElementById('coordsText')
  const mapHint = document.getElementById('mapHint')

  if (!navigator.geolocation) {
    coordsText.innerHTML = '<i data-lucide="map-pin"></i> Tu navegador no soporta geolocalización'
    if (window.lucide) lucide.createIcons()
    return
  }

  coordsText.innerHTML = '<i data-lucide="map-pin"></i> Obteniendo ubicación...'
  if (window.lucide) lucide.createIcons()

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords
      currentCoords = { lat: latitude, lng: longitude }
      setCoordsText(latitude, longitude)
      initOrMoveMap(latitude, longitude)
      reverseGeocode(latitude, longitude)
    },
    () => {
      coordsText.innerHTML = '<i data-lucide="map-pin"></i> No se pudo obtener tu ubicación'
      mapHint.textContent = 'Permite el acceso a tu ubicación en el navegador, o haz clic en el mapa para colocar el pin manualmente.'
      if (window.lucide) lucide.createIcons()
      initOrMoveMap(19.4326, -99.1332) // fallback editable con clic
    },
    { enableHighAccuracy: true, timeout: 8000 }
  )
}

function setCoordsText(lat, lng) {
  const coordsText = document.getElementById('coordsText')
  coordsText.innerHTML = `<i data-lucide="map-pin"></i> ${lat.toFixed(4)}° N, ${lng.toFixed(4)}° O`
  if (window.lucide) lucide.createIcons()
}

function initOrMoveMap(lat, lng) {
  if (MAPBOX_TOKEN === 'PON_AQUI_TU_MAPBOX_TOKEN') {
    document.getElementById('mapPrincipal').innerHTML =
      '<div style="padding:16px;font-size:11px;color:var(--muted-foreground)">Agrega tu Mapbox access token en js/config.js (const MAPBOX_TOKEN) para ver el mapa interactivo.</div>'
    return
  }

  if (!window.mapboxgl) return

  mapboxgl.accessToken = MAPBOX_TOKEN

  if (!map) {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
    map = new mapboxgl.Map({
      container: 'mapPrincipal',
      style: isDark ? 'mapbox://styles/mapbox/dark-v11' : 'mapbox://styles/mapbox/light-v11',
      center: [lng, lat],
      zoom: 15,
    })
    map.addControl(new mapboxgl.NavigationControl(), 'top-right')
    map.on('error', (e) => console.error('Mapbox error:', e?.error?.message || e))
    map.on('load', () => map.resize())
    window.addEventListener('resize', () => map && map.resize())

    // Repinta las capas cada vez que el mapa carga un estilo (inicio o cambio de tema)
    map.on('style.load', () => {
      const isDarkNow = document.documentElement.getAttribute('data-theme') === 'dark'
      if (isDarkNow) applyCustomDarkPalette()
    })

    marker = new mapboxgl.Marker({ draggable: true, color: '#E8B94A' })
      .setLngLat([lng, lat])
      .addTo(map)

    marker.on('dragend', () => {
      const pos = marker.getLngLat()
      currentCoords = { lat: pos.lat, lng: pos.lng }
      setCoordsText(pos.lat, pos.lng)
      reverseGeocode(pos.lat, pos.lng)
    })

    map.on('click', (e) => {
      const { lat, lng } = e.lngLat
      marker.setLngLat([lng, lat])
      currentCoords = { lat, lng }
      setCoordsText(lat, lng)
      reverseGeocode(lat, lng)
    })
  } else {
    map.setCenter([lng, lat])
    marker.setLngLat([lng, lat])
  }
}

async function reverseGeocode(lat, lng) {
  const lugarField = document.getElementById('lugarIntervencion')
  if (MAPBOX_TOKEN === 'PON_AQUI_TU_MAPBOX_TOKEN') return

  try {
    const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${lng},${lat}.json?access_token=${MAPBOX_TOKEN}&language=es&limit=1`
    const res = await fetch(url)
    const data = await res.json()
    const place = data?.features?.[0]?.place_name
    if (place) {
      lugarField.value = place
      const firstUbic = document.querySelector('#identidadBody .cell-ubic')
      if (firstUbic && !firstUbic.value) firstUbic.value = place
    }
  } catch (err) {
    console.error('Error al obtener la dirección:', err)
  }
}

// Si el usuario cambia de modo claro/oscuro, recarga el estilo del mapa
function syncMapStyleWithTheme() {
  if (!map) return
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  map.setStyle(isDark ? 'mapbox://styles/mapbox/dark-v11' : 'mapbox://styles/mapbox/light-v11')
  // No hace falta llamar applyCustomDarkPalette() aquí: el listener 'style.load'
  // de initOrMoveMap ya se encarga de repintar en cuanto el nuevo estilo termine de cargar.
}

// =====================================================================
// PALETA PERSONALIZADA PARA EL MODO OSCURO DEL MAPA
// Edita estos colores si quieres cambiar la apariencia del mapa oscuro.
// El amarillo del pin y de los títulos de la interfaz NO se tocan aquí.
// =====================================================================
const DARK_MAP_PALETTE = {
  land: '#292929',
  motorway: '#3D3D3D',
  greenspace: '#272525',
  water: '#1F1F1F',
  transit: '#A8A8A8',
  poi: '#878787',
}

function applyCustomDarkPalette() {
  if (!map) return
  const style = map.getStyle()
  if (!style || !style.layers) return

  style.layers.forEach((layer) => {
    const id = layer.id.toLowerCase()
    try {
      if (id === 'background') {
        setIfSupported(layer.id, 'background-color', DARK_MAP_PALETTE.land)
      } else if (id.includes('water')) {
        setIfSupported(layer.id, 'fill-color', DARK_MAP_PALETTE.water)
        setIfSupported(layer.id, 'line-color', DARK_MAP_PALETTE.water)
      } else if (id.includes('landuse') || id.includes('park') || id.includes('green') || id.includes('wood') || id.includes('forest') || id.includes('golf') || id.includes('pitch') || id.includes('cemetery') || id.includes('hospital') || id.includes('school')) {
        setIfSupported(layer.id, 'fill-color', DARK_MAP_PALETTE.greenspace)
      } else if (id.includes('building')) {
        setIfSupported(layer.id, 'fill-color', '#232323')
      } else if (id.includes('motorway') || id.includes('trunk')) {
        setIfSupported(layer.id, 'line-color', DARK_MAP_PALETTE.motorway)
      } else if (id.includes('transit') || id.includes('rail') || id.includes('aerialway') || id.includes('ferry')) {
        setIfSupported(layer.id, 'line-color', DARK_MAP_PALETTE.transit)
        setIfSupported(layer.id, 'text-color', DARK_MAP_PALETTE.transit)
        setIfSupported(layer.id, 'icon-color', DARK_MAP_PALETTE.transit)
      } else if (id.includes('road') || id.includes('street') || id.includes('bridge') || id.includes('tunnel') || id.includes('path')) {
        setIfSupported(layer.id, 'line-color', DARK_MAP_PALETTE.motorway)
      } else if (id.includes('poi')) {
        setIfSupported(layer.id, 'text-color', DARK_MAP_PALETTE.poi)
        setIfSupported(layer.id, 'icon-color', DARK_MAP_PALETTE.poi)
      }
      // Nota: los rótulos de calles/lugares y el amarillo de la interfaz
      // (títulos, pin del mapa) se dejan tal cual, sin tocar.
    } catch (e) {
      // Algunas capas no soportan cierta propiedad de pintura; se ignoran sin romper el resto
    }
  })
}

function setIfSupported(layerId, property, value) {
  try {
    map.setPaintProperty(layerId, property, value)
  } catch (e) {
    // La capa no tiene esa propiedad (ej. una capa de línea no acepta fill-color) — se ignora
  }
}
