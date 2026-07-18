# Plaid Integration — Investigation / Scoping

**Date:** 2026-07-18 · **HEAD:** `026913ce` (Reframe R-2, landed + deployed) · **Read-only — no build, no keys.**

**The operator's direction:** Plaid for bank + credit-card reconciliation — the LAST piece of
the accounting area, and the reframe's own example sentence made real ("the automation that
pulls the bank statement in and auto-categorizes"). Banked calls: **Sandbox for September**
(production application runs in parallel on the operator's side); the **sync-cadence call is
delegated to this investigation** (§4); the build phases follow (§6).

**The one-paragraph verdict up front:** the seam is smaller than feared. The reconciliation
matcher already consumes a generic bank-row shape and knows nothing about CSV; a durable
`BankTransaction` feed model slots in beside it (§1). The encryption substrate **already
exists** (Fernet + `CREDENTIAL_ENCRYPTION_KEY`, four production consumers) — Plaid tokens
need zero new crypto, only the discipline to not repeat QBO's plaintext mistake (§2). The
Link widget fits the house pattern (npm wrapper, Turnstile precedent; no CSP in the way)
(§3). The cadence evidence argues **polling, twice daily** — webhooks are an upgrade path,
not a September need (§4). Three phases, ~3 sessions (§6).

---

## 1. THE D-3 ALIGNMENT (the seam that decides the size)

### What the matcher consumes today

The reconciliation feature lives in `backend/app/models/financial_account.py` (4 models) +
`backend/app/api/routes/reconciliation.py` (the matching engine is inlined in the route,
lines 253–411 — there is no reconciliation_service.py). Zero Plaid traces anywhere.

The bank-side row is **`ReconciliationTransaction`** (`financial_account.py:76`): signed
`amount` Numeric(12,2) (positive=credit/deposit, negative=debit), `transaction_date`,
`description` + `raw_description`, `transaction_type` ("credit"/"debit"), optional
`reference_number`, plus the match fields (`match_status` default "unmatched",
`match_confidence`, `matched_record_type`/`matched_record_id` soft pointers).

**How rows arrive today: manual CSV upload, per run.** `POST /reconciliation/runs/start`
(statement date + closing balance) → `POST /runs/{id}/upload-csv` (heuristic column
detection, mapping memorized per account on `FinancialAccount.csv_*` columns) →
`POST /runs/{id}/run-matching`. The matcher pools `CustomerPayment` + `VendorPayment` in
the statement window, direction-honest (credits ↔ customer payments, debits ↔ vendor
payments), and matches on **amount + 5-day date window + reference number** — statuses
`auto_cleared` / `suggested` / `bank_fee` / `payroll` / `nsf` / `unmatched`, then the manual
action vocabulary. Confirm requires |difference| ≤ 0.005 and stamps the account's
`last_reconciled_*`.

**Credit cards are already first-class**: `FinancialAccount` carries `credit_limit` and
`statement_closing_day` specifically for cards; cards reconcile through the same
run/CSV/matcher machinery. No separate model needed.

### Mapping Plaid's transaction shape

| Plaid field | Lands where | Note |
|---|---|---|
| `transaction_id` | **`external_id` — the idempotency key** | The field the current substrate completely lacks |
| `account_id` | FK → the account (via `plaid_accounts`, §2) | |
| `amount` | `amount`, **sign-flipped** | Plaid: positive = money OUT (debit). Platform: positive = credit/deposit. One deliberate negation at ingest, tested hard — sign bugs here are the classic Plaid integration wound |
| `date` / `authorized_date` | `transaction_date` (posted date) | keep `authorized_date` alongside |
| `name` / `merchant_name` | `description` / `raw_description` | |
| `pending` (bool) | `is_pending` | pending→posted arrives as REMOVE(pending id) + ADD(posted id with `pending_transaction_id` linking) — the ingest must re-link, not duplicate |
| removals (`removed[]` in sync) | soft-delete + **un-match** | a retracted transaction must not linger matched (§4) |
| `personal_finance_category` | the categorization map (§4) | |

### The verdict: a clean `BankTransaction` feed model — NOT an extension

`ReconciliationTransaction` cannot be the system of record for a continuous feed, and the
blocker is **lifecycle, not columns**: rows are delete-orphaned children of a manually
started run (`reconciliation_run_id` NOT NULL, CASCADE), with no external id and no unique
constraint — re-pulling a window would duplicate silently, and deleting a run destroys the
"statement." Bolting `external_id` + a nullable run FK onto it would fork its semantics
(some rows durable feed, some ephemeral CSV children) and strand the CSV-shaped counters.

**The design:** a durable **`bank_transactions`** table owns feed identity (unique
`(tenant_id, plaid_transaction_id)`), FK'd to `financial_accounts`, run-independent. The
reconciliation run gains a second source: `run-matching` materializes its
`ReconciliationTransaction` rows **from the feed** for the statement window (CSV path
untouched — both sources produce the same rows the matcher already reads). Each
materialized row carries `bank_transaction_id` (nullable FK) so feed-side removals can
un-match run-side rows.

**Sizing both:** extend-in-place ≈ save one table + one materialization function, at the
cost of forked lifecycle semantics and a dedup story the table can't express — false
economy. Feed-model ≈ 1 table + 1 materialization function + the removal hook; the matcher
changes **zero lines**. Feed model wins; this is an extension seam, not a rework.

---

## 2. THE MODELS + THE SECRETS POSTURE (the crown jewels)

### The models (migration r133)

**`plaid_items`** — one row per tenant↔institution connection:

| Field | Notes |
|---|---|
| `id`, `tenant_id` FK companies.id NOT NULL indexed | house pattern |
| `plaid_item_id` String, unique | Plaid's item identity |
| `institution_id`, `institution_name` | display + re-auth context |
| `access_token_encrypted` Text | **Fernet ciphertext, actually fed** (see below) |
| `sync_cursor` Text nullable | `transactions/sync` cursor — per-item, updated only after a page is durably committed |
| `status` String | `active` / `login_required` / `pending_expiration` / `error` / `disconnected` |
| `last_error_code`, `last_synced_at` | the honest degradation surface (§3 re-auth) |
| `is_active`, audit stamps | house pattern |

**`plaid_accounts`** — one row per account under an item: `plaid_item_id` FK,
`plaid_account_id` (unique with tenant), `name`, `official_name`, `mask` String(4),
`type`/`subtype` (Plaid's own: `depository/checking`, `credit/credit card`),
`current_balance`/`available_balance` snapshots, and **`financial_account_id` nullable FK →
`financial_accounts.id`** — the link that hands the feed to the existing reconciliation
substrate. Linking is an explicit tenant-admin step (map this Plaid account onto this
platform account, or create a `FinancialAccount` from it in one click); unlinked accounts
sync but don't reconcile.

**`bank_transactions`** — the feed (§1): tenant + `plaid_account_id` FK +
`plaid_transaction_id` (partial-unique per tenant) + `pending_plaid_transaction_id`
(the pending→posted re-link) + amount (platform sign) + dates + descriptions +
`plaid_category_primary`/`plaid_category_detailed` + `expense_category` (post-mapping,
nullable = honest uncategorized) + `is_pending` + `removed_at` (soft retraction) +
audit stamps.

**Tenant isolation with full not-found rigor, pinned from day one.** Cross-tenant bank
data is the catastrophic class. Every read scopes `tenant_id == current_user.company_id`
inside the query (not post-filter); wrong-tenant ids return 404 indistinguishable from
absent; the test file ships cross-tenant pins for every endpoint in B-1 **before** any
sync code lands (the portal cross-realm test discipline, applied here).

### Encryption at rest — what exists (mapped honestly)

**The substrate exists and is production-proven.** Fernet under a single platform master
key in env var `CREDENTIAL_ENCRYPTION_KEY` (deliberately NOT in config.py — read from
os.environ inside the crypto modules so it never enters the settings object), with four
consumers: `credential_service.py` (TenantExternalAccount), `email/crypto.py`,
`calendar/crypto.py` (both with `redact_for_audit` utilities), `fh/crypto.py` (SSNs — note:
keyed off a divergent `BRIDGEABLE_ENCRYPTION_KEY`; Plaid should use
`CREDENTIAL_ENCRYPTION_KEY` to stay on the shared rotation surface). Rotation posture,
honestly: single master key, per-row FK-scoped tenant isolation, process-restart as the
rotation window, re-auth as the recovery path — documented as canon in
`email/crypto.py:1-36`. Adequate for September; a key-versioning column
(`encryption_key_version`) on `plaid_items` is a cheap forward-compat nicety, not a
blocker.

**The anti-precedent, surfaced loudly:** QBO OAuth tokens (AND the QBO client secret) are
stored **PLAINTEXT** in `Company.accounting_config` (`qbo_oauth_service.py:106-118`), while
`AccountingConnection`'s `qbo_*_token_encrypted` columns are **dead vestige** — never
written except to None. Plaid must not model on this. `plaid_items.access_token_encrypted`
is fed exclusively through `encrypt_credentials`/Fernet from birth; a unit pin asserts the
stored value is not the raw token (starts with Fernet's `gAAAA` prefix, decrypt round-trips).
The QBO plaintext liability itself is **adjacent debt for a separate session** — flagged,
not in scope here.

**NEVER-LOGGED discipline:** no central logging config exists (good — no global
body-logging middleware to fight). The rules for B-1: the access_token appears in exactly
two functions (exchange-write and decrypt-for-API-call), is never a route response field,
never in `audit_service.log_action` changes (use `redact_for_audit`), and Plaid API error
handling logs `error_code`/`request_id` only, never `resp.text` wholesale (the
`qbo_provider.py:164` pattern is the mistake to avoid — Plaid error bodies can echo
request context). A grep-able module docstring carries the discipline.

**ENV inventory (operator sets; Railway + dev .env, never the repo):**

| Var | Where | Note |
|---|---|---|
| `PLAID_CLIENT_ID` | config.py `str = ""` pattern | |
| `PLAID_SECRET` | config.py `str = ""` | sandbox secret now; production secret swaps in later |
| `PLAID_ENV` | config.py, default `"sandbox"` | `sandbox` / `production` |
| `CREDENTIAL_ENCRYPTION_KEY` | **already exists** on staging (email/calendar use it) | verify present; `Fernet.generate_key()` one-liner documented in credential_service.py |

Dependency note: `cryptography` is only transitive today (via `python-jose[cryptography]`)
— pin it explicitly in requirements.txt alongside `plaid-python`.

---

## 3. THE LINK FLOW (the connect moment)

**Server:** `POST /api/v1/plaid/link-token` (tenant-ADMIN gated) → Plaid
`link/token/create` with `products=["transactions"]`, `client_user_id=<user.id>`,
`country_codes=["US"]` → short-lived link_token to the client. `POST /api/v1/plaid/exchange`
receives the `public_token` from Link's onSuccess, exchanges server-side
(`item/public_token/exchange`), encrypts + stores the access_token, fetches
`accounts/get`, writes `plaid_items` + `plaid_accounts` rows. The access token never
touches the browser.

**Client — the stack fit is clean:** React 19.2 + Vite. The house precedent for
third-party widgets is the **npm wrapper** (Turnstile via `@marsidev/react-turnstile`, no
CDN scripts anywhere, fonts self-hosted) — **`react-plaid-link`** follows it exactly
(hooks-based `usePlaidLink`; it injects Plaid's script itself). No CSP exists in
index.html or nginx.conf, so nothing blocks `cdn.plaid.com`; noted for whenever a CSP
lands. Fallback if the wrapper fights React 19 in practice: a ~30-line script-loader hook
— Link's vanilla API is small. Not expected to be needed.

**WHERE it lives: the accounting area's "Connect your bank" SETUP CARD** — the onboarding
vision's first real setup task, spec'd as such: a card on `/bridgeable-map/Accounting`
(and the financials board) rendered when the tenant has zero active `plaid_items` —
"Connect your bank — Bridgeable pulls transactions in nightly and keeps reconciliation
fed." Tenant-admin sees the connect button; non-admins see who to ask (honest, not
hidden). **Suggestable by the rail**: a `setup_bank_connection` suggestion rule (why-line:
"Bank reconciliation runs on a live feed — connect your bank to turn it on"), dismissal
final per the rail's contract. Once connected, the card becomes the connection inventory
(institution, accounts with masks, last-synced, per-item status) with "Add another bank"
— multi-item and multi-account per tenant are first-class from B-1.

**Re-auth / update mode (the reconnect path — items degrade):** Plaid items go
`ITEM_LOGIN_REQUIRED` (password changes, MFA resets, bank-side revocation). Honest
surfacing, H1-adjacent: sync marks `plaid_items.status="login_required"`; the setup card
shows the degraded state ("Sunnycrest Bank needs re-connecting — the feed paused
Jul 14"); a `WorkflowReviewItem`-style surfacing rides the sync automation's failure
routing (§4) so it lands in Decision Triage rather than rotting silently. The reconnect
button requests a link_token **in update mode** (same endpoint, `access_token` passed) →
Link re-auths in place → status returns to `active`, cursor intact. No re-linking of
accounts, no data loss.

---

## 4. THE SYNC AUTOMATION + THE CADENCE RECOMMENDATION

### transactions/sync semantics (the ingest contract)

Per-item cursor loop: call with stored `sync_cursor` (null = full history bootstrap) →
`added[]` / `modified[]` / `removed[]` + `next_cursor` + `has_more`; page until
`has_more=false`; **persist the cursor only after the page's rows are durably committed**
(crash between = safe re-pull; idempotent by `plaid_transaction_id` upsert).
- **added** → upsert by `(tenant_id, plaid_transaction_id)`; sign-flip at the boundary;
  if `pending_transaction_id` present, stamp the link and soft-retire the pending row.
- **modified** → update in place (amounts/dates/descriptions can shift post-posting).
- **removed** → `removed_at` stamp, AND the un-match hook: if a materialized
  `ReconciliationTransaction` references it and is matched, flip it back to `unmatched`
  with a `match_note` ("bank retracted this transaction") — **a retracted transaction
  must not linger matched.** If the run containing it is already confirmed, surface a
  Decision Triage item instead of silently editing a closed statement (period-integrity
  over tidiness).

**Dry-run semantics, per the platform's philosophy:** a dry-run sync calls Plaid
read-only, computes the delta, **writes nothing**, and records the would-payload the
MoC ponder/runs strip already renders: *"would ingest 14 new transactions, update 2,
remove 1 (Sunnycrest Checking ····4321); would auto-categorize 11 of 14."* This is the
go-live confirm's evidence, exactly as the six adopted automations showed theirs.

### THE CADENCE CALL (delegated — argued from the platform's actual rhythms)

**The evidence.** The consumers of bank data run on these clocks (verbatim from
scheduler.py + the adopted MoC triggers):

| Consumer | When |
|---|---|
| Nightly accounting block (ar_aging → uncleared_check_monitor) | 23:00–23:40 ET |
| Cash Receipts Matching (adopted, moc) | daily 23:30 |
| AR Collections (adopted) | daily 23:00 |
| ar_balance_reconciliation | daily 02:00 |
| financial_health_score | daily 05:03 |
| Monthly Statement Run (adopted) | 1st, 06:00 |
| FH Billing (born native, T-2) | last day, 06:00 |
| Reconciliation itself | human-initiated, monthly-ish statement sessions |

**The argument.** Nothing here is intraday. The tightest consumer is the 23:00–23:40
nightly block; the human-facing surfaces (reconciliation sessions, the morning
financials board glance) are daily-or-slower. Real-time webhooks would buy freshness no
consumer reads — and cost a public webhook endpoint, signature verification (Plaid's
JWT/JWK verification flow), replay handling, and a liveness story for an inbound channel,
all before September. Meanwhile banks post overnight in batches: an evening-only sync
would miss same-day postings that land after it; a morning-only sync would feed the
nightly block day-old data.

**RECOMMENDATION: poll, twice daily per item, MoC-scheduled:**
- **22:30 ET** — feeds the 23:00–23:40 block and Cash Receipts Matching (23:30 — note:
  ingest at 22:30 keeps 30–60 min of headroom ahead of it) with everything the bank
  posted through end of business.
- **06:30 ET** — catches the overnight posting batch; the operator's morning glance and
  any daytime reconciliation session see yesterday complete. (After financial_health
  05:03 by design — that job reads platform records, not the bank feed, so no ordering
  dependency; 06:30 simply lands before humans do.)

Cost honesty: 2 syncs/day/item is well inside any Plaid plan; a manual "Sync now" button
on the connection card covers the demo moment and the impatient afternoon.
**Webhook upgrade path, noted:** `SYNC_UPDATES_AVAILABLE` → enqueue an immediate sync for
that item. Additive — same ingest function, a webhook route + verification in front. It
becomes worth building when a consumer becomes intraday (e.g., a future "payment arrived"
notification); nothing in September's scope is.

### The automation's shape: "Pull Bank Transactions" — BORN NATIVE

The FH Billing precedent, followed exactly (the born-native checklist from the R-1/T-2
lineage):
1. **Compiled workflow_template** — `scope='vertical_default'`, `vertical='manufacturing'`
   (cross-vertical later; Sunnycrest is the pilot), `workflow_type='pull_bank_transactions'`,
   `mirrored_from_workflow_id=NULL`, canvas `start → call_service_method
   (plaid_sync.run_sync_pipeline) → end`, registered in `_SERVICE_METHOD_REGISTRY`.
2. **Catalog row** — name "Pull Bank Transactions", task_type "Accounting",
   icon "landmark", description: *"Pulls the bank statement in and categorizes it —
   every transaction lands ready to reconcile."* (The reframe's sentence, literally.)
3. **Trigger** — MoC `schedule` triggers for 22:30 + 06:30, born `is_live=false`
   (dry-run first); promotion is a single `is_live=True` at the operator's confirm —
   no adopt needed, schedule authority is `moc` from birth.
4. **H1 routing** — automatic: a failed live run lands in `workflow_review_triage` via
   `_fail_run → route_failed_run`, deduped per workflow. Item-degradation
   (`login_required`) is surfaced through the same channel by the adapter (§3).
5. **Job ref** — `add_ref(job="Bank reconciliation", kind="automation")`. The job's
   ponder gains the beat the reframe promised: *"Pull Bank Transactions — pulls the
   statement in and categorizes it. Daily · 10:30 PM & 6:30 AM."* Credit-card months
   later ref the same automation from a "Card statement reconciliation" job if the
   operator wants the second job card — v2 call, not B-2 scope.

### Auto-categorization: Plaid categories → platform expense categories

Plaid ships `personal_finance_category` (primary + detailed, a stable ~120-value
taxonomy). The platform's vocabulary is the 15-value `EXPENSE_CATEGORIES`
(vault_materials … other_expense), with `TenantGLMapping` as the existing
category→GL-account hop.

**Where the mapping lives:** a new **`plaid_category_mappings`** table patterned on
TenantGLMapping — `plaid_category` (primary or detailed key; detailed wins over primary
at resolve time), `expense_category` (must be in the platform vocabulary),
`tenant_id` **nullable** (NULL = platform-seeded default, tenant row overrides — the
two-tier read the platform uses everywhere). Seeded sensible: ~30 rows covering the
obvious spans (`RENT_AND_UTILITIES.RENT` → rent, `TRANSPORTATION.GAS` → vehicle_expense,
`GENERAL_SERVICES.INSURANCE` → insurance, `LOAN_PAYMENTS.*` → other_expense…), authored
once in the seed, tenant-adjustable via a settings surface in B-3.

**Never silently confident:** unmapped Plaid categories → `expense_category = NULL` —
honest uncategorized, counted in the sync summary ("3 of 14 uncategorized"), visible as
a filter on the feed view, and food for the existing expense-categorization triage
muscle. No AI in the hot path for B-2 — the deterministic map covers the bulk; routing
the uncategorized residue through the existing Haiku classifier
(`agent.expense_categorization.classify`, 0.85 threshold, triage on low confidence) is
a natural B-3/v2 extension that reuses the whole Phase-8c apparatus.

---

## 5. THE RECONCILIATION WIRING + SANDBOX REALITY

### The seam's exact shape

`POST /reconciliation/runs/{id}/populate-from-feed` (new, beside upload-csv): for the
run's account (via `financial_accounts.id ← plaid_accounts.financial_account_id`) select
`bank_transactions` in `[period_start, statement_date]`, not-removed, posted-only
(pending excluded from statements by default — banks don't put pending on statements),
materialize `ReconciliationTransaction` rows (amount/dates/descriptions map 1:1;
`bank_transaction_id` back-ref), then the **unchanged** run-matching engine runs. The
run UI grows one choice: "From bank feed" (default when linked) / "Upload CSV" (the
fallback, forever — not every account will be Plaid-linked).

**Credit-card statement reconciliation:** same flow, credit-subtype account.
`statement_closing_day` (already on FinancialAccount) pre-fills the period; sign
conventions carry (card purchases arrive as Plaid-positive → platform-negative debits,
payments to the card as credits — covered by the same boundary negation + tests). The
matcher's debit pool (vendor payments) applies; card-specific matching improvements
(e.g., matching card charges to vendor bills) are v2, not wiring scope.

### The sandbox witness (all real API, zero real money)

Plaid sandbox: any test institution (e.g., First Platypus Bank), credentials
`user_good` / `pass_good`, deterministic seeded transactions; `/sandbox/*` endpoints can
force item states. The end-to-end witness script:
1. **Link** — accounting area setup card → Connect your bank → Link opens → First
   Platypus Bank → user_good/pass_good → accounts land in `plaid_accounts`; link
   checking to a FinancialAccount.
2. **Sync (dry-run)** — fire the automation's trigger dry: "would ingest N…" in the runs
   strip; DB clean.
3. **Promote at the confirm** — `is_live=True` (the T-2 choreography); fire live; feed
   rows present, cursor stored, re-fire = zero duplicates (idempotency witnessed).
4. **Categorize** — seeded map applied; the uncategorized residue honest.
5. **Reconcile** — start a run on the linked account → populate-from-feed →
   run-matching → matches against seeded platform payments (the witness seeds 2–3
   payments mirroring known sandbox transactions so auto_cleared actually fires) →
   confirm balances.
6. **Degrade + recover** — `/sandbox/item/reset_login` → next sync marks
   login_required → card shows the honest pause + triage item → update-mode Link →
   re-auth → sync resumes, cursor intact.
7. **Retract** — where sandbox permits forcing a removal, witness the un-match hook;
   otherwise pin it in tests only (the hook is unit-pinned regardless).

### The production checklist (the operator's parallel track, one sitting)

What Plaid's production application asks (Dashboard → request Production access):
- Company legal name, address, website (getbridgeable.com), and a **privacy policy URL**
  that covers bank-data handling — the one item worth pre-checking, since it may need a
  sentence added.
- Use case description (canned: "SaaS business-management platform; transactions product
  for bank/credit-card reconciliation and expense categorization on behalf of our
  business tenants"), products requested (**Transactions only** — keeps review light),
  expected volume (tens of items, low hundreds of users).
- Security posture questions (encryption at rest — truthfully yes for Plaid tokens per
  §2; access controls; incident contact).
- Billing details (pay-as-you-go; Transactions is per-connected-item).
- Timeline reality: Transactions-only applications are typically the fast lane (days,
  not weeks). When approved: swap `PLAID_SECRET` + `PLAID_ENV=production` in Railway —
  zero code changes by design.

---

## 6. THE PHASED PLAN

**B-1 — Client + models + encryption + Link (one session).** `plaid-python` + pinned
`cryptography`; config vars; r133 (`plaid_items`, `plaid_accounts`, `bank_transactions`,
`plaid_category_mappings`); the PlaidClient service wrapper (thin, error-taxonomy-aware,
never-logs-tokens docstring discipline); link-token + exchange + accounts + link-account
endpoints, tenant-admin gated, **cross-tenant 404 pins first**; encryption round-trip
pins (Fernet-prefix assertion); `react-plaid-link` + the Connect-your-bank setup card
(connect state only); manual "Sync now" (raw ingest, no automation yet) to prove the
pipe. *Exit witness: sandbox Link → accounts listed → manual sync → rows in
bank_transactions, idempotent on re-run.*

**B-2 — The governed sync automation + categorization (one session).** The sync adapter
(`plaid_sync.run_sync_pipeline`: per-item cursor loop, sign-flip, pending re-link,
removal + un-match hook, dry-run would-payload); the compiled workflow + catalog row +
22:30/06:30 triggers born dry; seeded category map + resolve; item-degradation surfacing
into Decision Triage; job-ref to Bank reconciliation (+ the ponder beat); the T-2-style
promote-at-confirm walk on dev. *Exit witness: steps 2–4 + 6 of the sandbox script.*

**B-3 — Reconciliation wiring + the setup card grown + documentation (one session).**
`populate-from-feed` + the run UI source choice; credit-card statement path witnessed;
the connection card grown to inventory + re-auth UX; the rail's setup suggestion; the
category-mapping settings surface; the full sandbox witness end-to-end; STATE.md +
ponder captions (R-3's authoring pass covers the operator's voice). *Exit witness: the
full §5 script, steps 1–7.*

Honest sizing: three real sessions. B-1 is the widest (four tables + Link + the security
pins); B-2 is the deepest (sync-loop correctness — the sign/pending/removal trio is
where Plaid integrations bleed); B-3 is the friendliest (wiring + surfaces).
**Migrations: r133 (B-1); none expected in B-2/B-3** (mapping seed rides r133's table).

---

## 7. SURFACED, PER STOP DISCIPLINE (none blocking)

1. **Encryption substrate exists** — no design arc needed. Reuse
   `CREDENTIAL_ENCRYPTION_KEY` + Fernet; do NOT inherit `fh/crypto`'s divergent key var.
2. **D-3 alignment is extension, not rework** — the feed model feeds the untouched
   matcher. The CSV path stays forever (unlinked accounts are a permanent reality).
3. **Link does not fight the stack** — npm-wrapper house pattern, no CSP in the way.
4. **Adjacent debt, flagged not scoped:** QBO tokens (and client secret) plaintext in
   `Company.accounting_config` with dead `*_encrypted` columns on AccountingConnection —
   deserves its own small hardening session; Plaid work must simply not copy it.
5. **Cadence-adjacent honesty:** the 22:30 sync's MoC trigger uses tenant-local time via
   the `scheduled`-cron path (the `time_of_day` UTC bug from the 8b.5 ledger still
   stands — don't route through it).
