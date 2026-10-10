#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>   /* SHGetSpecialFolderPathA, CSIDL_PERSONAL */
#include <string.h>   /* strrchr */
#include "../shared/sidecar_io.h" /* atomic mask-sidecar publish; invalid files set aside */
#include "../shared/story_bridge.h" /* Story / Cheat Upgrades: free upgrades, Pick Island Event */
#include "../shared/cause_bridge.h"  /* Cause of Death: graves and the Deaths log */
#include "../shared/game_save_slot.h" /* the slot the game itself saves to */
#include "../shared/crosscheck_bridge.h" /* the cross-check: silent at load, asked only at the quit */
#include "../shared/orphan_masks.h"  /* the cross-check's orphan mask entries */
#include "../shared/vv5_villager_table.h" /* the table, its slot count and the mask table, from the image */
#include "../shared/mask_follow.h" /* masks follow their villagers through a reload */
#include "../shared/data_subfolder.h" /* each kind of data file in its own folder */
#include "../shared/appearance_log.h" /* "Appearance changed" in the Births and Conceptions log */

/* Heathen-mask persistence: the per-villager mask side-table (nibble-packed,
   150 villagers x 4 bits = 75 bytes) lives in exe .data BSS at 0x7B1D20 (with
   256 Villagers (Experimental), 256 x 4 bits = 128 bytes at 0x7F1400). The
   safest way to persist it is OUTSIDE the game's save flow (VV5's autosave does
   not re-run get_save_path, so an exe save-hook never fires). Instead the native
   code writes it from the chooser (WriteMaskSidecar, on OK) and the render path
   reads it back through Vv5MaskSync. Both build the path here in clean C,
   next to the game's own save: Documents\LDW\<exe-basename>\vvfp_masks_<slot>.dat.
   Keyed by villager record index (positional + stable across reload) AND by save
   slot: the exe-side slot_capture detour on buildSavePath stashes the current
   village slot at 0x7B1D7C, so each village keeps its own sidecar instead of one
   shared file bleeding masks across slots. The sidecar is a SEPARATE file from the
   .ldw, so it can never corrupt a save. */
/* The villager slots: 150, or 256 with 256 Villagers (Experimental).  The
   record base, the slot count and the mask table are read from the running
   executable (native/shared/vv5_villager_table.h), so this one DLL serves
   either build; tables here are sized for the larger one and every walk
   stops at vv5_slots(). */
#define VV5_MAX_VILLAGERS 256
#define MASK_TABLE_MAX_BYTES (VV5_MAX_VILLAGERS / 2)

static unsigned int g_vv5_rec_base;
static int g_vv5_slots;

static void vv5_locate(void) {
    unsigned int rva, slots;
    if (g_vv5_rec_base != 0) {
        return;
    }
    vv5_villager_table((const unsigned char *)(UINT_PTR)0x400000u, &rva, &slots);
    g_vv5_slots = (int)slots;
    g_vv5_rec_base = 0x400000u + rva + 0x48u;
}

static unsigned int vv5_rec_base(void) {
    vv5_locate();
    return g_vv5_rec_base;
}

static int vv5_slots(void) {
    vv5_locate();
    return g_vv5_slots;
}

/* The nibble table: 0x7B1D20 (75 bytes) in a 150-slot build, 0x7F1400 (128
   bytes) in the 256 build, where the page's mask helpers are composed to it. */
static unsigned char *vv5_mask_table(void) {
    return (unsigned char *)(UINT_PTR)(vv5_slots() == 256 ? VV5_256_MASK_TABLE : VV5_STOCK_MASK_TABLE);
}

static DWORD vv5_mask_table_bytes(void) {
    return (DWORD)vv5_slots() / 2u;
}

/* 'VM05' -- a mask sidecar bound to the living roster of the village that
   wrote it (see VV5 VILLAGE IDENTITY below): the magic, 150 roster hashes and
   the 75-byte table.  The two earlier formats are rejected by this magic
   rather than misread: the original untagged 75-byte file has no header at
   all, and v1.35.13's 'VM01' carried a tag read from the wrong object, which
   is why it never got written in the first place.  'VM25' is the same for
   the 256 Villagers build: 256 hashes and a 128-byte table.  Each build
   writes its own format (a 150-slot build's files are byte-for-byte what
   they always were) and reads both, so a village copied from a 150-slot
   build keeps its masks in the 256 build. */
#define VV5_MASK_SIDECAR_MAGIC 0x35304D56u
#define VV5_MASK_SIDECAR_MAGIC_256 0x35324D56u
/* 'VM06' / 'VM26' (this build): the same shape, but each roster entry is the
   villager's IDENTITY -- name, gender and the parents' names -- not the name
   alone.  The game loads a save packed into records 0, 1, 2, ..., so after a
   death and a reload everyone behind it is in a lower record, and the masks
   are moved to their villagers by that identity (vv5_mask_follow_load); a
   name alone could hand a dead villager's mask to a living namesake.  The
   'VM05' / 'VM25' files are still read: their name hashes bind the village
   and move masks only DOWN a record (what a packed load does), and the file
   is rewritten in the new format at once. */
#define VV5_MASK_SIDECAR_MAGIC_V6 0x36304D56u
#define VV5_MASK_SIDECAR_MAGIC_V6_256 0x36324D56u
/* Current save slot, written by the exe slot_capture detour (0 until the first
   save/load; village slots are >=1, slot 0 is the meta file). */
#define VV5_SLOT_SCRATCH 0x007B1D7Cu
#define VV5_MASK_TABLE vv5_mask_table() /* nibble-packed side-table, one nibble per slot */

static HINSTANCE module_instance;
static HWND origins_owner;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1013,   /* 14 tech-menu rows: rows 0..13 -> Buy 1000..1013 (row 13 = Change Appearance for All) */
    ID_CHECK_FIRST = 1100,
    STATE_VILLAGER = 0x10000,
    /* Architecture-aware state, above every dialog row/unavailable bit
       (0..21) and separate from STATE_VILLAGER. Expanded VV5 binds only the
       original Tech rows 0..5 and Details rows 0..3. */
    STATE_LIMITED_CAPABILITY = 0x400000
};

enum {
    ACTION_YOUTH = 0,
    ACTION_MASTERY = 1,
    ACTION_RUNNING = 2,
    ACTION_AGE18 = 3,
    ACTION_HEAL = 4,
    ACTION_APPEARANCE = 5,
    ACTION_TECH_BASE = 16,
    ACTION_COMPLETE_COLLECTIONS = 16,
    ACTION_RESET_COLLECTIONS = 17,
    ACTION_TECH_DOUBLER = 18,
    ACTION_FOOD_DOUBLER = 19,
    ACTION_GRANT_RUNNING_ALL = 20,
    ACTION_GRANT_MASTERY_ALL = 21,
    ACTION_SET_AGE_18_ALL = 22,
    ACTION_EQUAL_DIVISION_PARENTING = 23,
    ACTION_EQUAL_DIVISION_NO_PARENTING = 24,
    ACTION_CHANGE_APPEARANCE_ALL = 25
};

enum {
    RESULT_SUCCESS = 0,
    RESULT_NO_CHANGE = 1,
    RESULT_INVALID = 2,
    RESULT_INSUFFICIENT = 3,
    RESULT_CANCELLED = 4,
    RESULT_RECHECK = 5,
    RESULT_RETAINED = 6,
    RESULT_CHARGE_UNKNOWN = 7,
    RESULT_NO_SLOT = 8,
    RESULT_INVALID_SKILL = 9,
    RESULT_UNAVAILABLE = 10,
    RESULT_REMOVED = 11,
    RESULT_PURCHASED = 12,
    RESULT_UNSUPPORTED_SICKNESS = 13,
    RESULT_RUNNING_DISLIKE_CLEARED = 14,
    RESULT_APPEARANCE_UNCHANGED = 15
};

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
        origins_owner = NULL;
    }
    return TRUE;
}

/* Build Documents\LDW\<exe-basename>\vvfp_masks.dat into out (>= MAX_PATH).
   Ensures the folder exists. Returns 1 on success, 0 on failure. Slot 0 is
   retained for the pre-load legacy sidecar read; numbered village saves are
   exactly 1..5. Fail open on a truncated module path or a final path that
   cannot fit, before any unbounded wsprintfA writes. */
/* MIGRATE A SIDECAR LEFT BY AN OLDER BUILD.

   The data files moved into "Virtual Villagers Fun Patcher Data" under
   names that say what they hold. A player who upgrades still has the old
   loose file beside their saves, and the new loader would not find it --
   so their masks, doublers and recorded parents would silently vanish on
   the first load even though valid state was sitting on disk.

   Called only when the NEW path is absent. Copies the legacy file into
   place and removes the original, so the migration happens once and the
   old name stops shadowing anything afterwards. A failed copy leaves both
   files untouched and the caller simply finds nothing, which is exactly
   what it would have found without this.

   MoveFileA rather than CopyFile + Delete: it is atomic within a volume,
   so an interrupted migration cannot leave a half-written new file that
   the loader would then read as corrupt state. */
/* 1 to proceed, 0 when a legacy sidecar exists and could NOT be moved.

   The result used to be discarded. A move can fail transiently -- the
   file open without delete sharing, a scanner, a lock -- and the caller
   then reported success pointing at a file that does not exist. The
   loader read nothing, an empty table was eventually committed, and the
   next write published it at the new path; from then on the destination
   existed, migration was skipped forever, and the real records were gone.
   Found in review.

   Refusing is safe: every caller treats a failed path build as "do not
   persist this time", so the state stays on disk under its old name and
   the next launch retries. Losing one save's worth of persistence is a
   far smaller harm than losing the records permanently. */
static int vv_migrate_legacy_sidecar(const char *new_path,
                                      const char *legacy_name,
                                      const char *docs,
                                      const char *base,
                                      int slot) {
    char legacy[MAX_PATH];
    if (new_path == NULL || legacy_name == NULL || docs == NULL
        || base == NULL) {
        return 1;
    }
    /* THE BOUND BELOW ASSUMES ONE DIGIT, so the slot has to be one.
       Every caller validates the slot before reaching here, but this
       function checks four pointers and a length and would be trusting
       exactly one argument it does not own -- and that argument is the one
       formatted with %d into a buffer sized for a single character. A
       negative or multi-digit slot is not a real save slot in any of the
       five games, so refusing is both safe and correct. */
    if (slot < 0 || slot > 9) {
        return 1;
    }
    if (GetFileAttributesA(new_path) != INVALID_FILE_ATTRIBUTES) {
        return 1;               /* already migrated, or never needed it */
    }
    if ((size_t)lstrlenA(docs) + (size_t)lstrlenA(base)
        + sizeof("\\LDW\\\\vv1_doublers_0.dat") > sizeof(legacy)) {
        return 1;
    }
    wsprintfA(legacy, "%s\\LDW\\%s\\%s%d.dat", docs, base, legacy_name, slot);
    if (GetFileAttributesA(legacy) == INVALID_FILE_ATTRIBUTES) {
        return 1;               /* nothing of that vintage to migrate */
    }
    if (!MoveFileA(legacy, new_path)) {
        /* The records are still there under the old name. Say so,
           so the caller does not publish over them. */
        return 0;
    }
    return 1;
}

static int build_mask_sidecar_path(char *out) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    char *dot;
    int slot = *(volatile int *)VV5_SLOT_SCRATCH;
    DWORD n;
    int docs_len, base_len;
    if (slot < 0 || slot > 5) {
        return 0;
    }
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;   /* basename incl. ".exe" */
    dot = strrchr(base, '.');
    if (dot) {
        *dot = '\0';                /* strip the extension */
    }
    /* The longest valid output is the numbered form with slot 5.  Include
       the terminating NUL: the helper's callers provide char path[MAX_PATH],
       and wsprintfA/lstrcatA do not perform destination-size checks. */
    docs_len = lstrlenA(docs);
    base_len = lstrlenA(base);
    if (docs_len + 5 + base_len + (int)sizeof("\\" VV_DATA_FOLDER "\\Village Masks - Save 5.dat") > MAX_PATH) {
        return 0;
    }
    /* ensure Documents\LDW and Documents\LDW\<base> exist (CreateDirectory is a
       no-op / harmless if they already do) */
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Data", docs, base);
    CreateDirectoryA(out, NULL);
    /* The data files now live in their own clearly named folder rather
       than loose beside the .ldw saves, so create that component too. */
    wsprintfA(out, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Data", docs, base);
    CreateDirectoryA(out, NULL);
    /* SLOT 0 IS NOT A VILLAGE. Before the first save or load the slot
       scratch reads 0, and an unsuffixed file shared by EVERY village used
       to be built for that case. That shared file is precisely the
       cross-save bleed this keying exists to stop -- the owner's carried
       144 masked villagers into a village that never chose any. VV1 has
       always refused slot 0 and has never shown the bleed, so the other
       games now match it. A pre-load read simply finds nothing, which is
       correct: a village that has not been loaded has no masks to show. */
    if (slot <= 0) {
        return 0;
    }
    /* The masks have a folder of their own inside it, "Village Masks". A
       file an older build left loose in the Data folder is moved in on the
       way (native/shared/data_subfolder.h); if it will not move, the loose
       file is the one read and written, so nothing is shadowed. `out`
       still holds the Data folder from just above. */
    {
        char name[32];
        wsprintfA(name, "Village Masks - Save %d.dat", slot);
        if (!vv_data_file_path(out, MAX_PATH, VV_DATA_SUB_MASKS, name, VV_DATA_RESERVE)) {
            return 0;
        }
    }
    /* A player upgrading from a build that wrote the loose name still
       has their masks under it; move them into place. */
    /* A legacy file that exists and will not move means the masks
       are still under the old name. Refuse rather than hand back a
       path to a file that does not exist: an empty table published
       there would overwrite them for good. Found in review. */
    if (!vv_migrate_legacy_sidecar(out, "vvfp_masks_", docs, base, slot)) {
        return 0;
    }
    return 1;
}

/* VV5 VILLAGE IDENTITY: THE LIVING ROSTER.

   New Believers has no village-identity field this code can trust.  v1.35.13
   tried to bind the file to two dwords at "save buffer +0x328/+0x338", read
   at 0x4DBFC8+8+0x328 -- but 0x4DBFC8 is the collectible manager, not the
   save state.  The save routine at 0x4244F0 is a __thiscall on a save-state
   object that GATHERS the static managers into the buffer:

       lea eax, [esi+0x328]; push eax; mov ecx, 0x4DB358; call 0x412EC0
       lea ecx, [esi+0x640]; push ecx; mov ecx, 0x4DBFC8; call 0x413B80

   so buffer+0x328 is what 0x4DB358 serialises (0x412EC0 is a 792-byte copy)
   and 0x4DBFC8 only lands at +0x640.  Read live, 0x4DC2F8/0x4DC308 are zero
   in a running village, so WriteMaskSidecar refused every write and no file
   was ever created -- the owner's "masks are not persistent" report.  Worse,
   0x4DB358 is the trophy-progress table (0x413450 adds to entry[index] and
   awards at a threshold), so even at the right address those dwords change
   during play and would have rejected a village's own file later.

   The identity that works, already proven in The Lost Children, is the
   village's own villagers: a snapshot of the living roster (a hash per record
   slot of the villager's name), matched on a STRICT MAJORITY of the smaller
   roster.  Different villages share essentially nothing -- a Start Over
   fills a handful of founder slots from a finite name pool -- while the same
   village across a birth, a death, or a barrel of babies keeps nearly every
   member.  See vv5_roster_same for the exact rule and its residual case.

   Record layout is the population exporter's VV5 row, confirmed live in the
   owner's running village (104 living villagers, names and ages where these
   offsets say): the array sits at exe 0x554148 (the same object the save
   routine gathers into buffer+0xC90C), records start 0x48 in, stride 0x2F44,
   150 slots, active byte at +0x1CD4, name at +0x1B9C (25 bytes).  With 256
   Villagers the object is at 0x800000 with 256 slots (vv5_rec_base,
   vv5_slots). */
