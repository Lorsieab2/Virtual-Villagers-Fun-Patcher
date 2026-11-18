/* VVFP Work First -- Builders and Healers Work First, upgraded to skill
   practice (all five games).

   An addendum to Builders Fix Huts When Idle.  The owner first asked for
   builders and healers to do their own work first, at any food level; the
   skill-practice upgrade (v1.35.97, the owner's decisions of 2026-11-17 on
   "Skill Practice - Behaviors to Approve") extends it so villagers practise
   their SELECTED job on their own: farmers, researchers, healers, builders
   and (New Believers) devotees.  Parenting stays under the Birth Control
   patches and is never put first.

   HOW.  Every game's adult idle scheduler -- and its catch-up worker -- asks
   one work dispatcher to start a job for the villager ("dispatch job N; true
   if something started").  For the scheduler's and the worker's own calls,
   on the decision's roll (about three times in four, shared with Builders
   Fix Huts When Idle), this companion first asks the dispatcher for the
   villager's own selected job; if that starts something, the caller sees
   "started".  If it starts nothing, a builder in The Secret City, The Tree of
   Life and New Believers may do the game's own "Doing exercise" (Building
   practice), and a healer in A New Home and The Lost Children whose village
   has solved Herb Mastery may study one of the understood plants (Healing
   practice); otherwise the caller's own request runs exactly as it would have.
   Whatever the work does -- which project, which crop, which patient -- is
   the game's own dispatcher's choice.

     game  dispatcher  displaced                      adult-scheduler returns         selected job             Farm Par Heal Res Bld
     VV1   0x4472C0    mov eax,[esp+8]; test eax,eax  0x448355 0x448382               village+i*0x3D8+0x3D0     1    2   5    3   4
     VV2   0x45FBF0    the same                       0x461A08 0x461A35               village+i*0xE48C+0x7F8    1    2   3    4   5
     VV3   0x45AF00    mov eax,[esp+8]; sub esp,0xA0  0x45C23C 0x45C27A 0x45C28F      record+0xEC0              0    1   2    3   4
     VV4   0x4639B0    mov eax,[esp+4]; sub esp,0x98  0x4659D2 0x465A17 0x465A2A      [obj+0x1B88]+0x1C70       0    1   2    3   4
     VV5   0x46C540    sub esp,0x94                   0x46F291 0x46F2D6 0x46F2EA      [obj+0x1B88]+0x1C74       0    1   2    3   4  (Devotion 5)

   WHO IS PUT FIRST.
   * Healing and Farming: always (whether there is anything to do is the
     dispatcher's decision).  A New Home's Farming case returns "started"
     having started nothing at Farming level 1 with nothing to forage, so
     there a farmer is put first only when the case would start something.
   * Research: always, except that it never displaces a Farming request (the
     low-food farming attempt of the later games' scheduler, or any Farming
     pick) -- researchers never take food work away from the village.
   * Building: builders never START a project the player never dropped anyone
     on (the owner's rule); they may continue one in progress.
       - A New Home / The Lost Children: only while the builder has hut work
         (as before), and never while the stock Building case could start a
         population hut nobody has worked on (A New Home: hut 9 any time, huts
         10/11 above 22/45 villagers; The Lost Children: hut 24), whose
         progress is below 2 -- the village drawing routine marks a scaffold
         with progress 1.
       - The Secret City / New Believers: always; their Building cases only
         continue projects above 0%.
       - The Tree of Life: always, except while the Building case would offer
         puzzle work it can start on its own: the stream before The Stream is
         solved (the owner: keeping the stream clear only once it has been
         cleared), the piers before Fishing Nets, the rubble before the
         Cooking Pit.
   * Devotion (New Believers): in catch-up always (as before); while you play
     only when Easier Devotee Training is not in the executable, so the two
     never double up.
   * Parenting: never.

   THE FALLBACKS (only after the own job started nothing).
   * Exercise (The Secret City, The Tree of Life, New Believers; the owner's
     items 56, 77, 92): a builder whose Building work started nothing does the
     game's own "Doing exercise" (do-action 0x96 / 0x47 / 0x4E), whose step
     raises Building through the standard practice roll -- above 250 food only
     (at 250 or less the village needs its farmers), and only when the
     dispatch left the villager's current action unchanged.
   * Plants (A New Home, The Lost Children; the owner's items 15, 39-41):
     once Herb Mastery is solved (A New Home [state+0xA080], The Lost Children
     [state+0x2E788]) a healer whose Healing work started nothing studies a
     random understood plant -- A New Home's medical cactus, rare rose,
     strange lily and strange plant (never the Magic Plant of Life), The Lost
     Children's six -- through the game's own study starter, whose re-study
     step is the Healing practice roll.  A villager the game would send
     "Running away" from a plant (trait 0xB, the drop's own test) is never
     sent to it.  In A New Home a villager whose last activity is 9 (the
     cactus: the Healing case started it and reports "nothing") is left alone.

   THE OTHER SITES (runtime detours, all-or-none with the dispatcher hook).
   * The Tree of Life / New Believers, beginners (items 1, 2): the job picker
     never sends a villager to a job whose skill is 5 or less (VV4 0x461E69,
     VV5 0x46A594: cmp esi,5; jle fail).  For the villager's SELECTED job
     (never Parenting), on the decision's roll, the gate lets the pick through
     to the game's own roll, rand(100) < skill + 40.
   * New Believers, "untrained" (item 3): every new villager starts with
     [record+0x1C54] = 1, and the dispatcher refuses every job while it is 1
     (0x46C565).  For the scheduler's and catch-up's calls, a request for the
     villager's selected job (never Parenting) is dispatched with the mark
     lifted for that one call and put back afterwards (a refusal inside the
     call writes 0, which would otherwise train them for everything).
   * The Tree of Life, the fruit trip in catch-up (item 84): the Farming case
     offers "Attempting to retrieve fruit" only while not catching up
     (0x463A30: cmp byte [game+0x171A4], bl; jne).  In catch-up a villager
     whose selected job is Farming is offered it too, on the decision's roll.
   * New Believers, noni in catch-up before the Hungry Totem (item 101): the
     same test at 0x46C5CA ([game+0x17E10]); a selected farmer is offered noni
     in catch-up on the decision's roll, as a dropped farmer already is.
   * The Lost Children, examining the sewing hut (item 30): the Building
     case's examine pick (0x4602B0: push 4; call rand) chooses among the three
     population huts and the hospital; once the sewing hut is finished
     ([state+0x2E790]), on the decision's roll and one time in five, it
     examines the sewing hut instead (0x45F7C0(index, 7), the drop's own
     call).

   CATCH-UP.  Time passing while the game was closed, and Time Warp, never
   run the idle scheduler: each game's catch-up worker takes the stock
   picker's job and dispatches it itself.  That pick dispatch (VV1 0x42E821,
   VV2 0x43B588, VV3 0x45BFC5, VV4 0x46582C, VV5 0x46E9CE returns) is one of
   the calls above, so everything here acts in catch-up too.  The worker's
   other branch, `cmp pick, Parenting; jne` (VV1/VV2 job 2, VV3-VV5 job 1),
   is the Parenting pick: 5% of the time a catch-up conception attempt.  An
   earlier version of this companion hooked it as "research" and gave
   builders and healers their own job instead; that took catch-up mating
   away from the Birth Control patches, so it is no longer hooked.  The
   worker's low-food Farming dispatch (VV3 0x45BFB0, VV4 0x46580F, VV5
   0x46E9B1) is not one of the calls: Farming still wins there.

   Loaded by "VVFP Fix Huts.dll" (VvfpFixHutsInstall, from a companion that
   runs every frame) by full path; The Secret City's hook is a stub in the
   fix-huts page that resolves VvfpWorkFirstFirst.  Not shipped: nothing is
   loaded, and every hook falls through to the stock code. */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include <intrin.h>
