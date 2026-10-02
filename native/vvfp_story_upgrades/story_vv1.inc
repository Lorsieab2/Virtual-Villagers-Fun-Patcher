/* A New Home: Pick Island Event.  Included by vvfp_story_upgrades.c.

   A New Home's island-event trigger (main village update, 0x4237B3) chooses
   among three families with rand(100) rolls, then each family chooses its
   event with its own roll (every roll is `push bound; call 0x402F10`):

     0x423818  rand(100) < 20 -> the villager encounters (0x41A460).  The
               village's first island event ever skips this roll and is
               always an encounter.
     0x42383A  rand(100) < 50 -> the island events of 0x427CA0 (selector
               0x428470, magnitude clamp(population / 3, 1, 10)), otherwise
               the Mysterious Crate / Vial (0x42D0E0).
     0x4284DB  island events: rand(15) is the case; a case whose own
               condition fails is rolled again.
     0x418932  encounters: rand(16) is the variant; a variant whose own
               condition fails is rolled again.
     0x42B03E  crates and vials: rand(9) is the variant.

   A pick replaces exactly those rolls, ONCE each.  Both choosers re-roll a
   variant whose condition fails, so a value forced on every call would loop
   forever on an impossible event (island case 1 and encounter 5 always
   fail); forced once, a failed condition falls back to the game's own
   re-roll.  The chooser only offers events whose condition holds, so that
   fallback is the exception, not the route.  The trigger, magnitude, text,
   sound, event counter and rescheduling all run as stock.

   A pick stores (family << 6) | index as its slot.

   An armed Custom Island Event (story_c1.inc) answers the two family rolls
   with the island family; its own delivery is the island event's chooser
   call, so the case roll is never reached for it. */

#define VV1_FAMILY_ISLAND 0
#define VV1_FAMILY_ENCOUNTER 1
#define VV1_FAMILY_CRATE 2
#define VV1_SLOT_FAMILY(slot) ((slot) >> 6)
#define VV1_SLOT_INDEX(slot) ((slot) & 0x3F)

typedef int (__cdecl *vv1_rand_fn)(int bound);
#define VV1_RAND ((vv1_rand_fn)(uintptr_t)0x402F10u)

#define VV1_WORLD_GLOBAL 0x48AEDCu
#define VV1_VILLAGERS_GLOBAL 0x48B614u
#define VV1_RECORD_STRIDE 0x3D8u
#define VV1_RECORD_COUNT 256
#define VV1_COUNTDOWN 0xA300u
#define VV1_EVENT_COUNT_FIELD 0x9E40u
#define VV1_CLOCK 0x402F70u
#define VV1_CHILD_AGE 0x118

static int vv1_peek(void) {
    drop_lapsed_pick();
    if (pick_slot < 0 || pick_game != 1) {
        return -1;
    }
    return pick_slot;
}

/* The family an armed pick or custom event needs, as a slot, or -1. */
static int vv1_route(void) {
    int slot = vv1_peek();
    if (slot < 0 && ce_pending(1)) {
        slot = (VV1_FAMILY_ISLAND << 6) | 0x3F;
    }
    return slot;
}

/* 0x423818: rand(100), < 20 is an encounter. */
static int __cdecl vv1_family_roll(int bound) {
    int slot = vv1_route();
    if (slot < 0) {
        return VV1_RAND(bound);
    }
    return VV1_SLOT_FAMILY(slot) == VV1_FAMILY_ENCOUNTER ? 0 : bound - 1;
}

/* 0x42383A: rand(100), < 50 is the island events, otherwise a crate. */
static int __cdecl vv1_island_or_crate_roll(int bound) {
    int slot = vv1_route();
    if (slot < 0) {
        return VV1_RAND(bound);
    }
    return VV1_SLOT_FAMILY(slot) == VV1_FAMILY_ISLAND ? 0 : bound - 1;
}

static int vv1_event_roll(int family, int bound) {
    int slot = vv1_peek();
    if (slot < 0 || VV1_SLOT_FAMILY(slot) != family || VV1_SLOT_INDEX(slot) >= bound) {
        return VV1_RAND(bound);
    }
    pick_slot = -1;
    STORY_COUNT(delivered);
    last_failed_event = NULL;
    return VV1_SLOT_INDEX(slot);
}

