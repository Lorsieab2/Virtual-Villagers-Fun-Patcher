/* Custom Island Event: A New Home.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md, "Custom Island Event").
   The world is [0x48AEDC] and the villager array [0x48B614] (records at +0,
   stride 0x3D8, 256 of them).

   DELIVERY.  The island event's constructor 0x4286B0 calls its chooser
   0x428470 at 0x428777 (`call`, ECX = the event object, type, magnitude,
   ret 8) to pick, word and apply a case.  With a custom event armed, the
   companion's replacement for that call writes the custom title and
   description into the object's own text buffer (+0x277F, 0x270F bytes)
   and applies the changes instead; the game's own trigger has already
   rescheduled the next event, played the sound and counted it, and the
   game's own modal popup (0x401AB0) shows the text.  The Origins Barrel's
   delivery (magnitude 0x7F4B1A2C) always goes to the game's chooser.  The
   trigger's family rolls (story_vv1.inc) send an armed custom event to the
   island family.  The first island event of a village is always a visitor
   (0x42382C), so a custom event is refused until it has happened. */

#define VV1_ARRAY() (*(unsigned char **)(uintptr_t)0x48B614u)
#define VV1_WORLD() (*(unsigned char **)(uintptr_t)0x48AEDCu)
#define VV1_BARREL_MAGNITUDE 0x7F4B1A2C
#define VV1_SELECTED 0xAD34u

static unsigned char *c1_record(int index) {
    unsigned char *array = VV1_ARRAY();
    if (array == NULL || index < 0 || index >= VV1_RECORD_COUNT) {
        return NULL;
    }
    return array + (size_t)index * VV1_RECORD_STRIDE;
}

/* A living villager: occupied (+0x28 == 1, the game's own test at 0x4377A5)
   with health above 0 (a corpse keeps +0x28 until it is removed). */
static int c1_listed(const unsigned char *r) {
    return r[0x28] == 1 && *(const int *)(r + 0x344) > 0;
}

static const char *c1_arm_refusal(void) {
    unsigned char *world = VV1_WORLD();
    if (world == NULL || VV1_ARRAY() == NULL) {
        return "There is no village to have an island event.";
    }
    /* The first event is always a villager encounter: a question (shown by
       the encounters' own popup) may be it, a plain event may not. */
    if (*(int *)(world + VV1_EVENT_COUNT_FIELD) == 0 && !ce_refusal_for_choice) {
        return "A village's first island event is always a visitor. A custom island event "
               "can be queued once it has happened.";
    }
    if (!vv1_any_villager(VV1_ARRAY(), VV1_CHILD_AGE, -1)) {
        return "An island event needs a living adult in the village.";
    }
    return NULL;
}

/* A record the creator can use: it takes the first record whose occupied
   byte is 0 (0x43C374) and has no bound of its own, and a corpse keeps its
   record, so the population count alone can not say a record is free.
   (0x43A200 is NOT that search: it returns the first corpse.) */
static int c1_free_record(void) {
    int i;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        if (c1_record(i)[0x28] == 0) {
            return i;
        }
    }
    return -1;
}

/* The game's own room predicate 0x43A1A0 (population below the mode's cap
   and the housing gates) and a free record. */
static int c1_room(void) {
    unsigned char *array = VV1_ARRAY();
    if (array == NULL) {
        return 0;
    }
    return (TC0(0x43A1A0u, array) & 0xFF) != 0 && c1_free_record() >= 0;
}

static const ce_adapter C1_ADAPTER;


/* 0x43C350 (thiscall on the array: family, skill, value, sex, age; ret 0x14)
   -- the creator the Barrel, the stranger and births use.  Family -1 is the
   game's own random 1..50 (0xC7 would be the Golden Child, never passed). */
static int c1_spawn(const ce_spawn *s) {
    unsigned char *array = VV1_ARRAY();
    int index;
    if (array == NULL || !c1_room()) {
        return -1;
    }
    index = TC5(0x43C350u, array, -1, 0, 0, s->sex == STORY_SEX_MALE ? 1 : 2, s->age);
    if (index < 0 || index >= VV1_RECORD_COUNT) {
        return -1;
    }
    ce_apply_spawn_record(&C1_ADAPTER, c1_record(index), s);
    return index;
}

/* Death is health 0, exactly as old age (0x42EF05) and the "Taste the
   berries" event (0x419509) do; the corpse stays until the game removes it. */
static int c1_kill(int index) {
    unsigned char *r = c1_record(index);
    *(int *)(r + 0x344) = 0;
    return 1;
}

/* "Get a closer look... never heard from again" (0x41979D): the record is
   freed, and the selection cleared (0x4393E0) when it was the selected one. */
static int c1_vanish(int index) {
    unsigned char *r = c1_record(index);
    r[0x28] = 0;
    if (*(int *)(VV1_WORLD() + VV1_SELECTED) == index) {
        TC0(0x4393E0u, VV1_ARRAY());
    }
    return 1;
}

/* Sick is +0x354 = 1, as Measles (0x427DBD) writes it. */
static int c1_sicken(int index) {
    *(int *)(c1_record(index) + 0x354) = 1;
    return 1;
}

