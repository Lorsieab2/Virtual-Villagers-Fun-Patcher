"""Skin tones: the tone table, the inheritance rule and the per-save file.

THE RULE IS THE GAMES' OWN HEAD RULE (the owner, 2026-11-26: "babies conceived from two parents inherit
skin tones same as head rules").  HeadRule runs each later game's own head roll out of its stock executable
(unicorn; the creator's code from its `push 100` to the body roll, rand() answered from a list) for every
pair of parents' heads and every roll, and compares it with src/vv_skin_tones.py head_rule.  Inherit then
holds vv_skin_tones.inherit to that same rule on the tone numbers, and the DLL's rule
(native/vvfp_skin_tones/skin_tone_rules.h, run by the harness) to inherit.

THE DATA DLL, by native/vvfp_skin_tones/skin_tone_harness.c on real files in a fresh folder under %TEMP%
(scripts/build_skin_tone_harness.ps1): founders and arrivals random, a baby its parents' by the rule, the
tone rolled at the conception kept for the held baby and given unchanged at the birth, twins alike, the
file's shape, the tone following its villager, Change Appearance's set, the Revive read and write.
"""
from __future__ import annotations

import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_skin_tones as tones  # noqa: E402

STOCK = {2: "Virtual Villagers - The Lost Children.exe", 3: "Virtual Villagers - The Secret City.exe",
         4: "Virtual Villagers - The Tree of Life.exe", 5: "Virtual Villagers - New Believers.exe"}
# Each creator's head roll: its `push 100` and the body roll's push that follows the head (the same sites
# tests/test_game_mechanics_genetics.py pins byte for byte).
HEAD_ROLL = {2: (0x44CBAB, 0x44CC35), 3: (0x4564A7, 0x456520), 4: (0x45F235, 0x45F2AE), 5: (0x46853A, 0x4685B3)}
RULES_H = ROOT / "native" / "vvfp_skin_tones" / "skin_tone_rules.h"


def stock(game: int):
    for folder in (ROOT / "inputs" / f"vv{game}-stock-copy", ROOT / "research" / "stock-executables"):
        path = folder / STOCK[game]
        if path.is_file():
            return path
    return None


class Table(unittest.TestCase):
    def test_ten_tones_light_to_dark(self) -> None:
        self.assertEqual(tones.TONE_COUNT, 10)
        self.assertEqual([row[0] for row in tones.TONE_TABLE],
                         ["Porcelain", "Fair", "Light golden", "Light olive", "Copper", "Warm brown", "Medium brown",
                          "Deep brown", "Dark", "Ebony"])
        lightness = [row[2] for row in tones.TONE_TABLE]
        self.assertEqual(lightness, sorted(lightness, reverse=True))
        for _name, _hex, L, chroma, hue in tones.TONE_TABLE:
            self.assertTrue(0.2 < L < 0.96 and 0.02 < chroma < 0.12 and 30 < hue < 80, (L, chroma, hue))

    def test_names(self) -> None:
        self.assertEqual(tones.tone_name(5), "Copper")
        self.assertEqual(tones.tone_name(0), "Game's own")
        self.assertEqual(tones.tone_name(tones.TONE_GAMES_OWN), "Game's own")

    def test_the_dll_has_the_same_numbers(self) -> None:
        text = RULES_H.read_text(encoding="utf-8")
        self.assertIn(f"#define VVFP_SKIN_TONE_COUNT {tones.TONE_COUNT}\n", text)
        self.assertIn(f"#define VVFP_SKIN_TONE_GAMES_OWN {tones.TONE_GAMES_OWN}\n", text)
        self.assertIn(f'#define VVFP_SKIN_TONE_WORD "{tones.LOG_WORD}"', text)
        self.assertIn(f'#define VVFP_SKIN_TONE_GAMES_OWN_NAME "{tones.GAMES_OWN_NAME}"', text)
        names = text.split("#define VVFP_SKIN_TONE_NAMES {", 1)[1].split("}", 1)[0].replace("\\\n", " ")
        self.assertEqual([n.strip().strip('"') for n in names.split(",")], [row[0] for row in tones.TONE_TABLE])
        store = (ROOT / "native" / "vvfp_skin_tones" / "vvfp_skin_tones.c").read_text(encoding="utf-8")
        self.assertIn(f"#define HL_MAGIC 0x{tones.MAGIC:08X}u", store)
        self.assertIn(f"#define HL_MAGIC_ONE_BYTE 0x{tones.MAGIC_ONE_BYTE:08X}u", store)
        self.assertIn(f'#define HL_KIND "{tones.FOLDER}"', store)


