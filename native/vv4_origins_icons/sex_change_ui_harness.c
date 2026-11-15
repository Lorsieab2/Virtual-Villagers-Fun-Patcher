/* Change Appearance's "Change sex..." button (native/shared/sex_change_ui.h) in The Secret City, The Tree of Life
   and New Believers: the Origins companions' real dialog procedures and chooser exports, driven by the button's own
   WM_COMMAND.

   Compiled once per game with /DHARNESS_GAME=<3..5>: this file includes that game's Origins companion source
   UNCHANGED (as native/shared/change_appearance_harness.c does), linked fixed at 0x400000 with a zeroed block over
   the game's own addresses the companions read (the mask slot words, The Tree of Life's record table), and the
   game's save manager stood in by a null one (native/shared/game_save_slot.h's VV_GAME_SAVE_MANAGER_AT), so no slot
   is known: no log line is written and no file is read or written.  Documents is redirected to a throwaway folder
   all the same (harness_redirect_documents.h).

   TEST MODE (no argument): the Win32 calls a dialog needs a screen for are stood in -- the dialog runs the scripted
   presses, EndDialog records the result, every message box is answered by the script (Yes or No for the warning)
   and remembered.  Checked: Yes changes the record's sex and what the window draws by it; No changes nothing; a
   villager carrying or nursing a baby is asked with the carrying sentence and keeps the pregnancy fields; The
   Secret City's Tribal Chief and stand-in and New Believers' story villagers (roles 12..17) are refused with a
   message and never asked; Undo changes does not change it back; an
   OK with only the sex changed returns no change to the executable and shows no "unchanged" box; a press again
   changes it back.

   GENDER PRESENTATION (native/shared/gender_presentation.h), with "VVFP Gender Presentation.dll" stood in by
   native/shared/gender_presentation_stand_in.h: the row off hides "Change sex..." and the checkbox; ticked, the window
   draws the other sex's sheets while the record's sex stays; OK keeps it (free: no change for the executable),
   Cancel and Undo changes keep nothing; a story villager is told why and nothing is kept; a failed write is told.

   SHOT MODE (`shots <folder>`): the companion's REAL dialog template (its .res is linked in) and procedure are
   shown on screen with the real Win32 calls; a thread captures the window (PrintWindow) to
   "<folder>\VV<g> Change Appearance - Change sex.bmp", presses Change sex..., captures the real warning box to
   "<folder>\VV<g> Change sex warning.bmp", answers No and closes the window with Cancel. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "../shared/harness_redirect_documents.h"
#include "../shared/gender_presentation_stand_in.h"

#ifndef HARNESS_GAME
#error "build with /DHARNESS_GAME=3..5"
#endif

static int h_shots;                 /* 1: real windows, captured */
static int h_gp_boxes;              /* the "Gender presentation" boxes shown */
static char h_gp_box_text[600];
static int h_failures;
static int h_checks;
static INT_PTR h_end_result;
static int h_answer = IDYES;        /* the warning's answer */
static int h_boxes;                 /* message boxes shown */
static int h_asked;                 /* ...of which a Yes / No question */
static char h_box_text[1200];
static const UINT *h_script;
static int h_script_len;

/* No save manager: no slot is known (game_save_slot.h). */
static const unsigned char *const volatile h_no_manager = NULL;
#define VV_GAME_SAVE_MANAGER_AT(game) (&h_no_manager)

static BOOL WINAPI h_EndDialog(HWND window, INT_PTR result) {
    h_end_result = result;
    return h_shots ? EndDialog(window, result) : TRUE;
}

static int WINAPI h_MessageBoxA(HWND window, LPCSTR text, LPCSTR caption, UINT flags) {
    if (h_shots) {
        return MessageBoxA(window, text, caption, flags);
    }
    if (caption != NULL && lstrcmpA(caption, "Gender presentation") == 0) {   /* VVFP_GP_TITLE */
        h_gp_boxes++;
        lstrcpynA(h_gp_box_text, text != NULL ? text : "", sizeof h_gp_box_text);
    }
    h_boxes++;
    lstrcpynA(h_box_text, text != NULL ? text : "", sizeof h_box_text);
    if ((flags & 0xF) == MB_YESNO) {
        h_asked++;
        return h_answer;
    }
    return IDOK;
}

static BOOL WINAPI h_InvalidateRect(HWND window, const RECT *rect, BOOL erase) {
    return h_shots ? InvalidateRect(window, rect, erase) : TRUE;
}

