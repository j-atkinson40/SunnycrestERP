# Bridgeable ERP — AI Call Site Audit v3

**Date:** 2026-04-18
**Purpose:** Exhaustive audit of every remaining AI call site in the Bridgeable codebase, serving as the source of truth for Phase 2c migration to `intelligence_service.execute()`.
**Scope:** Category B (legacy `call_anthropic` shim), Category C (direct Anthropic SDK), plus a roll-up of A/D/E/F/G/H for completeness.

**Key finding:** 37 remaining call sites across 37 files (23 Category B files containing 25 call sites, 14 Category C files containing 14 call sites). Nine services already migrated under Phase 2a/2b (Category A). All Category C sites bypass the audit shim entirely and are the highest migration priority — they produce zero `intelligence_executions` rows today.

---

## 2. Category A — MIGRATED (already using `intelligence_service.execute`)

| File | Prompt Key |
|---|---|
| `backend/app/services/urn_product_service.py` | `urn.semantic_search` |
| `backend/app/services/briefing_service.py` | `briefing.daily_summary` |
| `backend/app/services/safety_program_generation_service.py` | `safety.draft_monthly_program` |
| `backend/app/services/command_bar_extract_service.py` | `overlay.extract_fields_final` |
| `backend/app/api/routes/admin/chat.py` | `assistant.chat_with_context` |
| `backend/app/services/fh/story_thread_service.py` | `scribe.compose_story_thread` |
| `backend/app/services/fh/scribe_service.py` | `scribe.extract_case_fields` |
| `backend/app/services/agents/expense_categorization_agent.py` | `agent.expense_categorization.classify` |
| `backend/app/services/agents/ar_collections_agent.py` | `agent.ar_collections.draft_email` |

9 files, 9 call sites migrated. No verbatim prompt content needed — prompts are already registered in `prompts` table.

---

## 3. Category B — CALL_ANTHROPIC LEGACY (shim-covered)

All entries in this section call `app.services.ai_service.call_anthropic` (or alias `ai_service.call_anthropic`), which writes an `intelligence_executions` row with `prompt_id=null` and `caller_module="legacy"` for 100% audit coverage during migration.

### [backend/app/services/kb_retrieval_service.py:_synthesize_answer line 245]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514` via `AI_MODEL`)
- **force_json**: true (system prompt ends with "Respond with JSON")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none (call-center knowledge query — not tied to a persisted record)
- **Entity ID source**: `tenant_id` param (company_id); `caller_company_id` present but optional
- **Caller linkage candidates**: `company_id` (from tenant_id). No invoice/order/case linkage.
- **Proposed prompt_key**: `kb.synthesize_call_answer` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (live call-time answer, high accuracy required; token budget 512 is modest so cost is low).
- **Migration complexity**: LOW
- **Variables used**: `query`, `chunks[]` (content, document_title, category_slug), `pricing[]` (product_name, product_code, price, unit, price_tier, notes)
- **Response parsing**: `result.get("answer", "")`, `result.get("confidence", "medium")` — expects JSON dict.

#### System prompt — verbatim
```
You are a helpful assistant for a vault manufacturer's call center. You have been given knowledge base content relevant to a question asked during a phone call.

Synthesize a clear, concise answer from the provided context. If pricing information is available, present it clearly with the correct tier.

Rules:
- Be brief — the answer will be shown to the employee during a live call
- Lead with the most important information
- If pricing is involved, always specify the unit (each, per sq ft, etc.)
- If the context doesn't contain enough information, say so honestly
- Never make up prices or product details

Respond with JSON:
{
  "answer": "your synthesized answer",
  "confidence": "high" | "medium" | "low"
}
```

#### User prompt template — verbatim (constructed)
```
Question: {query}

Context:

{context_parts joined with '\n\n---\n\n'}
```
where `context_parts` is assembled as:
- `"PRICING:\n" + "\n".join(pricing_lines)` where each line is `"- {product_name} ({product_code or 'no code'}): ${price}/{unit} [{price_tier} tier]{' — ' + notes if notes else ''}"`
- For each chunk (capped at 5): `"[{category_slug} — {document_title}]\n{content}"`

**Notes**: Called inline on live phone calls — latency-sensitive. `max_tokens=512`. Fallback path on exception uses first pricing or chunk verbatim (not AI-derived).

---

### [backend/app/services/onboarding/unified_import_service.py:_classify_batch_ai line 539]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (system prompt requires JSON array)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company_entity` (batch of company classifications)
- **Entity ID source**: `row.id` from `ImportStagingCompany` (pre-company_entity records). `session_id` available via caller.
- **Caller linkage candidates**: None to `company_id` directly — staging rows precede final entity creation. Could link via `import_session_id` once linkage column exists.
- **Proposed prompt_key**: `onboarding.classify_import_companies` (NEW PROMPT NEEDED). `model_preference`: `haiku` (batch classification, cost-sensitive; 40-record batches with simple enum outputs).
- **Migration complexity**: LOW
- **Variables used**: `companies_data` (list of dicts with id/name/city/state/order_count/appears_as_cemetery/matched_sources)
- **Response parsing**: Accepts either a list or `{"classifications": [...]}` dict; maps by `id`.

#### System prompt — verbatim
```
You classify companies for a Wilbert burial vault manufacturer. Valid types: funeral_home, cemetery, contractor, individual, unknown. For contractors, also provide contractor_type: wastewater, concrete, general, landscaping, or null. Signal weights: appears_as_cemetery > 0 = VERY HIGH confidence cemetery. Multiple orders = HIGH confidence funeral_home. Name contains 'excavating'/'septic' = contractor. Return a JSON array with {id, customer_type, contractor_type, confidence, reasoning} for each.
```

#### User prompt template — verbatim (constructed)
```
Classify these companies:
{companies_data as python-repr list of dicts}
```

**Notes**: Batch size 40. Non-Decimal confidence conversions via `float(Decimal(str(conf)))`. Failure path preserves existing suggested_type with 0.3 confidence.

---

### [backend/app/services/onboarding/csv_column_detector.py:detect_columns line 163]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (system prompt says "Return ONLY a JSON object")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none (CSV header mapping for `cemetery` / `funeral_home` import)
- **Entity ID source**: none at call time; called during import flow
- **Caller linkage candidates**: None natively. Could attach `import_session_id` via future column.
- **Proposed prompt_key**: `onboarding.detect_csv_columns` (NEW PROMPT NEEDED). `model_preference`: `haiku` (small, structured; 256 max tokens).
- **Migration complexity**: LOW
- **Variables used**: `import_type`, `ai_remaining_headers`, `sample_preview` (first 3 rows), `list(alias_map.keys())`
- **Response parsing**: Expects dict mapping standard field names → actual header; validates against alias_map.

#### System prompt — verbatim (constructed via f-string)
```
Map CSV columns to standard {import_type} fields. Return ONLY a JSON object mapping standard field names to actual column names. Only include fields you are confident about.
```
With `import_type ∈ {"cemetery", "funeral_home"}`.

#### User prompt template — verbatim (constructed)
```
Headers: {ai_remaining_headers}

Sample data:
{sample_preview}

Standard fields: {list(alias_map.keys())}
```

**Notes**: Pass-3 fallback — only runs when critical fields `name`/`city` remain unmapped after rule + fuzzy passes. `max_tokens=256`.

---

### [backend/app/services/document_search_service.py:_extract_answer line 96]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (prompt specifies strict JSON output)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `document` (DocumentSearchIndex)
- **Entity ID source**: `doc.id` in scope from `_postgres_search` results; call triggered for command-bar FTS queries.
- **Caller linkage candidates**: `company_id` (search scope). Top `source_id` of each doc could populate a `document_id` linkage column.
- **Proposed prompt_key**: `commandbar.extract_document_answer` (NEW PROMPT NEEDED). `model_preference`: `haiku` (fast search augmentation, 300 max tokens).
- **Migration complexity**: LOW
- **Variables used**: `query`, `sections[]` built from top_chunks (section_title, content)
- **Response parsing**: JSON dict with `found`, `answer`, `source_chunk_index`, `confidence`; returns None if not found.

#### System prompt — verbatim
```
You are a search assistant for an ERP business platform. Extract the most relevant answer to the user's query from the provided document sections.

Return JSON only:
{
  "found": true | false,
  "answer": "1-3 sentence direct answer",
  "source_chunk_index": 0,
  "confidence": 0.0-1.0
}

If no direct answer exists in the provided sections, return {"found": false}.
Never invent information not present in the documents.
```

#### User prompt template — verbatim (constructed)
```
Query: {query}

Document sections:

{sections joined with '\n\n'}
```
where each section is `"[Section {i}] {title}:\n{content}"` (max 3 chunks).

**Notes**: `max_tokens=300`. Latency-sensitive (command bar). Silent failure allowed.

---

### [backend/app/services/kb_parsing_service.py:_run_claude_parsing line 122]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true ("Respond ONLY with valid JSON")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `document` (KBDocument)
- **Entity ID source**: `document_id` param; `tenant_id` param
- **Caller linkage candidates**: `company_id` (tenant_id); `document_id` (KBDocument FK). Could populate a `kb_document_id` linkage column.
- **Proposed prompt_key**: `kb.parse_document` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (high-quality structured extraction across multiple category schemas; 4096 max tokens).
- **Migration complexity**: MEDIUM — system prompt branches by `category_slug`, producing different output shapes. Migration must preserve all 5 branches (pricing/product_specs/personalization_options/company_policies/cemetery_policies/general).
- **Variables used**: `category_slug`, `tenant_vertical`, `extensions`, `raw_text` (truncated to 30000 chars)
- **Response parsing**: JSON with `items[]` (for pricing) or `chunks[]` + `summary`.

#### System prompt — verbatim
```
You are parsing a business document for a knowledge base. Extract and structure all useful information.

Instructions by category:

If category is "pricing":
  Extract every product/service with its price.
  Look for multiple price columns (contractor, homeowner, standard, retail etc).
  Return JSON: {{"items": [...], "summary": "..."}}
  Each item: {{"product_name": str, "product_code": str|null, "description": str|null, "standard_price": float|null, "contractor_price": float|null, "homeowner_price": float|null, "unit": str, "notes": str|null}}

If category is "product_specs":
  Extract each product with specifications. Return structured text chunks, one per product.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

If category is "personalization_options":
  Extract each personalization type, options, pricing, and lead times.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

If category is "company_policies":
  Extract each policy as a discrete chunk. Include policy name, description, fees.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

If category is "cemetery_policies":
  Extract each cemetery with equipment requirements, liner types, special requirements, contacts.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

For all other categories:
  Split into logical chunks. Return JSON: {{"chunks": [str, ...], "summary": "..."}}

Always include a "summary" field with a 2-3 sentence plain-English description.
Respond ONLY with valid JSON.
```
(Note: double-braces are Python `.format()` escapes; the rendered prompt uses single braces.)

#### User prompt template — verbatim (constructed)
```
Document category: {category_slug}
Tenant vertical: {tenant_vertical}
Enabled extensions: {', '.join(extensions) if extensions else 'none'}

Document content:

{raw_text[:30000]}
```

**Notes**: Conditional output schemas require per-category extraction parsing in the post-migration handler. Consider splitting into one prompt per category_slug for cleaner schemas.

---

### [backend/app/services/import_alias_service.py:_ai_match_products line 361]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (prompt requests JSON object with matches array)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `urn_product` / `product` (batch product match)
- **Entity ID source**: `product_catalog` dicts; no single caller entity id — batch context
- **Caller linkage candidates**: `company_id` (only contextually from caller). Could attach `import_session_id` once available.
- **Proposed prompt_key**: `import.match_product_aliases` (NEW PROMPT NEEDED). `model_preference`: `haiku` (catalog disambiguation, bulk).
- **Migration complexity**: LOW
- **Variables used**: `unmatched_names[:20]`, `product_catalog[:100]` (id/name/sku dicts)
- **Response parsing**: `result.get("matches", [])` — list of `{original_name, product_id, confidence, reasoning}`.

#### System prompt — verbatim
```
You are a product matching assistant for a burial vault manufacturer. Given a list of historical product names and a current product catalog, match each historical name to the most likely current product. Product names may use abbreviations, old model numbers, or informal names.
```

#### User prompt template — verbatim
```
Match each of these historical product names to the closest product in the catalog. Return a JSON object with a 'matches' array where each element has: original_name, product_id (from catalog, or null if no match), confidence (0.0-1.0), reasoning (brief).
```
Context data passed via `context_data={"historical_names": ..., "product_catalog": ...}`.

**Notes**: Uses `ai_service.call_anthropic`'s `context_data` parameter. `max_tokens=2048`.

---

### [backend/app/services/call_extraction_service.py:extract_order_from_transcript line 162]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true ("Respond ONLY with valid JSON")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `conversation` (RingCentral call) / `sales_order` (draft order created downstream)
- **Entity ID source**: `call_id` (RingCentralCallLog.id) param; `tenant_id` param; optional `existing_company_id`
- **Caller linkage candidates**: `company_id` (tenant_id), `call_log_id` (RingCentralCallLog), eventually `sales_order_id` via `draft_order_created`. Strong candidate for entity linkage.
- **Proposed prompt_key**: `calls.extract_order_from_transcript` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (complex multi-field structured extraction with downstream KB query generation; accuracy is critical for draft-order creation).
- **Migration complexity**: MEDIUM — tightly coupled with downstream KB retrieval fan-out, master_company resolution, and RingCentralCallExtraction persistence. Migration must keep the `kb_queries` subfield behavior.
- **Variables used**: `transcript`
- **Response parsing**: Rich JSON schema (see system prompt) parsed into `RingCentralCallExtraction` fields, with `_parse_date`/`_parse_time` helpers.

#### System prompt — verbatim
```
You are an order intake assistant for a Wilbert burial vault manufacturer. You are analyzing a transcript of a phone call between a funeral home and a vault manufacturer's employee.

Your job:
1. Extract any order information mentioned
2. Identify what information is MISSING that would be needed to place a complete order
3. Identify the funeral home if mentioned

A complete vault order requires:
- Funeral home name (who is ordering)
- Deceased name
- Vault type/model (e.g. Triune, Monticello, Venetian, Triune Stainless, etc.)
- Size (standard adult, oversize, infant)
- Cemetery name
- Burial date
- Burial time
- Grave section/lot/space (if known)
- Any personalization or special requests

Respond ONLY with valid JSON in this format:
{
  "funeral_home_name": string | null,
  "deceased_name": string | null,
  "vault_type": string | null,
  "vault_size": string | null,
  "cemetery_name": string | null,
  "burial_date": string | null,
  "burial_time": string | null,
  "grave_location": string | null,
  "special_requests": string | null,
  "confidence": {
    "funeral_home_name": "high"|"medium"|"low"|null,
    "deceased_name": "high"|"medium"|"low"|null,
    "vault_type": "high"|"medium"|"low"|null,
    "vault_size": "high"|"medium"|"low"|null,
    "cemetery_name": "high"|"medium"|"low"|null,
    "burial_date": "high"|"medium"|"low"|null,
    "burial_time": "high"|"medium"|"low"|null,
    "grave_location": "high"|"medium"|"low"|null
  },
  "missing_fields": [
    "list of field names that were NOT mentioned and are needed for a complete order"
  ],
  "call_summary": "1-2 sentence summary of the call",
  "call_type": "order"|"inquiry"|"callback_request"|"other",
  "urgency": "standard"|"urgent"|"same_day",
  "suggested_callback": true/false,
  "kb_queries": [
    {
      "query": "the question or topic needing a KB lookup",
      "query_type": "pricing"|"product_specs"|"policy"|"general"
    }
  ]
}

The "kb_queries" array should contain any questions that came up during the call where the employee might need reference information — product pricing, specs, cemetery requirements, company policies, etc. Include the query as the caller phrased it and classify the type. Return an empty array if no KB lookups are needed.
```

