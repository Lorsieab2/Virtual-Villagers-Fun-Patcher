/* VVFP Island Events Scale -- "Island Events Scale With Population (like The Lost Children)" and its alternative
   "Island Events Scale With Stored Food and Tech Points" (A New Home, The Tree of Life, New Believers).

   WHAT (the owner, 2026-11-12).  The Lost Children multiplies its island events' food and tech-point amounts by
   k = 1 up to 25 living villagers, 2 for 26 to 50 and 3 above 50 (its two-choice factor 0x41F720; The Secret
   City's are scaled too).  A New Home, The Tree of Life and New Believers pay fixed amounts.  With this companion:

     * POPULATION (the row vvN_island_events_scale_with_population): each amount below is multiplied by that k,
       the population counted by the game's own routine -- A New Home 0x41CF90 (living villagers plus the babies
       being carried), The Tree of Life 0x467610 (the same), New Believers 0x4713F0 (believers plus the babies
       they carry; Heathens are not counted: its record test 0x466170 with 0 refuses a Heathen);
     * STORED (vvN_island_events_scale_with_stored_amounts, which ships the flag file ES_STORED_FLAG beside this
       DLL): each amount becomes the stock amount plus a tenth (rounded down) of the food -- for a food amount --
       or the tech points -- for a tech amount -- stored at that moment, never less than the stock amount (a
       loss grows the same way: -300 with 5,000 food stored is -800).

   A gain stays a gain and a loss a loss.  Every loss keeps the game's own floor: a single-result loss setter
   clamps its loss to what is stored -- but it tests the store against its STOCK immediate, so the companion
   applies the same rule to the scaled loss first (ES_LOSS8), and the popup, which prints the amount the setter
   leaves at [this+8] as {award}, shows what is taken; the two-choice events' food and tech writers stop at 0.
   Food Mastery still raises a food gain inside the game's food writer, after this.  A random amount (A
   New Home's Wild Mushroom and Brass Compass, New Believers' Strange Crystals, Pesky Critter and Mushroom Day) is
   scaled after the game's roll and base, so the roll itself -- and a Story / Cheat Upgrades Pick Island Event
   setting that answers it -- is the game's own.

   HOW.  Each site is the one instruction that puts the stock amount in place (a `mov [ecx+8], imm`, a
   `mov [esp+4], imm`, a `push imm`, an `add eax, imm` after the roll, ...).  After every site's stock bytes are
   checked (native/shared/install_sites.h: all of them, or none), each becomes a `call site_stub` and nops.  The
   stub hands the registers to on_site, which finds the site by the return address and does exactly what the
   stock instruction did, with the scaled amount.  The flags are the stock flags before the site (the stock
   arithmetic sites' own flags are read by nothing: each is followed by a push, a mov and a call, or by an
   `add esp, 4` that sets them anew).

   SAFETY.  The game's own count routine runs on the game's own thread, between frames, exactly as its own
   callers run it; a fault in counting or reading leaves the stock amount.  Nothing is written to a save, a
   villager record or a file; no text is shown.  Custom Island Events (Story / Cheat Upgrades) never pass these
   sites, so they keep their own amounts.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"

#define ES_STORED_FLAG "VVFP Island Events Scale Stored.txt"

enum { ES_FOOD = 0, ES_TECH = 1 };
enum {
    ES_ECX8 = 1,        /* mov dword [ecx+8], imm32: a single-result gain (7)  */
    ES_LOSS8,           /* the same, a single-result loss: the setter then clamps it to what is stored by comparing
                           the store with the STOCK immediate (cmp eax, imm / jge), so a scaled loss is clamped here
                           first, the same way: no more than is stored (and the {award} shown is what is taken) */
    ES_ESP4,            /* mov dword [esp+4], imm32                       (8)  */
    ES_PUSH,            /* push imm32                                     (5)  */
    ES_PUSH_ECX,        /* push imm8 / mov ecx, STORE                     (7)  */
    ES_ADD_PUSH_ECX,    /* add eax, imm8 / push eax / mov ecx, STORE      (9)  */
    ES_ADD_EAX,         /* add eax, imm32 (after the roll)                (5)  */
    ES_SUB_ECX          /* mov ecx, imm32 / sub ecx, eax (after the roll) (7)  */
};

