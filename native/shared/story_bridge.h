/* The Origins companions' side of "Story / Cheat Upgrades".

   "VVFP Story Upgrades.dll" ships only with the Story / Cheat Upgrades row.
   Each game's Origins companion loads it by full path from the executable's
   own directory (never by a bare name), outside DllMain, and asks it to
   install for that game.  It is installed only when EVERY site it writes
   holds exactly the bytes the Origins payload put there; only then does
   VvfpStoryActive answer 1, and only then does this companion show and
   charge 0 for its own upgrades and offer Pick Island Event.  Not shipped
   (the row is off), or refused: nothing changes, the normal prices apply.

   Included once per companion; everything is file-static. */
#ifndef VVFP_STORY_BRIDGE_H
#define VVFP_STORY_BRIDGE_H

#include <windows.h>
#include <string.h>

#define VVFP_STORY_DLL "VVFP Story Upgrades.dll"
/* The Pick Island Event button the Tech menu gains while the row is active.
   Clear of every control id the Origins dialogs use (buttons 1000+row,
   badges 1100+row, pickers 2000-2023, bitmaps 3000s). */
#define VVFP_STORY_PICK_ID 4090
/* The Custom Island Event button, beside it. */
#define VVFP_STORY_CUSTOM_ID 4091
/* The Lost Children only: the Pick Gong of Wonder Outcome button, above them.
   It is not an island event and does not share the Island Event row's lock. */
#define VVFP_STORY_GONG_ID 4092

/* What the story companion asks of the Origins companion that hosts it: the
   save slot this companion keys its own sidecars by, and its own mask store
   (the Heathen masks are the Origins companion's, never game data).  Each
   Origins companion defines vvfp_story_host_table() after including this
   header. */
typedef struct {
    int size;                                          /* sizeof(vvfp_story_host) */
    int (__stdcall *slot)(void);                       /* 1..5, 0 = no village slot yet */
    int (__stdcall *mask_get)(void *record);           /* 0 = none, 1..5 */
    int (__stdcall *mask_set)(void *record, int mask); /* stored and persisted: 1 */
    void (__stdcall *preferences_changing)(int after); /* NULL, or bracket a likes/dislikes write */
} vvfp_story_host;
static const vvfp_story_host *vvfp_story_host_table(void);

typedef int (__stdcall *vvfp_story_install_fn)(int game);
typedef int (__stdcall *vvfp_story_active_fn)(int game);
typedef int (__stdcall *vvfp_story_pick_fn)(int game, HWND owner);
typedef int (__stdcall *vvfp_story_attach_fn)(int game, const vvfp_story_host *host);

static int vvfp_story_state;     /* 0 = not tried, 1 = loaded, -1 = unavailable */
static vvfp_story_install_fn vvfp_story_install;
static vvfp_story_active_fn vvfp_story_active;
static vvfp_story_pick_fn vvfp_story_pick;
static vvfp_story_pick_fn vvfp_story_custom;
static vvfp_story_pick_fn vvfp_story_gong;      /* NULL: an older story companion */
static vvfp_story_attach_fn vvfp_story_attach;

static int vvfp_story_load(void) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    HMODULE module;
    if (vvfp_story_state != 0) {
        return vvfp_story_state == 1;
    }
    vvfp_story_state = -1;
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    slash = strrchr(path, '\\');
    if (slash == NULL || (size_t)(slash + 1 - path) + sizeof(VVFP_STORY_DLL) > sizeof(path)) {
        return 0;
    }
    lstrcpyA(slash + 1, VVFP_STORY_DLL);
    module = LoadLibraryA(path);
    if (module == NULL) {
        return 0;                     /* not shipped: the row is off */
    }
    vvfp_story_install = (vvfp_story_install_fn)GetProcAddress(module, "VvfpStoryInstall");
    vvfp_story_active = (vvfp_story_active_fn)GetProcAddress(module, "VvfpStoryActive");
    vvfp_story_pick = (vvfp_story_pick_fn)GetProcAddress(module, "VvfpStoryPickIslandEvent");
    vvfp_story_custom = (vvfp_story_pick_fn)GetProcAddress(module, "VvfpStoryCustomIslandEvent");
    vvfp_story_attach = (vvfp_story_attach_fn)GetProcAddress(module, "VvfpStoryAttachHost");
    vvfp_story_gong = (vvfp_story_pick_fn)GetProcAddress(module, "VvfpStoryPickGongOutcome");
    if (vvfp_story_install == NULL || vvfp_story_active == NULL || vvfp_story_pick == NULL
        || vvfp_story_custom == NULL || vvfp_story_attach == NULL) {
        return 0;
    }
    vvfp_story_state = 1;
    return 1;
}

