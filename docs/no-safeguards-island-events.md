# No Safeguards for Island Events -- the games' own events

"No Safeguards for Island Events (and Additional Events too)" (`vvN_island_events_any_time`, the owner, 2026-11-15)
makes the games' OWN natural island events ignore every condition except what an event needs to happen or make
sense. The patcher ships `VVFP No Safeguards.dll` (`native/vvfp_no_safeguards`) with the row; it writes its sites
at start only when every site holds its stock bytes (all or none) and the installed-patches list names the row.
Each site, with its address and stock bytes, is in `native/vvfp_no_safeguards/ns_vvN.inc`. Static analysis of the
stock executables; not yet seen in a running game.

Unchanged in every game: the timer and the delays, which event is chosen among those that can happen (family
weights, case rolls), the first-event rules and the rescue rule. Kept for safety in every game: no villager is
made past the villager table's real size (the game's makers refuse; the patcher's record guards stay).

| Game | Sites | Lifted | Kept: casting | Kept: puzzle / sense | Kept for safety | Always protected (not living villagers) |
|---|---|---|---|---|---|---|
| A New Home | 5 | Trigger's villager of 14+; Locusts' Farming 2; Barrel O\` Babies' room (cap, huts at 15/25/50); Trapped Whale's Spirituality < 3; Visitor's Medicine < 3 | a child for Measles, Troubled Child, Suspicious Monkey; a living subject for encounters and crates | Big Wave: beach clean-up solved; village not empty; catch-up wait | the 256-record table (record guards) | the dead / bodies (no object records) |
| The Lost Children | 5 | Trigger's villager of 14+; Dangerous Mission's > 60 villagers; Gold Coin's Culture < 2; Cursed Idol's 250 food; Silver Mirror's 2 villagers (The Spyglass as stock) | a child (For The Birds, Child Prodigy); a woman 14+ (Prettiest Tribe Girl); a woman and a man 18+ (Love Note); a pregnant/nursing villager 18+ (Where Are The Infants?) | someone in the memorial (Day of Honor); all 16 puzzles (Epidemic, Rats!, Foul Passing, Infants) | room for Barrel O\` Babies, Old Friends, Savage Child (the check guards the table; its hut tiers stay with it); Crystal Ball's 14+ (Fix Vanilla Bugs' bytes) | totem statues; the dead |
| The Secret City | 35 | Trigger's villager of 14+; "not the chief" everywhere; head-counts (Tsunami, Science Fair, Daredevil, Mysterious Crate, Low Tide, Day of Honor 2 to 1); technology levels; room for Canoe, Crystal, Barrels; Mushroom Celebration's 500 items | the picker's classes (child < 14, adult 18-49 not pregnant/nursing, elder 50+); Lazy Apprentice's teacher (Research 30); the Chief for Chief's Address | Tsunami 15 of 16 puzzles; Bee Hive; Alchemy Lab; Cold Snap's burning fire; catch-up wait | the 150-record table | the dead (no object records) |
| The Tree of Life | 14 | Day of Honor 2 graves to 1; not pregnant/nursing (Arc, Sealed Box, Innovations); not sick (Abandoned Infants, Screaming Baby, Innovations); Infants' 6 women to 1 and room; Daredevil Barrel's room; Banyan's 500 deliveries; Pretty Shell's 2 to 1 | a child; a villager 14+; a pregnant/nursing woman; a woman 14+ for the Infants (as stock) | tree puzzles; The Stream; Soap; Cooking Pit; Cold Snap's fire; village not empty; catch-up wait | the 150-record table | bodies and ghosts |
| New Believers | 30 | Day of Honor 2 to 1; believer picks' role test; not sick (Heathen children, Outreach, Defector); Bed Bugs' not pregnant/nursing; Science < 2 / exactly 2; Trick Or Trade's 100 food; Fruit Bats' Food Mastery < 2; room (4 events); Strange Nectar's 18 (any age; to be checked live) | each event's believer or Heathen (and believer child) | Heathen role characters; Hydroponic Farm; Knowing Totem; Heathen Scientist; Cold Snap's fire; catch-up wait | the 150-record table; no God Power armed | corpses and Reanimate spirits; the dead |

Nothing is stricter than in the normal game (the owner, 2026-11-15). Owner decisions open (kept for now): the "all puzzles solved" progression gates (The Lost Children's four events,
The Secret City's Tsunami), The Lazy Apprentice's Research 30, The Cold Snap's burning fire, and New Believers' News
From Another Tribe (its own effect still checks room; it shares one condition with three other events).
