// Synthetic browser fixtures only. Every booking POST is intercepted; no DB write.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {base, playwright} = require('./browser_support.cjs');
const fixtures = [
  {id: 'SYNTHETIC-SEO-GP', profile_key: 'mehira', department: 'General Practice', name_en: 'Dr. Mehira Fadl', name_ar: 'د. مهيرة فضل', booking_enabled: true},
  {id: 'SYNTHETIC-SEO-DENTIST', profile_key: 'farouq', department: 'Dentistry', name_en: 'Dr. Farouq Ejami', name_ar: 'د. فاروق عجيمي', booking_enabled: true},
];

(async () => {
  const browser = await playwright.chromium.launch({headless: true});
  const results = [];
  try {
    for (const language of ['en', 'ar']) for (const doctor of fixtures) {
      const context = await browser.newContext({viewport: {width: 390, height: 900}, reducedMotion: 'reduce'});
      const existing = doctor.profile_key === 'mehira';
      const lookupReference = 'synthetic-session-booking-reference';
      let submitted = 0, checkedSlots = 0;
      try {
        await context.route('**/*', async route => {
          const request = route.request();
          const url = new URL(request.url());
          if (url.origin !== base) return route.abort();
          if (url.pathname === '/api/method/talya.api.lookup_patient') {
            const lookup = request.postDataJSON();
            if (lookup.kind === 'mobile') return route.fulfill({json: {message: {status: 'emirates_id'}}});
            assert.equal(lookup.shared_mobile, '+971500000000');
            return route.fulfill({json: {message: {first_name: language === 'ar' ? 'نور' : 'Noor', booking_reference: lookupReference}}});
          }
          if (url.pathname === '/api/method/talya.api.booking_notice') {
            assert.equal(request.postDataJSON().booking_reference, lookupReference);
            return route.fulfill({json: {message: {has_other_booking: true}}});
          }
          if (url.pathname === '/api/method/talya.api.invalidate_patient_lookup') {
            assert.equal(request.postDataJSON().booking_reference, lookupReference);
            return route.fulfill({json: {}});
          }
          if (url.pathname === '/api/method/talya.api.submit_booking') {
            assert.equal(request.method(), 'POST');
            const payload = request.postDataJSON();
            assert.equal(payload.healthcare_practitioner, doctor.id);
            assert.equal(payload.medical_department, doctor.department);
            assert.equal(payload.language, language);
            assert.equal(payload.preferred_time, '16:00');
            assert.equal(payload.consent_accepted, '1');
            assert.equal(payload.whatsapp_consent, undefined);
            assert.equal(payload.patient_mode, existing ? 'existing' : 'new');
            if (existing) {
              assert.equal(payload.booking_reference, lookupReference);
              for (const field of ['first_name', 'mobile_number', 'emirates_id', 'email']) assert.equal(payload[field], undefined);
            }
            submitted++;
            return route.fulfill({json: {message: {booking_reference: 'SYNTHETIC-SEO-ONLY', status: 'Pending'}}});
          }
          // No other mutation can reach the bench or any external service.
          assert.ok(['GET', 'HEAD'].includes(request.method()), 'Unexpected mutating request');
          if (url.pathname === '/api/method/talya.api.get_slots') {
            assert.equal(url.searchParams.get('practitioner'), doctor.id);
            checkedSlots++;
            return route.fulfill({json: {message: {slots: ['16:00', '16:30']}}});
          }
          url.hostname = '127.0.0.1';
          const response = await route.fetch({url: url.toString(), headers: {...request.headers(), host: 'talya.localhost:8000'}});
          if (url.pathname === '/' + language) {
            let body = await response.text();
            assert.ok(body.includes("data-practitioners='[]'"), 'Fixture runner requires the empty local public-practitioner setup');
            body = body.replace("data-practitioners='[]'", "data-practitioners='" + JSON.stringify(fixtures) + "'");
            body = body.replace('data-selected-doctor=""', `data-selected-doctor="${doctor.id}"`);
            return route.fulfill({response, body});
          }
          return route.fulfill({response});
        });
        const page = await context.newPage();
        await page.goto(`${base}/${language}?doctor=${doctor.profile_key}#appointment`, {waitUntil: 'networkidle'});
        assert.equal(await page.locator('#practitioner-select').inputValue(), doctor.id);
        assert.equal(await page.locator('#department-select').inputValue(), doctor.department);
        const alternate = await page.locator('.language-switch').evaluate(link => {
          link.addEventListener('click', event => event.preventDefault(), {once: true});
          link.click();
          return link.href;
        });
        assert.equal(new URL(alternate).searchParams.get('doctor'), doctor.profile_key);
        assert.equal(new URL(alternate).pathname, language === 'en' ? '/ar' : '/en');
        if (existing) {
          await page.locator('[name=patient_mode][value=existing]').check();
          await page.locator('#lookup-value').fill('+971500000000');
          await page.locator('#lookup-patient').click();
          await page.waitForFunction(() => document.querySelector('#lookup-kind').value === 'emirates_id');
          await page.locator('#lookup-value').fill('784-2000-1234567-1');
          await page.locator('#lookup-patient').click();
          await page.locator('#other-booking-notice').waitFor();
          assert.match(await page.locator('#patient-lookup-status').innerText(), language === 'ar' ? /مرحباً، نور/ : /Welcome, Noor/);
          assert.match(await page.locator('#other-booking-notice').innerText(), language === 'ar' ? /طبيب آخر/ : /another doctor/);
        } else {
          await page.locator('[name=patient_mode][value=new]').check();
          await page.locator('[name=first_name]').fill('Synthetic SEO Fixture');
          await page.locator('[name=sex]').selectOption('Other');
          await page.locator('[name=mobile_number]').fill('+971500000000');
          await page.locator('[name=email]').fill('synthetic-seo@example.invalid');
        }
        const date = new Date(Date.now() + 172800000).toISOString().slice(0, 10);
        await page.locator('#preferred-date').fill(date);
        await page.locator('#preferred-date').dispatchEvent('change');
        await page.waitForFunction(() => !!document.querySelector('#preferred-time option[value="16:00"]'));
        await page.locator('#preferred-time').selectOption('16:00');
        await page.locator('[name=consent_accepted]').check();
        await page.locator('#booking-form button[type=submit]').click();
        await page.locator('#form-status.success').waitFor();
        assert.equal(submitted, 1);
        assert.ok(checkedSlots > 0);
        results.push({language, doctor: doctor.profile_key, status: 'PASS', submission: 'intercepted synthetic response', actual_backend_posts: 0});
        console.log('Synthetic booking UI', language, doctor.profile_key, 'PASS; zero backend POSTs');
      } finally { await context.close(); }
    }
    if (process.env.TALYA_SEO_REPORT_DIR) fs.writeFileSync(path.join(process.env.TALYA_SEO_REPORT_DIR, 'seo-booking-fixtures.json'), JSON.stringify(results, null, 2) + '\n');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
