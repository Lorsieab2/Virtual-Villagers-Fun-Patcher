"""Manual Drop-Breeding overrides Birth Control, all five games.

The owner: "If the player manually drops two villagers to breed, they should
be able to have a child regardless if the woman is over 50/unchecked
Parenting/has Parenting skill or not. Default-OFF. Owner's-Defaults ON."
Not a guarantee ("Normal chance, no blocks"), and "every existing stock rule
still applies!!!" -- only the blocks go, and only for the manual drop.

What each game's real manual pairing handler does was established by running
it, not by reading it (the handler is the routine the villager step
dispatcher calls for the manual pairing step; it owns the "These villagers
are both the same gender." refusal and the "drag an adult male villager onto
an adult female villager" tutorial):

    game  handler    pregnancy writer  woman-50+ refusal (stock)
    VV1   0x43DAD0   0x43BBC0          none; Birth Control's hook at 0x43DD03 adds one
    VV2   0x44F610   0x44B980          0x44F7C8..0x44F7FE, after the conception roll
    VV3   0x4584B0   0x4582A0          0x4586F3..0x45871B, after the conception roll
    VV4   0x460C10   0x460990          0x460E67..0x460E8D, after the conception roll
    VV5   0x4689A0   0x467D20          0x468BC4..0x468BEA, after the conception roll

Neither the Parenting preference nor a Parenting skill threshold is a gate on
the manual drop in any game: the emulated handlers never read the preference
field, and a villager with no Parenting skill conceives on a passing roll in
stock. Skill only feeds the two stock chances (the skill-attempt roll and the
RNG(300) conception roll), which stay. So the patch lifts exactly one thing,
the woman-aged-50-or-older refusal, and in VV1 -- where the game has none --
it steps around Birth Control's manual hook so that refusal is lifted when
both patches are ticked.

The emulator runs the handler from its entry on the rendered bytes, together
with the game's own Parenting skill-attempt routine (and VV4/VV5's float-to-int
helper). Every other call is a stub that pops its own arguments; the random
routine is scripted. A run ends at the call into the pregnancy writer (the pair
conceives) or at the handler's return (no conception).

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
        UC_X86_REG_ECX,
        UC_X86_REG_EDI,
        UC_X86_REG_EFLAGS,
        UC_X86_REG_EIP,
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


# The one byte patch per game, pinned independently of the manifest.
PATCHES = {
    "vv1": (
        0x3DCD8,
        "8BF88B44241883C40483C70585C0741B8B4C241085C974133BC8750F6A03E81552FCFF8BF883C40483C705",
        "598D78058B4424148B4C24103BC8750F85C0740B6A03E81D52FCFF598D780583BD5003000002EB0A909090",
    ),
    "vv2": (0x4F7C8, "8B8F38050000", "EB3590909090"),
    "vv3": (0x586F3, "8B8EC40D0000", "EB2790909090"),
    "vv4": (0x60E67, "B8E8030000", "EB25909090"),
    "vv5": (0x68BC4, "B8E8030000", "EB25909090"),
}
# (site VA, stock continuation the jump must land on)
JUMPS = {
    "vv2": (0x44F7C8, 0x44F7FF),
    "vv3": (0x4586F3, 0x45871C),
    "vv4": (0x460E67, 0x460E8E),
    "vv5": (0x468BC4, 0x468BEB),
}
VV1_BLOCK_VA = 0x43DCD8
VV1_BC_MANUAL_HOOK_VA = 0x43DD03
VV1_BC_ACCEPT_VA = 0x43DD0A  # where Birth Control's own accept path resumes too

# Whether the unpatched game (plus Birth Control when named) refuses a woman
# aged 50 or older on a manual drop.
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
    dropped: Villager
    target: Villager
    rng: tuple = ()  # ((limit, (values...)), ...); unlisted draws return 0
    population: int = 5
    food: int = 5000


@dataclass
class Outcome:
    conceived: bool
    writer_args: tuple
    rng_calls: list = field(default_factory=list)
    preference_reads: list = field(default_factory=list)

    @property
    def conception_roll_reached(self) -> bool:
        return 300 in self.rng_calls


@functools.lru_cache(maxsize=None)
def _mapped(image: bytes) -> bytes:
    return bytes(pefile.PE(data=image, fast_load=True).get_memory_mapped_image())


_ARG_BYTES: dict = {}


def _callee_arg_bytes(mapped: bytes, target: int) -> int:
    """The callee's own `ret N`, following a tail jump when it has none."""
    key = (hash(mapped), target)
    if key in _ARG_BYTES:
        return _ARG_BYTES[key]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    offset = target - IMAGE_BASE
    result = tail = None
    for ins in md.disasm(mapped[offset : offset + 0x4000], target):
        if ins.mnemonic == "ret":
            result = int(ins.op_str, 16) if ins.op_str else 0
            break
        if ins.mnemonic == "jmp" and ins.op_str.startswith("0x"):
            tail = int(ins.op_str, 16)
            if ins.address == target:
                break
        if ins.mnemonic == "int3":
            break
    if result is None:
        if tail is None:
            raise AssertionError(f"no ret found for callee {target:#x}")
        result = _callee_arg_bytes(mapped, tail)
    _ARG_BYTES[key] = result
    return result