#define VV5_ROSTER_RECORDS  vv5_rec_base()
#define VV5_ROSTER_STRIDE   0x2F44u
#define VV5_RECORD_COUNT    VV5_MAX_VILLAGERS
#define VV5_ACTIVE_OFFSET   0x1CD4u
#define VV5_NAME_OFFSET     0x1B9Cu
#define VV5_NAME_CAPACITY   0x19
#define VV5_MASK_COUNT      6          /* 0 = none, 1..5 = the five masks */
#define VV5_SEX_OFFSET      0x1B90u    /* dword, 0 = male, 1 = female */
#define VV5_FATHER_OFFSET   0x1BC0u    /* the parents' names, set at birth (the population exporter's VV5 row) */
#define VV5_MOTHER_OFFSET   0x1BD9u

static unsigned int g_vv5_roster[VV5_RECORD_COUNT];
static int g_vv5_have_roster;
/* The part of each of those identities a rename does not change -- gender
   and the parents' names -- taken at the same moment (memory only; 0 for an
   empty record).  How the sync tells a rename from a new occupant
   (vv_roster_renamed, native/shared/mask_follow.h). */
static unsigned int g_vv5_stable[VV5_RECORD_COUNT];
static int g_vv5_slot;                 /* the slot the table was loaded for */
static DWORD g_vv5_sync_tick;          /* last roster check, GetTickCount */

static unsigned int vv5_fnv_text(unsigned int h, const unsigned char *text, int capacity) {
    int k;
    for (k = 0; k < capacity && text[k]; ++k) {
        h = (h ^ text[k]) * 16777619u;
    }
    return h;
}

/* A living record's identity: name, gender and the parents' names (empty
   for founders and arrivals), none of which changes during a life.  Never 0. */
static unsigned int vv5_identity(const unsigned char *rec) {
    unsigned int h = vv5_fnv_text(2166136261u, rec + VV5_NAME_OFFSET, VV5_NAME_CAPACITY);
    int k;
    h = (h ^ 0xFFu) * 16777619u;
    for (k = 0; k < 4; ++k) {
        h = (h ^ rec[VV5_SEX_OFFSET + k]) * 16777619u;
    }
    h = vv5_fnv_text(h, rec + VV5_FATHER_OFFSET, VV5_NAME_CAPACITY);
    h = (h ^ 0xFEu) * 16777619u;
    h = vv5_fnv_text(h, rec + VV5_MOTHER_OFFSET, VV5_NAME_CAPACITY);
    h = (h ^ 0xFDu) * 16777619u;
    return h ? h : 1u;
}

/* The part of a living record's identity that a rename leaves alone:
   gender and the parents' names.  Never 0. */
static unsigned int vv5_stable(const unsigned char *rec) {
    unsigned int h = 2166136261u;
    int k;
    for (k = 0; k < 4; ++k) {
        h = (h ^ rec[VV5_SEX_OFFSET + k]) * 16777619u;
    }
    h = vv5_fnv_text(h, rec + VV5_FATHER_OFFSET, VV5_NAME_CAPACITY);
    h = (h ^ 0xFEu) * 16777619u;
    h = vv5_fnv_text(h, rec + VV5_MOTHER_OFFSET, VV5_NAME_CAPACITY);
    h = (h ^ 0xFDu) * 16777619u;
    return h ? h : 1u;
}

/* Fill out[] with the identity of each living record (slots past this
   build's count read as inactive).  Returns the number of living villagers;
   0 means "no village is loaded", and every caller treats that as unknown. */
static int vv5_roster_identities(unsigned int *out, unsigned int *stable) {
    const unsigned char *base =
        (const unsigned char *)(UINT_PTR)VV5_ROSTER_RECORDS;
    int i, live = 0, slots = vv5_slots();
    memset(out, 0, VV5_RECORD_COUNT * sizeof(unsigned int));
    memset(stable, 0, VV5_RECORD_COUNT * sizeof(unsigned int));
    for (i = 0; i < slots; ++i) {
        const unsigned char *rec = base + (unsigned int)i * VV5_ROSTER_STRIDE;
        if (rec[VV5_ACTIVE_OFFSET] == 0) {
            continue;
        }
        out[i] = vv5_identity(rec);
        stable[i] = vv5_stable(rec);
        ++live;
    }
    return live;
}

/* The name hash of each living record: the roster a 'VM05' / 'VM25' file
   holds.  Returns the number of living villagers. */
static int vv5_roster_snapshot(unsigned int *out) {
    const unsigned char *base =
        (const unsigned char *)(UINT_PTR)VV5_ROSTER_RECORDS;
    int i, live = 0, slots = vv5_slots();
    memset(out, 0, VV5_RECORD_COUNT * sizeof(unsigned int));
    for (i = 0; i < slots; ++i) {
        const unsigned char *rec = base + (unsigned int)i * VV5_ROSTER_STRIDE;
        const unsigned char *name;
        unsigned int h = 2166136261u;          /* FNV-1a */
        int k;
        if (rec[VV5_ACTIVE_OFFSET] == 0) {
            out[i] = 0;
            continue;
        }
        name = rec + VV5_NAME_OFFSET;
        for (k = 0; k < VV5_NAME_CAPACITY && name[k]; ++k) {
            h = (h ^ name[k]) * 16777619u;
        }
        h = (h ^ 0xFFu) * 16777619u;           /* terminator: "Tai" != "Taiga" */
        out[i] = h ? h : 1u;                   /* reserve 0 for "inactive" */
        ++live;
    }
    return live;
}

/* How many of the recorded villagers in `a` are in `b` at the same record
   or at their RANK in `a` -- the record a packed load puts them in (every
   game loads a save into records 0, 1, 2, ..., so after a death everyone
   behind it comes back lower).  Both are exact positions, so a coincidence
   still has to land on one of two records. */
static int vv5_roster_overlap(const unsigned int *a, const unsigned int *b) {
    int i, n = 0, rank = 0;
    for (i = 0; i < VV5_RECORD_COUNT; ++i) {
        if (a[i] == 0) {
            continue;
        }
        if (a[i] == b[i] || a[i] == b[rank]) {
            ++n;
        }
        ++rank;
    }
    return n;
}

static int vv5_roster_living(const unsigned int *a) {
    int i, n = 0;
    for (i = 0; i < VV5_RECORD_COUNT; ++i) {
        if (a[i] != 0) {
            ++n;
        }
    }
    return n;
}

/* Are two rosters the same village?  A STRICT majority of the smaller roster
   must be shared:

       need = min(living_a, living_b) / 2 + 1

   Not (n + 1) / 2, which is exactly half when n is even.  Strict majority
   still admits every ordinary event, because a birth or a death keeps every
   member of the smaller roster.  The one legitimate case it rejects: a
   two-villager village losing one and gaining one in the same check window,
   which reloads and clears that village's masks.  Residual, stated rather
   than hidden: a predecessor with one or two living villagers can still be
   matched by a single same-slot name coincidence. */
static int vv5_roster_same(const unsigned int *a, const unsigned int *b) {
    int la = vv5_roster_living(a);
    int lb = vv5_roster_living(b);
    int need = la < lb ? la : lb;
    if (need == 0) {
        return 0;                              /* an empty roster matches nothing */
    }
    need = need / 2 + 1;                       /* STRICT majority of the smaller roster */
    return vv5_roster_overlap(a, b) >= need;
}

static int vv5_roster_equal(const unsigned int *a, const unsigned int *b) {
    int i;
    for (i = 0; i < VV5_RECORD_COUNT; ++i) {
        if (a[i] != b[i]) {
            return 0;
        }
    }
    return 1;
}

/* Persist the mask side-table (75 bytes at exe 0x7B1D20, or 128 at 0x7F1400
   with 256 Villagers; passed in) together with the roster it belongs to.  Called from the chooser on OK and whenever
   the roster changes under the same village.  A village that has never been
   identified writes nothing: an unsnapshotted file could never be matched,
   and writing one would recreate the very bleed this exists to stop.  Never
   touches the .ldw. */
/* The load/publish gate for the mask sidecar (native/shared/sidecar_io.h),
   keyed by save slot: a write is refused until this slot's file has loaded,
   been found missing, or -- present but invalid -- been moved aside intact. */
static vv_sidecar_gate g_vv5_mask_gate;

/* A file of `count` slots: the magic, `count` roster hashes, `count` / 2
   table bytes. */
#define VV5_MASK_SIDECAR_BYTES_FOR(count) (4 + (count) * sizeof(unsigned int) + (count) / 2)
#define VV5_MASK_SIDECAR_MAX_BYTES VV5_MASK_SIDECAR_BYTES_FOR(VV5_MAX_VILLAGERS)

/* The slot count a sidecar was written for -- 150 ('VM05') or 256 ('VM25')
   -- or 0 when it is neither or too short for its own format. */
static int vv5_mask_sidecar_count(const unsigned char *data, DWORD len) {
    unsigned int magic;
    int count;
    if (len < 4) {
        return 0;
    }
    memcpy(&magic, data, sizeof(magic));
    count = (magic == VV5_MASK_SIDECAR_MAGIC || magic == VV5_MASK_SIDECAR_MAGIC_V6) ? 150
          : (magic == VV5_MASK_SIDECAR_MAGIC_256 || magic == VV5_MASK_SIDECAR_MAGIC_V6_256) ? 256 : 0;
    return count != 0 && len >= VV5_MASK_SIDECAR_BYTES_FOR((DWORD)count) ? count : 0;
}

static int vv5_mask_sidecar_valid(const unsigned char *data, DWORD len,
                                  void *ctx) {
    (void)ctx;
    return vv5_mask_sidecar_count(data, len) != 0;
}

/* The identity each entry was stored with (orphan_masks.h, vv_om_track):
   the roster says 0 for a record nobody holds, so an entry left on a record
   that empties -- New Believers keeps a dead villager's mask there until
   someone takes the record -- keeps it only here.  Reset by every load; a
   'VM05' / 'VM25' file's name hashes become identities there
   (vv_om_from_names). */
static unsigned int g_vv5_mask_id[VV5_MAX_VILLAGERS];

/* 1 when the table is on disk (the orphan repair needs to know). */
static int vv5_write_mask_sidecar(const unsigned char *table) {
    char path[MAX_PATH];
    unsigned int magic = vv5_slots() == 256 ? VV5_MASK_SIDECAR_MAGIC_V6_256 : VV5_MASK_SIDECAR_MAGIC_V6;
    static unsigned int written_roster[VV5_RECORD_COUNT];
    static unsigned char value[VV5_RECORD_COUNT];
    const void *parts[3];
    DWORD sizes[3];
    int i;
    if (table == NULL || !g_vv5_have_roster) {
        return 0;                   /* unknown village -> do not write */
    }
    /* Never before this slot's load settled: a file that is present but
       could not be opened still holds the masks this table lacks.  Checked
       before the path is built, so a blocked slot costs no file I/O. */
    if (!vv_sidecar_gate_ready(&g_vv5_mask_gate, *(volatile int *)VV5_SLOT_SCRATCH)
        || !build_mask_sidecar_path(path)) {
        return 0;
    }
    /* ATOMIC: this used to CREATE_ALWAYS the real file -- truncating it at
       once -- and ignore every WriteFile, so a crash or a full disk left a
       short file the loader rejected, and every mask was lost.  Now the
       payload goes to "<path>.tmp", each write is checked, and only a
       complete, flushed file replaces the published one. */
    parts[0] = &magic;        sizes[0] = sizeof(magic);
    /* The roster binds the file to its village; an empty record keeps the
       identity of an ambiguous mask left on it (vv_om_roster_to_write). */
    for (i = 0; i < VV5_RECORD_COUNT; ++i) {
        value[i] = (unsigned char)(i < vv5_slots()
                                   ? ((i & 1) ? (table[i >> 1] >> 4) & 0x0Fu : table[i >> 1] & 0x0Fu) : 0);
    }
    vv_om_roster_to_write(VV5_RECORD_COUNT, g_vv5_roster, value, g_vv5_mask_id, written_roster);
    parts[1] = written_roster; sizes[1] = (DWORD)vv5_slots() * sizeof(unsigned int);
    parts[2] = table;         sizes[2] = vv5_mask_table_bytes();
    return vv_sidecar_publish(&g_vv5_mask_gate, path, parts, sizes, 3);
}

__declspec(dllexport) void __stdcall WriteMaskSidecar(const unsigned char *table) {
    (void)vv5_write_mask_sidecar(table);
}

/* Move the masks in `table` from the records `stored` names to where those
   villagers are in `live` (native/shared/mask_follow.h).  `weak` for a
   name-only roster: then a mask only moves DOWN a record.  Returns 1 when
   the table changed. */
static int vv5_mask_follow_table(unsigned char *table, const unsigned int *stored,
                                 const unsigned int *live, int weak) {
    static unsigned char value[VV5_MAX_VILLAGERS], moved[VV5_MAX_VILLAGERS];
    static unsigned int moved_id[VV5_MAX_VILLAGERS];
    int i, changed, slots = vv5_slots();
    for (i = 0; i < slots; ++i) {
        value[i] = (unsigned char)((i & 1) ? (table[i >> 1] >> 4) & 0x0Fu : table[i >> 1] & 0x0Fu);
    }
    changed = vv_mask_follow(slots, value, stored, stored, live, weak, moved, moved_id);
    vv_om_track(slots, moved, moved_id, g_vv5_mask_id);
    if (!changed) {
        return 0;
    }
    memset(table, 0, vv5_mask_table_bytes());
    for (i = 0; i < slots; ++i) {
        table[i >> 1] |= (unsigned char)((i & 1) ? moved[i] << 4 : moved[i]);
    }
    return 1;
}

/* Set by the load when the table it restored must be written back at once:
   masks were moved, or the file was in the name-only format. */
static int g_vv5_rewrite_after_load;

/* Load the table for the village whose living roster is `live`.  Clears
   first, so every failure path -- no file, short read, wrong magic, a file
   from a village that shares no majority with this one -- leaves NO masks,
   which is exactly what a village that never chose any sees, and what stops
   a new village inheriting a dead one's choices. */
/* 1 when the load settled (read, legitimately absent, or an invalid file
   moved aside), 0 when it must stay pending: the path was refused, or the
   file is present but cannot be opened.  Pending never permits a write. */
