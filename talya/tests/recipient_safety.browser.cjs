/* Actual reception template/assets with synthetic API fixtures; no database writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { app, bench, base, playwright } = require('./browser_support.cjs');
const artifacts = process.env.TALYA_ARTIFACTS || '/tmp/talya-p0-browser';
const engine = process.env.TALYA_BROWSER || 'chromium';
fs.mkdirSync(artifacts, { recursive: true });

// Render the real template without creating a staff session or invoking DB hooks.
const pages = JSON.parse(execFileSync(path.join(bench, 'env/bin/python'), ['-c', `
import csv, json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from talya.inquiry_labels import LABELS
app = Path(${JSON.stringify(app)})
catalogue = dict(csv.reader((app / 'talya/translations/ar.csv').open()))
template = Environment(loader=FileSystemLoader(app / 'talya/www'), autoescape=select_autoescape()).get_template('patient_inquiries.html')
print(json.dumps({lang: template.render(language=lang, direction='rtl' if lang == 'ar' else 'ltr', labels={k: catalogue.get(k, k) if lang == 'ar' else k for k in LABELS}, csrf_token='fixture', sitename='talya.localhost', socket_port=9000, development=False, manager=False, versions={'css':'fixture','js':'fixture'}) for lang in ['en', 'ar']}))
`], { cwd: bench, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } }));

(async () => {
  const browser = await playwright[engine].launch({ headless: true });
  try {
    for (const lang of ['ar', 'en']) {
      for (const width of [360, 375, 390, 430, 768, 1024, 1440]) {
        const page = await browser.newPage({ viewport: { width, height: 900 } });
        page.setDefaultTimeout(10000);
        const errors = [], posts = [];
        page.on('pageerror', e => errors.push(e.message));
        const doc = { name: 'SYNTHETIC-P0', patient_name: 'Synthetic P0 Contact', mobile_number: '+12025550123', source: 'WhatsApp', status: 'New', linked_patient: 'SYNTHETIC-PATIENT-A', preferred_date: '2030-01-02' };
        await page.route('**/*', async route => {
          const request = route.request(), url = new URL(request.url());
          assert.equal(url.origin, base, 'No external requests allowed');
          if (url.pathname === '/patient_inquiries') return route.fulfill({ contentType: 'text/html', body: pages[lang] });
          if (url.pathname.startsWith('/assets/talya/')) {
            const file = path.join(app, 'talya/public', url.pathname.slice('/assets/talya/'.length));
            return route.fulfill({ path: file });
          }
          if (url.pathname.startsWith('/assets/frappe/')) return route.fulfill({ contentType: 'text/javascript', body: '' });
          if (url.pathname.startsWith('/api/method/')) {
            const method = url.pathname.split('.').at(-1);
            const args = request.method() === 'POST' ? request.postDataJSON() : Object.fromEntries(url.searchParams);
            if (request.method() === 'POST') posts.push({ method, args });
            const lookup = { 'Healthcare Practitioner': [{ name: 'SYNTHETIC-DOCTOR' }], 'Appointment Type': [{ name: 'SYNTHETIC-TYPE' }], Gender: [{ name: 'Other' }], Patient: [{ name: 'SYNTHETIC-PATIENT-A' }, { name: 'SYNTHETIC-PATIENT-B' }] };
            let result;
            if (method === 'list_inquiries') result = [doc];
            else if (method === 'get_settings') result = { settings: { country_calling_code: '971' }, integration: { configured: false }, templates: [] };
            else if (method === 'lookup') result = lookup[args.doctype] || [];
            else if (method === 'patient_context') result = {matches:[{name:'SYNTHETIC-PATIENT-A',patient_name:'Synthetic A',mobile:'+12025550123',phone_match:true},{name:'SYNTHETIC-PATIENT-B',patient_name:'Synthetic B',mobile:'+12025550123',phone_match:true}],more_matches:false,identity_search_available:false,patient_fields:[{fieldname:'first_name',fieldtype:'Data',label:'First Name',reqd:1},{fieldname:'sex',fieldtype:'Link',label:'Gender',reqd:1},{fieldname:'mobile',fieldtype:'Data',label:'Mobile',reqd:0}],can_create:true,creation_error:null,verified:Boolean(doc.patient_verified_at),defaults:{first_name:doc.patient_name,mobile:doc.mobile_number},visit:{practitioner:'SYNTHETIC-DOCTOR',date:'2030-01-02',time:'09:00',appointment_type:'SYNTHETIC-TYPE',service_unit:'SYNTHETIC-ROOM',locked:false},inquiry_modified:'2030-01-01 08:00:00'};
            else if (method === 'detail') result = { inquiry: doc, integration: { configured: false }, conversation: { messages: [], templates: [], contact_allowed: false, fallback: 'https://wa.me/12025550123' } };
            else if (method === 'verify_patient') {
              assert.equal(args.identity_verified, true);
              assert.equal(args.patient, doc.linked_patient);
              doc.patient_verified_at = '2030-01-01 09:00:00'; result = doc.name;
            } else if (method === 'slot_options') result = {slots:[{time:'09:00',end_time:'09:30',service_unit:'SYNTHETIC-ROOM',duration:30}],service_units:['SYNTHETIC-ROOM'],duration:30};
            else if (method === 'confirm') {
              assert.equal(args.identity_verified, true);
              assert.equal(args.patient, 'SYNTHETIC-PATIENT-A');
              result = 'SYNTHETIC-APPOINTMENT';
            } else throw new Error('Unexpected API call: ' + method);
            return route.fulfill({ json: { message: result } });
          }
          throw new Error('Unexpected request: ' + url.pathname);
        });
        try {
          await page.goto(base + '/patient_inquiries?lang=' + lang);
          await page.locator('[data-open="SYNTHETIC-P0"]').first().click();
          assert.equal(await page.locator('html').getAttribute('dir'), lang === 'ar' ? 'rtl' : 'ltr');
          assert.equal(await page.locator('#detail-dialog [name=mobile_number]').getAttribute('dir'), 'ltr');
          page.once('dialog', d => d.accept());
          await page.locator('#verify-linked-patient').click();
          await page.locator('#verify-linked-patient').waitFor({ state: 'detached' });
          assert.equal(posts.filter(p => p.method === 'verify_patient').length, 1);
          await page.locator('#book-detail').click();
          const identity = page.locator('[name=identity_verified]');
          await identity.waitFor();
          assert.equal(await identity.isChecked(), false);
          assert.equal(await identity.getAttribute('required'), '');
          const label = await identity.locator('..').textContent();
          assert(lang === 'ar' ? /تحققت/.test(label) : /I verified/.test(label));
          await identity.check();
          await page.locator('#booking-form [name=patient][value="SYNTHETIC-PATIENT-B"]').check();
          assert.equal(await identity.isChecked(), false, 'Changing Patient must clear confirmation');
          await page.locator('#booking-form [name=patient][value="SYNTHETIC-PATIENT-A"]').check();
          await page.locator('#booking-form [name=practitioner]').selectOption('SYNTHETIC-DOCTOR');
          await page.locator('#booking-form [name=appointment_type]').selectOption('SYNTHETIC-TYPE');
          await page.locator('#load-slots').click();
          await page.locator('#booking-form [name=slot]').selectOption('0');
          assert.equal(await page.locator('#booking-form [name=end_time]').inputValue(), '09:30');
          await page.locator('#booking-form button[type=submit]').click();
          assert.equal(posts.filter(p => p.method === 'confirm').length, 0, 'Unchecked confirmation must block submission');
          await identity.check();
          const overflow = await page.evaluate(() => ({
            page: document.documentElement.scrollWidth > innerWidth + 1,
            dialog: [...document.querySelectorAll('dialog[open]')].some(d => d.scrollWidth > d.clientWidth + 1),
          }));
          assert.deepEqual(overflow, { page: false, dialog: false });
          if ([390, 1440].includes(width)) await page.screenshot({ path: `${artifacts}/${engine}-${lang}-${width}-identity.png` });
          await page.locator('#booking-form button[type=submit]').click();
          await page.locator('#offer-confirmation').waitFor();
          assert.equal(posts.filter(p => p.method === 'confirm').length, 1);
          assert.deepEqual(errors, []);
          console.log(`${engine} ${lang} ${width}: identity confirmation, booking guard, RTL/LTR and overflow PASS`);
        } finally { await page.close(); }
      }
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
