/* The skin tones of one village, kept in the patcher's own per-save file and following each villager, and
   the rules that give a villager a tone.  Included by vvfp_skin_tones.c, and unchanged by
   native/vvfp_skin_tones/skin_tone_harness.c (which gives it a village of its own on real files).

   WHAT IS KEPT, per villager record (every value 0 = none, else the tone + 1, so tone 0 -- the game's own
   art -- is kept as 1):
       tone      the tone the villager is drawn with
       original  the tone it was born with or first given (Change Appearance's Reset to original)
       mother, father   on a carrying mother's record only: her own tone and the father's, AS THEY WERE AT
                 CONCEPTION (the parentage rule: recorded at conception, frozen at birth).  Cleared once
                 she is no longer carrying (the delivery clears her due field +0x358 after its last child).
   Nothing is ever written into a villager record.

   WHO GETS WHICH TONE (the owner, 2026-11-06: "per villager with inheritance", "inherited and chosen",
   "founders and arrivals should have random skin tones"; babies only inherit):
     * A BABY gets its tone from its parents, never at random: the MIDPOINT of the mother's and the father's
       tone (the owner's agreed design: a blend of the parents'), a half step rounded toward the mother's.
       Tones are a scale from light (1) to dark (N); tone 0, the game's own painted skin, counts as the
       lightest.  With no father known (the conception hook not in the game, a Custom Island Event's
       pregnancy) the baby takes the mother's tone.  Twins and triplets get the same tone.  The Golden
       Child is a birth like any other.
     * A FOUNDER OR AN ARRIVAL -- any living villager the store sees with no tone who was not handed to it as
       a birth: the starting villagers, Start Over's new founders, anyone who joins from outside (island
       events, the Barrel of Babies, the Mysterious Crate and Face, a Custom Island Event's villager,
       Story / Cheat Upgrades' villagers) and everyone already in a save when the patch is first installed --
       gets a random tone, 0..N each equally likely, from the DLL's own generator (never the game's rand(),
       so the game's own random sequence is untouched).  A villager is given one only once the village's
       roster has stayed the same for ST_SETTLE looks in a row (a second or so), so a load that is still
       filling the records never gives anyone a tone their file holds.
     * The player chooses any tone in Change Appearance (Set / SetMany).

   THE FILE.  "Virtual Villagers Fun Patcher\Save <S>\Data\Skin Tones\Skin Tones - Save <S>.dat"
   (native/shared/per_save_data.h), written through native/shared/sidecar_io.h (a temporary file, checked,
   then put in place) and never before the slot's load has settled.  Little-endian:

       u32 magic 'VST1' (0x31545356), u32 game (1), u32 count (256, the build's records)
       u32 roster[count]   the identity of the LIVING villager in each record when written (0 = nobody)
       u32 id[count]       the identity each entry was kept for (0 = none)
       u8  tone[count], u8 original[count], u8 mother[count], u8 father[count]   (0 none, else tone + 1)

   exactly 12 + count * 12 bytes.  A file of another shape is moved aside intact and the village starts
   with no tones (founders and arrivals: random again); a value above ST_TONE_LIMIT + 1 reads as none.

   FOLLOWING THE VILLAGER: the rules of "VVFP Head Look.dll" (head_look_store.inc) and the Origins masks
   (native/shared/mask_follow.h, foreign_sidecar.h, villager_rekey.h): the file belongs to the village it
   shares a strict roster majority with; a load's packing moves each entry to the one villager with its
   identity (name, sex and family +0x36C), never guessing at an identity two villagers share; a newborn in a
   dead villager's record never inherits an entry; a rename keeps it; another village's file is never
   replaced; Start Over deletes the file (native/shared/save_reset.c).

   The includer defines ST_MAX, ST_TONE_LIMIT, st_slots(), st_record(i), st_present(r), st_identity(r),
   st_stable(r), st_slot_now(), st_game(), st_pregnant(r), st_tone_count() and st_random(n). */

#include "../shared/villager_rekey.h"   /* a rename at a load keeps the tone (VvfpVillagersRenamed) */

