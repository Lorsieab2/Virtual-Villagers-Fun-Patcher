/* BOUGHT ISLAND EVENTS DO NOT CHANGE WHEN THE GAME'S OWN ISLAND EVENTS COME.

   The owner (2026-10-23): "Do buying custom island events affect the timing
   of naturally spawned ones?  I would prefer they don't affect timing."

   WHAT THE GAMES DO.  Each game keeps ONE timer for its island events -- the
   second its next event is due (A New Home world+0xA300, The Lost Children
   world+0x2EAE0, The Secret City manager+0x12EF4, The Tree of Life
   world+0x170E0, New Believers manager+0x17D3C).  Its trigger, once that
   second has come (A New Home 0x4237BD, The Lost Children 0x42EECD, The
   Secret City 0x468732, The Tree of Life 0x43FA3D, New Believers 0x4426EA),
   writes the timer again -- now plus 12-23 hours (A New Home), 10-19 hours
   (The Lost Children) or 8-15 hours (the other three), or 30 minutes while
   its Island Events Seen count is 0 -- counts the event and builds it.
   Every purchase that delivers an island event makes it come by writing that
   same timer: the Origins "Island Event" (A New Home 0x456B47, The Lost
   Children 0x494824, The Secret City 0x6DF34A, The Tree of Life 0x4897B8,
   New Believers 0x7CCCFC: now + 5 seconds, or 0 in New Believers), The Tree
   of Life's and New Believers' "Barrel of Babies" (0x4897E6, 0x7CEE63: 0),
   The Tree of Life's re-arm of an Island Event a barrel went ahead of
   (0x728A6B), and the Story / Cheat Upgrades' Pick Island Event, Custom
   Island Event and Choose Time Skip Amount's closing notice (each made due
   "exactly as the Island Event purchase does").  So the next natural event's
   time was overwritten by the purchase, and the trigger then gave the bought
   event a fresh 8-23 hours: buying moved every natural event later.

   WHAT THIS DOES.  The natural time is kept, and put back:
     - where a purchase writes the timer, the time it held is kept as the
       distance from the value written (`delta` = natural - written);
     - where the trigger finds the timer due, the natural time is that value
       plus the distance (whatever the game did to the timer meanwhile --
       a pause moving it later, a Time Warp -- it did to the natural time
       too);
     - right after the trigger's own write for that event, the timer is set
       to the natural time.  The event itself is then counted, built and
       shown by the game exactly as before; a natural time already passed
       makes the game's own event come next, as it would have.
   Nothing else is written: the Island Events Seen count, the first-event
   and 30-minute rules, the visitors and the purchases' own locks are the
   game's and the purchases' as before.

   KEPT ACROSS A QUIT.  A purchase not yet delivered is in the save (the
   timer it wrote); the natural time is kept beside it per slot in
     <save folder>\...\Paid Purchases\Virtual Villagers N Island Event Timer - Save S.dat
   with the village's roster, written when the purchase is made and deleted
   when it is delivered.  It is used only for the same village (a strict
   majority of the roster) and only when the slot's save was written after
   the purchase (the save holds the timer the purchase wrote); a file older
   than the save on disk (a crash lost the save) is deleted.

   Included by each game's Origins companion (and by the test build, which
   keeps the file in memory); everything is file-static.  Each game's sites
   and stubs are in island_timer_vvN.inc. */
#ifndef VVFP_ISLAND_TIMER_KEEP_H
#define VVFP_ISLAND_TIMER_KEEP_H

#include <windows.h>
#include <string.h>

#include "install_sites.h"     /* every site written, or none */
#ifndef ITK_TEST
#include "paid_purchases.h"
#endif

#define ITK_MAGIC   0x4B544956u           /* 'V' 'I' 'T' 'K' */
#define ITK_VERSION 1u
#define ITK_ROSTER  256

typedef struct {
    unsigned int va;
    int length;                           /* 5..12; a jmp then nops */
    unsigned char expect[12];
    void *stub;
} itk_site;

