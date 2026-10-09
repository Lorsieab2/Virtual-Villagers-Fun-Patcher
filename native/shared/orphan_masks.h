/* Orphan mask entries (v1.35.59, all five games): the first-load
   cross-check's part for the Village Masks file (crosscheck_bridge.h).

   WHAT AN ORPHAN IS.  Every Origins companion keeps the masks the player
   chose in a table of its own, saved to "Virtual Villagers Fun Patcher
   Data\Village Masks\..." with the IDENTITY of the villager each entry is
   for (a hash of the name with the fields a life never changes; each game's
   own rule, kept by the companion).  An entry is an orphan when

     - no villager in the village carries the identity stored with it --
       living, or (The Secret City to New Believers) a body still in its
       record, which is a villager the save still holds -- and
     - it is shown on nobody: in A New Home, The Lost Children, The Tree of
       Life and New Believers the table is kept by record, and an entry on a
       record somebody holds is that villager's (the follow put it there, or
       the game's own death clear would have taken it), so only an entry on a
       record NOBODY holds is looked at.  The Secret City finds each mask by
       its identity wherever the villager is, so there every entry is.

   An entry stored with NO identity (0) on a record nobody holds is an
   orphan too: a roster-keyed file (A New Home, The Lost Children, New
   Believers) stores 0 for a record nobody held when it was written, and the
   follow never places an entry without an identity on anyone -- it stays
   while its record is empty and is dropped as soon as anyone takes it.

   An identity that ANY villager carries -- one, or several who cannot be
   told apart -- is never an orphan: that is the "ambiguous: keep" rule.  A
   name-only identity from an older file (The Lost Children 'VM04', New
   Believers 'VM05'/'VM25') is matched by the villagers' names at the load
   (vv_om_from_names).  So that an ambiguous entry stays one, the roster a
   roster-keyed file is written with keeps its identity on its empty record
   (vv_om_roster_to_write).

   WHAT REPAIR DOES (vv_om_commit), on the game's own thread, at once (the
   mask file is the companion's own, written whenever the table changes, not
   at a save):
     1. the village's header is read from its save ("VVFP Save Reset.dll",
        SavedVillageHeader) -- without it nothing is changed;
     2. the mask file is copied to "<file>.before-v1.35.59-repair" ("-2",
        "-3", ... when that exists; never replacing anything);
     3. the entries -- only those both listed in the prompt and still
        orphans now -- are removed from the table and the companion writes
        its file (atomically, native/shared/sidecar_io.h);
     4. each removal is listed in the Repairs log (repairs_log.h).
   A failure at 3 or 4 puts the entries back (and the file, after a failed
   note) and changes nothing: the next load asks again.  This repair's
   backup is deleted only when the file on disk is the one it copied -- if
   the file could not be written back, the backup keeps the entries.  "Not now" changes nothing.  Once removed, a scan finds
   nothing more, so no marker is needed: the next load does not ask.

   Header-only and file-static; included once per Origins companion, after
   crosscheck_bridge.h (whose VVFP_XC_LOAD finds "VVFP Save Reset.dll").
   native/shared/orphan_masks_harness.c drives every function here against
   real files. */
#ifndef VVFP_ORPHAN_MASKS_H
#define VVFP_ORPHAN_MASKS_H

#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "repairs_log.h"

#ifndef VVFP_CROSSCHECK_BRIDGE_H
#error "include crosscheck_bridge.h before orphan_masks.h"
#endif

#define VV_OM_MAX 256
#define VV_OM_BACKUP_SUFFIX L".before-v1.35.59-repair"
#define VV_OM_CHECKED "the Village Masks file, against the villagers in the village"

typedef struct {
    int count;
    int index[VV_OM_MAX];             /* the table entry (the record, where the table is kept by record) */
    unsigned char value[VV_OM_MAX];   /* the mask, 1..5 */
    unsigned int id[VV_OM_MAX];       /* the identity stored with it; 0 = none */
} vv_om_list;

/* Is `id` the identity of any of ids[0..n) (0 = an empty record)? */
static int vv_om_carried(const unsigned int *ids, int n, unsigned int id) {
    int i;
    for (i = 0; i < n; ++i) {
        if (ids[i] != 0 && ids[i] == id) {
            return 1;
        }
    }
    return 0;
}

/* The rule, for one entry: a mask (`value` != 0) on a record nobody holds
   (`held` 0; always 0 where the table is not kept by record) whose stored
   identity `id` no villager in ids[0..n) carries -- which none (0) never is. */
static int vv_om_orphan(unsigned char value, int held, unsigned int id, const unsigned int *ids, int n) {
    return value != 0 && !held && !vv_om_carried(ids, n, id);
}

static void vv_om_add(vv_om_list *list, int index, unsigned char value, unsigned int id) {
    if (list->count < VV_OM_MAX) {
        list->index[list->count] = index;
        list->value[list->count] = value;
        list->id[list->count] = id;
        ++list->count;
    }
}

