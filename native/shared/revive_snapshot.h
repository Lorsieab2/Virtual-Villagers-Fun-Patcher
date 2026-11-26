/* revive_snapshot.h -- the complete record of a villager kept at their death or disappearance, so Revive
   Buried/Disappeared Villagers brings back the SAME PERSON, every detail (the owner, 2026-11-25, all five games:
   "every single detail of every villager should be preserved so that the resurrect upgrade can perfectly
   recreate them").

   WHO WRITES IT.  "VVFP Cause of Death.dll" (native/vvfp_cause_of_death/cod_revive.inc): every death and every
   disappearance reaches its roster_departed at the moment the game frees the record (a burial, an unburied body's
   removal, a vanishing, a Custom Island Event's death or vanishing, a Heathen's death among the Heathens) -- the
   latest moment the record still holds the person.  The record's bytes are copied there, with what the patcher's
   own files keep for that villager, and written to this save slot's file at the next save of the village (so the
   file matches the save: a session quit without saving leaves nothing).

   WHO READS IT.  "VVFP Story Upgrades.dll" (native/vvfp_story_upgrades/story_revive.inc): each Death or
   Disappeared record of the logs is matched to its snapshot by who they are, and the revival writes the
   snapshot's persistent fields onto the record the game's own creator made, all or none, verified.

   WHAT IS PERSISTENT.  Exactly what each game's own save keeps of a villager (its own writer and loader, read in
   the stock executables -- tests/test_revive_snapshot_windows.py runs those loaders and proves it), less the
   state listed below.  A field the game never saves is lost by the game itself at every save and load, so it is
   never part of who a villager is:
     A New Home        save 0x43B5D0 / load 0x43B8C0: record [0x33C, 0x3D4)
     The Lost Children save 0x44B580 / load 0x44B640: record [0x524, 0x800)
     The Secret City   load 0x456830: [0xDC4,+0xA8) [0xE6C,+0x40) [0xEAC,+0x18) [0xFB4,+0xC) [0xFC0,+0xC)
     The Tree of Life  load 0x45DBE0: [0x1B8C,+0xA8) [0x1C34,+0x28) [0x1C5C,+0x18) [0x1E60,+0x18)
     New Believers     load 0x466B60: [0x1B8C,+0xA8) [0x1C34,+0x28) [0x1C5C,+0x1C) [0x1F5C,+0x18), the faction
                       byte +0x1CEC (through its setter 0x466880), +0x1CED..+0x1CEF, +0x1CF0, +0x1CF4, +0x1CFC
   Of those, the TRANSIENT ones are never restored (the creator's fresh values stay, as for any child it makes):
   the age (the owner: they come back at age 5, RV_AGE_YEARS in story_revive.inc) and everything that follows it
   (the processed age, the life tick's slice and clock mark); health and the cause of death; sickness; a
   pregnancy and everything it copies onto the mother (the stamp, the litter, the expected father's name, head,
   body and family, the baby's inherited skill); the current work assignment and action; the movement speed
   default; The Lost Children's totem statue fields and write stamp; The Secret City's totem marker and position,
   Chief stamp and robe-ceremony variant; New Believers' Heathen cooldown deadline.  The PERSISTENT spans below
   are everything else in the saved windows.

   The Secret City's Tribal Chief flag (+0xE80) is persistent but unique: it is restored only while no other
   living villager holds it (story_revive.inc).  New Believers' faction byte is set by the game's own creator
   (the Heathen creator for a Heathen) and must agree with the snapshot, never written raw: its setter derives
   two more fields.

   THE FILE.  <save>\Virtual Villagers Fun Patcher\Save <S>\Data\Revive Snapshots\
                  Virtual Villagers <N> Revive Snapshots - Save <S>.dat   (or the older layout's folder)
   little-endian:
       u32 magic 'VRS1', u32 version 1, u32 game, u32 count (at most VV_RS_MAX)
       count x vv_rs_entry (sizeof = VV_RS_ENTRY_BYTES), oldest first
   A file that is not exactly that is never read as snapshots and never overwritten (sidecar_io.h sets it aside);
   past VV_RS_MAX the oldest entries go.  Start Over deletes it with the village.  Nothing is ever written into a
   save or a game file.

   Header-only and file-static. */