/* A pregnancy, written as the conception routine 0x43BBC0 writes it (the
   routine itself can not be called from here: the parentage trampolines on
   its exits read the father from the caller's frame):
     +0x358 = the carrier's processed age (+0x34C) -- non-zero means pregnant;
     +0x35C = 2 or 3 for twins or triplets, 0 for one baby;
     +0x394 = the father's +0x36C (0 for an unknown father);
     +0x38C / +0x390 = the inherited skill (none: 0 / 0);
   the world's Babies Made (+0x9E24, per baby), twins (+0x9E44) and triplets
   (+0x9E48) counters, the carrying pose (0x439470), and the parentage log.
   Each baby only while the game's room predicate says there is room; there
   is no sex check in A New Home's delivery (0x42E900).

   The Golden Child's family 0xC7 is never part of a pregnancy: the delivery
   (0x42EF39) makes an extra Golden Child when +0x394 is 0xC7, and the baby
   takes the carrier's own family.  So a Golden Child neither carries nor
   fathers (stock: 0x42E5A4, the breeding predicate, refuses them). */
#define VV1_GOLDEN_FAMILY 0xC7

static int c1_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *array = VV1_ARRAY();
    unsigned char *world = VV1_WORLD();
    unsigned char *r = c1_record(index);
    int babies = 0;
    int age;
    if (*(int *)(r + 0x358) != 0 || *(int *)(r + 0x348) < 360
        || *(int *)(r + 0x36C) == VV1_GOLDEN_FAMILY
        || (father >= 0 && *(int *)(c1_record(father) + 0x36C) == VV1_GOLDEN_FAMILY)) {
        ++result->refused;
        return 0;
    }
    if (!(TC0(0x43A1A0u, array) & 0xFF)) {
        result->no_room_babies += litter;
        return 0;
    }
    age = *(int *)(r + 0x34C);
    *(int *)(r + 0x358) = age != 0 ? age : 1;
    *(int *)(r + 0x35C) = 0;
    *(int *)(r + 0x394) = father >= 0 ? *(int *)(c1_record(father) + 0x36C) : 0;
    *(int *)(r + 0x38C) = 0;
    *(int *)(r + 0x390) = 0;
    babies = 1;
    while (babies < litter && (TC0(0x43A1A0u, array) & 0xFF)) {
        ++babies;
        *(int *)(r + 0x35C) = babies;
    }
    result->no_room_babies += litter - babies;
    *(int *)(world + 0x9E24) += babies;
    if (babies == 2) {
        ++*(int *)(world + 0x9E44);
    } else if (babies == 3) {
        ++*(int *)(world + 0x9E48);
    }
    TC1(0x439470u, array, index);
    story_log_conception(1, array, r, father >= 0 ? c1_record(father) : NULL);
    return babies;
}

/* Every action starter is a thiscall on the villager array taking the
   villager's index (and, for a few, one more argument), called by the game's
   own idle pickers, job dispatcher, drop handler or events.  Offered: the
   ones that only look (walk, animate) or end by themselves; the jobs that
   give food or skill practice say so.  Never: puzzle actions, burial,
   pickups, embracing, or a starter no stock code calls. */
static const ce_action C1_BEHAVIOURS[] = {
    { "Stops what they are doing", ACT_STOP, 0x439470u, 0 },
    { "Dances (Blessings Day)", ACT_CALL_ARG, 0x443FA0u, 9 },
    { "Goes swimming", ACT_CALL_ARG, 0x444990u, 1 },
    { "Relaxes", ACT_CALL, 0x4410C0u, 0 },
    { "Recovers fully (cured, full health)", ACT_RECOVER, 0, 0 },
    { "Dances", ACT_CALL, 0x43F200u, 0 },
    { "Rain dancing", ACT_CALL, 0x4419A0u, 0 },
    { "Makes a party", ACT_CALL, 0x440590u, 0 },
    { "Exercises", ACT_CALL, 0x4411D0u, 0 },
    { "Does the laundry", ACT_CALL, 0x441A50u, 0 },
    { "Observes", ACT_CALL, 0x4408A0u, 0 },
    { "Unsure what to do (wanders)", ACT_CALL, 0x445AD0u, 0 },
    { "Goes indoors", ACT_CALL, 0x439DE0u, 0 },
    { "Runs away", ACT_CALL, 0x439EF0u, 0 },
    { "Shakes their head", ACT_CALL, 0x43A040u, 0 },
    { "Not feeling well (only looks it)", ACT_CALL, 0x441CC0u, 0 },
    { "Honors the dead", ACT_CALL, 0x4401E0u, 0 },
    { "Honors the Idol (once it is carved)", ACT_CALL, 0x442810u, 0 },
    { "Honors the temple (once it is restored)", ACT_CALL, 0x443D50u, 0 },
    { "Sees something unusual", ACT_CALL, 0x441750u, 0 },
    { "Curious about the rock", ACT_CALL, 0x43ED50u, 0 },
    { "Curious about the ruins", ACT_CALL, 0x43EF10u, 0 },
    { "Curious about the creek", ACT_CALL, 0x441620u, 0 },
    { "Curious about the field", ACT_CALL, 0x442E80u, 0 },
    { "Curious about the cactus", ACT_CALL, 0x445670u, 0 },
    { "Tries to push the boulder (no progress)", ACT_CALL, 0x440FA0u, 0 },
    { "Enjoys the lagoon", ACT_CALL, 0x43FF80u, 0 },
    { "Enjoys the garden (once it is grown)", ACT_CALL, 0x442DB0u, 0 },
    { "Admires the treasure (once it is found)", ACT_CALL, 0x4404B0u, 0 },
    { "Chases butterflies", ACT_CALL, 0x445840u, 0 },
    { "Drinks well water", ACT_CALL, 0x444B40u, 0 },
    { "Forages (Farming practice, food)", ACT_CALL, 0x441E10u, 0 },
    { "Plants or harvests crops (Farming practice)", ACT_CALL, 0x4439F0u, 0 },
    { "Waters the crops (Farming practice)", ACT_CALL, 0x445020u, 0 },
    { "Fishes (Farming practice, food; stock needs fishing)", ACT_CALL, 0x43F450u, 0 },
    { "Eats (uses food, restores health)", ACT_CALL, 0x43FAD0u, 0 },
    { "Fixes a hut (Building practice)", ACT_CALL, 0x440AD0u, 0 },
    { "Heals someone (Healing practice, cures nobody)", ACT_CALL, 0x445580u, 0 },
    { "Goes to school (children; stock needs the school)", ACT_CALL, 0x444AA0u, 0 },
};

