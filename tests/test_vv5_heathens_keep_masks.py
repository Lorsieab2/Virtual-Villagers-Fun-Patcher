"""New Believers' "Heathens Keep Their Masks When Converted" (the owner, 2026-11-08: "when a heathen converts their
mask stays on their head (as if the player manually set it using Change Appearance)", "Oh and the player can always
Change Appearance to change it or take it off if they want to.").

EMULATED, on the executable the patcher renders for the row (with the Origins base it needs), in each of the three
public modes, and with 256 Villagers (Experimental):

* "VVFP Heathens Keep Masks.dll" is started as VVFP Startup.dll starts it (VvfpStartup(5, ...));
* the game's own conversion 0x4668B0 runs on a Heathen record (its sound, sparkle, message and trophy calls stood
  in for; the faction setter 0x466880 writes the faction byte), and The Defector's answer 0x416970 runs its direct
  setter call 0x41699F;
* the Origins companion is a stand-in whose VvfpMaskKeep puts the mask in the mask table as the real one does
  (the real one, its file and the locked-file wait, are run by native/vv5_task9_origins/vv5_mask_identity_harness.c,
  tests/test_vv5_mask_identity_harness.py), and the Original Look companion a stand-in that records what it is told
  (its rule is run by native/vvfp_original_look/original_look_harness.c, tests/test_original_look.py).

Then the mask the Heathen wore -- blue, orange, red, purple (the Heathen Doctor and the three Masters) or the
Chief's -- is the villager's nibble in the mask table, read back by the Task9 page's own mask_get (the routine the
render and Change Appearance read), and Original Look is told it (so Reset to original gives it back).  The page's
own mask_set (what Change Appearance's OK and Reset to original write through) changes it or takes it off
afterwards, and nothing puts it back.  With the companion not started, without the Origins companion (or one with
no VvfpMaskKeep), or when the store refuses, nothing is kept and the convert loses the mask as in the stock game.
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ROW = "vv5_heathens_keep_masks_when_converted"
DLL = ROOT / "assets" / "heathens_keep_masks" / "VVFP Heathens Keep Masks.dll"
FEATURE = ROOT / "data" / "vv5_heathens_keep_masks_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

STRIDE, ACTIVE, FACTION, ORANGE, RED, ROLE, FAITH = 0x2F44, 0x1CD4, 0x1CEC, 0x1CED, 0x1CEE, 0x1CFC, 0x1CF0
STOCK_RECORDS, STOCK_TABLE = 0x554148 + 0x48, 0x7B1D20
BIG_RECORDS, BIG_TABLE = 0x800000 + 0x48, 0x7F1400
ORIGINS_BASE = 0x0B000000
LOOKS_BASE = 0x0B100000
CAUSE_BASE = 0x0B200000
CONVERT, DEFECTOR = 0x4668B0, 0x416970

# What the conversion 0x4668B0 calls, each popping its own arguments (thiscall/stdcall): sound 0x44C440, the
# villager's spot 0x466350 (answers a point: the pointer it is given), the sparkle 0x476D00, the scene 0x470810,
# the say-event 0x465580, the message 0x44EF60, the music 0x44E730, the trophies 0x413450, the tutorial 0x43AE80
# (answered 1: the hint is skipped), the activity clear 0x473440.
CONVERSION_CALLS = {0x44C440: 4, 0x466350: 4, 0x476D00: 20, 0x470810: 12, 0x465580: 8, 0x44EF60: 8,
                    0x44E730: 12, 0x413450: 8, 0x43AE80: 4, 0x473440: 0}

# The mask each Heathen kind wears (0x4728C6) and the nibble Change Appearance keeps for it.
KINDS = {
    "blue": (0, 0, 0, 1),
    "orange": (0, 1, 0, 2),
    "red": (0, 0, 1, 3),
    "purple (Heathen Doctor)": (12, 0, 0, 4),
    "purple (Heathen Master)": (14, 0, 0, 4),
    "purple (Heathen Master Farmer)": (16, 0, 0, 4),
    "the Chief's": (13, 0, 0, 5),
}


def _t9():
    spec = importlib.util.spec_from_file_location("vv5_task9_native_actions",
                                                  ROOT / "scripts" / "build_vv5_task9_native_actions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T9 = _t9()
PAGE_VA = 0x7C9000
MASK_GET = PAGE_VA + T9.OFF["mask_get"]
MASK_SET = PAGE_VA + T9.OFF["mask_set"]


class Village(Machine):
    """The rendered game, the companion, and a stand-in Origins companion."""

    def __init__(self, exe: bytes, *, big: bool = False, origins: bool = True, keep_export: bool = True,
                 keep_answer: int = 1, looks: bool = True):
        super().__init__(exe, DLL)
        self.records = BIG_RECORDS if big else STOCK_RECORDS
        self.table = BIG_TABLE if big else STOCK_TABLE
        self.origins = origins
        self.looks = looks
        self.keep_answer = keep_answer           # 1 kept now, 2 waiting for the load, 0 refused
        self.keeps: list[tuple[int, int]] = []
        self.told: list[tuple[int, int, int]] = []
        self.faction_calls: list[tuple[int, int, int]] = []
        stubs = self.alloc(0x100)
        self.exports_of_origins = {"WriteMaskSidecar": stubs + 0x10, "VvfpMaskOf": stubs + 0x20}
        if keep_export:
            self.exports_of_origins["VvfpMaskKeep"] = stubs
        self.exports_of_looks = {"VvfpOriginalLookConverted": stubs + 0x30}
        # The Cause of Death companion's Former Heathens file, as VvfpCauseFormerKind answers it: record -> kind.
        self.former: dict[int, int] | None = None
        self.exports_of_cause = {"VvfpCauseFormerKind": stubs + 0x40}
        self.stub(stubs, self._keep)
        self.stub(stubs + 0x10, lambda p: (0, 4))
        self.stub(stubs + 0x20, self._mask_of)
        self.stub(stubs + 0x30, self._converted)
        self.stub(stubs + 0x40, lambda p: (self.former.get(p.arg(0), 0xFFFFFFFF), 4))
        self.api_handlers["GetModuleHandleA"] = self._module
        self.api_handlers["GetProcAddress"] = self._proc
        for va, pop in CONVERSION_CALLS.items():
            self.stub(va, self._game_call(va, pop))
        self.stub(0x466880, self._faction_setter)

    # ---- the stand-in Origins companion ---------------------------------------------------------------------
    def _module(self, p):
        name = p.cstring(p.arg(0))
        if self.origins and name == "VVFP Origins Icons.dll":
            return ORIGINS_BASE, 4
        if self.former is not None and name == "VVFP Cause of Death.dll":
            return CAUSE_BASE, 4
        return (LOOKS_BASE if self.looks and name == "VVFP Original Look.dll" else 0), 4

    def _proc(self, p):
        exports = {ORIGINS_BASE: self.exports_of_origins, LOOKS_BASE: self.exports_of_looks,
                   CAUSE_BASE: self.exports_of_cause}.get(p.arg(0), {})
        return exports.get(p.cstring(p.arg(1)), 0), 8

    def _keep(self, p):
        """VvfpMaskKeep(record, mask): the nibble, as the real store sets it (vv5_keep_nibble)."""
        record, mask = p.arg(0), p.arg(1)
        self.keeps.append((record, mask))
        if self.keep_answer:
            index = (record - self.records) // STRIDE
            at = self.table + (index >> 1)
            byte = p.read(at, 1)[0]
            byte = ((byte & 0x0F) | (mask << 4)) if index & 1 else ((byte & 0xF0) | mask)
            p.write(at, bytes([byte]))
        return self.keep_answer, 8

    def _mask_of(self, p):
        """VvfpMaskOf(record): the nibble, as the real store answers it (vv5_story_mask_get)."""
        index = (p.arg(0) - self.records) // STRIDE
        byte = p.read(self.table + (index >> 1), 1)[0]
        return ((byte >> 4) if index & 1 else byte) & 0x0F, 4

    def _converted(self, p):
        self.told.append((p.arg(0), p.arg(1), p.arg(2)))
        return 1, 12

    # ---- the game ---------------------------------------------------------------------------------------
    def _game_call(self, va: int, pop: int):
        def call(p):
            if va == 0x466350:
                return p.arg(0), pop                 # the spot: a point the caller reads
            if va == 0x43AE80:
                return 1, pop                        # the tutorial hint is not shown
            return 0, pop
        return call

    def _faction_setter(self, p):
        record, value = p.reg("ecx"), p.arg(0) & 0xFF
        self.faction_calls.append((record, value, p.u32(p.reg("esp"))))
        p.write(record + FACTION, bytes([value]))
        return 0, 4

    def record(self, index: int) -> int:
        return self.records + index * STRIDE

    def heathen(self, index: int, role: int, orange: int, red: int) -> int:
        record = self.record(index)
        self.write(record, bytes(STRIDE))
        self.write(record + ACTIVE, b"\x01")
        self.write(record + 0x1B9C, f"Heathen{index}".encode() + b"\0")
        self.write(record + FACTION, b"\x01")
        self.write(record + ORANGE, bytes([orange]))
        self.write(record + RED, bytes([red]))
        self.put32(record + ROLE, role)
        return record

    def convert(self, record: int) -> None:
        self.call(CONVERT, [], ecx=record)

    def defector(self, record: int) -> None:
        """The Defector's "welcome" (0x416970 with answer 0): SetFaith(+20), which leaves the Faith at or below 0
        here (no conversion), then the faction setter with 0 at 0x41699F."""
        event = self.alloc(0x20)
        self.put32(event + 4, record)
        self.stub(0x470920, lambda p: (0, 4))
        self.stub(0x467F90, lambda p: (0, 8))
        self.call(DEFECTOR, [0], ecx=event)

    def mask_get(self, record: int) -> int:
        """The Task9 page's mask_get: what the render's mask flip and Change Appearance read."""
        return self.call(MASK_GET, regs={"esi": record})

    def mask_set(self, record: int, mask: int) -> None:
        """The Task9 page's mask_set: what Change Appearance's OK (and Reset to original) writes."""
        self.call(MASK_SET, regs={"esi": record, "ebx": mask})


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(5).is_file():
        return "stock executable not present (inputs/)"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


class TheRow(unittest.TestCase):
    def test_the_row_is_new_believers_and_needs_the_origins_base(self):
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        self.assertEqual(row["id"], ROW)
        self.assertEqual(row["name"], "Heathens Keep Their Masks When Converted")
        self.assertEqual(row["game_id"], "vv5")
        self.assertEqual(row["dependencies"], ["vv5_enable_origins_exclusive_features"])
        # The companion remembers every convert's mask itself (the owner, 2026-11-22): no other row is needed.
        self.assertNotIn("Log Every Death", row["description"])
        self.assertIn("its own Masks Worn file", row["description"])
        self.assertEqual(row["patches"], [])
        from origins_base_text import ORIGINS_BASE_SENTENCE
        self.assertTrue(row["description"].startswith(ORIGINS_BASE_SENTENCE), "the dependency comes first, in bold")
        owner = '"Heathen" masks are culturally important to them. Their choices must be honored.'
        self.assertTrue(row["description"].startswith(ORIGINS_BASE_SENTENCE + " " + owner + " When a Heathen"),
                      "the owner's sentence opens the description, right after the bold dependency")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertIn(owner, [line for e in guide["patches"] if ROW in e.get("ids", []) for line in e["guide"]])
        ids = {p.id for p in patcher.load_public_fun_patches()}
        self.assertIn(ROW, ids)
        self.assertEqual([c["destination"] for c in row["companion_files"]], ["VVFP Heathens Keep Masks.dll"])
        self.assertIn("VVFP Heathens Keep Masks.dll", patcher.STARTUP_LOADER_COMPANIONS_2)

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        how_to = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        self.assertIn('"assets/heathens_keep_masks/VVFP Heathens Keep Masks.dll"', release)
        self.assertIn('"data/vv5_heathens_keep_masks_feature.json"', release)
        self.assertIn(f"- Patch ID: `{ROW}`", readme)
        self.assertIn(row["description"], readme)
        self.assertIn("HEATHENS KEEP THEIR MASKS WHEN CONVERTED (NEW BELIEVERS)", how_to)
        entry = [e for e in guide["patches"] if ROW in e.get("ids", [])]
        self.assertEqual(len(entry), 1)
        lines = entry[0]["guide"]
        self.assertLessEqual(len(lines), 8)
        self.assertLessEqual(max(len(line) for line in lines), 180)
        self.assertLessEqual(sum(len(line) for line in lines), 900)
        self.assertIn(f"#### Heathens Keep Their Masks When Converted (`{ROW}`)", log)
        # The committed log is LF (scripts/generate_transparency_docs.py); a Windows checkout may hand it over
        # as CRLF (core.autocrlf), so the blob is what is checked.
        import subprocess
        blob = subprocess.run(["git", "show", "HEAD:docs/transparency-log.md"], cwd=ROOT, capture_output=True)
        if blob.returncode == 0:
            self.assertNotIn(b"\r", blob.stdout)

    def test_the_dll_exports_imports_and_shows_no_text(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpHeathensKeepMasksFaction", "VvfpHeathensKeepMasksInstalled",
                                 "VvfpHeathensKeepMasksKept", "VvfpHeathensKeepMasksLook",
                                 "VvfpHeathensKeepMasksReturned", "VvfpHeathensKeepMasksVillageReset", "VvfpStartup",
                                 "VvfpVillagerSexChanged",
                                 "VvfpVillagersRenamed"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA",
                                    "OutputDebugStringW", "MessageBoxA", "MessageBoxW",
                                    "DeleteFileW", "MoveFileW", "RegSetValueExW", "Sleep", "CreateThread"}, set())
        for section in pe.sections:
            self.assertFalse(section.Characteristics & 0x20000000 and section.Characteristics & 0x80000000)
        source = (ROOT / "native" / "vvfp_heathens_keep_masks" / "vvfp_heathens_keep_masks.c").read_text(
            encoding="utf-8")
        # The mask a villager going back wore: the Cause of Death companion's Former Heathens file, by its export.
        cause = pefile.PE(str(ROOT / "assets" / "cause_of_death" / "VVFP Cause of Death.dll"))
        self.assertIn(b"VvfpCauseFormerKind", {e.name for e in cause.DIRECTORY_ENTRY_EXPORT.symbols})
        self.assertIn('"VvfpCauseFormerKind"', source)
        self.assertNotIn("vvfp_tr", source)          # no text of its own: nothing to translate
        self.assertNotIn("OutputDebugString", source)


@unittest.skipIf(_skip(), _skip() or "")
class KeptMasks(unittest.TestCase):
    maxDiff = None

    def village(self, mode="collection_progression", *, big=False, start=True, **kw) -> Village:
        rows = [ROW] + (["vv5_population_256"] if big else [])
        v = Village(render(5, with_requirements(5, rows), mode), big=big, **kw)
        if start:
            v.export("VvfpStartup", 5, 0)
            self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 1)
        return v

    def test_every_mask_kind_is_kept_in_every_mode(self):
        for mode in MODES:
            for kind, (role, orange, red, mask) in KINDS.items():
                with self.subTest(mode=mode, kind=kind):
                    v = self.village(mode)
                    record = v.heathen(7, role, orange, red)
                    self.assertEqual(v.mask_get(record), 0, "no Change Appearance mask before")
                    v.convert(record)
                    self.assertEqual(v.read(record + FACTION, 1), b"\0", "the game's conversion still converts")
                    self.assertEqual(v.u32(record + ROLE), 13 if role == 13 else 0,
                                     "every role but the Chief's is cleared, as in the stock game")
                    self.assertEqual(v.mask_get(record), mask, "the mask they wore is their mask now")
                    self.assertEqual(v.keeps, [(record, mask)], "handed to the store once")
                    self.assertEqual(v.told, [(5, record, mask)], "Original Look is told: Reset gives it back")
                    self.assertEqual(v.export("VvfpHeathensKeepMasksKept"), 1)

    def test_with_256_villagers_the_table_of_that_build(self):
        for index in (0, 149, 150, 255):
            with self.subTest(record=index):
                v = self.village(big=True)
                record = v.heathen(index, 0, 0, 1)
                v.convert(record)
                self.assertEqual(v.mask_get(record), 3)
                self.assertEqual(v.read(STOCK_TABLE, 0x80), bytes(0x80), "the stock build's table is not used")

    def test_neighbours_keep_their_masks(self):
        """A nibble shares its byte with the record beside it: that one's mask is untouched."""
        v = self.village()
        left, right = v.record(4), v.heathen(5, 0, 1, 0)
        v.write(left, bytes(STRIDE))
        v.write(left + ACTIVE, b"\x01")
        v.mask_set(left, 4)
        v.convert(right)
        self.assertEqual((v.mask_get(left), v.mask_get(right)), (4, 2))

    def test_change_appearance_can_change_it_or_take_it_off_later(self):
        v = self.village()
        record = v.heathen(3, 0, 0, 1)
        v.convert(record)
        self.assertEqual(v.mask_get(record), 3)
        v.mask_set(record, 1)                         # Change Appearance: Blue
        self.assertEqual(v.mask_get(record), 1)
        v.mask_set(record, 0)                         # Change Appearance: No Mask (and Reset to original: none)
        self.assertEqual(v.mask_get(record), 0)
        v.convert(record)                             # a believer reaching the conversion again: nothing is kept
        self.assertEqual(v.mask_get(record), 0, "a believer's own choice is never put back")
        self.assertEqual(len(v.keeps), 1)

    def test_a_heathen_who_comes_back_takes_the_mask_of_this_conversion(self):
        """A believer with a Change Appearance mask who became a Heathen and joins again wears, and keeps, the
        Heathen mask the game draws now."""
        v = self.village()
        record = v.heathen(2, 0, 1, 0)
        v.mask_set(record, 5)
        v.convert(record)
        self.assertEqual(v.mask_get(record), 2)

    def test_the_defector_direct_setter_keeps_it_too(self):
        v = self.village()
        record = v.heathen(9, 14, 0, 0)
        v.defector(record)
        self.assertEqual(v.read(record + FACTION, 1), b"\0")
        self.assertEqual(v.faction_calls[-1][2], 0x4169A4, "the setter sees the stock return address")
        self.assertEqual(v.mask_get(record), 4)
        self.assertEqual(v.keeps, [(record, 4)])

    def test_the_defector_after_a_conversion_keeps_nothing_twice(self):
        v = self.village()
        record = v.heathen(9, 0, 0, 0)
        v.convert(record)                             # SetFaith(+20) converted already
        v.defector(record)
        self.assertEqual(v.mask_get(record), 1)
        self.assertEqual(len(v.keeps), 1)

    def test_the_patch_off_keeps_nothing(self):
        """Without the row the companion is not shipped, so VVFP Startup.dll never starts it: the stock loss."""
        v = Village(render(5, with_requirements(5, ["vv5_enable_origins_exclusive_features"]), "collection_progression"))
        record = v.heathen(7, 0, 1, 0)
        v.convert(record)
        self.assertEqual(v.mask_get(record), 0)
        self.assertEqual(v.keeps, [])
        shipping = {p.id for p in patcher.load_fun_patches()
                    if any(c.get("destination") == "VVFP Heathens Keep Masks.dll" for c in p.raw.get("companion_files", []))}
        self.assertEqual(shipping, {ROW}, "only this row ships the companion")

    def test_without_the_origins_companion_nothing_is_kept(self):
        v = self.village(origins=False)
        record = v.heathen(7, 0, 1, 0)
        v.convert(record)
        self.assertEqual(v.read(record + FACTION, 1), b"\0", "the conversion goes on")
        self.assertEqual(v.keeps, [])
        self.assertEqual(v.told, [])
        self.assertEqual(v.export("VvfpHeathensKeepMasksKept"), 0)

    def test_an_origins_companion_without_the_keep_export_keeps_nothing(self):
        v = self.village(keep_export=False)
        record = v.heathen(7, 0, 1, 0)
        v.convert(record)
        self.assertEqual((v.mask_get(record), v.keeps, v.told), (0, [], []))

    def test_a_refused_keep_tells_original_look_nothing(self):
        v = self.village(keep_answer=0)
        record = v.heathen(7, 0, 1, 0)
        v.convert(record)
        self.assertEqual(v.keeps, [(record, 2)])
        self.assertEqual((v.mask_get(record), v.told, v.export("VvfpHeathensKeepMasksKept")), (0, [], 0))

    def test_a_mask_waiting_for_the_load_is_still_part_of_the_original(self):
        """VvfpMaskKeep answering 2 (the slot's file not loaded yet: it waits, then is put on them)."""
        v = self.village(keep_answer=2)
        record = v.heathen(7, 13, 0, 0)
        v.convert(record)
        self.assertEqual(v.keeps, [(record, 5)])
        self.assertEqual(v.told, [(5, record, 5)])

    def test_without_original_look_the_mask_is_still_kept(self):
        v = self.village(looks=False)
        record = v.heathen(7, 0, 0, 1)
        v.convert(record)
        self.assertEqual((v.mask_get(record), v.told), (3, []))

    def test_the_install_is_refused_on_other_bytes(self):
        exe = bytearray(render(5, with_requirements(5, [ROW]), "collection_progression"))
        pe_offset = 0x41699F - 0x400000            # .text: file offset = VA - 0x400000
        exe[pe_offset] = 0x90
        v = Village(bytes(exe))
        v.export("VvfpStartup", 5, 0)
        self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 0)
        self.assertEqual(v.read(0x466966, 7), bytes.fromhex("83BEFC1C00000D"), "neither site is written")

    def test_another_game_installs_nothing(self):
        v = self.village(start=False)
        for game in (1, 2, 3, 4):
            v.export("VvfpStartup", game, 0)
        self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 0)


