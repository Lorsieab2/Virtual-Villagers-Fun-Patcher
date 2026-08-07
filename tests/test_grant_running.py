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


def record(likes, dislikes, *, identity="one", faction=0, heathen_active=0):
    return {
        "identity": identity,
        "active": True,
        "health": 1,
        "faction": faction,
        "heathen_active": heathen_active,
        "likes": list(likes),
        "dislikes": list(dislikes),
    }


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

    def test_vv5_faction_gate_fails_closed_before_preference_scan(self):
        vv5 = RunningBinding("vv5", "B" * 64, 0x2F44, (1, 2, 3), (4, 5, 6))
        heathen = record((38, -1, 7), (38, 8, -1), faction=1)
        self.assertFalse(scan_running(heathen, vv5).eligible)

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


if __name__ == "__main__":
    unittest.main()
