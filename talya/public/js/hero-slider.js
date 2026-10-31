(() => {
  const site = document.querySelector('.talya-site');
  const slider = site?.querySelector('.hero-slider');
  if (!slider || slider.dataset.initialized === 'true') return;
  slider.dataset.initialized = 'true';

  // Approved website profiles only; this does not alter Healthcare booking eligibility.
  const profiles = [
    {
      id: 'farouq', image: '/assets/talya/images/dr-farouq.png',
      en: ['Dr. Farouq Ejami', 'Dentist', 'Your Health. Your Smile. Our Priority.'],
      ar: ['د. فاروق عجيمي', 'طبيب أسنان', 'صحتك.. ابتسامتك.. أولويتنا'],
    },
    {
      id: 'mehira', image: '/assets/talya/images/dr-mehira-original.webp',
      en: ['Dr. Mehira Fadl', 'General Practitioner', 'Comprehensive Care. Experience You Can Trust.'],
      ar: ['د. مهيرة فضل', 'طبيبة عامة', 'رعاية متكاملة.. خبرة تثق بها'],
    },
  ];
  const labels = {
    en: {region: 'Our doctors', carousel: 'carousel', slide: 'slide', previous: 'Previous doctor', next: 'Next doctor', select: 'Select doctor', show: 'Show', pause: 'Pause slideshow', play: 'Start slideshow'},
    ar: {region: 'أطباؤنا', carousel: 'عرض شرائح', slide: 'شريحة', previous: 'الطبيب السابق', next: 'الطبيب التالي', select: 'اختر الطبيب', show: 'عرض', pause: 'إيقاف العرض التلقائي', play: 'بدء العرض التلقائي'},
  };
  const slides = profiles.map(profile => slider.querySelector(`[data-doctor="${profile.id}"]`));
  if (slides.some(slide => !slide)) return;
  const dots = [...slider.querySelectorAll('.hero-slider-dot')];
  const toggle = slider.querySelector('.hero-slider-toggle');
  const status = slider.querySelector('.hero-slider-status');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let language = site.lang === 'ar' ? 'ar' : 'en';
  let current = 0;
  let timer;
  let userPaused = reducedMotion.matches;
  let hovered = false;
  let requestVersion = 0;
  let requested = 0;
  let touchStart = null;

  // Decode each real asset before revealing it; retain the current slide on errors.
  const ready = slides.map((slide, index) => {
    const image = slide.querySelector('.hero-portrait');
    const valid = () => image.complete && image.naturalWidth > 0
      && new URL(image.currentSrc || image.src, document.baseURI).pathname === profiles[index].image;
    return image.decode().then(valid).catch(() => false);
  });

  function updateToggle() {
    toggle.setAttribute('aria-label', labels[language][userPaused ? 'play' : 'pause']);
    toggle.firstElementChild.textContent = userPaused ? '▶' : 'Ⅱ';
    slider.dataset.autoplay = userPaused ? 'paused' : 'playing';
  }

  function schedule() {
    window.clearTimeout(timer);
    if (!userPaused && !hovered && !document.hidden) {
      timer = window.setTimeout(() => show(current + 1), 6000);
    }
  }

  function pause() {
    userPaused = true;
    updateToggle();
    schedule();
  }

  async function show(index, manual = false) {
    if (manual) pause();
    window.clearTimeout(timer);
    const version = ++requestVersion;
    const next = (index + slides.length) % slides.length;
    requested = next;
    const loaded = await ready[next];
    if (version !== requestVersion) return;
    if (!loaded || (!manual && (userPaused || hovered || document.hidden))) {
      requested = current;
      schedule();
      return;
    }
    current = next;
    // Commit the whole decoded slide synchronously. Inactive slides are not
    // rendered, including during entrance animation and rapid navigation.
    slides.forEach((slide, i) => {
      slide.classList.toggle('is-active', i === current);
      slide.setAttribute('aria-hidden', String(i !== current));
      slide.inert = i !== current;
      dots[i].setAttribute('aria-current', String(i === current));
    });
    slider.dataset.activeDoctor = profiles[current].id;
    if (manual) status.textContent = profiles[current][language].slice(0, 2).join(' — ');
    schedule();
  }

  function translate() {
    const ui = labels[language];
    slider.setAttribute('aria-label', ui.region);
    slider.setAttribute('aria-roledescription', ui.carousel);
    slider.querySelector('.hero-slider-prev').setAttribute('aria-label', ui.previous);
    slider.querySelector('.hero-slider-next').setAttribute('aria-label', ui.next);
    slider.querySelector('.hero-slider-dots').setAttribute('aria-label', ui.select);
    slides.forEach((slide, i) => {
      const [name, specialty, tagline] = profiles[i][language];
      slide.querySelector('img').alt = name;
      slide.querySelector('.doctor-badge b').textContent = name;
      slide.querySelector('.doctor-badge small').textContent = specialty;
      slide.querySelector('.hero-note p').textContent = tagline;
      slide.setAttribute('aria-roledescription', ui.slide);
      dots[i].setAttribute('aria-label', `${ui.show} ${name}`);
    });
    status.textContent = '';
    updateToggle();
  }

  slider.querySelector('.hero-slider-prev').addEventListener('click', () => show(requested - 1, true));
  slider.querySelector('.hero-slider-next').addEventListener('click', () => show(requested + 1, true));
  dots.forEach((dot, i) => dot.addEventListener('click', () => show(i, true)));
  toggle.addEventListener('click', () => {
    userPaused = !userPaused;
    updateToggle();
    schedule();
  });
  slider.addEventListener('focusin', event => { if (event.target !== toggle) pause(); });
  slider.addEventListener('pointerenter', event => {
    if (event.pointerType !== 'mouse') return;
    hovered = true;
    schedule();
  });
  slider.addEventListener('pointerleave', () => { hovered = false; schedule(); });
  slider.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = requested + (language === 'ar' ? -1 : 1);
    if (event.key === 'ArrowLeft') next = requested + (language === 'ar' ? 1 : -1);
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = slides.length - 1;
    if (next !== undefined) { event.preventDefault(); show(next, true); }
  });
  slider.addEventListener('touchstart', event => {
    if (event.touches.length !== 1) { touchStart = null; return; }
    touchStart = {x: event.touches[0].clientX, y: event.touches[0].clientY};
    pause();
  }, {passive: true});
  slider.addEventListener('touchend', event => {
    if (!touchStart || !event.changedTouches.length) return;
    const dx = event.changedTouches[0].clientX - touchStart.x;
    const dy = event.changedTouches[0].clientY - touchStart.y;
    touchStart = null;
    if (Math.abs(dx) < 45 || Math.abs(dx) <= Math.abs(dy)) return;
    const step = dx < 0 ? 1 : -1;
    show(requested + (language === 'ar' ? -step : step), true);
  }, {passive: true});
  slider.addEventListener('touchcancel', () => { touchStart = null; }, {passive: true});
  document.addEventListener('visibilitychange', schedule);
  reducedMotion.addEventListener('change', () => { if (reducedMotion.matches) pause(); });
  site.addEventListener('talya:languagechange', event => {
    language = event.detail.language === 'ar' ? 'ar' : 'en';
    translate();
  });
  translate();
  slider.dataset.activeDoctor = profiles[current].id;
  schedule();
})();
