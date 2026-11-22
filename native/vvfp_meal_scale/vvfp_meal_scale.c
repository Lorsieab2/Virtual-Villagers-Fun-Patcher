/* VVFP Meal Scale -- Hungrier Villagers (all five games) at a multiplier whose meal is not whole food.

   WHAT (the owner, 2026-11-17: every multiplier slider goes less as well as more, 0.1x to its maximum in steps of
   0.1).  Each villager's meal is 2 food, and on Normal and Hard a difficulty extra of 2 more three times in four
   (scripts/build_hungrier_villagers_features.py).  At x N the patcher writes 2 x N into the meal's two byte
   immediates when that is whole food (0.5 -> 1, 1.5 -> 3, 2 -> 4 ...).  Any other N (0.1, 0.3, 1.7 ...) leaves those
   bytes at the normal 2 and ships this companion, which makes each of the two meals take 2 x N food ON AVERAGE: the
   whole part every time and one more food with the chance of the rest (x 0.3 = 0.6 food: 1 food six times in ten,
   else none; x 1.7 = 3.4 food: 3, and a fourth four times in ten).  N is read at start from "VVFP Meal Scale.txt"
   in the patcher's folder (native/shared/multiplier_choice.h, tenths); above 10 counts as 10.

   HOW.  The two meal instructions of each game's meal routine (the same routine live and while catching up):
     A New Home         0x42ECCC 0x42ED03   add dword [eax + 0xA2EC], -2       (83 80 EC A2 00 00 FE)
     The Lost Children  0x43BAF9 0x43BB30   add dword [eax + 0x2EAA4], -2      (83 80 A4 EA 02 00 FE)
     The Secret City    0x460080 0x4600C4   push -2; mov ecx, 0x582490         (6A FE B9 90 24 58 00)
     The Tree of Life   0x4684C8 0x46850B   push -2; mov ecx, 0x4D6DD0         (6A FE B9 D0 6D 4D 00)
     New Believers      0x472D9E 0x472DEF   push -2; mov ecx, 0x51D34C         (6A FE B9 4C D3 51 00)
   After both sites' seven stock bytes are checked (native/shared/install_sites.h: both, or none -- so a build whose
   bytes carry the multiplier is never touched), each becomes `call stub` and two nops.  A New Home and The Lost
   Children: the stub takes the food from [eax + offset] itself (sub), every register as the game left it; the
   game's own clamp then keeps food at 0 or more, as before.  The others: the stub leaves the meal's amount (minus
   the food) on the stack and the food store in ecx, exactly as the two stock instructions do, and the game then
   calls its food routine, which clamps a negative store to 0.  The instruction after each site sets the flags anew
   or does not read them (a call).  The chance is this companion's own number generator, seeded once at start: the
   game's rand is never drawn, so every other roll of the game is the same as without the patch.

   SAFETY.  Nothing is written to a save, a villager record or a file; no text is shown.  The setting file is only
   read; a whole-food multiplier (or no file) installs nothing.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/multiplier_choice.h"

#define MS_CHOICE_FILE "VVFP Meal Scale.txt"
#define MS_DEFAULT 20u                   /* 2, the slider's default, in tenths: whole food, nothing to do */
#define MS_MINIMUM 1u                    /* 0.1 */
#define MS_MAXIMUM 100u                  /* 10 (the owner, 2026-11-17: every slider capped at 10) */
#define MS_BYTE_LIMIT 640u               /* 64: the most the meal bytes hold, and so the most here too */
#define MS_SITE_BYTES 7

typedef struct {
    int game;
    int pushes;                          /* 1: push -2; mov ecx, store.  0: add dword [eax + offset], -2 */
    unsigned int value;                  /* the store's address (pushes) or its offset in the game object */
    unsigned int va[2];
} ms_game;

static const ms_game MS_GAMES[] = {
    { 1, 0, 0xA2ECu, { 0x42ECCCu, 0x42ED03u } },
    { 2, 0, 0x2EAA4u, { 0x43BAF9u, 0x43BB30u } },
    { 3, 1, 0x582490u, { 0x460080u, 0x4600C4u } },
    { 4, 1, 0x4D6DD0u, { 0x4684C8u, 0x46850Bu } },
    { 5, 1, 0x51D34Cu, { 0x472D9Eu, 0x472DEFu } },
};

