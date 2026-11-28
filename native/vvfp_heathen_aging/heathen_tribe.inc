/* heathen_tribe.inc -- part of vvfp_heathen_aging.c (included once, after the births' helpers): "Heathen Tribe
   Expansion and Evolution"'s visible embraces, visible nursing, the tribe's size and its masks (the owner,
   2026-11-27/28).  Only with the row's flag (g_evo).

   THE STOCK GAME (read from the stock executable with capstone).
     The believers' embrace.  The job dispatcher's embrace case (0x46CC93) asks the partner search 0x470A10 (a
     living believer, +0x1CEC 0, not sick, not expecting, of the other sex, 18 or older -- 0x470A53 -- and the
     partner under 50, 0x470A8F); the partner is stopped and given behaviour 6 ("Waiting for someone", 0x45CFD0:
     gesture 0x3C of animation 0), the seeker walks to the partner's spot +10 down (0x4745A0, distance 300) and is
     given behaviour 5 (0x45D010: "Embracing", string 0x193; the embrace step 0x474CE0, type 0x10; gesture 1).  The
     embrace step's case of the step runner (0x473853) calls 0x4689A0: whoever stands at the seeker's spot
     (0x4705D0), the checks of 0x468A00 (both healthy, not sick, 18 or older, not expecting, of two sexes; the Love
     Shack, project 23, built, else "The love shack has not been completed!"), the seeker's Parenting skill check
     0x46B270, and then both are given behaviour 7 (0x458060: walk area 0x19 into the Love Shack, step 0x0F, a stay
     of rand(100) % 3 + 5, step 0x11) and the believers' conception gate: rand(300) + 50 - 50 x Medicine <= the
     seeker's Parenting (the first baby's tip skips it), neither a woman 50 or older, then 0x467D20 -> the conception
     0x465E00 with the woman as the carrier.  The load-time catch-up does the same at once (0x46E078..0x46E19B).
     0x467D20's baby skill: the woman's best skill (0x4755C0), on 1 in 50 the man's; its value rand(3) + 5, or + 4
     when both bests are the same.
     The conception 0x465E00 (forced: its seventh argument 1 skips the room check 0x472BD0 and the statistics' births
     0x51D360) sets the litter by MEDICINE (0x465EC6..0x465F2D): one; at Medicine 3, rand(100) < 7 a multiple birth,
     of which rand(100) < 25 triplets (0x51D384 counted), else twins (0x51D380 counted).  It adds Parenting to the
     carrier (0x475730).  The birth comes 40 units later (0x4730AF: conception + 0x28 < processed age), the child
     made at age 40 (two years: "A mother cares for her child until age two"); until then the carrier NURSES: at
     every queue's end a carrier holds the baby (0x473563: carry 3; a believer through 0x466470), and the believers'
     action picker (0x46F0FD) gives a carrier the mothers' routine 0x46A1D0 -- in the rain behaviour 0x2B or 0x4A
     (by the rain preference 0x42), else on 80% of the picks one of 0x43 ("Taking care of her baby"), 0x42, 0x7E
     (once game +0x17D58 is over 15), 0x76, 0x77, 0xD4, 0xD5 (washing, changing, showing baby the beach, the herbs,
     the statue, the stream ...).  Those scripts hold only the game's look steps (walks, gestures, animations, the
     types 3, 9, 0x0B, 0x0F, 0x11, 0x18, 0x1C, 0x23-0x25, 0x28, 0x2C -- never the work step 0x14, the skill check 0x0A
     or the job types 0x12, 0x13, 0x1F-0x22 the catch-up's 0x473B30 does): nothing of the believers is touched.  The
     Heathen AI 0x46E9E0 gives a Heathen carrier only the carry (0x46EAB8..0x46EAC8) and its camp role.
     Medicine's other nursing effect is none: the 40 units are fixed (0x4730BA).

   WHAT THIS DOES.
     EMBRACES (in place of the old invisible roll).  On the village's clock, one roll a unit (the rates in
     heathen_evo.h section 2): about one conception for the whole tribe every 60 units (6 real hours on Normal) at
     1x births, the "Heathen tribe size" rates when it is on.  A roll that comes up picks, at random, one pair who
     may have a baby: a Heathen couple of a woman and a man, or a Heathen whose title says Parent (the Details
     panel's rule: the highest skill by 0x4755C0, or the job's +0x1C74, is Parenting at 20 or more; the owner: "heathens
     whose skill says Parent can embrace eligible heathen candidates too") with any Heathen of the other sex who is
     not their kin; the woman 14 to 45 and not expecting, the man an adult; both living aging Heathens, not sick, not
     held, not already embracing, not the Heathen Mommy, and a puzzle Heathen only once that puzzle is solved (until
     then they keep their stock life).  The partner is given the believers' behaviour 6 ("Waiting for someone"),
     the seeker the believers' embrace look without its embrace step (stopped, "Embracing", the walk to the partner's
     spot +10 down at distance 300, gesture 1 of animation 0): the step 0x10 would run 0x468A00's believer checks,
     messages and the statistics' births.  At each look after (every 250 ms), when the two stand within
     EMBRACE_NEAR pixels: the conception, then both the believers' behaviour 7 into the Love Shack once it is built
     (project 23), else an embrace look where they stand (stopped, "Embracing", gesture 1, a wait, gesture 1).  An
     embrace that has not met in EMBRACE_UNITS units, or whose pair is no longer free, is given up.  A look that
     brings more than CATCH_UP_UNITS units (the load-time catch-up) conceives at once, as the game's catch-up does.
     The CONCEPTION is the game's own 0x465E00, forced, with 0x467D20's baby skill and value, the woman the carrier:
     the litter is the believers' own Medicine rule (single below Medicine 3; 5.25% twins and 1.75% triplets at
     Medicine 3), as many as the room and the tribe size let in; the statistics' twins and triplets put back; the
     mother kept as expecting; its Conception record written (WriteParentageRecordWithFather) -- births are never
     logged as conceptions are, only by the Birth record at the birth (deliver).  The believers' Parenting gate is
     not applied: the owner's rate is the rate.  A same-sex couple has babies only through island events.
     NURSING.  A Heathen carrier of a baby this companion conceived (never a puzzle Heathen: the Heathen Mommy keeps
     her stock infant) is given the believers' mothers' routine 0x46A1D0 by the Heathen AI (the splice at 0x46EAB8),
     holding the baby as the stock Heathen carry does, until the birth 40 units after the conception, as believers.
     THE TRIBE'S SIZE (heathen_evo.h: tribe_max, room_kept, change_tenths).  Conceptions and arrivals add only while
     the camp (living Heathens and babies on the way) is under tribe_max and room_kept records stay free; growth
     slows over the last fifth and pauses at the limit; nobody is removed.  CHILDREN: while the camp holds fewer
     children (under 14, babies on the way counted) than a tenth of its size (tribe_max, or the camp itself; at
     least 2), with the tribe size on the conception roll counts double and an arrival is a family with children.
     MASKS: the caps (vvfp_heathen_aging.c mask_free); every orange or red Heathen child is labelled "Rascal" (the
     panel's child title, the splice at 0x4430C6: the stock tests only the orange byte); PURPLE MASTERS: a Heathen of
     the camp's own roles (0-11, no role for show) whose skill reaches 100 takes that skill's purple mask, the first
     to master it, one a skill, through the Origins mask store (store_mask: only with "VVFP Origins Icons.dll" and
     "VVFP Heathens Keep Masks.dll" in the game); when they die, convert or leave, the next master of the skill may.
     Titles are the game's: a Heathen master of the camp shows "Master <skill>" by the panel's rank (with Esteemed
     Elders' row a Heathen is never an Esteemed Elder), the puzzle Heathens their own titles.

   The tribe file: Data\Heathen Tribe\Heathen Tribe - Save <S>.dat (heathen_evo.h section 5), written through
   sidecar_io.h; the Rascal caps drawn once from this companion's own numbers. */