typedef struct {
    unsigned int va;
    unsigned char length;
    unsigned char form;
    unsigned char kind;
    int stock;                         /* the amount the instruction holds (signed) */
    unsigned char expect[9];
} es_site;

typedef struct {
    int game;
    const es_site *sites;
    int count;
    unsigned int count_routine;        /* the game's population count, thiscall on the villager manager (The Tree of
                                          Life, New Believers: where the executable says it is, vvN_villager_table.h,
                                          which 256 Villagers moves) or on the world (A New Home) */
    unsigned int food;                 /* VA of the stored food (0: world + food_field) */
    unsigned int tech;
    unsigned int food_field;           /* A New Home: the world's fields */
    unsigned int tech_field;
    unsigned int world_field;          /* A New Home: the encounter's world pointer, [esi + this] */
} es_game;

/* A New Home: the four encounters with a fixed or rolled amount (the resolve 0x419380; esi the encounter). */
static const es_site VV1_SITES[] = {
    /* The Whale (food): push 0x3E8 before call 0x41D140 */
    { 0x41944Fu, 5, ES_PUSH, ES_FOOD, 1000, { 0x68, 0xE8, 0x03, 0x00, 0x00 } },
    /* The Troubled Child (tech): push 0xBB8, then jmp 0x41A36D to the shared call 0x41D120 */
    { 0x419C35u, 5, ES_PUSH, ES_TECH, 3000, { 0x68, 0xB8, 0x0B, 0x00, 0x00 } },
    /* The Wild Mushroom, delicious (food): rand(200) + 300 */
    { 0x419F09u, 5, ES_ADD_EAX, ES_FOOD, 300, { 0x05, 0x2C, 0x01, 0x00, 0x00 } },
    /* The Brass Compass, given to the researchers (tech): rand(3000) + 2000 */
    { 0x41A367u, 5, ES_ADD_EAX, ES_TECH, 2000, { 0x05, 0xD0, 0x07, 0x00, 0x00 } },
};

