/* The Aspiring Adventurer: The Secret City, The Tree of Life and New Believers.  Included by
   vvfp_more_island_events.c.

   These three games keep their island events as objects in one table (The Secret City 0x4B3C78, slots 1-57; The
   Tree of Life 0x4CCA28, 1-49; New Believers 0x4DC850, 1-55) and present the one their selector drew (0x419B30,
   0x418000, 0x418870) with one two-choice dialog design (constructors 0x4192F0 / 0x417790 / 0x418020, click
   handlers 0x419A00 / 0x417EA0 / 0x418720; story_objects.inc of the Story / Cheat Upgrades companion describes it).

   THE EVENT is one more such object (a copy of a stock two-choice event's vtable -- 0x47EA40, 0x48CB64, 0x497D34 --
   with its own methods), kept in the table's slot 0: every selector lists slots 1 and up only, slot 0 is never
   written by a table builder (the teardowns 0x418F00 / 0x417760 / ... delete it like any slot: its deleter does
   nothing, the object is this DLL's), so the stock events keep every slot.  The selector's loop end (cmp esi, N /
   jl) jumps here: after the stock slots are listed, slot 0 is listed once for each of our events whose condition
   holds (the Adventurer: at least two villagers who may go, adv_possible; The Secret City's The Troubling Signs and
   Diving for Treasure their own), and the object put in slot 0 is one of theirs, each equally likely (t_list) -- so
   each takes an equal share of the draw, rand(count), like any listed event, with the game's own timing, rescue rule
   and counting.  Each selector's array holds one entry more than its stock slots (the slot count + 1 dwords before
   the dialog on the stack): t_list never adds more entries than that room.  Slot 0 is put
   back at every selection (a teardown clears it).  The picked index 0 is presented by the stock code as any other
   (`mov reg, [esi*4 + table]`), and its "shown" byte (table - slots - 1 + 0, never read) is set as any other's.

   THE POPUP.  The dialog asks the object, as story_objects.inc lists: +0x08 the title (looked up once: here the
   event is composed, adv_begin), +0x1C the villager shown (the adventurer), +0x10 "two choices" (yes), +0x24 the
   pose (5), +0x20 a second villager (none), +0x14 / +0x18 the labels, +0x28(c) at build for c = 0, 1 and +0x0C
   the question (the popup is sized to the tallest of those three, so +0x28 then gives the tallest page of the
   whole event); the click +0x34(c) (the answer) then +0x28(c) (the result's first page), OK +0x2C(c) (nothing).
   The effects wait for their own page (adv_log.inc): they are made when the result's last page is shown -- in the
   answer's click when the result is one page, else in the OK click that brings it -- and the event keeps its own one
   Island Events log entry.  One string id carries every text in turn: each method points it at its text just before
   returning it (the dialog copies the text at once, 0x416F60 -> 0x44D410 into its own 2,000 bytes).  The ids are
   ones nothing shows: The Secret City 0x3A7 / 0x3A9 (The Drought's strings, an event with no object and no code
   naming them), The Tree of Life 0x35F / 0x361 (The Medical Emergency's title and first label: its condition
   0x4146E0 is always false, so its object is never presented, and no other code names them), New Believers 0x3B3
   / 0x3B5 (no string has them, no code names them).  Their index slots are pointed at this DLL's entries while the
   popup is up and given back when it closes.

   PAGES.  Two more sites:
     * the presenter's `call <constructor>` (0x419BEA, 0x418106, 0x41896A): after the stock constructor, when the
       question's own text takes more than one page, the answer buttons (+0x85C, +0x860) are hidden, OK (+0x864)
       shown, and the first page is set (the dialog's own hide 0x40C230 / 0x40C210 / 0x40C700, show 0x40C1F0 /
       0x40C190 / 0x40C680 and text 0x4185A0 / 0x416F60 / 0x417700, as its click handler uses them);
     * the click handler's OK branch (`mov ecx, [esi+0x50]; mov eax, [ecx]`, 0x419A18, 0x417EB8, 0x418738): while
       this event has a page left, OK shows the next page (the last question page with the two buttons back and OK
       hidden) and the dialog stays; on the last page the stock branch runs on (+0x2C, close).
   The village does not run while the dialog is up (each presenter's modal loop runs only the dialog). */

typedef void (__fastcall *adv_tc0)(void *self, void *unused);
typedef void (__fastcall *adv_tc1)(void *self, void *unused, int a);
typedef int (__fastcall *adv_tc0r)(void *self, void *unused);
typedef int (__fastcall *adv_tc1r)(void *self, void *unused, int a);
typedef void (__fastcall *adv_tc2)(void *self, void *unused, int a, int b);
typedef int (__fastcall *adv_tc4r)(void *self, void *unused, int a, int b, int c, int d);
typedef int (__cdecl *adv_rand_fn)(int bound);
#define ADV_TC0(va, self) ((adv_tc0)(uintptr_t)(va))((void *)(self), NULL)
#define ADV_TC1(va, self, a) ((adv_tc1)(uintptr_t)(va))((void *)(self), NULL, (int)(a))
#define ADV_TC2(va, self, a, b) ((adv_tc2)(uintptr_t)(va))((void *)(self), NULL, (int)(a), (int)(b))

typedef struct {
    int id;
    const char *key;
    const char *text;
    const char *localized;
} adv_string;

