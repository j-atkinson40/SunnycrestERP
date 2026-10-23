"""Does every external credential still work? One authenticated no-op each, daily.

⚠️ WHY THIS EXISTS, MEASURED (James, 2026-10-23). The production Anthropic key went
invalid at 2026-10-22 ~17:00 UTC during a rotation. For the next 42 hours:

    briefing.morning / briefing.evening   36 briefings generated with a 29–61 character
                                          narrative instead of 356–528, cost $0.00, and
                                          NOTHING said the model had been skipped
    agent.ar_collections.draft_email      fell back to templates
    collections_sequence                  3 jobs failed outright

⚠️ AND THE EVIDENCE EXISTED WITHIN THE HOUR. `intelligence_executions` recorded every
one honestly as `api_error` from 17:00:01 onward. Nothing read that table. A dead
credential was discoverable in one query for 42 hours and nobody ran it — which is the
same shape as the CI channel and the Railway deploys the same week: things break
silently. This module is the thing that reads.

⚠️ NO SECRET VALUE IS EVER RETURNED, LOGGED OR NOTIFIED. Each probe yields a NAME and a
status. Not the value, not a prefix, not a length — a credential that transits a log has
a copy in that log permanently, which is the standing constraint in CLAUDE.md §7.

⚠️ `NOT_VERIFIABLE` IS A STATUS, NOT A SYNONYM FOR OK. OAuth *app* credentials (client
id + secret) cannot be exercised without a user's grant, so no call can prove them.
Reporting them as healthy because they are present would be the exact false claim this
module exists to catch — a green that is not evidence.

⚠️ AND EVERY PROBE CARRIES A POSITIVE CONTROL, because the ad-hoc audit that prompted
this module produced a FALSE POSITIVE on its first run: Resend returned `403 / error
code 1010`, which is Cloudflare refusing `urllib`'s default User-Agent — the instrument,
not the credential. A working email credential was one sentence from being reported
broken. `control_passes` runs the same probe with a deliberately invalid credential and
requires it to come back NOT ok; a probe that cannot fail reports `UNRELIABLE` rather
than a verdict.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

#: ⚠️ A REAL USER-AGENT, AND IT IS LOAD-BEARING. See the module docstring: the default
#: `Python-urllib/3.x` is blocked by Cloudflare in front of at least one provider.
USER_AGENT = "Bridgeable-credential-probe/1.0"

TIMEOUT = 12

OK = "ok"
INVALID = "invalid"
NOT_SET = "not set"
NOT_VERIFIABLE = "not verifiable"
PARTIAL = "partial"
UNRELIABLE = "unreliable probe"


@dataclass(frozen=True)
class ProbeResult:
    """One credential's status. ⚠️ CARRIES NO VALUE, BY CONSTRUCTION."""

    name: str
    status: str
    #: Provider-supplied explanation, truncated. Never contains the credential.
    detail: str = ""

    @property
    def needs_attention(self) -> bool:
        return self.status in (INVALID, PARTIAL, UNRELIABLE)


@dataclass
class _Probe:
    name: str
    #: () -> (present, status, detail)
    run: Callable[[], tuple[bool, str, str]]
    #: () -> bool. True when a deliberately wrong credential came back NOT ok.
    control: Callable[[], bool] | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


def _http(method: str, url: str, headers: dict | None = None,
          body: bytes | None = None) -> tuple[int | None, str]:
    """A 4xx is DATA here, not an exception — the status code is the answer."""
    req = urllib.request.Request(url, method=method, data=body)
    req.add_header("User-Agent", USER_AGENT)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(600).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(600).decode("utf-8", "replace")
    except Exception as e:  # network, DNS, TLS, timeout
        return None, f"{type(e).__name__}: {e}"


def _msg(txt: str, *path: str) -> str:
    try:
        node = json.loads(txt)
        for p in path:
            node = node.get(p, {}) if isinstance(node, dict) else {}
        return node if isinstance(node, str) else txt[:160]
    except Exception:
        return txt[:160]


