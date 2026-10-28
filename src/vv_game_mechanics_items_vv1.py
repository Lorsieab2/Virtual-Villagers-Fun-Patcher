"""Game Mechanics, A New Home (VV1): every technology, puzzle, building, item and patcher upgrade, each with what it
costs or how it is earned and exactly what it does (the owner, 2026-10-27: "Elaborate on what every store item and
upgrade and research and everything does!!!").

Each ENTRY is one thing the player can buy, earn, build, give or switch on.  item_facts() gives it as one bullet (its
name and what it is) and sub-bullets (its effects), in the page's Fact format, all in ITEMS_GROUP.  The coordinator wires
this module into src/vv_game_mechanics.py; nothing here reads a save, so the lines are the same on every page.

LABELS (src/vv_game_mechanics.py, TRUSTED): gm.RUNNING is VERIFIED-E (emulated from a live caller, or checked on the
games' own path), gm.CODE is VERIFIED-C (read in the stock exe on a live path, each address cited in the comment above
it), gm.OWNER the owner's word, False UNCONFIRMED.  Patcher lines say what the patcher's own code does (its catalog entry
in data/*.json and its sources under native/), and are gm.CODE on that ground; a line about a patch whose effect was not
read in its code is UNCONFIRMED.

THE STOCK EXE: research\\stock-executables\\Virtual Villagers - A New Home.exe (581,632 bytes).  State offsets below are
the game's (a save's file offset is 4 more).  Tech levels: Spirituality +0xA2BC, Science +0xA2C4, Construction +0xA2CC,
Medicine +0xA2D4, Fertility +0xA2DC, Farming +0xA2E4 (each starts at 1, 0x41C43E..0x41C45C; at most 3); tech points
+0xA2FC.  The tech screen's buy handler is 0x435AF8..0x435D6C: for each technology the price of level 2, then of level
3; too few points shows message 0x25 and buys nothing (0x435D38); level 3 shows "Your villagers have fully mastered this
technology!" (0x435D09).  The drop handler (a villager dropped on a place) is 0x424150, jump table 0x424E50; the job
dispatcher 0x4472C0 (builders 0x4474AA..0x447724); the effect callbacks 0x43A230 (table 0x43B46C).
"""
from __future__ import annotations

from dataclasses import dataclass

import vv_game_mechanics as gm

GAME = 1
ITEMS_GROUP = "Technologies, items and buildings"
KINDS = ("technology", "puzzle", "building", "item", "patcher")
TECH, PUZZLE, BUILDING, ITEM, PATCHER = KINDS


@dataclass(frozen=True)
class Entry:
    """One thing the player can buy, earn, build, give or switch on: `lines` are (text, label); the first is the
    entry's own bullet (shown after its name), the rest its sub-bullets."""
    kind: str
    name: str
    lines: tuple[tuple[str, bool | str], ...]


C, E, O, U = gm.CODE, gm.RUNNING, gm.OWNER, False

# The technologies' level-2 and level-3 prices (0x435AF8..0x435D2E), in the tech screen's button order.
TECH_COSTS = {"Farming": (6_000, 50_000), "Fertility": (11_000, 240_000), "Science": (12_000, 150_000),
              "Medicine": (15_000, 250_000), "Construction": (2_500, 80_000), "Spirituality": (5_000, 80_000)}
# The game's own titles for them (its tech tooltips' English strings).
TECH_TITLES = {"Farming": "Farming Technology", "Fertility": "Fertility Technology", "Science": "Science Technology",
               "Medicine": "Medicine Technology", "Construction": "Construction Technology",
               "Spirituality": "Spirituality"}


def _buy(tech: str, level: int) -> str:
    cost = TECH_COSTS[tech][level - 2]
    return (f"{tech} level {level}: {cost:,} tech points on the Tech screen (from level {level - 1}); the points are taken "
            "at once and the level is never lost.")


# Level 1 of each technology, its own entry like The Secret City's to New Believers' (the owner, 2026-10-27: "Same
# between the virtual villagers games"): what a new village has before anything is bought.  Every line restates, for
# level 1, a reading cited under that technology's level 2 and 3 below.
LEVEL_ONE = "a new village's level, no price (every technology starts at 1, 0x41C43E..0x41C45C)."


