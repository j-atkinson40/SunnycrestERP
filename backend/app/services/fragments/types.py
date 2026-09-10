"""Fragment contract types — the substrate the note surface renders.

Per DECISIONS 2026-09-04 ("Monitor is a daily note, not a dashboard" and
"Prose fragments declare four things or they don't ship").

⚠️ THE PAYLOAD IS A RENAME, NOT A REBUILD. `FragmentPayload` below is
`IntelligenceStream` from `frontend/src/types/pulse.ts:64-71` and
`app/services/pulse/types.py`, under fragment terminology. It already carried
`synthesized_text` + `referenced_items {kind, entity_id, label, href}` +
`priority`, and `AnomalyIntelligenceStream.tsx` already renders it as prose with
inline chips. The salvage investigation (`docs/investigations/2026-09-04-pulse-
salvage.md`) established that the body was correct and the DECLARATIONS were
what was missing. This module adds the declarations; it does not re-invent the
body.

──────────────────────────────────────────────────────────────────────────
THE FOUR DECLARATIONS

A fragment type that cannot express all four does not register. The enforcement
lives in `registry.register_fragment`; these types exist so that the four are
structurally impossible to omit rather than merely documented.

  (1) AUDIENCE       — `Audience`, evaluated against the EXISTING permission
                       system. Lacking the permission means the fragment DOES
                       NOT EXIST for that user; it is never emitted inert.
  (2) CONDITION      — a callable yielding zero or more `FragmentInstance`,
                       each carrying `condition_inputs` — enumerable and
                       snapshottable, because the surface arc's deferral wakes
                       a deferred prompt on divergence of those inputs. This
                       module builds the enumeration; the wake logic is surface
                       arc work.
  (3) TARGET + SCOPE — `target_surface` + `target_key` are type-level (what
                       kind of thing this opens); `FragmentInstance.scope` is
                       instance-level and REQUIRED NON-EMPTY. A scheduling
                       fragment opens the scheduling Focus already scoped to
                       tomorrow. An href with no scope carry does not satisfy
                       this declaration and is rejected at emission.
  (4) END TRANSITION — required for `kind="prompt"`, forbidden for
                       `kind="non_prompt"`. See the asymmetry note below.

──────────────────────────────────────────────────────────────────────────
PROMPT vs NON-PROMPT, AND THE EXIT ASYMMETRY

`kind="prompt"` — something a person must resolve. Per DECISIONS 2026-09-04
("Prompts leave the note by resolution or dated deferral, never silently"),
there is no "make this go away." A prompt therefore has NO dismiss path.

`kind="non_prompt"` — anomalies, insights, ambient observation. These exit by
dismiss, and `signal_service`'s existing dismiss inputs continue to serve them.

⚠️ A PROMPT CURRENTLY HAS NO EXIT AT ALL. Deferral is surface-arc work, so in
this sub-arc a prompt exits only by its declared end transition actually
occurring. That is correct for a substrate with no users and no rendering, and
it is the reason the surface arc follows immediately rather than being parked:
the contract cannot ship to a person in this state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Sequence

#: What a fragment opens. `window` is the floating-tablet surface; `peek` is the
#: transient hover/long-press layer; `focus` is the bounded-decision surface.
TargetSurface = Literal["peek", "focus", "window"]

#: Prompt fragments demand resolution. Non-prompt fragments inform.
FragmentKind = Literal["prompt", "non_prompt"]


class FragmentDeclarationError(ValueError):
    """A fragment type failed to declare one of the four. It does not register.

    Raised at REGISTRATION time, not at emission time, so a malformed fragment
    type fails at import rather than in front of a user.
    """


@dataclass(frozen=True)
class ReferencedItem:
    """One typed link inside a fragment's prose.

    Renamed from `pulse.types.ReferencedItem`, shape unchanged. Per DECISIONS
    2026-09-04 ("Three text states"), a referenced item is MEASURED text — the
    link is the provenance mark. Unlinked prose is connective tissue or
    inference, and the two are distinguished typographically, never by color.
    """

    kind: str
    entity_id: str
    label: str
    href: str | None = None


@dataclass(frozen=True)
class FragmentPayload:
    """The fragment body. Renamed from `IntelligenceStream`; shape unchanged.

    `synthesized_text` is the prose. `referenced_items` are its measured
    claims. `priority` is the urgency ordering the note composes on — higher
    surfaces first.
    """

    title: str
    synthesized_text: str
    referenced_items: tuple[ReferencedItem, ...] = ()
    priority: int = 50

    #: ⚠️ THE THREE TEXT STATES, added session 2. Typed spans rather than
    #: substring markers: marking "the label" inside a sentence where the label
    #: occurs twice puts the mark in the wrong place and nothing looks wrong.
    #: Empty for payloads built before spans existed; `synthesized_text` remains
    #: the single source every current consumer reads, and is DERIVED from the
    #: spans when they are present so the two cannot drift.
    #: See `fragments/synthesis.py`.
    spans: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Audience:
    """(1) AUDIENCE — a permission predicate over the EXISTING system.

    These are the same three gates `command_bar.registry.ActionRegistryEntry`
    declares and `command_bar.retrieval` applies, which in turn mirror
    `vault.hub_registry`'s VaultServiceDescriptor semantics. Evaluation reads
    `permission_service.user_has_permission` and `module_service.
    is_module_enabled`. No parallel permission system is introduced.

    ⚠️ `Audience.any_authenticated()` is an EXPLICIT declaration, not a default.
    A fragment type must say who sees it; saying "any authenticated tenant user"
    is a valid answer and must be stated, matching `triage.platform_defaults`'s
    `permissions=[]  # any authenticated tenant user`.
    """

    required_permission: str | None = None
    required_module: str | None = None
    required_extension: str | None = None

    @classmethod
    def any_authenticated(cls) -> "Audience":
        return cls()


@dataclass(frozen=True)
class Outcome:
    """One way a prompt can end, and the words for that ending.

    ⚠️ `key` IS MATCHED AGAINST A STRUCTURED FIELD ON THE RECORDED EVENT, never
    against prose. A settled record is what someone reads a week later as
    evidence of what they did; selecting its wording by substring-matching a
    note a human typed would put that record downstream of free text. This
    surface already rejected substring marking for spans, for the same reason
    and one layer up.
    """

    #: The structured discriminator. Matched against the outcome the resolving
    #: act RECORDED — a terminal state, an enum value — not parsed from a note.
    key: str
    #: This ending's own past tense. `{count}` and `{plural}` interpolate.
    past_tense: str


@dataclass(frozen=True)
class EndTransition:
    """(4) END TRANSITION — how a prompt ends, and what each ending reads as.

    Declarative rather than callable: the resolver reads `resolved_when` to
    decide whether a rendered prompt has been satisfied, and settling reads the
    matching `Outcome.past_tense` to render the settled note's record of what
    was done. Holding these as data rather than as a closure is what lets the
    settled note be generated from events that actually occurred rather than
    from a re-run of the condition.

    ──────────────────────────────────────────────────────────────────────
    ⚠️ OUTCOMES ARE PLURAL, AND THAT IS THE WHOLE CHANGE (2026-09-10)

    This field was a single `past_tense: str` until the settling session found
    it could not carry the note. `tasks_due_today` has FOUR terminal outcomes —
    done, cancelled, acknowledged, dismissed — and one template. A cancelled
    task resolves the prompt and was not completed.

    No phrasing fixes that. A single phrase either flattens the four ("you
    closed 4 tasks") or states one of them falsely about the other three. The
    contract had fewer slots than the world has endings.

    So a fragment now declares not just THAT it ends but HOW IT CAN END, and
    each ending carries its own words. The single-template form is deleted
    rather than deprecated: a fragment that can end two ways and says one thing
    is now unexpressible rather than merely discouraged.
    """

    #: Domain object whose state change resolves this prompt.
    entity_kind: str
    #: Declarative key the resolver dispatches on.
    resolved_when: str
    #: Every way this prompt can end. At least one; keys unique.
    outcomes: tuple[Outcome, ...]

    def outcome(self, key: str) -> Outcome | None:
        """The words for one ending, or None if this fragment cannot end that way."""
        for o in self.outcomes:
            if o.key == key:
                return o
        return None


@dataclass(frozen=True)
class FragmentInstance:
    """One emitted fragment. Produced by a declaration's condition.

    ⚠️ THERE IS NO `instance_key` FIELD, DELIBERATELY. Per DECISIONS 2026-09-04
    ("A fragment declares five things; IDENTITY is the fifth"), the key must be
    derived from what the condition is ABOUT and never from the evaluation that
    found it. A condition that could supply its own key could supply a
    run-scoped one — which is exactly the production defect this closes, where
    `base_agent` wrote `provenance_ref_id = self.job_id` and one unmapped
    vendor-bill line became 1,825 rows because nothing recognised the second
    sighting as the first.

    So the condition supplies the SUBJECT and the contract computes the key.
    See `EmittedFragment.instance_key`.

    ──────────────────────────────────────────────────────────────────────
    ⚠️ (3)'s INSTANCE HALF IS TWO FIELDS, NOT ONE (2026-09-10)

    `scope` was a single mapping until the Focus-capability arc built the first
    real scoped entrance and found it doing two jobs with different lifetimes:

      PREDICATE  — what the entrance MEANS. "Tasks due 2026-09-10 assigned to
                   this user." Survives a refresh, a deep link, and a week.
                   This is what goes in a URL.
      EXPANSION  — what that predicate HAPPENED TO SELECT when the fragment was
                   composed. The 4 task ids. Stale the moment anything changes.
                   Payload only. NEVER a URL key.

    Measured: `anomaly_ids` for five anomalies costs 355 URL-encoded characters,
    so ~30 ids reaches the practical URL ceiling and an id list is the worst
    possible thing to navigate on. And in every registered fragment the id list
    was the expansion of a predicate the same mapping already carried.

    ⚠️ SPLIT RATHER THAN CONVENTION, DELIBERATELY. The alternative was reading
    key names — `anomaly_ids` is expansion-shaped, `severity_filter` is
    predicate-shaped — which is an inference at every future declaration whose
    failure is SILENT: the entrance works, and it breaks the day someone shares
    the link or the list passes thirty. Split, an entrance declares which half
    it navigates on and an id list in a URL is unexpressible rather than
    discouraged.

    Same conflation as one column holding both `account → type` and
    `type → account`.

    `predicate` is REQUIRED NON-EMPTY. `expansion` is optional and defaults to
    empty — a fragment that selected nothing in particular has nothing to
    freeze.

    `condition_inputs` is (2)'s snapshot: the enumerable inputs that caused this
    instance to exist, which deferral diffs to wake a deferred prompt on
    divergence.
    """

    #: (5) IDENTITY — what this instance is ABOUT, stable for as long as the
    #: condition holds. The invoice id, the vendor-bill line id, the case id.
    #: A composite is fine when the subject genuinely is one ("this user, this
    #: day"); a run id, a job id, or a timestamp of evaluation is not.
    subject_id: str
    payload: FragmentPayload
    #: What the entrance MEANS. URL-carryable, re-derivable, required non-empty.
    predicate: Mapping[str, Any]
    #: What the predicate SELECTED at composition. Payload; never a URL key.
    #: ⚠️ The settled note is exactly where this is correct and the predicate
    #: would lie — a record must not re-derive.
    expansion: Mapping[str, Any] = field(default_factory=dict)
    condition_inputs: Mapping[str, Any] = field(default_factory=dict)


#: A condition is `(db, *, user) -> Sequence[FragmentInstance]`. Zero instances
#: is a correct and common answer — DECISIONS 2026-09-04 ("two registers"): a
#: three-line note on a quiet day is correct behavior, not a failure.
ConditionFn = Callable[..., Sequence[FragmentInstance]]


@dataclass(frozen=True)
class FragmentDeclaration:
    """A registered fragment type. All four declarations are structural.

    OWNED BY THIS MODULE, in the manner of `ActionRegistryEntry`. Later arcs
    extend it with new fields; they do not redefine it.
    """

    fragment_id: str
    label: str
    kind: FragmentKind

    # (1) AUDIENCE
    audience: Audience

    # (2) CONDITION
    condition: ConditionFn

    # (3) TARGET — type-level half; the scope half is per-instance.
    target_surface: TargetSurface
    target_key: str

    # (5) IDENTITY — the type-level half. Names the KIND of thing instances of
    # this fragment are about ("invoice", "vendor_bill_line", "user_day"). The
    # per-instance half is `FragmentInstance.subject_id`, and the key is the
    # two composed. Declaring it forces the author to answer "what is this
    # fragment about?" at registration rather than discovering at deferral time
    # that the answer was "the run that found it".
    subject_kind: str = ""

    # (4) END TRANSITION — required iff kind == "prompt".
    end_transition: EndTransition | None = None

    #: Free-form, registry-opaque. Mirrors ActionRegistryEntry.metadata.
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def dismissible(self) -> bool:
        """Only non-prompt fragments may be dismissed.

        Per DECISIONS 2026-09-04: "There is no 'make this go away.'" The salvage
        investigation found `LayerItem.dismissed` + `DismissSignalRequest`
        shipped and applying to everything; this property is where that stops
        applying to prompts.
        """
        return self.kind == "non_prompt"