#include "../shared/install_sites.h"    /* every site written, or none */

/* ---- Calling the game ----------------------------------------------------- */
static unsigned int tc0(unsigned int fn, unsigned int self) {
    unsigned int r;
    __asm {
        mov ecx, self
        mov eax, fn
        call eax
        mov r, eax
    }
    return r;
}

static unsigned int tc1(unsigned int fn, unsigned int self, unsigned int a) {
    unsigned int r;
    __asm {
        mov ecx, self
        mov eax, fn
        push a
        call eax
        mov r, eax
    }
    return r;
}

static unsigned int tc2(unsigned int fn, unsigned int self, unsigned int a, unsigned int b) {
    unsigned int r;
    __asm {
        mov ecx, self
        mov eax, fn
        push b
        push a
        call eax
        mov r, eax
    }
    return r;
}

/* ---- Population huts ------------------------------------------------------ */
/* The same tests the fix-huts companion makes (native/vvfp_fix_huts). */
static int vv1_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    return !(state[0x9FE8] == 1 && state[0x9FF0] == 1 && state[0x9FF8] == 1);
}

static int vv2_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    return !(state[0x2E818] == 1 && state[0x2E820] == 1 && state[0x2E828] == 1);
}

/* A New Home / The Lost Children: a builder has hut work while a population
   hut is unbuilt, or -- below Building level 3, where the owner wants
   builders to fix huts "if at least one is built" -- whenever one is built
   (Codex on #464). */
static int vv1_builder_has_hut_work(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    if (vv1_huts_incomplete(village)) return 1;
    return *(const int *)(state + 0xA2CC) < 3
        && (state[0x9FE8] == 1 || state[0x9FF0] == 1 || state[0x9FF8] == 1);
}

static int vv2_builder_has_hut_work(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    if (vv2_huts_incomplete(village)) return 1;
    return *(const int *)(state + 0x2EA84) < 3
        && (state[0x2E818] == 1 || state[0x2E820] == 1 || state[0x2E828] == 1);
}

/* Builders never start a project nobody was dropped on.  A New Home's stock
   Building case (0x447528) builds hut 9 whenever it is not done and huts 10 /
   11 above 22 / 45 villagers (population 0x41CF90, thiscall on the state),
   whatever their progress; a hut a player has worked on has progress 2 or
   more (the drawing routine writes 1 for a shown scaffold).  progress(id) =
   [state+0x9F9C+8*id], done = the byte 4 later. */
#define VV1_POPULATION 0x41CF90u
static int vv1_fresh_hut_on_offer(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    int population = -1;
    unsigned int id;
    for (id = 9; id <= 11; ++id) {
        const int progress = *(const int *)(state + 0x9F9Cu + 8u * id);
        if (state[0x9FA0u + 8u * id] == 1 || progress >= 2) continue;
        if (id == 9) return 1;
        if (population < 0) population = (int)tc0(VV1_POPULATION, (unsigned int)(uintptr_t)state);
        if (population > (id == 10 ? 22 : 45)) return 1;
    }
    return 0;
}

