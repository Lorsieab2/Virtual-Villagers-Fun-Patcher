/* The Secret City (VV3): "No Safeguards for Island Events" -- the game's own natural island events.

   Read from the stock "Virtual Villagers - The Secret City.exe" (831,488 bytes; .text raw offset == VA - 0x400000,
   checked).  The selector 0x419B30 asks each of the 57 slots of 0x4B3C78 (filled by 0x418630) its condition
   (vtable [1]) and draws one of those that pass.  Every condition below was disassembled; every site's stock bytes
   were compared with the exe.

   THE PICKERS THE CONDITIONS CALL (none is changed; all are shared with other game code):
     0x45D460(class, sex, excludeChief, &count)  living (+0xE78 > 0), present (+0xF10) villager records only;
        class bit 1 child (< 280 age units), bit 2 adult 360-999 not pregnant or nursing (+0xE8C == 0), bit 4 elder
        (>= 1000); so class 7 never draws a 14-17-year-old and classes 2 / 6 never draw a pregnant or nursing woman
        of 18-49.  excludeChief (the third argument) skips the Tribal Chief (+0xE80).
     0x45E610(skill, minimum, class, sex, excludeChief, &count)  the same, by skill (The Lazy Apprentice's teacher).
     0x45EF30  the first living, present record with the chief flag (The Chief's Address).
   Lifting "not the chief" is done by pushing 0 instead of 1 as the third argument -- the picker, its classes and
   its counts are untouched.  The age classes and the pregnant / nursing exclusion live inside the shared picker
   (also the amounts' multiplier m and other game code: 0x4481DD, 0x4668B1), and no class value means "adults
   including pregnant women", so they stay (KEPT, casting): an adult's event still casts an adult, a child's event
   a child.

   INANIMATE OBJECTS.  The Secret City keeps no object in its villager table: the table's 150 records are created
   only by the new-village set-up (0x427F70, eight calls of 0x45F0B0), births (0x45FF90 -> 0x45F0B0), The Canoe and
   the Barrels (0x45FF50 -> 0x45F0B0) and the copies of The Crystal of Reflections and the amber Mysterious Vial
   (0x45F2D0) -- all villagers.  The island's things (the fire pit 0x5946D8, the bee hive / honey 0x5945D0, the
   puzzles 0x594990, the trees, the 50-plot graveyard 0x5973F0) are separate objects that no picker reads, so no
   event can cast one, and no site below changes that.  (There is nothing like The Lost Children's totems here.)

   TRIGGER-LEVEL RULES (the scheduler 0x468750, the selector 0x419B30):
     LIFTED  0x468750  the scheduler's draw 0x45C9D0(1) asked for a living villager of 14 or more before any event
                       could come; now 0x45C9D0(0): any living villager.  (The drawn villager is never used
                       afterwards; Story / Cheat Upgrades' wrapper at the call 0x468757 passes the argument on.)
     KEPT    the timer and the delay (manager+0x12EF4; 15 minutes, 30 minutes after the first ever, then 8-15
             hours; island_timer_vv3.inc), the population-above-0 test (0x468743), the drawn villager's age ==
             processed age test (0x468786; a timing wait, not a condition of any event), the uniform draw among the
             passing slots (0x419B7C), the rescue rule (0x419B85-0x419BD9, still forcing slots 18 / 7 / 57 at 15%).
             There are no once-only or cooldown flags (the 'shown' bytes 0x4B3C3C+slot are written, never read) and
             no "village in trouble" skip in this game.

   EVERY NATURAL EVENT (slot, title):
     1  The Tsunami (0x414AC0)
          LIFTED  0x414AE5 at least 2 living women; 0x414B0F at least 2 living men who are not the chief.
          KEPT (puzzle)  15 of the 16 puzzles solved (0x435920 >= 15 at 0x414B1B) -- a puzzle-progress condition.
     2  The Plague Of Ants, 4 The Allergy Season, 5 Isola Day Celebration, 8-11 The Mysterious Fog (food gained,
        food lost, tech gained, tech lost), 12 Blessings Day Celebration, 14 The Reflection in the Water,
        48 The Rainy Season, 50 The Salty Air, 51 The Oppressive Humidity, 52 "Thick as Pea Soup",
        53 The Stinging Jellyfish, 55 The Yellow Geckos
          No condition (0x403390 returns 1).  Nothing to lift.
     3  The Science Fair (0x414BC0)
          LIFTED  0x414BDE 3 living children -> 1.   KEPT (casting)  a living child (the event is the children's).
     6  Day of Honor (0x414FC0)
          LIFTED  0x414FCA 2 graves -> 1.   KEPT (sense)  at least 1 grave (the villagers honour the dead).
     7  The Canoe from the Other Side (0x414D80)
          LIFTED  0x414D85 the room check 0x45FE30 (the population cap 90 + collections + Magic 3, or the patcher's
                  population mode, and the rebuilt-huts rule) -- the condition now always passes.
          KEPT-FOR-SAFETY  the villager table's real size: the creator 0x45F0B0 returns -1 when all 150 records are in
                  use (0x45F12B / 0x45F163) and the apply skips a -1 (0x45EE60 at 0x414DBC); with the patcher's
                  safety patches the apply also rechecks the physical limit first (builds.json 0x14D90).  This is
                  the same path the stock rescue rule already takes when it forces this event without its room
                  check.
     13 The Miraculous Bloom (0x415030)   KEPT (puzzle)  The Bee Hive solved (puzzle 1).
     15 The Daredevil (0x415420)
          LIFTED  0x415465 2 living women of 18+ -> 1 (cmp count, 1 / setg -> cmp count, 0 / setg).
          KEPT (casting)  a living man of 18+ (the subject; chief already allowed); at least 1 woman to impress.
     16 The Ghostly Dream, nature or healing (0x4154F0)
          LIFTED  0x4154F3 not the chief; 0x415520 Nature technology level 1 or more.
          KEPT (casting)  a living adult of 18+ (not pregnant or nursing) or elder.
     17 The Ghostly Dream, research or architecture (0x415630)
          LIFTED  0x415633 not the chief; 0x415660 Magic technology level 1 or more.
          KEPT (casting)  as slot 16.
     18 The Crystal of Reflections (0x415750)
          LIFTED  0x415775 the room check 0x45FE30 (as slot 7).
          KEPT (casting)  a living adult of 18+ (not pregnant or nursing) or elder, to be copied.
          KEPT-FOR-SAFETY  the table size: the copier 0x45F2D0 returns -1 with no free record and the keep effect
                  checks it (0x45EE60 at 0x419240); the patcher's safety patch at 0x4191EF rechecks before the likes
                  change.
     19 The Bitter Brown Beans, taste or dye, and 21 The Ancient Tablet, laundry or decoration (0x4157E0, shared)
          LIFTED  0x415800 Science technology below level 2: the read of Science (push 0 / mov ecx / call 0x426FC0,
                  which pops its argument) becomes xor eax, eax (+ nops), so "below 2" holds; the site ends before
                  0x41580C, where the patcher's safety patch builds.json safety_patches[20] jumps (see NOTE).
          KEPT (casting)  a living adult of 18-49 not pregnant or nursing.
     20 The Bitter Brown Beans, brew or fertilizer (0x4159B0)
          LIFTED  0x4159DF Science technology level 2 or more.   KEPT (casting)  as slot 19.
     22 The Ancient Tablet, research or display (0x415C40)
          LIFTED  0x415C6C Alchemy technology below level 3; 0x415C82 Science technology level 2 or more.
                  Safe at Alchemy 3: the level-up 0x426FD0 stops at 3 (0x426FDD) and its two listeners do nothing
                  for Alchemy (0x420E20 acts only on Nature / Magic level 2; 0x432E30 is empty) -- "Focus research"
                  then only costs the tech points.
          KEPT (casting)  a living adult of 18+ (not pregnant or nursing) or elder.
     23 The Low Tide (0x415DB0)
          LIFTED  0x415DCB not the chief; 0x415DEA at least 8 living villagers (now count >= 0).
          KEPT (casting)  a living villager (child, adult not pregnant or nursing, or elder) as the subject.
     24 The Ants and the Granary, 29 The Playful Otters, 30 The Ant Hill, 46 The Shooting Star (0x416A10, shared)
          LIFTED  0x416A13 not the chief.   KEPT (casting)  a living child under 14.
     25 The Green Pearl, 31 The Red Starfish, 32 The Blue Starfish, 33 Bed Bugs, 45 The Royal Jelly (0x416CD0)
          LIFTED  0x416CD3 not the chief.   KEPT (casting)  a living adult of 18+ (not pregnant or nursing) or elder.
     26 The Blue Pearl (0x416270)
          KEPT (casting)  an adult or elder (chief already allowed).   KEPT (puzzle)  The Alchemy Lab solved (2).
     27 The Lazy Apprentice (0x4163B0)
          LIFTED  0x4163B4 the child not the chief.
          KEPT (casting)  a living child under 14 (the apprentice); a living villager of 18+ with Research 30 or more
                  (the teacher, 0x45E610(3, 30, 6, -1, 0) at 0x4163E6 -- the event needs a teacher).
     28 The Omen in the Clouds (0x416550)
          LIFTED  0x416553 not the chief.   KEPT (casting)  an adult of 18+ (not pregnant or nursing) or elder.
     34 The Lovers, her gift (0x416ED0)
          LIFTED  0x416ED3 the woman not the chief; 0x416EF2 the man not the chief.
          KEPT (casting)  a woman of 18-49 not pregnant or nursing (she may conceive) and a man of 18-49.
     35 The Lovers, his gift (0x417050)
          LIFTED  0x417053 the man not the chief; 0x417072 the woman not the chief.   KEPT (casting)  as slot 34.
     36 The Medical Emergency (0x4171D0)
          LIFTED  0x4171D3 the patient not the chief; 0x4171F2 the healer not the chief; 0x417218 Medicine
                  technology level 2 or more.
          KEPT (casting)  a living patient (child, adult not pregnant or nursing, or elder) and a healer of 18+.
     37 The Mysterious Vial, quartz (0x417390)      KEPT (casting)  any living villager.  Nothing to lift.
     38 / 39 The Mysterious Vial, obsidian / amber (0x417590)   KEPT (casting)  an adult or elder.  Nothing to lift.
     40 The Mango and the Papaya (0x4178B0)         KEPT (casting)  an adult of 18-49.  Nothing to lift.
     41 The Mysterious Crate (0x417A80)
          LIFTED  0x417AA4 3 living adults of 18-49 -> 1.   KEPT (casting)  one adult of 18-49 (the opener; the
                  picker returns a villager exactly when its count is above 0, 0x45D723).
     42 Vanity and the Bee, 43 The Noisy Bird (0x417D10)
          LIFTED  0x417D13 not the chief.   KEPT (casting)  a woman of 18-49 not pregnant or nursing.
     44 The Hole in the Hut (0x417F30)
          LIFTED  0x417F33 not the chief.   KEPT (casting)  an adult of 18-49.   KEPT (puzzle)  The Bee Hive (1).
     47 The Chief's Address (0x415090)   KEPT (casting)  a living Tribal Chief (the speaker).
     49 The Cold Snap (0x415100)          KEPT (sense)  the fire burning (0x4337A0): the villagers huddle by it.
     54 The Mushroom Celebration (0x415290)
          LIFTED  0x415290 the hidden counter 0x5824B4 (non-collection items brought home) at 500 or more -> 0.
     56 The Return of Biggles (0x4182F0)
          LIFTED  0x4182F3 not the chief.   KEPT (casting)  a living villager (child, adult, elder).
     57 Another One of Those Barrels (0x415310)
          LIFTED  0x415315 the room check (as slot 7).
          KEPT-FOR-SAFETY  the table size: the first child's creator returns -1 when the table is full (nothing is
                  made); the second and third children keep the apply's own room checks (0x41535A, 0x41539D); the
                  patcher's safety patch at 0x415320 rechecks the physical limit first.
     Never offered (no slot): The Swarm of Bees, The Drought -- strings only.

   NOTE (not changed here, found while checking collisions): two of the patcher's VV3 safety patches in
   data\builds.json (and the same rows in data\vv3_population_256_feature.json) land on the wrong condition --
   0x1580C "The Crystal of Reflections is offered only with room for its reflection" patches The Bitter Brown Beans /
   The Ancient Tablet condition 0x4157E0 (its cave re-does "Science below 2" and adds "a free record"), and 0x178DA
   "The Mysterious Vial is offered only with room for its two copies" patches The Mango and the Papaya condition
   0x4178B0 (the vials' condition 0x417590 has the same bytes at 0x4175A5).  The sites below never overlap them.

   COLLISIONS CHECKED: every site and 12 bytes around it against native\ (island_timer_vv3.inc, vvfp_island_events*,
   vvfp_more_island_events, vvfp_story_upgrades, vvfp_island_frequency, the rest) and data\*.json (builds.json's
   population modes and safety patches, vv3_population_256_feature.json, vv3_story_cheat_upgrades_feature.json).
   No overlap.  Near, not overlapping: Story / Cheat Upgrades' detours on the picker calls (0x415500, 0x415640,
   0x4157F0, 0x4163C1, 0x416560, 0x416A20, 0x416CE0, 0x416EE0, 0x416EFD, 0x417060, 0x41707D, 0x4171E0, 0x417A9C,
   0x417D20, 0x417F40, 0x418300) and on 0x468757; population 256's "mov ecx, 0x59E110" rewrites (e.g. 0x414D80,
   0x415310, 0x415770, 0x4154FB, 0x468752) -- which is why the room-check sites take the call / jmp after the
   mov, not the mov; the safety patches at 0x414D90, 0x415320 and 0x41580C. */

