"""Fail-closed VV3 selected-villager Full Mastery transaction model.

The executable route remains a disabled candidate until an exact VV3 command-1
boundary is independently proven.  This model is deliberately side-effect free:
all game writes are represented as native callbacks, and the preferred-job field
is included in the revalidation snapshot but is never changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


PRICE = 100_000
TARGET = 100
SKILL_OFFSETS = (0xEAC, 0xEB0, 0xEB4, 0xEB8, 0xEBC)
SKILL_NAMES = ("farming", "parenting", "healing", "research", "building")
NOOP_MESSAGE = (
    "This villager is already fully mastered.\r\n"
    "No tech points have been deducted."
)
CONFIRM_MESSAGE = (
    "Grant Full Mastery to this villager for 100,000 tech points?\r\n"
    "Press OK to confirm, or Cancel."
)
CANCEL_MESSAGE = "Full Mastery was canceled.\r\nNo tech points have been deducted."
INSUFFICIENT_MESSAGE = "Not enough tech points.\r\nNo tech points have been deducted."
INVALID_MESSAGE = (
    "No valid living villager is selected.\r\n"
    "No tech points have been deducted."
)
RACE_MESSAGE = (
    "The selected villager changed before confirmation.\r\n"
    "No tech points have been deducted."
)
FAILURE_MESSAGE = (
    "Full Mastery could not be completed; native changes may remain.\r\n"
    "No tech points have been deducted."
)
DEPENDENCY_MESSAGE = (
    "Full Mastery dependencies are unavailable.\r\n"
    "No tech points have been deducted."
)


@dataclass(frozen=True)
class NativeSkillCall:
    physical_index: int
    skill_index: int
    delta: int


@dataclass(frozen=True)
class TransactionPlan:
    status: str
    message: str
    physical_index: int
    calls: tuple[NativeSkillCall, ...] = ()
    evaluator: bool = False
    deduction: int = 0
    snapshot: tuple[object, ...] = ()


def _record_skills(record: Mapping[str, object]) -> tuple[int, ...] | None:
    if not bool(record.get("active", False)) or int(record.get("health", 0)) <= 0:
        return None
    raw = record.get("skills")
    if isinstance(raw, Mapping):
        values = tuple(int(raw[name]) for name in SKILL_NAMES if name in raw)
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        values = tuple(int(value) for value in raw)
    else:
        return None
    if len(values) != len(SKILL_OFFSETS) or any(value < 0 or value > TARGET for value in values):
        return None
    return values


def _snapshot(record: Mapping[str, object], skills: tuple[int, ...]) -> tuple[object, ...]:
    # Preference is captured for exact race detection but is never written.
    return (
        record.get("identity", id(record)),
        bool(record.get("active", False)),
        int(record.get("health", 0)),
        skills,
        record.get("preferred_job", record.get("preference")),
    )


def plan_transaction(
    records: Sequence[Mapping[str, object]],
    physical_index: int,
    balance: int,
    confirmed: bool,
    reacquire: Callable[[], tuple[int, Sequence[Mapping[str, object]], int]],
    preflight: Callable[[], bool] | None = None,
) -> TransactionPlan:
    """Perform the complete dry-run/reacquire plan without mutating records."""

    # Dependency and result exports are validated before any record/action
    # fields are read.  A missing preflight callback is the pure-model default
    # (the production loader supplies one before invoking this planner).
    if preflight is not None and not preflight():
        return TransactionPlan("dependency", DEPENDENCY_MESSAGE, physical_index)
    if physical_index < 0 or physical_index >= len(records):
        return TransactionPlan("invalid", INVALID_MESSAGE, physical_index)
    initial_record = records[physical_index]
    initial_skills = _record_skills(initial_record)
    if initial_skills is None:
        return TransactionPlan("invalid", INVALID_MESSAGE, physical_index)
    initial_snapshot = _snapshot(initial_record, initial_skills)
    changed = tuple(i for i, value in enumerate(initial_skills) if value < TARGET)
    if not changed:
        return TransactionPlan("no_change", NOOP_MESSAGE, physical_index, snapshot=initial_snapshot)
    if not confirmed:
        return TransactionPlan("cancel", CANCEL_MESSAGE, physical_index, snapshot=initial_snapshot)

    current_index, current_records, current_balance = reacquire()
    if current_index != physical_index or current_index < 0 or current_index >= len(current_records):
        return TransactionPlan("race", RACE_MESSAGE, physical_index)
    current_record = current_records[current_index]
    current_skills = _record_skills(current_record)
    if current_skills is None:
        return TransactionPlan("invalid", INVALID_MESSAGE, physical_index)
    current_snapshot = _snapshot(current_record, current_skills)
    if current_snapshot != initial_snapshot:
        return TransactionPlan("race", RACE_MESSAGE, physical_index, snapshot=current_snapshot)
    changed = tuple(i for i, value in enumerate(current_skills) if value < TARGET)
    if not changed:
        return TransactionPlan("no_change", NOOP_MESSAGE, physical_index, snapshot=current_snapshot)
    if current_balance < PRICE:
        return TransactionPlan("insufficient", INSUFFICIENT_MESSAGE, physical_index, snapshot=current_snapshot)
    calls = tuple(
        NativeSkillCall(physical_index, i, TARGET - current_skills[i]) for i in changed
    )
    return TransactionPlan(
        "commit", "", physical_index, calls, evaluator=True, deduction=PRICE, snapshot=current_snapshot
    )


def apply_plan(
    plan: TransactionPlan,
    native_writer: Callable[[int, int, int], None],
    evaluator: Callable[[int], None],
    deduct: Callable[[int], None],
    funds_check: Callable[[], bool] | None = None,
) -> str:
    """Apply a committed plan through native callbacks, reporting partial failure."""

    if plan.status != "commit":
        return plan.message
    try:
        if funds_check is not None and not funds_check():
            return INSUFFICIENT_MESSAGE
        for call in plan.calls:
            native_writer(call.physical_index, call.skill_index, call.delta)
        if plan.evaluator:
            evaluator(plan.physical_index)
        if plan.deduction != PRICE:
            raise ValueError("VV3 Full Mastery deduction contract mismatch")
        if funds_check is not None and not funds_check():
            return FAILURE_MESSAGE
        deduct(plan.deduction)
    except Exception:
        return FAILURE_MESSAGE
    return "Full Mastery was granted."
