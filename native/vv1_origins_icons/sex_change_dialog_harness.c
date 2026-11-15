/* Change Appearance's "Change sex..." button (native/shared/sex_change_ui.h) in A New Home and The Lost
   Children: the real dialog procedures and templates of "VVFP VV1 Origins Icons.dll" / "VVFP VV2 Origins
   Icons.dll", driven here.

   Compiled once per game with /DHARNESS_GAME=1 or 2: this file includes that game's Origins companion source
   UNCHANGED, and the game's own .rc is linked in, so the templates are the DLL's.  Stand-ins only for what
   needs the game: its save manager (none here, so no save slot: nothing is logged or written), the mask scratch
   A New Home reads at its fixed addresses (a zeroed block the harness is linked over), and the companions the
   windows ask for by name (none, or a Head Look stand-in for the "Head look" templates).

     <exe>            the checks: the real dialog procedure gets the button's own WM_COMMAND (and Undo changes,
                      the hair colours, OK, Cancel) through a scripted DialogBoxParamA, MessageBoxA answers Yes or
                      No; then each template is created (hidden) and the button measured: inside the window,
                      over no other control, its text fully inside it.  Exit 0 when every check passed.
     <exe> shot DIR   the screenshots: the real window shown, captured with PrintWindow, the button pressed, the
                      warning box captured, answered No, the window cancelled.  BMP files in DIR (the build
                      script makes the PNGs).  Nothing is changed anywhere. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "../shared/harness_redirect_documents.h"

#ifndef HARNESS_GAME
#error "build with /DHARNESS_GAME=1 or 2"
#endif

/* No save manager: the game's save slot reads 0, so the change writes no log and tells no owner's file. */
static const unsigned char *h_no_manager;
#define VV_GAME_SAVE_MANAGER_AT(game) ((const unsigned char *const volatile *)&h_no_manager)

static int h_real;                  /* the screenshots: the real windows */
static int h_answer = IDYES;        /* the stand-in box's answer to a Yes / No box */
static int h_boxes;
static char h_box_text[2048];
static UINT h_box_flags;
static INT_PTR h_end_result;
static const UINT *h_script;
static int h_script_len;
static int h_look_there;            /* a "VVFP Head Look.dll" stand-in: the "Head look" templates */

static int WINAPI h_MessageBoxA(HWND window, LPCSTR text, LPCSTR caption, UINT flags) {
    if (h_real) {
        return MessageBoxA(window, text, caption, flags);
    }
    if (caption == NULL || lstrcmpA(caption, "Change sex") != 0) {   /* VVFP_AX_CHANGE_SEX_TITLE */
        return IDOK;                /* the window's other boxes (the head genetics, the result): OK */
    }
    h_boxes++;
    lstrcpynA(h_box_text, text != NULL ? text : "", sizeof h_box_text);
    h_box_flags = flags;
    return (flags & 0xFu) == MB_YESNO ? h_answer : IDOK;
}

static BOOL WINAPI h_EndDialog(HWND window, INT_PTR result) {
    if (h_real) {
        return EndDialog(window, result);
    }
    h_end_result = result;
    return TRUE;
}

static BOOL WINAPI h_InvalidateRect(HWND window, const RECT *rect, BOOL erase) {
    return h_real ? InvalidateRect(window, rect, erase) : TRUE;
}

/* The real window, owned by nobody (never by another program's window); or the scripted presses. */
static INT_PTR WINAPI h_DialogBoxParamA(HINSTANCE instance, LPCSTR name, HWND owner, DLGPROC proc, LPARAM param) {
    int i;
    (void)owner;
    if (h_real) {
        return DialogBoxParamA(instance, name, NULL, proc, param);
    }
    h_end_result = -1;
    for (i = 0; i < h_script_len; ++i) {
        proc(NULL, WM_COMMAND, MAKEWPARAM(h_script[i], BN_CLICKED), 0);
    }
    return h_end_result;
}

