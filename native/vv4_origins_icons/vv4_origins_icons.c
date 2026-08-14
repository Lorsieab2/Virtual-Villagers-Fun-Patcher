#define WIN32_LEAN_AND_MEAN
#include <windows.h>

/* Villager sex flag drives the male/female sprite atlas (render path
   0x45F5CF: cmp [record+0x1B90],0 / setne). Displayed age >= 1100 (55
   displayed years) uses the old-frame atlas page. */
#ifndef VV_SEX_OFFSET
#define VV_SEX_OFFSET 0x1B90
#endif
#ifndef VV_DISPLAY_AGE_OFFSET
#define VV_DISPLAY_AGE_OFFSET 0x1B8C
#endif
#ifndef VV_OLD_AGE_THRESHOLD
#define VV_OLD_AGE_THRESHOLD 1100
#endif
/* Atlas geometry: each sprite sheet is a grid of 40x65 cells. Heads have 8
   columns (directional frames); bodies have 16 columns and 10 outfits per
   page, split across pages 0..2 (male_bodies00/01/02 etc.). The picker shows
   one fixed viewing frame per field (playtest-chosen). */
#ifndef VV_CELL_W
#define VV_CELL_W 40
#endif
#ifndef VV_CELL_H
#define VV_CELL_H 65
#endif
#ifndef VV_HEAD_FRAME_COL
#define VV_HEAD_FRAME_COL 5
#endif
#ifndef VV_BODY_FRAME_COL
#define VV_BODY_FRAME_COL 8
#endif
#ifndef VV_BODY_ROWS_PER_PAGE
#define VV_BODY_ROWS_PER_PAGE 10
#endif

/* Minimal GDI+ flat-API surface (declared here to stay in C). Linked against
   gdiplus.lib; used only to load the PNG atlases and blit one cell. */
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
__declspec(dllimport) GpStatus __stdcall GdiplusStartup(
    ULONG_PTR *token, const struct GdiplusStartupInputC *input, void *output);
__declspec(dllimport) void __stdcall GdiplusShutdown(ULONG_PTR token);
__declspec(dllimport) GpStatus __stdcall GdipCreateBitmapFromFile(
    const WCHAR *filename, GpBitmap **bitmap);
__declspec(dllimport) GpStatus __stdcall GdipCreateFromHDC(
    HDC hdc, GpGraphics **graphics);
__declspec(dllimport) GpStatus __stdcall GdipDrawImageRectRectI(
    GpGraphics *graphics, GpImage *image,
    INT dstx, INT dsty, INT dstw, INT dsth,
    INT srcx, INT srcy, INT srcw, INT srch,
    INT srcUnit, void *imageAttributes, void *callback, void *callbackData);
__declspec(dllimport) GpStatus __stdcall GdipDeleteGraphics(GpGraphics *graphics);
__declspec(dllimport) GpStatus __stdcall GdipDisposeImage(GpImage *image);

static ULONG_PTR gdiplus_token = 0;

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
#define VV_HEAD_OFFSET 0x1BB8
#endif
#ifndef VV_CLOTHING_OFFSET
#define VV_CLOTHING_OFFSET 0x1BBC
#endif
/* VV4 head/body catalogs are gender-independent, unlike VV1's RNG(19)/RNG(20):
   the native clothing chooser (sub_419590) cycles the body field 0..28 for
   every villager (29 values), and both the male_heads and female_heads atlases
   carry exactly 30 rows (head 0..29). So no gender read is needed. */
#ifndef VV_HEAD_COUNT
#define VV_HEAD_COUNT 30
#endif
#ifndef VV_BODY_COUNT
#define VV_BODY_COUNT 29
#endif

static HINSTANCE module_instance;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    IDD_ORIGINS_APPEARANCE = 203,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1008,
    ID_CHECK_FIRST = 1100,
    ID_HEAD_LABEL = 2000,
    ID_HEAD_PREV = 2001,
    ID_HEAD_NEXT = 2002,
    ID_HEAD_PIC = 2003,
    ID_BODY_LABEL = 2010,
    ID_BODY_PREV = 2011,
    ID_BODY_NEXT = 2012,
    ID_BODY_PIC = 2013,
    STATE_VILLAGER = 0x10000,
    STATE_VILLAGE_WIDE = 0x20000,
    STATE_RUNNING_ONLY = 0x40000,
    STATE_VILLAGE_WIDE_BUY = 0x80000
};