def _new_machine(image: bytes):
    mapped = _mapped(image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(IMAGE_BASE, ((len(mapped) + 0xFFF) & ~0xFFF) + 0x10000)
    mu.mem_write(IMAGE_BASE, mapped)
    mu.mem_map(DATA, DATA_SIZE)
    mu.mem_map(STACK, STACK_SIZE)
    mu.mem_map(SENTINEL, 0x1000)
    return mu, mapped


def emulate_drop(image: bytes, game: str, scenario: Scenario) -> Outcome:
    layout = LAYOUTS[game]
    mu, mapped = _new_machine(image)

    def w32(addr: int, value: int) -> None:
        mu.mem_write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def r32(addr: int) -> int:
        return struct.unpack("<I", bytes(mu.mem_read(addr, 4)))[0]

    state = DATA + 0x00F00000  # zeroed state object for pointer-returning helpers
    if layout.array_stride is not None:
        dropped_index, target_index = 3, 7
        dropped = DATA + dropped_index * layout.array_stride
        target = DATA + target_index * layout.array_stride
        w32(DATA + layout.state_offset, state)
        w32(state + layout.state_food, scenario.food)
        w32(state + layout.state_tech, 1)
        finder_result = target_index
    else:
        dropped, target = DATA + 0x10000, DATA + 0x20000
        finder_result = target
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

    queues = {limit: list(values) for limit, values in scenario.rng}
    outcome = Outcome(False, ())
    faults: list[str] = []

    def stub_value(target_va: int, esp: int) -> int:
        if target_va == layout.partner_finder:
            return finder_result
        if target_va in layout.state_pointer_calls:
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

    def on_code(uc, address, size, _user):  # noqa: ANN001
        head = bytes(uc.mem_read(address, 2))
        if head[0] == 0xFF and (head[1] >> 3) & 7 == 2:
            faults.append(f"unexpected indirect call at {address:#x}")
            uc.emu_stop()
            return
        if head[0] != 0xE8:
            return
        rel = struct.unpack("<i", bytes(uc.mem_read(address + 1, 4)))[0]
        target_va = address + 5 + rel
        esp = uc.reg_read(UC_X86_REG_ESP)
        if target_va == layout.writer:
            outcome.conceived = True
            outcome.writer_args = tuple(r32(esp + 4 * i) for i in range(4))
            uc.emu_stop()
            return
        if target_va in layout.run_real:
            return
        if target_va == layout.rng:
            limit = r32(esp)
            outcome.rng_calls.append(limit)
            queue = queues.get(limit)
            uc.reg_write(UC_X86_REG_EAX, queue.pop(0) if queue else 0)
            uc.reg_write(UC_X86_REG_EIP, address + 5)
            return
        uc.reg_write(UC_X86_REG_EAX, stub_value(target_va, esp))
        uc.reg_write(UC_X86_REG_ESP, esp + _callee_arg_bytes(mapped, target_va))
        uc.reg_write(UC_X86_REG_EIP, address + 5)

    def on_unmapped(uc, access, address, size, value, _user):  # noqa: ANN001
        faults.append(f"unmapped access {address:#x}")
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

    esp = STACK + STACK_SIZE // 2
    w32(esp, SENTINEL)
    if layout.array_stride is not None:
        w32(esp + 4, dropped_index)
        mu.reg_write(UC_X86_REG_ECX, DATA)
    else:
        mu.reg_write(UC_X86_REG_ECX, dropped)
    mu.reg_write(UC_X86_REG_ESP, esp)
    try:
        mu.emu_start(layout.handler, SENTINEL, count=200000)
    except UcError as exc:
        faults.append(f"{exc} at {mu.reg_read(UC_X86_REG_EIP):#x}")
    if faults:
        raise AssertionError("; ".join(faults))
    if not outcome.conceived and mu.reg_read(UC_X86_REG_EIP) != SENTINEL:
        raise AssertionError("the handler neither conceived nor returned")
    return outcome


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


def variants(game: str) -> dict[str, tuple[str, ...]]:
    out = {"stock": (), "patch": (feature_id(game),)}
    if game in BIRTH_CONTROL_ADDS_REFUSAL:
        out["birth control"] = (f"{game}_birth_control",)
        out["birth control + patch"] = (f"{game}_birth_control", feature_id(game))
    return out


def refuses_50(game: str, ids: tuple[str, ...]) -> bool:
    if feature_id(game) in ids:
        return False
    return STOCK_REFUSES_50[game] or (
        f"{game}_birth_control" in ids and BIRTH_CONTROL_ADDS_REFUSAL.get(game, False)
    )


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
            offset, before, after = PATCHES[game]
            with self.subTest(game=game):
                record = _catalog()[feature_id(game)]
                self.assertEqual(
                    [(int(p["offset"], 0), p["before"].upper(), p["after"].upper())
                     for p in record.patches],
                    [(offset, before, after)],
                )
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
                    "Only the manual drop is changed",
                    "Off by default.",
                ):
                    self.assertIn(phrase, text)
        vv1 = _catalog()[feature_id("vv1")].description
        self.assertIn("only changes anything when Birth Control is also ticked", vv1)
        for game in ("vv2", "vv3"):
            self.assertIn("Works the same with or without Birth Control",
                          _catalog()[feature_id(game)].description)
        for game in ("vv4", "vv5"):
            self.assertIn("this game has no Birth Control patch",
                          _catalog()[feature_id(game)].description)

    def test_the_jumps_land_on_the_stock_continuation(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for game, (site, landing) in JUMPS.items():
            with self.subTest(game=game):
                after = bytes.fromhex(PATCHES[game][2])
                first = next(md.disasm(after, site))
                self.assertEqual(first.mnemonic, "jmp")
                self.assertEqual(int(first.op_str, 16), landing)
                self.assertLessEqual(site + len(after), landing)

    def test_vv1_block_does_the_stock_comparison_and_never_reaches_the_hook(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        after = bytes.fromhex(PATCHES["vv1"][2])
        instructions = [
            (ins.mnemonic, ins.op_str) for ins in md.disasm(after, VV1_BLOCK_VA)
        ]
        self.assertEqual(VV1_BLOCK_VA + len(after), VV1_BC_MANUAL_HOOK_VA)
        self.assertIn(("cmp", "dword ptr [ebp + 0x350], 2"), instructions)
        self.assertIn(("jmp", hex(VV1_BC_ACCEPT_VA)), instructions)
        self.assertIn(("call", "0x402f10"), instructions)
        for mnemonic, operand in instructions:
            if mnemonic.startswith("j"):
                self.assertNotEqual(int(operand, 16), VV1_BC_MANUAL_HOOK_VA)
                self.assertTrue(VV1_BLOCK_VA <= int(operand, 16) < VV1_BC_MANUAL_HOOK_VA
                                or int(operand, 16) == VV1_BC_ACCEPT_VA)
        # The last real instruction is the jump; the rest is padding.
        body = [i for i in instructions if i[0] != "nop"]
        self.assertEqual(body[-1], ("jmp", hex(VV1_BC_ACCEPT_VA)))

    def test_vv1_does_not_touch_birth_control_bytes(self) -> None:
        offset, before, _ = PATCHES["vv1"]
        mine = range(offset, offset + len(bytes.fromhex(before)))
        birth_control = _catalog()["vv1_birth_control"]
        for patch in birth_control.patches:
            start = int(patch["offset"], 0)
            theirs = range(start, start + len(bytes.fromhex(patch["before"])))
            with self.subTest(birth_control_offset=patch["offset"]):
                self.assertFalse(set(mine) & set(theirs))
        self.assertEqual(birth_control.patches[0]["offset"].upper(), "0X3DD03")


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
    offset, before, after = PATCHES[game]
    own = set(range(offset, offset + len(bytes.fromhex(after))))
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
    case.assertEqual(with_[offset : offset + len(bytes.fromhex(after))], bytes.fromhex(after))
    case.assertEqual(without[offset : offset + len(bytes.fromhex(before))], bytes.fromhex(before))


class ManualDropRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        missing = [game for game in GAMES if not stock_path(game).exists()]
        if missing:
            self.skipTest(f"stock executables absent: {missing}")

    def test_stock_bytes_match_the_pinned_preimages(self) -> None:
        for game in GAMES:
            offset, before, _ = PATCHES[game]
            with self.subTest(game=game):
                data = stock_path(game).read_bytes()
                self.assertEqual(data[offset : offset + len(bytes.fromhex(before))].hex().upper(), before)

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
# The real manual pairing handlers, executed
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAVE_EMULATOR, "requires unicorn and pefile")
class ManualDropEmulationTests(unittest.TestCase):
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
class VV1DurationBlockEquivalenceTests(unittest.TestCase):
    """The rewritten VV1 block must leave the same state at 0x43DD0A as stock.

    Stock runs 0x43DCD8 -> 0x43DD03 (cmp) -> 0x43DD0A; the patch runs its own
    block -> 0x43DD0A.  EDI (the embrace duration pushed to the writer), ESP,
    ZF (the carrier branch that follows), and the number of RNG(3) re-rolls
    must match for every combination of the two saved hut ids it compares.
    """

    def setUp(self) -> None:
        if not stock_path("vv1").exists():
            self.skipTest("stock VV1 executable absent")

    def _run(self, image: bytes, first_roll: int, locals_: tuple[int, int], carrier: int):
        mu, _ = _new_machine(image)
        esp = STACK + STACK_SIZE // 2
        # At 0x43DCD8 the RNG(3) argument is still on the stack; the two hut
        # ids the block compares are at [esp+0x18] and [esp+0x14] here (stock
        # reads the first before its add esp,4 and the second after it).
        mu.mem_write(esp, struct.pack("<I", 3))
        mu.mem_write(esp + 0x18, struct.pack("<I", locals_[0]))
        mu.mem_write(esp + 0x14, struct.pack("<I", locals_[1]))
        record = DATA + 0x1000
        mu.mem_write(record + 0x350, struct.pack("<I", carrier))
        mu.reg_write(UC_X86_REG_EBP, record)
        mu.reg_write(UC_X86_REG_EAX, first_roll)
        mu.reg_write(UC_X86_REG_EDI, 0x5A5A5A5A)
        mu.reg_write(UC_X86_REG_ESP, esp)
        rolls: list[int] = []

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

        visits: list[int] = []
        mu.hook_add(UC_HOOK_CODE, on_code)
        mu.emu_start(VV1_BLOCK_VA, VV1_BC_ACCEPT_VA, count=200)
        self.assertEqual(mu.reg_read(UC_X86_REG_EIP), VV1_BC_ACCEPT_VA)
        zf = (mu.reg_read(UC_X86_REG_EFLAGS) >> 6) & 1
        return (mu.reg_read(UC_X86_REG_EDI), mu.reg_read(UC_X86_REG_ESP) - esp, zf, tuple(rolls)), visits

    def test_same_duration_stack_and_branch_as_stock(self) -> None:
        pairs = ((0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (7, 7), (0xFFFFFFFF, 0xFFFFFFFF))
        for mode in MODES:
            stock = render("vv1", mode, ())
            for ids in ((feature_id("vv1"),), ("vv1_birth_control", feature_id("vv1"))):
                patched = render("vv1", mode, ids)
                for pair in pairs:
                    for carrier in (1, 2):
                        with self.subTest(mode=mode, build=ids, huts=pair, carrier=carrier):
                            expected, stock_visits = self._run(stock, 1, pair, carrier)
                            actual, patched_visits = self._run(patched, 1, pair, carrier)
                            self.assertEqual(actual, expected)
                            self.assertEqual(stock_visits, [VV1_BC_MANUAL_HOOK_VA])
                            self.assertEqual(patched_visits, [])


if __name__ == "__main__":
    unittest.main()
