/* VVFP VV3 Chief Hospital -- the Tribal Chief directs work at the hospital
   and helps the healers there (The Secret City).

   THE STOCK GAME.  Dropping a villager on the Hospital hotspot (drop table
   0x560808, entry 0x27, registered at 0x422C4F) runs 0x4215E0.  With
   Medicine 2 or more it writes the Healing site (+0xEA0 = 9) at 0x4215F6;
   an ordinary villager is then given action 0xBD, "Studying medicine"
   (0x421620; handler 0x451890), but the Tribal Chief (+0xE80 set) is given
   no action (0x421608).  The chief's own chooser (0x45BFE0 -> chief test
   0x45C110 -> 0x45BDA0) sends a chief with a site to 0x458C70, whose switch
   gives every valid site action 0x81, "Directing work" (push 0x81 at
   0x458D51; handler 0x44B5F0, which says string 0x219 eSayDirectWork at
   0x44B5F9).  Site 9 is not one of them: its index byte (0x458D94) sends
   it to 0x458D0B, which clears the site and gives nothing -- the owner's
   "he does nothing and picks another task".  The Directing-work handler has
   no stand position for site 9 either (its table 0x44BBBC sends site 9 to
   the exit 0x44BB80).  The chief's supervision roll 0x45FC60(site) passes
   only when the chief is alive, not sick and on that site, with chance
   25% x Leadership; the stock game never asks it for a cure.

   WHAT THIS COMPANION DOES, at four places:

   1. CURE (0x45739A, the existing row).  A healer's failed Healing roll in
      a cure (0x457350, roll at 0x457395) is followed by the chief's
      supervision roll 0x45FC60(9); when that passes the cure continues as a
      passed roll (0x4573A2), otherwise the stock failure runs (0x457431).
          stock:  84 C0 0F 84 8F 00 00 00   test al, al / je 0x457431
          patch:  E9 rel32 90 90 90

   2. THE CHIEF TAKES THE HOSPITAL (index byte 0x458D94).  Site 9's index
      becomes 0x0B, the index every other directed site uses, so the chief
      is given the stock action 0x81 "Directing work" (0x458D4C).
          stock:  00   patch:  0B

   3. WHERE HE STANDS (0x44B637).  The Directing-work handler's site switch
      `jmp [ecx*4+0x44BB88]` is detoured; for site 9 (eax = site - 4 = 5)
      the stub gives the handler the place the chief stands for "Concerned
      about the sick" (action 0x8A, handler 0x452540, string 0x1E4: walks
      to (0x47B + rand(0x96), 0x665 + rand(0x32)) at 0x452570..0x452599).
      The handler walks to base + rand(0x1E) on each axis, so the bases are
      0x47B + rand(0x79) and 0x665 + rand(0x15): every step stays inside the
      Concerned-about-the-sick area.  The stub then joins the handler's own
      plain pose (0x44B86B: edi = ebx = 0, poses 0x0A and 0x0F), so the
      walking, animation and "Directing work" text are the stock action's.
      Every other site takes the stock jump unchanged.
          stock:  FF 24 8D 88 BB 44 00   jmp dword ptr [ecx*4+0x44BB88]
          patch:  E9 rel32 90 90

   4. HEALERS STUDY BETTER (0x45A753).  Studying medicine (0xBD) ends with a
      Medicine practice step (0x4519FC: script op 7, skill 2), run at
      0x462051 as the practice roll 0x45A2C0(healer, 2); its success branch
      adds the gain at 0x45A753..0x45A75C (`push eax / push 2 / lea ecx,
      [esi+0xEAC] / call 0x455740`, the 0..100 clamped skill writer).  When
      that call came from the study step (return address 0x46206B), the
      healer is still on action 0xBD, and the chief is directing work there
      (alive, not sick, +0xEA0 = 9, action 0x81), the gain is doubled, and
      is at least 1.  The success chance is not changed, so nothing stacks
      with the Medicine technology's cure bonus.
          stock:  50 6A 02 8D 8E AC 0E 00 00
          patch:  E9 rel32 90 90 90 90

   Nothing jumps into the bytes the detours overwrite (checked in the stock
   executable).  Installed at run time by VvfpStartup(game, shipped), which
   the startup loader (VVFP Startup.dll) calls once at game start.  Only The
   Secret City (game 3) installs, and only over the stock bytes: all four
   places together or not at all (native/shared/install_sites.h). */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include "../shared/install_sites.h"