typedef struct {
    int game;
    unsigned int table;                /* the event table: slot 0 is the event's */
    int slots;                         /* the stock slots, 1..slots */
    unsigned int strings;              /* the string lookup's pointer per id */
    int title_id, body_id;
    unsigned int source_vtable;        /* a stock two-choice event's */
    unsigned int set_text, hide, show; /* thiscall on the dialog */
    unsigned int rand;
    /* The sites. */
    unsigned int loop_site, loop_top, loop_after;
    unsigned char loop_stock[5];
    int list_offset;                   /* the selector's list: [esp + offset + 4 * i] */
    unsigned int ok_site, ok_resume, ok_stay;
    unsigned int ctor_site, ctor;
    unsigned char ctor_stock[5];
} adv_table_game;

static const adv_table_game ADV_TABLE_GAMES[3] = {
    { 3, 0x4B3C78u, 57, 0x592730u, 0x3A7, 0x3A9, 0x47EA40u, 0x4185A0u, 0x40C230u, 0x40C1F0u, 0x4032D0u,
      0x419B6Eu, 0x419B54u, 0x419B73u, { 0x83, 0xFE, 0x3A, 0x7C, 0xE1 }, 0x08,
      0x419A18u, 0x419A1Du, 0x419AB4u,
      0x419BEAu, 0x4192F0u, { 0xE8, 0x01, 0xF7, 0xFF, 0xFF } },
    { 4, 0x4CCA28u, 49, 0x4DEA20u, 0x35F, 0x361, 0x48CB64u, 0x416F60u, 0x40C210u, 0x40C190u, 0x4036D0u,
      0x418070u, 0x418050u, 0x418075u, { 0x83, 0xFE, 0x32, 0x7C, 0xDB }, 0x10,
      0x417EB8u, 0x417EBDu, 0x417F60u,
      0x418106u, 0x417790u, { 0xE8, 0x85, 0xF6, 0xFF, 0xFF } },
    { 5, 0x4DC850u, 55, 0x5240A8u, 0x3B3, 0x3B5, 0x497D34u, 0x417700u, 0x40C700u, 0x40C680u, 0x403660u,
      0x4188E0u, 0x4188C0u, 0x4188E5u, { 0x83, 0xFE, 0x38, 0x7C, 0xDB }, 0x10,
      0x418738u, 0x41873Du, 0x4187E0u,
      0x41896Au, 0x418020u, { 0xE8, 0xB1, 0xF6, 0xFF, 0xFF } },
};
static const unsigned char ADV_OK_STOCK[5] = { 0x8B, 0x4E, 0x50, 0x8B, 0x01 };   /* mov ecx,[esi+0x50]; mov eax,[ecx] */

static const adv_table_game *g_tg;
static const adv_game *g_table_adv;

/* The stubs' addresses (read by the naked stubs). */
static unsigned int g_loop_end, g_loop_top, g_loop_after, g_list_offset;
static unsigned int g_ok_resume, g_ok_stay, g_ctor;

/* ---- The villagers of the three games ---------------------------------------------------------------------- */

static unsigned int g_manager;         /* The Secret City: the village; the other two: the villager manager */
static int g_records;
static unsigned int g_first;           /* the first record */
static unsigned int g_stride;

static unsigned char *t_record(int index) {
    if (index < 0 || index >= g_records) {
        return NULL;
    }
    return (unsigned char *)(uintptr_t)(g_first + (unsigned int)index * g_stride);
}

static int t_count(void) {
    return g_records;
}

static int t_rand(int n) {
    return n <= 1 ? 0 : ((adv_rand_fn)(uintptr_t)g_tg->rand)(n);
}

/* The Secret City: present (+0xF10), alive (health +0xE78), not a stand-in record (+0xE94), 14 or more (+0xDC4),
   not carrying a baby (+0xE8C, the game's "pregnant or nursing"), not the Tribal Chief (+0xE80). */
static int vv3_eligible(const unsigned char *r) {
    return r[0xF10] != 0 && *(const int *)(r + 0xE78) > 0 && r[0xE94] == 0 && *(const int *)(r + 0xDC4) >= ADV_ADULT_UNITS
        && !adv_is_protected(3, r);
}

/* The Tree of Life: present (+0xCC4 of the record's +0x1000 half: +0x1CC4), not a body or ghost (+0x1CC7), alive
   (+0x1C40), 14 or more (+0x1B8C), not carrying a baby (+0x1C4C). */
static int vv4_eligible(const unsigned char *r) {
    return r[0x1CC4] != 0 && *(const int *)(r + 0x1C40) > 0 && *(const int *)(r + 0x1B8C) >= ADV_ADULT_UNITS
        && !adv_is_protected(4, r);
}

/* New Believers: present (+0x1CD4), alive (+0x1C40), not a Reanimated spirit (+0x1CE1), a believer (Heathen
   +0x1CEC clear), not one of the roles the game's own picker skips (+0x1CFC 12-17: the chief, the Retired Chief,
   the puzzles' Heathens), 14 or more (+0x1B8C), not carrying a baby (+0x1C4C). */
static int vv5_eligible(const unsigned char *r) {
    return r[0x1CD4] != 0 && *(const int *)(r + 0x1C40) > 0 && r[0x1CEC] == 0
        && *(const int *)(r + 0x1B8C) >= ADV_ADULT_UNITS && !adv_is_protected(5, r);
}

static unsigned int t_name_offset(void) {
    return g_tg->game == 3 ? 0xDD4u : 0x1B9Cu;
}

static int t_female(const unsigned char *r) {
    return *(const int *)(r + (g_tg->game == 3 ? 0xDC8u : 0x1B90u)) != 0;
}

static void t_name(const unsigned char *r, char *out, int cap) {
    char field[0x1A];
    memcpy(field, r + t_name_offset(), 0x19);
    field[0x19] = '\0';
    adv_copy(out, cap, field);
}

