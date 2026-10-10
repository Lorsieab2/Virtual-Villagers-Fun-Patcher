/* A PAID PURCHASE THAT HAS NOT ARRIVED YET SURVIVES A QUIT.

   The Origins "Barrel of Babies" upgrade in A New Home, The Lost Children,
   The Secret City and The Tree of Life is the patcher's own (New Believers
   keeps its purchase bits in a block the save holds, 0x51D388): the purchase takes the tech points in the village
   (saved with it) and sets a pending token in the executable's own memory
   (A New Home 0x48D700 + its delay counter 0x48D704; The Lost Children
   0x49C700 + its cue counter 0x49C708), which the village's update turns into
   the barrel a little later -- or holds, as long as it takes, while the
   village has no room.  That token was process memory only: a quit (or any
   relaunch) before the delivery kept the charge and lost the barrel.  Stock
   games have no such state.

   So the token is kept in a per-slot file beside the save:
     <save folder>\Virtual Villagers Fun Patcher Data\Paid Purchases\
         Virtual Villagers N Paid Purchases - Save S.dat
   written (atomically: a temporary file moved over it) when the purchase
   becomes pending, refreshed with the village's roster while it waits, and
   deleted when the barrel is delivered.  When a village is first on screen
   (a load, a relaunch, a switch back to a slot) and nothing is pending in
   memory, a file for that slot re-arms the token as "the Tech screen has
   closed" -- the barrel then arrives through the game's own path, once --
   only when:
     - the file is this game's and this slot's, well formed;
     - its roster shares a strict majority with the village on screen (the
       same village: a Start Over or a new tribe in the slot is another one,
       and the file is deleted with it -- Start Over deletes it too,
       native/shared/save_reset.c);
     - the slot's save was written after the purchase: the charge is in the
       save.  After a crash that lost the save holding the charge, the
       village never paid, and the file is deleted rather than delivering a
       barrel for nothing.
   A file that exists but cannot be read is left alone (never deleted on a
   guess).  Switching villages never deletes another slot's file: it waits
   for its village.

   Included by the Origins companion of each game that uses it, after its
   own includes; everything is file-static. */
#ifndef VV_PAID_PURCHASES_H
#define VV_PAID_PURCHASES_H

#include <windows.h>
#include <shlobj.h>
#include <string.h>

#define VV_PAID_MAGIC    0x31505056u          /* 'V' 'P' 'P' '1' */
#define VV_PAID_VERSION  1u
#define VV_PAID_RECORDS  256
#define VV_PAID_REFRESH_MS 30000u
#define VV_PAID_FOLDER   "Virtual Villagers Fun Patcher Data"
#define VV_PAID_SUB      "Paid Purchases"

typedef struct {
    unsigned int magic;
    unsigned int version;
    unsigned int game;
    unsigned int slot;
    unsigned int token;            /* the pending value when written */
    unsigned int bought_lo;        /* FILETIME the purchase became pending */
    unsigned int bought_hi;
    unsigned int count;            /* living villagers in roster[] */
    unsigned int roster[VV_PAID_RECORDS];
} vv_paid_file;

/* What a game hands over: its token and counter, the token value that means
   "bought, the Tech screen closed" (re-armed with the counter at 0). */
typedef struct {
    volatile unsigned char *token;
    volatile unsigned int *counter;
    unsigned char restore_token;
    const char *save_stem;         /* "<stem><slot>.ldw" */
    /* What else the game's delivery needs re-armed after a relaunch (NULL:
       nothing); counter may be NULL when the game has none. */
    void (*restore)(void);
} vv_paid_game;

static int vv_paid_slot;                       /* the village tracked: its slot ... */
static unsigned int vv_paid_roster[VV_PAID_RECORDS];  /* ... and its roster */
static int vv_paid_have;
static int vv_paid_last;                       /* pending on the last frame */
static FILETIME vv_paid_bought;
static DWORD vv_paid_written;
static int vv_paid_dirty;                      /* the roster changed since the file was written */

#ifdef VV_PAID_TEST_FOLDER
#define VV_PAID_SAVE_FOLDER(out) vv_paid_test_folder(out)
#else
#define VV_PAID_SAVE_FOLDER(out) vv_paid_save_folder(out)
/* "<Documents>\LDW\<executable's name>", where the game saves. */
static int vv_paid_save_folder(char *out) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base, *dot;
    DWORD n;
    if (FAILED(SHGetFolderPathA(NULL, CSIDL_PERSONAL, NULL, 0, docs))) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base != NULL ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) {
        *dot = '\0';
    }
    if (base[0] == '\0' || lstrlenA(docs) + 5 + lstrlenA(base) + 160 >= MAX_PATH) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    return 1;
}
#endif

