(() => {
  const site = document.querySelector('.talya-site');
  if (!site) return;
  const toggle = site.querySelector('.menu-toggle');
  const nav = site.querySelector('.main-nav');
  toggle?.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  site.querySelector('.language-switch')?.addEventListener('click', event => {
    // A real language URL also works with JavaScript disabled. Keep anchors such
    // as #appointment on the corresponding page without storing patient details.
    event.currentTarget.hash = window.location.hash;
  });
})();
