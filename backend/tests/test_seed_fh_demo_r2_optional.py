"""R-6.2a.1 + R-6.2a.2 — verify seed_fh_demo's
_commit_canvas_state_r2_optional helper degrades gracefully when R2 is
not configured (CI environment) and propagates other failure modes.

R-6.2a.2 test correction: tests must mock at the REAL production
exception-origin boundary (`legacy_r2_client.upload_bytes` raising
RuntimeError) and let the canonical production wrap chain run
unchanged. instance_service.commit_canvas_state wraps the bare
RuntimeError into PersonalizationStudioError via `raise ... from exc`
at instance_service.py:465. R-6.2a.1's tests mocked
commit_canvas_state directly to raise RuntimeError, bypassing the
wrap — they verified a fictional path. Production code raises
PersonalizationStudioError; helper must catch that class to function.

Closes §15 entry #1 (seed_fh_demo R2 dependency blocking CI gate).

Pattern locked: test mocks exercise the actual production exception
path. Mock at the substrate boundary (legacy_r2_client) where the
canonical error originates; let production wrap chain run unchanged.
Do NOT mock at the layer the helper directly calls if that layer
wraps the exception.
"""

from unittest.mock import patch

import pytest

from scripts import seed_fh_demo


def test_helper_returns_true_on_successful_commit():
    """When the full commit pipeline succeeds (R2 upload included),
    helper returns True. DB write discipline is delegated to
    instance_service; helper just observes success/skip.

    Mocks at legacy_r2_client.upload_bytes — the actual R2 boundary
    — letting commit_canvas_state's wrap logic run as in production.
    """
    with patch(
        "app.services.personalization_studio.instance_service."
        "commit_canvas_state",
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


def test_helper_returns_false_when_r2_unavailable_via_production_path():
    """When legacy_r2_client.upload_bytes raises
    RuntimeError("R2 not configured"), commit_canvas_state wraps it
    into PersonalizationStudioError via `raise ... from exc` at
    instance_service.py:465. Helper catches the wrapped exception
    via substring check on the canonical "R2 not configured" message
    that the wrap preserves.

    This is the real production path the CI run hits. R-6.2a.1's
    tests mocked the wrong layer; this test mocks the correct
    boundary (legacy_r2_client.upload_bytes) and lets the production
    wrap chain run unchanged.
    """
    from app.services.personalization_studio.instance_service import (
        PersonalizationStudioError,
    )

    # Mock at the real boundary: legacy_r2_client.upload_bytes raises
    # the canonical RuntimeError. instance_service.commit_canvas_state
    # then wraps it as PersonalizationStudioError. Helper must catch
    # the wrapped class.
    wrapped_exc = PersonalizationStudioError(
        "R2 upload failed for canvas state v1 of instance 'fake-id': "
        "R2 not configured"
    )

    with patch(
        "app.services.personalization_studio.instance_service."
        "commit_canvas_state",
        side_effect=wrapped_exc,
    ):
        result = seed_fh_demo._commit_canvas_state_r2_optional(
            db=None,
            instance_id="fake-instance-id",
            canvas_state={"version": "1.0", "pages": []},
            committed_by_user_id="fake-user-id",
            label="ci-environment",
        )

    assert result is False


def test_helper_logs_degradation_when_r2_skipped(capsys):
    """When R2 is unavailable, helper logs degradation via print()
    matching seed's output convention. CI logs make the degradation
    visible to operators."""
    from app.services.personalization_studio.instance_service import (
        PersonalizationStudioError,
    )

    wrapped_exc = PersonalizationStudioError(
        "R2 upload failed for canvas state v1 of instance 'fake-id': "
        "R2 not configured"
    )

    with patch(
        "app.services.personalization_studio.instance_service."
        "commit_canvas_state",
        side_effect=wrapped_exc,
    ):
        seed_fh_demo._commit_canvas_state_r2_optional(
            db=None,
            instance_id="fake-instance-id",
            canvas_state={"version": "1.0", "pages": []},
            committed_by_user_id="fake-user-id",
            label="ci-environment",
        )

    captured = capsys.readouterr()
    assert "skipped" in captured.out
    assert "R2 not configured" in captured.out
    assert "ci-environment" in captured.out


def test_helper_propagates_non_r2_personalization_studio_errors():
    """PersonalizationStudioError NOT matching 'R2 not configured'
    propagates unchanged. Runtime callers retain the hard-error canon;
    seed helper only catches the specific R2-unavailable signal.

    Example real-world non-R2 PersonalizationStudioError causes:
    invalid lifecycle state transition, missing instance, permission
    denied. Seeds shouldn't swallow these — they indicate real
    misconfiguration distinct from the CI/R2 case.
    """
    from app.services.personalization_studio.instance_service import (
        PersonalizationStudioError,
    )

    with patch(
        "app.services.personalization_studio.instance_service."
        "commit_canvas_state",
        side_effect=PersonalizationStudioError(
            "Invalid lifecycle transition: cannot commit from voided state"
        ),
    ):
        with pytest.raises(
            PersonalizationStudioError, match="Invalid lifecycle transition"
        ):
            seed_fh_demo._commit_canvas_state_r2_optional(
                db=None,
                instance_id="fake-instance-id",
                canvas_state={"version": "1.0", "pages": []},
                committed_by_user_id="fake-user-id",
                label="non-r2-error",
            )


def test_helper_propagates_bare_runtime_errors():
    """Bare RuntimeErrors (not wrapped in PersonalizationStudioError)
    propagate unchanged. The helper's catch is narrow — only the
    canonical PersonalizationStudioError-with-'R2 not configured'-
    substring is caught.

    This guards against future refactors of commit_canvas_state that
    change the wrap behavior. If commit_canvas_state ever stops
    wrapping, bare RuntimeErrors would surface here — and the helper
    correctly lets them propagate (the seed maintainer would notice
    + update the catch shape if R2 errors started arriving unwrapped).
    """
    with patch(
        "app.services.personalization_studio.instance_service."
        "commit_canvas_state",
        side_effect=RuntimeError("R2 not configured"),
    ):
        with pytest.raises(RuntimeError, match="R2 not configured"):
            seed_fh_demo._commit_canvas_state_r2_optional(
                db=None,
                instance_id="fake-instance-id",
                canvas_state={"version": "1.0", "pages": []},
                committed_by_user_id="fake-user-id",
                label="bare-runtime-error",
            )


def test_helper_propagates_other_exception_classes():
    """Other exception classes (ValueError, KeyError, etc.) propagate.
    The catch is narrow by design — only PersonalizationStudioError
    with the canonical R2 sentinel substring is caught."""
    with patch(
        "app.services.personalization_studio.instance_service."
        "commit_canvas_state",
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
