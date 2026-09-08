"""Every appended parentage section must actually be mapped by the loader.

Bumping NumberOfSections and SizeOfImage is not enough to add a section: the
new IMAGE_SECTION_HEADER has to be written into the slot that follows the
stock section table.  VV4 and VV5 shipped that pair of header edits without
the header itself, which left a zero-filled entry -- the loader then maps a
zero-length section at the image base, the appended page is never mapped, and
the hook's first call jumps to unmapped memory.

Nothing caught it, because every other check looked at the payload bytes,
which were written correctly the whole time.  This asserts the property that
actually matters: the address the installed hook jumps to lies inside a
section the header table really describes, and the trampoline found there
still performs the call it stole.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, render_patched_bytes

# game -> stock exe, build id, feature id, hook VA, trampoline VA, conception VA
CASES = {
    4: (
        "Virtual Villagers - The Tree of Life.exe",
        "vv4",
        "vv4_write_parentage_log",
        0x00460A2E,
        0x0073F000,
        0x0045E7B0,
    ),
    5: (
        "Virtual Villagers - New Believers.exe",
        "vv5",
        "vv5_write_parentage_log",
        0x00467DBE,
        0x007C9000,
        0x00465E00,
    ),
}

MODES = ("collection_progression", "immediate_fixed")

# mov ebx, [esp+0x1C] -- the suppression flag, read before the stolen call
FLAG_READ = bytes.fromhex("8B5C241C")


def _sections(data):
    """Return the image base and the section table as the loader would read it."""
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    optional_size = struct.unpack_from("<H", data, e_lfanew + 0x14)[0]
    table = e_lfanew + 0x18 + optional_size
    image_base = struct.unpack_from("<I", data, e_lfanew + 0x34)[0]
    out = []
    for index in range(count):
        entry = table + index * 0x28
        virtual_size, rva, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, entry + 8
        )
        out.append(
            {
                "name": data[entry : entry + 8].rstrip(b"\0").decode("latin1"),
                "virtual_size": virtual_size,
                "virtual_address": image_base + rva,
                "raw_size": raw_size,
                "raw_pointer": raw_pointer,
                "characteristics": struct.unpack_from("<I", data, entry + 0x24)[0],
            }
        )
    return image_base, out


def _va_to_file(sections, va):
    for section in sections:
        start = section["virtual_address"]
        size = section["virtual_size"]
        if size and start <= va < start + size:
            return section["raw_pointer"] + (va - start)
    return None


class AppendedSectionsAreMappedTests(unittest.TestCase):
    def test_hook_target_lands_in_a_section_the_header_table_describes(self):
        for game, case in CASES.items():
            exe, build_id, feature_id, hook_va, page_va, conception = case
            stock = ROOT / "research/stock-executables" / exe
            # Opened, not probed with exists(): stock game executables are
            # gitignored, so no clean checkout has them, and conftest turns an
            # OSError naming a path under research/stock-executables into a
            # skip.  Testing exists() and continuing would bypass that and let
            # a checkout without the games look green rather than skipped.
            stock.open("rb").close()
            build = next(item for item in load_builds() if item.id == build_id)
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    rendered, _ = render_patched_bytes(stock, build, mode, [feature_id])
                    data = bytes(rendered)
                    image_base, sections = _sections(data)

                    # No section may be a zero-filled placeholder -- that is
                    # exactly the shape the missing header produced.
                    for section in sections:
                        self.assertTrue(
                            section["name"],
                            "VV%d %s: an unnamed section header is present"
                            % (game, mode),
                        )
                        self.assertGreater(
                            section["virtual_size"],
                            0,
                            "VV%d %s: %r has zero VirtualSize"
                            % (game, mode, section["name"]),
                        )
                        self.assertNotEqual(
                            section["virtual_address"],
                            image_base,
                            "VV%d %s: a section is mapped at the image base"
                            % (game, mode),
                        )

                    # The appended page is described, executable, and ends at EOF.
                    appended = [
                        item for item in sections if item["virtual_address"] == page_va
                    ]
                    self.assertEqual(
                        len(appended),
                        1,
                        "VV%d %s: no section describes the appended page"
                        % (game, mode),
                    )
                    page = appended[0]
                    self.assertTrue(
                        page["characteristics"] & 0x20000000,
                        "VV%d %s: the appended section is not executable" % (game, mode),
                    )
                    self.assertEqual(page["raw_pointer"] + page["raw_size"], len(data))

                    # SizeOfImage must still cover it.
                    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
                    size_of_image = struct.unpack_from(
                        "<I", data, e_lfanew + 0x18 + 0x38
                    )[0]
                    self.assertGreaterEqual(
                        image_base + size_of_image,
                        page["virtual_address"] + page["virtual_size"],
                        "VV%d %s: SizeOfImage does not cover the appended page"
                        % (game, mode),
                    )

                    # The installed hook must reach it, and the trampoline there
                    # must still perform the call it stole.
                    hook_file = _va_to_file(sections, hook_va)
                    self.assertIsNotNone(hook_file)
                    call = data[hook_file : hook_file + 5]
                    self.assertEqual(
                        call[0], 0xE8, "VV%d %s: hook is not a call" % (game, mode)
                    )
                    target = hook_va + 5 + struct.unpack_from("<i", call, 1)[0]
                    self.assertEqual(target, page_va)
                    target_file = _va_to_file(sections, target)
                    self.assertIsNotNone(
                        target_file,
                        "VV%d %s: the hook jumps to unmapped memory" % (game, mode),
                    )
                    trampoline = data[target_file : target_file + 9]
                    self.assertEqual(
                        trampoline[:4],
                        FLAG_READ,
                        "VV%d %s: trampoline does not read the flag first"
                        % (game, mode),
                    )
                    stolen = target + 9 + struct.unpack_from("<i", trampoline, 5)[0]
                    self.assertEqual(stolen, conception)



if __name__ == "__main__":
    unittest.main()
