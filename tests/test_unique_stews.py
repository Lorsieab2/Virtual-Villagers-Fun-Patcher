"""Unique stews: The Lost Children's Total Stews Found, The Secret City's and
The Tree of Life's Stews Found (docs/village-statistics-directive.md, sections
III-V, VII-X and XV).

What is pinned, and how:

* The stew-completion hooks are RUN, on the patcher's rendered bytes, in an
  emulator: for every ordered herb triple each game can put in its pot (and
  for The Tree of Life both waters), the hook sets exactly the one pending bit
  the companion decodes, a herb outside the game's set records nothing, and
  every register, the flags and the stack are left exactly as the stock
  instructions leave them when the stock code reaches the same point.
* A failed Secret City brew -- the potion blows up -- records nothing; a
  successful one records its herbs. Both are the stock brew routine run on
  the rendered image with only the dice replaced.
* The save wrapper hands primary-slot saves to the companion's
  SaveVillageStatistics (which flushes pending counts and stew bits to the
  .dat files and zeroes them before calling the stock writer), sends every
  other save straight to the writer, and never makes a save depend on the
  companion.
* The .dat behaviour -- tests A to G, missing / corrupt / foreign / unreadable
  files, union, atomic replace, restart -- is the C harness
  native/statistics_export/statistics_store_harness.c, compiled from the same
  source as the companion and run here where the 32-bit MSVC toolchain is
  installed.
* Rendering every game's whole public catalog in all three modes shows the
  new bytes collide with nothing.
"""
from __future__ import annotations

import itertools
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, UC_PROT_ALL, Uc, UcError
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EFLAGS, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import vv_fun_patcher as vfp  # noqa: E402
import build_statistics_features as builder  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
MANIFEST = ROOT / "data" / "statistics_features.json"
STORE = ROOT / "native" / "statistics_export" / "statistics_store.c"
HARNESS_BUILD = ROOT / "scripts" / "build_statistics_store_harness.ps1"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
MODES = ("stock", "collection_progression", "immediate_fixed")
REGS = (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
        UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP)
# CF PF AF ZF SF DF OF
FLAG_MASK = 0x001 | 0x004 | 0x010 | 0x040 | 0x080 | 0x400 | 0x800

MANAGER = 0x10000000
POT = 0x11000000
STACK = 0x20000000
RETURN = 0x30000000

# game: (stock continuation after the stolen bytes, herb ids, pending bitset
#        address kind, bitset location, water)
STEW = {
    "vv2": {"hook": 0x425B90, "resume": 0x425B97, "first": 0x30, "n": 6,
            "bits": ("manager", 0x2E5E8), "water": False},
    "vv3": {"hook": 0x430510, "resume": 0x430515, "first": 0x1F, "n": 7,
            "bits": ("absolute", 0x5824F8), "water": False},
    "vv4": {"hook": 0x42EE5F, "resume": 0x42EE66, "first": 0x1F, "n": 4,
            "bits": ("absolute", 0x4D6E40), "water": True, "salt": 0x704F00},
}

_RENDERS: dict[tuple[str, str, bool], bytes] = {}


def render(game: str, mode: str = "immediate_fixed", with_feature: bool = True) -> bytes:
    key = (game, mode, with_feature)
    if key not in _RENDERS:
        build = next(b for b in vfp.load_builds() if b.id == game)
        rows = [f"{game}_write_village_statistics"] if with_feature else []
        rendered, _ = vfp.render_patched_bytes(STOCK / EXE[game], build, mode, rows)
        _RENDERS[key] = bytes(rendered)
    return _RENDERS[key]


def machine(image: bytes) -> Uc:
    """The image mapped at its preferred base, every section in place."""
    pe = pefile.PE(data=image, fast_load=True)
    mapped = pe.get_memory_mapped_image()
    size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, size, UC_PROT_ALL)
    mu.mem_write(0x400000, bytes(mapped[:size]))
    for base in (MANAGER, POT, RETURN):
        mu.mem_map(base, 0x40000, UC_PROT_ALL)
    mu.mem_map(STACK - 0x10000, 0x20000, UC_PROT_ALL)
    mu.mem_write(RETURN, b"\xF4")
    return mu


