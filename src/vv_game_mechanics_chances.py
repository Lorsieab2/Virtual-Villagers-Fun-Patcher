"""Game Mechanics: the Chances groups -- every random roll that changes play, with its exact odds (all five games).

The owner (2026-10-24): exact odds for "anything with odds".  Each game's rolls are a table, ROLLS, in its own module
(src/vv_game_mechanics_chances_vv<N>.py, found by name); this module turns them into the page's lines.

THE GAMES' RANDOM NUMBERS.  Every game rolls through one routine, rand(n) (VV1 0x402F10, VV2 0x4031A0, VV3 0x4032D0,
VV4 0x4036D0, VV5 0x403660): for 1 <= n <= 32767 it is the C library's rand() % n.  rand() gives one of 32,768 values
(0 to 32767), every one equally often over the generator's whole cycle, so a roll's exact chance is the share of those
32,768 values whose remainder by n gives the outcome -- "rand(100) < 50" is 16,400 of 32,768 (50.05%), not 50%.  Each
Check below names one call of rand(n) in the stock exe (the address of the call), the n pushed for it, and the compare
and jump that read the result; tests/test_game_mechanics_chances.py reads every one of them from the exe and runs the
compare in the game's own code for all 32,768 values, so the chance shown is the one the game's code gives.

A Roll is one bullet: what is rolled, how often (every time in real-life time or per age unit, never a bare unit), and
its exact odds; its `subs` are the conditions that change them, as sub-bullets.  A Roll's `feature` is a patcher patch
that changes those odds: its words are shown (after the normal game's) only when the patch is in the game's exe.

LABELS (the owner, 2026-10-24): a roll read from the game's own reachable, running code at the cited addresses is
verified (gm.RUNNING); only what is not proven, or an estimate, carries UNCONFIRMED.

Nothing here writes anything.
"""
from __future__ import annotations

import functools
import importlib
from dataclasses import dataclass

import vv_game_mechanics as gm

CHANCES = "Chances"
BIRTHS = "Births and gender"
DRAWS = 32768
# Each game's rand(n) and the C library rand() it calls (both read by the tests from the stock exes).
RNG = {1: 0x402F10, 2: 0x4031A0, 3: 0x4032D0, 4: 0x4036D0, 5: 0x403660}
RAW_RAND = {1: 0x44B648, 2: 0x4686C8, 3: 0x46F3D8, 4: 0x471CF8, 5: 0x47CFD8}

# How often the age-unit rolls come, in real-life time (an age unit is 60 x speed real seconds).
AGE_UNIT = "once per age unit (an age unit is 3, 6 or 10 real-life minutes on Fast, Normal or Slow speed; 20 make a villager year)"

_JUMPS = {"jl": "<", "jb": "<", "jle": "<=", "jbe": "<=", "jg": ">", "ja": ">", "jge": ">=", "jae": ">=",
          "je": "==", "jne": "!="}


def _holds(r: int, op: str, k: int) -> bool:
    return {"<": r < k, "<=": r <= k, ">": r > k, ">=": r >= k, "==": r == k, "!=": r != k}[op]


@functools.lru_cache(maxsize=None)
def _hits(n: int, op: str, k: int) -> int:
    """How many of the 32,768 values v give (v % n) op k: counted once, then kept (the page renders them often)."""
    return sum(1 for v in range(DRAWS) if _holds(v % n, op, k))


@dataclass(frozen=True)
class Check:
    """One call of the game's rand(n) in the stock exe and the test of its result.
    site: the address of the call; n: the range pushed for it (None: worked out at run time);
    cmp: the constant the result is compared with (None: compared with a value worked out at run time);
    jump: the conditional jump after the compare; take: the roll's outcome is that jump taken (False: not taken);
    push: the address of the `push n`, when it is not the last push before the call (one call shared by branches)."""
    site: int
    n: int | None
    cmp: int | None = None
    jump: str | None = None
    take: bool = True
    push: int | None = None          # where n is pushed, when not just before the call (a call shared by branches)

    @property
    def count(self) -> int | None:
        """How many of the 32,768 values give the outcome, or None when n or the compare is worked out at run time."""
        if self.n is None or self.cmp is None or self.jump is None:
            return None
        hits = _hits(self.n, _JUMPS[self.jump], self.cmp)
        return hits if self.take else DRAWS - hits

    @property
    def chance(self) -> str:
        count = self.count
        return "?" if count is None else chance(count)


