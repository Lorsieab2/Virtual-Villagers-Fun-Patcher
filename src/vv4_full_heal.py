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


def _failure(text: str) -> str:
    return f"{text}\r\n{NO_DEDUCTION}"


@dataclass(frozen=True)
class EligibleState:
    index: int
    health: int
    sick: bool


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
        if not _eligible(record):
            continue
        try:
            health = int(record["health"])
            sick = int(record.get("sick", 0)) != 0
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        if health > 100:
            return None
        partial = 0 < health < 100
        sick_count += int(sick)
        partial_count += int(partial)
        if sick or partial:
            states.append(EligibleState(index, health, sick))
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
    return TransactionResult("commit", prompt, initial.sick_count, initial.partial_count)


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
    deduct: Callable[[int], None],
) -> TransactionResult:
    """Apply a committed plan through native callbacks and postverify it.

    The callbacks represent the proved VV4 ABIs.  No direct record mutation is
    performed here; a failure after a successful native callback is reported as
    partial and remains explicitly no-charge.
    """

    if plan.status != "commit":
        return plan
    actual_sick = actual_partial = 0
    for index in range(RECORD_COUNT):
        record = resolve(index)
        if not _eligible(record):
            continue
        try:
            health = int(record["health"])
            sick = int(record.get("sick", 0)) != 0
        except (KeyError, TypeError, ValueError, OverflowError):
            return TransactionResult("partial", failure_message(actual_sick, actual_partial, "record revalidation failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
        if health > 100:
            return TransactionResult("partial", failure_message(actual_sick, actual_partial, "health range changed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
        if 0 < health < 100:
            if not set_health(index, -1, 100):
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "native health write failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            after = resolve(index)
            if after is None or int(after.get("health", 0)) != 100:
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "health postverification failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            actual_partial += 1
        if sick:
            if not clear_sickness(index):
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "native sickness clear failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            after = resolve(index)
            if after is None or int(after.get("sick", 1)) != 0:
                return TransactionResult("partial", failure_message(actual_sick, actual_partial, "sickness postverification failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
            increment_people_cured()
            actual_sick += 1
    final = dry_run(resolve)
    if final is None or final.sick_count != 0 or final.partial_count != 0:
        return TransactionResult("partial", failure_message(actual_sick, actual_partial, "complete postverification failed"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
    if actual_sick != plan.predicted_sick or actual_partial != plan.predicted_partial:
        return TransactionResult("partial", failure_message(actual_sick, actual_partial, "verified counts did not match the confirmed counts"), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial)
    deduct(PRICE)
    return TransactionResult("success", success_message(actual_sick, actual_partial), plan.predicted_sick, plan.predicted_partial, actual_sick, actual_partial, PRICE)