static INT_PTR h_press(DLGPROC proc, const UINT *script, int len) {
    int i;
    h_end_result = -1;
    for (i = 0; i < len; ++i) {
        h_gp_click(script[i]);
        proc(NULL, WM_COMMAND, MAKEWPARAM(script[i], BN_CLICKED), 0);
    }
    return h_end_result;
}

static INT_PTR WINAPI h_DialogBoxParamA(HINSTANCE instance, LPCSTR name, HWND owner, DLGPROC proc, LPARAM param) {
    if (h_shots) {
        return DialogBoxParamA(instance, name, owner, proc, param);
    }
    return h_press(proc, h_script, h_script_len);
}

/* New Believers' chooser asks the game object which villager is selected: here, the harness's record when its
   sex and age are the ones asked for. */
static unsigned char *h_record;
static const unsigned char *h_selected(int sex, int age);
#define VV5_SELECTED_RECORD h_selected

static HMODULE WINAPI h_GetModuleHandleA(LPCSTR name) {
    int gp;
    HMODULE module = h_gp_module(name, &gp);
    return gp ? module : GetModuleHandleA(name);
}

static FARPROC WINAPI h_GetProcAddress(HMODULE module, LPCSTR name) {
    return module == H_GP_MODULE ? h_gp_proc(name) : GetProcAddress(module, name);
}

#define EndDialog h_EndDialog
#define MessageBoxA h_MessageBoxA
#define InvalidateRect h_InvalidateRect
#define DialogBoxParamA h_DialogBoxParamA
#define GetModuleHandleA h_GetModuleHandleA
#define GetProcAddress h_GetProcAddress
#define IsDlgButtonChecked h_gp_is_checked
#define CheckDlgButton h_gp_check

#if HARNESS_GAME == 3
#include "../vv3_full_mastery_candidate/vv3_full_mastery_candidate.c"
#elif HARNESS_GAME == 4
#include "vv4_origins_icons.c"
#elif HARNESS_GAME == 5
#include "../vv5_task9_origins/vv5_task9_origins.c"
#else
#error "HARNESS_GAME must be 3..5"
#endif

#undef EndDialog
#undef MessageBoxA
#undef InvalidateRect
#undef DialogBoxParamA
#undef GetModuleHandleA
#undef GetProcAddress
#undef IsDlgButtonChecked
#undef CheckDlgButton

/* The game's fixed addresses the companions read (the mask slot words 0x6E0044 / 0x728FCC, New Believers' mask
   table, The Tree of Life's records at 0x50E5AC): the image is fixed at 0x400000 and this zeroed block lies over
   them (vv5_mask_identity_harness.c's way). */
static unsigned char h_backing[0x600000];

static int h_covered(unsigned int lo, unsigned int size) {
    unsigned int b = (unsigned int)(UINT_PTR)h_backing;
    return lo >= b && lo + size <= b + sizeof h_backing;
}

static const vv_sex_layout *h_layout(void) {
    return &VV_SEX_LAYOUT[HARNESS_GAME];
}

static int h_sex(void) {
    return *(const int *)(h_record + h_layout()->sex);
}

static const unsigned char *h_selected(int sex, int age) {
    (void)age;
    return h_record != NULL && h_sex() == sex ? h_record : NULL;
}

static void h_check(int ok, const char *what) {
    h_checks++;
    if (!ok) {
        h_failures++;
        printf("FAIL game %d: %s\n", HARNESS_GAME, what);
    }
}

/* A fresh villager called Lani, of `sex`. */
static void h_villager(int sex) {
    const vv_sex_layout *l = h_layout();
    memset(h_record, 0, 0x4000);
    memcpy(h_record + l->name, "Lani", 5);
    *(int *)(h_record + l->sex) = sex;
    *(int *)(h_record + l->head) = 3;
    *(int *)(h_record + l->body) = 4;
    h_boxes = h_asked = 0;
    h_box_text[0] = 0;
    h_gp_boxes = 0;
    h_gp_box_text[0] = 0;
}

/* The window's own idea of the villager's sex (what its preview and hair colours are drawn by). */
static int h_window_sex(void) {
#if HARNESS_GAME == 3
    return vv3_appearance_sex;
#elif HARNESS_GAME == 4
    return appearance_state.sex;
#else
    return appearance_sex;
#endif
}

