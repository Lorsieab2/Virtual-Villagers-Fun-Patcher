/* villager_rekey.h -- a villager renamed by another companion keeps what is kept for them.

   WHY.  Every per-save file that follows a villager keys them by an identity that hashes the name:
   the custom titles and New Believers' Former Heathens (custom_titles.h vv_title_identity: name,
   likes, dislikes), the Origins masks, the Head Looks and the Original Looks (name, sex, the parents'
   names).  A rename the PLAYER makes during play is followed by each owner itself (one record
   changed between two looks, mask_follow.h vv_roster_renamed_in_play).  But "VVFP Last Names.dll"
   gives New Believers' Heathens with no last name one as the village LOADS (the owner, 2026-11-08),
   before any owner has looked: many records at once, and every stored identity of theirs would match
   nobody -- a Heathen's custom title, mask or look would be lost, and with enough of them the file
   would no longer share a majority with the village and be taken for another village's (Codex, #733).

   HOW.  Right after it renames them, the Last Names companion hands each owner that is loaded the
   whole batch -- the records (with their new names) and the names they had -- through the owner's
   export VvfpVillagersRenamed(game, slot, count, records, old_names).  The owner works out, by its OWN
   identity, each villager's identity before (a copy of the record with the old name) and after, and:
     * keeps the pairs for the slot (vv_rekey_note), so the next time it reads the slot's file every
       stored identity that is a `from` reads as its `to` (vv_rekey_apply) -- before the village test,
       the follow and everything else;
     * carries what it already holds in memory for that slot the same way, and writes its file through
       its own atomic write (sidecar_io.h) when it may.
   NEVER A GUESS: a `from` two villagers of the batch shared (two Heathens called Tama, of one sex and
   no parents) goes to neither -- what was kept for it stays ambiguous, as it was.  A pair whose
   identities are equal (the identity does not hash the name) changes nothing.  Pairs chain (a later
   rename of a renamed villager), and a pair already kept is not kept twice, so the same batch
   delivered again at a later load (the Last Names companion repeats its load-time renames from its
   record, for an owner whose file a session never rewrote) changes nothing more.

   Header-only and static: each owner has its own table.  Nothing here touches a villager record. */
#ifndef VV_VILLAGER_REKEY_H
#define VV_VILLAGER_REKEY_H

#include <windows.h>
#include <string.h>

#define VV_REKEY_MAX 1024               /* pairs kept per owner, per process */
#define VV_REKEY_BATCH 256              /* villagers in one batch: every record */
#define VV_REKEY_RECORD_MAX 0xF000u     /* the largest record (The Lost Children's 0xE48C) */
#define VV_REKEY_NAME_MAX 64

typedef int (__stdcall *vv_rekey_export_fn)(int game, int slot, int count, const void *const *records,
                                           const char *const *old_names);

typedef struct {
    int slot;
    unsigned int from, to;
} vv_rekey_pair;

static vv_rekey_pair vv_rekeys[VV_REKEY_MAX];
static int vv_rekey_count;

/* `record` (stride bytes) as if it were called `name`: a copy, the name field (name_bytes at name_at)
   holding the name, zero-filled.  NULL when it does not fit. */
static const unsigned char *vv_rekey_as_named(const unsigned char *record, unsigned int stride, unsigned int name_at,
                                              unsigned int name_bytes, const char *name) {
    static unsigned char copy[VV_REKEY_RECORD_MAX];
    size_t n;
    if (record == NULL || name == NULL || stride == 0 || stride > sizeof copy || name_at + name_bytes > stride
        || (n = strlen(name)) == 0 || n >= name_bytes || n >= VV_REKEY_NAME_MAX) {
        return NULL;
    }
    memcpy(copy, record, stride);
    memset(copy + name_at, 0, name_bytes);
    memcpy(copy + name_at, name, n);
    return copy;
}

/* The identity `id` follows to through the slot's pairs (a chain followed to its end); `id` itself
   when no pair names it. */
