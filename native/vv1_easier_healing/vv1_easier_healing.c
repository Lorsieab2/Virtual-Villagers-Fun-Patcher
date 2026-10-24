/* VVFP VV1 Easier Healing -- Easier Healing Mastery's 14% rule (A New Home).

   The owner (2026-10-20): "Applies to patch behaviors only: ALL villagers NOT
   checked on X skill perform actions that train that skill 14% of the time"
   -- and only for the game's own (autonomous) choices, never for anything
   the player does.

   Easier Healing Mastery (data/builds.json, vv1_easier_healing_mastery)
   rewrites the no-patient exit of the work dispatcher's Healing case
   (0x4472C0, case 5), 0x4478E7..0x447900, so that ANY villager the game
   gives healing work with no one to treat studies the Medical Cactus:

       0x4478E7  push ebp; mov ecx, esi; call 0x443270    (the study)
                 pop edi; pop ebp; pop ebx; mov al, 1; pop esi; ret 8
                 nop x9

   The stock exit studied only for a villager already in plant-study state 9
   (record +0x3B8 = 9, set when the player drops a villager on the cactus),
   then reported "nothing started" (0x447901).  The executable has no free
   code space for a gate, so this companion detours those 26 bytes at run
   time (after verifying them) to a stub that keeps the row's study for

     * a villager checked on Healing (job checkmark record +0x3D0 = 5), and
     * a villager in plant-study state 9 (the player's own drop on the cactus:
       never restricted),

   and for anyone else only when a roll of this companion's own (never the
   game's random numbers) passes 14 times in 100; otherwise it takes the
   stock no-patient exit 0x447901 (al = 0: nothing started), so the game goes
   on to its own next choice.  The dispatcher's Healing case is called only
   by the idle scheduler (0x448350, 0x44837D) and the catch-up worker
   (0x42E81C) -- the game's own choices; the player's drop on the cactus
   calls the study directly (0x424A6A) and never comes here.

   Started by VVFP Startup.dll (VvfpStartup) at game start, before any
   catch-up; with the row's bytes not in place (another build, the row off)
   it installs nothing.  esi = the villager array, ebp = the villager's index. */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include <intrin.h>
#include "../shared/install_sites.h"

#define VV1_GAME 1
#define NOT_PREFERRED_PERCENT 14u
#define SITE_VA        0x4478E7u
#define SITE_LENGTH    26
#define STUDY_VA       0x443270u
#define STARTED_VA     0x44788Bu   /* pop edi; pop ebp; pop ebx; mov al, 1; pop esi; ret 8 */
#define NOTHING_VA     0x447901u   /* pop edi; pop ebp; pop ebx; xor al, al; pop esi; ret 8 */
#define PREFERENCE     0x3D0u
#define ACTIVITY       0x3B8u
#define HEALING        5
#define PLANT_STUDY    9

/* Easier Healing Mastery's bytes at the site (data/builds.json). */
static const unsigned char ROW_BYTES[SITE_LENGTH] = {
    0x55, 0x8B, 0xCE, 0xE8, 0x81, 0xB9, 0xFF, 0xFF, 0x5F, 0x5D, 0x5B, 0xB0, 0x01,
    0x5E, 0xC2, 0x08, 0x00, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90
};

static unsigned int roll_state;

#ifdef VVFP_TEST
/* force: 0 = the real roll, 1 = pass, 2 = fail; draws: rolls drawn. */
struct vv1_easier_healing_roll_test { int force; int draws; };
__declspec(dllexport) struct vv1_easier_healing_roll_test VvfpVv1EasierHealingRollTest = { 0, 0 };
#endif

static int preference_roll(void) {
    unsigned int x = roll_state;
    if (x == 0) {
        x = (unsigned int)__rdtsc() ^ 0x27D4EB2Fu;
        if (x == 0) x = 0x27D4EB2Fu;
    }
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    roll_state = x;
#ifdef VVFP_TEST
    ++VvfpVv1EasierHealingRollTest.draws;
    if (VvfpVv1EasierHealingRollTest.force == 1) return 1;
    if (VvfpVv1EasierHealingRollTest.force == 2) return 0;
#endif
    return x % 100u < NOT_PREFERRED_PERCENT;
}

/* 1: study (the row's behaviour); 0: the stock no-patient exit. */
static int __cdecl study_allowed(const unsigned char *village, unsigned int index) {
    const unsigned char *record = village + index * 0x3D8u;
    if (*(const int *)(record + PREFERENCE) == HEALING || *(const int *)(record + ACTIVITY) == PLANT_STUDY) {
        return 1;
    }
    return preference_roll();
}

static const unsigned int study_va = STUDY_VA, started_va = STARTED_VA, nothing_va = NOTHING_VA;
static __declspec(naked) void gate_stub(void) {
    __asm {
        pushad
        push ebp                                ; the villager's index
        push esi
        call study_allowed
        add esp, 8
        mov dword ptr [esp + 0x1C], eax
        popad
        test eax, eax
        jz nothing
        push ebp                                ; the row's study, as it was
        mov ecx, esi
        call dword ptr [study_va]
        jmp dword ptr [started_va]
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
__declspec(dllexport) int __stdcall VvfpVv1EasierHealingProbe(unsigned int *site_va, unsigned char *row,
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