class SexChange(unittest.TestCase):
    """Codex on #900: the tone file's identity holds the sex, so a sex change must be told to this DLL, or the
    villager would be given a new random tone.  The harness proves the DLL carries it (Harness, "A sex change")."""

    def test_the_dll_is_told(self) -> None:
        text = (ROOT / "native" / "shared" / "sex_change.h").read_text(encoding="utf-8")
        owners = text[text.index("VV_SEX_OWNERS[] = {"):]
        owners = owners[:owners.index("};")]
        self.assertIn('"VVFP Skin Tones.dll"', owners)

    def test_the_dll_exports_the_answer(self) -> None:
        text = (ROOT / "native" / "vvfp_skin_tones" / "vvfp_skin_tones.def").read_text(encoding="utf-8")
        self.assertIn("VvfpVillagerSexChanged=_VvfpVillagerSexChanged@16", text)


class PreferredTone(unittest.TestCase):
    """The owner, 2026-11-28: "Preferred skin tone" -- no preference (random), or a tone most (4 in 5) randomly made
    villagers get; the rest random."""

    def test_no_preference_is_every_tone_alike(self) -> None:
        for preferred in (0, 11, 15, -1):
            self.assertEqual([tones.random_tone(preferred, r100, rn) for r100 in (0, 99) for rn in range(10)],
                             list(range(1, 11)) * 2)

    def test_four_in_five_get_the_preferred_tone(self) -> None:
        for preferred in range(1, tones.TONE_COUNT + 1):
            got = [tones.random_tone(preferred, r100, rn) for r100 in range(100) for rn in range(90)]
            self.assertEqual(got.count(preferred), 80 * 90)
            rest = [t for t in got if t != preferred]
            self.assertEqual({t: rest.count(t) for t in set(rest)},
                             {t: 20 * 10 for t in range(1, 11) if t != preferred}, "the rest: the other nine alike")

    def test_the_percent_is_the_dlls(self) -> None:
        text = (ROOT / "native" / "vvfp_skin_tones" / "skin_tone_rules.h").read_text(encoding="utf-8")
        self.assertIn(f"#define VVFP_SKIN_TONE_PREFERRED_PERCENT {tones.PREFERRED_PERCENT}u", text)
        self.assertIn(f'#define VVFP_SKIN_TONE_CHOICE_FILE "{tones.CHOICE_FILE}"', text)

    def test_the_file(self) -> None:
        self.assertEqual(tones.choice_text(0), "0\n")
        self.assertEqual(tones.choice_text(10), "10\n")
        for bad in (11, -1, True, "3", 2.0):
            with self.assertRaises(ValueError):
                tones.choice_text(bad)


class Inherit(unittest.TestCase):
    def test_it_is_the_head_rule_on_the_tone_numbers(self) -> None:
        """Wherever both parents have a tone and the head rule stays inside 1..COUNT, a tone is the head the
        games would roll; outside, it is held to the range as the head is held to 0..29."""
        n = tones.TONE_COUNT
        for father in range(1, n + 1):
            for mother in range(1, n + 1):
                for r100 in (0, 4, 5, 50, 99):
                    for r3 in range(3):
                        for rn in range(n):
                            got = tones.inherit(father, mother, r100, r3, rn)
                            self.assertTrue(1 <= got <= n)
                            if r100 < 5:
                                self.assertEqual(got, rn + 1)                   # any tone, each as likely
                            else:
                                head = tones.head_rule(father, mother, r100, r3, rn, count=30)
                                self.assertEqual(got, min(max(head, 1), n))

    def test_a_parent_not_known(self) -> None:
        for r3 in range(3):
            self.assertEqual(tones.inherit(0, 6, 50, r3, 0), 5 + r3)        # the other parent's tone, +-1
            self.assertEqual(tones.inherit(6, 0, 50, r3, 0), 5 + r3)
            self.assertEqual(tones.inherit(99, 6, 50, r3, 0), 5 + r3)       # 15, the game's own chosen, is not a tone either
        self.assertEqual({tones.inherit(0, 0, 50, 1, rn) for rn in range(10)}, set(range(1, 11)))

    def test_nothing_depends_on_which_parent(self) -> None:
        for a in range(1, 11):
            for b in range(1, 11):
                self.assertEqual(tones.inherit(a, b, 50, 1, 0), tones.inherit(b, a, 50, 1, 0))