/* What a follow did, for the identity each entry was STORED with: a
   companion that keeps its table by record but its identities by roster
   (The Lost Children, New Believers, A New Home) loses the identity of an
   entry on a record that empties -- the roster says 0 there -- so the one
   it was stored with is kept here, beside the table.  moved[] / moved_id[]
   are vv_mask_follow's outputs.  An entry the follow kept on its own record
   with no identity keeps the one noted for it before. */
static void vv_om_track(int n, const unsigned char *moved, const unsigned int *moved_id, unsigned int *id) {
    int i;
    for (i = 0; i < n; ++i) {
        if (moved[i] == 0) {
            id[i] = 0;
        } else if (moved_id[i] != 0) {
            id[i] = moved_id[i];
        }
    }
}

/* After a load from an older name-only file (The Lost Children 'VM04', New
   Believers 'VM05' / 'VM25'), whose identities are name hashes: each becomes
   the full identity of a villager who carries that name (names[] / ids[]:
   the name hash and the identity of each record, 0 = empty) -- the one the
   follow put it on, or, for one it could not place, a namesake, so it stays
   a mask some villager carries and is kept -- or 0 when nobody has the
   name. */
static void vv_om_from_names(int n, unsigned int *id, const unsigned int *names, const unsigned int *ids) {
    int i, j;
    for (i = 0; i < n; ++i) {
        unsigned int full = 0;
        for (j = 0; j < n && id[i] != 0; ++j) {
            if (names[j] != 0 && names[j] == id[i] && (j == i || full == 0)) {
                full = ids[j];
            }
        }
        id[i] = full;
    }
}

/* The roster a roster-keyed mask file is written with: who holds each
   record now (`live`, 0 = nobody) -- and, on a record nobody holds whose
   mask is stored for an identity some villager still CARRIES (several alike,
   so the follow could not tell whose it was), that identity.  Written as 0
   it would read as "nobody's" at the next load and be taken for an orphan:
   the ambiguous entry is kept, load after load, as the rule says.  Only that
   case: an identity no villager carries is written as 0 as before (written,
   a namesake born later would be handed the mask), and the record's roster
   entry only ever says what the load that kept the mask was given.  `value`
   and `id` are per record. */
static void vv_om_roster_to_write(int n, const unsigned int *live, const unsigned char *value,
                                  const unsigned int *id, unsigned int *out) {
    int i;
    for (i = 0; i < n; ++i) {
        out[i] = live[i];
    }
    for (i = 0; i < n; ++i) {
        if (live[i] == 0 && value[i] != 0 && id[i] != 0 && vv_om_carried(live, n, id[i])) {
            out[i] = id[i];
        }
    }
}

/* The entries of `asked` (listed in the prompt) that `now` (the same scan,
   repeated at the answer) still finds: only these are removed. */
static void vv_om_still(const vv_om_list *asked, const vv_om_list *now, vv_om_list *out) {
    int i, k;
    out->count = 0;
    for (i = 0; i < asked->count; ++i) {
        for (k = 0; k < now->count; ++k) {
            if (now->index[k] == asked->index[i] && now->value[k] == asked->value[i] && now->id[k] == asked->id[i]) {
                vv_om_add(out, asked->index[i], asked->value[i], asked->id[i]);
                break;
            }
        }
    }
}

static const char *vv_om_mask_name(unsigned char value) {
    static const char *const names[] = {
        "(None)", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask"
    };
    return value < sizeof names / sizeof names[0] ? names[value] : "Mask";
}

/* The prompt's line (crosscheck_bridge.h composes it): "- N mask entries
   for villagers who are no longer in the village. They will be removed." */
static void vv_om_describe(int count, char *text, size_t cap) {
    if (count == 1) {
        _snprintf_s(text, cap, _TRUNCATE, "- 1 mask entry for a villager who is no longer in the village. "
                                          "It will be removed.\r\n");
    } else {
        _snprintf_s(text, cap, _TRUNCATE, "- %d mask entries for villagers who are no longer in the village. "
                                          "They will be removed.\r\n", count);
    }
}

/* The village's "Village: <name> (Save S)" line, from its save. */
#ifndef VVFP_OM_HEADER
#define VVFP_OM_HEADER(game, slot, out, size) vv_om_saved_header(game, slot, out, size)
static int vv_om_saved_header(int game, int slot, char *out, int size) {
    typedef int (__stdcall *saved_header_fn)(int, int, char *, int);
    saved_header_fn header = (saved_header_fn)VVFP_XC_LOAD("VVFP Save Reset.dll", "SavedVillageHeader");
    return header != NULL && header(game, slot, out, size);
}
#endif

/* The Repairs log note (repairs_log.h); a harness stands in a failing one. */
#ifndef VVFP_OM_NOTE
#define VVFP_OM_NOTE(game, header, checked, body) vv_repairs_note(game, header, checked, body)
#endif

/* Copy `path` to "<path>.before-v1.35.59-repair" ("-2", "-3", ... when that
   is there; never replacing a file).  1: copied, or there is no file (then
   `*none` is 1); 0: no copy could be made. */
