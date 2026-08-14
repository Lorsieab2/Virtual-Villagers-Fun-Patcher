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

/* ---------- VV2 Change Appearance chooser ----------
   A modal picker that shows the selected villager's body and head cropped
   from the stock game art (embedded as build-time BMP strips) with left/right
   arrows for each. It only reports the chosen head/body indices back to the
   caller; the native handler performs eligibility, the 5,000-tech charge, and
   the record writes on OK, so this DLL never touches save data. */

#define IDD_APPEARANCE   203
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
#define APPEARANCE_COUNT 30
#define APPEARANCE_CELL_W 40
#define APPEARANCE_CELL_H 65

static int appearance_sex;   /* 0 = male, 1 = female */
static int appearance_old;   /* 0 = young head atlas, 1 = old head atlas */
static int appearance_head;
static int appearance_body;

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
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == IDC_BODY_PREV) {
            appearance_body = (appearance_body + APPEARANCE_COUNT - 1) % APPEARANCE_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_BODY_NEXT) {
            appearance_body = (appearance_body + 1) % APPEARANCE_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_PREV) {
            appearance_head = (appearance_head + APPEARANCE_COUNT - 1) % APPEARANCE_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_NEXT) {
            appearance_head = (appearance_head + 1) % APPEARANCE_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
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
    int *body
) {
    INT_PTR result;
    appearance_sex = sex ? 1 : 0;
    appearance_old = age >= 1100 ? 1 : 0;
    appearance_head = (head && *head >= 0 && *head < APPEARANCE_COUNT) ? *head : 0;
    appearance_body = (body && *body >= 0 && *body < APPEARANCE_COUNT) ? *body : 0;

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
        return 1;
    }
    return 0;
}
