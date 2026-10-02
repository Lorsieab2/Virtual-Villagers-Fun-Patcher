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
    if (*(int *)(world + VV1_EVENT_COUNT_FIELD) == 0) {
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
   is no sex check in A New Home's delivery (0x42E900). */
static int c1_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *array = VV1_ARRAY();
    unsigned char *world = VV1_WORLD();
    unsigned char *r = c1_record(index);
    int babies = 0;
    int age;
    if (*(int *)(r + 0x358) != 0 || *(int *)(r + 0x348) < 360) {
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

static const char *const C1_BEHAVIOURS[] = {
    "Stops what they are doing", "Dances", "Goes swimming", "Relaxes",
    "Recovers fully (cured, full health)"
};

/* Each is what a stock event does to a villager: the AI reset 0x439470;
   Blessings Day's dance 0x443FA0(idx, 9) (0x419D2E); the Heat Wave's swim
   0x444990(idx, 1) and rest 0x4410C0(idx) (0x428067); the healer's cure
   (sick 0) with full health (100, the game's own ceiling, 0x42EE4D). */
static int c1_behave(int index, int behaviour) {
    unsigned char *array = VV1_ARRAY();
    unsigned char *r = c1_record(index);
    switch (behaviour) {
    case 0: TC1(0x439470u, array, index); return 1;
    case 1: TC2(0x443FA0u, array, index, 9); return 1;
    case 2: TC2(0x444990u, array, index, 1); return 1;
    case 3: TC1(0x4410C0u, array, index); return 1;
    case 4:
        *(int *)(r + 0x354) = 0;
        *(int *)(r + 0x344) = 100;
        TC1(0x439470u, array, index);
        return 1;
    default: return 0;
    }
}

static const char *const C1_VILLAGE[] = {
    "Isola Day celebration (everyone celebrates)",
    "Blessings Day celebration (everyone celebrates)",
    "The beach is dirty again (as The Big Wave leaves it)",
};

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
    default: return 0;
    }
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

static const ce_adapter C1_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK
        | CAP_BEHAVIOUR | CAP_VILLAGE | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY,
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
    C1_BEHAVIOURS, 5,
    C1_VILLAGE, 3,
    "Not in A New Home:\r\n\r\n"
    "- Golden Child: only the game's own puzzle can make one (the creator's family "
    "0xC7 forces sex, age and looks, and the puzzle's own state would no longer agree).\r\n"
    "- Faction, Tribal Chief, Esteemed Elder, totems: A New Home has none.\r\n"
    "- Puzzle solved: no completion routine was found that can be called safely; only "
    "the dirty beach (as The Big Wave leaves it) is offered.\r\n"
    "- Likes and dislikes: the last word of the game's list (sleeping) is not offered "
    "(the game itself never uses it and its list reader can overrun on it).\r\n"
    "- The grave screen keeps the job a villager had when buried.",
    51, 14, 51, 0, 360,
    "Refills the berry bushes and, once the farm is producing, the crops.",
    "Your tribe gains %d food.", "Your tribe loses %d food.",
    "Your tribe gains %d tech points.", "Your tribe loses %d tech points.",
    c1_record, c1_listed, c1_arm_refusal, c1_room, c1_spawn, c1_kill, c1_vanish, c1_sicken,
    c1_conceive, NULL, c1_behave, c1_village, c1_food, c1_tech, c1_change_food, c1_change_tech,
    c1_refill, vv1_parents_supported, vv1_set_parents
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
