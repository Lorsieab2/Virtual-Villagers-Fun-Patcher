/* VVFP Original Look -- each villager's original head, body and mask, for Change Appearance's "Reset to
   original" (the owner, 2026-10-28: Change Appearance and Change Appearance for All put a villager back to
   the look they had before any Change Appearance or island event changed them, the head look on Auto).

   ONE FEATURE, ONE DLL.  The Reset buttons are in each game's Origins Change Appearance windows, which ask
   this DLL (native/shared/original_look.h: VvfpOriginalLookGet) and do the reset -- and log it -- themselves.
   This DLL only keeps the originals (original_look_store.inc: the patcher's own per-save file, following each
   villager).  It is shipped by its own catalog row (on by default; it brings the Origins row with it) and
   started by VVFP Startup.dll (its second word of companions, native/shared/startup_companions_2.h).

   SEEING THE VILLAGERS.  This DLL writes NOTHING into the game: no executable byte, no record byte.  It looks
   at the village from the game's own thread, between frames: VvfpStartup (called by VVFP Startup.dll on the
   game's thread, before the title screen) sets a WH_GETMESSAGE hook on that thread only, which Windows calls
   each time the game takes a message from its queue, and a thread timer (SetTimer, no window, no procedure)
   so that a message comes at least every OL_SYNC_MS even while nobody touches the mouse.  At most once per
   OL_SYNC_MS the store reads the villager records -- the same reads the head look makes at its draws -- and
   records the look of anyone it sees for the first time: a birth, an arrival (an island event's newcomer,
   a Barrel of Babies' child, a Lost Children's child found), or, the first time a village is bound, everyone
   already in it.  So no villager-creation site of any game is hooked, and none needs to be proven reached:
   a newcomer is seen at the first message after the frame that made them, whichever routine made them.

   Each game's records: A New Home and The Lost Children keep a pointer to their array ([0x48B614],
   [0x499F24], 256 records); The Secret City, The Tree of Life and New Believers a manager the executable
   names (native/shared/vv3/4/5_villager_table.h: 150 records, or 256 in the 256 Villagers build) -- the same
   as "VVFP Head Look.dll" (native/vvfp_head_look/vvfp_head_look.c), whose identity rules this DLL shares.
   The mask is the game's Origins companion's (VvfpMaskOf; native/shared/original_look.h says which). */
#include <windows.h>
#include <string.h>
#include "../shared/sidecar_io.h"
#include "../shared/save_folder.h"
#include "../shared/per_save_data.h"
#include "../shared/mask_follow.h"
#include "../shared/foreign_sidecar.h"
#include "../shared/game_save_slot.h"
#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/original_look.h"

#define OL_MAX 256

static int g_game;                  /* the game this process is (VvfpStartup), 0 before */

#include "original_look_records.inc"

/* Each game's Origins companion, which keeps the masks (native/shared/mask_line.h VV_MASK_ORIGINS). */
static const char *const ORIGINS[6] = {
    NULL, "VVFP VV1 Origins Icons.dll", "VVFP VV2 Origins Icons.dll", "VVFP Origins Icons.dll",
    "VVFP VV4 Origins Icons.dll", "VVFP Origins Icons.dll",
};

/* "<stem><slot>.ldw", each game's own save (scripts/vvfp_consistency_check.py SAVE_STEMS). */
static const char *const SAVE_STEMS[6] = {
    NULL, "Virtual Villagers", "Virtual Villagers - The Lost Children", "Virtual Villagers - The Secret City",
    "Virtual Villagers - The Tree of Life", "Virtual Villagers - New Believers",
};

static unsigned int g_records;      /* record 0 */
static int g_count;                 /* records in this build: 150 or 256 */
static int g_table_read;            /* The Secret City to New Believers: the table is read once */

static void ol_locate(void) {
    const unsigned char *image = (const unsigned char *)(UINT_PTR)0x400000u;
    unsigned int rva = 0, slots = 0;
    if (g_table_read) {
        return;
    }
    switch (g_game) {
    case 1:
        g_records = *(const unsigned int *)(UINT_PTR)0x48B614u;
        g_count = 256;
        return;
    case 2:
        g_records = *(const unsigned int *)(UINT_PTR)0x499F24u;
        g_count = 256;
        return;
    case 3:
        vv3_villager_table(image, &rva, &slots);
        g_records = 0x400000u + rva + 0x14u;
        break;
    case 4:
        vv4_villager_table(image, &rva, &slots);
        g_records = 0x400000u + rva + 0x44u;
        break;
    case 5:
        vv5_villager_table(image, &rva, &slots);
        g_records = 0x400000u + rva + 0x48u;
        break;
    default:
        g_records = 0;
        g_count = 0;
        return;
    }
    g_count = (int)slots;
    g_table_read = 1;
}

