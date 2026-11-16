/* A New Home (VV1): "No Safeguards for Island Events" -- the game's own sites.

   Read from the stock exe (inputs/vv1-stock-copy, .text raw offset == VA - 0x400000).  Every address below
   was checked in the disassembly.  Records: 256 of 0x3D8 bytes; present +0x28, health +0x344, age +0x348
   (20 units = 1 villager year; child = under 280 = 0x118).

   TRIGGER (0x4237B3 .. 0x423ABE), rules
     LIFTED  0x4237F1  "a living villager of 14 or more exists" (0x43BCD0(1) != -1).  No event casts that
                       villager (ebp is dropped after the age test below), so it is a pure gate: the je that
                       skipped the whole event is re-aimed at 0x423816 (the family roll).  With no villager of
                       14 or more, the processed-age test is skipped too (it reads that villager's record and
                       would read record -1).
     KEPT    0x4237BD  the timer (is the event due) -- the Island Timer companion's hook, untouched.
     KEPT    0x4237D2  population (0x41CF90) above 0: an event needs a village.  KEPT-FOR-SAFETY too: with
                       nobody living, the encounter and crate pickers return -1.
     KEPT    0x423810  the drawn villager's age +0x348 == processed age +0x34C (still working off credited
                       time): it only delays the event until catch-up is done -- part of the timing, which
                       the feature does not change.
     KEPT    0x423818 / 0x42383A  the family weights (first event always an Encounter; then 20% Encounter,
                       40% Island, 40% Crate), the delays (+0x708 first, then (rand(12)+12) h), the counter
                       world+0x9E40.  The 0x41D110 branch is dead (always 0) and stays.
     No rescue events and no rescue rule exist in this game.

   ISLAND family (chooser 0x428470: rand(15) at 0x4284DB re-rolled until the case's check passes; class
   bytes 0x4286A0, handlers 0x428688)
     [0]  The Bad Little Monkey, [2] The Plague of Parrots, [5] The South Wind, [6] The Heat Wave,
     [7]  Isola Day Celebration, [8] Blessings Day Celebration, [10] The Good Little Monkey,
     [11] The Greedy Little Monkey, [13] The North Wind, [14] The Helpful Honeybees:
          no condition in the stock game (class 0 -> 0x428671); nothing to lift.
     [3]  A Plague of Locusts
          LIFTED  0x42861D  Farming technology (world+0xA2E4) at level 2 or more (jl re-roll -> six nops).
     [4]  The Measles Epidemic
          KEPT (casting)  0x4284FA..0x42860E  a living child under 14 (present, health > 0, age < 0x118):
                          every child falls ill, so the event needs one.  Its result reaches the shared je at
                          0x42866B, which is why the Barrel's lift is made at the call, not at that je.
     [9]  The Big Wave
          KEPT (puzzle)   0x428644  the beach clean-up puzzle solved (byte world+0x9FB8 == 1): the wave
                          covers the cleaned beach again and clears that flag.
     [12] The Barrel O` Babies
          LIFTED  0x428664  the room check 0x43A1A0 (population below 90 -- or the population mode's cap --
                          and huts 1/2/3 at 15/25/50 people): the call becomes "mov al, 1" + nops, so the
                          test al,al / je at 0x42866B passes.  0x43A1A0 itself is shared with conception and
                          is not touched.
          KEPT-FOR-SAFETY the villager table (256 records): the maker 0x43C350 has no bound of its own; every
                          toddler allocation (0x428263, 0x4282C6, 0x4282E3, 0x42833C, 0x428359, 0x428376) goes
                          through the always-applied record guards in data/builds.json safety_patches, which
                          make a toddler only while a record is free (else -1, nothing made).  Not touched.
     [1]  A Mighty Storm: developer-dead (class 5 = the re-roll); not a condition, stays dead (the patcher's
          Restore Missing Island Events owns it, with its own stored-food test, untouched).

   ENCOUNTER family (chooser 0x418920: rand(16) at 0x418932 re-rolled until the class check passes; class
   bytes 0x4189A4, handlers 0x418990; subject 0x43BCD0(0), any living villager, unless noted)
     [64] The Trapped Whale
          LIFTED  0x41895B  Spirituality technology (world+0xA2BC) below level 3 (jge re-roll -> nops).
          KEPT-FOR-SAFETY none needed: the "free the whale" result caps the level at 3 (0x4193F4), so at level
                          3 that answer changes nothing.
     [68] The Visitor
          LIFTED  0x41896F  Medicine technology (world+0xA2D4) below level 3 (jge re-roll -> nops).
          KEPT-FOR-SAFETY none needed: the "gather samples" result caps the level at 3 (0x41981B).
     [71] The Troubled Child
          KEPT (casting)  0x418977 (0x43BE70 != -1) and 0x418DCB: a living child under 14 is the subject.
     [73] The Suspicious Monkey
          KEPT (casting)  0x418977 (0x43BE70 != -1, the same class 3 as The Troubled Child): the text is about
                          a child ("Little * ...", "the crying child").  The stock subject itself is drawn
                          with 0x43BCD0(0), any living villager (0x418F25); reported, not changed.
     [65] The Strange Berries, [66] The Old Drum, [67] The Mysterious Face, [70] A Mysterious Vial (red),
     [72] A Mysterious Vial (blue), [74] The Wild Mushroom, [75] The Black Pearl, [76] The Dream,
     [77] The Moth, [78] The Book, [79] The Brass Compass:
          no condition (class 1 -> 0x418987); KEPT (casting): a living villager as the subject.
     [69] The Furry Food: developer-dead (class 4 = the re-roll); stays dead (Restore Missing Island Events).
     Result-time room checks (not event conditions, unchanged): The Mysterious Face's newcomer 0x419700 (a
     safety-patch site with a free-record guard).

   CRATE family (0x42D0E0 -> 0x42AFF0: strength rand(100) at 0x42B00C, one rand(9) at 0x42B03E, no re-roll)
     [128]..[136] the seven crates and three vials: no condition in the stock game; KEPT (casting): a living
          villager (0x43BCD0(0)) as the subject.  The watertight crate's room check 0x42C358 is in its result
          (babies only with room when opened; the allocations behind it are record-guarded) and is unchanged.

   INANIMATE OBJECTS
     A New Home keeps no object in the villager table: no totem, statue or similar record kind exists (the
     only special villager is the Golden Child, +0x36C == 0xC7, a living villager).  The one non-living record
     is a body (present, health 0 or less).  The pickers 0x43BCD0 (0x43BCF0..0x43BCFD) and 0x43BE70
     (0x43BE90..0x43BE9D) and the measles scan (0x428510..0x42851C) all need present AND health > 0, so a body
     is never cast; none of the sites below touch them.  Stock, reported only: The Black Pearl's "share" adds
     health to all 256 records with no present or health test (0x41A050..0x41A09B), so an unburied body can
     come back.

   Collisions checked (+-12 bytes) against native/ (island timer 0x4237BD..0x4237C8, Story hooks 0x423818,
   0x42383A, 0x4284DB, 0x4284EC, 0x418932, 0x418941, Restore table bytes 0x42869C, 0x4189A0) and every
   data/*.json patch (builds.json population modes and safety patches): none. */