/* The Lost Children's stock Building case starts hut 24 whenever it is not
   done (0x4600D2), whatever its progress [state+0x2E814]; huts 25 / 26 and
   every other project need progress 2 or more already. */
static int vv2_fresh_hut_on_offer(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    return state[0x2E818] != 1 && *(const int *)(state + 0x2E814) < 2;
}

struct later_game {
    unsigned int complete_fn;      /* __stdcall(int) -> al, ecx = complete_obj */
    unsigned int complete_obj;
    int project_base;
};
static const struct later_game VV4 = { 0x438960u, 0x4D8BF8u, 19 };

static int project_done(const struct later_game *g, int project) {
    return (tc1(g->complete_fn, g->complete_obj, (unsigned int)project) & 0xFFu) != 0;
}

/* The Tree of Life's Building case (0x463C1C) offers puzzle work it can start
   on its own: the stream (option 5, obstruction 0x430FD0 on 0x4D8CF0 between
   1 and 97), the piers (option 6: stage 0x4396D0 on 0x4D86A8 below 2 and
   0x421570 below 100) and the rubble (option 7: stage 0x4396D0 on 0x4D8720
   at 0 and [0x4D8A8C] below 100).  The stream counts only until The Stream
   (project 1) is solved: after that, keeping it clear is building practice
   (the owner's item 73). */
static int vv4_puzzle_on_offer(void) {
    int obstruction = (int)tc0(0x430FD0u, 0x4D8CF0u);
    if (obstruction > 0 && obstruction < 0x62 && !project_done(&VV4, 1)) return 1;
    if ((int)tc0(0x4396D0u, 0x4D86A8u) < 2 && (int)tc0(0x421570u, 0x4D86A8u) < 100) return 1;
    if ((int)tc0(0x4396D0u, 0x4D8720u) == 0 && *(const int *)(uintptr_t)0x4D8A8Cu < 100) return 1;
    return 0;
}

/* ---- About three times in four ------------------------------------------------ */
/* The owner: the behaviour patches "should increase the LIKELIHOOD of
   villagers doing that action, not 100% replace them" -- 75%, one roll per
   decision shared by every patch in it.  The decision and its roll belong to
   "VVFP Fix Huts.dll", which wraps each game's idle scheduler and catch-up
   worker and hands this companion its VvfpFixHutsRoll through
   VvfpWorkFirstSetRoll before installing it; in The Secret City, where the
   fix-huts page stub loads that DLL, the export is looked up by module name.
   If the fix-huts DLL cannot be found at all (it loads this one, so that
   does not happen in play) each ask draws a 75% roll of this companion's
   own. */
static int (__cdecl *shared_roll)(void);
static int shared_roll_state;          /* 0 = not looked up, 1 = found, -1 = absent */
static unsigned int own_roll_state;

#ifdef VVFP_TEST
/* force: 0 = the real own roll, 1 = pass, 2 = fail; draws: own rolls drawn.
   TEST build only. */
struct vvfp_own_roll_test { int force; int draws; };
__declspec(dllexport) struct vvfp_own_roll_test VvfpWorkFirstRollTest = { 0, 0 };
#endif

__declspec(dllexport) void __stdcall VvfpWorkFirstSetRoll(int (__cdecl *roll)(void)) {
    shared_roll = roll;
    shared_roll_state = roll != NULL ? 1 : 0;
}

static unsigned int next_random(void) {
    unsigned int x = own_roll_state;
    if (x == 0) {
        x = (unsigned int)__rdtsc() ^ 0x2545F491u;
        if (x == 0) x = 0x2545F491u;
    }
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    own_roll_state = x;
    return x;
}

static int own_roll(void) {
    unsigned int x = next_random();
#ifdef VVFP_TEST
    ++VvfpWorkFirstRollTest.draws;
    if (VvfpWorkFirstRollTest.force == 1) return 1;
    if (VvfpWorkFirstRollTest.force == 2) return 0;
#endif
    return x % 100u < 75u;
}

static int decision_roll(void) {
    if (shared_roll_state == 0) {
        HMODULE fix_huts = GetModuleHandleA("VVFP Fix Huts.dll");
        shared_roll = fix_huts != NULL
            ? (int (__cdecl *)(void))GetProcAddress(fix_huts, "VvfpFixHutsRoll") : NULL;
        shared_roll_state = shared_roll != NULL ? 1 : -1;
    }
    return shared_roll_state == 1 ? shared_roll() : own_roll();
}

/* ---- Counters the tests read ------------------------------------------------ */
/* Compiled only into the TEST build (VVFP_TEST, tests/test_dlls/): the
   shipped DLL carries no counters and no probe.  pick: the random index the
   next plant choice uses (-1: the real random). */
#ifdef VVFP_TEST
struct vvfp_work_first_stats {
    int tried;          /* the villager's own job was tried first */
    int started;        /* ... and started something */
    int exercised;      /* the exercise fallback started */
    int studied;        /* the plant fallback started */
    int pick;           /* forced random pick, or -1 */
};
__declspec(dllexport) struct vvfp_work_first_stats VvfpWorkFirstStats = { 0, 0, 0, 0, -1 };
#define COUNT(field) (++VvfpWorkFirstStats.field)
static unsigned int pick_index(unsigned int n) {
    if (VvfpWorkFirstStats.pick >= 0) return (unsigned int)VvfpWorkFirstStats.pick % n;
    return next_random() % n;
}
#else
#define COUNT(field) ((void)0)
static unsigned int pick_index(unsigned int n) {
    return next_random() % n;
}
#endif

