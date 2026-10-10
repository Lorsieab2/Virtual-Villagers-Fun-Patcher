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
#include "startup_companions.h" /* only the companions this build ships */
#include "patcher_files.h"       /* the patcher's folder; full-path, wide loads */

#define VVFP_STORY_DLL "VVFP Story Upgrades.dll"
/* The Pick Island Event button the Tech menu gains while the row is active.
   Clear of every control id the Origins dialogs use (buttons 1000+row,
   badges 1100+row, pickers 2000-2023, bitmaps 3000s). */
#define VVFP_STORY_PICK_ID 4090
/* The Custom Island Event button, beside it. */
#define VVFP_STORY_CUSTOM_ID 4091
/* The Choose Time Skip Amount button (4092 is The Lost Children's Pick Gong
   of Wonder Outcome). */
#define VVFP_STORY_TIME_SKIP_ID 4093

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
    /* Choose Time Skip Amount: NULL in a companion that does not offer it.
       time_skip_step(years) runs this companion's own Time Warp advance for
       min(years, the years one Time Warp buys at the current speed) and
       returns the years advanced; 0 when there is no village to advance,
       -1 when the game is paused or its speed unknown (nothing changed).
       time_skip_settled() is 1 once the game's own villager tick has run
       since the last step (so its catch-up has replayed that step). */
    int (__stdcall *time_skip_step)(int years);
    int (__stdcall *time_skip_settled)(void);
} vvfp_story_host;
static const vvfp_story_host *vvfp_story_host_table(void);

/* For the log exporters' "Mask:" line (the owner, 2026-10-06: a villager's
   mask in every villager record and snapshot): the mask this companion keeps
   on `record` -- 0 none, 1 Blue, 2 Orange, 3 Red, 4 Purple, 5 the Tribal
   Chief's -- through the same store the Story companion is given. */
int __stdcall VvfpMaskOf(void *record) {
    const vvfp_story_host *host = vvfp_story_host_table();
    return record != NULL && host->mask_get != NULL ? host->mask_get(record) : 0;
}

typedef int (__stdcall *vvfp_story_install_fn)(int game);
typedef int (__stdcall *vvfp_story_active_fn)(int game);
typedef int (__stdcall *vvfp_story_pick_fn)(int game, HWND owner);
typedef int (__stdcall *vvfp_story_attach_fn)(int game, const vvfp_story_host *host);
typedef void (__stdcall *vvfp_story_charge_fn)(int game);

static int vvfp_story_state;     /* 0 = not tried, 1 = loaded, -1 = unavailable */
static vvfp_story_install_fn vvfp_story_install;
static vvfp_story_install_fn vvfp_story_arm;
static vvfp_story_active_fn vvfp_story_active;
static vvfp_story_pick_fn vvfp_story_pick;
static vvfp_story_pick_fn vvfp_story_custom;
/* Choose Time Skip Amount: NULL in a Story DLL older than that upgrade. */
static vvfp_story_pick_fn vvfp_story_time_skip;
static vvfp_story_attach_fn vvfp_story_attach;
/* "Story / Cheat Upgrades cost Tech Points": NULL in a Story DLL older
   than that row (it then never charges). */
static vvfp_story_charge_fn vvfp_story_charge;
static vvfp_story_active_fn vvfp_story_installed;
static vvfp_story_active_fn vvfp_story_event_price;

static int vvfp_story_load(void) {
    HMODULE module;
    if (vvfp_story_state != 0) {
        return vvfp_story_state == 1;
    }
    vvfp_story_state = -1;
    module = vvfp_startup_ships(VVFP_STORY_DLL) ? vvfp_load_patcher_dll(VVFP_STORY_DLL) : NULL;
    if (module == NULL) {
        return 0;                     /* not shipped: the row is off */
    }
    vvfp_story_install = (vvfp_story_install_fn)GetProcAddress(module, "VvfpStoryInstall");
    vvfp_story_arm = (vvfp_story_install_fn)GetProcAddress(module, "VvfpStoryArm");
    vvfp_story_active = (vvfp_story_active_fn)GetProcAddress(module, "VvfpStoryActive");
    vvfp_story_pick = (vvfp_story_pick_fn)GetProcAddress(module, "VvfpStoryPickIslandEvent");
    vvfp_story_custom = (vvfp_story_pick_fn)GetProcAddress(module, "VvfpStoryCustomIslandEvent");
    vvfp_story_time_skip = (vvfp_story_pick_fn)GetProcAddress(module, "VvfpStoryChooseTimeSkip");
    vvfp_story_attach = (vvfp_story_attach_fn)GetProcAddress(module, "VvfpStoryAttachHost");
    vvfp_story_charge = (vvfp_story_charge_fn)GetProcAddress(module, "VvfpStoryCharge");
    vvfp_story_installed = (vvfp_story_active_fn)GetProcAddress(module, "VvfpStoryInstalled");
    vvfp_story_event_price = (vvfp_story_active_fn)GetProcAddress(module, "VvfpStoryEventPrice");
    if (vvfp_story_install == NULL || vvfp_story_arm == NULL || vvfp_story_active == NULL || vvfp_story_pick == NULL
        || vvfp_story_custom == NULL || vvfp_story_attach == NULL) {
        return 0;
    }
    vvfp_story_state = 1;
    return 1;
}

