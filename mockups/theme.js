/* Theme switcher + PWA service worker registration */
(function () {
  // Apply saved theme before first paint (avoids flash)
  var saved = localStorage.getItem('onco-theme') || 'slate';
  document.documentElement.dataset.theme = saved;

  document.addEventListener('DOMContentLoaded', function () {
    // Sync button active state
    document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.themeBtn === saved);
      btn.addEventListener('click', function () {
        var t = btn.dataset.themeBtn;
        document.documentElement.dataset.theme = t;
        localStorage.setItem('onco-theme', t);
        document.querySelectorAll('[data-theme-btn]').forEach(function (b) {
          b.classList.toggle('active', b === btn);
        });
      });
    });
  });

  // Register service worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/mockups/sw.js').catch(function () {});
  }
})();
