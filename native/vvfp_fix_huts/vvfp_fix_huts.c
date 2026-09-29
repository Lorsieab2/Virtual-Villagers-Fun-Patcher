/* VVFP Fix Huts -- Builders fix huts when no building project is available.

   The owner: "When no building projects are present/available to be worked
   on AND not all population huts are complete, then builders will fix huts
   to increase their skill (just makes it able to be autonomously chosen;
   applies during catch-up time and live playing)."  All five games.

   WHAT THE STOCK GAMES DO, read from the executables.  Every game has one
   Building dispatcher that the idle scheduler calls, live and in catch-up,
   with the villager's preferred job:

     game  dispatcher   fix-a-hut route
     VV1   0x4472C0     after every project check fails: rand(100) <= 20 ->
                        nothing; else rand(3) picks hut 9/10/11 and examines
                        it only if that hut is complete (0x446600), else
                        nothing.
     VV2   0x45FBF0     the same shape: rand(100) <= 20 -> nothing; else
                        rand(4) picks hut 24/25/26 (or building 5), examined
                        only if complete (0x45F7C0).
     VV3   0x45AF00     a list of options is built; "fix a hut" (job 86,
                        random hut 0..2) is an option ONLY when all four huts
                        are complete.  An empty list -> nothing.
     VV4   0x4639B0     as VV3: job 46, huts = projects 19..22.
     VV5   0x46C540     as VV3: job 53, huts = projects 19..22.

   Examining a hut leads to fixing it (30% of the time) and the fix ends
   with a practice-Building roll.  So a builder whose village has no
   project available -- the next hut not yet unlocked by population,
   everything else built -- idles in VV3-VV5 and mostly idles in VV1-VV2.

   WHAT THIS COMPANION DOES.  At each game's "nothing available" point it
   asks two questions: is any population hut still incomplete, and is at
   least one complete?  If both, it picks a random COMPLETE hut and starts
   the game's own examine/fix job for it, exactly as the stock code does
   when it chooses a hut, and returns "job started" through the stock
   epilogue.  Otherwise the stock code runs unchanged (all huts complete:
   the stock fix-a-hut option is already there; none complete: nothing to
   fix).  Only huts 0..2 / 9..11 / 24..26 are candidates, the same huts the
   stock code fixes.

     VV1 site 0x447724: the rand(100) skip roll before the random hut.
     VV2 site 0x46029D: the same roll.
     VV3 site 0x45B39E: `cmp edi, ebx; je nothing` -- the empty-list test.
     VV4 site 0x463F8A: the same.
     VV5 site 0x46CADA: the same.

   Installed at run time by VvfpFixHutsInstall(game) from a companion that
   already runs every frame in that game; the stock bytes at the site are
   verified first, and any other build installs nothing. */
#include <windows.h>
#include <string.h>

/* Counters a test can read from the running game.  Diagnostic only. */
struct vvfp_fix_huts_stats {
    int checks;         /* the site was reached with nothing available */
    int started;        /* a hut fix was started */
};
__declspec(dllexport) struct vvfp_fix_huts_stats VvfpFixHutsStats = { 0 };

/* A small generator of our own (xorshift32) rather than the CRT's rand():
   no CRT state, no import, so the chooser runs anywhere -- including the
   test's emulator -- and the games' own RNG streams are left untouched. */
static unsigned int pick_state = 0x9E3779B9u;

static unsigned int next_random(void) {
    unsigned int x = pick_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    pick_state = x;
    return x;
}

/* Pick a random index among the set bits of `mask` (bits 0..2).  -1 if none. */
static int pick(unsigned int mask) {
    int candidates[3];
    int n = 0;
    int i;
    for (i = 0; i < 3; ++i) {
        if (mask & (1u << i)) {
            candidates[n++] = i;
        }
    }
    if (n == 0) {
        return -1;
    }
    return candidates[next_random() % (unsigned int)n];
}

