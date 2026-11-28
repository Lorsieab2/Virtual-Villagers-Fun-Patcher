/* skin_tone.h -- what "VVFP Skin Tones.dll" (native/vvfp_skin_tones) offers the other companions: the
   Change Appearance windows (each game's Origins DLL), Parentage Export (a conception and a birth) and the
   Revive snapshot (native/shared/revive_snapshot.h).  The numbers and the rule are skin_tone_rules.h's.

   Every caller finds the DLL with GetModuleHandleA (VVFP Startup.dll loads it at game start when the Skin
   Tones row is ticked); without it every call here does nothing and says 0. */
#ifndef VVFP_SKIN_TONE_H
#define VVFP_SKIN_TONE_H

#include "../vvfp_skin_tones/skin_tone_rules.h"

/* The Change Appearance row (inside appearance_extras.h's 3500..3539): "Skin tone:", the list ("Game's
   own", then the ten tones light to dark) and "Reset to birth tone". */
#define VVFP_AX_SKIN_LABEL 3508
#define VVFP_AX_SKIN_LIST  3509
#define VVFP_AX_SKIN_RESET 3515
#define VVFP_SKIN_LABEL_TEXT "Skin tone:"
#define VVFP_SKIN_RESET_TEXT "Reset to birth tone"
#define VVFP_SKIN_TITLE "Skin tone"

#ifndef RC_INVOKED
typedef int (__stdcall *vvfp_skin_game_fn)(int game);
typedef int (__stdcall *vvfp_skin_get_fn)(int game, const void *record);
typedef int (__stdcall *vvfp_skin_set_fn)(int game, const void *record, int tone);
typedef int (__stdcall *vvfp_skin_conceived_fn)(int game, const void *mother, const void *father);
typedef int (__stdcall *vvfp_skin_born_fn)(int game, const void *child, const void *mother, const void *first,
                                           int last);

static HMODULE vvfp_skin_dll(void) {
    return GetModuleHandleA(VVFP_SKIN_TONES_DLL);
}

static FARPROC vvfp_skin_export(const char *name) {
    HMODULE dll = vvfp_skin_dll();
    return dll != NULL ? GetProcAddress(dll, name) : NULL;
}

/* A CONCEPTION (Parentage Export, where the conception is logged): the baby's tone rolled now by the head
   rule on the parents' tones and kept on `carrier` (the villager who carries; `father` the other parent,
   NULL when not known).  It also replaces whatever was kept on the carrier before -- a tone chosen for a
   held baby that vanished.  The tone rolled, or 0. */
static int vvfp_skin_conceived(int game, const void *carrier, const void *father) {
    vvfp_skin_conceived_fn f = (vvfp_skin_conceived_fn)(void *)vvfp_skin_export("VvfpSkinToneConceived");
    return f != NULL && carrier != NULL ? f(game, carrier, father) : 0;
}

/* The tone kept on `carrier` for the baby to come (0: none). */
static int vvfp_skin_pending(int game, const void *carrier) {
    vvfp_skin_get_fn f = (vvfp_skin_get_fn)(void *)vvfp_skin_export("VvfpSkinTonePending");
    return f != NULL && carrier != NULL ? f(game, carrier) : 0;
}

/* A BIRTH (Parentage Export, where the birth is logged): the newborn in `child` gets the tone kept on
   `carrier`, or copies `first` (a twin or triplet: the first baby of the same delivery).  The tone given,
   or 0. */
static int vvfp_skin_born(int game, const void *child, const void *carrier, const void *first, int last) {
    vvfp_skin_born_fn f = (vvfp_skin_born_fn)(void *)vvfp_skin_export("VvfpSkinToneBorn");
    return f != NULL && child != NULL ? f(game, child, carrier, first, last) : 0;
}

/* ---- the Change Appearance windows ---------------------------------------------------------------------- */

typedef struct {
    vvfp_skin_get_fn get;        /* VvfpSkinToneOf: the kept tone (low byte: 0, 1..COUNT, 15) */
    vvfp_skin_set_fn set;        /* VvfpSkinToneSet: keep and log */
    vvfp_skin_get_fn birth;      /* VvfpSkinToneBirth */
} vvfp_skin_api;