def chance(count: int, of: int = DRAWS) -> str:
    """An exact chance in words: "50.05%", "0.171% (1 in 585)", "100%"."""
    if count <= 0:
        return "0%"
    if count >= of:
        return "100%"
    p = 100.0 * count / of
    if p >= 1:
        text = f"{p:.2f}".rstrip("0").rstrip(".")
        return f"{text}%"
    text = f"{p:.3g}"
    return f"{text}% (1 in {round(of / count):,})"


def below(n: int, k: int) -> int:
    """How many of the 32,768 values give rand(n) < k (k may be past n: then every value)."""
    return _hits(n, "<", k)


def at_most(n: int, k: int) -> int:
    return below(n, k + 1)


def times(*counts: int) -> int:
    """The chance of several independent rolls all coming out, as a count of 32,768 (rounded)."""
    p = 1.0
    for c in counts:
        p *= c / DRAWS
    return round(p * DRAWS)


@dataclass(frozen=True)
class Roll:
    """One bullet.  `text` and each of `subs` may hold {0}, {1}, ...: the exact chance of checks[0], checks[1], ...
    `feature` / `patched`: a patch that changes these odds and the words for it, shown only with it in the exe."""
    text: str
    checks: tuple[Check, ...] = ()
    subs: tuple[str, ...] = ()
    verified: bool | str = gm.RUNNING
    group: str = CHANCES
    feature: str | None = None
    patched: str = ""
    sub_verified: tuple[bool | str, ...] = ()   # per sub-bullet, when one differs from the roll's own

    def words(self, text: str) -> str:
        return text.format(*(c.chance for c in self.checks))


NOTE = ("Every chance here is exact for the game's own random numbers: each roll takes one of 32,768 equally likely "
        "values and divides it by the roll's range, so \"below 50 out of 100\" comes 16,400 times in 32,768 (50.05%), "
        "not exactly 50%. Each was read from the game's own running code; how often it is rolled is given in real-life "
        "time or per age unit.")
BIRTH_NOTE = ("Births: how many babies a pregnancy brings and whether each is a boy or a girl, exactly from the game's "
              "own code. Every way a villager can be born or arrive is listed.")
# Only A New Home has a Golden Child; the sentence is not shown for The Secret City, which has none (an inherited
# rule that cannot happen there is never listed, the owner 2026-10-25).
GOLDEN_BIRTH = " A Golden Child counts as a birth."


def rolls(game: int) -> tuple[Roll, ...]:
    try:
        module = importlib.import_module(f"vv_game_mechanics_chances_vv{game}")
    except ImportError:
        return ()
    return tuple(getattr(module, "ROLLS", ()))


def facts(village: gm.Village) -> list[gm.Fact]:
    """The Chances and Births and gender groups for one game's page: one bullet per roll, its conditions as
    sub-bullets, and a patch's change after the normal game's odds only when the patch is in the game."""
    out: list[gm.Fact] = []
    table = rolls(village.game)
    for group, note in ((CHANCES, NOTE), (BIRTHS, BIRTH_NOTE)):
        mine = [r for r in table if r.group == group]
        if not mine:
            continue
        if group == BIRTHS and village.game != 3:
            note += GOLDEN_BIRTH
        out.append(gm.Fact(group, note, gm.RUNNING))
        for roll in mine:
            out.append(gm.Fact(group, roll.words(roll.text), roll.verified))
            for k, sub in enumerate(roll.subs):
                ok = roll.sub_verified[k] if k < len(roll.sub_verified) else roll.verified
                out.append(gm.Fact(group, roll.words(sub), ok, True))
            if roll.feature and village.has(roll.feature) is True:
                out.append(gm.Fact(group, f"With the patcher's \"{gm.feature_name(roll.feature)}\" (in this game): "
                                          f"{roll.words(roll.patched)}", roll.verified, True))
    return out
