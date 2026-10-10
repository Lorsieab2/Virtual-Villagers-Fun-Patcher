/* VVFP Healers Study -- healers keep studying plants regardless of the food
   supply (A New Home, The Lost Children).

   The owner: "Healers study plants (VV1-VV2) or study medicine regardless of
   the food supply (for VV4 and VV5, only if the Hospital is accessible/
   built)."  The Secret City, The Tree of Life and New Believers read no food
   total on the way to their medicine study (and VV4/VV5 already require the
   Hospital), so only A New Home and The Lost Children need this.

   WHAT THE STOCK GAMES DO, read from the executables.  The idle scheduler,
   reached from the live per-frame caller only (catch-up has its own worker;
   see CATCH-UP below):

     VV1 0x448220  cmp [state+0xA2EC], 400; jge 0x44836F.  Below 400 it tries
                   the preferred job and then 0x447CD0(index, 60), which
                   continues the villager's last activity [record+0x3B8]; for
                   activity 9 (plant study) that starts "Studying medical
                   cactus" (0x443270) when Healing >= 1 or the village flag
                   [state+0xA30C] is clear.  At 400 food or more both are
                   skipped, so a healer who was studying stops.
     VV2 0x461850  the same at 300 food: below it, 0x460590(index, 40)
                   continues state [record+0x7E0]; state 9 is plant study
                   (Healing >= 1 or the flag, then one of four plants).

   Plant-study state 9 is set only when the player drops a villager on a plant
   (and, in VV2, by Easier Healing Mastery when no one is sick).

   WHAT THIS COMPANION DOES.  At the high-food target -- the first
   instruction of the general selection (VV1 0x44836F, VV2 0x461A22), which
   the low-food path also falls into -- a villager in plant-study state 9 at
   or above the threshold gets the same continuation call the stock game makes
   below it; if that starts a job, the scheduler's own "done" epilogue runs
   (VV1 0x44843D, VV2 0x461AF0).  Below the threshold (the stock code already
   made the call), for every other state, and when the continuation starts
   nothing, the displaced instructions run and the stock selection continues.

   CATCH-UP.  The scheduler is never run for time that passed while the game
   was closed, or for Time Warp.  Neither game's catch-up continues a
   studying villager's plant study the way the scheduler does: The Lost
   Children's never does, and A New Home's only when catch-up happens to
   pick the Healing job for that villager and nobody is sick (its
   dispatcher's Healing case, 0x4478EF).  So each gets a second site in its
   catch-up worker (see "VV1 catch-up" and "VV2 catch-up" below).

   Installed at run time by VvfpHealersStudyInstall(game) from the Origins
   companion, which runs every frame; the stock bytes at each site are
   verified first, and any other build installs nothing. */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include <intrin.h>

/* Counters the tests read.  Compiled only into the TEST build (VVFP_TEST,
   tests/test_dlls/): the shipped DLL carries no counters and no probe. */
#ifdef VVFP_TEST
struct vvfp_healers_stats {
    int checks;         /* a studying villager reached the site at high food */
    int continued;      /* the continuation started a job */
};
__declspec(dllexport) struct vvfp_healers_stats VvfpHealersStudyStats = { 0 };
#define HEALERS_COUNT_CHECK ++VvfpHealersStudyStats.checks
#else
#define HEALERS_COUNT_CHECK ((void)0)
#endif

/* ---- About three times in four ------------------------------------------------ */
/* The owner: the behaviour patches "should increase the LIKELIHOOD of
   villagers doing that action, not 100% replace them" -- 75%, one roll per
   decision shared by every patch in it.  A decision is one run of the idle
   scheduler (A New Home 0x448220, The Lost Children 0x461850) or, in
   catch-up, of the catch-up worker (The Lost Children 0x43B4D0), both of
   which "VVFP Fix Huts.dll" (Builders Fix Huts When Idle) wraps -- so the
   catch-up site below and Builders and Healers Work First's hook on the
   pick it then dispatches share one roll (Codex on #494); when that DLL is loaded
   this companion asks its VvfpFixHutsRoll, so a healer's decision that also
   meets Builders and Healers Work First rolls once.  Without it (this row
   ticked alone) there is nothing else in the decision to share with, and
   this site is reached at most once per scheduler run: it draws a 75% roll
   of its own each time it would act.  Neither roll touches the game's RNG. */
static int (__cdecl *shared_roll)(void);
static unsigned int own_roll_state;

