"""A patched build must write and find exactly the saves the base game does.

The mask features observe the stock save-path builder so a per-save sidecar can
follow the active slot.  That observation must never change how the game itself
builds a path, names a file, or serializes a save.

scripts/audit_save_path_integrity.py renders the full public patch selection for
every game and every public mode and checks, against the stock executable:

  * the "%s%d.ldw" format string is byte-identical,
  * the builder body is unchanged apart from a declared entry trampoline that
    replays the exact displaced instructions and resumes at the next stock
    instruction, and
  * no capture publishes its argument unguarded, or normalizes an out-of-range
    slot to zero and stores that.

The last check exists because VV1 did exactly that: the same stock builder
formats both the META file (slot 0) and the numbered village saves, so
normalizing 0 and storing it overwrote the live village slot and ran the table
reset, making a running game's masks vanish after any meta write.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_save_path_integrity.py"
sys.path.insert(0, str(ROOT / "src"))


def _load_audit():
    spec = importlib.util.spec_from_file_location("save_path_audit", AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the save-path integrity audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SavePathIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = _load_audit()

    def test_every_game_keeps_the_base_game_save_path_machinery(self) -> None:
        for game_id in self.audit.GAMES:
            stock = self.audit.STOCK_DIR / self.audit.GAMES[game_id]
            if not stock.is_file():
                self.skipTest(f"stock {game_id} executable fixture is unavailable")
        for game_id in self.audit.GAMES:
            with self.subTest(game=game_id):
                problems = self.audit.audit_game(game_id, verbose=False)
                self.assertEqual(problems, [], "\n".join(problems))

    def test_every_save_path_builder_is_declared(self) -> None:
        """A newly hooked builder must be declared, not silently accepted."""
        self.assertEqual(
            set(self.audit.OBSERVED_BUILDERS),
            set(self.audit.GAMES),
            "every game's save-path builder observation must be declared",
        )

    def test_guard_rejects_an_unguarded_or_zeroing_capture(self) -> None:
        """The guard must actually fail on the shapes it exists to reject.

        Both were real: an unguarded store, and VV1's normalize-invalid-to-zero
        form which passed a naive "is there a branch?" check because it did
        branch -- and then stored zero anyway.
        """
        try:
            sys.path.insert(0, str(ROOT / ".tools/keystone"))
            sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
            from keystone import KS_ARCH_X86, KS_MODE_32, Ks
        except ImportError:  # pragma: no cover - environment dependent
            self.skipTest("keystone is unavailable")

        import vv_fun_patcher as patcher

        stock = self.audit.STOCK_DIR / self.audit.GAMES["vv1"]
        if not stock.is_file():
            self.skipTest("stock VV1 executable fixture is unavailable")
        build = next(item for item in patcher.load_builds() if item.id == "vv1")
        selected = [
            p.id
            for p in patcher.load_public_fun_patches()
            if p.raw.get("game_id") == "vv1"
            and "collection_progression"
            in (p.raw.get("supported_modes") or ["collection_progression"])
        ]
        selected = patcher.resolve_fun_patch_ids(selected, game_id="vv1")
        rendered = bytearray(
            patcher.render_patched_bytes(
                stock, build, "collection_progression", selected
            )[0]
        )

        entry, entry_va, cave_offset, cave_va = 0x2ED0, 0x402ED0, 0x8E820, 0x490820
        self.assertIsNone(
            self.audit.capture_is_guarded(bytes(rendered), entry, entry_va),
            "the shipped VV1 capture should be accepted",
        )

        displaced = self.audit.OBSERVED_BUILDERS["vv1"][1]
        self.assertIsNone(
            self.audit.cave_replays_and_resumes(
                bytes(rendered), entry, entry_va, displaced
            ),
            "the shipped VV1 cave should replay and resume correctly",
        )

        assembler = Ks(KS_ARCH_X86, KS_MODE_32)
        replay = "popad\n mov eax, dword ptr [esp + 4]\n mov edx, dword ptr [ecx]"
        rejected = {
            # Every one of these was a real shape, or a real hole in an earlier
            # version of this audit.
            "unguarded store": f"""
                pushad
                mov eax, dword ptr [esp + 0x24]
                mov dword ptr [0x4911f4], eax
                {replay}
                jmp 0x402ed6
            """,
            "normalize invalid to zero, then store (old VV1)": f"""
                pushad
                mov eax, dword ptr [esp + 0x24]
                cmp eax, 5
                jbe high_ok
                xor eax, eax
                jmp publish
            high_ok:
                cmp eax, 1
                jae publish
                xor eax, eax
            publish:
                mov dword ptr [0x4911f4], eax
                {replay}
                jmp 0x402ed6
            """,
            "store a literal 0 on the invalid path (old VV4)": f"""
                pushad
                mov eax, dword ptr [esp + 0x24]
                cmp eax, 1
                jb invalid
                cmp eax, 5
                ja invalid
                mov dword ptr [0x4911f4], eax
                jmp finish
            invalid:
                mov dword ptr [0x4911f4], 0
            finish:
                {replay}
                jmp 0x402ed6
            """,
            "cave never replays the displaced prologue": """
                pushad
                mov eax, dword ptr [esp + 0x24]
                cmp eax, 1
                jb finish
                cmp eax, 5
                ja finish
                mov dword ptr [0x4911f4], eax
            finish:
                popad
                jmp 0x402ed6
            """,
            "cave resumes at the wrong stock instruction": f"""
                pushad
                mov eax, dword ptr [esp + 0x24]
                cmp eax, 1
                jb finish
                cmp eax, 5
                ja finish
                mov dword ptr [0x4911f4], eax
            finish:
                {replay}
                jmp 0x402f00
            """,
        }
        for label, source in rejected.items():
            with self.subTest(shape=label):
                mutated = bytearray(rendered)
                code = bytes(assembler.asm(source, cave_va)[0])
                mutated[cave_offset : cave_offset + len(code)] = code
                mutated[cave_offset + len(code) : cave_offset + 0x100] = b"\x90" * (
                    0x100 - len(code)
                )
                problem = self.audit.capture_is_guarded(
                    bytes(mutated), entry, entry_va
                ) or self.audit.cave_replays_and_resumes(
                    bytes(mutated), entry, entry_va, displaced
                )
                self.assertIsNotNone(problem, f"the audit must reject: {label}")


if __name__ == "__main__":
    unittest.main()
