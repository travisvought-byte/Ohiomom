# Yoga Mom Talk and OhioMom

One site for mothers and caregivers who need real help and a place to connect.

- **Yoga Mom Talk** (https://www.yogamomtalk.com/) is the national home: source-linked resources for all 50 states and DC. It is Deborah Vought's project and the primary site.
- **OhioMom** (https://www.ohiomom.org/) is the Ohio home of the same site and lives under `/ohio/`. It is one way in, with Ohio county pages, the Ohio family guide, listening and reporting forms.

Yoga Mom Talk is independent and is not affiliated with any other "Mom Talk" show or site.

## What is where

| Path | What it is |
| --- | --- |
| `/` (`index.html`, `help.html`, `connect.html`, `yoga.html`, `states.html`, `states/xx.html`, `about.html`, `report.html`) | National Yoga Mom Talk pages, generated from `data/ymt/` |
| `/ohio/` | OhioMom: the Ohio landing page, county pages, Ohio help pages, Wix forms and polls. Pages and their own `assets/` are self-contained here, except the site icon, which every page takes from `/assets/` |
| `/family-guide.html` | The Ohio family guide. The path is fixed because the Veteran Home Guardians guide and the printed flyer's QR code point to `ohiomom.org/family-guide.html`. It stays Ohio-only. Its own links and canonical address use `www.yogamomtalk.com`, so the page works whether or not ohiomom.org is connected |
| `/js/wix/` | Wix form code. It stays at the site root because the Ohio pages import `/js/wix/form-store.js` |
| Old Ohio URLs (`/events.html`, `/near-you.html`, `/counties.html`, `/listen.html`, `/wellbeing.html`, `/counties/*.html`, `/help/{bills,disability,pregnancy-baby,single-parent}.html`) | Small redirect pages that send people to the same page under `/ohio/` and keep the query string and fragment |

The root `index.html`, `connect.html`, `help.html`, `report.html` and `yoga.html` are now the national pages. The earlier Ohio versions of those five are at `/ohio/`.

When the site is served from ohiomom.org, the home page sends visitors on to `/ohio/`, so ohiomom.org still lands on the Ohio page.

## How it works

National site (Yoga Mom Talk):

- `data/ymt/resources.json` holds the site block and the 44 national resources in nine sections. `data/ymt/state-templates.json` and `data/ymt/states.json` expand into one record per state for 51 places (816 state records). Each listing has a plain-language description, a next step, a phone or website, the published source it was checked against, and the date it was checked.
- `python3 scripts/ymt_validate.py` checks the data. `python3 scripts/ymt_build.py` builds every national page, `robots.txt` and `sitemap.xml`; `--check` confirms what is on disk matches the data.
- `python3 -m unittest discover tests` runs safety and integrity tests: the exit button and referrer policy on every national page, no third-party loads or tracking code, internal links and anchors resolve, phone links match the printed numbers, state pages use their own state, old Ohio URLs still resolve, and the Ohio pages and family guide are kept.
- The site name and domain live in one place, the `site` block of `data/ymt/resources.json`.

Ohio site (OhioMom):

- `data/resources.json` holds the original general-help listings; `data/family-guide.json` owns the complete Ohio family guide.
- `python3 scripts/build.py` builds `family-guide.html` from `data/family-guide.json`, `data/family-counties.json` and `templates/family-guide.html`. The pages under `/ohio/` are static source.
- `python3 scripts/validate.py` checks the Ohio data, and `npm test` checks the family guide.

## How pages are laid out: a little first, the rest when asked

A mom arrives with one need. The pages show her the choice, then a short list, then the details, in that order.

- **Front pages show no listings.** `index.html` and `ohio/index.html` ask what she needs, offer the needs to choose from and a way to pick her state or area, and stop. The national front page has seven needs and a "See everything" choice, and keeps three small phone cards for emergencies.
- **Housing and shelter is a need of its own.** It leads with a shelter search, the women's shelter list for the state and the domestic violence hotline, then rent help, public housing, housing counselors and the organizations that shelter families. Shelter addresses are never printed.
- **Everything is on one page, and it can be searched.** `help.html` holds every national listing. A state page holds everything for that state: the state's own offices first, then every national listing the state has no version of (`REPLACED_BY_STATE` in `scripts/ymt_build.py` says which those are). Both pages have a search box and a "Show everything" button (`assets/ymt.js`). Searching hides what does not match and opens the needs that do; words match where a word starts, and a short list of everyday words ("homeless", "daycare", "food stamps") reaches the listing that uses another word. `help.html#everything` and `help.html#q=rent` do the same from a link. The box only filters what is already on the page: it has no name and no form, so nothing typed can be sent, and it stays hidden when the script does not run.
- **Needs are closed rows.** On `help.html` and every state page each need is a `<details class="need">` that stays closed until she opens it. A link that names a need (`help.html#food-bills`) or a listing inside one opens it for her (`assets/ymt.js`).
- **Cards are short.** A card shows the name, one line (the first sentence of `what`), and the Call and Website buttons. The organization, the rest of the description, the next step, the sources and the checked date sit behind "More about this".
- **The inner OhioMom pages work the same way.** County pages, `ohio/help/pregnancy-baby.html` and `ohio/wellbeing.html` are an index of closed rows; `ohio/help/bills.html` and `ohio/help/single-parent.html` are a handful of short cards. Searching a page opens the rows that match and puts the others away. `ohio/connect.html` and the area panel on `ohio/near-you.html` are rows by kind of group. `ohio/events.html` shows the next six events and a "Show all" button, and each event keeps its times, place, price and source behind "When, where and cost" (`ohio/assets/site.js`).
- **Crisis numbers are never behind a tap.** `ohio/wellbeing.html` keeps three small phone cards in the open above its rows, the way the national front page does. Each one repeats a listing further down the same page. The "Leave this page quickly" link sits with them, in the open, because a domestic violence line is showing; on county pages it is inside the "Safety at home" row, which shows nothing until it is opened.
- **The family guide asks before it lists.** `family-guide.html` opens with one question (how old is your child?) and six stages. Nothing is listed until a choice is made: a stage, a county, a need, or a link that names one listing. A choice shows the first calls for that stage and the first six programs as short cards, with a "Show all" button. Glossary, changes, rights, military programs, good-to-know notes and the shareable flyer are closed rows. It wears the OhioMom look (`ohio/assets/site.css`) with its own small stylesheet. Without JavaScript the whole list shows. `tests/family-guide.cjs` holds all of this.
- A printed page opens everything.
- `tests/ymt-pages.cjs` and `tests/test_ymt.py` fail the build if a listing appears on a front page, a need is open by default, or the short part of a card grows.

## Built so everyone can use it

- **One banner, one main, nothing loose.** Every page has a single page header and a single `<main>`, and everything a visitor meets sits inside one of them, including the "Leave this site" button and the "Did you find what you came for?" question.
- **Headings never skip a level.** Where a list of cards or events has no visible heading of its own, it has one for screen readers (`class="sr"`).
- **Row headings are valid HTML.** The `<h2>` of a closed row is a direct child of its `<summary>`; a CSS grid lays out the icon, the heading, the one-line summary and the count.
- **Text on buttons passes contrast.** White text on the pink (`--brand`) and teal buttons is at least 4.5:1.
- **Keyboard and touch.** Rows, cards and buttons are native elements with a visible focus ring. "More about this" has a tap area a thumb can hit.
- `tests/ymt-pages.cjs` and `tests/test_ymt.py` hold all of this. Every kind of page, the family guide included, was also run through axe (WCAG 2.2 A and AA rules) at phone and desktop widths on 2026-11-15 with no violations.

## When someone shares a link

- **A picture goes with it.** Every page names a 1200 by 630 picture (`og:image`) that a phone, Facebook or a group chat shows beside a shared link: `assets/share.jpg` for Yoga Mom Talk, `ohio/assets/share.jpg` for OhioMom and `assets/share-family-guide.jpg` for the family guide. The address is always the full `https://www.yogamomtalk.com/...` one, because those apps do not follow relative addresses.
- **The tab and the home screen show our icon.** `assets/icon.svg` is the drawing; `assets/icon-48.png` and `assets/icon-180.png` are the same drawing for browsers and iPhones that want a fixed size.
- **The pictures are made, not edited.** `scripts/share_cards.py` fills in `templates/share-card.html` and photographs it. It is not part of the build; run it only to change a card, look at the result, and commit the pictures. Words on a card are a promise in a picture, so they must stay true of the site ("Free. No sign-up, no ads."). `tests/test_ymt.py` checks that every page names a picture that exists and has the right size.
- An app that already showed an old preview keeps it for a while. Facebook's Sharing Debugger and a new message thread on a phone both fetch the current one.

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

## Publishing to Wix

Merging a pull request does not change the live site by itself. There are two ways to publish.

**By hand (what has been done so far).** The changed files are sent through the Wix connector, each one checked by fingerprint against the live copy before and after.

**From GitHub (built, waiting for a key).** `.github/workflows/publish.yml` runs `scripts/publish_wix.py`:

- **check** compares the live site with the repository and changes nothing.
- **publish** sends the files, then reads the site back and compares again. It refuses to run if what is live is not the last upload, it never deletes a live file, and it only publishes from `main`.

To switch it on:

1. In Wix, generate an API key ([Wix's steps](https://dev.wix.com/docs/api-reference/articles/authentication/api-keys/generate-an-api-key)). Limit its site access to this site. Wix shows the key once, so keep the window open for step 2. Wix's steps also say where to find the account ID.
2. In this repository on GitHub: Settings, Secrets and variables, Actions, New repository secret. Add `WIX_API_KEY` (the key) and `WIX_ACCOUNT_ID` (the account ID). `WIX_SITE_ID` is optional; without it the site is found by its name, OhioMom.
3. Actions, "Publish to Wix", Run workflow, mode **check**. It should report that the live site matches the repository.

What is not yet proven: the calls are the ones in Wix's recipe for uploading a site, and Wix says API keys are meant for automation such as GitHub Actions, but Wix's recipe shows these calls with a login token and does not say outright that they accept an API key. The first check run settles it and changes nothing either way. If Wix refuses the key, the run says so, and publishing stays by hand. Once a check and one publish have gone through, adding `push: branches: [main]` to the workflow makes every merge publish itself.

`tests/test_publish.py` runs the script against a stand-in for Wix: the complete file set is sent, nothing live is deleted, a refused key or an unexpected live state stops everything, and the key is never printed.

## Still to settle

- **Hosting.** Decided: Wix headless serves the whole site. Wix keeps each Ohio page without its `wix-site-script` tag and adds the tag back when it serves the page, so the stored copy of those pages is the repo copy minus that one tag. Wix also serves its own `sitemap.xml` (it lists these pages), `robots.txt` and not-found page. Publishing is described under "Publishing to Wix" below; the automatic route is built but not switched on.
- **Domains.** Decided (Nov 15, 2026): `www.yogamomtalk.com` is the primary domain, and yogamomtalk.org and ohiomom.org redirect to it. The redirect keeps the path (checked Nov 15, 2026): `ohiomom.org/family-guide.html` lands on the family guide, so the Veteran Home Guardians guide's link and the QR code on the printed flyer work. One thing does not: the ohiomom.org home page lands on the national home page and not on OhioMom, because the visitor has already left ohiomom.org by the time the page loads. Sending it straight to `/ohio/` needs a redirect rule for that one address in the domain settings. No page on this site links to ohiomom.org (a test enforces it).
- **Corrections email.** The default is `travis@vethomeguard.org`; change it in `data/ymt/resources.json` and rebuild.
- **Trademark.** The name is a decision for later. It is kept in one config value so a change is a rebuild.
- **Phone numbers.** No number on the site has been dialed. They match the published sources named on each card, and the state records match the three national lists as of November 15, 2026. Ohio's energy assistance line (800-282-0880) is still printed by local agencies but no longer appears on the state's own pages since the program changed departments in April 2026; dial it once to confirm it still connects.
- County-by-county Ohio pages beyond the four now published (Job and Family Services, board of developmental disabilities, housing front door, energy assistance provider).

## Credit and license

The disability, neurodiversity and military-family listings are adapted from the family guide in the Veteran Resident Resource Guide, created by Travis Vought and shared by Veteran Home Guardians (CC BY 4.0). Data here is CC BY 4.0; code is MIT. See `LICENSE`.

## Resource ownership

Ohio autism, ADHD and family disability resources are owned by `travisvought-byte/Ohiomom` at https://www.ohiomom.org/family-guide.html, now part of this combined site. The family guide covers Ohio only. The multi-state family guide remains at https://guide.vethomeguard.org/family-guide.html?state=US. Mobility resources are owned by https://mobilitytalk.org/. Related sites should link to the owning site, not replicate its section.
