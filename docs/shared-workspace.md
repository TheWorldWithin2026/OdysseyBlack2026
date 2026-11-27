# Shared workspace: what it would take, and how conflicts would be handled

Status: **not built. Not part of the pilot.** For the pilot, one designated working browser is the source of truth for Companies data. A second browser holds a separate, unmerged copy. This is a limitation, not a collaboration feature, and "Anthony" as an owner is only a label.

## What a shared workspace requires

1. **Sign-in.** Every person signs in with their own account. Today the app has no login of its own.
2. **A server-side store** for Companies data (companies, contacts, opportunities, quotes, bookings, activities, Pipeline links). Today it lives only in browser storage and is deliberately excluded from Cloud Sync.
3. **Workspace membership and row-level access rules.** Each record belongs to a workspace. Only members can read or change it. The rules must be enforced by the database, not by the page, and tested with a second, non-member account before real data is stored.
4. **Roles.** At minimum: who may lift a do-not-contact restriction, edit an accepted quote, or delete anything. Lifting a restriction should require a named person and a reason.
5. **Record versions.** Every record carries a version number or last-changed time set by the server, so a stale edit can be detected. IDs are already stable and unique.
6. **An audit trail.** Who changed what and when. Activities are already append-only records.
7. **An import path** from the working browser's backup, and a verified restore, before anyone else is added.
8. **Operating decisions:** who owns the data, who can see cost and profit (not stored in the app today), and how long records are kept.

## Proposed conflict rules

| Situation | Rule |
|---|---|
| Two people edit different fields of one record | Merge both changes. |
| Two people edit the same field | The later save is refused with the other person's value shown; the editor chooses. No silent overwrite. |
| Do-not-contact set by one person, record edited by another | The restriction always wins. It is only removed by an explicit, recorded lift. |
| Archive versus edit | The record stays archived. The editor is told and can restore it. |
| Accepted quote version | Immutable. A change is a new version. Two people adding a version at once get consecutive numbers; neither is lost. |
| Booking status | Allowed moves: scheduled to completed or cancelled, and back to scheduled with a logged reason. A concurrent change is refused and shown. |
| Duplicate booking | The same quote version, service date and time is refused by the server, as it is in the app today. |
| Activities and notes | Append-only. They never conflict. |
| Merge of two companies or contacts | One person at a time; others are blocked from editing the two records until it finishes. |
| Offline edits | Queued and replayed. Replays that conflict are shown for review, not applied silently. |

Backups remain necessary. A shared store does not replace a tested restore.

## Release 1c: what restore does when two copies disagree

This is the conflict handling the app has today. It applies to Restore (Merge) from a backup file; it is not a shared workspace.

- Records are matched by id. For an ordinary record the newer one wins, as before.
- **Accepted quote terms are protected.** If two copies of the same quote version differ in amount, vehicle, route, date, time or scope, and either copy was ever accepted, the accepted (or current) copy stays active. The other copy is kept in the Companies data as a conflict. A red notice appears in Companies and Quotes, and a critical row appears in Today.
- A quote with an open conflict cannot be accepted, revised or booked until you choose Keep current terms or Use restored copy. The choice and both versions are logged on the company.
- **Bookings keep their own agreed terms.** A booking with the same id but different amount, vehicle, route or quote version keeps the current terms and the other copy is flagged. Resolving a quote conflict never edits an existing booking.
- Restore (Replace) is different on purpose: it overwrites everything with the file. The restore preview says so, and says how many conflicts Merge would have flagged.
- A backup that carries a null for a key that already holds a list no longer replaces that list.

What still does not exist: automatic merging of two people's simultaneous edits, per-field merges, or any sync of Companies data between browsers.

## Release 1d: contact path, and what was removed

