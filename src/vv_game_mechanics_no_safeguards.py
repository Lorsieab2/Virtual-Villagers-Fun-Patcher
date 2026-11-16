"""Game Mechanics: what "No Safeguards for Island Events (and Additional Events too)" (vvN_island_events_any_time) does
to each game's OWN island events (the owner, 2026-11-15: "ONLY APPLIES TO VILLAGER ELIGIBILITY PICKING FOR ISLAND
EVENTS. ANYONE CAN BE PICKED AT ANY TIME, ANY EVENT CAN BE PICKED AT ANY TIME, EXCEPT: when it doesn't make sense
within the event's text or context ..., or the event mentions someone the village doesn't have") -- "VVFP No
Safeguards.dll", native/vvfp_no_safeguards, its sites and their addresses in ns_vvN.inc;
docs/no-safeguards-island-events.md has the same lists.

Shown in the Island events group only when that row is in the game (Village.has is True).  Every line is read from the
game's own code and popup text (static tracing), not yet seen in play.
"""
from __future__ import annotations

import vv_game_mechanics as gm

GROUP = "Island events"
NAME = "No Safeguards for Island Events (and Additional Events too)"
COMMON = (
    "anyone can be picked and any of the game's own island events can come, except where the event's own text or "
    "result would make no sense without the rule, or names someone the village does not have. Nothing is stricter "
    "than in the normal game. The timer, which event is chosen among those that can come, the first events' rules "
    "and the rescue events are the game's own. Kept for safety: a villager is never made past the villager table's "
    "real size. Never picked: anything that is not a living villager (the dead"
)

