/* Custom Island Event: New Believers.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md).  The villager manager is
   0x554148; record i at 0x554190 + i*0x2F44, 150 records.  A Heathen is a
   record with the faction byte +0x1CEC set.

   DELIVERY.  The island-event selector 0x418870 has chosen at 0x41895B (the
   Pick Island Event site, after the Origins Barrel stub and the stock
   Chutes override): with a custom event armed, the changes are made and the
   presenter is handed the custom event object (story_objects.inc, a copy of
   Blessings Day's simple-event vtable 0x49762C).  Its strings are ids 0x3AD
   / 0x3AE, string-table slots (0x5240A8) the game leaves empty and no code
   names. */

#define C5_MANAGER 0x554148u
#define C5_RECORDS 0x554190u
#define C5_STRIDE 0x2F44u
#define C5_COUNT 150
#define C5_FOOD 0x51D34Cu
#define C5_TECH 0x51D5F8u
#define C5_TITLE_ID 0x3AD
#define C5_BODY_ID 0x3AE
#define C5_STRING_TABLE 0x5240A8u

static unsigned char *c5_record(int index) {
    if (index < 0 || index >= C5_COUNT) {
        return NULL;
    }
    return (unsigned char *)(uintptr_t)(C5_RECORDS + (unsigned int)index * C5_STRIDE);
}

/* Active, health above 0, not a Reanimate spirit (+0x1CE1, which 0x466170
   excludes too). */
static int c5_listed(const unsigned char *r) {
    return r[0x1CD4] != 0 && *(const int *)(r + 0x1C40) > 0 && r[0x1CE1] == 0;
}

static int c5_heathen(const unsigned char *r) {
    return r[0x1CEC] != 0;
}

/* The Heathens of the game's own puzzles (roles 0xC..0x11, the Heathen
   Mommy among them) keep their faction: the puzzles depend on them. */
static int c5_puzzle_heathen(const unsigned char *r) {
    int role = *(const int *)(r + 0x1CFC);
    return role >= 0xC && role <= 0x11;
}

static int c5_demand(void) {
    int i;
    int n = 0;
    for (i = 0; i < C5_COUNT; ++i) {
        unsigned char *r = c5_record(i);
        if (r[0x1CD4] != 0) {
            ++n;
            if (*(int *)(r + 0x1C4C) != 0) {
                n += *(int *)(r + 0x1C50);
            }
        }
    }
    return n;
}

static const char *c5_arm_refusal(void) {
    int i;
    for (i = 0; i < C5_COUNT; ++i) {
        unsigned char *r = c5_record(i);
        if (c5_listed(r) && !c5_heathen(r) && *(int *)(r + 0x1B8C) >= 0x118) {
            return NULL;
        }
    }
    return "An island event needs a living adult believer in the village.";
}

/* The game's own room predicate 0x472BD0 (believers below the mode's cap,
   the housing gates) and the 150 records. */
static int c5_room(void) {
    return (TC0(0x472BD0u, C5_MANAGER) & 0xFF) != 0 && c5_demand() < C5_COUNT;
}

static const ce_adapter C5_ADAPTER;

/* 0x471E20 (thiscall on the manager: lineage, skill, value, sex, age; ret
   0x14) -- the believer creator the Barrel, Chutes and News From Another
   Tribe use (lineage 1, as they pass it); sex 0 male, 1 female. */
static int c5_spawn(const ce_spawn *s) {
    int index;
    if (!c5_room()) {
        return -1;
    }
    index = TC5(0x471E20u, C5_MANAGER, 1, 0, 0, s->sex == STORY_SEX_MALE ? 0 : 1, s->age);
    if (index < 0 || index >= C5_COUNT) {
        return -1;
    }
    ce_apply_spawn_record(&C5_ADAPTER, c5_record(index), s);
    return index;
}

/* The game's own death: the activity stops (0x473440), then SetHealth
   0x4758B0 (thiscall on the health block +0x1C34: 0, cause; ret 8) as old
   age calls it (0x47304A), with its cause 2 -- the cause the death
   statistic's hook needs to count the death exactly once. */
static int c5_kill(int index) {
    unsigned char *r = c5_record(index);
    TC0(0x473440u, r);
    TC2(0x4758B0u, r + 0x1C34, 0, 2);
    return 1;
}

/* Sick is the byte +0x1C48, as Missing Kids (0x4161FA) writes it; the game
   clears it on Heathens every tick, so a Heathen is refused. */
static int c5_sicken(int index) {
    unsigned char *r = c5_record(index);
    if (c5_heathen(r)) {
        return 0;
    }
    r[0x1C48] = 1;
    return 1;
}

