# Talya P0 local remediation

Verified on 22 November 2026, Asia/Dubai, against the original app at
`/home/nagi/my-bench/apps/talya` and local site `talya.localhost`.
This follows `talya-communication-readiness-audit.md`; that historical audit is unchanged.

## Implemented and applied locally

### Recipient identity and consent

- A change to the canonical phone number clears WhatsApp consent, its timestamp,
  its phone binding, Patient verification, the linked Patient and the current
  WhatsApp profile. A checkbox submitted together with a number change cannot
  carry consent forward. Staff must obtain consent for the new recipient explicitly.
- Formatting changes to the same canonical number preserve valid verification
  and consent. Legacy consent without a phone binding cannot authorize a send.
- Verification and consent bindings are server owned; client fields/flags cannot
  manufacture verification. Booking and Patient creation require explicit staff
  confirmation of identity and authorization to use the number. Matching a phone
  number alone is insufficient proof of identity.
- A different-number Patient and a switch between Patients sharing a number are
  rejected before appointment insertion. Use a separate inquiry for a different
  Patient or to change the recipient of an already linked appointment.
- Incoming messages continue only one unambiguous eligible inquiry. Shared numbers,
  multiple requests, inconsistent Patient/appointment links and mismatched accounts
  cannot silently select the latest Patient. Ambiguity creates/reuses an unlinked
  WhatsApp inquiry for staff review, without automatically creating a Patient.
- Changing the recipient removes only this inquiry's link from the old profile.
  Historical messages and the old profile's Patient/other inquiry links are retained.
  The inquiry's conversation filters out messages belonging to the previous number;
  attachments uploaded before the recipient change cannot be reused for sending.
- The send policy checks current consent, recipient, verified Patient, appointment
  ownership and account alignment before using the official WhatsApp API.

### Calling code

The invalid local calling-code setting was corrected to **`971` (UAE)** through
the settings controller. The previous value is intentionally omitted. Normalization
now checks configuration explicitly; settings reject phone-shaped and unknown
calling codes. Local UAE, `+` international, `00` international, Arabic-digit and
Persian-digit inputs normalize to the expected canonical number. Public website
submission uses the same normalizer, without changing the page layout.

### Reception permissions

Only Talya Receptionist permissions and narrowly scoped Patient field permissions
were changed, using Custom DocPerm and Property Setter records, without editing
Healthcare source files.

| Record | Retained reception access | Removed reception privileges |
|---|---|---|
| Patient | Read scheduling demographics/contact data; explicitly create a Patient | Write, export, reports, print, email, share, delete |
| Patient Appointment | Read, create, write for scheduling | Export, reports, print, email, share, delete |

The same bulk/distribution privileges are disabled on the six scheduling lookup
DocTypes already used by reception. Existing restrictions are preserved instead of
broadening existing grants.

Fifteen Patient fields are isolated at permission level 9: identification number
(`uid`), blood group, patient details, allergies, medication, medical and surgical
history, occupation, marital status, tobacco/alcohol history, surrounding factors
and other risk factors. Reception cannot read these fields through the document
API or list queries. Existing clinician roles retain equivalent access to these
fields; Physician access was tested. Reception has no Patient Encounter read access.

Patient demographic lookup and appointment scheduling remain clinic-wide. Appointment
scheduling notes remain available to reception. No doctor/company scoping policy
was invented. Frappe permissions are additive: the clinic must review any additional
roles assigned to real reception users before introducing patient data. The helper
refuses to repurpose level 9 if an unrelated customization already uses it.

### Migration/backfill preservation

The migration hook now creates **missing inquiries only**. Repeated backfills return
without saving existing inquiries, preserving staff notes, contact corrections,
Patient/profile links, status and verification timestamps. Normal booking updates
also stop mirroring editable source data into existing inquiries; only explicit
appointment lifecycle fields synchronize, with Patient/recipient consistency checks.

### Local application

The three new inquiry fields were loaded with a targeted Talya DocType reload.
`talya.setup.apply_p0_local_configuration` applied the calling code and permission
changes and is guarded to run only on `talya.localhost`. No full Bench migration,
other app changes, cloud access, deployment, commit or push was performed.

## Verification

- **46 backend integration tests passed**, with zero failures/errors. The additional
  invalid/unknown calling-code cases also passed after the final validation adjustment.
  Coverage includes manual and public guest inquiry creation, Arabic number input,
  Healthcare availability/booking/idempotence/cancellation, explicit Patient creation,
  consent/opt-out, CSV/XLSX preview/import/deduplication, permissions, backfill, official
  send policy, duplicate incoming delivery, webhook signatures and mocked reminders.
