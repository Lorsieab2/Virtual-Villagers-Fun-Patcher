/* The original looks of one village, kept in the patcher's own per-save file and following each villager.
   Included by vvfp_original_look.c, and unchanged by native/vvfp_original_look/original_look_harness.c (which
   gives it a village of its own on real files).

   WHAT IS KEPT.  For each villager, the head, body and mask (the Origins companion's mask value, 0..5:
   native/shared/original_look.h) they had before any Change Appearance or island event changed them, and
   where that original came from:
       1 FIRST RUN  the look they had when this companion first saw a village they were already in (the first
                    run over an existing save, or a load that found no original for them);
       2 SEEN       the look they had when they first appeared while their village was being played (a birth,
                    an arrival);
       3 LOGS       the look the patcher's logs prove they had before their first logged change -- the Old head
                    and Old body of the EARLIEST "Appearance changed" record of them (src/vv_original_look.py,
                    run by Repair Saves & Logs with the game closed).
   An original is never written over by a later first sight.  A body the game itself gives a villager (the
   robe, the clothing dialog's outfit) is folded into it (ol_game_body); Change Appearance and island events
   never are.  Nothing is ever written into a villager record.

   THE FILE.  "Virtual Villagers Fun Patcher\Save <S>\Data\Original Looks\Original Looks - Save <S>.dat"
   (native/shared/per_save_data.h routes it; an older-layout copy is used while one is there), next to the
   Head Looks file; written through native/shared/sidecar_io.h (to "<path>.tmp", checked, flushed, then moved
   into place), never before the slot's load has settled.  Little-endian:

       u32 magic 'VOL1' (0x314C4F56)   u32 version 1   u32 game (1..5)
       u32 count (150 or 256: the records)   u32 logged (0..256: the logs' originals)   u32 0
       count x { u32 roster   the identity of whoever held the record when it was written (0 = nobody: the
                              living only, so a load's village test and packing are judged on the living)
                 u32 id       the identity the original was kept for (0 = none kept on this record)
                 i32 head, i32 body, u8 mask, u8 source (1..3 above, or 4 NOT KNOWN: the logs said the
                 original of this villager is not known; kept on the record and following the villager like
                 an original -- through a load's packing and a rename in play, where the logs' entry stays
                 under the old identity -- so no first sight is ever recorded for them; head, body and mask 0),
                 u8 game body (1: the game itself set the body since -- the robe, a bought outfit -- so the
                 logs' original never takes it back; 0 otherwise), u8 0 }                 20 bytes each
       logged x { u32 id      the villager's identity in the save, by Repair Saves & Logs
                  i32 head, i32 body, u8 mask, u8 kind (1 the original is proven, 2 it is NOT known: the
                  villager was seen changed with no record of it, so nothing is ever recorded for them),
                  u8 0, u8 0 }                                                            16 bytes each
       u32 CRC-32 (zlib's) of every byte before it

   exactly 28 + count * 20 + logged * 16 bytes.  A file of another shape, version, game or checksum is moved
   aside intact (sidecar_io.h) and never read or written over.  The "logged" part is written only by the
   patcher (src/vv_original_look.py) and kept as it is by this companion.

   FOLLOWING THE VILLAGER -- as the Head Looks file (native/vvfp_head_look/head_look_store.inc), with the same
   shared rules (native/shared/mask_follow.h, foreign_sidecar.h), and two differences that keep a village's
   own file its own after a death (its roster names the living only, and the village test finds each
   villager wherever they are -- see ol_same_village):
     * the file belongs to the village whose living roster it shares a STRICT majority with (of the smaller
       roster), never to a slot alone: slots are reused by Start Over and by copied saves;
     * on a load the game packs its records, so each original goes to the one villager with its stored
       identity (name, sex and the parents' names; A New Home: name, sex and family), wherever they are now;
       an identity two villagers share is never guessed at -- and never given an original;
     * during play a birth or a death moves nobody: an original stays on its record while the record is
       empty (a body not yet buried, a villager away) and is dropped the moment anyone else holds it -- a
       newborn in a dead villager's record never inherits it, and is seen (and recorded) as themselves; a
       RENAME keeps it (one record changed, the sex and parents unchanged);
     * another village's file in the slot is never replaced on the strength of what is on screen: the game
       names a slot before its village is in the records (foreign_sidecar.h), so a village this companion
       has no file for -- or whose slot holds another village's file -- is kept in memory only until the
       game itself saves that slot with it (its "<stem><S>.ldw" written again: the village on screen IS that
       slot's); only then is the file written, another village's moved aside first, never deleted;
     * Start Over deletes the file with the rest of the save's folder (native/shared/save_reset.c).

   THE ORDER OF THE TWO WRITERS.  Repair Saves & Logs runs with the game closed (src/vv_log_tools.py refuses
   while it runs) and writes only the "logged" part, keeping every record entry byte for byte; this companion
   keeps the "logged" part as it read it.  When it binds a village and on every look after, each living
   villager with exactly one logged entry takes it over an original of source FIRST RUN or LOGS (a first
   sight is only a guess at history the logs may know better), and never over a SEEN one (seen at birth or
   arrival: nothing can be earlier); a logged "not known" removes a FIRST RUN original and stops any first
   sight.  So whichever runs first, the logs' original wins over a first-run snapshot and nothing proven is
   ever replaced.

   The includer defines, for its game: OL_MAX, ol_slots(), ol_record(i), ol_present(r), ol_named(r),
   ol_identity(r), ol_stable(r), ol_slot_now(), ol_game(), ol_look(r, &head, &body, &mask) (0 while the mask
   cannot be told) and ol_save_written(slot, &time) (0 when it cannot be told). */

