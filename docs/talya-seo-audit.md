# Talya organic SEO audit and local implementation

Audit and clinic approval date: 2026-11-28 (Asia/Dubai). App: original `/home/nagi/my-bench/apps/talya`, branch `version-16`. Local site: `talya.localhost`.

The clinic confirmed **https://talyamedical.com** as the preferred production origin. The implementation is local, with 12 bilingual public routes ready for review. Nothing was committed, pushed, deployed, or changed in cloud configuration. Public production requests were read-only. No patient records were created, no WhatsApp messages were sent, and reminders were not enabled.

The initial worktree was clean at `a562b1582cb424aae5e73dd71d2d83c735b9f771`. Existing app code, original images and all original Arabic translations have been preserved.

The signed-out public audit found these issues before implementation:

| Area | Observed production behavior | Local implementation |
| --- | --- | --- |
| Preferred domain | Owner confirmed `talyamedical.com`; apex HTTPS serves the clinic | HTTPS canonical origin defaults to the confirmed non-www domain |
| Duplicate homepage paths | `/` and `/talya` both returned the same clinic page without canonicals | Permanent redirects to `/en`; existing fragments and booking query links remain usable |
| Cloud alias | `talya.nvi.frappe.cloud` also served the clinic landing page | Public language routes redirect to the approved origin when accessed on an alias after deployment |
| HTTP | Apex and cloud HTTP requests redirected to HTTPS with 308 | Existing edge HTTPS behavior preserved |
| www TLS | `www.talyamedical.com` resolves to the same IP as the apex but certificate validation fails | Owner hosting/TLS action required; no remote changes made |
| Arabic | One URL used JavaScript/localStorage to replace English text | Separate `/ar` routes render Arabic, RTL and metadata in the initial HTML |
| Profiles and services | No dedicated app pages existed; names were not profile links | One useful page per doctor/service/language; doctor names are visible links |
| Descriptions | Two description tags on the homepage | One unique description per public page |
| Canonicals/hreflang | Absent | Self-canonical HTTPS URLs and reciprocal `ar-AE`, `en-AE`, plus English `x-default` |
| Sitemap/robots | Sitemap XML contained zero URLs; robots.txt was empty | XML allowlist of the 12 public canonicals; robots references the sitemap and excludes staff/private routes |
| Structured data | No JSON-LD on the clinic page | MedicalClinic, WebPage/ContactPage, and doctor ProfilePage/Person graphs |
| Image payload | Farouq PNG 1,341,564 bytes; reception PNG 1,923,767 bytes | Authentic-image WebP copies: 146,934 and 151,416 bytes respectively |
| Initial layout stability | Testing found late Inter font swaps rewrapping the English hero at tablet sizes | Same Frappe Inter files, preloads and optional font display; correct portrait intrinsic dimensions |

Both `talyamedical.com` and `www.talyamedical.com` resolved to `80.225.78.143` during the audit. The cloud hostname resolved to that IP too. `www.talya.nvi.frappe.cloud` resolved elsewhere and also failed TLS validation; it is not an official website hostname. TLS failures were not bypassed, so no claim is made that the www hosts served duplicate HTML successfully.

The public Maps link was followed successfully to Google’s listing named “Talya medical center medicine and dentistry”: https://maps.app.goo.gl/wjydTejcBzmawQNWA. The existing Al Nakheel / Ras Al Khaimah / near Action Hotel address and reception call numbers were retained. Shared app values supply visible contact links and structured data so the two cannot drift independently. A directory’s hours and spelling variants found during research were not treated as clinic approval.

The following are the final canonical URLs **for the approved future deployment**. Their corresponding paths resolve locally now; these new routes have not been published to production in this task.

| Page | English canonical | Arabic canonical |
| --- | --- | --- |
| Homepage | https://talyamedical.com/en | https://talyamedical.com/ar |
| Dr. Mehira Fadl | https://talyamedical.com/en/doctors/dr-mehira-fadl | https://talyamedical.com/ar/doctors/dr-mehira-fadl |
| Dr. Farouq Ejami | https://talyamedical.com/en/doctors/dr-farouq-ejami | https://talyamedical.com/ar/doctors/dr-farouq-ejami |
| General Medicine | https://talyamedical.com/en/services/general-medicine | https://talyamedical.com/ar/services/general-medicine |
| Dental | https://talyamedical.com/en/services/dental | https://talyamedical.com/ar/services/dental |
| Contact | https://talyamedical.com/en/contact | https://talyamedical.com/ar/contact |

The six new homepage/doctor URLs were also checked on production and currently return 404, which is expected before this local release is deployed. Do not submit those new paths for indexing yet.

For local review, replace `https://talyamedical.com` with `http://talya.localhost:8000`. Local pages deliberately send `noindex, follow` and local robots.txt blocks crawling, while their canonical and hreflang URLs show the confirmed production domain. The production code path allows public indexing. No production-wide noindex directive was added.

The code uses an explicit route allowlist, not a catch-all that returns 200 for invented doctor/service URLs. Unknown routes and the internal `talya_public` controller return 404. `/`, `/talya`, old `.html` paths and trailing-slash aliases normalize with 301 redirects. Query parameters such as the doctor selector survive redirects; canonicals omit those parameters. Staff routes keep their existing authentication behavior.

