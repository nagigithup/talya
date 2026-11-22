"""Talya reception's scheduling access and clinical-field separation."""

import frappe
from frappe import _

RECEPTION_ROLE = "Talya Receptionist"
CLINICAL_LEVEL = 9
PATIENT_CLINICAL_FIELDS = (
	"uid",
	"blood_group",
	"patient_details",
	"allergies",
	"medication",
	"medical_history",
	"surgical_history",
	"occupation",
	"marital_status",
	"tobacco_past_use",
	"tobacco_current_use",
	"alcohol_past_use",
	"alcohol_current_use",
	"surrounding_factors",
	"other_risk_factors",
)


def ensure_reception_permissions():
	from frappe.permissions import add_permission, update_permission_property

	permissions = {
		"Patient": ("read", "create"),
		"Patient Appointment": ("read", "create", "write"),
		"Healthcare Practitioner": ("read",),
		"Appointment Type": ("read",),
		"Medical Department": ("read",),
		"Healthcare Service Unit": ("read",),
		"Company": ("read",),
		"Gender": ("read",),
	}
	for doctype, rights in permissions.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": RECEPTION_ROLE}):
			add_permission(doctype, RECEPTION_ROLE, ptype="read")
			for right in rights:
				update_permission_property(doctype, RECEPTION_ROLE, 0, right, 1)
		# Do not broaden existing custom access. Remove bulk/distribution privileges
		# from the reception role only, preserving other roles and owner restrictions.
		for name in frappe.get_all(
			"Custom DocPerm", filters={"parent": doctype, "role": RECEPTION_ROLE}, pluck="name"
		):
			row = frappe.get_doc("Custom DocPerm", name)
			changes = {
				key: 0 for key in ("export", "report", "print", "email", "share", "delete") if row.get(key)
			}
			if doctype == "Patient" and row.write:
				changes["write"] = 0
			if row.permlevel == CLINICAL_LEVEL:
				changes.update({"read": 0, "write": 0, "select": 0, "create": 0})
			if changes:
				row.update(changes)
				row.save(ignore_permissions=True)
	ensure_patient_clinical_permissions()


def ensure_patient_clinical_permissions():
	"""Property setters, not Healthcare source changes; preserve clinicians' access."""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter
	from frappe.permissions import setup_custom_perms

	meta = frappe.get_meta("Patient")
	# Reserve a separate level so no unrelated customized higher-level fields become
	# newly readable as a side effect of granting access to these clinical fields.
	if any(f.permlevel == CLINICAL_LEVEL and f.fieldname not in PATIENT_CLINICAL_FIELDS for f in meta.fields):
		frappe.throw(
			_(
				"Patient permission level 9 is already in use. Review clinical access before applying Talya permissions."
			)
		)
	setup_custom_perms("Patient")
	for base in [p for p in meta.permissions if p.permlevel == 0 and p.role != RECEPTION_ROLE and p.read]:
		filters = {
			"parent": "Patient",
			"role": base.role,
			"permlevel": CLINICAL_LEVEL,
			"if_owner": base.if_owner,
		}
		# An existing clinician restriction remains an administrator decision.
		if not frappe.db.exists("Custom DocPerm", filters):
			frappe.get_doc(
				{
					"doctype": "Custom DocPerm",
					**filters,
					"parenttype": "DocType",
					"parentfield": "permissions",
					"read": 1,
					"write": int(bool(base.write)),
				}
			).insert(ignore_permissions=True)
	for field in PATIENT_CLINICAL_FIELDS:
		definition = meta.get_field(field)
		if definition and not definition.permlevel:
			setter = make_property_setter("Patient", field, "permlevel", str(CLINICAL_LEVEL), "Int")
			setter.module = "Talya"
			setter.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Patient")
