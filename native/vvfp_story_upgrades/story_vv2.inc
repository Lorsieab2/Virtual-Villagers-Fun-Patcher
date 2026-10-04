/* The Lost Children: Pick Island Event.  Included by vvfp_story_upgrades.c.

   VV2's island-event trigger (in the village update owner 0x42E990) chooses
   among three families with two rand(100) rolls, then each family chooses its
   event with its own roll:

     0x42EF28  rand(100) < 20 -> family A, the two-choice events (0x41F570).
               The village's first island event ever skips this roll and is
               always family A.
     0x42EF4A  rand(100) < 50 -> family C, the single-result events (selector
               0x434570, kind 2, magnitude clamp(population / 3, 1, 10)),
               otherwise family B, the Mysterious Sack / Vial (0x437AC0).
     0x434607  family C: rand(28) is the case of 0x433600.  A case whose own
               condition fails is rolled again (up to 10 tries, then case 10).
     0x41F59D  family A: rand(22) is the event; index 21 or a failed condition
               is rolled again (up to 10 tries, then event 5).
     0x437B0E  family B: rand(8) is the sack or vial.

   A pick replaces exactly those rolls, once each, so the game's own trigger,
   magnitude, condition table, text, sound, event counter and rescheduling all
   run as stock.  Every call site keeps its cdecl `push bound; call; add esp,4`
   shape: only the call's target changes, to a function with the same
   signature that returns the stock random value whenever no pick is armed for
   that roll.

   A pick of family A, B or C stores (family << 6) | index as its slot.

   An armed Custom Island Event (story_c2.inc) answers the two family rolls
   with family C; its own delivery is family C's chooser call, so the case
   roll is never reached for it.  One with a question answers them with
   family A, whose setup call asks it (story_c2.inc, "Two choices"). */

#define VV2_FAMILY_C 0
#define VV2_FAMILY_A 1
#define VV2_FAMILY_B 2
#define VV2_SLOT_FAMILY(slot) ((slot) >> 6)
#define VV2_SLOT_INDEX(slot) ((slot) & 0x3F)

typedef int (__cdecl *rand_fn)(int bound);
#define VV2_RAND ((rand_fn)(uintptr_t)0x4031A0u)

/* The armed pick for VV2 without consuming it, or -1. */
static int vv2_peek(void) {
    drop_lapsed_pick();
    if (pick_slot < 0 || pick_game != 2) {
        return -1;
    }
    return pick_slot;
}

/* The family an armed pick or custom event needs, as a slot, or -1. */
static int vv2_route(void) {
    int slot = vv2_peek();
    if (slot < 0 && ce_pending(2)) {
        /* A question is asked by family A's two-button popup (story_c2.inc),
           a plain event by family C's single-result popup. */
        slot = ((ce_choice_pending(2) ? VV2_FAMILY_A : VV2_FAMILY_C) << 6) | 0x3F;
    }
    return slot;
}

/* 0x42EF28: rand(100), < 20 is family A. */
static int __cdecl vv2_family_roll(int bound) {
    int slot;
    oc_new_choice(2);
    slot = vv2_route();
    if (slot < 0) {
        return VV2_RAND(bound);
    }
    return VV2_SLOT_FAMILY(slot) == VV2_FAMILY_A ? 0 : bound - 1;
}

/* 0x42EF4A: rand(100), < 50 is family C, otherwise family B. */
static int __cdecl vv2_c_or_b_roll(int bound) {
    int slot;
    oc_new_choice(2);
    slot = vv2_route();
    if (slot < 0) {
        return VV2_RAND(bound);
    }
    return VV2_SLOT_FAMILY(slot) == VV2_FAMILY_C ? 0 : bound - 1;
}

/* The family's own event roll: the picked index, once, if the armed pick is
   of this family.  Taking it disarms the pick, so a condition that fails (the
   chooser only offers events whose condition holds) falls back to the
   family's own stock rerolls. */
/* ---- Unlocked picks (as story_vv1.inc) --------------------------------------- */
static int vv2_unlock_c;
static int vv2_unlock_a;

/* 0x434617 `cmp ebp, 0x2AD` (family C's case through its condition table);
   passed: 0x434835, the call that runs the case. */
__declspec(naked) static void vv2_unlock_c_stub(void) {
    __asm {
        cmp vv2_unlock_c, 0
        jne pass
        cmp ebp, 0x2AD
        push 0x43461D
        ret
    pass:
        mov vv2_unlock_c, 0
        push 0x434835
        ret
    }
}

