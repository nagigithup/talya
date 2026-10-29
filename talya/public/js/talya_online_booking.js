frappe.ui.form.on('Talya Online Booking', {
  refresh(frm) {
    if (frm.doc.booking_status !== 'Pending') return;
    frm.add_custom_button(__('Confirm & Create Appointment'), () => {
      if (!frm.doc.linked_patient) return frappe.msgprint(__('Link a verified Patient record first.'));
      frappe.confirm(__('Create the Healthcare Patient Appointment and confirm this request?'), () => frm.call('confirm_booking').then(() => frm.reload_doc()));
    }, __('Actions'));
    frm.add_custom_button(__('Reject'), () => {
      frappe.prompt({fieldname:'reason',fieldtype:'Small Text',label:__('Rejection Reason'),reqd:1}, values => frm.call('reject_booking',{reason:values.reason}).then(() => frm.reload_doc()), __('Reject Booking'));
    }, __('Actions'));
  }
});
