# Talya release handoff

Local verification date: 22 November 2026 (Asia/Dubai).
Repository: `nagigithup/talya`; release branch: `version-16`.
The final handoff identifies the pushed commit SHA; use that SHA when selecting
the update. The source base reviewed here is `83bdc154d792d0743658a0474a4d6a940cc72479`.

## Included

The release includes the inquiry/communication/import modules, recipient and
permission helpers, all three new DocTypes and controllers, migrations/hooks,
reception pages and CSS/JS, Desk recovery page, translations, backend/browser tests
and documentation. Existing website HTML/CSS, portraits and Hero behavior are
preserved. The homepage controller and original backend test received formatting
fixes only, in addition to the previously completed phone-normalization change.

All seven public images are in Git: `dr-farouq.png`, `dr-mehira-original.webp`,
`talya-logo.svg`, `talya-logo-white.svg`, `talya-mark.svg`,
`talya-reception-styled.png` and `talya-reception.webp`. Service icons are SVG
symbols in the template. No site uploads are required for these static assets.

The P0 consent/recipient/Patient/profile protections and missing-only backfill are
described in [the remediation report](talya-p0-remediation.md). Release review also
fixed silent truncation of XLSX files wider than 30 columns and the corresponding
limit bypass on later CSV rows. Both now fail with the existing translated error
before an inquiry is imported. Browser tests now resolve dependencies portably
and reject any target other than the local Talya site. Python dependencies are
declared explicitly, and generated artifacts/site configuration are ignored.
Release checks also supplied two missing Arabic server-error translations. The
historical audit's three Markdown hard breaks were normalized without changing
its findings.
Guest reception/recovery redirects now use temporary HTTP 302 responses, avoiding
a permanent login redirect being retained when authentication changes.

## Local verification

- 49 synthetic backend integration tests passed after local migration, including
  P0 negative recipient cases, consent, permissions, booking/cancellation,
  import/deduplication and the two new import-width regressions.
- 6 release asset/schema/translation checks passed against the staged file list.
- 28 reception browser cases passed: Chromium/WebKit, Arabic/English, widths
  360, 375, 390, 430, 768, 1024 and 1440. These render the actual template/assets
  with synthetic API fixtures, without authenticating or persisting records.
- Existing Hero slider suites passed in Chromium and WebKit at the same seven
  widths, covering bilingual identities, mobile order/controls, swipe, delayed or
  failed images, rapid controls and timer lifecycle.
- A local database/public/private-file backup completed, followed by successful
  `bench --site talya.localhost migrate` and `bench build --app talya`.
- Ruff lint/format, JavaScript syntax, translation coverage, Git whitespace and
  release-file content checks passed. A wheel and the staged Git tree were checked
  for the required app modules, DocTypes and public assets.
- Live local HTTP checks returned the expected bytes for 12 image/CSS/JS assets,
  homepage HTTP 200, guest login redirects HTTP 302 and guest inquiry API HTTP 403.

Backend tests block external HTTP, email, SMS, queued work and realtime events;
official Meta clients are mocked. Transactions are rolled back. No real WhatsApp
messages were sent. Final local inquiry, Patient, appointment, WhatsApp account,
profile, message, template and dispatch counts remain zero. Reminders remain off.

No credentials, database dumps, patient records/uploads, site configuration,
temporary sessions, screenshots or compiled bundles belong in this commit. The
historical audit/remediation documents are dated evidence, not cloud state checks.
Local helpers/tests mentioning `talya.localhost` are guarded tooling, not exported
site settings; migration does not call the local configuration helper.

### Reproduce locally

From the Bench directory, use the transactional command in
`talya-p0-remediation.md`, or:

```bash
bench --site talya.localhost execute talya.tests.test_inquiries.run_local
env/bin/python -m unittest talya.tests.test_release_assets -v
env/bin/ruff check --no-cache apps/talya
env/bin/ruff format --check apps/talya
bench build --app talya
```

Release-file checks require all candidate files to be staged or committed. Backend
integration checks require the tested official WhatsApp app installed locally,
with no account configured; do not run the local test harness on cloud or real data.

Install Playwright in a separate developer/test directory if it is not already
available; it is not a production dependency. For example:

```bash
npm install --prefix /tmp/talya-browser-deps --no-save playwright
export TALYA_PLAYWRIGHT_PATH=/tmp/talya-browser-deps/node_modules/playwright
/tmp/talya-browser-deps/node_modules/.bin/playwright install chromium webkit
node apps/talya/talya/tests/recipient_safety.browser.cjs
TALYA_BROWSER=webkit node apps/talya/talya/tests/recipient_safety.browser.cjs
node apps/talya/talya/tests/hero_slider.browser.cjs
TALYA_BROWSER=webkit node apps/talya/talya/tests/hero_slider.browser.cjs
```

