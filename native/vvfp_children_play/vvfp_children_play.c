/* VVFP Children Play -- "Children Play Tag and Build Sandcastles" (all five games).

   The owner (2026-11-14): "children should be able to play tag and build sandcastles in VV1-VV4", "don't need any
   art for sandcastles. but the children should build sandcastles near the ocean in each game if they don't already
   do that", then: tag is a normal play choice like sandcastles; "all children should participate in tag. Same
   rules as VV2 or whatever games have them natively. Same for making sandcastles."

   WHAT EACH GAME GETS.  Every game picks a child's pastime in one routine (the "pastime pick"), reached from the
   villager's life tick when the child has nothing to do:
     A New Home        0x4479B0 (called at 0x448299)                     adds tag and sandcastles
     The Lost Children 0x45EE00 (0x4618C9)                               adds sandcastles; its own tag more often
     The Secret City   0x45B9B0 (0x45C16A, 0x45BDC9, the potion 0x4269C9) adds tag (its sandcastles are stock)
     The Tree of Life  0x465260 (0x4658D7)                               adds tag (its sandcastles are stock)
     New Believers     0x46E3F0 (0x46F125)                               its own tag more often
   Each call of the pick goes to pick() below.  A child who dislikes Playing (word 0x12, the games' own sandcastle
   gate) and A New Home's Golden Child (his own branch decides his picks) get the stock pick unchanged.  Otherwise one
   roll of the game's own rand(15): 0 is tag, 1 is sandcastles (in the games that get each), anything else the stock
   pick, which keeps its own odds among its choices.  So each new choice is one pick in 15, a normal play choice; the
   stock 5% roll in front of The Lost Children's and New Believers' tag is not made on this slot (their stock slot is
   left as it is).

   TAG.  The Lost Children (0x455CF0) and New Believers (0x46E705..0x46E769: the group recruiter 0x4710B0 and
   behaviour 0xEE) are started exactly as their stock slot starts them.  A New Home, The Secret City and The Tree of
   Life have none, so The Lost Children's own rule is ported: every child -- in use, alive, under 14 (age < 0x118),
   not sick, hands empty -- joins, and the game is played only when at least two such children are there (else the
   stock pick runs).  The starter is "It" (`Playing tag - "It" `), everyone else `Playing tag`, the stock words.  The
   Secret City and The Tree of Life use their own (unused) strings for them; A New Home has none, so the words are
   The Lost Children's, translatable.  New Believers' rule (80% each, up to three in four) is not used: The Lost
   Children's applies in all three games and is the one the owner named.
     - A New Home: each player is stopped (0x439470), then four rounds of a run (queue step 3, speed 150 as The Lost
       Children's tag) to a random point of one 120 by 120 square of the open village centre (845..964 by 659..778,
       inside the stock "Going to village center" area) and a pause (step 5, 10..13 as The Lost Children's).  No hop:
       A New Home has no picture of a child in the air.
     - The Secret City / The Tree of Life: each player is stopped, started on the game's own "Running around"
       (behaviour 0x94 / 0x46, so the action the game records is a stock one), stopped again (the queue and the text
       cleared; the action kept), given the tag text, and six runs at speed 150 through the six places of the stock
       "Running around" (the same six in both games), in one order shared by every player of that game of tag, ending
       with "Running around"'s own last step; then the queue is started (0x461BF0 / 0x46A030), as every stock action
       ends.  Children who dislike Playing, and The Secret City's Tribal Chief, do not join.

   SANDCASTLES (A New Home, The Lost Children: ported from The Secret City's 0x44DE40).  One child, as in every game
   that has them.  `Making sandcastles` (The Secret City's words, translatable); one of three places on the beach
   at the water picked once, then six rounds: walk there (step 3, speed 100), one time in five a short stand
   (step 2 kind 0), and twice bent over in the sand (step 2 kind 1: the "bent over at work" picture, 10..29 each).
     - A New Home: three of the stock "Cleaning up the beach" places (0x444690), south shore.
     - The Lost Children: the three stock "Relaxing at the beach" places nearest the sea (0x451E10), west shore.

   SAFETY.  Every call site is checked to be the stock `call` first and all are written or none
   (native/shared/install_sites.h).  Nothing is written to a save, a file or a villager record except through the
   game's own routines (stop, do-action, queue, its own string copy), or, in A New Home and The Lost Children, the
   Details text buffer the game's own string copy writes, bounded.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/vvfp_translate.h"

typedef int (__fastcall *pick1_fn)(void *self, void *edx, int arg);
typedef int (__fastcall *pick0_fn)(void *self, void *edx);
typedef int (__cdecl *rand_fn)(int n);
typedef int (__fastcall *tc1_fn)(void *self, void *edx, int a);
typedef int (__fastcall *tc2_fn)(void *self, void *edx, int a, int b);
typedef int (__fastcall *tc4_fn)(void *self, void *edx, int a, int b, int c, int d);
typedef int (__fastcall *tc7_fn)(void *self, void *edx, int a, int b, int c, int d, int e, int f, int g);
typedef int (__fastcall *tc8_fn)(void *self, void *edx, int a, int b, int c, int d, int e, int f, int g, int h);
typedef void *(__cdecl *getter_fn)(void);
typedef char *(__cdecl *copy_fn)(char *dst, const char *src, int cap);

#define CP_SLOTS 15                      /* one pick in 15 for each new choice */
#define CP_SLOT_TAG 0
#define CP_SLOT_SAND 1
#define CP_PLAYING 0x12                  /* the word "Playing" in the likes and dislikes lists */
#define CP_CHILD_AGE 0x118
#define CP_TAG_SPEED 150
#define CP_WALK_SPEED 100
#define CP_TEXT_BYTES 48                 /* A New Home's and The Lost Children's Details text: +0x314 / +0x4FC .. health */