static int vv5_mask_sidecar_load(unsigned char *table, const unsigned int *live) {
    char path[MAX_PATH];
    DWORD got = 0;
    unsigned int filesnap[VV5_RECORD_COUNT];
    unsigned int names[VV5_RECORD_COUNT];
    const unsigned int *against = live;
    unsigned int magic;
    int weak;
    unsigned char file[VV5_MASK_SIDECAR_MAX_BYTES];
    unsigned char buf[MASK_TABLE_MAX_BYTES];
    DWORD table_bytes = vv5_mask_table_bytes();
    int count;
    int kept;
    int i;
    int status;
    /* FAIL CLOSED: the clear precedes EVERY exit.

       A load that does not complete must not leave the PREVIOUS village's
       masks on screen, so the table is emptied before anything can fail.
       That rule outranks preserving a locked legacy sidecar: showing one
       village's masks on another is a visible wrong result, while a refused
       migration is retried on the next call and costs only this pass.

       The refusal is still REPORTED, so the caller does not latch the roster
       and adopt an empty table as this village's state. */
    memset(table, 0, table_bytes);
    memset(g_vv5_mask_id, 0, sizeof(g_vv5_mask_id));
    g_vv5_rewrite_after_load = 0;
    vv_sidecar_gate_bind(&g_vv5_mask_gate, *(volatile int *)VV5_SLOT_SCRATCH);
    if (vv_sidecar_gate_throttled(&g_vv5_mask_gate)) {
        return 0;               /* blocked a moment ago: no I/O until the retry */
    }
    if (!build_mask_sidecar_path(path)) {
        vv_sidecar_gate_block(&g_vv5_mask_gate);
        return 0;               /* not settled; retried later */
    }
    /* Only a genuinely missing file is "no masks".  A present file that fails
       the magic or is short is moved aside intact before anything may be
       written; one that cannot be opened at all keeps the load pending. */
    status = vv_sidecar_load(&g_vv5_mask_gate, path, file, sizeof(file), &got,
                             vv5_mask_sidecar_valid, NULL);
    if (status == VV_SIDECAR_LOAD_BLOCKED) {
        return 0;
    }
    if (status != VV_SIDECAR_LOAD_VALID) {
        return 1;                     /* no sidecar -> no masks, as before */
    }
    /* THE ROSTER DECIDES, not the slot.  Slots are reused, so a file left by
       the previous village is exactly what a Start Over leaves behind; its
       snapshot shares at most a coincidence with the village on screen.
       That is a valid file of another village, not a damaged one: it stays
       in place, as before, for this village's first write to replace. */
    /* The file's own slot count (150 or 256, validated above).  Slots past
       this build's count are not loaded; slots past the file's stay
       unmasked and out of the roster comparison. */
    count = vv5_mask_sidecar_count(file, got);
    kept = count < vv5_slots() ? count : vv5_slots();
    memset(filesnap, 0, sizeof(filesnap));
    memset(buf, 0, sizeof(buf));
    memcpy(filesnap, file + 4, (size_t)kept * sizeof(unsigned int));
    memcpy(buf, file + 4 + (size_t)count * sizeof(unsigned int), (size_t)kept / 2);
    memcpy(&magic, file, sizeof(magic));
    weak = magic == VV5_MASK_SIDECAR_MAGIC || magic == VV5_MASK_SIDECAR_MAGIC_256;
    if (weak) {
        vv5_roster_snapshot(names);   /* a name-only file is compared with names */
        against = names;
    }
    if (vv5_roster_same(filesnap, against)) {
        /* Sidecars are user-writable: only 0 (none) through 5 are valid
           nibbles, so normalise before publishing to the render thunks. */
        for (i = 0; i < (int)table_bytes; ++i) {
            if ((buf[i] & 0x0Fu) >= VV5_MASK_COUNT) buf[i] &= 0xF0u;
            if ((buf[i] >> 4) >= VV5_MASK_COUNT) buf[i] &= 0x0Fu;
        }
        memcpy(table, buf, table_bytes);
        /* The file was written against the records as they were then; a
           reload has packed them since.  Each mask goes to its villager. */
        g_vv5_rewrite_after_load = vv5_mask_follow_table(table, filesnap, against, weak) || weak;
        if (weak) {
            vv_om_from_names(VV5_RECORD_COUNT, g_vv5_mask_id, names, live);
        }
    }
    return 1;
}

/* The village-change decision, called from the render path's mask_flip on
   every head draw and therefore throttled: the roster is re-read at most
   every VV5_SYNC_INTERVAL_MS, which is far quicker than a player can reach
   the chooser after a Start Over, and costs nothing between checks.

     slot unpublished       -> unknown; touch nothing
     no living villagers    -> unknown; touch nothing
     slot changed           -> replaced, whatever the roster looks like
     majority, unchanged    -> same village, nothing to do
     majority, changed      -> same village, a birth or a death: adopt the
                               new snapshot and persist it, so the file is
                               never more than one event behind
     no majority            -> replaced: clear, reload only a file whose
                               snapshot shares a majority, adopt the new one

   Returns 1 when a village is on screen and the table corresponds to it,
   0 when nothing is known.  The appended page ignores the result. */
#define VV5_SYNC_INTERVAL_MS 250u

/* "VVFP Fix Huts.dll" (Builders Fix Huts When Idle,: loaded by
   full path and asked to install its detour for this game, once, from this
   periodic entry -- outside DllMain.  Not shipped (the row is off): nothing
   is installed, the stock scheduler runs. */
static int vvfp_fix_huts_state;   /* 0 = not tried, 1 = installed, -1 = unavailable */

static void vvfp_fix_huts_bridge(void) {
    HMODULE companion;
    int (__stdcall *install)(int game_id);
    if (vvfp_fix_huts_state != 0) {
        return;
    }
    vvfp_fix_huts_state = -1;
    companion = vvfp_startup_ships("VVFP Fix Huts.dll") ? vvfp_load_patcher_dll("VVFP Fix Huts.dll") : NULL;
    if (companion == NULL) {
        return;                   /* not shipped: the row is off */
    }
    install = (int (__stdcall *)(int))GetProcAddress(companion, "VvfpFixHutsInstall");
    if (install != NULL && install(5)) {
        vvfp_fix_huts_state = 1;
    }
}

/* The runtime companions, installed before the first catch-up.  Vv5MaskSync
   runs only on a villager head draw, and New Believers catches up the time
   that passed while it was closed when it enters the village (0x425E30, from
   the village screen's entry), before any head is drawn -- so the companions'
   detours were missing for that first catch-up.  The Task9 page's
   slot_capture, the detour on buildSavePath (0x403600), calls this export:
   the game builds the slot's save path to load the village, and only the
   loaded village has a clock to catch up.  Install-once (the bridge's own
   state); every later save and load makes it a no-op. */
__declspec(dllexport) void __stdcall Vv5InstallCompanions(void) {
    vvfp_fix_huts_bridge();
    vvfp_story_bridge(5);       /* story / cheat upgrades companion: once, fail-open */
    vvfp_cause_bridge(5);  /* cause of death companion: once, fail-open */
}

/* GAME START.  "VVFP Startup.dll" calls this from the executable's call of
   WinMain -- the game's own thread, outside the loader lock, before the
   game has a window, a village or a save slot -- so the runtime companions
   are loaded and their detours written before the title screen and the
   slot menu, ahead of Vv5InstallCompanions (buildSavePath, at the load).
   Only loads and installs: nothing here reads or writes the game's data or
   calls a game routine.  Every bridge is install-once.  `game` is the
   executable's own number (5); `shipped` is
   this build's companion bits (native/shared/startup_companions.h). */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)game;
    vvfp_startup_note_shipped(shipped);   /* every bridge loads only what this build ships */
    VVFP_STARTUP_GUARDED(vvfp_fix_huts_bridge());          /* loads and installs Builders and Healers Work First too */
    VVFP_STARTUP_GUARDED(vvfp_story_startup(5));
    VVFP_STARTUP_GUARDED(vvfp_cause_install_once(5));
    VVFP_STARTUP_GUARDED(vvfp_crosscheck_startup(5));   /* the quit check's hook, after the quit save (crosscheck_bridge.h) */
}

__declspec(dllexport) int __stdcall Vv5MaskSync(void) {
    unsigned int cur[VV5_RECORD_COUNT];
    unsigned int cur_stable[VV5_RECORD_COUNT];
    unsigned char *table = (unsigned char *)VV5_MASK_TABLE;
    DWORD now = GetTickCount();
    int slot;
    vvfp_fix_huts_bridge();     /* fix-huts companion: once, fail-open */
    vvfp_story_bridge(5);       /* story / cheat upgrades companion: once, fail-open */
    vvfp_cause_bridge(5);  /* cause of death companion: once, fail-open */
    vvfp_crosscheck_bridge(5, 1);  /* the cross-check, silent while played: a head is being drawn */
    if (g_vv5_have_roster && (now - g_vv5_sync_tick) < VV5_SYNC_INTERVAL_MS) {
        return 1;                   /* checked a moment ago */
    }
    g_vv5_sync_tick = now;
    slot = *(volatile int *)VV5_SLOT_SCRATCH;
    if (slot <= 0) {
        return 0;                   /* nothing known yet -> do not touch anything */
    }
    if (vv5_roster_identities(cur, cur_stable) == 0) {
        return 0;                   /* unknown village -> do not touch anything */
    }
    /* A RENAME (Codex, #516).  The identity hashes the name, so a villager
       the player renames would read as a new occupant: their mask dropped by
       the follow, and in a village of one or two the roster taken for
       another village's and every mask cleared.  One record changed, its
       gender and parents unchanged: the same villager.  The mask stays on
       its record, which takes the new identity, and the file says so now. */
    if (g_vv5_have_roster && slot == g_vv5_slot) {
        int renamed = vv_roster_renamed(VV5_RECORD_COUNT, g_vv5_roster, g_vv5_stable, cur, cur_stable);
        if (renamed >= 0) {
            g_vv5_roster[renamed] = cur[renamed];
            memcpy(g_vv5_stable, cur_stable, sizeof(cur_stable));
            WriteMaskSidecar(table);
            return 1;
        }
    }
    /* Same village means the same SLOT and a roster majority.  A slot change
       always reloads: the file is keyed per slot, and two slots can hold
       overlapping rosters when a save has been copied between them. */
    if (g_vv5_have_roster && slot == g_vv5_slot && vv5_roster_same(g_vv5_roster, cur)) {
        if (!vv5_roster_equal(g_vv5_roster, cur)) {
            /* A birth, a death, or villagers renumbered: each mask goes to
               its villager -- and a record reused by a newborn no longer
               hands it the dead villager's mask. */
            vv5_mask_follow_table(table, g_vv5_roster, cur, 0);
            memcpy(g_vv5_roster, cur, sizeof(cur));
            memcpy(g_vv5_stable, cur_stable, sizeof(cur_stable));
            WriteMaskSidecar(table);
        }
        return 1;                   /* same village -> keep the masks as they are */
    }
    /* REPLACED (or first sight): clear, reload only a matching file, adopt.

       ADOPT ONLY A SETTLED LOAD. A refused path used to be adopted
       anyway, so an empty table sat latched with no retry and the next
       write migrated the real file and truncated it. Found in review. */
    if (!vv5_mask_sidecar_load(table, cur)) {
        return 0;               /* stay pending; retried on the next call */
    }
    memcpy(g_vv5_roster, cur, sizeof(cur));
    memcpy(g_vv5_stable, cur_stable, sizeof(cur_stable));
    g_vv5_have_roster = 1;
    g_vv5_slot = slot;
    if (g_vv5_rewrite_after_load) {
        WriteMaskSidecar(table);    /* the followed table, in this build's format */
        g_vv5_rewrite_after_load = 0;
    }
    return 1;
}

/* ---- The cross-check's orphan mask entries (orphan_masks.h) ---------------
   The table is kept by record and the file by roster: the identity each
   entry was stored with is g_vv5_mask_id.  An orphan: a mask on a
   record nobody holds whose identity -- none, or one no villager carries,
   Heathens and bodies awaiting burial included, since every active record
   is one the save holds -- is no villager's. */
static vv_om_list g_vv5_om_asked;

static void vv5_om_put(int index, unsigned char value, unsigned int id) {
    unsigned char *slot = &((unsigned char *)VV5_MASK_TABLE)[index >> 1];
    *slot = (index & 1) ? (unsigned char)((*slot & 0x0F) | (value << 4))
                        : (unsigned char)((*slot & 0xF0) | value);
    g_vv5_mask_id[index] = id;
}

static int vv5_om_publish(void) {
    return vv5_write_mask_sidecar((const unsigned char *)VV5_MASK_TABLE);
}

/* -1 until this slot's masks are loaded onto the village on screen. */
static int vv5_om_scan(int slot, vv_om_list *out) {
    static unsigned int ids[VV5_RECORD_COUNT], stable[VV5_RECORD_COUNT];
    const unsigned char *table = (const unsigned char *)VV5_MASK_TABLE;
    int i, slots = vv5_slots();
    out->count = 0;
    if (slot < 1 || !g_vv5_have_roster || g_vv5_slot != slot || *(volatile int *)VV5_SLOT_SCRATCH != slot
        || !vv_sidecar_gate_ready(&g_vv5_mask_gate, slot) || vv5_roster_identities(ids, stable) == 0) {
        return -1;
    }
    for (i = 0; i < slots; ++i) {
        unsigned char value = (unsigned char)((i & 1) ? (table[i >> 1] >> 4) & 0x0Fu : table[i >> 1] & 0x0Fu);
        if (vv_om_orphan(value, ids[i] != 0, g_vv5_mask_id[i], ids, slots)) {
            vv_om_add(out, i, value, g_vv5_mask_id[i]);
        }
    }
    return out->count;
}

static int vvfp_xc_masks_scan(int game, int slot) {
    return game == 5 ? vv5_om_scan(slot, &g_vv5_om_asked) : 0;
}

/* 1 when nothing the scan noted is left undone: removed, or no longer an
   orphan; 0 when the masks cannot be told now or the change could not be
   made (the next scan finds them again). */
static int vvfp_xc_masks_repair(int game, int slot) {
    static vv_om_list now, gone;
    static const vv_om_table table = { vv5_om_put, vv5_om_publish, 1 };
    char path[MAX_PATH];
    int done = 1;
    if (game == 5 && g_vv5_om_asked.count > 0) {
        done = 0;
        if (vv5_om_scan(slot, &now) >= 0) {
            vv_om_still(&g_vv5_om_asked, &now, &gone);
            done = gone.count == 0
                   || (build_mask_sidecar_path(path) && vv_om_commit(5, slot, path, &gone, &table));
        }
    }
    g_vv5_om_asked.count = 0;
    return done;
}

/* ---------- VV5 Change Appearance chooser (VV2-style) ----------
   Owner-drawn modal picker showing the selected villager's head and body
   sprites cropped from the stock game art (embedded BMP strips: male/female x
   young/old heads, male/female bodies). It reports only the chosen head/body
   indices back to the caller through the head/body pointers; the native task9
   handler owns the believer gate, the 5,000-tech charge, and the record
   writes, so this DLL never touches save data. Head catalog is 30 (0..29),
   body/outfit catalog is 29 (0..28); young/old is a head-atlas swap. */
#define IDD_APPEARANCE   203
#define IDB_HEAD_M_YOUNG 3001
#define IDB_HEAD_M_OLD   3002
#define IDB_HEAD_F_YOUNG 3003
#define IDB_HEAD_F_OLD   3004
#define IDB_BODY_M       3011
#define IDB_BODY_F       3012
#define IDB_MASK_PREVIEW 3013
#define IDC_BODY_PREVIEW 3101
#define IDC_HEAD_PREVIEW 3102
#define IDC_MASK_PREVIEW 3110
#define IDC_BODY_PREV    3103
#define IDC_BODY_NEXT    3104
#define IDC_HEAD_PREV    3105
#define IDC_HEAD_NEXT    3106
#define APPEARANCE_HEAD_COUNT 30
#define APPEARANCE_BODY_COUNT 30
#define APPEARANCE_CELL_W 40
#define APPEARANCE_CELL_H 65
/* Cosmetic Heathen-mask overlay: a purely visual per-villager choice stored by
   the native handler in record byte +0x1BC0 (0..5). It is rendered by a
   transient render-time faction flip in the exe patch and touches no faction
   state, so the villager stays a believer in every game system. */
#define IDC_MASK_LABEL   3107
#define IDC_MASK_PREV    3108
#define IDC_MASK_NEXT    3109
#define APPEARANCE_MASK_COUNT 6

static const char *const APPEARANCE_MASK_NAMES[APPEARANCE_MASK_COUNT] = {
    "(None)", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask",
    "Tribal Chief Mask"
};

static int appearance_sex;   /* 0 = male, 1 = female */
static int appearance_old;   /* 0 = young head atlas, 1 = old head atlas */
static int appearance_head;
static int appearance_body;
static int appearance_mask;  /* 0 = none, 1..5 = Blue/Orange/Red/Purple/Chief */

static void appearance_update_mask_label(HWND window) {
    SetDlgItemTextA(window, IDC_MASK_LABEL, APPEARANCE_MASK_NAMES[appearance_mask]);
}

static int appearance_head_bitmap(void) {
    if (appearance_sex) {
        return appearance_old ? IDB_HEAD_F_OLD : IDB_HEAD_F_YOUNG;
    }
    return appearance_old ? IDB_HEAD_M_OLD : IDB_HEAD_M_YOUNG;
}