def run_until(mu: Uc, start: int, stops: set[int], limit: int = 5000) -> int:
    seen = {"at": None}

    def hook(uc, address, size, user):
        if address in stops:
            seen["at"] = address
            uc.emu_stop()

    handle = mu.hook_add(UC_HOOK_CODE, hook)
    try:
        mu.emu_start(start, 0, count=limit)
    finally:
        mu.hook_del(handle)
    return seen["at"]


def bits_address(game: str) -> int:
    kind, where = STEW[game]["bits"]
    return MANAGER + where if kind == "manager" else where


def bits_size(game: str) -> int:
    n = STEW[game]["n"]
    return ((n ** 3 * (2 if STEW[game]["water"] else 1)) + 31) // 32 * 4


def stage(mu: Uc, game: str, herbs: tuple[int, int, int], salt: int) -> None:
    """Put the pot's herbs where each game's completion code has them."""
    esp = STACK - 0x200
    mu.mem_write(esp, struct.pack("<4I", RETURN, *herbs))       # VV3 stack args
    mu.reg_write(UC_X86_REG_ESP, esp)
    if game == "vv2":
        mu.mem_write(MANAGER + 0x3043C, struct.pack("<3I", *herbs))
        mu.reg_write(UC_X86_REG_ECX, MANAGER)
    elif game == "vv3":
        mu.reg_write(UC_X86_REG_ECX, 0x593BA0)                  # the recipe object
    else:
        mu.mem_write(POT + 0xC, struct.pack("<3I", *herbs))
        mu.reg_write(UC_X86_REG_ESI, POT)
        mu.mem_write(STEW[game]["salt"], bytes([1 if salt else 0]))
    # Distinctive values in every other register, so a clobber shows.
    for reg, value in ((UC_X86_REG_EAX, 0x11111111), (UC_X86_REG_EBX, 0x22222222),
                       (UC_X86_REG_EDX, 0x44444444), (UC_X86_REG_EDI, 0x77777777),
                       (UC_X86_REG_EBP, 0x55555555)):
        mu.reg_write(reg, value)
    if game != "vv2":
        mu.reg_write(UC_X86_REG_ECX, mu.reg_read(UC_X86_REG_ECX))
    mu.reg_write(UC_X86_REG_EFLAGS, 0x202 | 0x001 | 0x040 | 0x800)   # CF ZF OF set


def state(mu: Uc) -> tuple:
    esp = mu.reg_read(UC_X86_REG_ESP)
    return (
        tuple(mu.reg_read(r) for r in REGS),
        mu.reg_read(UC_X86_REG_EFLAGS) & FLAG_MASK,
        bytes(mu.mem_read(esp, 0x40)),
    )


def run_hook(game: str, image: bytes, herbs: tuple[int, int, int], salt: int = 0):
    mu = machine(image)
    stage(mu, game, herbs, salt)
    at = run_until(mu, STEW[game]["hook"], {STEW[game]["resume"]})
    assert at == STEW[game]["resume"], (game, herbs, at)
    bits = bytes(mu.mem_read(bits_address(game), bits_size(game)))
    return state(mu), bits


def set_bits(bits: bytes) -> list[int]:
    return [i for i in range(len(bits) * 8) if bits[i >> 3] & (1 << (i & 7))]