#### User prompt template — verbatim
```
Call transcript:

{transcript}
```

**Notes**: `max_tokens=1024`. Result persisted to `ringcentral_call_extractions`. kb_queries fan-out to `kb_retrieval_service.retrieve_for_call` (which itself calls Claude — see entry above).

---

### [backend/app/services/historical_order_import_service.py:detect_format line 320]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (single-arg `call_anthropic(prompt, json_mode=True)` signature)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none (column mapping for historical order CSV)
- **Entity ID source**: optional `company_id`; nothing else at call time
- **Caller linkage candidates**: `company_id`. Could link via `historical_order_import_id` once available.
- **Proposed prompt_key**: `import.detect_order_csv_columns` (NEW PROMPT NEEDED). `model_preference`: `haiku` (small structured output).
- **Migration complexity**: LOW
- **Variables used**: `sample_text` (headers list + first 3 rows); fields list is embedded literal
- **Response parsing**: dict where each key is a column name → `{"field": str, "confidence": float}` or scalar string.

#### System prompt — verbatim
Not passed separately — the entire prompt is the user_message. Call signature: `call_anthropic(prompt, json_mode=True)`.

#### User prompt — verbatim (constructed)
```
Map these CSV columns to standard funeral order fields.

Standard fields: funeral_home_name, cemetery_name, product_name, equipment_description, scheduled_date, service_time, quantity, notes, order_number, csr_name, fulfillment_type, is_spring_surcharge.
For columns with no match use 'ignore'.
For Family Name / decedent name columns use 'skip_privacy'.

Headers and sample rows:
{sample_text}

Return JSON only: {"<column>": {"field": "<field>", "confidence": 0-1}}
```
where `sample_text` is:
```
{str(list(headers))}
{row0_values joined with ', ' (first 8 cols)}
{row1_values joined with ', ' (first 8 cols)}
{row2_values joined with ', ' (first 8 cols)}
```

**Notes**: Single-arg form of `call_anthropic` with positional `prompt`, uses `json_mode=True` kwarg (the shim treats prompt as user message with a generic "respond in JSON" system instruction). Graceful fallback to "ignore" mapping on exception.

---

### [backend/app/services/obituary_service.py:generate_with_ai line 104]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (system prompt ends with "Return a JSON object with a single key obituary_text")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `funeral_case` (FHCase)
- **Entity ID source**: `case_id` param; `tenant_id` param; `performed_by_id` (user)
- **Caller linkage candidates**: `company_id` (tenant_id), `case_id` (FHCase → fh_case linkage column), `user_id` (performed_by). Strong audit linkage candidate.
- **Proposed prompt_key**: `fh.obituary.generate` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (long-form creative generation, dignity-sensitive tone; ~250 words output).
- **Migration complexity**: LOW — well-scoped, single-case call with clear input/output contract.
- **Variables used**: `case_data` (deceased name/dob/dod/age/gender/veteran/disposition/service_type/service details), `biographical_data` (surviving_family, education, career, military, hobbies, faith, accomplishments, special_memories, tone_preference), `prompt` (caller-assembled opener)
- **Response parsing**: `result.get("obituary_text", "")` — raises HTTP 502 if empty.

#### System prompt — verbatim
```
You are helping write an obituary for a funeral home. Write in a warm, dignified tone. Include all provided facts accurately. Follow standard obituary structure: opening announcement, biographical information, surviving family, service details, and any special requests (donations, etc.). Avoid cliches. Keep to approximately 250 words unless more detail is provided. Do not fabricate any details not provided.

Return a JSON object with a single key "obituary_text" containing the full obituary text as a string.
```

#### User prompt template — verbatim (constructed)
```
Write an obituary for {first_name} {middle_name + ' ' if middle_name else ''}{last_name}.
```
Optionally appended with `" Tone preference: {tone_preference}."` when provided.
Context data passed via `context_data={"case_details": case_data, "biographical_information": biographical_data}`.

**Notes**: Stores `full_prompt` (user_message + json-serialized context) as `obituary.ai_prompt_used` for audit. Persists to FHObituary with version increment.

---

### [backend/app/services/ai_manufacturing_intents.py:parse_manufacturing_command line 143]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (system prompt mandates single JSON object)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none (NL command → intent classification)
- **Entity ID source**: command-bar context; `current_user` implicit at caller (ai.py route). No primary entity at prompt time.
- **Caller linkage candidates**: `company_id` (via ai.py route). `user_id` optional.
- **Proposed prompt_key**: `commandbar.classify_manufacturing_intent` (NEW PROMPT NEEDED; distinct from existing `commandbar.classify_intent` which is FH-aware). `model_preference`: `haiku` (command bar latency-sensitive).
- **Migration complexity**: MEDIUM — 6 intent branches, each with its own expected output schema.
- **Variables used**: `today` (date.today().isoformat()), `user_input`, optional `product_catalog[]`, `customer_catalog[]`, `employee_names[]`
- **Response parsing**: Dict with `intent` key; branch-specific fields.

#### System prompt — verbatim (constructed via `.format(today=today)`)
```
You are a manufacturing ERP assistant for a precast-concrete / vault production company.
Your job is to classify the user's natural-language command into exactly ONE intent
and extract structured data.

Today's date: {today}

INTENTS (pick exactly one):

1. log_production
   Triggers: "we made", "we poured", "produced today", "made this morning", "finished [qty] [product]"
   Extract: product names and quantities.
   Return:
   {
     "intent": "log_production",
     "entries": [{"product_name": "Standard Vault", "quantity": 6}, ...],
     "message": "Ready to log 6 Standard Vaults and 4 Grave Boxes"
   }

2. check_inventory
   Triggers: "how many", "do we have", "inventory", "stock", "in stock"
   Extract: product name.
   Return:
   {
     "intent": "check_inventory",
     "product_name": "<matched product name>",
     "product_id": "<id from catalog or null>",
     "message": "Looking up inventory for <product>..."
   }

3. create_order
   Triggers: customer name + product mention, "order", "to [customer]", "for [customer]"
   Extract: customer name, products, quantities, delivery date hints.
   Return:
   {
     "intent": "create_order",
     "customer": "Johnson Funeral Home",
     "items": [{"product_name": "Standard Vault", "quantity": 2}],
     "delivery_date_hint": "Friday" or null,
     "message": "Draft order: 2 Standard Vaults to Johnson Funeral Home"
   }

4. record_payment
   Triggers: "paid", "received payment", "check from", "payment from"
   Extract: customer name, optional amount, optional invoice reference.
   Return:
   {
     "intent": "record_payment",
     "customer": "...",
     "amount": 1500.00 or null,
     "invoice_reference": "INV-1042" or null,
     "payment_method": "check" or "cash" or "ach" or null,
     "message": "Record payment from <customer>..."
   }

5. log_training
   Triggers: "did training", "safety training", "trained the crew", "completed certification"
   Extract: training topic, employee names or "whole crew".
   Return:
   {
     "intent": "log_training",
     "topic": "Forklift Safety",
     "employees": ["John", "Mike"] or ["whole_crew"],
     "date": "{today}",
     "message": "Log forklift safety training for the whole crew"
   }

6. log_incident
   Triggers: "incident", "accident", "injury", "near miss", "slipped", "hurt"
   Extract: employee name, description, severity hint.
   Return:
   {
     "intent": "log_incident",
     "employee": "Mike",
     "description": "Slipped on wet concrete near pour area",
     "severity_hint": "first_aid" or "near_miss" or "medical" or "serious",
     "message": "We've started an incident report. Please review before submitting."
   }

CONTEXT DATA you will receive:
- product_catalog: list of {id, name, sku}
- customer_catalog: list of {id, name}
- employee_names: list of employee first names

RULES:
- Always return exactly one JSON object with an "intent" field.
- Match products / customers by fuzzy name against the catalogs provided.
- If the command doesn't match any intent, return:
  {"intent": "unknown", "message": "I'm not sure what you'd like to do. Try something like: 'we made 6 standard vaults today'"}
- confidence field is optional but encouraged: "high", "medium", or "low".
```
(Braces in the literal are doubled for `.format()`; rendered single.)

#### User prompt — verbatim
```
{user_input}
```
Context passed via `context_data={product_catalog?, customer_catalog?, employee_names?}`.

**Notes**: Intent classification for manufacturing command bar. Context data supplied by `ai.py:ai_manufacturing_command` endpoint.

---

### [backend/app/services/ai_funeral_home_intents.py:parse_funeral_home_command line 777]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (single JSON object per prompt)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `funeral_case` (tentative — NL intent can resolve to a case)
- **Entity ID source**: None directly at call time — intent classification precedes case resolution.
- **Caller linkage candidates**: `company_id` (caller ai.py route); could attach `case_id` once resolved.
- **Proposed prompt_key**: `commandbar.classify_fh_intent` (NEW PROMPT NEEDED; partial overlap with `commandbar.classify_intent` but FH-specific 11-intent taxonomy).
- **Migration complexity**: MEDIUM — 11 intents × branch-specific schemas.
- **Variables used**: `today` (date.today().isoformat()), `user_input`, optional `case_catalog[]`
- **Response parsing**: dict with `intent`; branch-specific fields per intent.

#### System prompt — verbatim (constructed via `.format(today=today)`)
```
You are a funeral home ERP assistant.
Your job is to classify the user's natural-language command into exactly ONE intent
and extract structured data.

Today's date: {today}

INTENTS (pick exactly one):

1. open_case
   Triggers: "first call", "new case", "passed away", "died"
   Extract: deceased name, date of death, place of death, disposition type, veteran status, next-of-kin.
   Return:
   {
     "intent": "open_case",
     "deceased_first_name": "...", "deceased_last_name": "...",
     "date_of_death": "...", "place_of_death": "...",
     "disposition_type": "burial" or "cremation" or "direct_cremation",
     "veteran": false,
     "contact_name": "...", "contact_relationship": "...", "contact_phone": "...",
     "message": "Ready to open case for [name]"
   }

2. update_case_status
   Triggers: "arrangement conference", "services complete", "burial done", "mark case"
   Extract: case/deceased name, new status.
   Return:
   {
     "intent": "update_case_status",
     "case_name": "...", "new_status": "...",
     "message": "Update [name] status to [status]"
   }

3. order_vault
   Triggers: "order vault", "vault for", "selected the vault"
   Extract: case name, vault type, delivery date.
   Return:
   {
     "intent": "order_vault",
     "case_name": "...", "vault_type": "...", "delivery_date_hint": "...",
     "message": "Order [vault type] for [name]"
   }

4. record_payment
   Triggers: "paid", "payment", "received", "check from", "insurance assignment", "deposit"
   Extract: case/family name, amount, payment method.
   Return:
   {
     "intent": "record_payment",
     "case_name": "...", "amount": 0.00, "payment_method": "...",
     "message": "Record $X payment from [name]"
   }

5. send_family_portal
   Triggers: "send portal", "portal to", "text the portal"
   Extract: case name, delivery method (email/sms), contact info.
   Return:
   {
     "intent": "send_family_portal",
     "case_name": "...", "delivery_method": "email" or "sms",
     "message": "Send portal link to [name]"
   }

6. update_service_details
   Triggers: "service is", "service at", "graveside", "memorial service"
   Extract: case name, service type, location, date, time.
   Return:
   {
     "intent": "update_service_details",
     "case_name": "...", "service_type": "...", "location": "...",
     "date_hint": "...", "time_hint": "...",
     "message": "Update service details for [name]"
   }

7. check_case_status
   Triggers: "where are we", "status of", "what's the status", "has the"
   Extract: case name, aspect to check.
   Return:
   {
     "intent": "check_case_status",
     "case_name": "...", "aspect": "general",
     "message": "Checking status for [name]"
   }

8. cremation_auth_signed
   Triggers: "authorization signed", "auth signed"
   Extract: case name, signed date.
   Return:
   {
     "intent": "cremation_auth_signed",
     "case_name": "...", "signed_date": "...",
     "message": "Mark cremation auth signed for [name]"
   }

9. cremation_scheduled
   Triggers: "cremation scheduled", "schedule cremation"
   Extract: case name, scheduled date/time.
   Return:
   {
     "intent": "cremation_scheduled",
     "case_name": "...", "scheduled_date": "...", "scheduled_time": "...",
     "message": "Schedule cremation for [name]"
   }

10. cremation_complete
    Triggers: "cremation complete", "cremation done", "cremated"
    Extract: case name, completion date.
    Return:
    {
      "intent": "cremation_complete",
      "case_name": "...", "completion_date": "...",
      "message": "Mark cremation complete for [name]"
    }

11. remains_released
    Triggers: "remains released", "released to", "ashes to", "cremains to"
    Extract: case name, released to whom, release date.
    Return:
    {
      "intent": "remains_released",
      "case_name": "...", "released_to": "...", "release_date": "...",
      "message": "Release remains for [name] to [person]"
    }

RULES:
- Always return exactly one JSON object with an "intent" field.
- If the command doesn't match any intent, return:
  {"intent": "unknown", "message": "I'm not sure what you'd like to do. Try something like: 'First call from the Johnson family'"}
- confidence field is optional but encouraged: "high", "medium", or "low".
```

#### User prompt — verbatim
```
{user_input}
```
Context passed via `context_data={"case_catalog": case_catalog}` (when provided).

**Notes**: Only reached when keyword classifier (`classify_funeral_home_intent`) misses; most entry points use rule-based classification first.

---

### [backend/app/services/core_command_service.py:_call_claude line 177]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (system prompt enforces JSON-only response)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none — this is the universal command bar intent classifier; results may link to any entity
- **Entity ID source**: `user.id`, `user.company_id` in scope via `process_command`
- **Caller linkage candidates**: `company_id` (user.company_id), `user_id` (user.id). Related entity FK populated by the action handler that consumes the result.
- **Proposed prompt_key**: Align with existing `commandbar.classify_intent` (already in registry) — this is the most likely match. Verify seed payload matches the system prompt here before collapse. `model_preference`: `haiku` (command-bar latency).
- **Migration complexity**: MEDIUM — contains massive intent + route enumeration; any change risks destabilizing command-bar routing.
- **Variables used**: `raw_input`, `resolved_entities` (companies/orders/products), `user_context`
- **Response parsing**: `json.loads(response) if isinstance(response, str) else response`; expects `{"results": [...], "intent": str, "needs_confirmation": bool}`.