static int vv_om_backup(const wchar_t *path, wchar_t *backup, size_t n, int *none) {
    int k;
    *none = 0;
    backup[0] = L'\0';
    if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) {
        DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) {
            *none = 1;
            return 1;
        }
        return 0;
    }
    for (k = 1; k < 1000; ++k) {
        /* In "Data\Copies Made Before Repairs", at the file's own place (save_layout.h). */
        wchar_t suffix[48];
        int w = k == 1 ? _snwprintf_s(suffix, 48, _TRUNCATE, VV_OM_BACKUP_SUFFIX)
                       : _snwprintf_s(suffix, 48, _TRUNCATE, VV_OM_BACKUP_SUFFIX L"-%d", k);
        if (w < 0) {
            break;
        }
        if (!vv_layout_copy_path(path, suffix, backup, n)) {
            w = _snwprintf_s(backup, n, _TRUNCATE, L"%ls%ls", path, suffix);
        }
        if (w < 0) {
            break;
        }
        if (CopyFileW(path, backup, TRUE)) {
            return 1;
        }
        if (GetLastError() != ERROR_FILE_EXISTS && GetLastError() != ERROR_ALREADY_EXISTS) {
            break;
        }
    }
    backup[0] = L'\0';
    return 0;
}

/* The companion's table, as vv_om_commit changes it. */
typedef struct {
    void (*put)(int index, unsigned char value, unsigned int id);   /* one entry (value 0 removes it) */
    int (*publish)(void);                                           /* the table to its file: 1 on disk */
    int by_record;                                                  /* 1: the index is a record */
} vv_om_table;

static void vv_om_put_back(const vv_om_list *entries, const vv_om_table *table) {
    int i;
    for (i = 0; i < entries->count; ++i) {
        table->put(entries->index[i], entries->value[i], entries->id[i]);
    }
}

/* Remove `entries` from the companion's table and from its file `path`
   (steps 1-4 above).  1 when they are gone and listed; 0 when nothing was
   changed. */
static int vv_om_commit(int game, int slot, const char *path, const vv_om_list *entries, const vv_om_table *table) {
    char header[256];
    char leaf[MAX_PATH];
    wchar_t wide[MAX_PATH], backup[MAX_PATH];
    char *body;
    size_t cap, len = 0, n;
    int none, i, ok, restored;
    if (entries->count == 0) {
        return 1;
    }
    if (game < 1 || game > 5 || slot < 1 || slot > 5 || path == NULL
        || !VVFP_OM_HEADER(game, slot, header, (int)sizeof header)) {
        return 0;
    }
    header[sizeof header - 1] = '\0';
    n = strlen(header);
    while (n > 0 && (header[n - 1] == '\r' || header[n - 1] == '\n')) {
        header[--n] = '\0';
    }
    if (strncmp(header, "Village: ", 9) != 0
        || MultiByteToWideChar(CP_ACP, 0, path, -1, wide, MAX_PATH) == 0
        || !vv_om_backup(wide, backup, MAX_PATH, &none)) {
        return 0;
    }
    cap = (size_t)entries->count * 192u + 512u;
    body = (char *)HeapAlloc(GetProcessHeap(), 0, cap);
    if (body == NULL) {
        if (backup[0]) {
            DeleteFileW(backup);
        }
        return 0;
    }
    body[0] = '\0';
    for (i = 0; i < entries->count; ++i) {
        table->put(entries->index[i], 0, 0);
        if (entries->id[i] != 0) {
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE,
                                       "  Mask removed: %s, %s %d -- kept for a villager who is no longer in the "
                                       "village (identity %08X)\r\n",
                                       vv_om_mask_name(entries->value[i]), table->by_record ? "record" : "entry",
                                       entries->index[i] + 1, entries->id[i]);
        } else if (table->by_record) {
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE,
                                       "  Mask removed: %s, record %d -- kept on a record no villager holds, with "
                                       "no villager's identity\r\n",
                                       vv_om_mask_name(entries->value[i]), entries->index[i] + 1);
        } else {
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE,
                                       "  Mask removed: %s, entry %d -- kept with no villager's identity\r\n",
                                       vv_om_mask_name(entries->value[i]), entries->index[i] + 1);
        }
    }
    if (backup[0]) {
        const wchar_t *slash = wcsrchr(backup, L'\\');
        _snprintf_s(leaf, sizeof leaf, _TRUNCATE, "%ls", slash != NULL ? slash + 1 : backup);
        len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE, "  Backup: %s\r\n", leaf);
    } else {
        len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE, "  Backup: none (there was no file)\r\n");
    }
    ok = table->publish();
    restored = !ok;                   /* a failed write left the file as it was */
    if (ok && !VVFP_OM_NOTE(game, header, VV_OM_CHECKED, body)) {
        ok = 0;                       /* no note, no change: the file goes back too */
        vv_om_put_back(entries, table);
        restored = table->publish();
    } else if (!ok) {
        vv_om_put_back(entries, table);
    }
    HeapFree(GetProcessHeap(), 0, body);
    /* The backup goes only when the file on disk is the one it copied: if
       the write back failed, the removed entries are in nothing but it. */
    if (!ok && restored && backup[0]) {
        DeleteFileW(backup);
    }
    return ok;
}

#endif /* VVFP_ORPHAN_MASKS_H */
