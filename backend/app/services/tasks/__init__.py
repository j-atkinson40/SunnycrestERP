"""Task substrate v1 — services package.

Modules:
- lifecycle: dual-shape state machine (action + reminder) + transition guards.
- subscribers: subscriber registry (7 events, 6 subscribers, sync exec).
- plugins: 3 plugin category contracts + 5 task type behavior plugins.
- service: top-level CRUD + façade preserving 8 existing Task consumers.

Per build prompt §5; state doc §5; phasing §1.
"""

from app.services.tasks import lifecycle, service  # noqa: F401
from app.services.tasks.subscribers import registry as subscriber_registry  # noqa: F401
from app.services.tasks.plugins import (  # noqa: F401
    creators,
    surfaces,
    type_behaviors,
)

# Side-effect imports — modules auto-register against their registries
# on first import. Importing the tasks package activates the substrate.
from app.services.tasks.subscribers import (  # noqa: F401
    notification_subscriber,
    audit_subscriber,
    briefings_subscriber,
    pulse_subscriber,
    workflow_subscriber,
    focus_subscriber,
)
from app.services.tasks.plugins.types import (  # noqa: F401
    generic_task,
    review_approval_task,
    scheduled_recurring_task,
    customer_communication_task,
    anomaly_resolution_task,
)
