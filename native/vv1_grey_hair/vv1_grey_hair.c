/* VVFP VV1 Grey Hair -- "Grey Hair at 55" for A New Home (the owner, 2026-10-28): a villager is drawn
   with a grey head from age 55, the age The Lost Children to New Believers switch to their old heads.

   THE LATER GAMES.  Each draws a villager's head from its old-head art once the age the Details screen
   shows reaches 1,100 age units (55 years at 20 units a year), compared against that constant alone:
   VV2 0x4469BA (village), 0x445694 (Details); VV3 0x46086D / 0x4608AE (village), 0x456A15 (Details);
   VV4 0x467E89 (village), 0x45F6C4 (Details); VV5 0x4722A2 (village), 0x466DC1 (Details).

   A NEW HOME.  The stock game has one head sheet per sex and no old one: male_heads.png and
   female_heads.png, 7 columns (facings and frames) x 20 rows (the head value 0..19) of 40 x 65 cells,
   built at 0x43C099 / 0x43C0D4 and kept at gameobj+0x3DFF8 (male) and gameobj+0x3DFF4 (female).  The
   age it shows is the record's +0x348 (the Details screen prints +0x348 / 20 at 0x44919D; 20 units a
   year, 0x42EB14..0x42EB3F), so 1,100 is 55 years here too.

   WHAT THIS DOES.  Wherever the game draws a villager's head, a villager whose shown age (+0x348) is
   1,100 or more is drawn from this patch's grey sheet of the same sex instead -- the same column and
   the same row, so the same head in grey.  Every head follows that rule, head 19 too (the owner,
   2026-10-28): the Golden Child himself never grows old (the age tick puts him back to 100 units,
   0x42EB80..0x42EB8E), but anyone else given head 19 is drawn from row 19 of the grey sheet.  Nothing is written to a villager record: the head value stays what it
   is, so logs, the Family Tree, genetics and Change Appearance all read the same number as before.

   EVERY HEAD THE GAME DRAWS.  Those two sheets are read in exactly 31 places (a byte scan of every
   reference to gameobj+0x3DFF4 / +0x3DFF8): two in the teardown 0x437173 / 0x4371A3, which frees them,
   and the 29 below, each `mov reg, [esi+disp]` (ESI the gameobj) a few instructions before the draw
   that takes that register as its sprite.  They sit in four routines:
     * 0x437340, the Details screen's portrait (from the Details screen's draw 0x449170): 4 reads,
       the villager's record in EDI throughout;
     * 0x4375F0, a dialog's villager figure (the two dialogs whose draw methods 0x4187E0 and 0x42A9D0
       call it at 0x4188A6 / 0x42AA96): 3 reads, the record in EDI;
     * 0x437790, the village (from the frame at 0x4240FE): 13 reads, EDI the loop counter, the record
       gameobj + [gameobj + 0x3DBDC + EDI*4] * 0x3D8;
     * 0x4388E0, the map (from 0x42A5F2; every position is divided by four): 9 reads, EBP the loop's
       pointer into gameobj+0x3DBDC, the record gameobj + [EBP] * 0x3D8.
   No register named here is written between the routine's prologue and its loop's end but by the
   loop step itself (0x4388CE inc edi; 0x4392BA add ebp, 4).  Every one of those draws goes through
   0x409410 (to the engine's scaled cell draw 0x408AF0) or 0x4093C0 (to 0x408740).

   HOW.  Two parts, so the sprite the game's own code and every other patch see is the stock one:
     1. Each of the 29 reads is spliced (jmp + nop): the stub does the read itself, puts the young
        sheet in the register as before, and remembers which sheet and which villager it was for.
     2. The entries of 0x408AF0 and 0x408740 are spliced: when the sprite a draw is given is the sheet
        just remembered, and that villager is drawn grey, the draw gets the grey sheet instead.  The
        remembered pair is used once.
   So the Origins mask hooks (which find a head draw by its sprite being one of the two young sheets,
   scripts/build_vv1_origins_feature.py) still see the young sheet and keep drawing masks.

   THE ART.  Images\vvfp_grey_male_heads.png and Images\vvfp_grey_female_heads.png, beside the game's
   own sheets (the game's sprite loader opens them there by name), each exactly the stock layout:
   280 x 1300 pixels, 7 columns x 20 rows of 40 x 65 cells, the row the head value.  Each is built on
   first use by the game's own allocator 0x44AF03 and sprite constructor 0x40A070 (as the stock sheets
   are, with 7 and 20), after its PNG header is read and found to be exactly 280 x 1300; a missing or
   wrong-sized sheet, or one the game does not load as 40 x 65 cells, is never used and that sex stays
   young.  The stock sheets are never edited.

   INSTALLING.  VvfpStartup(1, shipped), from "VVFP Startup.dll"'s second word of companions
   (native/shared/startup_companions_2.h).  Every spliced site, both engine entries and the register
   set-ups named above must hold the stock bytes; then all 31 splices go in through the shared
   all-or-none writer (native/shared/install_sites.h), or nothing is written.  Off (the row unticked):
   the DLL and the art are not shipped and the game is stock. */
