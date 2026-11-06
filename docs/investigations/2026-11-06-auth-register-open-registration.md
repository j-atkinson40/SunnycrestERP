# `POST /auth/register` lets a stranger create an account in an existing tenant

**2026-11-06. Read-only investigation. Production reachability confirmed; no
production user was created.**

James's hypothesis, raised after the area-guard sweep found `/auth/register`
admitted by the old `/auth` prefix and named by no stated reason:

> Earlier we learned that `get_current_company` only reads the X-Company-Slug
> header, so it proves nothing about who's calling. When we swept for endpoints
> that need no sign-in, register was excluded by name on the assumption it was
> the sign-up page for new companies. If it actually adds a user to an
> *existing* company like Sunnycrest, anyone on the internet could create
> themselves an account there.

**It is true.** The assumption that excluded it was wrong: new-company signup is
a *different endpoint*.

## 1. What it creates

A user **inside an existing company, chosen by the request header.** Not a new
company.

`backend/app/api/routes/auth.py:38-48`:

```python
@router.post("/register", status_code=201)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    user = register_user(db, data, company)
```

No `get_current_user`. No `require_admin`. No invite token. The only dependency
beyond the database is `get_current_company`.

`backend/app/api/company_resolver.py:30-57` — what that dependency actually
does:

```python
def get_current_company(slug: str = Depends(get_company_slug), ...) -> Company:
    """Resolve the company from the slug. Raises 404 if not found or inactive."""
```

and `get_company_slug` (`:8-27`) reads `X-Company-Slug`, falling back to the
subdomain. **It is a lookup, not a check.** It answers "does this tenant
exist", never "may you act on it". It also cannot create a company — it 404s
when the slug does not resolve — so the new-company reading is excluded by the
code itself.

`backend/app/services/auth_service.py::register_user` — its own docstring is
the finding:

```python
def register_user(db: Session, data: RegisterRequest, company: Company) -> User:
    """Register a user within an existing company."""
```

⚠️ **AND THE CONTRAST IS THE PROOF THAT THE TWO WERE CONFUSED.** New-company
signup is `POST /api/v1/companies/register`, a separate route whose only
dependency is `get_db`, reached by `frontend/src/pages/company-register.tsx`.
`/auth/register` is reached by `frontend/src/pages/register.tsx`. Two pages,
two endpoints, and the sweep credited one with the other's purpose.

## 2. What the registered user gets

| | |
|---|---|
| role | **`admin` if the company has ZERO users, else `employee`** |
| password | the one they supplied, hashed — no verification step |
| `is_active` | **`True`** (column default; nothing sets it otherwise) |
| invite token | none |
| admin approval | none |
| email verification | none |
| `RegisterRequest` fields | `email`, `password`, `first_name`, `last_name` — four strings |

**They can sign in immediately.** No role field is accepted, so self-assigning
admin directly is not possible — but the zero-user branch grants it.

⚠️ **`employee` HAS NO PERMISSIONS AND NO AREA LIMIT, AND THE SECOND HALF IS
WHAT MATTERS.** `EMPLOYEE_DEFAULT_PERMISSIONS` is `[]`
(`role_service.py:48`), so every `require_permission` endpoint refuses them.
But the role declares no `limited_to_areas`, so it is **NULL** — and
`enforce_area_limit` early-returns on a NULL limit. The area guard does not
confine them at all.

So the reach is: the common set, plus every endpoint gated only by
`get_current_user`. Measured on the live app: **1,027 of 1,934 method+path
pairs under `/api/v1` declare neither `require_admin` nor
`require_permission`.** That is an upper bound — some check inside the handler
— and CLAUDE.md §4 records 886 of 1,063 as having no handler check either.

Directly measured on dev with such an account (6 endpoints, so a sample and
reported as one): `/auth/me` 200, `/locations/users` 200, `/locations` 200,
`/notifications` 200, `/customers` 403, `/products` 403.

## 3. Reachable on production with no `Authorization` header: yes