/* 0x41F5A5 `cmp eax, 0x14; mov [esp+0x14], eax` (family A's event through
   its condition table); passed: the event stored, 0x41F694. */
__declspec(naked) static void vv2_unlock_a_stub(void) {
    __asm {
        cmp vv2_unlock_a, 0
        jne pass
        cmp eax, 0x14
        mov dword ptr [esp + 0x14], eax
        push 0x41F5AC
        ret
    pass:
        mov vv2_unlock_a, 0
        mov dword ptr [esp + 0x14], eax
        push 0x41F694
        ret
    }
}

/* ---- Restore Missing Island Events (its own row) ----------------------------

   The row points the single-result condition table (0x434868) entries of
   cases 18, 20 and 26 at its accept target 0x434822, and gives the empty
   case 4 a body (VV2_LORE_BODY at 0x42F032, runner table 0x4344F4[4]) whose
   rand(3) at VV2_LORE_PAGE_SITE picks one of three lore pages.  With the row
   the three restored events are ordinary events here, and the pages (slots
   28-30, past the case roll) can be picked: the case roll answers 4 and the
   page roll answers the page.  Without the row nothing here is installed. */
#define VV2_CONDITION_TABLE 0x434868u
#define VV2_RUNNER_TABLE 0x4344F4u
#define VV2_ACCEPT 0x434822u
#define VV2_LORE_HOST 4
#define VV2_LORE_FIRST 28
#define VV2_LORE_COUNT 3

/* Whether single-result case `index` is accepted by the chooser's own table
   (the row's edit of 18, 20 or 26). */
static int vv2_case_accepted(int index) {
    return read_u32(VV2_CONDITION_TABLE + 4u * (unsigned int)index) == VV2_ACCEPT;
}

/* Whether the row's case-4 body is there, read once before the page site is
   written (afterwards the call at the page site is this companion's). */
static int vv2_lore_state = -1;
static int vv2_lore_ready(void) {
    if (vv2_lore_state < 0) {
        vv2_lore_state = vv2_case_accepted(VV2_LORE_HOST)
            && read_u32(VV2_RUNNER_TABLE + 4u * VV2_LORE_HOST) == VV2_LORE_BODY_VA
            && mem_matches(VV2_LORE_BODY_VA, VV2_LORE_BODY, (int)sizeof VV2_LORE_BODY);
    }
    return vv2_lore_state;
}

/* The page a pick delivers, set by the case roll just before case 4 runs. */
static int vv2_page_pick = -1;
static int vv2_page_installed;

/* VV2_LORE_PAGE_SITE: rand(3) in the case-4 body. */
static int __cdecl vv2_page_roll(int bound) {
    int page = vv2_page_pick;
    vv2_page_pick = -1;
    if (page >= 0 && page < bound) {
        return page;
    }
    return VV2_RAND(bound);
}

/* Called once the game's sites are installed: points the page roll at
   vv2_page_roll when the row's body is there. */
static void vv2_install_page_roll(void) {
    unsigned char call[5];
    unsigned int rel;
    if (vv2_page_installed || !vv2_lore_ready()) {
        return;
    }
    rel = (unsigned int)((uintptr_t)vv2_page_roll - (VV2_LORE_PAGE_SITE + 5u));
    call[0] = 0xE8;
    memcpy(call + 1, &rel, 4);
    vv2_page_installed = mem_write(VV2_LORE_PAGE_SITE, call, 5);
}

static int vv2_event_roll(int family, int bound) {
    int slot;
    oc_reroll(2);
    slot = vv2_peek();
    if (slot >= 0 && family == VV2_FAMILY_C && VV2_SLOT_INDEX(slot) >= VV2_LORE_FIRST
        && VV2_SLOT_INDEX(slot) < VV2_LORE_FIRST + VV2_LORE_COUNT && vv2_page_installed) {
        /* A lore page: case 4 (accepted by the row's table), then its page. */
        vv2_page_pick = VV2_SLOT_INDEX(slot) - VV2_LORE_FIRST;
        pick_slot = -1;
        STORY_COUNT(delivered);
        last_failed_event = NULL;
        oc_delivered(2, NULL);
        return VV2_LORE_HOST;
    }
    if (slot < 0 || VV2_SLOT_FAMILY(slot) != family || VV2_SLOT_INDEX(slot) >= bound) {
        return VV2_RAND(bound);
    }
    if (oc_unlocked(2, slot)) {
        /* pass the event's own condition for this one roll */
        if (family == VV2_FAMILY_C) {
            vv2_unlock_c = 1;
        } else if (family == VV2_FAMILY_A) {
            vv2_unlock_a = 1;
        }
    }
    pick_slot = -1;
    STORY_COUNT(delivered);
    last_failed_event = NULL;
    oc_delivered(2, NULL);
    return VV2_SLOT_INDEX(slot);
}

