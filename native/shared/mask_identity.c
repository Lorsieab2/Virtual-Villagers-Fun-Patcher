/* Implementation of the additive mask-distribution identity safeguard.
 *
 * Address-free by construction: this file names no game address and no record
 * offset.  Everything build-specific arrives in the vv_identity_adapter, which
 * data/mask_identity_adapters.json documents field by field with the evidence
 * that establishes it.  That is what lets the same object code run inside a
 * 32-bit game companion DLL and inside the 64-bit test harness.
 *
 * Freestanding: no libc, no allocation, no floating point.  The game companions
 * are injected into a running process, so the module must not pull in a CRT.
 */
#include "mask_identity.h"

/* ------------------------------------------------------------------ hashing */

#define VV_FNV_OFFSET 2166136261u
#define VV_FNV_PRIME  16777619u

static unsigned int vv_hash_byte(unsigned int h, unsigned char b)
{
    h ^= (unsigned int)b;
    h *= VV_FNV_PRIME;
    return h;
}

static unsigned int vv_hash_u32(unsigned int h, unsigned int v)
{
    h = vv_hash_byte(h, (unsigned char)(v & 0xFFu));
    h = vv_hash_byte(h, (unsigned char)((v >> 8) & 0xFFu));
    h = vv_hash_byte(h, (unsigned char)((v >> 16) & 0xFFu));
    h = vv_hash_byte(h, (unsigned char)((v >> 24) & 0xFFu));
    return h;
}

/* ------------------------------------------------------- record field access */

static const unsigned char *vv_record_at(const vv_identity_adapter *a, int slot)
{
    return a->base + (unsigned int)slot * a->stride;
}

static unsigned char vv_read_u8(const unsigned char *rec, unsigned int off)
{
    return rec[off];
}

static int vv_read_i32(const unsigned char *rec, unsigned int off)
{
    /* Byte-wise so the module never assumes the host's alignment rules. */
    unsigned int v = (unsigned int)rec[off]
                   | ((unsigned int)rec[off + 1] << 8)
                   | ((unsigned int)rec[off + 2] << 16)
                   | ((unsigned int)rec[off + 3] << 24);
    return (int)v;
}

/* Mix one declared field into `h`.  An absent field contributes NOTHING -- not
 * even a marker -- so that adding evidence for a field later changes the
 * fingerprint of every villager uniformly rather than only of some. */
static unsigned int vv_hash_field(unsigned int h,
                                  const unsigned char *rec,
                                  const vv_identity_field *f,
                                  unsigned int tag)
{
    int i;
    int count;

    if (!f->present) {
        return h;
    }

    /* The tag keeps field boundaries meaningful: two different fields holding
     * the same value must not produce the same contribution. */
    h = vv_hash_u32(h, tag);

    count = f->count > 0 ? f->count : 1;

    if (f->kind == VV_FIELD_STR) {
        if (count > VV_IDENTITY_MAX_NAME) {
            count = VV_IDENTITY_MAX_NAME;
        }
        /* No separate length is mixed in: the next thing hashed is always the
         * following field's tag, so a short name cannot run into its
         * neighbour.  Bytes past the terminator are ignored, which is what the
         * game shows the player. */
        for (i = 0; i < count; ++i) {
            unsigned char c = vv_read_u8(rec, f->offset + (unsigned int)i);
            if (c == 0) {
                break;
            }
            h = vv_hash_byte(h, c);
        }
        return h;
    }

    if (f->kind == VV_FIELD_U8) {
        if (count > VV_IDENTITY_MAX_ARRAY) {
            count = VV_IDENTITY_MAX_ARRAY;
        }
        for (i = 0; i < count; ++i) {
            h = vv_hash_byte(h, vv_read_u8(rec, f->offset + (unsigned int)i));
        }
        return h;
    }

    /* VV_FIELD_I32 */
    if (count > VV_IDENTITY_MAX_ARRAY) {
        count = VV_IDENTITY_MAX_ARRAY;
    }
    for (i = 0; i < count; ++i) {
        h = vv_hash_u32(h,
                        (unsigned int)vv_read_i32(rec,
                                                  f->offset + (unsigned int)i * 4u));
    }
    return h;
}

