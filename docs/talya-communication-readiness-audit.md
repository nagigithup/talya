# Talya Patient Communication, WhatsApp & Healthcare Readiness Audit

**Audit date:** 22 November 2026, Asia/Dubai.<br>
**Application:** original `talya`, `/home/nagi/my-bench/apps/talya`.<br>
**Verified local site:** `talya.localhost`.<br>
**Execution:** audit only. No fixes, settings changes, installations, migrations, database mutations, messages, Git commits/pushes, or deployments were performed. This report is the only application file created or modified by the audit. `nagi_chat` was not inspected or modified.

## 1. Executive summary

**The system is not ready for the requested complete reception demonstration, connection of the real WhatsApp number, or production release.** The website and much of the application code exist, but the operational prerequisites are absent. There are also confirmed safety/reliability issues that configuration alone will not resolve.

- The official WhatsApp app is installed and its APIs import successfully, but there are **zero WA Accounts, templates, profiles, messages and dispatches**. No Meta credentials or webhook verification/signing tokens are configured. No live Meta exchange was verified.
- Healthcare has **zero practitioners, schedules, appointment types, Patients and appointments**, no leaf service units and no Gender master values. The two doctors shown publicly are static website profiles, not configured Healthcare records.
- The stored country-calling-code setting is invalid: it contains a phone-number-shaped value instead of a calling code. Its value is intentionally redacted. A valid local UAE number fails normalization with the actual setting; the same input works with `971` supplied only to an in-memory test stub.
- **Confirmed patient-safety defect:** changing an inquiry's phone number preserves its prior WhatsApp consent, consent timestamp and linked Patient. An in-memory controller probe reproduced this without saving a record. This creates a wrong-recipient disclosure risk once sending is enabled.
- Reception currently has unrestricted level-zero Patient read/create and Patient Appointment read/create/write permissions, including **export** permission. There are no User Permission restrictions. The intended access policy needs review before real patient data is introduced.
- Six tracked Talya files are modified and 23 files are untracked before this report. The communication module is not in the current GitHub branch tip. The observed cloud site's inquiry page and new assets return 404.

**Evidence-based local readiness score: 50% — 10/20 equally weighted gates satisfied.** This measures implementation plus operational readiness, not the percentage of messaging that works. Safety and configuration blockers veto release regardless of score. Seven gates pass, six receive half credit, and seven fail or remain unverified; see the scoring table below.

### Readiness scoring criteria

1 = prerequisite verified in the current environment; 0.5 = implementation/presentation verified but its state-changing workflow not currently verified or configured; 0 = missing, unsafe, blocked or unverified release prerequisite.

| Gate | Score | Current evidence |
|---|---:|---|
| 1. Compatible framework/Python/app versions | 1 | Installed versions satisfy the declared local version ranges |
| 2. WhatsApp installation, DocTypes and integration imports | 1 | Installed app, expected DocTypes and five callable integration imports verified |
| 3. Declared patches and Talya/WhatsApp field schemas | 1 | No pending Patch Log entries or missing stored fields found in the inspected app schemas |
| 4. Current local runtime assets | 1 | All 93 inspected framework/ERPNext/Healthcare bundle targets exist; runtime Talya assets present |
| 5. Public website and synchronized doctor slider | 1 | Current Chromium and WebKit regression checks pass |
| 6. Guest inquiry restrictions/basic public validation | 1 | Current non-mutating API/helper probes pass |
| 7. Inquiry creation and website synchronization | 0.5 | Controllers/hooks present; actual write flow not rerun; no records available |
| 8. Reception UI | 0.5 | 28 current bilingual presentation cases pass with synthetic GET fixtures; authenticated live workflow not rerun |
| 9. Import workflow | 0.5 | Preview/mapping/deduplication code and UI exist; actual upload/import requires writes |
| 10. Correct phone normalization configuration | 0 | Current local-number probe fails |
| 11. Actual Healthcare master data | 0 | Required practitioner/schedule/type/unit/Gender configuration absent |
| 12. Healthcare booking and status transitions | 0.5 | Code path reviewed; current insert/cancel/reschedule flows not executed |
| 13. Configured WhatsApp account and credentials | 0 | No account/default account/credentials |
| 14. Reachable, verified Meta webhook | 0 | Localhost is not publicly reachable; no configured public local callback or Meta verification |
| 15. Incoming/outgoing conversation transport | 0.5 | Official API integration exists; in-memory signature checks pass; no actual transport evidence |
| 16. Approved templates and confirmation configuration | 0 | No templates or confirmation selection |
| 17. Reminder workflow | 0.5 | Scheduler registration exists; reminders disabled, template/account absent |
| 18. Recipient/consent safety for live patient communication | 0 | Consent/Patient linkage survives recipient change |
| 19. Local scheduler/worker infrastructure | 1 | Scheduler enabled and job registered; one current idle worker covers short/default/long; observed queues empty |
| 20. Reproducible cloud release artifact | 0 | Required code/assets untracked; observed cloud inquiry artifacts absent; private cloud checks unverified |
| **Total** | **10 / 20 = 50%** | Operational and safety blockers remain |

## 2. Local environment

### Inventory

Bench: `/home/nagi/my-bench`; Python **3.14.3**. HTTP development server listens on port 8000, Socket.IO on 9000, cache Redis on 13000 and queue Redis on 11000.

