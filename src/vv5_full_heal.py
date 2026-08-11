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
NO_DEDUCTION = "No tech points have been deducted."
UNKNOWN_ROLLBACK = "Rollback status is unknown; complete rollback is not claimed."
UNKNOWN_CHARGE = "The tech-point charge outcome is unknown; no no-charge claim is permitted without exact balance readback."

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
SnapshotReacquire = Callable[[], "FullHealSnapshot"]
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
    sickness read. This models the required read order without claiming a
    withdrawn synthetic eligibility field.
    """

    index: int
    identity: str | None
    record_pointer: str | None
    active: int
    faction: int
    health: int | None
    sick: bool | None

    def __post_init__(self) -> None:
        index = _exact_int(self.index, "slot.index")
        if not 0 <= index < RECORD_COUNT:
            raise ValueError("slot.index must be in exact range 0..149")
        _exact_int(self.active, "slot.active")
        _exact_int(self.faction, "slot.faction")
        if not 0 <= self.active <= 0xFF or not 0 <= self.faction <= 0xFF:
            raise ValueError("slot active and faction must be exact byte values")
        if self.identity is None or self.record_pointer is None:
            if self.identity is not None or self.record_pointer is not None:
                raise TypeError("absent slot identity and pointer must both be None")
            if self.active != 0 or self.faction != 0 or self.health is not None or self.sick is not None:
                raise ValueError("absent slots must contain only zero gate values")
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
        if tuple(slot.index for slot in self.slots) != tuple(range(RECORD_COUNT)):
            raise ValueError("dry_run slots must be unique and ordered by physical index")
        expected_sick = sum(slot.sick is True for slot in self.slots if _eligible(slot))
        expected_partial = sum(
            slot.health is not None and 0 < slot.health < 100
            for slot in self.slots if _eligible(slot)
        )
        if (self.sick_count, self.partial_count) != (expected_sick, expected_partial):
            raise ValueError("dry-run counts must exactly equal the 150-slot snapshot")


@dataclass(frozen=True)
class FullHealSnapshot:
    """One independently acquired transaction boundary snapshot."""

    selected_index: int
    selected_pointer: str
    records: FullHealDryRun
    funds: int
    people_cured: int

    def __post_init__(self) -> None:
        selected_index = _exact_int(self.selected_index, "snapshot.selected_index")
        if not 0 <= selected_index < RECORD_COUNT:
            raise ValueError("snapshot.selected_index must be in exact range 0..149")
        _exact_identity(self.selected_pointer, "snapshot.selected_pointer")
        if type(self.records) is not FullHealDryRun:
            raise TypeError("snapshot.records must be an exact FullHealDryRun")
        _exact_int(self.funds, "snapshot.funds")
        people_cured = _exact_int(self.people_cured, "snapshot.people_cured")
        if people_cured < 0:
            raise ValueError("snapshot.people_cured cannot be negative")
        selected = self.records.slots[selected_index]
        if selected.record_pointer != self.selected_pointer:
            raise ValueError("snapshot selected pointer must equal the resolved selected record pointer")


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
    charge_truth: Literal["not_attempted", "verified", "unknown"] = "not_attempted"
    dry_run: FullHealDryRun | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not str or self.status not in Status.__args__:
            raise TypeError("result.status is not exact")
        _exact_identity(self.message, "result.message")
        for name in ("predicted_sick", "predicted_partial", "actual_sick", "actual_partial", "funds"):
            value = _exact_int(getattr(self, name), f"result.{name}")
            if value < 0:
                raise ValueError(f"result.{name} cannot be negative")
        for name in ("charged", "charge_verified", "charge_attempted"):
            _exact_bool(getattr(self, name), f"result.{name}")
        if self.native_effects not in {"none", "may_have_occurred"}:
            raise TypeError("result.native_effects is not exact")
        if self.rollback_status not in {"not_attempted", "unknown"}:
            raise TypeError("result.rollback_status is not exact")
        if self.charge_truth not in {"not_attempted", "verified", "unknown"}:
            raise TypeError("result.charge_truth is not exact")
        if self.dry_run is not None and type(self.dry_run) is not FullHealDryRun:
            raise TypeError("result.dry_run must be an exact FullHealDryRun or None")
        if self.charge_verified and not (self.charge_attempted and self.charged):
            raise ValueError("verified charge requires one attempted and charged outcome")
        if self.charged and not self.charge_verified:
            raise ValueError("charged cannot be true without exact balance verification")
        if self.charge_verified and self.charge_truth != "verified":
            raise ValueError("verified charge requires verified charge truth")
        if self.charge_truth == "unknown" and self.charge_verified:
            raise ValueError("unknown charge truth cannot be verified")
        if self.status == "committed" and not self.charge_verified:
            raise ValueError("committed requires exact charge verification")


def transaction_contract() -> dict[str, object]:
    """Return the strict disabled candidate contract consumed by the builder."""

    return {
        "sequence": [
            "complete 150-record dry-run",
            "explicit IDOK/Cancel confirmation",
            "independently reacquire selected index, resolved pointer, all 150 records, funds, and People Cured",
            "require exact pre-confirmation snapshot and predicted-count equality",
            "invoke only abstract unproven health/sickness/statistic callbacks",
            "postverify complete predicted/actual 150-record and People Cured equality",
            "invoke exactly one abstract deduction callback after complete verification",
            "independently reacquire the complete after snapshot and prove one exact 30,000 deduction by balance readback",
        ],
        "confirmation_results": {"idok": IDOK, "cancel": list(CANCEL_RESULTS)},
        "record_reacquire": "independent snapshots bind selected index, resolved selected pointer, and all 150 ordered physical slots",
        "pre_confirmation_snapshot": "exact selected record, full 150-slot state, funds, People Cured, and predicted-count equality",
        "funds_reacquire": "before and after independent snapshots contain exact funds; charge truth comes only from exact balance readback",
        "required_callbacks": [
            "before_snapshot",
            "postverify_snapshot",
            "after_snapshot",
            "health_setter",
            "sickness_clearer",
            "people_cured_incrementer",
            "deduct",
        ],
        "native_callbacks": "unproven callback signatures only; no native implementation or output is emitted",
        "no_revive": "health <= 0 is excluded and never written",
        "counting": "sick and partial-health counts are separate; one overlapping record increments both",
        "postverify": "complete predicted and actual 150-record snapshots, counts, and People Cured readback must be exactly equal",
        "charge_verification": "one deduction callback only after postverify; charge is true only when exact after-balance equals before-balance minus 30,000",
        "native_effects": "callbacks may have native effects; this reference model supplies no rollback implementation",
        "rollback_disclosure": UNKNOWN_ROLLBACK,
        "charge_disclosure": "callback return values never prove charge or no-charge; exact balance readback is authoritative, otherwise charge is unknown",
        "unknown_charge_text": UNKNOWN_CHARGE,
        "no_charge_suffix": NO_DEDUCTION,
        "no_charge_results": [
            "invalid_state",
            "no_change",
            "cancelled",
            "insufficient_funds",
            "recheck_failed",
            "funds_recheck_failed",
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
    # sickness. No withdrawn synthetic eligibility field is present or read.
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
    selected_index: int,
    selected_pointer: str,
    people_cured: int,
    before_snapshot: SnapshotReacquire,
    postverify_snapshot: SnapshotReacquire,
    after_snapshot: SnapshotReacquire,
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
    selected_index = _exact_int(selected_index, "selected_index")
    if not 0 <= selected_index < RECORD_COUNT:
        raise ValueError("selected_index must be in exact range 0..149")
    selected_pointer = _exact_identity(selected_pointer, "selected_pointer")
    people_cured = _exact_int(people_cured, "people_cured")
    if funds < 0 or people_cured < 0:
        raise ValueError("funds and people_cured cannot be negative")
    callbacks = {
        "before_snapshot": before_snapshot,
        "postverify_snapshot": postverify_snapshot,
        "after_snapshot": after_snapshot,
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
    except Exception:
        return TransactionResult(
            "invalid_state",
            f"Full Heal / Cure All could not read an exact villager snapshot. Callback effects may have occurred; {UNKNOWN_ROLLBACK} {UNKNOWN_CHARGE}",
            funds=funds,
            native_effects="may_have_occurred",
            rollback_status="unknown",
            charge_truth="unknown",
        )

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
        charge_truth: Literal["not_attempted", "verified", "unknown"] = "not_attempted",
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
            charge_truth,
            initial,
        )

    if initial.sick_count == 0 and initial.partial_count == 0:
        return result("no_change", _failure_message("Full Heal / Cure All found no sick villagers to cure or partial-health villagers to restore to exactly 100."))
    if funds < PRICE:
        return result("insufficient_funds", _failure_message("Not enough tech points for Full Heal / Cure All."))
    if confirm_result != IDOK:
        return result("cancelled", _failure_message("Full Heal / Cure All was canceled."))

    try:
        before = before_snapshot()
    except Exception:
        return result(
            "recheck_failed",
            f"The independent pre-mutation snapshot callback failed. Callback effects may have occurred; {UNKNOWN_ROLLBACK} {UNKNOWN_CHARGE}",
            native_effects="may_have_occurred",
            rollback_status="unknown",
            charge_truth="unknown",
        )
    if type(before) is not FullHealSnapshot:
        return result(
            "recheck_failed",
            f"The independent pre-mutation snapshot callback returned an invalid value. Callback effects may have occurred; {UNKNOWN_ROLLBACK} {UNKNOWN_CHARGE}",
            native_effects="may_have_occurred",
            rollback_status="unknown",
            charge_truth="unknown",
        )
    if (
        before.selected_index != selected_index
        or before.selected_pointer != selected_pointer
        or before.funds != funds
        or before.people_cured != people_cured
        or not _same_snapshot(initial, before.records)
    ):
        return result("recheck_failed", _failure_message("The Full Heal / Cure All villager snapshot changed during confirmation."))
    confirmed_funds = before.funds

    actual_sick = 0
    actual_partial = 0

    def partial_failure(status: Literal["partial", "partial_unknown"], reason: str) -> TransactionResult:
        effects = "may_have_occurred"
        rollback = "unknown"
        return result(
            status,
            f"Full Heal / Cure All stopped: {reason}. Callback effects may have occurred. {UNKNOWN_ROLLBACK}",
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=confirmed_funds,
            native_effects=effects,
            rollback_status=rollback,
            charge_truth="unknown",
        )

    for expected in initial.slots:
        if not _eligible(expected):
            continue
        assert expected.identity is not None and expected.record_pointer is not None
        try:
            current = _slot_from_record(expected.index, resolve(expected.index))
        except Exception:
            return partial_failure("partial_unknown", "the record resolver callback failed before mutation")
        if current != expected:
            return result(
                "recheck_failed" if not (actual_sick or actual_partial) else "partial",
                _failure_message("The Full Heal / Cure All record snapshot changed before mutation."),
                actual_sick=actual_sick,
                actual_partial=actual_partial,
                available_funds=confirmed_funds,
                native_effects="may_have_occurred" if actual_sick or actual_partial else "none",
                rollback_status="unknown" if actual_sick or actual_partial else "not_attempted",
                charge_truth="unknown" if actual_sick or actual_partial else "not_attempted",
            )
        assert current.health is not None

        if current.health < 100:
            try:
                outcome = _outcome(health_setter(current.index, current.record_pointer, 100), "health_setter")
            except Exception:
                return partial_failure("partial_unknown", "the health callback raised after possible mutation")
            if outcome == "unknown":
                return partial_failure("partial_unknown", "the native health setter outcome is unknown")
            if outcome == "failure":
                return partial_failure("partial", "the native health setter reported failure")
            try:
                after_health = _slot_from_record(current.index, resolve(current.index))
            except Exception:
                return partial_failure("partial_unknown", "the health postverification resolver callback failed")
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
            try:
                before_clear = _slot_from_record(current.index, resolve(current.index))
            except Exception:
                return partial_failure("partial_unknown", "the sickness preverification resolver callback failed")
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
            try:
                outcome = _outcome(sickness_clearer(current.index, current.record_pointer), "sickness_clearer")
            except Exception:
                return partial_failure("partial_unknown", "the sickness callback raised after possible mutation")
            if outcome == "unknown":
                return partial_failure("partial_unknown", "the native sickness-clear outcome is unknown")
            if outcome == "failure":
                return partial_failure("partial", "the native sickness-clear callback reported failure")
            try:
                after_clear = _slot_from_record(current.index, resolve(current.index))
            except Exception:
                return partial_failure("partial_unknown", "the sickness postverification resolver callback failed")
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
            try:
                stat_outcome = _outcome(people_cured_incrementer(current.index, current.record_pointer), "people_cured_incrementer")
            except Exception:
                return partial_failure("partial_unknown", "the People Cured callback raised after possible mutation")
            if stat_outcome == "unknown":
                return partial_failure("partial_unknown", "the People Cured update outcome is unknown")
            if stat_outcome == "failure":
                return partial_failure("partial", "the People Cured update callback reported failure")

    try:
        final = dry_run(resolve)
    except Exception:
        return partial_failure("partial_unknown", "final postverification could not read an exact snapshot")
    expected_slots = tuple(
        FullHealSlot(
            slot.index, slot.identity, slot.record_pointer, slot.active, slot.faction,
            100 if _eligible(slot) and slot.health is not None and 0 < slot.health < 100 else slot.health,
            False if _eligible(slot) and slot.sick is True else slot.sick,
        )
        for slot in initial.slots
    )
    expected_final = FullHealDryRun(0, 0, expected_slots)
    if final != expected_final:
        return partial_failure("partial", "final postverification did not equal the complete predicted 150-record snapshot")
    if actual_sick != initial.sick_count or actual_partial != initial.partial_count:
        return partial_failure("partial", "verified counts did not match the confirmed counts")

    try:
        verified = postverify_snapshot()
    except Exception:
        return partial_failure("partial_unknown", "the complete post-mutation snapshot could not be reacquired")
    if type(verified) is not FullHealSnapshot:
        return partial_failure("partial_unknown", "the postverification callback returned an invalid snapshot")
    if (
        verified.selected_index != selected_index
        or verified.selected_pointer != selected_pointer
        or verified.records != expected_final
        or verified.funds != confirmed_funds
        or verified.people_cured != people_cured + initial.sick_count
    ):
        return partial_failure("partial", "postverification did not equal the complete predicted records, funds, and People Cured snapshot")

    try:
        deduction_outcome = _outcome(deduct(PRICE), "deduct")
    except Exception:
        deduction_outcome = "unknown"
    try:
        after = after_snapshot()
    except Exception:
        after = None
    if type(after) is not FullHealSnapshot:
        return result(
            "charge_unknown",
            f"{success_message(actual_sick, actual_partial)} Final snapshot is unavailable; charge and callback effects are unknown. {UNKNOWN_ROLLBACK}",
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=confirmed_funds,
            charge_attempted=True,
            native_effects="may_have_occurred",
            rollback_status="unknown",
            charge_truth="unknown",
        )
    if (
        after.selected_index != selected_index
        or after.selected_pointer != selected_pointer
        or after.records != expected_final
        or after.people_cured != verified.people_cured
    ):
        return result(
            "charge_unknown",
            f"{success_message(actual_sick, actual_partial)} Final record/statistic snapshot did not exactly match the prediction; charge is unknown. {UNKNOWN_ROLLBACK}",
            actual_sick=actual_sick, actual_partial=actual_partial,
            available_funds=after.funds, charge_attempted=True,
            native_effects="may_have_occurred", rollback_status="unknown", charge_truth="unknown",
        )
    if after.funds != confirmed_funds - PRICE:
        return result(
            "charge_unknown",
            f"{success_message(actual_sick, actual_partial)} Exact balance readback did not prove one 30,000-point charge; charge is unknown. {UNKNOWN_ROLLBACK}",
            actual_sick=actual_sick,
            actual_partial=actual_partial,
            available_funds=after.funds,
            charge_attempted=True,
            native_effects="may_have_occurred",
            rollback_status="unknown",
            charge_truth="unknown",
        )
    return result(
        "committed",
        success_message(actual_sick, actual_partial),
        actual_sick=actual_sick,
        actual_partial=actual_partial,
        available_funds=after.funds,
        charged=True,
        charge_verified=True,
        charge_attempted=True,
        native_effects="may_have_occurred",
        rollback_status="unknown",
        charge_truth="verified",
    )