# ---------------------------------------------------------------------------------------------------------------
# Technologies.  Every reading of a level below is cited; the Chances, Births and gender, Death and graves and Food
# sources groups give the full odds where they are the same rule.
# ---------------------------------------------------------------------------------------------------------------
TECHNOLOGIES = (
    Entry(TECH, "Every technology", (
        ("A New Home has six: Farming, Fertility, Science, Medicine, Construction and Spirituality. A new village "
         "starts each at level 1 and with 99 tech points; 3 is the top level. Tech points come only from research "
         "(Tech points and effects) and from island events, their encounters and crates (Island events); the levels "
         "change nothing else than the effects listed under each one.", C),
        # 0x41C43E..0x41C45C (levels 1), 0x41C410 (99 points), 0x41D120 (the only adder of tech points besides events).
        ("Once all six are at level 3 (the six levels add up to 18), researchers stop researching on their own; one "
         "you drop on the research spot still researches.", C),
        # 0x447481: call 0x41CEA0 (the sum), cmp 0x12, jge -> no research; the work-spot route 0x447DA7..0x447DC7 has no
        # such test.
    )),
    Entry(TECH, "Farming level 1", (
        (LEVEL_ONE, C),
        # 0x4472EB (the farmers' switch on Farming): level 1 picks the berry bush only.
        ("Farmers pick only the berry bush (Food sources); the crop field never refills (0x42EC16) and a villager "
         "dropped on the field does not plant or harvest (0x424BCC).", C),
        # 0x4241D6: Farming > 2 for fishing; otherwise "Going swimming".
        ("A villager dropped in the sea only goes swimming, beach cleaned or not.", C),
    )),
    Entry(TECH, "Farming level 2", (
        (_buy("Farming", 2), C),
        # 0x42EC16 (regrowth +800 at Farming >= 2), 0x42F2C5 (cap 800).
        ("The crop field starts to refill: at every regrowth (every 2 hours, 4 hours or 6 hours 40 minutes of "
         "real-life play on Fast, Normal or Slow) it is filled to 800. Below level 2 it never refills.", C),
        # 0x435B36..0x435B79: buying level 2 sets the next regrowth to now + speed x 2,400 / 4 seconds (a paused speed
        # counts as Normal, 6).
        ("Buying it moves the next regrowth to 30 minutes, 1 hour or 1 hour 40 minutes of real-life time from the "
         "purchase (Fast, Normal, Slow; bought while paused, 1 hour).", C),
        # 0x4472EB (switch on Farming): level 2 0x4473E3.
        ("Farmers then pick the berry bush or the crops half the time each, and always the crops while the bush "
         "holds under 100 (Food sources).", C),
        # 0x424BCC (drop area 34, the field): Farming >= 2 -> "Planting crops / Harvesting crops" 0x4439F0 (work spot 5).
        ("A villager dropped on the field plants or harvests the crops (7 food a harvest); below level 2 the drop "
         "does not start that job.", C),
        # 0x424E0B (the well, drop areas 10 and 37, once the well is uncovered): one of three picks is "Watering
        # crops" 0x445020 only at Farming >= 2.
        ("Once The Well is uncovered, a villager dropped on the well can go \"Watering crops\" (one pick in three), "
         "which only trains Farming.", C),
        # 0x416759: the village picture of the field is drawn at Farming >= 2.
        ("The village shows the planted field from level 2.", C),
    )),
    Entry(TECH, "Farming level 3", (
        (_buy("Farming", 3), C),
        # 0x44730B: level 3 with the beach clean ([+0x9FB8]).
        ("With The Beach cleaned, farmers fish half the time (9 food a catch; 55 for a crab 21% of the time at "
         "Farming skill 90 or more); the rest goes to berries, crops or nothing (Food sources).", C),
        # 0x4241D6 (drop area 15, the sea, beach clean): Farming > 2 -> Fishing 0x43F450 (work spot 6); otherwise
        # message 0x27 and "Going swimming".
        ("A villager dropped in the sea fishes (beach cleaned); below level 3 it only goes swimming.", C),
        # 0x4243C6 (drop area 15, the lagoon, not pregnant): Magic Fish not found, Farming 3, Farming skill >= 90
        # -> "Hunting a strange fish!" 0x444C80.
        ("It is needed for The Magic Fish of Fertility (a villager with Farming skill 90 or more dropped in the "
         "lagoon).", C),
    )),
    Entry(TECH, "Fertility level 1", (
        (LEVEL_ONE, C),
        # 0x43DC6B, 0x446F6B, 0x44716C: rand(300) <= Parenting - 50 + 50 x Fertility.
        ("Every conception roll: a baby when a roll of 0 to 299 is at most the Parenting of the villager who started "
         "the embrace, so Parenting + 1 in 300 (Births and gender).", C),
        # 0x43BC28: twins only at Fertility 3 or with The Magic Fish; triplets need both.
        ("No twins unless The Magic Fish of Fertility has been found (then 7% of conceptions); never triplets.", C),
    )),
    Entry(TECH, "Fertility level 2", (
        (_buy("Fertility", 2), C),
        # 0x43DC6B (live embrace) and 0x446F6B, 0x44716C (catch-up): rand(300) <= Parenting - 50 + 50 x Fertility.
        ("Every conception roll gets 50 more in 300: a baby when a roll of 0 to 299 is at most the Parenting of the "
         "villager who started the embrace + 50 x Fertility - 50, so Parenting + 51 in 300 at level 2 (Births and "
         "gender).", C),
    )),
    Entry(TECH, "Fertility level 3", (
        (_buy("Fertility", 3), C),
        ("Every conception roll gets 50 more in 300 again: Parenting + 101 in 300 (at most 67%).", C),
        # 0x43BC28: twins only at Fertility 3 or with The Magic Fish ([+0xA090]); 7%; triplets need both, 25%.
        ("Twins become possible (7% of conceptions) without The Magic Fish of Fertility; with it as well, a quarter "
         "of those are triplets (Births and gender).", C),
        # 0x42426E: the Golden Child needs Fertility 3.
        ("It is needed for The Golden Child (a pregnant villager dropped in the lagoon after The Idol).", C),
        # 0x44638D: the devotion pick "Sees something unusual..." 0x441750 needs The Idol and Fertility 3.
        ("With The Idol done it adds \"Sees something unusual...\" to the devotion picks (Spirituality).", C),
    )),
    Entry(TECH, "Science level 1", (
        (LEVEL_ONE, C),
        # 0x43B2E9: Research / 7 at Science 1.
        ("Each successful research session gives the researcher's Research skill ÷ 7 tech points, rounded down (a "
         "researcher of 50 gets 7, one below 7 gets nothing).", C),
        ("Digging for The Treasure cannot start (it needs Science level 3).", C),
    )),
    Entry(TECH, "Science level 2", (
        (_buy("Science", 2), C),
        # 0x43B2E9: Research / 7, / 5, / 3 at Science 1, 2, 3.
        ("Each successful research session gives the researcher's Research skill ÷ 5 tech points instead of ÷ 7, "
         "rounded down (a researcher of 50 gets 10 instead of 7).", C),
        # 0x416705: a picture at (500, 1000) is drawn from Science 2, another at (552, 1000) from Science 3.
        ("The village picture gains one more drawn piece from level 2 (and another at level 3); it changes nothing "
         "in play.", C),
    )),
    Entry(TECH, "Science level 3", (
        (_buy("Science", 3), C),
        ("Each successful research session gives Research ÷ 3 tech points, rounded down (a researcher of 90 gets 30; "
         "18 at level 2, 12 at level 1).", C),
        # 0x424682: digging (drop area 19) needs Science > 2 and Construction > 2, and Building 90 or digging started.
        ("It is needed, with Construction level 3, to start digging for The Treasure.", C),
    )),
    Entry(TECH, "Medicine level 1", (
        (LEVEL_ONE, C),
        # 0x42E5D4 (rand(2400) <= 3 at 1), 0x42E624 / 0x42EDFC (elderly from 840 + 160 x Medicine age units), 0x42EE8A
        # (old age from 940 + 160 x Medicine).
        ("A villager of 14 or more falls sick 4 in 2,400 each age unit (Chances); \"elderly\" from 50 years; the "
         "old-age death rolls start at 55 and death is certain from 65 (Death and graves).", C),
        # 0x418969: the antibiotics stranger is offered only below Medicine 3.
        ("The island encounter whose stranger gives antibiotics (+1 Medicine level) can come (Island events).", C),
    )),
    Entry(TECH, "Medicine level 2", (
        (_buy("Medicine", 2), C),
        # 0x42E5D4 (sickness: rand(2400) <= 3 at 1, rand(4800) <= 3 at 2, rand(10000) <= 2 at 3), 0x42E624 / 0x42EDFC
        # (elderly from 840 + 160 x Medicine age units), 0x42EE8A (old age from 940 + 160 x Medicine), 0x43CD49
        # (the elderly walk).
        ("A villager of 14 or more falls sick half as often: 4 in 4,800 each age unit instead of 4 in 2,400 "
         "(Chances); \"elderly\" (more "
         "sickness, slower healing, a slow walk) starts at 58 years instead of 50; the old-age death rolls start at "
         "63 instead of 55, and death is certain from 73 instead of 65 (Death and graves).", C),
        # 0x418969: the antibiotics stranger (encounter) is offered only below Medicine 3; 0x419815 +1 Medicine.
        ("The island encounter whose stranger gives antibiotics (+1 Medicine level) still comes; see Island events.", C),
    )),
    Entry(TECH, "Medicine level 3", (
        (_buy("Medicine", 3), C),
        ("Sickness drops to 3 in 10,000 for each age unit (from 4 in 4,800 at level 2); elderly from 66 years; "
         "old-age rolls from 71, certain death from 81.", C),
        ("The antibiotics encounter no longer comes once Medicine is at level 3.", C),
    )),
    Entry(TECH, "Construction level 1", (
        (LEVEL_ONE, C),
        # 0x4475D7 (blockage and field need >= 2), 0x447664 (ruins, chiseling, digging and hut repair need 3).
        ("Builders do not clear the blockage, water the garden field, restore the ruins, chisel the idol, dig or "
         "examine huts on their own.", C),
        # 0x4244AC: the blockage drop needs Construction >= 2.
        ("A villager dropped on the blockage is left confused.", C),
    )),
    Entry(TECH, "Construction level 2", (
        (_buy("Construction", 2), C),
        # 0x4475D7: builders clear the blockage and water the garden field only at Construction >= 2.
        ("Builders carry on clearing the blockage (The Lagoon) and watering the field (The Garden) on their own; "
         "below level 2 they do neither.", C),
        # 0x4244AC (drop area 16): the blockage drop "Clearing blockage" 0x43FDA0 needs Construction >= 2.
        ("A villager dropped on the blockage clears it; below level 2 the drop leaves it confused.", C),
    )),
    Entry(TECH, "Construction level 3", (
        (_buy("Construction", 3), C),
        # 0x447664: below 3 builders give up after the blockage and the field.
        ("Builders carry on the ruins (The Temple), the chiseling (The Idol) and the digging (The Treasure) on "
         "their own, and examine and fix huts (Hut repair); below level 3 they never do.", C),
        # 0x424C73 (ruins drop needs Spirituality 2 and Construction 3); 0x424695 (digging drop needs Construction 3
        # and Science 3).
        ("A villager dropped on the ruins restores them (with Spirituality level 2 or more); one dropped on the "
         "digging site digs (with Science level 3, and Building skill 90 or the digging already started).", C),
    )),
    Entry(TECH, "Spirituality level 1", (
        (LEVEL_ONE, C),
        # 0x424543 (burial needs >= 2), 0x424C73 (ruins need 2), 0x42499C / 0x424A03 (chiseling needs 3).
        ("Nobody can bury the dead, so The Cemetery cannot be founded; the ruins cannot be restored and the idol "
         "cannot be chiseled.", C),
        # 0x41CED0: 3 x Spirituality + 3 for each of the four.
        ("Devotion's roll is 4% to 16%, by how many of The Temple, The Cemetery, The Idol and The Golden Child are "
         "done (Spirituality level 2 gives the rule).", C),
        # 0x418955: the whale encounter is offered while Spirituality < 3.
        ("The beached-whale encounter (\"Your tribe has gained spirituality\", +1 level) can come.", C),
    )),
    Entry(TECH, "Spirituality level 2", (
        (_buy("Spirituality", 2), C),
        # 0x424543 (drop area 17, the burial ground): with no cemetery yet, Spirituality >= 2 and a body (0x43A200)
        # -> "Burying the dead" 0x443890, which sets the cemetery flag +0xA000 (The Cemetery).
        ("A villager dropped on the burial ground while a body lies unburied buries it, and that founds The "
         "Cemetery; below level 2 nobody can.", C),
        ("A villager dropped on the ruins restores them (with Construction level 3).", C),
        # 0x41CED0 (3 x Spirituality + 3 for each of The Temple, The Cemetery, The Idol, The Golden Child), called
        # only at 0x4483F3: at 2,000 food or more, when the leisure pick 0x4480F0 starts nothing, rand(100) <= that
        # value sends the adult to the devotion pick 0x4462E0.
        ("Devotion: at 2,000 food or more, when an adult's leisure pick starts nothing, a roll of 0 to 99 at most "
         "3 x Spirituality + 3 for each of The Temple, The Cemetery, The Idol and The Golden Child done sends it to "
         "devotion: 7% to 19% at level 2 (4% to 16% at level 1, 10% to 22% at level 3), by how many of the four are "
         "done.", C),
        # 0x4462E0: rand(100) > 50 (49%) then rand(5): Honoring the Dead (Cemetery), Honoring the Idol (Idol),
        # Honoring the temple (Temple), "Sees something unusual..." (Idol and Fertility 3), Rain dancing (not for one
        # who dislikes dancing).
        ("A devotion pick does something 49% of the time: one of five, each 1 in 5 — Honoring the Dead (with The "
         "Cemetery), Honoring the Idol (with The Idol), Honoring the temple (with The Temple), \"Sees something "
         "unusual...\" (The Idol and Fertility level 3) or Rain dancing (not for one who dislikes dancing); a pick "
         "whose condition fails does nothing.", C),
    )),
    Entry(TECH, "Spirituality level 3", (
        (_buy("Spirituality", 3), C),
        # 0x42499C / 0x424A03 (drop areas 5 and 21): with The Temple done and Spirituality 3 -> chiseling 0x442A60.
        ("A villager dropped on the idol stone chisels it (The Idol) once The Temple is done; below level 3 the "
         "drop does nothing.", C),
        ("Devotion's roll becomes 10% to 22%, by how many of The Temple, The Cemetery, The Idol and The Golden Child "
         "are done.", C),
        # 0x418955: the whale encounter is offered only while Spirituality < 3; 0x4193EE: +1 Spirituality.
        ("The beached-whale encounter (\"Your tribe has gained spirituality\", +1 level) no longer comes.", C),
    )),
)

