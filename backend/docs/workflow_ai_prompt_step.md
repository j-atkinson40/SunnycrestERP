# Workflow Step Type: `ai_prompt`

The `ai_prompt` step invokes a managed Intelligence prompt as part of a
workflow. Variables come from step config (literals or references to
prior steps). The response is stored as the step's output and can be
referenced by downstream steps.

Added in Phase 3d. No schema migration — `intelligence_executions`
already has the `caller_workflow_run_id` / `caller_workflow_run_step_id`
columns from Phase 1.

## When to use it

- You want a workflow to extract structured data from a message, email,
  or record.
- You want a workflow to classify something (sentiment, urgency, category).
- You want a workflow to draft content (email body, summary, reply) that
  a later step sends.

## When not to use it

- If the AI call is the whole feature, not part of a multi-step process,
  call `intelligence_service.execute` directly from a route — the
  workflow engine's audit overhead isn't needed.
- If the prompt needs vision (image/document content blocks), defer —
  vision support in workflow steps is not yet implemented.

## Step config

```json
{
  "prompt_key": "scribe.extract_first_call",
  "variables": {
    "caller_name": "{input.ask_caller.value}",
    "body": "{input.ask_body.value}"
  },
  "store_output_as": "extraction"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `prompt_key` | string | ✅ | Must resolve to an active prompt visible to this tenant (platform-global or tenant-override). Validated at save time. |
| `variables` | object | ✅ (if the prompt has required vars) | Map each required variable declared in the prompt's `variable_schema`. Values can be literals or reference strings like `{input.step_key.field}` / `{output.step_key.field}` / `{current_user.id}` / `{current_record.name}`. |
| `store_output_as` | string | optional | Reserved for future nesting support. For now, the output always lands at `{output.<step_key>.<field>}`. |

### Variable references

References are resolved before the managed prompt is called, using the
same resolver other step types use. Single-reference strings return
their native type; interpolated references stringify.

## Output shape

The step's `output_data` depends on whether the managed prompt has
`force_json=true`:

- **`force_json=true` + valid JSON response:** parsed fields are spread
  at the top level of `output_data`. Downstream steps reference them as
  `{output.<step_key>.<field_name>}`.
- **Plain text response:** output is `{"text": "…"}` — referenced as
  `{output.<step_key>.text}`.

Every output also carries `_execution_id` (the persisted
`intelligence_executions.id`) and `_status`. Use `_execution_id` to
drill into the execution detail page when debugging:
`/admin/intelligence/executions/<_execution_id>`.

## Caller linkage

The executor auto-populates Intelligence linkage columns from the
workflow run context:

- `caller_module` = `workflow_engine.{workflow_id}.{step_key}`
- `company_id` = workflow run's company
- `caller_workflow_run_id` + `caller_workflow_run_step_id` — always
- `caller_entity_type` + `caller_entity_id` — from
  `trigger_context.entity_type` / `entity_id` when present
- Specialty columns routed by `entity_type`:
  - `funeral_case` / `fh_case` → `caller_fh_case_id`
  - `agent_job` → `caller_agent_job_id`
  - `ringcentral_call_log` / `call_log` → `caller_ringcentral_call_log_id`
  - `kb_document` → `caller_kb_document_id`
  - `price_list_import` → `caller_price_list_import_id`
  - `accounting_analysis_run` → `caller_accounting_analysis_run_id`
  - anything else: generic entity_type + entity_id only

This means "show me all AI calls made by this workflow run" (or "by any
run of this workflow") is a single filter on `intelligence_executions`.

## Validation at save time

When a workflow containing an `ai_prompt` step is created or updated,
the save endpoint runs `validate_ai_prompt_steps`. It fails the save
with HTTP 400 if:

1. `prompt_key` is missing or empty.
2. The prompt doesn't exist or has no active version.
3. Any variable declared `required` in the prompt's `variable_schema` is
   not mapped in step config.
4. A variable references `{output.step_key.…}` where `step_key` does
   not appear earlier in the workflow (forward reference).

Optional variables (`{"optional": true}` in the schema) may be unmapped.

## Error handling

When `intelligence_service.execute` returns `status != "success"` or
raises, the step fails with the error message. The workflow run
transitions to `"failed"` — same behavior as other action steps.

If you want to continue even when the AI call fails, wrap the
`ai_prompt` step's downstream with a condition step that branches on
the status.

## Common patterns

### Extract structured data, then create a record

```
ask_email_body (input)
 → classify_email (ai_prompt, prompt_key="email.classify")
 → create_case (action: create_record with customer_id={output.classify_email.customer_id})
```

### Draft a reply, then send

```
load_thread (action: fetch_record)
 → draft_reply (ai_prompt, prompt_key="support.draft_reply",
    variables={thread: {output.load_thread.messages}})
 → send_email (action: send_email with body={output.draft_reply.text})
```

### Classify, then branch

```
classify_urgency (ai_prompt, prompt_key="triage.classify_urgency",
  variables={text: {input.ask_body.value}})
 → is_urgent (condition: {output.classify_urgency.urgency} == "high")
    ├─ true → notify_manager (action)
    └─ false → queue_normal (action)
```

### Chain multiple prompts

```
extract_facts (ai_prompt, prompt_key="extract.from_text")
 → verify_facts (ai_prompt, prompt_key="verify.facts",
    variables={facts: {output.extract_facts.facts}})
```

Deterministic variant assignment uses `input_hash`, so the same logical
input routes consistently across replays of a workflow run.

## Observability

Every `ai_prompt` step execution produces:

1. A `WorkflowRunStep` row with `output_data` populated.
2. An `intelligence_executions` row with the full linkage chain.
3. (If an experiment is active on the prompt) an `experiment_variant` label
   on the execution row — the workflow step participates in A/B tests
   transparently.

Query `SELECT * FROM intelligence_executions WHERE caller_workflow_run_id = :run_id`
to see every AI call one workflow run made.
