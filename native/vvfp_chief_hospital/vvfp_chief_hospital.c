/* VVFP VV3 Chief Hospital -- the Tribal Chief supervising the hospital helps
   the healers' cures (The Secret City).

   The stock game: dropping the Tribal Chief on the Hospital hotspot assigns
   the chief the Healing site (the chief's +0xEA0 = 9, written by the
   hospital drop handler 0x4215E0 when Medicine is 2 or more).  The chief's
   supervision bonus is the roll 0x45FC60(site): it passes only when the
   chief is alive, not sick and standing on that site, and then with
   chance 25% x Leadership.  The stock game asks that roll for the
   Fishing, Fruit, Honey, Hut, Research and Puzzle work, but never for a
   cure.  A healer's cure (0x457350) makes its Healing roll 0x45A2C0 at
   0x457395; when the roll fails the cure ends at 0x457431.

   This companion adds the chief's roll there.  A healer's failed roll is
   followed by the supervision roll 0x45FC60(9); when that passes the cure
   continues exactly as a passed Healing roll (0x4573A2), otherwise the
   stock failure runs (0x457431).  With no chief on the hospital the roll
   draws nothing from the game's random generator, so every other cure is
   stock.

   SITE.  Eight bytes at 0x45739A, after the call 0x457395:
       stock:  84 C0          test al, al
               0F 84 8F 00 00 00   je 0x457431
       patch:  E9 rel32 (jmp to the stub)  90 90 90
   Nothing jumps into those bytes (checked in the stock executable).  The
   stub replays the test, so a passed roll reaches 0x4573A2 unchanged.

   Installed at run time by VvfpStartup(game, shipped), which the startup
   loader (VVFP Startup.dll) calls once at game start for every shipped
   companion.  Only The Secret City (game 3) installs; the stock bytes at the
   site are verified first, and any other build installs nothing. */
#include <windows.h>
#include <string.h>
#include <stdint.h>

#define VV3_GAME 3

#define CURE_SITE 0x45739Au       /* test al, al  (after the Healing roll's call) */
#define CURE_FAILED 0x457431u     /* the stock failure branch's target */
#define CURE_CONTINUES 0x4573A2u  /* push 4: the cure goes on after a passed roll */
#define CHIEF_ROLL 0x45FC60u      /* stdcall (site): the chief's supervision roll */
#define VILLAGE 0x59E110u         /* the village (population manager) */
#define HOSPITAL_SITE 9           /* the Healing site: the hospital's task code */

static const unsigned char CURE_STOCK[8] = { 0x84, 0xC0, 0x0F, 0x84, 0x8F, 0x00, 0x00, 0x00 };

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

/* Write `length` bytes at `va`, unprotecting only that range (the same
   narrow write the Story companion makes). */
static int write_code(unsigned int va, const unsigned char *bytes, int length) {
    DWORD old;
    void *at = (void *)(uintptr_t)va;
    if (!VirtualProtect(at, (SIZE_T)length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, (size_t)length);
    VirtualProtect(at, (SIZE_T)length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)length);
    return 1;
}

/* The stock bytes first: a build that differs gets no change at all. */
static int site_is_stock(void) {
    return memcmp((const void *)(uintptr_t)CURE_SITE, CURE_STOCK, sizeof CURE_STOCK) == 0;
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    unsigned char bytes[8];
    unsigned int rel;
    (void)shipped;
    if (game != VV3_GAME || installed || !site_is_stock()) {
        return;
    }
    rel = (unsigned int)((uintptr_t)chief_cure_stub - (CURE_SITE + 5u));
    bytes[0] = 0xE9;
    memcpy(bytes + 1, &rel, 4);
    bytes[5] = 0x90;
    bytes[6] = 0x90;
    bytes[7] = 0x90;
    if (write_code(CURE_SITE, bytes, sizeof bytes)) {
        installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
