/* The Secret City (VV3): "No Safeguards for Island Events" -- the game's own natural island events.

   SCOPE (the owner, 2026-11-15): villager eligibility for island events only.  Anyone can be picked and any event
   can come at any time, except where the event's own text or outcome would not make sense, or the event names
   someone the village does not have.  Crash / corruption guards stay.  Nothing is stricter than the stock game.
   Each event below was judged by its own popup text (the game's string table at file offset 0xAF6xx: id, name,
   text) and its outcome code.

   Read from the stock "Virtual Villagers - The Secret City.exe" (831,488 bytes; .text raw offset == VA - 0x400000,
   checked).  The selector 0x419B30 asks each of the 57 slots of 0x4B3C78 (filled by 0x418630) its condition
   (vtable [1]) and draws one of those that pass.  Every site's stock bytes were compared with the exe.

   THE PICKERS THE CONDITIONS CALL (none is changed; all are shared with other game code):
     0x45D460(class, sex, excludeChief, &count)  living (+0xE78 > 0), present (+0xF10) villager records only;
        class bit 1 child (< 280 age units), bit 2 adult 360-999 not pregnant or nursing (+0xE8C == 0), bit 4 elder
        (>= 1000).  Class 7 is the widest the picker has.
     0x45E610(skill, minimum, class, sex, excludeChief, &count)  the same, by skill (The Lazy Apprentice's master).
     0x45EF30  the first living, present record with the chief flag (The Chief's Address).
   Per event this table widens a pick by changing that event's own arguments only: excludeChief 1 -> 0, class 2 or
   6 -> 7.  What no argument can reach stays everywhere (KEPT, shared picker): 14-17-year-olds and pregnant or
   nursing women of 18-49 are in no class.  Including them would mean changing the shared picker 0x45D460, which
   also counts the amounts' multiplier m and serves other game code (0x4481DD, 0x4668B1) -- new code, not a byte
   edit.

   INANIMATE OBJECTS.  The Secret City keeps no object in its villager table: its 150 records are created only by
   the new-village set-up (0x427F70, eight calls of 0x45F0B0), births (0x45FF90 -> 0x45F0B0), The Canoe and the
   Barrels (0x45FF50 -> 0x45F0B0) and the copies of The Crystal of Reflections and the amber Mysterious Vial
   (0x45F2D0) -- all villagers.  The island's things (fire pit 0x5946D8, bee hive / honey 0x5945D0, puzzles
   0x594990, trees, the 50-plot graveyard 0x5973F0) are separate objects no picker reads; no site changes that.

   TRIGGER-LEVEL RULES (the scheduler 0x468750, the selector 0x419B30):
     LIFTED  0x468750  the scheduler's draw 0x45C9D0(1) asked for a living villager of 14 or more before any event
                       could come; now 0x45C9D0(0): any living villager.  (The drawn villager is never used
                       afterwards; Story / Cheat Upgrades' wrapper at the call 0x468757 passes the argument on.)
     KEPT    the timer and the delays (island_timer_vv3.inc), the population-above-0 test (0x468743), the catch-up
             wait (the drawn villager's age == processed age, 0x468786: timing), the uniform draw (0x419B7C), the
             rescue rule (0x419B85-0x419BD9).  No once-only or cooldown flags exist (the 'shown' bytes 0x4B3C3C+slot
             are never read) and no "village in trouble" skip.

   EVERY NATURAL EVENT (slot, title):
     1  The Tsunami (0x414AC0)
          LIFTED  0x414AE5 at least 2 living women; 0x414B0F at least 2 men not the chief; 0x414B1E 15 of the 16
                  puzzles solved (the text is about the sea, not the puzzles).
     2, 4, 5, 8-11, 12, 14, 48, 50, 51, 52, 53, 55  (Plague Of Ants, Allergy Season, Isola Day, the four Mysterious
        Fogs, Blessings Day, Reflection in the Water, Rainy Season, Salty Air, Oppressive Humidity, "Thick as Pea
        Soup", Stinging Jellyfish, Yellow Geckos)  no condition (0x403390 returns 1).
     3  The Science Fair (0x414BC0)
          LIFTED  0x414BDE 3 children -> 1.   KEPT  a child ("the children spend the day ... their own experiments").
     6  Day of Honor (0x414FC0)
          LIFTED  0x414FCA 2 graves -> 1.   KEPT  1 grave ("pay their respects to those who have passed on").
     7  The Canoe from the Other Side (0x414D80)
          LIFTED  0x414D85 the room check 0x45FE30 (population cap and rebuilt huts) -- always passes now.
          KEPT (crash / corruption guard)  the villager table's 150 records: the creator 0x45F0B0 returns -1 when
                  all are in use and the apply skips it (0x45EE60 at 0x414DBC); the patcher's safety patch at
                  0x414D90 rechecks first.  The stock rescue rule already runs this event without its room check.
     13 The Miraculous Bloom (0x415030)   KEPT  The Bee Hive puzzle: the text's bees make the honey, the outcome
                                                sets the hive's honey.
     15 The Daredevil (0x415420)
          LIFTED  0x415465 2 women -> 1.
          KEPT  a man of 18+ ("he", showing off, "popular with the tribe's women"); at least one woman of 18+ ("a
                  crowd of village women gathers").
     16 The Ghostly Dream, nature or healing (0x4154F0)
          LIFTED  0x4154F3 not the chief; 0x4154F9 adults / elders only (now children too); 0x415520 Nature level 1
                  or more (the outcome gives a skill, not a technology).
     17 The Ghostly Dream, research or architecture (0x415630)
          LIFTED  0x415633 not the chief; 0x415639 adults / elders only; 0x415660 Magic level 1 or more.
     18 The Crystal of Reflections (0x415750)
          LIFTED  0x415759 adults / elders only (a child may find the crystal and be copied); 0x415775 the room
                  check 0x45FE30.
          KEPT (crash / corruption guard)  the table size: the copier 0x45F2D0 returns -1 with no free record and
                  the keep effect checks it (0x419240); the patcher's safety patch at 0x4191EF too.
     19 The Bitter Brown Beans, taste or dye, and 21 The Ancient Tablet, laundry or decoration (0x4157E0, shared)
          LIFTED  0x4157E9 adults 18-49 only (now children and elders); 0x415800 Science below level 2 (no answer
                  raises Science).  The site ends before 0x41580C, where the patcher's safety patch jumps.
     20 The Bitter Brown Beans, brew or fertilizer (0x4159B0)
          LIFTED  0x4159B9 adults 18-49 only; 0x4159DF Science level 2 or more.
     22 The Ancient Tablet, research or display (0x415C40)
          LIFTED  0x415C49 adults / elders only; 0x415C82 Science level 2 or more ("display" gives Research skill).
          KEPT  Alchemy below level 3 -- "Focus research on tablet" raises Alchemy a level.
     23 The Low Tide (0x415DB0)
          LIFTED  0x415DCB not the chief; 0x415DEA at least 8 villagers.   (Stock already picks any villager.)
     24 The Ants and the Granary, 29 The Playful Otters, 30 The Ant Hill, 46 The Shooting Star (0x416A10, shared)
          LIFTED  0x416A13 not the chief.
          KEPT  a child: "the children spot ... otters", "Little {name}" (Ant Hill, Shooting Star -- "when he grows
                  up"); the four share one condition.
     25 The Green Pearl, 31 The Red Starfish, 32 The Blue Starfish, 33 Bed Bugs, 45 The Royal Jelly (0x416CD0)
          LIFTED  0x416CD3 not the chief.
          KEPT  an adult or elder: The Green Pearl's bracelet makes the wearer "popular with the other adults, as
                  well as with the children"; the five share one condition.
     26 The Blue Pearl (0x416270)
          LIFTED  0x416279 adults / elders only.
          KEPT  The Alchemy Lab puzzle: both answers take the pearl to the lab, marks "correspond to alchemy herbs".
     27 The Lazy Apprentice (0x4163B0)
          LIFTED  0x4163B4 the apprentice not the chief.
          KEPT  a child ("Little {name} is an apprentice"); a master of 18+ with Research 30 or more (the text names
                  the master, "the strict teacher").
     28 The Omen in the Clouds (0x416550)
          LIFTED  0x416553 not the chief.
          KEPT  an adult or elder ("a reputation among the villagers for being level headed ... wise counsel").
     34 / 35 The Lovers, her gift / his gift (0x416ED0 / 0x417050)
          LIFTED  0x416ED3, 0x416EF2, 0x417053, 0x417072 either partner not the chief.
          KEPT  a woman and a man of 18-49, the woman not pregnant or nursing (a crush, courting, a romance; the
                  knife and the flowers start a pregnancy).
     36 The Medical Emergency (0x4171D0)
          LIFTED  0x4171D3 the patient not the chief; 0x4171F2 the healer not the chief; 0x4171F6 the healer adults /
                  elders only (the text names no healer -- "the villagers" do it -- and the outcome never reads
                  that pick); 0x417218 Medicine level 2 or more (no answer raises Medicine).
     37 The Mysterious Vial, quartz (0x417390)   Stock already picks any villager; its fixed ages (a child becomes
                                                 50, anyone older becomes 10) fit everyone it can pick.
     38 / 39 The Mysterious Vial, obsidian / amber (0x417590, shared)
          LIFTED  0x417599 adults / elders only.  (Amber's "years younger" lowers the age by 100 units, never below
                  100 -- it never makes anyone older.)
     40 The Mango and the Papaya (0x4178B0)   LIFTED  0x4178CB adults 18-49 only.
     41 The Mysterious Crate (0x417A80)       LIFTED  0x417A8D adults 18-49 only; 0x417AA4 3 villagers -> 1.
     42 Vanity and the Bee, 43 The Noisy Bird (0x417D10, shared)
          LIFTED  0x417D13 not the chief.
          KEPT  a woman of 18-49: Vanity's "lovely young woman ... her glorious hair"; the two share one condition.
     44 The Hole in the Hut (0x417F30)
          LIFTED  0x417F33 not the chief; 0x417F39 adults 18-49 only.
          KEPT  The Bee Hive puzzle: the beeswax answer takes honeycomb from the hive.
     47 The Chief's Address (0x415090)   KEPT  a living Tribal Chief: the text names "the tribal chief".
     49 The Cold Snap (0x415100)          KEPT  the fire burning: "the villagers huddle around the fire".
     54 The Mushroom Celebration (0x415290)   KEPT  500 items brought home: "celebrate collecting their 500th
                                              mushroom".
     56 The Return of Biggles (0x4182F0)   LIFTED  0x4182F3 not the chief.
     57 Another One of Those Barrels (0x415310)
          LIFTED  0x415315 the room check.
          KEPT (crash / corruption guard)  the table size: the first child's creator returns -1 when full; the
                  second and third children keep the apply's own room checks; the safety patch at 0x415320.
     Never offered (no slot): The Swarm of Bees, The Drought -- strings only.

   NOTE (not changed here): two of the patcher's VV3 safety patches in data\builds.json (and the same rows in
   data\vv3_population_256_feature.json) land on the wrong condition -- 0x1580C "The Crystal of Reflections is
   offered only with room" patches The Bitter Brown Beans / The Ancient Tablet condition 0x4157E0, and 0x178DA "The
   Mysterious Vial is offered only with room for its two copies" patches The Mango and the Papaya condition 0x4178B0
   (the vials' condition 0x417590 has the same bytes at 0x4175A5).  No site below overlaps them.

   COLLISIONS CHECKED: every site and 12 bytes around it against native\ and data\*.json.  No overlap.  Near, not
   overlapping: Story / Cheat Upgrades' detours on the picker calls (0x415500, 0x415640, 0x415760, 0x4157F0,
   0x416280, 0x4163C1, 0x416560, 0x416A20, 0x416CE0, 0x416EE0, 0x416EFD, 0x417060, 0x41707D, 0x4171E0, 0x4175A0,
   0x4178D5, 0x417A9C, 0x417D20, 0x417F40, 0x418300) and on 0x468757; population 256's "mov ecx, 0x59E110"
   rewrites (0x414D80, 0x415310, 0x415770, 0x4154FB, 0x41563B, 0x41575B, 0x4157EB, 0x4159BB, 0x415C4B, 0x41627B,
   0x4171F8, 0x41759B, 0x4178D0, 0x417A8F, 0x417F3B, 0x468752) -- so the room-check sites take the call / jmp
   after the mov; the safety patches at 0x414D90, 0x415320, 0x41580C. */

