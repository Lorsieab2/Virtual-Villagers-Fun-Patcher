/* VVFP VV1 Research At Max -- Continue Research at Max Technologies' 14% rule
   (A New Home).

   The owner (2026-10-20): "ALL villagers NOT checked on X skill perform
   actions that train that skill 14% of the time" -- patch behaviours only,
   and only the game's own (autonomous) choices.

   The work dispatcher's Research case (0x4472C0, case 3, entry 0x44747B)
   adds the six technology levels (0x41CEA0) and, when they reach 18 -- every
   technology at level 3 -- gives up (0x447486: cmp eax, 0x12; jge 0x447901,
   "nothing started").  Continue Research at Max Technologies
   (data/builds.json, vv1_continue_research_at_max_technologies) changes the
   0x12 to 0x13, so at 18 the villager still researches (0x44748F: the
   stock research action 0x442C10, Research practice and tech points).

   This companion keeps that for a villager checked on Research (job
   checkmark record +0x3D0 = 3) and, at 18 only, lets anyone else research
   only when a roll of its own (never the game's random numbers) passes 14
   times in 100; otherwise the stock "nothing started" (0x447901), so the
   game goes on to its own next choice.  Below 18 nothing changes.  The
   Research case is called only by the idle scheduler (0x448350, 0x44837D)
   and the catch-up worker (0x42E81C) -- the game's own choices, never a
   player's drop.

   Started by VVFP Startup.dll (VvfpStartup) at game start; it replaces the
   row's nine bytes at 0x447486 after verifying them, and installs nothing
   on any other bytes.  esi = the villager array; the villager's index is the
   dispatcher's first argument, [esp+0x14] at the site. */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include <intrin.h>
#include "../shared/install_sites.h"

#define VV1_GAME 1
#define NOT_PREFERRED_PERCENT 14u
#define SITE_VA        0x447486u
#define SITE_LENGTH    9
#define RESEARCH_VA    0x44748Fu   /* mov edx, [esp+0x14]; ... call 0x442C10 */
#define NOTHING_VA     0x447901u   /* pop edi; pop ebp; pop ebx; xor al, al; pop esi; ret 8 */
#define MAX_LEVELS     18
#define PREFERENCE     0x3D0u
#define RESEARCH       3

/* The row's bytes at the site: cmp eax, 0x13; jge 0x447901. */
static const unsigned char ROW_BYTES[SITE_LENGTH] = { 0x83, 0xF8, 0x13, 0x0F, 0x8D, 0x72, 0x04, 0x00, 0x00 };

static unsigned int roll_state;

#ifdef VVFP_TEST
/* force: 0 = the real roll, 1 = pass, 2 = fail; draws: rolls drawn. */
struct vv1_research_roll_test { int force; int draws; };
__declspec(dllexport) struct vv1_research_roll_test VvfpVv1ResearchAtMaxRollTest = { 0, 0 };
#endif

static int preference_roll(void) {
    unsigned int x = roll_state;
    if (x == 0) {
        x = (unsigned int)__rdtsc() ^ 0x165667B1u;
        if (x == 0) x = 0x165667B1u;
    }
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    roll_state = x;
#ifdef VVFP_TEST
    ++VvfpVv1ResearchAtMaxRollTest.draws;
    if (VvfpVv1ResearchAtMaxRollTest.force == 1) return 1;
    if (VvfpVv1ResearchAtMaxRollTest.force == 2) return 0;
#endif
    return x % 100u < NOT_PREFERRED_PERCENT;
}

/* 1: research; 0: the stock "nothing started". */
static int __cdecl research_allowed(int levels, const unsigned char *village, unsigned int index) {
    if (levels < MAX_LEVELS) {
        return 1;                                   /* the stock research */
    }
    if (levels > MAX_LEVELS) {
        return 0;                                   /* the row's own bound */
    }
    if (*(const int *)(village + index * 0x3D8u + PREFERENCE) == RESEARCH) {
        return 1;
    }
    return preference_roll();
}

static const unsigned int research_va = RESEARCH_VA, nothing_va = NOTHING_VA;
static __declspec(naked) void gate_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 0x34]             ; the villager's index ([esp+0x14] + pushad)
        push esi
        push eax                                ; the technology levels
        call research_allowed
        add esp, 12
        mov dword ptr [esp + 0x1C], eax
        popad
        test eax, eax
        jz nothing
        jmp dword ptr [research_va]
    nothing:
        jmp dword ptr [nothing_va]
    }
}

static void site_bytes(unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)gate_stub
                                      - ((const unsigned char *)(uintptr_t)SITE_VA + 5));
    int i;
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < SITE_LENGTH; ++i) {
        out[i] = 0x90;
    }
}

static int site_is_the_rows(void) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)SITE_VA;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, ROW_BYTES, SITE_LENGTH) == 0;
}

static int installed;

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    unsigned char bytes[SITE_LENGTH];
    vvfp_site_write w[1];
    (void)shipped;
    if (game != VV1_GAME || installed || !site_is_the_rows()) {
        return;
    }
    site_bytes(bytes);
    vvfp_site_bytes(&w[0], SITE_VA, SITE_LENGTH, ROW_BYTES, bytes);
    installed = vvfp_install_sites(w, 1);    /* all-or-none (native/shared/install_sites.h) */
}

#ifdef VVFP_TEST
/* For the test build only: the site, the row's bytes there, what it becomes,
   the stub. */
__declspec(dllexport) int __stdcall VvfpVv1ResearchAtMaxProbe(unsigned int *site_va, unsigned char *row,
                                                               unsigned char *patched, unsigned int *stub_va) {
    *site_va = SITE_VA;
    memcpy(row, ROW_BYTES, SITE_LENGTH);
    site_bytes(patched);
    *stub_va = (unsigned int)(uintptr_t)gate_stub;
    return SITE_LENGTH;
}
#endif

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
