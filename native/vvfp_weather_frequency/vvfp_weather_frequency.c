/* VVFP Weather Frequency -- "0.1-10x Weather Changes" (The Secret City, The Tree of Life, New Believers; the owner,
   2026-11-25: "Frequency of weather changes in games that have them", and "Leave powers alone").  A New Home and
   The Lost Children have no weather.

   WHAT.  The weather changes N times as often on its own, N the patcher window's slider (0.1 to 10, 1 unless
   moved), read at start from "VVFP Weather Frequency.txt" in the patcher's folder: every NATURAL spell of weather
   lasts 1/N of its normal length on the game's clock (which runs 2, 1 or 0.6 times real time on Fast, Normal or Slow
   and stops while paused).  A spell an island event, a God Power (New Believers' Sunshine and Tempest) or anything
   else sets, directly or by queueing its kind, lasts exactly as in the normal game.

   HOW.  Each game has one setter for the weather.  It gives the spell an end on the game's clock: the clock + the
   least length + rand(the greatest - the least), the least and greatest four `mov reg, imm32` in the setter:

     The Secret City   (setter 0x41FB40)  0x41FBF9 mov edi, 900    0x41FBFE mov ebx, 1800   clear
                                          0x41FC05 mov edi, 180    0x41FC0A mov ebx, 360    any other kind
     The Tree of Life  (setter 0x46BC30)  0x46BD1D mov edi, 480    0x46BD22 mov eax, 1800   clear
                                          0x46BD29 mov edi, 180    0x46BD2E mov eax, 360    any other kind
     New Believers     (setter 0x477060)  0x4771AB mov edi, 480    0x4771B0 mov eax, 1800   clear
                                          0x4771B7 mov edi, 180    0x4771BC mov eax, 360    any other kind

   Each `mov` becomes a call of a small piece that loads the stock length, or, while a natural change is being made,
   the length divided by N ((x x 10 + tenths / 2) / tenths, at least 1, the greatest kept above the least), and
   returns with every other register and the flags as they were.

   The natural changes are the setter's calls from the weather's own code: the start of a village's weather and,
   when a spell ends with no kind queued, clear -> one of the four others (The Secret City: rain in one state of its
   fruit trees) and any other -> clear:

     The Secret City   0x41FD11 (start), 0x41FF9C (the fruit trees' rain), 0x41FFAB (-> clear), 0x41FFC0 (-> another)
     The Tree of Life  0x46BDF8 (start), 0x46C103 (-> another), 0x46C113 (-> clear)
     New Believers     0x477298 (start), 0x477563 (-> another), 0x477573 (-> clear)

   Each becomes a call of wf_natural_stub, which marks the change natural, calls the setter with the same two
   arguments and ecx, and clears the mark.  A kind someone queued goes next through its own call (The Tree of Life
   0x46C129, New Believers 0x477589: left alone); The Secret City shares its 0x41FFC0 call with the queued kind, so the
   queued path's first instruction (0x41FFB4 mov dword ptr [esi + 4], -1) becomes a jump to wf_queued_stub, which
   does that move and the same call of the setter itself, unmarked, and goes on at 0x41FFC5 as the game does.  Every
   other caller of the setter (the island events, the God Powers ...) is never touched.

   SAFETY.  At 1x, or with no setting file, nothing is installed.  Every site is checked to hold exactly its stock
   bytes first, and the writes go through vvfp_install_sites (all of them, or none).  Nothing is written to a save,
   a villager record or a file; no text is shown.  No debug output. */
#include <windows.h>
#include "../shared/slider_scale.h"

#define WF_CHOICE_FILE "VVFP Weather Frequency.txt"
#define WF_LENGTHS 4
#define WF_MAX_NATURAL 4
#define WF_MAX_SITES (WF_LENGTHS + WF_MAX_NATURAL + 1)

