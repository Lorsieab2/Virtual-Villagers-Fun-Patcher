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
    return r[0x30] != 0 && *(const int *)(r + 0x52C) > 0 && r[0x558] == 0;
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

/* What a natural conception counts, at conception (0x44BA5E..0x44BAD2):
   Babies Made (+0x2E500) once per baby, Triplets Birthed (+0x2E524) once
   for triplets.  The Lost Children has no twins counter of its own; with
   the Village Statistics row ticked its hook at 0x44BA8C (the instruction
   after the twins branch) adds one to the pending Twins Birthed field
   (+0x2E5E4) and its triplets hook takes it back, so twins count once and
   triplets not as twins.  The hook's presence is the row's: without it the
   field is not the statistics' and is never written. */
static const unsigned char C2_TWINS_HOOK_STOCK[6] = { 0x8B, 0x87, 0xD4, 0x74, 0xE5, 0x00 };

static void c2_count_conception(int babies) {
    unsigned char *world = VV2_WORLD();
    *(int *)(world + 0x2E500) += babies;
    if (babies == 3) {
        ++*(int *)(world + 0x2E524);
    } else if (babies == 2 && mem_readable(0x44BA8Cu, 6)
               && memcmp((const void *)(uintptr_t)0x44BA8Cu, C2_TWINS_HOOK_STOCK, 6) != 0) {
        ++*(int *)(world + 0x2E5E4);
    }
}

/* A pregnancy, written as the conception routine 0x44B980 writes it:
     +0x540 = the carrier's processed age (+0x534);
     +0x544 = 2 or 3 for twins or triplets, 0 for one baby;
     +0x5E4 / +0x5E8 = the inherited skill (none: 0 / 0);
     +0x5EC = the father's lineage (+0x554);
     +0x5C0 = the father's name, +0x5E0 / +0x5DC his head and body;
     +0x44 = 0x1A;
   the counters as the routine counts them (c2_count_conception), and the
   parentage log with the father's record (the call the routine's own
   trampoline makes).  An unknown father
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
    c2_count_conception(babies);
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
        if (t[0x30] != 0 && t[0x558] != 0) {
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
        if (t == r || t[0x30] == 0 || t[0x558] == 0) {
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
        if (r[0x7FC] != 0 || c2_totems() >= 50 || c2_free_record() < 0) {
            return 0;
        }
        TC1(0x44D190u, VV2_POOL(), index);
        ++*(int *)(VV2_WORLD() + 0x2E514);
        return 1;
    }
    if (status >= 1 && status <= 8) {
        unsigned char *totem = r[0x7FC] != 0 ? c2_totem_of(r) : NULL;
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

/* What stock code does to one villager (thiscall on the pool, the index):
   the first six as the island events do (the Heat Wave's swim 0x451690,
   Blessings Day's celebration 0x452920, the Day of Honor's grave visit
   0x454890, Spring Allergies' sneeze 0x44AF20, the Origins Full Heal's
   cure), then the starters the game's idle choosers, job dispatcher and drop
   handler call.  Never: puzzle actions, burial, pickups, new clothes,
   embracing, lessons or games that stop other villagers, or a starter no
   stock code calls. */
