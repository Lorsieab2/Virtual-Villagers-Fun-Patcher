/* Custom Island Event: The Lost Children.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md).  The world is
   [0x4997BC] and the villager pool [0x499F24] (record i at pool + i*0xE48C,
   256 records; a totem statue is a record with +0x558 set).

   DELIVERY.  The single-result island event's constructor 0x4348E0 calls its
   chooser 0x434570 at 0x4349B2 (ECX = the event object, kind, magnitude,
   ret 8), which picks the case and lets it write the text (+0x277F) and make
   its changes.  With a custom event armed, the companion's replacement for
   that call writes the custom text there and applies the changes; the game's
   own trigger has already rescheduled, sounded and counted the event, and
   its own modal popup (0x401AD0) shows it (the draw, 0x433200, centres the
   first line as the title).  The Origins Barrel (magnitude 0x7F4B1A2C) always
   goes to the game's chooser.  The family rolls (story_vv2.inc) send an
   armed custom event to this family; the first island event of a village is
   always a two-choice event, so a custom one waits until it has happened. */

#define VV2_POOL() (*(unsigned char **)(uintptr_t)VV2_POOL_GLOBAL)
#define VV2_WORLD() (*(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL)
#define VV2_BARREL_MAGNITUDE 0x7F4B1A2C
#define VV2_SELECTED 0x304F0u

static unsigned char *c2_record(int index) {
    unsigned char *pool = VV2_POOL();
    if (pool == NULL || index < 0 || index >= VV2_RECORD_COUNT) {
        return NULL;
    }
    return pool + (size_t)index * VV2_RECORD_STRIDE;
}

/* A living villager: active, health above 0, not a totem statue. */
static int c2_listed(const unsigned char *r) {
    return r[0x30] != 0 && *(const int *)(r + 0x52C) > 0 && *(const int *)(r + 0x558) == 0;
}

static int c2_free_record(void) {
    int i;
    for (i = 0; i < VV2_RECORD_COUNT; ++i) {
        if (c2_record(i)[0x30] == 0) {
            return i;
        }
    }
    return -1;
}

static const char *c2_arm_refusal(void) {
    unsigned char *world = VV2_WORLD();
    if (world == NULL || VV2_POOL() == NULL) {
        return "There is no village to have an island event.";
    }
    if (*(int *)(world + VV2_EVENT_COUNT_FIELD) == 0) {
        return "A village's first island event is always one with a choice. A custom island "
               "event can be queued once it has happened.";
    }
    if (!vv2_any_villager(VV2_POOL(), 0x118, -1, 0, 0)) {
        return "An island event needs a living adult in the village.";
    }
    return NULL;
}

/* The game's own room predicate 0x44B310 (population below the mode's cap
   and the housing gates) and a record the creator can use: in the
   population modes with a 256 cap the renders' clamped slot scan would
   otherwise reuse record 255 when every record is taken. */
static int c2_room(void) {
    unsigned char *pool = VV2_POOL();
    return pool != NULL && (TC0(0x44B310u, pool) & 0xFF) != 0 && c2_free_record() >= 0;
}

static void c2_apply_spawn_fields(unsigned char *r, const ce_spawn *s);

/* 0x44F580 (thiscall on the pool: lineage, skill selector, value, sex, age;
   ret 0x14) -- the creator the Barrel and Old Friends use.  Lineage -1 is the
   game's own random; selector 0 gives no starting skill. */
static int c2_spawn(const ce_spawn *s) {
    int index;
    if (!c2_room()) {
        return -1;
    }
    index = TC5(0x44F580u, VV2_POOL(), -1, 0, 0, s->sex == STORY_SEX_MALE ? 1 : 2, s->age);
    if (index < 0 || index >= VV2_RECORD_COUNT) {
        return -1;
    }
    c2_apply_spawn_fields(c2_record(index), s);
    return index;
}

/* Death is health 0, as old age (0x43BDEE) writes it; the skeleton stays
   until a villager buries it (0x465024). */
static int c2_kill(int index) {
    *(int *)(c2_record(index) + 0x52C) = 0;
    return 1;
}

/* A Dangerous Mission (0x433E9C) clears the record's active byte; the
   game's own removal of a long-dead skeleton (0x43B720) also drops the
   selection when the record was the selected one, which is done first. */