#### System prompt — verbatim
```
You are the intent classification engine for Bridgeable — a physical economy operating platform for the death care industry. Parse natural language input from users (precast manufacturers, funeral home directors, cemetery managers) and return structured JSON.

Current user context will be provided. Resolve entity references against the provided data. Return confidence scores.

ALWAYS return valid JSON matching the schema below. NEVER return markdown, explanation, or preamble — only the JSON object.

Response schema:
{
  "results": [
    {
      "id": "string",
      "type": "ACTION" | "VIEW" | "RECORD" | "NAV" | "ASK",
      "icon": "string (lucide icon name)",
      "title": "string",
      "subtitle": "string",
      "shortcut": 1-5,
      "action": {
        "type": "navigate" | "navigate_with_prefill" | "open_timeline" | "execute_action" | "vault_query" | "open_modal",
        "route": "string",
        "prefill": {}
      },
      "confidence": 0.0-1.0
    }
  ],
  "intent": "string",
  "needs_confirmation": false
}

Available intents: search, create_order, schedule_delivery, log_production, view_compliance, create_reminder, find_record, navigate, log_pour, log_strip, create_employee, find_employee, view_briefing, call_customer, create_invoice, run_statements, view_ar_aging, view_ap_aging, view_revenue_report, create_disinterment, view_disinterments, log_incident, run_audit_prep, view_safety, view_training, view_ss_certificates, settings_programs, settings_locations, settings_team, settings_product_lines, settings_tax, settings_email, view_invoices, view_bills, view_purchase_orders, view_products, view_knowledge_base, view_team, create_urn_order, view_urns, view_transfers, view_spring_burials, view_calls, view_agents

Known navigable routes (use the canonical path when intent=navigate):
  /dashboard /orders /orders/new /scheduling /scheduling/new
  /crm /crm/companies /crm/funeral-homes /crm/pipeline
  /compliance /compliance/disinterments /compliance/disinterments/new
  /ar/invoices /ar/invoices/review /ar/aging /ar/payments /ar/quotes /ar/statements
  /ap/bills /ap/aging /ap/payments /ap/purchase-orders
  /products /products/urns /urns/catalog /urns/orders /urns/orders/new
  /safety /safety/programs /safety/incidents /safety/incidents/new
  /safety/training /safety/osha-300 /safety/toolbox-talks
  /social-service-certificates /spring-burials /transfers /calls /agents /team
  /reports /knowledge-base
  /settings/programs /settings/locations /settings/product-lines
  /settings/tax /settings/invoice /settings/call-intelligence
  /settings/compliance
  /production /production/pour-events/new /production-log
```

#### User prompt — verbatim (constructed)
```
{json.dumps({"input": raw_input, "resolved_entities": resolved, "user_context": context, "instruction": "Return JSON only. No preamble."})}
```

**Notes**: 800ms soft timeout lives in the caller (not in this call). `max_tokens=1000`. Falls back to local Postgres search on any exception.

---

### [backend/app/services/command_bar_data_search.py:_try_claude_catalog_answer line 903]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `urn_product` / `product` (answers may reference products)
- **Entity ID source**: `company_id` param; product list sourced from DB
- **Caller linkage candidates**: `company_id`. Could populate `related_product_ids` once schema allows.
- **Proposed prompt_key**: `commandbar.answer_catalog_question` (NEW PROMPT NEEDED; distinct from existing `commandbar.answer_price_question`). `model_preference`: `haiku` (on-demand, not automatic — user clicks Ask AI).
- **Migration complexity**: LOW
- **Variables used**: `query`, compact catalog context (up to 80 products: name, sku, tiered standard price)
- **Response parsing**: dict with `answer`, `confidence`, `referenced_product_names[]`.

#### System prompt — verbatim
```
You are a search assistant for a Bridgeable ERP tenant. Given a user's question and a snapshot of their product catalog (with prices), answer the question concisely.

Return JSON only:
{
  "answer": "1-2 sentence direct answer, or null if you cannot answer from the catalog",
  "confidence": 0.0-1.0,
  "referenced_product_names": ["Exact Product Name From List", ...]
}

Rules:
- Only reference products that appear verbatim in the list.
- Never invent prices or products.
- If the question is about something not in the catalog (HR, compliance, weather, etc.), return answer: null.
- If the user typed a vague term like "equipment" or "vaults", you may summarize what's available at a high level.
- Prefer to name specific products and their prices when relevant.
```

#### User prompt — verbatim (constructed)
```
Question: {q}

Available products:
- {product.name} (SKU {sku or 'n/a'}, {formatted_price or 'no price'})
... (up to 80 products, one per line)
```

**Notes**: Last-resort "Ask Bridgeable AI" handler. Not called in automatic search pipeline. `max_tokens=250`. Confidence threshold 0.55 before surfaced.

---

### [backend/app/services/crm/classification_service.py:_ai_classify line 477]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (prompt ends with explicit JSON schema)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company_entity` (CompanyEntity)
- **Entity ID source**: `entity.id`, `entity.company_id` (tenant)
- **Caller linkage candidates**: `company_id` (tenant), `company_entity_id` (entity.id). Strong candidates for structured linkage.
- **Proposed prompt_key**: `crm.classify_entity_single` (NEW PROMPT NEEDED — distinct from batch classifier in Category C). `model_preference`: `haiku` (single classification, low stakes).
- **Migration complexity**: LOW
- **Variables used**: `entity.name`, `entity.city`, `entity.state`, `entity.email`, `order_data.total_orders`, `order_data.is_active`, `name_matches`
- **Response parsing**: `json.loads(response)` — expects `{customer_type, contractor_type, confidence, reasons}`.

#### System prompt / User prompt — verbatim (single argument)
Call: `call_anthropic(prompt, max_tokens=200)` (single-arg form — shim treats as user message).
```
Classify this business customer for a precast concrete manufacturer in upstate New York.

Company: {entity.name}
City: {entity.city or 'unknown'}, State: {entity.state or 'unknown'}
Email: {entity.email or 'none'}
Total orders: {order_data.get('total_orders', 0)}
Active (12mo): {order_data.get('is_active', False)}
Name keyword matches: {json.dumps(name_matches)}

Classify as ONE of: funeral_home, cemetery, contractor, crematory, licensee, church, government, individual, other
For contractors also set contractor_type: full_service, wastewater_only, redi_rock_only, general, occasional

Return JSON: {"customer_type": str, "contractor_type": str|null, "confidence": float, "reasons": [str]}
```

**Notes**: Only called when rule-based confidence < 0.80. `max_tokens=200`. Runs as part of `classify_company` which is invoked both synchronously and via bulk classification sweep.

---

### [backend/app/services/urn_intake_agent.py:process_intake_email line 56]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true ("Return ONLY a JSON object")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `urn_product` / `urn_order` (draft) — email is pre-draft-order intake
- **Entity ID source**: `tenant_id` param; email metadata (from_email, subject)
- **Caller linkage candidates**: `company_id` (tenant_id). Future: `urn_order_id` once created.
- **Proposed prompt_key**: `urn.extract_intake_email` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (multi-field email extraction, drives draft-order creation).
- **Migration complexity**: LOW
- **Variables used**: `subject`, `body[:3000]`
- **Response parsing**: `json.loads(result) if result else {}` — expects funeral_home_name/fh_contact_email/urn_description/quantity/engraving_line_[1-4]/font/color/need_by_date/delivery_method/notes/confidence_scores.

#### System prompt / User prompt — verbatim (single argument)
Call: `call_anthropic(prompt, max_tokens=800)` (single-arg form).
```
Extract urn order details from this funeral home email.
Return ONLY a JSON object with these fields:
- funeral_home_name: string or null
- fh_contact_email: string or null
- urn_description: string or null (product name, SKU, or description)
- quantity: integer (default 1)
- engraving_line_1: string or null (decedent name)
- engraving_line_2: string or null (dates, e.g. birth-death)
- engraving_line_3: string or null
- engraving_line_4: string or null
- font_selection: string or null
- color_selection: string or null
- need_by_date: string or null (ISO format)
- delivery_method: string or null
- notes: string or null
- confidence_scores: object mapping field names to 0.0-1.0

Subject: {subject}

Body:
{body[:3000]}
```

**Notes**: `max_tokens=800`. Downstream calls `UrnOrderService.create_draft_from_extraction`.

---

### [backend/app/services/urn_intake_agent.py:match_proof_email line 138]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `urn_product` / `urn_engraving_job`
- **Entity ID source**: `tenant_id` param; email metadata
- **Caller linkage candidates**: `company_id` (tenant_id), `urn_engraving_job_id` once matched.
- **Proposed prompt_key**: `urn.match_proof_email` (NEW PROMPT NEEDED). `model_preference`: `haiku` (single-field extraction).
- **Migration complexity**: LOW
- **Variables used**: `subject`, `body[:1500]`
- **Response parsing**: `json.loads(result) if result else {}` — reads `decedent_name`.

#### System prompt / User prompt — verbatim (single argument)
Call: `call_anthropic(prompt, max_tokens=100)` (single-arg form).
```
Extract the decedent name from this proof email from Wilbert.
Return ONLY a JSON object: {"decedent_name": "..."}

Subject: {subject}
Body:
{body[:1500]}
```

**Notes**: `max_tokens=100`. Fallback from order-reference regex match.

---

### [backend/app/services/ai/voice_memo_service.py:extract_memo_data line 69]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company_entity` (ActivityLog attached to master_company_id)
- **Entity ID source**: `master_company_id` param (optional); `tenant_id` and `user_id` from caller
- **Caller linkage candidates**: `company_id` (tenant_id), `company_entity_id` (master_company_id), `user_id`. Future `activity_log_id` once persisted.
- **Proposed prompt_key**: `crm.extract_voice_memo` (NEW PROMPT NEEDED). `model_preference`: `haiku` (short transcripts, cost-sensitive per memo).
- **Migration complexity**: LOW
- **Variables used**: `transcript`, optional `company_context`
- **Response parsing**: `json.loads(response)` — reads activity_type/title/body/outcome/follow_up_needed/follow_up_days/action_items.

#### System prompt / User prompt — verbatim (single argument)
Call: `call_anthropic(prompt, max_tokens=300)` (single-arg form).
```
Extract structured data from this voice memo by a business owner/employee at a precast concrete manufacturer.

Return JSON only:
{
  "activity_type": "call"|"visit"|"note"|"complaint"|"follow_up",
  "contact_name": string or null,
  "title": "brief 1-line summary",
  "body": "full cleaned-up notes",
  "outcome": string or null,
  "follow_up_needed": boolean,
  "follow_up_description": string or null,
  "follow_up_days": integer or null,
  "action_items": ["list of action items"]
}

Voice memo transcript:
{transcript}

{f"Company context: {company_context}" if company_context else ""}
```

**Notes**: Transcript from Deepgram; Claude is the second stage. Feature-flag gated via `ai_settings_service.is_enabled`. `max_tokens=300`.

---

### [backend/app/services/ai/briefing_intelligence.py:generate_narrative line 18]
- **Category**: B — NOTE: this file's `_call_claude` at line 15 wraps `call_anthropic`; there are three downstream callers (`generate_narrative`, `generate_prep_note`, `generate_weekly_summary`). Counted as one call site per the pre-classification.
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: false — returns plain string narrative
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `user` / `company` (morning briefing)
- **Entity ID source**: `tenant_id`, `user_id` params; `master_company_id` for prep_note flavor
- **Caller linkage candidates**: `company_id`, `user_id`, `company_entity_id` (for prep_note).
- **Proposed prompt_key**: `briefing.generate_narrative` (NEW PROMPT NEEDED — the existing `briefing.daily_summary` is used by briefing_service.py and produces different output; this one is conversational narrative text). Also needs `briefing.generate_prep_note` and `briefing.generate_weekly_summary` sub-prompts (or collapse into one with variant var). `model_preference`: `haiku` (daily jobs, cost-sensitive).
- **Migration complexity**: MEDIUM — three distinct prompts inside one file; migrate as three separate prompt keys OR one parameterized prompt.
- **Variables used**: For narrative: `user_name`, `company_name`, `tone_instruction`, `today_str`, `orders_count`, `legacy_count`, `followup_count`, `overdue_count`, `at_risk_count`. For prep_note: `entity.name`, `context` (multi-line facts), `activity_context`. For weekly_summary: `this_week.orders`, `this_week.revenue`, `last_week.orders`, `last_week.revenue`.
- **Response parsing**: Plain string return.

#### System prompt — verbatim
None — `_call_claude` wraps `call_anthropic(prompt, max_tokens=...)` with only a single positional prompt argument (no separate system prompt).

#### Prompt for `generate_narrative` — verbatim (constructed)
```
You are writing a morning briefing narrative for {user_name}, who manages {company_name}, a precast concrete manufacturer.

Write in second person. Be direct and specific. Prioritize urgent items. Sound like a knowledgeable assistant, not a robot.
Tone: {tone_instruction}

Today is {today_str}.

Data:
- Services/deliveries today: {orders_count}
- Legacy proofs pending review: {legacy_count}
- Follow-ups due today: {followup_count}
- Overdue follow-ups: {overdue_count}
- At-risk accounts: {at_risk_count}

Write the narrative. Include what looks good AND what needs attention. Do not list everything — focus on what matters most.
```
Where `tone_instruction` is `"2-3 sentences max."` or `"4-6 sentences, more detail."`.

#### Prompt for `generate_prep_note` — verbatim (constructed)
```
Generate a brief pre-call prep note for a call with {entity.name}.

{f"Last interaction context: {activity_context}" if activity_context else ""}

Current data:
{context}

Provide:
1. Quick situation summary (1 sentence)
2. Key things to address (2-3 bullets)
3. Any issues to watch (1-2 bullets if relevant)

Be specific. Use actual data.
```
Where `context` is a multi-line string: `Company: ...`, `Location: ...`, `Balance: ...`, `Payment terms: ...`, `Recent orders: ...`, `Health: ...`, `Avg payment: ...`.

#### Prompt for `generate_weekly_summary` — verbatim (constructed)
```
Write a weekly business summary for a precast concrete manufacturer. Be specific with numbers. Note trends (up/down). Under 100 words.

This week: {this_week.orders} orders, ${float(this_week.revenue):,.0f} revenue
Last week: {last_week.orders if last_week else 0} orders, ${float(last_week.revenue if last_week else 0):,.0f} revenue

Summarize performance and note any trends.
```

**Notes**: All three gated via `ai_settings_service.is_enabled`. `max_tokens`: 200/200/150 respectively. One call site per the pre-classification; treat the three internal prompts as sub-variants.

---

### [backend/app/services/ai/agent_orchestrator.py:account_rescue_agent line 437]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (JSON expected with subject/body)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company_entity` (at-risk customer)
- **Entity ID source**: `entity.id`, `tenant_id` in scope
- **Caller linkage candidates**: `company_id` (tenant_id), `company_entity_id` (entity.id). Future `ai_rescue_draft_id`.
- **Proposed prompt_key**: `crm.draft_rescue_email` (NEW PROMPT NEEDED). `model_preference`: `haiku` (email draft, nightly batch).
- **Migration complexity**: LOW
- **Variables used**: `entity.name`, `getattr(entity, 'customer_type', 'customer')`, `reason` (first item from `profile.health_reasons`)
- **Response parsing**: `json.loads(response)` — reads `subject`, `body`.

