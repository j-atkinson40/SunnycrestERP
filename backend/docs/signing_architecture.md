# Bridgeable Signing — Architecture

Native e-signature infrastructure introduced in Phase D-4. Runs in
parallel with the existing DocuSign integration (DocuSign stays active
for disinterment until D-5 migrates it). Targets US ESIGN Act
compliance.

Audience: developers adding signing to a new flow, or reviewing legal
compliance.

---

## Concepts

- **Envelope** — a single signing request. Has a subject, a document,
  routing policy, and one or more parties.
- **Party** — a single signer. Each party gets a unique `signer_token`
  that's the sole authentication for their signing URL.
- **Field** — something a party fills in (signature, initial, text,
  checkbox, date). Placed in the PDF by `anchor_string` (text search)
  or explicit page + x/y position.
- **Event** — an append-only audit entry. Every envelope/party state
  transition writes one, with monotonically-increasing
  `sequence_number` per envelope.

---

## State machines

### Envelope

```
draft → sent → in_progress → completed
                           ↘ declined
                           ↘ voided
                           ↘ expired
```

- `draft` — creator can still edit parties/fields.
- `sent` — first party notified (sequential) or all parties notified
  (parallel).
- `in_progress` — at least one party has viewed the link.
- `completed` — all parties signed. Signed PDF + Certificate of
  Completion generated.
- `declined` / `voided` / `expired` — terminal dead states.

### Party

```
pending → sent → viewed → consented → signed
                                   ↘ declined
                                   ↘ expired
```

- `pending` — envelope created but this party hasn't been notified yet
  (sequential, still waiting their turn).
- `sent` — invite email fired.
- `viewed` — they opened the signing link.
- `consented` — they checked the ESIGN consent box.
- `signed` — signature captured + fields filled.

---

## Routing

**Sequential** (default): parties sign in `signing_order`. Party N+1
only gets notified after party N signs. First-view transitions the
envelope from `sent` → `in_progress`.

**Parallel**: all parties receive the invite at `send_envelope` time.
The envelope completes when the last party signs (any order).

---

## Token security model

- `signer_token` is generated via `secrets.token_urlsafe(32)` = 256
  bits, base64-urlsafe encoded, 43 chars, no padding.
- Unique across all parties (enforced by DB `UNIQUE` constraint).
- Not guessable, not correlated to any identifier.
- No expiry of the token itself — envelope-level `expires_at` controls
  the window. After expiry, action endpoints reject.
- Public routes are rate-limited to 10 req/min per token (in-process
  token bucket).

---

## ESIGN compliance — what we record

Per the US ESIGN Act (15 U.S.C. § 7001 et seq.):

| Requirement | How we meet it |
|---|---|
| **Intent to sign** | Party clicks "Continue to signing" on consent screen |
| **Consent to electronic business** | Explicit `consent_text` stored in `signature_events.meta_json` with the ESIGN consent paragraph |
| **Attribution** | `display_name` + `email` at envelope creation; typed-name or drawn-signature captured; IP + user-agent recorded with every action |
| **Record retention** | Document + certificate persisted in R2; `signature_events` is append-only |
| **Copy to signer** | `email.signing_completed` sent on completion with both the signed PDF and Certificate of Completion attached |

Tamper detection:
- `signature_envelopes.document_hash` — SHA-256 of the original document
  PDF at envelope creation.
- `certificate.signed_document_hash` — SHA-256 of the signed PDF after
  all signatures applied.

---

## Anatomy of a completion

When the last party signs:

1. `record_party_signature` captures the signature + fields → writes
   `signature_captured` + `party_signed` events.
2. `_advance_after_party_signed` detects that all parties have signed
   and calls `complete_envelope`.
3. `complete_envelope`:
   - Sets `envelope.status = "completed"`.
   - Writes `envelope_completed` event.
   - `signature_renderer.apply_signatures_as_new_version()` produces
     the signed PDF as a new `DocumentVersion` on the original
     Document.
   - `certificate_service.generate_certificate()` produces the
     Certificate of Completion as a canonical `Document` via the
     managed `pdf.signature_certificate` template. Points
     `envelope.certificate_document_id` at it.
   - `notification_service.send_completed()` emails all parties with
     the signed PDF + certificate as attachments.

Each step writes its own `signature_event`. Failures in rendering or
notification are non-fatal (the completion still persists) but write
`*_failed` events for admin visibility.

---

## Developer usage

### Creating an envelope from a generator

```python
from app.services.signing import signature_service

envelope = signature_service.create_envelope(
    db,
    document_id=doc.id,
    company_id=company.id,
    created_by_user_id=current_user.id,
    subject="Disinterment Release Form",
    description="Signed authorization for disinterment of remains",
    parties=[
        signature_service.PartyInput(
            signing_order=1, role="funeral_home_director",
            display_name="Jane Smith", email="jsmith@fh.com",
        ),
        signature_service.PartyInput(
            signing_order=2, role="next_of_kin",
            display_name="John Doe", email="jdoe@gmail.com",
        ),
    ],
    fields=[
        signature_service.FieldInput(
            signing_order=1, field_type="signature",
            anchor_string="/sig_fh/",
        ),
        signature_service.FieldInput(
            signing_order=2, field_type="signature",
            anchor_string="/sig_nok/",
        ),
    ],
    routing_type="sequential",
    expires_in_days=30,
)
signature_service.send_envelope(db, envelope.id)
db.commit()
```

### Listing / observing envelopes

```python
envelopes = db.query(SignatureEnvelope).filter(
    SignatureEnvelope.company_id == company_id,
    SignatureEnvelope.status == "in_progress",
).all()
```

