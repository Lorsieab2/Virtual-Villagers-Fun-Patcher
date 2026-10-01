/* VVFP Work First -- Builders and Healers Work First (all five games).

   An addendum to Builders Fix Huts When Idle.  The owner: "in both low and
   high food situations, builders and healers still should prioritize fixing
   huts over other stuff for all 5 games" -- builders their building work,
   healers their healing and study, first, only while not every population
   hut is built -- and "make the work patches an addendum to the preexisting
   ones".

   HOW.  Every game's adult idle scheduler asks one work dispatcher to start
   a job for the villager ("dispatch job N; true if something started").  When
   the adult scheduler makes that call for a villager whose selected job is
   Building or Healing, while a population hut is unbuilt, this companion
   first asks the dispatcher for the villager's own job; if that starts
   something, the scheduler sees "started".  If it starts nothing -- no
   project, no hut to fix, no one sick, nothing to study -- the scheduler's own
   request runs exactly as it would have.  So builders and healers work first
   when there is work of theirs to do, and otherwise do whatever the stock
   game would have them do (farming, research, ...).  At low food in VV3-VV5
   the scheduler's farming attempt is one of these calls, so a builder or
   healer tries their own work before farming.

     game  dispatcher  displaced                      adult-scheduler returns         selected job             Bld Heal
     VV1   0x4472C0    mov eax,[esp+8]; test eax,eax  0x448355 0x448382               village+i*0x3D8+0x3D0     4   5
     VV2   0x45FBF0    the same                       0x461A08 0x461A35               village+i*0xE48C+0x7F8    5   3
     VV3   0x45AF00    mov eax,[esp+8]; sub esp,0xA0  0x45C23C 0x45C27A 0x45C28F      record+0xEC0              4   2
     VV4   0x4639B0    mov eax,[esp+4]; sub esp,0x98  0x4659D2 0x465A17 0x465A2A      [obj+0x1B88]+0x1C70       4   2
     VV5   0x46C540    sub esp,0x94                   0x46F291 0x46F2D6 0x46F2EA      [obj+0x1B88]+0x1C74       4   2

   VV1/VV2: thiscall(index, job), ret 8, ecx = village.  VV3: thiscall(record,
   job), ret 8.  VV4/VV5: thiscall(job), ret 4, ecx = the villager object.
   The result is in al.  Every other caller of a dispatcher is untouched.

   CATCH-UP.  Time passing while the game was closed, and Time Warp, never run
   the idle scheduler: each game has a catch-up worker, called a few times per
   age unit for each adult (14+, health >= 20, not busy), which takes the
   stock picker's job and dispatches it itself.  The owner: in catch-up too, a
   villager whose selected job is Building or Healing -- and in New Believers
   Devotion, which only catch-up boosts ("the patch is only meant to boost
   skill gain and progress in jobs that kind of lack that natively") -- does
   that job about three times in four, one roll per worker decision; otherwise
   the stock pick runs.  The worker reaches the dispatcher by one of two
   routes, and both are covered:

     game  worker    pick dispatch (return)  research pick: site, bytes      research path  done
     VV1   0x42E790  0x42E81C (0x42E821)     0x42E7E0 cmp eax,2; jne   (5)   0x42E7E5       0x42E821
     VV2   0x43B4D0  0x43B583 (0x43B588)     0x43B52D cmp ebp,2; jne   (5)   0x43B532       0x43B588
     VV3   0x45BF00  0x45BFC0 (0x45BFC5)     0x45BF52 cmp ebx,1; jne   (5)   0x45BF57       0x45BFC5
     VV4   0x465750  0x465827 (0x46582C)     0x46579F cmp edi,1; jne   (5)   0x4657A4       0x46582C
     VV5   0x46E8E0  0x46E9C9 (0x46E9CE)     0x46E92F cmp edi,1; jne   (5)   0x46E934       0x46E9CE

   * The pick dispatch: its return address is one of the dispatcher stub's
     callers, so it acts exactly as for the live scheduler (own job first;
     nothing of theirs to do -> the pick).  In The Lost Children, The Tree of
     Life and New Believers the worker's task-state continuation runs before
     it, as the live scheduler's does.
   * The research pick (VV1/VV2 job 2, VV3-VV5 job 1) never reaches the
     dispatcher: the worker gives it its own 5% research step.  The site above
     tests for it; a research pick of a builder, healer (or devotee) asks the
     same question and, if the own job starts something, goes to the worker's
     own "done" (its queue processor); otherwise the stock research step runs.
     Any other pick continues to the stock code unchanged.
   * The low-food safety net: at 250 food or less with Farming 20 or more,
     The Secret City, The Tree of Life and New Believers dispatch Farming from
     a third call (returns 0x45BFB0, 0x46580F, 0x46E9B1) and then finish; that
     call is not one of the stub's callers, so Farming still wins.

   Loaded by "VVFP Fix Huts.dll" (VvfpFixHutsInstall, from a companion that
   runs every frame) by full path; The Secret City's hook is a stub in the
   fix-huts page that resolves VvfpWorkFirstFirst, and its catch-up site is
   installed by the first VvfpWorkFirstFirst call.  Not shipped: nothing is
   loaded, and every hook falls through to the stock code. */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include <intrin.h>

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
static const struct later_game VV3 = { 0x4321F0u, 0x594620u, 0 };
static const struct later_game VV4 = { 0x438960u, 0x4D8BF8u, 19 };
static const struct later_game VV5 = { 0x43AE80u, 0x51E008u, 19 };

