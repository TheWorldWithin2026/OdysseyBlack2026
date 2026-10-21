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
