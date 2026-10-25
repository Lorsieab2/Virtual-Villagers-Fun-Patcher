"""Game Mechanics: the Genetics group -- how each game gives a villager its head and body (the owner, 2026-10-24:
"how head genetics works").

Every rule below was traced in the game's own stock executable (inputs\\vvN-stock-copy), on code the game reaches
from its own call paths (the owner's rule, 2026-10-24: reachable code read statically counts as verified; dead code
does not).  The addresses are the game's own.  A head or a body value is a ROW of the game's own head or body
pictures (Images\\male_heads*.png, female_heads*.png, <sex>_bodies*.png), counted from 0.

THE LATER GAMES' INHERITANCE (The Lost Children, The Secret City, The Tree of Life, New Believers).  One creator
makes every villager (VV2 0x44C600, VV3 0x456120, VV4 0x45EF10, VV5 0x4681F0).  Of its 14 stack arguments, the
7th to 10th are the father's body, the father's head, the mother's body and the mother's head: a birth passes the
mother's own head and body (read from her at the delivery) and the father's head and body as the game copied them
onto her at the conception (VV2 0x43BE40..0x43BE8E; VV3 0x46037F..0x4603B6; VV4 0x468819..0x468853; VV5
0x4730E8..0x473120).  The head is then (identical in all four, rand(n) being the game's rand() % n):
    if rand(100) >= 5 and any of the four is not 0:  (father's head + mother's head) / 2 + rand(3) - 1
    else:                                            rand(30)
and a result below 0 is made 0, above 29 is made 29.  The body is rand(30) in VV2 and rand(29) in the others --
never the parents'.  A 14th argument, when not 0, then replaces both from fixed lists by sex: only VV2's new-village
setup passes it (its first two villagers); in VV3, VV4 and VV5 every caller passes 0, so their lists are dead code
and are not shown.  The second and third babies of a pregnancy are copies of the first's looks (VV2 0x44D009..
0x44D01B; VV3 0x45C520 from 0x4566E0; VV4 0x465CE0 from 0x45D9B0; VV5 0x46F5C0 from 0x4687F0).

A NEW HOME (VV1) has no inheritance: its creator 0x43C350 rolls the body and the head at random by sex
(0x43C616..0x43C647) and never reads a parent's looks; the Golden Child's family number (199) gives head 19 and
body 19 (0x43C7AF..0x43C7F5).  Its twins and triplets copy the first baby's sex, body and head (0x43C9C1..0x43C9DF).

WHAT CHANGES A HEAD LATER, in the game itself: a sweep of every instruction writing the head field found, besides
the creators, the twin copies and the new-village setup, only these -- A New Home's "A Mysterious Vial" drink
(0x42C92D..0x42CA41), The Lost Children's "A Mysterious Vial" drink (0x4395DF..0x439707) and The Secret City's
obsidian vial (its event action at vtable 0x47F008: the roll 0x4175BB, the new head 0x417634).  The Tree of Life
and New Believers have none; their head is written only by the creator and by whole-record copies.

PER VILLAGER.  The Lost Children to New Believers keep, on each child's own record, its parents' names and the
head and body each parent passed at the birth (the save's fields vv_last_names.FIELDS[n].looks); the page shows the
child's head beside them, read from the save -- never a guessed parent.  A New Home's save holds no parents.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm

GENETICS = gm.GENETICS

ORIGINS = "vv{}_enable_origins_exclusive_features"
STORY = "vv{}_story_cheat_upgrades"
GENETICS_PATCH = "vv1_genetics"

# The later games' creator, its head roll and its body roll, the birth's call, and the twin copy.
_LATER = {
    2: dict(creator="0x44C600", head="0x44CBA8..0x44CC2F", body=("0x44CC35", 30), birth="0x43BE8E",
            twin="0x44D009..0x44D01B, in the twin and triplet creator 0x44CEC0"),
    3: dict(creator="0x456120", head="0x4564A7..0x456519", body=("0x456520", 29), birth="0x4603B6",
            twin="0x45C520 called from 0x4566E0, via the twin and triplet creator 0x45F1D0"),
    4: dict(creator="0x45EF10", head="0x45F235..0x45F2A7", body=("0x45F2AE", 29), birth="0x468853",
            twin="0x465CE0 called from 0x45D9B0, via the twin and triplet creator 0x466310"),
    5: dict(creator="0x4681F0", head="0x46853A..0x4685AC", body=("0x4685B3", 29), birth="0x473120",
            twin="0x46F5C0 called from 0x4687F0, via the twin and triplet creator 0x46FD70"),
}
# The share of each of the three heads around the parents' average, and of any other head (per birth).
NEAR = 0.95 / 3 + 0.05 / 30
FAR = 0.05 / 30


def _pct(share: float) -> str:
    text = f"{share * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _patch_lines(village: gm.Village) -> list[gm.Fact]:
    """The patches that change a head, only when the game has them (the owner, 2026-10-24: the normal game first,
    then the patch; nothing said of a patch the game does not have)."""
    out = []
    g = village.game
    if g == 1 and village.has(GENETICS_PATCH):
        out.append(gm.Fact(GENETICS, (
            f"With the patcher's \"{gm.feature_name(GENETICS_PATCH)}\" (in this game): a baby's head comes from "
            "its parents as in the later games -- the father's and the mother's heads added and halved (dropping "
            "any half), then -1, 0 or +1, one chance in 3 each; on 5 births in 100 the head the game rolled "
            "instead. A boy stays within 0 to 18 (never the Golden Child's 19), a girl within 0 to 19. The "
            "father is the one Show Parents recorded at the conception; when it knows none, the mother's head "
            "alone. Twins and triplets share the first baby's head; bodies stay random. (\"VVFP VV1 "
            "Genetics.dll\", at 0x43C647, for a birth's first child only.)"), gm.RUNNING))
    if village.has(ORIGINS.format(g)):
        out.append(gm.Fact(GENETICS, (
            f"With the patcher's \"{gm.feature_name(ORIGINS.format(g))}\" (in this game): Change Appearance on the "
            "Villager Details screen sets a villager's head (and body) to any the player picks, and Change Appearance "
            "for All can give the whole village random heads by sex or heads of one hair colour (Black, Brown, Red, "
            "Blonde or Other). Neither changes anyone's recorded parents."), gm.RUNNING))
    if g in (1, 2, 3) and village.has(STORY.format(g)):
        event = {1: "A Mysterious Vial (red, from the sea)", 2: "A Mysterious Vial (green)",
                 3: "The Mysterious Vial (obsidian)"}[g]
        out.append(gm.Fact(GENETICS, (
            f"With the patcher's \"{gm.feature_name(STORY.format(g))}\" (in this game): Pick Island Event can run "
            f"{event} with the new head chosen instead of rolled."), gm.RUNNING))
    return out


def _vv1() -> list[gm.Fact]:
    f = gm.Fact
    return [
        f(GENETICS, ("A New Home has no head genetics: a baby's head and body are rolled at random when it is born, "
                     "and neither parent's looks are read (the creator 0x43C350, rolls at 0x43C616..0x43C647). A boy "
                     "gets any head 0 to 18 and any body 0 to 18, 1 chance in 19 each; a girl any head 0 to 19 and "
                     "any body 0 to 19, 1 chance in 20 each."), gm.RUNNING),
        f(GENETICS, ("Twins and triplets: the second and third babies copy the first baby's sex, body and head "
                     "(0x43C9C1..0x43C9DF, the creator 0x43C840 called at 0x42F021 and 0x42F06D), so they always "
                     "look alike."), gm.RUNNING),
        f(GENETICS, ("The Golden Child (family number 199, made at 0x42EF5F) is always a boy with head 19 and body "
                     "19 (0x43C7AF..0x43C7FB): the last row of the men's pictures, which no other boy is born with."),
          gm.RUNNING),
        f(GENETICS, ("A New Home has 20 heads (0 to 19) and 20 bodies (0 to 19) for each sex, one row each of its "
                     "own pictures, and no separate old-age head pictures."), gm.RUNNING),
        f(GENETICS, ("What changes a head later: only the island event \"A Mysterious Vial\" whose drinker \"doesn't "
                     "quite feel\" themselves afterwards (Pick Island Event's \"A Mysterious Vial (red, from the "
                     "sea)\"), when the villager drinks it: the head is rolled again, a man any of 0 to 18, a "
                     "woman any of 0 to 19 (it can come out the same), and the body is kept (0x42C92D..0x42CA41). "
                     "Pouring it out changes nothing. Growing older never changes the head."), gm.RUNNING),
    ]


def _later(game: int) -> list[gm.Fact]:
    f = gm.Fact
    t = _LATER[game]
    body_at, body_n = t["body"]
    out = [
        f(GENETICS, (f"A baby's head comes from both parents: the game adds the father's head and the mother's head, "
                     "halves it (dropping any half) and adds -1, 0 or +1, one chance in 3 each; a result below 0 "
                     "becomes 0 and one above 29 becomes 29. On 5 births in 100 it instead picks any head 0 to 29, "
                     f"1 chance in 30 each. (The creator {t['creator']}, head at {t['head']}; the birth's call "
                     f"{t['birth']} passes the mother's head at the birth and the father's as copied onto her at the "
                     "conception.)"), gm.RUNNING),
        f(GENETICS, (f"So each of the 3 heads around the parents' average comes {_pct(NEAR)} of the time and any "
                     f"other head {_pct(FAR)}; when the parents average 0, the -1 also becomes 0, so head 0 "
                     "comes 63.5% of the time (29 likewise when both parents have head 29). The 5-in-100 pick is why a few children's heads are far from "
                     "both parents'."), gm.RUNNING),
        f(GENETICS, ("A father or mother with head 0 counts as head 0 in that sum; only when both parents' heads "
                     "and bodies are all 0 is the head picked from 0 to 29 every time."), gm.RUNNING),
        f(GENETICS, ("The body is never inherited: any body 0 to "
                     + (f"29, 1 chance in 30 each ({body_at})." if body_n == 30 else
                        f"28, 1 chance in 29 each ({body_at}); body 29 is never given at birth.")), gm.RUNNING),
        f(GENETICS, ("Twins and triplets: the second and third babies copy the first baby's head and body "
                     f"({t['twin']}), so they always look alike."), gm.RUNNING),
    ]
    if game == 2:
        out.append(f(GENETICS, (
            "The Gong of Wonder's pregnancies have the father \"?\" with head 0 and body 0 (0x44EB1D..0x44EB3E), so "
            "such a baby's head is half the mother's head, -1, 0 or +1 (or any head on 5 births in 100)."),
            gm.RUNNING))
        out.append(f(GENETICS, (
            "A new village's first two villagers take their looks from fixed lists (0x44CC54..0x44CCA3, passed only "
            "at 0x4252F2, 0x425347 and 0x42537B): a man one of the heads 0, 1, 2, 3, 6, 7, 9, 10, 11, 12, 16, 17, 18, "
            "20, 21, 28 or 29 and the bodies 0, 1, 2, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14 or 15; a woman one of the "
            "heads 1, 4, 8, 17, 18, 19, 26, 27, 28 or 29 and the bodies 10, 12, 15, 16, 18, 19, 22, 23 or 29, each "
            "equally likely."), gm.RUNNING))
    elif game == 5:
        # Nothing about Joey: his only writer, the abandoned-infants event (0x4155E0 -> 0x471A50), is inherited and
        # never drawn (its condition 0x415B10 is `xor al, al; ret`), and inherited unused events are never listed
        # (the owner).  The Heathen Mommy's father "Unknown": the patch's new-village code (file 0x94620, from the
        # original build) calls the pregnancy writer 0x465E00 with the name 0x4B6AA0 ("Unknown", the game's own
        # word, string id 0x4A6), head 2 and body 2; no record stands behind it.  Every stock conception passes the
        # partner's own record (0x467DBE, 0x46E16B, 0x46E19B).
        out.append(f(GENETICS, (
            "The Heathen Mommy's children have the father \"Unknown\" (the owner). He is a name only, not a villager: "
            "in a village made with the patcher's \"Heathen Mommy Puzzle Restoration\", the new-village code it "
            "restores from the original build starts her pregnancy with the game's own word \"Unknown\" as the "
            "father's name, head 2 and body 2 (0x465E00), so her baby's head is half of (her head + 2), -1, 0 or +1 "
            "(or any head on 5 births in 100). Every other conception in New Believers passes the real partner's "
            "name, head and body (0x467DBE)."), gm.RUNNING))   # the owner's fact, read in the patch and the exe
    elif game in (4, 5):
        out.append(f(GENETICS, (
            "One island event makes a woman expecting by the game's default father Joey, who has head 2 and body 2 "
            + {4: "(0x467B00, its conception call 0x467C15)", 5: "(0x471A50)"}[game]
            + ", so such a baby's head is half of (the mother's head + 2), -1, 0 or +1 (or any head on 5 births in "
            "100)."), gm.RUNNING))
    # "Unknown" (the owner: seen for the Heathen Mommy in New Believers and after island events): no game passes it
    # as a father -- its one reference in each exe is the string table (VV2 0x49640C, VV3 0x4ABB38, VV4 0x4C49E0,
    # VV5 0x4D38A8); every conception copies a partner record's head and body onto the mother (VV5 0x467DBE,
    # 0x46E16B, 0x46E19B; VV4 0x460A2E, 0x4650EB, 0x46511B) apart from the default fathers ("?" in VV2, Joey in VV4
    # and VV5).  See docs/known-behaviours-and-non-bugs.md, the default fathers.
    default = {2: "The Gong of Wonder's \"?\" (head 0)", 3: "", 4: "Joey (head 2)", 5: ""}[game]
    if game != 5:      # New Believers' "Unknown" is a father the game passes (its line above)
        out.append(f(GENETICS, (
            "A father shown as \"Unknown\" is not one the game itself names: this game never passes \"Unknown\" as a "
            "father; the patcher shows it where the game kept no father's name. The baby's head was still worked "
            "out by the rule above, from the father's head the game copied onto the mother at the conception: every "
            "conception copies a real partner's head"
            + (f", except {default}, as above." if default else " (this game has no fatherless conception).")
            + " So \"Unknown\" never stands for a head of its own and never changes a baby's head."), gm.RUNNING))
    old = {2: "male_heads_old / female_heads_old", 3: "male_heads_old / female_heads_old",
           4: "male_heads10 / female_heads10", 5: "male_heads10 / female_heads10"}[game]
    out.append(f(GENETICS, (
        f"The game has 30 heads (0 to 29) and 30 bodies (0 to 29) for each sex, one row each of its own pictures. "
        f"Growing older never changes the head value: an elder's head is the same row of its old-age pictures "
        f"({old})."), gm.RUNNING))
    later = {
        2: ("What changes a head later: only the island event \"A Mysterious Vial\" (the green liquid), when the "
            "villager drinks it: the head is rolled again, a man any of 0 to 28, a woman any of 0 to 29 (it can come "
            "out the same), and the body is kept (0x4395DF..0x439707)."),
        3: ("What changes a head later: only the island event \"The Mysterious Vial\" (the obsidian one), when the "
            "villager tastes it: 33 times in 100 their looks change, a new head any of 0 to 29 (0x4175BB, "
            "0x417634); otherwise Clumsy (33 in 100) lowers two skills or Insight (34 in 100) raises two."),
        4: "Nothing in The Tree of Life changes a villager's head after it is made: no island event or other code "
           "writes it, apart from copying a whole villager (twins, loading a save).",
        5: "Nothing in New Believers changes a villager's head after it is made: no island event or other code "
           "writes it, apart from copying a whole villager (twins, loading a save).",
    }[game]
    out.append(f(GENETICS, later, gm.RUNNING))
    return out


def _villagers(village: gm.Village) -> list[gm.Fact]:
    """Each living child's head beside the heads its parents passed at its birth, as the save records them on the
    child's own record (The Lost Children to New Believers).  A villager with no parents recorded is left out."""
    if village.general or village.game == 1:
        return []
    try:
        import vv_last_names as names
        roster = names.living(village.folder, village.game, village.slot)
        fields = names.FIELDS[village.game]
    except Exception:  # noqa: BLE001 -- a villager table that cannot be read gives no per-villager lines
        return []
    data = village.data
    fh, _fb, mh, _mb = fields.looks[:4]

    def text(at: int, cap: int) -> str:
        if not 0 <= at < len(data):
            return ""
        raw = data[at:at + cap]
        return raw.split(b"\0", 1)[0].decode("latin-1", "replace")

    def i32(at: int) -> int | None:
        return struct.unpack_from("<i", data, at)[0] if 0 <= at <= len(data) - 4 else None

    out = []
    near = 0
    for v in roster:
        father, mother = text(v.at + fields.father, fields.parent_cap), text(v.at + fields.mother, fields.parent_cap)
        father_head, mother_head = i32(v.at + fh), i32(v.at + mh)
        if not father or not mother or father_head is None or mother_head is None:
            continue
        same = [who for who, head in (("the mother's", mother_head), ("the father's", father_head)) if head == v.head]
        match = (" -- the same as " + " and ".join(same)) if same else " -- the same as neither"
        average = (father_head + mother_head) // 2
        near += min(29, max(0, average - 1)) <= v.head <= min(29, max(0, average + 1))
        out.append(gm.Fact(GENETICS, (
            f"{v.name}: head {v.head}; mother {mother} passed head {mother_head} and father {father} head "
            f"{father_head} at the birth{match}."), gm.SAVE))
    if out:
        out.insert(0, gm.Fact(GENETICS, (
            f"In this village {near} of the {len(out)} living villagers whose parents the save records have a head "
            "within 1 of their parents' average (the game's rule gives that 95.5% of the time; the others come from the "
            "5-in-100 pick or a later change of looks). Each one's head beside the heads its "
            "parents passed at its birth, as the save records them:"), gm.SAVE))
    return out


def facts(village: gm.Village) -> list[gm.Fact]:
    """The Genetics group for one save (or, with village.general, the game's general rules)."""
    rules = _vv1() if village.game == 1 else _later(village.game)
    return rules + _patch_lines(village) + _villagers(village)
