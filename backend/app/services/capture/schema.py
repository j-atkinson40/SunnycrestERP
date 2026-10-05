"""The capture schema — what this tenant asks for on an order.

⚠️ REQUIRED MEANS ANSWERED, NOT FILLED. A required field is one that must be
ANSWERED. `none` is a valid answer and clears the requirement. A drop-off with
no equipment is answered; an order where equipment was never mentioned is not.
That is what makes the missing set checkable: an answer set defines what counts
as answered, so "answered" is a property of the data rather than a judgment.
Ruled 2026-09-22, `Required means answered, not filled`.

⚠️ A FIELD SWITCHED OFF IS NEVER ASKED AND NEVER MISSING. Tenant configuration
sits over a platform default. A tenant that does not take grave locations
switches the field off, and it leaves the schema entirely — it is not a required
field that is permanently unsatisfied, and it is not an optional field that
nags. Ruled 2026-09-22, `Capture fields are tenant-configurable over a platform
default`.

⚠️ THE VAULT CANNOT BE SWITCHED OFF, and the reason is mechanical rather than
editorial: personalization availability is read per product, so without a vault
there is no product to read availability from and the conditional questions
cannot be resolved at all. `switchable=False` on that one field is what keeps
`resolve_schema` total.

⚠️ CONDITIONAL QUESTIONS ARE NOT PROPERTIES OF THE ORDER. Whether personalization
is required depends on whether this licensee offers it on the vault named —
Sunnycrest does not offer nameplates on the Monticello where neighbouring
licensees do. The answer is the licensee's decision about that vault and is
stored with the licensee, read through `personalization.availability`. Ruled
2026-09-22, `Conditional requirements are determined by the vault, not stored on
it`.

⚠️ NOT CONFIGURED MEANS ASK. A licensee who has said nothing has said nothing.
Only a licensee who has said "none" has said none. `NOT_CONFIGURED` therefore
resolves to APPLIES, not to skipped — the opposite choice would silently stop
asking about every vault of every licensee who has not finished configuring,
which is currently all of them (`wilbert_program_enrollments` holds zero rows on
production as of 2026-09-22).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from app.services.personalization.availability import (
    AvailabilityState,
    read_availability,
)
from app.services.personalization.questions import QUESTIONS

#: The one field that may not be switched off. See the module docstring.
VAULT_FIELD_ID = "vault"


#: ⚠️ REVIEW LAYOUT IS UNBUILT, AND THIS NOTE EXISTS SO ITS ABSENCE IS NOT
#: MISTAKEN FOR ITS PRESENCE. DECISIONS 2026-10-02 says a template declares four
#: things: its fields, which are required, what each field depends on, AND ITS
#: REVIEW LAYOUT. The first three are below. The fourth has no representation
#: anywhere — measured 2026-10-05, zero hits for `summary_layout` / `review
#: layout` / `summaryLayout` across `backend/app` and `frontend/src`.
#:
#: Today the review layout is encoded as JSX per card in `CallOverlay.tsx`, which
#: is why two surfaces render two different field lists. Giving it a
#: representation is NET-NEW DESIGN, not a reshape of anything here, and it is
#: not blocking a second template — a template can declare fields today and
#: inherit whatever rendering the surface does.
#:
#: A reader asking "does a template carry its layout?" should get `no, and
#: deliberately not yet` from this file rather than infer `yes` from the canon
#: entry.


@dataclass(frozen=True)
class FieldDefinition:
    """One thing an order is asked for.

    `required` is about whether an ANSWER is needed, never about whether a value
    is non-empty — see the module docstring.
    """

    field_id: str
    label: str
    required: bool = True
    #: False only for the vault. Everything else a tenant may turn off.
    switchable: bool = True
    #: Set for the three personalization questions. When present the field
    #: applies only if the named vault offers that question.
    #:
    #: ⚠️ THIS IS ONE CONDITIONAL SHAPE, NOT THE CONDITIONAL MECHANISM, and a
    #: SECOND SHAPE IS ALREADY KNOWN. Recorded here so Piece 4's generalisation
    #: is derived from two cases rather than from the only one anyone had looked
    #: at — which is the failure this arc has been cataloguing.
    #:
    #:   1. PERSONALIZATION (built, this field). Depends on an EXTERNAL
    #:      AVAILABILITY LOOKUP: `read_availability(personalization_config,
    #:      vault_product_id, question_id)` reads the licensee's config for the
    #:      named vault. The condition's input is outside the capture payload,
    #:      and resolving it needs a product id the payload does not carry.
    #:
    #:   2. `service_location_other` (NOT BUILT — do not add it as a plain
    #:      field). Applies only when `service_location == "other"`. Depends on
    #:      ANOTHER FIELD'S VALUE IN THE SAME TEMPLATE. No external lookup, no
    #:      product id, and resolvable from the extracted values alone — which
    #:      `resolve_schema` never sees, because it resolves the schema BEFORE
    #:      `evaluate` compares anything against it.
    #:
    #: ⚠️ That ordering is the real obstacle, and it is why shape 2 is not a
    #: small addition. Shape 1 is answerable from configuration at schema-resolve
    #: time; shape 2 is answerable only from the answers, so a mechanism covering
    #: both cannot resolve applicability once, up front, the way this one does.
    #:
    #: A third shape — tenant setting, user role, time of day, another object's
    #: state — should cost one declaration, and the proposal must say what it
    #: would cost rather than assume it is free.
    question_id: str | None = None

    @property
    def is_conditional(self) -> bool:
        return self.question_id is not None


def _personalization_fields() -> tuple[FieldDefinition, ...]:
    """⚠️ DERIVED FROM `QUESTIONS`, NOT TYPED OUT. A hand-written copy is a second
    list that can drift from the first; `questions.py` already makes the same
    argument for the vinyl answer ids. Adding a question adds a capture field.
    """
    return tuple(
        FieldDefinition(
            field_id=q.question_id,
            label=q.display_label,
            required=True,
            switchable=True,
            question_id=q.question_id,
        )
        for q in QUESTIONS
    )


#: What every tenant is asked for before it configures anything.
PLATFORM_DEFAULT_FIELDS: tuple[FieldDefinition, ...] = (
    FieldDefinition(VAULT_FIELD_ID, "Vault", switchable=False),
    FieldDefinition("funeral_home", "Funeral home"),
    FieldDefinition("deceased_name", "Deceased name"),
    FieldDefinition("vault_size", "Size"),
    FieldDefinition("cemetery", "Cemetery"),
    FieldDefinition("burial_date", "Burial date"),
    FieldDefinition("burial_time", "Burial time"),
    FieldDefinition("grave_location", "Grave section / lot / space"),
) + _personalization_fields()


#: Object type -> the platform-default field set for that type.
#:
#: ⚠️ A REGISTRY RATHER THAN A SECOND TUPLE. `resolve_schema` already takes
#: `platform_fields` as a keyword, so keying by object type adds a mapping and
#: changes neither that signature nor `PLATFORM_DEFAULT_FIELDS`'s contents. The
#: second object type is then a row here, not a refactor — which is what
#: DECISIONS 2026-10-02 "One capture engine, one template per object type"
#: requires. Sales order is the only entry today; quote, purchase order, email,
#: text message and calendar event each need their own template and have none
#: anywhere in the codebase.
#:
#: ⚠️ RENAMED FROM `FUNERAL_ORDER` / `"funeral_order"` ON 2026-10-05, BY RULING.
#: The warrant: the call-to-order flow captures an order which then appears on
#: the note for scheduling and is rendered by the sales-order surface — ONE
#: object across three surfaces, not a funeral-specific variant of one. The
#: template key is therefore the OBJECT TYPE, and what varies between tenants
#: and verticals is the FIELD SET, which is what `tenant_config` and the
#: platform/tenant split already express. That is the same shape the product
#: catalog uses: one `product_templates` row per product, tenant deltas on top.
#:
#: ⚠️ `"funeral_order"` was never one of the eight object types DECISIONS
#: 2026-10-02 enumerates (sales order, quote, purchase order, email, text
#: message, calendar event, disinterment case, time-off request), so a second
#: template added beside it would have had no sales order to sit beside. The
#: rename settles that before a second template is written rather than after.
#:
#: ⚠️ NOT TO BE CONFUSED WITH `SalesOrder.order_type == "funeral"`, which is a
#: live column VALUE distinguishing funeral from retail and wholesale orders and
#: is untouched by this rename. The capture key names the OBJECT; order_type
#: classifies an instance of it.
SALES_ORDER = "sales_order"

CAPTURE_TEMPLATES: dict[str, tuple[FieldDefinition, ...]] = {
    SALES_ORDER: PLATFORM_DEFAULT_FIELDS,
}


def template_for(object_type: str) -> tuple[FieldDefinition, ...]:
    """The platform-default fields for an object type.

    Raises rather than falling back to the funeral order: a typo that silently
    captured the wrong object's fields would be worse than a crash, and an
    unregistered type is a programming error rather than a user condition.
    """
    try:
        return CAPTURE_TEMPLATES[object_type]
    except KeyError:
        raise KeyError(
            f"no capture template for object type {object_type!r}; "
            f"registered: {sorted(CAPTURE_TEMPLATES)}"
        ) from None


class FieldNotSwitchable(ValueError):
    """Raised when configuration tries to switch off a field that may not be."""


@dataclass(frozen=True)
class TenantCaptureConfig:
    """A tenant's overlay on the platform default.

    Only deltas are stored, in the same spirit as the theme and component-config
    layers: `disabled_field_ids` names what this tenant does not ask for, and
    everything absent is inherited.
    """

    disabled_field_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        unswitchable = {
            f.field_id
            for f in PLATFORM_DEFAULT_FIELDS
            if not f.switchable and f.field_id in self.disabled_field_ids
        }
        if unswitchable:
            raise FieldNotSwitchable(
                f"these capture fields may not be switched off: "
                f"{sorted(unswitchable)}"
            )


@dataclass(frozen=True)
class ResolvedField:
    """A field that this tenant asks for on this vault."""

    definition: FieldDefinition
    #: Permitted answers when the field is a conditional question and the vault
    #: configures it. Empty for plain fields and for NOT_CONFIGURED questions,
    #: where any answer the question defines is acceptable.
    permitted_answers: tuple[str, ...] = ()

    @property
    def field_id(self) -> str:
        return self.definition.field_id

    @property
    def required(self) -> bool:
        return self.definition.required


def resolve_schema(
    *,
    vault_product_id: str | None,
    personalization_config: dict | None,
    tenant_config: TenantCaptureConfig | None = None,
    platform_fields: tuple[FieldDefinition, ...] = PLATFORM_DEFAULT_FIELDS,
) -> tuple[ResolvedField, ...]:
    """The fields that apply, in platform order.

    A field is absent from the result — not present-and-unsatisfied — when the
    tenant switched it off, or when it is a personalization question the named
    vault does not offer. Absent means never asked and never missing.

    ⚠️ `vault_product_id=None` is the before-the-vault-is-named case, not an
    error. Applicability of the conditional questions is UNKNOWN until a vault
    is named, and unknown is not shown: the capture list holds what is answered
    and what is still needed, and nothing else (ruled 2026-09-22, `The capture
    list shows only the questions that apply`). So the conditional questions are
    omitted until there is a vault to resolve them against.
    """
    config = tenant_config or TenantCaptureConfig()
    resolved: list[ResolvedField] = []

    for definition in platform_fields:
        if definition.switchable and definition.field_id in config.disabled_field_ids:
            continue

        if not definition.is_conditional:
            resolved.append(ResolvedField(definition))
            continue

        if vault_product_id is None:
            # Applicability unknown — not shown, not counted. See docstring.
            continue

        availability = read_availability(
            personalization_config, vault_product_id, definition.question_id
        )
        if availability.state is AvailabilityState.NOT_OFFERED:
            continue
        # OFFERED and NOT_CONFIGURED both apply. NOT_CONFIGURED carries no
        # permitted set, which is how "ask, but nothing constrains the answer
        # yet" is expressed.
        resolved.append(
            ResolvedField(definition, tuple(availability.permitted_answers))
        )

    return tuple(resolved)


def without_field(
    fields: tuple[FieldDefinition, ...], field_id: str
) -> tuple[FieldDefinition, ...]:
    """Test helper — a platform field list with one entry made optional.

    Kept here rather than in the tests so the `replace` call sits next to the
    dataclass it copies.
    """
    return tuple(
        replace(f, required=False) if f.field_id == field_id else f for f in fields
    )
