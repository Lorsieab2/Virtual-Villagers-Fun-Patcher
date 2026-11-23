/* The third word of companions: started by "VVFP More Companions.dll" (native/vvfp_more_companions), itself a
   second-word companion (native/shared/startup_companions_2.h), because the second word is nearly full (the owner,
   2026-11-17: the new multiplier sliders each need a companion of their own).

   The patcher writes the bits of the third-word companions a build ships, as one decimal number, into "VVFP More
   Companions.txt" beside them, and ships "VVFP More Companions.dll" with the build whenever that number is not 0
   (src/vv_fun_patcher.py, STARTUP_LOADER_COMPANIONS_3).  Bit i is VVFP_STARTUP_COMPANIONS_3[i].  The order is a
   contract with the patcher (pinned by tests/test_more_companions.py): APPEND ONLY -- never reorder, rename or remove
   an entry.

   Each is started as the other words' companions are: loaded by its full path from the patcher's folder, then its
   VvfpStartup(game, shipped) called with the FIRST word, a fault in it abandoned. */
#ifndef VVFP_STARTUP_COMPANIONS_3_H
#define VVFP_STARTUP_COMPANIONS_3_H

static const char *const VVFP_STARTUP_COMPANIONS_3[] = {
    /* Hungrier Villagers (all five games): a meal multiplier whose 2 x N is not whole food (0.1x, 0.3x, 1.7x ...)
       takes 2 x N food on average (the patcher window's slider, read from VVFP Meal Scale.txt beside it). */
    "VVFP Meal Scale.dll",
    /* The 0.1x-10x sliders (all five games; the owner, 2026-11-17), each reading its number from the .txt of
       its own name beside it (native/shared/slider_scale.h): Collectible and Mushroom Frequency, Food Gained per
       Food Source, Tech Point Gain Rate, Skill Practice Success Chance, Age and Nursing Timer Speed. */
    "VVFP Collectible Frequency.dll",
    "VVFP Food Gain.dll",
    "VVFP Tech Gain.dll",
    "VVFP Skill Success.dll",
    "VVFP Age Speed.dll",
    /* Fix Vanilla Bugs (A New Home, The Lost Children): herb study Healing practice (second word full: moved here at the v1.35.97 merge) */
    "VVFP Herb Study.dll",
    /* Village Solidarity (all five games): the village's 0-100 score (second word full: moved here at the v1.35.97 merge) */
    "VVFP Village Solidarity.dll",
    /* Cloth Sacks for Yellow Fruit (The Tree of Life) (second word full: moved here at the v1.35.97 merge) */
    "VVFP VV4 Cloth Sacks.dll",
    /* Up to 99 Cutting Tools/Soap/Cloth (The Tree of Life) (second word full: moved here at the v1.35.97 merge) */
    "VVFP VV4 Supply Cap.dll",
    /* Fix Vanilla Bugs (The Tree of Life): no tool used on an empty source (second word full: moved here at the v1.35.97 merge) */
    "VVFP VV4 Empty Sources.dll",
    /* Fog of Doom Lets Red and Orange Heathens Listen (New Believers): in the Fog of Doom, a believer dropped on a Heathen in
       the orange or red mask with Faith below -10 starts the stock listening. */
    "VVFP Fog Listening.dll",
    /* Fix Vanilla Bugs (The Tree of Life): the broken piers' ten hole sprites drawn from the owner's redrawn pictures
       (separate files in Images) instead of the stock ones (second word full: placed here at the v1.35.97 merge). */
    "VVFP VV4 Pier Holes.dll",
    /* Practicing Devotion Builds Faith and Divine Energy (New Believers): each Devotion skill check of a believer gives
       a 1 in 10 chance of Faith +1 and a separate 1 in 10 chance of Divine Energy +1 (the owner, 2026-11-21). */
    "VVFP Devotion Faith.dll",
    /* The four Heathen aging rows (New Believers): Heathens who age and die of old age, are replaced at once, and
       (the tribe row) have children; each row's flag file says which (the owner, 2026-11-22). */
    "VVFP Heathen Aging.dll",
    /* APPEND ONLY (see above). */
};
#define VVFP_STARTUP_COMPANION_COUNT_3 \
    (sizeof VVFP_STARTUP_COMPANIONS_3 / sizeof VVFP_STARTUP_COMPANIONS_3[0])

#endif /* VVFP_STARTUP_COMPANIONS_3_H */