/* The sex the window's preview draws (with the gender presentation: the other one). */
static int h_window_drawn(void) {
#if HARNESS_GAME == 5
    return appearance_drawn_sex();
#else
    return h_window_sex();
#endif
}

static const vvfp_gp_window *h_gp_window(void) {
#if HARNESS_GAME == 3
    return &vv3_appearance_gp;
#else
    return &appearance_gp;
#endif
}

/* Open the per-villager window's state on the record, as the chooser export does. */
static void h_open(void) {
#if HARNESS_GAME == 3
    vvfp_gp_window_open(&vv3_appearance_gp, 3, h_record);
#elif HARNESS_GAME == 4
    vvfp_gp_window_open(&appearance_gp, 4, h_record);
#else
    appearance_gp_record = h_record;
    vvfp_gp_window_open(&appearance_gp, 5, h_record);
#endif
#if HARNESS_GAME == 3
    vv3_appearance_sex = h_sex() ? 1 : 0;
    vv3_appearance_age = 600;
    vv3_appearance_look_offered = h_shots;
    vv3_appearance_look = 0;
    vv3_appearance_old = 0;
    vv3_appearance_head = vv3_appearance_open_head = 3;
    vv3_appearance_body = vv3_appearance_open_body = 4;
    vv3_appearance_mask = vv3_appearance_open_mask = 0;
    vv3_appearance_open_look = 0;
    vv3_appearance_record = h_record;
    vv3_appearance_sex_changed = 0;
#elif HARNESS_GAME == 4
    appearance_state.villager = h_record;
    appearance_state.original_head = 3;
    appearance_state.original_body = 4;
    appearance_state.original_mask = 0;
    appearance_state.head_count = VV_HEAD_COUNT;
    appearance_state.body_count = VV_BODY_COUNT;
    appearance_state.sex = h_sex();
    appearance_state.is_old = 0;
    appearance_look_offered = h_shots;
    appearance_look = appearance_look_was = 0;
    appearance_sex_changed = 0;
#else
    appearance_sex = h_sex() ? 1 : 0;
    appearance_age = 600;
    appearance_record = h_shots ? h_record : NULL;
    appearance_look = 0;
    appearance_old = 0;
    appearance_head = appearance_open_head = 3;
    appearance_body = appearance_open_body = 4;
    appearance_mask = appearance_open_mask = 0;
    appearance_open_look = 0;
    appearance_sex_changed = 0;
#endif
}

#if HARNESS_GAME == 3
#define H_PROC vv3_appearance_dialog
#else
#define H_PROC appearance_dialog
#endif

/* Press the scripted buttons in the per-villager window. */
static INT_PTR h_window(const UINT *script, int len) {
    h_open();
    return h_press(H_PROC, script, len);
}

/* The chooser export end to end, as the executable calls it; the value it returns to the executable. */
static int h_export(const UINT *script, int len) {
    h_script = script;
    h_script_len = len;
#if HARNESS_GAME == 3
    {
        int head = 3, body = 4;
        return ShowVV3AppearanceChooser(h_sex(), 600, &head, &body, h_record);
    }
#elif HARNESS_GAME == 4
    return ShowOriginsAppearancePicker((int)(UINT_PTR)h_record);
#else
    {
        int head = 3, body = 4, mask = 0;
        return ShowAppearanceChooser(h_sex(), 600, &head, &body, &mask);
    }
#endif
}

static void h_refused(const char *what, void (*make)(void), const char *says) {
    static const UINT press[] = { VVFP_AX_CHANGE_SEX, IDCANCEL };
    int was;
    h_villager(1);
    make();
    was = h_sex();
    h_window(press, 2);
    h_check(h_sex() == was && h_asked == 0 && h_boxes == 1 && strstr(h_box_text, says) != NULL, what);
}

static void h_make_pregnant(void) {
    *(int *)(h_record + h_layout()->pregnant) = 40;
}

static void h_make_nursing(void) {
    *(int *)(h_record + h_layout()->pregnant + 4) = 1;
}

#if HARNESS_GAME == 3
static void h_make_chief(void) {
    h_record[0xE80] = 1;
}

static void h_make_standin(void) {
    h_record[0xE94] = 1;
}
#endif

#if HARNESS_GAME == 5
static void h_make_story(void) {
    *(int *)(h_record + 0x1CFC) = 12;
}

static void h_make_story_last(void) {
    *(int *)(h_record + 0x1CFC) = 17;
}
#endif