static int appearance_body_bitmap(void) {
    return appearance_sex ? IDB_BODY_F : IDB_BODY_M;
}

static void appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
    /* The None entry has no artwork, so blitting its cell leaves an
       empty grey box next to Body and Head, which print words. Name
       it instead: a blank cell reads as a broken preview rather than
       a deliberate choice. */
    if (bitmap_id == IDB_MASK_PREVIEW && index == 0) {
        RECT none_rc = item->rcItem;
        HBRUSH none_bg = CreateSolidBrush(RGB(236, 236, 236));
        FillRect(item->hDC, &none_rc, none_bg);
        DeleteObject(none_bg);
        SetBkMode(item->hDC, TRANSPARENT);
        DrawTextA(item->hDC, "(None)", -1, &none_rc,
                  DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }

    RECT rc = item->rcItem;
    int width = rc.right - rc.left;
    int height = rc.bottom - rc.top;
    HBRUSH background = CreateSolidBrush(RGB(236, 236, 236));
    HBITMAP bitmap;
    HDC source;
    HBITMAP previous;
    double scale_x, scale_y, scale;
    int draw_w, draw_h, draw_x, draw_y;

    FillRect(item->hDC, &rc, background);
    DeleteObject(background);

    bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bitmap_id));
    if (bitmap == NULL) {
        return;
    }
    source = CreateCompatibleDC(item->hDC);
    previous = (HBITMAP)SelectObject(source, bitmap);

    scale_x = (double)width / APPEARANCE_CELL_W;
    scale_y = (double)height / APPEARANCE_CELL_H;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(APPEARANCE_CELL_W * scale);
    draw_h = (int)(APPEARANCE_CELL_H * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, index * APPEARANCE_CELL_W, 0, APPEARANCE_CELL_W, APPEARANCE_CELL_H,
        SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void appearance_repaint(HWND window, int control) {
    InvalidateRect(GetDlgItem(window, control), NULL, TRUE);
}

/* A pending Island Event or Barrel of Babies must not be sold again: both
   are queued by writing a value that may already be there -- the countdown
   zeroed, the barrel flag set -- so the second purchase changes nothing
   while still charging full price. That is the reported bug.

   The executable sets these bits while it builds the menu's state word, and
   the row is then drawn as a disabled "Unavailable" button. Refusing the
   click outright, rather than after it, is what makes this free: a refusal
   message would need a string, and these executables' string blocks are
   full.

   Dedicated bits, deliberately above every row bit (0-13), every (8 + row)
   unavailable bit (8-21) and every STATE_* flag (16-22). Reusing the
   (8 + row) scheme is not safe for these two rows: in a 14-row tech menu
   bit 9 means both "row 9 satisfied" and "row 1 unavailable". */
enum {
    STATE_ISLAND_PENDING = 0x800000,
    STATE_BARREL_PENDING = 0x1000000,
    /* Set when the barrel cannot be delivered because the village has no room
       for the children, as distinct from one already being queued.

       These shared a bit until Codex caught it on #254: the payload set
       STATE_BARREL_PENDING for BOTH causes, so a player whose village was full
       was told a barrel had already been bought -- a plainly false statement
       about their own save. VV4 was worse still, setting the barrel bit while
       only an Island Event was pending. */
    STATE_BARREL_NO_ROOM = 0x2000000
};

enum {
    PENDING_ROW_ISLAND = 1,   /* Island Event */
    PENDING_ROW_BARREL = 2    /* Barrel of Babies */
};

/* Is this tech-menu row blocked by an identical purchase already pending?
   Villager-menu rows are never affected. */
/* Villager record array. Base and stride are fixed in the image, so the DLL
   can answer this without anything from the executable. The slot bound comes
   from the same 0x41F1E6 immediate the Cure sweep reads, because expanded
   builds raise it.

   A slot counts as OCCUPIED whenever its active byte is set, alive or not.
   That is the point: an unburied skeleton still holds its record, and the
   game's own population counter skips it, so a village full of bodies reads as
   small while its slots are nearly all taken -- and the barrel then spawns
   fewer children than it charged for, sometimes none. */
#define VV5_RECORD_BASE      vv5_rec_base()
#define VV5_RECORD_STRIDE    0x2F44
#define VV5_SLOT_BOUND_PTR   0x41F1E6
#define VV5_OFF_ACTIVE       0x1CD4
#define VV5_BARREL_CHILDREN  3

static int vv5_has_free_villager_slots(int wanted) {
    unsigned int bound = *(volatile unsigned int *)(UINT_PTR)VV5_SLOT_BOUND_PTR;
    const unsigned char *record = (const unsigned char *)(UINT_PTR)VV5_RECORD_BASE;
    unsigned int index;
    int free_slots = 0;

    if (bound == 0 || bound > 256) {
        return 1;               /* unrecognised bound -> do not block */
    }
    for (index = 0; index < bound; ++index) {
        if (*(volatile unsigned char *)(record + VV5_OFF_ACTIVE) == 0) {
            ++free_slots;
            if (free_slots >= wanted) {
                return 1;
            }
        }
        record += VV5_RECORD_STRIDE;
    }
    return 0;
}

/* The live population cap, rebuilt exactly the way the payload's own
   barrel_room rebuilds it -- which is in turn exactly how the game's gate at
   0x472BD0 builds it.

   This is a SECOND capacity question, not a restatement of the record scan
   above. That scan counts free physical records; this counts against the
   population maximum the installed mode actually set. A village at its cap
   with records to spare -- the ordinary case -- passes the scan and fails
   this, and until now the row only asked the scan, so it read "Buy" and the
   purchase then refused it. Codex found this on #254.

   The bonuses and base are read from the bytes the population mode installed
   rather than hardcoded, so this tracks stock (90 + 15 = 105), Collection
   Progression (135 + 15 = 150) and Immediate Fixed (60 + 90 = 150) without
   knowing which is present:

     * the two collection bonuses (+5 each, both -> 15) come from the game's
       own 0x414690 on manager 0x4DBFC8, which is __thiscall;
     * Immediate Fixed replaces the "both -> 15" step at 0x472C04 with
       `mov esi, 0x3C`, so a 0xBE opcode there means a flat base with the
       bonuses discarded;
     * stock still has `add esi, 0x5A` at 0x472C49 (opcode 0x83), so the base
       is its own byte operand; the population modes replace that with a jump
       to the 0x494500 helper, whose `add esi, imm32` carries the raised base.

   Fails OPEN, unlike the payload's copy, and deliberately: this only decides
   whether to grey a row and say why, so an unrecognised form must not invent
   a refusal the purchase gate would not make. The payload's own check still
   fails closed before any charge, which is where the money is at stake. */
static int vv5_barrel_has_room_for_three(void) {
    unsigned int bonus = 0;
    unsigned int maximum;
    unsigned int current;

    if (*(volatile unsigned char *)(UINT_PTR)0x472C04 == 0xBE) {
        maximum = *(volatile unsigned int *)(UINT_PTR)0x472C05;
    } else {
        __asm {
            push 0x68
            mov ecx, 0x4DBFC8
            mov eax, 0x414690
            call eax
            test al, al
            je v5r_second
            add dword ptr bonus, 5
        v5r_second:
            push 0x50
            mov ecx, 0x4DBFC8
            mov eax, 0x414690
            call eax
            test al, al
            je v5r_done
            add dword ptr bonus, 5
        v5r_done:
        }
        maximum = (bonus == 10u) ? 15u : bonus;
    }

    if (*(volatile unsigned char *)(UINT_PTR)0x472C49 == 0x83) {
        maximum += *(volatile unsigned char *)(UINT_PTR)0x472C4B;
    } else if (*(volatile unsigned char *)(UINT_PTR)0x472C49 == 0xE9) {
        maximum += *(volatile unsigned int *)(UINT_PTR)0x494502;
    } else {
        return 1;               /* unrecognised form -> claim nothing */
    }

    __asm {
        mov eax, 0x4944C0
        call eax
        mov current, eax
    }
    return (current + 3u <= maximum) ? 1 : 0;
}

/* Why a Tech-menu row is blocked, or BLOCK_NONE.

   The two causes are kept distinct rather than collapsed into a boolean,
   because they ask completely different things of the player: a queued event
   clears itself in a few seconds, while a full village needs them to act. The
   row used to be drawn as a disabled button reading "Unavailable", which
   conveyed neither -- and a disabled button also swallows the click, so there
   was nowhere to put an explanation even if one existed.

   This covers only the two queued-event rows. VV5 also disables rows for
   STATE_LIMITED_CAPABILITY, which means something else entirely (this build
   is not verified for that path) and keeps its own "Unavailable" label. */
enum {
    BLOCK_NONE = 0,
    BLOCK_ALREADY_PENDING = 1,
    BLOCK_NO_VILLAGER_SLOTS = 2
};

#define ROW_STATE_MAX 16
static int block_reasons[ROW_STATE_MAX];

static const char *block_reason_text(int reason, int row) {
    if (reason == BLOCK_NO_VILLAGER_SLOTS) {
        return "There is not enough room in the village for the three children "
               "a barrel brings.\n\nThree villager slots have to be free. A "
               "villager who has died still occupies a slot until they are "
               "buried, and a pregnancy holds one too, so burying any remains "
               "may be enough to free the space.";
    }
    if (row == PENDING_ROW_ISLAND) {
        return "An island event has already been bought and is on its way."
               "\n\nIt arrives a few seconds after this screen closes. Buying "
               "it again would charge you a second time for the same event, "
               "so close this screen and wait for it to arrive.";
    }
    return "A barrel of babies has already been bought and is on its way."
           "\n\nIt arrives a few seconds after this screen closes. Buying it "
           "again would charge you a second time for the same barrel, so "
           "close this screen and wait for it to arrive.";
}

static int row_block_reason(int villager_menu, int row, long state) {
    if (villager_menu) {
        return BLOCK_NONE;
    }
    if (row == PENDING_ROW_ISLAND && (state & STATE_ISLAND_PENDING) != 0) {
        return BLOCK_ALREADY_PENDING;
    }
    if (row != PENDING_ROW_BARREL) {
        return BLOCK_NONE;
    }
    /* All three capacity sources, because they refuse independently. The
       payload may publish STATE_BARREL_NO_ROOM; the record scan catches
       physical exhaustion (slots held by the dead); and the live cap catches
       the ordinary population boundary. Asking only the first two left the row
       reading "Buy" right up to the mode's maximum, and the purchase preflight
       then refused what the row had just offered. */
    if ((state & STATE_BARREL_NO_ROOM) != 0
        || !vv5_has_free_villager_slots(VV5_BARREL_CHILDREN)
        || !vv5_barrel_has_room_for_three()) {
        return BLOCK_NO_VILLAGER_SLOTS;
    }
    if ((state & STATE_BARREL_PENDING) != 0) {
        return BLOCK_ALREADY_PENDING;
    }
    return BLOCK_NONE;
}

/* Thin wrapper so callers needing only the yes/no answer are unchanged. */
static int row_purchase_pending(int villager_menu, int row, long state) {
    return row_block_reason(villager_menu, row, state) != BLOCK_NONE;
}

static INT_PTR CALLBACK appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        vvfp_story_relabel(5, window);   /* "OK deducts 0 tech points" */
        appearance_update_mask_label(window);
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_BODY_PREVIEW) {
            appearance_draw(item, appearance_body_bitmap(), appearance_body);
            return TRUE;
        }
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            appearance_draw(item, appearance_head_bitmap(), appearance_head);
            return TRUE;
        }
        if (item->CtlID == IDC_MASK_PREVIEW) {
            appearance_draw(item, IDB_MASK_PREVIEW, appearance_mask);
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == IDC_BODY_PREV) {
            appearance_body = (appearance_body + APPEARANCE_BODY_COUNT - 1) % APPEARANCE_BODY_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_BODY_NEXT) {
            appearance_body = (appearance_body + 1) % APPEARANCE_BODY_COUNT;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_PREV) {
            appearance_head = (appearance_head + APPEARANCE_HEAD_COUNT - 1) % APPEARANCE_HEAD_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_HEAD_NEXT) {
            appearance_head = (appearance_head + 1) % APPEARANCE_HEAD_COUNT;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_PREV) {
            appearance_mask = (appearance_mask + APPEARANCE_MASK_COUNT - 1) % APPEARANCE_MASK_COUNT;
            appearance_update_mask_label(window);
            appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDC_MASK_NEXT) {
            appearance_mask = (appearance_mask + 1) % APPEARANCE_MASK_COUNT;
            appearance_update_mask_label(window);
            appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDOK) {
            EndDialog(window, 1);
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, 0);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

/* Declared ahead of its first use: the Change Appearance picker parents
   its modal on the validated owner rather than the foreground window. */
__declspec(dllexport) HWND __stdcall GetOriginsOwner(void);

__declspec(dllexport) int __stdcall ShowAppearanceChooser(
    int sex,
    int age,
    int *head,
    int *body,
    int *mask
) {
    INT_PTR result;
    appearance_sex = sex ? 1 : 0;
    appearance_old = age >= 1100 ? 1 : 0;
    appearance_head = (head && *head >= 0 && *head < APPEARANCE_HEAD_COUNT) ? *head : 0;
    appearance_body = (body && *body >= 0 && *body < APPEARANCE_BODY_COUNT) ? *body : 0;
    appearance_mask = (mask && *mask >= 0 && *mask < APPEARANCE_MASK_COUNT) ? *mask : 0;

    /* GetOriginsOwner, not GetForegroundWindow. The emitted owner contract
       promises "same-process HWND only; ... no foreground fallback", and a raw
       foreground read breaks that: if focus moves to another application while
       the purchase confirmation is open, the chooser parents itself to an
       unrelated window. The owner is captured and validated by
       BeginOriginsOwner before the menu opens, so it is available here. */
    result = DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_APPEARANCE),
        GetOriginsOwner(),
        appearance_dialog,
        0
    );
    if (result == 1) {
        if (head) {
            *head = appearance_head;
        }
        if (body) {
            *body = appearance_body;
        }
        if (mask) {
            *mask = appearance_mask;
        }
        return 1;
    }
    return 0;
}

/* The chooser never sees the record, so the exe's router calls this once it has written the new
   look into it (scripts/build_vv5_task9_native_actions.py, build_appearance). */
__declspec(dllexport) void __stdcall LogVV5AppearanceChange(
    const void *record,
    int old_head,
    int old_body,
    int new_head,
    int new_body
) {
    vv_log_appearance(5, record, old_head, old_body, new_head, new_body);
}

__declspec(dllexport) void __stdcall WriteMaskSidecar(const unsigned char *table);

/* ---------- Change Appearance for All (VV2-style, VV5 offsets) ----------
   Whole-village mass appearance editor for the Tech screen (450,000 tech). The
   DLL owns the entire commit: it shows dialog 214, then -- reading the game's
   absolute non-ASLR globals directly -- iterates the villager record array,
   applies the chosen head/body (per-sex or a village-wide override) and mask
   (per-sex, a village-wide single colour, or a distribution) writing head/body
   into the record and the mask into the exe's nibble-packed side-table, charges
   450,000 ONLY if at least one active villager was touched, and saves the mask
   sidecar. The exe side is a one-call bridge that never touches save data. */
