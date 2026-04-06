"""Duplicate clustering for unified import staging data.

Uses name similarity, geography, and phone matching with union-find
to build merge clusters.
"""

import logging
import re
import uuid
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models.import_staging_company import ImportStagingCompany

logger = logging.getLogger(__name__)

# ── Name normalization ─────────────────────────────────────────────

_SUFFIXES_TO_STRIP = [
    " funeral home", " funeral chapel", " funeral service", " funeral services",
    " mortuary", " chapel", " fh", " f.h.",
    " cemetery", " cem", " memorial gardens", " memorial park", " memorial", " gardens",
    " inc.", " inc", " llc", " corp", " co.", " co",
    "& sons", "& son",
]

_PHONE_RE = re.compile(r"\D")


def normalize_name(name: str) -> str:
    """Strip common business suffixes for comparison."""
    n = name.lower().strip()
    for suffix in _SUFFIXES_TO_STRIP:
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


def normalize_phone(phone: str | None) -> str | None:
    """Strip non-digits from phone for comparison."""
    if not phone:
        return None
    digits = _PHONE_RE.sub("", phone)
    # Keep last 10 digits (strip country code)
    if len(digits) > 10:
        digits = digits[-10:]
    return digits if len(digits) >= 7 else None


def _name_similarity(a: str, b: str) -> float:
    """Max of raw and normalized name similarity."""
    raw = SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
    norm = SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()
    return max(raw, norm)


# ── Union-Find ─────────────────────────────────────────────────────

class _UnionFind:
    """Simple union-find with path compression."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


# ── Cluster scoring ────────────────────────────────────────────────

def _primary_score(row: ImportStagingCompany) -> int:
    """Score a staging row for cluster primary selection."""
    score = 0
    if row.matched_sources and len(row.matched_sources) > 0:
        score += 3
    score += min(row.order_count or 0, 10) * 2
    if row.city:
        score += 1
    if row.phone:
        score += 1
    if row.email:
        score += 1
    if row.name and row.name == row.name.upper() and len(row.name) > 3:
        score -= 1  # All-caps penalty
    if row.name and len(row.name) < 5:
        score -= 1  # Very short name penalty
    return score


# ── Main clustering ────────────────────────────────────────────────

def cluster_duplicates(db: Session, session_id: str) -> dict:
    """Build duplicate clusters from staging companies.

    Returns summary dict with cluster count and sizes.
    """
    rows = (
        db.query(ImportStagingCompany)
        .filter(ImportStagingCompany.session_id == session_id)
        .all()
    )

    if not rows:
        return {"clusters_found": 0, "total_records_in_clusters": 0}

    # Build pairwise similarity and cluster via union-find
    uf = _UnionFind()
    row_map = {r.id: r for r in rows}
    ids = list(row_map.keys())

    for i in range(len(ids)):
        a = row_map[ids[i]]
        if not a.name:
            continue
        for j in range(i + 1, len(ids)):
            b = row_map[ids[j]]
            if not b.name:
                continue

            # ── Geography hard-zero for cemeteries in different cities
            if (
                a.suggested_type == "cemetery"
                and b.suggested_type == "cemetery"
                and a.city
                and b.city
                and a.city.lower().strip() != b.city.lower().strip()
            ):
                continue

            # ── Name score
            name_score = _name_similarity(a.name, b.name)

            # ── City match
            city_score = 0.5  # neutral if unknown
            if a.city and b.city:
                if a.city.lower().strip() == b.city.lower().strip():
                    city_score = 1.0
                else:
                    city_score = 0.0
                    name_score *= 0.4  # heavy penalty for different known cities

            # ── Phone match
            phone_score = 0.0
            pa, pb = normalize_phone(a.phone), normalize_phone(b.phone)
            if pa and pb and pa == pb:
                phone_score = 1.0

            final_score = name_score * 0.55 + city_score * 0.30 + phone_score * 0.15

            if final_score >= 0.75:
                uf.union(a.id, b.id)

    # ── Build cluster groups from union-find ───────────────────────
    clusters: dict[str, list[str]] = {}
    for rid in ids:
        root = uf.find(rid)
        if root not in clusters:
            clusters[root] = []
        clusters[root].append(rid)

    # Filter to only real clusters (2+ members)
    real_clusters = {k: v for k, v in clusters.items() if len(v) >= 2}

    # ── Assign cluster_id and primary ──────────────────────────────
    total_clustered = 0
    for members in real_clusters.values():
        cid = str(uuid.uuid4())
        best_score = -999
        best_id = members[0]
        for mid in members:
            row = row_map[mid]
            s = _primary_score(row)
            if s > best_score:
                best_score = s
                best_id = mid

        for mid in members:
            row = row_map[mid]
            row.cluster_id = cid
            row.is_cluster_primary = mid == best_id
            total_clustered += 1

    db.flush()

    return {
        "clusters_found": len(real_clusters),
        "total_records_in_clusters": total_clustered,
    }