static const ce_action C2_BEHAVIOURS[] = {
    { "Stops what they are doing", ACT_STOP, 0x4492A0u, 0 },
    { "Cools off with a swim", ACT_CALL, 0x451690u, 0 },
    { "Celebrates", ACT_CALL, 0x452920u, 0 },
    { "Visits the graves", ACT_CALL, 0x454890u, 0 },
    { "Sneezes", ACT_EFFECT, 0x44AF20u, 0 },
    { "Recovers fully (cured, full health)", ACT_RECOVER, 0, 0 },
    { "Does something of their own choosing", ACT_CALL, 0x461850u, 0 },
    { "Dances", ACT_CALL, 0x450580u, 0 },
    { "Dances in a circle (a long dance)", ACT_CALL, 0x4530E0u, 0 },
    { "Rain dancing", ACT_CALL, 0x455A20u, 0 },
    { "Jumpy!", ACT_CALL, 0x455AC0u, 0 },
    { "Enjoys the pond", ACT_CALL, 0x45F420u, 0 },
    { "Goes swimming", ACT_CALL_ARG, 0x45C1B0u, 0 },
    { "Relaxes at the beach", ACT_CALL, 0x451E10u, 0 },
    { "Relaxes", ACT_CALL, 0x454AB0u, 0 },
    { "Reflects", ACT_CALL, 0x4523A0u, 0 },
    { "Exercises (Building practice)", ACT_CALL, 0x455330u, 0 },
    { "Gets a drink", ACT_CALL, 0x453430u, 0 },
    { "Cools their feet in the stream", ACT_CALL, 0x453A70u, 0 },
    { "Does the laundry", ACT_CALL, 0x453D10u, 0 },
    { "Listens to a story", ACT_CALL, 0x44A0E0u, 0 },
    { "Tells a story (Parenting practice)", ACT_CALL, 0x449F40u, 0 },
    { "Thinking", ACT_CALL, 0x44FE10u, 0 },
    { "Unsure what to do (wanders)", ACT_CALL, 0x45E700u, 0 },
    { "Nature is calling!", ACT_CALL, 0x45CD00u, 0 },
    { "A little bit lonely", ACT_CALL, 0x45CDC0u, 0 },
    { "Goes indoors", ACT_CALL, 0x44A240u, 0 },
    { "Runs away", ACT_CALL, 0x44B010u, 0 },
    { "Shakes their head", ACT_CALL, 0x44B1B0u, 0 },
    { "Not feeling well (only looks it)", ACT_CALL, 0x45C590u, 0 },
    { "Recovers at the hospital", ACT_CALL, 0x45C250u, 0 },
    { "Admires the ancient mosaic", ACT_CALL, 0x457AA0u, 0 },
    { "Admires the ancient gong encasement", ACT_CALL, 0x459710u, 0 },
    { "Observes the Gong of Wonder", ACT_CALL, 0x459980u, 0 },
    { "Reads the writings on the wall", ACT_CALL, 0x459A50u, 0 },
    { "Curious about the thorny bushes", ACT_CALL, 0x4501F0u, 0 },
    { "Curious about the ancient place", ACT_CALL, 0x4503C0u, 0 },
    { "Curious about the vines", ACT_CALL, 0x454F50u, 0 },
    { "Curious about the patch of soil", ACT_CALL, 0x455030u, 0 },
    { "Curious about the strange flower", ACT_CALL, 0x45D670u, 0 },
    { "Tries to reach the coconuts (children)", ACT_CALL, 0x454BC0u, 0 },
    { "Plays in the very narrow stream (children)", ACT_CALL, 0x454D40u, 0 },
    { "Looks at the dry shrubs (children)", ACT_CALL, 0x454E40u, 0 },
    { "Looks at the fire (children)", ACT_CALL, 0x455170u, 0 },
    { "Fishes (Farming practice, food)", ACT_CALL, 0x4507A0u, 0 },
    { "Harvests coconuts (Farming practice, food)", ACT_CALL, 0x456F70u, 0 },
    { "Plants or harvests crops (Farming practice)", ACT_CALL, 0x4593D0u, 0 },
    { "Waters the crops (Farming practice)", ACT_CALL, 0x45D280u, 0 },
    { "Eats (uses food)", ACT_CALL, 0x4513F0u, 0 },
};

/* The stop 0x4492A0 first, as the drop handler and the stock events do
   (a sneeze is an effect, not an activity, and is not stopped for). */
static int c2_behave(int index, int behaviour) {
    unsigned char *pool = VV2_POOL();
    unsigned char *r = c2_record(index);
    const ce_action *act;
    if (behaviour < 0 || behaviour >= (int)(sizeof C2_BEHAVIOURS / sizeof C2_BEHAVIOURS[0])) {
        return 0;
    }
    act = &C2_BEHAVIOURS[behaviour];
    if (act->kind == ACT_EFFECT) {
        TC1(act->routine, pool, index);
        return 1;
    }
    if (act->kind == ACT_RECOVER) {
        *(int *)(r + 0x53C) = 0;
        *(int *)(r + 0x52C) = 100;
    }
    TC1(0x4492A0u, pool, index);
    if (act->kind == ACT_CALL) {
        TC1(act->routine, pool, index);
    } else if (act->kind == ACT_CALL_ARG) {
        TC2(act->routine, pool, index, act->arg);
    }
    return 1;
}

/* ---- Pregnancy: none, a different number of babies, the father --------- */

