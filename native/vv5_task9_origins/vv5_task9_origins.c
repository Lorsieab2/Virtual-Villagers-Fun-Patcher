#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>   /* SHGetSpecialFolderPathA, CSIDL_PERSONAL */
#include <string.h>   /* strrchr */

/* Heathen-mask persistence: the per-villager mask side-table (nibble-packed,
   150 villagers x 4 bits = 75 bytes) lives in exe .data BSS at 0x7B1D20. The
   safest way to persist it is OUTSIDE the game's save flow (VV5's autosave does
   not re-run get_save_path, so an exe save-hook never fires). Instead the native
   code writes it from the chooser (WriteMaskSidecar, on OK) and reads it back on
   the first village frame (ReadMaskSidecar). Both build the path here in clean C,
   next to the game's own save: Documents\LDW\<exe-basename>\vvfp_masks_<slot>.dat.
   Keyed by villager record index (positional + stable across reload) AND by save
   slot: the exe-side slot_capture detour on buildSavePath stashes the current
   village slot at 0x7B1D7C, so each village keeps its own sidecar instead of one
   shared file bleeding masks across slots. The sidecar is a SEPARATE file from the
   .ldw, so it can never corrupt a save. */
#define MASK_TABLE_BYTES 75
/* Current save slot, written by the exe slot_capture detour (0 until the first
   save/load; village slots are >=1, slot 0 is the meta file). */
#define VV5_SLOT_SCRATCH 0x007B1D7Cu

static HINSTANCE module_instance;
static HWND origins_owner;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1013,   /* 14 tech-menu rows: rows 0..13 -> Buy 1000..1013 (row 13 = Change Appearance for All) */
    ID_CHECK_FIRST = 1100,
    STATE_VILLAGER = 0x10000,
    /* Architecture-aware state, above every dialog row/unavailable bit
       (0..21) and separate from STATE_VILLAGER. Expanded VV5 binds only the
       original Tech rows 0..5 and Details rows 0..3. */
    STATE_LIMITED_CAPABILITY = 0x400000
};

enum {
    ACTION_YOUTH = 0,
    ACTION_MASTERY = 1,
    ACTION_RUNNING = 2,
    ACTION_AGE18 = 3,
    ACTION_HEAL = 4,
    ACTION_APPEARANCE = 5,
    ACTION_TECH_BASE = 16,
    ACTION_COMPLETE_COLLECTIONS = 16,
    ACTION_RESET_COLLECTIONS = 17,
    ACTION_TECH_DOUBLER = 18,
    ACTION_FOOD_DOUBLER = 19,
    ACTION_GRANT_RUNNING_ALL = 20,
    ACTION_GRANT_MASTERY_ALL = 21,
    ACTION_SET_AGE_18_ALL = 22,
    ACTION_EQUAL_DIVISION_PARENTING = 23,
    ACTION_EQUAL_DIVISION_NO_PARENTING = 24,
    ACTION_CHANGE_APPEARANCE_ALL = 25
};

enum {
    RESULT_SUCCESS = 0,
    RESULT_NO_CHANGE = 1,
    RESULT_INVALID = 2,
    RESULT_INSUFFICIENT = 3,
    RESULT_CANCELLED = 4,
    RESULT_RECHECK = 5,
    RESULT_RETAINED = 6,
    RESULT_CHARGE_UNKNOWN = 7,
    RESULT_NO_SLOT = 8,
    RESULT_INVALID_SKILL = 9,
    RESULT_UNAVAILABLE = 10,
    RESULT_REMOVED = 11,
    RESULT_PURCHASED = 12,
    RESULT_UNSUPPORTED_SICKNESS = 13,
    RESULT_RUNNING_DISLIKE_CLEARED = 14,
    RESULT_APPEARANCE_UNCHANGED = 15
};

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
        origins_owner = NULL;
    }
    return TRUE;
}

/* Build Documents\LDW\<exe-basename>\vvfp_masks.dat into out (>= MAX_PATH).
   Ensures the folder exists. Returns 1 on success, 0 on failure. Slot 0 is
   retained for the pre-load legacy sidecar read; numbered village saves are
   exactly 1..5. Fail open on a truncated module path or a final path that
   cannot fit, before any unbounded wsprintfA writes. */
static int build_mask_sidecar_path(char *out) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    char *dot;
    int slot = *(volatile int *)VV5_SLOT_SCRATCH;
    DWORD n;
    int docs_len, base_len;
    if (slot < 0 || slot > 5) {
        return 0;
    }
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;   /* basename incl. ".exe" */
    dot = strrchr(base, '.');
    if (dot) {
        *dot = '\0';                /* strip the extension */
    }
    /* The longest valid output is the numbered form with slot 5.  Include
       the terminating NUL: the helper's callers provide char path[MAX_PATH],
       and wsprintfA/lstrcatA do not perform destination-size checks. */
    docs_len = lstrlenA(docs);
    base_len = lstrlenA(base);
    if (docs_len + 5 + base_len + (int)sizeof("\\vvfp_masks_5.dat") > MAX_PATH) {
        return 0;
    }
    /* ensure Documents\LDW and Documents\LDW\<base> exist (CreateDirectory is a
       no-op / harmless if they already do) */
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    /* Key per save slot when known (village slots are >=1). Before the first
       save/load the scratch is 0; fall back to the legacy unsuffixed name so a
       pre-load read never points at a slot-specific file that does not exist. */
    if (slot > 0) {
        wsprintfA(out, "%s\\LDW\\%s\\vvfp_masks_%d.dat", docs, base, slot);
    } else {
        wsprintfA(out, "%s\\LDW\\%s\\vvfp_masks.dat", docs, base);
    }
    return 1;
}

/* Persist the mask side-table (75 bytes at exe 0x7B1D20, passed in) to the
   sidecar. Called from the chooser on OK. Never touches the .ldw. */
__declspec(dllexport) void __stdcall WriteMaskSidecar(const unsigned char *table) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD wrote = 0;
    if (table == NULL || !build_mask_sidecar_path(path)) {
        return;
    }
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return;
    }
    WriteFile(h, table, MASK_TABLE_BYTES, &wrote, NULL);
    CloseHandle(h);
}

/* Restore the mask side-table from the sidecar into the 75-byte buffer at
   exe 0x7B1D20 (passed in). Zeroes the table if the sidecar is absent (a save
   with no recorded masks shows none). Called on the first village frame. */
__declspec(dllexport) void __stdcall ReadMaskSidecar(unsigned char *table) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0;
    if (table == NULL || !build_mask_sidecar_path(path)) {
        return;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        memset(table, 0, MASK_TABLE_BYTES);
        return;
    }
    ReadFile(h, table, MASK_TABLE_BYTES, &got, NULL);
    if (got < MASK_TABLE_BYTES) {
        memset(table + got, 0, MASK_TABLE_BYTES - got);
    }
    CloseHandle(h);
}

