/* VVFP Island Frequency -- "More Frequent Island Events" (all five games).

   WHAT (the owner, 2026-11-15).  The game's own island events come N times as often, N the patcher window's slider
   (2 unless moved; the owner, 2026-11-17: 0.1 to 100 in tenths, below 1 they come less often), read from "VVFP
   Island Frequency.txt" in the patcher's folder (native/shared/multiplier_choice.h): each wait the game draws after
   an event -- 12 to 23 whole real-life hours in A New Home, 10 to 19 in The Lost Children, 8 to 15 in The Secret
   City, The Tree of Life and New Believers -- is divided by N (x 10 / tenths, rounded down to the second) as the game
   writes it into its island timer: at 0.1 the longest wait is 230 hours, 828,000 seconds, far inside the timer.  The first event's 15 minutes (The Tree of Life, New Believers: the new
   village's 0x384 seconds) and the 30 minutes while a village has seen no event (the trigger's `add [timer],
   0x708`) are the stock ones, and so is which event comes and every rule for it.

   HOW.  Each game's trigger draws the wait as `push K; call rand; ...; add eax, K; imul eax, eax, 0xE10` -- rand(K)
   + K whole hours in seconds, K 12 (A New Home), 10 (The Lost Children) or 8 -- and then adds eax to the timer:

     A New Home         0x423883 0x42390A 0x423A61        (K 12; the timer world+0xA300)
     The Lost Children  0x42EF93 0x42F01A 0x42F171        (K 10; world+0x2EAE0)
     The Secret City    0x4687FB 0x468832 0x4688C6        (K 8;  manager+0x12EF4)
     The Tree of Life   0x43FAF7 0x43FB35 0x43FBC4        (K 8;  world+0x170E0)
     New Believers      0x4427C1 0x442828                 (K 8;  manager+0x17D3C)

   Those are every such draw in each executable (each game's only other `imul ..., 0xE10` is the C runtime's time
   conversion).  After every site's stock nine bytes are checked (native/shared/install_sites.h: all of them, or
   none), each becomes `call site_stub` and four nops; the stub puts (rand + K) x 36000 / tenths in eax and goes on after
   the nine bytes, every other register as the game left it.  The flags are not kept: the instruction after each
   site sets them anew (an add) or does not read them, exactly as after the stock imul.

   THE TIMER KEEPER.  The Origins companions' keeper (native/shared/island_timer_keep.h) keeps a bought island
   event from moving the natural one: the natural time it keeps is whatever the timer held when the purchase wrote
   it, and these sites run before the trigger's own write that the keeper hooks, so the time it keeps and puts back
   is already the shortened one.  The two never share a byte.

   SAFETY.  Nothing is written to a save, a villager record or a file; no text is shown.  The setting file is only
   read (its first 15 bytes): above 100 is 100, below 0.1 is 0.1, no number or no file is 2.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/multiplier_choice.h"

#define IF_CHOICE_FILE "VVFP Island Frequency.txt"
#define IF_DEFAULT 20u                   /* the slider's default, 2, in tenths */
#define IF_MINIMUM 1u                    /* 0.1 */
#define IF_MAXIMUM 1000u                 /* 100 */
#define IF_SITE_BYTES 9                  /* add eax, K (83 C0 K); imul eax, eax, 0xE10 (69 C0 10 0E 00 00) */
#define IF_MAX_SITES 3

typedef struct {
    int game;
    unsigned int hours;                  /* K: the wait is rand(K) + K whole hours */
    int count;
    unsigned int va[IF_MAX_SITES];
} if_game;

static const if_game IF_GAMES[] = {
    { 1, 12u, 3, { 0x423883u, 0x42390Au, 0x423A61u } },
    { 2, 10u, 3, { 0x42EF93u, 0x42F01Au, 0x42F171u } },
    { 3, 8u, 3, { 0x4687FBu, 0x468832u, 0x4688C6u } },
    { 4, 8u, 3, { 0x43FAF7u, 0x43FB35u, 0x43FBC4u } },
    { 5, 8u, 2, { 0x4427C1u, 0x442828u } },
};

static unsigned char g_expect[IF_SITE_BYTES];
static unsigned int g_hours;
static unsigned int g_tenths = IF_DEFAULT;
static int g_installed;

/* The wait in seconds: (the game's roll + K) whole hours, divided by N (x 10 / tenths). */
static unsigned int __cdecl shortened(unsigned int roll) {
    return (roll + g_hours) * 36000u / g_tenths;
}

/* Every site's call comes here: [esp] the site + 5; eax the game's roll. */
__declspec(naked) static void site_stub(void) {
    __asm {
        push ecx
        push edx
        push eax
        call shortened
        add esp, 4
        pop edx
        pop ecx
        add dword ptr [esp], 4         ; on after the site's nine bytes (the call and its four nops)
        ret
    }
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpIslandFrequencyInstalled(void) {
    return g_installed;
}

/* N in tenths, the number read at start (for the tests' emulation): 20 is 2, 5 is 0.5. */
int __stdcall VvfpIslandFrequencyDivisor(void) {
    return (int)g_tenths;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[IF_MAX_SITES];
    const if_game *g = NULL;
    int i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    for (i = 0; i < (int)(sizeof IF_GAMES / sizeof IF_GAMES[0]); ++i) {
        if (IF_GAMES[i].game == game) {
            g = &IF_GAMES[i];
        }
    }
    if (g == NULL) {
        return;
    }
    g_expect[0] = 0x83;
    g_expect[1] = 0xC0;
    g_expect[2] = (unsigned char)g->hours;
    g_expect[3] = 0x69;
    g_expect[4] = 0xC0;
    g_expect[5] = 0x10;
    g_expect[6] = 0x0E;
    g_expect[7] = 0x00;
    g_expect[8] = 0x00;
    for (i = 0; i < g->count; ++i) {
        vvfp_site_branch(&w[i], g->va[i], IF_SITE_BYTES, g_expect, 0xE8, (const void *)site_stub);
    }
    g_hours = g->hours;
    g_tenths = vvfp_read_tenths(IF_CHOICE_FILE, IF_DEFAULT, IF_MINIMUM, IF_MAXIMUM);
    if (vvfp_install_sites(w, g->count)) {
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
