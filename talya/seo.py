"""Talya's public pages, language URLs and indexing policy.

This module reads only approved website profiles. It never reads Patient records,
changes Healthcare availability, or sends messages.
"""

import csv
import ipaddress
import re
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import frappe

from talya.website_content import (
	ADDITIONAL_PHONE,
	ADDITIONAL_PHONE_DISPLAY,
	APPROVED_ORIGIN,
	CLINIC_OPENING_HOURS,
	DENTAL_SERVICES,
	DOCTORS,
	LABELS,
	MAPS_URL,
	PAGE_SLUGS,
	PHONE,
	PHONE_DISPLAY,
	PUBLIC_BOOKING_ERRORS,
	PUBLIC_ROUTES,
	WHATSAPP_DISPLAY,
	WHATSAPP_URL,
)

PRIVATE_PATHS = (
	"/desk",
	"/app",
	"/api",
	"/login",
	"/patient_inquiries",
	"/desk_recovery",
	"/patient-portal",
	"/printview",
	"/private",
	"/me",
	"/update-password",
)


@lru_cache(maxsize=1)
def arabic_catalogue():
	with Path(frappe.get_app_path("talya", "translations", "ar.csv")).open(newline="") as source:
		return dict(csv.reader(source))


def translate(source, language):
	return arabic_catalogue().get(source, source) if language == "ar" else source


def labels_for(language):
	return {key: translate(source, language) for key, source in LABELS.items()}


def page_path(page, language):
	slug = PAGE_SLUGS[page]
	return f"/{language}" + (f"/{slug}" if slug else "")


def request_path():
	request = getattr(frappe.local, "request", None)
	return request.path if request else "/" + (getattr(frappe.local, "path", "") or "").lstrip("/")


def is_local_preview():
	return getattr(frappe.local, "site", None) == "talya.localhost"


def validated_origin(value):
	"""Never derive a production canonical or a redirect target from a Host header."""
	try:
		value = str(value or "")
		if any(character.isspace() for character in value):
			return None
		parts = urlsplit(value)
		if (
			parts.scheme != "https"
			or not parts.hostname
			or "." not in parts.hostname
			or parts.username
			or parts.password
			or parts.port not in (None, 443)
			or parts.path not in ("", "/")
			or parts.query
			or parts.fragment
			or parts.hostname.endswith((".localhost", ".local", ".invalid"))
		):
			return None
		try:
			ipaddress.ip_address(parts.hostname)
		except ValueError:
			pass
		else:
			return None
		hostname = parts.hostname.lower().encode("idna").decode("ascii")
		if len(hostname) > 253 or not all(
			re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in hostname.split(".")
		):
			return None
		return "https://" + hostname
	except (ValueError, UnicodeError):
		return None


def production_origin():
	return validated_origin(frappe.conf.get("talya_canonical_origin") or APPROVED_ORIGIN)


def canonical_origin():
	configured = production_origin()
	if configured:
		return configured
	if is_local_preview():
		return "http://talya.localhost:8000"
	return None


def redirect(target):
	query = getattr(getattr(frappe.local, "request", None), "query_string", b"")
	if query:
		target += "?" + query.decode("utf-8", errors="replace")
	frappe.local.flags.redirect_location = target
	raise frappe.Redirect(http_status_code=301)


def before_request():
	request = getattr(frappe.local, "request", None)
	if not request or request.method not in ("GET", "HEAD"):
		return
	path = request.path
	clean = path.rstrip("/")
	if clean.endswith(".html"):
		clean = clean[:-5]
	if clean not in PUBLIC_ROUTES:
		return
	# Choose HTML language from the route, never the browser, a query parameter,
	# a previous login, or localStorage. Both variants are stable for crawlers.
	frappe.local.lang = PUBLIC_ROUTES[clean][1]


def private_path(path):
	return any(path == prefix or path.startswith(prefix + "/") for prefix in PRIVATE_PATHS)


def after_request(response, request):
	if private_path(request.path):
		response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
	elif request.path in PUBLIC_ROUTES:
		response.headers["Content-Language"] = PUBLIC_ROUTES[request.path][1] + "-AE"
		if is_local_preview():
			response.headers["X-Robots-Tag"] = "noindex, follow"
	return response


def profile_key(practitioner):
	"""Match approved website identities, not private practitioner credentials."""
	image = urlsplit(practitioner.get("image") or "").path
	name = str(practitioner.get("name_en") or "").strip().casefold()
	name_key = None
	image_key = None
	for key, doctor in DOCTORS.items():
		images = {
			"/assets/talya/" + doctor["image"],
			"/assets/talya/" + doctor.get("optimized_image", doctor["image"]),
		}
		if image in images:
			image_key = key
		if name == LABELS[doctor["name_key"]].casefold():
			name_key = key
	# A copied portrait must not silently associate another practitioner's booking
	# record with a named doctor's profile. Conflicting identities fail closed.
	return name_key if name_key and image_key in (None, name_key) else None


