"""Public website copy and stable routes. No patient data or private site settings.

The clinic confirmed these public names, Arabic, Sudanese nationality, clinic
hours, service list and the two published prices on 2026-11-28. Experience is a
team statement only. Individual experience and unconfirmed prices stay absent.
"""

LABELS = {
	"menu": "Menu",
	"home": "Home",
	"services": "Services",
	"doctors": "Doctors",
	"book": "Book Appointment",
	"contact": "Contact",
	"eyebrow": "Medicine & Dentistry in Al Nakheel, Ras Al Khaimah",
	"hero_title": "Talya Medical Center",
	"hero_subtitle": "Medicine & Dentistry",
	"hero_description": "General medicine and dental care in Al Nakheel, Ras Al Khaimah, with personal "
	"attention for individuals and families.",
	"whatsapp": "Chat on WhatsApp",
	"location": "Open Location",
	"care_areas": "Care Areas",
	"hero_doctors": "Doctors",
	"hero_compassion": "Care with Compassion & Privacy",
	"our_services": "Our Services",
	"care_for_family": "Complete care for every family",
	"services_intro": "Focused medical and dental care, delivered with clarity and compassion.",
	"dental": "Dental Clinic",
	"dental_desc": "Dental checkups, cleaning, fillings and treatment planning in Al Nakheel.",
	"dental_one": "Checkups and dental cleaning",
	"dental_two": "Cavity fillings",
	"dental_three": "Crowns and bridges",
	"request_appointment": "Request appointment",
	"family": "General Medicine",
	"family_desc": "General medical consultations with Dr. Mehira Fadl in Al Nakheel.",
	"family_one": "GP consultations",
	"family_two": "Discuss your health concerns",
	"family_three": "Chronic disease follow-up",
	"lab": "Medical Laboratory",
	"lab_desc": "Contact reception to confirm requested tests and how they are arranged.",
	"lab_one": "Discuss requested tests",
	"lab_two": "Confirm availability with reception",
	"lab_three": "Ask about test preparation",
	"our_doctors": "Our Doctors",
	"meet_team": "Meet your care team",
	"doctors_intro": "Talya\u2019s team includes Arabic-speaking Sudanese doctors with over 10 years of experience "
	"in UAE government hospitals.",
	"dentist": "Dentist",
	"farouq_name": "Dr. Farouq Ejami",
	"farouq_bio": "Dr. Farouq Ejami provides dental consultations at Talya Medical Center in Al Nakheel, Ras "
	"Al Khaimah.",
	"booking_unavailable": "Booking configuration required",
	"gp": "General Practitioner",
	"mehira_name": "Dr. Mehira Fadl",
	"mehira_bio": "Dr. Mehira Fadl is a general practitioner at Talya Medical Center in Al Nakheel, Ras Al "
	"Khaimah.",
	"appointment_request": "Appointment Request",
	"start_care": "Take the first step toward better care",
	"booking_intro": "Send a preferred appointment request. Our team will contact you to confirm "
	"it—submitting this form does not create a confirmed appointment.",
	"secure_request": "Secure request handling",
	"schedule_aware": "Schedule-aware availability",
	"human_confirmation": "Confirmed by our reception team",
	"need_help": "Need help?",
	"book_appointment": "Book Appointment",
	"pending_note": "Requests remain pending until reception confirms.",
	"easy": "Quick · Easy · Private",
	"setup_needed": "Online booking setup is in progress",
	"setup_explainer": "No approved Healthcare Practitioner is enabled yet. Please call or WhatsApp the "
	"clinic.",
	"full_name": "Full Name",
	"mobile": "Mobile Number",
	"email": "Email Address",
	"clinic": "Clinic / Specialty",
	"select_clinic": "Select clinic",
	"doctor": "Doctor",
	"select_doctor": "Select doctor",
	"preferred_date": "Preferred Date",
	"preferred_time": "Preferred Time",
	"select_time": "Select time",
	"choose_doctor_date": "Choose a doctor and date to view configured availability.",
	"notes": "Notes (Optional)",
	"consent": "I consent to Talya Medical Center using these details to process and contact me about this "
	"appointment request.",
	"submit_request": "Submit Appointment Request",
	"our_location": "Our Location",
	"visit_talya": "Visit Talya Medical Center",
	"about_one": "Talya Medical Center offers general medicine and dental consultations in Al Nakheel, Ras Al "
	"Khaimah, near Action Hotel. Contact reception for directions and information about "
	"requested laboratory tests.",
	"about_two": "Our focus is patient comfort, personalized attention, and quality care for individuals and "
	"families.",
	"address": "Ras Al Khaimah, Al Nakheel, near Action Hotel, UAE.",
	"call_us": "Call us",
	"additional_phone": "Additional phone",
	"email_us": "Email us",
	"open_maps": "Open Google Maps",
	"tagline": "Your Health. Your Smile. Our Priority.",
	"privacy": "Privacy Policy",
	"notes_placeholder": "Anything our team should know...",
	"no_slots": "No configured slots are available on this date.",
	"loading_slots": "Loading availability…",
	"submit_success": "Your appointment request has been received successfully. Our team will contact you to "
	"confirm your appointment.",
	"generic_error": "We could not submit the request. Please review the details or contact us.",
	"skip_content": "Skip to content",
	"main_navigation": "Main navigation",
	"footer_navigation": "Footer navigation",
	"switch_language": "العربية",
	"view_profile": "View doctor profile",
	"service_details": "About this service",
	"contact_details": "Location and contact details",
	"doctor_profiles": "Meet our doctors in Al Nakheel",
	"home_title": "Talya Medical Center | Al Nakheel, Ras Al Khaimah",
	"home_description": "General medicine and dental consultations at Talya Medical Center in Al Nakheel, Ras "
	"Al Khaimah. Meet Dr. Mehira and Dr. Farouq and request an appointment.",
	"mehira_title": "{0} | GP in Al Nakheel, Ras Al Khaimah",
	"mehira_description": "Meet {0}, an Arabic-speaking Sudanese general practitioner at Talya Medical Center "
	"in Al Nakheel, Ras Al Khaimah. Request an appointment.",
	"farouq_title": "{0} | Dentist in Al Nakheel, Ras Al Khaimah",
	"farouq_description": "Meet {0}, an Arabic-speaking Sudanese dentist at Talya Medical Center in Al "
	"Nakheel, Ras Al Khaimah. Request a dental appointment.",
	"gp_title": "General Medicine in Al Nakheel, Ras Al Khaimah | Talya",
	"gp_description": "GP consultations and chronic disease follow-up with Dr. Mehira Fadl at Talya Medical "
	"Center in Al Nakheel, Ras Al Khaimah. Request an appointment.",
	"gp_heading": "General medicine in Al Nakheel, Ras Al Khaimah",
	"gp_intro": "Talya Medical Center provides GP consultations and chronic disease follow-up with Dr. Mehira "
	"Fadl in Al Nakheel, Ras Al Khaimah.",
	"gp_body": "Discuss your health concerns and ongoing conditions with the general practitioner. Dr. Mehira "
	"Fadl speaks Arabic and provides GP consultations and chronic disease follow-up at Talya "
	"Medical Center.",
	"gp_visit_heading": "Planning your GP consultation",
	"gp_visit_body": "Bring relevant previous medical reports and a current medication list for your "
	"consultation. If you need a particular test or procedure, contact reception to confirm "
	"whether it can be arranged and ask about preparation and fees before visiting.",
	"dental_title": "Dental Clinic in Al Nakheel, Ras Al Khaimah | Talya",
	"dental_description": "Dental care with Dr. Farouq Ejami in Al Nakheel, Ras Al Khaimah. Professional "
	"cleaning and cavity fillings at AED 150 each. Request an appointment at Talya.",
	"dental_heading": "Dental clinic in Al Nakheel, Ras Al Khaimah",
	"dental_intro": "Find dental consultations with Dr. Farouq Ejami at Talya Medical Center in Al Nakheel, "
	"Ras Al Khaimah.",
	"dental_body": "Dr. Farouq Ejami speaks Arabic and provides dental care at Talya Medical Center. Services "
	"include checkups, professional cleaning, cavity fillings, zirconia and porcelain crowns "
	"and bridges, whitening, veneers, braces, and gum care.",
	"dental_visit_heading": "Planning your dental visit",
	"dental_visit_body": "Contact reception for details and price quotations for other dental services. The "
	"dentist will assess your needs and discuss the treatment options with you.",
	"contact_title": "Contact Talya Medical Center | Al Nakheel, Ras Al Khaimah",
	"contact_description": "Find Talya Medical Center in Al Nakheel, Ras Al Khaimah, near Action Hotel. Get "
	"directions, call reception, or request a medical or dental appointment.",
	"contact_heading": "Visit Talya Medical Center in Al Nakheel",
	"contact_intro": "Our medical center is in Al Nakheel, Ras Al Khaimah, near Action Hotel. Use the Google "
	"Maps link for directions or call reception for help finding the clinic.",
	"hours_heading": "Opening hours and visits",
	"hours_body": "The clinic is open daily, including Fridays, from 4:00 PM to midnight. Walk-ins are "
	"welcome and online booking is available. Doctor appointment times shown in the booking "
	"form are separate from the public clinic hours.",
	"appointment_availability": "Doctor appointment availability",
	"availability_body": "Choose a date in the booking form to see the doctor's current available appointment "
	"times in Asia/Dubai. Reception confirms each request; sending the form does not "
	"create a confirmed appointment.",
	"about_doctor": "About the doctor",
	"languages": "Consultation languages",
	"nationality": "Nationality",
	"experience": "Experience",
	"clinic_location": "Clinic location",
	"related_care": "Related care at Talya",
	"appointment_steps": "How to request an appointment",
	"appointment_step_one": "Choose the doctor, date, and an available time in the booking form.",
	"appointment_step_two": "Provide your contact details and submit the appointment request.",
	"appointment_step_three": "Wait for reception to contact you and confirm the appointment.",
	"contact_reception": "Contact reception",
	"clinic_name": "Talya Medical Center",
	"location_short": "Al Nakheel, Ras Al Khaimah",
	"clinic_address": "Al Nakheel, near Action Hotel",
	"city": "Ras Al Khaimah",
	"country": "United Arab Emirates",
	"patient_request": "Request an appointment",
	"not_found": "Page not found",
	"clinic_hours_heading": "Clinic opening hours",
	"clinic_hours": "Daily, including Fridays, from 4:00 PM to midnight.",
	"walk_in_policy": "Walk-ins are welcome. Online booking is also available.",
	"dubai_timezone": "Asia/Dubai",
	"arabic_language": "Arabic",
	"sudan": "Sudan",
	"sudanese_female": "Sudanese female doctor",
	"sudanese_male": "Sudanese dentist",
	"sudanese": "Sudanese",
	"nationality_female": "Sudanese nationality",
	"dental_services_prices": "Dental services and prices",
	"service_column": "Service",
	"price_column": "Price",
	"currency_aed": "AED",
	"professional_cleaning": "Professional dental cleaning",
	"cavity_fillings": "Cavity fillings",
	"zirconia_crowns_bridges": "Zirconia crowns and bridges",
	"porcelain_crowns_bridges": "Porcelain crowns and bridges",
	"dental_checkups": "Dental checkups",
	"teeth_whitening": "Teeth whitening",
	"veneers": "Veneers",
	"braces": "Braces",
	"gum_care": "Gum care",
	"other_dental_prices": "For other dental services, contact reception for a price quotation.",
	"mehira_tagline": "Comprehensive Care. Experience You Can Trust.",
	"patient_mode": "Patient type",
	"existing_patient": "Existing patient",
	"new_patient": "New patient",
	"lookup_kind": "Look up by",
	"emirates_id": "Emirates ID",
	"emirates_id_optional": "Emirates ID (optional)",
	"find_my_record": "Find my record",
	"patient_welcome": "Welcome, {0}",
	"no_patient_match": "No patient record was found. Enter your details to continue.",
	"shared_mobile_lookup": "More than one patient uses this number. Enter your Emirates ID to continue.",
	"patient_lookup_reception": "Contact reception for help finding your patient record.",
	"lookup_required": "Enter your mobile number or Emirates ID.",
	"first_name": "First Name",
	"last_name": "Last Name",
	"gender": "Gender",
	"select_gender": "Select gender",
	"other_booking_notice": "You already have an upcoming booking with another doctor. You can continue with this request.",
	"booking_rate_limited": "Too many attempts. Please try again later.",
	"booking_reference_label": "Reference",
	"website_field": "Website",
}