/* The stop routine 0x439470 first (a starter appends to the step queue;
   live, without the stop the villager first finishes what it was doing),
   then the starter; the healer's cure (sick 0) with full health (100, the
   game's own ceiling, 0x42EE4D). */
static int c1_behave(int index, int behaviour) {
    unsigned char *array = VV1_ARRAY();
    unsigned char *r = c1_record(index);
    const ce_action *act;
    if (behaviour < 0 || behaviour >= (int)(sizeof C1_BEHAVIOURS / sizeof C1_BEHAVIOURS[0])) {
        return 0;
    }
    act = &C1_BEHAVIOURS[behaviour];
    if (act->kind == ACT_RECOVER) {
        *(int *)(r + 0x354) = 0;
        *(int *)(r + 0x344) = 100;
    }
    TC1(0x439470u, array, index);
    if (act->kind == ACT_CALL) {
        TC1(act->routine, array, index);
    } else if (act->kind == ACT_CALL_ARG) {
        TC2(act->routine, array, index, act->arg);
    }
    return 1;
}

/* ---- Pregnancy: none, or a different number of babies ------------------ */

/* "0 babies": as the delivery (0x42E900) and the Golden Child puzzle end a
   pregnancy -- +0x358 and the litter +0x35C cleared (the conception never
   writes +0x35C for one baby, so a stale 2 or 3 would turn the next single
   into twins or triplets), +0x3C = 0x13, and the AI reset 0x439470 for the
   pose the pregnancy set.  Babies Made is left as counted. */
static int c1_cancel(int index) {
    unsigned char *r = c1_record(index);
    if (*(int *)(r + 0x358) == 0) {
        return 0;
    }
    *(int *)(r + 0x358) = 0;
    *(int *)(r + 0x35C) = 0;
    *(int *)(r + 0x3C) = 0x13;
    TC1(0x439470u, VV1_ARRAY(), index);
    return 1;
}

/* The litter of a pregnancy (+0x35C: 0 one baby, 2 twins, 3 triplets; the
   delivery 0x42F011 makes a second baby for any non-zero value, so 1 is
   never written).  Each added baby only while the game's own room predicate
   0x43A1A0 says there is room (neither the creator nor the delivery checks).
   Returns the babies added. */
static int c1_relitter(int index, int litter, ce_result *result) {
    unsigned char *array = VV1_ARRAY();
    unsigned char *r = c1_record(index);
    int field = *(int *)(r + 0x35C);
    int babies = field == 3 ? 3 : field != 0 ? 2 : 1;
    int added = 0;
    if (litter < babies) {
        *(int *)(r + 0x35C) = litter == 1 ? 0 : litter;
        return 0;
    }
    while (babies < litter && (TC0(0x43A1A0u, array) & 0xFF)) {
        ++babies;
        ++added;
        *(int *)(r + 0x35C) = babies;
    }
    result->no_room_babies += litter - babies;
    return added;
}

/* ---- Revive ------------------------------------------------------------- */

/* A skeleton: occupied with health 0 or less (the Golden Child included). */
static int c1_skeleton(const unsigned char *r) {
    return r[0x28] == 1 && *(const int *)(r + 0x344) <= 0;
}

/* Death is health 0 alone (0x42EF05), so life is health again -- after the
   last-update time +0x340 is set to the game clock 0x402F70 (live: without
   it the first living tick ages the villager by the time spent dead) --
   then the AI reset.  Only while the game's own room predicate says the
   village has room. */