English source strings and the existing app `translations/ar.csv` catalogue render the initial HTML and supply booking UI messages. Language is selected by the URL rather than an earlier visit, query-string locale, or browser preference. The language switch is a crawlable anchor and works without JavaScript. The carousel preserves its visible doctor and pause preference across language navigation; only that non-patient state is kept in sessionStorage. Its existing six-second timing, authenticated booking integration and appointment APIs are unchanged.

Each doctor’s profile links to the existing homepage booking form using `?doctor=mehira#appointment` or `?doctor=farouq#appointment`. Matching an approved public practitioner preselects that doctor. An unrelated doctor using a copied portrait is not silently linked to a named profile. Local Healthcare masters are empty, so the existing local booking-setup warning remains honest; synthetic unit fixtures verify preselection without adding practitioners or appointments.

The clinic supplied and approved these facts during this task:

- **Dr. Mehira Fadl / د. مهيرة فضل** — General Practitioner / طبيبة عامة.
- **Dr. Farouq Ejami / د. فاروق عجيمي** — Dentist / طبيب أسنان.
- Both doctors are Sudanese and speak Arabic. The public profiles and Person markup include those facts; no additional language is implied by the English website.
- The team statement appears in the homepage Doctors section: “Talya’s team includes Arabic-speaking Sudanese doctors with over 10 years of experience in UAE government hospitals.” Its Arabic version is «يضم مركز تاليا أطباء سودانيين يتحدثون العربية، بخبرة تزيد على 10 سنوات في مستشفيات حكومية في الإمارات.» It is not attributed to either individual doctor’s biography, credentials or Person experience.
- Public clinic hours are **daily, including Fridays, 16:00–00:00 Asia/Dubai**. Midnight is represented as `closes: "00:00"` following a 16:00 opening, not as 24-hour service. Hours appear in the homepage contact area, contact page, visit information and MedicalClinic JSON-LD. Walk-ins are welcome.
- GP consultations and chronic disease follow-up are published. Detailed claims about tests, imaging, vaccinations or minor procedures are withheld.
- Dental checkups, cleaning, cavity fillings, zirconia/porcelain crowns and bridges, whitening, veneers, braces and gum care are published. Only cleaning and cavity fillings have public prices: **AED 150 each**. Other services direct visitors to reception for a quote. Neither supplied crown/bridge amount is published because its pricing unit is still unconfirmed.

The research map is [talya-seo-keyword-map.csv](talya-seo-keyword-map.csv): 129 queries in 14 intent groups. Brand and location terms map to the homepage/contact pages; each approved doctor has one profile per language; GP and dental queries map to the relevant service page. Conditional condition-specific or diagnostic queries stay research entries until their clinical scope/provision is confirmed. “Near me” and “open now” are research intents supported by accurate address, Maps and hours, not stuffed into headings or metadata. There are no meta-keywords tags, spelling-variant doorway pages, invented search volumes, fabricated reviews or rating markup.