static int ol_game(void) {
    return g_game;
}

static int ol_slots(void) {
    ol_locate();
    return g_count < OL_MAX ? g_count : OL_MAX;
}

static const unsigned char *ol_record(int i) {
    ol_locate();
    if (g_records == 0 || i < 0 || i >= g_count) {
        return NULL;
    }
    return (const unsigned char *)(UINT_PTR)(g_records + (unsigned int)i * LAYOUT[g_game].stride);
}

/* The slot the game itself saves to (native/shared/game_save_slot.h). */
static int ol_slot_now(void) {
    return vv_game_save_slot(g_game);
}

typedef int (__stdcall *ol_mask_of_fn)(void *record);

/* The villager's head and body, and the mask the game's Origins companion keeps on them: 0 while that
   companion is not loaded (the mask cannot be told, so nothing is recorded yet). */
static int ol_look(const unsigned char *r, int *head, int *body, int *mask) {
    HMODULE origins = GetModuleHandleA(ORIGINS[g_game]);
    ol_mask_of_fn mask_of = origins != NULL ? (ol_mask_of_fn)GetProcAddress(origins, "VvfpMaskOf") : NULL;
    if (mask_of == NULL) {
        return 0;
    }
    memcpy(head, r + LAYOUT[g_game].head, 4);
    memcpy(body, r + LAYOUT[g_game].body, 4);
    *mask = mask_of((void *)r);
    return 1;
}

/* When the game last wrote the slot's own save, "<save folder>\<stem><slot>.ldw". */
static int ol_save_written(int slot, FILETIME *out) {
    char path[MAX_PATH];
    WIN32_FILE_ATTRIBUTE_DATA data;
    int tail = lstrlenA(SAVE_STEMS[g_game]) + 8;
    if (slot < 1 || slot > 5 || !vv_save_folder(path, tail)) {
        return 0;
    }
    lstrcatA(path, "\\");
    lstrcatA(path, SAVE_STEMS[g_game]);
    path[lstrlenA(path) + 1] = '\0';
    path[lstrlenA(path)] = (char)('0' + slot);
    lstrcatA(path, ".ldw");
    if (!GetFileAttributesExA(path, GetFileExInfoStandard, &data)) {
        return 0;
    }
    *out = data.ftLastWriteTime;
    return 1;
}

#include "original_look_store.inc"

/* ---- the look between frames ---------------------------------------------------------------------- */

static HHOOK g_hook;
static int g_busy;

/* Every message the game's thread takes: a look at the village, at most every OL_SYNC_MS. */
static LRESULT CALLBACK ol_message(int code, WPARAM wparam, LPARAM lparam) {
    if (code >= 0 && !g_busy) {
        g_busy = 1;
        (void)ol_sync(0);
        g_busy = 0;
    }
    return CallNextHookEx(g_hook, code, wparam, lparam);
}

/* ---- exports ------------------------------------------------------------------------------------- */

/* Called once at game start by "VVFP Startup.dll" (its second word), on the game's own thread, outside
   DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_game != 0 || game < 1 || game > 5) {
        return;
    }
    g_game = game;
    g_hook = SetWindowsHookExA(WH_GETMESSAGE, ol_message, NULL, GetCurrentThreadId());
    if (g_hook != NULL) {
        (void)SetTimer(NULL, 0, OL_SYNC_MS, NULL);
    }
}

int __stdcall VvfpOriginalLookGet(int game, const void *record, int *head, int *body, int *mask) {
    int h, b, m, known;
    if (g_game == 0 || game != g_game || g_busy) {
        return 0;
    }
    g_busy = 1;
    known = ol_get((const unsigned char *)record, &h, &b, &m);
    g_busy = 0;
    if (!known || head == NULL || body == NULL || mask == NULL) {
        return 0;
    }
    *head = h;
    *body = b;
    *mask = m;
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