#define OL_MAGIC 0x314C4F56u            /* 'VOL1' */
#define OL_VERSION 1u
#define OL_HEADER 24u
#define OL_ENTRY 20u
#define OL_LOGGED_ENTRY 16u
#define OL_LOGGED_MAX 256u
#define OL_FILE_BYTES(count, logged) (OL_HEADER + (DWORD)(count) * OL_ENTRY + (DWORD)(logged) * OL_LOGGED_ENTRY + 4u)
#define OL_FILE_MAX OL_FILE_BYTES(OL_MAX, OL_LOGGED_MAX)
#define OL_SYNC_MS 250u                 /* at most one look at the village each quarter second */
#define OL_SETTLE_MS 1500u              /* a village is bound only after its roster held this long */
#define OL_KIND "Original Looks"

enum { OL_NONE = 0, OL_FIRST_RUN = 1, OL_SEEN = 2, OL_LOGS = 3, OL_NOT_KNOWN = 4 };
enum { OL_LOGGED_KNOWN = 1, OL_LOGGED_UNKNOWN = 2 };
enum { OL_UNBOUND = 0, OL_PENDING = 1, OL_BOUND = 2 };

typedef struct {
    unsigned int id;
    int head, body;
    unsigned char mask, kind;
} ol_logged;

static unsigned char g_source[OL_MAX];        /* by record: OL_NONE..OL_LOGS */
static unsigned int g_id[OL_MAX];             /* the identity each original was kept for */
static int g_head[OL_MAX], g_body[OL_MAX];
static unsigned char g_mask[OL_MAX];
static unsigned char g_game_body[OL_MAX];     /* 1: the body is the game's own since (ol_game_body) */
static ol_logged g_logged[OL_LOGGED_MAX];     /* the logs' originals (src/vv_original_look.py) */
static unsigned int g_logged_count;
static unsigned int g_roster[OL_MAX];         /* who held each record at the last look */
static unsigned int g_stable[OL_MAX];         /* ...and what a rename leaves of it */
static unsigned int g_at_bind[OL_MAX];        /* who was there when the village was bound */
static int g_state;                           /* OL_UNBOUND, OL_PENDING (memory only), OL_BOUND */
static int g_slot;                            /* the slot the table is for */
static int g_foreign;                         /* the slot's file is another village's */
static int g_saved_known;                     /* the slot's save time when the village was bound... */
static FILETIME g_saved;                      /* ...: a save after it confirms the village */
static DWORD g_sync_tick;
static int g_synced;
static int g_candidate_slot;                  /* a village waiting to settle: its slot, roster and since */
static unsigned int g_candidate[OL_MAX];
static DWORD g_candidate_since;
static vv_sidecar_gate g_gate;
static unsigned char g_file[OL_FILE_MAX];

/* zlib's CRC-32 (reflected 0xEDB88320), so the patcher's Python writes the same with zlib.crc32. */
static unsigned int ol_crc32(const unsigned char *data, DWORD len) {
    unsigned int crc = 0xFFFFFFFFu;
    DWORD i;
    int k;
    for (i = 0; i < len; ++i) {
        crc ^= data[i];
        for (k = 0; k < 8; ++k) {
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
        }
    }
    return ~crc;
}