PUBLIC_BOOKING_ERRORS = (
	"Reload the appointment form and try again.",
	"Enter a valid Emirates ID.",
	"Choose mobile number or Emirates ID.",
	"Enter a valid mobile number or Emirates ID.",
	"Look up your patient record again to continue.",
	"Enter your first name.",
	"Select your gender.",
	"Please enter a valid email address.",
	"Please enter a valid international mobile number.",
	"A matching patient record may already exist. Use Existing patient or contact reception.",
	"Contact reception to register as a new patient.",
	"We could not save this request. Try again or contact reception.",
	"Unable to process this request.",
	"Privacy consent is required.",
	"Please enter a valid preferred time.",
	"Choose a valid appointment date.",
	"The selected slot is no longer available.",
	"Choose Existing patient or New patient.",
	"Contact reception to complete this booking.",
	"This time has just been requested. Please choose another time.",
	"The selected practitioner is not available for public booking.",
	"Online booking is not enabled for the selected practitioner.",
	"The selected practitioner does not belong to this department.",
)

PAGE_SLUGS = {
	"home": "",
	"mehira": "doctors/dr-mehira-fadl",
	"farouq": "doctors/dr-farouq-ejami",
	"general_medicine": "services/general-medicine",
	"dental": "services/dental",
	"contact": "contact",
}