typedef struct {
    int game;
    const itk_site *sites;
    int site_count;
    int (__stdcall *slot)(void);          /* 1..5, 0 = not known */
    int (*roster)(unsigned int *out);     /* ITK_ROSTER identities, 0 = empty; returns how many */
    const char *save_stem;                /* "<stem><slot>.ldw" */
} itk_game;

typedef struct {
    unsigned int magic;
    unsigned int version;
    unsigned int game;
    unsigned int slot;
    unsigned int delta;                   /* natural - the value the purchase wrote */
    unsigned int reserved;
    unsigned __int64 when;                /* FILETIME units */
    unsigned int roster[ITK_ROSTER];
} itk_file;

static const itk_game *itk_g;
static int itk_state;                     /* 0 not tried, 1 installed, -1 refused */

static int itk_active;                    /* a bought event is on its way */
static itk_file itk_rec;                  /* ... its natural time, village and moment */

static int itk_fire_pending;              /* the trigger found the timer due with one on its way */
static unsigned int *itk_fire_field;
static unsigned int itk_fire_value;       /* the natural time to put back */
static unsigned int itk_fire_seen;        /* the timer when that was worked out */

static int itk_checked;                   /* the slot's file was looked at for ... */
static int itk_checked_slot;
static unsigned int itk_checked_value;    /* ... this timer */

/* ---- Time, the file and the save (the test build keeps them in memory) ---- */

#ifdef ITK_TEST
static unsigned __int64 itk_test_now = 1000u;
static unsigned __int64 itk_test_save_time;  /* 0 = no save */
static itk_file itk_test_file;
static int itk_test_have_file;

static unsigned __int64 itk_now(void) { return ++itk_test_now; }

static int itk_save_time(int slot, unsigned __int64 *out) {
    (void)slot;
    *out = itk_test_save_time;
    return itk_test_save_time != 0u;
}

static int itk_read(int slot, itk_file *f) {
    (void)slot;
    if (!itk_test_have_file) {
        return 0;
    }
    *f = itk_test_file;
    return 1;
}

static void itk_store(const itk_file *f) {
    itk_test_file = *f;
    itk_test_have_file = 1;
}

static void itk_remove(int slot) {
    (void)slot;
    itk_test_have_file = 0;
}
#else
static unsigned __int64 itk_now(void) {
    FILETIME t;
    GetSystemTimeAsFileTime(&t);
    return ((unsigned __int64)t.dwHighDateTime << 32) | t.dwLowDateTime;
}

static int itk_save_time(int slot, unsigned __int64 *out) {
    FILETIME t;
    if (itk_g == NULL || itk_g->save_stem == NULL || !vv_paid_stem_time(itk_g->save_stem, slot, &t)) {
        return 0;
    }
    *out = ((unsigned __int64)t.dwHighDateTime << 32) | t.dwLowDateTime;
    return 1;
}

/* 1 read, 0 absent or not whole, -1 there but unreadable. */
static int itk_read(int slot, itk_file *f) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0;
    BOOL ok;
    if (!vv_paid_named_path(itk_g->game, slot, "Island Event Timer", path, 0)) {
        return -1;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        return (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) ? 0 : -1;
    }
    ok = ReadFile(h, f, sizeof *f, &got, NULL);
    CloseHandle(h);
    if (!ok) {
        return -1;
    }
    return got == sizeof *f ? 1 : 2;
}

static void itk_store(const itk_file *f) {
    char path[MAX_PATH];
    const void *parts[1];
    DWORD sizes[1];
    if (!vv_paid_named_path(itk_g->game, (int)f->slot, "Island Event Timer", path, 1)) {
        return;
    }
    parts[0] = f;
    sizes[0] = sizeof *f;
    (void)vv_paid_write_parts(path, parts, sizes, 1);
}

static void itk_remove(int slot) {
    char path[MAX_PATH];
    if (slot >= 1 && slot <= 5 && vv_paid_named_path(itk_g->game, slot, "Island Event Timer", path, 0)) {
        DeleteFileA(path);
    }
}
#endif

