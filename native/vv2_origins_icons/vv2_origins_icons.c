#define VV_AGE_OFFSET 0x530
#define VV_SKILL_FARMING_OFFSET 0x7E4
#define VV_SKILL_BUILDING_OFFSET 0x7E8
#define VV_SKILL_RESEARCH_OFFSET 0x7EC
#define VV_SKILL_HEALING_OFFSET 0x7F0
#define VV_SKILL_PARENTING_OFFSET 0x7F4
#define VV_LIKES_OFFSET 0x5F0
#define VV_DISLIKES_OFFSET 0x6E8
#define VV_LIKE_SLOT_COUNT 62
#define VV_ALREADY_LIKES_TEXT "Already 62 likes."
#include "../vv1_origins_icons/vv1_origins_icons.c"

/* ---------- VV2 self-contained upgrade menus + Change Appearance ----------
   VV2 uses its own dialog resources (211 tech, 212 villager, 213 Change
   Appearance) and its own dialog procs/exports so nothing here touches the
   shared VV1 dialogs, symbols, or resource IDs. The shared enums (ID_BUY_FIRST,
   ID_CHECK_FIRST, STATE_*) come from the included base source. */

#define IDD_VV2_TECH       211
#define IDD_VV2_VILLAGER   212
#define IDD_VV2_APPEARANCE 213

/* VV2 upgrade dialog: every row stays visible and buyable. The game re-checks
   the selected villager / village state at click time and no-ops with a
   message (no charge) when there is nothing to do, so no row is hidden or
   disabled. The checkmark glyph is informational: it marks an already-
   satisfied row. */
static INT_PTR CALLBACK vv2_upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int village_wide_buy = (lparam & STATE_VILLAGE_WIDE_BUY) != 0;
        int row_count = villager_menu ? 5 : 9;
        int row;
        for (row = 0; row < 9; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            int satisfied = (lparam & (1 << row)) != 0;
            if (satisfied) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
            }
            if (!villager_menu && satisfied && !(village_wide_buy && row >= 6)) {
                /* Owned Tech/Food Doubler: offer the removal toggle. */
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
            } else {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
            }
            EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
        }
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            EndDialog(window, (INT_PTR)(command - ID_BUY_FIRST));
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowVV2UpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    int resource = villager_menu ? IDD_VV2_VILLAGER : IDD_VV2_TECH;
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        GetForegroundWindow(),
        vv2_upgrade_dialog,
        dialog_state
    );
}

/* Full Heal / Cure All result message. sick = villagers whose sickness was
   cleared; health = villagers restored to full health. When both are zero the
   caller charged nothing. */
__declspec(dllexport) void __stdcall ShowVV2CureResult(int sick, int health) {
    char message[256];
    if (sick == 0 && health == 0) {
        MessageBoxA(
            GetForegroundWindow(),
            "Everyone is at full health already. No villagers are sick. "
            "No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
        return;
    }
    wsprintfA(
        message,
        "Cured sickness from %d villagers.\r\n\r\n"
        "Restored %d villagers to full health.",
        sick, health
    );
    MessageBoxA(
        GetForegroundWindow(), message, "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION
    );
}

/* ---- Change Appearance chooser (213) ---- */

#define IDB_HEAD_M_YOUNG 3001
#define IDB_HEAD_M_OLD   3002
#define IDB_HEAD_F_YOUNG 3003
#define IDB_HEAD_F_OLD   3004
#define IDB_BODY_M       3011
#define IDB_BODY_F       3012
#define IDC_BODY_PREVIEW 3101
#define IDC_HEAD_PREVIEW 3102
#define IDC_BODY_PREV    3103
#define IDC_BODY_NEXT    3104
#define IDC_HEAD_PREV    3105
#define IDC_HEAD_NEXT    3106
#define VV2_APPEARANCE_COUNT 30
#define VV2_APPEARANCE_CELL_W 40
#define VV2_APPEARANCE_CELL_H 65

static int vv2_appearance_sex;   /* 0 = male, 1 = female */
static int vv2_appearance_old;   /* 0 = young head atlas, 1 = old head atlas */
static int vv2_appearance_head;
static int vv2_appearance_body;

static int vv2_appearance_head_bitmap(void) {
    if (vv2_appearance_sex) {
        return vv2_appearance_old ? IDB_HEAD_F_OLD : IDB_HEAD_F_YOUNG;
    }
    return vv2_appearance_old ? IDB_HEAD_M_OLD : IDB_HEAD_M_YOUNG;
}

static int vv2_appearance_body_bitmap(void) {
    return vv2_appearance_sex ? IDB_BODY_F : IDB_BODY_M;
}

static void vv2_appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
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

    scale_x = (double)width / VV2_APPEARANCE_CELL_W;
    scale_y = (double)height / VV2_APPEARANCE_CELL_H;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(VV2_APPEARANCE_CELL_W * scale);
    draw_h = (int)(VV2_APPEARANCE_CELL_H * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, index * VV2_APPEARANCE_CELL_W, 0,
        VV2_APPEARANCE_CELL_W, VV2_APPEARANCE_CELL_H, SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void vv2_appearance_repaint(HWND window, int control) {
    InvalidateRect(GetDlgItem(window, control), NULL, TRUE);
}

static INT_PTR CALLBACK vv2_appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_BODY_PREVIEW) {
            vv2_appearance_draw(item, vv2_appearance_body_bitmap(), vv2_appearance_body);
            return TRUE;
        }
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            vv2_appearance_draw(item, vv2_appearance_head_bitmap(), vv2_appearance_head);
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == IDC_BODY_PREV) {
            vv2_appearance_body = (vv2_appearance_body + VV2_APPEARANCE_COUNT - 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_BODY_NEXT) {
            vv2_appearance_body = (vv2_appearance_body + 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_PREV) {
            vv2_appearance_head = (vv2_appearance_head + VV2_APPEARANCE_COUNT - 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_NEXT) {
            vv2_appearance_head = (vv2_appearance_head + 1) % VV2_APPEARANCE_COUNT;
            vv2_appearance_repaint(window, IDC_HEAD_PREVIEW);
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

/* Reports the chosen head/body indices back to the caller; the native handler
   owns eligibility, the 5,000-tech charge, and the record writes, so the DLL
   never touches save data. */
__declspec(dllexport) int __stdcall ShowVV2AppearanceChooser(
    int sex,
    int age,
    int *head,
    int *body
) {
    INT_PTR result;
    /* VV2 stores sex as 1 (male) or 2 (female); the stock renderer branches on
       `sex == 1` (0x4456A3). Match it: sex 1 -> male atlas (0), else female (1). */
    vv2_appearance_sex = (sex == 1) ? 0 : 1;
    vv2_appearance_old = age >= 1100 ? 1 : 0;
    vv2_appearance_head = (head && *head >= 0 && *head < VV2_APPEARANCE_COUNT) ? *head : 0;
    vv2_appearance_body = (body && *body >= 0 && *body < VV2_APPEARANCE_COUNT) ? *body : 0;

    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_VV2_APPEARANCE),
        GetForegroundWindow(),
        vv2_appearance_dialog,
        0
    );
    if (result == 1) {
        if (head) {
            *head = vv2_appearance_head;
        }
        if (body) {
            *body = vv2_appearance_body;
        }
        return 1;
    }
    return 0;
}