- **Contact path** on every company page: six ordered routes to find the person who books car service (company line, company website, referral, event or association, free LinkedIn X-ray, email lookup). Each route is logged with a result, a note and an optional source link. The page says "No booking contact yet" until a contact has a recorded check at level "Confirmed booker". The state is worked out from the contacts and routes, not stored, so it cannot disagree with them.
- Routes are stored on the company (`routes`, at most 20) and travel with Backup, Restore (Merge keeps the newer company copy) and company merges.
- **Removed:** Company Intel and 90-Day Plan. Both were built on the older Pipeline numbers that Companies replaces. Their stored data key `ob-cal-progress` is still accepted in old backups. The removed code is in git history (Release 1c).
- **Kept, moved to a Reference group:** War Room and Market Expansion. They hold written strategy and a Google Places search but track nothing. Treat the dollar figures and close rates in them as the author's estimates, not sourced results.
- **Renamed:** Gatekeeper Finder is now Contact Path. Its stored data (`ob-gatekeepers`) is unchanged.

## Release 1e: search area

- The badge at the top right is now a button. It opens a list of saved **search areas** (stored in `ob-areas`, included in Full Backup, not cloud-synced). Metro Atlanta is home and cannot be removed; sub-areas (Buckhead, Midtown, Downtown, Sandy Springs, Perimeter / Dunwoody, Alpharetta) are preset; any other place can be added with a "we serve this area" flag.
- The active area is a **setting, not a filter**. It sets the city in Contact Path searches, the Market Expansion (Google Places) search area, the default city for Company Research, and the area name given to newly created companies (blank at home, as before). It never hides, moves or recounts saved companies, so pilot counts do not change with the area.
- The Companies tab has a **Find companies in (area)** box: Google Maps search links by category. They open in a new tab and need no server key. Nothing returned is stored by the app; a company exists only once you add it.
- An area marked "not served" shows a warning before outreach. The Market Radar watchlist keeps its own curated areas and is not driven by this setting.

## Release 1f: find people at a company

- **Find people at a company** (top of the Companies tab): one box. It runs Company Research for the name, saves the company, and opens its page. A failed or empty lookup still saves the company, so the Contact path is never blocked. A company already researched is opened without a second lookup (the lookup costs money); "Research again" forces one. The older "Research now" buttons (Today and the company page) use the same flow and stay on Companies.
- **What it does not do:** find assistants by name. Public pages almost never list them, and the app never guesses a person. For assistants the company page gives a tap-to-call link to the saved main phone (with the question to ask), seven role searches by company and city (Google, new tab, nothing collected), and "Plan the first call for tomorrow", which creates one open opportunity with a dated next step.
- **Add all as listed contacts:** files each publicly listed leader as a contact at level "Publicly listed" (skipping people already saved). None counts as a booking contact until a check at level "Confirmed booker" is recorded.
- **City limit:** the research service only accepts Georgia metro-Atlanta cities. For other search areas the app sends Atlanta and the card says it is searching by company name alone.

## Release 1g: simplified app

Removed from the tab bar and the page: Market Radar, Prospect Builder, Apollo Import, Lookalikes, Pipeline (older), Forecast, Results, War Room, Market Expansion. Kept: Today, Companies, Contact Path, AI Outreach, Call Script, Quote Builder, Vendor Packet, Partners.

Why: the app exists to win executive clients. Companies, Contact Path and Today now cover finding companies, finding people and the next call. The removed tabs duplicated that, or tracked things (MRR targets, forecasts, market news) that do not help a first call.

Data safety: no storage key was removed. APPROVED_BACKUP_KEYS is unchanged, so Full Backup and Merge restore still carry ob-pipeline, ob-radar, ob-lookalike, ob-forecast and ob-research. Older Pipeline prospects still appear on Today under "Older prospects" and can be linked to a company. The header now counts Companies, Booker found and Due today.

Not removed: the unreachable renderer code and the places.js function stay in the repo for now. They are harmless and can be deleted in a later cleanup once Kerry confirms nothing is missed.

## Release 1h: essential usability fixes

Buttons and tabs are at least 44px tall on screens up to 900px wide. Text inputs are 16px so iPhones do not zoom on tap. The muted grey text now passes 4.5:1 contrast. Labels were already present on every field of the 8 remaining tabs. Not done on purpose: first-run checklist, collapsing long pages, self-hosted font.