#ifndef VV_REVIVE_SNAPSHOT_H
#define VV_REVIVE_SNAPSHOT_H

#include <windows.h>
#include <string.h>

#define VV_RS_MAGIC 0x31535256u          /* 'VRS1' */
#define VV_RS_VERSION 1u
#define VV_RS_HEADER 16u
#define VV_RS_MAX 2048                   /* entries kept per save slot (the newest) */
#define VV_RS_DATA_MAX 0x300u            /* the largest saved window total: The Lost Children's 0x2DC */
#define VV_RS_NAME 32
#define VV_RS_FOLDER "Revive Snapshots"

/* What the patcher's own files kept for the villager (vv_rs_entry.flags). */
#define VV_RS_HEAD_LOOK     0x01u         /* head_look: VVFP Head Look.dll (0 Auto, 1 Young, 2 Old) */
#define VV_RS_PRESENTATION  0x02u         /* presentation: VVFP Gender Presentation.dll (0 / 1) */
#define VV_RS_MASK          0x04u         /* mask: the Origins companion's cosmetic mask (0 none, 1..5) */
#define VV_RS_TRAITS        0x08u         /* traits: the story traits (VvfpStoryTraitsOf) */
#define VV_RS_PARENTS       0x10u         /* A New Home's parents (VVFP VV1 Parentage.dll: names, looks) */
#define VV_RS_ORIGINAL      0x20u         /* original_*: VVFP Original Look.dll's look before any change (The Secret
                                             City: a Chief who comes back while another Chief lives takes their
                                             own body, not the robe -- the owner's decision, 2026-11-26) */

/* Where a snapshot came from (vv_rs_entry.source).  Repair Saves & Logs (src/vv_revive_backfill.py, the owner
   2026-11-26: "repair logs/saves should also retroactively make revival files for any deceased/disappeared
   villagers") makes them for those who left before the capture existed, from the saved entries the game's own
   save writes -- a stale copy still in the save, or the slot's save in a backup -- byte for byte. */
#define VV_RS_CAPTURED 0u                /* kept at the departure (cod_revive.inc): every field as they left */
#define VV_RS_FROM_SAVE 1u               /* a stale copy of their entry still in the slot's save */
#define VV_RS_FROM_BACKUP 2u             /* their entry in a backup of the slot's save (when they were alive) */
/* What a backfilled snapshot holds exactly (vv_rs_entry.exact); a captured one holds everything. */
#define VV_RS_EXACT_IDENTITY 0x01u       /* name, sex, looks, personal number, family, parents, likes, dislikes */
#define VV_RS_EXACT_LATER 0x02u          /* skills, job preference, titles, Faith, masks, role: as at the departure
                                            (else as they were when the source was saved) */

typedef struct {
    unsigned int check;                  /* FNV-1a of every byte after this field (vv_rs_checksum) */
    unsigned int game;
    unsigned int bytes;                  /* vv_rs_data_bytes(game) */
    unsigned int flags;                  /* VV_RS_* */
    unsigned int source;                 /* VV_RS_CAPTURED / VV_RS_FROM_SAVE / VV_RS_FROM_BACKUP */
    unsigned int exact;                  /* VV_RS_EXACT_* */
    unsigned int when_lo, when_hi;       /* FILETIME (UTC) of the departure, or of the source's save */
    int head_look;
    int presentation;
    int mask;
    unsigned int traits;
    int original_head, original_body, original_mask;   /* VV_RS_ORIGINAL: their look before any change */
    int parent_looks[4];                 /* A New Home: father head, body, mother head, body (-1 unknown) */
    char father[VV_RS_NAME];             /* A New Home's parents' names ("" unknown) */
    char mother[VV_RS_NAME];
    unsigned char data[VV_RS_DATA_MAX];  /* the saved windows, in order (vv_rs_saved) */
} vv_rs_entry;

#define VV_RS_ENTRY_BYTES ((unsigned int)sizeof(vv_rs_entry))