class HeadRule(unittest.TestCase):
    """Each later game's own head roll, run from its stock executable."""

    def roll(self, game: int):
        try:
            import pefile
            import unicorn
            from unicorn import x86_const as x
        except ImportError:
            self.skipTest("unicorn / pefile are not installed")
        path = stock(game)
        if path is None:
            self.skipTest(f"no stock VV{game} executable")
        pe = pefile.PE(str(path))
        base = pe.OPTIONAL_HEADER.ImageBase
        image = pe.get_memory_mapped_image()
        start, stop = HEAD_ROLL[game]
        code = image[start - base:start - base + 7]
        self.assertEqual(code[:3], b"\x6a\x64\xe8")                             # push 100; call rand
        rand = start + 7 + struct.unpack_from("<i", code, 3)[0]
        size = (len(image) + 0xFFFF) & ~0xFFFF
        stack, record = 0x10000000, 0x20000000
        esp = stack + 0x10000
        # One machine for the whole game: the image, a stack and a record, set back before every roll.
        mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        mu.mem_map(base, size)
        mu.mem_write(base, bytes(image))
        mu.mem_map(stack, 0x20000)
        mu.mem_map(record, 0x100000)
        state = {"queue": [], "reads": [], "writes": []}

        def on_code(uc, address, _size, _user):
            uc.reg_write(x.UC_X86_REG_EAX, state["queue"].pop(0))
            sp = uc.reg_read(x.UC_X86_REG_ESP)
            uc.reg_write(x.UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(sp, 4))[0])
            uc.reg_write(x.UC_X86_REG_ESP, sp + 4)

        def on_read(uc, _access, address, _size, _value, _user):
            if esp <= address < stack + 0x20000 and address not in state["reads"]:
                state["reads"].append(address)

        def on_write(uc, _access, address, _size, value, _user):
            if record <= address < record + 0x100000:
                state["writes"].append((address, value))

        mu.hook_add(unicorn.UC_HOOK_CODE, on_code, begin=rand, end=rand)
        mu.hook_add(unicorn.UC_HOOK_MEM_READ, on_read)
        mu.hook_add(unicorn.UC_HOOK_MEM_WRITE, on_write)

        def run(values, rolls):
            """The head the roll stores, with the stack dwords at `values` {address: dword} and rand()
            answering `rolls` in turn; the stack addresses it read, in order; the rolls left over."""
            mu.mem_write(stack, bytes(0x20000))
            for address, value in values.items():
                mu.mem_write(address, struct.pack("<i", value))
            mu.reg_write(x.UC_X86_REG_ESP, esp)
            for reg in (x.UC_X86_REG_ESI, x.UC_X86_REG_EDI, x.UC_X86_REG_EBP):    # whichever holds the record
                mu.reg_write(reg, record + 0x40000)
            mu.reg_write(x.UC_X86_REG_EBX, 0)       # the creators of the later three keep 0 in ebx here
            state["queue"], state["reads"], state["writes"] = list(rolls), [], []
            mu.emu_start(start, stop, count=400)
            self.assertEqual(mu.reg_read(x.UC_X86_REG_EIP), stop)
            self.assertTrue(state["writes"], "the roll stored no head")
            head = state["writes"][-1][1]
            return (head - (1 << 32) if head & 0x80000000 else head), list(state["reads"]), list(state["queue"])

        return run

    def check(self, game: int) -> None:
        run = self.roll(game)
        # With every parent value 0 the roll reads all four (both heads, both bodies) and then rolls at random.
        head, reads, left = run({}, [50, 17])
        self.assertEqual((head, left), (17, []))
        self.assertEqual(len(reads), 4, [hex(a) for a in reads])
        # The two the average is made of: the pair whose values move the head.
        pair = None
        for a in range(4):
            for b in range(a + 1, 4):
                if run({reads[a]: 20, reads[b]: 10}, [50, 1, 0])[0] == 15:
                    self.assertIsNone(pair)
                    pair = (reads[a], reads[b])
        self.assertIsNotNone(pair, "no two stack values average into the head")
        for father in (0, 1, 2, 7, 14, 15, 28, 29):
            for mother in (0, 1, 3, 8, 14, 22, 29):
                for r100 in (0, 4, 5, 6, 99):
                    for r3 in range(3):
                        with self.subTest(game=game, father=father, mother=mother, r100=r100, r3=r3):
                            inherits = r100 >= 5 and (father or mother)
                            rolls = [r100, r3, 0] if inherits else [r100, 23]
                            head, _, left = run({pair[0]: father, pair[1]: mother}, rolls)
                            self.assertEqual(head, tones.head_rule(father, mother, r100, r3, 23))
                            self.assertEqual(left, [0] if inherits else [])
        # The other two parent values (the bodies) only decide WHETHER to inherit, never the head.
        others = [a for a in reads if a not in pair]
        head, _, _ = run({others[0]: 9}, [50, 2, 0])
        self.assertEqual(head, 1)                                               # (0 + 0) / 2 + 2 - 1

    def test_the_lost_children(self) -> None:
        self.check(2)

    def test_the_secret_city(self) -> None:
        self.check(3)

    def test_the_tree_of_life(self) -> None:
        self.check(4)

    def test_new_believers(self) -> None:
        self.check(5)

    def test_a_new_home_inherits_nothing(self) -> None:
        """Its creator rolls the head at random by sex (0x43C61F rand(19), 0x43C62A rand(20)) and reads no
        parent: so its tones use the later games' rule."""
        path = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
        if not path.is_file():
            self.skipTest("no stock A New Home executable")
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(path))
        image = pe.get_memory_mapped_image()
        base = pe.OPTIONAL_HEADER.ImageBase
        self.assertEqual(image[0x43C61F - base:0x43C61F - base + 2], b"\x6a\x13")
        self.assertEqual(image[0x43C62A - base:0x43C62A - base + 2], b"\x6a\x14")

    def test_a_new_homes_genetics_is_the_same_rule(self) -> None:
        """A New Home's own head rule is the patcher's Genetics (native/vv1_genetics): 5 in 100 any head, else
        the parents' average rounded down (the mother's alone with no father) + rand(3) - 1, held to the range
        -- the rule the tones use."""
        source = (ROOT / "native" / "vv1_genetics" / "vv1_genetics.c").read_text(encoding="utf-8")
        self.assertIn("base = father >= 0 ? (father + mother) / 2 : mother;", source)
        self.assertIn("if (game_rand(100) < 5) {", source)
        self.assertIn("head = base + game_rand(3) - 1;", source)
        rules = (ROOT / "native" / "vvfp_skin_tones" / "skin_tone_rules.h").read_text(encoding="utf-8")
        self.assertIn("if (r100 % 100u < 5u || (father == 0 && mother == 0)) {", rules)
        self.assertIn("tone = (father + mother) / 2 + (int)(r3 % 3u) - 1;", rules)
        for mother in range(1, 11):                 # the mother's alone: the missing father counts as her
            for r3 in range(3):
                self.assertEqual(tones.inherit(0, mother, 50, r3, 0),
                                 max(1, min(10, mother + r3 - 1)))

    def test_parentage_export_tells_the_tones(self) -> None:
        """Parentage Export calls the conception and the birth (native/shared/skin_tone.h): the conception
        with the carrier and the father it resolved (nobody for the game's own default father), the birth
        after any new name, a second baby of the delivery copying the first."""
        source = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("(void)vvfp_skin_conceived(game_id, mother, default_father ? NULL : father);", source)
        birth = source.index("skin_tone_birth(game_id, tone_carrier, child_record);")
        self.assertLess(source.index("number_new_name(game_id, (unsigned char *)child_record);\n    }"), birth)
        self.assertIn("first = last_child;", source)


