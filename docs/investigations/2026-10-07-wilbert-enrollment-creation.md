# How a `wilbert_program_enrollments` row is created — report only

**2026-10-07.** Read-only. Nothing written. Answers the separate question in the
typed-capture slice-1 dispatch.

## There is exactly one writer

`WilbertProgramService.enroll_in_program` — `app/services/wilbert_program_service.py:140`,
constructing the row at `:202-220`. No seeder inserts one; no migration inserts one.
Measured: zero `INSERT INTO wilbert_program_enrollments` anywhere in `app/`, `scripts/`
or `alembic/`.

## Three callers, all tenant-authenticated

| caller | shape |
|---|---|
| `POST /api/v1/programs/{code}/enroll` — `app/api/routes/programs.py:129-153` | an admin action; `get_current_user` + `get_current_company` |
| `POST` onboarding step — `app/api/routes/onboarding_flow.py:304-318` | *"Enroll in Wilbert programs"*, loops over a list |
| `wilbert_program_service.py:399` | internal, same service |

⚠️ **It is NOT an onboarding CHECKLIST item.** `onboarding_service.py` has zero
references to Wilbert enrollment, so it does not appear in
`MANUFACTURING_CHECKLIST_ITEMS` and nothing gates completion on it. The onboarding
*flow* route exists; the checklist does not know about it.

## What enrolling Sunnycrest on production would write

One `wilbert_program_enrollments` row: `company_id`, `program_code`, `program_name`
(from the program definition), `is_active=True`, plus the territory and product
selections the caller supplies.

⚠️ **`personalization_config` would be NULL.** It is an optional parameter defaulting
to `None` (`wilbert_program_service.py:149`) and is passed straight through (`:213`).
Nothing computes a default.

## Does r201's mapping apply automatically on enrollment?

**No. Only to rows that existed when it ran.**

r201 selects `WHERE personalization_config IS NOT NULL`
(`r201_personalization_availability_data.py:104`). A new enrollment has
`personalization_config = NULL`, so it is not selected — and even without that filter,
a migration runs once and does not re-run for rows created later.

**So enrolling Sunnycrest today would produce an enrollment with no availability, and
capture would read NOT_CONFIGURED for every vault** — the question asked with an empty
permitted set on every order. That is the ruling working as designed and is almost
certainly not what anyone wants on the day Sunnycrest goes live.

## Three ways to close it — proposed, not built

1. **Seed availability at enrollment time.** `enroll_in_program` computes the default
   `availability` and stores it when the caller supplies none. Smallest change, and it
   puts the mapping in the one place enrollments are created. ⚠️ Cost: the mapping then
   lives in a service as well as in r201 and the seed script — a third copy, and
   `test_r201_availability_data.py` currently guards only two.
2. **Make availability platform-level with a tenant override**, read through a resolver
   the way `platform_themes` and `component_configurations` already do
   (`platform_default → vertical_default → tenant_override`, resolved at READ time).
   ⚠️ Largest change and the only one that makes a new licensee correct on day one
   without anyone running anything. It also removes the "copy per enrollment" problem
   rather than adding to it, and it matches an inheritance pattern this codebase already
   uses five times.
3. **A post-enrollment idempotent step** — the existing
   `scripts/seed_personalization_availability.py` with its production refusal lifted,
   run deliberately after enrolling. ⚠️ Smallest code change and the worst shape: it is
   a one-time human act with no artifact, which is the *provisioning corollary* failure
   CLAUDE.md §11 names — the thing that is missing after the next environment reset and
   surfaces incidentally.

**My recommendation is (2)**, and the reason is the one r201 already exposed: a mapping
copied per enrollment is a mapping that drifts per enrollment, and this codebase already
has a read-time three-scope resolver for exactly this shape. (1) is the right answer only
if availability is genuinely per-licensee data rather than a platform default a licensee
narrows.

⚠️ **Whichever is chosen, it is a decision about where the catalog's truth lives, not a
migration.** Nothing here should be built from this report without a ruling.