#define IDD_APPEARANCE_ALL 214
/* per-sex owner-draw cyclers */
#define IDC_CAF_M_BODY 3201
#define IDC_CAF_M_HEAD 3202
#define IDC_CAF_M_MASK 3203
#define IDC_CAF_F_BODY 3204
#define IDC_CAF_F_HEAD 3205
#define IDC_CAF_F_MASK 3206
#define IDC_CAF_M_BODY_P 3211
#define IDC_CAF_M_HEAD_P 3212
#define IDC_CAF_M_MASK_P 3213
#define IDC_CAF_F_BODY_P 3214
#define IDC_CAF_F_HEAD_P 3215
#define IDC_CAF_F_MASK_P 3216
#define IDC_CAF_M_BODY_N 3221
#define IDC_CAF_M_HEAD_N 3222
#define IDC_CAF_M_MASK_N 3223
#define IDC_CAF_F_BODY_N 3224
#define IDC_CAF_F_HEAD_N 3225
#define IDC_CAF_F_MASK_N 3226
/* Mask Distribution radios */
#define IDC_CAF_DIST_OFF   3230
#define IDC_CAF_DIST_VV5   3231
#define IDC_CAF_DIST_RANDN 3232
#define IDC_CAF_DIST_RAND5 3234
#define IDC_CAF_DIST_EQUAL 3233
/* Village-wide single mask colour radios */
#define IDC_CAF_SINGLE_FIRST 3241   /* 3241..3246 = None,Blue,Orange,Red,Purple,Chief */
/* Village-wide Heads / Bodies radios */
#define IDC_CAF_HEADS_FIRST  3250   /* 3250..3256 = Off,Random,Black,Brown,Red,Blonde,Other */
#define IDC_CAF_BODIES_OFF   3260
#define IDC_CAF_BODIES_RAND  3261

/* VV5 game globals (non-ASLR, absolute) */
#define VV5_REC_BASE   vv5_rec_base()   /* 0x554190, or 0x800048 with 256 Villagers */
#define VV5_REC_STRIDE 0x2F44u
#define VV5_REC_COUNT  VV5_MAX_VILLAGERS /* array sizes; every walk stops at vv5_slots() */
#define VV5_OFF_ACTIVE 0x1CD4      /* byte, 0 = free/dead */
#define VV5_OFF_SEX    0x1B90      /* dword, 0 = male, 1 = female */
#define VV5_OFF_AGE    0x1B8C      /* dword */
#define VV5_OFF_HEAD   0x1BB8      /* dword head index 0..29 */
#define VV5_OFF_BODY   0x1BBC      /* dword body index 0..28 */
#define VV5_OFF_RANK    0x1CFC     /* dword chief-rank marker; 0xD on the Retired Chief, 0 on ordinary villagers */
#define VV5_RANK_RETIRED_CHIEF 0x0D
#define VV5_TECH       0x0051D5F8u /* int tech-point balance */
#define VV5_CHARGE_FN  0x004237B0u /* __thiscall(void* balance_ptr, int delta) */

/* Charge the tech balance through the game's own tech-adjust routine
   (0x4237B0, __thiscall: ecx = balance ptr, delta on stack). Inline asm avoids a
   __thiscall function-pointer cast, which the C compiler rejects. */
static void caf_charge(int delta) {
    __asm {
        mov  eax, delta
        push eax
        mov  ecx, 0x51D5F8
        mov  eax, 0x4237B0
        call eax
    }
}
/* The whole-village chooser must offer exactly what the individual one
   does, so these track APPEARANCE_*_COUNT rather than carrying their own
   numbers -- a separate 29 here left body 29 reachable only per villager. */
#define VV5_HEAD_COUNT APPEARANCE_HEAD_COUNT
#define VV5_BODY_COUNT APPEARANCE_BODY_COUNT

/* Hair-colour buckets (head-atlas rows) for the "All <colour> Hair" options.
   Seeded from the hair-band median RGB then hand-verified against a labelled
   render (VV2 principle: RED = only clearly-ginger / high-saturation warm hair;
   auburn/dark-gold reads as BROWN; dyed green/blue and grey elder hair -> OTHER).
   adjust an index here if any head is miscategorised. */
static const unsigned char CAF_M_BLACK[]  = {0,1,2,4,5,7,19};
static const unsigned char CAF_M_BROWN[]  = {6,8,9,10,12,13,16};
static const unsigned char CAF_M_RED[]    = {11,20,21,22};
static const unsigned char CAF_M_BLONDE[] = {14,15,17,18,23,24,25,26,27,28,29};
static const unsigned char CAF_M_OTHER[]  = {3};
static const unsigned char CAF_F_BLACK[]  = {0,1,2,3,4,6};
static const unsigned char CAF_F_BROWN[]  = {8,10,11,12,13,14,16,20,23};
static const unsigned char CAF_F_RED[]    = {7,9,15,17,19,22};
static const unsigned char CAF_F_BLONDE[] = {24,25,26,27,28,29};
static const unsigned char CAF_F_OTHER[]  = {5,18,21};

/* dialog state: per-sex cyclers ([0]=male,[1]=female); -1 = "No change". */
static int caf_body[2];
static int caf_head[2];
static int caf_mask[2];
static int caf_heads_mode;   /* 0=Off,1=Random,2=Black,3=Brown,4=Red,5=Blonde,6=Other */
static int caf_bodies_mode;  /* 0=Off,1=Random */
static int caf_mask_dist;    /* 0=Off,1=VV5,2=Rand+None,3=RandAll5,4=Equal */
static int caf_single_mask;  /* -1 = none selected; 0..5 = single colour override */

static unsigned int caf_rng;
static unsigned int caf_rand(void) {           /* xorshift, self-contained */
    caf_rng ^= caf_rng << 13; caf_rng ^= caf_rng >> 17; caf_rng ^= caf_rng << 5;
    return caf_rng;
}

static unsigned char *caf_rec(int i) {
    return (unsigned char *)(VV5_REC_BASE + (unsigned int)i * VV5_REC_STRIDE);
}
static int caf_get_mask(int idx) {
    const unsigned char *t = (const unsigned char *)VV5_MASK_TABLE;
    unsigned char b = t[idx >> 1];
    return (idx & 1) ? ((b >> 4) & 0x0F) : (b & 0x0F);
}
/* Every appearance write goes through these two, and both report whether they
   actually changed anything.  The caller charges 450,000 on a positive count,
   so counting writes instead of changes billed the player for re-selecting the
   head, body or mask colour a villager already had -- a village left
   byte-identical.  VV1 through VV4 all count changes; VV5 was the exception. */
static int caf_set_mask(int idx, int mask) {
    unsigned char *t = (unsigned char *)VV5_MASK_TABLE;
    unsigned char b = t[idx >> 1];
    if (caf_get_mask(idx) == (mask & 0x0F)) return 0;
    if (idx & 1) b = (unsigned char)((b & 0x0F) | ((mask & 0x0F) << 4));
    else         b = (unsigned char)((b & 0xF0) | (mask & 0x0F));
    t[idx >> 1] = b;
    return 1;
}
static int caf_set_field(int idx, int offset, int value) {
    int *field = (int *)(caf_rec(idx) + offset);
    if (*field == value) return 0;
    *field = value;
    return 1;
}
static int caf_bucket_head(int sex, int mode) {
    const unsigned char *b; int n;
    switch (mode) {
        case 2: b = sex ? CAF_F_BLACK : CAF_M_BLACK; n = sex ? (int)(sizeof CAF_F_BLACK) : (int)(sizeof CAF_M_BLACK); break;
        case 3: b = sex ? CAF_F_BROWN : CAF_M_BROWN; n = sex ? (int)(sizeof CAF_F_BROWN) : (int)(sizeof CAF_M_BROWN); break;
        case 4: b = sex ? CAF_F_RED : CAF_M_RED;     n = sex ? (int)(sizeof CAF_F_RED)   : (int)(sizeof CAF_M_RED);   break;
        case 5: b = sex ? CAF_F_BLONDE : CAF_M_BLONDE; n = sex ? (int)(sizeof CAF_F_BLONDE) : (int)(sizeof CAF_M_BLONDE); break;
        default: b = sex ? CAF_F_OTHER : CAF_M_OTHER; n = sex ? (int)(sizeof CAF_F_OTHER) : (int)(sizeof CAF_M_OTHER); break;
    }
    return b[caf_rand() % (unsigned)n];
}

/* Find the Retired Chief for the VV5-style single Chief slot. The Retired Chief
   is the one villager carrying the native chief-rank marker +0x1CFC == 0xD;
   ordinary villagers read 0 there. Verified live: in a real village exactly one
   villager (the Retired Chief) has this set, and it is his native value (his mask
   in the side-table is unrelated). The mask feature only flips +0x1CFC transiently
   inside the render, so at apply time it holds the native value. If no Retired
   Chief exists in the village, a RANDOM active villager gets the Chief mask.
   Returns -1 only if the village is empty. */
static int caf_find_chief(const int *active, int na) {
    int i;
    if (na <= 0) return -1;
    for (i = 0; i < na; ++i) {
        if (*(unsigned int *)(caf_rec(active[i]) + VV5_OFF_RANK) == VV5_RANK_RETIRED_CHIEF)
            return i;
    }
    return (int)(caf_rand() % (unsigned)na);
}

static void caf_shuffle(int *a, int n) {
    int i, j, t;
    for (i = n - 1; i > 0; --i) { j = (int)(caf_rand() % (unsigned)(i + 1)); t = a[i]; a[i] = a[j]; a[j] = t; }
}

/* Apply the current dialog selection to every active villager. Returns the
   number of active villagers touched (0 if nothing was selected / village
   empty). Head/body writes go to the record; mask writes go to the side-table. */
static int caf_apply(void) {
    int active[VV5_REC_COUNT];
    int sex_of[VV5_REC_COUNT];
    int old_head[VV5_REC_COUNT];
    int old_body[VV5_REC_COUNT];
    int na = 0, i, touched = 0, slots = vv5_slots();
    for (i = 0; i < slots; ++i) {
        unsigned char *r = caf_rec(i);
        if (r[VV5_OFF_ACTIVE] == 0) continue;
        active[na] = i;
        sex_of[na] = (*(int *)(r + VV5_OFF_SEX)) ? 1 : 0;
        old_head[na] = *(int *)(r + VV5_OFF_HEAD);
        old_body[na] = *(int *)(r + VV5_OFF_BODY);
        ++na;
    }
    if (na == 0) return 0;

    /* Heads */
    if (caf_heads_mode != 0) {
        for (i = 0; i < na; ++i)
            touched += caf_set_field(active[i], VV5_OFF_HEAD,
                (caf_heads_mode == 1) ? (int)(caf_rand() % VV5_HEAD_COUNT)
                                      : caf_bucket_head(sex_of[i], caf_heads_mode));
    } else {
        for (i = 0; i < na; ++i)
            if (caf_head[sex_of[i]] >= 0)
                touched += caf_set_field(active[i], VV5_OFF_HEAD, caf_head[sex_of[i]]);
    }
    /* Bodies */
    if (caf_bodies_mode != 0) {
        for (i = 0; i < na; ++i)
            touched += caf_set_field(active[i], VV5_OFF_BODY,
                                     (int)(caf_rand() % VV5_BODY_COUNT));
    } else {
        for (i = 0; i < na; ++i)
            if (caf_body[sex_of[i]] >= 0)
                touched += caf_set_field(active[i], VV5_OFF_BODY, caf_body[sex_of[i]]);
    }
    /* Change Appearance for All is logged too (Codex, #558). */
    for (i = 0; i < na; ++i)
        vv_log_appearance(5, caf_rec(active[i]), old_head[i], old_body[i],
                          *(int *)(caf_rec(active[i]) + VV5_OFF_HEAD), *(int *)(caf_rec(active[i]) + VV5_OFF_BODY));
    /* Masks */
    if (caf_single_mask >= 0) {                       /* village-wide single colour */
        for (i = 0; i < na; ++i) touched += caf_set_mask(active[i], caf_single_mask);
    } else if (caf_mask_dist == 1) {                  /* VV5-style tiers */
        int order[VV5_REC_COUNT], k;
        for (i = 0; i < na; ++i) order[i] = i;         /* index into active[] */
        caf_shuffle(order, na);
        {
            int chief = caf_find_chief(active, na);
            int purple = 4, red = 7, orange = 10, assigned = 0;
            for (k = 0; k < na; ++k) {
                int slot = order[k], m;
                if (active[slot] == (chief >= 0 ? active[chief] : -1)) continue; /* chief handled below */
                if (assigned < purple) m = 4;
                else if (assigned < purple + red) m = 3;
                else if (assigned < purple + red + orange) m = 2;
                else m = 1;
                touched += caf_set_mask(active[slot], m);
                ++assigned;
            }
            if (chief >= 0) touched += caf_set_mask(active[chief], 5);
        }
    } else if (caf_mask_dist == 2) {                  /* Random (All 5 + No Mask) */
        for (i = 0; i < na; ++i) touched += caf_set_mask(active[i], (int)(caf_rand() % 6));
    } else if (caf_mask_dist == 3) {                  /* Random (All 5) */
        for (i = 0; i < na; ++i) touched += caf_set_mask(active[i], (int)(caf_rand() % 5) + 1);
    } else if (caf_mask_dist == 4) {                  /* Equal, balanced M/F */
        int males[VV5_REC_COUNT], females[VV5_REC_COUNT], nm = 0, nf = 0, k = 0, a = 0, b = 0;
        for (i = 0; i < na; ++i) (sex_of[i] ? (females[nf++] = active[i]) : (males[nm++] = active[i]));
        caf_shuffle(males, nm); caf_shuffle(females, nf);
        while (a < nm || b < nf) {
            if (a < nm) touched += caf_set_mask(males[a++], (k++ % 5) + 1);
            if (b < nf) touched += caf_set_mask(females[b++], (k++ % 5) + 1);
        }
    } else {                                          /* Off -> per-sex mask cyclers */
        for (i = 0; i < na; ++i)
            if (caf_mask[sex_of[i]] >= 0)
                touched += caf_set_mask(active[i], caf_mask[sex_of[i]]);
    }
    return touched;
}

/* draw one for-All preview cell: "No change" text when value < 0, else the
   stock sprite cell (young head atlas / body / mask strip). */
static void caf_draw(DRAWITEMSTRUCT *item, int sex, int kind, int value) {
    RECT rc = item->rcItem;
    HBRUSH bg = CreateSolidBrush(RGB(236, 236, 236));
    int bmp_id, cell_w, cell_h;
    FillRect(item->hDC, &rc, bg);
    DeleteObject(bg);
    if (value < 0) {
        SetBkMode(item->hDC, TRANSPARENT);
        DrawTextA(item->hDC, "No change", -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }
    if (kind == 0) { bmp_id = sex ? IDB_BODY_F : IDB_BODY_M; cell_w = APPEARANCE_CELL_W; cell_h = APPEARANCE_CELL_H; }
    else if (kind == 1) { bmp_id = sex ? IDB_HEAD_F_YOUNG : IDB_HEAD_M_YOUNG; cell_w = APPEARANCE_CELL_W; cell_h = APPEARANCE_CELL_H; }
    else { bmp_id = IDB_MASK_PREVIEW; cell_w = APPEARANCE_CELL_W; cell_h = APPEARANCE_CELL_H; }
    {
        HBITMAP bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bmp_id));
        HDC src; HBITMAP prev; double sx, sy, s; int dw, dh, dx, dy;
        int w = rc.right - rc.left, h = rc.bottom - rc.top;
        if (bitmap == NULL) return;
        src = CreateCompatibleDC(item->hDC);
        prev = (HBITMAP)SelectObject(src, bitmap);
        sx = (double)w / cell_w; sy = (double)h / cell_h; s = sx < sy ? sx : sy;
        dw = (int)(cell_w * s); dh = (int)(cell_h * s);
        dx = rc.left + (w - dw) / 2; dy = rc.top + (h - dh) / 2;
        SetStretchBltMode(item->hDC, COLORONCOLOR);
        StretchBlt(item->hDC, dx, dy, dw, dh, src, value * cell_w, 0, cell_w, cell_h, SRCCOPY);
        SelectObject(src, prev); DeleteDC(src); DeleteObject(bitmap);
    }
}

static void caf_cycle(int *v, int max, int dir) {   /* -1 = No change wraps at each end */
    if (dir > 0) *v = (*v >= max) ? -1 : (*v + 1);
    else         *v = (*v < 0) ? max : (*v - 1);
}
static void caf_repaint(HWND w, int id) { InvalidateRect(GetDlgItem(w, id), NULL, TRUE); }