/* Kill: the game's own death with cause -1, "Unknown causes" (the record's health block, value 0, cause -1),
   as The Secret City's Medical Emergency (0x4172D9), The Tree of Life's Sealed Box (0x415D94, after the stop
   0x468C60) and New Believers' (0x473440, then SetHealth 0x4758B0) write it. */
static void t_kill(int index) {
    unsigned char *r = t_record(index);
    switch (g_tg->game) {
    case 3:
        ADV_TC2(0x462670u, r + 0xE6C, 0, -1);
        break;
    case 4:
        ADV_TC0(0x468C60u, r);
        ADV_TC2(0x46AF00u, r + 0x1C34, 0, -1);
        break;
    default:
        ADV_TC0(0x473440u, r);
        ADV_TC2(0x4758B0u, r + 0x1C34, 0, -1);
        break;
    }
}

/* Gone, no body: The Secret City's wave sweep (0x45D9D1: the active byte, the selection dropped first, 0x45FCC0,
   as the burial does); The Tree of Life's Sealed Box wave (0x415D91: the death, then the active byte); New
   Believers' removal of a living villager (0x420142: the activity stopped, the selection dropped, the presence
   byte). */
static void t_vanish(int index) {
    unsigned char *r = t_record(index);
    switch (g_tg->game) {
    case 3:
        if (r[0xF11] != 0) {
            ADV_TC0(0x45FCC0u, g_manager);
        }
        r[0xF10] = 0;
        break;
    case 4:
        ADV_TC0(0x468C60u, r);
        ADV_TC2(0x46AF00u, r + 0x1C34, 0, -1);
        r[0x1CC4] = 0;
        break;
    default:
        ADV_TC0(0x473440u, r);
        if ((((adv_tc0r)(uintptr_t)0x4653D0u)(r, NULL) & 0xFF) != 0) {
            ADV_TC0(0x470800u, g_manager);
        }
        r[0x1CD4] = 0;
        break;
    }
}

static void t_injure(int index, int health) {
    unsigned char *r = t_record(index);
    switch (g_tg->game) {
    case 3:
        ADV_TC2(0x462670u, r + 0xE6C, health, -1);
        adv_dislike((int *)(r + 0xFB4), (int *)(r + 0xFC0), 3, 38);
        break;
    case 4:
        ADV_TC2(0x46AF00u, r + 0x1C34, health, -1);
        adv_dislike((int *)(r + 0x1E60), (int *)(r + 0x1E6C), 3, 38);
        break;
    default:
        ADV_TC2(0x4758B0u, r + 0x1C34, health, -1);
        adv_dislike((int *)(r + 0x1F5C), (int *)(r + 0x1F68), 3, 38);
        break;
    }
}

/* Farming, Building, Research, Healing, Parenting: The Secret City's ints +0xEAC.. (Farming, Parenting, Healing,
   Research, Building), the later two's floats +0x1C5C.. in the same order; at most 100, never below 0 (The Secret
   City's own skill adder 0x455740: cmp edx, 0x64 / mov 0x64, test / mov 0). */
static void t_skill(int index, int which, int amount) {
    static const int SLOT[5] = { 0, 4, 3, 2, 1 };
    unsigned char *r = t_record(index);
    if (g_tg->game == 3) {
        int *field = (int *)(r + 0xEAC + 4 * SLOT[which]);
        *field = adv_capped(*field + amount);
    } else {
        float *field = (float *)(r + 0x1C5C + 4 * SLOT[which]);
        float value = *field + (float)amount;
        *field = value > 100.0f ? 100.0f : (value < 0.0f ? 0.0f : value);
    }
}

/* New Believers: the game's own conversion 0x4669E0 (the bottom bar's "stopped believing" line, the role cleared,
   the faction set by 0x466880, the activity stopped), with The Mask's Faith -10. */
static void vv5_convert(int index) {
    unsigned char *r = t_record(index);
    ADV_TC0(0x4669E0u, r);
    *(int *)(r + 0x1CF0) = -10;
}

/* "Isolans'" when the game's own eSayStoppedBelieving (id 0x48) says "left the tribe" (Guardians of Isola's
   rewrite), else "heathens'". */