# ---------------------------------------------------------------------------------------------------------------
# Puzzles: how each is solved and what it gives.  The solved flags and hours are under Puzzles (the save's state).
# Completion callbacks (table 0x43B46C): 1 Cave 0x43ABC4, 2 Lagoon 0x43B0D6 (350), 3 Beach 0x43AAA6 (+2 a trip, 150),
# 4 Garden 0x43B1E6 (200), 5 Treasure 0x43AC5B, 7 Idol 0x43A578 (1,350), 8 Temple 0x43B357 (1,000), 9-11 huts
# 0x43A757/0x43A87E/0x43A9A5 (250/400/600), 22 School 0x43A6AD, 23 Well 0x43AE12, 24-27 the four plants (25 and 27
# set Herb Mastery when all four are studied, 0x43A3BD/0x43A4CF), 29 Butterflies 0x43A4F7, 30 Magic Fish 0x43A2D6.
# No puzzle's completion adds food or tech points: the only callers of the food and tech adders 0x41D140/0x41D120
# are work, the Golden Child, island events and crates.
# ---------------------------------------------------------------------------------------------------------------
PUZZLE_ENTRIES = (
    Entry(PUZZLE, "The Well", (
        # 0x424D18 (drop areas 10 and 37): well not uncovered, Building skill > 0 -> "Uncovering the well" 0x444EC0,
        # whose queue ends in callback 23 (0x43AE12, sets +0xA058) with no skill roll; Building 0 -> message 0x37
        # ("Yuck! The well is still dirty...") and a shake of the head.
        ("Solved by dropping a villager with any Building skill (1 or more) on the dirty well: it walks there and "
         "\"Uncovering the well\" always succeeds once the walk is done (no skill roll). With Building 0 the game "
         "says the well is still dirty and nothing happens.", C),
        # 0x424DC3..0x424E43: rand(3): 0 drinking well water 0x444B40; 1 Watering crops 0x445020 at Farming >= 2,
        # otherwise rolled again; 2 "Trying to water strange patch" 0x4452A0 while The Garden is neither done
        # (+0x9FC0) nor started (+0x9FBC), otherwise drinking.
        ("Reward: the well can be used. A villager dropped on it rolls 0 to 2: 0 drinks well water; 1 waters the "
         "crops (at Farming level 2 or more; below that the roll is made again); 2 tries to water the strange patch "
         "while The Garden is not yet started, and otherwise drinks.", C),
    )),
    Entry(PUZZLE, "The Hut", (
        # Callback 9 (0x43A757): 250 trips sets +0x9FE8; conception gate 0x43A1A0 (15+ need it).
        ("Solved when the first population hut is built: 250 successful building trips.", C),
        ("Reward: babies can be conceived at 15 people or more (babies on the way counted); without it conception "
         "stops at 15. See Population huts.", C),
    )),
    Entry(PUZZLE, "The Beach", (
        # Callback 3 (0x43AAA6): +2 a trip, solved at 150 (+0x9FB8); drop area 36 starts "Cleaning up the beach"
        # 0x444690 at any tech level.
        ("Solved by cleaning up the beach: 75 successful trips (each adds 2, done at 150). Drop a villager on the "
         "beach to start; builders then carry it on (Construction is not needed).", C),
        ("Reward: fishing at Farming level 3 (Food sources), and dropping a villager in the sea then fishes.", C),
    )),
    Entry(PUZZLE, "The School", (
        # 0x424418 (drop area 7): not founded, Research skill >= 90 -> "Founding a school" 0x440E50, callback 22
        # (0x43A6AD, +0xA050) with no skill roll; below 90 message 0x41 and "Confused".
        ("Solved by dropping a villager with Research skill 90 or more on the school site: \"Founding a school\" "
         "always succeeds once the walk is done. Below 90 the villager is only confused.", C),
        # docs/vv1-school-lessons-research.md: the drum lesson 0x444AA0 (sole caller 0x425505) queues no reward.
        ("Reward: children can be sent to school with the drum (\"Going to school\"). In the original game a lesson "
         "teaches nothing: it ends with no skill gain.", C),
        ("With the patcher (School Lessons Grant Skill, on by default): each child who finishes a lesson gains 7, 8 "
         "or 9 points (each 1 in 3) in one of its five skills (each 1 in 5), up to 100. With School Lessons Stop at "
         "50 as well (on by default): only a skill below 50 is chosen, the gain stops at 50, and a child with every "
         "skill at 50 gains nothing.", C),
    )),
    Entry(PUZZLE, "The Lagoon", (
        # Callback 2 (0x43B0D6): 350 sets +0x9FB0.  Drop area 16 with Construction >= 2 starts "Clearing blockage".
        ("Solved by clearing the blockage: 350 successful building trips. Needs Construction level 2 (for the drop "
         "and for builders to carry it on).", C),
        # 0x4241AC..0x4243E7 (drop in the lagoon), 0x423D47 (a fourth sparkle group).
        ("Reward: the lagoon opens: dropped in it a villager enjoys the lagoon or swims, a pregnant one there can "
         "bring The Golden Child, and a master fisher can find The Magic Fish of Fertility; the garden field's "
         "watering (The Garden) opens; one more group of sparkles (pictures only).", C),
    )),
    Entry(PUZZLE, "The Magic Fish of Fertility", (
        # 0x4243C6: lagoon drop, not pregnant, fish not found, Farming 3, Farming skill >= 90 -> 0x444C80; callback 30
        # (0x43A2D6, +0xA090), message 0x13F.
        ("Solved by dropping a villager with Farming skill 90 or more into the lagoon at Farming level 3: \"Hunting "
         "a strange fish!\" finds it.", C),
        ("Reward: twins become possible (7% of conceptions) without Fertility level 3; with Fertility level 3 as "
         "well, a quarter of twin pregnancies are triplets (Births and gender).", C),
    )),
    Entry(PUZZLE, "The Cemetery", (
        ("Solved by dropping a villager on the burial ground at Spirituality level 2 or more while a body lies "
         "unburied: it buries the body (\"Burying the dead\") and the cemetery is founded at once.", C),
        # 0x448307: with +0xA000 set, any dead body sends the next idle adult to bury it.
        ("Reward: from then any unburied body sends the next idle adult to bury it before it looks for work (Death "
         "and graves); dropped on the cemetery a villager goes \"Honoring the Dead\"; it adds 3 to the devotion "
         "roll (Spirituality).", C),
    )),
    Entry(PUZZLE, "Herb Mastery", (
        # Callbacks 24-27 set the four plants (+0xA060 rose, +0xA068 cactus, +0xA070 lily, +0xA078 strange plant);
        # 25 and 27 set +0xA080 when all four are set.  Drop routes 0x424A6A (cactus), 0x424A99 (lily), 0x424ABC
        # (rose), 0x424ADF (strange plant), each refused by a villager who dislikes herbs (0x4372E0).
        ("Solved by studying all four plants: the medical cactus, the strange lily, the rare rose and the strange "
         "plant, each by dropping a villager on it (one who dislikes herbs refuses). The first study of the cactus "
         "always succeeds; the others are Healing skill rolls.", C),
        # 0x43CF5B: every cure then adds 10 + rand(20) health, up to 100.
        ("Reward: every cure also restores 10 to 29 health (each amount 1 in 20), up to 100.", C),
        ("With the patcher (Easier Healing Mastery, on by default): healers with no patient study the medical cactus "
         "on their own, including during catch-up (a villager not checked on Healing only 14% of the time).", C),
        ("With the patcher (Healers Study Plants Regardless of Food, on by default): a villager studying the cactus "
         "carries on at 400 food or more as below it, 50% of the time each choice (14% for one not checked on "
         "Healing).", C),
    )),
    Entry(PUZZLE, "The Garden", (
        # Callback 4 (0x43B1E6): 200 sets +0x9FC0.  0x43FC20 queues no skill roll (hidden gates #36).
        ("Solved by watering the field after The Lagoon: 200 waterings. Drop a villager on the field to start; "
         "builders carry it on at Construction level 2. Watering never fails (no skill roll).", C),
        ("Reward: villagers enjoy the garden (leisure); dropping The Golden Child on it brings The Butterflies.", C),
        ("With the patcher (Watering the Field Trains Building, on by default): each watering that advances the "
         "garden also makes one Building practice roll; a villager not checked on Building is sent to water only "
         "14% of the times the game would.", C),
    )),
    Entry(PUZZLE, "The Magic Plant of Life", (
        # The butterflies' update (0x412933..0x412A15, 0x413174..0x413287): with The Butterflies done (+0xA088) and the
        # plant not (+0xA098), a butterfly follows the villager of family 199 (state 4, 0x413179..0x4131B8); left of
        # x 634 and above y 215 it settles (state 5, 0x4131C0..0x4131DA); each move there adds 1 to +0xA094 and flies
        # to a point 573-632, 142-211 (0x41320B..0x413248); at 300 +0xA098 is set and the hour stamped (0x41327B).
        # The update's own caller was not traced.
        ("Solved by the butterflies (after The Butterflies): they follow The Golden Child, and once he is by the "
         "fruitless plant they settle on it; every move a butterfly makes there counts 1 (a count the save keeps), "
         "and at 300 the plant is solved.", U),
        # 0x424C13 (drop area 27): with +0xA098 "Enjoying magic fruit" 0x443150, otherwise "Studying fruitless
        # plant" 0x443030.
        ("Reward: dropped on the plant a villager eats magic fruit (\"Enjoying magic fruit\"); in the original game "
         "that changes nothing else.", C),
        ("With the patcher (Magic Fruit of Life Alters Mortality, on by default): the old-age death rolls start 7 "
         "years later (62, 70 or 78 at Medicine 1, 2, 3), during catch-up too; and a villager who finishes "
         "\"Enjoying magic fruit\" is cured and set to 100 health, as often as it eats.", C),
    )),
    Entry(PUZZLE, "The Temple", (
        # Callback 8 (0x43B357): 1,000 sets +0x9FE0; Building 90+ adds 2 a trip (hidden gates #35).
        ("Solved by restoring the ruins: 1,000 progress (each successful trip 1, or 2 at Building 90 or more). "
         "Needs Spirituality level 2 and Construction level 3.", C),
        ("Reward: villagers honour the temple; the idol stone can be chiseled (The Idol, Spirituality level 3); it "
         "adds 3 to the devotion roll.", C),
    )),
    Entry(PUZZLE, "The Idol", (
        # Callback 7 (0x43A578): 1,350 sets +0x9FD8.
        ("Solved by chiseling the idol: 1,350 progress (2 a trip at Building 90 or more). Needs The Temple and "
         "Spirituality level 3.", C),
        ("Reward: it is needed for The Golden Child; villagers honour the idol; it adds 3 to the devotion roll; the "
         "sparkles near the idol stop (pictures only).", C),
    )),
    Entry(PUZZLE, "The Butterflies", (
        ("Solved only by dropping The Golden Child on the garden once The Garden is done (\"Calling "
         "Butterflies!\"). See Golden Child.", E),
        ("Reward: the butterflies over the garden and the puzzle itself; no value of the village changes.", C),
    )),
    Entry(PUZZLE, "The Treasure", (
        # Callback 5 (0x43AC5B): sets +0x9FC8 at 800 (hidden gates #35); 0x424665: admiring once found.
        ("Solved by digging: 800 successful trips. Needs Science level 3, Construction level 3, and to start it a "
         "villager with Building skill 90 or more dropped on the site.", C),
        ("Reward: villagers admire the treasure; two more groups of sparkles (pictures only). It gives no food or "
         "tech points.", C),
    )),
    Entry(PUZZLE, "The Cave", (
        ("Solved only by The Golden Child: 36 real-life hours (real time, at any speed, paused or closed) after his "
         "birth he may open it, or earlier by one of "
         "his own acts. See Golden Child.", E),
        ("Reward: the boulder is gone and dropping a villager on the cave takes the game to the cave's own screen "
         "(Golden Child).", E),
    )),
    Entry(PUZZLE, "The Golden Child", (
        ("Solved by dropping a pregnant villager into the lagoon after The Idol, with Fertility level 3. See Golden "
         "Child for everything he does.", E),
        ("Reward: the Golden Child (one a village), The Cave and The Butterflies through him; it adds 3 to the "
         "devotion roll.", C),
    )),
)

