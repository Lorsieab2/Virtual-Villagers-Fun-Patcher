# No Safeguards for Island Events -- the games' own events

"No Safeguards for Island Events (and Additional Events too)" (`vvN_island_events_any_time`). The owner's final
scope (2026-11-15): "ONLY APPLIES TO VILLAGER ELIGIBILITY PICKING FOR ISLAND EVENTS. ANYONE CAN BE PICKED AT ANY TIME,
ANY EVENT CAN BE PICKED AT ANY TIME, EXCEPT: when it doesn't make sense within the event's text or context ..., or the
event mentions someone the village doesn't have." Nothing is stricter than in the normal game. Heathens are picked
only for their own conversion roles; The Lost Children's totems and anything else that is not a living villager are
never picked.

The patcher ships `VVFP No Safeguards.dll` (`native/vvfp_no_safeguards`) with the row; it writes its sites at start
only when every site holds its stock bytes (all or none) and the installed-patches list names the row. Each site,
with its address, stock bytes and reason, is in `native/vvfp_no_safeguards/ns_vvN.inc`; the Game Mechanics page
shows the same lists (`src/vv_game_mechanics_no_safeguards.py`). Static analysis of the stock executables and the
events' own text; not yet seen in a running game.

Unchanged in every game: the timer and the delays, which event is chosen among those that can come, the first-event
rules, the rescue rule, and the catch-up wait. Kept for safety in every game: no villager is made past the villager
table's real size.

## A New Home -- 2 sites
- Lifted: island events no longer wait for a villager of 14 or more; The Barrel O\` Babies' room (population cap,
  huts at 15/25/50).
- Kept: Locusts' Farming 2 (crops are food only from Farming 2); Trapped Whale's Spirituality < 3 and Visitor's
  Medicine < 3 (the answers raise them); The Big Wave's cleaned beach (the wave covers it again); a child for
  Measles, The Troubled Child, The Suspicious Monkey; a living villager for every encounter and crate.

## The Lost Children -- 5 sites
- Lifted: the 14+ villager wait; all 16 puzzles for The Epidemic, Rats!, The Foul Passing, Where Are The Infants?
  (their texts never mention puzzles); the Infants' mother's 18+; The Silver Mirror's 2 villagers.
- Kept: Day of Honor's grave; A Dangerous Mission's 61 ("eight villagers depart"); a pregnant or nursing villager
  for the Infants ("the mothers are in a panic"); Gold Coin's Culture < 2 (raised by wearing it); Cursed Idol's 250
  food (the offering takes it); The Spyglass fully vanilla; a female 14+ for Prettiest Tribe Girl; a child for For
  The Birds and The Child Prodigy; a woman and a man 18+ for The Love Note; Crystal Ball's 14+ (Fix Vanilla Bugs'
  bytes); room for Barrel O\` Babies, Old Friends, Savage Child (it guards the villager table; its hut tiers stay
  with it). Totems: every picker and loop the sites reach needs a record in use and alive -- no totem.

## The Secret City -- 46 sites
- Lifted: the 14+ villager wait; "not the Tribal Chief" everywhere; "adults only" picks where the story does not need
  them (Ghostly Dreams, Crystal of Reflections, Bitter Brown Beans, Ancient Tablet, Blue Pearl, Medical Emergency's
  healer, obsidian/amber Vials, Mango and the Papaya, Mysterious Crate, Hole in the Hut); The Tsunami's 2 women, 2 men
  and 15 puzzles; Science Fair's 3 children; Daredevil's 2 women; Mysterious Crate's 3; Low Tide's 8; Day of Honor
  2 graves to 1; Nature 1, Magic 1, Science < or >= 2, Medicine 2; room for the Canoe, the Crystal and the Barrels.
- Kept: a child for the children's events; Lazy Apprentice's teacher with Research 30; an adult or elder for the
  pearl/starfish events and The Omen; a man 18+ and a woman for The Daredevil; the Lovers' adults; a woman 18-49 for
  Vanity and the Bee / The Noisy Bird; the Chief for The Chief's Address; a grave; Bee Hive and Alchemy Lab where the
  story uses them; Ancient Tablet's Alchemy < 3 (raised by research); Cold Snap's fire; Mushroom Celebration's 500th
  mushroom; 14-17-year-olds and pregnant/nursing women 18-49 still unpicked (no class for them in the shared picker).

## The Tree of Life -- 17 sites
- Lifted: Day of Honor 2 graves to 1; Festival of the Banyan's healthy-tree gate; room for the Daredevil Barrel and
  The Abandoned Infants; the Infants' 6 women to 1 and "not sick"; "not pregnant or nursing" (Arc, Sealed Box,
  Innovations); "not sick" (Screaming Baby, Innovations); the 14+ for Mosquito Larvae, Faces in the Night, Sealed Box;
  Pretty Shell's 2 to 1.
- Kept: Festival's 500th mushroom; a grave; Cold Snap's fire; The Stream, Soap, the Cooking Pit where the story uses
  them; the tree's state for The State of the Tree; a child for the children's events and Tough Lessons; a pregnant
  or nursing woman for The Screaming Baby; a woman 14+ for The Abandoned Infants (stock); 14+ for the Innovations and
  Pretty Shell.

## New Believers -- 22 sites
- Lifted: Day of Honor 2 graves to 1; the role test on believer picks (the Retired Chief; the picker's own Heathen
  test still skips every Heathen); Bed Bugs' "not pregnant or nursing"; Outreach's and the Fruit Bats' believer age;
  Advanced Artifacts' Science >= 2; The Storyteller's Heathen Scientist puzzle; room for the Barrels, the Chutes and
  News From Another Tribe (its newcomer still needs room to join).
- Kept: a grave; Cold Snap's fire; Hydroponic Farm and Knowing Totem where the story uses them; Science < 2 (You're
  Doing It Wrong), Science < 3 (Advanced Artifacts), Food Mastery < 2 (Fruit Bats) -- the answers raise them; Trick Or
  Trade's 100 food (the trade takes it); Strange Nectar's 18+ (it sets the age to 16.5); a believer child for the
  children's stories; 14+ for You're Doing It Wrong's teacher; every Heathen pick exactly as stock; no God Power armed
  (safety). Checked against both the stock and the Guardians of Isola texts (that row writes no exe bytes).

## Found, not changed
Two VV3 safety patches (`data/builds.json`, repeated in `data/vv3_population_256_feature.json`) are labelled for the
wrong event: 0x1580C ("The Crystal of Reflections") patches the Bitter Brown Beans / Ancient Tablet condition, and
0x178DA ("The Mysterious Vial") patches The Mango and the Papaya condition.