static int g_game;
static int g_installed;
static UINT_PTR g_stock_pick;
static unsigned char g_expect[3][5];

static const char TAG_WORDS[] = "Playing tag";
static const char IT_WORDS[] = "Playing tag - \"It\" ";
static const char SAND_WORDS[] = "Making sandcastles";

/* ---- shared ---------------------------------------------------------------------------------------------------- */

static int game_rand(int n) {
    static const UINT_PTR RAND[6] = { 0, 0x402F10u, 0x4031A0u, 0x4032D0u, 0x4036D0u, 0x403660u };
    return ((rand_fn)RAND[g_game])(n);
}

static int in_range(int lo, int spread) {
    return lo + game_rand(spread);
}

static int dislikes(const unsigned char *list, int slots, int word) {
    int i;
    for (i = 0; i < slots; ++i) {
        if (((const int *)list)[i] == word) {
            return 1;
        }
    }
    return 0;
}

/* A text the patcher adds (A New Home, The Lost Children): its translation when it fits, into the record's own
   Details text buffer, as the game's string copy would. */
static void put_text(unsigned char *at, const char *stem, const char *english) {
    const char *text = vvfp_tr(stem, english, CP_TEXT_BYTES);
    lstrcpynA((char *)at, text, CP_TEXT_BYTES);
}

/* ---- A New Home and The Lost Children: the array's records and its queue --------------------------------------- */

typedef struct old_game {
    UINT_PTR stop, queue;
    unsigned int stride;
    int count;
    unsigned int in_use, health, age, sick, carried, text;
    int nothing;                         /* the carried value for empty hands */
} old_game;

static const old_game VV1 = { 0x439470u, 0x4399F0u, 0x3D8u, 256, 0x28u, 0x344u, 0x348u, 0x354u, 0x3Cu, 0x314u, 0x13 };
static const old_game VV2 = { 0x4492A0u, 0x449B70u, 0xE48Cu, 256, 0x30u, 0x52Cu, 0x530u, 0x53Cu, 0x44u, 0x4FCu, 0x1A };

static unsigned char *old_record(const old_game *g, unsigned char *array, int i) {
    return array + (size_t)i * g->stride;
}

static void old_queue(const old_game *g, unsigned char *array, int i, int step, int p1, int p2, int p3, int p5) {
    ((tc7_fn)g->queue)(array, NULL, i, step, p1, p2, p3, 0, p5);
}

/* The Lost Children's tag rule (0x455D20..0x455E76): in use, under 14, alive, not sick, hands empty. */
static int old_tag_player(const old_game *g, const unsigned char *r) {
    return r[g->in_use] != 0 && *(const int *)(r + g->age) < CP_CHILD_AGE && *(const int *)(r + g->health) > 0
           && *(const int *)(r + g->sick) == 0 && *(const int *)(r + g->carried) == g->nothing;
}

