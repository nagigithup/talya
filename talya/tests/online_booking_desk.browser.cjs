/* Real Frappe controls with synthetic API fixtures. No sessions, DB writes or messages. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {app,bench,base,playwright}=require('./browser_support.cjs');
const source=fs.readFileSync(path.join(app,'talya/public/js/talya_online_booking.js'),'utf8');
const schema=JSON.parse(fs.readFileSync(path.join(app,'talya/talya/doctype/talya_online_booking/talya_online_booking.json'),'utf8'));
const cataloguePath=JSON.stringify(path.join(app,'talya/translations/ar.csv'));
const messages=JSON.parse(execFileSync(path.join(bench,'env/bin/python'),['-c',
  `import csv,json;print(json.dumps(dict(csv.reader(open(${cataloguePath})))))`],{encoding:'utf8'}));
const artifacts=process.env.TALYA_ARTIFACTS || '/tmp/talya-online-booking-desk';
fs.mkdirSync(artifacts,{recursive:true});

(async()=>{
  const engine=process.env.TALYA_BROWSER || 'chromium';
  const browser=await playwright[engine].launch({headless:true});
  try {
    const widths=process.env.TALYA_TEST_WIDTHS ? process.env.TALYA_TEST_WIDTHS.split(',').map(Number) : [360,375,390,430,768,1024,1440];
    for(const lang of ['en','ar']) for(const width of widths) {
      const page=await browser.newPage({viewport:{width,height:1000}});
      page.setDefaultTimeout(15000);
      const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
      try {
        // Login supplies Frappe's actual dialog, controls and Layout to a Guest;
        // every workflow request below is intercepted with explicit fixtures.
        await page.goto(base+'/login?_lang='+lang,{waitUntil:'networkidle'});
        await page.evaluate(()=>frappe.require('controls.bundle.js'));
        const cssDir=path.join(bench,'sites/assets/frappe/dist',lang==='ar'?'css-rtl':'css');
        const cssFile=fs.readdirSync(cssDir).find(n=>/^desk\.bundle\.[^.]+\.css$/.test(n));
        await page.addStyleTag({path:path.join(cssDir,cssFile)});
        await page.route('**/api/method/**',route=>{
          const url=new URL(route.request().url());
          const args=route.request().method()==='POST' ? new URLSearchParams(route.request().postData()) : url.searchParams;
          if(url.pathname.includes('validate_link')) return route.fulfill({json:{message:{name:args.get('docname') || 'Other'}}});
          if(url.pathname.endsWith('get_link_title')) return route.fulfill({json:{message:url.searchParams.get('docname') || 'Synthetic'}});
          return route.fulfill({json:{message:[]}});
        });
        await page.evaluate(({schema,source,lang,messages})=>{
          document.documentElement.dir=lang==='ar'?'rtl':'ltr';
          document.documentElement.lang=lang;
          document.body.dataset.route='Form/Talya Online Booking/SYNTHETIC-BOOKING';
          document.body.style.cssText='display:block;width:100%;padding:12px;';
          document.body.innerHTML='<main style="width:100%;min-width:0;max-width:1180px;margin:auto"><div id="fixture-toolbar"></div><div id="fixture-form"></div></main><div id="modals"></div>';
          frappe._messages=lang==='ar'?messages:{};
          frappe.ui.form.on=(doctype,handlers)=>{window.bookingHandlers=handlers;};
          const originalCall=frappe.call;
          const context={can_create:true,verified:false,defaults:{first_name:'Synthetic family member',mobile:'+12025550123',email:'synthetic@example.invalid'},
            patient_fields:[{fieldname:'first_name',fieldtype:'Data',label:__('First Name'),reqd:1},
              {fieldname:'sex',fieldtype:'Select',label:__('Gender'),options:'\nOther',reqd:1},
              {fieldname:'mobile',fieldtype:'Data',label:__('Mobile'),reqd:0},{fieldname:'email',fieldtype:'Data',label:__('Email'),reqd:0}],
            matches:[{name:'SYNTHETIC-PATIENT-A',patient_name:'Synthetic first family member',dob:'1990-01-02',sex:'Other',mobile:'+12025550123',phone_match:true},
              {name:'SYNTHETIC-PATIENT-B',patient_name:'Synthetic second family member',dob:'2000-02-03',sex:'Other',mobile:'+12025550123',phone_match:true}]};
          frappe.call=options=>{
            let message;
            if(options.method==='talya.online_booking.patient_context') message=context;
            else if(options.method==='talya.online_booking.visit_options') message={types:[{name:'SYNTHETIC-TYPE',default_duration:30}],service_units:['SYNTHETIC-ROOM'],default_type:'SYNTHETIC-TYPE',verified:false,publicly_linked:Boolean(window.bookingForm?.doc.linked_patient)};
            else if(options.method==='talya.internal_booking.slots') message={slots:[{time:'11:00',end_time:'11:30',service_unit:'SYNTHETIC-ROOM',duration:30}],duration:30};
            else if(options.method.includes('validate_link')) message={name:options.args.docname};
            else if(options.method.includes('get_link_title')) message=options.args.docname;
            else return originalCall(options);
            options.callback?.({message});
            return Promise.resolve({message});
          };
          new Function(source)();
          const fields=schema.field_order.map(name=>({...schema.fields.find(f=>f.fieldname===name)}));
          window.bookingGroup=new frappe.ui.FieldGroup({fields,body:$('#fixture-form')});bookingGroup.make();
          const doc={doctype:'Talya Online Booking',name:'SYNTHETIC-BOOKING',booking_status:'Pending',modified:'2030-01-01 09:00:00',
            patient_name:'Synthetic family member',mobile_number:'+12025550123',healthcare_practitioner:'SYNTHETIC-DOCTOR',medical_department:'SYNTHETIC-DEPARTMENT',
            preferred_date:'2030-01-02',preferred_time:'11:00:00',appointment_type:'SYNTHETIC-TYPE',service_unit:'SYNTHETIC-ROOM',consent_accepted:1};
          window.capturedBookingCalls=[];
          window.bookingForm={doc,fields_dict:bookingGroup.fields_dict,is_new:()=>false,is_dirty:()=>false,
            page:{inner_toolbar:$('#fixture-toolbar')},save:async()=>{},set_query:()=>{},
            set_df_property:(name,key,value)=>{bookingGroup.fields_dict[name].df[key]=value;bookingGroup.fields_dict[name].refresh();},
            set_value:async (field,value)=>{const values=typeof field==='object'?field:{[field]:value};Object.assign(doc,values);await bookingGroup.set_values(values);},
            add_custom_button:(label,click)=>$('<button class="btn btn-default btn-sm" type="button">').text(label).on('click',click).appendTo('#fixture-toolbar'),
            reload_doc:async()=>{},call:async(method,args)=>{capturedBookingCalls.push({method,args});return {message:'SYNTHETIC-APPOINTMENT'};}};
          frappe.show_alert=()=>{};
        },{schema,source,lang,messages});
        await page.evaluate(async()=>{
          const bounded=(promise,label)=>new Promise((resolve,reject)=>{
            const timer=setTimeout(()=>reject(Error('Fixture stalled: '+label)),4000);
            promise.then(value=>{clearTimeout(timer);resolve(value);},error=>{clearTimeout(timer);reject(error);});
          });
          for(const [field,value] of Object.entries(bookingForm.doc)) await bounded(bookingGroup.set_value(field,value),field);
          await bounded(bookingHandlers.refresh(bookingForm),'refresh');
        });
        const columns=await page.locator('[data-fieldname=contact_section] > .section-body > .form-column').evaluateAll(elements=>elements.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));
        assert.equal(await page.locator('.msgprint-dialog:visible').count(),0);
        assert.equal(columns.length,3);
        if(width>=1024) assert.equal(new Set(columns.map(c=>c.y)).size,1);
        else if(width>=768) assert.equal(new Set(columns.map(c=>c.y)).size,2);
        else assert.equal(new Set(columns.map(c=>c.y)).size,3);
        if([390,1440].includes(width)) await page.locator('main').screenshot({path:`${artifacts}/${engine}-${lang}-${width}-form.png`});
        await page.evaluate(()=>talya.booking_desk.find_patient(bookingForm));
        await page.locator('.talya-patient-match').first().waitFor();
        await page.waitForFunction(()=>bookingForm.__talya_patient_dialog.display);
        assert.equal(await page.locator('.talya-patient-match').count(),2);
        assert.equal(await page.evaluate(()=>bookingForm.__talya_patient_dialog.get_value('patient') || ''),'');
        await page.evaluate(async()=>{
          const d=bookingForm.__talya_patient_dialog;
          await d.set_value('patient','SYNTHETIC-PATIENT-A');await d.set_value('identity_verified',1);
          await d.set_value('patient','SYNTHETIC-PATIENT-B');
        });
        assert.equal(await page.evaluate(()=>bookingForm.__talya_patient_dialog.get_value('identity_verified')),0);
        await page.evaluate(()=>bookingForm.__talya_patient_dialog.set_value('identity_verified',1));
        await page.evaluate(()=>{const button=bookingForm.__talya_patient_dialog.get_primary_btn();button.trigger('click');button.trigger('click');});
        await page.waitForFunction(()=>capturedBookingCalls.length===1);
        assert.equal(await page.evaluate(()=>capturedBookingCalls[0].args.patient),'SYNTHETIC-PATIENT-B');
        await page.waitForFunction(()=>getComputedStyle(bookingForm.__talya_patient_dialog.$wrapper[0]).display==='none');
        await page.evaluate(async()=>{
          bookingForm.doc.linked_patient='SYNTHETIC-PATIENT-B';
          $('#fixture-toolbar').empty();
          await bookingHandlers.refresh(bookingForm);
          frappe.confirm=(_message,callback)=>callback();
          $('#fixture-toolbar button').filter((_,button)=>button.textContent===__('Confirm & Create Appointment')).trigger('click');
        });
        await page.waitForFunction(()=>capturedBookingCalls.length===2 && !bookingForm.__talya_confirm_busy);
        assert.equal(await page.evaluate(()=>capturedBookingCalls[1].method),'confirm_booking');
        assert.equal(await page.evaluate(()=>Boolean(capturedBookingCalls[1].args.patient_data)),false);
        await page.evaluate(()=>{bookingForm.doc.linked_patient=null;});
        await page.evaluate(async()=>{await talya.booking_desk.find_patient(bookingForm);await bookingForm.__talya_patient_dialog.set_value('mode','new');});
        await page.waitForFunction(()=>bookingForm.__talya_patient_dialog.display);
        assert.equal(await page.evaluate(()=>bookingForm.__talya_patient_dialog.get_value('new_first_name') || ''),'');
        await page.evaluate(()=>bookingForm.__talya_patient_dialog.set_value('identity_verified',1));
        assert.equal(await page.evaluate(()=>bookingForm.__talya_patient_dialog.get_value('new_first_name')),'Synthetic family member');
        assert.equal(await page.evaluate(()=>bookingForm.__talya_patient_dialog.get_value('new_sex') || ''),'');
        assert.equal(await page.locator('.modal.show [data-fieldname=new_mobile] .control-value').evaluate(e=>getComputedStyle(e).direction),'ltr');
        await page.evaluate(async()=>{const d=bookingForm.__talya_patient_dialog;await d.set_value('new_sex','Other');await d.set_value('reviewed_matches',1);});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
        if([390,1440].includes(width)) await page.locator('.modal.show .modal-dialog').screenshot({path:`${artifacts}/${engine}-${lang}-${width}-patient.png`});
        await page.evaluate(()=>bookingForm.__talya_patient_dialog.get_primary_btn().trigger('click'));
        await page.waitForFunction(()=>capturedBookingCalls.length===3);
        const result=await page.evaluate(()=>capturedBookingCalls[2]);
        assert.equal(result.args.patient_data.first_name,'Synthetic family member');
        assert.equal(result.args.patient_data.sex,'Other');assert.equal(result.args.reviewed_matches,1);
        assert.equal(result.args.identity_verified,1);assert(!('whatsapp_consent' in result.args));
        assert.deepEqual(errors,[]);
        console.log(engine,lang,width,'3/2/1 columns, shared-phone selection, verification reset and new-Patient confirmation PASS');
      } finally {await page.close();}
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