static void caf_update_gray(HWND w) {
    int mask_override = (caf_mask_dist != 0) || (caf_single_mask >= 0);
    int head_override = (caf_heads_mode != 0);
    int body_override = (caf_bodies_mode != 0);
    int i;
    static const int mask_c[] = {IDC_CAF_M_MASK_P, IDC_CAF_M_MASK_N, IDC_CAF_F_MASK_P, IDC_CAF_F_MASK_N};
    static const int head_c[] = {IDC_CAF_M_HEAD_P, IDC_CAF_M_HEAD_N, IDC_CAF_F_HEAD_P, IDC_CAF_F_HEAD_N};
    static const int body_c[] = {IDC_CAF_M_BODY_P, IDC_CAF_M_BODY_N, IDC_CAF_F_BODY_P, IDC_CAF_F_BODY_N};
    for (i = 0; i < 4; ++i) EnableWindow(GetDlgItem(w, mask_c[i]), !mask_override);
    for (i = 0; i < 4; ++i) EnableWindow(GetDlgItem(w, head_c[i]), !head_override);
    for (i = 0; i < 4; ++i) EnableWindow(GetDlgItem(w, body_c[i]), !body_override);
}

static INT_PTR CALLBACK caf_dialog(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_INITDIALOG) {
        vvfp_story_relabel(5, w);   /* "OK deducts 0 tech points" */
        caf_body[0] = caf_body[1] = caf_head[0] = caf_head[1] = caf_mask[0] = caf_mask[1] = -1;
        caf_heads_mode = 0; caf_bodies_mode = 0; caf_mask_dist = 0; caf_single_mask = -1;
        CheckDlgButton(w, IDC_CAF_HEADS_FIRST, BST_CHECKED);
        CheckDlgButton(w, IDC_CAF_BODIES_OFF, BST_CHECKED);
        CheckDlgButton(w, IDC_CAF_DIST_OFF, BST_CHECKED);
        caf_update_gray(w);
        return TRUE;
    } else if (msg == WM_DRAWITEM) {
        DRAWITEMSTRUCT *it = (DRAWITEMSTRUCT *)lp;
        switch (it->CtlID) {
            case IDC_CAF_M_BODY: caf_draw(it, 0, 0, caf_body[0]); return TRUE;
            case IDC_CAF_M_HEAD: caf_draw(it, 0, 1, caf_head[0]); return TRUE;
            case IDC_CAF_M_MASK: caf_draw(it, 0, 2, caf_mask[0]); return TRUE;
            case IDC_CAF_F_BODY: caf_draw(it, 1, 0, caf_body[1]); return TRUE;
            case IDC_CAF_F_HEAD: caf_draw(it, 1, 1, caf_head[1]); return TRUE;
            case IDC_CAF_F_MASK: caf_draw(it, 1, 2, caf_mask[1]); return TRUE;
        }
    } else if (msg == WM_COMMAND) {
        int id = LOWORD(wp);
        switch (id) {
            case IDC_CAF_M_BODY_P: caf_cycle(&caf_body[0], VV5_BODY_COUNT - 1, -1); caf_repaint(w, IDC_CAF_M_BODY); return TRUE;
            case IDC_CAF_M_BODY_N: caf_cycle(&caf_body[0], VV5_BODY_COUNT - 1,  1); caf_repaint(w, IDC_CAF_M_BODY); return TRUE;
            case IDC_CAF_F_BODY_P: caf_cycle(&caf_body[1], VV5_BODY_COUNT - 1, -1); caf_repaint(w, IDC_CAF_F_BODY); return TRUE;
            case IDC_CAF_F_BODY_N: caf_cycle(&caf_body[1], VV5_BODY_COUNT - 1,  1); caf_repaint(w, IDC_CAF_F_BODY); return TRUE;
            case IDC_CAF_M_HEAD_P: caf_cycle(&caf_head[0], VV5_HEAD_COUNT - 1, -1); caf_repaint(w, IDC_CAF_M_HEAD); return TRUE;
            case IDC_CAF_M_HEAD_N: caf_cycle(&caf_head[0], VV5_HEAD_COUNT - 1,  1); caf_repaint(w, IDC_CAF_M_HEAD); return TRUE;
            case IDC_CAF_F_HEAD_P: caf_cycle(&caf_head[1], VV5_HEAD_COUNT - 1, -1); caf_repaint(w, IDC_CAF_F_HEAD); return TRUE;
            case IDC_CAF_F_HEAD_N: caf_cycle(&caf_head[1], VV5_HEAD_COUNT - 1,  1); caf_repaint(w, IDC_CAF_F_HEAD); return TRUE;
            case IDC_CAF_M_MASK_P: caf_cycle(&caf_mask[0], 5, -1); caf_repaint(w, IDC_CAF_M_MASK); return TRUE;
            case IDC_CAF_M_MASK_N: caf_cycle(&caf_mask[0], 5,  1); caf_repaint(w, IDC_CAF_M_MASK); return TRUE;
            case IDC_CAF_F_MASK_P: caf_cycle(&caf_mask[1], 5, -1); caf_repaint(w, IDC_CAF_F_MASK); return TRUE;
            case IDC_CAF_F_MASK_N: caf_cycle(&caf_mask[1], 5,  1); caf_repaint(w, IDC_CAF_F_MASK); return TRUE;
            case IDOK: EndDialog(w, 1); return TRUE;
            case IDCANCEL: EndDialog(w, 0); return TRUE;
        }
        if (id >= IDC_CAF_HEADS_FIRST && id <= IDC_CAF_HEADS_FIRST + 6) {
            caf_heads_mode = id - IDC_CAF_HEADS_FIRST; caf_update_gray(w); return TRUE;
        }
        if (id == IDC_CAF_BODIES_OFF || id == IDC_CAF_BODIES_RAND) {
            caf_bodies_mode = (id == IDC_CAF_BODIES_RAND) ? 1 : 0; caf_update_gray(w); return TRUE;
        }
        /* Mask Distribution + Single-Mask-Colour are ONE logical group across two
           groupboxes: selecting one clears the other. */
        if (id == IDC_CAF_DIST_OFF || id == IDC_CAF_DIST_VV5 || id == IDC_CAF_DIST_RANDN
            || id == IDC_CAF_DIST_RAND5 || id == IDC_CAF_DIST_EQUAL) {
            int m; caf_single_mask = -1;
            for (m = 0; m < 6; ++m) CheckDlgButton(w, IDC_CAF_SINGLE_FIRST + m, BST_UNCHECKED);
            caf_mask_dist = (id == IDC_CAF_DIST_VV5) ? 1 : (id == IDC_CAF_DIST_RANDN) ? 2
                          : (id == IDC_CAF_DIST_RAND5) ? 3 : (id == IDC_CAF_DIST_EQUAL) ? 4 : 0;
            caf_update_gray(w); return TRUE;
        }
        if (id >= IDC_CAF_SINGLE_FIRST && id <= IDC_CAF_SINGLE_FIRST + 5) {
            CheckDlgButton(w, IDC_CAF_DIST_OFF, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_VV5, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_RANDN, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_RAND5, BST_UNCHECKED);
            CheckDlgButton(w, IDC_CAF_DIST_EQUAL, BST_UNCHECKED);
            caf_mask_dist = 0; caf_single_mask = id - IDC_CAF_SINGLE_FIRST;
            caf_update_gray(w); return TRUE;
        }
    } else if (msg == WM_CLOSE) {
        EndDialog(w, 0); return TRUE;
    }
    return FALSE;
}

/* Change Appearance for All. Shows dialog 214; on OK, if the village has enough
   tech and at least one villager is touched, applies to all and charges 450,000
   via the game's own tech-adjust routine, then saves the mask sidecar. Returns
   1 if applied+charged, 0 otherwise. All commit logic is here (exe is a bridge). */
/* ------------------------------------------------------------------ *
 *  Time Warp                                                          *
 * ------------------------------------------------------------------ *
 *
 * The clamp is the same as the other four -- 0x0046FFCB: over 86400 becomes
 * 86400, otherwise anything over 23800 slow / 31000 normal / 38200 fast is
 * forced to 31000 -- so the shipped flat 43200 collapses at every speed and
 * lands 2.55 / 4.3 / 8.6 years instead of 3 / 6 / 12.
 *
 * But VV5's conversion is NOT the same as the others, and this is the only
 * game where it differs.  Its loop at 0x00470040 reads a per-villager aging
 * RATE from +0x1CC8 and folds it in:
 *
 *     edi = [rec+0x1CC8];  if (edi > 1) edi += edi;      // 0x00470046
 *     units = ((pending / 60) * edi) / speed_code;       // 0x0047006C
 *
 * so a villager whose rate is 2 ages at four times the base, not twice.  And
 * the credit is gated on the faction byte at +0x1CEC being zero
 * (0x00470077) -- villagers outside it do not age at all.
 *
 * Crediting a flat years*20 to everyone would therefore be wrong in both
 * directions: it would under-age the fast agers and over-age the gated ones.
 * The rate is reproduced here instead, so a warp advances exactly what the
 * same elapsed time would have.
 *
 *   pending slice   record + 0x1C34
 *   last-seen mark  record + 0x1C38
 *   age units       record + 0x1B8C, 20 units == 1 villager year
 *
 * VV5's adder at 0x0046F7F0 is a plain `add dword ptr [ecx], eax; ret 4` with
 * no side effects, so the field is written directly.  (VV3's is not -- its
 * adder fires the 80-year notification -- which is why only VV3 calls the
 * game's routine.)
 *
 * The epoch is 64-bit: the executable's own advance did `sub` then `sbb`, so
 * the borrow into the high dword has to be reproduced.
 */
#define VV5_TW_SPEED_OFFSET     0x17D7C  /* on the world object; 999 = paused */
#define VV5_TW_SPEED_PAUSED     999
#define VV5_TW_WORLD_GETTER     0x00425950u
#define VV5_TW_TIME_EPOCH_VA    0x004C6250u   /* 64-bit, low dword           */
#define VV5_TW_PENDING_OFFSET   0x1C34
#define VV5_TW_LAST_SEEN_OFFSET 0x1C38
#define VV5_TW_AGE_OFFSET       0x1B8C
#define VV5_TW_RATE_OFFSET      0x1CC8   /* per-villager aging rate          */
#define VV5_TW_FACTION_OFFSET   0x1CEC   /* byte; only 0 ages                */
#define VV5_TW_UNITS_PER_YEAR   20

/* Speed codes are the engine's own divisors.  A year is 20 * 60 * code
   seconds: 2 hours at normal and 1 at fast exactly, and 3h20m at slow -- slow
   is NOT the 4 hours it is often quoted as, which is why the years are
   targeted directly here instead of derived from an hours-per-year figure. */
#define VV5_TW_SPEED_SLOW       10
#define VV5_TW_SPEED_NORMAL     6
#define VV5_TW_SPEED_FAST       3

#define VV5_TW_CANCELLED 0
#define VV5_TW_APPLIED   1
#define VV5_TW_REFUSED   2

typedef unsigned char *(__cdecl *vv5_world_getter_fn)(void);

static int vv5_time_warp_years(int speed) {
    switch (speed) {
    case VV5_TW_SPEED_SLOW:   return 3;
    case VV5_TW_SPEED_NORMAL: return 6;
    case VV5_TW_SPEED_FAST:   return 12;
    default:                  return 0;   /* paused, or a code we don't know */
    }
}

static const char *vv5_speed_name(int speed) {
    switch (speed) {
    case VV5_TW_SPEED_SLOW:   return "slow";
    case VV5_TW_SPEED_NORMAL: return "normal";
    case VV5_TW_SPEED_FAST:   return "fast";
    default:                  return "unknown";
    }
}

/* The engine's own rate fold, reproduced exactly (0x00470046). */
static int vv5_aging_rate(const unsigned char *rec) {
    int rate = *(const int *)(rec + VV5_TW_RATE_OFFSET);
    return rate > 1 ? rate + rate : rate;
}

/* Returns how many occupied records were carried, 0 when the village is
   empty -- the caller treats that as "nothing happened" and charges nothing. */
typedef void(__fastcall *vv5_charge_fn)(void *balance, int unused_edx, int delta);


/* Count BEFORE touching anything: an empty village must not move the world
   clock and must not be billed. Any occupied record counts, whether or not the
   age credit will reach it -- see the marker write below for why that
   distinction matters. This is a helper of its own, unlike the other four
   games, because the charge sits between the confirmation and the mutation and
   so needs the count before either. */
static int vv5_village_occupied(void) {
    const unsigned char *base = (const unsigned char *)(UINT_PTR)VV5_REC_BASE;
    int i, occupied = 0, slots = vv5_slots();
    for (i = 0; i < slots; ++i) {
        if (base[(size_t)i * VV5_REC_STRIDE + VV5_OFF_ACTIVE] != 0) {
            ++occupied;
        }
    }
    return occupied;
}


static int vv5_time_warp_apply(int speed, int years) {
    unsigned char *base = (unsigned char *)(UINT_PTR)VV5_REC_BASE;
    int units = years * VV5_TW_UNITS_PER_YEAR;   /* the base-rate credit */
    int delta = units * 60 * speed;              /* the real seconds it costs */
    int i, occupied = vv5_village_occupied(), slots = vv5_slots();

    if (occupied == 0) {
        return 0;
    }

    /* Half one: the world clock.  64-bit, so the borrow has to be carried --
       the executable's own advance was `sub` followed by `sbb`. */
    {
        unsigned int *epoch = (unsigned int *)(UINT_PTR)VV5_TW_TIME_EPOCH_VA;
        unsigned int low = epoch[0];
        epoch[0] = low - (unsigned int)delta;
        if (low < (unsigned int)delta) {
            epoch[1] -= 1;
        }
    }

    /* Half two: exact ages, past the clamp. */
    for (i = 0; i < slots; ++i) {
        unsigned char *rec = base + (size_t)i * VV5_REC_STRIDE;
        int rate;
        if (rec[VV5_OFF_ACTIVE] == 0) {
            continue;
        }
        /* The marker moves for EVERY occupied record, including ones the age
           credit skips.  It is what stops that villager's own tick from
           putting this jump through the clamp -- skipping it would not hold
           the record's age, it would advance it by the clamped amount. */
        *(int *)(rec + VV5_TW_LAST_SEEN_OFFSET) += delta;
        /* Only the faction the engine ages gets the credit (0x00470077),
           and only the living (0x0046FF63): a body holds its record but no
           longer ages -- credited, its age at death grew with every warp. */
        if (rec[VV5_TW_FACTION_OFFSET] != 0) {
            continue;
        }
        if (*(const int *)(rec + 0x1C40) <= 0) {
            continue;
        }
        rate = vv5_aging_rate(rec);
        if (rate <= 0) {
            continue;               /* rate 0 -> this villager does not age */
        }
        *(int *)(rec + VV5_TW_AGE_OFFSET) += units * rate;
    }
    return occupied;
}

/* Group a cost with thousands separators, matching every other purchase box in
   this menu: those read their price from a pre-formatted table ("50,000"), but
   Time Warp receives its cost as an argument, so it has to format the value it
   was actually given rather than substitute a fixed string. Mirrors VV1's
   vv1_format_cost. `out` must be at least 16 bytes; the largest upgrade cost is
   7 digits (1,000,000). */
static void vv5_format_cost(int value, char *out) {
    char digits[16];
    int count = 0;
    int position;
    int written = 0;
    if (value < 0) {
        value = 0;
    }
    do {
        digits[count++] = (char)('0' + (value % 10));
        value /= 10;
    } while (value > 0 && count < (int)sizeof(digits));
    for (position = count - 1; position >= 0; --position) {
        out[written++] = digits[position];
        if (position > 0 && (position % 3) == 0) {
            out[written++] = ',';
        }
    }
    out[written] = '\0';
}

