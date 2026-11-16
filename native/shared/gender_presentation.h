/* gender_presentation.h -- what "VVFP Gender Presentation.dll" (native/vvfp_gender_presentation) offers the
   Change Appearance windows and the Custom Island Event engine (the owner, 2026-11-15).

   A villager keeps the sex the game records for them and may be drawn with the other sex's heads and bodies (the
   same head and body rows: every game has as many rows on each sex's sheets).  The choice is kept per villager in the
   patcher's own per-save file and follows them (deaths, reloads, renames, a sex change); Start Over clears it.  The
   game's sex field is never written for it.

   The DLL is shipped by each game's "Change Sex and Gender Presentation" row (on in Owner's Defaults only), started
   by VVFP Startup.dll.  The same row gates Change Appearance's "Change sex..." button: both are offered only when the
   DLL is in the game (vvfp_gp_find).  The window and the engine find it with GetModuleHandleA. */
#ifndef VVFP_GENDER_PRESENTATION_H
#define VVFP_GENDER_PRESENTATION_H

#define VVFP_GP_DLL "VVFP Gender Presentation.dll"

/* The Change Appearance checkbox (inside appearance_extras.h's 3500..3539) and its words. */
#define VVFP_AX_PRESENTATION 3507
#define VVFP_AX_PRESENTATION_LABEL "Gender presentation: use the other sex's look"
#define VVFP_GP_TITLE "Gender presentation"

/* int __stdcall VvfpGenderPresentationInstalled(int game): 1 when that game's draws follow the choice. */
#define VVFP_GP_INSTALLED "VvfpGenderPresentationInstalled"
/* int __stdcall VvfpGenderPresentationGet(int game, const void *record): 1 when the villager in `record` is drawn
   with the other sex's look; 0 otherwise (nothing kept, or the village not known yet). */
#define VVFP_GP_GET "VvfpGenderPresentationGet"
/* int __stdcall VvfpGenderPresentationSet(int game, const void *record, int on): keep `on` (0 or 1) for that
   villager; 1 when the file says so, 0 when nothing changed (refused for the Golden Child, The Secret City's Tribal
   Chief and stand-in, New Believers' story villagers; no village known; a failed write). */
#define VVFP_GP_SET "VvfpGenderPresentationSet"

#ifndef RC_INVOKED
typedef int (__stdcall *vvfp_gp_installed_fn)(int game);
typedef int (__stdcall *vvfp_gp_get_fn)(int game, const void *record);
typedef int (__stdcall *vvfp_gp_set_fn)(int game, const void *record, int on);

typedef struct {
    int there;                   /* the DLL is in the game: the row is on (Change sex is offered) */
    vvfp_gp_get_fn get;          /* ...and its draws follow the choice (the checkbox is offered); else NULL */
    vvfp_gp_set_fn set;
} vvfp_gp_api;

/* Asked each time a Change Appearance window opens (the DLL is never unloaded).  1 when the checkbox may be offered. */
static int vvfp_gp_find(int game, vvfp_gp_api *api) {
    HMODULE dll = GetModuleHandleA(VVFP_GP_DLL);
    vvfp_gp_installed_fn installed;
    api->there = dll != NULL;
    api->get = NULL;
    api->set = NULL;
    if (dll == NULL) {
        return 0;
    }
    installed = (vvfp_gp_installed_fn)(void *)GetProcAddress(dll, VVFP_GP_INSTALLED);
    if (installed == NULL || !installed(game)) {
        return 0;
    }
    api->get = (vvfp_gp_get_fn)(void *)GetProcAddress(dll, VVFP_GP_GET);
    api->set = (vvfp_gp_set_fn)(void *)GetProcAddress(dll, VVFP_GP_SET);
    if (api->get == NULL || api->set == NULL) {
        api->get = NULL;
        api->set = NULL;
        return 0;
    }
    return 1;
}

/* The sex value a villager whose field holds `sex` is drawn with in `game` (A New Home and The Lost Children: 1 male,
   2 female; the later games 0 male, 1 female) when `on`: the other one.  A value that is neither is kept. */
static int vvfp_gp_drawn_sex(int game, int sex, int on) {
    int male = game <= 2 ? 1 : 0, female = game <= 2 ? 2 : 1;
    if (!on) {
        return sex;
    }
    return sex == male ? female : sex == female ? male : sex;
}

/* The message when the choice cannot be kept for `name` (`special`: a story villager), in `out` (512 bytes). */
static void vvfp_gp_refused_text(char *out, const char *name, int special) {
    if (special) {
        wsprintfA(out, "%s is a story villager, so %s's look stays as the game draws it.", name, name);
    } else {
        wsprintfA(out, "The look could not be kept: the patcher's file for this save could not be written. "
                  "Nothing was changed.");
    }
}

