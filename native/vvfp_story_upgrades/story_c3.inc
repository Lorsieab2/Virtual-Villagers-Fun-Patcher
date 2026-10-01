/* Custom Island Event: The Secret City.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md).  The village is
   0x59E110; record i at 0x59E124 + i*0x1F8C, 150 records.

   DELIVERY.  The island-event selector 0x419B30 has chosen at 0x419BDB (the
   Pick Island Event site): with a custom event armed, the changes are made
   and the presenter is handed the custom event object (story_objects.inc,
   a copy of The Fog's simple-event vtable 0x47E600) instead.  Its strings
   are ids 0x4CB / 0x4CC, the two string-table slots (0x592730) the game
   leaves empty and no code or string names.  The Origins Barrel's call of
   the same selector (every slot the barrel) never takes it. */

#define C3_VILLAGE 0x59E110u
#define C3_RECORDS 0x59E124u
#define C3_STRIDE 0x1F8Cu
#define C3_COUNT 150
#define C3_FOOD 0x582490u
#define C3_TECH 0x582644u
#define C3_TITLE_ID 0x4CB
#define C3_BODY_ID 0x4CC
#define C3_STRING_TABLE 0x592730u

static unsigned char *c3_record(int index) {
    if (index < 0 || index >= C3_COUNT) {
        return NULL;
    }
    return (unsigned char *)(uintptr_t)(C3_RECORDS + (unsigned int)index * C3_STRIDE);
}

static int c3_listed(const unsigned char *r) {
    return r[0xF10] != 0 && *(const int *)(r + 0xE78) > 0;
}

/* Records in use plus the babies on the way: the 150 records are the
   physical limit, which the game's room predicate does not count. */
static int c3_demand(void) {
    int i;
    int n = 0;
    for (i = 0; i < C3_COUNT; ++i) {
        unsigned char *r = c3_record(i);
        if (r[0xF10] != 0) {
            ++n;
            if (*(int *)(r + 0xE8C) != 0) {
                n += *(int *)(r + 0xE90);
            }
        }
    }
    return n;
}

static const char *c3_arm_refusal(void) {
    int i;
    for (i = 0; i < C3_COUNT; ++i) {
        unsigned char *r = c3_record(i);
        if (c3_listed(r) && *(int *)(r + 0xDC4) >= 0x118) {
            return NULL;
        }
    }
    return "An island event needs a living adult in the village.";
}

/* The game's own room predicate 0x45FE30 (the mode's cap, the building
   gates) and the 150 records. */
static int c3_room(void) {
    return (TC0(0x45FE30u, C3_VILLAGE) & 0xFF) != 0 && c3_demand() < C3_COUNT;
}

static const ce_adapter C3_ADAPTER;

/* 0x45FF50 (thiscall on the village: family, skill, value, sex, age; ret
   0x14) -- the creator The Canoe and the Barrel use.  Family -1 is the
   game's own random; sex 0 male, 1 female. */
static int c3_spawn(const ce_spawn *s) {
    int index;
    if (!c3_room()) {
        return -1;
    }
    index = TC5(0x45FF50u, C3_VILLAGE, -1, 0, 0, s->sex == STORY_SEX_MALE ? 0 : 1, s->age);
    if (index < 0 || index >= C3_COUNT) {
        return -1;
    }
    ce_apply_spawn_record(&C3_ADAPTER, c3_record(index), s);
    return index;
}

/* The Medical Emergency's death (0x4172D9): 0x462670 (thiscall on the
   record's health block +0xE6C: value 0, cause -1). */
static int c3_kill(int index) {
    TC2(0x462670u, c3_record(index) + 0xE6C, 0, -1);
    return 1;
}

/* The Tsunami and The Low Tide (0x45D990 -> 0x45D9D1) clear the active byte;
   the selection is dropped first (0x45FCC0) when it is this villager, as the
   burial does. */
static int c3_vanish(int index) {
    unsigned char *r = c3_record(index);
    if (r[0xF11] != 0) {
        TC0(0x45FCC0u, C3_VILLAGE);
    }
    r[0xF10] = 0;
    return 1;
}

/* Sick is the byte +0xE89, as Bed Bugs (0x416E40) writes it. */
static int c3_sicken(int index) {
    c3_record(index)[0xE89] = 1;
    return 1;
}