/* ---------- VV5 Change Appearance chooser (VV2-style) ----------
   Owner-drawn modal picker showing the selected villager's head and body
   sprites cropped from the stock game art (embedded BMP strips: male/female x
   young/old heads, male/female bodies). It reports only the chosen head/body
   indices back to the caller through the head/body pointers; the native task9
   handler owns the believer gate, the 5,000-tech charge, and the record
   writes, so this DLL never touches save data. Head catalog is 30 (0..29),
   body/outfit catalog is 29 (0..28); young/old is a head-atlas swap. */
#define IDD_APPEARANCE   203
#define IDB_HEAD_M_YOUNG 3001
#define IDB_HEAD_M_OLD   3002
#define IDB_HEAD_F_YOUNG 3003
#define IDB_HEAD_F_OLD   3004
#define IDB_BODY_M       3011
#define IDB_BODY_F       3012
#define IDB_MASK_PREVIEW 3013
#define IDC_BODY_PREVIEW 3101
#define IDC_HEAD_PREVIEW 3102
#define IDC_MASK_PREVIEW 3110
#define IDC_BODY_PREV    3103
#define IDC_BODY_NEXT    3104
#define IDC_HEAD_PREV    3105
#define IDC_HEAD_NEXT    3106
#define APPEARANCE_HEAD_COUNT 30
#define APPEARANCE_BODY_COUNT 30
#define APPEARANCE_CELL_W 40
#define APPEARANCE_CELL_H 65
/* Cosmetic Heathen-mask overlay: a purely visual per-villager choice stored by
   the native handler in record byte +0x1BC0 (0..5). It is rendered by a
   transient render-time faction flip in the exe patch and touches no faction
   state, so the villager stays a believer in every game system. */
#define IDC_MASK_LABEL   3107
#define IDC_MASK_PREV    3108
#define IDC_MASK_NEXT    3109
#define APPEARANCE_MASK_COUNT 6

static const char *const APPEARANCE_MASK_NAMES[APPEARANCE_MASK_COUNT] = {
    "(None)", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask",
    "Tribal Chief Mask"
};

static int appearance_sex;   /* 0 = male, 1 = female */
static int appearance_old;   /* 0 = young head atlas, 1 = old head atlas */
static int appearance_head;
static int appearance_body;
static int appearance_mask;  /* 0 = none, 1..5 = Blue/Orange/Red/Purple/Chief */

static void appearance_update_mask_label(HWND window) {
    SetDlgItemTextA(window, IDC_MASK_LABEL, APPEARANCE_MASK_NAMES[appearance_mask]);
}

static int appearance_head_bitmap(void) {
    if (appearance_sex) {
        return appearance_old ? IDB_HEAD_F_OLD : IDB_HEAD_F_YOUNG;
    }
    return appearance_old ? IDB_HEAD_M_OLD : IDB_HEAD_M_YOUNG;
}

static int appearance_body_bitmap(void) {
    return appearance_sex ? IDB_BODY_F : IDB_BODY_M;
}

static void appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
    /* The None entry has no artwork, so blitting its cell leaves an
       empty grey box next to Body and Head, which print words. Name
       it instead: a blank cell reads as a broken preview rather than
       a deliberate choice. */
    if (bitmap_id == IDB_MASK_PREVIEW && index == 0) {
        RECT none_rc = item->rcItem;
        HBRUSH none_bg = CreateSolidBrush(RGB(236, 236, 236));
        FillRect(item->hDC, &none_rc, none_bg);
        DeleteObject(none_bg);
        SetBkMode(item->hDC, TRANSPARENT);
        DrawTextA(item->hDC, "(None)", -1, &none_rc,
                  DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }

    RECT rc = item->rcItem;
    int width = rc.right - rc.left;
    int height = rc.bottom - rc.top;
    HBRUSH background = CreateSolidBrush(RGB(236, 236, 236));
    HBITMAP bitmap;
    HDC source;
    HBITMAP previous;
    double scale_x, scale_y, scale;
    int draw_w, draw_h, draw_x, draw_y;

    FillRect(item->hDC, &rc, background);
    DeleteObject(background);

    bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bitmap_id));
    if (bitmap == NULL) {
        return;
    }
    source = CreateCompatibleDC(item->hDC);
    previous = (HBITMAP)SelectObject(source, bitmap);

    scale_x = (double)width / APPEARANCE_CELL_W;
    scale_y = (double)height / APPEARANCE_CELL_H;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(APPEARANCE_CELL_W * scale);
    draw_h = (int)(APPEARANCE_CELL_H * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, index * APPEARANCE_CELL_W, 0, APPEARANCE_CELL_W, APPEARANCE_CELL_H,
        SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void appearance_repaint(HWND window, int control) {
    InvalidateRect(GetDlgItem(window, control), NULL, TRUE);
}

static INT_PTR CALLBACK appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        appearance_update_mask_label(window);
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_BODY_PREVIEW) {
            appearance_draw(item, appearance_body_bitmap(), appearance_body);
            return TRUE;
        }
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            appearance_draw(item, appearance_head_bitmap(), appearance_head);
            return TRUE;
        }
        if (item->CtlID == IDC_MASK_PREVIEW) {
            appearance_draw(item, IDB_MASK_PREVIEW, appearance_mask);
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == IDC_BODY_PREV) {
            appearance_body = (appearance_body + APPEARANCE_BODY_COUNT - 1) % APPEARANCE_BODY_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_BODY_NEXT) {
            appearance_body = (appearance_body + 1) % APPEARANCE_BODY_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_PREV) {
            appearance_head = (appearance_head + APPEARANCE_HEAD_COUNT - 1) % APPEARANCE_HEAD_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_NEXT) {
            appearance_head = (appearance_head + 1) % APPEARANCE_HEAD_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_PREV) {
            appearance_mask = (appearance_mask + APPEARANCE_MASK_COUNT - 1) % APPEARANCE_MASK_COUNT;
            appearance_update_mask_label(window);
            appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_NEXT) {
            appearance_mask = (appearance_mask + 1) % APPEARANCE_MASK_COUNT;
            appearance_update_mask_label(window);
            appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDOK) {
            EndDialog(window, 1);
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, 0);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowAppearanceChooser(
    int sex,
    int age,
    int *head,
    int *body,
    int *mask
) {
    INT_PTR result;
    appearance_sex = sex ? 1 : 0;
    appearance_old = age >= 1100 ? 1 : 0;
    appearance_head = (head && *head >= 0 && *head < APPEARANCE_HEAD_COUNT) ? *head : 0;
    appearance_body = (body && *body >= 0 && *body < APPEARANCE_BODY_COUNT) ? *body : 0;
    appearance_mask = (mask && *mask >= 0 && *mask < APPEARANCE_MASK_COUNT) ? *mask : 0;

    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_APPEARANCE),
        GetForegroundWindow(),
        appearance_dialog,
        0
    );
    if (result == 1) {
        if (head) {
            *head = appearance_head;
        }
        if (body) {
            *body = appearance_body;
        }
        if (mask) {
            *mask = appearance_mask;
        }
        return 1;
    }
    return 0;
}

__declspec(dllexport) void __stdcall WriteMaskSidecar(const unsigned char *table);
__declspec(dllexport) HWND __stdcall GetOriginsOwner(void);

