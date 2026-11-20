/* Tema común para panel, etapas y administración. */
(() => {
  const KEY = 'cadena_custodia_theme';
  const getTheme = () => localStorage.getItem(KEY) || 'dark';
  const apply = () => {
    const theme = getTheme();
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('.app-shell').forEach(el => {
      el.classList.toggle('theme-light', theme === 'light');
      el.classList.toggle('theme-dark', theme !== 'light');
    });
    document.documentElement.classList.remove('pre-theme-dark', 'pre-theme-light');
  };
  const toggle = () => {
    localStorage.setItem(KEY, getTheme() === 'dark' ? 'light' : 'dark');
    apply();
  };
  window.CustodiaTheme = { apply, toggle, get: getTheme };
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    ['stageTheme', 'portalTheme', 'adminTheme'].forEach(id => {
      document.getElementById(id)?.addEventListener('click', toggle);
    });
    apply();
  });
})();