class File(unittest.TestCase):
    def test_round_trip(self) -> None:
        roster = [0] * 150
        ids = [0] * 150
        values = [0] * 150
        roster[3] = ids[3] = 0x1234
        values[3] = 7
        roster[9] = ids[9] = 0x9999
        values[9] = (4 << 4) | 2                # tone 2, carrying a baby of tone 4
        ids[20] = 0x7777
        values[20] = tones.TONE_GAMES_OWN
        births = [0] * 150
        births[3], births[9] = 5, 2
        data = tones.pack(5, roster, ids, values, births)
        self.assertEqual(len(data), 12 + 150 * 10)
        self.assertEqual(data[:4], b"VST2")
        game, got_roster, got_ids, got_values, got_births = tones.unpack(data)
        self.assertEqual((game, list(got_roster), list(got_ids), list(got_values), list(got_births)),
                         (5, roster, ids, values, births))
        self.assertEqual(tones.birth_tones_by_identity(data), {0x1234: 5, 0x9999: 2})
        # The first layout: no birth bytes; the tones it holds are the birth tones.
        old = b"VST1" + data[4:12 + 150 * 9]
        self.assertEqual(tones.unpack(old)[3], tuple(values))
        self.assertEqual(tones.birth_tones_by_identity(old), {0x1234: 7, 0x9999: 2})
        self.assertEqual(tones.tones_by_identity(data), {0x1234: 7, 0x9999: 2, 0x7777: 0})
        self.assertEqual(tones.pending_baby_tone(values[9]), 4)
        self.assertEqual(tones.pending_baby_tone(values[3]), 0)

    def test_another_shape_is_refused(self) -> None:
        good = tones.pack(2, [0] * 256, [0] * 256, [0] * 256, [0] * 256)
        for bad in (good[:-1], good + b"\0", b"VHL2" + good[4:], good[:4] + struct.pack("<I", 6) + good[8:], b""):
            with self.assertRaises(ValueError):
                tones.unpack(bad)

    def test_the_path(self) -> None:
        self.assertEqual(tones.file_path(Path("X"), 3),
                         Path("X") / "Save 3" / "Data" / "Skin Tones" / "Skin Tones - Save 3.dat")