/* The "Gender presentation" checkbox and its row. */
static void h_gp_tests(void) {
    const vv_sex_layout *l = h_layout();
    int result;
    {
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, VVFP_AX_PRESENTATION, IDCANCEL };
        h_gp_reset();
        h_gp_there = 0;
        h_villager(l->female);
        h_window(press, 3);
        h_check(h_sex() == l->female && h_boxes == 0 && !vvfp_ax_change_sex_offered(HARNESS_GAME, h_record),
                "the row off: Change sex is not offered and its command does nothing");
        h_check(!h_gp_window()->offered && h_gp_sets == 0, "the row off: the checkbox is not offered, nothing kept");
    }
    {
        static const UINT press[] = { VVFP_AX_PRESENTATION, IDOK };
        h_gp_reset();
        h_villager(l->female);
        result = h_export(press, 2);
        h_check(h_sex() == l->female, "ticked: the record's sex stays");
        h_check(h_window_drawn() == 0, "ticked: the preview draws the other sex's heads and bodies");
        h_check(h_gp_sets == 1 && h_gp_record == h_record && h_gp_on == 1, "ticked, OK: the choice is kept");
        h_check(result == 0 && h_boxes == 0, "ticked alone, OK: no change for the executable, no box");
        h_check(*(int *)(h_record + l->head) == 3 && *(int *)(h_record + l->body) == 4, "ticked: the same rows");
    }
    {
        static const UINT press[] = { VVFP_AX_PRESENTATION, IDCANCEL };
        h_gp_reset();
        h_villager(l->female);
        h_export(press, 2);
        h_check(h_gp_sets == 0, "ticked, Cancel: nothing is kept");
    }
    {
        static const UINT press[] = { VVFP_AX_PRESENTATION, VVFP_AX_UNDO, IDOK };
        h_gp_reset();
        h_villager(l->female);
        h_export(press, 3);
        h_check(h_gp_sets == 0 && h_window_drawn() == 1 && !h_gp_box, "ticked, Undo changes: nothing kept");
    }
    {
        static const UINT show[] = { VVFP_AX_UNDO, IDCANCEL };
        h_gp_reset();
        h_villager(l->male);
        h_gp_record = h_record;
        h_gp_on = 1;
        h_export(show, 2);
        h_check(h_window_drawn() == 1 && h_gp_box && h_gp_sets == 0, "kept on: the window opens with the other look");
    }
    {
        static const UINT press[] = { VVFP_AX_PRESENTATION, IDOK };
        h_gp_reset();
        h_gp_fail = 1;
        h_villager(l->female);
        h_export(press, 2);
        h_check(h_gp_boxes == 1 && strstr(h_gp_box_text, "could not be written") != NULL && h_gp_on == 0,
                "a failed write: told, nothing kept");
    }
    {
        /* Born male, changing to female: told they will not conceive on their own (the owner, 2026-11-15). */
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, IDCANCEL };
        h_gp_reset();
        h_gp_born_female = 0;
        h_villager(l->male);
        memcpy(h_record + l->name, "Kai", 4);
        h_answer = IDNO;
        h_window(press, 2);
        h_check(strstr(h_box_text, "Kai was born male, so Kai will not conceive on their own. A Custom Island Event can still give Kai a baby with a partner you choose.") != NULL && strstr(h_box_text, "able to carry") == NULL,
                "born male: the warning says they will not conceive on their own, a Custom Island Event can");
        h_gp_reset();
        h_villager(l->male);
        h_window(press, 2);
        h_check(strstr(h_box_text, "will not conceive") == NULL, "born female: no such sentence");
        h_answer = IDYES;
    }
#if HARNESS_GAME == 3 || HARNESS_GAME == 5
    {
        static const UINT press[] = { VVFP_AX_PRESENTATION, IDOK };
        h_gp_reset();
        h_villager(l->female);
#if HARNESS_GAME == 3
        h_make_chief();
#else
        h_make_story();
#endif
        h_export(press, 2);
        h_check(h_gp_boxes == 1 && strstr(h_gp_box_text, "is a story villager") != NULL && h_gp_sets == 0
                && !h_gp_box && h_window_drawn() == 1, "a story villager: told why, nothing kept");
    }
#endif
    h_gp_reset();
}