/* ---- The decision ---------------------------------------------------------- */
struct jobs {
    int farming, parenting, healing, research, building, devotion;
};
static const struct jobs VV1_JOBS = { 1, 2, 5, 3, 4, -1 };
static const struct jobs VV2_JOBS = { 1, 2, 3, 4, 5, -1 };
static const struct jobs LATER_JOBS = { 0, 1, 2, 3, 4, -1 };
static const struct jobs VV5_JOBS = { 0, 1, 2, 3, 4, 5 };

/* The villager's own job to try first, or -1: the caller's request alone.
   building_ok / devotion_ok / farming_ok: whether that job may be put first
   now (see WHO IS PUT FIRST).  The roll is asked only when the companion
   would act. */
static int own_first(const struct jobs *j, int selected, int requested,
                     int building_ok, int devotion_ok, int farming_ok) {
    if (selected < 0 || selected == requested || selected == j->parenting) {
        return -1;
    }
    if (selected == j->building) {
        if (!building_ok) return -1;
    } else if (selected == j->devotion) {
        if (!devotion_ok) return -1;
    } else if (selected == j->research) {
        if (requested == j->farming) return -1;
    } else if (selected == j->farming) {
        if (!farming_ok) return -1;
    } else if (selected != j->healing) {
        return -1;
    }
    if (!decision_roll()) {
        return -1;
    }
    COUNT(tried);
    return selected;
}

/* The later games' builders asked for Building already (the picker's usual
   answer): on the decision's roll the request is dispatched here, so that if
   it starts nothing the exercise fallback can follow; -1 = the stock request
   alone (roll failed), -2 = not this case (ask own_first). */
static int builder_asked(const struct jobs *j, int selected, int requested) {
    if (selected != j->building || requested != j->building) {
        return -2;
    }
    if (!decision_roll()) {
        return -1;
    }
    COUNT(tried);
    return selected;
}

static int is_one_of(unsigned int ret, const unsigned int *sites, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        if (ret == sites[i]) return 1;
    }
    return 0;
}

/* The adult scheduler's calls, then the catch-up worker's pick dispatch.
   The worker's low-food Farming dispatch in VV3-VV5 is deliberately absent. */
static const unsigned int VV1_CALLS[] = { 0x448355u, 0x448382u, 0x42E821u };
static const unsigned int VV2_CALLS[] = { 0x461A08u, 0x461A35u, 0x43B588u };
static const unsigned int VV3_CALLS[] = { 0x45C23Cu, 0x45C27Au, 0x45C28Fu, 0x45BFC5u };
static const unsigned int VV4_CALLS[] = { 0x4659D2u, 0x465A17u, 0x465A2Au, 0x46582Cu };
static const unsigned int VV5_CALLS[] = { 0x46F291u, 0x46F2D6u, 0x46F2EAu, 0x46E9CEu };
#define VV5_CATCH_UP_CALL 0x46E9CEu

/* Easier Devotee Training replaces New Believers' scheduler test at 0x46F1DD;
   while it is there the live scheduler leaves devotees to it. */
static const unsigned char VV5_EDT_STOCK[9] = { 0x83, 0xB9, 0xFC, 0x1C, 0x00, 0x00, 0x0D, 0x75, 0x54 };
static int vv5_devotee_training_present(void) {
    return !vvfp_site_holds(0x46F1DDu, VV5_EDT_STOCK, sizeof VV5_EDT_STOCK);
}

/* A New Home's Farming case (0x4472E5) returns "started" having started
   nothing at Farming level 1 with nothing to forage ([state+0xA2F4] <= 0)
   or at a level outside 1-3. */
static int vv1_farming_starts(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    const int level = *(const int *)(state + 0xA2E4);
    if (level == 2 || level == 3) return 1;
    return level == 1 && *(const int *)(state + 0xA2F4) > 0;
}

/* ---- The plants (A New Home, The Lost Children) ---------------------------- */
struct plant { unsigned int starter; unsigned int flag; int trait_check; };
/* A New Home: medical cactus, rare rose, strange lily, strange plant.  The
   Magic Plant of Life ("Studying fruitless plant", 0x443030) is never here. */
static const struct plant VV1_PLANTS[4] = {
    { 0x443270u, 0xA068u, 0 }, { 0x4435B0u, 0xA060u, 1 },
    { 0x443440u, 0xA070u, 1 }, { 0x443720u, 0xA078u, 1 },
};
/* The Lost Children: herbs 1-6; the drop refuses all six for trait 0xB. */
static const struct plant VV2_PLANTS[6] = {
    { 0x458CD0u, 0x2E860u, 1 }, { 0x4589A0u, 0x2E868u, 1 }, { 0x458B70u, 0x2E870u, 1 },
    { 0x458E30u, 0x2E878u, 1 }, { 0x458FD0u, 0x2E880u, 1 }, { 0x459130u, 0x2E888u, 1 },
};

/* Start a random understood plant for the villager; 1 when started.
   has_trait: the game's trait test (thiscall(index, trait) on the village). */