- Focused negative cases cover substituted recipients, legacy/forged bindings,
  mismatched Patient numbers, shared-number Patient switches, ambiguous incoming
  routing, wrong appointment ownership, wrong accounts and old-recipient attachments.
- Tests use a synthetic transactional harness on the local database, with a savepoint
  and rollback per test. Commits, external HTTP, email, queueing, realtime publication
  and Healthcare SMS are blocked/mocked. Official Meta clients are mocked. No live
  WhatsApp account exists locally, and no messages were sent to real people.
- Record counts were unchanged after rollback. Final counts are zero for Patients,
  appointments, practitioners, schedules, appointment types, Gender, website requests,
  inquiries, WhatsApp accounts/profiles/messages/templates and message dispatches.
- **28 reception browser cases passed**: Chromium and WebKit, Arabic/English, widths
  360, 375, 390, 430, 768, 1024 and 1440. Actual template/assets with synthetic API
  fixtures verified translated identity confirmation, reset on Patient changes,
  blocked unchecked booking, explicit confirmation payload, RTL/LTR and no overflow.
  These browser fixtures do not create sessions or database records.
- Existing public Hero slider regressions passed in both engines at all seven
  widths, including both doctor identities, bilingual text, rapid controls, swipe,
  delayed/failed images and timer guards. Initial parallel runs encountered a page
  load timeout and timing assertion; subsequent runs with reduced contention passed.
- Python Ruff checks, JavaScript syntax checks, translation coverage and Git diff
  whitespace checks passed. All required new labels have English and Arabic text.
- Public homepage layout/assets and the historical audit are unchanged. All original
  modified/untracked application files remain present; no existing work was discarded.

Reproduce backend verification from the Bench directory without enabling the global
Frappe test runner or changing `allow_tests`:

```bash
PYTHONDONTWRITEBYTECODE=1 env/bin/python - <<'PY'
import os
os.chdir('sites')
import frappe
frappe.init(site='talya.localhost')
frappe.connect()
try:
    from talya.tests.test_inquiries import run_local
    print(run_local())
finally:
    frappe.db.rollback()
    frappe.destroy()
PY
```

The harness refuses another site or a site with a configured WhatsApp account.
Browser checks: `node talya/tests/recipient_safety.browser.cjs` and
`node talya/tests/hero_slider.browser.cjs`, from the app directory; repeat with
`TALYA_BROWSER=webkit`. Synthetic screenshots/logs are under `/tmp/talya-p0-*`,
outside the Git worktree.

## Files changed by this remediation

- `talya/recipients.py`, `talya/permissions.py` (new helpers).
- `talya/inquiries.py`, `talya/communication.py`, `talya/booking.py`, `talya/api.py`.
- `talya/setup.py`.
- `talya/talya/doctype/talya_patient_inquiry/talya_patient_inquiry.py` and `.json`.
- `talya/talya/doctype/talya_communication_settings/talya_communication_settings.py`.
- `talya/public/js/patient-inquiries.js`, `talya/inquiry_labels.py`, `talya/translations/ar.csv`.
- `talya/tests/test_inquiries.py`, new `talya/tests/test_recipient_safety.py` and
  `talya/tests/recipient_safety.browser.cjs`.
- This report. Other pre-existing changes remain unstaged and untouched by this task.

## Still needed locally

**Clinic-provided data:** approved Healthcare records for the actual doctors,
departments, Company-linked service units, working schedules/holidays, appointment
types/durations, Gender values and the legacy default appointment type. Confirm
website visibility/booking flags, reception user roles/scope, shared-number identity
verification procedures, consent/opt-out procedures and non-clinical template wording.
The public doctor portraits are not operational Healthcare practitioner records.

**Meta credentials and authorized setup:** official account/WABA identifiers, phone
number ID, app ID, access token, webhook signing secret/verification token, a reachable
HTTPS callback with subscriptions, approved confirmation/reminder templates and an
authorized test recipient. These were neither added nor connected. WhatsApp remains
unconfigured and reminders remain disabled.

**Outside this local P0 work:** actual text/template/media delivery and status round
trips, restored-database migration rehearsal, transport timeout/retry and reminder
error isolation, old webhook timestamp/timezone handling and the legacy availability
differences remain release work described in the audit. Synthetic tests do not prove
Meta transport or cloud readiness. This report does not authorize live activation.