#include <windows.h>
#include <string.h>
#include "../shared/patcher_files.h"
#include "../shared/install_sites.h"
#include "../shared/vv1_grey_hair.h"
#include "../shared/head_look.h"

#define VV1_GAME 1
#define MALE_HEADS 0x3DFF8u             /* gameobj: male_heads.png's sprite */
#define FEMALE_HEADS 0x3DFF4u           /* gameobj: female_heads.png's sprite */
#define DRAW_ORDER 0x3DBDCu             /* gameobj: 256 record indices, the order villagers are drawn in */
#define RECORD_STRIDE 0x3D8u
#define RECORD_COUNT 256u
#define REC_AGE 0x348u                  /* the age the game shows, in age units (20 a year) */
#define REC_SEX 0x350u                  /* 1 a man */
#define GREY_AGE 1100                   /* 55 years */
#define SITE_LEN 6                      /* mov r32, [esi+disp32] */
#define ENGINE_LEN 7                    /* sub esp, 0x10 / mov edx, [esp+0x24] */
#define ALLOC_VA 0x44AF03u              /* the game's operator new */
#define CTOR_VA 0x40A070u               /* sprite(name, cols, rows), thiscall */
#define SPRITE_SIZE 0x34u
#define SPRITE_FRAMEW 0x10u
#define SPRITE_FRAMEH 0x14u
#define SHEET_W 280
#define SHEET_H 1300
#define SHEET_COLS 7
#define SHEET_ROWS 20
#define CELL_W 40
#define CELL_H 65

/* Where each read finds the villager. */
enum { IN_EDI, IN_VILLAGE, IN_MAP };

struct site {
    unsigned int va;
    unsigned char reg;                  /* the destination register: 0 eax, 1 ecx, 2 edx */
    unsigned char male;
    unsigned char where;
};

static const struct site SITES[] = {
    /* 0x437340, the Details portrait */
    { 0x437405u, 1, 1, IN_EDI }, { 0x43748Eu, 1, 0, IN_EDI }, { 0x4374E6u, 0, 1, IN_EDI },
    { 0x437539u, 2, 0, IN_EDI },
    /* 0x4375F0, a dialog's villager figure */
    { 0x4376B0u, 1, 1, IN_EDI }, { 0x437735u, 1, 1, IN_EDI }, { 0x43775Du, 1, 0, IN_EDI },
    /* 0x437790, the village */
    { 0x437B9Du, 2, 1, IN_VILLAGE }, { 0x437D73u, 2, 0, IN_VILLAGE }, { 0x437E9Bu, 2, 1, IN_VILLAGE },
    { 0x437FA1u, 2, 0, IN_VILLAGE }, { 0x43812Fu, 1, 1, IN_VILLAGE }, { 0x438140u, 1, 0, IN_VILLAGE },
    { 0x438265u, 1, 1, IN_VILLAGE }, { 0x4382D7u, 1, 0, IN_VILLAGE }, { 0x43836Cu, 1, 1, IN_VILLAGE },
    { 0x4383C2u, 1, 0, IN_VILLAGE }, { 0x4385D9u, 1, 0, IN_VILLAGE }, { 0x438766u, 1, 1, IN_VILLAGE },
    { 0x4387BAu, 1, 0, IN_VILLAGE },
    /* 0x4388E0, the map */
    { 0x438BF3u, 1, 0, IN_MAP }, { 0x438D23u, 1, 1, IN_MAP }, { 0x438DDBu, 0, 0, IN_MAP },
    { 0x438E73u, 1, 1, IN_MAP }, { 0x438EE0u, 1, 0, IN_MAP }, { 0x439052u, 0, 1, IN_MAP },
    { 0x4390D7u, 1, 0, IN_MAP }, { 0x4391CFu, 0, 1, IN_MAP }, { 0x439249u, 0, 0, IN_MAP },
};
#define SITE_COUNT (sizeof SITES / sizeof SITES[0])

