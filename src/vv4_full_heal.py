"""Pure transaction model for the disabled VV4 Full Heal / Cure All candidate.

The model deliberately contains no raw record writes.  Runtime code must supply
the proved VV4 resolver and native setter/statistic ABIs; this module only
defines the ordering, counters, snapshots, and fail-closed result semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


PRICE = 30_000
RECORD_COUNT = 150
NO_DEDUCTION = "No tech points have been deducted."
TECH_DEDUCTION_RECEIVER = 0x4D6F88
TECH_DEDUCTION_CALL = 0x41E300
PEOPLE_CURED_RECEIVER = 0x4D6DF0


def _failure(text: str) -> str:
    return f"{text}\r\n{NO_DEDUCTION}"


@dataclass(frozen=True)
class EligibleState:
    index: int
    identity: object
    health: int
    sick: bool
    active: int = 1
    status: int = 0


@dataclass(frozen=True)
class DryRun:
    sick_count: int
    partial_count: int
    states: tuple[EligibleState, ...]


@dataclass(frozen=True)
class TransactionResult:
    status: str
    message: str
    predicted_sick: int = 0
    predicted_partial: int = 0
    actual_sick: int = 0
    actual_partial: int = 0
    deduction: int = 0
    snapshot: tuple[EligibleState, ...] = ()


def _eligible(record: Mapping[str, object] | None) -> bool:
    """Apply the proved VV4 gate before reading health or sickness."""

    if record is None:
        return False
    if int(record.get("active", 0)) == 0:
        return False
    if int(record.get("status", 0)) != 0:
        return False
    try:
        return int(record.get("health", 0)) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def dry_run(
    resolve: Callable[[int], Mapping[str, object] | None],
) -> DryRun | None:
    """Resolve every physical index in order and count overlapping work."""

    states: list[EligibleState] = []
    sick_count = partial_count = 0
    for index in range(RECORD_COUNT):
        record = resolve(index)
        if record is None:
            states.append(EligibleState(index, None, 0, False, 0, 0))
            continue
        try:
            health = int(record["health"])
            sick = int(record.get("sick", 0)) != 0
            active = int(record.get("active", 0))
            status = int(record.get("status", 0))
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        identity = record.get("identity", record.get("pointer", index))
        # Keep a complete physical-index snapshot, including ineligible
        # records, so replacement/activation/status changes cannot evade the
        # confirmation gate.
        states.append(EligibleState(index, identity, health, sick, active, status))
        if not _eligible(record):
            continue
        partial = 0 < health < 100
        sick_count += int(sick)
        partial_count += int(partial)
    return DryRun(sick_count, partial_count, tuple(states))


def _same_snapshot(before: DryRun, after: DryRun) -> bool:
    return before.states == after.states and (
        before.sick_count,
        before.partial_count,
    ) == (after.sick_count, after.partial_count)


def plan_transaction(
    resolve: Callable[[int], Mapping[str, object] | None],
    balance: int,
    confirmed: bool,
    reacquire: Callable[[], tuple[Callable[[int], Mapping[str, object] | None], int]],
) -> TransactionResult:
    """Perform dry-run/confirmation/reacquisition planning without mutation."""

    initial = dry_run(resolve)
    if initial is None:
        return TransactionResult("invalid", _failure("No valid living believer state was available."))
    if initial.sick_count == 0 and initial.partial_count == 0:
        return TransactionResult(
            "no_change",
            _failure("No eligible villager requires healing or sickness clearing."),
            initial.sick_count,
            initial.partial_count,
        )
    prompt = (
        f"Full Heal / Cure All will cure {initial.sick_count} sick villager(s) "
        f"and restore partial health for {initial.partial_count} villager(s) "
        f"for {PRICE:,} tech points.\r\nPress OK to confirm, or Cancel."
    )
    if not confirmed:
        return TransactionResult("cancel", _failure("Full Heal / Cure All was canceled."), initial.sick_count, initial.partial_count)
    fresh_resolve, fresh_balance = reacquire()
    fresh = dry_run(fresh_resolve)
    if fresh is None or not _same_snapshot(initial, fresh):
        return TransactionResult("stale", _failure("The villager state changed before confirmation."), initial.sick_count, initial.partial_count)
    if fresh_balance < PRICE:
        return TransactionResult("insufficient", _failure("Not enough tech points."), initial.sick_count, initial.partial_count)
    return TransactionResult("commit", prompt, initial.sick_count, initial.partial_count, snapshot=initial.states)


def success_message(actual_sick: int, actual_partial: int) -> str:
    return f"Full Heal / Cure All cured {actual_sick} sick villager(s) and restored partial health for {actual_partial} villager(s)."


def failure_message(actual_sick: int, actual_partial: int, reason: str) -> str:
    return _failure(
        f"Full Heal / Cure All stopped after {actual_sick} sickness clear(s) "
        f"and {actual_partial} partial-health restore(s): {reason}"
    )


def apply_transaction(
    resolve: Callable[[int], Mapping[str, object] | None],
    plan: TransactionResult,
    set_health: Callable[[int, int, int], bool],
    clear_sickness: Callable[[int], bool],
    increment_people_cured: Callable[[], None],
    deduct: Callable[[int, int, int], None],
    funds: Callable[[], int] | None = None,
) -> TransactionResult:
    """Apply a committed plan through native callbacks and postverify it.

    The callbacks represent the proved VV4 ABIs.  No direct record mutation is
    performed here; a failure after a successful native callback is reported as
    partial and remains explicitly no-charge.
    """

    if plan.status != "commit":
        return plan
    if funds is not None and funds() < PRICE:
        return TransactionResult(
            "insufficient",
            _failure("Not enough tech points."),
            plan.predicted_sick,
            plan.predicted_partial,
        )
    actual_sick = actual_partial = 0
    for index in range(RECORD_COUNT):
        record = resolve(index)
        expected = next((state for state in plan.snapshot if state.index == index), None)
        if expected is None:
            return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record snapshot missing"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
        if record is None:
            if expected != EligibleState(index, None, 0, False, 0, 0):
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record identity or prestate changed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            continue
        try:
            current_identity = record.get("identity", record.get("pointer", index))
            current_health = int(record.get("health", 0))
            current_sick = int(record.get("sick", 0)) != 0
            current_active = int(record.get("active", 0))
            current_status = int(record.get("status", 0))
        except (TypeError, ValueError, OverflowError):
            return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record revalidation failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
        if (current_identity, current_health, current_sick, current_active, current_status) != (expected.identity, expected.health, expected.sick, expected.active, expected.status):
            return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record identity or prestate changed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
        if not _eligible(record):
            continue
        try:
            health = int(record["health"])
            sick = int(record.get("sick", 0)) != 0
        except (KeyError, TypeError, ValueError, OverflowError):
            return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record revalidation failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
        identity = current_identity
        # The runtime transaction uses a complete per-index snapshot.  The
        # model mirrors that contract while retaining the historical public
        # result shape used by existing callers.
        if expected is not None and (
            identity != expected.identity
            or int(record.get("active", 0)) != expected.active
            or int(record.get("status", 0)) != expected.status
            or health != expected.health
            or (int(record.get("sick", 0)) != 0) != expected.sick
        ):
            return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record identity or prestate changed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
        if health <= 0:
            continue
        if 0 < health < 100:
            if not set_health(index, -1, 100):
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "native health write failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            after = resolve(index)
            if after is None or after.get("identity", after.get("pointer", index)) != identity or int(after.get("health", 0)) != 100:
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "health postverification failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            actual_partial += 1
        if sick:
            before_clear = resolve(index)
            if (
                before_clear is None
                or before_clear.get("identity", before_clear.get("pointer", index)) != identity
                or int(before_clear.get("active", 0)) == 0
                or int(before_clear.get("status", 0)) != 0
                or int(before_clear.get("health", 0)) <= 0
                or int(before_clear.get("sick", 0)) == 0
            ):
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record changed before sickness clear"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            if not clear_sickness(index):
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "native sickness clear failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            after = resolve(index)
            if after is None or after.get("identity", after.get("pointer", index)) != identity or int(after.get("active", 0)) == 0 or int(after.get("status", 0)) != 0 or int(after.get("health", 0)) <= 0 or int(after.get("sick", 1)) != 0:
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "sickness postverification failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            increment_people_cured()
            actual_sick += 1
    final = dry_run(resolve)
    if final is None or final.sick_count != 0 or final.partial_count != 0:
        return TransactionResult("partial", failure_message(actual_sick, actual_partial, "complete postverification failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
    if actual_sick != plan.predicted_sick or actual_partial != plan.predicted_partial:
        return TransactionResult("partial", failure_message(actual_sick, actual_partial, "verified counts did not match the confirmed counts"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
    if funds is not None and funds() < PRICE:
        return TransactionResult("insufficient", failure_message(actual_sick, actual_partial, "funds changed before deduction"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
    deduct(TECH_DEDUCTION_RECEIVER, -PRICE, TECH_DEDUCTION_CALL)
    return TransactionResult("success", success_message(actual_sick, actual_partial), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial, PRICE)
