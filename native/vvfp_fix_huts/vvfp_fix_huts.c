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

/* Counters the tests read.  Compiled only into the TEST build (VVFP_TEST,
   tests/test_dlls/): the shipped DLL carries no counters and no probe. */
#ifdef VVFP_TEST
struct vvfp_fix_huts_stats {
    int checks;         /* the site was reached with nothing available */
    int started;        /* a hut fix was started */
};
__declspec(dllexport) struct vvfp_fix_huts_stats VvfpFixHutsStats = { 0 };
#define FIX_HUTS_COUNT(field) (++VvfpFixHutsStats.field)
#else
#define FIX_HUTS_COUNT(field) ((void)0)
#endif

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
    FIX_HUTS_COUNT(checks);
    if (state[0x9FE8] == 1) mask |= 1;
    if (state[0x9FF0] == 1) mask |= 2;
    if (state[0x9FF8] == 1) mask |= 4;
    if (mask == 7 || mask == 0) {
        return -1;                     /* all complete (stock handles it) or none */
    }
    return 9 + pick(mask);
}

/* Below Building level 3 (the owner: "below level 3, at all food levels,
   villagers will fix huts if at least one is built and there are no other
   building projects available"): any complete population hut, including
   when every one is complete; -1 only when none is. */
static int __cdecl vv1_choose_any(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    unsigned int mask = 0;
    FIX_HUTS_COUNT(checks);
    if (state[0x9FE8] == 1) mask |= 1;
    if (state[0x9FF0] == 1) mask |= 2;
    if (state[0x9FF8] == 1) mask |= 4;
    return mask == 0 ? -1 : 9 + pick(mask);
}

static const unsigned int vv1_rand = VV1_RAND, vv1_resume = VV1_RESUME;
static const unsigned int vv1_examine = VV1_EXAMINE, vv1_started = VV1_STARTED;
/* No population hut complete: nothing to fix. */
static int __cdecl vv1_none_complete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    return state[0x9FE8] != 1 && state[0x9FF0] != 1 && state[0x9FF8] != 1;
}

/* A New Home's Building branch reports "started" (al = bl = 1) on every way
   it gives up -- the 20% skip roll, a picked hut that is not complete, the
   Building-level-below-3 gate -- so a builder with nothing to do stands on
   "Nothing" and the scheduler never looks further.  Seen in the owner's live
   village (v1.35.36): Building level 2, hut 9 built, huts 10/11 not, both
   builders on "Nothing" for a full minute and this companion's check counter
   still 0.  Here the give-up paths report "nothing started" (al = 0), the
   same as The Lost Children and the later games do, so the scheduler goes on
   to other work; the epilogue pops the dispatcher's own saves. */
static __declspec(naked) void vv1_nothing(void) {
    __asm {
        pop edi
        pop ebp
        pop ebx
        pop esi
        xor al, al
        ret 8
    }
}

static const unsigned int vv1_hut_pick = VV1_RESUME + 9;   /* 0x447737: push 3; the stock rand(3) hut */

/* BUILD FIRST, THEN FIX.  The owner: "The builders will prioritize fixing huts
   OVER building the new huts or other projects, when in fact they should build
   new stuff first, then fix huts."

   Both places this companion fixes a hut are reached on paths where the stock
   branch had NOT chosen construction for reasons that are not "there is none":
   the 20% "not this time" roll at 0x447724, and the Building-level-below-3 gate
   at 0x44765E, which the stock branch also reaches through a 20% roll in front
   of each project (0x4475E0, 0x447621).  Stock then retried on a later tick and
   built; a hut fix started here instead occupies the builder.  So before any
   fix, this asks whether construction is available exactly as the stock branch
   judges it, and if so enters that construction's own stock code:

     new huts (entry 0x447528, the stock hut section): hut 9 while incomplete,
       hut 10 while incomplete and population > 22, hut 11 while incomplete
       and population > 45 -- population from the game's own counter 0x41CF90
       (ecx = village state), as the stock checks call it;
     started projects, each at the check block after its random roll:
       project 3 (0x4475A8) at any level, 2 (0x4475F8) and 4 (0x447635) from
       Building level 2, 8 (0x447685), 7 (0x4476C2) and 5 (0x4476FB) from 3 --
       each only while its progress dword > 0 and its complete flag != 1,
       the very tests its block makes.

   The predicates mirror the blocks they enter, so a jump always starts that
   construction and never falls back here.  Project record i: progress dword at
   state + 0x9F9C + 8*i, complete flag byte 4 bytes later (read from the
   owner's saves: progress counts up to the target, the flag turns 1). */
