/* VVFP Herb Study -- part of "Fix Vanilla Bugs" in A New Home and The Lost
   Children (the owner, 2026-11-17, skill practice items 15 and 40: every
   studyable plant gives Healing practice when studied, first study and
   re-studies alike, and a plant the game never lets anyone re-study becomes
   re-studyable -- "original-game bugs", so they go under Fix Vanilla Bugs,
   by a companion, not by patched executable bytes).

   A NEW HOME.  Each herb's study starter (medical cactus 0x443270, rare rose
   0x4435B0, strange lily 0x443440, strange plant 0x443720) queues, for a herb
   already understood, step 6 with skill 5 -- the Healing practice roll
   0x43D440(index, 5) -- and, for a herb not yet understood, step 0xE with the
   herb's number, which runs the completion routine 0x43A230.  Its four herb
   cases (cactus 0x43A361, rose 0x43A451, lily 0x43A432, strange plant
   0x43A473) set the herb's understood flag and show the message, and never
   call 0x43D440: the first study of every herb -- the one that counts toward
   Herb Mastery -- gave no Healing practice, and neither did a first study
   finished by a second villager after the flag was set.  Now each case's
   entry first makes the same Healing practice roll, 0x43D440(index, 5), the
   re-study's own; then the stock case runs unchanged.  Catch-up's first
   studies run the same completion routine (0x446DBF), so they roll too.  The
   Magic Plant of Life ("Studying fruitless plant", 0x443030) has no study
   step and no understood flag; it is untouched.

   THE LOST CHILDREN.  Every plant already rolls Healing on a re-study (step
   6) and gives +5 on its first study.  But the study continuation 0x460590 --
   which carries a villager dropped on a plant (task state 9) on to further
   studies -- picks rand(4) among herbs 1, 2, 5 and 6 (0x4606A1, table
   0x460AE4): herbs 3 (0x458B70) and 4 (0x458E30) are never studied again
   after their first study.  Now it picks rand(6), the four stock cases for 0
   to 3 and herbs 3 and 4 for 4 and 5, each, like the stock cases, only when
   the herb is understood ([state+0x2E870] / [state+0x2E878]; otherwise the
   continuation's own fallback 0x460961).

   SAFETY.  Each site's stock bytes are checked first; all of a game's sites
   or none are written (native/shared/install_sites.h).  Nothing is saved.  No
   debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define HS_GAME_BASE 0x400000u

/* ---- A New Home: the completion routine's four herb cases ------------------ */
/* At each case entry: esi = the village, [esp+0x14] = the villager's index
   (0x43A230 pushed esi, ebx, ebp and edi); the entry's own 6 bytes are
   mov eax, [esi+0x3E010]. */
static const unsigned char VV1_ENTRY_STOCK[6] = { 0x8B, 0x86, 0x10, 0xE0, 0x03, 0x00 };
static const unsigned int vv1_practice = 0x43D440u;
static const unsigned int vv1_cactus_back = 0x43A367u, vv1_rose_back = 0x43A457u;
static const unsigned int vv1_lily_back = 0x43A438u, vv1_plant_back = 0x43A479u;

#define VV1_HERB_STUB(NAME)                                                   \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm push 5                                                     \
            __asm push dword ptr [esp + 0x18]      /* the index */            \
            __asm mov ecx, esi                                               \
            __asm call dword ptr [vv1_practice]                              \
            __asm mov eax, dword ptr [esi + 0x3E010]                         \
            __asm jmp dword ptr [NAME##_back]                                \
        }                                                                    \
    }
VV1_HERB_STUB(vv1_cactus)
VV1_HERB_STUB(vv1_rose)
VV1_HERB_STUB(vv1_lily)
VV1_HERB_STUB(vv1_plant)

/* ---- The Lost Children: the study continuation's plant pick ---------------- */
/* At 0x4606A1 (push 4; call rand, 7 bytes): esi = the village, ebp = the
   villager's index, bl = 0. */
