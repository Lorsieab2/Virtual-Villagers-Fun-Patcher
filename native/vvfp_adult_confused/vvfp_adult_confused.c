/* VVFP Adult Confused -- "Adults Dropped on Mushrooms or Collectibles Are Confused" (all five games:
   vv1_adult_confused .. vv5_adult_confused).

   WHAT (the owner, 2026-11-14): "dropping a 14+ year old villager on a mushroom or collectible should give the
   'confused' behavior: 'only children can see and pick up mushrooms/collectibles'".  The villager does the game's
   own Confused action and the game's status line shows "Only children can see and pick up mushrooms." (a mushroom)
   or "Only children can see and pick up collectibles." (a collectible: relics and lab gear too, in New Believers).
   A child still picks it up exactly as before.  Nothing else changes.

   THE STOCK GAMES (every game counts age in units of 20 a year: a child is younger than 0x118 = 14 years):
     A New Home       the drop (0x424FF0's handler) reads the map's area under the villager (0x414200); an adult
                      ([record + 0x348] >= 0x118, 0x42510B) goes to the area dispatcher 0x424150 (0x425168), whose
                      case for a mushroom (area 0x21, written into the map where a mushroom grows, 0x4234E4) is the
                      empty default 0x424E48: the adult just stands there.  A child goes to the mushroom job
                      0x444500 (0x4251CC).  There are no collectibles.
     The Lost Children
                      an adult ([record + 0x530] >= 0x118, 0x430C9E) goes to the adult dispatcher 0x42FB20 (0x430B54),
                      whose case for a mushroom (area 0x2F) and a collectible (area 0x30) is 0x42FCAB: the Confused
                      action 0x454590 with text 43, "Only children can see collectibles." (for a mushroom too).
     The Secret City, The Tree of Life, New Believers
                      the drop 0x42D2E0 / 0x4131A0 / 0x413660 finds the item under the villager and starts its action
                      through the do-action 0x455570 / 0x45DEC0 / 0x465580: the mushroom pick (0x2F / 0x1E / 0x23; in
                      The Tree of Life also 0x90, the stew pot's take, while a stew is being made) or the collectible
                      pick (0x30 / 0x1F / 0x24).  Each handler's first test sends an adult ([record + 0xDC4] /
                      [record + 0x1B8C] / [record + 0x1B8C] >= 0x118) straight out: the adult just stands there.
                      The games' own "Only children can see collectibles." (text 0x1A / 0x80 / 0x76) is not shown by
                      any code found.

   HOW.  After every site's stock bytes and the stock code each detour relies on are checked
   (native/shared/install_sites.h: all of them, or none):
     A New Home       0x425168, the adult's `call 0x424150`, calls vv1_area: an adult on a mushroom (area 0x21) gets
                      the Confused action (0x440040, the game's own: "Confused", the head scratch, and its one-time
                      tip) and the message on the message bar (0x40BB30 on [screen + 0x350], shown 5 seconds:
                      [screen + 0x284] = the clock 0x402F70 + 5, as the game's message routine 0x421B40 does); every
                      other area goes to 0x424150 as before.
     The Lost Children
                      0x42FCAE, case 0x42FCAB's `call 0x454590`, calls vv2_confused: the same Confused action with no
                      queued text (0 -- the queue 0x44B2A0 stores nothing), then the message on the message bar
                      (0x40C510 on [screen + 0x2BC], [screen + 0x1D4] = the clock 0x403200 + 5, as the game's own
                      0x42CC9F does) chosen by the area the dispatcher was given (0x2F mushroom, else collectible).
     The Secret City, The Tree of Life, New Believers
                      the drop's `call` of the do-action for each mushroom / collectible action calls the game's
                      own stub here instead: an adult gets the game's Confused action (0x2C / 0x1A / 0x1F) with the
                      game's own "Only children can see collectibles." as its text, which the handler shows on the
                      status line when the villager is the selected one (byte [record + 0xF11] / 0x45DD10 /
                      0x4653D0); the line is then given this patch's message instead (0x42E200 / 0x44C3A0 / 0x44F0B0
                      on the status line 0x58F5E8 / 0x4DB8E8 / 0x520F68, 5 seconds, in the same frame).  A child's
                      action is started exactly as before.

   The words go through VVFP Translations.dll (vvfp_tr).  SAFETY: the game's own thread, inside the game's own drop
   code; nothing is saved, no villager record is written beyond what the game's own Confused action writes; a fault
   is caught and the action is left to the game.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/vvfp_translate.h"

#define AC_GAME_BASE 0x400000u
#define AC_CHILD_UNTIL 0x118              /* 14 years of 20 age units */