typedef unsigned char (__stdcall *complete_t)(int);

static int later_complete(const struct later_game *g, int hut) {
    complete_t fn = (complete_t)(uintptr_t)g->complete_fn;
    unsigned char r;
    unsigned int obj = g->complete_obj;
    int arg = g->project_base + hut;
    __asm {
        mov ecx, obj
        push arg
        call fn
        mov r, al
    }
    return r != 0;
}

static int later_huts_incomplete(const struct later_game *g) {
    int i;
    for (i = 0; i < 4; ++i) {
        if (!later_complete(g, i)) {
            return 1;
        }
    }
    return 0;
}

/* ---- About three times in four ------------------------------------------------ */
/* The owner: the behaviour patches "should increase the LIKELIHOOD of
   villagers doing that action, not 100% replace them" -- 75%, one roll per
   decision shared by every patch in it.  The decision and its roll belong to
   "VVFP Fix Huts.dll", which wraps each game's idle scheduler (see "About
   three times in four" there) and hands this companion its VvfpFixHutsRoll
   through VvfpWorkFirstSetRoll before installing it; in The Secret City,
   where the fix-huts page stub loads that DLL, the export is looked up by
   module name.  This companion acts only for the scheduler's own calls, so
   it always asks within a decision.  If the fix-huts DLL cannot be found at
   all (it loads this one, so that does not happen in play) each ask draws a
   75% roll of this companion's own. */
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

