"""The Origins Food and Tech Point Doublers double exactly the owner's scope (2026-11-17), in all five games.

FOOD = only food gathered from a food source.  TECH = research-table work (with the research bonuses worked out
there), collectible duplicates and collection effects on tech gain.  Island events, rewards, purchases and cheats
are never doubled.  Each doubler is a whitelist of exact stock return addresses at its game's writer.

The tests render each game's executable through the patcher with only the Origins row, then run the doubler
wrapper in an emulator from the writer's entry, as the game would call it:

* every whitelisted caller doubles a positive amount when the save owns the doubler, and not when it does not;
* every other call of the writer in the stock executable (island events, rewards, purchases, deductions, the
  job events outside the scope) and a call from a companion DLL leave the amount unchanged;
* zero and negative amounts are never changed.

Each whitelisted return is also checked against the stock executable: it is the return of a call to that
game's writer (the VV3 food-bin fruit call exists only with "Fruit is Harvested at the Food Bin").
"""
from __future__ import annotations

import functools
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, UC_PROT_ALL, Uc
    from unicorn.x86_const import (
        UC_X86_REG_ECX,
        UC_X86_REG_EIP,
        UC_X86_REG_ESI,
        UC_X86_REG_ESP,
    )

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

STOCK_DIR = ROOT / "research" / "stock-executables"
STACK_TOP = 0x0FF00000
STORE = 0x20000000          # VV1/VV2: the fake world the writer adds into
DLL_CALLER = 0x10001234     # a companion DLL's call (More Island Events, Story Upgrades, ...)

# The owner's scope, per game: (writer, {return: what it pays}).
TECH = {
    1: (0x41D120, {0x43B318: "research (Science 1)", 0x43B333: "research (Science 2)",
                   0x43B350: "research (Science 3)"}),
    2: (0x426290, {0x46373C: "research (Science 3)", 0x4637C5: "research", 0x46380E: "the fire's point",
                   0x463461: "a duplicate collectible", 0x46346D: "a duplicate collectible",
                   0x463479: "a duplicate collectible"}),
    3: (0x427130, {0x459237: "research (Science 0 or 4+)", 0x4593AF: "research (Science 1-3)",
                   0x4593D5: "the chief's quarter", 0x4593F2: "Magic's point",
                   0x459410: "the chief's third or the potion's point", 0x45943A: "the fire's point",
                   0x42DF7E: "a duplicate collectible"}),
    4: (0x41E300, {0x464E5D: "research", 0x464E87: "the Lab Equipment bonus", 0x464EB0: "the fire's point",
                   0x41447C: "a duplicate collectible", 0x414498: "a duplicate collectible",
                   0x4144B4: "a duplicate collectible"}),
    5: (0x4237B0, {0x46DE4D: "research", 0x46DE7C: "the second set's bonus", 0x46DEA5: "the fire's point",
                   0x4147BE: "a duplicate collectible", 0x4147DD: "a duplicate collectible",
                   0x4147F9: "a duplicate collectible"}),
}
FOOD = {
    1: (0x41D140, {0x43AD91: "berries", 0x43AED2: "crops", 0x43AF41: "fish", 0x43AF93: "crab",
                   0x43AFFC: "mushroom", 0x43B0A0: "the Golden Child's +150 (the owner, 2026-11-18)"}),
    2: (0x4262B0, {0x46319D: "coconuts", 0x46325E: "crops", 0x463317: "fish", 0x463369: "the big catch",
                   0x4633D2: "mushroom"}),
    3: (0x4263F0, {0x434AF1: "fruit", 0x434B1A: "the chief's fruit bonus", 0x431C2F: "honey",
                   0x431C51: "the chief's honey bonus", 0x458EEA: "fish", 0x458FE6: "crab",
                   0x42E07E: "mushroom", 0x434C0B: "the rain lift's fruit", 0x434D84: "the cliff top's fruit",
                   0x434C7C: "fruit at the food bin",
                   0x45906D: "the chief's grant, job event 43 (the owner, 2026-11-18)"}),
    4: (0x41D920, {0x464497: "blackberry bush", 0x464510: "cutting-tool berries", 0x464578: "yellow breadfruit",
                   0x4645B5: "fish", 0x464600: "golden fish", 0x464A4B: "crab", 0x436F1A: "the Mossy Rocks crab",
                   0x468AB7: "the Cooking Pit's catch-up fruit", 0x414665: "mushroom",
                   0x464438: "the inherited fish job"}),
    5: (0x41EB40, {0x46D000: "noni", 0x46D113: "crops", 0x46D7A1: "lake fish", 0x414970: "mushroom",
                   0x46CFA1: "an inherited food job", 0x46D079: "an inherited food job",
                   0x46D764: "an inherited food job", 0x46D7DE: "an inherited food job",
                   0x46DB25: "an inherited food job"}),
}
# Calls that exist only with another row (not in the stock executable).
ROW_ONLY_RETURNS = {0x434C7C}
# Out-of-scope callers named by the owner's rule, checked by name as well as by the full inventory.
NAMED_EXCLUSIONS = {
    1: {"tech": {0x428194: "island event", 0x42BB18: "milestone dialog", 0x41A378: "puzzle discovery"},
        "food": {0x4281DA: "island event", 0x42B938: "milestone dialog"}},
    2: {"tech": {0x4205AC: "island event", 0x44EA32: "Gong of Wonder", 0x4385E6: "Sack/Vial reward"},
        "food": {0x420AE9: "island event", 0x44E9C3: "Gong of Wonder", 0x438298: "Sack/Vial reward"}},
    3: {"tech": {0x41592D: "island event"}, "food": {0x414B95: "island event"}},
    4: {"tech": {0x414A2D: "island event", 0x431AA0: "the +250 object", 0x440889: "the +80,000 grant"},
        "food": {0x41494E: "island event", 0x440898: "the +5,000 grant"}},
    5: {"tech": {0x414D0D: "island event", 0x419EA3: "a refund"}, "food": {0x416D01: "island event"}},
}