#define H_HEAD_LOOK ((HMODULE)(UINT_PTR)0x20000)
static int __stdcall h_look_installed(int game) { return game == HARNESS_GAME; }
static int __stdcall h_look_get(int game, const void *record) { (void)game; (void)record; return 0; }
static int __stdcall h_look_set(int game, const void *record, int look) {
    (void)game; (void)record; (void)look;
    return 1;
}
static int __stdcall h_look_set_many(int game, const void *const *records, const int *looks, int count) {
    (void)game; (void)records; (void)looks; (void)count;
    return 1;
}

static HMODULE WINAPI h_GetModuleHandleA(LPCSTR name) {
    if (name == NULL) {
        return GetModuleHandleA(NULL);
    }
    if (h_look_there && lstrcmpiA(name, "VVFP Head Look.dll") == 0) {
        return H_HEAD_LOOK;
    }
    return NULL;                    /* no other companion is in this harness */
}

static FARPROC WINAPI h_GetProcAddress(HMODULE module, LPCSTR name) {
    if (module == H_HEAD_LOOK) {
        if (lstrcmpA(name, "VvfpHeadLookInstalled") == 0) return (FARPROC)h_look_installed;
        if (lstrcmpA(name, "VvfpHeadLookGet") == 0) return (FARPROC)h_look_get;
        if (lstrcmpA(name, "VvfpHeadLookSet") == 0) return (FARPROC)h_look_set;
        if (lstrcmpA(name, "VvfpHeadLookSetMany") == 0) return (FARPROC)h_look_set_many;
        return NULL;
    }
    return GetProcAddress(module, name);
}

#define MessageBoxA h_MessageBoxA
#define EndDialog h_EndDialog
#define InvalidateRect h_InvalidateRect
#define DialogBoxParamA h_DialogBoxParamA
#define GetModuleHandleA h_GetModuleHandleA
#define GetProcAddress h_GetProcAddress

#if HARNESS_GAME == 1
#include "vv1_origins_icons.c"
#elif HARNESS_GAME == 2
#include "../vv2_origins_icons/vv2_origins_icons.c"
#else
#error "HARNESS_GAME must be 1 or 2"
#endif

#undef MessageBoxA
#undef EndDialog
#undef InvalidateRect
#undef DialogBoxParamA
#undef GetModuleHandleA
#undef GetProcAddress

static int h_failures, h_checks;

static void h_check(int ok, const char *what) {
    h_checks++;
    if (!ok) {
        h_failures++;
        printf("FAIL game %d: %s\n", HARNESS_GAME, what);
    }
}

/* A New Home's mask scratch is read at its fixed addresses (0x491000..): the harness is linked fixed at
   0x200000 and this zeroed block lies over them (change_appearance_extras_harness.c's way). */
static unsigned char h_backing[0x600000];

static int h_game_memory(void) {
    unsigned int b = (unsigned int)(UINT_PTR)h_backing;
    return 0x00480000u >= b && 0x004C0000u <= b + sizeof h_backing;
}

/* ---- each game's villager and window ----------------------------------------------------------------- */

#if HARNESS_GAME == 1
#define H_STRIDE 0x3D8u
#define H_SEX 0x350u
#define H_PREGNANT 0x358u
#define H_NAME 0x370u
#define H_HEAD 0x360u
#define H_BODY 0x364u
#define H_MALE 1
#define H_FEMALE 2
#define H_TEMPLATE IDD_ORIGINS_APPEARANCE
#define H_TEMPLATE_LOOK IDD_ORIGINS_APPEARANCE_LOOK
#define H_GAME_NAME "VV1"
static unsigned char h_record[0x400];

static int h_open(void) {
    return ShowOriginsAppearancePicker((int)(UINT_PTR)h_record);
}

/* What the window shows by the sex: 1 for a man. */
static int h_window_male(void) {
    return appearance_state.male;
}

