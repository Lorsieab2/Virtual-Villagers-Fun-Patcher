/* VVFP Weather Frequency -- "Frequency of Weather Changes" (The Secret City, The Tree of Life, New Believers; the
   owner, 2026-11-25: "Frequency of weather changes in games that have them").  A New Home and The Lost Children have
   no weather.

   WHAT.  The weather changes N times as often, N the patcher window's slider (0.1 to 10, 1 unless moved), read at
   start from "VVFP Weather Frequency.txt" in the patcher's folder: every spell of weather lasts 1/N of its normal
   length on the game's clock (which runs 2, 1 or 0.6 times real time on Fast, Normal or Slow and stops while
   paused).

   HOW.  Each game has one setter for the weather (every kind, whatever asks for it: the weather's own turn, an
   island event, a God Power or a new village).  It gives the spell an end on the game's clock: the clock + the
   least length + rand(the greatest - the least).  When a spell ends, a weather an event queued comes next; else
   clear weather is followed by one of the four other kinds (rand(5) redrawn until not clear) and any other kind by
   clear.  The least and greatest lengths are four `mov reg, imm32` in the setter:

     The Secret City   (setter 0x41FB40)  0x41FBF9 mov edi, 900    0x41FBFE mov ebx, 1800   clear
                                          0x41FC05 mov edi, 180    0x41FC0A mov ebx, 360    any other kind
                                          (while the first fruit tree has grown and no second is planted, a spell
                                          lasts exactly the least: 0x41FC3F -> 0x41FC64)
     The Tree of Life  (setter 0x46BC30)  0x46BD1D mov edi, 480    0x46BD22 mov eax, 1800   clear
                                          0x46BD29 mov edi, 180    0x46BD2E mov eax, 360    any other kind
     New Believers     (setter 0x477060)  0x4771AB mov edi, 480    0x4771B0 mov eax, 1800   clear
                                          0x4771B7 mov edi, 180    0x4771BC mov eax, 360    any other kind

   Each immediate becomes (x x 10 + tenths / 2) / tenths, x / N rounded, at least 1 second; the greatest is kept
   above the least, so rand's range is never 0.  A spell already under way when the game starts keeps its end.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  Every site is checked to hold exactly its stock
   bytes first, and the writes go through vvfp_install_sites (all of them, or none).  Nothing is written to a save,
   a villager record or a file; no text is shown.  No debug output. */
#include <windows.h>
#include "../shared/slider_scale.h"

#define WF_CHOICE_FILE "VVFP Weather Frequency.txt"
#define WF_SITES 4

typedef struct {
    int game;
    unsigned int va[WF_SITES];          /* clear's least, clear's greatest, the others' least, the others' greatest */
    unsigned char op[WF_SITES];         /* the mov's opcode (0xB8 + register) */
    unsigned int seconds[WF_SITES];     /* the stock lengths */
} wf_game;

static const wf_game WF_GAMES[] = {
    { 3, { 0x41FBF9u, 0x41FBFEu, 0x41FC05u, 0x41FC0Au }, { 0xBF, 0xBB, 0xBF, 0xBB }, { 900u, 1800u, 180u, 360u } },
    { 4, { 0x46BD1Du, 0x46BD22u, 0x46BD29u, 0x46BD2Eu }, { 0xBF, 0xB8, 0xBF, 0xB8 }, { 480u, 1800u, 180u, 360u } },
    { 5, { 0x4771ABu, 0x4771B0u, 0x4771B7u, 0x4771BCu }, { 0xBF, 0xB8, 0xBF, 0xB8 }, { 480u, 1800u, 180u, 360u } },
};

static int g_wf_installed;

/* x / N in whole seconds (rounded), at least 1. */
static unsigned int wf_scaled(unsigned int x) {
    unsigned int y = (x * 10u + g_ss_tenths / 2u) / g_ss_tenths;
    return y < 1u ? 1u : y;
}

/* 1 when installed (for the tests' emulation), else 0. */
int __stdcall VvfpWeatherFrequencyInstalled(void) {
    return g_wf_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpWeatherFrequencyTenths(void) {
    return (int)g_ss_tenths;
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[WF_SITES];
    static unsigned char expect[WF_SITES][5];
    const wf_game *g = NULL;
    unsigned int value[WF_SITES];
    int i;
    (void)shipped;
    if (g_wf_installed) {
        return;
    }
    for (i = 0; i < (int)(sizeof WF_GAMES / sizeof WF_GAMES[0]); ++i) {
        if (WF_GAMES[i].game == game) {
            g = &WF_GAMES[i];
        }
    }
    if (g == NULL || !ss_start(WF_CHOICE_FILE)) {
        return;
    }
    for (i = 0; i < WF_SITES; i += 2) {
        value[i] = wf_scaled(g->seconds[i]);
        value[i + 1] = wf_scaled(g->seconds[i + 1]);
        if (value[i + 1] <= value[i]) {
            value[i + 1] = value[i] + 1u;
        }
    }
    for (i = 0; i < WF_SITES; ++i) {
        unsigned char bytes[5];
        expect[i][0] = g->op[i];
        memcpy(&expect[i][1], &g->seconds[i], 4);
        if (!vvfp_site_holds(g->va[i], expect[i], 5)) {
            return;
        }
        bytes[0] = g->op[i];
        memcpy(&bytes[1], &value[i], 4);
        vvfp_site_bytes(&w[i], g->va[i], 5, expect[i], bytes);
    }
    if (vvfp_install_sites(w, WF_SITES)) {
        g_wf_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
