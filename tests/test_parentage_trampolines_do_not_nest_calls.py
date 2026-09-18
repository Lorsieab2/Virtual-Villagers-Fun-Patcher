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

# The two games whose parentage trampoline wraps a game routine by replacing
# its call site. VV1 redirects conception call sites to stubs that `jmp`, and
# VV2/VV3 hook-and-resume, so none of them wrap a call.
WRAPPING_GAMES = {
    4: ("vv4_parentage_feature.json", 0x45E7B0),
    5: ("vv5_parentage_feature.json", 0x465E00),
}

# Both callees are __thiscall with seven arguments and end in `ret 0x1C`.
CALLEE_CLEANUP = 0x1C


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

    def test_the_trampoline_rebuilds_the_argument_frame(self) -> None:
        """Seven re-pushes before the call, so the callee gets its own frame.

        Without them the callee reads the game's arguments through two return
        addresses instead of one. The pushes all read the same displacement
        because each one lowers esp by four, moving the next argument down
        into that slot.
        """
        for game, (manifest, conception) in sorted(WRAPPING_GAMES.items()):
            with self.subTest(game=game):
                pages = payloads(manifest)
                self.assertTrue(pages, "%s has no appended page" % manifest)
                code, address = pages[0]
                stream = self.decoded(code, address)

                call_index = next(
                    (i for i, ins in enumerate(stream)
                     if ins.mnemonic == "call"
                     and ins.op_str == hex(conception)), None)
                self.assertIsNotNone(
                    call_index,
                    "no call to the conception routine in the page")

                pushes = [ins for ins in stream[:call_index]
                          if ins.mnemonic == "push"
                          and "esp" in ins.op_str]
                self.assertEqual(
                    len(pushes), 7,
                    "the seven arguments must be re-pushed before the call")

    def test_the_trampoline_cleans_the_callers_arguments(self) -> None:
        """It must end in the same `ret 0x1C` the routine it replaces used.

        A bare `ret` would strand 0x1C bytes of the caller's frame, because
        the caller expects the callee to have cleaned them.
        """
        for game, (manifest, conception) in sorted(WRAPPING_GAMES.items()):
            with self.subTest(game=game):
                code, address = payloads(manifest)[0]
                rets = [ins for ins in self.decoded(code, address, 0x100)
                        if ins.mnemonic == "ret"]
                self.assertTrue(rets, "the page never returns")
                self.assertTrue(
                    any(r.op_str and int(r.op_str, 16) == CALLEE_CLEANUP
                        for r in rets),
                    "the trampoline must clean the caller's arguments with "
                    "ret %#x, as the routine it replaces does" % CALLEE_CLEANUP)

    def test_no_stray_push_sits_between_entry_and_the_stolen_call(
        self,
    ) -> None:
        """Only the seven argument re-pushes may precede the call.

        The first version of this trampoline did `push ebx` and then called,
        which shifted the callee's frame by a further dword on top of the
        nested-call shift. Anything pushed that is not one of the seven
        argument copies reintroduces that class of bug.
        """
        for game, (manifest, conception) in sorted(WRAPPING_GAMES.items()):
            with self.subTest(game=game):
                code, address = payloads(manifest)[0]
                stream = self.decoded(code, address)
                call_index = next(
                    i for i, ins in enumerate(stream)
                    if ins.mnemonic == "call"
                    and ins.op_str == hex(conception))
                for ins in stream[:call_index]:
                    if ins.mnemonic != "push":
                        continue
                    self.assertRegex(
                        ins.op_str, r"^dword ptr \[esp \+ 0x[0-9a-f]+\]$",
                        "only argument re-pushes may precede the stolen call")


if __name__ == "__main__":
    unittest.main()
