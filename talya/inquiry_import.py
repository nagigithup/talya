"""Private, preview-first CSV/XLSX imports. Never sends messages or overwrites."""

import csv
import hashlib
import io
import json

import frappe
from frappe import _
from frappe.utils import getdate

from talya.inquiries import INQUIRY, normalize_phone, require_reception

FIELDS = (
	"patient_name",
	"mobile_number",
	"healthcare_practitioner",
	"requested_service",
	"preferred_date",
	"notes",
)


def read_file(file_name):
	require_reception()
	file = frappe.get_doc("File", file_name)
	file.check_permission("read")
	if not file.is_private or file.owner != frappe.session.user:
		frappe.throw(_("Upload your own private import file."), frappe.PermissionError)
	content = file.get_content()
	if len(content) > 2_000_000:
		frappe.throw(_("Import files must be smaller than 2 MB."))
	if file.file_name.lower().endswith(".csv"):
		text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
		rows = list(csv.reader(io.StringIO(text)))
	elif file.file_name.lower().endswith(".xlsx"):
		from openpyxl import load_workbook

		book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
		try:
			if book.active.max_column and book.active.max_column > 30:
				frappe.throw(_("Import up to 1000 rows and 30 columns at a time."))
			rows = list(book.active.iter_rows(max_row=1002, max_col=30, values_only=True))
			while rows and not any(v is not None for v in rows[-1]):
				rows.pop()
		finally:
			book.close()
	else:
		frappe.throw(_("Choose a UTF-8 CSV or XLSX file."))
	if not rows or len(rows) > 1001 or any(len(row) > 30 for row in rows):
		frappe.throw(_("Import up to 1000 rows and 30 columns at a time."))
	return [[str(v or "").strip() for v in row] for row in rows]


@frappe.whitelist(methods=["GET"])
def columns(file_name):
	rows = read_file(file_name)
	return {"columns": rows[0], "sample": rows[1:6], "count": len(rows) - 1}


def prepare(file_name, mapping):
	rows = read_file(file_name)
	mapping = frappe.parse_json(mapping)
	if not isinstance(mapping, dict) or not all(k in mapping for k in ("patient_name", "mobile_number")):
		frappe.throw(_("Map Name and Mobile before previewing."))
	result, seen = [], set()
	for number, row in enumerate(rows[1:], start=2):
		if not any(row):
			continue
		data = {}
		try:
			for field in FIELDS:
				index = mapping.get(field)
				data[field] = (
					row[int(index)]
					if index not in (None, "") and int(index) < len(row) and int(index) >= 0
					else ""
				)
			data["normalized_phone"] = normalize_phone(data["mobile_number"])
			if len(data["patient_name"]) < 2:
				frappe.throw(_("Please enter the patient's full name."))
			if data["preferred_date"]:
				data["preferred_date"] = str(getdate(data["preferred_date"].split(" ")[0]))
			if data["healthcare_practitioner"]:
				frappe.get_doc("Healthcare Practitioner", data["healthcare_practitioner"]).check_permission(
					"read"
				)
			for field in ("patient_name", "requested_service", "healthcare_practitioner"):
				if len(data[field]) > 140:
					frappe.throw(_("A field exceeds the maximum length."))
			data["import_key"] = hashlib.sha256(
				json.dumps({**data, "mobile_number": data["normalized_phone"]}, sort_keys=True).encode()
			).hexdigest()
			duplicate = data["import_key"] in seen or bool(
				frappe.db.exists(INQUIRY, {"import_key": data["import_key"]})
			)
			seen.add(data["import_key"])
			# An identical pre-existing request is a duplicate; another service/date is legitimate.
			if not duplicate:
				duplicate = bool(
					frappe.db.exists(
						INQUIRY,
						{
							"normalized_phone": data["normalized_phone"],
							"patient_name": data["patient_name"],
							"requested_service": data["requested_service"],
							"preferred_date": data["preferred_date"] or ["is", "not set"],
							"healthcare_practitioner": data["healthcare_practitioner"] or ["is", "not set"],
							"notes": data["notes"],
						},
					)
				)
			result.append({"row": number, "data": data, "duplicate": duplicate, "error": None})
		except (frappe.ValidationError, frappe.DoesNotExistError, ValueError, IndexError) as exc:
			frappe.clear_last_message()
			result.append({"row": number, "data": data, "duplicate": False, "error": str(exc)})
	return result


@frappe.whitelist(methods=["POST"])
def preview(file_name, mapping):
	require_reception()
	return prepare(file_name, mapping)


@frappe.whitelist(methods=["POST"])
def import_rows(file_name, mapping, confirmed=False):
	require_reception()
	if str(confirmed).lower() not in ("1", "true"):
		frappe.throw(_("Preview and confirm the import first."))
	# Serialize imports on this site's single settings row; uniqueness also protects reruns.
	frappe.db.get_value("DocType", "Talya Communication Settings", "name", for_update=True)
	rows = prepare(file_name, mapping)
	if any(row["error"] for row in rows):
		frappe.throw(_("Correct invalid rows before importing."))
	created, skipped = [], 0
	for row in rows:
		if row["duplicate"]:
			skipped += 1
			continue
		doc = frappe.get_doc({"doctype": INQUIRY, **row["data"], "source": "Import", "status": "New"})
		doc.flags.integration_update = True
		doc.insert()
		created.append(doc.name)
	return {"created": len(created), "skipped": skipped}
