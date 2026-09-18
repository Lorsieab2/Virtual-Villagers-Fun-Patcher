"""VV1 captures the father at the conception call sites.

VV1 stores nothing about the father in the mother's record: its conception
routine receives a partner value and never stores it, and the field that once
looked like a father id turned out to be a skill value. So unlike VV2-VV5 there
is nothing to read at the success tails.

His record IS live at the call sites. sub_43BBC0 has six callers and no
indirect references, and each loads exactly one field off his record (+0x36C)
before discarding the pointer.

He travels in an argument slot the routine never reads. sub_43BBC0 ends in
`ret 0x10` and takes four stack arguments; disassembling every esp-based memory
operand in the whole routine finds reads of [esp+0x08], [esp+0x10] and
[esp+0x14] and NONE of [esp+0x0C]. So each call site is routed through a stub
that overwrites that dead argument with his record pointer, and the
success-tail trampolines read it back out of their own frame.

THE SLOT IS NOT IN MEMORY, and that is load-bearing. An earlier draft kept the
pointer at a fixed cave address; Codex caught that the cave is in .text
(0x60000020, R-X) and the Origins-composed page is .vv1mc with the same
characteristics, so the first conception would have written a read-only page
and access-violated. No test here could have caught it -- the manifests were
byte-correct and every jump target verified. Only the section characteristics
said otherwise, which is why one of these guards now checks them directly.

These guards pin the parts that would fail silently rather than loudly: a stub
aimed at the wrong register still assembles and captures a stranger, and a
trampoline reading the wrong displacement gets a neighbouring argument.
"""

from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MANIFEST = ROOT / "data/vv1_parentage_feature.json"
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"
STOCK = ROOT / "research/stock-executables/Virtual Villagers - A New Home.exe"

CONCEPTION_VA = 0x0043BBC0
CALL_SITES = (0x43DD33, 0x43DD54, 0x43DD7B, 0x43DD94, 0x447031, 0x447238)
CAVE_VA = 0x00456900
CAVE_FILE = 0x00056900
STUB_OFFSET = 0x170
STUB_SIZE = 0x10


def _feature():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["features"][0]


def _cave_payload():
    for patch in _feature()["patches"]:
        if int(patch["offset"], 16) == CAVE_FILE:
            return bytes.fromhex(patch["after"])
    raise AssertionError("the cave patch is missing")


def _is_clobbered_before_call(blob, call_va, base_reg):
    """Is `base_reg` written again between the +0x36C load and the call?

    Capstone-free so this guard keeps working without the optional
    dependency. Both register-to-register mov encodings have to be checked:
    0x44722E clobbers ecx with esi as `8B CE`, the /r form whose ModRM *reg*
    field names the destination, and an assembler is equally free to emit
    `89 F1` for the same instruction, where *rm* names it. Looking for only
    one form misses the very clobber this exists to detect.
    """
    start = call_va - 0x400000 - 96
    end = call_va - 0x400000
    window = blob[start:end]
    # Find the +0x36C load, and only look after it.
    load_at = None
    for i in range(len(window) - 6):
        if (
            window[i] == 0x8B
            and (window[i + 1] >> 6) == 2
            and (window[i + 1] & 7) != 4
            and window[i + 2 : i + 6] == b"\x6c\x03\x00\x00"
            and (window[i + 1] & 7) == base_reg
        ):
            load_at = i + 6
    if load_at is None:
        return False
    for i in range(load_at, len(window) - 1):
        modrm = window[i + 1]
        if (modrm >> 6) != 3:
            continue
        # 89 /r : mov r/m32, r32  -> destination is rm
        if window[i] == 0x89 and (modrm & 7) == base_reg:
            return True
        # 8B /r : mov r32, r/m32  -> destination is reg
        if window[i] == 0x8B and ((modrm >> 3) & 7) == base_reg:
            return True
    return False


