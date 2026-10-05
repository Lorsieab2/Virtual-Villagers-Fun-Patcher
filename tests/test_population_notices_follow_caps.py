"""Every population-limit notice and refusal follows the cap the mode enforces.

The owner, playing A New Home at 254 of 256: "I got a notification about max
population when I was at like 115 villagers." The notice was the world tick's
(0x42E900) "Congratulations! Your village reached its maximum sustainable
population!" (string 315). Its test was the stock `cmp eax, 0x5A` -- 90, A New
Home's stock cap -- and no population mode touched it: the modes only patch the
growth predicate 0x43A1A0. The notice is one-shot per village (flag byte +0x16C,
saved with the village), so it fired at the first tick that found 90 or more,
which for a village that grew while the game was closed is whatever the
load-time catch-up left it at -- 115 here.

The audit (docs/max-population-research.md, "Population notices and refusals
follow the cap") found every place the five games compare a population
against a limit. Three used the stock number and not the cap; the Collection
Progression and Immediate Fixed variants now rewrite them:

  VV1 0x42F1EE  the maximum-population notice      stock 90 -> 256
  VV1 0x43DE45  the dragged pair's refusal reason   stock 90 -> 256
  VV2 0x44FAF9  the dragged pair's refusal reason   stock 90 -> 256 (the
                predicate 0x44B310 then decides, as no VV2 cap exceeds 256)

Every other notice already asks the game's own predicate, which each mode (and
256 Villagers) patches, so it follows the cap by construction. This file proves
both halves by EXECUTING the rendered bytes, per game x mode x build x
collection state, with the population counter, the collection/magic queries and
the hut queries stubbed:

  * a notice fires at the effective cap and never below it;
  * the refusal reason is shown exactly while the predicate would still let the
    village grow (so it is never silent below the cap) and the cap the notice
    uses is the cap the predicate enforces;
  * stock mode keeps the stock thresholds byte for byte.

Skipped (not failed) without unicorn or the stock executables (CI has neither).
"""
from __future__ import annotations

import functools
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

try:  # optional dependency
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc, UcError
    from unicorn.x86_const import (
        UC_X86_REG_EAX,
        UC_X86_REG_ECX,
        UC_X86_REG_EIP,
        UC_X86_REG_ESI,
        UC_X86_REG_ESP,
    )

    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

STOCK_DIR = ROOT / "research" / "stock-executables"
MODES = ("stock", "collection_progression", "immediate_fixed")
EXPANDED = ("collection_progression", "immediate_fixed")

# The rows this change adds: (game, file offset, stock bytes, expanded bytes).
NOTICE_ROWS = (
    ("vv1", 0x2F1EE, "83F85A7C20", "84E4742190"),
    ("vv1", 0x3DE45, "837C24185A7D3C", "807C241900753C"),
    ("vv2", 0x4FAF9, "837C24185A7D38", "807C2419007538"),
)

POP_256 = {"vv3": "vv3_population_256", "vv4": "vv4_population_256", "vv5": "vv5_population_256"}

# Collection bonus states each game can reach, as the set of completed
# collection ids the predicate asks about. A stock ladder of +5 per collection,
# 20 -> 25 for all four (VV2-VV4) and 10 -> 15 for both (VV5).
COLLECTION_IDS = {
    "vv2": (0x00, 0x0C, 0x18, 0x24),
    "vv3": (0x34, 0x40, 0x4C, 0x58),
    "vv4": (0x46, 0x52, 0x5E, 0x6A),
    "vv5": (0x68, 0x50),
}


def bonus_of(game: str, done: int) -> int:
    ids = COLLECTION_IDS[game]
    bonus = 5 * done
    if done == len(ids) and len(ids) == 4:
        bonus = 25
    if done == len(ids) and len(ids) == 2:
        bonus = 15
    return bonus


def expected_cap(game: str, mode: str, pop256: bool, done: int, magic: bool) -> int:
    """The cap the selected mode enforces (docs/max-population-research.md and
    the 256 Villagers manifests)."""
    bonus = 0 if game == "vv1" else bonus_of(game, done) + (10 if game == "vv3" and magic else 0)
    if mode == "stock":
        return 90 + bonus
    if game in ("vv1", "vv2"):
        return 256 if mode == "immediate_fixed" else (256 if game == "vv1" else 231 + bonus)
    slots = 256 if pop256 else 150
    if mode == "immediate_fixed":
        return slots
    base = {"vv3": (115, 221), "vv4": (125, 231), "vv5": (135, 241)}[game][pop256]
    return base + bonus


@functools.lru_cache(maxsize=None)
def build_of(game: str):
    return next(b for b in patcher.load_builds() if b.id == game)


def stock_path(game: str) -> Path:
    return STOCK_DIR / build_of(game).input_name


