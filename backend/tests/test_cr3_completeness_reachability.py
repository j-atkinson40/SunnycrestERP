"""CR-3 — can the person the review was built for actually get to it.

⚠️ THE ARC WAS SCOPED AROUND THE INTERNAL ACCOUNTANT AND THE ACCOUNTANT COULD
NOT OPEN IT. `/vault/accounting/completeness` sat inside V-1e's admin-only
accounting subtree (`ba424db6`, April 2026) because that is where CR-2 A-4
mounted it — an inherited gate, not a chosen one. The comment beside it justified
the gate by parity with "the gate the backend uses on every endpoint under
/api/v1/vault/accounting/*", which is true of the six configuration tabs and
false of the completeness router: it mounts at /api/v1/completeness and gates on
`get_current_user`.

Reaching a surface takes TWO things and this arc has now shipped one without the
other twice — A-3's hub mount was an import and nothing else, and A-4's endpoint
had no caller for three sub-arcs. So both halves are asserted here:

  1. the route admits the role  (frontend `ProtectedRoute anyRole`, tested there)
  2. something OFFERS it        (this file)

The Vault hub will not offer it: `hub_registry`'s accounting descriptor is
`required_permission="admin"` and the accountant role does not hold `admin` —
correctly, since six of the seven tabs really are tenant configuration. So the
pin is the offer, and without it the surface is URL-only, which is a surface
nobody finds.

Registry-only by construction: no DB, no Company rows, no litter. That is what
makes it safe to gate.
"""
from __future__ import annotations

import pytest

from app.services.spaces import registry as reg

COMPLETENESS_HREF = "/vault/accounting/completeness"

#: Both verticals Phase 8e seeded an accountant for.
ACCOUNTANT_KEYS = [("funeral_home", "accountant"), ("manufacturing", "accountant")]


class TestTheAccountantIsOfferedTheReview:
    @pytest.mark.parametrize("key", ACCOUNTANT_KEYS)
    def test_the_books_space_pins_the_completeness_review(self, key):
        templates = reg.SEED_TEMPLATES[key]
        pinned = {
            pin.target
            for tpl in templates
            for pin in tpl.pins
            if pin.pin_type == "nav_item"
        }
        assert COMPLETENESS_HREF in pinned, (
            f"{key} has no pin to the completeness review, so the accountant "
            f"reaches it only by typing the URL. Pinned nav items: {sorted(pinned)}"
        )

    @pytest.mark.parametrize("key", ACCOUNTANT_KEYS)
    def test_it_is_pinned_in_the_default_space(self, key):
        """The daily question belongs in the space they land in. A pin in the
        non-default space is reachable and not offered."""
        default = [t for t in reg.SEED_TEMPLATES[key] if t.is_default]
        assert len(default) == 1, "exactly one template is the landing space"
        assert any(
            p.pin_type == "nav_item" and p.target == COMPLETENESS_HREF
            for p in default[0].pins
        ), f"pinned somewhere other than {key}'s default space ({default[0].name})"

    def test_the_pin_resolves_to_a_label_and_an_icon(self):
        """⚠️ AN UNLABELLED PIN FALLS BACK TO `(href, "Link")` — it renders, so
        nothing fails, and the sidebar shows a raw path. The general form of this
        is already gated by `test_spaces_phase8e.py::TestNavLabelCoverage`;
        stated again here because THIS href is the one CR-3 depends on."""
        got = reg.get_nav_label(COMPLETENESS_HREF)
        assert got is not None, f"{COMPLETENESS_HREF} is missing from NAV_LABEL_TABLE"
        label, icon = got
        assert label and icon

    def test_the_icon_is_one_the_sidebar_can_render(self):
        """⚠️ AN ICON THE FRONTEND DOES NOT KNOW FALLS BACK TO `Layers` SILENTLY
        — CLAUDE.md names this as a visual bug with no failure. There is no
        mechanism holding the Python table and `PinnedSection.ICON_MAP` together
        (the label side has one; the icon side does not), so this asserts the one
        icon CR-3 introduces against the known-rendered set rather than trusting
        that someone remembered.

        The general guard is a cross-language check and is NOT built here — see
        the CR-3 report. This is a spot weld, and it says so.
        """
        known = {
            "BarChart3", "Bell", "BookOpen", "Building2", "Calculator",
            "Calendar", "CheckSquare", "ClipboardCheck", "Factory", "FileCheck",
            "FileText", "FolderOpen", "Home", "Kanban", "Layers",
            "LayoutDashboard", "Link", "ListChecks", "MapPin", "Phone", "Plus",
            "Receipt", "Scale", "ShieldCheck", "ShoppingBag", "Store",
            "TrendingUp", "Truck", "Users", "Wrench", "Zap",
        }
        _, icon = reg.get_nav_label(COMPLETENESS_HREF)
        assert icon in known, (
            f"{icon!r} is not in PinnedSection.ICON_MAP — the pin will render "
            f"the generic Layers icon and nothing will fail"
        )


class TestTheHubStillShapesAccountingAsAdminConfiguration:
    def test_the_vault_service_stays_admin_gated(self):
        """⚠️ ASSERTED, NOT ASSUMED — AND DELIBERATELY NOT CHANGED. Opening the
        Accounting service to the accountant would put six configuration tabs
        they cannot open into their Vault nav. The pin is the narrower correction
        and this pins the shape it depends on: if someone later relaxes the
        descriptor, the pin becomes a duplicate offer and this test says so.
        """
        from app.services.vault import hub_registry

        services = hub_registry.list_services()
        assert services, "the hub registry is empty; this test proves nothing"
        svc = next(s for s in services if s.service_key == "accounting")
        assert svc.required_permission == "admin", (
            "the Accounting Vault service is no longer admin-gated — the "
            "accountant now reaches it twice, and the six configuration tabs "
            "beside Completeness are in their nav"
        )
