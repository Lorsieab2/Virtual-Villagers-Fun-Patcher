"""Fail-closed VV5 selected-villager transaction reference model.

The model mirrors the disabled native candidate's transaction boundary.  It is
deliberately save-free and reference-only: callers provide an immutable
villager snapshot and get back a new reference state only after the complete
dry-run, confirmation, re-acquire, funds recheck, mutation, postverification,
and single-charge arithmetic sequence succeeds.  This module performs no
native write, native readback, or rollback and must not be treated as runtime
evidence for any of those operations.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Callable, Literal


IDOK = 1
CANCEL_RESULTS = (0, 2)
RUNNING_PREFERENCE = 38
EMPTY_PREFERENCE = -1
NO_DEDUCTION = "No tech points have been deducted."
UNKNOWN_CHARGE = "The tech-point charge outcome is unknown; no no-charge claim is permitted without exact balance readback."

Action = Literal["youth", "full_mastery", "running", "age_18"]
Status = Literal[
    "committed",
    "invalid_selection",
    "invalid_skill",
    "no_change",
    "no_empty_like",
    "insufficient_funds",
    "cancelled",
    "recheck_failed",
    "funds_recheck_failed",
    "callback_failed",
    "postverify_failed",
    "charge_failed",
]


@dataclass(frozen=True)
class VV5Villager:
    """The native fields read or written by the four individual actions."""

    index: int
    identity: str
    active: bool
    health: int
    faction: int
    age: int
    record_pointer: str
    age_companion: int = 0
    age_timer: int = 0
    skills: tuple[float, ...] = (100.0, 100.0, 100.0, 100.0, 100.0, 100.0)
    likes: tuple[int, ...] = (EMPTY_PREFERENCE, EMPTY_PREFERENCE, EMPTY_PREFERENCE)
    dislikes: tuple[int, ...] = (EMPTY_PREFERENCE, EMPTY_PREFERENCE, EMPTY_PREFERENCE)

    def __post_init__(self) -> None:
        """Reject lossy/coercible reference states at the model boundary."""

        exact_ints = {
            "index": self.index,
            "health": self.health,
            "faction": self.faction,
            "age": self.age,
            "age_companion": self.age_companion,
            "age_timer": self.age_timer,
        }
        for field, value in exact_ints.items():
            if type(value) is not int:
                raise TypeError(f"{field} must be an exact int")
        for field, value in {"active": self.active}.items():
            if type(value) is not bool:
                raise TypeError(f"{field} must be an exact bool")
        for field, value in {"identity": self.identity, "record_pointer": self.record_pointer}.items():
            if type(value) is not str or not value:
                raise TypeError(f"{field} must be a non-empty identity string")
        if type(self.skills) is not tuple or len(self.skills) != 6:
            raise TypeError("skills must be an exact six-item tuple")
        if any(type(value) is not float for value in self.skills):
            raise TypeError("skills must contain exact Float32-like floats")
        if any(not math.isfinite(value) for value in self.skills):
            raise ValueError("skills must contain finite values")
        for field, values in {"likes": self.likes, "dislikes": self.dislikes}.items():
            if type(values) is not tuple or len(values) != 3:
                raise TypeError(f"{field} must be an exact three-item tuple")
            if any(type(value) is not int for value in values):
                raise TypeError(f"{field} must contain exact ints")


@dataclass(frozen=True)
class DryRun:
    action: Action
    valid: bool
    changed: bool
    reason: str
    snapshot: tuple[object, ...]
    changed_skill_indices: tuple[int, ...] = ()
    first_empty_like: int | None = None
    has_running_like: bool = False
    running_dislike_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class TransactionResult:
    action: Action
    status: Status
    villager: VV5Villager
    funds: int
    charged: bool
    charge_verified: bool
    message: str
    dry_run: DryRun
    native_write_performed: bool = False
    native_readback_verified: bool = False
    rollback_performed: bool = False
    effects_may_have_occurred: bool = False
    funds_known: bool = True
    charge_truth: Literal["not_attempted", "verified", "unknown"] = "not_attempted"


_PRICES: dict[Action, int] = {
    "youth": 50_000,
    "full_mastery": 100_000,
    "running": 40_000,
    "age_18": 50_000,
}


def transaction_contracts() -> dict[Action, dict[str, object]]:
    """Return the static contract consumed by the disabled candidate manifest."""

    common = {
        "sequence": [
            "complete dry-run",
            "explicit IDOK/Cancel confirmation",
            "reacquire same selected index and exact record pointer",
            "recheck exact pre-confirmation snapshot and eligibility",
            "reacquire and require exact pre-confirmation funds before any write",
            "reference-model mutation only; native writer remains separately disabled",
            "reference postverify only; native readback remains separately disabled",
            "verify one reference charge outcome and exact funds delta",
        ],
        "confirmation_results": {"idok": IDOK, "cancel": list(CANCEL_RESULTS)},
        "record_reacquire": "same selected index and exact record pointer",
        "pre_confirmation_snapshot": "exact snapshot equality before any native write",
        "funds_reacquire": "post-confirmation funds must equal the pre-confirmation amount immediately before any write",
        "required_callbacks": ["before_reacquire", "before_funds_reacquire"],
        "before_reacquire": "mandatory callable returning the same-index, same-record-pointer snapshot",
        "before_funds_reacquire": "mandatory callable returning the exact post-confirmation funds snapshot",
        "callback_exception_policy": "callback exception or malformed callback return yields structured possible-effects disclosure and unknown charge; no no-charge claim is made without exact balance readback",
        "charge_verification": "reference charge outcome is verified and final funds equal original funds minus exact action price",
        "native_effects": "reference-only; no native write, native readback, or rollback is implemented or implied",
        "no_charge_suffix": NO_DEDUCTION,
        "unknown_charge_text": UNKNOWN_CHARGE,
        "no_charge_results": [
            "invalid_selection",
            "invalid_skill",
            "no_change",
            "no_empty_like",
            "insufficient_funds",
            "cancelled",
            "recheck_failed",
            "funds_recheck_failed",
            "postverify_failed",
        ],
    }
    return {
        "youth": {
            **common,
            "price": _PRICES["youth"],
            "dry_run": "snapshot displayed age and both native age companions; no write",
            "postverify": "displayed age is exactly max(raw age - 700, 100) and age, companion, and nonzero timer deltas match the reference transition",
        },
        "full_mastery": {
            **common,
            "price": _PRICES["full_mastery"],
            "dry_run": "validate all six finite Float32 skills in [0,100] and count below-100 fields",
            "postverify": "all six native skills are exactly 100.0",
        },
        "running": {
            **common,
            "price": _PRICES["running"],
            "dry_run": "snapshot all three Likes and all three Dislikes; preserve duplicates; choose first physical -1 Like",
            "postverify": "Running is present in the planned Like slot and every Running Dislike is -1",
            "native_preference_abi": "stock 3+3 preference ABI only: membership 0x464F90; insertion 0x464AD0 uses the first -1 Like; repeated removal 0x4649E0 clears each Running Dislike; an existing Running Like skips the entire record without confirmation, cleanup, or charge",
        },
        "age_18": {
            **common,
            "price": _PRICES["age_18"],
            "dry_run": "snapshot raw age and both native age companions; no write",
            "postverify": "raw age is exactly 360 and age, companion, and nonzero timer deltas match the reference transition",
        },
    }


def _snapshot(villager: VV5Villager) -> tuple[object, ...]:
    return (
        villager.index,
        villager.identity,
        villager.record_pointer,
        villager.active,
        villager.health,
        villager.faction,
        villager.age,
        villager.age_companion,
        villager.age_timer,
        villager.skills,
        villager.likes,
        villager.dislikes,
    )


def _eligible(villager: VV5Villager) -> bool:
    return (
        0 <= villager.index < 150
        and villager.active
        and villager.health > 0
        and villager.faction == 0
    )


def dry_run(villager: VV5Villager, action: Action) -> DryRun:
    """Read and validate one selected villager without changing any field."""

    if type(villager) is not VV5Villager:
        raise TypeError("villager must be a VV5Villager")
    if type(action) is not str or action not in _PRICES:
        raise ValueError(f"unknown VV5 individual action: {action}")
    snapshot = _snapshot(villager)
    if not _eligible(villager):
        return DryRun(action, False, False, "invalid_selection", snapshot)

    if action == "full_mastery":
        if len(villager.skills) != 6 or any(
            not math.isfinite(value) or not 0.0 <= value <= 100.0
            for value in villager.skills
        ):
            return DryRun(action, False, False, "invalid_skill", snapshot)
        changed = tuple(
            index for index, value in enumerate(villager.skills) if value < 100.0
        )
        return DryRun(action, True, bool(changed), "changed" if changed else "no_change", snapshot, changed_skill_indices=changed)

    if action == "running":
        if len(villager.likes) != 3 or len(villager.dislikes) != 3:
            return DryRun(action, False, False, "invalid_selection", snapshot)
        has_like = RUNNING_PREFERENCE in villager.likes
        first_empty = next(
            (index for index, value in enumerate(villager.likes) if value == EMPTY_PREFERENCE),
            None,
        )
        running_dislikes = tuple(
            index for index, value in enumerate(villager.dislikes) if value == RUNNING_PREFERENCE
        )
        if has_like:
            return DryRun(
                action, True, False, "no_change", snapshot,
                first_empty_like=first_empty,
                has_running_like=True,
                running_dislike_indices=running_dislikes,
            )
        if not has_like and first_empty is None:
            return DryRun(
                action, True, False, "no_empty_like", snapshot,
                first_empty_like=None,
                has_running_like=False,
                running_dislike_indices=running_dislikes,
            )
        return DryRun(
            action, True, True, "changed", snapshot,
            first_empty_like=first_empty,
            has_running_like=False,
            running_dislike_indices=running_dislikes,
        )

    if action == "youth":
        changed = villager.age != _youth_target(villager.age)
        return DryRun(action, True, changed, "changed" if changed else "no_change", snapshot)

    if action == "age_18":
        changed = villager.age != 360
        return DryRun(action, True, changed, "changed" if changed else "no_change", snapshot)

def _youth_target(raw_age: int) -> int:
    return max(raw_age - 700, 100)


def _apply_youth(villager: VV5Villager) -> VV5Villager:
    target = _youth_target(villager.age)
    delta = target - villager.age
    companion = villager.age_companion + delta
    timer = villager.age_timer + delta if villager.age_timer != 0 else villager.age_timer
    return replace(villager, age=target, age_companion=companion, age_timer=timer)


def _apply_age_target(villager: VV5Villager, target: int) -> VV5Villager:
    delta = target - villager.age
    companion = villager.age_companion + delta
    timer = villager.age_timer + delta if villager.age_timer != 0 else villager.age_timer
    return replace(villager, age=target, age_companion=companion, age_timer=timer)


def _mutate(villager: VV5Villager, plan: DryRun) -> VV5Villager:
    if plan.action == "youth":
        return _apply_youth(villager)
    if plan.action == "age_18":
        return _apply_age_target(villager, 360)
    if plan.action == "full_mastery":
        skills = list(villager.skills)
        for index in plan.changed_skill_indices:
            skills[index] = 100.0
        return replace(villager, skills=tuple(skills))
    if plan.action == "running":
        likes = list(villager.likes)
        if not plan.has_running_like:
            assert plan.first_empty_like is not None
            likes[plan.first_empty_like] = RUNNING_PREFERENCE
        dislikes = tuple(
            EMPTY_PREFERENCE if value == RUNNING_PREFERENCE else value
            for value in villager.dislikes
        )
        return replace(villager, likes=tuple(likes), dislikes=dislikes)
    raise ValueError(f"unknown VV5 individual action: {plan.action}")


def _postverify(before: VV5Villager, after: VV5Villager, plan: DryRun) -> bool:
    if not _eligible(after):
        return False
    # Reference-only exactness guard: no unrelated field may change. A native
    # readback/rollback implementation is deliberately outside this module.
    if after != _mutate(before, plan):
        return False
    if plan.action == "youth":
        target = _youth_target(before.age)
        expected_delta = target - before.age
        expected_timer = before.age_timer + expected_delta if before.age_timer != 0 else before.age_timer
        return (
            after.age == target
            and after.age_companion - before.age_companion == expected_delta
            and after.age_timer == expected_timer
        )
    if plan.action == "age_18":
        expected_delta = 360 - before.age
        expected_timer = before.age_timer + expected_delta if before.age_timer != 0 else before.age_timer
        return (
            after.age == 360
            and after.age_companion - before.age_companion == expected_delta
            and after.age_timer == expected_timer
        )
    if plan.action == "full_mastery":
        return len(after.skills) == 6 and all(value == 100.0 for value in after.skills)
    if plan.action == "running":
        return (
            RUNNING_PREFERENCE in after.likes
            and all(value != RUNNING_PREFERENCE for value in after.dislikes)
        )
    return False


def _verify_reference_charge(before_funds: int, after_funds: int, price: int) -> bool:
    """Verify arithmetic only; this is not a native charge/readback."""

    return (
        type(before_funds) is int
        and type(after_funds) is int
        and type(price) is int
        and before_funds >= price
        and before_funds - after_funds == price
        and after_funds == before_funds - price
    )


def execute(
    villager: VV5Villager,
    funds: int,
    action: Action,
    confirm_result: int,
    *,
    before_reacquire: Callable[[VV5Villager], VV5Villager],
    before_funds_reacquire: Callable[[int], int],
    force_postverify_failure: bool = False,
    force_charge_failure: bool = False,
) -> TransactionResult:
    """Run the complete transaction boundary without mutating the input."""

    if type(villager) is not VV5Villager:
        raise TypeError("villager must be a VV5Villager")
    if type(funds) is not int:
        raise TypeError("funds must be an exact int")
    if type(confirm_result) is not int:
        raise TypeError("confirm_result must be an exact int")
    if confirm_result != IDOK and confirm_result not in CANCEL_RESULTS:
        raise ValueError("confirm_result must be exact IDOK or Cancel/close")
    if not callable(before_reacquire):
        raise TypeError("before_reacquire is mandatory and must be callable")
    if not callable(before_funds_reacquire):
        raise TypeError("before_funds_reacquire is mandatory and must be callable")
    if type(force_postverify_failure) is not bool or type(force_charge_failure) is not bool:
        raise TypeError("force flags must be exact bools")

    plan = dry_run(villager, action)
    price = _PRICES[action]

    def result(
        status: Status,
        state: VV5Villager,
        message: str,
        available_funds: int = funds,
        *,
        effects_may_have_occurred: bool = False,
        funds_known: bool = True,
        charge_truth: Literal["not_attempted", "verified", "unknown"] = "not_attempted",
    ) -> TransactionResult:
        return TransactionResult(
            action, status, state, available_funds, False, False, message, plan,
            effects_may_have_occurred=effects_may_have_occurred,
            funds_known=funds_known,
            charge_truth=charge_truth,
        )

    if plan.reason == "invalid_skill":
        return result("invalid_skill", villager, f"The selected villager has an invalid skill.\r\n{NO_DEDUCTION}")
    if not plan.valid:
        return result("invalid_selection", villager, f"No valid living villager is selected.\r\n{NO_DEDUCTION}")
    if plan.reason == "no_empty_like":
        return result("no_empty_like", villager, f"This villager has no empty Like slot.\r\n{NO_DEDUCTION}")
    if not plan.changed:
        return result("no_change", villager, f"No change is required.\r\n{NO_DEDUCTION}")
    if funds < price:
        return result("insufficient_funds", villager, f"Not enough tech points.\r\n{NO_DEDUCTION}")
    if confirm_result != IDOK:
        return result("cancelled", villager, f"The upgrade was canceled.\r\n{NO_DEDUCTION}")

    try:
        reacquired = before_reacquire(villager)
    except Exception:
        return result(
            "callback_failed",
            villager,
            f"The pre-mutation record callback failed. Callback effects may have occurred; rollback is not claimed. {UNKNOWN_CHARGE}",
            effects_may_have_occurred=True,
            funds_known=False,
            charge_truth="unknown",
        )
    if type(reacquired) is not VV5Villager:
        return result(
            "callback_failed",
            villager,
            f"The pre-mutation record callback returned an invalid snapshot. Callback effects may have occurred; rollback is not claimed. {UNKNOWN_CHARGE}",
            effects_may_have_occurred=True,
            funds_known=False,
            charge_truth="unknown",
        )
    if reacquired.index != villager.index or reacquired.record_pointer != villager.record_pointer:
        return result("recheck_failed", reacquired, f"The selected villager changed during confirmation.\r\n{NO_DEDUCTION}")
    if _snapshot(reacquired) != plan.snapshot:
        return result("recheck_failed", reacquired, f"The selected villager changed during confirmation.\r\n{NO_DEDUCTION}")
    second_plan = dry_run(reacquired, action)
    if not second_plan.valid or not second_plan.changed:
        return result("recheck_failed", reacquired, f"The selected villager changed during confirmation.\r\n{NO_DEDUCTION}")

    try:
        confirmed_funds = before_funds_reacquire(funds)
    except Exception:
        return result(
            "callback_failed",
            reacquired,
            f"The pre-mutation funds callback failed. Callback effects may have occurred; rollback is not claimed. {UNKNOWN_CHARGE}",
            effects_may_have_occurred=True,
            funds_known=False,
            charge_truth="unknown",
        )
    if type(confirmed_funds) is not int:
        return result(
            "callback_failed",
            reacquired,
            f"The pre-mutation funds callback returned an invalid snapshot. Callback effects may have occurred; rollback is not claimed. {UNKNOWN_CHARGE}",
            effects_may_have_occurred=True,
            funds_known=False,
            charge_truth="unknown",
        )
    if confirmed_funds != funds or confirmed_funds < price:
        return result(
            "funds_recheck_failed",
            reacquired,
            f"Tech points changed during confirmation.\r\n{NO_DEDUCTION}",
            confirmed_funds,
        )

    mutated = _mutate(reacquired, second_plan)
    if force_postverify_failure or not _postverify(reacquired, mutated, second_plan):
        return result(
            "postverify_failed",
            mutated,
            "The upgrade could not be verified after mutation. Earlier effects may remain.\r\n"
            f"{NO_DEDUCTION}",
            effects_may_have_occurred=True,
        )

    if force_charge_failure:
        return result(
            "charge_failed",
            mutated,
            UNKNOWN_CHARGE,
            effects_may_have_occurred=True,
            funds_known=False,
            charge_truth="unknown",
        )

    # Reference arithmetic only: native charge/write/readback/rollback are not performed here.
    charged_funds = confirmed_funds - price
    if not _verify_reference_charge(confirmed_funds, charged_funds, price):
        return result(
            "charge_failed",
            mutated,
            UNKNOWN_CHARGE,
            effects_may_have_occurred=True,
            funds_known=False,
            charge_truth="unknown",
        )
    return TransactionResult(
        action,
        "committed",
        mutated,
        charged_funds,
        True,
        True,
        "Upgrade committed.",
        plan,
        charge_truth="verified",
    )
