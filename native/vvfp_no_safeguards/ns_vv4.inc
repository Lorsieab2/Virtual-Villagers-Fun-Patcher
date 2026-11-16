/* The Tree of Life (VV4): "No Safeguards for Island Events" -- the game's own natural island events.

   Read from the stock "Virtual Villagers - The Tree of Life.exe" (.text raw offset == VA - 0x400000, checked).  The
   selector 0x418000 asks each of the 49 slots of 0x4CCA28 (filled by 0x416FF0; slot 19 never written) its condition
   (vtable [1]) and draws one of those that pass.  Every condition below was disassembled; every site's stock bytes
   were compared with the exe.

   THE PICKER THE CONDITIONS CALL (not changed; shared with other game code):
     0x4679B0(minAge, maxAge, sex, allowPregnant, allowSick, skill, minSkill, mustBePregnant, mustBeSick, &count)
     -- only records present (+0x1CC4, 0x4679D6), not a body or ghost (+0x1CC7, 0x4679E0) and with health above 0
     (+0x1C40, 0x4679E9).  allowPregnant / allowSick are byte arguments: pushing 1 instead of 0 lifts "not pregnant
     or nursing" / "not sick" without touching the picker.  There is no Tribal Chief in this game.

   INANIMATE OBJECTS.  The only villager-table records that are not living villagers are bodies and ghosts (u8
   +0x1CC7; ghosts drawn by 0x466370).  The picker above rejects them (and absent and dead records) for every
   event, and the Abandoned Infants' own mother pick 0x467B00 makes the same three tests (0x467B28..0x467B3A).  No
   site below touches either routine, so no event can cast or harm one.  The four creators of records
   (0x466270, called at 0x420263, 0x43B924, 0x467D3B, 0x467D8D) make villagers only.  The island's things (fire
   pit 0x4D867C, stream 0x4D8CF0, puzzles 0x4D8BF8, the Roster of the Dead 0x5025C8) are separate objects that no
   picker reads.

   TRIGGER-LEVEL RULES (the scheduler 0x43FA3D.., the selector 0x418000): nothing lifted.
     KEPT  the timer and the delays (manager+0x170E0; 15 min, 30 min after the first ever, then 8-15 hours;
           native/shared/island_timer_vv4.inc); the population-above-0 test (0x43FA53); the scheduler's random draw
           (0x43FA70, no filters: any living villager) and its age == processed-age test (0x43FA8F; a timing wait
           while credited time is worked off, not a condition of any event); the uniform draw among the passing
           slots (0x4180A5); the rescue rule (0x4180C0-0x4180F2, still forcing slot 25 at 15% x 40%).  There are no
           once-only or cooldown flags (the 'shown' bytes 0x4CC9F4+slot are written at 0x418136, never read) and no
           "village in trouble" skip.

   ROOM FOR NEW VILLAGERS (Barrel, Abandoned Infants).  The condition's call of the room check 0x468350 (population
   cap 90 + collections, or the patcher's population mode, and the rebuilt-huts rule) is lifted at the branch.
     KEPT-FOR-SAFETY  the villager table's real size, in the events' own code: the creator 0x466270 returns -1 when
     all 150 records are in use (0x46628D / 0x46629C); the patcher's always-installed safety patches recheck the
     physical limit before the Barrel's first child (builds.json 0x14D90), clamp the Abandoned Infants to the free
     records (0x14FC0), make the room check itself answer "no room" while the records' demand has no record left
     (0x68357), and make a delivery wait until its litter fits (0x687E4).  The Barrel's 2nd and 3rd child still
     come only while 0x468350 passes (0x414DCA / 0x414E0D, the event's own code, unchanged) -- as when the stock
     rescue rule forces it.

   EVERY NATURAL EVENT (slot, title):
     2 The Creeping Mold, 3 The Allergy Season, 4 Isola Day Celebration, 7-10 The Mysterious Footprints (food
       gained, food lost, tech gained, tech lost), 11 Blessings Day Celebration, 17 The Rainy Season, 20 "A
       Monsoon!", 21 The Stinging Wasps, 23 The Pure Sea Air
         No condition (0x414920 returns 1).  Nothing to lift.
     5  Day of Honor (0x414AD0)
         LIFTED  0x414ADA 2 graves -> 1.   KEPT (sense)  at least 1 grave (the villagers pay respects to the dead).
     12 A Closer Look, 14 The Robber Crab, 29 The Pink Shell, 30 The Calabash Instrument, 36 The Wet Book, 38-43 The
        Aspiring Doctor (algae, sea water, mushrooms, bark, fasting, cut leg), 44 The Aspiring Scientist, 49 The
        Legendary Stranger (0x415E00, shared)
         KEPT (casting)  any living villager (pregnant / nursing and sick already allowed).  Nothing to lift.
     13 The Arc of Brilliant Colors (0x415020)
         LIFTED  0x41502D not pregnant or nursing.   KEPT (casting)  any living villager.
     15 The Phosphorescent Fungi, 31 The Climber, 37 The Lie (0x415F50, shared)
         KEPT (casting)  a living child under 14.  Nothing to lift.
     18 The Cold Snap (0x414BC0)
         KEPT (sense)  the village fire burning (0x432600 on 0x4D867C): the event puts the fire out.
     22 The Festival of the Banyan (0x414CB0)
         LIFTED  0x414CCB the Tree of Life healthy (3 of the 5 tree puzzles solved, 0x41F570 >= 3): the text
                 never mentions the tree's health.
         KEPT (text)  the delivery counter [0x4D6DF4] >= 500 (0x414CB0): the text celebrates "their 500th
                 mushroom".
     25 Daredevil Barrel...of Babies! (0x414D50)
         LIFTED  0x414D5C the room check (see ROOM).
         KEPT (puzzle)  The Stream solved (puzzle 1, 0x414D65) and the stream flowing (0x4396E0 >= 1, 0x414D78).
         KEPT-FOR-SAFETY  the table size (see ROOM).
     26 The State of the Tree, glum (0x414E90)         KEPT (puzzle)  fewer than 3 tree puzzles solved.
     27 The State of the Tree, rejuvenated (0x414F00)  KEPT (puzzle)  3 or more tree puzzles solved.
     28 The Abandoned Infants (0x414F60)
         LIFTED  0x414F6F not sick; 0x414FA4 the room check (see ROOM); 0x414FA6 6 women -> 1.
         KEPT (casting)  a woman of 14 or more not pregnant or nursing (she becomes a mother), as in the stock
                 game (the owner, 2026-11-15: nothing stricter than vanilla; the event's own mother pick 0x467B00
                 still takes a woman of 18 or more, as in the stock game).
         KEPT-FOR-SAFETY  the table size (see ROOM).
     32 The Mosquito Larvae (0x4159C0)
         LIFTED  0x4159D5 the age 14 or more (the text: "{name} notices ... the villagers decide").
         KEPT (text)  Soap solved (3: "put soap in the pond"), The Stream solved (1) and the stream flowing
                 (0x4396E0 >= 1) -- the pond the text uses (UNCONFIRMED that the pond needs the stream).
     33 Faces in the Night (0x415AD0)
         LIFTED  0x415AE5 the age 14 or more (nothing in the text needs an adult).   KEPT (casting)  any villager.
     34 The Screaming Baby (0x415BD0)
         LIFTED  0x415BDB not sick.   KEPT (casting)  a pregnant or nursing woman of 14 or more (the mother).
     35 The Sealed Box (0x415CF0)
         LIFTED  0x415D11 not pregnant or nursing; 0x415D17 the age 14 or more (a swimmer of any age).
                 (The wave 0x415D91 sets health -1 and clears present +0x1CC4 -- the same end state as the game's
                 own death of a pregnant villager at 0x46A977.)
     45 Innovation in Construction (0x416780)
         LIFTED  0x41679C not sick; 0x4167A1 not pregnant or nursing.
         KEPT (text)  a villager of 14 or more: hut construction is adults' work (children never build).
     46 Innovation in Farming (0x4168A0)
         LIFTED  0x4168BC not sick; 0x4168C1 not pregnant or nursing.
         KEPT (text)  a villager of 14 or more: cooking at the pit is the farmers' work (children never farm).
         KEPT (puzzle)  The Cooking Pit solved (puzzle 6, 0x4168EB).
     47 Tough Lessons (0x4169D0)
         KEPT (casting)  a living child under 14 (stuck in the tree) and a villager of 14 or more.  Nothing to lift.
     48 The Pretty Shell (0x416AE0)
         LIFTED  0x416B18 2 villagers of 14 or more -> 1 (the effect 0x416B60 uses only the one subject).
         KEPT (text)  a living villager of 14 or more (the one who parents the children).  The text's "two
                 children" are not checked by the stock game; adding that would be stricter than stock, so not done.
     The rolls inside conditions (Sealed Box 0x415CF5, Innovations 0x416785 / 0x4168A5) decide outcomes, not
     whether the event comes; unchanged.
     Never in the game (developer-dead, untouched): 1 The Tsunami, 6 The Canoe from the Other Side, 16 The Medical
     Emergency, 24 The Return of Biggles (condition 0x4146E0 = xor al,al); 19 The Salty Air (no object).

   OTHER COMPANIONS.  No site overlaps another companion's bytes: Origins' jump at 0x414D50 (5 bytes) ends before
   0x414D5C; Story / Cheat Upgrades' call-site hooks (e.g. 0x414F8B, 0x41503C, 0x415BEF, 0x415D24, 0x4167B4,
   0x4168D4, 0x416B0B) and the safety patches at 0x414D90 / 0x414FC0 are outside every site. */