/* Only one appearance picker can be open at a time (it is a modal dialog),
   so a single file-scope slot for its working state is sufficient -- this
   mirrors module_instance above, which is the same kind of single-instance
   global already used in this file. The tech-point balance check and
   charge live in the caller (the same reused code path every other
   Villager Upgrades row already charges through), not here: this dialog
   only ever previews and either keeps or reverts the head/body fields.

   VV4's head and body catalogs differ from each other and, unlike VV1, do
   NOT depend on gender: the native clothing chooser (sub_419590) cycles the
   body field over 0..28 for every villager (29 values; special value 29 is
   the chief outfit, outside the cycle), and both the male_heads and
   female_heads atlases carry exactly 30 rows (head 0..29). So head_count is
   30 and body_count is 29 for all villagers -- see VV_HEAD_COUNT/VV_BODY_COUNT
   above. Each field is stored as the 0-based atlas row index directly. */
static struct {
    unsigned char *villager;
    int original_head;
    int original_body;
    int head_count;
    int body_count;
    int sex;      /* 0 / non-zero -> female / male sprite atlas */
    int is_old;   /* displayed age >= VV_OLD_AGE_THRESHOLD */
} appearance_state;

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        struct GdiplusStartupInputC input;
        module_instance = instance;
        input.GdiplusVersion = 1;
        input.DebugEventCallback = NULL;
        input.SuppressBackgroundThread = FALSE;
        input.SuppressExternalCodecs = FALSE;
        GdiplusStartup(&gdiplus_token, &input, NULL);
    } else if (reason == DLL_PROCESS_DETACH) {
        if (gdiplus_token) {
            GdiplusShutdown(gdiplus_token);
            gdiplus_token = 0;
        }
    }
    return TRUE;
}

/* Blit one 40x65 atlas cell for the given head/body value into an
   owner-drawn control. head==1 selects the head sheet + column, otherwise
   the body sheet + column (and its per-page split). The atlas PNGs live in
   the game's Images folder; the villager re-renders live behind this dialog
   regardless, so a failed load simply shows nothing here. */
