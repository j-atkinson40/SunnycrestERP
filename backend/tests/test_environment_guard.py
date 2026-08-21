"""The production guard refuses when ENVIRONMENT is unset, rather than guessing.

⚠️ A PRODUCTION-REFUSAL GUARD THAT FAILS OPEN IS NOT A GUARD. `railway-start.sh`
tested `[ "${ENVIRONMENT:-dev}" != "production" ]`. When the variable was simply
MISSING that read as "dev" and the demo seeds ran — against whatever database the
deploy was pointed at.

The fingerprint is dated: the guard was committed 2026-05-06 18:19:29 UTC, and
`hopkins-fh` was created on the PRODUCTION database at 18:20:42 UTC — 73 seconds
later, by the deploy that shipped the guard. `st-marys` followed the same
evening. They were not created before the guard existed; they were created
THROUGH it, while it was open.

The shape is the arc's signature, in the one place the safe default is obvious:
the guard's passing state required a variable to be present, and absence
silently permitted. Same as `setup_complete` outliving what it described, and
the teardown that stopped cleaning up because of the thing it failed to clean.

⚠️ THESE TESTS READ THE REAL FILES AND EXECUTE THE REAL SCRIPT. Asserting on a
copy of the guard would pass while the shipped one stayed open.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
RESOLVER = BACKEND / "scripts" / "require_known_environment.sh"
START = BACKEND / "railway-start.sh"


def _run(env: dict | None):
    """Invoke the real resolver with a scrubbed environment."""
    base = {"PATH": "/usr/bin:/bin"}
    if env:
        base.update(env)
    return subprocess.run(
        ["bash", str(RESOLVER)], capture_output=True, text=True, env=base,
    )


def _shell_code_only(path: pathlib.Path) -> str:
    """Strip `#` comments so a WARNING ABOUT a pattern is not read as the pattern.

    ⚠️ THIS IS LOAD-BEARING AND WAS NEEDED IMMEDIATELY. The comment added above
    the fixed guard quotes the old fail-open test verbatim, so a naive grep for
    it matches the documentation that exists to prevent it — a test that fails
    on its own explanation. Mirrors `tests/_source.code_only` for Python.
    """
    out = []
    for line in path.read_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line.split(" #", 1)[0] if " #" in line else line)
    return "\n".join(out)


class TestTheResolverRefusesRatherThanGuessing:
    def test_unset_refuses(self):
        r = _run(None)
        assert r.returncode != 0, (
            "ENVIRONMENT unset was accepted — the guard still infers an "
            "environment instead of refusing to guess"
        )
        assert "ENVIRONMENT is not set" in r.stderr
        assert r.stdout.strip() == "", "refusal must not also print a value"

    def test_empty_string_refuses_too(self):
        """⚠️ SET-BUT-EMPTY IS THE SAME HOLE WEARING A DIFFERENT HAT. A Railway
        variable cleared to "" is present as far as `${VAR:-x}` is concerned in
        some shells and absent in others; both must refuse."""
        r = _run({"ENVIRONMENT": ""})
        assert r.returncode != 0
        assert "ENVIRONMENT is not set" in r.stderr

    @pytest.mark.parametrize("value", ["dev", "staging", "production"])
    def test_an_explicit_value_is_returned_verbatim(self, value):
        r = _run({"ENVIRONMENT": value})
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == value

    def test_it_does_not_normalise_or_interpret(self):
        """The resolver reports; the CALLER decides. If this started lowercasing
        or mapping unknown values onto `dev`, it would be making the same class
        of guess it exists to stop."""
        r = _run({"ENVIRONMENT": "Production"})
        assert r.returncode == 0
        assert r.stdout.strip() == "Production"


class TestTheStartScriptUsesIt:
    def test_no_fail_open_default_on_environment(self):
        """⚠️ BANS A NON-EMPTY DEFAULT SPECIFICALLY. `${ENVIRONMENT:-}` is fine
        — that is an empty default feeding an emptiness test, which is
        fail-CLOSED and is what the resolver itself uses. `${ENVIRONMENT:-dev}`
        is the defect: a value invented when the variable is missing."""
        for path in (START, RESOLVER):
            code = _shell_code_only(path)
            bad = re.findall(r"\$\{ENVIRONMENT:-\s*[^}\s]+\s*\}", code)
            assert not bad, (
                f"{path.name} invents an environment when the variable is "
                f"missing: {bad}"
            )

    def test_the_start_script_actually_calls_the_resolver(self):
        """A resolver nothing calls is a file, not a guard."""
        code = _shell_code_only(START)
        assert "require_known_environment.sh" in code

    def test_the_start_script_aborts_when_the_resolver_refuses(self):
        """⚠️ CALLING IT IS NOT ENOUGH. If the invocation ignored a non-zero
        exit, the seeds would run on an unresolved environment exactly as
        before — the resolver would be decoration."""
        code = _shell_code_only(START)
        # ⚠️ `[^)]*` DOES NOT WORK HERE — the invocation nests a command
        # substitution (`$(dirname "$0")`), so a paren-excluding class stops
        # inside it. Match to end-of-line instead.
        m = re.search(
            r"if\s+!\s+ENV_RESOLVED=.*require_known_environment\.sh.*?then\n(.*?)\nfi",
            code, re.S,
        )
        assert m, "the resolver's exit status is not being tested"
        assert "exit 1" in m.group(1), (
            "the resolver refused and the script continued anyway"
        )

    def test_the_seed_block_keys_on_the_resolved_value(self):
        """The decision must use what the resolver returned, not re-read the
        raw variable — otherwise the refusal is bypassed on the very next line."""
        code = _shell_code_only(START)
        assert '"$ENV_RESOLVED" != "production"' in code


def test_the_resolver_is_reachable_from_the_start_script_as_written():
    """⚠️ THE PATH IS RELATIVE TO `dirname $0`, AND A WRONG PATH FAILS CLOSED
    — the deploy aborts. That is the safe direction, but it would abort EVERY
    deploy, so the path is worth pinning rather than discovering on Railway."""
    assert RESOLVER.exists()
    assert (START.parent / "scripts" / "require_known_environment.sh").resolve() \
        == RESOLVER.resolve()