static const char MUSHROOMS[] = "Only children can see and pick up mushrooms.";
static const char COLLECTIBLES[] = "Only children can see and pick up collectibles.";

static int g_installed;
static int g_game;

static const char *ac_words(int mushroom) {
    return mushroom ? vvfp_tr("vvfp.adult_confused/vvfp_adult_confused.MUSHROOMS.s0", MUSHROOMS, 256)
                    : vvfp_tr("vvfp.adult_confused/vvfp_adult_confused.COLLECTIBLES.s0", COLLECTIBLES, 256);
}

static unsigned int rd(unsigned int va) {
    return *(volatile unsigned int *)(UINT_PTR)va;
}

static void wr(unsigned int va, unsigned int value) {
    *(volatile unsigned int *)(UINT_PTR)va = value;
}

typedef int(__fastcall *this0_fn)(unsigned int self, unsigned int edx);
typedef int(__fastcall *this1_fn)(unsigned int self, unsigned int edx, unsigned int a);
typedef int(__fastcall *this2_fn)(unsigned int self, unsigned int edx, unsigned int a, unsigned int b);

#define CALL0(va, self) (((this0_fn)(UINT_PTR)(va))((self), 0))
#define CALL1(va, self, a) (((this1_fn)(UINT_PTR)(va))((self), 0, (a)))
#define CALL2(va, self, a, b) (((this2_fn)(UINT_PTR)(va))((self), 0, (a), (b)))

/* ---- A New Home ------------------------------------------------------------------------------------------- */

#define VV1_SITE 0x425168u                /* the drop's adult `call 0x424150` (screen, slot, area) */
#define VV1_AREAS 0x424150u               /* the area dispatcher: thiscall (slot, area), ret 8 */
#define VV1_CONFUSED 0x440040u            /* the Confused action: thiscall villagers (slot), ret 4 */
#define VV1_SET_TEXT 0x40BB30u            /* a label's text: thiscall (text), ret 4 */
#define VV1_CLOCK 0x402F70u               /* seconds */
#define VV1_MUSHROOM 0x21u