#define ST_MAGIC 0x31545356u            /* 'VST1' */
#define ST_HEADER 12u
#define ST_TABLES 4
#define ST_FILE_BYTES(count) (ST_HEADER + (DWORD)(count) * 12u)
#define ST_FILE_MAX ST_FILE_BYTES(ST_MAX)
#define ST_SYNC_MS 250u
#define ST_SETTLE 4                     /* looks with the same roster before a newcomer gets a tone */
#define ST_KIND "Skin Tones"

enum { ST_TONE, ST_ORIGINAL, ST_MOTHER, ST_FATHER };

static unsigned char g_st[ST_TABLES][ST_MAX];  /* by record: 0 none, else tone + 1 */
static unsigned int g_st_id[ST_MAX];           /* the identity the record's entries were kept for */
static unsigned int g_roster[ST_MAX];          /* who held each record at the last look */
static unsigned int g_stable[ST_MAX];          /* ...and what a rename leaves of it */
static int g_have_roster;
static int g_slot;
static int g_quiet;                            /* looks in a row with the same roster */
static DWORD g_sync_tick;
static int g_sync_tried;
static vv_sidecar_gate g_gate;
static int g_foreign;
static unsigned char g_file[ST_FILE_MAX];

static int st_any(int i) {
    int t;
    for (t = 0; t < ST_TABLES; ++t) {
        if (g_st[t][i] != 0) {
            return 1;
        }
    }
    return 0;
}

static int st_roster(unsigned int *ids, unsigned int *stable) {
    int i, n = 0, slots = st_slots();
    memset(ids, 0, ST_MAX * sizeof(unsigned int));
    memset(stable, 0, ST_MAX * sizeof(unsigned int));
    for (i = 0; i < slots && i < ST_MAX; ++i) {
        const unsigned char *r = st_record(i);
        if (r != NULL && st_present(r)) {
            ids[i] = st_identity(r);
            stable[i] = st_stable(r);
            ++n;
        }
    }
    return n;
}

static int st_overlap(const unsigned int *a, const unsigned int *b) {
    int i, j, n = 0;
    for (i = 0; i < ST_MAX; ++i) {
        if (a[i] == 0) {
            continue;
        }
        for (j = 0; j < ST_MAX; ++j) {
            if (b[j] == a[i]) {
                ++n;
                break;
            }
        }
    }
    return n;
}

static int st_living(const unsigned int *a) {
    int i, n = 0;
    for (i = 0; i < ST_MAX; ++i) {
        n += a[i] != 0;
    }
    return n;
}

static int st_same_village(const unsigned int *a, const unsigned int *b) {
    int la = st_living(a), lb = st_living(b);
    int need = la < lb ? la : lb;
    return need != 0 && st_overlap(a, b) >= need / 2 + 1;
}

static int st_path(int slot, char *out) {
    char name[] = "Skin Tones - Save 0.dat";
    if (slot < 1 || slot > 5) {
        return 0;
    }
    name[sizeof "Skin Tones - Save " - 1] = (char)('0' + slot);
    return vv_ps_data_file_a(out, ST_KIND, name, VV_PS_RESERVE);
}

static int st_valid(const unsigned char *data, DWORD len, void *ctx) {
    unsigned int magic, game, count;
    (void)ctx;
    if (len < ST_HEADER) {
        return 0;
    }
    memcpy(&magic, data, 4);
    memcpy(&game, data + 4, 4);
    memcpy(&count, data + 8, 4);
    return magic == ST_MAGIC && game == (unsigned int)st_game() && (count == 150u || count == 256u)
        && count <= ST_MAX && len == ST_FILE_BYTES(count);
}

static int st_table_any(int slots) {
    int t;
    for (t = 0; t < ST_TABLES; ++t) {
        if (vv_table_any(g_st[t], slots)) {
            return 1;
        }
    }
    return 0;
}

/* Write the tables with the roster they belong to.  1 when on disk (or nothing to write over another
   village's file). */