static int own_roll(void) {
    unsigned int x = own_roll_state;
    if (x == 0) {
        x = (unsigned int)__rdtsc() ^ 0x2545F491u;
        if (x == 0) x = 0x2545F491u;
    }
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    own_roll_state = x;
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

/* ---- The decision ---------------------------------------------------------- */
/* Counters the tests read.  Compiled only into the TEST build (VVFP_TEST,
   tests/test_dlls/): the shipped DLL carries no counters and no probe. */
#ifdef VVFP_TEST
struct vvfp_work_first_stats {
    int tried;          /* the villager's own job was tried first */
    int started;        /* ... and started something */
};
__declspec(dllexport) struct vvfp_work_first_stats VvfpWorkFirstStats = { 0 };
#define WORK_FIRST_COUNT_TRIED ++VvfpWorkFirstStats.tried
#define WORK_FIRST_COUNT_STARTED __asm inc dword ptr [VvfpWorkFirstStats + 4]
#else
#define WORK_FIRST_COUNT_TRIED ((void)0)
#define WORK_FIRST_COUNT_STARTED
#endif

/* The villager's own job to try first, or -1: the stock request alone.
   Builders: only while a population hut is unbuilt.  Healers: always -- the
   owner: "For healers, they should study medicine at all food levels, when
   they can study medicine"; whether they can (a patient, the Medicine tech,
   the Hospital) is the game's own healing dispatcher's decision, and when it
   starts nothing the scheduler's own request runs.  All of it only when the
   decision's roll passes; otherwise the stock request alone.  devotion: New
   Believers' Devotion job in catch-up (always first, like Healing; whether
   there is anything to honour is the dispatcher's decision), else -1. */
static int own_first(int selected, int requested, int building, int healing, int devotion,
                     int huts_incomplete) {
    if (selected == requested) {
        return -1;
    }
    if (selected == building ? !huts_incomplete
                             : selected != healing && (devotion < 0 || selected != devotion)) {
        return -1;
    }
    if (!decision_roll()) {
        return -1;
    }
    WORK_FIRST_COUNT_TRIED;
    return selected;
}

static int is_one_of(unsigned int ret, const unsigned int *sites, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        if (ret == sites[i]) return 1;
    }
    return 0;
}

/* The adult scheduler's calls, then the catch-up worker's pick dispatch (the
   last entry of each list; see CATCH-UP above).  The worker's low-food
   Farming dispatch in VV3-VV5 is deliberately absent. */
static const unsigned int VV1_CALLS[] = { 0x448355u, 0x448382u, 0x42E821u };
static const unsigned int VV2_CALLS[] = { 0x461A08u, 0x461A35u, 0x43B588u };
static const unsigned int VV3_CALLS[] = { 0x45C23Cu, 0x45C27Au, 0x45C28Fu, 0x45BFC5u };
static const unsigned int VV4_CALLS[] = { 0x4659D2u, 0x465A17u, 0x465A2Au, 0x46582Cu };
static const unsigned int VV5_CALLS[] = { 0x46F291u, 0x46F2D6u, 0x46F2EAu, 0x46E9CEu };
#define VV5_CATCH_UP_CALL 0x46E9CEu
#define VV5_DEVOTION 5

/* The decision for one villager.  catch_up: New Believers' Devotion counts
   only there. */
static int vv1_decide(const unsigned char *village, unsigned int index, int job) {
    return own_first(*(const int *)(village + index * 0x3D8u + 0x3D0u), job, 4, 5, -1,
                     vv1_builder_has_hut_work(village));
}

static int vv2_decide(const unsigned char *village, unsigned int index, int job) {
    return own_first(*(const int *)(village + index * 0xE48Cu + 0x7F8u), job, 5, 3, -1,
                     vv2_builder_has_hut_work(village));
}

static int vv3_decide(const unsigned char *record, int job) {
    return own_first(*(const int *)(record + 0xEC0u), job, 4, 2, -1, later_huts_incomplete(&VV3));
}

static int vv4_decide(const unsigned char *object, int job) {
    const unsigned char *record = *(const unsigned char *const *)(object + 0x1B88u);
    return own_first(*(const int *)(record + 0x1C70u), job, 4, 2, -1, later_huts_incomplete(&VV4));
}

static int vv5_decide(const unsigned char *object, int job, int catch_up) {
    const unsigned char *record = *(const unsigned char *const *)(object + 0x1B88u);
    return own_first(*(const int *)(record + 0x1C74u), job, 4, 2, catch_up ? VV5_DEVOTION : -1,
                     later_huts_incomplete(&VV5));
}

