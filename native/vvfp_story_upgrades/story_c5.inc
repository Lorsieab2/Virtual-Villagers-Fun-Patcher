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
   Tribe use (lineage 1, as they pass it); sex 0 male, 1 female.  A new
   Heathen comes from the game's one Heathen creator 0x46FD20 (ret 0x24),
   called exactly as Barrel O' Babies! (heathens) calls it (0x4152B0):
   lineage 1, no starting skill, sex, age, no camp flags, an ordinary
   Heathen (status 0), faith -55 -- each only while the room predicate says
   there is room, as that event rations its babies. */
static int c5_spawn(const ce_spawn *s) {
    int index;
    int sex = s->sex == STORY_SEX_MALE ? 0 : 1;
    if (!c5_room()) {
        return -1;
    }
    if (s->faction == 1) {
        index = TC9(0x46FD20u, C5_MANAGER, 1, 0, 0, sex, s->age, 0, 0, 0, -55);
    } else {
        index = TC5(0x471E20u, C5_MANAGER, 1, 0, 0, sex, s->age);
    }
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

/* Disappearance is the game's own removal of a record without a body: the
   presence byte +0x1CD4 cleared, as the stock code clears it for a living
   villager it takes away (0x420142, 0x46723E) and for a body it removes
   (0x473F8F).  The activity stops first (0x473440, as the death does), and
   the selection is dropped when it is this villager, as the body's removal
   does (0x473F7A: 0x4653D0 is "is selected", 0x470800 clears it). */
static int c5_vanish(int index) {
    unsigned char *r = c5_record(index);
    TC0(0x473440u, r);
    if ((TC0(0x4653D0u, r) & 0xFF) != 0) {
        TC0(0x470800u, C5_MANAGER);
    }
    r[0x1CD4] = 0;
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
    /* The routine rolls twins and triplets whatever `force` says and counts
       them as it rolls them (Twins Birthed [0x51D380] at 0x465F2D, Triplets
       Birthed [0x51D384] at 0x465F1A, a believer carrier counted by the
       statistics row's Heathen guard too): the rolled litter's count is
       taken back and the chosen litter counted once, as a natural one is. */
    if (*(int *)(r + 0x1C50) == 2) {
        --*(int *)(uintptr_t)0x51D380u;
    } else if (*(int *)(r + 0x1C50) == 3) {
        --*(int *)(uintptr_t)0x51D384u;
    }
    *(int *)(r + 0x1C50) = 1;
    babies = 1;
    while (babies < litter && c5_room()) {
        ++babies;
        *(int *)(r + 0x1C50) = babies;
    }
    result->no_room_babies += litter - babies;
    if (babies == 2) {
        ++*(int *)(uintptr_t)0x51D380u;
    } else if (babies == 3) {
        ++*(int *)(uintptr_t)0x51D384u;
    }
    *(int *)(uintptr_t)0x51D360u += babies;
    story_log_conception(5, (const void *)(uintptr_t)C5_MANAGER, r, f);
    return babies;
}

static const char *const C5_STATUSES[] = {
    "Becomes a believer", "Becomes a Heathen",
    "Heathen's mask: blue", "Heathen's mask: orange (aggressive)", "Heathen's mask: red (scary)",
};

/* What a conversion to a believer counts (owner, 2026-10-02: the Maker's
   faction changes are not the player's conversions and must not count).
   Emulated on the stock code and the full catalog render, 0x4668B0 writes
   exactly two things outside the record that are not the screen's: the
   trophy table 0x4DB358 (0x413450 adds 1 to "A Heathen's Prerogative" 0x13,
   3 to earn, and "If You Can't Beat 'Em..." 0x14, 10 to earn; earning one
   sets its byte, stamps it, queues the "Trophy earned" popup at +0x318 and
   adds to the Over-Achiever / Unachievable trophies 0x40 / 0x41) and the
   patcher's Heathens Converted total 0x51D3A4 (build_statistics_features.py
   conversion_stat_va, its detour on 0x4668B0's entry).  Both are memory
   only -- the table reaches a file only inside the slot's save, the popup
   is drawn by a later frame, the total is exported later -- so the whole
   table and the total are put back on this same game thread before
   anything can read them.  To a Heathen (0x4669E0) and the Heathen creator
   write neither (emulated), so they need nothing. */
#define C5_TROPHIES 0x4DB358u
#define C5_TROPHY_BYTES 0x428          /* 66 entries of 12, the popup queue, its timer */
#define C5_HEATHENS_CONVERTED 0x51D3A4u

static void c5_convert_uncounted(unsigned char *r) {
    unsigned char trophies[C5_TROPHY_BYTES];
    int converted = *(volatile int *)(uintptr_t)C5_HEATHENS_CONVERTED;
    memcpy(trophies, (const void *)(uintptr_t)C5_TROPHIES, sizeof trophies);
    TC0(0x4668B0u, r);
    memcpy((void *)(uintptr_t)C5_TROPHIES, trophies, sizeof trophies);
    *(volatile int *)(uintptr_t)C5_HEATHENS_CONVERTED = converted;
}

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
    if (status >= 2 && status <= 4) {
        /* An ordinary Heathen's kind, the two bytes the Heathen AI and the
           mask's art read (0x4728C6): orange +0x1CED "an aggressive
           heathen", red +0x1CEE "a scary heathen", neither the plain blue
           mask.  The puzzles' Heathens (roles 0xC-0x11) are refused above. */
        if (!c5_heathen(r)) {
            return 0;
        }
        r[0x1CED] = (unsigned char)(status == 3);
        r[0x1CEE] = (unsigned char)(status == 4);
        return 1;
    }
    if (status == 0) {
        if (c5_heathen(r)) {
            c5_convert_uncounted(r);
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

/* Every action is started by the game's DoBehaviour 0x465580 (thiscall on
   the record: behaviour id, a pointer to its argument; ret 8) after the stop
   0x473440, as every stock caller does; these read no argument.  Offered:
   the ones that only look or end by themselves; the jobs that give food,
   tech or skill practice say so.  Never: puzzle actions (the guards, the
   statue), conversions, the Heathens' own camp life, burial, pickups, new
   clothes, games that stop other villagers, or an action no stock code
   starts. */
static const ce_action C5_BEHAVIOURS[] = {
    { "Stops what they are doing", ACT_STOP, 0, 0 },
    { "Recovers fully (cured, full health)", ACT_RECOVER, 0, 0 },
    { "Dances", ACT_DO, 0, 0xF },
    { "Dances (another dance)", ACT_DO, 0, 0xDF },
    { "Rain dancing", ACT_DO, 0, 0x12 },
    { "Celebrates Isola Day", ACT_DO, 0, 0x2F },
    { "Celebrates mushrooms", ACT_DO, 0, 0x75 },
    { "Relaxes", ACT_DO, 0, 0x13 },
    { "Praises", ACT_DO, 0, 0x2A },
    { "Watches the clouds", ACT_DO, 0, 0x86 },
    { "Goes swimming", ACT_DO, 0, 0x1 },
    { "Enjoys the waterfall", ACT_DO, 0, 0x22 },
    { "Enjoys the lake", ACT_DO, 0, 0x1E },
    { "Strolls around the lake", ACT_DO, 0, 0x1C },
    { "Bathes", ACT_DO, 0, 0x98 },
    { "Cools their feet in the stream", ACT_DO, 0, 0x1A },
    { "Washes up in the stream", ACT_DO, 0, 0xD3 },
    { "Drinks the rain", ACT_DO, 0, 0x2B },
    { "Gets out of the rain", ACT_DO, 0, 0x4A },
    { "Cleans up after the rain", ACT_DO, 0, 0x6B },
    { "Washes the laundry", ACT_DO, 0, 0x2C },
    { "Honors the dead", ACT_DO, 0, 0x11 },
    { "Wanders around", ACT_DO, 0, 0x37 },
    { "Unsure what to do", ACT_DO, 0, 0x48 },
    { "A little bit lonely", ACT_DO, 0, 0x41 },
    { "Nature is calling!", ACT_DO, 0, 0xA2 },
    { "Shakes their head", ACT_DO, 0, 0x25 },
    { "Runs away", ACT_DO, 0, 0x9 },
    { "Annoyed by the bees", ACT_DO, 0, 0xA },
    { "Hides from lightning", ACT_DO, 0, 0x9E },
    { "Hides in the water", ACT_DO, 0, 0xAA },
    { "Escapes from foulness", ACT_DO, 0, 0xD1 },
    { "Plays with butterflies!", ACT_DO, 0, 0xE5 },
    { "Chases fish", ACT_DO, 0, 0xEA },
    { "Excited about the puddles", ACT_DO, 0, 0xEB },
    { "Curious about the pools", ACT_DO, 0, 0xC8 },
    { "Curious about the hidden grove", ACT_DO, 0, 0xCA },
    { "Curious about the aqueduct", ACT_DO, 0, 0xCB },
    { "Curious about the cave", ACT_DO, 0, 0xCD },
    { "Does exercise", ACT_DO, 0, 0x4E },
    { "Health chanting (Healing practice)", ACT_DO, 0, 0x67 },
    { "Listens to a story (children)", ACT_DO, 0, 0x3C },
    { "Watches people work (children)", ACT_DO, 0, 0x44 },
    { "Jumpy! (children)", ACT_DO, 0, 0x39 },
    { "Runs around (children)", ACT_DO, 0, 0x4D },
    { "Plays in puddles (children)", ACT_DO, 0, 0x5E },
    { "Plays in the dirt (children)", ACT_DO, 0, 0x68 },
    { "Races! (children)", ACT_DO, 0, 0x83 },
    { "Researches (Research practice, tech points)", ACT_DO, 0, 0x4 },
    { "Harvests noni (Farming practice, food)", ACT_DO, 0, 0x6C },
    { "Eats (uses food)", ACT_DO, 0, 0x33 },
};

/* The stop routine 0x473440 (thiscall on the record, used by many events),
   then the behaviour; the cure (sick 0) with SetHealth(100, -1) as
   0x472F77 heals. */
static int c5_behave(int index, int behaviour) {
    static const int no_argument[8];
    unsigned char *r = c5_record(index);
    const ce_action *act;
    if (behaviour < 0 || behaviour >= (int)(sizeof C5_BEHAVIOURS / sizeof C5_BEHAVIOURS[0])) {
        return 0;
    }
    act = &C5_BEHAVIOURS[behaviour];
    if (act->kind == ACT_RECOVER) {
        r[0x1C48] = 0;
        TC2(0x4758B0u, r + 0x1C34, 100, -1);
    }
    TC0(0x473440u, r);
    if (act->kind == ACT_DO) {
        TC2(0x465580u, r, act->arg, (int)(uintptr_t)no_argument);
    }
    return 1;
}

/* ---- Pregnancy: none, a different number of babies, the father --------- */

/* "0 babies": the pregnancy +0x1C4C and its litter +0x1C50 cleared, then
   the stop 0x473440, which also releases the place the pregnancy held
   (0x466420(-1)), as the delivery does.  Babies Made is left as counted. */
static int c5_cancel(int index) {
    unsigned char *r = c5_record(index);
    if (*(int *)(r + 0x1C4C) == 0) {
        return 0;
    }
    *(int *)(r + 0x1C4C) = 0;
    *(int *)(r + 0x1C50) = 0;
    TC0(0x473440u, r);
    return 1;
}

/* The litter +0x1C50 (0 or 1 one baby, 2, 3: the delivery 0x47319A tests
   > 1 and == 3); each added baby only while there is room. */
static int c5_relitter(int index, int litter, ce_result *result) {
    unsigned char *r = c5_record(index);
    int field = *(int *)(r + 0x1C50);
    int babies = field >= 3 ? 3 : field == 2 ? 2 : 1;
    int added = 0;
    if (litter < babies) {
        *(int *)(r + 0x1C50) = litter;
        return 0;
    }
    while (babies < litter && c5_room()) {
        ++babies;
        ++added;
        *(int *)(r + 0x1C50) = babies;
    }
    result->no_room_babies += litter - babies;
    return added;
}

/* The father the delivery hands the creator: name +0x1C10 (0x18 bytes),
   head +0x1C30, body +0x1C2C. */
static int c5_unborn(int index, const ce_change *c) {
    unsigned char *r = c5_record(index);
    if ((c->unborn_head != CE_KEEP && (c->unborn_head < 0 || c->unborn_head >= 30))
        || (c->unborn_body != CE_KEEP && (c->unborn_body < 0 || c->unborn_body >= 30))) {
        return 0;
    }
    if (c->unborn_name[0] != '\0') {
        ce_write_name(r + 0x1C10, 0x18, c->unborn_name);
    }
    if (c->unborn_head != CE_KEEP) *(int *)(r + 0x1C30) = c->unborn_head;
    if (c->unborn_body != CE_KEEP) *(int *)(r + 0x1C2C) = c->unborn_body;
    return 1;
}

/* ---- Revive ------------------------------------------------------------- */

/* While the game's own Reanimate runs (+0x1CE1 on its villager) its
   stand-in corpse is a present, health-0 record too: nothing is offered or
   revived then. */
static int c5_reanimating(void) {
    int i;
    for (i = 0; i < C5_COUNT; ++i) {
        if (c5_record(i)[0x1CE1] != 0) {
            return 1;
        }
    }
    return 0;
}

/* A skeleton: present, health 0 or less, a believer whose role is not one
   of the puzzles' (no Heathen grave is ever made).  (While a Reanimate
   runs, its stand-in corpse passes this too; the revive refuses then.) */
static int c5_skeleton(const unsigned char *r) {
    return r[0x1CD4] != 0 && r[0x1CE1] == 0 && *(const int *)(r + 0x1C40) <= 0
        && !c5_heathen(r) && !c5_puzzle_heathen(r);
}

/* SetHealth 0x4758B0 (cause back to -1), the last-update time +0x1C38 to
   the game clock 0x4036E0 (on 0x425950()), then the stop -- what the
   game's own Reanimate does, with the clock too (without it the villager
   ages by the time spent dead).  Only while the room predicate 0x472BD0
   says there is room. */
static int c5_revive(int index, int health, int cure) {
    unsigned char *r = c5_record(index);
    if (c5_reanimating()) {
        return 0;
    }
    if (!(TC0(0x472BD0u, C5_MANAGER) & 0xFF)) {
        return -1;
    }
    TC2(0x4758B0u, r + 0x1C34, health, -1);
    *(int *)(r + 0x1C38) = TC0(0x4036E0u, ((getter_fn)(uintptr_t)0x425950u)());
    if (cure) {
        r[0x1C48] = 0;
    }
    TC0(0x473440u, r);
    return 1;
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

/* ---- Food sources ------------------------------------------------------- */

static const ce_value_def C5_VALUES[] = {
    { "Noni bushes", 0, 1000, "One store for every bush; the game's own ceiling is 1000." },
    { "Crops", 0, 800,
      "Only once the Hydroponic Farm is built (before it, the game would draw crops on "
      "the unbuilt farm). The ceiling is 800." },
};

static int c5_farm_built(void) {
    return (TC1(0x43AE80u, 0x51E008u, 5) & 0xFF) != 0;
}

static int c5_value_get(int which) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV5_WORLD_GLOBAL;
    if (world == NULL || which < 0 || which > 1 || (which == 1 && !c5_farm_built())) {
        return -1;
    }
    return *(int *)(world + (which == 0 ? 0x17D58 : 0x17D5C));
}

/* Plain writes, as the game's own events change them (0x414FB5, 0x41678B);
   the bushes' art is redrawn from the store every frame. */
static int c5_value_set(int which, int amount) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV5_WORLD_GLOBAL;
    if (c5_value_get(which) < 0) {
        return 0;
    }
    *(int *)(world + (which == 0 ? 0x17D58 : 0x17D5C)) = amount;
    return 1;
}

/* ---- Puzzles ---------------------------------------------------------------

   Item i is {progress, solve time} at 0x51E008 + 8i, done at the threshold
   0x51DF30[i] (filled when the game starts).  Solved goes through the
   game's own Advance 0x43AF80 (thiscall on 0x51E008, the id; ret 4) from
   one short of the threshold, as the item's last step does: it stamps the
   play clock, gives the hut achievements and runs the item's completion --
   or, where the research found the completion needs more than the item
   (The Prison Break, The Tribute Statue), the progress and the play clock
   (0x41ED40 on 0x51D490) written directly.  Unsolved is the game's own
   Reset 0x43AC10 (progress 0 and the item's own reset) or, for the huts and
   the nursery milestone, the progress alone; the solve time back to 0.
   Seen live: The Prison Break's fence and bin follow its progress. */
#define C5P_DIRECT 1           /* solved by the progress and clock alone */
#define C5P_RESET 2            /* unsolved through Reset */
#define C5P_HUT 4              /* refused while a builder is mid-way (handler +0x30) */
#define C5P_NURSERY 8          /* the milestone: solved only once the building is */
#define C5P_NURSERY_HUT 16     /* the building: unsolved only while the milestone is */

typedef struct {
    int id;
    int how;
    unsigned int handler;      /* C5P_HUT: the hut's own object */
} c5_puzzle;

static const ce_puzzle_def C5_PUZZLE_DEFS[] = {
    { "The Nursery School (the milestone, not on the Puzzles screen)", 1, 1,
      "Solved only once the nursery school building is built." },
    { "The Prison Break", 1, 1, NULL },
    { "The Hungry Totem", 1, 1, NULL },
    { "The Knowing Totem", 1, 1, NULL },
    { "The Buried Mausoleum", 1, 0,
      "Not offered as unsolved: graves already in the mausoleum would sit in an undug "
      "one." },
    { "The Blocking Totem", 1, 1, NULL },
    { "The Hollow Totem", 1, 1, NULL },
    { "The Lake", 1, 0,
      "Not offered as unsolved: the lake's creatures would stay in a dead lake." },
    { "The Pain Totem", 1, 1, NULL },
    { "The Rainbow Totem", 1, 1, NULL },
    { "The Tribute Statue", 1, 1, NULL },
    { "The Blind Totem", 1, 1, NULL },
    { "Hut 1 (not on the Puzzles screen)", 1, 1,
      "Refused while a builder is part way through it. Unsolved, the village keeps "
      "everyone it has, but makes no room for more." },
    { "Hut 2 (not on the Puzzles screen)", 1, 1,
      "Refused while a builder is part way through it. Unsolved, the village keeps "
      "everyone it has, but makes no room for more." },
    { "Hut 3 (not on the Puzzles screen)", 1, 1,
      "Refused while a builder is part way through it. Unsolved, the village keeps "
      "everyone it has, but makes no room for more." },
    { "The clothing hut", 1, 1, "Refused while a builder is part way through it." },
    { "The love shack", 1, 1,
      "Refused while a builder is part way through it. Unsolved, no one conceives until "
      "it is built again." },
    { "The nursery school building", 1, 1,
      "Refused while a builder is part way through it. Unsolved only while the nursery "
      "milestone is unsolved." },
};

static const c5_puzzle C5_PUZZLES[] = {
    { 0, C5P_NURSERY, 0 },
    { 2, C5P_DIRECT | C5P_RESET, 0 },
    { 3, C5P_RESET, 0 },
    { 4, C5P_RESET, 0 },
    { 6, 0, 0 },
    { 7, C5P_RESET, 0 },
    { 8, C5P_RESET, 0 },
    { 10, 0, 0 },
    { 11, C5P_RESET, 0 },
    { 12, C5P_RESET, 0 },
    { 14, C5P_DIRECT | C5P_RESET, 0 },
    { 15, C5P_RESET, 0 },
    { 19, C5P_HUT, 0x51DCD8u },
    { 20, C5P_HUT, 0x51DA28u },
    { 21, C5P_HUT, 0x51DBC8u },
    { 22, C5P_HUT, 0x51DAB0u },
    { 23, C5P_HUT, 0x51DB40u },
    { 24, C5P_HUT | C5P_NURSERY_HUT, 0x51DC50u },
};

#define C5_PUZZLE_COUNT ((int)(sizeof C5_PUZZLES / sizeof C5_PUZZLES[0]))
#define C5_PUZZLE_ENTRY(id) ((int *)(uintptr_t)(0x51E008u + 8u * (unsigned int)(id)))
#define C5_THRESHOLD(id) (*(int *)(uintptr_t)(0x51DF30u + 4u * (unsigned int)(id)))

static int c5_item_done(int id) {
    return C5_THRESHOLD(id) >= 1 && C5_PUZZLE_ENTRY(id)[0] >= C5_THRESHOLD(id);
}

static int c5_puzzle_solved(int which) {
    if (which < 0 || which >= C5_PUZZLE_COUNT) {
        return 0;
    }
    return c5_item_done(C5_PUZZLES[which].id);
}

static int c5_puzzle_set(int which, int solved) {
    const c5_puzzle *p;
    int *entry;
    int threshold;
    if (which < 0 || which >= C5_PUZZLE_COUNT) {
        return 0;
    }
    p = &C5_PUZZLES[which];
    entry = C5_PUZZLE_ENTRY(p->id);
    threshold = C5_THRESHOLD(p->id);
    if (threshold < 1) {
        return 0;                      /* the table is not filled yet */
    }
    if ((p->how & C5P_HUT) && *(unsigned char *)(uintptr_t)(p->handler + 0x30) != 0) {
        return 0;                      /* a builder is part way through it */
    }
    if (solved) {
        if ((p->how & C5P_NURSERY) && !c5_item_done(24)) {
            return 0;
        }
        if (p->how & C5P_DIRECT) {
            entry[0] = threshold;
            entry[1] = TC0(0x41ED40u, 0x51D490u);
            return 1;
        }
        entry[0] = threshold - 1;
        TC1(0x43AF80u, 0x51E008u, p->id);
        return entry[0] >= threshold;
    }
    if ((p->how & C5P_NURSERY_HUT) && c5_item_done(0)) {
        return 0;
    }
    if (p->how & C5P_RESET) {
        TC1(0x43AC10u, 0x51E008u, p->id);
    }
    entry[0] = 0;
    entry[1] = 0;
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

typedef int (__cdecl *c5_rand_fn)(int bound);

/* The game's own rand(bound) 0x403660 (cdecl, 0..bound-1). */
static int c5_rand_below(int n) {
    return ((c5_rand_fn)(uintptr_t)0x403660u)(n);
}

/* A villager a question may feature: a believer, never a Heathen. */
static int c5_believer(const unsigned char *r) {
    return !c5_heathen(r);
}

static const ce_adapter C5_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT | CAP_PREFS
        | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK | CAP_STATUS
        | CAP_BEHAVIOUR | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY | CAP_SPAWN_FACTION | CAP_VALUES
        | CAP_PUZZLES | CAP_CANCEL | CAP_RELITTER | CAP_UNBORN | CAP_REVIVE | CAP_CHOICE,
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
    C5_STATUSES, 5,
    C5_BEHAVIOURS, (int)(sizeof C5_BEHAVIOURS / sizeof C5_BEHAVIOURS[0]),
    NULL, 0,
    "Not in New Believers:\r\n\r\n"
    "- The puzzles' own Heathens (the Heathen Mommy and the others) keep their faction, "
    "their role and their mask, and their puzzles are not offered: marked alone, the "
    "Heathen at the heart of each would stay a Heathen. The Hydroponic Farm and The Last "
    "Heathen likewise.\r\n"
    "- The Buried Mausoleum and The Lake as unsolved (see each one's note).\r\n"
    "- Heathens can not be made sick (the game cures them every moment) or pregnant "
    "(Heathens never give birth), and are never revived (no Heathen grave is ever made).\r\n"
    "- The unborn baby's starting skill: what the baby does with it at birth was not "
    "traced to the end, so only the father's name and looks are offered.\r\n"
    "- Actions that solve or advance a puzzle, conversions, the Heathens' own camp life, "
    "burying, picking things up, new clothes and games that stop other villagers.\r\n"
    "- Revive: nothing while the game's own Reanimate is under way; buried villagers "
    "(their record is gone) and skeletons that have already crumbled away.\r\n"
    "- Esteemed Elder and Retired Chief are worked out from skills and the chief puzzle.\r\n"
    "- Counting: \"Becomes a believer\", \"Becomes a Heathen\" and new Heathens made here "
    "are not your conversions, so they never count toward the game's trophies (A "
    "Heathen's Prerogative, If You Can't Beat 'Em...) or the Heathens Converted "
    "statistic. Heathens you convert in play count as always.",
    48, 14, 30, 1, 0x118,
    "Refills the noni bushes and, once the farm is built, the crops.",
    "Your village gains %d food.", "Your village has lost %d food.",
    "Your village has gained %d tech points.", "Your village has lost %d tech points.",
    c5_record, c5_listed, c5_arm_refusal, c5_room, c5_spawn, c5_kill, c5_vanish, c5_sicken,
    c5_conceive, c5_set_status, c5_behave, NULL, c5_food, c5_tech, c5_change_food, c5_change_tech,
    c5_refill, c5_parents_supported, c5_set_parents,
    C5_VALUES, 2, c5_value_get, c5_value_set,
    C5_PUZZLE_DEFS, C5_PUZZLE_COUNT, c5_puzzle_solved, c5_puzzle_set,
    c5_cancel, c5_relitter, c5_unborn,
    c5_skeleton, c5_revive,
    2, 0x1C4C,
    /* The two-choice popup (0x418020): 48 characters, 11 lines for the
       question and 17 for a result (the tallest stock question and result:
       Innovation in Farming's), the title above the result, labels of 38
       characters (the longest stock). */
    48, 11, 48, 17, 0, 38, c5_rand_below, c5_believer
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

/* A question (story_objects.inc): a copy of the first two-choice event's
   vtable (0x497D34) with the custom ids, featuring the picked or a random living believer. */
static void *c5_choice_object(void) {
    return choice_object(5, C5_STRING_TABLE, C5_TITLE_ID, C5_BODY_ID, 0, 0x497D34u,
                         (void *)c5_title_id);
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
