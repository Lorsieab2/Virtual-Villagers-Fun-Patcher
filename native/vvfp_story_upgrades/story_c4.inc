/* Custom Island Event: The Tree of Life.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md).  The villager manager is
   0x50E568; record i at 0x50E5AC + i*0x2E3C, 150 records.

   DELIVERY.  The island-event selector 0x418000 has chosen at 0x4180F7 (the
   Pick Island Event site): with a custom event armed, the changes are made
   and the presenter is handed the custom event object (story_objects.inc, a
   copy of the event base vtable 0x48C4EC) instead.  Its strings are ids
   0x32A / 0x32B, The Salty Air's, which have no event object and which no
   code names. */

#define C4_MANAGER 0x50E568u
#define C4_RECORDS 0x50E5ACu
#define C4_STRIDE 0x2E3Cu
#define C4_COUNT 150
#define C4_FOOD 0x4D6DD0u
#define C4_TECH 0x4D6F88u
#define C4_TITLE_ID 0x32A
#define C4_BODY_ID 0x32B
#define C4_STRING_TABLE 0x4DEA20u

static unsigned char *c4_record(int index) {
    if (index < 0 || index >= C4_COUNT) {
        return NULL;
    }
    return (unsigned char *)(uintptr_t)(C4_RECORDS + (unsigned int)index * C4_STRIDE);
}

/* Active, not a corpse (+0x1CC7), health above 0 -- 0x467980's test. */
static int c4_listed(const unsigned char *r) {
    return r[0x1CC4] != 0 && r[0x1CC7] == 0 && *(const int *)(r + 0x1C40) > 0;
}

/* Records in use (corpses keep theirs until buried) plus the babies on the
   way, against the 150 records. */
static int c4_demand(void) {
    int i;
    int n = 0;
    for (i = 0; i < C4_COUNT; ++i) {
        unsigned char *r = c4_record(i);
        if (r[0x1CC4] != 0) {
            ++n;
            if (*(int *)(r + 0x1C4C) != 0) {
                n += *(int *)(r + 0x1C50);
            }
        }
    }
    return n;
}

static const char *c4_arm_refusal(void) {
    int i;
    for (i = 0; i < C4_COUNT; ++i) {
        unsigned char *r = c4_record(i);
        if (c4_listed(r) && *(int *)(r + 0x1B8C) >= 0x118) {
            return NULL;
        }
    }
    return "An island event needs a living adult in the village.";
}

/* The game's own room predicate 0x468350 (the mode's cap, the housing
   gates) and the 150 records. */
static int c4_room(void) {
    return (TC0(0x468350u, C4_MANAGER) & 0xFF) != 0 && c4_demand() < C4_COUNT;
}

static const ce_adapter C4_ADAPTER;

/* 0x467D10 (thiscall on the manager: attribute, skill, value, sex, age; ret
   0x14) -- the creator the Daredevil Barrel uses.  Attribute -1 is the
   game's own random; sex 0 male, 1 female. */
static int c4_spawn(const ce_spawn *s) {
    int index;
    if (!c4_room()) {
        return -1;
    }
    index = TC5(0x467D10u, C4_MANAGER, -1, 0, 0, s->sex == STORY_SEX_MALE ? 0 : 1, s->age);
    if (index < 0 || index >= C4_COUNT) {
        return -1;
    }
    ce_apply_spawn_record(&C4_ADAPTER, c4_record(index), s);
    return index;
}

/* The stock island-event death: the villager's task stops and what it holds
   is dropped (0x468C60), then health 0 with cause -1 ("Unknown causes", as
   The Sealed Box 0x415D9E and The Medical Emergency write it) through
   0x46AF00 (thiscall on the health block +0x1C34; ret 8). */
static int c4_kill(int index) {
    unsigned char *r = c4_record(index);
    TC0(0x468C60u, r);
    TC2(0x46AF00u, r + 0x1C34, 0, -1);
    return 1;
}

/* The Sealed Box's disappearance (0x415D91): the same death, then the
   record's active byte cleared, so no corpse or grave is left. */
static int c4_vanish(int index) {
    unsigned char *r = c4_record(index);
    TC0(0x468C60u, r);
    TC2(0x46AF00u, r + 0x1C34, 0, -1);
    r[0x1CC4] = 0;
    return 1;
}

/* Sick is the byte +0x1C48, as the Fungi (0x4153F4) writes it. */
static int c4_sicken(int index) {
    c4_record(index)[0x1C48] = 1;
    return 1;
}