static int c2_vanish(int index) {
    unsigned char *r = c2_record(index);
    if (r[0x31] != 0) {
        r[0x31] = 0;
        *(int *)(VV2_WORLD() + VV2_SELECTED) = -1;
    }
    r[0x30] = 0;
    return 1;
}

/* Sick is +0x53C = 1, as the Epidemic's 0x4332F0 writes it. */
static int c2_sicken(int index) {
    *(int *)(c2_record(index) + 0x53C) = 1;
    return 1;
}

/* A pregnancy, written as the conception routine 0x44B980 writes it:
     +0x540 = the carrier's processed age (+0x534);
     +0x544 = 2 or 3 for twins or triplets, 0 for one baby;
     +0x5E4 / +0x5E8 = the inherited skill (none: 0 / 0);
     +0x5EC = the father's lineage (+0x554);
     +0x5C0 = the father's name, +0x5E0 / +0x5DC his head and body;
     +0x44 = 0x1A;
   Babies Made (+0x2E500) once, and the parentage log with the father's
   record (the call the routine's own trampoline makes).  An unknown father
   is "Unknown" with the carrier's own head and body.  Each baby only while
   the room predicate says there is room; there is no sex check in the
   conception or the delivery (0x43BE01). */
static int c2_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *pool = VV2_POOL();
    unsigned char *r = c2_record(index);
    unsigned char *f = father >= 0 ? c2_record(father) : NULL;
    int babies;
    int age;
    if (*(int *)(r + 0x540) != 0 || *(int *)(r + 0x530) < 360) {
        ++result->refused;
        return 0;
    }
    if (!(TC0(0x44B310u, pool) & 0xFF)) {
        result->no_room_babies += litter;
        return 0;
    }
    age = *(int *)(r + 0x534);
    *(int *)(r + 0x540) = age != 0 ? age : 1;
    *(int *)(r + 0x544) = 0;
    *(int *)(r + 0x5E4) = 0;
    *(int *)(r + 0x5E8) = 0;
    *(int *)(r + 0x5EC) = f != NULL ? *(int *)(f + 0x554) : *(int *)(r + 0x554);
    ce_write_name(r + 0x5C0, 0x1C, f != NULL ? (const char *)(f + 0x564) : "Unknown");
    *(int *)(r + 0x5E0) = *(int *)((f != NULL ? f : r) + 0x548);
    *(int *)(r + 0x5DC) = *(int *)((f != NULL ? f : r) + 0x54C);
    *(int *)(r + 0x44) = 0x1A;
    babies = 1;
    while (babies < litter && (TC0(0x44B310u, pool) & 0xFF)) {
        ++babies;
        *(int *)(r + 0x544) = babies;
    }
    result->no_room_babies += litter - babies;
    ++*(int *)(VV2_WORLD() + 0x2E500);
    story_log_conception(2, pool, r, f);
    return babies;
}

/* ---- Esteemed Elders and their totems -------------------------------- */

static const char *const C2_STATUSES[] = {
    "Becomes an Esteemed Elder (with a totem)",
    "Totem: brown face, blue mouth", "Totem: green figure", "Totem: teal, red crest",
    "Totem: yellow and purple", "Totem: red headdress", "Totem: dark navy face",
    "Totem: tall carved wood", "Totem: green grinning face",
};

static int c2_totems(void) {
    int i;
    int n = 0;
    for (i = 0; i < VV2_RECORD_COUNT; ++i) {
        unsigned char *t = c2_record(i);
        if (t[0x30] != 0 && *(int *)(t + 0x558) != 0) {
            ++n;
        }
    }
    return n;
}

/* The totem statue 0x44D190 made for the elder in `r`: it copies the name,
   sex, lineage and both parents' names onto the statue and keeps no index,
   so all of them must agree -- and exactly one statue may. */
static unsigned char *c2_totem_of(const unsigned char *r) {
    unsigned char *found = NULL;
    int i;
    for (i = 0; i < VV2_RECORD_COUNT; ++i) {
        unsigned char *t = c2_record(i);
        if (t == r || t[0x30] == 0 || *(int *)(t + 0x558) == 0) {
            continue;
        }
        if (memcmp(t + 0x564, r + 0x564, 0x18) != 0 || *(int *)(t + 0x538) != *(int *)(r + 0x538)
            || *(int *)(t + 0x554) != *(int *)(r + 0x554) || memcmp(t + 0x57D, r + 0x57D, 0x32) != 0) {
            continue;
        }
        if (found != NULL) {
            return NULL;
        }
        found = t;
    }
    return found;
}