/* ---- VV1 --------------------------------------------------------------- */
/* esi = villager array, ebp = the villager's index, ebx = 1 (the result).
   Hut flags: state = [esi+0x3E010]; hut 9 complete: byte [state+0x9FE8],
   hut 10: +0x9FF0, hut 11: +0x9FF8 (== 1).  Examine: push proj; mov ecx,esi;
   push idx; call 0x446600; then the epilogue at 0x4477A6 (result 1). */
#define VV1_SITE     0x447724u
#define VV1_RESUME   0x44772Eu
#define VV1_STARTED  0x4477A6u
#define VV1_EXAMINE  0x446600u
#define VV1_RAND     0x402F10u
static const unsigned char VV1_STOCK[] = { 0x6A, 0x64, 0xE8, 0xE5, 0xB7, 0xFB, 0xFF, 0x83, 0xC4, 0x04 };

static int __cdecl vv1_choose(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    unsigned int mask = 0;
    ++VvfpFixHutsStats.checks;
    if (state[0x9FE8] == 1) mask |= 1;
    if (state[0x9FF0] == 1) mask |= 2;
    if (state[0x9FF8] == 1) mask |= 4;
    if (mask == 7 || mask == 0) {
        return -1;                     /* all complete (stock handles it) or none */
    }
    return 9 + pick(mask);
}

static const unsigned int vv1_rand = VV1_RAND, vv1_resume = VV1_RESUME;
static const unsigned int vv1_examine = VV1_EXAMINE, vv1_started = VV1_STARTED;
static __declspec(naked) void vv1_stub(void) {
    __asm {
        pushad
        push esi
        call vv1_choose
        add esp, 4
        mov [esp + 0x1C], eax          ; pushad's eax slot
        popad
        cmp eax, -1
        je stock
        push eax                       ; project 9/10/11
        mov ecx, esi
        push ebp                       ; the villager's index
        call dword ptr [vv1_examine]
        inc dword ptr [VvfpFixHutsStats + 4]
        jmp dword ptr [vv1_started]
    stock:
        push 0x64                      ; the displaced bytes
        call dword ptr [vv1_rand]
        add esp, 4
        jmp dword ptr [vv1_resume]
    }
}

/* ---- VV2 --------------------------------------------------------------- */
/* esi = village, edi = the villager's index, ebx = 1.  state = [esi+0xE574D4];
   hut 24 complete: byte [state+0x2E818], 25: +0x2E820, 26: +0x2E828.
   Examine: push proj; push idx; mov ecx,esi; call 0x45F7C0; epilogue
   (result 1) at 0x4602E5. */
#define VV2_SITE     0x46029Du
#define VV2_RESUME   0x4602A7u
#define VV2_STARTED  0x4602E5u
#define VV2_EXAMINE  0x45F7C0u
#define VV2_RAND     0x4031A0u
static const unsigned char VV2_STOCK[] = { 0x6A, 0x64, 0xE8, 0xFC, 0x2E, 0xFA, 0xFF, 0x83, 0xC4, 0x04 };

static int __cdecl vv2_choose(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    unsigned int mask = 0;
    ++VvfpFixHutsStats.checks;
    if (state[0x2E818] == 1) mask |= 1;
    if (state[0x2E820] == 1) mask |= 2;
    if (state[0x2E828] == 1) mask |= 4;
    if (mask == 7 || mask == 0) {
        return -1;
    }
    return 24 + pick(mask);
}

static const unsigned int vv2_rand = VV2_RAND, vv2_resume = VV2_RESUME;
static const unsigned int vv2_examine = VV2_EXAMINE, vv2_started = VV2_STARTED;
static __declspec(naked) void vv2_stub(void) {
    __asm {
        pushad
        push esi
        call vv2_choose
        add esp, 4
        mov [esp + 0x1C], eax
        popad
        cmp eax, -1
        je stock
        push eax                       ; project 24/25/26
        push edi                       ; the villager's index
        mov ecx, esi
        call dword ptr [vv2_examine]
        inc dword ptr [VvfpFixHutsStats + 4]
        jmp dword ptr [vv2_started]
    stock:
        push 0x64
        call dword ptr [vv2_rand]
        add esp, 4
        jmp dword ptr [vv2_resume]
    }
}

