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
   Repair Saves & Logs asks the player about those. */

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

/* EVERY CHANGE REACHES THE FILE (the identity audit, case 7).  The file is the only place a former
   Heathen is kept, and a conversion or a rename the tick saw while the file could not be read or
   written (another program holding it, a read error, the retry window after one) was dropped: the
   rename was never carried, the entry stayed under the old name, and the villager was no longer
   called a Former Heathen.  So each change is queued, in order, and applied once the file can be
   read and written; a queued change is dropped only by Start Over (former_reset). */
enum { FORMER_OP_FILE = 1, FORMER_OP_REKEY = 2, FORMER_OP_UNSURE = 3 };
struct former_op {
    int slot;
    int op;
    unsigned int a, b;          /* FILE: identity, kind; REKEY / UNSURE: from, to */
};
/* NOTHING QUEUED IS EVER DROPPED (Codex, #601): the queue grows for as long as the file stays locked
   -- every change waits, in order, for the file to take it.  It starts in this companion's own memory
   and moves to the process heap past that. */
#define FORMER_PENDING_START 64
static struct former_op former_pending_first[FORMER_PENDING_START];
static struct former_op *former_pending = former_pending_first;
static int former_pending_capacity = FORMER_PENDING_START;
static int former_pending_count;

static int former_bind(int slot);

/* Room for one more queued change: 1, or 0 only when the process has no memory left to give. */
static int former_pending_room(void) {
    struct former_op *grown;
    int capacity;
    if (former_pending_count < former_pending_capacity) {
        return 1;
    }
    capacity = former_pending_capacity * 2;
    grown = (struct former_op *)HeapAlloc(GetProcessHeap(), 0, sizeof(struct former_op) * (size_t)capacity);
    if (grown == NULL) {
        return 0;
    }
    memcpy(grown, former_pending, sizeof(struct former_op) * (size_t)former_pending_count);
    if (former_pending != former_pending_first) {
        HeapFree(GetProcessHeap(), 0, former_pending);
    }
    former_pending = grown;
    former_pending_capacity = capacity;
    return 1;
}

static void former_queue(int op, unsigned int a, unsigned int b) {
    int slot = cod_slot();
    if (slot <= 0) {
        return;
    }
    if (!former_pending_room()) {
        /* No memory left in the process (never seen): two renames of one villager in a row are one
           rename -- from her first name to her last -- so the chain is shortened rather than any
           change lost. */
        int k;
        for (k = former_pending_count - 1; k >= 0; --k) {
            if (former_pending[k].slot == slot && former_pending[k].op == FORMER_OP_REKEY && op == FORMER_OP_REKEY
                && former_pending[k].b == a) {
                former_pending[k].b = b;
                return;
            }
        }
        return;                       /* the process is out of memory: nothing more can be kept */
    }
    former_pending[former_pending_count].slot = slot;
    former_pending[former_pending_count].op = op;
    former_pending[former_pending_count].a = a;
    former_pending[former_pending_count].b = b;
    ++former_pending_count;
}

/* Append (identity, kind) to the loaded buffer of `count` entries; the oldest gives way when full. */
static unsigned int former_append(unsigned int count, unsigned int identity, unsigned int kind) {
    if (count == VV_FORMER_MAX) {
        memmove(former_buffer + VV_FORMER_HEADER, former_buffer + VV_FORMER_HEADER + VV_FORMER_ENTRY,
                (VV_FORMER_MAX - 1) * VV_FORMER_ENTRY);
        --count;
    }
    memcpy(former_buffer + VV_FORMER_HEADER + count * VV_FORMER_ENTRY, &identity, 4);
    memcpy(former_buffer + VV_FORMER_HEADER + count * VV_FORMER_ENTRY + 4, &kind, 4);
    return count + 1;
}

/* One queued change applied to the loaded file of `count` entries; returns the new count. */
static unsigned int former_apply_one(int op, unsigned int a, unsigned int b, unsigned int count) {
    unsigned int i, kept = 0;
    if (op == FORMER_OP_FILE) {
        /* The conversion: (identity a, kind b), replacing any entry of the same identity. */
        for (i = 0; i < count; ++i) {
            unsigned char *e = former_buffer + VV_FORMER_HEADER + i * VV_FORMER_ENTRY;
            if (vv_former_u32(e) == a) {
                continue;
            }
            memmove(former_buffer + VV_FORMER_HEADER + kept * VV_FORMER_ENTRY, e, VV_FORMER_ENTRY);
            ++kept;
        }
        return former_append(kept, a, b);
    }
    if (op == FORMER_OP_REKEY) {
        /* A rename or a change in place: every entry of identity a carried to b. */
        for (i = 0; i < count; ++i) {
            unsigned char *e = former_buffer + VV_FORMER_HEADER + i * VV_FORMER_ENTRY;
            if (vv_former_u32(e) == a) {
                memcpy(e, &b, 4);
            }
        }
        return count;
    }
    {
        /* FORMER_OP_UNSURE: identity a was carried by two villagers at once (one name, likes and
           dislikes -- an identity the readers already call nobody's) and one of them changed to
           b.  Which of the two the entry was for is not known, so nobody is given it: both
           identities are left carried by two entries -- nobody's (vv_former_lookup) -- and Repair
           Saves & Logs asks the player, as for any former Heathen the file cannot name. */
        unsigned int kind = 0, from = 0, to = 0;
        for (i = 0; i < count; ++i) {
            const unsigned char *e = former_buffer + VV_FORMER_HEADER + i * VV_FORMER_ENTRY;
            if (vv_former_u32(e) == a) {
                if (from++ == 0) {
                    kind = vv_former_u32(e + 4);
                }
            }
            to += vv_former_u32(e) == b;
        }
        if (from == 0) {
            return count;             /* neither of them was filed */
        }
        for (; from < 2; ++from) {
            count = former_append(count, a, kind);
        }
        for (; to < 2; ++to) {
            count = former_append(count, b, kind);
        }
        return count;
    }
}

