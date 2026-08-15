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
    ID_BUY_LAST = 1010,
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

/* Full-screen approach mirrors VV1/VV2, which display correctly in the game's
   scaled full-screen mode: a plain modal owned by the game's foreground window,
   with no HWND_TOPMOST / SetForegroundWindow manipulation. Forcing the dialog
   topmost and stealing the foreground fights the game's borderless full-screen
   window and can leave the menu hidden or unresponsive, so VV_MB_FRONT is a
   no-op and dialogs are shown exactly as VV1/VV2 do. */
#define VV_MB_FRONT 0

/* OFFICIAL per-row purchase-confirm names + costs. Tech rows 6-8 (village-wide)
   use the payload's own OFFICIAL confirm and are skipped here. */
static const char *const g_tech_names[11] = {
    "Time Warp", "Island Event", "Barrel of Babies",
    "Tech Point Doubler", "Food Point Doubler", "Full Heal / Cure All",
    "", "", "", "Complete All Collections", "Reset All Collections"
};
static const char *const g_tech_costs[11] = {
    "50,000", "30,000", "75,000", "500,000", "500,000", "30,000", "", "", "",
    "1,000,000", "1,000,000"
};
static const char *const g_villager_names[5] = {
    "Grant Youth", "Grant Full Mastery", "Grant Running",
    "Set Age to 18", "Change Appearance"
};
static const char *const g_villager_costs[5] = {
    "50,000", "100,000", "40,000", "50,000", "5,000"
};
static int g_villager_menu;  /* set at WM_INITDIALOG; menus are modal/one-at-a-time */
/* The full state bitmask handed to the villager menu at open time (low bits:
   0=youth already youngest, 1=already fully mastered, 2=already likes Running,
   3=already 18, 10=no free Like slot). Used by WM_COMMAND to report the
   OFFICIAL no-change line when a would-do-nothing row is clicked. */
static int g_villager_mask;
/* The row/menu the player last acted on, captured at click time so the result
   popup (shown after the menu closes) can name the upgrade. */