/* Load, hand it this companion's slot and mask store (once), and install
   for `game` -- nothing else: no tick.  What the companion's VvfpStartup
   export runs at game start (from "VVFP Startup.dll", at the executable's
   call of WinMain), before any village exists, so the story detours are in
   place for the first load-time catch-up.  Returns whether it is active. */
static int vvfp_story_startup(int game) {
    static int attached;
    if (!vvfp_story_load()) {
        return 0;
    }
    if (!attached) {
        attached = 1;
        vvfp_story_attach(game, vvfp_story_host_table());
        /* The patcher's "cost Tech Points" row: before the install, so the
           zero prices are never written. */
        if (vvfp_story_charge != NULL && vvfp_startup_known
            && (vvfp_startup_shipped & VVFP_STARTUP_STORY_CHARGES) != 0u) {
            vvfp_story_charge(game);
        }
    }
    return vvfp_story_arm(game) != 0;
}

/* The same (a no-op once game start has made it), then the story
   companion's tick; whether the upgrades are free.  Called every frame from
   the companion's per-frame path. */
static int vvfp_story_bridge(int game) {
    if (!vvfp_story_startup(game)) {
        return 0;
    }
    return vvfp_story_install(game) != 0;
}

/* Whether this game's Origins upgrades cost 0 right now. */
static int vvfp_story_free(int game) {
    return vvfp_story_load() && vvfp_story_active(game) != 0;
}

/* Whether the story buttons are offered: the row is in place, free or
   charged ("cost Tech Points"). */
static int vvfp_story_offered(int game) {
    if (!vvfp_story_load()) {
        return 0;
    }
    return vvfp_story_installed != NULL ? vvfp_story_installed(game) != 0 : vvfp_story_active(game) != 0;
}

/* A story button's label: "<what> (<price> tech points)...", the price
   what the Story DLL charges for it now (0, or the Island Event's). */