static int st_publish(void) {
    static unsigned int ids[ST_MAX];
    char path[MAX_PATH];
    unsigned int header[3];
    const void *parts[3 + ST_TABLES];
    DWORD sizes[3 + ST_TABLES];
    int i, t, nothing, slots = st_slots();
    if (!g_have_roster || !vv_sidecar_gate_ready(&g_gate, g_slot) || !st_path(g_slot, path)) {
        return 0;
    }
    for (i = 0; i < ST_MAX; ++i) {
        ids[i] = st_any(i) ? g_st_id[i] : 0u;
    }
    header[0] = ST_MAGIC;
    header[1] = (unsigned int)st_game();
    header[2] = (unsigned int)slots;
    parts[0] = header;   sizes[0] = sizeof header;
    parts[1] = g_roster; sizes[1] = (DWORD)slots * sizeof(unsigned int);
    parts[2] = ids;      sizes[2] = (DWORD)slots * sizeof(unsigned int);
    for (t = 0; t < ST_TABLES; ++t) {
        parts[3 + t] = g_st[t];
        sizes[3 + t] = (DWORD)slots;
    }
    if (!vv_foreign_before_write(&g_foreign, path, st_table_any(slots), &nothing)) {
        return nothing;
    }
    return vv_sidecar_publish(&g_gate, path, parts, sizes, 3 + ST_TABLES);
}

/* Move every entry to where its villager is in `live` (mask_follow.h), each table by the same identities.
   1 when anything changed. */
static int st_follow(const unsigned int *stored, const unsigned int *stored_roster, const unsigned int *live,
                     int in_play) {
    static unsigned char moved[ST_MAX];
    static unsigned int moved_id[ST_TABLES][ST_MAX];
    int slots = st_slots();
    int changed = 0, t, i;
    for (t = 0; t < ST_TABLES; ++t) {
        changed |= in_play
            ? vv_mask_follow_in_play(slots, g_st[t], stored, stored_roster, live, 0, moved, moved_id[t])
            : vv_mask_follow(slots, g_st[t], stored, stored_roster, live, 0, moved, moved_id[t]);
        memcpy(g_st[t], moved, (size_t)slots);
    }
    for (i = 0; i < slots; ++i) {
        g_st_id[i] = 0;
        for (t = 0; t < ST_TABLES; ++t) {
            if (g_st[t][i] != 0) {
                g_st_id[i] = moved_id[t][i];
                break;
            }
        }
    }
    return changed;
}

/* Load the slot's file for the village whose roster is `live`.  The tables are cleared FIRST.  1 when the
   load settled, 0 while it must stay pending.  *rewrite: the entries moved on the way. */
static int st_load(int slot, const unsigned int *live, int *rewrite) {
    static unsigned int filesnap[ST_MAX], fileids[ST_MAX];
    char path[MAX_PATH];
    DWORD got = 0;
    unsigned int count;
    int status, kept, i, t, renamed;
    memset(g_st, 0, sizeof g_st);
    memset(g_st_id, 0, sizeof g_st_id);
    g_foreign = 0;
    *rewrite = 0;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (vv_sidecar_gate_throttled(&g_gate)) {
        return 0;
    }
    if (!st_path(slot, path)) {
        vv_sidecar_gate_block(&g_gate);
        return 0;
    }
    status = vv_sidecar_load(&g_gate, path, g_file, sizeof g_file, &got, st_valid, NULL);
    if (status == VV_SIDECAR_LOAD_BLOCKED) {
        return 0;
    }
    if (status != VV_SIDECAR_LOAD_VALID) {
        return 1;                               /* no file (or one set aside): nobody has a tone yet */
    }
    memcpy(&count, g_file + 8, 4);
    kept = (int)count < st_slots() ? (int)count : st_slots();
    memset(filesnap, 0, sizeof filesnap);
    memset(fileids, 0, sizeof fileids);
    memcpy(filesnap, g_file + ST_HEADER, (size_t)kept * sizeof(unsigned int));
    memcpy(fileids, g_file + ST_HEADER + count * 4u, (size_t)kept * sizeof(unsigned int));
    renamed = vv_rekey_apply(slot, filesnap, kept) + vv_rekey_apply(slot, fileids, kept);
    g_foreign = !st_same_village(filesnap, live);
    if (g_foreign) {
        return 1;                               /* another village's file: kept, never replaced */
    }
    for (t = 0; t < ST_TABLES; ++t) {
        const unsigned char *from = g_file + ST_HEADER + count * 8u + (unsigned int)t * count;
        for (i = 0; i < kept; ++i) {
            g_st[t][i] = from[i] <= ST_TONE_LIMIT + 1 ? from[i] : 0;   /* the file is the player's to edit */
        }
    }
    for (i = 0; i < kept; ++i) {
        if (!st_any(i)) {
            fileids[i] = 0;
        }
    }
    *rewrite = st_follow(fileids, filesnap, live, 0) || renamed > 0;
    return 1;
}

