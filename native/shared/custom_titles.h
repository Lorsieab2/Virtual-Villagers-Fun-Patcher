/* Custom villager titles: the per-save-slot .dat file the Story / Cheat
 * Upgrades "Custom Island Event" writes, and every reader agrees on.
 *
 * The owner: a custom title ("Master Farmer" -> any text) is shown EVERYWHERE
 * the title shows -- the villager panel, the Details screen and the patcher's
 * logs -- and is "persisted per save slot in a patcher .dat file beside the
 * saves" (untracked data goes in a .dat file, never in spare record bytes),
 * and the file follows the Start Over reset.
 *
 *     <save folder>\Virtual Villagers Fun Patcher Data\Custom Titles\Custom Titles - Save N.dat
 *
 * `<save folder>` is Documents\LDW\<exe basename> (native/shared/save_folder.h).
 * Written by "VVFP Story Upgrades.dll" through native/shared/sidecar_io.h
 * (atomic publish, invalid files set aside, never written before its load
 * settled); read by it and by the Village Population / History exporter;
 * deleted by the Start Over reset (native/shared/save_reset.c).
 *
 * FORMAT (little-endian):
 *     u32 magic 'VCT1' (0x31544356), u32 version 1, u32 game (1..5),
 *     u32 count (0..VV_TITLES_MAX), then `count` entries:
 *         u32 record index, u32 fingerprint, char title[VV_TITLE_BYTES]
 *     The file is exactly 16 + count * 40 bytes.
 *
 * A title belongs to the villager in record `index` whose name hashes to
 * `fingerprint`.  A record index alone is not an identity -- the games reuse
 * a dead villager's record for the next birth -- so every reader checks the
 * fingerprint against the record it is about to label, and shows nothing when
 * it differs.  A title is printable ASCII (the games' fonts), at most
 * VV_TITLE_MAX characters, never empty. */
#ifndef VV_CUSTOM_TITLES_H
#define VV_CUSTOM_TITLES_H

#include <windows.h>
#include <string.h>

#define VV_TITLES_MAGIC 0x31544356u     /* 'VCT1' */
#define VV_TITLES_VERSION 1u
#define VV_TITLES_MAX 256
#define VV_TITLE_BYTES 32
#define VV_TITLE_MAX (VV_TITLE_BYTES - 1)
#define VV_TITLES_HEADER 16u
#define VV_TITLES_ENTRY 40u
#define VV_TITLES_FILE_MAX (VV_TITLES_HEADER + VV_TITLES_MAX * VV_TITLES_ENTRY)
#define VV_TITLES_SUBFOLDER "Virtual Villagers Fun Patcher Data\\Custom Titles"

typedef struct {
    unsigned int index;
    unsigned int fingerprint;
    char title[VV_TITLE_BYTES];
} vv_custom_title;

/* FNV-1a over the villager's own name (up to `capacity` bytes, stopping at
   the terminator), with a terminator mixed in so a short name is not a
   prefix of a longer one.  Never 0. */
static unsigned int vv_title_fingerprint(const unsigned char *name, unsigned int capacity) {
    unsigned int h = 2166136261u;
    unsigned int i;
    for (i = 0; i < capacity && name[i] != 0; ++i) {
        h = (h ^ name[i]) * 16777619u;
    }
    h = (h ^ 0xFFu) * 16777619u;
    return h ? h : 1u;
}

/* 1 when `text` is a title this format accepts: 1..VV_TITLE_MAX printable
   ASCII characters, not all spaces, NUL-terminated within VV_TITLE_BYTES. */
static int vv_title_valid(const char *text) {
    int i;
    int visible = 0;
    for (i = 0; i < VV_TITLE_BYTES; ++i) {
        unsigned char c = (unsigned char)text[i];
        if (c == 0) {
            return visible && i <= VV_TITLE_MAX;
        }
        if (c < 0x20 || c > 0x7E) {
            return 0;
        }
        if (c != ' ') {
            visible = 1;
        }
    }
    return 0;
}