/* ---- the per-villager Change Appearance window (all five games) ------------------------------------------------

   The window shows, when the row is on (the DLL is in the game):
     * "Change sex..." (sex_change_ui.h) -- never for the Golden Child;
     * the checkbox "Gender presentation: use the other sex's look" (VVFP_AX_PRESENTATION) when the game's draws
       follow it -- never for the Golden Child.  Ticking it shows the other sex's head and body in the preview at
       once; OK keeps it (free, like Change sex: an OK with nothing else changed is no change to charge); Cancel and
       Undo changes put it back.  A story villager (sex_change.h) is told why and the box stays as it was.
   Without the row both are hidden (the checkbox row stays empty). */
/* int __stdcall VvfpBornFemale(int game, const void *record): 1 when the villager was born female -- the birth sex
   the DLL keeps by identity (written at each sex change, following renames), else the Sex Changes log's, else the
   sex now. */
#define VVFP_GP_BORN_FEMALE "VvfpBornFemale"
typedef int (__stdcall *vvfp_gp_born_female_fn)(int game, const void *record);

#ifdef VV_SEX_CHANGE_H
/* Was the villager in `record` born female?  The DLL's answer when it is in the game; the log's otherwise
   (native/shared/sex_change.h vv_sex_born_female_by_log). */
static int vvfp_born_female(int game, const unsigned char *record) {
    HMODULE dll = GetModuleHandleA(VVFP_GP_DLL);
    vvfp_gp_born_female_fn born = dll != NULL
        ? (vvfp_gp_born_female_fn)(void *)GetProcAddress(dll, VVFP_GP_BORN_FEMALE) : NULL;
    return born != NULL ? born(game, record) == 1 : vv_sex_born_female_by_log(game, record);
}

typedef struct {
    vvfp_gp_api api;
    int offered;                 /* the checkbox is shown */
    int on;                      /* what the preview shows now */
    int was;                     /* what is kept for the villager */
} vvfp_gp_window;

/* As the window opens for villager `record` of `game`. */
static void vvfp_gp_window_open(vvfp_gp_window *w, int game, const unsigned char *record) {
    w->offered = vvfp_gp_find(game, &w->api) && record != NULL && !vv_sex_golden_child(game, record);
    w->on = w->was = w->offered ? (w->api.get(game, record) == 1) : 0;
}

/* WM_INITDIALOG (and after Undo changes): the two controls shown or hidden, the box checked as `on` says. */
static void vvfp_gp_window_show(HWND window, const vvfp_gp_window *w, int game, const unsigned char *record) {
    HWND sex = GetDlgItem(window, 3506), box = GetDlgItem(window, VVFP_AX_PRESENTATION);
    if (sex != NULL) {
        ShowWindow(sex, w->api.there && record != NULL && !vv_sex_golden_child(game, record) ? SW_SHOW : SW_HIDE);
    }
    if (box != NULL) {
        ShowWindow(box, w->offered ? SW_SHOW : SW_HIDE);
    }
    CheckDlgButton(window, VVFP_AX_PRESENTATION, w->on ? BST_CHECKED : BST_UNCHECKED);
}

#ifndef VVFP_GP_MESSAGE_BOX
#define VVFP_GP_MESSAGE_BOX MessageBoxA
#endif

/* The checkbox clicked: 1 when the preview must be drawn again (the choice changed). */
static int vvfp_gp_window_toggle(HWND window, vvfp_gp_window *w, int game, const unsigned char *record) {
    char name[64], text[512];
    int want = IsDlgButtonChecked(window, VVFP_AX_PRESENTATION) == BST_CHECKED;
    if (!w->offered) {
        return 0;
    }
    if (want && vv_sex_change_refusal(game, record, -1) != VV_SEX_OK) {
        vv_sex_name(game, record, name);
        vvfp_gp_refused_text(text, name, 1);
        (void)VVFP_GP_MESSAGE_BOX(window, text, VVFP_GP_TITLE, MB_OK | MB_ICONINFORMATION);
        CheckDlgButton(window, VVFP_AX_PRESENTATION, w->on ? BST_CHECKED : BST_UNCHECKED);
        return 0;
    }
    if (want == w->on) {
        return 0;
    }
    w->on = want;
    return 1;
}

/* The sex value the preview draws villager `record` with. */
static int vvfp_gp_window_sex(const vvfp_gp_window *w, int game, const unsigned char *record) {
    return vvfp_gp_drawn_sex(game, *(const int *)(record + VV_SEX_LAYOUT[game].sex), w->on);
}

/* OK: keep the choice when it changed.  1 when kept (or nothing to keep); a failure is told and 0 returned. */
static int vvfp_gp_window_keep(HWND window, vvfp_gp_window *w, int game, const unsigned char *record) {
    char text[512];
    if (!w->offered || w->on == w->was) {
        return 1;
    }
    if (w->api.set(game, record, w->on) == 1) {
        w->was = w->on;
        return 1;
    }
    vvfp_gp_refused_text(text, "", 0);
    (void)VVFP_GP_MESSAGE_BOX(window, text, VVFP_GP_TITLE, MB_OK | MB_ICONWARNING);
    return 0;
}

static int vvfp_gp_window_changed(const vvfp_gp_window *w) {
    return w->offered && w->on != w->was;
}
#endif
#endif

#endif /* VVFP_GENDER_PRESENTATION_H */
