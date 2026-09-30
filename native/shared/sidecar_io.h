/* Durable load and publish for the patcher's small per-village sidecar files
 * (the heathen-mask tables in all five games).
 *
 * WHY THIS EXISTS
 * ---------------
 * A sidecar holds state the game itself never saves -- every mask a player
 * chose for a village.  Two defects each destroyed that state outright:
 *
 *   1. VV2 and VV5 wrote the real file in place with CREATE_ALWAYS, which
 *      truncates it before a single byte of the replacement exists, and never
 *      checked a WriteFile.  A crash, a full disk or an I/O error mid-write
 *      left a short file; the loader rejected it and every mask was gone.
 *
 *   2. In every game a file that was PRESENT but not valid (wrong magic, short,
 *      another version) loaded as an empty table and was then overwritten by
 *      the next write.  A file that existed but could not be OPENED (sharing
 *      violation, access denied) was treated exactly like a missing one, so
 *      the next write replaced it too.
 *
 * THE RULES THIS FILE ENFORCES
 * ----------------------------
 *  - A write goes to "<path>.tmp", checks every WriteFile and its byte count,
 *    flushes, closes, and only then replaces the real file with MoveFileEx
 *    (REPLACE_EXISTING | WRITE_THROUGH).  Any failure deletes the temporary
 *    file and leaves the published one byte-for-byte as it was.
 *  - Only a genuinely missing file (ERROR_FILE_NOT_FOUND/ERROR_PATH_NOT_FOUND)
 *    means "no masks yet".
 *  - A file that was read but fails the caller's validation is moved aside to
 *    "<path>.unreadable-<ticks>-<n>", a name that never replaces an existing
 *    file, BEFORE anything may be written.  If it cannot be moved aside it is
 *    treated as blocked.
 *  - A file that exists but cannot be opened or read is BLOCKED: it is neither
 *    read nor written this session until a later retry opens it.  Retries are
 *    throttled to one attempt per VV_SIDECAR_RETRY_MS so a persistent lock
 *    never turns into file I/O on every frame.
 *  - Publishing is refused unless the gate says the load of that exact path
 *    settled (valid, missing, or moved aside).  So nothing a game does while a
 *    file is blocked, or before it has been loaded, can overwrite it.
 *
 * Header-only and static so each companion DLL (and VV2, which textually
 * includes VV1's source) carries its own copy; the include guard keeps the
 * textual inclusion single.  native/shared/sidecar_io_harness.c drives these
 * exact functions against real files.
 */
#ifndef VV_SIDECAR_IO_H
#define VV_SIDECAR_IO_H

#include <windows.h>

/* The harness substitutes a failing writer here to model a crash or a full
   disk partway through a write.  Shipped builds always use WriteFile. */
#ifndef VV_SIDECAR_WRITE_FILE
#define VV_SIDECAR_WRITE_FILE WriteFile
#endif

/* ...and a controllable clock here, to step through the retry window and to
   force two set-asides into the same tick.  Shipped builds use GetTickCount. */
#ifndef VV_SIDECAR_TICKS
#define VV_SIDECAR_TICKS() GetTickCount()
#endif

#define VV_SIDECAR_RETRY_MS 2000u

/* Gate states. */
#define VV_SIDECAR_UNKNOWN 0   /* not loaded for this path yet: never write */
#define VV_SIDECAR_SETTLED 1   /* loaded, missing, or moved aside: may write */
#define VV_SIDECAR_BLOCKED 2   /* present but unusable: never write, retry later */

/* vv_sidecar_load results. */
#define VV_SIDECAR_LOAD_BLOCKED  (-1)  /* leave the table empty; do not write */
#define VV_SIDECAR_LOAD_MISSING    0   /* no file: start empty */
#define VV_SIDECAR_LOAD_VALID      1   /* buffer holds a validated file */
#define VV_SIDECAR_LOAD_SET_ASIDE  2   /* invalid file preserved aside: start empty */

