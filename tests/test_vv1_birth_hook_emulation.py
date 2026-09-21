"""Emulate VV1's exact birth hook at all four child-creation sites.

The Show Parents row relies on the Origins row's birth hook handing the
Origins companion's Vv1Born the NEW CHILD's record and its MOTHER's, at every
place the pregnancy tick sub_42E900 creates a child.  The first version of
that hook sat inside sub_43C840, which only twins go through, and passed the
sibling as the mother; a Time Warp birth in the owner's village showed no
parents.  Byte pins prove the splices are where the design says; this test
proves what the patched bytes DO when the game reaches them:

  * Vv1Born receives (records + index*0x3D8, records + EDI) -- the child the
    creation routine returned in EAX and the mother the tick loops over --
    at all four sites, with the array read through [ESI+4].
  * The stub returns to the stock instruction after the seven displaced bytes
    with EAX, ESI, EDI, ESP and the flags-independent register rebuilds
    (ECX/EBX/EBP) exactly as stock would have them.
  * The fail-open paths (no DLL, no export, cached 1) leave every register
    and ESP intact too, and never call.
  * Nothing reads or writes outside the regions this test deliberately maps.

The creation routines, LoadLibraryA and GetProcAddress are replaced in the
emulated image by tiny fakes, so only the patch's own bytes are exercised.
Skipped (not failed) when the optional `unicorn` package is unavailable.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:  # optional dependency
    from unicorn import (
        UC_ARCH_X86,
        UC_HOOK_MEM_FETCH_UNMAPPED,
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
        UC_X86_REG_EIP,
        UC_X86_REG_ESI,
        UC_X86_REG_ESP,
    )

    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

try:
    import pefile

    HAVE_PEFILE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_PEFILE = False

STOCK = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"

IMAGE_BASE = 0x400000
RECORDS = 0x10000000     # the record array ([village + 4])
VILLAGE = 0x20000000     # the village object the tick keeps in ESI
STACK = 0x30000000
FAKES = 0x40000000       # fake LoadLibraryA / GetProcAddress / Vv1Born
RECORD_SIZE = 0x3D8

LOADLIBRARY_IAT = 0x457010
GETPROCADDRESS_IAT = 0x4570D4
BORN_CACHE = 0x491208    # scratch +0x208: 0 untried, 1 unavailable, else Vv1Born

FAKE_LOADLIBRARY = FAKES + 0x000
FAKE_GETPROC = FAKES + 0x040
FAKE_BORN = FAKES + 0x080
CAPTURE = FAKES + 0x800  # child, mother, call count
FAKE_MODULE = 0x7A000000
FAKE_LOADLIBRARY_NULL = FAKES + 0x100
FAKE_GETPROC_NULL = FAKES + 0x140

# (splice, the creation call before it, the routine it calls, which register
# gets [esi+4] and which gets eax in the displaced bytes)
SITES = (
    (0x42EF64, 0x42EF5F, 0x43C350, "ebx", "ebp"),
    (0x42EFD5, 0x42EFD0, 0x43C350, "ebp", "ebx"),
    (0x42F026, 0x42F021, 0x43C840, "ebp", "ebx"),
    (0x42F072, 0x42F06D, 0x43C840, "ebp", "ebx"),
)


def _render() -> bytes:
    import vv_fun_patcher as patcher

    builds = {build.id: build for build in patcher.load_builds()}
    ids = [item.id for item in patcher.load_fun_patches() if item.game_id == "vv1"]
    rendered, _ = patcher.render_patched_bytes(STOCK, builds["vv1"], "stock", ids)
    return bytes(rendered)


def _le(value: int) -> bytes:
    return int(value).to_bytes(4, "little", signed=False)


class _Run:
    def __init__(self, image: bytes):
        self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu = self.mu
        size = ((len(image) + 0xFFF) & ~0xFFF) + 0x10000
        mu.mem_map(IMAGE_BASE, size)
        mu.mem_write(IMAGE_BASE, image)
        mu.mem_map(RECORDS, 0x400000)
        mu.mem_map(VILLAGE, 0x10000)
        mu.mem_map(STACK, 0x100000)
        mu.mem_map(FAKES, 0x10000)
        mu.mem_write(VILLAGE + 4, _le(RECORDS))
        # LoadLibraryA(name): eax = FAKE_MODULE; ret 4
        mu.mem_write(FAKE_LOADLIBRARY, b"\xB8" + _le(FAKE_MODULE) + b"\xC2\x04\x00")
        # GetProcAddress(module, name): eax = FAKE_BORN; ret 8
        mu.mem_write(FAKE_GETPROC, b"\xB8" + _le(FAKE_BORN) + b"\xC2\x08\x00")
        # the failing variants return 0
        mu.mem_write(FAKE_LOADLIBRARY_NULL, b"\x31\xC0\xC2\x04\x00")
        mu.mem_write(FAKE_GETPROC_NULL, b"\x31\xC0\xC2\x08\x00")
        # Vv1Born(child, mother) __stdcall: capture both, count, eax = 1; ret 8
        mu.mem_write(
            FAKE_BORN,
            b"\x8B\x44\x24\x04" + b"\xA3" + _le(CAPTURE)            # mov eax,[esp+4]; mov [CAPTURE],eax
            + b"\x8B\x44\x24\x08" + b"\xA3" + _le(CAPTURE + 4)      # mov eax,[esp+8]; mov [CAPTURE+4],eax
            + b"\xFF\x05" + _le(CAPTURE + 8)                        # inc dword [CAPTURE+8]
            + b"\xB8" + _le(1) + b"\xC2\x08\x00",                   # mov eax,1; ret 8
        )
        self.faults: list[tuple[str, int]] = []

        def on_unmapped(uc, access, address, size, value, user_data):
            self.faults.append(("unmapped", address))
            return False

        mu.hook_add(UC_HOOK_MEM_READ_UNMAPPED, on_unmapped)
        mu.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, on_unmapped)
        mu.hook_add(UC_HOOK_MEM_FETCH_UNMAPPED, on_unmapped)
        self.iat(FAKE_LOADLIBRARY, FAKE_GETPROC)

    def iat(self, loadlibrary: int, getproc: int) -> None:
        self.mu.mem_write(LOADLIBRARY_IAT, _le(loadlibrary))
        self.mu.mem_write(GETPROCADDRESS_IAT, _le(getproc))

    def fake_routine(self, routine: int, child_index: int, arg_bytes: int) -> None:
        """Replace a creation routine by `mov eax, index; ret N`.  Once per
        _Run: unicorn keeps translated code, so a rewrite is not seen."""
        self.mu.mem_write(routine, b"\xB8" + _le(child_index) + b"\xC2" + arg_bytes.to_bytes(2, "little"))

    def read32(self, address: int) -> int:
        return int.from_bytes(self.mu.mem_read(address, 4), "little")

    def run(self, start: int, stop: int, *, eax: int, esi: int, edi: int, ebx: int, ebp: int, esp: int, ecx: int = 0x11111111):
        mu = self.mu
        mu.reg_write(UC_X86_REG_EAX, eax)
        mu.reg_write(UC_X86_REG_ECX, ecx)
        mu.reg_write(UC_X86_REG_ESI, esi)
        mu.reg_write(UC_X86_REG_EDI, edi)
        mu.reg_write(UC_X86_REG_EBX, ebx)
        mu.reg_write(UC_X86_REG_EBP, ebp)
        mu.reg_write(UC_X86_REG_ESP, esp)
        try:
            mu.emu_start(start, stop, count=4000)
        except UcError as exc:
            self.faults.append(("ucerror", int(mu.reg_read(UC_X86_REG_EIP))))
            raise AssertionError(f"emulation fault at {int(mu.reg_read(UC_X86_REG_EIP)):#x}: {exc}") from exc
        return {
            "eip": int(mu.reg_read(UC_X86_REG_EIP)),
            "eax": int(mu.reg_read(UC_X86_REG_EAX)),
            "ecx": int(mu.reg_read(UC_X86_REG_ECX)),
            "ebx": int(mu.reg_read(UC_X86_REG_EBX)),
            "ebp": int(mu.reg_read(UC_X86_REG_EBP)),
            "esi": int(mu.reg_read(UC_X86_REG_ESI)),
            "edi": int(mu.reg_read(UC_X86_REG_EDI)),
            "esp": int(mu.reg_read(UC_X86_REG_ESP)),
        }


@unittest.skipUnless(HAVE_UNICORN and HAVE_PEFILE, "unicorn/pefile not installed")
@unittest.skipUnless(STOCK.is_file(), "stock A New Home not present")
class BirthHookEmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rendered = _render()
        pe = pefile.PE(data=rendered, fast_load=True)
        pe.parse_data_directories()
        cls.image = bytes(pe.get_memory_mapped_image())
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.offsets = {int(p["offset"], 16) for p in manifest["patches"]}

    def _fresh(self) -> _Run:
        run = _Run(self.image)
        run.mu.mem_write(BORN_CACHE, _le(0))
        run.mu.mem_write(CAPTURE, b"\0" * 12)
        return run

    def _drive(self, run: _Run, site, *, child_index: int, mother_index: int, args: int = 5):
        """Start at the creation CALL before the splice and stop at splice + 7."""
        splice, call_at, routine, _array_reg, _eax_reg = site
        run.fake_routine(routine, child_index, 4 * args)
        mother_off = mother_index * RECORD_SIZE
        run.mu.mem_write(VILLAGE, _le(0x5A5A5A5A))          # [esi]: what the displaced mov ecx,[esi] reloads
        esp = STACK + 0x80000
        # the arguments the stock code pushed for the routine sit above the return address
        for k in range(args):
            esp -= 4
            run.mu.mem_write(esp, _le(0x600 + k))
        # stock loads ECX = [esi+4] (the record array) right before the call;
        # the build's safety cave in front of both sub_43C350 calls counts
        # the occupied records through it before creating
        return run.run(call_at, splice + 7, eax=0xDEADBEEF, esi=VILLAGE, edi=mother_off,
                       ebx=0x22222222, ebp=0x33333333, esp=esp, ecx=RECORDS), esp + 4 * args

    def test_the_splices_are_in_the_rendered_image(self):
        for splice, call_at, _routine, _a, _b in SITES:
            self.assertIn(splice - IMAGE_BASE, self.offsets)
            self.assertEqual(self.image[splice - IMAGE_BASE], 0xE9, f"jmp at {splice:#x}")
            self.assertEqual(self.image[splice - IMAGE_BASE + 5: splice - IMAGE_BASE + 7], b"\x90\x90")

    def test_every_site_hands_the_child_and_its_mother_to_vv1born(self):
        for site in SITES:
            splice, call_at, routine, array_reg, eax_reg = site
            with self.subTest(site=hex(splice)):
                run = self._fresh()
                args = 5 if routine == 0x43C350 else 1
                regs, esp_after = self._drive(run, site, child_index=37, mother_index=12, args=args)
                self.assertEqual(run.faults, [])
                self.assertEqual(regs["eip"], splice + 7, "resumed at the stock instruction after the displaced bytes")
                self.assertEqual(regs["esp"], esp_after, "the stack is exactly as after the stock call")
                self.assertEqual(regs["eax"], 37, "the child's index survives to the stock code")
                self.assertEqual(regs["esi"], VILLAGE)
                self.assertEqual(regs["edi"], 12 * RECORD_SIZE)
                self.assertEqual(regs["ecx"], 0x5A5A5A5A, "mov ecx,[esi] replayed")
                self.assertEqual(regs[array_reg], RECORDS, f"mov {array_reg},[esi+4] replayed")
                self.assertEqual(regs[eax_reg], 37, f"mov {eax_reg},eax replayed")
                self.assertEqual(run.read32(CAPTURE + 8), 1, "Vv1Born called exactly once")
                self.assertEqual(run.read32(CAPTURE), RECORDS + 37 * RECORD_SIZE, "the child's record")
                self.assertEqual(run.read32(CAPTURE + 4), RECORDS + 12 * RECORD_SIZE, "the mother's record")
                self.assertEqual(run.read32(BORN_CACHE), FAKE_BORN, "the export is cached")

    def test_the_cached_export_is_reused_and_the_mother_is_the_loop_record(self):
        run = self._fresh()
        # a cached export must be used as is: make resolving again impossible
        run.iat(FAKE_LOADLIBRARY_NULL, FAKE_GETPROC_NULL)
        run.mu.mem_write(BORN_CACHE, _le(FAKE_BORN))
        regs, _ = self._drive(run, SITES[1], child_index=4, mother_index=201)
        self.assertEqual(run.faults, [])
        self.assertEqual(run.read32(CAPTURE + 8), 1)
        self.assertEqual(run.read32(CAPTURE), RECORDS + 4 * RECORD_SIZE)
        self.assertEqual(run.read32(CAPTURE + 4), RECORDS + 201 * RECORD_SIZE)
        self.assertEqual(regs["eax"], 4)
        self.assertEqual(run.read32(BORN_CACHE), FAKE_BORN)

    def test_fail_open_paths_touch_nothing(self):
        for label, loadlibrary, getproc, cache_before, cache_after in (
            ("no DLL", FAKE_LOADLIBRARY_NULL, FAKE_GETPROC, 0, 1),
            ("no export", FAKE_LOADLIBRARY, FAKE_GETPROC_NULL, 0, 1),
            ("cached unavailable", FAKE_LOADLIBRARY, FAKE_GETPROC, 1, 1),
        ):
            for site in SITES:
                splice, _call_at, routine, array_reg, eax_reg = site
                with self.subTest(path=label, site=hex(splice)):
                    run = self._fresh()
                    run.iat(loadlibrary, getproc)
                    run.mu.mem_write(BORN_CACHE, _le(cache_before))
                    args = 5 if routine == 0x43C350 else 1
                    regs, esp_after = self._drive(run, site, child_index=9, mother_index=5, args=args)
                    self.assertEqual(run.faults, [])
                    self.assertEqual(regs["eip"], splice + 7)
                    self.assertEqual(regs["esp"], esp_after)
                    self.assertEqual(regs["eax"], 9)
                    self.assertEqual(regs["esi"], VILLAGE)
                    self.assertEqual(regs["edi"], 5 * RECORD_SIZE)
                    self.assertEqual(regs["ecx"], 0x5A5A5A5A)
                    self.assertEqual(regs[array_reg], RECORDS)
                    self.assertEqual(regs[eax_reg], 9)
                    self.assertEqual(run.read32(CAPTURE + 8), 0, "Vv1Born never called")
                    self.assertEqual(run.read32(BORN_CACHE), cache_after)


if __name__ == "__main__":
    unittest.main()