static const ns_site NS_VV4_SITES[] = {
    /* 5 Day of Honor: 2 graves -> 1 */
    { 0x414ADAu, 3, { 0x83, 0xF8, 0x02 }, { 0x83, 0xF8, 0x01 } },
    /* 22 The Festival of the Banyan: the tree-health gate (jl -> nops); the 500 counter stays */
    { 0x414CCBu, 2, { 0x7C, 0x03 }, { 0x90, 0x90 } },
    /* 25 Daredevil Barrel: the room check (je -> nops) */
    { 0x414D5Cu, 2, { 0x74, 0x22 }, { 0x90, 0x90 } },
    /* 28 The Abandoned Infants: sick allowed; room; 6 -> 1 (the minimum age 14 stays the stock one) */
    { 0x414F6Fu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x414FA4u, 2, { 0x74, 0x0A }, { 0x90, 0x90 } },
    { 0x414FA6u, 4, { 0x83, 0x3C, 0x24, 0x06 }, { 0x83, 0x3C, 0x24, 0x01 } },
    /* 13 The Arc of Brilliant Colors: pregnant / nursing allowed */
    { 0x41502Du, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 32 The Mosquito Larvae: any age (minimum age 280 -> -1) */
    { 0x4159D5u, 5, { 0x68, 0x18, 0x01, 0x00, 0x00 }, { 0x68, 0xFF, 0xFF, 0xFF, 0xFF } },
    /* 33 Faces in the Night: any age */
    { 0x415AE5u, 5, { 0x68, 0x18, 0x01, 0x00, 0x00 }, { 0x68, 0xFF, 0xFF, 0xFF, 0xFF } },
    /* 34 The Screaming Baby: sick allowed */
    { 0x415BDBu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 35 The Sealed Box: pregnant / nursing allowed; any age */
    { 0x415D11u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415D17u, 5, { 0x68, 0x18, 0x01, 0x00, 0x00 }, { 0x68, 0xFF, 0xFF, 0xFF, 0xFF } },
    /* 45 Innovation in Construction: sick, pregnant / nursing allowed */
    { 0x41679Cu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x4167A1u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 46 Innovation in Farming: sick, pregnant / nursing allowed */
    { 0x4168BCu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x4168C1u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 48 The Pretty Shell: 2 villagers of 14+ -> 1 */
    { 0x416B18u, 4, { 0x83, 0x3C, 0x24, 0x02 }, { 0x83, 0x3C, 0x24, 0x01 } },
};

#define NS_VV4_COUNT (sizeof NS_VV4_SITES / sizeof NS_VV4_SITES[0])