/* Apply what is queued, in order -- each change to the file of the slot it was seen in -- while
   the file can be read and written. */
static void former_apply(void) {
    while (former_pending_count > 0) {
        DWORD length = 0;
        int result, k = 0, done = 0;
        int slot = former_pending[0].slot;
        unsigned int count = 0;
        const void *parts[1];
        DWORD sizes[1];
        if (!former_bind(slot)) {
            return;
        }
        result = vv_sidecar_load(&former.gate, former.path, former_buffer, sizeof former_buffer, &length,
                                 former_validate, NULL);
        if (result == VV_SIDECAR_LOAD_BLOCKED) {
            return;                   /* tried again at a later frame */
        }
        if (result == VV_SIDECAR_LOAD_VALID) {
            count = vv_former_u32(former_buffer + 12);
        }
        /* Every queued change for this slot, in one write. */
        while (k < former_pending_count && former_pending[k].slot == slot) {
            if (former_pending[k].op != FORMER_OP_FILE && count == 0) {
                ++k;                  /* nothing filed to carry */
                continue;
            }
            count = former_apply_one(former_pending[k].op, former_pending[k].a, former_pending[k].b, count);
            ++k;
            done = 1;
        }
        if (done) {
            ((unsigned int *)former_buffer)[0] = VV_FORMER_MAGIC;
            ((unsigned int *)former_buffer)[1] = VV_FORMER_VERSION;
            ((unsigned int *)former_buffer)[2] = 5u;
            ((unsigned int *)former_buffer)[3] = count;
            parts[0] = former_buffer;
            sizes[0] = VV_FORMER_HEADER + count * VV_FORMER_ENTRY;
            if (!vv_sidecar_publish(&former.gate, former.path, parts, sizes, 1)) {
                return;               /* not written: everything stays queued */
            }
        }
        memmove(&former_pending[0], &former_pending[k], sizeof former_pending[0] * (size_t)(former_pending_count - k));
        former_pending_count -= k;
    }
}

/* File `kind` for the villager in `record`, replacing any entry of the same identity. */
static void former_file(const unsigned char *record, int kind) {
    if (kind < VV_FORMER_BLUE || kind > VV_FORMER_CHIEF) {
        return;
    }
    former_queue(FORMER_OP_FILE,
                 vv_title_identity(record, FORMER_NAME, FORMER_NAME_CAP, FORMER_LIKES, FORMER_DISLIKES,
                                   FORMER_SLOTS),
                 (unsigned int)kind);
    former_apply();
}

/* FORMER HEATHENS FOLLOW THEIR VILLAGER (v1.35.68).  The file keeps each
   former Heathen by name, likes and dislikes; an island event, the Custom
   Island Event or an upgrade that changes a villager's likes or dislikes
   left the entry under the old identity, and the villager was no longer
   called a Former Heathen.  So every tick looks at the roster, and when a
   villager changed identity in place -- same record, name, sex and age, and
   nobody moved (native/shared/identity_in_place.h) -- or was renamed (the
   same rule as the masks' and titles': one record changed, its sex, likes
   and dislikes unchanged), their entry is carried to the new identity.  An
   identity two entries carry stays nobody's (vv_former_lookup): nothing is
   guessed.  Since the identity audit (case 7): the change is queued until the
   file takes it (a rename while the file was held was lost); a rename in the
   frame of a birth or a death is followed (former_renamed); and when two
   villagers carried the old identity, neither is given the entry (FORMER_OP_UNSURE). */
static unsigned int former_roster[RECORDS_MAX];
static unsigned int former_roster_stable[RECORDS_MAX];
static unsigned int former_roster_keep[RECORDS_MAX];
static int former_roster_age[RECORDS_MAX];
static int former_roster_known;

static unsigned int former_identity(const unsigned char *record) {
    return vv_title_identity(record, FORMER_NAME, FORMER_NAME_CAP, FORMER_LIKES, FORMER_DISLIKES,
                             FORMER_SLOTS);
}

/* Bind the gate and path to `slot`; 0 when the file has no place. */
static int former_bind(int slot) {
    if (slot <= 0) {
        return 0;
    }
    if (slot != former.slot) {
        former.slot = slot;
        former.path[0] = '\0';
        vv_sidecar_gate_bind(&former.gate, 0x300 + slot);
    }
    return former.path[0] != '\0' || cod_data_path(former.path, "Former Heathens", "Former Heathens", slot);
}

