/* VVFP Original Look -- each villager's original head, body and mask, for Change Appearance's "Reset to
   original" (the owner, 2026-10-28: Change Appearance and Change Appearance for All put a villager back to
   the look they had before any Change Appearance or island event changed them, the head look on Auto).

   ONE FEATURE, ONE DLL.  The Reset buttons are in each game's Origins Change Appearance windows, which ask
   this DLL (native/shared/original_look.h: VvfpOriginalLookGet) and do the reset -- and log it -- themselves.
   This DLL only keeps the originals (original_look_store.inc: the patcher's own per-save file, following each
   villager).  It is shipped by its own catalog row (on by default; it brings the Origins row with it) and
   started by VVFP Startup.dll (its second word of companions, native/shared/startup_companions_2.h).

   SEEING THE VILLAGERS.  This DLL writes no record byte of its own.  It looks
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
   The mask is the game's Origins companion's (VvfpMaskOf; native/shared/original_look.h says which).

   THE GAME'S OWN CHANGES (the owner, 2026-10-28: "Keep game changes").  Reset to original undoes Change
   Appearance and island events only; a look the game itself gives a villager stays, so it is folded into the
   original (original_look_store.inc ol_game_body).  The game's own writers of a living villager's head, body
   or mask, found by reading every instruction of each stock executable that stores to the record's head or
   body field (directly, or through the record's +0xDC4 / +0x1B8C block) -- tests/test_original_look.py
   GAME_WRITERS lists every one and what it is:
     * villager creation (the founders, a birth, twins, the Golden Child, an arrival): first sight sees them;
     * island events (A New Home's and The Lost Children's crates, The Secret City's event outcomes): never
       folded -- they are not spliced here;
     * the robe: The Secret City's robing 0x45FBC0 (called by the robe's success 0x431FE0, and by the Story /
       Cheat Upgrades' "make the Tribal Chief") gives the new chief the robe, body 29, at 0x45FBDE;
     * the game's clothing dialog (theFernsaceDialog in The Tree of Life and New Believers, by their RTTI;
       the same dialog by its fields in The Lost Children and The Secret City), opened from the village
       (theMainScene 0x43F750 at 0x43F8E9 in The Tree of Life, 0x442350 at 0x44255A in New Believers, after
       0x46CE60 has taken its 5,000 tech points; The Lost Children from 0x42EB48, The Secret City from
       0x4685E5): its OK writes the chosen outfit -- VV2 0x4228E4, VV3 0x41BF89, VV4 0x41961D, VV5 0x419D68
       and its second button 0x419E8E.
   Neither a Change Appearance window (the Origins companions write the record themselves) nor an island
   event reaches those instructions, so a change seen there is the game's own.  Each is spliced, after its
   stock bytes are checked, through the shared all-or-none writer (native/shared/install_sites.h): the
   splice tells the store the body about to be written, then makes the very write the game makes and goes
   on at the next instruction, every register and flag as they were.  A New Home has none in its stock
   executable (its F6 clothing cheat is the developers' own dead code, made live only by the patcher's
   "Reenable F6 Clothing Change Cheat" row: not folded, UNCONFIRMED whether the owner counts it as the
   game's). */
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
#include "../shared/install_sites.h"
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

/* ---- the game's own writers of a villager's body -------------------------------------------------- */

/* Register numbers as x86 encodes them; R_NONE for none. */
enum { R_EAX, R_ECX, R_EDX, R_EBX, R_ESP, R_EBP, R_ESI, R_EDI, R_NONE = 0xFF };

/* `mov [rec_a (+ rec_b) + field], value_reg` (or the immediate `value` when value_reg is R_NONE). */
typedef struct {
    unsigned int va;
    unsigned char length;
    unsigned char rec_a, rec_b, value_reg;
    int value;
    unsigned int field;
    unsigned char stock[10];
} ol_writer;

