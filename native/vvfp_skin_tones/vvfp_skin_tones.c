/* VVFP Skin Tones -- per-villager skin tones for A New Home (a DRAFT; the owner, 2026-11-06: "per villager
   with inheritance", "inherited and chosen", "Try it in one game first"; after the automatic recolours of
   draft PR #707 were rejected: "meh. I'll do it myself.").  NOTHING IS RECOLOURED HERE: the owner draws each
   tone's sheets by hand, and this DLL only chooses, for each villager, which sheets the game draws.

   THE ART (docs/skin-tones-art-guide.md).  Tone 0 is the game's own art.  Tone n (1..15) is the folder
   Images\vvfp_skin\<n>\ in the game folder, holding sheets under the game's own file names and sizes:
       male_heads.png, female_heads.png                     280 x 1300 (7 x 20 cells of 40 x 65)
       male_bodies00/10/01/11.png, female_bodies00/10/01/11.png    640 x 650 each (a 2 x 2 grid, 32 x 20 cells)
       male_actions00/01.png, female_actions00/01.png       360 x 650 each (a 1 x 2 grid, 9 x 20 cells)
       vvfp_grey_male_heads.png, vvfp_grey_female_heads.png 280 x 1300 (Grey Hair at 55's grey heads)
   The number of tones, N, is the number of folders 1, 2, 3, ... present when the game starts (the first
   missing number ends it); with none at all N is the design's eight, so tones are given -- and kept --
   before the art exists.  Each sheet is checked by its PNG header (the exact stock size) and built once,
   on first use, by the game's own allocator 0x44AF03 and sprite constructors (0x40A070 one sheet, 0x40A0F0
   a grid of sheets, as the game builds its own at 0x43C08E..0x43C1DD), then kept for the session.  A sheet
   that is missing, of another size, or that the game does not load as 40 x 65 cells is never used: that
   villager is drawn from the game's own sheet (or, for a grey head, Grey Hair's untoned grey sheet).

   THE DRAWS.  A New Home reads a villager's sheets from six gameobj slots (+0x3DFF4/8 the heads, +0x3DFE4/8
   the bodies, +0x3DFEC/F0 the actions) in four routines, each read a 6-byte `mov r32, [esi+disp32]` a few
   instructions before the engine draw that takes the register as its sprite (design: draft PR #707,
   docs/reports/skin-tone/design.md; the same routines and register set-ups Grey Hair at 55 relies on):
     0x437340 the Details portrait and 0x4375F0 a dialog's villager figure (the record in EDI),
     0x437790 the village (EDI the loop counter: the record gameobj + [gameobj+0x3DBDC+EDI*4] * 0x3D8),
     0x4388E0 the map (EBP the loop's pointer into gameobj+0x3DBDC).
     * THE 35 BODY AND ACTION READS (17 bodies, 18 actions; SITES below) are spliced here: the stub does the
       read itself and puts that villager's tone's sheet in the register (the game's own when tone 0 or no
       sheet), every other register and the flags as they were.  Nothing else compares a body or action
       sprite (the Origins mask hooks look only at the two head sheets).
     * THE 29 HEAD READS and the engine entries 0x408AF0 / 0x408740 are Grey Hair at 55's
       (native/vv1_grey_hair): the masks find a head draw by its YOUNG sheet, so a head's sheet may only be
       swapped at the engine entry, after them.  Grey Hair asks this DLL there (Vv1SkinToneSheetFor for the
       young sheet, Vv1SkinToneGreySheetFor for its grey one), so this row needs Grey Hair at 55.
   Show Parents (native/vv1_parentage), which draws a child's body and head again over the parents, asks the
   same exports.

   THE TONES (skin_tone_store.inc): kept per villager in "Skin Tones - Save <S>.dat", following the villager;
   founders and arrivals random, babies the midpoint of their parents' tones at conception (a half step
   toward the mother's), Change Appearance's choice.  Births reach Vv1SkinToneBorn through the Origins
   companion's Vv1Born (the Origins row's exact birth hook in the pregnancy tick: live play, the load-time
   catch-up, Time Warp, twins and triplets, a golden-child mother's extra child, and the Golden Child puzzle
   0x4242F8, which the Origins companion forwards the same way); conceptions reach Vv1SkinToneConceived
   through the parentage log's conception hook (native/parentage_export).

   INSTALLING.  VvfpStartup(1, shipped) from "VVFP Startup.dll" (its second word of companions), on the
   game's thread before the title screen: every spliced read and every register set-up it relies on must
   hold its stock bytes; then all 35 go in through the shared all-or-none writer (native/shared/
   install_sites.h), or nothing is written and every villager is drawn from the game's own art (Change
   Appearance then does not offer the tone: Vv1SkinToneInstalled). */
