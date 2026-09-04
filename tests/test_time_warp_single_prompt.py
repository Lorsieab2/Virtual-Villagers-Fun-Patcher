"""One Time Warp click must produce one prompt, and it must name the LIVE speed.

Two properties, asserted for all five games, because both drifted per-game.

**One prompt.** The companion owns the whole interaction: it confirms, applies
and reports. So the executable must not add a dialog of its own around it. VV1,
VV2, VV3 and VV4 all fall through silently when the companion reports the player
cancelled; VV5 alone routed that to a `cancelled:` label that showed a second
"Time Warp was canceled" box, making one click produce two dialogs in exactly
one of the five games.

**Live speed.** The prompt has to quote the speed as it is at the instant the
player clicks, not one sampled earlier and cached -- otherwise it reads "On
normal game speed" after the player changed speed with the menu already open.
Each companion must therefore read the speed field out of the world object
inside the confirmation function, before it formats the message.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# game -> (companion source, confirmation function, speed field offset)
COMPANIONS = {
    "vv1": ("native/vv1_origins_icons/vv1_origins_icons.c",
            "ShowOriginsTimeWarp", "VV1_TW_SPEED_OFFSET"),
    "vv2": ("native/vv2_origins_icons/vv2_origins_icons.c",
            "ShowVV2TimeWarp", "VV2_TW_SPEED_OFFSET"),
    "vv3": ("native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
            "ShowVV3TimeWarp", "vv3_speed_field"),
    "vv4": ("native/vv4_origins_icons/vv4_origins_icons.c",
            "ShowVv4TimeWarp", "VV4_TW_SPEED_OFFSET"),
    "vv5": ("native/vv5_task9_origins/vv5_task9_origins.c",
            "ShowVv5TimeWarp", "VV5_TW_SPEED_OFFSET"),
}

# game -> generator holding the executable-side dispatch
GENERATORS = {
    "vv1": "scripts/build_vv1_origins_feature.py",
    "vv2": "scripts/build_vv2_origins_feature.py",
    "vv3": "scripts/build_vv3_origins_feature.py",
    "vv4": "scripts/build_vv4_origins_feature.py",
    "vv5": "scripts/build_vv5_task9_native_actions.py",
}

# Labels a cancel may branch to: they reopen or close the menu and say nothing.
SILENT_TARGETS = {"menu_loop", "menu", "menu_done", "done"}

CONFIRM_TEXT = "On %s game speed, this will advance %d villager years."


def body(source: str, func: str) -> str:
    """The text of one C function, from its signature to the closing brace."""
    # Signatures vary: most carry __declspec(dllexport), VV3 deliberately does
    # not (that would publish the decorated name too), and the return type sits
    # behind __stdcall. Anchor on the name at the head of its own line instead.
    m = re.search(rf"^[^\n]*\b{re.escape(func)}\s*\(", source, re.M)
    if m is None:
        raise AssertionError(f"{func} not found")
    start = source.index("{", m.end())
    depth, i = 0, start
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"{func} has no closing brace")


class TimeWarpPromptTests(unittest.TestCase):
    def test_every_companion_quotes_the_speed_it_just_read(self) -> None:
        for game, (path, func, speed) in COMPANIONS.items():
            with self.subTest(game=game):
                src = (ROOT / path).read_text(encoding="utf-8", errors="replace")
                fn = body(src, func)

                self.assertIn(
                    CONFIRM_TEXT, fn,
                    f"{game}: the confirmation does not name the speed and years",
                )
                read = fn.find(speed)
                self.assertNotEqual(
                    read, -1,
                    f"{game}: {func} never reads the speed field ({speed}); a "
                    "cached speed would misreport a speed changed with the menu open",
                )
                self.assertLess(
                    read, fn.index(CONFIRM_TEXT),
                    f"{game}: the speed is read after the prompt is formatted",
                )

    def test_exactly_one_confirmation_box_per_companion(self) -> None:
        for game, (path, func, _speed) in COMPANIONS.items():
            with self.subTest(game=game):
                fn = body((ROOT / path).read_text(encoding="utf-8", errors="replace"),
                          func)
                asked = fn.count("MB_OKCANCEL") + fn.count("MB_YESNO")
                self.assertEqual(
                    asked, 1,
                    f"{game}: {func} asks {asked} times; one click must ask once",
                )

    def test_the_executable_adds_no_dialog_when_the_player_cancels(self) -> None:
        """Return 0 must reach a silent label in every game.

        This is the assertion VV5 failed: `jz cancelled` printed a second box
        after the companion's own prompt had already been dismissed.
        """
        for game, path in GENERATORS.items():
            with self.subTest(game=game):
                src = (ROOT / path).read_text(encoding="utf-8", errors="replace")

                # The dispatch is the `call`/`call eax` whose result is tested
                # against 0 and then compared with 1 (applied). Match on that
                # shape rather than a label name, which differs per game.
                hits = re.findall(
                    r"test eax, eax\s*\n\s*(?:#[^\n]*\n\s*)*j(?:z|e)\s+(\w+)"
                    r"(?:\s*\n\s*(?:#[^\n]*\n\s*)*(?:cmp eax, 1|jmp \w+))",
                    src,
                )
                warp = [h for h in hits if "time" in h or h in SILENT_TARGETS
                        or h == "cancelled"]
                self.assertTrue(warp, f"{game}: no Time Warp cancel branch found")
                for target in warp:
                    self.assertIn(
                        target, SILENT_TARGETS,
                        f"{game}: a cancel branches to {target!r}, which shows a "
                        "message -- the companion already owns the interaction, "
                        "so this makes one click produce two dialogs",
                    )


if __name__ == "__main__":
    unittest.main()
