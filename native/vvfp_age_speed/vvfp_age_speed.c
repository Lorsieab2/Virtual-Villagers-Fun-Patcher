/* VVFP Age Speed -- "Age and Nursing Timer Speed" (all five games; the owner, 2026-11-17).

   WHAT.  Villagers' age clock runs N times as fast (on average), N the patcher window's slider (0.1 to 10, 1 unless
   moved), read at start from "VVFP Age Speed.txt" in the patcher's folder.  Every game keeps one age clock per
   villager and everything counted in age units runs on it: growing up, becoming an elder, old age, pregnancy and
   nursing (a baby is born when the mother's age passes the conception + 40 units: there is no separate nursing
   clock), and the per-age-unit rolls and needs (eating, health, sickness; New Believers' faith and Divine Energy).
   So one change keeps them all in step.

   HOW.  Each game's world tick adds, for each villager, the real seconds since its last look (now - the villager's
   stamp) to the villager's uncounted seconds; then it caps them (a day at most, less per speed) and turns whole
   minutes of them (x the speed) into age units.  That one add -- the same in play, while the game catches up and
   after a Time Warp -- is where the seconds are scaled (ss_scale: N times on average), BEFORE the cap, so the most a
   single look can add is the game's own:

     A New Home         0x42EA62  sub eax, [ecx + 0x340]                    (6 bytes)
     The Lost Children  0x43B856  sub eax, edx; add ecx, eax; mov [ebp + 0x524], ecx     (10 bytes)
     The Secret City    0x45F4F5  sub eax, edi; add edx, eax; mov eax, 0x15180            (9 bytes)
     The Tree of Life   0x46656C  sub eax, edi; add [esi - 0x93], eax       (8 bytes)
     New Believers      0x46FFA3  sub eax, edi; add [esi + 0x1C34], eax     (8 bytes)

   Each becomes `call` this game's stub and nops; the stub does the same with the difference scaled and returns
   after them.  The instruction after each site sets the flags anew (or does not read them).

   NOT CHANGED.  The Golden Child (A New Home) is set back to 5 (100 units) right after on every look, as before; The
   Lost Children's Esteemed Elders (totems), The Tree of Life's ghosts and New Believers' Heathens are not aged by the
   game at all, as before.  Absolute age changes (Set Age to 18, Youth, Make Villagers Young Adults, "feels years
   younger") are the game's own.  Work, conception attempts, food regrowth, island events, puzzles, the Nursery
   School's lessons and everything else on the game's own clocks run at the normal speed.  The age at which each thing
   happens is the game's own; only how soon it comes changes.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  The site is checked to hold exactly its stock bytes
   first.  Nothing is written to a save, a villager record or a file; no text is shown.  No debug output. */
#include <windows.h>
#include "../shared/slider_scale.h"

#define AS_CHOICE_FILE "VVFP Age Speed.txt"

static int g_installed;

#define AS_SCALE_EAX           \
    __asm push ecx             \
    __asm push edx             \
    __asm push eax             \
    __asm call ss_scale        \
    __asm add esp, 4           \
    __asm pop edx              \
    __asm pop ecx

__declspec(naked) static void vv1_stub(void) {
    __asm sub eax, dword ptr [ecx + 0x340]
    AS_SCALE_EAX
    __asm ret
}

__declspec(naked) static void vv2_stub(void) {
    __asm sub eax, edx
    AS_SCALE_EAX
    __asm add ecx, eax
    __asm mov dword ptr [ebp + 0x524], ecx
    __asm ret
}

__declspec(naked) static void vv3_stub(void) {
    __asm sub eax, edi
    AS_SCALE_EAX
    __asm add edx, eax
    __asm mov eax, 0x15180
    __asm ret
}

__declspec(naked) static void vv4_stub(void) {
    __asm sub eax, edi
    AS_SCALE_EAX
    __asm add dword ptr [esi - 0x93], eax
    __asm ret
}

__declspec(naked) static void vv5_stub(void) {
    __asm sub eax, edi
    AS_SCALE_EAX
    __asm add dword ptr [esi + 0x1C34], eax
    __asm ret
}

static const unsigned char VV1_STOCK[] = { 0x2B, 0x81, 0x40, 0x03, 0x00, 0x00 };
static const unsigned char VV2_STOCK[] = { 0x2B, 0xC2, 0x03, 0xC8, 0x89, 0x8D, 0x24, 0x05, 0x00, 0x00 };
static const unsigned char VV3_STOCK[] = { 0x2B, 0xC7, 0x03, 0xD0, 0xB8, 0x80, 0x51, 0x01, 0x00 };
static const unsigned char VV4_STOCK[] = { 0x2B, 0xC7, 0x01, 0x86, 0x6D, 0xFF, 0xFF, 0xFF };
static const unsigned char VV5_STOCK[] = { 0x2B, 0xC7, 0x01, 0x86, 0x34, 0x1C, 0x00, 0x00 };

typedef struct {
    int game;
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
} as_game;

static const as_game AS_GAMES[] = {
    { 1, 0x42EA62u, VV1_STOCK, sizeof VV1_STOCK, vv1_stub },
    { 2, 0x43B856u, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
    { 3, 0x45F4F5u, VV3_STOCK, sizeof VV3_STOCK, vv3_stub },
    { 4, 0x46656Cu, VV4_STOCK, sizeof VV4_STOCK, vv4_stub },
    { 5, 0x46FFA3u, VV5_STOCK, sizeof VV5_STOCK, vv5_stub },
};

/* 1 when the site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpAgeSpeedInstalled(void) {
    return g_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpAgeSpeedTenths(void) {
    return (int)g_ss_tenths;
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w;
    const as_game *g = NULL;
    int i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    for (i = 0; i < (int)(sizeof AS_GAMES / sizeof AS_GAMES[0]); ++i) {
        if (AS_GAMES[i].game == game) {
            g = &AS_GAMES[i];
        }
    }
    if (g == NULL || !ss_start(AS_CHOICE_FILE)) {
        return;
    }
    vvfp_site_branch(&w, g->va, g->length, g->stock, 0xE8, (const void *)g->stub);
    if (vvfp_install_sites(&w, 1)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
