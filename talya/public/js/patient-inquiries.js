/* Reception UI; all messages and appointments are owned by their existing apps. */
(() => {
  'use strict';
  const config = JSON.parse(document.querySelector('#talya-config').textContent);
  const t = key => config.labels[key] || key;
  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const statusNames = ['New', 'Contacted', 'Awaiting Reply', 'Booked', 'Closed'];
  const options = (rows, current = '') => rows.map(row => {
    const value = typeof row === 'string' ? row : row.name;
    const label = typeof row === 'string' ? t(row) : row.label || row.name;
    return `<option value="${esc(value)}" ${value === current ? 'selected' : ''}>${esc(label)}</option>`;
  }).join('');
  const field = (name, label, value = '', type = 'text', extra = '') => `<label>${esc(t(label))}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
  let start = 0, selected = null, detailSequence = 0, settingsCache, rows = [], socket;
  let toastTimer, filterTimer, pollTimer;
  const detailDialog = $('#detail-dialog'), actionDialog = $('#action-dialog');

  function toast(message) {
    clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').hidden = false;
    toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 5500);
  }
  function errorText(error) { return error.message || t('Unable to complete this action. Please try again.'); }
  async function api(method, args = {}, post = false) {
    args = {...args,_lang:config.language};
    const url = `/api/method/${method}`;
    const response = await fetch(post ? url : url + '?' + new URLSearchParams(args), {
      method: post ? 'POST' : 'GET', credentials: 'same-origin',
      headers: {'X-Frappe-CSRF-Token': config.csrf, 'Accept': 'application/json', ...(post ? {'Content-Type':'application/json'} : {})},
      body: post ? JSON.stringify(args) : undefined,
    });
    let data;
    try { data = await response.json(); } catch { throw new Error(t('The server is unavailable. Please try again.')); }
    if (!response.ok || data.exc) {
      let message = t('Unable to complete this action. Please try again.');
      try { const logs = JSON.parse(data._server_messages || '[]'); if (logs.length) message = JSON.parse(logs.at(-1)).message; } catch { /* Generic error remains safe. */ }
      const text = document.createElement('div'); text.innerHTML = message;
      throw new Error(text.textContent);
    }
    return data.message;
  }
  const call = (method, args, post) => api('talya.inquiries.' + method, args, post);
  async function busy(form, task) {
    const controls = [...form.querySelectorAll('button[type=submit]')];
    controls.forEach(button => { button.disabled = true; });
    form.querySelector('.error')?.remove();
    try { return await task(); } catch (error) {
      const alert = document.createElement('div'); alert.className = 'error'; alert.role = 'alert'; alert.textContent = errorText(error); form.prepend(alert);
    } finally { controls.forEach(button => { button.disabled = false; }); }
  }
  function openAction(title, html) {
    $('#action-title').textContent = t(title); $('#action-content').innerHTML = html;
    if (!actionDialog.open) actionDialog.showModal();
  }
  document.addEventListener('click', event => { if (event.target.closest('[data-close]')) event.target.closest('dialog').close(); });
  detailDialog.addEventListener('close', () => { if (selected && socket) socket.emit('doc_unsubscribe', 'Talya Patient Inquiry', selected); selected = null; detailSequence++; });

  let listSequence = 0;
  async function loadList(silent = false) {
    const request = ++listSequence;
    if (!silent) $('#inquiry-list').innerHTML = `<div class="empty">${esc(t('Loading inquiries…'))}</div>`;
    const filters = Object.fromEntries(new FormData($('#filters')));
    try {
      const result = await call('list_inquiries', {...filters, start});
      if (request !== listSequence) return;
      rows = result;
      $('#result-count').textContent = `${start + (rows.length ? 1 : 0)}–${start + rows.length}`;
      $('#previous').disabled = start === 0; $('#next').disabled = rows.length < 30;
      $('#inquiry-list').innerHTML = rows.length ? rows.map(row => `<article class="inquiry-row">
        <div><h3><button class="open-record" data-open="${esc(row.name)}">${esc(row.patient_name)}</button></h3><p class="phone">${esc(row.mobile_number)}</p></div>
        <div class="doctor-column"><p>${esc(row.healthcare_practitioner || t('Doctor not selected'))}</p><p>${esc(row.preferred_date || t('No preferred date'))}</p></div>
        <div class="service-column"><p>${esc(row.requested_service || t('General inquiry'))}</p><p>${esc(t(row.source))}</p></div>
        <span class="badge" data-status="${esc(row.status)}">${esc(t(row.status))}</span>
        <div class="mini-actions"><button class="secondary" data-open="${esc(row.name)}" data-mode="conversation">${esc(t('WhatsApp'))}</button><button data-open="${esc(row.name)}" data-mode="book">${esc(t(row.linked_patient_appointment ? 'View Appointment' : 'Book Appointment'))}</button></div>
      </article>`).join('') : `<div class="empty"><strong>${esc(t('No inquiries yet'))}</strong>${esc(t('New website requests, imports and conversations will appear here.'))}</div>`;
    } catch (error) { if (request === listSequence) $('#inquiry-list').innerHTML = `<div class="empty error">${esc(errorText(error))}</div>`; }
  }
  $('#filters').addEventListener('submit', event => { event.preventDefault(); start = 0; loadList(); });
  $('#filters input').addEventListener('input', () => { clearTimeout(filterTimer); filterTimer = setTimeout(() => { start = 0; loadList(true); }, 300); });
  $('#previous').onclick = () => { start = Math.max(0, start - 30); loadList(); };
  $('#next').onclick = () => { start += 30; loadList(); };
  $('#inquiry-list').addEventListener('click', event => {
    const button = event.target.closest('[data-open]');
    if (button) openDetail(button.dataset.open, button.dataset.mode).catch(error => toast(errorText(error)));
  });

  async function lookups() { return await call('lookup', {doctype:'Healthcare Practitioner'}); }
  function inquiryForm(doc, doctors) {
    return `<form id="inquiry-form"><div class="form-grid">
      ${field('patient_name','Patient Name',doc.patient_name,'text','required maxlength="140" autocomplete="name" dir="auto"')}
      ${field('mobile_number','Mobile / WhatsApp',doc.mobile_number,'tel','required maxlength="30" dir="ltr" autocomplete="tel"')}
      <p class="hint full">${esc(t('Changing the recipient clears consent and Patient verification. Linked appointments require a new inquiry.'))}</p>
      <label>${esc(t('Doctor'))}<select name="healthcare_practitioner"><option value="">${esc(t('Select doctor'))}</option>${options(doctors,doc.healthcare_practitioner)}</select></label>
      ${field('requested_service','Requested Service',doc.requested_service,'text','maxlength="140" dir="auto"')}
      ${field('preferred_date','Preferred Date',doc.preferred_date,'date','dir="ltr"')}
      ${field('preferred_time','Preferred Time',String(doc.preferred_time || '').slice(0,5),'time','dir="ltr"')}
      <label class="full">${esc(t('Status'))}<select name="status">${options(statusNames,doc.status || 'New')}</select></label>
      <label class="full">${esc(t('Notes'))}<textarea name="notes" maxlength="4000" dir="auto">${esc(doc.notes)}</textarea></label>
      <label class="check full"><input type="checkbox" name="whatsapp_consent" ${doc.whatsapp_consent ? 'checked':''}>${esc(t('Patient consented to WhatsApp communication'))}</label>
      <label class="check full"><input type="checkbox" name="opt_out" ${doc.opt_out ? 'checked':''}>${esc(t('Opt Out'))}</label>
      <p class="hint full">${esc(t('Website privacy consent does not imply WhatsApp consent.'))}</p>
      </div><div class="form-footer"><button type="submit">${esc(t('Save Inquiry'))}</button></div></form>`;
  }
  function bindInquiryForm(doc, root) {
    const form = $('#inquiry-form',root);
    form.onsubmit = event => { event.preventDefault(); busy(form, async () => {
      const data = Object.fromEntries(new FormData(form)); data.whatsapp_consent = form.whatsapp_consent.checked ? 1 : 0; data.opt_out = form.opt_out.checked ? 1 : 0;
      const name = await call('save_inquiry',{name:doc.name || undefined,data:JSON.stringify(data)},true);
      if (actionDialog.open) actionDialog.close();
      toast(t('Inquiry saved')); await loadList(true); await openDetail(name);
    }); };
  }
  $('#new-button').onclick = async () => {
    try { openAction('New Inquiry',inquiryForm({},await lookups())); bindInquiryForm({},actionDialog); }
    catch (error) { toast(errorText(error)); }
  };

  async function openDetail(name, mode) {
    const sequence = ++detailSequence;
    if (selected && socket) socket.emit('doc_unsubscribe','Talya Patient Inquiry',selected);
    selected = name;
    $('#detail-title').textContent = t('Loading…');
    $('#detail-content').innerHTML = `<div class="empty">${esc(t('Loading…'))}</div>`;
    if (!detailDialog.open) detailDialog.showModal();
    try {
      const [data, doctors] = await Promise.all([call('detail',{name}),lookups()]);
      if (sequence !== detailSequence || selected !== name) return;
      const doc = data.inquiry;
      if (doc.healthcare_practitioner && !doctors.some(d => d.name === doc.healthcare_practitioner)) doctors.push({name:doc.healthcare_practitioner});
      $('#detail-title').textContent = doc.patient_name;
      $('#detail-content').innerHTML = `<nav class="detail-tabs" aria-label="${esc(t('Inquiry navigation'))}"><button class="secondary" data-panel=".inquiry-fields">${esc(t('Inquiry details'))}</button><button class="secondary" data-panel=".conversation">${esc(t('WhatsApp'))}</button></nav><div class="detail-grid"><section class="inquiry-fields">
        ${doc.source === 'WhatsApp' && !doc.linked_patient ? `<p class="notice">${esc(t('This incoming inquiry is unlinked. Verify the Patient before booking or sharing appointment details.'))}</p>`:''}
        ${doc.linked_patient && !doc.patient_verified_at ? `<button id="verify-linked-patient" class="secondary" type="button">${esc(t('Verify Patient'))}</button>`:''}
        ${doc.linked_patient_appointment ? `<div class="linked-appointment">${esc(t('Appointment booked'))} <a href="/desk/patient-appointment/${encodeURIComponent(doc.linked_patient_appointment)}" target="_blank" rel="noopener">${esc(doc.linked_patient_appointment)} ↗</a></div>` : `<button id="book-detail" style="width:100%;margin-block-end:20px">${esc(t('Book Appointment'))}</button>`}
        ${inquiryForm(doc,doctors)}</section><section class="conversation" aria-label="${esc(t('WhatsApp conversation'))}">
        <div class="conversation-heading"><h2>${esc(t('WhatsApp conversation'))}</h2><button class="quiet" id="refresh-messages">${esc(t('Refresh'))}</button></div>
        <div id="messages" class="messages" aria-live="polite"></div>
        ${data.integration.configured ? `<p class="hint">${esc(t('Free text within 24 hours of a patient reply. Approved templates otherwise.'))}</p><form id="message-form" class="composer"><label>${esc(t('Approved template'))}<select name="template"><option value="">${esc(t('Text message'))}</option>${options(data.conversation.templates.map(row => ({name:row.name,label:row.template_name})))}</select></label>
          <label>${esc(t('Message'))}<textarea id="message-input" name="message" maxlength="4000" dir="auto" placeholder="${esc(t('Write a message…'))}"></textarea></label>
          <label>${esc(t('Private attachment'))}<input name="attachment" type="file" accept="image/*,audio/*,video/*,.pdf"></label><p class="attachment-name" id="attachment-name"></p>
          <button type="submit">${esc(t('Send Message'))}</button><p class="hint">${esc(t('Delivery is confirmed only by WhatsApp status updates.'))}</p></form>` : `<p class="hint">${esc(t('WhatsApp API is not configured. Open WhatsApp to send manually.'))}</p><a class="fallback" id="fallback-link" href="${esc(data.conversation.fallback)}" target="_blank" rel="noopener">${esc(t('Open WhatsApp'))} ↗</a><p class="hint">${esc(t('Opening WhatsApp does not send a message.'))}</p>`}
        </section></div>`;
      bindInquiryForm(doc,detailDialog); renderMessages(data.conversation.messages);
      document.querySelectorAll('[data-panel]').forEach(button => { button.onclick = () => $(button.dataset.panel,detailDialog).scrollIntoView({block:'start',behavior:'smooth'}); });
      $('#book-detail')?.addEventListener('click',() => openBooking(doc).catch(error => toast(errorText(error))));
      $('#verify-linked-patient')?.addEventListener('click',async event => {
        if (!confirm(t('I verified this Patient and their authorization to use this phone number. Continue?'))) return;
        event.target.disabled = true;
        try { await call('verify_patient',{name:doc.name,patient:doc.linked_patient,identity_verified:true},true); toast(t('Patient identity verified')); await openDetail(doc.name); }
        catch (error) { toast(errorText(error)); event.target.disabled = false; }
      });
      $('#refresh-messages').onclick = () => refreshMessages();
      $('#fallback-link')?.addEventListener('click',event => { if (!data.conversation.contact_allowed) { event.preventDefault(); toast(t('Record WhatsApp consent and check opt-out before contacting the patient.')); } });
      if ($('#message-form')) bindComposer(doc);
      if (socket) socket.emit('doc_subscribe','Talya Patient Inquiry',name);
      if (mode === 'book') {
        if (doc.linked_patient_appointment) { location.href = '/desk/patient-appointment/' + encodeURIComponent(doc.linked_patient_appointment); }
        else await openBooking(doc);
      }
      if (mode === 'conversation') $('.conversation').scrollIntoView({block:'start'});
    } catch (error) { if (sequence === detailSequence) { $('#detail-title').textContent = t('Patient Inquiries'); $('#detail-content').innerHTML = `<div class="empty error">${esc(errorText(error))}</div>`; } }
  }
  function renderMessages(messages) {
    const container = $('#messages'); if (!container) return;
    container.innerHTML = messages.length ? messages.map(message => `<div class="bubble ${message.direction === 'Outgoing' ? 'outgoing':''}" data-status="${esc(message.status)}"><div dir="auto">${esc(message.template || message.message || t('Media attachment'))}</div>
      ${safeMedia(message.media_url) ? `<a href="${esc(safeMedia(message.media_url))}" target="_blank" rel="noopener">${esc(message.file_name || t('View Attachment'))} ↗</a>`:message.media_url || message.mime_type ? `<small>${esc(t('Attachment metadata received; file download is unavailable.'))}</small>`:''}
      <small>${esc(t(message.direction))} · ${esc(t(message.status))} · <bdi>${esc(String(message.creation || '').slice(0,16))}</bdi></small>${message.status === 'Failed' ? `<small>${esc(message.error_message || t('Message failed'))}</small>`:''}</div>`).join('') : `<div class="empty">${esc(t('No messages yet'))}</div>`;
    container.scrollTop = container.scrollHeight;
  }
  function safeMedia(url) { return String(url || '').startsWith('/private/files/') ? url : null; }
  async function refreshMessages() {
    if (!selected || !detailDialog.open || !$('#messages')) return;
    const name = selected;
    try { const data = await call('detail',{name}); if (name === selected) renderMessages(data.conversation.messages); }
    catch (error) { toast(errorText(error)); }
  }
  async function upload(file, inquiry) {
    const body = new FormData(); body.append('file',file); body.append('is_private','1');
    if (inquiry) { body.append('doctype','Talya Patient Inquiry'); body.append('docname',inquiry); }
    const response = await fetch('/api/method/upload_file',{method:'POST',headers:{'X-Frappe-CSRF-Token':config.csrf},body});
    const data = await response.json();
    if (!response.ok || !data.message) throw new Error(t('Upload failed. Please try again.'));
    return data.message;
  }
  function bindComposer(doc) {
    const form = $('#message-form'); let key = crypto.randomUUID(), attachment = null;
    form.template.onchange = () => { form.message.disabled = Boolean(form.template.value); form.attachment.disabled = Boolean(form.template.value); };
    form.onsubmit = event => { event.preventDefault(); busy(form,async () => {
      if (form.attachment.files.length && !attachment) { attachment = await upload(form.attachment.files[0],doc.name); $('#attachment-name').textContent = attachment.file_name; }
      const result = await api('talya.communication.send',{name:doc.name,request_key:key,message:form.message.value,template:form.template.value || undefined,attach:attachment?.file_url},true);
      if (result.state === 'Reserved') { toast(t('Send outcome is unconfirmed. Review history before trying again.')); await refreshMessages(); return; }
      key = crypto.randomUUID(); attachment = null; form.message.value = ''; form.attachment.value = '';
      $('#attachment-name').textContent = ''; toast(t(result.status === 'Failed' ? 'Message failed. Review the message status.' : 'Message recorded. Check its delivery status.')); await refreshMessages();
    }); };
  }

  async function openBooking(doc) {
    openAction('Book Appointment',`<p>${esc(t('Loading…'))}</p>`);
    const [context, doctors, types, genders] = await Promise.all([call('patient_context',{name:doc.name}),lookups(),call('lookup',{doctype:'Appointment Type'}),call('lookup',{doctype:'Gender'})]);
    const visit = context.visit || {};
    const patientField = df => {
      const value = context.defaults[df.fieldname] ?? '';
      const required = df.reqd ? 'required' : '';
      if (df.fieldname === 'sex') return `<label>${esc(df.label)}<select name="patient_${esc(df.fieldname)}" ${required}><option value="">${esc(t('Select gender'))}</option>${options(genders,value)}</select></label>`;
      if (df.fieldtype === 'Select') return `<label>${esc(df.label)}<select name="patient_${esc(df.fieldname)}" ${required}>${options(String(df.options || '').split('\n'),value)}</select></label>`;
      if (df.fieldtype === 'Check') return `<label class="check"><input name="patient_${esc(df.fieldname)}" type="checkbox" ${value ? 'checked':''}>${esc(df.label)}</label>`;
      const type = df.fieldtype === 'Date' ? 'date' : ['Int','Float'].includes(df.fieldtype) ? 'number' : 'text';
      return `<label>${esc(df.label)}<input name="patient_${esc(df.fieldname)}" type="${type}" value="${esc(value)}" ${required} dir="auto"></label>`;
    };
    const matchMarkup = rows => rows.length ? rows.map(row => `<label class="patient-match"><input type="radio" name="patient" value="${esc(row.name)}" ${row.name === doc.linked_patient ? 'checked':''}><span><strong>${esc(row.patient_name || row.name)}</strong><small>${esc([row.mobile || row.phone,row.dob,row.sex,row.identity_hint].filter(Boolean).join(' · '))}</small><small>${esc(t(row.identity_match ? 'Identity number match' : row.phone_match ? 'Same contact number — verify the person' : 'Name match — verify the person'))}</small></span></label>`).join('') : `<p class="hint">${esc(t('No possible matches found. Search again or create a Patient.'))}</p>`;
    $('#action-content').innerHTML = `<form id="booking-form"><div class="form-grid">
      <section class="full patient-resolution"><h3>${esc(t('Find or Create Patient'))}</h3>
      <label>${esc(t('Find existing patient'))}<input name="patient_search" type="search" placeholder="${esc(t(context.identity_search_available ? 'Patient name, mobile, or identity number' : 'Patient name or mobile number'))}"></label>
      <button type="button" class="secondary" id="patient-search-button">${esc(t('Search'))}</button>
      <div id="patient-matches" class="patient-matches">${matchMarkup(context.matches)}</div>
      ${context.more_matches ? `<p class="hint">${esc(t('More matches exist. Narrow your search.'))}</p>`:''}
      <button type="button" class="quiet" id="create-patient" ${context.can_create ? '' : 'disabled'}>${esc(t('Create Patient'))}</button>
      ${context.creation_error ? `<p class="error">${esc(context.creation_error)}</p>`:''}
      <div id="new-patient-fields" class="form-grid" hidden>${context.patient_fields.map(patientField).join('')}<label class="check full"><input name="reviewed_matches" type="checkbox">${esc(t('I reviewed the possible matches and none is the correct Patient.'))}</label></div></section>
      <p class="hint full">${esc(t('Verify patient identity before linking. Shared phone numbers may match several patients.'))}</p>
      <label class="check full"><input name="identity_verified" type="checkbox" required>${esc(t('I verified the Patient and their authorization to use this phone number.'))}</label>
      <label>${esc(t('Doctor'))}<select name="practitioner" required ${visit.locked?'disabled':''}><option value="">${esc(t('Select doctor'))}</option>${options(doctors,visit.practitioner || doc.healthcare_practitioner)}</select></label>
      ${field('date','Appointment Date',visit.date || doc.preferred_date || new Date().toLocaleDateString('en-CA'),'date',`required dir="ltr" ${visit.locked?'readonly':''}`)}
      <label class="full">${esc(t('Appointment Type'))}<select name="appointment_type" required ${visit.locked?'disabled':''}><option value="">${esc(t('Select appointment type'))}</option>${options(types,visit.appointment_type)}</select></label>
      <label class="full">${esc(t('Service Unit'))}<select name="service_unit" required ${visit.locked?'disabled':''}><option value="">${esc(t('Select service unit'))}</option>${visit.service_unit ? options([visit.service_unit],visit.service_unit):''}</select></label>
      ${visit.locked ? `<p class="notice full">${esc(t('This website request keeps its doctor, visit type, date, and time. Availability is checked again when you confirm.'))}</p>`:''}
      <button id="load-slots" type="button" class="secondary full">${esc(t('Check Available Times'))}</button>
      <label class="full">${esc(t('Available Time'))}<select name="slot" required><option value="">${esc(t('Check availability first'))}</option></select></label>
      ${field('end_time','End Time','','text','readonly dir="ltr"')}
      <p class="hint full" id="slot-status" role="status"></p>
      <label class="full">${esc(t('Notes'))}<textarea name="notes" maxlength="1000" dir="auto"></textarea></label>
      </div><div class="form-footer"><button type="submit">${esc(t('Confirm Booking'))}</button></div></form>`;
    const form = $('#booking-form'); let slots = [], slotSequence = 0, previous = null, createMode = false;
    const newFields = $('#new-patient-fields');
    const setCreateMode = enabled => { createMode = enabled; newFields.hidden = !enabled; newFields.querySelectorAll('input,select,textarea').forEach(control => { control.disabled = !enabled; }); if (enabled) form.reviewed_matches.required = true; };
    setCreateMode(false);
    const selectedPatient = () => form.querySelector('[name=patient]:checked')?.value || '';
    $('#patient-search-button').onclick = async () => { try { const result = await call('patient_context',{name:doc.name,search:form.patient_search.value}); $('#patient-matches').innerHTML = matchMarkup(result.matches); setCreateMode(false); form.identity_verified.checked = false; reset(); } catch (error) { toast(errorText(error)); } };
    $('#patient-matches').addEventListener('change',() => { setCreateMode(false); form.identity_verified.checked = false; reset(); });
    $('#create-patient').onclick = () => { setCreateMode(true); form.querySelectorAll('[name=patient]').forEach(input => { input.checked = false; }); form.identity_verified.checked = false; reset(); };
    const bookingArgs = () => ({name:doc.name,patient:createMode ? undefined : selectedPatient(),new_patient:createMode ? 1 : 0,practitioner:form.practitioner.value,date:form.date.value,appointment_type:form.appointment_type.value,service_unit:form.service_unit.value || undefined});
    const reset = () => { previous = slots[Number(form.slot.value)] || previous; slotSequence++; slots = []; form.slot.innerHTML = `<option value="">${esc(t('Check availability first'))}</option>`; form.end_time.value = ''; };
    ['practitioner','date','appointment_type','service_unit'].forEach(name => form[name].addEventListener('change',() => { reset(); if (name === 'practitioner') form.service_unit.value = ''; loadSlots(); }));
    async function loadSlots() {
      const sequence = ++slotSequence;
      if ((!selectedPatient() && !createMode) || !form.practitioner.value || !form.date.value || !form.appointment_type.value) return;
      $('#load-slots').disabled = true; $('#slot-status').textContent = t('Loading…');
      try {
        const result = await call('slot_options',bookingArgs());
        if (sequence !== slotSequence) return;
        const oldUnit = form.service_unit.value;
        form.service_unit.innerHTML = `<option value="">${esc(t('Select service unit'))}</option>` + options(result.service_units,oldUnit);
        if (!form.service_unit.value && result.service_units.length === 1) form.service_unit.value = result.service_units[0];
        if (oldUnit && form.service_unit.value !== oldUnit) { await loadSlots(); return; }
        slots = result.slots;
        form.slot.innerHTML = `<option value="">${esc(t('Select time'))}</option>` + slots.map((slot,index) => `<option value="${index}">${esc(slot.time)}${slot.service_unit ? ' · ' + esc(slot.service_unit) : ''}</option>`).join('');
        const wanted = previous || (visit.time ? {time:visit.time,service_unit:visit.service_unit || form.service_unit.value} : null);
        const index = wanted ? slots.findIndex(slot => slot.time === wanted.time && (!wanted.service_unit || slot.service_unit === wanted.service_unit)) : -1;
        form.slot.value = index < 0 ? '' : String(index); previous = index < 0 ? null : slots[index]; form.end_time.value = previous?.end_time || '';
        $('#slot-status').textContent = slots.length ? t('Choose an available time.') : t('No available times. Choose another date.');
      } catch (error) { if (sequence === slotSequence) $('#slot-status').textContent = errorText(error); } finally { if (sequence === slotSequence) $('#load-slots').disabled = false; }
    }
    form.slot.addEventListener('change',() => { previous = form.slot.value === '' ? null : slots[Number(form.slot.value)]; form.end_time.value = previous?.end_time || ''; });
    $('#load-slots').onclick = () => { reset(); loadSlots(); };
    form.onsubmit = event => { event.preventDefault(); busy(form,async () => {
      const slot = slots[Number(form.slot.value)]; if (!slot || form.slot.value === '') throw new Error(t('Check availability first'));
      if (!createMode && !selectedPatient()) throw new Error(t('Select and verify a Patient.'));
      const patientData = createMode ? Object.fromEntries(context.patient_fields.map(df => [df.fieldname,df.fieldtype === 'Check' ? (form[`patient_${df.fieldname}`].checked ? 1 : 0) : form[`patient_${df.fieldname}`].value])) : undefined;
      const appointment = await call('confirm',{...bookingArgs(),patient:createMode?undefined:selectedPatient(),patient_data:createMode?JSON.stringify(patientData):undefined,reviewed_matches:createMode && form.reviewed_matches.checked,identity_verified:form.identity_verified.checked,time:slot.time,service_unit:slot.service_unit,notes:form.notes.value,expected_modified:context.inquiry_modified,expected_booking_modified:visit.booking_modified},true);
      toast(t('Appointment booked')); await loadList(true); await openDetail(doc.name);
      openAction('Appointment booked',`<div class="linked-appointment"><a href="/desk/patient-appointment/${encodeURIComponent(appointment)}" target="_blank" rel="noopener">${esc(t('View Appointment'))} · ${esc(appointment)} ↗</a><p>${esc(form.date.value)} · ${esc(slot.time)}</p></div><p>${esc(t('Offer a confirmation through the WhatsApp conversation. No message has been sent automatically.'))}</p><div class="form-footer"><button id="offer-confirmation">${esc(t('WhatsApp Confirmation'))}</button></div>`);
      $('#offer-confirmation').onclick = () => { actionDialog.close(); $('.conversation')?.scrollIntoView({block:'nearest'}); if ($('#message-form')) { $('#message-form').template.value = settingsCache?.settings.confirmation_template || ''; $('#message-form').template.dispatchEvent(new Event('change')); } };
    }); };
  }

  $('#settings-button').onclick = async () => {
    try {
      settingsCache = await api('talya.communication.get_settings');
      const s = settingsCache.settings, integration = settingsCache.integration;
      const templates = (settingsCache.templates || []).map(row => ({name:row.name,label:row.template_name}));
      const templateField = (name,label) => `<label>${esc(t(label))}<select name="${name}"><option value="">${esc(t('No template selected'))}</option>${options(templates,s[name])}</select></label>`;
      openAction('Communication Settings',`<div class="notice settings-status">${esc(t(integration.configured ? 'WhatsApp API configured' : 'WhatsApp API is not configured'))}<br>${esc(t('Default WhatsApp Account'))}: ${esc(integration.account || t('Not configured'))}</div>
        ${config.manager ? `<p class="hint"><a href="/desk/wa-settings">${esc(t('Official WhatsApp Settings'))} ↗</a> · <a href="/desk/wa-account">${esc(t('WhatsApp Accounts'))} ↗</a></p>`:''}
        <form id="settings-form"><fieldset style="border:0;padding:0" ${config.manager ? '' : 'disabled'}><div class="form-grid">
        ${field('country_calling_code','Default Country Calling Code',s.country_calling_code || '971','text','required dir="ltr"')}
        <label>${esc(t('Default Message Language'))}<select name="default_language"><option value="ar" ${s.default_language === 'ar'?'selected':''}>${esc(t('Arabic'))}</option><option value="en" ${s.default_language === 'en'?'selected':''}>${esc(t('English'))}</option></select></label>
        ${templateField('confirmation_template','Appointment Confirmation Template')}
        ${templateField('reminder_template','Appointment Reminder Template')}
        <label class="check full"><input name="reminders_enabled" type="checkbox" ${s.reminders_enabled ? 'checked':''}>${esc(t('Enable Appointment Reminders'))}</label>
        ${field('reminder_hours','Reminder Hours Before Appointment',s.reminder_hours || 24,'number','min="1" max="168" required dir="ltr"')}
        <p class="hint full">${esc(t('WhatsApp consent is required. API credentials are managed in the official WhatsApp app.'))}</p></div>${config.manager ? `<div class="form-footer"><button type="submit">${esc(t('Save Settings'))}</button></div>`:''}</fieldset></form>`);
      $('#settings-form').onsubmit = event => { event.preventDefault(); busy(event.target,async () => { const data = Object.fromEntries(new FormData(event.target)); data.reminders_enabled = event.target.reminders_enabled.checked ? 1 : 0; settingsCache = await api('talya.communication.save_settings',{data:JSON.stringify(data)},true); actionDialog.close(); toast(t('Settings saved')); }); };
    } catch (error) { toast(errorText(error)); }
  };

  $('#import-button').onclick = () => {
    openAction('Import',`<p>${esc(t('Import public contact requests only. No messages will be sent.'))}</p><form id="upload-form"><label>${esc(t('Private CSV or Excel file'))}<input name="file" type="file" accept=".csv,.xlsx" required></label><p class="hint">${esc(t('Up to 1000 rows. UTF-8 CSV or XLSX, smaller than 2 MB.'))}</p><div class="form-footer"><button type="submit">${esc(t('Upload and Map Columns'))}</button></div></form>`);
    $('#upload-form').onsubmit = event => { event.preventDefault(); busy(event.target,async () => {
      const uploaded = await upload(event.target.file.files[0]);
      const info = await api('talya.inquiry_import.columns',{file_name:uploaded.name});
      const fields = {patient_name:'Patient Name',mobile_number:'Mobile / WhatsApp',healthcare_practitioner:'Doctor',requested_service:'Requested Service',preferred_date:'Preferred Date',notes:'Notes'};
      $('#action-content').innerHTML = `<form id="mapping-form"><p class="hint">${esc(t('Map columns, then preview. Existing inquiries will never be overwritten.'))}</p><div class="form-grid">${Object.entries(fields).map(([name,label]) => `<label>${esc(t(label))}<select name="${name}" ${['patient_name','mobile_number'].includes(name)?'required':''}><option value="">${esc(t('Select column'))}</option>${info.columns.map((column,index) => `<option value="${index}">${esc(column)}</option>`).join('')}</select></label>`).join('')}</div><div class="form-footer"><button type="submit">${esc(t('Preview Import'))}</button></div></form><div id="import-preview"></div>`;
      const form = $('#mapping-form');
      form.onsubmit = event => { event.preventDefault(); busy(form,async () => {
        const mapping = Object.fromEntries(new FormData(form));
        const preview = await api('talya.inquiry_import.preview',{file_name:uploaded.name,mapping:JSON.stringify(mapping)},true);
        const invalid = preview.some(row => row.error);
        $('#import-preview').innerHTML = `<div class="import-preview">${preview.map(row => `<div><strong>${esc(t('Row'))} ${row.row}</strong> · ${esc(row.data.patient_name)} · <bdi>${esc(row.data.normalized_phone || row.data.mobile_number)}</bdi><p>${esc(row.error || t(row.duplicate ? 'Duplicate — will be skipped' : 'Ready to import'))}</p></div>`).join('')}</div><p class="hint">${esc(t('Duplicates are skipped. No existing records are changed.'))}</p><div class="form-footer"><button id="confirm-import" ${invalid || !preview.length ? 'disabled':''}>${esc(t('Confirm Import'))}</button></div>`;
        const snapshot = JSON.stringify(mapping);
        form.onchange = () => { $('#import-preview').innerHTML = ''; };
        $('#confirm-import').onclick = async event => {
          if (!confirm(t('Import valid new inquiries and skip duplicates?'))) return;
          event.target.disabled = true;
          try { const result = await api('talya.inquiry_import.import_rows',{file_name:uploaded.name,mapping:snapshot,confirmed:true},true); actionDialog.close(); toast(`${t('Imported')}: ${result.created} · ${t('Skipped')}: ${result.skipped}`); await loadList(true); }
          catch (error) { toast(errorText(error)); event.target.disabled = false; }
        };
      }); };
    }); };
  };

  function realtime() {
    if (!window.io) return;
    const host = config.development ? location.protocol + '//' + location.hostname + ':' + config.socketPort : location.origin;
    socket = window.io(host + '/' + config.site,{withCredentials:true,reconnectionAttempts:3});
    socket.on('connect',() => { if (selected) socket.emit('doc_subscribe','Talya Patient Inquiry',selected); });
    socket.on('talya_inquiry',event => { loadList(true); if (event.incoming) toast(t('New incoming WhatsApp message')); if (selected === event.name) refreshMessages(); });
    socket.on('whatsapp_message',event => { if (event.reference_docname === selected) refreshMessages(); });
  }
  async function init() {
    await loadList();
    try { settingsCache = await api('talya.communication.get_settings'); $('#integration-banner').textContent = t(settingsCache.integration.configured ? 'WhatsApp API configured' : 'WhatsApp API is not configured. Reception can use the manual WhatsApp fallback.'); }
    catch (error) { $('#integration-banner').textContent = errorText(error); }
    realtime();
    // Reconcile delivery changes and reconnect gaps; do not replace unsaved forms.
    pollTimer = setInterval(() => { if (!document.hidden) { loadList(true); refreshMessages(); } },20000);
    document.addEventListener('visibilitychange',() => { if (!document.hidden) { loadList(true); refreshMessages(); } });
    window.addEventListener('pagehide',() => { clearInterval(pollTimer); socket?.disconnect(); });
  }
  init();
})();
