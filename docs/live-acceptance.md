# Live acceptance check (Release 1c)

Status: **not yet performed.** Everything below is a checklist for Kerry to run on the deployed site. Nothing here has been verified on the live site by anyone. Mark a line Pass only after you have done it and seen the stated result.

Repository tests (the Playwright and Node suites) check the code on a local server. They say nothing about what Netlify is serving, what your browser has cached, or the Supabase project. That is why these checks exist.

## Rules for the check

- Use a **separate browser profile** (Chrome: profile icon, Add, Continue without an account). Its storage is empty and cannot touch your working browser. Do not use a private window; it forgets everything when closed, so it cannot test persistence.
- Every record you create here is a **test record**: tick "This is a test record" when adding the company and start the name with `ZZ TEST`. Test companies carry a TEST label and are left out of the pilot counts and values. Delete the profile when you are done. Never enter test data in the working browser.
- Do not turn on Cloud Sync for any of this.
- If any line fails, stop and send the line number and what you saw. Do not widen the pilot until it is fixed.

## A. Which release is loaded (do this first)

1. Open the live site in the test profile. Open **Data & Backup**.
2. Read the line "This page is release ...". It should say release 1c and then "Server file says release 1c ... Matches this page."
3. If it says Mismatch or "Could not read": reload with the cache cleared (Ctrl+Shift+R), or close the tab and reopen it, then check again. Do not continue until it says Matches.

## B. Complete workflow (about 20 minutes)

| # | Do this | Expect | Result |
|---|---------|--------|--------|
| B1 | Companies: add `ZZ TEST Acme` with "This is a test record" ticked | TEST label in the list; "1 test company is left out of every number above" | |
| B2 | Add a contact, then an opportunity with a dated next step | Next step appears on Today, marked [TEST] | |
| B3 | Log an attempt with outcome Conversation (spoke, confirmed need, agreed next step) | Activity shows on the company; pilot counts stay at 0 | |
| B4 | Add a quote of 200 dollars marked "A recurring arrangement" and a second quote marked "One trip" | Each version shows its scope | |
| B5 | Accept the recurring quote | The screen says acceptance of a recurring arrangement and that dates are chosen later | |
| B6 | Create bookings: repeat weekly, 4 trips | Before saving, the preview lists 4 dates and says "Create 4 bookings". Weekly with no end is refused | |
| B7 | Cancel the second booking only | The other three stay scheduled; "Cancel this trip only" wording; cancelled value excluded | |
| B8 | Accept the one-trip quote, create its booking, then try a second | Second is refused | |
| B9 | Revise the accepted recurring quote to 230 dollars | v1 stays accepted at 200; existing bookings stay at 200 | |
| B10 | Open the Quotes tab (link a saved quote first if you have one) | A linked quote shows "Managed in Companies. Change it there." and no status dropdown | |

## C. Refresh and restart

| # | Do this | Expect | Result |
|---|---------|--------|--------|
| C1 | Reload the page | Everything from B is still there | |
| C2 | Close Chrome completely, reopen the profile and the site | Still there | |

## D. Restrictions

| # | Do this | Expect | Result |
|---|---------|--------|--------|
| D1 | Mark the test contact do not contact | Its next step leaves Today; any quote reminder moves to "Held for review"; existing bookings still show as service communication | |

## E. Backup and recovery

1. Data & Backup: Export Full Backup. Note the "Companies data fingerprint" shown there.
2. Open a **second** new profile with the site. Choose the backup file. Press **Check import (changes nothing)** and read the preview: format, creation date, fingerprint.
3. Press Restore (Replace). After the reload the fingerprint should equal the one from step 1, and every company, contact, opportunity, quote, booking and activity should be back with its links.
4. Conflict protection needs two different backups of the same accepted quote, which is awkward to stage by hand. The repository tests cover it; the in-app preview also reports "Merge would flag N conflicts" if you ever restore a file that disagrees with accepted terms.

| # | Result |
|---|--------|
| E1 export and fingerprint noted | |
| E2 preview shows format, date, fingerprint and changes nothing | |
| E3 Replace restore: fingerprint matches, relationships intact | |

## F. Pipeline link (only if you have an existing Pipeline prospect)

Link it to a TEST company (not a real one). In the Pipeline tab the card should say "Linked to Companies. Follow up there, not here." and offer only Open in Companies and Edit. It should not appear in the Pipeline action queue or in Pipeline's overdue count. The follow-up should show once, in Acquisition on Today.

## G. Cloud Sync (blocked; not needed for a local-only pilot)

Cloud Sync sign-in is blocked in the app until verification is recorded in Data & Backup. A local-only pilot does **not** need it. Do these on the Supabase project before ever recording verification:

1. Confirm the row-level security policies in `supabase/001_ob_store.sql` are applied to the live project.
2. Sign in as a second, separate account and confirm it cannot read the first account's rows.
3. Confirm public sign-up is off or restricted to the accounts you intend.
4. Only then tick the box and record what was checked and when in Data & Backup.

## Decision rule

- **Local-only pilot may proceed** when A, B, C, D and E all pass in the isolated profile (F if applicable).
- **Cloud Sync stays off** until G is done, whatever the other results.
- Any failure: stop, report the line, and wait for a fix.

## After the check

Delete the test profile. Confirm the working browser has no `ZZ TEST` records and that its fingerprint has not changed.