/* 0: the game's own elder-and-totem routine 0x44D190 (thiscall on the pool,
   the elder's index, ret 4), which 0x44D4C0 calls when a villager has
   mastered three skills, with that caller's own guards: fewer than 50
   totems, a free record, not already an elder; and the Village Elders count
   (+0x2E514) the caller adds.  1..8: the elder's totem drawn with art frame
   0..7 -- the statue's +0x550 modulo 8, read every frame by 0x445B50 and the
   map 0x4478E0, and by nothing else for a statue. */
static int c2_set_status(int index, int status) {
    unsigned char *r = c2_record(index);
    if (status == 0) {
        if (*(int *)(r + 0x7FC) != 0 || c2_totems() >= 50 || c2_free_record() < 0) {
            return 0;
        }
        TC1(0x44D190u, VV2_POOL(), index);
        ++*(int *)(VV2_WORLD() + 0x2E514);
        return 1;
    }
    if (status >= 1 && status <= 8) {
        unsigned char *totem = *(int *)(r + 0x7FC) != 0 ? c2_totem_of(r) : NULL;
        int value;
        if (totem == NULL) {
            return 0;
        }
        value = *(int *)(totem + 0x550);
        value = value - (value % 8 + 8) % 8 + (status - 1);
        while (value < 1) {
            value += 8;
        }
        while (value > 123) {
            value -= 8;
        }
        *(int *)(totem + 0x550) = value;
        return 1;
    }
    return 0;
}

static const char *const C2_BEHAVIOURS[] = {
    "Stops what they are doing", "Cools off with a swim", "Celebrates", "Visits the graves",
    "Sneezes", "Recovers fully (cured, full health)"
};

/* What stock events do to one villager (thiscall on the pool, the index):
   stop 0x4492A0, the Heat Wave's swim 0x451690 (0x4338D4), Blessings Day's
   celebration 0x452920 (0x433C38), the Day of Honor's grave visit 0x454890
   (0x433A98), Spring Allergies' sneeze 0x44AF20 (0x433B04); and the Origins
   Full Heal's cure (sick 0, health 100). */
static int c2_behave(int index, int behaviour) {
    unsigned char *pool = VV2_POOL();
    unsigned char *r = c2_record(index);
    switch (behaviour) {
    case 0: TC1(0x4492A0u, pool, index); return 1;
    case 1: TC1(0x451690u, pool, index); return 1;
    case 2: TC1(0x452920u, pool, index); return 1;
    case 3: TC1(0x454890u, pool, index); return 1;
    case 4: TC1(0x44AF20u, pool, index); return 1;
    case 5:
        *(int *)(r + 0x53C) = 0;
        *(int *)(r + 0x52C) = 100;
        return 1;
    default: return 0;
    }
}

static int c2_food(void) { return *(int *)(VV2_WORLD() + 0x2EAA4); }
static int c2_tech(void) { return *(int *)(VV2_WORLD() + 0x2EADC); }

/* Written directly, as the stock events change them (0x433706, 0x433787):
   the adders 0x4262B0 / 0x426290 are detoured through the Origins doubler.
   A gain also counts in Food Gathered (+0x2E504) / Points Earned (+0x2E4FC)
   as the adders count it. */
static void c2_change_food(int op, int amount) {
    unsigned char *world = VV2_WORLD();
    int before = *(int *)(world + 0x2EAA4);
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(world + 0x2EAA4) = after;
    if (after > before) {
        *(int *)(world + 0x2E504) += after - before;
    }
}

static void c2_change_tech(int op, int amount) {
    unsigned char *world = VV2_WORLD();
    int before = *(int *)(world + 0x2EADC);
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(world + 0x2EADC) = after;
    if (after > before) {
        *(int *)(world + 0x2E4FC) += after - before;
    }
}

/* The coconut trees (+0x2EACC, the game's own ceiling 1500) and, while the
   farm is planted and its soil not exhausted (0x425AC0), the crops
   (+0x2EAD8, ceiling 800): the stores the West Wind (0x4342DA) adds to.
   The fish and the soil are not refilled: they are depleted by design and
   restored only by their puzzles. */
static int c2_refill(void) {
    unsigned char *world = VV2_WORLD();
    if (*(int *)(world + 0x2EACC) < 1500) {
        *(int *)(world + 0x2EACC) = 1500;
    }
    if (world[0x2E798] != 0 && !(TC0(0x425AC0u, world) & 0xFF)) {
        *(int *)(world + 0x2EAD8) = 800;
    }
    return 1;
}

