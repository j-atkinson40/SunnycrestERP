"""The least the model needs to turn a phrase into an OrderQuestion.

⚠️ JAMES'S RULING, 2026-10-20: "Send the model the least it needs, and adopt that as a
rule. Working out 'hopkins order' needs a surname at most. Answering 'when's the service'
for the order in front needs no model at all. A deceased person's name only goes to a
model when it's actually needed."

⚠️ SO THIS MODULE'S JOB IS SUBTRACTION, NOT ASSEMBLY, and the thing it subtracts is the
only sensitive data in the system. A funeral order carries a dead person's name, their
funeral home, their cemetery and the day they are buried. Three of those four are
business records. The first is not.

⚠️ AND NO DECEASED NAME IS EVER SENT FROM HERE — not "unless needed", not "only the
surname", NONE. The reason is structural rather than a policy choice, which is what makes
it hold:

    `OrderQuestion.decedent` is filled from the PHRASE, because the phrase IS the
    surname. "smith order" needs the model to put "smith" in the decedent field; it
    does not need a list of decedents to pick from.

The three fields that DO need a list — `funeral_home`, `cemetery`, `vault` — need it
because `stage.matches` does substring matching against them, so a model guessing
"Hopkins FH" against a record reading "Hopkins Funeral Home" silently filters to zero
rows. Those three are the whole context.

⚠️ WHAT THIS DELIBERATELY DOES NOT SEND, each with the reason:

    deceased names        never needed — see above
    order numbers         `_ORDER_NUMBER` resolves them in rules before the model runs
    row contents          a question is a FILTER, not an answer; the engine fetches
    totals, counts        `_BANNED_KEYS` already refuses them on the way back
    the front pane        front-pane requests are answered by rules and never reach here
    other tenants         every query is scoped to one `company_id`

⚠️ AND IT IS CAPPED. A tenant with 4,000 customers would otherwise put 4,000 names in
every prompt — cost, latency, and a context the model cannot use well. The cap is stated
in the prompt so a truncated list reads as truncated rather than as "these are all of
them".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

#: How many names of each kind travel. Chosen against the measured sizes rather than
#: guessed: Sunnycrest has 5 customers, 1 cemetery and 10 products (production,
#: 2026-10-20), and the platform catalog has 29 variants. 60 leaves room for a tenant an
#: order of magnitude larger before anything is dropped.
NAME_CAP = 60

#: Keys that must never appear in the variables this module produces.
#:
#: ⚠️ ASSERTED BY A TEST RATHER THAN TRUSTED. The subtraction above is the whole point of
#: the module, and a later edit adding `decedents` for convenience would be invisible —
#: the prompt would still render, the model would still answer, and a deceased person's
#: name would start leaving the tenant. This list is what the test checks against.
FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "decedent", "decedents", "deceased", "deceased_name", "deceased_names",
    "names", "orders", "rows", "records", "total", "totals", "amount", "count",
})


@dataclass(frozen=True)
class ModelContext:
    """The variables the prompt is rendered with. Nothing else is sent."""

    today: str
    phrase: str
    funeral_homes: list[str] = field(default_factory=list)
    cemeteries: list[str] = field(default_factory=list)
    vaults: list[str] = field(default_factory=list)
    truncated: bool = False

    def as_variables(self) -> dict:
        """⚠️ EXPLICIT, NOT `asdict`. `asdict` would carry any field a future edit adds,
        which is how a forbidden key gets in without anyone choosing it."""
        return {
            "today": self.today,
            "phrase": self.phrase,
            "funeral_homes": ", ".join(self.funeral_homes) or "(none on record)",
            "cemeteries": ", ".join(self.cemeteries) or "(none on record)",
            "vaults": ", ".join(self.vaults) or "(none on record)",
            "truncated": "yes" if self.truncated else "no",
        }


def _names(db: Session, sql: str, company_id: str) -> tuple[list[str], bool]:
    rows = db.execute(text(sql), {"c": company_id, "n": NAME_CAP + 1}).scalars().all()
    truncated = len(rows) > NAME_CAP
    return [r for r in rows[:NAME_CAP] if r], truncated


def build(db: Session, company_id: str, phrase: str, today: date) -> ModelContext:
    """The context block for one request, scoped to one tenant.

    ⚠️ THREE QUERIES, EACH SELECTING A SINGLE COLUMN. Selecting rows and picking a field
    off them would put the rest of the row one attribute access away from the prompt;
    selecting the column means there is nothing else in hand to send.
    """
    homes, t1 = _names(
        db,
        "SELECT name FROM customers WHERE company_id = :c AND is_active = true "
        "ORDER BY name LIMIT :n",
        company_id,
    )
    cems, t2 = _names(
        db,
        "SELECT CASE WHEN city IS NULL OR city = '' THEN name "
        "ELSE name || ', ' || city END "
        "FROM cemeteries WHERE company_id = :c ORDER BY name LIMIT :n",
        company_id,
    )
    # ⚠️ THE TENANT'S OWN PRODUCTS, NOT THE PLATFORM CATALOG. `stage.matches` compares
    # `question.vault` against the vault name on the ORDER, which came from the tenant's
    # `products` row. Sending the 29 platform variants would offer names no order of
    # this tenant's can carry.
    vaults, t3 = _names(
        db,
        "SELECT name FROM products WHERE company_id = :c AND is_active = true "
        "ORDER BY name LIMIT :n",
        company_id,
    )
    return ModelContext(
        today=today.isoformat(),
        phrase=phrase,
        funeral_homes=homes,
        cemeteries=cems,
        vaults=vaults,
        truncated=t1 or t2 or t3,
    )
