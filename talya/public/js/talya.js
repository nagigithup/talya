(() => {
  const site = document.querySelector('.talya-site');
  if (!site) return;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const dict = {
    ar: {
      menu:'القائمة',home:'الرئيسية',services:'خدماتنا',doctors:'أطباؤنا',book:'احجز موعد',contact:'تواصل معنا',
      eyebrow:'الطب وطب الأسنان في رأس الخيمة',hero_title:'مركز تاليا الطبي',hero_subtitle:'الطب العام وطب الأسنان',hero_description:'رعاية صحية مهنية وإنسانية للأفراد والعائلات.',
      whatsapp:'تواصل عبر واتساب',location:'موقعنا',care_areas:'مجالات رعاية',hero_doctors:'من الأطباء',hero_compassion:'رعاية باهتمام وخصوصية',dentist:'طبيب أسنان',tagline:'صحتك.. ابتسامتك.. أولويتنا',
      our_services:'خدماتنا',care_for_family:'رعاية متكاملة لكل عائلة',services_intro:'رعاية طبية وطب أسنان مركزة، بوضوح واهتمام.',
      dental:'عيادة طب الأسنان',dental_desc:'استشارات ورعاية وقائية وترميمية وتجميلية للأسنان.',dental_one:'الفحوصات والتنظيف والعناية باللثة',dental_two:'الحشوات والترميمات وعلاج الجذور',dental_three:'تجميل الأسنان والتبييض والزراعة',
      family:'الطب العام',family_desc:'استشارات وفحوصات ورعاية صحية مستمرة تتمحور حول المريض والأسرة.',family_one:'الاستشارات العامة والفحوصات الشاملة',family_two:'تشخيص وعلاج الأمراض الشائعة',family_three:'الرعاية الوقائية والمتابعة ومراقبة الحالات',
      lab:'المختبر الطبي',lab_desc:'فحوصات مخبرية وتحقيقات طبية لدعم التشخيص السريري.',lab_one:'الفحوصات المخبرية',lab_two:'التحقيقات الطبية',lab_three:'دعم التشخيص',request_appointment:'اطلب موعداً',
      our_doctors:'أطباؤنا',meet_team:'تعرّف على فريق رعايتك',doctors_intro:'رعاية مهنية تركز على صحتك وراحتك واحتياجاتك الفردية.',
      farouq_name:'د. فاروق عجيمي',farouq_bio:'يقدم رعاية في طب الأسنان العام والتجميلي، تشمل الفحوصات والرعاية الوقائية والترميمات وخطط العلاج مع التركيز على صحة الفم على المدى الطويل.',
      mehira_name:'د. مهيرة فضل',mehira_bio:'طبيبة عامة تقدم رعاية شاملة تتمحور حول المريض، وتشمل الاستشارات الطبية والفحوصات الصحية العامة والرعاية الأسرية والمتابعة.',
      booking_unavailable:'يلزم إعداد الحجز',gp:'طبيبة عامة',appointment_request:'طلب موعد',start_care:'ابدأ خطوتك الأولى نحو رعاية أفضل',booking_intro:'أرسل طلب موعد مفضل. سيتواصل فريقنا معك لتأكيده — إرسال النموذج لا يعني تأكيد الموعد.',
      secure_request:'معالجة آمنة للطلب',schedule_aware:'مواعيد مرتبطة بالجدول',human_confirmation:'تأكيد من فريق الاستقبال',need_help:'هل تحتاج مساعدة؟',book_appointment:'احجز موعد',pending_note:'يبقى الطلب معلقاً حتى يؤكده الاستقبال.',easy:'سريع · سهل · خاص',
      setup_needed:'إعداد الحجز الإلكتروني جارٍ',setup_explainer:'لا يوجد ممارس رعاية صحية معتمد ومفعّل بعد. يرجى الاتصال أو التواصل عبر واتساب.',full_name:'الاسم الكامل',mobile:'رقم الهاتف',email:'البريد الإلكتروني',clinic:'العيادة / التخصص',select_clinic:'اختر العيادة',doctor:'الطبيب',select_doctor:'اختر الطبيب',preferred_date:'التاريخ المفضل',preferred_time:'الوقت المفضل',select_time:'اختر الوقت',choose_doctor_date:'اختر الطبيب والتاريخ لعرض المواعيد المتاحة.',notes:'ملاحظات (اختياري)',notes_placeholder:'أي معلومات تود إبلاغ فريقنا بها...',consent:'أوافق على استخدام مركز تاليا الطبي لهذه البيانات لمعالجة طلبي والتواصل معي بخصوصه.',submit_request:'إرسال طلب الموعد',
      our_location:'موقعنا',visit_talya:'قم بزيارة مركز تاليا الطبي',about_one:'يقدم مركز تاليا الطبي خدمات الرعاية الصحية في رأس الخيمة، بما يشمل الطب العام وطب الأسنان والخدمات المخبرية، مع التركيز على جودة الرعاية وراحة المرضى والاهتمام باحتياجات كل فرد من أفراد الأسرة.',about_two:'نهتم براحة المرضى والرعاية الشخصية وتقديم خدمات صحية ذات جودة للأفراد والعائلات.',address:'رأس الخيمة، النخيل، بالقرب من فندق أكشن، الإمارات العربية المتحدة.',call_us:'اتصل بنا',additional_phone:'هاتف إضافي',email_us:'راسلنا',open_maps:'افتح خرائط Google',privacy:'سياسة الخصوصية',
      no_slots:'لا توجد مواعيد متاحة في هذا التاريخ.',loading_slots:'جارٍ تحميل المواعيد...',submit_success:'تم استلام طلب حجز موعدك بنجاح. سيتواصل معك فريق المركز لتأكيد الموعد.',generic_error:'تعذر إرسال الطلب. يرجى مراجعة البيانات أو التواصل معنا.'
    }
  };
  const en = {};
  $$('[data-i18n]').forEach(el => en[el.dataset.i18n] = el.textContent.trim());
  en.notes_placeholder = 'Anything our team should know...'; en.select_time='Select time'; en.no_slots='No configured slots are available on this date.'; en.loading_slots='Loading availability…'; en.submit_success='Your appointment request has been received successfully. Our team will contact you to confirm your appointment.'; en.generic_error='We could not submit the request. Please review the details or contact us.';
  const translations = { en, ar: dict.ar };
  let lang = localStorage.getItem('talya-language') === 'ar' ? 'ar' : 'en';
  let practitioners = [];
  try { practitioners = JSON.parse(site.dataset.practitioners || '[]'); } catch (_) {}
  const form = $('#booking-form'); const department = $('#department-select'); const practitioner = $('#practitioner-select'); const date = $('#preferred-date'); const time = $('#preferred-time'); const status = $('#form-status');
  const text = key => (translations[lang] && translations[lang][key]) || en[key] || key;
  function applyLanguage(next) {
    lang = next; localStorage.setItem('talya-language', lang); site.dir = lang === 'ar' ? 'rtl' : 'ltr'; site.lang = lang; document.documentElement.lang = lang; document.documentElement.dir = site.dir;
    $$('[data-i18n]').forEach(el => { const v = text(el.dataset.i18n); if (v) el.textContent = v; });
    $$('[data-i18n-placeholder]').forEach(el => el.placeholder = text(el.dataset.i18nPlaceholder));
    $('.lang-en').classList.toggle('active', lang === 'en'); $('.lang-ar').classList.toggle('active', lang === 'ar');
    document.title = lang === 'ar' ? 'مركز تاليا الطبي | الطب وطب الأسنان' : 'Talya Medical Center | Medicine & Dentistry';
    renderSelects();
    site.dispatchEvent(new CustomEvent('talya:languagechange', {detail: {language: lang}}));
  }
  $('.language-switch').addEventListener('click', () => applyLanguage(lang === 'en' ? 'ar' : 'en'));
  const toggle = $('.menu-toggle'); const nav = $('#main-nav'); toggle.addEventListener('click', () => { const open = !nav.classList.contains('open'); nav.classList.toggle('open', open); toggle.setAttribute('aria-expanded', String(open)); });
  $$('.main-nav a').forEach(a => a.addEventListener('click', () => { nav.classList.remove('open'); toggle.setAttribute('aria-expanded','false'); }));
  document.addEventListener('scroll', () => { let best = '#top'; $$('main section[id]').forEach(s => { if (s.getBoundingClientRect().top < 180) best = '#' + s.id; }); $$('.main-nav a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === best)); }, {passive:true});
  date.min = new Date().toLocaleDateString('en-CA', {timeZone:'Asia/Dubai'});
  function option(value, label, key) { const el = document.createElement('option'); el.value=value; el.textContent=label; if(key) el.dataset.i18n=key; return el; }
  function renderSelects() {
    const chosenDepartment = department.value, chosenPractitioner = practitioner.value;
    department.replaceChildren(option('', text('select_clinic')));
    [...new Set(practitioners.map(p => p.department).filter(Boolean))].forEach(d => department.append(option(d,d)));
    if ([...department.options].some(o => o.value === chosenDepartment)) department.value = chosenDepartment;
    practitioner.replaceChildren(option('', text('select_doctor')));
    practitioners.filter(p => !department.value || p.department === department.value).forEach(p => practitioner.append(option(p.id, lang === 'ar' ? p.name_ar : p.name_en)));
    if ([...practitioner.options].some(o => o.value === chosenPractitioner)) practitioner.value=chosenPractitioner;
    $('#configuration-alert').hidden = practitioners.length > 0;
    [department, practitioner, date, time, form.querySelector('button[type=submit]')].forEach(el => el.disabled = practitioners.length === 0);
    renderDoctors();
  }
  function renderDoctors() {
    if (!practitioners.length) return;
    const grid = $('#doctor-grid'); grid.innerHTML='';
    practitioners.forEach(p => { const card=document.createElement('article'); card.className='doctor-card'; const image=p.image || (String(p.name_en).toLowerCase().includes('farouq') ? '/assets/talya/images/dr-farouq.png' : ''); card.innerHTML=`<div class="doctor-photo ${image?'':'placeholder'}">${image?`<img src="${image}" alt="">`:`<div class="avatar-mark">${(p.name_en||'DR').split(/\s+/).map(x=>x[0]).slice(-2).join('')}</div>`}</div><div class="doctor-info"><span class="specialty">${lang==='ar'?p.specialty_ar:p.specialty_en}</span><h3>${lang==='ar'?p.name_ar:p.name_en}</h3><p>${lang==='ar'?p.bio_ar:p.bio_en}</p><button class="doctor-book ${p.booking_enabled?'enabled':''}" type="button" ${p.booking_enabled?'':'disabled'}>${p.booking_enabled?text('book'):text('booking_unavailable')}</button></div>`; const b=$('button',card); if(p.booking_enabled)b.addEventListener('click',()=>{ department.value=p.department; renderSelects(); practitioner.value=p.id; document.querySelector('#appointment').scrollIntoView({behavior:'smooth'}); }); grid.append(card); });
  }
  department.addEventListener('change', () => { renderSelects(); time.replaceChildren(option('',text('select_time'))); });
  async function loadSlots() {
    time.replaceChildren(option('', text('loading_slots'))); time.disabled=true;
    if (!practitioner.value || !date.value) { time.replaceChildren(option('',text('select_time'))); time.disabled=practitioners.length===0; return; }
    try { const url=`/api/method/talya.api.get_slots?practitioner=${encodeURIComponent(practitioner.value)}&date=${encodeURIComponent(date.value)}`; const res=await fetch(url,{headers:{Accept:'application/json'}}); const data=await res.json(); if(!res.ok)throw new Error(); const slots=(data.message&&data.message.slots)||[]; time.replaceChildren(option('', slots.length?text('select_time'):text('no_slots'))); slots.forEach(s=>time.append(option(s,s))); time.disabled=!slots.length; }
    catch(e){time.replaceChildren(option('',text('generic_error'))); time.disabled=true;}
  }
  practitioner.addEventListener('change', () => { const p=practitioners.find(x=>x.id===practitioner.value); if(p&&p.department){department.value=p.department;} loadSlots(); }); date.addEventListener('change',loadSlots);
  form.addEventListener('submit', async e => { e.preventDefault(); status.className='form-status'; status.textContent=''; if(!form.reportValidity())return; const button=form.querySelector('button[type=submit]'); button.disabled=true; const payload=Object.fromEntries(new FormData(form)); payload.language=lang; try{const res=await fetch('/api/method/talya.api.submit_booking',{method:'POST',headers:{'Content-Type':'application/json','X-Frappe-CSRF-Token':$('meta[name=csrf-token]').content,Accept:'application/json'},body:JSON.stringify(payload)}); const data=await res.json(); if(!res.ok||data.exc)throw new Error(data._server_messages||''); const ref=data.message.booking_reference; status.className='form-status success'; status.textContent=`${text('submit_success')} ${lang==='ar'?'رقم الطلب':'Reference'}: ${ref}`; form.reset(); renderSelects(); date.min=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Dubai'});}catch(err){let msg=text('generic_error'); try{const messages=JSON.parse(JSON.parse(err.message)[0]); if(messages.message)msg=messages.message;}catch(_){} status.className='form-status error';status.textContent=msg;}finally{button.disabled=practitioners.length===0;}});
  $$('[data-service]').forEach(a => a.addEventListener('click', () => { const wanted=a.dataset.service.toLowerCase(); const match=[...department.options].find(o=>o.value.toLowerCase().includes(wanted.split(' ')[0].toLowerCase())); if(match){department.value=match.value;renderSelects();} }));
  applyLanguage(lang);
})();