/* The slot's file; `make` creates the folders on the way. */
static int vv_paid_path(int game, int slot, char *out, int make) {
    char folder[MAX_PATH];
    if (game < 1 || game > 5 || slot < 1 || slot > 5 || !VV_PAID_SAVE_FOLDER(folder)) {
        return 0;
    }
    if (make) {
        CreateDirectoryA(folder, NULL);
    }
    wsprintfA(out, "%s\\" VV_PAID_FOLDER, folder);
    if (make) {
        CreateDirectoryA(out, NULL);
    }
    wsprintfA(out, "%s\\" VV_PAID_FOLDER "\\" VV_PAID_SUB, folder);
    if (make) {
        CreateDirectoryA(out, NULL);
    }
    wsprintfA(out, "%s\\" VV_PAID_FOLDER "\\" VV_PAID_SUB "\\Virtual Villagers %d Paid Purchases - Save %d.dat",
              folder, game, slot);
    return 1;
}

/* When the slot's save was last written; 0 when it cannot be told. */
static int vv_paid_save_time(const vv_paid_game *g, int slot, FILETIME *out) {
    char folder[MAX_PATH];
    char path[MAX_PATH];
    WIN32_FILE_ATTRIBUTE_DATA data;
    if (!VV_PAID_SAVE_FOLDER(folder) || lstrlenA(folder) + lstrlenA(g->save_stem) + 16 >= MAX_PATH) {
        return 0;
    }
    wsprintfA(path, "%s\\%s%d.ldw", folder, g->save_stem, slot);
    if (!GetFileAttributesExA(path, GetFileExInfoStandard, &data)) {
        return 0;
    }
    *out = data.ftLastWriteTime;
    return 1;
}

/* 1 read and well formed for game/slot, 0 absent or malformed, -1 present but
   unreadable (left alone). */
static int vv_paid_read(int game, int slot, vv_paid_file *f) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0;
    BOOL ok;
    if (!vv_paid_path(game, slot, path, 0)) {
        return -1;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        return (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) ? 0 : -1;
    }
    ok = ReadFile(h, f, sizeof(*f), &got, NULL);
    CloseHandle(h);
    if (!ok) {
        return -1;
    }
    return got == sizeof(*f) && f->magic == VV_PAID_MAGIC && f->version == VV_PAID_VERSION
        && f->game == (unsigned int)game && f->slot == (unsigned int)slot && f->token != 0u
        && f->count <= VV_PAID_RECORDS;
}

static int vv_paid_write(int game, int slot, unsigned int token, const unsigned int *roster) {
    char path[MAX_PATH];
    char tmp[MAX_PATH + 8];
    static vv_paid_file f;
    HANDLE h;
    DWORD wrote = 0;
    BOOL ok;
    int i;
    if (!vv_paid_path(game, slot, path, 1)) {
        return 0;
    }
    memset(&f, 0, sizeof f);
    f.magic = VV_PAID_MAGIC;
    f.version = VV_PAID_VERSION;
    f.game = (unsigned int)game;
    f.slot = (unsigned int)slot;
    f.token = token;
    f.bought_lo = vv_paid_bought.dwLowDateTime;
    f.bought_hi = vv_paid_bought.dwHighDateTime;
    for (i = 0; i < VV_PAID_RECORDS; ++i) {
        f.roster[i] = roster[i];
        f.count += roster[i] != 0u;
    }
    wsprintfA(tmp, "%s.tmp", path);
    h = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = WriteFile(h, &f, sizeof f, &wrote, NULL) && wrote == sizeof f && FlushFileBuffers(h);
    CloseHandle(h);
    if (!ok || !MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp);
        return 0;
    }
    vv_paid_written = GetTickCount();
    return 1;
}

static void vv_paid_delete(int game, int slot) {
    char path[MAX_PATH];
    if (vv_paid_path(game, slot, path, 0)) {
        DeleteFileA(path);
    }
}

/* A strict majority of the living villagers in `was` are in `now`. */
static int vv_paid_same_village(const unsigned int *was, const unsigned int *now) {
    int i, k, had = 0, kept = 0;
    for (i = 0; i < VV_PAID_RECORDS; ++i) {
        if (was[i] == 0u) {
            continue;
        }
        ++had;
        for (k = 0; k < VV_PAID_RECORDS; ++k) {
            if (now[k] == was[i]) {
                ++kept;
                break;
            }
        }
    }
    return had > 0 && kept * 2 > had;
}