/* ---------- Change Appearance for All (VV2-style, VV5 offsets) ----------
   Whole-village mass appearance editor for the Tech screen (450,000 tech). The
   DLL owns the entire commit: it shows dialog 214, then -- reading the game's
   absolute non-ASLR globals directly -- iterates the villager record array,
   applies the chosen head/body (per-sex or a village-wide override) and mask
   (per-sex, a village-wide single colour, or a distribution) writing head/body
   into the record and the mask into the exe's nibble-packed side-table, charges
   450,000 ONLY if at least one active villager was touched, and saves the mask
   sidecar. The exe side is a one-call bridge that never touches save data. */
#define IDD_APPEARANCE_ALL 214
/* per-sex owner-draw cyclers */
#define IDC_CAF_M_BODY 3201
#define IDC_CAF_M_HEAD 3202
#define IDC_CAF_M_MASK 3203
#define IDC_CAF_F_BODY 3204
#define IDC_CAF_F_HEAD 3205
#define IDC_CAF_F_MASK 3206
#define IDC_CAF_M_BODY_P 3211
#define IDC_CAF_M_HEAD_P 3212
#define IDC_CAF_M_MASK_P 3213
#define IDC_CAF_F_BODY_P 3214
#define IDC_CAF_F_HEAD_P 3215
#define IDC_CAF_F_MASK_P 3216
#define IDC_CAF_M_BODY_N 3221
#define IDC_CAF_M_HEAD_N 3222
#define IDC_CAF_M_MASK_N 3223
#define IDC_CAF_F_BODY_N 3224
#define IDC_CAF_F_HEAD_N 3225
#define IDC_CAF_F_MASK_N 3226
/* Mask Distribution radios */
#define IDC_CAF_DIST_OFF   3230
#define IDC_CAF_DIST_VV5   3231
#define IDC_CAF_DIST_RANDN 3232
#define IDC_CAF_DIST_RAND5 3234
#define IDC_CAF_DIST_EQUAL 3233
/* Village-wide single mask colour radios */
#define IDC_CAF_SINGLE_FIRST 3241   /* 3241..3246 = None,Blue,Orange,Red,Purple,Chief */
/* Village-wide Heads / Bodies radios */
#define IDC_CAF_HEADS_FIRST  3250   /* 3250..3256 = Off,Random,Black,Brown,Red,Blonde,Other */
#define IDC_CAF_BODIES_OFF   3260
#define IDC_CAF_BODIES_RAND  3261

/* VV5 game globals (non-ASLR, absolute) */
#define VV5_REC_BASE   0x00554190u
#define VV5_REC_STRIDE 0x2F44u
#define VV5_REC_COUNT  150
#define VV5_OFF_ACTIVE 0x1CD4      /* byte, 0 = free/dead */
#define VV5_OFF_SEX    0x1B90      /* dword, 0 = male, 1 = female */
#define VV5_OFF_AGE    0x1B8C      /* dword */
#define VV5_OFF_HEAD   0x1BB8      /* dword head index 0..29 */
#define VV5_OFF_BODY   0x1BBC      /* dword body index 0..28 */
#define VV5_OFF_RANK    0x1CFC     /* dword chief-rank marker; 0xD on the Retired Chief, 0 on ordinary villagers */
#define VV5_RANK_RETIRED_CHIEF 0x0D
#define VV5_MASK_TABLE 0x007B1D20u /* nibble-packed side-table, 150 villagers */
#define VV5_TECH       0x0051D5F8u /* int tech-point balance */
#define VV5_CHARGE_FN  0x004237B0u /* __thiscall(void* balance_ptr, int delta) */

/* Charge the tech balance through the game's own tech-adjust routine
   (0x4237B0, __thiscall: ecx = balance ptr, delta on stack). Inline asm avoids a
   __thiscall function-pointer cast, which the C compiler rejects. */
static void caf_charge(int delta) {
    __asm {
        mov  eax, delta
        push eax
        mov  ecx, 0x51D5F8
        mov  eax, 0x4237B0
        call eax
    }
}
/* The whole-village chooser must offer exactly what the individual one
   does, so these track APPEARANCE_*_COUNT rather than carrying their own
   numbers -- a separate 29 here left body 29 reachable only per villager. */
#define VV5_HEAD_COUNT APPEARANCE_HEAD_COUNT
#define VV5_BODY_COUNT APPEARANCE_BODY_COUNT

/* Hair-colour buckets (head-atlas rows) for the "All <colour> Hair" options.
   Seeded from the hair-band median RGB then hand-verified against a labelled
   render (VV2 principle: RED = only clearly-ginger / high-saturation warm hair;
   auburn/dark-gold reads as BROWN; dyed green/blue and grey elder hair -> OTHER).
   adjust an index here if any head is miscategorised. */
static const unsigned char CAF_M_BLACK[]  = {0,1,2,4,5,7,19};
static const unsigned char CAF_M_BROWN[]  = {6,8,9,10,12,13,16};
static const unsigned char CAF_M_RED[]    = {11,20,21,22};
static const unsigned char CAF_M_BLONDE[] = {14,15,17,18,23,24,25,26,27,28,29};
static const unsigned char CAF_M_OTHER[]  = {3};
static const unsigned char CAF_F_BLACK[]  = {0,1,2,3,4,6};
static const unsigned char CAF_F_BROWN[]  = {8,10,11,12,13,14,16,20,23};
static const unsigned char CAF_F_RED[]    = {7,9,15,17,19,22};
static const unsigned char CAF_F_BLONDE[] = {24,25,26,27,28,29};
static const unsigned char CAF_F_OTHER[]  = {5,18,21};

/* dialog state: per-sex cyclers ([0]=male,[1]=female); -1 = "No change". */
static int caf_body[2];
static int caf_head[2];
static int caf_mask[2];
static int caf_heads_mode;   /* 0=Off,1=Random,2=Black,3=Brown,4=Red,5=Blonde,6=Other */
static int caf_bodies_mode;  /* 0=Off,1=Random */
static int caf_mask_dist;    /* 0=Off,1=VV5,2=Rand+None,3=RandAll5,4=Equal */
static int caf_single_mask;  /* -1 = none selected; 0..5 = single colour override */

static unsigned int caf_rng;
static unsigned int caf_rand(void) {           /* xorshift, self-contained */
    caf_rng ^= caf_rng << 13; caf_rng ^= caf_rng >> 17; caf_rng ^= caf_rng << 5;
    return caf_rng;
}

