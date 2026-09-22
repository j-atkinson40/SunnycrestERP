"""One id per test session, carried by every identifier a test mints.

⚠️ THE PROBLEM THIS SOLVES IS NOT A NARROW KEYSPACE. A random suffix drawn from a
fixed space into a table nothing empties has a collision probability that is a
function of the accumulated rows, and that function only increases. Widening
`uuid4().hex[:6]` (16^6) to something larger moves the failure out and changes
nothing structural — the same curve with a gentler slope and no bound anywhere on
it.

Measured 2026-09-22: `platform_users` held 7,790 rows, 3,707 of them in the single
namespace `platform-<6 hex>@bridgeable.test`, shared by six test files. One run
collided and failed an unrelated assertion:

    psycopg2.errors.UniqueViolation: duplicate key value violates unique
    constraint "ix_platform_users_email"
    DETAIL:  Key (email)=(platform-748396@bridgeable.test) already exists.

THE VARIABLE THAT SHOULD BE BOUNDED IS HOW LONG A NAME MUST STAY UNIQUE. Today a
minted email must stay unique against every row any run has ever written. It only
ever needs to stay unique within its own run.

So every minted identifier carries `RUN_ID`, and teardown deletes by `RUN_ID`
rather than by a name pattern. Two consequences follow, and both matter:

- **The collision closes immediately, before anything is cleaned.** A name
  carrying this run's id cannot collide with a resident row from another run,
  whatever is already in the table. The 3,707 rows stop being a hazard the moment
  this ships, not the moment they are deleted.
- **Teardown cannot over-reach.** A pattern-based delete can catch another run's
  rows or a real user. `RUN_ID` is not shared and not guessable, so a delete keyed
  on it touches only what this session created.

⚠️ `BRIDGEABLE_TEST_RUN_ID` exists so a caller that needs to know the id in
advance — a CI job that wants to sweep after a killed session — can set it. It is
NOT a way to reuse an id across sessions; doing that reintroduces exactly the
cross-run collision this module removes.
"""
from __future__ import annotations

import os
import uuid

#: Unique to this pytest session. Eight hex chars: it only has to be distinct
#: from other sessions running concurrently, not from every session in history,
#: which is the whole point of the change.
RUN_ID: str = os.environ.get("BRIDGEABLE_TEST_RUN_ID") or uuid.uuid4().hex[:8]

#: SQL LIKE pattern matching every identifier this session minted.
#: ⚠️ The leading and trailing `-` are load-bearing: they stop `RUN_ID` matching
#: as a substring of a longer random suffix.
RUN_ID_LIKE: str = f"%-{RUN_ID}-%"


def run_scoped(stem: str) -> str:
    """`stem` with this run's id folded in.

    For identifiers that are not built from the `-{RUN_ID}-{suffix}@` email
    shape and so cannot take the id by the usual edit.
    """
    return f"{stem}-{RUN_ID}-{uuid.uuid4().hex[:6]}"