#define VV1_POPULATION   0x41CF90u
#define VV1_HUT_SECTION  0x447528u
#define VV1_HUT9_CALL    0x44753Cu   /* stock: call 0x442090, the hut gate */
#define VV1_HUT_GATE     0x442090u
static const unsigned int vv1_population_fn = VV1_POPULATION;

static const struct { unsigned int id; int min_level; unsigned int block; } VV1_PROJECTS[] = {
    { 3, 0, 0x4475A8u }, { 2, 2, 0x4475F8u }, { 4, 2, 0x447635u },
    { 8, 3, 0x447685u }, { 7, 3, 0x4476C2u }, { 5, 3, 0x4476FBu },
};

static int vv1_progress(const unsigned char *state, unsigned int id) {
    return *(const int *)(state + 0x9F9C + 8 * id);
}

static int vv1_complete(const unsigned char *state, unsigned int id) {
    return state[0x9F9C + 8 * id + 4] == 1;
}

static int vv1_population(const unsigned char *state) {
    int n;
    __asm {
        mov ecx, state
        call dword ptr [vv1_population_fn]
        mov n, eax
    }
    return n;
}

/* A progress gate on the new-hut calls (older Builder Action Fixes) would make
   the stock hut section skip a hut at zero progress; mirror it if present, so
   the hut predicate still matches what that section will do. */
static int vv1_huts_need_progress(void) {
    const unsigned char *call = (const unsigned char *)VV1_HUT9_CALL;
    if (call[0] != 0xE8) return 1;
    return VV1_HUT9_CALL + 5 + *(const int *)(call + 1) != VV1_HUT_GATE;
}

static int vv1_hut_buildable(const unsigned char *state, unsigned int id, int population, int need_progress) {
    static const int min_population[3] = { -1, 0x16, 0x2D };
    if (vv1_complete(state, id)) return 0;
    if (population <= min_population[id - 9]) return 0;
    return !need_progress || vv1_progress(state, id) > 0;
}

/* The stock construction entry to take instead of a fix, or 0 when there is
   no construction to do. */
static unsigned int __cdecl vv1_construction(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    const int level = *(const int *)(state + 0xA2CC);
    const int need_progress = vv1_huts_need_progress();
    unsigned int i;
    int population = -1;
    for (i = 9; i <= 11; ++i) {
        if (vv1_complete(state, i)) continue;
        if (population < 0) population = vv1_population(state);
        if (vv1_hut_buildable(state, i, population, need_progress)) return VV1_HUT_SECTION;
    }
    for (i = 0; i < sizeof VV1_PROJECTS / sizeof VV1_PROJECTS[0]; ++i) {
        if (level < VV1_PROJECTS[i].min_level) continue;
        if (!vv1_complete(state, VV1_PROJECTS[i].id) && vv1_progress(state, VV1_PROJECTS[i].id) > 0) {
            return VV1_PROJECTS[i].block;
        }
    }
    return 0;
}