static unsigned char g_expect[MS_SITE_BYTES];
static unsigned int g_tenths = MS_DEFAULT;
static unsigned int g_value;             /* the store (pushes) or its offset (adds) */
static unsigned int g_seed = 0x9E3779B9u;
static int g_installed;

/* xorshift32: this companion's own numbers, never the game's rand. */
static unsigned int next_number(void) {
    unsigned int x = g_seed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_seed = x;
    return x;
}

/* The food one meal takes at x N: 2 x N on average (tenths x 2 / 10 = tenths / 5, the rest a chance in five). */
static unsigned int __cdecl meal_food(void) {
    unsigned int whole = g_tenths / 5u, rest = g_tenths % 5u;
    return whole + ((rest != 0u && next_number() % 5u < rest) ? 1u : 0u);
}

/* A New Home, The Lost Children: [esp] the site + 5, eax the game object; the meal taken from [eax + offset]. */
__declspec(naked) static void add_stub(void) {
    __asm {
        push ecx
        push edx
        push eax
        call meal_food
        mov ecx, eax
        pop eax
        mov edx, g_value
        sub dword ptr [eax + edx], ecx
        pop edx
        pop ecx
        ret
    }
}

/* The Secret City, The Tree of Life, New Believers: [esp] the site + 5; on return [esp] is minus the meal (the
   food routine's argument) and ecx the food store, as after `push -2; mov ecx, store`. */
__declspec(naked) static void push_stub(void) {
    __asm {
        push eax
        push ecx
        push edx
        call meal_food
        pop edx
        pop ecx
        neg eax
        xchg eax, dword ptr [esp + 4]  ; the return address out, minus the meal in its place
        xchg eax, dword ptr [esp]      ; the return address on top, the saved eax back
        mov ecx, g_value
        ret
    }
}

/* 1 when both sites are installed (for the tests' emulation), else 0. */
int __stdcall VvfpMealScaleInstalled(void) {
    return g_installed;
}

/* N in tenths, as read at start (for the tests' emulation). */
int __stdcall VvfpMealScaleTenths(void) {
    return (int)g_tenths;
}

/* The food of the next meal (for the tests' emulation: the average over many). */
int __stdcall VvfpMealScaleNextMeal(void) {
    return (int)meal_food();
}

/* Called once by VVFP More Companions.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[2];
    const ms_game *g = NULL;
    int i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    for (i = 0; i < (int)(sizeof MS_GAMES / sizeof MS_GAMES[0]); ++i) {
        if (MS_GAMES[i].game == game) {
            g = &MS_GAMES[i];
        }
    }
    if (g == NULL) {
        return;
    }
    g_tenths = vvfp_read_tenths(MS_CHOICE_FILE, MS_DEFAULT, MS_MINIMUM, MS_MAXIMUM);
    if (g_tenths > MS_BYTE_LIMIT) {
        g_tenths = MS_BYTE_LIMIT;
    }
    if (g_tenths % 5u == 0u) {
        return;                          /* whole food: the bytes carry it */
    }
    g_seed ^= GetTickCount() ^ (GetCurrentProcessId() << 16);
    if (g_seed == 0u) {
        g_seed = 0x9E3779B9u;
    }
    g_value = g->value;
    if (g->pushes) {
        g_expect[0] = 0x6A;
        g_expect[1] = 0xFE;
        g_expect[2] = 0xB9;
        memcpy(g_expect + 3, &g->value, 4);
    } else {
        g_expect[0] = 0x83;
        g_expect[1] = 0x80;
        memcpy(g_expect + 2, &g->value, 4);
        g_expect[6] = 0xFE;
    }
    for (i = 0; i < 2; ++i) {
        vvfp_site_branch(&w[i], g->va[i], MS_SITE_BYTES, g_expect, 0xE8,
                         g->pushes ? (const void *)push_stub : (const void *)add_stub);
    }
    if (vvfp_install_sites(w, 2)) {
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
