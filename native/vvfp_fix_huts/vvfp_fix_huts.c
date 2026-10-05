/* VVFP Fix Huts -- Builders fix huts when no building project is available.

   The owner: "When no building projects are present/available to be worked
   on AND not all population huts are complete, then builders will fix huts
   to increase their skill (just makes it able to be autonomously chosen;
   applies during catch-up time and live playing)."  All five games.

   WHAT THE STOCK GAMES DO, read from the executables.   Every game has one
   Building dispatcher, called with the villager's preferred job by the idle
   scheduler in live play and directly by the catch-up worker (A New Home
   0x42E790, The Lost Children 0x43B4D0, The Secret City 0x45BF00, The Tree
   of Life 0x465750, New Believers 0x46E8E0), which never runs the idle
   scheduler:

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

   Everything this companion changes happens about three times in four:
   one roll per decision of the idle scheduler, shared with Builders and
   Healers Work First, Healers Study and Builder Action Fixes (see "About
   three times in four" below); when it fails, every site runs the stock
   code.  One change is not a choice and holds on every decision: in A New
   Home (at or below its population numbers) and The Lost Children the second
   and third population hut count as construction only once the player has
   worked on them, and then until they
   are finished (see "Huts need a manual start" below).

   Installed at run time by VvfpFixHutsInstall(game) from a companion that
   already runs every frame in that game; the stock bytes at the site are
   verified first, and any other build installs nothing. */
#include <windows.h>
#include <string.h>
#include <intrin.h>
#include "../shared/patcher_files.h"  /* the patcher's folder; full-path, wide loads */

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

/* ---- About three times in four: one roll per decision -------------------- */
/* The owner: "For all 5 games there should still be a chance of doing other
   things too like stock.  The 'Fix Huts' and 'Builder Action Fixes' patch
   (and any other patch that increases certain behaviors) should increase the
   LIKELIHOOD of villagers doing that action, not 100% replaces them" -- 75%,
   once per decision: each time the game chooses what a builder or healer
   does, one roll decides whether the patches step in at all; if it passes
   they act together (own work first, construction before a fix, the hut fix
   when idle, the food bypasses), and if it fails the stock game decides that
   turn unchanged.

   A decision is one run of the game's idle scheduler for one villager, which
   this companion wraps (SCHED_SITES below):

     VV1 0x448220, VV2 0x461850   thiscall(index), ret 4
     VV3 0x45BFE0                 thiscall(record), ret 4
     VV4 0x465840, VV5 0x46F070   thiscall(), ret

   The Secret City, The Tree of Life and New Believers call their scheduler
   only from their "choose the next job" routine, in a retry loop that runs it
   again, at most ten times, while the villager still has no job: VV3 0x45C388
   (counter ebx), VV4 0x465B1A and VV5 0x46F3DA (counter edi) -- each counter
   is zeroed immediately before its loop and incremented by one after each
   call, and nothing else runs between the calls.  That loop is one decision:
   a call from it whose counter is not 0 and is one more than the previous
   scheduler call's, from the same loop for the same villager, continues the
   previous call's decision.  Every other scheduler call starts a new one.

   A New Home and The Lost Children make one call per decision in play
   (0x4487C8, 0x464E9C); their only retry loop is a once-per-load placement
   pass (0x448488, 0x464498) whose counter is NOT zeroed per villager, so a
   continuation there could not be told from the villager's next pass -- each
   of those calls is its own decision.

   The roll is drawn lazily, the first time a patched site asks within the
   decision, from a generator of this companion's own (never the game's RNG,
   so the stock random stream is unchanged).  A patched site reached outside
   any scheduler run -- the Building dispatcher called from elsewhere -- is its
   own decision and draws its own roll; it is reached at most once per call. */
#define VVFP_CHANCE_PERCENT 75u

static unsigned int roll_state;

#ifdef VVFP_TEST
/* force: 0 = the real roll, 1 = always pass, 2 = always fail.  draws: rolls
   drawn.  TEST build only. */
struct vvfp_fix_huts_roll { int force; int draws; };
__declspec(dllexport) struct vvfp_fix_huts_roll VvfpFixHutsRollTest = { 0, 0 };
#endif

static int draw_roll(void) {
    unsigned int x = roll_state;
    if (x == 0) {
        x = (unsigned int)__rdtsc() ^ 0x6C8E9CF5u;
        if (x == 0) {
            x = 0x6C8E9CF5u;
        }
    }
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    roll_state = x;
#ifdef VVFP_TEST
    ++VvfpFixHutsRollTest.draws;
    if (VvfpFixHutsRollTest.force == 1) return 1;
    if (VvfpFixHutsRollTest.force == 2) return 0;
#endif
    return x % 100u < VVFP_CHANCE_PERCENT;
}

struct decision {
    unsigned int ret;          /* the scheduler's return address */
    unsigned int counter;      /* the caller's retry counter at the call */
    unsigned int key;          /* the villager: index, record or object */
    int roll;                  /* -1 not drawn yet, 0 stock, 1 the patches act */
};
#define DECISION_DEPTH 8
static struct decision decisions[DECISION_DEPTH];
static int decision_depth;                 /* scheduler runs in progress */
static struct decision last_decision;      /* the most recent run to finish */
static int last_valid;

/* The retry loop's return address per game (0: none that continues). */
static const unsigned int LOOP_RETURN[6] = { 0, 0, 0, 0x45C38Du, 0x465B1Fu, 0x46F3DFu };

static void __cdecl decision_enter(int game, unsigned int ret, unsigned int counter, unsigned int key) {
    struct decision d;
    d.ret = ret;
    d.counter = counter;
    d.key = key;
    d.roll = -1;
    if (game >= 1 && game <= 5 && LOOP_RETURN[game] != 0 && ret == LOOP_RETURN[game]
        && last_valid && last_decision.ret == ret && last_decision.key == key
        && counter != 0 && counter == last_decision.counter + 1) {
        d.roll = last_decision.roll;        /* the same loop's next attempt */
    }
    if (decision_depth >= 0 && decision_depth < DECISION_DEPTH) {
        decisions[decision_depth] = d;
    }
    ++decision_depth;
}