/* --------------------------------------------------------------- classifiers */

static int vv_slot_is_live(const vv_identity_adapter *a, const unsigned char *rec)
{
    /* An adapter with no proven `active` field cannot tell a villager from an
     * empty slot, so it treats nothing as live.  Such an adapter should be
     * disabled outright; this is the belt-and-braces half of that. */
    if (!a->active.present) {
        return 0;
    }
    if (vv_read_u8(rec, a->active.offset) == 0) {
        return 0;
    }
    if (a->dead.present && vv_read_u8(rec, a->dead.offset) != 0) {
        return 0;
    }
    return 1;
}

static int vv_slot_is_special(const vv_identity_adapter *a, const unsigned char *rec)
{
    switch (a->special.kind) {
    case VV_SPECIAL_RECORD_POINTER:
        /* The global legitimately holds 0 for "no such villager".  No explicit
         * null test is needed -- vv_check_adapter has already refused a null
         * base, so `rec` is never 0 and a null global matches nobody. */
        return a->special.pointer == rec;
    case VV_SPECIAL_RECORD_FLAG:
        return vv_read_u8(rec, a->special.offset) != 0;
    case VV_SPECIAL_RECORD_RANK:
        return vv_read_i32(rec, a->special.offset) == a->special.value;
    case VV_SPECIAL_NONE:
    default:
        return 0;
    }
}

static unsigned int vv_fingerprint(const vv_identity_adapter *a,
                                   const unsigned char *rec)
{
    unsigned int h = VV_FNV_OFFSET;

    /* Fixed order.  Each field carries a distinct tag, so reordering this list
     * would change every fingerprint but never make two fields interchangeable. */
    h = vv_hash_field(h, rec, &a->name,            1u);
    h = vv_hash_field(h, rec, &a->health,          2u);
    h = vv_hash_field(h, rec, &a->age,             3u);
    h = vv_hash_field(h, rec, &a->gender,          4u);
    h = vv_hash_field(h, rec, &a->head,            5u);
    h = vv_hash_field(h, rec, &a->body,            6u);
    h = vv_hash_field(h, rec, &a->nursing,         7u);
    h = vv_hash_field(h, rec, &a->skills,          8u);
    h = vv_hash_field(h, rec, &a->preferred_skill, 9u);
    h = vv_hash_field(h, rec, &a->likes,          10u);
    h = vv_hash_field(h, rec, &a->dislikes,       11u);
    return h;
}

static vv_identity_status vv_check_adapter(const vv_identity_adapter *a)
{
    if (a == 0) {
        return VV_IDENTITY_BAD_ARGUMENT;
    }
    if (!a->enabled) {
        return VV_IDENTITY_ADAPTER_DISABLED;
    }
    if (a->base == 0 || a->stride == 0 || a->count <= 0) {
        return VV_IDENTITY_BAD_ARGUMENT;
    }
    if (a->count > VV_IDENTITY_MAX_SLOTS) {
        return VV_IDENTITY_TOO_MANY_SLOTS;
    }
    return VV_IDENTITY_OK;
}

/* --------------------------------------------------------------- public API */

