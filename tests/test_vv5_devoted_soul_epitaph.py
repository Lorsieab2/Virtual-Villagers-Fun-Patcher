"""Charitable Soul Epitaph (New Believers; patch id vv5_devoted_soul_epitaph).

The stock picker and the change are described in
scripts/build_vv5_devoted_soul_epitaph_feature.py.  These tests check the
manifest against the generator and the stock bytes, decode the recoded block,
and run both the stock and the patched block in an emulator for every grave
job (-1..5) and every value the game's rand(100) can return, so each job's
epitaph distribution is measured rather than read off a description: a
Devotee gets the game's usual epitaph (string 0x305: "Respected Citizen",
or "Respected Devotee" with Guardians of Isola Rewrite) for exactly 50 of
the 100 values and "Charitable Soul" for the other 50, and no other job's
result changes.  The coin itself is checked too: rand(100) is the C
runtime's clock-seeded rand() % 100.

Tests that need the stock executable or unicorn skip when they are absent
(GitHub CI has no stock executables).
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher_gui import (  # noqa: E402
    default_fun_patch_selection,
    owners_default_fun_patch_selection,
    select_all_fun_patch_selection,
)

try:
    import capstone
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
        UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

PATCH_ID = "vv5_devoted_soul_epitaph"
MANIFEST = ROOT / "data" / "vv5_devoted_soul_epitaph_feature.json"
_spec = importlib.util.spec_from_file_location(
    "build_vv5_devoted_soul_epitaph_feature", ROOT / "scripts" / "build_vv5_devoted_soul_epitaph_feature.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

BUILD = next(b for b in patcher.load_builds() if b.id == "vv5")
STOCK = ROOT / "research" / "stock-executables" / BUILD.input_name
MODES = ("stock", "collection_progression", "immediate_fixed")
START, END, COPY, RAND = gen.START, gen.END, gen.COPY, gen.RAND
BASE = gen.IMAGE_BASE
CHARITABLE = "Charitable Soul"
FORMER = "Devoted Soul"           # v1.35.58-59; graves written with it stay as they are
RESPECTED = 0x305
# The stock pairs (first id: rand < 50, second: rand >= 50), by grave job.
STOCK_PAIRS = {0: 0x306, 1: 0x30A, 2: 0x30C, 3: 0x308, 4: 0x30E}


def stock_bytes() -> bytes:
    if not STOCK.is_file():
        raise unittest.SkipTest("stock New Believers exe not present in this checkout")
    return STOCK.read_bytes()


class ManifestTests(unittest.TestCase):
    def manifest(self) -> dict:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_one_same_length_edit_over_the_dispatch(self):
        m = self.manifest()
        self.assertEqual((m["id"], m["game_id"], m["name"]), (PATCH_ID, "vv5", "Charitable Soul Epitaph"))
        self.assertTrue(m["enabled"] and m["catalog_enabled"] and not m["catalog_hidden"])
        self.assertEqual(m["companion_files"], [])
        self.assertNotIn("dependencies", m)
        (p,) = m["patches"]
        self.assertEqual(int(p["offset"], 16), START - BASE)
        self.assertEqual(len(p["before"]), len(p["after"]))
        self.assertEqual(len(p["after"]) // 2, END - START)
        self.assertEqual(bytes.fromhex(p["after"]), gen.build_block())

    def test_the_manifest_is_what_the_generator_writes(self):
        stock = stock_bytes()
        expected = json.dumps(gen.feature(gen.build_block(), gen.stock_block(stock)), indent=2, ensure_ascii=False) + "\n"
        self.assertEqual(MANIFEST.read_bytes().decode("utf-8"), expected)

    def test_the_text_fits_the_grave_epitaph(self):
        block = gen.build_block()
        self.assertIn(CHARITABLE.encode() + b"\0", block)
        self.assertNotIn(FORMER.encode(), block)
        self.assertLess(len(CHARITABLE), 0x20)       # char[0x20] at entry +0x38, strncpy limit 0x20
        # No longer than the stock epitaphs the grave dialog already shows in the same place.
        self.assertLessEqual(len(CHARITABLE), len("Parent, Teacher, Friend"))

    def test_the_recoded_block_decodes_to_the_intended_instructions(self):
        if not HAVE_EMULATOR:
            self.skipTest("capstone/unicorn not installed")
        block = gen.build_block()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        got = []
        for ins in md.disasm(block, START):
            got.append(f"{ins.mnemonic} {ins.op_str}".strip())
            if len(got) == 18:
                break
        table = START + block.index(gen.FIRST_IDS + gen.CHARITABLE_SOUL)
        string = table + 6
        self.assertEqual(got, [
            "mov eax, dword ptr [esi + 0x28]", "cmp eax, 5", "ja 0x464e19",
            f"movzx ebx, byte ptr [eax + {table:#x}]", "push 0x64", "call 0x403660", "pop ecx",
            "xor ecx, ecx", "cmp eax, 0x32", "setge cl", "cmp ebx, 5", "jne 0x464dbc", "jecxz 0x464dbc",
            "push 0x20", f"mov eax, {string:#x}", "jmp 0x464e28",
            "lea ecx, [ecx + ebx + 0x300]", "jmp 0x464e19",
        ])
        self.assertEqual(block[table - START: table - START + 6], bytes([6, 0x0A, 0x0C, 8, 0x0E, 5]))
        self.assertEqual(block[string - START: string - START + 16], b"Charitable Soul\0")
        self.assertEqual(set(block[string - START + 16:]), {0xCC})


    def test_the_usual_epitaph_is_the_games_string_so_guardians_of_isola_shows_its_own(self):
        """The under-50 half is string 0x305 fetched as stock, never a text the
        patch carries: the stock Assets/sm.xml says "Respected Citizen" there and
        Guardians of Isola Rewrite's says "Respected Devotee"."""
        import re
        texts = {}
        for side in ("base", "new"):
            xml = (ROOT / "data" / "guardians_of_isola" / side / "Assets" / "sm.xml").read_bytes().decode("latin-1")
            texts[side] = re.search(r'<Text id="eEulogyDefault">\s*(.*?)\s*</Text>', xml, re.S).group(1)
        self.assertEqual(texts, {"base": "Respected Citizen", "new": "Respected Devotee"})
        block = gen.build_block()
        for usual in texts.values():
            self.assertNotIn(usual.encode(), block)
        self.assertIn("the game's usual epitaph (\"Respected Citizen\", or \"Respected Devotee\" with Guardians of "
                      "Isola Rewrite) and \"Charitable Soul\"", self.manifest()["description"])

    def test_graves_written_as_devoted_soul_stay_and_nothing_checks_an_epitaph(self):
        """v1.35.58-59 graves keep "Devoted Soul": no code in the patcher, its
        companions or its checker carries either text to hold a grave to (only
        the generator, which puts "Charitable Soul" into the block), so nothing
        can flag or rewrite one."""
        self.assertIn("keep that epitaph", self.manifest()["description"])
        roots = [ROOT / "src", ROOT / "native", ROOT / "scripts"]
        for root in roots:
            for path in root.rglob("*"):
                if path.suffix not in (".py", ".c", ".h", ".inc") or path.name == "build_vv5_devoted_soul_epitaph_feature.py":
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for epitaph in (FORMER, CHARITABLE):        # as a string literal, in either language
                    self.assertFalse(f'"{epitaph}' in text or f"'{epitaph}" in text, (path, epitaph))