/* The Tree of Life: single-result setters (vtable [14]) and two-choice results. */
static const es_site VV4_SITES[] = {
    { 0x414730u, 7, ES_LOSS8,ES_FOOD, 100, { 0xC7, 0x41, 0x08, 0x64, 0x00, 0x00, 0x00 } },          /* Creeping Mold, lost */
    { 0x414930u, 7, ES_ECX8, ES_FOOD, 300, { 0xC7, 0x41, 0x08, 0x2C, 0x01, 0x00, 0x00 } },          /* Footprints, food gained */
    { 0x414980u, 7, ES_LOSS8,ES_FOOD, 300, { 0xC7, 0x41, 0x08, 0x2C, 0x01, 0x00, 0x00 } },          /* Footprints, food lost */
    { 0x414A00u, 7, ES_ECX8, ES_TECH, 2000, { 0xC7, 0x41, 0x08, 0xD0, 0x07, 0x00, 0x00 } },         /* Footprints, tech gained */
    { 0x414A50u, 7, ES_LOSS8,ES_TECH, 2000, { 0xC7, 0x41, 0x08, 0xD0, 0x07, 0x00, 0x00 } },         /* Footprints, tech lost */
    { 0x415201u, 8, ES_ESP4, ES_FOOD, 300, { 0xC7, 0x44, 0x24, 0x04, 0x2C, 0x01, 0x00, 0x00 } },    /* Arc of Colors */
    { 0x41585Au, 8, ES_ESP4, ES_TECH, 3000, { 0xC7, 0x44, 0x24, 0x04, 0xB8, 0x0B, 0x00, 0x00 } },   /* Calabash, first notch */
    { 0x415867u, 8, ES_ESP4, ES_TECH, -2000, { 0xC7, 0x44, 0x24, 0x04, 0x30, 0xF8, 0xFF, 0xFF } },  /* Calabash, to the top */
    { 0x415942u, 5, ES_PUSH, ES_TECH, -500, { 0x68, 0x0C, 0xFE, 0xFF, 0xFF } },                      /* Climber, yelling */
    { 0x415A74u, 8, ES_ESP4, ES_TECH, 500, { 0xC7, 0x44, 0x24, 0x04, 0xF4, 0x01, 0x00, 0x00 } },    /* Mosquito Larvae, oil */
    { 0x415B39u, 8, ES_ESP4, ES_TECH, 1000, { 0xC7, 0x44, 0x24, 0x04, 0xE8, 0x03, 0x00, 0x00 } },   /* Faces in the Night */
    { 0x415D7Fu, 8, ES_ESP4, ES_TECH, 5000, { 0xC7, 0x44, 0x24, 0x04, 0x88, 0x13, 0x00, 0x00 } },   /* Sealed Box */
    { 0x416715u, 8, ES_ESP4, ES_TECH, 2000, { 0xC7, 0x44, 0x24, 0x04, 0xD0, 0x07, 0x00, 0x00 } },   /* Aspiring Scientist, salts */
    { 0x416728u, 8, ES_ESP4, ES_TECH, -1000, { 0xC7, 0x44, 0x24, 0x04, 0x18, 0xFC, 0xFF, 0xFF } },  /* Aspiring Scientist, algae */
};