@functools.lru_cache(maxsize=None)
def catalog() -> dict:
    return {p.id: p for p in patcher.load_fun_patches()}


def closure(feature_id: str, into: list[str] | None = None) -> list[str]:
    into = [] if into is None else into
    for dependency in catalog()[feature_id].raw.get("dependencies") or []:
        closure(dependency, into)
    if feature_id not in into:
        into.append(feature_id)
    return into


def public_ids(game: str) -> list[str]:
    out = []
    for p in patcher.load_fun_patches():
        r = p.raw
        if (
            p.game_id == game
            and not r.get("catalog_hidden")
            and r.get("catalog_enabled", True)
            and r.get("enabled", True)
            and p.id not in POP_256.values()
        ):
            out.append(p.id)
    return out


@functools.lru_cache(maxsize=None)
def render(game: str, mode: str, ids: tuple[str, ...]) -> bytes:
    data, _ = patcher.render_patched_bytes(stock_path(game), build_of(game), mode, list(ids))
    return bytes(data)


def builds_for(game: str) -> list[tuple[str, tuple[str, ...], bool]]:
    """(label, selection, is_256) for the bare mode, everything public, and --
    VV3-VV5 -- 256 Villagers (Experimental) alone and with everything."""
    out = [("bare", (), False), ("all public", tuple(public_ids(game)), False)]
    if game in POP_256:
        out.append(("256", tuple(closure(POP_256[game])), True))
        out.append(("256 + all public", tuple(dict.fromkeys(public_ids(game) + closure(POP_256[game]))), True))
    return out


# ---------------------------------------------------------------------------
# Emulator
# ---------------------------------------------------------------------------

FAKE = 0x20000000  # fake objects (the handler/tick `this` and the village)
FAKE_SIZE = 0x01000000
STACK = 0x30000000
STACK_SIZE = 0x00100000
SENTINEL = 0x0BADF00D


class Emu:
    """The rendered image mapped at its base, with a scratch object area."""

    def __init__(self, data: bytes):
        pe = pefile.PE(data=data)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(self.base, size)
        self.uc.mem_write(self.base, data[: pe.OPTIONAL_HEADER.SizeOfHeaders])
        for s in pe.sections:
            raw = s.get_data()[: max(s.Misc_VirtualSize, s.SizeOfRawData)]
            self.uc.mem_write(self.base + s.VirtualAddress, raw)
        self.uc.mem_map(FAKE, FAKE_SIZE)
        self.uc.mem_map(STACK, STACK_SIZE)
        self.uc.mem_map(SENTINEL & ~0xFFF, 0x1000)
        self.stubs: dict[int, tuple[int, object]] = {}
        self.uc.hook_add(UC_HOOK_CODE, self._hook)
        self.stop_at: set[int] = set()
        self.stopped_at: int | None = None

    def stub(self, address: int, arg_bytes: int, fn) -> None:
        """Replace the function at `address`: fn(first stack arg) -> eax."""
        self.stubs[address] = (arg_bytes, fn)

    def _hook(self, uc, address, size, _user):
        if address in self.stop_at:
            self.stopped_at = address
            uc.emu_stop()
            return
        if address in self.stubs:
            arg_bytes, fn = self.stubs[address]
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = int.from_bytes(uc.mem_read(esp, 4), "little")
            arg = int.from_bytes(uc.mem_read(esp + 4, 4), "little") if arg_bytes else None
            uc.reg_write(UC_X86_REG_EAX, int(fn(arg)) & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + arg_bytes)
            uc.reg_write(UC_X86_REG_EIP, ret)

    def run(self, start: int, stops: set[int], regs: dict[int, int]) -> int:
        self.stop_at = set(stops)
        self.stopped_at = None
        esp = STACK + STACK_SIZE - 0x1000
        self.uc.mem_write(esp, SENTINEL.to_bytes(4, "little"))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        for reg, value in regs.items():
            self.uc.reg_write(reg, value)
        try:
            self.uc.emu_start(start, 0xFFFFFFF0, count=20000)
        except UcError as exc:  # pragma: no cover - a failure explains itself
            eip = self.uc.reg_read(UC_X86_REG_EIP)
            raise AssertionError(f"emulation fault at 0x{eip:X}: {exc}") from exc
        if self.stopped_at is None:
            eip = self.uc.reg_read(UC_X86_REG_EIP)
            raise AssertionError(f"ran off the expected paths (eip 0x{eip:X})")
        return self.stopped_at

    def write32(self, address: int, value: int) -> None:
        self.uc.mem_write(address, (value & 0xFFFFFFFF).to_bytes(4, "little"))

    def write8(self, address: int, value: int) -> None:
        self.uc.mem_write(address, bytes([value & 0xFF]))