static unsigned char *caf_rec(int i) {
    return (unsigned char *)(VV5_REC_BASE + (unsigned int)i * VV5_REC_STRIDE);
}
static void caf_set_mask(int idx, int mask) {
    unsigned char *t = (unsigned char *)VV5_MASK_TABLE;
    unsigned char b = t[idx >> 1];
    if (idx & 1) b = (unsigned char)((b & 0x0F) | ((mask & 0x0F) << 4));
    else         b = (unsigned char)((b & 0xF0) | (mask & 0x0F));
    t[idx >> 1] = b;
}
static int caf_bucket_head(int sex, int mode) {
    const unsigned char *b; int n;
    switch (mode) {
        case 2: b = sex ? CAF_F_BLACK : CAF_M_BLACK; n = sex ? (int)(sizeof CAF_F_BLACK) : (int)(sizeof CAF_M_BLACK); break;
        case 3: b = sex ? CAF_F_BROWN : CAF_M_BROWN; n = sex ? (int)(sizeof CAF_F_BROWN) : (int)(sizeof CAF_M_BROWN); break;
        case 4: b = sex ? CAF_F_RED : CAF_M_RED;     n = sex ? (int)(sizeof CAF_F_RED)   : (int)(sizeof CAF_M_RED);   break;
        case 5: b = sex ? CAF_F_BLONDE : CAF_M_BLONDE; n = sex ? (int)(sizeof CAF_F_BLONDE) : (int)(sizeof CAF_M_BLONDE); break;
        default: b = sex ? CAF_F_OTHER : CAF_M_OTHER; n = sex ? (int)(sizeof CAF_F_OTHER) : (int)(sizeof CAF_M_OTHER); break;
    }
    return b[caf_rand() % (unsigned)n];
}

/* Find the Retired Chief for the VV5-style single Chief slot. The Retired Chief
   is the one villager carrying the native chief-rank marker +0x1CFC == 0xD;
   ordinary villagers read 0 there. Verified live: in a real village exactly one
   villager (the Retired Chief) has this set, and it is his native value (his mask
   in the side-table is unrelated). The mask feature only flips +0x1CFC transiently
   inside the render, so at apply time it holds the native value. If no Retired
   Chief exists in the village, a RANDOM active villager gets the Chief mask.
   Returns -1 only if the village is empty. */
static int caf_find_chief(const int *active, int na) {
    int i;
    if (na <= 0) return -1;
    for (i = 0; i < na; ++i) {
        if (*(unsigned int *)(caf_rec(active[i]) + VV5_OFF_RANK) == VV5_RANK_RETIRED_CHIEF)
            return i;
    }
    return (int)(caf_rand() % (unsigned)na);
}

static void caf_shuffle(int *a, int n) {
    int i, j, t;
    for (i = n - 1; i > 0; --i) { j = (int)(caf_rand() % (unsigned)(i + 1)); t = a[i]; a[i] = a[j]; a[j] = t; }
}

/* Apply the current dialog selection to every active villager. Returns the
   number of active villagers touched (0 if nothing was selected / village
   empty). Head/body writes go to the record; mask writes go to the side-table. */
static int caf_apply(void) {
    int active[VV5_REC_COUNT];
    int sex_of[VV5_REC_COUNT];
    int na = 0, i, touched = 0;
    for (i = 0; i < VV5_REC_COUNT; ++i) {
        unsigned char *r = caf_rec(i);
        if (r[VV5_OFF_ACTIVE] == 0) continue;
        active[na] = i;
        sex_of[na] = (*(int *)(r + VV5_OFF_SEX)) ? 1 : 0;
        ++na;
    }
    if (na == 0) return 0;

    /* Heads */
    if (caf_heads_mode != 0) {
        for (i = 0; i < na; ++i)
            *(int *)(caf_rec(active[i]) + VV5_OFF_HEAD) =
                (caf_heads_mode == 1) ? (int)(caf_rand() % VV5_HEAD_COUNT)
                                      : caf_bucket_head(sex_of[i], caf_heads_mode);
        touched = na;
    } else {
        for (i = 0; i < na; ++i)
            if (caf_head[sex_of[i]] >= 0) { *(int *)(caf_rec(active[i]) + VV5_OFF_HEAD) = caf_head[sex_of[i]]; touched = na; }
    }
    /* Bodies */
    if (caf_bodies_mode != 0) {
        for (i = 0; i < na; ++i)
            *(int *)(caf_rec(active[i]) + VV5_OFF_BODY) = (int)(caf_rand() % VV5_BODY_COUNT);
        touched = na;
    } else {
        for (i = 0; i < na; ++i)
            if (caf_body[sex_of[i]] >= 0) { *(int *)(caf_rec(active[i]) + VV5_OFF_BODY) = caf_body[sex_of[i]]; touched = na; }
    }
    /* Masks */
    if (caf_single_mask >= 0) {                       /* village-wide single colour */
        for (i = 0; i < na; ++i) caf_set_mask(active[i], caf_single_mask);
        touched = na;
    } else if (caf_mask_dist == 1) {                  /* VV5-style tiers */
        int order[VV5_REC_COUNT], k;
        for (i = 0; i < na; ++i) order[i] = i;         /* index into active[] */
        caf_shuffle(order, na);
        {
            int chief = caf_find_chief(active, na);
            int purple = 4, red = 7, orange = 10, assigned = 0;
            for (k = 0; k < na; ++k) {
                int slot = order[k], m;
                if (active[slot] == (chief >= 0 ? active[chief] : -1)) continue; /* chief handled below */
                if (assigned < purple) m = 4;
                else if (assigned < purple + red) m = 3;
                else if (assigned < purple + red + orange) m = 2;
                else m = 1;
                caf_set_mask(active[slot], m);
                ++assigned;
            }
            if (chief >= 0) caf_set_mask(active[chief], 5);
        }
        touched = na;
    } else if (caf_mask_dist == 2) {                  /* Random (All 5 + No Mask) */
        for (i = 0; i < na; ++i) caf_set_mask(active[i], (int)(caf_rand() % 6));
        touched = na;
    } else if (caf_mask_dist == 3) {                  /* Random (All 5) */
        for (i = 0; i < na; ++i) caf_set_mask(active[i], (int)(caf_rand() % 5) + 1);
        touched = na;
    } else if (caf_mask_dist == 4) {                  /* Equal, balanced M/F */
        int males[VV5_REC_COUNT], females[VV5_REC_COUNT], nm = 0, nf = 0, k = 0, a = 0, b = 0;
        for (i = 0; i < na; ++i) (sex_of[i] ? (females[nf++] = active[i]) : (males[nm++] = active[i]));
        caf_shuffle(males, nm); caf_shuffle(females, nf);
        while (a < nm || b < nf) {
            if (a < nm) caf_set_mask(males[a++], (k++ % 5) + 1);
            if (b < nf) caf_set_mask(females[b++], (k++ % 5) + 1);
        }
        touched = na;
    } else {                                          /* Off -> per-sex mask cyclers */
        for (i = 0; i < na; ++i)
            if (caf_mask[sex_of[i]] >= 0) { caf_set_mask(active[i], caf_mask[sex_of[i]]); touched = na; }
    }
    return touched;
}

/* draw one for-All preview cell: "No change" text when value < 0, else the
   stock sprite cell (young head atlas / body / mask strip). */
