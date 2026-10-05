"""Every "How:" path of the Arrived records, RUN in the executables the patcher publishes.

"VVFP Cause of Death.dll" tells how a villager came by return addresses read
at fixed places in the stack at the game's villager creators
(native/vvfp_cause_of_death/cod_arrival_sites.inc).  Each marker is checked
here by running the rendered executable -- Owner's Defaults in Immediate
Fixed mode, with and without 256 Villagers (Experimental) in The Secret City
to New Believers, and the other two modes with nothing ticked -- from the
marker's own call down to the creator's hook, and reading the slot there.

The owner's v1.35.58 live pass found two patcher bugs these cover:

* A New Home and The Lost Children: an existing village's villagers got
  "How: Founder" records at its first save.  The new-village seeding also
  runs at the startup scan (and for the no-save-yet default), ahead of the
  load that overwrites what it made, and those creations were read as
  founders.  The seeding's own caller decides now, as it always did in The
  Secret City: every caller of the seeding is classified.
* The Secret City: the picked "Another One of Those Barrels" and "The Canoe
  from the Other Side" got "How: unknown".  The Story / Cheat Upgrades
  companion's outcome scope calls hold those very calls, and while one runs
  its own return address is in the slot; that companion now says whose the
  slot is (VvfpStoryCallerReturn), run here in its test build.

The emulation (scratch-built, below) executes the marker's call and every
function on a direct-call path from it to the creator for real; every other
call is skipped, popping what the callee's own `ret n` pops, so the frames
on the path are exactly the game's.  Memory nobody set up reads as zero (the
stack as garbage), the game's rand cycles through every value, and the
creator returns, by the stack pointer it was entered with, as soon as its
hook has been reached.
"""
from __future__ import annotations

import functools
import os
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UC_MODE_32, UC_PROT_ALL, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
        UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

STOCK = ROOT / "research" / "stock-executables"
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
          5: "New Believers"}