/* The register set-ups the reads rely on: each routine's prologue and its loop step, stock. */
struct anchor {
    unsigned int va;
    unsigned char length;
    unsigned char bytes[16];
};
static const struct anchor ANCHORS[] = {
    { 0x437340u, 9, { 0x56, 0x57, 0x68, 0xE8, 0x03, 0x00, 0x00, 0x8B, 0xF1 } },          /* esi = gameobj */
    { 0x43737Du, 3, { 0x8D, 0x3C, 0x30 } },                                            /* lea edi, [eax+esi] */
    { 0x4375FFu, 8, { 0x55, 0x56, 0x8B, 0xF1, 0x57, 0x8D, 0x3C, 0x30 } },              /* esi; edi = record */
    { 0x437790u, 8, { 0x53, 0x55, 0x56, 0x57, 0x8B, 0xF1, 0x33, 0xFF } },              /* esi; edi = 0 */
    { 0x4388CEu, 9, { 0x47, 0x81, 0xFF, 0x00, 0x01, 0x00, 0x00, 0x0F, 0x8C } },        /* inc edi; < 256 */
    { 0x4388E0u, 13, { 0x51, 0x53, 0x55, 0x56, 0x8B, 0xF1, 0x57, 0x8D, 0xAE, 0xDC, 0xDB, 0x03, 0x00 } },
    { 0x4392BAu, 3, { 0x83, 0xC5, 0x04 } },                                            /* add ebp, 4 */
};
#define ANCHOR_COUNT (sizeof ANCHORS / sizeof ANCHORS[0])

static const unsigned char ENGINE_STOCK[ENGINE_LEN] = { 0x83, 0xEC, 0x10, 0x8B, 0x54, 0x24, 0x24 };
#define ENGINE_CELL 0x408AF0u           /* via 0x409410 */
#define ENGINE_CELL_RESUME 0x408AF7u
#define ENGINE_ROWCOL 0x408740u         /* via 0x4093C0 */
#define ENGINE_ROWCOL_RESUME 0x408747u

/* The game keeps the name pointer it is given, so each lives as long as the module (never unloaded). */
static const char *const SHEET_NAME[2] = { "vvfp_grey_female_heads.png", "vvfp_grey_male_heads.png" };
static const char *const SHEET_RELATIVE[2] = {
    "Images\\vvfp_grey_female_heads.png", "Images\\vvfp_grey_male_heads.png",
};

static int installed;
static unsigned char site_expect[SITE_COUNT][SITE_LEN];
static unsigned int remembered_sheet;              /* the young sheet a read just handed out, 0 none */
static const unsigned char *remembered_record;
static int remembered_male;
static int sheet_state[2];                         /* by sex: 0 not tried, 1 built, -1 not usable */
static unsigned char *sheet[2];

typedef void *(__cdecl *alloc_fn)(unsigned int);
typedef void *(__fastcall *ctor_fn)(void *self, void *unused, const char *name, int cols, int rows);

/* ---- the rule --------------------------------------------------------------------------------- */

/* Change Appearance's head look (native/shared/head_look.h): "VVFP Head Look.dll" keeps each villager's
   Auto, Young or Old in the save's own file.  Found once, at the first head drawn (every companion is
   loaded by then: VVFP Startup.dll starts them all before the title screen); without it every look is
   Auto. */
static int look_state;                             /* 0 not looked for, 1 found, -1 not in the game */
static vvfp_head_look_get_fn look_get;

static int head_look(const unsigned char *record) {
    if (look_state == 0) {
        HMODULE dll = GetModuleHandleA(VVFP_HEAD_LOOK_DLL);
        look_get = dll != NULL ? (vvfp_head_look_get_fn)GetProcAddress(dll, VVFP_HEAD_LOOK_GET) : NULL;
        look_state = look_get != NULL ? 1 : -1;
    }
    return look_state == 1 ? look_get(VV1_GAME, record) : VVFP_HEAD_LOOK_AUTO;
}

/* Grey from a shown age of 1,100 -- or always (Old), or never (Young), when Change Appearance says so. */
static int drawn_grey(const unsigned char *record) {
    return record != NULL && vvfp_head_look_old(head_look(record), *(const int *)(record + REC_AGE));
}

/* ---- the art ------------------------------------------------------------------------------------ */

