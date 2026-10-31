// TALYA_PLAYWRIGHT_PATH=/absolute/path/to/playwright TALYA_BROWSER=webkit node talya/tests/hero_slider.browser.cjs
// Optional TALYA_BASE_URL can target a read-only cloud page. No bookings are submitted.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
let playwright;
if (process.env.TALYA_PLAYWRIGHT_PATH) {
  playwright = require(process.env.TALYA_PLAYWRIGHT_PATH);
} else {
  // Reuse the Bench's browser-test dependency, without adding a carousel/build dependency.
  try { playwright = require('playwright'); }
  catch (_) { playwright = createRequire(path.resolve(__dirname, '../../../pos_next/package.json'))('playwright'); }
}
const base = process.env.TALYA_BASE_URL || 'http://talya.localhost:8000/';
const engine = process.env.TALYA_BROWSER || 'chromium';
const portraits = ['dr-farouq.png', 'dr-mehira-original.webp'];

async function open(browser, options = {}) {
  const page = await browser.newPage({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, ...options});
  page.setDefaultTimeout(10000);
  page.errors = [];
  page.on('pageerror', error => page.errors.push(error.message));
  await page.clock.install();
  return page;
}

async function load(page) {
  await page.goto(base, {waitUntil: 'networkidle'});
  await page.locator('.hero-slider[data-initialized="true"]').waitFor();
  await page.locator('.hero-slide.is-active .hero-portrait').evaluate(image => image.decode());
}

async function assertIdentity(page, index, language = 'en') {
  const actual = await page.locator('.hero-slider').evaluate(slider => {
    const visible = [...slider.querySelectorAll('.hero-slide')].filter(slide => {
      const css = getComputedStyle(slide);
      return css.display !== 'none' && css.visibility !== 'hidden' && Number(css.opacity) > 0;
    });
    return visible.map(slide => ({
      id: slide.dataset.doctor, active: slide.classList.contains('is-active'),
      accessible: slide.getAttribute('aria-hidden'), inert: slide.inert,
      image: new URL(slide.querySelector('img').currentSrc).pathname.split('/').pop(),
      loaded: slide.querySelector('img').complete && slide.querySelector('img').naturalWidth > 0,
      name: slide.querySelector('b').textContent,
      specialty: slide.querySelector('small').textContent,
    }));
  });
  const names = language === 'en' ? ['Dr. Farouq Ejami', 'Dr. Mehira Fadl'] : ['د. فاروق عجيمي', 'د. مهيرة فضل'];
  const specialties = language === 'en' ? ['Dentist', 'General Practitioner'] : ['طبيب أسنان', 'طبيبة عامة'];
  assert.deepEqual(actual, [{id: ['farouq', 'mehira'][index], active: true, accessible: 'false', inert: false,
    image: portraits[index], loaded: true, name: names[index], specialty: specialties[index]}]);
}

async function monitorFrames(page) {
  await page.evaluate(() => {
    window.heroPaintFailures = [];
    function sample() {
      const visible = [...document.querySelectorAll('.hero-slide')].filter(slide => {
        const css = getComputedStyle(slide);
        return css.display !== 'none' && css.visibility !== 'hidden' && +css.opacity > 0;
      });
      if (visible.length !== 1) window.heroPaintFailures.push('Expected one painted identity, got ' + visible.length);
      requestAnimationFrame(sample);
    }
    requestAnimationFrame(sample);
  });
}