#ifndef R_SICK
#define R_SICK 0x1C48u
#endif
#define R_HELD 0x1CD6u
#define R_BEHAVIOUR 0x1D10u
#define R_DOING 0x1D14u
#define R_DOING_CAP 0x27u
#define R_JOB_SKILL 0x1C74u             /* the ticked job's skill, -1 none (the panel 0x442E96) */

#define G_BEHAVIOUR 0x465580u           /* thiscall on the record: (behaviour, char *); ret 8 */
#define G_POSITION 0x466350u            /* thiscall on the record: (int out[2]) -> out; ret 4 */
#define G_TEXTS 0x450D40u               /* cdecl: the string table */
#define G_TEXT 0x4506D0u                /* thiscall on it: (id) -> char *; ret 4 */
#define G_WALK_POINT 0x4745A0u          /* (x, y, distance, 0); ret 0x10 */
#define G_GESTURE 0x474450u             /* (count, animation); ret 8 */
#define G_WAIT 0x4747E0u                /* (seconds); ret 4 */
#define G_START 0x473590u               /* start the queue */
#define G_MOTHERS 0x46A1D0u             /* thiscall on the AI object: al, a mothers' behaviour given */
#define B_WAITING 6                     /* 0x45CFD0 */
#define B_LOVE_SHACK 7                  /* 0x458060 */
#define T_EMBRACING 0x193
#define P_LOVE_SHACK 23
#define CAMP_WANDER 0x9C                /* the Heathens' own behaviour id (0x46F00C), as Heathen Life's looks */
#define CARRY_BABY 3
#define SKILL_PARENTING 1
#define PARENT_TITLE_FROM 20            /* the panel's skill title from 20 (0x442F01) */

