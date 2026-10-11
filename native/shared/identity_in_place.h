/* A villager whose likes or dislikes changed is still the same villager.

   The custom titles (custom_titles.h) and New Believers' Former Heathens
   (former_heathens.h) are kept by vv_title_identity: the name, likes and
   dislikes.  But the games DO change likes and dislikes -- island events
   (The Tree of Life's "Faces in the Night" gave Alapai new dislikes, and her
   title "Moon Mother" was dropped: seen live, v1.35.67), the Custom Island
   Event, the Mysterious Vial, the Crystal of Reflections, the Origins
   "Running" upgrades -- and the new identity then matched no stored entry:
   the sweep took the villager for somebody else and dropped what was kept
   for them.

   vv_roster_changed_in_place tells such a change from everything else
   between two looks at the whole roster (one identity per record, 0 for a
   record nobody is in), so the caller can carry each entry to the new
   identity at the moment it changes.  A record changed IN PLACE when:
     - it held somebody at both looks, under a different identity now;
     - what a likes / dislikes change leaves alone (`keep`: the name and the
       sex, never 0) is the same at both looks;
     - the age went on by 0..VV_IN_PLACE_AGE_STEP age units (a newborn put
       into a dead villager's freed record between two looks starts again
       from 0 -- never a few units after the dead villager's age);
   and only when, with those records taken as the same villagers, nothing
   else moved (vv_roster_moved over the WHOLE roster): a reload that packs
   the records down moves at least one villager into another record and
   empties the last, so even a namesake of the same sex and age who moved
   into a dead twin's record is never taken for her.  Any change that is
   not explained this way and is a move leaves every record unexplained:
   nothing is carried, nothing guessed.  A rename (the name changes) is not
   an in-place change here; the callers keep their own rename rule
   (mask_follow.h vv_roster_renamed).

   Pure: arrays in, flags out.  tests/test_custom_titles_persistence.py drives it
   through native/vvfp_story_upgrades/custom_titles_harness.c. */
#ifndef VV_IDENTITY_IN_PLACE_H
#define VV_IDENTITY_IN_PLACE_H

#include "mask_follow.h"

/* A year is 20 age units in every game; the looks are a frame apart. */
#define VV_IN_PLACE_AGE_STEP 20

/* Sets same[i] to 1 for each record whose villager stayed and only changed
   identity; returns how many (0 when none, or when anything else moved). */
static int vv_roster_changed_in_place(int n, const unsigned int *was, const unsigned int *was_keep,
                                      const int *was_age, const unsigned int *now,
                                      const unsigned int *now_keep, const int *now_age,
                                      unsigned char *same) {
    static unsigned int adjusted[VV_MASK_FOLLOW_MAX];
    int i, count = 0;
    if (n <= 0 || n > VV_MASK_FOLLOW_MAX) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        int step = now_age[i] - was_age[i];
        same[i] = (unsigned char)(was[i] != 0 && now[i] != 0 && was[i] != now[i] && was_keep[i] != 0
                                  && was_keep[i] == now_keep[i] && step >= 0
                                  && step <= VV_IN_PLACE_AGE_STEP);
        adjusted[i] = same[i] ? now[i] : was[i];
        count += same[i];
    }
    if (count == 0) {
        return 0;
    }
    if (vv_roster_moved(n, adjusted, now)) {
        for (i = 0; i < n; ++i) {
            same[i] = 0;
        }
        return 0;
    }
    return count;
}

/* What a likes / dislikes change leaves of a villager: the name (to its
   terminator, at most `capacity` bytes) and the sex dword.  Never 0. */
static unsigned int vv_identity_keep(const unsigned char *record, unsigned int name, unsigned int capacity,
                                     unsigned int sex) {
    unsigned int h = 2166136261u;
    unsigned int i;
    for (i = 0; i < capacity && record[name + i] != 0; ++i) {
        h = (h ^ record[name + i]) * 16777619u;
    }
    h = (h ^ 0xFFu) * 16777619u;
    for (i = 0; i < 4u; ++i) {
        h = (h ^ record[sex + i]) * 16777619u;
    }
    return h ? h : 1u;
}

#endif