#include <windows.h>
#include <string.h>
#include "../shared/sidecar_io.h"
#include "../shared/save_folder.h"
#include "../shared/per_save_data.h"
#include "../shared/mask_follow.h"
#include "../shared/foreign_sidecar.h"
#include "../shared/game_save_slot.h"
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/skin_tones.h"

#define VV1_GAME 1
#define ST_MAX 256
#define ST_TONE_LIMIT VVFP_SKIN_TONE_MAX

#define RECORDS_GLOBAL 0x48B614u        /* -> record 0 (the gameobj) */
#define RECORD_STRIDE 0x3D8u
#define RECORD_COUNT 256u
#define REC_PRESENT 0x28u               /* 1: the record is held */
#define REC_SEX 0x350u
#define REC_DUE 0x358u                  /* non-zero while carrying (cleared after the delivery's last child) */
#define REC_FAMILY 0x36Cu
#define REC_NAME 0x370u
#define REC_NAME_BYTES 0x1Cu
#define DRAW_ORDER 0x3DBDCu             /* gameobj: 256 record indices, the order villagers are drawn in */
#define SITE_LEN 6
#define ALLOC_VA 0x44AF03u              /* the game's operator new */
#define CTOR_VA 0x40A070u               /* sprite(name, cols, rows), thiscall */
#define GRID_CTOR_VA 0x40A0F0u          /* sprite(prefix, suffix, across, down, cols, rows), thiscall */
#define SPRITE_SIZE 0x34u
#define SPRITE_FRAMEW 0x10u
#define SPRITE_FRAMEH 0x14u
#define CELL_W 40
#define CELL_H 65

/* ---- the village (skin_tone_store.inc's game) -------------------------------------------------------- */

static int g_started;
static int g_installed;
static int g_tone_count = VVFP_SKIN_TONE_DEFAULT_COUNT;
static unsigned int g_rng;

static int st_game(void) {
    return VV1_GAME;
}

static int st_slots(void) {
    return (int)RECORD_COUNT;
}

static const unsigned char *st_record(int i) {
    unsigned int base = *(const unsigned int *)(UINT_PTR)RECORDS_GLOBAL;
    if (base == 0 || i < 0 || i >= (int)RECORD_COUNT) {
        return NULL;
    }
    return (const unsigned char *)(UINT_PTR)(base + (unsigned int)i * RECORD_STRIDE);
}

static int st_present(const unsigned char *r) {
    return r[REC_PRESENT] == 1;
}

static int st_pregnant(const unsigned char *r) {
    return *(const int *)(r + REC_DUE) != 0;
}

static unsigned int st_mix(unsigned int h, const unsigned char *at, unsigned int n, int stop_at_nul) {
    unsigned int k;
    for (k = 0; k < n && !(stop_at_nul && at[k] == 0); ++k) {
        h = (h ^ at[k]) * 16777619u;
    }
    return h;
}

/* What a rename leaves of a villager's identity: the sex and the family.  Never 0. */
static unsigned int st_stable(const unsigned char *r) {
    unsigned int h = st_mix(2166136261u, r + REC_SEX, 4, 0);
    h = st_mix(h, r + REC_FAMILY, 4, 0);
    return h ? h : 1u;
}