MedicalClinic markup uses the visible clinic name, address, existing reception telephone, approved hours and Maps link. Each doctor is represented as a Person working for that clinic, with a stable entity ID across languages. The doctor page is a ProfilePage whose mainEntity references that Person. Individual credentials, hospital affiliations, individual years, reviews, ratings and price-range guesses are absent. JSON syntax, entity references and published values were checked locally; Google rich-result eligibility and Google-selected canonicals require owner verification after release. [Google’s localized-page guidance](https://developers.google.com/search/docs/specialty/international/localized-versions) and [LocalBusiness structured-data guidance](https://developers.google.com/search/docs/appearance/structured-data/local-business) inform these choices.

Private pages are excluded from the sitemap by construction and the Talya staff controllers now explicitly declare `sitemap = 0`. Desk, reception, API, portal, print and private-file paths receive noindex headers; native access controls remain enforced. Signed-out checks denied Patient, Patient Appointment, Talya Online Booking and Talya Patient Inquiry reads. Login redirects are preserved, including Frappe’s existing Desk redirect status. Robots rules are not used as a substitute for authentication. Existing explicit Website Settings or file-based robots policies are retained rather than silently overwritten.

The two optimized images retain their original dimensions and composition; the originals remain available for existing public links. The hero portrait’s attributes now reflect its actual 1182×1330 dimensions. The smaller files save 2,966,981 bytes for those two requests. The same installed Inter font files are used under an isolated website font family so Frappe’s earlier swap faces cannot cause a second layout; Cairo remains the Arabic family. Preloading and optional display follow [the Chrome team’s font-loading guidance](https://web.dev/articles/preload-optional-fonts). Performance results are local lab observations, not a claim about field Core Web Vitals or Google ranking.

The verification commands are reproducible from the app/bench workspace:

```bash
# Pure synthetic tests; no records or messages are created.
/home/nagi/my-bench/env/bin/python -m unittest talya.tests.test_seo -v

# Running local site only; guest GET requests and metadata/permission checks.
/home/nagi/my-bench/env/bin/python -m talya.tests.seo_http

# Browser dependency already present in this bench.
TALYA_PLAYWRIGHT_PATH=/home/nagi/my-bench/apps/pos_next/node_modules/playwright   TALYA_BROWSER=chromium node talya/tests/seo.browser.cjs
TALYA_PLAYWRIGHT_PATH=/home/nagi/my-bench/apps/pos_next/node_modules/playwright   TALYA_BROWSER=webkit node talya/tests/seo.browser.cjs
TALYA_PLAYWRIGHT_PATH=/home/nagi/my-bench/apps/pos_next/node_modules/playwright   TALYA_BROWSER=chromium node talya/tests/hero_slider.browser.cjs
TALYA_PLAYWRIGHT_PATH=/home/nagi/my-bench/apps/pos_next/node_modules/playwright \
  node talya/tests/seo_booking.browser.cjs
```

Four additional synthetic browser fixtures exercise each doctor’s profile-to-booking link in English and Arabic, validate doctor/department preselection, date/slot loading and the existing request payload, and intercept every booking POST. They verify privacy consent remains separate from WhatsApp consent; no fixture creates a real booking.

The browser suite checks English and Arabic homepage, both doctor profiles, both services and contact pages. Chromium covers 360, 375, 390, 430, 768, 1024 and 1440 pixels; WebKit covers 390 and 1440. It also checks all 12 pages per engine with JavaScript disabled, both portrait identities, mobile controls/statistics order, images, links, metadata and overflow. Chromium asserts the initial local layout-shift measurement remains at most 0.1. The separate carousel suite covers five complete automatic cycles at each width, delayed/failed photos, rapid controls, language navigation, swipe, background/resume and duplicate initialization.

Screenshots, sanitized HTTP results and the production read-only audit are stored outside the app at `/home/nagi/my-bench/artifacts/talya-seo-20261128T064430Z/`. They are not release assets. Final verification totals and representative screenshot paths are recorded in `verification-summary.json` there. New assets and local asset references are checked using a temporary Git index so no review files are silently staged in the real index.

The following owner actions require access that was not available here:

1. **Hosting/TLS:** in Frappe Cloud, confirm the `www.talyamedical.com` alias belongs to this site and issue/repair its certificate. Both names resolved to the same IP during this audit; check the actual DNS records and host mappings before changing targets. Once TLS works and the approved app release is deployed, verify www and the cloud alias redirect public pages to the non-www canonical without loops. The apex HTTPS certificate and its HTTP→HTTPS redirect already worked. No DNS, certificate or hosting setting was changed here.
2. **Google Search Console:** use the existing Domain property `sc-domain:talyamedical.com` if present; otherwise add `talyamedical.com` as a Domain property and verify using Google’s supplied DNS TXT record. The exact URL-prefix alternative is `https://talyamedical.com/`. No connected authorized Search Console session was available, so no property was created/verified and no sitemap or indexing request was submitted. [Google’s property instructions](https://support.google.com/webmasters/answer/34592) describe the verification scopes.
3. **After an approved deployment:** submit **https://talyamedical.com/sitemap.xml**. It should contain the 12 URLs listed above. In URL Inspection, live-test both homepages and the four doctor URLs, inspect rendered content and crawl permission, and request indexing where appropriate. Check the indexed report later for Google-selected canonicals; a successful live test does not establish indexing. [Google’s URL Inspection documentation](https://support.google.com/webmasters/answer/9012289) explains that distinction.
4. **Google Business Profile:** the authorized owner should confirm the existing listing’s verified status, business name, complete street/building/unit address, map pin and primary reception phone, then use the official website `https://talyamedical.com/` and an appointment link such as `https://talyamedical.com/ar#appointment` after release. Set daily public hours to 16:00–00:00 including Friday, record walk-ins accurately, and use only categories/services that match the approved clinic offering. Compare and correct inconsistent directory hours/addresses. No listing edit, review request, or message was sent. [Google’s local-ranking guidance](https://support.google.com/business/answer/7091) supports accurate, complete business information; no ranking outcome is promised.
5. **Clinic content:** confirm each crown/bridge pricing unit before publishing its supplied amount; confirm additional languages, individual experience and hospital affiliations before adding individual claims. Confirm how laboratory tests, X-rays, ultrasound, vaccinations and minor procedures are provided before detailed service pages or on-site claims. The existing footer also points to an unprovided privacy-policy section; clinic-approved policy text is needed before presenting a full policy page.

A read-only public availability check for **2026-11-29** returned 24 starts per approved doctor, from **11:00 to 22:30**, using the existing public endpoint. Those are practitioner booking times, not the clinic hours. The clinic has now confirmed public hours of 16:00–00:00; whether pre-16:00 online starts are intended is a separate schedule decision. This SEO task did not change schedules, appointment durations, occupied-slot handling, Patient links, booking confirmation, invoicing, consent, WhatsApp settings or reminders.

Search Console query data, actual Google index status, Business Profile ownership/edits, production field performance and the new pages’ post-deployment behavior remain unverified. No paid tools, ads or paid placements were used. There is no claim that Google has indexed these local changes or that any ranking is guaranteed.
