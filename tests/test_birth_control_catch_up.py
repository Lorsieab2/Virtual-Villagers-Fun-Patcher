"""Birth Control, all five games: Parenting-ticked villagers try for babies during catch-up as often as any other
job is done (the owner, 2026-11-19: "why are people checked on parenting not embracing people during catchup and
making them have babies? they should" ... "that should be part of birth control for all 5 games").

Each game's catch-up job turn (A New Home 0x42E790, The Lost Children 0x43B4D0, The Secret City 0x45BF00, The Tree
of Life 0x465750, New Believers 0x46E8E0) takes the chooser's pick and, for the Children pick only, rolls
RNG(100) <= 5 before the embrace: 6 tries in 100 job turns, while every other pick goes on to its job.  Each game's
Birth Control row raises that bound to 99 (one guarded byte), so the pick always goes on to the embrace.

The worker is EMULATED FROM ITS ENTRY in the executable the patcher renders (stock, Birth Control off, Birth Control
on).  The worker runs as machine code; its leaf calls (the opening update, the chooser, the RNG, New Believers'
population check, the embrace queue and the step runner) are scripted, and any other call stops the run and is
recorded, so a non-Children pick is seen leaving for its own job.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, render_patched_bytes, resolve_fun_patch_ids  # noqa: E402

STACK_TOP = 0x0F000000
SENTINEL = 0x0E000000
OBJ = 0x20000000            # the worker's this (VV1/VV2: game object; VV3: the manager; VV4/VV5: villager object)
ARRAY = 0x30000000          # VV1/VV2 villager array, VV3/VV4/VV5 villager record
INDEX = 3
ADULT, CHILD = 0x168, 0x117     # 18 years; 280 age units - 1 (13.95 years)

# Per game: the worker; how the villager is passed; record field offsets (sick, age, health, pregnant); the
# scripted calls {entry: (name, stack bytes popped)}; the patched byte's VA; the Children pick.
G = {
    "vv1": dict(worker=0x42E790, end=0x42E82F, stride=0x3D8, arg="index", sick=0x354, age=0x348, health=0x344, preg=0x358,
                calls={0x439470: ("update", 4), 0x439AE0: ("choose", 8), 0x402F10: ("rand", 0),
                       0x4399F0: ("embrace", 28), 0x446C70: ("run", 4)},
                site=0x42E7EF, children=2, other=1, retbytes=4),
    "vv2": dict(worker=0x43B4D0, end=0x43B598, stride=0xE48C, arg="index", sick=0x53C, age=0x530, health=0x52C, preg=0x540,
                calls={0x4492A0: ("update", 4), 0x449C60: ("choose", 8), 0x4031A0: ("rand", 0),
                       0x449B70: ("embrace", 28), 0x464680: ("run", 4)},
                site=0x43B53C, children=2, other=1, retbytes=4),
    "vv3": dict(worker=0x45BF00, end=0x45BFD3, arg="record", sick=0xE89, age=0xDC4, health=0xE78, preg=0xE8C,
                calls={0x460F70: ("update", 4), 0x459730: ("choose", 4), 0x4032D0: ("rand", 0),
                       0x4616B0: ("embrace", 0), 0x45B790: ("run", 4)},
                site=0x45BF61, children=1, other=3, retbytes=4),
    "vv4": dict(worker=0x465750, end=0x465837, arg="object", sick=0x1C48, age=0x1B8C, health=0x1C40, preg=0x1C4C,
                calls={0x468C60: ("update", 0), 0x461CC0: ("choose", 0), 0x4036D0: ("rand", 0),
                       0x469720: ("embrace", 0), 0x464FA0: ("run", 0)},
                site=0x4657AE, children=1, other=3, retbytes=0),
    "vv5": dict(worker=0x46E8E0, end=0x46E9D9, arg="object", sick=0x1C48, age=0x1B8C, health=0x1C40, preg=0x1C4C,
                calls={0x473440: ("update", 0), 0x46A3C0: ("choose", 0), 0x403660: ("rand", 0),
                       0x472BD0: ("population", 0), 0x474CE0: ("embrace", 0), 0x46E020: ("run", 0)},
                site=0x46E93E, children=1, other=3, retbytes=0),
}
# The conception code each game keeps byte for byte (the roll and what reaches it).
CONCEPTION = {"vv1": (0x446C70, 0x447260), "vv2": (0x464680, 0x464A60), "vv3": (0x45B790, 0x45B8D0),
              "vv4": (0x464FA0, 0x465200), "vv5": (0x46E020, 0x46E260)}
BUILDS = {build.id: build for build in load_builds()}
STOCK = {g: ROOT / "research" / "stock-executables" / BUILDS[g].input_name for g in G}
STOCK_PRESENT = all(path.is_file() for path in STOCK.values())
MODES = ("stock", "collection_progression", "immediate_fixed")


def _feature(game: str) -> str:
    return f"{game}_birth_control"


_RENDERS: dict[tuple[str, bool, str], bytes] = {}


def rendered(game: str, birth_control: bool, mode: str = "stock") -> bytes:
    key = (game, birth_control, mode)
    if key not in _RENDERS:
        ids: list[str] = []
        if birth_control:
            catalog = [p for p in load_fun_patches() if p.id == _feature(game)]
            ids = resolve_fun_patch_ids([_feature(game)], game_id=game, patches=catalog)
        data, _ = render_patched_bytes(STOCK[game], BUILDS[game], mode, ids)
        _RENDERS[key] = bytes(data)
    return _RENDERS[key]


def _file_offset(exe: bytes, va: int) -> int:
    pe = pefile.PE(data=exe, fast_load=True)
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


class Worker:
    """One game's catch-up job turn, run from its entry for one adult villager."""

    def __init__(self, game: str, exe: bytes):
        self.game, self.g = game, G[game]
        pe = pefile.PE(data=exe, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        mu.mem_map(base, size)
        mu.mem_write(base, exe[:pe.OPTIONAL_HEADER.SizeOfHeaders])
        for section in pe.sections:
            raw = exe[section.PointerToRawData:section.PointerToRawData + section.SizeOfRawData]
            mu.mem_write(base + section.VirtualAddress, raw[:max(0, size - section.VirtualAddress)])
        mu.mem_map(STACK_TOP - 0x100000, 0x100000)
        mu.mem_map(SENTINEL, 0x1000)
        mu.mem_map(OBJ, 0x10000)
        mu.mem_map(ARRAY, 0x100000)
        self.mu = mu
        # The worker's own body: from its entry to its last ret (the padding after it).
        self.lo, self.hi = self.g["worker"], self.g["end"]
        mu.hook_add(UC_HOOK_CODE, self._hook)

    def _record(self) -> int:
        return ARRAY + (INDEX * self.g["stride"] if self.g["arg"] == "index" else 0)

    def _hook(self, mu, address, size, user_data):
        if address == SENTINEL:
            self.events.append(("returned",))
            mu.emu_stop()
            return
        if self.lo <= address < self.hi:
            return
        leaf = self.g["calls"].get(address)
        if leaf is None:
            self.events.append(("other", address))
            mu.emu_stop()
            return
        name, pops = leaf
        value = 0
        if name == "rand":
            (bound,) = struct.unpack("<i", mu.mem_read(mu.reg_read(UC_X86_REG_ESP) + 4, 4))
            assert bound == 100, bound
            value = self.rolls.pop(0)
        elif name == "choose":
            value = self.pick
        elif name == "population":
            value = 1 if self.room else 0
        self.events.append((name,))
        sp = mu.reg_read(UC_X86_REG_ESP)
        (ret,) = struct.unpack("<I", mu.mem_read(sp, 4))
        mu.reg_write(UC_X86_REG_EAX, value)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + pops)
        mu.reg_write(UC_X86_REG_EIP, ret)

    def turn(self, *, pick: int, roll: int = 50, age: int = ADULT, room: bool = True) -> list[tuple]:
        """One job turn: the villager (adult unless `age` says otherwise, healthy, not sick or pregnant) whose
        chooser answers `pick`, with the RNG answering `roll`.  The events, in order."""
        mu, g = self.mu, self.g
        mu.mem_write(OBJ, bytes(0x10000))
        mu.mem_write(ARRAY, bytes(0x100000))
        record = self._record()
        if g["arg"] == "object":
            mu.mem_write(OBJ + 0x1B88, struct.pack("<I", record))
        elif g["arg"] == "index":
            mu.mem_write(OBJ + 4, struct.pack("<I", ARRAY))
        mu.mem_write(record + g["age"], struct.pack("<i", age))
        mu.mem_write(record + g["health"], struct.pack("<i", 100))
        self.pick, self.rolls, self.room, self.events = pick, [roll], room, []
        sp = STACK_TOP - 0x1000
        if g["arg"] == "index":
            sp -= 4
            mu.mem_write(sp, struct.pack("<I", INDEX))
        elif g["arg"] == "record":
            sp -= 4
            mu.mem_write(sp, struct.pack("<I", record))
        sp -= 4
        mu.mem_write(sp, struct.pack("<I", SENTINEL))
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.reg_write(UC_X86_REG_ECX, OBJ)
        mu.emu_start(g["worker"], 0xFFFFFFFF, count=100_000)
        if self.events[-1] == ("returned",):
            # The worker returned to its caller with its own arguments popped.
            assert mu.reg_read(UC_X86_REG_ESP) == STACK_TOP - 0x1000, hex(mu.reg_read(UC_X86_REG_ESP))
        return self.events


