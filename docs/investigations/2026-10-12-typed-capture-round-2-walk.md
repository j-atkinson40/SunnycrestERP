# Walking typed capture, round 2 — dev and production

For James. Written 2026-10-12, after the four commits listed at the end.

---

## ⚠️ READ THIS FIRST: the backend on your machine is running OLD CODE

Your `localhost:8000` backend was started before this work and has not picked it
up. I checked rather than assumed: `PUT /api/v1/capture/sessions/x/text` returned
`{"detail":"Not Found"}`, which is FastAPI's generic route-miss — not the
handler's own "capture session not found". The route is not registered in that
process.

**So step 1 is a restart, and without it every step below fails in a way that
looks like the feature not working.** I verified everything in this document
against a second uvicorn I started on port 8001 and then stopped; I did not touch
your process.

---

## Dev

### 1. Restart the backend

In the terminal where it is running, stop it and start it again:

```
cd ~/Projects/SunnycrestERP/backend
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev .venv/bin/uvicorn app.main:app --reload --port 8000
```

`--reload` means you will not have to do this again.

### 2. Apply the migration

One new migration, `r208_capture_session_text`. Already applied to your dev
database by me — this is here so you can confirm:

```
cd ~/Projects/SunnycrestERP/backend
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev .venv/bin/alembic current
```

Expect `r208_capture_session_text (head)`.

### 3. Hard-refresh the browser

`Cmd+Shift+R` on `http://localhost:5173/?slug=testco`. The frontend bundle
changed; a tab left open from before will show the old pane and no error.

Log in as `admin@testco.com`. The password is in
`backend/scripts/seed_staging.py` — I have deliberately not written it here.

### 4. Open Opas and start an order

Click the sphere, bottom right. Type:

```
start an order
```

and press Enter.

**What to look for:** the pane appears at the BOTTOM RIGHT, directly above the
command bar, and unfolds from its corner rather than fading in at the top. That
is the "entry panes grow from the bar" ruling. Open the catalog afterwards
(`the catalog`) and you will see an info pane cascade from the TOP right instead
— the difference is the pane type, not a setting.

### 5. The bar is now the order's field

**Do not look for a text box in the pane. There isn't one.** The placeholder in
the bar changes to tell you what it is doing, and it is derived from the current
state on every render rather than set on an event, so it cannot go stale:

| What is true | What the bar says |
|---|---|
| still starting the session | Starting the order… |
| nothing typed yet | Say what the director said |
| a request is in flight | Reading what you typed… |
| a pick is waiting | Which one? 1–N, or ⌘ and the number |
| fields still required | N still needed — keep typing |
| nothing required left | Nothing needed — say "that's it" |

### 6. Type the sentence

Type this, slowly enough to watch the rows fill in. Do not press Enter.

```
start an order for Hopkins, Mary Smith, Bronze Triune Burial Vault, tent only, nameplate and vinyl, cross, years only, to St Marys in Skaneateles, service at the church Thursday 10am, eta 11:30
```

**What to look for:**

- rows fill in while you type, about a third of a second after you stop
- **`Mary Smith` in Deceased Name** — not the cemetery's name. That was broken
  until today: "St Marys" failed to match "St. Mary's Cemetery" because of the
  apostrophe, and the unmatched name was then taken as the decedent and
  overwrote Mary Smith.
- **`cross` is captured as the vinyl symbol, and is NOT listed as not
  understood.** It was both missed and reported unreadable until today.
- the Cemetery row reads `St. Mary's Cemetery · Skaneateles · 11:30 AM`
- **nothing in "Not understood"** — the whole sentence is placed

I measured this exact sentence over HTTP on dev: HTTP 200 in 62 ms, 13 fields
captured, no conflicts, nothing unplaced, all nine rows correct.

### 7. Delete something

Select `tent only` in the bar and delete it.

**The Cemetery Equipment row empties.** That is the point of the whole-text
model: the text is the source, so deleting a word un-captures what it said. Under
the old line-by-line model a value was written once and nothing could take it
back.

### 8. A combination the vault does not allow

Clear the bar and type:

```
Continental 34, nameplate and vinyl
```