static void caf_draw(DRAWITEMSTRUCT *item, int sex, int kind, int value) {
    RECT rc = item->rcItem;
    HBRUSH bg = CreateSolidBrush(RGB(236, 236, 236));
    int bmp_id, cell_w, cell_h;
    FillRect(item->hDC, &rc, bg);
    DeleteObject(bg);
    if (value < 0) {
        SetBkMode(item->hDC, TRANSPARENT);
        DrawTextA(item->hDC, "No change", -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }
    if (kind == 0) { bmp_id = sex ? IDB_BODY_F : IDB_BODY_M; cell_w = APPEARANCE_CELL_W; cell_h = APPEARANCE_CELL_H; }
    else if (kind == 1) { bmp_id = sex ? IDB_HEAD_F_YOUNG : IDB_HEAD_M_YOUNG; cell_w = APPEARANCE_CELL_W; cell_h = APPEARANCE_CELL_H; }
    else { bmp_id = IDB_MASK_PREVIEW; cell_w = APPEARANCE_CELL_W; cell_h = APPEARANCE_CELL_H; }
    {
        HBITMAP bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bmp_id));
        HDC src; HBITMAP prev; double sx, sy, s; int dw, dh, dx, dy;
        int w = rc.right - rc.left, h = rc.bottom - rc.top;
        if (bitmap == NULL) return;
        src = CreateCompatibleDC(item->hDC);
        prev = (HBITMAP)SelectObject(src, bitmap);
        sx = (double)w / cell_w; sy = (double)h / cell_h; s = sx < sy ? sx : sy;
        dw = (int)(cell_w * s); dh = (int)(cell_h * s);
        dx = rc.left + (w - dw) / 2; dy = rc.top + (h - dh) / 2;
        SetStretchBltMode(item->hDC, COLORONCOLOR);
        StretchBlt(item->hDC, dx, dy, dw, dh, src, value * cell_w, 0, cell_w, cell_h, SRCCOPY);
        SelectObject(src, prev); DeleteDC(src); DeleteObject(bitmap);
    }
}

static void caf_cycle(int *v, int max, int dir) {   /* -1 = No change wraps at each end */
    if (dir > 0) *v = (*v >= max) ? -1 : (*v + 1);
    else         *v = (*v < 0) ? max : (*v - 1);
}
static void caf_repaint(HWND w, int id) { InvalidateRect(GetDlgItem(w, id), NULL, TRUE); }

static void caf_update_gray(HWND w) {
    int mask_override = (caf_mask_dist != 0) || (caf_single_mask >= 0);
    int head_override = (caf_heads_mode != 0);
    int body_override = (caf_bodies_mode != 0);
    int i;
    static const int mask_c[] = {IDC_CAF_M_MASK_P, IDC_CAF_M_MASK_N, IDC_CAF_F_MASK_P, IDC_CAF_F_MASK_N};
    static const int head_c[] = {IDC_CAF_M_HEAD_P, IDC_CAF_M_HEAD_N, IDC_CAF_F_HEAD_P, IDC_CAF_F_HEAD_N};
    static const int body_c[] = {IDC_CAF_M_BODY_P, IDC_CAF_M_BODY_N, IDC_CAF_F_BODY_P, IDC_CAF_F_BODY_N};
    for (i = 0; i < 4; ++i) EnableWindow(GetDlgItem(w, mask_c[i]), !mask_override);
    for (i = 0; i < 4; ++i) EnableWindow(GetDlgItem(w, head_c[i]), !head_override);
    for (i = 0; i < 4; ++i) EnableWindow(GetDlgItem(w, body_c[i]), !body_override);
}

static INT_PTR CALLBACK caf_dialog(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_INITDIALOG) {
        caf_body[0] = caf_body[1] = caf_head[0] = caf_head[1] = caf_mask[0] = caf_mask[1] = -1;
        caf_heads_mode = 0; caf_bodies_mode = 0; caf_mask_dist = 0; caf_single_mask = -1;
        CheckDlgButton(w, IDC_CAF_HEADS_FIRST, BST_CHECKED);
        CheckDlgButton(w, IDC_CAF_BODIES_OFF, BST_CHECKED);
        CheckDlgButton(w, IDC_CAF_DIST_OFF, BST_CHECKED);
        caf_update_gray(w);
        return TRUE;
    } else if (msg == WM_DRAWITEM) {
        DRAWITEMSTRUCT *it = (DRAWITEMSTRUCT *)lp;
        switch (it->CtlID) {
            case IDC_CAF_M_BODY: caf_draw(it, 0, 0, caf_body[0]); return TRUE;
            case IDC_CAF_M_HEAD: caf_draw(it, 0, 1, caf_head[0]); return TRUE;
            case IDC_CAF_M_MASK: caf_draw(it, 0, 2, caf_mask[0]); return TRUE;
            case IDC_CAF_F_BODY: caf_draw(it, 1, 0, caf_body[1]); return TRUE;
            case IDC_CAF_F_HEAD: caf_draw(it, 1, 1, caf_head[1]); return TRUE;
            case IDC_CAF_F_MASK: caf_draw(it, 1, 2, caf_mask[1]); return TRUE;
        }
    } else if (msg == WM_COMMAND) {
        int id = LOWORD(wp);
        switch (id) {
            case IDC_CAF_M_BODY_P: caf_cycle(&caf_body[0], VV5_BODY_COUNT - 1, -1); caf_repaint(w, IDC_CAF_M_BODY); return TRUE;
            case IDC_CAF_M_BODY_N: caf_cycle(&caf_body[0], VV5_BODY_COUNT - 1,  1); caf_repaint(w, IDC_CAF_M_BODY); return TRUE;
            case IDC_CAF_F_BODY_P: caf_cycle(&caf_body[1], VV5_BODY_COUNT - 1, -1); caf_repaint(w, IDC_CAF_F_BODY); return TRUE;
            case IDC_CAF_F_BODY_N: caf_cycle(&caf_body[1], VV5_BODY_COUNT - 1,  1); caf_repaint(w, IDC_CAF_F_BODY); return TRUE;
            case IDC_CAF_M_HEAD_P: caf_cycle(&caf_head[0], VV5_HEAD_COUNT - 1, -1); caf_repaint(w, IDC_CAF_M_HEAD); return TRUE;
            case IDC_CAF_M_HEAD_N: caf_cycle(&caf_head[0], VV5_HEAD_COUNT - 1,  1); caf_repaint(w, IDC_CAF_M_HEAD); return TRUE;
            case IDC_CAF_F_HEAD_P: caf_cycle(&caf_head[1], VV5_HEAD_COUNT - 1, -1); caf_repaint(w, IDC_CAF_F_HEAD); return TRUE;
            case IDC_CAF_F_HEAD_N: caf_cycle(&caf_head[1], VV5_HEAD_COUNT - 1,  1); caf_repaint(w, IDC_CAF_F_HEAD); return TRUE;
            case IDC_CAF_M_MASK_P: caf_cycle(&caf_mask[0], 5, -1); caf_repaint(w, IDC_CAF_M_MASK); return TRUE;
            case IDC_CAF_M_MASK_N: caf_cycle(&caf_mask[0], 5,  1); caf_repaint(w, IDC_CAF_M_MASK); return TRUE;
            case IDC_CAF_F_MASK_P: caf_cycle(&caf_mask[1], 5, -1); caf_repaint(w, IDC_CAF_F_MASK); return TRUE;
            case IDC_CAF_F_MASK_N: caf_cycle(&caf_mask[1], 5,  1); caf_repaint(w, IDC_CAF_F_MASK); return TRUE;
            case IDOK: EndDialog(w, 1); return TRUE;
            case IDCANCEL: EndDialog(w, 0); return TRUE;
        }
        if (id >= IDC_CAF_HEADS_FIRST && id <= IDC_CAF_HEADS_FIRST + 6) {
            caf_heads_mode = id - IDC_CAF_HEADS_FIRST; caf_update_gray(w); return TRUE;
        }
        if (id == IDC_CAF_BODIES_OFF || id == IDC_CAF_BODIES_RAND) {
            caf_bodies_mode = (id == IDC_CAF_BODIES_RAND) ? 1 : 0; caf_update_gray(w); return TRUE;
        }
        /* Mask Distribution + Single-Mask-Colour are ONE logical group across two
           groupboxes: selecting one clears the other. */
        if (id == IDC_CAF_DIST_OFF || id == IDC_CAF_DIST_VV5 || id == IDC_CAF_DIST_RANDN
            || id == IDC_CAF_DIST_RAND5 || id == IDC_CAF_DIST_EQUAL) {
            int m; caf_single_mask = -1;
            for (m = 0; m < 6; ++m) CheckDlgButton(w, IDC_CAF_SINGLE_FIRST + m, BST_UNCHECKED);
            caf_mask_dist = (id == IDC_CAF_DIST_VV5) ? 1 : (id == IDC_CAF_DIST_RANDN) ? 2
                          : (id == IDC_CAF_DIST_RAND5) ? 3 : (id == IDC_CAF_DIST_EQUAL) ? 4 : 0;
            caf_update_gray(w); return TRUE;
        }
        if (id >= IDC_CAF_SINGLE_FIRST && id <= IDC_CAF_SINGLE_FIRST + 5) {
            CheckDlgButton(w, IDC_CAF_DIST_OFF, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_VV5, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_RANDN, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_RAND5, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_EQUAL, BST_UNCHECKED);
            caf_mask_dist = 0; caf_single_mask = id - IDC_CAF_SINGLE_FIRST;
            caf_update_gray(w); return TRUE;
        }
    } else if (msg == WM_CLOSE) {
        EndDialog(w, 0); return TRUE;
    }
    return FALSE;
}

