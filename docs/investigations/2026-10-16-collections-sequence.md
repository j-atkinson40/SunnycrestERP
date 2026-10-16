# What does COLLECTIONS_SEQUENCE do when it succeeds, and who would it contact?

Read-only. James's question, 2026-10-16, asked before anyone fixes the job: *"If it emails
funeral homes about overdue balances, fixing it could suddenly start sending reminders to
real customers."*

**Environment.** Production figures from read-only probes via `railway run` with
`default_transaction_read_only=on`, target `shuttle.proxy.rlwy.net:57253/railway`. No
query bounded except where stated. Code citations are `file:line`.

---

## The short answer

**It drafts. It does not send.** And right now it could not send even if someone tried:
the human Send route is broken by a second, separate bug that the job's failure has been
hiding.

Fixing the nightly job would produce, for Sunnycrest, **two draft emails and two
`action_required` alerts about two seeded demo customers at `.example.com` addresses** —
not real funeral homes. It would also make two Claude API calls.

---

## 1. What a successful run actually does

`agent_service.run_collections_sequence`. Per due sequence:

| Step | Effect |
|---|---|
| selects | `agent_collection_sequences` where `next_scheduled_at <= now`, `paused` false, `completed` false |
| drafts | an email body via the managed prompt `agent.ar_collections.draft_email` (a **Claude call**), tier from `sequence_step`: 1→FOLLOW_UP, 2→ESCALATE, 3→CRITICAL |
| writes | `draft_subject`, `draft_body`, `original_draft_body` **on the sequence row** |
| writes | `next_scheduled_at = now + 14 days` |
| writes | one `agent_alerts` row, severity **`action_required`**, titled *"Collections email ready for {customer}"*, `action_url=/ar/collections/{id}/review` |
| writes | one `agent_activity_log` row |

**No outbound mail.** `send_collections_email` is never called from the job.

## 2. Who sends, then

A human, through `POST /api/v1/agents/collections/{sequence_id}/send`
(`app/api/routes/agents.py:168-221`). That route calls
`email_service.send_collections_email(...)` with `body.recipient_email` — **the recipient
comes from the request body**, not from the sequence. So the nightly job cannot cause a
send under any circumstance; somebody has to open the review page and submit.

⚠️ **AND THE INVOICE-EMAIL SWITCH ADDED IN STEP 2 DOES NOT COVER THIS PATH.** That switch
guards `email_service.send_invoice_email`. Collections go through
`send_collections_email`, a different function, and are ungated. Stated plainly because
"there is a tenant switch now" would otherwise read as covering more than it does. It was
not widened here: the dispatch asked for invoice sending to be gated, and quietly
extending a switch to a second channel is the kind of scope drift that makes a later
reader unsure what the switch means.

## 3. ⚠️ The Send route is broken, and the job's failure has been concealing it

`app/api/routes/agents.py:197`:

```python
customer_name=seq.customer_name or "Valued Customer",
```

`AgentCollectionSequence` has **no `customer_name`** — not as a column, not as a mapped
attribute. Measured both ways:

```
hasattr(AgentCollectionSequence, 'customer_name')  ->  False

information_schema columns: completed, created_at, customer_id, draft_body,
draft_subject, id, invoice_id, last_sent_at, next_scheduled_at, original_draft_body,
pause_reason, paused, sent_without_edit, sequence_step, tenant_id, updated_at
```

So the route raises `AttributeError` **before** reaching `send_collections_email`. It
cannot send.

⚠️ **This is the shape `CLAUDE.md §11` records for `run_ar_aging_monitor`, repeated.** The
nightly job has raised on every run since 2026-09-10, so no draft was ever written, so no
alert was ever raised, so nobody ever opened the review page, so nobody ever clicked Send
— and an `AttributeError` on the send path has sat there unexecuted, wearing the look of
tested code. The §11 entry's own warning applies: *"the size of the fix is not evidence
about the size of the problem"*, and *"run the repaired path before believing the repair is
the whole of it."*

**Corroborated by the data, not only by reading:** `last_sent_at IS NOT NULL` returns
**0 rows across every tenant on production**. A collections email has never been sent.

## 4. Why the job itself fails

`unsupported operand type(s) for -: 'datetime.date' and 'datetime.datetime'`, every
scheduled run since **2026-09-10 23:05 UTC** (35 days as of writing), 3 of 4 tenants.

`agent_service.py`, inside the per-sequence loop:

```python
days_overdue = (date.today() - invoice.due_date).days if invoice.due_date else 0
```

`Invoice.due_date` is `Mapped[datetime]` (`app/models/invoice.py:46`). `date - datetime`
raises. ⚠️ Same defect class as the one `CLAUDE.md §11` already documents for
`run_ar_aging_monitor` — a `date` minus a `datetime` — in a different job.

**Not fixed here.** This is a read-only report.

## 5. Who would be contacted if it were fixed

Production, unbounded.

### Sunnycrest — 2 due sequences, neither ever sent

| customer | email on file | sequence step | due since | invoice | outstanding |
|---|---|---|---|---|---|
| St. Mary's Cemetery | `ap@demo2-c002.example.com` | 2 (ESCALATE) | 2026-09-25 | INV-2026-0003 | $98.93 of $4,946.43 |
| Riverside Memorial Chapel | `ap@demo2-c003.example.com` | 1 (FOLLOW_UP) | 2026-10-02 | INV-2026-0002 | $400.00 of $2,150.00 |

⚠️ **BOTH ARE `.example.com`, WHICH IS RFC 2606 RESERVED-FOR-DOCUMENTATION.** These are
seeded demo customers, not real funeral homes, and mail to those addresses is
unroutable by design. Note also that neither is a funeral home — one is a cemetery and
one is a chapel — and both invoices are `partial` rather than unpaid: the balances are
$98.93 and $400.00, the residue of payments already made.

So the specific risk James named — reminders going to real customers — **is not present
for Sunnycrest today.** What a fix would produce is two drafts about demo rows.

### Every tenant

| tenant | due, unpaused, incomplete | ever sent |
|---|---|---|
| sunnycrest | 2 (steps 1 and 2) | 0 |
| st-marys | 2 (step 2) | 0 |
| testco | 2 (steps 1 and 2) | 0 |

`agent_collection_sequences` with `last_sent_at IS NOT NULL`: **0, all tenants.**

## 6. What I would want before fixing it

Not a plan, and not in scope — the things a fix dispatch should decide:

1. **Fix the send route too, or fix neither.** Repairing the job alone puts two
   `action_required` alerts in front of the office saying "Collections email ready",
   whose Send button 500s. That is worse than silence: it looks like a feature and fails
   on use. §11's *"a failure can be the only thing preventing a worse one"* cuts the other
   way here — the broken job is also what keeps a broken button out of sight.
2. **Decide whether collections email needs its own tenant switch.** The invoice switch
   does not cover it (§2). Given `sent_rows = 0` platform-wide, defaulting it off costs
   nothing and matches how the invoice side was just handled.
3. **The demo sequences are probably worth retiring rather than drafting against.** Two
   of Sunnycrest's three collection sequences point at seeded `.example.com` customers.
   Drafting Claude-written dunning letters about demo rows spends money to produce noise.
4. **Check `_draft_collections_email` for its own unexecuted lines** before trusting that
   the TypeError is the whole of it. Everything after the raise in that loop has never
   run — the Claude call, the prompt mapping, the fallback body, the alert. §11: run the
   repaired path.