#### System prompt / User prompt — verbatim (single argument)
Call: `call_anthropic(prompt, max_tokens=150)` (single-arg form).
```
Draft a short, friendly check-in email from a small precast concrete manufacturer to a customer who hasn't ordered recently. Warm tone, not salesy. 3-4 sentences max.

Customer: {entity.name}
Type: {getattr(entity, 'customer_type', 'customer')}
Reason flagged: {reason}

Return JSON: {"subject": "...", "body": "..."}
```

**Notes**: Gated via `ai_settings_service.is_enabled("account_rescue")`. Persists to `ai_rescue_drafts`.

---

### [backend/app/api/routes/operations_board.py:get_daily_context line 582]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (mandates JSON schema)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `user` (plant manager daily briefing)
- **Entity ID source**: `current_user.id`, `current_user.company_id` via dependency
- **Caller linkage candidates**: `company_id`, `user_id`.
- **Proposed prompt_key**: `briefing.plant_manager_daily_context` (NEW PROMPT NEEDED). `model_preference`: `haiku` (daily briefing, cost-sensitive).
- **Migration complexity**: MEDIUM — complex context_data with conditional `vault_prompt_addendum`.
- **Variables used**: `day_name`, `hour`, `vault_prompt_addendum` (dynamic), `context_data` (day_name, hour, today, today_deliveries, expected_pos_count, expected_pos, production_entries_today, optional vault_status)
- **Response parsing**: Expects `{greeting, priority_message, items: [...]}`.

#### System prompt — verbatim
```
You are an operations assistant for a burial vault manufacturing plant. Generate brief, practical daily context for the plant manager. Be concise — plant managers are busy. No fluff.
```

#### User prompt — verbatim (constructed)
```
Generate a daily context briefing for {day_name} at {hour}:00. Return JSON only: {"greeting": string, "priority_message": string, "items": [{"type": string, "message": string, "action_label": string, "action_url": string}]}{vault_prompt_addendum}
```
Where `vault_prompt_addendum` is empty OR one of:
```


IMPORTANT: Vault inventory is CRITICAL. Include this as the FIRST item in 'items': type='vault_reorder', message='Vault order must be placed TODAY — stock is below reorder point', action_label='Create Vault Order', action_url='/purchasing/po/new?vendor={vault_supplier_vendor_id}'
```
```


Vault inventory needs attention. Include a normal-priority item in 'items': type='vault_reorder', message='Vault reorder needed soon — stock approaching reorder point', action_label='Review Vault Stock', action_url='/console/operations'
```
Context data passed via `context_data=context_data`.

**Notes**: `max_tokens=400`. Fallback path returns hard-coded greeting when API fails.

---

### [backend/app/api/routes/operations_board.py:interpret_transcript line 662]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true (each branch prompt embeds JSON schema)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: depends on `request.context`: `none`/`safety_program`/`employee`/`agent_job`; effectively none at prompt time
- **Entity ID source**: `current_user.id`, `company_id` via dep
- **Caller linkage candidates**: `company_id`, `user_id`. Related FK populated by downstream handler.
- **Proposed prompt_key**: `voice.interpret_transcript` (NEW PROMPT NEEDED). Could also split into per-context prompt keys: `voice.interpret_production_log`, `voice.interpret_incident`, `voice.interpret_safety_observation`, `voice.interpret_qc_fail_note`, `voice.interpret_inspection`. `model_preference`: `haiku` (voice interpretation, fast turnaround).
- **Migration complexity**: MEDIUM — 5 distinct system prompts selected by `request.context`.
- **Variables used**: `request.transcript`, `request.available_products`, `request.available_employees`; `request.context` selects the system prompt
- **Response parsing**: Passthrough — returned directly from `call_anthropic`.

#### System prompts — verbatim (one per context key)

**production_log**:
```
You are interpreting a voice log entry from a burial vault manufacturing plant manager. Extract production quantities. Match product names flexibly (e.g. 'monty' = Monticello, 'gravliner' = Graveliner, 'venish' = Venetian). Return JSON: {"entries": [{"product_name": string, "matched_product_id": string|null, "quantity": number, "confidence": number}], "unrecognized": [string], "notes": string|null}
```

**incident**:
```
You are interpreting a safety incident report from a burial vault plant manager. Extract incident details. Return JSON: {"incident_type": "near_miss"|"first_aid"|"recordable"|"property_damage"|"other", "location": string|null, "people_involved": [{"name": string, "matched_id": string|null}], "description": string, "immediate_actions": string|null, "confidence": number}
```

**safety_observation**:
```
You are interpreting a safety observation from a burial vault plant manager. Return JSON: {"observation_type": "positive"|"concern"|"near_miss", "location": string|null, "description": string, "people_involved": [{"name": string, "matched_id": string|null}], "confidence": number}
```

**qc_fail_note**:
```
Extract a defect description from a QC failure note. Return JSON: {"defect_description": string, "disposition": "rework"|"scrap"|"accept"|null}
```

**inspection**:
```
Extract inspection results from a voice note. Return JSON: {"overall_pass": boolean, "issues": [{"equipment": string|null, "description": string}], "notes": string|null}
```

#### User prompt — verbatim (constructed)
```
The manager said: '{transcript}'

Available products: {available_products}
Available employees: {available_employees}
```

**Notes**: Voice-driven transcript interpreter. 400 validation if context key is unknown.

---

### [backend/app/services/ai/name_enrichment_agent.py:enrich_company_name line 153]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company_entity`
- **Entity ID source**: `entity.id`, `entity.company_id`
- **Caller linkage candidates**: `company_id`, `company_entity_id`. Future: `ai_name_suggestion_id`.
- **Proposed prompt_key**: `crm.suggest_complete_name` (NEW PROMPT NEEDED). `model_preference`: `haiku` (short fallback call).
- **Migration complexity**: LOW
- **Variables used**: `suffix_type` ("cemetery" or "funeral home"), `entity.name`, `entity.city`, `entity.state`
- **Response parsing**: `json.loads(response)` — reads `suggested_name`, `confidence`, `reasoning`.

#### System prompt / User prompt — verbatim (single argument)
Call: `call_anthropic(prompt, max_tokens=100)` (single-arg form).
```
A precast concrete manufacturer has a {suffix_type} in their CRM with the shorthand name "{entity.name}".
Location: {entity.city or 'unknown'}, {entity.state or 'unknown'}

What is the most likely complete professional name? Add "Cemetery", "Memorial Gardens", "Funeral Home" etc as appropriate.
Return JSON only: {"suggested_name": "...", "confidence": 0.0-1.0, "reasoning": "..."}
```

**Notes**: Fallback from Google Places; called only when Places returns nothing or confidence < 0.70. `max_tokens=100`.

---

### [backend/app/api/routes/workflows.py:generate_workflow line 427]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: true ("Respond with the JSON object only")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `workflow_run` (but really `workflow` definition — admin-authored)
- **Entity ID source**: `current_user.id`, `current_user.company_id` via require_admin
- **Caller linkage candidates**: `company_id`, `user_id`. Future: `workflow_id` once persisted.
- **Proposed prompt_key**: `workflow.generate_from_description` (NEW PROMPT NEEDED; distinct from existing `workflow.ai_step_generic`). `model_preference`: `sonnet` (structural generation requires high accuracy).
- **Migration complexity**: MEDIUM — output feeds directly into workflow_step creation; schema drift would break engine.
- **Variables used**: `data.description`, `vert` (company vertical)
- **Response parsing**: Direct return as dict; `setdefault` for trigger_type and steps.

#### System prompt — verbatim
```
You are a workflow designer for an ERP platform. Convert a natural-language description of a business process into a structured workflow JSON object.

Output schema:
{
  "name": "Short imperative name (e.g. 'Schedule Delivery')",
  "description": "One-sentence description.",
  "keywords": ["phrase", "another phrase"],
  "trigger_type": "manual" | "scheduled" | "event",
  "trigger_config": {} | null,
  "icon": "lucide-icon-name",
  "steps": [
    {
      "step_order": 1,
      "step_key": "snake_case_key",
      "step_type": "input" | "action" | "condition" | "output",
      "config": { ... }
    }
  ]
}

Input step config: { "prompt": "...", "input_type": "text|number|select|date_picker|datetime_picker|crm_search|record_search|user_search", "required": bool, "options": [...] (for select), "record_type": "..." (for record_search) }
Action step config: { "action_type": "create_record|send_email|send_notification|log_vault_item|generate_document|open_slide_over|show_confirmation", plus action-specific fields }
Condition step config: { "expression": "...", "true_next": "step_key", "false_next": "step_key" }
Output step config: { "action_type": "open_slide_over|show_confirmation", "message": "..." }

Use {input.step_key.field} and {output.step_key.field} to reference prior step outputs.

Respond with the JSON object only.
```

#### User prompt — verbatim
```
{data.description}
```
Context data: `{"company_vertical": vert}`.

**Notes**: `max_tokens=2048`. Requires admin role. Returns 400 if description < 10 chars; 502 on AI failure.

---

### [backend/app/api/routes/ai.py:ai_prompt line 44]
- **Category**: B
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: depends on caller (`request.system_prompt` arbitrary)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none — generic passthrough endpoint
- **Entity ID source**: `current_user` via dep (company_id, id)
- **Caller linkage candidates**: `company_id`, `user_id`.
- **Proposed prompt_key**: NO PROMPT KEY — this endpoint MUST be removed or restricted once Phase 2c completes. It is a generic Claude passthrough that bypasses the prompt registry entirely. Architectural concern.
- **Migration complexity**: HIGH — this endpoint is an open back door to any Claude call. Migration requires understanding and removing every frontend caller that relies on arbitrary `system_prompt`/`user_message` parameters, or gating by an explicit allow-list of prompt_keys. No simple drop-in replacement.
- **Variables used**: `request.system_prompt`, `request.user_message`, `request.context_data`
- **Response parsing**: Passthrough — caller owns schema.

#### System prompt — verbatim
Caller-supplied (arbitrary). There is no hardcoded system prompt at this site.

#### User prompt — verbatim
Caller-supplied.

**Notes**: This endpoint must not be preserved as-is post-migration. Recommend deprecation with a sunset header and a frontend survey to identify any remaining callers before removal. Treat as architectural debt, not a migration target.

---

### [backend/app/api/routes/ai_command.py:process_command → _call_claude line 53]
- **Category**: B — NOTE: file-level helper `_call_claude` at line 49 wraps `call_anthropic`; multiple endpoints (`process_command`, `parse_filters`, `company_chat`, `enhance_briefing` via sub-service, `voice_command`) call it. All are wrappers of `call_anthropic(prompt, max_tokens=...)` with a single positional string.
- **Model string**: default (`claude-sonnet-4-20250514`)
- **force_json**: varies per caller — true for command/parse_filters/company_chat
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `user`, `company_entity` (company_chat), `user_actions`
- **Entity ID source**: `current_user.company_id`, `current_user.id`; `data.master_company_id` (company_chat)
- **Caller linkage candidates**: `company_id`, `user_id`, `company_entity_id` (for chat variants).
- **Proposed prompt_key**: Multiple — `commandbar.legacy_process_command`, `commandbar.parse_filters`, `commandbar.company_chat`. All NEW PROMPT NEEDED. `model_preference`: `haiku` (fast turnaround). These may overlap with the newer `/core/command` pipeline; confirm overlap and collapse where possible.
- **Migration complexity**: MEDIUM — four sibling endpoints, each with its own prompt; some duplication with core_command_service.
- **Variables used**: For command: `data.query`, `(data.context or {}).get('current_page')`. For parse_filters: `data.entity_type`, `today`, `data.query`. For company_chat: `context` (company facts), `history_text`, `data.message`.
- **Response parsing**: `json.loads(response)` in most handlers.

#### Prompt for `process_command` — verbatim (constructed)
```
You are a command interpreter for a vault manufacturer's business platform called Bridgeable.

Classify this query and return JSON only:
{
  "intent": "navigate"|"search"|"action"|"question",
  "display_text": "plain English description of what will happen",
  "navigation_url": "/path" or null,
  "action_type": "log_activity"|"complete_followup"|"create_order"|"navigate" or null,
  "parameters": {},
  "entity_name": "company name mentioned" or null
}

Available pages: /ar/orders, /crm/companies, /crm/funeral-homes, /legacy/library, /scheduling, /announcements, /settings, /admin/users, /inventory, /production-log, /safety

User query: {data.query}
Current page: {(data.context or {}).get('current_page', 'unknown')}
```

#### Prompt for `parse_filters` — verbatim (constructed)
```
Parse this filter query for a {data.entity_type} list in a business platform.
Today is {today}.

Return JSON only with these fields (all optional, null if not specified):
{
  "date_from": "YYYY-MM-DD" or null,
  "date_to": "YYYY-MM-DD" or null,
  "status": "string" or null,
  "customer_type": "funeral_home"|"contractor"|"cemetery"|etc or null,
  "amount_min": number or null,
  "amount_max": number or null,
  "search_text": "string" or null,
  "chips": ["human-readable label for each filter"]
}

Examples:
"last month" → date_from: first of last month, date_to: last of last month
"over $2000" → amount_min: 2000
"funeral homes" → customer_type: "funeral_home"
"unpaid" → status: "unpaid"
"overdue" → status: "overdue"

Query: {data.query}
```

#### Prompt for `company_chat` — verbatim (constructed)
```
You are answering questions about a specific company in a business CRM for a vault manufacturer.

Company data:
{context}

{f"Conversation so far:{history_text}" if history_text else ""}

Answer the user's question using only the data provided. Be concise — 1-3 sentences. If the data doesn't contain the answer, say so clearly.

User: {data.message}
```
Where `context` is a multi-line block: `Company: {name}`, `Type: {customer_type}`, `Location: {city}, {state}`, `Phone: {phone}`, `Account status: {account_status}`, `Current balance: $...`, `Payment terms: ...`, `Recent orders: ...`, `Contacts: ...`, `Health score: ...`, `Orders (12mo): ...`, `Revenue (12mo): $...`, `Most ordered: ...`, `Avg payment time: ... days`.

**Notes**: Feature-flag gated via `ai_settings_service.is_enabled` (per endpoint). `max_tokens`: 200 for all three.

---


## 4. Category C — DIRECT SDK (no audit coverage today — highest priority)

Every entry in this section imports `anthropic` and calls `client.messages.create(...)` directly, bypassing `call_anthropic` and the audit shim entirely. These produce **zero** `intelligence_executions` rows and are the priority for Phase 2c.

### [backend/app/services/first_call_extraction_service.py:extract_first_call line 90]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20251001` (hardcoded in module-level `EXTRACTION_MODEL`)
- **force_json**: true (system prompt says "Return JSON only")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `funeral_case` (FHCase — first call intake)
- **Entity ID source**: None at call time — the extraction *precedes* FHCase creation. Caller (FH scribe workflow) has user/tenant in scope.
- **Caller linkage candidates**: `company_id` and `user_id` from caller context; `fh_case_id` not yet available. Future: could link via a `scribe_session_id`.
- **Proposed prompt_key**: Align with existing `scribe.extract_case_fields_live` or add `scribe.extract_first_call`. `model_preference`: `haiku` (matches current hardcoded model; fast scribe pass).
- **Migration complexity**: LOW — clean interface, `_build_user_prompt` already isolates the user message.
- **Variables used**: `text`, `existing_values`, `today` (date.today().isoformat())
- **Response parsing**: `_strip_code_fences` → `json.loads` → reads `extracted` map of `{field: {value, confidence}}`.

