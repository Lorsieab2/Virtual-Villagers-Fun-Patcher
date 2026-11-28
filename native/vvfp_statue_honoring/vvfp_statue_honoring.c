/* VVFP Statue Honoring -- "Villagers Dropped on an Unfinished Statue May Honor", New Believers.

   The owner (2026-11-27): "villagers when dropped on the statue when it can be improved, should have a chance of
   practicing devotion (honoring) instead of being confused (roughly equal) so people can always get triggered to
   honor no matter what".

   THE STOCK GAME (every address read from the stock executable with capstone).
     The statue (the Believer Idol, project 14, "The Tribute Statue") is map area 0x18, registered at 0x47A9D9 with
     the handler 0x479560, highlight 6 and permission 0 (the area table 0x77DC80, filled by 0x479810).  A villager
     dropped on a map area goes through the drop dispatcher 0x4794A0: a child (age < 280, 14 years) and an
     expecting mother are turned away before the handler when the area's permission is 0 (0x4794F1..0x47954B: the
     tips 0x2CF and 0x2D0), so only an adult who is not expecting reaches the statue's handler.  Heathens never get
     there: the game will not pick one up (0x445F32: "You cannot touch heathens because they do not believe in
     you.").  The handler's drop case (message 0, 0x47969C) is:
       1. the statue can be worked on now (0x432350: not solved, and a stage under way, or the first stage, or the
          second with Construction and Spirituality both at 2 or more, or the third with both at 3): "Building a
          statue", behaviour 0x95, job 0x17 (0x4796AA..0x4796C7);
       2. else the statue is solved (0x43AE80(14)): "Polishing the Statue", behaviour 0x9D, job 0x1A, and the
          one-time polishing tip 0x2DE (0x4796D2..0x479712);
       3. else -- carved to its first or second stage, its next stage waiting for technology -- "Confused",
          behaviour 0x1F with its parameter 0x66 (0x47971D..0x479730: lea ecx, [esp+4] / push ecx / mov ecx,
          [esp+0x14] / push 0x1F / mov dword [esp+0xC], 0x66 / call 0x465580).
     Honoring is behaviour 0xA0 (0x45CB70).  The believers' own job dispatcher offers it from the statue's first
     stage: the statue solved, or its stage (+8 of the statue object 0x51D950, read by 0x4271C0) 1 or 2
     (0x46CDB6..0x46CDED).  Half of all Honorings go to the statue (rand(100) < 50, 0x45CBA5) and a quarter of those
     queue the game's Devotion skill check 0x46B270(5) through the practice step 0x474780 (0x45CC88..0x45CC9B); the
     statue half ends in the work event 0x5D (Divine Energy, 0x45CCA0); the other half (area 0x6E) only gestures.

   WHAT THIS DOES.  Case 3's two instructions `push 0x1F / mov dword [esp+0xC], 0x66` (0x479726, 10 bytes) call the
   companion.  For a believer (faction byte +0x1CEC 0) of 14 or more while the statue's stage is 1 or 2 -- exactly
   when the game itself offers Honoring -- one draw of this companion's own xorshift (native/shared/slider_scale.h's
   rule: the game's rand is never drawn more or less often) picks, 1 in 2 each, the stock "Confused" (0x1F,
   parameter 0x66) or the game's own Honoring (0xA0, its parameter byte 0, as the stock Honoring dispatches set it
   at 0x46CDE8 and 0x46C462).  Either way the stock `call 0x465580` that follows starts it, so Honoring is the
   game's own, whole: its walk, its Devotion check 0x46B270 by the game's own rule, its Divine Energy, and whatever
   other patches do with them.  Every other villager, a fault, or any other stage: the stock Confused.  Cases 1
   and 2, the hover and click cases and every other handler are untouched.

   AGE RULES.  Children never reach this handler (the dispatcher turns them away first, above); the age test here
   is the believers' own child line (280), kept so the rule holds wherever the handler is reached from.

   HEATHENS.  None can be dropped (0x445F32), so none ever reaches case 3; a record with the faction byte set keeps
   the stock answer.  (The Heathens' own statue visits are "VVFP Heathen Life.dll"'s, untouched here.)

   SAFETY.  One site, spliced at run time after its stock bytes are checked (native/shared/install_sites.h); no
   executable byte is patched.  The splice keeps every register and flag as the stock instructions leave them; the
   decision runs under structured exception handling (a fault: the stock Confused).  Started by VVFP More
   Companions.dll (the third word, native/shared/startup_companions_3.h).  Nothing is written to a save, a record
   or a file; no text is shown; no debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define SH_GAME 5

#define SH_SITE 0x479726u               /* push 0x1F / mov dword [esp+0xC], 0x66 */
#define SH_SITE_LENGTH 10
#define SH_STATUE 0x51D950u             /* the statue object: its stage at +8 (0x4271C0) */
#define SH_STAGE 0x08u
#define SH_FACTION 0x1CECu              /* 1: a Heathen */
#define SH_AGE 0x1B8Cu
#define SH_ADULT 280                    /* 14 years: the believers' child line (0x4794F1) */
#define SH_CONFUSED 0x1Fu
#define SH_CONFUSED_PARAMETER 0x66u
#define SH_HONORING 0xA0u