vv_identity_status vv_identity_snapshot_build(const vv_identity_adapter *adapter,
                                              const unsigned char *mask_table,
                                              vv_identity_snapshot *out)
{
    vv_identity_status status;
    unsigned int signature = VV_FNV_OFFSET;
    int slot;

    if (out == 0) {
        return VV_IDENTITY_BAD_ARGUMENT;
    }

    status = vv_check_adapter(adapter);
    if (status != VV_IDENTITY_OK) {
        return status;
    }

    out->count = adapter->count;
    out->live_count = 0;
    out->candidate_count = 0;

    for (slot = 0; slot < adapter->count; ++slot) {
        const unsigned char *rec = vv_record_at(adapter, slot);
        vv_identity_entry *e = &out->entries[slot];

        e->slot = slot;
        e->live = vv_slot_is_live(adapter, rec);
        e->special = e->live ? vv_slot_is_special(adapter, rec) : 0;
        e->already_masked = (mask_table != 0 && mask_table[slot] != 0) ? 1 : 0;
        e->fingerprint = e->live ? vv_fingerprint(adapter, rec) : 0u;

        if (e->live) {
            out->live_count += 1;
            if (!e->special && !e->already_masked) {
                out->candidate_count += 1;
            }
        }

        /* Signature covers membership AND identity AND mask state, so any of
         * the three changing tells the caller to rebuild (requirement 1).
         *
         * Liveness is not hashed separately: a slot that is not live
         * contributes fingerprint 0 above, so arriving and departing villagers
         * already move the signature. */
        signature = vv_hash_u32(signature, (unsigned int)slot);
        signature = vv_hash_byte(signature, (unsigned char)e->special);
        signature = vv_hash_byte(signature, (unsigned char)e->already_masked);
        signature = vv_hash_u32(signature, e->fingerprint);
    }

    /* Slots beyond the adapter's count are not part of the village. */
    for (slot = adapter->count; slot < VV_IDENTITY_MAX_SLOTS; ++slot) {
        vv_identity_entry *e = &out->entries[slot];
        e->slot = slot;
        e->live = 0;
        e->special = 0;
        e->already_masked = 0;
        e->fingerprint = 0u;
    }

    out->village_signature = signature;
    return VV_IDENTITY_OK;
}

int vv_identity_snapshot_is_stale(const vv_identity_adapter *adapter,
                                  const unsigned char *mask_table,
                                  const vv_identity_snapshot *previous)
{
    vv_identity_snapshot now;

    if (previous == 0) {
        return 1;
    }
    if (vv_identity_snapshot_build(adapter, mask_table, &now) != VV_IDENTITY_OK) {
        /* If the village cannot even be read, the old snapshot is not usable. */
        return 1;
    }
    if (now.count != previous->count) {
        return 1;
    }
    return now.village_signature != previous->village_signature ? 1 : 0;
}

int vv_identity_is_candidate(const vv_identity_snapshot *snapshot, int slot)
{
    const vv_identity_entry *e;

    if (snapshot == 0 || slot < 0 || slot >= snapshot->count) {
        return 0;
    }
    e = &snapshot->entries[slot];
    return (e->live && !e->special && !e->already_masked) ? 1 : 0;
}

/* Re-locate one planned villager in the village as it stands now.
 *
 * Returns the resolved slot, or a negative marker:
 *   -1  not present any more            -> VV_IDENTITY_STALE_SNAPSHOT
 *   -2  two candidates cannot be told apart -> VV_IDENTITY_AMBIGUOUS
 * On -2 the two offending slots are written to *a_out / *b_out. */
static int vv_resolve_slot(const vv_identity_snapshot *now,
                           unsigned int fingerprint,
                           int original_slot,
                           int *a_out,
                           int *b_out)
{
    int matches = 0;
    int first = -1;
    int second = -1;
    int slot;

    for (slot = 0; slot < now->count; ++slot) {
        const vv_identity_entry *e = &now->entries[slot];
        if (!e->live || e->fingerprint != fingerprint) {
            continue;
        }
        matches += 1;
        if (first < 0) {
            first = slot;
        } else if (second < 0) {
            second = slot;
        }
    }

    if (matches == 0) {
        return -1;
    }
    if (matches == 1) {
        return first;
    }

    /* Several villagers share every captured field.  The stable record key is
     * the tie-breaker: if the planned villager is still sitting in its own
     * slot, that is the one meant. */
    if (original_slot >= 0 && original_slot < now->count) {
        const vv_identity_entry *e = &now->entries[original_slot];
        if (e->live && e->fingerprint == fingerprint) {
            return original_slot;
        }
    }

    /* Indistinguishable twins AND the planned one has moved: there is no
     * evidence left that says which is which.  Refuse rather than guess. */
    if (a_out != 0) {
        *a_out = first;
    }
    if (b_out != 0) {
        *b_out = second;
    }
    return -2;
}