# Per game: (who is never picked, the lifted rules, the kept rules with their reasons).
GAMES = {
    1: (", bodies).",
        "Lifted: an island event no longer waits for a villager of 14 or more; The Barrel O` Babies no longer needs "
        "room (the population cap and the huts for 15, 25 and 50 people).",
        "Kept: A Plague of Locusts' Farming 2 (crops are food only from Farming 2); The Trapped Whale's Spirituality "
        "below 3 and The Visitor's Medicine below 3 (the answers raise them); the cleaned beach for The Big Wave (the "
        "wave covers it again); a child for The Measles Epidemic, The Troubled Child and The Suspicious Monkey (their "
        "stories are about children); a living villager for every encounter and crate; the catch-up wait (timing)."),
    2: (", and the Esteemed Elders' totem statues, which no event can ever reach).",
        "Lifted: an island event no longer waits for a villager of 14 or more; The Epidemic, Rats!, The Foul Passing "
        "and Where Are The Infants? no longer need all 16 puzzles solved (their texts never mention puzzles); Where "
        "Are The Infants?' mother no longer has to be 18 or more; The Silver Mirror no longer needs 2 villagers.",
        "Kept: Day of Honor's grave (it honours those who have passed); A Dangerous Mission's 61 villagers (\"eight "
        "villagers depart\"); a pregnant or nursing villager for Where Are The Infants? (\"the mothers are in a "
        "panic\"); The Ancient Gold Coin's Culture below 2 (wearing it raises Culture); The Cursed Idol's 250 food "
        "(the offering takes it); The Spyglass as in the normal game (keeping it sets Exploration 2); a girl or "
        "woman of 14 or more for Prettiest Tribe Girl; a child for For The Birds and The Child Prodigy; a woman and "
        "a man of 18 or more for The Love Note; The Crystal Ball's villager of 14 or more (Fix Vanilla Bugs owns "
        "those bytes); room for The Barrel O` Babies, Old Friends and The Savage Child (it guards the villager table, "
        "so its hut tiers stay with it); the catch-up wait (timing)."),
    3: (", and nothing else: The Secret City keeps no object in its villager table).",
        "Lifted: an island event no longer waits for a villager of 14 or more; \"not the Tribal Chief\" everywhere; "
        "\"adults only\" or \"adults and elders only\" where the story does not need it (The Ghostly Dreams, The "
        "Crystal of Reflections, Bitter Brown Beans, The Ancient Tablet, The Blue Pearl, The Medical Emergency's "
        "healer, the obsidian and amber Mysterious Vials, The Mango and the Papaya, The Mysterious Crate, The Hole "
        "in the Hut); The Tsunami's 2 women, 2 men and 15 puzzles; The Science Fair's 3 children; The Daredevil's 2 "
        "women; The Mysterious Crate's 3 villagers; The Low Tide's 8 villagers; Day of Honor's 2 graves to 1; Nature "
        "1, Magic 1, Science below or above 2 and Medicine 2; the room for The Canoe from the Other Side, The "
        "Crystal of Reflections and Another One of Those Barrels.",
        "Kept: a child for The Science Fair, The Lazy Apprentice and the children's events; The Lazy Apprentice's "
        "teacher with Research 30 (the text's strict master); an adult or elder for the pearl and starfish events "
        "and The Omen in the Clouds; a man of 18 or more and a woman for The Daredevil; a woman and a man of 18 to "
        "49 for The Lovers and a woman of 18 to 49 for Vanity and the Bee and The Noisy Bird; the Tribal Chief for "
        "The Chief's Address; a grave for Day of Honor; the Bee Hive for The Miraculous Bloom and The Hole in the "
        "Hut and the Alchemy Lab for The Blue Pearl (their stories use them); The Ancient Tablet's Alchemy below 3 "
        "(researching it raises Alchemy); the burning fire for The Cold Snap; The Mushroom Celebration's 500th "
        "mushroom; 14 to 17-year-olds and pregnant or nursing women of 18 to 49 are still not picked (the game's "
        "shared picker has no class for them); the catch-up wait (timing)."),
    4: (", bodies and ghosts).",
        "Lifted: Day of Honor's 2 graves to 1; Festival of the Banyan's healthy-tree gate (its text never mentions "
        "the tree's health); the room for the Daredevil Barrel and The Abandoned Infants; The Abandoned Infants' "
        "6 women to 1 and \"not sick\"; \"not pregnant or nursing\" for The Arc of Brilliant Colors, The Sealed Box "
        "and both Innovations; \"not sick\" for The Screaming Baby and both Innovations; the age of 14 for The "
        "Mosquito Larvae, Faces in the Night and The Sealed Box; The Pretty Shell's 2 villagers to 1.",
        "Kept: Festival of the Banyan's 500th mushroom; a grave for Day of Honor; the burning fire for The Cold Snap "
        "(it puts it out); The Stream for the Daredevil Barrel and The Mosquito Larvae, Soap for The Mosquito Larvae "
        "and the Cooking Pit for Innovation in Farming (their stories use them); the tree's state for The State of "
        "the Tree; a child for the children's events and Tough Lessons (with an adult); a pregnant or nursing woman "
        "for The Screaming Baby (\"her baby\"); a woman of 14 or more for The Abandoned Infants (as in the normal "
        "game); 14 or more for both Innovations and The Pretty Shell (adults' work, a parent); the catch-up wait "
        "(timing)."),
    5: (", corpses and Reanimate spirits). Heathens are picked only for their own conversion roles, exactly as in "
        "the normal game -- never in a believer's place. The Guardians of Isola texts are checked too.",
        "Lifted: Day of Honor's 2 graves to 1; the role test on believer picks (the Retired Chief can be picked; "
        "never a Heathen); \"not pregnant or nursing\" for Bed Bugs; the believer's age for Outreach and The "
        "Migrating Fruit Bats; The Advanced Artifacts' Science 2 or more; the Heathen Scientist puzzle for The "
        "Storyteller; the room for the two Barrels, the Chutes and News From Another Tribe (whose newcomer still "
        "needs room to join).",
        "Kept: a grave for Day of Honor; the burning fire for The Cold Snap; the Hydroponic Farm and the Knowing "
        "Totem where the story uses them; Science below 2 for You're Doing It Wrong and below 3 for The Advanced "
        "Artifacts, and Food Mastery below 2 for The Migrating Fruit Bats (the answers raise them); 100 food for "
        "Trick Or Trade (the trade takes it); 18 or more for The Strange Nectar (drinking it sets the age to 16.5); "
        "a believer child for the children's stories; 14 or more for You're Doing It Wrong's teacher; every Heathen "
        "pick exactly as in the normal game; no God Power armed on the pointer (kept for safety); the catch-up wait "
        "(timing)."),
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
