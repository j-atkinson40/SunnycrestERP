"""Playwright script base class and error type.

Each script is a stateless class. The workflow engine calls
``script.execute(inputs, credentials)`` in an isolated event loop.
Credentials are decrypted by the caller and passed as a plain dict —
the script never touches the database.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class PlaywrightScriptError(Exception):
    """Raised by a script when execution fails.

    Includes an optional screenshot path (for debugging) and the step
    name where the failure occurred.
    """

    def __init__(
        self,
        message: str,
        screenshot_path: str | None = None,
        step: str | None = None,
    ) -> None:
        super().__init__(message)
        self.screenshot_path = screenshot_path
        self.step = step


class PlaywrightScript(ABC):
    """Abstract base for all Playwright automation scripts."""

    name: str
    service_key: str
    required_inputs: list[str]
    outputs: list[str]

    @abstractmethod
    async def execute(
        self,
        inputs: dict[str, Any],
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Execute the script. Returns a dict whose keys match ``self.outputs``.

        Raises ``PlaywrightScriptError`` on failure with optional
        screenshot path for debugging.
        """

    async def _take_screenshot(self, page: Any, prefix: str = "error") -> str | None:
        """Best-effort screenshot to /tmp for debugging."""
        try:
            path = f"/tmp/playwright_{prefix}_{id(page)}.png"
            await page.screenshot(path=path)
            return path
        except Exception:
            return None

    def validate_inputs(self, inputs: dict[str, Any]) -> None:
        missing = [k for k in self.required_inputs if k not in inputs or inputs[k] is None]
        if missing:
            raise PlaywrightScriptError(
                f"Missing required inputs for {self.name}: {', '.join(missing)}"
            )