#ifdef VVFP_TEST
/* force: 0 = the real own roll, 1 = pass, 2 = fail; draws: own rolls drawn.
   TEST build only. */
struct vvfp_own_roll_test { int force; int draws; };
__declspec(dllexport) struct vvfp_own_roll_test VvfpHealersStudyRollTest = { 0, 0 };
#endif

static int own_roll(void) {
    unsigned int x = own_roll_state;
    if (x == 0) {
        x = (unsigned int)__rdtsc() ^ 0x1B873593u;
        if (x == 0) x = 0x1B873593u;
    }
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    own_roll_state = x;
#ifdef VVFP_TEST
    ++VvfpHealersStudyRollTest.draws;
    if (VvfpHealersStudyRollTest.force == 1) return 1;
    if (VvfpHealersStudyRollTest.force == 2) return 0;
#endif
    return x % 100u < 75u;
}

static int decision_roll(void) {
    if (shared_roll == NULL) {
        /* Looked up each time until found: the fix-huts DLL may be loaded
           after this one. */
        HMODULE fix_huts = GetModuleHandleA("VVFP Fix Huts.dll");
        if (fix_huts != NULL) {
            shared_roll = (int (__cdecl *)(void))GetProcAddress(fix_huts, "VvfpFixHutsRoll");
        }
    }
    return shared_roll != NULL ? shared_roll() : own_roll();
}

/* ---- VV1 --------------------------------------------------------------- */
/* ebp = state, esi = village (villager array), edi = the villager's index. */
#define VV1_SITE      0x44836Fu
#define VV1_RESUME    0x448379u     /* push eax: the pick */
#define VV1_DONE      0x44843Du
#define VV1_PICKER    0x439AE0u
#define VV1_CONTINUE  0x447CD0u
static const unsigned char VV1_STOCK[10] = { 0x6A, 0x00, 0x57, 0x8B, 0xCE, 0xE8, 0x67, 0x17, 0xFF, 0xFF };

static int __cdecl vv1_studying(const unsigned char *state, const unsigned char *village, unsigned int index) {
    if (*(const int *)(state + 0xA2ECu) < 400) {
        return 0;                                  /* the stock code already asked */
    }
    if (*(const int *)(village + index * 0x3D8u + 0x3B8u) != 9) {
        return 0;
    }
    if (!decision_roll()) {
        return 0;                                  /* the stock selection this decision */
    }
    HEALERS_COUNT_CHECK;
    return 1;
}

static const unsigned int vv1_resume = VV1_RESUME, vv1_done = VV1_DONE;
static const unsigned int vv1_picker = VV1_PICKER, vv1_continue = VV1_CONTINUE;
static __declspec(naked) void vv1_stub(void) {
    __asm {
        pushad
        push edi
        push esi
        push ebp
        call vv1_studying
        add esp, 12
        test eax, eax
        popad
        jz selection
        push 0x3C
        push edi
        mov ecx, esi
        call dword ptr [vv1_continue]
        test eax, eax
        jz selection
#ifdef VVFP_TEST
        inc dword ptr [VvfpHealersStudyStats + 4]
#endif
        jmp dword ptr [vv1_done]
    selection:
        push 0
        push edi
        mov ecx, esi
        call dword ptr [vv1_picker]
        jmp dword ptr [vv1_resume]
    }
}

/* ---- VV1 catch-up ---------------------------------------------------------- */
/* A New Home's catch-up worker (0x42E790) has no task-state step: it takes
   the stock picker's job and, unless it is research (job 2, its own research
   step), dispatches it at 0x42E817:
       mov ecx, [edi+4]; push eax; push esi; call 0x4472C0     (10 bytes)
   and then runs the queue processor (0x42E821).  The dispatcher's Healing
   case continues a studying villager's plant study only when the pick is
   Healing and nobody is sick, so a villager dropped on the medical cactus
   stops studying in catch-up whenever catch-up picks anything else -- the
   same gap The Lost Children has, and this patch's job to fill.
   The site is that dispatch, which Builders and Healers Work First's own
   catch-up site (0x42E7E0) also falls through to for a non-research pick.
   A villager in plant-study state 9, on the decision's roll, gets the
   scheduler's own continuation 0x447CD0(index, 60) (any food level: the
   stock catch-up never makes the call); if it starts a job the worker's
   queue processor runs (0x42E821).  Otherwise the pick is dispatched exactly
   as the stock call would, with the stock return address 0x42E821 pushed,
   so a dispatcher hook that recognises the worker's call (Builders and
   Healers Work First) still does.
   edi = the worker, [edi+4] = village, esi = index, eax = the pick. */