#define VV3_GAME 3

#define CURE_SITE 0x45739Au       /* test al, al  (after the Healing roll's call) */
#define CURE_FAILED 0x457431u     /* the stock failure branch's target */
#define CURE_CONTINUES 0x4573A2u  /* push 4: the cure goes on after a passed roll */
#define CHIEF_ROLL 0x45FC60u      /* stdcall (site): the chief's supervision roll */
#define VILLAGE 0x59E110u         /* the village (population manager) */
#define HOSPITAL_SITE 9           /* the Healing site: the hospital's task code */

#define SITE_INDEX 0x458D90u      /* the chief site switch: last table entry + site 9's index byte */
#define DIRECT_SWITCH 0x44B637u   /* the Directing-work handler's site jump */
#define DIRECT_PLAIN 0x44B86Bu    /* the handler's plain pose, then its walks */
#define STUDY_GAIN 0x45A753u      /* the Medicine practice gain, before the skill writer */
#define STUDY_WRITER 0x45A75Cu    /* call 0x455740 */
#define STUDY_STEP_RETURN 0x46206Bu  /* the practice step's call 0x45A2C0 returns here */
#define GET_CHIEF 0x45EF30u       /* thiscall(village): the living chief's record, or 0 */
#define ACTION_STUDY 0xBD         /* "Studying medicine" */
#define ACTION_DIRECT 0x81        /* "Directing work" */

static const unsigned char CURE_STOCK[8] = { 0x84, 0xC0, 0x0F, 0x84, 0x8F, 0x00, 0x00, 0x00 };
/* entry 11 of 0x458D64 (0x458D4C, the Directing-work order) and site 9's index 0 */
static const unsigned char INDEX_STOCK[5] = { 0x4C, 0x8D, 0x45, 0x00, 0x00 };
static const unsigned char SWITCH_STOCK[7] = { 0xFF, 0x24, 0x8D, 0x88, 0xBB, 0x44, 0x00 };
static const unsigned char GAIN_STOCK[9] = { 0x50, 0x6A, 0x02, 0x8D, 0x8E, 0xAC, 0x0E, 0x00, 0x00 };

typedef unsigned char *(__fastcall *get_chief_fn)(void *village, void *unused);

static int installed;

/* Entered by the jump at CURE_SITE with the Healing roll's result in al and
   the stack and registers exactly as the stock test sees them.  A passed
   roll continues the cure; a failed one asks the chief's supervision roll
   for the hospital, and continues on its success.  The roll (0x45FC60) is
   stdcall, one argument: the site, with ecx the village as its callers set
   it.  Its own registers are its callers' business: the game's functions
   keep edi and esi, which the cure needs afterwards. */
static __declspec(naked) void chief_cure_stub(void) {
    __asm {
        test al, al
        jne continues
        push 9
        mov ecx, 0x59E110
        mov eax, 0x45FC60
        call eax
        test al, al
        jne continues
        push 0x457431
        ret
    continues:
        push 0x4573A2
        ret
    }
}

/* Entered by the jump at DIRECT_SWITCH with eax = site - 4 and ecx = the
   site's case index, after the handler's push ebx / push ebp / push edi.
   Site 9 gets the Concerned-about-the-sick area as its bases (ebp, eax) and
   joins the handler's plain pose; every other site takes the stock jump.
   0x4032D0 is the game's cdecl rand(n), 0..n-1; it keeps ebp. */