class VV1CapturesTheFatherAtTheCallSitesTests(unittest.TestCase):
    def test_the_exporter_uses_the_capture_kind(self) -> None:
        """FATHER_NOT_RECORDED would short-circuit before the pointer is read."""
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn("FATHER_BY_CAPTURE", source)
        self.assertIn(
            "FATHER_BY_CAPTURE, 0, 0, 0x35C,",
            source,
            "VV1's layout row must declare the capture kind",
        )

    def test_the_validator_accepts_the_capture_kind(self) -> None:
        """Its else branch returns 0, which would refuse every VV1 record.

        A layout the validator rejects does not fail loudly -- the feature
        simply never writes a line, which looks exactly like a village with no
        births.
        """
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn(
            "|| g->father_kind == FATHER_BY_CAPTURE",
            source,
            "the layout validator must accept FATHER_BY_CAPTURE",
        )

    def test_every_call_site_is_redirected(self) -> None:
        """All six, or some births silently lose their father."""
        if not STOCK.is_file():
            self.skipTest("the exact-build VV1 executable is not available")
        blob = STOCK.read_bytes()
        patches = {int(p["offset"], 16): p for p in _feature()["patches"]}
        for va in CALL_SITES:
            file_off = va - 0x400000
            with self.subTest(site=hex(va)):
                self.assertIn(
                    file_off, patches, "call site is not redirected"
                )
                patch = patches[file_off]
                before = bytes.fromhex(patch["before"])
                self.assertEqual(
                    blob[file_off : file_off + len(before)],
                    before,
                    "the guard does not match the stock bytes",
                )
                self.assertEqual(
                    len(bytes.fromhex(patch["after"])),
                    len(before),
                    "the redirect changed width, so code after it shifts",
                )

    def test_each_redirect_lands_on_its_own_stub(self) -> None:
        """An off-by-one here still assembles and still runs."""
        patches = {int(p["offset"], 16): p for p in _feature()["patches"]}
        for index, va in enumerate(CALL_SITES):
            after = bytes.fromhex(patches[va - 0x400000]["after"])
            with self.subTest(site=hex(va)):
                self.assertEqual(after[0], 0xE8, "not a near call")
                rel = struct.unpack_from("<i", after, 1)[0]
                self.assertEqual(
                    va + 5 + rel,
                    CAVE_VA + STUB_OFFSET + index * STUB_SIZE,
                    "the redirect does not land on this site's stub",
                )

    def test_each_stub_returns_to_the_conception_routine(self) -> None:
        """A stub that does not reach sub_43BBC0 breaks conception itself."""
        payload = _cave_payload()
        for index in range(len(CALL_SITES)):
            start = STUB_OFFSET + index * STUB_SIZE
            stub = payload[start : start + STUB_SIZE]
            with self.subTest(stub=index):
                self.assertIn(0xE9, stub, "no jump back")
                j = stub.index(0xE9)
                rel = struct.unpack_from("<i", stub, j + 1)[0]
                site = CAVE_VA + start + j
                self.assertEqual(
                    site + 5 + rel,
                    CONCEPTION_VA,
                    "the stub does not tail-call the conception routine",
                )

    def test_no_stub_writes_into_the_image(self) -> None:
        """The regression Codex caught: a write target inside a R-X section.

        The cave lives in .text, which is 0x60000020 -- readable and
        executable, NOT writable. A stub storing to any absolute address in the
        image would access-violate on the first conception. Writing the
        caller's own stack cannot, because a stack page is always writable.
        """
        payload = _cave_payload()
        for index in range(len(CALL_SITES)):
            start = STUB_OFFSET + index * STUB_SIZE
            stub = payload[start : start + STUB_SIZE]
            with self.subTest(stub=index):
                # mov [esp+disp8], r32 is 89 /r with mod=01, rm=100 (SIB),
                # and a SIB base of esp. An absolute store would be 89 /r with
                # mod=00 rm=101, or the A3 short form for eax.
                self.assertNotEqual(
                    stub[0], 0xA3, "absolute store to eax's short form"
                )
                self.assertEqual(stub[0], 0x89, "not a register store")
                modrm = stub[1]
                self.assertEqual(
                    modrm >> 6, 1, "not an [esp+disp8] store"
                )
                self.assertEqual(
                    modrm & 7, 4, "not SIB-addressed, so not stack-relative"
                )
                self.assertEqual(stub[2], 0x24, "SIB base is not esp")

    def test_the_cave_section_is_not_writable(self) -> None:
        """States the premise the guard above depends on.

        If .text ever became writable this test would fail, and the reasoning
        in the docstring would need revisiting rather than silently holding.
        """
        if not STOCK.is_file():
            self.skipTest("the exact-build VV1 executable is not available")
        blob = STOCK.read_bytes()
        pe = struct.unpack_from("<I", blob, 0x3C)[0]
        count = struct.unpack_from("<H", blob, pe + 6)[0]
        opt = struct.unpack_from("<H", blob, pe + 20)[0]
        base = struct.unpack_from("<I", blob, pe + 24 + 28)[0]
        for index in range(count):
            off = pe + 24 + opt + index * 40
            vsize, vaddr, rsize, _ = struct.unpack_from("<IIII", blob, off + 8)
            chars = struct.unpack_from("<I", blob, off + 36)[0]
            start = base + vaddr
            if start <= CAVE_VA < start + max(vsize, rsize):
                self.assertFalse(
                    chars & 0x80000000,
                    "the cave's section is writable, so the reasoning that "
                    "forced the father onto the stack no longer applies",
                )
                return
        self.fail("the cave is not inside any section")

    def test_every_stub_writes_the_dead_argument(self) -> None:
        """Six stubs, one slot -- a stray address would capture nothing."""
        """[esp+0x08] at the stub, which is the routine's [esp+0x0C].

        One slot lower would overwrite the mother's index; one higher would
        overwrite a skill selector the routine does read. Either changes
        gameplay rather than merely logging the wrong thing.
        """
        payload = _cave_payload()
        for index in range(len(CALL_SITES)):
            start = STUB_OFFSET + index * STUB_SIZE
            stub = payload[start : start + STUB_SIZE]
            with self.subTest(stub=index):
                self.assertEqual(
                    stub[3],
                    0x08,
                    "the stub writes the wrong argument slot",
                )

    def test_each_stub_captures_the_register_its_site_uses(self) -> None:
        """Derived from the executable, not from the build script's own table.

        This is the mutation that survives every other guard: a stub naming the
        wrong register still assembles, still lands correctly, still tail-calls
        the routine, and still writes the slot. It just stores something that
        is not the father, and the log fills with a stranger's name.

        The father's register at each site is whatever the stock code loads
        +0x36C from, because that load is the game reading his appearance
        variant off his own record. So the check reads the nearest such load
        before each call and requires the stub to capture the same register.
        """
        if not STOCK.is_file():
            self.skipTest("the exact-build VV1 executable is not available")
        blob = STOCK.read_bytes()
        payload = _cave_payload()

        for index, va in enumerate(CALL_SITES):
            with self.subTest(site=hex(va)):
                call_off = va - 0x400000
                window = blob[call_off - 96 : call_off]
                # mov r32,[base+0x36C] is 8B /r with mod=10; rm is the base.
                base = None
                for i in range(len(window) - 6):
                    if (
                        window[i] == 0x8B
                        and (window[i + 1] >> 6) == 2
                        and (window[i + 1] & 7) != 4
                        and window[i + 2 : i + 6] == b"\x6c\x03\x00\x00"
                    ):
                        base = window[i + 1] & 7
                self.assertIsNotNone(
                    base, "no +0x36C load before this call site"
                )

                # The stub is  mov [esp+0x08], <reg>  ==  89 /r 24 08, where
                # the reg field of the ModRM byte names the source register.
                start = STUB_OFFSET + index * STUB_SIZE
                stub = payload[start : start + STUB_SIZE]
                self.assertEqual(stub[0], 0x89, "not a register store")
                source = (stub[1] >> 3) & 7

                # The register must still hold the father AT THE CALL, which
                # is not the same as having loaded him.
                #
                # This previously required the stub's register to be the base
                # of the +0x36C load. At 0x447238 that is ecx, and 0x44722E
                # does `mov ecx,esi` -- esi is the `this` pointer, the mother
                # -- so the stub would have handed the companion her record.
                # The companion rejects a father equal to the mother, so that
                # site could never have captured even with the displacement
                # right. eax carries him there instead: 0x447229 loads it from
                # [esp+0x14], the very slot ecx was loaded from, and nothing
                # writes it again before the call.
                #
                # So the rule is: either the register that loaded him, or one
                # loaded from the same stack slot, provided it is not written
                # again before the call.
                clobbered = _is_clobbered_before_call(blob, va, base)
                if clobbered:
                    self.assertNotEqual(
                        source,
                        base,
                        "stub %d stores the register the site clobbers "
                        "before the call" % index,
                    )
                else:
                    self.assertEqual(
                        source,
                        base,
                        "stub %d stores register %d, but the site loads the "
                        "father from register %d -- it would capture a "
                        "stranger" % (index, source, base),
                    )

    def test_each_trampoline_reads_the_right_displacement(self) -> None:
        """Measured from the routine's own pushes and pops, not assumed.

        The triplets tail and both singleton branches sit between `push edi` /
        `push esi` and the matching pops, so the argument is 8 bytes further
        down than at entry; the twins tail is past both pops and is not. pushad
        then adds 0x20 to all of them.

        Reading the wrong displacement silently fetches a neighbouring
        argument, which is a plausible-looking wrong pointer rather than a
        crash.
        """
        payload = _cave_payload()
        # The father is the dead SECOND argument, at entry-esp +0x08 --
        # not +0x0C, which is arg1. This test asserted 0x0C and so confirmed
        # the defect rather than catching it: every shipped trampoline read
        # arg3, a skill selector, and the owner's log reported "(not captured
        # for this birth)" on every single VV1 conception.
        #
        # Anchored at the call, where esp points at the return address and the
        # arguments follow at +0x04, +0x08, +0x0C, +0x10. The routine's own
        # reads agree: after its `push edi` it touches [esp+0x08], [esp+0x10]
        # and [esp+0x14] -- entry +0x04, +0x0C, +0x10 -- and never entry +0x08.
        expected = {0: 0x20 + 0x08 + 8, 1: 0x20 + 0x08 + 0, 2: 0x20 + 0x08 + 8}
        for index, want in expected.items():
            body = payload[index * 0x60 : (index + 1) * 0x60]
            with self.subTest(trampoline=index):
                # push dword ptr [esp+disp8] == FF 74 24 disp8. The FIRST such
                # push in each body is the father; the two after it read the
                # pushad frame at a fixed 0x08.
                #
                # The actual value is compared rather than merely asserting the
                # expected one appears somewhere: triplets and singleton share
                # a displacement, so a containment check still passes when
                # their two values are swapped -- which is exactly the mutation
                # that survived the first version of this guard.
                marker = b"\xff\x74\x24"
                self.assertIn(marker, body, "no father push in this body")
                at = body.index(marker)
                self.assertEqual(
                    body[at + 3],
                    want,
                    "trampoline %d reads the father at %#x, expected %#x"
                    % (index, body[at + 3], want),
                )

    def test_the_composed_payload_does_not_overlap_origins(self) -> None:
        """The composed cave moved twice; both earlier addresses were occupied.

        This compares against the Origins manifest, which is the overlap the
        renderer itself would reject. It is NOT a substitute for measuring free
        space against a real render -- Birth Control reserves the whole page
        through a generated payload that no manifest shows.
        """
        origins = ROOT / "data/vv1_origins_feature.json"
        if not origins.is_file():
            self.skipTest("the Origins manifest is not available")
        spans = []

        def walk(node):
            if isinstance(node, dict):
                off, after = node.get("offset"), node.get("after")
                if isinstance(off, str) and isinstance(after, str):
                    try:
                        spans.append((int(off, 16), len(after) // 2))
                    except ValueError:
                        pass
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(json.loads(origins.read_text(encoding="utf-8")))
        composed = _feature()["composition_patches"][
            "vv1_enable_origins_exclusive_features"
        ]
        for patch in composed:
            start = int(patch["offset"], 16)
            length = len(bytes.fromhex(patch["after"]))
            for other_start, other_length in spans:
                overlaps = (
                    start < other_start + other_length
                    and other_start < start + length
                )
                self.assertFalse(
                    overlaps,
                    "composed parentage at %#x+%#x overlaps Origins at %#x+%#x"
                    % (start, length, other_start, other_length),
                )


if __name__ == "__main__":
    unittest.main()
