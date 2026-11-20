/* Interacciones sin dependencias externas. */
const icons = {
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  home:'<path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/>',
  file:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/>',
  book:'<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
  settings:'<circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.6-1.4-2.4L7.1 15a8 8 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.6a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.6 1.4 2.4-1.4 1.1a8 8 0 0 1 0 2z"/>',
  chevron:'<path d="m9 18 6-6-6-6"/>', bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/>',
  moon:'<path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13z"/>', menu:'<path d="M4 6h16M4 12h16M4 18h16"/>', x:'<path d="m18 6-12 12M6 6l12 12"/>',
  help:'<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3m.1 4h.01"/>', search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>', shield:'<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z"/><path d="m9 12 2 2 4-4"/>',
  building:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 21V9h6v12M7 7h.01M17 7h.01M7 11h.01M17 11h.01"/>',
  briefcase:'<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V4h8v3M3 12h18M10 12v2h4v-2"/>'
};
document.querySelectorAll('[data-icon]').forEach(el => {
  const name = el.dataset.icon;
  if (icons[name]) el.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]}</svg>`;
});

const app = document.getElementById('app');
const themeToggle = document.getElementById('themeToggle');

// Recuperar el tema guardado al abrir cualquier página.
const savedTheme = localStorage.getItem('portal-theme');
const initialTheme = savedTheme || 'theme-dark';

if (app) {
  app.classList.remove('theme-dark', 'theme-light');
  app.classList.add(initialTheme);
}

function updateThemeIcon() {
  if (!themeToggle || !app) return;

  const dark = app.classList.contains('theme-dark');
  const iconName = dark ? 'sun' : 'moon';

  themeToggle.innerHTML =
    `<span data-icon="${iconName}"></span>`;

  themeToggle.setAttribute(
    'aria-label',
    dark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'
  );

  const holder = themeToggle.querySelector('[data-icon]');

  if (holder && icons[iconName]) {
    holder.innerHTML =
      `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[iconName]}</svg>`;
  }
}

updateThemeIcon();

if (themeToggle && app) {
  themeToggle.addEventListener('click', () => {
    const dark = app.classList.contains('theme-dark');
    const newTheme = dark ? 'theme-light' : 'theme-dark';

    app.classList.remove('theme-dark', 'theme-light');
    app.classList.add(newTheme);

    // Guardar la elección para las demás páginas.
    localStorage.setItem('portal-theme', newTheme);

    updateThemeIcon();
  });
}
const nav = document.getElementById('mainNav');
const menuToggle = document.getElementById('menuToggle');
const closeMenu = document.getElementById('closeMenu');
function setMenu(open) {
  if (!nav || !menuToggle) return;
  nav.classList.toggle('is-open', open);
  menuToggle.setAttribute('aria-expanded', String(open));
}
menuToggle?.addEventListener('click', () => setMenu(true));
closeMenu?.addEventListener('click', () => setMenu(false));
const notificationToggle = document.getElementById('notificationToggle');
const popover = document.getElementById('notificationPopover');
function toggleNotifications(open) {
  if (!popover || !notificationToggle) return;
  popover.classList.toggle('hidden', !open);
  notificationToggle.setAttribute('aria-expanded', String(open));
  notificationToggle.classList.toggle('selected', open);
}
notificationToggle?.addEventListener('click', (event) => {
  event.stopPropagation();
  toggleNotifications(popover?.classList.contains('hidden'));
});
document.addEventListener('click', (event) => {
  if (popover && !popover.classList.contains('hidden') && !popover.contains(event.target) && !notificationToggle?.contains(event.target)) toggleNotifications(false);
});
document.getElementById('openInbox')?.addEventListener('click', () => { window.location.href = 'pages/solicitudes.html'; });

document.getElementById('requestForm')?.addEventListener('submit', (event) => {
  event.preventDefault();
  const message = document.getElementById('formMessage');
  if (message) message.textContent = 'Solicitud de demostración registrada en esta pantalla. No se guardó en un servidor.';
});



function updateDateAndGreeting() {
  const now = new Date();

  // Fecha actual en español.
  const dateElement = document.getElementById('currentDate');

  if (dateElement) {
    const formattedDate = new Intl.DateTimeFormat('es-MX', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    }).format(now);

    dateElement.textContent = formattedDate.toLocaleUpperCase('es-MX');
  }

  // Saludo según la hora local del dispositivo.
  const greetingElement = document.getElementById('greeting');

  if (greetingElement) {
    const hour = now.getHours();
    let greeting;

    if (hour >= 5 && hour < 12) {
      greeting = 'Buenos días';
    } else if (hour >= 12 && hour < 19) {
      greeting = 'Buenas tardes';
    } else {
      greeting = 'Buenas noches';
    }

    greetingElement.textContent = greeting;
  }
}

updateDateAndGreeting();
