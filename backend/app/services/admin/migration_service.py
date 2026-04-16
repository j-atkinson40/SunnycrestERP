"""Migration control — read-only for production, runnable on staging."""

import asyncio
import os
import subprocess
from pathlib import Path


def _backend_dir() -> Path:
    # backend/app/services/admin/migration_service.py → backend/
    return Path(__file__).resolve().parent.parent.parent.parent


def get_current_revision(database_url: str) -> str | None:
    """Return the current alembic revision for the given DATABASE_URL."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    try:
        result = subprocess.run(
            ["alembic", "current"],
            cwd=str(_backend_dir()),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = result.stdout.strip() + "\n" + result.stderr.strip()
        # Parse "<revision> (head)" or similar
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("INFO") and " " in line:
                return line.split()[0]
            if line and not line.startswith("INFO") and line:
                return line
        return None
    except Exception:
        return None


def get_pending_revisions() -> list[str]:
    """Return list of revisions in the alembic chain that are after current head on the given DB.

    For simplicity uses `alembic history` and parses; detailed pending-only requires comparing with DB.
    """
    try:
        result = subprocess.run(
            ["alembic", "heads"],
            cwd=str(_backend_dir()),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


async def run_staging_migrations(stream_callback=None) -> dict:
    """Run `alembic upgrade head` against the STAGING database.

    Uses STAGING_DATABASE_URL env var. Refuses to run against production.
    Streams output line-by-line via stream_callback.
    """
    staging_url = os.getenv("STAGING_DATABASE_URL")
    if not staging_url:
        raise RuntimeError("STAGING_DATABASE_URL not configured")
    if "production" in staging_url.lower() or "prod-" in staging_url.lower():
        raise RuntimeError("SAFETY: STAGING_DATABASE_URL appears to point to production")

    env = os.environ.copy()
    env["DATABASE_URL"] = staging_url

    proc = await asyncio.create_subprocess_exec(
        "alembic", "upgrade", "head",
        cwd=str(_backend_dir()),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    output_lines: list[str] = []
    async for line_bytes in proc.stdout:  # type: ignore
        line = line_bytes.decode("utf-8", errors="replace").rstrip()
        output_lines.append(line)
        if stream_callback:
            try:
                res = stream_callback(line)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
    await proc.wait()
    return {
        "returncode": proc.returncode,
        "success": proc.returncode == 0,
        "output": "\n".join(output_lines),
    }
