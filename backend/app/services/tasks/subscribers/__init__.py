"""Task substrate v1 — subscriber package.

Modules importable from this package register themselves against the
registry at module-import time. The parent `app.services.tasks.__init__`
side-effect-imports each subscriber module to activate registration.
"""
