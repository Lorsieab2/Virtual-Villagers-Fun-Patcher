"""Emulate every VV1 conception path through the real rendered executable.

The VV1 parentage log finds the father at conception. An earlier design routed
all six calls into the conception routine sub_43BBC0 through stubs that
overwrote an argument it believed was dead, and read the father back at the
success tails. Every static guard passed while it:

  * wrote a record POINTER into the mother's +0x394 on every conception. The
    routine stores its second argument there (0x43BC00/0x43BC04), and delivery
    compares that field with 0xC7 at 0x42EF39 to pick a special child-creation
    path -- so the patch changed the game, and at 0x447238, where the stub
    stored the mother's own index, a mother in slot 199 would have taken it;
  * lost the father on the twins tail (it read a return address), at 0x447238
    (the mother's index) and on 0x447031's fallthrough (his record + 0x348).

So these tests run the actual bytes rather than reading them. For each of the
six call sites, on each branch of the two pairing scans, and for a single,
twin and triplet litter, the caller's code runs from before the father is
loaded, through the call, the routine, the patched tail and the companion
call, back to the caller's return address. The same scenario runs on the stock
executable, and the two must leave the villager array, the game state and the
caller's registers byte-for-byte identical -- the patch may observe the game,
never change it -- while the patched run must hand the companion exactly the
real father's record.

Renders covered: the feature alone (cave in .text at 0x456900), and every
public VV1 patch together (the composed cave in .vv1mc) in each of the three
build modes, which is what players receive.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:  # optional dependencies
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX,
        UC_X86_REG_EBP,
        UC_X86_REG_EBX,
        UC_X86_REG_ECX,
        UC_X86_REG_EDI,
        UC_X86_REG_EDX,
        UC_X86_REG_EIP,
        UC_X86_REG_ESI,
        UC_X86_REG_ESP,
    )

    HAVE_DEPS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_DEPS = False

STOCK = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"

IMAGE_BASE = 0x400000
THIS = 0x10000000  # the villager record array, `this` for sub_43BBC0
STATE = 0x20000000  # the manager at [this+0x3E010]
STACK = 0x30000000
FAKE = 0x40000000  # stand-ins for the three imports and the companion export
STRIDE = 0x3D8
SLOTS = 256

CAPACITY_PREDICATE = 0x43A1A0
RAND = 0x402F10
IAT_GET_MODULE_HANDLE = 0x4570D0
IAT_LOAD_LIBRARY = 0x457010
IAT_GET_PROC_ADDRESS = 0x4570D4
FAKE_GET_MODULE_HANDLE = FAKE + 0x00
FAKE_LOAD_LIBRARY = FAKE + 0x10
FAKE_GET_PROC_ADDRESS = FAKE + 0x20
FAKE_EXPORT = FAKE + 0x30

# The litter rolls inside sub_43BBC0: the first rand(100) < 7 makes twins, and
# then a second rand(100) < 0x19 makes triplets. Both need the manager's
# difficulty at 3 or its +0xA090 flag set, which every scenario sets.
LITTERS = {
    "single": (50,),
    "twins": (3, 80),
    "triplets": (3, 10),
}


def _record(index: int) -> int:
    return THIS + index * STRIDE


def _field_36c(index: int) -> int:
    # Distinct per record, and never 0xC7, so a record whose +0x36C reached
    # the mother's +0x394 is identifiable by value.
    return 0x1000 + index


class _Run:
    def __init__(self) -> None:
        self.exports: list[tuple[int, int, int, int]] = []
        self.records = b""
        self.state = b""
        self.regs: dict[str, int] = {}
        self.stopped_at = 0


def _emulate(image: bytes, entry: int, stop: int, *, stack_slots, regs, rolls,
             genders) -> _Run:
    pe = pefile.PE(data=image, fast_load=True)
    mapped = pe.get_memory_mapped_image(ImageBase=IMAGE_BASE)
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(IMAGE_BASE, (len(mapped) + 0xFFFF) & ~0xFFFF)
    uc.mem_write(IMAGE_BASE, mapped)
    uc.mem_map(THIS, 0x40000 + 0x1000)
    uc.mem_map(STATE, 0x10000)
    uc.mem_map(STACK, 0x10000)
    uc.mem_map(FAKE, 0x1000)
    uc.mem_write(FAKE, b"\xC3" * 0x100)

    def w32(address: int, value: int) -> None:
        uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    for index in range(SLOTS):
        record = _record(index)
        uc.mem_write(record + 0x28, b"\x01")
        w32(record + 0x36C, _field_36c(index))
        w32(record + 0x34C, 0x2000 + index)
        w32(record + 0x350, genders.get(index, 1))
    w32(THIS + 0x3E010, STATE)
    w32(STATE + 0xA2DC, 3)
    uc.mem_write(STATE + 0xA090, b"\x01")

    w32(IAT_GET_MODULE_HANDLE, FAKE_GET_MODULE_HANDLE)
    w32(IAT_LOAD_LIBRARY, FAKE_LOAD_LIBRARY)
    w32(IAT_GET_PROC_ADDRESS, FAKE_GET_PROC_ADDRESS)

    esp = STACK + 0x8000
    for offset in range(0, 0x80, 4):
        w32(esp + offset, 0x5000 + offset)  # distinct markers
    for offset, value in stack_slots.items():
        w32(esp + offset, value)
    uc.reg_write(UC_X86_REG_ESP, esp)
    names = {
        "eax": UC_X86_REG_EAX, "ebx": UC_X86_REG_EBX, "ecx": UC_X86_REG_ECX,
        "edx": UC_X86_REG_EDX, "esi": UC_X86_REG_ESI, "edi": UC_X86_REG_EDI,
        "ebp": UC_X86_REG_EBP,
    }
    for name, value in regs.items():
        uc.reg_write(names[name], value)

    run = _Run()
    queue = list(rolls)

    def code(uc, address, size, _user):
        sp = uc.reg_read(UC_X86_REG_ESP)

        def ret(value: int, popped: int) -> None:
            back = struct.unpack("<I", uc.mem_read(sp, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, value)
            uc.reg_write(UC_X86_REG_ESP, sp + 4 + popped)
            uc.reg_write(UC_X86_REG_EIP, back)

        if address == stop:
            run.stopped_at = address
            uc.emu_stop()
        elif address == CAPACITY_PREDICATE:
            ret(1, 0)
        elif address == RAND:
            ret(queue.pop(0) if queue else 99, 0)
        elif address == FAKE_GET_MODULE_HANDLE:
            ret(0x77000000, 4)
        elif address == FAKE_LOAD_LIBRARY:
            ret(0x77000000, 4)
        elif address == FAKE_GET_PROC_ADDRESS:
            ret(FAKE_EXPORT, 8)
        elif address == FAKE_EXPORT:
            run.exports.append(struct.unpack("<4I", uc.mem_read(sp + 4, 16)))
            ret(1, 16)

    uc.hook_add(UC_HOOK_CODE, code)
    uc.emu_start(entry, 0xFFFFFFFF, count=20000)
    run.records = bytes(uc.mem_read(THIS, SLOTS * STRIDE))
    run.state = bytes(uc.mem_read(STATE, 0x10000))
    run.regs = {name: uc.reg_read(reg) for name, reg in names.items()}
    run.regs["esp"] = uc.reg_read(UC_X86_REG_ESP)
    return run


# ---------------------------------------------------------------------------
# The scenarios, one per conception path, built from the stock caller code.
#
# Each returns (entry, stop, stack_slots, regs, rolls_before, mother, father,
# genders). `rolls_before` are the caller's own rand() results consumed before
# sub_43BBC0 is called; the litter rolls follow them.
# ---------------------------------------------------------------------------

MOTHER = 37
FATHER = 150


def _pairing_site(site: int):
    """0x43DD33 / 0x43DD54 / 0x43DD7B / 0x43DD94 in FUN_0043DAD0.

    Entered at the caller's rand(100) with its `push 0x64` already on the
    stack. After that argument is cleaned up (esp = H), `push edi` makes
    G = H-4, and the four sites read:

        0x43DD33  arg1=[H+0x20] mother index, father record = [H+0x18]
        0x43DD54  arg1=[H+0x20] mother index, father record = [H+0x18]
        0x43DD7B  arg1=ebx mother index,      father record = ebp
        0x43DD94  arg1=ebx mother index,      father record = ebp

    The first rand decides between the two sites of each pair (< 0x32 takes
    the first). The entry is past 0x43DD03, where Birth Control splices, so
    both renders run stock caller code from here on.
    """
    push_64 = {0: 0x64}  # the argument of the rand call being entered
    h = 4  # H relative to the entry esp
    if site in (0x43DD33, 0x43DD54):
        entry, stop = 0x43DD0E, site + 5
        slots = dict(push_64)
        slots[h + 0x10] = 1  # arg3 at 0x43DD33
        slots[h + 0x14] = 1  # arg3 at 0x43DD54
        slots[h + 0x18] = _record(FATHER)
        slots[h + 0x20] = MOTHER
        regs = {"esi": THIS, "ebp": _record(MOTHER), "ebx": 0xB0B, "edi": 7}
        genders = {MOTHER: 2}
    else:
        entry, stop = 0x43DD5E, site + 5
        slots = dict(push_64)
        slots[h + 0x10] = 1
        slots[h + 0x14] = 1
        regs = {"esi": THIS, "ebp": _record(FATHER), "ebx": MOTHER, "edi": 7}
        genders = {FATHER: 1}
    roll = 10 if site in (0x43DD33, 0x43DD7B) else 60
    return entry, stop, slots, regs, (roll,), MOTHER, FATHER, genders


def _scan_site(site: int, a_is_mother: bool):
    """0x447031 (first scan) and 0x447238 (second scan).

    Entered at the gender branch (0x446FE2 / 0x4471E7) with F the scan frame:
        [F+0x10] A's record, [F+0x14] B's index,
        [F+0x18] B's record + 0x348 (the cursor), [F+0x28] A's index.
    `cmp [A+0x350],2 ; jne` -- equal makes A the mother and B the father;
    otherwise B is the mother and A the father.
    """
    entry = 0x446FE2 if site == 0x447031 else 0x4471E7
    a, b = (MOTHER, FATHER) if a_is_mother else (FATHER, MOTHER)
    slots = {
        0x10: _record(a),
        0x14: b,
        0x18: _record(b) + 0x348,
        0x28: a,
    }
    regs = {"esi": THIS, "ebx": 0xB0B, "ebp": 0xE0E, "edi": 7}
    genders = {a: 2 if a_is_mother else 1, b: 1 if a_is_mother else 2}
    return entry, site + 5, slots, regs, (10,), MOTHER, FATHER, genders


def _scenarios():
    for site in (0x43DD33, 0x43DD54, 0x43DD7B, 0x43DD94):
        yield f"{site:#x}", _pairing_site(site)
    for site in (0x447031, 0x447238):
        yield f"{site:#x} A mother (fallthrough)", _scan_site(site, True)
        yield f"{site:#x} B mother (jne taken)", _scan_site(site, False)


_RENDERS: dict[str, bytes] = {}


ALL_MODES = ("stock", "collection_progression", "immediate_fixed")


def _render(label: str) -> bytes:
    """'alone', or a build mode with every public VV1 patch selected."""
    if label not in _RENDERS:
        import vv_fun_patcher as patcher

        builds = {build.id: build for build in patcher.load_builds()}
        if label == "alone":
            ids = ["vv1_write_parentage_log"]
        else:
            ids = [
                patch.id
                for patch in patcher.load_public_fun_patches()
                if patch.game_id == "vv1"
            ]
            assert "vv1_write_parentage_log" in ids
        rendered, _ = patcher.render_patched_bytes(
            STOCK, builds["vv1"], "stock" if label == "alone" else label, ids
        )
        rendered = bytes(rendered)
        # The triplets tail must jump to the cave this render is meant to
        # exercise: .text when alone, the Origins page (.vv1mc) when composed,
        # which Origins is always pulled into by the public village-wide rows.
        tail = 0x3BCA2
        assert rendered[tail] == 0xE9
        target = 0x43BCA2 + 5 + struct.unpack_from("<i", rendered, tail + 1)[0]
        assert target == (0x456900 if label == "alone" else 0x490E00), hex(target)
        _RENDERS[label] = rendered
    return _RENDERS[label]


@unittest.skipUnless(HAVE_DEPS, "unicorn and pefile are required")
class VV1ConceptionEmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not STOCK.is_file():
            raise unittest.SkipTest("the exact-build VV1 executable is not available")
        cls.stock = STOCK.read_bytes()

    def _check(self, render_label: str) -> None:
        image = _render(render_label)
        for name, scenario in _scenarios():
            entry, stop, slots, regs, before, mother, father, genders = scenario
            for litter, rolls in LITTERS.items():
                with self.subTest(render=render_label, path=name, litter=litter):
                    kwargs = dict(stack_slots=slots, regs=regs,
                                  rolls=before + rolls, genders=genders)
                    stock = _emulate(self.stock, entry, stop, **kwargs)
                    patched = _emulate(image, entry, stop, **kwargs)
                    self.assertEqual(stock.stopped_at, stop,
                                     "the stock run never returned to the caller")
                    self.assertEqual(patched.stopped_at, stop,
                                     "the patched run never returned to the caller")

                    # The scenario really is the path it names.
                    litter_field = struct.unpack_from(
                        "<I", stock.records, mother * STRIDE + 0x35C)[0]
                    self.assertEqual(
                        litter_field, {"single": 0, "twins": 2, "triplets": 3}[litter])
                    stock_394 = struct.unpack_from(
                        "<I", stock.records, mother * STRIDE + 0x394)[0]
                    self.assertEqual(
                        stock_394, _field_36c(father),
                        "stock stores the father's +0x36C in the mother's +0x394")

                    # (1) The patch changes nothing the game can observe.
                    patched_394 = struct.unpack_from(
                        "<I", patched.records, mother * STRIDE + 0x394)[0]
                    self.assertEqual(
                        patched_394, stock_394,
                        "the mother's +0x394 differs from stock: %#x, stock %#x"
                        % (patched_394, stock_394))
                    self.assertEqual(patched.records, stock.records,
                                     "the villager array differs from stock")
                    self.assertEqual(patched.state, stock.state,
                                     "the game state differs from stock")
                    for reg in ("esp", "ebx", "ebp", "esi", "edi"):
                        self.assertEqual(
                            patched.regs[reg], stock.regs[reg],
                            "%s at the caller's return differs from stock" % reg)

                    # (2) The companion is handed the real father, once.
                    self.assertEqual(stock.exports, [])
                    self.assertEqual(
                        patched.exports,
                        [(1, THIS, _record(mother), _record(father))],
                        "the companion was not handed (game, records, mother, "
                        "father) -- father expected %#x" % _record(father))

    def test_the_feature_alone(self) -> None:
        self._check("alone")

    def test_every_public_vv1_patch_together(self) -> None:
        for mode in ALL_MODES:
            self._check(mode)

    def test_an_unknown_caller_passes_no_father(self) -> None:
        """A return address outside the six sites must not name anyone.

        Entering the routine directly with a fake return address stands in for
        a caller this build does not know; the companion must then be handed a
        null father ("not captured for this birth"), never a stranger.
        """
        image = _render("alone")
        fake_return = 0x401000
        slots = {0: fake_return, 4: MOTHER, 8: _field_36c(FATHER), 0xC: 1,
                 0x10: 7, 0x2C: _record(FATHER), 0x24: _record(FATHER)}
        run = _emulate(image, 0x43BBC0, fake_return, stack_slots=slots,
                       regs={"ecx": THIS, "ebp": _record(FATHER)},
                       rolls=LITTERS["single"], genders={})
        self.assertEqual(run.stopped_at, fake_return)
        self.assertEqual(run.exports, [(1, THIS, _record(MOTHER), 0)])


if __name__ == "__main__":
    unittest.main()
