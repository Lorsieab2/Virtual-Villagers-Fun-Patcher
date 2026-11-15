/* gender_presentation_stand_in.h -- "VVFP Gender Presentation.dll" (native/shared/gender_presentation.h) stood in for
   the Change Appearance harnesses (native/vv1_origins_icons/sex_change_dialog_harness.c,
   native/vv4_origins_icons/sex_change_ui_harness.c).  Test code only: never included by a shipped DLL.

   Include before the companion source, after <windows.h>, with HARNESS_GAME defined.  The harness routes its
   GetModuleHandleA / GetProcAddress through h_gp_module / h_gp_proc, and (with no window on screen) the checkbox
   through h_gp_is_checked / h_gp_check; a scripted press of the checkbox flips it first (h_gp_click), as a real
   AUTOCHECKBOX does before it sends WM_COMMAND. */
#ifndef VVFP_GENDER_PRESENTATION_STAND_IN_H
#define VVFP_GENDER_PRESENTATION_STAND_IN_H

#define H_GP_MODULE ((HMODULE)(UINT_PTR)0x30000)
#define H_GP_BOX 3507                 /* VVFP_AX_PRESENTATION */

static int h_gp_there = 1;            /* the row is on: the DLL is in the game */
static int h_gp_draws = 1;            /* ...and its draws follow the choice */
static int h_gp_fail;                 /* every Set fails (a file that cannot be written) */
static const void *h_gp_record;       /* the villager whose choice is kept */
static int h_gp_on;                   /* ...and what is kept */
static int h_gp_sets;                 /* Set calls */
static int h_gp_box;                  /* the checkbox, when no window is on screen */

static int __stdcall h_gp_installed(int game) {
    return h_gp_draws && game == HARNESS_GAME;
}

static int __stdcall h_gp_get(int game, const void *record) {
    (void)game;
    return record != NULL && record == h_gp_record ? h_gp_on : 0;
}

static int __stdcall h_gp_set(int game, const void *record, int on) {
    (void)game;
    ++h_gp_sets;
    if (h_gp_fail) {
        return 0;
    }
    h_gp_record = record;
    h_gp_on = on;
    return 1;
}

/* A fresh village: nothing kept, the row on, the box clear. */
static void h_gp_reset(void) {
    h_gp_there = 1;
    h_gp_draws = 1;
    h_gp_fail = 0;
    h_gp_record = NULL;
    h_gp_on = 0;
    h_gp_sets = 0;
    h_gp_box = 0;
}

/* GetModuleHandleA for the DLL's name: the stand-in module while the row is on; NULL otherwise.  Other names: -1. */
static HMODULE h_gp_module(LPCSTR name, int *handled) {
    *handled = name != NULL && lstrcmpiA(name, "VVFP Gender Presentation.dll") == 0;
    return *handled && h_gp_there ? H_GP_MODULE : NULL;
}

static FARPROC h_gp_proc(LPCSTR name) {
    if (lstrcmpA(name, "VvfpGenderPresentationInstalled") == 0) return (FARPROC)(void *)h_gp_installed;
    if (lstrcmpA(name, "VvfpGenderPresentationGet") == 0) return (FARPROC)(void *)h_gp_get;
    if (lstrcmpA(name, "VvfpGenderPresentationSet") == 0) return (FARPROC)(void *)h_gp_set;
    return NULL;
}

static UINT WINAPI h_gp_is_checked(HWND window, int id) {
    if (window != NULL) {
        return IsDlgButtonChecked(window, id);
    }
    return id == H_GP_BOX && h_gp_box ? BST_CHECKED : BST_UNCHECKED;
}

static BOOL WINAPI h_gp_check(HWND window, int id, UINT state) {
    if (window != NULL) {
        return CheckDlgButton(window, id, state);
    }
    if (id == H_GP_BOX) {
        h_gp_box = state == BST_CHECKED;
    }
    return TRUE;
}

/* A scripted press of control `id` with no window: the checkbox flips first. */
static void h_gp_click(UINT id) {
    if (id == H_GP_BOX) {
        h_gp_box = !h_gp_box;
    }
}

#endif /* VVFP_GENDER_PRESENTATION_STAND_IN_H */