/* A held record's identity: the name, the sex and the family.  Never 0. */
static unsigned int st_identity(const unsigned char *r) {
    unsigned int h = st_mix(2166136261u, r + REC_NAME, REC_NAME_BYTES, 1);
    h = (h ^ 0xFFu) * 16777619u;
    h = (h ^ st_stable(r)) * 16777619u;
    return h ? h : 1u;
}

static int st_slot_now(void) {
    return vv_game_save_slot(VV1_GAME);
}

static int st_tone_count(void) {
    return g_tone_count;
}

/* 0..n-1, from this DLL's own xorshift (never the game's rand()). */
static int st_random(int n) {
    unsigned int x = g_rng ? g_rng : 0x2545F491u;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_rng = x;
    return n > 0 ? (int)((x >> 8) % (unsigned int)n) : 0;
}

#include "skin_tone_store.inc"

int __stdcall VvfpVillagersRenamed(int game, int slot, int count, const void *const *records,
                                   const char *const *old_names) {
    if (game != VV1_GAME || !g_started) {
        return 0;
    }
    return st_renamed(slot, count, records, old_names, RECORD_STRIDE, REC_NAME, REC_NAME_BYTES);
}

/* ---- the sheets ----------------------------------------------------------------------------------- */

enum { K_F_HEADS, K_M_HEADS, K_F_BODIES, K_M_BODIES, K_F_ACTIONS, K_M_ACTIONS, K_F_GREY, K_M_GREY, K_COUNT };

/* Each kind: its gameobj slot (0 for Grey Hair's grey heads, which the game does not hold), its file name
   (or the grid's prefix), the grid (across x down sheets, 1 x 1 for one sheet), the cells and each file's
   exact size. */
static const struct {
    unsigned int slot;
    const char *name;
    int across, down, cols, rows, file_w, file_h;
} KIND[K_COUNT] = {
    { 0x3DFF4u, "female_heads.png", 1, 1, 7, 20, 280, 1300 },
    { 0x3DFF8u, "male_heads.png", 1, 1, 7, 20, 280, 1300 },
    { 0x3DFE4u, "female_bodies", 2, 2, 32, 20, 640, 650 },
    { 0x3DFE8u, "male_bodies", 2, 2, 32, 20, 640, 650 },
    { 0x3DFECu, "female_actions", 1, 2, 9, 20, 360, 650 },
    { 0x3DFF0u, "male_actions", 1, 2, 9, 20, 360, 650 },
    { 0, "vvfp_grey_female_heads.png", 1, 1, 7, 20, 280, 1300 },
    { 0, "vvfp_grey_male_heads.png", 1, 1, 7, 20, 280, 1300 },
};

/* The game keeps the name pointer it is given, so each lives as long as the module (never unloaded). */
static char g_name[VVFP_SKIN_TONE_MAX + 1][K_COUNT][48];
static int g_sheet_state[VVFP_SKIN_TONE_MAX + 1][K_COUNT];  /* 0 not tried, 1 built, -1 not usable */
static unsigned char *g_sheet[VVFP_SKIN_TONE_MAX + 1][K_COUNT];

typedef void *(__cdecl *alloc_fn)(unsigned int);
typedef void *(__fastcall *ctor_fn)(void *self, void *unused, const char *name, int cols, int rows);
typedef void *(__fastcall *grid_ctor_fn)(void *self, void *unused, const char *prefix, const char *suffix,
                                         int across, int down, int cols, int rows);

/* "vvfp_skin\<tone>\<leaf>" into out (cap characters). */
static void tone_leaf(char *out, int cap, int tone, const char *leaf) {
    char number[8];
    wsprintfA(number, "%d", tone);
    lstrcpynA(out, "vvfp_skin\\", cap);
    if (lstrlenA(out) + lstrlenA(number) + 1 + lstrlenA(leaf) < cap) {
        lstrcatA(out, number);
        lstrcatA(out, "\\");
        lstrcatA(out, leaf);
    }
}

