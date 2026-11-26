# Heathen Tribe Expansion and Evolution -- the owner's decisions (2026-11-26)

These settle the 18 questions in `heathen-tribe-expansion-design.md` section 2. Where the owner changed a
recommendation, the owner's words are quoted. Everything not changed is the design's recommendation. Ships in
v1.35.101 ("everything waits in one release"). Default: OFF in Default Patches and Select All, **ON in Owner's
Defaults** (owner: "the heathen expansion = default on in owners defaults").

Owner's standing rules that apply: villagers are villagers regardless of gender (no sex gate on anything but
conception itself); the logs record Heathens too; Heathens never count in the Village Statistics; when Heathens
die with skeletons they go in the mud hut memorial, only if their faction is Heathen.

| # | Decision |
|---|---|
| 1 | Births and arrivals run at the slider rates before The Last Heathen; the row text says in bold that a growing camp makes The Last Heathen harder or impossible to reach. |
| 2 | Births continue after The Last Heathen while a Heathen woman and man are alive. |
| 3 | Births slider 0.1-10x, 1x everywhere. Arrivals slider 0-10x: 0 (off) in Default Patches, 1x in Owner's Defaults. |
| 4 | 1x arrivals = one arrival (a single Heathen or a group) about every 48 real hours on Normal (480 units). |
| 5 | Groups of 1 to 4, sometimes a couple with 0-2 children. |
| 6 | New Chief / Masters: the real role 13-16 while that puzzle is unsolved (today's rule) or after The Last Heathen; otherwise cosmetic (the role's skills, a custom title, its mask). |
| 7 | **Changed.** Owner: "preferably blue ones. red and orange ones should be much fewer." Arrivals and newborns are mostly blue: 90% blue, 7% orange, 3% red (a newborn too, not its parent's colour). The puzzle roles keep their own masks. |
| 8 | **Changed.** Owner: "i want doctor heathens to heal sick ones (besides the puzzle one)". Heathens fall sick; ordinary Heathens with healing skill act as the camp's doctors and heal sick Heathens (as the believers' healers do; the puzzle Heathen Doctor, role 12, is not one of them). A sick Heathen never dies of it and never looks near death (health floor 21). Heathen cures never count in People Cured. With no Heathen able to heal, they get well on their own. |
| 9 | **Changed.** Owner: "heathens can "harvest" fish crops or noni after their puzzles are solved. they never deplete their resources in reality and walk to the encampment instead of the granary." Each show-harvest is available to Heathens only once the puzzle that opens that source for the believers is solved; it never takes from any source (no counter, no food) and they carry it to the encampment, not the granary. The stock Heathens' noni eating (vanilla) is left alone. |
| 10 | **Changed.** Owner: "they can also use the science lab etc." Facilities, all for show and never changing the believers' state: the spa, the statue / Believer Idol, the nursery, the Love Shack door (no embrace), the farm plots, **the science lab**, and the game's other facilities where the same show-only use is safe (each listed in the row text). |
| 11 | **Changed.** Owner: "heathens should bury heathens (believers can be a fallback)". Heathens carry a Heathen body to the mud hut and bury it there; if no Heathen can, believers do it (after the Buried Mausoleum as today), still into the mud hut. |
| 12 | Heathen graves already in the believers' Roster of the Dead stay where they are (still never counted). |
| 13 | The Heathen Mausoleum Screen reuses the game's Mausoleum art unchanged. |
| 14 | With the row on, every Heathen leaves a skeleton, former villagers included. **Owner: "former villagers still in the heathens when they die can go in the mud hut. when converted they go in the normal mausoleum."** -- decided by the faction at death. The mud-hut memorial also works when only "Former Villagers Among the Heathens Leave Skeletons" is on. |
| 15 | Former villagers among the Heathens pair too; couples stay together until one dies or converts; half-siblings are never paired. |
| 16 | New log records "Couple formed" and "Took the role" (new exports WriteParentageHeathenCouple, VvfpCauseHeathenRole). |
| 17 | A Heathen keeps its grown skills when it converts. |
| 18 | Heathens never take a record the believers could still need (10 free + the believers' remaining room); no extra fixed cap. Read the 256 build's believer cap from that exe. |

Also in scope: the Heathen tribe conception-log bug (forced conceptions skip the parentage hook) is fixed and
checked live.

## Second round (2026-11-26), the builders' questions

Core (W-A):
- A regrown camp after The Last Heathen gets a new Chief and Masters once it has 6 adults (eldest suitable; real roles).
- **Owner: "for show masters = purple masks (no puzzles)".** For-show Masters wear the purple mask, no puzzle.
- **Owner: "for show chief can be at most an esteemed elder. he can still do chief exclusve actions like spreading the word etc".** A for-show Chief's title tops out at Esteemed Elder; he can still do the Chief-exclusive actions such as Spreading the Word.
- **Owner: "chief = he or she after the first one".** The original Heathen Chief is as the game makes him; every later Chief (and Master) can be any sex.
- **Owner: "same sex yes, events may give them babies too".** Couples of any sex; natural conception stays woman + man; island events and Custom Island Events can give any couple a baby.
- Groups 1/2/3/4 at 40/30/20/10%, adults 18-40, children 2-12; couples pair gradually (no log flood on install).
- **Owner: "they should grow normally. (anyway we're gonna convert everyone so no point restricting)".** Decision 18 changed: no believers'-room reservation; Heathens grow normally in every population mode; only 10 records are kept free.
- An unreadable couples file pauses that village's couples, births and arrivals (with a log note).

Mausoleum (W-C), all as recommended:
- Believers take a Heathen's body after 120 units, or at once when no able Heathen lives.
- Heathens bury half the times asked; never puzzle Heathens, children, the sick or the expecting.
- A drop on the hut opens the Heathen Mausoleum Screen; the hut opens once it holds a grave.
- Heathen buriers also run with only "Former Villagers Among the Heathens Leave Skeletons".
- With the Guardians of Isola rewrite: "the encampment memorial" instead of "the mud hut memorial".
- The hut's file follows the main save only.