/* New Believers. */
static const es_site VV5_SITES[] = {
    { 0x414A00u, 7, ES_LOSS8,ES_FOOD, 100, { 0xC7, 0x41, 0x08, 0x64, 0x00, 0x00, 0x00 } },          /* Creeping Mold, lost */
    { 0x414C10u, 7, ES_ECX8, ES_FOOD, 300, { 0xC7, 0x41, 0x08, 0x2C, 0x01, 0x00, 0x00 } },          /* Footprints, food gained */
    { 0x414C60u, 7, ES_LOSS8,ES_FOOD, 300, { 0xC7, 0x41, 0x08, 0x2C, 0x01, 0x00, 0x00 } },          /* Footprints, food lost */
    { 0x414CE0u, 7, ES_ECX8, ES_TECH, 2000, { 0xC7, 0x41, 0x08, 0xD0, 0x07, 0x00, 0x00 } },         /* Footprints, tech gained */
    { 0x414D30u, 7, ES_LOSS8,ES_TECH, 2000, { 0xC7, 0x41, 0x08, 0xD0, 0x07, 0x00, 0x00 } },         /* Footprints, tech lost */
    { 0x414EFDu, 5, ES_ADD_EAX, ES_TECH, 2000, { 0x05, 0xD0, 0x07, 0x00, 0x00 } },                   /* Strange Crystals */
    { 0x41507Au, 7, ES_SUB_ECX, ES_TECH, -500, { 0xB9, 0x0C, 0xFE, 0xFF, 0xFF, 0x2B, 0xC8 } },       /* Pesky Critter */
    { 0x415110u, 9, ES_ADD_PUSH_ECX, ES_FOOD, 50, { 0x83, 0xC0, 0x32, 0x50, 0xB9, 0x4C, 0xD3, 0x51, 0x00 } },
                                                                                                      /* Mushroom Day, food */
    { 0x415128u, 7, ES_SUB_ECX, ES_TECH, -500, { 0xB9, 0x0C, 0xFE, 0xFF, 0xFF, 0x2B, 0xC8 } },       /* Mushroom Day, tech */
    { 0x4155B0u, 5, ES_PUSH, ES_TECH, 2000, { 0x68, 0xD0, 0x07, 0x00, 0x00 } },                      /* News From Another Tribe */
    { 0x415F01u, 8, ES_ESP4, ES_FOOD, -40, { 0xC7, 0x44, 0x24, 0x04, 0xD8, 0xFF, 0xFF, 0xFF } },     /* Spying on the Heathens */
    { 0x4160A5u, 8, ES_ESP4, ES_TECH, 500, { 0xC7, 0x44, 0x24, 0x04, 0xF4, 0x01, 0x00, 0x00 } },    /* You're Doing It Wrong */
    { 0x4163CAu, 7, ES_PUSH_ECX, ES_FOOD, -25, { 0x6A, 0xE7, 0xB9, 0x4C, 0xD3, 0x51, 0x00 } },       /* Outreach?, food */
    { 0x4163D7u, 8, ES_ESP4, ES_TECH, -800, { 0xC7, 0x44, 0x24, 0x04, 0xE0, 0xFC, 0xFF, 0xFF } },   /* Outreach?, tech */
    { 0x41655Au, 5, ES_PUSH, ES_TECH, 2000, { 0x68, 0xD0, 0x07, 0x00, 0x00 } },                      /* Advanced Artifacts, gained */
    { 0x416548u, 8, ES_ESP4, ES_TECH, -100, { 0xC7, 0x44, 0x24, 0x04, 0x9C, 0xFF, 0xFF, 0xFF } },   /* Advanced Artifacts, lost */
    { 0x416648u, 5, ES_PUSH, ES_TECH, 1500, { 0x68, 0xDC, 0x05, 0x00, 0x00 } },                      /* Trick Or Trade, ruse */
    { 0x41666Bu, 7, ES_PUSH_ECX, ES_FOOD, -100, { 0x6A, 0x9C, 0xB9, 0x4C, 0xD3, 0x51, 0x00 } },      /* Trick Or Trade, food */
    { 0x416692u, 8, ES_ESP4, ES_TECH, 3000, { 0xC7, 0x44, 0x24, 0x04, 0xB8, 0x0B, 0x00, 0x00 } },   /* Trick Or Trade, tech */
    { 0x416891u, 8, ES_ESP4, ES_TECH, 1500, { 0xC7, 0x44, 0x24, 0x04, 0xDC, 0x05, 0x00, 0x00 } },   /* Aphids */
    { 0x4169A9u, 8, ES_ESP4, ES_TECH, -2000, { 0xC7, 0x44, 0x24, 0x04, 0x30, 0xF8, 0xFF, 0xFF } },  /* The Defector, a spy */
    { 0x416A57u, 8, ES_ESP4, ES_FOOD, 200, { 0xC7, 0x44, 0x24, 0x04, 0xC8, 0x00, 0x00, 0x00 } },    /* The Straw Hat */
    { 0x416B3Au, 8, ES_ESP4, ES_TECH, 2000, { 0xC7, 0x44, 0x24, 0x04, 0xD0, 0x07, 0x00, 0x00 } },   /* Strange Nectar */
};

#define ES_COUNT(a) ((int)(sizeof(a) / sizeof((a)[0])))

static const es_game ES_GAMES[] = {
    /* A New Home: 0x41CF90 on the world, the encounter's [esi+0x50A4] (as the island events' 0x4280B7 calls it). */
    { 1, VV1_SITES, ES_COUNT(VV1_SITES), 0x41CF90u, 0u, 0u, 0xA2ECu, 0xA2FCu, 0x50A4u },
    /* The Tree of Life: 0x467610, the count the island-event trigger (0x43FA4E) and the room check (0x468357) ask. */
    { 4, VV4_SITES, ES_COUNT(VV4_SITES), 0x467610u, 0x4D6DD0u, 0x4D6F88u, 0u, 0u, 0u },
    /* New Believers: 0x4713F0, believers only (the trigger 0x4426FB, the room check 0x472BD7). */
    { 5, VV5_SITES, ES_COUNT(VV5_SITES), 0x4713F0u, 0x51D34Cu, 0x51D5F8u, 0u, 0u, 0u },
};