/* 1 when the tone may be offered for `game`: the DLL is in the game and that game's draws follow the tone
   (VvfpSkinToneDrawn). */
static int vvfp_skin_find(int game, vvfp_skin_api *api) {
    vvfp_skin_game_fn drawn = (vvfp_skin_game_fn)(void *)vvfp_skin_export("VvfpSkinToneDrawn");
    api->get = NULL;
    api->set = NULL;
    api->birth = NULL;
    if (drawn == NULL || !drawn(game)) {
        return 0;
    }
    api->get = (vvfp_skin_get_fn)(void *)vvfp_skin_export("VvfpSkinToneOf");
    api->set = (vvfp_skin_set_fn)(void *)vvfp_skin_export("VvfpSkinToneSet");
    api->birth = (vvfp_skin_get_fn)(void *)vvfp_skin_export("VvfpSkinToneBirth");
    if (api->get == NULL || api->set == NULL || api->birth == NULL) {
        api->get = NULL;
        api->set = NULL;
        api->birth = NULL;
        return 0;
    }
    return 1;
}

/* The list's entries: 0 "Game's own" (tone 15), then 1..COUNT the tones.  A tone of 0 (none kept yet) shows
   as "Game's own", which is how such a villager is drawn. */
static int vvfp_skin_entry_of(int tone) {
    return tone >= 1 && tone <= VVFP_SKIN_TONE_COUNT ? tone : 0;
}

static int vvfp_skin_tone_of_entry(int entry) {
    return entry >= 1 && entry <= VVFP_SKIN_TONE_COUNT ? entry : VVFP_SKIN_TONE_GAMES_OWN;
}

/* The preview's picture for a stock sheet `own` ("Images\\female_heads00.png" etc.) in `tone` -- the tone's
   copy "Images\\vvfp_skin_NN_<the rest>" when that file is there -- into `out` (MAX_PATH wide characters).
   0 (and `out` the stock name) for the game's own art or a copy that is not there. */
static int vvfp_skin_preview_path(WCHAR *out, const WCHAR *own, int tone) {
    const WCHAR *leaf = own, *p;
    int folder;
    for (p = own; *p; ++p) {
        if (*p == L'\\') {
            leaf = p + 1;
        }
    }
    lstrcpynW(out, own, MAX_PATH);
    if (tone < 1 || tone > VVFP_SKIN_TONE_COUNT) {
        return 0;
    }
    folder = (int)(leaf - own);
    if (folder + 13 + lstrlenW(leaf) >= MAX_PATH) {
        return 0;
    }
    wsprintfW(out + folder, L"vvfp_skin_%02d_%ls", tone, leaf);
    if (GetFileAttributesW(out) == INVALID_FILE_ATTRIBUTES) {
        lstrcpynW(out, own, MAX_PATH);
        return 0;
    }
    return 1;
}

typedef struct {
    vvfp_skin_api api;
    int offered;                 /* the row is shown */
    int tone;                    /* what the preview shows: 1..COUNT, or 15 the game's own */
    int was;                     /* what is kept now (0 none, 1..COUNT, 15) */
} vvfp_skin_window;

/* As the window opens for villager `record` of `game`. */
static void vvfp_skin_window_open(vvfp_skin_window *w, int game, const void *record) {
    w->offered = record != NULL && vvfp_skin_find(game, &w->api);
    w->was = w->offered ? (w->api.get(game, record) & 0xFF) : 0;
    w->tone = vvfp_skin_tone_of_entry(vvfp_skin_entry_of(w->was));
}

/* The tone the preview draws with: 1..COUNT, or 0 for the game's own art. */
static int vvfp_skin_window_drawn(const vvfp_skin_window *w) {
    return w->offered && w->tone >= 1 && w->tone <= VVFP_SKIN_TONE_COUNT ? w->tone : 0;
}