The optional older `inquiries.browser.cjs` test performs real local manual/import
actions and needs an authorized temporary login session; it was not rerun in this
release. Backend integration and session-free browser tests cover the release.

## Cloud update steps for the owner

These instructions were prepared from local source and official documentation.
No cloud site was accessed, updated, migrated or deployed by this task.

1. In Frappe Cloud, open the existing Talya site's **Backups** area. Create a fresh
   backup of database, public files and private files and confirm it completed.
   Retain the previous app revision and a usable backup for rollback.
2. Confirm the existing private Bench Group uses `nagigithup/talya`, branch
   `version-16`, and compatible Frappe/ERPNext/Healthcare 16 with Python 3.14.
   Local tested versions are Frappe 16.60.2, ERPNext 16.60.0, Healthcare 16.7.0 and
   Python 3.14.3. The compatibility table in `pyproject.toml` is included in Git.
3. If Communication Settings already exists, confirm the UAE calling code is
   `971` and reminders are disabled before updating. Migration preserves existing
   site settings rather than copying the local database. Fresh settings default
   to `971` with reminders off. The Patient level-9 permission guard deliberately
   stops migration if unrelated fields already use that level; resolve such a
   collision deliberately rather than deleting custom permissions.
4. In the Bench Group, open **Update Available / Show Updates**, select **Talya**,
   and confirm its source commit matches the handoff SHA. Select the intended Talya
   site and choose **Deploy and Update**. Do not select unrelated app upgrades.
   Monitor **Deploys** and the site's update until build and migration complete.
   These are Frappe Cloud's documented selective app/site update actions.
   ([Site update guide](https://docs.frappe.io/cloud/sites/how-to-update-an-app-site-on-a-private-bench),
   [Bench updates](https://docs.frappe.io/cloud/benches/updating_a_bench))
5. In the completed deploy's menu, choose **View App Versions** and check Talya's
   commit. If your workflow deploys a bench without immediately updating the site,
   explicitly update the site to that completed bench release; a built bench alone
   is not proof that the site migration ran.
6. Open the homepage on mobile/desktop in Arabic and English, then log in as
   authorized staff and open `/patient_inquiries` and
   `/patient_inquiries?lang=en`. Verify the doctor photos, slider controls, reception
   CSS/JS, dialogs, restricted Patient fields and existing inquiry notes/links.
   Leave the real WhatsApp number unconnected and reminders disabled.

The cloud UI performs its own build/migration/restart pipeline. Do not `git pull`
inside a managed Cloud container or copy local `sites`, `node_modules`, backups or
asset build output there. Do not run `apply_p0_local_configuration` on cloud; it is
explicitly local only. Check the actual target with your own authorized account;
this handoff does not claim its installed apps, permissions or settings were read.

### Optional read-only checks using authorized cloud SSH

From that site's managed Bench directory, replace `YOUR_CLOUD_SITE` yourself:

```bash
bench --site YOUR_CLOUD_SITE list-apps
git -C apps/talya rev-parse HEAD
bench --site YOUR_CLOUD_SITE execute frappe.db.get_single_value \
  --kwargs '{"doctype":"Talya Communication Settings","fieldname":"country_calling_code"}'
bench --site YOUR_CLOUD_SITE execute frappe.db.get_single_value \
  --kwargs '{"doctype":"Talya Communication Settings","fieldname":"reminders_enabled"}'
```

Expected: the handoff SHA, calling code `971`, reminders `0`/false. Cloud may use a
checkout without Git metadata; **View App Versions** remains the authoritative
managed-deploy check in that case. Do not print access tokens or webhook secrets.

## What remains outside this release

The clinic must supply approved doctor/department records, schedules/holidays,
Company-linked service units, appointment types/durations, Gender values and
staff identity/consent procedures before demonstrating real Healthcare booking.
Review the roles assigned to real reception users because Frappe role grants are
additive. Existing staff inquiry edits are preserved by migration.

The official WhatsApp app is optional for the website/inquiry/manual-contact
release. Embedded messaging was tested locally with version 1.3.0 at
`b32dfe2736a4a2bbaf2ab3f7c883fa31b43093a4`; do not substitute an unreviewed older
API. If it is absent on cloud, no Meta setup is needed for this release. Installing
or configuring it is a separate owner-controlled change.

Meta credentials, approved templates, reachable HTTPS webhook/subscriptions, an
authorized test recipient and actual delivery/status verification remain separate
activation work. Transport timeout/reminder error handling, old event timestamps,
legacy availability differences, workbook complexity/upload scanning and a
restored-production-data migration rehearsal remain follow-up release gates for
live patient communication. This GitHub artifact is not certification of those
unverified services. Leave reminders disabled and Meta unconfigured.
