"""The Quiet Hands' story trait "mute" (native/vvfp_story_upgrades/story_traits.inc): its per-save file and the
trait following its villager, in all five games.

native/vvfp_story_upgrades/story_traits_harness.c compiles the companion's trait store unchanged against real files
in a fresh folder under %TEMP% (scripts/build_story_traits_harness.ps1): the file written in the documented format
and read back by a new session; the trait following the villager through a death and a packed reload; a newborn in
the dead villager's record never inheriting it; a rename in play (a mask or a title on the name); a sex change in
play, after a reload, and with a save from before the change (the Sex Changes log); another village's file kept.
The emulated casting rule (a story-mute villager never takes a speaking role) is tests/test_event_content.py.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TheStoryTraitsFile(unittest.TestCase):
    def test_the_harness_on_real_files(self):
        script = ROOT / "scripts" / "build_story_traits_harness.ps1"
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                capture_output=True, text=True, timeout=600)
        out = result.stdout + result.stderr
        if result.returncode != 0 and "cl.exe" in out and "not recognized" in out:
            self.skipTest("the compiler is not installed")
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("failures: 0", result.stdout)
        for game in range(1, 6):
            self.assertIn(f"== game {game}", result.stdout)
        self.assertGreaterEqual(result.stdout.count("[PASS]"), 5 * 18)


if __name__ == "__main__":
    unittest.main()