static int g_last_row = -1;
static int g_last_villager;

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        g_villager_menu = villager_menu;
        g_villager_mask = (int)lparam;
        int village_wide_buy = (lparam & STATE_VILLAGE_WIDE_BUY) != 0;
        /* Village-wide tech menu carries 11 rows: the 6 base upgrades, the 3
           village-wide grants (rows 6-8), and Complete/Reset All Collections
           (rows 9-10). */
        int row_count = villager_menu
            ? 5
            : ((lparam & STATE_RUNNING_ONLY) != 0
                ? 7
                : ((lparam & STATE_VILLAGE_WIDE) != 0 ? 11 : 6));
        int row;
        for (row = 0; row < 11; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            if (villager_menu) {
                /* Every villager row stays a clickable "Buy". A row that would
                   change nothing is not greyed out; it opens and reports the
                   OFFICIAL no-change line (see WM_COMMAND) so the specified
                   wording actually reaches the player, and nothing is charged.
                   The check-mark still flags an already-satisfied row. */
                if ((lparam & (1 << row)) != 0
                    || (lparam & (1 << (8 + row))) != 0) {
                    ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                }
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                continue;
            }
            if ((lparam & (1 << row)) != 0) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                if (village_wide_buy && row >= 6) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                } else {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                }
            } else if ((8 + row) >= row_count && (8 + row) < 16
                       && (lparam & (1 << (8 + row))) != 0) {
                /* The (8+row) unavailable bit must stay below the STATE_* flags
                   at bits 16-19, or rows 8-10 would read a state flag (e.g.
                   STATE_VILLAGE_WIDE at bit 17) as an "Unavailable" marker. */
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
        }
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            int row = (int)(command - ID_BUY_FIRST);
            char label[16];
            label[0] = '\0';
            GetDlgItemTextA(window, command, label, (int)sizeof(label));
            /* A villager row that would change nothing reports the OFFICIAL
               no-change line and charges nothing, using the state bits the
               payload computed for this villager at open time. Running has two
               distinct cases: already-likes (checked first) vs. no free slot. */
            if (g_villager_menu) {
                const char *nochange = NULL;
                if (row == 0 && (g_villager_mask & (1 << 0)) != 0) {
                    nochange = "This villager is already full of youth. "
                               "No tech points have been deducted.";
                } else if (row == 1 && (g_villager_mask & (1 << 1)) != 0) {
                    nochange = "This villager is already fully mastered. "
                               "No tech points have been deducted.";
                } else if (row == 2 && (g_villager_mask & (1 << 2)) != 0) {
                    nochange = "This villager already likes Running. "
                               "No tech points have been deducted.";
                } else if (row == 2 && (g_villager_mask & (1 << (8 + 2))) != 0) {
                    nochange = "This villager already has full Likes slots. "
                               "Running can not be added.";
                } else if (row == 3 && (g_villager_mask & (1 << 3)) != 0) {
                    nochange = "No changes were needed. "
                               "No tech points have been deducted.";
                }
                if (nochange != NULL) {
                    MessageBoxA(window, nochange, "Villager Upgrades",
                                MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
                    return TRUE; /* Stay in the menu; nothing was purchased. */
                }
            }
            /* Only the "Buy" action is confirmed here; the doubler "Remove"
               toggle is reversible and not a purchase. The village-wide rows
               (tech 6/7/8) run their own OFFICIAL confirm from the payload
               after a dry run, so pass straight through for them -- but the
               Collections rows (9/10) take the standard confirm here. */
            if (lstrcmpA(label, "Buy") == 0
                && !(!g_villager_menu && row >= 6 && row <= 8)) {
                const char *name = g_villager_menu ? g_villager_names[row]
                                                   : g_tech_names[row];
                const char *cost = g_villager_menu ? g_villager_costs[row]
                                                   : g_tech_costs[row];
                char msg[256];
                wsprintfA(msg,
                    "Do you want to buy %s for %s tech points?\r\n"
                    "Press OK to confirm, or Cancel.", name, cost);
                if (MessageBoxA(window, msg,
                        g_villager_menu ? "Villager Upgrades" : "Origins Upgrades",
                        MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) != IDOK) {
                    return TRUE; /* Cancel: stay in the menu. */
                }
            }
            g_last_row = row;
            g_last_villager = g_villager_menu;
            EndDialog(window, (INT_PTR)row);
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
    char msg[192];
    const char *out = (text != NULL) ? text : "";
    /* The payload's Barrel capacity guard uses a short string to fit the full
       payload string table; render the OFFICIAL near-max wording here where DLL
       string space is free. Row-independent, so it always translates. */
    if (text != NULL
        && lstrcmpA(text,
               "The village population is already at maximum capacity.") == 0) {
        out = "Village population is close to its maximum. The Barrel of Babies "
              "needs room for 3 children. No tech points have been deducted.";
    } else if (text != NULL && g_last_row >= 0) {
        /* Translate the payload's generic result strings into the OFFICIAL
           per-upgrade wording, using the row the player just clicked. (Cure and
           the village-wide grants have their own result exports and never reach
           here.) */
        const char *const *names = g_last_villager ? g_villager_names
                                                   : g_tech_names;
        int nmax = g_last_villager ? 5 : 9;
        if (g_last_row < nmax) {
            if (lstrcmpA(text, "Purchased.") == 0) {
                if (g_last_villager && g_last_row == 4) {
                    return 0;  /* Change Appearance shows no result box */
                }
                wsprintfA(msg, "%s completed.", names[g_last_row]);
                out = msg;
            } else if (lstrcmpA(text, "Removed.") == 0) {
                wsprintfA(msg, "%s was removed. No refund was issued.",
                          names[g_last_row]);
                out = msg;
            }
        }
    }
    MessageBoxA(
        GetForegroundWindow(),
        out,
        title != NULL ? title : "Origins Upgrades",
        MB_OK | VV_MB_FRONT
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
            MB_OK | VV_MB_FRONT
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

/* ---- Complete / Reset All Collections (VV4 collectible + goal system) ----
   Reverse-engineered from the native collect handler at 0x4144xx (verified
   live with Cheat Engine): the 48 collectible found-flags are the contiguous
   dwords 0x4CC918..0x4CC9D4 (Fish Scales, Lab Pieces, Mausoleum, Wind Flutes;
   found == non-zero). Each collection's TROPHY only latches through the game's
   own goal machinery, so we drive it exactly as a natural final collect does:
   enqueue each collection goal id through the native goal writer 0x44B890
   (thiscall on the goal manager 0x4DACE0), which the game drains on the next
   tick and shows the trophy. Goal ids: Fish 0x302, Lab 0x303, Mausoleum 0x304,
   Wind Flute 0x305, master "All Collections Complete!" 0x306. Reset clears the
   flags and zeroes those five 0x20-byte goal records; the shared difficulty-
   scaled score stats and one-time rewards are left untouched (not collection-
   exclusive / not reversible), so Reset undoes exactly what Complete did. */
#define VV4_COLL_FLAG_BASE   0x4CC918u   /* found-flag for item index 0x46 */
#define VV4_COLL_FLAG_COUNT  48
#define VV4_GOAL_MANAGER     0x4DACE0u
#define VV4_GOAL_RECORD(id)  (VV4_GOAL_MANAGER + (unsigned)((id) - 0x2AA) * 0x20u)

static const int VV4_COLLECTION_GOALS[5] = { 0x302, 0x303, 0x304, 0x305, 0x306 };

/* The Trophies-screen "N of 12" progress is a native statistic, not the
   found-flags: the collect handler increments a per-collection stat for each
   new find via 0x412F90 (ECX = stat manager 0x4CBB98). Records are 12 bytes at
   [0x4CBB98 + id*12] = { byte0 complete-flag, +4 value }, and the writer latches
   the trophy when the value reaches its threshold. Fish Scales 0xE, Lab 0x11,
   Mausoleum 0xF, Wind Flutes 0x10 (indexed by collection = flag_index / 12). */
#define VV4_STAT_MANAGER     0x4CBB98u
#define VV4_STAT_RECORD(id)  (VV4_STAT_MANAGER + (unsigned)(id) * 12u)
static const int VV4_COLLECTION_STATS[4] = { 0xE, 0x11, 0xF, 0x10 };

/* Enqueue one goal through the native writer 0x44B890 (thiscall: this in ECX,
   three stack args, callee-cleaned via ret 0xC). Inline asm keeps the exact
   calling convention without a __thiscall typedef the C compiler rejects. */
static void vv4_enqueue_goal(int id) {
    void *mgr = (void *)(UINT_PTR)VV4_GOAL_MANAGER;
    __asm {
        push 0
        push 0
        mov  eax, id
        push eax
        mov  ecx, mgr
        mov  eax, 0x44B890
        call eax
    }
}

/* Add `amount` to statistic `id` via the native writer 0x412F90 (thiscall:
   this in ECX = stat manager, two stack args id/amount, ret 8). Reaching the
   stat's threshold latches its trophy, exactly as a real new find does. */
static void vv4_stat_add(int id, int amount) {
    void *mgr = (void *)(UINT_PTR)VV4_STAT_MANAGER;
    __asm {
        mov  eax, amount
        push eax
        mov  eax, id
        push eax
        mov  ecx, mgr
        mov  eax, 0x412F90
        call eax
    }
}

/* Returns the number of collectibles newly marked found (0 => everything was
   already complete, so the caller can report no-change and refund the charge). */
__declspec(dllexport) int __stdcall ApplyVV4CompleteCollections(void) {
    unsigned int *flags = (unsigned int *)(UINT_PTR)VV4_COLL_FLAG_BASE;
    int i, newly = 0;
    for (i = 0; i < VV4_COLL_FLAG_COUNT; ++i) {
        if (flags[i] == 0) {
            flags[i] = 1;
            /* Drive the same progress stat a real new find fires, so the
               Trophies screen reaches N-of-12 and latches (found-flags alone
               update the Collections screen but never the trophy). */
            vv4_stat_add(VV4_COLLECTION_STATS[i / 12], 1);
            ++newly;
        }
    }
    if (newly == 0) {
        /* Everything was already found: no-change, no charge (payload refunds
           on a 0 return). */
        MessageBoxA(GetForegroundWindow(),
            "All collectibles are already found. No tech points have been "
            "deducted.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
        return 0;
    }
    /* Fire every collection trophy plus the master; the writer is idempotent
       (it skips a goal whose record is already latched), so it is safe even for
       collections that were already complete. */
    for (i = 0; i < 5; ++i) {
        vv4_enqueue_goal(VV4_COLLECTION_GOALS[i]);
    }
    {
        char msg[160];
        wsprintfA(msg,
            "Marked all %d collectibles as found and triggered %d collection goals.",
            VV4_COLL_FLAG_COUNT, 5);
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    }
    return newly;
}

/* Returns the number of collectibles cleared (0 => nothing was collected). */
__declspec(dllexport) int __stdcall ApplyVV4ResetCollections(void) {
    unsigned int *flags = (unsigned int *)(UINT_PTR)VV4_COLL_FLAG_BASE;
    int i, cleared = 0;
    for (i = 0; i < VV4_COLL_FLAG_COUNT; ++i) {
        if (flags[i] != 0) { flags[i] = 0; ++cleared; }
    }
    if (cleared == 0) {
        /* Nothing was collected: no-change, no charge (payload refunds on 0). */
        MessageBoxA(GetForegroundWindow(),
            "The collections are already cleared. No tech points have been "
            "deducted.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
        return 0;
    }
    /* Mark each collection goal/trophy incomplete again by zeroing its record. */
    for (i = 0; i < 5; ++i) {
        unsigned char *rec =
            (unsigned char *)(UINT_PTR)VV4_GOAL_RECORD(VV4_COLLECTION_GOALS[i]);
        int j;
        for (j = 0; j < 0x20; ++j) { rec[j] = 0; }
    }
    /* Reset the four "N of 12" progress stats (value + latched flag) so the
       Trophies screen shows the collections incomplete again, plus the master
       "collections completed" counter (stat 0x12) that the native latch
       (0x412F10) bumps once per completed collection -- otherwise the "Master
       Collector - 4 of 4" trophy stays complete after a reset. */
    for (i = 0; i < 4; ++i) {
        unsigned char *rec =
            (unsigned char *)(UINT_PTR)VV4_STAT_RECORD(VV4_COLLECTION_STATS[i]);
        int j;
        for (j = 0; j < 12; ++j) { rec[j] = 0; }
    }
    {
        unsigned char *master = (unsigned char *)(UINT_PTR)VV4_STAT_RECORD(0x12);
        int j;
        for (j = 0; j < 12; ++j) { master[j] = 0; }
    }
    {
        char msg[96];
        wsprintfA(msg, "Cleared all %d collectibles.", VV4_COLL_FLAG_COUNT);
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    }
    return cleared;
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

/* ---- Village-wide dry-run counting (for VV5-task9-style confirms) ---- */
#define VV_RECORD_BASE       0x50E5AC
#define VV_RECORD_STRIDE     0x2E3C
#define VV_RECORD_COUNT_ADDR 0x42001C   /* record-array capacity (150) */
#define VV_ACTIVE_OFFSET     0x1CC4
#define VV_DEAD_OFFSET       0x1CC7
#define VV_HEALTH_OFFSET     0x1C40
#define VVW_LIKES_OFFSET     0x1E60
#define VVW_DISLIKES_OFFSET  0x1E6C
#define VV_SKILL0_OFFSET     0x1C5C
#define VV_DISPLAY_AGE_OFF   0x1B8C
#define VV_RUNNING_PREF      38
#define VV_LIKE_SLOTS        3
#define VV_SKILL_COUNT       5
#define VV_MASTER_VALUE      0x42C80000  /* float 100.0 */
#define VV_AGE_18            360         /* 20 displayed units per year */

static int vv_record_total(void) { return *(int *)VV_RECORD_COUNT_ADDR; }
static unsigned char *vv_record(int i) {
    return (unsigned char *)(VV_RECORD_BASE + (unsigned)i * VV_RECORD_STRIDE);
}
static int vv_eligible(const unsigned char *r) {
    return r[VV_ACTIVE_OFFSET] != 0 && r[VV_DEAD_OFFSET] == 0
        && *(const int *)(r + VV_HEALTH_OFFSET) > 0;
}

/* Dry-run counts for the current village-wide action, computed in the confirm
   and reused in the result. Valid only within one confirm->apply->result
   sequence, which is modal so village state cannot change between them. */
static int vw_granted, vw_already, vw_full, vw_removed;

static const char *vv_villagers(int n) { return n == 1 ? "Villager" : "Villagers"; }

/* Running: classify every eligible villager into granted / already-liking /
   full-slots, and count how many of the granted ones also had a Running
   dislike that will be removed. */
static void vv_scan_running(void) {
    int total = vv_record_total(), i;
    vw_granted = vw_already = vw_full = vw_removed = 0;
    for (i = 0; i < total; ++i) {
        const unsigned char *r = vv_record(i);
        const int *likes;
        int s, has_run = 0, free_slot = 0;
        if (!vv_eligible(r)) continue;
        likes = (const int *)(r + VVW_LIKES_OFFSET);
        for (s = 0; s < VV_LIKE_SLOTS; ++s) {
            if (likes[s] == VV_RUNNING_PREF) has_run = 1;
            else if (likes[s] == -1) free_slot = 1;
        }
        if (has_run) { ++vw_already; continue; }
        if (!free_slot) { ++vw_full; continue; }
        ++vw_granted;
        {
            const int *dis = (const int *)(r + VVW_DISLIKES_OFFSET);
            for (s = 0; s < VV_LIKE_SLOTS; ++s) {
                if (dis[s] == VV_RUNNING_PREF) { ++vw_removed; break; }
            }
        }
    }
}

/* Mastery: eligible villagers with any skill below 100 are mastered; the rest
   are already fully mastered. */
static void vv_scan_mastery(void) {
    int total = vv_record_total(), i;
    vw_granted = vw_already = 0;
    for (i = 0; i < total; ++i) {
        const unsigned char *r = vv_record(i);
        const int *sk;
        int s, full = 1;
        if (!vv_eligible(r)) continue;
        sk = (const int *)(r + VV_SKILL0_OFFSET);
        for (s = 0; s < VV_SKILL_COUNT; ++s) {
            if (sk[s] != (int)VV_MASTER_VALUE) { full = 0; break; }
        }
        if (full) ++vw_already; else ++vw_granted;
    }
}

/* Age: how many eligible villagers are not already exactly 18 (360 units). */
static int vv_count_age18(void) {
    int total = vv_record_total(), i, n = 0;
    for (i = 0; i < total; ++i) {
        const unsigned char *r = vv_record(i);
        if (!vv_eligible(r)) continue;
        if (*(const int *)(r + VV_DISPLAY_AGE_OFF) != VV_AGE_18) ++n;
    }
    return n;
}

/* Confirmation shown before charging a village-wide upgrade (OFFICIAL wording).
   Dry-runs first: if nothing would change, report it with no charge and return
   0; otherwise show "Do you want to buy ... ?" and return 1 only on OK.
   Commands not yet converted return 1 (proceed with the old flow). */
__declspec(dllexport) int __stdcall ConfirmOriginsVillageWide(int command) {
    if (command == 6) {
        vv_scan_running();
        if (vw_granted == 0) {
            MessageBoxA(GetForegroundWindow(),
                "Everyone already likes running, or has full Likes slots. "
                "No tech points have been deducted.",
                "Origins Upgrades", MB_OK | MB_ICONWARNING | VV_MB_FRONT);
            return 0;
        }
        return MessageBoxA(GetForegroundWindow(),
            "Do you want to buy Grant Running to All Villagers for 1,000,000 "
            "tech points?\r\nPress OK to confirm, or Cancel.",
            "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) == IDOK;
    }
    if (command == 7) {
        vv_scan_mastery();
        if (vw_granted == 0) {
            MessageBoxA(GetForegroundWindow(),
                "Everyone has already mastered their skills. "
                "No tech points have been deducted.",
                "Origins Upgrades", MB_OK | MB_ICONWARNING | VV_MB_FRONT);
            return 0;
        }
        return MessageBoxA(GetForegroundWindow(),
            "Do you want to buy Grant Full Mastery to All Villagers for "
            "1,000,000 tech points?\r\nPress OK to confirm, or Cancel.",
            "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) == IDOK;
    }
    if (command == 8) {
        if (vv_count_age18() == 0) {
            MessageBoxA(GetForegroundWindow(),
                "Everyone is already 18. No tech points have been deducted.",
                "Origins Upgrades", MB_OK | MB_ICONWARNING | VV_MB_FRONT);
            return 0;
        }
        return MessageBoxA(GetForegroundWindow(),
            "Do you want to buy Set All Villagers to 18 for 1,000,000 tech "
            "points?\r\nPress OK to confirm, or Cancel.",
            "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) == IDOK;
    }
    return 1;
}

/* Counted result (OFFICIAL wording), using the stored dry-run counts. */
__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult(
    int command,
    int granted,
    int already_running_skipped,
    int removed_running_dislike
) {
    char msg[512], line[128];
    (void)granted;
    (void)already_running_skipped;
    (void)removed_running_dislike;
    if (command == 6) {
        wsprintfA(msg, "Granted Running to %d %s.",
                  vw_granted, vv_villagers(vw_granted));
        if (vw_removed) {
            wsprintfA(line, "\r\n\r\nRemoved a Running dislike from %d %s.",
                      vw_removed, vv_villagers(vw_removed));
            lstrcatA(msg, line);
        }
        if (vw_already) {
            wsprintfA(line, "\r\n\r\nSkipped %d %s: already like Running.",
                      vw_already, vv_villagers(vw_already));
            lstrcatA(msg, line);
        }
        if (vw_full) {
            wsprintfA(line, "\r\n\r\nSkipped %d %s: already have 3 likes.",
                      vw_full, vv_villagers(vw_full));
            lstrcatA(msg, line);
        }
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    } else if (command == 7) {
        wsprintfA(msg, "Granted Full Mastery to %d %s.",
                  vw_granted, vv_villagers(vw_granted));
        if (vw_already) {
            wsprintfA(line, "\r\n\r\nSkipped %d %s: already fully mastered.",
                      vw_already, vv_villagers(vw_already));
            lstrcatA(msg, line);
        }
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    } else if (command == 8) {
        MessageBoxA(GetForegroundWindow(),
            "Set All Villagers to 18 completed.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
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
        MB_OK | MB_ICONINFORMATION | VV_MB_FRONT
    );
    return 0;
}