/* Change Appearance for All. Shows dialog 214; on OK, if the village has enough
   tech and at least one villager is touched, applies to all and charges 450,000
   via the game's own tech-adjust routine, then saves the mask sidecar. Returns
   1 if applied+charged, 0 otherwise. All commit logic is here (exe is a bridge). */
__declspec(dllexport) int __stdcall ShowVV5AppearanceForAll(void) {
    INT_PTR ok;
    HWND owner;
    caf_rng = GetTickCount() | 1u;
    owner = GetOriginsOwner();
    ok = DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_APPEARANCE_ALL),
                         owner, caf_dialog, 0);
    if (ok != 1) return 0;
    if (*(int *)VV5_TECH < 450000) {
        MessageBoxA(owner, "Not enough tech points. This upgrade costs 450,000.",
                    "Change Appearance for All", MB_OK | MB_ICONWARNING);
        return 0;
    }
    /* one-time genetics warning if any head field will change */
    if (caf_heads_mode != 0 || caf_head[0] >= 0 || caf_head[1] >= 0) {
        if (MessageBoxA(owner,
                "Warning: This will change the head genetics of every villager of the selected sex, affecting their descendants.\r\n\r\nProceed?",
                "Change Appearance for All", MB_OKCANCEL | MB_ICONWARNING) != IDOK)
            return 0;
    }
    {
        int touched = caf_apply();
        if (touched <= 0) {
            MessageBoxA(owner, "No appearance options were selected. No tech points deducted.",
                        "Change Appearance for All", MB_OK | MB_ICONINFORMATION);
            return 0;
        }
        caf_charge(-450000);
        WriteMaskSidecar((const unsigned char *)VV5_MASK_TABLE);
        MessageBoxA(owner, "Change Appearance for All applied to every villager.",
                    "Change Appearance for All", MB_OK | MB_ICONINFORMATION);
        return 1;
    }
}

static HWND validate_same_process_window(HWND window) {
    DWORD process_id = 0;
    if (window == NULL || !IsWindow(window)) {
        return NULL;
    }
    if (GetWindowThreadProcessId(window, &process_id) == 0
        || process_id != GetCurrentProcessId()) {
        return NULL;
    }
    return window;
}

__declspec(dllexport) int __stdcall BeginOriginsOwner(void) {
    HWND candidate = validate_same_process_window(GetForegroundWindow());
    origins_owner = candidate;
    return candidate != NULL;
}

__declspec(dllexport) HWND __stdcall GetOriginsOwner(void) {
    HWND owner = validate_same_process_window(origins_owner);
    if (owner == NULL) {
        origins_owner = NULL;
    }
    return owner;
}

__declspec(dllexport) void __stdcall EndOriginsOwner(void) {
    origins_owner = NULL;
}

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int limited_capability = (lparam & STATE_LIMITED_CAPABILITY) != 0;
        int first_unsupported_row = villager_menu ? 4 : 6;
        int row_count = villager_menu ? 5 : 14;
        int row;
        for (row = 0; row < row_count; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
            if (limited_capability && row >= first_unsupported_row) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            } else if ((lparam & (1 << row)) != 0) {
                /* Only the two Doublers may ever show a green check, and only
                   while they are owned in the current save. Every other row --
                   including the Details menu's already-satisfied rows, whose
                   state bits 0-3 the callers deliberately set -- keeps its
                   badge hidden and conveys state through the button instead. */
                if (!villager_menu && (row == 3 || row == 4)) {
                    ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                }
                if (villager_menu) {
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                } else if (row == 3 || row == 4) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                } else {
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                }
            } else if ((lparam & (1 << (8 + row))) != 0) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
        }
        return TRUE;
    }
    if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            EndDialog(window, (INT_PTR)(command - ID_BUY_FIRST));
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    }
    if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    HWND owner = GetOriginsOwner();
    if (owner == NULL) {
        return -1;
    }
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(villager_menu ? IDD_ORIGINS_VILLAGER : IDD_ORIGINS_TECH),
        owner,
        upgrade_dialog,
        dialog_state
    );
}

static const char *action_name(unsigned int action) {
    switch (action) {
    case ACTION_YOUTH: return "Grant Youth";
    case ACTION_MASTERY: return "Grant Full Mastery";
    case ACTION_RUNNING: return "Grant Running";
    case ACTION_AGE18: return "Set Age to 18";
    case ACTION_HEAL: return "Full Heal / Cure All";
    case ACTION_APPEARANCE: return "Change Appearance";
    case ACTION_COMPLETE_COLLECTIONS: return "Complete All Collections";
    case ACTION_RESET_COLLECTIONS: return "Reset All Collections";
    case ACTION_TECH_DOUBLER: return "Tech Point Doubler";
    case ACTION_FOOD_DOUBLER: return "Food Point Doubler";
    case ACTION_GRANT_RUNNING_ALL: return "Grant Running to All Villagers";
    case ACTION_GRANT_MASTERY_ALL: return "Grant Full Mastery to All Villagers";
    case ACTION_SET_AGE_18_ALL: return "All Villagers are Exactly 18";
    case ACTION_EQUAL_DIVISION_PARENTING: return "Equal Division of Labor (Includes Parenting)";
    case ACTION_EQUAL_DIVISION_NO_PARENTING: return "Equal Division of Labor (No Parenting)";
    case ACTION_CHANGE_APPEARANCE_ALL: return "Change Appearance for All";
    default: return "Origins upgrade";
    }
}

