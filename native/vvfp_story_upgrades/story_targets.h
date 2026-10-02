/* Custom Island Event: who a change applies to.  Included by
   vvfp_story_upgrades.c; pure (no game memory), so it is the same in every
   game.

   The owner: "A Windows list of villagers with standard extended selection:
   Ctrl+click toggles, Shift+click selects a range.  There are also five group
   toggles named exactly: "All Adult Women" (adults only); "All Adult Men"
   (adults only); "All Females" (any age); "All Males" (any age); "All
   Children".  "Adult" uses each game's own adult boundary.  Toggles combine
   with each other and with individual picks, and a villager matched more than
   once counts once."

   The list's own extended selection (LBS_EXTENDEDSEL) gives Ctrl and Shift
   their standard meaning; this file only combines that selection with the
   toggles.  Each villager of the roster is visited once, so a villager that
   is both picked and matched by one or more toggles is in the result once. */
#ifndef VVFP_STORY_TARGETS_H
#define VVFP_STORY_TARGETS_H

#define STORY_T_ADULT_WOMEN 0x01u
#define STORY_T_ADULT_MEN 0x02u
#define STORY_T_FEMALES 0x04u
#define STORY_T_MALES 0x08u
#define STORY_T_CHILDREN 0x10u
#define STORY_T_ALL (STORY_T_ADULT_WOMEN | STORY_T_ADULT_MEN | STORY_T_FEMALES \
                     | STORY_T_MALES | STORY_T_CHILDREN)

#define STORY_SEX_MALE 1
#define STORY_SEX_FEMALE 2

/* One living villager as the target list shows it: the game's record index,
   its sex normalised to STORY_SEX_*, and its age in the game's own units. */
typedef struct {
    int index;
    int sex;
    int age;
} story_member;

/* Whether `m` is matched by any of the `toggles`.  `adult_age` is the game's
   own adult boundary (an age at or above it is an adult). */
static int story_toggle_matches(const story_member *m, unsigned int toggles, int adult_age) {
    int adult = m->age >= adult_age;
    if ((toggles & STORY_T_ADULT_WOMEN) && adult && m->sex == STORY_SEX_FEMALE) {
        return 1;
    }
    if ((toggles & STORY_T_ADULT_MEN) && adult && m->sex == STORY_SEX_MALE) {
        return 1;
    }
    if ((toggles & STORY_T_FEMALES) && m->sex == STORY_SEX_FEMALE) {
        return 1;
    }
    if ((toggles & STORY_T_MALES) && m->sex == STORY_SEX_MALE) {
        return 1;
    }
    if ((toggles & STORY_T_CHILDREN) && !adult) {
        return 1;
    }
    return 0;
}

/* The targets: every roster member that is picked (picked[i] != 0 for
   roster position i) or matched by a toggle, each once, in roster order.
   Writes at most `cap` record indices to `out`; returns how many. */
static int story_resolve_targets(const story_member *roster, int count,
                                 const unsigned char *picked, unsigned int toggles,
                                 int adult_age, int *out, int cap) {
    int i;
    int n = 0;
    toggles &= STORY_T_ALL;
    for (i = 0; i < count && n < cap; ++i) {
        if ((picked != 0 && picked[i]) || story_toggle_matches(&roster[i], toggles, adult_age)) {
            out[n++] = roster[i].index;
        }
    }
    return n;
}

#endif