#define EMBRACE_MAX 4                   /* embraces under way at once */
#define EMBRACE_NEAR 40                 /* pixels: met */
#define EMBRACE_UNITS 3                 /* given up after this many units of the village's clock */
#define CATCH_UP_UNITS 20               /* more units in one look: the load-time catch-up, conceived at once */

typedef int (__fastcall *tc3_fn)(void *self, void *unused_edx, int a, int b, int c);
typedef int (__fastcall *tc4_fn)(void *self, void *unused_edx, int a, int b, int c, int d);
typedef int *(__fastcall *position_fn)(void *self, void *unused_edx, int *out);
typedef void *(__cdecl *texts_fn)(void);
typedef const char *(__fastcall *text_fn)(void *self, void *unused_edx, int id);

/* ---- the tribe file ----------------------------------------------------------------------------------------- */

static unsigned int g_tribe_words[HE_TRIBE_WORDS];   /* 0 the orange Rascals' cap, 1 the red, 2..7 the masters */
static int g_tribe_slot;
static int g_tribe_blocked;
static int g_tribe_dirty;
static vv_sidecar_gate g_tribe_gate;
static DWORD g_tribe_synced_at;
static unsigned int g_tribe_buffer[HE_TRIBE_HEADER / 4u + HE_TRIBE_WORDS + 1u];

static int tribe_path(int slot, char *out, int make) {
    return data_path(slot, out, make, HE_TRIBE_FOLDER, HE_TRIBE_FILE);
}

static int valid_tribe(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    if (len != HE_TRIBE_HEADER + HE_TRIBE_WORDS * 4u || u[0] != HE_TRIBE_MAGIC || u[1] != HE_TRIBE_VERSION
        || u[2] != HA_GAME || u[3] != HE_TRIBE_WORDS || u[4] != (unsigned int)*(const int *)ctx) {
        return 0;
    }
    return u[5] >= HE_RASCAL_CAP_MIN && u[5] <= HE_RASCAL_CAP_MAX && u[6] >= HE_RASCAL_CAP_MIN
        && u[6] <= HE_RASCAL_CAP_MAX;
}

static void tribe_caps_follow(void) {
    g_rascal_cap[0] = (int)g_tribe_words[0];
    g_rascal_cap[1] = (int)g_tribe_words[1];
}

static void read_tribe(int slot) {
    char path[MAX_PATH];
    DWORD got = 0;
    int status;
    vv_sidecar_gate_bind(&g_tribe_gate, slot);
    g_tribe_blocked = 0;
    memset(g_tribe_words, 0, sizeof g_tribe_words);
    if (!tribe_path(slot, path, 0)) {
        vv_sidecar_gate_block(&g_tribe_gate);
        g_tribe_blocked = 1;
        return;
    }
    status = vv_sidecar_load(&g_tribe_gate, path, (unsigned char *)g_tribe_buffer, sizeof g_tribe_buffer, &got,
                             valid_tribe, &slot);
    g_tribe_blocked = status == VV_SIDECAR_LOAD_BLOCKED;
    if (status == VV_SIDECAR_LOAD_VALID) {
        memcpy(g_tribe_words, g_tribe_buffer + 5, sizeof g_tribe_words);
    } else if (!g_tribe_blocked) {
        /* A village seen for the first time (or its file set aside): its Rascal caps, fixed from now on. */
        g_tribe_words[0] = (unsigned int)(HE_RASCAL_CAP_MIN + he_below(HE_RASCAL_CAP_MAX - HE_RASCAL_CAP_MIN + 1));
        g_tribe_words[1] = (unsigned int)(HE_RASCAL_CAP_MIN + he_below(HE_RASCAL_CAP_MAX - HE_RASCAL_CAP_MIN + 1));
        g_tribe_dirty = 1;
    }
    if (!g_tribe_blocked) {
        tribe_caps_follow();
    }
    g_tribe_synced_at = GetTickCount() - HA_WRITE_MS;
}

