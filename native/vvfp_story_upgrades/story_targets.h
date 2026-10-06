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

   Added (owner, 2026-10-05): "Everyone", "All Female Children", "All Male
   Children" and "All Nursing" (every villager carrying or nursing a baby,
   male or female) in all five games; in New Believers also "All Heathens"
   and one toggle for each Heathen type the game draws (blue, red, orange,
   purple, Chief, the Heathen Mommy).  And "All Skeletons": every villager
   who has died and is not yet buried (the list shows them too, so they can
   be brought back; every other toggle is for the living only).

   The list's own extended selection (LBS_EXTENDEDSEL) gives Ctrl and Shift
   their standard meaning; this file only combines that selection with the
   toggles.  Each villager of the roster is visited once, so a villager that
   is both picked and matched by one or more toggles is in the result once. */
#ifndef VVFP_STORY_TARGETS_H
#define VVFP_STORY_TARGETS_H

#define STORY_T_ADULT_WOMEN 0x0001u
#define STORY_T_ADULT_MEN 0x0002u
#define STORY_T_FEMALES 0x0004u
#define STORY_T_MALES 0x0008u
#define STORY_T_CHILDREN 0x0010u
#define STORY_T_EVERYONE 0x0020u
#define STORY_T_FEMALE_CHILDREN 0x0040u
#define STORY_T_MALE_CHILDREN 0x0080u
#define STORY_T_NURSING 0x0100u
#define STORY_T_HEATHENS 0x0200u
#define STORY_T_BLUE_HEATHENS 0x0400u
#define STORY_T_RED_HEATHENS 0x0800u
#define STORY_T_ORANGE_HEATHENS 0x1000u
#define STORY_T_PURPLE_HEATHENS 0x2000u
#define STORY_T_CHIEF_HEATHENS 0x4000u
#define STORY_T_HEATHEN_MOMMIES 0x8000u
#define STORY_T_SKELETONS 0x10000u
#define STORY_T_ALL 0x1FFFFu

#define STORY_SEX_MALE 1
#define STORY_SEX_FEMALE 2

/* What the game itself makes of a villager, for the list's label and the
   Heathen toggles (ce_adapter.kind).  STORY_KIND_NONE: nothing special. */
enum {
    STORY_KIND_NONE = 0,
    STORY_KIND_BELIEVER,          /* New Believers */
    STORY_KIND_HEATHEN_BLUE,
    STORY_KIND_HEATHEN_ORANGE,
    STORY_KIND_HEATHEN_RED,
    STORY_KIND_HEATHEN_PURPLE,
    STORY_KIND_HEATHEN_CHIEF,
    STORY_KIND_HEATHEN_MOMMY,
    STORY_KIND_RETIRED_CHIEF,     /* New Believers: a believer who was the Heathen Chief */
    STORY_KIND_GOLDEN_CHILD,      /* A New Home */
    STORY_KIND_ESTEEMED_ELDER,    /* The Lost Children */
    STORY_KIND_TRIBAL_CHIEF,      /* The Secret City */
    STORY_KIND_COUNT
};

/* One villager as the target list shows it: the game's record index, its
   sex normalised to STORY_SEX_*, its age in the game's own units, whether it
   carries or nurses a baby, its STORY_KIND_*, and whether it is a body
   awaiting burial (dead). */
typedef struct {
    int index;
    int sex;
    int age;
    int nursing;
    int kind;
    int dead;
} story_member;

static int story_is_heathen(int kind) {
    return kind >= STORY_KIND_HEATHEN_BLUE && kind <= STORY_KIND_HEATHEN_MOMMY;
}

/* Whether `m` is matched by any of the `toggles`.  `adult_age` is the game's
   own adult boundary (an age at or above it is an adult). */
static int story_toggle_matches(const story_member *m, unsigned int toggles, int adult_age) {
    static const struct {
        unsigned int bit;
        int kind;
    } TYPES[] = {
        { STORY_T_BLUE_HEATHENS, STORY_KIND_HEATHEN_BLUE },
        { STORY_T_RED_HEATHENS, STORY_KIND_HEATHEN_RED },
        { STORY_T_ORANGE_HEATHENS, STORY_KIND_HEATHEN_ORANGE },
        { STORY_T_PURPLE_HEATHENS, STORY_KIND_HEATHEN_PURPLE },
        { STORY_T_CHIEF_HEATHENS, STORY_KIND_HEATHEN_CHIEF },
        { STORY_T_HEATHEN_MOMMIES, STORY_KIND_HEATHEN_MOMMY },
    };
    int adult = m->age >= adult_age;
    int female = m->sex == STORY_SEX_FEMALE;
    int male = m->sex == STORY_SEX_MALE;
    int i;
    if (m->dead) {
        return (toggles & STORY_T_SKELETONS) != 0;
    }
    if ((toggles & STORY_T_EVERYONE)
        || ((toggles & STORY_T_ADULT_WOMEN) && adult && female)
        || ((toggles & STORY_T_ADULT_MEN) && adult && male)
        || ((toggles & STORY_T_FEMALES) && female)
        || ((toggles & STORY_T_MALES) && male)
        || ((toggles & STORY_T_CHILDREN) && !adult)
        || ((toggles & STORY_T_FEMALE_CHILDREN) && !adult && female)
        || ((toggles & STORY_T_MALE_CHILDREN) && !adult && male)
        || ((toggles & STORY_T_NURSING) && m->nursing)
        || ((toggles & STORY_T_HEATHENS) && story_is_heathen(m->kind))) {
        return 1;
    }
    for (i = 0; i < (int)(sizeof TYPES / sizeof TYPES[0]); ++i) {
        if ((toggles & TYPES[i].bit) && m->kind == TYPES[i].kind) {
            return 1;
        }
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
