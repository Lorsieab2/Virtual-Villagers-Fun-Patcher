/* The Lost Children (VV2): "No Safeguards for Island Events" -- the game's own sites.

   Read from the stock exe (inputs/vv2-stock-copy, .text raw offset == VA - 0x400000: .text VA 0x1000, raw
   0x1000).  Every address below was checked in the disassembly and every site's stock bytes were compared with
   the file.  Records: 256 of 0xE48C bytes (pool [0x499F24]); in use +0x30, health +0x52C, age +0x530 (20 units
   = 1 villager year; child = under 280 = 0x118), processed age +0x534, sex +0x538, pregnant/nursing +0x540,
   Is Totem +0x558.

   TRIGGER (0x42EECD .. 0x42F1F9), rules
     KEPT    0x42EECD  the timer (is the event due) -- the Island Timer companion's hook, untouched.
     KEPT    0x42EEE2  population (0x425860) above 0: an event needs a village (the Story Upgrades' empty-village
                       stub at 0x42EEDB stays as it is).  KEPT-FOR-SAFETY too: with nobody living, the pickers
                       return -1 and the two-choice / sack setups would cast no one.
     LIFTED  0x42EF01  "a living villager of 14 or more exists" (0x44BAE0(1) != -1).  No event casts that
                       villager (ebp is overwritten before any event uses it), so it is a pure gate: the je that
                       skipped the whole event (to 0x42F1F9) is re-aimed at 0x42EF26 (the family roll) -- the
                       same point the Story Upgrades' empty-village stub resumes at.  With no villager of 14 or
                       more, the processed-age test is skipped too (it reads that villager's record and would
                       read record -1).  A village of children only now gets island events; every event that
                       needs an older villager still checks for one itself (see below), and the two fallbacks
                       (single-result case 10, two-choice case 5) cast nobody / any villager.
     KEPT    0x42EF20  the drawn villager's age +0x530 == processed age +0x534 (still working off credited
                       time): it only delays the event until catch-up is done -- part of the timing, which the
                       feature does not change.  (Its call 0x42EEED is the Story Upgrades' fast-delivery hook.)
     KEPT    0x42EF28 / 0x42EF4A  the family weights (first event always two-choice; then 20% two-choice, 40%
                       single-result, 40% Sack / Vial), the delays (+0x708 after the first, then (rand(10)+10) h),
                       the counter world+0x2E51C.  The 0x426110 branch (0x42EF5B) is dead (always 0) and stays.
     No rescue events and no rescue rule exist in this game.  No event has a once-only flag or cooldown.

   SINGLE-RESULT family (chooser 0x434570: case = rand(max-min+1)+min at 0x434607, up to 10 draws, condition
   table 0x434868 [0x434822 accept, 0x434824 reject]; none passing -> case 10; bodies table 0x4344F4)
     [0]  The Obnoxious Parrot, [1] The Flash Flood, [2] The Dense Fog (food lost), [3] The Dense Fog (tech
     lost), [5] The East Wind, [6] The Heat Wave, [7] Isola Day Celebration, [9] Day of Elders, [10] Blessings
     Day Celebration (first), [12] Blessings Day Celebration (second), [13] The Spring Allergies, [19] The
     Friendly Parrot, [22] The West Wind, [23] The Dense Fog (tech gained), [24] The Dense Fog (food gained),
     [27] The Mother Parrot:
          no condition in the stock game (table -> 0x434822); nothing to lift.
     [8]  Day of Honor
          KEPT    0x4347C0  at least one occupied slot in the 50-slot memorial (0x426160: +0x74 > 0 of the
                            memorial at world+0x2EB0C, stride 0x7C): a day honouring those who have passed needs
                            someone who has passed (the owner's rule for the later games' Day of Honor: "at least
                            1" grave).  The body (0x433A31) itself reads no memorial slot.
     [11] The Epidemic, [14] Rats!, [17] The Foul Passing
          LIFTED  0x4347F2  all 16 puzzles solved (0x4261D0, flags world+0x2E768..+0x2E7E8): setne bl -> mov bl,1;
                            nop.  None of the three texts mentions a puzzle (a sick parrot's epidemic; rats; a
                            foul passing).  The call 0x4261D0 still runs (it only reads flags).  The Epidemic and
                            Rats! work through 0x4332F0, which takes only records in use with health > 0
                            (0x43332C / 0x433336); The Foul Passing only sets the food to 0 (0x433E30).
     [15] Where Are The Infants?
          LIFTED  0x4345E5  the mother's age of 18 or more: the scan's bound esi = 0x168 becomes 0 (esi is used
                            by nothing else in the chooser: the eight `cmp [eax+4], esi` of the unrolled scan and
                            its push/pop).  The text is about mothers and infants; being pregnant or nursing is the
                            need, not the age.
          KEPT    0x434639..0x4347A9  a living villager (in use 0x434656, health > 0 0x43465A) with +0x540 > 0
                            (pregnant or nursing): "the village infants disappeared! The mothers are in a panic".
          LIFTED  0x4347BA  all 16 puzzles solved (0x4261D0): jne 0x434822 -> jmp 0x434822 (reached only after the
                            scan found a mother: 0x4347AB still rejects when none).  The text mentions no puzzle.
                            The body (0x433D3A) clears +0x540 only of records in use with health > 0 (0x433D6C,
                            0x433D70).
     [16] A Dangerous Mission
          KEPT    0x4347D2  population (0x425860) above 60: the text says "Eight villagers depart", the strongest
                            and youngest adults; the body (0x433E3E) takes up to 8 living villagers aged 281..499
                            units.  No byte change can test "8 such villagers exist", and with the population
                            lifted the text would name eight who are not there; the stock 61 is the guard.
     [21] The Barrel O` Babies, [25] Old Friends
          KEPT-FOR-SAFETY 0x434809 / 0x4347F7 -> 0x44B310  the game's room check.  Its population cap (90 + 5
                            per finished children's collection, 0x44B3AD -- the base the population modes
                            change) is the ONLY guard of the villager table: the maker 0x44C600 takes the first
                            record not in use with no bound at 256 (0x44C823), so villagers added past the table
                            would be written past its end.  Its hut tiers (15 / 25 / 50 people need 1 / 2 / 3
                            huts, 0x44B3BB..0x44B3EE) are a lift the feature wants but cannot make: they are in
                            the same shared routine, which conception, delivery, The Savage Child and The Silver
                            Mirror also call (and the population modes and record guards patch), and no plain
                            byte change at these two calls can test the cap alone.  KEPT, and why.
     [4], [18] The Mosquito Swarm, [20] The Dragonfly Migration, [26]
          developer-dead (table -> 0x434824); restoring them is Restore Missing Island Events' job.  Untouched.
     The stray `cmp ebp, 0x2AD / 0x2B7` at 0x434617 / 0x43481A never match a case (ebp <= 27).  Untouched.

   TWO-CHOICE family (chooser 0x41F570: rand(22) at 0x41F59D, 21 always rejected (0x41F5AC, the More Island
   Events' site), up to 10 draws; none passing -> case 5; condition table 0x41F6C8; setups 0x420454; answers
   0x422264)
     [64] The Ancient Gold Coin
          KEPT    0x41F5B9  Culture (world+0x2EA74) below 2: "wear it" raises Culture (0x42052E inc, while
                            below 2), so the level the answer raises keeps its condition (owner's rule).
          KEPT    subject: a random living villager of any age (0x44BAE0(0), setup 0x41F7BC).
     [65] The Cursed Idol
          KEPT    0x41F5CD  at least 250 food (world+0x2EAA4): the offering answer takes 250 food (x2 / x3 by
                            population, 0x420678..0x420684), so the food it takes keeps its condition.
          KEPT    subject: a random living villager of any age.
     [66] The Prettiest Tribe Girl
          KEPT    0x41F5E5  a living female aged 14 or more (0x44BC80(1, 2)): the text speaks of "lots of male
                            attention" and "the most beautiful girl in the tribe" -- an adult-attention text,
                            kept to the stock 14 (the Isola content rules: no adult-minor romance).  Sex: the
                            event is about a girl.  (Stock: the setup then casts ANY living female, 0x44BC80(0, 2)
                            at 0x41F8BB, a girl included -- unchanged, nothing stricter.)
     [67] The Strange Request
          no condition (stock); the Record Guards' table entry 0x41F6D4 may add a free-record check.  Nothing.
     [68] The Savage Child
          KEPT-FOR-SAFETY 0x41F5FE -> 0x44B310  the room check, as [21] / [25] (the record guards also hook
                            this call, 0x41F604).
     [69] The Voices In The Brush, [71] The Fastest Runner, [72] The Nightmare, [73] A Bump On The Head,
     [75] The Swarm Of Dragonflies, [76] The Black Seeds, [79] The Huge Coconut, [80] The Falling Star,
     [81] The Hole In The Sand, [84] The White Pearl:
          no condition (stock); KEPT subject: a random living villager of any age.
     [70] For The Birds, [74] The Child Prodigy
          KEPT    0x41F613  a living child under 14 (0x44C030 != -1): the event is about a child.
     [77] The Crystal Ball
          KEPT    0x41F626  a living villager aged 14 or more (0x44BAE0(1)).  Fix Vanilla Bugs replaces
                            0x41F636 with its jump (to also need two living villagers, so the finder has someone
                            to trade places with) -- a collision, and the check is a casting need once fixed.
     [78] The Silver Mirror
          LIFTED  0x41F648  population (0x425860) of at least 2: setge bl -> mov bl,1; nop.  The text names only
                            the finder (and an old man seen in the mirror, not a villager).  Safe: the first word
                            only shows text; the second copies the subject only after its own room check
                            (0x4217DF, kept; the record guards' site).  The subject is picked by 0x44BAE0(0)
                            (0x44BB00 health > 0, 0x44BB0A in use): never a totem, so no totem is ever copied.
          KEPT    subject: a random living villager of any age.
     [82] The Spyglass
          KEPT (stock, the owner 2026-11-15: "keep the Spyglass fully vanilla")  Exploration (world+0x2EA94)
                            below 2 (0x41F659): "keep it" WRITES Exploration = 2 (0x421E7D).
          KEPT    subject: a random living villager of any age.
     [83] The Love Note
          KEPT    0x41F65E..0x41F692  a living woman of 18 or more (the admirer) and a living man of 18 or more
                            (the subject, stored at +0x70): a love note between adults.
     [85] (case 21) developer-dead / the More Island Events' slot.  Untouched.

   SACK / VIAL family (0x437AC0: one rand(8) at 0x437B0E, strength rand(100) at 0x437ADC)
     [128]..[135] the five Mysterious Sacks and three Mysterious Vials: no condition; KEPT subject: a random
     living villager of any age (0x44BAE0(0), 0x437B3B).  Nothing to lift.

   INANIMATE OBJECTS -- the Esteemed Elders' totem statues (the only object kind kept in villager records)
     A totem is a record in use with Is Totem +0x558 set and health 0 or less (the totem maker 0x44D190; with
     "VVFP VV2 Totems" installed they are not in the records at all).  Every casting scan and picker an island
     event uses requires health > 0: 0x44BAE0 (0x44BB00..), 0x44BC80 (0x44BCB0..), 0x44BE70, 0x44C030, the
     infants scan (0x43465A), A Dangerous Mission (0x433E7B), Day of Honor (0x433A6E) and every other body loop
     in 0x433600..0x4344F0 (0x4337D1, 0x43388E, 0x43394E, 0x4339E0, 0x433AEE, 0x433C0E, 0x433D70, 0x433DB0,
     0x433EFE, 0x433F50, 0x4343E0); the population count 0x425860 leaves totems out.  So no event can cast,
     harm or remove a totem.  No site below touches any of those tests.  Day of Elders (0x433B68) only reads
     +0x558.  The stock game casts no totem.  Per site: 0x42EF01 casts nobody (the drawn index is dropped);
     0x4345E5 / 0x4347BA keep the infants scan's in-use and health > 0 tests (0x434656, 0x43465A) and the body's
     (0x433D6C, 0x433D70); 0x4347F2 leads to 0x4332F0 (in use 0x43332C, health > 0 0x433336) or a food write;
     0x41F648's subject is 0x44BAE0(0)'s (health > 0 0x44BB06, in use 0x44BB0D).  A totem held by the VV2 Totems
     companion is in no record, so no scan can reach it.

   OTHER COMPANIONS, checked (+-12 bytes of every site): Island Timer 0x42EECD; Story Upgrades 0x42EEDB, 0x42EEED,
   0x42EF28, 0x41F59D, 0x41F5A5, 0x4349B2; Story Upgrades / More Island Events 0x434607, 0x434617; More Island
   Events 0x41F5AC, 0x41F792, 0x41F7A0; Fix Vanilla Bugs
   0x41F636 (data/builds.json); Record Guards 0x41F604, 0x4217DF, table 0x41F6D4; Restore Missing Island Events
   (table 0x434868 entries, 0x4344F4[4]).  None within 12 bytes of a site.  The 0x347CD / 0x347EB fun patches
   in data/builds.json are The Secret City's. */