def public_profiles(practitioners, language):
	labels = labels_for(language)
	profiles = {}
	for key, approved in DOCTORS.items():
		linked = next((row for row in practitioners if profile_key(row) == key), {})
		profile = {
			**approved,
			"key": key,
			"name": linked.get("name_" + language) or labels[approved["name_key"]],
			"name_en": linked.get("name_en") or LABELS[approved["name_key"]],
			"name_ar": linked.get("name_ar") or translate(LABELS[approved["name_key"]], "ar"),
			"specialty": linked.get("specialty_" + language) or labels[approved["specialty_key"]],
			"bio": linked.get("bio_" + language) or labels[approved["bio_key"]],
			"image_url": "/assets/talya/" + approved.get("optimized_image", approved["image"]),
			"path": page_path(key, language),
			"booking_path": page_path("home", language) + "?doctor=" + key + "#appointment",
			"practitioner": linked.get("id") or "",
			"booking_enabled": bool(linked.get("booking_enabled")),
			"language_names": [labels["arabic_language"] for code in approved["languages"] if code == "ar"],
			"nationality_display": translate(approved["nationality"], language),
			"summary": labels["sudanese_female" if key == "mehira" else "sudanese_male"],
		}
		profiles[key] = profile
	return profiles


def asset_versions():
	assets = (
		"css/talya.css",
		"css/public-pages.css",
		"js/talya.js",
		"js/public-page.js",
		"js/hero-slider.js",
		"images/dr-farouq.webp",
		"images/dr-mehira-original.webp",
		"images/talya-reception-styled.webp",
	)
	return {
		asset: sha256(Path(frappe.get_app_path("talya", "public", asset)).read_bytes()).hexdigest()[:12]
		for asset in assets
	}


def structured_data(page, language, origin, labels, profiles, title, description):
	if not origin:
		return None
	canonical = origin + page_path(page, language)
	clinic = {
		"@type": "MedicalClinic",
		"@id": origin + "/#clinic",
		"name": labels["clinic_name"],
		"alternateName": [LABELS["clinic_name"], translate(LABELS["clinic_name"], "ar")],
		"url": origin + page_path("home", language),
		"image": origin + "/assets/talya/images/talya-center-logo.jpeg",
		"telephone": PHONE,
		"address": {
			"@type": "PostalAddress",
			"streetAddress": labels["clinic_address"],
			"addressLocality": labels["city"],
			"addressRegion": labels["city"],
			"addressCountry": "AE",
		},
		"hasMap": MAPS_URL,
		"medicalSpecialty": ["https://schema.org/PrimaryCare", "https://schema.org/Dentistry"],
	}
	if CLINIC_OPENING_HOURS:
		clinic["openingHoursSpecification"] = CLINIC_OPENING_HOURS
	webpage = {
		"@type": "ProfilePage" if page in DOCTORS else "ContactPage" if page == "contact" else "WebPage",
		"@id": canonical + "#webpage",
		"url": canonical,
		"name": title,
		"description": description,
		"inLanguage": language + "-AE",
		"about": {"@id": clinic["@id"]},
	}
	graph = [clinic, webpage]
	if page in DOCTORS:
		doctor = profiles[page]
		person = {
			"@type": "Person",
			"@id": origin + "/#doctor-" + page,
			"name": doctor["name"],
			"alternateName": [doctor["name_en"], doctor["name_ar"]],
			"jobTitle": doctor["specialty"],
			"description": doctor["bio"],
			"url": canonical,
			"image": origin + doctor["image_url"],
			"worksFor": {"@id": clinic["@id"]},
		}
		if doctor["languages"]:
			person["knowsLanguage"] = doctor["languages"]
		if doctor["nationality"]:
			person["nationality"] = {"@type": "Country", "name": translate(doctor["nationality"], language)}
		webpage["mainEntity"] = {"@id": person["@id"]}
		graph.append(person)
	return {"@context": "https://schema.org", "@graph": graph}