static const ns_site NS_VV3_SITES[] = {
    /* the scheduler: a living villager of any age, not only 14+ (push 1 -> push 0) */
    { 0x468750u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 1 The Tsunami: 2 women (jge -> jmp), 2 men not the chief (jl -> nops) */
    { 0x414AE5u, 2, { 0x7D, 0x06 }, { 0xEB, 0x06 } },
    { 0x414B0Fu, 2, { 0x7C, 0xD6 }, { 0x90, 0x90 } },
    /* 3 The Science Fair: cmp [esp], 3 -> cmp [esp], 1 */
    { 0x414BDEu, 5, { 0x83, 0x7C, 0x24, 0x00, 0x03 }, { 0x83, 0x7C, 0x24, 0x00, 0x01 } },
    /* 7 The Canoe: call 0x45FE30 -> mov al, 1 (+ nops); test al, al / setne al follow */
    { 0x414D85u, 5, { 0xE8, 0xA6, 0xB0, 0x04, 0x00 }, { 0xB0, 0x01, 0x90, 0x90, 0x90 } },
    /* 6 Day of Honor: cmp eax, 2 -> cmp eax, 1 */
    { 0x414FCAu, 3, { 0x83, 0xF8, 0x02 }, { 0x83, 0xF8, 0x01 } },
    /* 54 The Mushroom Celebration: cmp [0x5824B4], 500 -> cmp [0x5824B4], 0 */
    { 0x415290u, 10, { 0x81, 0x3D, 0xB4, 0x24, 0x58, 0x00, 0xF4, 0x01, 0x00, 0x00 },
                     { 0x81, 0x3D, 0xB4, 0x24, 0x58, 0x00, 0x00, 0x00, 0x00, 0x00 } },
    /* 57 Another One of Those Barrels: jmp 0x45FE30 -> mov al, 1 / ret */
    { 0x415315u, 5, { 0xE9, 0x16, 0xAB, 0x04, 0x00 }, { 0xB0, 0x01, 0xC3, 0x90, 0x90 } },
    /* 15 The Daredevil: cmp ecx, 1 / setg -> cmp ecx, 0 / setg (1 woman) */
    { 0x415465u, 3, { 0x83, 0xF9, 0x01 }, { 0x83, 0xF9, 0x00 } },
    /* 16 The Ghostly Dream (nature): not the chief; Nature >= 1 (setg cl -> mov cl, 1) */
    { 0x4154F3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x415520u, 3, { 0x0F, 0x9F, 0xC1 }, { 0xB1, 0x01, 0x90 } },
    /* 17 The Ghostly Dream (magic): not the chief; Magic >= 1 */
    { 0x415633u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x415660u, 3, { 0x0F, 0x9F, 0xC1 }, { 0xB1, 0x01, 0x90 } },
    /* 18 The Crystal of Reflections: jmp 0x45FE30 -> mov al, 1 / ret */
    { 0x415775u, 5, { 0xE9, 0xB6, 0xA6, 0x04, 0x00 }, { 0xB0, 0x01, 0xC3, 0x90, 0x90 } },
    /* 19 / 21 Beans (taste or dye), Tablet (laundry or decoration): Science < 2 -- the level read
       (push 0 / mov ecx, 0x582618 / call 0x426FC0, ret 4) -> xor eax, eax + 10 nops */
    { 0x415800u, 12, { 0x6A, 0x00, 0xB9, 0x18, 0x26, 0x58, 0x00, 0xE8, 0xB4, 0x17, 0x01, 0x00 },
                     { 0x33, 0xC0, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 } },
    /* 20 Beans (brew or fertilizer): Science > 1 (setg al -> mov al, 1) */
    { 0x4159DFu, 3, { 0x0F, 0x9F, 0xC0 }, { 0xB0, 0x01, 0x90 } },
    /* 22 Tablet (research or display): Alchemy < 3 (jl -> jmp); Science >= 2 (setge cl -> mov cl, 1) */
    { 0x415C6Cu, 2, { 0x7C, 0x03 }, { 0xEB, 0x03 } },
    { 0x415C82u, 3, { 0x0F, 0x9D, 0xC1 }, { 0xB1, 0x01, 0x90 } },
    /* 23 The Low Tide: not the chief; cmp [esp], 8 -> cmp [esp], 0 */
    { 0x415DCBu, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x415DEAu, 5, { 0x83, 0x7C, 0x24, 0x00, 0x08 }, { 0x83, 0x7C, 0x24, 0x00, 0x00 } },
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
    /* 36 The Medical Emergency: patient, healer not the chief; Medicine >= 2 (setge al -> mov al, 1) */
    { 0x4171D3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x4171F2u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    { 0x417218u, 3, { 0x0F, 0x9D, 0xC0 }, { 0xB0, 0x01, 0x90 } },
    /* 41 The Mysterious Crate: cmp [esp+4], 3 -> cmp [esp+4], 1 */
    { 0x417AA4u, 5, { 0x83, 0x7C, 0x24, 0x04, 0x03 }, { 0x83, 0x7C, 0x24, 0x04, 0x01 } },
    /* 42 / 43 Vanity and the Bee, The Noisy Bird: not the chief */
    { 0x417D13u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 44 The Hole in the Hut: not the chief */
    { 0x417F33u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
    /* 56 The Return of Biggles: not the chief */
    { 0x4182F3u, 2, { 0x6A, 0x01 }, { 0x6A, 0x00 } },
};

#define NS_VV3_COUNT (sizeof NS_VV3_SITES / sizeof NS_VV3_SITES[0])
