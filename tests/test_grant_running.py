from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grant_running import (  # noqa: E402
    ALREADY_MESSAGE,
    NO_SLOT_MESSAGE,
    RunningBinding,
    apply_plan,
    binding_from_manifest,
    plan_transaction,
    scan_running,
)


def binding(*, enabled: bool = True) -> RunningBinding:
    return RunningBinding(
        "test",
        "A" * 64,
        0x100,
        (0x10, 0x14, 0x18),
        (0x1C, 0x20, 0x24),
        enabled=enabled,
        preference_write_abi_proven=enabled,
        deduction_abi_proven=enabled,
    )


def record(
    likes,
    dislikes,
    *,
    identity="one",
    active=True,
    health=1,
    faction=0,
    heathen_active=0,
):
    return {
        "identity": identity,
        "active": active,
        "health": health,
        "faction": faction,
        "heathen_active": heathen_active,
        "likes": list(likes),
        "dislikes": list(dislikes),
    }


class ReadProbe(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads = []

    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)


class GrantRunningTests(unittest.TestCase):
    def test_already_running_is_whole_record_noop_and_preserves_duplicates(self):
        current = record((38, 38, 7), (38, 8, 38))
        before = deepcopy(current)
        plan = plan_transaction(current, 40_000, True, lambda: (current, 40_000), binding())
        self.assertEqual((plan.status, plan.message), ("no_change", ALREADY_MESSAGE))
        self.assertEqual(current, before)
        self.assertEqual(scan_running(current, binding()).running_dislikes, (0, 2))

    def test_first_empty_like_is_selected_and_all_running_dislikes_are_planned(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, True, lambda: (current, 40_000), binding())
        self.assertEqual(plan.status, "commit")
        self.assertEqual(plan.like_index, 1)
        self.assertEqual(plan.dislike_indices, (0, 2))
        self.assertEqual(plan.after_likes, (7, 38, 8))
        self.assertEqual(plan.after_dislikes, (-1, 9, -1))
        self.assertEqual(current["likes"], [7, -1, 8])
        self.assertEqual(current["dislikes"], [38, 9, 38])

    def test_no_empty_like_does_not_clear_dislikes(self):
        current = record((7, 8, 9), (38, 38, 6))
        plan = plan_transaction(current, 40_000, True, lambda: (current, 40_000), binding())
        self.assertEqual((plan.status, plan.message), ("no_change", NO_SLOT_MESSAGE))
        self.assertEqual(plan.before_dislikes, (38, 38, 6))
        self.assertEqual(plan.after_dislikes, ())

    def test_cancel_and_reacquire_race_are_no_charge(self):
        current = record((7, -1, 8), (-1, 9, -1))
        self.assertEqual(
            plan_transaction(current, 40_000, False, lambda: (current, 40_000), binding()).status,
            "cancel",
        )
        changed = record((7, 5, 8), (-1, 9, -1), identity="two")
        race = plan_transaction(current, 40_000, True, lambda: (changed, 40_000), binding())
        self.assertEqual(race.status, "race")

    def test_reacquire_rejects_stale_identity_slot_and_funds(self):
        current = record((7, -1, 8), (-1, 9, -1))
        stale_identity = record((7, -1, 8), (-1, 9, -1), identity="two")
        self.assertEqual(
            plan_transaction(current, 40_000, True, lambda: (stale_identity, 40_000), binding()).status,
            "race",
        )
        stale_slot = record((7, 6, 8), (-1, 9, -1))
        self.assertEqual(
            plan_transaction(current, 40_000, True, lambda: (stale_slot, 40_000), binding()).status,
            "race",
        )
        self.assertEqual(
            plan_transaction(current, 40_000, True, lambda: (current, 39_999), binding()).status,
            "insufficient",
        )

    def test_vv5_faction_gate_fails_closed_before_preference_scan(self):
        vv5 = RunningBinding("vv5", "B" * 64, 0x2F44, (1, 2, 3), (4, 5, 6))
        heathen = record((38, -1, 7), (38, 8, -1), faction=1)
        self.assertFalse(scan_running(heathen, vv5).eligible)

    def test_health_and_faction_gates_precede_all_preference_reads(self):
        vv1 = binding()
        vv5 = RunningBinding("vv5", "B" * 64, 0x2F44, (1, 2, 3), (4, 5, 6))
        cases = (
            (vv1, {"active": False, "health": 1, "faction": 0, "heathen_active": 0}),
            (vv1, {"active": True, "health": 0, "faction": 0, "heathen_active": 0}),
            (vv5, {"active": True, "health": 1, "faction": 1, "heathen_active": 0}),
            (vv5, {"active": True, "health": 1, "faction": 0, "heathen_active": 1}),
        )
        for current_binding, gates in cases:
            with self.subTest(game=current_binding.game_id, gates=gates):
                probe = ReadProbe(
                    record((38, -1, 7), (38, 8, -1), **gates)
                )
                self.assertFalse(scan_running(probe, current_binding).eligible)
                self.assertNotIn("likes", probe.reads)
                self.assertNotIn("dislikes", probe.reads)

    def test_exhaustive_first_empty_slot_permutation_for_every_configured_count(self):
        expected_slots = {"vv1": 4, "vv2": 62, "vv3": 3, "vv4": 3, "vv5": 3}
        checked = 0
        for game, slot_count in expected_slots.items():
            path = ROOT / "data" / "candidates" / f"{game}_individual_grant_running_binding.json"
            current_binding = binding_from_manifest(json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(current_binding.slot_count, slot_count)
            for empty_index in range(slot_count):
                with self.subTest(game=game, empty_index=empty_index):
                    likes = [7] * slot_count
                    likes[empty_index] = current_binding.empty_id
                    dislikes = [9] * slot_count
                    dislikes[0] = current_binding.running_id
                    dislikes[-1] = current_binding.running_id
                    current = record(likes, dislikes)
                    plan = plan_transaction(
                        current,
                        current_binding.price,
                        True,
                        lambda current=current: (current, current_binding.price),
                        current_binding,
                    )
                    self.assertEqual(plan.status, "commit")
                    self.assertEqual(plan.like_index, empty_index)
                    self.assertEqual(plan.dislike_indices, (0, slot_count - 1))
                    expected_likes = list(likes)
                    expected_likes[empty_index] = current_binding.running_id
                    expected_dislikes = list(dislikes)
                    expected_dislikes[0] = current_binding.empty_id
                    expected_dislikes[-1] = current_binding.empty_id
                    self.assertEqual(plan.after_likes, tuple(expected_likes))
                    self.assertEqual(plan.after_dislikes, tuple(expected_dislikes))
                    self.assertEqual(current["likes"], likes)
                    self.assertEqual(current["dislikes"], dislikes)
                    checked += 1
        self.assertEqual(checked, sum(expected_slots.values()))

    def test_all_running_dislikes_are_cleared_and_unrelated_duplicates_remain(self):
        current = record((7, -1, 7), (38, 9, 38))
        plan = plan_transaction(current, 40_000, True, lambda: (current, 40_000), binding())
        self.assertEqual(plan.dislike_indices, (0, 2))
        self.assertEqual(plan.after_likes, (7, 38, 7))
        self.assertEqual(plan.after_dislikes, (-1, 9, -1))
        self.assertEqual(plan.after_likes.count(7), 2)
        self.assertEqual(plan.after_dislikes.count(9), 1)

    def test_disabled_binding_never_calls_native_callbacks(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, True, lambda: (current, 40_000), binding(enabled=False))
        calls = []
        result = apply_plan(
            plan,
            lambda *_: calls.append("like"),
            lambda *_: calls.append("dislike"),
            lambda: ((7, -1, 8), (38, 9, 38)),
            lambda *_: calls.append("deduct"),
        )
        self.assertEqual(result.status, "disabled")
        self.assertEqual(calls, [])

    def test_current_game_binding_manifests_normalize_into_the_shared_model(self):
        expected_slots = {"vv1": 4, "vv2": 62, "vv3": 3, "vv4": 3, "vv5": 3}
        for game, slot_count in expected_slots.items():
            with self.subTest(game=game):
                path = ROOT / "data" / "candidates" / f"{game}_individual_grant_running_binding.json"
                raw = json.loads(path.read_text(encoding="utf-8"))
                normalized = binding_from_manifest(raw)
                self.assertEqual(normalized.game_id, game)
                self.assertEqual(normalized.slot_count, slot_count)
                self.assertFalse(normalized.commit_enabled)
                self.assertEqual(raw["status"], "STOP")
                self.assertFalse(raw["enabled"])
                self.assertFalse(raw["catalog_enabled"])
                self.assertTrue(raw["catalog_hidden"])

    def test_postverify_failure_rolls_back_only_when_expected_state_is_still_present(self):
        current = [[7, -1, 8], [38, 9, 38]]
        plan_record = record(*current)
        plan = plan_transaction(plan_record, 40_000, True, lambda: (plan_record, 40_000), binding())
        calls = []
        observed = iter([
            ((7, 38, 8), (38, 9, -1)),
            ((7, 38, 8), (-1, 9, -1)),
            ((7, -1, 8), (38, 9, 38)),
        ])
        result = apply_plan(
            plan,
            lambda kind, value: calls.append(("like", kind, value)),
            lambda kind, value: calls.append(("dislike", kind, value)),
            lambda: next(observed),
            lambda *_: calls.append(("deduct",)),
            lambda kind, index, value: calls.append(("restore", kind, index, value)),
        )
        self.assertEqual(result.rollback, "complete")
        self.assertFalse(result.charged)
        self.assertNotIn(("deduct",), calls)

    def test_each_native_callback_failure_is_uncharged_and_disclosed(self):
        failures = ("like", "dislike-0", "dislike-2", "deduct")
        for failure in failures:
            with self.subTest(failure=failure):
                current = record((7, -1, 8), (38, 9, 38))
                plan = plan_transaction(current, 40_000, True, lambda: (current, 40_000), binding())
                state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
                dislike_calls = 0
                deductions = []

                def write_like(index, value):
                    if failure == "like":
                        raise RuntimeError("like callback failure")
                    state["likes"][index] = value

                def write_dislike(index, value):
                    nonlocal dislike_calls
                    dislike_calls += 1
                    if failure == f"dislike-{index}":
                        raise RuntimeError("dislike callback failure")
                    state["dislikes"][index] = value

                def read_slots():
                    return tuple(state["likes"]), tuple(state["dislikes"])

                def deduct(value):
                    if failure == "deduct":
                        raise RuntimeError("deduction callback failure")
                    deductions.append(value)

                def restore_slot(kind, index, value):
                    state["likes" if kind == "like" else "dislikes"][index] = value

                result = apply_plan(
                    plan,
                    write_like,
                    write_dislike,
                    read_slots,
                    deduct,
                    restore_slot,
                )
                expected_status = "deduction-failed" if failure == "deduct" else "write-failed"
                self.assertEqual(result.status, expected_status)
                self.assertFalse(result.charged)
                self.assertIn("No tech points have been deducted.", result.message)
                self.assertEqual(result.rollback, "complete" if failure == "deduct" else "unsafe")
                self.assertEqual(deductions, [])
                self.assertEqual(dislike_calls, 0 if failure == "like" else (1 if failure == "dislike-0" else 2))

    def test_rollback_failure_is_reported_as_partial_and_uncharged(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, True, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}

        def write_like(index, value):
            state["likes"][index] = value

        def write_dislike(index, value):
            state["dislikes"][index] = value

        def deduct(_value):
            raise RuntimeError("deduction callback failure")

        def restore_slot(_kind, _index, _value):
            raise RuntimeError("rollback callback failure")

        result = apply_plan(
            plan,
            write_like,
            write_dislike,
            lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
            deduct,
            restore_slot,
        )
        self.assertEqual(result.status, "deduction-failed")
        self.assertEqual(result.rollback, "partial")
        self.assertFalse(result.charged)
        self.assertIn("No tech points have been deducted.", result.message)


if __name__ == "__main__":
    unittest.main()