# ---- Going back to the Heathens (the owner, 2026-11-22) ---------------------------------------------------------
# "a villager who goes back to the Heathens gets back exactly the mask they wore as a Heathen before -- blue, orange,
# red, purple, or the Chief's mask -- whatever it was; behaviour is always an ordinary blue Heathen (listens,
# convertible; never the puzzle role again: not a Master, not the Chief)."
TO_HEATHEN = 0x4669E0                    # SetFaith's to-a-Heathen routine (the drift, events, CIE, Story)
SPA_TAIL, CRACKED_TAIL = 0x415CFE, 0x416C4A   # The Spa's / The Cracked Mask's "go Heathen" answers
DROP_TEST, DROP_LISTEN = 0x443D4D, 0x443D65   # the drop handler's mask test and its listening path
HEAD_TEST, HEAD_DRAW = 0x472732, 0x472769     # the render's head kind tests and the call they feed (edx)
MASK_PICK, MASK_DRAW = 0x4728C6, 0x472919     # the render's mask pick (role, then kind bytes) and its art row (ebx)
SLOT_BLUE, SLOT_ORANGE, SLOT_RED = 0xB10E, 0x0A4A, 0x4ED0   # stand-in sprite handles at [esp+0x30/0x4C/0x54]
ROW_BLUE, ROW_ORANGE, ROW_RED, ROW_PURPLE, ROW_CHIEF = 0, 1, 2, 3, 4   # the art rows 0x4728C6..0x472919 pick
K_BLUE, K_ORANGE, K_RED, K_PURPLE, K_CHIEF = 0, 1, 2, 3, 4                         # former_heathens.h VV_FORMER_*


