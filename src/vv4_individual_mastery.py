"""Fail-closed transaction model for the VV4 individual mastery candidate.

This module is deliberately independent of the stock executable.  It records
the native operation sequence without performing direct skill stores; the
candidate remains disabled until the executable ABI and physical-index route
receive independent D27 recertification.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


PRICE = 100_000
TARGET = 100.0
SKILL_COUNT = 5
NOOP_MESSAGE = "Everyone is already fully mastered.\r\nNo tech points have been deducted."
INSUFFICIENT_MESSAGE = "Not enough tech points.\r\nNo tech points have been deducted."
INVALID_MESSAGE = (
    "Full Mastery cannot be applied because the selected villager has an "
    "out-of-range skill.\r\nNo tech points have been deducted."
)
RACE_MESSAGE = "The selected villager changed before confirmation.\r\nNo tech points have been deducted."


@dataclass(frozen=True)
class NativeSkillCall:
    """One native sub_46AD80 call; no raw field write is represented."""

    physical_index: int
    skill_index: int
    delta: float


@dataclass(frozen=True)
class TransactionPlan:
    status: str
    message: str
    physical_index: int
    calls: tuple[NativeSkillCall, ...] = ()
    deduction: int = 0


def float32(value: float) -> float:
    """Round-trip through the game's Float32 representation."""

    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _skills(record: Mapping[str, object]) -> tuple[float, ...] | None:
    if not bool(record.get("active", False)) or int(record.get("health", 0)) <= 0:
        return None
    raw = record.get("skills")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return None
    if len(raw) != SKILL_COUNT:
        return None
    values: list[float] = []
    for value in raw:
        try:
            rounded = float32(float(value))
        except (TypeError, ValueError, OverflowError, struct.error):
            return None
        if not math.isfinite(rounded) or rounded < 0.0 or rounded > TARGET:
            return None
        values.append(rounded)
    return tuple(values)


def plan_transaction(
    records: Sequence[Mapping[str, object]],
    physical_index: int,
    balance: int,
    confirmed: bool,
    reacquire: Callable[[], tuple[int, Sequence[Mapping[str, object]], int]],
) -> TransactionPlan:
    """Plan the exact two-pass native transaction.

    ``reacquire`` returns ``(physical_index, records, balance)`` after the
    explicit confirmation.  The planner never mutates a record or balance;
    callers must apply the returned native calls and single deduction through
    the game's proven ABIs.
    """

    if physical_index < 0 or physical_index >= len(records):
        return TransactionPlan("invalid", INVALID_MESSAGE, physical_index)
    initial = _skills(records[physical_index])
    if initial is None:
        return TransactionPlan("invalid", INVALID_MESSAGE, physical_index)
    changed = tuple(i for i, value in enumerate(initial) if value < TARGET)
    if not changed:
        return TransactionPlan("no_change", NOOP_MESSAGE, physical_index)
    if not confirmed:
        return TransactionPlan("cancel", "", physical_index)

    current_index, current_records, current_balance = reacquire()
    if current_index != physical_index:
        return TransactionPlan("race", RACE_MESSAGE, physical_index)
    if current_index < 0 or current_index >= len(current_records):
        return TransactionPlan("invalid", INVALID_MESSAGE, physical_index)
    final = _skills(current_records[current_index])
    if final is None:
        return TransactionPlan("invalid", INVALID_MESSAGE, physical_index)
    final_changed = tuple(i for i, value in enumerate(final) if value < TARGET)
    if not final_changed:
        return TransactionPlan("no_change", NOOP_MESSAGE, physical_index)
    if current_balance < PRICE:
        return TransactionPlan("insufficient", INSUFFICIENT_MESSAGE, physical_index)

    calls = tuple(
        NativeSkillCall(physical_index, i, float32(TARGET - final[i]))
        for i in final_changed
    )
    return TransactionPlan("commit", "", physical_index, calls, PRICE)


def apply_plan(
    plan: TransactionPlan,
    native_writer: Callable[[int, int, float], None],
    deduct: Callable[[int], None],
) -> None:
    """Apply only a committed plan through native callbacks."""

    if plan.status != "commit":
        return
    for call in plan.calls:
        native_writer(call.physical_index, call.skill_index, call.delta)
    if plan.deduction != PRICE:
        raise ValueError("individual mastery deduction contract mismatch")
    deduct(plan.deduction)