static void __cdecl decision_exit(void) {
    if (decision_depth > 0) {
        --decision_depth;
    }
    if (decision_depth < DECISION_DEPTH) {
        last_decision = decisions[decision_depth];
        last_valid = 1;
    } else {
        last_valid = 0;
    }
}

/* 1: the patches step in for this decision; 0: the stock game decides. */
static int __cdecl decision_roll(void) {
    if (decision_depth > 0 && decision_depth <= DECISION_DEPTH) {
        struct decision *d = &decisions[decision_depth - 1];
        if (d->roll < 0) {
            d->roll = draw_roll();
        }
        return d->roll;
    }
    return draw_roll();
}

/* For the other behaviour companions ("VVFP Work First.dll", "VVFP Healers
   Study.dll"), so a decision they share with this one rolls once. */
__declspec(dllexport) int __cdecl VvfpFixHutsRoll(void) {
    return decision_roll();
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

     new huts: hut 9 while incomplete (entry 0x447528, the stock hut
       section); hut 10 and hut 11 while incomplete and progress >= 2 or the
       population above 22 / 45 -- see "Huts need a manual start" below --
       population from the game's own counter 0x41CF90 (ecx = village state),
       as the stock checks call it -- each entered through
       vv1_build_hut10 / vv1_build_hut11, which push the hut and run the
       section's own build tail (0x447539: push ebp; mov ecx, esi; call
       0x442090; the started epilogue);
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

static const unsigned int vv1_population_fn = VV1_POPULATION;
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

/* HUTS NEED A MANUAL START.  The stock hut section (0x447528) builds hut 10
   only while the population is above 22 and hut 11 only above 45 (0x44754F,
   0x447581), whatever the hut's progress, although the village drawing
   routine (0x414AE2, 0x414BC7) shows their scaffolds at 15 and 28 villagers
   (or with any progress) and writes progress 1 when it first shows one.  So
   builders started a hut on their own above those numbers and abandoned a
   started one whenever the population fell back (the owner's village,
   v1.35.42: population 17, hut 10 at progress 12, its builders fixing huts).
   The owner: at or below 22 / 45 villagers builders only work on one of
   those huts once the player has dropped a villager on it at least once, and
   then finish it whatever the population; above 22 / 45 they may start it
   themselves, as the stock game does.  A drop works the hut past the drawing
   routine's mark, so hut 10 and hut 11 count as construction exactly while
   they are not complete and their progress is 2 or more or the population is
   above 22 (hut 10) / 45 (hut 11).  Hut 9 has no gate, as in the stock
   game.  The stock section itself is lifted to the
   same test (VV1_GATE below; Builder Action Fixes writes the same bytes into
   the executable), so the stock path and this one agree. */
static int vv1_hut_buildable(const unsigned char *state, unsigned int id, int need_progress) {
    if (vv1_complete(state, id)) return 0;
    if (id != 9 && vv1_progress(state, id) < 2 && vv1_population(state) <= (id == 10 ? 22 : 45)) return 0;
    return !need_progress || vv1_progress(state, id) > 0;
}

/* Build hut 10 / hut 11: the hut, then the stock section's own build tail
   (ebx = 1, ebp = the villager's index, esi = the village, as at 0x447528). */
static const unsigned int vv1_hut_tail = 0x447539u;
static __declspec(naked) void vv1_build_hut10(void) {
    __asm {
        push ebx
        push 10
        jmp dword ptr [vv1_hut_tail]
    }
}
static __declspec(naked) void vv1_build_hut11(void) {
    __asm {
        push ebx
        push 11
        jmp dword ptr [vv1_hut_tail]
    }
}

/* The stock construction entry to take instead of a fix, or 0 when there is
   no construction to do. */
static unsigned int __cdecl vv1_construction(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    const int level = *(const int *)(state + 0xA2CC);
    const int need_progress = vv1_huts_need_progress();
    unsigned int i;
    for (i = 9; i <= 11; ++i) {
        if (vv1_hut_buildable(state, i, need_progress)) {
            if (i == 9) return VV1_HUT_SECTION;
            return (unsigned int)(uintptr_t)(i == 10 ? vv1_build_hut10 : vv1_build_hut11);
        }
    }
    for (i = 0; i < sizeof VV1_PROJECTS / sizeof VV1_PROJECTS[0]; ++i) {
        if (level < VV1_PROJECTS[i].min_level) continue;
        if (!vv1_complete(state, VV1_PROJECTS[i].id) && vv1_progress(state, VV1_PROJECTS[i].id) > 0) {
            return VV1_PROJECTS[i].block;
        }
    }
    return 0;
}

/* The decision's roll first: when it fails (a quarter of the decisions) the
   displaced skip roll runs and the stock branch carries on unchanged. */
