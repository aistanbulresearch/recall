from __future__ import annotations

from datetime import timedelta

import pytest

from recall.scheduler.compressed_identity import collection_prefix
import recall.scheduler.compressed as compressed_module
from recall.scheduler.compressed import CompressedCycleScheduler
from recall.scheduler.compressed_plan import (
    FINAL_ONLY_OWNER_RELEASE_REASON,
    FINAL_ONLY_OWNER_RELEASE_TOKEN,
    authorize_final_only_owner_release,
    parse_compressed_plan,
)
from recall.scheduler.entrypoint import execute
from tests.scheduler.test_compressed_plan import _wire_for_final_only


def _plan():
    return parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)


def test_owner_release_is_exact_final_only_c6_and_actual_start_bound() -> None:
    plan = _plan()
    c6 = plan.by_id("c6")
    actual_start = c6.window_end + timedelta(seconds=1)

    release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=actual_start,
        max_retries=0,
    )

    assert release.cycle_id == "c6"
    assert release.actual_start == actual_start
    assert release.write_deadline == actual_start + timedelta(seconds=1_800)
    assert release.execution_deadline == actual_start + timedelta(seconds=28_800)
    assert release.agent_timeout_seconds == 27_000
    assert release.max_retries == 0
    prefix = collection_prefix(plan, c6)
    assert prefix == "dev_recall_m2_compressed_peeeeeeeeeeee_c6_20260831_"
    assert len(f"{prefix}tool_gateway_invocations") == 75


@pytest.mark.parametrize(
    ("token", "reason", "max_retries", "offset", "failure"),
    [
        ("wrong", FINAL_ONLY_OWNER_RELEASE_REASON, 0, 1, "token_invalid"),
        (FINAL_ONLY_OWNER_RELEASE_TOKEN, "wrong", 0, 1, "reason_invalid"),
        (FINAL_ONLY_OWNER_RELEASE_TOKEN, FINAL_ONLY_OWNER_RELEASE_REASON, 1, 1, "max_retries_invalid"),
        (FINAL_ONLY_OWNER_RELEASE_TOKEN, FINAL_ONLY_OWNER_RELEASE_REASON, 0, 0, "not_late"),
    ],
)
def test_owner_release_fails_closed_on_authority_or_runtime_drift(
    token: str,
    reason: str,
    max_retries: int,
    offset: int,
    failure: str,
) -> None:
    plan = _plan()
    with pytest.raises(RuntimeError, match=f"final_only_owner_release_{failure}"):
        authorize_final_only_owner_release(
            plan,
            token=token,
            reason=reason,
            actual_start=plan.by_id("c6").window_end
            + timedelta(seconds=offset),
            max_retries=max_retries,
        )


def test_owner_release_scheduler_selects_c6_without_static_window_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    cycle = plan.by_id("c6")
    actual_start = cycle.window_end + timedelta(seconds=1)
    release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=actual_start,
        max_retries=0,
    )
    calls: list[str] = []

    def forbidden_static_resolution(*_args, **_kwargs):
        raise AssertionError("static_window_resolution_must_not_run")

    def stop_after_history(*_args, **_kwargs):
        calls.append("history")
        raise RuntimeError("stop_after_history_verification")

    monkeypatch.setattr(
        compressed_module, "resolve_declared_cycle", forbidden_static_resolution
    )
    monkeypatch.setattr(
        compressed_module, "verify_final_only_supersession", stop_after_history
    )
    scheduler = CompressedCycleScheduler(
        object(),
        plan=plan,
        cycle=cycle,
        bundle=object(),
        source_commit="a" * 40,
        image_digest=f"sha256:{'b' * 64}",
        owner_release=release,
    )

    with pytest.raises(RuntimeError, match="stop_after_history_verification"):
        scheduler.trigger(
            now=actual_start,
            previous_manifest=None,
            historical_ledger_factory=lambda _prefix: object(),
        )

    assert calls == ["history"]


@pytest.mark.parametrize(
    "argv",
    [
        ["--owner-release-token", FINAL_ONLY_OWNER_RELEASE_TOKEN],
        ["--owner-release-reason", FINAL_ONLY_OWNER_RELEASE_REASON],
        [
            "--owner-release-token",
            "wrong",
            "--owner-release-reason",
            FINAL_ONLY_OWNER_RELEASE_REASON,
        ],
    ],
)
def test_owner_release_cli_rejects_partial_or_invalid_authority_before_writes(
    argv: list[str],
) -> None:
    ledger_calls = 0

    def forbidden_ledger(**_kwargs):
        nonlocal ledger_calls
        ledger_calls += 1
        raise AssertionError("ledger_must_not_be_constructed")

    with pytest.raises(RuntimeError, match="final_only_owner_release"):
        execute(
            argv,
            environment={
                "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
                "RECALL_PROVIDER_RPM": "8",
            },
            ledger_factory=forbidden_ledger,
        )
    assert ledger_calls == 0