typedef struct {
    int key;               /* caller's namespace (the save slot) */
    int state;             /* VV_SIDECAR_UNKNOWN / SETTLED / BLOCKED */
    DWORD blocked_at;      /* GetTickCount() of the last blocked attempt */
    char path[MAX_PATH];   /* the file the state describes */
} vv_sidecar_gate;

/* Structural validation of the bytes read: 1 = a file this build understands. */
typedef int (*vv_sidecar_validate_fn)(const unsigned char *data, DWORD len,
                                      void *ctx);

/* Rebind the gate to a namespace (a save slot).  A different key forgets every
   earlier result, so a slot is never written on the strength of another
   slot's load. */
static void vv_sidecar_gate_bind(vv_sidecar_gate *g, int key) {
    if (g->key != key) {
        g->key = key;
        g->state = VV_SIDECAR_UNKNOWN;
        g->blocked_at = 0;
        g->path[0] = '\0';
    }
}

/* 1 while a blocked file must not be retried yet.  Callers check this before
   building a path, so a persistent lock costs no file I/O between retries. */
static int vv_sidecar_gate_throttled(const vv_sidecar_gate *g) {
    return g->state == VV_SIDECAR_BLOCKED
        && (DWORD)(VV_SIDECAR_TICKS() - g->blocked_at) < VV_SIDECAR_RETRY_MS;
}

/* Record a failure that happened before the file could even be named (a
   legacy file that would not migrate): the same no-write, retry-later state. */
static void vv_sidecar_gate_block(vv_sidecar_gate *g) {
    g->state = VV_SIDECAR_BLOCKED;
    g->blocked_at = VV_SIDECAR_TICKS();
}

/* 1 when the gate's last load for `key` settled, so a write may proceed. */
static int vv_sidecar_gate_ready(const vv_sidecar_gate *g, int key) {
    return g->key == key && g->state == VV_SIDECAR_SETTLED;
}

static int vv_sidecar_append_uint(char *out, int cap, unsigned int v) {
    char digits[11];
    int n = 0, len = lstrlenA(out);
    do {
        digits[n++] = (char)('0' + v % 10u);
        v /= 10u;
    } while (v != 0u);
    if (len + n + 1 > cap) {
        return 0;
    }
    while (n > 0) {
        out[len++] = digits[--n];
    }
    out[len] = '\0';
    return 1;
}

/* Move a present-but-invalid file to "<path>.unreadable-<ticks>-<n>" without
   ever replacing an existing file.  1 = moved (the original name is now free),
   0 = the file is still where it was. */
static int vv_sidecar_set_aside(const char *path) {
    char aside[MAX_PATH];
    unsigned int ticks = (unsigned int)VV_SIDECAR_TICKS();
    unsigned int n;
    int stem;
    if (lstrlenA(path) + (int)sizeof(".unreadable-") > MAX_PATH) {
        return 0;
    }
    lstrcpyA(aside, path);
    lstrcatA(aside, ".unreadable-");
    if (!vv_sidecar_append_uint(aside, MAX_PATH, ticks)
        || lstrlenA(aside) + 2 > MAX_PATH) {
        return 0;
    }
    lstrcatA(aside, "-");
    stem = lstrlenA(aside);
    for (n = 0; n < 1000u; ++n) {
        DWORD err;
        aside[stem] = '\0';
        if (!vv_sidecar_append_uint(aside, MAX_PATH, n)) {
            return 0;
        }
        /* No MOVEFILE_REPLACE_EXISTING: an occupied name fails and the next
           number is tried, so an earlier set-aside is never overwritten. */
        if (MoveFileExA(path, aside, MOVEFILE_WRITE_THROUGH)) {
            return 1;
        }
        err = GetLastError();
        if (err != ERROR_ALREADY_EXISTS && err != ERROR_FILE_EXISTS) {
            return 0;   /* locked, denied, ... -- the file stays put */
        }
    }
    return 0;
}