# ---------------------------------------------------------------------------------------------------------------
# Buildings, and repairs.
# ---------------------------------------------------------------------------------------------------------------
BUILDINGS = (
    Entry(BUILDING, "Population huts", (
        # Callbacks 9/10/11: 250 / 400 / 600 trips (+0x9FE4/+0x9FEC/+0x9FF4, flags +0x9FE8/+0x9FF0/+0x9FF8); a 2% injury
        # roll of 0-14 health on each.  The conception gate 0x43A1A0: 15 / 25 / 50 people need hut 1 / 2 / 3; 90 stops
        # conception.  Builders: hut 1 at any population, hut 2 only above 22, hut 3 above 45 (0x44754A, 0x44757C).
        ("Three huts: the first needs 250 successful building trips, the second 400, the third 600. Each trip is a "
         "Building skill roll; 2% of trips injure the builder (0 to 14 health).", C),
        ("They let the village grow: 15 people or more need the first hut, 25 the second and 50 the third before "
         "any baby is conceived (babies on the way counted); at 90 conception stops.", C),
        ("Builders work on the first hut at any population, on the second only above 22 people and on the third "
         "only above 45, and stop again if the village falls back to that number; a villager you drop on a hut "
         "builds it at any population.", C),
        ("With the patcher (Builders Fix Huts When Idle, on by default; Builder Action Fixes, also on by default, "
         "makes the same change): at 22 (or 45) people or fewer builders work on the second (or third) hut only "
         "once you have dropped a villager on it, and from then they finish it at any population.", C),
    )),
    Entry(BUILDING, "Hut repair (Examining hut, Fixing hut)", (
        # 0x447724 (Construction 3 only): rand(3) hut, only a built one; 0x4468CE: 70% fixes; 0x4423E0 ends in a
        # Building skill roll with no callback.
        ("At Construction level 3 a builder with nothing else open examines a standing hut, and fixes it 70% of the "
         "time. Huts never wear out: fixing is only a Building skill roll (practice) and changes no hut.", C),
        ("With the patcher (Builders Fix Huts When Idle, on by default): idle builders fix standing huts at any "
         "Construction level while no building project is open; building always comes first.", C),
    )),
    Entry(BUILDING, "The beach clean-up", (
        ("75 successful trips (The Beach). A villager who dislikes drift wood refuses 85% of the time.", C),
    )),
    Entry(BUILDING, "The blockage", (
        ("350 successful trips (The Lagoon), from Construction level 2. A villager who dislikes rocks refuses 75% of "
         "the time.", C),
    )),
    Entry(BUILDING, "The garden field", (
        ("200 waterings after The Lagoon (The Garden); watering never fails.", C),
    )),
    Entry(BUILDING, "The temple ruins", (
        ("1,000 progress, 1 a trip or 2 at Building 90 or more (The Temple); Spirituality level 2 and Construction "
         "level 3.", C),
    )),
    Entry(BUILDING, "The idol", (
        ("1,350 progress, 1 a trip or 2 at Building 90 or more (The Idol); The Temple and Spirituality level 3.", C),
    )),
    Entry(BUILDING, "The treasure dig", (
        ("800 successful trips (The Treasure); Science and Construction level 3.", C),
    )),
    Entry(BUILDING, "The well", (
        ("One uncovering by a villager with Building 1 or more (The Well).", C),
    )),
    Entry(BUILDING, "The school", (
        ("Founded by one villager with Research 90 or more (The School).", C),
    )),
    Entry(BUILDING, "The cemetery", (
        ("Founded by the first burial at Spirituality level 2 (The Cemetery).", C),
    )),
)