/* A pregnancy through the conception routine 0x45E7B0 (thiscall on the
   carrier: father attribute, skill, value, father's name, head, body,
   forced; ret 0x1C) with forced = 1, which writes every pregnancy field
   (+0x1C4C, +0x1C04..+0x1C0C, the father's name, head and body, the
   litter) without its own room check, log and Babies Made, so the litter
   can be the chosen one:
     the rolled litter's Twins [0x4D6E08] / Triplets [0x4D6E0C] count is
     taken back, the chosen litter set (each baby only while there is room)
     and counted, Babies Made [0x4D6DE8] += babies, the "baby / twins /
     triplets" achievement (0x412F90, ids 0x14-0x16) as forced = 0 gives it,
     and the parentage log as the routine's own trampoline writes it.
   An unknown father is "Unknown" with the carrier's own head and body.
   There is no sex check in the conception or the delivery (0x4687E4). */
static int c4_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *r = c4_record(index);
    unsigned char *f = father >= 0 ? c4_record(father) : NULL;
    const unsigned char *source = f != NULL ? f : r;
    int rolled;
    int babies;
    if (*(int *)(r + 0x1C4C) != 0 || *(int *)(r + 0x1B8C) < 360) {
        ++result->refused;
        return 0;
    }
    if (!c4_room()) {
        result->no_room_babies += litter;
        return 0;
    }
    TC7(0x45E7B0u, r, *(int *)(source + 0x1B98), 0, 0,
        (int)(uintptr_t)(f != NULL ? (const char *)(f + 0x1B9C) : "Unknown"),
        *(int *)(source + 0x1BB8), *(int *)(source + 0x1BBC), 1);
    if (*(int *)(r + 0x1C4C) == 0) {
        ++result->refused;
        return 0;
    }
    rolled = *(int *)(r + 0x1C50);
    if (rolled == 2) {
        --*(int *)(uintptr_t)0x4D6E08u;
    } else if (rolled == 3) {
        --*(int *)(uintptr_t)0x4D6E0Cu;
    }
    *(int *)(r + 0x1C50) = 1;
    babies = 1;
    while (babies < litter && c4_room()) {
        ++babies;
        *(int *)(r + 0x1C50) = babies;
    }
    result->no_room_babies += litter - babies;
    if (babies == 2) {
        ++*(int *)(uintptr_t)0x4D6E08u;
    } else if (babies == 3) {
        ++*(int *)(uintptr_t)0x4D6E0Cu;
    }
    *(int *)(uintptr_t)0x4D6DE8u += babies;
    TC2(0x412F90u, 0x4CBB98u, 0x13 + babies, 1);
    story_log_conception(4, (const void *)(uintptr_t)C4_MANAGER, r, f);
    return babies;
}

static const char *const C4_BEHAVIOURS[] = {
    "Stops what they are doing", "Recovers fully (cured, full health)"
};

/* The stop routine 0x468C60 (thiscall on the record); the Origins Full
   Heal's cure: sick 0 and 0x46AF00(100, -1). */
static int c4_behave(int index, int behaviour) {
    unsigned char *r = c4_record(index);
    switch (behaviour) {
    case 0: TC0(0x468C60u, r); return 1;
    case 1:
        r[0x1C48] = 0;
        TC2(0x46AF00u, r + 0x1C34, 100, -1);
        return 1;
    default: return 0;
    }
}

static const char *const C4_VILLAGE[] = {
    "Rain begins (as in The Rainy Season)",
    "The weather clears",
};

/* The weather, 0x46BC30 (thiscall on 0x6C461C: type, duration 0 = the
   game's own random length; ret 8): type 2 is the rain The Rainy Season and
   The Monsoon set, type 0 the clear weather the scheduler returns to. */
static int c4_village(int which) {
    switch (which) {
    case 0: TC2(0x46BC30u, 0x6C461Cu, 2, 0); return 1;
    case 1: TC2(0x46BC30u, 0x6C461Cu, 0, 0); return 1;
    default: return 0;
    }
}

static int c4_food(void) { return *(int *)(uintptr_t)C4_FOOD; }
static int c4_tech(void) { return *(int *)(uintptr_t)C4_TECH; }

/* Written directly: the food adder 0x41D920 multiplies a gain by Food
   Mastery and both adders are detoured through the Origins doubler. */
static void c4_change_food(int op, int amount) {
    int after;
    ce_amount(op, amount, c4_food(), &after);
    *(int *)(uintptr_t)C4_FOOD = after;
}