static int study_a_plant(unsigned char *village, unsigned int index, const unsigned char *state,
                         const struct plant *plants, unsigned int count, unsigned int has_trait) {
    unsigned int ok[6];
    unsigned int n = 0, i;
    int refuses = -1;
    for (i = 0; i < count; ++i) {
        if (state[plants[i].flag] == 0) continue;
        if (plants[i].trait_check) {
            if (refuses < 0) {
                refuses = (int)(tc2(has_trait, (unsigned int)(uintptr_t)village, index, 0xB) & 0xFFu) != 0;
            }
            if (refuses) continue;
        }
        ok[n++] = plants[i].starter;
    }
    if (n == 0) return 0;
    tc1(ok[pick_index(n)], (unsigned int)(uintptr_t)village, index);
    COUNT(studied);
    return 1;
}

static int vv1_plant_fallback(unsigned char *village, unsigned int index) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    if (state[0xA080] == 0) return 0;                                       /* Herb Mastery */
    if (*(const int *)(village + index * 0x3D8u + 0x3B8u) == 9) return 0;  /* the cactus runs */
    return study_a_plant(village, index, state, VV1_PLANTS, 4, 0x4372E0u);
}

static int vv2_plant_fallback(unsigned char *village, unsigned int index) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    if (state[0x2E788] == 0) return 0;                                      /* Herb Mastery */
    return study_a_plant(village, index, state, VV2_PLANTS, 6, 0x4454E0u);
}

/* ---- Exercise (The Secret City, The Tree of Life, New Believers) ----------- */
struct exercise {
    unsigned int do_action;        /* thiscall(action, args) on the record, ret 8 */
    unsigned int action;
    unsigned int food;             /* the village's food total */
    unsigned int current;          /* the record's current action */
};
static const struct exercise VV3_EXERCISE = { 0x455570u, 0x96u, 0x582490u, 0xF24u };
static const struct exercise VV4_EXERCISE = { 0x45DEC0u, 0x47u, 0x4D6DD0u, 0x1CE0u };
static const struct exercise VV5_EXERCISE = { 0x465580u, 0x4Eu, 0x51D34Cu, 0x1D10u };

static int exercise(const struct exercise *e, unsigned char *record, int action_before) {
    unsigned char args[0x58];
    if (*(const int *)(uintptr_t)e->food <= 250) return 0;
    if (*(const int *)(record + e->current) != action_before) return 0;
    memset(args, 0, sizeof args);
    tc2(e->do_action, (unsigned int)(uintptr_t)record, e->action, (unsigned int)(uintptr_t)args);
    COUNT(exercised);
    return 1;
}

/* ---- The stock dispatchers, callable --------------------------------------- */
#define VV1_DISPATCHER 0x4472C0u
#define VV2_DISPATCHER 0x45FBF0u
#define VV3_DISPATCHER 0x45AF00u
#define VV4_DISPATCHER 0x4639B0u
#define VV5_DISPATCHER 0x46C540u
static const unsigned char VV1_STOCK[6] = { 0x8B, 0x44, 0x24, 0x08, 0x85, 0xC0 };
static const unsigned char VV2_STOCK[6] = { 0x8B, 0x44, 0x24, 0x08, 0x85, 0xC0 };
static const unsigned char VV4_STOCK[10] = { 0x8B, 0x44, 0x24, 0x04, 0x81, 0xEC, 0x98, 0x00, 0x00, 0x00 };
static const unsigned char VV5_STOCK[6] = { 0x81, 0xEC, 0x94, 0x00, 0x00, 0x00 };
static const unsigned int vv1_body = VV1_DISPATCHER + 6, vv2_body = VV2_DISPATCHER + 6;
static const unsigned int vv4_body = VV4_DISPATCHER + 10, vv5_body = VV5_DISPATCHER + 6;

/* The displaced bytes, then the body: the stock dispatcher, bypassing the
   hook.  Also the target when the caller's request should simply run. */
static __declspec(naked) void vv1_original(void) {
    __asm {
        mov eax, dword ptr [esp + 8]
        test eax, eax
        jmp dword ptr [vv1_body]
    }
}
static __declspec(naked) void vv2_original(void) {
    __asm {
        mov eax, dword ptr [esp + 8]
        test eax, eax
        jmp dword ptr [vv2_body]
    }
}
static __declspec(naked) void vv4_original(void) {
    __asm {
        mov eax, dword ptr [esp + 4]
        sub esp, 0x98
        jmp dword ptr [vv4_body]
    }
}
static __declspec(naked) void vv5_original(void) {
    __asm {
        sub esp, 0x94
        jmp dword ptr [vv5_body]
    }
}

static int dispatch12(void (*original)(void), unsigned char *village, unsigned int index, int job) {
    int started = (tc2((unsigned int)(uintptr_t)original, (unsigned int)(uintptr_t)village, index,
                       (unsigned int)job) & 0xFFu) != 0;
    if (started) COUNT(started);
    return started;
}

static int dispatch_later(void (*original)(void), unsigned char *object, int job) {
    return (tc1((unsigned int)(uintptr_t)original, (unsigned int)(uintptr_t)object, (unsigned int)job)
            & 0xFFu) != 0;
}

/* ---- The handlers: -1 = run the caller's request (the stub jumps to the
   stock dispatcher with the caller's own frame); 0 / 1 = return that. ------- */
