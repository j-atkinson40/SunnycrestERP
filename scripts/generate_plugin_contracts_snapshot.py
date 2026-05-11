#!/usr/bin/env python3
"""R-8.y.d — codegen: PLUGIN_CONTRACTS.md → JSON snapshot.

Parses the 24-category canonical 8-section structure of PLUGIN_CONTRACTS.md
into a structured JSON snapshot committed at
`frontend/src/lib/plugin-registry/plugin-contracts-snapshot.json` so the
admin browser can import it at build time.

Idempotent: re-running over an unchanged source produces byte-identical
JSON (sorted keys, deterministic ordering).

CI verifies the committed snapshot matches what this script would
generate. PRs modifying PLUGIN_CONTRACTS.md MUST regenerate + commit
the snapshot or the test_plugin_contracts_snapshot.py gate fails.

Architectural pattern: documentation-as-canonical-data — canonical
platform documentation generates structured snapshots consumed by
tooling. PLUGIN_CONTRACTS.md is the first instance.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "PLUGIN_CONTRACTS.md"
OUTPUT = (
    REPO_ROOT
    / "frontend"
    / "src"
    / "lib"
    / "plugin-registry"
    / "plugin-contracts-snapshot.json"
)

# Canonical 8-section structure per category. Each category emits one
# subsection per heading. Order is documented at PLUGIN_CONTRACTS.md
# Document conventions.
CANONICAL_SUBSECTIONS = [
    "Purpose",
    "Input Contract",
    "Output Contract",
    "Guarantees",
    "Failure Modes",
    "Configuration Shape",
    "Registration Mechanism",
    "Current Implementations",
    "Cross-References",
]

# Optional subsections that some categories carry.
OPTIONAL_SUBSECTIONS = [
    "Current Divergences from Canonical",
    "Frontend-backend symmetry contract",
]


@dataclass
class ContractCategory:
    section_number: int
    title: str
    maturity_badge: str
    maturity_group: str  # "canonical" | "partial" | "implicit"
    anchor: str
    purpose: str
    summary: str
    input_contract: str
    output_contract: str
    guarantees: str
    failure_modes: str
    configuration_shape: str
    registration_mechanism: str
    current_implementations: str
    cross_references: str
    current_divergences: str = ""
    optional_subsections: dict[str, str] = field(default_factory=dict)
    tier_hint: str = ""


@dataclass
class ContractSnapshot:
    schema_version: int
    document_version: str
    total_count: int
    canonical_count: int
    partial_count: int
    implicit_count: int
    categories: list[ContractCategory]


def _classify_maturity(badge: str) -> str:
    """Map a maturity badge to a group label.

    The badge strings from PLUGIN_CONTRACTS.md TOC entries:
      ✓ canonical
      ✓ canonical — reclassified R-8.y.b investigation
      ~ partial — see Current Divergences
      ~ implicit pattern
    """
    if "implicit" in badge.lower():
        return "implicit"
    if "partial" in badge.lower():
        return "partial"
    if "canonical" in badge.lower():
        return "canonical"
    return "implicit"


def _slugify_anchor(section_number: int, title: str) -> str:
    """Match the GitHub-style anchor used by the TOC.

    e.g. "1. Intake adapters" → "1-intake-adapters"
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    return f"{section_number}-{slug}"


def _extract_summary(purpose: str) -> str:
    """First sentence or two from Purpose, capped at ~280 chars."""
    if not purpose:
        return ""
    # Split into sentences crudely on `. ` followed by a capital letter
    # OR newline boundaries. Cheap heuristic; PLUGIN_CONTRACTS.md prose
    # is consistent enough that this works.
    text = purpose.strip().split("\n\n", 1)[0]
    text = " ".join(text.split())  # collapse whitespace
    if len(text) <= 320:
        return text
    cut = text.rfind(". ", 0, 320)
    if cut < 80:
        cut = 320
    return text[: cut + 1].rstrip()


def _classify_tier(registration_mechanism: str) -> str:
    """Heuristic tier classification from Registration Mechanism prose.

    Returns:
      "R1" — explicit register API (side-effect import + register call)
      "R2" — frozen constant / dict literal
      "R3" — partial: registered table without register API
      "R4" — if/elif dispatch chain, no runtime registry
      ""   — unknown
    """
    rm = registration_mechanism.lower()
    if not rm:
        return ""
    if "register_" in rm and "side-effect" in rm:
        return "R1"
    if "register_" in rm and "import" in rm:
        return "R1"
    if "module-level dict" in rm or "module-level mapping" in rm:
        return "R2"
    if "frozenset" in rm or "frozen constant" in rm:
        return "R2"
    if "if/elif" in rm or "dispatch chain" in rm or "elif" in rm:
        return "R4"
    if "register_" in rm:
        return "R1"
    if "check constraint" in rm and "register" not in rm:
        return "R3"
    return ""


def _parse_toc(lines: list[str]) -> dict[int, str]:
    r"""Parse the TOC to extract the maturity badge per section number.

    The TOC entries are markdown list items with this shape:
      `1. [Intake adapters](#1-intake-adapters) ` `\`[✓ canonical]\``
    """
    badges: dict[int, str] = {}
    in_toc = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Table of Contents":
            in_toc = True
            continue
        if in_toc and stripped.startswith("## "):
            break
        if not in_toc:
            continue
        # Look for entries of the form `N. [Title](#...) \`[badge]\``
        m = re.match(
            r"^\d+\.\s+\[([^\]]+)\]\(#(\d+)-[^\)]+\)\s+`\[([^\]]+)\]`",
            stripped,
        )
        if m:
            section_number = int(m.group(2))
            badges[section_number] = m.group(3).strip()
    return badges


