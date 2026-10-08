# Rules for working on the Virtual Villagers Fun Patcher

## Never forget the special gameplay mechanics

The owner, 2026-10-08:

> NEVER EVER EVER FORGET TO ACCOUNT FOR CORE GAMEPLAY MECHANICS THAT DO NOT FOLLOW THE TYPICAL RULES OF THINGS.

What happened: A New Home's birth logging hooked only the pregnancy tick's child-creation calls. The Golden Child
puzzle (0x4242F8) makes a child from a pregnant mother outside that tick, so it was never logged as a Birth. It was
later recorded as a parentless "Arrived" villager and given no last name. Fixed in v1.35.63-v3 (PR #571).

Whenever a change classifies or counts villagers (births, arrivals, founders, deaths, names, statistics, logs):

- Find **every** call site of the routine that creates (or kills, or renames) a villager, in **every** game. Never
  stop at the common path.
- Before calling it done, name each special mechanic and say whether the change covers it:
  - A New Home: the Golden Child (the puzzle, and a golden-child mother's extra child), Barrel of Babies, the
    Mysterious Crate, the Mysterious Face.
  - The Lost Children: Barrel of Babies, Old Friends, the Savage Child, the Strange Request, the Silver Mirror.
  - The Secret City: the canoe, the barrels, the Crystal of Reflections and the amber vial (copies), Tribal Chiefs.
  - The Tree of Life: the canoe, Barrel of Babies, the adoption scene, the ghosts, Abandoned Infants.
  - New Believers: Barrel O' Babies, Chutes Without Ladders, News From Another Tribe, Heathens and their conversion,
    Reanimate, Abandoned Infants.
  - Every game: founders and Start Over, Time Warp and the load-time catch-up (where most births happen), the Custom
    Island Event and the Story / Cheat Upgrades' villagers, twins and triplets.