⚠️ **NO PRODUCTION USER WAS CREATED.** The probe body is deliberately invalid
(`email` is not an email), so Pydantic rejects it before `register_user` is
entered — no duplicate check, no `db.add`, no commit. A 422 means the request
passed every dependency and reached body validation; authentication would have
answered 401 regardless of the body.

    1. valid slug + INVALID body, no auth  -> 422  value is not a valid email address
    2. NO slug      + INVALID body, no auth -> 404  "Company not found."
    3. BOGUS slug   + INVALID body, no auth -> 404  "Company 'no-such-tenant-xyz' not found"

422 on (1) is the finding: the only thing between a stranger and
`register_user` is a well-formed body, and a well-formed body is four strings.
404 on (2) and (3) shows the tenant is selected by the header. **A 401 anywhere
would have falsified this.**

### And the full mechanism, demonstrated end to end on dev

Against local `bridgeable_dev` through `TestClient` — the real app, the real
dependency tree, **no `Authorization` header on any request**:

    testco users before: 14
    POST /auth/register with NO auth -> 201
      created user role='employee' is_active=True
    testco users after: 15  (delta 1)
    POST /auth/login as that account -> 200
      got an access token: True

The dev user was deleted afterwards; `stranger-%@example.com` count back to 0.

## 4. Who calls it

- `frontend/src/services/auth-service.ts:21` → `apiClient.post("/auth/register")`
- `frontend/src/pages/register.tsx`, routed at **`App.tsx:590`** as
  `<Route path="register" element={<RegisterPage />} />` — sitting beside
  `login` in the **public** part of the tenant tree, outside `ProtectedRoute`.

⚠️ **SO THIS IS NOT ONLY AN API PROPERTY. There is a live public page at
`{slug}.getbridgeable.com/register`.**

- `register_user` has exactly **one** call site, the route above (AST sweep over
  `app/` and `scripts/`, not grep).
- No seed and no script calls it. Three tests reference it, all of them
  asserting about it rather than using it — including
  `test_service_territories_requires_login.py:186`, which is the sweep that
  **excluded it by name**.

## 5. How many production users came through it

**No positive evidence of any, and the signature is weak.** `register_user`
sets no `created_by`, so NULL `created_by` plus a password is the best
available marker — and seeds create users the same way, so the marker does not
discriminate.

    users with created_by IS NULL and a password: 18
      by role: driver 5, admin 4, office_staff 2, director 2,
               production 2, office 1, accountant 1, dispatcher 1
    users on sunnycrest with created_by IS NULL: 1

⚠️ **Register can only ever assign `admin` (zero-user branch) or `employee`, and
ZERO of the 18 hold `employee`.** So nothing here looks like a non-first-user
registration. The 4 `admin` rows are **indistinguishable** between the
first-user branch and ordinary seed creation; I cannot separate them from this
data and am not going to claim I can.

## Production exposure today

    active companies (each a target via the header)                     4
    ...with users AND an 'employee' system role -> stranger = employee  4
    ACTIVE companies with ZERO users -> stranger = ADMIN                0
    sunnycrest 'employee' role limited_to_areas                      None
    sunnycrest users                                                    2

**All four live tenants are reachable.** The admin branch is **not** currently
reachable — but it is one deleted-last-user away, and nothing in the code
treats that transition as dangerous.

## Proposed fix (James's shape, not yet built)

> registration into an existing company requires an invite token (the Payroll 2
> invite flow) or an admin. New-company signup, if it's a real feature, stays
> open but can't target an existing slug. Break test fails first, then passes.

Notes for whoever builds it:

- The invite flow already exists and already does this correctly —
  `tenant_invite.invite_user` + `POST /invites/{token}/accept`. The honest fix
  may be to **delete** `POST /auth/register` and the page at `/register`
  rather than gate it, since the capability is fully served elsewhere. An
  absent endpoint is not a hole with a guard on it.
- ⚠️ **Check `POST /companies/register` separately before assuming it is fine.**
  It takes `get_db` alone. It was not investigated here and no claim is made
  about it. "The other one is the safe one" is exactly the assumption that
  produced this finding.
- The zero-user admin branch deserves its own decision even if registration is
  otherwise closed.