/* ---- VV3 / VV4 / VV5 ---------------------------------------------------- */
/* The three share one shape.  At the site: edi = option count, ebx = 0,
   esi = the dispatcher's object.  Hut i (0..3) complete: a __stdcall
   predicate returning al -- VV3 0x4321F0(i) with ecx = 0x594620; VV4
   0x438960(19+i) with ecx = 0x4D8BF8; VV5 0x43AE80(19+i) with ecx =
   0x51E008.  Start the fix: the hut index in a stack slot, `push &slot;
   push job; mov ecx, <villager>; call start` -- VV3 villager = esi, job 86,
   start 0x455570; VV4 villager = [esi+0x1B88], job 46, start 0x45DEC0; VV5
   villager = [esi+0x1B88], job 53, start 0x465580 -- then the stock
   "started" epilogue (result 1). */
struct later_game {
    unsigned int site;
    unsigned char stock[8];
    unsigned int nothing;          /* the je's target: no option */
    unsigned int resume;           /* after the je: an option exists */
    unsigned int complete_fn;      /* __stdcall(int) -> al, ecx = complete_obj */
    unsigned int complete_obj;
    int project_base;              /* hut i -> predicate argument */
    unsigned int start_fn;         /* thiscall(job, &arg), ret 8 */
    int job;
    int villager_is_field;         /* 0: villager = esi; else [esi + this] */
    unsigned int started;          /* the epilogue after a start */
};

#define VV3_SITE    0x45B39Eu
#define VV3_NOTHING 0x45B742u
#define VV3_RESUME  0x45B3A6u
#define VV3_STARTED 0x45B5F0u
#define VV4_SITE    0x463F8Au
#define VV4_NOTHING 0x4640FBu
#define VV4_RESUME  0x463F92u
#define VV4_STARTED 0x463FC8u
#define VV5_SITE    0x46CADAu
#define VV5_NOTHING 0x46CDF7u
#define VV5_RESUME  0x46CAE2u
#define VV5_STARTED 0x46CB23u
static const unsigned char VV3_STOCK[8] = { 0x3B, 0xFB, 0x0F, 0x84, 0x9C, 0x03, 0x00, 0x00 };
static const unsigned char VV4_STOCK[8] = { 0x3B, 0xFB, 0x0F, 0x84, 0x69, 0x01, 0x00, 0x00 };
static const unsigned char VV5_STOCK[8] = { 0x3B, 0xFB, 0x0F, 0x84, 0x15, 0x03, 0x00, 0x00 };
static const struct later_game VV3 = {
    VV3_SITE, { 0x3B, 0xFB, 0x0F, 0x84, 0x9C, 0x03, 0x00, 0x00 }, VV3_NOTHING, VV3_RESUME,
    0x4321F0u, 0x594620u, 0, 0x455570u, 86, 0, VV3_STARTED
};
static const struct later_game VV4 = {
    VV4_SITE, { 0x3B, 0xFB, 0x0F, 0x84, 0x69, 0x01, 0x00, 0x00 }, VV4_NOTHING, VV4_RESUME,
    0x438960u, 0x4D8BF8u, 19, 0x45DEC0u, 46, 0x1B88, VV4_STARTED
};
static const struct later_game VV5 = {
    VV5_SITE, { 0x3B, 0xFB, 0x0F, 0x84, 0x15, 0x03, 0x00, 0x00 }, VV5_NOTHING, VV5_RESUME,
    0x43AE80u, 0x51E008u, 19, 0x465580u, 53, 0x1B88, VV5_STARTED
};

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