static unsigned int vv_titles_u32(const unsigned char *p) {
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8) | ((unsigned int)p[2] << 16)
        | ((unsigned int)p[3] << 24);
}

/* Structural validation of a whole file for `game` (passed as ctx, an int*):
   the header, the exact size, every index below `slots`, every title valid,
   and no index listed twice. */
typedef struct {
    int game;
    unsigned int slots;
} vv_titles_check;

static int vv_titles_validate(const unsigned char *data, DWORD len, void *ctx) {
    const vv_titles_check *check = (const vv_titles_check *)ctx;
    unsigned int count;
    unsigned int i;
    unsigned int j;
    if (len < VV_TITLES_HEADER || vv_titles_u32(data) != VV_TITLES_MAGIC
        || vv_titles_u32(data + 4) != VV_TITLES_VERSION
        || vv_titles_u32(data + 8) != (unsigned int)check->game) {
        return 0;
    }
    count = vv_titles_u32(data + 12);
    if (count > VV_TITLES_MAX || len != VV_TITLES_HEADER + count * VV_TITLES_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + VV_TITLES_HEADER + i * VV_TITLES_ENTRY;
        if (vv_titles_u32(e) >= check->slots || vv_titles_u32(e + 4) == 0
            || !vv_title_valid((const char *)(e + 8))) {
            return 0;
        }
        for (j = 0; j < i; ++j) {
            if (vv_titles_u32(data + VV_TITLES_HEADER + j * VV_TITLES_ENTRY) == vv_titles_u32(e)) {
                return 0;
            }
        }
    }
    return 1;
}

/* Copy the entries of a validated file into `out`; returns the count. */
static int vv_titles_parse(const unsigned char *data, vv_custom_title *out) {
    unsigned int count = vv_titles_u32(data + 12);
    unsigned int i;
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + VV_TITLES_HEADER + i * VV_TITLES_ENTRY;
        out[i].index = vv_titles_u32(e);
        out[i].fingerprint = vv_titles_u32(e + 4);
        memcpy(out[i].title, e + 8, VV_TITLE_BYTES);
        out[i].title[VV_TITLE_MAX] = '\0';
    }
    return (int)count;
}

/* Serialise `count` entries (at most VV_TITLES_MAX) into `out`, which must
   hold VV_TITLES_FILE_MAX bytes.  Returns the byte count. */
static DWORD vv_titles_serialise(int game, const vv_custom_title *entries, int count,
                                 unsigned char *out) {
    unsigned int header[4];
    int i;
    header[0] = VV_TITLES_MAGIC;
    header[1] = VV_TITLES_VERSION;
    header[2] = (unsigned int)game;
    header[3] = (unsigned int)count;
    memcpy(out, header, sizeof header);
    for (i = 0; i < count; ++i) {
        unsigned char *e = out + VV_TITLES_HEADER + (unsigned int)i * VV_TITLES_ENTRY;
        memcpy(e, &entries[i].index, 4);
        memcpy(e + 4, &entries[i].fingerprint, 4);
        memset(e + 8, 0, VV_TITLE_BYTES);
        lstrcpynA((char *)(e + 8), entries[i].title, VV_TITLE_BYTES);
    }
    return VV_TITLES_HEADER + (DWORD)count * VV_TITLES_ENTRY;
}

/* "<folder>\Custom Titles - Save N.dat" from an already-resolved folder
   (kernel32 only: the population exporter links no user32). */
static int vv_titles_file_name(char *out, int cap, const char *folder, int slot) {
    int length;
    if (slot < 1 || slot > 5 || lstrlenA(folder) + (int)sizeof("\\Custom Titles - Save 0.dat") > cap) {
        return 0;
    }
    lstrcpyA(out, folder);
    lstrcatA(out, "\\Custom Titles - Save 0.dat");
    length = lstrlenA(out);
    out[length - 5] = (char)('0' + slot);
    return 1;
}

#endif /* VV_CUSTOM_TITLES_H */
