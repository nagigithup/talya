"""Read-only signed-out checks: python -m talya.tests.seo_http.

The target is deliberately fixed to the original local Talya site. Patient and
appointment permission responses are checked without printing their payloads.
"""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from talya.website_content import PUBLIC_ROUTES

BASE = "http://127.0.0.1:8000"
HEADERS = {"Host": "talya.localhost:8000"}


def run():
	results = []
	titles, descriptions, origins = set(), set(), set()
	canonical_urls = set()
	with requests.Session() as session:
		for path, (page, language) in PUBLIC_ROUTES.items():
			response = session.get(BASE + path, headers=HEADERS, timeout=20, allow_redirects=False)
			assert response.status_code == 200, (path, response.status_code)
			soup = BeautifulSoup(response.text, "html.parser")
			assert soup.html["lang"] == language, path
			assert soup.html["dir"] == ("rtl" if language == "ar" else "ltr"), path
			assert len(soup.select("h1")) == 1, path
			assert len(soup.select('meta[name="description"]')) == 1, path
			assert not soup.select('meta[name="keywords"]'), path
			assert len(soup.select('link[rel="canonical"]')) == 1, path
			canonical = soup.select_one('link[rel="canonical"]')["href"]
			parts = urlsplit(canonical)
			assert parts.scheme == "https" and parts.netloc == "talyamedical.com", path
			assert parts.path == path and not parts.query and not parts.fragment, path
			canonical_urls.add(canonical)
			origins.add(parts.scheme + "://" + parts.netloc)
			alternates = {
				link["hreflang"]: link["href"] for link in soup.select('link[rel="alternate"][hreflang]')
			}
			assert set(alternates) == {"en-AE", "ar-AE", "x-default"}, path
			assert alternates[language + "-AE"] == canonical, path
			assert alternates["x-default"] == alternates["en-AE"], path
			for url in alternates.values():
				assert urlsplit(url).path in PUBLIC_ROUTES, url
			assert response.headers["Content-Language"] == language + "-AE", path
			# The original development site must remain outside Google's index.
			assert "noindex" in response.headers["X-Robots-Tag"], path
			assert "noindex" in soup.select_one('meta[name="robots"]')["content"], path
			assert len(soup.select('script[type="application/ld+json"]')) == 1, path
			data = json.loads(soup.select_one('script[type="application/ld+json"]').string)
			assert data["@context"] == "https://schema.org", path
			assert data["@graph"][0]["@type"] == "MedicalClinic", path
			assert data["@graph"][0]["telephone"] == "+971522207872", path
			assert "aggregateRating" not in json.dumps(data), path
			hours = data["@graph"][0]["openingHoursSpecification"][0]
			assert (hours["opens"], hours["closes"]) == ("16:00", "00:00"), path
			if page in ("mehira", "farouq"):
				assert data["@graph"][-1]["name"] == soup.h1.get_text(strip=True), path
				assert data["@graph"][-1]["knowsLanguage"] == ["ar"], path
				assert "government hospitals" not in data["@graph"][-1]["description"], path
				assert soup.select_one(f'a[href="/{language}?doctor={page}#appointment"]'), path
			if page == "home":
				for doctor in ("mehira", "farouq"):
					assert soup.select_one(
						f'.doctor-info h3 a[href="/{language}/doctors/dr-{doctor}-'
						+ ("fadl" if doctor == "mehira" else "ejami")
						+ '"]'
					), path
				assert soup.select_one("#booking-form"), path
				assert soup.select_one('meta[name="csrf-token"]'), path
				assert ("مستشفيات حكومية" if language == "ar" else "government hospitals") in soup.select_one(
					"#doctors"
				).get_text(), path
			if page == "dental":
				rows = soup.select(".service-prices tbody tr")
				assert len(rows) == 9, path
				assert [row.select_one("td").get_text(" ", strip=True) for row in rows[:2]] == (
					["150 درهم", "150 درهم"] if language == "ar" else ["AED 150", "AED 150"]
				), path
				assert all("800" not in row.get_text() and "450" not in row.get_text() for row in rows), path
			titles.add(soup.title.get_text())
			descriptions.add(soup.select_one('meta[name="description"]')["content"])
			results.append(
				{
					"path": path,
					"status": response.status_code,
					"language": language,
					"title": soup.title.get_text(),
					"canonical": canonical,
					"json_ld": "valid JSON",
					"initial_html": "PASS",
				}
			)
		assert len(titles) == len(descriptions) == 12
		assert len(origins) == 1

		response = session.get(BASE + "/sitemap.xml", headers=HEADERS, timeout=20)
		assert response.status_code == 200
		assert "xml" in response.headers["Content-Type"]
		xml = ElementTree.fromstring(response.content)
		links = {node.text for node in xml.findall("{*}url/{*}loc")}
		assert links == canonical_urls, "Sitemap must contain only the 12 canonical public URLs"
		robots = session.get(BASE + "/robots.txt", headers=HEADERS, timeout=20)
		assert robots.status_code == 200
		assert "Sitemap: " + next(iter(origins)) + "/sitemap.xml" in robots.text

		for source, target in (
			("/", "/en"),
			("/talya", "/en"),
			("/talya.html", "/en"),
			("/en/", "/en"),
			("/ar.html", "/ar"),
			("/talya?doctor=mehira", "/en?doctor=mehira"),
		):
			response = session.get(BASE + source, headers=HEADERS, timeout=20, allow_redirects=False)
			assert response.status_code == 301, (source, response.status_code)
			assert response.headers["Location"] == target, source
		for path in ("/talya_public", "/en/doctors/unknown", "/ar/services/implants"):
			assert session.get(BASE + path, headers=HEADERS, timeout=20).status_code == 404, path

		for path in ("/patient_inquiries", "/desk_recovery", "/desk"):
			response = session.get(BASE + path, headers=HEADERS, timeout=20, allow_redirects=False)
			# Frappe's Desk currently uses 301; Talya's staff pages use 302.
			# Keep the existing authentication routing while verifying access.
			assert response.status_code in (301, 302, 303), (path, response.status_code)
			assert response.headers["Location"].startswith("/login"), path
			assert "noindex" in response.headers["X-Robots-Tag"], path
		for doctype in ("Patient", "Patient Appointment", "Talya Online Booking", "Talya Patient Inquiry"):
			response = session.get(
				BASE + "/api/resource/" + doctype,
				params={"fields": '["name"]', "limit_page_length": "1"},
				headers=HEADERS,
				timeout=20,
				allow_redirects=False,
			)
			assert response.status_code in (401, 403), (
				doctype,
				"Guest record access was not denied",
				response.status_code,
			)
			assert "noindex" in response.headers["X-Robots-Tag"]
		# Query parameters cannot turn the Arabic URL into an English duplicate.
		response = session.get(BASE + "/ar/doctors/dr-mehira-fadl?lang=en", headers=HEADERS, timeout=20)
		soup = BeautifulSoup(response.text, "html.parser")
		assert soup.html["lang"] == "ar"
		assert urlsplit(soup.select_one('link[rel="canonical"]')["href"]).path == "/ar/doctors/dr-mehira-fadl"
	print(
		"PASS: 12 public URLs; initial HTML, metadata, reciprocal hreflang, XML sitemap, redirects, 404s and signed-out Patient/appointment access."
	)
	if output := os.environ.get("TALYA_SEO_REPORT_DIR"):
		directory = Path(output)
		directory.mkdir(mode=0o700, parents=True, exist_ok=True)
		(directory / "seo-http-results.json").write_text(
			json.dumps(results, ensure_ascii=False, indent=2) + "\n"
		)
	return results


if __name__ == "__main__":
	run()
