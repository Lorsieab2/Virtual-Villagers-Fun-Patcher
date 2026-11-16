/* New Believers (VV5): "No Safeguards for Island Events" -- the game's own natural island events.

   Read from the stock "Virtual Villagers - New Believers.exe" (.text raw offset == VA - 0x400000, checked).  The
   selector 0x418870 asks each of the 55 slots of 0x4DC850 (filled by 0x417790) its condition (vtable [1]) and draws
   one of those that pass.  Every condition below was disassembled; every site's stock bytes were compared with the
   exe.

   THE PICKER THE CONDITIONS CALL (not changed; shared with other game code):
     0x471870(minAge, maxAge, sex, allowPregnant, allowSick, skill, minSkill, mustBePregnant, mustBeSick, &count,
              heathenOnly, a12, allowHeathen, allowRole) -- every call here passes a12 = 1 (the +0x1D0C test off).
       * a record must pass 0x466170(0): present (+0x1CD4) and NOT a corpse or Reanimate spirit (+0x1CE1)
         (0x4718A0..0x4718AF), and have health above 0 (+0x1C40, 0x4718B5);
       * heathenOnly = 1 takes only Heathens (+0x1CEC, 0x471976); otherwise a Heathen is skipped unless
         allowHeathen (0x4719B8);
       * allowRole = 0 skips the roles +0x1CFC 12-17 (0x47198A..0x4719B6): the Heathen Doctor, Heathen Chief,
         Heathen Master Scientist / Builder / Farmer and Heathen Mommy, and the Retired Chief (a believer who keeps
         role 13).  Pushing 1 lifts it for one call.
   Lifting "not pregnant or nursing" / "not sick" / the role test is a push 0 -> push 1 of that call's argument.

   BELIEVERS AND HEATHENS.  Heathens are villagers, not objects.  Each event's believer / Heathen casting is KEPT as
   a casting need, because each event is about one side: the believer events change the subject's Faith or
   Devotion, make a believer a Heathen ("Put it on", "Enjoy the pools", "Try to trick the heathen"), or ask the
   player to decide for one of the tribe; the Heathen picks are the Heathen the story names (the toy's owner, the
   envoy, the defector), whose Faith the event raises (a Heathen above 0 joins the tribe).  The role test is LIFTED
   on every believer pick (it can only skip the Retired Chief, or a convert whose role a companion keeps -- both
   ordinary villagers now; the Retired Chief can already turn Heathen by the stock Faith drift).  It is KEPT on the
   Heathen picks (KEPT, puzzle): roles 12-17 are the Heathen characters of the puzzles and conversions (e.g. The
   Heathen Scientist, puzzle 13, is convincing the Master Scientist to join), and Outreach (envoy Faith +20) and The
   Defector (Faith set to 20) can convert the one picked outside those puzzles.  UNCONFIRMED which role belongs to
   which puzzle; kept so no puzzle can be bypassed.

   INANIMATE OBJECTS.  The records that are not living villagers are corpses and Reanimate spirits (u8 +0x1CE1) and
   the dead (health <= 0).  The picker's first two tests reject them for every event; no site below touches the
   picker or 0x466170, so no event can cast or harm one.  The creators 0x46FAD0 / 0x46FB80 (believers / Heathens)
   make villagers only, and stop at 150 records (-1).  The island's things (fire 0x51DE80, puzzles 0x51E008, the
   Roster of the Dead 0x5481A8) are separate objects no picker reads.

   TRIGGER-LEVEL RULES (the scheduler 0x4426EA.., the selector 0x418870): nothing lifted.
     KEPT  the timer and the delays (manager+0x17D3C; native/shared/island_timer_vv5.inc); the believers-above-0
           test (0x442700); no God Power armed on the pointer (0x442708: the attempt waits, the timer untouched --
           KEPT-FOR-SAFETY, an event popup over an armed power is not proven safe, UNCONFIRMED); the scheduler's
           random believer draw (0x44272F, role test on: its "push ebx" arguments cannot be changed in place) and
           its age == processed-age test (0x44274E; a timing wait); the uniform draw (0x41890A); the rescue rule
           (0x418913-0x418956, still forcing slot 30).  No once-only or cooldown flags (the 'shown' bytes
           0x4DC814+slot are written at 0x41899A, never read) and no "village in trouble" skip.

   ROOM FOR NEW VILLAGERS (slots 26, 27, 30, 31 share the condition 0x4151C0).  LIFTED at 0x4151CA: the room check
   0x472BD0 (believers + babies they carry against 90 + collections or the patcher's population mode, and the
   rebuilt-huts rule) is still called, its answer replaced by 1.
     KEPT-FOR-SAFETY  the table size, in the events' own code: the creators return -1 at 150 records; the
     always-installed safety patches recheck the physical limit before each first child (builds.json 0x151D0
     Barrel, 0x152B0 Heathen Barrel, 0x15410 Chutes), make the room check answer "no room" while the records'
     demand has no record left (0x72BD7), and make a delivery wait until its litter fits (0x730AF).  The later
     children still come only while 0x472BD0 passes (the events' own code, unchanged).
     NOTE  slot 31 News From Another Tribe (a newcomer): its own effect 0x415510 asks 0x472BD0 again (0x415515)
     before it creates the master, so with no room by the game's rule the popup comes and no one joins.

   EVERY NATURAL EVENT (slot, title):
     1 The Creeping Mold, 2 The Allergy Season, 3 Isola Day Celebration, 6-9 The Mysterious Footprints (food
       gained, food lost, tech gained, tech lost), 10 Blessings Day Celebration, 18 The Strange Crystals, 19 The
       Especially Offensive Cloud, 20 The Bottle of Spicy Juice, 22 The Clumsy Heathen, 28 The Salty Air, 32 News
       From Another Tribe (a message)
         No condition (0x408470 returns 1).  Nothing to lift.
     4  Day of Honor (0x414DB0)
         LIFTED  0x414DBA 2 graves -> 1.   KEPT (sense)  at least 1 grave.
     5 The Vision, 12 The Mask, 35 Doubt, 43 The Aphids in the Noni Bush, 45 The Straw Hat (0x414B90, shared)
         LIFTED  0x414B91 the role test.   KEPT (casting)  a living believer of any age.
     11 The Bed Bugs (0x415640)
         LIFTED  0x415641 the role test; 0x415655 not pregnant or nursing.   KEPT (casting)  a living believer.
     13 The Heathen Toy (0x415820)
         LIFTED  0x415822 the believer's role test; 0x415865 the Heathen child not sick.
         KEPT (casting)  a believer child under 14 and a Heathen child under 14.   KEPT (puzzle)  the Heathen's role.
     14 The Daredevil Jump (0x415960)
         LIFTED  0x415961, 0x415994 the role test (both picks).   KEPT (casting)  a living believer.
     15 The Cold Snap (0x414E10)          KEPT (sense)  the village fire burning (the event puts it out).
     16 Army Ants!, 17 Aphid Infestation!, 21 The River Breaks Its Banks (0x414E60)
         KEPT (puzzle)  The Hydroponic Farm solved (puzzle 5).
     23 The Pesky Critter (0x415050)      KEPT (puzzle)  The Knowing Totem solved (puzzle 4).
     24 Mushroom Day! (0x4150B0)
         LIFTED  0x4150B1 the role test.   KEPT (casting)  a believer child under 14.
     26 Barrel O' Babies! (believers), 27 Barrel O' Babies! (heathens), 30 Chutes Without Ladders, 31 News From
        Another Tribe (a newcomer) (0x4151C0)
         LIFTED  0x4151CA the room check (see ROOM).   KEPT-FOR-SAFETY  the table size (see ROOM).
     34 The Spa, 47 The Cracked Mask (0x415C40)
         LIFTED  0x415C42 the believer's role test; 0x415C8B the Heathen child not sick.
         KEPT (casting)  a believer and a Heathen child under 14.   KEPT (puzzle)  the Heathen's role.
     36 Spying on the Heathens, 38 The Missing Kids (0x415E20)
         LIFTED  0x415E22 the believer's role test; 0x415E6E the Heathen child not sick.
         KEPT (casting)  a believer child under 14 and a Heathen child under 14.   KEPT (puzzle)  the Heathen's role.
     37 You're Doing It Wrong! (0x415F60)
         LIFTED  0x415F62 the believer's role test; 0x415FAE the Heathen child not sick; 0x415FDB Science
                 technology below level 2 (safe: the effect raises Science only while below 2, 0x416090, and the
                 level-up 0x423610 stops at 3).
         KEPT (casting)  a believer of 14 or more and a Heathen child under 14.   KEPT (puzzle)  the Heathen's role.
     39 Outreach? (0x416280)
         LIFTED  0x416282 the believer's role test; 0x4162CE the envoy not sick.
         KEPT (casting)  a believer of 14 or more and a Heathen of 14 or more.   KEPT (puzzle)  the envoy's role.
     40 The Advanced Artifacts (0x416430)
         LIFTED  0x416442 Science level 2 or more; 0x416452 the role test; 0x416499 Science below level 3 (the
                 level-up 0x423610 stops at 3, 0x423622).
         KEPT (casting)  a living believer.
     41 Trick Or Trade (0x4165D0)
         LIFTED  0x4165DA 100 food or more (the trade's -100 goes through 0x41EB40, which stops at 0); 0x4165E0 the
                 role test.
         KEPT (casting)  a living believer.
     42 The Migrating Fruit Bats (0x4166F0)
         LIFTED  0x4166F1 the role test; 0x416736 Food Mastery below level 2 (the level-up stops at 3).
         KEPT (casting)  a believer child under 14.
     44 The Defector (0x416900)
         LIFTED  0x416928 not sick.   KEPT (casting)  a living Heathen.   KEPT (puzzle)  the Heathen's role.
     46 The Strange Nectar (0x416AB0)
         LIFTED  0x416AB1 the role test.
         KEPT (casting, the owner 2026-11-15: vanilla)  a believer of 18 or more (0x416ACD, push 0x168).
     55 Innovation in Farming, the mysterious storyteller (0x416FA0)
         LIFTED  0x416FB5 the role test.   KEPT (casting)  a believer child under 14.
         KEPT (puzzle)  The Heathen Scientist solved (puzzle 13).
     The rolls inside conditions (0x415FDF, 0x41644A, 0x416906) decide outcomes, not whether the event comes;
     unchanged.
     Never in the game (developer-dead, condition 0x415B10 = xor al,al; untouched): 25 The Stinging Wasps, 29 The
     Return of Biggles, 33 The Abandoned Infants, 48-50 The Smelly / Floral / Invisible Vial, 51 Innovation in
     Farming, 52 Tough Lessons, 53 The Pretty Shell, 54 The Legendary Stranger.

   OTHER COMPANIONS.  No site overlaps another companion's bytes: Story / Cheat Upgrades' call-site hooks (e.g.
   0x4151D7, 0x415FDF, 0x41644A, 0x416AD7) and the safety patches at 0x4151D0 / 0x4152B0 / 0x415410 are outside
   every site. */

