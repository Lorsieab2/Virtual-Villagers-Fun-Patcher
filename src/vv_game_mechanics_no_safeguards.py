"""Game Mechanics: what "No Safeguards for Island Events (and Additional Events too)" (vvN_island_events_any_time) does
to each game's OWN island events (the owner, 2026-11-15) -- "VVFP No Safeguards.dll", native/vvfp_no_safeguards, its
sites and their addresses in ns_vvN.inc; docs/no-safeguards-island-events.md has the same lists as tables.

Shown in the Island events group only when that row is in the game (Village.has is True).  Every line is read from the
game's own code (static tracing), not yet seen in play.
"""
from __future__ import annotations

import vv_game_mechanics as gm

GROUP = "Island events"
NAME = "No Safeguards for Island Events (and Additional Events too)"
COMMON = (
    "the game's own island events lose every condition except what an event needs to happen or make sense: the "
    "villagers it casts (a child for a child's event, a woman and a man, a pregnant villager, a healer...), the "
    "puzzle it is tied to, and at least one grave for a Day of Honor. The timer, which event is chosen among those "
    "that can happen, the first events' rules and the rescue events are the game's own. Kept for safety: a "
    "villager is never made past the villager table's real size (the game's own makers refuse then, and the "
    "patcher's record guards stay). Always protected: anything that is not a living villager (the dead, bodies"
)

# Per game: (the objects always protected, the lifted conditions, the kept conditions).
GAMES = {
    1: (", and nothing else: A New Home keeps no object in its villager table) is never cast.",
        "Lifted: an island event no longer waits for a villager of 14 or more; A Plague of Locusts no longer needs "
        "Farming 2; The Barrel O` Babies no longer needs room (the population cap and the huts for 15, 25 and 50 "
        "people); The Trapped Whale no longer needs Spirituality below 3, The Visitor Medicine below 3.",
        "Kept: a living child for The Measles Epidemic, The Troubled Child and The Suspicious Monkey; the beach "
        "clean-up solved for The Big Wave; the village not empty; the catch-up wait (the drawn villager's age caught "
        "up)."),
    2: (", and the Esteemed Elders' totem statues) is never cast or harmed.",
        "Lifted: an island event no longer waits for a villager of 14 or more; A Dangerous Mission no longer needs "
        "more than 60 villagers; The Ancient Gold Coin no longer needs Culture below 2; The Cursed Idol no longer "
        "needs 250 food; The Silver Mirror no longer needs 2 villagers; The Spyglass comes at Exploration 2 too.",
        "Kept: a child for For The Birds and The Child Prodigy; a woman of 14 or more for Prettiest Tribe Girl; a "
        "woman and a man of 18 or more for The Love Note; a pregnant or nursing villager of 18 or more for Where Are "
        "The Infants?; someone in the memorial for Day of Honor; all 16 puzzles solved for The Epidemic, Rats!, The "
        "Foul Passing and Where Are The Infants?. Kept for safety: room for The Barrel O` Babies, Old Friends and The "
        "Savage Child (the same check guards the villager table, so its hut tiers stay too); Exploration 3 for The "
        "Spyglass (keeping it would take a researched level away); The Crystal Ball's villager of 14 or more (Fix "
        "Vanilla Bugs rewrites those bytes)."),
    3: (", and nothing else: The Secret City keeps no object in its villager table) is never cast.",
        "Lifted: an island event no longer waits for a villager of 14 or more; \"not the Tribal Chief\" in every "
        "event; the head-counts (The Tsunami's 2 women and 2 men, The Science Fair's 3 children, The Daredevil's 2 "
        "women, The Mysterious Crate's 3 adults, The Low Tide's 8 villagers, Day of Honor's 2 graves to 1); "
        "technology levels (Nature 1, Magic 1, Science below or above 2, Alchemy below 3, Medicine 2); the room for "
        "The Canoe from the Other Side, The Crystal of Reflections and Another One of Those Barrels; The Mushroom "
        "Celebration's 500 items brought home.",
        "Kept: each event's own villagers (children under 14, adults 18 to 49 not pregnant or nursing, elders 50 and "
        "over -- the shared picker's classes; The Lazy Apprentice's teacher with Research 30; the Tribal Chief for The "
        "Chief's Address); the puzzles (15 of 16 for The Tsunami, the Bee Hive for The Miraculous Bloom and The Hole "
        "in the Hut, the Alchemy Lab for The Blue Pearl); the burning fire for The Cold Snap; the catch-up wait."),
    4: (", bodies and ghosts) is never cast.",
        "Lifted: Day of Honor's 2 graves to 1; \"not pregnant or nursing\" (The Arc of Brilliant Colors, The Sealed "
        "Box, the two Innovations); \"not sick\" (The Abandoned Infants, The Screaming Baby, the two Innovations); The "
        "Abandoned Infants' 6 women to 1 and its room; the Daredevil Barrel's room; Festival of the Banyan's 500 "
        "deliveries; The Pretty Shell's 2 villagers of 14 or more to 1.",
        "Kept: each event's own villagers (a child, a villager of 14 or more, a pregnant or nursing woman, and for "
        "The Abandoned Infants a woman of 18 or more to take the baby -- the event's own pick); the tree puzzles (3 "
        "of 5 for Festival of the Banyan, the tree's state events), The Stream for the Daredevil Barrel and The "
        "Mosquito Larvae, Soap for The Mosquito Larvae, the Cooking Pit for Innovation in Farming; the burning fire "
        "for The Cold Snap; the village not empty; the catch-up wait."),
    5: (", corpses and Reanimate spirits) is never cast. Heathens are villagers.",
        "Lifted: Day of Honor's 2 graves to 1; the believer picks' role test (the Retired Chief and converts can be "
        "cast); \"not sick\" for the Heathen children and Heathens of Outreach and The Defector; \"not pregnant or "
        "nursing\" for Bed Bugs; Science below 2 (You're Doing It Wrong) and exactly 2 (The Advanced Artifacts); "
        "100 food for Trick Or Trade; Food Mastery below 2 for The Migrating Fruit Bats; the room for the four "
        "events that bring villagers; The Strange Nectar from 18 to 14.",
        "Kept: each event's own believer or Heathen (and a believer child where the story is a child's); the "
        "Heathen role characters; the puzzles (the Hydroponic Farm, the Knowing Totem, The Heathen Scientist); the "
        "burning fire for The Cold Snap; no God Power armed on the pointer and The Strange Nectar's 14 (kept for "
        "safety: not proven safe without them); the catch-up wait."),
}


def row_id(game: int) -> str:
    return f"vv{game}_island_events_any_time"


def facts(village) -> list[gm.Fact]:
    """The row's lines, only when it is in the game."""
    game = village.game
    if game not in GAMES or village.has(row_id(game)) is not True:
        return []
    objects, lifted, kept = GAMES[game]
    head = f"With the patcher's \"{NAME}\" (in this game): {COMMON}{objects}"
    return [gm.Fact(GROUP, head, gm.CODE), gm.Fact(GROUP, lifted, gm.CODE, sub=True),
            gm.Fact(GROUP, kept, gm.CODE, sub=True)]
