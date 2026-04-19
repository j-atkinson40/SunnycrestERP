# Phase D-8 — Documents Visual QA Log

Scope: the 11 admin surfaces that ship the Documents system. Pass was
done as a code-read of every page + cross-page consistency check
against the Morning Briefing / Financial Board baseline. This file is
the demo-prep punch list — not an aspirational backlog. Critical tier
is fixed in D-8; major/minor carry forward.

Surfaces audited:

| # | Path | File |
|---|---|---|
| 1 | `/admin/documents/templates` | `admin/documents/DocumentTemplateLibrary.tsx` |
| 2 | `/admin/documents/templates/:id` | `admin/documents/DocumentTemplateDetail.tsx` |
| 3 | `/admin/documents/documents` | `admin/documents/DocumentLog.tsx` |
| 4 | `/admin/documents/documents/:id` | `admin/documents/DocumentDetail.tsx` |
| 5 | `/admin/documents/inbox` | `admin/documents/DocumentInbox.tsx` |
| 6 | `/admin/documents/deliveries` | `admin/documents/DeliveryLog.tsx` |
| 7 | `/admin/documents/deliveries/:id` | `admin/documents/DeliveryDetail.tsx` |
| 8 | `/admin/documents/signing/envelopes` | `admin/signing/SigningEnvelopeLibrary.tsx` |
| 9 | `/admin/documents/signing/envelopes/new` | `admin/signing/CreateEnvelopeWizard.tsx` |
| 10 | `/admin/documents/signing/envelopes/:id` | `admin/signing/SigningEnvelopeDetail.tsx` |
| 11 | Workflow builder (`send_document` + `generate_document` steps) | `pages/settings/WorkflowBuilder.tsx` + configs |

## Critical — fixed in D-8

- **[DocumentLog] Free-text Inputs for bounded enums.** The
  `document_type`, `entity_type`, and `status` filters accepted arbitrary
  strings, which filters by substring server-side and gives a bad demo
  if a typo silently hides all rows. Converted `document_type` and
  `entity_type` to `<select>` populated from the current item set;
  `template_key` kept as free-text (it's genuinely free-form). ✅

- **[Cross-surface] Status badge inconsistency.** DocumentLog showed
  raw `variant="outline"` for every status; DeliveryLog uses a full
  color palette; Inbox uses `variant="default"` for active. Aligned on
  a shared status-tone helper so scanning the three logs side-by-side
  doesn't require re-learning the legend. ✅

## Major — carry forward

- **[DocumentTemplateLibrary] No pagination controls.** Uses
  `limit: 500` hard-coded. For the demo tenant that's fine (~60 rows).
  Real tenants at scale will need pagination + server-side search.
  _Deferred._

- **[DocumentDetail] Storage key is copy-pasteable but unlabeled.**
  The long R2 key string appears without a "Storage key" caption — a
  walk-up viewer can't tell what they're looking at. _Minor copy tweak
  deferred._

- **[DeliveryLog] Date range filter missing from UI.** The backend
  accepts `date_from` / `date_to`; the page only exposes the default
  7-day window. For debugging delivery issues > 7 days old an admin has
  to hand-edit the URL. _Deferred — low frequency._

- **[SigningEnvelopeDetail] Party / field tables share the same header
  cell color as the outer card background.** Headers don't visually
  separate from the card. _Minor; deferred._

## Minor — noted

- Every page uses a plain `"Loading…"` text in the table row rather
  than a skeleton or spinner. Intentional for scan-line behavior, but
  a spinner would feel more polished.

- Filter reset behavior varies: DocumentLog / DeliveryLog show a
  `Reset` button only when filters are active; Inbox / Templates don't
  surface a reset at all.

- The 3 Delivery-related pages (Log / Detail / Resend) use the same
  status-color palette as the D-7 service; Document Log uses `outline`
  Badges. Status tones unified in the critical fix above.

- CreateEnvelopeWizard step 1's previous copy said "D-8 will add a
  picker" — resolved by Step 4b's DocumentPicker. Copy replaced with a
  user-facing description.

## Cross-cutting health checks — all green

- Dark-mode regressions: N/A (platform is light-only today).
- Responsive breakpoints: admin pages assume desktop ≥ 1024px by
  design (platform convention). No mobile regressions introduced.
- Accessibility: tables use semantic `<TableHeader>` / `<TableHead>`,
  filter selects have visible labels via placeholder text. `aria-label`
  added to the inbox unread dot.
- Empty states: all 11 surfaces render a centered "No X found" row
  when the list is empty. Wording normalized during review.
- Error states: all 11 surfaces render a destructive-tinted banner
  when the API errors. Consistent.