typedef struct {
    int game;
    unsigned int setter;
    unsigned int va[WF_LENGTHS];        /* clear's least, clear's greatest, the others' least, the others' greatest */
    unsigned char op[WF_LENGTHS];       /* the mov's opcode (0xB8 + register) */
    unsigned int seconds[WF_LENGTHS];   /* the stock lengths */
    int natural_count;
    unsigned int natural[WF_MAX_NATURAL];
    unsigned int queued;                /* The Secret City's queued path (7 bytes), else 0 */
    unsigned int queued_resume;
} wf_game;

static const wf_game WF_GAMES[] = {
    { 3, 0x41FB40u, { 0x41FBF9u, 0x41FBFEu, 0x41FC05u, 0x41FC0Au }, { 0xBF, 0xBB, 0xBF, 0xBB },
      { 900u, 1800u, 180u, 360u }, 4, { 0x41FD11u, 0x41FF9Cu, 0x41FFABu, 0x41FFC0u }, 0x41FFB4u, 0x41FFC5u },
    { 4, 0x46BC30u, { 0x46BD1Du, 0x46BD22u, 0x46BD29u, 0x46BD2Eu }, { 0xBF, 0xB8, 0xBF, 0xB8 },
      { 480u, 1800u, 180u, 360u }, 3, { 0x46BDF8u, 0x46C103u, 0x46C113u }, 0u, 0u },
    { 5, 0x477060u, { 0x4771ABu, 0x4771B0u, 0x4771B7u, 0x4771BCu }, { 0xBF, 0xB8, 0xBF, 0xB8 },
      { 480u, 1800u, 180u, 360u }, 3, { 0x477298u, 0x477563u, 0x477573u }, 0u, 0u },
};

static int g_wf_installed;
static unsigned int g_wf_natural;                   /* 1 while a natural change is being made */
static unsigned int g_wf_setter;
static unsigned int g_wf_resume;
static unsigned int g_wf_stock[WF_LENGTHS];
static unsigned int g_wf_scaled[WF_LENGTHS];

/* x / N in whole seconds (rounded), at least 1. */
static unsigned int wf_scaled(unsigned int x) {
    unsigned int y = (x * 10u + g_ss_tenths / 2u) / g_ss_tenths;
    return y < 1u ? 1u : y;
}

/* The four lengths: the register the game's `mov` loads, the stock or the scaled one; the flags kept. */
__declspec(naked) static void wf_edi_0(void) {
    __asm {
        pushfd
        mov edi, dword ptr [g_wf_stock]
        cmp dword ptr [g_wf_natural], 0
        je done
        mov edi, dword ptr [g_wf_scaled]
    done:
        popfd
        ret
    }
}

__declspec(naked) static void wf_ebx_1(void) {
    __asm {
        pushfd
        mov ebx, dword ptr [g_wf_stock + 4]
        cmp dword ptr [g_wf_natural], 0
        je done
        mov ebx, dword ptr [g_wf_scaled + 4]
    done:
        popfd
        ret
    }
}

__declspec(naked) static void wf_eax_1(void) {
    __asm {
        pushfd
        mov eax, dword ptr [g_wf_stock + 4]
        cmp dword ptr [g_wf_natural], 0
        je done
        mov eax, dword ptr [g_wf_scaled + 4]
    done:
        popfd
        ret
    }
}

__declspec(naked) static void wf_edi_2(void) {
    __asm {
        pushfd
        mov edi, dword ptr [g_wf_stock + 8]
        cmp dword ptr [g_wf_natural], 0
        je done
        mov edi, dword ptr [g_wf_scaled + 8]
    done:
        popfd
        ret
    }
}

__declspec(naked) static void wf_ebx_3(void) {
    __asm {
        pushfd
        mov ebx, dword ptr [g_wf_stock + 12]
        cmp dword ptr [g_wf_natural], 0
        je done
        mov ebx, dword ptr [g_wf_scaled + 12]
    done:
        popfd
        ret
    }
}