static const ol_writer VV2_WRITERS[] = {
    /* the clothing dialog's OK: mov [eax+edx+0x54C], ecx (the pool + the villager's offset) */
    { 0x4228E4u, 7, R_EAX, R_EDX, R_ECX, 0, 0x54Cu, { 0x89, 0x8C, 0x10, 0x4C, 0x05, 0x00, 0x00 } },
};
static const ol_writer VV3_WRITERS[] = {
    /* the clothing dialog's OK: mov [eax+0xDF4], ecx */
    { 0x41BF89u, 6, R_EAX, R_NONE, R_ECX, 0, 0xDF4u, { 0x89, 0x88, 0xF4, 0x0D, 0x00, 0x00 } },
    /* the robing 0x45FBC0: mov dword [eax+0xDF4], 29 -- the chief's robe */
    { 0x45FBDEu, 10, R_EAX, R_NONE, R_NONE, 29, 0xDF4u, { 0xC7, 0x80, 0xF4, 0x0D, 0x00, 0x00, 0x1D, 0x00, 0x00, 0x00 } },
};
static const ol_writer VV4_WRITERS[] = {
    /* theFernsaceDialog's OK: mov [eax+0x1BBC], edx */
    { 0x41961Du, 6, R_EAX, R_NONE, R_EDX, 0, 0x1BBCu, { 0x89, 0x90, 0xBC, 0x1B, 0x00, 0x00 } },
};
static const ol_writer VV5_WRITERS[] = {
    /* theFernsaceDialog: mov [edi+0x1BBC], edx (its OK) and mov [edi+0x1BBC], ecx (its other button) */
    { 0x419D68u, 6, R_EDI, R_NONE, R_EDX, 0, 0x1BBCu, { 0x89, 0x97, 0xBC, 0x1B, 0x00, 0x00 } },
    { 0x419E8Eu, 6, R_EDI, R_NONE, R_ECX, 0, 0x1BBCu, { 0x89, 0x8F, 0xBC, 0x1B, 0x00, 0x00 } },
};

static const ol_writer *g_writers;
static int g_writer_count;

/* The site's registers: [0..7] pushad (edi, esi, ebp, esp, ebx, edx, ecx, eax), [8] the flags, [9] the
   site's number, replaced with where the game goes on.  The game's own write is made here. */
static void __cdecl ol_writer_hit(unsigned int *frame) {
    const ol_writer *w = &g_writers[frame[9]];
    unsigned int record = frame[7 - w->rec_a] + (w->rec_b != R_NONE ? frame[7 - w->rec_b] : 0u);
    int value = w->value_reg != R_NONE ? (int)frame[7 - w->value_reg] : w->value;
    if (!g_busy) {
        g_busy = 1;
        (void)ol_game_body((const unsigned char *)(UINT_PTR)record, value);
        g_busy = 0;
    }
    *(int *)(UINT_PTR)(record + w->field) = value;
    frame[9] = w->va + w->length;
}

static __declspec(naked) void ol_writer_common(void) {
    __asm {
        pushfd
        pushad
        push esp
        call ol_writer_hit
        add esp, 4
        popad
        popfd
        ret                                 ; to the instruction after the site
    }
}

#define OL_STUB(n) static __declspec(naked) void ol_stub_##n(void) { __asm push n __asm jmp ol_writer_common }
OL_STUB(0) OL_STUB(1)

static void (*const OL_STUBS[])(void) = { ol_stub_0, ol_stub_1 };

/* Every writer of the game, or none. */
static void ol_install_writers(const ol_writer *writers, int count) {
    vvfp_site_write w[sizeof OL_STUBS / sizeof OL_STUBS[0]];
    int i;
    if (count <= 0 || count > (int)(sizeof OL_STUBS / sizeof OL_STUBS[0])) {
        return;
    }
    for (i = 0; i < count; ++i) {
        vvfp_site_branch(&w[i], writers[i].va, writers[i].length, writers[i].stock, 0xE9, (const void *)OL_STUBS[i]);
    }
    g_writers = writers;
    g_writer_count = count;
    if (!vvfp_install_sites(w, count)) {
        g_writers = NULL;
        g_writer_count = 0;
    }
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
    switch (game) {
    case 2:
        ol_install_writers(VV2_WRITERS, (int)(sizeof VV2_WRITERS / sizeof VV2_WRITERS[0]));
        break;
    case 3:
        ol_install_writers(VV3_WRITERS, (int)(sizeof VV3_WRITERS / sizeof VV3_WRITERS[0]));
        break;
    case 4:
        ol_install_writers(VV4_WRITERS, (int)(sizeof VV4_WRITERS / sizeof VV4_WRITERS[0]));
        break;
    case 5:
        ol_install_writers(VV5_WRITERS, (int)(sizeof VV5_WRITERS / sizeof VV5_WRITERS[0]));
        break;
    default:
        break;
    }
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