/* The PNG at Images\<leaf> is there and its header says exactly w x h. */
static int png_fits(const char *leaf, int w, int h) {
    static const unsigned char SIGNATURE[16] = {
        0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 'I', 'H', 'D', 'R',
    };
    char relative[80];
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    unsigned char header[24];
    DWORD got = 0;
    HANDLE file;
    int ok;
    lstrcpynA(relative, "Images\\", sizeof relative);
    if (lstrlenA(relative) + lstrlenA(leaf) >= (int)sizeof relative) {
        return 0;
    }
    lstrcatA(relative, leaf);
    if (!vvfp_game_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, relative)) {
        return 0;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(file, header, sizeof header, &got, NULL) && got == sizeof header
        && memcmp(header, SIGNATURE, sizeof SIGNATURE) == 0
        && header[16] == 0 && header[17] == 0 && header[18] == (unsigned char)(w >> 8)
        && header[19] == (unsigned char)(w & 0xFF)
        && header[20] == 0 && header[21] == 0 && header[22] == (unsigned char)(h >> 8)
        && header[23] == (unsigned char)(h & 0xFF);
    CloseHandle(file);
    return ok;
}

/* Every file of the kind is there at its stock size. */
static int kind_files_fit(int tone, int kind) {
    char leaf[64];
    int x, y;
    if (KIND[kind].across == 1 && KIND[kind].down == 1) {
        tone_leaf(leaf, sizeof leaf, tone, KIND[kind].name);
        return png_fits(leaf, KIND[kind].file_w, KIND[kind].file_h);
    }
    for (y = 0; y < KIND[kind].down; ++y) {
        for (x = 0; x < KIND[kind].across; ++x) {
            char file[40];
            wsprintfA(file, "%s%d%d.png", KIND[kind].name, x, y);
            tone_leaf(leaf, sizeof leaf, tone, file);
            if (!png_fits(leaf, KIND[kind].file_w, KIND[kind].file_h)) {
                return 0;
            }
        }
    }
    return 1;
}

/* The tone's sheet of that kind, built on first use; NULL when it cannot be used. */
static unsigned char *tone_sheet(int tone, int kind) {
    if (tone < 1 || tone > VVFP_SKIN_TONE_MAX || kind < 0 || kind >= K_COUNT) {
        return NULL;
    }
    if (g_sheet_state[tone][kind] == 0) {
        unsigned char *made;
        char *name = g_name[tone][kind];
        g_sheet_state[tone][kind] = -1;
        if (!kind_files_fit(tone, kind)) {
            return NULL;
        }
        made = (unsigned char *)((alloc_fn)(UINT_PTR)ALLOC_VA)(SPRITE_SIZE);
        if (made == NULL) {
            return NULL;
        }
        tone_leaf(name, sizeof g_name[tone][kind], tone, KIND[kind].name);
        if (KIND[kind].across == 1 && KIND[kind].down == 1) {
            ((ctor_fn)(UINT_PTR)CTOR_VA)(made, NULL, name, KIND[kind].cols, KIND[kind].rows);
        } else {
            ((grid_ctor_fn)(UINT_PTR)GRID_CTOR_VA)(made, NULL, name, ".png", KIND[kind].across, KIND[kind].down,
                                                    KIND[kind].cols, KIND[kind].rows);
        }
        if (*(const int *)(made + SPRITE_FRAMEW) != CELL_W || *(const int *)(made + SPRITE_FRAMEH) != CELL_H) {
            return NULL;                /* not loaded as the stock cells: never drawn (the object is kept) */
        }
        g_sheet[tone][kind] = made;
        g_sheet_state[tone][kind] = 1;
    }
    return g_sheet_state[tone][kind] == 1 ? g_sheet[tone][kind] : NULL;
}

/* `stock` as the villager in `record` is drawn: its tone's sheet of that kind, or `stock`. */
static void *toned(const unsigned char *record, int kind, void *stock) {
    int tone;
    unsigned char *sheet;
    if (!g_installed || record == NULL || stock == NULL) {
        return stock;
    }
    tone = st_get(record);
    if (tone <= 0) {
        return stock;
    }
    sheet = tone_sheet(tone, kind);
    return sheet != NULL ? sheet : stock;
}