static int c1_revive(int index, int health, int cure) {
    unsigned char *array = VV1_ARRAY();
    unsigned char *r = c1_record(index);
    if (!(TC0(0x43A1A0u, array) & 0xFF)) {
        return -1;
    }
    *(int *)(r + 0x340) = TC0(0x402F70u, VV1_WORLD());
    *(int *)(r + 0x344) = health;
    if (cure) {
        *(int *)(r + 0x354) = 0;
    }
    TC1(0x439470u, array, index);
    return 1;
}

static const char *const C1_VILLAGE[] = {
    "Isola Day celebration (everyone celebrates)",
    "Blessings Day celebration (everyone celebrates)",
    "The beach is dirty again (as The Big Wave leaves it)",
    "A Golden Child appears (if the village has room)",
};

/* Hours since the village began, as every puzzle completion writes them:
   (the game clock 0x402F70 - the start [world+0x9E1C]) / 3600, at least 1
   (0x43AE40..0x43AE71). */
static int c1_hours(void) {
    unsigned char *world = VV1_WORLD();
    unsigned int now = (unsigned int)TC0(0x402F70u, world);
    unsigned int hours = (now - *(unsigned int *)(world + 0x9E1C)) / 3600u;
    return hours == 0 ? 1 : (int)hours;
}

/* The Golden Child, made exactly as the puzzle's drop (0x424242) makes him:
   the creator 0x43C350 with the Golden Child's family 0xC7 (which forces his
   sex, age, looks and skills, 0x43C7AF) and age 0x28, his last-update time
   the game clock; and, the first time, the puzzle's own latch [world+0xA008]
   and the hour he came [world+0x9E80] (the Cave's clock, 0x447A14: left 0,
   the Cave would open at once).  Only while the game's own room predicate
   says there is room. */
static int c1_golden_child(void) {
    unsigned char *array = VV1_ARRAY();
    unsigned char *world = VV1_WORLD();
    int index;
    if (!c1_room()) {
        return 0;
    }
    index = TC5(0x43C350u, array, VV1_GOLDEN_FAMILY, 0, 0, 0, 0x28);
    if (index < 0 || index >= VV1_RECORD_COUNT) {
        return 0;
    }
    *(int *)(c1_record(index) + 0x340) = TC0(0x402F70u, world);
    if (world[0xA008] == 0) {
        world[0xA008] = 1;
        *(int *)(world + 0x9E80) = c1_hours();
    }
    return 1;
}

/* Isola Day (0x4280B2) and Blessings Day: the village celebration
   0x4457D0(kind 3 / 7).  The Big Wave (0x42813D): the cleaned-beach state
   back to dirty, [world+0x9FB8] = [world+0x9FB4] = 0. */
static int c1_village(int which) {
    unsigned char *world = VV1_WORLD();
    switch (which) {
    case 0: TC1(0x4457D0u, VV1_ARRAY(), 3); return 1;
    case 1: TC1(0x4457D0u, VV1_ARRAY(), 7); return 1;
    case 2:
        world[0x9FB8] = 0;
        *(int *)(world + 0x9FB4) = 0;
        return 1;
    case 3: return c1_golden_child();
    default: return 0;
    }
}

/* ---- Puzzles ---------------------------------------------------------------

   Each puzzle is a byte flag (exactly 1 when solved: the Statistics screen
   sums them) in an 8-byte slot after its progress counter, and an hours
   field the Puzzles screen shows ("Completed in N hours"; a flag alone shows
   0 hours, seen live).  Solved writes what the game's own completion writes
   (progress at the threshold, the flag, the hours); unsolved puts back what
   a new village has, so builders and the puzzle's own route can solve it
   again.  The whole block is saved as it stands.  Verified live (2026-10-01):
   the layout, writes kept, no crash, the Cave's scenery following its flag
   both ways, the Puzzles screen's icons and text. */
#define C1P_NAV 1              /* the walk grid reads it: rebuilt now (0x414590) */
#define C1P_HOURS_ONCE 2       /* hours written only the first time (Beach, Treasure) */
#define C1P_HERBS 4            /* Herb Mastery: the four herb flags too */
#define C1P_CAVE 8             /* unsolve only outside the cave scene */
#define C1P_HUT2 16            /* unsolved: started (1) once 15 villagers live here */
#define C1P_HUT3 32            /* unsolved: started (1) once 28 villagers live here */

typedef struct {
    unsigned int flag;
    unsigned int progress;     /* 0 = none */
    int solved_progress;
    int unsolved_progress;
    unsigned int hours;
    int how;
} c1_puzzle;

static const ce_puzzle_def C1_PUZZLE_DEFS[] = {
    { "The Well", 1, 1, NULL },
    { "The Hut (the first small hut)", 1, 1,
      "Unsolved, the village keeps everyone it has, but makes no room for more." },
    { "The Beach", 1, 1, NULL },
    { "The School", 1, 1, NULL },
    { "The Lagoon", 1, 1, NULL },
    { "The Magic Fish of Fertility", 1, 1, NULL },
    { "The Cemetery", 1, 1, NULL },
    { "Herb Mastery", 1, 1, "Unsolved also forgets the four herbs, so it can be solved again." },
    { "The Garden", 1, 1, NULL },
    { "The Magic Plant of Life", 1, 1, "Solving it again needs The Butterflies solved." },
    { "The Temple", 1, 1, NULL },
    { "The Idol", 1, 1, NULL },
    { "The Butterflies", 1, 1,
      "Unsolved, only a living Golden Child dropped on the Garden can solve it again." },
    { "The Treasure", 1, 1, NULL },
    { "The Cave", 1, 1,
      "Unsolved is refused while you are inside the cave. Only a Golden Child opens it again." },
    { "The second small hut (not on the Puzzles screen)", 1, 1,
      "Unsolved, the village keeps everyone it has, but makes no room for more." },
    { "The third small hut (not on the Puzzles screen)", 1, 1,
      "Unsolved, the village keeps everyone it has, but makes no room for more." },
};