/* Load and install for `game`, once (handing it this companion's slot and
   mask store); then whether the upgrades are free.  Called every frame from
   the companion's per-frame path, which is also the story companion's tick. */
static int vvfp_story_bridge(int game) {
    static int attached;
    if (!vvfp_story_load()) {
        return 0;
    }
    if (!attached) {
        attached = 1;
        vvfp_story_attach(game, vvfp_story_host_table());
    }
    return vvfp_story_install(game) != 0;
}

/* Whether this game's Origins upgrades cost 0 right now. */
static int vvfp_story_free(int game) {
    return vvfp_story_load() && vvfp_story_active(game) != 0;
}

/* A price as this companion shows and charges it: 0 while the row is active. */
static int vvfp_story_price(int game, int price) {
    return vvfp_story_free(game) ? 0 : price;
}

static const char *vvfp_story_price_text(int game, const char *text) {
    return vvfp_story_free(game) ? "0" : text;
}

/* Rewrite every formatted price ("50,000", "1,000,000") in a static text
   that mentions tech points to "0". */
static void vvfp_story_zero_prices(char *text) {
    char out[512];
    int i = 0, o = 0;
    if (strstr(text, "tech point") == NULL) {
        return;
    }
    while (text[i] != '\0' && o < (int)sizeof(out) - 2) {
        if (text[i] >= '0' && text[i] <= '9') {
            int j = i, comma = 0;
            while ((text[j] >= '0' && text[j] <= '9') || (text[j] == ',' && text[j + 1] >= '0'
                                                          && text[j + 1] <= '9')) {
                comma |= text[j] == ',';
                ++j;
            }
            if (comma) {
                out[o++] = '0';
                i = j;
                continue;
            }
        }
        out[o++] = text[i++];
    }
    out[o] = '\0';
    lstrcpynA(text, out, 512);
}

/* A fixed prompt that names a price ("... for 1,000,000 tech points?"),
   with the price shown as 0 while the row is active.  One buffer: the
   prompts are modal and shown one at a time. */
static const char *vvfp_story_text(int game, const char *text) {
    static char buffer[512];
    if (!vvfp_story_free(game)) {
        return text;
    }
    lstrcpynA(buffer, text, sizeof buffer);
    vvfp_story_zero_prices(buffer);
    return buffer;
}

static BOOL CALLBACK vvfp_story_relabel_child(HWND child, LPARAM unused) {
    char cls[16];
    char text[512];
    (void)unused;
    if (GetClassNameA(child, cls, sizeof cls) && lstrcmpiA(cls, "Static") == 0
        && GetWindowTextA(child, text, sizeof text) > 0) {
        char before[512];
        lstrcpynA(before, text, sizeof before);
        vvfp_story_zero_prices(text);
        if (lstrcmpA(before, text) != 0) {
            SetWindowTextA(child, text);
        }
    }
    return TRUE;
}

/* Every price an Origins dialog prints, shown as 0 while the row is active. */
static void vvfp_story_relabel(int game, HWND dialog) {
    if (vvfp_story_free(game)) {
        EnumChildWindows(dialog, vvfp_story_relabel_child, 0);
    }
}

/* Adds the Pick Island Event and Custom Island Event buttons to a Tech
   menu, to the left of its Cancel button (IDCANCEL), while the row is
   active. */
