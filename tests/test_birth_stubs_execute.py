"""VV2, VV4 and VV5 birth stubs, RUN from the rendered executable.

The Births and Conceptions log's `Birth` record is written from each game's
three child-creation sites (first child, twin, triplet).  At each site the
parentage feature replaces the instruction after the creating call with a jump
to a per-site stub, which calls a shared body and then replays the displaced
bytes and jumps back:

    VV2  0x43BE93 -> 0x43BE9A   mov ecx,[esi] ; mov ebp,[esi+4] ; mov ebx,eax
         0x43BEE4 -> 0x43BEEB   (the same seven bytes)
         0x43BF30 -> 0x43BF37   (the same seven bytes)
         record = [ESI+4] + index * 0xE48C      (ESI is the village object)
    VV4  0x468858 -> 0x46885D   mov edi,eax ; cmp edi,-1
         0x4688F3 -> 0x4688F8   mov ebp,eax ; cmp ebp,-1
         0x468996 -> 0x46899E   mov edi,eax ; imul eax,eax,0x2E3C
         record = 0x50E568 (container) + 0x44 + index * 0x2E3C
    VV5  0x473125 -> 0x47312A   mov edi,eax ; cmp edi,-1
         0x4731C4 -> 0x4731C9   mov ebp,eax ; cmp ebp,-1
         0x47325F -> 0x473267   mov edi,eax ; imul eax,eax,0x2F44
         record = 0x554148 (container) + 0x48 + index * 0x2F44

The body saves every register (pushad), reads the index from the pushad copy of
EAX, skips a child that was never allocated (-1), and calls
WriteParentageBirth(game id, 0,-1,-1, 0,-1,-1, 0,-1,-1, child record), stdcall.

Each site is executed in an emulator from the patched jump, with the new
child's index in EAX, and compared against the same bytes executed in a render
WITHOUT the feature: the companion must be called exactly once with the record
of that index, the game must resume at exactly the first byte after the
displaced instructions, and every register and the arithmetic flags must match
the unpatched game.  A child that was never allocated (EAX = -1) must reach the
game's own code with no companion call.  Only the loader imports and the export
are faked; everything else is the rendered code.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import capstone
import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EFLAGS, UC_X86_REG_EIP, UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

VILLAGE = 0x0E000000          # VV2's village object: [+0] and [+4] are read
VV2_RECORDS = 0x0D000000      # what VV2's [village+4] holds: record zero

GAMES = {
    "vv2": dict(
        game_id=2, exe="Virtual Villagers - The Lost Children.exe",
        feature="vv2_write_parentage_log", first_record=VV2_RECORDS, stride=0xE48C,
        # Three movs set no flags, and every site is followed at once by
        # `call 0x403200`, so the flags the body leaves behind are dead.
        flags_live=False,
        sites=((0x43BE93, "8B0E8B6E048BD8", "first child"),
               (0x43BEE4, "8B0E8B6E048BD8", "twin"),
               (0x43BF30, "8B0E8B6E048BD8", "triplet")),
    ),
    "vv4": dict(
        game_id=4, exe="Virtual Villagers - The Tree of Life.exe",
        feature="vv4_write_parentage_log", first_record=0x50E568 + 0x44, stride=0x2E3C, flags_live=True,
        sites=((0x468858, "8BF883FFFF", "first child"),
               (0x4688F3, "8BE883FDFF", "twin"),
               (0x468996, "8BF869C03C2E0000", "triplet")),
    ),
    "vv5": dict(
        game_id=5, exe="Virtual Villagers - New Believers.exe",
        feature="vv5_write_parentage_log", first_record=0x554148 + 0x48, stride=0x2F44, flags_live=True,
        sites=((0x473125, "8BF883FFFF", "first child"),
               (0x4731C4, "8BE883FDFF", "twin"),
               (0x47325F, "8BF869C0442F0000", "triplet")),
    ),
}
# VV5's parentage page is re-emitted as an overlay at a different address when
# Origins is co-selected, so its stubs are exercised in both layouts. VV2's
# log depends on Origins and lives in the Origins page as composition patches.
LAYOUTS = {
    "vv2": {"with origins": []},
    "vv4": {"alone": []},
    "vv5": {"alone": [], "with origins": ["vv5_enable_origins_exclusive_features"]},
}
# VV2's feature applies as seven composition patches over Origins: the
# conception rejection retarget, the success-join divert, the conception
# trampoline, the birth body, and the three birth splices.
VV2_COMPOSITION = {0x4B98A, 0x4BAD8, 0xB241A, 0xB2558, 0x3BE93, 0x3BEE4, 0x3BF30}

SCRATCH = 0x0F000000
FAKE_MODULE = SCRATCH + 0x100
FAKE_LOAD = SCRATCH + 0x140
FAKE_PROC = SCRATCH + 0x180
FAKE_EXPORT = SCRATCH + 0x1C0
FAKE_OTHER = SCRATCH + 0x200
STACK_TOP = 0x10800000
EXPORT = b"WriteParentageBirth"
FLAGS = 0x8D5   # CF PF AF ZF SF OF
SENTINELS = dict(ebx=0x11111111, ecx=0x22222222, edx=0x33333333, esi=VILLAGE,
                 edi=0x55555555, ebp=0x66666666)
REGS = dict(eax=UC_X86_REG_EAX, ebx=UC_X86_REG_EBX, ecx=UC_X86_REG_ECX, edx=UC_X86_REG_EDX,
            esi=UC_X86_REG_ESI, edi=UC_X86_REG_EDI, ebp=UC_X86_REG_EBP, esp=UC_X86_REG_ESP)

_cache: dict = {}


def _render(game: str, extra: list[str], with_feature: bool = True) -> bytes:
    key = (game, tuple(extra), with_feature)
    if key not in _cache:
        cfg = GAMES[game]
        build = next(b for b in vfp.load_builds() if b.id == game)
        wanted = ([cfg["feature"]] if with_feature else []) + extra
        ids = vfp.resolve_fun_patch_ids(wanted, game_id=game) if wanted else []
        image, applied = vfp.render_patched_bytes(STOCK / cfg["exe"], build, "immediate_fixed", ids)
        owners = {r["owner"] for r in applied}
        assert (f"feature:{cfg['feature']}" in owners) == with_feature, owners
        _cache[key] = bytes(image)
    return _cache[key]


def _file_offset(image: bytes, va: int) -> int:
    return pefile.PE(data=image, fast_load=True).get_offset_from_rva(va - 0x400000)


def _read(image: bytes, va: int, n: int) -> bytes:
    o = _file_offset(image, va)
    return image[o:o + n]


def _decode_site(image: bytes, site: int, displaced: bytes) -> dict:
    """The jump at the site, the stub it reaches, and what the stub does."""
    entry = _read(image, site, len(displaced))
    (jmp,) = list(CS.disasm(entry[:5], site))
    assert jmp.mnemonic == "jmp", jmp
    stub = int(jmp.op_str, 16)
    code = _read(image, stub, 5 + len(displaced) + 5)
    call = next(CS.disasm(code[:5], stub))
    back = next(CS.disasm(code[5 + len(displaced):], stub + 5 + len(displaced)))
    return dict(entry=entry, stub=stub, call=call, replay=code[5:5 + len(displaced)], back=back)


def _load(image: bytes) -> Uc:
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    mu.mem_map(SCRATCH, 0x1000)
    mu.mem_map(VILLAGE, 0x1000)
    mu.mem_write(VILLAGE, struct.pack("<II", 0x77777777, VV2_RECORDS))
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)
    # Every import is a trap; the three loader calls get their contracts.
    stubs = {
        b"GetModuleHandleA": (FAKE_MODULE, b"\xB8" + struct.pack("<I", FAKE_MODULE) + b"\xC2\x04\x00"),
        b"LoadLibraryA": (FAKE_LOAD, b"\xB8" + struct.pack("<I", FAKE_MODULE) + b"\xC2\x04\x00"),
        b"GetProcAddress": (FAKE_PROC, b"\xB8" + struct.pack("<I", FAKE_EXPORT) + b"\xC2\x08\x00"),
    }
    mu.mem_write(FAKE_OTHER, b"\xF4")
    mu.mem_write(FAKE_EXPORT, b"\xC2\x2C\x00")    # ret 0x2C: eleven stdcall dwords
    found = set()
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        for imp in entry.imports:
            target = FAKE_OTHER
            if imp.name in stubs:
                target, body = stubs[imp.name]
                mu.mem_write(target, body)
                found.add(imp.name)
            mu.mem_write(imp.address, struct.pack("<I", target))
    assert found == set(stubs), found
    return mu


def _execute(image: bytes, site: int, length: int, index: int, page: range | None) -> dict:
    mu = _load(image)
    calls, names, trace = [], [], {"return": None, "left_page": False}

    def hook(uc, address, size, _):
        if address == FAKE_PROC:
            esp = uc.reg_read(UC_X86_REG_ESP)
            name_ptr = struct.unpack("<I", uc.mem_read(esp + 8, 4))[0]
            names.append(bytes(uc.mem_read(name_ptr, 32)).split(b"\0")[0])
        elif address == FAKE_EXPORT:
            esp = uc.reg_read(UC_X86_REG_ESP)
            calls.append(struct.unpack("<11i", uc.mem_read(esp + 4, 44)))
        elif address == FAKE_OTHER:
            raise AssertionError("an unexpected import was called")
        elif page is not None:
            if address in page:
                trace["left_page"] = True
            elif trace["left_page"] and trace["return"] is None and address < 0x500000:
                trace["return"] = address

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.reg_write(UC_X86_REG_ESP, STACK_TOP - 0x200)
    mu.reg_write(UC_X86_REG_EAX, index & 0xFFFFFFFF)
    for name, value in SENTINELS.items():
        mu.reg_write(REGS[name], value)
    mu.reg_write(UC_X86_REG_EFLAGS, 0x2)
    mu.emu_start(site, site + length, count=5000)
    # emu_start stops BEFORE the instruction at `until`, so no hook sees it:
    # a stub that jumped straight there is recorded from the final EIP.
    if trace["left_page"] and trace["return"] is None:
        trace["return"] = mu.reg_read(UC_X86_REG_EIP)
    return dict(
        regs={name: mu.reg_read(reg) for name, reg in REGS.items()},
        flags=mu.reg_read(UC_X86_REG_EFLAGS) & FLAGS,
        calls=calls, names=names, returned_to=trace["return"],
    )


def _page_of(image: bytes, va: int) -> range:
    pe = pefile.PE(data=image, fast_load=True)
    for s in pe.sections:
        lo = 0x400000 + s.VirtualAddress
        if lo <= va < lo + s.Misc_VirtualSize:
            return range(lo, lo + s.Misc_VirtualSize)
    raise AssertionError(f"{va:#x} is in no section")


class BirthStubsExecute(unittest.TestCase):
    def test_vv2_log_is_the_seven_composition_patches_over_origins_and_all_are_rendered(self):
        feature = next(p for p in vfp.load_fun_patches() if p.id == GAMES["vv2"]["feature"]).raw
        patches = feature["composition_patches"]["vv2_enable_origins_exclusive_features"]
        self.assertEqual({int(p["offset"], 16) for p in patches}, VV2_COMPOSITION)
        self.assertEqual(len(patches), len(VV2_COMPOSITION))
        image = _render("vv2", [])
        for p in patches:
            o = int(p["offset"], 16)
            after = bytes.fromhex(p["after"])
            with self.subTest(offset=p["offset"]):
                self.assertEqual(image[o:o + len(after)], after)

    def test_each_site_jumps_to_a_stub_that_replays_its_own_bytes_and_returns_after_them(self):
        for game, cfg in GAMES.items():
            stock = (STOCK / cfg["exe"]).read_bytes()
            for layout, extra in LAYOUTS[game].items():
                patched = _render(game, extra)
                for site, displaced_hex, what in cfg["sites"]:
                    displaced = bytes.fromhex(displaced_hex)
                    with self.subTest(game=game, layout=layout, site=what):
                        self.assertEqual(_read(stock, site, len(displaced)), displaced, "stock bytes moved")
                        s = _decode_site(patched, site, displaced)
                        self.assertEqual(s["entry"][5:], b"\x90" * (len(displaced) - 5))
                        self.assertEqual(s["call"].mnemonic, "call")
                        self.assertEqual(s["replay"], displaced, "the stub must replay the displaced bytes verbatim")
                        self.assertEqual(s["back"].mnemonic, "jmp")
                        self.assertEqual(int(s["back"].op_str, 16), site + len(displaced),
                                         "the stub must resume at the first byte after the displaced ones")

    def test_each_stub_logs_the_childs_record_and_leaves_the_game_state_unchanged(self):
        for game, cfg in GAMES.items():
            unpatched = _render(game, [], with_feature=False)
            for layout, extra in LAYOUTS[game].items():
                patched = _render(game, extra)
                for site, displaced_hex, what in cfg["sites"]:
                    n = len(bytes.fromhex(displaced_hex))
                    page = _page_of(patched, _decode_site(patched, site, bytes.fromhex(displaced_hex))["stub"])
                    for index in (0, 7, 148):
                        with self.subTest(game=game, layout=layout, site=what, index=index):
                            want = _execute(unpatched, site, n, index, None)
                            got = _execute(patched, site, n, index, page)
                            self.assertEqual(want["calls"], [])
                            self.assertEqual(got["names"], [EXPORT])
                            self.assertEqual(len(got["calls"]), 1, "WriteParentageBirth once per child")
                            args = got["calls"][0]
                            self.assertEqual(args[0], cfg["game_id"])
                            self.assertEqual(args[1:10], (0, -1, -1, 0, -1, -1, 0, -1, -1))
                            self.assertEqual(args[10] & 0xFFFFFFFF, cfg["first_record"] + index * cfg["stride"],
                                             "the child's own record: record zero + index * stride")
                            self.assertEqual(got["returned_to"], site + n)
                            self.assertEqual(got["regs"], want["regs"])
                            if cfg["flags_live"]:
                                self.assertEqual(got["flags"], want["flags"])

    def test_a_child_that_was_never_allocated_is_not_logged(self):
        for game, cfg in GAMES.items():
            unpatched = _render(game, [], with_feature=False)
            for layout, extra in LAYOUTS[game].items():
                patched = _render(game, extra)
                for site, displaced_hex, what in cfg["sites"]:
                    n = len(bytes.fromhex(displaced_hex))
                    with self.subTest(game=game, layout=layout, site=what):
                        want = _execute(unpatched, site, n, -1, None)
                        got = _execute(patched, site, n, -1, None)
                        self.assertEqual(got["calls"], [])
                        self.assertEqual(got["regs"], want["regs"])
                        if cfg["flags_live"]:
                            self.assertEqual(got["flags"], want["flags"])


if __name__ == "__main__":
    unittest.main()