/* The PNG's own header says exactly 280 x 1300. */
static int sheet_file_fits(int male) {
    static const unsigned char SIGNATURE[16] = {
        0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 'I', 'H', 'D', 'R',
    };
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    unsigned char header[24];
    DWORD got = 0;
    HANDLE file;
    int ok;
    if (!vvfp_game_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, SHEET_RELATIVE[male])) {
        return 0;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(file, header, sizeof header, &got, NULL) && got == sizeof header
        && memcmp(header, SIGNATURE, sizeof SIGNATURE) == 0
        && header[16] == 0 && header[17] == 0 && header[18] == (SHEET_W >> 8) && header[19] == (SHEET_W & 0xFF)
        && header[20] == 0 && header[21] == 0 && header[22] == (SHEET_H >> 8) && header[23] == (SHEET_H & 0xFF);
    CloseHandle(file);
    return ok;
}

/* The grey sheet of a sex, built on first use; NULL when it cannot be used. */
static unsigned char *grey_sheet(int male) {
    if (sheet_state[male] == 0) {
        unsigned char *made;
        sheet_state[male] = -1;
        if (!sheet_file_fits(male)) {
            return NULL;
        }
        made = (unsigned char *)((alloc_fn)(UINT_PTR)ALLOC_VA)(SPRITE_SIZE);
        if (made == NULL) {
            return NULL;
        }
        ((ctor_fn)(UINT_PTR)CTOR_VA)(made, NULL, SHEET_NAME[male], SHEET_COLS, SHEET_ROWS);
        if (*(const int *)(made + SPRITE_FRAMEW) != CELL_W || *(const int *)(made + SPRITE_FRAMEH) != CELL_H) {
            return NULL;                /* not loaded as the stock cells: never drawn (the object is kept) */
        }
        sheet[male] = made;
        sheet_state[male] = 1;
    }
    return sheet_state[male] == 1 ? sheet[male] : NULL;
}

/* ---- part 1: the 29 reads ----------------------------------------------------------------------- */

/* The villager the read at `s` is for; NULL when the registers do not name a record. */
static const unsigned char *villager_at(const struct site *s, const unsigned int *frame, const unsigned char *game) {
    unsigned int offset, index;
    switch (s->where) {
    case IN_EDI:
        offset = frame[0] - (unsigned int)(UINT_PTR)game;
        if (frame[0] < (unsigned int)(UINT_PTR)game || offset % RECORD_STRIDE != 0
            || offset / RECORD_STRIDE >= RECORD_COUNT) {
            return NULL;
        }
        return game + offset;
    case IN_VILLAGE:
        if (frame[0] >= RECORD_COUNT) {
            return NULL;
        }
        index = *(const unsigned int *)(game + DRAW_ORDER + 4u * frame[0]);
        break;
    default:
        index = *(const unsigned int *)(UINT_PTR)frame[2];
        break;
    }
    return index < RECORD_COUNT ? game + index * RECORD_STRIDE : NULL;
}

/* `frame` is the common stub's: [0..7] pushad (edi, esi, ebp, esp, ebx, edx, ecx, eax), [8] the flags,
   [9] the site's number.  Does the read, remembers it, and returns where the game goes on. */
static unsigned int __cdecl site_read(unsigned int *frame) {
    const struct site *s = &SITES[frame[9]];
    const unsigned char *game = (const unsigned char *)(UINT_PTR)frame[1];
    unsigned int young = *(const unsigned int *)(game + (s->male ? MALE_HEADS : FEMALE_HEADS));
    frame[7 - s->reg] = young;
    remembered_record = villager_at(s, frame, game);
    remembered_male = s->male;
    remembered_sheet = remembered_record != NULL ? young : 0;
    return s->va + SITE_LEN;
}

static __declspec(naked) void site_common(void) {
    __asm {
        pushfd
        pushad
        push esp
        call site_read
        add esp, 4
        mov dword ptr [esp + 0x24], eax     ; the site's number becomes where to go on
        popad
        popfd
        ret
    }
}

#define SITE_STUB(n) \
    static __declspec(naked) void site_stub_##n(void) { __asm push n __asm jmp site_common }
SITE_STUB(0) SITE_STUB(1) SITE_STUB(2) SITE_STUB(3) SITE_STUB(4) SITE_STUB(5) SITE_STUB(6) SITE_STUB(7)
SITE_STUB(8) SITE_STUB(9) SITE_STUB(10) SITE_STUB(11) SITE_STUB(12) SITE_STUB(13) SITE_STUB(14)
SITE_STUB(15) SITE_STUB(16) SITE_STUB(17) SITE_STUB(18) SITE_STUB(19) SITE_STUB(20) SITE_STUB(21)
SITE_STUB(22) SITE_STUB(23) SITE_STUB(24) SITE_STUB(25) SITE_STUB(26) SITE_STUB(27) SITE_STUB(28)