static int st_renamed(int slot, int count, const void *const *records, const char *const *old_names,
                      unsigned int stride, unsigned int name_at, unsigned int name_bytes) {
    static unsigned int from[VV_REKEY_BATCH], to[VV_REKEY_BATCH];
    int n = vv_rekey_pairs(count, records, old_names, st_identity, stride, name_at, name_bytes, from, to);
    int kept;
    (void)vv_rekey_drop_carried(from, n, records, st_slots(), st_record, st_present, st_identity);
    kept = vv_rekey_note(slot, from, to, n);
    if (kept > 0 && g_have_roster && g_slot == slot
        && vv_rekey_apply(slot, g_roster, ST_MAX) + vv_rekey_apply(slot, g_st_id, ST_MAX) > 0) {
        (void)st_publish();
    }
    return kept;
}

/* ---- the rules ------------------------------------------------------------------------------------- */

/* A random tone, 0..N each equally likely. */
static int st_random_tone(void) {
    return st_random(st_tone_count() + 1);
}

/* Record `i` (held) is seen for the first time with no tone: a founder or an arrival, given a random one. */
static void st_first_sight(int i) {
    int tone = st_random_tone();
    g_st[ST_TONE][i] = (unsigned char)(tone + 1);
    g_st[ST_ORIGINAL][i] = (unsigned char)(tone + 1);
    g_st_id[i] = g_roster[i];
}

/* Every living villager with no tone yet, once the roster has settled.  1 when anyone was given one. */
static int st_give_newcomers(void) {
    int i, slots = st_slots(), any = 0;
    for (i = 0; i < slots; ++i) {
        if (g_roster[i] != 0 && g_st[ST_TONE][i] == 0) {
            st_first_sight(i);
            any = 1;
        }
    }
    return any;
}

/* The conception tones a mother keeps are dropped once she is no longer carrying.  1 when any were. */
static int st_drop_spent(void) {
    int i, slots = st_slots(), any = 0;
    for (i = 0; i < slots; ++i) {
        const unsigned char *r;
        if (g_st[ST_MOTHER][i] == 0 && g_st[ST_FATHER][i] == 0) {
            continue;
        }
        r = st_record(i);
        if (g_roster[i] != 0 && r != NULL && !st_pregnant(r)) {
            g_st[ST_MOTHER][i] = 0;
            g_st[ST_FATHER][i] = 0;
            if (!st_any(i)) {
                g_st_id[i] = 0;
            }
            any = 1;
        }
    }
    return any;
}

/* A baby's tone from its parents' (each 0..N, or -1 not known): the midpoint, a half step toward the
   mother's; the mother's alone when the father is not known (and the father's when she is not). */
static int st_blend(int mother, int father) {
    int sum, mid;
    if (father < 0) {
        return mother < 0 ? 0 : mother;
    }
    if (mother < 0) {
        return father;
    }
    sum = mother + father;
    mid = sum / 2;
    if ((sum & 1) != 0 && mother > father) {
        ++mid;
    }
    return mid;
}

/* Bind the tables to the village on screen (throttled: at most every ST_SYNC_MS).  1 when they are that
   village's. */