static HWND vvfp_story_button(HWND dialog, const char *text, int id, int x, int y, int width,
                              int height) {
    HWND button = CreateWindowExA(0, "BUTTON", text, WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
                                  x, y, width, height, dialog, (HMENU)(INT_PTR)id, NULL, NULL);
    if (button != NULL) {
        SendMessageA(button, WM_SETFONT, SendMessageA(dialog, WM_GETFONT, 0, 0), TRUE);
    }
    return button;
}

static void vvfp_story_add_pick_button(int game, HWND dialog) {
    HWND cancel = GetDlgItem(dialog, IDCANCEL);
    RECT rc;
    RECT unit = { 0, 0, 120, 4 };
    RECT client;
    int width;
    int gap;
    int x;
    int height;
    if (!vvfp_story_free(game) || cancel == NULL || GetDlgItem(dialog, VVFP_STORY_PICK_ID) != NULL) {
        return;
    }
    GetWindowRect(cancel, &rc);
    MapWindowPoints(NULL, dialog, (POINT *)&rc, 2);
    MapDialogRect(dialog, &unit);
    GetClientRect(dialog, &client);
    width = unit.right;
    gap = unit.bottom * 2;
    height = rc.bottom - rc.top;
    /* Left of Cancel, side by side; in a dialog with no room for both there,
       stacked above Cancel's row on the right, as wide as the dialog allows. */
    x = rc.left - 2 * (width + gap);
    if (x >= unit.bottom) {
        vvfp_story_button(dialog, "Custom Island Event (0 tech points)...", VVFP_STORY_CUSTOM_ID,
                          x, rc.top, width, height);
        vvfp_story_button(dialog, "Pick Island Event (0 tech points)...", VVFP_STORY_PICK_ID,
                          x + width + gap, rc.top, width, height);
        if (game == 2 && vvfp_story_gong != NULL) {
            vvfp_story_button(dialog, "Pick Gong of Wonder Outcome (0 tech points)...",
                              VVFP_STORY_GONG_ID, x + width + gap, rc.top - height - unit.bottom,
                              width, height);
        }
        return;
    }
    x = rc.left - width - gap;
    if (x < unit.bottom) {
        x = rc.right + gap;
        if (x + width > client.right - unit.bottom) {
            width = client.right - unit.bottom - x;
        }
    }
    vvfp_story_button(dialog, "Pick Island Event (0 tech points)...", VVFP_STORY_PICK_ID,
                      x, rc.top, width, height);
    vvfp_story_button(dialog, "Custom Island Event (0 tech points)...", VVFP_STORY_CUSTOM_ID,
                      x, rc.top - height - unit.bottom, width, height);
    if (game == 2 && vvfp_story_gong != NULL) {
        vvfp_story_button(dialog, "Pick Gong of Wonder Outcome (0 tech points)...", VVFP_STORY_GONG_ID,
                          x, rc.top - 2 * (height + unit.bottom), width, height);
    }
}

/* The Pick Island Event or Custom Island Event button (`command`) was
   clicked.  `blocked_reason` is the text the Island Event row would show for
   its own lock, or NULL when it is not locked: both share that lock.
   Returns 1 when an event is now on its way (the caller closes the menu). */
static int vvfp_story_pick_clicked(int game, HWND dialog, int command, const char *blocked_reason) {
    if (!vvfp_story_free(game)) {
        return 0;
    }
    if (blocked_reason != NULL) {
        MessageBoxA(dialog, blocked_reason, "Not right now", MB_OK | MB_ICONINFORMATION);
        return 0;
    }
    if (command == VVFP_STORY_CUSTOM_ID) {
        return vvfp_story_custom(game, dialog) == 1;
    }
    if (command == VVFP_STORY_GONG_ID) {
        return vvfp_story_gong != NULL && vvfp_story_gong(game, dialog) == 1;
    }
    return vvfp_story_pick(game, dialog) == 1;
}

#endif
