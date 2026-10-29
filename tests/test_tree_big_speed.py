"""Big family trees are drawn fast, and exactly as before (the owner, v1.35.85: "speed up big trees without changing
the picture").

The line routing kept recounting every pair of lines: the lanes' order (_order_lanes) counted every upright line
against every level one at each swap, and the separation of lines (_separate) asked every crowded bucket again
for each of up to ~120 places it tried.  Both now find once what does not change and count only what does.  The
pinned hashes below were made with the code from before the speed-up (v1.35.85 23272512): the same layout, the
same lines, the same picture, to the byte.  Made-up villages only; nothing outside is read.
"""
from __future__ import annotations

import hashlib
import random
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402

FIRST = "2026-01-01 10:00:00"


def big_village(n: int = 260, seed: int = 7) -> gen.Village:
    """A made-up village of `n` villagers: 16 founders, then generation after generation of couples from the one
    before with 1-4 children each, and a few arrivals."""
    rnd = random.Random(seed)
    people: dict[int, gen.Person] = {}

    def add(sex, father=None, mother=None):
        pid = len(people) + 1
        people[pid] = gen.Person(pid, f"V{pid} Clan{rnd.randint(1, 30)}", rnd.randint(0, 29), rnd.randint(0, 29),
                                 sex=sex, age=rnd.randint(100, 1600), alive=rnd.random() < 0.7, father=father,
                                 mother=mother, first_seen=FIRST, arrived=father is None,
                                 how="Founder" if father is None else "")
        if not people[pid].alive:
            people[pid].gone = "died"
        return pid
    now = [add("Male" if k % 2 else "Female") for k in range(16)]
    while len(people) < n:
        men = [q for q in now if people[q].sex == "Male"]
        women = [q for q in now if people[q].sex == "Female"]
        rnd.shuffle(men)
        nxt = []
        for f, m in zip(men, women):
            for _ in range(rnd.randint(1, 4)):
                if len(people) >= n:
                    break
                nxt.append(add(rnd.choice(("Male", "Female")), f, m))
        nxt += [add(rnd.choice(("Male", "Female"))) for _ in range(rnd.randint(0, 3)) if len(people) < n]
        now = nxt or [add("Male"), add("Female")]
    v = gen.Village(3, 1, "Made-up Tribe", people)
    gen._generations(v, {FIRST: set(people)})
    gen.number_people(v)
    return v


def picture(v: gen.Village, edits: ft.Edits) -> str:
    """Every page's layout and lines, hashed."""
    ft.arrange(v, edits)
    first = ft.layout(v, edits)
    lays = [first] + [ft.layout(v, edits, k) for k in range(1, first.pages)]
    data = [(sorted(lay.x.items()), sorted(lay.y.items()), lay.width, lay.height, ft.lines(lay)) for lay in lays]
    return hashlib.sha256(repr(data).encode("utf-8")).hexdigest()[:16]


# Made with the code before the speed-up (see above).
PINNED = {
    ("dynamic", 260, 7): "bb1c01bac01d5939",
    ("rows", 260, 11): "a40f8071901b1d7a",
    ("packed", 200, 3): "b8c13584f81de9e6",
}


class SamePictureFaster(unittest.TestCase):
    def test_the_same_layout_and_lines_as_before(self) -> None:
        for (positioning, n, seed), want in PINNED.items():
            with self.subTest(positioning=positioning):
                got = picture(big_village(n, seed), ft.Edits(positioning=positioning))
                self.assertEqual(got, want)

    def test_a_260_villager_tree_is_laid_out_quickly(self) -> None:
        v = big_village()
        t = time.perf_counter()
        picture(v, ft.Edits(positioning="rows"))
        # Generous (a busy machine): the old routing took several times this on the owner's large villages.
        self.assertLess(time.perf_counter() - t, 30.0)


if __name__ == "__main__":
    unittest.main()