# ── per-provider probes ────────────────────────────────────────────────────
# ⚠️ EVERY CALL IS SIDE-EFFECT FREE. Nothing sends, charges, writes or uploads. Where an
# error SHAPE separates a good credential from a bad one for free, that is preferred over
# a billable read — see the Google Places probe.

def _anthropic(key: str) -> tuple[bool, str, str]:
    code, txt = _http("GET", "https://api.anthropic.com/v1/models?limit=1",
                      {"x-api-key": key, "anthropic-version": "2023-06-01"})
    if code == 200:
        return True, OK, "models listed"
    return True, INVALID, f"{code}: {_msg(txt, 'error', 'message')}"


def _deepgram(key: str) -> tuple[bool, str, str]:
    code, txt = _http("GET", "https://api.deepgram.com/v1/projects",
                      {"Authorization": f"Token {key}"})
    return (True, OK, "") if code == 200 else (True, INVALID, f"{code}: {txt[:120]}")


def _resend(key: str) -> tuple[bool, str, str]:
    code, txt = _http("GET", "https://api.resend.com/domains",
                      {"Authorization": f"Bearer {key}"})
    return (True, OK, "") if code == 200 else (True, INVALID, f"{code}: {_msg(txt, 'message')}")


def _places(key: str) -> tuple[bool, str, str]:
    """⚠️ FREE AND DISCRIMINATING. An authenticated-but-incomplete request returns
    `INVALID_REQUEST`; a bad key or an unbilled project returns `REQUEST_DENIED`. No
    result is billed either way, so this costs nothing to run daily."""
    code, txt = _http("GET",
                      "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?"
                      + urllib.parse.urlencode({"key": key, "inputtype": "textquery"}))
    try:
        j = json.loads(txt)
    except Exception:
        return True, INVALID, f"{code}: {txt[:120]}"
    st = j.get("status", "")
    if st == "INVALID_REQUEST":
        return True, OK, "key accepted (INVALID_REQUEST is about the arguments)"
    if st == "REQUEST_DENIED":
        return True, INVALID, j.get("error_message", "REQUEST_DENIED")[:150]
    return True, INVALID, f"unexpected status {st or code}"


def _twilio(sid: str, token: str) -> tuple[bool, str, str]:
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    code, txt = _http("GET", f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
                      {"Authorization": f"Basic {auth}"})
    return (True, OK, "") if code == 200 else (True, INVALID, f"{code}: {txt[:120]}")


def _stripe(key: str) -> tuple[bool, str, str]:
    code, txt = _http("GET", "https://api.stripe.com/v1/balance",
                      {"Authorization": f"Bearer {key}"})
    return (True, OK, "") if code == 200 else (True, INVALID, f"{code}: {_msg(txt, 'error', 'message')}")


def _plaid(cid: str, secret: str) -> tuple[bool, str, str]:
    body = json.dumps({"client_id": cid, "secret": secret, "count": 1, "offset": 0,
                       "country_codes": ["US"]}).encode()
    last = ""
    for host, label in (("https://production.plaid.com", "production"),
                        ("https://sandbox.plaid.com", "sandbox")):
        code, txt = _http("POST", f"{host}/institutions/get",
                          {"Content-Type": "application/json"}, body)
        if code == 200:
            # ⚠️ WHICH ENVIRONMENT IS PART OF THE ANSWER. Sandbox credentials are fine
            # until real bank feeds are wanted, and "ok" alone would hide that.
            return True, OK, label
        last = f"{code}: {_msg(txt, 'error_message')}"
    return True, INVALID, last