/* ---- The village ---------------------------------------------------------- */

static int itk_slot_now(void) {
    int slot = itk_g != NULL && itk_g->slot != NULL ? itk_g->slot() : 0;
    return slot >= 1 && slot <= 5 ? slot : 0;
}

static int itk_roster_now(unsigned int *out) {
    memset(out, 0, ITK_ROSTER * sizeof *out);
    return itk_g != NULL && itk_g->roster != NULL ? itk_g->roster(out) : 0;
}

/* A strict majority of the villagers in `was` are in `now`. */
static int itk_same_village(const unsigned int *was, const unsigned int *now) {
    int i, k, had = 0, kept = 0;
    for (i = 0; i < ITK_ROSTER; ++i) {
        if (was[i] == 0u) {
            continue;
        }
        ++had;
        for (k = 0; k < ITK_ROSTER; ++k) {
            if (now[k] == was[i]) {
                ++kept;
                break;
            }
        }
    }
    return had > 0 && kept * 2 > had;
}

/* ---- The three moments ---------------------------------------------------- */

/* Nothing on its way in memory: the slot's file -- once for this timer
   (`force` 0, the trigger's frames), or now whatever was looked at before
   (`force` 1: a purchase is about to write the timer, and a purchase saved
   and reloaded before its delivery -- a Barrel of Babies re-armed after a
   relaunch -- must keep the natural time its file holds, not take the
   saved purchase's own timer for it). */
static void itk_load(const unsigned int *field, int force) {
    static unsigned int roster[ITK_ROSTER];
    static itk_file f;
    unsigned __int64 saved;
    int slot = itk_slot_now(), read;
    if (slot == 0 || (!force && itk_checked && itk_checked_slot == slot && itk_checked_value == *field)) {
        return;
    }
    if (itk_roster_now(roster) == 0) {
        return;                           /* no village to tell yet: asked again */
    }
    itk_checked = 1;
    itk_checked_slot = slot;
    itk_checked_value = *field;
    read = itk_read(slot, &f);
    if (read <= 0) {
        return;                           /* none, or there and unreadable: left alone */
    }
    if (read != 1 || f.magic != ITK_MAGIC || f.version != ITK_VERSION || itk_g == NULL
        || f.game != (unsigned int)itk_g->game || f.slot != (unsigned int)slot) {
        itk_remove(slot);                 /* malformed: nothing it says can be used */
        return;
    }
    if (!itk_same_village(f.roster, roster)) {
        return;                           /* another village's: it waits for its own */
    }
    if (!itk_save_time(slot, &saved) || saved < f.when) {
        itk_remove(slot);                 /* the save on disk was never bought in */
        return;
    }
    itk_rec = f;
    itk_active = 1;
}

/* Whether the bought event in memory is this village's: its slot, and --
   when it was bought with anyone in the village -- a majority of its
   villagers.  One bought in another village (its file stays for it) is
   never applied here, nor its distance added to a purchase made here. */
static int itk_rec_here(void) {
    static unsigned int roster[ITK_ROSTER];
    int i, any = 0;
    if (itk_rec.slot != 0u && (unsigned int)itk_slot_now() != itk_rec.slot) {
        return 0;
    }
    for (i = 0; i < ITK_ROSTER && !any; ++i) {
        any = itk_rec.roster[i] != 0u;
    }
    return !any || (itk_roster_now(roster) > 0 && itk_same_village(itk_rec.roster, roster));
}