/* The hut to fix, or -1 for "leave the stock code alone".

   "All complete" is judged over all FOUR population huts, the candidates
   over the first three.  Both come from the stock dispatchers: hut 3 (VV3
   index 3; VV4/VV5 project 22) is built through the same build-a-hut job as
   huts 0..2 (VV3 job 9 with argument 3; VV4/VV5 job 16 with argument 3), so
   it is a population hut, and the stock "fix a hut" option appears only once
   all four are complete while its random pick covers 0..2 only.  So huts
   0..2 complete with hut 3 still unbuilt is exactly a "not all population
   huts are complete" state in which the stock game never fixes anything --
   the case the owner asked to cover -- and the fix goes to one of the three
   huts the stock code itself fixes. */
static int __cdecl later_choose(const struct later_game *g) {
    unsigned int mask = 0;
    int all = 1;
    int i;
    ++VvfpFixHutsStats.checks;
    for (i = 0; i < 4; ++i) {
        int c = later_complete(g, i);
        if (!c) {
            all = 0;
        } else if (i < 3) {
            mask |= 1u << i;
        }
    }
    if (all || mask == 0) {
        return -1;
    }
    return pick(mask);
}

typedef void (__stdcall *start_t)(int job, int *arg);

static void later_start(const struct later_game *g, unsigned int esi, int hut) {
    int slot = hut;
    int *parg = &slot;
    int job = g->job;
    unsigned int villager = g->villager_is_field
        ? *(const unsigned int *)(uintptr_t)(esi + g->villager_is_field) : esi;
    start_t fn = (start_t)(uintptr_t)g->start_fn;
    __asm {
        push parg
        push job
        mov ecx, villager
        call fn
    }
    ++VvfpFixHutsStats.started;
}

/* One stub per game: on the empty-list path, choose; if a hut was chosen,
   start it and take the stock "started" epilogue; else the stock je. */