static int h_hair_ok(int colour, int head) {
    int k, male = *(int *)(h_record + H_SEX) == H_MALE;
    int n = male ? vv1_head_bucket_m_count[colour] : vv1_head_bucket_f_count[colour];
    for (k = 0; k < n; ++k) {
        if ((male ? vv1_head_bucket_m[colour][k] : vv1_head_bucket_f[colour][k]) == head) {
            return 1;
        }
    }
    return 0;
}
#else
#define H_STRIDE 0xE48Cu
#define H_SEX 0x538u
#define H_PREGNANT 0x540u
#define H_NAME 0x564u
#define H_HEAD 0x548u
#define H_BODY 0x54Cu
#define H_MALE 1
#define H_FEMALE 2
#define H_TEMPLATE IDD_VV2_APPEARANCE
#define H_TEMPLATE_LOOK IDD_VV2_APPEARANCE_LOOK
#define H_GAME_NAME "VV2"
static unsigned char *h_record, *h_player;

static int h_open(void) {
    if (!h_real) {
        vv2_mask_table_state = -1;      /* no .mtab here: no mask is read or written */
    }
    return ShowVV2AppearanceChooser(h_player, h_record, 0);
}

static int h_window_male(void) {
    return vv2_appearance_sex == 0;
}

static int h_hair_ok(int colour, int head) {
    int k, s = *(int *)(h_record + H_SEX) == H_MALE ? 0 : 1;
    for (k = 0; k < caf_hair_n[s][colour]; ++k) {
        if (caf_hair[s][colour][k] == head) {
            return 1;
        }
    }
    return 0;
}
#endif

#define H_SEX_NOW() (*(int *)(h_record + H_SEX))

/* A villager called `name` of `sex`, head 4 and body 5, nobody expecting. */
static void h_villager(const char *name, int sex) {
    memset(h_record, 0, H_STRIDE);
    lstrcpynA((char *)h_record + H_NAME, name, 20);
    *(int *)(h_record + H_SEX) = sex;
    *(int *)(h_record + H_HEAD) = 4;
    *(int *)(h_record + H_BODY) = 5;
#if HARNESS_GAME == 1
    *(int *)(h_record + VV_AGE_OFFSET) = 600;
#else
    *(int *)(h_record + VV_AGE_OFFSET) = 600;
    *(int *)(h_player + VV2_TECH_BALANCE_OFFSET) = 100000;
#endif
}

static int h_press(const UINT *script, int len, int answer) {
    h_script = script;
    h_script_len = len;
    h_answer = answer;
    h_boxes = 0;
    h_box_text[0] = 0;
    h_box_flags = 0;
    return h_open();
}

static INT_PTR CALLBACK h_quiet_proc(HWND w, UINT m, WPARAM wp, LPARAM lp);

