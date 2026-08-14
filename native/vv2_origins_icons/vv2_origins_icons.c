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

/* VV2 tech screen now carries 11 rows: the 9 shared Origins upgrades plus
   Complete all Collections (1009) and Reset all Collections (1010).  The shared
   ID_BUY_LAST (1008) only bounds the VV1 dialogs, so the VV2 proc uses its own
   upper bound instead of editing the shared enum. */
#define VV2_TECH_ROW_COUNT 11
#define ID_VV2_BUY_LAST    1010

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
        int row_count = villager_menu ? 5 : VV2_TECH_ROW_COUNT;
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
        if (command >= ID_BUY_FIRST && command <= ID_VV2_BUY_LAST) {
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

/* ---- Village-wide Grant Running / Grant Full Mastery, with counted reports.
   `base` is the certified record array (sub_44F4E0 result): 256 records, stride
   0xE48C, record 0 at base+0.  Field offsets match the whole-village helper:
   +0x30 active byte, +0x52C health, +0x558 special flag, +0x5F0 likes[62],
   +0x6E8 dislikes[62], +0x7E4 the five skills.  A slot holds -1 when empty and
   a positive preference id otherwise; running is id 38. ---- */
#define VV2_RECORD_STRIDE   0xE48C
#define VV2_RECORD_COUNT    256
#define VV2_ACTIVE_OFFSET   0x30
#define VV2_HEALTH_OFFSET   0x52C
#define VV2_SPECIAL_OFFSET  0x558
#define VV2_LIKES_OFFSET    0x5F0
#define VV2_DISLIKES_OFFSET 0x6E8
#define VV2_PREF_SLOTS      62
#define VV2_RUNNING_PREF    38
#define VV2_LIKE_CAP        3
#define VV2_SKILL0_OFFSET   0x7E4

static int vv2_record_eligible(const unsigned char *record) {
    if (record[VV2_ACTIVE_OFFSET] == 0) {
        return 0;
    }
    if (*(const int *)(record + VV2_HEALTH_OFFSET) <= 0) {
        return 0;
    }
    if (record[VV2_SPECIAL_OFFSET] != 0) {
        return 0;
    }
    return 1;
}

__declspec(dllexport) void __stdcall ApplyVV2RunningToAll(unsigned char *base) {
    int already_like = 0, full_likes = 0, granted = 0, removed_dislike = 0;
    int i, j;
    unsigned char *record = base;
    if (base == 0) {
        return;
    }
    for (i = 0; i < VV2_RECORD_COUNT; ++i, record += VV2_RECORD_STRIDE) {
        int *likes, *dislikes;
        int has_running = 0, occupied = 0, free_slot = -1;
        if (!vv2_record_eligible(record)) {
            continue;
        }
        dislikes = (int *)(record + VV2_DISLIKES_OFFSET);
        {
            int removed_here = 0;
            for (j = 0; j < VV2_PREF_SLOTS; ++j) {
                if (dislikes[j] == VV2_RUNNING_PREF) {
                    dislikes[j] = -1;
                    removed_here = 1;
                }
            }
            if (removed_here) {
                ++removed_dislike;
            }
        }
        likes = (int *)(record + VV2_LIKES_OFFSET);
        for (j = 0; j < VV2_PREF_SLOTS; ++j) {
            int value = likes[j];
            if (value == VV2_RUNNING_PREF) {
                has_running = 1;
            } else if (value == -1) {
                if (free_slot < 0) {
                    free_slot = j;
                }
            } else if (value > 0) {
                ++occupied;
            }
        }
        if (has_running) {
            ++already_like;
        } else if (occupied >= VV2_LIKE_CAP || free_slot < 0) {
            ++full_likes;
        } else {
            likes[free_slot] = VV2_RUNNING_PREF;
            ++granted;
        }
    }
    {
        char message[512];
        wsprintfA(
            message,
            "%d villagers already like running; skipped over.\r\n\r\n"
            "%d villagers already have 3 likes; skipped over.\r\n\r\n"
            "Granted Running to %d villagers.\r\n\r\n"
            "Removed Running Dislike from %d villagers.",
            already_like, full_likes, granted, removed_dislike
        );
        MessageBoxA(
            GetForegroundWindow(), message, "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
    }
}

__declspec(dllexport) void __stdcall ApplyVV2MasteryToAll(unsigned char *base) {
    int granted = 0, already_mastered = 0;
    int i;
    unsigned char *record = base;
    if (base == 0) {
        return;
    }
    for (i = 0; i < VV2_RECORD_COUNT; ++i, record += VV2_RECORD_STRIDE) {
        int *skills;
        if (!vv2_record_eligible(record)) {
            continue;
        }
        skills = (int *)(record + VV2_SKILL0_OFFSET);
        if (skills[0] == 100 && skills[1] == 100 && skills[2] == 100 &&
            skills[3] == 100 && skills[4] == 100) {
            ++already_mastered;
        } else {
            skills[0] = 100;
            skills[1] = 100;
            skills[2] = 100;
            skills[3] = 100;
            skills[4] = 100;
            ++granted;
        }
    }
    {
        char message[512];
        wsprintfA(
            message,
            "Granted Full Mastery to %d Villagers.\r\n\r\n"
            "%d villagers are already Fully Mastered. Skipped over.",
            granted, already_mastered
        );
        MessageBoxA(
            GetForegroundWindow(), message, "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
    }
}

/* ---- Complete (mode 9) / Reset (mode 10) all Collections.  `player` is the
   Tech menu's game object: 48 collectible found-flags at +0x2E720, and the
   per-group goal "pending" bytes at +0x20F..+0x213.  Complete fills the flags
   and enqueues the four group goals plus the master goal through the stock goal
   queue (sub_4257A0, __thiscall on the player object) exactly the way the stock
   deposit handler does; Reset clears the flags and re-arms those pending bytes
   so a later real completion can fire them again. ---- */
/* sub_4257A0 is __thiscall (player in ECX, message id + flag on the stack,
   callee-cleaned).  Call it from C via __fastcall with an ignored EDX slot: the
   player lands in ECX, the ignored value in EDX, and message id + flag spill to
   the stack exactly where the thiscall expects them. */
typedef int(__fastcall *vv2_fire_goal_t)(
    void *player, int edx_ignored, int message_id, int flag
);

__declspec(dllexport) void __stdcall ApplyVV2Collections(
    unsigned char *player,
    int mode
) {
    static const int goal_pending[5] = {0x20F, 0x210, 0x211, 0x212, 0x213};
    static const int goal_message[5] = {0x1DE, 0x1DF, 0x1E0, 0x1E1, 0x1E2};
    int i;
    if (player == 0) {
        return;
    }
    if (mode == 9) {
        for (i = 0; i < 48; ++i) {
            player[0x2E720 + i] = 1;
        }
        {
            vv2_fire_goal_t fire = (vv2_fire_goal_t)(UINT_PTR)0x004257A0;
            for (i = 0; i < 5; ++i) {
                if (player[goal_pending[i]] != 0) {
                    player[goal_pending[i]] = 0;
                    fire(player, 0, goal_message[i], 1);
                }
            }
        }
    } else {
        for (i = 0; i < 48; ++i) {
            player[0x2E720 + i] = 0;
        }
        for (i = 0; i < 5; ++i) {
            player[goal_pending[i]] = 1;
        }
    }
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