# ---------------------------------------------------------------------------------------------------------------
# Items, and what the player can give.
# ---------------------------------------------------------------------------------------------------------------
ITEMS = (
    Entry(ITEM, "Mushrooms", (
        ("Brown mushroom: 8 food; red (rare) mushroom: 45 food, 1 in 20 of them. One appears about every 2 real-life "
         "minutes while none is out and stays 1 real-life minute (real time, at every speed, even while paused); it "
         "is picked only when you drop a villager on it. "
         "See Mushrooms.", E),
        ("With the patcher (Super-Secret Golden Mushroom, off by default): 1 in 1,000,000 of them is a Golden "
         "Mushroom worth 100 food (Mushrooms).", E),
    )),
    Entry(ITEM, "Collectibles", (
        ("A New Home has none.", E),
    )),
    Entry(ITEM, "The food store", (
        ("Dropped on it, a villager goes \"Eating\": 1 food, and below 100 health +1 health 50.05% of the time (Food "
         "earned).", C),
    )),
    Entry(ITEM, "Research", (
        ("The tech points that buy every technology: Research skill ÷ 7, ÷ 5 or ÷ 3 at Science level 1, 2, 3 for "
         "each successful session (Tech points and effects).", E),
        ("With the patcher (Continue Research at Max Technologies, on by default): researchers keep researching "
         "once all six technologies are at level 3 (one not checked on Research only 14% of the times the game "
         "gives it research).", C),
    )),
    Entry(ITEM, "Clothing (F6)", (
        # docs/vv1-f6-clothing-research.md: the key translator 0x403970 still makes F6 event 1023, but the gameplay
        # screen's key table (0x41FDF0, events 1000-1026) sends 1023 to the unhandled return.
        ("In the original game F6 does nothing: the game still reads the key, but its gameplay screen has no branch "
         "for it.", C),
        ("With the patcher (Reenable F6 Clothing Change Cheat, on by default): F6 costs 5,000 tech points and moves "
         "the selected villager to its next outfit (19 wraps to 0); with fewer points nothing happens.", C),
    )),
)