static int __cdecl vv2_case_roll_c(int bound) { return vv2_event_roll(VV2_FAMILY_C, bound); }
static int __cdecl vv2_event_roll_a(int bound) { return vv2_event_roll(VV2_FAMILY_A, bound); }
static int __cdecl vv2_event_roll_b(int bound) { return vv2_event_roll(VV2_FAMILY_B, bound); }

static story_detour vv2_detours[] = {
    { 0x42EF28u, 5, VV2_ROLL_FAMILY_BYTES, 1, (void *)vv2_family_roll },
    { 0x42EF4Au, 5, VV2_ROLL_C_OR_B_BYTES, 1, (void *)vv2_c_or_b_roll },
    { 0x434607u, 5, VV2_ROLL_CASE_C_BYTES, 1, (void *)vv2_case_roll_c },
    { 0x41F59Du, 5, VV2_ROLL_EVENT_A_BYTES, 1, (void *)vv2_event_roll_a },
    { 0x437B0Eu, 5, VV2_ROLL_EVENT_B_BYTES, 1, (void *)vv2_event_roll_b },
    { 0x434617u, 6, VV2_UNLOCK_C_BYTES, 0, (void *)vv2_unlock_c_stub },
    { 0x41F5A5u, 7, VV2_UNLOCK_A_BYTES, 0, (void *)vv2_unlock_a_stub },
};

/* ---- Conditions: each event's own condition, as the game evaluates it ----

   The world is [0x4997BC] and the villager pool [0x499F24] (the same objects
   the Tech screen and the village update use).  The game's pure predicates
   are called; the villager pickers (0x44BAE0, 0x44BC80, 0x44C030, 0x44BE70)
   are NOT, because they consume the game's random generator, so their
   filters are repeated here as plain scans. */
#define VV2_WORLD_GLOBAL 0x4997BCu
#define VV2_POOL_GLOBAL 0x499F24u
#define VV2_RECORD_FIRST 0x30u
#define VV2_RECORD_STRIDE 0xE48Cu
#define VV2_RECORD_COUNT 256
#define VV2_COUNTDOWN 0x2EAE0u
#define VV2_EVENT_COUNT_FIELD 0x2E51Cu
#define VV2_CLOCK 0x403200u

typedef char (__fastcall *vv2_pred_fn)(void *self, void *unused_edx);
typedef int (__fastcall *vv2_count_fn)(void *self, void *unused_edx);

/* Living, occupied records matching: min_age (or -1), max_age_exclusive (or
   -1), sex (or 0), and a positive +0x510 field when need_510. */
static int vv2_any_villager(unsigned char *pool, int min_age, int max_age, int sex, int need_510) {
    int i;
    for (i = 0; i < VV2_RECORD_COUNT; ++i) {
        unsigned char *r = pool + VV2_RECORD_FIRST + (size_t)i * VV2_RECORD_STRIDE;
        int age = *(int *)(r + 0x500);
        if (r[0] == 0 || *(int *)(r + 0x4FC) <= 0) {
            continue;
        }
        if (min_age >= 0 && age < min_age) {
            continue;
        }
        if (max_age >= 0 && age >= max_age) {
            continue;
        }
        if (sex != 0 && *(int *)(r + 0x508) != sex) {
            continue;
        }
        if (need_510 && *(int *)(r + 0x510) <= 0) {
            continue;
        }
        return 1;
    }
    return 0;
}

/* The number of living villagers, by the Crystal Ball's own test (active
   byte +0x30 set and health +0x52C > 0; r points at +0x30). */
static int vv2_living_count(unsigned char *pool) {
    int i;
    int count = 0;
    for (i = 0; i < VV2_RECORD_COUNT; ++i) {
        unsigned char *r = pool + VV2_RECORD_FIRST + (size_t)i * VV2_RECORD_STRIDE;
        if (r[0] != 0 && *(int *)(r + 0x4FC) > 0) {
            ++count;
        }
    }
    return count;
}

/* The Lost Children's "Fix Vanilla Bugs" (vv2_fix_vanilla_bugs) makes The
   Crystal Ball (two-choice case 13) also need at least two living villagers,
   so the finder always has someone to trade places with.  Its chooser hook,
   0x41F636 `jmp 0x4215D0` in place of `setne bl; jmp 0x41F696`, tells a build
   with the fix from the base game, whose condition is only the adult. */
