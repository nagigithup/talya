/* Live local manual/import flows; synthetic conversation data tests presentation only. */
const { bench, base, playwright: { chromium, webkit } } = require('./browser_support.cjs');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const session = fs.readFileSync(process.env.TALYA_TEST_SESSION_FILE || '/tmp/talya-inquiries-browser-session','utf8').trim();
const artifacts = process.env.TALYA_ARTIFACTS || '/tmp/talya-inquiry-browser';
fs.mkdirSync(artifacts,{recursive:true});
const inquiryNames = new Set(), files = new Set();

(async () => {
  const engine = process.env.TALYA_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await engine.launch({headless:true});
  const context = await browser.newContext();
  await context.addCookies([{name:'sid',value:session,domain:new URL(base).hostname,path:'/'}]);
  const page = await context.newPage();
  const errors = []; page.on('pageerror',error => errors.push(error.message));
  async function api(method,args = {},post = false) {
    return page.evaluate(async ({method,args,post}) => {
      const conf = JSON.parse(document.querySelector('#talya-config').textContent);
      const url = '/api/method/' + method;
      const r = await fetch(post ? url : url + '?' + new URLSearchParams(args),{method:post?'POST':'GET',headers:{'X-Frappe-CSRF-Token':conf.csrf,...(post?{'Content-Type':'application/json'}:{})},body:post?JSON.stringify(args):undefined});
      const result = await r.json(); if (!r.ok) throw Error(result.exception || r.status); return result.message;
    },{method,args,post});
  }
  async function noOverflow() {
    const overflow = await page.evaluate(() => {
      const dialog = [...document.querySelectorAll('dialog[open]')].at(-1);
      return {document:document.documentElement.scrollWidth > innerWidth + 1,dialog:dialog ? dialog.scrollWidth > dialog.clientWidth + 1 : false};
    });
    assert.deepEqual(overflow,{document:false,dialog:false});
  }
  try {
    await page.goto(base + '/patient_inquiries?lang=en');
    await page.locator('#integration-banner').filter({hasText:'WhatsApp API'}).waitFor();
    await page.locator('#new-button').click();
    await page.locator('#action-dialog [name=patient_name]').fill('Talya Browser Test — synthetic');
    await page.locator('#action-dialog [name=mobile_number]').fill('123');
    await page.locator('#action-dialog button[type=submit]').click();
    await page.locator('#action-dialog .error').filter({hasText:'valid international mobile number'}).waitFor();
    await page.locator('#action-dialog [name=mobile_number]').fill('+12025550123');
    await page.locator('#action-dialog [name=requested_service]').fill('Synthetic general inquiry');
    const saved = page.waitForResponse(r => r.url().includes('talya.inquiries.save_inquiry') && r.request().method() === 'POST');
    await page.locator('#action-dialog button[type=submit]').click();
    const name = (await (await saved).json()).message; inquiryNames.add(name);
    await page.locator('#detail-title').filter({hasText:'Talya Browser Test'}).waitFor();
    await page.locator('#fallback-link').waitFor();
    assert((await page.locator('#fallback-link').getAttribute('href')).startsWith('https://wa.me/12025550123?text='));
    await page.locator('#detail-dialog [name=whatsapp_consent]').check();
    await page.locator('#detail-dialog button[type=submit]').click();
    await page.waitForResponse(r => r.url().includes('talya.inquiries.save_inquiry'));
    await page.locator('#fallback-link').waitFor();
    await page.locator('#detail-dialog [data-close]').click();

    // Real private CSV upload, mapping, validation preview and confirmed import.
    await page.locator('#import-button').click();
    await page.locator('#upload-form [name=file]').setInputFiles({name:'talya-browser-isolated.csv',mimeType:'text/csv',buffer:Buffer.from('Name,Mobile,Service\nTalya Import Test,+12025550124,General\nTalya Import Test,+12025550124,General\n')});
    const uploaded = page.waitForResponse(r => r.url().includes('/api/method/upload_file'));
    await page.locator('#upload-form button[type=submit]').click();
    files.add((await (await uploaded).json()).message.name);
    await page.locator('#mapping-form').waitFor();
    await page.locator('#mapping-form [name=patient_name]').selectOption('0');
    await page.locator('#mapping-form [name=mobile_number]').selectOption('1');
    await page.locator('#mapping-form [name=requested_service]').selectOption('2');
    await page.locator('#mapping-form button[type=submit]').click();
    await page.locator('#import-preview').filter({hasText:'Duplicate — will be skipped'}).waitFor();
    page.once('dialog',dialog => dialog.accept());
    await page.locator('#confirm-import').click();
    await page.locator('#toast').filter({hasText:'Imported: 1'}).waitFor();
    const imported = await api('talya.inquiries.list_inquiries',{search:'Talya Import Test'});
    imported.forEach(row => inquiryNames.add(row.name)); assert.equal(imported.length,1);
    // Actual local realtime transport, with a synthetic event to this test's own admin session.
    await page.waitForTimeout(1000);
    execFileSync(process.env.TALYA_BENCH_BIN || 'bench',['--site','talya.localhost','execute','frappe.publish_realtime','--kwargs',JSON.stringify({event:'talya_inquiry',message:{incoming:1},user:'Administrator'})],{cwd:bench,env:{...process.env,PATH:path.join(bench,'env/bin') + path.delimiter + process.env.PATH},stdio:'pipe'});
    await page.locator('#toast').filter({hasText:'New incoming WhatsApp message'}).waitFor();

    const live = await api('talya.inquiries.detail',{name});
    // Presentation fixtures only: no Meta account, transport, patient or appointment is created.
    const messages = [
      {name:'mock-1',direction:'Incoming',message:'مرحباً، أريد الاستفسار عن موعد متاح.',status:'Sent',creation:'2026-11-08 09:00'},
      {name:'mock-2',direction:'Outgoing',message:'Welcome to Talya. We can help arrange an appointment.',status:'Delivered',creation:'2026-11-08 09:01'},
      {name:'mock-3',direction:'Incoming',message:'هل يمكنني الحجز غداً؟',status:'Read',creation:'2026-11-08 09:02'},
      {name:'mock-4',direction:'Outgoing',message:'Synthetic transport failure',status:'Failed',error_message:'Mock only — no external message sent.',creation:'2026-11-08 09:03'},
    ];
    await page.route('**/api/method/talya.inquiries.detail?*',route => route.fulfill({json:{message:{...live,integration:{installed:true,configured:true,account:'UI fixture only'},conversation:{...live.conversation,messages,templates:[{name:'mock-template',template_name:'UI fixture confirmation'}]}}}}));
    await page.route('**/api/method/talya.inquiries.lookup?*',route => {
      const dt = new URL(route.request().url()).searchParams.get('doctype');
      const data = { 'Healthcare Practitioner':[{name:'Mock Doctor',label:'UI fixture doctor'}], 'Appointment Type':[{name:'Mock Consultation'}], 'Patient':[{name:'Mock Patient',label:'UI fixture patient'}], 'Gender':[{name:'Other'}] };
      return route.fulfill({json:{message:data[dt] || []}});
    });
    await page.route('**/api/method/talya.inquiries.patient_context?*',r => r.fulfill({json:{message:{matches:[{name:'Mock Patient',patient_name:'UI fixture patient',mobile:'+12025550123',phone_match:true}],more_matches:false,identity_search_available:false,patient_fields:[{fieldname:'first_name',fieldtype:'Data',label:'First Name',reqd:1},{fieldname:'sex',fieldtype:'Link',label:'Gender',reqd:1},{fieldname:'mobile',fieldtype:'Data',label:'Mobile',reqd:0}],can_create:true,creation_error:null,verified:false,defaults:{first_name:'Talya Browser Test — synthetic',mobile:'+12025550123'},visit:{practitioner:'Mock Doctor',date:'2030-01-02',time:'09:00',appointment_type:'Mock Consultation',service_unit:'UI fixture room',locked:false},inquiry_modified:'2026-11-23 00:00:00'}}}));
    await page.route('**/api/method/talya.inquiries.slot_options?*',r => r.fulfill({json:{message:{slots:[{time:'09:00',end_time:'09:30',service_unit:'UI fixture room',duration:30}],service_units:['UI fixture room'],duration:30}}}));
    for (const lang of ['ar','en']) {
      for (const width of [360,375,390,430,768,1024,1440]) {
        await page.setViewportSize({width,height:900});
        await page.goto(base + '/patient_inquiries?lang=' + lang);
        await page.locator('[data-open="'+name+'"]').first().waitFor();
        assert.equal(await page.locator('html').getAttribute('dir'),lang === 'ar' ? 'rtl':'ltr');
        await noOverflow();
        if ([390,1440].includes(width)) await page.screenshot({path:`${artifacts}/${lang}-${width}-list.png`,fullPage:true});
        await page.locator('[data-open="'+name+'"]').first().click();
        await page.locator('#message-form').waitFor();
        assert.equal(await page.locator('.bubble').count(),4);
        assert.equal(await page.locator('#detail-dialog [name=mobile_number]').getAttribute('dir'),'ltr');
        await noOverflow();
        if ([390,1440].includes(width)) {
          if (width === 390) await page.locator('[data-panel=".conversation"]').click();
          await page.waitForTimeout(350);
          await page.screenshot({path:`${artifacts}/${lang}-${width}-conversation.png`});
          if (width === 390) { await page.locator('#detail-dialog').evaluate(el => { el.scrollTop=0; }); }
        }
        await page.locator('#book-detail').click();
        await page.locator('#booking-form').waitFor();
        await page.locator('#booking-form [name=patient][value="Mock Patient"]').check();
        await page.locator('#booking-form [name=practitioner]').selectOption('Mock Doctor');
        await page.locator('#booking-form [name=appointment_type]').selectOption('Mock Consultation');
        await page.locator('#load-slots').click();
        await page.locator('#booking-form [name=slot] option[value="0"]').waitFor({state:'attached'});
        await page.locator('#booking-form [name=slot]').selectOption('0');
        await noOverflow();
        if ([390,1440].includes(width)) await page.screenshot({path:`${artifacts}/${lang}-${width}-booking.png`});
        await page.locator('#action-dialog [data-close]').click();
        await page.locator('#detail-dialog [data-close]').click();
        await page.locator('#settings-button').click();
        await page.locator('#settings-form').waitFor();
        await noOverflow();
        await page.locator('#action-dialog [data-close]').click();
        console.log(`${process.env.TALYA_BROWSER || 'chromium'} ${lang} ${width}: list, conversation, booking layout passed`);
      }
    }
    assert.deepEqual(errors,[]);
    console.log('Real manual inquiry + private CSV import passed; 14 bilingual responsive cases passed; conversation/slot UI data mocked.');
  } finally {
    await page.unrouteAll({behavior:'wait'});
    // Remove only synthetic records created by this test, using normal authorized resource APIs.
    for (const [doctype,names] of [['Talya Patient Inquiry',inquiryNames],['File',files]]) {
      for (const name of names) {
        const status = await page.evaluate(async ({doctype,name}) => {
          const csrf = JSON.parse(document.querySelector('#talya-config').textContent).csrf;
          const response = await fetch('/api/resource/' + encodeURIComponent(doctype) + '/' + encodeURIComponent(name),{method:'DELETE',headers:{'X-Frappe-CSRF-Token':csrf}});
          return response.status;
        },{doctype,name});
        assert.equal(status,202,'Synthetic record cleanup failed: ' + doctype);
      }
    }
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