class GoingBack(Village):
    """The village with the game's own ways a believer goes back to the Heathens and the render's own mask pick."""

    def __init__(self, exe: bytes, **kw):
        super().__init__(exe, **kw)
        self.stub(0x467F90, lambda p: (0, 8))   # SetFaith(-10): the Faith left above 0 here (the direct setter)
        self.former = {}                        # the Cause of Death companion is loaded; its file is filled per test

    def believer(self, index: int, role: int, orange: int, red: int, *, filed: bool = True) -> int:
        """A villager converted from a Heathen of this role and kind bytes (the bytes the stock conversion leaves),
        filed in the Former Heathens file as the Cause of Death companion files them (the mask drawn)."""
        record = self.heathen(index, role, orange, red)
        wore = K_CHIEF if role == 13 else K_PURPLE if role in (12, 14, 15, 16) else K_ORANGE if orange else K_RED if red \
            else K_BLUE
        self.convert(record)
        if filed:
            self.former[record] = wore
        return record

    def go_back(self, record: int, way: str) -> None:
        if way == "Faith at 0 (0x4669E0)":
            self.call(TO_HEATHEN, ecx=record)
            return
        event = self.alloc(0x20)
        self.put32(event + 4, record)
        from story_emulator import RETURN
        # Mid-answer: the tail's `pop esi; ret 4` lands on RETURN.
        self.call(SPA_TAIL if way == "The Spa" else CRACKED_TAIL, [RETURN, 0], regs={"esi": event})

    def head_slot(self, record: int) -> int:
        """The sprite the render's head draw is handed for this Heathen (0x472732..0x472769: edx)."""
        from story_emulator import STACK_TOP
        esp = STACK_TOP - 0x1000 - 4
        for offset, slot in ((0x30, SLOT_BLUE), (0x4C, SLOT_ORANGE), (0x54, SLOT_RED)):
            self.put32(esp + offset, slot)
        self.call(HEAD_TEST, regs={"esi": record}, until=HEAD_DRAW, limit=5_000_000)
        return self.reg("edx")

    def mask_row(self, record: int) -> int:
        """The mask art row the render picks (0x4728C6..0x472919: ebx)."""
        self.call(MASK_PICK, regs={"esi": record, "ebx": 0x77}, until=MASK_DRAW, limit=5_000_000)
        return self.reg("ebx")

    def listens(self, record: int) -> bool:
        """The drop handler's mask test: on to the listening path (a blue Heathen's), or turned away."""
        try:
            self.call(DROP_TEST, regs={"esi": record, "ebx": 0}, until=DROP_LISTEN, limit=20)
        except Exception:
            return False
        return True