static const unsigned char VV2_PICK_STOCK[7] = { 0x6A, 0x04, 0xE8, 0xF8, 0x2A, 0xFA, 0xFF };
static const unsigned int vv2_rand = 0x4031A0u, vv2_pick_table = 0x4606ABu;
static const unsigned int vv2_fallback = 0x460961u, vv2_started = 0x4606D5u;
static const unsigned int vv2_herb3 = 0x458B70u, vv2_herb4 = 0x458E30u;
static __declspec(naked) void vv2_pick_stub(void) {
    __asm {
        push 6
        call dword ptr [vv2_rand]
        add esp, 4
        cmp eax, 4
        jae more
        jmp dword ptr [vv2_pick_table]      /* cmp eax, 3; ja; jmp [table] */
    more:
        mov ecx, dword ptr [esi + 0xE574D4]
        cmp eax, 4
        jne herb4
        cmp byte ptr [ecx + 0x2E870], bl
        je not_understood
        push ebp
        mov ecx, esi
        call dword ptr [vv2_herb3]
        jmp dword ptr [vv2_started]
    herb4:
        cmp byte ptr [ecx + 0x2E878], bl
        je not_understood
        push ebp
        mov ecx, esi
        call dword ptr [vv2_herb4]
        jmp dword ptr [vv2_started]
    not_understood:
        jmp dword ptr [vv2_fallback]
    }
}

static int g_installed;

/* 1 when the sites went in, 0 when they did not (or this game has none). */
__declspec(dllexport) int __stdcall VvfpHerbStudyInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[4];
    const unsigned char *module;
    int count = 0;
    (void)shipped;
    if (g_installed || game < 1 || game > 2) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleA(NULL);
    if (module != NULL && (UINT_PTR)module != HS_GAME_BASE) {
        return;
    }
    if (game == 1) {
        if (!vvfp_site_holds(0x43A361u, VV1_ENTRY_STOCK, 6) || !vvfp_site_holds(0x43A451u, VV1_ENTRY_STOCK, 6)
            || !vvfp_site_holds(0x43A432u, VV1_ENTRY_STOCK, 6) || !vvfp_site_holds(0x43A473u, VV1_ENTRY_STOCK, 6)) {
            return;
        }
        vvfp_site_branch(&w[count++], 0x43A361u, 6, VV1_ENTRY_STOCK, 0xE9, (const void *)vv1_cactus_stub);
        vvfp_site_branch(&w[count++], 0x43A451u, 6, VV1_ENTRY_STOCK, 0xE9, (const void *)vv1_rose_stub);
        vvfp_site_branch(&w[count++], 0x43A432u, 6, VV1_ENTRY_STOCK, 0xE9, (const void *)vv1_lily_stub);
        vvfp_site_branch(&w[count++], 0x43A473u, 6, VV1_ENTRY_STOCK, 0xE9, (const void *)vv1_plant_stub);
    } else {
        if (!vvfp_site_holds(0x4606A1u, VV2_PICK_STOCK, 7)) {
            return;
        }
        vvfp_site_branch(&w[count++], 0x4606A1u, 7, VV2_PICK_STOCK, 0xE9, (const void *)vv2_pick_stub);
    }
    if (vvfp_install_sites(w, count)) {
        g_installed = 1;
    }
}

#ifdef VVFP_TEST
/* For the test build only: site `which` of the game -- its address and the
   stub it branches to.  0: no such site. */
__declspec(dllexport) int __stdcall VvfpHerbStudyProbeSite(int game, int which, unsigned int *va,
                                                          unsigned int *stub_va) {
    static const unsigned int vv1_sites[4] = { 0x43A361u, 0x43A451u, 0x43A432u, 0x43A473u };
    const void *vv1_stubs[4];
    vv1_stubs[0] = (const void *)vv1_cactus_stub;
    vv1_stubs[1] = (const void *)vv1_rose_stub;
    vv1_stubs[2] = (const void *)vv1_lily_stub;
    vv1_stubs[3] = (const void *)vv1_plant_stub;
    if (game == 1 && which >= 0 && which < 4) {
        *va = vv1_sites[which];
        *stub_va = (unsigned int)(UINT_PTR)vv1_stubs[which];
        return 6;
    }
    if (game == 2 && which == 0) {
        *va = 0x4606A1u;
        *stub_va = (unsigned int)(UINT_PTR)vv2_pick_stub;
        return 7;
    }
    return 0;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