**This returned HTTP 500 and killed the pane this morning.** Now an amber block
appears above the rows saying the combination is not permitted on that vault and
naming what is — `nameplate_only`. The Personalization row does NOT show the
refused value; the response used to report it as unavailable and display it as
done in the same breath.

### 9. A numbered pick

Clear the bar and type:

```
Continental
```

Several vaults match. The pane shows a numbered list with the numbers visible.
Settle it two ways:

- **click** an option
- **⌘ and the number** — ⌘2 picks the second

Then check the two negatives, both of which are rulings:

- **type a digit.** `depth 3` puts the 3 in the text. Bare digits are never
  stolen, because a director types numbers — grave depths, vault sizes, times.
  Only ⌘ settles a pick.
- **⌘2 with no pick open does nothing**, and does not swallow the key.

After settling, **keep typing.** The question does not come back, even though the
ambiguous word is still on screen. That is what the new `resolutions` column is
for; without it every keystroke would re-ask a question you had just answered.

### 10. Enter does nothing

With the order pane in front, type anything and press Enter. **Nothing happens** —
no request routed, no second pane, the text stays. Enter is reserved for whatever
ends an order later. Try `the catalog{Enter}` specifically: with the order in
front it does nothing; close the order and the same thing opens the catalog.

### 11. Reload

`Cmd+R`, then click the sphere.

**The bar comes back with the full text in it and your settled picks still
settled.** The order lives on the server; the pane holds none of it.

---

## Production

**NOT YET, AND THERE IS A GATE: THE MIGRATION.**

`backend/railway-start.sh:45` runs `alembic upgrade head` on every deploy, so
**merging this to `main` IS a production write.** r208 adds two nullable columns
to `capture_sessions` — `full_text` and `resolutions`. Both nullable, no server
default and no model-side default (I checked both layers), so no existing row is
asserted about. The round trip is clean: r208 → r207 drops both, re-upgrade
applies them.

`capture_sessions` is the table added for typed capture and nothing else writes
it, so the blast radius is that table alone.

Once you have pushed and Railway has deployed:

1. Confirm the deploy took the commit — `/api/health` carries a `commit` field.
2. **Hard-refresh** `app.getbridgeable.com`. Railway's deploy does not reload an
   open tab, and a tab on the old bundle against the new backend looks like a
   regression that is not one.
3. Run steps 4–11 above. Production is a different tenant with different
   cemeteries, funeral homes and vaults, so substitute real names — the sentence
   in step 6 is built from `testco`'s seeded data and its vault and cemetery will
   not resolve there.

⚠️ **Step 8 will behave differently on production and that is expected.** Whether
a combination is refused depends on what the licensee has enrolled, so you will
need a vault whose availability actually excludes something to see the conflict
block at all.

---

## What I did not build

Listed so its absence is not read as a decision.

- **Span attribution for unrecognized text.** The pane shows what the server
  could not place; it does not show which characters produced it. The dispatch
  asked for span attribution and this is the part of it I did not do.
- **The call pipeline's identical 500.** `resolve_and_evaluate` raises
  `UnpermittedAnswer` on exactly the input that used to break the pane, and
  nothing catches it there either. `evaluate_typed` is reached only from the typed
  session, so my fix cannot touch the call path — closing it changes call-overlay
  behaviour, which is E6 territory and yours to rule on.
- **Three fields with no row.** `burial_date`, `grave_location` and
  `nameplate_date_format` are captured and displayed nowhere. Two of the three
  block completion, so the pane can report an order incomplete while showing no
  row for what is missing. Whether they get rows is a display decision; I added a
  ratchet so the set cannot grow unnoticed.
- **No approve path.** Still read-only at review, per E5.

## The commits

```
d588b569  capture: parse the cemetery clause as named steps, not one regex
40164347  capture: the whole text is the source, and settled picks outlive re-reading it
163e73ed  capture: five defects found by running the pane on dev, not by any test
015bbcb8  opas: show a combination the vault forbids, and fix a race in my own test
2bd1702e  opas: the bar is the only input, and the order fills in while you type
```

Migration status: **one**, `r208_capture_session_text`, on dev only.