static const ns_site NS_VV5_SITES[] = {
    /* 5, 12, 35, 43, 45 (0x414B90): the role test */
    { 0x414B91u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 4 Day of Honor: 2 graves -> 1 */
    { 0x414DBAu, 3, { 0x83, 0xF8, 0x02 }, { 0x83, 0xF8, 0x01 } },
    /* 24 Mushroom Day!: the role test */
    { 0x4150B1u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 26, 27, 30, 31 (0x4151C0): the room check's answer -> 1 (test al,al / setne al -> mov al,1 + nops) */
    { 0x4151CAu, 5, { 0x84, 0xC0, 0x0F, 0x95, 0xC0 }, { 0xB0, 0x01, 0x90, 0x90, 0x90 } },
    /* 11 The Bed Bugs: the role test; pregnant / nursing allowed */
    { 0x415641u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415655u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 13 The Heathen Toy: the believer's role test; the Heathen child may be sick */
    { 0x415822u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415865u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 14 The Daredevil Jump: the role test, both picks */
    { 0x415961u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415994u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 34, 47 (0x415C40): the believer's role test; the Heathen child may be sick */
    { 0x415C42u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415C8Bu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 36, 38 (0x415E20): the believer's role test; the Heathen child may be sick */
    { 0x415E22u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415E6Eu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 37 You're Doing It Wrong!: the believer's role test; the Heathen child may be sick; Science < 2 (jge -> nops) */
    { 0x415F62u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415FAEu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415FDBu, 2, { 0x7D, 0xB7 }, { 0x90, 0x90 } },
    /* 39 Outreach?: the believer's role test; the envoy may be sick */
    { 0x416282u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x4162CEu, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 40 The Advanced Artifacts: Science >= 2 (jge -> jmp); the role test; Science < 3 (setl al -> mov al,1) */
    { 0x416442u, 2, { 0x7D, 0x04 }, { 0xEB, 0x04 } },
    { 0x416452u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x416499u, 3, { 0x0F, 0x9C, 0xC0 }, { 0xB0, 0x01, 0x90 } },
    /* 41 Trick Or Trade: 100 food (jge -> jmp); the role test */
    { 0x4165DAu, 2, { 0x7D, 0x04 }, { 0xEB, 0x04 } },
    { 0x4165E0u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 42 The Migrating Fruit Bats: the role test; Food Mastery < 2 (setl al -> mov al,1) */
    { 0x4166F1u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x416736u, 3, { 0x0F, 0x9C, 0xC0 }, { 0xB0, 0x01, 0x90 } },
    /* 44 The Defector: the Heathen may be sick */
    { 0x416928u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 46 The Strange Nectar: the role test (its 18 or more stays the stock one) */
    { 0x416AB1u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 55 the mysterious storyteller: the role test */
    { 0x416FB5u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
};

#define NS_VV5_COUNT (sizeof NS_VV5_SITES / sizeof NS_VV5_SITES[0])