/* WM_INITDIALOG (and after Undo changes): the row filled and shown, or hidden. */
static void vvfp_skin_window_show(HWND window, const vvfp_skin_window *w, int game, const void *record) {
    static const char *const names[VVFP_SKIN_TONE_COUNT] = VVFP_SKIN_TONE_NAMES;
    HWND list = GetDlgItem(window, VVFP_AX_SKIN_LIST);
    int k, show = w->offered ? SW_SHOW : SW_HIDE;
    ShowWindow(GetDlgItem(window, VVFP_AX_SKIN_LABEL), show);
    ShowWindow(GetDlgItem(window, VVFP_AX_SKIN_RESET), show);
    if (list == NULL) {
        return;
    }
    ShowWindow(list, show);
    if (SendMessageA(list, CB_GETCOUNT, 0, 0) == 0) {
        SendMessageA(list, CB_ADDSTRING, 0, (LPARAM)VVFP_SKIN_TONE_GAMES_OWN_NAME);
        for (k = 0; k < VVFP_SKIN_TONE_COUNT; ++k) {
            SendMessageA(list, CB_ADDSTRING, 0, (LPARAM)names[k]);
        }
    }
    SendMessageA(list, CB_SETCURSEL, (WPARAM)vvfp_skin_entry_of(w->tone), 0);
    EnableWindow(GetDlgItem(window, VVFP_AX_SKIN_RESET),
                 w->offered && w->api.birth != NULL && w->api.birth(game, record) != 0);
}

/* WM_COMMAND for one of the row's controls: 1 when the preview must be drawn again (the tone changed). */
static int vvfp_skin_window_command(HWND window, vvfp_skin_window *w, int game, const void *record,
                                    unsigned int id, unsigned int code) {
    int tone;
    if (!w->offered) {
        return 0;
    }
    if (id == VVFP_AX_SKIN_LIST && code == CBN_SELCHANGE) {
        tone = vvfp_skin_tone_of_entry((int)SendDlgItemMessageA(window, VVFP_AX_SKIN_LIST, CB_GETCURSEL, 0, 0));
    } else if (id == VVFP_AX_SKIN_RESET && code == BN_CLICKED) {
        tone = w->api.birth(game, record);
        if (tone == 0) {
            return 0;
        }
        SendDlgItemMessageA(window, VVFP_AX_SKIN_LIST, CB_SETCURSEL, (WPARAM)vvfp_skin_entry_of(tone), 0);
    } else {
        return 0;
    }
    if (tone == w->tone) {
        return 0;
    }
    w->tone = tone;
    return 1;
}

/* Undo changes: back to what is kept. */
static void vvfp_skin_window_undo(vvfp_skin_window *w) {
    w->tone = vvfp_skin_tone_of_entry(vvfp_skin_entry_of(w->was));
}

/* 1 when OK has a tone to keep. */
static int vvfp_skin_window_changed(const vvfp_skin_window *w) {
    return w->offered && w->tone != vvfp_skin_tone_of_entry(vvfp_skin_entry_of(w->was));
}

#ifndef VVFP_SKIN_MESSAGE_BOX
#define VVFP_SKIN_MESSAGE_BOX MessageBoxA
#endif

/* OK: keep the tone when it changed (VvfpSkinToneSet logs "Appearance changed" with "Old skin tone" and "New
   skin tone").  1 when kept (or nothing to keep); a failure is told and 0 returned. */
static int vvfp_skin_window_keep(HWND window, vvfp_skin_window *w, int game, const void *record) {
    if (!vvfp_skin_window_changed(w)) {
        return 1;
    }
    if (w->api.set(game, record, w->tone) == 1) {
        w->was = w->tone;
        return 1;
    }
    (void)VVFP_SKIN_MESSAGE_BOX(window, "The skin tone could not be kept: the patcher's file for this save could "
                                "not be written. Nothing was changed.", VVFP_SKIN_TITLE, MB_OK | MB_ICONWARNING);
    return 0;
}
#endif

#endif /* VVFP_SKIN_TONE_H */
