"""Fail-closed Grant Running transaction model for VV1-VV5.

The model is deliberately independent of any executable.  It scans the
configured physical Like/Dislike slots without mutating them, plans only the
first empty Like insertion, and exposes native callbacks for the eventual
write and deduction.  Adapter records must provide exact integer identity,
selected-index, resolved-record-pointer, eligibility, and balance fields;
these are reference-contract requirements, not native proof.  A binding
cannot be committed unless its complete native preference-write and
deduction ABIs are certified and enabled.
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
IDENTITY_UNKNOWN_MESSAGE = (
    f"The selected villager or tech account could not be revalidated.\r\n{NO_DEDUCTION}"
)
WRITE_FAILURE_MESSAGE = f"Running could not be verified.\r\n{NO_DEDUCTION}"
ROLLBACK_UNVERIFIED_MESSAGE = (
    "Preference rollback could not be verified; retained per-slot effects may remain."
)
DISABLED_MESSAGE = f"Grant Running is unavailable for this build.\r\n{NO_DEDUCTION}"
CHARGE_UNKNOWN_MESSAGE = (
    "Grant Running charge outcome could not be verified.\r\n"
    "The tech-point deduction state is unknown; no no-charge claim is made."
)
SUCCESS_MESSAGE = "Running was granted."
CHARGE_NOT_ATTEMPTED = "not-attempted"
CHARGE_NOT_CHARGED = "not-charged"
CHARGE_CHARGED = "charged"
CHARGE_UNKNOWN = "unknown"
IDOK = 1
IDCANCEL = 2
IDCLOSE = 0
CONFIRM_CANCEL_RESULTS = frozenset({IDCLOSE, IDCANCEL})
UINT32_MAX = 0xFFFFFFFF
INT32_MAX = 0x7FFFFFFF
HEALTH_MAX = INT32_MAX
RECORD_POINTER_MIN = 1
RECORD_INDEX_MIN = 0


@dataclass(frozen=True)
class RunningBinding:
    """Exact-build field binding and native certification gate."""

    game_id: str
    fingerprint: str
    record_stride: int
    like_offsets: tuple[int, ...]
    dislike_offsets: tuple[int, ...]
    image_size: int = 0
    record_count: int = 256
    running_id: int = RUNNING
    empty_id: int = EMPTY
    price: int = PRICE
    enabled: bool = False
    preference_write_abi_proven: bool = False
    deduction_abi_proven: bool = False
    eligibility_order_declared: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.game_id, str) or not self.game_id:
            raise ValueError("Grant Running binding identity is incomplete")
        if not self.like_offsets or len(self.like_offsets) != len(self.dislike_offsets):
            raise ValueError("Like/Dislike slot bounds must match")
        if (
            not isinstance(self.fingerprint, str)
            or len(self.fingerprint) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in self.fingerprint)
        ):
            raise ValueError("Grant Running binding fingerprint must be a 64-digit SHA-256")
        if type(self.image_size) is not int or self.image_size <= 0:
            raise ValueError("Grant Running binding image size must be a positive integer")
        if type(self.record_count) is not int or not 1 <= self.record_count <= 256:
            raise ValueError("Grant Running record count must be an exact integer in 1..256")
        if type(self.record_stride) is not int or self.record_stride <= 0 or self.record_stride % 4:
            raise ValueError("Grant Running record stride must be a positive DWORD-aligned integer")
        all_offsets = self.like_offsets + self.dislike_offsets
        if any(type(offset) is not int for offset in all_offsets):
            raise ValueError("Grant Running slot offsets must be exact integers")
        if len(set(all_offsets)) != len(all_offsets):
            raise ValueError("Grant Running slot offsets must be unique")
        if any(offset < 0 or offset % 4 or offset + 4 > self.record_stride for offset in all_offsets):
            raise ValueError("Grant Running slot offsets must be aligned and in-record")
        if type(self.running_id) is not int or type(self.empty_id) is not int:
            raise ValueError("Grant Running IDs must be exact integers")
        if self.running_id == self.empty_id:
            raise ValueError("Running and empty IDs must differ")
        if type(self.price) is not int or self.price <= 0:
            raise ValueError("Grant Running price must be positive")
        if self.price > UINT32_MAX:
            raise ValueError("Grant Running price must fit an unsigned DWORD")
        for name in (
            "enabled",
            "preference_write_abi_proven",
            "deduction_abi_proven",
            "eligibility_order_declared",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"Grant Running {name} must be a boolean")

    @property
    def slot_count(self) -> int:
        return len(self.like_offsets)

    @property
    def commit_enabled(self) -> bool:
        return (
            self.enabled
            and self.preference_write_abi_proven
            and self.deduction_abi_proven
            and self.eligibility_order_declared
        )


def _manifest_int(value: object, *, field: str, allow_hex_string: bool = True) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must not be boolean")
    if isinstance(value, int):
        return value
    if (
        allow_hex_string
        and isinstance(value, str)
        and len(value) > 2
        and value.startswith("0x")
        and all(character in "0123456789abcdefABCDEF" for character in value[2:])
    ):
        return int(value, 16)
    raise ValueError(f"{field} must be an exact integer or canonical hexadecimal address string")


def binding_from_manifest(raw: Mapping[str, Any]) -> RunningBinding:
    """Normalize either per-game binding manifest shape into the shared model."""

    exact = raw.get("exact_build") or raw.get("stock_fingerprint") or raw.get("fingerprint")
    layout = raw.get("record_identity") or raw.get("record_layout")
    if not isinstance(exact, Mapping) or not isinstance(layout, Mapping):
        raise ValueError("binding manifest is missing exact-build identity or record layout")
    if type(raw.get("game_id")) is not str or not raw["game_id"]:
        raise ValueError("binding manifest game_id must be a non-empty string")
    fingerprint = exact.get("sha256")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in fingerprint
    ):
        raise ValueError("binding manifest fingerprint must be a 64-digit SHA-256")
    image_size = _manifest_int(exact.get("size"), field="exact-build size", allow_hex_string=False)
    if image_size <= 0:
        raise ValueError("binding manifest exact-build size must be positive")
    record_stride = _manifest_int(
        layout.get("stride", layout.get("record_stride")),
        field="record stride",
    )
    if record_stride <= 0 or record_stride % 4:
        raise ValueError("binding manifest record stride must be positive and DWORD-aligned")
    record_count_value = layout.get(
        "physical_bound",
        layout.get("physical_record_count", layout.get("record_count")),
    )
    if record_count_value is None and isinstance(layout.get("selected_index"), Mapping):
        record_count_value = layout["selected_index"].get(
            "bound_exclusive",
            layout["selected_index"].get("record_count"),
        )
    if type(record_count_value) is not int or not 1 <= record_count_value <= 256:
        raise ValueError("binding manifest record count must be an exact integer in 1..256")
    if raw.get("status") not in {"STOP", "GO"}:
        raise ValueError("binding manifest status must be STOP or GO")
    if raw.get("status") == "STOP" and raw.get("enabled") is True:
        raise ValueError("STOP binding cannot be enabled")
    if raw.get("catalog_enabled") is True and raw.get("enabled") is not True:
        raise ValueError("catalog-enabled binding must also be enabled")
    # This is ordering metadata only; it is not native selected-index,
    # resolver, living/status, or VV5 current-believer proof.
    if raw.get("eligibility_gate_order") != "before_preference_access":
        raise ValueError("binding manifest must declare eligibility ordering before preference access")
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
            count = section.get("count")
            if type(count) is not int or count <= 0 or count != len(raw_offsets):
                raise ValueError("binding manifest slot count must be an exact positive integer matching offsets")
            result = tuple(
                _manifest_int(item, field="slot offset")
                for item in raw_offsets
            )
            if len(set(result)) != len(result):
                raise ValueError("binding manifest slot offsets must be unique")
            return result
        base = section.get("base_offset")
        count = section.get("count")
        stride = section.get("slot_stride", 4)
        if base is None or count is None:
            return ()
        if type(count) is not int or count <= 0:
            raise ValueError("binding manifest slot count must be an exact positive integer")
        slot_stride = _manifest_int(stride, field="slot stride")
        if slot_stride != 4:
            raise ValueError("Grant Running preference slots must be DWORD-spaced")
        return tuple(
            _manifest_int(base, field="slot base") + slot_stride * index
            for index in range(count)
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
        game_id=raw["game_id"],
        fingerprint=fingerprint,
        record_stride=record_stride,
        like_offsets=like_offsets,
        dislike_offsets=dislike_offsets,
        image_size=image_size,
        record_count=record_count_value,
        running_id=_manifest_int(running_value, field="Running ID", allow_hex_string=False),
        empty_id=_manifest_int(
            (
                slots.get(
                    "sentinel",
                    slots.get("empty_value", slots.get("empty_id", like.get("empty", EMPTY))),
                )
                if isinstance(slots, Mapping)
                else like.get("empty", EMPTY)
            ),
            field="empty ID",
            allow_hex_string=False,
        ),
        price=_manifest_int(
            (raw.get("transaction_contract") or {}).get("price", PRICE),
            field="transaction price",
            allow_hex_string=False,
        ),
        enabled=raw.get("enabled") is True,
        preference_write_abi_proven=(
            native.get("complete_preference_write_abi_proved") is True
            or (
                isinstance(native.get("preference_write"), Mapping)
                and native["preference_write"].get("complete") is True
            )
        ),
        deduction_abi_proven=native.get("deduction_abi_proven") is True,
        eligibility_order_declared=raw.get("eligibility_gate_order") == "before_preference_access",
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
    record_identity: tuple[int, int, int] | None = None
    account_identity: int | None = None


@dataclass(frozen=True)
class DeductionOutcome:
    """Adapter assertion of an atomic deduction result, not independent proof."""

    status: str

    def __post_init__(self) -> None:
        if self.status not in {CHARGE_CHARGED, CHARGE_NOT_CHARGED, CHARGE_UNKNOWN}:
            raise ValueError("deduction outcome must be charged, not-charged, or unknown")


@dataclass(frozen=True)
class ApplyResult:
    status: str
    message: str
    charged: bool | None = False
    rollback: str = "not-needed"
    charge_status: str = CHARGE_NOT_ATTEMPTED


def _exact_slot_values(raw: object, count: int) -> tuple[int, ...] | None:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return None
    if len(raw) != count:
        return None
    if any(type(value) is not int for value in raw):
        return None
    return tuple(raw)


def _int_slots(record: Mapping[str, object], key: str, count: int) -> tuple[int, ...] | None:
    return _exact_slot_values(record.get(key), count)


def _read_slot_snapshot(
    read_slots: Callable[[], tuple[Sequence[int], Sequence[int]]],
    count: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    likes, dislikes = read_slots()
    exact_likes = _exact_slot_values(likes, count)
    exact_dislikes = _exact_slot_values(dislikes, count)
    if exact_likes is None or exact_dislikes is None:
        raise ValueError("native preference readback must contain exact integer slots")
    return exact_likes, exact_dislikes


def _strict_field(value: object, *, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{field} must be an exact integer in {minimum}..{maximum}")
    return value


def _record_identity(
    record: Mapping[str, object],
    binding: RunningBinding,
) -> tuple[int, int, int]:
    if not isinstance(record, Mapping):
        raise ValueError("selected record must be a mapping")
    identity = _strict_field(
        record.get("identity"),
        field="record identity",
        minimum=RECORD_POINTER_MIN,
        maximum=UINT32_MAX,
    )
    selected_index = _strict_field(
        record.get("selected_index"),
        field="selected record index",
        minimum=RECORD_INDEX_MIN,
        maximum=binding.record_count - 1,
    )
    if "record_pointer" in record:
        pointer_value = record.get("record_pointer")
    elif "resolved_record_pointer" in record:
        pointer_value = record.get("resolved_record_pointer")
    else:
        pointer_value = None
    record_pointer = _strict_field(
        pointer_value,
        field="resolved record pointer",
        minimum=RECORD_POINTER_MIN,
        maximum=UINT32_MAX,
    )
    return identity, selected_index, record_pointer


def _callback_record_identity(raw: object, binding: RunningBinding) -> tuple[int, int, int]:
    if not isinstance(raw, tuple) or len(raw) != 3:
        raise ValueError("selection identity callback must return an exact three-item tuple")
    identity = _strict_field(
        raw[0], field="record identity", minimum=RECORD_POINTER_MIN, maximum=UINT32_MAX
    )
    selected_index = _strict_field(
        raw[1], field="selected record index", minimum=RECORD_INDEX_MIN,
        maximum=binding.record_count - 1,
    )
    record_pointer = _strict_field(
        raw[2], field="resolved record pointer", minimum=RECORD_POINTER_MIN,
        maximum=UINT32_MAX,
    )
    return identity, selected_index, record_pointer


def _account_snapshot(raw: object) -> tuple[int, int]:
    if not isinstance(raw, tuple) or len(raw) != 2:
        raise ValueError("account callback must return an exact two-item tuple")
    account_identity = _strict_field(
        raw[0], field="tech account identity", minimum=RECORD_POINTER_MIN,
        maximum=UINT32_MAX,
    )
    return account_identity, _strict_balance(raw[1])


def _eligible(record: Mapping[str, object], binding: RunningBinding) -> bool:
    try:
        _record_identity(record, binding)
        active = _strict_field(record.get("active"), field="active", minimum=0, maximum=1)
        health = _strict_field(record.get("health"), field="health", minimum=0, maximum=HEALTH_MAX)
    except (TypeError, ValueError, OverflowError):
        return False
    if active != 1 or health <= 0:
        return False
    if binding.game_id == "vv5":
        # Current faction +0x1CEC == 0 is the only supported VV5
        # current-believer predicate.  No +0x1CE1/status substitute is used.
        try:
            faction = _strict_field(record.get("faction"), field="VV5 faction", minimum=0, maximum=1)
        except (TypeError, ValueError, OverflowError):
            return False
        if faction != 0:
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
    confirmed: object,
    reacquire: Callable[[], tuple[Mapping[str, object], int, int]],
    binding: RunningBinding,
    *,
    account_identity: object,
) -> RunningPlan:
    """Perform dry-run, confirmation, reacquisition, and final recheck.

    The input record and every reacquired record are read-only mappings from
    this model's perspective.  The caller supplies native callbacks only after
    receiving a ``commit`` plan from a certified binding.
    """

    try:
        initial_balance = _strict_balance(balance)
    except (TypeError, ValueError, OverflowError):
        return RunningPlan(
            "invalid-funds",
            f"No valid tech-point balance was provided.\r\n{NO_DEDUCTION}",
            binding,
        )
    try:
        initial_account_identity = _strict_field(
            account_identity,
            field="tech account identity",
            minimum=RECORD_POINTER_MIN,
            maximum=UINT32_MAX,
        )
    except (TypeError, ValueError, OverflowError):
        return RunningPlan(
            "invalid-account",
            f"No valid tech account identity was provided.\r\n{NO_DEDUCTION}",
            binding,
        )
    initial = scan_running(record, binding)
    planned = _plan_from_scan(initial, binding)
    if planned.status != "candidate":
        return planned
    if initial_balance < binding.price:
        return RunningPlan("insufficient", f"Not enough tech points.\r\n{NO_DEDUCTION}", binding)
    if type(confirmed) is not int:
        return RunningPlan(
            "invalid-confirmation",
            f"The confirmation result was not an exact dialog result.\r\n{NO_DEDUCTION}",
            binding,
        )
    if confirmed in CONFIRM_CANCEL_RESULTS:
        return RunningPlan("cancel", CANCELED_MESSAGE, binding)
    if confirmed != IDOK:
        return RunningPlan(
            "invalid-confirmation",
            f"The confirmation result was not an accepted IDOK.\r\n{NO_DEDUCTION}",
            binding,
        )

    try:
        initial_identity = _record_identity(record, binding)
        reacquired = reacquire()
        if not isinstance(reacquired, tuple) or len(reacquired) != 3:
            raise ValueError("reacquire must return (record, balance, account identity)")
        current_record, current_balance_raw, current_account_raw = reacquired
        current_balance = _strict_balance(current_balance_raw)
        current_account_identity = _strict_field(
            current_account_raw,
            field="tech account identity",
            minimum=RECORD_POINTER_MIN,
            maximum=UINT32_MAX,
        )
        current_identity = _record_identity(current_record, binding)
    except Exception:
        return RunningPlan(
            "reacquire-unknown",
            f"The selected villager could not be revalidated.\r\n{NO_DEDUCTION}",
            binding,
        )
    if current_identity != initial_identity:
        return RunningPlan("race", RACE_MESSAGE, binding)
    if current_account_identity != initial_account_identity:
        return RunningPlan("account-race", RACE_MESSAGE, binding)
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
        record_identity=initial_identity,
        account_identity=initial_account_identity,
    )


def apply_plan(
    plan: RunningPlan,
    write_like: Callable[[int, int], None],
    write_dislike: Callable[[int, int], None],
    read_slots: Callable[[], tuple[Sequence[int], Sequence[int]]],
    deduct: Callable[[int, int], DeductionOutcome],
    reacquire_identity: Callable[[], tuple[int, int, int]],
    read_account: Callable[[], tuple[int, int]],
    restore_slot: Callable[[str, int, int], None] | None = None,
) -> ApplyResult:
    """Apply a committed plan through callbacks with bounded rollback.

    ``DeductionOutcome`` is only an adapter assertion.  Exact selection and
    account callbacks are mandatory at every mutation boundary.  Account-bound
    balance-before/after readback supplies charge verification; an adapter-only
    outcome cannot establish a charge.  Unknown charge state is never converted
    into a no-deduction claim.
    """

    if plan.status != "commit":
        return ApplyResult(plan.status, plan.message)
    if not plan.binding.commit_enabled:
        return ApplyResult("disabled", DISABLED_MESSAGE)
    if plan.record_identity is None or plan.account_identity is None:
        return ApplyResult("invalid-plan", IDENTITY_UNKNOWN_MESSAGE)
    assert plan.like_index is not None
    boundary_status, boundary_balance = _transaction_boundary(
        plan, reacquire_identity, read_account
    )
    if boundary_status is not None:
        return ApplyResult(boundary_status, IDENTITY_UNKNOWN_MESSAGE)
    if boundary_balance is None or boundary_balance < plan.deduction:
        return ApplyResult(
            "charge-preflight-failed",
            f"Not enough tech points.\r\n{NO_DEDUCTION}",
        )
    written: list[tuple[str, int, int]] = []
    try:
        write_like(plan.like_index, plan.binding.running_id)
        written.append(("like", plan.like_index, plan.before_likes[plan.like_index]))
        # A successful Like callback is not proof that the destination is
        # readable in the selected record.  Prove the Like readback while all
        # Dislikes still match the dry-run snapshot before clearing any one.
        likes_after_like = list(plan.before_likes)
        likes_after_like[plan.like_index] = plan.binding.running_id
        boundary_status, _ = _transaction_boundary(plan, reacquire_identity, read_account)
        if boundary_status is not None:
            return _rollback(
                plan, written, read_slots, restore_slot, reacquire_identity,
                read_account, boundary_status,
            )
        likes, dislikes = _read_slot_snapshot(read_slots, plan.binding.slot_count)
        if tuple(likes) != tuple(likes_after_like) or tuple(dislikes) != plan.before_dislikes:
            return _rollback(
                plan, written, read_slots, restore_slot, reacquire_identity,
                read_account, "postverify-failed",
            )
        for index in plan.dislike_indices:
            write_dislike(index, plan.binding.empty_id)
            written.append(("dislike", index, plan.before_dislikes[index]))
    except Exception:
        return _rollback(
            plan, written, read_slots, restore_slot, reacquire_identity,
            read_account, "write-failed",
        )

    try:
        boundary_status, _ = _transaction_boundary(plan, reacquire_identity, read_account)
        if boundary_status is not None:
            return _rollback(
                plan, written, read_slots, restore_slot, reacquire_identity,
                read_account, boundary_status,
            )
        likes, dislikes = _read_slot_snapshot(read_slots, plan.binding.slot_count)
        if tuple(likes) != plan.after_likes or tuple(dislikes) != plan.after_dislikes:
            return _rollback(
                plan, written, read_slots, restore_slot, reacquire_identity,
                read_account, "postverify-failed",
            )
    except Exception:
        return _rollback(
            plan, written, read_slots, restore_slot, reacquire_identity,
            read_account, "postverify-failed",
        )

    boundary_status, balance_before = _transaction_boundary(
        plan, reacquire_identity, read_account
    )
    if boundary_status is not None or balance_before is None:
        return _rollback(
            plan, written, read_slots, restore_slot, reacquire_identity,
            read_account, boundary_status or "charge-preflight-unknown",
        )
    if balance_before < plan.deduction:
        return _rollback(
            plan, written, read_slots, restore_slot, reacquire_identity,
            read_account, "charge-preflight-failed",
        )

    try:
        deduct(plan.account_identity, plan.deduction)
    except Exception:
        charge_status = _readback_charge_status(
            plan.account_identity, balance_before, read_account, plan.deduction
        )
        return _finish_charge(
            plan, written, read_slots, restore_slot, reacquire_identity,
            read_account, charge_status, "deduction-failed",
        )

    # DeductionOutcome is only an adapter assertion.  The balance transition
    # is the sole source of truth for whether a charge actually occurred.
    charge_status = _readback_charge_status(
        plan.account_identity, balance_before, read_account, plan.deduction
    )
    return _finish_charge(
        plan, written, read_slots, restore_slot, reacquire_identity,
        read_account, charge_status, "deduction-failed",
    )


def _transaction_boundary(
    plan: RunningPlan,
    reacquire_identity: Callable[[], tuple[int, int, int]],
    read_account: Callable[[], tuple[int, int]],
) -> tuple[str | None, int | None]:
    try:
        current_identity = _callback_record_identity(
            reacquire_identity(), plan.binding
        )
    except Exception:
        return "identity-unknown", None
    if current_identity != plan.record_identity:
        return "identity-race", None
    try:
        account_identity, balance = _account_snapshot(read_account())
    except Exception:
        return "account-unknown", None
    if account_identity != plan.account_identity:
        return "account-race", None
    return None, balance


def _strict_balance(value: object) -> int:
    if type(value) is not int or not 0 <= value <= UINT32_MAX:
        raise ValueError("native funds/balance must be an exact unsigned DWORD")
    return value


def _readback_charge_status(
    expected_account_identity: int,
    before: int,
    read_account: Callable[[], tuple[int, int]],
    price: int,
) -> str:
    try:
        account_identity, after = _account_snapshot(read_account())
    except Exception:
        return CHARGE_UNKNOWN
    if account_identity != expected_account_identity:
        return CHARGE_UNKNOWN
    if after == before:
        return CHARGE_NOT_CHARGED
    if after == before - price:
        return CHARGE_CHARGED
    return CHARGE_UNKNOWN


def _finish_charge(
    plan: RunningPlan,
    written: list[tuple[str, int, int]],
    read_slots: Callable[[], tuple[Sequence[int], Sequence[int]]],
    restore_slot: Callable[[str, int, int], None] | None,
    reacquire_identity: Callable[[], tuple[int, int, int]],
    read_account: Callable[[], tuple[int, int]],
    charge_status: str,
    reason: str,
) -> ApplyResult:
    if charge_status == CHARGE_CHARGED:
        return ApplyResult(
            "committed",
            SUCCESS_MESSAGE,
            charged=True,
            charge_status=CHARGE_CHARGED,
        )
    if charge_status == CHARGE_NOT_CHARGED:
        return _rollback(
            plan,
            written,
            read_slots,
            restore_slot,
            reacquire_identity,
            read_account,
            reason,
            message=WRITE_FAILURE_MESSAGE,
            charged=False,
            charge_status=CHARGE_NOT_CHARGED,
        )
    return _rollback(
        plan,
        written,
        read_slots,
        restore_slot,
        reacquire_identity,
        read_account,
        "charge-unknown",
        message=CHARGE_UNKNOWN_MESSAGE,
        charged=None,
        charge_status=CHARGE_UNKNOWN,
    )


def _rollback(
    plan: RunningPlan,
    written: list[tuple[str, int, int]],
    read_slots: Callable[[], tuple[Sequence[int], Sequence[int]]],
    restore_slot: Callable[[str, int, int], None] | None,
    reacquire_identity: Callable[[], tuple[int, int, int]],
    read_account: Callable[[], tuple[int, int]],
    reason: str,
    *,
    message: str = WRITE_FAILURE_MESSAGE,
    charged: bool | None = False,
    charge_status: str = CHARGE_NOT_ATTEMPTED,
) -> ApplyResult:
    if restore_slot is None:
        return ApplyResult(
            reason,
            f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
            charged=charged,
            rollback="unavailable",
            charge_status=charge_status,
        )
    try:
        boundary_status, _ = _transaction_boundary(plan, reacquire_identity, read_account)
        if boundary_status is not None:
            return ApplyResult(
                reason,
                f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
                charged=charged,
                rollback="unsafe",
                charge_status=charge_status,
            )
        expected_likes = list(plan.before_likes)
        expected_dislikes = list(plan.before_dislikes)
        for kind, index, _value in written:
            if kind == "like":
                expected_likes[index] = plan.binding.running_id
            else:
                expected_dislikes[index] = plan.binding.empty_id
        likes, dislikes = _read_slot_snapshot(read_slots, plan.binding.slot_count)
        if tuple(likes) != tuple(expected_likes) or tuple(dislikes) != tuple(expected_dislikes):
            return ApplyResult(
                reason,
                f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
                charged=charged,
                rollback="unsafe",
                charge_status=charge_status,
            )
        for kind, index, value in reversed(written):
            boundary_status, _ = _transaction_boundary(
                plan, reacquire_identity, read_account
            )
            if boundary_status is not None:
                return ApplyResult(
                    reason,
                    f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
                    charged=charged,
                    rollback="partial",
                    charge_status=charge_status,
                )
            likes, dislikes = _read_slot_snapshot(read_slots, plan.binding.slot_count)
            if tuple(likes) != tuple(expected_likes) or tuple(dislikes) != tuple(expected_dislikes):
                return ApplyResult(
                    reason,
                    f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
                    charged=charged,
                    rollback="partial",
                    charge_status=charge_status,
                )
            restore_slot(kind, index, value)
            if kind == "like":
                expected_likes[index] = value
            else:
                expected_dislikes[index] = value
        boundary_status, _ = _transaction_boundary(plan, reacquire_identity, read_account)
        if boundary_status is not None:
            return ApplyResult(
                reason,
                f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
                charged=charged,
                rollback="partial",
                charge_status=charge_status,
            )
        final_likes, final_dislikes = _read_slot_snapshot(read_slots, plan.binding.slot_count)
        if tuple(final_likes) != plan.before_likes or tuple(final_dislikes) != plan.before_dislikes:
            return ApplyResult(
                reason,
                f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
                charged=charged,
                rollback="partial",
                charge_status=charge_status,
            )
    except Exception:
        return ApplyResult(
            reason,
            f"{message}\r\n{ROLLBACK_UNVERIFIED_MESSAGE}",
            charged=charged,
            rollback="partial",
            charge_status=charge_status,
        )
    return ApplyResult(
        reason,
        message,
        charged=charged,
        rollback="complete",
        charge_status=charge_status,
    )