/* A pregnancy, written as the conception routine 0x455AB0 writes it:
     +0xE8C = the carrier's processed age (+0xE74);
     +0xE44 = the father's family (+0xDD0);
     +0xE3C / +0xE40 = the inherited skill (none: 0 / 0);
     +0xE48 = the father's name, +0xE68 / +0xE64 his head and body;
     +0xE90 = the babies (1, 2 or 3);
   Babies Made [0x5824A8] += babies, Twins [0x5824C8] / Triplets [0x5824CC]
   +1; the carried-baby pose through the stop routine 0x460F70; and the
   parentage log with the father's record.  An unknown father is "Unknown"
   with the carrier's own head and body.  Each baby only while there is
   room; there is no sex check in the delivery (0x460341). */
static int c3_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *r = c3_record(index);
    unsigned char *f = father >= 0 ? c3_record(father) : NULL;
    int babies;
    int age;
    if (*(int *)(r + 0xE8C) != 0 || *(int *)(r + 0xDC4) < 360) {
        ++result->refused;
        return 0;
    }
    if (!c3_room()) {
        result->no_room_babies += litter;
        return 0;
    }
    age = *(int *)(r + 0xE74);
    *(int *)(r + 0xE44) = *(int *)((f != NULL ? f : r) + 0xDD0);
    *(int *)(r + 0xE3C) = 0;
    *(int *)(r + 0xE40) = 0;
    ce_write_name(r + 0xE48, 0x18, f != NULL ? (const char *)(f + 0xDD4) : "Unknown");
    *(int *)(r + 0xE68) = *(int *)((f != NULL ? f : r) + 0xDF0);
    *(int *)(r + 0xE64) = *(int *)((f != NULL ? f : r) + 0xDF4);
    *(int *)(r + 0xE90) = 1;
    *(int *)(r + 0xE8C) = age != 0 ? age : 1;
    babies = 1;
    while (babies < litter && c3_room()) {
        ++babies;
        *(int *)(r + 0xE90) = babies;
    }
    result->no_room_babies += litter - babies;
    *(int *)(uintptr_t)0x5824A8u += babies;
    if (babies == 2) {
        ++*(int *)(uintptr_t)0x5824C8u;
    } else if (babies == 3) {
        ++*(int *)(uintptr_t)0x5824CCu;
    }
    TC1(0x460F70u, r, (int)(uintptr_t)r);
    story_log_conception(3, (const void *)(uintptr_t)C3_VILLAGE, r, f);
    return babies;
}

static const char *const C3_BEHAVIOURS[] = {
    "Stops what they are doing", "Recovers fully (cured, full health)"
};

/* The stop routine 0x460F70 (thiscall on the record, the record; 137
   callers, e.g. The Low Tide 0x415EAF); the Origins Full Heal's cure: sick
   0 and 0x462670(100, -1). */
static int c3_behave(int index, int behaviour) {
    unsigned char *r = c3_record(index);
    switch (behaviour) {
    case 0: TC1(0x460F70u, r, (int)(uintptr_t)r); return 1;
    case 1:
        r[0xE89] = 0;
        TC2(0x462670u, r + 0xE6C, 100, -1);
        return 1;
    default: return 0;
    }
}

static int c3_food(void) { return *(int *)(uintptr_t)C3_FOOD; }
static int c3_tech(void) { return *(int *)(uintptr_t)C3_TECH; }

/* Written directly (the adders 0x4263F0 / 0x427130 are detoured through the
   Origins doubler); a gain also counts in the lifetime totals [0x5824AC] /
   [0x5824A4] as the adders count it. */
static void c3_change_food(int op, int amount) {
    int before = c3_food();
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(uintptr_t)C3_FOOD = after;
    if (after > before) {
        *(int *)(uintptr_t)0x5824ACu += after - before;
    }
}

static void c3_change_tech(int op, int amount) {
    int before = c3_tech();
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(uintptr_t)C3_TECH = after;
    if (after > before) {
        *(int *)(uintptr_t)0x5824A4u += after - before;
    }
}

/* The fruit trees (object 0x5947E0, count at +0x64, at most 3): 0x4340A0
   (thiscall on the trees, the tree; ret 4) sets a tree's fruit to the full
   1000, as Bitter Brown Beans' "use the beans as fertilizer" does
   (0x415AD0). */