static void write_tribe(int slot, int now) {
    unsigned int header[5];
    const void *parts[2];
    DWORD sizes[2];
    char path[MAX_PATH];
    if (!g_tribe_dirty || slot == 0 || slot != g_tribe_slot || g_tribe_blocked
        || !vv_sidecar_gate_ready(&g_tribe_gate, slot) || (!now && GetTickCount() - g_tribe_synced_at < HA_WRITE_MS)
        || !tribe_path(slot, path, 1)) {
        return;
    }
    g_tribe_synced_at = GetTickCount();
    header[0] = HE_TRIBE_MAGIC;
    header[1] = HE_TRIBE_VERSION;
    header[2] = HA_GAME;
    header[3] = HE_TRIBE_WORDS;
    header[4] = (unsigned int)slot;
    parts[0] = header;
    sizes[0] = sizeof header;
    parts[1] = g_tribe_words;
    sizes[1] = sizeof g_tribe_words;
    if (vv_sidecar_publish(&g_tribe_gate, path, parts, sizes, 2)) {
        g_tribe_dirty = 0;
    }
}

/* The slot's tribe file read when the village's slot is first seen (a lock retried on the gate's throttle); changes
   written at most once a second. */
static void keep_tribe(void) {
    if (g_file_slot == 0) {
        return;
    }
    if (g_tribe_slot != g_file_slot) {
        g_tribe_slot = g_file_slot;
        g_tribe_dirty = 0;
        read_tribe(g_tribe_slot);
    } else if (g_tribe_blocked && !vv_sidecar_gate_throttled(&g_tribe_gate)) {
        read_tribe(g_tribe_slot);
    }
    write_tribe(g_tribe_slot, 0);
}

/* The last village's tribe file written now (a Change Tribe, before its pieces are forgotten). */
static void flush_tribe(void) {
    write_tribe(g_tribe_slot, 1);
}

/* A master's identity follows the villager (follow_identities' rekey). */
static void tribe_rekey(unsigned int from, unsigned int to) {
    unsigned int k;
    for (k = 2; k < HE_TRIBE_WORDS; ++k) {
        if (g_tribe_words[k] == from && from != 0u) {
            g_tribe_words[k] = to;
            g_tribe_dirty = 1;
        }
    }
}

/* ---- the game's look steps (the believers' scripts' own adders) ------------------------------------------------ */

static void say(unsigned char *record, int text) {
    void *table = ((texts_fn)(UINT_PTR)G_TEXTS)();
    const char *words = ((text_fn)(UINT_PTR)G_TEXT)(table, NULL, text);
    unsigned int i = 0;
    if (words != NULL) {
        for (; i + 1u < R_DOING_CAP && words[i] != '\0'; ++i) {
            record[R_DOING + i] = (unsigned char)words[i];
        }
    }
    record[R_DOING + i] = 0;
}

static void give_behaviour(unsigned char *record, int behaviour) {
    char flag = 0;                                  /* the stock callers' local byte, 0 */
    ((tc0_fn)(UINT_PTR)G_STOP)(record, NULL);
    ((tc2_fn)(UINT_PTR)G_BEHAVIOUR)(record, NULL, behaviour, (int)(UINT_PTR)&flag);
}

static void spot_of(const unsigned char *record, int *x, int *y) {
    int at[2] = { 0, 0 };
    int *p = ((position_fn)(UINT_PTR)G_POSITION)((void *)record, NULL, at);
    *x = p[0];
    *y = p[1];
}

/* 0x45D010's look, without its embrace step: walk to the partner's spot, gesture. */
static void look_embrace_walk(unsigned char *seeker, const unsigned char *partner) {
    int x, y;
    spot_of(partner, &x, &y);
    ((tc0_fn)(UINT_PTR)G_STOP)(seeker, NULL);
    *(int *)(seeker + R_BEHAVIOUR) = CAMP_WANDER;
    say(seeker, T_EMBRACING);
    ((tc4_fn)(UINT_PTR)G_WALK_POINT)(seeker, NULL, x, y + 10, 300, 0);
    ((tc2_fn)(UINT_PTR)G_GESTURE)(seeker, NULL, 1, 0);
    ((tc0_fn)(UINT_PTR)G_START)(seeker, NULL);
}