def tries(game: str, birth_control: bool, **kw) -> int:
    """Over 100 job turns whose chooser picks Children, with the RNG answering 0 to 99 once each, how many go on to
    the embrace (queued and run)."""
    worker = Worker(game, rendered(game, birth_control))
    count = 0
    for roll in range(100):
        events = worker.turn(pick=G[game]["children"], roll=roll, **kw)
        if ("embrace",) in events:
            assert events[events.index(("embrace",)) + 1] == ("run",), events
            count += 1
    return count


@unittest.skipUnless(STOCK_PRESENT, "the stock executables (research/stock-executables) are gitignored and absent")
class BirthControlCatchUpTests(unittest.TestCase):
    def test_the_rows_exist_in_all_five_games_and_each_owns_the_gate_byte(self) -> None:
        catalog = {p.id: p for p in load_fun_patches()}
        for game in G:
            with self.subTest(game=game):
                feature = catalog[_feature(game)]
                self.assertEqual(feature.name, "Birth Control")
                edit = [p for p in feature.raw["patches"] if p["before"] == "83F805"]
                self.assertEqual(len(edit), 1)
                self.assertEqual(edit[0]["after"], "83F863")
                stock = STOCK[game].read_bytes()
                offset = int(edit[0]["offset"], 0)
                self.assertEqual(offset, _file_offset(stock, G[game]["site"]))
                # cmp eax,5 ; jg -- right after push 100 ; call rand ; add esp,4
                self.assertEqual(stock[offset - 10:offset - 8], bytes.fromhex("6A64"))
                self.assertEqual(stock[offset - 3:offset + 3], bytes.fromhex("83C40483F805"))
                self.assertIn(stock[offset + 3], (0x7F, 0x0F))
                self.assertIn("**While catching up (time away and Time Warp)", feature.description)

    def test_stock_tries_on_6_job_turns_in_100(self) -> None:
        for game in G:
            with self.subTest(game=game):
                self.assertEqual(tries(game, False), 6)

    def test_birth_control_tries_on_every_job_turn_whose_pick_is_children(self) -> None:
        for game in G:
            with self.subTest(game=game):
                self.assertEqual(tries(game, True), 100)

    def test_other_picks_leave_for_their_own_job_unchanged(self) -> None:
        for game in G:
            with self.subTest(game=game):
                stock = Worker(game, rendered(game, False)).turn(pick=G[game]["other"])
                patched = Worker(game, rendered(game, True)).turn(pick=G[game]["other"])
                self.assertEqual(stock, patched)
                self.assertNotIn(("rand",), patched)
                self.assertNotIn(("embrace",), patched)

    def test_children_get_no_job_turn_at_all(self) -> None:
        for game in G:
            with self.subTest(game=game):
                for birth_control in (False, True):
                    events = Worker(game, rendered(game, birth_control)).turn(
                        pick=G[game]["children"], roll=0, age=CHILD)
                    self.assertNotIn(("choose",), events)
                    self.assertNotIn(("embrace",), events)

    def test_new_believers_population_limit_still_stops_the_try(self) -> None:
        self.assertEqual(tries("vv5", True, room=False), 0)
        self.assertEqual(tries("vv5", False, room=False), 0)

    def test_the_conception_roll_and_everything_after_the_gate_are_unchanged(self) -> None:
        catalog = {p.id: p for p in load_fun_patches()}
        for game in G:
            stock = STOCK[game].read_bytes()
            off = _file_offset(stock, G[game]["site"])
            # The bytes Birth Control already owned before the catch-up edit (A New Home to The Secret City: its
            # partner-age and chooser rules, some inside the embrace code); none in The Tree of Life / New Believers.
            owned = set()
            for edit in catalog[_feature(game)].raw["patches"]:
                start = int(edit["offset"], 0)
                if start != off:
                    owned.update(range(start, start + len(edit["before"]) // 2))
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    patched, without = rendered(game, True, mode), rendered(game, False, mode)
                    self.assertEqual(patched[off:off + 3], bytes.fromhex("83F863"))
                    lo, hi = CONCEPTION[game]
                    a, b = _file_offset(stock, lo), _file_offset(stock, hi)
                    changed = {a + i for i in range(b - a) if patched[a + i] != without[a + i]}
                    self.assertLessEqual(changed, owned)
                    # In the worker only that one byte differs from the render without Birth Control.
                    w = _file_offset(stock, G[game]["worker"])
                    end = _file_offset(stock, G[game]["end"])
                    diff = [w + i for i in range(end - w) if patched[w + i] != without[w + i]]
                    self.assertEqual(diff, [off + 2])

    def test_with_the_row_off_the_gate_is_stock(self) -> None:
        for game in G:
            with self.subTest(game=game):
                stock = STOCK[game].read_bytes()
                off = _file_offset(stock, G[game]["site"])
                self.assertEqual(rendered(game, False)[off:off + 3], bytes.fromhex("83F805"))


if __name__ == "__main__":
    unittest.main()