class StewHookTests(unittest.TestCase):
    def test_every_ordered_triple_sets_exactly_its_own_bit_and_the_stock_state(self):
        for game, facts in STEW.items():
            image = render(game)
            stock = (STOCK / EXE[game]).read_bytes()
            first, n = facts["first"], facts["n"]
            waters = (0, 1) if facts["water"] else (0,)
            checked = 0
            for salt in waters:
                for triple in itertools.product(range(n), repeat=3):
                    herbs = tuple(first + h for h in triple)
                    with self.subTest(game=game, herbs=herbs, salt=salt):
                        patched_state, bits = run_hook(game, image, herbs, salt)
                        stock_state, stock_bits = run_hook(game, stock, herbs, salt)
                        index = (triple[0] * n + triple[1]) * n + triple[2]
                        if facts["water"]:
                            index = index * 2 + salt
                        self.assertEqual(set_bits(bits), [index])
                        self.assertEqual(set_bits(stock_bits), [], "stock sets no bit")
                        self.assertEqual(
                            patched_state, stock_state,
                            "registers, flags or stack differ from the stock "
                            "instructions at the resume point",
                        )
                        checked += 1
            self.assertEqual(checked, n ** 3 * len(waters))

    def test_a_herb_outside_the_game_set_records_nothing(self):
        for game, facts in STEW.items():
            image = render(game)
            first, n = facts["first"], facts["n"]
            for bad in (0, first - 1, first + n, 0xFFFFFFFF):
                for position in range(3):
                    herbs = [first, first, first]
                    herbs[position] = bad
                    with self.subTest(game=game, herbs=herbs):
                        patched_state, bits = run_hook(game, image, tuple(herbs))
                        stock_state, _ = run_hook(game, (STOCK / EXE[game]).read_bytes(), tuple(herbs))
                        self.assertEqual(set_bits(bits), [])
                        self.assertEqual(patched_state, stock_state)

    def test_the_bits_accumulate_and_decode_to_the_triples(self):
        """Two stews before a save leave two bits; the companion decodes each
        ordered index back to its herbs exactly as statistics_store.c does."""
        for game, facts in STEW.items():
            first, n = facts["first"], facts["n"]
            mu = machine(render(game))
            made = [(first, first + 1, first + 2), (first + 2, first + 2, first)]
            for herbs in made:
                stage(mu, game, herbs, 1 if facts["water"] else 0)
                self.assertEqual(run_until(mu, facts["hook"], {facts["resume"]}), facts["resume"])
            bits = set_bits(bytes(mu.mem_read(bits_address(game), bits_size(game))))
            decoded = set()
            for index in bits:
                triple = index // 2 if facts["water"] else index
                decoded.add((triple // (n * n) + first, (triple // n) % n + first, triple % n + first))
            with self.subTest(game=game):
                self.assertEqual(decoded, set(made))

    def test_the_pending_bitsets_fit_inside_the_saved_scratch_space(self):
        """The bits must stay inside the scratch space reserved for them: VV2
        manager+0x2E5E8..+0x2E603 (inside +0x2E528..+0x2E607, zeroed by the
        new-village reset), VV3 live +0x58..+0x83 and VV4 live +0x60..+0x6F
        (inside the 0x98-byte block copied to and from the save)."""
        limits = {"vv2": (0x2E5E8, 0x2E608), "vv3": (0x5824F8, 0x5824A0 + 0x98),
                  "vv4": (0x4D6E40, 0x4D6DE0 + 0x98)}
        for game in STEW:
            start, end = limits[game]
            with self.subTest(game=game):
                self.assertEqual(STEW[game]["bits"][1], start)
                self.assertLessEqual(start + bits_size(game), end)


class SecretCityBrewTests(unittest.TestCase):
    """0x430A50 rolls rand(100) against the brewer's odds: a roll at or under
    them is the explosion (0x430A9C jle 0x430AED) and never reaches the
    recipe routine; above them, 0x430AAC calls it with the pot's herbs."""

    RAND = 0x4032D0

    def brew(self, roll: int) -> tuple[int, list[int]]:
        mu = machine(render("vv3"))
        pot = POT
        mu.mem_write(pot + 8, struct.pack("<3I", 0x1F, 0x21, 0x25))
        esp = STACK - 0x200
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_EDI, pot)
        # 3 - level, which 0x430A8F multiplies by 15: a threshold of 30.
        mu.reg_write(UC_X86_REG_EBX, 2)

        def dice(uc, address, size, user):
            if address == self.RAND:
                ret = struct.unpack("<I", uc.mem_read(uc.reg_read(UC_X86_REG_ESP), 4))[0]
                uc.reg_write(UC_X86_REG_EAX, roll)
                uc.reg_write(UC_X86_REG_ESP, uc.reg_read(UC_X86_REG_ESP) + 4)
                uc.reg_write(UC_X86_REG_EIP, ret)

        mu.hook_add(UC_HOOK_CODE, dice)
        # From the roll itself: push 0x64 ; call rand ; add esp,4 ; cmp ; jle.
        at = run_until(mu, 0x430A8D, {0x430AED, 0x430515})
        return at, set_bits(bytes(mu.mem_read(0x5824F8, bits_size("vv3"))))

    def test_a_failed_brew_records_nothing(self):
        for roll in (0, 12, 30):
            with self.subTest(roll=roll):
                at, bits = self.brew(roll)
                self.assertEqual(at, 0x430AED, "the failure path")
                self.assertEqual(bits, [])

    def test_a_successful_brew_records_its_herbs(self):
        for roll in (31, 99):
            with self.subTest(roll=roll):
                at, bits = self.brew(roll)
                self.assertEqual(at, 0x430515, "through the hook into the recipe routine")
                self.assertEqual(bits, [((0 * 7) + 2) * 7 + 6])

    def test_the_recipe_routine_has_one_caller_in_the_rendered_image(self):
        image = render("vv3")
        pe = pefile.PE(data=image, fast_load=True)
        text = pe.sections[0]
        base = 0x400000 + text.VirtualAddress
        raw = image[text.PointerToRawData:text.PointerToRawData + text.Misc_VirtualSize]
        callers = []
        for i in range(len(raw) - 5):
            if raw[i] == 0xE8:
                target = base + i + 5 + struct.unpack_from("<i", raw, i + 1)[0]
                if target == 0x430510:
                    callers.append(base + i)
        self.assertEqual(callers, [0x430AAC])


class TreeOfLifeSuccessOnlyTests(unittest.TestCase):
    def test_the_hook_is_reached_only_after_the_success_test(self):
        """0x42EE0B calls the success test 0x42DC80; `jne 0x42EE44` takes the
        success path, whose two routes both arrive at 0x42EE5F. The failure
        path returns at 0x42EE43 without passing it."""
        import capstone
        stock = (STOCK / EXE["vv4"]).read_bytes()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        start, end = 0x42EDE0, 0x42EE83
        code = stock[start - 0x400000:end - 0x400000]
        instructions = list(md.disasm(code, start))
        by_address = {i.address: i for i in instructions}
        self.assertEqual(by_address[0x42EE0B].op_str, "0x42dc80")
        self.assertEqual((by_address[0x42EE12].mnemonic, by_address[0x42EE12].op_str),
                         ("jne", "0x42ee44"))
        self.assertEqual(by_address[0x42EE43].mnemonic, "ret")
        # Predecessors of 0x42EE5F: the je at 0x42EE46 and the fall-through
        # from 0x42EE5A -- both on the success side (addresses >= 0x42EE44).
        preds = [i.address for i in instructions
                 if i.op_str == "0x42ee5f" and i.mnemonic.startswith("j")]
        preds.append(0x42EE5A)
        self.assertTrue(all(p >= 0x42EE44 for p in preds), preds)
        failure = [i for i in instructions if 0x42EE14 <= i.address <= 0x42EE43]
        self.assertFalse(any(i.op_str == "0x42ee5f" for i in failure))


class SaveWrapperTests(unittest.TestCase):
    """The full-save wrapper in each game's statistics cave."""

    GET_MODULE = RETURN + 0x100
    LOAD = RETURN + 0x200
    PROC = RETURN + 0x300
    EXPORT = RETURN + 0x400

    def run_wrapper(self, game: str, slot: int, *, dll: bool = True, export: bool = True):
        config = builder.GAMES[game]
        mu = machine(render(game))
        calls: list[tuple] = []
        writer = int(config["writer_va"])
        for iat, stub in ((config["get_module_handle_iat"], self.GET_MODULE),
                          (config["load_library_iat"], self.LOAD),
                          (config["get_proc_address_iat"], self.PROC)):
            mu.mem_write(int(iat), struct.pack("<I", stub))

        def args(uc, count):
            esp = uc.reg_read(UC_X86_REG_ESP)
            return struct.unpack("<%dI" % (count + 1), uc.mem_read(esp, 4 * (count + 1)))

        def stdcall_return(uc, value, count):
            ret = args(uc, 0)[0]
            uc.reg_write(UC_X86_REG_EAX, value)
            uc.reg_write(UC_X86_REG_ESP, uc.reg_read(UC_X86_REG_ESP) + 4 + 4 * count)
            uc.reg_write(UC_X86_REG_EIP, ret)

        def hook(uc, address, size, user):
            if address == self.GET_MODULE:
                calls.append(("GetModuleHandleA",))
                stdcall_return(uc, 0, 1)            # not yet loaded
            elif address == self.LOAD:
                calls.append(("LoadLibraryA", bytes(uc.mem_read(args(uc, 1)[1], 27))))
                stdcall_return(uc, 0x6000000 if dll else 0, 1)
            elif address == self.PROC:
                a = args(uc, 2)
                calls.append(("GetProcAddress", bytes(uc.mem_read(a[2], 22))))
                stdcall_return(uc, self.EXPORT if export else 0, 2)
            elif address == self.EXPORT:
                calls.append(("SaveVillageStatistics",) + args(uc, 6)[1:])
                stdcall_return(uc, 0xABCD0001, 6)
            elif address == writer:
                calls.append(("writer", uc.reg_read(UC_X86_REG_ECX)) + args(uc, 3)[1:])
                stdcall_return(uc, 0x12340001, 3)

        mu.hook_add(UC_HOOK_CODE, hook)
        esp = STACK - 0x200
        mu.mem_write(esp, struct.pack("<4I", RETURN, 0x5000, 0x1234, slot))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, MANAGER)
        mu.reg_write(UC_X86_REG_EDI, slot)
        mu.reg_write(UC_X86_REG_EBX, 0xB0B0B0B0)
        mu.reg_write(UC_X86_REG_ESI, 0x5E5E5E5E)
        mu.reg_write(UC_X86_REG_EBP, 0xBEBEBEBE)
        at = run_until(mu, int(config["cave_va"]), {RETURN}, limit=2000)
        self.assertEqual(at, RETURN)
        after = {
            "eax": mu.reg_read(UC_X86_REG_EAX),
            "ebx": mu.reg_read(UC_X86_REG_EBX),
            "esi": mu.reg_read(UC_X86_REG_ESI),
            "edi": mu.reg_read(UC_X86_REG_EDI),
            "ebp": mu.reg_read(UC_X86_REG_EBP),
            "esp": mu.reg_read(UC_X86_REG_ESP),
        }
        return calls, after, esp

    def test_a_primary_slot_save_goes_through_the_companion(self):
        for game in EXE:
            config = builder.GAMES[game]
            for slot in (1, 3, 5):
                with self.subTest(game=game, slot=slot):
                    calls, after, esp = self.run_wrapper(game, slot)
                    names = [c[0] for c in calls]
                    self.assertEqual(names, ["GetModuleHandleA", "LoadLibraryA",
                                             "GetProcAddress", "SaveVillageStatistics"])
                    self.assertEqual(calls[1][1], b"VVFP Statistics Export.dll\0")
                    self.assertEqual(calls[2][1], b"SaveVillageStatistics\0")
                    self.assertEqual(
                        calls[3][1:],
                        (int(config["game_number"]), MANAGER, slot,
                         int(config["writer_va"]), 0x5000, 0x1234))
                    self.assertEqual(after["eax"], 0xABCD0001, "the companion's result is the game's")
                    self.assertEqual(after["esp"], esp + 4 + 0xC, "ret 0xC like the writer")
                    self.assertEqual((after["ebx"], after["esi"], after["edi"], after["ebp"]),
                                     (0xB0B0B0B0, 0x5E5E5E5E, slot, 0xBEBEBEBE))

    def test_every_other_save_goes_straight_to_the_writer(self):
        for game in EXE:
            for slot, dll, export in ((0, True, True), (0x15, True, True), (6, True, True),
                                      (2, False, True), (2, True, False)):
                with self.subTest(game=game, slot=slot, dll=dll, export=export):
                    calls, after, esp = self.run_wrapper(game, slot, dll=dll, export=export)
                    self.assertNotIn("SaveVillageStatistics", [c[0] for c in calls])
                    self.assertEqual(calls[-1], ("writer", MANAGER, 0x5000, 0x1234, slot))
                    self.assertEqual(after["eax"], 0x12340001)
                    self.assertEqual(after["esp"], esp + 4 + 0xC)
                    self.assertEqual(after["ebx"], 0xB0B0B0B0)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_each_stew_hook_is_a_jump_over_whole_stock_instructions(self):
        stews = {"vv2": ("0x25B90", "5556578BF133FF"), "vv3": ("0x30510", "538B5C240C"),
                 "vv4": ("0x2EE5F", "6A18B948517000")}
        for feature in self.manifest["features"]:
            game = feature["game_id"]
            rows = [p for p in feature["patches"] if "combination every completed stew" in p["purpose"]]
            with self.subTest(game=game):
                if game not in stews:
                    self.assertEqual(rows, [])
                    continue
                self.assertEqual(len(rows), 1)
                offset, before = stews[game]
                self.assertEqual((rows[0]["offset"], rows[0]["before"]), (offset, before))
                after = bytes.fromhex(rows[0]["after"])
                self.assertEqual(after[0], 0xE9)
                self.assertEqual(after[5:], b"\x90" * (len(after) - 5))

    def test_the_vv2_chain_lies_only_in_stock_nop_padding_after_a_return(self):
        stock = (STOCK / EXE["vv2"]).read_bytes()
        feature = next(f for f in self.manifest["features"] if f["game_id"] == "vv2")
        pieces = [p for p in feature["patches"] if "NOP padding" in p["purpose"]]
        self.assertGreaterEqual(len(pieces), 2)
        for piece in pieces:
            offset = int(piece["offset"], 16)
            before = bytes.fromhex(piece["before"])
            with self.subTest(offset=piece["offset"]):
                self.assertEqual(stock[offset:offset + len(before)], before)
                self.assertEqual(set(before), {0x90})
                self.assertTrue(stock[offset - 1] == 0xC3 or stock[offset - 3] == 0xC2)
                self.assertNotIn(0x73F42, range(offset, offset + len(before)),
                                 "the publish-time crash-immunity run is off limits")