/* The record `record` is in `gameobj`'s 256 records. */
static int is_record_of(const unsigned char *game, const unsigned char *record) {
    unsigned int offset;
    if (game == NULL || record == NULL || record < game) {
        return 0;
    }
    offset = (unsigned int)(record - game);
    return offset % RECORD_STRIDE == 0 && offset / RECORD_STRIDE < RECORD_COUNT;
}

/* ---- the 35 body and action reads ---------------------------------------------------------------- */

enum { IN_EDI, IN_VILLAGE, IN_MAP };

struct site {
    unsigned int va;
    unsigned char reg;                  /* the destination register: 0 eax, 1 ecx, 2 edx */
    unsigned char kind;
    unsigned char where;
};

static const struct site SITES[] = {
    /* 0x437340, the Details portrait */
    { 0x4373B8u, 2, K_M_BODIES, IN_EDI }, { 0x437441u, 1, K_F_BODIES, IN_EDI },
    { 0x4374C0u, 0, K_M_BODIES, IN_EDI }, { 0x437513u, 2, K_F_BODIES, IN_EDI },
    /* 0x4375F0, a dialog's villager figure */
    { 0x437679u, 1, K_M_BODIES, IN_EDI }, { 0x4376D5u, 1, K_F_BODIES, IN_EDI },
    { 0x437723u, 1, K_M_BODIES, IN_EDI }, { 0x437744u, 1, K_F_BODIES, IN_EDI },
    /* 0x437790, the village */
    { 0x437A8Eu, 1, K_M_ACTIONS, IN_VILLAGE }, { 0x437AEDu, 2, K_M_BODIES, IN_VILLAGE },
    { 0x437B2Du, 2, K_M_ACTIONS, IN_VILLAGE }, { 0x437C62u, 2, K_M_ACTIONS, IN_VILLAGE },
    { 0x437D08u, 2, K_F_ACTIONS, IN_VILLAGE }, { 0x437E38u, 2, K_M_BODIES, IN_VILLAGE },
    { 0x437F3Eu, 2, K_F_BODIES, IN_VILLAGE }, { 0x438210u, 1, K_M_ACTIONS, IN_VILLAGE },
    { 0x438286u, 1, K_F_ACTIONS, IN_VILLAGE }, { 0x438327u, 1, K_M_ACTIONS, IN_VILLAGE },
    { 0x43837Du, 1, K_F_ACTIONS, IN_VILLAGE }, { 0x43853Fu, 1, K_M_ACTIONS, IN_VILLAGE },
    { 0x438593u, 1, K_F_ACTIONS, IN_VILLAGE }, { 0x438723u, 1, K_M_BODIES, IN_VILLAGE },
    { 0x438777u, 1, K_F_BODIES, IN_VILLAGE },
    /* 0x4388E0, the map */
    { 0x438A07u, 0, K_M_ACTIONS, IN_MAP }, { 0x438AAEu, 1, K_M_ACTIONS, IN_MAP },
    { 0x438B05u, 1, K_M_BODIES, IN_MAP }, { 0x438B7Bu, 1, K_F_BODIES, IN_MAP },
    { 0x438CDCu, 0, K_M_ACTIONS, IN_MAP }, { 0x438D6Au, 1, K_F_ACTIONS, IN_MAP },
    { 0x438E36u, 0, K_M_ACTIONS, IN_MAP }, { 0x438EA3u, 0, K_F_ACTIONS, IN_MAP },
    { 0x439002u, 0, K_M_ACTIONS, IN_MAP }, { 0x439087u, 1, K_F_ACTIONS, IN_MAP },
    { 0x439170u, 1, K_M_BODIES, IN_MAP }, { 0x4391EAu, 1, K_F_BODIES, IN_MAP },
};
#define SITE_COUNT (sizeof SITES / sizeof SITES[0])