/* A New Home's tag (the port of The Lost Children's 0x455CF0). 1 when it was started. */
static int vv1_tag(unsigned char *array, int starter) {
    const old_game *g = &VV1;
    int i, players = 0;
    for (i = 0; i < g->count; ++i) {
        players += old_tag_player(g, old_record(g, array, i));
    }
    if (players < 2) {
        return 0;
    }
    for (i = 0; i < g->count; ++i) {
        unsigned char *r = old_record(g, array, i);
        int round;
        if (i != starter && !old_tag_player(g, r)) {
            continue;
        }
        ((tc1_fn)g->stop)(array, NULL, i);
        if (i == starter) {
            put_text(r + g->text, "vvfp.children_play/vvfp_children_play.IT_WORDS.s0", IT_WORDS);
        } else {
            put_text(r + g->text, "vvfp.children_play/vvfp_children_play.TAG_WORDS.s0", TAG_WORDS);
        }
        for (round = 0; round < 4; ++round) {
            old_queue(g, array, i, 3, in_range(845, 120), in_range(659, 120), 0, CP_TAG_SPEED);
            old_queue(g, array, i, 5, 0, 0, in_range(10, 4), 0);
        }
    }
    return 1;
}

typedef struct place {
    int x_base, x_spread, x_times, y_base, y_spread, y_times;
} place;

/* A New Home: three stock "Cleaning up the beach" places (0x444690: x = 3 (base + rand), y likewise), the
   south shore at the water. */
static const place VV1_BEACH[3] = {
    { 0xA0, 0x26, 3, 0x1F5, 0x13, 3 },   /* 480..591 by 1503..1557 (0x44478D) */
    { 0xC8, 0x26, 3, 0x1FE, 0x1D, 3 },   /* 600..711 by 1530..1614 (0x4447BB) */
    { 0x7B, 0x26, 3, 0x1E4, 0x1E, 3 },   /* 369..480 by 1452..1539 (0x4446ED) */
};
/* The Lost Children: the three stock "Relaxing at the beach" places nearest the sea (0x451E10: base + rand % 40),
   the west shore. */
static const place VV2_BEACH[3] = {
    { 0xD9, 40, 1, 0x36E, 40, 1 },       /* 217..256 by 878..917 (0x451F48) */
    { 0x8E, 40, 1, 0x36E, 40, 1 },       /* 142..181 by 878..917 (0x451FC6) */
    { 0x91, 40, 1, 0x2F0, 40, 1 },       /* 145..184 by 752..791 (0x452008) */
};

/* Sandcastles in A New Home and The Lost Children (the port of The Secret City's 0x44DE40). */
static void old_sandcastles(const old_game *g, const place *beach, const char *stem, unsigned char *array, int i) {
    const place *at = &beach[game_rand(3)];
    unsigned char *r = old_record(g, array, i);
    int round;
    put_text(r + g->text, stem, SAND_WORDS);
    for (round = 0; round < 6; ++round) {
        int y = in_range(at->y_base, at->y_spread) * at->y_times;
        int x = in_range(at->x_base, at->x_spread) * at->x_times;
        old_queue(g, array, i, 3, x, y, 0, CP_WALK_SPEED);
        if (game_rand(100) < 20) {
            old_queue(g, array, i, 2, 0, 0, in_range(5, 10), 0);
        }
        old_queue(g, array, i, 2, 0, 0, in_range(10, 20), 1);
        old_queue(g, array, i, 2, 0, 0, in_range(10, 20), 1);
    }
}

/* ---- The Secret City and The Tree of Life: tag through the game's own actions ---------------------------------- */

typedef struct new_game {
    UINT_PTR strings, lookup, copy, stop, act, walk, last, start;
    int running, tag_id, it_id;
    unsigned int text, in_use, health, age, sick, carried, dislike, chief, corpse;
    unsigned int stride, records_from;   /* records = manager + records_from */
} new_game;

static const new_game VV3 = { 0x42F740u, 0x42F190u, 0x46F780u, 0x460F70u, 0x455570u, 0x4611B0u, 0x461B50u, 0x461BF0u,
                              0x94, 0x190, 0x191,
                              0xF28u, 0xF10u, 0xE78u, 0xDC4u, 0xE89u, 0xF20u, 0xFC0u, 0xE80u, 0u,
                              0x1F8Cu, 0x14u };
static const new_game VV4 = { 0x44DA20u, 0x44D3D0u, 0x4724E0u, 0x468C60u, 0x45DEC0u, 0x469050u, 0x469EC0u, 0x46A030u,
                              0x46, 0x1EB, 0x1EC,
                              0x1CE4u, 0x1CC4u, 0x1C40u, 0x1B8Cu, 0x1C48u, 0x1CDCu, 0x1E6Cu, 0u, 0x1CC7u,
                              0x2E3Cu, 0x44u };