def get_public_context(context, *, home=False):
	path = request_path()
	clean = path.rstrip("/")
	if clean.endswith(".html"):
		clean = clean[:-5]
	selection = PUBLIC_ROUTES.get(clean)
	if not selection or (selection[0] == "home") != home:
		raise frappe.DoesNotExistError(
			translate(LABELS["not_found"], "ar" if path.startswith("/ar/") else "en")
		)
	# Frappe's website renderer handles redirects here; raising them from a
	# before_request hook would produce an error page without a Location header.
	request = getattr(frappe.local, "request", None)
	configured = production_origin()
	if (
		configured
		and not is_local_preview()
		and request
		and request.host.lower() != urlsplit(configured).netloc
	):
		redirect(configured + clean)
	if clean != path:
		redirect(clean)
	page, language = selection
	frappe.local.lang = language
	labels = labels_for(language)
	from talya.api import _public_practitioners

	practitioners = _public_practitioners()
	profiles = public_profiles(practitioners, language)
	localized_profiles = {lang: public_profiles(practitioners, lang) for lang in ("en", "ar")}
	hero_profiles = [
		{
			"id": key,
			"image": profiles[key]["image_url"],
			**{
				lang: [
					localized_profiles[lang][key]["name"],
					localized_profiles[lang][key]["specialty"],
					labels_for(lang)["mehira_tagline" if key == "mehira" else "tagline"],
				]
				for lang in ("en", "ar")
			},
		}
		for key in ("farouq", "mehira")
	]
	for row in practitioners:
		key = profile_key(row)
		if key:
			row["profile_url"] = profiles[key]["path"]
			row["profile_key"] = key
	title_key = "gp" if page == "general_medicine" else page
	title = labels[title_key + "_title"]
	description = labels[title_key + "_description"]
	if page in DOCTORS:
		title = title.format(profiles[page]["name"])
		description = description.format(profiles[page]["name"])
	origin = canonical_origin()
	canonical = origin + path if origin else None
	image = profiles[page]["image_url"] if page in DOCTORS else "/assets/talya/images/talya-center-logo.jpeg"
	context.update(
		{
			"no_cache": 1,
			"sitemap": 0,
			"full_width": True,
			"title": title,
			"description": description,
			"page_kind": page,
			"language": language,
			"direction": "rtl" if language == "ar" else "ltr",
			"labels": labels,
			"home_path": page_path("home", language),
			"alternate_path": page_path(page, "en" if language == "ar" else "ar"),
			"contact_path": page_path("contact", language),
			"service_paths": {key: page_path(key, language) for key in ("general_medicine", "dental")},
			"dental_services": DENTAL_SERVICES,
			"profiles": profiles,
			"hero_profiles": hero_profiles,
			"practitioners": practitioners,
			"public_translations": {lang: labels_for(lang) for lang in ("en", "ar")},
			"asset_versions": asset_versions(),
			"csrf_token": frappe.sessions.get_csrf_token() if home else None,
			"maps_url": MAPS_URL,
			"phone": PHONE,
			"phone_display": PHONE_DISPLAY,
			"additional_phone": ADDITIONAL_PHONE,
			"additional_phone_display": ADDITIONAL_PHONE_DISPLAY,
			"whatsapp_url": WHATSAPP_URL,
			"whatsapp_display": WHATSAPP_DISPLAY,
			"seo": {
				"title": title,
				"description": description,
				"canonical_url": canonical,
				"robots": "noindex, follow"
				if is_local_preview()
				else "index, follow, max-image-preview:large",
				"alternates": {lang + "-AE": origin + page_path(page, lang) for lang in ("en", "ar")}
				if origin
				else {},
				"image": origin + image if origin else None,
				"json_ld": structured_data(page, language, origin, labels, profiles, title, description),
			},
		}
	)
	# Website Settings builds boot before the controller runs; keep the base <html>
	# language correct even if another app supplied a cached English context.
	if context.get("boot"):
		context.boot["lang"] = language
	if page in DOCTORS:
		context.doctor = profiles[page]
	if home:
		from talya.public_booking import browser_session

		browser_session(create=True)
		frappe.local.response_headers["Cache-Control"] = "private, no-store"
		for lang, catalogue in context.public_translations.items():
			catalogue["public_errors"] = [translate(source, lang) for source in PUBLIC_BOOKING_ERRORS]
		context.booking_genders = [
			{"value": value, "label": frappe._(value, lang=language)}
			for value in frappe.get_all("Gender", pluck="name", order_by="name")
		]
		key = str(frappe.form_dict.get("doctor") or "")
		context.selected_doctor = profiles.get(key, {}).get("practitioner", "")
		if key in profiles:
			context.alternate_path += "?doctor=" + key
	return context


def sitemap_links():
	origin = canonical_origin()
	return [origin + path for path in PUBLIC_ROUTES] if origin else []


def robots_text(existing=""):
	lines = [existing.strip(), "", "User-agent: *"] if existing.strip() else ["User-agent: *"]
	if is_local_preview():
		lines.append("Disallow: /")
	else:
		lines.extend("Disallow: " + path for path in PRIVATE_PATHS)
	origin = canonical_origin()
	if origin:
		lines.extend(("", "Sitemap: " + origin + "/sitemap.xml"))
	return "\n".join(lines) + "\n"