/* No Love Shack yet: the embrace where they stand. */
static void look_embrace_here(unsigned char *record) {
    ((tc0_fn)(UINT_PTR)G_STOP)(record, NULL);
    *(int *)(record + R_BEHAVIOUR) = CAMP_WANDER;
    say(record, T_EMBRACING);
    ((tc2_fn)(UINT_PTR)G_GESTURE)(record, NULL, 1, 0);
    ((tc1_fn)(UINT_PTR)G_WAIT)(record, NULL, 3);
    ((tc2_fn)(UINT_PTR)G_GESTURE)(record, NULL, 1, 0);
    ((tc0_fn)(UINT_PTR)G_START)(record, NULL);
}

/* ---- who may embrace ---------------------------------------------------------------------------------------- */

typedef struct {
    int seeker, partner;
    unsigned int seeker_who, partner_who;
    unsigned int units;
} he_embrace;
static he_embrace g_embrace[EMBRACE_MAX];
static int g_embrace_count;

static int embracing(int index) {
    int k;
    for (k = 0; k < g_embrace_count; ++k) {
        if (g_embrace[k].seeker == index || g_embrace[k].partner == index) {
            return 1;
        }
    }
    return 0;
}

/* A living aging adult Heathen free to embrace now. */
static int free_to_embrace(const unsigned char *r) {
    int role = i32(r, R_ROLE), puzzle = puzzle_of_role(role);
    return r[R_FACTION] != 0 && living(r) && ages(r) && i32(r, R_AGE) >= ADULT && role != 17
        && (puzzle == 0 || puzzle_done(puzzle)) && r[R_SICK] == 0 && r[R_HELD] == 0 && i32(r, R_PREGNANT) == 0
        && !embracing(rec_index(r));
}

/* The panel's skill title (0x442E8B..0x442F01): the ticked job's skill, else the highest by 0x4755C0 (a skill
   wins when above the best so far cut to a whole number); a title only from 20. */
static int titled_parent(const unsigned char *r) {
    const float *skills = (const float *)(r + R_SKILLS);
    int best = -1, whole = 0, k, job = i32(r, R_JOB_SKILL);
    for (k = 0; k < 6; ++k) {
        if (skills[k] > (float)whole) {
            whole = (int)skills[k];
            best = k;
        }
    }
    if (job >= 0 && job < 6) {
        best = job;
        whole = (int)skills[job];
    }
    return best == SKILL_PARENTING && whole >= PARENT_TITLE_FROM;
}

/* 1 when the two may have a baby now: a woman who could conceive and a man (either order), not kin. */
static int baby_pair(const unsigned char *a, const unsigned char *b) {
    const unsigned char *woman = i32(a, R_SEX) == 1 ? a : b, *man = woman == a ? b : a;
    return i32(woman, R_SEX) == 1 && i32(man, R_SEX) != 1 && could_conceive(woman) && !kin(a, b);
}

#define PAIRS_MAX 512

/* One pair who may embrace, at random: a couple of a woman and a man, or a Heathen titled Parent with any free
   Heathen of the other sex who is not their kin.  0 none. */
static int pick_pair(int *seeker, int *partner) {
    static int first[PAIRS_MAX], second[PAIRS_MAX];
    unsigned int i, j;
    int n = 0, k;
    for (i = 0; i < g_slots && i < 256u; ++i) {
        unsigned char *r = rec_at((int)i), *m;
        if (!free_to_embrace(r)) {
            continue;
        }
        if (i32(r, R_SEX) == 1 && (m = partner_man(r)) != NULL && free_to_embrace(m) && baby_pair(r, m)
            && n < PAIRS_MAX) {
            int her_first = he_below(2) != 0;                    /* either of the couple seeks the other */
            first[n] = her_first ? (int)i : rec_index(m);
            second[n] = her_first ? rec_index(m) : (int)i;
            ++n;
        }
        if (!titled_parent(r)) {
            continue;
        }
        for (j = 0; j < g_slots && j < 256u && n < PAIRS_MAX; ++j) {
            const unsigned char *c = rec_at((int)j);
            if (j != i && free_to_embrace(c) && i32(c, R_SEX) != i32(r, R_SEX) && baby_pair(r, c)
                && partner_of(r) != c) {
                first[n] = (int)i;
                second[n++] = (int)j;
            }
        }
    }
    if (n == 0) {
        return 0;
    }
    k = he_below((unsigned int)n);
    *seeker = first[k];
    *partner = second[k];
    return 1;
}