__declspec(naked) static void wf_eax_3(void) {
    __asm {
        pushfd
        mov eax, dword ptr [g_wf_stock + 12]
        cmp dword ptr [g_wf_natural], 0
        je done
        mov eax, dword ptr [g_wf_scaled + 12]
    done:
        popfd
        ret
    }
}

/* A natural change: [esp] the caller's return, [esp + 4] the kind, [esp + 8] the setter's second argument, ecx the
   weather.  The setter is `ret 8`; its eax is kept. */
__declspec(naked) static void wf_natural_stub(void) {
    __asm {
        mov dword ptr [g_wf_natural], 1
        push dword ptr [esp + 8]
        push dword ptr [esp + 8]
        call dword ptr [g_wf_setter]
        mov dword ptr [g_wf_natural], 0
        ret 8
    }
}

/* The Secret City's queued kind (edi), reached by a jump from 0x41FFB4 with esi the weather: the game's own
   `mov dword ptr [esi + 4], -1; push 0; push edi; mov ecx, esi; call setter`, unmarked, then on at 0x41FFC5. */
__declspec(naked) static void wf_queued_stub(void) {
    __asm {
        mov dword ptr [esi + 4], 0xFFFFFFFF
        push 0
        push edi
        mov ecx, esi
        call dword ptr [g_wf_setter]
        jmp dword ptr [g_wf_resume]
    }
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
    static vvfp_site_write w[WF_MAX_SITES];
    static unsigned char expect[WF_MAX_SITES][7];
    static const unsigned char queued_stock[7] = { 0xC7, 0x46, 0x04, 0xFF, 0xFF, 0xFF, 0xFF };
    const wf_game *g = NULL;
    const void *piece[WF_LENGTHS];
    int i, n = 0;
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
    for (i = 0; i < WF_LENGTHS; i += 2) {
        g_wf_stock[i] = g->seconds[i];
        g_wf_stock[i + 1] = g->seconds[i + 1];
        g_wf_scaled[i] = wf_scaled(g->seconds[i]);
        g_wf_scaled[i + 1] = wf_scaled(g->seconds[i + 1]);
        if (g_wf_scaled[i + 1] <= g_wf_scaled[i]) {
            g_wf_scaled[i + 1] = g_wf_scaled[i] + 1u;
        }
    }
    g_wf_setter = g->setter;
    g_wf_resume = g->queued_resume;
    piece[0] = (const void *)wf_edi_0;
    piece[1] = g->op[1] == 0xBB ? (const void *)wf_ebx_1 : (const void *)wf_eax_1;
    piece[2] = (const void *)wf_edi_2;
    piece[3] = g->op[3] == 0xBB ? (const void *)wf_ebx_3 : (const void *)wf_eax_3;
    for (i = 0; i < WF_LENGTHS; ++i) {
        expect[n][0] = g->op[i];
        memcpy(&expect[n][1], &g->seconds[i], 4);
        if (!vvfp_site_holds(g->va[i], expect[n], 5)) {
            return;
        }
        vvfp_site_branch(&w[n], g->va[i], 5, expect[n], 0xE8, piece[i]);
        ++n;
    }
    for (i = 0; i < g->natural_count; ++i) {
        unsigned int rel = g->setter - (g->natural[i] + 5u);
        expect[n][0] = 0xE8;
        memcpy(&expect[n][1], &rel, 4);
        if (!vvfp_site_holds(g->natural[i], expect[n], 5)) {
            return;
        }
        vvfp_site_branch(&w[n], g->natural[i], 5, expect[n], 0xE8, (const void *)wf_natural_stub);
        ++n;
    }
    if (g->queued != 0u) {
        memcpy(expect[n], queued_stock, 7);
        if (!vvfp_site_holds(g->queued, expect[n], 7)) {
            return;
        }
        vvfp_site_branch(&w[n], g->queued, 7, expect[n], 0xE9, (const void *)wf_queued_stub);
        ++n;
    }
    if (vvfp_install_sites(w, n)) {
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