static int __cdecl vv1_first(unsigned int ret, const unsigned char *village, unsigned int index, int job) {
    if (!is_one_of(ret, VV1_CALLS, 3)) return -1;
    return vv1_decide(village, index, job);
}

static int __cdecl vv2_first(unsigned int ret, const unsigned char *village, unsigned int index, int job) {
    if (!is_one_of(ret, VV2_CALLS, 3)) return -1;
    return vv2_decide(village, index, job);
}

static int __cdecl vv4_first(unsigned int ret, const unsigned char *object, int job) {
    if (!is_one_of(ret, VV4_CALLS, 4)) return -1;
    return vv4_decide(object, job);
}

static int __cdecl vv5_first(unsigned int ret, const unsigned char *object, int job) {
    if (!is_one_of(ret, VV5_CALLS, 4)) return -1;
    return vv5_decide(object, job, ret == VV5_CATCH_UP_CALL);
}

/* The catch-up worker's research pick (the sites' stubs below): the job to
   try first, or -1. */
static int __cdecl vv1_research_first(const unsigned char *village, unsigned int index, int pick) {
    return vv1_decide(village, index, pick);
}
static int __cdecl vv2_research_first(const unsigned char *village, unsigned int index, int pick) {
    return vv2_decide(village, index, pick);
}
static int __cdecl vv3_research_first(const unsigned char *record, int pick) {
    return vv3_decide(record, pick);
}
static int __cdecl vv4_research_first(const unsigned char *object, int pick) {
    return vv4_decide(object, pick);
}
static int __cdecl vv5_research_first(const unsigned char *object, int pick) {
    return vv5_decide(object, pick, 1);
}

static void install_catch_up(int game_id);

/* For The Secret City's executable-side stub at the dispatcher's entry: the
   scheduler's return address, the record and the requested job.  The job to
   try first, or -1.  A started job is counted by the stub's caller.  The
   first call also installs The Secret City's catch-up site (its research
   pick): nothing else in that game calls VvfpWorkFirstInstall. */
__declspec(dllexport) int __cdecl VvfpWorkFirstFirst(int game_id, unsigned int ret,
                                                     const unsigned char *record, int job) {
    if (game_id != 3 || record == NULL) return -1;
    install_catch_up(3);
    if (!is_one_of(ret, VV3_CALLS, 4)) return -1;
    return vv3_decide(record, job);
}

/* ---- The stubs ------------------------------------------------------------ */
#define VV1_DISPATCHER 0x4472C0u
#define VV2_DISPATCHER 0x45FBF0u
#define VV4_DISPATCHER 0x4639B0u
#define VV5_DISPATCHER 0x46C540u
static const unsigned char VV1_STOCK[6] = { 0x8B, 0x44, 0x24, 0x08, 0x85, 0xC0 };
static const unsigned char VV2_STOCK[6] = { 0x8B, 0x44, 0x24, 0x08, 0x85, 0xC0 };
static const unsigned char VV4_STOCK[10] = { 0x8B, 0x44, 0x24, 0x04, 0x81, 0xEC, 0x98, 0x00, 0x00, 0x00 };
static const unsigned char VV5_STOCK[6] = { 0x81, 0xEC, 0x94, 0x00, 0x00, 0x00 };
static const unsigned int vv1_body = VV1_DISPATCHER + 6, vv2_body = VV2_DISPATCHER + 6;
static const unsigned int vv4_body = VV4_DISPATCHER + 10, vv5_body = VV5_DISPATCHER + 6;

/* The stock dispatcher, callable: the displaced bytes, then its body.  Also
   the target when the stock request should simply run. */
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

/* VV1/VV2: [esp] = the caller, [esp+4] = index, [esp+8] = job; after
   pushad, +0x20.  Try the own job with the same ecx; al != 0 -> "started"
   (ret 8); else the stock request with the stack untouched. */