class CatalogCompositionTests(unittest.TestCase):
    def test_every_game_renders_its_whole_public_catalog_in_every_mode(self):
        """The patcher refuses overlapping claims; rendering every public
        feature together, in each mode, proves the new bytes collide with
        nothing."""
        patches = vfp.load_public_fun_patches()
        for game in EXE:
            ids = [p.raw["id"] for p in patches if p.raw.get("game_id") == game]
            build = next(b for b in vfp.load_builds() if b.id == game)
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    # Any refusal fails the test: a render that does not
                    # happen proves nothing about overlap.
                    _, applied = vfp.render_patched_bytes(STOCK / EXE[game], build, mode, ids)
                    owners = {row["owner"] for row in applied}
                    self.assertIn(f"feature:{game}_write_village_statistics", owners)
                    spans = []
                    for row in applied:
                        offset = int(row["offset"], 16)
                        length = (len(bytes.fromhex(row["before"])) if row.get("before")
                                  else int(row.get("length", 0)))
                        spans.append((offset, offset + length, row["owner"]))
                    # Only this feature's rows are checked: other features'
                    # appended pages are composed through the patcher's own
                    # overlays and legitimately share bytes with each other.
                    mine = f"feature:{game}_write_village_statistics"
                    own = [s for s in spans if s[2] == mine]
                    others = [s for s in spans if s[2] != mine]
                    self.assertGreater(len(own), 1)
                    for a0, a1, _ in own:
                        for b0, b1, bo in others:
                            self.assertFalse(
                                a0 < b1 and b0 < a1,
                                f"{mine} {a0:#x}..{a1:#x} overlaps {bo} {b0:#x}..{b1:#x}")


