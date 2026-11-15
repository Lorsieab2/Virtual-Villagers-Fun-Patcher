"""A carrier's delivery, run from each stock executable's own code in unicorn (all five games).

Used by tests/test_sex_change_carrier_all.py.  The stock executable (inputs/vvN-stock-copy) is mapped whole;
its imports go to stubs (the few the delivery reaches are answered, anything else stops the run).  A village
holds a carrier (record CARRIER) and the father (record FATHER), both living adults; the carrier's pregnancy
field holds the age at conception, the litter field the babies.  `deliver` runs the pregnancy tick's delivery
block -- from its "is this villager carrying" test to the join where a villager not delivering goes on -- with
every routine the block calls (the creators, the twin/triplet copies, rand, the clocks, the messages) run for
real, and records every read of the carrier's sex field (a memory-read hook, whoever reads it).
"""
from __future__ import annotations

import struct
from pathlib import Path

import pefile

try:
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_UNMAPPED, UC_MODE_32, Uc, UcError
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX,
        UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )
    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - the tests skip
    HAVE_UNICORN = False

ROOT = Path(__file__).resolve().parents[1]
EXE = {
    "vv1": ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe",
    "vv2": ROOT / "inputs" / "vv2-stock-copy" / "Virtual Villagers - The Lost Children.exe",
    "vv3": ROOT / "inputs" / "vv3-stock-copy" / "Virtual Villagers - The Secret City.exe",
    "vv4": ROOT / "inputs" / "vv4-stock-copy" / "Virtual Villagers - The Tree of Life.exe",
    "vv5": ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe",
}

# Per game: the record layout and the delivery block.
#   entry / join: the block's "carrying?" test and the join a villager not delivering goes on from
#   (tests/test_slot_guards_count_records.py names the same sites);
#   sex, male, female: the sex field (native/shared/sex_change.h); pregnant: the age at conception
#   (the babies, i.e. the litter, are the dword after it); clock: the age field the block compares with;
#   active / age / head / body / name / child_father / child_mother: native/parentage_export GAME_LAYOUTS;
#   health: the field each game's population count tests (VV3 0x45E90A, VV4 0x46762B,
#   VV5 0x471416); container / base: VV3-VV5's villager table (a global) and record zero in it.
GAMES = {
    "vv1": dict(stride=0x3D8, slots=256, entry=0x42EF15, join=0x42F0CE, sex=0x350, male=1, female=2,
                pregnant=0x358, clock=0x34C, active=0x28, health=0x344, age=0x348, head=0x360, body=0x364,
                name=0x370, hands=0x3C, empty_hands=0x13, family=0x36C, array_of_world=0xADE8, world_of_array=0x3E010,
                speed=0xA318),
    "vv2": dict(stride=0xE48C, slots=256, entry=0x43BDFE, join=0x43BF91, sex=0x538, male=1, female=2,
                pregnant=0x540, clock=0x534, active=0x30, health=0x52C, age=0x530, head=0x548, body=0x54C,
                name=0x564, father_name=0x5C0, father_head=0x5E0, father_body=0x5DC,
                child_father=0x57D, child_mother=0x596, hands=0x44, empty_hands=0x1A, array_of_world=0x305A4,
                world_of_array=0xE574D4, speed=0x2EB08),
    "vv3": dict(stride=0x1F8C, slots=150, entry=0x460341, join=0x460512, sex=0xDC8, male=0, female=1,
                pregnant=0xE8C, clock=0xE74, active=0xF10, health=0xE78, age=0xDC4, head=0xDF0, body=0xDF4,
                name=0xDD4, father_name=0xE48, father_head=0xE68, father_body=0xE64,
                child_father=0xDF8, child_mother=0xE11, container=0x59E110, base=0x14, esi=0xDCC,
                game_object=(0x4B309C, 0x12FD4, 0x12F20)),
    "vv4": dict(stride=0x2E3C, slots=150, entry=0x4687E4, join=0x468A1A, sex=0x1B90, male=0, female=1,
                pregnant=0x1C4C, clock=0x1C3C, active=0x1CC4, health=0x1C40, age=0x1B8C, head=0x1BB8,
                body=0x1BBC, name=0x1B9C, father_name=0x1C10, father_head=0x1C30, father_body=0x1C2C,
                child_father=0x1BC0, child_mother=0x1BD9, container=0x50E568, base=0x44, esi=0x1C3C,
                game_object=(0x4CB51C, 0x171C8, 0x17110), self_pointers=(0x1B80, 0x1B88), crt_rand=0x471CF8,
                locale_update=0x472604),
    "vv5": dict(stride=0x2F44, slots=150, entry=0x4730AF, join=0x4732E1, sex=0x1B90, male=0, female=1,
                pregnant=0x1C4C, clock=0x1C3C, active=0x1CD4, health=0x1C40, age=0x1B8C, head=0x1BB8,
                body=0x1BBC, name=0x1B9C, father_name=0x1C10, father_head=0x1C30, father_body=0x1C2C,
                child_father=0x1BC0, child_mother=0x1BD9, container=0x554148, base=0x48, esi=0x1C3C,
                game_object=(0x4DACE0, 0x17E3C, 0x17D7C), self_pointers=(0x1B80, 0x1B88), crt_rand=0x47CFD8,
                locale_update=0x47D8E4),
}