static unsigned int ol_u32(const unsigned char *p) {
    unsigned int v;
    memcpy(&v, p, 4);
    return v;
}

/* Every record's identity and stable part (0 for a record nobody holds, or one not named yet). */
static int ol_roster(unsigned int *ids, unsigned int *stable) {
    int i, n = 0, slots = ol_slots();
    memset(ids, 0, OL_MAX * sizeof(unsigned int));
    memset(stable, 0, OL_MAX * sizeof(unsigned int));
    for (i = 0; i < slots && i < OL_MAX; ++i) {
        const unsigned char *r = ol_record(i);
        if (r != NULL && ol_present(r) && ol_named(r)) {
            ids[i] = ol_identity(r);
            stable[i] = ol_stable(r);
            ++n;
        }
    }
    return n;
}

/* How many records of `ids` hold `id`. */
static int ol_holders(const unsigned int *ids, unsigned int id) {
    int i, n = 0;
    for (i = 0; i < OL_MAX; ++i) {
        n += ids[i] == id;
    }
    return n;
}

/* The same village: a STRICT majority of the smaller roster is shared (head_look_store.inc hl_same_village,
   vv5_roster_same) -- wherever each villager is in the other roster, not only at the same record or at the
   rank a packed load gives: a death the file was not written after (a quit right after it) would shift
   every later villager's rank by one and make the village's own file look like another village's. */
static int ol_same_village(const unsigned int *a, const unsigned int *b) {
    int i, shared = 0, la = 0, lb = 0, need;
    for (i = 0; i < OL_MAX; ++i) {
        la += a[i] != 0;
        lb += b[i] != 0;
    }
    need = la < lb ? la : lb;
    if (need == 0) {
        return 0;
    }
    for (i = 0; i < OL_MAX; ++i) {
        shared += a[i] != 0 && ol_holders(b, a[i]) != 0;
    }
    return shared >= need / 2 + 1;
}

static int ol_path(int slot, char *out) {
    char name[] = "Original Looks - Save 0.dat";
    if (slot < 1 || slot > 5) {
        return 0;
    }
    name[sizeof "Original Looks - Save " - 1] = (char)('0' + slot);
    return vv_ps_data_file_a(out, OL_KIND, name, VV_PS_RESERVE);
}

/* The header: magic, version, game, count, logged, 0 -- and the checksum at the end. */
static int ol_valid(const unsigned char *data, DWORD len, void *ctx) {
    unsigned int count, logged;
    (void)ctx;
    if (len < OL_HEADER + 4u) {
        return 0;
    }
    count = ol_u32(data + 12);
    logged = ol_u32(data + 16);
    return ol_u32(data) == OL_MAGIC && ol_u32(data + 4) == OL_VERSION && ol_u32(data + 8) == (unsigned int)ol_game()
        && (count == 150u || count == 256u) && count <= (unsigned int)OL_MAX && logged <= OL_LOGGED_MAX
        && ol_u32(data + 20) == 0u && len == OL_FILE_BYTES(count, logged)
        && ol_u32(data + len - 4) == ol_crc32(data, len - 4);
}

/* Write the table with the roster it belongs to, and the logs' part as it was read.  1 when it is on disk
   (or there was nothing to write over another village's file). */