WAYS = ("Faith at 0 (0x4669E0)", "The Spa", "The Cracked Mask")
# Heathen (role, orange, red) -> (Origins mask, head sprite, mask art row)
WORN = {
    "blue": ((0, 0, 0), 1, SLOT_BLUE, ROW_BLUE),
    "orange": ((0, 1, 0), 2, SLOT_ORANGE, ROW_ORANGE),
    "red": ((0, 0, 1), 3, SLOT_RED, ROW_RED),
    "purple (a Master)": ((14, 0, 0), 4, SLOT_BLUE, ROW_PURPLE),
    "purple (the Heathen Doctor)": ((12, 0, 0), 4, SLOT_BLUE, ROW_PURPLE),
    "the Chief's (the Retired Chief)": ((13, 0, 0), 5, SLOT_BLUE, ROW_CHIEF),
    "the Heathen Mommy's (orange)": ((17, 1, 0), 2, SLOT_ORANGE, ROW_ORANGE),
}


@unittest.skipIf(_skip(), _skip() or "")
class GoingBackToTheHeathens(unittest.TestCase):
    maxDiff = None

    def village(self, mode="collection_progression", *, big=False, start=True, **kw) -> GoingBack:
        rows = [ROW] + (["vv5_population_256"] if big else [])
        v = GoingBack(render(5, with_requirements(5, rows), mode), big=big, **kw)
        if start:
            v.export("VvfpStartup", 5, 0)
            self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 1)
        return v

    def test_the_stock_game_gets_the_mask_or_the_behaviour_wrong(self):
        """Without the companion: an orange convert goes back an orange Heathen in behaviour too (a drop on them does
        nothing), a purple one is drawn blue, and the Retired Chief through The Spa's own call is the Heathen Chief
        again -- what the owner's request changes."""
        v = GoingBack(render(5, with_requirements(5, [ROW]), "collection_progression"))
        orange = v.believer(3, 0, 1, 0)
        v.go_back(orange, WAYS[0])
        self.assertEqual(v.read(orange + ORANGE, 2), b"\x01\x00")
        self.assertFalse(v.listens(orange))
        master = v.believer(4, 14, 0, 0)
        v.go_back(master, WAYS[0])
        self.assertEqual(v.mask_row(master), ROW_BLUE)
        chief = v.believer(5, 13, 0, 0)
        v.go_back(chief, "The Spa")
        self.assertEqual(v.u32(chief + ROLE), 13, "the Heathen Chief's puzzle role again")

    def test_they_wear_their_own_mask_and_behave_as_an_ordinary_blue_heathen(self):
        for mode in MODES:
            for way in WAYS:
                for worn, ((role, orange, red), mask, slot, row) in WORN.items():
                    with self.subTest(mode=mode, way=way, worn=worn):
                        v = self.village(mode)
                        record = v.believer(7, role, orange, red)
                        self.assertEqual(v.mask_get(record), mask, "kept as a believer (as before)")
                        v.go_back(record, way)
                        self.assertEqual(v.read(record + FACTION, 1), b"\x01", "a Heathen again")
                        self.assertEqual(v.read(record + ORANGE, 2), b"\0\0", "both kind bytes 0")
                        self.assertEqual(v.u32(record + ROLE), 0, "never a puzzle role again")
                        self.assertEqual(v.faction_calls[-1][2],
                                         {WAYS[0]: 0x466A04, "The Spa": 0x415D11, "The Cracked Mask": 0x416C60}[way],
                                         "the setter sees its stock return address")
                        self.assertEqual(v.mask_get(record), mask, "their own mask is kept by the villager")
                        self.assertEqual(v.head_slot(record), slot, "the head is drawn as in their own mask")
                        self.assertEqual(v.mask_row(record), row, "their own mask is drawn")
                        self.assertTrue(v.listens(record), "a believer dropped on them preaches, as on a blue one")
                        self.assertEqual(v.export("VvfpHeathensKeepMasksLook", record),
                                         0xFFFFFFFF if mask == 1 else mask - 1)
                        self.assertEqual(v.export("VvfpHeathensKeepMasksReturned"), 1)

    def test_with_256_villagers(self):
        for index in (0, 149, 150, 255):
            with self.subTest(record=index):
                v = self.village(big=True)
                record = v.believer(index, 14, 0, 0)
                v.go_back(record, WAYS[0])
                self.assertEqual((v.mask_get(record), v.mask_row(record), v.u32(record + ROLE)), (4, ROW_PURPLE, 0))

    def test_joining_again_keeps_their_mask_and_going_back_again_too(self):
        for worn, ((role, orange, red), mask, _slot, row) in WORN.items():
            with self.subTest(worn=worn):
                v = self.village()
                record = v.believer(4, role, orange, red)
                for round_trip in range(3):
                    v.go_back(record, WAYS[round_trip % 3])
                    self.assertEqual((v.read(record + ORANGE, 2), v.u32(record + ROLE), v.mask_row(record)),
                                     (b"\0\0", 0, row))
                    v.convert(record)
                    self.assertEqual(v.read(record + FACTION, 1), b"\0")
                    self.assertEqual(v.mask_get(record), mask, "their own mask is kept, not the blue the bytes say")
                    self.assertEqual(v.keeps[-1], (record, mask))
                    self.assertEqual(v.told[-1], (5, record, mask), "Original Look is told their mask")
                    self.assertEqual(v.read(record + ORANGE, 2), bytes([orange, red]),
                                     "an orange or red kind byte is back, as the stock conversion leaves it")

    def test_a_companion_calling_the_setter_itself_tells_the_companion_first(self):
        """The Custom Island Event's "Becomes a Heathen" / "Becomes a believer" call the setter 0x466880 directly
        when their SetFaith did not convert (story_graph.inc cg_keep_masks_faction): VvfpHeathensKeepMasksFaction
        first does what the splices do at the game's own calls."""
        for worn, ((role, orange, red), mask, _slot, row) in WORN.items():
            with self.subTest(worn=worn):
                v = self.village()
                record = v.believer(4, role, orange, red)
                self.assertEqual(v.export("VvfpHeathensKeepMasksFaction", record, 1), 1)
                v.call(0x466880, [1], ecx=record)                  # the Story DLL's own setter call
                self.assertEqual((v.read(record + ORANGE, 2), v.u32(record + ROLE)), (b"\0\0", 0))
                self.assertEqual((v.mask_get(record), v.mask_row(record)), (mask, row))
                self.assertTrue(v.listens(record))
                self.assertEqual(v.export("VvfpHeathensKeepMasksFaction", record, 0), 1)
                v.call(0x466880, [0], ecx=record)
                self.assertEqual((v.read(record + FACTION, 1), v.mask_get(record)), (b"\0", mask),
                                 "joining again the same way keeps their mask")
        v = self.village(start=False)
        record = v.believer(4, 0, 1, 0)
        self.assertEqual(v.export("VvfpHeathensKeepMasksFaction", record, 1), 0, "not installed: nothing")
        self.assertEqual(v.read(record + ORANGE, 1), b"\x01")

    def test_a_camp_job_later_keeps_their_mask(self):
        """The Heathens' own jobs are roles 1-11 (the owner's saves hold them): a Heathen who went back and is
        later given one is still drawn in their own mask."""
        for role in (1, 6, 11):
            with self.subTest(role=role):
                v = self.village()
                record = v.believer(4, 14, 0, 0)
                v.go_back(record, WAYS[0])
                v.put32(record + ROLE, role)
                self.assertEqual(v.mask_row(record), ROW_PURPLE)
                self.assertEqual(v.export("VvfpHeathensKeepMasksLook", record), K_PURPLE)

    def test_a_mask_changed_as_a_believer_does_not_change_the_one_they_wore(self):
        v = self.village()
        record = v.believer(4, 0, 0, 1)
        v.mask_set(record, 2)                       # Change Appearance: Orange, as a believer
        v.go_back(record, WAYS[0])
        self.assertEqual((v.mask_get(record), v.mask_row(record)), (3, ROW_RED), "red, the mask they wore")

    def test_the_former_heathens_file_is_what_they_wore(self):
        """The Former Heathens file says what was drawn at their conversion; the kind bytes say only orange or red."""
        v = self.village()
        record = v.believer(4, 0, 1, 0)
        v.former[record] = K_RED                      # e.g. Story / Cheat Upgrades set their kind after it was filed
        v.go_back(record, WAYS[0])
        self.assertEqual((v.mask_get(record), v.mask_row(record)), (3, ROW_RED))

    def test_without_the_file_the_bytes_and_the_retired_chief_still_tell(self):
        for (role, orange, red), mask in (((0, 1, 0), 2), ((0, 0, 1), 3), ((13, 0, 0), 5)):
            with self.subTest(role=role, orange=orange, red=red):
                v = self.village()
                record = v.believer(4, role, orange, red, filed=False)
                v.go_back(record, WAYS[0])
                self.assertEqual((v.mask_get(record), v.u32(record + ROLE)), (mask, 0))

    def test_not_known_to_have_worn_a_mask_goes_back_blue(self):
        """No Former Heathens entry and nothing in the record (born a believer, or a Master converted before
        anything recorded it), with an orange, red, purple or Chief's Change Appearance mask: blue, as before -- a
        believer's chosen mask is never taken for one they wore."""
        for chosen in (2, 3, 4, 5):
            with self.subTest(chosen=chosen):
                v = self.village()
                record = v.believer(6, 14, 0, 0, filed=False)
                v.mask_set(record, chosen)
                v.go_back(record, WAYS[0])
                self.assertEqual(v.mask_get(record), 1)
                self.assertEqual((v.head_slot(record), v.mask_row(record)), (SLOT_BLUE, ROW_BLUE))
                self.assertTrue(v.listens(record))
                self.assertEqual(v.export("VvfpHeathensKeepMasksReturned"), 0)

    def test_heathens_the_game_makes_and_the_puzzle_heathens_are_drawn_as_ever(self):
        v = self.village()
        for role, orange, red, slot, row in ((0, 0, 0, SLOT_BLUE, ROW_BLUE), (0, 1, 0, SLOT_ORANGE, ROW_ORANGE),
                                             (0, 0, 1, SLOT_RED, ROW_RED), (12, 0, 0, SLOT_BLUE, ROW_PURPLE),
                                             (14, 0, 0, SLOT_BLUE, ROW_PURPLE), (13, 0, 0, SLOT_BLUE, ROW_CHIEF),
                                             (17, 0, 1, SLOT_RED, ROW_RED)):
            with self.subTest(role=role, orange=orange, red=red):
                record = v.heathen(9, role, orange, red)
                if role or orange or red:            # a store entry never changes a puzzle or orange/red Heathen
                    v.mask_set(record, 5 if role != 13 else 2)
                self.assertEqual((v.head_slot(record), v.mask_row(record)), (slot, row))
                self.assertEqual(v.listens(record), not (orange or red), "the drop test as stock")
                self.assertEqual(v.export("VvfpHeathensKeepMasksLook", record), 0xFFFFFFFF)

    def test_without_the_store_going_back_is_the_stock_game(self):
        for kw in ({"origins": False}, {"keep_export": False}, {"keep_answer": 0}):
            with self.subTest(**kw):
                v = self.village(**kw)
                record = v.heathen(7, 0, 1, 0)
                v.write(record + FACTION, b"\0")    # a believer from an orange Heathen
                v.former[record] = K_ORANGE
                v.go_back(record, WAYS[0])
                self.assertEqual(v.read(record + ORANGE, 2), b"\x01\x00", "the stock bytes, its behaviour")
                self.assertEqual(v.export("VvfpHeathensKeepMasksReturned"), 0)

    def test_the_install_is_refused_on_other_bytes_at_a_drawing_site(self):
        exe = bytearray(render(5, with_requirements(5, [ROW]), "collection_progression"))
        exe[MASK_PICK - 0x400000] = 0x90
        v = GoingBack(bytes(exe))
        v.export("VvfpStartup", 5, 0)
        self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 0)
        self.assertEqual(v.read(0x4669F5, 10), bytes.fromhex("C786FC1C000000000000"), "no site is written")
        self.assertEqual(v.read(0x466966, 7), bytes.fromhex("83BEFC1C00000D"))