# ---------------------------------------------------------------------------------------------------------------
# The patcher's Origins and Story / Cheat upgrades.  Prices: the Origins price table 0x485FC0 (Tech rows 0-5 50,000 /
# 30,000 / 75,000 / 500,000 / 500,000 / 30,000; Details rows 0-4 50,000 / 100,000 / 40,000 / 50,000 / 5,000) and the
# 1,000,000 and 450,000 immediates (data/vv1_story_cheat_upgrades_feature.json, runtime_detours); the rows'
# names: native/vv1_origins_icons/vv1_origins_icons.c (vv1_tech_row_name, vv1_detail_row_name).
# ---------------------------------------------------------------------------------------------------------------
def _origins(row: str, price: int, where: str, effect: str) -> str:
    return (f"With the patcher (Enable Origins Tech, Details, and Village-Wide Upgrades, on by default): \"{row}\" on "
            f"the {where}, {price:,} tech points (0 with Story / Cheat Upgrades and its cost row unticked): {effect}")


ORIGINS = (
    Entry(PATCHER, "Origins: Time Warp", (
        (_origins("Time Warp", 50_000, "Tech screen's Upgrades", "moves the village on 12 game years on Fast, 6 on "
                  "Normal and 3 on Slow (12, 12 and 10 hours of real-life time), the time replayed by the game's own "
                  "catch-up; refused while paused."), gm.CLAMP),
    )),
    Entry(PATCHER, "Origins: Island Event", (
        (_origins("Island Event", 30_000, "Tech screen's Upgrades", "queues one of the game's own island events, "
                  "chosen by the game as usual; one at a time, and the game's own island event timer is not "
                  "changed."), C),
    )),
    Entry(PATCHER, "Origins: Barrel of Babies", (
        (_origins("Barrel of Babies", 75_000, "Tech screen's Upgrades", "the game's own Barrel O` Babies event at "
                  "strength 10: three toddlers; only while the village has room for three (an unburied body still "
                  "takes a place)."), C),
    )),
    Entry(PATCHER, "Origins: Tech Point Doubler and Food Point Doubler", (
        (_origins("Tech Point Doubler / Food Point Doubler", 500_000, "Tech screen's Upgrades", "each owned doubler "
                  "doubles the tech points research gives, or the food farmers bring in; island events, crates, "
                  "puzzle and story rewards and the Golden Child's gifts are not doubled. Owned, its row reads "
                  "Remove: removing it is free and refunds nothing."), C),
    )),
    Entry(PATCHER, "Origins: Full Heal / Cure All", (
        (_origins("Full Heal / Cure All", 30_000, "Tech screen's Upgrades", "cures every sick villager and sets every "
                  "living villager to full health (100)."), U),
    )),
    Entry(PATCHER, "Origins: village-wide rows", (
        (_origins("Grant Running to All Villagers / Grant Full Mastery to All Villagers / All Villagers are Exactly "
                  "18", 1_000_000, "Tech screen's Upgrades", "each once: running added as a like to every villager "
                  "with a free like slot (a running dislike removed); every villager's five skills set to 100; every "
                  "villager's age set to 18 years (360 age units)."), C),
        (_origins("Equal Division of Labor (Includes Parenting) / (No Parenting)", 1_000_000, "Tech screen's "
                  "Upgrades", "splits the village evenly across the jobs, men and women balanced in each, each "
                  "villager to the job of its most-progressed skill while that job has room; the Golden Child is "
                  "skipped."), C),
        (_origins("Clear All Skill Preferences", 500_000, "Tech screen's Upgrades", "unticks every villager's job "
                  "checkmark; no skill changes."), C),
        (_origins("Check Highest Skill (Includes Parenting) / (No Parenting)", 1_000_000, "Tech screen's Upgrades",
                  "ticks each villager's most-progressed skill (ties to the first of Farming, Building, Research, "
                  "Healing, Parenting); a villager with no progress keeps its checkmark."), C),
        (_origins("Change Appearance for All", 450_000, "Tech screen's Upgrades", "sets the head, body or Heathen "
                  "mask of every villager at once."), C),
    )),
    Entry(PATCHER, "Origins: Villager Details rows", (
        (_origins("Grant Youth", 50_000, "Villager Details screen", "makes the villager shown 35 years younger (700 "
                  "age units), never under 5 years."), U),
        (_origins("Grant Full Mastery", 100_000, "Villager Details screen", "sets the villager's five skills to 100; its "
                  "job checkmark is kept, or Farming is ticked when it has none."), C),
        (_origins("Grant Running", 40_000, "Villager Details screen", "adds running to the villager's likes (and "
                  "removes it from its dislikes); refused, free, when all its like slots are full."), C),
        (_origins("Set Age to 18", 50_000, "Villager Details screen", "sets the villager's age to 18 years (360 age "
                  "units), moving a pregnancy's timing with it."), C),
        (_origins("Change Appearance", 5_000, "Villager Details screen", "picks the villager's head, body or Heathen "
                  "mask."), C),
    )),
    Entry(PATCHER, "Story / Cheat Upgrades", (
        ("With the patcher (Story / Cheat Upgrades, off by default; needs the Origins upgrades): every Origins "
         "upgrade costs 0 tech points unless Story / Cheat Upgrades cost Tech Points (ticked with it) is also on.", C),
        ("Pick Island Event (0, or 30,000 tech points): choose which of 40 island events comes next and, where the "
         "event rolls for it, how it turns out (its result, every amount, who it hits, its strength 1 to 10); the "
         "game's own event code runs it. One pending event at a time.", C),
        ("Custom Island Event (0, or 30,000 tech points): an event you write: food and tech points added, taken or "
         "set to 0, the berry bush and crops refilled, new villagers, deaths, sickness, pregnancies, likes, looks, "
         "skills, titles, masks and villager actions, or a question with two choices and up to four outcomes each "
         "with its own chance.", C),
        ("Choose Time Skip Amount (0, or 50,000 tech points): 1 to 72 years, made in steps of at most one Time Warp "
         "each, the game's catch-up replaying each step.", C),
    )),
)

ENTRIES: tuple[Entry, ...] = TECHNOLOGIES + PUZZLE_ENTRIES + BUILDINGS + ITEMS + ORIGINS


def item_facts(village: gm.Village | None = None) -> list[gm.Fact]:
    """Every entry as Facts of ITEMS_GROUP: the entry's name and first line, then its other lines as sub-bullets.
    `village` is accepted for the page's module interface; the lines are the same on every page."""
    out: list[gm.Fact] = []
    for entry in ENTRIES:
        (head, ok), *rest = entry.lines
        out.append(gm.Fact(ITEMS_GROUP, f"{entry.name}: {head}", ok))
        out.extend(gm.Fact(ITEMS_GROUP, text, label, sub=True) for text, label in rest)
    return out


def counts() -> dict[str, int]:
    """How many entries of each kind."""
    return {kind: sum(1 for entry in ENTRIES if entry.kind == kind) for kind in KINDS}