static int __cdecl vv1_handle(unsigned int ret, unsigned char *village, unsigned int index, int job) {
    int selected, own;
    if (!is_one_of(ret, VV1_CALLS, 3)) return -1;
    selected = *(const int *)(village + index * 0x3D8u + 0x3D0u);
    own = own_first(&VV1_JOBS, selected, job,
                    selected == VV1_JOBS.building
                        && vv1_builder_has_hut_work(village) && !vv1_fresh_hut_on_offer(village), 0,
                    selected == VV1_JOBS.farming && vv1_farming_starts(village));
    if (own < 0) return -1;
    if (dispatch12(vv1_original, village, index, own)) return 1;
    if (own == VV1_JOBS.healing && vv1_plant_fallback(village, index)) return 1;
    return -1;
}

static int __cdecl vv2_handle(unsigned int ret, unsigned char *village, unsigned int index, int job) {
    int selected, own;
    if (!is_one_of(ret, VV2_CALLS, 3)) return -1;
    selected = *(const int *)(village + index * 0xE48Cu + 0x7F8u);
    own = own_first(&VV2_JOBS, selected, job,
                    selected == VV2_JOBS.building
                        && vv2_builder_has_hut_work(village) && !vv2_fresh_hut_on_offer(village), 0, 1);
    if (own < 0) return -1;
    if (dispatch12(vv2_original, village, index, own)) return 1;
    if (own == VV2_JOBS.healing && vv2_plant_fallback(village, index)) return 1;
    return -1;
}

static int __cdecl vv4_handle(unsigned int ret, unsigned char *object, int job) {
    unsigned char *record;
    int own, before, selected;
    if (!is_one_of(ret, VV4_CALLS, 4)) return -1;
    record = *(unsigned char *const *)(object + 0x1B88u);
    selected = *(const int *)(record + 0x1C70u);
    own = builder_asked(&LATER_JOBS, selected, job);
    if (own == -2) {
        own = own_first(&LATER_JOBS, selected, job,
                        selected == LATER_JOBS.building && !vv4_puzzle_on_offer(), 0, 1);
    }
    if (own < 0) return -1;
    before = *(const int *)(record + VV4_EXERCISE.current);
    if (dispatch_later(vv4_original, object, own)) {
        COUNT(started);
        return 1;
    }
    if (own == LATER_JOBS.building && exercise(&VV4_EXERCISE, record, before)) return 1;
    return own == job ? 0 : -1;                    /* the request already ran */
}

/* New Believers: the "untrained" mark is lifted for one dispatch of the
   villager's selected job (never Parenting). */
static int vv5_dispatch(unsigned char *object, unsigned char *record, int job) {
    int *mark = (int *)(record + 0x1C54u);
    int lifted = *mark == 1 && job >= 0 && job != VV5_JOBS.parenting && job == *(const int *)(record + 0x1C74u);
    int started;
    if (lifted) *mark = 0;
    started = dispatch_later(vv5_original, object, job);
    if (lifted && *mark == 0) *mark = 1;
    return started;
}

static int __cdecl vv5_handle(unsigned int ret, unsigned char *object, int job) {
    unsigned char *record;
    int own, before, catch_up;
    if (!is_one_of(ret, VV5_CALLS, 4)) return -1;
    catch_up = ret == VV5_CATCH_UP_CALL;
    record = *(unsigned char *const *)(object + 0x1B88u);
    own = builder_asked(&VV5_JOBS, *(const int *)(record + 0x1C74u), job);
    if (own == -2) {
        own = own_first(&VV5_JOBS, *(const int *)(record + 0x1C74u), job, 1,
                        catch_up || !vv5_devotee_training_present(), 1);
    }
    if (own >= 0) {
        before = *(const int *)(record + VV5_EXERCISE.current);
        if (vv5_dispatch(object, record, own)) {
            COUNT(started);
            return 1;
        }
        if (own == VV5_JOBS.building && exercise(&VV5_EXERCISE, record, before)) return 1;
        if (own == job) return 0;                  /* the request already ran */
    }
    if (*(const int *)(record + 0x1C54u) != 1) return -1;     /* the stock request, as it was */
    return vv5_dispatch(object, record, job);
}

/* For The Secret City's executable-side stub at the dispatcher's entry (the
   fix-huts page): the scheduler's return address, the record, the requested
   job and the ecx the dispatcher was called with.  Returns -2 when this
   companion started something (the stub returns "started"), -3 when it ran
   the request itself and nothing started (the stub returns "nothing"), else
   -1 (the stub runs the stock request).  The own job is dispatched through the
   dispatcher's entry, which reaches this export again with a caller that is
   none of the calls and so runs the stock dispatcher. */
__declspec(dllexport) int __cdecl VvfpWorkFirstFirst(int game_id, unsigned int ret,
                                                     unsigned char *record, int job,
                                                     unsigned int self) {
    int own, before;
    if (game_id != 3 || record == NULL) return -1;
    if (!is_one_of(ret, VV3_CALLS, 4)) return -1;
    own = builder_asked(&LATER_JOBS, *(const int *)(record + 0xEC0u), job);
    if (own == -2) {
        own = own_first(&LATER_JOBS, *(const int *)(record + 0xEC0u), job, 1, 0, 1);
    }
    if (own < 0) return -1;
    before = *(const int *)(record + VV3_EXERCISE.current);
    if ((tc2(VV3_DISPATCHER, self, (unsigned int)(uintptr_t)record, (unsigned int)own) & 0xFFu) != 0) {
        COUNT(started);
        return -2;
    }
    if (own == LATER_JOBS.building && exercise(&VV3_EXERCISE, record, before)) return -2;
    return own == job ? -3 : -1;                   /* -3: the request already ran, nothing started */
}