static int ol_publish(void) {
    static unsigned char out[OL_FILE_MAX];
    char path[MAX_PATH];
    const void *parts[1];
    DWORD sizes[1];
    unsigned int header[6], crc;
    unsigned char any = 0;
    DWORD at;
    int i, nothing, slots = ol_slots();
    if (g_state != OL_BOUND || !vv_sidecar_gate_ready(&g_gate, g_slot) || !ol_path(g_slot, path)) {
        return 0;
    }
    header[0] = OL_MAGIC;
    header[1] = OL_VERSION;
    header[2] = (unsigned int)ol_game();
    header[3] = (unsigned int)slots;
    header[4] = g_logged_count;
    header[5] = 0u;
    memcpy(out, header, sizeof header);
    at = OL_HEADER;
    for (i = 0; i < slots; ++i) {
        /* The roster names the LIVING only: an original left on an empty record (a body buried, a villager
           away) keeps its identity in `id` alone, so the next load's village test and its packing are judged
           on the living (an id there would shift every later rank by one -- see THE FILE). */
        unsigned int roster = g_roster[i];
        unsigned int id = g_source[i] != OL_NONE ? g_id[i] : 0u;
        int head = g_source[i] != OL_NONE ? g_head[i] : 0, body = g_source[i] != OL_NONE ? g_body[i] : 0;
        unsigned char tail[4];
        tail[0] = g_source[i] != OL_NONE ? g_mask[i] : 0;
        tail[1] = g_source[i];
        tail[2] = g_source[i] != OL_NONE ? g_game_body[i] : 0;
        tail[3] = 0;
        any |= g_source[i];
        memcpy(out + at, &roster, 4);
        memcpy(out + at + 4, &id, 4);
        memcpy(out + at + 8, &head, 4);
        memcpy(out + at + 12, &body, 4);
        memcpy(out + at + 16, tail, 4);
        at += OL_ENTRY;
    }
    for (i = 0; i < (int)g_logged_count; ++i) {
        unsigned char tail[4];
        tail[0] = g_logged[i].mask;
        tail[1] = g_logged[i].kind;
        tail[2] = tail[3] = 0;
        memcpy(out + at, &g_logged[i].id, 4);
        memcpy(out + at + 4, &g_logged[i].head, 4);
        memcpy(out + at + 8, &g_logged[i].body, 4);
        memcpy(out + at + 12, tail, 4);
        at += OL_LOGGED_ENTRY;
    }
    crc = ol_crc32(out, at);
    memcpy(out + at, &crc, 4);
    at += 4;
    if (!vv_foreign_before_write(&g_foreign, path, any != 0 || g_logged_count != 0, &nothing)) {
        return nothing;
    }
    parts[0] = out;
    sizes[0] = at;
    return vv_sidecar_publish(&g_gate, path, parts, sizes, 1);
}

/* Move each original to where its villager is in `live` (mask_follow.h, as head_look_store.inc hl_follow:
   `stored_roster` is the roster the table was keyed by).  1 when the table changed. */
static int ol_follow(const unsigned int *stored_roster, const unsigned int *live, int in_play) {
    static unsigned char value[OL_MAX], moved[OL_MAX];
    static unsigned int moved_id[OL_MAX];
    static unsigned char source[OL_MAX], mask[OL_MAX], game_body[OL_MAX];
    static unsigned int id[OL_MAX];
    static int head[OL_MAX], body[OL_MAX];
    int slots = ol_slots(), t, i, changed;
    for (i = 0; i < slots; ++i) {
        value[i] = g_source[i] != OL_NONE;
    }
    changed = in_play
        ? vv_mask_follow_in_play(slots, value, stored_roster, stored_roster, live, 0, moved, moved_id)
        : vv_mask_follow(slots, value, stored_roster, stored_roster, live, 0, moved, moved_id);
    memset(source, 0, sizeof source);
    for (t = 0; t < slots; ++t) {
        int from = -1;
        if (!moved[t]) {
            continue;
        }
        if (value[t] && stored_roster[t] == moved_id[t]) {
            from = t;                           /* stayed where it was */
        } else {
            /* Moved: mask_follow.h moves an original only when its identity is held by exactly one. */
            for (i = 0; i < slots; ++i) {
                if (value[i] && stored_roster[i] == moved_id[t]) {
                    from = i;
                    break;
                }
            }
        }
        if (from < 0) {
            continue;
        }
        source[t] = g_source[from];
        id[t] = g_id[from];
        head[t] = g_head[from];
        body[t] = g_body[from];
        mask[t] = g_mask[from];
        game_body[t] = g_game_body[from];
    }
    for (t = 0; t < slots; ++t) {
        g_source[t] = source[t];
        g_id[t] = source[t] != OL_NONE ? id[t] : 0u;
        g_head[t] = source[t] != OL_NONE ? head[t] : 0;
        g_body[t] = source[t] != OL_NONE ? body[t] : 0;
        g_mask[t] = source[t] != OL_NONE ? mask[t] : 0;
        g_game_body[t] = source[t] != OL_NONE ? game_body[t] : 0;
    }
    return changed;
}

/* The logs' entry for `id`: its index when exactly one entry names it, else -1. */
static int ol_logged_of(unsigned int id) {
    unsigned int i;
    int found = -1;
    for (i = 0; i < g_logged_count; ++i) {
        if (g_logged[i].id == id) {
            if (found >= 0) {
                return -1;                      /* two entries of one identity: never guessed at */
            }
            found = (int)i;
        }
    }
    return found;
}

