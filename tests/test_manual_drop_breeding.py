"""Manual Drop-Breeding overrides Birth Control, all five games.

The owner: "If the player manually drops two villagers to breed, they should
be able to have a child regardless if the woman is over 50/unchecked
Parenting/has Parenting skill or not. Default-OFF. Owner's-Defaults ON."
Not a guarantee ("Normal chance, no blocks"), and "every existing stock rule
still applies!!!" -- only the blocks go, and ONLY FOR THE MANUAL DROP.

What each game's real pairing handler does was established by running it, not
by reading it (the handler is the routine the villager step dispatcher calls
for the pairing step; it owns the "These villagers are both the same gender."
refusal and the "drag an adult male villager onto an adult female villager"
tutorial):

    game  handler    pregnancy writer  woman-50+ refusal (stock)
    VV1   0x43DAD0   0x43BBC0          none; Birth Control's hook at 0x43DD03 adds one
    VV2   0x44F610   0x44B980          0x44F7C8..0x44F7FE, after the conception roll
    VV3   0x4584B0   0x4582A0          0x4586F3..0x45871B, after the conception roll
    VV4   0x460C10   0x460990          0x460E67..0x460E8D, after the conception roll
    VV5   0x4689A0   0x467D20          0x468BC4..0x468BEA, after the conception roll

THE HANDLER IS SHARED. Villagers who pair up on their own (the live Embracing
route) reach the same handler through the same pairing step as the player's
drop (see ROUTES below). The first version of this patch skipped the refusal
for every entry, so an autonomous initiator of 50 or older conceived too --
contrary to the patch's own description and to Birth Control's VV4/VV5
reference. The refusal is now skipped only when the player's drop is on the
stack, which these tests establish by running both real routes.

Neither the Parenting preference nor a Parenting skill threshold is a gate on
the manual drop in any game: the emulated handlers never read the preference
field, and a villager with no Parenting skill conceives on a passing roll in
stock. Skill only feeds the two stock chances (the skill-attempt roll and the
RNG(300) conception roll), which stay. So the patch lifts exactly one thing,
the woman-aged-50-or-older refusal, for the drop only, and in VV1 -- where the
game has none -- it steps the drop around Birth Control's hook so that refusal
is lifted for the drop when both patches are ticked.

The emulator runs each route from its real call site on the rendered bytes:
the game's own action table (filled by the game's own static initialiser),
step queue, dispatcher and pop-and-dispatch routine, the handler, the game's
Parenting skill-attempt routine and VV4/VV5's float-to-int helper. Every other
call is a stub that pops its own arguments; the random routine is scripted. A
run ends at the call into the pregnancy writer (the pair conceives) or when the
route returns (no conception).

Tests that need a stock executable or unicorn skip when it is absent (CI has
no game files); the catalog and decode tests run everywhere.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import capstone  # noqa: E402

import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher_gui import (  # noqa: E402
    default_fun_patch_selection,
    owners_default_fun_patch_selection,
)

try:  # optional dependency
    import pefile
    from unicorn import (
        UC_ARCH_X86,
        UC_HOOK_CODE,
        UC_HOOK_MEM_FETCH_UNMAPPED,
        UC_HOOK_MEM_READ,
        UC_HOOK_MEM_READ_UNMAPPED,
        UC_HOOK_MEM_WRITE_UNMAPPED,
        UC_MODE_32,
        Uc,
        UcError,
    )
    from unicorn.x86_const import (
        UC_X86_REG_EAX,
        UC_X86_REG_EBP,
        UC_X86_REG_EBX,
        UC_X86_REG_ECX,
        UC_X86_REG_EDI,
        UC_X86_REG_EDX,
        UC_X86_REG_EFLAGS,
        UC_X86_REG_EIP,
        UC_X86_REG_ESI,
        UC_X86_REG_ESP,
    )

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False


GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
MODES = ("stock", "collection_progression", "immediate_fixed")
NAME = "Manual Drop-Breeding overrides Birth Control"


def feature_id(game: str) -> str:
    return f"{game}_manual_drop_breeding_overrides_birth_control"


# The byte patches per game, pinned independently of the manifest:
# [(file offset, stock bytes, patched bytes), ...]
PATCHES = {
    "vv1": [(
        0x3DCD8,
        "8BF88B44241883C40483C70585C0741B8B4C241085C974133BC8750F6A03E81552FCFF8BF883C40483C705",
        "598B4C2414E30E3B4C241075086A03E82452FCFF598D7805817C2430BE524200750983BD5003000002EB07",
    )],
    "vv2": [(
        0x4F7C8,
        "8B8F38050000B8020000003BC8750C81BF30050000E80300007C1C3983380500000F856D030000"
        "81BB30050000E80300000F8D5D030000",
        "817C2430630F4300742DB8E803000083BF380500000275083987300500007C1783BB3805000002"
        "75083983300500007C06E95E03000090",
    )],
    "vv3": [
        (0x586F3, "8B8EC40D0000B8E80300003BC8", "EB4CB8E80300003986C40D0000"),
        (0x58741, "909090909090909090909090", "817C2448D669460074D1EBA8"),
    ],
    "vv4": [
        (0x60E67, "B8E8030000", "E947000000"),
        (0x60EB3, "CCCCCCCCCCCCCCCCCCCCCCCC", "817C2440F20E440074D1EB06"),
        (0x60EC5, "CCCCCCCCCCCCCC", "B8E8030000EBA0"),
    ],
    "vv5": [
        (0x68BC4, "B8E8030000", "E9F7BF0200"),
        (0x94BC0, "000000000000000000000000000000000000000000000000",
         "817C244C2D4044000F841D40FDFFB8E8030000E9F13FFDFF"),
    ],
}

# The drop test: `cmp dword ptr [esp + depth], drop_return` at VA, then where the
# drop goes and where every other entry goes (the first instruction each reaches
# after the test's own jumps; VV1's drop then does the stock compare and jumps
# to 0x43DD0A).
#   game: (VA of the cmp, depth, drop's return address, drop continues at, others continue at)
DROP_TEST = {
    "vv1": (0x43DCF0, 0x30, 0x4252BE, 0x43DCFA, 0x43DD03),
    "vv2": (0x44F7C8, 0x30, 0x430F63, 0x44F7FF, 0x44F7D2),
    "vv3": (0x458741, 0x48, 0x4669D6, 0x45871C, 0x4586F5),
    "vv4": (0x460EB3, 0x40, 0x440EF2, 0x460E8E, 0x460EC5),
    "vv5": (0x494BC0, 0x4C, 0x44402D, 0x468BEB, 0x494BCE),
}
VV1_BLOCK_VA = 0x43DCD8
VV1_BC_MANUAL_HOOK_VA = 0x43DD03
VV1_BC_ACCEPT_VA = 0x43DD0A  # where Birth Control's own accept path resumes too

# Whether the unpatched game (plus Birth Control when named) refuses a woman
# aged 50 or older in the pairing handler -- on a drop and on autonomous
# pairing alike.
STOCK_REFUSES_50 = {"vv1": False, "vv2": True, "vv3": True, "vv4": True, "vv5": True}
BIRTH_CONTROL_ADDS_REFUSAL = {"vv1": True, "vv2": False, "vv3": False}


def stock_path(game: str) -> Path:
    build = _builds()[game]
    return ROOT / "inputs" / f"{game}-stock-copy" / build.input_name


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


@functools.lru_cache(maxsize=None)
def _catalog():
    return {patch.id: patch for patch in patcher.load_fun_patches()}


@functools.lru_cache(maxsize=None)
def _public():
    return tuple(patcher.load_public_fun_patches())


@functools.lru_cache(maxsize=None)
def render(game: str, mode: str, ids: tuple[str, ...]) -> bytes:
    data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[game], mode, list(ids))
    return bytes(data)


def pe_checksum_range(data: bytes) -> range:
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    start = pe_offset + 0x18 + 0x40
    return range(start, start + 4)


# ---------------------------------------------------------------------------
# Emulator
# ---------------------------------------------------------------------------

IMAGE_BASE = 0x400000
DATA = 0x10000000
DATA_SIZE = 0x01000000
STACK = 0x30000000
STACK_SIZE = 0x100000
SENTINEL = 0x3F000000


@dataclass(frozen=True)
class GameLayout:
    handler: int
    writer: int
    rng: int
    run_real: frozenset
    female: int
    male: int
    age: int
    sex: int
    health: int
    sick: int
    sick_width: int
    pending: int
    skill: int
    skill_is_float: bool
    preference: int
    parenting_preference: int
    array_stride: int | None
    partner_finder: int
    tip_query: int | None = None
    conception_tip: int | None = None
    love_shack: int | None = None
    population: int | None = None
    tech_level: int | None = None
    state_pointer_calls: tuple = ()
    self_pointer: int | None = None
    state_offset: int | None = None
    state_food: int | None = None
    state_tech: int | None = None
    food_global: int | None = None


LAYOUTS = {
    "vv1": GameLayout(
        handler=0x43DAD0, writer=0x43BBC0, rng=0x402F10, run_real=frozenset({0x43D440}),
        female=2, male=1, age=0x348, sex=0x350, health=0x344, sick=0x354, sick_width=4,
        pending=0x358, skill=0x3BC, skill_is_float=False, preference=0x3D0,
        parenting_preference=2, array_stride=0x3D8, partner_finder=0x439350,
        population=0x41CF90, state_offset=0x3E010, state_food=0xA2EC, state_tech=0xA2DC,
    ),
    "vv2": GameLayout(
        handler=0x44F610, writer=0x44B980, rng=0x4031A0, run_real=frozenset({0x44E170}),
        female=2, male=1, age=0x530, sex=0x538, health=0x52C, sick=0x53C, sick_width=4,
        pending=0x540, skill=0x7E4, skill_is_float=False, preference=0x7F8,
        parenting_preference=2, array_stride=0xE48C, partner_finder=0x449160,
        population=0x425860, state_offset=0xE574D4, state_food=0x2EAA4, state_tech=0x2EA8C,
    ),
    "vv3": GameLayout(
        handler=0x4584B0, writer=0x4582A0, rng=0x4032D0, run_real=frozenset({0x45A2C0}),
        female=1, male=0, age=0xDC4, sex=0xDC8, health=0xE78, sick=0xE89, sick_width=1,
        pending=0xE8C, skill=0xEB0, skill_is_float=False, preference=0xEC0,
        parenting_preference=1, array_stride=None, partner_finder=0x45F960,
        tip_query=0x436F70, conception_tip=0x291, population=0x45E8F0,
        tech_level=0x426FC0, state_pointer_calls=(0x428B60,), food_global=0x582490,
    ),
    "vv4": GameLayout(
        handler=0x460C10, writer=0x460990, rng=0x4036D0,
        run_real=frozenset({0x462A80, 0x471630}), female=1, male=0, age=0x1B8C,
        sex=0x1B90, health=0x1C40, sick=0x1C48, sick_width=1, pending=0x1C4C,
        skill=0x1C60, skill_is_float=True, preference=0x1C70, parenting_preference=1,
        array_stride=None, partner_finder=0x466A00, tip_query=0x44B9A0,
        conception_tip=0x2CE, love_shack=0x438960, population=0x467610,
        tech_level=0x41E1C0, state_pointer_calls=(0x41FE70,), self_pointer=0x1B88,
        food_global=0x4D6DD0,
    ),
    "vv5": GameLayout(
        handler=0x4689A0, writer=0x467D20, rng=0x403660,
        run_real=frozenset({0x46B270, 0x47C9B0}), female=1, male=0, age=0x1B8C,
        sex=0x1B90, health=0x1C40, sick=0x1C48, sick_width=1, pending=0x1C4C,
        skill=0x1C60, skill_is_float=True, preference=0x1C74, parenting_preference=1,
        array_stride=None, partner_finder=0x4705D0, tip_query=0x44E840,
        conception_tip=0x2BE, love_shack=0x43AE80, tech_level=0x423600,
        self_pointer=0x1B88, food_global=0x51D34C,
    ),
}


# ---------------------------------------------------------------------------
# The real routes INTO the handler: the player's drop and autonomous pairing
# ---------------------------------------------------------------------------
#
# The handler is not only the player's drop. In every game the villagers who
# pair up on their own reach the SAME handler through the SAME pairing step:
#
#   game  drop site (returns to)        autonomous site (returns to)   step  queued by
#   VV1   0x4252B9 call 0x445510        0x447886 call 0x445510           9   0x445510 (both call it directly)
#   VV2   0x430F5E call 0x45D510        0x46044C call 0x45D510          12   0x45D510 (both call it directly)
#   VV3   0x4669D1 action 4 (0x4669D6)  0x45B674 action 4 (0x45B679)    13   action 4 = 0x44A680
#   VV4   0x440EED action 3 (0x440EF2)  0x463FC3 action 3 (0x463FC8)    15   action 3 = 0x455420
#   VV5   0x444028 action 5 (0x44402D)  0x46CB1E action 5 (0x46CB23)    16   action 5 = 0x45D010
#
# The difference between them is WHEN the handler runs. The drop clears the
# dropped villager's steps and queues the pairing step on the empty queue, so
# the game's own dispatcher runs the handler at once, inside the drop's call.
# The autonomous initiator first queues a walk to the partner, so the pairing
# step runs later, when the walk arrives and the game's own pop-and-dispatch
# routine moves to it -- never inside the autonomous site's call, and never
# inside the drop's. So "the drop's call is on the stack" is exactly "this is
# a manual drop", and the patch tests the drop's return address at the stack
# depth the game's own fixed call chain puts it (DROP_TEST).
#
# Catch-up (VV2's 0x464680, VV3's 0x45B790, VV4's 0x464FA0, VV5's 0x46E020,
# VV1's 0x446C70) executes the same pairing step in its own executor and never
# reaches the handler.
#
# Each route below runs from the real site to the real handler; only engine
# services outside the step machinery are stubbed.


@dataclass(frozen=True)
class Route:
    start: int  # first instruction executed
    stop: int  # the site's return address: the route has finished when EIP gets here
    regs: tuple  # (register, symbol) with symbol in dropped/target/array/ai/zero
    next_step: int | None = None  # autonomous: the game's own pop-and-dispatch routine
    next_step_args: tuple = ()  # its stack arguments (symbols or ints)
    next_step_ecx: str = "dropped"


@dataclass(frozen=True)
class GameRoutes:
    manual: Route
    autonomous: Route
    run_real: frozenset  # the step machinery the routes execute
    measure: tuple  # where the woman-50 check executes (stack identical to the patch's check)
    handler_end: int  # inside the handler only its own helpers run
    init: int | None = None  # static initialiser that registers the action table
    stub_entries: frozenset = frozenset()  # routines reached by a jump, returned from at once
    walk_step: int = 0  # the step the autonomous initiator queues first
    step_code_offset: int = 0  # where the head step's code lives, from the record


ROUTES = {
    "vv1": GameRoutes(
        manual=Route(0x4252B8, 0x4252BE, (("edx", "dropped"), ("ecx", "array"))),
        autonomous=Route(0x447850, 0x44788B,
                         (("ebx", "dropped"), ("edi", "target"), ("esi", "array")),
                         next_step=0x445C50, next_step_args=("dropped",), next_step_ecx="array"),
        run_real=frozenset({0x445510, 0x4399F0, 0x439470, 0x43DEF0, 0x445C50}),
        measure=(0x43DD03, 0x43DCF0),  # the stock compare; the patched block's drop test
        handler_end=0x43DEF0,
        stub_entries=frozenset({0x43CCF0}),  # the walk, reached by the dispatcher's jump
        walk_step=3, step_code_offset=0x44,
    ),
    "vv2": GameRoutes(
        manual=Route(0x430F5D, 0x430F63, (("eax", "dropped"), ("ecx", "array"))),
        autonomous=Route(0x460416, 0x460451,
                         (("ebx", "dropped"), ("edi", "target"), ("esi", "array")),
                         next_step=0x449380, next_step_args=("dropped",), next_step_ecx="array"),
        run_real=frozenset({0x45D510, 0x449B70, 0x4492A0, 0x44FBB0, 0x449380}),
        measure=(0x44F7C8,), handler_end=0x44FBB0,
        stub_entries=frozenset({0x44D810}),  # the walk, reached by the dispatcher's jump
        walk_step=3, step_code_offset=0x4C,
    ),
    "vv3": GameRoutes(
        manual=Route(0x4669C0, 0x4669D6, (("esi", "dropped"),)),
        autonomous=Route(0x45B63C, 0x45B679, (("edi", "dropped"), ("esi", "target")),
                         next_step=0x460F20, next_step_args=("dropped", 1), next_step_ecx="dropped"),
        run_real=frozenset({0x455570, 0x441170, 0x44A680, 0x4616B0, 0x460E30, 0x461080,
                            0x460F70, 0x461BF0, 0x460F20, 0x455EF0,
                            0x4411B0, 0x4411D0, 0x4611B0}),
        measure=(0x4586F3,), handler_end=0x458750, init=0x47B110,
        walk_step=3,
    ),
    "vv4": GameRoutes(
        manual=Route(0x440ED9, 0x440EF2, (("edi", "dropped"), ("ebx", "zero"))),
        autonomous=Route(0x4641B7, 0x463FC8,
                         (("esi", "ai"), ("edi", "target"), ("ebx", "zero")),
                         next_step=0x468C10, next_step_args=(1,), next_step_ecx="dropped"),
        run_real=frozenset({0x468C60, 0x45DEC0, 0x44F720, 0x455420, 0x469720, 0x468B20,
                            0x468EE0, 0x46A030, 0x469050, 0x45ED00, 0x468C10,
                            0x44F770, 0x44F790}),
        measure=(0x460E67,), handler_end=0x460ED0, init=0x488D50,
        walk_step=3,
    ),
    "vv5": GameRoutes(
        manual=Route(0x444014, 0x44402D, (("edi", "dropped"), ("ebx", "zero"))),
        autonomous=Route(0x46CCCF, 0x46CB23,
                         (("esi", "ai"), ("edi", "target"), ("ebx", "zero")),
                         next_step=0x4733F0, next_step_args=(1,), next_step_ecx="dropped"),
        run_real=frozenset({0x473440, 0x465580, 0x452BD0, 0x45D010, 0x474CE0, 0x473380,
                            0x474450, 0x473590, 0x4745A0, 0x466350, 0x4733F0,
                            0x452C20, 0x452C40}),
        measure=(0x468BC4,), handler_end=0x468C10, init=0x494030,
        walk_step=4,
    ),
}
ENGINE_STATE_GETTERS = frozenset({0x41FE70, 0x425950, 0x42F740, 0x428B60})


@dataclass(frozen=True)
class Villager:
    female: bool
    age: int = 400  # internal units: 360 = 18 years, 1000 = 50 years
    skill: int = 50
    parenting_checked: bool = True
    health: int = 100
    sick: bool = False
    expecting: bool = False


@dataclass(frozen=True)
class Scenario:
    dropped: Villager  # the villager the handler runs for: the dropped one, or the initiator
    target: Villager  # the partner
    rng: tuple = ()  # ((limit, (values...)), ...); unlisted draws return 0
    population: int = 5
    food: int = 5000


@dataclass
class Outcome:
    conceived: bool
    writer_args: tuple = ()
    rng_calls: list = field(default_factory=list)
    preference_reads: list = field(default_factory=list)
    drop_slots: list = field(default_factory=list)  # k with [esp+k] == the drop's return address, at measure
    handler_entered: bool = False
    head_step_after_start: int | None = None

    @property
    def conception_roll_reached(self) -> bool:
        return 300 in self.rng_calls


@functools.lru_cache(maxsize=None)
def _mapped(image: bytes) -> bytes:
    return bytes(pefile.PE(data=image, fast_load=True).get_memory_mapped_image())


_ARG_BYTES: dict = {}


def _callee_arg_bytes(mapped: bytes, target: int) -> int:
    """The callee's own `ret N`, on its fall-through path."""
    key = (hash(mapped), target)
    if key in _ARG_BYTES:
        return _ARG_BYTES[key]
    # Walk the fall-through path, following unconditional jumps (tail calls
    # and in-function jumps alike), to the first ret on it.
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    address, visited, result = target, set(), None
    while result is None:
        if address in visited:
            raise AssertionError(f"no ret found for callee {target:#x}")
        visited.add(address)
        offset = address - IMAGE_BASE
        for ins in md.disasm(mapped[offset : offset + 0x4000], address):
            if ins.mnemonic == "ret":
                result = int(ins.op_str, 16) if ins.op_str else 0
                break
            if ins.mnemonic == "jmp" and ins.op_str.startswith("0x"):
                address = int(ins.op_str, 16)
                break
            if ins.mnemonic == "int3":
                raise AssertionError(f"no ret found for callee {target:#x}")
        else:
            raise AssertionError(f"no ret found for callee {target:#x}")
    _ARG_BYTES[key] = result
    return result