#define ES_MAX_SITES 32
#define ES_MODE_POPULATION 1
#define ES_MODE_STORED 2

/* pushad's frame under the flags and the return address the site's call pushed. */
typedef struct {
    unsigned int edi, esi, ebp, esp, ebx, edx, ecx, eax;
    unsigned int eflags;
    unsigned int ret;
} es_frame;

static const es_game *g_game;
static unsigned int g_manager;         /* The Tree of Life, New Believers: the villager manager's VA */
static int g_mode;
static int g_installed;
static unsigned int g_resume;          /* where a push-form site goes on (the game runs events on one thread) */
static int g_last_k;                   /* the last population factor used (for the tests' emulation) */

/* The population as the game's own routine counts it; -1 when it cannot be asked. */
static int es_population(const es_game *g, const es_frame *f) {
    void *self;
    if (g_manager != 0) {
        self = (void *)(UINT_PTR)g_manager;
    } else {
        self = *(void *const volatile *)(UINT_PTR)(f->esi + g->world_field);
    }
    if (self == NULL) {
        return -1;
    }
    return ((int (__fastcall *)(void *, void *))(UINT_PTR)g->count_routine)(self, NULL);
}

static volatile int *es_store(const es_game *g, const es_frame *f, int kind) {
    if (g->food != 0) {
        return (volatile int *)(UINT_PTR)(kind == ES_FOOD ? g->food : g->tech);
    }
    {
        unsigned int world = *(const volatile unsigned int *)(UINT_PTR)(f->esi + g->world_field);
        if (world == 0) {
            return NULL;
        }
        return (volatile int *)(UINT_PTR)(world + (kind == ES_FOOD ? g->food_field : g->tech_field));
    }
}

static int es_clamp(__int64 v) {
    if (v > 0x7FFFFFFF) {
        return 0x7FFFFFFF;
    }
    if (v < -0x7FFFFFFF - 1) {
        return -0x7FFFFFFF - 1;
    }
    return (int)v;
}

