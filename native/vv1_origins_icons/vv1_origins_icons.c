#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#ifndef VV_AGE_OFFSET
#define VV_AGE_OFFSET 0x348
#endif
#ifndef VV_SKILL_FARMING_OFFSET
#define VV_SKILL_FARMING_OFFSET 0x3BC
#endif
#ifndef VV_SKILL_BUILDING_OFFSET
#define VV_SKILL_BUILDING_OFFSET 0x3C0
#endif
#ifndef VV_SKILL_RESEARCH_OFFSET
#define VV_SKILL_RESEARCH_OFFSET 0x3C4
#endif
#ifndef VV_SKILL_HEALING_OFFSET
#define VV_SKILL_HEALING_OFFSET 0x3C8
#endif
#ifndef VV_SKILL_PARENTING_OFFSET
#define VV_SKILL_PARENTING_OFFSET 0x3CC
#endif
#ifndef VV_LIKES_OFFSET
#define VV_LIKES_OFFSET 0x398
#endif
#ifndef VV_DISLIKES_OFFSET
#define VV_DISLIKES_OFFSET 0x3A8
#endif
#ifndef VV_LIKE_SLOT_COUNT
#define VV_LIKE_SLOT_COUNT 4
#endif
#ifndef VV_ALREADY_LIKES_TEXT
#define VV_ALREADY_LIKES_TEXT "Already 4 likes."
#endif
#ifndef VV_HEAD_OFFSET
#define VV_HEAD_OFFSET 0x360
#endif
#ifndef VV_CLOTHING_OFFSET
#define VV_CLOTHING_OFFSET 0x364
#endif
#ifndef VV_GENDER_OFFSET
#define VV_GENDER_OFFSET 0x350
#endif
#ifndef VV_GENDER_MALE
#define VV_GENDER_MALE 1
#endif

static HINSTANCE module_instance;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    IDD_ORIGINS_APPEARANCE = 203,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1008,
    ID_CHECK_FIRST = 1100,
    /* IDC_HEAD_PREVIEW/IDC_BODY_PREVIEW: owner-draw STATIC controls that
       preview the real head/body sprite cropped from the stock game art
       (see appearance_draw below) -- these reuse the same control IDs the
       plain-text labels used before this dialog grew real art. */
    IDC_HEAD_PREVIEW = 2000,
    ID_HEAD_PREV = 2001,
    ID_HEAD_NEXT = 2002,
    IDC_BODY_PREVIEW = 2010,
    ID_BODY_PREV = 2011,
    ID_BODY_NEXT = 2012,
    IDB_HEAD_M = 3001,
    IDB_HEAD_F = 3002,
    IDB_BODY_M = 3011,
    IDB_BODY_F = 3012,
    STATE_VILLAGER = 0x10000,
    STATE_VILLAGE_WIDE = 0x20000,
    STATE_RUNNING_ONLY = 0x40000,
    STATE_VILLAGE_WIDE_BUY = 0x80000
};

/* Every strip built by scripts/build_vv1_appearance_bitmaps.py is a single
   40-wide column holding all 20 variant rows stacked vertically (one
   villager-record index per row), 65 pixels tall each -- exactly the cell
   geometry the stock exe's own sprite-sheet loader computes for these same
   source images (see that script's docstring for the decompiled proof). */
#define APPEARANCE_CELL_W 40
#define APPEARANCE_CELL_H 65

/* Only one appearance picker can be open at a time (it is a modal dialog),
   so a single file-scope slot for its working state is sufficient -- this
   mirrors module_instance above, which is the same kind of single-instance
   global already used in this file. The tech-point balance check and
   charge live in the caller (the same reused code path every other
   Villager Upgrades row already charges through), not here: this dialog
   only ever previews and either keeps or reverts the head/body fields.

   valid_count is not a fixed 20 for both fields: the villager-creation
   code assigns head and body their random starting value from RNG(19)
   for male villagers and RNG(20) for everyone else (confirmed by
   decompiling the exact-build initializer), so male villagers only have
   19 valid values (0-18) for both fields, not 20 -- cycling through 19
   for a male villager would write a value the stock renderer was never
   given a sprite for. */