REGISTERS = {
    "eax": "UC_X86_REG_EAX", "ebx": "UC_X86_REG_EBX", "ecx": "UC_X86_REG_ECX",
    "edx": "UC_X86_REG_EDX", "esi": "UC_X86_REG_ESI", "edi": "UC_X86_REG_EDI",
}


def emulate_route(image: bytes, game: str, scenario: Scenario, route_name: str) -> Outcome:
    """Run a real route -- the player's drop or autonomous pairing -- into the handler."""
    layout = LAYOUTS[game]
    routes = ROUTES[game]
    route = routes.manual if route_name == "manual" else routes.autonomous
    drop_return = routes.manual.stop
    mapped = _mapped(image)
    size = (pefile.PE(data=image, fast_load=True).OPTIONAL_HEADER.SizeOfImage + 0xFFFF) & ~0xFFFF
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(IMAGE_BASE, size)
    mu.mem_write(IMAGE_BASE, mapped[:size])
    mu.mem_map(DATA, DATA_SIZE)
    mu.mem_map(STACK, STACK_SIZE)
    mu.mem_map(SENTINEL, 0x1000)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    regs = {name: getattr(sys.modules["unicorn.x86_const"], const) for name, const in REGISTERS.items()}

    def w32(addr: int, value: int) -> None:
        mu.mem_write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def r32(addr: int) -> int:
        return struct.unpack("<I", bytes(mu.mem_read(addr, 4)))[0]

    state = DATA + 0x00F00000  # zeroed state object for pointer-returning helpers
    ai = DATA + 0x00E00000  # VV4/VV5's thinking object: [ai+0x1B88] is the villager
    if layout.array_stride is not None:
        dropped_index, target_index = 3, 7
        dropped = DATA + dropped_index * layout.array_stride
        target = DATA + target_index * layout.array_stride
        w32(DATA + layout.state_offset, state)
        w32(state + layout.state_food, scenario.food)
        w32(state + layout.state_tech, 1)
        symbols = {"dropped": dropped_index, "target": target_index, "array": DATA}
        finder_result = target_index
    else:
        dropped, target = DATA + 0x10000, DATA + 0x20000
        symbols = {"dropped": dropped, "target": target, "array": DATA}
        finder_result = target
    symbols.update(zero=0, ai=ai)
    w32(ai + 0x1B88, dropped)
    if layout.food_global is not None:
        w32(layout.food_global, scenario.food)

    for record, villager in ((dropped, scenario.dropped), (target, scenario.target)):
        w32(record + layout.age, villager.age)
        w32(record + layout.sex, layout.female if villager.female else layout.male)
        w32(record + layout.health, villager.health)
        if layout.sick_width == 1:
            mu.mem_write(record + layout.sick, b"\x01" if villager.sick else b"\x00")
        else:
            w32(record + layout.sick, 1 if villager.sick else 0)
        w32(record + layout.pending, 1 if villager.expecting else 0)
        if layout.skill_is_float:
            mu.mem_write(record + layout.skill, struct.pack("<f", float(villager.skill)))
        else:
            w32(record + layout.skill, villager.skill)
        w32(record + layout.preference,
            layout.parenting_preference if villager.parenting_checked else 0)
        if layout.self_pointer is not None:
            w32(record + layout.self_pointer, record)
            w32(record + 0x1B80, record)  # the step queue's owner

    run_real = layout.run_real | routes.run_real | {layout.handler}
    queues = {limit: list(values) for limit, values in scenario.rng}
    outcome = Outcome(False)
    faults: list[str] = []

    def stub_value(target_va: int, esp: int) -> int:
        if target_va == layout.partner_finder:
            return finder_result
        if target_va in layout.state_pointer_calls or target_va in ENGINE_STATE_GETTERS:
            return state
        if target_va == layout.tip_query:
            return 1 if r32(esp) == layout.conception_tip else 0
        if target_va == layout.love_shack:
            return 1
        if target_va == layout.population:
            return scenario.population
        if target_va == layout.tech_level:
            return 1
        return 0

    def stub(uc, resume: int, target_va: int, esp: int, value: int) -> None:
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, esp + _callee_arg_bytes(mapped, target_va))
        uc.reg_write(UC_X86_REG_EIP, resume)

    def on_code(uc, address, size, _user):  # noqa: ANN001
        if address == layout.handler:
            outcome.handler_entered = True
        if address in routes.measure:
            esp = uc.reg_read(UC_X86_REG_ESP)
            outcome.drop_slots = [k for k in range(0, 0x200, 4) if r32(esp + k) == drop_return]
        if address in routes.stub_entries:
            esp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EAX, 0)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + _callee_arg_bytes(mapped, address))
            uc.reg_write(UC_X86_REG_EIP, r32(esp))
            return
        head = bytes(uc.mem_read(address, 2))
        inside_handler = layout.handler <= address < routes.handler_end
        real = layout.run_real if inside_handler else run_real
        if head[0] == 0xFF and (head[1] >> 3) & 7 == 2:
            ins = next(md.disasm(bytes(uc.mem_read(address, 8)), address))
            if ins.op_str not in regs:
                faults.append(f"unexpected indirect call at {address:#x}: {ins.op_str}")
                uc.emu_stop()
                return
            target_va = uc.reg_read(regs[ins.op_str])
            if target_va not in real:
                stub(uc, address + ins.size, target_va, uc.reg_read(UC_X86_REG_ESP), 0)
            return
        if head[0] != 0xE8:
            return
        rel = struct.unpack("<i", bytes(uc.mem_read(address + 1, 4)))[0]
        target_va = (address + 5 + rel) & 0xFFFFFFFF
        esp = uc.reg_read(UC_X86_REG_ESP)
        if target_va == layout.writer:
            outcome.conceived = True
            outcome.writer_args = tuple(r32(esp + 4 * i) for i in range(4))
            uc.emu_stop()
            return
        if target_va in real:
            return
        if target_va == layout.rng:
            limit = r32(esp)
            outcome.rng_calls.append(limit)
            queue = queues.get(limit)
            uc.reg_write(UC_X86_REG_EAX, queue.pop(0) if queue else 0)
            uc.reg_write(UC_X86_REG_EIP, address + 5)
            return
        stub(uc, address + 5, target_va, esp, stub_value(target_va, esp))

    def on_unmapped(uc, access, address, size, value, _user):  # noqa: ANN001
        faults.append(f"unmapped access {address:#x} at {uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

    def on_read(uc, access, address, size, value, _user):  # noqa: ANN001
        for record in (dropped, target):
            if record + layout.preference <= address < record + layout.preference + 4:
                outcome.preference_reads.append(address)

    mu.hook_add(UC_HOOK_CODE, on_code)
    mu.hook_add(
        UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED | UC_HOOK_MEM_FETCH_UNMAPPED,
        on_unmapped,
    )
    mu.hook_add(UC_HOOK_MEM_READ, on_read, begin=DATA, end=DATA + DATA_SIZE - 1)

    def run(start: int, stop: int, esp: int) -> None:
        mu.reg_write(UC_X86_REG_ESP, esp)
        try:
            mu.emu_start(start, stop, count=400000)
        except UcError as exc:
            faults.append(f"{exc} at {mu.reg_read(UC_X86_REG_EIP):#x}")
        if faults:
            raise AssertionError("; ".join(faults))

    base_esp = STACK + STACK_SIZE // 2
    if routes.init is not None:  # the game's own static initialiser fills the action table
        w32(base_esp, SENTINEL)
        run(routes.init, SENTINEL, base_esp)
    for reg, symbol in route.regs:
        mu.reg_write(regs[reg], symbols[symbol])
    # The route starts in the middle of its own function: below ESP is that frame.
    run(route.start, route.stop, base_esp - 0x400)
    if outcome.conceived or route.next_step is None:
        if not outcome.conceived and mu.reg_read(UC_X86_REG_EIP) != route.stop:
            raise AssertionError("the route neither conceived nor returned")
        return outcome
    # Autonomous: the pairing step waits behind the walk to the partner.
    outcome.head_step_after_start = r32(dropped + routes.step_code_offset)
    if outcome.handler_entered:
        raise AssertionError("the autonomous route reached the handler before its walk")
    # The walk arrives: the game's own pop-and-dispatch moves on to the pairing step.
    esp = base_esp - 0x800
    w32(esp, SENTINEL)
    for i, value in enumerate(route.next_step_args):
        w32(esp + 4 + 4 * i, symbols[value] if isinstance(value, str) else value)
    mu.reg_write(UC_X86_REG_ECX, symbols[route.next_step_ecx] if route.next_step_ecx != "dropped"
                 or layout.array_stride is not None else dropped)
    run(route.next_step, SENTINEL, esp)
    if not outcome.conceived and mu.reg_read(UC_X86_REG_EIP) != SENTINEL:
        raise AssertionError("the walk's arrival neither conceived nor returned")
    return outcome


def emulate_drop(image: bytes, game: str, scenario: Scenario) -> Outcome:
    """The player drops `scenario.dropped` onto `scenario.target`."""
    return emulate_route(image, game, scenario, "manual")


def emulate_autonomous(image: bytes, game: str, scenario: Scenario) -> Outcome:
    """`scenario.dropped` pairs up with `scenario.target` on its own."""
    return emulate_route(image, game, scenario, "autonomous")


YOUNG_WOMAN = Villager(female=True)
MAN = Villager(female=False)
OLD_WOMAN = Villager(female=True, age=1200)  # 60 years
EDGE_WOMAN = Villager(female=True, age=1000)  # exactly 50 years
JUST_UNDER_WOMAN = Villager(female=True, age=999)
OLD_MAN = Villager(female=False, age=1500)

FAIL_CONCEPTION_ROLL = ((300, (299,)),)
FAIL_SKILL_ATTEMPT = ((100, (99, 99, 99)),)

# Every stock rule the patch must leave in force: (label, scenario).
KEPT_RULES = (
    ("same sex (two women)", Scenario(OLD_WOMAN, YOUNG_WOMAN)),
    ("same sex (two men)", Scenario(MAN, OLD_MAN)),
    ("dropped woman is a child", Scenario(replace(OLD_WOMAN, age=300), MAN)),
    ("target man is a child", Scenario(OLD_WOMAN, replace(MAN, age=300))),
    ("woman already expecting or nursing", Scenario(replace(OLD_WOMAN, expecting=True), MAN)),
    ("woman is ill", Scenario(replace(OLD_WOMAN, sick=True), MAN)),
    ("man is ill", Scenario(OLD_WOMAN, replace(MAN, sick=True))),
    ("target is dead", Scenario(OLD_WOMAN, replace(MAN, health=0))),
    ("hungry village", Scenario(OLD_WOMAN, MAN, rng=((100, (99,)),), food=10)),
)
# The stock population refusal, where the handler itself has one (VV5's is
# not in the handler: its pregnancy writer applies the capacity checks).
POPULATION_RULE_GAMES = ("vv1", "vv2", "vv3", "vv4")

# Pairs both ways round, for the autonomous comparisons.
AUTONOMOUS_PAIRS = tuple(
    pair
    for woman in (OLD_WOMAN, EDGE_WOMAN, JUST_UNDER_WOMAN, YOUNG_WOMAN)
    for pair in ((woman, MAN), (MAN, woman), (woman, OLD_MAN))
)


def variants(game: str) -> dict[str, tuple[str, ...]]:
    out = {"stock": (), "patch": (feature_id(game),)}
    if game in BIRTH_CONTROL_ADDS_REFUSAL:
        out["birth control"] = (f"{game}_birth_control",)
        out["birth control + patch"] = (f"{game}_birth_control", feature_id(game))
    return out


def handler_refuses_50(game: str, ids: tuple[str, ...]) -> bool:
    """The game's (or VV1 Birth Control's) refusal, which autonomous pairing keeps."""
    return STOCK_REFUSES_50[game] or (
        f"{game}_birth_control" in ids and BIRTH_CONTROL_ADDS_REFUSAL.get(game, False)
    )


def refuses_50(game: str, ids: tuple[str, ...]) -> bool:
    """Whether the player's DROP is refused for a woman of 50 or older."""
    if feature_id(game) in ids:
        return False
    return handler_refuses_50(game, ids)


def _patch_ranges(game: str) -> list[range]:
    return [range(offset, offset + len(bytes.fromhex(after))) for offset, _, after in PATCHES[game]]


# ---------------------------------------------------------------------------
# Catalog, wording and encodings -- no game files needed
# ---------------------------------------------------------------------------


class ManualDropCatalogTests(unittest.TestCase):
    def test_one_record_per_game_with_the_owners_name(self) -> None:
        catalog = _catalog()
        public = {patch.id for patch in _public()}
        for game in GAMES:
            with self.subTest(game=game):
                record = catalog[feature_id(game)]
                self.assertEqual(record.game_id, game)
                self.assertEqual(record.name, NAME)
                self.assertIn(record.id, public)

    def test_default_off_and_owners_defaults_on(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                self.assertFalse(default_fun_patch_selection(feature_id(game)))
                self.assertTrue(owners_default_fun_patch_selection(feature_id(game)))

    def test_each_record_writes_exactly_the_pinned_bytes(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                record = _catalog()[feature_id(game)]
                self.assertEqual(
                    [(int(p["offset"], 0), p["before"].upper(), p["after"].upper())
                     for p in record.patches],
                    [(offset, before.upper(), after.upper()) for offset, before, after in PATCHES[game]],
                )
                for offset, before, after in PATCHES[game]:
                    self.assertEqual(len(bytes.fromhex(before)), len(bytes.fromhex(after)))
                self.assertFalse(record.raw.get("dependencies"))
                self.assertFalse(record.raw.get("needs_on"))
                self.assertFalse(record.raw.get("composition_patches"))

    def test_descriptions_state_the_dependency_in_bold_and_agree(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                text = _catalog()[feature_id(game)].description
                self.assertTrue(text.startswith("**"), text)
                self.assertEqual(text.count("**"), 2)
                for phrase in (
                    "a woman aged 50 or older is no longer refused",
                    "It is not a guarantee",
                    "so a drop can still fail",
                    "a man and a woman, both adults",
                    "the woman not already expecting or nursing",
                    "The game never looks at the Parenting preference on a manual drop",
                    "Only the manual drop is changed: villagers pairing up on their own",
                    "Off by default.",
                ):
                    self.assertIn(phrase, text)
        vv1 = _catalog()[feature_id("vv1")].description
        self.assertIn("only changes anything when Birth Control is also ticked", vv1)
        self.assertIn("for manual drops only", vv1)
        for game in ("vv2", "vv3"):
            self.assertIn("Works the same with or without Birth Control",
                          _catalog()[feature_id(game)].description)
        for game in ("vv4", "vv5"):
            self.assertIn("this game has no Birth Control patch",
                          _catalog()[feature_id(game)].description)

    def _decode(self, game: str) -> dict[int, tuple[str, str, int]]:
        """Every instruction the patch writes: VA -> (mnemonic, operands, size)."""
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        out = {}
        for offset, _, after in PATCHES[game]:
            for ins in md.disasm(bytes.fromhex(after), IMAGE_BASE + offset):
                out[ins.address] = (ins.mnemonic, ins.op_str, ins.size)
        return out

    @staticmethod
    def _follow(code: dict, va: int, zf: bool) -> int:
        """Follow the patch's jumps from va with the drop test's ZF; return the first non-jump VA."""
        for _ in range(16):
            if va not in code:
                return va
            mnemonic, operands, size = code[va]
            if mnemonic == "jmp":
                va = int(operands, 16)
            elif mnemonic == "je":
                va = int(operands, 16) if zf else va + size
            elif mnemonic == "jne":
                va = int(operands, 16) if not zf else va + size
            else:
                return va
        raise AssertionError("the patch's jumps loop")

    def test_the_drop_test_compares_the_drops_return_address_at_its_depth(self) -> None:
        for game in GAMES:
            va, depth, drop_return, _, _ = DROP_TEST[game]
            with self.subTest(game=game):
                code = self._decode(game)
                self.assertEqual(code[va][:2], ("cmp", f"dword ptr [esp + {depth:#x}], {drop_return:#x}"))
                # it is the only stack test the patch makes
                stack_tests = [a for a, (m, o, _) in code.items()
                               if m == "cmp" and o.startswith("dword ptr [esp") and ", 0x" in o]
                self.assertEqual(stack_tests, [va])

    def test_the_drop_and_every_other_entry_leave_the_test_where_they_should(self) -> None:
        for game in GAMES:
            va, _, _, drop_exit, other_exit = DROP_TEST[game]
            code = self._decode(game)
            with self.subTest(game=game):
                after_test = va + code[va][2]
                self.assertEqual(self._follow(code, after_test, zf=True), drop_exit)
                self.assertEqual(self._follow(code, after_test, zf=False), other_exit)

    def test_the_refusal_site_goes_to_the_drop_test_first(self) -> None:
        for game in ("vv2", "vv3", "vv4", "vv5"):
            va = DROP_TEST[game][0]
            site = IMAGE_BASE + PATCHES[game][0][0]
            code = self._decode(game)
            with self.subTest(game=game):
                first = site if site == va else int(code[site][1], 16)
                if site != va:
                    self.assertEqual(code[site][0], "jmp")
                self.assertEqual(first, va)

    def test_vv1_block_recomputes_the_duration_then_tests_for_the_drop(self) -> None:
        code = self._decode("vv1")
        instructions = [code[a][:2] for a in sorted(code)]
        offset, _, after = PATCHES["vv1"][0]
        self.assertEqual(IMAGE_BASE + offset + len(bytes.fromhex(after)), VV1_BC_MANUAL_HOOK_VA)
        self.assertIn(("call", "0x402f10"), instructions)
        self.assertIn(("lea", "edi, [eax + 5]"), instructions)
        self.assertIn(("cmp", "dword ptr [ebp + 0x350], 2"), instructions)
        # the drop does the stock compare itself and resumes past the hook;
        # everything else falls into 0x43DD03 (the stock compare, or the hook)
        self.assertEqual(instructions[-1], ("jmp", hex(VV1_BC_ACCEPT_VA)))
        self.assertIn(("jne", hex(VV1_BC_MANUAL_HOOK_VA)), instructions)

    def test_vv1_does_not_touch_birth_control_bytes(self) -> None:
        mine = set().union(*map(set, _patch_ranges("vv1")))
        birth_control = _catalog()["vv1_birth_control"]
        for patch in birth_control.patches:
            start = int(patch["offset"], 0)
            theirs = range(start, start + len(bytes.fromhex(patch["before"])))
            with self.subTest(birth_control_offset=patch["offset"]):
                self.assertFalse(mine & set(theirs))
        self.assertEqual(birth_control.patches[0]["offset"].upper(), "0X3DD03")

    def test_vv2_vv3_do_not_touch_birth_control_bytes(self) -> None:
        for game in ("vv2", "vv3"):
            mine = set().union(*map(set, _patch_ranges(game)))
            for patch in _catalog()[f"{game}_birth_control"].patches:
                start = int(patch["offset"], 0)
                theirs = range(start, start + len(bytes.fromhex(patch["before"])))
                with self.subTest(game=game, birth_control_offset=patch["offset"]):
                    self.assertFalse(mine & set(theirs))


# ---------------------------------------------------------------------------
# Rendered executables -- need the stock executables
# ---------------------------------------------------------------------------


def _other_public_ids(game: str) -> list[str]:
    return [p.id for p in _public() if p.game_id == game and p.id != feature_id(game)]


def _public_dependencies(patch_id: str) -> set[str]:
    """A public patch's public prerequisites, transitively (the GUI ticks them)."""
    public = {p.id for p in _public()}
    out: set[str] = set()
    pending = [patch_id]
    while pending:
        current = pending.pop()
        for dependency in _catalog()[current].raw.get("dependencies") or ():
            if dependency in public and dependency not in out:
                out.add(dependency)
                pending.append(dependency)
    return out


def _with_prerequisites(game: str, patch_id: str) -> tuple[str, ...]:
    wanted = {patch_id} | _public_dependencies(patch_id)
    return tuple(i for i in _other_public_ids(game) if i in wanted)


def _without_dependents(game: str, patch_id: str) -> tuple[str, ...]:
    """The public catalog minus a patch and everything that requires it."""
    return tuple(
        i for i in _other_public_ids(game)
        if i != patch_id and patch_id not in _public_dependencies(i)
    )


def _assert_only_own_bytes(case: unittest.TestCase, game: str, without: bytes, with_: bytes) -> None:
    own = set().union(*map(set, _patch_ranges(game)))
    allowed = own | set(pe_checksum_range(with_))
    case.assertEqual(len(without), len(with_))
    changed: set[int] = set()
    chunk = 0x1000
    for start in range(0, len(with_), chunk):
        a, b = with_[start : start + chunk], without[start : start + chunk]
        if a != b:
            changed.update(start + i for i in range(len(a)) if a[i] != b[i])
    case.assertTrue(changed - set(pe_checksum_range(with_)))
    case.assertEqual(changed - allowed, set())
    for offset, before, after in PATCHES[game]:
        length = len(bytes.fromhex(after))
        case.assertEqual(with_[offset : offset + length], bytes.fromhex(after))
        case.assertEqual(without[offset : offset + length], bytes.fromhex(before))


class ManualDropRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        missing = [game for game in GAMES if not stock_path(game).exists()]
        if missing:
            self.skipTest(f"stock executables absent: {missing}")

    def test_stock_bytes_match_the_pinned_preimages(self) -> None:
        for game in GAMES:
            data = stock_path(game).read_bytes()
            for offset, before, _ in PATCHES[game]:
                with self.subTest(game=game, offset=hex(offset)):
                    self.assertEqual(data[offset : offset + len(bytes.fromhex(before))].hex().upper(),
                                     before.upper())

    def test_the_padding_it_uses_is_padding_and_nothing_reaches_it(self) -> None:
        """VV3/VV4/VV5's drop test lives in padding no stock code branches into."""
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.skipdata = True
        for game in ("vv3", "vv4", "vv5"):
            data = stock_path(game).read_bytes()
            pe = pefile.PE(data=data, fast_load=True)
            mapped = _mapped(data)
            text = pe.sections[0]
            caves = [r for r in _patch_ranges(game)[1:]]
            targets = set()
            for ins in md.disasm(mapped[text.VirtualAddress:text.VirtualAddress + text.Misc_VirtualSize],
                                 IMAGE_BASE + text.VirtualAddress):
                if (ins.mnemonic.startswith("j") or ins.mnemonic == "call") and ins.op_str.startswith("0x"):
                    targets.add(int(ins.op_str, 16))
            for cave in caves:
                with self.subTest(game=game, cave=hex(cave.start)):
                    self.assertTrue(set(data[cave.start:cave.stop]) <= {0x90, 0xCC, 0x00})
                    self.assertFalse({IMAGE_BASE + o for o in cave} & targets)

    def test_alone_and_with_the_whole_catalog_it_changes_only_its_own_bytes(self) -> None:
        for game in GAMES:
            everything = tuple(_other_public_ids(game))
            for mode in MODES:
                with self.subTest(game=game, mode=mode, selection="alone"):
                    _assert_only_own_bytes(self, game, render(game, mode, ()),
                                           render(game, mode, (feature_id(game),)))
                with self.subTest(game=game, mode=mode, selection="whole public catalog"):
                    _assert_only_own_bytes(self, game, render(game, mode, everything),
                                           render(game, mode, everything + (feature_id(game),)))

    def test_with_every_other_patch_of_its_game(self) -> None:
        """Pairwise with each public patch (and its prerequisites) in every
        mode, and the whole catalog minus each patch (and its dependents).

        The feature's bytes are disjoint from every other claim, so the
        patched image differs from the same selection without it only in its
        own bytes and the PE checksum.
        """
        for game in GAMES:
            others = _other_public_ids(game)
            for mode in MODES:
                for other in others:
                    pair = _with_prerequisites(game, other)
                    with self.subTest(game=game, mode=mode, with_=other):
                        _assert_only_own_bytes(
                            self, game, render(game, mode, pair),
                            render(game, mode, pair + (feature_id(game),)))
                    if mode != "stock":
                        # The whole catalog is checked in every mode above;
                        # leave-one-out repeats it per patch in one mode.
                        continue
                    rest = _without_dependents(game, other)
                    with self.subTest(game=game, mode=mode, all_but=other):
                        _assert_only_own_bytes(
                            self, game, render(game, mode, rest),
                            render(game, mode, rest + (feature_id(game),)))


# ---------------------------------------------------------------------------
# The real routes, executed
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAVE_EMULATOR, "requires unicorn and pefile")
class ManualDropEmulationTests(unittest.TestCase):
    """The player's drop, from the drop's own call site."""

    def setUp(self) -> None:
        missing = [game for game in GAMES if not stock_path(game).exists()]
        if missing:
            self.skipTest(f"stock executables absent: {missing}")

    def _each(self):
        for game in GAMES:
            for mode in MODES:
                for label, ids in variants(game).items():
                    yield game, mode, label, ids, render(game, mode, ids)

    def test_a_woman_aged_50_or_older(self) -> None:
        """Refused where the game (or VV1 Birth Control) refuses her, only
        AFTER the stock conception roll; conceives with the patch."""
        for game, mode, label, ids, image in self._each():
            for woman in (OLD_WOMAN, EDGE_WOMAN):
                for name, scenario in (
                    ("she is dropped on him", Scenario(woman, MAN)),
                    ("he is dropped on her", Scenario(MAN, woman)),
                ):
                    with self.subTest(game=game, mode=mode, build=label, age=woman.age, drop=name):
                        outcome = emulate_drop(image, game, scenario)
                        self.assertTrue(outcome.handler_entered)
                        self.assertTrue(outcome.conception_roll_reached)
                        self.assertEqual(outcome.conceived, not refuses_50(game, ids))

    def test_a_woman_just_under_50_is_never_refused(self) -> None:
        for game, mode, label, ids, image in self._each():
            with self.subTest(game=game, mode=mode, build=label):
                self.assertTrue(emulate_drop(image, game, Scenario(JUST_UNDER_WOMAN, MAN)).conceived)
                self.assertTrue(emulate_drop(image, game, Scenario(MAN, JUST_UNDER_WOMAN)).conceived)

    def test_the_patch_conceives_exactly_as_stock_would(self) -> None:
        """Same writer call, same arguments, as a younger woman in stock."""
        for game in GAMES:
            for mode in MODES:
                patched = render(game, mode, (feature_id(game),))
                stock = render(game, mode, ())
                for dropped, target in ((OLD_WOMAN, MAN), (MAN, OLD_WOMAN)):
                    with self.subTest(game=game, mode=mode, dropped_female=dropped.female):
                        young = Scenario(*(replace(v, age=400) if v.female else v for v in (dropped, target)))
                        old = Scenario(dropped, target)
                        reference = emulate_drop(stock, game, young)
                        result = emulate_drop(patched, game, old)
                        self.assertTrue(reference.conceived and result.conceived)
                        self.assertEqual(result.writer_args, reference.writer_args)
                        self.assertEqual(result.rng_calls, reference.rng_calls)

    def test_a_younger_womans_drop_is_unchanged(self) -> None:
        for game in GAMES:
            for mode in MODES:
                for label, ids in variants(game).items():
                    if feature_id(game) not in ids:
                        continue
                    base = tuple(i for i in ids if i != feature_id(game))
                    for scenario in (Scenario(YOUNG_WOMAN, MAN), Scenario(MAN, JUST_UNDER_WOMAN),
                                     Scenario(YOUNG_WOMAN, MAN, rng=FAIL_CONCEPTION_ROLL)):
                        with self.subTest(game=game, mode=mode, build=label, scenario=scenario):
                            before = emulate_drop(render(game, mode, base), game, scenario)
                            after = emulate_drop(render(game, mode, ids), game, scenario)
                            self.assertEqual((after.conceived, after.writer_args, after.rng_calls),
                                             (before.conceived, before.writer_args, before.rng_calls))

    def test_the_parenting_preference_is_not_a_gate_in_any_build(self) -> None:
        """Unchecked on both: same result, and the field is never read."""
        for game, mode, label, ids, image in self._each():
            with self.subTest(game=game, mode=mode, build=label):
                unchecked = emulate_drop(image, game, Scenario(
                    replace(YOUNG_WOMAN, parenting_checked=False),
                    replace(MAN, parenting_checked=False)))
                checked = emulate_drop(image, game, Scenario(YOUNG_WOMAN, MAN))
                self.assertTrue(unchecked.conceived)
                self.assertEqual(unchecked.writer_args, checked.writer_args)
                self.assertEqual(unchecked.preference_reads, [])
                self.assertEqual(checked.preference_reads, [])

    def test_no_parenting_skill_is_not_a_gate_in_any_build(self) -> None:
        """Zero skill on both conceives on passing rolls, stock and patched."""
        for game, mode, label, ids, image in self._each():
            with self.subTest(game=game, mode=mode, build=label):
                outcome = emulate_drop(image, game, Scenario(
                    replace(OLD_WOMAN if not refuses_50(game, ids) else YOUNG_WOMAN, skill=0),
                    replace(MAN, skill=0)))
                self.assertTrue(outcome.conceived)

    def test_the_stock_rolls_still_decide(self) -> None:
        for game, mode, label, ids, image in self._each():
            for woman in (YOUNG_WOMAN, OLD_WOMAN):
                with self.subTest(game=game, mode=mode, build=label, age=woman.age, roll="conception"):
                    outcome = emulate_drop(image, game, Scenario(woman, MAN, rng=FAIL_CONCEPTION_ROLL))
                    self.assertTrue(outcome.conception_roll_reached)
                    self.assertFalse(outcome.conceived)
                with self.subTest(game=game, mode=mode, build=label, age=woman.age, roll="skill attempt"):
                    outcome = emulate_drop(image, game, Scenario(
                        replace(woman, skill=0), replace(MAN, skill=0), rng=FAIL_SKILL_ATTEMPT))
                    self.assertFalse(outcome.conception_roll_reached)
                    self.assertFalse(outcome.conceived)

    def test_the_dropped_villagers_skill_sets_the_chance(self) -> None:
        """Both stock rolls read the DROPPED villager's Parenting skill.

        With technology level 1 the conception roll passes when RNG(300) is at
        most that skill, so a draw of 40 passes for a dropped villager with 50
        skill and fails for one with none -- whichever partner that is.
        """
        draw = ((300, (40,)),)
        for game, mode, label, ids, image in self._each():
            skilled_man = replace(MAN, skill=50)
            unskilled_woman = replace(OLD_WOMAN if not refuses_50(game, ids) else YOUNG_WOMAN, skill=0)
            with self.subTest(game=game, mode=mode, build=label):
                self.assertTrue(emulate_drop(image, game, Scenario(skilled_man, unskilled_woman, rng=draw)).conceived)
                self.assertFalse(emulate_drop(image, game, Scenario(unskilled_woman, skilled_man, rng=draw)).conceived)

    def test_every_other_stock_rule_still_refuses(self) -> None:
        for game, mode, label, ids, image in self._each():
            rules = list(KEPT_RULES)
            if game in POPULATION_RULE_GAMES:
                rules.append(("population check", Scenario(OLD_WOMAN, MAN, population=7)))
            for rule, scenario in rules:
                with self.subTest(game=game, mode=mode, build=label, rule=rule):
                    outcome = emulate_drop(image, game, scenario)
                    self.assertFalse(outcome.conceived)
                    self.assertFalse(outcome.conception_roll_reached)


@unittest.skipUnless(HAVE_EMULATOR, "requires unicorn and pefile")
class AutonomousPairingTests(unittest.TestCase):
    """Villagers pairing up on their own: the same handler, and the patch must not change it."""

    def setUp(self) -> None:
        missing = [game for game in GAMES if not stock_path(game).exists()]
        if missing:
            self.skipTest(f"stock executables absent: {missing}")

    def test_it_reaches_the_same_handler_after_a_walk(self) -> None:
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    outcome = emulate_autonomous(render(game, mode, (feature_id(game),)), game,
                                                 Scenario(YOUNG_WOMAN, MAN))
                    self.assertEqual(outcome.head_step_after_start, ROUTES[game].walk_step)
                    self.assertTrue(outcome.handler_entered)
                    self.assertTrue(outcome.conceived)

    def test_a_woman_aged_50_or_older_is_refused_exactly_as_without_the_patch(self) -> None:
        for game in GAMES:
            for mode in MODES:
                for label, ids in variants(game).items():
                    image = render(game, mode, ids)
                    for dropped, target in ((OLD_WOMAN, MAN), (EDGE_WOMAN, MAN), (MAN, OLD_WOMAN),
                                            (MAN, EDGE_WOMAN), (OLD_WOMAN, OLD_MAN)):
                        with self.subTest(game=game, mode=mode, build=label,
                                          initiator="woman" if dropped.female else "man",
                                          age=(dropped if dropped.female else target).age):
                            outcome = emulate_autonomous(image, game, Scenario(dropped, target))
                            self.assertTrue(outcome.handler_entered)
                            self.assertTrue(outcome.conception_roll_reached)
                            self.assertEqual(outcome.conceived, not handler_refuses_50(game, ids))

    def test_the_patch_changes_nothing_about_autonomous_pairing(self) -> None:
        """Every pairing, both ways round, with and without the patch: same result, same rolls."""
        for game in GAMES:
            for mode in MODES:
                for label, ids in variants(game).items():
                    if feature_id(game) not in ids:
                        continue
                    base = tuple(i for i in ids if i != feature_id(game))
                    for dropped, target in AUTONOMOUS_PAIRS:
                        for rng in ((), FAIL_CONCEPTION_ROLL):
                            scenario = Scenario(dropped, target, rng=rng)
                            with self.subTest(game=game, mode=mode, build=label, scenario=scenario):
                                before = emulate_autonomous(render(game, mode, base), game, scenario)
                                after = emulate_autonomous(render(game, mode, ids), game, scenario)
                                self.assertEqual(
                                    (after.conceived, after.writer_args, after.rng_calls),
                                    (before.conceived, before.writer_args, before.rng_calls))

    def test_the_drop_is_never_on_the_autonomous_stack(self) -> None:
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    outcome = emulate_autonomous(render(game, mode, (feature_id(game),)), game,
                                                 Scenario(YOUNG_WOMAN, MAN))
                    self.assertEqual(outcome.drop_slots, [])


@unittest.skipUnless(HAVE_EMULATOR, "requires unicorn and pefile")
class DropTestDepthTests(unittest.TestCase):
    """The drop's return address is exactly where the patch looks for it."""

    def setUp(self) -> None:
        missing = [game for game in GAMES if not stock_path(game).exists()]
        if missing:
            self.skipTest(f"stock executables absent: {missing}")

    def test_the_drops_return_address_sits_at_the_tested_depth(self) -> None:
        for game in GAMES:
            depth = DROP_TEST[game][1]
            for mode in MODES:
                for label, ids in variants(game).items():
                    with self.subTest(game=game, mode=mode, build=label):
                        outcome = emulate_drop(render(game, mode, ids), game, Scenario(YOUNG_WOMAN, MAN))
                        self.assertEqual(outcome.drop_slots, [depth])

    def test_with_the_whole_public_catalog(self) -> None:
        """Nothing else in the catalog moves the drop's call chain or the handler."""
        for game in GAMES:
            everything = tuple(_other_public_ids(game)) + (feature_id(game),)
            refuses_autonomously = handler_refuses_50(game, everything)
            for mode in MODES:
                image = render(game, mode, everything)
                with self.subTest(game=game, mode=mode, route="drop"):
                    outcome = emulate_drop(image, game, Scenario(OLD_WOMAN, MAN))
                    self.assertEqual(outcome.drop_slots, [DROP_TEST[game][1]])
                    self.assertTrue(outcome.conceived)
                with self.subTest(game=game, mode=mode, route="autonomous"):
                    outcome = emulate_autonomous(image, game, Scenario(OLD_WOMAN, MAN))
                    self.assertTrue(outcome.conception_roll_reached)
                    self.assertEqual(outcome.conceived, not refuses_autonomously)


@unittest.skipUnless(HAVE_EMULATOR, "requires unicorn and pefile")
class VV1DurationBlockEquivalenceTests(unittest.TestCase):
    """The rewritten VV1 block must leave the same state as stock.

    Stock runs 0x43DCD8 -> 0x43DD03 (cmp) -> 0x43DD0A. The patch runs its own
    block and then, for the player's drop, its own copy of that comparison to
    0x43DD0A; for every other entry it falls into 0x43DD03 exactly as stock.
    EDI (the embrace duration pushed to the writer), ESP, ZF (the carrier
    branch that follows), and the RNG(3) re-rolls must match for every
    combination of the two saved hut ids it compares.
    """

    def setUp(self) -> None:
        if not stock_path("vv1").exists():
            self.skipTest("stock VV1 executable absent")

    def _run(self, image: bytes, first_roll: int, locals_: tuple[int, int], carrier: int, drop: bool):
        mu, _ = _new_machine(image)
        esp = STACK + STACK_SIZE // 2
        # At 0x43DCD8 the RNG(3) argument is still on the stack; the two hut
        # ids the block compares are at [esp+0x18] and [esp+0x14] here (stock
        # reads the first before its add esp,4 and the second after it). The
        # drop's return address is 0x30 above the popped stack.
        mu.mem_write(esp, struct.pack("<I", 3))
        mu.mem_write(esp + 0x18, struct.pack("<I", locals_[0]))
        mu.mem_write(esp + 0x14, struct.pack("<I", locals_[1]))
        mu.mem_write(esp + 4 + 0x30, struct.pack("<I", DROP_TEST["vv1"][2] if drop else 0x445575))
        record = DATA + 0x1000
        mu.mem_write(record + 0x350, struct.pack("<I", carrier))
        mu.reg_write(UC_X86_REG_EBP, record)
        mu.reg_write(UC_X86_REG_EAX, first_roll)
        mu.reg_write(UC_X86_REG_EDI, 0x5A5A5A5A)
        mu.reg_write(UC_X86_REG_ESP, esp)
        rolls: list[int] = []
        visits: list[int] = []

        def on_code(uc, address, size, _user):  # noqa: ANN001
            if bytes(uc.mem_read(address, 1))[0] == 0xE8:
                rel = struct.unpack("<i", bytes(uc.mem_read(address + 1, 4)))[0]
                if address + 5 + rel != 0x402F10:
                    raise AssertionError(f"unexpected call at {address:#x}")
                rolls.append(struct.unpack("<I", bytes(uc.mem_read(uc.reg_read(UC_X86_REG_ESP), 4)))[0])
                uc.reg_write(UC_X86_REG_EAX, 2)
                uc.reg_write(UC_X86_REG_EIP, address + 5)
            if address == VV1_BC_MANUAL_HOOK_VA:
                visits.append(address)
                uc.emu_stop()  # stock's compare, or Birth Control's hook: as stock from here

        mu.hook_add(UC_HOOK_CODE, on_code)
        mu.emu_start(VV1_BLOCK_VA, VV1_BC_ACCEPT_VA, count=200)
        stopped_at = mu.reg_read(UC_X86_REG_EIP)
        zf = (mu.reg_read(UC_X86_REG_EFLAGS) >> 6) & 1
        state = (mu.reg_read(UC_X86_REG_EDI), mu.reg_read(UC_X86_REG_ESP) - esp, tuple(rolls))
        return state, zf, stopped_at, visits

    def test_same_duration_stack_and_branch_as_stock(self) -> None:
        pairs = ((0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (7, 7), (0xFFFFFFFF, 0xFFFFFFFF))
        for mode in MODES:
            stock = render("vv1", mode, ())
            for ids in ((feature_id("vv1"),), ("vv1_birth_control", feature_id("vv1"))):
                patched = render("vv1", mode, ids)
                for pair in pairs:
                    for carrier in (1, 2):
                        for drop in (True, False):
                            with self.subTest(mode=mode, build=ids, huts=pair, carrier=carrier, drop=drop):
                                expected, _, stock_stop, stock_visits = self._run(stock, 1, pair, carrier, drop)
                                actual, zf, stop, visits = self._run(patched, 1, pair, carrier, drop)
                                self.assertEqual(stock_visits, [VV1_BC_MANUAL_HOOK_VA])
                                self.assertEqual(actual, expected)
                                if drop:
                                    # past the hook, with the stock comparison's flags
                                    self.assertEqual(visits, [])
                                    self.assertEqual(stop, VV1_BC_ACCEPT_VA)
                                    self.assertEqual(zf, int(carrier == 2))
                                else:
                                    self.assertEqual(visits, [VV1_BC_MANUAL_HOOK_VA])


def _new_machine(image: bytes):
    mapped = _mapped(image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(IMAGE_BASE, ((len(mapped) + 0xFFF) & ~0xFFF) + 0x10000)
    mu.mem_write(IMAGE_BASE, mapped)
    mu.mem_map(DATA, DATA_SIZE)
    mu.mem_map(STACK, STACK_SIZE)
    mu.mem_map(SENTINEL, 0x1000)
    return mu, mapped


if __name__ == "__main__":
    unittest.main()