static void h_checks_run(void) {
    int c, k;
    {
        static const UINT script[] = { VVFP_AX_CHANGE_SEX, IDOK };
        h_villager("Lani", H_FEMALE);
        h_press(script, 2, IDYES);
        h_check(H_SEX_NOW() == H_MALE, "Yes: the record's sex is the other one");
        h_check(h_window_male(), "Yes: the window draws and groups by the new sex");
        h_check(h_boxes == 1 && (h_box_flags & 0xFu) == MB_YESNO && (h_box_flags & MB_DEFBUTTON2) != 0,
                "Yes: one warning box, Yes or No, No the default");
        h_check(strstr(h_box_text, "Change Lani's sex to male?") != NULL
                && strstr(h_box_text, "Undo changes does not undo it") != NULL, "the warning names her and says so");
        h_check(*(int *)(h_record + H_HEAD) == 4 && *(int *)(h_record + H_BODY) == 5,
                "the same head and body rows");
#if HARNESS_GAME == 2
        h_check(*(int *)(h_player + VV2_TECH_BALANCE_OFFSET) == 100000, "the change alone is not charged");
#endif
    }
    {
        static const UINT script[] = { VVFP_AX_CHANGE_SEX, IDOK };
        h_villager("Lani", H_FEMALE);
        h_press(script, 2, IDNO);
        h_check(H_SEX_NOW() == H_FEMALE && !h_window_male() && h_boxes == 1, "No: nothing changes");
    }
    {
        static const UINT script[] = { VVFP_AX_CHANGE_SEX, VVFP_AX_UNDO, IDOK };
        h_villager("Kai", H_MALE);
        h_press(script, 3, IDYES);
        h_check(H_SEX_NOW() == H_FEMALE && !h_window_male(), "Undo changes does not change the sex back");
    }
    {
        static const UINT script[] = { VVFP_AX_CHANGE_SEX, IDCANCEL };
        h_villager("Kai", H_MALE);
        h_press(script, 2, IDYES);
        h_check(H_SEX_NOW() == H_FEMALE, "Cancel does not change the sex back (made at once)");
    }
    {
        static const UINT script[] = { VVFP_AX_CHANGE_SEX, VVFP_AX_CHANGE_SEX, IDOK };
        h_villager("Kai", H_MALE);
        h_press(script, 3, IDYES);
        h_check(H_SEX_NOW() == H_MALE && h_window_male(), "pressed again: changed back");
    }
    for (c = 0; c < 5; ++c) {
        for (k = 0; k < 6; ++k) {
            UINT script[3];
            script[0] = VVFP_AX_CHANGE_SEX;
            script[1] = (UINT)(VVFP_AX_HAIR_FIRST + c);
            script[2] = IDOK;
            h_villager("Kai", H_MALE);
            h_press(script, 3, IDYES);
            h_check(H_SEX_NOW() == H_FEMALE && h_hair_ok(c, *(int *)(h_record + H_HEAD)),
                    "after the change a hair colour gives a head of the new sex's colour group");
        }
    }
    {
        /* Carrying or nursing (the same field in every game): offered, the warning says they go on carrying;
           Yes changes the sex and the pregnancy fields stay exactly as they were. */
        static const UINT script[] = { VVFP_AX_CHANGE_SEX, IDOK };
        h_villager("Lani", H_FEMALE);
        *(int *)(h_record + H_PREGNANT) = 7;
        *(int *)(h_record + H_PREGNANT + 4u) = 2;
        h_press(script, 2, IDYES);
        h_check(H_SEX_NOW() == H_MALE && h_window_male(), "carrying: Yes changes the sex");
        h_check(h_boxes == 1 && (h_box_flags & 0xFu) == MB_YESNO
                && strstr(h_box_text, "Lani is carrying or nursing a baby. Lani goes on carrying, and stays the "
                                      "carrying parent") != NULL, "carrying: the warning says they go on carrying");
        h_check(*(int *)(h_record + H_PREGNANT) == 7 && *(int *)(h_record + H_PREGNANT + 4u) == 2,
                "carrying: the pregnancy fields are untouched");
        h_villager("Lani", H_FEMALE);
        *(int *)(h_record + H_PREGNANT) = 7;
        h_press(script, 2, IDNO);
        h_check(H_SEX_NOW() == H_FEMALE && *(int *)(h_record + H_PREGNANT) == 7, "carrying, No: nothing changes");
        h_villager("Lani", H_FEMALE);
        h_press(script, 2, IDNO);
        h_check(strstr(h_box_text, "goes on carrying") == NULL, "not carrying: no carrying sentence");
    }
#if HARNESS_GAME == 1
    {
        /* The Golden Child: never offered.  The button's own command does nothing and shows no box. */
        static const UINT script[] = { VVFP_AX_CHANGE_SEX, IDOK };
        HWND w;
        h_villager("Golden Child", H_MALE);
        *(int *)(h_record + 0x36C) = 0xC7;
        h_press(script, 2, IDYES);
        h_check(H_SEX_NOW() == H_MALE && h_boxes == 0, "the Golden Child: the button's command does nothing, no box");
        h_check(!vvfp_ax_change_sex_offered(1, h_record), "the Golden Child: not offered");
        /* The window's own code hides the button (appearance_offer_sex, called at WM_INITDIALOG). */
        for (k = 0; k < 2; ++k) {
            HWND button;
            w = CreateDialogParamA(module_instance, MAKEINTRESOURCEA(k ? H_TEMPLATE_LOOK : H_TEMPLATE), NULL,
                                   h_quiet_proc, 0);
            h_check(w != NULL, "the Golden Child: the template is there");
            if (w == NULL) {
                continue;
            }
            button = GetDlgItem(w, VVFP_AX_CHANGE_SEX);
            appearance_state.villager = h_record;
            appearance_offer_sex(w);
            h_check(button != NULL && !(GetWindowLongA(button, GWL_STYLE) & WS_VISIBLE) && !IsWindowEnabled(button),
                    "the Golden Child: the Change sex button is hidden");
            *(int *)(h_record + 0x36C) = 10;
            appearance_offer_sex(w);
            h_check(button != NULL && (GetWindowLongA(button, GWL_STYLE) & WS_VISIBLE) && IsWindowEnabled(button),
                    "anyone else: the Change sex button is shown");
            *(int *)(h_record + 0x36C) = 0xC7;
            DestroyWindow(w);
        }
    }
#endif
}