def _parse_categories(
    lines: list[str], badges: dict[int, str]
) -> list[ContractCategory]:
    """Parse each `## N. Title` section into a ContractCategory."""
    categories: list[ContractCategory] = []

    # Find all `## N. Title` lines + their positions.
    section_starts: list[tuple[int, int, str]] = []  # (line_idx, num, title)
    for i, line in enumerate(lines):
        m = re.match(r"^## (\d+)\.\s+(.+?)\s*$", line)
        if m:
            section_starts.append((i, int(m.group(1)), m.group(2).strip()))

    # Bound the parse: stop at the appendix.
    appendix_idx = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "## Cross-category patterns appendix":
            appendix_idx = i
            break

    for idx, (start_line, num, title) in enumerate(section_starts):
        # Determine end of this section: next section start or appendix.
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1][0]
        else:
            end_line = appendix_idx

        section_lines = lines[start_line:end_line]
        badge = badges.get(num, "")
        maturity_group = _classify_maturity(badge)
        anchor = _slugify_anchor(num, title)

        # Parse subsections via `### Subsection`.
        subsection_content: dict[str, str] = {}
        current: str | None = None
        buf: list[str] = []
        for line in section_lines[1:]:  # skip the `## N. Title` line
            sm = re.match(r"^###\s+(.+?)\s*$", line)
            if sm:
                if current is not None:
                    subsection_content[current] = "\n".join(buf).strip()
                current = sm.group(1).strip()
                buf = []
                continue
            # Stop at `---` separator between categories.
            if line.strip() == "---":
                continue
            buf.append(line.rstrip())
        if current is not None:
            subsection_content[current] = "\n".join(buf).strip()

        # Some sections combine "Current Implementations + Cross-References"
        # under a single heading. Detect + duplicate the content into both
        # canonical slots so the snapshot stays uniform.
        combined = subsection_content.get(
            "Current Implementations + Cross-References", ""
        ).strip()
        if combined:
            subsection_content.setdefault(
                "Current Implementations", combined
            )
            subsection_content.setdefault("Cross-References", combined)

        purpose = subsection_content.get("Purpose", "").strip()
        input_contract = subsection_content.get("Input Contract", "").strip()
        output_contract = subsection_content.get("Output Contract", "").strip()
        guarantees = subsection_content.get("Guarantees", "").strip()
        failure_modes = subsection_content.get("Failure Modes", "").strip()
        config_shape = subsection_content.get("Configuration Shape", "").strip()
        reg_mech = subsection_content.get("Registration Mechanism", "").strip()
        cur_impls = subsection_content.get(
            "Current Implementations", ""
        ).strip()
        cross_refs = subsection_content.get("Cross-References", "").strip()
        cur_div = subsection_content.get(
            "Current Divergences from Canonical", ""
        ).strip()
        # Also accept the alternate divergences heading.
        if not cur_div:
            cur_div = subsection_content.get(
                "Current Divergences", ""
            ).strip()

        # Collect optional subsections not in the canonical 8-set.
        canonical_set = set(CANONICAL_SUBSECTIONS) | {
            "Current Divergences from Canonical",
            "Current Divergences",
        }
        optional = {
            k: v
            for k, v in subsection_content.items()
            if k not in canonical_set
        }

        category = ContractCategory(
            section_number=num,
            title=title,
            maturity_badge=badge,
            maturity_group=maturity_group,
            anchor=anchor,
            purpose=purpose,
            summary=_extract_summary(purpose),
            input_contract=input_contract,
            output_contract=output_contract,
            guarantees=guarantees,
            failure_modes=failure_modes,
            configuration_shape=config_shape,
            registration_mechanism=reg_mech,
            current_implementations=cur_impls,
            cross_references=cross_refs,
            current_divergences=cur_div,
            optional_subsections=optional,
            tier_hint=_classify_tier(reg_mech),
        )
        categories.append(category)

    return categories


def _parse_document_version(lines: list[str]) -> str:
    for line in lines[:30]:
        if line.startswith("**Document version**"):
            m = re.search(r"\*\*Document version\*\*:\s*([\d.]+)", line)
            if m:
                return m.group(1)
    return "unknown"


def parse_contracts(source_text: str) -> ContractSnapshot:
    lines = source_text.split("\n")
    badges = _parse_toc(lines)
    categories = _parse_categories(lines, badges)

    canonical = sum(1 for c in categories if c.maturity_group == "canonical")
    partial = sum(1 for c in categories if c.maturity_group == "partial")
    implicit = sum(1 for c in categories if c.maturity_group == "implicit")

    return ContractSnapshot(
        schema_version=1,
        document_version=_parse_document_version(lines),
        total_count=len(categories),
        canonical_count=canonical,
        partial_count=partial,
        implicit_count=implicit,
        categories=categories,
    )


def generate(write: bool = True) -> dict:
    """Generate the snapshot dict. Write to disk if write=True."""
    if not SOURCE.exists():
        raise FileNotFoundError(f"PLUGIN_CONTRACTS.md not found at {SOURCE}")
    text = SOURCE.read_text(encoding="utf-8")
    snapshot = parse_contracts(text)
    payload = asdict(snapshot)
    if write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        # sort_keys=True for byte-identical re-runs. indent=2 for
        # reviewer readability in PRs.
        OUTPUT.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    return payload


if __name__ == "__main__":
    payload = generate(write=True)
    print(
        f"Wrote {OUTPUT} — {payload['total_count']} categories "
        f"({payload['canonical_count']} canonical / "
        f"{payload['partial_count']} partial / "
        f"{payload['implicit_count']} implicit), "
        f"document version {payload['document_version']}"
    )