/* "0 babies": as the delivery (0x43BF6E) ends a pregnancy -- +0x540 and the
   litter +0x544 cleared (the conception writes +0x544 only for twins and
   triplets), +0x44 = 0x1A.  Babies Made is left as counted. */
static int c2_cancel(int index) {
    unsigned char *r = c2_record(index);
    if (*(int *)(r + 0x540) == 0) {
        return 0;
    }
    *(int *)(r + 0x540) = 0;
    *(int *)(r + 0x544) = 0;
    *(int *)(r + 0x44) = 0x1A;
    return 1;
}

/* The litter +0x544 (0 one baby, 2 twins, 3 triplets, as A New Home's);
   each added baby only while the room predicate 0x44B310 says there is room
   (the renders' clamped creator would otherwise reuse record 255). */
static int c2_relitter(int index, int litter, ce_result *result) {
    unsigned char *pool = VV2_POOL();
    unsigned char *r = c2_record(index);
    int field = *(int *)(r + 0x544);
    int babies = field == 3 ? 3 : field != 0 ? 2 : 1;
    int added = 0;
    if (litter < babies) {
        *(int *)(r + 0x544) = litter == 1 ? 0 : litter;
        return 0;
    }
    while (babies < litter && (TC0(0x44B310u, pool) & 0xFF) && c2_free_record() >= 0) {
        ++babies;
        ++added;
        *(int *)(r + 0x544) = babies;
    }
    result->no_room_babies += litter - babies;
    return added;
}

/* The father the baby is born to (0x43BE5A passes them to the creator
   0x44F5C0): his name +0x5C0 (0x1C bytes), head +0x5E0 and body +0x5DC --
   the child records them as its father and its head is drawn from both
   parents' heads. */
static int c2_unborn(int index, const ce_change *c) {
    unsigned char *r = c2_record(index);
    if ((c->unborn_head != CE_KEEP && (c->unborn_head < 0 || c->unborn_head >= 30))
        || (c->unborn_body != CE_KEEP && (c->unborn_body < 0 || c->unborn_body >= 30))) {
        return 0;
    }
    if (c->unborn_name[0] != '\0') {
        ce_write_name(r + 0x5C0, 0x1C, c->unborn_name);
    }
    if (c->unborn_head != CE_KEEP) *(int *)(r + 0x5E0) = c->unborn_head;
    if (c->unborn_body != CE_KEEP) *(int *)(r + 0x5DC) = c->unborn_body;
    return 1;
}

/* ---- Revive ------------------------------------------------------------- */

/* A skeleton: present with health 0 or less, not a totem (the Esteemed
   Elder ceremony makes the totem a health-0 record, 0x44D467). */
static int c2_skeleton(const unsigned char *r) {
    return r[0x30] != 0 && r[0x558] == 0 && *(const int *)(r + 0x52C) <= 0;
}

/* Health again, after the last-update time +0x528 is set to the game clock
   0x403200 (else the villager ages by the time spent dead), then the stop
   0x4492A0.  Only while the room predicate 0x44B310 says there is room. */
