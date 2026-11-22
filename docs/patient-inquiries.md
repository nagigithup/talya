# Talya Patient Inquiries

Reception URL: `/patient_inquiries` (Arabic), `/patient_inquiries?lang=en` (English).
The Talya Online Booking list also has a **Patient Inquiries** button.

## Workflow

Receive inquiry → verify WhatsApp consent → communicate → select a verified Patient → book a Healthcare appointment.

- Website requests keep their original `Talya Online Booking` record. A unique link creates one inquiry per request; migration backfills historical requests. Patient and appointment records are linked, never copied into a new clinical model.
- Manual entry, private CSV/XLSX import and official WhatsApp inbound messages use the same inquiry list. Filters cover status, source and patient name/mobile. Pagination shows 30 records.
- Inquiry statuses: New, Contacted, Awaiting Reply, Booked, Closed. Existing website statuses remain Pending, Confirmed, Rejected, Cancelled, Completed. Booking confirms the original request; cancellation closes the inquiry and cancels the request status.
- Matching uses E.164 numbers, including UAE local numbers and Arabic numerals. Several legitimate requests can share a phone number. Incoming messages continue one unambiguous eligible inquiry, including a verified booked thread. Ambiguous or shared-number messages create/reuse an unlinked WhatsApp inquiry for staff review. Shared numbers never auto-select a Patient.
- Changing a recipient clears consent, its timestamp and Patient/profile verification. A new recipient needs renewed consent and explicit Patient identity verification. Different Patients and recipient changes on booked requests require a separate inquiry. Backfill creates missing inquiries only and preserves existing staff edits.
- Creating a Patient is a separate, explicit action after checking authorized existing matches. Healthcare requires Gender, so it is requested only for a new Patient. No Patient is created during import or webhook ingestion.
- Availability comes from Healthcare's `get_availability_data`, including schedules, service units, holidays, leave and practitioner unavailability. Duration-aware slots are rechecked under Patient/practitioner/service-unit locks; Healthcare performs the final insert and overlap validation. Repeated booking of the same inquiry returns its linked appointment.
- Booking success offers a confirmation; it does **not** automatically send one. Appointment reminders are disabled by default and run every 15 minutes only when enabled with an approved template, a configured account and recorded consent.

## DocTypes and permissions

New application DocTypes:

| DocType | Purpose |
| --- | --- |
| Talya Patient Inquiry | The administrative request, contact number, requested service, status, consent/opt-out and links |
| Talya Communication Settings | Non-secret language, calling code, template and reminder preferences |
| Talya Message Dispatch | Durable send-request reservation and official message link; administrator access only |

`Talya Receptionist` and `System Manager` can access the inquiry interface. Settings are readable by reception and writable only by System Manager. Reception retains Patient demographic read/create and Patient Appointment read/create/write, plus scheduling lookups. Export, report, print, email, share and delete rights are removed from those scheduling roles; Patient write is disabled. Fifteen sensitive Patient fields use a separate permission level that preserves clinician access. Existing narrower rules, Frappe User Permissions and record checks still apply. Additional staff roles grant additive access and must be reviewed. No clinical encounter or lab-result access is granted. See `talya-p0-remediation.md` for the precise policy.

The original booking DocType is retained. Its staff confirmation/rejection methods refresh locked records and synchronize their inquiry. No Frappe, ERPNext, Healthcare or WhatsApp source files were modified.

## Official WhatsApp dependency

Latest local verification: Frappe 16.60.2, ERPNext 16.60.0, Python 3.14.3, Healthcare 16.7.0 and official WhatsApp 1.3.0.

- Repository: <https://github.com/frappe/whatsapp>
- Reviewed stable branch: `main`
- Tested upstream revision: `b32dfe2736a4a2bbaf2ab3f7c883fa31b43093a4`
- Declared WhatsApp compatibility: `>=16.0.0-dev,<18.0.0`.

The official app is installed **only on local `talya.localhost`**. It owns accounts, encrypted access tokens, templates, profiles, messages, transport, webhook processing, logs, statuses and conversation events. Talya calls its `get_messages`, `send_message`, `send_template` and profile APIs. The plain JavaScript reception UI renders their results; the upstream shared UI consists of raw Vue components requiring a separate Vue/Vite/Tailwind host, which this existing Talya application does not use. There is no alternate WhatsApp transport.

CRM is not installed on the current local Talya site and is **not** a dependency of this feature. No other application is included in this release.

Talya remains usable without WhatsApp via an explicit `wa.me` fallback. Opening that link does not send or acknowledge a message. The app does not declare WhatsApp as a mandatory dependency because the fallback must work without it. Embedded messaging requires the separate official app on the same production bench/site.

### Meta setup still required

No live Meta account or token was available. Configure these in the **official app**, not in Talya or Git:

1. In Meta, create/configure the business app and WhatsApp Business account. Obtain App ID, Business Account ID, Phone Number ID and a permanent system-user access token with the WhatsApp messaging/management permissions.
2. In **WA Settings**, set Webhook Verify Token and Webhook Secret (the Meta App Secret). In **WA Account**, create the active account and set the IDs and encrypted access token. Choose its Default Account in WA Settings. Talya displays that existing account instead of storing another copy.
3. Use HTTPS callback `https://<site>/api/method/whatsapp.whatsapp.webhook.handler`; subscribe to `messages` and `message_template_status_update` and subscribe the app to the business account. A local test needs an explicitly configured HTTPS tunnel; this task did not publish a tunnel.
4. Sync/create Meta-approved templates in **WA Template**. Select confirmation/reminder templates in Talya settings. Templates with variables must reference `Talya Patient Inquiry`; allowed mapped fields are `patient_name`, `preferred_date`, `preferred_time`, and `name`. Keep template text non-clinical. The account and template languages are managed by the official app.
5. Record genuine patient WhatsApp consent before sending. Website privacy consent is separate. STOP/unsubscribe and Arabic opt-out replies block contact. An opt-out on any inquiry for the number blocks API sends from the others.
6. Verify a real incoming message, reply, approved-template send, attachment, delivery/read event and consented reminder using an authorized test recipient before enabling production communication. No live send/delivery/read claims were verified here.