static void c4_change_tech(int op, int amount) {
    int after;
    ce_amount(op, amount, c4_tech(), &after);
    *(int *)(uintptr_t)C4_TECH = after;
}

/* The berry bushes, [world+0x170F8], to their full 1000 (the game's own
   ceiling, 0x4203CA; A Closer Look adds to them, 0x414B30). */
static int c4_refill(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV4_WORLD_GLOBAL;
    if (world == NULL) {
        return 0;
    }
    if (*(int *)(world + 0x170F8) < 1000) {
        *(int *)(world + 0x170F8) = 1000;
    }
    return 1;
}

static int c4_parents_supported(void) {
    return 1;
}

static int c4_set_parents(int index, const ce_change *c) {
    return ce_set_record_parents(c4_record(index), 0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC,
                                 0x1C00, 30, 30, c);
}

static const char *const C4_SKILLS[] = { "Farming", "Parenting", "Healing", "Research", "Building" };

static const ce_adapter C4_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK
        | CAP_BEHAVIOUR | CAP_VILLAGE | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY,
    "The Tree of Life",
    0x118, 40, 1100,
    C4_COUNT, 0x19,
    0x1B9C, 0x1B90, 0x1B8C, 0x1BB8, 0x1BBC, 0x1E60, 0x1E6C, 0x1C5C,
    0, 1,
    3, 79,
    STORY_PREFERENCES_79,
    30, 30,
    5, 1, C4_SKILLS,
    0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00,
    NULL, 0,
    C4_BEHAVIOURS, 2,
    C4_VILLAGE, 2,
    "Not in The Tree of Life:\r\n\r\n"
    "- Refill: only the berry bushes have a store the game refills; the fruit trees "
    "and fishing have no refill the game can make.\r\n"
    "- Special statuses: Scholar and Elderly are worked out from skills and age, and "
    "\"Tribal Chief\" is never shown, so there is none to give.\r\n"
    "- Puzzle states: only the collections have a completion route (the Origins rows).\r\n"
    "- Weather other than rain and clear: the other types are not identified.\r\n"
    "- Golden Child, faction, totems: The Tree of Life has none.",
    48, 14, 30, 1, 360,
    "Refills the berry bushes.",
    "Your village gains %d food.", "Your village has lost %d food.",
    "Your village has gained %d tech points.", "Your village has lost %d tech points.",
    c4_record, c4_listed, c4_arm_refusal, c4_room, c4_spawn, c4_kill, c4_vanish, c4_sicken,
    c4_conceive, NULL, c4_behave, c4_village, c4_food, c4_tech, c4_change_food, c4_change_tech,
    c4_refill, c4_parents_supported, c4_set_parents
};

/* ---- Delivery ----------------------------------------------------------- */

static int __fastcall c4_title_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C4_TITLE_ID;
}

static int __fastcall c4_body_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C4_BODY_ID;
}

/* The event base (0x48C4EC, whose condition and string ids are pure
   virtual) with: +0x04 always possible, +0x08 / +0x0C the custom ids; its
   own apply (+0x30) and prepare (+0x38) already do nothing. */
static void *c4_custom_object(void) {
    static const int slots[3] = { 1, 2, 3 };
    void *functions[3];
    if (ce_deliver_object(4, C4_STRING_TABLE, C4_TITLE_ID, C4_BODY_ID, 1) == NULL) {
        return NULL;
    }
    functions[0] = (void *)ce_object_true;
    functions[1] = (void *)c4_title_id;
    functions[2] = (void *)c4_body_id;
    return ce_build_object(0x48C4ECu, slots, functions, 3);
}

/* ---- Title ---------------------------------------------------------------

   The HUD 0x440150 builds the selected villager's title in [esp+0x28] for
   the record at [esp+0x10]; every branch reaches 0x4404D9 `lea ecx,
   [esp+0x28]; push ecx` before setting the label. */
static void __cdecl c4_title(const unsigned char *record, char *buffer) {
    const char *custom = titles_lookup(4, record);
    if (custom != NULL) {
        lstrcpynA(buffer, custom, VV_TITLE_BYTES);
    }
}

__declspec(naked) static void c4_title_stub(void) {
    __asm {
        pushad
        mov eax, dword ptr [esp + 0x20 + 0x10]
        lea ecx, [esp + 0x20 + 0x28]
        push ecx
        push eax
        call c4_title
        add esp, 8
        popad
        lea ecx, [esp + 0x28]
        push ecx
        push 0x4404DE
        ret
    }
}
