import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_vv1_vv2_fullscreen_candidates.py"
spec = importlib.util.spec_from_file_location("vv1_vv2_fullscreen_builder", SCRIPT)
builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(builder)


class VV1VV2FullscreenCandidateTests(unittest.TestCase):
    def test_oracle_wrappers_are_exactly_228_and_contiguous(self):
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs

        for game, wrappers in builder.WRAPPERS.items():
            for wrapper in wrappers:
                self.assertEqual(len(wrapper), 228)
                ins = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(wrapper, 0x400000))
                self.assertTrue(ins)
                self.assertEqual(sum(i.size for i in ins), len(wrapper))
                self.assertFalse(any(i.mnemonic == "ret" and i.op_str for i in ins))

    def test_deterministic_generation_and_exact_contract(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as tmp:
            first = Path(tmp) / "a"
            second = Path(tmp) / "b"
            builder.emit(first)
            builder.emit(second)
            first_files = sorted(p.relative_to(first) for p in first.rglob("*"))
            second_files = sorted(p.relative_to(second) for p in second.rglob("*"))
            self.assertEqual(first_files, second_files)
            for rel in first_files:
                if (first / rel).is_file():
                    self.assertEqual((first / rel).read_bytes(), (second / rel).read_bytes())

            for game, cfg in builder.ORACLE.items():
                for mode in ("collection_progression", "immediate_fixed"):
                    stem = f"vv{game[-1]}_fullscreen_safe_candidate_{mode}"
                    exe = (first / f"{stem}.exe").read_bytes()
                    page = (first / f"{stem}_page.bin").read_bytes()
                    self.assertEqual(len(page), 0x2000)
                    for off, wrapper in zip(cfg["wrapper_offsets"], builder.WRAPPERS[game]):
                        self.assertEqual(page[off:off + 228], wrapper)
                    for name, (_, _, after) in cfg["hooks"].items():
                        va = cfg["hooks"][name][0]
                        self.assertEqual(exe[va - 0x400000:va - 0x400000 + 5], after)
                    va, _, after = cfg["cure_guard"]
                    self.assertEqual(exe[va - 0x400000:va - 0x400000 + 3], after)
                    self.assertEqual(page[cfg["fm_hook_offset"]:cfg["fm_hook_offset"] + 5], cfg["fm_hook_after"])
                    manifest = __import__("json").loads((first / f"{stem}.json").read_text())
                    self.assertFalse(manifest["enabled"])
                    self.assertTrue(manifest["catalog_hidden"])
                    self.assertTrue(manifest["expanded_rejected"])
                    self.assertTrue(manifest["fullscreen_contract"]["owner_pid_centering"])
                    self.assertEqual(manifest["companion"]["parent_sha256"], builder.ORIGINS_DLL_SHA256)
                    self.assertEqual(manifest["companion"]["restore_sha256"], builder.ORIGINS_DLL_SHA256)
                    self.assertEqual(manifest["wrapper_sha256"], [hashlib.sha256(w).hexdigest().upper() for w in builder.WRAPPERS[game]])
                    self.assertEqual(manifest["cure_guard"]["after"], cfg["cure_guard"][2].hex().upper())
                    self.assertEqual(manifest["hashes"]["output_sha256"], hashlib.sha256(exe).hexdigest().upper())
                    self.assertEqual(manifest["hashes"]["page_sha256"], hashlib.sha256(page).hexdigest().upper())

                    # The final append transaction must carry a valid PE checksum.
                    pe = int.from_bytes(exe[0x3C:0x40], "little")
                    checksum_off = pe + 24 + 64
                    expected = bytearray(exe)
                    expected[checksum_off:checksum_off + 4] = b"\0\0\0\0"
                    total = 0
                    for off in range(0, len(expected), 2):
                        total = (total & 0xFFFF) + (total >> 16) + expected[off] + ((expected[off + 1] if off + 1 < len(expected) else 0) << 8)
                    total = (total & 0xFFFF) + (total >> 16)
                    total = (total & 0xFFFF) + (total >> 16)
                    self.assertEqual(int.from_bytes(exe[checksum_off:checksum_off + 4], "little"), (total + len(exe)) & 0xFFFFFFFF)

    def test_companion_structural_cure_removal_and_detail_parity(self):
        source = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"
        original = source.read_bytes()
        candidate = builder.transform_companion(source)
        self.assertEqual(len(original), len(candidate))
        self.assertEqual(hashlib.sha256(original).hexdigest().upper(), "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9")
        self.assertEqual(hashlib.sha256(candidate).hexdigest().upper(), "846BA4EDF29E52689883A6E20DBF5CB92244DBB52531D7573EDAFF6C9C91543D")
        import pefile
        p = pefile.PE(str(source))
        leaves = {}
        for typ in p.DIRECTORY_ENTRY_RESOURCE.entries:
            if (typ.name.string.decode() if typ.name else typ.struct.Id) != 5:
                continue
            for ent in typ.directory.entries:
                ident = ent.name.string.decode() if ent.name else ent.struct.Id
                if ident in (201, 202):
                    leaf = ent.directory.entries[0].data.struct
                    leaves[ident] = (p.get_offset_from_rva(leaf.OffsetToData), leaf.Size)
        off201, size201 = leaves[201]
        off202, size202 = leaves[202]
        before = original[off201:off201 + size201]
        after = candidate[off201:off201 + size201]
        self.assertEqual(int.from_bytes(after[16:18], "little"), 41)
        self.assertNotIn("Cure all Villagers".encode("utf-16le"), after)
        self.assertEqual(original[off202:off202 + size202], candidate[off202:off202 + size202])

    def test_install_contract_is_candidate_owned_and_atomic(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as tmp:
            root = Path(tmp) / "one"
            builder.emit(root)
            for game in ("vv1", "vv2"):
                contract = __import__("json").loads((root / f"vv{game[-1]}_fullscreen_safe_candidate_contract.json").read_text())
                self.assertFalse(contract["enabled"])
                self.assertTrue(contract["catalog_hidden"])
                self.assertTrue(contract["owner_pid_centering"])
                dll = root / f"VVFP VV{game[-1]} Fullscreen Safe Candidate.dll"
                self.assertTrue(dll.is_file())
                self.assertEqual(dll.stat().st_size, 295936)

    def test_tracked_source_contract_is_disabled_and_fail_closed(self):
        contract = json.loads((ROOT / "data/candidates/vv1_vv2_fullscreen_safe_candidate.json").read_text())
        self.assertFalse(contract["enabled"])
        self.assertTrue(contract["catalog_hidden"])
        self.assertTrue(contract["expanded_rejected"])
        self.assertEqual(contract["companion"]["candidate_sha256"], builder.WINDOWS_CURE_DLL_SHA256)
        self.assertEqual(contract["owner_pid_centering"]["status"], "companion-side contract pending independent emitted/runtime recertification")
        self.assertNotIn("catalog", contract.get("public_choices", {}))


if __name__ == "__main__":
    unittest.main()