/* ---- the conception ----------------------------------------------------------------------------------------- */

static int best_skill(const unsigned char *r) {          /* 0x4755C0 */
    const float *skills = (const float *)(r + R_SKILLS);
    int best = -1, whole = 0, k;
    for (k = 0; k < 6; ++k) {
        if (skills[k] > (float)whole) {
            whole = (int)skills[k];
            best = k;
        }
    }
    return best;
}

/* The woman conceives by the man: the game's own conception, forced, with 0x467D20's baby skill and value; the
   litter its Medicine rule, as many as fit; the statistics' counters put back; the Conception record.  1 done. */
static int conceive(unsigned char *woman, unsigned char *man) {
    int twins, triplets, babies, wb, mb, skill, value, fit = tribe_fit(3);
    if (!could_conceive(woman) || fit < 1) {
        return 0;
    }
    wb = best_skill(woman);
    mb = best_skill(man);
    skill = he_below(50) == 0 ? mb : wb;
    value = he_below(3) + (wb == mb && mb != -1 ? 4 : 5);
    twins = *(volatile int *)(UINT_PTR)G_TWINS;
    triplets = *(volatile int *)(UINT_PTR)G_TRIPLETS;
    ((tc7_fn)(UINT_PTR)G_CONCEIVE)(woman, NULL, i32(man, R_LINEAGE), skill, value, (int)(UINT_PTR)(man + R_NAME),
                                   i32(man, R_HEAD), i32(man, R_BODY), 1);
    *(volatile int *)(UINT_PTR)G_TWINS = twins;
    *(volatile int *)(UINT_PTR)G_TRIPLETS = triplets;
    if (i32(woman, R_PREGNANT) == 0) {
        *(int *)(woman + R_PREGNANT) = i32(woman, R_PROCESSED) > 0 ? i32(woman, R_PROCESSED) : 1;
    }
    babies = i32(woman, R_LITTER);
    babies = babies < 1 ? 1 : babies > 3 ? 3 : babies;
    *(int *)(woman + R_LITTER) = babies < fit ? babies : fit;   /* as many as the room and the tribe size let in */
    known_put(identity(woman), KIND_EXPECTING);
    log_conception(woman, man);
    return 1;
}

static void conceive_pair(int a, int b) {
    unsigned char *x = rec_at(a), *y = rec_at(b);
    if (i32(x, R_SEX) == 1) {
        (void)conceive(x, y);
    } else {
        (void)conceive(y, x);
    }
}

/* ---- the embraces under way --------------------------------------------------------------------------------- */

static void embrace_drop(int k) {
    memmove(&g_embrace[k], &g_embrace[k + 1], sizeof g_embrace[0] * (size_t)(g_embrace_count - k - 1));
    --g_embrace_count;
}

/* A roll came up: one pair embraces (live: the walk, then the conception when they meet; in the catch-up at once). */
static void embrace_one(int at_once) {
    int a, b;
    if (g_embrace_count >= EMBRACE_MAX || !pick_pair(&a, &b)) {
        return;
    }
    if (at_once) {
        conceive_pair(a, b);
        return;
    }
    give_behaviour(rec_at(b), B_WAITING);
    look_embrace_walk(rec_at(a), rec_at(b));
    g_embrace[g_embrace_count].seeker = a;
    g_embrace[g_embrace_count].partner = b;
    g_embrace[g_embrace_count].seeker_who = identity(rec_at(a));
    g_embrace[g_embrace_count].partner_who = identity(rec_at(b));
    g_embrace[g_embrace_count].units = 0;
    ++g_embrace_count;
}

/* One embrace's pair still free for it (the same two, living, not sick, held or expecting, a baby pair). */
static int embrace_holds(const he_embrace *e) {
    const unsigned char *a = rec_at(e->seeker), *b = rec_at(e->partner);
    return identity(a) == e->seeker_who && identity(b) == e->partner_who && a[R_FACTION] != 0 && b[R_FACTION] != 0
        && living(a) && living(b) && a[R_SICK] == 0 && b[R_SICK] == 0 && a[R_HELD] == 0 && b[R_HELD] == 0
        && i32(a, R_PREGNANT) == 0 && i32(b, R_PREGNANT) == 0 && baby_pair(a, b);
}