/* A pregnancy through the conception routine 0x465E00 (thiscall on the
   carrier: father attribute, skill, value, father's name, head, body,
   force; ret 0x1C) with force = 1, which writes every pregnancy field
   without its own room check, Babies Made and log, so the litter can be the
   chosen one: the litter set (each baby only while there is room), Babies
   Made [0x51D360] += babies as force = 0 adds it, and the parentage log as
   the routine's own trampoline writes it.  An unknown father is "Unknown"
   with the carrier's own head and body.  Heathens never deliver (0x472CB7),
   so only believers carry; there is no sex check in the conception or the
   delivery (0x4730AF), which is how the Heathen Mommy's male mother works. */
static int c5_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *r = c5_record(index);
    unsigned char *f = father >= 0 ? c5_record(father) : NULL;
    const unsigned char *source = f != NULL ? f : r;
    int babies;
    if (*(int *)(r + 0x1C4C) != 0 || *(int *)(r + 0x1B8C) < 0x118 || c5_heathen(r)) {
        ++result->refused;
        return 0;
    }
    if (!c5_room()) {
        result->no_room_babies += litter;
        return 0;
    }
    TC7(0x465E00u, r, *(int *)(source + 0x1B98), 0, 0,
        (int)(uintptr_t)(f != NULL ? (const char *)(f + 0x1B9C) : "Unknown"),
        *(int *)(source + 0x1BB8), *(int *)(source + 0x1BBC), 1);
    if (*(int *)(r + 0x1C4C) == 0) {
        ++result->refused;
        return 0;
    }
    *(int *)(r + 0x1C50) = 1;
    babies = 1;
    while (babies < litter && c5_room()) {
        ++babies;
        *(int *)(r + 0x1C50) = babies;
    }
    result->no_room_babies += litter - babies;
    *(int *)(uintptr_t)0x51D360u += babies;
    story_log_conception(5, (const void *)(uintptr_t)C5_MANAGER, r, f);
    return babies;
}

static const char *const C5_STATUSES[] = { "Becomes a believer", "Becomes a Heathen" };

/* The game's own conversions -- 0x4668B0 to a believer (what SetFaith
   0x467F90 calls when faith rises above 0; The Defector) and 0x4669E0 to a
   Heathen (when it falls to 0 or below; The Mask) -- with the faith they
   leave (+0x1CF0: 55, the floor SetFaith gives a convert; -10, The Mask's).
   The puzzles' own Heathens are refused. */
static int c5_set_status(int index, int status) {
    unsigned char *r = c5_record(index);
    if (c5_puzzle_heathen(r)) {
        return 0;
    }
    if (status == 0) {
        if (c5_heathen(r)) {
            TC0(0x4668B0u, r);
        }
        *(int *)(r + 0x1CF0) = 55;
        return !c5_heathen(r);
    }
    if (status == 1) {
        if (*(int *)(r + 0x1C4C) != 0) {
            return 0;               /* a Heathen never delivers: keep her baby */
        }
        if (!c5_heathen(r)) {
            TC0(0x4669E0u, r);
        }
        *(int *)(r + 0x1CF0) = -10;
        return c5_heathen(r);
    }
    return 0;
}

static const char *const C5_BEHAVIOURS[] = {
    "Stops what they are doing", "Recovers fully (cured, full health)"
};

/* The stop routine 0x473440 (thiscall on the record, used by many events);
   the cure (sick 0) with SetHealth(100, -1) as 0x472F77 heals. */
static int c5_behave(int index, int behaviour) {
    unsigned char *r = c5_record(index);
    switch (behaviour) {
    case 0: TC0(0x473440u, r); return 1;
    case 1:
        r[0x1C48] = 0;
        TC2(0x4758B0u, r + 0x1C34, 100, -1);
        return 1;
    default: return 0;
    }
}

static int c5_food(void) { return *(int *)(uintptr_t)C5_FOOD; }
static int c5_tech(void) { return *(int *)(uintptr_t)C5_TECH; }

/* Written directly: the food adder 0x41EB40 multiplies a gain by Food
   Mastery; tech has no floor of its own, so it is kept at 0 or more as the
   stock penalties keep it (0x414D30). */
static void c5_change_food(int op, int amount) {
    int after;
    ce_amount(op, amount, c5_food(), &after);
    *(int *)(uintptr_t)C5_FOOD = after;
}

static void c5_change_tech(int op, int amount) {
    int after;
    ce_amount(op, amount, c5_tech(), &after);
    *(int *)(uintptr_t)C5_TECH = after;
}