CARRIER, FATHER = 3, 5
CONCEIVED = 500                 # the carrier's age at conception (the pregnancy field)
ARRAY = 0x10000000              # VV1 / VV2: the villager array
WORLD = 0x30000000              # VV1 / VV2: the world object
VILLAGE = 0x31000000            # VV1 / VV2: the village object the tick runs on ([+0] world, [+4] array)
STACK = 0x32000000
STACK_TOP = STACK + 0x20000 - 0x200
API = 0x0E000000
RETURN = 0x0BAD0000
HEAP = 0x40000000


def available(game: str) -> bool:
    return HAVE_UNICORN and EXE[game].is_file()


class Village:
    def __init__(self, game: str):
        self.game = game
        self.g = g = GAMES[game]
        pe = pefile.PE(str(EXE[game]))
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        image = pe.get_memory_mapped_image()
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        uc.mem_map(0x400000, size)
        uc.mem_write(0x400000, image[:size])
        uc.mem_map(0, 0x1000)                         # fs:[0] (the SEH prologues), FS base 0
        uc.mem_map(STACK, 0x20000)
        uc.mem_map(RETURN, 0x1000)
        uc.mem_map(API, 0x10000)
        uc.mem_map(HEAP, 0x00400000)
        self._heap = HEAP
        self.api: dict[int, str] = {}
        n = 0
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                stub = API + 16 * n
                n += 1
                self.api[stub] = imp.name.decode() if imp.name else f"ordinal {imp.ordinal}"
                uc.mem_write(imp.address, struct.pack("<I", stub))
        if "container" in g:
            self.records = g["container"] + g["base"]
            # The game object (its getter builds it on first use, reading the settings): made here, the game speed 1.
            where, size, speed = g["game_object"]
            obj = self.alloc(size)
            self.put(obj + speed, 1)
            self.put(where, obj)
            # VV4 / VV5: each record's own pointers to itself (+0x1B88 is read as the record: its preferences at
            # +0x1E60, 0x461964; +0x1B80 the same object, the reset's label 0x468C7D).
            for field in g.get("self_pointers", ()):
                for i in range(g["slots"]):
                    self.put(self.rec(i) + field, self.rec(i))
        else:
            uc.mem_map(ARRAY, (g["slots"] * g["stride"] + 0x20FFF) & ~0xFFF)
            uc.mem_map(WORLD, 0x40000)
            uc.mem_map(VILLAGE, 0x1000)
            self.records = ARRAY
            self.put(VILLAGE, WORLD)
            self.put(VILLAGE + 4, ARRAY)
            self.put(WORLD + g["array_of_world"], ARRAY)     # the population count's array
            self.put(ARRAY + g["world_of_array"], WORLD)     # the world, read off the array
            self.put(WORLD + g["speed"], 1)                  # the game speed
        self._ptd()
        self.calls: list[str] = []
        self.sex_reads: list[tuple[int, int]] = []    # (eip, value read) of every read of the carrier's sex
        self.fault = None
        uc.hook_add(UC_HOOK_CODE, self._api, begin=API, end=API + 0x10000)
        if "crt_rand" in g:
            # VV4 / VV5: the CRT's rand() needs the CRT's start-up (its locks); the same generator in Python
            # (seed * 214013 + 2531011, bits 16..30), from srand(1).
            self._seed = 1
            uc.hook_add(UC_HOOK_CODE, self._rand, begin=g["crt_rand"], end=g["crt_rand"])
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped)
        sex_va = self.rec(CARRIER) + g["sex"]
        uc.hook_add(UC_HOOK_MEM_READ, self._read, begin=sex_va - 3, end=sex_va + 3)
        self._sex_va = sex_va
        # Two living adults: the carrier and the father.
        for i, female in ((CARRIER, True), (FATHER, False)):
            self.adult(i, female, b"Carrier" if i == CARRIER else b"Father")

    def crowd(self, n: int = 8) -> None:
        """n more living adults (records 10..), half of each sex: more than six villagers, so the delivery skips
        each game's small-village sex balance (the only routine on the path that reads anyone's sex)."""
        for k in range(n):
            self.adult(10 + k, k % 2 == 0, b"Villager%d" % k)

    def _ptd(self) -> int:
        if not hasattr(self, "_ptd_block"):
            self._ptd_block = self.alloc(0x400)
            self.put(self._ptd_block + 0x14, 1)       # the thread's rand seed, as srand(1)
            # The VV4 / VV5 CRT keeps FlsGetValue in a TLS slot (TlsGetValue returns it) and calls it:
            # a two-instruction FlsGetValue that answers the block (mov eax, block; ret 4).
            self._fls = RETURN + 0x100
            self.uc.mem_write(self._fls, b"\xB8" + struct.pack("<I", self._ptd_block) + b"\xC2\x04\x00")
            update = self.g.get("locale_update")
            if update:
                # The thread's locale is the global one (its _LocaleUpdate compares the thread's +0x6C and +0x68
                # with the globals at +0x24 and +0x41 and, when equal, takes no lock).
                self.put(self._ptd_block + 0x6C, self.get(self.get(update + 0x26)))
                self.put(self._ptd_block + 0x68, self.get(self.get(update + 0x43)))
        return self._ptd_block

    def alloc(self, n: int) -> int:
        at = self._heap
        self._heap += (n + 0x1F) & ~0xF
        self.uc.mem_write(at, bytes(n))
        return at

    # ---- memory ------------------------------------------------------------------------------------------------
    def rec(self, i: int) -> int:
        return self.records + i * self.g["stride"]

    def put(self, va: int, value: int) -> None:
        self.uc.mem_write(va, struct.pack("<I", value & 0xFFFFFFFF))

    def get(self, va: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(va, 4))[0]

    def text(self, va: int, n: int = 0x18) -> bytes:
        return bytes(self.uc.mem_read(va, n)).split(b"\0")[0]

    def adult(self, i: int, female: bool, name: bytes) -> None:
        g, r = self.g, self.rec(i)
        self.uc.mem_write(r + g["active"], b"\x01")
        self.put(r + g["health"], 90)
        self.put(r + g["age"], 400)
        self.put(r + g["clock"], 400)
        self.put(r + g["sex"], g["female"] if female else g["male"])
        self.put(r + g["head"], 4 if female else 7)
        self.put(r + g["body"], 5 if female else 8)
        self.uc.mem_write(r + g["name"], name + b"\0")
        if "hands" in g:
            self.put(r + g["hands"], g["empty_hands"])

    def carrier(self, sex_male: bool, litter: int = 0) -> None:
        """Make CARRIER carry FATHER's babies (litter: VV1/VV2 0 one baby, 2 twins, 3 triplets; VV3-VV5 1,2,3),
        conceived at age CONCEIVED; then their sex field set to male (the change mid-pregnancy) or kept female."""
        g, r, f = self.g, self.rec(CARRIER), self.rec(FATHER)
        self.put(r + g["pregnant"], CONCEIVED)
        self.put(r + g["pregnant"] + 4, litter)
        if "father_name" in g:              # what each game's conception writes on the carrier (VV2-VV5)
            self.uc.mem_write(r + g["father_name"], b"Father\0")
            self.put(r + g["father_head"], self.get(f + g["head"]))
            self.put(r + g["father_body"], self.get(f + g["body"]))
        else:                               # A New Home's conception 0x43BBC0: the father's family, the selectors
            self.put(f + 0x36C, 17)
            self.put(r + 0x36C, 23)
            self.put(r + 0x394, 17)
            self.put(r + 0x38C, 1)
            self.put(r + 0x390, 0)
        self.set_sex(sex_male)

    def set_sex(self, male: bool) -> None:
        """The carrier's sex field written, as native/shared/sex_change.h writes it (nothing else on the record)."""
        self.put(self.rec(CARRIER) + self.g["sex"], self.g["male"] if male else self.g["female"])

    # ---- hooks -------------------------------------------------------------------------------------------------
    def _read(self, uc, access, address, size, value, user):
        if address <= self._sex_va < address + size:
            self.sex_reads.append((uc.reg_read(UC_X86_REG_EIP), self.get(self._sex_va)))

    def _rand(self, uc, address, size, user):
        self._seed = (self._seed * 214013 + 2531011) & 0xFFFFFFFF
        esp = uc.reg_read(UC_X86_REG_ESP)
        uc.reg_write(UC_X86_REG_EAX, (self._seed >> 16) & 0x7FFF)
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, self.get(esp))

    def _unmapped(self, uc, access, address, size, value, user):
        self.fault = (uc.reg_read(UC_X86_REG_EIP), address, access)
        return False

    def _api(self, uc, address, size, user):
        name = self.api.get(address)
        if name is None:
            return
        self.calls.append(name)
        answers = {"timeGetTime": (1_000_000, 0), "GetTickCount": (1_000_000, 0), "HeapFree": (1, 12),
                   "GetProcessHeap": (0x1234, 0), "SHGetSpecialFolderPathA": (0, 16),
                   # the CRT's per-thread data (rand's seed): one block for the one thread
                   "GetLastError": (0, 0), "SetLastError": (0, 4), "TlsGetValue": (self._fls, 4),
                   "FlsGetValue": (self._ptd(), 4), "GetCurrentThreadId": (1, 0),
                   "GetModuleHandleA": (0, 4), "GetModuleHandleW": (0, 4)}
        if name == "GetSystemTimeAsFileTime":         # a fixed clock (the CRT's time())
            uc.mem_write(self.get(uc.reg_read(UC_X86_REG_ESP) + 4), struct.pack("<Q", 0x01D0000000000000))
            answers[name] = (0, 4)
        if name == "GetModuleFileNameA":              # (module, buffer, size): the game's own path
            uc.mem_write(self.get(uc.reg_read(UC_X86_REG_ESP) + 8), b"C:\\Game\\Game.exe\0")
            answers[name] = (16, 12)
        if name == "HeapAlloc":                     # HeapAlloc(heap, flags, bytes): a fresh zeroed block
            n = (self.get(uc.reg_read(UC_X86_REG_ESP) + 12) + 0x1F) & ~0xF
            answers[name] = (self._heap, 12)
            uc.mem_write(self._heap, bytes(n))
            self._heap += n
        if name not in answers:
            self.fault = ("api", name)
            uc.emu_stop()
            return
        value, pop = answers[name]
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = self.get(esp)
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, ret)

    # ---- the delivery ------------------------------------------------------------------------------------------
    def snapshot(self) -> bytes:
        return bytes(self.uc.mem_read(self.records, self.g["slots"] * self.g["stride"]))

    def deliver(self, age: int) -> dict:
        """The carrier at `age` (the field the block compares with): run the block from its test to its join."""
        g, r = self.g, self.rec(CARRIER)
        self.put(r + g["clock"], age)
        self.put(r + g["age"], age)
        esp = STACK_TOP - 0x100
        container = g.get("container", 0)
        frame = [0] * 0x40
        # VV3-VV5: the tick's frame holds the villager table (VV3 [esp+0x10] for the creator, [esp+0x14] for the
        # twin copy 0x45F1D0, whose free-record scan reads +0xF24 from it: record zero's +0xF10, in use).
        frame[0x14 // 4] = container
        frame[0x10 // 4] = container
        for k, value in enumerate(frame):
            self.put(esp + 4 * k, value)
        regs = {UC_X86_REG_ESP: esp}
        if self.game in ("vv1", "vv2"):
            regs.update({UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EDI: CARRIER * g["stride"]})
        else:
            regs.update({UC_X86_REG_ESI: r + g["esi"], UC_X86_REG_EBP: container, UC_X86_REG_EBX: container})
        for reg, value in regs.items():
            self.uc.reg_write(reg, value)
        self.sex_reads.clear()
        before = self.living()
        try:
            self.uc.emu_start(g["entry"], g["join"], count=5_000_000)
        except UcError as error:
            raise AssertionError(f"{self.game}: {error} fault={self.fault!r} eip={self.uc.reg_read(UC_X86_REG_EIP):#x}")
        if self.fault is not None or self.uc.reg_read(UC_X86_REG_EIP) != g["join"]:
            raise AssertionError(f"{self.game}: stopped at {self.uc.reg_read(UC_X86_REG_EIP):#x}, fault={self.fault!r}")
        babies = [i for i in self.living() if i not in before]
        return dict(babies=babies, pregnant=self.get(r + g["pregnant"]), litter=self.get(r + g["pregnant"] + 4),
                    sex_reads=list(self.sex_reads), calls=list(self.calls))

    def living(self) -> list[int]:
        g = self.g
        return [i for i in range(g["slots"]) if self.uc.mem_read(self.rec(i) + g["active"], 1)[0]]
