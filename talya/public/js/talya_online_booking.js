frappe.provide('talya.booking_desk');
(() => {
  'use strict';
  const escape = value => frappe.utils.escape_html(String(value ?? ''));
  const call = (method,args) => frappe.call({method:'talya.online_booking.' + method,args,type:'GET'}).then(r=>r.message);
  frappe.dom.set_style(`
    body[data-route^="Form/Talya Online Booking/"] .form-section[data-fieldname="contact_section"] > .section-body {
      display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0 12px;
    }
    body[data-route^="Form/Talya Online Booking/"] .form-section[data-fieldname="contact_section"] > .section-body > .form-column {
      min-width:0; max-width:100%; width:100%; padding-inline:0;
    }
    body[data-route^="Form/Talya Online Booking/"] [data-fieldname="mobile_number"] input,
    body[data-route^="Form/Talya Online Booking/"] [data-fieldname="preferred_date"] input,
    body[data-route^="Form/Talya Online Booking/"] [data-fieldname="preferred_time"] input,
    body[data-route^="Form/Talya Online Booking/"] [data-fieldname="appointment_end_time"] input {direction:ltr;unicode-bidi:isolate;}
    .talya-patient-matches {display:grid;gap:8px;max-height:260px;overflow:auto;margin-block:10px;}
    .talya-patient-match {border:1px solid var(--border-color);border-radius:var(--border-radius);padding:10px;overflow-wrap:anywhere;}
    .talya-patient-match small {display:block;color:var(--text-muted);}
    .talya-booking-patient-dialog [data-fieldname="new_mobile"] input,
    .talya-booking-patient-dialog [data-fieldname="new_mobile"] .control-value,
    .talya-booking-patient-dialog [data-fieldname="new_phone"] input,
    .talya-booking-patient-dialog [data-fieldname="new_email"] input {direction:ltr;unicode-bidi:isolate;}
    @media(max-width:991px) {
      body[data-route^="Form/Talya Online Booking/"] .form-section[data-fieldname="contact_section"] > .section-body {grid-template-columns:repeat(2,minmax(0,1fr));}
    }
    @media(max-width:767px) {
      body[data-route^="Form/Talya Online Booking/"] .form-section[data-fieldname="contact_section"] > .section-body {grid-template-columns:minmax(0,1fr);}
    }
  `,'talya-online-booking-layout');
  async function saved(frm) {
    if (frm.is_dirty()) await frm.save();
    if (frm.is_new()) frappe.throw(__('Save the booking before continuing.'));
  }
  function errorText(error) {
    try {
      const messages=JSON.parse(error.responseJSON?._server_messages || '[]');
      if (messages.length) {
        const element=document.createElement('div');element.innerHTML=JSON.parse(messages.at(-1)).message;
        return element.textContent;
      }
    } catch { /* Use a translated fallback. */ }
    return __('Unable to confirm. Reload the booking and review its status before retrying.');
  }
  async function action(frm,method,args,dialog) {
    if (frm.__talya_confirm_busy) return;
    frm.__talya_confirm_busy=true;
    const buttons=dialog ? dialog.get_primary_btn().add(dialog.get_secondary_btn()) : frm.page.inner_toolbar.find('button');
    buttons.prop('disabled',true);
    try {
      const response=await frm.call(method,{...args,expected_modified:frm.doc.modified});
      dialog?.hide(); await frm.reload_doc();
      frappe.show_alert({message:method==='link_verified_patient' ? __('Verified Patient linked.') : __('Booking confirmed.'),indicator:'green'});
      return response.message;
    } catch (error) {
      if (dialog) dialog.fields_dict.result.$wrapper.empty().append($('<p class="text-danger" role="alert">').text(errorText(error)));
      else frappe.msgprint(errorText(error));
    } finally { frm.__talya_confirm_busy=false; buttons.prop('disabled',false); }
  }
  talya.booking_desk.find_patient=async frm => {
    if (frm.__talya_patient_dialog?.is_visible || frm.__talya_patient_dialog?.display || frm.__talya_patient_dialog_loading) return;
    frm.__talya_patient_dialog_loading=true;
    try {
    await saved(frm);
    let context=await call('patient_context',{name:frm.doc.name}),prefilled=false;
    const patientFields=context.patient_fields.map(field=>({...field,fieldname:'new_' + field.fieldname,
      depends_on:"eval:doc.mode==='new'",reqd:0,mandatory_depends_on:field.reqd ? "eval:doc.mode==='new'" : undefined,
      read_only:field.fieldname==='mobile' ? 1 : 0}));
    const dialog=new frappe.ui.Dialog({title:__('Find or Create Patient'),size:'large',fields:[
      {fieldtype:'HTML',fieldname:'explanation',options:`<p>${escape(__('A shared phone number does not identify a Patient. Verify the person before linking.'))}</p>`},
      {fieldtype:'Data',fieldname:'search',label:__('Search Patient name or ID')},
      {fieldtype:'Button',fieldname:'search_button',label:__('Search')},
      {fieldtype:'HTML',fieldname:'matches'},
      {fieldtype:'Select',fieldname:'mode',label:__('Patient action'),options:[{label:__('Link Existing Patient'),value:'existing'},
        ...(context.can_create ? [{label:__('Create New Patient'),value:'new'}] : [])],default:'existing',reqd:1},
      {fieldtype:'Select',fieldname:'patient',label:__('Select verified Patient'),options:'',depends_on:"eval:doc.mode==='existing'",mandatory_depends_on:"eval:doc.mode==='existing'"},
      {fieldtype:'Check',fieldname:'identity_verified',label:__("I verified the Patient and their authorization to use this phone number."),reqd:1},
      {fieldtype:'Check',fieldname:'reviewed_matches',label:__('I reviewed the possible matches; none is the correct Patient.'),depends_on:"eval:doc.mode==='new'",mandatory_depends_on:"eval:doc.mode==='new'"},
      {fieldtype:'Section Break',label:__('Verified Patient Details'),depends_on:"eval:doc.mode==='new'"},...patientFields,
      {fieldtype:'Section Break'},
      {fieldtype:'HTML',fieldname:'result',options:`<p class="text-muted">${escape(__('Confirmation does not send messages. Website privacy consent is separate from WhatsApp consent.'))}</p>`},
    ],primary_action_label:__('Link Patient & Confirm Booking'),primary_action:()=>submit(false),
      secondary_action_label:__('Link Patient Only'),secondary_action:()=>submit(true)});
    dialog.$wrapper.addClass('talya-booking-patient-dialog');
    frm.__talya_patient_dialog=dialog;
    function renderMatches() {
      const lines=row=>[[__('Patient ID'),row.name],[__('Gender'),row.sex],[__('Date of birth'),row.dob],
        [__('Mobile Number'),row.mobile],[__('Phone'),row.phone],[__('Email Address'),row.email]]
        .filter(([,value])=>value).map(([label,value])=>`<small>${escape(label)}: <bdi dir="ltr">${escape(value)}</bdi></small>`).join('');
      dialog.fields_dict.matches.$wrapper.html(`<div class="talya-patient-matches">${context.matches.map(row=>
        `<div class="talya-patient-match"><strong>${escape(row.patient_name || row.name)}</strong>${lines(row)}${row.phone_match ? '' : `<small>${escape(__('Primary contact differs. Authorized staff must review the Patient contact before linking.'))}</small>`}</div>`
      ).join('') || `<p>${escape(__('No possible matches found. Verify the details before creating a Patient.'))}</p>`}</div>${context.more_matches ? `<p>${escape(__('More matches exist. Search by the exact Patient name or ID.'))}</p>` : ''}`);
      if (context.creation_error) dialog.fields_dict.matches.$wrapper.append($('<p class="text-warning">').text(context.creation_error));
      dialog.set_df_property('patient','options',[{label:__('Select verified Patient'),value:''},
        ...context.matches.filter(row=>row.phone_match).map(row=>({label:`${row.patient_name || row.name} · ${row.name}`,value:row.name}))]);
    }
    async function submit(linkOnly) {
      const values=dialog.get_values(); if (!values || frm.__talya_confirm_busy) return;
      const warning=message=>dialog.fields_dict.result.$wrapper.empty().append($('<p class="text-danger" role="alert">').text(message));
      if (!values.identity_verified) return warning(__("Confirm the patient's identity and authorization to use this number before linking."));
      if (values.mode==='new' && !values.reviewed_matches) return warning(__('Review the possible matches and confirm that none is the correct Patient.'));
      if (values.mode==='new') {
        if (linkOnly) return;
        const data=Object.fromEntries(context.patient_fields.map(field=>[field.fieldname,values['new_' + field.fieldname]])
          .filter(([,value])=>value!==undefined && value!==null && value!==''));
        await action(frm,'confirm_booking',{patient_data:data,identity_verified:values.identity_verified,reviewed_matches:values.reviewed_matches},dialog);
      } else await action(frm,linkOnly ? 'link_verified_patient' : 'confirm_booking',{patient:values.patient,identity_verified:values.identity_verified},dialog);
    }
    dialog.fields_dict.search_button.df.click=async () => {
      context=await call('patient_context',{name:frm.doc.name,search:dialog.get_value('search')});
      renderMatches(); await dialog.set_value('patient',''); await dialog.set_value('identity_verified',0);
    };
    dialog.fields_dict.patient.df.onchange=()=>dialog.set_value('identity_verified',0);
    dialog.fields_dict.mode.df.onchange=async () => {
      const creating=dialog.get_value('mode')==='new';
      dialog.set_primary_action(creating ? __('Create Patient & Confirm Booking') : __('Link Patient & Confirm Booking'),()=>submit(false));
      dialog.get_secondary_btn().toggle(!creating); await dialog.set_value('identity_verified',0); dialog.refresh_dependency();
    };
    dialog.fields_dict.identity_verified.df.onchange=async () => {
      if (dialog.get_value('mode')==='new' && dialog.get_value('identity_verified') && !prefilled) {
        prefilled=true;
        for (const [field,value] of Object.entries(context.defaults)) {
          if (dialog.fields_dict['new_' + field] && !dialog.get_value('new_' + field)) await dialog.set_value('new_' + field,value);
        }
      }
    };
    dialog.show(); renderMatches(); return dialog;
    } finally { frm.__talya_patient_dialog_loading=false; }
  };
  async function visitOptions(frm) {
    if (frm.is_new() || !frm.doc.healthcare_practitioner) return;
    const sequence=frm.__talya_options_sequence=(frm.__talya_options_sequence || 0)+1;
    const options=await call('visit_options',{name:frm.doc.name,practitioner:frm.doc.healthcare_practitioner});
    if (sequence!==frm.__talya_options_sequence) return;
    frm.__talya_visit_options=options;
    frm.set_query('service_unit',()=>({filters:{name:['in',options.service_units]}}));
    if (frm.doc.booking_status==='Pending') {
      if (!frm.doc.appointment_type && options.default_type) await frm.set_value('appointment_type',options.default_type);
      if (!frm.doc.service_unit && options.service_units.length===1) await frm.set_value('service_unit',options.service_units[0]);
    }
    frm.fields_dict.patient_identity_status.$wrapper.text(options.verified ? __('Patient identity verified.') : __('Patient identity verification required.'));
    await availability(frm);
  }
  async function availability(frm) {
    const sequence=frm.__talya_slot_sequence=(frm.__talya_slot_sequence || 0)+1,wrapper=frm.fields_dict.visit_availability.$wrapper;
    if (frm.doc.booking_status!=='Pending') { wrapper.empty(); return; }
    if (!frm.doc.healthcare_practitioner || !frm.doc.appointment_type || !frm.doc.preferred_date) {
      wrapper.empty(); await frm.set_value('appointment_end_time',''); return;
    }
    wrapper.text(__('Loading…'));
    try {
      const {message:data}=await frappe.call({method:'talya.internal_booking.slots',type:'GET',args:{practitioner:frm.doc.healthcare_practitioner,
        date:frm.doc.preferred_date,appointment_type:frm.doc.appointment_type,service_unit:frm.doc.service_unit || undefined,patient:frm.doc.linked_patient || undefined}});
      if (sequence!==frm.__talya_slot_sequence) return;
      const choice=data.slots.find(row=>row.time===String(frm.doc.preferred_time).slice(0,5) && row.service_unit===frm.doc.service_unit);
      await frm.set_value('appointment_end_time',choice ? choice.end_time + ':00' : '');
      wrapper.empty().append($('<p class="text-muted small">').text(choice ? __('Full visit available.') : __('Requested time is unavailable. Choose another time.')));
      const button=$('<button type="button" class="btn btn-default btn-sm">').text(__('Choose Available Time')).appendTo(wrapper);
      button.prop('disabled',!data.slots.length).on('click',()=>{
        const picker=new frappe.ui.Dialog({title:__('Choose Available Time'),fields:[{fieldtype:'Select',fieldname:'slot',label:__('Available Time'),reqd:1,
          options:[{label:__('Select time'),value:''},...data.slots.map((slot,index)=>({label:slot.time+' – '+slot.end_time+' · '+slot.service_unit,value:String(index)}))]}],
          primary_action_label:__('Select time'),primary_action:async values=>{const slot=data.slots[Number(values.slot)];
            await frm.set_value({preferred_time:slot.time + ':00',service_unit:slot.service_unit,appointment_end_time:slot.end_time + ':00'});picker.hide();}});
        picker.show();
      });
    } catch (error) { if (sequence===frm.__talya_slot_sequence) wrapper.text(errorText(error)); }
  }
  frappe.ui.form.on('Talya Online Booking',{
    async refresh(frm) {
      frm.set_query('healthcare_practitioner',()=>({filters:{status:'Active',department:frm.doc.medical_department,custom_show_on_talya_website:1,custom_enable_talya_online_booking:1}}));
      frm.set_query('appointment_type',()=>({filters:{allow_booking_for:'Practitioner'}}));
      for (const field of ['medical_department','healthcare_practitioner','appointment_type','service_unit','preferred_date','preferred_time']) {
        frm.set_df_property(field,'read_only',frm.doc.booking_status!=='Pending');
      }
      for (const field of ['appointment_type','service_unit']) frm.set_df_property(field,'reqd',frm.doc.booking_status==='Pending');
      if (frm.doc.booking_status!=='Pending' || frm.is_new()) return;
      frm.add_custom_button(__('Find or Create Patient'),()=>talya.booking_desk.find_patient(frm));
      frm.add_custom_button(__('Confirm & Create Appointment'),async()=>{
        await saved(frm);
        if (!frm.doc.linked_patient || !frm.__talya_visit_options?.verified) return talya.booking_desk.find_patient(frm);
        frappe.confirm(__('Create the Healthcare Patient Appointment and confirm this request?'),()=>action(frm,'confirm_booking',{}));
      });
      frm.add_custom_button(__('Reject'),()=>frappe.prompt({fieldname:'reason',fieldtype:'Small Text',label:__('Rejection Reason'),reqd:1},
        values=>frm.call('reject_booking',{reason:values.reason}).then(()=>frm.reload_doc()),__('Reject Booking')),__('Actions'));
      await visitOptions(frm);
    },
    async healthcare_practitioner(frm) {await frm.set_value('service_unit','');await visitOptions(frm);},
    appointment_type:availability,service_unit:availability,preferred_date:availability,preferred_time:availability,
  });
})();