SITES = ROOT / "native" / "vvfp_cause_of_death" / "cod_arrival_sites.inc"
STORY_TEST_DLL = Path(os.environ.get(
    "VVFP_STORY_TEST_DLL", ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"))
RAND = {1: 0x402F10, 2: 0x4031A0, 3: 0x4032D0, 4: 0x4036D0, 5: 0x403660}
# Each creator hook (cod_roster_sites.inc) and the creator it sits in.
CREATOR = {
    0x43C39B: 0x43C350, 0x43C888: 0x43C840,
    0x44C84F: 0x44C600, 0x44CF04: 0x44CEC0,
    0x456326: 0x456120, 0x4566EF: 0x4566E0,
    0x45F175: 0x45EF10, 0x45D9BB: 0x45D9B0,
    0x468411: 0x4681F0, 0x4687FE: 0x4687F0,
}
KIND = {"MARK_BIRTH": 1, "MARK_FOUNDER": 2, "MARK_EVENT": 3, "MARK_TEMPORARY": 4}
STACK = 0x0F000000
HEAP = 0x30000000


def have_stock() -> bool:
    return all((STOCK / f"Virtual Villagers - {t}.exe").is_file() for t in TITLES.values())


needs_tools = unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")
needs_stock = unittest.skipUnless(have_stock(), "the stock executables are not in this checkout")


# ---- The marker tables, as the compiler sees them --------------------------------

def _expand(text: str, macros: dict) -> str:
    for _ in range(4):
        for name, (params, body) in macros.items():
            if params is None:
                text = re.sub(rf"\b{name}\b(?!\()", body, text)
            else:
                def call(m, params=params, body=body):
                    args = [a.strip() for a in m.group(1).split(",")]
                    out = body
                    for p, a in zip(params, args):
                        out = re.sub(rf"\(?\b{p}\b\)?", a, out)
                    return out
                text = re.sub(rf"\b{name}\(([^()]*)\)", call, text)
    return text


def markers(game: int) -> list[dict]:
    """The rows of MARKERS_VV<game>, macros expanded."""
    source = SITES.read_text(encoding="utf-8").replace("\\\n", " ")
    macros = {}
    for m in re.finditer(r"^#define (\w+)(\(([^)]*)\))? (.+)$", source, re.M):
        if m.group(1).startswith("MARK"):
            continue
        params = [p.strip() for p in m.group(3).split(",")] if m.group(2) else None
        macros[m.group(1)] = (params, m.group(4).strip())
    head = f"static const struct arrival_marker MARKERS_VV{game}[] = {{"
    table = source[source.index(head) + len(head):]
    table = _expand(table[:table.index("\n};")], macros)
    rows = []
    for row in re.findall(r"\{([^{}]*)\}", table):
        f = [x.strip() for x in row.split(",", 6)]
        num = [int(x.rstrip("u"), 16) if x.startswith("0x") else int(x) for x in f[:5]]
        rows.append(dict(site=num[0], offset=num[1], value=num[2], need_offset=num[3], need_value=num[4],
                         kind=KIND[f[5]], label=None if f[6] == "NULL" else f[6].strip('"')))
    return rows


# ---- The executables the patcher publishes ---------------------------------------

@functools.lru_cache(maxsize=None)
def _builds():
    return {b.id: b for b in patcher.load_builds()}


@functools.lru_cache(maxsize=None)
def owners_defaults(game: int) -> tuple[str, ...]:
    from vv_fun_patcher_gui import owners_default_fun_patch_selection
    ids = [p.id for p in patcher.load_public_fun_patches()
           if p.game_id == f"vv{game}" and owners_default_fun_patch_selection(p.id)]
    return tuple(patcher.resolve_fun_patch_ids(ids, game_id=f"vv{game}"))


def renders(game: int):
    """(label, mode, patch ids) of each build checked."""
    full = owners_defaults(game)
    big = f"vv{game}_population_256"
    yield "Owner's Defaults, Immediate Fixed", "immediate_fixed", full
    if game >= 3:
        assert big in full, "Owner's Defaults ticks 256 Villagers (Experimental)"
        yield "Owner's Defaults without 256, Immediate Fixed", "immediate_fixed", tuple(
            patcher.resolve_fun_patch_ids([i for i in full if i != big], game_id=f"vv{game}"))
    yield "nothing ticked, Collection Progression", "collection_progression", ()
    yield "nothing ticked, Stock", "stock", ()


@functools.lru_cache(maxsize=None)
def render(game: int, mode: str, ids: tuple[str, ...]) -> bytes:
    data, _ = patcher.render_patched_bytes(STOCK / f"Virtual Villagers - {TITLES[game]}.exe",
                                           _builds()[f"vv{game}"], mode, list(ids))
    return bytes(data)


# ---- The emulation ---------------------------------------------------------------

class Image:
    def __init__(self, data: bytes):
        pe = pefile.PE(data=data, fast_load=True)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        self.img = bytes(pe.get_memory_mapped_image()[: self.size])
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self._pops: dict[int, int] = {}
        self._callees: dict[int, set] = {}

    def code(self, va: int, n: int = 16) -> bytes:
        return self.img[va - self.base: va - self.base + n]

    def inside(self, va: int) -> bool:
        return self.base <= va < self.base + self.size

    def call_target(self, va: int) -> int | None:
        b = self.code(va, 5)
        if b[:1] == b"\xE8":
            return (va + 5 + struct.unpack("<i", b[1:5])[0]) & 0xFFFFFFFF
        return None

    def _walk(self, entry: int):
        """Every instruction of the function at `entry`, its jumps followed."""
        seen = set()
        work = [entry]
        while work and len(seen) < 20000:
            va = work.pop()
            if va in seen or not self.inside(va):
                continue
            for ins in self.md.disasm(self.code(va, 0x400), va):
                if ins.address in seen:
                    break
                seen.add(ins.address)
                yield ins
                if ins.mnemonic == "ret":
                    break
                if ins.mnemonic.startswith("j") and ins.op_str.startswith("0x"):
                    work.append(int(ins.op_str, 16))
                if ins.mnemonic == "jmp":
                    break

    def callees(self, entry: int) -> set:
        if entry not in self._callees:
            self._callees[entry] = {int(i.op_str, 16) for i in self._walk(entry)
                                    if i.mnemonic == "call" and i.op_str.startswith("0x")}
        return self._callees[entry]

    def callee_pop(self, target: int) -> int:
        """What the function at `target` pops on return: its `ret n`."""
        if target not in self._pops:
            pops = {int(i.op_str, 16) if i.op_str else 0 for i in self._walk(target) if i.mnemonic == "ret"}
            if len(pops) != 1:
                raise AssertionError(f"{target:#x} returns with {sorted(pops)}")
            self._pops[target] = pops.pop()
        return self._pops[target]

    def chain(self, start: int, creator: int, depth: int = 4) -> set:
        """Every function on a direct-call path of at most `depth` calls from
        `start` to `creator`."""
        found: set = set()

        def walk(f, path):
            if f == creator:
                found.update(path + [f])
            elif len(path) < depth:
                for g in self.callees(f):
                    if g not in path:
                        walk(g, path + [f])
        walk(start, [])
        return found


SAVED = None


def run_to_hook(image: Image, game: int, start: int, creator: int, hook: int, *, turn: int = 0,
                limit: int = 3_000_000) -> list[bytes]:
    """Execute the call at `start` until it returns; the 0x400 bytes above
    esp at each arrival at `hook`."""
    saved_regs = (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(image.base, image.size, UC_PROT_ALL)
    uc.mem_write(image.base, image.img)
    uc.mem_map(STACK, 0x100000)
    uc.mem_write(STACK, b"\x5A" * 0x100000)

    def unmapped(uc, access, address, size, value, user):
        uc.mem_map(address & ~0xFFF, 0x1000)
        return True
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, unmapped)
    first = image.call_target(start)
    follow = image.chain(first, creator) | {first}
    pop_creator = image.callee_pop(creator)
    stacks: list[bytes] = []
    entries: list = []
    counter = [turn]
    error: list[str] = []

    def code(uc, address, size, user):
        if not image.inside(address):
            error.append(f"left the image at {address:#x}")
            uc.emu_stop()
            return
        if address == creator:
            entries.append((uc.reg_read(UC_X86_REG_ESP), [uc.reg_read(r) for r in saved_regs]))
        if address == hook:
            esp = uc.reg_read(UC_X86_REG_ESP)
            stacks.append(bytes(uc.mem_read(esp, 0x400)))
            entry, regs = entries.pop()
            for r, v in zip(saved_regs, regs):
                uc.reg_write(r, v)
            back = struct.unpack("<I", uc.mem_read(entry, 4))[0]
            uc.reg_write(UC_X86_REG_ESP, entry + 4 + pop_creator)
            uc.reg_write(UC_X86_REG_EAX, 0)
            uc.reg_write(UC_X86_REG_EIP, back)
            return
        b = image.code(address, 2)
        if b[:1] == b"\xE8":
            target = image.call_target(address)
            if address == start or target in follow:
                return
            esp = uc.reg_read(UC_X86_REG_ESP)
            if target == RAND[game]:
                bound = struct.unpack("<I", uc.mem_read(esp, 4))[0] or 1
                counter[0] += 1
                result = counter[0] % bound if bound < 0x10000 else counter[0]
            else:
                result = HEAP + 0x100000
            uc.reg_write(UC_X86_REG_ESP, esp + image.callee_pop(target))
            uc.reg_write(UC_X86_REG_EAX, result)
            uc.reg_write(UC_X86_REG_EIP, address + 5)
        elif b[:1] == b"\xFF" and (b[1] >> 3) & 7 == 2 and address != start:
            error.append(f"an indirect call at {address:#x}")
            uc.emu_stop()
    uc.hook_add(UC_HOOK_CODE, code)
    uc.reg_write(UC_X86_REG_ESP, STACK + 0x80000)
    uc.reg_write(UC_X86_REG_ECX, HEAP)
    end = start + (5 if image.code(start, 1) == b"\xE8" else 3)
    uc.emu_start(start, end, count=limit)
    if error:
        raise AssertionError(f"{start:#x}: {error[0]} ({len(stacks)} hook arrivals)")
    if uc.reg_read(UC_X86_REG_EIP) != end:
        raise AssertionError(f"{start:#x}: stopped at {uc.reg_read(UC_X86_REG_EIP):#x}")
    return stacks


def word(stack: bytes, offset: int) -> int:
    return struct.unpack_from("<I", stack, offset)[0]


def the_call(image: Image, value: int) -> int:
    """The call whose return address `value` is: `call rel32` (E8), the
    dispatcher's `call [edx+0x2C]` (FF 52 2C), or a slot guard's six-byte
    `call <guard>; nop`, which hands the creator the address past the nop."""
    if image.code(value - 5, 1) == b"\xE8":
        return value - 5
    if image.code(value - 3, 3) == b"\xFF\x52\x2C":
        return value - 3
    if image.code(value - 6, 1) == b"\xE8" and image.code(value - 1, 1) == b"\x90":
        return value - 6
    raise AssertionError(f"{value:#x} follows no call")


# ---- The checks ------------------------------------------------------------------

@needs_tools
@needs_stock
class EveryMarkerHoldsInEveryPublishedBuild(unittest.TestCase):
    def check(self, game: int):
        rows = markers(game)
        self.assertGreater(len(rows), 5)
        for label, mode, ids in renders(game):
            image = Image(render(game, mode, ids))
            for m in rows:
                if image.code(m["value"] - 3, 3) == b"\xFF\x52\x2C":
                    continue     # the dispatcher's own return: reached through a tail jmp (checked by its row)
                with self.subTest(build=label, marker=hex(m["value"]), need=hex(m["need_value"])):
                    start = the_call(image, m["value"])
                    creator = CREATOR[m["site"]]
                    seen = []
                    for turn in range(6):        # another rand sequence reaches another branch
                        for stack in run_to_hook(image, game, start, creator, m["site"], turn=turn):
                            seen.append((word(stack, m["offset"]),
                                         word(stack, m["need_offset"]) if m["need_offset"] else 0))
                        if (m["value"], m["need_value"]) in seen:
                            break
                    self.assertIn((m["value"], m["need_value"]), seen,
                                  f"VV{game} {label}: the marker {m['value']:#x} (+{m['offset']:#x}) / "
                                  f"{m['need_value']:#x} (+{m['need_offset']:#x}) is never what the creator "
                                  f"hook {m['site']:#x} reads; it read {[(hex(a), hex(b)) for a, b in seen[:8]]}")

    def test_a_new_home(self):
        self.check(1)

    def test_the_lost_children(self):
        self.check(2)

    def test_the_secret_city(self):
        self.check(3)

    def test_the_tree_of_life(self):
        self.check(4)

    def test_new_believers(self):
        self.check(5)


@needs_tools
@needs_stock
class EverySeedingCallerIsClassified(unittest.TestCase):
    """The new-village seeding of A New Home (0x41C000), The Lost Children
    (0x424C80) and The Secret City (0x427F70): every call of it in the
    executable is either a founder's path (a new village) or a temporary one
    (a load follows and overwrites what it made), so an existing village's
    villagers are never read as founders (the owner's v1.35.58 live pass)."""

    SEEDERS = {1: 0x41C000, 2: 0x424C80, 3: 0x427F70}

    def test_every_caller_of_the_seeding(self):
        for game, seeder in self.SEEDERS.items():
            image = Image(render(game, "stock", ()))
            callers = set()
            text = image.img
            for rva in range(0x1000, len(text) - 5):
                if text[rva] == 0xE8 and image.call_target(image.base + rva) == seeder:
                    callers.add(image.base + rva + 5)
            rows = markers(game)
            kinds = {m["value"]: m["kind"] for m in rows if m["kind"] in (KIND["MARK_FOUNDER"], KIND["MARK_TEMPORARY"])}
            with self.subTest(game=game):
                self.assertEqual(len(callers), 5 if game < 3 else 6)
                self.assertEqual(sorted(callers), sorted(c for c in kinds if c in callers),
                                 f"VV{game}: a caller of the seeding with no marker")
                founders = sorted(c for c in callers if kinds[c] == KIND["MARK_FOUNDER"])
                self.assertEqual(len(founders), 3, f"VV{game}: new tribe, first naming, Start Over")
                seeds = {m["need_value"] for m in rows if m["value"] in callers}
                calls = {image.base + r + 5 for r in range(0x1000, len(text) - 5)
                         if text[r] == 0xE8 and image.call_target(image.base + r) in (
                             CREATOR[next(iter({m["site"] for m in rows if m["value"] in callers}))],
                             0x45F0B0)
                         and seeder <= image.base + r < seeder + 0x800}
                self.assertEqual(seeds, calls, f"VV{game}: every seeding call, under every caller")


@needs_tools
@needs_stock
@unittest.skipUnless(STORY_TEST_DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")
class AStoryScopeCallNamesTheGamesReturn(unittest.TestCase):
    """The Story / Cheat Upgrades companion installed in the game, as Owner's
    Defaults ships it: a marker whose call is one of its outcome scope calls
    (The Secret City's barrels and canoe and amber vial, A New Home's
    Mysterious Face) finds the companion's own return address in its slot
    while the creator runs, and VvfpStoryCallerReturn gives the game's."""

    def test_the_scope_calls_on_marker_paths(self):
        from story_emulator import Process, STACK_TOP
        scoped = {1: [0x41974F], 3: [0x415355, 0x415398, 0x4153DB, 0x414DB4, 0x417840]}
        for game, values in scoped.items():
            rows = {m["value"]: m for m in markers(game)}
            for label, mode, ids in list(renders(game))[:2]:
                data = render(game, mode, ids)
                for value in values:
                    m = rows[value]
                    with self.subTest(game=game, build=label, marker=hex(value)):
                        proc = Process(data, STORY_TEST_DLL)
                        self.assertEqual(proc.export("VvfpStoryInstall", game), 1)
                        image = Image(data)
                        start = value - 5
                        self.assertNotEqual(image.call_target(start), None)
                        rewritten = struct.unpack("<i", proc.read(start + 1, 4))[0] + start + 5
                        self.assertTrue(proc.dll_base <= rewritten < proc.dll_base + proc.dll_size,
                                        f"{start:#x} is not one of the companion's scope calls")
                        stub = rewritten
                        # Run the companion's scope stub as the game's call
                        # reaches it, up to the original callee's entry,
                        # then the callee's frames to the creator's hook.
                        esp = STACK_TOP - 0x8000
                        proc.write(esp - 0x400, b"\x5A" * 0x400)
                        proc.put32(esp - 4, value)       # the game's call pushed its return address
                        proc.set_reg("esp", esp - 4)
                        proc.set_reg("ecx", HEAP)
                        callee = image.call_target(start)
                        proc.run(stub, callee)
                        slot = proc.reg("esp")
                        held = proc.u32(slot)
                        self.assertNotEqual(held, value, "the scope call holds its own return address there")
                        self.assertTrue(proc.dll_base <= held < proc.dll_base + proc.dll_size)
                        # The slot is m["offset"] above the hook's esp once the
                        # creator's hook is reached (EveryMarkerHoldsInEveryPublishedBuild);
                        # the companion names the game's address for that slot.
                        saved = proc.reg("esp")
                        self.assertEqual(proc.export("VvfpStoryCallerReturn", slot), value)
                        self.assertEqual(proc.export("VvfpStoryCallerReturn", slot + 4), 0,
                                         "never for a slot no scope call took")
                        proc.set_reg("esp", saved)
                        self.assertEqual(proc.u32(slot), held, "asking changes nothing")


if __name__ == "__main__":
    unittest.main()