# How each game's wrapper is entered, owned and read back.
#   ownership: ("store", tech offset/bit, food offset/bit) for VV1/VV2 (fields of the world ECX points at),
#              ("global", address) for VV3-VV5 (bit 0 Tech, bit 1 Food).
#   result:    where the (possibly doubled) amount is read when the run stops.
GAMES = {
    1: {"ownership": ("store", {"tech": (0x9E90, None), "food": (0x9E94, None)}),
        "store_fields": {"tech": 0xA2FC, "food": 0xA2EC}},
    2: {"ownership": ("store", {"tech": (0x2EAE8, 1), "food": (0x2EAE8, 2)}),
        "store_fields": {"tech": 0x2EADC, "food": 0x2EAA4}},
    3: {"ownership": ("global", 0x5824D0), "stops": {"tech": (0x427136,), "food": (0x4263F5,)},
        "read": {"tech": "arg", "food": "arg"}},
    4: {"ownership": ("global", 0x4D6E10), "stops": {"tech": (0x41E307,), "food": (0x41D954, 0x41D987)},
        "read": {"tech": "arg", "food": "esi"}},
    5: {"ownership": ("global", 0x51D388), "stops": {"tech": (0x4237B7,), "food": (0x41EB74, 0x41EBA7)},
        "read": {"tech": "arg", "food": "esi"}},
}


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


def _stock(game: int) -> Path:
    return STOCK_DIR / _builds()[f"vv{game}"].input_name


@functools.lru_cache(maxsize=None)
def _rendered(game: int) -> bytes:
    build = _builds()[f"vv{game}"]
    data, _ = patcher.render_patched_bytes(_stock(game), build, "collection_progression",
                                           [f"vv{game}_enable_origins_exclusive_features"])
    return bytes(data)


@functools.lru_cache(maxsize=None)
def _writer_calls(game: int, writer: int) -> tuple[int, ...]:
    """Every E8 call to `writer` in the stock executable, as return addresses."""
    pe = pefile.PE(str(_stock(game)), fast_load=True)
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Name.startswith(b".text"))
    found = []
    for rva in range(text.VirtualAddress, text.VirtualAddress + text.Misc_VirtualSize - 5):
        if image[rva] == 0xE8:
            target = base + rva + 5 + struct.unpack_from("<i", image, rva + 1)[0]
            if target == writer:
                found.append(base + rva + 5)
    return tuple(found)