static __declspec(naked) void direct_switch_stub(void) {
    __asm {
        cmp eax, 5
        je hospital
        jmp dword ptr [ecx*4 + 0x44BB88]
    hospital:
        push 0x79
        mov edx, 0x4032D0
        call edx
        add esp, 4
        add eax, 0x47B
        mov ebp, eax
        push 0x15
        mov edx, 0x4032D0
        call edx
        add esp, 4
        add eax, 0x665
        push 0x44B86B
        ret
    }
}

/* The chief directs work at the hospital now: alive, not sick, on the
   Healing site and doing action 0x81 (the same tests as the supervision
   roll 0x45FC60, plus the action). */
static int chief_directs_hospital(void) {
    unsigned char *chief = ((get_chief_fn)(uintptr_t)GET_CHIEF)((void *)(uintptr_t)VILLAGE, 0);
    if (chief == 0) {
        return 0;
    }
    return *(int *)(chief + 0xE78) > 0
        && chief[0xE89] == 0
        && *(int *)(chief + 0xEA0) == HOSPITAL_SITE
        && *(int *)(chief + 0xF24) == ACTION_DIRECT;
}

/* The Medicine practice gain about to be written.  Only the study step of a
   healer studying medicine, with the chief directing work there, changes. */
static int __cdecl study_gain(int gain, unsigned int caller, unsigned char *healer) {
    if (caller != STUDY_STEP_RETURN || *(int *)(healer + 0xF24) != ACTION_STUDY) {
        return gain;
    }
    if (!chief_directs_hospital()) {
        return gain;
    }
    gain *= 2;
    return gain < 1 ? 1 : gain;
}

/* Entered by the jump at STUDY_GAIN with eax = the gain and esi = the
   villager, the practice roll's return address at [esp+0x1C].  The stolen
   instructions are replayed after the gain is settled. */
static __declspec(naked) void study_gain_stub(void) {
    __asm {
        pushad
        mov ecx, dword ptr [esp + 0x3C]
        push esi
        push ecx
        push eax
        call study_gain
        add esp, 12
        mov dword ptr [esp + 0x1C], eax
        popad
        push eax
        push 2
        lea ecx, [esi + 0xEAC]
        push 0x45A75C
        ret
    }
}

/* All four places stock, then all four written -- or none
   (native/shared/install_sites.h).  The cure, directing work at the hospital
   and the study bonus are one feature: before, the cure went in on its own
   and the behaviour's three writes went one at a time, so a refused
   VirtualProtect could leave the cure without the rest, or the two detours
   without the index byte. */
static void install(void) {
    static const unsigned char take_hospital = 0x0B;
    vvfp_site_write w[4];
    if (installed
        || !vvfp_site_holds(CURE_SITE, CURE_STOCK, sizeof CURE_STOCK)
        || !vvfp_site_holds(SITE_INDEX, INDEX_STOCK, sizeof INDEX_STOCK)
        || !vvfp_site_holds(DIRECT_SWITCH, SWITCH_STOCK, sizeof SWITCH_STOCK)
        || !vvfp_site_holds(STUDY_GAIN, GAIN_STOCK, sizeof GAIN_STOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], CURE_SITE, sizeof CURE_STOCK, CURE_STOCK, 0xE9, (const void *)chief_cure_stub);
    vvfp_site_branch(&w[1], DIRECT_SWITCH, sizeof SWITCH_STOCK, SWITCH_STOCK, 0xE9,
                     (const void *)direct_switch_stub);
    vvfp_site_branch(&w[2], STUDY_GAIN, sizeof GAIN_STOCK, GAIN_STOCK, 0xE9, (const void *)study_gain_stub);
    vvfp_site_bytes(&w[3], SITE_INDEX + 4u, 1, INDEX_STOCK + 4, &take_hospital);
    if (vvfp_install_sites(w, 4)) {
        installed = 1;
    }
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (game != VV3_GAME) {
        return;
    }
    install();
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