static void h_tests(void) {
    const vv_sex_layout *l = h_layout();
    h_gp_tests();
    {
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, IDCANCEL };
        h_villager(l->female);
        h_answer = IDYES;
        h_window(press, 2);
        h_check(h_sex() == l->male && h_asked == 1, "Yes: the record's sex is changed at once, Cancel keeps it");
        h_check(h_window_sex() == 0, "the window draws the new sex's sheets");
        h_check(strstr(h_box_text, "Change Lani's sex to male?") != NULL, "the warning names the villager and the sex");
        h_check(*(int *)(h_record + l->head) == 3 && *(int *)(h_record + l->body) == 4,
                "the head and body rows stay");
    }
    {
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, IDOK };
        h_villager(l->male);
        h_answer = IDNO;
        h_window(press, 2);
        h_check(h_sex() == l->male && h_asked == 1 && h_window_sex() == 0, "No: nothing is changed");
    }
    {
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, VVFP_AX_UNDO, IDCANCEL };
        h_villager(l->male);
        h_answer = IDYES;
        h_window(press, 3);
        h_check(h_sex() == l->female && h_window_sex() == 1, "Undo changes does not change the sex back");
    }
    {
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, VVFP_AX_CHANGE_SEX, IDCANCEL };
        h_villager(l->male);
        h_answer = IDYES;
        h_window(press, 3);
        h_check(h_sex() == l->male && h_asked == 2, "pressing again changes it back");
    }
    {
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, IDOK };
        int result;
        h_villager(l->female);
        h_answer = IDYES;
        result = h_export(press, 2);
        h_check(result == 0 && h_sex() == l->male && h_boxes == 1,
                "OK with only the sex changed: no change for the executable, no \"unchanged\" box");
    }
    {
        /* Carrying or nursing (the same field in every game): offered; the warning says they go on carrying and
           stay the carrying parent; Yes changes the sex and leaves the pregnancy fields as they were. */
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, IDCANCEL };
        h_villager(l->female);
        h_make_pregnant();
        h_make_nursing();
        h_answer = IDYES;
        h_window(press, 2);
        h_check(h_sex() == l->male && h_asked == 1 && h_boxes == 1, "carrying: asked, Yes changes the sex");
        h_check(strstr(h_box_text, "Lani is carrying or nursing a baby. Lani goes on carrying, and stays the "
                                   "carrying parent") != NULL, "carrying: the warning says they go on carrying");
        h_check(*(int *)(h_record + l->pregnant) == 40 && *(int *)(h_record + l->pregnant + 4) == 1,
                "carrying: the pregnancy fields are untouched");
        h_villager(l->female);
        h_make_pregnant();
        h_answer = IDNO;
        h_window(press, 2);
        h_check(h_sex() == l->female && *(int *)(h_record + l->pregnant) == 40, "carrying, No: nothing changes");
        h_villager(l->female);
        h_window(press, 2);
        h_check(strstr(h_box_text, "goes on carrying") == NULL, "not carrying: no carrying sentence");
        h_answer = IDYES;
    }
#if HARNESS_GAME == 3
    h_refused("the Tribal Chief: refused, never asked", h_make_chief, "is a story villager");
    h_refused("the Tribal Chief's stand-in: refused, never asked", h_make_standin, "is a story villager");
#endif
#if HARNESS_GAME == 5
    {
        /* A Heathen (an Isolan with Guardians of Isola: the same record) and a believer: offered, Yes changes the
           sex, and the faith fields -- the faction byte, the mask selectors, the faith, the role -- stay as they
           were (0x1CE0..0x1CFF compared byte for byte). */
        static const UINT press[] = { VVFP_AX_CHANGE_SEX, IDCANCEL };
        unsigned char faith[0x20];
        int heathen;
        for (heathen = 0; heathen < 2; ++heathen) {
            h_villager(l->female);
            h_record[0x1CEC] = (unsigned char)heathen;          /* the faction: a Heathen */
            h_record[0x1CED] = (unsigned char)heathen;          /* the orange mask selector */
            *(int *)(h_record + 0x1CF0) = heathen ? -25 : 60;   /* the faith */
            *(int *)(h_record + 0x1CFC) = heathen ? 3 : 0;      /* an ordinary role, not 12..17 */
            memcpy(faith, h_record + 0x1CE0, sizeof faith);
            h_answer = IDYES;
            h_window(press, 2);
            h_check(h_sex() == l->male && h_asked == 1,
                    heathen ? "a Heathen (Isolan): Yes changes the sex" : "a believer: Yes changes the sex");
            h_check(memcmp(faith, h_record + 0x1CE0, sizeof faith) == 0,
                    heathen ? "a Heathen (Isolan): the faith fields are untouched"
                            : "a believer: the faith fields are untouched");
        }
    }
    h_refused("a story villager (role 12): refused, never asked", h_make_story, "is a story villager");
    h_refused("a story villager (role 17): refused, never asked", h_make_story_last, "is a story villager");