/* The register set-ups the reads rely on: each routine's prologue and its loop step, stock (the same as
   Grey Hair at 55's). */
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

static unsigned char site_expect[SITE_COUNT][SITE_LEN];

/* The villager the read at `s` is for; NULL when the registers do not name a record. */
static const unsigned char *villager_at(const struct site *s, const unsigned int *frame, const unsigned char *game) {
    unsigned int index;
    switch (s->where) {
    case IN_EDI:
        return is_record_of(game, (const unsigned char *)(UINT_PTR)frame[0])
            ? (const unsigned char *)(UINT_PTR)frame[0] : NULL;
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

/* `frame`: [0..7] pushad (edi, esi, ebp, esp, ebx, edx, ecx, eax), [8] the flags, [9] the site's number.
   Does the read with the villager's tone and returns where the game goes on. */
static unsigned int __cdecl site_read(unsigned int *frame) {
    const struct site *s = &SITES[frame[9]];
    const unsigned char *game = (const unsigned char *)(UINT_PTR)frame[1];
    void *stock = *(void *const *)(game + KIND[s->kind].slot);
    const unsigned char *record = villager_at(s, frame, game);
    frame[7 - s->reg] = (unsigned int)(UINT_PTR)(record != NULL ? toned(record, s->kind, stock) : stock);
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
SITE_STUB(29) SITE_STUB(30) SITE_STUB(31) SITE_STUB(32) SITE_STUB(33) SITE_STUB(34)

static void (*const SITE_STUBS[])(void) = {
    site_stub_0, site_stub_1, site_stub_2, site_stub_3, site_stub_4, site_stub_5, site_stub_6,
    site_stub_7, site_stub_8, site_stub_9, site_stub_10, site_stub_11, site_stub_12, site_stub_13,
    site_stub_14, site_stub_15, site_stub_16, site_stub_17, site_stub_18, site_stub_19, site_stub_20,
    site_stub_21, site_stub_22, site_stub_23, site_stub_24, site_stub_25, site_stub_26, site_stub_27,
    site_stub_28, site_stub_29, site_stub_30, site_stub_31, site_stub_32, site_stub_33, site_stub_34,
};
typedef char st_one_stub_per_site[sizeof SITE_STUBS / sizeof SITE_STUBS[0] == SITE_COUNT ? 1 : -1];

/* ---- installing ---------------------------------------------------------------------------------- */

/* N: the tone folders 1, 2, 3, ... in Images\vvfp_skin (the first missing number ends it); the design's
   eight when there is none. */
static int count_tones(void) {
    int n;
    for (n = 1; n <= VVFP_SKIN_TONE_MAX; ++n) {
        char relative[40];
        wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
        DWORD attributes;
        wsprintfA(relative, "Images\\vvfp_skin\\%d", n);
        if (!vvfp_game_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, relative)) {
            break;
        }
        attributes = GetFileAttributesW(path);
        if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0) {
            break;
        }
    }
    return n > 1 ? n - 1 : VVFP_SKIN_TONE_DEFAULT_COUNT;
}

static void install_vv1(void) {
    vvfp_site_write w[SITE_COUNT];
    size_t i;
    for (i = 0; i < ANCHOR_COUNT; ++i) {
        if (!vvfp_site_holds(ANCHORS[i].va, ANCHORS[i].bytes, ANCHORS[i].length)) {
            return;
        }
    }
    for (i = 0; i < SITE_COUNT; ++i) {
        unsigned int disp = KIND[SITES[i].kind].slot;
        site_expect[i][0] = 0x8B;
        site_expect[i][1] = (unsigned char)(0x86 | (SITES[i].reg << 3));    /* mod 10, rm esi */
        memcpy(&site_expect[i][2], &disp, 4);
        vvfp_site_branch(&w[i], SITES[i].va, SITE_LEN, site_expect[i], 0xE9, (const void *)SITE_STUBS[i]);
    }
    if (vvfp_install_sites(w, (int)SITE_COUNT)) {
        g_installed = 1;
    }
}

/* ---- the Change Appearance preview (GDI+, never started from DllMain) ---------------------------- */

typedef INT GpStatus;
typedef void GpImage;
typedef void GpBitmap;
typedef void GpGraphics;
struct GdiplusStartupInputC {
    UINT32 GdiplusVersion;
    void *DebugEventCallback;
    BOOL SuppressBackgroundThread;
    BOOL SuppressExternalCodecs;
};
__declspec(dllimport) GpStatus __stdcall GdiplusStartup(ULONG_PTR *token, const struct GdiplusStartupInputC *input,
                                                        void *output);
__declspec(dllimport) GpStatus __stdcall GdipCreateBitmapFromFile(const WCHAR *filename, GpBitmap **bitmap);
__declspec(dllimport) GpStatus __stdcall GdipCreateFromHDC(HDC hdc, GpGraphics **graphics);
__declspec(dllimport) GpStatus __stdcall GdipSetInterpolationMode(GpGraphics *graphics, INT mode);
__declspec(dllimport) GpStatus __stdcall GdipDrawImageRectRectI(GpGraphics *graphics, GpImage *image,
                                                                INT dstx, INT dsty, INT dstw, INT dsth,
                                                                INT srcx, INT srcy, INT srcw, INT srch,
                                                                INT srcUnit, void *imageAttributes,
                                                                void *callback, void *callbackData);
__declspec(dllimport) GpStatus __stdcall GdipDeleteGraphics(GpGraphics *graphics);
__declspec(dllimport) GpStatus __stdcall GdipDisposeImage(GpImage *image);
static ULONG_PTR g_gdiplus;

/* The picker's preview cells: the head's column 5, the body's column 8 (scripts/build_vv1_appearance_
   bitmaps.py HEAD_FRAME / BODY_FRAME), so a tone's preview is the same pose as the game's own strip. */
#define PREVIEW_HEAD_COL 5
#define PREVIEW_BODY_COL 8

int __stdcall Vv1SkinToneDrawPreview(HDC dc, const RECT *rc, int male, int part, int row, int tone) {
    char leaf[64], relative[80];
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    int kind, file_w, file_h, src_x, src_y, width, height, draw_w, draw_h;
    double scale_x, scale_y, scale;
    GpBitmap *bitmap = NULL;
    GpGraphics *graphics = NULL;
    HBRUSH background;
    if (!g_installed || dc == NULL || rc == NULL || tone < 1 || tone > VVFP_SKIN_TONE_MAX || row < 0 || row >= 20) {
        return 0;
    }
    male = male != 0;
    if (part == VVFP_SKIN_PART_HEAD || part == VVFP_SKIN_PART_GREY_HEAD) {
        kind = part == VVFP_SKIN_PART_HEAD ? K_F_HEADS + male : K_F_GREY + male;
        tone_leaf(leaf, sizeof leaf, tone, KIND[kind].name);
        file_w = 280;
        file_h = 1300;
        src_x = PREVIEW_HEAD_COL * CELL_W;
        src_y = row * CELL_H;
    } else if (part == VVFP_SKIN_PART_BODY) {
        char file[40];
        kind = K_F_BODIES + male;
        wsprintfA(file, "%s0%d.png", KIND[kind].name, row / 10);
        tone_leaf(leaf, sizeof leaf, tone, file);
        file_w = 640;
        file_h = 650;
        src_x = PREVIEW_BODY_COL * CELL_W;
        src_y = (row % 10) * CELL_H;
    } else {
        return 0;
    }
    if (!png_fits(leaf, file_w, file_h)) {
        return 0;
    }
    lstrcpyA(relative, "Images\\");
    lstrcatA(relative, leaf);
    if (!vvfp_game_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, relative)) {
        return 0;
    }
    if (g_gdiplus == 0) {
        struct GdiplusStartupInputC input;
        input.GdiplusVersion = 1;
        input.DebugEventCallback = NULL;
        input.SuppressBackgroundThread = FALSE;
        input.SuppressExternalCodecs = FALSE;
        if (GdiplusStartup(&g_gdiplus, &input, NULL) != 0) {
            g_gdiplus = 0;
            return 0;
        }
    }
    if (GdipCreateBitmapFromFile(path, &bitmap) != 0 || bitmap == NULL) {
        return 0;
    }
    if (GdipCreateFromHDC(dc, &graphics) != 0 || graphics == NULL) {
        GdipDisposeImage(bitmap);
        return 0;
    }
    /* As the picker draws its own strip (vv1_origins_icons.c appearance_draw_from): the cell scaled to fit,
       centred, on the picker's grey. */
    width = rc->right - rc->left;
    height = rc->bottom - rc->top;
    background = CreateSolidBrush(RGB(236, 236, 236));
    FillRect(dc, rc, background);
    DeleteObject(background);
    scale_x = (double)width / CELL_W;
    scale_y = (double)height / CELL_H;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(CELL_W * scale);
    draw_h = (int)(CELL_H * scale);
    GdipSetInterpolationMode(graphics, 5);                  /* nearest neighbour, like COLORONCOLOR */
    GdipDrawImageRectRectI(graphics, bitmap, rc->left + (width - draw_w) / 2, rc->top + (height - draw_h) / 2,
                           draw_w, draw_h, src_x, src_y, CELL_W, CELL_H, 2 /* UnitPixel */, NULL, NULL, NULL);
    GdipDeleteGraphics(graphics);
    GdipDisposeImage(bitmap);
    return 1;
}