PUBLIC_ROUTES = {
	f"/{language}" + (f"/{slug}" if slug else ""): (page, language)
	for page, slug in PAGE_SLUGS.items()
	for language in ("en", "ar")
}

DOCTORS = {
	"mehira": {
		"name_key": "mehira_name",
		"specialty_key": "gp",
		"bio_key": "mehira_bio",
		"image": "images/dr-mehira-original.webp",
		"width": 720,
		"height": 900,
		"service": "general_medicine",
		"languages": ["ar"],
		"nationality": "Sudan",
		"experience": "",
	},
	"farouq": {
		"name_key": "farouq_name",
		"specialty_key": "dentist",
		"bio_key": "farouq_bio",
		"image": "images/dr-farouq.png",
		"optimized_image": "images/dr-farouq.webp",
		"width": 1182,
		"height": 1330,
		"service": "dental",
		"languages": ["ar"],
		"nationality": "Sudan",
		"experience": "",
	},
}

# A doctor's work schedule must never become the clinic's opening hours.
APPROVED_ORIGIN = "https://talyamedical.com"
CLINIC_OPENING_HOURS = [
	{
		"@type": "OpeningHoursSpecification",
		"dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
		"opens": "16:00",
		"closes": "00:00",
	}
]

DENTAL_SERVICES = [
	{"label": "professional_cleaning", "price": 150},
	{"label": "cavity_fillings", "price": 150},
	{"label": "zirconia_crowns_bridges", "price": None},
	{"label": "porcelain_crowns_bridges", "price": None},
	{"label": "dental_checkups", "price": None},
	{"label": "teeth_whitening", "price": None},
	{"label": "veneers", "price": None},
	{"label": "braces", "price": None},
	{"label": "gum_care", "price": None},
]
MAPS_URL = "https://maps.app.goo.gl/wjydTejcBzmawQNWA"
PHONE = "+971522207872"
PHONE_DISPLAY = "+971 52 220 7872"
ADDITIONAL_PHONE = "+971504087963"
ADDITIONAL_PHONE_DISPLAY = "+971 50 408 7963"
WHATSAPP_URL = "https://wa.me/971588698578"
WHATSAPP_DISPLAY = "+971 58 869 8578"
