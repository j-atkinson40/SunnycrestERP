# How to customize a template

For tenant admins who want to adjust the wording, layout, or branding
of a PDF or email the platform produces.

## What you're editing

Every document the platform renders — monthly statements, signing
invites, invoice emails, vault prints, certificates — is produced from
a **managed template** that lives in the template registry. Platform
templates are the defaults; tenant templates are per-licensee
overrides that take precedence when present.

You edit platform behavior by **forking to your tenant** first, then
editing the fork. The original platform template is never mutated by
a tenant edit.

## Find the template

1. Go to **Admin → Documents → Templates**.
2. Filter by the document type you care about (`invoice`,
   `statement`, `email`, `signing_certificate`, etc.).
3. Click the template row to open its detail page.

Each template has a **Scope** badge — `platform` or `tenant`.
`platform` means it's the default; `tenant` means it's your fork.

## Fork a platform template

If the template is scoped `platform`:

1. Click **Fork to tenant**.
2. Confirm. A new tenant-scoped template is created with the current
   platform version copied forward.
3. You're now editing your own copy. The platform template is
   unchanged and continues to ship to other tenants.

Only super-admins can edit platform templates directly — the fork
path is how tenants customize.

## Edit a template

Every template has a **current active version** and zero-or-more
drafts. You can't edit the active version directly — edits happen on
a draft, then you **activate** the draft to make it live.

1. On the template detail page, click **New draft**. This creates a
   draft version copied from the current active version.
2. Edit:
   - **Body template** — Jinja HTML. `{{ variable_name }}` for
     substitution, `{% for %}` / `{% if %}` for logic.
   - **Subject template** — for email only. Also Jinja.
   - **Variable schema** — optional. Names + expected shape for the
     context variables. Used by test-render.
   - **Sample context** — example values so you can click **Test
     render** and preview the output.
3. Click **Test render**. A modal shows the rendered HTML (or PDF
   download link). Errors render inline.
4. Iterate. The draft saves automatically; you can leave and come
   back.

## Activate the draft

When the rendered output looks right:

1. Click **Activate** on the draft.
2. Enter a **changelog** — a one-line summary that goes into the
   audit trail. "Added payment-plan paragraph" is fine; "updates" is
   not.
3. Confirm. The draft becomes the new active version; the previous
   active version is retired but stays in the version history. New
   renders use the new version from this moment forward.

## Roll back

Every activation is reversible:

1. Open the template's **Version history**.
2. Find the prior version you want to restore.
3. Click **Roll back**. Enter a rollback changelog.
4. The rolled-back version becomes active again.

The version you rolled back *from* stays in history — nothing is
deleted.

## Common gotchas

- **Jinja syntax errors** fail the test render. Read the error
  message; it identifies the line.
- **Unknown variables** render as empty strings by default.
  Double-check spelling against the sample context.
- **Variables with dots** — `{{ customer.name }}` works if `customer`
  is a dict. The workflow engine exposes step outputs as
  `{output.step_key.field}`.
- **Email tenant overrides** also need to respect any tenant
  branding settings (logo, primary color) — those come from company
  settings, not the template.

## Your customization is tenant-scoped

When you activate a draft, it affects **only your tenant**. Other
licensees continue to use the platform default. If you want a change
pushed upstream to the platform template, file a ticket — the
platform template registry is the source of truth for tenant defaults,
and changes there are reviewed by the Bridgeable team.

## Audit trail

Every draft, activation, rollback, and fork generates an entry in
`document_template_audit_log`. You can see the log on the template
detail page. The log records the actor (user + email), the action,
the changelog, and a timestamp.

If something rendered unexpectedly in production, the Document Log
(`/admin/documents/documents`) shows exactly which template + version
produced it — click into a row to see `template_key` + `template_version`.
