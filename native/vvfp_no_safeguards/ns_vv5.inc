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
   Lifting "not pregnant or nursing" / the role test is a push 0 -> push 1 of that call's argument; lifting an age
   bound is a push of -1 in its place.

   HEATHENS ONLY IN CONVERSION ROLES (the owner's rule).  No site lets a Heathen be cast where the stock game casts a
   believer.  Proof, from the picker 0x471870: the role test (0x47198A: if allowRole == 0, skip roles 12-17) only
   ever SKIPS records; it is followed by the Heathen test at 0x4719B8 (if allowHeathen == 0 and the record is a
   Heathen, +0x1CEC at [esi+0x160], and heathenOnly (cl) == 0 -> skip), which does not read allowRole.  Every
   believer pick passes heathenOnly = 0 and allowHeathen = 0 (unchanged), so after allowRole 0 -> 1 every Heathen
   is still skipped at 0x4719CD; only believers whose role is 12-17 are added (the Retired Chief, role 13, kept by
   the conversion 0x4668B0 at 0x466966, and a convert whose role a companion keeps).  0x466170 (present +0x1CD4,
   +0x1CE1 clear unless its argument is 1; the picker passes 0) is not touched.  Every Heathen pick (the Heathen
   Toy's, Spa / Cracked Mask's, Spying / Missing Kids', You're Doing It Wrong's Heathen child; Outreach's envoy; The
   Defector) is EXACTLY the stock one -- its role test, its "not sick", its ages -- no site in those calls.  The
   believer / Heathen side of every event stays as stock.

   GUARDIANS OF ISOLA.  The row vv5_guardians_of_isola_rewrite writes no exe bytes (Assets/sm.xml and images only),
   so no site here touches anything it writes.  Every "the text needs it" test below was made against both the
   stock texts and the Guardians texts (data/guardians_of_isola/{base,new}/Assets/sm.xml); a need is kept if either
   text needs it.

   INANIMATE OBJECTS.  The records that are not living villagers are corpses and Reanimate spirits (u8 +0x1CE1) and
   the dead (health <= 0).  The picker's first two tests reject them for every event; no site below touches the
   picker or 0x466170, so no event can cast or harm one.  The creators 0x46FAD0 / 0x46FB80 (believers / Heathens)
   make villagers only, and stop at 150 records (-1).  The island's things (fire 0x51DE80, puzzles 0x51E008, the
   Roster of the Dead 0x5481A8) are separate objects no picker reads.

   TRIGGER-LEVEL RULES (the scheduler 0x4426EA.., the selector 0x418870): nothing lifted.
     KEPT  the timer and the delays (manager+0x17D3C; native/shared/island_timer_vv5.inc); the believers-above-0
           test (0x442700); no God Power armed on the pointer (0x442708: the attempt waits, the timer untouched;
           crash guard); the scheduler's random believer draw (0x44272F) and its age == processed-age test
           (0x44274E; timing); the uniform draw (0x41890A); the rescue rule (0x418913-0x418956, slot 30).  No
           once-only or cooldown flags (the 'shown' bytes 0x4DC814+slot are written at 0x41899A, never read) and no
           "village in trouble" skip.

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
         LIFTED  0x414DBA 2 graves -> 1.   KEPT (text)  at least 1 grave ("pay their respects to those who have
                 passed on").
     5 The Vision, 12 The Mask, 35 Doubt, 43 The Aphids in the Noni Bush, 45 The Straw Hat (0x414B90, shared)
         LIFTED  0x414B91 the role test.   KEPT (stock)  a living believer of any age.
     11 The Bed Bugs (0x415640)
         LIFTED  0x415641 the role test; 0x415655 not pregnant or nursing.   KEPT (stock)  a living believer.
     13 The Heathen Toy (0x415820)
         LIFTED  0x415822 the believer's role test.
         KEPT (text)  a believer child under 14 ("little {name}", "while playing").   KEPT (stock)  the Heathen
                 child, exactly as stock (a conversion role: "Return it" raises its Faith).
     14 The Daredevil Jump (0x415960)
         LIFTED  0x415961, 0x415994 the role test (both picks).   KEPT (stock)  a living believer.
     15 The Cold Snap (0x414E10)          KEPT (text)  the village fire burning (the text puts it out).
     16 Army Ants!, 17 Aphid Infestation!, 21 The River Breaks Its Banks (0x414E60)
         KEPT (text)  The Hydroponic Farm solved (puzzle 5): the crops every text names.
     23 The Pesky Critter (0x415050)      KEPT (text)  The Knowing Totem solved (puzzle 4): the lab the text uses.
     24 Mushroom Day! (0x4150B0)
         LIFTED  0x4150B1 the role test.   KEPT (text)  a believer child under 14 ("those little youngsters").
     26 Barrel O' Babies! (believers), 27 Barrel O' Babies! (heathens), 30 Chutes Without Ladders, 31 News From
        Another Tribe (a newcomer) (0x4151C0)
         LIFTED  0x4151CA the room check (see ROOM).   KEPT-FOR-SAFETY  the table size (see ROOM).
     34 The Spa, 47 The Cracked Mask (0x415C40)
         LIFTED  0x415C42 the believer's role test.   KEPT (stock)  the Heathen child, exactly as stock.
     36 Spying on the Heathens, 38 The Missing Kids (0x415E20)
         LIFTED  0x415E22 the believer's role test.
         KEPT (text)  a believer child under 14 ("little {name}").   KEPT (stock)  the Heathen child.
     37 You're Doing It Wrong! (0x415F60)
         LIFTED  0x415F62 the believer's role test.
         KEPT (text)  a believer of 14 or more: teaching in the lab is adults' work (children never research).
         KEPT (outcome)  Science technology below level 2 (0x415FDB): "Teach them" raises Science a level.
         KEPT (stock)  the Heathen child.
     39 Outreach? (0x416280)
         LIFTED  0x416282 the believer's role test; 0x41629E the believer's age 14 or more (the host is not named;
                 neither text needs an adult).
         KEPT (stock)  the envoy, exactly as stock (a conversion role: "Offer a tour" raises its Faith +20).
     40 The Advanced Artifacts (0x416430)
         LIFTED  0x416442 Science level 2 or more (neither text needs it); 0x416452 the role test.
         KEPT (outcome)  Science below level 3 (0x416499): "Prepare an independent report" raises Science a level.
     41 Trick Or Trade (0x4165D0)
         LIFTED  0x4165E0 the role test.
         KEPT (outcome)  100 food or more (0x4165DA): "Trade some food" takes 100 food.
     42 The Migrating Fruit Bats (0x4166F0)
         LIFTED  0x4166F1 the role test; 0x416709 the child-only rule (under 14): neither text needs a child.
         KEPT (outcome)  Food Mastery below level 2 (0x416736): "Observe them" raises it a level.
     44 The Defector (0x416900)            KEPT (stock)  the Heathen, exactly as stock (the conversion itself).
     46 The Strange Nectar (0x416AB0)
         LIFTED  0x416AB1 the role test.
         KEPT (outcome; the owner 2026-11-15: vanilla)  a believer of 18 or more: "Drink it" sets the age to 16.5.
     55 Innovation in Farming, the mysterious storyteller (0x416FA0)
         LIFTED  0x416FB1 The Heathen Scientist solved (puzzle 13): neither text mentions it; 0x416FB5 the role
                 test.
         KEPT (text)  a believer child under 14 ("gather the other children", "handled by the adults").
     The rolls inside conditions (0x415FDF, 0x41644A, 0x416906) decide outcomes, not whether the event comes;
     unchanged.
     Never in the game (developer-dead, condition 0x415B10 = xor al,al; untouched): 25 The Stinging Wasps, 29 The
     Return of Biggles, 33 The Abandoned Infants, 48-50 The Smelly / Floral / Invisible Vial, 51 Innovation in
     Farming, 52 Tough Lessons, 53 The Pretty Shell, 54 The Legendary Stranger.

   OTHER COMPANIONS.  No site overlaps another companion's bytes: Story / Cheat Upgrades' call-site hooks (e.g.
   0x4151D7, 0x4162A8, 0x41644A, 0x416717, 0x416AD7) and the safety patches at 0x4151D0 / 0x4152B0 / 0x415410 are
   outside every site. */

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
    /* 13 The Heathen Toy: the believer's role test */
    { 0x415822u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 14 The Daredevil Jump: the role test, both picks */
    { 0x415961u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x415994u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 34, 47 (0x415C40): the believer's role test */
    { 0x415C42u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 36, 38 (0x415E20): the believer's role test */
    { 0x415E22u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 37 You're Doing It Wrong!: the believer's role test */
    { 0x415F62u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 39 Outreach?: the believer's role test; the believer any age (minimum age 280 -> -1) */
    { 0x416282u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x41629Eu, 5, { 0x68, 0x18, 0x01, 0x00, 0x00 }, { 0x68, 0xFF, 0xFF, 0xFF, 0xFF } },
    /* 40 The Advanced Artifacts: Science >= 2 (jge -> jmp); the role test */
    { 0x416442u, 2, { 0x7D, 0x04 }, { 0xEB, 0x04 } },
    { 0x416452u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 41 Trick Or Trade: the role test */
    { 0x4165E0u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 42 The Migrating Fruit Bats: the role test; any age (maximum age 280 -> -1) */
    { 0x4166F1u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    { 0x416709u, 5, { 0x68, 0x18, 0x01, 0x00, 0x00 }, { 0x68, 0xFF, 0xFF, 0xFF, 0xFF } },
    /* 46 The Strange Nectar: the role test (its 18 or more stays the stock one) */
    { 0x416AB1u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
    /* 55 the mysterious storyteller: The Heathen Scientist gate (jne -> jmp); the role test */
    { 0x416FB1u, 2, { 0x75, 0x02 }, { 0xEB, 0x02 } },
    { 0x416FB5u, 2, { 0x6A, 0x00 }, { 0x6A, 0x01 } },
};

#define NS_VV5_COUNT (sizeof NS_VV5_SITES / sizeof NS_VV5_SITES[0])