| Installed on Talya site | Version | Branch | Local revision |
|---|---|---|---|
| Frappe | 16.60.2 | version-16 | `2df0425571` |
| ERPNext | 16.60.0 | version-16 | `886ab6ae18` |
| Talya | 0.0.1 | version-16 | `83bdc15` |
| Healthcare | 16.7.0 | version-16 | `5530f48` |
| Official WhatsApp | 1.3.0 | main | `b32dfe2736a4a2bbaf2ab3f7c883fa31b43093a4` |

These five apps are the actual installed-app list. CRM is **not currently installed on this site**; earlier documents describe an older environment. No app was installed or removed during this audit.

Site directories found: `helohala.localhost`, `tagstock.localhost`, `adan.local`, `dev.localhost`, `restaurant.local`, `pos-settlements-test.localhost`, and `talya.localhost`. Directory presence does not prove every other site is actively served; they are outside scope.

Talya declares Frappe/ERPNext/Healthcare `>=16.0.0-dev,<17.0.0` and Python `>=3.14`. Installed WhatsApp declares Frappe `>=16.0.0-dev,<18.0.0` and Python `>=3.14`. No declared-range incompatibility was found. This is not certification of every upgraded API: the original integration was previously tested against older Frappe/WhatsApp versions, and its full write tests need a separately authorized rerun.

`phonenumbers`, `openpyxl`, `requests`, `flit_core` and Pillow are importable. The official `get_messages`, `send_message`, `send_template`, webhook handler and Talya reminder function all resolve. The official UI package contains raw Vue source, not a compiled conversation bundle. Talya uses its own plain-JavaScript panel over the official APIs, so the unused Vue package does not need to be built for this interface.

### Git and assets

Remote: `https://github.com/nagigithup/talya.git`. Local branch and remote `version-16` both point to `83bdc154d792d0743658a0474a4d6a940cc72479` (`fix(talya): align Arabic section headings and booking introduction`). This was checked with read-only `ls-remote`, not fetch/pull.

Before this report: **6 modified tracked files and 23 untracked files**. Modified: `talya/booking.py`, `hooks.py`, `setup.py`, `public/js/talya_online_booking_list.js`, the online-booking controller and `translations/ar.csv`. Untracked: the communication/inquiry/import modules, labels, two reception assets, three new DocTypes/controllers, reception and recovery pages, two tests and the two earlier documentation files. This report adds one more untracked file. No changes were staged.

All seven existing public image files exist and are tracked: `dr-farouq.png`, `dr-mehira-original.webp`, `talya-logo.svg`, `talya-logo-white.svg`, `talya-mark.svg`, `talya-reception-styled.png`, and `talya-reception.webp`. Service and statistics icons are SVG symbols/code. No patient-upload files are needed for these static assets. The reception CSS/JS exist locally and are not ignored, but are **not tracked yet**. The apparent `logo.png` reference is in a commented-out hooks example, not an active asset dependency.

All 93 inspected bundle-manifest targets exist. Homepage and public data GETs return 200. Browser regressions decode both portraits successfully. These facts establish current assets exist and can render; **no build was run**, so a clean release build is not newly verified by this audit.

### Migrations, scheduler and local settings

- Declared patches compared with successful Patch Log entries: **0 pending**. Stored-field checks against current Talya and WhatsApp DocType JSON: **0 missing DocTypes/columns**. This does not prove every future migration hook is safe or replace a full schema/type/index migration rehearsal.
- `unique_message_id` exists on WA Message, with a unique index. Website booking and import-key uniqueness are declared in the Talya schemas.
- Scheduler enabled; not paused; maintenance off. `talya.communication.reminders` registered, not stopped, cron `*/15 * * * *`, with last execution recorded on the audit day. Execution alone does not mean a message was sent: the routine returns immediately when disabled/unconfigured.
- One worker with a current heartbeat handles Bench-prefixed short/default/long queues; it was idle and all three queues were empty. Nine other Redis worker registrations have old heartbeats/no queues; they are stale registrations, not evidence of nine functioning workers. No job was enqueued for this audit.
- Timezone `Asia/Dubai`; developer mode enabled; CSRF protection not disabled; site encryption key present. `allow_tests` is false. No local `host_name` is configured.
- Desk home is `workspace`, and framework/ERPNext setup is complete. The previously repaired setup-wizard default has not reverted. Authenticated Desk stability was not retested with a newly created session because session creation modifies records.
- Local backup directory contains **0 files**. Off-host/local external backups and production backups were not verified.

## 3. Feature inventory

“Verified” distinguishes runtime/read-only evidence from source inspection and synthetic presentation tests. It never means live Meta delivery unless explicitly stated; none was verified here.