typedef struct {
    unsigned short offset;
    unsigned short size;
} vv_rs_span;

/* What each game's save keeps of a villager, record offsets (the stock writers and loaders above). */
static const vv_rs_span VV_RS_SAVED_1[] = { { 0x33C, 0x98 } };
static const vv_rs_span VV_RS_SAVED_2[] = { { 0x524, 0x2DC } };
static const vv_rs_span VV_RS_SAVED_3[] = {
    { 0xDC4, 0xA8 }, { 0xE6C, 0x40 }, { 0xEAC, 0x18 }, { 0xFB4, 0x0C }, { 0xFC0, 0x0C } };
static const vv_rs_span VV_RS_SAVED_4[] = { { 0x1B8C, 0xA8 }, { 0x1C34, 0x28 }, { 0x1C5C, 0x18 }, { 0x1E60, 0x18 } };
static const vv_rs_span VV_RS_SAVED_5[] = {
    { 0x1B8C, 0xA8 }, { 0x1C34, 0x28 }, { 0x1C5C, 0x1C }, { 0x1CEC, 0x0C }, { 0x1CFC, 0x04 }, { 0x1F5C, 0x18 } };

/* The persistent part: restored onto the revived villager.  Field by field (tests/test_revive_snapshot_windows.py
   FIELDS holds the whole table, persistent and transient, with the code that proves each):
     A New Home        +0x350 sex; +0x360 head, +0x364 body, +0x368 the personal number (picks the name, the
                       skeleton frame and the voice), +0x36C the family (the last name's), +0x370 the name (0x1C);
                       +0x398 likes, +0x3A8 dislikes (4 each); +0x3BC..+0x3CC skills, +0x3D0 job preference
     The Lost Children +0x538 sex; +0x548 head, +0x54C body, +0x550 personal number, +0x554 family; +0x564 name,
                       +0x57D father's name, +0x596 mother's name, +0x5B0..+0x5BC their heads and bodies;
                       +0x5F0 likes, +0x6E8 dislikes (62 each); +0x7E4..+0x7F4 skills, +0x7F8 job preference,
                       +0x7FC Esteemed Elder (the totem already made stays the only one)
     The Secret City   +0xDC8 sex, +0xDCC personal number, +0xDD0 family, +0xDD4 name, +0xDF0 head, +0xDF4 body,
                       +0xDF8 / +0xE11 the parents' names, +0xE2C..+0xE38 their looks; +0xEAC..+0xEBC skills,
                       +0xEC0 job preference; +0xFB4 likes, +0xFC0 dislikes; (+0xE80 Tribal Chief: see above)
     The Tree of Life  +0x1B90 sex, +0x1B94 personal number, +0x1B98 family, +0x1B9C name, +0x1BB8 head, +0x1BBC
                       body, +0x1BC0 / +0x1BD9 the parents' names, +0x1BF4..+0x1C00 their looks; +0x1C5C..+0x1C6C
                       skills, +0x1C70 job preference; +0x1E60 likes, +0x1E6C dislikes
     New Believers     as The Tree of Life, and +0x1C70 Devotion, +0x1C74 job preference; +0x1CED / +0x1CEE the
                       Heathen mask selectors, +0x1CEF (saved, no other reader), +0x1CF0 Faith, +0x1CFC the role
                       (Retired Chief; the puzzle roles never come back); +0x1F5C likes, +0x1F68 dislikes */
static const vv_rs_span VV_RS_KEEP_1[] = { { 0x350, 0x04 }, { 0x360, 0x2C }, { 0x398, 0x20 }, { 0x3BC, 0x18 } };
static const vv_rs_span VV_RS_KEEP_2[] = {
    { 0x538, 0x04 }, { 0x548, 0x10 }, { 0x564, 0x5C }, { 0x5F0, 0x1F0 }, { 0x7E4, 0x19 } };