static void embraces_follow(void) {
    int k;
    for (k = g_embrace_count; k-- > 0;) {
        he_embrace *e = &g_embrace[k];
        int ax, ay, bx, by;
        if (!embrace_holds(e)) {
            embrace_drop(k);
            continue;
        }
        spot_of(rec_at(e->seeker), &ax, &ay);
        spot_of(rec_at(e->partner), &bx, &by);
        if ((ax - bx) * (ax - bx) + (ay - by) * (ay - by) <= EMBRACE_NEAR * EMBRACE_NEAR) {
            unsigned char *a = rec_at(e->seeker), *b = rec_at(e->partner);
            embrace_drop(k);
            conceive_pair(rec_index(a), rec_index(b));
            if (puzzle_done(P_LOVE_SHACK)) {
                give_behaviour(a, B_LOVE_SHACK);        /* 0x468B50..0x468B76: both into the Love Shack */
                give_behaviour(b, B_LOVE_SHACK);
            } else {
                look_embrace_here(a);
                look_embrace_here(b);
            }
            continue;
        }
        e->units += g_clock_units;
        if (e->units > EMBRACE_UNITS) {
            embrace_drop(k);                            /* never met: given up */
        }
    }
}

/* ---- the growth rolls (heathen_evo.h section 2) -------------------------------------------------------------- */

/* F, 0..100: full speed until the last fifth of tribe_max (at least 3 below it), then down to 0 at the limit. */
static unsigned int growth_factor(void) {
    int left, band;
    if (g_tribe_max <= 0) {
        return 100u;
    }
    left = g_tribe_max - tribe_count();
    band = g_tribe_max / HE_SLOWING_SHARE;
    band = band < 3 ? 3 : band;
    if (left <= 0) {
        return 0u;
    }
    return left >= band ? 100u : (unsigned int)(100 * left / band);
}

/* Fewer children (under 14, babies on the way counted) than a tenth of the camp's size (tribe_max, or the camp
   itself), at least 2: the next additions favour babies and families. */
static int children_short(void) {
    unsigned int i;
    int children = 0, size = g_tribe_max > 0 ? g_tribe_max : tribe_count(), wanted;
    for (i = 0; i < g_slots; ++i) {
        const unsigned char *r = rec_at((int)i);
        if (r[R_FACTION] != 0 && living(r)) {
            children += i32(r, R_AGE) < ADULT;
            children += i32(r, R_PREGNANT) != 0 ? (i32(r, R_LITTER) > 0 ? i32(r, R_LITTER) : 1) : 0;
        }
    }
    wanted = size / 10;
    wanted = wanted < 2 ? 2 : wanted;
    return children < wanted;
}

/* Each unit the village's clock record was credited since the last look: one conception roll and one arrival roll.
   Tribe size off: 1 in HE_CONCEIVE_UNITS x 10 / b, and 1 in HE_ARRIVAL_ROLL / a.  On: b x c x F (x 2 short of
   children) in HE_CONCEIVE_UNITS x 100,000, and a x c x F in HE_ARRIVE_UNITS_SIZED x 10,000 (an arrival a family
   while short of children). */
static void growth(void) {
    unsigned int units = g_clock_units, u, f = 100u;
    int short_of = 0, at_once = units > CATCH_UP_UNITS, sized = g_tribe_max > 0;
    g_clock_units = 0;
    if (units > 100000u) {
        units = 100000u;
    }
    if (units > 0 && sized) {
        f = growth_factor();
        short_of = children_short();
    }
    for (u = 0; u < units; ++u) {
        int hit, conceived;
        if (sized) {
            hit = (unsigned int)he_below(HE_ARRIVE_UNITS_SIZED * 10000u) < g_arrivals_tenths * g_change_tenths * f;
        } else {
            hit = (unsigned int)he_below(HE_ARRIVAL_ROLL) < g_arrivals_tenths;
        }
        if (hit && arrival_open()) {
            arrive(sized && short_of);
        }
        if (sized) {
            conceived = (unsigned int)he_below(HE_CONCEIVE_UNITS * 100000u)
                < g_births_tenths * g_change_tenths * f * (short_of ? 2u : 1u);
        } else {
            conceived = (unsigned int)he_below(HE_CONCEIVE_UNITS * 10u) < g_births_tenths;
        }
        if (conceived) {
            embrace_one(at_once);
        }
        if (sized && (hit || conceived)) {
            f = growth_factor();
            short_of = children_short();
        }
    }
}