| Feature | Implemented | Verified | Issue | Action required |
|---|---|---|---|---|
| Bilingual public homepage, RTL/LTR and responsive hero | Yes | Current Chromium/WebKit regressions and rendered mobile review | None found in audited layout paths | Preserve in release regression |
| Doctor carousel identity synchronization | Yes | Both portraits/names/specialties across seven widths and five cycles per width per engine | Static profiles are not Healthcare practitioner records | Configure real masters separately |
| Services/contact/map/public WhatsApp actions | Yes | Template/source review, working homepage; external message links not followed | Public contact buttons launch external WhatsApp; no sending/delivery integration evidence | Verify clinic contact data with owner before demonstration |
| Appointment form/guest validation | Yes | Current helper checks and public data GET; no submission | No public approved doctors/departments; booking UI remains configuration-gated | Configure masters and authorize isolated submission test |
| Guest protection/rate limit | Yes | Guest read/API checks; POST-only endpoints and five-per-hour booking limiter reviewed | Current public phone regex accepts ASCII digits, unlike inquiry normalization | Test/decide Arabic-digit input support; load/rate-limit execution not performed |
| Privacy consent | Yes | Public consent requirement and inquiry consent fields reviewed | Website processing consent is separate from WhatsApp consent; recipient-change flaw below | Repair consent binding before live use |
| Website request → inquiry | Yes | `after_insert`/`on_update` hooks registered; unique website link exists in schema | No current requests to verify; migration synchronization overwrites existing inquiry fields | Isolated E2E verification and preservation fix |
| Manual inquiry | Yes | Actual template/controllers reviewed; synthetic UI renders | Current local phone setting breaks ordinary UAE local-number entry | Correct setting after approval; rerun create tests |
| CSV/XLSX import/mapping/preview | Yes | Source and modal presentation only | Actual imports not run; same phone is allowed for different legitimate requests | Authorize isolated import tests after configuration repair |
| Import duplicate detection | Yes | Exact-data hash, unique key, repeated rows and existing-record comparison reviewed | Deduplication is not “one inquiry per phone”; XLSX import caps reading at 30 columns | Explain matching rules; reject or disclose truncated extra columns |
| Patient search/matching | Yes | Permission-filtered queries and normalized matching reviewed | Patient table empty; current country code affects local-number matching; scan loads all readable Patients | Configure data, test access and consider indexed normalized matching |
| Customer search | No dedicated feature | Lookup whitelist reviewed | Patient lookup only; no Customer search in reception UI | Clarify whether actually needed |
| Inquiry assignment | No dedicated reception feature | Schema/UI reviewed | No assignee/filter/assignment workflow in custom interface; generic Desk assignment is separate | Add only if clinic needs individual ownership |
| Statuses/internal notes | Yes | New/Contacted/Awaiting Reply/Booked/Closed in schema/UI | One editable Notes field; original preferred values replaced by booked values; migration can overwrite notes | Preserve source request/audit history and staff notes |
| Contact history | Partial | Official message query reviewed | Scoped to one inquiry; no unified history across repeat inquiries; no telephone-contact activity UI | Decide conversation/thread model |
| Conversation panel/composer/templates | Yes | Current presentation fixtures pass; actual route is authenticated | Actual composer hidden while account unconfigured; no live records | Configure account/templates and run end-to-end tests |
| Unread workflow | No persistent custom UI workflow | UI/schema inspection | Toast and delivery labels do not provide staff unread counts/acknowledgements | Reception usability improvement |
| Patient/appointment links | Yes | Links, booking action and success UI reviewed; synthetic slot chooser renders | No current Patient/appointment exists; no current write-path verification | Authorized isolated booking demonstration |
| Cancellation/rescheduling | Partial | Healthcare status hook reviewed | Cancelled linked appointment remains attached; `book()` returns any existing linked appointment, so rebooking requires a defined workflow | Test and define reception rebooking/rescheduling steps |
| WhatsApp confirmations | Yes, manual offer | UI success/offer path and settings reviewed | No selected approved template/account; no automatic confirmation promised | Configure then test real authorized recipient |
| Reminders | Yes, opt-in | Job registration/current settings/source reviewed | Disabled; no account/template; no real run tested | Fix safety issues, configure, then explicitly authorize enablement |
| Realtime notifications | Yes | Hooks and listening process exist; synthetic UI stubs only during audit | No authenticated Socket.IO delivery was emitted/tested | Authorized reception-session notification test |

### Current DocTypes

- **Talya Patient Inquiry:** patient/contact, normalized phone, practitioner/service, preferred date/time, source/status, notes, unique website/import links, Patient/Appointment links, WhatsApp consent timestamp/opt-out and profile reference. `track_changes` is enabled. Source/link fields are protected by controller checks; role-based read/write/create applies. Patient/profile changes use internal integration flags.
- **Talya Communication Settings:** country calling code, message language, confirmation/reminder template names, reminder enable/timing and consent requirement. Reception can read; only System Manager can write. Official account/credential management is reused rather than duplicated here. Current country-code value is invalid despite a controller validation rule; how that value was originally written was not determined.
- **Talya Message Dispatch:** inquiry, unique hashed request key, official message name and Reserved/Completed state. Administrator role access only. This is an idempotency ledger, not a second messaging engine. Official WA Message owns delivery/failure details.
- **Talya Online Booking:** existing workflow retained: Pending/Confirmed/Rejected/Cancelled/Completed, privacy-consent timestamp, staff notes/rejection reason and Patient/Appointment links. Confirmation/rejection acquire locks and synchronize an inquiry. There is no dedicated new-website-request reception notification hook; rows appear when the list refreshes/polls.

## 4. WhatsApp readiness

