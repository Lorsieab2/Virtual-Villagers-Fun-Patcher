"""Fail-closed Grant Running transaction model for VV1-VV5.

The model is deliberately independent of any executable.  It scans the
configured physical Like/Dislike slots without mutating them, plans only the
first empty Like insertion, and exposes native callbacks for the eventual
write and deduction.  A binding cannot be committed unless its complete
native preference-write and deduction ABIs are certified and enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


PRICE = 40_000
RUNNING = 38
EMPTY = -1
NO_DEDUCTION = "No tech points have been deducted."
ALREADY_MESSAGE = f"This villager already likes Running.\r\n{NO_DEDUCTION}"
NO_SLOT_MESSAGE = f"This villager has no empty Like slot.\r\n{NO_DEDUCTION}"
INVALID_MESSAGE = f"No valid living villager is selected.\r\n{NO_DEDUCTION}"
CANCELED_MESSAGE = f"Grant Running was canceled.\r\n{NO_DEDUCTION}"
RACE_MESSAGE = f"The selected villager changed during confirmation.\r\n{NO_DEDUCTION}"
WRITE_FAILURE_MESSAGE = f"Running could not be verified.\r\n{NO_DEDUCTION}"
DISABLED_MESSAGE = f"Grant Running is unavailable for this build.\r\n{NO_DEDUCTION}"
SUCCESS_MESSAGE = "Running was granted."


@dataclass(frozen=True)
class RunningBinding:
    """Exact-build field binding and native certification gate."""

    game_id: str
    fingerprint: str
    record_stride: int
    like_offsets: tuple[int, ...]
    dislike_offsets: tuple[int, ...]
    running_id: int = RUNNING
    empty_id: int = EMPTY
    price: int = PRICE
    enabled: bool = False
    preference_write_abi_proven: bool = False
    deduction_abi_proven: bool = False

    def __post_init__(self) -> None:
        if not self.game_id or len(self.fingerprint) != 64:
            raise ValueError("Grant Running binding identity is incomplete")
        if not self.like_offsets or len(self.like_offsets) != len(self.dislike_offsets):
            raise ValueError("Like/Dislike slot bounds must match")
        if self.running_id == self.empty_id:
            raise ValueError("Running and empty IDs must differ")
        if self.price <= 0:
            raise ValueError("Grant Running price must be positive")

    @property
    def slot_count(self) -> int:
        return len(self.like_offsets)

    @property
    def commit_enabled(self) -> bool:
        return self.enabled and self.preference_write_abi_proven and self.deduction_abi_proven


def _manifest_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric binding value")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError("binding value is not an integer")


def binding_from_manifest(raw: Mapping[str, Any]) -> RunningBinding:
    """Normalize either per-game binding manifest shape into the shared model."""

    exact = raw.get("exact_build") or raw.get("stock_fingerprint") or raw.get("fingerprint")
    layout = raw.get("record_identity") or raw.get("record_layout")
    if not isinstance(exact, Mapping) or not isinstance(layout, Mapping):
        raise ValueError("binding manifest is missing exact-build identity or record layout")
    slots = raw.get("preference_slots") or raw.get("slots") or raw.get("preferences")
    if isinstance(slots, Mapping):
        like = slots.get("like") or slots.get("likes") or slots.get("like_slots")
        dislike = slots.get("dislike") or slots.get("dislikes") or slots.get("dislike_slots")
    else:
        like = raw.get("like_slots")
        dislike = raw.get("dislike_slots")
    if not isinstance(like, Mapping) or not isinstance(dislike, Mapping):
        raise ValueError("binding manifest is missing Like/Dislike slots")
    def offsets(section: Mapping[str, Any]) -> tuple[int, ...]:
        raw_offsets = section.get("offsets")
        if isinstance(raw_offsets, Sequence) and not isinstance(raw_offsets, (str, bytes, bytearray)):
            return tuple(_manifest_int(item) for item in raw_offsets)
        base = section.get("base_offset")
        count = section.get("count")
        stride = section.get("slot_stride", 4)
        if base is None or count is None:
            return ()
        return tuple(
            _manifest_int(base) + _manifest_int(stride) * index
            for index in range(_manifest_int(count))
        )

    like_offsets = offsets(like)
    dislike_offsets = offsets(dislike)
    native = (
        raw.get("native_abi")
        or raw.get("native_abi_proof")
        or raw.get("native_abi_proof_status")
    )
    if not isinstance(native, Mapping):
        native = {}
    running_meta = raw.get("running") or raw.get("running_preference")
    running_value = running_meta.get("id") if isinstance(running_meta, Mapping) else None
    if running_value is None:
        running_value = exact.get("running_id")
    if running_value is None and isinstance(slots, Mapping):
        running_value = slots.get("running_id")
    if running_value is None:
        running_value = RUNNING
    return RunningBinding(
        game_id=str(raw["game_id"]),
        fingerprint=str(exact["sha256"]),
        record_stride=_manifest_int(layout.get("stride", layout.get("record_stride"))),
        like_offsets=like_offsets,
        dislike_offsets=dislike_offsets,
        running_id=_manifest_int(running_value),
        empty_id=_manifest_int(
            (
                slots.get(
                    "sentinel",
                    slots.get("empty_value", slots.get("empty_id", like.get("empty", EMPTY))),
                )
                if isinstance(slots, Mapping)
                else like.get("empty", EMPTY)
            )
        ),
        price=_manifest_int((raw.get("transaction_contract") or {}).get("price", PRICE)),
        enabled=raw.get("enabled") is True,
        preference_write_abi_proven=(
            native.get("complete_preference_write_abi_proved") is True
            or (
                isinstance(native.get("preference_write"), Mapping)
                and native["preference_write"].get("complete") is True
            )
        ),
        deduction_abi_proven=native.get("deduction_abi_proven") is True,
    )


@dataclass(frozen=True)
class RunningScan:
    eligible: bool
    likes: tuple[int, ...] = ()
    dislikes: tuple[int, ...] = ()
    already_running: bool = False
    first_empty_like: int | None = None
    running_dislikes: tuple[int, ...] = ()


@dataclass(frozen=True)
class RunningPlan:
    status: str
    message: str
    binding: RunningBinding
    like_index: int | None = None
    dislike_indices: tuple[int, ...] = ()
    before_likes: tuple[int, ...] = ()
    before_dislikes: tuple[int, ...] = ()
    after_likes: tuple[int, ...] = ()
    after_dislikes: tuple[int, ...] = ()
    deduction: int = 0


@dataclass(frozen=True)
class ApplyResult:
    status: str
    message: str
    charged: bool = False
    rollback: str = "not-needed"


def _int_slots(record: Mapping[str, object], key: str, count: int) -> tuple[int, ...] | None:
    raw = record.get(key)
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return None
    if len(raw) != count:
        return None
    try:
        return tuple(int(value) for value in raw)
    except (TypeError, ValueError, OverflowError):
        return None


def _eligible(record: Mapping[str, object], binding: RunningBinding) -> bool:
    try:
        health = int(record.get("health", 0))
    except (TypeError, ValueError, OverflowError):
        return False
    if not bool(record.get("active", False)) or health <= 0:
        return False
    if binding.game_id == "vv5":
        # The faction gate is the only supported current-believer predicate.
        # Missing fields fail closed; the unproved status-byte substitute is
        # intentionally not accepted here.
        if record.get("faction") != 0:
            return False
        if record.get("heathen_active") != 0:
            return False
    return True


def scan_running(record: Mapping[str, object], binding: RunningBinding) -> RunningScan:
    """Read every configured slot and return a mutation-free scan."""

    # Eligibility is a hard gate.  Do not touch preference storage for an
    # inactive, unhealthy, or VV5-faction-ineligible record.
    if not _eligible(record, binding):
        return RunningScan(False)
    likes = _int_slots(record, "likes", binding.slot_count)
    dislikes = _int_slots(record, "dislikes", binding.slot_count)
    if likes is None or dislikes is None:
        return RunningScan(False)
    already = binding.running_id in likes
    first_empty = None if already else next(
        (index for index, value in enumerate(likes) if value == binding.empty_id),
        None,
    )
    running_dislikes = tuple(
        index for index, value in enumerate(dislikes) if value == binding.running_id
    )
    return RunningScan(
        True,
        likes,
        dislikes,
        already_running=already,
        first_empty_like=first_empty,
        running_dislikes=running_dislikes,
    )


def _plan_from_scan(scan: RunningScan, binding: RunningBinding) -> RunningPlan:
    if not scan.eligible:
        return RunningPlan("invalid", INVALID_MESSAGE, binding)
    if scan.already_running:
        return RunningPlan("no_change", ALREADY_MESSAGE, binding, before_likes=scan.likes, before_dislikes=scan.dislikes)
    if scan.first_empty_like is None:
        return RunningPlan("no_change", NO_SLOT_MESSAGE, binding, before_likes=scan.likes, before_dislikes=scan.dislikes)
    after_likes = list(scan.likes)
    after_likes[scan.first_empty_like] = binding.running_id
    after_dislikes = list(scan.dislikes)
    for index in scan.running_dislikes:
        after_dislikes[index] = binding.empty_id
    return RunningPlan(
        "candidate",
        "",
        binding,
        like_index=scan.first_empty_like,
        dislike_indices=scan.running_dislikes,
        before_likes=scan.likes,
        before_dislikes=scan.dislikes,
        after_likes=tuple(after_likes),
        after_dislikes=tuple(after_dislikes),
        deduction=binding.price,
    )


def plan_transaction(
    record: Mapping[str, object],
    balance: int,
    confirmed: bool,
    reacquire: Callable[[], tuple[Mapping[str, object], int]],
    binding: RunningBinding,
) -> RunningPlan:
    """Perform dry-run, confirmation, reacquisition, and final recheck.

    The input record and every reacquired record are read-only mappings from
    this model's perspective.  The caller supplies native callbacks only after
    receiving a ``commit`` plan from a certified binding.
    """

    initial = scan_running(record, binding)
    planned = _plan_from_scan(initial, binding)
    if planned.status != "candidate":
        return planned
    if balance < binding.price:
        return RunningPlan("insufficient", f"Not enough tech points.\r\n{NO_DEDUCTION}", binding)
    if not confirmed:
        return RunningPlan("cancel", CANCELED_MESSAGE, binding)

    current_record, current_balance = reacquire()
    if record.get("identity") is None or current_record.get("identity") != record.get("identity"):
        return RunningPlan("race", RACE_MESSAGE, binding)
    current = scan_running(current_record, binding)
    if current != initial:
        return RunningPlan("race", RACE_MESSAGE, binding)
    if current_balance < binding.price:
        return RunningPlan("insufficient", f"Not enough tech points.\r\n{NO_DEDUCTION}", binding)
    return RunningPlan(
        "commit",
        "",
        binding,
        like_index=planned.like_index,
        dislike_indices=planned.dislike_indices,
        before_likes=planned.before_likes,
        before_dislikes=planned.before_dislikes,
        after_likes=planned.after_likes,
        after_dislikes=planned.after_dislikes,
        deduction=binding.price,
    )


def apply_plan(
    plan: RunningPlan,
    write_like: Callable[[int, int], None],
    write_dislike: Callable[[int, int], None],
    read_slots: Callable[[], tuple[Sequence[int], Sequence[int]]],
    deduct: Callable[[int], None],
    restore_slot: Callable[[str, int, int], None] | None = None,
) -> ApplyResult:
    """Apply a committed plan through native callbacks with bounded rollback."""

    if plan.status != "commit":
        return ApplyResult(plan.status, plan.message)
    if not plan.binding.commit_enabled:
        return ApplyResult("disabled", DISABLED_MESSAGE)
    assert plan.like_index is not None
    written: list[tuple[str, int, int]] = []
    try:
        write_like(plan.like_index, plan.binding.running_id)
        written.append(("like", plan.like_index, plan.before_likes[plan.like_index]))
        for index in plan.dislike_indices:
            write_dislike(index, plan.binding.empty_id)
            written.append(("dislike", index, plan.before_dislikes[index]))
    except Exception:
        return _rollback(plan, written, read_slots, restore_slot, "write-failed")

    try:
        likes, dislikes = read_slots()
        if tuple(likes) != plan.after_likes or tuple(dislikes) != plan.after_dislikes:
            return _rollback(plan, written, read_slots, restore_slot, "postverify-failed")
        deduct(plan.deduction)
    except Exception:
        return _rollback(plan, written, read_slots, restore_slot, "deduction-failed")
    return ApplyResult("committed", SUCCESS_MESSAGE, charged=True)


def _rollback(
    plan: RunningPlan,
    written: list[tuple[str, int, int]],
    read_slots: Callable[[], tuple[Sequence[int], Sequence[int]]],
    restore_slot: Callable[[str, int, int], None] | None,
    reason: str,
) -> ApplyResult:
    if restore_slot is None:
        return ApplyResult(reason, WRITE_FAILURE_MESSAGE, rollback="unavailable")
    try:
        likes, dislikes = read_slots()
        if tuple(likes) != plan.after_likes or tuple(dislikes) != plan.after_dislikes:
            return ApplyResult(reason, WRITE_FAILURE_MESSAGE, rollback="unsafe")
        for kind, index, value in reversed(written):
            restore_slot(kind, index, value)
        final_likes, final_dislikes = read_slots()
        if tuple(final_likes) != plan.before_likes or tuple(final_dislikes) != plan.before_dislikes:
            return ApplyResult(reason, WRITE_FAILURE_MESSAGE, rollback="partial")
    except Exception:
        return ApplyResult(reason, WRITE_FAILURE_MESSAGE, rollback="partial")
    return ApplyResult(reason, WRITE_FAILURE_MESSAGE, rollback="complete")