static int __cdecl vv1_island_case_roll(int bound) { return vv1_event_roll(VV1_FAMILY_ISLAND, bound); }
static int __cdecl vv1_encounter_roll(int bound) { return vv1_event_roll(VV1_FAMILY_ENCOUNTER, bound); }
static int __cdecl vv1_crate_roll(int bound) { return vv1_event_roll(VV1_FAMILY_CRATE, bound); }

static story_detour vv1_detours[] = {
    { 0x423818u, 5, VV1_ROLL_FAMILY_BYTES, 1, (void *)vv1_family_roll },
    { 0x42383Au, 5, VV1_ROLL_ISLAND_OR_CRATE_BYTES, 1, (void *)vv1_island_or_crate_roll },
    { 0x4284DBu, 5, VV1_ROLL_ISLAND_CASE_BYTES, 1, (void *)vv1_island_case_roll },
    { 0x418932u, 5, VV1_ROLL_ENCOUNTER_BYTES, 1, (void *)vv1_encounter_roll },
    { 0x42B03Eu, 5, VV1_ROLL_CRATE_BYTES, 1, (void *)vv1_crate_roll },
};

/* ---- Conditions: each event's own condition, as the game evaluates it ----

   The world is [0x48AEDC] and the villager records [0x48B614] (active byte
   +0x28, health +0x344, age +0x348, stride 0x3D8). */
typedef char (__fastcall *vv1_pred_fn)(void *self, void *unused_edx);

static int vv1_any_villager(unsigned char *records, int min_age, int max_age) {
    int i;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        unsigned char *r = records + (size_t)i * VV1_RECORD_STRIDE;
        int age = *(int *)(r + 0x348);
        if (r[0x28] == 0 || *(int *)(r + 0x344) <= 0) {
            continue;
        }
        if (min_age >= 0 && age < min_age) {
            continue;
        }
        if (max_age >= 0 && age >= max_age) {
            continue;
        }
        return 1;
    }
    return 0;
}

static int vv1_possible(const story_event *e) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV1_WORLD_GLOBAL;
    unsigned char *records = *(unsigned char **)(uintptr_t)VV1_VILLAGERS_GLOBAL;
    int family = VV1_SLOT_FAMILY(e->slot);
    int index = VV1_SLOT_INDEX(e->slot);
    if (world == NULL || records == NULL) {
        return 0;
    }
    /* The trigger needs a living adult (0x4237DB), and the first island
       event of a village is always an encounter (0x42382C). */
    if (!vv1_any_villager(records, VV1_CHILD_AGE, -1)) {
        return 0;
    }
    if (*(int *)(world + VV1_EVENT_COUNT_FIELD) == 0 && family != VV1_FAMILY_ENCOUNTER) {
        return 0;
    }
    if (family == VV1_FAMILY_ISLAND) {
        switch (index) {
        case 3: return *(int *)(world + 0xA2E4) >= 2;
        case 4: return vv1_any_villager(records, -1, VV1_CHILD_AGE);
        case 9: return world[0x9FB8] == 1;
        case 12: return ((vv1_pred_fn)(uintptr_t)0x43A1A0u)(records, NULL) != 0;
        default: return 1;
        }
    }
    if (family == VV1_FAMILY_ENCOUNTER) {
        switch (index) {
        case 0: return *(int *)(world + 0xA2BC) < 3;
        case 4: return *(int *)(world + 0xA2D4) < 3;
        case 7: case 9: return vv1_any_villager(records, -1, VV1_CHILD_AGE);
        default: return 1;
        }
    }
    return 1;
}

static int vv1_island_pending(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV1_WORLD_GLOBAL;
    unsigned int countdown;
    if (world == NULL) {
        return 1;
    }
    countdown = *(unsigned int *)(world + VV1_COUNTDOWN);
    if (countdown == 0) {
        return 1;
    }
    return countdown - (unsigned int)((clock_fn)(uintptr_t)VV1_CLOCK)(world, NULL) <= 5u;
}

/* The Origins Island Event purchase (0x456B3B): countdown = clock + 5. */
static int vv1_arm(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV1_WORLD_GLOBAL;
    if (world == NULL) {
        return 0;
    }
    *(unsigned int *)(world + VV1_COUNTDOWN) =
        (unsigned int)((clock_fn)(uintptr_t)VV1_CLOCK)(world, NULL) + 5u;
    return 1;
}