/* The noni bushes ([world+0x17D58], ceiling 1000, 0x425F72) and, once item
   5 is done (0x43AE80 on 0x51E008), the crops (+0x17D5C, ceiling 800): the
   stores The River Breaks Its Banks and The Clumsy Heathen add to. */
static int c5_refill(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV5_WORLD_GLOBAL;
    if (world == NULL) {
        return 0;
    }
    if (*(int *)(world + 0x17D58) < 1000) {
        *(int *)(world + 0x17D58) = 1000;
    }
    if (TC1(0x43AE80u, 0x51E008u, 5) & 0xFF) {
        *(int *)(world + 0x17D5C) = 800;
    }
    return 1;
}

static int c5_parents_supported(void) {
    return 1;
}

static int c5_set_parents(int index, const ce_change *c) {
    return ce_set_record_parents(c5_record(index), 0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC,
                                 0x1C00, 30, 30, c);
}

static const char *const C5_SKILLS[] = {
    "Farming", "Parenting", "Healing", "Research", "Building", "Devotion"
};

static const ce_adapter C5_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_SICK | CAP_PREGNANT | CAP_PREFS
        | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK | CAP_STATUS
        | CAP_BEHAVIOUR | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY,
    "New Believers",
    0x118, 40, 1100,
    C5_COUNT, 0x19,
    0x1B9C, 0x1B90, 0x1B8C, 0x1BB8, 0x1BBC, 0x1F5C, 0x1F68, 0x1C5C,
    0, 1,
    3, 79,
    STORY_PREFERENCES_79,
    30, 30,
    6, 1, C5_SKILLS,
    0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00,
    C5_STATUSES, 2,
    C5_BEHAVIOURS, 2,
    NULL, 0,
    "Not in New Believers:\r\n\r\n"
    "- Disappear: the game has no way of removing a living villager (no event does it); "
    "only a corpse that is never buried disappears.\r\n"
    "- New Heathens: the Heathen creator's arguments are not all understood; make a "
    "believer and turn them into a Heathen instead.\r\n"
    "- The puzzles' own Heathens (the Heathen Mommy and the others) keep their faction.\r\n"
    "- Heathens can not be made sick (the game cures them every moment) or pregnant "
    "(Heathens never give birth).\r\n"
    "- Puzzle states: the puzzle completion routine needs world state that is not proven.\r\n"
    "- Esteemed Elder and Retired Chief are worked out from skills and the chief puzzle.",
    48, 14, 30, 1, 0x118,
    "Refills the noni bushes and, once the farm is built, the crops.",
    "Your village gains %d food.", "Your village has lost %d food.",
    "Your village has gained %d tech points.", "Your village has lost %d tech points.",
    c5_record, c5_listed, c5_arm_refusal, c5_room, c5_spawn, c5_kill, NULL, c5_sicken,
    c5_conceive, c5_set_status, c5_behave, NULL, c5_food, c5_tech, c5_change_food, c5_change_tech,
    c5_refill, c5_parents_supported, c5_set_parents
};

/* ---- Delivery ----------------------------------------------------------- */

static int __fastcall c5_title_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C5_TITLE_ID;
}

static int __fastcall c5_body_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C5_BODY_ID;
}

/* Blessings Day (0x49762C) with: +0x08 / +0x0C the custom ids and +0x30
   apply doing nothing; its prepare (+0x38) already does nothing. */
static void *c5_custom_object(void) {
    static const int slots[3] = { 2, 3, 12 };
    void *functions[3];
    if (ce_deliver_object(5, C5_STRING_TABLE, C5_TITLE_ID, C5_BODY_ID, 0) == NULL) {
        return NULL;
    }
    functions[0] = (void *)c5_title_id;
    functions[1] = (void *)c5_body_id;
    functions[2] = (void *)ce_object_nothing;
    return ce_build_object(0x49762Cu, slots, functions, 3);
}

/* ---- Title ---------------------------------------------------------------

   The HUD 0x442CE0 builds the title in [esp+0x24] for the record in ESI and
   reaches 0x44319E `mov ecx,[ebp+0xE0]` before setting the label. */
static void __cdecl c5_title(const unsigned char *record, char *buffer) {
    const char *custom = titles_lookup(5, record);
    if (custom != NULL) {
        lstrcpynA(buffer, custom, VV_TITLE_BYTES);
    }
}

__declspec(naked) static void c5_title_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 0x20 + 0x24]
        push eax
        push esi
        call c5_title
        add esp, 8
        popad
        mov ecx, dword ptr [ebp + 0xE0]
        push 0x4431A4
        ret
    }
}