static struct {
    unsigned char *villager;
    int original_head;
    int original_body;
    int valid_count;
    int male;
} appearance_state;

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
    }
    return TRUE;
}

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int village_wide_buy = (lparam & STATE_VILLAGE_WIDE_BUY) != 0;
        int row_count = villager_menu
            ? 5
            : ((lparam & STATE_RUNNING_ONLY) != 0
                ? 7
                : ((lparam & STATE_VILLAGE_WIDE) != 0 ? 9 : 6));
        int row;
        for (row = 0; row < 9; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            if ((lparam & (1 << row)) != 0) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                if (villager_menu) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Done");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                } else if (village_wide_buy && row >= 6) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                } else {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                }
            } else if ((lparam & (1 << (8 + row))) != 0) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
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

static int show_upgrade_menu(int villager_menu, int dialog_state) {
    int resource = villager_menu ? IDD_ORIGINS_VILLAGER : IDD_ORIGINS_TECH;
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        GetForegroundWindow(),
        upgrade_dialog,
        dialog_state
    );
}

/* Crops row `index` (one villager-record value = one 40x65 row) out of
   the strip for the current villager's sex and stretches it to fill the
   owner-draw control's actual rect, the same StretchBlt/COLORONCOLOR
   approach the stock renderer itself would use for an arbitrary preview
   size. */
static void appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
    RECT rc = item->rcItem;
    int width = rc.right - rc.left;
    int height = rc.bottom - rc.top;
    HBRUSH background = CreateSolidBrush(RGB(236, 236, 236));
    HBITMAP bitmap;
    HDC source;
    HBITMAP previous;

    FillRect(item->hDC, &rc, background);
    DeleteObject(background);

    bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bitmap_id));
    if (bitmap == NULL) {
        return;
    }
    source = CreateCompatibleDC(item->hDC);
    previous = (HBITMAP)SelectObject(source, bitmap);

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, rc.left, rc.top, width, height,
        source, 0, index * APPEARANCE_CELL_H, APPEARANCE_CELL_W, APPEARANCE_CELL_H,
        SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void appearance_repaint(HWND window, int control_id) {
    InvalidateRect(GetDlgItem(window, control_id), NULL, TRUE);
}

static void appearance_revert(void) {
    *(int *)(appearance_state.villager + VV_HEAD_OFFSET) = appearance_state.original_head;
    *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET) = appearance_state.original_body;
}

/* Writes each tentative value straight into the live villager record so
   the stock renderer (which already reads these exact fields every
   frame, the same field the F6 clothing-cycle cheat uses for body) shows
   the change immediately behind this dialog -- no separate preview
   rendering is built or needed here. Reverted on Cancel/close; kept on
   OK. The tech-point balance check and charge are the caller's job (the
   exact same charge code every other Villager Upgrades row already
   uses) -- this dialog never touches tech points, only the head/body
   fields, and returns 1 only when the player actually confirmed with
   OK. */
static INT_PTR CALLBACK appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        /* appearance_state was already populated by ShowOriginsAppearancePicker
           before this dialog was created; WM_DRAWITEM below paints the
           starting values on the dialog's own first paint, nothing to do
           here. */
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            appearance_draw(
                item,
                appearance_state.male ? IDB_HEAD_M : IDB_HEAD_F,
                *(int *)(appearance_state.villager + VV_HEAD_OFFSET)
            );
            return TRUE;
        }
        if (item->CtlID == IDC_BODY_PREVIEW) {
            appearance_draw(
                item,
                appearance_state.male ? IDB_BODY_M : IDB_BODY_F,
                *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET)
            );
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        int count = appearance_state.valid_count;
        int *head = (int *)(appearance_state.villager + VV_HEAD_OFFSET);
        int *body = (int *)(appearance_state.villager + VV_CLOTHING_OFFSET);
        if (command == ID_HEAD_PREV) {
            *head = (*head + count - 1) % count;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == ID_HEAD_NEXT) {
            *head = (*head + 1) % count;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == ID_BODY_PREV) {
            *body = (*body + count - 1) % count;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == ID_BODY_NEXT) {
            *body = (*body + 1) % count;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDOK) {
            EndDialog(window, 1);
            return TRUE;
        }
        if (command == IDCANCEL) {
            appearance_revert();
            EndDialog(window, 0);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        appearance_revert();
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowOriginsAppearancePicker(
    int villager_ptr
) {
    unsigned char *villager = (unsigned char *)(UINT_PTR)(unsigned int)villager_ptr;
    if (villager == NULL) {
        return 0;
    }
    appearance_state.villager = villager;
    appearance_state.original_head = *(int *)(villager + VV_HEAD_OFFSET);
    appearance_state.original_body = *(int *)(villager + VV_CLOTHING_OFFSET);
    appearance_state.male = *(int *)(villager + VV_GENDER_OFFSET) == VV_GENDER_MALE;
    appearance_state.valid_count = appearance_state.male ? 19 : 20;
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_ORIGINS_APPEARANCE),
        GetForegroundWindow(),
        appearance_dialog,
        (LPARAM)(UINT_PTR)villager
    );
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    return show_upgrade_menu(villager_menu, dialog_state);
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenu(
    int villager_menu,
    int state
) {
    int dialog_state = 0;
    if (villager_menu) {
        unsigned char *villager = (unsigned char *)(UINT_PTR)(unsigned int)state;
        int row;
        int running_like = 0;
        int running_dislike = 0;
        int available_like = 0;
        if (villager != NULL) {
            if (*(int *)(villager + VV_AGE_OFFSET) <= 100) {
                dialog_state |= 1 << 0;
            }
            if (*(int *)(villager + VV_SKILL_FARMING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_BUILDING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_RESEARCH_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_HEALING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_PARENTING_OFFSET) == 100) {
                dialog_state |= 1 << 1;
            }
            for (row = 0; row < VV_LIKE_SLOT_COUNT; ++row) {
                int like = *(int *)(villager + VV_LIKES_OFFSET + row * 4);
                if (like == 38) {
                    running_like = 1;
                } else if (like == -1) {
                    available_like = 1;
                }
                if (*(int *)(villager + VV_DISLIKES_OFFSET + row * 4) == 38) {
                    running_dislike = 1;
                }
            }
            if (running_like) {
                dialog_state |= 1 << 2;
            } else if (!available_like) {
                dialog_state |= 1 << (8 + 2);
            }
            if (*(int *)(villager + VV_AGE_OFFSET) == 360) {
                dialog_state |= 1 << 3;
            }
        }
    } else {
        if ((state & 1) != 0) {
            dialog_state |= 1 << 3;
        }
        if ((state & 2) != 0) {
            dialog_state |= 1 << 4;
        }
    }
    return show_upgrade_menu(villager_menu, dialog_state);
}