static const c1_puzzle C1_PUZZLES[] = {
    { 0xA058, 0xA054, 2, 0, 0x9EA8, 0 },
    { 0x9FE8, 0x9FE4, 250, 125, 0x9E70, C1P_NAV },
    { 0x9FB8, 0x9FB4, 150, 0, 0x9E58, C1P_NAV | C1P_HOURS_ONCE },
    { 0xA050, 0xA04C, 1, 0, 0x9EA4, 0 },
    { 0x9FB0, 0x9FAC, 350, 0, 0x9E54, C1P_NAV },
    { 0xA090, 0, 0, 0, 0x9EC4, 0 },
    { 0xA000, 0, 0, 0, 0x9E7C, 0 },
    { 0xA080, 0, 0, 0, 0x9EBC, C1P_HERBS },
    { 0x9FC0, 0x9FBC, 200, 0, 0x9E5C, 0 },
    { 0xA098, 0xA094, 300, 0, 0x9EC8, 0 },
    { 0x9FE0, 0x9FDC, 1000, 0, 0x9E6C, C1P_NAV },
    { 0x9FD8, 0x9FD4, 1350, 0, 0x9E68, 0 },
    { 0xA088, 0, 0, 0, 0x9EC0, 0 },
    { 0x9FC8, 0x9FC4, 800, 0, 0x9E60, C1P_HOURS_ONCE },
    { 0x9FA8, 0, 0, 0, 0x9E50, C1P_NAV | C1P_CAVE },
    { 0x9FF0, 0x9FEC, 400, 0, 0x9E74, C1P_NAV | C1P_HUT2 },
    { 0x9FF8, 0x9FF4, 600, 0, 0x9E78, C1P_NAV | C1P_HUT3 },
};

#define C1_PUZZLE_COUNT ((int)(sizeof C1_PUZZLES / sizeof C1_PUZZLES[0]))

static int c1_puzzle_solved(int which) {
    unsigned char *world = VV1_WORLD();
    if (world == NULL || which < 0 || which >= C1_PUZZLE_COUNT) {
        return 0;
    }
    return world[C1_PUZZLES[which].flag] != 0;
}

static int c1_population(void) {
    int i;
    int n = 0;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        if (c1_listed(c1_record(i))) {
            ++n;
        }
    }
    return n;
}

static int c1_puzzle_set(int which, int solved) {
    static const unsigned int herbs[4] = { 0xA060, 0xA068, 0xA070, 0xA078 };
    unsigned char *world = VV1_WORLD();
    const c1_puzzle *p;
    int k;
    if (world == NULL || which < 0 || which >= C1_PUZZLE_COUNT) {
        return 0;
    }
    p = &C1_PUZZLES[which];
    if (solved) {
        if (p->progress != 0) {
            *(int *)(world + p->progress) = p->solved_progress;
        }
        if (p->how & C1P_HERBS) {
            for (k = 0; k < 4; ++k) {
                world[herbs[k]] = 1;
            }
        }
        world[p->flag] = 1;
        if (!(p->how & C1P_HOURS_ONCE) || *(int *)(world + p->hours) == 0) {
            *(int *)(world + p->hours) = c1_hours();
        }
    } else {
        if ((p->how & C1P_CAVE) && *(int *)(world + 0xACB4) == 0x14) {
            return 0;                  /* the player is inside the cave */
        }
        world[p->flag] = 0;
        if (p->progress != 0) {
            int value = p->unsolved_progress;
            if (p->how & C1P_HUT2) {
                value = c1_population() >= 15 ? 1 : 0;
            } else if (p->how & C1P_HUT3) {
                value = c1_population() >= 28 ? 1 : 0;
            }
            *(int *)(world + p->progress) = value;
        }
        if (p->how & C1P_HERBS) {
            for (k = 0; k < 4; ++k) {
                world[herbs[k]] = 0;
            }
        }
    }
    if (p->how & C1P_NAV) {
        /* The walk grid, rebuilt as the hut and cave completions rebuild it
           (0x43A7E4); otherwise it follows at the next scene change. */
        void *nav = *(void **)(VV1_ARRAY() + 0x3E014);
        if (nav != NULL) {
            TC0(0x414590u, nav);
        }
    }
    return 1;
}

/* ---- Food sources ------------------------------------------------------- */

static const ce_value_def C1_VALUES[] = {
    { "Berry bushes", 0, 5000,
      "One store for every bush; a new village has 1900, and the bushes look full from 1300." },
    { "Crops", 0, 800,
      "Only once the farm is producing (Farming level 2). The game's own ceiling is 800." },
};