static __declspec(naked) void vv1_stub(void) {
    __asm {
        pushad                         ; construction first, whatever the roll
        push esi
        call vv1_construction
        add esp, 4
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jz no_construction
        jmp eax                        ; the stock code for that construction
    no_construction:
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
#ifdef VVFP_TEST
        inc dword ptr [VvfpFixHutsStats + 4]
#endif
        jmp dword ptr [vv1_started]
    stock:
        pushad
        push esi
        call vv1_none_complete
        add esp, 4
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jnz vv1_nothing                ; no hut stands: nothing to fix
        push 0x64                      ; the displaced bytes: the skip roll
        call dword ptr [vv1_rand]
        add esp, 4
        cmp eax, 0x14
        jle vv1_nothing                ; skipped: "nothing", not a false "started"
        jmp dword ptr [vv1_hut_pick]   ; every hut complete: the stock random hut
    }
}

/* The Building-level gate before the hut: `mov edx, [esi+0x3E010]; cmp
   [edx+0xA2CC], 3; jl give-up` at 0x44765E.  Below level 3 the stock branch
   gives up here, before the hut fix; with this detour it goes on to the hut
   fix above (esi, ebp and bl = 1 are what the hut site sees).  Level 3 and
   above: the stock code at 0x447664. */
#define VV1_LEVEL_SITE   0x44765Eu
static const unsigned char VV1_LEVEL_STOCK[6] = { 0x8B, 0x96, 0x10, 0xE0, 0x03, 0x00 };
static const unsigned int vv1_level_resume = 0x447671u;
/* Below level 3 a builder fixes any complete population hut -- the owner:
   "below level 3, at all food levels, villagers will fix huts if at least
   one is built and there are no other building projects available" -- and
   with none built, "nothing".  Never the stock random pick the gate used to
   skip (Codex on #463). */