static const char *action_cost(unsigned int action) {
    switch (action) {
    case ACTION_YOUTH: return "50,000";
    case ACTION_MASTERY: return "100,000";
    case ACTION_RUNNING: return "40,000";
    case ACTION_AGE18: return "50,000";
    case ACTION_HEAL: return "30,000";
    case ACTION_APPEARANCE: return "5,000";
    case ACTION_TECH_DOUBLER:
    case ACTION_FOOD_DOUBLER: return "500,000";
    case ACTION_CHANGE_APPEARANCE_ALL: return "450,000";
    default: return "1,000,000";
    }
}

/* Correct singular/plural for a villager count. */
static const char *vpl(unsigned int n) { return n == 1 ? "Villager" : "Villagers"; }
static const char *vpl_lc(unsigned int n) { return n == 1 ? "villager" : "villagers"; }

/* Capitalised forms for the Equal Division results. The possessive moves the
   apostrophe rather than just adding an "s", so it needs its own helper. */
static const char *vpl_uc(unsigned int n) { return n == 1 ? "Villager" : "Villagers"; }
static const char *vpl_pos(unsigned int n) { return n == 1 ? "Villager's" : "Villagers'"; }


/* ---- Equal Division of Labor (VV5) -------------------------------------------
   Split every eligible Believer's job-preference checkmark round-robin so the
   population is spread evenly across the professions. Record fields (base +
   i*STRIDE): active +0x1CD4, Heathen mask +0x1CE1 (== 0), faction +0x1CEC
   (== 0), signed health +0x1C40 (> 0), sex dword +0x1B90 (0 male / 1 female),
   preferred-skill index +0x1C74 (0 Farming, 1 Parenting, 2 Healing, 3 Research,
   4 Building, 5 Devotion). A separate seat counter per sex keeps each
   profession's male/female split balanced as well as the total count.
   Assignment order is Farming, Building, Research, Healing, [Parenting,]
   Devotion -- `parenting` picks 6 professions, otherwise 5 (Parenting dropped).
   Preferences are overwritten unconditionally, so the count is simply the
   number eligible. Believer-only: masked Heathens and off-faction villagers are
   never touched, and VV5 has no Golden Child so nothing else is skipped.
   Eligibility is otherwise EVERYONE alive -- children of any age, nursing
   mothers, and adults. The per-profession, per-sex breakdown does not fit
   ShowVV5Task9Result's two counts, so this composes and shows its own result. */
#define VV5_ED_STRIDE     0x2F44
#define VV5_ED_COUNT      150
#define VV5_ED_ACTIVE     0x1CD4
#define VV5_ED_MASK       0x1CE1
#define VV5_ED_FACTION    0x1CEC
#define VV5_ED_HEALTH     0x1C40
#define VV5_ED_SEX        0x1B90
#define VV5_ED_PREFERENCE 0x1C74