#define VV1_CU_SITE      0x42E817u
#define VV1_CU_DONE      0x42E821u
#define VV1_DISPATCHER   0x4472C0u
static const unsigned char VV1_CU_STOCK[10] = { 0x8B, 0x4F, 0x04, 0x50, 0x56, 0xE8, 0x9F, 0x8A, 0x01, 0x00 };

static int __cdecl vv1_catch_up_studying(const unsigned char *village, unsigned int index) {
    if (*(const int *)(village + index * 0x3D8u + 0x3B8u) != 9) {
        return 0;
    }
    if (!decision_roll()) {
        return 0;                                  /* the stock pick this decision */
    }
    HEALERS_COUNT_CHECK;
    return 1;
}

static const unsigned int vv1_cu_done = VV1_CU_DONE, vv1_dispatcher = VV1_DISPATCHER;
static __declspec(naked) void vv1_cu_stub(void) {
    __asm {
        pushad
        push esi
        push dword ptr [edi + 4]
        call vv1_catch_up_studying
        add esp, 8
        test eax, eax
        popad
        jz pick
        push eax                                   /* the pick */
        push 0x3C
        push esi
        mov ecx, dword ptr [edi + 4]
        call dword ptr [vv1_continue]
        test eax, eax
        pop eax
        jz pick
#ifdef VVFP_TEST
        inc dword ptr [VvfpHealersStudyStats + 4]
#endif
        jmp dword ptr [vv1_cu_done]
    pick:
        mov ecx, dword ptr [edi + 4]
        push eax
        push esi
        push dword ptr [vv1_cu_done]
        jmp dword ptr [vv1_dispatcher]
    }
}

/* ---- VV2 --------------------------------------------------------------- */
/* esi = village, edi = the villager's index, ebp = the villager's record;
   state = [esi+0xE574D4], food [state+0x2EAA4]. */
#define VV2_SITE      0x461A22u
#define VV2_RESUME    0x461A2Cu
#define VV2_DONE      0x461AF0u
#define VV2_PICKER    0x449C60u
#define VV2_CONTINUE  0x460590u
static const unsigned char VV2_STOCK[10] = { 0x6A, 0x00, 0x57, 0x8B, 0xCE, 0xE8, 0x34, 0x82, 0xFE, 0xFF };

static int __cdecl vv2_studying(const unsigned char *village, const unsigned char *record) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4u);
    if (*(const int *)(state + 0x2EAA4u) < 300) {
        return 0;
    }
    if (*(const int *)(record + 0x7E0u) != 9) {
        return 0;
    }
    if (!decision_roll()) {
        return 0;                                  /* the stock selection this decision */
    }
    HEALERS_COUNT_CHECK;
    return 1;
}

static const unsigned int vv2_resume = VV2_RESUME, vv2_done = VV2_DONE;
static const unsigned int vv2_picker = VV2_PICKER, vv2_continue = VV2_CONTINUE;
static __declspec(naked) void vv2_stub(void) {
    __asm {
        pushad
        push ebp
        push esi
        call vv2_studying
        add esp, 8
        test eax, eax
        popad
        jz selection
        push 0x28
        push edi
        mov ecx, esi
        call dword ptr [vv2_continue]
        test eax, eax
        jz selection
#ifdef VVFP_TEST
        inc dword ptr [VvfpHealersStudyStats + 4]
#endif
        jmp dword ptr [vv2_done]
    selection:
        push 0
        push edi
        mov ecx, esi
        call dword ptr [vv2_picker]
        jmp dword ptr [vv2_resume]
    }
}