Signature validation is mandatory in Talya's request guard, including when the upstream webhook secret would otherwise be optional. An unconfigured/unsigned POST is rejected. The official handler processes verified payloads; a unique message-ID index and upstream duplicate handling prevent repeated webhook records. Outgoing policy runs during validation, **before** the official controller's send side effect. Free-form text requires an incoming message within 24 hours. File sends require a private File attached to that inquiry and authorized File access.

Send requests reserve a unique key and commit it before calling Meta through the official app. A crash or uncertain response leaves `Reserved`; it is never automatically retried. Reception must review official message history/logs before deliberately sending again. `Sent`, `Delivered` and `Read` are taken from official records/webhooks; no Meta message ID means Pending. Failed records remain visible. Reminder keys include the appointment and scheduled datetime, preventing repeated reminders for the same appointment occurrence.

**Upstream media limitation:** at the tested stable revision, incoming media is recorded as media ID/MIME/filename metadata; the official client does not expose an inbound-media download API. Talya shows that limitation rather than a broken download link. Outgoing private attachments use the official app's existing media-upload/send API. Full incoming-file download needs upstream support; no parallel downloader or messaging engine was added.

## Import

Upload a private, user-owned UTF-8 CSV or XLSX (under 2 MB, up to 1000 rows and 30 columns). Map Name and Mobile, then optionally Doctor (Healthcare Practitioner record ID), Service, Date and Notes. Dates should use ISO `YYYY-MM-DD`. Preview shows validation errors and duplicates before explicit confirmation. Invalid batches are rejected. Duplicates are skipped; no records are overwritten and no messages are sent. Same phone with a different service/date/notes can create another legitimate inquiry.

## Verification

Current verification is recorded in `talya-release.md` and `talya-p0-remediation.md`. `patient-inquiries-verification.md` is the historical November 8 run. Synthetic data is isolated or removed afterward. Meta HTTP calls are mocked in backend tests; browser conversation and available-slot fixtures are presentation tests, not live Meta evidence.

Useful commands:

```bash
bench --site talya.localhost execute talya.tests.test_inquiries.run_local
node apps/talya/talya/tests/recipient_safety.browser.cjs
TALYA_BROWSER=webkit node apps/talya/talya/tests/recipient_safety.browser.cjs
bench build --app talya
```

Browser tests require Playwright installed in Node's module search path, or `TALYA_PLAYWRIGHT_PATH` pointing to its module directory. All browser checks are restricted to `talya.localhost:8000`. The recipient-safety fixture checks need no login/session. The optional `inquiries.browser.cjs` live local manual/import test additionally requires an authorized temporary session file (`TALYA_TEST_SESSION_FILE`); never commit one. Screenshots stay in `/tmp` or the `TALYA_ARTIFACTS` directory.

## Production installation, after approval

Follow `talya-release.md` for the current GitHub release and cloud update instructions. The historical reports describe their own earlier execution scope. Cloud operations remain the site owner's responsibility; this local release does not activate live messaging.

1. Use the reviewed `nagigithup/talya` `version-16` commit identified in the release handoff.
2. Add the official WhatsApp app as a separate production dependency on the target Frappe 16 bench, using the reviewed stable revision or a separately verified compatible revision. Do not install CRM for this feature.
3. Back up the production site. Install WhatsApp on that site if embedded messaging is wanted, update the Talya app, run site migration and build assets:

   ```bash
   bench get-app https://github.com/frappe/whatsapp --branch main
   bench --site <site> install-app whatsapp
   bench --site <site> migrate
   bench build --app talya
   bench --site <site> clear-cache
   ```

   On Frappe Cloud, add both applications to the bench and use its normal update/migration/build process instead of running local deployment commands. Reconcile existing duplicate WA message IDs before applying the unique index if the official app already has historical duplicates.
4. Assign `Talya Receptionist` only to authorized staff. Review the supplied minimum scheduling permissions and any existing User Permissions. Preserve any intentionally narrower customized rules.
5. Configure actual active practitioners, their schedules/service units and Company, appointment types with positive durations, and Gender master values for new Patients. The local site initially had no practitioners, Patients or requests; test doctors/patients were not retained as production configuration.
6. Leave Meta accounts unconfigured and reminders disabled during this update. Real-number activation and reminder acceptance require separate clinic authorization and the verification described above. Keep authenticated inquiry HTML private and uncached by any external CDN.

Earlier development repairs to local process routing, Customer schema and tmux processes are not deployment configuration. Site settings, local hostnames, loopback overrides, sessions, uploads and secrets must not be copied into a cloud release.

## Files

- `talya/inquiries.py`, `communication.py`, `inquiry_import.py`, `inquiry_labels.py`
- `talya/talya/doctype/talya_patient_inquiry/*`, `talya_communication_settings/*`, `talya_message_dispatch/*`
- `talya/www/patient_inquiries.html`, `patient_inquiries.py`
- `talya/public/css/patient-inquiries.css`, `talya/public/js/patient-inquiries.js`
- `talya/hooks.py`, `setup.py`, `booking.py`, existing online-booking controller and list script
- `talya/translations/ar.csv`, inquiry backend/browser tests and this documentation

The public homepage HTML/CSS, doctor carousel and booking-form layout were not redesigned or modified.