static unsigned int vv_rekey_follow(int slot, unsigned int id) {
    int steps, i;
    for (steps = 0; steps < 16 && id != 0u; ++steps) {
        for (i = 0; i < vv_rekey_count; ++i) {
            if (vv_rekeys[i].slot == slot && vv_rekeys[i].from == id) {
                break;
            }
        }
        if (i == vv_rekey_count) {
            break;
        }
        id = vv_rekeys[i].to;
    }
    return id;
}

/* Each of `n` stored identities that a pair of the slot names read as where it leads.  Returns how
   many changed. */
static int vv_rekey_apply(int slot, unsigned int *ids, int n) {
    int i, changed = 0;
    if (slot <= 0 || vv_rekey_count == 0) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        unsigned int to = vv_rekey_follow(slot, ids[i]);
        if (to != ids[i]) {
            ids[i] = to;
            ++changed;
        }
    }
    return changed;
}

/* A batch's pairs (from[i] -> to[i], `n` of them) kept for the slot: a `from` two of them share is
   dropped from both, a pair with a 0 or with from == to is no pair, and one already kept is not kept
   again.  The pairs kept are left in from[] / to[] (the first *kept); returns how many. */
static int vv_rekey_note(int slot, unsigned int *from, unsigned int *to, int n) {
    int i, j, kept = 0;
    if (slot <= 0) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        int shared = 0;
        if (from[i] == 0u || to[i] == 0u || from[i] == to[i]) {
            continue;
        }
        for (j = 0; j < n; ++j) {
            if (j != i && from[j] == from[i]) {
                shared = 1;
            }
        }
        if (shared) {
            continue;                   /* two villagers were this identity: nothing is guessed */
        }
        for (j = 0; j < vv_rekey_count; ++j) {
            if (vv_rekeys[j].slot == slot && vv_rekeys[j].from == from[i]) {
                break;
            }
        }
        if (j == vv_rekey_count) {
            if (vv_rekey_count == VV_REKEY_MAX) {
                memmove(vv_rekeys, vv_rekeys + 1, (VV_REKEY_MAX - 1) * sizeof vv_rekeys[0]);
                --vv_rekey_count;
            }
            vv_rekeys[vv_rekey_count].slot = slot;
            vv_rekeys[vv_rekey_count].from = from[i];
            vv_rekeys[vv_rekey_count].to = to[i];
            ++vv_rekey_count;
        } else if (vv_rekeys[j].to != to[i]) {
            vv_rekeys[j].to = to[i];   /* the latest word on it */
        }
        from[kept] = from[i];
        to[kept] = to[i];
        ++kept;
    }
    return kept;
}

/* Start Over in the slot: its pairs are the erased village's. */
static void vv_rekey_forget(int slot) {
    int i, kept = 0;
    for (i = 0; i < vv_rekey_count; ++i) {
        if (vv_rekeys[i].slot != slot) {
            vv_rekeys[kept++] = vv_rekeys[i];
        }
    }
    vv_rekey_count = kept;
}

/* Every pair of a batch, by the owner's identity `identity` (of a record at `stride` with its name at
   name_at, name_bytes): from[] the identity with the old name, to[] with the name the record has now.
   Returns how many villagers the batch had (`count`, at most VV_REKEY_BATCH); a record or name that is
   not usable gives the pair 0 -> 0. */
typedef unsigned int (*vv_rekey_identity_fn)(const unsigned char *record);

static int vv_rekey_pairs(int count, const void *const *records, const char *const *old_names,
                          vv_rekey_identity_fn identity, unsigned int stride, unsigned int name_at,
                          unsigned int name_bytes, unsigned int *from, unsigned int *to) {
    int i;
    if (records == NULL || old_names == NULL || count <= 0) {
        return 0;
    }
    if (count > VV_REKEY_BATCH) {
        count = VV_REKEY_BATCH;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *record = (const unsigned char *)records[i];
        const unsigned char *before = vv_rekey_as_named(record, stride, name_at, name_bytes, old_names[i]);
        from[i] = to[i] = 0u;
        if (before != NULL) {
            from[i] = identity(before);
            to[i] = identity(record);
        }
    }
    return count;
}

#endif /* VV_VILLAGER_REKEY_H */