static const ns_site NS_VV1_SITES[] = {
    /* trigger: no living villager of 14 or more -> go on to the family roll instead of skipping the event
       (je 0x423ABE -> je 0x423816; ZF from cmp ebp,-1 at 0x4237EC, the mov between keeps flags) */
    { 0x4237F1u, 6, { 0x0F, 0x84, 0xC7, 0x02, 0x00, 0x00 }, { 0x0F, 0x84, 0x1F, 0x00, 0x00, 0x00 } },
    /* A Plague of Locusts: Farming >= 2 (jl 0x4284D6 -> nops) */
    { 0x42861Du, 6, { 0x0F, 0x8C, 0xB3, 0xFE, 0xFF, 0xFF }, { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 } },
    /* The Barrel O` Babies: room check call 0x43A1A0 -> mov al, 1 (test al,al / je at 0x42866B passes) */
    { 0x428664u, 5, { 0xE8, 0x37, 0x1B, 0x01, 0x00 }, { 0xB0, 0x01, 0x90, 0x90, 0x90 } },
    /* The Trapped Whale: Spirituality < 3 (jge 0x418930 -> nops) */
    { 0x41895Bu, 2, { 0x7D, 0xD3 }, { 0x90, 0x90 } },
    /* The Visitor: Medicine < 3 (jge 0x418930 -> nops) */
    { 0x41896Fu, 2, { 0x7D, 0xBF }, { 0x90, 0x90 } },
};

#define NS_VV1_COUNT (sizeof NS_VV1_SITES / sizeof NS_VV1_SITES[0])