#endif
}

/* ---- shot mode ----------------------------------------------------------------------------------------------- */

static char h_folder[MAX_PATH];

typedef struct {
    const char *title;
    HWND not_this;
    HWND found;
} h_find;

static BOOL CALLBACK h_find_one(HWND window, LPARAM param) {
    h_find *f = (h_find *)param;
    char title[128];
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    if (pid == GetCurrentProcessId() && window != f->not_this && IsWindowVisible(window)
        && GetWindowTextA(window, title, sizeof title) > 0 && lstrcmpA(title, f->title) == 0) {
        f->found = window;
        return FALSE;
    }
    return TRUE;
}

static HWND h_wait(const char *title, HWND not_this) {
    h_find f;
    int tries;
    for (tries = 0; tries < 200; ++tries) {
        f.title = title;
        f.not_this = not_this;
        f.found = NULL;
        EnumWindows(h_find_one, (LPARAM)&f);
        if (f.found != NULL) {
            return f.found;
        }
        Sleep(50);
    }
    return NULL;
}

/* The window as it draws itself, to a 24-bit BMP. */
static int h_capture(HWND window, const char *name) {
    RECT rc;
    HDC screen, dc;
    HBITMAP bitmap, old;
    BITMAPINFOHEADER bi;
    BITMAPFILEHEADER bf;
    char path[MAX_PATH];
    unsigned char *bits;
    DWORD row, size, wrote;
    HANDLE file;
    int w, h, ok;
    GetWindowRect(window, &rc);
    w = rc.right - rc.left;
    h = rc.bottom - rc.top;
    screen = GetDC(NULL);
    dc = CreateCompatibleDC(screen);
    bitmap = CreateCompatibleBitmap(screen, w, h);
    old = (HBITMAP)SelectObject(dc, bitmap);
    ok = PrintWindow(window, dc, 2 /* PW_RENDERFULLCONTENT */);
    SelectObject(dc, old);
    memset(&bi, 0, sizeof bi);
    bi.biSize = sizeof bi;
    bi.biWidth = w;
    bi.biHeight = h;
    bi.biPlanes = 1;
    bi.biBitCount = 24;
    row = ((DWORD)w * 3u + 3u) & ~3u;
    size = row * (DWORD)h;
    bits = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, size);
    ok = ok && bits != NULL && GetDIBits(dc, bitmap, 0, (UINT)h, bits, (BITMAPINFO *)&bi, DIB_RGB_COLORS) == h;
    wsprintfA(path, "%s\\%s", h_folder, name);
    if (ok) {
        memset(&bf, 0, sizeof bf);
        bf.bfType = 0x4D42;
        bf.bfOffBits = sizeof bf + sizeof bi;
        bf.bfSize = bf.bfOffBits + size;
        file = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        ok = file != INVALID_HANDLE_VALUE
            && WriteFile(file, &bf, sizeof bf, &wrote, NULL) && WriteFile(file, &bi, sizeof bi, &wrote, NULL)
            && WriteFile(file, bits, size, &wrote, NULL);
        if (file != INVALID_HANDLE_VALUE) {
            CloseHandle(file);
        }
    }
    if (bits != NULL) {
        HeapFree(GetProcessHeap(), 0, bits);
    }
    DeleteObject(bitmap);
    DeleteDC(dc);
    ReleaseDC(NULL, screen);
    printf("%s %s\n", ok ? "captured" : "FAILED to capture", path);
    return ok;
}

static int h_shot_carrying;        /* the second shot: Lani carrying */

