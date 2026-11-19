/* VVFP Work First -- Villagers Work Their Own Job First (formerly Builders and
   Healers Work First), upgraded to skill practice (all five games).

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
   "started".  If it starts nothing, a healer in A New Home and The Lost
   Children whose village has solved Herb Mastery may study one of the
   understood plants (Healing practice); otherwise the caller's own request
   runs exactly as it would have.  A villager is never put first while their
   skill in that job is 5 or less (see "Only above skill 5").
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
         (as before).  No population hut is ever started by nobody's drop:
         Builders Fix Huts When Idle's choices and new-hut test need a hut
         worked on, and the stock hut start is checked here (see "No
         population hut started by nobody's drop").
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

   THE FALLBACK (only after the own job started nothing).  "Doing exercise"
   stays exactly the game's own leisure (the owner, 2026-11-18: "Villagers'
   exercising frequency should stay stock").
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
   * Only above skill 5 (the owner, 2026-11-18, replacing items 1 and 2): A
     New Home's job picker gate (0x439C80, cmp esi, 1) becomes cmp esi, 5,
     the other four games' rule, so in every game a villager goes to a job
     on their own only above skill 5; and nothing here puts a villager's own
     job first at skill 5 or less (see "Only above skill 5").
   * The Tree of Life and New Believers, "untrained" (item 3; The Tree of
     Life added by the owner on #807): every new villager starts with
     [record+0x1C54] = 1, and the dispatcher refuses every job while it is 1
     (VV4 0x4639D2, VV5 0x46C565).  For the scheduler's and catch-up's calls, a request for the
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
    int studied;        /* the plant fallback started */
    int pick;           /* forced random pick, or -1 */
};
__declspec(dllexport) struct vvfp_work_first_stats VvfpWorkFirstStats = { 0, 0, 0, -1 };
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
static int own_first(const struct jobs *j, int selected, int requested, int skill_ok,
                     int building_ok, int devotion_ok, int farming_ok) {
    /* The game's own pick of Parenting (an embrace attempt) is never displaced
       either: mating stays the game's and the Birth Control patches'. */
    if (selected < 0 || selected == requested || selected == j->parenting || requested == j->parenting
        || !skill_ok) {
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

/* A villager asked for the very job that has a fallback -- A New Home's /
   The Lost Children's healers (herb study), the picker's usual answer for
   them: on the decision's roll the
   request is dispatched here, so that if it starts nothing the fallback can
   follow (Codex on #807); -1 = the stock request alone (roll failed), -2 =
   not this case (ask own_first). */
static int own_asked(int selected, int requested, int job_with_fallback, int skill_ok) {
    if (selected != job_with_fallback || requested != job_with_fallback) {
        return -2;
    }
    if (!skill_ok) {
        return -1;
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
/* New Believers: a Heathen (u8 record+0x1CEC non-zero) never gets job work in the game, and nothing here
   gives them any -- not their selected job, not the untrained mark, not noni. */
#define VV5_HEATHEN 0x1CECu

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


/* ---- Only above skill 5 ---------------------------------------------------- */
/* The owner (2026-11-18, on #807): "Villagers should go to their chosen job on
   their own only above skill 5 in all 5 games."  The Lost Children, The Secret
   City, The Tree of Life and New Believers' job pickers never send a villager
   to a job whose skill is 5 or less (VV2 0x449E0F, VV3 0x45986D, VV4
   0x461E69, VV5 0x46A594: cmp esi, 5; jle); A New Home's did so from skill 2
   (0x439C80: cmp esi, 1), and is brought to the same rule below.  This
   companion never puts a villager's own job first while that skill is 5 or
   less either.  The skill of each job, as the pickers read it:
     A New Home        village+i*0x3D8: Farming 0x3C4, Parenting 0x3BC,
                       Research 0x3CC, Building 0x3C0, Healing 0x3C8
     The Lost Children village+i*0xE48C: Farming 0x7EC, Parenting 0x7E4,
                       Healing 0x7F0, Research 0x7F4, Building 0x7E8
     The Secret City   record+0xEAC+4*job (ints)
     Tree of Life / New Believers  record+0x1C5C+4*job (floats, truncated as
                       the pickers' 0x471630 / 0x47C9B0 do) */
#define SKILL_ABOVE 5
static int vv1_skill(const unsigned char *rec, int job) {
    static const unsigned int at[6] = { 0, 0x3C4u, 0x3BCu, 0x3CCu, 0x3C0u, 0x3C8u };
    return job >= 1 && job <= 5 ? *(const int *)(rec + at[job]) : 0;
}
static int vv2_skill(const unsigned char *rec, int job) {
    static const unsigned int at[6] = { 0, 0x7ECu, 0x7E4u, 0x7F0u, 0x7F4u, 0x7E8u };
    return job >= 1 && job <= 5 ? *(const int *)(rec + at[job]) : 0;
}
static int vv3_skill(const unsigned char *rec, int job) {
    return job >= 0 && job <= 4 ? *(const int *)(rec + 0xEACu + 4u * (unsigned int)job) : 0;
}
static int later_skill(const unsigned char *rec, int job, int last) {
    return job >= 0 && job <= last ? (int)*(const float *)(rec + 0x1C5Cu + 4u * (unsigned int)job) : 0;
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
    int selected, own, skill_ok;
    if (!is_one_of(ret, VV1_CALLS, 3)) return -1;
    selected = *(const int *)(village + index * 0x3D8u + 0x3D0u);
    skill_ok = vv1_skill(village + index * 0x3D8u, selected) > SKILL_ABOVE;
    own = own_asked(selected, job, VV1_JOBS.healing, skill_ok);
    if (own == -2) {
        own = own_first(&VV1_JOBS, selected, job, skill_ok,
                        selected == VV1_JOBS.building && vv1_builder_has_hut_work(village), 0,
                        selected == VV1_JOBS.farming && vv1_farming_starts(village));
    }
    if (own < 0) return -1;
    if (dispatch12(vv1_original, village, index, own)) return 1;
    if (own == VV1_JOBS.healing && vv1_plant_fallback(village, index)) return 1;
    return own == job ? 0 : -1;                    /* the request already ran */
}

static int __cdecl vv2_handle(unsigned int ret, unsigned char *village, unsigned int index, int job) {
    int selected, own, skill_ok;
    if (!is_one_of(ret, VV2_CALLS, 3)) return -1;
    selected = *(const int *)(village + index * 0xE48Cu + 0x7F8u);
    skill_ok = vv2_skill(village + index * 0xE48Cu, selected) > SKILL_ABOVE;
    own = own_asked(selected, job, VV2_JOBS.healing, skill_ok);
    if (own == -2) {
        own = own_first(&VV2_JOBS, selected, job, skill_ok,
                        selected == VV2_JOBS.building && vv2_builder_has_hut_work(village), 0, 1);
    }
    if (own < 0) return -1;
    if (dispatch12(vv2_original, village, index, own)) return 1;
    if (own == VV2_JOBS.healing && vv2_plant_fallback(village, index)) return 1;
    return own == job ? 0 : -1;                    /* the request already ran */
}

/* The Tree of Life and New Believers: every new villager starts with the
   "untrained" mark [record+0x1C54] = 1, which the dispatcher refuses (VV4
   0x4639D2, VV5 0x46C565).  The mark is lifted for one dispatch of the
   villager's selected job (never Parenting) and put back afterwards if it is
   still 0 (a refusal inside the call writes 0, which would otherwise train
   them for everything).  The owner: New Believers (item 3), and The Tree of
   Life too (2026-11-18, on #807). */
static int untrained_dispatch(void (*original)(void), unsigned char *object, unsigned char *record, int job,
                              unsigned int selected_at) {
    int *mark = (int *)(record + 0x1C54u);
    int lifted = *mark == 1 && job >= 0 && job != LATER_JOBS.parenting && job == *(const int *)(record + selected_at)
                 && later_skill(record, job, 5) > SKILL_ABOVE;
    int started;
    if (lifted) *mark = 0;
    started = dispatch_later(original, object, job);
    if (lifted && *mark == 0) *mark = 1;
    return started;
}

static int __cdecl vv4_handle(unsigned int ret, unsigned char *object, int job) {
    unsigned char *record;
    int own, selected, skill_ok;
    if (!is_one_of(ret, VV4_CALLS, 4)) return -1;
    record = *(unsigned char *const *)(object + 0x1B88u);
    selected = *(const int *)(record + 0x1C70u);
    skill_ok = later_skill(record, selected, 4) > SKILL_ABOVE;
    own = own_first(&LATER_JOBS, selected, job, skill_ok,
                    selected == LATER_JOBS.building && !vv4_puzzle_on_offer(), 0, 1);
    if (own >= 0 && untrained_dispatch(vv4_original, object, record, own, 0x1C70u)) {
        COUNT(started);
        return 1;
    }
    if (*(const int *)(record + 0x1C54u) != 1) return -1;     /* the stock request, as it was */
    return untrained_dispatch(vv4_original, object, record, job, 0x1C70u);
}


static int __cdecl vv5_handle(unsigned int ret, unsigned char *object, int job) {
    unsigned char *record;
    int own, catch_up, skill_ok;
    if (!is_one_of(ret, VV5_CALLS, 4)) return -1;
    catch_up = ret == VV5_CATCH_UP_CALL;
    record = *(unsigned char *const *)(object + 0x1B88u);
    if (record[VV5_HEATHEN] != 0) return -1;                /* Heathens get nothing new */
    skill_ok = later_skill(record, *(const int *)(record + 0x1C74u), 5) > SKILL_ABOVE;
    own = own_first(&VV5_JOBS, *(const int *)(record + 0x1C74u), job, skill_ok, 1,
                    catch_up || !vv5_devotee_training_present(), 1);
    if (own >= 0 && untrained_dispatch(vv5_original, object, record, own, 0x1C74u)) {
        COUNT(started);
        return 1;
    }
    if (*(const int *)(record + 0x1C54u) != 1) return -1;     /* the stock request, as it was */
    return untrained_dispatch(vv5_original, object, record, job, 0x1C74u);
}

/* For The Secret City's executable-side stub at the dispatcher's entry (the
   fix-huts page): the scheduler's return address, the record, the requested
   job and the ecx the dispatcher was called with.  Returns -2 when this
   companion started something (the stub returns "started"), else
   -1 (the stub runs the stock request).  The own job is dispatched through the
   dispatcher's entry, which reaches this export again with a caller that is
   none of the calls and so runs the stock dispatcher. */
__declspec(dllexport) int __cdecl VvfpWorkFirstFirst(int game_id, unsigned int ret,
                                                     unsigned char *record, int job,
                                                     unsigned int self) {
    int own, skill_ok;
    if (game_id != 3 || record == NULL) return -1;
    if (!is_one_of(ret, VV3_CALLS, 4)) return -1;
    skill_ok = vv3_skill(record, *(const int *)(record + 0xEC0u)) > SKILL_ABOVE;
    own = own_first(&LATER_JOBS, *(const int *)(record + 0xEC0u), job, skill_ok, 1, 0, 1);
    if (own < 0) return -1;
    if ((tc2(VV3_DISPATCHER, self, (unsigned int)(uintptr_t)record, (unsigned int)own) & 0xFFu) != 0) {
        COUNT(started);
        return -2;
    }
    return -1;
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
    return *(const int *)(record + 0x1C74u) == VV5_JOBS.farming && record[VV5_HEATHEN] == 0 && decision_roll();
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

/* ---- No population hut started by nobody's drop (A New Home, The Lost Children) */
/* The owner (2026-11-18, on #807): builders never start a population hut on
   their own; it is started only once the player has dropped a builder on it,
   and then builders continue it as usual.  Builders Fix Huts When Idle's own
   choices and its new-hut test already require a hut worked on (A New Home:
   hut 9 progress 1 or more, huts 10 / 11 2 or more -- the drawing routine
   marks a shown scaffold with 1; The Lost Children: huts 25 / 26 2 or more,
   hut 24 1 or more).  What is left is the stock code that builds A New
   Home's hut 9 and The Lost Children's hut 24 whenever they are not done --
   a new village starts them at progress 125 and 205, but an earthquake can
   take a hut back to 0.  So the call that starts a hut there (A New Home
   0x44753C, call 0x442090, which huts 9 and 10 share; The Lost Children
   0x45FF11, call 0x457130 for hut 24) asks first: the hut is worked on, or
   this villager was dropped on it (the drop's own activity, A New Home
   [rec+0x3B8] 0xB / 0xC / 0xD for huts 9 / 10 / 11; The Lost Children's task
   [rec+0x7E0] 0xB for hut 24).  Otherwise nothing is started and the
   dispatcher reports "nothing" (its own exit: A New Home 0x447901, The Lost
   Children 0x46004C), so the scheduler goes on to other work. */
static int __cdecl vv1_hut_may_start(const unsigned char *village, unsigned int index, int hut) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    if (hut < 9 || hut > 11) return 1;
    if (state[0x9FA0u + 8u * (unsigned int)hut] == 1) return 1;
    if (*(const int *)(state + 0x9F9Cu + 8u * (unsigned int)hut) >= (hut == 9 ? 1 : 2)) return 1;
    return *(const int *)(village + index * 0x3D8u + 0x3B8u) == 0xB + (hut - 9);
}
static int __cdecl vv2_hut_may_start(const unsigned char *village, unsigned int index, int hut) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    if (hut != 24) return 1;
    if (state[0x2E818] == 1 || *(const int *)(state + 0x2E814) >= 1) return 1;
    return *(const int *)(village + index * 0xE48Cu + 0x7E0u) == 0xB;
}
static const unsigned int vv1_build_hut = 0x442090u, vv1_nothing = 0x447901u;
static const unsigned int vv2_build_hut = 0x457130u, vv2_nothing = 0x46004Cu;
/* Entered as the call: [esp] = its return, then (index, hut, flag); ecx =
   the village. */
#define HUT_CALL_STUB(NAME)                                                   \
    static __declspec(naked) void NAME##_hut_stub(void) {                     \
        __asm {                                                              \
            __asm push ecx                                                   \
            __asm push dword ptr [esp + 0x0C]      /* hut */                  \
            __asm push dword ptr [esp + 0x0C]      /* index */                \
            __asm push ecx                         /* the village */          \
            __asm call NAME##_hut_may_start                                  \
            __asm add esp, 12                                                \
            __asm pop ecx                                                    \
            __asm test eax, eax                                              \
            __asm jz blocked                                                 \
            __asm jmp dword ptr [NAME##_build_hut]                           \
            __asm blocked:                                                   \
            __asm add esp, 16                      /* the return, 3 args */   \
            __asm jmp dword ptr [NAME##_nothing]                             \
        }                                                                    \
    }
HUT_CALL_STUB(vv1)
HUT_CALL_STUB(vv2)

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
    unsigned char opcode;          /* 0: a jmp (0xE9); else this opcode (0xE8, a call) */
};

static const unsigned char VV1_HUT_CALL_STOCK[5] = { 0xE8, 0x4F, 0xAB, 0xFF, 0xFF };   /* call 0x442090 */
static const unsigned char VV2_HUT_CALL_STOCK[5] = { 0xE8, 0x1A, 0x72, 0xFF, 0xFF };   /* call 0x457130 */
static const unsigned char VV2_SEWING_STOCK[7] = { 0x6A, 0x04, 0xE8, 0xE9, 0x2E, 0xFA, 0xFF };
/* A New Home's job picker: cmp esi, 1 (no job at skill 0 or 1) becomes cmp
   esi, 5, the other games' rule; the jle that follows (0F 8E 99 FE FF FF)
   is checked too. */
#define VV1_PICKER_GATE 0x439C80u
static const unsigned char VV1_PICKER_GATE_STOCK[9] = { 0x83, 0xFE, 0x01, 0x0F, 0x8E, 0x99, 0xFE, 0xFF, 0xFF };
static const unsigned char VV1_PICKER_GATE_ABOVE_5[3] = { 0x83, 0xFE, 0x05 };
static const unsigned char VV4_OFFER_STOCK[8] = { 0x38, 0x98, 0xA4, 0x71, 0x01, 0x00, 0x75, 0x0B };
static const unsigned char VV5_OFFER_STOCK[8] = { 0x38, 0x98, 0x10, 0x7E, 0x01, 0x00, 0x75, 0x06 };

#define MAX_SITES 3
static const struct site SITES[6][MAX_SITES] = {
    { { 0 } },
    { { VV1_DISPATCHER, VV1_STOCK, sizeof VV1_STOCK, vv1_stub },
      { 0x44753Cu, VV1_HUT_CALL_STOCK, sizeof VV1_HUT_CALL_STOCK, vv1_hut_stub, 0xE8 } },
    { { VV2_DISPATCHER, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
      { 0x4602B0u, VV2_SEWING_STOCK, sizeof VV2_SEWING_STOCK, vv2_sewing_stub },
      { 0x45FF11u, VV2_HUT_CALL_STOCK, sizeof VV2_HUT_CALL_STOCK, vv2_hut_stub, 0xE8 } },
    { { 0 } },                          /* The Secret City: the fix-huts page's stub */
    { { VV4_DISPATCHER, VV4_STOCK, sizeof VV4_STOCK, vv4_stub },
      { 0x463A30u, VV4_OFFER_STOCK, sizeof VV4_OFFER_STOCK, vv4_offer_stub } },
    { { VV5_DISPATCHER, VV5_STOCK, sizeof VV5_STOCK, vv5_stub },
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
    vvfp_site_write w[MAX_SITES + 1];
    int n = 0, i, gate_stock = 0;
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
    /* A New Home's picker gate: stock (cmp esi, 1; jle), or already cmp esi, 5
       -- Birth Control (vv1_birth_control) raises the same floor to 5 and
       routes the jle into its own page, which keeps the "above 5" rule; the
       gate is then left as it is.  Anything else: install nothing. */
    if (game_id == 1) {
        gate_stock = vvfp_site_holds(VV1_PICKER_GATE, VV1_PICKER_GATE_STOCK, sizeof VV1_PICKER_GATE_STOCK);
        if (!gate_stock && !vvfp_site_holds(VV1_PICKER_GATE, VV1_PICKER_GATE_ABOVE_5,
                                            sizeof VV1_PICKER_GATE_ABOVE_5)) {
            return 0;
        }
    }
    for (i = 0; i < MAX_SITES && SITES[game_id][i].va != 0; ++i) {
        vvfp_site_branch(&w[n++], SITES[game_id][i].va, SITES[game_id][i].length, SITES[game_id][i].stock,
                         SITES[game_id][i].opcode ? SITES[game_id][i].opcode : 0xE9,
                         (const void *)SITES[game_id][i].stub);
    }
    if (game_id == 1 && gate_stock) {
        vvfp_site_bytes(&w[n++], VV1_PICKER_GATE, sizeof VV1_PICKER_GATE_ABOVE_5, VV1_PICKER_GATE_STOCK,
                        VV1_PICKER_GATE_ABOVE_5);
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
__declspec(dllexport) int __stdcall VvfpWorkFirstProbeSiteAt(int game_id, int which, unsigned int *va,
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
    patched[0] = s->opcode ? s->opcode : 0xE9;
    memcpy(patched + 1, &rel, 4);
    for (i = 5; i < s->length; ++i) {
        patched[i] = 0x90;
    }
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* The dispatcher hook (site 0), as the other tests' harnesses probe it. */
__declspec(dllexport) int __stdcall VvfpWorkFirstProbeSite(int game_id, unsigned int *va, unsigned char *stock,
                                                            unsigned char *patched, unsigned int *stub_va) {
    return VvfpWorkFirstProbeSiteAt(game_id, 0, va, stock, patched, stub_va);
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
