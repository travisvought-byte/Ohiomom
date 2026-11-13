# OhioMom

Source for **OhioMom.org**, an Ohio resource hub for mothers and caregivers: clear next steps for safety, housing and bills, disability and neurodiversity, and single-parent support.

## How it works

- `data/resources.json` is the single source of every listing. Each listing has a plain-language description, a next step, a phone or website, the published sources it was checked against, and the date it was checked.
- `python3 scripts/build.py` writes `index.html` from that file and `templates/index.html`. Never edit `index.html` by hand.
- `python3 scripts/validate.py` checks the data before anything is published.

## Keeping it current

- Every push runs the validation and confirms the page matches the data.
- On the 3rd of each month, every listed website is requested automatically. If any fail, an issue is opened naming them so a person can review.

## Safety standards

- A "Leave this site" button is on every page.
- No tracking, cookies, sign-up or third-party scripts.
- Domestic violence shelter addresses are never listed. Listings point to the hotline or county program that places people safely.

## Still to settle

- `site.founder` and `site.corrections_email` in `data/resources.json` are empty; the founder credit and "Report a problem" link appear once they are filled in.
- County-by-county pages (Job and Family Services, board of developmental disabilities, housing front door, energy assistance provider).
- Domain: point ohiomom.org at this site.

## Credit and license

The disability and neurodiversity listings are adapted from the family guide in the Veteran Resident Resource Guide, created by Travis Vought and shared by Veteran Home Guardians (CC BY 4.0). Data here is CC BY 4.0; code is MIT. See `LICENSE`.
