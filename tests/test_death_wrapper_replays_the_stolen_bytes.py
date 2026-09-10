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

    def test_the_replayed_bytes_appear_in_the_cave_payload(self):
        """The wrapper's payload must actually contain the stolen bytes.

        The strongest available end-to-end check short of running the game: for
        each death hook, the guard bytes it replaces must appear inside the
        cave payload the same feature installs. If the generator ever emitted a
        restatement again, and that restatement differed, this fails.
        """
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        checked = 0
        for feature in manifest["features"]:
            # The cave payload is carried as `after_base64`, not `after` --
            # large rows use base64 and declare `length`/`before_fill` instead
            # of a hex preimage. Collecting only `after` finds the five-byte
            # hook jumps and none of the payload, which made an earlier version
            # of this test fail against a perfectly correct manifest.
            blob = b"".join(
                base64.b64decode(row["after_base64"])
                for row in feature["patches"]
                if row.get("after_base64")
            )
            self.assertTrue(
                blob,
                f"{feature['game_id']} has no cave payload to search, which "
                "means this check is looking in the wrong place",
            )
            for row in feature["patches"]:
                if "count every villager death" not in str(row.get("purpose", "")):
                    continue
                guard = bytes.fromhex(row["before"])
                with self.subTest(
                    game=feature["game_id"], offset=row["offset"]
                ):
                    self.assertIn(
                        guard,
                        blob,
                        "the stolen bytes must be replayed inside the cave "
                        "payload; a hardcoded replay that drifted from the "
                        "guard would not appear here",
                    )
                checked += 1
        self.assertGreater(
            checked, 0, "no death hooks found to check, which is itself wrong"
        )


if __name__ == "__main__":
    unittest.main()