/* ---- exports ------------------------------------------------------------------------------------- */

/* Called once at game start by "VVFP Startup.dll" (its second word), outside DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_started || game != VV1_GAME) {
        return;
    }
    g_started = 1;
    g_rng = (GetTickCount() ^ (unsigned int)(UINT_PTR)&g_rng) | 1u;
    g_tone_count = count_tones();
    install_vv1();
}

int __stdcall Vv1SkinToneInstalled(void) {
    return g_installed;
}

int __stdcall Vv1SkinToneCount(void) {
    return g_installed ? g_tone_count : 0;
}

int __stdcall Vv1SkinToneGet(const void *record) {
    return g_installed ? st_get((const unsigned char *)record) : -1;
}

int __stdcall Vv1SkinToneOriginal(const void *record) {
    return g_installed ? st_original((const unsigned char *)record) : -1;
}

int __stdcall Vv1SkinToneSet(const void *record, int tone) {
    return g_installed ? st_set((const unsigned char *)record, tone) : 0;
}

int __stdcall Vv1SkinToneSetMany(const void *const *records, const int *tones, int count) {
    return g_installed ? st_set_many((const unsigned char *const *)records, tones, count) : 0;
}

int __stdcall Vv1SkinToneConceived(const void *mother, const void *father) {
    return g_installed ? st_conceived((const unsigned char *)mother, (const unsigned char *)father) : 0;
}

int __stdcall Vv1SkinToneBorn(const void *child, const void *mother) {
    return g_installed ? st_born((const unsigned char *)child, (const unsigned char *)mother) : 0;
}

void *__stdcall Vv1SkinToneSheetFor(const void *gameobj, const void *record, void *sprite) {
    const unsigned char *game = (const unsigned char *)gameobj;
    int kind;
    if (!g_installed || sprite == NULL || !is_record_of(game, (const unsigned char *)record)) {
        return sprite;
    }
    for (kind = K_F_HEADS; kind <= K_M_ACTIONS; ++kind) {
        if (*(void *const *)(game + KIND[kind].slot) == sprite) {
            return toned((const unsigned char *)record, kind, sprite);
        }
    }
    return sprite;
}

void *__stdcall Vv1SkinToneGreySheetFor(const void *record, int male, void *sprite) {
    if (!g_installed || sprite == NULL || st_index((const unsigned char *)record) < 0) {
        return sprite;
    }
    return toned((const unsigned char *)record, male ? K_M_GREY : K_F_GREY, sprite);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