/* Read `path` into buf (at most cap bytes; *len receives the count) and
   classify it.  The gate records the outcome for vv_sidecar_publish.

     MISSING   no file at all                      -> settled, start empty
     VALID     read and accepted by `validate`     -> settled, use buf
     SET_ASIDE read, rejected, moved aside         -> settled, start empty
     BLOCKED   cannot open, cannot read, or a rejected file that would not
               move, or still inside the retry window -> never write */
static int vv_sidecar_load(vv_sidecar_gate *g, const char *path,
                           unsigned char *buf, DWORD cap, DWORD *len,
                           vv_sidecar_validate_fn validate, void *ctx) {
    HANDLE h;
    DWORD total = 0;
    *len = 0;
    if (lstrcmpiA(g->path, path) != 0) {
        if (lstrlenA(path) >= MAX_PATH) {
            vv_sidecar_gate_block(g);
            return VV_SIDECAR_LOAD_BLOCKED;
        }
        lstrcpyA(g->path, path);
        g->state = VV_SIDECAR_UNKNOWN;
    }
    if (vv_sidecar_gate_throttled(g)) {
        return VV_SIDECAR_LOAD_BLOCKED;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        if (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) {
            g->state = VV_SIDECAR_SETTLED;
            return VV_SIDECAR_LOAD_MISSING;
        }
        vv_sidecar_gate_block(g);   /* present but unopenable: leave it alone */
        return VV_SIDECAR_LOAD_BLOCKED;
    }
    while (total < cap) {
        DWORD got = 0;
        if (!ReadFile(h, buf + total, cap - total, &got, NULL)) {
            CloseHandle(h);
            vv_sidecar_gate_block(g);   /* an I/O error is not evidence of a bad file */
            return VV_SIDECAR_LOAD_BLOCKED;
        }
        if (got == 0) {
            break;                      /* end of file */
        }
        total += got;
    }
    CloseHandle(h);
    *len = total;
    if (validate(buf, total, ctx)) {
        g->state = VV_SIDECAR_SETTLED;
        return VV_SIDECAR_LOAD_VALID;
    }
    *len = 0;
    if (vv_sidecar_set_aside(path)) {
        g->state = VV_SIDECAR_SETTLED;
        return VV_SIDECAR_LOAD_SET_ASIDE;
    }
    vv_sidecar_gate_block(g);
    return VV_SIDECAR_LOAD_BLOCKED;
}

/* Atomically replace `path` with the concatenation of parts[0..count).
   Refused unless the gate's load of this same path settled.  1 = published. */
static int vv_sidecar_publish(const vv_sidecar_gate *g, const char *path,
                              const void *const *parts, const DWORD *sizes,
                              int count) {
    char tmp[MAX_PATH];
    HANDLE h;
    BOOL ok = TRUE;
    int i;
    if (g->state != VV_SIDECAR_SETTLED || lstrcmpiA(g->path, path) != 0) {
        return 0;
    }
    if (lstrlenA(path) + (int)sizeof(".tmp") > MAX_PATH) {
        return 0;
    }
    lstrcpyA(tmp, path);
    lstrcatA(tmp, ".tmp");
    h = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    for (i = 0; ok && i < count; ++i) {
        DWORD wrote = 0;
        if (!VV_SIDECAR_WRITE_FILE(h, parts[i], sizes[i], &wrote, NULL)
            || wrote != sizes[i]) {
            ok = FALSE;
        }
    }
    if (ok && !FlushFileBuffers(h)) {
        ok = FALSE;
    }
    if (!CloseHandle(h)) {
        ok = FALSE;
    }
    if (!ok) {
        DeleteFileA(tmp);   /* only the temporary name; the real file is untouched */
        return 0;
    }
    if (!MoveFileExA(tmp, path,
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp);
        return 0;
    }
    return 1;
}

#endif /* VV_SIDECAR_IO_H */