/* Shared confirmation prompt: every purchasable row on both the Tech
   screen (including its Village-Wide rows) and the Villager Details
   screen routes through this before any charge or change happens, so
   it takes no arguments and reports nothing beyond the player's choice
   -- the caller already knows which row it is asking about. */
__declspec(dllexport) int __stdcall ShowOriginsPermanentChangeConfirm(void) {
    int result = MessageBoxA(
        GetForegroundWindow(),
        "This upgrade makes permanent changes to your village. "
        "Do you still want to purchase this?",
        "Origins Upgrades",
        MB_YESNO | MB_ICONQUESTION
    );
    return result == IDYES ? 1 : 0;
}

/* Full Heal/Cure All Villagers: the .shr helper only calls this once it
   already knows at least one villager was sick or below full health (and
   has already charged for it), so this never needs its own "nothing
   happened" branch -- that message is a plain string shown directly by
   the helper without ever resolving this export. */
__declspec(dllexport) int __stdcall ShowOriginsCureResult(
    int sick_cured,
    int healed_restored
) {
    char message[128];
    wsprintfA(
        message,
        "Cured sickness from %d villagers.\r\nRestored %d villagers to full health.",
        sick_cured,
        healed_restored
    );
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION
    );
    return 0;
}

__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult(
    int command,
    int full_like_skipped,
    int already_running_skipped,
    int removed_running_dislike
) {
    char message[128];
    if (command == 6) {
        wsprintfA(
            message,
            "Skipped over %d villagers. Reason: " VV_ALREADY_LIKES_TEXT "\r\nskipped over %d villagers. Reason: already likes running",
            full_like_skipped,
            already_running_skipped
        );
        if (removed_running_dislike > 0) {
            char removal[64];
            wsprintfA(
                removal,
                "\r\nRemoved running dislike from %d villagers",
                removed_running_dislike
            );
            lstrcatA(message, removal);
        }
        MessageBoxA(
            GetForegroundWindow(),
            message,
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
    }
    return 0;
}

__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult20(
    int command,
    unsigned int granted,
    unsigned int already_like,
    unsigned int full_like,
    unsigned int removed_dislike
) {
    char message[256];
    char line[96];
    if (command != 6) {
        return 0;
    }
    wsprintfA(message, "Granted Running to %u villagers", granted);
    wsprintfA(
        line,
        "\r\nSkipped over %u villagers. Reason: already likes running",
        already_like
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\nSkipped over %u villagers. Reason: all like slots are occupied",
        full_like
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\nRemoved running dislike from %u villagers",
        removed_dislike
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION
    );
    return 0;
}