/* Whether any of the logs' entries says the original of `id` is not known. */
static int ol_logged_unknown(unsigned int id) {
    unsigned int i;
    for (i = 0; i < g_logged_count; ++i) {
        if (g_logged[i].id == id && g_logged[i].kind == OL_LOGGED_UNKNOWN) {
            return 1;
        }
    }
    return 0;
}

/* The logs' originals over a first-run snapshot (see THE ORDER OF THE TWO WRITERS).  1 when the table
   changed. */
static int ol_apply_logged(const unsigned int *live) {
    int i, changed = 0, slots = ol_slots();
    for (i = 0; i < slots; ++i) {
        const ol_logged *e;
        int k, body;
        if (live[i] == 0 || ol_holders(live, live[i]) != 1 || (k = ol_logged_of(live[i])) < 0) {
            continue;
        }
        e = &g_logged[k];
        if (e->kind == OL_LOGGED_UNKNOWN) {
            /* Not known: kept on the record as NOT KNOWN (over a first-run snapshot too), so it follows the
               villager through a rename in play -- the logs' entry stays under the old identity (Codex, PR
               #653) -- and no first sight is ever recorded for them. */
            if (g_source[i] == OL_NONE || g_source[i] == OL_FIRST_RUN
                || (g_source[i] == OL_NOT_KNOWN && g_id[i] != live[i])) {
                g_source[i] = OL_NOT_KNOWN;
                g_id[i] = live[i];
                g_head[i] = g_body[i] = 0;
                g_mask[i] = 0;
                g_game_body[i] = 0;
                changed = 1;
            }
            continue;
        }
        /* A body the game itself set since (the robe, a bought outfit) is part of the original: the logs,
           written before it, never take it back (the owner, 2026-10-28: Reset keeps the game's changes). */
        body = g_source[i] != OL_NONE && g_game_body[i] ? g_body[i] : e->body;
        if (e->kind != OL_LOGGED_KNOWN || g_source[i] == OL_SEEN
            || (g_source[i] == OL_LOGS && g_head[i] == e->head && g_body[i] == body && g_mask[i] == e->mask)) {
            continue;
        }
        g_game_body[i] = (unsigned char)(body != e->body);
        g_source[i] = OL_LOGS;
        g_id[i] = live[i];
        g_head[i] = e->head;
        g_body[i] = body;
        g_mask[i] = e->mask;
        changed = 1;
    }
    return changed;
}

/* Record the look of every villager seen for the first time: one of the village when it was bound is a
   FIRST RUN original, anyone after a SEEN one.  Never over an original kept, never for an identity two
   villagers share, never for one the logs say is not known, never while the mask cannot be told.  1 when
   the table changed. */
static int ol_first_sight(const unsigned int *live) {
    int i, changed = 0, slots = ol_slots();
    for (i = 0; i < slots; ++i) {
        int head, body, mask;
        const unsigned char *r;
        if (live[i] == 0 || g_source[i] != OL_NONE || ol_holders(live, live[i]) != 1
            || ol_logged_unknown(live[i]) || (r = ol_record(i)) == NULL || !ol_look(r, &head, &body, &mask)
            || mask < 0 || mask > 5) {
            continue;
        }
        g_source[i] = (unsigned char)(ol_holders(g_at_bind, live[i]) != 0 ? OL_FIRST_RUN : OL_SEEN);
        g_id[i] = live[i];
        g_head[i] = head;
        g_body[i] = body;
        g_mask[i] = (unsigned char)mask;
        g_game_body[i] = 0;
        changed = 1;
    }
    return changed;
}

/* Load the slot's file for the village whose roster is `live`.  The table is cleared FIRST, so every
   failure leaves no original known.  Returns -1 while it must stay pending (blocked: nothing may be read or
   written), 0 for no file (missing, or an invalid one set aside), 1 for this village's file, 2 for another
   village's.  *rewrite: the originals moved on the way. */