static int c2_parents_supported(void) {
    return 1;
}

static int c2_set_parents(int index, const ce_change *c) {
    return ce_set_record_parents(c2_record(index), 0x57D, 0x596, 0x19, 0x5B0, 0x5B4, 0x5B8, 0x5BC,
                                 30, 30, c);
}

static const char *const C2_SKILLS[] = { "Parenting", "Building", "Farming", "Healing", "Research" };

static const ce_adapter C2_ADAPTER;

static void c2_apply_spawn_fields(unsigned char *r, const ce_spawn *s) {
    ce_apply_spawn_record(&C2_ADAPTER, r, s);
}

static const ce_adapter C2_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK | CAP_STATUS
        | CAP_BEHAVIOUR | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY,
    "The Lost Children",
    0x118, 40, 1100,
    VV2_RECORD_COUNT, 0x18,
    0x564, 0x538, 0x530, 0x548, 0x54C, 0x5F0, 0x6E8, 0x7E4,
    1, 2,
    62, 62,
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,"
    "flowers,bees,the dark,caves,herbs,berries,snakes,wind,rocks,"
    "heights,the ocean,playing,exploring,blue,green,red,yellow,drums,"
    "bushes,bananas,coconuts,sand,sunlight,wood,crab meat,whale meat,"
    "fish,fruit,papaya,flies,swimming,running,learning,dancing,"
    "monkeys,parrots,work,lifting,surprises,jokes,sleeping,jumping,"
    "cooking,fire,eating,dragonflies,owls,dreaming,children,talking,"
    "holidays,vegetables,quiet,clouds,dirt",
    30, 30,
    5, 0, C2_SKILLS,
    0x57D, 0x596, 0x19, 0x5B0, 0x5B4, 0x5B8, 0x5BC,
    C2_STATUSES, 9,
    C2_BEHAVIOURS, 6,
    NULL, 0,
    "Not in The Lost Children:\r\n\r\n"
    "- Village and puzzle states: no puzzle has a completion routine that can be "
    "called on its own (each is tied to its objects and goal messages).\r\n"
    "- Refill: the fish and the farm soil are depleted by design and restored only by "
    "their puzzles, so only the coconut trees and the crops are refilled.\r\n"
    "- Golden Child, chief, faction: The Lost Children has none.\r\n"
    "- An Esteemed Elder's totem type can only be changed once the villager is an "
    "Esteemed Elder (the game makes the totem then).",
    46, 20, 46, 0, 360,
    "Refills the coconut trees and, while the farm is planted, the crops.",
    "Your villagers gain %d food.", "Your villagers lose %d food.",
    "Your villagers gain %d tech points.", "Your villagers lose %d tech points.",
    c2_record, c2_listed, c2_arm_refusal, c2_room, c2_spawn, c2_kill, c2_vanish, c2_sicken,
    c2_conceive, c2_set_status, c2_behave, NULL, c2_food, c2_tech, c2_change_food,
    c2_change_tech, c2_refill, c2_parents_supported, c2_set_parents
};

/* ---- Delivery ----------------------------------------------------------- */

/* The replacement for `call 0x434570` at 0x4349B2 (thiscall, ret 8). */
static void __fastcall c2_choose(void *event, void *unused_edx, int kind, int magnitude) {
    (void)unused_edx;
    if (magnitude != VV2_BARREL_MAGNITUDE
        && ce_deliver(2, (char *)event + 0x277F, 9000)) {
        return;
    }
    TC2(0x434570u, event, kind, magnitude);
}

/* ---- Title ---------------------------------------------------------------

   The HUD (0x4299B0) builds the selected villager's title and every branch
   reaches 0x429DE3 `call 0x40C510` (set the label's text; thiscall on the
   label, the text, ret 4).  The detour replaces the text with the selected
   villager's custom title, if any. */
static int __fastcall c2_title(void *label, void *unused_edx, const char *text) {
    (void)unused_edx;
    unsigned char *world = VV2_WORLD();
    const char *custom = NULL;
    if (world != NULL) {
        custom = titles_lookup(2, c2_record(*(int *)(world + VV2_SELECTED)));
    }
    return TC1(0x40C510u, label, custom != NULL ? custom : text);
}