/* The village on screen's first frame: re-arm a pending purchase its save
   paid for.  Returns 1 when it re-armed one. */
static int vv_paid_arrive(int game, int slot, const unsigned int *roster, const vv_paid_game *g) {
    static vv_paid_file f;
    FILETIME saved;
    int read;
    if (*g->token != 0) {
        return 0;
    }
    read = vv_paid_read(game, slot, &f);
    if (read <= 0) {
        if (read == 0) {
            vv_paid_delete(game, slot);       /* malformed: nothing it says can be used */
        }
        return 0;
    }
    vv_paid_bought.dwLowDateTime = f.bought_lo;
    vv_paid_bought.dwHighDateTime = f.bought_hi;
    if (!vv_paid_same_village(f.roster, roster)) {
        /* Not this village -- or not yet: while a slot is switched, a frame can
           still show the last village's records.  The file waits; Start Over
           deletes it with the village it belongs to. */
        return 0;
    }
    if (!vv_paid_save_time(g, slot, &saved) || CompareFileTime(&saved, &vv_paid_bought) < 0) {
        vv_paid_delete(game, slot);           /* the save on disk never paid for it (a crash) */
        return 0;
    }
    if (g->counter != NULL) {
        *g->counter = 0u;
    }
    *g->token = g->restore_token;
    if (g->restore != NULL) {
        g->restore();
    }
    return 1;
}

/* The token and counter are writable memory of this executable (an Origins
   build without the purchase may not map them): probed once. */
static int vv_paid_mapped_state;     /* 0 unprobed, 1 usable, -1 not */
static int vv_paid_mapped(const vv_paid_game *g) {
    if (vv_paid_mapped_state == 0) {
        MEMORY_BASIC_INFORMATION a, b;
        int ok = VirtualQuery((const void *)g->token, &a, sizeof a) == sizeof a
            && VirtualQuery(g->counter != NULL ? (const void *)g->counter : (const void *)g->token, &b, sizeof b) == sizeof b
            && a.State == MEM_COMMIT && b.State == MEM_COMMIT
            && (a.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_WRITECOPY))
            && (b.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_WRITECOPY));
        vv_paid_mapped_state = ok ? 1 : -1;
    }
    return vv_paid_mapped_state > 0;
}

/* Every frame a village is on screen, with its slot and its roster (record
   identities, 0 for an empty record).  Returns 1 when it re-armed a purchase. */
static int vv_paid_tick(int game, int slot, const unsigned int *roster, const vv_paid_game *g) {
    int pending, restored = 0;
    if (slot < 1 || slot > 5 || roster == NULL || !vv_paid_mapped(g)) {
        return 0;
    }
    {
        int i, live = 0;
        for (i = 0; i < VV_PAID_RECORDS; ++i) {
            live += roster[i] != 0u;
        }
        if (live == 0) {
            return 0;                 /* no village (a load frame): nothing is known */
        }
    }
    if (!vv_paid_have || slot != vv_paid_slot
        || (memcmp(vv_paid_roster, roster, sizeof vv_paid_roster) != 0
            && !vv_paid_same_village(vv_paid_roster, roster))) {
        /* Another village on screen: its own file, if any, is its own. */
        vv_paid_have = 1;
        vv_paid_slot = slot;
        memcpy(vv_paid_roster, roster, sizeof vv_paid_roster);
        restored = vv_paid_arrive(game, slot, roster, g);
        pending = *g->token != 0;
        if (pending && !restored) {
            GetSystemTimeAsFileTime(&vv_paid_bought);
            vv_paid_write(game, slot, *g->token, roster);
        }
        vv_paid_last = pending;
        return restored;
    }
    pending = *g->token != 0;
    if (pending && !vv_paid_last) {
        GetSystemTimeAsFileTime(&vv_paid_bought);   /* bought now */
        vv_paid_write(game, slot, *g->token, roster);
    } else if (!pending && vv_paid_last) {
        vv_paid_delete(game, slot);                  /* delivered */
    } else if (pending) {
        if (memcmp(vv_paid_roster, roster, sizeof vv_paid_roster) != 0) {
            vv_paid_dirty = 1;                        /* a birth, a death while it waits */
        }
        if (vv_paid_dirty && GetTickCount() - vv_paid_written >= VV_PAID_REFRESH_MS
            && vv_paid_write(game, slot, *g->token, roster)) {
            vv_paid_dirty = 0;                        /* the village it waits in, as it is now */
        }
    }
    memcpy(vv_paid_roster, roster, sizeof vv_paid_roster);
    vv_paid_last = pending;
    return 0;
}

#endif /* VV_PAID_PURCHASES_H */
