"""Write New Believers' "Heathen Tribe Expansion and Evolution" row (v1.35.101) and its flag file.

The owner (2026-11-25 and 2026-11-26; docs/heathen-tribe-expansion-decisions.md, which overrides the design in
docs/heathen-tribe-expansion-design.md): one row, id vv5_heathen_tribe_evolution, off in Default Patches and Select
All, ON in Owner's Defaults.  It folds three earlier rows into one:

  * "Heathen Tribe Ages, Dies and Has Children"                            (vv5_heathen_tribe_ages)
  * "All Heathens Leave Skeletons"                                         (vv5_all_heathens_leave_skeletons)
  * "Heathens can be selected in Island Events/Heathen-Exclusive Events"   (vv5_heathens_in_island_events)

A saved selection naming any of them ticks this row (src/vv_fun_patcher.py FOLDED_FUN_PATCH_IDS); the companions
still honour the old flag files, and a re-patch removes them (RETIRED_PATCHER_FILES).

It ships three companions, each pinned by SHA-256, and one flag file:

  * "VVFP Heathen Aging.dll"     (W-A, native/vvfp_heathen_aging)     tribe life and population;
  * "VVFP Heathen Life.dll"      (W-B, native/vvfp_heathen_life)      sickness, Heathen doctors, show actions, skills;
  * "VVFP Heathen Mausoleum.dll" (W-C, native/vvfp_heathen_mausoleum) the Shrine to the Ancestors;
  * "VVFP Heathen Tribe Evolution.txt" (native/shared/heathen_evo.h HE_FLAG_ROW), the flag every one of them reads.

The row's Settings window (src/vv_fun_patcher_gui.py) holds the two sliders, the show-action percent, "keep every
new Heathen blue", and (the owner, 2026-11-28) the tribe size, the room kept for believers and how often the tribe
changes; the patcher writes them beside the companions at each patch ("VVFP Heathen Tribe Births.txt",
"VVFP Heathen Arrivals.txt", "VVFP Heathen Options.txt": src/vv_fun_patcher.py _write_heathen_evolution_choices).

"Former Villagers Among the Heathens Leave Skeletons" stays its own row and ships the Mausoleum too (decision 14):
scripts/build_heathen_aging_features.py imports MAUSOLEUM_DLL and MAUSOLEUM_SITES from here.

    python scripts/build_heathen_tribe_evolution_feature.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ROW_ID = "vv5_heathen_tribe_evolution"
ROW_NAME = "Heathen Tribe Expansion and Evolution"
ROW_TAG = "Heathen Tribe Evolution"
FLAG = "VVFP Heathen Tribe Evolution.txt"
FLAG_SOURCE = ROOT / "assets" / "heathen_aging" / FLAG

AGING_DLL = "VVFP Heathen Aging.dll"
LIFE_DLL = "VVFP Heathen Life.dll"
MAUSOLEUM_DLL = "VVFP Heathen Mausoleum.dll"
DLL_SOURCES = {
    AGING_DLL: ROOT / "assets" / "heathen_aging" / AGING_DLL,
    LIFE_DLL: ROOT / "assets" / "heathen_life" / LIFE_DLL,
    MAUSOLEUM_DLL: ROOT / "assets" / "heathen_mausoleum" / MAUSOLEUM_DLL,
}
FOLDED_IDS = ("vv5_heathen_tribe_ages", "vv5_all_heathens_leave_skeletons", "vv5_heathens_in_island_events")


def _installed(dll: str) -> str:
    return f"{dll}, VvfpStartup (started by VVFP More Companions.dll, third word)"


# "VVFP Heathen Life.dll" (vvfp_heathen_life.c VvfpStartup): (VA, stock bytes, branch opcode, what it is).
LIFE_SITES = (
    (0x46F0BA, "389AEC1C0000740D", "E9",
     "the believers' next-action picker 0x46F070's faction test `cmp byte [edx+0x1CEC], bl; je`: an ordinary "
     "Heathen with nothing to do takes, on the row's show-action percent of the picks, a show action built from the "
     "game's own step adders with no skill-check or payoff step (a harvest once its puzzle is solved, carried to "
     "the encampment; a facility visit; a show meal; devotion at the mud hut; a child's nursery play while someone "
     "teaches there), a sick one the sick look; everything else the stock Heathen AI 0x46E9E0"),
    (0x468C3C, "389E481C0000751D", "E9",
     "the drag-a-healer cure 0x468C10's sickness test: the patient's faction is noted as the cure begins (only "
     "when the Village Statistics row's detour is not already there; with it, nothing of ours is written here)"),
    (0x468D4D, "830568D3510001", "E9",
     "the drag-a-healer cure's People Cured +1 (0x51D368): skipped for a patient who was a Heathen as the cure "
     "began (only when the Village Statistics row's detour is not already there)"),
)


# "VVFP Heathen Aging.dll" with this row's flag only (vvfp_heathen_aging.c walk_stub; the owner, 2026-11-26: an elder
# Heathen's "speed must not be impacted at elderly age").
WALK_SITES = (
    (0x4659C5, "8D8E8C1B0000E8C09D0000", "E9",
     "the walk set-up 0x465980's elder test (`lea ecx, [esi+0x1B8C]; call 0x46F790`, the slow pace 0x28 for an "
     "elder at 0x465A06): a Heathen skips it and walks at the pace of anyone who is not an elder; a believer elder "
     "still slows"),
)


# "VVFP Heathen Aging.dll" with this row's flag, their own all-or-none set (vvfp_heathen_aging.c nurse_stub and
# rascal_stub; the owner, 2026-11-27/28).
LOOK_SITES = (
    (0x46EAB8, "8B8E881B000039994C1C00007407", "E9",
     "the Heathen AI 0x46E9E0's carrier test (`mov ecx, [esi+0x1B88]; cmp [ecx+0x1C4C], ebx; je`): a Heathen carrying "
     "a baby this companion conceived (never a puzzle Heathen) holds the baby and is given the believers' mothers' "
     "routine 0x46A1D0 (\"Taking care of her baby\", washing, changing, showing baby the island) until the birth; "
     "any other carrier the stock carry"),
    (0x4430C6, "3898ED1C00007415", "E9",
     "the Details panel's Heathen child title (`cmp byte [eax+0x1CED], bl; je`): an orange OR red Heathen child is "
     "titled \"Rascal\" (string 0xD2), every other one \"Child\""),
)


def _call(va: int, target: int) -> str:
    return "E8" + ((target - (va + 5)) & 0xFFFFFFFF).to_bytes(4, "little").hex().upper()


# "VVFP Heathen Mausoleum.dll" (vvfp_heathen_mausoleum.c VvfpStartup, 17 sites).
MAUSOLEUM_SITES = (
    (0x473FA9, "E8C20CFFFF", "E8",
     "the burial's Roster of the Dead write (op 0x1D, 0x473F50): a Heathen's grave (the faction at death) goes to the "
     "Shrine to the Ancestors' own table, written by the game's own writer 0x464C70; a believer's to the Roster of "
     "the Dead as before"),
    (0x45B650, "6A14E80980FAFF83C4046A006A64B9BD0600005183C07D508BCEE8318F0100", "E9",
     "the burial script 0x45B5D0's carry walk: a Heathen's body is carried to the mud hut, a believer's to the "
     "mausoleum door; the game's rand(20) drawn as in the stock script"),
    (0x46E9E0, "83EC2053568BF1", "E9",
     "the Heathen AI's entry: an able adult Heathen (no puzzle role, not sick or expecting) starts the game's own "
     "\"Burying the dead\" on a Heathen's body nobody is burying, half the times it is asked"),
    (0x46F146, "E8F5170000", "E8",
     "the believers' burial chooser's body finder: a Heathen's body only when no Heathen can bury it or it has lain "
     "120 units -- still carried to the mud hut"),
    (0x43F4F1, "B9A8815400", "E8", "the Mausoleum screen's roster count read: the table the screen shows"),
    (0x43F735, "B9A8815400", "E8", "the Mausoleum screen's row draw read: the table the screen shows"),
    (0x43FDC0, "B9A8815400", "E8", "the Mausoleum screen's click read: the table the screen shows"),
    (0x43FED6, "B9A8815400", "E8", "the Mausoleum screen's hover read: the table the screen shows"),
    (0x43CE24, _call(0x43CE24, 0x43CC00), "E8",
     "the mausoleum's own opener: the believers' Roster of the Dead, then 0x43CC00"),
    (0x423E2B, "E880370500", "E8",
     "after the lcmap load: hotspot 0x0B registered (area-handler table 0x77DC80) and stamped on the mud hut's cells"),
    (0x4246E1, "E8CA2E0500", "E8", "after the other lcmap load: the same"),
    (0x424569, "E832060400", "E8",
     "the save's roster copy (0x4244F0): once the slot save is written, the Shrine's table is published to the slot's "
     "file, so the file always matches the save"),
    (0x424733, "E898040400", "E8", "the new village's roster clear (0x4246A0): the Shrine's table is cleared too"),
    (0x425849, "E8A2F60300", "E8", "the load's roster read (0x425640): the slot's Shrine file is read"),
    (0x43F1DF, "E8ACEBFCFF", "E8",
     "the Mausoleum screen's title widget: \"Shrine to the Ancestors\" while it shows the Heathens' graves"),
    (0x46B116, "B9A8815400E8709DFFFF", "E8",
     "the everyday \"Honoring the dead\" chooser's grave count: the believers' graves and the Shrine's"),
    (0x414DB0, "B9A8815400E8D6000500", "E8", "the Day of Honor's \"two graves or more\": the same count"),
)
MAUSOLEUM_CHANGES = [
    "\"VVFP Heathen Mausoleum.dll\" (the Shrine to the Ancestors): a Heathen's grave -- decided by the faction at "
    "death: a camp Heathen, an arrival, a puzzle Heathen or a former villager who died a Heathen -- goes to a table of "
    "its own laid out as the game's Roster of the Dead (500 graves), written by the game's own writer, so its "
    "epitaph, cause and job are the game's.  A believer's grave, a converted former villager's included, goes to "
    "the Roster of the Dead as before.  A full table: no grave, the body gone, the Death record says so.",
    "Heathens bury Heathens (decision 11): an able adult Heathen starts the game's own \"Burying the dead\" on a "
    "Heathen's body and carries it to the mud hut; believers bury it (once The Buried Mausoleum is solved) only when "
    "no Heathen can or it has lain 120 units, still to the mud hut.",
    "The mud hut (hotspot 0x0B, registered and stamped after each map load) opens the game's own Mausoleum screen on "
    "the Shrine's table with a click or a villager dropped on it, once it holds a grave; the title says \"Shrine to "
    "the Ancestors\" (translatable), the art is the game's own.  Holding a villager over it shows \"<name> sees a "
    "heartfelt memorial shrine.\" (Fix Vanilla Bugs' hovel hover line).",
    "The table is kept per save slot in \"Virtual Villagers Fun Patcher\\Save <S>\\Data\\Heathen Mausoleum\\Heathen "
    "Mausoleum - Save <S>.dat\" ('VHM1'), written only when the game saves the slot and read when it loads it; a new "
    "village clears it; Start Over forgets it (VVFP Save Reset.dll).",
    "Day of Honor, the everyday Honoring the dead, the Remembrance Ceremony and Story / Cheat Upgrades' \"graves\" "
    "condition count the Shrine's graves too; the Village Statistics never do.  The Deaths log names the grave "
    "\"the Shrine to the Ancestors (...)\", or \"no grave (the Shrine to the Ancestors was full)\".",
]

AGING_SITES_NOTE = "two sites of \"VVFP Heathen Aging.dll\" (scripts/build_heathen_aging_features.py SITES)"


def description() -> str:
    not_seen = "**Not yet seen in a running game** (checked by emulation of the stock executable)."
    return (
        "New Believers. The Heathen camp lives and grows as a tribe of its own. **A growing camp makes The Last "
        "Heathen harder to reach, or impossible: that puzzle is solved only when no Heathen is left, and with births "
        "and new arrivals the camp may never empty.** Its Settings... button holds the two sliders and the options. "
        "AGING: every Heathen ages as believers do and can die of old age by the believers' rule -- the camp's "
        "Heathens, villagers who left your tribe and the puzzle Heathens. A puzzle Heathen whose puzzle is not "
        "solved yet is replaced at once in the same role, so every puzzle can still be solved. "
        "COUPLES AND BABIES: two adult Heathens who are not kin (never parent and child, full or half siblings) pair "
        "for life, until one dies or joins your tribe; a couple can be of either sex. A Heathen couple of a woman "
        "and a man EMBRACE as believers do -- one walks to the other, who waits for them, and they go into the Love "
        "Shack once it is built (before that they embrace where they stand) -- and the baby is conceived then. A "
        "Heathen whose title says Parent may also embrace any Heathen of the other sex who is not their kin. At 1x "
        "about one conception for the whole tribe every 6 real-life hours on Normal speed (\"0.1-10x Heathen Tribe "
        "Births\"). Twins and triplets come as for believers: only with Medicine at level 3 (5.25% twins, 1.75% "
        "triplets). The mother carries and nurses the baby as believers do (taking care of it, washing, changing, "
        "showing it the island) until it is two and joins the camp as a child; Heathen children grow up and can "
        "have children of their own. Births go on after The Last Heathen while a Heathen woman and a Heathen man are "
        "alive. A couple of one sex has babies only through island events. "
        "NEW ARRIVALS (\"0-10x New Heathen Arrivals\", 0 = none): at 1x one arrival about every 48 real-life hours "
        "on Normal -- one to four Heathens, sometimes a couple with up to two children -- before and after The Last "
        "Heathen. "
        "TRIBE SIZE (Settings): \"Heathen tribe size\" Off (the default: the camp grows by the rates above) or a "
        "most of 10 up to what the game can hold (50 in Owner's Defaults): babies on the way count, growth slows "
        "near the limit and waits at it, and nobody is ever removed. While it is on, \"How often the tribe changes\" "
        "(0.1-10x) paces the growth: at 1x something new comes to the camp about every 2-6 real-life hours on Normal "
        "(a conception about every 6 hours, an arrival about every 12 with arrivals at 1x), and while the camp has "
        "fewer children than a tenth of its size (at least 2) babies come twice as often and arrivals are families "
        "with children. \"Room kept for believers\" (20 unless changed, at least 10) is always left free for your "
        "own villagers' babies and arrivals. "
        "MASKS: newcomers and Heathen babies are mostly blue-masked: 90% blue, 7% orange, 3% red (all blue with the "
        "option), never more than 10 orange or 10 red Heathens (the camp's own may be more), and among the children "
        "at most 1 or 2 orange and 1 or 2 red, each of them a \"Rascal\"; a village that already has more keeps them, "
        "new children are blue until it is under. A Heathen of the camp (not a puzzle Heathen) who masters a skill "
        "(100) wears the purple mask -- the first master of each of the six skills, one each, the next one when they "
        "die or leave (needs \"Heathens Keep Their Masks When Converted\" and the Origins icons); they show the "
        "game's \"Master\" titles, and only the puzzle Heathens keep their own titles. "
        "A NEW CHIEF AND MASTERS: when the Heathen Chief or a Heathen Master dies after their puzzle is solved, the "
        "eldest adult Heathen takes the role -- for show (the role's skills, mask and title) until The Last Heathen "
        "is solved, the real role after it; a regrown camp of six adults gets a Chief and Masters again. Every later "
        "Chief, Master, Doctor or Mommy can be of either sex. A show Chief who joins your tribe becomes a real "
        "Retired Chief. "
        "CHILDREN GROW UP: when one of the camp's own children reaches 14, a new child takes their place at once, in "
        "the same camp role and mask -- the Rascal, the camp's orange-masked child, is replaced by a new Rascal -- "
        "and the grown one stays as an adult (an Arrived record \"Replaced a Heathen child who grew up\"). Babies of "
        "Heathen couples, arrivals' children and children who left your tribe are the tribe's growth and are not "
        "replaced. After The Last Heathen this happens only while New Heathen Arrivals is above 0. "
        "ELDERS RETIRE: at the game's elder age (55, later with Medicine) a Heathen with a camp role or a puzzle role "
        "-- the Heathen Doctor, a Heathen Master, the Heathen Mommy -- retires to the encampment and the eldest "
        "younger adult Heathen takes the role, with the puzzle's own set-up (the Mommy's successor carries her "
        "infant), so every puzzle can still be solved. **The Heathen Chief never retires.** With nobody younger the "
        "elder keeps the role until someone grows up or arrives. Elder Heathens keep their walking pace; elder "
        "believers still slow down as in the game. "
        "SICKNESS AND HEATHEN DOCTORS: Heathens fall sick by the believers' rule; ordinary Heathens with Healing "
        "skill heal them (never the puzzle's Heathen Doctor); with nobody able they get well on their own. A sick "
        "Heathen never dies of it and never drops below 21 health. Heathens never eat from your food store and never "
        "starve. Heathen cures never count in People Cured. "
        "SHOW ACTIONS (about 1 in 4 of an idle adult Heathen's choices at the default 25%): harvesting noni, crops "
        "or fish once the puzzle that opens each to your believers is solved -- never taking anything, carried to "
        "the encampment, not the granary; visiting the pools, the Believer Idol, the science lab, the farm plots, "
        "and the Love Shack and Clothing Hut doors once built (no embrace, no clothes); a show meal; devotion at the "
        "mud hut. Heathens do only what believers of their age do: children play in the nursery while someone "
        "teaches there, and the Love Shack only at the couples' ages. None of it changes anything of your "
        "believers'. "
        "SKILLS grow by practice as believers' do, Devotion included (no tech bonus, no trophies); a Heathen keeps "
        "them on joining your tribe. "
        "THE SHRINE TO THE ANCESTORS: every Heathen who dies leaves a skeleton. Heathens carry their own dead to the "
        "mud hut and bury them there; believers do it, still to the mud hut, when no Heathen can (once The Buried "
        "Mausoleum is solved). Click the mud hut, or drop a villager on it, to see the Shrine to the Ancestors: the "
        "game's own Mausoleum screen with the Heathens' graves. A villager who left your tribe and died a Heathen "
        "goes there; one who rejoined your tribe goes to your Mausoleum. Heathen graves already in your Mausoleum "
        "stay there. Day of Honor, the Remembrance Ceremony and Honoring the dead count the Shrine's graves. "
        "ISLAND EVENTS: Heathens can be chosen for island events, the new ones and the game's own, and the "
        "Heathen-Exclusive Events can happen. A sick Heathen is never chosen; the puzzles' Heathens can be in a new "
        "event but nothing in it really happens to them (\"(no effect)\"); in the game's own events a Heathen's Faith "
        "never changes; outcomes for the whole tribe happen to the Heathens' village when only Heathens are in an "
        "event (\"(no effect)\"). "
        "LOGS: each Heathen's conception, birth, couple, arrival, new role, retirement, death and grave goes in the "
        "logs, marked "
        "as a Heathen. **Heathens never count in the Village Statistics.** Heathens always leave the room kept for "
        "believers free. "
        "This row replaces \"Heathen Tribe Ages, Dies and Has Children\", \"All Heathens Leave Skeletons\" and "
        "\"Heathens can be selected in Island Events/Heathen-Exclusive Events\": a saved selection with any of them "
        "ticks this row. \"Former Villagers Keep Aging Among the Heathens\" and \"Former Villagers Among the Heathens "
        "Leave Skeletons\" stay separate (with this row on they change nothing more). Off by default and in Select "
        "All; Owner's Defaults ticks it, with new arrivals at 1x. **Needs Story / Cheat Upgrades for the island "
        "events and the show Chief's and Masters' titles; the Heathen-Exclusive Events also need the Isola Grand "
        "Event Collection.** " + not_seen + " The companions are \"VVFP Heathen Aging.dll\", \"VVFP Heathen "
        "Life.dll\" and \"VVFP Heathen Mausoleum.dll\"; they keep their own small files per save and never write a "
        "save."
    )


EVOLUTION_CHANGES = [
    "\"VVFP Heathen Aging.dll\" with \"VVFP Heathen Tribe Evolution.txt\" (which stands for the folded rows' three "
    "flags; the old flags are still read): every Heathen ages and can die of old age by the believers' rule, a "
    "puzzle Heathen whose puzzle is unsolved is replaced at once by the stock camp's own set-up of that role, and "
    "every Heathen leaves a body for the burial.",
    "Embraces and births (the owner, 2026-11-27/28; native/vvfp_heathen_aging/heathen_tribe.inc): once a unit of the "
    "village's clock, after its arrival roll, 1 in 600 / t (t the births slider in tenths, 1..100; \"VVFP Heathen "
    "Tribe Births.txt\", 1x when missing; with \"Heathen tribe size\" on b x c x F in 6,000,000, doubled while short "
    "of children): about one conception for the tribe every 60 units (6 h on Normal) at 1x.  The roll picks a pair "
    "at random: a couple of a woman 14-45 (not expecting, not the Heathen Mommy) and a man, or a Heathen titled "
    "Parent (0x4755C0's highest skill, or the job +0x1C74, Parenting at 20+) with a Heathen of the other sex who is "
    "not kin; both free (living, aging, adult, not sick, held or carrying; a puzzle Heathen only once its puzzle is "
    "solved).  The believers' embrace (0x46CC93): the partner behaviour 6, the seeker stopped, \"Embracing\" "
    "(0x193), the walk to the partner's spot +10 (distance 300), gesture 1 -- without the embrace step 0x10 "
    "(0x4689A0's believer checks, messages and births counter).  Met within 40 px at a later look: 0x465E00 forced "
    "with 0x467D20's baby skill and value, the woman the carrier, the Medicine litter rule of the routine (single "
    "below Medicine 3), as many as fit; the twins and triplets counters put back; then both behaviour 7 (the Love "
    "Shack) once project 23 is done, else an embrace look where they stand.  Not met in 3 units: given up.  The "
    "load-time catch-up (more than 20 units in a look) conceives at once.  The believers' Parenting gate (rand(300) "
    "+ 50 - 50 x Medicine <= Parenting, 0x468B8E) is not applied: the owner's rate is the rate.  Births go on after "
    "The Last Heathen.",
    "Nursing: at 0x46EAB8 (the Heathen AI's carrier test) a carrier of a baby this companion conceived (never roles "
    "12-17) holds the baby (carry 3) and is given the believers' mothers' routine 0x46A1D0 (behaviours 0x2B / 0x4A "
    "in the rain, else 0x43, 0x42, 0x7E, 0x76, 0x77, 0xD4, 0xD5 on 80% of the picks -- look steps only); the birth "
    "40 units after the conception as before.",
    "Tribe size (\"VVFP Heathen Options.txt\": tribe_max, 0 off; room_kept, 20, 10-100; change_tenths, 10): "
    "conceptions, event pregnancies and arrivals add only while living Heathens plus babies on the way stay under "
    "tribe_max (10 or more, kept within the table less room_kept) and room_kept records stay free; F falls from 100 "
    "to 0 over the last fifth of the limit (at least 3); arrivals then roll a x c x F in 1,200,000 (one every 120 "
    "units at 1x) and are a family with 1-2 children while short of children (fewer than a tenth of the size, at "
    "least 2, under 14 or on the way).  Nobody is removed.",
    "Masks (the owner, 2026-11-28): a new orange or red mask only while fewer than 10 living Heathens wear it, and "
    "for a child (a newborn, an arrival's child, a grown-up camp child's replacement) fewer than the village's "
    "Rascal cap of that colour (1 or 2 each, drawn once, kept in \"...\\Data\\Heathen Tribe\\Heathen Tribe - Save "
    "<S>.dat\", 'VHT1'); no existing mask changes.  At 0x4430C6 an orange or red Heathen child is titled \"Rascal\".  "
    "Purple masters: the first Heathen of roles 0-11 (no role for show) with a skill at 100 wears that skill's "
    "purple mask through the Origins mask store (one a skill; the next when they die, convert or leave; their "
    "identities in the tribe file, following renames).",
    "Couples (decision 15): two living adult Heathens of either sex, not kin (parent and child; full and half "
    "siblings, by the records' parent name, head and body), pair for life, at most one new couple a look; kept per "
    "slot in \"Virtual Villagers Fun Patcher\\Save <S>\\Data\\Heathen Couples\\Heathen Couples - Save <S>.dat\" "
    "('VHC1'), following renames.  An unreadable couples file is never replaced, and pauses that village's couples, "
    "births and arrivals.",
    "Arrivals: rolled once a unit of the village's clock, 1 in 4,800 / t (t the arrivals slider in tenths, 0..100; "
    "\"VVFP Heathen Arrivals.txt\", 0 = none when missing): a group of 1-4 (40/30/20/10%), half of the groups of two "
    "or more a couple with 0-2 children aged 2-12, made by the Heathen creator 0x46FD20 (Faith 1, then the camp's "
    "Faith written), roles 0-11, placed beside a living Heathen; never from nobody before The Last Heathen.",
    "Masks of arrivals and newborns (decision 7): 90% blue, 7% orange, 3% red (\"VVFP Heathen Options.txt\" "
    "mask_orange_percent / mask_red_percent; 0 / 0 with \"Keep every new Heathen blue\"); the puzzle roles keep "
    "their own masks.",
    "Roles (decision 6): a dead Chief or Master whose puzzle is solved is succeeded by the eldest adult ordinary "
    "Heathen -- the real role 13-16 after The Last Heathen, otherwise for show (the role's skills, the Chief's or "
    "the purple mask through the Origins mask store, the original's own title through Story / Cheat Upgrades' "
    "VvfpStorySetCustomTitle); a regrown camp of 6 adults gets a real Chief and Masters; a show Chief who converts "
    "is given role 13 (the Retired Chief) and the show title is taken off.",
    "Children who grow up (the owner, 2026-11-26): when a camp child (a Heathen with no recorded parents, never a "
    "former villager; roles 0-11) reaches 280 units in the life tick, a new child is made at once by the Heathen "
    "creator 0x46FD20 in the same role and mask, Healing 0, the stock camp's Faith: the Rascal (the Details title "
    "0x4430AE..0x4430D6, string 0xD2: a Heathen younger than 280 in the orange mask; the stock camp's 0x424D23, "
    "age 140) by a Rascal of 140, a blue child at 120 or 240 (0x424CF9, 0x424D4D); its Arrived record \"Replaced a "
    "Heathen child who grew up\" (\"... an Isolan child ...\"), within the Rascal caps.  No room (the room "
    "kept): owed in the slot's "
    "file.  After The Last Heathen only while New Heathen Arrivals is above 0.",
    "Elders retire (the owner, 2026-11-26; \"the chief shouldn't retire\"): an elder by the game's test 0x46F790 "
    "(age >= 160 x Medicine + 840) who holds a camp role 1-11, a puzzle role 12, 14-17 while its puzzle is "
    "unsolved, or a Master's role for show or after The Last Heathen gives it, at a throttled look, to the eldest "
    "adult Heathen who is not an elder and holds none (for a puzzle role a camp-role holder when there is none), "
    "set up as the stock camp sets the role up (skill, Faith; the Mommy's infant by the game's forced conception "
    "with a named other parent) -- never the Chief (13); the elder's role becomes 0, the Heathen AI's default "
    "(0x46EAD9 -> 0x46F007, the camp wander at the encampment).  Nobody younger: no retirement.  Records \"Retired "
    "to the encampment\" (VvfpCauseHeathenRetired) and \"Took the role\" (VvfpCauseHeathenRole).",
    "Elders keep their pace: at 0x4659C5 (the walk set-up 0x465980's `lea ecx, [esi+0x1B8C]; call 0x46F790`, the "
    "slow pace 0x28 for an elder at 0x465A06) a Heathen skips the elder test; a believer elder still slows.",
    "Partners: the life tick's partner cache is checked against the couple's saved identities before every use, "
    "and a Heathen who leaves (a death, an island event) is dropped from it at once, so a reused record is never "
    "taken for a partner.",
    "Room (decision 18 as changed; the owner, 2026-11-28): Heathens are born or arrive only while \"Room kept for "
    "believers\" (room_kept, 20 unless changed, never under 10) villager records stay free, in every population "
    "mode and in the 256 build.",
    "\"VVFP Heathen Life.dll\" (VvfpHeathenLifeUnit, called by Heathen Aging's life-tick splice): the believers' "
    "sickness onset 0x465F50 for ordinary Heathens, their damage never below the floor (21; options sick_floor) "
    "written straight to health (never a cause that can kill), their +1 recovery; Heathen doctors (the best Healing "
    "among ordinary adult Heathens, never role 12) judged by the believers' skill check; well on their own 1 in "
    "240 a unit with no healer; skill practice by the believers' rule with no tech bonus and no trophies.",
    "Show actions (the picker 0x46F0BA, on options show_percent of an idle ordinary adult's picks; 25 by default): "
    "the game's own step adders with the skill-check and payoff steps left out -- noni, crops (the farm plots) and "
    "fish once their puzzles (2, 5, 10) are solved, carried to the encampment; the pools, the Believer Idol once "
    "carved, the science lab, the Love Shack (the couples' ages, no embrace) and the Clothing Hut (no clothes) "
    "doors once built; a show meal (no food taken); devotion at the mud hut; a child's nursery play while someone "
    "teaches at the nursery school.",
    "People Cured: the drag-a-healer cure's +1 is skipped for a Heathen patient (the Village Statistics row's own "
    "technique; with that row applied its detours are left alone).",
    "Logs: every forced Heathen conception gets its Conception record (WriteParentageRecordWithFather); a couple a "
    "\"Couple formed\" record (WriteParentageHeathenCouple); a new arrival an Arrived record \"Arrived at the "
    "Heathen camp\" or \"... with N other(s)\" (\"Isolan\" with Guardians of Isola Rewrite; VvfpCauseHeathenArrived); "
    "a new Chief or Master a \"Took the role\" record (VvfpCauseHeathenRole); each marked \"Faction: Heathen\".",
]
NON_CHANGES = [
    "No executable byte is patched: the three companions splice their sites at run time, only after verifying "
    "their stock bytes, each all or none; Story / Cheat Upgrades splices the game's-own-event sites the same way.",
    "Nothing is written to a save.  The companions keep their own files per save slot (Heathen Aging, Heathen "
    "Couples, Heathen Mausoleum), each written atomically and never replaced when unreadable.",
    "Heathens never count in the Village Statistics: births, arrivals, cures, deaths and the Shrine's graves are "
    "all left out; Babies Made, People Cured, the twins and triplets counters and the death counter are put back or "
    "never touched.",
    "Show actions never take from a source, the food store, a building, tech points or a believer's skill.",
    "The puzzle Heathens (roles 12-17) keep their stock behaviour while their puzzles are unsolved.",
]


def flag_text() -> bytes:
    return (f"Virtual Villagers Fun Patcher: \"{ROW_NAME}\" (New Believers).\n"
            "While this file is here, \"VVFP Heathen Aging.dll\", \"VVFP Heathen Life.dll\" and \"VVFP Heathen "
            "Mausoleum.dll\" make the Heathen camp a tribe of its own.\n"
            "The patcher adds and removes this file with the patch; nothing reads what it says.\n").encode("ascii")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def detours(sites, dll: str) -> list[dict]:
    return [{"va": f"0x{va:X}", "stock_bytes": stock,
             "written_bytes": f"{op}XXXXXXXX" + "90" * (len(stock) // 2 - 5),
             "routine": what, "installed_by": _installed(dll)} for va, stock, op, what in sites]


def row() -> dict:
    import build_heathen_aging_features as aging
    import build_island_event_content_features as content
    events = content.heathens_row(5)
    files = [{"source": DLL_SOURCES[dll].relative_to(ROOT).as_posix(), "destination": dll,
              "sha256": sha(DLL_SOURCES[dll])} for dll in (AGING_DLL, LIFE_DLL, MAUSOLEUM_DLL)]
    files.append({"source": FLAG_SOURCE.relative_to(ROOT).as_posix(), "destination": FLAG, "sha256": sha(FLAG_SOURCE)})
    aging_detours = [{"va": f"0x{va:X}", "stock_bytes": stock,
                      "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
                      "routine": what, "installed_by": aging.INSTALLED_BY} for va, stock, what in aging.SITES]
    story_detours = [d for d in events["runtime_detours"] if "Story Upgrades" in d["installed_by"]]
    return {
        "id": ROW_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": ROW_NAME,
        "description": description(),
        "output_tag": ROW_TAG,
        "dependencies": [],
        "needs_on": [
            {"id": "vv5_story_cheat_upgrades",
             "for": "the island-event engine that chooses the villagers, and the show Chief's and Masters' titles"},
            {"id": "vv5_isola_grand_event_collection", "for": "the Heathen-Exclusive Events"},
        ],
        "conflicts": [],
        "behavior_changes": (aging.AGING_CHANGES + EVOLUTION_CHANGES + MAUSOLEUM_CHANGES
                             + events["behavior_changes"]),
        "explicit_non_changes": NON_CHANGES + events["explicit_non_changes"][1:],
        "evidence_status": ("emulated on the stock executable: tests/test_vv5_heathen_aging.py, "
                            "tests/test_vv5_heathen_evolution.py, tests/test_vv5_heathen_tribe_looks.py, "
                            "tests/test_vv5_heathen_life.py, "
                            "tests/test_vv5_heathen_mausoleum.py, tests/test_vv5_heathen_evo_logs.py, "
                            "tests/test_heathens_in_island_events.py, tests/test_heathens_in_existing_events.py, "
                            "tests/test_heathen_only_events.py; the row in tests/test_vv5_heathen_tribe_evolution.py; "
                            "runtime/player confirmation pending"),
        "companion_files": files,
        "patches": [],
        "runtime_detours": (aging_detours + detours(WALK_SITES, AGING_DLL) + detours(LOOK_SITES, AGING_DLL)
                            + detours(LIFE_SITES, LIFE_DLL) + detours(MAUSOLEUM_SITES, MAUSOLEUM_DLL)
                            + story_detours),
    }


def main() -> None:
    FLAG_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    FLAG_SOURCE.write_bytes(flag_text())
    out = ROOT / "data" / f"{ROW_ID}_feature.json"
    out.write_text(json.dumps(row(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
