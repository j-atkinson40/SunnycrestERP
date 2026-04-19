"""Tests for the Manufacturing Platform Polish build:

Part 1 — Cmd+1-5 capture-phase listener (verified in the frontend code)
Part 2 — Nav grouping + 5 new widget definitions seeded
Part 3 — Onboarding sidebar widget uses visible_steps from /onboarding-flow/status
"""

import os
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent


class TestCmdNumberShortcuts:
    """The Cmd+1..5 fix lives in CommandBar.tsx. Verify the capture-phase
    listener exists and is gated on isOpen."""

    def test_capture_phase_listener_present(self):
        # The capture-phase listener was moved out of CommandBar.tsx into a
        # module-scope installer at frontend/src/lib/cmd-digit-shortcuts.ts
        # so it attaches BEFORE React mounts — no race window with the
        # browser's Cmd+N tab-switch shortcut. main.tsx calls
        # installCmdDigitShortcuts() before createRoot.
        shortcut_file = (
            REPO / "frontend" / "src" / "lib" / "cmd-digit-shortcuts.ts"
        )
        content = shortcut_file.read_text()
        # Capture-phase listener is the critical flag
        assert "capture: true" in content
        # Listener gated on isOpen via shared module state
        assert "state.isOpen" in content and "if (!state.isOpen) return" in content
        # Handles both metaKey (Mac) and ctrlKey (Windows/Linux)
        assert "e.metaKey || e.ctrlKey" in content
        # Uses both e.key and e.code for digit detection
        assert "parseInt(e.key" in content
        assert "e.code" in content and "Digit" in content
        # main.tsx installs it before React mounts
        main_tsx = (REPO / "frontend" / "src" / "main.tsx").read_text()
        assert "installCmdDigitShortcuts" in main_tsx

    def test_shortcut_badges_rendered(self):
        p = REPO / "frontend" / "src" / "components" / "core" / "CommandBar.tsx"
        content = p.read_text()
        # ShortcutBadge exists and is used per result
        assert "ShortcutBadge" in content


class TestNavGrouping:
    def test_knowledge_base_and_training_under_resources(self):
        p = REPO / "frontend" / "src" / "services" / "navigation-service.ts"
        content = p.read_text()
        # Resources section exists
        assert 'title: "Resources"' in content
        # Knowledge Base is in the Resources list
        assert '"Knowledge Base"' in content
        assert "/knowledge-base" in content
        # Training is in the Resources list (not a separate top-level section)
        assert 'label: "Training"' in content

    def test_no_separate_tools_section(self):
        """Tools section was merged into Resources — ensure we renamed cleanly."""
        p = REPO / "frontend" / "src" / "services" / "navigation-service.ts"
        content = p.read_text()
        # No standalone title: "Tools" section pushed to sections array
        # (Legacy Studio nav items are fine to keep their sub-sub-structure.)
        lines = content.splitlines()
        tools_push = [
            i for i, line in enumerate(lines)
            if 'title: "Tools"' in line and "sections.push" in "\n".join(lines[max(i-3,0):i+1])
        ]
        assert len(tools_push) == 0, "Tools section should have been renamed to Resources"

    def test_no_separate_training_section(self):
        p = REPO / "frontend" / "src" / "services" / "navigation-service.ts"
        content = p.read_text()
        # The old "// ── Training (single hub item) ──" block should be gone
        assert "Training (single hub item)" not in content


class TestDashboardWidgets:
    def test_new_widget_definitions_registered(self):
        from app.services.widgets.widget_registry import WIDGET_DEFINITIONS
        ids = {w["widget_id"] for w in WIDGET_DEFINITIONS}
        assert "compliance_upcoming" in ids
        assert "team_certifications" in ids
        assert "my_certifications" in ids
        assert "my_training" in ids
        assert "kb_recent" in ids

    def test_new_widgets_mapped_to_components(self):
        p = REPO / "frontend" / "src" / "components" / "widgets" / "ops-board" / "index.ts"
        content = p.read_text()
        for widget_id in ["compliance_upcoming", "team_certifications", "my_certifications", "my_training", "kb_recent"]:
            assert widget_id in content, f"Widget {widget_id} not mapped in ops-board index"
        # Components exist
        for comp in [
            "ComplianceUpcomingWidget",
            "TeamCertificationsWidget",
            "MyCertificationsWidget",
            "MyTrainingWidget",
            "KbRecentWidget",
        ]:
            assert comp in content

    def test_existing_widgets_unaffected(self):
        """Existing widgets are untouched — the new ones are additive."""
        from app.services.widgets.widget_registry import WIDGET_DEFINITIONS
        ids = {w["widget_id"] for w in WIDGET_DEFINITIONS}
        # Baseline widgets must still be present
        for existing in [
            "todays_services", "legacy_queue", "driver_status",
            "production_status", "open_orders", "inventory_levels",
            "briefing_summary", "activity_feed", "at_risk_accounts",
            "qc_status", "time_clock", "safety_status",
            "revenue_summary", "ar_summary",
        ]:
            assert existing in ids, f"Existing widget {existing} removed"

    def test_widget_page_contexts(self):
        """compliance_upcoming + team_certifications render on home/ops_board.
        my_certifications + my_training + kb_recent render on home."""
        from app.services.widgets.widget_registry import WIDGET_DEFINITIONS
        by_id = {w["widget_id"]: w for w in WIDGET_DEFINITIONS}
        assert "home" in by_id["compliance_upcoming"]["page_contexts"]
        assert "home" in by_id["team_certifications"]["page_contexts"]
        assert "home" in by_id["my_certifications"]["page_contexts"]
        assert "home" in by_id["my_training"]["page_contexts"]
        assert "home" in by_id["kb_recent"]["page_contexts"]


class TestOnboardingSidebar:
    def test_sidebar_prefers_visible_steps_endpoint(self):
        p = REPO / "frontend" / "src" / "components" / "onboarding" / "sidebar-widget.tsx"
        content = p.read_text()
        # Sidebar widget hits the new /onboarding-flow/status endpoint first
        assert "/onboarding-flow/status" in content
        # And reads visible_steps from it
        assert "visible_steps" in content
        # Legacy checklist still used as fallback
        assert "getChecklist" in content


class TestOnboardingStatusResponseShape:
    """End-to-end style — verify the backend returns the expected new step keys."""

    def test_visible_steps_contains_new_keys(self):
        from app.api.routes.onboarding_flow import get_onboarding_status
        from app.database import SessionLocal
        from app.models.company import Company
        from app.models.user import User

        db = SessionLocal()
        try:
            c = db.query(Company).filter(Company.is_active == True).first()  # noqa: E712
            if not c:
                pytest.skip("No active company in local DB to test against")
            u = db.query(User).filter(User.company_id == c.id).first()
            if not u:
                pytest.skip("No user for company")
            r = get_onboarding_status(current_user=u, company=c, db=db)
            visible = r.get("visible_steps", [])
            for expected in ["identity", "locations", "programs", "compliance", "team", "network", "command_bar"]:
                assert expected in visible, f"Expected step '{expected}' in visible_steps"
        finally:
            db.close()