static int ol_load(int slot, const unsigned int *live, int *rewrite) {
    static unsigned int filesnap[OL_MAX];
    char path[MAX_PATH];
    DWORD got = 0, at;
    unsigned int count, logged, i;
    int status, kept;
    memset(g_source, 0, sizeof g_source);
    memset(g_id, 0, sizeof g_id);
    memset(g_head, 0, sizeof g_head);
    memset(g_body, 0, sizeof g_body);
    memset(g_mask, 0, sizeof g_mask);
    memset(g_game_body, 0, sizeof g_game_body);
    g_logged_count = 0;
    g_foreign = 0;
    *rewrite = 0;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (vv_sidecar_gate_throttled(&g_gate)) {
        return -1;
    }
    if (!ol_path(slot, path)) {
        vv_sidecar_gate_block(&g_gate);
        return -1;
    }
    status = vv_sidecar_load(&g_gate, path, g_file, sizeof g_file, &got, ol_valid, NULL);
    if (status == VV_SIDECAR_LOAD_BLOCKED) {
        return -1;
    }
    if (status != VV_SIDECAR_LOAD_VALID) {
        return 0;
    }
    count = ol_u32(g_file + 12);
    logged = ol_u32(g_file + 16);
    kept = (int)count < ol_slots() ? (int)count : ol_slots();
    memset(filesnap, 0, sizeof filesnap);
    for (i = 0; i < (unsigned int)kept; ++i) {
        filesnap[i] = ol_u32(g_file + OL_HEADER + i * OL_ENTRY);
    }
    if (!ol_same_village(filesnap, live)) {
        g_foreign = 1;
        return 2;                               /* another village's file: kept, never replaced */
    }
    for (i = 0; i < (unsigned int)kept; ++i) {
        const unsigned char *e = g_file + OL_HEADER + i * OL_ENTRY;
        unsigned int id = ol_u32(e + 4);
        if (id == 0u || e[17] < OL_FIRST_RUN || e[17] > OL_NOT_KNOWN || e[16] > 5) {
            continue;                           /* nothing kept here (or nothing this build knows) */
        }
        g_id[i] = id;
        memcpy(&g_head[i], e + 8, 4);
        memcpy(&g_body[i], e + 12, 4);
        g_mask[i] = e[16];
        g_source[i] = e[17];
        g_game_body[i] = (unsigned char)(e[18] == 1);
    }
    at = OL_HEADER + count * OL_ENTRY;
    for (i = 0; i < logged; ++i, at += OL_LOGGED_ENTRY) {
        g_logged[i].id = ol_u32(g_file + at);
        memcpy(&g_logged[i].head, g_file + at + 4, 4);
        memcpy(&g_logged[i].body, g_file + at + 8, 4);
        g_logged[i].mask = g_file[at + 12];
        g_logged[i].kind = g_file[at + 13];
    }
    g_logged_count = logged;
    *rewrite = ol_follow(filesnap, live, 0);
    return 1;
}

/* The game saved the slot since the village was bound: the village on screen is that slot's. */
static int ol_confirmed(void) {
    FILETIME now;
    if (!ol_save_written(g_slot, &now)) {
        return 0;
    }
    return !g_saved_known || CompareFileTime(&now, &g_saved) != 0;
}

/* Look at the village on screen (throttled: at most every OL_SYNC_MS unless `now_please`): bind it once it
   has settled, follow births, deaths, reloads and renames, record whoever is seen for the first time, and
   write the file when it may.  1 when the table is that village's. */
