// Read-only local SEO/layout checks; no booking is submitted and no message sent.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {base, playwright} = require('./browser_support.cjs');
const engineName = process.env.TALYA_BROWSER || 'chromium';
const widths = engineName === 'chromium' ? [360, 375, 390, 430, 768, 1024, 1440] : [390, 1440];
const directory = process.env.TALYA_SEO_REPORT_DIR;
const pages = ['', '/doctors/dr-mehira-fadl', '/doctors/dr-farouq-ejami', '/services/general-medicine', '/services/dental', '/contact'];

async function localRequests(context) {
  await context.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== base) return route.abort();
    assert.ok(['GET', 'HEAD'].includes(request.method()), 'Read-only browser verification');
    // WebKit and Python do not resolve *.localhost on every development host.
    url.hostname = '127.0.0.1';
    const response = await route.fetch({url: url.toString(), headers: {...request.headers(), host: 'talya.localhost:8000'}});
    await route.fulfill({response});
  });
}

(async () => {
  if (directory) fs.mkdirSync(directory, {recursive: true});
  const browser = await playwright[engineName].launch({headless: true});
  const results = [];
  try {
    for (const width of widths) for (const language of ['en', 'ar']) for (const suffix of pages) {
      const context = await browser.newContext({viewport: {width, height: 1000}, reducedMotion: 'reduce'});
      try {
        await localRequests(context);
        // A stale language preference must never override a crawlable URL.
        await context.addInitScript(lang => {
          localStorage.setItem('talya-language', lang === 'ar' ? 'en' : 'ar');
          window.seoLayoutShift = 0;
          try {
            new PerformanceObserver(list => {
              for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.seoLayoutShift += entry.value;
            }).observe({type: 'layout-shift', buffered: true});
          } catch (_) { /* WebKit does not expose every performance entry type. */ }
        }, language);
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const url = `${base}/${language}${suffix}`;
        const response = await page.goto(url, {waitUntil: 'networkidle'});
        assert.equal(response.status(), 200);
        await page.evaluate(() => { for (const image of document.images) image.loading = 'eager'; });
        await page.waitForFunction(() => [...document.querySelectorAll('.talya-site img')].every(i => i.complete));
        const state = await page.evaluate(() => ({
          language: document.documentElement.lang,
          direction: document.documentElement.dir,
          siteLanguage: document.querySelector('.talya-site').lang,
          title: document.title,
          h1: document.querySelector('h1').textContent.trim(),
          overflow: document.documentElement.scrollWidth > innerWidth,
          broken: [...document.querySelectorAll('.talya-site img')].filter(i => !i.naturalWidth).map(i => i.getAttribute('src')),
          whatsapp: [...document.querySelectorAll('a[href*="wa.me/"]')].map(a => a.href),
          cls: window.seoLayoutShift,
        }));
        assert.equal(state.language, language);
        assert.equal(state.siteLanguage, language);
        assert.equal(state.direction, language === 'ar' ? 'rtl' : 'ltr');
        assert.equal(state.overflow, false, `${url} at ${width}px`);
        assert.deepEqual(state.broken, []);
        assert.ok(state.whatsapp.every(href => href === 'https://wa.me/971588698578'));
        assert.deepEqual(errors, []);
        if (engineName === 'chromium') assert.ok(state.cls <= 0.1, `Initial local layout shift ${state.cls} at ${url} ${width}px`);
        assert.equal(await page.locator('meta[name=description]').count(), 1);
        assert.equal(await page.locator('link[rel=canonical]').count(), 1);
        if (!suffix) {
          assert.equal(await page.locator('.doctor-info h3 a').count(), 2);
          assert.equal(await page.locator('#booking-form').count(), 1);
          const expected = ['farouq', 'mehira'];
          for (let i = 0; i < 2; i++) {
            await page.locator('.hero-slider-dot').nth(i).click();
            await page.waitForFunction(doctor => document.querySelector('.hero-slider').dataset.activeDoctor === doctor, expected[i]);
            const identity = await page.locator('.hero-slide.is-active').evaluate(slide => ({
              id: slide.dataset.doctor, name: slide.querySelector('b').textContent,
              alt: slide.querySelector('img').alt, src: new URL(slide.querySelector('img').currentSrc).pathname,
            }));
            assert.equal(identity.name, identity.alt);
            assert.ok(identity.src.endsWith(i === 0 ? '/dr-farouq.webp' : '/dr-mehira-original.webp'));
          }
          if (width <= 860) {
            const geometry = await page.evaluate(() => {
              const rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {top: r.top, bottom: r.bottom, left: r.left, width: r.width};
              };
              return {portrait: rect('.hero-slide.is-active .hero-portrait'), badge: rect('.hero-slide.is-active .doctor-badge'), controls: rect('.hero-slider-controls'), stats: rect('.trust-row')};
            });
            assert.ok(geometry.controls.top >= geometry.portrait.bottom - 1);
            assert.ok(geometry.controls.top >= geometry.badge.bottom);
            assert.ok(geometry.stats.top > geometry.controls.bottom);
            assert.ok(Math.abs(geometry.controls.left + geometry.controls.width / 2 - width / 2) < 3);
          }
        } else if (suffix.startsWith('/doctors/')) {
          const key = suffix.includes('mehira') ? 'mehira' : 'farouq';
          assert.ok(await page.locator(`a[href="/${language}?doctor=${key}#appointment"]`).count());
        } else if (suffix === '/services/dental') {
          assert.equal(await page.locator('.service-prices tbody tr').count(), 9);
          assert.equal(await page.locator('.service-prices bdi').count(), 2);
        } else if (suffix === '/services/general-medicine') {
          assert.ok(await page.locator(`a[href="/${language}?doctor=mehira#appointment"]`).count());
        } else {
          assert.ok(await page.locator('a[href^="https://maps.app.goo.gl/"]').count());
        }
        if (directory && [390, 1440].includes(width)) {
          await page.screenshot({path: path.join(directory, `after-${engineName}-${language}-${suffix ? suffix.split('/').pop() : 'home'}-${width}.png`), fullPage: true});
        }
        results.push({browser: engineName, width, language, path: `/${language}${suffix}`, status: 'PASS', layout_shift_local_lab: state.cls});
        console.log(engineName, width, language, suffix || '/home', 'PASS');
      } finally { await context.close(); }
    }
    // Crawlability must survive JavaScript being completely disabled.
    const noJs = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 900}});
    try {
      await localRequests(noJs);
      for (const language of ['en', 'ar']) for (const suffix of pages) {
        const page = await noJs.newPage();
        await page.goto(`${base}/${language}${suffix}`, {waitUntil: 'networkidle'});
        assert.ok((await page.locator('h1').innerText()).trim());
        assert.equal(await page.locator('html').getAttribute('lang'), language);
        const alternate = await page.locator('.language-switch').getAttribute('href');
        assert.ok(alternate.startsWith(language === 'en' ? '/ar' : '/en'));
        if (!suffix) assert.equal(await page.locator('.doctor-info h3 a').count(), 2);
        await page.close();
      }
    } finally { await noJs.close(); }
    console.log(engineName, '12 no-JavaScript page checks PASS');
    if (directory) fs.writeFileSync(path.join(directory, `seo-${engineName}-results.json`), JSON.stringify(results, null, 2) + '\n');
    console.log('TOTAL', engineName, results.length, 'responsive checks PASS');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
