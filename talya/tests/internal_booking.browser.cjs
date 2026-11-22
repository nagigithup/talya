/* Read-only verification of the actual Healthcare dialog and live slot endpoint.
 * Supply a temporary staff session and a fixture with approved practitioner/type
 * IDs. This script never saves appointments or sends messages.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.TALYA_BASE_URL || 'http://talya.localhost:8000';
assert(['http://talya.localhost:8000','https://talya.nvi.frappe.cloud'].includes(base));
const playwright = require(process.env.TALYA_PLAYWRIGHT_PATH || 'playwright');
const session = fs.readFileSync(process.env.TALYA_TEST_SESSION_FILE,'utf8').trim();
const sessions = session.startsWith('{') ? JSON.parse(session) : {en:session,ar:session};
const fixture = JSON.parse(fs.readFileSync(process.env.TALYA_BOOKING_FIXTURE,'utf8'));
const artifacts = process.env.TALYA_ARTIFACTS || '/tmp/talya-internal-booking-browser';
fs.mkdirSync(artifacts,{recursive:true});

(async () => {
  const browser = await playwright[process.env.TALYA_BROWSER || 'chromium'].launch({headless:true});
  try {
    for (const lang of ['en','ar']) for (const width of [390,1440]) {
      const context = await browser.newContext({viewport:{width,height:1000}});
      await context.addCookies([{name:'sid',value:sessions[lang],url:base,httpOnly:true,secure:base.startsWith('https:')},
        {name:'preferred_language',value:lang,url:base}]);
      const page = await context.newPage(); page.setDefaultTimeout(30000);
      try {
        await page.goto(base + '/desk?_lang=' + lang,{waitUntil:'domcontentloaded'});
        await page.waitForFunction(() => window.frappe?.ui?.Dialog && frappe.boot?.user?.name !== 'Guest');
        assert.equal(await page.locator('html').getAttribute('dir'),lang === 'ar' ? 'rtl' : 'ltr');
        await page.evaluate(async () => {
          await frappe.model.with_doctype('Patient Appointment');
          window.talyaCheckAvailability = new Function(frappe.get_meta('Patient Appointment').__js + '\nreturn check_and_set_availability;')();
          if (!String(window.talyaCheckAvailability).includes('talya.internal_booking.open')) throw Error('Native entry point did not load Talya override');
        });
        for (const doctor of fixture.doctors) {
          await page.evaluate(async ({doctor,date,type}) => {
            const doc={doctype:'Patient Appointment',appointment_for:'Practitioner',patient:null,
              practitioner:doctor.name,department:doctor.department,service_unit:doctor.service_unit,
              appointment_type:type,appointment_date:date};
            window.bookingForm={doc,is_new:()=>true};
            await window.talyaCheckAvailability(window.bookingForm);
          },{doctor,date:fixture.date,type:fixture.short_type});
          const buttons=page.locator('.modal.show [data-talya-slot]');
          const endTime=() => page.evaluate(() => bookingForm.__talya_booking_dialog.get_value('end_time') || '');
          await page.waitForFunction(() => document.querySelectorAll('.modal.show [data-talya-slot]').length === 24);
          assert.deepEqual((await buttons.allTextContents()).map(t=>t.trim()).slice(0,3),['11:00','11:30','12:00']);
          assert.equal((await buttons.last().textContent()).trim(),'22:30');
          await buttons.last().click();
          assert.equal(await endTime(),'23:00');
          await page.evaluate(async type => bookingForm.__talya_booking_dialog.set_value('appointment_type',type),fixture.long_type);
          await page.waitForFunction(() => document.querySelectorAll('.modal.show [data-talya-slot]').length === 23);
          assert.equal((await buttons.last().textContent()).trim(),'22:00');
          assert.equal(await endTime(),'');
          await buttons.first().click();
          assert.equal(await endTime(),'12:00');
          const overflow=await page.evaluate(() => {
            const m=document.querySelector('.modal.show .modal-dialog');
            return m.getBoundingClientRect().left < -1 || m.getBoundingClientRect().right > innerWidth+1;
          });
          assert.equal(overflow,false);
          await page.locator('.modal.show .modal-dialog').screenshot({path:path.join(artifacts,`${lang}-${width}-${doctor.key}.png`)});
          if (doctor.key === 'farouq' && fixture.blocked_date) {
            await page.evaluate(async date => bookingForm.__talya_booking_dialog.set_value('appointment_date',date),fixture.blocked_date);
            await page.waitForFunction(() => document.querySelector('.modal.show [data-talya-slot]')?.textContent.trim() === '12:00');
            assert.equal(await endTime(),'');
            await page.evaluate(async other => bookingForm.__talya_booking_dialog.set_value('practitioner',other.name),fixture.doctors[1]);
            await page.waitForFunction(() => document.querySelectorAll('.modal.show [data-talya-slot]').length === 23);
            assert.equal(await page.evaluate(() => bookingForm.__talya_booking_dialog.get_value('service_unit')),fixture.doctors[1].service_unit);
          }
          // Exercise the real primary action with an in-memory form adapter.
          // Availability still comes from Healthcare; saving cannot reach HTTP.
          await page.evaluate(() => {
            bookingForm.doc.patient='SYNTHETIC-UI-ONLY';
            bookingForm.set_value=async (field,value) => Object.assign(bookingForm.doc,typeof field === 'object' ? field : {[field]:value});
            bookingForm.enable_save=() => {};
            bookingForm.save=async () => {window.talyaCapturedBooking={...bookingForm.doc};};
          });
          await buttons.first().click();
          await page.getByRole('button',{name:await page.evaluate(() => __('Book')),exact:true}).click();
          const saved=await page.evaluate(() => window.talyaCapturedBooking);
          assert.equal(saved.duration,60); assert.equal(saved.appointment_type,fixture.long_type);
          assert.equal(saved.appointment_time,'11:00');
          await page.evaluate(() => bookingForm.__talya_booking_dialog?.hide());
          await page.locator('.modal.show').waitFor({state:'hidden'});
          console.log(`${lang} ${width} ${doctor.key}: 24/23 starts, final times, end calculation and stale selection PASS`);
        }
      } finally { await context.close(); }
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