#define VV12_STUB(NAME)                                                       \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push dword ptr [esp + 0x28]      /* job */                  \
            __asm push dword ptr [esp + 0x28]      /* index */                \
            __asm push ecx                         /* village */              \
            __asm push dword ptr [esp + 0x2C]      /* the caller */           \
            __asm call NAME##_first                                          \
            __asm add esp, 16                                                \
            __asm mov [esp + 0x1C], eax                                      \
            __asm popad                                                      \
            __asm cmp eax, -1                                                \
            __asm je stock_request                                           \
            __asm push ecx                                                   \
            __asm push eax                         /* the own job */          \
            __asm push dword ptr [esp + 0x0C]      /* index */                \
            __asm call NAME##_original                                       \
            __asm pop ecx                                                    \
            __asm test al, al                                                \
            __asm jz stock_request                                           \
            WORK_FIRST_COUNT_STARTED                                         \
            __asm ret 8                                                      \
            __asm stock_request:                                             \
            __asm jmp NAME##_original                                        \
        }                                                                    \
    }

/* VV4/VV5: [esp] = the caller, [esp+4] = job; ecx = the villager object. */
#define LATER_STUB(NAME)                                                      \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push dword ptr [esp + 0x24]      /* job */                  \
            __asm push ecx                         /* the object */           \
            __asm push dword ptr [esp + 0x28]      /* the caller */           \
            __asm call NAME##_first                                          \
            __asm add esp, 12                                                \
            __asm mov [esp + 0x1C], eax                                      \
            __asm popad                                                      \
            __asm cmp eax, -1                                                \
            __asm je stock_request                                           \
            __asm push ecx                                                   \
            __asm push eax                         /* the own job */          \
            __asm call NAME##_original                                       \
            __asm pop ecx                                                    \
            __asm test al, al                                                \
            __asm jz stock_request                                           \
            WORK_FIRST_COUNT_STARTED                                         \
            __asm ret 4                                                      \
            __asm stock_request:                                             \
            __asm jmp NAME##_original                                        \
        }                                                                    \
    }

VV12_STUB(vv1)
VV12_STUB(vv2)
LATER_STUB(vv4)
LATER_STUB(vv5)

/* ---- Catch-up: the research pick ------------------------------------------ */
/* Each site is the worker's `cmp pick, research; jne` (five bytes) right
   after the stock picker.  The stub replays it: any other pick jumps where
   the jne went.  A research pick asks NAME_research_first; a job back is
   dispatched (the stock dispatcher, with the worker's own arguments); if it
   starts something the worker's "done" runs (its queue processor), else --
   and for -1 -- the stock research step.  Every register the worker keeps is
   untouched; the dispatcher, like the stock call, may change eax/ecx/edx,
   which neither continuation reads before setting. */
static const unsigned int vv1_cu_other = 0x42E817u, vv1_cu_research = 0x42E7E5u, vv1_cu_done = 0x42E821u;
static const unsigned int vv2_cu_other = 0x43B566u, vv2_cu_research = 0x43B532u, vv2_cu_done = 0x43B588u;
static const unsigned int vv3_cu_other = 0x45BF7Bu, vv3_cu_research = 0x45BF57u, vv3_cu_done = 0x45BFC5u;
static const unsigned int vv4_cu_other = 0x4657C3u, vv4_cu_research = 0x4657A4u, vv4_cu_done = 0x46582Cu;
static const unsigned int vv5_cu_other = 0x46E965u, vv5_cu_research = 0x46E934u, vv5_cu_done = 0x46E9CEu;
/* The Secret City's dispatcher is called at its entry, whatever is there:
   the fix-huts page's stub (which leaves this caller to the stock code) or
   the stock bytes. */
static const unsigned int vv3_dispatcher = 0x45AF00u;