/* Tech-menu row 0.  Owns the WHOLE transaction, in this order: confirm
   (naming the current speed and the years it buys), count the village, verify
   funds, charge through the game's own tech-point routine at 0x004237B0, read
   the deduction back, and only then move the clock and credit the villagers.

   The charge lives here, not in the executable, and the ordering is the whole
   point.  The confirmation is a blocking MessageBoxA, so a balance the caller
   reads before this returns is stale by the time the player answers; and a
   charge issued after this returns is too late, because the clock has moved,
   every villager has been credited and "Advanced N years" has been shown, so
   a deduction that did not land grants a free warp that was already reported.
   Between the confirmation and the first write is the only correct place, and
   only this function can be there.  The executable must NOT deduct anything.

   Return value, which the caller branches on:
     0  the player pressed Cancel -- nothing was said, nothing was charged and
        nothing was done.  The caller must stay silent too: this box is the
        only dialog one Time Warp click may produce;
     1  applied, and already paid for;
     2  refused, with the reason already shown, and nothing charged. */
/* ---- Story / Cheat Upgrades host (Custom Island Event) -----------------
   The save slot the mask sidecar is keyed by, and one villager's mask, set
   exactly as Change Appearance for All commits one (the nibble table, then
   the sidecar). */
static int vv5_story_index(void *record) {
    unsigned int delta;
    if ((unsigned int)(UINT_PTR)record < VV5_REC_BASE) {
        return -1;
    }
    delta = (unsigned int)(UINT_PTR)record - VV5_REC_BASE;
    if (delta % VV5_REC_STRIDE != 0 || delta / VV5_REC_STRIDE >= (unsigned int)vv5_slots()) {
        return -1;
    }
    return (int)(delta / VV5_REC_STRIDE);
}

static int __stdcall vv5_story_slot(void) {
    return vv_current_save_slot(5, *(volatile int *)VV5_SLOT_SCRATCH);
}

static int __stdcall vv5_story_mask_get(void *record) {
    int index = vv5_story_index(record);
    int mask;
    if (index < 0) {
        return 0;
    }
    mask = caf_get_mask(index);
    return mask < APPEARANCE_MASK_COUNT ? mask : 0;
}

static int __stdcall vv5_story_mask_set(void *record, int mask) {
    int index = vv5_story_index(record);
    if (index < 0 || mask < 0 || mask >= APPEARANCE_MASK_COUNT) {
        return 0;
    }
    caf_set_mask(index, mask);
    WriteMaskSidecar((const unsigned char *)VV5_MASK_TABLE);
    return 1;
}

/* Choose Time Skip Amount (the Story DLL drives it): one step of the Time
   Warp above, at most the years one Time Warp buys at the current speed.
   The villager tick (whose catch-up replays the new age units) rewrites
   every living believer's marker (+0x1C38) each time it runs, so a marker
   that moved off the value the step left is the sign it has replayed the
   step.  A Heathen is never the one watched (the tick skips them). */
static int vv5_skip_watch = -1;
static int vv5_skip_mark;

static int vv5_skip_living(const unsigned char *rec) {
    return rec[VV5_OFF_ACTIVE] != 0 && rec[VV5_TW_FACTION_OFFSET] == 0
        && *(const int *)(rec + 0x1C40) > 0;
}

static int __stdcall vv5_story_time_skip_step(int years) {
    vv5_world_getter_fn get_world = (vv5_world_getter_fn)(UINT_PTR)VV5_TW_WORLD_GETTER;
    unsigned char *world = get_world();
    unsigned char *base = (unsigned char *)(UINT_PTR)VV5_REC_BASE;
    int speed, step, i, slots;
    if (world == 0 || years <= 0) {
        return 0;
    }
    speed = *(int *)(world + VV5_TW_SPEED_OFFSET);
    step = vv5_time_warp_years(speed);
    if (step <= 0) {
        return -1;                     /* paused, or a speed we do not know */
    }
    if (step > years) {
        step = years;
    }
    if (vv5_time_warp_apply(speed, step) <= 0) {
        return 0;
    }
    vv5_skip_watch = -1;
    slots = vv5_slots();
    for (i = 0; i < slots; ++i) {
        unsigned char *rec = base + (size_t)i * VV5_REC_STRIDE;
        if (vv5_skip_living(rec)) {
            vv5_skip_watch = i;
            vv5_skip_mark = *(int *)(rec + VV5_TW_LAST_SEEN_OFFSET);
            break;
        }
    }
    return step;
}

static int __stdcall vv5_story_time_skip_settled(void) {
    unsigned char *rec;
    if (vv5_skip_watch < 0 || vv5_skip_watch >= vv5_slots()) {
        return 1;
    }
    rec = (unsigned char *)(UINT_PTR)VV5_REC_BASE + (size_t)vv5_skip_watch * VV5_REC_STRIDE;
    return !vv5_skip_living(rec) || *(int *)(rec + VV5_TW_LAST_SEEN_OFFSET) != vv5_skip_mark;
}

/* Whether the game's clock runs (a known speed, not paused): only that time
   counts toward the time skip's replay wait (native/shared/story_bridge.h). */
static int __stdcall vv5_story_time_skip_running(void) {
    vv5_world_getter_fn get_world = (vv5_world_getter_fn)(UINT_PTR)VV5_TW_WORLD_GETTER;
    unsigned char *world = get_world();
    return world != 0 && vv5_time_warp_years(*(int *)(world + VV5_TW_SPEED_OFFSET)) > 0;
}

static const vvfp_story_host *vvfp_story_host_table(void) {
    static const vvfp_story_host host = {
        sizeof(vvfp_story_host), vv5_story_slot, vv5_story_mask_get, vv5_story_mask_set, NULL,
        vv5_story_time_skip_step, vv5_story_time_skip_settled, vv5_story_time_skip_running
    };
    return &host;
}

__declspec(dllexport) int __stdcall ShowVv5TimeWarp(int cost) {
    static const char *const TITLE = "Origins Upgrades";
    char message[448];
    /* GetOriginsOwner, not GetForegroundWindow: this file deliberately has
       no owner fallback -- the owner is captured once by BeginOriginsOwner
       and validated as belonging to this process. */
    HWND owner = GetOriginsOwner();
    vv5_world_getter_fn get_world = (vv5_world_getter_fn)(UINT_PTR)VV5_TW_WORLD_GETTER;
    unsigned char *world = get_world();
    char cost_text[16];
    int speed, years;

    if (world == 0) {
        MessageBoxA(owner,
                    "Time Warp could not reach the village. No tech points "
                    "have been deducted.",
                    TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return VV5_TW_REFUSED;
    }
    speed = *(int *)(world + VV5_TW_SPEED_OFFSET);
    years = vv5_time_warp_years(speed);
    if (years <= 0) {
        /* Paused advances nothing at all, so it must refuse BEFORE the caller
           charges rather than bill for a no-op. */
        MessageBoxA(owner,
                    speed >= VV5_TW_SPEED_PAUSED
                        ? "Time Warp is unavailable while the game is paused."
                        : "Time Warp could not read the game speed. No tech "
                          "points have been deducted.",
                    TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return VV5_TW_REFUSED;
    }
    vv5_format_cost(cost, cost_text);
    wsprintfA(message,
              "Do you want to buy Time Warp for %s tech points?\r\n"
              "On %s game speed, this will advance %d villager years.\r\n"
              "Press OK to confirm, or Cancel.",
              cost_text, vv5_speed_name(speed), years);
    if (MessageBoxA(owner, message, TITLE,
                    MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND)
        != IDOK) {
        return VV5_TW_CANCELLED;
    }
    if (vv5_village_occupied() <= 0) {
        MessageBoxA(owner,
                    "Time Warp could not reach the village records. No tech "
                    "points have been deducted.",
                    TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return VV5_TW_REFUSED;
    }
    /* Charge HERE: after the player confirms, before anything is mutated.
       The executable used to pay after this function returned, by which point
       the clock had moved, every villager had been credited and the success
       box had been shown -- so a charge that did not land granted a free warp
       that had already been reported, and could not be undone. Both the funds
       check and the deduction read-back therefore have to sit between the
       confirmation and the first write, which is only possible in here: the
       confirmation is a blocking MessageBoxA, so any balance the caller reads
       beforehand is stale by the time the player answers. */
    {
        vv5_charge_fn charge = (vv5_charge_fn)(UINT_PTR)VV5_CHARGE_FN;
        int *balance = (int *)(UINT_PTR)VV5_TECH;
        int before = *balance;

        if (before < cost) {
            MessageBoxA(owner,
                        "Time Warp needs more tech points than the village "
                        "has. Nothing has been changed or deducted.",
                        TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
            return VV5_TW_REFUSED;
        }
        charge(balance, 0, -cost);
        if (*balance != before - cost) {
            /* True as written, now that it runs before the mutation. */
            MessageBoxA(owner,
                        "Time Warp could not deduct its tech points. The "
                        "village clock has not been changed.",
                        TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
            return VV5_TW_REFUSED;
        }
    }
    vv5_time_warp_apply(speed, years);
    wsprintfA(message, "Advanced %d years.", years);
    MessageBoxA(owner, message, TITLE,
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return VV5_TW_APPLIED;
}

__declspec(dllexport) int __stdcall ShowVV5AppearanceForAll(void) {
    INT_PTR ok;
    HWND owner;
    caf_rng = GetTickCount() | 1u;
    owner = GetOriginsOwner();
    ok = DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_APPEARANCE_ALL),
                         owner, caf_dialog, 0);
    if (ok != 1) return 0;
    if (*(int *)VV5_TECH < vvfp_story_price(5, 450000)) {
        MessageBoxA(owner, "Not enough tech points. This upgrade costs 450,000.",
                    "Change Appearance for All", MB_OK | MB_ICONWARNING);
        return 0;
    }
    /* one-time genetics warning if any head field will change */
    if (caf_heads_mode != 0 || caf_head[0] >= 0 || caf_head[1] >= 0) {
        if (MessageBoxA(owner,
                "Warning: This will change the head genetics of every villager of the selected sex, affecting their descendants.\r\n\r\nProceed?",
                "Change Appearance for All", MB_OKCANCEL | MB_ICONWARNING) != IDOK)
            return 0;
    }
    {
        int touched = caf_apply();
        if (touched <= 0) {
            MessageBoxA(owner,
                "Nothing was changed -- either no appearance options were "
                "selected, or every villager already had the ones chosen. "
                "No tech points have been deducted.",
                        "Change Appearance for All", MB_OK | MB_ICONINFORMATION);
            return 0;
        }
        if (vvfp_story_price(5, 450000) != 0) {
            caf_charge(-450000);
        }
        WriteMaskSidecar((const unsigned char *)VV5_MASK_TABLE);
        MessageBoxA(owner, "Change Appearance for All applied to every villager.",
                    "Change Appearance for All", MB_OK | MB_ICONINFORMATION);
        return 1;
    }
}

static HWND validate_same_process_window(HWND window) {
    DWORD process_id = 0;
    if (window == NULL || !IsWindow(window)) {
        return NULL;
    }
    if (GetWindowThreadProcessId(window, &process_id) == 0
        || process_id != GetCurrentProcessId()) {
        return NULL;
    }
    return window;
}

__declspec(dllexport) int __stdcall BeginOriginsOwner(void) {
    HWND candidate = validate_same_process_window(GetForegroundWindow());
    origins_owner = candidate;
    return candidate != NULL;
}

__declspec(dllexport) HWND __stdcall GetOriginsOwner(void) {
    HWND owner = validate_same_process_window(origins_owner);
    if (owner == NULL) {
        origins_owner = NULL;
    }
    return owner;
}

__declspec(dllexport) void __stdcall EndOriginsOwner(void) {
    origins_owner = NULL;
}

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int limited_capability = (lparam & STATE_LIMITED_CAPABILITY) != 0;
        int first_unsupported_row = villager_menu ? 4 : 6;
        int row_count = villager_menu ? 5 : 14;
        int row;
        int blocked;
        for (row = 0; row < ROW_STATE_MAX; ++row) {
            block_reasons[row] = BLOCK_NONE;
        }
        for (row = 0; row < row_count; ++row) {
            /* Unlike the other games, VV5 hides the badge inside this loop
               rather than in a separate pass beforehand, so the hide has to
               happen before any `continue` -- the dialog resource creates the
               badges VISIBLE, and skipping it would leave a stale green
               checkmark on the row. */
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
            /* A row this BUILD cannot run is refused before any reason is
               computed, and BOTH forms of that have to be tested here.
               STATE_LIMITED_CAPABILITY covers rows at or above
               first_unsupported_row; the per-row bit 1 << (8 + row) covers the
               rest, and the expanded layout sets exactly those -- menu_state
               0x700 is bits 8, 9 and 10, which are rows 0, 1 and 2, and row 2
               is the Barrel.
               Asking row_block_reason first let its capacity check win on a
               row the build does not bind at all, turning an unsupported row
               into a clickable "Why not?" promising that freeing three
               villager slots would allow the purchase -- and after the player
               freed them the row went back to "Unavailable" and still did
               nothing. A false remedy is worse than a bare refusal, which is
               the opposite of what these reasons exist for. Codex found this
               on #254; the capability half alone does not cover row 2. */
            if ((limited_capability && row >= first_unsupported_row)
                || (lparam & (1L << (8 + row))) != 0) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                continue;
            }
            blocked = row_block_reason(villager_menu, row, (long)lparam);
            if (blocked != BLOCK_NONE) {
                /* Enabled on purpose: the WM_COMMAND handler intercepts the
                   click, explains, and neither closes the dialog nor charges. */
                block_reasons[row] = blocked;
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Why not?");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                continue;
            }
            if ((lparam & (1 << row)) != 0) {
                /* Only the two Doublers may ever show a green check, and only
                   while they are owned in the current save. Every other row --
                   including the Details menu's already-satisfied rows, whose
                   state bits 0-3 the callers deliberately set -- keeps its
                   badge hidden and conveys state through the button instead. */
                if (!villager_menu && (row == 3 || row == 4)) {
                    ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                }
                if (villager_menu) {
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                } else if (row == 3 || row == 4) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                } else {
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                }
            }
            /* No trailing `1 << (8 + row)` branch here any more: that bit is
               tested at the top of the loop, before any reason is computed,
               and `continue`s. Leaving a second copy would be unreachable
               code documenting a path that cannot run. */
        }
        /* Story / Cheat Upgrades: every price reads 0, and the Tech menu
           gains Pick Island Event. */
        vvfp_story_relabel(5, window);
        if (!villager_menu) {
            vvfp_story_add_pick_button(5, window);
        }
        return TRUE;
    }
    if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == VVFP_STORY_PICK_ID || command == VVFP_STORY_CUSTOM_ID
            || command == VVFP_STORY_TIME_SKIP_ID) {
            /* Pick Island Event and Custom Island Event share the Island
               Event row's lock (Choose Time Skip Amount ignores it). */
            if (vvfp_story_pick_clicked(
                    5, window, (int)command,
                    block_reasons[PENDING_ROW_ISLAND] != BLOCK_NONE
                        ? block_reason_text(block_reasons[PENDING_ROW_ISLAND], PENDING_ROW_ISLAND)
                        : NULL)) {
                EndDialog(window, -1);
            }
            return TRUE;
        }
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            int clicked = (int)(command - ID_BUY_FIRST);
            if (clicked >= 0 && clicked < ROW_STATE_MAX
                && block_reasons[clicked] != BLOCK_NONE) {
                /* Explain and stay open. Returning the row here would run the
                   purchase path and charge for it. */
                MessageBoxA(window,
                            block_reason_text(block_reasons[clicked], clicked),
                            "Not right now",
                            MB_OK | MB_ICONINFORMATION);
                return TRUE;
            }
            EndDialog(window, (INT_PTR)clicked);
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    }
    if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    HWND owner = GetOriginsOwner();
    vvfp_story_bridge(5);   /* before any price is shown or charged */
    vvfp_cause_bridge(5);  /* cause of death companion: once, fail-open */
    if (owner == NULL) {
        return -1;
    }
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(villager_menu ? IDD_ORIGINS_VILLAGER : IDD_ORIGINS_TECH),
        owner,
        upgrade_dialog,
        dialog_state
    );
}