/* A purchase is about to write `value` into the timer at `field`. */
static void __cdecl itk_note(unsigned int *field, unsigned int value) {
    static unsigned int roster[ITK_ROSTER];
    unsigned int natural;
    if (field == NULL) {
        return;
    }
    if (itk_active && !itk_rec_here()) {
        itk_active = 0;                   /* another village's purchase: this one starts fresh */
    }
    if (!itk_active) {
        itk_load(field, 1);               /* this village's own, saved before a reload */
    }
    /* The natural time: the timer itself, or -- a second write before the
       first purchase was delivered -- what that purchase kept. */
    natural = itk_active ? *field + itk_rec.delta : *field;
    memset(&itk_rec, 0, sizeof itk_rec);
    itk_rec.magic = ITK_MAGIC;
    itk_rec.version = ITK_VERSION;
    itk_rec.game = itk_g != NULL ? (unsigned int)itk_g->game : 0u;
    itk_rec.slot = (unsigned int)itk_slot_now();
    itk_rec.delta = natural - value;
    itk_rec.when = itk_now();
    itk_active = 1;
    itk_fire_pending = 0;
    if (itk_roster_now(roster) > 0) {
        memcpy(itk_rec.roster, roster, sizeof roster);
        if (itk_rec.slot != 0u) {
            itk_store(&itk_rec);
        }
    }
}

/* The trigger found the timer at `field` due. */
static void __cdecl itk_firing(unsigned int *field) {
    if (itk_fire_pending && field == itk_fire_field && *field == itk_fire_seen) {
        return;                           /* worked out already, nothing moved */
    }
    itk_fire_pending = 0;
    if (!itk_active) {
        itk_load(field, 0);
        if (!itk_active) {
            return;
        }
    }
    if (!itk_rec_here()) {
        itk_active = 0;                   /* another village's: its file stays for it */
        return;
    }
    itk_fire_pending = 1;
    itk_fire_field = field;
    itk_fire_seen = *field;
    itk_fire_value = *field + itk_rec.delta;
}

/* The trigger found the timer not due. */
static void __cdecl itk_not_due(void) {
    itk_fire_pending = 0;
}

/* The trigger has just written the timer at `field` for the event it is
   making: that event is the bought one, and the natural time goes back. */
static void __cdecl itk_rescheduled(unsigned int *field) {
    if (!itk_fire_pending || field != itk_fire_field) {
        return;
    }
    *field = itk_fire_value;
    itk_fire_pending = 0;
    itk_active = 0;
    itk_remove((int)itk_rec.slot);
    itk_checked = 0;
}

/* For the Story / Cheat Upgrades' arms (story_bridge.h's host table). */
static void __stdcall itk_story_arming(void *field, unsigned int value) {
    if (itk_state == 1) {
        itk_note((unsigned int *)field, value);
    }
}

/* ---- Installing ----------------------------------------------------------- */

static int itk_readable(unsigned int va, int length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(UINT_PTR)va;
    if (VirtualQuery(at, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
        return 0;
    }
    return (UINT_PTR)at + (unsigned int)length <= (UINT_PTR)info.BaseAddress + info.RegionSize;
}

/* Every site holds exactly the bytes listed, then every one is written -- or
   nothing is (a build whose bytes differ keeps the game's own behaviour).
   Every site is made writable before any is written
   (native/shared/install_sites.h), so a refused VirtualProtect leaves them
   all stock; before, the sites already written were "put back" with more
   writes that could fail the same way.  Once; returns whether it is in
   place. */
#define ITK_MAX_SITES 16
static int itk_install(const itk_game *g) {
    vvfp_site_write w[ITK_MAX_SITES];
    int i;
    if (itk_state != 0) {
        return itk_state == 1;
    }
    itk_state = -1;
    itk_g = g;
    if (g->site_count <= 0 || g->site_count > ITK_MAX_SITES) {
        return 0;
    }
    for (i = 0; i < g->site_count; ++i) {
        const itk_site *s = &g->sites[i];
        if (s->length < 5 || s->length > 12 || !itk_readable(s->va, s->length)
            || memcmp((const void *)(UINT_PTR)s->va, s->expect, (size_t)s->length) != 0) {
            return 0;
        }
        vvfp_site_branch(&w[i], s->va, s->length, s->expect, 0xE9, (const void *)s->stub);
    }
    if (!vvfp_install_sites(w, g->site_count)) {
        return 0;
    }
    itk_state = 1;
    return 1;
}

#endif /* VVFP_ISLAND_TIMER_KEEP_H */