# ---- The masks worn: the companion's own file (the owner, 2026-11-22: "Keep Masks must remember the former Heathen
# kind ITSELF, so purple (and every kind) works even with Log Every Death off") -----------------------------------
DOCS = "C:\\Docs"
GAME_MANAGER_WORD, SLOT_FIELD = 0x4DACE0, 0x17D80     # native/shared/game_save_slot.h: New Believers' save slot
NAME = 0x1B9C


class Disk:
    """A small in-memory disk for the companion's file calls (the paths as it builds them)."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.open: dict[int, list] = {}
        self.next = 0x400
        self.blocked = False                 # the Masks Worn file held by another program (OneDrive, an antivirus)
        self.error = 2

    def install(self, p) -> None:
        h = p.api_handlers

        def path_a(q, i=0):
            return q.cstring(q.arg(i)).lower()

        def create(q):
            name, access, disposition = path_a(q), q.arg(1), q.arg(4)
            if self.blocked and "masks worn" in name:
                self.error = 32                                          # ERROR_SHARING_VIOLATION
                return 0xFFFFFFFF, 28
            self.error = 2
            if disposition == 3 and name not in self.files:            # OPEN_EXISTING
                return 0xFFFFFFFF, 28
            if access & 0x40000000:                                      # GENERIC_WRITE: CREATE_ALWAYS
                self.files[name] = b""
            self.next += 4
            self.open[self.next] = [name, 0]
            return self.next, 28

        def read(q):
            name, at = self.open[q.arg(0)]
            piece = self.files[name][at:at + q.arg(2)]
            q.write(q.arg(1), piece)
            self.open[q.arg(0)][1] = at + len(piece)
            if q.arg(3):
                q.put32(q.arg(3), len(piece))
            return 1, 20

        def write(q):
            name, _at = self.open[q.arg(0)]
            self.files[name] += q.read(q.arg(1), q.arg(2))
            if q.arg(3):
                q.put32(q.arg(3), q.arg(2))
            return 1, 20

        def move(q):
            old, new = path_a(q, 0), path_a(q, 1)
            if old not in self.files:
                return 0, 12
            self.files[new] = self.files.pop(old)
            return 1, 12

        def delete(q):
            self.files.pop(path_a(q), None)
            return 1, 4

        def attributes(q):
            return (0x80 if path_a(q) in self.files else 0xFFFFFFFF), 4

        def docs(q):
            q.write(q.arg(1), (DOCS + "\0").encode("utf-16-le"))
            return 1, 16

        def wide_to_multi(q):
            text = q.wstring(q.arg(2)) if q.arg(3) == 0xFFFFFFFF else q.read(q.arg(2), 2 * q.arg(3)).decode("utf-16-le")
            out = text.encode("latin-1", "replace") + (b"\0" if q.arg(3) == 0xFFFFFFFF else b"")
            if q.arg(5):
                q.write(q.arg(4), out[:q.arg(5)])
            return len(out), 32

        h.update({"CreateFileA": create, "ReadFile": read, "WriteFile": write, "MoveFileExA": move,
                  "DeleteFileA": delete, "GetFileAttributesA": attributes, "SHGetSpecialFolderPathW": docs,
                  "FlushFileBuffers": lambda q: (1, 4), "CloseHandle": lambda q: (self.open.pop(q.arg(0), None), (1, 4))[1],
                  "CreateDirectoryW": lambda q: (1, 8), "CreateDirectoryA": lambda q: (1, 8),
                  "GetFileAttributesExW": lambda q: (0, 12), "FindFirstFileW": lambda q: (0xFFFFFFFF, 8),
                  "WideCharToMultiByte": wide_to_multi, "SetLastError": lambda q: (0, 4),
                  "GetLastError": lambda q: (self.error, 0)})


class Remembering(GoingBack):
    """A village whose game knows its save slot, on a disk that outlives the process (a save and a load)."""

    def __init__(self, exe: bytes, disk: Disk, **kw):
        super().__init__(exe, **kw)
        disk.install(self)
        self.clock = 1000
        self.api_handlers["GetTickCount"] = self._tick
        manager = self.alloc(SLOT_FIELD + 0x10)
        self.put32(manager + SLOT_FIELD, 1)
        self.put32(GAME_MANAGER_WORD, manager)
        self.former = None                      # Log Every Death is off: no Former Heathens file

    def _tick(self, q):
        self.clock += 300                       # time passes between the companion's looks at the village
        return self.clock, 0


@unittest.skipIf(_skip(), _skip() or "")
class TheCompanionRemembersTheMaskItself(unittest.TestCase):
    """With Log Every Death off, the masks worn are this companion's own file's: a converted purple Master or
    Heathen Doctor goes back purple, after a save and a load, after a rename, never on a reused record."""
    maxDiff = None

    def village(self, disk: Disk, people=()) -> Remembering:
        v = Remembering(render(5, with_requirements(5, [ROW]), "collection_progression"), disk)
        v.export("VvfpStartup", 5, 0)
        self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 1)
        for index, name in people:
            record = v.record(index)
            v.write(record, bytes(STRIDE))
            v.write(record + ACTIVE, b"\x01")
            v.write(record + NAME, name.encode() + b"\0")
        return v

    def worn_file(self, disk: Disk) -> bytes | None:
        found = [data for path, data in disk.files.items() if path.endswith("masks worn - save 1.dat")]
        return found[0] if found else None

    def test_a_purple_convert_goes_back_purple_without_log_every_death(self):
        for role in (14, 12):                       # a Master, the Heathen Doctor
            with self.subTest(role=role):
                disk = Disk()
                v = self.village(disk, [(0, "Kai")])
                record = v.believer(4, role, 0, 0, filed=False)
                self.assertIsNotNone(self.worn_file(disk), "the companion's own file is written at the conversion")
                v.go_back(record, WAYS[0])
                self.assertEqual((v.mask_get(record), v.mask_row(record), v.u32(record + ROLE)), (4, ROW_PURPLE, 0))
                self.assertTrue(v.listens(record))

    def test_it_survives_a_save_and_a_load(self):
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        v.believer(4, 14, 0, 0, filed=False)
        w = self.village(disk, [(0, "Kai"), (4, "Heathen4")])     # the same village, a new process
        record = w.record(4)
        w.mask_set(record, 1)                       # Change Appearance chose blue for him as a believer
        w.go_back(record, WAYS[0])
        self.assertEqual((w.mask_get(record), w.mask_row(record)), (4, ROW_PURPLE))

    def test_a_rename_in_play_keeps_it(self):
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        record = v.believer(4, 14, 0, 0, filed=False)
        v.write(record + NAME, b"Nobu Akana\0")    # a last name given in play
        v.go_back(record, WAYS[0])
        self.assertEqual((v.mask_get(record), v.mask_row(record)), (4, ROW_PURPLE))

    def test_a_rename_at_a_load_keeps_it(self):
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        v.believer(4, 14, 0, 0, filed=False)
        w = self.village(disk, [(0, "Kai"), (4, "Nobu Akana")])
        record = w.record(4)
        old = w.alloc(32)
        w.write(old, b"Heathen4\0")
        records, names = w.alloc(8), w.alloc(8)
        w.put32(records, record)
        w.put32(names, old)
        self.assertEqual(w.export("VvfpVillagersRenamed", 5, 1, 1, records, names), 1)
        w.go_back(record, WAYS[0])
        self.assertEqual((w.mask_get(record), w.mask_row(record)), (4, ROW_PURPLE))

    def test_a_sex_change_keeps_it(self):
        """A sex change (the Custom Island Event's or Change Appearance's Change sex: native/shared/sex_change.h tells
        every owner in VV_SEX_OWNERS) carries the villager's mask worn to who they are now."""
        source = (ROOT / "native" / "shared" / "sex_change.h").read_text(encoding="utf-8")
        start = source.index("VV_SEX_OWNERS[] = {")
        self.assertIn('"VVFP Heathens Keep Masks.dll"', source[start:source.index("};", start)])
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        record = v.believer(4, 14, 0, 0, filed=False)
        before = v.alloc(STRIDE)
        v.write(before, v.read(record, STRIDE))
        v.put32(record + 0x1B90, 1)                 # now female
        self.assertEqual(v.export("VvfpVillagerSexChanged", 5, 1, record, before), 1)
        v.go_back(record, WAYS[0])
        self.assertEqual((v.mask_get(record), v.mask_row(record)), (4, ROW_PURPLE))

    def test_start_over_drops_the_slots_masks_worn(self):
        """Start Over ("VVFP Save Reset.dll" calls VvfpHeathensKeepMasksVillageReset before it wipes the save's own
        folder, the Masks Worn file with it): nothing of the erased village comes back in the new one."""
        source = (ROOT / "native" / "save_reset_export" / "save_reset_export.c").read_text(encoding="utf-8")
        self.assertIn('"VvfpHeathensKeepMasksVillageReset"', source)
        self.assertIn("notify_heathens_keep_masks(game, slot);", source)
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        record = v.believer(4, 14, 0, 0, filed=False)
        v.export("VvfpHeathensKeepMasksVillageReset", 5, 1)
        for path in [p for p in disk.files if p.endswith("masks worn - save 1.dat")]:
            del disk.files[path]                                    # the save's own folder wiped
        v.mask_set(record, 1)
        v.go_back(record, WAYS[0])                                  # the same name in the new village: not him
        self.assertEqual((v.mask_get(record), v.mask_row(record)), (1, ROW_BLUE))

    def test_another_slots_start_over_keeps_it(self):
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        record = v.believer(4, 14, 0, 0, filed=False)
        v.export("VvfpHeathensKeepMasksVillageReset", 5, 2)
        v.go_back(record, WAYS[0])
        self.assertEqual(v.mask_row(record), ROW_PURPLE)

    def test_a_file_held_a_moment_keeps_it_waiting(self):
        """Codex (#843): the Masks Worn file held by another program at the conversion -- the mask waits, by the
        villager, is theirs while it waits, and is written once the file can be."""
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        v.mask_row(v.heathen(9, 0, 0, 0))          # the companion has the village
        disk.blocked = True
        record = v.believer(4, 14, 0, 0, filed=False)
        self.assertIsNone(self.worn_file(disk), "nothing written while the file is held")
        disk.blocked = False
        v.mask_row(v.record(9))                     # a draw: the store looks again, the waiting mask is kept
        worn = self.worn_file(disk)
        self.assertIsNotNone(worn)
        count = struct.unpack_from("<I", worn, 8)[0]
        self.assertEqual(worn[12 + 8 * count + 4], 4, "his purple (4) is in the file, at his record")
        w = self.village(disk, [(0, "Kai"), (4, "Heathen4"), (9, "Heathen9")])   # a new process: from the file
        w.write(w.record(9) + FACTION, b"\x01")
        w.go_back(w.record(4), WAYS[0])
        self.assertEqual(w.mask_row(w.record(4)), ROW_PURPLE)

    def test_the_patchers_offline_identity_is_the_companions(self):
        """src/vv_last_names.py carries this file in an offline rename by _store_identity: the same identity the
        companion writes (name, sex, parents), checked against the file the companion itself wrote."""
        import vv_last_names as ln
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        record = v.heathen(4, 14, 0, 0)
        v.write(record + 0x1BC0, b"Mako\0")         # a father and a mother, so the parents count
        v.write(record + 0x1BD9, b"Lani\0")
        v.write(record + 0x1B90, struct.pack("<i", 1))
        v.convert(record)
        worn = self.worn_file(disk)
        count = struct.unpack_from("<I", worn, 8)[0]
        stored = struct.unpack_from(f"<{count}I", worn, 12 + 4 * count)
        raw = v.read(record, STRIDE)
        self.assertIn(ln._store_identity(5, raw, NAME, ln.FIELDS[5]), stored[:16])

    def test_going_back_while_the_file_is_still_held(self):
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        disk.blocked = True
        record = v.believer(4, 14, 0, 0, filed=False)
        v.go_back(record, WAYS[0])                  # the file still held: the waiting mask is theirs
        self.assertEqual((v.mask_get(record), v.mask_row(record)), (4, ROW_PURPLE))

    def test_a_reused_record_never_inherits_it(self):
        disk = Disk()
        v = self.village(disk, [(0, "Kai")])
        record = v.believer(4, 14, 0, 0, filed=False)
        v.write(record + ACTIVE, b"\0")             # he passes away; the record is empty
        v.mask_row(v.heathen(9, 0, 0, 0))           # a draw: the companion looks at the village
        v.write(record, bytes(STRIDE))              # a newcomer in his record, a believer
        v.write(record + ACTIVE, b"\x01")
        v.write(record + NAME, b"Lani\0")
        v.mask_set(record, 4)                       # who chose a purple Change Appearance mask
        v.go_back(record, WAYS[0])
        self.assertEqual((v.mask_get(record), v.mask_row(record)), (1, ROW_BLUE), "blue: never his")


if __name__ == "__main__":
    unittest.main()
