frappe.listview_settings['Talya Online Booking'] = {
  onload(listview) {
    listview.page.add_inner_button(__('Patient Inquiries'), () => { window.location.href = '/patient_inquiries'; });
  },
  add_fields: ['booking_status'],
  get_indicator(doc) {
    const colors = {Pending:'orange',Confirmed:'green',Rejected:'red',Cancelled:'gray',Completed:'blue'};
    return [__(doc.booking_status), colors[doc.booking_status] || 'gray', `booking_status,=,${doc.booking_status}`];
  }
};