static const vv_rs_span VV_RS_KEEP_3[] = { { 0xDC8, 0x74 }, { 0xEAC, 0x18 }, { 0xFB4, 0x0C }, { 0xFC0, 0x0C } };
static const vv_rs_span VV_RS_KEEP_4[] = { { 0x1B90, 0x74 }, { 0x1C5C, 0x18 }, { 0x1E60, 0x18 } };
static const vv_rs_span VV_RS_KEEP_5[] = {
    { 0x1B90, 0x74 }, { 0x1C5C, 0x1C }, { 0x1CED, 0x07 }, { 0x1CFC, 0x04 }, { 0x1F5C, 0x18 } };

#define VV_RS_COUNT(a) ((int)(sizeof(a) / sizeof((a)[0])))

/* Each game's identity fields (record offsets), for matching a log record to its snapshot. */
typedef struct {
    unsigned int stride;
    unsigned int age, sex, name, name_bytes, head, body, likes, dislikes, pref_slots;
    unsigned int faction;                /* New Believers' faction byte; 0 none */
    unsigned int chief;                  /* The Secret City's Tribal Chief byte; 0 none */
    unsigned int role;                   /* New Believers' role dword; 0 none */
    unsigned int family;
} vv_rs_layout;

static const vv_rs_layout VV_RS_LAYOUT[6] = {
    { 0 },
    { 0x3D8u, 0x348u, 0x350u, 0x370u, 0x1Cu, 0x360u, 0x364u, 0x398u, 0x3A8u, 4u, 0u, 0u, 0u, 0x36Cu },
    { 0xE48Cu, 0x530u, 0x538u, 0x564u, 0x18u, 0x548u, 0x54Cu, 0x5F0u, 0x6E8u, 62u, 0u, 0u, 0u, 0x554u },
    { 0x1F8Cu, 0xDC4u, 0xDC8u, 0xDD4u, 0x19u, 0xDF0u, 0xDF4u, 0xFB4u, 0xFC0u, 3u, 0u, 0xE80u, 0u, 0xDD0u },
    { 0x2E3Cu, 0x1B8Cu, 0x1B90u, 0x1B9Cu, 0x19u, 0x1BB8u, 0x1BBCu, 0x1E60u, 0x1E6Cu, 3u, 0u, 0u, 0u, 0x1B98u },
    { 0x2F44u, 0x1B8Cu, 0x1B90u, 0x1B9Cu, 0x19u, 0x1BB8u, 0x1BBCu, 0x1F5Cu, 0x1F68u, 3u, 0x1CECu, 0u, 0x1CFCu, 0x1B98u },
};

static const vv_rs_span *vv_rs_saved(int game, int *count) {
    switch (game) {
    case 1: *count = VV_RS_COUNT(VV_RS_SAVED_1); return VV_RS_SAVED_1;
    case 2: *count = VV_RS_COUNT(VV_RS_SAVED_2); return VV_RS_SAVED_2;
    case 3: *count = VV_RS_COUNT(VV_RS_SAVED_3); return VV_RS_SAVED_3;
    case 4: *count = VV_RS_COUNT(VV_RS_SAVED_4); return VV_RS_SAVED_4;
    case 5: *count = VV_RS_COUNT(VV_RS_SAVED_5); return VV_RS_SAVED_5;
    default: *count = 0; return NULL;
    }
}

static const vv_rs_span *vv_rs_keep(int game, int *count) {
    switch (game) {
    case 1: *count = VV_RS_COUNT(VV_RS_KEEP_1); return VV_RS_KEEP_1;
    case 2: *count = VV_RS_COUNT(VV_RS_KEEP_2); return VV_RS_KEEP_2;
    case 3: *count = VV_RS_COUNT(VV_RS_KEEP_3); return VV_RS_KEEP_3;
    case 4: *count = VV_RS_COUNT(VV_RS_KEEP_4); return VV_RS_KEEP_4;
    case 5: *count = VV_RS_COUNT(VV_RS_KEEP_5); return VV_RS_KEEP_5;
    default: *count = 0; return NULL;
    }
}

/* The bytes a snapshot of `game` holds (0 for no game). */
static unsigned int vv_rs_data_bytes(int game) {
    int n, i;
    unsigned int total = 0;
    const vv_rs_span *s = vv_rs_saved(game, &n);
    for (i = 0; i < n; ++i) {
        total += s[i].size;
    }
    return total;
}

