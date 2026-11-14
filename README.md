# OhioMom

Source for **OhioMom.org**, an Ohio resource hub for mothers and caregivers: clear next steps for safety, housing and bills, disability and neurodiversity, and single-parent support.

## How it works

- `data/resources.json` contains the original general-help listings; `data/family-guide.json` owns the complete Ohio family guide. Each listing has a plain-language description, a next step, a phone or website, the published sources it was checked against, and the date it was checked.
- `python3 scripts/build.py` builds `family-guide.html` from `data/family-guide.json`, `data/family-counties.json` and `templates/family-guide.html`. Other live pages are static source.
- `python3 scripts/validate.py` checks the data before anything is published.

## Keeping it current

- Every push runs the validation and confirms the page matches the data.
- On the 3rd of each month, every listed website is requested automatically. If any fail, an issue is opened naming them so a person can review.

## Safety standards

- A "Leave this site" button is on every page.
- No tracking, cookies, sign-up or third-party scripts.
- Domestic violence shelter addresses are never listed. Listings point to the hotline or county program that places people safely.

## Still to settle

- County-by-county pages (Job and Family Services, board of developmental disabilities, housing front door, energy assistance provider).
- Live host: Wix, https://www.ohiomom.org/. The current static site is tracked here.

## Credit and license

The disability and neurodiversity listings are adapted from the family guide in the Veteran Resident Resource Guide, created by Travis Vought and shared by Veteran Home Guardians (CC BY 4.0). Data here is CC BY 4.0; code is MIT. See `LICENSE`.

## Resource ownership

Ohio autism, ADHD and family disability resources are owned by `travisvought-byte/Ohiomom` at https://www.ohiomom.org/family-guide.html. OhioMom covers Ohio only. The multi-state family guide remains at https://guide.vethomeguard.org/family-guide.html?state=US. Existing Ohio/default family-guide URLs redirect with their query parameters and fragments preserved. Other independently maintained assets remain in place until they have a working destination; related sites should link to the owning site, not replicate its section.