static const char *vvfp_story_label(int game, const char *what, char *out, int size) {
    int price = vvfp_story_event_price != NULL ? vvfp_story_event_price(game) : 0;
    if (price >= 1000) {
        wsprintfA(out, "%s (%d,%03d tech points)...", what, price / 1000, price % 1000);
    } else {
        wsprintfA(out, "%s (%d tech points)...", what, price);
    }
    (void)size;
    return out;
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

/* Whether Choose Time Skip Amount is offered: the row is in place, the
   Story DLL has the upgrade and this companion can advance its clock. */
static int vvfp_story_time_skip_offered(int game) {
    const vvfp_story_host *host = vvfp_story_host_table();
    return vvfp_story_offered(game) && vvfp_story_time_skip != NULL && host->time_skip_step != NULL
        && host->time_skip_settled != NULL;
}

/* Whether a story button already covers the rectangle `want`. */
static int vvfp_story_button_overlaps(HWND dialog, const RECT *want) {
    static const int ids[] = { VVFP_STORY_PICK_ID, VVFP_STORY_CUSTOM_ID, 4092 };
    int i;
    for (i = 0; i < (int)(sizeof ids / sizeof ids[0]); ++i) {
        HWND button = GetDlgItem(dialog, ids[i]);
        RECT rc, overlap;
        if (button == NULL) {
            continue;
        }
        GetWindowRect(button, &rc);
        MapWindowPoints(NULL, dialog, (POINT *)&rc, 2);
        if (IntersectRect(&overlap, &rc, want)) {
            return 1;
        }
    }
    return 0;
}

/* The Choose Time Skip Amount button: right of Cancel when that is free and
   inside the dialog, otherwise above the Custom Island Event button. */
static void vvfp_story_add_time_skip_button(int game, HWND dialog) {
    HWND cancel = GetDlgItem(dialog, IDCANCEL);
    HWND custom = GetDlgItem(dialog, VVFP_STORY_CUSTOM_ID);
    RECT rc, unit = { 0, 0, 120, 4 }, client, want;
    int width, gap, height;
    char label[96];
    if (!vvfp_story_time_skip_offered(game) || cancel == NULL
        || GetDlgItem(dialog, VVFP_STORY_TIME_SKIP_ID) != NULL) {
        return;
    }
    vvfp_story_label(game, "Choose Time Skip Amount", label, sizeof label);
    GetWindowRect(cancel, &rc);
    MapWindowPoints(NULL, dialog, (POINT *)&rc, 2);
    MapDialogRect(dialog, &unit);
    GetClientRect(dialog, &client);
    width = unit.right;
    gap = unit.bottom * 2;
    height = rc.bottom - rc.top;
    SetRect(&want, rc.right + gap, rc.top, rc.right + gap + width, rc.bottom);
    if (want.right <= client.right - unit.bottom && !vvfp_story_button_overlaps(dialog, &want)) {
        vvfp_story_button(dialog, label, VVFP_STORY_TIME_SKIP_ID, want.left, want.top, width, height);
        return;
    }
    if (custom != NULL) {
        GetWindowRect(custom, &rc);
        MapWindowPoints(NULL, dialog, (POINT *)&rc, 2);
    }
    SetRect(&want, rc.left, rc.top - height - unit.bottom, rc.left + width, rc.top - unit.bottom);
    while (want.top >= 0 && vvfp_story_button_overlaps(dialog, &want)) {
        OffsetRect(&want, 0, -(height + unit.bottom));
    }
    vvfp_story_button(dialog, label, VVFP_STORY_TIME_SKIP_ID, want.left, want.top, width, height);
}

static void vvfp_story_add_event_buttons(int game, HWND dialog);

static void vvfp_story_add_pick_button(int game, HWND dialog) {
    vvfp_story_add_event_buttons(game, dialog);
    vvfp_story_add_time_skip_button(game, dialog);
}

static void vvfp_story_add_event_buttons(int game, HWND dialog) {
    HWND cancel = GetDlgItem(dialog, IDCANCEL);
    RECT rc;
    RECT unit = { 0, 0, 120, 4 };
    RECT client;
    int width;
    int gap;
    int x;
    int height;
    char custom_label[96];
    char pick_label[96];
    if (!vvfp_story_offered(game) || cancel == NULL || GetDlgItem(dialog, VVFP_STORY_PICK_ID) != NULL) {
        return;
    }
    vvfp_story_label(game, "Custom Island Event", custom_label, sizeof custom_label);
    vvfp_story_label(game, "Pick Island Event", pick_label, sizeof pick_label);
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
        vvfp_story_button(dialog, custom_label, VVFP_STORY_CUSTOM_ID, x, rc.top, width, height);
        vvfp_story_button(dialog, pick_label, VVFP_STORY_PICK_ID, x + width + gap, rc.top, width, height);
        return;
    }
    x = rc.left - width - gap;
    if (x < unit.bottom) {
        x = rc.right + gap;
        if (x + width > client.right - unit.bottom) {
            width = client.right - unit.bottom - x;
        }
    }
    vvfp_story_button(dialog, pick_label, VVFP_STORY_PICK_ID, x, rc.top, width, height);
    vvfp_story_button(dialog, custom_label, VVFP_STORY_CUSTOM_ID,
                      x, rc.top - height - unit.bottom, width, height);
}

/* Whether `command` is one of the story buttons vvfp_story_pick_clicked
   handles. */
#define VVFP_STORY_COMMAND(command) \
    ((command) == VVFP_STORY_PICK_ID || (command) == VVFP_STORY_CUSTOM_ID \
     || (command) == VVFP_STORY_TIME_SKIP_ID)

/* The Pick Island Event, Custom Island Event or Choose Time Skip Amount
   button (`command`) was clicked.  `blocked_reason` is the text the Island Event row would show for
   its own lock, or NULL when it is not locked: both share that lock.
   Returns 1 when an event is now on its way (the caller closes the menu). */
static int vvfp_story_pick_clicked(int game, HWND dialog, int command, const char *blocked_reason) {
    if (!vvfp_story_offered(game)) {
        return 0;
    }
    if (command == VVFP_STORY_TIME_SKIP_ID) {
        /* Not an island event: the Island Event row's lock does not apply. */
        return vvfp_story_time_skip_offered(game) && vvfp_story_time_skip(game, dialog) == 1;
    }
    if (blocked_reason != NULL) {
        MessageBoxA(dialog, blocked_reason, "Not right now", MB_OK | MB_ICONINFORMATION);
        return 0;
    }
    if (command == VVFP_STORY_CUSTOM_ID) {
        return vvfp_story_custom(game, dialog) == 1;
    }
    return vvfp_story_pick(game, dialog) == 1;
}

#endif
