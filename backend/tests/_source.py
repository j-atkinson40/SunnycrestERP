"""Shared helper for tests that assert against SOURCE TEXT.

⚠️ WHY THIS EXISTS. Source-scraping tests match comment PROSE as readily as code,
and the more carefully the code is commented the more likely a false match
becomes. This defect occurred FOUR times in one session, twice after the rule had
been written down and once after a guard had been hardened against it:

  1. `send_statement_email` as a split point landed inside a comment describing it
  2. "no `raise` in this branch" tripped on the words "a later raise cannot…"
  3. the ownership ratchet fired on a docstring that merely MENTIONED
     `UPDATE workflow_steps SET config`
  4. "the old vocabulary is gone" tripped on a comment quoting the old vocabulary
     in order to explain why it was replaced

Naming the rule did not install it; a shared helper might. Follows the
`tests/_cleanup.py` precedent — a single place for a discipline that every test
file otherwise re-implements slightly differently.

A test that reads its own explanatory comments is measuring documentation, not
behaviour.
"""
from __future__ import annotations

import re


def code_only(src: str) -> str:
    """Return `src` with docstrings and `#` comments removed.

    Docstrings first, because they can contain `#`.

    Line-based rather than tokenised: `inspect.getsource` of an indented block
    does not round-trip through `tokenize.untokenize`. The known limitation is a
    `#` inside a string literal, which would truncate that line — acceptable for
    assertion targets, and loud rather than silent if it ever bites.
    """
    without_docstrings = re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', " ", src)
    return "\n".join(line.split("#")[0] for line in without_docstrings.splitlines())