static __declspec(naked) void vv1_stub(void) {
    __asm {
        pushad
        call decision_roll
        test eax, eax
        popad
        jz stock_decides
        pushad                         ; construction first, whatever the stock roll
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
    stock_decides:
        push 0x64                      ; the displaced bytes, then the stock code
        call dword ptr [vv1_rand]
        add esp, 4
        jmp dword ptr [vv1_resume]
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
static const unsigned int vv1_level_stock = 0x447664u;   /* the stock cmp / jl, after the displaced mov */
/* Below level 3 a builder fixes any complete population hut -- the owner:
   "below level 3, at all food levels, villagers will fix huts if at least
   one is built and there are no other building projects available" -- and
   with none built, "nothing".  Never the stock random pick the gate used to
   skip (Codex on #463).  Only when the decision's roll passes; otherwise the
   stock compare gives up as it always did. */
static __declspec(naked) void vv1_level_stub(void) {
    __asm {
        mov edx, dword ptr [esi + 0x3E010]
        cmp dword ptr [edx + 0xA2CC], 3
        jl below
        jmp dword ptr [vv1_level_resume]
    below:
        pushad
        call decision_roll
        test eax, eax
        popad
        jnz below_patched
        jmp dword ptr [vv1_level_stock]
    below_patched:
        pushad                         ; construction first, whatever the stock rolls
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
     3. new huts: hut 24 while incomplete (at any progress); hut 25 and hut
        26 while incomplete and progress >= 2 (stock: also population > 22 /
        > 45 -- see "Huts need a manual start" below);
     4. Building level >= 2: project 17 (project 9 complete), project 8
        (progress > 0), project 5 (progress >= 2, [state+0x2EA8C] >= 3);
     5. Building level >= 3: project 12 and project 11 (progress >= 1, not
        complete, [state+0x2EA74] >= 3; 11 also needs project 9 complete).

   A project record is (signed progress dword, complete-flag byte) at state
   + 0x2E754 + id*8 -- in the owner's saves (state + 4 in the .ldw) hut 24
   reads 383/0 while being built and 24/1 once built.  So a failed roll could
   send a builder to fix a hut -- this companion's fix or the stock one --
   while a hut or project the stock game would build was right there.  This
   is the same test without the rolls, in the same order, and it answers
   with the stock code that builds the first one it finds: when the
   decision's roll passes, the hut site and the level gate go STRAIGHT INTO
   that construction (the owner's option A, as A New Home does) instead of a
   hut fix.  Each entry is the instruction just after that construction's own
   test in the Building branch, so the jump always starts it:

     own task 11..20  the task table's handler (0x460550), eax = &record+0x7E0
                      (the handler clears the task only if its project is
                      complete, which the test here excludes)
     project 1        0x4600A7    hut 24 0x45FF0B   hut 25 0x45FF38
     hut 26           0x45FF65    project 17 0x460171   project 8 0x4601A9
     project 5        0x45FF92    project 12 0x46023D   project 11 0x46028C

   Every handler returns "started" (al = bl = 1; ebx is 1 at both sites) and
   pops the dispatcher's frame, which is the frame both sites run in. */

#define VV2_PROGRESS(state, id) (*(const int *)((state) + 0x2E754 + (id) * 8))
#define VV2_DONE(state, id) ((state)[0x2E758 + (id) * 8])

/* The stock entry of the first construction available, or 0 for none. */
static unsigned int __cdecl vv2_construction(const unsigned char *village, unsigned int index) {
    /* [record+0x7E0] task 11..20 -> the project whose flag the stock handler
       tests, and that handler (jump table 0x460550). */
    static const unsigned char task_project[10] = { 24, 25, 26, 5, 7, 8, 1, 17, 12, 11 };
    static const unsigned int task_handler[10] = {
        0x45FEF2u, 0x45FF1Fu, 0x45FF4Cu, 0x45FF79u, 0x45FFA6u,
        0x460036u, 0x45FECDu, 0x45FFD3u, 0x45FFF4u, 0x460015u };
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    int task = *(const int *)(village + index * 0xE48Cu + 0x7E0u);
    int level = *(const int *)(state + 0x2EA84);
    if (task >= 11 && task <= 20 && VV2_DONE(state, task_project[task - 11]) == 0) return task_handler[task - 11];
    if (VV2_DONE(state, 1) != 1 && VV2_PROGRESS(state, 1) > 0 && task == 0) return 0x4600A7u;
    if (VV2_DONE(state, 24) != 1) return 0x45FF0Bu;
    /* The executable's new-hut test (this row's record): worked on by the player. */
    if (VV2_DONE(state, 25) != 1 && VV2_PROGRESS(state, 25) >= 2) return 0x45FF38u;
    if (VV2_DONE(state, 26) != 1 && VV2_PROGRESS(state, 26) >= 2) return 0x45FF65u;
    if (level < 2) return 0;
    if (VV2_DONE(state, 9) != 0 && VV2_PROGRESS(state, 17) > 0 && VV2_DONE(state, 17) == 0) return 0x460171u;
    if (VV2_DONE(state, 8) != 1 && VV2_PROGRESS(state, 8) > 0) return 0x4601A9u;
    if (VV2_DONE(state, 5) != 1 && VV2_PROGRESS(state, 5) >= 2 && *(const int *)(state + 0x2EA8C) >= 3) return 0x45FF92u;
    if (level < 3) return 0;
    if (VV2_PROGRESS(state, 12) >= 1 && VV2_DONE(state, 12) == 0 && *(const int *)(state + 0x2EA74) >= 3) return 0x46023Du;
    if (VV2_PROGRESS(state, 11) >= 1 && VV2_DONE(state, 11) == 0 && VV2_DONE(state, 9) != 0
        && *(const int *)(state + 0x2EA74) >= 3) return 0x46028Cu;
    return 0;
}

static const unsigned int vv2_rand = VV2_RAND, vv2_resume = VV2_RESUME;
static const unsigned int vv2_examine = VV2_EXAMINE, vv2_started = VV2_STARTED;
/* The decision's roll first: when it fails the displaced skip roll runs and
   the stock branch carries on unchanged. */
static __declspec(naked) void vv2_stub(void) {
    __asm {
        pushad
        call decision_roll
        test eax, eax
        popad
        jz stock
        pushad
        push edi                       ; the villager's index
        push esi
        call vv2_construction
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
        mov edx, eax                   ; the construction's stock entry
        mov eax, edi
        imul eax, eax, 0xE48C
        lea eax, [eax + esi + 0x7E0]   ; &record+0x7E0, as the task handlers expect
        jmp edx
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
        call decision_roll
        test eax, eax
        popad
        jz nothing                     ; the roll failed: the stock jl's "nothing"
        pushad
        push edi                       ; the villager's index
        push esi
        call vv2_construction
        add esp, 8
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jnz build_first                ; construction first: never a hut fix
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
    build_first:
        mov edx, eax                   ; the construction's stock entry
        mov eax, edi
        imul eax, eax, 0xE48C
        lea eax, [eax + esi + 0x7E0]
        jmp edx
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

   So, when the decision's roll passes, option 9 is taken out of any list
   that has construction in it, and a list those rolls left without
   construction (empty, or only option 9) while construction stands is given
   that construction back -- every option the dislike rolls removed, by the
   dispatcher's own tests in its own order -- so the stock pick goes STRAIGHT
   INTO it (the owner's option A, as A New Home does); the villager is never
   sent to a hut instead.  Each of those options' handlers starts its job
   unconditionally (VV4 table 0x4642C0, VV5 0x46CE2C), so the rebuilt list
   always starts construction.  Only when there is no construction at all is
   a hut fixed: the stock option 9 when every hut is built, or this
   companion's pick among the built huts when some are not.  The Secret City
   has no such rolls, so there the filter only drops option 9 from a mixed
   list.  When the roll fails, the list is left exactly as the stock code
   built it. */
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
   own tests, in the dispatcher's order, written to `out` (at most 8).
   Returns how many. */
#define ROLLED_OPTION_6 0
static int vv4_rolled_construction(int *out) {
    /* options 1-4, 6, 8, 10, 11 in list order; 0 = option 6's own test */
    static const int options[8] = { 1, 2, 3, 4, 6, 8, 10, 11 };
    static const int projects[8] = { 19, 20, 21, 23, ROLLED_OPTION_6, 22, 25, 24 };
    int i, n = 0;
    for (i = 0; i < 8; ++i) {
        int open;
        if (projects[i] == ROLLED_OPTION_6) {
            /* 0x4396D0(0x4D86A8) < 2 and 0x421570(0x4D86A8) < 100 */
            open = call_count(0x4396D0u, 0x4D86A8u) < 2 && call_count(0x421570u, 0x4D86A8u) < 100;
        } else {
            /* state >= 1 (0x438980) and not complete (0x438960) */
            open = call_state(0x438980u, 0x4D8BF8u, projects[i]) >= 1
                && !later_complete(&VV4, projects[i] - 19);
        }
        if (open) {
            out[n++] = options[i];
        }
    }
    return n;
}

static int vv5_rolled_construction(int *out) {
    /* options 1-4, 6, 8, 11 in list order */
    static const int options[7] = { 1, 2, 3, 4, 6, 8, 11 };
    static const int projects[7] = { 19, 20, 21, 23, ROLLED_OPTION_6, 22, 24 };
    int i, n = 0, count;
    for (i = 0; i < 7; ++i) {
        int open;
        if (projects[i] == ROLLED_OPTION_6) {
            /* 0 < 0x4388D0(0x51DE40) < 100 */
            count = call_count(0x4388D0u, 0x51DE40u);
            open = count > 0 && count < 100;
        } else {
            /* state > 1 (0x43AEA0) and not complete (0x43AE80) */
            open = call_state(0x43AEA0u, 0x51E008u, projects[i]) > 1
                && !later_complete(&VV5, projects[i] - 19);
        }
        if (open) {
            out[n++] = options[i];
        }
    }
    return n;
}

/* The filter.  -1: a hut fix was started (take the stock "started"
   epilogue); otherwise the new option count (0: the stock "nothing").  The
   decision's roll is asked only where the list would change; when it fails,
   the list and the count are returned exactly as the stock code built them. */
static int later_filter(const struct later_game *g, int (*rolled)(int *), unsigned int esi,
                        int *list, int count) {
    int i, fix_at = -1;
    for (i = 0; i < count; ++i) {
        if (list[i] == FIX_A_HUT_OPTION) {
            fix_at = i;
        }
    }
    if (count - (fix_at >= 0 ? 1 : 0) > 0) {
        /* Construction in the list: only a stock option 9 beside it changes. */
        if (fix_at < 0 || !decision_roll()) {
            return count;
        }
        for (i = fix_at; i + 1 < count; ++i) {
            list[i] = list[i + 1];
        }
        list[--count] = 0;
        return count;
    }
    if (rolled != NULL) {
        int taken[8];
        int n = rolled(taken);
        if (n > 0) {
            /* The dislike rolls took every construction option away. */
            if (!decision_roll()) {
                return count;
            }
            for (i = 0; i < n; ++i) {
                list[i] = taken[i];
            }
            for (; i < count; ++i) {
                list[i] = 0;
            }
            return n;                  /* option A: straight into that construction */
        }
    }
    if (count > 0) {
        return count;                  /* only option 9: the stock fix, every hut built */
    }
    {
        int hut = later_choose(g);
        if (hut < 0 || !decision_roll()) {
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
   from the live per-frame caller only -- the catch-up worker calls the
   Building dispatcher directly, so this bypass is live-only):

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
   built, runs the stock code -- and only when the decision's roll passes.
   A different build installs nothing here; in VV1 with Builder Action Fixes
   owning 0x448336 its gate is taken over instead (see vv1_baf_stub). */

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

/* Each bypass asks the decision's roll last, once it would act; a failed
   roll takes the stock path. */
static int __cdecl vv1_builder_first(const unsigned char *village, unsigned int index) {
    if (*(const int *)(village + index * 0x3D8u + 0x3D0u) != 4 || !vv1_builder_has_hut_work(village)
        || !decision_roll()) {
        return 0;
    }
    FIX_HUTS_COUNT_BYPASS;
    return 1;
}

static int __cdecl vv2_builder_first(const unsigned char *village, const unsigned char *record) {
    if (*(const int *)(record + 0x7F8u) != 5 || !vv2_builder_has_hut_work(village)
        || !decision_roll()) {
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
    if (!decision_roll()) {
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
   attempt; else the stock high-food jump, with every register as the stock
   code has it. */
static __declspec(naked) void vv1_food_stub(void) {
    __asm {
        cmp dword ptr [ebp + 0xA2EC], 400
        jl low_path
        pushad
        push edi
        push esi
        call vv1_builder_first
        add esp, 8
        test eax, eax                  ; every register the stock code has, kept
        popad
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
        test eax, eax                  ; every register the stock code has, kept
        popad
        jnz low_path
        jmp dword ptr [vv2_food_high]
    low_path:
        jmp dword ptr [vv2_food_low]
    }
}

/* Builder Action Fixes (A New Home, an executable-only row) owns the same
   400-food gate: its jmp at 0x448336 leads to a cave at 0x4568A0 that sends
   every villager whose selected job is Building to the preferred-job attempt
   at 400+ food -- about three times in four, by a roll of the cave's own
   (the processor's time-stamp counter, hashed), since without this companion
   nothing else rolls for the decision.  With this companion loaded the two
   would roll separately for one decision, so the companion takes the gate
   over: after verifying the row's exact jmp and cave bytes it points the jmp
   at this stub, which makes the same Building test and asks the decision's
   own roll.  Any other bytes there install nothing. */
#define VV1_BAF_CAVE_VA 0x4568A0u
static const unsigned char VV1_BAF_JUMP[12] = {
    0xE9, 0x65, 0xE5, 0x00, 0x00, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
static const unsigned char VV1_BAF_CAVE[65] = {
    0x81, 0xBD, 0xEC, 0xA2, 0x00, 0x00, 0x90, 0x01, 0x00, 0x00, 0x0F, 0x8C, 0x92, 0x1A, 0xFF, 0xFF,
    0x50, 0x52, 0x89, 0xF8, 0x69, 0xC0, 0xD8, 0x03, 0x00, 0x00, 0x83, 0xBC, 0x30, 0xD0, 0x03, 0x00,
    0x00, 0x04, 0x75, 0x16, 0x0F, 0x31, 0x69, 0xC0, 0xB9, 0x79, 0x37, 0x9E, 0x3D, 0x00, 0x00, 0x00,
    0x40, 0x72, 0x07, 0x5A, 0x58, 0xE9, 0x68, 0x1A, 0xFF, 0xFF, 0x5A, 0x58, 0xE9, 0x8E, 0x1A, 0xFF,
    0xFF };

static int __cdecl vv1_baf_first(const unsigned char *village, unsigned int index) {
    if (*(const int *)(village + index * 0x3D8u + 0x3D0u) != 4 || !decision_roll()) {
        return 0;
    }
    FIX_HUTS_COUNT_BYPASS;
    return 1;
}

static __declspec(naked) void vv1_baf_stub(void) {
    __asm {
        cmp dword ptr [ebp + 0xA2EC], 400
        jl low_path
        pushad
        push edi
        push esi
        call vv1_baf_first
        add esp, 8
        test eax, eax
        popad
        jnz low_path
        jmp dword ptr [vv1_food_high]
    low_path:
        jmp dword ptr [vv1_food_low]
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
    if (work_first_state != 0) {
        return work_first_state == 1;
    }
    work_first_state = -1;
    work_first_module = vvfp_load_patcher_dll("VVFP Work First.dll");
    if (work_first_module == NULL) {
        return 0;
    }
    work_first_state = 1;
    return 1;
}

static void work_first_bridge(int game_id) {
    int (__stdcall *install)(int);
    void (__stdcall *set_roll)(int (__cdecl *)(void));
    if (work_first_installed[game_id] != 0 || !work_first_present()) {
        return;
    }
    work_first_installed[game_id] = -1;
    /* The addendum acts inside the same decisions: it asks this companion's
       roll, so one decision rolls once. */
    set_roll = (void (__stdcall *)(int (__cdecl *)(void)))GetProcAddress(work_first_module, "VvfpWorkFirstSetRoll");
    if (set_roll != NULL) {
        set_roll(VvfpFixHutsRoll);
    }
    install = (int (__stdcall *)(int))GetProcAddress(work_first_module, "VvfpWorkFirstInstall");
    if (install != NULL && install(game_id)) {
        work_first_installed[game_id] = 1;
    }
}

/* ---- The decision: wrapping the idle scheduler ---------------------------- */
/* Each game's scheduler entry jumps here; the wrapper opens the decision
   (decision_enter: the return address, the caller's retry counter and the
   villager), runs the stock scheduler -- the displaced prologue, then its
   body -- with the same argument, closes the decision and returns as the
   scheduler does.  Every register the scheduler receives is the caller's;
   eax, which it returns, is passed back. */
static const unsigned int vv1_sched_body = 0x448228u, vv2_sched_body = 0x461858u;
static const unsigned int vv3_sched_body = 0x45BFE6u, vv4_sched_body = 0x465846u;
static const unsigned int vv5_sched_body = 0x46F075u;

/* VV1/VV2: push ebx; push ebp; push esi; push edi; mov edi, [esp+0x14]. */
static __declspec(naked) void vv1_sched_original(void) {
    __asm {
        push ebx
        push ebp
        push esi
        push edi
        mov edi, dword ptr [esp + 0x14]
        jmp dword ptr [vv1_sched_body]
    }
}
static __declspec(naked) void vv2_sched_original(void) {
    __asm {
        push ebx
        push ebp
        push esi
        push edi
        mov edi, dword ptr [esp + 0x14]
        jmp dword ptr [vv2_sched_body]
    }
}
/* VV3: push ecx; push esi; mov esi, [esp+0xC]. */
static __declspec(naked) void vv3_sched_original(void) {
    __asm {
        push ecx
        push esi
        mov esi, dword ptr [esp + 0xC]
        jmp dword ptr [vv3_sched_body]
    }
}
/* VV4: sub esp, 8; push esi; mov esi, ecx.  VV5: sub esp, 8; push ebx; push esi. */
static __declspec(naked) void vv4_sched_original(void) {
    __asm {
        sub esp, 8
        push esi
        mov esi, ecx
        jmp dword ptr [vv4_sched_body]
    }
}
static __declspec(naked) void vv5_sched_original(void) {
    __asm {
        sub esp, 8
        push ebx
        push esi
        jmp dword ptr [vv5_sched_body]
    }
}

/* One argument ([esp+4]: VV1/VV2 the index, VV3 the record, the key), ret 4;
   the caller's retry counter is ebx (only VV3's is ever continued). */
#define SCHED_STUB_ARG(NAME, GAME)                                            \
    static __declspec(naked) void NAME##_sched_stub(void) {                   \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push dword ptr [esp + 0x24]      /* the villager */        \
            __asm push ebx                         /* the retry counter */   \
            __asm push dword ptr [esp + 0x28]      /* the return address */  \
            __asm push GAME                                                  \
            __asm call decision_enter                                        \
            __asm add esp, 16                                                \
            __asm popad                                                      \
            __asm push dword ptr [esp + 4]                                   \
            __asm call NAME##_sched_original                                 \
            __asm push eax                                                   \
            __asm call decision_exit                                         \
            __asm pop eax                                                    \
            __asm ret 4                                                      \
        }                                                                    \
    }

/* No argument (ecx, the villager object, is the key), plain ret; the retry
   counter is edi. */
#define SCHED_STUB_OBJECT(NAME, GAME)                                         \
    static __declspec(naked) void NAME##_sched_stub(void) {                   \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push ecx                         /* the villager */        \
            __asm push edi                         /* the retry counter */   \
            __asm push dword ptr [esp + 0x28]      /* the return address */  \
            __asm push GAME                                                  \
            __asm call decision_enter                                        \
            __asm add esp, 16                                                \
            __asm popad                                                      \
            __asm call NAME##_sched_original                                 \
            __asm push eax                                                   \
            __asm call decision_exit                                         \
            __asm pop eax                                                    \
            __asm ret                                                        \
        }                                                                    \
    }

SCHED_STUB_ARG(vv1, 1)
SCHED_STUB_ARG(vv2, 2)
SCHED_STUB_ARG(vv3, 3)
SCHED_STUB_OBJECT(vv4, 4)
SCHED_STUB_OBJECT(vv5, 5)

/* The Secret City has no per-frame companion to write a detour from, so its
   row's page carries a stub at the scheduler entry that resolves this export
   once and jumps to it with the stack and every register untouched. */
__declspec(dllexport) __declspec(naked) void VvfpFixHutsScheduler3(void) {
    __asm {
        jmp vv3_sched_stub
    }
}

/* ---- The decision in catch-up: wrapping the catch-up worker --------------- */
/* Time passing while the game was closed, and Time Warp, never run the idle
   scheduler: each game's catch-up worker picks a job and dispatches it
   itself, and several patches can act on that one choice -- Builders and
   Healers Work First at the pick dispatch or the research pick, this
   companion's own sites inside the Building dispatcher, and in The Lost
   Children Healers Study's plant-study continuation.  Outside a decision
   each of them used to draw its own roll, so a villager could get an
   intervention far more often than three times in four (Codex on #494: a
   plant-studying healer about 94%).  So the worker is a decision too: its
   entry opens one (decision_enter, never a continuation), every patch the
   choice reaches asks this companion's roll and shares it, and the exit
   closes it.  One worker call is one decision.

     VV1 0x42E790  push esi; mov esi, [esp+8]; push edi        thiscall(index), ret 4
     VV2 0x43B4D0  push ebx; push esi; push edi; mov edi, [esp+0x10]   (index), ret 4
     VV3 0x45BF00  push esi; mov esi, [esp+8]; push edi        (record), ret 4 -- the
                   row's page stub resolves VvfpFixHutsCatchUp3
     VV4 0x465750  push esi; mov esi, ecx; call 0x468C60       thiscall(), ret
     VV5 0x46E8E0  push esi; mov esi, ecx; call 0x473440       thiscall(), ret */
static const unsigned int vv1_cu_body = 0x42E796u, vv2_cu_body = 0x43B4D7u, vv3_cu_body = 0x45BF06u;
static const unsigned int vv4_cu_body = 0x465758u, vv5_cu_body = 0x46E8E8u;
static const unsigned int vv4_cu_prep = 0x468C60u, vv5_cu_prep = 0x473440u;

static __declspec(naked) void vv1_cu_original(void) {
    __asm {
        push esi
        mov esi, dword ptr [esp + 8]
        push edi
        jmp dword ptr [vv1_cu_body]
    }
}
static __declspec(naked) void vv2_cu_original(void) {
    __asm {
        push ebx
        push esi
        push edi
        mov edi, dword ptr [esp + 0x10]
        jmp dword ptr [vv2_cu_body]
    }
}
static __declspec(naked) void vv3_cu_original(void) {
    __asm {
        push esi
        mov esi, dword ptr [esp + 8]
        push edi
        jmp dword ptr [vv3_cu_body]
    }
}
static __declspec(naked) void vv4_cu_original(void) {
    __asm {
        push esi
        mov esi, ecx
        call dword ptr [vv4_cu_prep]
        jmp dword ptr [vv4_cu_body]
    }
}
static __declspec(naked) void vv5_cu_original(void) {
    __asm {
        push esi
        mov esi, ecx
        call dword ptr [vv5_cu_prep]
        jmp dword ptr [vv5_cu_body]
    }
}

#define CU_STUB_ARG(NAME, GAME)                                               \
    static __declspec(naked) void NAME##_cu_stub(void) {                      \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push dword ptr [esp + 0x24]      /* the villager */        \
            __asm push 0                           /* no retry counter */    \
            __asm push dword ptr [esp + 0x28]      /* the return address */  \
            __asm push GAME                                                  \
            __asm call decision_enter                                        \
            __asm add esp, 16                                                \
            __asm popad                                                      \
            __asm push dword ptr [esp + 4]                                   \
            __asm call NAME##_cu_original                                    \
            __asm push eax                                                   \
            __asm call decision_exit                                         \
            __asm pop eax                                                    \
            __asm ret 4                                                      \
        }                                                                    \
    }

#define CU_STUB_OBJECT(NAME, GAME)                                            \
    static __declspec(naked) void NAME##_cu_stub(void) {                      \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push ecx                         /* the villager */        \
            __asm push 0                           /* no retry counter */    \
            __asm push dword ptr [esp + 0x28]      /* the return address */  \
            __asm push GAME                                                  \
            __asm call decision_enter                                        \
            __asm add esp, 16                                                \
            __asm popad                                                      \
            __asm call NAME##_cu_original                                    \
            __asm push eax                                                   \
            __asm call decision_exit                                         \
            __asm pop eax                                                    \
            __asm ret                                                        \
        }                                                                    \
    }

CU_STUB_ARG(vv1, 1)
CU_STUB_ARG(vv2, 2)
CU_STUB_ARG(vv3, 3)
CU_STUB_OBJECT(vv4, 4)
CU_STUB_OBJECT(vv5, 5)

/* The Secret City: the row's page carries a stub at the worker's entry that
   resolves this export once and jumps to it with the stack and every
   register untouched. */
__declspec(dllexport) __declspec(naked) void VvfpFixHutsCatchUp3(void) {
    __asm {
        jmp vv3_cu_stub
    }
}

/* ---- Huts need a manual start: the stock hut gates ---------------------- */
/* A New Home and The Lost Children decide in their Building branch whether a
   builder may work on the second and third population hut:

     A New Home     0x44754A  hut 10: population > 22; hut 11 (0x447576):
                              population > 45 -- progress never tested; now
                              also progress >= 2 at any population.  The
                              scaffold shows at 15 and 28 (drawing routine
                              0x414AE2, 0x414BC7), or with any progress, and
                              gets progress 1 when it first shows.
     The Lost Children
                    0x4600DE  hut 25: population > 22 and progress >= 2;
                              hut 26 (0x460102): population > 45 and
                              progress >= 2.  The scaffold shows at 21 and 46
                              (0x4196E8, 0x419763), or with any progress, and
                              gets progress 1 when it first shows.

   The owner: builders start work on those huts only once the player has
   dropped a villager on one at least once, and then finish it whatever the
   population.  Progress 1 is the drawing routine's mark; a villager's work
   takes it past that.  So each test becomes: not complete and progress >= 2,
   with no population test -- in the stock bytes, so every decision uses it
   (it decides WHICH huts are construction; how often a builder builds is
   untouched).  Hut 9 / hut 24 and every other test in the branch are
   unchanged; ecx is the village state on entry, bl 1, and the builds are the
   branch's own (A New Home: push ebx; push 10 into the hut-9 tail 0x447539,
   hut 11 into its own block 0x447594; The Lost Children: its hut-25 / hut-26
   blocks 0x45FF38 / 0x45FF65).  The int3 bytes are never reached.

   Only A New Home's is written here (Builder Action Fixes writes the same
   bytes into the executable, data/builds.json, so they are accepted as
   already in place; any other bytes: nothing is written).  The Lost
   Children's companion is installed only once the village is first drawn,
   after the session's load-time catch-up has run, so its test is written
   into the executable by the Builders Fix Huts When Idle row itself
   (scripts/build_vvfp_fix_huts_features.py, GATE_PATCHES) and
   vv2_construction mirrors it. */
struct gate {
    unsigned int va;
    const unsigned char *stock;
    const unsigned char *lifted;
    int length;
};
static const unsigned char VV1_GATE_STOCK[74] = {
    0xE8, 0x41, 0x5A, 0xFD, 0xFF, 0x83, 0xF8, 0x16, 0x7E, 0x22, 0x8B, 0x96, 0x10, 0xE0, 0x03, 0x00,
    0x38, 0x9A, 0xF0, 0x9F, 0x00, 0x00, 0x74, 0x14, 0x53, 0x6A, 0x0A, 0x55, 0x8B, 0xCE, 0xE8, 0x23,
    0xAB, 0xFF, 0xFF, 0x5F, 0x5D, 0x8A, 0xC3, 0x5B, 0x5E, 0xC2, 0x08, 0x00, 0x8B, 0x8E, 0x10, 0xE0,
    0x03, 0x00, 0xE8, 0x0F, 0x5A, 0xFD, 0xFF, 0x83, 0xF8, 0x2D, 0x7E, 0x4B, 0x8B, 0x86, 0x10, 0xE0,
    0x03, 0x00, 0x38, 0x98, 0xF8, 0x9F, 0x00, 0x00, 0x74, 0x3D };
static const unsigned char VV1_GATE_LIFTED[74] = {
    0x38, 0x99, 0xF0, 0x9F, 0x00, 0x00, 0x74, 0x21, 0x83, 0xB9, 0xEC, 0x9F, 0x00, 0x00, 0x01, 0x7F,
    0x0A, 0xE8, 0x30, 0x5A, 0xFD, 0xFF, 0x83, 0xF8, 0x16, 0x7E, 0x0E, 0x53, 0x6A, 0x0A, 0xEB, 0xCF,
    0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0x8B, 0x8E, 0x10, 0xE0, 0x03, 0x00, 0x38,
    0x99, 0xF8, 0x9F, 0x00, 0x00, 0x74, 0x50, 0x83, 0xB9, 0xF4, 0x9F, 0x00, 0x00, 0x01, 0x7F, 0x0A,
    0xE8, 0x01, 0x5A, 0xFD, 0xFF, 0x83, 0xF8, 0x2D, 0x7E, 0x3D };
static const struct gate GATES[6] = {
    { 0 },
    { 0x44754Au, VV1_GATE_STOCK, VV1_GATE_LIFTED, sizeof VV1_GATE_STOCK },
    { 0 }, { 0 }, { 0 }, { 0 },
};
static int gate_install_state[6];

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};

/* Committed executable code at `va` holding exactly `bytes`. */
static int code_matches(unsigned int va, const unsigned char *bytes, int length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, bytes, (size_t)length) == 0;
}

static int site_is_stock(const struct site *s) {
    return code_matches(s->va, s->stock, s->length);
}

/* The lifted hut gate: already there (Builder Action Fixes), or written over
   the exact stock bytes.  1 when it is in place. */
static int install_gate(const struct gate *g) {
    unsigned char *at;
    DWORD old;
    if (g->va == 0) {
        return 0;
    }
    if (code_matches(g->va, g->lifted, g->length)) {
        return 1;
    }
    if (!code_matches(g->va, g->stock, g->length)) {
        return 0;
    }
    at = (unsigned char *)(uintptr_t)g->va;
    if (!VirtualProtect(at, (SIZE_T)g->length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, g->lifted, (size_t)g->length);
    VirtualProtect(at, (SIZE_T)g->length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)g->length);
    return 1;
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

/* The scheduler entries (The Secret City's is executable-side). */
static const unsigned char VV1_SCHED_STOCK[8] = { 0x53, 0x55, 0x56, 0x57, 0x8B, 0x7C, 0x24, 0x14 };
static const unsigned char VV2_SCHED_STOCK[8] = { 0x53, 0x55, 0x56, 0x57, 0x8B, 0x7C, 0x24, 0x14 };
static const unsigned char VV4_SCHED_STOCK[6] = { 0x83, 0xEC, 0x08, 0x56, 0x8B, 0xF1 };
static const unsigned char VV5_SCHED_STOCK[5] = { 0x83, 0xEC, 0x08, 0x53, 0x56 };
static const struct site SCHED_SITES[6] = {
    { 0 },
    { 0x448220u, VV1_SCHED_STOCK, sizeof VV1_SCHED_STOCK, vv1_sched_stub },
    { 0x461850u, VV2_SCHED_STOCK, sizeof VV2_SCHED_STOCK, vv2_sched_stub },
    { 0 },
    { 0x465840u, VV4_SCHED_STOCK, sizeof VV4_SCHED_STOCK, vv4_sched_stub },
    { 0x46F070u, VV5_SCHED_STOCK, sizeof VV5_SCHED_STOCK, vv5_sched_stub },
};
static int sched_install_state[6];

/* The catch-up workers' entries (The Secret City's is executable-side). */
static const unsigned char VV1_CU_STOCK[6] = { 0x56, 0x8B, 0x74, 0x24, 0x08, 0x57 };
static const unsigned char VV2_CU_STOCK[7] = { 0x53, 0x56, 0x57, 0x8B, 0x7C, 0x24, 0x10 };
static const unsigned char VV4_CU_STOCK[8] = { 0x56, 0x8B, 0xF1, 0xE8, 0x08, 0x35, 0x00, 0x00 };
static const unsigned char VV5_CU_STOCK[8] = { 0x56, 0x8B, 0xF1, 0xE8, 0x58, 0x4B, 0x00, 0x00 };
static const struct site CU_SITES[6] = {
    { 0 },
    { 0x42E790u, VV1_CU_STOCK, sizeof VV1_CU_STOCK, vv1_cu_stub },
    { 0x43B4D0u, VV2_CU_STOCK, sizeof VV2_CU_STOCK, vv2_cu_stub },
    { 0 },
    { 0x465750u, VV4_CU_STOCK, sizeof VV4_CU_STOCK, vv4_cu_stub },
    { 0x46E8E0u, VV5_CU_STOCK, sizeof VV5_CU_STOCK, vv5_cu_stub },
};
static int cu_install_state[6];

/* A New Home's 400-food gate as Builder Action Fixes leaves it. */
static const struct site VV1_BAF_SITE = { VV1_FOOD_SITE, VV1_BAF_JUMP, sizeof VV1_BAF_JUMP, vv1_baf_stub };

static int baf_cave_is_ours(void) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)VV1_BAF_CAVE_VA;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, VV1_BAF_CAVE, sizeof VV1_BAF_CAVE) == 0;
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

/* Called by a companion that runs every frame in the game.  Idempotent.
   The scheduler wrapper goes in first and everything else only after it:
   without it a decision could not be told apart, so nothing else is
   installed (the stock game runs).  After it, the hut site, the level gate,
   the lifted hut gate and the food site are independent: any may be absent
   (another patch owns its bytes) without holding back the others.  Returns
   whether the hut site is installed, as before. */
__declspec(dllexport) int __stdcall VvfpFixHutsInstall(int game_id) {
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    if (sched_install_state[game_id] == 0) {
        sched_install_state[game_id] = install_site(&SCHED_SITES[game_id]) ? 1 : -1;
    }
    if (sched_install_state[game_id] != 1) {
        return 0;
    }
    if (level_install_state[game_id] == 0) {
        level_install_state[game_id] = install_site(&LEVEL_SITES[game_id]) ? 1 : -1;
    }
    if (gate_install_state[game_id] == 0) {
        gate_install_state[game_id] = install_gate(&GATES[game_id]) ? 1 : -1;
    }
    if (food_install_state[game_id] == 0) {
        food_install_state[game_id] = install_site(&FOOD_SITES[game_id]) ? 1 : -1;
        if (food_install_state[game_id] != 1 && game_id == 1 && baf_cave_is_ours()
            && install_site(&VV1_BAF_SITE)) {
            food_install_state[game_id] = 2;       /* Builder Action Fixes' gate, taken over */
        }
    }
    if (cu_install_state[game_id] == 0) {
        cu_install_state[game_id] = install_site(&CU_SITES[game_id]) ? 1 : -1;
    }
    work_first_bridge(game_id);
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = install_site(&SITES[game_id]) ? 1 : -1;
    return install_state[game_id] == 1;
}

#ifdef VVFP_TEST
/* For the test build only: the hut gate, its stock bytes and its lifted
   bytes. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbeGate(int game_id, unsigned int *va,
                                                          unsigned char *stock,
                                                          unsigned char *lifted) {
    const struct gate *g;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    g = &GATES[game_id];
    if (g->va == 0) {
        return 0;
    }
    *va = g->va;
    memcpy(stock, g->stock, (size_t)g->length);
    memcpy(lifted, g->lifted, (size_t)g->length);
    return g->length;
}

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

/* For the test build only: a site table entry, its bytes, what it becomes,
   the stub.  which: 0 the scheduler entry, 1 Builder Action Fixes' gate. */
__declspec(dllexport) int __stdcall VvfpFixHutsProbeDecisionSite(int game_id, int which, unsigned int *va,
                                                                  unsigned char *stock,
                                                                  unsigned char *patched,
                                                                  unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    if (which == 1) {
        if (game_id != 1) return 0;
        s = &VV1_BAF_SITE;
    } else {
        s = &SCHED_SITES[game_id];
    }
    if (s->va == 0) {
        return 0;
    }
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* For the test build only: open / close a decision as the scheduler wrapper
   does, seed the roll's generator, and read the decision state. */
__declspec(dllexport) void __stdcall VvfpFixHutsProbeEnter(int game_id, unsigned int ret, unsigned int counter,
                                                           unsigned int key) {
    decision_enter(game_id, ret, counter, key);
}

__declspec(dllexport) void __stdcall VvfpFixHutsProbeExit(void) {
    decision_exit();
}

__declspec(dllexport) void __stdcall VvfpFixHutsProbeSeedRoll(unsigned int seed) {
    roll_state = seed;
    decision_depth = 0;
    last_valid = 0;
}

__declspec(dllexport) int __stdcall VvfpFixHutsProbeDepth(void) {
    return decision_depth;
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