static const char *action_name(unsigned int action) {
    switch (action) {
    case ACTION_YOUTH: return "Grant Youth";
    case ACTION_MASTERY: return "Grant Full Mastery";
    case ACTION_RUNNING: return "Grant Running";
    case ACTION_AGE18: return "Set Age to 18";
    case ACTION_HEAL: return "Full Heal / Cure All";
    case ACTION_APPEARANCE: return "Change Appearance";
    case ACTION_COMPLETE_COLLECTIONS: return "Complete All Collections";
    case ACTION_RESET_COLLECTIONS: return "Reset All Collections";
    case ACTION_TECH_DOUBLER: return "Tech Point Doubler";
    case ACTION_FOOD_DOUBLER: return "Food Point Doubler";
    case ACTION_GRANT_RUNNING_ALL: return "Grant Running to All Villagers";
    case ACTION_GRANT_MASTERY_ALL: return "Grant Full Mastery to All Villagers";
    case ACTION_SET_AGE_18_ALL: return "All Villagers are Exactly 18";
    case ACTION_EQUAL_DIVISION_PARENTING: return "Equal Division of Labor (Includes Parenting)";
    case ACTION_EQUAL_DIVISION_NO_PARENTING: return "Equal Division of Labor (No Parenting)";
    case ACTION_CHANGE_APPEARANCE_ALL: return "Change Appearance for All";
    default: return "Origins upgrade";
    }
}

static const char *action_cost(unsigned int action) {
    if (vvfp_story_free(5)) {
        return "0";             /* Story / Cheat Upgrades */
    }
    switch (action) {
    case ACTION_YOUTH: return "50,000";
    case ACTION_MASTERY: return "100,000";
    case ACTION_RUNNING: return "40,000";
    case ACTION_AGE18: return "50,000";
    case ACTION_HEAL: return "30,000";
    case ACTION_APPEARANCE: return "5,000";
    case ACTION_TECH_DOUBLER:
    case ACTION_FOOD_DOUBLER: return "500,000";
    case ACTION_CHANGE_APPEARANCE_ALL: return "450,000";
    default: return "1,000,000";
    }
}

/* Correct singular/plural for a villager count. */
static const char *vpl(unsigned int n) { return n == 1 ? "Villager" : "Villagers"; }
static const char *vpl_lc(unsigned int n) { return n == 1 ? "villager" : "villagers"; }

/* Capitalised forms for the Equal Division results. The possessive moves the
   apostrophe rather than just adding an "s", so it needs its own helper. */
static const char *vpl_uc(unsigned int n) { return n == 1 ? "Villager" : "Villagers"; }
static const char *vpl_pos(unsigned int n) { return n == 1 ? "Villager's" : "Villagers'"; }


/* ---- Equal Division of Labor (VV5) -------------------------------------------
   Split every eligible Believer's job-preference checkmark round-robin so the
   population is spread evenly across the professions. Record fields (base +
   i*STRIDE): active +0x1CD4, Heathen mask +0x1CE1 (== 0), faction +0x1CEC
   (== 0), signed health +0x1C40 (> 0), sex dword +0x1B90 (0 male / 1 female),
   preferred-skill index +0x1C74 (0 Farming, 1 Parenting, 2 Healing, 3 Research,
   4 Building, 5 Devotion). A separate seat counter per sex keeps each
   profession's male/female split balanced as well as the total count.
   Assignment order is Farming, Building, Research, Healing, [Parenting,]
   Devotion -- `parenting` picks 6 professions, otherwise 5 (Parenting dropped).
   Preferences are overwritten unconditionally, so the count is simply the
   number eligible. Believer-only: masked Heathens and off-faction villagers are
   never touched, and VV5 has no Golden Child so nothing else is skipped.
   Eligibility is otherwise EVERYONE alive -- children of any age, nursing
   mothers, and adults. The per-profession, per-sex breakdown does not fit
   ShowVV5Task9Result's two counts, so this composes and shows its own result. */
#define VV5_ED_STRIDE     0x2F44
#define VV5_ED_COUNT      vv5_slots()   /* 150, or 256 with 256 Villagers */
#define VV5_ED_ACTIVE     0x1CD4
#define VV5_ED_MASK       0x1CE1
#define VV5_ED_FACTION    0x1CEC
#define VV5_ED_HEALTH     0x1C40
#define VV5_ED_SEX        0x1B90
#define VV5_ED_PREFERENCE 0x1C74

__declspec(dllexport) int __stdcall ApplyVV5EqualDivision(
    unsigned char *base,
    int parenting
) {
    /* Seat order names plus the skill index written to +0x1C74 for each seat. */
    static const char *const name_parenting[6] = {
        "Farming", "Building", "Research", "Healing", "Breeding", "Devotion"
    };
    static const int index_parenting[6] = { 0, 4, 3, 2, 1, 5 };
    static const char *const name_no_parenting[5] = {
        "Farming", "Building", "Research", "Healing", "Devotion"
    };
    static const int index_no_parenting[5] = { 0, 4, 3, 2, 5 };
    const char *const *pro_name = parenting ? name_parenting : name_no_parenting;
    const int *pro_index = parenting ? index_parenting : index_no_parenting;
    int professions = parenting ? 6 : 5;
    int male_seat = 0, female_seat = 0;
    int male_count[6] = { 0, 0, 0, 0, 0, 0 };
    int female_count[6] = { 0, 0, 0, 0, 0, 0 };
    int total = 0;
    /* Counted separately from `total`: the caller charges 1,000,000 only when
       this reports a REAL change, so re-buying the same variant with an
       unchanged roster must report none. `total` still drives the per-seat
       summary, which describes the resulting division either way. */
    int changed = 0;
    int i, p;
    char message[512];
    char line[128];
    unsigned char *record = base;
    HWND owner = GetOriginsOwner();
    if (base == 0) {
        return 0;
    }
    for (i = 0; i < VV5_ED_COUNT; ++i, record += VV5_ED_STRIDE) {
        int seat;
        if (record[VV5_ED_ACTIVE] == 0) {
            continue;
        }
        if (record[VV5_ED_MASK] != 0) {       /* masked Heathen -- never touch */
            continue;
        }
        if (record[VV5_ED_FACTION] != 0) {    /* off-faction -- never touch */
            continue;
        }
        if (*(int *)(record + VV5_ED_HEALTH) <= 0) {
            continue;
        }
        if (*(int *)(record + VV5_ED_SEX) == 0) {   /* male */
            seat = male_seat % professions;
            ++male_seat;
            ++male_count[seat];
        } else {                                     /* female */
            seat = female_seat % professions;
            ++female_seat;
            ++female_count[seat];
        }
        if (*(int *)(record + VV5_ED_PREFERENCE) != pro_index[seat]) {
            *(int *)(record + VV5_ED_PREFERENCE) = pro_index[seat];
            ++changed;
        }
        ++total;
    }
    if (total == 0) {
        MessageBoxA(
            owner,
            "No villagers were eligible. No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
        return 0;
    }
    if (changed == 0) {
        MessageBoxA(
            owner,
            "Every villager already has this division of labor. "
            "No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK | MB_ICONINFORMATION
        );
        return 0;
    }
    wsprintfA(message, "Set %u %s Job Preferences.", (unsigned int)total,
              vpl_pos((unsigned int)total));
    for (p = 0; p < professions; ++p) {
        wsprintfA(line, "\r\n\r\n%s: %u %s (%u Male, %u Female).",
                  pro_name[p],
                  (unsigned int)(male_count[p] + female_count[p]),
                  vpl_uc((unsigned int)(male_count[p] + female_count[p])),
                  (unsigned int)male_count[p], (unsigned int)female_count[p]);
        lstrcatA(message, line);
    }
    MessageBoxA(
        owner, message, "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION
    );
    return 1;
}



__declspec(dllexport) int __stdcall ConfirmVV5Task9Action(
    unsigned int action,
    unsigned int amount_a,
    unsigned int amount_b
) {
    HWND owner = GetOriginsOwner();
    char message[512];
    const char *title = (action == ACTION_HEAL || action >= ACTION_TECH_BASE)
        ? "Origins Upgrades"
        : "Villager Upgrades";
    (void)amount_a;
    (void)amount_b;
    if (owner == NULL) {
        return 0;
    }
    /* One OK/Cancel purchase box naming the upgrade and its cost. */
    wsprintfA(
        message,
        "Do you want to buy %s for %s tech points?\r\nPress OK to confirm, or Cancel.",
        action_name(action),
        action_cost(action)
    );
    return MessageBoxA(owner, message, title, MB_OKCANCEL | MB_ICONQUESTION) == IDOK;
}

__declspec(dllexport) int __stdcall ShowVV5Task9GeneticsWarning(void) {
    HWND owner = GetOriginsOwner();
    if (owner == NULL) {
        return 0;
    }
    return MessageBoxA(
        owner,
        "Warning: This will change the villager's head genetics.",
        "Villager Upgrades",
        MB_OKCANCEL | MB_ICONWARNING
    ) == IDOK;
}

__declspec(dllexport) int __stdcall ShowVV5Task9Result(
    unsigned int action,
    unsigned int status,
    unsigned int amount_a,
    unsigned int amount_b
) {
    HWND owner = GetOriginsOwner();
    char message[512];
    const char *name = action_name(action);
    if (owner == NULL) {
        return 0;
    }
    switch (status) {
    case RESULT_SUCCESS:
        if (action == ACTION_HEAL) {
            wsprintfA(message, "Cured sickness from %u %s.\r\n\r\nRestored %u %s to full health.",
                      amount_a, vpl_lc(amount_a), amount_b, vpl_lc(amount_b));
        } else if (action == ACTION_COMPLETE_COLLECTIONS) {
            /* amount_b is a runtime count of the trophies this click actually
               earned (relics, science, Master Collector), so it can legitimately
               be 1 -- pluralise it the way VV2 does rather than always printing
               "goals". VV2 conditions on its own amount_a; here the varying
               count is amount_b. */
            wsprintfA(message, "Marked all %u collectibles as found and triggered %u collection goal%s.",
                      amount_a, amount_b, amount_b == 1 ? "" : "s");
        } else if (action == ACTION_RESET_COLLECTIONS) {
            wsprintfA(message, "Cleared all %u collectibles.", amount_a);
        } else if (action == ACTION_GRANT_RUNNING_ALL) {
            unsigned int granted = amount_b >> 16, removed = amount_b & 0xFFFF;
            unsigned int liked = amount_a >> 16, full = amount_a & 0xFFFF;
            wsprintfA(
                message,
                "Granted Running to %u %s.\r\n\r\n"
                "Removed a Running dislike from %u %s.\r\n\r\n"
                "Skipped %u %s: already like Running.\r\n\r\n"
                "Skipped %u %s: already have 3 likes.",
                granted, vpl(granted), removed, vpl(removed),
                liked, vpl(liked), full, vpl(full)
            );
        } else if (action == ACTION_GRANT_MASTERY_ALL) {
            wsprintfA(
                message,
                "Granted Full Mastery to %u %s.\r\n\r\n"
                "Skipped %u %s: already fully mastered.",
                amount_a, vpl(amount_a), amount_b, vpl(amount_b)
            );
        } else if (action == ACTION_SET_AGE_18_ALL) {
            wsprintfA(
                message,
                "Set %u %s to Age 18.\r\n\r\n"
                "Skipped %u %s: already exactly 18.",
                amount_a, vpl(amount_a), amount_b, vpl(amount_b)
            );
        } else {
            wsprintfA(message, "%s completed.", name);
        }
        break;
    case RESULT_NO_CHANGE:
        if (action == ACTION_YOUTH) {
            lstrcpyA(message, "This villager is already full of youth. No tech points have been deducted.");
        } else if (action == ACTION_MASTERY) {
            lstrcpyA(message, "This villager is already fully mastered. No tech points have been deducted.");
        } else if (action == ACTION_RUNNING) {
            lstrcpyA(message, "This villager already likes Running. No tech points have been deducted.");
        } else if (action == ACTION_AGE18) {
            lstrcpyA(message, "No changes were needed. No tech points have been deducted.");
        } else if (action == ACTION_HEAL) {
            lstrcpyA(message, "Everyone is at full health already. No villagers are sick. No tech points have been deducted.");
        } else if (action == ACTION_GRANT_RUNNING_ALL) {
            lstrcpyA(message, "Everyone already likes running, or has full Likes slots. No tech points have been deducted.");
        } else if (action == ACTION_GRANT_MASTERY_ALL) {
            lstrcpyA(message, "Everyone has already mastered their skills. No tech points have been deducted.");
        } else if (action == ACTION_SET_AGE_18_ALL) {
            lstrcpyA(message, "Everyone is already exactly 18. No tech points have been deducted.");
        } else if (action == ACTION_COMPLETE_COLLECTIONS) {
            lstrcpyA(message, "All collectibles are already found. No tech points have been deducted.");
        } else if (action == ACTION_RESET_COLLECTIONS) {
            lstrcpyA(message, "The collections are already cleared. No tech points have been deducted.");
        } else {
            lstrcpyA(message, "No changes were needed. No tech points have been deducted.");
        }
        break;
    case RESULT_INVALID:
        lstrcpyA(message, "No valid living Believer is selected.\r\nNo tech points have been deducted.");
        break;
    case RESULT_INSUFFICIENT:
        lstrcpyA(message, "Not enough tech points.");
        break;
    case RESULT_CANCELLED:
        wsprintfA(message, "%s was canceled.\r\nNo tech points have been deducted.", name);
        break;
    case RESULT_RECHECK:
        lstrcpyA(message, "The selected Villager, village snapshot, or tech-point balance changed during confirmation.\r\nNo tech points have been deducted.");
        break;
    case RESULT_RETAINED:
        lstrcpyA(message, "The action could not be fully verified after native writes began. Earlier verified effects may remain.\r\nNo tech points have been deducted.");
        break;
    case RESULT_CHARGE_UNKNOWN:
        lstrcpyA(message, "The action effects were verified, but the final tech-point balance did not match the exact expected deduction. The charge outcome is unknown.");
        break;
    case RESULT_NO_SLOT:
        lstrcpyA(message, "This villager already has full Likes slots. Running can not be added.");
        break;
    case RESULT_INVALID_SKILL:
        lstrcpyA(message, "Full Mastery cannot be applied because a skill is NaN, infinite, negative, or outside 0..100.\r\nNo tech points have been deducted.");
        break;
    case RESULT_UNAVAILABLE:
        lstrcpyA(message, "This VV5 native action remains unavailable.\r\nNo tech points have been deducted.");
        break;
    case RESULT_REMOVED:
        wsprintfA(message, "%s was removed. No refund was issued.", name);
        break;
    case RESULT_PURCHASED:
        wsprintfA(message, "%s completed.", name);
        break;
    case RESULT_UNSUPPORTED_SICKNESS:
        lstrcpyA(message, "Full Heal / Cure All is unavailable because an eligible Villager has sickness type 12, whose additional native effects are not yet implemented.\r\nNo tech points have been deducted.");
        break;
    case RESULT_RUNNING_DISLIKE_CLEARED:
        lstrcpyA(message, "This villager's Likes are full, so Running could not be added, but its Running dislike was removed. No tech points have been deducted.");
        break;
    case RESULT_APPEARANCE_UNCHANGED:
        lstrcpyA(message, "The appearance is unchanged. No tech points have been deducted.");
        break;
    default:
        lstrcpyA(message, "The action stopped without a verified charge.");
        break;
    }
    MessageBoxA(
        owner,
        message,
        action == ACTION_HEAL || action >= ACTION_TECH_BASE
            ? "Origins Upgrades"
            : "Villager Upgrades",
        MB_OK | (status == RESULT_SUCCESS || status == RESULT_PURCHASED || status == RESULT_REMOVED
            ? MB_ICONINFORMATION : MB_ICONWARNING)
    );
    return 0;
}