class StockEvidenceTests(unittest.TestCase):
    """The stock picker as the generator documents it."""

    def test_before_bytes_are_the_stock_dispatch(self):
        stock = stock_bytes()
        (p,) = json.loads(MANIFEST.read_text(encoding="utf-8"))["patches"]
        off = int(p["offset"], 16)
        self.assertEqual(stock[off: off + len(p["before"]) // 2].hex().upper(), p["before"])
        # ecx = 0x305 before the age test; the dispatch is cmp eax,4 / ja END / jmp [eax*4+0x464E5C].
        self.assertEqual(stock[0x64D31:0x64D36], bytes.fromhex("B905030000"))
        self.assertEqual(stock[0x64D89:0x64D99], bytes.fromhex("83F8040F8787000000FF24855C4E4600"))
        # the shared fetch and the writer's strncpy into entry+0x38, limit 0x20
        self.assertEqual(stock[END - BASE: END - BASE + 20],
                         bytes.fromhex("6A2051E81FBFFEFF8BC8E8A8B8FEFF508D463850"))

    def test_the_string_ids_are_the_eulogy_strings(self):
        stock = stock_bytes()
        pe = pefile.PE(data=stock, fast_load=True) if HAVE_EMULATOR else None
        if pe is None:
            self.skipTest("pefile not installed")
        image = pe.get_memory_mapped_image()

        def cstr(va: int) -> str:
            o = va - BASE
            return image[o: image.index(b"\0", o)].decode("latin-1")

        texts = {}
        for o in range(0xD0000, 0xE0000, 4):          # {0, id, name, text} rows in .data
            z, ident, name, text = struct.unpack_from("<IIII", image, o)
            if z == 0 and 0x305 <= ident <= 0x312 and BASE < text < BASE + len(image) and BASE < name < BASE + len(image):
                try:
                    if cstr(name).startswith("eEulogy"):
                        texts[ident] = (cstr(name), cstr(text))
                except ValueError:
                    continue
        self.assertEqual(texts[0x305], ("eEulogyDefault", "Respected Citizen"))
        self.assertEqual(texts[0x306][0], "eEulogyTextFarmer1")
        self.assertEqual(texts[0x30A][0], "eEulogyTextBreeder1")
        self.assertEqual(texts[0x30C][0], "eEulogyTextDoctor1")
        self.assertEqual(texts[0x308][0], "eEulogyTextResearcher1")
        self.assertEqual(texts[0x30E][0], "eEulogyTextBuilder1")
        # The jump table the stock dispatch reads: Farmer, Parent, Doctor, Scientist, Builder.
        targets = struct.unpack_from("<5I", stock, 0x64E5C)
        for job, target in enumerate(targets):
            off = target - BASE
            # each case: push 0x64 / call rand / xor ecx,ecx / add esp,4 / cmp eax,0x32 / setge cl / add ecx, id
            self.assertEqual(stock[off: off + 2], bytes.fromhex("6A64"))
            self.assertEqual(stock[off + 18: off + 20], bytes.fromhex("81C1"))
            self.assertEqual(struct.unpack_from("<I", stock, off + 20)[0], STOCK_PAIRS[job])

    def test_the_coin_is_the_runtimes_clock_seeded_rand(self):
        """rand(100) at 0x403660 is rand() % 100 for any limit up to 0x7FFF;
        rand (0x47CFD8) is the C runtime's LCG on the thread's seed; the only
        srand call (0x402F97) seeds it with time(NULL) at start-up.  So each
        burial draws the next value of the one clock-seeded stream, and over
        the generator's 32768 outputs 0..49 and 50..99 split 16400 / 16368."""
        if not HAVE_EMULATOR:
            self.skipTest("capstone not installed")
        stock = stock_bytes()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

        def listing(va: int, n: int) -> list:
            return [f"{i.mnemonic} {i.op_str}".strip() for i in md.disasm(stock[va - BASE: va - BASE + n], va)]

        self.assertEqual(listing(RAND, 0x21), [
            "sub esp, 8", "push esi", "mov esi, dword ptr [esp + 0x10]", "lea eax, [esi - 1]", "cmp eax, 0x7ffe",
            "ja 0x403681", "call 0x47cfd8", "cdq", "idiv esi", "pop esi", "mov eax, edx", "add esp, 8", "ret"])
        self.assertEqual(listing(0x47CFD8, 0x22)[1:], [
            "mov ecx, dword ptr [eax + 0x14]", "imul ecx, ecx, 0x343fd", "add ecx, 0x269ec3",
            "mov dword ptr [eax + 0x14], ecx", "mov eax, ecx", "shr eax, 0x10", "and eax, 0x7fff", "ret"])
        self.assertEqual(listing(0x47CFCB, 0xD)[1:], ["mov ecx, dword ptr [esp + 4]", "mov dword ptr [eax + 0x14], ecx", "ret"])
        srand_calls = [o for o in range(len(stock) - 5) if stock[o] == 0xE8
                       and BASE + o + 5 + struct.unpack_from("<i", stock, o + 1)[0] == 0x47CFCB]
        self.assertEqual([BASE + o for o in srand_calls], [0x402F97])
        self.assertEqual(listing(0x402F8F, 0xD), ["push 0", "call 0x47c96a", "push eax", "call 0x47cfcb"])
        pe = pefile.PE(data=stock, fast_load=True)
        pe.parse_data_directories()
        imports = {i.address: i.name for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports}
        call = next(md.disasm(stock[0x7C973: 0x7C979], 0x47C973))      # time(): the clock
        self.assertEqual(imports[int(call.op_str.split("[")[1].rstrip("]"), 16)], b"GetSystemTimeAsFileTime")
        under = sum(1 for v in range(0x8000) if v % 100 < 50)
        self.assertEqual((under, 0x8000 - under), (16400, 16368))

    def test_nothing_else_enters_the_recoded_bytes(self):
        """No branch, call or address operand anywhere in .text, and no aligned
        pointer in .rdata/.data, lands strictly inside the block -- except the
        old jump table at 0x464E5C, which only the replaced dispatch read."""
        if not HAVE_EMULATOR:
            self.skipTest("capstone/pefile not installed")
        stock = stock_bytes()
        inside = range(START + 1, END)
        pe = pefile.PE(data=stock, fast_load=True)
        table = 0x464E5C
        self.assertEqual(stock.count(struct.pack("<I", table)), 1)   # read only by jmp [eax*4+0x464E5C]
        self.assertEqual(stock.find(struct.pack("<I", table)), 0x64D95)
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.skipdata = True
        for section in pe.sections:
            name = section.Name.rstrip(b"\0")
            raw = stock[section.PointerToRawData: section.PointerToRawData + section.SizeOfRawData]
            va = BASE + section.VirtualAddress
            if name == b".text":
                for ins in md.disasm(raw, va):
                    if START <= ins.address < END or table <= ins.address < table + 20:
                        continue
                    for token in ins.op_str.replace("[", " ").replace("]", " ").replace(",", " ").replace(":", " ").split():
                        if token.startswith("0x") and int(token, 16) in inside:
                            self.fail("%#x %s %s" % (ins.address, ins.mnemonic, ins.op_str))
            else:
                for o in range(0, len(raw) - 3, 4):
                    self.assertNotIn(struct.unpack_from("<I", raw, o)[0], inside, (name, hex(va + o)))

    def test_ebx_is_free_between_the_fetch_and_its_restore(self):
        if not HAVE_EMULATOR:
            self.skipTest("capstone not installed")
        stock = stock_bytes()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.detail = True
        seen = []
        for ins in md.disasm(stock[END - BASE: 0x64E43], END):
            seen.append(ins.mnemonic + " " + ins.op_str)
            regs_read, _ = ins.regs_access()
            self.assertNotIn("ebx", [ins.reg_name(r) for r in regs_read], seen[-1])
        self.assertEqual(seen[-1], "pop ebx")                 # restored before the writer returns


def run_block(image: bytes, job: int, rand_value: int):
    """Run 0x464D86 until it reaches the fetch (0x464E19) or the strncpy (0x464E28)."""
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    size = (len(image) + 0xFFFF) & ~0xFFFF
    mu.mem_map(BASE, size)
    mu.mem_write(BASE, image)
    entry, stack = 0x10000000, 0x20000000
    mu.mem_map(entry, 0x1000)
    mu.mem_map(stack, 0x10000)
    mu.mem_write(entry + 0x28, struct.pack("<i", job))
    esp0 = stack + 0x8000
    mu.reg_write(UC_X86_REG_ESP, esp0)
    mu.reg_write(UC_X86_REG_ESI, entry)
    mu.reg_write(UC_X86_REG_ECX, RESPECTED)          # set at 0x464D31, before the age test
    mu.reg_write(UC_X86_REG_EBX, 0xDEAD0000)
    mu.reg_write(UC_X86_REG_EDX, 0x12345678)
    calls = []

    def hook(uc, address, _size, _user):
        if address == RAND:
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, limit = struct.unpack("<II", bytes(uc.mem_read(esp, 8)))
            calls.append(limit)
            uc.reg_write(UC_X86_REG_EAX, rand_value % limit)
            uc.reg_write(UC_X86_REG_ECX, 0xBAD0BAD0)   # rand clobbers ecx/edx
            uc.reg_write(UC_X86_REG_EDX, 0xBAD0BAD0)
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
            uc.reg_write(UC_X86_REG_EIP, ret)
        elif address in (END, COPY):
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.emu_start(START, END + 0x100, count=200)
    eip = mu.reg_read(UC_X86_REG_EIP)
    esp = mu.reg_read(UC_X86_REG_ESP)
    if eip == END:
        assert esp == esp0, "stack unbalanced at the fetch"
        return ("id", mu.reg_read(UC_X86_REG_ECX)), calls
    assert eip == COPY, hex(eip)
    assert esp == esp0 - 4 and struct.unpack("<I", bytes(mu.mem_read(esp, 4)))[0] == 0x20, "strncpy limit"
    ptr = mu.reg_read(UC_X86_REG_EAX)
    text = bytes(mu.mem_read(ptr, 0x20)).split(b"\0")[0].decode()
    return ("text", text), calls


@unittest.skipUnless(HAVE_EMULATOR, "requires unicorn, capstone and pefile")
class EmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stock = stock_bytes()
        rendered, applied = patcher.render_patched_bytes(STOCK, BUILD, patcher.DEFAULT_PATCH_MODE, [PATCH_ID])
        cls.applied = applied
        cls.stock_image = pefile.PE(data=stock, fast_load=True).get_memory_mapped_image()
        cls.patched_image = pefile.PE(data=bytes(rendered), fast_load=True).get_memory_mapped_image()

    def outcomes(self, image: bytes, job: int) -> list:
        return [run_block(image, job, r)[0] for r in range(100)]

    def test_devotees_get_each_epitaph_for_exactly_half_the_rolls(self):
        stock = self.outcomes(self.stock_image, 5)
        self.assertEqual(stock, [("id", RESPECTED)] * 100)          # stock: always Respected Citizen
        patched = self.outcomes(self.patched_image, 5)
        self.assertEqual(patched[:50], [("id", RESPECTED)] * 50)
        self.assertEqual(patched[50:], [("text", CHARITABLE)] * 50)
        _, calls = run_block(self.patched_image, 5, 0)
        self.assertEqual(calls, [100])                               # one rand(100), the game's own

    def test_every_other_job_is_unchanged_and_never_charitable_soul(self):
        for job in (-1, 0, 1, 2, 3, 4):
            with self.subTest(job=job):
                stock = self.outcomes(self.stock_image, job)
                patched = self.outcomes(self.patched_image, job)
                self.assertEqual(patched, stock)
                self.assertNotIn(("text", CHARITABLE), patched)
                if job == -1:
                    self.assertEqual(patched, [("id", RESPECTED)] * 100)
                    self.assertEqual(run_block(self.patched_image, job, 0)[1], [])   # no rand call, as stock
                else:
                    first = STOCK_PAIRS[job]
                    self.assertEqual(patched, [("id", first)] * 50 + [("id", first + 1)] * 50)

    def test_a_sampled_village_sees_both_epitaphs_about_equally(self):
        import random
        rng = random.Random(1234)
        counts = {"usual": 0, CHARITABLE: 0}
        for _ in range(2000):
            (kind, value), _ = run_block(self.patched_image, 5, rng.randrange(0x8000))
            if kind == "text":
                self.assertEqual(value, CHARITABLE)
                counts[CHARITABLE] += 1
            else:
                self.assertEqual(value, RESPECTED)
                counts["usual"] += 1
        self.assertEqual(sum(counts.values()), 2000)
        self.assertLess(abs(counts[CHARITABLE] - 1000), 100, counts)


class RenderTests(unittest.TestCase):
    def test_the_patcher_applies_it_and_only_it(self):
        stock = stock_bytes()
        base = bytes(patcher.render_patched_bytes(STOCK, BUILD, patcher.DEFAULT_PATCH_MODE, [])[0])
        rendered, applied = patcher.render_patched_bytes(STOCK, BUILD, patcher.DEFAULT_PATCH_MODE, [PATCH_ID])
        rendered = bytes(rendered)
        self.assertEqual(base[START - BASE: END - BASE], gen.stock_block(stock))
        self.assertEqual(rendered[START - BASE: END - BASE], gen.build_block())
        checksum = struct.unpack_from("<I", stock, 0x3C)[0] + 0x58      # the PE checksum is recomputed
        self.assertEqual(rendered[:checksum], base[:checksum])
        self.assertEqual(rendered[checksum + 4:START - BASE], base[checksum + 4:START - BASE])
        self.assertEqual(rendered[END - BASE:], base[END - BASE:])
        self.assertTrue(any(PATCH_ID in str(item.get("owner", "")) for item in applied))

    def test_every_public_vv5_patch_in_every_mode_leaves_the_writer_to_it(self):
        stock = stock_bytes()
        public = [p.id for p in patcher.load_public_fun_patches() if p.game_id == "vv5"]
        self.assertIn(PATCH_ID, public)
        writer = range(0x64C70, 0x64E70)
        for with_256 in (False, True):
            ids = [i for i in public if with_256 or i != "vv5_population_256"]
            for mode in MODES:
                with self.subTest(mode=mode, with_256=with_256):
                    rendered = bytes(patcher.render_patched_bytes(STOCK, BUILD, mode, ids)[0])
                    self.assertEqual(rendered[START - BASE: END - BASE], gen.build_block())
                    for o in writer:
                        if not START - BASE <= o < END - BASE:
                            self.assertEqual(rendered[o], stock[o], hex(o))
                    if HAVE_EMULATOR:   # and it runs there: the full build's own rand and fetch
                        image = pefile.PE(data=rendered, fast_load=True).get_memory_mapped_image()
                        self.assertEqual(run_block(image, 5, 10)[0], ("id", RESPECTED))
                        self.assertEqual(run_block(image, 5, 90)[0], ("text", CHARITABLE))
                        self.assertEqual(run_block(image, 0, 90)[0], ("id", 0x307))
                        self.assertEqual(run_block(image, -1, 90)[0], ("id", RESPECTED))

    def test_no_other_manifest_or_detour_claims_the_bytes(self):
        mine = set(range(START - BASE, END - BASE))
        for path in sorted((ROOT / "data").glob("*.json")):
            if path.name == MANIFEST.name:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            items = data if isinstance(data, list) else [data] + list(data.get("features", []) if isinstance(data, dict) else [])
            for item in items:
                if not isinstance(item, dict) or item.get("game_id") not in (None, "vv5"):
                    continue
                for p in item.get("patches", []) or []:
                    try:
                        off = int(str(p.get("offset")), 16)
                        n = len(p.get("before", "")) // 2
                    except (TypeError, ValueError):
                        continue
                    self.assertFalse(mine & set(range(off, off + n)), (path.name, item.get("id"), p.get("offset")))
                for d in item.get("runtime_detours", []) or []:
                    va = int(str(d.get("va")), 16)
                    self.assertFalse(START <= va < END, (path.name, d))


class RegistrationTests(unittest.TestCase):
    def test_registered_on_by_default_bundled_and_documented(self):
        public = patcher.load_public_fun_patches()
        row = next(p for p in public if p.id == PATCH_ID)
        self.assertEqual(row.name, "Charitable Soul Epitaph")
        self.assertTrue(default_fun_patch_selection(PATCH_ID))
        self.assertTrue(owners_default_fun_patch_selection(PATCH_ID))
        self.assertTrue(select_all_fun_patch_selection(PATCH_ID))
        self.assertEqual(patcher.patch_requirement_text(row, public), "Requires no other patch to be ticked.")
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('DEVOTED_SOUL_EPITAPH_FEATURE_PATHS = (ROOT / "data" / "vv5_devoted_soul_epitaph_feature.json",)', source)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"data/vv5_devoted_soul_epitaph_feature.json"', release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("- Patch ID: `vv5_devoted_soul_epitaph`", readme)
        howto = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        self.assertIn("CHARITABLE SOUL EPITAPH (NEW BELIEVERS)", howto)
        doc = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn("#### Charitable Soul Epitaph (`vv5_devoted_soul_epitaph`)", doc)


if __name__ == "__main__":
    unittest.main()
