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
   next to the game's own save: Documents\LDW\<exe-basename>\vvfp_masks.dat. Keyed
   by villager record index (positional + stable across reload). The sidecar is a
   SEPARATE file from the .ldw, so it can never corrupt a save. */
#define MASK_TABLE_BYTES 75

static HINSTANCE module_instance;
static HWND origins_owner;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1012,
    ID_CHECK_FIRST = 1100,
    STATE_VILLAGER = 0x10000
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
    ACTION_EQUAL_DIVISION_NO_PARENTING = 24
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
   Ensures the folder exists. Returns 1 on success, 0 on failure. */
static int build_mask_sidecar_path(char *out) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    char *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;   /* basename incl. ".exe" */
    dot = strrchr(base, '.');
    if (dot) {
        *dot = '\0';                /* strip the extension */
    }
    /* ensure Documents\LDW and Documents\LDW\<base> exist (CreateDirectory is a
       no-op / harmless if they already do) */
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\vvfp_masks.dat", docs, base);
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
#define APPEARANCE_BODY_COUNT 29
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
        int row_count = villager_menu ? 5 : 13;
        int row;
        for (row = 0; row < row_count; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
            if ((lparam & (1 << row)) != 0) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
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
    default: return "1,000,000";
    }
}

/* Correct singular/plural for a villager count. */
static const char *vpl(unsigned int n) { return n == 1 ? "Villager" : "Villagers"; }
static const char *vpl_lc(unsigned int n) { return n == 1 ? "villager" : "villagers"; }

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
    wsprintfA(message, "Set %u Villagers' Job Preferences.", (unsigned int)total);
    for (p = 0; p < professions; ++p) {
        wsprintfA(line, "\r\n\r\n%s: %u Villagers (%u Male, %u Female).",
                  pro_name[p],
                  (unsigned int)(male_count[p] + female_count[p]),
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