The admin UI at `/admin/documents/signing/envelopes/{id}` renders the
same data plus the events timeline.

---

## Anchor-based overlay (Phase D-5)

D-4 shipped a cover-page approach — signatures listed on an appended
page. D-5 replaces it with **inline overlay on the original document
pages** using PyMuPDF.

### How it works

1. `signature_renderer.render_signed_pdf(envelope)` fetches the current
   document PDF from R2.
2. For each `SignatureField` with a resolved signature (party has
   `status == "signed"`), build an `OverlaySpec`:
   - `image_bytes` — PNG of the drawn or typed signature
     (`_signature_image.signature_image_for_party`).
   - `anchor_string` OR explicit `page_number + position_x + position_y`.
   - `x_offset_pt`, `y_offset_pt` — fine-tune placement without
     re-rendering the source template.
3. `_overlay_engine.apply_overlays(src_pdf, specs)` opens the PDF once,
   calls `page.search_for(anchor)` on each page to resolve anchor
   positions, places every signature, and returns the modified bytes.
4. The result is uploaded as a new `DocumentVersion` on the envelope's
   Document (via the same mechanism as a D-1 re-render).

Graceful degradation: if the anchor isn't found AND no explicit
position is configured, that specific overlay is skipped (a
`signed_pdf_anchors_missed` event is logged for admin visibility). If
the PDF read / overlay library fails entirely, the renderer falls back
to the D-4 cover-page path so a signed artifact still exists.

### Adding anchors to a new template

1. Place the literal anchor string in the Jinja template at the
   signature line location:
   ```html
   <span class="sig-anchor">/sig_director/</span>
   ```
2. Style `.sig-anchor` so the text is invisible in the rendered PDF
   but still extractable by `page.search_for`:
   ```css
   .sig-anchor { color: white; font-size: 1px; }
   ```
3. Reference the anchor from your `FieldInput`:
   ```python
   FieldInput(
       party_role="funeral_home_director",
       field_type="signature",
       anchor_string="/sig_director/",
       anchor_y_offset=-30,  # shift signature slightly up
   )
   ```

Name your anchors uniquely across the document — `search_for` returns
the first match per page. `/sig_{role}/` is a solid convention.

### Anchor vs. explicit position

**Prefer anchors.** They survive template edits (renamed fields, page
count changes) because placement re-resolves on every render.

**Use explicit page + position** only when:
- The template doesn't support adding anchor text (e.g. a scanned PDF
  you're stamping).
- You need pixel-level control that anchors can't express (e.g. a
  signature that must align with pre-printed graphics).

### Signature image rendering

`_signature_image.signature_image_for_party` picks between:
- **Drawn**: decoded from the signer's base64 canvas PNG, resized to
  fit the field bounds preserving aspect ratio, transparent letterbox.
- **Typed**: rendered via PIL using Caveat-Regular.ttf if bundled under
  `app/services/signing/fonts/`, otherwise a fallback italic or PIL
  default. Auto-shrinks to fit the target rect.

Both paths return PNG bytes at 3× points-per-inch-equivalent for
crispness at print resolution.

### Tuning placement

`SignatureField.anchor_x_offset`, `anchor_y_offset`, `anchor_units`
(currently `"points"` only — inches/cm are future work) let an admin
adjust placement **without editing the template source**. This is
useful for templates where the anchor text lands slightly above or
beside where the signature line is drawn.

## Disinterment migration (Phase D-5)

D-5 migrated the disinterment release-form flow off DocuSign. Changes:

- `DisintermentCase.signature_envelope_id` — new FK to the native
  envelope. `disinterment_cases.docusign_envelope_id` stays for any
  in-flight DocuSign envelopes created pre-cutover.
- `disinterment_service.send_for_signatures` now calls
  `signature_service.create_envelope` with four parties
  (`funeral_home_director`, `cemetery_rep`, `next_of_kin`,
  `manufacturer`) and four anchor-mapped fields.
- `signature_service.sync_disinterment_case_status` mirrors party
  status into the legacy `sig_*` columns on every transition so code
  that still reads them sees consistent state.
- `docusign_service` + `docusign_webhook` marked deprecated (module
  docstring + `DeprecationWarning` in `create_envelope`). Webhook
  still receives events for pre-cutover envelopes.

Once `SELECT COUNT(*) FROM disinterment_cases WHERE
docusign_envelope_id IS NOT NULL AND status IN
('signatures_pending', 'signatures_sent')` returns 0 in production,
the DocuSign code can be deleted.

## Future work

- **SMS verification**: `SignatureParty.phone` accepts numbers but D-4/D-5
  do nothing with it. Native SMS ships separately.
- **Workflow engine `request_signature` step**: expose envelope
  creation as a managed workflow step type so orchestrated flows
  (intake → draft → sign) compose naturally. D-6+ scope.
- **Cremation authorization migration**: still uses manual sign-off
  fields; deferred to a separate focused build.
- **Notarization, bulk signing** — indefinitely deferred.
- **DocuSign code deletion**: after all legacy envelopes resolve.

---

## Database tables

See `backend/alembic/versions/r23_native_signing.py`.

- `signature_envelopes`
- `signature_parties`
- `signature_fields`
- `signature_events`

Plus five platform templates seeded:
- `pdf.signature_certificate`
- `email.signing_invite`
- `email.signing_completed`
- `email.signing_declined`
- `email.signing_voided`

All templates are tenant-customizable via the D-3 fork-to-tenant flow.
