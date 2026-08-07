"""Fail-closed VV5 Full Heal / Cure All reference transaction model.

This module contains no native implementation and performs no save I/O.  It
only defines the exact-build record gate, aggregate counts, confirmation
ordering, and callback boundary that a future native implementation would
have to satisfy.  Health mutation, sickness clearing, People Cured updates,
and tech deduction are deliberately abstract outcomes supplied by callers;
their VV5 ABIs remain unproven.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal


IDOK = 1
CANCEL_RESULTS = (0, 2)
PRICE = 30_000
RECORD_COUNT = 150
RECORD_STRIDE = 0x2F44
ACTIVE_OFFSET = 0x1CD4
FACTION_OFFSET = 0x1CEC
HEALTH_OFFSET = 0x1C40
FORBIDDEN_UNPROVEN_OFFSET = 0x1CE1
NO_DEDUCTION = "No tech points have been deducted."
UNKNOWN_ROLLBACK = "Rollback status is unknown; complete rollback is not claimed."

NativeOutcome = Literal["success", "failure", "unknown"]
Status = Literal[
    "committed",
    "invalid_state",
    "no_change",
    "cancelled",
    "insufficient_funds",
    "recheck_failed",
    "funds_recheck_failed",
    "partial",
    "partial_unknown",
    "charge_failed",
    "charge_unknown",
]

RECORD_KEYS = frozenset(
    {"identity", "record_pointer", "active", "faction", "health", "sick"}
)

Resolve = Callable[[int], Mapping[str, object] | None]
BeforeReacquire = Callable[[], "FullHealDryRun"]
BeforeFundsReacquire = Callable[[int], int]
AfterFundsReacquire = Callable[[int], int | None]
HealthSetter = Callable[[int, str, int], NativeOutcome]
SicknessClearer = Callable[[int, str], NativeOutcome]
PeopleCuredIncrementer = Callable[[int, str], NativeOutcome]
Deduction = Callable[[int], NativeOutcome]


def _exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an exact int")
    return value


def _exact_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be an exact bool")
    return value


def _exact_identity(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise TypeError(f"{label} must be a non-empty identity string")
    return value


def _outcome(value: object, label: str) -> NativeOutcome:
    if type(value) is not str or value not in {"success", "failure", "unknown"}:
        raise TypeError(f"{label} must return exact success, failure, or unknown")
    return value  # type: ignore[return-value]


@dataclass(frozen=True)
class FullHealSlot:
    """The exact fields read for one physical VV5 record.

    Health and sickness are intentionally ``None`` when the active/faction
    gate excludes a record, or when non-positive health excludes it before a
    sickness read.  This models the required read order and avoids claiming
    the unproved ``+0x1CE1`` field.
    """

    index: int
    identity: str | None
    record_pointer: str | None
    active: int
    faction: int
    health: int | None
    sick: bool | None

    def __post_init__(self) -> None:
        _exact_int(self.index, "slot.index")
        _exact_int(self.active, "slot.active")
        _exact_int(self.faction, "slot.faction")
        if self.identity is None or self.record_pointer is None:
            if self.identity is not None or self.record_pointer is not None:
                raise TypeError("absent slot identity and pointer must both be None")
        else:
            _exact_identity(self.identity, "slot.identity")
            _exact_identity(self.record_pointer, "slot.record_pointer")
        if self.health is not None:
            health = _exact_int(self.health, "slot.health")
            if not 0 <= health <= 100:
                raise ValueError("slot.health must be in exact range 0..100")
        if self.sick is not None:
            _exact_bool(self.sick, "slot.sick")
        if self.sick is not None and (self.health is None or self.health <= 0):
            raise ValueError("slot.sick is readable only for positive health")


@dataclass(frozen=True)
class FullHealDryRun:
    sick_count: int
    partial_count: int
    slots: tuple[FullHealSlot, ...]

    def __post_init__(self) -> None:
        _exact_int(self.sick_count, "dry_run.sick_count")
        _exact_int(self.partial_count, "dry_run.partial_count")
        if self.sick_count < 0 or self.partial_count < 0:
            raise ValueError("dry-run counts cannot be negative")
        if type(self.slots) is not tuple or len(self.slots) != RECORD_COUNT:
            raise TypeError("dry_run.slots must contain exactly 150 physical records")
        if any(type(slot) is not FullHealSlot for slot in self.slots):
            raise TypeError("dry_run.slots must contain exact FullHealSlot values")


@dataclass(frozen=True)
class TransactionResult:
    status: Status
    message: str
    predicted_sick: int = 0
    predicted_partial: int = 0
    actual_sick: int = 0
    actual_partial: int = 0
    funds: int = 0
    charged: bool = False
    charge_verified: bool = False
    charge_attempted: bool = False
    native_effects: Literal["none", "may_have_occurred"] = "none"
    rollback_status: Literal["not_attempted", "unknown"] = "not_attempted"
    dry_run: FullHealDryRun | None = None


def transaction_contract() -> dict[str, object]:
    """Return the strict disabled candidate contract consumed by the builder."""

    return {
        "sequence": [
            "complete 150-record dry-run",
            "explicit IDOK/Cancel confirmation",
            "reacquire every physical index and exact record pointer",
            "require exact full snapshot and predicted-count equality",
            "reacquire and require exact pre-confirmation funds before any callback",
            "invoke only abstract unproven health/sickness/statistic callbacks",
            "postverify each callback result and final zero sick/partial counts",
            "require actual sick/partial counts to equal confirmed counts",
            "invoke exactly one abstract deduction callback after complete verification",
            "reacquire final reference funds and verify one exact 30,000 deduction",
        ],
        "confirmation_results": {"idok": IDOK, "cancel": list(CANCEL_RESULTS)},
        "record_reacquire": "same physical index and exact record pointer for all 150 slots",
        "pre_confirmation_snapshot": "exact full 150-slot snapshot and predicted-count equality",
        "funds_reacquire": "pre-confirmation funds must be reacquired equal before any callback; final funds must equal minus 30,000",
        "required_callbacks": [
            "before_reacquire",
            "before_funds_reacquire",
            "after_funds_reacquire",
            "health_setter",
            "sickness_clearer",
            "people_cured_incrementer",
            "deduct",
        ],
        "native_callbacks": "unproven callback signatures only; no native implementation or output is emitted",
        "no_revive": "health <= 0 is excluded and never written",
        "counting": "sick and partial-health counts are separate; one overlapping record increments both",
        "postverify": "partial health is exactly 100 and sickness is exactly false; final counts are zero and actual counts equal predicted counts",
        "charge_verification": "one deduction callback only after postverify; final reference funds equal original funds minus 30,000",
        "native_effects": "callbacks may have native effects; this reference model supplies no rollback implementation",
        "rollback_disclosure": UNKNOWN_ROLLBACK,
        "charge_disclosure": "failure or unknown deduction outcome never claims a verified charge",
        "no_charge_suffix": NO_DEDUCTION,
        "no_charge_results": [
            "invalid_state",
            "no_change",
            "cancelled",
            "insufficient_funds",
            "recheck_failed",
            "funds_recheck_failed",
            "partial",
            "partial_unknown",
            "charge_failed",
            "charge_unknown",
        ],
        "price": PRICE,
    }


def record_contract() -> dict[str, object]:
    """Return the exact proven record fields and read ordering."""

    return {
        "record_count": RECORD_COUNT,
        "stride": f"0x{RECORD_STRIDE:X}",
        "offsets": {
            "active": f"0x{ACTIVE_OFFSET:X}",
            "faction": f"0x{FACTION_OFFSET:X}",
            "health": f"0x{HEALTH_OFFSET:X}",
        },
        "read_order": [
            "active +0x1CD4",
            "current faction +0x1CEC == 0",
            "positive health +0x1C40 > 0",
            "logical sickness state only after active/faction/health gate; no native offset is claimed",
        ],
        "eligibility": "active != 0, current faction == 0, health > 0",
        "no_revive": "health <= 0 is never read for sickness and never written",
        "partial_health": "health 1..99 is restored to exactly 100",
        "full_health": "health 100 is unchanged unless sickness is true",
        "heathen_policy": "faction != 0 is excluded before health or sickness reads",
    }


def callback_contract() -> dict[str, object]:
    """Return unproven callback signatures without inventing native VAs."""

    return {
        "health_setter": {
            "status": "unproven callback only; no native implementation",
            "signature": "Callable[[physical_index, exact_record_pointer, target_health_100], NativeOutcome]",
        },
        "sickness_clearer": {
            "status": "unproven callback only; no native implementation",
            "signature": "Callable[[physical_index, exact_record_pointer], NativeOutcome]",
        },
        "people_cured_incrementer": {
            "status": "unproven callback only; no native implementation",
            "signature": "Callable[[physical_index, exact_record_pointer], NativeOutcome]",
        },
        "deduct": {
            "status": "unproven callback only; no native implementation",
            "signature": "Callable[[exact_price_30000], NativeOutcome]",
        },
        "readback": {
            "status": "reference resolver callback only; no native readback implementation",
            "signature": "Callable[[physical_index], exact_record_mapping_or_none]",
        },
        "rollback": {
            "status": "not implemented; unknown after callback effects",
            "signature": "no callback is claimed",
        },
    }


def message_contract() -> dict[str, object]:
    """Return exact player-facing neutral/singular-safe message templates."""

    return {
        "label": "Full Heal / Cure All",
        "prompt": "Full Heal / Cure All will cure X sick villagers and restore Y partial-health villagers to exactly 100 for 30,000 tech points?",
        "success": "Full Heal / Cure All completed: X sick villagers were cured; Y partial-health villagers were restored to exactly 100.",
        "no_change": "Full Heal / Cure All found no sick villagers to cure or partial-health villagers to restore to exactly 100.",
        "partial": "Full Heal / Cure All stopped after X sick villagers were cured and Y partial-health villagers were restored to exactly 100.",
        "rollback_disclosure": UNKNOWN_ROLLBACK,
        "charge_unknown": "No verified charge is claimed when the deduction or final-funds outcome is unknown.",
        "no_charge_suffix": NO_DEDUCTION,
    }


def _empty_slot(index: int) -> FullHealSlot:
    return FullHealSlot(index, None, None, 0, 0, None, None)


def _slot_from_record(index: int, record: Mapping[str, object] | None) -> FullHealSlot:
    if record is None:
        return _empty_slot(index)
    if not isinstance(record, Mapping):
        raise TypeError("resolver must return an exact mapping or None")
    if set(record) != RECORD_KEYS:
        raise ValueError("resolver record schema must exclude unknown and unproved fields")

    # Deliberate order: active and current faction are read before health or
    # sickness.  +0x1CE1 is not present in RECORD_KEYS and is never read.
    identity = _exact_identity(record["identity"], "record.identity")
    pointer = _exact_identity(record["record_pointer"], "record.record_pointer")
    active = _exact_int(record["active"], "record.active")
    faction = _exact_int(record["faction"], "record.faction")
    if active == 0 or faction != 0:
        return FullHealSlot(index, identity, pointer, active, faction, None, None)

    health = _exact_int(record["health"], "record.health")
    if not 0 <= health <= 100:
        raise ValueError("record.health must be in exact range 0..100")
    if health <= 0:
        return FullHealSlot(index, identity, pointer, active, faction, health, None)
    sick = _exact_bool(record["sick"], "record.sick")
    return FullHealSlot(index, identity, pointer, active, faction, health, sick)


def _eligible(slot: FullHealSlot) -> bool:
    return (
        slot.identity is not None
        and slot.record_pointer is not None
        and slot.active != 0
        and slot.faction == 0
        and slot.health is not None
        and slot.health > 0
    )


def dry_run(resolve: Resolve) -> FullHealDryRun:
    """Read all 150 records in physical order without mutating anything."""

    if not callable(resolve):
        raise TypeError("resolve must be callable")
    slots: list[FullHealSlot] = []
    sick_count = 0
    partial_count = 0
    for index in range(RECORD_COUNT):
        slot = _slot_from_record(index, resolve(index))
        slots.append(slot)
        if not _eligible(slot):
            continue
        assert slot.health is not None
        if slot.sick is True:
            sick_count += 1
        if 0 < slot.health < 100:
            partial_count += 1
    return FullHealDryRun(sick_count, partial_count, tuple(slots))


def _same_snapshot(left: FullHealDryRun, right: FullHealDryRun) -> bool:
    return (
        type(left) is FullHealDryRun
        and type(right) is FullHealDryRun
        and left.slots == right.slots
        and left.sick_count == right.sick_count
        and left.partial_count == right.partial_count
    )


def _sick_phrase(count: int) -> str:
    return f"{count} sick villager was cured" if count == 1 else f"{count} sick villagers were cured"


def _partial_phrase(count: int) -> str:
    return (
        f"{count} partial-health villager was restored to exactly 100"
        if count == 1
        else f"{count} partial-health villagers were restored to exactly 100"
    )


def success_message(sick_count: int, partial_count: int) -> str:
    return f"Full Heal / Cure All completed: {_sick_phrase(sick_count)}; {_partial_phrase(partial_count)}."


def prompt_message(sick_count: int, partial_count: int) -> str:
    sick = f"{sick_count} sick villager" if sick_count == 1 else f"{sick_count} sick villagers"
    partial = f"{partial_count} partial-health villager" if partial_count == 1 else f"{partial_count} partial-health villagers"
    return f"Full Heal / Cure All will cure {sick} and restore {partial} to exactly 100 for {PRICE:,} tech points.\r\nPress OK to confirm, or Cancel."


def _failure_message(text: str) -> str:
    return f"{text}\r\n{NO_DEDUCTION}"


def _partial_message(sick_count: int, partial_count: int, reason: str) -> str:
    return (
        f"Full Heal / Cure All stopped after {_sick_phrase(sick_count)} and "
        f"{_partial_phrase(partial_count)}: {reason}. {UNKNOWN_ROLLBACK} "
        f"{NO_DEDUCTION}"
    )


def execute(
    resolve: Resolve,
    funds: int,
    confirm_result: int,
    *,
    before_reacquire: BeforeReacquire,
    before_funds_reacquire: BeforeFundsReacquire,
    after_funds_reacquire: AfterFundsReacquire,
    health_setter: HealthSetter,
    sickness_clearer: SicknessClearer,
    people_cured_incrementer: PeopleCuredIncrementer,
    deduct: Deduction,
) -> TransactionResult:
    """Run the abstract callback transaction boundary without native code."""

    _exact_int(funds, "funds")
    _exact_int(confirm_result, "confirm_result")
    if confirm_result != IDOK and confirm_result not in CANCEL_RESULTS:
        raise ValueError("confirm_result must be exact IDOK or Cancel/close")
    callbacks = {
        "before_reacquire": before_reacquire,
        "before_funds_reacquire": before_funds_reacquire,
        "after_funds_reacquire": after_funds_reacquire,
        "health_setter": health_setter,
        "sickness_clearer": sickness_clearer,
        "people_cured_incrementer": people_cured_incrementer,
        "deduct": deduct,
    }
    for name, callback in callbacks.items():
        if not callable(callback):
            raise TypeError(f"{name} is mandatory and must be callable")

    try:
        initial = dry_run(resolve)
    except (TypeError, ValueError, KeyError, IndexError):
        return TransactionResult("invalid_state", _failure_message("Full Heal / Cure All could not read an exact villager snapshot."), funds=funds)

    def result(
        status: Status,
        message: str,
        *,
        actual_sick: int = 0,
        actual_partial: int = 0,
        available_funds: int = funds,
        charged: bool = False,
        charge_verified: bool = False,
        charge_attempted: bool = False,
        native_effects: Literal["none", "may_have_occurred"] = "none",
        rollback_status: Literal["not_attempted", "unknown"] = "not_attempted",
    ) -> TransactionResult:
        return TransactionResult(
            status,
            message,
            initial.sick_count,
            initial.partial_count,
            actual_sick,
            actual_partial,
            available_funds,
            charged,
            charge_verified,
            charge_attempted,
            native_effects,
            rollback_status,
            initial,
        )

    if initial.sick_count == 0 and initial.partial_count == 0:
        return result("no_change", _failure_message("Full Heal / Cure All found no sick villagers to cure or partial-health villagers to restore to exactly 100."))
    if funds < PRICE:
        return result("insufficient_funds", _failure_message("Not enough tech points for Full Heal / Cure All."))
    if confirm_result != IDOK:
        return result("cancelled", _failure_message("Full Heal / Cure All was canceled."))

    reacquired = before_reacquire()
    if type(reacquired) is not FullHealDryRun:
        raise TypeError("before_reacquire must return an exact FullHealDryRun")
    if not _same_snapshot(initial, reacquired):
        return result("recheck_failed", _failure_message("The Full Heal / Cure All villager snapshot changed during confirmation."))

    confirmed_funds = before_funds_reacquire(funds)
    if type(confirmed_funds) is not int:
        raise TypeError("before_funds_reacquire must return an exact int")
    if confirmed_funds != funds or confirmed_funds < PRICE:
        return result("funds_recheck_failed", _failure_message("Tech points changed during Full Heal / Cure All confirmation."), available_funds=confirmed_funds)

    actual_sick = 0
    actual_partial = 0

    def partial_failure(status: Literal["partial", "partial_unknown"], reason: str) -> TransactionResult:
        effects = "may_have_occurred" if actual_sick or actual_partial else "none"
        rollback = "unknown" if effects == "may_have_occurred" else "not_attempted"
        return result(
            status,
            _partial_message(actual_sick, actual_partial, reason),
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=confirmed_funds,
            native_effects=effects,
            rollback_status=rollback,
        )

    for expected in initial.slots:
        if not _eligible(expected):
            continue
        assert expected.identity is not None and expected.record_pointer is not None
        current = _slot_from_record(expected.index, resolve(expected.index))
        if current != expected:
            return result(
                "recheck_failed" if not (actual_sick or actual_partial) else "partial",
                _failure_message("The Full Heal / Cure All record snapshot changed before mutation."),
                actual_sick=actual_sick,
                actual_partial=actual_partial,
                available_funds=confirmed_funds,
                native_effects="may_have_occurred" if actual_sick or actual_partial else "none",
                rollback_status="unknown" if actual_sick or actual_partial else "not_attempted",
            )
        assert current.health is not None

        if current.health < 100:
            outcome = _outcome(
                health_setter(current.index, current.record_pointer, 100),
                "health_setter",
            )
            if outcome == "unknown":
                return partial_failure("partial_unknown", "the native health setter outcome is unknown")
            if outcome == "failure":
                return partial_failure("partial", "the native health setter reported failure")
            after_health = _slot_from_record(current.index, resolve(current.index))
            if (
                after_health.identity != current.identity
                or after_health.record_pointer != current.record_pointer
                or after_health.active != current.active
                or after_health.faction != current.faction
                or after_health.health != 100
                or after_health.sick != current.sick
            ):
                return partial_failure("partial", "health postverification did not prove exact 100 with no unrelated change")
            actual_partial += 1

        if current.sick is True:
            before_clear = _slot_from_record(current.index, resolve(current.index))
            expected_health = 100 if current.health < 100 else current.health
            if (
                before_clear.identity != current.identity
                or before_clear.record_pointer != current.record_pointer
                or before_clear.active != current.active
                or before_clear.faction != current.faction
                or before_clear.health != expected_health
                or before_clear.sick is not True
            ):
                return partial_failure("partial", "sickness preverification did not prove the same live believer record")
            outcome = _outcome(
                sickness_clearer(current.index, current.record_pointer),
                "sickness_clearer",
            )
            if outcome == "unknown":
                return partial_failure("partial_unknown", "the native sickness-clear outcome is unknown")
            if outcome == "failure":
                return partial_failure("partial", "the native sickness-clear callback reported failure")
            after_clear = _slot_from_record(current.index, resolve(current.index))
            if (
                after_clear.identity != current.identity
                or after_clear.record_pointer != current.record_pointer
                or after_clear.active != current.active
                or after_clear.faction != current.faction
                or after_clear.health != expected_health
                or after_clear.sick is not False
            ):
                return partial_failure("partial", "sickness postverification did not prove exact clear")
            actual_sick += 1
            stat_outcome = _outcome(
                people_cured_incrementer(current.index, current.record_pointer),
                "people_cured_incrementer",
            )
            if stat_outcome == "unknown":
                return partial_failure("partial_unknown", "the People Cured update outcome is unknown")
            if stat_outcome == "failure":
                return partial_failure("partial", "the People Cured update callback reported failure")

    try:
        final = dry_run(resolve)
    except (TypeError, ValueError, KeyError, IndexError):
        return partial_failure("partial_unknown", "final postverification could not read an exact snapshot")
    if final.sick_count != 0 or final.partial_count != 0:
        return partial_failure("partial", "final postverification still found sick or partial-health villagers")
    if actual_sick != initial.sick_count or actual_partial != initial.partial_count:
        return partial_failure("partial", "verified counts did not match the confirmed counts")

    deduction_outcome = _outcome(deduct(PRICE), "deduct")
    if deduction_outcome == "unknown":
        return result(
            "charge_unknown",
            f"{success_message(actual_sick, actual_partial)} Native deduction outcome is unknown; no verified charge is claimed. {UNKNOWN_ROLLBACK}",
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=confirmed_funds,
            charge_attempted=True,
            native_effects="may_have_occurred",
            rollback_status="unknown",
        )
    if deduction_outcome == "failure":
        return result(
            "charge_failed",
            f"{success_message(actual_sick, actual_partial)} Native deduction reported failure. {NO_DEDUCTION}",
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=confirmed_funds,
            charge_attempted=True,
            native_effects="may_have_occurred",
            rollback_status="unknown",
        )
    final_funds = after_funds_reacquire(confirmed_funds)
    if final_funds is None:
        return result(
            "charge_unknown",
            f"{success_message(actual_sick, actual_partial)} Final funds reacquisition is unknown; no verified charge is claimed. {UNKNOWN_ROLLBACK}",
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=confirmed_funds,
            charge_attempted=True,
            native_effects="may_have_occurred",
            rollback_status="unknown",
        )
    if type(final_funds) is not int:
        raise TypeError("after_funds_reacquire must return an exact int or None for unknown")
    if final_funds != confirmed_funds - PRICE:
        return result(
            "charge_failed",
            f"{success_message(actual_sick, actual_partial)} Final funds did not verify one exact 30,000 deduction. {UNKNOWN_ROLLBACK}",
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=final_funds,
            charge_attempted=True,
            native_effects="may_have_occurred",
            rollback_status="unknown",
        )
    return result(
        "committed",
        success_message(actual_sick, actual_partial),
        actual_sick=actual_sick,
        actual_partial=actual_partial,
        available_funds=final_funds,
        charged=True,
        charge_verified=True,
        charge_attempted=True,
        native_effects="may_have_occurred",
        rollback_status="unknown",
    )