def stub_game(emu: Emu, game: str, population: dict, done: int, magic: bool) -> None:
    """Stub the predicate's queries: the counter returns population['n'], the
    first `done` collections are complete, Magic is level 3 or 0, every hut is
    built. Physical demand (VV5's mode helper) is the same population."""
    completed = set(COLLECTION_IDS.get(game, ())[:done])
    count = lambda _arg: population["n"]  # noqa: E731
    if game == "vv1":
        emu.stub(0x41CF90, 0, count)
    elif game == "vv2":
        emu.stub(0x425860, 0, count)
        emu.stub(0x426120, 4, lambda first: 1 if first in completed else 0)
    elif game == "vv3":
        emu.stub(0x45E8F0, 0, count)
        emu.stub(0x42DE40, 4, lambda tech: 1 if tech in completed else 0)
        emu.stub(0x426FC0, 4, lambda _f: 3 if magic else 0)
        emu.stub(0x4321F0, 4, lambda _h: 1)
    elif game == "vv4":
        emu.stub(0x467610, 0, count)
        emu.stub(0x4143F0, 4, lambda tech: 1 if tech in completed else 0)
        emu.stub(0x438960, 4, lambda _h: 1)
    elif game == "vv5":
        emu.stub(0x4713F0, 0, count)
        emu.stub(0x4944C0, 0, count)  # the modes' physical-demand helper
        emu.stub(0x414690, 4, lambda tech: 1 if tech in completed else 0)
        emu.stub(0x43AE80, 4, lambda _h: 1)


VV1_VILLAGE = FAKE + 0x00800000
VV2_VILLAGE = FAKE + 0x00F00000  # well clear of the handler's +0xE574D4 field


def prepare_vv1(emu: Emu) -> None:
    # Tick/handler objects: [this] and [this+0x3E010] both reach the village,
    # whose three hut flags are set (every housing tier open).
    emu.write32(FAKE, VV1_VILLAGE)
    emu.write32(FAKE + 0x3E010, VV1_VILLAGE)
    for flag in (0x9FE8, 0x9FF0, 0x9FF8):
        emu.write8(VV1_VILLAGE + flag, 1)
    emu.write8(VV1_VILLAGE + 0x16C, 1)  # the notice is armed


def prepare_vv2(emu: Emu) -> None:
    emu.write32(FAKE, VV2_VILLAGE)  # milestone tick: [esi]
    emu.write32(FAKE + 4, FAKE)  # milestone tick: [esi+4] -> predicate's this
    emu.write32(FAKE + 0xE574D4, VV2_VILLAGE)
    for flag in (0x2E818, 0x2E820, 0x2E828):
        emu.write8(VV2_VILLAGE + flag, 1)


# The maximum-population notice in each game: start, notice branch, no notice.
# The population is in the counter (VV1-VV3) or in ESI (VV4, VV5).
NOTICE_SITES = {
    "vv1": (0x42F1E7, 0x42F1F3, 0x42F213),
    "vv2": (0x43C137, 0x43C14F, 0x43C16F),
    "vv3": (0x428D01, 0x428D1E, 0x428D29),
    "vv4": (0x42063C, 0x42064F, 0x420662),
    "vv5": (0x4261F5, 0x426208, 0x426213),
}
# The growth predicate (the cap the mode enforces).
PREDICATES = {"vv1": 0x43A1A0, "vv2": 0x44B310, "vv3": 0x45FE30, "vv4": 0x468350, "vv5": 0x472BD0}
PREDICATE_THIS = {"vv1": FAKE, "vv2": FAKE, "vv3": 0x59E110, "vv4": 0x50E568, "vv5": 0x554148}
# The dragged pair's refusal: start (the stock 90 test), explained, silent.
REFUSAL_SITES = {
    "vv1": (0x43DE45, {0x43DE57, 0x43DE5B}, 0x43DE88),
    "vv2": (0x44FAF9, {0x44FB0B}, 0x44FB38),
}


def notice_fires(emu: Emu, game: str, population: dict, n: int) -> bool:
    population["n"] = n
    start, fired, quiet = NOTICE_SITES[game]
    regs = {UC_X86_REG_ESI: n if game in ("vv4", "vv5") else FAKE}
    return emu.run(start, {fired, quiet}, regs) == fired


def predicate_allows(emu: Emu, game: str, population: dict, n: int) -> bool:
    population["n"] = n
    # Called like the game calls it; it returns to the sentinel.
    emu.run(PREDICATES[game], {SENTINEL}, {UC_X86_REG_ECX: PREDICATE_THIS[game]})
    return (emu.uc.reg_read(UC_X86_REG_EAX) & 0xFF) != 0


