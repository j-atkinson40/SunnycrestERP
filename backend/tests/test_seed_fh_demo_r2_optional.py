"""R-6.2a.1 — verify seed_fh_demo's _commit_canvas_state_r2_optional
helper degrades gracefully when R2 is not configured (CI environment),
and propagates other RuntimeErrors (runtime callers retain hard error
canon).

Closes §15 entry #1 (seed_fh_demo R2 dependency blocking CI gate).
"""

from unittest.mock import patch

import pytest

from scripts import seed_fh_demo


def test_helper_returns_true_on_successful_commit():
    """When commit_canvas_state succeeds, helper returns True. DB write
    discipline is delegated to instance_service; helper just observes
    success/skip."""
    with patch(
        "app.services.personalization_studio.instance_service.commit_canvas_state",
        return_value=None,
    ) as mock_commit:
        result = seed_fh_demo._commit_canvas_state_r2_optional(
            db=None,
            instance_id="fake-instance-id",
            canvas_state={"version": "1.0", "pages": []},
            committed_by_user_id="fake-user-id",
            label="unit-test",
        )

    assert result is True
    mock_commit.assert_called_once()


def test_helper_returns_false_and_logs_on_r2_not_configured(capsys):
    """When commit_canvas_state raises RuntimeError("R2 not configured"),
    helper catches + logs degradation + returns False. Seed continues."""
    with patch(
        "app.services.personalization_studio.instance_service.commit_canvas_state",
        side_effect=RuntimeError("R2 not configured"),
    ):
        result = seed_fh_demo._commit_canvas_state_r2_optional(
            db=None,
            instance_id="fake-instance-id",
            canvas_state={"version": "1.0", "pages": []},
            committed_by_user_id="fake-user-id",
            label="ci-environment",
        )

    assert result is False
    captured = capsys.readouterr()
    assert "skipped" in captured.out
    assert "R2 not configured" in captured.out
    assert "ci-environment" in captured.out


def test_helper_propagates_non_r2_runtime_errors():
    """RuntimeErrors NOT matching 'R2 not configured' propagate
    unchanged. Runtime callers retain the hard-error canon; seed
    helper only catches the specific R2-unavailable signal."""
    with patch(
        "app.services.personalization_studio.instance_service.commit_canvas_state",
        side_effect=RuntimeError("Some other runtime failure"),
    ):
        with pytest.raises(RuntimeError, match="Some other runtime failure"):
            seed_fh_demo._commit_canvas_state_r2_optional(
                db=None,
                instance_id="fake-instance-id",
                canvas_state={"version": "1.0", "pages": []},
                committed_by_user_id="fake-user-id",
                label="non-r2-error",
            )


def test_helper_propagates_non_runtime_exceptions():
    """Other exception classes (ValueError, KeyError, etc.) also
    propagate. The catch is narrow by design — only RuntimeError with
    the canonical R2 sentinel message is caught."""
    with patch(
        "app.services.personalization_studio.instance_service.commit_canvas_state",
        side_effect=ValueError("Bad canvas state"),
    ):
        with pytest.raises(ValueError, match="Bad canvas state"):
            seed_fh_demo._commit_canvas_state_r2_optional(
                db=None,
                instance_id="fake-instance-id",
                canvas_state={"version": "1.0", "pages": []},
                committed_by_user_id="fake-user-id",
                label="value-error",
            )
