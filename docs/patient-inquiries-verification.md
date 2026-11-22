# Local verification — 2026-11-08

Target: `talya.localhost`, Frappe 16.54.0, Healthcare 16.7.0, official WhatsApp 1.2.0 stable `main` at `fa0ec60321f6577bf5e0ad8bafb6cbfa7133d35f`.

## Backend

`bench --site talya.localhost execute talya.tests.test_inquiries.run_local`: **16 tests passed**. Test data is rolled back; explicit dispatch commits are mocked inside the test transaction. Real Meta HTTP and SMS are blocked/mocked.

- International/UAE/Arabic-digit phone normalization; invalid numbers rejected.
- Manual inquiry creation/detail; guest access rejected.
- Website booking creates exactly one inquiry; Healthcare booking confirms the original request; cancellation synchronizes both statuses.
- Real Healthcare schedule/service-unit availability, conflicting appointments and Practitioner Availability exclusions.
- Duplicate booking retry returns the existing appointment.
- Authorized Patient matching; duplicate Patient creation blocked; explicit creation and linked-record tampering checks.
- A user with only Talya Receptionist can book; that user cannot configure WhatsApp secrets/settings.
- CSV duplicate preview, confirmed import and repeated-import deduplication; no messages during import.
- XLSX preview and invalid-row rejection.
- Official inbound webhook message processing links inquiries; duplicate events do not create another message; STOP sets opt-out.
- Incoming notification hooks are scoped to reception/admin users and contain no message content or contact details.
- Official outbound API invocation, consent, opt-out, 24-hour window, approved-template and rejected-template checks.
- Stable send request keys and retained Reserved state after an uncertain failure prevent automatic retries.
- Transport failure remains Failed; approved templates and opt-in reminders use the official client, mocked in tests; repeated reminders do not resend.
- Valid/invalid webhook HMAC signatures. A live HTTP POST without configured signature protection returns **401**.

## Browser and UI refinement

Chromium and WebKit each passed Arabic RTL and English LTR at **360, 375, 390, 430, 768, 1024 and 1440 px**: 28 language/viewport/engine cases.

Each browser run exercised real local manual entry, server validation feedback, consent save, private CSV upload, column mapping, duplicate preview and confirmed import. It also received an actual local Socket.IO event sent to its own temporary admin session and displayed the incoming-message toast. Synthetic inquiries and uploaded files were removed by authorized resource deletion afterward.

Conversation bubbles/statuses and appointment-popup options/slots used explicitly synthetic browser fixtures. They verify presentation, not actual Meta delivery or a real patient appointment in the browser. Appointment creation/availability were independently tested with real, isolated Healthcare records in the backend suite.

Reviewed rendered screenshots and refined message whitespace, mobile conversation navigation, modal sizing and logical RTL spacing. Verified no document/dialog horizontal overflow, no JavaScript page errors, LTR phone fields, readable Arabic/English messages, clickable controls, import/settings dialogs and booking popup. Desktop uses side-by-side inquiry/conversation panels; mobile uses one scrollable modal with detail/conversation navigation.

Representative screenshots (local artifacts, deliberately outside Git):

- `/tmp/talya-inquiry-browser/ar-390-list.png`
- `/tmp/talya-inquiry-browser/ar-390-conversation.png`
- `/tmp/talya-inquiry-browser/ar-390-booking.png`
- `/tmp/talya-inquiry-browser/en-1440-conversation.png`
- Equivalent views in `/tmp/talya-inquiry-browser-webkit/`.

The existing Chromium hero-slider regression passed all seven widths, five complete cycles per width, identity synchronization, exclusive portrait painting, rapid controls, bilingual text, swipe, delayed/failed image handling, stale callbacks, background resume and duplicate initialization. The public homepage and carousel source files were unchanged.

## Build, security and remaining external checks

- `bench build --app talya`: passed; translations compiled.
- Ruff for new/modified Python implementation/tests: passed.
- JavaScript syntax and Git whitespace checks: passed.
- UI translation keys and new server messages exist in the Arabic catalogue; duplicate translation entries were removed while preserving the original translations.
- No account tokens, webhook secrets, temporary sessions, private patient files or screenshots were added to Git.
- Temporary browser sessions are revoked after testing. Test doctors, Patients, appointments, WhatsApp accounts/messages and import data are not retained.

**Not verified live:** Meta inbound delivery, real outbound text/templates/media, real delivery/read callbacks and live reminders. Required account credentials, HTTPS webhook and Meta-approved templates must be supplied and tested with an authorized recipient. The stable official app records incoming media metadata but lacks an incoming-file download API; the UI shows that limitation. See `patient-inquiries.md` for setup and deployment instructions.

No commit, push or cloud deployment was performed.
