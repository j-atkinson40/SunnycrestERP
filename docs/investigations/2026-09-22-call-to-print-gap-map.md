# Call-to-print gap map

**2026-09-22.** Read-only. No code changed. Every count and status below was derived this
session; nothing is inherited from the dispatch, which says so of itself.

⚠️ **The prototype file is not in the repo.** `docs/prototypes/` does not exist and no
`bridgeable-demo.html` is anywhere on this machine. The map is built from the dispatch's
feature list, as it instructed. Nothing here cites the prototype as a source.

---

## The two the dispatch said to watch — both answered, in opposite directions

**The Legacy engine is IN THIS REPO, and it is much further along than "an engine James
built."** Eight services (`legacy_compositor`, `legacy_delivery`, `legacy_email_service`,
`legacy_print_service`, `legacy_r2_client`, `legacy_service`, `legacy_templates`,
`legacy_watermark`), four route modules, four models, and a canvas editor. It already has
the licensed-background catalog, server-side PIL compositing, the watermark, the proof
email, the print email, the Dropbox upload, and — verbatim — the filename template the
prototype drew: `legacy_settings.tif_filename_template` defaults to
`'{print_name} - {name}.tif'`. The Legacy arc does not change shape. It gets smaller.

**The required-field schema does NOT exist, and the demo's best moment rests on nothing.**
The missing-field flag is real in the sense that `missing_fields` is captured and
persisted — but it is produced by the model, not by the system. The seeded prompt
`calls.extract_order_from_transcript` asks for:

> `"missing_fields": [ "list of field names that were NOT mentioned and are needed for a complete order" ]`

`call_extraction_service.py:157` then stores `result.get("missing_fields", [])`. **The model
decides what an order needs.** There is no server-side required-field set per order type to
check it against, so the flag cannot be trusted to fire, cannot be trusted not to fire
spuriously, and cannot be tested. ⚠️ **STOP — this is a feature that depends on data the
model does not hold.**

For contrast, a required-field schema *does* exist one surface over:
`nl_creation/types.py:232` gives each entity config a `required_fields` list, and
`extractor.py:260` computes the missing set from it. That is the shape the call overlay
needs and does not have.

---

## A. The note

⚠️ **The note is far more built than its own header comment says.** `/home` has served the
note since session 5 (2026-09-10, `App.tsx:608`) and `HomePage` is deleted.
`backend/app/services/note/` holds `composition`, `counts`, `deferral`, `registry`,
`service`, `settling`, `settling_sweep`, `spans`, `types`.

