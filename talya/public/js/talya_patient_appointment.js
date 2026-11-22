/* App-owned Healthcare dialog; the public Talya booking form is unchanged. */
frappe.provide('talya.internal_booking');
(() => {
  'use strict';
  // Keep Healthcare's links and permissions; only arrange this form's records.
  frappe.dom.set_style(`
    body[data-route^="Form/Patient Appointment/"] .form-links .form-documents > .row > .col-md-4 {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      flex: 0 0 100%;
      width: 100%;
      max-width: 100%;
    }
    body[data-route^="Form/Patient Appointment/"] .form-links .form-link-title {
      grid-column: 1 / -1;
      margin-bottom: 0;
    }
    body[data-route^="Form/Patient Appointment/"] .form-links .document-link {
      width: 100%;
      max-width: none;
      min-width: 0;
      margin-bottom: 0;
    }
    body[data-route^="Form/Patient Appointment/"] .form-links .document-link-badge {
      min-width: 0;
    }
    body[data-route^="Form/Patient Appointment/"] .form-links .badge-link {
      white-space: normal;
      overflow-wrap: anywhere;
    }
    body[data-route^="Form/Patient Appointment/"] .form-links .btn-new {
      flex-shrink: 0;
    }
    @media (max-width: 767px) {
      body[data-route^="Form/Patient Appointment/"] .form-links .form-documents > .row > .col-md-4 {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      body[data-route^="Form/Patient Appointment/"] .form-links .document-link:last-child:nth-child(even) {
        grid-column: 1 / -1;
      }
    }
  `, 'talya-appointment-records-layout');
  const escape = value => frappe.utils.escape_html(String(value ?? ''));
  talya.internal_booking.open = async frm => {
    let sequence = 0, selected = null, slots = [], initializing = true, applying = false;
    const dialog = new frappe.ui.Dialog({
      title: __('Available slots'),
      fields: [
        {fieldtype:'Link', fieldname:'practitioner', options:'Healthcare Practitioner', label:__('Healthcare Practitioner'), reqd:1,
          get_query:() => ({filters:{status:'Active'}})},
        {fieldtype:'Date', fieldname:'appointment_date', label:__('Date'), reqd:1, min_date:new Date(frappe.datetime.get_today())},
        {fieldtype:'Column Break'},
        {fieldtype:'Link', fieldname:'appointment_type', options:'Appointment Type', label:__('Appointment Type'), reqd:1,
          get_query:() => ({filters:{allow_booking_for:'Practitioner'}})},
        {fieldtype:'Select', fieldname:'service_unit', label:__('Service Unit'), options:'', reqd:1},
        {fieldtype:'Section Break'},
        {fieldtype:'Data', fieldname:'end_time', label:__('End Time'), read_only:1},
        {fieldtype:'HTML', fieldname:'available_slots'},
      ],
      primary_action_label:__('Book'),
      primary_action:async () => {
        if (!selected || !frm.doc.patient) return;
        const choice = {...selected}, values = dialog.get_values();
        if (!values) return;
        dialog.get_primary_btn().prop('disabled',true);
        try {
          applying = true; frm.__talya_booking_applying = true;
          await frm.set_value({appointment_for:'Practitioner',appointment_type:values.appointment_type,
            practitioner:values.practitioner,department:dialog.__department,appointment_date:values.appointment_date,
            appointment_time:choice.time,service_unit:choice.service_unit,appointment_based_on_check_in:0});
          await frm.set_value('duration',choice.duration);
          frm.enable_save();
          await frm.save(); // The server locks and rechecks the complete visit.
          dialog.hide();
        } catch (error) {
          applying = false; frm.__talya_booking_applying = false;
          await load();
        } finally { applying = false; frm.__talya_booking_applying = false; }
      },
    });
    frm.__talya_booking_dialog = dialog;
    const wrapper = dialog.fields_dict.available_slots.$wrapper;
    const args = () => ({practitioner:dialog.get_value('practitioner'),date:dialog.get_value('appointment_date'),
      appointment_type:dialog.get_value('appointment_type'),service_unit:dialog.get_value('service_unit') || undefined,
      patient:frm.doc.patient || undefined,appointment_name:frm.is_new() ? undefined : frm.doc.name});
    function render() {
      wrapper.html(`<div style="display:flex;flex-wrap:wrap;gap:6px">${slots.map((slot,index) =>
        `<button type="button" class="btn btn-sm ${selected === slot ? 'btn-primary':'btn-default'}" data-talya-slot="${index}" title="${escape(slot.time + ' – ' + slot.end_time)}">${escape(slot.time)}${dialog.get_value('service_unit') ? '' : ' · ' + escape(slot.service_unit)}</button>`
      ).join('')}</div><p class="text-muted small" style="margin-top:10px">${escape(slots.length ? __('Choose an available time.') : __('No available times. Choose another date.'))}</p>`);
      wrapper.find('[data-talya-slot]').on('click',async event => {
        selected = slots[Number(event.currentTarget.dataset.talyaSlot)];
        if (selected.service_unit !== dialog.get_value('service_unit')) {
          initializing = true;
          await dialog.set_value('service_unit',selected.service_unit);
          initializing = false;
          await load();
        } else { await dialog.set_value('end_time',selected.end_time); render(); }
      });
      dialog.get_primary_btn().prop('disabled',!selected || !frm.doc.patient);
    }
    async function load() {
      if (initializing || applying) return;
      const current = ++sequence, previous = selected;
      selected = null; slots = [];
      dialog.get_primary_btn().prop('disabled',true);
      await dialog.set_value('end_time','');
      const values = args();
      if (!values.practitioner || !values.date || !values.appointment_type) {
        wrapper.html(`<p class="text-muted">${escape(__('Select practitioner, date and Appointment Type to view times.'))}</p>`);
        return;
      }
      wrapper.html(`<p class="text-muted">${escape(__('Loading…'))}</p>`);
      try {
        const response = await frappe.call({method:'talya.internal_booking.slots',args:values,type:'GET'});
        if (current !== sequence) return;
        const data = response.message;
        dialog.__department = data.department;
        dialog.set_df_property('service_unit','options',['',...data.service_units].join('\n'));
        const oldUnit = dialog.get_value('service_unit');
        if (!data.service_units.includes(oldUnit)) {
          initializing = true;
          await dialog.set_value('service_unit',data.service_units.length === 1 ? data.service_units[0] : '');
          initializing = false;
          if (oldUnit && dialog.get_value('service_unit') !== oldUnit) { await load(); return; }
        }
        slots = data.slots;
        selected = previous && slots.find(row => row.time === previous.time && row.service_unit === previous.service_unit);
        await dialog.set_value('end_time',selected?.end_time || '');
        render();
      } catch (error) {
        if (current === sequence) wrapper.html(`<p class="text-muted">${escape(__('No available times. Choose another date.'))}</p>`);
      }
    }
    ['practitioner','appointment_date','appointment_type','service_unit'].forEach(field => {
      dialog.fields_dict[field].df.onchange = async () => {
        if (initializing) return;
        if (field === 'practitioner') {
          initializing = true; await dialog.set_value('service_unit',''); initializing = false;
        }
        load();
      };
    });
    dialog.$wrapper.on('hidden.bs.modal',() => { sequence++; if (frm.__talya_booking_dialog === dialog) delete frm.__talya_booking_dialog; });
    dialog.__talya_reload = load;
    dialog.show(); dialog.get_primary_btn().prop('disabled',true);
    await dialog.set_values({practitioner:frm.doc.practitioner,appointment_date:frm.doc.appointment_date || frappe.datetime.get_today(),
      appointment_type:frm.doc.appointment_type,service_unit:frm.doc.service_unit || ''});
    initializing = false;
    await load();
    return dialog;
  };

  // Frappe appends doctype_js to Healthcare's script in the same function scope.
  // Reuse every existing Check Availability/Reschedule entry point without a
  // fork or mutation of Healthcare's source or of its public website endpoints.
  if (typeof check_and_set_availability === 'function') {
    check_and_set_availability = frm => talya.internal_booking.open(frm);
  }
  const changed = frm => {
    if (frm.__talya_booking_applying) return;
    frm.__talya_booking_dialog?.__talya_reload();
    if (frm.doc.appointment_time) frm.set_value('appointment_time',null);
  };
  frappe.ui.form.on('Patient Appointment',{
    practitioner:changed, appointment_date:changed, appointment_type:changed, service_unit:changed,
  });
})();
