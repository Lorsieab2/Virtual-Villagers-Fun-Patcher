"""A death wrapper must replay the bytes it stole, not a restatement of them.

The generator used to emit `mov dword ptr [ecx + 0x0C], 0` as the instruction
replayed after counting. That is correct today only by coincidence: every game
currently shipping this feature hooks that same instruction, so the hardcoded
text and the site's own `guard` bytes are the same seven bytes.

The coincidence ends the moment a game hooks anything else -- The Lost Children
has no cause-of-death field and its damage sites open with
`lea eax, [<base> + <index> + 0x52C]` in four different encodings. A hardcoded
replay there would execute the wrong instruction on resume, which is a crash or
a silently wrong count depending on the site.

So the wrapper replays `guard` verbatim. This test pins that, and pins the two
properties that make the change safe:

  * the emitted payload for every currently-shipping game is unchanged, and
  * `guard` really is the stolen bytes, because the generator refuses to build
    when it does not match what the stock image holds at `hook_va`.

The second is what makes the first meaningful. Replaying a field that had drifted
from the executable would be worse than a hardcoded instruction, not better.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GENERATOR = ROOT / "scripts" / "build_statistics_features.py"
MANIFEST = ROOT / "data" / "statistics_features.json"
STOCK = ROOT / "research" / "stock-executables"

EXE_BY_GAME = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}


def _generator_source():
    return GENERATOR.read_text(encoding="utf-8")


class DeathWrapperReplaysTheStolenBytes(unittest.TestCase):
    def test_the_generator_does_not_hardcode_a_replay_instruction(self):
        """The old hardcoded replay must be gone from the death emitter.

        Asserted on the parsed source rather than by substring, so the
        explanatory comment describing the old form -- which necessarily quotes
        it -- cannot keep this test green after a revert. A source-slicing test
        that matches its own comment is a known way to pass for the wrong
        reason.
        """
        tree = ast.parse(_generator_source())
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        offenders = [
            text
            for text in literals
            if "mov dword ptr [ecx + 0x0C], 0" in text
        ]
        self.assertEqual(
            [],
            offenders,
            "the death wrapper must replay `guard`, not a hardcoded "
            "instruction that only happens to match it",
        )

    def test_the_stolen_bytes_are_verified_against_the_stock_image(self):
        """`guard` is checked against the executable before it is replayed.

        This is the property that makes replaying `guard` safe. Without it the
        change would swap a wrong-but-known instruction for an unverified one.
        """
        source = _generator_source()
        self.assertIn(
            "death hook guard does not match",
            source,
            "the generator must refuse to build when the recorded guard bytes "
            "are not what the stock image holds at the hook",
        )

    def test_every_shipped_death_hook_matches_its_stock_bytes(self):
        """The recorded guards agree with the executables, right now.

        The generator's check runs at build time; this runs against the
        committed manifest, so a manifest edited by hand cannot slip past.
        """
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        checked = 0
        for feature in manifest["features"]:
            game_id = feature["game_id"]
            exe = STOCK / EXE_BY_GAME[game_id]
            if not exe.is_file():
                continue
            image = exe.read_bytes()
            for row in feature["patches"]:
                purpose = str(row.get("purpose", ""))
                if "count every villager death" not in purpose:
                    continue
                offset = int(row["offset"], 0)
                before = bytes.fromhex(row["before"])
                with self.subTest(game=game_id, offset=row["offset"]):
                    self.assertEqual(
                        image[offset:offset + len(before)],
                        before,
                        "the recorded preimage is not what the stock image "
                        "holds there",
                    )
                checked += 1
        if not checked:
            self.skipTest(
                "requires a local game file that is gitignored and absent: "
                "no death hook could be checked against its executable"
            )

    def test_each_wrapper_replays_its_own_guard_in_its_own_slot(self):
        """Every death wrapper must contain its stolen bytes, at its own slot.

        Two earlier versions of this assertion could not fail, and both reasons
        are worth keeping because neither is visible from reading it.

        **It read the committed manifest.** Deleting `death_guard` from the
        generator's `death_wrapper = ...` line left this test green: the
        manifest on disk is then *stale*, not wrong, so the test measured a
        file the change never touched. It only went red if someone happened to
        regenerate first. The payload is now built by calling ``build_game``
        here, so the bytes under test are produced by the code under test.

        **It searched the whole payload.** Every shipping game has *two* death
        hooks with the same seven guard bytes:

            vv3, vv4, vv5:  2 hooks each, guard C7410C00000000 for both

        so a whole-payload ``assertIn`` is satisfied by the sibling wrapper
        even when one wrapper has lost its replay entirely. Each check is now
        scoped to that wrapper's own ``slot``.

        Both were found by review rather than by my own mutation runs, which
        had all targeted the manifest rather than the generator -- the same
        error as mutating a list instead of the derivation that fills it.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        spec = importlib.util.spec_from_file_location(
            "_statistics_generator", GENERATOR
        )
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)

        companion = hashlib.sha256(generator.COMPANION.read_bytes()).hexdigest().upper()

        checked = 0
        for game_id, config in generator.GAMES.items():
            hooks = config.get("death_hooks") or []
            if not hooks:
                continue
            exe = ROOT / "research" / "stock-executables" / str(config["exe"])
            if not exe.is_file():
                continue

            feature = generator.build_game(game_id, config, companion)
            payloads = [
                base64.b64decode(row["after_base64"])
                for row in feature["patches"]
                if row.get("after_base64")
            ]
            self.assertEqual(
                len(payloads),
                1,
                f"{game_id} must emit exactly one cave payload for slots to "
                "be meaningful",
            )
            payload = payloads[0]

            for hook in hooks:
                guard = bytes.fromhex(str(hook["guard"]))
                slot = int(hook["slot"])
                # The wrapper occupies [slot, next wrapper or end). Bounding it
                # by the next slot is what stops a sibling satisfying this.
                later = [
                    int(other["slot"])
                    for other in hooks
                    if int(other["slot"]) > slot
                ]
                end = min(later) if later else len(payload)
                window = payload[slot:end]
                with self.subTest(game=game_id, slot=hex(slot)):
                    self.assertTrue(
                        window,
                        f"{game_id} slot {slot:#x} is empty, so this check "
                        "would pass vacuously",
                    )
                    self.assertIn(
                        guard,
                        window,
                        "the wrapper at this slot must replay ITS OWN stolen "
                        "bytes; a whole-payload search would be satisfied by "
                        "the sibling wrapper, which shares the same guard",
                    )
                checked += 1

        if not checked:
            self.skipTest(
                "requires a local game file that is gitignored and absent: "
                "no death wrapper could be generated"
            )
        self.assertGreaterEqual(
            checked, 2, "at least one game ships two death hooks"
        )


if __name__ == "__main__":
    unittest.main()
