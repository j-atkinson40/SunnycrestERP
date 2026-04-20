# Intelligence — User Guide

_Admin-facing guide for the Intelligence service in the Vault hub.
For the full migration context, see
[`../intelligence_audit_v3.md`](../intelligence_audit_v3.md)._

## What this service does

Intelligence is the unified AI layer for Bridgeable. Every AI call
in the platform — Scribe, accounting agents, briefings, command
bar, NL Overlay, Ask Assistant, urn pipeline, safety, CRM, KB,
onboarding, training, compose, workflows, vision — routes through
`intelligence_service.execute(prompt_key=..., variables=...,
company_id=..., caller_module=..., caller_entity_*=...)`.

Each call produces an `intelligence_executions` audit row with
prompt ID, model used, input + output token counts, cost in USD,
latency, and typed caller linkage (workflow run, agent job, case,
conversation, etc.). Every AI cost in the platform is auditable
back to exactly which feature triggered it and against exactly
which managed prompt.

**73 active platform-global managed prompts** today. Tenant-specific
forks supported but rarely used.

## Where it lives in the nav

**Vault hub sidebar → Intelligence** (`/vault/intelligence`).

Admin-only: non-admin users don't see the sidebar entry. Each
sub-tab is individually admin-gated server-side.

## Key admin surfaces

| Surface | Path | Purpose |
|---|---|---|
| **Prompt Library** | `/vault/intelligence` | All managed prompts — filter by status / category / scope / search |
| **Prompt Detail** | `/vault/intelligence/prompts/:id` | Active version body, variable schema, version history, draft editor |
| **Execution Log** | `/vault/intelligence/executions` | Every AI call with cost, tokens, caller linkage (last 7 days default) |
| **Execution Detail** | `/vault/intelligence/executions/:id` | Full prompt render, context, response, token breakdown, caller click-through |
| **Model Routes** | `/vault/intelligence/model-routes` | Routing rules (per-prompt-key model selection + fallback chain) |
| **Experiments** | `/vault/intelligence/experiments` | A/B experiment library |
| **Create Experiment** | `/vault/intelligence/experiments/new` | Wizard to split traffic between prompt variants |
| **Experiment Detail** | `/vault/intelligence/experiments/:id` | Results, split ratios, metrics |
| **Conversations** | `/vault/intelligence/conversations` | Multi-turn conversation audit (Scribe, Ask Assistant) |

## Common workflows

### Find the prompt a feature uses

1. Navigate to `/vault/intelligence`.
2. Use the search filter — the prompt_key is the discoverable
   identifier (e.g. `scribe.arrangement_summary`,
   `accounting.gl_classification`, `commandbar.intent_classify`).
3. Click the prompt to see its active version body.

Prompts follow a loose namespace convention:

- `scribe.*` — Funeral Home Arrangement Scribe
- `accounting.*` — 12 accounting agents
- `commandbar.*` — Universal Command Bar
- `briefing.*` — Morning Briefing
- `urn.*` — Wilbert catalog + urn order assistant
- `crm.*` — CRM classification + health scoring + duplicate detection
- `kb.*` — Knowledge Base parser + retrieval
- `safety.*` — Safety Program Generation + toolbox talks
- `workflow.*` — Workflow engine AI steps
- `legacy.arbitrary_prompt` — Temporary backstop for the deprecated
  `/ai/prompt` endpoint (sunset 2027-04-18)

### Edit a prompt (draft → activate)

Prompt editing uses the same draft/activate pattern as Document
templates (see
[`../how_to_customize_a_template.md`](../how_to_customize_a_template.md)):

1. Open the prompt detail page.
2. Click **"Create draft"** on the active version.
3. Edit the system prompt, user prompt template, variable schema,
   model hints (model, temperature, max_tokens), and changelog.
4. **Preview** does a client-side Jinja substitution — useful for
   syntax-checking your variable references.
5. **Test render** runs a backend render against a provided context
   dict (no actual AI call — just template rendering).
6. **Activate** requires a changelog + (for platform-global prompts)
   typing the `prompt_key` as confirmation.

Variable schema validation is strict: every `{{ variable }}` in the
template must be declared in the schema (or marked `optional: true`),
and every declared variable must be referenced. Unused or
undeclared variables block activation.

### When to fork a prompt vs. create new

**Fork** when you need a tenant-specific twist on an existing
platform prompt — e.g. Sunnycrest wants their Scribe to call the
deceased "the loved one" instead of "the decedent." Fork creates a
tenant-scoped copy. The hybrid lookup (tenant-first, platform-fallback)
routes only that tenant's calls to the forked version.