static int c1_value_get(int which) {
    unsigned char *world = VV1_WORLD();
    if (world == NULL) {
        return -1;
    }
    if (which == 0) {
        return *(int *)(world + 0xA2F4);
    }
    if (which == 1) {
        return *(int *)(world + 0xA2E4) >= 2 ? *(int *)(world + 0xA2F8) : -1;
    }
    return -1;
}

/* Plain writes, as the game's own events change them (North Wind 0x4283B5,
   Locusts 0x427F73); seen live: the bushes' art follows within seconds and
   the crops' too (the game caps crops at 800 itself). */
static int c1_value_set(int which, int amount) {
    unsigned char *world = VV1_WORLD();
    if (c1_value_get(which) < 0) {
        return 0;
    }
    *(int *)(world + (which == 0 ? 0xA2F4 : 0xA2F8)) = amount;
    return 1;
}

static int c1_food(void) { return *(int *)(VV1_WORLD() + 0xA2EC); }
static int c1_tech(void) { return *(int *)(VV1_WORLD() + 0xA2FC); }

/* Written directly, as the stock events change them (0x427D00): a call to
   the adders 0x41D140 / 0x41D120 would go through the Origins doubler.  A
   gain also counts in the lifetime totals (+0x9E28 food, +0x9E20 tech) as
   the adders count it. */
static void c1_change_food(int op, int amount) {
    unsigned char *world = VV1_WORLD();
    int before = *(int *)(world + 0xA2EC);
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(world + 0xA2EC) = after;
    if (after > before) {
        *(int *)(world + 0x9E28) += after - before;
    }
}

static void c1_change_tech(int op, int amount) {
    unsigned char *world = VV1_WORLD();
    int before = *(int *)(world + 0xA2FC);
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(world + 0xA2FC) = after;
    if (after > before) {
        *(int *)(world + 0x9E20) += after - before;
    }
}

/* The berry bushes ([world+0xA2F4], a new village starts at 1900) and, once
   the farm is producing (stage [world+0xA2E4] >= 2), the crops (+0xA2F8, the
   game's own ceiling 800): the stores North Wind (0x428388) and the
   Honeybees (0x4283DF) add to. */
static int c1_refill(void) {
    unsigned char *world = VV1_WORLD();
    if (*(int *)(world + 0xA2F4) < 1900) {
        *(int *)(world + 0xA2F4) = 1900;
    }
    if (*(int *)(world + 0xA2E4) >= 2) {
        *(int *)(world + 0xA2F8) = 800;
    }
    return 1;
}

/* A New Home keeps a villager's parents only in the Show Parents
   companion's sidecar ("VVFP VV1 Parentage.dll", shipped with that row):
   its Vv1ParentageSetParents writes them there.  Without the row there is
   nowhere to keep them, and the option is disabled. */
typedef int (__stdcall *vv1_set_parents_fn)(int index, const char *father, int father_head,
                                            int father_body, const char *mother, int mother_head,
                                            int mother_body);

static vv1_set_parents_fn vv1_parents_export(void) {
    static int state;
    static vv1_set_parents_fn set_parents;
    if (state == 0) {
        char path[MAX_PATH];
        char *slash;
        DWORD n = GetModuleFileNameA(NULL, path, MAX_PATH);
        HMODULE module;
        state = -1;
        slash = n > 0 && n < MAX_PATH ? strrchr(path, '\\') : NULL;
        if (slash != NULL
            && (size_t)(slash + 1 - path) + sizeof("VVFP VV1 Parentage.dll") <= sizeof path) {
            lstrcpyA(slash + 1, "VVFP VV1 Parentage.dll");
            module = LoadLibraryA(path);
            if (module != NULL) {
                set_parents = (vv1_set_parents_fn)GetProcAddress(module, "Vv1ParentageSetParents");
                if (set_parents != NULL) {
                    state = 1;
                }
            }
        }
    }
    return state == 1 ? set_parents : NULL;
}

static int vv1_parents_supported(void) {
    return vv1_parents_export() != NULL;
}

static int vv1_set_parents(int index, const ce_change *c) {
    vv1_set_parents_fn set_parents = vv1_parents_export();
    if (set_parents == NULL) {
        return 0;
    }
    return set_parents(index, c->father_name, c->father_head == CE_KEEP ? -1 : c->father_head,
                       c->father_body == CE_KEEP ? -1 : c->father_body, c->mother_name,
                       c->mother_head == CE_KEEP ? -1 : c->mother_head,
                       c->mother_body == CE_KEEP ? -1 : c->mother_body);
}

static const char *const C1_SKILLS[] = { "Parenting", "Building", "Farming", "Healing", "Research" };

/* The game's own rand(bound) (cdecl, 0..bound-1), for a question's roll. */
static int c1_rand_below(int n) {
    return VV1_RAND(n);
}