static const unsigned char VV2_CRYSTAL_BALL_FIX[5] = { 0xE9, 0x95, 0x1F, 0x00, 0x00 };

static int vv2_crystal_ball_fixed(void) {
    return mem_matches(0x41F636u, VV2_CRYSTAL_BALL_FIX, 5);
}

/* What any island event needs, whatever its own condition: a living adult
   for the trigger (0x44BAE0(1)), and the village's first island event is
   always a two-choice event.  An unlocked pick needs only this. */
static int vv2_base_possible(const story_event *e) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL;
    unsigned char *pool = *(unsigned char **)(uintptr_t)VV2_POOL_GLOBAL;
    if (world == NULL || pool == NULL) {
        return 0;
    }
    if (!vv2_any_villager(pool, 0x118, -1, 0, 0)) {
        return 0;
    }
    return *(int *)(world + VV2_EVENT_COUNT_FIELD) != 0 || VV2_SLOT_FAMILY(e->slot) == VV2_FAMILY_A;
}

static int vv2_possible(const story_event *e) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL;
    unsigned char *pool = *(unsigned char **)(uintptr_t)VV2_POOL_GLOBAL;
    int family = VV2_SLOT_FAMILY(e->slot);
    int index = VV2_SLOT_INDEX(e->slot);
    vv2_pred_fn graves = (vv2_pred_fn)(uintptr_t)0x426160u;
    vv2_pred_fn advanced = (vv2_pred_fn)(uintptr_t)0x4261D0u;
    vv2_count_fn population = (vv2_count_fn)(uintptr_t)0x425860u;
    vv2_pred_fn room = (vv2_pred_fn)(uintptr_t)0x44B310u;
    if (!vv2_base_possible(e)) {
        return 0;
    }
    if (family == VV2_FAMILY_C) {
        switch (index) {
        /* The Mosquito Swarm, The Dragonfly Migration, Science Awareness Day:
           the selector's condition table maps them to the never-valid
           0x434824 -- unless Restore Missing Island Events accepts them. */
        case 18: case 20: case 26: return vv2_case_accepted(index);
        /* The lore pages exist only with that row's case-4 body. */
        case 28: case 29: case 30: return vv2_page_installed;
        case 8: return graves(world, NULL) != 0;
        case 11: case 14: case 17: return advanced(world, NULL) != 0;
        case 15: return vv2_any_villager(pool, 0x168, -1, 0, 1) && advanced(world, NULL) != 0;
        case 16: return population(world, NULL) > 60;
        case 21: case 25: return room(pool, NULL) != 0;
        default: return 1;
        }
    }
    if (family == VV2_FAMILY_A) {
        switch (index) {
        case 0: return *(int *)(world + 0x2EA74) < 2;
        case 1: return *(int *)(world + 0x2EAA4) >= 250;
        case 2: return vv2_any_villager(pool, 0x118, -1, 2, 0);
        case 4: return room(pool, NULL) != 0;
        case 6: case 10: return vv2_any_villager(pool, -1, 0x118, 0, 0);
        case 13:
            return vv2_any_villager(pool, 0x118, -1, 0, 0)
                && (!vv2_crystal_ball_fixed() || vv2_living_count(pool) >= 2);
        case 14: return population(world, NULL) >= 2;
        case 18: return *(int *)(world + 0x2EA94) < 2;
        case 19: return vv2_any_villager(pool, 0x168, -1, 2, 0) && vv2_any_villager(pool, 0x168, -1, 1, 0);
        default: return 1;
        }
    }
    /* Family B needs a living villager to find the sack or vial. */
    return vv2_any_villager(pool, -1, -1, 0, 0);
}

static int vv2_island_pending(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL;
    unsigned int countdown;
    if (world == NULL) {
        return 1;
    }
    countdown = *(unsigned int *)(world + VV2_COUNTDOWN);
    if (countdown == 0) {
        return 1;
    }
    return countdown - (unsigned int)((clock_fn)(uintptr_t)VV2_CLOCK)(world, NULL) <= 5u;
}

/* The Origins Island Event purchase (0x494818): countdown = clock + 5. */
static int vv2_arm(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL;
    if (world == NULL) {
        return 0;
    }
    *(unsigned int *)(world + VV2_COUNTDOWN) =
        (unsigned int)((clock_fn)(uintptr_t)VV2_CLOCK)(world, NULL) + 5u;
    return 1;
}