#define LATER_STUB(NAME, G, NOTHING, RESUME, STARTED)                        \
    static int __cdecl NAME##_decide(unsigned int esi) {                     \
        int hut = later_choose(&G);                                          \
        if (hut < 0) {                                                       \
            return 0;                                                        \
        }                                                                    \
        later_start(&G, esi, hut);                                           \
        return 1;                                                            \
    }                                                                        \
    static const unsigned int NAME##_nothing = NOTHING;                      \
    static const unsigned int NAME##_resume = RESUME;                        \
    static const unsigned int NAME##_started = STARTED;                      \
    static __declspec(naked) void NAME##_stub(void) {                        \
        __asm {                                                              \
            __asm cmp edi, ebx              /* the displaced compare */      \
            __asm jne has_option                                             \
            __asm pushad                                                     \
            __asm push esi                                                   \
            __asm call NAME##_decide                                         \
            __asm add esp, 4                                                 \
            __asm test eax, eax                                              \
            __asm popad                                                      \
            __asm jz nothing                                                 \
            __asm jmp dword ptr [NAME##_started]                             \
            __asm nothing:                                                   \
            __asm jmp dword ptr [NAME##_nothing]                             \
            __asm has_option:                                                \
            __asm jmp dword ptr [NAME##_resume]                              \
        }                                                                    \
    }

LATER_STUB(vv3, VV3, VV3_NOTHING, VV3_RESUME, VV3_STARTED)
LATER_STUB(vv4, VV4, VV4_NOTHING, VV4_RESUME, VV4_STARTED)
LATER_STUB(vv5, VV5, VV5_NOTHING, VV5_RESUME, VV5_STARTED)

/* For an executable-side trampoline (The Secret City has no companion that
   runs every frame to install a detour from, so its row patches the site
   to a stub in the Origins page which calls this): the decision itself.
   Returns 1 when a hut fix was started for the villager the dispatcher's
   esi identifies, 0 when the stock "nothing" path should run.  cdecl. */
__declspec(dllexport) int __cdecl VvfpFixHutsDecide(int game_id, unsigned int esi) {
    if (game_id == 3) return vv3_decide(esi);
    if (game_id == 4) return vv4_decide(esi);
    if (game_id == 5) return vv5_decide(esi);
    return 0;
}

/* ---- Regardless of the food supply --------------------------------------- */
/* The owner: "Builders fix huts regardless of the food supply when not all
   population huts are built."  Every game's idle scheduler reads the food
   total before it reaches the Building dispatcher (one scheduler, reached
   from both the live per-frame caller and the catch-up loop):

     VV1 0x448336  cmp [ebp+0xA2EC], 400; jge -> at 400+ food the preferred
                   job attempt (and the continue-assigned-job step) is
                   skipped for every job.  ebp = state, esi = village,
                   edi = index; preference [esi + edi*0x3D8 + 0x3D0], and
                   Building is job 4 (dispatcher case 4 holds VV1_SITE).
     VV2 0x4619E9  cmp [ecx+0x2EAA4], 300; jge -> the same at 300+ food.
                   ebp = the villager's record; preference [ebp+0x7F8],
                   Building is job 5 (case 5 holds VV2_SITE).
     VV3 0x45C229  at 250 food or LESS the pick (ebx) waits behind a
                   farming attempt, then half the time is swapped for a food
                   action; Building is job 4.  Replaced: the farming test.
     VV4 0x4659B0  the same at 250 or less, pick in eax; Building job 4.
     VV5 0x46F271  the same, pick in eax; Building job 4.

   So a builder -- preferred job Building (VV1/VV2) or picked Building
   (VV3-VV5) -- takes the path the stock game gives it when food is
   plentiful (VV3-VV5) or scarce (VV1/VV2), only while not every population
   hut is complete; everyone else, and every village whose huts are all
   built, runs the stock code.  A different build, or VV1 with Builder
   Action Fixes already owning 0x448336, installs nothing here. */

static int vv1_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    return !(state[0x9FE8] == 1 && state[0x9FF0] == 1 && state[0x9FF8] == 1);
}

static int vv2_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    return !(state[0x2E818] == 1 && state[0x2E820] == 1 && state[0x2E828] == 1);
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

/* Counts for a test reading the running game.  Diagnostic only. */
__declspec(dllexport) int VvfpFixHutsFoodBypasses = 0;

static int __cdecl vv1_builder_first(const unsigned char *village, unsigned int index) {
    if (*(const int *)(village + index * 0x3D8u + 0x3D0u) != 4 || !vv1_huts_incomplete(village)) {
        return 0;
    }
    ++VvfpFixHutsFoodBypasses;
    return 1;
}

static int __cdecl vv2_builder_first(const unsigned char *village, const unsigned char *record) {
    if (*(const int *)(record + 0x7F8u) != 5 || !vv2_huts_incomplete(village)) {
        return 0;
    }
    ++VvfpFixHutsFoodBypasses;
    return 1;
}

/* VV3-VV5 pick numbering: 4 Building, 2 Healing.  A healer's pick waits
   behind the same farming attempt (the 50% food swap already spares job 2);
   while "VVFP Work First.dll" (Builders and Healers Work First) is shipped,
   it is dispatched at once too. */
static int work_first_present(void);

static int __cdecl later_builder_first(const struct later_game *g, int pick) {
    if ((pick != 4 && !(pick == 2 && work_first_present())) || !later_huts_incomplete(g)) {
        return 0;
    }
    ++VvfpFixHutsFoodBypasses;
    return 1;
}

static int __cdecl vv4_builder_first(int pick) { return later_builder_first(&VV4, pick); }
static int __cdecl vv5_builder_first(int pick) { return later_builder_first(&VV5, pick); }

#define VV1_FOOD_SITE 0x448336u
#define VV2_FOOD_SITE 0x4619E9u
#define VV4_FOOD_SITE 0x4659B0u
#define VV5_FOOD_SITE 0x46F271u
static const unsigned char VV1_FOOD_STOCK[12] = {
    0x81, 0xBD, 0xEC, 0xA2, 0x00, 0x00, 0x90, 0x01, 0x00, 0x00, 0x7D, 0x2D };
static const unsigned char VV2_FOOD_STOCK[12] = {
    0x81, 0xB9, 0xA4, 0xEA, 0x02, 0x00, 0x2C, 0x01, 0x00, 0x00, 0x7D, 0x2D };
static const unsigned char VV4_FOOD_STOCK[6] = { 0x8B, 0x8E, 0x88, 0x1B, 0x00, 0x00 };
static const unsigned char VV5_FOOD_STOCK[6] = { 0x8B, 0x8E, 0x88, 0x1B, 0x00, 0x00 };
static const unsigned int vv1_food_low = 0x448342u, vv1_food_high = 0x44836Fu;
static const unsigned int vv2_food_low = 0x4619F5u, vv2_food_high = 0x461A22u;
static const unsigned int vv4_food_dispatch = 0x465A0Fu, vv4_food_resume = 0x4659B6u;
static const unsigned int vv5_food_dispatch = 0x46F2CEu, vv5_food_resume = 0x46F277u;

/* VV1: the displaced compare, then low food or a builder -> the preferred
   attempt; else the stock high-food jump. */
static __declspec(naked) void vv1_food_stub(void) {
    __asm {
        cmp dword ptr [ebp + 0xA2EC], 400
        jl low_path
        pushad
        push edi
        push esi
        call vv1_builder_first
        add esp, 8
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jnz low_path
        jmp dword ptr [vv1_food_high]
    low_path:
        jmp dword ptr [vv1_food_low]
    }
}

static __declspec(naked) void vv2_food_stub(void) {
    __asm {
        cmp dword ptr [ecx + 0x2EAA4], 300
        jl low_path
        pushad
        push ebp
        push esi
        call vv2_builder_first
        add esp, 8
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jnz low_path
        jmp dword ptr [vv2_food_high]
    low_path:
        jmp dword ptr [vv2_food_low]
    }
}

/* VV4/VV5: eax = the pick, fresh from the picker.  A builder goes straight
   to the stock dispatch-with-pick (which reads edi); else the displaced
   mov ecx, [esi+0x1B88] and on into the stock farming-first test. */
#define LATER_FOOD_STUB(NAME)                                                 \
    static __declspec(naked) void NAME##_food_stub(void) {                    \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push eax                                                   \
            __asm call NAME##_builder_first                                  \
            __asm add esp, 4                                                 \
            __asm test eax, eax                                              \
            __asm popad                                                      \
            __asm jz stock_path                                              \
            __asm mov edi, eax                                               \
            __asm jmp dword ptr [NAME##_food_dispatch]                       \
            __asm stock_path:                                                \
            __asm mov ecx, dword ptr [esi + 0x1B88]                          \
            __asm jmp dword ptr [NAME##_food_resume]                         \
        }                                                                    \
    }

LATER_FOOD_STUB(vv4)
LATER_FOOD_STUB(vv5)

/* The Secret City has no companion that runs every frame, so its detour
   is an executable-side stub (scripts/build_vvfp_fix_huts_features.py) that
   calls this with the pick in ebx at 0x45C229: 1 = dispatch the pick now. */
__declspec(dllexport) int __cdecl VvfpFixHutsBuilderFirst(int game_id, int pick) {
    if (game_id == 3) return later_builder_first(&VV3, pick);
    return 0;
}

/* ---- The "Builders and Healers Work First" addendum ---------------------- */
/* "VVFP Work First.dll" is its own companion (one feature per DLL); this one
   loads it by full path, once, from the same per-frame install call, and asks
   it to install its dispatcher hook for this game.  Not shipped (the row is
   off): nothing is loaded and nothing changes.  The Secret City's dispatcher stub
   resolves the addendum's export itself (scripts/build_vvfp_fix_huts_features.py);
   its low-food healer bypass asks work_first_present(). */
static HMODULE work_first_module;
static int work_first_state;          /* 0 = not tried, 1 = loaded, -1 = absent */
static int work_first_installed[6];

static int work_first_present(void) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    if (work_first_state != 0) {
        return work_first_state == 1;
    }
    work_first_state = -1;
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    slash = strrchr(path, '\\');
    if (slash == NULL
        || (size_t)(slash + 1 - path) + sizeof("VVFP Work First.dll") > sizeof(path)) {
        return 0;
    }
    lstrcpyA(slash + 1, "VVFP Work First.dll");
    work_first_module = LoadLibraryA(path);
    if (work_first_module == NULL) {
        return 0;
    }
    work_first_state = 1;
    return 1;
}