static int vv5_joins_key(void) {
    static const char WORDS[] = "left the tribe";
    int found = 0;
    __try {
        const unsigned int *entry = *(const unsigned int *const *)(uintptr_t)(0x5240A8u + 4u * 0x48u);
        const char *text;
        int i, k;
        if (entry != NULL && entry[0] == 0x48u) {
            text = (const char *)(uintptr_t)(entry[3] != 0 ? entry[3] : entry[2]);
            for (i = 0; text != NULL && text[i] != '\0' && i < 256 && !found; ++i) {
                for (k = 0; WORDS[k] != '\0'; ++k) {
                    char c = text[i + k];
                    if (c >= 'A' && c <= 'Z') {
                        c = (char)(c - 'A' + 'a');
                    }
                    if (c != WORDS[k]) {
                        break;
                    }
                }
                found = WORDS[k] == '\0';
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        found = 0;
    }
    return found ? ADV_L2_ISOLANS : ADV_L2_HEATHENS;
}

static int t_other_joins(void) {
    return ADV_L2_OTHER;
}

/* ---- The reward ---------------------------------------------------------------------------------------------- */

static volatile int *t_store(int kind) {
    static const unsigned int STORES[3][2] = {
        { 0x582490u, 0x582644u }, { 0x4D6DD0u, 0x4D6F88u }, { 0x51D34Cu, 0x51D5F8u } };
    return (volatile int *)(uintptr_t)STORES[g_tg->game - 3][kind];
}

/* The Secret City's own rule for its events' amounts (every two-choice event's [13]): x m, m = the villagers its
   picker 0x45D460(7, -1, 1) counts, / 20, + 1. */
static int vv3_amount(int kind, int base) {
    int count = 0;
    (void)kind;
    __try {
        ((adv_tc4r)(uintptr_t)0x45D460u)((void *)(uintptr_t)g_manager, NULL, 7, -1, 1, (int)(uintptr_t)&count);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        count = 0;
    }
    if (count < 0) {
        count = 0;
    }
    return base * (count / 20 + 1);
}

/* The Tree of Life and New Believers pay fixed amounts; with "Island Events Scale With Population" (or "...With
   Stored Food and Tech Points") ticked its companion's rule, as it scales the game's own events
   (native/vvfp_island_events_scale). */
static int t_scaled(int kind, int base, unsigned int count_routine) {
    typedef int (__stdcall *mode_fn)(void);
    HMODULE module = GetModuleHandleA("VVFP Island Events Scale.dll");
    mode_fn mode = module != NULL ? (mode_fn)(void *)GetProcAddress(module, "VvfpIslandEventsScaleMode") : NULL;
    int m = mode != NULL ? mode() : 0;
    __try {
        if (m == 2) {
            int stored = *t_store(kind);
            return base + (stored > 0 ? stored / 10 : 0);
        }
        if (m == 1) {
            int n = ((adv_tc0r)(uintptr_t)count_routine)((void *)(uintptr_t)g_manager, NULL);
            return base * (n > 50 ? 3 : (n > 25 ? 2 : 1));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return base;
}

static int vv4_amount(int kind, int base) {
    return t_scaled(kind, base, 0x467610u);
}

static int vv5_amount(int kind, int base) {
    return t_scaled(kind, base, 0x4713F0u);
}

/* Through the game's own writer (thiscall on the store, the amount): The Secret City 0x4263F0 / 0x427130, The Tree
   of Life 0x41D920 / 0x41E300, New Believers 0x41EB40 / 0x4237B0 -- each counts the lifetime total and its
   trophies as for the game's own events. */
static void t_award(int kind, int amount) {
    static const unsigned int WRITERS[3][2] = {
        { 0x4263F0u, 0x427130u }, { 0x41D920u, 0x41E300u }, { 0x41EB40u, 0x4237B0u } };
    ADV_TC1(WRITERS[g_tg->game - 3][kind], (void *)t_store(kind), amount);
}

/* The awards' base ranges (src/vv_aspiring_adventurer.py AWARD_RANGES: each game's smallest and largest stock
   island-event gain): The Secret City food 200 (the Bitter Brown Beans' taste, m x 200) .. 600 (their brew), tech
   1,000 (the beans' taste, The Return of Biggles) .. 2,000 (The Mysterious Fog); The Tree of Life food 300 (The
   Mysterious Footprints, The Arc of Brilliant Colors: its only food gains), tech 500 (The Mosquito Larvae 0x415A74)
   .. 5,000 (The Sealed Box 0x415D7F); New Believers food 50 (Mushroom Day!'s rand(50) + 50, 0x415110) .. 300 (The
   Mysterious Footprints), tech 500 (You're Doing It Wrong! 0x4160A5) .. 3,000 (Trick Or Trade 0x416692). */
static const adv_game ADV_VV3 = {
    3, t_count, t_record, vv3_eligible, t_female, t_name, t_rand, t_kill, t_vanish, t_injure, t_skill, NULL,
    vv3_amount, t_award, t_other_joins, 46, 11, 0,
    200, 600, 1000, 2000, NULL, NULL
};
static const adv_game ADV_VV4 = {
    4, t_count, t_record, vv4_eligible, t_female, t_name, t_rand, t_kill, t_vanish, t_injure, t_skill, NULL,
    vv4_amount, t_award, t_other_joins, 46, 11, 0,
    300, 300, 500, 5000, NULL, NULL
};
static const adv_game ADV_VV5 = {
    5, t_count, t_record, vv5_eligible, t_female, t_name, t_rand, t_kill, t_vanish, t_injure, t_skill, vv5_convert,
    vv5_amount, t_award, vv5_joins_key, 46, 17, 0,
    50, 300, 500, 3000, NULL, NULL
};

/* ---- The events in slot 0 ------------------------------------------------------------------------------------------

   Every More Island Events event of these games is an object put in the table's slot 0 (THE EVENT, above), each with
   its own place in the draw (t_list).  The two-choice ones -- The Aspiring Adventurer in all three games, Diving for
   Treasure in The Secret City (dive_vv3.inc) -- share one virtual table and the methods below, each through its own
   adv_flow (its question, labels, answer, endings and effects); The Troubling Signs (troubling_vv3.inc) has its own
   object, methods and four-answer dialog.  Each registers itself with t_register. */

typedef struct adv_object {
    void *vtable;
    void *villager;
    int amount;
    int extra[2];
} adv_object;

#define T_MAX_EVENTS 8

typedef struct t_event {
    adv_object *object;
    const adv_flow *flow;              /* NULL: not shown by the two-choice methods below (The Troubling Signs) */
    int (*listable)(void);             /* it can happen now */
    int (*begin)(void);                /* composed for the popup about to be built: 1 ready */
    int ready, answered, ending;       /* ending: adv_flow's, -1 none yet */
} t_event;

static t_event g_events[T_MAX_EVENTS]; /* in the order registered: the order t_list's draw counts them */
static int g_event_count;
static t_event *g_ev;                  /* the two-choice event of the popup being shown */

static unsigned int g_vtable[17];      /* [0] = the source's RTTI locator */
static adv_object g_object;            /* The Aspiring Adventurer's */
static adv_object g_ts_object;         /* The Troubling Signs' (The Secret City, troubling_vv3.inc) */
static void *g_ctor_dialog;            /* the dialog being built (t_ctor_thunk) */
static int g_list_count;               /* the entries t_list adds */
static void ts_after_ctor(void *dialog);
static int ts_ok(void *dialog);
static void ts_install(void);
static void dv_install(void);
static adv_string g_title_entry, g_body_entry;
static adv_string *g_saved_title, *g_saved_body;
static int g_strings_in;
static char g_title[256];

static void *g_dialog;
static int g_stage, g_page;
static int g_effects_page = -1;          /* the ending's page that makes its effects (its last), -1 made */

static void t_register(adv_object *object, const adv_flow *flow, int (*listable)(void), int (*begin)(void)) {
    if (g_event_count < T_MAX_EVENTS) {
        t_event *ev = &g_events[g_event_count++];
        memset(ev, 0, sizeof *ev);
        ev->object = object;
        ev->flow = flow;
        ev->listable = listable;
        ev->begin = begin;
        ev->ending = -1;
    }
}

/* The two-choice event whose object `object` is, NULL when none. */
static t_event *t_event_of(const void *object) {
    int k;
    for (k = 0; k < g_event_count; ++k) {
        if (object != NULL && (const void *)g_events[k].object == object && g_events[k].flow != NULL) {
            return &g_events[k];
        }
    }
    return NULL;
}

static adv_string **t_slots(void) {
    return (adv_string **)(uintptr_t)g_tg->strings;
}

/* Our entries in the two ids' index slots (the stock ones kept to give back). */
static void t_strings_in(void) {
    adv_string **slots = t_slots();
    if (!g_strings_in) {
        g_saved_title = slots[g_tg->title_id];
        g_saved_body = slots[g_tg->body_id];
        g_strings_in = 1;
    }
    g_title_entry.id = g_tg->title_id;
    g_title_entry.key = "eVvfpAspiringAdventurerTitle";
    g_title_entry.text = g_title;
    g_title_entry.localized = NULL;
    g_body_entry.id = g_tg->body_id;
    g_body_entry.key = "eVvfpAspiringAdventurerText";
    g_body_entry.localized = NULL;
    slots[g_tg->title_id] = &g_title_entry;
    slots[g_tg->body_id] = &g_body_entry;
}

static void t_strings_out(void) {
    adv_string **slots = t_slots();
    if (g_strings_in) {
        if (slots[g_tg->title_id] == &g_title_entry) {
            slots[g_tg->title_id] = g_saved_title;
        }
        if (slots[g_tg->body_id] == &g_body_entry) {
            slots[g_tg->body_id] = g_saved_body;
        }
        g_strings_in = 0;
    }
}

/* The body id, carrying `text` (already the player's language). */
static int t_text_id(const char *text) {
    t_strings_in();
    g_body_entry.text = adv_shown(text);
    g_body_entry.localized = NULL;
    return g_tg->body_id;
}

/* The body id, carrying a button's label as it is (never wrapped). */
static int t_label_text_id(const char *text) {
    t_strings_in();
    g_body_entry.text = text;
    return g_tg->body_id;
}

/* The popup being built (g_ctor_dialog) is sized for `*text`: with `count` answers (3 or 4), `*text` padded with
   blank lines worth the extra buttons' room (the shared multi-answer popup).  Returns that room (0: two answers). */
static int t_padded_for(int count, const char **text) {
    static char padded[ADV_PAGE_BYTES];
    int room = count > 2 && g_ctor_dialog != NULL ? ma_room_for(g_ctor_dialog, count) : 0;
    if (room > 0) {
        *text = ma_padded(ma_game_of(g_tg->game), *text, g_ctor_dialog, room, padded, ADV_PAGE_TEXT_MAX);
    }
    return room;
}

static void __fastcall o_delete(void *self, void *unused, int flags) {
    (void)self; (void)unused; (void)flags;
}

static char __fastcall o_condition(void *self, void *unused) {
    t_event *ev = t_event_of(self);
    (void)unused;
    return (char)(ev != NULL && ev->listable());
}

static char __fastcall o_true(void *self, void *unused) {
    (void)self; (void)unused;
    return 1;
}

/* +0x08, asked once as the dialog is built: the event is composed here. */
static int __fastcall o_title(void *self, void *unused) {
    t_event *ev = t_event_of(self);
    (void)unused;
    g_dialog = NULL;
    g_stage = ADV_STAGE_NONE;
    g_effects_page = -1;
    g_ev = ev;
    g_title[0] = '\0';
    if (ev == NULL) {
        ((adv_object *)self)->villager = NULL;         /* not ours: the dialog is not shown */
    } else {
        ev->answered = 0;
        ev->ending = -1;
        ev->ready = ev->begin();
        ((adv_object *)self)->villager = ev->ready ? g_table_adv->record(ev->flow->subject()) : NULL;
        ev->flow->title(g_title, sizeof g_title);
        if (ev->ready) {
            adv_log_event(g_table_adv->game, g_title);
        }
    }
    t_strings_in();
    return g_tg->title_id;
}

static int __fastcall o_question(void *self, void *unused) {
    t_event *ev = t_event_of(self);
    const adv_pages *q = ev != NULL ? ev->flow->question(0) : NULL;
    (void)unused;
    return t_text_id(q != NULL && q->count > 0 ? q->text[q->count - 1] : "");
}

static int t_label_id(void *self, int which) {
    static char label[2][128];
    t_event *ev = t_event_of(self);
    label[which][0] = '\0';
    if (ev != NULL) {
        ev->flow->label(0, which, label[which], sizeof label[which]);
    }
    t_strings_in();
    g_body_entry.text = label[which];
    return g_tg->body_id;
}

static int __fastcall o_label_a(void *self, void *unused) {
    (void)unused;
    return t_label_id(self, 0);
}

static int __fastcall o_label_b(void *self, void *unused) {
    (void)unused;
    return t_label_id(self, 1);
}

static void *__fastcall o_villager(void *self, void *unused) {
    (void)unused;
    return ((adv_object *)self)->villager;
}

static void *__fastcall o_nobody(void *self, void *unused) {
    (void)self; (void)unused;
    return NULL;
}

static int __fastcall o_pose(void *self, void *unused) {
    (void)self; (void)unused;
    return 5;
}

/* +0x28(c): before the answer the tallest page of the event (the popup is sized to it), then the ending's page. */
static int __fastcall o_result(void *self, void *unused, int choice) {
    t_event *ev = t_event_of(self);
    const adv_pages *pages;
    (void)unused; (void)choice;
    if (ev == NULL) {
        return t_text_id("");
    }
    if (!ev->answered) {
        const char *text = ev->flow->tallest();
        if (adv_answers(ev->flow, 0) > 2) {
            __try {
                t_padded_for(adv_answers(ev->flow, 0), &text);   /* room for the extra answers */
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                text = ev->flow->tallest();
            }
        }
        return t_text_id(text);
    }
    pages = ev->flow->ending(ev->ending);
    return t_text_id(pages->text[g_page < pages->count ? g_page : 0]);
}

/* The ending's last page is shown: its effects (adv_log.inc). */
static void t_page_effects(void) {
    g_effects_page = -1;
    if (g_ev != NULL && g_ev->answered) {
        adv_log_effects(g_ev->flow->effects, g_ev->ending);
    }
}

/* Answer `choice` (0 the first) of event `ev`: logged, the ending's first page next, with the effects when it is the
   last. */
static void t_chosen(t_event *ev, int choice) {
    static char label[128];
    if (ev == NULL || !ev->ready || ev->answered) {
        return;
    }
    ev->flow->label(0, choice, label, sizeof label);
    ev->answered = 1;
    ev->ending = -1 - ev->flow->choose(0, choice);
    g_ev = ev;
    adv_log_choice(label);
    g_stage = ADV_STAGE_RESULT;
    g_page = 0;
    g_effects_page = ev->flow->ending(ev->ending)->count - 1;
    if (g_effects_page == 0) {
        t_page_effects();
    }
}

/* +0x34(c): the game's own two buttons (c 0 the first); the ending's first page follows (+0x28). */
static void __fastcall o_choose(void *self, void *unused, int choice) {
    (void)unused;
    t_chosen(t_event_of(self), choice != 0);
}

/* +0x2C(c): OK on the last page (the effects were made as it was shown). */
static void __fastcall o_apply(void *self, void *unused, int choice) {
    (void)self; (void)unused; (void)choice;
    if (g_effects_page >= 0) {
        t_page_effects();                    /* never left unmade (a page count that changed: a fault) */
    }
    g_stage = ADV_STAGE_NONE;
    g_dialog = NULL;
    t_strings_out();
}

/* The two-choice events' virtual table (a copy of the stock event's, its methods ours), built once. */
static void t_build_object(void) {
    static const int SLOTS[] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13 };
    void *functions[13];
    int i;
    memcpy(g_vtable, (const void *)(uintptr_t)(g_tg->source_vtable - 4u), sizeof g_vtable);
    functions[0] = (void *)o_delete;
    functions[1] = (void *)o_condition;
    functions[2] = (void *)o_title;
    functions[3] = (void *)o_question;
    functions[4] = (void *)o_true;
    functions[5] = (void *)o_label_a;
    functions[6] = (void *)o_label_b;
    functions[7] = (void *)o_villager;
    functions[8] = (void *)o_nobody;
    functions[9] = (void *)o_pose;
    functions[10] = (void *)o_result;
    functions[11] = (void *)o_apply;
    functions[12] = (void *)o_choose;
    for (i = 0; i < 13; ++i) {
        g_vtable[1 + SLOTS[i]] = (unsigned int)(uintptr_t)functions[i];
    }
}

/* A two-choice event's object: the shared virtual table. */
static void t_new_object(adv_object *object) {
    memset(object, 0, sizeof *object);
    object->vtable = &g_vtable[1];
    object->amount = -1;
}

/* The Aspiring Adventurer, as these methods ask it. */
static int adv_listable(void) {
    return adv_possible(g_table_adv);
}

static int adv_begin_now(void) {
    return adv_begin(g_table_adv);
}

/* ---- The sites ------------------------------------------------------------------------------------------------ */

/* After the stock slots are listed (`listed` of them): the entries to add, one for EACH registered event that can
   happen now -- so each is drawn as any stock event, 1 in (count + entries) -- and the object put in slot 0 one of
   those events', each equally likely (the game's own rand; none drawn when only one can happen).  Whichever entry
   the selector then draws presents slot 0, so each event's chance is its own entry's.  The list holds the stock
   slots + 1 entries (the dialog's frame follows it): never more entries than its room (when it is full the extra
   entries are left out, never written past it; the slot's object is still drawn fairly among the events). */
static int __cdecl t_list(int listed) {
    int k, n = 0, room = g_tg->slots + 1 - listed;
    int can[T_MAX_EVENTS];
    adv_log_reset();                     /* an island event is being drawn: whatever was ours is over */
    __try {
        *(void **)(uintptr_t)g_tg->table = &g_object;
        for (k = 0; k < g_event_count; ++k) {
            if (g_events[k].listable != NULL && g_events[k].listable()) {
                can[n++] = k;
            }
        }
        if (n > 0) {
            *(void **)(uintptr_t)g_tg->table = g_events[can[t_rand(n)]].object;
        }
        {
            /* Pick Island Event chose one of ours (mie_pick.inc): its object in slot 0, which the Story companion's
               pick (slot 0) presents when the object's own condition holds. */
            adv_object *picked = mp_due_object(g_tg->game);
            if (picked != NULL) {
                *(void **)(uintptr_t)g_tg->table = picked;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *(void **)(uintptr_t)g_tg->table = &g_object;
        n = 0;
    }
    if (room < 0) {
        room = 0;
    }
    return n < room ? n : room;
}

/* jmp from the loop end `cmp esi, N; jl top` (5 bytes). */
__declspec(naked) static void t_loop_stub(void) {
    __asm {
        cmp esi, dword ptr [g_loop_end]
        jge done_loop
        jmp dword ptr [g_loop_top]
    done_loop:
        pushad
        push edi
        call t_list
        add esp, 4
        mov dword ptr [g_list_count], eax
        popad
    next_entry:
        cmp dword ptr [g_list_count], 0
        jle not_listed
        mov eax, esp
        add eax, dword ptr [g_list_offset]
        mov dword ptr [eax + edi * 4], 0
        inc edi
        dec dword ptr [g_list_count]
        jmp next_entry
    not_listed:
        jmp dword ptr [g_loop_after]
    }
}

static void t_set_text(void *dialog, const char *page) {
    ADV_TC1(g_tg->set_text, dialog, t_text_id(page));
}

static void *t_control(void *dialog, unsigned int offset) {
    return *(void **)((unsigned char *)dialog + offset);
}

/* ---- Three or four answers (the shared multi-answer popup, native/shared/vvfp_multi_answer.h) ------------------- */

static int g_multi;                    /* the popup on screen has our extra answer buttons */

static int t_state(void *dialog) {
    if (dialog == NULL || dialog != g_dialog || g_ev == NULL) {
        return MA_NOT_OURS;
    }
    if (g_ev->answered) {
        return MA_ANSWERED;
    }
    return g_stage == ADV_STAGE_QUESTION ? MA_ASKING : (g_stage == ADV_STAGE_INTRO ? MA_OK_UP : MA_NOT_OURS);
}

/* Answer 2 or 3 clicked (or typed): as the game answers its own two -- the answer, the ending's first page, OK up. */
static void t_extra_answer(void *dialog, int answer) {
    const adv_pages *pages;
    t_chosen(g_ev, answer);
    if (g_ev != NULL && g_ev->answered) {
        pages = g_ev->flow->ending(g_ev->ending);
        t_set_text(dialog, pages->text[0]);
    }
    ADV_TC1(g_tg->show, dialog, t_control(dialog, 0x864));
}

static const ma_client T_CLIENT = { t_label_text_id, t_state, t_extra_answer };

/* The answers on screen or off: ours with the game's two when there are more than two. */
static void t_show_answers(void *dialog, int shown) {
    if (g_multi) {
        ma_show(dialog, shown);
        return;
    }
    ADV_TC1(shown ? g_tg->show : g_tg->hide, dialog, t_control(dialog, 0x85C));
    ADV_TC1(shown ? g_tg->show : g_tg->hide, dialog, t_control(dialog, 0x860));
}

/* After the dialog's constructor: three or four answers get their extra buttons; a question of more than one page
   starts with its first page and OK. */
static void __cdecl t_after_ctor(void *dialog) {
    __try {
        void *object = dialog != NULL ? *(void **)((unsigned char *)dialog + 0x50) : NULL;
        t_event *ev = t_event_of(object);
        const adv_pages *q;
        int n;
        g_ctor_dialog = NULL;
        g_multi = 0;
        if (object != NULL && object == &g_ts_object) {
            ts_after_ctor(dialog);
            return;
        }
        if (ev == NULL || ev != g_ev || !ev->ready) {
            return;
        }
        q = ev->flow->question(0);
        g_dialog = dialog;
        g_page = 0;
        n = adv_answers(ev->flow, 0);
        if (n > 2 && ((unsigned char *)dialog)[0x4C] != 0) {
            static char labels[MA_MAX_ANSWERS][MA_LABEL_BYTES];
            const char *words[MA_MAX_ANSWERS];
            int k;
            for (k = 0; k < n; ++k) {
                ev->flow->label(0, k, labels[k], sizeof labels[k]);
                words[k] = labels[k];
            }
            g_multi = ma_attach(g_tg->game, &T_CLIENT, dialog, n, words);
            if (g_multi && q->count <= 1) {
                t_set_text(dialog, q->text[q->count - 1]);   /* the labels went through the text: the question back */
            }
        }
        if (q->count > 1) {
            t_show_answers(dialog, 0);
            ADV_TC1(g_tg->show, dialog, t_control(dialog, 0x864));
            t_set_text(dialog, q->text[0]);
            g_stage = ADV_STAGE_INTRO;
        } else {
            g_stage = ADV_STAGE_QUESTION;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* In place of the presenter's `call <constructor>` (ecx the dialog, one argument, ret 4). */
__declspec(naked) static void t_ctor_thunk(void) {
    __asm {
        mov dword ptr [g_ctor_dialog], ecx
        push ecx
        push dword ptr [esp + 8]
        call dword ptr [g_ctor]
        pop ecx
        pushad
        push ecx
        call t_after_ctor
        add esp, 4
        popad
        ret 4
    }
}

/* OK: 1 when this event's next page was shown (the dialog stays). */
static int __cdecl t_ok(void *dialog) {
    int stay = 0;
    __try {
        void *object = dialog != NULL ? *(void **)((unsigned char *)dialog + 0x50) : NULL;
        t_event *ev;
        if (object != NULL && object == &g_ts_object) {
            return ts_ok(dialog);
        }
        ev = t_event_of(object);
        if (dialog == NULL || dialog != g_dialog || ev == NULL || ev != g_ev) {
            return 0;
        }
        if (g_stage == ADV_STAGE_INTRO) {
            const adv_pages *q = ev->flow->question(0);
            ++g_page;
            if (g_page >= q->count - 1) {
                t_set_text(dialog, q->text[q->count - 1]);
                ADV_TC1(g_tg->hide, dialog, t_control(dialog, 0x864));
                t_show_answers(dialog, 1);
                g_stage = ADV_STAGE_QUESTION;
            } else {
                t_set_text(dialog, q->text[g_page]);
            }
            stay = 1;
        } else if (g_stage == ADV_STAGE_RESULT) {
            const adv_pages *pages = ev->flow->ending(ev->ending);
            if (g_page + 1 < pages->count) {
                ++g_page;
                t_set_text(dialog, pages->text[g_page]);
                if (g_page == g_effects_page) {
                    t_page_effects();
                }
                stay = 1;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        stay = 0;
    }
    return stay;
}

/* jmp from the OK branch's `mov ecx, [esi+0x50]; mov eax, [ecx]` (esi the dialog). */
__declspec(naked) static void t_ok_stub(void) {
    __asm {
        pushad
        push esi
        call t_ok
        add esp, 4
        test eax, eax
        popad
        jnz stay
        mov ecx, dword ptr [esi + 0x50]
        mov eax, dword ptr [ecx]
        jmp dword ptr [g_ok_resume]
    stay:
        jmp dword ptr [g_ok_stay]
    }
}

/* The room the extra answer buttons of the popup on screen take beyond the game's two, for Scrolling Popups (the
   shared multi-answer popup: The Troubling Signs' four, or any event's three or four): 0 for any other dialog. */
int __stdcall VvfpMoreIslandEventsButtonRoom(const void *popup) {
    return ma_room(popup);
}

/* The answer buttons of the popup on screen, top to bottom (for the tests): out[0..3]; the count (0 none of ours). */
int __stdcall VvfpMoreIslandEventsAnswerButtons(void **out) {
    int k;
    if (out == NULL || g_ma.dialog == NULL) {
        return 0;
    }
    for (k = 0; k < g_ma.count; ++k) {
        out[k] = ma_button(g_ma.dialog, k);
    }
    return g_ma.count;
}

static int t_locate(int game) {
    const unsigned char *module = (const unsigned char *)GetModuleHandleA(NULL);
    unsigned int rva = 0, slots = 0;
    if (module == NULL) {
        module = (const unsigned char *)(uintptr_t)0x400000u;
    }
    if (game == 3) {
        vv3_villager_table(module, &rva, &slots);
        g_first = 0x14u;
        g_stride = 0x1F8Cu;
    } else if (game == 4) {
        vv4_villager_table(module, &rva, &slots);
        g_first = 0x44u;
        g_stride = 0x2E3Cu;
    } else {
        vv5_villager_table(module, &rva, &slots);
        g_first = 0x48u;
        g_stride = 0x2F44u;
    }
    if (rva == 0 || slots == 0) {
        return 0;
    }
    g_manager = (unsigned int)(uintptr_t)module + rva;
    g_first += g_manager;
    g_records = (int)slots;
    return 1;
}

static int t_install(int game) {
    static vvfp_site_write w[3];
    if (game < 3 || game > 5 || !t_locate(game)) {
        return 0;
    }
    g_tg = &ADV_TABLE_GAMES[game - 3];
    g_table_adv = game == 3 ? &ADV_VV3 : (game == 4 ? &ADV_VV4 : &ADV_VV5);
    g_loop_end = (unsigned int)(g_tg->slots + 1);
    g_loop_top = g_tg->loop_top;
    g_loop_after = g_tg->loop_after;
    g_list_offset = (unsigned int)g_tg->list_offset;
    g_ok_resume = g_tg->ok_resume;
    g_ok_stay = g_tg->ok_stay;
    g_ctor = g_tg->ctor;
    if (*(const unsigned int *)(uintptr_t)g_tg->table != 0u
        || !vvfp_site_holds(g_tg->source_vtable - 4u, (const unsigned char *)(uintptr_t)(g_tg->source_vtable - 4u),
                            (int)sizeof g_vtable)) {
        return 0;                       /* slot 0 taken by something else, or no vtable to copy */
    }
    t_build_object();
    g_event_count = 0;
    t_new_object(&g_object);
    t_register(&g_object, &ADV_FLOW, adv_listable, adv_begin_now);   /* first: the draw's index 0 */
    if (game == 3) {
        ts_install();                   /* The Troubling Signs (troubling_vv3.inc): no site of its own */
        dv_install();                   /* Diving for Treasure (dive_vv3.inc): no site of its own */
    }
    vvfp_site_branch(&w[0], g_tg->loop_site, 5, g_tg->loop_stock, 0xE9, (const void *)t_loop_stub);
    vvfp_site_branch(&w[1], g_tg->ok_site, 5, ADV_OK_STOCK, 0xE9, (const void *)t_ok_stub);
    vvfp_site_branch(&w[2], g_tg->ctor_site, 5, g_tg->ctor_stock, 0xE8, (const void *)t_ctor_thunk);
    if (!vvfp_install_sites(w, 3)) {
        return 0;
    }
    g_adv_game = g_table_adv;
    return 1;
}