/* ---- the templates, measured -------------------------------------------------------------------------- */

static INT_PTR CALLBACK h_quiet_proc(HWND w, UINT m, WPARAM wp, LPARAM lp) {
    (void)w; (void)wp; (void)lp;
    return m == WM_INITDIALOG;
}

static BOOL CALLBACK h_overlap(HWND child, LPARAM lp) {
    HWND *pair = (HWND *)lp;          /* [0] the button, [1] set when something overlaps it */
    RECT a, b, x;
    char cls[32];
    if (child == pair[0] || !(GetWindowLongA(child, GWL_STYLE) & WS_VISIBLE)) {
        return TRUE;
    }
    GetClassNameA(child, cls, sizeof cls);
    if (lstrcmpiA(cls, "Button") == 0 && (GetWindowLongA(child, GWL_STYLE) & 0xF) == BS_GROUPBOX) {
        /* a group box is a frame: only its edges are drawn */
        RECT g;
        GetWindowRect(child, &g);
        GetWindowRect(pair[0], &a);
        if (IntersectRect(&x, &a, &g) && !(a.left > g.left && a.right < g.right && a.top > g.top + 8
                                           && a.bottom < g.bottom)) {
            pair[1] = child;
        }
        return TRUE;
    }
    GetWindowRect(pair[0], &a);
    GetWindowRect(child, &b);
    if (IntersectRect(&x, &a, &b)) {
        pair[1] = child;
    }
    return TRUE;
}

static void h_measure(int template_id, const char *which) {
    HWND w = CreateDialogParamA(module_instance, MAKEINTRESOURCEA(template_id), NULL, h_quiet_proc, 0);
    HWND button, pair[2];
    RECT client, r;
    char text[64], what[160];
    HDC dc;
    HFONT font, old;
    SIZE extent;
    if (w == NULL) {
        wsprintfA(what, "%s: the template is there", which);
        h_check(0, what);
        return;
    }
    button = GetDlgItem(w, VVFP_AX_CHANGE_SEX);
    wsprintfA(what, "%s: the Change sex button is there", which);
    h_check(button != NULL, what);
    if (button == NULL) {
        DestroyWindow(w);
        return;
    }
    GetWindowTextA(button, text, sizeof text);
    wsprintfA(what, "%s: the label is \"" VVFP_AX_CHANGE_SEX_LABEL "\"", which);
    h_check(lstrcmpA(text, VVFP_AX_CHANGE_SEX_LABEL) == 0, what);
    GetClientRect(w, &client);
    GetWindowRect(button, &r);
    MapWindowPoints(NULL, w, (POINT *)&r, 2);
    wsprintfA(what, "%s: the button is inside the window", which);
    h_check(r.left >= client.left && r.top >= client.top && r.right <= client.right && r.bottom <= client.bottom, what);
    pair[0] = button;
    pair[1] = NULL;
    EnumChildWindows(w, h_overlap, (LPARAM)pair);
    if (pair[1] != NULL) {
        GetWindowTextA(pair[1], text, sizeof text);
        wsprintfA(what, "%s: the button overlaps no other control (it overlaps \"%s\")", which, text);
        h_check(0, what);
    }
    dc = GetDC(button);
    font = (HFONT)SendMessageA(button, WM_GETFONT, 0, 0);
    old = (HFONT)SelectObject(dc, font);
    GetTextExtentPoint32A(dc, VVFP_AX_CHANGE_SEX_LABEL, lstrlenA(VVFP_AX_CHANGE_SEX_LABEL), &extent);
    SelectObject(dc, old);
    ReleaseDC(button, dc);
    printf("%s %s: button %ldx%ld px, text %ldx%ld px\n", H_GAME_NAME, which, r.right - r.left, r.bottom - r.top,
           extent.cx, extent.cy);
    /* a push button draws its text inside a 3 px edge and focus rectangle on each side */
    wsprintfA(what, "%s: the label fits inside the button", which);
    h_check(extent.cx + 8 <= r.right - r.left && extent.cy + 4 <= r.bottom - r.top, what);
    DestroyWindow(w);
}