static int c3_refill(void) {
    unsigned char *trees = (unsigned char *)(uintptr_t)0x5947E0u;
    int count = *(int *)(trees + 0x64);
    int i;
    for (i = 0; i < count && i < 3; ++i) {
        TC1(0x4340A0u, trees, i);
    }
    return 1;
}

static int c3_parents_supported(void) {
    return 1;
}

static int c3_set_parents(int index, const ce_change *c) {
    return ce_set_record_parents(c3_record(index), 0xDF8, 0xE11, 0x19, 0xE2C, 0xE30, 0xE34, 0xE38,
                                 30, 30, c);
}

static const char *const C3_SKILLS[] = { "Farming", "Parenting", "Healing", "Research", "Building" };

static const ce_adapter C3_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK
        | CAP_BEHAVIOUR | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY,
    "The Secret City",
    0x118, 40, 1100,
    C3_COUNT, 0x19,
    0xDD4, 0xDC8, 0xDC4, 0xDF0, 0xDF4, 0xFB4, 0xFC0, 0xEAC,
    0, 1,
    3, 79,
    STORY_PREFERENCES_79,
    30, 30,
    5, 0, C3_SKILLS,
    0xDF8, 0xE11, 0x19, 0xE2C, 0xE30, 0xE34, 0xE38,
    NULL, 0,
    C3_BEHAVIOURS, 2,
    NULL, 0,
    "Not in The Secret City:\r\n\r\n"
    "- Tribal Chief: only the robe puzzle makes a chief, and a second chief is a known defect.\r\n"
    "- Esteemed Elder is not a status here: the game shows it for any villager with three "
    "mastered skills, so set the skills instead.\r\n"
    "- Village and puzzle states: no puzzle has a completion routine that can be called on "
    "its own (the puzzles create the objects they need).\r\n"
    "- Refill: only the fruit trees have a refill the game itself uses; the beehive's is "
    "tied to its puzzle.\r\n"
    "- Golden Child, faction, totems: The Secret City has none.",
    48, 14, 30, 1, 360,
    "Refills the fruit trees.",
    "Your village gains %d food.", "Your village has lost %d food.",
    "Your village has gained %d tech points.", "Your village has lost %d tech points.",
    c3_record, c3_listed, c3_arm_refusal, c3_room, c3_spawn, c3_kill, c3_vanish, c3_sicken,
    c3_conceive, NULL, c3_behave, NULL, c3_food, c3_tech, c3_change_food, c3_change_tech,
    c3_refill, c3_parents_supported, c3_set_parents
};

/* ---- Delivery ----------------------------------------------------------- */

static int __fastcall c3_title_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C3_TITLE_ID;
}

static int __fastcall c3_body_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C3_BODY_ID;
}

/* The Fog (0x47E600) with: +0x08 / +0x0C the custom ids, +0x30 apply and
   +0x38 prepare doing nothing (the changes are already made). */
static void *c3_custom_object(void) {
    static const int slots[4] = { 2, 3, 12, 14 };
    void *functions[4];
    if (ce_deliver_object(3, C3_STRING_TABLE, C3_TITLE_ID, C3_BODY_ID, 0) == NULL) {
        return NULL;
    }
    functions[0] = (void *)c3_title_id;
    functions[1] = (void *)c3_body_id;
    functions[2] = (void *)ce_object_nothing;
    functions[3] = (void *)ce_object_nothing;
    return ce_build_object(0x47E600u, slots, functions, 4);
}

/* ---- Title ---------------------------------------------------------------

   The HUD 0x468C10 builds the selected villager's title in a stack buffer
   ([esp+0x28]) for the record at [esp+0x10]; both branches join at 0x468FC8
   `mov ecx,[ebp+0xE4]` before setting the label. */
static void __cdecl c3_title(const unsigned char *record, char *buffer) {
    const char *custom = titles_lookup(3, record);
    if (custom != NULL) {
        lstrcpynA(buffer, custom, VV_TITLE_BYTES);
    }
}

__declspec(naked) static void c3_title_stub(void) {
    __asm {
        pushad
        mov eax, dword ptr [esp + 0x20 + 0x10]
        lea ecx, [esp + 0x20 + 0x28]
        push ecx
        push eax
        call c3_title
        add esp, 8
        popad
        mov ecx, dword ptr [ebp + 0xE4]
        push 0x468FCE
        ret
    }
}