static void (*const SITE_STUBS[])(void) = {
    site_stub_0, site_stub_1, site_stub_2, site_stub_3, site_stub_4, site_stub_5, site_stub_6,
    site_stub_7, site_stub_8, site_stub_9, site_stub_10, site_stub_11, site_stub_12, site_stub_13,
    site_stub_14, site_stub_15, site_stub_16, site_stub_17, site_stub_18, site_stub_19, site_stub_20,
    site_stub_21, site_stub_22, site_stub_23, site_stub_24, site_stub_25, site_stub_26, site_stub_27,
    site_stub_28,
};

/* ---- part 2: the two engine draws ----------------------------------------------------------------- */

/* `sprite` is the draw's first argument. */
static void __cdecl engine_draw(unsigned int *sprite) {
    if (remembered_sheet != 0 && *sprite == remembered_sheet) {
        const unsigned char *record = remembered_record;
        int male = remembered_male;
        remembered_sheet = 0;
        if (drawn_grey(record)) {
            unsigned char *grey = grey_sheet(male);
            if (grey != NULL) {
                *sprite = (unsigned int)(UINT_PTR)grey;
            }
        }
    }
}

static __declspec(naked) void engine_cell_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 0x24]               ; the first argument, past pushad and the return
        push eax
        call engine_draw
        add esp, 4
        popad
        sub esp, 0x10                       ; the displaced entry
        mov edx, dword ptr [esp + 0x24]
        push ENGINE_CELL_RESUME
        ret
    }
}

static __declspec(naked) void engine_rowcol_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 0x24]
        push eax
        call engine_draw
        add esp, 4
        popad
        sub esp, 0x10
        mov edx, dword ptr [esp + 0x24]
        push ENGINE_ROWCOL_RESUME
        ret
    }
}

/* ---- installing --------------------------------------------------------------------------------- */

static void install_vv1(void) {
    vvfp_site_write w[SITE_COUNT + 2];
    size_t i;
    for (i = 0; i < ANCHOR_COUNT; ++i) {
        if (!vvfp_site_holds(ANCHORS[i].va, ANCHORS[i].bytes, ANCHORS[i].length)) {
            return;
        }
    }
    for (i = 0; i < SITE_COUNT; ++i) {
        unsigned int disp = SITES[i].male ? MALE_HEADS : FEMALE_HEADS;
        site_expect[i][0] = 0x8B;
        site_expect[i][1] = (unsigned char)(0x86 | (SITES[i].reg << 3));    /* mod 10, rm esi */
        memcpy(&site_expect[i][2], &disp, 4);
        vvfp_site_branch(&w[i], SITES[i].va, SITE_LEN, site_expect[i], 0xE9, (const void *)SITE_STUBS[i]);
    }
    vvfp_site_branch(&w[SITE_COUNT], ENGINE_CELL, ENGINE_LEN, ENGINE_STOCK, 0xE9, (const void *)engine_cell_stub);
    vvfp_site_branch(&w[SITE_COUNT + 1], ENGINE_ROWCOL, ENGINE_LEN, ENGINE_STOCK, 0xE9,
                     (const void *)engine_rowcol_stub);
    if (vvfp_install_sites(w, (int)(SITE_COUNT + 2))) {
        installed = 1;
    }
}

/* Called once at game start by "VVFP Startup.dll" (its second word), outside DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (installed || game != VV1_GAME) {
        return;
    }
    install_vv1();
}

/* Whether the splices are in (tests). */
int __stdcall VvfpGreyHairInstalled(void) {
    return installed;
}

int __stdcall Vv1GreyHairUsable(int male);

/* Whether the village draws this villager grey (native/shared/vv1_grey_hair.h): the splices are in,
   the rule says so, and that sex's grey sheet is there and the right size (or already built).  Asked
   from a dialog, so it never builds a sprite itself. */
int __stdcall Vv1GreyHairWanted(const void *record) {
    const unsigned char *r = (const unsigned char *)record;
    int male;
    if (!installed || r == NULL) {
        return 0;
    }
    male = *(const int *)(r + REC_SEX) == 1;          /* 1 a man: the sex the game picks his sheet by */
    if (!drawn_grey(r)) {
        return 0;
    }
    return Vv1GreyHairUsable(male);
}

/* Whether the grey heads of a sex can be drawn at all (native/shared/vv1_grey_hair.h).  Asked from a
   dialog, so it never builds a sprite itself. */
int __stdcall Vv1GreyHairUsable(int male) {
    male = male != 0;
    if (!installed || sheet_state[male] < 0) {
        return 0;
    }
    return sheet_state[male] == 1 || sheet_file_fits(male);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
