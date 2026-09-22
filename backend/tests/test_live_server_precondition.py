"""One test whose only job is to make an unreachable server impossible to miss.

⚠️ THIS IS THE LOUD HALF OF THE GUARD. `tests/_live_server.require_live_server`
SKIPS the HTTP integration suites when their server is down, because raising at
module level produces a collection error and pytest treats those as fatal — one
guarded module aborted a run containing 21 unrelated tests.

A skip on its own is quiet, and quiet is the original defect. This test fails,
so a run with no server carries a failure that cannot be read as clean, while
every other suite still executes.
"""
from __future__ import annotations

from tests._live_server import BASE_URL, is_reachable, unreachable_message


def test_the_http_integration_suites_have_a_server_to_talk_to():
    assert is_reachable(BASE_URL), unreachable_message(BASE_URL)
