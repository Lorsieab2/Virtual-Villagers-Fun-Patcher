import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_vv3_vv4_fullscreen_candidates.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("vv3_vv4_fullscreen_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VV3VV4FullscreenCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_builder()

    def test_candidates_are_disabled_and_not_public_catalog_entries(self):
        for game in ("vv3", "vv4"):
            stem = f"vv{game[-1]}_fullscreen_safe_candidate"
            manifest = json.loads((ROOT / "data" / "candidates" / f"{stem}.json").read_text())
            mapping = json.loads((ROOT / "data" / "candidates" / f"{stem}_map.json").read_text())
            self.assertFalse(manifest["enabled"])
            self.assertFalse(manifest["catalog_enabled"])
            self.assertTrue(manifest["catalog_hidden"])
            self.assertFalse(mapping["enabled"])
            self.assertTrue(mapping["catalog_hidden"])
            self.assertEqual(manifest["rejected_modes"], [
                "experimental_expanded_256",
                "experimental_expanded_256_progression",
            ])
            from vv_fun_patcher import load_fun_patches
            self.assertNotIn(stem, {patch.id for patch in load_fun_patches()})

    def test_wrappers_are_continuous_plain_return_and_use_native_contract(self):
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32

        md = Cs(CS_ARCH_X86, CS_MODE_32)
        for game, cfg in self.builder.CONFIG.items():
            target = self.builder._target(*cfg["tech"])
            body, meta = self.builder.build_wrapper(cfg, int(cfg["section_va"]) + 0x100,
                                                    int(cfg["section_va"]) + 0xE00, target)
            ins = list(md.disasm(body, int(cfg["section_va"]) + 0x100))
            self.assertEqual(sum(i.size for i in ins), len(body), game)
            self.assertTrue(ins and ins[-1].mnemonic == "ret")
            self.assertTrue(all(not (i.mnemonic == "ret" and i.op_str) for i in ins))
            self.assertEqual(meta["flags_mask"], "0x1001")
            self.assertIn("stdcall with no caller cleanup", meta["api_abi"])
            self.assertIn("identity", meta["failure"] or "")
            # The wrapper has one cdecl SDL call cleanup and no cleanup after
            # either stdcall IAT call.
            text = " ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
            self.assertIn("add esp, 4", text)
            self.assertNotIn("add esp, 8", text)
            self.assertNotIn("add esp, 16", text)
            # Every SDL_GetWindowFlags call receives the window as its cdecl
            # argument. Native leave/enter return values are never treated as
            # success indicators; state/flag reacquisition is authoritative.
            self.assertEqual(sum(i.mnemonic == "push" and i.op_str == "dword ptr [ebp - 0x18]" for i in ins), 2)
            self.assertEqual(sum(i.mnemonic == "add" and i.op_str == "esp, 4" for i in ins), 2)
            for index, insn in enumerate(ins[:-1]):
                if insn.mnemonic == "call" and insn.op_str in {
                    f"0x{self.builder.CONFIG[game]['leave']:x}",
                    f"0x{self.builder.CONFIG[game]['enter']:x}",
                }:
                    self.assertNotEqual(ins[index + 1].mnemonic, "test")

    def test_isolated_generation_is_deterministic_and_pins_parent_outputs(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first)
            second_root = Path(second)
            first_result = {g: self.builder.emit_game(g, cfg, first_root)
                            for g, cfg in self.builder.CONFIG.items()}
            second_result = {g: self.builder.emit_game(g, cfg, second_root)
                             for g, cfg in self.builder.CONFIG.items()}
            first_files = sorted(p.name for p in first_root.iterdir())
            second_files = sorted(p.name for p in second_root.iterdir())
            self.assertEqual(first_files, second_files)
            for name in first_files:
                self.assertEqual((first_root / name).read_bytes(), (second_root / name).read_bytes(), name)
            self.assertEqual(first_result, second_result)
            for game, cfg in self.builder.CONFIG.items():
                for mode, parent in cfg["parents"].items():
                    self.assertEqual(first_result[game]["modes"][mode]["parent_sha256"], parent)
                    self.assertEqual(first_result[game]["modes"][mode]["size"], cfg["parent_size"] + 0x1000)
                    self.assertEqual(len((first_root / f"vv{game[-1]}_fullscreen_safe_candidate.json").read_bytes()) > 0, True)

    def test_hook_and_section_contracts_are_guarded(self):
        for game, cfg in self.builder.CONFIG.items():
            for key in ("tech", "detail"):
                va, before = cfg[key]
                self.assertEqual(len(before), 5)
                self.assertEqual(va - 0x400000, cfg[key][0] - 0x400000)
            self.assertEqual(cfg["section_count_before"], 7 if game == "vv3" else 6)
            self.assertEqual(cfg["image_after"], cfg["image_before"] + 0x1000)
            self.assertEqual(cfg["append_raw"] % 0x1000, 0)
            self.assertEqual(cfg["section_rva"] % 0x1000, 0)
            self.assertEqual(cfg["section_va"] % 0x1000, 0)
            self.assertTrue(cfg["dll"].isalnum() and len(cfg["dll"]) == 64)


if __name__ == "__main__":
    unittest.main()