static int st_sync(void) {
    static unsigned int cur[ST_MAX], cur_stable[ST_MAX];
    DWORD now = GetTickCount();
    int slot, renamed, rewrite;
    if ((g_have_roster || g_sync_tried) && (DWORD)(now - g_sync_tick) < ST_SYNC_MS) {
        return g_have_roster;
    }
    g_sync_tick = now;
    g_sync_tried = 1;
    slot = st_slot_now();
    if (slot <= 0 || st_roster(cur, cur_stable) == 0) {
        return 0;
    }
    if (g_have_roster && slot == g_slot) {
        int changed = 0;
        renamed = vv_roster_renamed_in_play(ST_MAX, g_roster, g_stable, cur, cur_stable);
        if (renamed >= 0) {
            g_roster[renamed] = cur[renamed];
            if (st_any(renamed)) {
                g_st_id[renamed] = cur[renamed];
            }
            memcpy(g_stable, cur_stable, sizeof g_stable);
            g_quiet = 0;
            st_publish();
            return 1;
        }
        if (!st_same_village(g_roster, cur)) {
            goto reload;
        }
        if (memcmp(g_roster, cur, sizeof cur) != 0) {
            st_follow(g_roster, g_roster, cur, 1);
            memcpy(g_roster, cur, sizeof cur);
            memcpy(g_stable, cur_stable, sizeof cur_stable);
            g_quiet = 0;
            changed = 1;
        } else if (g_quiet < ST_SETTLE) {
            ++g_quiet;
        }
        changed |= st_drop_spent();
        if (g_quiet >= ST_SETTLE) {
            changed |= st_give_newcomers();
        }
        if (changed) {
            st_publish();
        }
        return 1;
    }
reload:
    g_have_roster = 0;
    g_quiet = 0;
    if (!st_load(slot, cur, &rewrite)) {
        return 0;
    }
    memcpy(g_roster, cur, sizeof cur);
    memcpy(g_stable, cur_stable, sizeof cur_stable);
    g_have_roster = 1;
    g_slot = slot;
    if (rewrite) {
        st_publish();
    }
    return 1;
}

/* Look at the village now, not a moment ago. */
static int st_sync_now(void) {
    g_sync_tick = GetTickCount() - ST_SYNC_MS;
    return st_sync();
}

static int st_index(const unsigned char *record) {
    const unsigned char *first = st_record(0);
    const unsigned char *second = st_record(1);
    size_t stride, offset;
    if (first == NULL || second == NULL || record < first) {
        return -1;
    }
    stride = (size_t)(second - first);
    offset = (size_t)(record - first);
    if (offset % stride != 0 || offset / stride >= (size_t)st_slots()) {
        return -1;
    }
    return (int)(offset / stride);
}

/* The held villager's record number in the village on screen, or -1. */
static int st_held(const unsigned char *record) {
    int i = record != NULL ? st_index(record) : -1;
    if (i < 0 || !st_present(record) || g_roster[i] == 0 || g_roster[i] != st_identity(record)) {
        return -1;
    }
    return i;
}

/* The villager's tone 0..N, or -1 while none is kept (drawn with the game's own art). */
static int st_get(const unsigned char *record) {
    int i;
    if (record == NULL || !st_sync()) {
        return -1;
    }
    i = st_index(record);
    if (i < 0 || g_roster[i] == 0 || g_roster[i] != st_identity(record) || g_st[ST_TONE][i] == 0) {
        return -1;
    }
    return g_st[ST_TONE][i] - 1;
}

static int st_original(const unsigned char *record) {
    int i;
    if (record == NULL || !st_sync()) {
        return -1;
    }
    i = st_held(record);
    return i >= 0 && g_st[ST_ORIGINAL][i] != 0 ? g_st[ST_ORIGINAL][i] - 1 : -1;
}

/* Keep tones[k] for records[k], k < count, in ONE write.  Every record a held villager of the village on
   screen and every tone 0..ST_TONE_LIMIT, or nothing changes; a failed write puts every tone back. */