def refusal_explained(emu: Emu, game: str, population: dict, n: int) -> bool:
    population["n"] = n
    start, explained, silent = REFUSAL_SITES[game]
    esp = STACK + STACK_SIZE - 0x2000
    # The handler keeps the population it counted at [esp+0x18].
    emu.write32(esp + 0x18, n)
    emu.stop_at = set(explained) | {silent}
    emu.stopped_at = None
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_ESI, FAKE)
    emu.uc.emu_start(start, 0xFFFFFFF0, count=20000)
    assert emu.stopped_at is not None, f"{game} refusal ran off its paths"
    return emu.stopped_at in explained


POPULATIONS = sorted(
    set(range(0, 300, 7))
    | {14, 15, 24, 25, 49, 50, 89, 90, 91, 104, 105, 114, 115, 116, 124, 125, 134, 135}
    | {139, 140, 149, 150, 151, 230, 231, 235, 240, 241, 245, 250, 254, 255, 256, 257, 300}
)


def collection_states(game: str) -> list[tuple[int, bool]]:
    if game == "vv1":
        return [(0, False)]
    states = [(done, False) for done in range(len(COLLECTION_IDS[game]) + 1)]
    if game == "vv3":
        states += [(0, True), (len(COLLECTION_IDS[game]), True)]
    return states


def _have_inputs() -> bool:
    return HAVE_UNICORN and all(stock_path(g).is_file() for g in ("vv1", "vv2", "vv3", "vv4", "vv5"))


class NoticeRowsAreDeclared(unittest.TestCase):
    """Catalog-level: runs everywhere, with no game files."""

    def test_rows_in_the_expanded_variants_only(self):
        data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        games = {g["id"]: g for g in data["games"]}
        for game, offset, before, after in NOTICE_ROWS:
            for mode in MODES:
                rows = [
                    r for r in games[game]["variants"][mode]["patches"]
                    if int(r["offset"], 16) == offset
                ]
                with self.subTest(game=game, mode=mode, offset=hex(offset)):
                    if mode == "stock":
                        self.assertEqual(rows, [], "stock mode keeps the stock threshold")
                    else:
                        self.assertEqual(len(rows), 1)
                        self.assertEqual(rows[0]["before"], before)
                        self.assertEqual(rows[0]["after"], after)


@unittest.skipUnless(_have_inputs(), "needs unicorn and the stock executables")
class NoticesFollowTheCap(unittest.TestCase):
    def test_stock_bytes_are_what_the_rows_guard(self):
        for game, offset, before, _after in NOTICE_ROWS:
            data = stock_path(game).read_bytes()
            self.assertEqual(data[offset:offset + len(before) // 2].hex().upper(), before)

    def test_stock_mode_renders_the_stock_threshold(self):
        for game, offset, before, _after in NOTICE_ROWS:
            for label, ids, _is256 in builds_for(game):
                data = render(game, "stock", ids)
                with self.subTest(game=game, build=label):
                    self.assertEqual(data[offset:offset + len(before) // 2].hex().upper(), before)

    def test_max_population_notice_fires_at_the_effective_cap_and_not_before(self):
        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            for mode in MODES:
                for label, ids, is256 in builds_for(game):
                    # 256 Villagers leaves the stock-mode cap stock.
                    emu = Emu(render(game, mode, ids))
                    population = {"n": 0}
                    if game == "vv1":
                        prepare_vv1(emu)
                    elif game == "vv2":
                        prepare_vv2(emu)
                    for done, magic in collection_states(game):
                        stub_game(emu, game, population, done, magic)
                        cap = expected_cap(game, mode, is256 and mode != "stock", done, magic)
                        for n in POPULATIONS:
                            with self.subTest(game=game, mode=mode, build=label, done=done, magic=magic, n=n):
                                allows = predicate_allows(emu, game, population, n)
                                fires = notice_fires(emu, game, population, n)
                                self.assertEqual(allows, n < cap, f"predicate cap is not {cap}")
                                self.assertEqual(fires, n >= cap, f"notice does not fire exactly at {cap}")

    def test_pair_refusal_is_explained_exactly_below_the_cap(self):
        for game in ("vv1", "vv2"):
            for mode in MODES:
                for label, ids, _is256 in builds_for(game):
                    emu = Emu(render(game, mode, ids))
                    population = {"n": 0}
                    if game == "vv1":
                        prepare_vv1(emu)
                    else:
                        prepare_vv2(emu)
                    for done, magic in collection_states(game):
                        stub_game(emu, game, population, done, magic)
                        cap = expected_cap(game, mode, False, done, magic)
                        # Stock keeps its stock gate: explained only below 90.
                        explained_below = 90 if mode == "stock" else cap
                        for n in POPULATIONS:
                            with self.subTest(game=game, mode=mode, build=label, done=done, n=n):
                                self.assertEqual(
                                    refusal_explained(emu, game, population, n),
                                    n < explained_below,
                                )


if __name__ == "__main__":
    unittest.main()