/* ---- The dispatcher stubs -------------------------------------------------- */
/* VV1/VV2: [esp] = the caller, [esp+4] = index, [esp+8] = job, ecx = the
   village.  ecx is kept for the stock request. */
#define VV12_STUB(NAME)                                                       \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm push ecx                                                   \
            __asm push dword ptr [esp + 0x0C]      /* job */                  \
            __asm push dword ptr [esp + 0x0C]      /* index */                \
            __asm push ecx                         /* village */              \
            __asm push dword ptr [esp + 0x10]      /* the caller */           \
            __asm call NAME##_handle                                         \
            __asm add esp, 16                                                \
            __asm pop ecx                                                    \
            __asm cmp eax, -1                                                \
            __asm je stock_request                                           \
            __asm ret 8                                                      \
            __asm stock_request:                                             \
            __asm jmp NAME##_original                                        \
        }                                                                    \
    }

/* VV4/VV5: [esp] = the caller, [esp+4] = job; ecx = the villager object. */
#define LATER_STUB(NAME)                                                      \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm push ecx                                                   \
            __asm push dword ptr [esp + 0x08]      /* job */                  \
            __asm push ecx                         /* the object */           \
            __asm push dword ptr [esp + 0x0C]      /* the caller */           \
            __asm call NAME##_handle                                         \
            __asm add esp, 12                                                \
            __asm pop ecx                                                    \
            __asm cmp eax, -1                                                \
            __asm je stock_request                                           \
            __asm ret 4                                                      \
            __asm stock_request:                                             \
            __asm jmp NAME##_original                                        \
        }                                                                    \
    }

VV12_STUB(vv1)
VV12_STUB(vv2)
LATER_STUB(vv4)
LATER_STUB(vv5)

/* ---- Beginners: the picker's skill gate (The Tree of Life, New Believers) --- */
/* At the site: esi = the job's skill, ebx = the job, edi = the villager
   object.  The stock `cmp esi, 5; jle fail` is replayed; at 5 or less, for
   the selected job (never Parenting) on the decision's roll, the pick goes on
   to the game's own roll. */
static int __cdecl vv4_beginner(int job, const unsigned char *object) {
    const unsigned char *record = *(const unsigned char *const *)(object + 0x1B88u);
    return job >= 0 && job != LATER_JOBS.parenting && job == *(const int *)(record + 0x1C70u)
        && decision_roll();
}
static int __cdecl vv5_beginner(int job, const unsigned char *object) {
    const unsigned char *record = *(const unsigned char *const *)(object + 0x1B88u);
    return job >= 0 && job != VV5_JOBS.parenting && job == *(const int *)(record + 0x1C74u)
        && decision_roll();
}
static const unsigned int vv4_gate_go = 0x461E6Eu, vv4_gate_fail = 0x461EB4u;
static const unsigned int vv5_gate_go = 0x46A599u, vv5_gate_fail = 0x46A5DFu;
#define GATE_STUB(NAME)                                                       \
    static __declspec(naked) void NAME##_gate_stub(void) {                    \
        __asm {                                                              \
            __asm cmp esi, 5                                                 \
            __asm jg go                                                      \
            __asm pushad                                                     \
            __asm push edi                                                   \
            __asm push ebx                                                   \
            __asm call NAME##_beginner                                       \
            __asm add esp, 8                                                 \
            __asm test eax, eax                                              \
            __asm popad                                                      \
            __asm jnz go                                                     \
            __asm jmp dword ptr [NAME##_gate_fail]                           \
            __asm go:                                                        \
            __asm jmp dword ptr [NAME##_gate_go]                             \
        }                                                                    \
    }
GATE_STUB(vv4)
GATE_STUB(vv5)

/* ---- Catch-up offers: fruit (The Tree of Life), noni (New Believers) ------- */
/* At the site: eax = the game object, ebx = 0, esi = the villager object.
   The stock `cmp byte [eax+flag], bl; jne skip` is replayed; in catch-up a
   villager whose selected job is Farming is offered the option on the
   decision's roll. */
static int __cdecl vv4_farmer_offer(const unsigned char *object) {
    const unsigned char *record = *(const unsigned char *const *)(object + 0x1B88u);
    return *(const int *)(record + 0x1C70u) == LATER_JOBS.farming && decision_roll();
}
static int __cdecl vv5_farmer_offer(const unsigned char *object) {
    const unsigned char *record = *(const unsigned char *const *)(object + 0x1B88u);
    return *(const int *)(record + 0x1C74u) == VV5_JOBS.farming && decision_roll();
}
static const unsigned int vv4_offer_yes = 0x463A38u, vv4_offer_no = 0x463A43u;
static const unsigned int vv5_offer_yes = 0x46C5D2u, vv5_offer_no = 0x46C5D8u;
static __declspec(naked) void vv4_offer_stub(void) {
    __asm {
        cmp byte ptr [eax + 0x171A4], bl
        je yes
        pushad
        push esi
        call vv4_farmer_offer
        add esp, 4
        test eax, eax
        popad
        jnz yes
        jmp dword ptr [vv4_offer_no]
    yes:
        jmp dword ptr [vv4_offer_yes]
    }
}
static __declspec(naked) void vv5_offer_stub(void) {
    __asm {
        cmp byte ptr [eax + 0x17E10], bl
        je yes
        pushad
        push esi
        call vv5_farmer_offer
        add esp, 4
        test eax, eax
        popad
        jnz yes
        jmp dword ptr [vv5_offer_no]
    yes:
        jmp dword ptr [vv5_offer_yes]
    }
}

/* ---- The Lost Children: examining the finished sewing hut ------------------ */
/* At 0x4602B0 (push 4; call rand, 7 bytes): esi = the village, edi = the
   villager's index, bl = 1.  1 when this pick examines the sewing hut. */
static int __cdecl vv2_sewing_pick(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    if (state[0x2E790] != 1) return 0;
    if (!decision_roll()) return 0;
    return pick_index(5) == 4;
}
static const unsigned int vv2_rand = 0x4031A0u, vv2_examine = 0x45F7C0u;
static const unsigned int vv2_pick_resume = 0x4602B7u, vv2_examine_started = 0x4602E5u;
static __declspec(naked) void vv2_sewing_stub(void) {
    __asm {
        pushad
        push esi
        call vv2_sewing_pick
        add esp, 4
        test eax, eax
        popad
        jnz sewing
        push 4
        call dword ptr [vv2_rand]
        jmp dword ptr [vv2_pick_resume]
    sewing:
        push 7
        push edi
        mov ecx, esi
        call dword ptr [vv2_examine]
        jmp dword ptr [vv2_examine_started]
    }
}

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};