def _turnstile(secret: str) -> tuple[bool, str, str]:
    body = urllib.parse.urlencode({"secret": secret, "response": "x"}).encode()
    code, txt = _http("POST", "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                      {"Content-Type": "application/x-www-form-urlencoded"}, body)
    try:
        codes = json.loads(txt).get("error-codes", []) or []
    except Exception:
        codes = []
    if "invalid-input-secret" in codes:
        return True, INVALID, "invalid-input-secret"
    if codes:
        return True, OK, f"secret accepted ({','.join(codes)})"
    return True, INVALID, f"unexpected response {code}"


def _r2(settings) -> tuple[bool, str, str]:
    try:
        import boto3

        c = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        c.head_bucket(Bucket=settings.R2_BUCKET_NAME)
        return True, OK, "head_bucket"
    except Exception as e:
        return True, INVALID, f"{type(e).__name__}: {e}"[:150]


def _build(settings) -> list[_Probe]:
    """The probe list, built from what is actually configured."""

    def s(attr: str) -> str:
        return getattr(settings, attr, "") or ""

    def single(name: str, attr: str, fn, bad: str) -> _Probe:
        def run():
            k = s(attr)
            return (False, NOT_SET, "") if not k else fn(k)

        # ⚠️ THE CONTROL: the same probe with a deliberately invalid credential must NOT
        # come back ok. Without it a provider that answers 200 to everything, or a probe
        # whose request never reaches the provider, reports a credential healthy.
        def control():
            if not s(attr):
                return True  # nothing claimed, nothing to vouch for
            _p, st, _d = fn(bad)
            return st != OK

        return _Probe(name, run, control)

    def pair(name: str, a: str, b: str, fn, bad: tuple[str, str]) -> _Probe:
        def run():
            x, y = s(a), s(b)
            if not (x or y):
                return False, NOT_SET, ""
            if not (x and y):
                return True, PARTIAL, f"only one of {a} / {b} is set"
            return fn(x, y)

        def control():
            if not (s(a) and s(b)):
                return True
            _p, st, _d = fn(*bad)
            return st != OK

        return _Probe(name, run, control)

    def app_oauth(name: str, attrs: tuple[str, str]) -> _Probe:
        def run():
            vals = [bool(s(x)) for x in attrs]
            if not any(vals):
                return False, NOT_SET, ""
            if not all(vals):
                return True, PARTIAL, f"only one of {attrs[0]} / {attrs[1]} is set"
            return True, NOT_VERIFIABLE, (
                "OAuth app credentials need a user grant; no standalone call can prove "
                "them. Reported as itself rather than as ok."
            )

        return _Probe(name, run, None)

    probes = [
        single("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", _anthropic,
               "sk-ant-probe-deliberately-invalid"),
        single("DEEPGRAM_API_KEY", "DEEPGRAM_API_KEY", _deepgram, "deliberately-invalid"),
        single("RESEND_API_KEY", "RESEND_API_KEY", _resend,
               "re_00000000_0000000000000000000000"),
        single("GOOGLE_PLACES_API_KEY", "GOOGLE_PLACES_API_KEY", _places,
               "deliberately-invalid-key"),
        single("STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY", _stripe,
               "sk_test_deliberately_invalid"),
        single("TURNSTILE_SECRET_KEY", "TURNSTILE_SECRET_KEY", _turnstile,
               "0x0000000000000000000000000000000000"),
        pair("TWILIO_ACCOUNT_SID / AUTH_TOKEN", "TWILIO_ACCOUNT_SID",
             "TWILIO_AUTH_TOKEN", _twilio, ("ACdeadbeef", "deadbeef")),
        pair("PLAID_CLIENT_ID / SECRET", "PLAID_CLIENT_ID", "PLAID_SECRET", _plaid,
             ("deadbeef", "deadbeef")),
        app_oauth("QBO_CLIENT_ID / SECRET", ("QBO_CLIENT_ID", "QBO_CLIENT_SECRET")),
        app_oauth("RINGCENTRAL_CLIENT_ID / SECRET",
                  ("RINGCENTRAL_CLIENT_ID", "RINGCENTRAL_CLIENT_SECRET")),
        app_oauth("GDRIVE_CLIENT_ID / SECRET", ("GDRIVE_CLIENT_ID", "GDRIVE_CLIENT_SECRET")),
        app_oauth("DROPBOX_APP_KEY / SECRET", ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET")),
    ]

    if all(s(a) for a in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ACCOUNT_ID")):
        probes.append(_Probe("R2_* (storage)", lambda: _r2(settings), None))
    else:
        probes.append(_Probe("R2_* (storage)", lambda: (False, NOT_SET, "incomplete"), None))

    return probes


#: Names whose values must never appear in a detail string.
_SECRET_ATTRS = (
    "ANTHROPIC_API_KEY", "DEEPGRAM_API_KEY", "RESEND_API_KEY",
    "GOOGLE_PLACES_API_KEY", "STRIPE_SECRET_KEY", "TURNSTILE_SECRET_KEY",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "PLAID_CLIENT_ID", "PLAID_SECRET",
    "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ACCOUNT_ID",
    "QBO_CLIENT_ID", "QBO_CLIENT_SECRET",
    "RINGCENTRAL_CLIENT_ID", "RINGCENTRAL_CLIENT_SECRET",
    "GDRIVE_CLIENT_ID", "GDRIVE_CLIENT_SECRET",
    "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET",
)


def _redact(detail: str, settings) -> str:
    """Remove any configured credential value from provider-supplied text.

    ⚠️ THIS EXISTS BECAUSE THE PROBE LEAKED, AND A TEST CAUGHT IT RATHER THAN A REVIEW.
    `test_NO_RESULT_CARRIES_A_CREDENTIAL_VALUE` feeds a provider error body that ECHOES
    THE KEY BACK — which real providers do — and the first version of this module passed
    that message straight into `detail`, into the log, and into the notification body.
    The one property this module cannot compromise, broken by the module itself.

    ⚠️ IT REDACTS AT THE BOUNDARY, NOT IN EACH PROBE. Twelve probes each remembering to
    scrub is twelve chances to forget, and the thirteenth probe someone adds would not
    know it had to. One pass over every result is a property of the module instead.

    ⚠️ AND IT SCRUBS SUBSTRINGS DOWN TO 8 CHARACTERS, because a provider that echoes a
    TRUNCATED key ("bad key sk-ant-abc…") would otherwise slip a usable prefix through.
    """
    if not detail:
        return detail
    out = detail
    for attr in _SECRET_ATTRS:
        v = (getattr(settings, attr, "") or "").strip()
        if len(v) < 8:
            continue
        if v in out:
            out = out.replace(v, "[redacted]")
        # a truncated echo: scan progressively shorter prefixes
        for n in range(len(v), 7, -1):
            frag = v[:n]
            if frag in out:
                out = out.replace(frag, "[redacted]")
                break
    return out


def run_probes(settings=None) -> list[ProbeResult]:
    """Every configured credential's status. No network call is made for an unset one."""
    if settings is None:
        from app.config import settings as _s

        settings = _s

    out: list[ProbeResult] = []
    for p in _build(settings):
        try:
            _present, status, detail = p.run()
        except Exception as e:  # a probe must never take the job down
            out.append(ProbeResult(p.name, UNRELIABLE,
                                   _redact(f"probe raised: {type(e).__name__}", settings)))
            continue

        # ⚠️ THE CONTROL IS READ BEFORE THE VERDICT, not after. An `ok` from a probe that
        # cannot fail is worth nothing, and the only honest thing to report for it is
        # that the instrument is unreliable.
        if status == OK and p.control is not None:
            try:
                if not p.control():
                    out.append(ProbeResult(
                        p.name, UNRELIABLE,
                        "the probe returned ok for a deliberately invalid credential, so "
                        "its ok means nothing",
                    ))
                    continue
            except Exception as e:
                out.append(ProbeResult(
                    p.name, UNRELIABLE, f"control raised: {type(e).__name__}"))
                continue
        out.append(ProbeResult(p.name, status, _redact(detail, settings)))
    return out


def format_report(results: list[ProbeResult]) -> str:
    """A table for a log or a notification body. ⚠️ CONTAINS NO CREDENTIAL VALUES."""
    lines = [f"{'credential':34} {'status':16} detail"]
    lines.append("-" * 96)
    for r in results:
        lines.append(f"{r.name:34} {r.status:16} {r.detail[:44]}")
    bad = [r for r in results if r.needs_attention]
    lines.append("")
    lines.append(f"needing attention: {len(bad)} of {len(results)}")
    for r in bad:
        lines.append(f"  {r.name}: {r.status} — {r.detail[:90]}")
    return "\n".join(lines)