/* Carry every entry of identity `from` to `to` in the slot's file -- queued, so it reaches the file
   even when the file cannot be written this frame.  `shared`: `from` was carried by more than one
   villager at the last look, so which of them the entry is for is not known (FORMER_OP_UNSURE). */
static void former_rekey(unsigned int from, unsigned int to, int shared) {
    if (from == to || from == 0u || to == 0u) {
        return;
    }
    former_queue(shared ? FORMER_OP_UNSURE : FORMER_OP_REKEY, from, to);
}

/* How many records carried `identity` at the last look. */
static int former_carried(int n, const unsigned int *seen, unsigned int identity) {
    int i, c = 0;
    for (i = 0; i < n; ++i) {
        c += seen[i] == identity;
    }
    return c;
}

/* A rename between two looks: exactly one record holds a villager at both looks and changed
   identity, keeping its sex, likes and dislikes (`*_stable`); every other change is a record
   emptied (a death, a departure) or filled (a birth, a newcomer) -- never a villager moved, which
   empties one record and fills another, and is no rename.  The masks' and titles' rule
   (vv_roster_renamed) refuses a rename in the same frame as a birth or a death; here it is
   followed (the identity audit, case 7).  Returns that record, or -1. */
static int former_renamed(int n, const unsigned int *was, const unsigned int *was_stable,
                          const unsigned int *now, const unsigned int *now_stable) {
    int i, at = -1;
    for (i = 0; i < n; ++i) {
        if (was[i] != now[i] && was[i] != 0u && now[i] != 0u) {
            if (at >= 0) {
                return -1;            /* two records hold somebody else: not one rename */
            }
            at = i;
        }
    }
    if (at < 0 || was_stable[at] == 0 || was_stable[at] != now_stable[at]) {
        return -1;
    }
    return at;
}

/* What a rename leaves of the identity: the likes, dislikes and sex. */
static unsigned int former_stable(const unsigned char *record) {
    unsigned int h = vv_title_identity(record, FORMER_NAME, 0u, FORMER_LIKES, FORMER_DISLIKES, FORMER_SLOTS);
    h = (h ^ (unsigned int)*(const int *)(record + REC[g_game].sex)) * 16777619u;
    return h ? h : 1u;
}

/* Every tick (New Believers): the roster now against the last look. */
static void former_follow(const unsigned char *records) {
    static unsigned int now[RECORDS_MAX], now_stable[RECORDS_MAX], now_keep[RECORDS_MAX];
    static int now_age[RECORDS_MAX];
    static unsigned char same[RECORDS_MAX];
    int n = (int)REC[g_game].slots < RECORDS_MAX ? (int)REC[g_game].slots : RECORDS_MAX;
    int i, anyone = 0;
    for (i = 0; i < n; ++i) {
        const unsigned char *record = records + (size_t)i * REC[g_game].stride;
        now[i] = now_stable[i] = now_keep[i] = 0;
        now_age[i] = 0;
        if (roster_member(record)) {
            now[i] = former_identity(record);
            now_stable[i] = former_stable(record);
            now_keep[i] = vv_identity_keep(record, FORMER_NAME, FORMER_NAME_CAP, REC[g_game].sex);
            now_age[i] = rec_age(record);
            anyone = 1;
        }
    }
    if (former_roster_known && anyone) {
        int renamed = former_renamed(n, former_roster, former_roster_stable, now, now_stable);
        if (renamed >= 0) {
            former_rekey(former_roster[renamed], now[renamed],
                         former_carried(n, former_roster, former_roster[renamed]) > 1);
        } else if (vv_roster_changed_in_place(n, former_roster, former_roster_keep, former_roster_age, now,
                                              now_keep, now_age, same) > 0) {
            for (i = 0; i < n; ++i) {
                if (same[i]) {
                    former_rekey(former_roster[i], now[i], former_carried(n, former_roster, former_roster[i]) > 1);
                }
            }
        }
    }
    former_apply();                   /* what is queued, as soon as the file can take it */
    memcpy(former_roster, now, sizeof(unsigned int) * (size_t)n);
    memcpy(former_roster_stable, now_stable, sizeof(unsigned int) * (size_t)n);
    memcpy(former_roster_keep, now_keep, sizeof(unsigned int) * (size_t)n);
    memcpy(former_roster_age, now_age, sizeof(int) * (size_t)n);
    former_roster_known = anyone;
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
    int i, kept = 0;
    /* Start Over: nothing queued for the erased village is written into the new one. */
    for (i = 0; i < former_pending_count; ++i) {
        if (former_pending[i].slot != slot) {
            former_pending[kept++] = former_pending[i];
        }
    }
    former_pending_count = kept;
    if (slot == former.slot) {
        vv_sidecar_gate_bind(&former.gate, -1);
        former.slot = 0;
        former.path[0] = '\0';
    }
    former_roster_known = 0;
    if (former_ready) {
        memset(former_kind_seen, -1, sizeof former_kind_seen);
    }
}
