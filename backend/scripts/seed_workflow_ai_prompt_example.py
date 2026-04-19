"""Seed an example workflow using the Phase 3d `ai_prompt` step.

Creates a platform-global template workflow named "Process inbound
email" that demonstrates:

  1. An input step (paste email body + sender)
  2. An `ai_prompt` step (scribe.extract_first_call) that extracts
     structured fields from the body
  3. An action step (show_confirmation) that surfaces the extracted
     fields to the user for review

Intended to be:
  - A working example the Workflow Builder UI can clone into a
    tenant-scoped workflow.
  - A smoke test for the end-to-end wiring (save validation, execute
    path, output references).

Idempotent — safe to re-run. Finds the existing workflow by slug-style
name key and replaces steps.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
      python scripts/seed_workflow_ai_prompt_example.py
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models.intelligence import IntelligencePrompt  # noqa: E402
from app.models.workflow import Workflow, WorkflowStep  # noqa: E402

# Sentinel identifies the seeded workflow for idempotent re-runs.
_WORKFLOW_NAME = "Process inbound email (Example — AI Prompt)"
_EXAMPLE_PROMPT_KEY = "scribe.extract_first_call"


def seed() -> None:
    db = SessionLocal()
    try:
        # Sanity check — the referenced prompt must exist, else the workflow
        # wouldn't pass validate_ai_prompt_steps. This is a hard fail so
        # the developer sees the problem early.
        prompt = (
            db.query(IntelligencePrompt)
            .filter(IntelligencePrompt.prompt_key == _EXAMPLE_PROMPT_KEY)
            .first()
        )
        if prompt is None:
            print(
                f"ERROR: prompt {_EXAMPLE_PROMPT_KEY!r} not found. "
                f"Run scripts/seed_intelligence.py first.",
                file=sys.stderr,
            )
            sys.exit(1)

        wf = (
            db.query(Workflow)
            .filter(
                Workflow.name == _WORKFLOW_NAME,
                Workflow.company_id.is_(None),
            )
            .first()
        )
        if wf is None:
            wf = Workflow(
                id=str(uuid.uuid4()),
                company_id=None,  # platform-global template
                name=_WORKFLOW_NAME,
                description=(
                    "Example workflow demonstrating the ai_prompt step "
                    "type. Paste an email, the AI extracts structured "
                    "fields, then shows them for review."
                ),
                keywords=["example", "ai_prompt", "email extraction"],
                tier=4,  # custom-tier template so admins can inspect + clone
                vertical="funeral_home",
                trigger_type="manual",
                trigger_config={},
                is_active=True,
                is_system=False,
                icon="sparkles",
                command_bar_priority=1,
                is_coming_soon=False,
                overlay_config=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(wf)
            db.flush()
            print(f"Created workflow {wf.id} ({_WORKFLOW_NAME!r})")
        else:
            print(f"Found existing workflow {wf.id} — refreshing steps")

        # Replace steps
        db.query(WorkflowStep).filter(WorkflowStep.workflow_id == wf.id).delete()

        steps = [
            {
                "step_order": 1,
                "step_key": "ask_subject",
                "step_type": "input",
                "display_name": "Email subject",
                "config": {
                    "prompt": "What's the email subject?",
                    "input_type": "text",
                    "required": True,
                },
            },
            {
                "step_order": 2,
                "step_key": "ask_body",
                "step_type": "input",
                "display_name": "Email body",
                "config": {
                    "prompt": "Paste the email body",
                    "input_type": "text",
                    "required": True,
                },
            },
            {
                "step_order": 3,
                "step_key": "extract",
                "step_type": "ai_prompt",
                "display_name": "Extract structured fields",
                "config": {
                    "prompt_key": _EXAMPLE_PROMPT_KEY,
                    "variables": {
                        "subject": "{input.ask_subject.value}",
                        "body": "{input.ask_body.value}",
                    },
                    "store_output_as": "extraction",
                },
            },
            {
                "step_order": 4,
                "step_key": "review",
                "step_type": "output",
                "display_name": "Review extracted fields",
                "config": {
                    "action_type": "show_confirmation",
                    "message": (
                        "Extraction complete. Deceased name: "
                        "{output.extract.deceased_name} · Service date: "
                        "{output.extract.service_date}. "
                        "Execution: {output.extract._execution_id}"
                    ),
                },
            },
        ]

        for s in steps:
            db.add(
                WorkflowStep(
                    id=str(uuid.uuid4()),
                    workflow_id=wf.id,
                    step_order=s["step_order"],
                    step_key=s["step_key"],
                    step_type=s["step_type"],
                    display_name=s.get("display_name"),
                    config=s["config"],
                )
            )

        db.commit()
        print(f"Seeded {len(steps)} steps on workflow {_WORKFLOW_NAME!r}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