static void __fastcall vv1_area(unsigned int screen, unsigned int edx, unsigned int slot, unsigned int area) {
    (void)edx;
    __try {
        unsigned int villagers = rd(screen + 0x20);
        if (area == VV1_MUSHROOM && (int)rd(villagers + slot * 0x3D8u + 0x348) >= AC_CHILD_UNTIL) {
            CALL1(VV1_CONFUSED, villagers, slot);
            CALL1(VV1_SET_TEXT, rd(screen + 0x350), (unsigned int)(UINT_PTR)ac_words(1));
            wr(screen + 0x284, (unsigned int)CALL0(VV1_CLOCK, rd(screen + 0x10)) + 5u);
            return;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    CALL2(VV1_AREAS, screen, slot, area);
}

/* ---- The Lost Children ------------------------------------------------------------------------------------ */

#define VV2_SITE 0x42FCAEu                /* case 0x42FCAB's `call 0x454590` (push 0x2B / push edi) */
#define VV2_DISPATCH 0x42FB20u            /* the adult dispatcher: thiscall (slot, area), ret 8 */
#define VV2_CONFUSED 0x454590u            /* the Confused action: thiscall villagers (slot, text), ret 8 */
#define VV2_SET_TEXT 0x40C510u
#define VV2_CLOCK 0x403200u
#define VV2_MUSHROOM 0x2Fu
#define VV2_STOCK_TEXT 0x2Bu

static void __stdcall vv2_adult(unsigned int villagers, unsigned int screen, unsigned int slot, unsigned int text,
                                unsigned int area) {
    if (text == VV2_STOCK_TEXT) {
        __try {
            CALL2(VV2_CONFUSED, villagers, slot, 0);
            CALL1(VV2_SET_TEXT, rd(screen + 0x2BC), (unsigned int)(UINT_PTR)ac_words(area == VV2_MUSHROOM));
            wr(screen + 0x1D4, (unsigned int)CALL0(VV2_CLOCK, rd(screen + 0x10)) + 5u);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        return;
    }
    CALL2(VV2_CONFUSED, villagers, slot, text);
}

/* Reached from 0x42FCAE: ecx the villagers, esi the screen (the dispatcher's this); [esp+4] the slot, [esp+8] the
   text, then the dispatcher's saved edi, esi, ebp, ebx, its return, its slot and, at [esp+0x24], its area. */
__declspec(naked) static void vv2_confused(void) {
    __asm {
        mov eax, esp
        push dword ptr [eax + 0x24]         /* area */
        push dword ptr [eax + 8]            /* text */
        push dword ptr [eax + 4]            /* slot */
        push esi                            /* the screen */
        push ecx                            /* the villagers */
        call vv2_adult
        ret 8
    }
}

/* ---- The Secret City, The Tree of Life, New Believers ----------------------------------------------------- */

typedef struct {
    unsigned int do_action;               /* thiscall record (action, arguments), ret 8 */
    unsigned int age;                     /* the record's age */
    unsigned int confused;                /* the Confused action */
    unsigned int stock_text;              /* "Only children can see collectibles." */
    unsigned int selected;                /* VV3: the record's byte; else thiscall record () -> al */
    unsigned int status_line, status_show;
    unsigned int mushroom[3];             /* the drop's mushroom actions (0 = none) */
} ac_later;

static const ac_later LATER[3] = {
    {0x455570u, 0xDC4u, 0x2Cu, 0x1Au, 0xF11u, 0x58F5E8u, 0x42E200u, {0x2Fu, 0, 0}},
    {0x45DEC0u, 0x1B8Cu, 0x1Au, 0x80u, 0x45DD10u, 0x4DB8E8u, 0x44C3A0u, {0x1Eu, 0x90u, 0}},
    {0x465580u, 0x1B8Cu, 0x1Fu, 0x76u, 0x4653D0u, 0x520F68u, 0x44F0B0u, {0x23u, 0, 0}},
};

/* Takes the place of the drop's `call do-action` for a mushroom or collectible: ecx the villager's record. */
static void __fastcall later_drop(unsigned int record, unsigned int edx, unsigned int action, unsigned int args) {
    const ac_later *g = &LATER[g_game - 3];
    (void)edx;
    __try {
        if ((int)rd(record + g->age) >= AC_CHILD_UNTIL) {
            unsigned int text[2];
            int shown;
            text[0] = g->stock_text;
            text[1] = 0xFFFFFFFFu;
            CALL2(g->do_action, record, g->confused, (unsigned int)(UINT_PTR)text);
            shown = g_game == 3 ? *(volatile unsigned char *)(UINT_PTR)(record + g->selected) != 0
                                : (CALL0(g->selected, record) & 0xFF) != 0;
            if (shown) {
                int mushroom = action == g->mushroom[0] || (g->mushroom[1] != 0 && action == g->mushroom[1]);
                CALL1(g->status_show, g->status_line, (unsigned int)(UINT_PTR)ac_words(mushroom));
            }
            return;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    CALL2(g->do_action, record, action, args);
}

/* ---- Install ---------------------------------------------------------------------------------------------- */

typedef struct {
    unsigned int va;                      /* the call (E8 rel32) */
    unsigned char before[8];              /* the instructions just before it (push action / mov ecx, edi ...) */
    int before_length;
} ac_site;

/* The drop's call sites, each with the pushes before it, per game. */
static const ac_site VV3_SITES[] = {
    {0x42D377u, {0x51, 0x6A, 0x2F, 0x8B, 0xCF}, 5},                     /* push ecx / push 0x2F / mov ecx, edi */
    {0x42D391u, {0x52, 0x6A, 0x30, 0x8B, 0xCF}, 5},                     /* push edx / push 0x30 / mov ecx, edi */
};
static const ac_site VV4_SITES[] = {
    {0x41324Cu, {0x50, 0x68, 0x90, 0x00, 0x00, 0x00, 0x8B, 0xCF}, 8},   /* push eax / push 0x90 / mov ecx, edi */
    {0x413266u, {0x51, 0x6A, 0x1E, 0x8B, 0xCF}, 5},                     /* push ecx / push 0x1E / mov ecx, edi */
    {0x413284u, {0x6A, 0x1F, 0x8B, 0xCF, 0x89, 0x74, 0x24, 0x28}, 8},   /* push 0x1F / mov ecx, edi / mov [], esi */
};
static const ac_site VV5_SITES[] = {
    {0x413700u, {0x50, 0x6A, 0x23, 0x8B, 0xCF}, 5},                     /* push eax / push 0x23 / mov ecx, edi */
    {0x41371Au, {0x51, 0x6A, 0x24, 0x8B, 0xCF}, 5},                     /* push ecx / push 0x24 / mov ecx, edi */
};

/* The first bytes of every game routine called here: the code these calls rely on is the stock code. */
typedef struct {
    unsigned int va;
    unsigned char bytes[10];
    int length;
} ac_code;

static const ac_code VV1_CODE[] = {
    {0x424150u, {0x8B, 0x44, 0x24, 0x08, 0x83, 0xC0, 0xFE, 0x83}, 8},
    {0x440040u, {0x56, 0x8B, 0xF1, 0x8B, 0x86, 0x10, 0xE0, 0x03}, 8},
    {0x40BB30u, {0x8B, 0x49, 0x10, 0xE9, 0x28, 0xFD, 0xFF, 0xFF}, 8},
    {0x402F70u, {0x51, 0x8D, 0x44, 0x24, 0x00, 0x50, 0xE8, 0x9F}, 8},
    /* the drop's adult test: cmp [eax+0x348], ebp (ebp = 0x118, 0x425043) */
    {0x42510Bu, {0x39, 0xA8, 0x48, 0x03, 0x00, 0x00, 0x7D, 0x35}, 8},
    /* push eax / mov eax, [esi+0x294] / push eax / mov ecx, esi -- the area, the slot, the screen */
    {0x42515Eu, {0x50, 0x8B, 0x86, 0x94, 0x02, 0x00, 0x00, 0x50, 0x8B, 0xCE}, 10},
};
static const ac_code VV2_CODE[] = {
    {0x42FB20u, {0x8B, 0x54, 0x24, 0x08, 0x53, 0x55, 0x56, 0x57}, 8},    /* the frame vv2_confused reads */
    {0x454590u, {0x56, 0x8B, 0xF1, 0x8B, 0x86, 0xD4, 0x74, 0xE5}, 8},
    {0x40C510u, {0x8B, 0x49, 0x10, 0xE9, 0x28, 0xFD, 0xFF, 0xFF}, 8},
    {0x403200u, {0x51, 0x8D, 0x44, 0x24, 0x00, 0x50, 0xE8, 0x8F}, 8},
    {0x42FCA6u, {0x5D, 0x5B, 0xC2, 0x08, 0x00, 0x6A, 0x2B, 0x57}, 8},    /* pop ebp / pop ebx / ret 8 / push 0x2B /
                                                                          push edi -- then the site */
};
static const ac_code VV3_CODE[] = {
    {0x455570u, {0x8B, 0x54, 0x24, 0x08, 0x8B, 0x44, 0x24, 0x04}, 8},
    {0x42E200u, {0x8B, 0x44, 0x24, 0x04, 0x56, 0x68, 0xFF, 0x00}, 8},
};
static const ac_code VV4_CODE[] = {
    {0x45DEC0u, {0x8B, 0x54, 0x24, 0x08, 0x8B, 0x44, 0x24, 0x04}, 8},
    {0x44C3A0u, {0x8B, 0x44, 0x24, 0x04, 0x56, 0x68, 0xFF, 0x00}, 8},
    {0x45DD10u, {0x56, 0x8B, 0xF1, 0xE8, 0x58, 0x21, 0xFC, 0xFF}, 8},
};
static const ac_code VV5_CODE[] = {
    {0x465580u, {0x8B, 0x54, 0x24, 0x08, 0x8B, 0x44, 0x24, 0x04}, 8},
    {0x44F0B0u, {0x8B, 0x44, 0x24, 0x04, 0x56, 0x68, 0xFF, 0x00}, 8},
    {0x4653D0u, {0x56, 0x8B, 0xF1, 0xE8, 0x78, 0x05, 0xFC, 0xFF}, 8},
};

static int code_holds(const ac_code *code, int count) {
    int i;
    for (i = 0; i < count; ++i) {
        if (!vvfp_site_holds(code[i].va, code[i].bytes, code[i].length)) {
            return 0;
        }
    }
    return 1;
}

/* A stock `call target` at va: E8 and the rel32 to target. */
static void call_bytes(unsigned char out[5], unsigned int va, unsigned int target) {
    unsigned int rel = target - (va + 5u);
    out[0] = 0xE8;
    out[1] = (unsigned char)rel;
    out[2] = (unsigned char)(rel >> 8);
    out[3] = (unsigned char)(rel >> 16);
    out[4] = (unsigned char)(rel >> 24);
}

/* 1 when every site of the game is installed (for the tests' emulation), else 0. */
int __stdcall VvfpAdultConfusedInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[3];
    static unsigned char stock[3][5];
    const unsigned char *module;
    const ac_site *sites = NULL;
    int count = 0, i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleA(NULL);
    if (module != NULL && (UINT_PTR)module != AC_GAME_BASE) {
        return;                             /* every site is a VA of the games' fixed base */
    }
    if (game == 1) {
        if (!code_holds(VV1_CODE, sizeof VV1_CODE / sizeof VV1_CODE[0])) {
            return;
        }
        call_bytes(stock[0], VV1_SITE, VV1_AREAS);
        vvfp_site_branch(&w[count++], VV1_SITE, 5, stock[0], 0xE8, (const void *)vv1_area);
    } else if (game == 2) {
        if (!code_holds(VV2_CODE, sizeof VV2_CODE / sizeof VV2_CODE[0])) {
            return;
        }
        call_bytes(stock[0], VV2_SITE, VV2_CONFUSED);
        vvfp_site_branch(&w[count++], VV2_SITE, 5, stock[0], 0xE8, (const void *)vv2_confused);
    } else if (game >= 3 && game <= 5) {
        const ac_code *code = game == 3 ? VV3_CODE : game == 4 ? VV4_CODE : VV5_CODE;
        int codes = game == 4 ? 3 : (game == 3 ? 2 : 3);
        int n = game == 3 ? 2 : game == 4 ? 3 : 2;
        sites = game == 3 ? VV3_SITES : game == 4 ? VV4_SITES : VV5_SITES;
        if (!code_holds(code, codes)) {
            return;
        }
        for (i = 0; i < n; ++i) {
            if (!vvfp_site_holds(sites[i].va - (unsigned int)sites[i].before_length, sites[i].before,
                                 sites[i].before_length)) {
                return;
            }
            call_bytes(stock[i], sites[i].va, LATER[game - 3].do_action);
            vvfp_site_branch(&w[count++], sites[i].va, 5, stock[i], 0xE8, (const void *)later_drop);
        }
    } else {
        return;
    }
    g_game = game;
    if (vvfp_install_sites(w, count)) {
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