static __declspec(naked) void vv1_level_stub(void) {
    __asm {
        mov edx, dword ptr [esi + 0x3E010]
        cmp dword ptr [edx + 0xA2CC], 3
        jl below
        jmp dword ptr [vv1_level_resume]
    below:
        pushad                         ; construction first, whatever the rolls
        push esi
        call vv1_construction
        add esp, 4
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jz below_no_construction
        jmp eax                        ; the stock code for that construction
    below_no_construction:
        pushad
        push esi
        call vv1_choose_any
        add esp, 4
        mov [esp + 0x1C], eax
        popad
        cmp eax, -1
        je vv1_nothing
        mov ebx, 1                     ; the started epilogue returns bl
        push eax                       ; project 9/10/11
        mov ecx, esi
        push ebp                       ; the villager's index
        call dword ptr [vv1_examine]
#ifdef VVFP_TEST
        inc dword ptr [VvfpFixHutsStats + 4]
#endif
        jmp dword ptr [vv1_started]
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
    FIX_HUTS_COUNT(checks);
    if (state[0x2E818] == 1) mask |= 1;
    if (state[0x2E820] == 1) mask |= 2;
    if (state[0x2E828] == 1) mask |= 4;
    if (mask == 7 || mask == 0) {
        return -1;
    }
    return 24 + pick(mask);
}

/* Below Building level 3: any complete population hut (24/25/26), including
   when every one is complete; -1 only when none is.  Never building 5. */
static int __cdecl vv2_choose_any(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    unsigned int mask = 0;
    FIX_HUTS_COUNT(checks);
    if (state[0x2E818] == 1) mask |= 1;
    if (state[0x2E820] == 1) mask |= 2;
    if (state[0x2E828] == 1) mask |= 4;
    return mask == 0 ? -1 : 24 + pick(mask);
}

/* Build first, fix last (the owner: "The builders will prioritize fixing huts
   OVER building the new huts or other projects, when in fact they should
   build new stuff first, then fix huts").  The Lost Children's Building
   branch (case 5 of 0x45FBF0) tries its construction in this order, each
   behind a rand(100) > 20 roll (80%), and reaches the level gate
   (0x4601F2) and the hut site (0x46029D) whenever a roll fails:

     1. the villager's own assigned build task, [record+0x7E0] 11..20, while
        that project's complete flag is still 0;
     2. project 1 (progress > 0, not complete) when the villager has no task;
     3. new huts: hut 24 while incomplete (at any progress); hut 25 with
        population > 22, incomplete, progress >= 2; hut 26 the same with
        population > 45;
     4. Building level >= 2: project 17 (project 9 complete), project 8
        (progress > 0), project 5 (progress >= 2, [state+0x2EA8C] >= 3);
     5. Building level >= 3: project 12 and project 11 (progress >= 1, not
        complete, [state+0x2EA74] >= 3; 11 also needs project 9 complete).

   A project record is (signed progress dword, complete-flag byte) at state
   + 0x2E754 + id*8 -- in the owner's saves (state + 4 in the .ldw) hut 24
   reads 383/0 while being built and 24/1 once built.  So a failed roll could
   send a builder to fix a hut -- this companion's fix or the stock one --
   while a hut or project the stock game would build was right there.  This
   is the same test without the rolls: while it holds, the hut site and the
   level gate give "nothing" (al = 0, the stock gate's own target), so the
   builder is never sent to fix a hut and the next attempt rolls for the
   construction again.  Population: 0x425860, thiscall on the state. */
static int vv2_population(const unsigned char *state) {
    int n;
    __asm {
        mov ecx, state
        mov eax, 0x425860
        call eax
        mov n, eax
    }
    return n;
}

#define VV2_PROGRESS(state, id) (*(const int *)((state) + 0x2E754 + (id) * 8))
#define VV2_DONE(state, id) ((state)[0x2E758 + (id) * 8])

static int __cdecl vv2_construction_available(const unsigned char *village, unsigned int index) {
    /* [record+0x7E0] task 11..20 -> the project whose flag the stock handler
       tests (jump table 0x460550). */
    static const unsigned char task_project[10] = { 24, 25, 26, 5, 7, 8, 1, 17, 12, 11 };
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    int task = *(const int *)(village + index * 0xE48Cu + 0x7E0u);
    int level = *(const int *)(state + 0x2EA84);
    if (task >= 11 && task <= 20 && VV2_DONE(state, task_project[task - 11]) == 0) return 1;
    if (VV2_DONE(state, 1) != 1 && VV2_PROGRESS(state, 1) > 0 && task == 0) return 1;
    if (VV2_DONE(state, 24) != 1) return 1;
    if (VV2_DONE(state, 25) != 1 && VV2_PROGRESS(state, 25) >= 2 && vv2_population(state) > 22) return 1;
    if (VV2_DONE(state, 26) != 1 && VV2_PROGRESS(state, 26) >= 2 && vv2_population(state) > 45) return 1;
    if (level < 2) return 0;
    if (VV2_DONE(state, 9) != 0 && VV2_PROGRESS(state, 17) > 0 && VV2_DONE(state, 17) == 0) return 1;
    if (VV2_DONE(state, 8) != 1 && VV2_PROGRESS(state, 8) > 0) return 1;
    if (VV2_DONE(state, 5) != 1 && VV2_PROGRESS(state, 5) >= 2 && *(const int *)(state + 0x2EA8C) >= 3) return 1;
    if (level < 3) return 0;
    if (VV2_PROGRESS(state, 12) >= 1 && VV2_DONE(state, 12) == 0 && *(const int *)(state + 0x2EA74) >= 3) return 1;
    if (VV2_PROGRESS(state, 11) >= 1 && VV2_DONE(state, 11) == 0 && VV2_DONE(state, 9) != 0
        && *(const int *)(state + 0x2EA74) >= 3) return 1;
    return 0;
}

static const unsigned int vv2_rand = VV2_RAND, vv2_resume = VV2_RESUME;
static const unsigned int vv2_examine = VV2_EXAMINE, vv2_started = VV2_STARTED;
static const unsigned int vv2_nothing = 0x46004Cu;   /* pop edi/ebp/ebx; al = 0; pop esi; ret 8 */
static __declspec(naked) void vv2_stub(void) {
    __asm {
        pushad
        push edi                       ; the villager's index
        push esi
        call vv2_construction_available
        add esp, 8
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jnz build_first                ; construction the stock game would do: never a hut fix
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
#ifdef VVFP_TEST
        inc dword ptr [VvfpFixHutsStats + 4]
#endif
        jmp dword ptr [vv2_started]
    stock:
        push 0x64
        call dword ptr [vv2_rand]
        add esp, 4
        jmp dword ptr [vv2_resume]
    build_first:
        jmp dword ptr [vv2_nothing]
    }
}

/* The Building-level gate before the hut: `cmp [state+0x2EA84], 3; jl
   nothing` at 0x4601F2 (edx = state).  Below level 3 the stock branch gives up
   here, before the hut fix -- the same gate A New Home has -- so a builder in
   a village below level 3 never fixes a hut.  With this detour it fixes a
   complete population hut, with ebx = 1 for the "started" epilogue.  Level 3
   and above: the stock code at 0x4601FF.  The Lost Children already reports
   "nothing started" when it gives up (xor al, al). */
#define VV2_LEVEL_SITE   0x4601F2u
static const unsigned char VV2_LEVEL_STOCK[13] = {
    0x83, 0xBA, 0x84, 0xEA, 0x02, 0x00, 0x03, 0x0F, 0x8C, 0x4D, 0xFE, 0xFF, 0xFF };
static const unsigned int vv2_level_resume = 0x4601FFu;
static const unsigned int vv2_level_nothing = 0x46004Cu;   /* the stock gate's own target: al = 0 */
/* Below level 3 only a population hut is ever fixed: any complete one (the
   owner: "if at least one is built"), including when every one is.  With none
   built, the stock gate's "nothing"; the stock random pick, whose fourth
   option is building 5 rather than a hut, is never reached from here (Codex
   on #463). */
static __declspec(naked) void vv2_level_stub(void) {
    __asm {
        cmp dword ptr [edx + 0x2EA84], 3
        jl below
        jmp dword ptr [vv2_level_resume]
    below:
        pushad
        push edi                       ; the villager's index
        push esi
        call vv2_construction_available
        add esp, 8
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jnz nothing                    ; construction first: never a hut fix
        pushad
        push esi
        call vv2_choose_any
        add esp, 4
        mov [esp + 0x1C], eax
        popad
        cmp eax, -1
        je nothing
        mov ebx, 1                     ; the started epilogue returns bl
        push eax                       ; project 24/25/26
        push edi                       ; the villager's index
        mov ecx, esi
        call dword ptr [vv2_examine]
#ifdef VVFP_TEST
        inc dword ptr [VvfpFixHutsStats + 4]
#endif
        jmp dword ptr [vv2_started]
    nothing:
        jmp dword ptr [vv2_level_nothing]
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
    FIX_HUTS_COUNT(checks);
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
    FIX_HUTS_COUNT(started);
}

/* ---- Build first, fix last (VV3 / VV4 / VV5) ---------------------------- */
/* The owner: "The builders will prioritize fixing huts OVER building the new
   huts or other projects, when in fact they should build new stuff first,
   then fix huts."  At the site the dispatcher's option list is complete:
   `count` = edi entries at [esp + list offset] (VV3 +0x64, VV4 +0x5C, VV5
   +0x58), each an option number; the stock random pick then takes one of
   them uniformly.  Option 9 is the stock "fix a hut" (present once all four
   huts are complete); every other option is construction -- a new hut, or a
   project to start or continue (VV3 options 1-8; VV4 1-8, 10, 11; VV5 1-8,
   11, 12).  Two ways led a builder to fix a hut while construction stood:

     * The stock mix: with every hut built, option 9 sits in the list beside
       the projects and is picked 1 time in n.
     * The Tree of Life and New Believers roll most construction options
       away for a villager whose dislikes (record +0x1E6C / +0x1F68, the game's
       own membership test 0x45D1F0 / 0x464F90) include item 30 -- and VV5's
       option 6 for item 53: only a rand(100) <= 15 keeps the option.  So
       the list came out empty (this companion then fixed a hut) or held only
       option 9 while a hut or project was there to build.

   So option 9 is taken out of any list that has construction in it, and a
   list emptied by those rolls while construction stands gives the stock
   "nothing" -- the next attempt rolls for the construction again, exactly as
   the stock game does; the villager is never sent to a hut instead.  Only
   when there is no construction at all is a hut fixed: the stock option 9
   when every hut is built, or this companion's pick among the built huts
   when some are not.  The Secret City has no such rolls, so there the
   filter only drops option 9 from a mixed list. */
#define FIX_A_HUT_OPTION 9

/* thiscall(arg) -> eax, and thiscall() -> eax, on a game object. */
static int call_state(unsigned int fn, unsigned int obj, int arg) {
    int r;
    __asm {
        mov ecx, obj
        push arg
        call fn
        mov r, eax
    }
    return r;
}

static int call_count(unsigned int fn, unsigned int obj) {
    int r;
    __asm {
        mov ecx, obj
        call fn
        mov r, eax
    }
    return r;
}

/* The options the dislike rolls can remove, without the rolls: the game's
   own tests, in the dispatcher's order. */
static int vv4_rolled_construction(void) {
    static const int projects[7] = { 19, 20, 21, 23, 22, 25, 24 };  /* options 1-4, 8, 10, 11 */
    int i;
    for (i = 0; i < 7; ++i) {
        if (call_state(0x438980u, 0x4D8BF8u, projects[i]) >= 1
            && !later_complete(&VV4, projects[i] - 19)) {
            return 1;
        }
    }
    /* option 6: 0x4396D0(0x4D86A8) < 2 and 0x421570(0x4D86A8) < 100 */
    return call_count(0x4396D0u, 0x4D86A8u) < 2 && call_count(0x421570u, 0x4D86A8u) < 100;
}

static int vv5_rolled_construction(void) {
    static const int projects[6] = { 19, 20, 21, 23, 22, 24 };      /* options 1-4, 8, 11 */
    int i, n;
    for (i = 0; i < 6; ++i) {
        if (call_state(0x43AEA0u, 0x51E008u, projects[i]) > 1
            && !later_complete(&VV5, projects[i] - 19)) {
            return 1;
        }
    }
    /* option 6: 0 < 0x4388D0(0x51DE40) < 100 */
    n = call_count(0x4388D0u, 0x51DE40u);
    return n > 0 && n < 100;
}

/* The filter.  -1: a hut fix was started (take the stock "started"
   epilogue); otherwise the new option count (0: the stock "nothing"). */
static int later_filter(const struct later_game *g, int (*rolled)(void), unsigned int esi,
                        int *list, int count) {
    int i, fix_at = -1, construction;
    for (i = 0; i < count; ++i) {
        if (list[i] == FIX_A_HUT_OPTION) {
            fix_at = i;
        }
    }
    construction = count - (fix_at >= 0 ? 1 : 0) > 0 || (rolled != NULL && rolled());
    if (construction) {
        if (fix_at >= 0) {
            for (i = fix_at; i + 1 < count; ++i) {
                list[i] = list[i + 1];
            }
            list[--count] = 0;
        }
        return count;
    }
    if (count > 0) {
        return count;                  /* only option 9: the stock fix, every hut built */
    }
    {
        int hut = later_choose(g);
        if (hut < 0) {
            return 0;
        }
        later_start(g, esi, hut);
        return -1;
    }
}

static int __cdecl vv3_filter(unsigned int esi, int *list, int count) { return later_filter(&VV3, NULL, esi, list, count); }
static int __cdecl vv4_filter(unsigned int esi, int *list, int count) { return later_filter(&VV4, vv4_rolled_construction, esi, list, count); }
static int __cdecl vv5_filter(unsigned int esi, int *list, int count) { return later_filter(&VV5, vv5_rolled_construction, esi, list, count); }

/* One stub per game, at `cmp edi, ebx; je nothing` (ebx = 0): filter the
   list, then the stock test on the new count -- or, after a hut fix was
   started, the stock "started" epilogue. */
#define LATER_STUB(NAME, LIST, NOTHING, RESUME, STARTED)                     \
    static const unsigned int NAME##_nothing = NOTHING;                      \
    static const unsigned int NAME##_resume = RESUME;                        \
    static const unsigned int NAME##_started = STARTED;                      \
    static __declspec(naked) void NAME##_stub(void) {                        \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm lea eax, [esp + 0x20 + LIST]                               \
            __asm push edi                  /* count */                      \
            __asm push eax                  /* the option list */            \
            __asm push esi                                                   \
            __asm call NAME##_filter                                         \
            __asm add esp, 12                                                \
            __asm cmp eax, -1                                                \
            __asm je started                                                 \
            __asm mov [esp], eax            /* pushad's edi slot */          \
            __asm popad                                                      \
            __asm cmp edi, ebx              /* the displaced compare */      \
            __asm je nothing                                                 \
            __asm jmp dword ptr [NAME##_resume]                              \
            __asm nothing:                                                   \
            __asm jmp dword ptr [NAME##_nothing]                             \
            __asm started:                                                   \
            __asm popad                                                      \
            __asm jmp dword ptr [NAME##_started]                             \
        }                                                                    \
    }

LATER_STUB(vv3, 0x64, VV3_NOTHING, VV3_RESUME, VV3_STARTED)
LATER_STUB(vv4, 0x5C, VV4_NOTHING, VV4_RESUME, VV4_STARTED)
LATER_STUB(vv5, 0x58, VV5_NOTHING, VV5_RESUME, VV5_STARTED)

/* For The Secret City's executable-side trampoline (it has no companion that
   runs every frame to install a detour from, so its row patches the site to
   a stub in the Origins page which calls this): the filter above.  `list`
   is the dispatcher's option list, `count` its length (edi).  -1: a hut fix
   was started for the villager the dispatcher's esi identifies; otherwise
   the new count for the stock `cmp edi, ebx; je nothing`.  cdecl. */
__declspec(dllexport) int __cdecl VvfpFixHutsFilter(int game_id, unsigned int esi, int *list, int count) {
    if (game_id == 3) return vv3_filter(esi, list, count);
    if (game_id == 4) return vv4_filter(esi, list, count);
    if (game_id == 5) return vv5_filter(esi, list, count);
    return count;
}

/* The earlier export, kept for a page built before VvfpFixHutsFilter: on an
   empty list, 1 when a hut fix was started, else 0.  With construction
   rolled away (VV4/VV5) it now answers 0, as the filter does. */
__declspec(dllexport) int __cdecl VvfpFixHutsDecide(int game_id, unsigned int esi) {
    int none[1] = { 0 };
    return VvfpFixHutsFilter(game_id, esi, none, 0) == -1;
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

/* Builders sent to hut work regardless of the food supply, counted for the
   tests.  TEST build only (VVFP_TEST), like the counters above. */
#ifdef VVFP_TEST
__declspec(dllexport) int VvfpFixHutsFoodBypasses = 0;
#define FIX_HUTS_COUNT_BYPASS (++VvfpFixHutsFoodBypasses)
#else
#define FIX_HUTS_COUNT_BYPASS ((void)0)
#endif

/* When a builder has hut work to do (Codex on #464): a population hut still
   unbuilt, or -- below Building level 3, where the owner wants builders to
   fix huts "if at least one is built", every one built included -- at least
   one built. */
static int vv1_builder_has_hut_work(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    if (vv1_huts_incomplete(village)) return 1;
    return *(const int *)(state + 0xA2CC) < 3 && !vv1_none_complete(village);
}

static int vv2_builder_has_hut_work(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    if (vv2_huts_incomplete(village)) return 1;
    return *(const int *)(state + 0x2EA84) < 3
        && (state[0x2E818] == 1 || state[0x2E820] == 1 || state[0x2E828] == 1);
}

static int __cdecl vv1_builder_first(const unsigned char *village, unsigned int index) {
    if (*(const int *)(village + index * 0x3D8u + 0x3D0u) != 4 || !vv1_builder_has_hut_work(village)) {
        return 0;
    }
    FIX_HUTS_COUNT_BYPASS;
    return 1;
}

static int __cdecl vv2_builder_first(const unsigned char *village, const unsigned char *record) {
    if (*(const int *)(record + 0x7F8u) != 5 || !vv2_builder_has_hut_work(village)) {
        return 0;
    }
    FIX_HUTS_COUNT_BYPASS;
    return 1;
}

/* VV3-VV5 pick numbering: 4 Building, 2 Healing.  A healer's pick waits
   behind the same farming attempt (the 50% food swap already spares job 2);
   while "VVFP Work First.dll" (Builders and Healers Work First) is shipped,
   it is dispatched at once too. */
static int work_first_present(void);

static int __cdecl later_builder_first(const struct later_game *g, int pick) {
    /* A builder: always.  VV3-VV5 have no level gate before their hut site,
       so a builder always has hut work -- this companion's fix while a hut is
       unbuilt, the stock "fix a hut" option once every one is built -- and the
       owner wants it done "at all food levels" (Codex on #464).  A healer:
       whenever the addendum is shipped -- "Healers should not be gated by
       huts at all". */
    (void)g;
    if (pick != 4 && !(pick == 2 && work_first_present())) {
        return 0;
    }
    FIX_HUTS_COUNT_BYPASS;
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

/* The Building-level gates (A New Home, The Lost Children only). */
static const struct site LEVEL_SITES[6] = {
    { 0 },
    { VV1_LEVEL_SITE, VV1_LEVEL_STOCK, sizeof VV1_LEVEL_STOCK, vv1_level_stub },
    { VV2_LEVEL_SITE, VV2_LEVEL_STOCK, sizeof VV2_LEVEL_STOCK, vv2_level_stub },
    { 0 }, { 0 }, { 0 },
};
static int level_install_state[6];


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
    if (level_install_state[game_id] == 0) {
        level_install_state[game_id] = install_site(&LEVEL_SITES[game_id]) ? 1 : -1;
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

#ifdef VVFP_TEST
/* For the test build only: the level-gate site, its stock bytes, what it
   becomes, the stub. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbeLevelSite(int game_id, unsigned int *va,
                                                               unsigned char *stock,
                                                               unsigned char *patched,
                                                               unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    s = &LEVEL_SITES[game_id];
    if (s->va == 0) {
        return 0;
    }
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* For the test build only: the food site, its stock bytes, what it
   becomes, the stub. */
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

/* For the test build only: the site, its stock bytes, what it becomes,
   the stub. */
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

/* For the test build only: the choosers over a caller-supplied village
   image (VV1/VV2) -- the game's own offsets are read, so the test lays the flags
   out where the game keeps them. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbeChoose(int game_id, const void *village) {
    if (game_id == 1) return vv1_choose((const unsigned char *)village);
    if (game_id == 2) return vv2_choose((const unsigned char *)village);
    return -2;
}

/* For the test build only: `pick` over a mask, with the RNG seeded. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbePick(unsigned int mask, unsigned int seed) {
    pick_state = seed ? seed : 1u;
    return pick(mask);
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