| feature | status | evidence |
|---|---|---|
| Prose composed, typed fragments | **EXISTS** | `services/note/composition.py`; `routes/note.py` returns `prose[]` with `fragment_id` |
| Text states carried structurally | **EXISTS** | `services/note/spans.py`; `routes/note.py` — *"SPANS, NOT A STRING… so the renderer never has to find a substring"* |
| Grouped by kind, worst-first | **MISSING** | no grouping or ordering-by-severity in `composition.py`; fragments are ordered, not grouped |
| Link treatment (entities only, underline, no colour) | **PARTIAL** | the span model can express it; the ruling landed today. Not verified as rendered |
| Standing set | **EXISTS** | `models/standing_set_config.py`, `render_standing_set`, `NotePage.tsx` §"Standing set" |
| Standing line opens its Focus | **MISSING (ruled, not built)** | `routes/note.py:114` — `"openable": False`, with the ruling in the comment |
| Counts neutral, never zero | **EXISTS** | `counts.py` — *"of DISTINCT SUBJECTS, never of raw rows"*; `count: number \| null`, `count_state: absent\|ok\|unavailable` |
| Today's Activity region | **MISSING** | no `Today's Activity`, `activity_counts` or `work_log` anywhere under the note |
| Deferral on prompts | **EXISTS** | `services/note/deferral.py`, `NoteFragmentDeferral`; payload carries `deferrable`, `deferred_until`, `deferred_until_label`, `deferred_count` |
| Settled phase | **EXISTS** | `settling.py`, `settling_sweep.py`, `settled_at` |
| Live shortening of a part-completed line | **MISSING** | no re-render-on-change path found; composition is per-request |

⚠️ **A stale comment I walked past one commit ago.** `NotePage.tsx:9` still reads *"What
this renders: the standing set, and an empty prose region."* The file is 450 lines and
renders prose spans, deferral controls and count states. I corrected the bullet three lines
below it in `84d5644c` and did not notice the summary above it was also wrong. Same file,
same read, same commit.

---

## B. Call overlay

| feature | status | evidence |
|---|---|---|
| Inbound call model + webhook | **EXISTS** | `models/ringcentral_call_log.py`, `routes/ringcentral.py:88` `/webhook`, `:543` `/events` (SSE) |
| Transcription | **EXISTS** | `services/transcription_service.py` |
| Extraction from transcript | **EXISTS** | `call_extraction_service.extract_order_from_transcript`, `models/ringcentral_call_extraction.py` |
| Captured / needed counts | **PARTIAL** | `missing_fields` JSONB is persisted; see the STOP above for what produces it |
| **Missing-field flag during the live call** | **MISSING** | no required-field schema per order type; and extraction runs after-call (`after_call_service.py`), not during |
| Panel anchored over the note | **MISSING** | `contexts/call-context.tsx` exists; no overlay component on the note surface |
| `cemetery_equipment` as a capturable field | **EXISTS as a concept** | 4 files reference it; not established as part of any required set |

⚠️ **STOP — RingCentral is still half-provisioned, and the repo says so in its own words.**
`services/ringcentral_oauth_state.py:60`: *"No authorize endpoint exists yet (S-3a
established the entrance is half-built: no authorize route, no frontend authorize URL, and
the 'Connect RingCentral' [button]…)"*. Route enumeration confirms it: `/webhook`,
`/events`, `/oauth/callback` — **no authorize route**. State-nonce minting and the callback
both exist; the door a tenant walks through does not.

**Measured on production, 2026-09-22 09:1x ET, presence only, no values printed:**
`RINGCENTRAL_CLIENT_ID` **SET**, `RINGCENTRAL_CLIENT_SECRET` **SET**. So the app is
registered with RingCentral; what is missing is the per-tenant grant and the route that
starts it.

---

## C. Summary to sales order

| feature | status | evidence |
|---|---|---|
| Draft order from extraction | **EXISTS** | `call_extraction_service.create_draft_order_from_extraction:211`; `routes/urn_sales.py:368` `create_order_from_extraction` |
| Backend order creation | **EXISTS** | `sales_service.create_sales_order:537`, `routes/sales.py:428` |
| Editable summary panel with notes | **MISSING** | no such component |
| **Frontend `createSalesOrder` has a caller** | **MISSING — confirmed** | `services/sales-service.ts:104` defines it; a whole-tree search for the identifier returns **that definition and nothing else** |

That last row is the "complete machinery behind an unprovisioned entrance" shape from
CLAUDE.md §11, one instance further on. The method exists, is correct, and is dead.

---

## D. Manufacturing scheduling focus

**The delivery model is the strongest part of this map.** Field names read off
`models/delivery.py` rather than guessed:

| prototype card field | model | status |
|---|---|---|
| deliver-to | `delivery_address` | EXISTS |
| location | `delivery_lat`, `delivery_lng`, `origin_location_id` | EXISTS |
| time | `required_window_start/end`, `scheduled_at`, `driver_start_time` | EXISTS |
| ETA | `delivery_stop.estimated_arrival` | EXISTS |
| firm | `customer_id` → `customers` | EXISTS (not `funeral_home_id` — checked) |
| family name | — | **MISSING on delivery**; reachable via `order_id` → sales order → case |
| place (church / graveside / FH / drop) | `delivery_type`, `type_config` JSONB, `delivery_type_definition` | **PARTIAL** — `graveside` appears in 10 files; no `place_of_service` field |
| equipment | `type_config` / `cemetery_equipment` | **PARTIAL** |
| product | via order lines | EXISTS indirectly |

| feature | status | evidence |
|---|---|---|
| Driver kanban core | **EXISTS** | `components/dispatch/scheduling-focus/SchedulingKanbanCore.tsx` |
| Core-plus-accessories Focus | **EXISTS** | `SchedulingFocusWithAccessories.tsx`, `ComposedFocus.tsx`, `CompositionRenderer.tsx`, `focus_compositions` |
| Ancillary stops as a record type | **EXISTS** | `delivery.ancillary_fulfillment_status`, `ancillary_is_floating`, `ancillary_soft_target_date`, `attached_to_delivery_id` |
| Graveside rule (ETA = service time) | **MISSING** | business rule not expressed anywhere |
| **Time off for the day** | **MISSING** | ⚠️ see the substring note below |
| **Drive time / distance / verdict** | **MISSING** | no maps or routing API of any kind |
| Background click closes the Focus | **PARTIAL** | Focus close exists; not verified for this surface |
| Vertical gating on Focus registration | **NONE FOUND** | `focus_session_service` keys on `focus_type` only; no vertical predicate |

⚠️ **A false presence caught by checking.** `pto` matched 55 files, which would have read
as "time off partly exists." Sampling the matches returns `descriptor` (61), `crypto` (27),
`ActionTypeDescriptor` (36), `cryptography` (12). **Pure substring noise.** `time_off`,
`TimeOff`, `timeoff`, `vacation` and `days_off` are all **0**, and the 19 `availability`
hits are urn, vault and intake code. Time off does not exist.

⚠️ **STOP — the two-run route card depends on an external service that is not chosen.**
`mapbox`, `google_maps`, `distancematrix`, `osrm`, `drive_time`, `travel_time` are all **0**
across backend and frontend. `haversine` appears twice, so straight-line distance exists —
which is not drive time, and the prototype's verdict ("tight", "needs two drivers") is a
drive-time claim.

---

## E. Comms panel

| feature | status | evidence |
|---|---|---|
| Generic thread / chat primitive | **MISSING** | `comms_panel`, `CommsPanel`, `chat_message`, `message_thread` all 0. `admin/chat.py` is a platform-admin surface, not a tenant primitive |
| Email thread primitive | **EXISTS** | `services/email/inbox_service.py` — `ThreadSummary`, `ThreadDetail`; `routes/email_inbox.py` |
| Inbound email parsing | **EXISTS** | `services/email/providers/` — `gmail`, `imap`, `msgraph`; `models/email_primitive.py` |
| Scoped-to-permission display | **MISSING** | no per-thread audience statement |

So instance 2 (print-shop email thread, outbound **and** replies) has a substrate; instance
1 (dispatcher-only chat) has none. The panel is one primitive per the ruling, so the chat
case is what sets the cost.

---

## F. Legacy focus

| feature | status | evidence |
|---|---|---|
| Licensed background catalog | **EXISTS** | `models/program_legacy_print.py` — Wilbert standard + tenant custom, per-print enable and price, `file_url`, `thumbnail_url` |
| Custom background upload + processing | **EXISTS** | `routes/legacy.py:135`, `legacy_compositor.process_custom_background`, `apply_oval_fade` |
| Server-side compositing | **EXISTS** | `legacy_compositor.composite_layout:112` — PIL, background + photo layers + text layer |
| Watermarked proof | **EXISTS** | `legacy_watermark.py`; `legacy_settings.watermark_*` |
| Canvas editor, draggable layers | **PARTIAL** | `components/legacy/LegacyCompositor.tsx` (552 lines) — multiple photo layers, drag, scale, opacity, **centre-anchored** (`cw*photo.x - pw/2`), plus mobile variant |
| Name and dates as separate layers | **MISSING** | one `textLayer`, not separate |
| **Emblems as a layer type** | **MISSING** | no emblem in the compositor; emblems exist in `workshop`, `monument_catalog`, `personalization_config` — a different surface |
| **Emblem library card, drag onto panel** | **MISSING** | — |
| **Snapping to centre / other layers, with guides** | **MISSING** | 0 files matching `snap` under the studio or legacy components |
| Send proof to funeral home | **EXISTS** | `legacy_email_service`, `legacy_email_settings.proof_email_subject/body/reply_to` |
| Approve | **EXISTS** | `routes/legacy_studio.py:236` `/approve`; `:281` `/revise`; `:377` `/versions` |
| Save `"{Background} - {Deceased name}.tif"` | **EXISTS** | `legacy_settings.tif_filename_template` default `'{print_name} - {name}.tif'` |
| Dropbox upload to configured folder | **EXISTS (code)** | `legacy_delivery.dropbox_upload_tif:117`, folder from `dropbox_target_folder`, default `/Bridgeable Legacies` |
| Email the print shop | **EXISTS** | `legacy_email_settings.print_email_subject` default `'Legacy Ready — {name}, needed by {deadline}'` |
| Approved state (locked panel, order, thread) | **PARTIAL** | `legacy_proofs.approved_layout` JSONB stores the locked layout; no thread on the surface |

⚠️ **STOP — Dropbox is not provisioned on production.** Measured 2026-09-22, presence only:
`DROPBOX_APP_KEY` **ABSENT**, `DROPBOX_APP_SECRET` **ABSENT**. The OAuth authorize URL,
the callback, the token exchange and the upload are all written
(`legacy_delivery.py:85-160`), and none of it can run. The variables are also **absent from
`backend/.env.example`**, so nothing documents that they are needed. `RESEND_API_KEY` is
**SET**, so the email half works today.

---

## G. Cross-cutting

| question | answer |
|---|---|
| Does the Focus layer support context cards around a core? | **YES.** `ComposedFocus`, `CompositionRenderer`, `FocusContextBridge`, `useResolvedComposition`, and `focus_compositions` with the three-scope inheritance. `SchedulingFocusWithAccessories` is the shipped instance |
| Where does Clock In live? | An **ops-board widget**, `widget_id: "time_clock"`, **extension-gated** on `required_extension: "time_clock"` (`services/widgets/widget_registry.py:165`), rendered by `components/widgets/ops-board/TimeClockWidget.tsx`. It is not on the note and is not in the standing set — which is where it should stay: it is an action, and the standing set admits only what is checked against something in the user's hand |

---

## External dependencies, in one list

| dependency | needed for | code | production credential | state |
|---|---|---|---|---|
| **RingCentral** | inbound call, transcript, extraction | webhook, SSE, callback, state nonce all written | `RINGCENTRAL_CLIENT_ID` **SET**, `_SECRET` **SET** | ⚠️ **half-provisioned** — no authorize route, no frontend authorize URL, no per-tenant grant |
| **Dropbox** | `.tif` to the print folder | OAuth + upload + shared link all written | `DROPBOX_APP_KEY` **ABSENT**, `_SECRET` **ABSENT** | ⚠️ **not provisioned**, and undocumented in `.env.example` |
| **Maps / routing** | drive time, distance, fit verdict | **none** | — | ⚠️ **not chosen** |
| **Resend** (email out) | proof email, print-shop email | `legacy_email_service`, `legacy_email_settings` | `RESEND_API_KEY` **SET** | provisioned |
| **Email in** (Gmail / IMAP / MS Graph) | print-shop replies | three providers written | per-tenant OAuth, not checked here | provider code exists; per-tenant grant not established |
| **Anthropic** | extraction, note composition | in use | `ANTHROPIC_API_KEY` **SET** | provisioned |

Presence read 2026-09-22 via `railway run … --environment production`, printing only
whether each variable is non-empty. No value entered or left a session.

---

## Proposed arc order — named, not decided

Dependencies stated; sequencing is James's.

1. **Required-field schema per order type.** Nothing in B or C is testable without it, and
   it is the demo's best moment. It has a worked precedent in `nl_creation` to copy. No
   external dependency. **Blocks: B, C.**
2. **Legacy finish.** Emblems as a layer type, the emblem library, snapping, name and dates
   as separate layers. Everything else in F exists. **Blocks: nothing. Blocked by: Dropbox
   provisioning, for the print half only — the proof half ships without it.**
3. **The note's remaining three.** Grouping worst-first, Today's Activity, live shortening.
   Self-contained. **Blocked by: nothing.**
4. **Standing line opens its Focus.** Ruled today, one flag and a target. **Blocked by:**
   the Focus targets existing.
5. **RingCentral authorize route.** Small, and it unblocks every runtime check of B.
   **Blocks: all live validation of B.**
6. **Call overlay + summary panel.** **Blocked by: 1 and 5.**
7. **Manufacturing scheduling Focus.** Reuses the kanban core and the accessory layer.
   Needs the graveside rule, a time-off model, and family-name reach-through. **Blocked by:
   nothing external.**
8. **Route card.** **Blocked by: choosing a maps provider.**
9. **Comms panel.** Email instance has a substrate; the dispatcher-chat instance does not.
   **Blocked by: a decision on whether chat is a new primitive or a degenerate thread.**

---

## Method notes

- Every name was enumerated in its forms before searching — `legacy` in three cases,
  `pto`/`time_off`/`vacation`/`days_off` for time off, nine forms for the maps providers,
  eight for a thread primitive.
- Two results that were **too clean** were re-derived: `pto` at 55 files (substring noise,
  disproved by sampling the matched tokens) and `createSalesOrder` at one hit (confirmed by
  searching the identifier across the whole frontend rather than one directory).
- Production was read only for credential **presence**. No value was printed, requested or
  written.
- ⚠️ Not established here: whether any tenant has ever completed a Legacy print end to
  end, and whether the RingCentral webhook has ever fired in production. Both are
  row-count questions against production and were out of this dispatch's read scope.
