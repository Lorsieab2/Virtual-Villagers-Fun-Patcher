/* New Believers' former Heathens: who was converted from the Heathens, and
 * which mask they wore -- the per-save-slot .dat file "VVFP Cause of
 * Death.dll" writes and the log exporters read.
 *
 * WHY.  The owner's Special villager titles (2026-10-06) include "Former
 * Heathen (blue/red/orange mask)", "Former Heathen Master (purple mask)" and
 * "Retired Heathen Chief".  The game keeps only some of that: the conversion
 * 0x4668B0 zeroes the type dword +0x1CFC unless it is 13 (the Heathen
 * Chief, 0x466966), then clears the faction byte (0x466880(0)); the mask
 * selector bytes +0x1CED (orange) and +0x1CEE (red) are left as they were.
 * So a converted Master or Doctor (type 12, 14-16: the purple mask, 0x4728C6)
 * and a converted blue Heathen look exactly like a villager born a believer.
 * What the game does not keep goes in a .dat file (the owner's rule):
 *
 *     <save folder>\Virtual Villagers Fun Patcher Data\Former Heathens\Former Heathens - Save N.dat
 *
 * FORMAT (little-endian):
 *     u32 magic 'VFH1' (0x31484656), u32 version 1, u32 game (5),
 *     u32 count (0..VV_FORMER_MAX), then `count` entries:
 *         u32 identity, u32 kind
 *     The file is exactly 16 + count * 8 bytes.
 *
 * `identity` is native/shared/custom_titles.h's vv_title_identity -- the
 * name, likes and dislikes, which the games never change on their own -- so
 * a record reused by somebody else never inherits it, and an identity two
 * entries carry is nobody's.  `kind` is the mask the Heathen wore, as the
 * game's mask draw picks it (0x4728C6): VV_FORMER_BLUE, _ORANGE, _RED,
 * _MASTER (purple: types 12 and 14-16, the Doctor and the three Masters),
 * _CHIEF (type 13).  Start Over deletes the file with the village
 * (native/shared/save_reset.c).  Header-only and static. */
#ifndef VV_FORMER_HEATHENS_H
#define VV_FORMER_HEATHENS_H

#include <windows.h>
#include <string.h>

#define VV_FORMER_MAGIC 0x31484656u     /* 'VFH1' */
#define VV_FORMER_VERSION 1u
#define VV_FORMER_MAX 1024
#define VV_FORMER_HEADER 16u
#define VV_FORMER_ENTRY 8u
#define VV_FORMER_FILE_MAX (VV_FORMER_HEADER + VV_FORMER_MAX * VV_FORMER_ENTRY)
#define VV_FORMER_SUBFOLDER "Virtual Villagers Fun Patcher Data\\Former Heathens"

enum {
    VV_FORMER_BLUE = 0,
    VV_FORMER_ORANGE = 1,
    VV_FORMER_RED = 2,
    VV_FORMER_MASTER = 3,
    VV_FORMER_CHIEF = 4
};

/* New Believers' villager record (vv5 offsets). */
#define VV5_FACTION 0x1CECu             /* u8, non-zero: a Heathen */
#define VV5_ORANGE 0x1CEDu              /* u8 mask selector */
#define VV5_RED 0x1CEEu                 /* u8 mask selector */
#define VV5_TYPE 0x1CFCu                /* i32, 12..17 the Heathen roles */

/* The mask a Heathen's record wears, as the game's mask draw chooses it
   (0x4728C6: types 12 and 14-16 purple, 13 the Chief's; otherwise orange,
   red or blue by the selector bytes). */
static int vv_former_kind_of(const unsigned char *record) {
    int type = *(const int *)(record + VV5_TYPE);
    if (type == 13) {
        return VV_FORMER_CHIEF;
    }
    if (type == 12 || (type >= 14 && type <= 16)) {
        return VV_FORMER_MASTER;
    }
    if (record[VV5_ORANGE] != 0) {
        return VV_FORMER_ORANGE;
    }
    return record[VV5_RED] != 0 ? VV_FORMER_RED : VV_FORMER_BLUE;
}

static const char *vv_former_mask_word(int kind) {
    switch (kind) {
    case VV_FORMER_BLUE: return "blue mask";
    case VV_FORMER_ORANGE: return "orange mask";
    case VV_FORMER_RED: return "red mask";
    case VV_FORMER_MASTER: return "purple mask";
    case VV_FORMER_CHIEF: return "Tribal Chief mask";
    default: return NULL;
    }
}

/* The Special villager title of a believer converted from the Heathens. */
static const char *vv_former_title(int kind) {
    switch (kind) {
    case VV_FORMER_BLUE: return "Former Heathen (blue mask)";
    case VV_FORMER_ORANGE: return "Former Heathen (orange mask)";
    case VV_FORMER_RED: return "Former Heathen (red mask)";
    case VV_FORMER_MASTER: return "Former Heathen Master (purple mask)";
    case VV_FORMER_CHIEF: return "Retired Heathen Chief";
    default: return NULL;
    }
}

static unsigned int vv_former_u32(const unsigned char *p) {
    unsigned int v;
    memcpy(&v, p, 4);
    return v;
}

/* The whole file: header, exact size, every kind known. */
static int vv_former_validate(const unsigned char *data, DWORD len) {
    unsigned int count, i;
    if (len < VV_FORMER_HEADER || vv_former_u32(data) != VV_FORMER_MAGIC
        || vv_former_u32(data + 4) != VV_FORMER_VERSION || vv_former_u32(data + 8) != 5u) {
        return 0;
    }
    count = vv_former_u32(data + 12);
    if (count > VV_FORMER_MAX || len != VV_FORMER_HEADER + count * VV_FORMER_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (vv_former_u32(data + VV_FORMER_HEADER + i * VV_FORMER_ENTRY + 4) > VV_FORMER_CHIEF) {
            return 0;
        }
    }
    return 1;
}

/* The kind recorded for `identity` in a validated file: -1 when no entry,
   or two, carry it. */
static int vv_former_lookup(const unsigned char *data, unsigned int identity) {
    unsigned int count = vv_former_u32(data + 12), i;
    int found = -1;
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + VV_FORMER_HEADER + i * VV_FORMER_ENTRY;
        if (vv_former_u32(e) == identity) {
            if (found >= 0) {
                return -1;
            }
            found = (int)vv_former_u32(e + 4);
        }
    }
    return found;
}

/* "<folder>\Former Heathens - Save N.dat" from an already-resolved folder. */
static int vv_former_file_name(char *out, int cap, const char *folder, int slot) {
    int length;
    if (slot < 1 || slot > 5 || lstrlenA(folder) + (int)sizeof("\\Former Heathens - Save 0.dat") > cap) {
        return 0;
    }
    lstrcpyA(out, folder);
    lstrcatA(out, "\\Former Heathens - Save 0.dat");
    length = lstrlenA(out);
    out[length - 5] = (char)('0' + slot);
    return 1;
}

#endif /* VV_FORMER_HEATHENS_H */