**Create new** when you're adding a new AI capability that doesn't
exist yet. Use a new unique `prompt_key` in the appropriate
namespace. Submit with `company_id=NULL` for a platform-global
prompt. Add it to the seed (`backend/app/data/seed_intelligence_prompts.py`)
so fresh deployments have it.

### Investigate an AI call

1. `/vault/intelligence/executions` — filter by prompt_key, caller
   module, company, date range.
2. Click a row to see:
   - Full rendered prompt (system + user)
   - Full response (JSON or text)
   - Token breakdown (input / output / thinking if the model
     supports it)
   - Cost in USD (auto-computed from model pricing)
   - Latency
   - Caller linkage — click any `caller_*` FK to jump to the source
     (workflow run, agent job, conversation, etc.)

**Cost surveillance.** The Execution Log is the single source of
truth for AI spend. Platform admins can filter by date range to see
rolling cost, by caller_module to see which feature is expensive,
or by prompt_key to see which prompt is expensive. No separate
billing system — the audit IS the billing.

### Run an experiment

1. `/vault/intelligence/experiments/new`.
2. Pick a **control prompt version** and a **variant prompt version**
   (typically a newer draft vs. the current active).
3. Set a **split ratio** (e.g. 80/20 control/variant).
4. Set a **success metric** — user feedback, downstream action
   completion, or a custom event key.
5. Run the experiment. Execution routing respects the split; results
   aggregate on the detail page.
6. When decided, manually activate the winning version in the
   prompt's version history.

**Experiments aren't live-traffic guardrails.** They're for
prompt-quality research. The platform doesn't auto-promote the
winner — that's an explicit admin action.

### Configure model routing

1. `/vault/intelligence/model-routes`.
2. Each route maps a `prompt_key` → primary model + fallback chain
   + timeout.
3. Default fallback (most prompts): Claude Sonnet primary, Claude
   Haiku fallback, cost caps.
4. Specific prompts with different requirements:
   - Briefings use Haiku (cost-conscious, prose-generation)
   - Accounting agents use Haiku-4.5 (COA classification threshold
     0.85 for auto-approve)
   - Scribe uses Sonnet (complex structured extraction)
   - Vision prompts use Sonnet vision variants (PDFs, check images)
5. Edit a route to change models globally or per-prompt.

## Permission model

- **Sidebar entry visible to admins only.** Non-admin users don't
  see "Intelligence" in the Vault hub sidebar.
- **All sub-routes admin-gated.** Platform-global prompt edits
  require super_admin + typed-confirmation-text gate.
- **Tenant-scoped prompt edits** (forks) are admin-only within that
  tenant — regular tenant admins can't edit platform-global prompts,
  only fork them and edit the fork.
- **Execution log is per-tenant.** Admins see their tenant's
  executions; cross-tenant visibility requires super_admin.

## Related services

- **Documents.** Intelligence-generated PDFs (Scribe output, agent
  reports, briefings) create Document rows via `document_renderer`.
  The Intelligence execution has `caller_document_id` pointing
  forward to the resulting document; the document has
  `intelligence_execution_id` pointing back.
- **Workflows (Phase 3).** Workflow engine's `ai_prompt` step type
  calls Intelligence with the step's configured `prompt_key`. The
  execution row has `caller_workflow_run_id` + `caller_workflow_step_id`
  — click the linkage to jump to the workflow run that triggered
  the AI call.
- **Delivery (D-7).** When an Intelligence execution drafts an email
  body that's then sent via `DeliveryService`, the delivery row has
  `caller_intelligence_execution_id` for reverse lookup.
- **CRM.** Health scoring, duplicate detection, and AI classification
  all route through Intelligence. The execution log is the single
  audit trail for those AI decisions.

## Known limitations

- **Execution log pagination** uses live aggregation — at current
  scale this is fine, but projected growth (tens of thousands to
  millions of executions per year) will require a materialized
  daily rollup table. Tracked in DEBT.md.
- **Cost aggregates are on-demand queries**, not cached. Same
  concern as pagination — fine today, won't scale.
- **Legacy `/ai/prompt` endpoint** still exists for backward compat,
  sunset 2027-04-18. Internally routes through the
  `legacy.arbitrary_prompt` managed prompt. Kept for any caller that
  hasn't migrated to specific managed prompts yet.
- **Experiment auto-promotion isn't built.** Admin decides the
  winner and activates manually.
- **No per-user prompt overrides.** Platform-tenant split is the
  only scoping axis; there's no "user X wants a slightly different
  prompt than user Y in the same tenant" mechanism.

See [`../DEBT.md`](../DEBT.md) for the full list of deferred items
and [`../intelligence_audit_v3.md`](../intelligence_audit_v3.md) for
the 9-sub-phase migration retrospective.