class _Wrapper:
    """The rendered executable mapped once; run(kind, caller, amount, owned) -> amount the writer goes on with."""

    def __init__(self, game: int):
        self.game = game
        pe = pefile.PE(data=_rendered(game))
        self.base = pe.OPTIONAL_HEADER.ImageBase
        image = pe.get_memory_mapped_image()
        size = (len(image) + 0xFFF) & ~0xFFF
        self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        self.mu.mem_map(self.base, size, UC_PROT_ALL)
        self.mu.mem_write(self.base, bytes(image))
        self.pristine = bytes(image)
        self.mu.mem_map(STACK_TOP - 0x100000, 0x100000, UC_PROT_ALL)
        self.mu.mem_map(STORE, 0x40000, UC_PROT_ALL)
        self.mu.mem_map(DLL_CALLER & ~0xFFF, 0x1000, UC_PROT_ALL)   # the companion DLL's code page
        self.mu.mem_write(DLL_CALLER & ~0xFFF, b"\xF4" * 0x1000)
        self.stops: set[int] = set()
        self.mu.hook_add(UC_HOOK_CODE, self._on_code)

    def _on_code(self, mu, address, size, user):
        if address in self.stops:
            mu.emu_stop()

    def _set_owned(self, kind: str, owned: bool) -> None:
        how = GAMES[self.game]["ownership"]
        if how[0] == "global":
            mask = 1 if kind == "tech" else 2
            self.mu.mem_write(how[1], struct.pack("<I", mask if owned else 0))
            return
        offset, bit = how[1][kind]
        value = (bit if bit else 1) if owned else 0
        self.mu.mem_write(STORE + offset, struct.pack("<I", value))

    def run(self, kind: str, caller: int, amount: int, owned: bool) -> int:
        self.mu.mem_write(self.base, self.pristine)
        self.mu.mem_write(STORE, bytes(0x40000))
        self._set_owned(kind, owned)
        writer = (TECH if kind == "tech" else FOOD)[self.game][0]
        esp = STACK_TOP - 0x1000
        self.mu.mem_write(esp, struct.pack("<Ii", caller, amount))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, STORE)
        self.mu.reg_write(UC_X86_REG_ESI, 0x5A5A5A5A)
        spec = GAMES[self.game]
        self.stops = {caller} | set(spec.get("stops", {}).get(kind, ()))
        self.mu.emu_start(writer, 0, count=2000)
        eip = self.mu.reg_read(UC_X86_REG_EIP)
        if eip not in self.stops:
            raise AssertionError(f"VV{self.game} {kind} run from {caller:#x} stopped at {eip:#x}")
        if "store_fields" in spec:
            return struct.unpack("<i", self.mu.mem_read(STORE + spec["store_fields"][kind], 4))[0]
        if spec["read"][kind] == "esi":
            return struct.unpack("<i", struct.pack("<I", self.mu.reg_read(UC_X86_REG_ESI)))[0]
        return struct.unpack("<i", self.mu.mem_read(esp + 4, 4))[0]


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn are not installed")
class DoublerScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        for game in range(1, 6):
            if not _stock(game).is_file():
                self.skipTest(f"stock executable missing: {_stock(game)}")

    @functools.lru_cache(maxsize=None)
    def _wrapper(self, game: int) -> "_Wrapper":
        return _Wrapper(game)

    def test_every_whitelisted_return_is_a_stock_call_of_the_writer(self) -> None:
        for table, kind in ((TECH, "tech"), (FOOD, "food")):
            for game, (writer, eligible) in table.items():
                calls = set(_writer_calls(game, writer))
                for ret in eligible:
                    if ret in ROW_ONLY_RETURNS:
                        continue
                    with self.subTest(game=game, kind=kind, ret=hex(ret)):
                        self.assertIn(ret, calls)

    def test_manifests_carry_the_same_whitelists(self) -> None:
        for game in range(1, 6):
            if game == 5:
                evidence = json.loads((ROOT / "data" / "vv5_task9_native_actions.json").read_text(
                    encoding="utf-8"))["doubler_evidence"]
                tech, food = evidence["tech_positive_returns"], evidence["food_positive_returns"]
            else:
                evidence = json.loads((ROOT / "data" / f"vv{game}_origins_feature.json").read_text(
                    encoding="utf-8"))["doubler_evidence"]
                tech, food = evidence["tech_eligible_returns"], evidence["food_eligible_returns"]
            with self.subTest(game=game):
                self.assertEqual({int(v, 16) for v in tech}, set(TECH[game][1]))
                self.assertEqual({int(v, 16) for v in food}, set(FOOD[game][1]))

    def _check(self, game: int, kind: str) -> None:
        writer, eligible = (TECH if kind == "tech" else FOOD)[game]
        wrapper = self._wrapper(game)
        for ret, what in eligible.items():
            with self.subTest(game=game, kind=kind, source=what, ret=hex(ret)):
                self.assertEqual(wrapper.run(kind, ret, 37, True), 74)
                self.assertEqual(wrapper.run(kind, ret, 37, False), 37)
                self.assertEqual(wrapper.run(kind, ret, 0, True), 0)
                self.assertEqual(wrapper.run(kind, ret, -5, True), -5)
        others = (set(_writer_calls(game, writer)) - set(eligible)) | {DLL_CALLER}
        others |= set(NAMED_EXCLUSIONS[game][kind])
        for ret in sorted(others):
            with self.subTest(game=game, kind=kind, outside=hex(ret),
                              named=NAMED_EXCLUSIONS[game][kind].get(ret, "")):
                self.assertEqual(wrapper.run(kind, ret, 37, True), 37)

    def test_vv1_doublers(self) -> None:
        self._check(1, "tech")
        self._check(1, "food")

    def test_vv2_doublers(self) -> None:
        self._check(2, "tech")
        self._check(2, "food")

    def test_vv3_doublers(self) -> None:
        self._check(3, "tech")
        self._check(3, "food")

    def test_vv4_doublers(self) -> None:
        self._check(4, "tech")
        self._check(4, "food")

    def test_vv5_doublers(self) -> None:
        self._check(5, "tech")
        self._check(5, "food")


if __name__ == "__main__":
    unittest.main()