vv_identity_status vv_identity_preflight(const vv_identity_adapter *adapter,
                                         const unsigned char *mask_table,
                                         const vv_identity_snapshot *snapshot,
                                         const int *plan_slots,
                                         const unsigned char *plan_masks,
                                         int plan_count,
                                         int *resolved_slots,
                                         int *collision_a,
                                         int *collision_b)
{
    vv_identity_snapshot now;
    vv_identity_status status;
    int scratch[VV_IDENTITY_MAX_SLOTS];
    unsigned char taken[VV_IDENTITY_MAX_SLOTS];
    int i;

    if (snapshot == 0 || plan_slots == 0 || plan_masks == 0) {
        return VV_IDENTITY_BAD_ARGUMENT;
    }
    if (plan_count < 0) {
        return VV_IDENTITY_BAD_ARGUMENT;
    }
    if (plan_count > VV_IDENTITY_MAX_SLOTS) {
        return VV_IDENTITY_TOO_MANY_SLOTS;
    }

    status = vv_check_adapter(adapter);
    if (status != VV_IDENTITY_OK) {
        return status;
    }

    /* Validate against the village as it is RIGHT NOW, not against the
     * caller's possibly-stale copy. */
    status = vv_identity_snapshot_build(adapter, mask_table, &now);
    if (status != VV_IDENTITY_OK) {
        return status;
    }
    if (now.count != snapshot->count) {
        return VV_IDENTITY_STALE_SNAPSHOT;
    }

    for (i = 0; i < VV_IDENTITY_MAX_SLOTS; ++i) {
        taken[i] = 0;
        scratch[i] = -1;
    }

    for (i = 0; i < plan_count; ++i) {
        int planned = plan_slots[i];
        const vv_identity_entry *was;
        int resolved;

        if (planned < 0 || planned >= snapshot->count) {
            return VV_IDENTITY_PLAN_OUT_OF_RANGE;
        }

        was = &snapshot->entries[planned];
        if (!was->live) {
            return VV_IDENTITY_PLAN_TARGETS_DEAD;
        }
        if (was->special) {
            return VV_IDENTITY_PLAN_TARGETS_SPECIAL;
        }
        if (was->already_masked) {
            return VV_IDENTITY_PLAN_TARGETS_MASKED;
        }
        /* A mask value of 0 would be a no-op write; treat it as a malformed
         * plan rather than silently skipping it. */
        if (plan_masks[i] == 0) {
            return VV_IDENTITY_BAD_ARGUMENT;
        }

        resolved = vv_resolve_slot(&now, was->fingerprint, planned,
                                   collision_a, collision_b);
        if (resolved == -1) {
            return VV_IDENTITY_STALE_SNAPSHOT;
        }
        if (resolved == -2) {
            return VV_IDENTITY_AMBIGUOUS;
        }

        /* The rules are re-checked at the RESOLVED record, because that is the
         * one that would actually be written. */
        if (!now.entries[resolved].live) {
            return VV_IDENTITY_PLAN_TARGETS_DEAD;
        }
        if (now.entries[resolved].special) {
            return VV_IDENTITY_PLAN_TARGETS_SPECIAL;
        }
        if (now.entries[resolved].already_masked) {
            return VV_IDENTITY_PLAN_TARGETS_MASKED;
        }
        if (taken[resolved]) {
            return VV_IDENTITY_PLAN_DUPLICATE_SLOT;
        }

        taken[resolved] = 1;
        scratch[i] = resolved;
    }

    /* Everything resolved.  Only now is anything handed back, so a rejected
     * plan leaves the caller with no partial mapping to apply. */
    if (resolved_slots != 0) {
        for (i = 0; i < plan_count; ++i) {
            resolved_slots[i] = scratch[i];
        }
    }
    return VV_IDENTITY_OK;
}