static void work_first_bridge(int game_id) {
    int (__stdcall *install)(int);
    if (work_first_installed[game_id] != 0 || !work_first_present()) {
        return;
    }
    work_first_installed[game_id] = -1;
    install = (int (__stdcall *)(int))GetProcAddress(work_first_module, "VvfpWorkFirstInstall");
    if (install != NULL && install(game_id)) {
        work_first_installed[game_id] = 1;
    }
}

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};

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

static const struct site SITES[6] = {
    { 0 },
    { VV1_SITE, VV1_STOCK, sizeof VV1_STOCK, vv1_stub },
    { VV2_SITE, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
    { VV3_SITE, VV3_STOCK, 8, vv3_stub },
    { VV4_SITE, VV4_STOCK, 8, vv4_stub },
    { VV5_SITE, VV5_STOCK, 8, vv5_stub },
};
static int install_state[6];

/* The food-gate sites (VV3's is executable-side, so none here). */
static const struct site FOOD_SITES[6] = {
    { 0 },
    { VV1_FOOD_SITE, VV1_FOOD_STOCK, sizeof VV1_FOOD_STOCK, vv1_food_stub },
    { VV2_FOOD_SITE, VV2_FOOD_STOCK, sizeof VV2_FOOD_STOCK, vv2_food_stub },
    { 0 },
    { VV4_FOOD_SITE, VV4_FOOD_STOCK, sizeof VV4_FOOD_STOCK, vv4_food_stub },
    { VV5_FOOD_SITE, VV5_FOOD_STOCK, sizeof VV5_FOOD_STOCK, vv5_food_stub },
};
static int food_install_state[6];


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

/* Called by a companion that runs every frame in the game.  Idempotent.
   The hut site and the food site are independent: either may be absent
   (another patch owns its bytes) without holding back the other.  Returns
   whether the hut site is installed, as before. */
__declspec(dllexport) int __stdcall VvfpFixHutsInstall(int game_id) {
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    if (food_install_state[game_id] == 0) {
        food_install_state[game_id] = install_site(&FOOD_SITES[game_id]) ? 1 : -1;
    }
    work_first_bridge(game_id);
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = install_site(&SITES[game_id]) ? 1 : -1;
    return install_state[game_id] == 1;
}

/* For the test: the food site, its stock bytes, what it becomes, the stub. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbeFoodSite(int game_id, unsigned int *va,
                                                              unsigned char *stock,
                                                              unsigned char *patched,
                                                              unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    s = &FOOD_SITES[game_id];
    if (s->va == 0) {
        return 0;
    }
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* For the test: the site, its stock bytes, what it becomes, the stub. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbeSite(int game_id, unsigned int *va,
                                                          unsigned char *stock,
                                                          unsigned char *patched,
                                                          unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    s = &SITES[game_id];
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* For the test: the choosers over a caller-supplied village image (VV1/VV2)
   -- the game's own offsets are read, so the test lays the flags out where
   the game keeps them. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbeChoose(int game_id, const void *village) {
    if (game_id == 1) return vv1_choose((const unsigned char *)village);
    if (game_id == 2) return vv2_choose((const unsigned char *)village);
    return -2;
}

/* For the test: `pick` over a mask, with the RNG seeded. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbePick(unsigned int mask, unsigned int seed) {
    pick_state = seed ? seed : 1u;
    return pick(mask);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