static const unsigned char SITE_STOCK[SH_SITE_LENGTH] = {
    0x6A, 0x1F,                                     /* push 0x1F */
    0xC7, 0x44, 0x24, 0x0C, 0x66, 0x00, 0x00, 0x00  /* mov dword [esp+0xC], 0x66 */
};

static int g_installed;
static unsigned int g_seed = 0x9E3779B9u;
static unsigned int g_honored;          /* drops that became Honoring this session (the tests read it) */
static unsigned int g_confused;         /* drops that kept the stock Confused by the draw (the tests read it) */

static unsigned int sh_next(void) {
    unsigned int x = g_seed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_seed = x;
    return x;
}

/* The behaviour for this villager dropped on the statue in case 3: Honoring or the stock Confused. */
static unsigned int sh_decide(const unsigned char *record) {
    int stage = *(const int *)(UINT_PTR)(SH_STATUE + SH_STAGE);
    if (record == NULL || record[SH_FACTION] != 0 || *(const int *)(record + SH_AGE) < SH_ADULT
        || (stage != 1 && stage != 2)) {
        return SH_CONFUSED;
    }
    if ((sh_next() >> 31) != 0u) {
        ++g_honored;
        return SH_HONORING;
    }
    ++g_confused;
    return SH_CONFUSED;
}

static unsigned int __stdcall sh_choose(const unsigned char *record) {
    unsigned int behaviour = SH_CONFUSED;
    __try {
        behaviour = sh_decide(record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        behaviour = SH_CONFUSED;
    }
    return behaviour;
}

/* Called from 0x479726: [esp] the return (0x47972B: nops to the stock call 0x479730), [esp+4] the address of the
   handler's local the stock code pushed, ecx the dropped villager.  Leaves the stack as `push behaviour` would,
   the local as the chosen behaviour's stock dispatch sets it, every register and flag unchanged. */
__declspec(naked) static void sh_stub(void) {
    __asm {
        push dword ptr [esp]            /* the return, again: [esp+4] becomes the behaviour's slot */
        pushfd
        pushad
        push ecx
        call sh_choose
        mov dword ptr [esp + 40], eax   /* above the 32 bytes of pushad, the 4 of pushfd, the return */
        mov edx, dword ptr [esp + 44]   /* the local's address */
        cmp eax, SH_HONORING
        je honoring
        mov dword ptr [edx], SH_CONFUSED_PARAMETER
        jmp done
    honoring:
        mov byte ptr [edx], 0
    done:
        popad
        popfd
        ret
    }
}

/* 1 when the site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpStatueHonoringInstalled(void) {
    return g_installed;
}

/* Drops that became Honoring (which 1) or kept the stock Confused by the draw (which 0) this session (for the tests'
   emulation). */
unsigned int __stdcall VvfpStatueHonoringCount(int which) {
    return which ? g_honored : g_confused;
}

/* Called once by VVFP More Companions.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write site;
    (void)shipped;
    if (g_installed || game != SH_GAME) {
        return;
    }
    g_seed ^= GetTickCount() ^ (GetCurrentProcessId() << 16);
    if (g_seed == 0u) {
        g_seed = 0x9E3779B9u;
    }
    vvfp_site_branch(&site, SH_SITE, SH_SITE_LENGTH, SITE_STOCK, 0xE8, (const void *)sh_stub);
    if (vvfp_install_sites(&site, 1)) {
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