static const ns_site NS_VV3_SITES[] = {
    /* 1 The Tsunami: 2 women (jge -> jmp), 2 men not the chief (jl -> nops), 15 puzzles (setge al -> mov al, 1) */
    { 0x414AE5u, 2, { 0x7D, 0x06 }, { 0xEB, 0x06 } },
    { 0x414B0Fu, 2, { 0x7C, 0xD6 }, { 0x90, 0x90 } },
    { 0x414B1Eu, 3, { 0x0F, 0x9D, 0xC0 }, { 0xB0, 0x01, 0x90 } },
    /* 3 The Science Fair: cmp [esp], 3 -> cmp [esp], 1 */
    { 0x414BDEu, 5, { 0x83, 0x7C, 0x24, 0x00, 0x03 }, { 0x83, 0x7C, 0x24, 0x00, 0x01 } },
    /* 7 The Canoe: call 0x45FE30 -> mov al, 1 (+ nops); test al, al / setne al follow */
    { 0x414D85u, 5, { 0xE8, 0xA6, 0xB0, 0x04, 0x00 }, { 0xB0, 0x01, 0x90, 0x90, 0x90 } },
    /* 6 Day of Honor: cmp eax, 2 -> cmp eax, 1 */
    { 0x414FCAu, 3, { 0x83, 0xF8, 0x02 }, { 0x83, 0xF8, 0x01 } },
    /* 57 Another One of Those Barrels: jmp 0x45FE30 -> mov al, 1 / ret */
    { 0x415315u, 5, { 0xE9, 0x16, 0xAB, 0x04, 0x00 }, { 0xB0, 0x01, 0xC3, 0x90, 0x90 } },
    /* 15 The Daredevil: cmp ecx, 1 / setg -> cmp ecx, 0 / setg (1 woman) */
    { 0x415465u, 3, { 0x83, 0xF9, 0x01 }, { 0x83, 0xF9, 0x00 } },
    /* 16 The Ghostly Dream (nature): not the chief; class 6 -> 7; Nature >= 1 (setg cl -> mov cl, 1) */
    { 0x4154F3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x4154F9u, 2, { 0x6A, 0x06 }, { 0x6A, 0x07 } },
    { 0x415520u, 3, { 0x0F, 0x9F, 0xC1 }, { 0xB1, 0x01, 0x90 } },
    /* 17 The Ghostly Dream (magic): not the chief; class 6 -> 7; Magic >= 1 */
    { 0x415633u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x415639u, 2, { 0x6A, 0x06 }, { 0x6A, 0x07 } },
    { 0x415660u, 3, { 0x0F, 0x9F, 0xC1 }, { 0xB1, 0x01, 0x90 } },
    /* 18 The Crystal of Reflections: class 6 -> 7; jmp 0x45FE30 -> mov al, 1 / ret */
    { 0x415759u, 2, { 0x6A, 0x06 }, { 0x6A, 0x07 } },
    { 0x415775u, 5, { 0xE9, 0xB6, 0xA6, 0x04, 0x00 }, { 0xB0, 0x01, 0xC3, 0x90, 0x90 } },
    /* 19 / 21 Beans (taste or dye), Tablet (laundry or decoration): class 2 -> 7; Science < 2 -- the level read
       (push 0 / mov ecx, 0x582618 / call 0x426FC0, ret 4) -> xor eax, eax + 10 nops */
    { 0x4157E9u, 2, { 0x6A, 0x02 }, { 0x6A, 0x07 } },
    { 0x415800u, 12, { 0x6A, 0x00, 0xB9, 0x18, 0x26, 0x58, 0x00, 0xE8, 0xB4, 0x17, 0x01, 0x00 },
                     { 0x33, 0xC0, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 } },
    /* 20 Beans (brew or fertilizer): class 2 -> 7; Science > 1 (setg al -> mov al, 1) */
    { 0x4159B9u, 2, { 0x6A, 0x02 }, { 0x6A, 0x07 } },
    { 0x4159DFu, 3, { 0x0F, 0x9F, 0xC0 }, { 0xB0, 0x01, 0x90 } },
    /* 22 Tablet (research or display): class 6 -> 7; Science >= 2 (setge cl -> mov cl, 1); Alchemy < 3 stays */
    { 0x415C49u, 2, { 0x6A, 0x06 }, { 0x6A, 0x07 } },
    { 0x415C82u, 3, { 0x0F, 0x9D, 0xC1 }, { 0xB1, 0x01, 0x90 } },
    /* 23 The Low Tide: not the chief; cmp [esp], 8 -> cmp [esp], 0 */
    { 0x415DCBu, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x415DEAu, 5, { 0x83, 0x7C, 0x24, 0x00, 0x08 }, { 0x83, 0x7C, 0x24, 0x00, 0x00 } },
    /* 26 The Blue Pearl: class 6 -> 7 */
    { 0x416279u, 2, { 0x6A, 0x06 }, { 0x6A, 0x07 } },
    /* 27 The Lazy Apprentice: the child not the chief */
    { 0x4163B4u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 28 The Omen in the Clouds: not the chief */
    { 0x416553u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 24 / 29 / 30 / 46 the children's events: not the chief */
    { 0x416A13u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 25 / 31 / 32 / 33 / 45 the adults' events: not the chief */
    { 0x416CD3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 34 The Lovers (her gift): the woman, the man not the chief */
    { 0x416ED3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x416EF2u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 35 The Lovers (his gift): the man, the woman not the chief */
    { 0x417053u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x417072u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 36 The Medical Emergency: patient, healer not the chief; healer class 6 -> 7; Medicine >= 2 */
    { 0x4171D3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x4171F2u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x4171F6u, 2, { 0x6A, 0x06 }, { 0x6A, 0x07 } },
    { 0x417218u, 3, { 0x0F, 0x9D, 0xC0 }, { 0xB0, 0x01, 0x90 } },
    /* 38 / 39 The Mysterious Vial (obsidian, amber): class 6 -> 7 */
    { 0x417599u, 2, { 0x6A, 0x06 }, { 0x6A, 0x07 } },
    /* 40 The Mango and the Papaya: class 2 -> 7 */
    { 0x4178CBu, 2, { 0x6A, 0x02 }, { 0x6A, 0x07 } },
    /* 41 The Mysterious Crate: class 2 -> 7; cmp [esp+4], 3 -> cmp [esp+4], 1 */
    { 0x417A8Du, 2, { 0x6A, 0x02 }, { 0x6A, 0x07 } },
    { 0x417AA4u, 5, { 0x83, 0x7C, 0x24, 0x04, 0x03 }, { 0x83, 0x7C, 0x24, 0x04, 0x01 } },
    /* 42 / 43 Vanity and the Bee, The Noisy Bird: not the chief */
    { 0x417D13u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 44 The Hole in the Hut: not the chief; class 2 -> 7 */
    { 0x417F33u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x417F39u, 2, { 0x6A, 0x02 }, { 0x6A, 0x07 } },
    /* 56 The Return of Biggles: not the chief */
    { 0x4182F3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* the scheduler: a living villager of any age, not only 14+ (push 1 -> push 0) */
    { 0x468750u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
};

#define NS_VV3_COUNT (sizeof NS_VV3_SITES / sizeof NS_VV3_SITES[0])
