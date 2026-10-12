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
 *     u32 magic 'VCT1' (0x31544356), u32 version 3, u32 game (1..5),
 *     u32 count (0..VV_TITLES_MAX), then `count` entries of 84 bytes:
 *         u32 record index, or VV_TITLE_PENDING (0xFFFFFFFF)
 *         u32 fingerprint
 *         u32 flags: bit 0 VV_TITLE_KNOWN = the looks below were read from
 *             the villager (0: not yet -- an entry carried over from a
 *             version 2 file -- and the looks are all 0)
 *             bit 1 VV_TITLE_CONTESTED = pending only: while it waited,
 *             two or more villagers could be them at once, so the companion
 *             never binds it again by itself (the reconciliation asks)
 *         i32 age, i32 head, i32 body, i32 sex (the record's own values)
 *         u32 skills[VV_TITLE_SKILLS] (the record's own dwords: ints in A New
 *             Home to The Secret City, floats in The Tree of Life and New
 *             Believers; 0 past the game's own skill count)
 *         char title[VV_TITLE_BYTES]
 *     The file is exactly 16 + count * 84 bytes.
 *
 *     Version 2 (v1.35.58 to v1.35.69) is still read: 40-byte entries of
 *     u32 record index, u32 fingerprint, char title[32], each taken as a
 *     bound entry whose looks are not known yet; the companion writes the
 *     table back as version 3.  Version 1 hashed the name alone, and names
 *     repeat, so a v1 file is set aside, never read.
 *
 * A title belongs to the villager in record `index` whose name, likes and
 * dislikes hash to `fingerprint` (vv_title_identity).  A record index alone
 * is not an identity -- the games reuse a dead villager's record for the next
 * birth -- so every reader checks the fingerprint against the record it is
 * about to label, and shows nothing when it differs.
 *
 * A PENDING title (index VV_TITLE_PENDING) is one whose villager could not be
 * told apart after a load: two present villagers could be them, or none.  It
 * is shown on nobody and is never dropped for that; the companion binds it
 * again once exactly one present villager has the whole stored identity --
 * the fingerprint, the same head, body and sex, and an age and every skill no
 * lower than stored (a villager only grows older and more skilled) -- and no
 * other entry claims that villager.  NEVER A GUESS (the owner): a pending
 * title that two or more villagers could be at once is CONTESTED, and when
 * the others later die or leave, the one left is not taken for them -- that
 * would be a guess -- so a contested title waits for the player.  The
 * read-only reconciliation asks the player about every pending title,
 * naming who could be them (src/vv_reconcile.py).  The stored age and
 * skills are the values the companion first saw the villager with in the
 * session (the save's own, so a later save never holds less).
 *
 * A title is printable ASCII (the games' fonts), at most VV_TITLE_MAX
 * characters, never empty. */
#ifndef VV_CUSTOM_TITLES_H
#define VV_CUSTOM_TITLES_H

#include <windows.h>
#include <string.h>

#define VV_TITLES_MAGIC 0x31544356u     /* 'VCT1' */
#define VV_TITLES_VERSION 3u
#define VV_TITLES_VERSION_2 2u
#define VV_TITLES_MAX 256
#define VV_TITLE_BYTES 32
#define VV_TITLE_MAX (VV_TITLE_BYTES - 1)
#define VV_TITLE_SKILLS 6               /* New Believers has six skills, the others five */
#define VV_TITLE_PENDING 0xFFFFFFFFu
#define VV_TITLE_KNOWN 1u
#define VV_TITLE_CONTESTED 2u           /* pending only: two or more could be them while it waited */
#define VV_TITLE_FLAGS (VV_TITLE_KNOWN | VV_TITLE_CONTESTED)
#define VV_TITLES_HEADER 16u
#define VV_TITLES_ENTRY 84u
#define VV_TITLES_ENTRY_2 40u
#define VV_TITLES_FILE_MAX (VV_TITLES_HEADER + VV_TITLES_MAX * VV_TITLES_ENTRY)
#define VV_TITLES_SUBFOLDER "Virtual Villagers Fun Patcher Data\\Custom Titles"

/* What a title's villager looked like besides the fingerprint. */
typedef struct {
    int age;
    int head;
    int body;
    int sex;
    unsigned int skills[VV_TITLE_SKILLS];
} vv_title_looks;

typedef struct {
    unsigned int index;             /* the record, or VV_TITLE_PENDING */
    unsigned int fingerprint;
    unsigned int flags;             /* VV_TITLE_KNOWN */
    vv_title_looks looks;
    char title[VV_TITLE_BYTES];
} vv_custom_title;

static float vv_title_skill_float(unsigned int raw) {
    float value;
    memcpy(&value, &raw, sizeof value);
    return value;
}

#define VV_TITLE_SKILL_MAX 100

/* One skill dword as the corrupted-skill reset leaves it (native/shared/
   skill_repair.h, src/vv_corrupt_skills.py): NaN, +-infinity or below 0 ->
   0, above 100 -> 100, anything else as it is.  A title's skills are stored
   and compared so, so a reset of a corrupted value never makes its villager
   look like someone else. */
static unsigned int vv_title_skill_normalised(unsigned int raw, int skills_float) {
    if (skills_float) {
        /* By the bits, so no floating-point mode can change it: an all-ones
           exponent is NaN or infinity, the sign bit a value below 0. */
        if ((raw & 0x7F800000u) == 0x7F800000u || (raw & 0x80000000u) != 0u) {
            return 0u;                                        /* 0.0f */
        }
        return vv_title_skill_float(raw) > (float)VV_TITLE_SKILL_MAX ? 0x42C80000u : raw;   /* 100.0f */
    }
    if ((int)raw < 0) {
        return 0u;
    }
    return (int)raw > VV_TITLE_SKILL_MAX ? (unsigned int)VV_TITLE_SKILL_MAX : raw;
}

static void vv_title_normalise_skills(vv_title_looks *looks, int skills_float) {
    int k;
    for (k = 0; k < VV_TITLE_SKILLS; ++k) {
        looks->skills[k] = vv_title_skill_normalised(looks->skills[k], skills_float);
    }
}

/* Could the villager `now` (head, body and sex as they are; age and skills
   as first seen this session) be the one `stored` was taken from?  The same
   head, body and sex; no younger; no skill lower -- both sides' skills taken
   as the corrupted-skill reset leaves them, so a reset is never a lower
   skill.  `skills_float`: the game keeps float skills. */
static int vv_title_looks_could_be(const vv_title_looks *stored, const vv_title_looks *now, int skills_float) {
    int k;
    if (stored->head != now->head || stored->body != now->body || stored->sex != now->sex
        || now->age < stored->age) {
        return 0;
    }
    for (k = 0; k < VV_TITLE_SKILLS; ++k) {
        unsigned int was = vv_title_skill_normalised(stored->skills[k], skills_float);
        unsigned int is = vv_title_skill_normalised(now->skills[k], skills_float);
        if (skills_float ? vv_title_skill_float(is) < vv_title_skill_float(was) : (int)is < (int)was) {
            return 0;
        }
    }
    return 1;
}

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

/* Who a title belongs to: the name, then the likes and dislikes arrays
   (`slots` dwords each).  The games DO change likes and dislikes (island
   events, the Custom Island Event, vials, upgrades): the writers carry each
   entry to the new identity as it changes (identity_in_place.h).  Names
   come from a fixed pool, so a record reused by another villager of the same
   name must not inherit the title.  Appearance is left out: the player can
   change it (Change Appearance) without becoming someone else.  Never 0. */
static unsigned int vv_title_identity(const unsigned char *record, unsigned int name,
                                      unsigned int name_capacity, unsigned int likes,
                                      unsigned int dislikes, unsigned int slots) {
    unsigned int h = vv_title_fingerprint(record + name, name_capacity);
    unsigned int i;
    for (i = 0; i < slots * 4u; ++i) {
        h = (h ^ record[likes + i]) * 16777619u;
    }
    for (i = 0; i < slots * 4u; ++i) {
        h = (h ^ record[dislikes + i]) * 16777619u;
    }
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
   the header, the version (3, or 2 from older releases), the exact size,
   every index below `slots` or pending, every fingerprint non-zero, every
   flag known, the looks all 0 when not known, every title valid, and no
   record listed twice. */
typedef struct {
    int game;
    unsigned int slots;
} vv_titles_check;

static unsigned int vv_titles_entry_size(unsigned int version) {
    return version == VV_TITLES_VERSION ? VV_TITLES_ENTRY : VV_TITLES_ENTRY_2;
}

/* Where an entry's title is (the last 32 bytes of either version's entry). */
#define VV_TITLES_TITLE_AT(size) ((size) - VV_TITLE_BYTES)

static int vv_titles_validate(const unsigned char *data, DWORD len, void *ctx) {
    const vv_titles_check *check = (const vv_titles_check *)ctx;
    unsigned int count;
    unsigned int version;
    unsigned int size;
    unsigned int i;
    unsigned int j;
    if (len < VV_TITLES_HEADER || vv_titles_u32(data) != VV_TITLES_MAGIC
        || vv_titles_u32(data + 8) != (unsigned int)check->game) {
        return 0;
    }
    version = vv_titles_u32(data + 4);
    if (version != VV_TITLES_VERSION && version != VV_TITLES_VERSION_2) {
        return 0;
    }
    size = vv_titles_entry_size(version);
    count = vv_titles_u32(data + 12);
    if (count > VV_TITLES_MAX || len != VV_TITLES_HEADER + count * size) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + VV_TITLES_HEADER + i * size;
        unsigned int index = vv_titles_u32(e);
        if (index == VV_TITLE_PENDING ? version != VV_TITLES_VERSION : index >= check->slots) {
            return 0;
        }
        if (vv_titles_u32(e + 4) == 0 || !vv_title_valid((const char *)(e + VV_TITLES_TITLE_AT(size)))) {
            return 0;
        }
        if (version == VV_TITLES_VERSION) {
            unsigned int flags = vv_titles_u32(e + 8);
            if ((flags & ~VV_TITLE_FLAGS) != 0
                || ((flags & VV_TITLE_CONTESTED) && index != VV_TITLE_PENDING)) {
                return 0;
            }
            if (!(flags & VV_TITLE_KNOWN)) {
                for (j = 12; j < 12 + (unsigned int)sizeof(vv_title_looks); ++j) {
                    if (e[j] != 0) {
                        return 0;
                    }
                }
            }
        }
        for (j = 0; j < i && index != VV_TITLE_PENDING; ++j) {
            if (vv_titles_u32(data + VV_TITLES_HEADER + j * size) == index) {
                return 0;
            }
        }
    }
    return 1;
}

/* Copy the entries of a validated file into `out`; returns the count.  A
   version 2 entry is bound, its looks not known yet. */
static int vv_titles_parse(const unsigned char *data, vv_custom_title *out) {
    unsigned int version = vv_titles_u32(data + 4);
    unsigned int size = vv_titles_entry_size(version);
    unsigned int count = vv_titles_u32(data + 12);
    unsigned int i;
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + VV_TITLES_HEADER + i * size;
        memset(&out[i], 0, sizeof out[i]);
        out[i].index = vv_titles_u32(e);
        out[i].fingerprint = vv_titles_u32(e + 4);
        if (version == VV_TITLES_VERSION) {
            out[i].flags = vv_titles_u32(e + 8);
            memcpy(&out[i].looks, e + 12, sizeof out[i].looks);
        }
        memcpy(out[i].title, e + VV_TITLES_TITLE_AT(size), VV_TITLE_BYTES);
        out[i].title[VV_TITLE_MAX] = '\0';
    }
    return (int)count;
}

/* Serialise `count` entries (at most VV_TITLES_MAX) into `out`, which must
   hold VV_TITLES_FILE_MAX bytes, as version 3.  Returns the byte count. */
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
        unsigned int flags = entries[i].flags
            & (entries[i].index == VV_TITLE_PENDING ? VV_TITLE_FLAGS : VV_TITLE_KNOWN);
        memcpy(e, &entries[i].index, 4);
        memcpy(e + 4, &entries[i].fingerprint, 4);
        memcpy(e + 8, &flags, 4);
        if (flags & VV_TITLE_KNOWN) {
            memcpy(e + 12, &entries[i].looks, sizeof entries[i].looks);
        } else {
            memset(e + 12, 0, sizeof entries[i].looks);
        }
        memset(e + 52, 0, VV_TITLE_BYTES);
        lstrcpynA((char *)(e + 52), entries[i].title, VV_TITLE_BYTES);
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
