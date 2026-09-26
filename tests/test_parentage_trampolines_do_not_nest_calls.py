"""A trampoline that replaces a call must not nest another call inside it.

VV4 and VV5 crashed on startup in every build that selected their parentage
log. The owner reported it; the Windows crash dumps named the cause exactly.

The hook replaces `call <conception routine>` at the game's own call site, so
the game's `call` has already pushed a return address by the time the
trampoline runs. Doing a second `call` to the same routine pushes another, and
the callee then starts with TWO return addresses below its arguments and reads
every one of them a dword high.

The dump made that concrete: walking the frame from the trampoline's return
address showed the callee's "arg1" holding the game's own return address, and
MSVC's string copy faulting on a source pointer of 0x1 -- a save-slot index
read where a name pointer belongs. The routine also builds the save-slot name
list, which is why a parentage patch produced a startup crash rather than a
conception-time one.

The correction is for the trampoline to impersonate the routine it replaces:
re-push the arguments, call, and clean the caller's arguments itself with the
same `ret <n>` the original used. These guards check the emitted bytes, since
that is where the defect lived -- the source read plausibly either way.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# VV4 and VV5 no longer wrap a call at all. Their hook moved from one call
# site to the conception routine's success exit (so every conception path is
# logged -- see tests/test_vv45_every_conception_path_is_logged.py): the page is
# entered by a JMP from inside the routine, runs in the routine's own frame, and
# JMPs back. There is no replaced call, so the double-return-address defect
# this file was written for cannot occur -- provided no page ever CALLS the
# conception routine again. That is what is pinned now.
TAIL_HOOKED_GAMES = {
    4: ("vv4_parentage_feature.json", 0x45E7B0, 0x45E8E4, 0x45E8EE, 0x45E922),
    5: ("vv5_parentage_feature.json", 0x465E00, 0x465F34, 0x465F3E, 0x465F44),
}


def payloads(manifest_name):
    """Every appended page in a rendered parentage manifest."""
    record = json.loads(
        (ROOT / "data" / manifest_name).read_text(encoding="utf-8"))
    out = []
    stack = [record]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("append_bytes") and node.get("page_virtual_address"):
                out.append((bytes.fromhex(node["append_bytes"]),
                            int(node["page_virtual_address"], 16)))
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return out


class ParentageTrampolinesDoNotNestCallsTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import capstone  # noqa: F401
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("capstone is not installed")

    def decoded(self, code, address, limit=0x80):
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        return list(md.disasm(code[:limit], address))

    def test_no_page_calls_the_conception_routine(self) -> None:
        """The defect needed a nested call to the routine; none may exist."""
        for game, (manifest, conception, _, _, _) in sorted(TAIL_HOOKED_GAMES.items()):
            for code, address in payloads(manifest):
                with self.subTest(game=game, page=hex(address)):
                    stream = self.decoded(code, address, 0x100)
                    self.assertFalse(
                        [ins for ins in stream
                         if ins.mnemonic == "call" and ins.op_str == hex(conception)],
                        "a parentage page calls the conception routine again")

    def test_the_page_returns_through_the_replayed_exit(self) -> None:
        """Entered by jmp, it must end by replaying the stolen exit and
        jumping back to the instruction after it -- never by `ret`, which
        would return from the routine early."""
        for game, (manifest, _, _, resume, reject) in sorted(TAIL_HOOKED_GAMES.items()):
            for code, address in payloads(manifest):
                with self.subTest(game=game, page=hex(address)):
                    stream = self.decoded(code, address, 0x100)
                    text = [(ins.mnemonic, ins.op_str) for ins in stream]
                    popad = text.index(("popal", ""))
                    self.assertEqual(text[popad + 1], ("test", "bl, bl"))
                    self.assertEqual(text[popad + 2], ("jne", hex(reject)))
                    self.assertEqual(text[popad + 4], ("jmp", hex(resume)))
                    self.assertNotIn("ret", [m for m, _ in text[:popad + 5]])


if __name__ == "__main__":
    unittest.main()