static const ns_site NS_VV2_SITES[] = {
    /* trigger: a living villager of 14 or more -- je 0x42F1F9 re-aimed at the family roll 0x42EF26 */
    { 0x42EF01u, 6, { 0x0F, 0x84, 0xF2, 0x02, 0x00, 0x00 }, { 0x0F, 0x84, 0x1F, 0x00, 0x00, 0x00 } },
    /* [15] Where Are The Infants?: the mother's 18 -- mov esi,0x168 -> mov esi,0 */
    { 0x4345E5u, 5, { 0xBE, 0x68, 0x01, 0x00, 0x00 }, { 0xBE, 0x00, 0x00, 0x00, 0x00 } },
    /* [15] Where Are The Infants?: all 16 puzzles -- jne 0x434822 -> jmp 0x434822 */
    { 0x4347BAu, 2, { 0x75, 0x66 }, { 0xEB, 0x66 } },
    /* [11] The Epidemic, [14] Rats!, [17] The Foul Passing: all 16 puzzles -- setne bl -> mov bl,1; nop */
    { 0x4347F2u, 3, { 0x0F, 0x95, 0xC3 }, { 0xB3, 0x01, 0x90 } },
    /* [78] The Silver Mirror: population of 2 -- setge bl -> mov bl,1; nop */
    { 0x41F648u, 3, { 0x0F, 0x9D, 0xC3 }, { 0xB3, 0x01, 0x90 } },
    /* [82] The Spyglass: as in the stock game (the owner, 2026-11-15) -- no site. */
};

#define NS_VV2_COUNT (sizeof NS_VV2_SITES / sizeof NS_VV2_SITES[0])
