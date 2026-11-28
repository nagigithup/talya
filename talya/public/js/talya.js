(() => {
  const site = document.querySelector('.talya-site');
  if (!site) return;
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const translations = JSON.parse($('#talya-translations').textContent);
  const lang = site.lang === 'ar' ? 'ar' : 'en';
  const text = key => translations[lang][key] || translations.en[key] || key;
  const practitioners = JSON.parse(site.dataset.practitioners || '[]').filter(row => row.booking_enabled);
  const form = $('#booking-form');
  const department = $('#department-select');
  const practitioner = $('#practitioner-select');
  const date = $('#preferred-date');
  const time = $('#preferred-time');
  const status = $('#form-status');
  const lookupFields = $('#patient-lookup');
  const registration = $('#patient-registration');
  const visit = $('#appointment-fields');
  const lookupKind = $('#lookup-kind');
  const lookupValue = $('#lookup-value');
  const lookupButton = $('#lookup-patient');
  const lookupStatus = $('#patient-lookup-status');
  const notice = $('#other-booking-notice');
  const submitButton = form.querySelector('button[type=submit]');
  const csrf = $('meta[name=csrf-token]').content;
  const nonce = () => [...crypto.getRandomValues(new Uint8Array(16))]
    .map(byte => byte.toString(16).padStart(2, '0')).join('');

  const flow = nonce();
  let requestId = nonce();
  let mode = '';
  let reference = '';
  let sharedMobile = '';
  let pendingIdentity = Promise.resolve();
  let identityVersion = 0;
  let availabilityVersion = 0;
  let noticeVersion = 0;
  let submitting = false;
  let booked = false;
  let lookingUp = false;

  async function request(method, data) {
    const response = await fetch('/api/method/talya.api.' + method, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf, Accept: 'application/json'},
      body: JSON.stringify({...data, language: lang}),
      cache: 'no-store',
    });
    if (response.status === 429) throw new Error(text('booking_rate_limited'));
    const result = await response.json();
    if (!response.ok || result.exc) {
      // Display only errors this form explicitly expects. Framework errors can
      // contain private record or configuration details.
      let message;
      try {
        message = JSON.parse(JSON.parse(result._server_messages)[0]).message;
      } catch { /* Use the public fallback. */ }
      throw new Error(translations[lang].public_errors.includes(message) ? message : text('generic_error'));
    }
    return result.message;
  }

  function displayLookup(message = '') {
    lookupStatus.textContent = message;
    lookupStatus.hidden = !message;
  }

  function setPanel(element, visible) {
    element.hidden = !visible;
    element.disabled = !visible;
  }

  function refreshForm() {
    const ready = mode === 'new' || (mode === 'existing' && Boolean(reference));
    setPanel(lookupFields, mode === 'existing');
    setPanel(registration, mode === 'new');
    setPanel(visit, ready && practitioners.length > 0);
    submitButton.hidden = visit.hidden || booked;
    submitButton.disabled = submitButton.hidden || submitting;
    lookupButton.disabled = lookingUp;
  }

  function invalidateLookup() {
    const previous = reference;
    reference = '';
    identityVersion++;
    noticeVersion++;
    notice.hidden = true;
    requestId = nonce();
    displayLookup();
    if (previous) {
      pendingIdentity = pendingIdentity.then(() =>
        request('invalidate_patient_lookup', {flow_id: flow, booking_reference: previous})
      ).catch(() => {
        // Discard this form's reference immediately. A new lookup also replaces
        // its server reference, and every reference has a short lifetime.
      });
    }
    refreshForm();
  }

  function updateLookupLabel() {
    const useId = lookupKind.value === 'emirates_id';
    $('#lookup-label').textContent = text(useId ? 'emirates_id' : 'mobile');
    lookupValue.inputMode = useId ? 'numeric' : 'tel';
  }

  function selectMode(next) {
    invalidateLookup();
    booked = false;
    status.textContent = '';
    status.className = 'form-status';
    mode = next;
    sharedMobile = '';
    lookupKind.value = 'mobile';
    lookupValue.value = '';
    updateLookupLabel();
    refreshForm();
  }

  $('#patient-mode').addEventListener('change', event => selectMode(event.target.value));
  lookupValue.addEventListener('input', invalidateLookup);
  lookupKind.addEventListener('change', () => {
    invalidateLookup();
    if (lookupKind.value === 'mobile') sharedMobile = '';
    lookupValue.value = '';
    updateLookupLabel();
    lookupValue.focus();
  });

  async function lookupPatient() {
    if (lookingUp || !lookupValue.value.trim()) {
      if (!lookingUp) displayLookup(text('lookup_required'));
      return;
    }
    const kind = lookupKind.value;
    const value = lookupValue.value;
    invalidateLookup();
    const version = identityVersion;
    lookingUp = true;
    refreshForm();
    try {
      await pendingIdentity;
      const result = await request('lookup_patient', {flow_id: flow, kind, value, shared_mobile: sharedMobile});
      if (version !== identityVersion) {
        if (result.booking_reference) {
          await request('invalidate_patient_lookup', {flow_id: flow, booking_reference: result.booking_reference});
        }
        return;
      }
      if (result.booking_reference) {
        reference = result.booking_reference;
        displayLookup(text('patient_welcome').replace('{0}', () => result.first_name));
        refreshForm();
        updateNotice();
      } else if (result.status === 'new') {
        const mobile = kind === 'mobile' ? value : '';
        const emiratesId = kind === 'emirates_id' ? value : '';
        form.querySelector('[name=patient_mode][value=new]').checked = true;
        selectMode('new');
        form.elements.mobile_number.value = mobile;
        form.elements.emirates_id.value = emiratesId;
        displayLookup(text('no_patient_match'));
        form.elements.first_name.focus();
      } else if (result.status === 'emirates_id') {
        sharedMobile = value;
        lookupKind.value = 'emirates_id';
        lookupValue.value = '';
        updateLookupLabel();
        displayLookup(text('shared_mobile_lookup'));
        lookupValue.focus();
      } else {
        displayLookup(text('patient_lookup_reception'));
      }
    } catch (error) {
      if (version === identityVersion) displayLookup(error.message);
    } finally {
      lookingUp = false;
      refreshForm();
    }
  }

  async function updateNotice() {
    const version = ++noticeVersion;
    notice.hidden = true;
    if (!reference || !practitioner.value) return;
    try {
      const result = await request('booking_notice', {
        flow_id: flow,
        booking_reference: reference,
        practitioner: practitioner.value,
      });
      if (version === noticeVersion) notice.hidden = !result.has_other_booking;
    } catch { /* The final submission rechecks this non-blocking notice. */ }
  }

  function renderSelects() {
    const selectedDepartment = department.value;
    const selectedDoctor = practitioner.value;
    const departments = [...new Set(practitioners.map(row => row.department).filter(Boolean))];
    department.replaceChildren(new Option(text('select_clinic'), ''), ...departments.map(d => new Option(d, d)));
    department.value = departments.includes(selectedDepartment) ? selectedDepartment : '';
    const doctors = practitioners.filter(row => !department.value || row.department === department.value);
    practitioner.replaceChildren(
      new Option(text('select_doctor'), ''),
      ...doctors.map(row => new Option(lang === 'ar' ? row.name_ar : row.name_en, row.id))
    );
    practitioner.value = doctors.some(row => row.id === selectedDoctor) ? selectedDoctor : '';
  }

  async function loadSlots() {
    const version = ++availabilityVersion;
    time.replaceChildren(new Option(text('select_time'), ''));
    time.disabled = true;
    if (!practitioner.value || !date.value) return;
    time.replaceChildren(new Option(text('loading_slots'), ''));
    try {
      const params = new URLSearchParams({practitioner: practitioner.value, date: date.value});
      const response = await fetch('/api/method/talya.api.get_slots?' + params, {cache: 'no-store'});
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (version !== availabilityVersion) return;
      const slots = result.message.slots;
      time.replaceChildren(new Option(text(slots.length ? 'select_time' : 'no_slots'), ''),
        ...slots.map(slot => new Option(slot, slot)));
      time.disabled = !slots.length;
    } catch {
      if (version === availabilityVersion) time.replaceChildren(new Option(text('generic_error'), ''));
    }
  }

  lookupButton.addEventListener('click', lookupPatient);
  lookupValue.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      lookupPatient();
    }
  });
  form.addEventListener('input', () => {
    if (!submitting) requestId = nonce();
  });
  department.addEventListener('change', () => { renderSelects(); loadSlots(); updateNotice(); });
  practitioner.addEventListener('change', () => {
    const selected = practitioners.find(row => row.id === practitioner.value);
    if (selected) department.value = selected.department;
    loadSlots();
    updateNotice();
  });
  date.addEventListener('change', loadSlots);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting || booked || visit.hidden || time.disabled || !form.reportValidity()) return;
    const booking = Object.fromEntries(new FormData(form));
    submitting = true;
    status.textContent = '';
    status.className = 'form-status';
    const controls = [...form.elements].filter(element => !element.disabled);
    controls.forEach(element => { element.disabled = true; });
    try {
      await pendingIdentity;
      const result = await request('submit_booking', {
        ...booking, flow_id: flow, request_id: requestId, booking_reference: reference,
      });
      notice.hidden = !result.has_other_booking;
      booked = true;
      status.classList.add('success');
      status.textContent = text('submit_success') + ' ' + text('booking_reference_label') + ' ' + result.booking_reference;
      invalidateLookup();
      notice.hidden = !result.has_other_booking;
      form.reset();
      mode = '';
    } catch (error) {
      status.classList.add('error');
      status.textContent = error.message;
    } finally {
      controls.forEach(element => { element.disabled = false; });
      submitting = false;
      refreshForm();
    }
  });

  const toggle = $('.menu-toggle');
  const nav = $('#main-nav');
  toggle.addEventListener('click', () => {
    toggle.setAttribute('aria-expanded', String(nav.classList.toggle('open')));
  });
  $$('.main-nav a').forEach(link => link.addEventListener('click', () => {
    nav.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }));
  document.addEventListener('scroll', () => {
    let active = '#top';
    $$('main section[id]').forEach(section => {
      if (section.getBoundingClientRect().top < 180) active = '#' + section.id;
    });
    $$('.main-nav a').forEach(link => link.classList.toggle('active', new URL(link.href).hash === active));
  }, {passive: true});
  $('.language-switch').addEventListener('click', event => {
    const target = new URL(event.currentTarget.href);
    const selected = practitioners.find(row => row.id === practitioner.value);
    if (selected?.profile_key) target.searchParams.set('doctor', selected.profile_key);
    target.hash = window.location.hash;
    event.currentTarget.href = target.toString();
  });

  function chooseDoctor(selected) {
    if (!selected) return;
    department.value = selected.department;
    renderSelects();
    practitioner.value = selected.id;
    requestId = nonce();
    loadSlots();
    updateNotice();
  }
  $$('#doctor-grid .doctor-book').forEach(button => button.addEventListener('click', () => {
    chooseDoctor(practitioners.find(row => row.id === button.dataset.practitioner));
    $('#appointment').scrollIntoView({behavior: 'smooth'});
  }));
  $$('[data-service]').forEach(link => link.addEventListener('click', () => {
    const wanted = link.dataset.service.toLowerCase();
    const match = [...department.options].find(option => option.value.toLowerCase().includes(wanted));
    if (!match) return;
    department.value = match.value;
    renderSelects();
    requestId = nonce();
    loadSlots();
    updateNotice();
  }));

  date.min = new Date().toLocaleDateString('en-CA', {timeZone: 'Asia/Dubai'});
  $('#configuration-alert').hidden = practitioners.length > 0;
  renderSelects();
  chooseDoctor(practitioners.find(row => row.id === site.dataset.selectedDoctor));
  refreshForm();
})();