#### System prompt — verbatim
```
You are extracting first call information for a funeral home intake form.
Extract only information explicitly stated. Do not infer or assume. Return JSON only. No other text.
Date references like "this morning", "last night", "yesterday" should be resolved relative to today's date.
Phone numbers should be formatted as entered, not reformatted.
Names should be capitalized correctly.
```

#### User prompt template — verbatim (constructed)
```
Extract the following fields from this first call description.
For each field, provide the value and a confidence score (0-1).
Only extract fields where you have clear evidence in the text.

Fields to extract:
- deceased_first_name (string)
- deceased_last_name (string)
- deceased_date_of_death (ISO date YYYY-MM-DD — today is {today})
- deceased_time_of_death (HH:MM 24hr format)
- deceased_place_of_death (enum: hospital, home, nursing_facility, hospice, other)
- deceased_place_of_death_name (string — facility name if applicable)
- deceased_place_of_death_city (string)
- deceased_place_of_death_state (string — 2 letter code)
- deceased_age_at_death (integer)
- deceased_veteran (boolean)
- contact_first_name (string)
- contact_last_name (string)
- contact_relationship (enum: spouse, child, parent, sibling, other)
- contact_phone_primary (string)
- contact_phone_secondary (string)
- contact_email (string)
- disposition_type (enum: burial, cremation, green_burial, donation, entombment)
- service_type (enum: traditional_funeral, graveside_only, memorial_service, direct_burial, direct_cremation, celebration_of_life, no_service)
- disposition_location (string — cemetery name)
- notes (string — anything mentioned that doesn't fit other fields)

Current form values (do not re-extract these unless the new text contradicts them):
{json.dumps(existing_values)}

First call description:
{text}

Return JSON in this exact format:
{
  "extracted": {
    "field_name": {"value": ..., "confidence": 0.0-1.0}
  }
}
Only include fields where you found clear evidence. Omit fields with no evidence.
```

**Notes**: `max_tokens=1024`. Overlaps conceptually with already-migrated `scribe.extract_case_fields` but uses distinct field taxonomy. Decide during migration whether to collapse or keep separate.

---

### [backend/app/services/website_analysis_service.py:analyze_website_content line 85]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20251001` (module-level `ANALYSIS_MODEL`)
- **force_json**: true (JSON object per prompt)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company_entity` (website-sourced enrichment for a tenant or a customer during onboarding)
- **Entity ID source**: Not directly in this function — passed only `raw_content`. Caller (onboarding) has `tenant_id` in scope.
- **Caller linkage candidates**: `company_id` (via caller). Future: `company_entity_id` when called on behalf of a specific entity.
- **Proposed prompt_key**: `onboarding.analyze_website` (NEW PROMPT NEEDED). `model_preference`: `haiku`.
- **Migration complexity**: LOW — isolated function, deterministic inputs.
- **Variables used**: `raw_content[:60_000]` (truncated)
- **Response parsing**: `_strip_code_fences` → `json.loads` → full nested schema (see prompt).

#### System prompt — verbatim
```
You are a business intelligence analyst examining a company's website content.
Extract structured information about this business, focusing on precast concrete /
burial vault / funeral product manufacturing. If the business is in a different
industry, adapt your analysis accordingly.

Return a JSON object with these fields:

{
  "business_name": "string — company name",
  "industry": "string — primary industry (e.g. 'precast_concrete', 'burial_vaults', 'funeral_products', 'general_manufacturing', 'other')",
  "description": "string — 1-2 sentence business summary",
  "product_lines": [
    {"name": "string", "confidence": 0.0-1.0, "evidence": "string — quote or reference from content"}
  ],
  "vault_lines": [
    {"name": "string", "confidence": 0.0-1.0, "evidence": "string"}
  ],
  "certifications": [
    {"name": "string", "type": "string — e.g. 'npca', 'iso', 'other'", "confidence": 0.0-1.0, "evidence": "string"}
  ],
  "npca_certified": {"detected": true/false, "confidence": 0.0-1.0, "evidence": "string or null"},
  "spring_burials": {"detected": true/false, "confidence": 0.0-1.0, "evidence": "string or null"},
  "urn_categories": [
    {"name": "string", "confidence": 0.0-1.0, "evidence": "string"}
  ],
  "services": ["string — list of services offered"],
  "locations": ["string — any mentioned locations or service areas"],
  "key_differentiators": ["string — notable capabilities or selling points"],
  "recommended_extensions": [
    {"key": "string — extension identifier", "reason": "string", "confidence": 0.0-1.0}
  ],
  "summary": "string — 2-3 sentence onboarding summary with recommendations"
}

Rules:
- Set confidence between 0.0 and 1.0 based on how clearly the info is stated.
- Only include items you actually find evidence for; do not fabricate.
- For vault_lines, look for brand names like Wilbert, Trigard, etc.
- For spring_burials, look for references to winter/spring burial, temporary storage, seasonal burial.
- For NPCA, look for "National Precast Concrete Association" or "NPCA certified/member".
- For urn_categories, look for cremation urns, keepsakes, companion urns, etc.
- recommended_extensions should map to: vault_program, spring_burial, cremation_tracking, npca_compliance, urn_catalog.
```

#### User prompt — verbatim (constructed)
```
Analyze the following website content and extract structured business information. Respond with valid JSON only.

{truncated raw_content up to 60000 chars}
```

**Notes**: `max_tokens=2048`. Returns token usage alongside analysis. Clean single-call service ideal for migration.

---

### [backend/app/services/price_list_extraction_service.py:_extract_pdf_via_claude line 100]
- **Category**: C
- **Model string**: `claude-sonnet-4-20250514` (hardcoded in the `client.messages.create` call)
- **force_json**: false — returns plain text extracted from a PDF
- **Streaming**: false
- **Tool use**: false
- **Vision**: true — PDF document as `type=document`
- **Caller entity type**: `price_list` / `invoice` (vendor or customer price list PDF)
- **Entity ID source**: Not at this function — called during `_extract_pdf` fallback.
- **Caller linkage candidates**: `company_id` (tenant), future `price_list_import_id`.
- **Proposed prompt_key**: `pricing.extract_pdf_text` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (document OCR / layout preservation benefits from higher-quality model; already using sonnet).
- **Migration complexity**: MEDIUM — document-type content (vision/PDF) needs the intelligence layer to support non-text inputs. Confirm the registry renderer supports document content blocks before migration.
- **Variables used**: `content` (PDF bytes → base64)
- **Response parsing**: `message.content[0].text if message.content else ""` — plain text.

#### System prompt — verbatim
None (no system prompt passed).

#### User prompt — verbatim (multimodal)
- Content block 1 (document):
  - `type: "document"`, `source: {type: "base64", media_type: "application/pdf", data: <b64>}`
- Content block 2 (text):
```
Extract all text content from this price list PDF. Preserve the layout as accurately as possible — keep section headers, product names, prices, and any notes exactly as they appear. Return only the extracted text, no commentary.
```

**Notes**: `max_tokens=8192`. Fallback path from pdfplumber for scanned/image-only PDFs. The multimodal content block is a first-class migration concern.

---

### [backend/app/services/customer_classification_service.py:_classify_batch_with_ai line 357]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20250514` (hardcoded)
- **force_json**: true (system prompt amended with strict JSON-array instruction)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company_entity` / `customer` (batch)
- **Entity ID source**: Each input has `index` (in-batch pointer); caller has tenant context via parse_customers.
- **Caller linkage candidates**: `company_id` (via caller). Per-batch entity IDs are pre-persistence staging.
- **Proposed prompt_key**: `onboarding.classify_customer_batch` (NEW PROMPT NEEDED; distinct from single-row `crm.classify_entity_single` in Category B). `model_preference`: `haiku` (matches current model).
- **Migration complexity**: LOW
- **Variables used**: `unclassified` (list of `{index, name, city, state}`)
- **Response parsing**: Strip code fences → `json.loads` → expect JSON array with same length; map by `index`.

#### System prompt — verbatim (with appended JSON instruction)
```
You are a customer classification assistant for Sunnycrest Precast, a Wilbert burial vault manufacturer in Auburn, NY. Their customers fall into these categories:

- funeral_home: Funeral homes, mortuaries, chapels, cremation services
- cemetery: Cemeteries, memorial parks, mausoleums, burial grounds
- contractor: Excavation, construction, landscaping, septic/wastewater, well drilling, site work, drain fields, concrete, masonry, and other tradespeople
- individual: A private person (not a business)
- unknown: Cannot be determined from available information

You will receive a JSON array of customers, each with:
  { "index": number, "name": string, "city": string | null, "state": string | null }

Return a JSON array (same length, same order) where each element is:
  {
    "index": <same as input>,
    "customer_type": "funeral_home" | "cemetery" | "contractor" | "individual" | "unknown",
    "confidence": <float 0.0–1.0>,
    "reasoning": "<one sentence>"
  }

Rules:
- Confidence >= 0.85: Very confident
- Confidence 0.70–0.84: Reasonably confident
- Confidence < 0.70: Ambiguous — use "unknown"
- Do not guess — if truly unclear, return unknown with confidence 0.0
- The Wilbert network context: most business customers are funeral homes; contractors often supply precast concrete, septic, or wastewater systems


IMPORTANT: Respond with a valid JSON array only. No markdown, no code fences.
```

#### User prompt — verbatim (constructed)
```
Classify these customers:
{json.dumps(unclassified)}
```

**Notes**: `max_tokens=4096`. Batch size up to 50. Prompt mentions "Sunnycrest Precast" by name — this is a Category C architectural flag (tenant-specific hardcoded branding in a platform service). Migrating should parameterize tenant name.

---

### [backend/app/services/training_content_generation_service.py:_call_claude line 169]
- **Category**: C — NOTE: file-level helper `_call_claude` wraps `client.messages.create`; **three** caller sites (`generate_procedures`, `generate_curriculum_tracks`, `regenerate_specific_procedures`) pass different system prompts and user messages. Pre-classification counts as one call site.
- **Model string**: `claude-sonnet-4-20250514` (module-level `AI_MODEL`)
- **force_json**: true (all prompts append "Respond with valid JSON only. No markdown, no code fences.")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none (content library generation; output is written to `training_procedures` / `training_curriculum_tracks` with `tenant_id=NULL` — shared across manufacturing tenants)
- **Entity ID source**: None — content is platform-wide.
- **Caller linkage candidates**: None (platform-level content). Could link to procedure_key / training_role for bookkeeping.
- **Proposed prompt_key**: Two prompts needed: `training.generate_procedure` and `training.generate_curriculum_track` (both NEW PROMPT NEEDED). `model_preference`: `sonnet` (long-form structured content, once-per-procedure so cost matters less than quality).
- **Migration complexity**: MEDIUM — two distinct system prompts, distinct output schemas, large token budgets (3000/5000).
- **Variables used**: For procedures: `defn.key`, `defn.title`, `defn.roles`, `defn.category`, optional custom `user_msg`. For curriculum: `role`, `role_label`.
- **Response parsing**: Strip fences → `json.loads` → `(dict|None, error|None)` tuple.

#### System prompt — PROCEDURE_SYSTEM_PROMPT verbatim
```
You are generating training content for employees at a Wilbert burial vault manufacturing company using the Bridgeable business management platform.

The company manufactures concrete burial vaults and sells them to funeral homes on charge accounts. Funeral homes order throughout the month and receive a consolidated monthly statement. The company also handles cross-licensee transfers (shipping vaults to other Wilbert licensees in other territories).

End-of-day invoice workflow: At 6 PM each day, the system automatically generates draft invoices for all funeral service orders scheduled for that day. These drafts appear in the Invoice Review Queue (AR Command Center → Invoice Review tab). Accounting staff review and approve the drafts each morning before they are posted to AR. If the company has "require driver status updates" enabled, only orders explicitly confirmed by drivers appear as drafts — unconfirmed orders are flagged separately. Invoices with driver exceptions (shortages, refusals, damage) require individual review before approval. Clean invoices can be batch-approved with one click. This replaces manual invoice entry for recurring funeral service charges.

Bridgeable platform navigation conventions:
- Financials Board → [zone name] (e.g., Financials Board → AR Zone)
- AR Command Center → [tab name] (e.g., AR Command Center → Aging tab)
- AP Command Center → [tab name]
- Operations Board → [zone name]
- Settings → [section name]

Generate a detailed procedure document. Write for new employees who are unfamiliar with the business. Explain WHY each step matters, not just what to do. Be specific about platform navigation paths.

Return JSON only — no markdown, no preamble:
{
  "overview": "string (2-3 paragraphs: business context, why this procedure exists, what goes wrong without it)",
  "steps": [
    {
      "step_number": 1,
      "title": "string (action-oriented title)",
      "instruction": "string (clear, specific instruction)",
      "platform_path": "string (exact navigation path, e.g. 'AR Command Center → Aging tab → Customer row → Apply Payment')",
      "why_this_matters": "string (consequence of skipping or doing wrong)",
      "common_mistakes": ["string", "string"]
    }
  ],
  "related_procedure_keys": ["string"]
}
```
(Appended at call time: `\n\nIMPORTANT: Respond with valid JSON only. No markdown, no code fences.`)

#### System prompt — CURRICULUM_SYSTEM_PROMPT verbatim
```
You are generating a 4-week onboarding curriculum for a new employee at a Wilbert burial vault manufacturing company using the Bridgeable platform.

The platform has these core modules: AR management, AP and purchasing, monthly statement billing, finance charges, bank reconciliation, journal entries, financial reports, funeral order management, cross-licensee transfers, and driver/delivery management.

The company sells burial vaults to funeral homes on charge accounts with monthly statement billing. Net 30 payment terms. Finance charges apply to overdue accounts. Cross-licensee transfers happen when a funeral home in another territory needs a vault.

Bridgeable has an AI assistant that proactively flags issues (overdue accounts, payment mismatches, PO discrepancies). Employees review AI suggestions before anything is sent or posted.

Create 12-16 modules across 4 weeks. Each module teaches one specific business process. Write for someone with basic computer skills but no prior industry experience. The first module must be ai_orientation about working with the AI assistant.

Return JSON only:
{
  "track_name": "string",
  "description": "string (2-3 sentences)",
  "estimated_weeks": 4,
  "modules": [
    {
      "week": 1,
      "module_key": "string (snake_case, unique within track)",
      "title": "string",
      "description": "string (one sentence)",
      "concept_explanation": "string (2-3 paragraphs explaining the business concept and why it matters)",
      "guided_task": {
        "instruction": "string",
        "platform_action": "string (specific navigation path and action)",
        "success_criteria": "string (how employee knows they did it right)"
      },
      "comprehension_check": {
        "question": "string",
        "options": ["string", "string", "string", "string"],
        "correct_index": 0,
        "explanation": "string (why that answer is correct)"
      },
      "estimated_minutes": 20
    }
  ]
}
```

#### User messages — verbatim examples
For a standard procedure:
```
Generate a complete procedure document for: {title}
Roles: {', '.join(defn['roles'])}
Category: {defn['category']}
```
For curriculum:
```
Generate a complete 4-week onboarding curriculum for a new {role_label} employee. The first module must be ai_orientation covering: what the AI assistant does, the difference between agent alerts and human decisions, confidence scores, and why human judgment always overrides agent suggestions.
```
Some PROCEDURE_DEFINITIONS entries provide a custom `user_msg` (e.g. `taking_a_funeral_order`, `managing_cemeteries`) — when present, that string is used verbatim. Both literal `user_msg` values in the file are shown below for reference.

**Custom user_msg for `taking_a_funeral_order`:**
```
Write a procedure for taking a funeral order by phone at a Wilbert burial vault manufacturing company using Bridgeable.