static int st_set_many(const unsigned char *const *records, const int *tones, int count) {
    static unsigned char was[ST_TABLES][ST_MAX];
    static unsigned int was_id[ST_MAX];
    int at[ST_MAX];
    int k;
    if (records == NULL || tones == NULL || count <= 0 || count > ST_MAX || !st_sync_now()) {
        return 0;
    }
    for (k = 0; k < count; ++k) {
        at[k] = st_held(records[k]);
        if (at[k] < 0 || tones[k] < 0 || tones[k] > ST_TONE_LIMIT) {
            return 0;
        }
    }
    memcpy(was, g_st, sizeof was);
    memcpy(was_id, g_st_id, sizeof was_id);
    for (k = 0; k < count; ++k) {
        int i = at[k];
        if (g_st[ST_ORIGINAL][i] == 0) {        /* no tone yet: the one it had (drawn) was the game's own */
            g_st[ST_ORIGINAL][i] = (unsigned char)(g_st[ST_TONE][i] != 0 ? g_st[ST_TONE][i] : 1);
        }
        g_st[ST_TONE][i] = (unsigned char)(tones[k] + 1);
        g_st_id[i] = g_roster[i];
    }
    if (!st_publish()) {
        memcpy(g_st, was, sizeof was);          /* memory never says what the file does not */
        memcpy(g_st_id, was_id, sizeof was_id);
        return 0;
    }
    return 1;
}

static int st_set(const unsigned char *record, int tone) {
    const unsigned char *one[1];
    one[0] = record;
    return st_set_many(one, &tone, 1);
}

/* The tone of the held villager in record `i`, giving a first-sight one when it has none yet. */
static int st_tone_of(int i) {
    if (g_st[ST_TONE][i] == 0) {
        st_first_sight(i);
    }
    return g_st[ST_TONE][i] - 1;
}

/* A conception: the mother's and the father's tones as they are now, kept against the mother.  `father`
   NULL (or not a held villager): not known.  1 when the file says so. */
static int st_conceived(const unsigned char *mother, const unsigned char *father) {
    int m, f;
    if (mother == NULL || !st_sync_now()) {
        return 0;
    }
    m = st_held(mother);
    if (m < 0) {
        return 0;
    }
    f = father != NULL ? st_held(father) : -1;
    g_st[ST_MOTHER][m] = (unsigned char)(st_tone_of(m) + 1);
    g_st[ST_FATHER][m] = (unsigned char)(f >= 0 ? st_tone_of(f) + 1 : 0);
    g_st_id[m] = g_roster[m];
    return st_publish();
}

/* A birth: the child (named, already in its record) gets its tone from the tones kept at conception, or
   from its mother's own tone when none were kept.  The kept tones stay for a twin or a triplet; they are
   dropped once the mother is no longer carrying (st_drop_spent).  1 when the file says so. */
static int st_born(const unsigned char *child, const unsigned char *mother) {
    int c, m, mother_tone, father_tone;
    if (child == NULL || mother == NULL) {
        return 0;
    }
    st_sync_now();
    if (!g_have_roster) {
        return 0;
    }
    c = st_index(child);
    m = st_held(mother);
    if (c < 0 || m < 0 || !st_present(child)) {
        return 0;
    }
    /* The child is the record's villager now (a birth in a dead villager's record never inherits). */
    g_roster[c] = st_identity(child);
    g_stable[c] = st_stable(child);
    if (g_st[ST_MOTHER][m] != 0) {
        mother_tone = g_st[ST_MOTHER][m] - 1;
        father_tone = g_st[ST_FATHER][m] != 0 ? g_st[ST_FATHER][m] - 1 : -1;
    } else {
        mother_tone = st_tone_of(m);
        father_tone = -1;
    }
    {
        int tone = st_blend(mother_tone, father_tone);
        g_st[ST_TONE][c] = (unsigned char)(tone + 1);
        g_st[ST_ORIGINAL][c] = (unsigned char)(tone + 1);
        g_st[ST_MOTHER][c] = 0;
        g_st[ST_FATHER][c] = 0;
        g_st_id[c] = g_roster[c];
    }
    return st_publish();
}