static int c2_revive(int index, int health, int cure) {
    unsigned char *pool = VV2_POOL();
    unsigned char *r = c2_record(index);
    if (!(TC0(0x44B310u, pool) & 0xFF)) {
        return -1;
    }
    *(int *)(r + 0x528) = TC0(0x403200u, VV2_WORLD());
    *(int *)(r + 0x52C) = health;
    if (cure) {
        *(int *)(r + 0x53C) = 0;
    }
    TC1(0x4492A0u, pool, index);
    return 1;
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

/* The fish a village of this difficulty starts with ([world+0x2EAEC] 0, 1,
   2: 2200, 1100, 550; 0x42524D / 0x42558C). */
static int c2_fish_start(void) {
    int difficulty = *(int *)(VV2_WORLD() + 0x2EAEC);
    return difficulty == 0 ? 2200 : difficulty == 2 ? 550 : 1100;
}

/* The coconut trees (+0x2EACC, the game's own ceiling 1500), the fish
   (+0x2EAD0, the village's starting stock), the field's protection from
   birds (+0x2EAD4, a new village's 1000) and, while the farm is planted
   (the Dam, +0x2E798), the crops (+0x2EAD8, ceiling 800).  Read and written
   directly: the game's field test 0x425AC0 also queues "Birds found your
   field" while its message gate is armed.  The puzzles' own flags (the
   algae fish, the scarecrow) are never touched -- they make the stores
   matter no more, and nothing in the game ever raises them. */
static int c2_refill(void) {
    unsigned char *world = VV2_WORLD();
    int fish = c2_fish_start();
    if (*(int *)(world + 0x2EACC) < 1500) {
        *(int *)(world + 0x2EACC) = 1500;
    }
    if (*(int *)(world + 0x2EAD0) < fish) {
        *(int *)(world + 0x2EAD0) = fish;
    }
    if (*(int *)(world + 0x2EAD4) < 1000) {
        *(int *)(world + 0x2EAD4) = 1000;
    }
    if (world[0x2E798] == 1) {
        *(int *)(world + 0x2EAD8) = 800;
    }
    return 1;
}

/* ---- Food sources ------------------------------------------------------- */

static const ce_value_def C2_VALUES[] = {
    { "Coconut trees", 0, 1500,
      "One store for all three trees; the game's own ceiling is 1500." },
    { "Fish", 0, 2200,
      "A new village has 2200, 1100 or 550 by its difficulty; at 0 fishing stops until "
      "the algae-eating fish puzzle is solved." },
    { "Field protection from birds", 0, 1000,
      "Used up by harvests; at 0 the birds take the field until the scarecrow is built. "
      "A new village has 1000." },
    { "Crops", 0, 800, "Only while the farm is planted (after The Dam). The ceiling is 800." },
};

static int c2_value_get(int which) {
    static const unsigned int fields[4] = { 0x2EACC, 0x2EAD0, 0x2EAD4, 0x2EAD8 };
    unsigned char *world = VV2_WORLD();
    if (world == NULL || which < 0 || which > 3) {
        return -1;
    }
    if (which == 3 && world[0x2E798] != 1) {
        return -1;
    }
    return *(int *)(world + fields[which]);
}

/* Plain writes: the game's own writers are plain adds and subtracts
   (fish 0x463305, the field 0x463264, the regrowth 0x43B9B0). */
static int c2_value_set(int which, int amount) {
    static const unsigned int fields[4] = { 0x2EACC, 0x2EAD0, 0x2EAD4, 0x2EAD8 };
    if (c2_value_get(which) < 0) {
        return 0;
    }
    *(int *)(VV2_WORLD() + fields[which]) = amount;
    return 1;
}

/* ---- Puzzles ---------------------------------------------------------------

   Puzzle k is a solved byte at world+0x2E760+8k after its progress / stage
   dword, an hours slot at world+0x2E52C+4k (0 = never solved) and a
   one-shot message gate byte (1 = its message not yet shown).  Solved
   writes what the completion writes (the progress or stage it reaches, the
   flag, the hours, the gate down); unsolved puts back a new village's state
   with the hours 0.  The buildings are redrawn as the game redraws them
   (0x418660, 0x41C1D0).  The four Gong of Wonder pieces keep the restored
   Gong in step (+0x2E7F0 = all four; on becoming whole also "ready to
   strike", +0x2EAC8, as the pieces' own completions set it).  Traced in the
   stock executable; not yet seen in the running game. */
#define C2P_REFRESH 1
#define C2P_GATE_BACK 2        /* unsolved: its message gate back up */
#define C2P_HERBS 4            /* Herb Mastery: the six herbs too */
#define C2P_GONG 8             /* a Gong of Wonder piece */
#define C2P_CRATE 16           /* the Boxed piece: the crate is opened too */
#define C2P_DAM 32             /* the Dam: the crops start from 0, as it does */
#define C2P_MOSAIC 64          /* unsolved only while the Inlaid piece is unsolved */

typedef struct {
    unsigned int flag;
    unsigned int progress;     /* 0 = none */
    int solved_progress;
    unsigned int hours;
    unsigned int gate;         /* 0 = none */
    int how;
} c2_puzzle;

static const ce_puzzle_def C2_PUZZLE_DEFS[] = {
    { "The Lovely Hut (not on the Puzzles screen)", 1, 1, NULL },
    { "Fire", 1, 1, "Unsolved, the game marks it solved again the next time the fire is lit." },
    { "The Scarecrow", 1, 1, NULL },
    { "The Elder Totem", 1, 1,
      "Totems already made stay. Marking it solved makes no totem (The Inlaid Gong Piece "
      "needs a real one)." },
    { "The Hospital", 1, 1, NULL },
    { "Herb Mastery", 1, 1, "Unsolved also forgets the six herbs, so it can be solved again." },
    { "The Sewing Hut", 1, 1, NULL },
    { "The Dam", 1, 1, "Solved, the crops start from 0 as the game's own completion leaves them." },
    { "The Cutting Tool", 1, 1, NULL },
    { "The Stew", 1, 0,
      "Not offered as unsolved: the game could then never solve it again, or would count "
      "a known recipe as a new one." },
    { "The Vine Wall", 1, 1, NULL },
    { "The Ancient Mosaic", 1, 1,
      "Unsolved is refused once The Inlaid Gong Piece is solved (its piece came out of the "
      "restored mosaic)." },
    { "The Boxed Gong Piece", 1, 1, "Unsolved, the piece is back in the open crate." },
    { "The Sunken Gong Piece", 1, 1, NULL },
    { "The Inlaid Gong Piece", 1, 1, NULL },
    { "The Overgrown Gong Piece", 1, 1, NULL },
    { "Sustainable Fishing", 1, 1, NULL },
};

static const c2_puzzle C2_PUZZLES[] = {
    { 0x2E760, 0x2E75C, 400, 0x2E52C, 0x1FC, C2P_REFRESH },
    { 0x2E768, 0, 0, 0x2E530, 0x1FD, C2P_GATE_BACK },
    { 0x2E770, 0x2E76C, 2, 0x2E534, 0x1FE, C2P_REFRESH },
    { 0x2E778, 0, 0, 0x2E538, 0x1FF, C2P_GATE_BACK },
    { 0x2E780, 0x2E77C, 1200, 0x2E53C, 0x200, C2P_REFRESH },
    { 0x2E788, 0, 0, 0x2E540, 0x201, C2P_GATE_BACK | C2P_HERBS },
    { 0x2E790, 0x2E78C, 400, 0x2E544, 0x202, C2P_REFRESH },
    { 0x2E798, 0x2E794, 425, 0x2E548, 0x203, C2P_REFRESH | C2P_DAM },
    { 0x2E7A0, 0x2E79C, 1, 0x2E54C, 0x204, C2P_REFRESH },
    { 0x2E7A8, 0, 0, 0x2E550, 0x205, 0 },
    { 0x2E7B0, 0x2E7AC, 1000, 0x2E554, 0x206, 0 },
    { 0x2E7B8, 0x2E7B4, 5000, 0x2E558, 0x207, C2P_REFRESH | C2P_MOSAIC },
    { 0x2E7C0, 0x2E7BC, 1, 0x2E55C, 0x208, C2P_REFRESH | C2P_GONG | C2P_CRATE },
    { 0x2E7C8, 0x2E7C4, 1, 0x2E560, 0x209, C2P_REFRESH | C2P_GONG },
    { 0x2E7D8, 0x2E7D4, 2, 0x2E568, 0x20B, C2P_REFRESH | C2P_GONG },
    { 0x2E7E0, 0x2E7DC, 3000, 0x2E56C, 0x20A, C2P_REFRESH | C2P_GONG },
    { 0x2E7E8, 0x2E7E4, 10, 0x2E570, 0x20D, 0 },
};

#define C2_PUZZLE_COUNT ((int)(sizeof C2_PUZZLES / sizeof C2_PUZZLES[0]))

/* Hours since the village began, as the completions write them: (the clock
   0x403200 - [world+0x2E4F8]) / 3600, at least 1 (0x462B44..0x462B73). */
static int c2_hours(void) {
    unsigned char *world = VV2_WORLD();
    unsigned int now = (unsigned int)TC0(0x403200u, world);
    unsigned int hours = (now - *(unsigned int *)(world + 0x2E4F8)) / 3600u;
    return hours == 0 ? 1 : (int)hours;
}

static int c2_puzzle_solved(int which) {
    unsigned char *world = VV2_WORLD();
    if (world == NULL || which < 0 || which >= C2_PUZZLE_COUNT) {
        return 0;
    }
    return world[C2_PUZZLES[which].flag] != 0;
}

static int c2_puzzle_set(int which, int solved) {
    unsigned char *world = VV2_WORLD();
    unsigned char *pool = VV2_POOL();
    const c2_puzzle *p;
    int k;
    if (world == NULL || pool == NULL || which < 0 || which >= C2_PUZZLE_COUNT) {
        return 0;
    }
    p = &C2_PUZZLES[which];
    if (solved) {
        if (p->progress != 0) {
            *(int *)(world + p->progress) = p->solved_progress;
        }
        if (p->how & C2P_HERBS) {
            for (k = 0; k < 6; ++k) {
                world[0x2E860 + 8 * k] = 1;
            }
        }
        if (p->how & C2P_CRATE) {
            world[0x2E7D0] = 1;
        }
        if (p->how & C2P_DAM) {
            *(int *)(world + 0x2EAD8) = 0;
        }
        world[p->flag] = 1;
        *(int *)(world + p->hours) = c2_hours();
        world[p->gate] = 0;
    } else {
        if ((p->how & C2P_MOSAIC) && world[0x2E7D8] != 0) {
            return 0;
        }
        world[p->flag] = 0;
        if (p->progress != 0) {
            *(int *)(world + p->progress) = 0;
        }
        if (p->how & C2P_HERBS) {
            for (k = 0; k < 6; ++k) {
                world[0x2E860 + 8 * k] = 0;
            }
        }
        *(int *)(world + p->hours) = 0;
        if (p->how & C2P_GATE_BACK) {
            world[p->gate] = 1;
        }
    }
    if (p->how & C2P_GONG) {
        int whole = world[0x2E7C0] && world[0x2E7C8] && world[0x2E7D8] && world[0x2E7E0];
        if (whole && world[0x2E7F0] == 0) {
            *(int *)(world + 0x2EAC8) = 1;
        }
        world[0x2E7F0] = (unsigned char)(whole ? 1 : 0);
    }
    if (p->how & C2P_REFRESH) {
        void *scene = *(void **)(pool + 0xE574D8);
        void *map = *(void **)(pool + 0xE574E8);
        if (scene != NULL) {
            TC0(0x418660u, scene);
        }
        if (map != NULL) {
            TC0(0x41C1D0u, map);
        }
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
        | CAP_BEHAVIOUR | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY | CAP_VALUES | CAP_PUZZLES
        | CAP_CANCEL | CAP_RELITTER | CAP_UNBORN | CAP_REVIVE,
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
    C2_BEHAVIOURS, (int)(sizeof C2_BEHAVIOURS / sizeof C2_BEHAVIOURS[0]),
    NULL, 0,
    "Not in The Lost Children:\r\n\r\n"
    "- The Stew as unsolved: the game could then never solve it again, or would count a "
    "known recipe as a new one.\r\n"
    "- The Gong of Wonder on its own: it is whole exactly when its four pieces are.\r\n"
    "- The three population huts as puzzles: they belong to the builders.\r\n"
    "- The unborn baby's starting skill: what the baby does with it at birth was not "
    "traced to the end, so only the father's name and looks are offered.\r\n"
    "- Golden Child, chief, faction: The Lost Children has none.\r\n"
    "- An Esteemed Elder's totem type can only be changed once the villager is an "
    "Esteemed Elder (the game makes the totem then).\r\n"
    "- Actions that solve or advance a puzzle, burying, picking things up, new clothes, "
    "embracing, and lessons or games that stop other villagers.\r\n"
    "- Revive: totems, buried villagers (their record is gone) and skeletons that have "
    "already crumbled away.",
    46, 20, 46, 0, 360,
    "Refills the coconut trees, the fish (to the village's starting stock), the field's "
    "protection from birds and, while the farm is planted, the crops.",
    "Your villagers gain %d food.", "Your villagers lose %d food.",
    "Your villagers gain %d tech points.", "Your villagers lose %d tech points.",
    c2_record, c2_listed, c2_arm_refusal, c2_room, c2_spawn, c2_kill, c2_vanish, c2_sicken,
    c2_conceive, c2_set_status, c2_behave, NULL, c2_food, c2_tech, c2_change_food,
    c2_change_tech, c2_refill, c2_parents_supported, c2_set_parents,
    C2_VALUES, 4, c2_value_get, c2_value_set,
    C2_PUZZLE_DEFS, C2_PUZZLE_COUNT, c2_puzzle_solved, c2_puzzle_set,
    c2_cancel, c2_relitter, c2_unborn,
    c2_skeleton, c2_revive,
    0, 0x540
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