/* The amount the site puts in place: `amount` (the stock amount, after the roll) scaled. */
static int es_scale(const es_site *s, const es_frame *f, int amount) {
    int out = amount;
    __try {
        if (g_mode == ES_MODE_STORED) {
            volatile int *store = es_store(g_game, f, s->kind);
            if (store != NULL) {
                int stored = *store;
                __int64 bonus = stored > 0 ? (__int64)(stored / 10) : 0;
                out = es_clamp(amount >= 0 ? (__int64)amount + bonus : (__int64)amount - bonus);
            }
        } else {
            int n = es_population(g_game, f);
            int k = n > 50 ? 3 : (n > 25 ? 2 : 1);
            g_last_k = n < 0 ? 0 : k;
            out = es_clamp((__int64)amount * k);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out = amount;
    }
    return out;
}

/* A site's call: do what its stock instruction did, with the scaled amount.  1: a push-form site (the value is in
   the return address's slot, and the stub goes on at g_resume). */
static int __cdecl on_site(es_frame *f) {
    const es_site *s = NULL;
    unsigned int at = f->ret - 5u;
    unsigned int esp_before = (unsigned int)(UINT_PTR)&f->ret + 4u;     /* the stack as the site found it */
    int i, value;
    for (i = 0; i < g_game->count; ++i) {
        if (g_game->sites[i].va == at) {
            s = &g_game->sites[i];
            break;
        }
    }
    if (s == NULL) {
        return 0;                      /* never: only the table's sites call here */
    }
    switch (s->form) {
    case ES_ECX8:
        *(int *)(UINT_PTR)(f->ecx + 8u) = es_scale(s, f, s->stock);
        return 0;
    case ES_LOSS8:
        value = es_scale(s, f, s->stock);
        __try {
            volatile int *store = es_store(g_game, f, s->kind);
            if (store != NULL && *store < value) {
                value = *store;        /* the setter's own rule (if stored < amount: amount = stored) */
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        *(int *)(UINT_PTR)(f->ecx + 8u) = value;
        return 0;
    case ES_ESP4:
        *(int *)(UINT_PTR)(esp_before + 4u) = es_scale(s, f, s->stock);
        return 0;
    case ES_ADD_EAX:
        f->eax = (unsigned int)es_scale(s, f, (int)f->eax + s->stock);
        return 0;
    case ES_SUB_ECX:
        f->ecx = (unsigned int)es_scale(s, f, s->stock - (int)f->eax);
        return 0;
    case ES_PUSH:
        value = es_scale(s, f, s->stock);
        break;
    case ES_PUSH_ECX:
        value = es_scale(s, f, s->stock);
        f->ecx = *(const unsigned int *)(s->expect + 3);
        break;
    case ES_ADD_PUSH_ECX:
        f->eax = (unsigned int)((int)f->eax + s->stock);
        value = es_scale(s, f, (int)f->eax);
        f->ecx = *(const unsigned int *)(s->expect + 5);
        break;
    default:
        return 0;
    }
    g_resume = f->ret;
    f->ret = (unsigned int)value;
    return 1;
}

/* Every site's call comes here: [esp] the address after the call (the site + 5). */
__declspec(naked) static void site_stub(void) {
    __asm {
        pushfd
        pushad
        push esp
        call on_site
        add esp, 4
        test eax, eax
        popad
        jnz pushed
        popfd
        ret
    pushed:
        popfd
        jmp dword ptr [g_resume]
    }
}

/* "Island Events Scale With Stored Food and Tech Points" is shipped: its file is in the patcher's folder.  Any
   failure reads as not shipped (the population row). */
static int stored_shipped(void) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    DWORD attributes;
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, ES_STORED_FLAG) == 0) {
        return 0;
    }
    attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpIslandEventsScaleInstalled(void) {
    return g_installed;
}

/* 1: scaled by the population; 2: by the stored food and tech points; 0: not installed (for the tests). */
int __stdcall VvfpIslandEventsScaleMode(void) {
    return g_installed ? g_mode : 0;
}

/* The population factor the last population-scaled amount used, 0 when the count could not be asked (tests). */
int __stdcall VvfpIslandEventsScaleLastFactor(void) {
    return g_last_k;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[ES_MAX_SITES];
    const es_game *g = NULL;
    int i;
    (void)shipped;
    if (g_installed) {
        return;
    }
    for (i = 0; i < ES_COUNT(ES_GAMES); ++i) {
        if (ES_GAMES[i].game == game) {
            g = &ES_GAMES[i];
        }
    }
    if (g == NULL || g->count > ES_MAX_SITES) {
        return;
    }
    if (game == 4 || game == 5) {
        const unsigned char *module = (const unsigned char *)GetModuleHandleA(NULL);
        unsigned int rva = 0, slots = 0;
        if (module == NULL) {
            module = (const unsigned char *)(UINT_PTR)0x400000u;   /* the games' fixed base, as every site's VA */
        }
        if (game == 4) {
            vv4_villager_table(module, &rva, &slots);
        } else {
            vv5_villager_table(module, &rva, &slots);
        }
        g_manager = (unsigned int)(UINT_PTR)module + rva;
    }
    for (i = 0; i < g->count; ++i) {
        vvfp_site_branch(&w[i], g->sites[i].va, g->sites[i].length, g->sites[i].expect, 0xE8,
                         (const void *)site_stub);
    }
    g_game = g;
    g_mode = stored_shipped() ? ES_MODE_STORED : ES_MODE_POPULATION;
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