The [official repository](https://github.com/frappe/whatsapp) documents the stable `main` installation and its Business Cloud API/webhook architecture. The installed source at the revision above was treated as authoritative for implementation details; upstream `develop` is not assumed identical.

| Component | Status | Evidence | Required action |
|---|---|---|---|
| Official WhatsApp App | Installed; declared-compatible | 1.3.0/main; site installed-app list; expected DocTypes/imports exist | Pin/test a chosen production revision; rerun integration after approval |
| WA Settings | Partially populated defaults | API URL `https://graph.facebook.com`, API version `v23.0`; verify/signing tokens absent | Configure official settings and check supported Meta API version for the chosen account |
| WA Account | Not configured | 0 records; no default account | Create/activate authorized official account |
| Meta Credentials | Missing; no validity check possible | No account means App ID, WABA ID, Phone Number ID and access token absent; verify token and App Secret absent | Obtain approved credentials; keep secret values out of Git/report |
| Webhook | Implemented; not connected | Official `/api/method/whatsapp.whatsapp.webhook.handler`; challenge/signature memory probes pass | Configure HTTPS callback, token, App Secret, subscriptions and authorized reachability test |
| Incoming Messages | Implemented, not Meta-verified | Official handler creates/submits WA Message and calls Talya hook; 0 message records | Resolve routing/shared-number risks; test a real authorized sender |
| Outgoing Messages | Implemented, not configured/Meta-verified | Talya calls official send functions; 0 dispatches/messages | Fix consent binding; configure and verify text/template responses and failures |
| Conversation UI | Presentation verified only | 28 synthetic bilingual viewport/engine cases pass | Authenticate reception and test actual data/API/realtime behavior |
| Templates | Not configured | 0 WA Templates; no confirmation/reminder selection | Sync approved non-clinical templates and map parameters |
| Appointment Confirmation | Code implemented, operationally blocked | Explicit post-booking offer; no automatic send | Complete Healthcare setup plus account/template/consent setup |
| Reminders | Implemented, disabled | Every-15-minute job; timing 24 hours; enable flag 0 | Do not enable until recipient, timing, failure and duplicate tests pass |

### Trace of the messaging paths

1. **Send:** UI `bindComposer()` → authenticated POST `talya.communication.send` → reception/record write checks → consent/global opt-out/configuration checks → unique dispatch reservation → normalized official profile → attachment/reference/template/24-hour checks → durable reservation commit → official `send_message`/`send_template` → official WA Message → dispatch completed. Explicit commit means this endpoint cannot be safely invoked as a “read-only test.” Reserved outcomes are not automatically retried. Changing the request key is a new send; operators need a documented uncertain-send review procedure.
2. **Receive:** Meta POST → Talya `before_request` requires an App Secret and calls official HMAC validation → official handler resolves an account/profile, locks profile and creates WA Message → Talya `incoming()` picks the most recently modified inquiry for that phone with status neither Booked nor Closed, or creates a New inquiry → profile/reference links → notifications. No Patient is automatically created by incoming messages.
3. **History:** Talya requests official `get_messages` for **only the selected inquiry**. Official reference read checks and reception access guard run; messages sort by database creation/name. A later inquiry for the same phone does not automatically show earlier inquiry history.
4. **Attachments:** outgoing requires a readable private File attached to that inquiry, then official upload/send. Incoming records media IDs/MIME/filename metadata; the installed official client has an upload API but no inbound media-download API. Talya honestly shows that limitation. No actual media was sent/downloaded in this audit.
5. **Statuses:** official webhook supports Sent/Delivered/Read/Failed; Talya displays those records and leaves an unacknowledged send Pending when no message ID is present. Upstream status code overwrites by arrival order; a late Delivered event can regress a Read state. This was source-reviewed, not replay-tested against Meta.
6. **Realtime:** official document-scoped `whatsapp_message` plus Talya user-scoped `talya_inquiry` events; minimal Talya payload omits message body/contact number. UI subscribes to the selected inquiry and polls every 20 seconds as fallback. No current live authenticated notification test was performed.
7. **Templates:** approved status, account association, reference mapping and a non-clinical field allowlist are checked. Allowed inquiry parameter fields: `patient_name`, `preferred_date`, `preferred_time`, `name`. System Managers must still review template text/headers/media; a field allowlist alone cannot guarantee safe wording.

### Webhook security and reachability

Talya's active request hook makes signatures mandatory even though the official handler permits an unset secret by itself. The guard/import/hook registration was verified. In-memory valid/invalid HMAC and challenge-response tests were performed with dummy secrets and logging patched out. **No live POST or successful live verification GET was sent**, because these code paths can create logs/messages and violate this audit's write restrictions.

The local address is plain HTTP on `.localhost`; it is **not reachable by Meta**. No public local hostname/tunnel is configured or verified. A publicly reachable HTTPS callback, Meta messages/template-status subscriptions and business-account app subscription are still required. The observed cloud domain being HTTPS does not establish that its WhatsApp app/webhook is installed or configured. Existing webhook settings were not changed.

Official duplicate handling checks message IDs and locks profiles; the local unique message-ID index provides a further database safeguard. The duplicate precheck occurs before profile locking, so concurrent duplicates may still surface an index exception before a later retry is recognized. A unique index prevents a duplicate persisted row, not necessarily a clean concurrent webhook acknowledgement. This requires an authorized concurrency test.

## 5. Healthcare booking readiness

**Reception cannot complete the real end-to-end workflow in the current local data state.**

| Required master/configuration | Actual local result |
|---|---|
| Healthcare practitioners | 0 |
| Practitioner schedules | 0 |
| Appointment types | 0 |
| Leaf Healthcare service units | 0 |
| Gender values for required new-Patient field | 0 |
| Patients / appointments | 0 / 0 |
| Existing website requests / inquiries | 0 / 0 |
| Companies | 1, but no default Company configured |
| Healthcare default appointment type | Not configured |

Company can be derived from a configured service unit in the inquiry path; absence of a global default alone need not block that path. Here, service units are also absent. The legacy website confirmation path additionally requires the Healthcare default appointment type.

The public homepage's Dr. Farouq/Dr. Mehira profiles exist in template/assets. No corresponding live Healthcare records were found. The public data endpoint currently returns empty practitioners/departments; the configuration warning/disabled booking state is appropriate. No previously configured doctors were assumed to exist.

### Workflow source review

- **Website request:** validates patient name/mobile/date/time/privacy consent and public practitioner flags. It creates a Pending request, not a confirmed appointment. If configured slot list is empty the API does not enforce membership in that list; an unavailable preferred time can therefore be requested but is not automatically booked.
- **Inquiry synchronization:** registered hooks create/reuse a uniquely linked inquiry. This could not be exercised on existing records because none exist; no synthetic records were inserted.
- **Patient:** permission-filtered normalized-phone matching; multiple candidates require staff selection. New Patient creation is explicit, checks current authorized matches and locks the Patient DocType. A Patient can only be created after Gender values and ordinary Healthcare prerequisites are available.
- **Inquiry booking:** uses Healthcare `get_availability_data`, calculates duration-aware slots, locks inquiry/request/Patient/practitioner/service unit, rechecks availability and lets Healthcare validate/insert. It links the appointment, updates preferred slot/practitioner to actual booked values and confirms a linked website request. Repeat calls return an existing appointment link.
- **Legacy booking confirmation:** has a separate `talya.booking.get_available_slots` implementation. It filters exact booked start times, not full overlapping durations, and omits the Healthcare availability API's employee holiday/leave logic. Healthcare insert still validates overlaps/practitioner unavailability, but the two availability paths are not equivalent. Unify or explicitly verify their behavior before release.
- **Appointment update/cancel:** hook updates inquiry date/time/practitioner/status and linked request status. Rebooking is not a separate custom UI action; the existing appointment link is returned even if that appointment has been cancelled. Rescheduling should be performed through an authorized Healthcare record and tested for consistent links/templates.

### Confirmation/reminder review

No automatic confirmation is sent merely by booking. The success popup offers a conversation action and preselects the configured confirmation template. Those prerequisites are absent.

Reminders check enabled flag, selected template, configured account, inquiry Booked status, consent/opt-out, appointment cancellation/closure and a future datetime inside the configured window. They run as Administrator and call the same guarded official send adapter. The dispatch key includes appointment and scheduled datetime to suppress repeated sends for that occurrence. A rescheduled datetime becomes a new key. Failed/uncertain deliveries require manual review; no automatic retry strategy is implemented.

The site timezone is Dubai and appointment dates/times are combined locally. Cross-timezone/UTC boundary behavior was not exercised. The free-text service window uses **database message creation time**, not Meta's original incoming timestamp, so a delayed old webhook can incorrectly appear to reopen a 24-hour window. The upstream timestamp conversion also uses the host's local timestamp convention; timezone handling requires a targeted test.

The reminder loop fetches an appointment and parses its time outside its per-message try/except; one broken link/date can abort the remaining batch. The official HTTP client does not set an explicit request timeout. These are reliability risks, not evidence that a current reminder failed; reminders are disabled and there are no appointments.

## 6. Security and reliability findings

**Critical:** none confirmed. There are no local patient/message records and no configured live transport, so this audit did not observe an actual patient-data disclosure. The following High findings must still block activation.

| ID | Severity | Finding and evidence | Required action |
|---|---|---|---|
| S1 | **High** | **Consent and Patient link survive recipient change.** `save_inquiry` allows changing `mobile_number`; inquiry controller retains consent timestamp whenever old consent is true and leaves Patient link intact. In-memory current-controller probe confirmed all three retained after number change. `send()` subsequently resolves a profile for the new number. Evidence: `talya/inquiries.py:save_inquiry`, inquiry controller `validate`, `communication.py:send`. | Bind consent to normalized recipient; require renewed verification/consent after recipient changes; reconcile Patient/profile/appointment links before sending. Add a negative regression test. |
| S2 | **High — configuration** | **Invalid country calling code breaks UAE local-number workflows.** Actual value redacted; current normalization raises ValidationError for a valid local-format input. International-format input succeeds. | Replace with the verified calling code only (UAE `971`) after approval; investigate why persisted data bypassed validation; retest manual/import/matching. |
| S3 | **High — privacy/routing risk** | Incoming messages are matched only by phone to the latest modified open inquiry; multiple same-phone inquiries/shared family numbers are not disambiguated. Booked/Closed inquiries are excluded, so replies after booking create another inquiry and disappear from the original selected thread. `communication.py:100–129`, `conversation()`. | Define a stable conversation/profile-to-patient/inquiry policy; protect ambiguous/shared-number cases; provide an explicit reception link/relink choice and continuity after booking. |
| S4 | **High — data preservation** | `after_migrate()` calls `sync_booking()` for every website request. That function unconditionally overwrites existing inquiry notes, contact fields and Patient link from the original booking. Reception-edited notes or a Patient linked before confirmation can be lost. No data was mutated to demonstrate it; assignment statements are explicit in source. | Backfill missing inquiries only or synchronize authoritative fields selectively; preserve reception edits and verified links; test migration on representative restored data. |
| S5 | Medium | Reception's actual Patient/Appointment permissions include export and broad read access; no User Permission rules exist. Existing administrator custom permissions are intentionally retained by setup, so the audit cannot attribute who granted export. | Approve a documented least-privilege policy and review bulk export, Company scope and sensitive Patient fields. Do not assume the earlier “minimum permissions” description matches actual grants. |
| S6 | Medium | 24-hour free-text check uses record creation rather than sender timestamp; official webhook falls back to default account for an unknown phone ID; status updates can regress by arrival order. | Test delayed/out-of-order events and account scoping; reject/quarantine foreign account events; derive service-window validity from authoritative event time. |
| S7 | Medium | Dispatch state is durable before network send, appropriately preventing automatic retry after crashes. However official direct send APIs do not use Talya's request-key ledger, and reopening a composer produces a new key. | Document/verify supported sending entry points and manual reconciliation of Reserved/Failed records; test concurrency/crash handling. No exactly-once delivery claim is justified. |
| S8 | Medium | Official App Secret is a `Data` field, unlike encrypted account access token; WA logs keep request/response content and can contain patient communication. Current secrets/logs are absent. | Review at-rest secret handling, access controls, logging/redaction, retention and backups before configuring real credentials. Do not copy secrets into Talya code. |
| S9 | Medium | Reminder batch can abort before per-message exception handling; network calls lack an explicit timeout. | Add bounded transport/error handling through supported integration mechanisms and test malformed/cancelled/rescheduled records before enabling reminders. |
| S10 | Medium | Private owner/file authorization is present, but XLSX 30-column reading can silently ignore later columns; compressed file size alone does not bound uncompressed workbook complexity. No antivirus/media-content validation is supplied by this Talya layer. | Test malformed/oversized workbooks and private attachment authorization; define upload scanning/limits for patient documents. |
| S11 | Medium | Public and inquiry booking availability differ; public phone regex rejects Arabic-Indic digits even though inquiry normalization supports them. | Align availability and Arabic-first phone behavior; verify negative cases on both APIs. |
| S12 | Low / usability | No persistent staff unread markers, assignment UI, cross-inquiry contact history or automatic scroll-position preservation; 20-second refresh always scrolls messages to bottom. | Improve after essential safety/configuration work, based on reception testing. |
| S13 | Low / operational | Developer mode on; old worker registry entries; no local backup files observed; no dedicated reception release artifact yet. | Use a production configuration, monitor queues, verify external backup/restore and maintain a reviewable release procedure. |

Positive controls: guest inquiry calls are rejected; state-changing Talya endpoints are POST-only; framework CSRF is enabled; template/attachment recipient and record checks exist; global opt-out blocks sending; incoming does not automatically create Patients; notifications omit contact/message bodies; message-ID uniqueness and request-key reservations exist. A source-pattern scan found no obvious real hardcoded access token/private key in Talya production code. This was a limited pattern/code review, not an exhaustive credential scan or penetration test.

## 7. Current test results and restrictions

All Python database inspection connections explicitly used **session transaction read-only mode**. Controller/helper experiments either read the existing site or substituted objects in memory. No test session/user/record was created. Browser fixtures rendered the actual current Jinja template/CSS/JS, intercepted API requests with synthetic data and blocked mutations; they do not authenticate to, create data in, or send messages from the real application.

| Current check | Passed | Failed | Blocked / not run | Evidence/limit |
|---|---:|---:|---:|---|
| Read-only helper/API/signature/challenge probes | **14** | **1** | 0 | The failure is local-number normalization under the actual calling-code setting |
| Recipient/consent drift probe | — | **1 defect reproduced** | 0 | A transient document's `validate()` retains consent/timestamp/Patient link after phone change; no save |
| Reception presentation cases | **28** | 0 | 0 | Chromium + WebKit × Arabic/English × 360/375/390/430/768/1024/1440; list/detail/fallback/composer/template/slot/settings/import layout; no page JS errors or horizontal document/dialog overflow |
| Existing hero regression | **14 viewport groups + 6 scenario groups** | 0 | 0 | Seven widths per engine, five full cycles, identities, controls, bilingual switching, swipe, layout stability; delayed/failed image/stale callbacks/background/duplicate-init scenarios |
| Python AST parsing | **28 files** | 0 | 0 | Syntax only; no `.pyc` generated by audit commands |
| Selected implementation Ruff check | Pass | 0 | 0 | `--no-cache`, no formatting/fix option |
| JavaScript syntax | **3 files** | 0 | 0 | Reception JS, public JS, hero slider |
| Reception literal translation coverage | **93 literals** | 0 missing keys/translations | 0 | Literal `t(...)` labels only, not every dynamic/data/browser-native label |
| Runtime asset targets | **93 bundle targets; 7 tracked images present** | 0 required missing targets | 0 | Existing files/browser loading; clean build not executed |
| Original `test_inquiries.py` suite | 0 currently claimed | 0 currently claimed | **16 tests** | Inserts/updates Patients, appointments, users, settings, Files and WA records, even with rollback/mocked transport. Running it would violate this audit's database-write restriction. |
| Original authenticated `inquiries.browser.cjs` workflow | 0 currently claimed | 0 currently claimed | Entire workflow | Requires session file, creates/imports/deletes records and publishes realtime events; deliberately not run |
| Original public `IntegrationTestCase` runner | 0 currently claimed | 0 currently claimed | 4 runner tests | Framework test setup may write fixtures/settings; equivalent non-mutating assertions were run separately |
| Clean asset build / migration rehearsal | 0 | 0 | Both | They modify artifacts/database and are prohibited |
| Real Meta sends/webhooks/statuses/media/reminders | 0 | 0 | All | No credentials or authorization to message; no live transport was exercised |

### Names of the 15 read-only probes

Passed: `public_phone_validation`, `public_clean_html_length`, `public_data_empty_no_doctors`, `public_booking_guest_read_denied`, `international_phone_current_setting`, `local_phone_reference_valid_calling_code`, `arabic_digit_phone_reference`, `inquiry_list_denies_guest`, `inquiry_detail_denies_guest`, `message_send_denies_guest`, `valid_signature_in_memory`, `invalid_signature_in_memory_rejected`, `webhook_challenge_in_memory`, `webhook_wrong_token_in_memory`.

Failed: **`local_phone_current_setting_expected_to_work` → ValidationError**. The valid-code reference tests patch only an in-memory settings accessor; they do not repair the site or prove its configured normalization works.

### Original 16 backend tests not rerun

`test_phone_and_manual_entry`; `test_guest_and_unprivileged_access`; `test_website_reuse_and_status_sync`; `test_appointment_availability_and_idempotence`; `test_patient_matching_prevents_duplicate_creation`; `test_reception_can_book_but_cannot_configure_secrets`; `test_forged_link_rejected_and_patient_creation_explicit`; `test_unavailability_blocks_slots`; `test_approved_template_outside_window_and_failures_are_honest`; `test_csv_import_preview_dedup_and_no_messages`; `test_xlsx_and_invalid_import`; `test_incoming_linking_duplicate_webhook_and_opt_out`; `test_send_uses_official_api_once_and_enforces_consent_window`; `test_webhook_signature_verification`; `test_reserved_send_is_not_retried_after_uncertain_failure`; `test_reminder_is_opt_in_and_idempotent`.

Their earlier passes remain **historical**, as do the previous asset-build result and authenticated browser workflow result. Current Frappe/WhatsApp versions and the invalid setting make unqualified reuse of those claims inappropriate.

Rendered views were visually reviewed in memory, including the real public mobile Arabic hero and a synthetic Arabic conversation/detail modal. No screenshot files were created. Native browser date/file controls may follow device language independently of page labels. The actual logged-in reception view, staff unread workflow, upload security at HTTP level and realtime delivery remain unverified.

## 8. Reception demonstration checklist

| Proposed demonstration step | Status | Reason |
|---|---|---|
| 1. Open Patient Inquiries | Ready with test data | Page/assets exist and render; live authenticated access not rerun under audit constraints |
| 2. Show an inquiry received from website | Requires configuration | No website requests; no bookable practitioner configuration |
| 3. Open contact details | Ready with test data | Current synthetic detail-modal checks pass; no real inquiry available |
| 4. Open the WhatsApp conversation | Requires configuration | Official account unconfigured; no real message history |
| 5. Compose a demonstration message | Ready with test data | Synthetic composer works; never represent it as a live send |
| 6. Select a doctor | Requires configuration | Static website portraits do not create Healthcare practitioners |
| 7. Book an available appointment | Blocked | Missing practitioners, schedules, units, appointment types and Gender values; current writes unverified |
| 8. Show linked Healthcare appointment | Blocked | No existing appointment and no authorized creation in this audit |
| 9. Show appointment confirmation | Requires configuration | No account/approved template; fix consent/recipient safety first |
| 10. Explain daily inquiry management | Ready | Explain implemented list/status/notes; disclose absent unread/assignment/history workflows |

Do not visit the clinic promising a working end-to-end demonstration based on synthetic UI evidence alone. A read-only website/interface walkthrough is possible if clearly presented as such. Before the intended demonstration, authorize a separate local setup/test task, obtain clinic-approved practitioner/schedule data, use synthetic Patients and an explicitly authorized WhatsApp test recipient, and perform a timed reception rehearsal.

## 9. Cloud deployment readiness

Only after the local audit, public read-only requests were made to the previously supplied address **`https://talya.nvi.frappe.cloud`**:

| Observation | Result | What it proves |
|---|---|---|
| Public homepage | HTTP 200, Talya content | Public HTTPS website is reachable |
| Public practitioner data endpoint | HTTP 200, zero exposed practitioners | No publicly approved doctors returned; does not prove the private Healthcare table is empty |
| `/patient_inquiries` | **HTTP 404** | Inquiry route not available at this observed deployment |
| `/assets/talya/js/patient-inquiries.js` | **HTTP 404** | New reception JS not served there |
| `/assets/talya/css/patient-inquiries.css` | **HTTP 404** | New reception CSS not served there |

No authenticated cloud access was used. Cloud installed apps/versions, private masters, schemas/migrations, scheduler/workers, credentials, webhook subscriptions, permissions, backups and rollback arrangements are all **Not Verified**. A public 200 response is not a production-readiness check. The candidate domain's ownership/deployment identity was not authenticated during the audit.

### Release prerequisites

1. Repair and review P0/P1 defects in a separately authorized task. Preserve current working changes; do not deploy the current unreviewed worktree.
2. Stage/review/commit all required Talya modules, DocTypes, CSS/JS and tests. The current GitHub branch does not contain them; locally existing untracked files will disappear from a Git-only release. All existing static portraits/logos/reception images are already tracked.
3. Verify a production-compatible Frappe 16 / ERPNext 16 / Healthcare 16 / Python 3.14 combination and a pinned official WhatsApp revision. WhatsApp is optional in Talya's dependency declarations to permit the external `wa.me` fallback; **embedded messaging requires explicitly installing the separate official app on the cloud site/bench**. CRM is not required.
4. Confirm production state using authorized read-only access; back up database, public/private files and required encrypted-secret recovery material; test restoration on an isolated environment. No backup or restore was attempted here.
5. Rehearse schema synchronization, unique-index creation and backfill against a restored database. Resolve duplicate historical WA IDs before adding uniqueness. Address the existing inquiry-overwrite hook before any production migration. Zero local pending patches is not evidence that the cloud schema matches.
6. Build from a clean checkout with all required assets/dependencies and verify mobile/desktop plus the existing website. Avoid copying local developer mode, local hostname/loopback/tunnel settings or local test fixtures into production.
7. Configure protected official account credentials, the exact authenticated production HTTPS callback, verification token/App Secret, Meta business-account subscriptions, approved templates, reception roles and consent process. Test signature failure, foreign accounts, duplicates, delayed callbacks and wrong-recipient prevention before enabling live use.
8. Validate site timezone, scheduler/workers/Socket.IO, request timeouts, logging redaction/retention and failure alerts. Leave reminders disabled until their own acceptance test is approved.
9. Establish rollback criteria: preserve data/files, retain compatible app revisions, avoid restoring an older schema under newer code blindly, and use a tested backup/restore procedure where migrations are not reversible. Review how dispatches reconcile messages already accepted by Meta before a rollback.

No action above was executed against cloud or local configuration during this audit.

## 10. Prioritized action plan

### P0 — before connecting the real WhatsApp number

1. Fix recipient-change consent/Patient/profile binding (S1) and add a negative regression test that cannot send appointment information to a newly substituted number.
2. Correct the invalid country calling code under approval, investigate the persisted invalid setting, and retest local/international/Arabic phone paths.
3. Decide safe phone/profile/inquiry routing, including shared family numbers and replies after booking (S3); test that messages cannot silently attach to the wrong Patient context.
4. Review actual reception read/export scope and sensitive fields; agree a consent/opt-out and uncertain-send procedure with the clinic.
5. Configure official Meta account/secrets/HTTPS/subscriptions and approved non-clinical templates only after code safety work; verify against an authorized test recipient. No real number should be connected merely to discover these defects during a clinic visit.
6. Authorize an isolated test run on the upgraded stack: backend creation/import/booking/status/permission tests, event concurrency, wrong-account callbacks, real text/template/media status round trip and negative consent checks.

### P1 — before cloud deployment and the complete reception demonstration

1. Prevent migration/backfill overwrite of staff notes, contact edits and Patient links (S4); rehearse on a restore with representative existing data.
2. Configure clinic-approved active practitioners, departments, Company-linked service units, schedules, appointment types/durations and Gender values. Explicitly verify both website visibility/booking flags and the legacy default appointment type.
3. Unify/test legacy and inquiry availability; verify holidays, overlapping durations, cancellation, rescheduling, linked statuses and confirmation parameters.
4. Bound transport requests and isolate reminder record errors; test timezone boundaries, stale/uncertain sends and duplicate reminder keys. Do not enable reminders prematurely.
5. Review file authorization, workbook limits and secret/log retention; document the upstream incoming-download limitation and obtain acceptance or a supported resolution.
6. Produce a reviewed, reproducible Git release; verify cloud versions/dependencies, backup/restore, migrations, assets, permissions, scheduler and realtime. Re-run existing website regression from the release artifact.
7. Rehearse all ten demonstration steps with authorized synthetic data, then reissue the Go/No-Go decision with current evidence.

### P2 — improvements that can wait

- Staff unread counters/acknowledgements, optional assignment, cross-inquiry contact history and preserved message scroll position.
- Indexed normalized Patient-phone search and larger/paginated lookup lists; currently the popup returns 30 results and matching scans all readable Patients.
- Better failed/Reserved-send reconciliation UI, clearer retry instructions and accessible delivery/notification states.
- Native control language/accessibility and upload error UX review; clarify XLSX extra-column behavior.
- Clean obsolete worker registrations during an approved maintenance window; improve operational dashboards and document the release procedure.

## 11. Final Go/No-Go decisions

### A. Local Demonstration Readiness: **NO-GO** for the requested full workflow

The website and synthetic reception presentation are demonstrable. The actual site has no inquiries or clinical masters, its current local phone normalization fails, the authenticated write workflows have not been rerun on the upgraded stack, and WhatsApp has no configuration. A restricted read-only preview must be described as a preview, not a functioning medical-center reception demonstration.

### B. Live WhatsApp Integration Readiness: **NO-GO**

Account/credentials/templates/HTTPS callback/subscriptions are missing; no Meta transport was verified. More importantly, the confirmed recipient-change consent defect and inquiry-routing risks need resolution before the real number or patient messages are introduced.

### C. Production Cloud Deployment Readiness: **NO-GO**

Required new code/assets are untracked, the observed cloud inquiry page/assets are absent, private cloud dependencies/schema/jobs/permissions/backups are unverified, and the current migration hook risks overwriting reception edits. Do not deploy simply because the public homepage and static layout tests pass.

**Next authorized task should be targeted P0 remediation and isolated configuration/testing, not live-number activation or cloud deployment.**
