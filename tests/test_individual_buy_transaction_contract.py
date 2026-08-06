from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NO_DEDUCTION = "No tech points have been deducted."


def load(name: str) -> dict[str, object]:
    return json.loads((ROOT / "data" / "candidates" / name).read_text(encoding="utf-8"))


class IndividualBuyTransactionContractTests(unittest.TestCase):
    """Fail-closed contract checks for every currently exposed individual route."""

    def test_vv3_individual_running_has_complete_buy_contract(self) -> None:
        raw = load("vv3_individual_grant_running_candidate.json")
        tx = raw["transaction_contract"]
        self.assertEqual(
            {key: tx[key] for key in ("command", "price", "action", "repeatable", "ownership", "remove")},
            {"command": 2, "price": 40000, "action": "Buy", "repeatable": True, "ownership": None, "remove": False},
        )
        self.assertEqual(
            tx["passes"],
            [
                "complete initial three-DWORD Like snapshot/scan",
                "funds >= 40000",
                "OK/Cancel",
                "fresh singleton/index/record",
                "complete second scan and exact snapshot comparison",
                "fresh funds check",
                "verified single first-empty write of 38",
                "one native deduction",
            ],
        )
        messages = raw["result_messages"]
        self.assertEqual(messages["no_charge_suffix"], NO_DEDUCTION)
        self.assertIn(NO_DEDUCTION, messages["invalid_selection_text"])
        self.assertIn("canceled", messages["distinct"])
        self.assertIn("insufficient_funds", messages["distinct"])

    def test_vv5_selected_villager_route_has_complete_buy_contract(self) -> None:
        raw = load("vv5_full_mastery_all_candidate.json")
        tx = raw["transaction_contract"]["individual_transaction"]
        self.assertEqual(tx["price"], 100000)
        self.assertEqual(tx["route_offset"], "0xDB766")
        self.assertTrue(tx["reacquire_same_index"])
        self.assertIn("selected-Believer", raw["description"])
        self.assertIn("No tech points have been deducted.", tx["no_deduction_text"])
        self.assertIn("postverify", tx)
        self.assertIn("before 0x4237B0 deduction", tx["postverify"])

    def test_other_games_do_not_claim_an_unproven_individual_route(self) -> None:
        vv1 = load("vv1_full_mastery_all_candidate.json")
        vv2 = load("vv2_full_mastery_all_candidate.json")
        vv4 = load("vv4_full_heal_cure_all_candidate.json")
        self.assertNotIn("individual_transaction", vv1["transaction_contract"])
        self.assertNotIn("individual_transaction", vv2["transaction_contract"])
        self.assertNotIn("individual_transaction", vv4["transaction"])

    def test_vv5_no_charge_contract_is_not_silent(self) -> None:
        raw = load("vv5_full_mastery_all_candidate.json")
        text = json.dumps(raw)
        self.assertIn(NO_DEDUCTION, text)
        self.assertIn("reacquire_same_index", text)
        self.assertIn("postverify", text.casefold())

    def test_vv5_running_candidate_is_isolated_and_disabled(self) -> None:
        raw = load("vv5_individual_running_candidate.json")
        self.assertFalse(raw["enabled"])
        self.assertTrue(raw["catalog_hidden"])
        self.assertFalse(raw["catalog_enabled"])
        self.assertEqual(raw["unsupported_patch_modes"], ["experimental_expanded_256", "experimental_expanded_256_progression"])
        self.assertEqual(raw["dependencies"], ["vv5_full_mastery_all_stage_a_candidate"])
        tx = raw["transaction_contract"]
        self.assertEqual({k: tx[k] for k in ("command", "price", "action", "repeatable", "ownership", "remove")},
                         {"command": 2, "price": 40000, "action": "Buy", "repeatable": True, "ownership": None, "remove": False})
        self.assertEqual(tx["likes"], ["record+0x1F5C", "record+0x1F60", "record+0x1F64"])
        self.assertIn("first physical -1 Like", tx["dry_run"])
        self.assertEqual(tx["dislike_slots"], ["record+0x1F68", "record+0x1F6C", "record+0x1F70"])
        self.assertEqual(tx["forbidden_reads"], ["movement", "speed"])
        self.assertEqual(tx["accept_result"], 1)
        self.assertIn(NO_DEDUCTION, tx["no_deduction"])
        self.assertEqual(raw["parent_hashes"]["collection_progression"], "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0")
        self.assertEqual(raw["parent_hashes"]["immediate_fixed"], "E93822F752F730ECB751EBAA87021194C992984721B4370FF0015D5FC4BB2E9A")
        self.assertEqual(raw["pe_append_transaction"]["section"], ".vv5run")
        self.assertIsNone(raw["provenance"]["implementation_commit"])

    def test_vv5_running_builder_has_command2_and_all_six_preference_offsets(self) -> None:
        source = (ROOT / "scripts" / "build_vv5_full_mastery_candidate.py").read_text(encoding="utf-8")
        self.assertIn("cmp ebx, 2", source)
        self.assertIn("0x1F5C", source)
        self.assertIn("0x1F60", source)
        self.assertIn("0x1F64", source)
        self.assertIn("push -40000", source)
        self.assertIn("0x1F68", source)
        self.assertIn("0x1F6C", source)
        self.assertIn("0x1F70", source)

    def test_vv5_running_emitted_helper_snapshots_all_likes_and_deducts_once(self) -> None:
        raw = load("vv5_individual_running_candidate_map.json")
        helper = bytes.fromhex(raw["slot"]["running_helper_bytes"])
        self.assertIn(bytes.fromhex("89 44 BD D8"), helper)
        self.assertIn(bytes.fromhex("3B 45 D8"), helper)
        self.assertIn(bytes.fromhex("3B 45 DC"), helper)
        self.assertIn(bytes.fromhex("3B 45 E0"), helper)
        self.assertEqual(helper.count(bytes.fromhex("68 C0 63 FF FF")), 1)
        # The revised helper snapshots and clears all three Dislike slots.
        self.assertIn(b"\x68\x1f", helper)
        self.assertIn(b"\x6c\x1f", helper)
        self.assertIn(b"\x70\x1f", helper)

    def test_vv5_running_stack_intervals_are_disjoint_and_initialized(self) -> None:
        raw = load("vv5_individual_running_candidate_map.json")
        slot = raw["slot"]
        self.assertEqual(slot["running_stack_frame_size"], 0x40)
        self.assertLessEqual(slot["running_helper_length"], 0x800)
        self.assertEqual(slot["running_offset"], 0x1100)
        self.assertEqual(slot["running_confirm_offset"], 0x0E00)
        locals_ = slot["running_stack_locals"]
        saved = slot["running_saved_register_intervals"]
        intervals = list(locals_.items()) + list(saved.items())
        for i, (name, (start, end)) in enumerate(intervals):
            self.assertLessEqual(start, end, name)
            self.assertGreaterEqual(start, -0x40, name)
            self.assertLessEqual(end, -1, name)
            for other, (other_start, other_end) in intervals[i + 1 :]:
                self.assertTrue(end < other_start or other_end < start, f"{name} overlaps {other}")
        snapshots = [locals_[f"likes_snapshot_{i}"] for i in range(3)]
        self.assertEqual(snapshots, [[-0x28, -0x25], [-0x24, -0x21], [-0x20, -0x1D]])
        self.assertEqual([locals_[f"dislikes_snapshot_{i}"] for i in range(3)], [[-0x34, -0x31], [-0x30, -0x2D], [-0x2C, -0x29]])
        self.assertIn("all three Like and all three Dislike", slot["running_snapshot_initialization"])
        helper = bytes.fromhex(slot["running_helper_bytes"])
        self.assertIn(bytes.fromhex("83 EC 40"), helper)
        self.assertIn(bytes.fromhex("89 45 E8"), helper)  # record identity -0x18
        self.assertGreaterEqual(helper.count(bytes.fromhex("89 44 BD D8")), 1)
        self.assertIn(bytes.fromhex("3B 45 E8"), helper)  # identity recheck
        self.assertIn(bytes.fromhex("83 C4 40"), helper)

    def test_vv5_running_production_page_dispatch_and_composed_hook(self) -> None:
        raw = load("vv5_individual_running_candidate.json")
        patch = raw["patches"][0]
        self.assertEqual(patch["offset"], "0xDB766")
        self.assertEqual(patch["before"], "E995750100")
        self.assertEqual(patch["after"], "E9B5880100")
        append = raw["pe_append_transaction"]
        self.assertEqual(append["section"], ".vv5run")
        self.assertEqual(append["append_offset"], "0xF4000")
        self.assertEqual(append["rva"], "0x3CB000")
        self.assertEqual(append["va"], "0x7CB000")
        self.assertEqual(append["dispatcher_va"], "0x7CB020")
        self.assertEqual(append["append_length"], 0x2000)
        self.assertEqual(set(append["layouts"]), {"collection_progression", "immediate_fixed"})
        for layout in append["layouts"].values():
            self.assertEqual(layout["hook_before"], "E995750100")
            self.assertEqual(layout["hook_after"], "E9B5880100")
        emitted = raw["emitted"]
        self.assertEqual(emitted["page_va"], "0x7CB000")
        self.assertEqual(emitted["dispatcher_va"], "0x7CB020")
        disp = bytes.fromhex(emitted["dispatcher_bytes"])
        self.assertGreaterEqual(len(disp), 5)
        targets: list[int] = []
        for i in range(len(disp) - 4):
            if disp[i : i + 2] == b"\x0f\x84":
                rel = struct.unpack_from("<i", disp, i + 2)[0]
                targets.append(0x7CB020 + i + 6 + rel)
            elif disp[i] == 0xE9:
                rel = struct.unpack_from("<i", disp, i + 1)[0]
                targets.append(0x7CB020 + i + 5 + rel)
        self.assertEqual(set(targets), {0x7C9D00, 0x7CC100, 0x7B2790})
        self.assertNotIn("83FB027525", json.dumps(raw))

    def test_vv5_running_emitted_ebp_edi_operands_are_disjoint(self) -> None:
        """Decode the actual helper and calculate each indexed EBP interval."""
        import importlib.util
        sys_path = str(ROOT / "scripts")
        if sys_path not in __import__("sys").path:
            __import__("sys").path.insert(0, sys_path)
        spec = importlib.util.spec_from_file_location("vv5_running_builder", ROOT / "scripts" / "build_vv5_full_mastery_candidate.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        from capstone.x86_const import X86_REG_EBP, X86_REG_EDI
        _, slot_map = module.build_slot(module.RUNNING_PAGE_VA, True, True)
        helper = bytes.fromhex(slot_map["running_helper_bytes"])
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        indexed = []
        for insn in md.disasm(helper, module.RUNNING_PAGE_VA + module.RUNNING_OFFSET):
            for operand in insn.operands:
                if operand.type == 3 and operand.mem.base == X86_REG_EBP and operand.mem.index == X86_REG_EDI:
                    indexed.append(operand.mem.disp)
        self.assertEqual(set(indexed), {-0x34, -0x28})
        self.assertNotIn(bytes.fromhex("89 44 BD E0"), helper)
        self.assertEqual(slot_map["running_stack_locals"]["likes_snapshot_0"], [-0x28, -0x25])
        self.assertEqual(slot_map["running_stack_locals"]["likes_snapshot_1"], [-0x24, -0x21])
        self.assertEqual(slot_map["running_stack_locals"]["likes_snapshot_2"], [-0x20, -0x1D])

    def test_vv5_running_production_render_and_remove_roundtrip(self) -> None:
        from vv_fun_patcher import render_vv5_individual_running_parent, remove_vv5_individual_running_parent
        parent = ROOT / "outputs" / "c265-render" / "collection.exe"
        if not parent.is_file():
            self.skipTest("certified VV5 Collection parent evidence is unavailable")
        original = parent.read_bytes()
        rendered, _ = render_vv5_individual_running_parent(parent, "collection_progression")
        self.assertEqual(len(rendered), 0xF6000)
        self.assertEqual(bytes(rendered[0xDB766:0xDB76B]), bytes.fromhex("E9B5880100"))
        remove_vv5_individual_running_parent(rendered, "collection_progression")
        self.assertEqual(bytes(rendered), original)

    def test_vv5_running_raw_metadata_and_canonical_strings_are_pinned(self) -> None:
        import hashlib
        manifest_path = ROOT / "data" / "candidates" / "vv5_individual_running_candidate.json"
        map_path = ROOT / "data" / "candidates" / "vv5_individual_running_candidate_map.json"
        self.assertEqual(hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper(), "833CF24DCE1B11D6A837AEDD70A94F448B496435ABBFA23992A9EDDB2EA470CA")
        self.assertEqual(hashlib.sha256(map_path.read_bytes()).hexdigest().upper(), "7F349E6BC98036B9954E6020BAE7899C00CFCB46CDE03975EF91C114DA2ECF60")
        raw = json.loads(map_path.read_text(encoding="utf-8"))
        blob = bytes.fromhex(raw["slot"]["running_strings_blob"])
        self.assertEqual(hashlib.sha256(blob).hexdigest().upper(), "0BE4E54A34DA91228F4E333C6DCC8E18FB3BE4292004766B97649A8EE124DCE2")
        self.assertEqual(raw["candidate"]["emitted"]["helper_sha256"], "0F3AE9C5F1998A6BF1FD65962E1565969B9FB08D1A003937B08BABB69E0598AF")
        self.assertEqual(raw["candidate"]["emitted"]["page_sha256"], "8CE3015E5B7E3587C8997A36CA52BD0DE06537B09D76DAD3ED8ABF101352EF6C")
        self.assertEqual(raw["candidate"]["emitted"]["rendered_exe_size"], 0xF6000)
        self.assertEqual(raw["candidate"]["emitted"]["rendered_exe_sha256"], {"collection_progression": "511997D3BA57AA6844D390FFD9BD980A6E36D277BFFD56BFC9A2672CAEFC8125", "immediate_fixed": "390916F2BCE337FA89BC33A69569EDB89B5D361730DF0DB23067B2995F94AFA2"})


if __name__ == "__main__":
    unittest.main()
