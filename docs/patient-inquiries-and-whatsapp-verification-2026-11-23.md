# Patient Inquiries and WhatsApp Readiness — 23 November 2026

Scope: original `talya` app on local `talya.localhost`, plus public read-only checks of
`https://talya.nvi.frappe.cloud`. At audit time no commit, push, deployment, WhatsApp
configuration, number connection, reminder activation, or real message was performed.
Credential values were not printed or recorded here.

## Patient inquiry booking flow

The portal now uses the existing Desk patient-resolution and website-booking confirmation
logic. Reception must explicitly select a possible Patient and confirm identity; matches are
never auto-linked. Search covers normalized mobile, normalized name, and identity fields only
when the current user has field-level read permission. Identity values are returned only as a
masked last-four hint. On this site, `Patient.uid` is the identity field and Talya's receptionist
role cannot read it; System Managers can search it.

New-Patient fields come from the live Patient metadata and create permissions. Inquiry values
are prefilled, missing mandatory demographics are requested, and creation plus appointment
confirmation occurs in one savepoint. Manual/WhatsApp inquiries use the shared duration-,
practitioner-, room-, closure-, and overlap-aware availability service. Website inquiries call
the same final confirmation method as Desk and keep their doctor, type, date, time, and room.
The server rechecks availability at confirmation. Existing appointment links make retries
idempotent; failed confirmation rolls back Patient creation and verification.

Verification:

- Isolated backend sweep: **88 passed**, external HTTP blocked, all database test changes rolled
  back, and before/after record counts unchanged.
- Focused inquiry suite: **21 passed**, including permission-filtered identity search, new
  Patient plus appointment, duplicate retry, unavailable-slot rollback, and retained notes.
- Existing Desk suite: **23 passed**.
- Chromium and WebKit: Arabic and English at 360, 375, 390, 430, 768, 1024, and 1440 px:
  **28 passed**, with no page errors or horizontal overflow.
- JavaScript syntax, Python compilation, translation-key coverage, and `git diff --check` passed.

## WhatsApp readiness audit

### Local

- Installed official app: `whatsapp` **1.3.0**, branch `main`, revision
  `b32dfe2736a4a2bbaf2ab3f7c883fa31b43093a4`; Graph API setting is `v23.0`.
- Configured WA Accounts: **0**. No default account or configured phone/Phone Number ID exists.
- App ID, Business/WABA ID, Phone Number ID, permanent access token: **absent** because there is
  no account. Webhook verify token and App Secret/webhook secret: **absent**.
- Templates: **0**; approved templates: **0**. Confirmation/reminder template selections: absent.
- Profiles, messages, WhatsApp logs, and Talya dispatch reservations: **0**. Therefore no actual
  local send, receive, delivery, read, failure, or opt-out event has occurred.
- The local webhook code responds over plain `.localhost` HTTP and is not a public Meta callback.
  With no verify token, an audit challenge is rejected with 403 as expected.
- Consent binding, global number opt-out, shared-number routing, signature checking, request-key
  reservation, duplicate inbound ID handling, and send/receive policy are verified in isolated
  mocked tests. This proves code behavior only, not Meta transport.
- Scheduler is active, maintenance is off, and `talya.communication.reminders` is registered at
  `*/15 * * * *`. Reminders are disabled and have no selected template, so the observed job run
  is a no-op.

### Cloud public surface

- The Talya site, protected `/patient_inquiries` route, and Talya inquiry assets are reachable by
  HTTPS. The cloud asset hashes differ from this release-candidate implementation.
- The cloud WhatsApp webhook endpoint returns `App whatsapp is not installed`. Thus the official
  app/account/credentials/phone/templates/webhook handler are absent on this cloud site.
- No authenticated cloud configuration was read. Meta app subscription state cannot be verified
  from the public site and cannot be operational against this endpoint while the app is absent.

## GO / NO-GO

- Authorized test message: **NO-GO**. There is no account, connected/test number, token, verified
  HTTPS callback, Meta subscription, approved template, or authorized test recipient.
- Live patient use: **NO-GO**. In addition to the missing transport setup, the clinic must approve
  consent evidence, opt-out operations, template wording/languages, staff access, retention,
  incident handling, and reminder policy; then complete an authorized end-to-end test first.

## Activation order

1. Clinic chooses the WhatsApp number, Meta Business Portfolio/WABA ownership, authorized test
   recipient, consent wording/evidence, opt-out procedure, template languages/text, staff roles,
   log retention, escalation owner, and whether reminders are allowed at all.
2. Review and release this Talya change; back up cloud; install the reviewed official WhatsApp app
   revision on the cloud bench/site; migrate/build; verify the app version and protected portal.
3. In Meta, create/connect the WhatsApp business account and number, assign the app/system user,
   and create a permanent token with the required WhatsApp management/messaging permissions.
4. In cloud WA Account, set an Active account with App ID, WABA/Business ID, Phone Number ID, and
   encrypted access token; select it as WA Settings default. Confirm the display number against
   Meta without copying credentials into Talya or Git.
5. Generate separate webhook verify token and App Secret; store them in WA Settings. Configure
   Meta callback exactly as
   `https://talya.nvi.frappe.cloud/api/method/whatsapp.whatsapp.webhook.handler`, complete the
   challenge, subscribe `messages` and `message_template_status_update`, and subscribe the app to
   the WABA. Verify subscription with a read-only Graph query.
6. Create/sync clinic-approved Utility templates, wait for Meta `Approved`, verify account and
   language variants, then select only the confirmation template in Talya. Keep reminders off.
7. Record explicit consent for the authorized test number and execute one controlled round trip:
   approved template out, inbound reply, free text inside 24 hours, Sent/Delivered/Read callbacks,
   duplicate webhook, invalid signature, failure display, STOP/Arabic opt-out, and post-opt-out
   blocking. Reconcile official Meta records, WA Message, WA Log, inquiry, and dispatch state.
8. Resolve any defects and obtain clinic sign-off. Only then authorize live patient use. If
   reminders are approved, select the reminder template and separately test timing, cancellation,
   rescheduling, duplicates, timezone, failure isolation, and opt-out before enabling them.