/* ---- VV2 catch-up ---------------------------------------------------------- */
/* Time passing while the game was closed, and Time Warp, never run the idle
   scheduler: The Lost Children's catch-up worker (0x43B4D0) takes the stock
   picker's job, runs the task-state continuation 0x461580 for a nonzero
   state -- whose plant-study case (state 9) starts nothing -- and dispatches
   the pick (0x43B583), whose Healing case does nothing when no one is sick.
   So a healer's plant study never continues in catch-up.  The owner: Lost
   Children healers continue plant study during catch-up, as this patch's
   catch-up behaviour (A New Home gets the same site: "VV1 catch-up" above).

   The site is the worker's pick dispatch, `push ebp; push edi; call
   0x45FBF0` (0x43B581, seven bytes), which both the state-0 path and a failed
   0x461580 reach -- so the order is the live scheduler's: the task-state
   continuation, then plant study, then the pick.  A villager in state 9, on
   the decision's roll (any food level: the stock catch-up never makes the
   call), gets the scheduler's own continuation 0x460590(index, 40); if it
   starts a job the worker's "done" runs (0x43B588, its queue processor).
   Otherwise the pick is dispatched exactly as the stock call would, with
   the stock return address 0x43B588 pushed, so a dispatcher hook that
   recognises the worker's call (Builders and Healers Work First) still does.
   The worker's research pick (job 2) never reaches this site: catch-up gives
   it its own research step, as in the stock game.
   ebx = the worker, [ebx+4] = village, edi = index, ebp = the pick; ecx =
   village. */
#define VV2_CU_SITE      0x43B581u
#define VV2_CU_DONE      0x43B588u
#define VV2_DISPATCHER   0x45FBF0u
static const unsigned char VV2_CU_STOCK[7] = { 0x55, 0x57, 0xE8, 0x68, 0x46, 0x02, 0x00 };

static int __cdecl vv2_catch_up_studying(const unsigned char *village, unsigned int index) {
    if (*(const int *)(village + index * 0xE48Cu + 0x7E0u) != 9) {
        return 0;
    }
    if (!decision_roll()) {
        return 0;                                  /* the stock pick this decision */
    }
    HEALERS_COUNT_CHECK;
    return 1;
}

static const unsigned int vv2_cu_done = VV2_CU_DONE, vv2_dispatcher = VV2_DISPATCHER;
static __declspec(naked) void vv2_cu_stub(void) {
    __asm {
        pushad
        push edi
        push dword ptr [ebx + 4]
        call vv2_catch_up_studying
        add esp, 8
        test eax, eax
        popad
        jz pick
        push 0x28
        push edi
        mov ecx, dword ptr [ebx + 4]
        call dword ptr [vv2_continue]
        mov ecx, dword ptr [ebx + 4]
        test eax, eax
        jz pick
#ifdef VVFP_TEST
        inc dword ptr [VvfpHealersStudyStats + 4]
#endif
        jmp dword ptr [vv2_cu_done]
    pick:
        push ebp
        push edi
        push dword ptr [vv2_cu_done]
        jmp dword ptr [vv2_dispatcher]
    }
}

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};
static const struct site SITES[3] = {
    { 0 },
    { VV1_SITE, VV1_STOCK, sizeof VV1_STOCK, vv1_stub },
    { VV2_SITE, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
};
static int install_state[3];
/* The catch-up sites. */
static const struct site CU_SITES[3] = {
    { 0 },
    { VV1_CU_SITE, VV1_CU_STOCK, sizeof VV1_CU_STOCK, vv1_cu_stub },
    { VV2_CU_SITE, VV2_CU_STOCK, sizeof VV2_CU_STOCK, vv2_cu_stub },
};
static int cu_install_state[3];

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

/* Called by a companion that runs every frame in the game.  Idempotent: the
   scheduler site and the catch-up site, each tried once
   and independently.  Returns whether the scheduler site is installed. */
__declspec(dllexport) int __stdcall VvfpHealersStudyInstall(int game_id) {
    if (game_id < 1 || game_id > 2) {
        return 0;
    }
    if (cu_install_state[game_id] == 0) {
        cu_install_state[game_id] = install_site(&CU_SITES[game_id]) ? 1 : -1;
    }
    if (install_state[game_id] == 0) {
        install_state[game_id] = install_site(&SITES[game_id]) ? 1 : -1;
    }
    return install_state[game_id] == 1;
}

#ifdef VVFP_TEST
/* For the test build only: the site, its stock bytes, what it becomes, the
   stub. */
__declspec(dllexport) int __stdcall VvfpHealersStudyProbeSite(int game_id, unsigned int *va,
                                                               unsigned char *stock,
                                                               unsigned char *patched,
                                                               unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 2) {
        return 0;
    }
    s = &SITES[game_id];
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* For the test build only: the catch-up site, the same way (0: none). */
__declspec(dllexport) int __stdcall VvfpHealersStudyProbeCatchUpSite(int game_id, unsigned int *va,
                                                                      unsigned char *stock,
                                                                      unsigned char *patched,
                                                                      unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 2) {
        return 0;
    }
    s = &CU_SITES[game_id];
    if (s->va == 0) {
        return 0;
    }
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