static const ce_adapter C1_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK
        | CAP_BEHAVIOUR | CAP_VILLAGE | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY | CAP_VALUES
        | CAP_PUZZLES | CAP_CANCEL | CAP_RELITTER | CAP_REVIVE | CAP_CHOICE,
    "A New Home",
    280, 40, 1100,
    VV1_RECORD_COUNT, 0x1C,
    0x370, 0x350, 0x348, 0x360, 0x364, 0x398, 0x3A8, 0x3BC,
    1, 2,
    4, 46,
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,"
    "the dark,caves,herbs,berries,snakes,wind,rocks,heights,the ocean,playing,"
    "exploring,blue,green,red,yellow,drums,bushes,bananas,coconuts,sand,"
    "sunlight,rough wood,crab meat,whale meat,fish,fruit,papaya,flies,"
    "swimming,running,learning,dancing,monkeys,parrots,work,lifting,surprises",
    20, 20,
    5, 0, C1_SKILLS,
    0, 0, 28, 0, 0, 0, 0,
    NULL, 0,
    C1_BEHAVIOURS, (int)(sizeof C1_BEHAVIOURS / sizeof C1_BEHAVIOURS[0]),
    C1_VILLAGE, 4,
    "Not in A New Home:\r\n\r\n"
    "- Turning a villager into the Golden Child: the game snaps their age to 5 years at "
    "the next moment and keeps their old looks, sex and skills. A new Golden Child can "
    "appear instead (village changes).\r\n"
    "- The Golden Child puzzle: marked alone it leaves no Golden Child, so the Cave and "
    "The Butterflies could never be solved; a new Golden Child solves it.\r\n"
    "- Faction, Tribal Chief, Esteemed Elder, totems: A New Home has none.\r\n"
    "- The unborn baby's father: A New Home keeps no father on a pregnancy (only his "
    "family number, which is never shown).\r\n"
    "- Actions that solve or advance a puzzle, burying, picking things up and embracing.\r\n"
    "- Likes and dislikes: the last word of the game's list (sleeping) is not offered "
    "(the game itself never uses it and its list reader can overrun on it).\r\n"
    "- Revive: buried villagers (their record is gone) and skeletons that have already "
    "crumbled away.\r\n"
    "- The grave screen keeps the job a villager had when buried.",
    51, 14, 51, 0, 360,
    "Refills the berry bushes and, once the farm is producing, the crops.",
    "Your tribe gains %d food.", "Your tribe loses %d food.",
    "Your tribe gains %d tech points.", "Your tribe loses %d tech points.",
    c1_record, c1_listed, c1_arm_refusal, c1_room, c1_spawn, c1_kill, c1_vanish, c1_sicken,
    c1_conceive, NULL, c1_behave, c1_village, c1_food, c1_tech, c1_change_food, c1_change_tech,
    c1_refill, vv1_parents_supported, vv1_set_parents,
    C1_VALUES, 2, c1_value_get, c1_value_set,
    C1_PUZZLE_DEFS, C1_PUZZLE_COUNT, c1_puzzle_solved, c1_puzzle_set,
    c1_cancel, c1_relitter, NULL,
    c1_skeleton, c1_revive,
    0, 0x358,
    /* The villager encounters' popup (0x41A460): lines of 49 characters,
       15 lines (the longest and tallest stock encounter texts, at its 450
       pixels); the result replaces the whole text, title included; labels
       of 34 characters (the longest stock label). */
    49, 15, 49, 15, 1, 34, c1_rand_below
};

/* ---- Delivery ----------------------------------------------------------- */

/* The replacement for `call 0x428470` at 0x428777 (thiscall, ret 8). */
static void __fastcall c1_choose(void *event, void *unused_edx, int type, int magnitude) {
    int strength;
    (void)unused_edx;
    if (magnitude == VV1_BARREL_MAGNITUDE) {
        /* The Origins Barrel of Babies: never a pick's outcome. */
        TC2(0x428470u, event, type, magnitude);
        return;
    }
    if (ce_deliver(1, (char *)event + 0x277F, 0x270F)) {
        return;
    }
    /* A pick of an island event: the event is chosen (the case roll) and
       applied inside this call, with this magnitude. */
    strength = vv1_island_strength();
    if (strength > 0) {
        magnitude = strength;
    }
    oc_island_begin(1);
    TC2(0x428470u, event, type, magnitude);
    oc_island_end(1);
}

/* ---- Two choices -----------------------------------------------------------

   A question is asked by the villager encounters' own popup.  The trigger
   (0x4237B3: rescheduled, sounded and counted as stock) builds the dialog on
   its stack with 0x41A460, whose setup call at 0x41A51F (0x4189E0, thiscall,
   returns AL; 0 closes the dialog at once) picks a variant and writes the
   question (+0x74), the two labels (+0x4E92 / +0x4F92, 0x100 bytes each), the
   variant (+0x5094, 0..15), the villager shown (+0x5098, -1 = none) and the
   popup's width (+0x60).  The ctor then sizes the popup ONCE, from the
   question's lines.  A click (handler 0x41A3D0) removes the two buttons,
   shows OK, stores 1 / 2 (first / second button) in +0x509C and calls the
   resolve 0x419380 at 0x41A444, which writes the result (+0x2783, drawn in
   place of the question) and makes the changes.

   The setup detour fills those fields for the asked question: the question
   padded to the tallest result either button can show (the popup is never
   resized), the labels, no villager, the stock width, and a variant out of
   range (16+: the stock resolve's jump-table bound returns without writing,
   so a missed dispatch changes nothing).  The resolve call is an outcomes
   scope call (story_outcomes.inc); oc_scope_enter hands it to
   c1_choice_resolve when ECX is the dialog remembered here.  The dialog is
   on the trigger's stack, so the next encounter reuses the address: it is
   forgotten after our resolve and at every setup that is not ours. */