async function rotations(browser) {
  for (const width of [360, 375, 390, 430, 768, 1024, 1440]) {
    const page = await open(browser, {viewport: {width, height: 900}, isMobile: width < 768});
    try {
      await load(page);
      await page.locator('.hero-slide img').evaluateAll(images => Promise.all(images.map(i => i.decode())));
      const identities = await page.locator('.hero-slide').evaluateAll(slides => slides.map(s => s.dataset.doctor));
      assert.equal(new Set(identities).size, 2);
      await monitorFrames(page);
      const geometry = await page.locator('.hero').boundingBox();
      await assertIdentity(page, 0);
      for (let i = 0; i < 10; i++) { // Five complete Farouq -> Mehira -> Farouq cycles.
        await page.clock.fastForward(6000);
        await page.clock.runFor(750);
        await assertIdentity(page, (i + 1) % 2);
      }
      assert.deepEqual(await page.locator('.hero').boundingBox(), geometry);
      await page.click('.hero-slider-next');
      await page.clock.runFor(16);
      await assertIdentity(page, 1);
      await page.clock.runFor(150);
      await assertIdentity(page, 1); // Catches the original overlapping opacity transition.
      await page.click('.language-switch');
      await assertIdentity(page, 1, 'ar');
      await page.click('.hero-slider-prev');
      await assertIdentity(page, 0, 'ar');
      await page.locator('.hero-slider-dot').nth(1).click();
      await assertIdentity(page, 1, 'ar');
      await page.click('.language-switch');
      await assertIdentity(page, 1);
      await page.evaluate(() => {
        for (let i = 0; i < 21; i++) document.querySelector('.hero-slider-next').click();
      });
      await assertIdentity(page, 0);
      await page.clock.runFor(750);
      await assertIdentity(page, 0);
      await page.clock.fastForward(12000);
      await assertIdentity(page, 0); // Manual navigation stays paused.
      await page.locator('.hero-slider').dispatchEvent('touchstart', {touches: [{identifier: 1, clientX: 280, clientY: 600}]});
      await page.locator('.hero-slider').dispatchEvent('touchend', {changedTouches: [{identifier: 1, clientX: 100, clientY: 605}]});
      await assertIdentity(page, 1);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.deepEqual(await page.evaluate(() => window.heroPaintFailures), []);
      assert.deepEqual(page.errors, []);
      console.log(`${engine} ${width}px: five cycles, exclusive painting, matched identities, rapid controls, bilingual text, swipe and stable layout PASS`);
    } finally { await page.close(); }
  }
}

async function loadingAndTimers(browser) {
  for (const failure of [false, true]) {
    const page = await open(browser);
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    try {
      // The first complete identity stays visible while the other portrait is pending/failed.
      await page.route('**/dr-mehira-original.webp*', async route => {
        await gate;
        if (failure) await route.abort(); else await route.continue();
      });
      await page.goto(base, {waitUntil: 'domcontentloaded'});
      await page.locator('.hero-slider[data-initialized="true"]').waitFor();
      await page.locator('.hero-slide.is-active img').evaluate(i => i.decode());
      await page.clock.fastForward(6100);
      await assertIdentity(page, 0);
      await page.locator('.hero-slider-dot').nth(1).click();
      await page.click('.hero-slider-prev');
      await page.clock.runFor(16);
      release();
      if (!failure) await page.locator('.hero-slide-mehira img').evaluate(i => i.decode());
      else await page.waitForFunction(() => document.querySelector('.hero-slide-mehira img').complete);
      await assertIdentity(page, 0); // A stale decoded callback must not win.
      await page.click('.hero-slider-next');
      await assertIdentity(page, failure ? 0 : 1);
      await page.click('.language-switch');
      await assertIdentity(page, failure ? 0 : 1, 'ar');
      console.log(`${engine}: ${failure ? 'failed' : 'delayed'} image, stale callbacks and language change PASS`);
    } finally { release(); await page.close(); }
  }

  const page = await open(browser);
  try {
    await load(page);
    await page.locator('.hero-slide-mehira img').evaluate(i => i.decode());
    await page.evaluate(() => {
      window.testHidden = true;
      Object.defineProperty(document, 'hidden', {configurable: true, get: () => window.testHidden});
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await page.clock.fastForward(18000);
    await assertIdentity(page, 0);
    await page.evaluate(() => { window.testHidden = false; document.dispatchEvent(new Event('visibilitychange')); });
    await page.clock.fastForward(6100);
    await assertIdentity(page, 1);
    // Evaluating the script twice must not create a second timer or event listeners.
    await page.addScriptTag({content: fs.readFileSync(path.join(__dirname, '../public/js/hero-slider.js'), 'utf8')});
    await page.clock.fastForward(6100);
    await assertIdentity(page, 0);
    console.log(`${engine}: background/resume and duplicate-initialization guard PASS`);
  } finally { await page.close(); }
}

(async () => {
  const browser = await playwright[engine].launch();
  try { await rotations(browser); await loadingAndTimers(browser); }
  finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