/* Where record offset `offset` (`size` bytes) is kept in a snapshot's data, or NULL when it is not saved. */
static const unsigned char *vv_rs_at(const vv_rs_entry *e, unsigned int offset, unsigned int size) {
    int n, i;
    unsigned int at = 0;
    const vv_rs_span *s = vv_rs_saved((int)e->game, &n);
    for (i = 0; i < n; ++i) {
        if (offset >= s[i].offset && offset + size <= (unsigned int)s[i].offset + s[i].size) {
            return e->data + at + (offset - s[i].offset);
        }
        at += s[i].size;
    }
    return NULL;
}

static int vv_rs_int(const vv_rs_entry *e, unsigned int offset, int fallback) {
    const unsigned char *p = vv_rs_at(e, offset, 4);
    return p != NULL ? *(const int *)p : fallback;
}

static unsigned int vv_rs_fnv(unsigned int h, const unsigned char *p, unsigned int n) {
    unsigned int i;
    for (i = 0; i < n; ++i) {
        h = (h ^ p[i]) * 16777619u;
    }
    return h;
}

static unsigned int vv_rs_checksum(const vv_rs_entry *e) {
    unsigned int h = vv_rs_fnv(2166136261u, (const unsigned char *)e + sizeof e->check,
                               VV_RS_ENTRY_BYTES - (unsigned int)sizeof e->check);
    return h != 0 ? h : 1u;
}

/* A fresh entry for `game`: nothing the patcher's files keep known yet. */
static void vv_rs_begin(vv_rs_entry *e, int game) {
    memset(e, 0, sizeof *e);
    e->game = (unsigned int)game;
    e->bytes = vv_rs_data_bytes(game);
    e->source = VV_RS_CAPTURED;
    e->exact = VV_RS_EXACT_IDENTITY | VV_RS_EXACT_LATER;
    e->head_look = e->presentation = e->mask = -1;
    e->original_head = e->original_body = e->original_mask = -1;
    e->parent_looks[0] = e->parent_looks[1] = e->parent_looks[2] = e->parent_looks[3] = -1;
}

/* The record's saved windows into `e` (vv_rs_begin first).  1 done. */
static int vv_rs_take(vv_rs_entry *e, const unsigned char *record) {
    int n, i;
    unsigned int at = 0;
    const vv_rs_span *s = vv_rs_saved((int)e->game, &n);
    if (record == NULL || s == NULL || e->bytes > VV_RS_DATA_MAX) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        memcpy(e->data + at, record + s[i].offset, s[i].size);
        at += s[i].size;
    }
    return 1;
}

/* Sealed: the checksum over everything (call after the last field is set). */
static void vv_rs_seal(vv_rs_entry *e) {
    e->check = vv_rs_checksum(e);
}

/* Whether `e` is a whole, sealed snapshot of `game`. */
static int vv_rs_valid(const vv_rs_entry *e, int game) {
    return e->game == (unsigned int)game && game >= 1 && game <= 5 && e->bytes == vv_rs_data_bytes(game)
        && e->source <= VV_RS_FROM_BACKUP && e->check == vv_rs_checksum(e) && e->father[VV_RS_NAME - 1] == '\0' && e->mother[VV_RS_NAME - 1] == '\0';
}

/* Whether a whole file image (`length` bytes) is a snapshot file of `game`: every entry valid. */
static int vv_rs_file_valid(const unsigned char *data, DWORD length, int game) {
    unsigned int count, i;
    if (length < VV_RS_HEADER) {
        return 0;
    }
    count = ((const unsigned int *)data)[3];
    if (((const unsigned int *)data)[0] != VV_RS_MAGIC || ((const unsigned int *)data)[1] != VV_RS_VERSION
        || ((const unsigned int *)data)[2] != (unsigned int)game || count > (unsigned int)VV_RS_MAX
        || length != VV_RS_HEADER + count * VV_RS_ENTRY_BYTES) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        vv_rs_entry e;
        memcpy(&e, data + VV_RS_HEADER + i * VV_RS_ENTRY_BYTES, sizeof e);
        if (!vv_rs_valid(&e, game)) {
            return 0;
        }
    }
    return 1;
}

