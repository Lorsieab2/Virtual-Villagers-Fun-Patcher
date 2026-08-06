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
        self.assertNotIn(bytes.fromhex("89 44 BD E0"), helper)
        self.assertIn(bytes.fromhex("3B 45 E0"), helper)
        self.assertEqual(helper.count(bytes.fromhex("68 C0 63 FF FF")), 1)
        # The revised helper snapshots and clears all three Dislike slots.
        self.assertIn(b"\x68\x1f", helper)
        self.assertIn(b"\x6c\x1f", helper)
        self.assertIn(b"\x70\x1f", helper)

    def test_vv5_running_stack_intervals_are_disjoint_and_initialized(self) -> None:
        raw = load("vv5_individual_running_candidate_map.json")
        slot = raw["slot"]
        self.assertEqual(slot["running_stack_frame_size"], 0x48)
        self.assertLessEqual(slot["running_helper_length"], 0x800)
        self.assertEqual(slot["running_offset"], 0x1620)
        self.assertEqual(slot["running_confirm_offset"], 0x15D4)
        locals_ = slot["running_stack_locals"]
        saved = slot["running_saved_register_intervals"]
        intervals = list(locals_.items()) + list(saved.items())
        for i, (name, (start, end)) in enumerate(intervals):
            self.assertLessEqual(start, end, name)
            self.assertGreaterEqual(start, -0x48, name)
            self.assertLessEqual(end, -1, name)
            for other, (other_start, other_end) in intervals[i + 1 :]:
                self.assertTrue(end < other_start or other_end < start, f"{name} overlaps {other}")
        snapshots = [locals_[f"likes_snapshot_{i}"] for i in range(3)]
        self.assertEqual(snapshots, [[-0x28, -0x25], [-0x24, -0x21], [-0x20, -0x1D]])
        self.assertEqual([locals_[f"dislikes_snapshot_{i}"] for i in range(3)], [[-0x34, -0x31], [-0x30, -0x2D], [-0x2C, -0x29]])
        self.assertIn("all three Like and all three Dislike", slot["running_snapshot_initialization"])
        helper = bytes.fromhex(slot["running_helper_bytes"])
        self.assertIn(bytes.fromhex("83 EC 48"), helper)
        self.assertIn(bytes.fromhex("89 45 E8"), helper)  # record identity -0x18
        self.assertIn(bytes.fromhex("83 4D BC 01"), helper)  # mutation ownership mask
        self.assertIn(bytes.fromhex("3B 45 E8"), helper)  # identity recheck
        self.assertIn(bytes.fromhex("83 C4 48"), helper)

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
        self.assertEqual(set(targets), {0x7C9D00, 0x7CC620, 0x7B2790})
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
        self.assertEqual(hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper(), "BBBCCF15DF3858ADD6BDF74E2E112FB20EC769FFDC77AD3985650AB30E2FB0F8")
        self.assertEqual(hashlib.sha256(map_path.read_bytes()).hexdigest().upper(), "23117F33D46961A2B228A3E0B61B0EBF77705EA3B2B9C4E3147D710ED3942404")
        raw = json.loads(map_path.read_text(encoding="utf-8"))
        blob = bytes.fromhex(raw["slot"]["running_strings_blob"])
        self.assertEqual(hashlib.sha256(blob).hexdigest().upper(), "0BE4E54A34DA91228F4E333C6DCC8E18FB3BE4292004766B97649A8EE124DCE2")
        self.assertEqual(raw["candidate"]["emitted"]["helper_sha256"], "B241577470F7FDA4E9B7B646A489C266F93B84638CC6BACA5D843C7CED423375")
        self.assertEqual(raw["candidate"]["emitted"]["page_sha256"], "7C6576FD669261BD0C1D688280EAD8653C6B22FDA4BE92151387FE2A4E35B28C")
        self.assertEqual(raw["candidate"]["emitted"]["rendered_exe_size"], 0xF6000)
        self.assertEqual(raw["candidate"]["emitted"]["rendered_exe_sha256"], {"collection_progression": "CEE399896343055CB35AEC345A863F50E7CFF4989F71669912BC588E2F3D8B8C", "immediate_fixed": None})

    def test_vv5_running_page_ownership_excludes_full_mastery_and_stale_output(self) -> None:
        raw = load("vv5_individual_running_candidate_map.json")
        slot = raw["slot"]
        helper_start = slot["running_offset"]
        helper_end = helper_start + slot["running_helper_length"]
        confirm_start = slot["running_confirm_offset"]
        confirm_end = confirm_start + len(bytes.fromhex(slot["running_confirm_bytes"]))
        strings_start = slot["running_strings_offset"]
        strings_end = strings_start + len(bytes.fromhex(slot["running_strings_blob"]))
        intervals = [(0x100, 0x1100), (0x1200, 0x15D3), (confirm_start, confirm_end), (helper_start, helper_end), (strings_start, strings_end)]
        for i, (start, end) in enumerate(intervals):
            self.assertLessEqual(start, end)
            self.assertLessEqual(end, 0x2000)
            for other_start, other_end in intervals[i + 1 :]:
                self.assertTrue(end <= other_start or other_end <= start)
        self.assertNotIn("511997D3BA57AA6844D390FFD9BD980A6E36D277BFFD56BFC9A2672CAEFC8125", json.dumps(raw))


if __name__ == "__main__":
    unittest.main()