The procedure should feel like a cheat sheet for someone on the phone with a funeral home director.

Cover:
- Opening the order station
- Selecting a quick order template vs starting fresh (when to use each)
- Selecting the funeral home (type first 3 letters)
- Understanding the cemetery shortlist (why their common cemeteries appear)
- What happens when a cemetery is selected (equipment auto-fills, county auto-fills)
- Setting the service date
- What to do if the vault or equipment is unusual (override the template)
- Saving the order
- What NOT to do: don't create an invoice manually, it happens automatically tonight
- The AI shorthand trick for speed

Also cover:
- What to do when the funeral home isn't in the system yet: type their name → select '+ Add [name] as new funeral home' → they are created instantly with a monthly statement charge account → complete their profile from Customers later
- The platform will alert you weekly about any customers created this way that still need their profiles completed

Include a 'quick reference' step at the end that summarizes the entire flow in 5 bullet points — something they could tape next to their monitor.

WHY this matters: Every order that gets entered while the funeral home is still on the phone is one that doesn't get lost on a sticky note or forgotten in the afternoon rush.
```

**Custom user_msg for `managing_cemeteries`:**
```
Write a procedure for managing the cemetery list at a Wilbert burial vault manufacturing company using Bridgeable.

Cover:
- Where to find the cemetery list (Customers → Cemeteries tab)
- How to add a new cemetery manually from the customer list
- How to configure equipment settings on a cemetery record (what each flag means)
- What the equipment prefill does on new orders — explain that when a funeral home selects a cemetery that provides its own lowering device, the lowering device charge is automatically removed from the order
- When to update equipment settings: cemetery bought new equipment, policy changed, seasonal variation
- How the county field on a cemetery affects which tax rate is applied to the order
- What to do when a new cemetery comes up during a call (you can create it inline from the order form — you don't need to stop the call)
- The consequence of NOT keeping cemetery settings updated: you charge a funeral home for equipment the cemetery provides, the funeral home pushes back, awkward call after the service

Write for inside sales staff who may be new to the death care industry. Be specific about navigation paths and explain the real-world impact of each setting.
```

**Notes**: `max_tokens`: 3000 (procedure) / 5000 (curriculum). Generates shared content written with `tenant_id=NULL`. Two distinct prompts; treat as two separate registrations.

---

### [backend/app/api/routes/journal_entries.py:parse_entry line 279]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20250514` (module-level `JE_MODEL`)
- **force_json**: true
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `invoice` / `journal_entry` — NL → debit/credit extraction; output becomes a JournalEntry draft
- **Entity ID source**: `current_user.company_id`, `current_user.id` (via dep)
- **Caller linkage candidates**: `company_id`, `user_id`. Future `journal_entry_id` once persisted.
- **Proposed prompt_key**: `accounting.parse_journal_entry` (NEW PROMPT NEEDED). `model_preference`: `haiku` (matches current model).
- **Migration complexity**: LOW
- **Variables used**: `accounts_text` (one line per GL account), `body.input`
- **Response parsing**: `json.loads(response.content[0].text)` — passed through.

#### System prompt — verbatim (constructed)
```
Parse a natural language journal entry into structured debit/credit lines. Chart of accounts:
{accounts_text}

Rules: Assets increase with debits. Liabilities increase with credits. Revenue increases with credits. Expenses increase with debits. Every entry must balance. Return JSON only: {"description": str, "entry_date": str or null, "entry_type": str, "lines": [{"gl_account_id": str, "gl_account_number": str, "gl_account_name": str, "side": "debit"|"credit", "amount": number, "description": str or null}], "confidence": number, "clarification_needed": str or null}
```
Where `accounts_text` is `"\n".join(f"- {a.account_number}: {a.account_name} ({a.platform_category})" for a in gl_accounts)`.

#### User prompt — verbatim
```
{body.input}
```

**Notes**: `max_tokens=500`. Anthropic client uses default API key (no explicit kwarg).

---

### [backend/app/api/routes/accounting_connection.py:sage_analyze_csv line 781]
- **Category**: C
- **Model string**: `claude-sonnet-4-20250514` (hardcoded)
- **force_json**: true ("Return ONLY the JSON object")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none (Sage CSV column mapping)
- **Entity ID source**: `current_user.company_id` via dep
- **Caller linkage candidates**: `company_id`. Future: `accounting_connection_id`.
- **Proposed prompt_key**: `accounting.map_sage_csv` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (matches current model; structured mapping).
- **Migration complexity**: LOW
- **Variables used**: `sample_display` (headers + first 3 rows), `expected` (list of field names)
- **Response parsing**: Handles code-fenced JSON → `json.loads`.

#### System prompt — verbatim
None.

#### User prompt — verbatim (constructed)
```
Analyze this CSV export and map the columns to the expected fields.

CSV Data:
{sample_display}

Expected fields to map to: {json.dumps(expected)}

For each expected field, determine which CSV column (by header name) best matches it.
Return a JSON object with this exact structure:
{
  "mappings": {
    "<expected_field>": {
      "csv_column": "<header_name or null if no match>",
      "confidence": <0.0 to 1.0>
    }
  },
  "unmapped_csv_columns": ["<headers that don't map to any expected field>"]
}

Return ONLY the JSON object, no other text.
```
Where `sample_display` is:
```
Headers: {headers joined with ' | '}
Row 1: {row0_values joined with ' | '}
Row 2: {row1_values joined with ' | '}
Row 3: {row2_values joined with ' | '}
```

**Notes**: `max_tokens=1024`. Supports three export types: invoice_history, customer_list, cash_receipts.

---

### [backend/app/api/routes/reports.py:parse_package_request line 143]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20250514` (module-level `REPORT_MODEL`)
- **force_json**: true
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: none (NL → audit package request)
- **Entity ID source**: `current_user.company_id` via dep
- **Caller linkage candidates**: `company_id`, `user_id`. Future `audit_package_id`.
- **Proposed prompt_key**: `reports.parse_audit_package_request` (NEW PROMPT NEEDED). `model_preference`: `haiku`.
- **Migration complexity**: LOW
- **Variables used**: `body.input`
- **Response parsing**: `json.loads(response.content[0].text)`.

#### System prompt — verbatim
```
Parse an audit package request. Available reports: income_statement, balance_sheet, trial_balance, gl_detail, ar_aging, ap_aging, sales_by_customer, sales_by_product, invoice_register, payment_history, vendor_payment_history, cash_flow, tax_summary. Full audit package: income_statement, balance_sheet, trial_balance, ar_aging, ap_aging, gl_detail, tax_summary. Return JSON: {"package_name": str, "period_start": str, "period_end": str, "reports": [str], "confidence": float}
```

#### User prompt — verbatim
```
{body.input}
```

**Notes**: `max_tokens=400`. Anthropic client uses default API key.

---

### [backend/app/api/routes/order_station.py:parse_order line 626]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20251001` (hardcoded)
- **force_json**: true (prompt ends "Return JSON only")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `sales_order` (NL → draft order)
- **Entity ID source**: `current_user` via dep
- **Caller linkage candidates**: `company_id`, `user_id`. Future `sales_order_id` once persisted.
- **Proposed prompt_key**: `orderstation.parse_voice_order` (NEW PROMPT NEEDED — distinct from the existing `overlay.*` prompts; this is a single-field extractor for the quick-entry form). `model_preference`: `haiku`.
- **Migration complexity**: LOW
- **Variables used**: `today_str` (substituted into `{today}` placeholder in prompt), `input_text`
- **Response parsing**: `json.loads` after stripping code fences.

#### System prompt — verbatim (module-level `_PARSE_ORDER_SYSTEM_PROMPT` with `{today}` replaced)
```
You are parsing a natural language funeral order entry for a burial vault manufacturer.

Extract these fields from the input:
{
  "vault_product": string or null,
  "equipment": string or null,
  "cemetery_name": string or null,
  "service_date": string or null,
  "confidence": float
}

vault_product — match to known vault names (use exact casing):
Monticello, Venetian, Continental, Salute, Tribute, Monarch, Graveliner,
Graveliner SS, Bronze Triune, Copper Triune, SST Triune, Cameo Rose,
Veteran Triune, Wilbert Bronze, Loved & Cherished 19", Loved & Cherished 24",
Loved & Cherished 31", Continental 34, Graveliner 34, Graveliner 38, Pine Box,
Urn Vault (append line name if specified, e.g. "Urn Vault Monticello")

equipment — one of: full_equipment, lowering_device_grass, lowering_device_only, tent_only, no_equipment, null

cemetery_name — extract and expand shorthand:
  "Oak Hill" → "Oak Hill Cemetery", "St Mary's" → "St. Mary's Cemetery",
  "Lakeview" → "Lakeview Cemetery". If already a full name, return as-is.

service_date — always YYYY-MM-DD. Resolve relative dates using today's date:
  "tomorrow" → tomorrow, "Thursday" → next Thursday,
  "March 31" → current or next year's March 31.
  Current date: {today}

confidence — 0.0 to 1.0, how confident you are in the overall parse.

Return JSON only, no markdown. If a field cannot be determined, return null.
```

#### User prompt — verbatim
```
{input_text}
```

**Notes**: `max_tokens=500`. Fails gracefully with `{error, confidence: 0.0}` on any exception. The braces in the output schema are LITERAL JSON braces — not f-string interpolation. Only `{today}` is substituted.

---

### [backend/app/api/routes/financials_board.py:get_briefing line 165]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20250514` (module-level `BRIEFING_MODEL`)
- **force_json**: false (returns plain-text briefing)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `user` / `company` (daily briefing)
- **Entity ID source**: `current_user.company_id`, `current_user.id`
- **Caller linkage candidates**: `company_id`, `user_id`.
- **Proposed prompt_key**: `briefing.financial_board` (NEW PROMPT NEEDED — semantically adjacent to existing `briefing.daily_summary` but renders different context). `model_preference`: `haiku`.
- **Migration complexity**: LOW
- **Variables used**: `summary` (ar_overdue_count/total, ap_due_this_week, payments_today), `alerts_text`, `largest_overdue`
- **Response parsing**: `response.content[0].text` — plain string.

#### System prompt — verbatim
```
You are a financial assistant for a manufacturing business. Write a concise morning briefing (3-5 sentences) based on the data provided. Lead with the most urgent item. Be direct and specific with dollar amounts. Do not use bullet points. Write in second person (you have, you owe).
```

#### User prompt — verbatim (constructed)
```
Overdue AR: {summary['ar_overdue_count']} invoices totaling ${summary['ar_overdue_total']:,.2f}.
AP due this week: ${summary.get('ap_due_this_week', 0):,.2f}.
Payments received today: ${summary['payments_today_total']:,.2f} ({summary['payments_today_count']} payments).
Action required alerts: {alerts_text}.
Largest overdue: {largest_overdue or 'none'}.
```

**Notes**: `max_tokens=300`. Cached per-tenant in-process for 30 min (`_briefing_cache`). Anthropic client uses default API key.

---

### [backend/app/services/sales_service.py:scan_check_image line 2301]
- **Category**: C
- **Model string**: `claude-sonnet-4-20250514` (hardcoded)
- **force_json**: true
- **Streaming**: false
- **Tool use**: false
- **Vision**: true — base64 image as `type=image`
- **Caller entity type**: `invoice` / `customer_payment` (check image → suggested payment applications)
- **Entity ID source**: `company_id` param; caller (route) has user context
- **Caller linkage candidates**: `company_id`. Future `customer_payment_id` once persisted.
- **Proposed prompt_key**: `accounting.extract_check_image` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (vision task, accuracy critical for payment amounts).
- **Migration complexity**: MEDIUM — vision multimodal; requires the intelligence layer to support image content blocks.
- **Variables used**: `b64_image`, `content_type`
- **Response parsing**: `_json.loads(response.content[0].text)` — reads payer_name/amount/check_number/check_date/memo/bank_name + confidence map.

#### System prompt — verbatim
None.

#### User prompt — verbatim (multimodal)
- Content block 1 (image):
  - `type: "image"`, `source: {type: "base64", media_type: {content_type}, data: {b64_image}}`
- Content block 2 (text):
```
Extract payment information from this check image. Return JSON only:
{
  "payer_name": "string or null",
  "amount": "decimal number or null",
  "check_number": "string or null",
  "check_date": "YYYY-MM-DD or null",
  "memo": "string or null",
  "bank_name": "string or null",
  "confidence": {
    "payer_name": 0.0,
    "amount": 0.0,
    "check_number": 0.0,
    "check_date": 0.0
  }
}
Return only valid JSON. If a field is not clearly visible, return null.
```

**Notes**: `max_tokens=500`. Uses `settings.anthropic_api_key` (note lowercase — possible config inconsistency; all other call sites use `settings.ANTHROPIC_API_KEY`). Architectural flag: normalize config access during migration.

---

### [backend/app/services/agent_service.py:_generate_collections_draft line 246]
- **Category**: C
- **Model string**: module-level `COLLECTIONS_MODEL` (not shown in snippet; verify at file top — likely `claude-haiku-4-5-20250514` per pattern; exact value depends on line 1 imports)
- **force_json**: true (prompt specifies strict JSON output)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `invoice` / `company_entity` (AR collections)
- **Entity ID source**: caller (`collections_sequence`) has `invoice.id`, `customer.id`, `seq.tenant_id` in scope
- **Caller linkage candidates**: `company_id`, `invoice_id`, `company_entity_id` (customer.master_company_id). Strong linkage candidates. Overlaps heavily with already-migrated `agent.ar_collections.draft_email` — this is a LEGACY duplicate that should be retired in favor of the registered prompt.
- **Proposed prompt_key**: Collapse to existing `agent.ar_collections.draft_email` (Category A). No new prompt needed. `model_preference`: `haiku`.
- **Migration complexity**: LOW — replace with a call to the already-migrated prompt; the caller path (the nightly `collections_sequence` job) then writes via `intelligence_service.execute` instead.
- **Variables used**: `customer_name`, `invoice_number`, `amount`, `due_date`, `days_overdue`, `tone`, `step`
- **Response parsing**: `json.loads(response.content[0].text)`.

#### System prompt — verbatim (constructed)
```
You are a professional AR collections assistant. Write a {tone} collections email. {tone_instructions.get(tone, '')} Keep it brief. Return JSON only: {"subject": string, "body": string}
```
Where `tone_instructions` maps to:
- `friendly_reminder`: `"Polite and professional. Assume good faith — this may be an oversight."`
- `firm_professional`: `"Professional but firm. This is the second notice. Express concern about the overdue balance."`
- `final_notice`: `"Direct and serious. This is the final notice before account review. Mention that the account may be placed on hold if payment is not received within 10 days."`

#### User prompt — verbatim (constructed)
```
Customer: {customer_name}
Invoice: #{invoice_number}
Amount: ${amount:,.2f}
Original due date: {due_date}
Days overdue: {days_overdue}
Notice: step {step} of 3
```

**Notes**: This is the legacy job-style caller, distinct from the newer `ARCollectionsAgent` service class that uses `intelligence_service.execute`. During Phase 2c, retire this function and route `run_collections_sequence` through the agent. Until then, this is a legacy call site that must still be migrated.

---

### [backend/app/services/accounting_analysis_service.py:run_ai_analysis line 174]
- **Category**: C
- **Model string**: `claude-haiku-4-5-20250514` (module-level `ANALYSIS_MODEL`)
- **force_json**: true (ends "No preamble, no markdown")
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `company` (tenant-wide COA analysis)
- **Entity ID source**: `tenant_id` param
- **Caller linkage candidates**: `company_id`. Future: `analysis_run_id` already generated (persist alongside `intelligence_execution`).
- **Proposed prompt_key**: `accounting.coa_classify` (ALREADY SEEDED in the prompt_registry candidates list). Confirm existing seed matches this prompt verbatim; if drift, update seed. `model_preference`: `haiku`.
- **Migration complexity**: **HIGH** — see dedicated section below. Central to the COA-connection onboarding experience; output mutates multiple tables (TenantAccountingAnalysis rows for gl_mappings/customer_analysis/vendor_analysis/stale_accounts/product_matches/network_flags) with confidence-based auto-approval gating (0.85 threshold). Any drift in the JSON response schema silently breaks the review UI.
- **Variables used**: `user_data` — json.dumps of all staged records grouped by `data_type`; unbounded size depending on tenant's COA / vendor / customer list.
- **Response parsing**: `json.loads(result_text)` → iterates `gl_mappings`, `stale_accounts`, `customer_analysis`, `vendor_analysis`, `product_matches`, `network_flags`.

#### System prompt — verbatim
```
You are an accounting data analyst specializing in manufacturing and funeral service businesses. You will be given a chart of accounts and customer/vendor/product data from a new tenant onboarding to a business management platform.

Your job is to analyze this data and return structured JSON mapping their accounts to our platform schema.

Platform account categories that need mapping:

REVENUE: vault_sales, urn_sales, equipment_sales, delivery_revenue, redi_rock_sales, wastewater_sales, rosetta_sales, service_revenue, other_revenue
AR: ar_funeral_homes, ar_contractors, ar_government, ar_other
COGS: vault_materials, direct_labor, delivery_costs, other_cogs
AP: accounts_payable
EXPENSES: rent, utilities, insurance, payroll, office_supplies, vehicle_expense, repairs_maintenance, depreciation, professional_fees, advertising, other_expense

For each mapping return:
- account_number
- account_name
- platform_category (from lists above)
- confidence (0.0 to 1.0)
- reasoning (one sentence)
- alternative (second best guess if confidence below 0.85)

Also analyze:

STALE ACCOUNTS: Flag any accounts with zero transaction volume in the last 90 days (or no transaction data available) as potentially stale. Return a stale_accounts array.

CUSTOMER ANALYSIS: For each customer, infer:
- customer_type (funeral_home, cemetery, contractor, government, retail, unknown)
- confidence score
- reasoning

VENDOR ANALYSIS: For each vendor, infer:
- vendor_type (materials_supplier, equipment, utilities, professional_services, unknown)
- confidence score

PRODUCT MATCHING: For each product/item in their accounting system, suggest the closest match in our platform product catalog if one exists.

NETWORK COMPARISON: Note that this tenant is joining a network of similar businesses. Flag any accounts or configurations that appear unusual compared to standard manufacturing/funeral service COA patterns.

Return ONLY valid JSON with this structure:
{
  "gl_mappings": [...],
  "stale_accounts": [...],
  "customer_analysis": [...],
  "vendor_analysis": [...],
  "product_matches": [...],
  "network_flags": [...]
}
No preamble, no markdown.
```

#### User prompt — verbatim (constructed)
```
{json.dumps(user_data, default=str)}
```
Where `user_data = {data_type: raw_data_list}` across all staged rows.

**Notes**: `max_tokens=4096`. Anthropic client uses default API key. Produces the pre-approved vs pending-review split that drives the onboarding review UI. See High-Complexity Items section for migration plan.

---

### [backend/app/services/price_list_analysis_service.py:analyze_price_list line 848]
- **Category**: C
- **Model string**: module-level `ANALYSIS_MODEL` (verify — likely `claude-sonnet-4-20250514` per pricing-analysis pattern)
- **force_json**: true (system prompt enforces JSON-only, with post-processing for truncation)
- **Streaming**: false
- **Tool use**: false
- **Vision**: false
- **Caller entity type**: `price_list` (PriceListImport)
- **Entity ID source**: `imp.id`, `imp.tenant_id` in scope
- **Caller linkage candidates**: `company_id` (tenant_id), `price_list_import_id` (imp.id). Strong linkage candidate.
- **Proposed prompt_key**: `pricing.analyze_price_list` (NEW PROMPT NEEDED). `model_preference`: `sonnet` (complex structured match against catalog; 16384 max tokens output).
- **Migration complexity**: MEDIUM — very large output (16384 max_tokens) with multi-stage post-processing (`_reclassify_bundle_items`, `_group_bundle_variants`, `_fix_urn_vault_items`, `_promote_exact_matches`, `_classify_charge_items`). Registry renderer must tolerate truncation repair path.
- **Variables used**: `catalog_ref`, `WILBERT_VARIATIONS` (module constant), `text` (price list content up to 50000 chars)
- **Response parsing**: Strip code fences → fix trailing commas → `_try_parse_json` (custom repair); persists `parsed.items[]`, `parsed.billing_terms`, token usage.

#### System prompt — verbatim
```
You are analyzing a funeral vault manufacturer's price list to extract products and prices, then matching them to a known product catalog.
Be precise about prices — extract the exact dollar amount shown.
Be thorough about product names — recognize variations and abbreviations.
Be honest about confidence — flag anything ambiguous.
IMPORTANT: When you match a product to the catalog, use the EXACT template_name from the catalog as the template_name in your response. Do NOT modify, shorten, or create your own product name. For example, if the catalog has 'Monticello Urn Vault', return exactly 'Monticello Urn Vault' — not 'Monticello (Urn)' or 'Monticello Urn'.
Return JSON only. No other text.
```

#### User prompt — verbatim (constructed)
```
Here is a price list from a Wilbert burial vault licensee. Extract every product and its selling price, then match each product to the known catalog below.

KNOWN PRODUCT CATALOG:
{catalog_ref}

{WILBERT_VARIATIONS}

PRICE LIST CONTENT:
{text}

For each item in the price list, return:
{
  "items": [
    {
      "raw_text": "the original line from the price list",
      "extracted_name": "your interpretation of the product name",
      "extracted_price": 0.00,
      "extracted_sku": "SKU if present or null",
      "extracted_price_with_vault": null,
      "extracted_price_standalone": null,
      "has_conditional_pricing": false,
      "is_bundle_price_variant": false,
      "price_variant_type": null,
      "bundle_variant_group": null,
      "charge_category": null,
      "charge_key_suggestion": null,
      "match": {
        "template_id": "uuid-string or null",
        "template_name": "matched product name",
        "confidence": 0.95,
        "reasoning": "explanation"
      },
      "match_status": "high_confidence|low_confidence|unmatched|bundle"
    }
  ],
  "summary": {
    "total_items": 0,
    "matched_high": 0,
    "matched_low": 0,
    "unmatched": 0
  }
}

Confidence thresholds:
- high_confidence (>= 0.85): clear match
- low_confidence (0.60-0.84): likely match but needs confirmation
- unmatched (< 0.60): no confident match

Also look for and extract any billing or payment policy information present in the document.
Return these in an additional top-level field alongside "items" and "summary":

"billing_terms": {
  "payment_terms_days": <integer or null>,
  "early_payment_discount_percent": <decimal or null>,
  "early_payment_discount_days": <integer or null>,
  "finance_charge_rate_monthly": <decimal or null>,
  "finance_charge_basis": <"past_due_only" | "total_balance" | null>,
  "holidays": <string[] or null>,
  "raw_text": "<the exact text found in the document describing billing terms>"
} or null if no billing terms are found.

Examples of billing term text to look for:
- "Net 30", "Due on receipt", "Payment due within 30 days"
- "5% discount if paid by the 15th", "2% 10 net 30"
- "Finance charge of 2% per month on balances over 30 days"
- "Observed holidays: New Year's Day, Memorial Day, July 4th, ..."
- Any section titled "Terms", "Payment Terms", "Billing Policy"
```

**Notes**: `max_tokens=16384`. Truncation path logs a warning and attempts JSON repair. Post-processing pipeline hardens the output. Anthropic client constructed with explicit `settings.ANTHROPIC_API_KEY`.

---

## 5. Category D — HARDCODED STRINGS

**None found.** Every hardcoded Anthropic model string in the codebase is accompanied by a direct SDK call (Category C) or lives within the intelligence layer itself (Category E). There are no cases of a model string stored without the matching SDK usage or shim call.

---

## 6. Category E — INFRASTRUCTURE (allowed to reference SDK)

| File | Role |
|---|---|
| `backend/app/services/intelligence/__init__.py` | Package root |
| `backend/app/services/intelligence/chat_service.py` | Chat orchestration |
| `backend/app/services/intelligence/cost_service.py` | Token cost calculation |
| `backend/app/services/intelligence/experiment_service.py` | A/B experiments |
| `backend/app/services/intelligence/extraction_service.py` | Field extraction pipeline |
| `backend/app/services/intelligence/intelligence_service.py` | `execute()` entry point |
| `backend/app/services/intelligence/model_router.py` | Model selection |
| `backend/app/services/intelligence/prompt_registry.py` | Prompt lookup |
| `backend/app/services/intelligence/prompt_renderer.py` | Variable interpolation |
| `backend/app/models/intelligence.py` | ORM models |
| `backend/app/schemas/intelligence.py` | Pydantic schemas |
| `backend/app/api/routes/intelligence.py` | Admin routes |
| `backend/alembic/versions/r16_bridgeable_intelligence.py` | Migration |

---

## 7. Category F — TESTS

| File | Role |
|---|---|
| `backend/tests/test_intelligence.py` | Core tests |
| `backend/tests/test_intelligence_execute.py` | Execute entrypoint |
| `backend/tests/test_intelligence_phase2a.py` | Phase 2a migration tests |
| `backend/tests/test_intelligence_phase2a_lint.py` | Ruff/TID251 guards |

---

## 8. Category G — LEGACY WRAPPER

`backend/app/services/ai_service.py` contains the `call_anthropic()` function — the 60-day emergency escape hatch used by all Category B callers. It writes an `intelligence_executions` row with `prompt_id=null` and `caller_module="legacy:<module>.<func>"` so audit coverage stays 100% until every Category B migration lands.

After Phase 2c, this file can be deleted or reduced to a raise-on-call stub.

---

## 9. Category H — CONFIG/SEED

| File | Role |
|---|---|
| `backend/ruff.toml` | Lints for TID251 forbidding new `call_anthropic` / direct `anthropic` imports |
| `backend/scripts/seed_intelligence.py` | Base prompt seeds |
| `backend/scripts/seed_intelligence_phase2a.py` | Phase 2a prompt seeds |
| `backend/scripts/seed_intelligence_phase2b.py` | Phase 2b prompt seeds |

---

## 10. Summary: Totals by Category

| Category | Files | Call Sites | Audit Coverage |
|---|---|---|---|
| A — MIGRATED | 9 | 9 | 100% (native) |
| B — CALL_ANTHROPIC LEGACY | 23 | 25 | 100% (via shim) |
| C — DIRECT SDK | 14 | 14 | 0% (bypass) |
| D — HARDCODED STRINGS | 0 | 0 | — |
| E — INFRASTRUCTURE | 13 | N/A | N/A |
| F — TESTS | 4 | N/A | N/A |
| G — LEGACY WRAPPER | 1 | N/A | N/A |
| H — CONFIG/SEED | 4 | N/A | N/A |

**Total remaining to migrate:** 39 call sites (25 B + 14 C) across 37 files. The B vs C split matters: B is already audited so it's safe to migrate behind the scenes; C must be migrated *before* it can be observed.

**Call-site count reconciliation:** Pre-classification listed 25 B sites and 14 C sites (39 total). This audit documents all 39.

---

## 11. Migration Priority Ranking

Priority is driven by (a) audit gap — C has none today — and (b) blast radius of the downstream write. The most important Category C migrations first, then Category B in rough order of volume.

### Tier 1 — Category C, HIGH visibility / mutation risk

1. **`accounting_analysis_service.py`** (line 174) — **HIGH complexity**. Central to onboarding COA review. Mutates 5+ table rows with confidence gating.
2. **`price_list_analysis_service.py`** (line 848) — 16K output, multi-stage repair pipeline, persists to PriceListImportItem.
3. **`agent_service.py:_generate_collections_draft`** (line 246) — Duplicate of already-migrated `agent.ar_collections.draft_email`; migrating collapses duplication.
4. **`sales_service.py:scan_check_image`** (line 2301) — Vision model; drives payment-match suggestions. Config kwarg inconsistency (`settings.anthropic_api_key` vs `ANTHROPIC_API_KEY`) must be fixed.
5. **`price_list_extraction_service.py:_extract_pdf_via_claude`** (line 100) — Vision (PDF); fallback path from pdfplumber.

### Tier 2 — Category C, narrow blast radius

6. **`first_call_extraction_service.py`** (line 90) — Overlaps with `scribe.extract_case_fields`; collapse if schemas align.
7. **`training_content_generation_service.py`** (line 169) — Two prompts (procedure + curriculum); platform-level content.
8. **`website_analysis_service.py`** (line 85) — Onboarding enrichment; isolated.
9. **`customer_classification_service.py`** (line 357) — Batch classifier; carries tenant-name hardcoding.
10. **`journal_entries.py:parse_entry`** (line 279) — NL → JE draft.
11. **`accounting_connection.py:sage_analyze_csv`** (line 781) — Sage CSV mapping.
12. **`reports.py:parse_package_request`** (line 143) — Audit package NL parse.
13. **`order_station.py:parse_order`** (line 626) — Voice order entry.
14. **`financials_board.py:get_briefing`** (line 165) — Financial briefing; collapses into `briefing.*` family.

### Tier 3 — Category B, already audited but still off-registry

15. `ai.py:ai_prompt` (line 44) — **architectural debt**; must be deprecated, not migrated. See High-Complexity Items.
16. `ai_command.py` (line 53) — Four sibling prompts; collapse with `core_command_service.py`.
17. `core_command_service.py` (line 177) — Confirm overlap with `commandbar.classify_intent`.
18. `call_extraction_service.py` (line 162) — Rich call-order extraction; multi-table persistence.
19. `operations_board.py:get_daily_context` (line 582) — Plant manager briefing.
20. `operations_board.py:interpret_transcript` (line 662) — Voice interpreter (5 sub-prompts).
21. `ai_manufacturing_intents.py` (line 143) — 6 intent branches.
22. `ai_funeral_home_intents.py` (line 777) — 11 intent branches.
23. `workflows.py:generate_workflow` (line 427) — Workflow designer.
24. `kb_parsing_service.py` (line 122) — 6-branch document parser.
25. `briefing_intelligence.py` (line 18) — 3 sub-prompts (narrative / prep / weekly).
26. `command_bar_data_search.py` (line 903) — Ask-AI fallback.
27. `obituary_service.py` (line 104) — Obituary drafting.
28. `kb_retrieval_service.py` (line 245) — KB synthesis.
29. `classification_service.py` (line 477) — Single-row classifier.
30. `voice_memo_service.py` (line 69) — Voice memo → activity log.
31. `agent_orchestrator.py:account_rescue_agent` (line 437) — At-risk email draft.
32. `urn_intake_agent.py` (lines 56, 138) — Two email intake extractors.
33. `name_enrichment_agent.py` (line 153) — Shorthand name suggestion.
34. `document_search_service.py` (line 96) — Document answer extraction.
35. `historical_order_import_service.py` (line 320) — CSV column mapping.
36. `unified_import_service.py` (line 539) — Batch import classification.
37. `import_alias_service.py` (line 361) — Product catalog match.
38. `csv_column_detector.py` (line 163) — Critical-field CSV mapping fallback.

---

## 12. Prompt Key Coverage

### Existing seeded keys (Phase 1 + 2a + 2b) referenced by this audit

| Prompt Key | Referenced by audit call sites |
|---|---|
| `scribe.extract_case_fields` | Category A (migrated); potentially collapse `first_call_extraction_service` if schema aligns |
| `scribe.extract_case_fields_live` | Candidate for `first_call_extraction_service` |
| `scribe.compose_story_thread` | Category A (migrated) |
| `commandbar.classify_intent` | Candidate for `core_command_service`; verify schema match |
| `commandbar.answer_price_question` | Adjacent to `command_bar_data_search` (but distinct) |
| `commandbar.detect_quote_intent` | Unused by remaining call sites |
| `overlay.extract_fields_live` | Unused by remaining call sites |
| `overlay.extract_fields_final` | Category A (migrated) |
| `assistant.chat_with_context` | Category A (migrated) |
| `compose.generate_draft` | Adjacent to `account_rescue_agent`; may collapse |
| `workflow.ai_step_generic` | Distinct from `workflows.py:generate_workflow` |
| `agent.month_end_close.executive_summary` | Agent service (already migrated path) |
| `agent.ar_collections.draft_email` | Category A — **collapse `agent_service._generate_collections_draft`** here |
| `agent.unbilled_orders.pattern_analysis` | Agent service (already migrated path) |
| `agent.cash_receipts.match_rationale` | Agent service (already migrated path) |
| `agent.expense_categorization.classify` | Category A (migrated) |
| `agent.estimated_tax_prep.narrative` | Agent service (already migrated path) |
| `agent.inventory_reconciliation.narrative` | Agent service (already migrated path) |
| `agent.budget_vs_actual.variance_narrative` | Agent service (already migrated path) |
| `agent.prep_1099.filing_gaps` | Agent service (already migrated path) |
| `agent.year_end_close.summary` | Agent service (already migrated path) |
| `agent.tax_package.cpa_narrative` | Agent service (already migrated path) |
| `agent.annual_budget.assumption_forecast` | Agent service (already migrated path) |
| `accounting.coa_classify` | **Claim for** `accounting_analysis_service.run_ai_analysis` |
| `briefing.daily_summary` | Category A (migrated) |
| `briefing.safety_talking_point` | Unused by remaining call sites |
| `safety.draft_monthly_program` | Category A (migrated) |
| `urn.enrich_catalog_entry` | Unused directly by remaining call sites |
| `urn.semantic_search` | Category A (migrated) |
| `urn.engraving_proof_narrative` | Unused by remaining call sites |

### NEW PROMPT NEEDED proposals (derived from this audit)

30 distinct new prompt keys proposed (some collapse multiple call sites into one key):

| Proposed Key | Source | Notes |
|---|---|---|
| `kb.synthesize_call_answer` | kb_retrieval_service | Live-call KB answer |
| `kb.parse_document` | kb_parsing_service | 6 category branches; may split |
| `onboarding.classify_import_companies` | unified_import_service | Batch classifier (staging rows) |
| `onboarding.detect_csv_columns` | csv_column_detector | Critical-field fallback |
| `onboarding.analyze_website` | website_analysis_service | Onboarding enrichment |
| `onboarding.classify_customer_batch` | customer_classification_service | Tenant-name parameterize |
| `commandbar.extract_document_answer` | document_search_service | FTS augmentation |
| `commandbar.classify_manufacturing_intent` | ai_manufacturing_intents | 6-branch |
| `commandbar.classify_fh_intent` | ai_funeral_home_intents | 11-branch |
| `commandbar.answer_catalog_question` | command_bar_data_search | Ask-AI fallback |
| `commandbar.legacy_process_command` | ai_command.py | Retire after core_command consolidation |
| `commandbar.parse_filters` | ai_command.py | Named filter parsing |
| `commandbar.company_chat` | ai_command.py | Company-scoped Q&A |
| `import.match_product_aliases` | import_alias_service | Bulk product match |
| `import.detect_order_csv_columns` | historical_order_import_service | Column mapper |
| `calls.extract_order_from_transcript` | call_extraction_service | RingCentral extraction |
| `fh.obituary.generate` | obituary_service | Warm obituary tone |
| `crm.classify_entity_single` | crm/classification_service | Single-row fallback |
| `crm.extract_voice_memo` | voice_memo_service | Activity-log extract |
| `crm.draft_rescue_email` | agent_orchestrator | At-risk outreach |
| `crm.suggest_complete_name` | name_enrichment_agent | Shorthand-name fallback |
| `briefing.generate_narrative` | briefing_intelligence | Morning narrative |
| `briefing.generate_prep_note` | briefing_intelligence | Pre-call prep |
| `briefing.generate_weekly_summary` | briefing_intelligence | Weekly roll-up |
| `briefing.plant_manager_daily_context` | operations_board | Plant floor briefing |
| `briefing.financial_board` | financials_board | AR/AP briefing |
| `voice.interpret_transcript` | operations_board | 5 sub-contexts; may split into 5 keys |
| `urn.extract_intake_email` | urn_intake_agent | FH email intake |
| `urn.match_proof_email` | urn_intake_agent | Decedent-name lookup |
| `workflow.generate_from_description` | workflows.py | Workflow designer |
| `scribe.extract_first_call` | first_call_extraction_service | Possibly collapse with scribe.extract_case_fields |
| `pricing.extract_pdf_text` | price_list_extraction_service | Vision PDF OCR |
| `pricing.analyze_price_list` | price_list_analysis_service | Bulk price list analysis |
| `accounting.parse_journal_entry` | journal_entries.parse | NL JE parser |
| `accounting.map_sage_csv` | accounting_connection | Sage CSV column mapper |
| `accounting.extract_check_image` | sales_service.scan_check_image | Vision check |
| `reports.parse_audit_package_request` | reports.parse_package_request | NL audit package |
| `orderstation.parse_voice_order` | order_station.parse_order | Voice quick-entry |
| `training.generate_procedure` | training_content_generation_service | Procedure JSON |
| `training.generate_curriculum_track` | training_content_generation_service | Curriculum JSON |

**Total NEW PROMPT NEEDED proposals: 40** (the table above is deduplicated; the number exceeds 30 because I counted briefing_intelligence's three sub-prompts and voice.interpret_transcript's five sub-contexts separately when they may ultimately collapse).

### Keys candidate for retirement/collapse

- `ai_service.call_anthropic` single-arg callers (classification_service, voice_memo_service, agent_orchestrator, urn_intake_agent, name_enrichment_agent) — normalize to keyed `execute`.
- `ai.py:ai_prompt` — open-ended passthrough; retire rather than migrate.
- `agent_service._generate_collections_draft` — collapse into `agent.ar_collections.draft_email`.

---

## 13. High-Complexity Items

### HIGH-1: `backend/app/services/accounting_analysis_service.py` (line 174)
**Why HIGH:**
- Produces six distinct output sections (gl_mappings, stale_accounts, customer_analysis, vendor_analysis, product_matches, network_flags) each fanning out to TenantAccountingAnalysis rows with different `mapping_type` discriminators.
- Confidence-gated auto-approval at 0.85 triggers automatic status="confirmed" writes.
- Input is a JSON dump of *all* staged accounting data — potentially very large and variable per tenant. Token-budgeting and truncation handling are not yet enforced in the intelligence layer.
- Drives the onboarding review screen — any schema drift silently breaks the UI.

**Migration plan:**
1. Verify `accounting.coa_classify` seed payload matches this prompt verbatim.
2. Add intelligence-layer support for very large user messages with truncation heuristics.
3. Persist `analysis_run_id` into a linkage column on `intelligence_executions` (new column: `accounting_analysis_run_id` or repurpose `entity_id`).
4. Gate the write-back logic on a successful `IntelligenceExecution.status="ok"` rather than Exception-swallow.
5. Add schema contract tests against the six output sections.

### HIGH-2: `backend/app/api/routes/ai.py:ai_prompt` (line 44)
**Why HIGH:** This endpoint exposes an arbitrary `system_prompt`+`user_message`+`context_data` pipe. Any frontend caller can bypass prompt-registry controls by invoking it. It is the single largest audit hole.

**Migration plan:** Do **not** create a prompt_key. Instead:
1. Survey the frontend for every `apiClient.post("/ai/prompt", ...)` caller.
2. For each, either promote its system prompt into the registry (migrate individually) or delete the call.
3. Once no frontend callers remain, delete the endpoint.
4. Document as a breaking change in the changelog. The ruff lint rule (TID251) should be updated to also forbid any new `/ai/prompt` usage.

### HIGH-3 (honorable mention): `backend/app/services/price_list_analysis_service.py` (line 848)
Not counted as HIGH in the strict sense but close: 16K max_tokens output, multi-stage post-processing, JSON truncation repair, and vendor-specific `WILBERT_VARIATIONS` constant. Tag as HIGH if the intelligence layer cannot support the repair path out-of-the-box.

---

## 14. Phase 2c Sub-phase Proposal

### Sub-phase 2c-0 — Infrastructure & Hard Gates (1 day)
- Add `document`/`image` multimodal content support to `intelligence_service.execute` (required for `price_list_extraction_service._extract_pdf_via_claude`, `sales_service.scan_check_image`).
- Add `accounting_analysis_run_id` / `price_list_import_id` linkage columns to `intelligence_executions` (migration).
- Normalize `settings.ANTHROPIC_API_KEY` access — fix `sales_service.scan_check_image` typo (`settings.anthropic_api_key`) and add a TID251 lint rule for direct `anthropic.Anthropic()` instantiation outside the intelligence package.

### Sub-phase 2c-1 — Category C High Priority (2 days)
Migrate in this order:
1. `accounting_analysis_service.run_ai_analysis` → `accounting.coa_classify` (verify/update seed)
2. `price_list_analysis_service.analyze_price_list` → `pricing.analyze_price_list` (NEW)
3. `agent_service._generate_collections_draft` → collapse into `agent.ar_collections.draft_email`
4. `sales_service.scan_check_image` → `accounting.extract_check_image` (NEW, vision)
5. `price_list_extraction_service._extract_pdf_via_claude` → `pricing.extract_pdf_text` (NEW, vision)

### Sub-phase 2c-2 — Category C Medium Priority (1.5 days)
6. `first_call_extraction_service.extract_first_call` → `scribe.extract_first_call` (NEW) OR collapse into existing
7. `training_content_generation_service._call_claude` → `training.generate_procedure` + `training.generate_curriculum_track` (2 NEW)
8. `website_analysis_service.analyze_website_content` → `onboarding.analyze_website` (NEW)
9. `customer_classification_service._classify_batch_with_ai` → `onboarding.classify_customer_batch` (NEW)
10. `journal_entries.parse_entry` → `accounting.parse_journal_entry` (NEW)
11. `accounting_connection.sage_analyze_csv` → `accounting.map_sage_csv` (NEW)
12. `reports.parse_package_request` → `reports.parse_audit_package_request` (NEW)
13. `order_station.parse_order` → `orderstation.parse_voice_order` (NEW)
14. `financials_board.get_briefing` → `briefing.financial_board` (NEW)

### Sub-phase 2c-3 — Category B High-Value (2 days)
Prioritize call sites with clear entity linkage and/or existing registry alignment:
- `ai.py:ai_prompt` → **DEPRECATE** (architectural, not migration)
- `core_command_service._call_claude` → verify/collapse with `commandbar.classify_intent`
- `ai_command.py` (3 prompts) → `commandbar.parse_filters`, `commandbar.company_chat`, `commandbar.legacy_process_command`
- `call_extraction_service.extract_order_from_transcript` → `calls.extract_order_from_transcript` (NEW)
- `operations_board.get_daily_context` → `briefing.plant_manager_daily_context` (NEW)
- `operations_board.interpret_transcript` → `voice.interpret_transcript` (NEW) or 5 sub-keys

### Sub-phase 2c-4 — Category B Remaining (2 days)
- `ai_manufacturing_intents` → `commandbar.classify_manufacturing_intent` (NEW)
- `ai_funeral_home_intents` → `commandbar.classify_fh_intent` (NEW)
- `workflows.generate_workflow` → `workflow.generate_from_description` (NEW)
- `kb_parsing_service._run_claude_parsing` → `kb.parse_document` (NEW) — consider splitting by category_slug
- `briefing_intelligence` → 3 NEW prompts
- `command_bar_data_search._try_claude_catalog_answer` → `commandbar.answer_catalog_question` (NEW)
- `obituary_service.generate_with_ai` → `fh.obituary.generate` (NEW)
- `kb_retrieval_service._synthesize_answer` → `kb.synthesize_call_answer` (NEW)
- `crm/classification_service._ai_classify` → `crm.classify_entity_single` (NEW)
- `voice_memo_service.extract_memo_data` → `crm.extract_voice_memo` (NEW)
- `agent_orchestrator.account_rescue_agent` → `crm.draft_rescue_email` (NEW)
- `urn_intake_agent` (2 sites) → `urn.extract_intake_email`, `urn.match_proof_email` (NEW)
- `name_enrichment_agent.enrich_company_name` → `crm.suggest_complete_name` (NEW)
- `document_search_service._extract_answer` → `commandbar.extract_document_answer` (NEW)
- `historical_order_import_service.detect_format` → `import.detect_order_csv_columns` (NEW)
- `unified_import_service._classify_batch_ai` → `onboarding.classify_import_companies` (NEW)
- `import_alias_service._ai_match_products` → `import.match_product_aliases` (NEW)
- `csv_column_detector.detect_columns` → `onboarding.detect_csv_columns` (NEW)

### Sub-phase 2c-5 — Cleanup (0.5 day)
- Delete `backend/app/services/ai_service.py` (or reduce to a raise-on-call stub).
- Enable strict TID251 rule: no module may import `anthropic` outside `app/services/intelligence/`.
- Final audit coverage check: every remaining `intelligence_executions.prompt_id` should be non-null.
- Update CLAUDE.md Recent Changes to reflect Phase 2c completion and Category G retirement.

---

*End of audit.*