/* VV1: eax = pick, esi = index, edi = the worker, [edi+4] = village. */
static __declspec(naked) void vv1_cu_stub(void) {
    __asm {
        cmp eax, 2
        jne other
        pushad
        push eax
        push esi
        push dword ptr [edi + 4]
        call vv1_research_first
        add esp, 12
        mov [esp + 0x1C], eax
        popad
        cmp eax, -1
        je research
        mov ecx, dword ptr [edi + 4]
        push eax
        push esi
        call vv1_original
        test al, al
        jz research
        WORK_FIRST_COUNT_STARTED
        jmp dword ptr [vv1_cu_done]
    research:
        jmp dword ptr [vv1_cu_research]
    other:
        jmp dword ptr [vv1_cu_other]
    }
}

/* VV2: ebp = pick, edi = index, ebx = the worker, [ebx+4] = village. */
static __declspec(naked) void vv2_cu_stub(void) {
    __asm {
        cmp ebp, 2
        jne other
        pushad
        push ebp
        push edi
        push dword ptr [ebx + 4]
        call vv2_research_first
        add esp, 12
        mov [esp + 0x1C], eax
        popad
        cmp eax, -1
        je research
        mov ecx, dword ptr [ebx + 4]
        push eax
        push edi
        call vv2_original
        test al, al
        jz research
        WORK_FIRST_COUNT_STARTED
        jmp dword ptr [vv2_cu_done]
    research:
        jmp dword ptr [vv2_cu_research]
    other:
        jmp dword ptr [vv2_cu_other]
    }
}

/* VV3: ebx = pick, esi = record, edi = village. */
static __declspec(naked) void vv3_cu_stub(void) {
    __asm {
        cmp ebx, 1
        jne other
        pushad
        push ebx
        push esi
        call vv3_research_first
        add esp, 8
        mov [esp + 0x1C], eax
        popad
        cmp eax, -1
        je research
        mov ecx, edi
        push eax
        push esi
        call dword ptr [vv3_dispatcher]
        test al, al
        jz research
        WORK_FIRST_COUNT_STARTED
        jmp dword ptr [vv3_cu_done]
    research:
        jmp dword ptr [vv3_cu_research]
    other:
        jmp dword ptr [vv3_cu_other]
    }
}

/* VV4/VV5: edi = pick, esi = the villager object. */
#define LATER_CU_STUB(NAME)                                                   \
    static __declspec(naked) void NAME##_cu_stub(void) {                      \
        __asm {                                                              \
            __asm cmp edi, 1                                                 \
            __asm jne other                                                  \
            __asm pushad                                                     \
            __asm push edi                                                   \
            __asm push esi                                                   \
            __asm call NAME##_research_first                                 \
            __asm add esp, 8                                                 \
            __asm mov [esp + 0x1C], eax                                      \
            __asm popad                                                      \
            __asm cmp eax, -1                                                \
            __asm je research                                                \
            __asm mov ecx, esi                                               \
            __asm push eax                                                   \
            __asm call NAME##_original                                       \
            __asm test al, al                                                \
            __asm jz research                                                \
            WORK_FIRST_COUNT_STARTED                                         \
            __asm jmp dword ptr [NAME##_cu_done]                             \
            __asm research:                                                  \
            __asm jmp dword ptr [NAME##_cu_research]                         \
            __asm other:                                                     \
            __asm jmp dword ptr [NAME##_cu_other]                            \
        }                                                                    \
    }

LATER_CU_STUB(vv4)
LATER_CU_STUB(vv5)

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};

static const struct site SITES[6] = {
    { 0 },
    { VV1_DISPATCHER, VV1_STOCK, sizeof VV1_STOCK, vv1_stub },
    { VV2_DISPATCHER, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
    { 0 },
    { VV4_DISPATCHER, VV4_STOCK, sizeof VV4_STOCK, vv4_stub },
    { VV5_DISPATCHER, VV5_STOCK, sizeof VV5_STOCK, vv5_stub },
};
static int install_state[6];

/* The catch-up worker's research-pick sites (see CATCH-UP above). */
static const unsigned char VV1_CU_STOCK[5] = { 0x83, 0xF8, 0x02, 0x75, 0x32 };
static const unsigned char VV2_CU_STOCK[5] = { 0x83, 0xFD, 0x02, 0x75, 0x34 };
static const unsigned char VV3_CU_STOCK[5] = { 0x83, 0xFB, 0x01, 0x75, 0x24 };
static const unsigned char VV4_CU_STOCK[5] = { 0x83, 0xFF, 0x01, 0x75, 0x1F };
static const unsigned char VV5_CU_STOCK[5] = { 0x83, 0xFF, 0x01, 0x75, 0x31 };
static const struct site CU_SITES[6] = {
    { 0 },
    { 0x42E7E0u, VV1_CU_STOCK, sizeof VV1_CU_STOCK, vv1_cu_stub },
    { 0x43B52Du, VV2_CU_STOCK, sizeof VV2_CU_STOCK, vv2_cu_stub },
    { 0x45BF52u, VV3_CU_STOCK, sizeof VV3_CU_STOCK, vv3_cu_stub },
    { 0x46579Fu, VV4_CU_STOCK, sizeof VV4_CU_STOCK, vv4_cu_stub },
    { 0x46E92Fu, VV5_CU_STOCK, sizeof VV5_CU_STOCK, vv5_cu_stub },
};
static int cu_install_state[6];

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

static void site_bytes(const struct site *s, unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)s->stub
                                      - ((const unsigned char *)(uintptr_t)s->va + 5));
    int i;
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < s->length; ++i) {
        out[i] = 0x90;
    }
}