/* The six places of "Running around" (The Secret City 0x4444B0, The Tree of Life 0x450F10: the same six). */
static const place RUNNING[6] = {
    { 0x3B4, 0x20, 1, 0x3B8, 0x20, 1 }, { 0x2F5, 0x1E, 1, 0x3C5, 0x20, 1 }, { 0x2CB, 0x1E, 1, 0x428, 0x20, 1 },
    { 0x3A4, 0x22, 1, 0x4AD, 0x24, 1 }, { 0x41C, 0x24, 1, 0x428, 0x24, 1 }, { 0x3DA, 0x24, 1, 0x3EB, 0x26, 1 },
};

static void new_table(const new_game *g, unsigned char **records, int *count) {
    unsigned int rva, slots;
    if (g == &VV3) {
        vv3_villager_table((const unsigned char *)(UINT_PTR)0x400000u, &rva, &slots);
    } else {
        vv4_villager_table((const unsigned char *)(UINT_PTR)0x400000u, &rva, &slots);
    }
    *records = (unsigned char *)(UINT_PTR)(0x400000u + rva + g->records_from);
    *count = (int)slots;
}

static int new_tag_player(const new_game *g, const unsigned char *r) {
    return r[g->in_use] != 0 && (g->corpse == 0 || r[g->corpse] == 0) && *(const int *)(r + g->health) > 0
           && *(const int *)(r + g->age) < CP_CHILD_AGE && r[g->sick] == 0 && *(const int *)(r + g->carried) == -1
           && !dislikes(r + g->dislike, 3, CP_PLAYING) && (g->chief == 0 || r[g->chief] == 0);
}

static void new_stop(const new_game *g, unsigned char *r) {
    if (g == &VV3) {
        ((tc1_fn)g->stop)(r, NULL, (int)(UINT_PTR)r);
    } else {
        ((pick0_fn)g->stop)(r, NULL);
    }
}

