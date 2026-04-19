# How to send a document for signing

Native e-signature — no DocuSign, no third-party portal. The signer
receives an email, opens a hosted signing page, types their name /
draws a signature / checks boxes, and submits. The platform overlays
the captured signatures onto the original PDF and issues a completion
certificate.

## Prerequisites

You need a **Document** in the system — signing is always against a
canonical `Document`. Invoices, release forms, contracts, anything
produced through a template will work. Ad-hoc PDFs can be uploaded
through the document generator first.

Your PDF should include **anchor strings** at the positions where
signatures go. Anchors look like `/sig_customer/` or `/initial_fh/` —
any unique token the signer-position matcher can find in the PDF
text. If the document has no anchors, signatures still capture but
render on a cover page rather than inline.

## Create the envelope

1. Go to **Admin → Documents → Signing Envelopes**.
2. Click **New envelope**. The 4-step wizard opens.

### Step 1 — Select document

The **DocumentPicker** lists your tenant's recent documents. Search
by title, type, or ID. Click a row to select it.

- The preview card shows the title, type, template key, created-at
  timestamp, and full UUID.
- If the document isn't in the recent list (historical, testing),
  click **Advanced: paste a document UUID** and paste it directly.
- Enter a **Subject** — this is what signers see in their email.
- Optionally add a **Description**.

### Step 2 — Signers

- Name, email, and role for each signer. Role is free text ("signer",
  "funeral director", "customer") — it shows in the signing UI.
- Add additional signers with **Add signer**. The order in this list
  determines signing order when **Routing = Sequential**.
- Sequential: signer 1 completes, then signer 2 is invited, etc.
- Parallel: all signers invited at once.

### Step 3 — Signature fields (optional)

- If you skip this step, signers' captured signatures render on a
  cover page appended to the document.
- To render inline, add a field per anchor:
  - **Signer** — which party this field is for.
  - **Field type** — signature / initial / date / typed_name / text
    / checkbox.
  - **Anchor** — the literal text in the PDF to position against,
    e.g. `/sig_fh/`.
  - **Label** — optional helper text shown in the signing UI.

### Step 4 — Review + create

- Pick **routing** (sequential vs. parallel) and **expires in** days
  (default 30).
- Click **Create envelope**. The envelope is created as a **draft**.
  Nothing is sent yet.

## Send the envelope

On the envelope detail page:

1. Verify the summary, signers, and fields.
2. Click **Send** (top-right).
3. Emails go out immediately (or just to signer 1 for sequential
   routing). The envelope status moves `draft → out_for_signature`.

## What happens on signer side

1. The signer receives an email with a tenant-branded signing invite.
2. They click through to a hosted signing page — no account required,
   no app install.
3. They review the PDF, sign where indicated, and submit.
4. The next signer (sequential) or the envelope itself (parallel last
   signer) is notified.

## Tracking progress

On the envelope detail page:

- **Parties** — who's signed, who's pending, timestamps.
- **Timeline** — every event in the envelope lifecycle: created,
  sent, party-opened, party-signed, completed, voided, expired.
- Click **Resend** to re-trigger a signer email (counts toward the
  envelope's email quota; signers won't receive duplicate emails in
  quick succession).

## Completion

When the last signer signs:

1. Status moves to **Completed**.
2. The platform overlays all captured signatures onto the original
   PDF, producing a new `DocumentVersion` (the signed copy).
3. A **Certificate of Completion** is generated — a separate
   `Document` listing every signer, their timestamps, email, IP, and
   the hash of the final signed PDF.
4. Both documents are downloadable from the envelope detail page.

## Voiding

If something's wrong:

1. Click **Void envelope**.
2. Enter a reason — stored on the envelope for audit.
3. Pending signers receive a cancellation email. The envelope can
   never be re-activated; create a new one if you need to restart.

## Gotchas

- **Anchors must be present in the PDF text layer.** Scanned PDFs
  without OCR don't work — the matcher has no text to search.
- **Anchor strings must be unique.** If `/sig/` appears three times
  in the document, the field won't know which location to use. Use
  specific anchors like `/sig_customer/` and `/sig_witness/`.
- **Sequential routing blocks** if an early signer doesn't respond.
  The envelope sits in `out_for_signature` until they sign, decline,
  or the envelope expires. Resend / void as needed.
- **Declined envelopes can't be edited or re-sent.** Create a new
  envelope referencing the same document.

## Where it all lives

- **Envelopes**: `/admin/documents/signing/envelopes`
- **Source document**: linked on the envelope detail page — opens
  DocumentDetail.
- **Certificate of completion**: a separate Document with
  `document_type = signing_certificate`, linked from the envelope.
- **Audit trail**: Every envelope event is a row in
  `signature_events`. Visible on the envelope detail's Timeline panel.

For the architecture behind the anchor matcher, signature capture
pipeline, and certificate generation, see
[signing_architecture.md](./signing_architecture.md).