/* ---- the screenshots ------------------------------------------------------------------------------------ */

static char h_dir[MAX_PATH];
static DWORD h_main_thread;

typedef struct { const char *title; HWND found; } h_find;

static BOOL CALLBACK h_find_window(HWND w, LPARAM lp) {
    h_find *f = (h_find *)lp;
    char title[128];
    if (IsWindowVisible(w) && GetWindowTextA(w, title, sizeof title) > 0 && lstrcmpA(title, f->title) == 0) {
        f->found = w;
        return FALSE;
    }
    return TRUE;
}

static HWND h_wait_window(const char *title) {
    h_find f;
    int tries;
    for (tries = 0; tries < 100; ++tries) {
        f.title = title;
        f.found = NULL;
        EnumThreadWindows(h_main_thread, h_find_window, (LPARAM)&f);
        if (f.found != NULL) {
            Sleep(700);                 /* painted */
            return f.found;
        }
        Sleep(100);
    }
    return NULL;
}

/* The window as it is on screen, into a 24-bit BMP. */
static int h_capture(HWND w, const char *name) {
    RECT r;
    int width, height, row, ok = 0;
    HDC screen, mem;
    HBITMAP bitmap, old;
    BITMAPINFOHEADER info;
    BITMAPFILEHEADER head;
    unsigned char *bits;
    char path[MAX_PATH];
    HANDLE file;
    DWORD wrote;
    GetWindowRect(w, &r);
    width = r.right - r.left;
    height = r.bottom - r.top;
    screen = GetDC(NULL);
    mem = CreateCompatibleDC(screen);
    bitmap = CreateCompatibleBitmap(screen, width, height);
    old = (HBITMAP)SelectObject(mem, bitmap);
    PrintWindow(w, mem, 2 /* PW_RENDERFULLCONTENT */);
    SelectObject(mem, old);
    row = ((width * 3 + 3) / 4) * 4;
    memset(&info, 0, sizeof info);
    info.biSize = sizeof info;
    info.biWidth = width;
    info.biHeight = height;
    info.biPlanes = 1;
    info.biBitCount = 24;
    info.biCompression = BI_RGB;
    bits = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)row * height);
    if (bits != NULL && GetDIBits(mem, bitmap, 0, (UINT)height, bits, (BITMAPINFO *)&info, DIB_RGB_COLORS) > 0) {
        wsprintfA(path, "%s\\%s", h_dir, name);
        file = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (file != INVALID_HANDLE_VALUE) {
            memset(&head, 0, sizeof head);
            head.bfType = 0x4D42;
            head.bfOffBits = sizeof head + sizeof info;
            head.bfSize = head.bfOffBits + (DWORD)row * height;
            ok = WriteFile(file, &head, sizeof head, &wrote, NULL) && WriteFile(file, &info, sizeof info, &wrote, NULL)
                 && WriteFile(file, bits, (DWORD)row * height, &wrote, NULL);
            CloseHandle(file);
        }
    }
    if (bits != NULL) {
        HeapFree(GetProcessHeap(), 0, bits);
    }
    DeleteObject(bitmap);
    DeleteDC(mem);
    ReleaseDC(NULL, screen);
    printf("%s %s\n", ok ? "saved" : "NOT SAVED", name);
    return ok;
}

static const char *h_shot_window, *h_shot_box;