/* ---- the purple masters (the owner, 2026-11-28) -------------------------------------------------------------- */

static unsigned char *living_heathen_of(unsigned int who) {
    unsigned int i;
    if (who == 0u) {
        return NULL;
    }
    for (i = 0; i < g_slots; ++i) {
        unsigned char *r = rec_at((int)i);
        if (r[R_FACTION] != 0 && living(r) && identity(r) == who) {
            return r;
        }
    }
    return NULL;
}

static int purple_already(unsigned int who) {
    unsigned int k;
    for (k = 2; k < HE_TRIBE_WORDS; ++k) {
        if (g_tribe_words[k] == who) {
            return 1;
        }
    }
    return 0;
}

static void purple_masters(void) {
    unsigned int k, i;
    if (g_tribe_slot == 0 || g_tribe_blocked) {
        return;
    }
    for (k = 0; k < 6; ++k) {
        unsigned int *word = &g_tribe_words[2 + k];
        if (*word != 0u && living_heathen_of(*word) == NULL) {
            *word = 0u;                                 /* died, converted or left: the next master may */
            g_tribe_dirty = 1;
        }
        if (*word != 0u) {
            continue;
        }
        for (i = 0; i < g_slots; ++i) {
            unsigned char *r = rec_at((int)i);
            int role = i32(r, R_ROLE);
            if (r[R_FACTION] == 0 || !living(r) || role < 0 || role > 11 || held_role(r) != 0
                || i32(r, R_AGE) < ADULT || ((const float *)(r + R_SKILLS))[k] < 100.0f
                || purple_already(identity(r))) {
                continue;
            }
            if (store_mask(r, MASK_STORE_PURPLE)) {
                r[R_ORANGE] = 0;
                r[R_RED] = 0;
                *word = identity(r);
                g_tribe_dirty = 1;
            }
            break;                                      /* the first master of the skill, or nobody can show it */
        }
    }
}

/* A purple master is gone from the camp (gone()): the store's mask goes with them, so a record reused by a newcomer
   never shows it. */
static void purple_gone(unsigned char *record) {
    unsigned int k, who = identity(record);
    for (k = 2; k < HE_TRIBE_WORDS; ++k) {
        if (who != 0u && g_tribe_words[k] == who) {
            (void)store_mask(record, MASK_STORE_BLUE);
            g_tribe_words[k] = 0u;
            g_tribe_dirty = 1;
        }
    }
}

/* Everything of one village's tribe forgotten (a Change Tribe, Start Over): never written back. */
static void forget_tribe(void) {
    memset(g_tribe_words, 0, sizeof g_tribe_words);
    g_tribe_slot = 0;
    g_tribe_dirty = 0;
    g_tribe_blocked = 0;
    g_embrace_count = 0;
    g_rascal_cap[0] = g_rascal_cap[1] = HE_RASCAL_CAP_MIN;
}

/* ---- nursing: the Heathen AI's carrier branch (0x46EAB8) --------------------------------------------------- */

typedef unsigned char (__fastcall *mothers_fn)(void *self, void *unused_edx);

/* 1 when the believers' mothers' routine gave this Heathen carrier a behaviour (the AI then returns). */
static int __cdecl nurse(unsigned char *ai) {
    int answer = 0;
    __try {
        unsigned char *r = *(unsigned char **)(ai + 0x1B88);
        int role;
        if (!g_evo || rec_index(r) < 0 || r[R_FACTION] == 0 || !living(r) || i32(r, R_PREGNANT) == 0) {
            return 0;
        }
        role = i32(r, R_ROLE);
        if ((role >= 12 && role <= 17) || known_find(identity(r), KIND_EXPECTING) < 0) {
            return 0;                                   /* the puzzle Heathens' stock life; another's pregnancy */
        }
        ((tc1_fn)(UINT_PTR)G_CARRY)(r, NULL, CARRY_BABY);   /* the stock Heathen carry (0x46EAC6) */
        answer = ((mothers_fn)(UINT_PTR)G_MOTHERS)(ai, NULL) != 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = 0;
    }
    return answer;
}
