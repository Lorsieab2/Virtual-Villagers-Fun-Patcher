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

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

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

# The conception routine cleans its seven copied arguments; the caller's
# originals remain on the stack for the trampoline to read afterwards.
FLAG_READ_MNEMONIC = "mov"


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
                    self._check_trampoline(
                        game, mode, data, target_file, target, conception
                    )

    def _check_trampoline(self, game, mode, data, target_file, target, conception):
        """Decode the trampoline and check what it does, not how it encodes it.

        Asserted as behaviour rather than as a byte pattern, so a correct change
        to the prologue does not fail a test it did not break -- pinning the
        first four bytes did exactly that when ebx preservation was added.
        """
        where = "VV%d %s" % (game, mode)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        # 0x100, not 0x60: the trampoline re-pushes the callee's seven
        # arguments before the stolen call, so its epilogue sits further in
        # than it did when the page merely wrapped the call.
        listing = list(md.disasm(data[target_file : target_file + 0x100], target))
        self.assertTrue(listing, "%s: trampoline did not disassemble" % where)
        decoded = [(item.mnemonic, item.op_str) for item in listing]

        # Only a checked snapshot and the seven copied arguments may precede
        # the stolen call.
        #
        # The hook replaces a call, so the game's call already pushed a return
        # address. A stray push between that return address and the seven
        # copied arguments shifts the callee's frame. A conception-total
        # snapshot is safe only when all seven copies read one dword farther
        # down the original frame.
        call_first = next(
            (i for i, item in enumerate(listing)
             if item.mnemonic == "call" and item.op_str.startswith("0x")),
            None,
        )
        self.assertIsNotNone(
            call_first, "%s: trampoline makes no direct call" % where)
        pushes = [item.op_str for item in listing[:call_first]
                  if item.mnemonic == "push"]
        if len(pushes) == 8:
            total = {4: "0x4d6de8", 5: "0x51d360"}[game]
            expected = ["dword ptr [%s]" % total] + [
                "dword ptr [esp + 0x20]"] * 7
        else:
            expected = ["dword ptr [esp + 0x1c]"] * 7
        self.assertEqual(pushes, expected,
                         "%s: copied argument frame is shifted" % where)

        # The trampoline impersonates the routine it replaces, so it must clean
        # the caller's arguments itself with the same `ret <n>`. A bare `ret`
        # would strand them.
        popad = next(
            (i for i, item in enumerate(decoded) if item[0] in ("popal", "popad")),
            None,
        )
        self.assertIsNotNone(popad, "%s: trampoline never restores the frame" % where)
        cleaning_ret = next(
            (item for item in listing
             if item.mnemonic == "ret" and item.op_str),
            None,
        )
        self.assertIsNotNone(
            cleaning_ret,
            "%s: trampoline must clean the caller's arguments with ret <n>"
            % where,
        )

        # The flag is read into ebx AFTER the stolen call.
        #
        # This previously required the opposite, on the premise that the
        # callee cleans its own arguments so they no longer exist afterwards.
        # That was true while the page WRAPPED the call. It is false now that
        # the page impersonates the routine: the callee pops only the copies
        # this page re-pushed, and the game's own seven arguments survive
        # untouched -- this page cleans those itself with its `ret 0x1C`.
        #
        # Reading afterwards is what lets ebx be preserved. Saving the
        # caller's ebx before the call would put a dword between esp and the
        # callee's arguments and shift its esp-relative reads, which is the
        # defect this whole page exists to avoid; and the flag cannot be read
        # into ebx before saving ebx, because the read destroys it. Doing both
        # after the call resolves that, and the displacement accounts for the
        # push: the seventh argument sits one dword higher.
        call_index = next(
            (
                i
                for i, item in enumerate(listing)
                if item.mnemonic == "call" and item.op_str.startswith("0x")
            ),
            None,
        )
        self.assertIsNotNone(call_index, "%s: trampoline makes no direct call" % where)
        flag_read = next(
            (
                i
                for i, item in enumerate(listing)
                if item.mnemonic == FLAG_READ_MNEMONIC
                and item.op_str.startswith("ebx, dword ptr [esp")
            ),
            None,
        )
        self.assertIsNotNone(flag_read, "%s: trampoline never reads the flag" % where)
        self.assertGreater(
            flag_read,
            call_index,
            "%s: the flag must be read after the call, so that saving ebx "
            "cannot shift the callee's argument frame" % where,
        )

        # And it must read the GAME's surviving argument, one dword above its
        # entry displacement to account for the pushed ebx.
        save_ebx = next(
            (i for i, item in enumerate(decoded) if item == ("push", "ebx")),
            None,
        )
        self.assertIsNotNone(save_ebx, "%s: the caller's ebx is never saved" % where)
        self.assertGreater(
            save_ebx,
            call_index,
            "%s: ebx is saved before the call, which shifts the frame" % where,
        )
        self.assertLess(
            save_ebx,
            flag_read,
            "%s: the flag read destroys ebx, so ebx must be saved first"
            % where,
        )

        # And the stolen call still goes where it went before the hook.
        self.assertEqual(
            int(listing[call_index].op_str, 16),
            conception,
            "%s: trampoline does not perform the stolen call" % where,
        )



if __name__ == "__main__":
    unittest.main()