static DWORD WINAPI h_shooter(LPVOID unused) {
    char name[96];
    HWND window, box;
    const char *suffix = h_shot_carrying ? " (carrying)" : "";
    (void)unused;
    window = h_wait("Change Appearance", NULL);
    if (window == NULL) {
        h_failures++;
        printf("FAIL: the Change Appearance window was not shown\n");
        return 0;
    }
    Sleep(800);
    wsprintfA(name, "VV%d Change Appearance - Change sex%s.bmp", HARNESS_GAME, suffix);
    h_check(h_capture(window, name), "the window captured");
    PostMessageA(window, WM_COMMAND, MAKEWPARAM(VVFP_AX_CHANGE_SEX, BN_CLICKED),
                 (LPARAM)GetDlgItem(window, VVFP_AX_CHANGE_SEX));
    box = h_wait(VVFP_AX_CHANGE_SEX_TITLE, window);
    if (box == NULL) {
        h_failures++;
        printf("FAIL: the warning was not shown\n");
    } else {
        Sleep(800);
        wsprintfA(name, "VV%d Change sex warning%s.bmp", HARNESS_GAME, suffix);
        h_check(h_capture(box, name), "the warning captured");
        PostMessageA(box, WM_COMMAND, IDNO, 0);
        Sleep(300);
    }
    PostMessageA(window, WM_COMMAND, IDCANCEL, 0);
    return 0;
}

/* The Gender presentation shots: the window as it opens, then the box ticked (the other sex's sheets). */
static DWORD WINAPI h_gp_shooter(LPVOID unused) {
    char name[96];
    HWND window;
    (void)unused;
    window = h_wait("Change Appearance", NULL);
    if (window == NULL) {
        h_failures++;
        printf("FAIL: the Change Appearance window was not shown\n");
        return 0;
    }
    Sleep(800);
    wsprintfA(name, "VV%d Change Appearance - Gender presentation off.bmp", HARNESS_GAME);
    h_check(h_capture(window, name), "the window captured (presentation off)");
    SendMessageA(GetDlgItem(window, VVFP_AX_PRESENTATION), BM_CLICK, 0, 0);
    Sleep(800);
    wsprintfA(name, "VV%d Change Appearance - Gender presentation on.bmp", HARNESS_GAME);
    h_check(h_capture(window, name), "the window captured (presentation on)");
    PostMessageA(window, WM_COMMAND, IDCANCEL, 0);
    return 0;
}

static void h_gp_shot(void) {
    HANDLE thread;
    h_villager(VV_SEX_LAYOUT[HARNESS_GAME].female);
    h_open();
    thread = CreateThread(NULL, 0, h_gp_shooter, NULL, 0, NULL);
    DialogBoxParamA(GetModuleHandleA(NULL), MAKEINTRESOURCEA(208), NULL, H_PROC, 0);
    WaitForSingleObject(thread, 15000);
    CloseHandle(thread);
    h_check(h_sex() == VV_SEX_LAYOUT[HARNESS_GAME].female && h_gp_sets == 0, "Cancel kept nothing");
}

static void h_shot(int carrying) {
    HANDLE thread;
    h_shot_carrying = carrying;
    h_villager(VV_SEX_LAYOUT[HARNESS_GAME].female);
    if (carrying) {
        h_make_pregnant();
    }
    h_open();
    thread = CreateThread(NULL, 0, h_shooter, NULL, 0, NULL);
    DialogBoxParamA(GetModuleHandleA(NULL), MAKEINTRESOURCEA(208), NULL, H_PROC, 0);
    WaitForSingleObject(thread, 15000);
    CloseHandle(thread);
    h_check(h_sex() == VV_SEX_LAYOUT[HARNESS_GAME].female, "No on the warning changed nothing");
}

int main(int argc, char **argv) {
    if (!harness_redirect_documents_process()) {
        printf("FAIL: Documents not redirected to a throwaway folder; not running\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    if (!h_covered(0x50E000u, 150u * 0x2E3Cu + 0x1000u) || !h_covered(0x6E0000u, 0x1000u)
        || !h_covered(0x728000u, 0x1000u) || !h_covered(0x7B1000u, 0x1000u)) {
        printf("FAIL: the backing block %p does not cover the game's addresses (link fixed at 0x400000)\n",
               (void *)h_backing);
        return 2;
    }
    h_record = (unsigned char *)VirtualAlloc(NULL, 0x4000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    module_instance = GetModuleHandleA(NULL);
    if (argc >= 3 && lstrcmpA(argv[1], "shots") == 0) {
        h_shots = 1;
        lstrcpynA(h_folder, argv[2], sizeof h_folder);
        h_shot(0);
        h_shot(1);
        h_gp_shot();
    } else {
        h_tests();
    }
    printf("game %d: %d checks, %d failures\n", HARNESS_GAME, h_checks, h_failures);
    if (h_checks == 0) {
        return 2;
    }
    return h_failures == 0 ? 0 : 1;
}