/* The snapshot's name (NUL-terminated, at most `size` - 1 characters of the record's field). */
static void vv_rs_name(const vv_rs_entry *e, char *out, int size) {
    const vv_rs_layout *l = &VV_RS_LAYOUT[e->game <= 5 ? e->game : 0];
    const unsigned char *p = vv_rs_at(e, l->name, l->name_bytes);
    int k;
    out[0] = '\0';
    if (p == NULL) {
        return;
    }
    for (k = 0; k + 1 < size && (unsigned int)k < l->name_bytes && p[k] != 0; ++k) {
        out[k] = (char)p[k];
    }
    out[k] = '\0';
}

/* Whether every persistent byte of two snapshots is the same (the same person kept twice). */
static int vv_rs_same_keep(const vv_rs_entry *a, const vv_rs_entry *b) {
    int n, i;
    const vv_rs_span *s;
    if (a->game != b->game) {
        return 0;
    }
    s = vv_rs_keep((int)a->game, &n);
    for (i = 0; i < n; ++i) {
        const unsigned char *x = vv_rs_at(a, s[i].offset, s[i].size), *y = vv_rs_at(b, s[i].offset, s[i].size);
        if (x == NULL || y == NULL || memcmp(x, y, s[i].size) != 0) {
            return 0;
        }
    }
    return a->flags == b->flags && a->head_look == b->head_look && a->presentation == b->presentation
        && a->mask == b->mask && a->traits == b->traits && a->original_body == b->original_body
        && memcmp(a->parent_looks, b->parent_looks, sizeof a->parent_looks) == 0
        && lstrcmpA(a->father, b->father) == 0 && lstrcmpA(a->mother, b->mother) == 0;
}

/* The persistent fields of `e` written onto `record` (the record the game's own creator just made), all or
   none: `backup` (the record's stride of bytes) takes the record first, every span is written, then read back;
   any difference and the record is put back exactly as the creator left it.  `chief`: The Secret City's Tribal
   Chief byte is written too (the caller found no other living Chief).  1 when every field is the snapshot's. */
static int vv_rs_apply(const vv_rs_entry *e, unsigned char *record, unsigned char *backup, int chief) {
    const vv_rs_layout *l;
    int n, i, ok = 1;
    const vv_rs_span *s;
    int game = (int)e->game;
    if (record == NULL || backup == NULL || game < 1 || game > 5 || !vv_rs_valid(e, game)) {
        return 0;
    }
    l = &VV_RS_LAYOUT[game];
    s = vv_rs_keep(game, &n);
    if (l->faction != 0u) {
        const unsigned char *f = vv_rs_at(e, l->faction, 1);
        if (f == NULL || (record[l->faction] != 0) != (*f != 0)) {
            return 0;                    /* the creator made the other faction: never flipped raw */
        }
    }
    memcpy(backup, record, l->stride);
    for (i = 0; i < n; ++i) {
        const unsigned char *from = vv_rs_at(e, s[i].offset, s[i].size);
        if (from == NULL) {
            ok = 0;
            break;
        }
        memcpy(record + s[i].offset, from, s[i].size);
    }
    if (ok && chief && l->chief != 0u) {
        const unsigned char *c = vv_rs_at(e, l->chief, 1);
        if (c != NULL) {
            record[l->chief] = *c;
        }
    }
    for (i = 0; ok && i < n; ++i) {
        const unsigned char *from = vv_rs_at(e, s[i].offset, s[i].size);
        ok = from != NULL && memcmp(record + s[i].offset, from, s[i].size) == 0;
    }
    /* ...and nothing the creator made for a child of five moved: the age stays the creator's. */
    if (ok && memcmp(record + l->age, backup + l->age, 4) != 0) {
        ok = 0;
    }
    if (!ok) {
        memcpy(record, backup, l->stride);
        return 0;
    }
    return 1;
}

#endif /* VV_REVIVE_SNAPSHOT_H */
