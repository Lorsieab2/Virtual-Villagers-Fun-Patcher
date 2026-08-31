/* Additive identity safeguard for village-wide mask distribution (VV1-VV5).
 *
 * WHAT THIS IS FOR
 * ----------------
 * A village-wide mask distribution has to decide which villager receives which
 * mask.  If two villagers cannot be told apart, a plan can attach a mask to the
 * wrong record.  This module builds a patch-owned snapshot of the village,
 * fingerprints each villager from EXACT, PER-BUILD VERIFIED record fields, and
 * refuses to apply a plan it cannot resolve uniquely.
 *
 * WHAT THIS IS NOT
 * ----------------
 * It is not a planner.  It does not choose masks, quotas, ordering, or random
 * values, and it never writes a villager record, a mask table, a sidecar, or a
 * tech-point balance.  The caller keeps its existing planner; this module only
 * answers "is this plan safe to apply, and to which records?".  When an adapter
 * is disabled the caller must run exactly the code it runs today.
 *
 * DESIGN RULES
 * ------------
 *  - Address-free.  Every game-specific address and offset arrives in a
 *    vv_identity_adapter supplied by the caller, so this file compiles
 *    unchanged into a 32-bit game companion and into a 64-bit test harness.
 *  - Offsets are never guessed.  A field the caller cannot prove is left out of
 *    the adapter (present = 0) and simply does not contribute to identity.
 *  - Two phase.  vv_identity_preflight() validates everything and writes
 *    nothing.  Only if it returns VV_IDENTITY_OK may the caller apply its plan,
 *    and then only to the records named in `resolved_slots`.
 *  - Fail closed.  Any ambiguity, capacity problem, or malformed input aborts
 *    the whole distribution rather than assigning a partially-resolved plan.
 */
#ifndef VV_MASK_IDENTITY_H
#define VV_MASK_IDENTITY_H

#define VV_IDENTITY_MAX_SLOTS 256
#define VV_IDENTITY_MAX_ARRAY 64      /* per-field array cap (VV2 likes = 62) */
#define VV_IDENTITY_MAX_NAME  66      /* per-build name cap (VV2 = 66) */

/* Result codes.  Anything other than VV_IDENTITY_OK means the caller must
 * abandon the distribution and leave masks, sidecars, saves and tech points
 * exactly as they were. */
typedef enum {
    VV_IDENTITY_OK = 0,
    VV_IDENTITY_ADAPTER_DISABLED,     /* no proven evidence: use the native planner */
    VV_IDENTITY_BAD_ARGUMENT,
    VV_IDENTITY_TOO_MANY_SLOTS,
    VV_IDENTITY_AMBIGUOUS,            /* two live villagers cannot be separated */
    VV_IDENTITY_PLAN_OUT_OF_RANGE,    /* plan names a slot outside the snapshot */
    VV_IDENTITY_PLAN_TARGETS_MASKED,  /* plan would overwrite an existing mask */
    VV_IDENTITY_PLAN_TARGETS_SPECIAL, /* plan would touch a protected villager */
    VV_IDENTITY_PLAN_DUPLICATE_SLOT,  /* plan names the same villager twice */
    VV_IDENTITY_PLAN_TARGETS_DEAD,    /* plan names a slot that holds no villager */
    VV_IDENTITY_STALE_SNAPSHOT        /* a planned villager is no longer in the village */
} vv_identity_status;

/* How to read a record field.  Needed because the same struct describes a
 * status byte, a 32-bit counter, an array of counters and a name buffer. */
typedef enum {
    VV_FIELD_U8 = 0,
    VV_FIELD_I32,
    VV_FIELD_STR                      /* NUL-terminated, hashed up to `count` */
} vv_field_kind;

/* One record field.  `present` is 0 when the build has no proven offset for it,
 * in which case the field contributes nothing to the fingerprint. */
typedef struct {
    int present;
    unsigned int offset;
    vv_field_kind kind;
    int count;                        /* elements for arrays/strings, else 1 */
} vv_identity_field;