#define C1_DLG_QUESTION 0x74u
#define C1_DLG_RESULT 0x2783u
#define C1_DLG_TEXT_BYTES 0x270F
#define C1_DLG_LABEL_FIRST 0x4E92u
#define C1_DLG_LABEL_SECOND 0x4F92u
#define C1_DLG_LABEL_BYTES 0x100
#define C1_DLG_VARIANT 0x5094u
#define C1_DLG_SUBJECT 0x5098u
#define C1_DLG_CHOICE 0x509Cu
#define C1_DLG_WIDTH 0x60u
#define C1_ENCOUNTER_WIDTH 0x1C2
#define CHOICE_VARIANT_NONE 0x7F4B1A2D     /* past every stock jump table */

static void *c1_choice_dialog;
static char c1_choice_title[CE_TITLE_BYTES];

/* The asked question of `game` into a VV1 / VV2 two-choice dialog: the
   question padded to the tallest result, the two labels.  The title is kept
   for a result that can not be written. */
static void choice_fill_dialog(int game, unsigned char *dialog, unsigned int question,
                               unsigned int first_label, unsigned int second_label, char *title) {
    static char tallest[4096];
    int lines = ce_choice_tallest(game, 0, tallest, sizeof tallest);
    int other = ce_choice_tallest(game, 1, tallest, sizeof tallest);
    const char *first = ce_choice_label(game, 0);
    const char *second = ce_choice_label(game, 1);
    const char *named = ce_choice_title(game);
    if (other > lines) {
        lines = other;
    }
    ce_pad_lines((char *)dialog + question, C1_DLG_TEXT_BYTES, lines);
    lstrcpynA((char *)dialog + first_label, first != NULL ? first : "", C1_DLG_LABEL_BYTES);
    lstrcpynA((char *)dialog + second_label, second != NULL ? second : "", C1_DLG_LABEL_BYTES);
    lstrcpynA(title, named != NULL ? named : "", CE_TITLE_BYTES);
}

/* The replacement for `call 0x4189E0` at 0x41A51F (thiscall, no stack
   arguments, AL = keep the dialog). */
static char __fastcall c1_choice_setup(void *dialog, void *unused_edx) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused_edx;
    if (!ce_choice_begin(1, (char *)d + C1_DLG_QUESTION, C1_DLG_TEXT_BYTES)) {
        c1_choice_dialog = NULL;
        return (char)TC0(0x4189E0u, dialog);
    }
    choice_fill_dialog(1, d, C1_DLG_QUESTION, C1_DLG_LABEL_FIRST, C1_DLG_LABEL_SECOND, c1_choice_title);
    *(int *)(d + C1_DLG_VARIANT) = CHOICE_VARIANT_NONE;
    *(int *)(d + C1_DLG_SUBJECT) = -1;
    *(int *)(d + C1_DLG_WIDTH) = C1_ENCOUNTER_WIDTH;
    d[C1_DLG_RESULT] = '\0';
    c1_choice_dialog = dialog;
    return 1;
}

/* The question's answer, in place of the resolve 0x419380 (thiscall, no
   stack arguments): +0x509C is 1 for the first button, 2 for the second. */
static void __fastcall c1_choice_resolve(void *dialog, void *unused_edx) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused_edx;
    c1_choice_dialog = NULL;
    if (!ce_choice_resolve(1, *(int *)(d + C1_DLG_CHOICE) - 1, (char *)d + C1_DLG_RESULT,
                           C1_DLG_TEXT_BYTES)) {
        /* Another village by now, or nothing asked: the title alone. */
        lstrcpynA((char *)d + C1_DLG_RESULT, c1_choice_title, C1_DLG_TEXT_BYTES);
    }
}

/* ---- Title ---------------------------------------------------------------

   The HUD (0x41F9B0) builds the selected villager's title in a 256-byte
   stack buffer and every branch joins at 0x41FD75 `lea edx,[esp+0x24]; push
   edx` before setting the label (0x40BB30, which copies it).  The detour
   replaces the text with the villager's custom title, if any. */
static void __cdecl c1_title(char *buffer) {
    unsigned char *world = VV1_WORLD();
    const char *custom;
    if (world == NULL) {
        return;
    }
    custom = titles_lookup(1, c1_record(*(int *)(world + VV1_SELECTED)));
    if (custom != NULL) {
        lstrcpynA(buffer, custom, VV_TITLE_BYTES);
    }
}

__declspec(naked) static void c1_title_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 0x20 + 0x24]
        push eax
        call c1_title
        add esp, 4
        popad
        lea edx, [esp + 0x24]
        push edx
        push 0x41FD7A
        ret
    }
}