static DWORD WINAPI h_shooter(LPVOID unused) {
    HWND dialog = h_wait_window("Change Appearance"), box;
    (void)unused;
    if (dialog == NULL) {
        printf("NOT SAVED: no Change Appearance window\n");
        return 1;
    }
    h_capture(dialog, h_shot_window);
    box = NULL;
    if (h_shot_box != NULL) {
        PostMessageA(dialog, WM_COMMAND, MAKEWPARAM(VVFP_AX_CHANGE_SEX, BN_CLICKED),
                     (LPARAM)GetDlgItem(dialog, VVFP_AX_CHANGE_SEX));
        box = h_wait_window(VVFP_AX_CHANGE_SEX_TITLE);
    }
    if (box != NULL) {
        h_capture(box, h_shot_box);
        PostMessageA(box, WM_COMMAND, IDNO, 0);   /* No: nothing changes */
        Sleep(400);
    }
    PostMessageA(dialog, WM_COMMAND, IDCANCEL, 0);
    return 0;
}

/* `who`: 0 Lani, 1 Lani carrying, 2 the Golden Child (A New Home). */
static void h_shot(const char *window_name, const char *box_name, int look, int who) {
    HANDLE thread;
    h_look_there = look;
    h_shot_window = window_name;
    h_shot_box = box_name;
    if (who == 2) {
        h_villager("Golden Child", H_MALE);
        *(int *)(h_record + 0x36C) = 0xC7;
        *(int *)(h_record + H_HEAD) = 19;    /* the golden head and body (row 19) */
        *(int *)(h_record + H_BODY) = 19;
    } else {
        h_villager("Lani", H_FEMALE);
        if (who == 1) {
            *(int *)(h_record + H_PREGNANT) = 7;
        }
    }
    thread = CreateThread(NULL, 0, h_shooter, NULL, 0, NULL);
    h_open();
    WaitForSingleObject(thread, 20000);
    CloseHandle(thread);
    h_look_there = 0;
}

int main(int argc, char **argv) {
    if (!harness_redirect_documents_process()) {
        printf("FAIL: Documents not redirected to a throwaway folder; not running\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    module_instance = GetModuleHandleA(NULL);
#if HARNESS_GAME == 1
    if (!h_game_memory()) {
        printf("FAIL: the game's addresses 0x480000..0x4C0000 are not in the harness's block\n");
        return 2;
    }
#else
    h_record = (unsigned char *)VirtualAlloc(NULL, 0x10000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    h_player = (unsigned char *)VirtualAlloc(NULL, 0x40000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
#endif
    if (argc >= 3 && lstrcmpA(argv[1], "shot") == 0) {
        char window_name[96], box_name[96], look_name[96];
        lstrcpynA(h_dir, argv[2], sizeof h_dir);
        h_main_thread = GetCurrentThreadId();
        h_real = 1;
        wsprintfA(window_name, "%s Change Appearance - Change sex.bmp", H_GAME_NAME);
        wsprintfA(box_name, "%s Change sex warning.bmp", H_GAME_NAME);
        wsprintfA(look_name, "%s Change Appearance (Head look) - Change sex.bmp", H_GAME_NAME);
        h_shot(window_name, box_name, 0, 0);
        h_shot(look_name, NULL, 1, 0);
        wsprintfA(window_name, "%s Change Appearance - carrying.bmp", H_GAME_NAME);
        wsprintfA(box_name, "%s Change sex warning (carrying).bmp", H_GAME_NAME);
        h_shot(window_name, box_name, 0, 1);
#if HARNESS_GAME == 1
        h_shot("VV1 Change Appearance - Golden Child (no Change sex).bmp", NULL, 0, 2);
#endif
        return 0;
    }
    h_checks_run();
    h_measure(H_TEMPLATE, "Change Appearance");
    h_measure(H_TEMPLATE_LOOK, "Change Appearance (Head look)");
    printf("game %d: %d checks, %d failures\n", HARNESS_GAME, h_checks, h_failures);
    return h_checks > 0 && h_failures == 0 ? 0 : 1;
}
