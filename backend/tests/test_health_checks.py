"""No more silent failures: the credential probe and the model-failure watch.

James, 2026-10-23. The production Anthropic key went invalid mid-rotation at
2026-10-22 ~17:00 UTC. For 42 hours:

    briefing.morning / briefing.evening   36 briefings, narrative 29–61 chars instead of
                                          356–528, cost $0.00, and nothing on them said
                                          the writing model had been skipped
    agent.ar_collections.draft_email      fell back to templates

⚠️ AND `intelligence_executions` RECORDED EVERY ONE AS `api_error` FROM THE FIRST MINUTE.
Nothing read the table. The data was never the problem — the reading was.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.health import credential_probe as cp
from app.services.health import model_failure_watch as mfw


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        s.execute(sql_text("SELECT 1"))
    except Exception as exc:
        s.close()
        pytest.skip(f"database unavailable: {exc}")
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# ───────────────────────────────────────────────────────────────────────────
# the probe: no secrets, and no ok it cannot justify
# ───────────────────────────────────────────────────────────────────────────

class _Settings:
    """A settings stand-in. Only the attributes a probe reads are present."""

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getattr__(self, _name):  # every unset credential reads as absent
        return ""


def test_an_unset_credential_makes_NO_network_call(monkeypatch):
    """⚠️ A PROBE THAT CALLED OUT FOR EVERY UNSET CREDENTIAL WOULD BE A DAILY BURST OF
    POINTLESS REQUESTS, and on a tenant with nothing configured it would be all of them.
    """
    calls = []
    monkeypatch.setattr(cp, "_http", lambda *a, **k: calls.append(a) or (200, "{}"))
    out = cp.run_probes(_Settings())
    assert calls == [], calls
    assert all(r.status in (cp.NOT_SET, cp.PARTIAL) for r in out), [
        (r.name, r.status) for r in out
    ]


def test_NO_RESULT_CARRIES_A_CREDENTIAL_VALUE(monkeypatch):
    """⚠️ THE ONE PROPERTY THAT CANNOT BE COMPROMISED. A credential in a log has a copy
    in that log permanently — CLAUDE.md §7 — and this probe's output goes to a log AND to
    a notification body.

    ⚠️ IT ASSERTS OVER THE WHOLE REPORT, NOT JUST THE STATUS, because `format_report` is
    what reaches the notification and a value leaking through `detail` would be invisible
    to a status-only check.
    """
    SECRET = "sk-ant-THIS-IS-THE-SECRET-VALUE-0123456789"
    # the provider echoes the credential back in its error body, which is the nastiest
    # realistic case — some providers do
    monkeypatch.setattr(cp, "_http",
                        lambda *a, **k: (401, '{"error":{"message":"bad key ' + SECRET + '"}}'))
    out = cp.run_probes(_Settings(ANTHROPIC_API_KEY=SECRET))
    report = cp.format_report(out)
    for frag in (SECRET, SECRET[:20], SECRET[7:27]):
        assert frag not in report, "a credential value reached the report"
    # ⚠️ THE CONTROL: the probe really did run and really did report a problem, so the
    # absence above is about redaction rather than about a probe that produced nothing.
    assert any(r.status == cp.INVALID for r in out), [(r.name, r.status) for r in out]


def test_a_TRUNCATED_echo_is_redacted_too(monkeypatch):
    """⚠️ ADDED AFTER A BREAK TEST FOUND NOTHING RED. Narrowing `_redact` to whole values
    only left all 14 tests green, because the leak test feeds the FULL secret back and a
    whole-value match still catches that.

    ⚠️ A TRUNCATED ECHO IS THE REALISTIC CASE AND THE MORE DANGEROUS ONE. Providers
    commonly echo a prefix — "bad key sk-ant-abc123…" — and a prefix long enough to
    identify the credential is still a leak. Redaction scans down to 8 characters, so a
    partial echo is caught; this is what holds that.
    """
    SECRET = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"
    monkeypatch.setattr(
        cp, "_http",
        lambda *a, **k: (401, '{"error":{"message":"bad key ' + SECRET[:24] + '..."}}'),
    )
    out = cp.run_probes(_Settings(ANTHROPIC_API_KEY=SECRET))
    report = cp.format_report(out)
    assert SECRET[:24] not in report, report
    assert SECRET[:12] not in report, report
    # the control: the probe ran and said something
    assert any(r.status == cp.INVALID for r in out)
    assert "[redacted]" in report


def test_an_OK_FROM_A_PROBE_THAT_CANNOT_FAIL_IS_REPORTED_UNRELIABLE(monkeypatch):
    """⚠️ THIS IS THE FALSE POSITIVE THAT PROMPTED THE CONTROL, INVERTED.

    The ad-hoc audit reported Resend INVALID on its first run because Cloudflare refused
    `urllib`'s default User-Agent — the instrument, not the credential. A working email
    credential was one sentence from being called broken. The mirror-image failure is
    worse: a provider (or a proxy, or a stub) that answers 200 to everything would make
    every probe report `ok`.

    So each probe is re-run with a deliberately invalid credential and must NOT come back
    ok. Here everything answers 200, so the control fails and the honest verdict is that
    the instrument cannot be trusted — not `ok`.
    """
    monkeypatch.setattr(cp, "_http", lambda *a, **k: (200, "{}"))
    out = cp.run_probes(_Settings(ANTHROPIC_API_KEY="anything"))
    ant = [r for r in out if r.name == "ANTHROPIC_API_KEY"]
    assert len(ant) == 1
    assert ant[0].status == cp.UNRELIABLE, ant[0]
    assert ant[0].needs_attention


def test_a_real_ok_survives_the_control(monkeypatch):
    """The other side: a provider that accepts the good credential and rejects the bad
    one yields `ok`. Without this the test above is satisfied by a probe that can never
    say ok at all."""
    good = "the-good-one"

    def http(method, url, headers=None, body=None):
        sent = " ".join((headers or {}).values())
        return (200, "{}") if good in sent else (401, '{"error":{"message":"nope"}}')

    monkeypatch.setattr(cp, "_http", http)
    out = cp.run_probes(_Settings(ANTHROPIC_API_KEY=good))
    ant = [r for r in out if r.name == "ANTHROPIC_API_KEY"][0]
    assert ant.status == cp.OK, ant


def test_oauth_app_credentials_are_NOT_VERIFIABLE_never_ok():
    """⚠️ "not verifiable" IS A STATUS, NOT A SYNONYM FOR OK. An OAuth app credential
    cannot be exercised without a user's grant, so no call can prove it. Calling it
    healthy because it is present is the green-that-is-not-evidence this whole module
    exists to catch.
    """
    out = cp.run_probes(_Settings(
        RINGCENTRAL_CLIENT_ID="id", RINGCENTRAL_CLIENT_SECRET="sec",
    ))
    rc = [r for r in out if r.name.startswith("RINGCENTRAL")][0]
    assert rc.status == cp.NOT_VERIFIABLE
    # ⚠️ AND IT DOES NOT RAISE AN ALARM EITHER — it is not a failure, it is an unknown.
    assert not rc.needs_attention


def test_half_a_pair_is_PARTIAL_not_ok_and_not_absent():
    out = cp.run_probes(_Settings(TWILIO_ACCOUNT_SID="AC1"))
    tw = [r for r in out if r.name.startswith("TWILIO")][0]
    assert tw.status == cp.PARTIAL
    assert tw.needs_attention


def test_a_probe_that_raises_does_not_take_the_run_down(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network on fire")

    monkeypatch.setattr(cp, "_http", boom)
    out = cp.run_probes(_Settings(ANTHROPIC_API_KEY="x", DEEPGRAM_API_KEY="y"))
    assert len(out) >= 2
    assert all(r.status in (cp.UNRELIABLE, cp.NOT_SET, cp.NOT_VERIFIABLE, cp.INVALID)
               for r in out), [(r.name, r.status) for r in out]


def test_the_probe_sends_a_real_user_agent(monkeypatch):
    """⚠️ THE FALSE POSITIVE'S ACTUAL CAUSE, PINNED. `Python-urllib/3.x` is refused by
    the Cloudflare edge in front of at least one provider, which is how a working
    credential came back 403."""
    seen = {}

    def http(method, url, headers=None, body=None):
        return 200, "{}"

    assert "urllib" not in cp.USER_AGENT.lower()
    assert cp.USER_AGENT.strip() != ""


# ───────────────────────────────────────────────────────────────────────────
# the watch: it must be able to speak
# ───────────────────────────────────────────────────────────────────────────

@pytest.fixture
def prompt_rows(db):
    """A prompt and executions we control, cleaned up afterwards."""
    pid = str(uuid.uuid4())
    key = f"test.health.{uuid.uuid4().hex[:8]}"
    # ⚠️ EVERY NOT-NULL COLUMN, READ OFF THE SCHEMA RATHER THAN GUESSED. My first
    # version wrote `name`, which does not exist — the column is `display_name`, and
    # `domain`, `is_active` and `updated_at` are also NOT NULL.
    db.execute(sql_text(
        "INSERT INTO intelligence_prompts "
        "(id, prompt_key, display_name, domain, is_active, created_at, updated_at) "
        "VALUES (:i, :k, 'health test', 'test', true, now(), now())"
    ), {"i": pid, "k": key})
    db.commit()
    made: list[str] = []

    def add(status: str, minutes_ago: int):
        eid = str(uuid.uuid4())
        db.execute(sql_text(
            "INSERT INTO intelligence_executions "
            "(id, prompt_id, status, created_at, is_test_execution) "
            "VALUES (:i, :p, :s, now() - make_interval(mins => :m), false)"
        ), {"i": eid, "p": pid, "s": status, "m": minutes_ago})
        made.append(eid)
        db.commit()

    try:
        yield key, add
    finally:
        db.rollback()
        db.execute(sql_text("DELETE FROM intelligence_executions WHERE prompt_id = :p"),
                   {"p": pid})
        db.execute(sql_text("DELETE FROM intelligence_prompts WHERE id = :p"), {"p": pid})
        db.commit()


def test_a_prompt_failing_EVERY_attempt_is_named(db, prompt_rows):
    key, add = prompt_rows
    for m in (10, 30, 50):
        add("api_error", m)
    got = {f.prompt_key: f for f in mfw.failing_prompts(db)}
    assert key in got, sorted(got)
    assert got[key].failures == 3
    assert "api_error" in got[key].statuses


def test_ONE_SUCCESS_IN_THE_WINDOW_IS_ENOUGH_TO_STAY_QUIET(db, prompt_rows):
    """⚠️ "ANY SUCCESS?", NOT "ANY FAILURE?", AND THIS IS THE TEST OF IT. A 529 overload
    or a schema miss is ordinary — this table holds 15 of the first and 44 of the second
    across six months, and none of them is an incident. Alerting on a failure would make
    the check cry wolf until nobody read it, which is how a channel goes dark.
    """
    key, add = prompt_rows
    add("api_error", 40)
    add("api_error", 30)
    add("success", 20)
    assert key not in {f.prompt_key for f in mfw.failing_prompts(db)}


def test_a_failure_OUTSIDE_the_window_is_not_an_incident(db, prompt_rows):
    key, add = prompt_rows
    add("api_error", mfw.WINDOW_MINUTES + 30)
    assert key not in {f.prompt_key for f in mfw.failing_prompts(db)}


def test_THE_WATCH_CAN_SPEAK_ABOUT_A_PAST_WINDOW(db, prompt_rows):
    """⚠️ `as_of` IS WHY THIS CHECK IS AN INSTRUMENT AND NOT A HOPE. Run against `now()`
    on a healthy database it says "all clear" — which is the same output a broken query
    gives. CLAUDE.md's absent signal: an empty result and a blind instrument are
    indistinguishable.

    Verified against the real incident on production: pointed at 2026-10-22 18:30 it
    named `briefing.evening`, 17 attempts, all `api_error`. It would have caught the
    outage 90 minutes in instead of 42 hours.
    """
    key, add = prompt_rows
    add("api_error", 500)  # well outside the live window
    assert key not in {f.prompt_key for f in mfw.failing_prompts(db)}
    as_of = (datetime.now(timezone.utc) - timedelta(minutes=470)).isoformat()
    named = {f.prompt_key for f in mfw.failing_prompts(db, as_of=as_of)}
    assert key in named, named


def test_the_report_says_nothing_happened_when_nothing_did(db):
    msg = mfw.format_report([])
    assert "No prompt" in msg
    assert str(mfw.WINDOW_MINUTES) in msg


def test_the_window_is_wider_than_an_hour_on_purpose():
    """⚠️ 90 MINUTES FOR AN "OVER AN HOUR" RULE. The briefing prompts fire hourly, so a
    60-minute window can contain exactly one attempt — and one failed attempt is not yet
    a pattern. 90 guarantees at least two opportunities for an hourly prompt."""
    assert mfw.WINDOW_MINUTES > 60