class StoreSourceTests(unittest.TestCase):
    def test_the_documented_formats_are_the_ones_written(self):
        text = STORE.read_text(encoding="utf-8")
        for needle in ('"VVFP STEW DISCOVERIES v1 game=%d"', '"VVFP VILLAGE STATISTICS v1 game=%d\\n"',
                       '"stew=%d herbs=%02X,%02X,%02X water=%s"', '"stew=%d herbs=%02X,%02X,%02X"',
                       'L"Virtual Villagers Fun Patcher Data\\\\Stew Discoveries"',
                       'L"%ls\\\\Stew Discoveries - Save %d.dat"',
                       'L"%ls\\\\Village Statistics - Save %d.dat"',
                       "MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_store_harness_passes(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HARNESS_BUILD)],
            capture_output=True, text=True, timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("== 0 failure(s) ==", result.stdout)
        for name in ("VV2 A:", "VV2 B:", "VV2 C:", "VV2 D:", "VV2 E:", "VV2: every order",
                     "VV3 A:", "VV3 D:", "VV3 E:", "VV4 G:", "VV4 E:",
                     "a corrupt file invents no discoveries", "each flush is the union",
                     "the atomic replace leaves no .tmp", "an unreadable file is left alone",
                     "increment -> PreSave", "reloading an older save does not double count"):
            with self.subTest(case=name):
                self.assertIn(name, result.stdout)


if __name__ == "__main__":
    unittest.main()