typedef enum {
    VV_SPECIAL_NONE = 0,
    VV_SPECIAL_RECORD_POINTER,        /* VV1 Golden Child: global holds the record */
    VV_SPECIAL_RECORD_FLAG,           /* VV3 Tribal Chief: record byte != 0 */
    VV_SPECIAL_RECORD_RANK            /* VV5 Retired Chief: record int == value */
} vv_special_kind;

typedef struct {
    vv_special_kind kind;
    unsigned int offset;              /* for FLAG / RANK */
    int value;                        /* for RANK */
    const unsigned char *pointer;     /* for POINTER (already dereferenced) */
} vv_identity_special;

typedef struct {
    int enabled;                      /* 0 => caller must use the native planner */
    const unsigned char *base;        /* first villager record */
    unsigned int stride;
    int count;                        /* slots to scan */

    /* Liveness.  A slot holds a villager when `active` is non-zero and `dead`
     * (when the build proves one) is zero.  Health is deliberately NOT a
     * liveness test: no build establishes which health value means "dead", so
     * health is treated purely as an identity contributor below. */
    vv_identity_field active;
    vv_identity_field dead;

    /* Identity contributors.  Any of these may be absent. */
    vv_identity_field name;
    vv_identity_field health;
    vv_identity_field age;
    vv_identity_field gender;
    vv_identity_field head;
    vv_identity_field body;
    vv_identity_field nursing;
    vv_identity_field skills;
    vv_identity_field preferred_skill;
    vv_identity_field likes;
    vv_identity_field dislikes;

    vv_identity_special special;
} vv_identity_adapter;

/* One snapshot row.  `slot` is the stable native record index and is the
 * tie-breaker of last resort. */
typedef struct {
    int slot;
    int live;
    int special;                      /* protected: never a distribution target */
    int already_masked;
    unsigned int fingerprint;         /* visible-field hash, NOT unique by itself */
} vv_identity_entry;

typedef struct {
    int count;
    int live_count;
    int candidate_count;              /* live, not special, not already masked */
    unsigned int village_signature;   /* changes when membership or identity changes */
    vv_identity_entry entries[VV_IDENTITY_MAX_SLOTS];
} vv_identity_snapshot;

/* Build a snapshot.  Reads only; writes nothing but `out`.
 * `mask_table` may be NULL, in which case no villager is treated as masked. */
vv_identity_status vv_identity_snapshot_build(
    const vv_identity_adapter *adapter,
    const unsigned char *mask_table,  /* one byte per slot, 0 = no mask */
    vv_identity_snapshot *out);

/* True when the village has changed since `previous` was taken, so the caller
 * knows to rebuild.  Membership changes and any tracked identity change both
 * move the signature. */
int vv_identity_snapshot_is_stale(
    const vv_identity_adapter *adapter,
    const unsigned char *mask_table,
    const vv_identity_snapshot *previous);

/* Phase one.  Validates the plan against the village as it stands RIGHT NOW and
 * writes nothing.  `plan_slots[i]` names the snapshot slot the caller chose and
 * `plan_masks[i]` the mask it chose for it.
 *
 * Each planned villager is re-located in the current village by fingerprint,
 * with the record slot as the tie-breaker, so a villager that merely moved
 * record slots (save/reload compaction) still resolves.  The record it resolves
 * to is written to `resolved_slots[i]`, and the caller must apply the mask
 * THERE rather than at `plan_slots[i]`.
 *
 * On VV_IDENTITY_AMBIGUOUS, *collision_a and *collision_b receive the two
 * offending record slots so the caller can report precisely which villagers
 * could not be separated.  All out-params may be NULL.
 *
 * Nothing is written to `resolved_slots` unless the return value is
 * VV_IDENTITY_OK, so a rejected plan cannot be half-applied. */
vv_identity_status vv_identity_preflight(
    const vv_identity_adapter *adapter,
    const unsigned char *mask_table,
    const vv_identity_snapshot *snapshot,
    const int *plan_slots,
    const unsigned char *plan_masks,
    int plan_count,
    int *resolved_slots,
    int *collision_a,
    int *collision_b);

/* Convenience: is this slot an eligible distribution target?  Mirrors the rule
 * preflight enforces, for callers that want to filter before planning. */
int vv_identity_is_candidate(const vv_identity_snapshot *snapshot, int slot);

#endif /* VV_MASK_IDENTITY_H */