class Tools(unittest.TestCase):
    """The patcher's tools take the file with its slot (Back Up Saves: tests/test_save_backup.py; the
    renames: tests/test_last_names_masks_worn.py)."""

    def test_copy_slot_copies_it_under_the_new_slot(self) -> None:
        import vv_copy_slot
        source = tones.file_path(Path("Virtual Villagers Fun Patcher"), 2)
        self.assertEqual(vv_copy_slot.target_relative(source, 2, 5),
                         tones.file_path(Path("Virtual Villagers Fun Patcher"), 5))

class Harness(unittest.TestCase):
    def test_the_dll_on_real_files(self) -> None:
        script = ROOT / "scripts" / "build_skin_tone_harness.ps1"
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                capture_output=True, text=True, timeout=600)
        text = result.stdout + result.stderr
        if "cl.exe" in text and "not recognized" in text or "cannot find the path" in text.lower():
            self.skipTest("the compiler is not installed")
        self.assertEqual(result.returncode, 0, text[-4000:])
        self.assertNotIn("[FAIL]", text)
        self.assertIn("[PASS]", text)
        # The DLL's rule, printed for every case, is the Python rule.
        seen = 0
        for line in text.splitlines():
            if line.startswith("INHERIT "):
                father, mother, r100, r3, rn, got = (int(v) for v in line.split()[1:])
                self.assertEqual(got, tones.inherit(father, mother, r100, r3, rn), line)
                seen += 1
        self.assertEqual(seen, 12 * 12 * 5 * 3 * 3)
        randoms = 0
        for line in text.splitlines():
            if line.startswith("RANDOM "):
                preferred, r100, rn, got = (int(v) for v in line.split()[1:])
                self.assertEqual(got, tones.random_tone(preferred, r100, rn), line)
                randoms += 1
        self.assertEqual(randoms, 12 * 34 * 12)


if __name__ == "__main__":
    unittest.main()