static void new_player(const new_game *g, unsigned char *r, int it, const int *order) {
    int block[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
    void *strings;
    const char *words;
    int k;
    new_stop(g, r);
    ((tc2_fn)g->act)(r, NULL, g->running, (int)(UINT_PTR)block);
    new_stop(g, r);
    strings = ((getter_fn)g->strings)();
    words = (const char *)((tc1_fn)g->lookup)(strings, NULL, it ? g->it_id : g->tag_id);
    if (words != NULL) {
        ((copy_fn)g->copy)((char *)(r + g->text), words, 0x27);
    }
    for (k = 0; k < 6; ++k) {
        const place *at = &RUNNING[order[k]];
        int y = in_range(at->y_base, at->y_spread);
        int x = in_range(at->x_base, at->x_spread);
        ((tc4_fn)g->walk)(r, NULL, x, y, CP_TAG_SPEED, 0);
    }
    if (g == &VV3) {
        ((tc4_fn)g->last)(r, NULL, 1, 0, 1, 0);
        ((tc1_fn)g->start)(r, NULL, (int)(UINT_PTR)r);
    } else {
        ((tc4_fn)g->last)(r, NULL, 1, 4, 1, 0);
        ((pick0_fn)g->start)(r, NULL);
    }
}

/* Tag in The Secret City and The Tree of Life (The Lost Children's rule; see the top). 1 when it was started. */
static int new_tag(const new_game *g, unsigned char *starter) {
    unsigned char *records;
    int count, i, players = 0, order[6];
    new_table(g, &records, &count);
    for (i = 0; i < count; ++i) {
        players += new_tag_player(g, records + (size_t)i * g->stride);
    }
    if (players < 2) {
        return 0;
    }
    for (i = 0; i < 6; ++i) {
        order[i] = i;
    }
    for (i = 5; i > 0; --i) {
        int j = game_rand(i + 1), t = order[i];
        order[i] = order[j];
        order[j] = t;
    }
    new_player(g, starter, 1, order);
    for (i = 0; i < count; ++i) {
        unsigned char *r = records + (size_t)i * g->stride;
        if (r != starter && new_tag_player(g, r)) {
            new_player(g, r, 0, order);
        }
    }
    return 1;
}

/* ---- New Believers: its own tag slot, without the 5% roll (0x46E705..0x46E769) --------------------------------- */

static int vv5_tag(unsigned char *record) {
    unsigned int rva, slots;
    unsigned char *manager;
    int children, joined = 0;
    unsigned char flag = 0;
    vv5_villager_table((const unsigned char *)(UINT_PTR)0x400000u, &rva, &slots);
    manager = (unsigned char *)(UINT_PTR)(0x400000u + rva);
    children = ((pick0_fn)0x471450u)(manager, NULL);
    ((tc8_fn)0x4710B0u)(manager, NULL, 0xEE, 0x50, 0, 0x117, -1, (int)(UINT_PTR)&joined, 2, children * 75 / 100);
    if (joined > 1) {
        ((tc2_fn)0x465580u)(record, NULL, 0xEE, (int)(UINT_PTR)&flag);
    }
    return 1;
}

/* ---- the pick -------------------------------------------------------------------------------------------------- */

/* A New Home, The Lost Children, The Secret City: thiscall (array or queue, index or record), ret 4. */
static int __fastcall pick1(void *self, void *edx, int arg) {
    int slot;
    (void)edx;
    if (g_game == 1) {
        unsigned char *r = old_record(&VV1, (unsigned char *)self, arg);
        if (*(const int *)(r + 0x36C) != 0xC7) {          /* the Golden Child: his own branch */
            slot = game_rand(CP_SLOTS);
            if (slot == CP_SLOT_TAG && vv1_tag((unsigned char *)self, arg)) {
                return 1;
            }
            if (slot == CP_SLOT_SAND) {
                old_sandcastles(&VV1, VV1_BEACH, "vvfp.children_play/vvfp_children_play.SAND_WORDS.s0",
                                (unsigned char *)self, arg);
                return 1;
            }
        }
    } else if (g_game == 2) {
        unsigned char *r = old_record(&VV2, (unsigned char *)self, arg);
        if (!dislikes(r + 0x6E8, 62, CP_PLAYING)) {
            slot = game_rand(CP_SLOTS);
            if (slot == CP_SLOT_TAG) {
                ((tc1_fn)0x455CF0u)(self, NULL, arg);
                return 1;
            }
            if (slot == CP_SLOT_SAND) {
                old_sandcastles(&VV2, VV2_BEACH, "vvfp.children_play/vvfp_children_play.SAND_WORDS.s0",
                                (unsigned char *)self, arg);
                return 1;
            }
        }
    } else if (g_game == 3) {
        unsigned char *r = (unsigned char *)(UINT_PTR)arg;
        if (!dislikes(r + VV3.dislike, 3, CP_PLAYING) && game_rand(CP_SLOTS) == CP_SLOT_TAG && new_tag(&VV3, r)) {
            return 1;
        }
    }
    return ((pick1_fn)g_stock_pick)(self, NULL, arg);
}

/* The Tree of Life, New Believers: thiscall (the villager's AI, whose +0x1B88 is the record), no arguments. */
static int __fastcall pick0(void *self, void *edx) {
    unsigned char *r = *(unsigned char **)((unsigned char *)self + 0x1B88);
    (void)edx;
    if (g_game == 4) {
        if (!dislikes(r + VV4.dislike, 3, CP_PLAYING) && game_rand(CP_SLOTS) == CP_SLOT_TAG && new_tag(&VV4, r)) {
            return 1;
        }
    } else if (g_game == 5) {
        if (!dislikes(r + 0x1F68, 3, CP_PLAYING) && game_rand(CP_SLOTS) == CP_SLOT_TAG) {
            return vv5_tag(r);
        }
    }
    return ((pick0_fn)g_stock_pick)(self, NULL);
}

/* ---- install --------------------------------------------------------------------------------------------------- */

/* 1 when the calls are pointed at the pick (for the tests' emulation), else 0. */
int __stdcall VvfpChildrenPlayInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static const unsigned int SITES[6][3] = {
        { 0, 0, 0 }, { 0x448299u, 0, 0 }, { 0x4618C9u, 0, 0 }, { 0x45C16Au, 0x45BDC9u, 0x4269C9u },
        { 0x4658D7u, 0, 0 }, { 0x46F125u, 0, 0 },
    };
    static const UINT_PTR STOCK[6] = { 0, 0x4479B0u, 0x45EE00u, 0x45B9B0u, 0x465260u, 0x46E3F0u };
    vvfp_site_write sites[3];
    int n = 0, i;
    (void)shipped;
    if (g_installed || game < 1 || game > 5) {
        return;
    }
    for (i = 0; i < 3 && SITES[game][i] != 0; ++i) {
        unsigned int va = SITES[game][i];
        unsigned int rel = (unsigned int)(STOCK[game] - (va + 5u));
        g_expect[i][0] = 0xE8;
        memcpy(g_expect[i] + 1, &rel, 4);
        vvfp_site_branch(&sites[i], va, 5, g_expect[i], 0xE8,
                         game >= 4 ? (const void *)pick0 : (const void *)pick1);
        ++n;
    }
    g_game = game;
    g_stock_pick = STOCK[game];
    if (vvfp_install_sites(sites, n)) {
        g_installed = 1;
    } else {
        g_game = 0;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