static void appearance_draw_cell(const DRAWITEMSTRUCT *dis, int is_head, int value) {
    WCHAR path[MAX_PATH];
    /* LDW engine convention (matches the VV2 companion): a non-zero sex field
       is female, zero is male. */
    const WCHAR *sex = appearance_state.sex ? L"female" : L"male";
    int age = appearance_state.is_old ? 1 : 0;
    int col, row, page;
    GpBitmap *bitmap = NULL;
    RECT rc = dis->rcItem;
    int dstw = rc.right - rc.left;
    int dsth = rc.bottom - rc.top;

    FillRect(dis->hDC, &rc, (HBRUSH)(COLOR_BTNFACE + 1));
    if (is_head) {
        col = VV_HEAD_FRAME_COL;
        row = value;
        wsprintfW(path, L"Images\\%ls_heads%d0.png", sex, age);
    } else {
        col = VV_BODY_FRAME_COL;
        page = value / VV_BODY_ROWS_PER_PAGE;
        row = value % VV_BODY_ROWS_PER_PAGE;
        wsprintfW(path, L"Images\\%ls_bodies%d%d.png", sex, age, page);
    }
    if (GdipCreateBitmapFromFile(path, &bitmap) == 0 && bitmap != NULL) {
        GpGraphics *graphics = NULL;
        if (GdipCreateFromHDC(dis->hDC, &graphics) == 0 && graphics != NULL) {
            /* Preserve the 40x65 cell aspect ratio: scale by the smaller of the
               two axis ratios and centre the result, so the sprite is never
               squashed to fill a differently-proportioned control. */
            double scale_x = (double)dstw / VV_CELL_W;
            double scale_y = (double)dsth / VV_CELL_H;
            double scale = scale_x < scale_y ? scale_x : scale_y;
            int draw_w = (int)(VV_CELL_W * scale);
            int draw_h = (int)(VV_CELL_H * scale);
            int draw_x = rc.left + (dstw - draw_w) / 2;
            int draw_y = rc.top + (dsth - draw_h) / 2;
            /* UnitPixel == 2 */
            GdipDrawImageRectRectI(
                graphics, bitmap,
                draw_x, draw_y, draw_w, draw_h,
                col * VV_CELL_W, row * VV_CELL_H, VV_CELL_W, VV_CELL_H,
                2, NULL, NULL, NULL);
            GdipDeleteGraphics(graphics);
        }
        GdipDisposeImage(bitmap);
    }
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
            } else if ((8 + row) >= row_count
                       && (lparam & (1 << (8 + row))) != 0) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
        }
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            /* Confirm every purchase. The doubler "Remove" toggle is reversible
               and is not a purchase, so only gate the "Buy" action. */
            char label[16];
            label[0] = '\0';
            GetDlgItemTextA(window, command, label, (int)sizeof(label));
            if (lstrcmpA(label, "Buy") == 0
                && MessageBoxA(
                       window,
                       "This upgrade makes permanent changes to your village. "
                       "Do you still want to purchase this?",
                       "Confirm Purchase",
                       MB_YESNO | MB_ICONWARNING) != IDYES) {
                return TRUE; /* No: do nothing, stay in the menu. */
            }
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
    if (message == WM_INITDIALOG) {
        /* appearance_state was already populated by ShowOriginsAppearancePicker
           before this dialog was created; the owner-drawn previews read the
           live head/body fields directly, so nothing else is needed here. */
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        const DRAWITEMSTRUCT *dis = (const DRAWITEMSTRUCT *)lparam;
        if (dis->CtlID == ID_HEAD_PIC) {
            appearance_draw_cell(dis, 1, *(int *)(appearance_state.villager + VV_HEAD_OFFSET));
            return TRUE;
        }
        if (dis->CtlID == ID_BODY_PIC) {
            appearance_draw_cell(dis, 0, *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET));
            return TRUE;
        }
        return FALSE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        int head_count = appearance_state.head_count;
        int body_count = appearance_state.body_count;
        int *head = (int *)(appearance_state.villager + VV_HEAD_OFFSET);
        int *body = (int *)(appearance_state.villager + VV_CLOTHING_OFFSET);
        if (command == ID_HEAD_PREV) {
            *head = (*head + head_count - 1) % head_count;
            InvalidateRect(GetDlgItem(window, ID_HEAD_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == ID_HEAD_NEXT) {
            *head = (*head + 1) % head_count;
            InvalidateRect(GetDlgItem(window, ID_HEAD_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == ID_BODY_PREV) {
            *body = (*body + body_count - 1) % body_count;
            InvalidateRect(GetDlgItem(window, ID_BODY_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == ID_BODY_NEXT) {
            *body = (*body + 1) % body_count;
            InvalidateRect(GetDlgItem(window, ID_BODY_PIC), NULL, TRUE);
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
    appearance_state.head_count = VV_HEAD_COUNT;
    appearance_state.body_count = VV_BODY_COUNT;
    appearance_state.sex = *(int *)(villager + VV_SEX_OFFSET);
    appearance_state.is_old =
        *(int *)(villager + VV_DISPLAY_AGE_OFFSET) >= VV_OLD_AGE_THRESHOLD;
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_ORIGINS_APPEARANCE),
        GetForegroundWindow(),
        appearance_dialog,
        (LPARAM)(UINT_PTR)villager
    );
}

/* Simple status popup for the payload's upgrade menus ("Purchased.",
   "Not enough tech points.", etc.). Owned by the game's foreground window so
   it reliably appears on top -- a NULL owner could render behind the game
   window right after the menu dialog closed and never be seen. */
__declspec(dllexport) int __stdcall ShowOriginsUpgradeMessage(
    const char *title,
    const char *text
) {
    MessageBoxA(
        GetForegroundWindow(),
        text != NULL ? text : "",
        title != NULL ? title : "Origins Upgrades",
        MB_OK
    );
    return 0;
}

/* Full Heal / Cure All result. The caller (the exact-build .shr cure cave)
   passes how many villagers had their sickness cleared and how many were
   restored to full health. Shows the exact two-line result, or -- when both
   are zero -- the all-healthy notice, and returns 1 when anything was done /
   0 when nothing was so the caller can refund the charge. */
__declspec(dllexport) int __stdcall ShowOriginsCureResult(
    int sickness_cleared,
    int health_restored
) {
    char text[256];
    if (sickness_cleared == 0 && health_restored == 0) {
        MessageBoxA(
            GetForegroundWindow(),
            "Everyone is at full health already. No villagers are sick. "
            "No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK
        );
        return 0;
    }
    wsprintfA(
        text,
        "Cured sickness from %d villagers.\r\n\r\n"
        "Restored %d villagers to full health.",
        sickness_cleared,
        health_restored
    );
    MessageBoxA(GetForegroundWindow(), text, "Origins Upgrades", MB_OK);
    return 1;
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