static int ol_sync(int now_please) {
    static unsigned int cur[OL_MAX], cur_stable[OL_MAX];
    DWORD now = GetTickCount();
    int slot, renamed, rewrite, status, changed = 0;
    if (!now_please && g_synced && (DWORD)(now - g_sync_tick) < OL_SYNC_MS) {
        return g_state != OL_UNBOUND;
    }
    g_synced = 1;
    g_sync_tick = now;
    slot = ol_slot_now();
    if (slot <= 0 || ol_roster(cur, cur_stable) == 0) {
        return 0;                               /* no village known: nothing touched */
    }
    if (g_state != OL_UNBOUND && slot == g_slot) {
        renamed = vv_roster_renamed_in_play(OL_MAX, g_roster, g_stable, cur, cur_stable);
        if (renamed >= 0) {
            /* A rename: the same villager, the original stays on the record under the new name. */
            g_roster[renamed] = cur[renamed];
            if (g_source[renamed] != OL_NONE) {
                g_id[renamed] = cur[renamed];
            }
            memcpy(g_stable, cur_stable, sizeof g_stable);
            changed = 1;
        } else if (ol_same_village(g_roster, cur)) {
            if (memcmp(g_roster, cur, sizeof cur) != 0) {
                /* A birth, a death, or a reload of the same village: each original goes to its villager, and
                   the file is written with the roster as it is now. */
                (void)ol_follow(g_roster, cur, 1);
                changed = 1;
                memcpy(g_roster, cur, sizeof cur);
                memcpy(g_stable, cur_stable, sizeof cur_stable);
            }
        } else {
            g_state = OL_UNBOUND;               /* another village: bound again once it has settled */
        }
        if (g_state != OL_UNBOUND) {
            changed |= ol_apply_logged(cur);
            changed |= ol_first_sight(cur);
            if (g_state == OL_PENDING && ol_confirmed()) {
                g_state = OL_BOUND;
                changed = 1;
            }
            if (changed && g_state == OL_BOUND) {
                ol_publish();
            }
            return 1;
        }
    }
    /* A village not bound yet: only one that has held still for OL_SETTLE_MS (a load in progress, or the
       title screen's seeded records, change under it). */
    if (g_candidate_slot != slot || memcmp(g_candidate, cur, sizeof cur) != 0) {
        g_candidate_slot = slot;
        memcpy(g_candidate, cur, sizeof cur);
        g_candidate_since = now;
        g_state = OL_UNBOUND;
        return 0;
    }
    if ((DWORD)(now - g_candidate_since) < OL_SETTLE_MS) {
        return 0;
    }
    status = ol_load(slot, cur, &rewrite);
    if (status < 0) {
        return 0;
    }
    g_slot = slot;
    memcpy(g_roster, cur, sizeof cur);
    memcpy(g_stable, cur_stable, sizeof cur_stable);
    memcpy(g_at_bind, cur, sizeof cur);
    if (status == 1) {
        g_state = OL_BOUND;
    } else {
        g_state = OL_PENDING;                   /* no file of this village yet: memory only until it saves */
        g_saved_known = ol_save_written(slot, &g_saved);
    }
    changed = rewrite;
    changed |= ol_apply_logged(cur);
    changed |= ol_first_sight(cur);
    if (changed && g_state == OL_BOUND) {
        ol_publish();
    }
    return 1;
}

/* The record's number, or -1 when `record` is not the start of one (the records are one array). */
static int ol_index(const unsigned char *record) {
    const unsigned char *first = ol_record(0);
    const unsigned char *second = ol_record(1);
    size_t stride, offset;
    if (first == NULL || second == NULL || record < first) {
        return -1;
    }
    stride = (size_t)(second - first);
    offset = (size_t)(record - first);
    if (offset % stride != 0 || offset / stride >= (size_t)ol_slots()) {
        return -1;
    }
    return (int)(offset / stride);
}

/* THE GAME'S OWN CHANGES ARE KEPT (the owner, 2026-10-28: "Keep game changes"): Reset to original undoes only
   Change Appearance and island events, so a body the game itself gives a villager -- The Secret City's robe
   for a new Tribal Chief, the outfit the game's own clothing dialog puts on -- becomes part of their
   original.  Called by the includer from the game's own writer of that body, just before it writes
   (vvfp_original_look.c GAME_WRITERS: no Change Appearance window and no island event reaches those
   instructions).  A villager with no original yet is left to the first sight, which sees the new body.
   1 when an original changed. */
static int ol_game_body(const unsigned char *record, int body) {
    int i;
    if (record == NULL || g_state == OL_UNBOUND || (i = ol_index(record)) < 0 || g_source[i] == OL_NONE
        || g_source[i] == OL_NOT_KNOWN || g_roster[i] == 0 || g_roster[i] != ol_identity(record) || g_id[i] != g_roster[i]
        || (g_body[i] == body && g_game_body[i])) {
        return 0;
    }
    g_body[i] = body;
    g_game_body[i] = 1;
    if (g_state == OL_BOUND) {
        ol_publish();
    }
    return 1;
}

/* The original look of the villager in `record`: 1 and the three filled when it is known. */
static int ol_get(const unsigned char *record, int *head, int *body, int *mask) {
    int i;
    if (record == NULL || head == NULL || body == NULL || mask == NULL || !ol_sync(1)) {
        return 0;
    }
    i = ol_index(record);
    if (i < 0 || g_roster[i] == 0 || g_source[i] == OL_NONE || g_source[i] == OL_NOT_KNOWN
        || g_roster[i] != ol_identity(record)
        || g_id[i] != g_roster[i]) {
        return 0;
    }
    *head = g_head[i];
    *body = g_body[i];
    *mask = g_mask[i];
    return 1;
}

