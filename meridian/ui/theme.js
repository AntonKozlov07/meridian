/* Theme: follows the system until the user picks one. app.js shows the button and saves the choice. */
(function () {
  var root = document.documentElement, mq = window.matchMedia && matchMedia('(prefers-color-scheme: light)');
  var pref = null; /* 'dark' | 'light' | null = follow the system */
  function effective() { return pref || (mq && mq.matches ? 'light' : 'dark'); }
  function apply(user) {
    root.setAttribute('data-theme', effective());
    document.dispatchEvent(new CustomEvent('meridian-theme', { detail: { theme: effective(), pref: pref, user: !!user } }));
  }
  window.meridianTheme = {
    set: function (t) { pref = (t === 'dark' || t === 'light') ? t : null; apply(false); },
    toggle: function () { pref = effective() === 'light' ? 'dark' : 'light'; apply(true); },
    current: effective
  };
  if (mq && mq.addEventListener) mq.addEventListener('change', function () { if (!pref) apply(false); });
  apply(false);
})();