static const unsigned char VV2_SEWING_STOCK[7] = { 0x6A, 0x04, 0xE8, 0xE9, 0x2E, 0xFA, 0xFF };
static const unsigned char GATE_STOCK[5] = { 0x83, 0xFE, 0x05, 0x7E, 0x46 };
static const unsigned char VV4_OFFER_STOCK[8] = { 0x38, 0x98, 0xA4, 0x71, 0x01, 0x00, 0x75, 0x0B };
static const unsigned char VV5_OFFER_STOCK[8] = { 0x38, 0x98, 0x10, 0x7E, 0x01, 0x00, 0x75, 0x06 };

#define MAX_SITES 3
static const struct site SITES[6][MAX_SITES] = {
    { { 0 } },
    { { VV1_DISPATCHER, VV1_STOCK, sizeof VV1_STOCK, vv1_stub } },
    { { VV2_DISPATCHER, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
      { 0x4602B0u, VV2_SEWING_STOCK, sizeof VV2_SEWING_STOCK, vv2_sewing_stub } },
    { { 0 } },                          /* The Secret City: the fix-huts page's stub */
    { { VV4_DISPATCHER, VV4_STOCK, sizeof VV4_STOCK, vv4_stub },
      { 0x461E69u, GATE_STOCK, sizeof GATE_STOCK, vv4_gate_stub },
      { 0x463A30u, VV4_OFFER_STOCK, sizeof VV4_OFFER_STOCK, vv4_offer_stub } },
    { { VV5_DISPATCHER, VV5_STOCK, sizeof VV5_STOCK, vv5_stub },
      { 0x46A594u, GATE_STOCK, sizeof GATE_STOCK, vv5_gate_stub },
      { 0x46C5CAu, VV5_OFFER_STOCK, sizeof VV5_OFFER_STOCK, vv5_offer_stub } },
};
static int install_state[6];

static int site_is_stock(const struct site *s) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)s->va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, s->stock, (size_t)s->length) == 0;
}

/* Called by the fix-huts companion from its per-frame install.  Idempotent:
   every site of the game is checked, then all written, or none
   (native/shared/install_sites.h). */
__declspec(dllexport) int __stdcall VvfpWorkFirstInstall(int game_id) {
    vvfp_site_write w[MAX_SITES];
    int n = 0, i;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = -1;
    if (SITES[game_id][0].va == 0) {
        return 0;
    }
    for (i = 0; i < MAX_SITES && SITES[game_id][i].va != 0; ++i) {
        if (!site_is_stock(&SITES[game_id][i])) {
            return 0;
        }
    }
    for (i = 0; i < MAX_SITES && SITES[game_id][i].va != 0; ++i) {
        vvfp_site_branch(&w[n++], SITES[game_id][i].va, SITES[game_id][i].length, SITES[game_id][i].stock,
                         0xE9, (const void *)SITES[game_id][i].stub);
    }
    if (!vvfp_install_sites(w, n)) {
        return 0;
    }
    install_state[game_id] = 1;
    return 1;
}

#ifdef VVFP_TEST
/* For the test build only: site `which` of the game -- its address, stock
   bytes, what it becomes, the stub.  0: no such site. */
__declspec(dllexport) int __stdcall VvfpWorkFirstProbeSite(int game_id, int which, unsigned int *va,
                                                            unsigned char *stock, unsigned char *patched,
                                                            unsigned int *stub_va) {
    const struct site *s;
    unsigned int rel;
    int i;
    if (game_id < 1 || game_id > 5 || which < 0 || which >= MAX_SITES) {
        return 0;
    }
    s = &SITES[game_id][which];
    if (s->va == 0) {
        return 0;
    }
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    rel = (unsigned int)((const unsigned char *)s->stub - ((const unsigned char *)(uintptr_t)s->va + 5));
    patched[0] = 0xE9;
    memcpy(patched + 1, &rel, 4);
    for (i = 5; i < s->length; ++i) {
        patched[i] = 0x90;
    }
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
