/* New Believers' former Heathens: who was converted, and which mask they
   wore (native/shared/former_heathens.h has the file and why the game cannot
   say it).  Included by vvfp_cause_of_death.c, after cod_backfill.inc
   (cod_data_path) and before cod_arrivals.inc, whose tick sees the
   conversions.

   While the tick sees a record as a Heathen it keeps the mask that Heathen
   wears (vv_former_kind_of: the game's own mask choice, 0x4728C6); the tick
   that sees the same villager a believer -- the conversion 0x4668B0, or any
   other path through the faction setter 0x466880 -- files that mask for
   the villager's identity in the slot's Former Heathens file.  A Heathen the
   tick never saw as one (converted before this build ran) is not filed:
   Repair Logs asks the player about those. */

static signed char former_kind_seen[RECORDS_MAX];   /* -1: not seen as a Heathen */
static int former_ready;

static struct {
    int slot;
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} former;

static unsigned char former_buffer[VV_FORMER_FILE_MAX];

static int former_validate(const unsigned char *data, DWORD length, void *context) {
    (void)context;
    return vv_former_validate(data, length);
}

/* New Believers' record: the identity custom titles and former Heathens are
   kept by (custom_titles.h: name, likes, dislikes). */
#define FORMER_NAME 0x1B9Cu
#define FORMER_NAME_CAP 0x19u
#define FORMER_LIKES 0x1F5Cu
#define FORMER_DISLIKES 0x1F68u
#define FORMER_SLOTS 3u

/* File `kind` for the villager in `record`, replacing any entry of the same
   identity; the oldest entry gives way when the file is full. */
static void former_file(const unsigned char *record, int kind) {
    int slot = cod_slot();
    DWORD length = 0;
    int result;
    unsigned int count = 0, kept = 0, i, identity;
    const void *parts[1];
    DWORD sizes[1];
    if (slot <= 0 || kind < VV_FORMER_BLUE || kind > VV_FORMER_CHIEF) {
        return;
    }
    if (slot != former.slot) {
        former.slot = slot;
        former.path[0] = '\0';
        vv_sidecar_gate_bind(&former.gate, 0x300 + slot);
    }
    if (former.path[0] == '\0' && !cod_data_path(former.path, "Former Heathens", "Former Heathens", slot)) {
        return;
    }
    result = vv_sidecar_load(&former.gate, former.path, former_buffer, sizeof former_buffer, &length,
                             former_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;
    }
    if (result == VV_SIDECAR_LOAD_VALID) {
        count = vv_former_u32(former_buffer + 12);
    }
    identity = vv_title_identity(record, FORMER_NAME, FORMER_NAME_CAP, FORMER_LIKES, FORMER_DISLIKES,
                                 FORMER_SLOTS);
    for (i = 0; i < count; ++i) {
        unsigned char *e = former_buffer + VV_FORMER_HEADER + i * VV_FORMER_ENTRY;
        if (vv_former_u32(e) == identity) {
            continue;
        }
        memmove(former_buffer + VV_FORMER_HEADER + kept * VV_FORMER_ENTRY, e, VV_FORMER_ENTRY);
        ++kept;
    }
    if (kept == VV_FORMER_MAX) {
        memmove(former_buffer + VV_FORMER_HEADER, former_buffer + VV_FORMER_HEADER + VV_FORMER_ENTRY,
                (VV_FORMER_MAX - 1) * VV_FORMER_ENTRY);
        --kept;
    }
    memcpy(former_buffer + VV_FORMER_HEADER + kept * VV_FORMER_ENTRY, &identity, 4);
    memcpy(former_buffer + VV_FORMER_HEADER + kept * VV_FORMER_ENTRY + 4, &kind, 4);
    ++kept;
    ((unsigned int *)former_buffer)[0] = VV_FORMER_MAGIC;
    ((unsigned int *)former_buffer)[1] = VV_FORMER_VERSION;
    ((unsigned int *)former_buffer)[2] = 5u;
    ((unsigned int *)former_buffer)[3] = kept;
    parts[0] = former_buffer;
    sizes[0] = VV_FORMER_HEADER + kept * VV_FORMER_ENTRY;
    (void)vv_sidecar_publish(&former.gate, former.path, parts, sizes, 1);
}

/* The tick's view of record `index`: `heathen` as it is now, `was_heathen`
   as the last tick saw it (faction_seen). */
static void former_tick(int index, const unsigned char *record, int heathen, int was_heathen) {
    if (!former_ready) {
        memset(former_kind_seen, -1, sizeof former_kind_seen);
        former_ready = 1;
    }
    if (heathen) {
        former_kind_seen[index] = (signed char)vv_former_kind_of(record);
        return;
    }
    if (was_heathen == 1 && former_kind_seen[index] >= 0) {
        former_file(record, former_kind_seen[index]);
    }
    former_kind_seen[index] = -1;
}

static void former_forget(int index) {
    if (former_ready && index >= 0 && index < RECORDS_MAX) {
        former_kind_seen[index] = -1;
    }
}

static void former_reset(int slot) {
    if (slot == former.slot) {
        vv_sidecar_gate_bind(&former.gate, -1);
        former.slot = 0;
        former.path[0] = '\0';
    }
    if (former_ready) {
        memset(former_kind_seen, -1, sizeof former_kind_seen);
    }
}
