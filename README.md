# Yoga Mom Talk and OhioMom

One site for mothers and caregivers who need real help and a place to connect.

- **Yoga Mom Talk** (https://www.yogamomtalk.com/) is the national home: source-linked resources for all 50 states and DC. It is Deborah Vought's project and the primary site.
- **OhioMom** (https://www.ohiomom.org/) is the Ohio home of the same site and lives under `/ohio/`. It is one way in, with Ohio county pages, the Ohio family guide, listening and reporting forms.

Yoga Mom Talk is independent and is not affiliated with any other "Mom Talk" show or site.

## What is where

| Path | What it is |
| --- | --- |
| `/` (`index.html`, `help.html`, `connect.html`, `yoga.html`, `states.html`, `states/xx.html`, `about.html`, `report.html`) | National Yoga Mom Talk pages, generated from `data/ymt/` |
| `/ohio/` | OhioMom: the Ohio landing page, county pages, Ohio help pages, Wix forms and polls. Pages and their own `assets/` are self-contained here |
| `/family-guide.html` | The Ohio family guide. The path is fixed because the Veteran Home Guardians guide and the printed flyer's QR code point to `ohiomom.org/family-guide.html`. It stays Ohio-only. Its own links and canonical address use `www.yogamomtalk.com`, so the page works whether or not ohiomom.org is connected |
| `/js/wix/` | Wix form code. It stays at the site root because the Ohio pages import `/js/wix/form-store.js` |
| Old Ohio URLs (`/events.html`, `/near-you.html`, `/counties.html`, `/listen.html`, `/wellbeing.html`, `/counties/*.html`, `/help/{bills,disability,pregnancy-baby,single-parent}.html`) | Small redirect pages that send people to the same page under `/ohio/` and keep the query string and fragment |

The root `index.html`, `connect.html`, `help.html`, `report.html` and `yoga.html` are now the national pages. The earlier Ohio versions of those five are at `/ohio/`.

When the site is served from ohiomom.org, the home page sends visitors on to `/ohio/`, so ohiomom.org still lands on the Ohio page.

## How it works

National site (Yoga Mom Talk):

- `data/ymt/resources.json` holds the site block and the 38 national resources in eight sections. `data/ymt/state-templates.json` and `data/ymt/states.json` expand into one record per state for 51 places (714 state records). Each listing has a plain-language description, a next step, a phone or website, the published source it was checked against, and the date it was checked.
- `python3 scripts/ymt_validate.py` checks the data. `python3 scripts/ymt_build.py` builds every national page, `robots.txt` and `sitemap.xml`; `--check` confirms what is on disk matches the data.
- `python3 -m unittest discover tests` runs safety and integrity tests: the exit button and referrer policy on every national page, no third-party loads or tracking code, internal links and anchors resolve, phone links match the printed numbers, state pages use their own state, old Ohio URLs still resolve, and the Ohio pages and family guide are kept.
- The site name and domain live in one place, the `site` block of `data/ymt/resources.json`.

Ohio site (OhioMom):

- `data/resources.json` holds the original general-help listings; `data/family-guide.json` owns the complete Ohio family guide.
- `python3 scripts/build.py` builds `family-guide.html` from `data/family-guide.json`, `data/family-counties.json` and `templates/family-guide.html`. The pages under `/ohio/` are static source.
- `python3 scripts/validate.py` checks the Ohio data, and `npm test` checks the family guide.

## How pages are laid out: a little first, the rest when asked

A mom arrives with one need. The pages show her the choice, then a short list, then the details, in that order.

- **Front pages show no listings.** `index.html` and `ohio/index.html` ask what she needs, offer six needs and a way to pick her state or area, and stop. The national front page also keeps three small phone cards for emergencies.
- **Needs are closed rows.** On `help.html` and every state page each need is a `<details class="need">` that stays closed until she opens it. A link that names a need (`help.html#food-bills`) or a listing inside one opens it for her (`assets/ymt.js`).
- **Cards are short.** A card shows the name, one line (the first sentence of `what`), and the Call and Website buttons. The organization, the rest of the description, the next step, the sources and the checked date sit behind "More about this".
- A printed page opens everything.
- `tests/ymt-pages.cjs` and `tests/test_ymt.py` fail the build if a listing appears on a front page, a need is open by default, or the short part of a card grows.

## Keeping it current

- Every push runs both validations, both build checks, the Python tests and the family-guide test.
- On the 3rd of each month the Ohio listings are requested automatically, and on the 4th the national ones (`scripts/linkcheck.py` does the work for both). Either check can also be run by hand from the Actions tab; a run on a branch other than `main` is a trial and opens no issue.
- A robot cannot settle every link, so each one is sorted: it loaded; it is **broken** (gone, failing, parked, taken over, or a page that says "not found"); it has **moved** (the address now forwards to a different website); or it **cannot be checked** (the site refuses robots). The last three open an issue, or add to the one already open, because a person has to look.
- `data/link-checks.json` records each link a person opened in a real browser and found working, with the date. The checks skip those for 180 days and then ask again. Add or re-date an entry only after opening the link yourself.
- A link that loads is not proof the listing is right. On November 15, 2026 two parent-center addresses loaded fine for the robot while one forwarded to a gambling site and the other was parked for sale; one phone number was simply wrong. Those were found by comparing every state record with the national lists it is sourced from: the NDRN member list (disability-rights agencies), the CDC early intervention contact list, and the Parent Center Hub. Repeat that comparison a couple of times a year.

## Safety standards

- A fixed "Leave this site" button is on every national page. It jumps to an everyday page and does not erase browser history; the About page says so.
- The national pages carry no cookies, tracking, sign-up forms or third-party scripts of our own, and the report page uses a mail link only. Wix adds its own script and cookies to every page it serves, so the pages say that plainly and do not claim to be cookie-free.
- Domestic violence shelter addresses are never listed. Listings point to the hotline or program that places people safely.

## Still to settle

- **Hosting.** Decided: Wix headless serves the whole site. Nothing deploys when a branch is merged; each release is uploaded to the Wix site by hand. Wix keeps each Ohio page without its `wix-site-script` tag and adds the tag back when it serves the page, so the stored copy of those pages is the repo copy minus that one tag. Wix also serves its own `sitemap.xml`, `robots.txt` and not-found page.
- **Domains.** Decided (Nov 15, 2026): `www.yogamomtalk.com` is the primary domain and yogamomtalk.org redirects to it. Still open: ohiomom.org is not assigned, so every outside link to it is dead until it is connected again, including the Veteran Home Guardians guide's link and the QR code on the printed family guide flyer. No page on this site links or redirects to ohiomom.org any more (a test enforces it). Assigned as a redirecting domain, its old page links land on the same page here and the redirect pages carry them on to `/ohio/`, but its home page lands on the national home, because the visitor has already left ohiomom.org by the time the page loads and the home page check never runs. Sending the ohiomom.org home page straight to `/ohio/` needs a redirect hosted outside Wix.
- **Corrections email.** The default is `travis@vethomeguard.org`; change it in `data/ymt/resources.json` and rebuild.
- **Trademark.** The name is a decision for later. It is kept in one config value so a change is a rebuild.
- **Phone numbers.** No number on the site has been dialed. They match the published sources named on each card, and the state records match the three national lists as of November 15, 2026. Ohio's energy assistance line (800-282-0880) is still printed by local agencies but no longer appears on the state's own pages since the program changed departments in April 2026; dial it once to confirm it still connects.
- County-by-county Ohio pages beyond the four now published (Job and Family Services, board of developmental disabilities, housing front door, energy assistance provider).

## Credit and license

The disability, neurodiversity and military-family listings are adapted from the family guide in the Veteran Resident Resource Guide, created by Travis Vought and shared by Veteran Home Guardians (CC BY 4.0). Data here is CC BY 4.0; code is MIT. See `LICENSE`.

## Resource ownership

Ohio autism, ADHD and family disability resources are owned by `travisvought-byte/Ohiomom` at https://www.ohiomom.org/family-guide.html, now part of this combined site. The family guide covers Ohio only. The multi-state family guide remains at https://guide.vethomeguard.org/family-guide.html?state=US. Mobility resources are owned by https://mobilitytalk.org/. Related sites should link to the owning site, not replicate its section.