__declspec(dllexport) int __stdcall ApplyVV5EqualDivision(
    unsigned char *base,
    int parenting
) {
    /* Seat order names plus the skill index written to +0x1C74 for each seat. */
    static const char *const name_parenting[6] = {
        "Farming", "Building", "Research", "Healing", "Breeding", "Devotion"
    };
    static const int index_parenting[6] = { 0, 4, 3, 2, 1, 5 };
    static const char *const name_no_parenting[5] = {
        "Farming", "Building", "Research", "Healing", "Devotion"
    };
    static const int index_no_parenting[5] = { 0, 4, 3, 2, 5 };
    const char *const *pro_name = parenting ? name_parenting : name_no_parenting;
    const int *pro_index = parenting ? index_parenting : index_no_parenting;
    int professions = parenting ? 6 : 5;
    int male_seat = 0, female_seat = 0;
    int male_count[6] = { 0, 0, 0, 0, 0, 0 };
    int female_count[6] = { 0, 0, 0, 0, 0, 0 };
    int total = 0;
    int i, p;
    char message[512];
    char line[128];
    unsigned char *record = base;
    HWND owner = GetOriginsOwner();
    if (base == 0) {
        return 0;
    }
    for (i = 0; i < VV5_ED_COUNT; ++i, record += VV5_ED_STRIDE) {
        int seat;
        if (record[VV5_ED_ACTIVE] == 0) {
            continue;
        }
        if (record[VV5_ED_MASK] != 0) {       /* masked Heathen -- never touch */
            continue;
        }
        if (record[VV5_ED_FACTION] != 0) {    /* off-faction -- never touch */
            continue;
        }
        if (*(int *)(record + VV5_ED_HEALTH) <= 0) {
            continue;
        }
        if (*(int *)(record + VV5_ED_SEX) == 0) {   /* male */
            seat = male_seat % professions;
            ++male_seat;
            ++male_count[seat];
        } else {                                     /* female */
            seat = female_seat % professions;
            ++female_seat;
            ++female_count[seat];
        }
        *(int *)(record + VV5_ED_PREFERENCE) = pro_index[seat];
        ++total;
    }
    if (total == 0) {
        MessageBoxA(
            owner,
            "No villagers were eligible. No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
        return 0;
    }
    wsprintfA(message, "Set %u %s Job Preferences.", (unsigned int)total,
              vpl_pos((unsigned int)total));
    for (p = 0; p < professions; ++p) {
        wsprintfA(line, "\r\n\r\n%s: %u %s (%u Male, %u Female).",
                  pro_name[p],
                  (unsigned int)(male_count[p] + female_count[p]),
                  vpl_uc((unsigned int)(male_count[p] + female_count[p])),
                  (unsigned int)male_count[p], (unsigned int)female_count[p]);
        lstrcatA(message, line);
    }
    MessageBoxA(
        owner, message, "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION
    );
    return 1;
}

__declspec(dllexport) int __stdcall ConfirmVV5Task9Action(
    unsigned int action,
    unsigned int amount_a,
    unsigned int amount_b
) {
    HWND owner = GetOriginsOwner();
    char message[256];
    const char *title = (action == ACTION_HEAL || action >= ACTION_TECH_BASE)
        ? "Origins Upgrades"
        : "Villager Upgrades";
    (void)amount_a;
    (void)amount_b;
    if (owner == NULL) {
        return 0;
    }
    /* One OK/Cancel purchase box naming the upgrade and its cost. */
    wsprintfA(
        message,
        "Do you want to buy %s for %s tech points?\r\nPress OK to confirm, or Cancel.",
        action_name(action),
        action_cost(action)
    );
    return MessageBoxA(owner, message, title, MB_OKCANCEL | MB_ICONQUESTION) == IDOK;
}

__declspec(dllexport) int __stdcall ShowVV5Task9GeneticsWarning(void) {
    HWND owner = GetOriginsOwner();
    if (owner == NULL) {
        return 0;
    }
    return MessageBoxA(
        owner,
        "Warning: This will change the villager's head genetics.",
        "Villager Upgrades",
        MB_OKCANCEL | MB_ICONWARNING
    ) == IDOK;
}

__declspec(dllexport) int __stdcall ShowVV5Task9Result(
    unsigned int action,
    unsigned int status,
    unsigned int amount_a,
    unsigned int amount_b
) {
    HWND owner = GetOriginsOwner();
    char message[512];
    const char *name = action_name(action);
    if (owner == NULL) {
        return 0;
    }
    switch (status) {
    case RESULT_SUCCESS:
        if (action == ACTION_HEAL) {
            wsprintfA(message, "Cured sickness from %u %s.\r\n\r\nRestored %u %s to full health.",
                      amount_a, vpl_lc(amount_a), amount_b, vpl_lc(amount_b));
        } else if (action == ACTION_COMPLETE_COLLECTIONS) {
            wsprintfA(message, "Marked all %u collectibles as found and triggered %u collection goals.", amount_a, amount_b);
        } else if (action == ACTION_RESET_COLLECTIONS) {
            wsprintfA(message, "Cleared all %u collectibles.", amount_a);
        } else if (action == ACTION_GRANT_RUNNING_ALL) {
            unsigned int granted = amount_b >> 16, removed = amount_b & 0xFFFF;
            unsigned int liked = amount_a >> 16, full = amount_a & 0xFFFF;
            wsprintfA(
                message,
                "Granted Running to %u %s.\r\n\r\n"
                "Removed a Running dislike from %u %s.\r\n\r\n"
                "Skipped %u %s: already like Running.\r\n\r\n"
                "Skipped %u %s: already have 3 likes.",
                granted, vpl(granted), removed, vpl(removed),
                liked, vpl(liked), full, vpl(full)
            );
        } else if (action == ACTION_GRANT_MASTERY_ALL) {
            wsprintfA(
                message,
                "Granted Full Mastery to %u %s.\r\n\r\n"
                "Skipped %u %s: already fully mastered.",
                amount_a, vpl(amount_a), amount_b, vpl(amount_b)
            );
        } else if (action == ACTION_SET_AGE_18_ALL) {
            wsprintfA(
                message,
                "Set %u %s to Age 18.\r\n\r\n"
                "Skipped %u %s: already exactly 18.",
                amount_a, vpl(amount_a), amount_b, vpl(amount_b)
            );
        } else {
            wsprintfA(message, "%s completed.", name);
        }
        break;
    case RESULT_NO_CHANGE:
        if (action == ACTION_YOUTH) {
            lstrcpyA(message, "This villager is already full of youth. No tech points have been deducted.");
        } else if (action == ACTION_MASTERY) {
            lstrcpyA(message, "This villager is already fully mastered. No tech points have been deducted.");
        } else if (action == ACTION_RUNNING) {
            lstrcpyA(message, "This villager already likes Running. No tech points have been deducted.");
        } else if (action == ACTION_AGE18) {
            lstrcpyA(message, "No changes were needed. No tech points have been deducted.");
        } else if (action == ACTION_HEAL) {
            lstrcpyA(message, "Everyone is at full health already. No villagers are sick. No tech points have been deducted.");
        } else if (action == ACTION_GRANT_RUNNING_ALL) {
            lstrcpyA(message, "Everyone already likes running, or has full Likes slots. No tech points have been deducted.");
        } else if (action == ACTION_GRANT_MASTERY_ALL) {
            lstrcpyA(message, "Everyone has already mastered their skills. No tech points have been deducted.");
        } else if (action == ACTION_SET_AGE_18_ALL) {
            lstrcpyA(message, "Everyone is already exactly 18. No tech points have been deducted.");
        } else if (action == ACTION_COMPLETE_COLLECTIONS) {
            lstrcpyA(message, "All collectibles are already found. No tech points have been deducted.");
        } else if (action == ACTION_RESET_COLLECTIONS) {
            lstrcpyA(message, "The collections are already cleared. No tech points have been deducted.");
        } else {
            lstrcpyA(message, "No changes were needed. No tech points have been deducted.");
        }
        break;
    case RESULT_INVALID:
        lstrcpyA(message, "No valid living Believer is selected.\r\nNo tech points have been deducted.");
        break;
    case RESULT_INSUFFICIENT:
        lstrcpyA(message, "Not enough tech points.");
        break;
    case RESULT_CANCELLED:
        wsprintfA(message, "%s was canceled.\r\nNo tech points have been deducted.", name);
        break;
    case RESULT_RECHECK:
        lstrcpyA(message, "The selected Villager, village snapshot, or tech-point balance changed during confirmation.\r\nNo tech points have been deducted.");
        break;
    case RESULT_RETAINED:
        lstrcpyA(message, "The action could not be fully verified after native writes began. Earlier verified effects may remain.\r\nNo tech points have been deducted.");
        break;
    case RESULT_CHARGE_UNKNOWN:
        lstrcpyA(message, "The action effects were verified, but the final tech-point balance did not match the exact expected deduction. The charge outcome is unknown.");
        break;
    case RESULT_NO_SLOT:
        lstrcpyA(message, "This villager already has full Likes slots. Running can not be added.");
        break;
    case RESULT_INVALID_SKILL:
        lstrcpyA(message, "Full Mastery cannot be applied because a skill is NaN, infinite, negative, or outside 0..100.\r\nNo tech points have been deducted.");
        break;
    case RESULT_UNAVAILABLE:
        lstrcpyA(message, "This VV5 native action remains unavailable.\r\nNo tech points have been deducted.");
        break;
    case RESULT_REMOVED:
        wsprintfA(message, "%s was removed. No refund was issued.", name);
        break;
    case RESULT_PURCHASED:
        wsprintfA(message, "%s completed.", name);
        break;
    case RESULT_UNSUPPORTED_SICKNESS:
        lstrcpyA(message, "Full Heal / Cure All is unavailable because an eligible Villager has sickness type 12, whose additional native effects are not yet implemented.\r\nNo tech points have been deducted.");
        break;
    case RESULT_RUNNING_DISLIKE_CLEARED:
        lstrcpyA(message, "This villager's Likes are full, so Running could not be added, but its Running dislike was removed. No tech points have been deducted.");
        break;
    case RESULT_APPEARANCE_UNCHANGED:
        lstrcpyA(message, "The appearance is unchanged. No tech points have been deducted.");
        break;
    default:
        lstrcpyA(message, "The action stopped without a verified charge.");
        break;
    }
    MessageBoxA(
        owner,
        message,
        action == ACTION_HEAL || action >= ACTION_TECH_BASE
            ? "Origins Upgrades"
            : "Villager Upgrades",
        MB_OK | (status == RESULT_SUCCESS || status == RESULT_PURCHASED || status == RESULT_REMOVED
            ? MB_ICONINFORMATION : MB_ICONWARNING)
    );
    return 0;
}