/* Verify the stock bytes, then write the jmp.  1 on success. */
static int install_site(const struct site *s) {
    unsigned char bytes[16];
    unsigned char *at;
    DWORD old;
    if (s->va == 0 || !site_is_stock(s)) {
        return 0;
    }
    at = (unsigned char *)(uintptr_t)s->va;
    site_bytes(s, bytes);
    if (!VirtualProtect(at, (SIZE_T)s->length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, (size_t)s->length);
    VirtualProtect(at, (SIZE_T)s->length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)s->length);
    return 1;
}

/* The catch-up worker's research-pick site, once.  A New Home, The Lost
   Children, The Tree of Life and New Believers call this only once their
   dispatcher hook is in (VvfpWorkFirstInstall), since the site's stub calls
   the dispatcher through the replayed stock bytes that hook verified; The
   Secret City (VvfpWorkFirstFirst) calls its dispatcher's entry. */
static void install_catch_up(int game_id) {
    if (cu_install_state[game_id] == 0) {
        cu_install_state[game_id] = install_site(&CU_SITES[game_id]) ? 1 : -1;
    }
}

/* Called by the fix-huts companion from its per-frame install.  Idempotent:
   the dispatcher hook and then the catch-up site, each tried once. */
__declspec(dllexport) int __stdcall VvfpWorkFirstInstall(int game_id) {
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = -1;
    if (!install_site(&SITES[game_id])) {
        return 0;
    }
    install_state[game_id] = 1;
    install_catch_up(game_id);
    return 1;
}

#ifdef VVFP_TEST
/* For the test build only: the site, its stock bytes, what it becomes, the
   stub. */
__declspec(dllexport) int __stdcall VvfpWorkFirstProbeSite(int game_id, unsigned int *va,
                                                            unsigned char *stock,
                                                            unsigned char *patched,
                                                            unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    s = &SITES[game_id];
    if (s->va == 0) {
        return 0;
    }
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* For the test build only: the catch-up research-pick site, the same way. */
__declspec(dllexport) int __stdcall VvfpWorkFirstProbeCatchUpSite(int game_id, unsigned int *va,
                                                                   unsigned char *stock,
                                                                   unsigned char *patched,
                                                                   unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    s = &CU_SITES[game_id];
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
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
