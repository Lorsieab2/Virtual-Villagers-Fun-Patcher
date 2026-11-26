/* The Living Event Engine at run time (docs/event-collection/living-pack.md).  Included by vvfp_story_upgrades.c
   after story_collection.inc; its prototypes are declared before story_graph.inc (cg_finish, the library purchase)
   and story_collection.inc (the rare roll, Pick Island Event) call it.

   A manifest row whose id begins "living_" is a Living Event Engine seed: its event is not a "<id>.cieg" file but
   one of the seed's variants in its group's pack, "Events\<group>.pak" beside "<group>.lst" (VLEP v1 or v2; an older install's single "living.pak" beside its "manifest.txt" when no
   split file exists: the group ""), each an ordinary version 6 graph.  ONE GROUP'S PACK IS LOADED AT A TIME, into
   memory of its own size, and changed when another group is asked for (the owner, 2026-11-15: many small files).

   THE DRAW (the rare roll, story_collection.inc sc_choose_and_arm): before the collection's draw, a seed among the
   last W seeds armed in this village (W = min(64, living rows / 3)) is left out (4.1), and each living category's
   series weighs by its mood (4.1a: the owner's Global Editorial Override, about one third warm, social and serious;
   a mood the history has seen least weighs LV_MOOD_BOOST).  A drawn seed orders its variants (lv_order, 4.2: fewer
   uses of the same role pair, lens, family set and variant weigh more), tries up to 12 under STRICT casting and
   queues the first that casts through cg_queue_origin -- so resume and the one-popup work as for every collection
   event.  None casts: the seed is left out and the draw made again.

   THE HISTORY, split (the owner, 2026-11-15): the GLOBAL part (VLEH v2) -- the recency ring by seed id (a 32-bit
   FNV-1a of the id, with the seed's mood) and the counts of role pairs, lenses, families and archetypes, the bank's
   own numbering in every pack -- in "Virtual Villagers N Living Events - Save S.dat"; and each GROUP's variant use
   counts (VLEG v1) in "Virtual Villagers N Living Events <group> - Save S.dat", tied to its pack's CRC.  Both beside
   the save, written after each arm and each finish; a missing, damaged or foreign file (another village:
   lv_roster_sig; other bank sizes; another pack) is a fresh part; Start Over and a deleted tribe delete them
   (VvfpStoryVillageReset).

   THE FINISH (lv_on_finish, called by cg_finish): the variant last armed (its group, kept in memory) is matched to
   the run's graph, its last node to the variant's outcome records, and the archetype reached is counted.

   PICK ISLAND EVENT AND THE LIBRARY: a living row is possible when any of its variants casts (STRICT for Pick, the
   library's own PREFER for a purchase); the variant queued is chosen by lv_order as well. */

#define LV_PREFIX "living_"
#define LV_PACK_LEAF "living.pak"
#define LV_PACK_MAX 0x10000000u          /* 256 MB: a sanity limit -- the pack is read into memory of its own size
                                             (a pack is about 23 MB; the owner, 2026-11-15) */
#define LV_HEADER 64u                     /* VLEP v1 */
#define LV_HEADER_V2 72u                  /* VLEP v2: 32-bit seed, variant, string and outcome fields */
#define LV_MAX_SEED_VARIANTS 4096         /* one seed's variants, v2 (v1: 255) */
#define LV_RING 64
#define LV_TRIES 12
#define LV_WEIGHT 1000
#define LV_MOODS 3                        /* warm, social, serious (bank.json moods.order) */
#define LV_MOOD_BOOST 2
#define LV_FAMILIES 128                   /* the family-set byte's values (bits 0..6) */
#define LV_NONE16 0xFFFFu
#define LV_NONE8 0xFFu
#define LV_FILE_HEAD 48u                  /* VLEH v2: the global part's header */
#define LV_RING_BYTES 8u                  /* a ring entry: I seed-id hash, B mood, 3 x 0 */
#define LV_FILE_COUNTS (LV_FILE_HEAD + LV_RING_BYTES * LV_RING)
#define LV_GROUP_HEAD 32u                 /* VLEG v1: a group's variant counts */
#define LV_MAX_KIND 255                   /* archetypes, lenses: at most 255 each */
#define LV_MAX_ROLES 64                   /* the bank has 30 */
#define LV_MAX_VARIANTS 32768             /* one group's pack (a sanity limit) */
#define LV_MAX_COUNTS (LV_MAX_ROLES * LV_MAX_ROLES + LV_MAX_KIND + LV_FAMILIES + LV_MAX_KIND)
#define LV_MAX_FILE (LV_FILE_COUNTS + 2u * LV_MAX_COUNTS)
#define LV_MAX_GROUP_FILE (LV_GROUP_HEAD + 2u * LV_MAX_VARIANTS)
#define LV_GROUP_BYTES 32                 /* a group's name: [a-z0-9_], at most 24 characters */
#define LV_WHAT "Living Events"

typedef struct {
    const unsigned char *d;
    unsigned int size;
    unsigned int crc;
    int game;
    int version;                       /* 1 or 2 */
    unsigned int seed_bytes, var_bytes;  /* a seed's and a variant's record: v1 16 / 24, v2 24 / 32 */
    int seeds, variants, outcomes;
    unsigned int o_seed, o_var, o_out, o_str, n_str, o_blob, n_blob;
    int roles, arcs, lenses;
} lv_pack;

typedef struct {
    int loaded;
    int game;
    int slot;
    story_village village;
    unsigned short ring_used, ring_head;
    unsigned int total;
    unsigned int ring[LV_RING];             /* each seed armed: the FNV-1a of its id (0 none) */
    unsigned char ring_mood[LV_RING];       /* ... and its mood */
    unsigned short counts[LV_MAX_COUNTS];   /* pair R*R, lens L, family 128, archetype A */
    unsigned int n_counts;
    int roles, arcs, lenses;
    /* The loaded group's variant counts (VLEG v1) */
    int group_loaded;
    char group[LV_GROUP_BYTES];
    unsigned int group_crc;
    int variants;
    unsigned short group_counts[LV_MAX_VARIANTS];
} lv_history;

static lv_pack lv_p;                  /* the loaded pack (lv_p.d != NULL): the group lv_pack_group names */
static char lv_pack_group[LV_GROUP_BYTES];   /* the group whose pack lv_p is */
/* The variant last armed (its group, seed and variant): the finish counts its archetype. */
static char lv_last_group[LV_GROUP_BYTES];
static int lv_last_variant = -1;
#ifndef VVFP_TEST
/* The pack read from its file: reserved once, at the first living draw (VirtualAlloc; a static buffer would push
   the DLL's image past the room a companion has). */
static unsigned char *lv_buf;
static unsigned int lv_buf_cap;           /* the bytes lv_buf holds (the pack's own size) */
#endif
static FILETIME lv_buf_time;
static unsigned int lv_buf_size;
static lv_history lv_h;
static int lv_mood_w[LV_MOODS] = { 1, 1, 1 };
static int lv_pending_seed = -1;      /* the library's chosen variant, recorded once it is queued */
static int lv_pending_variant = -1;

#ifdef VVFP_TEST
static const unsigned char *lv_test_pack;
static unsigned int lv_test_pack_size;
static unsigned char lv_test_file[LV_MAX_FILE];   /* the global history file, kept in memory here */
static unsigned int lv_test_file_size;
static int lv_test_have_file;
static unsigned char lv_test_gfile[LV_MAX_GROUP_FILE];   /* the group's file */
static unsigned int lv_test_gfile_size;
static int lv_test_have_gfile;
#endif

static unsigned int lv_u16(const unsigned char *p) {
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8);
}

static unsigned int lv_u32(const unsigned char *p) {
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8) | ((unsigned int)p[2] << 16) | ((unsigned int)p[3] << 24);
}

static void lv_put16(unsigned char *p, unsigned int v) {
    p[0] = (unsigned char)v;
    p[1] = (unsigned char)(v >> 8);
}

static void lv_put32(unsigned char *p, unsigned int v) {
    p[0] = (unsigned char)v;
    p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16);
    p[3] = (unsigned char)(v >> 24);
}

/* ---- The pack ------------------------------------------------------------------------------------------------ */

/* A NUL-ended string of the pack's strings at `off`, or NULL. */
static const char *lv_string(const lv_pack *p, unsigned int off) {
    unsigned int i;
    for (i = off; i < p->n_str; ++i) {
        if (p->d[p->o_str + i] == 0) {
            return (const char *)(p->d + p->o_str + off);
        }
    }
    return NULL;
}

/* THE RECORDS, v1 and v2 (living-pack.md 2; v2 widens what outgrew 16 bits at three mixer versions per static
   event: ~3,500 seeds, string offsets past 64 KB):
     seed     v1 16 bytes: H id, H series, H first variant, H count, B bank, B category, H index, B mood, 3 x 0
              v2 24 bytes: I id, I series, I first variant, I count, B bank, B category, H index, B mood, 3 x 0
     variant  v1 24 bytes: I blob, I size, H seed, B k, B flags, H role a, H role b, B lens, B family, H games,
                           H first outcome, H outcomes
              v2 32 bytes: I blob, I size, I seed, H role a, H role b, B lens, B family, B k, B flags,
                           I first outcome, I outcomes, H games, H 0
   The role pair, lens and family sit at the same places in both (+12 .. +17). */
static const unsigned char *lv_seed_rec(int s) {
    return lv_p.d + lv_p.o_seed + lv_p.seed_bytes * (unsigned int)s;
}

static const unsigned char *lv_var_rec(int v) {
    return lv_p.d + lv_p.o_var + lv_p.var_bytes * (unsigned int)v;
}

static unsigned int lv_seed_field(const lv_pack *p, const unsigned char *rec, int k) {
    return p->version >= 2 ? lv_u32(rec + 4u * (unsigned int)k) : lv_u16(rec + 2u * (unsigned int)k);
}
static unsigned int lv_seed_id(const lv_pack *p, const unsigned char *rec) { return lv_seed_field(p, rec, 0); }
static unsigned int lv_seed_series(const lv_pack *p, const unsigned char *rec) { return lv_seed_field(p, rec, 1); }
static unsigned int lv_seed_first(const lv_pack *p, const unsigned char *rec) { return lv_seed_field(p, rec, 2); }
static unsigned int lv_seed_count(const lv_pack *p, const unsigned char *rec) { return lv_seed_field(p, rec, 3); }
static unsigned int lv_seed_mood(const lv_pack *p, const unsigned char *rec) {
    return rec[p->version >= 2 ? 20 : 12];
}
static unsigned int lv_var_seed(const lv_pack *p, const unsigned char *rec) {
    return p->version >= 2 ? lv_u32(rec + 8) : lv_u16(rec + 8);
}
static unsigned int lv_var_out_first(const lv_pack *p, const unsigned char *rec) {
    return p->version >= 2 ? lv_u32(rec + 20) : lv_u16(rec + 20);
}
static unsigned int lv_var_out_count(const lv_pack *p, const unsigned char *rec) {
    return p->version >= 2 ? lv_u32(rec + 24) : lv_u16(rec + 22);
}

/* The pack `d` (`size` bytes) checked for `game` (living-pack.md 2.1: magic, version, sizes, crc, every offset and
   count inside the file) into `out`.  1 when it can be used. */
static int lv_check(const unsigned char *d, unsigned int size, int game, lv_pack *out) {
    lv_pack p;
    int i;
    unsigned int version;
    memset(&p, 0, sizeof p);
    if (d == NULL || size < LV_HEADER || memcmp(d, "VLEP", 4) != 0) {
        return 0;
    }
    version = lv_u16(d + 4);
    /* v1 and v2 are read; any other version is refused whole (never partly used). */
    if ((version != 1u && version != 2u) || lv_u16(d + 6) != (version == 2u ? LV_HEADER_V2 : LV_HEADER)
        || size < lv_u16(d + 6) || lv_u32(d + 8) != size || d[16] != (unsigned char)game
        || cg_crc32(d, size, 12) != lv_u32(d + 12)) {
        return 0;
    }
    p.d = d;
    p.size = size;
    p.crc = lv_u32(d + 12);
    p.game = game;
    p.version = (int)version;
    if (version == 2u) {
        /* v2 header (72 bytes): 4s VLEP, H 2, H 72, I size, I crc, B game, B 0, H 0, I seeds, I variants,
           I seeds at, I variants at, I outcomes at, I outcomes, I strings at, I strings, I blobs at, I blobs,
           H roles, H archetypes, H lenses, H 0, I 0. */
        p.seed_bytes = 24u;
        p.var_bytes = 32u;
        p.seeds = (int)lv_u32(d + 20);
        p.variants = (int)lv_u32(d + 24);
        p.o_seed = lv_u32(d + 28);
        p.o_var = lv_u32(d + 32);
        p.o_out = lv_u32(d + 36);
        p.outcomes = (int)lv_u32(d + 40);
        p.o_str = lv_u32(d + 44);
        p.n_str = lv_u32(d + 48);
        p.o_blob = lv_u32(d + 52);
        p.n_blob = lv_u32(d + 56);
        p.roles = (int)lv_u16(d + 60);
        p.arcs = (int)lv_u16(d + 62);
        p.lenses = (int)lv_u16(d + 64);
    } else {
        p.seed_bytes = 16u;
        p.var_bytes = 24u;
        p.seeds = (int)lv_u16(d + 18);
        p.variants = (int)lv_u16(d + 20);
        p.o_seed = lv_u32(d + 24);
        p.o_var = lv_u32(d + 28);
        p.o_out = lv_u32(d + 32);
        p.outcomes = (int)lv_u32(d + 36);
        p.o_str = lv_u32(d + 40);
        p.n_str = lv_u32(d + 44);
        p.o_blob = lv_u32(d + 48);
        p.n_blob = lv_u32(d + 52);
        p.roles = (int)lv_u16(d + 56);
        p.arcs = (int)lv_u16(d + 58);
        p.lenses = (int)lv_u16(d + 60);
    }
    if (p.seeds < 1 || p.seeds > SC_MAX || p.variants < 1 || p.outcomes < 0
        || (version == 1u && p.outcomes > 0xFFFF) || p.outcomes > 0x00FFFFFF
        || p.variants > LV_MAX_VARIANTS || p.roles > LV_MAX_ROLES || p.arcs > LV_MAX_KIND || p.lenses > LV_MAX_KIND
        || p.o_seed > size || p.seed_bytes * (unsigned int)p.seeds > size - p.o_seed
        || p.o_var > size || p.var_bytes * (unsigned int)p.variants > size - p.o_var
        || p.o_out > size || 4u * (unsigned int)p.outcomes > size - p.o_out
        || p.o_str > size || p.n_str > size - p.o_str
        || p.o_blob > size || p.n_blob > size - p.o_blob || (p.o_blob & 3u) != 0u) {
        return 0;
    }
    for (i = 0; i < p.seeds; ++i) {
        const unsigned char *s = d + p.o_seed + p.seed_bytes * (unsigned int)i;
        unsigned int first = lv_seed_first(&p, s), count = lv_seed_count(&p, s);
        if (count < 1u || count > (version == 2u ? (unsigned int)LV_MAX_SEED_VARIANTS : 255u)
            || first > (unsigned int)p.variants || count > (unsigned int)p.variants - first
            || lv_string(&p, lv_seed_id(&p, s)) == NULL || lv_string(&p, lv_seed_series(&p, s)) == NULL
            || lv_seed_mood(&p, s) >= LV_MOODS) {
            return 0;
        }
    }
    for (i = 0; i < p.variants; ++i) {
        const unsigned char *v = d + p.o_var + p.var_bytes * (unsigned int)i;
        unsigned int at = lv_u32(v), bytes = lv_u32(v + 4);
        unsigned int of = lv_var_out_first(&p, v), oc = lv_var_out_count(&p, v);
        if (at > p.n_blob || bytes == 0u || bytes > CG_MAX_FILE || bytes > p.n_blob - at
            || lv_var_seed(&p, v) >= (unsigned int)p.seeds
            || of > (unsigned int)p.outcomes || oc > (unsigned int)p.outcomes - of) {
            return 0;
        }
    }
    *out = p;
    return 1;
}

/* The pack of the group the collection loaded (lv_want_group: "<group>.pak", or the older single "living.pak"
   for the group ""), loaded and checked into memory of its own size -- the previous group's freed -- and read again
   only when the file changed: 1 when it can be used. */
static int lv_pack_for(int game) {
#ifdef VVFP_TEST
    if (lv_test_pack == NULL) {
        lv_p.d = NULL;
        return 0;
    }
    if (lv_p.d == lv_test_pack && lv_p.game == game) {
        return 1;
    }
    lv_p.d = NULL;
    lstrcpynA(lv_pack_group, lv_want_group, LV_GROUP_BYTES);
    return lv_check(lv_test_pack, lv_test_pack_size, game, &lv_p);
#else
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    WIN32_FILE_ATTRIBUTE_DATA info;
    char leaf[LV_GROUP_BYTES + 16];
    unsigned int size = 0;
    if (lv_want_group[0] != '\0') {
        wsprintfA(leaf, "%s.pak", lv_want_group);
    } else {
        lstrcpyA(leaf, LV_PACK_LEAF);
    }
    if (game < 1 || game > 5 || sc_path(path, leaf) == 0
        || !GetFileAttributesExW(path, GetFileExInfoStandard, &info) || info.nFileSizeHigh != 0
        || info.nFileSizeLow < LV_HEADER || info.nFileSizeLow > LV_PACK_MAX) {
        if (game >= 1 && game <= 5 && GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) {
            sc_problem("A living events pack is larger than its 256 MB limit or too small: its events were left out.");
        }
        lv_p.d = NULL;
        return 0;
    }
    if (lv_p.d != NULL && lv_p.game == game && lstrcmpA(lv_pack_group, lv_want_group) == 0
        && lv_buf_size == info.nFileSizeLow && CompareFileTime(&lv_buf_time, &info.ftLastWriteTime) == 0) {
        return 1;
    }
    lv_p.d = NULL;
    if (lv_buf != NULL && lv_buf_cap != info.nFileSizeLow) {
        VirtualFree(lv_buf, 0, MEM_RELEASE);   /* the previous group's pack: freed */
        lv_buf = NULL;
        lv_buf_cap = 0;
    }
    if (lv_buf == NULL) {
        lv_buf_cap = info.nFileSizeLow;
        lv_buf = (unsigned char *)VirtualAlloc(NULL, lv_buf_cap, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (lv_buf == NULL) {
            lv_buf_cap = 0;
            sc_problem("A living events pack could not be read: not enough memory.");
            return 0;
        }
    }
    if (!sc_read_w(path, lv_buf, lv_buf_cap, &size) || size != info.nFileSizeLow
        || !lv_check(lv_buf, size, game, &lv_p)) {
        sc_problem("A living events pack is damaged or of another version: its events were left out.");
        lv_p.d = NULL;
        return 0;
    }
    lstrcpynA(lv_pack_group, lv_want_group, LV_GROUP_BYTES);
    lv_buf_size = size;
    lv_buf_time = info.ftLastWriteTime;
    return 1;
#endif
}

/* The pack's seed whose id is `id`, -1 none (the pack must be loaded). */
static int lv_seed_of(const char *id) {
    int s;
    for (s = 0; s < lv_p.seeds; ++s) {
        const char *sid = lv_string(&lv_p, lv_seed_id(&lv_p, lv_seed_rec(s)));
        if (sid != NULL && lstrcmpA(sid, id) == 0) {
            return s;
        }
    }
    return -1;
}

static int lv_is_living(const char *id) {
    int i;
    for (i = 0; LV_PREFIX[i] != '\0'; ++i) {
        if (id[i] != LV_PREFIX[i]) {
            return 0;
        }
    }
    return 1;
}

/* Whether collection entry `i` (as lv_map_entries mapped it) is a seed of the loaded pack. */
static int lv_entry_living(int i) {
    return i >= 0 && i < sc_count && lv_entry_seed[i] >= 0 && lv_p.d != NULL;
}

static const unsigned char *lv_blob(int v, unsigned int *size) {
    const unsigned char *r = lv_var_rec(v);
    *size = lv_u32(r + 4);
    return lv_p.d + lv_p.o_blob + lv_u32(r);
}

/* ---- The history (VLEH v1) ---------------------------------------------------------------------------------- */

/* THE ROSTER SIGNATURE (living-pack.md 3): the identity (story_title_identity; 0 is read as 1) of the youngest
   villager in the village's records -- the smallest identity among the youngest -- when the file was written, 0
   when there is nobody.  A file is this village's when that villager is still among its records: the youngest is
   the one most likely to be there at the next event, and a villager who has gone since only costs a fresh history. */
static unsigned int lv_roster_sig(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned int best = 0u;
    int best_age = 0, i;
    if (a == NULL) {
        return 0u;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        unsigned int id;
        int age;
        if (r == NULL || !a->listed(r)) {
            continue;
        }
        id = story_title_identity(game, r);
        if (id == 0u) {
            id = 1u;
        }
        age = ce_age(a, r);
        if (best == 0u || age < best_age || (age == best_age && id < best)) {
            best = id;
            best_age = age;
        }
    }
    return best;
}

static int lv_roster_has(int game, unsigned int sig) {
    const ce_adapter *a = ce_adapter_for(game);
    int i;
    if (a == NULL || sig == 0u) {
        return 0;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        unsigned int id;
        if (r == NULL || !a->listed(r)) {
            continue;
        }
        id = story_title_identity(game, r);
        if ((id == 0u ? 1u : id) == sig) {
            return 1;
        }
    }
    return 0;
}

static unsigned int lv_pair_base(void) { return 0u; }
static unsigned int lv_lens_base(void) { return (unsigned int)(lv_h.roles * lv_h.roles); }
static unsigned int lv_family_base(void) { return lv_lens_base() + (unsigned int)lv_h.lenses; }
static unsigned int lv_arc_base(void) { return lv_family_base() + LV_FAMILIES; }

static unsigned int lv_file_bytes(void) {
    return LV_FILE_COUNTS + 2u * lv_h.n_counts;
}

static unsigned int lv_group_bytes(void) {
    return LV_GROUP_HEAD + 2u * (unsigned int)lv_h.variants;
}

/* The FNV-1a of a seed's id: what the recency ring keeps (never 0). */
static unsigned int lv_id_hash(const char *id) {
    unsigned int h = 2166136261u;
    for (; id != NULL && *id != '\0'; ++id) {
        h = (h ^ (unsigned char)*id) * 16777619u;
    }
    return h != 0u ? h : 1u;
}

/* The group's history file's "what" ("Living Events <group>"; the older single pack's group "" keeps "Living
   Events Group"). */
static void lv_group_what(const char *group, char *out) {
    wsprintfA(out, "%s %s", LV_WHAT, group[0] != '\0' ? group : "Group");
}

#ifdef VVFP_TEST
static int lv_file_read(int game, int slot, const char *group, unsigned char **data, unsigned int *size) {
    (void)game;
    (void)slot;
    if (group == NULL ? !lv_test_have_file : !lv_test_have_gfile) {
        return 0;
    }
    *data = group == NULL ? lv_test_file : lv_test_gfile;
    *size = group == NULL ? lv_test_file_size : lv_test_gfile_size;
    return 1;
}

static void lv_file_write(int game, int slot, const char *group, const unsigned char *data, unsigned int size) {
    (void)game;
    (void)slot;
    if (group == NULL) {
        if (size <= sizeof lv_test_file) {
            memcpy(lv_test_file, data, size);
            lv_test_file_size = size;
            lv_test_have_file = 1;
        }
    } else if (size <= sizeof lv_test_gfile) {
        memcpy(lv_test_gfile, data, size);
        lv_test_gfile_size = size;
        lv_test_have_gfile = 1;
    }
}

static void lv_file_delete(int game, int slot, const char *group) {
    (void)game;
    (void)slot;
    if (group == NULL) {
        lv_test_have_file = 0;
    } else {
        lv_test_have_gfile = 0;
    }
}
#else
static unsigned char lv_read_buf[LV_MAX_GROUP_FILE > LV_MAX_FILE ? LV_MAX_GROUP_FILE : LV_MAX_FILE];

/* The global part (group NULL) or a group's file of `slot`. */
static int lv_file_path(int game, int slot, const char *group, char *path, int make) {
    char what[LV_GROUP_BYTES + 32];
    if (group == NULL) {
        return vv_paid_named_path(game, slot, LV_WHAT, path, make);
    }
    lv_group_what(group, what);
    return vv_paid_named_path(game, slot, what, path, make);
}

static int lv_file_read(int game, int slot, const char *group, unsigned char **data, unsigned int *size) {
    char path[MAX_PATH];
    if (!lv_file_path(game, slot, group, path, 0)) {
        return 0;
    }
    *data = lv_read_buf;
    return cg_read_whole(path, lv_read_buf, sizeof lv_read_buf, size);
}

static void lv_file_write(int game, int slot, const char *group, const unsigned char *data, unsigned int size) {
    char path[MAX_PATH];
    const void *parts[1];
    DWORD sizes[1];
    if (!lv_file_path(game, slot, group, path, 1)) {
        return;
    }
    parts[0] = data;
    sizes[0] = size;
    (void)vv_paid_write_parts(path, parts, sizes, 1);
}

static void lv_file_delete(int game, int slot, const char *group) {
    char path[MAX_PATH];
    if (lv_file_path(game, slot, group, path, 0)) {
        DeleteFileA(path);
    }
}
#endif

/* A fresh (all zero) global part sized for the bank the loaded pack names. */
static void lv_fresh(int game, int slot) {
    unsigned int n = (unsigned int)(lv_p.roles * lv_p.roles + lv_p.lenses + LV_FAMILIES + lv_p.arcs);
    memset(lv_h.counts, 0, 2u * n);
    memset(lv_h.ring, 0, sizeof lv_h.ring);
    memset(lv_h.ring_mood, 0, sizeof lv_h.ring_mood);
    lv_h.n_counts = n;
    lv_h.ring_used = lv_h.ring_head = 0;
    lv_h.total = 0u;
    lv_h.game = game;
    lv_h.slot = slot;
    lv_h.village = story_village_now(game);
    lv_h.roles = lv_p.roles;
    lv_h.arcs = lv_p.arcs;
    lv_h.lenses = lv_p.lenses;
    lv_h.group_loaded = 0;
    lv_h.loaded = 1;
}

/* The loaded pack's group part, read from its file (fresh when missing, damaged, foreign or of another pack). */
static void lv_bind_group(int game, int slot) {
    unsigned char *f = NULL;
    unsigned int size = 0, i;
    lstrcpynA(lv_h.group, lv_pack_group, LV_GROUP_BYTES);
    lv_h.group_crc = lv_p.crc;
    lv_h.variants = lv_p.variants;
    memset(lv_h.group_counts, 0, 2u * (unsigned int)lv_p.variants);
    lv_h.group_loaded = 1;
    if (!lv_file_read(game, slot, lv_h.group, &f, &size) || size != lv_group_bytes() || size < LV_GROUP_HEAD
        || memcmp(f, "VLEG", 4) != 0 || lv_u16(f + 4) != 1u || lv_u16(f + 6) != LV_GROUP_HEAD
        || lv_u32(f + 8) != size || cg_crc32(f, size, 12) != lv_u32(f + 12) || lv_u32(f + 16) != lv_p.crc
        || !lv_roster_has(game, lv_u32(f + 20)) || lv_u32(f + 24) != (unsigned int)lv_p.variants) {
        return;                        /* a fresh part */
    }
    for (i = 0; i < (unsigned int)lv_p.variants; ++i) {
        lv_h.group_counts[i] = (unsigned short)lv_u16(f + LV_GROUP_HEAD + 2u * i);
    }
}

/* The village's history for the loaded pack: the global part kept while the same village plays (and the bank's
   sizes stay), else read from its file; the group's part likewise for the loaded pack.  1 when there is one. */
static int lv_bind(int game) {
    unsigned char *f = NULL;
    unsigned int size = 0, i;
    int slot = story_current_slot(game);
    if (lv_p.d == NULL || slot < 1) {
        return 0;
    }
    if (!(lv_h.loaded && lv_h.game == game && lv_h.slot == slot && story_village_is(game, &lv_h.village)
          && lv_h.roles == lv_p.roles && lv_h.arcs == lv_p.arcs && lv_h.lenses == lv_p.lenses)) {
        lv_fresh(game, slot);
        if (lv_file_read(game, slot, NULL, &f, &size) && size == lv_file_bytes() && size >= LV_FILE_COUNTS
            && memcmp(f, "VLEH", 4) == 0 && lv_u16(f + 4) == 2u && lv_u16(f + 6) == LV_FILE_HEAD
            && lv_u32(f + 8) == size && cg_crc32(f, size, 12) == lv_u32(f + 12)
            && lv_roster_has(game, lv_u32(f + 20)) && lv_u16(f + 24) <= LV_RING && lv_u16(f + 26) < LV_RING
            && lv_u16(f + 28) == (unsigned int)lv_p.roles && lv_u16(f + 30) == (unsigned int)lv_p.arcs
            && lv_u16(f + 32) == (unsigned int)lv_p.lenses) {
            lv_h.ring_used = (unsigned short)lv_u16(f + 24);
            lv_h.ring_head = (unsigned short)lv_u16(f + 26);
            lv_h.total = lv_u32(f + 40);
            for (i = 0; i < LV_RING; ++i) {
                lv_h.ring[i] = lv_u32(f + LV_FILE_HEAD + LV_RING_BYTES * i);
                lv_h.ring_mood[i] = f[LV_FILE_HEAD + LV_RING_BYTES * i + 4u];
            }
            for (i = 0; i < lv_h.n_counts; ++i) {
                lv_h.counts[i] = (unsigned short)lv_u16(f + LV_FILE_COUNTS + 2u * i);
            }
        }
    }
    if (!lv_h.group_loaded || lstrcmpA(lv_h.group, lv_pack_group) != 0 || lv_h.group_crc != lv_p.crc) {
        lv_bind_group(game, slot);
    }
    return 1;
}

/* Both parts written (the global one, then the loaded group's). */
static void lv_store(void) {
    static unsigned char out[LV_MAX_GROUP_FILE > LV_MAX_FILE ? LV_MAX_GROUP_FILE : LV_MAX_FILE];
    unsigned int size = lv_file_bytes(), i;
    if (!lv_h.loaded) {
        return;
    }
    memset(out, 0, size);
    memcpy(out, "VLEH", 4);
    lv_put16(out + 4, 2u);
    lv_put16(out + 6, LV_FILE_HEAD);
    lv_put32(out + 8, size);
    lv_put32(out + 20, lv_roster_sig(lv_h.game));
    lv_put16(out + 24, lv_h.ring_used);
    lv_put16(out + 26, lv_h.ring_head);
    lv_put16(out + 28, (unsigned int)lv_h.roles);
    lv_put16(out + 30, (unsigned int)lv_h.arcs);
    lv_put16(out + 32, (unsigned int)lv_h.lenses);
    lv_put32(out + 40, lv_h.total);
    for (i = 0; i < LV_RING; ++i) {
        lv_put32(out + LV_FILE_HEAD + LV_RING_BYTES * i, lv_h.ring[i]);
        out[LV_FILE_HEAD + LV_RING_BYTES * i + 4u] = lv_h.ring_mood[i];
    }
    for (i = 0; i < lv_h.n_counts; ++i) {
        lv_put16(out + LV_FILE_COUNTS + 2u * i, lv_h.counts[i]);
    }
    lv_put32(out + 12, cg_crc32(out, size, 12));
    lv_file_write(lv_h.game, lv_h.slot, NULL, out, size);
    if (!lv_h.group_loaded) {
        return;
    }
    size = lv_group_bytes();
    memset(out, 0, size);
    memcpy(out, "VLEG", 4);
    lv_put16(out + 4, 1u);
    lv_put16(out + 6, LV_GROUP_HEAD);
    lv_put32(out + 8, size);
    lv_put32(out + 16, lv_h.group_crc);
    lv_put32(out + 20, lv_roster_sig(lv_h.game));
    lv_put32(out + 24, (unsigned int)lv_h.variants);
    for (i = 0; i < (unsigned int)lv_h.variants; ++i) {
        lv_put16(out + LV_GROUP_HEAD + 2u * i, lv_h.group_counts[i]);
    }
    lv_put32(out + 12, cg_crc32(out, size, 12));
    lv_file_write(lv_h.game, lv_h.slot, lv_h.group, out, size);
}

static void lv_bump(unsigned int at) {
    if (at < lv_h.n_counts && lv_h.counts[at] < 0xFFFFu) {
        ++lv_h.counts[at];
    }
}

/* The role-pair key of variant record `r`, or -1 (a NONE role). */
static int lv_pair_key(const unsigned char *r) {
    unsigned int a = lv_u16(r + 12), b = lv_u16(r + 14);
    if (a == LV_NONE16 || b == LV_NONE16 || a >= (unsigned int)lv_h.roles || b >= (unsigned int)lv_h.roles) {
        return -1;
    }
    return (int)((a < b ? a : b) * (unsigned int)lv_h.roles + (a < b ? b : a));
}

/* u(v): the uses of variant `v`'s role pair, lens, family set and the variant itself (living-pack.md 4.2). */
static unsigned int lv_uses(int v) {
    const unsigned char *r = lv_var_rec(v);
    int key = lv_pair_key(r);
    unsigned int u = 0u;
    if (key >= 0) {
        u += lv_h.counts[lv_pair_base() + (unsigned int)key];
    }
    if (r[16] != LV_NONE8 && r[16] < (unsigned int)lv_h.lenses) {
        u += lv_h.counts[lv_lens_base() + r[16]];
    }
    u += lv_h.counts[lv_family_base() + (r[17] & (LV_FAMILIES - 1))];
    if (lv_h.group_loaded && v >= 0 && v < lv_h.variants) {
        u += lv_h.group_counts[v];
    }
    return u;
}

/* Seed `s` and its variant `v` armed: the ring and the counts (4.3), then the file. */
static void lv_record_arm(int s, int v) {
    const unsigned char *r = lv_var_rec(v);
    const unsigned char *seed = lv_seed_rec(s);
    int key = lv_pair_key(r);
    lv_h.ring[lv_h.ring_head] = lv_id_hash(lv_string(&lv_p, lv_seed_id(&lv_p, seed)));
    lv_h.ring_mood[lv_h.ring_head] = (unsigned char)lv_seed_mood(&lv_p, seed);
    lstrcpynA(lv_last_group, lv_pack_group, LV_GROUP_BYTES);
    lv_last_variant = v;
    lv_h.ring_head = (unsigned short)((lv_h.ring_head + 1) % LV_RING);
    if (lv_h.ring_used < LV_RING) {
        ++lv_h.ring_used;
    }
    if (key >= 0) {
        lv_bump(lv_pair_base() + (unsigned int)key);
    }
    if (r[16] != LV_NONE8 && r[16] < (unsigned int)lv_h.lenses) {
        lv_bump(lv_lens_base() + r[16]);
    }
    lv_bump(lv_family_base() + (r[17] & (LV_FAMILIES - 1)));
    if (lv_h.group_loaded && v >= 0 && v < lv_h.variants && lv_h.group_counts[v] < 0xFFFFu) {
        ++lv_h.group_counts[v];
    }
    ++lv_h.total;
    lv_store();
}

/* The ring's entry `k` back from the newest (k = 0 the newest): its seed-id hash, 0 past what is used. */
static unsigned int lv_ring_back(int k) {
    if (k < 0 || k >= lv_h.ring_used) {
        return 0u;
    }
    return lv_h.ring[(lv_h.ring_head + LV_RING - 1 - k) % LV_RING];
}

/* ...and its mood. */
static unsigned int lv_ring_mood_back(int k) {
    return lv_h.ring_mood[(lv_h.ring_head + LV_RING - 1 - k) % LV_RING];
}

/* ---- Choosing ---------------------------------------------------------------------------------------------- */

/* THE EXCLUSION HOOK: 1 when variant `v` of seed `s` may not be offered in `game` now.  Every path that tries a
   variant asks it first (the rare roll, Pick Island Event, the library).  It excludes nothing yet; it is the one
   place for the owner's coming rules (2026-11-15 answers: Q21 serious-event cooldowns of 30 / 60 in-game days per
   villager and immediate family, Q29 subject filters), which can read the variant's outcome records (2.4: each
   ending's group and archetype) before it is chosen. */
static int lv_excluded(int game, int s, int v) {
    unsigned int size = 0;
    const unsigned char *blob;
    (void)game;
    (void)s;
    if (!sc_gate) {
        return 0;                      /* only the natural draw below 61 villagers (story_collection.inc) */
    }
    /* The population gate (story_collection.inc): below 61 villagers the natural draw never takes a variant that
       can kill a villager, make one disappear or lose a pregnancy. */
    blob = lv_blob(v, &size);
    return blob != NULL && sc_graph_deadly(blob, size);
}

/* lv_order (living-pack.md 4.2; Python twin vv_living_mixer.lv_order): seed `s`'s variants in the order they are
   tried, into `order` (at most LV_TRIES).  The count. */
static int lv_order(int game, int s, int *order) {
    const unsigned char *rec = lv_seed_rec(s);
    int first = (int)lv_seed_first(&lv_p, rec), count = (int)lv_seed_count(&lv_p, rec);
    int left[255], weight[255], n = 0, k = 0, j;
    for (j = 0; j < count && j < 255; ++j) {
        unsigned int w = (unsigned int)LV_WEIGHT / (1u + lv_uses(first + j));
        left[n] = first + j;
        weight[n] = w < 1u ? 1 : (int)w;
        ++n;
    }
    while (n > 0 && k < LV_TRIES) {
        int total = 0, r, pick;
        for (j = 0; j < n; ++j) {
            total += weight[j];
        }
        r = sc_rand(game, total);      /* ce_random_below: no roll when the sum is at most 1 */
        pick = ce_roll_index(weight, n, r);
        order[k++] = left[pick];
        for (j = pick; j + 1 < n; ++j) {
            left[j] = left[j + 1];
            weight[j] = weight[j + 1];
        }
        --n;
    }
    return k;
}

/* Variant `v` loaded into the engine's graph (cg_g on cg_bytes) and checked with `cast` and `origin`: NULL when it
   can be cast now, else the refusal. */
static const char *lv_refusal(int game, int v, int cast, int origin) {
    unsigned int size = 0, planned = 0;
    const unsigned char *blob = lv_blob(v, &size);
    const char *refusal;
    int keep_cast = cg_cast_now, keep_origin = cg_origin_now;
    if (!cg_bytes_room(size)) {
        return "the event can not be read";
    }
    memcpy(cg_bytes, blob, size);
    cg_bytes_size = size;
    if (!cg_load(&cg_g, cg_bytes, size)) {
        cg_bytes_size = 0;
        return "its file can not be read: install the patch again";
    }
    cg_cast_now = cast;
    cg_origin_now = origin;
    refusal = cg_refusal(game, &planned);
    cg_cast_now = keep_cast;
    cg_origin_now = keep_origin;
    return refusal;
}

/* Seed `s` queued in `game` (cg_queue_origin with `origin` and `cast`): its variants tried in lv_order's order, the
   first that casts queued and recorded.  The variant, -1 when none can happen now. */
static int lv_arm_seed(int game, int s, int origin, int cast) {
    int order[LV_TRIES], n, k;
    if (lv_p.d == NULL || s < 0 || s >= lv_p.seeds || !lv_bind(game)) {
        return -1;
    }
    n = lv_order(game, s, order);
    for (k = 0; k < n; ++k) {
        unsigned int size = 0;
        const unsigned char *blob = lv_blob(order[k], &size);
        if (lv_excluded(game, s, order[k])) {
            continue;
        }
        if (cg_queue_origin(game, blob, size, origin, cast)) {
            lv_record_arm(s, order[k]);
            return order[k];
        }
    }
    return -1;
}

/* The collection entries (sc_list after sc_scan) mapped to the pack's seeds (lv_entry_seed); the count of living
   rows the game lists. */
static int lv_map_entries(int game) {
    int i, living = 0, have = lv_pack_for(game);
    for (i = 0; i < sc_count; ++i) {
        lv_entry_seed[i] = -1;
        if (lv_is_living(sc_list[i].id)) {
            lv_entry_seed[i] = (short)(have ? lv_seed_of(sc_list[i].id) : -1);
            living += lv_entry_seed[i] >= 0;
        }
    }
    return living;
}

/* Before the rare roll's draw: every living row the pack cannot give, and every seed among the last W armed
   (4.1), is left out (left[i] = 0); the moods' weights are set (4.1a).  The count left out. */
static int lv_draw_prepare(int game, unsigned char *left) {
    int i, k, out = 0, w, living = lv_map_entries(game);
    int count[LV_MOODS] = { 0, 0, 0 }, low, high;
    for (k = 0; k < LV_MOODS; ++k) {
        lv_mood_w[k] = 1;
    }
    if (living == 0 || !lv_bind(game)) {
        for (i = 0; i < sc_count; ++i) {
            if (lv_is_living(sc_list[i].id) && left[i]) {
                left[i] = 0;
                ++out;
            }
        }
        return out;
    }
    w = living / 3 < LV_RING ? living / 3 : LV_RING;
    for (i = 0; i < sc_count; ++i) {
        if (!left[i] || !lv_is_living(sc_list[i].id)) {
            continue;
        }
        if (lv_entry_seed[i] < 0) {
            left[i] = 0;
            ++out;
            continue;
        }
        for (k = 0; k < w; ++k) {
            if (lv_ring_back(k) == lv_id_hash(sc_list[i].id)) {
                left[i] = 0;
                ++out;
                break;
            }
        }
    }
    for (k = 0; k < lv_h.ring_used; ++k) {
        unsigned int mood = lv_ring_mood_back(k);
        if (mood < LV_MOODS) {
            ++count[mood];
        }
    }
    low = high = count[0];
    for (k = 1; k < LV_MOODS; ++k) {
        low = count[k] < low ? count[k] : low;
        high = count[k] > high ? count[k] : high;
    }
    for (k = 0; low != high && k < LV_MOODS; ++k) {
        lv_mood_w[k] = count[k] == low ? LV_MOOD_BOOST : 1;
    }
    return out;
}

/* A series' weight in the draw: a living category's by its mood, every other series 1. */
static int lv_series_weight(int i) {
    if (i < 0 || i >= sc_count || lv_entry_seed[i] < 0 || lv_p.d == NULL) {
        return 1;
    }
    return lv_mood_w[lv_seed_mood(&lv_p, lv_seed_rec(lv_entry_seed[i]))];
}

/* Collection entry `i` (a living row) queued: 1 when one of its variants is on its way. */
static int lv_arm_entry(int game, int i, int origin, int cast) {
    if (i < 0 || i >= sc_count || lv_entry_seed[i] < 0 || !lv_pack_for(game)) {
        return 0;
    }
    return lv_arm_seed(game, lv_entry_seed[i], origin, cast) >= 0;
}

/* Pick Island Event's check of a living row: NULL when any of its variants casts now (STRICT; with the picker's
   override, as the library buys it: story_more_events.inc sc_pick_override), else the first variant's refusal. */
static const char *lv_check_entry(int game, int i) {
    const unsigned char *rec;
    const char *first_refusal = NULL;
    int v, first, count;
    if (i < 0 || i >= sc_count || lv_entry_seed[i] < 0 || !lv_pack_for(game)) {
        return "its file can not be read: install the patch again";
    }
    rec = lv_seed_rec(lv_entry_seed[i]);
    first = (int)lv_seed_first(&lv_p, rec);
    count = (int)lv_seed_count(&lv_p, rec);
    for (v = first; v < first + count; ++v) {
        const char *refusal;
        if (lv_excluded(game, lv_entry_seed[i], v)) {
            continue;
        }
        cg_override_now = sc_pick_override;   /* the override: no puzzle requirement (story_more_events.inc) */
        refusal = lv_refusal(game, v, sc_pick_override ? CG_CAST_PREFER : CG_CAST_STRICT, CG_ORIGIN_PICK);
        cg_override_now = 0;
        if (refusal == NULL) {
            return NULL;
        }
        if (first_refusal == NULL) {
            first_refusal = refusal;
        }
    }
    return first_refusal;
}

/* ---- The library ------------------------------------------------------------------------------------------- */

#define LV_LIBRARY_TAG "?living:"         /* a library path no file can have: "<group>/<id>" follows */

static int lv_library_path(const char *path) {
    int i;
    for (i = 0; LV_LIBRARY_TAG[i] != '\0'; ++i) {
        if (path[i] != LV_LIBRARY_TAG[i]) {
            return 0;
        }
    }
    return 1;
}

/* The library's living row `path` ("?living:<id>"): the first variant lv_order gives that the library's cast
   (PREFER) can cast, left in cg_bytes / cg_g as cg_library_purchase reads a file there.  1 when there is one;
   else 0 with the reason in cg_why. */
static int lv_library_load(int game, const char *path) {
    int s, order[LV_TRIES], n, k;
    const char *first_refusal = NULL;
    const char *rest = path + lstrlenA(LV_LIBRARY_TAG), *slash;
    lv_pending_seed = lv_pending_variant = -1;
    for (slash = rest; *slash != '\0' && *slash != '/'; ++slash) {
    }
    if (*slash == '/' && slash - rest < LV_GROUP_BYTES) {
        lstrcpynA(lv_want_group, rest, (int)(slash - rest) + 1);   /* the row's group */
        rest = slash + 1;
    }
    if (!lv_pack_for(game) || (s = lv_seed_of(rest)) < 0 || !lv_bind(game)) {
        lstrcpynA(cg_why, "its file can not be read: install the patch again", sizeof cg_why);
        return 0;
    }
    n = lv_order(game, s, order);
    for (k = 0; k < n; ++k) {
        const char *refusal;
        if (lv_excluded(game, s, order[k])) {
            continue;
        }
        refusal = lv_refusal(game, order[k], CG_CAST_PREFER, CG_ORIGIN_PURCHASE);
        if (refusal == NULL) {
            lv_pending_seed = s;
            lv_pending_variant = order[k];
            return 1;
        }
        if (first_refusal == NULL) {
            first_refusal = refusal;
        }
    }
    lstrcpynA(cg_why, first_refusal != NULL ? first_refusal : "it can not happen right now", sizeof cg_why);
    cg_bytes_size = 0;
    return 0;
}

/* The library's purchase is on its way: its living variant (when it was one) is recorded. */
static void lv_library_armed(int game) {
    if (lv_pending_seed >= 0 && lv_pack_for(game) && lv_bind(game)) {
        lv_record_arm(lv_pending_seed, lv_pending_variant);
    }
    lv_pending_seed = lv_pending_variant = -1;
}

/* The library's group: each living row the pack holds, with its tagged path. */
static int lv_library_entry(int game, int i, char *path) {
    if (lv_entry_seed[i] < 0 || !lv_pack_for(game)) {
        return 0;
    }
    lstrcpynA(path, LV_LIBRARY_TAG, MAX_PATH);
    lstrcatA(path, lv_pack_group);
    lstrcatA(path, "/");
    lstrcatA(path, sc_list[i].id);
    return 1;
}

/* ---- The finish and Start Over ------------------------------------------------------------------------------- */

/* cg_finish: the run's graph matched to its variant and its last node to the variant's outcome records; the
   archetype reached (when it has one) is counted (4.3). */
static void lv_on_finish(int game) {
    int v, last;
    if (game < 1 || game > 5 || cg_bytes_size == 0u || cg.path.nodes <= 0 || lv_last_variant < 0) {
        return;
    }
    lstrcpynA(lv_want_group, lv_last_group, LV_GROUP_BYTES);   /* the group of the variant last armed */
    if (!lv_pack_for(game) || lv_last_variant >= lv_p.variants) {
        return;
    }
    last = cg.path.node[cg.path.nodes - 1];
    for (v = lv_last_variant; v == lv_last_variant; ++v) {
        unsigned int size = 0, o, first, count;
        const unsigned char *blob = lv_blob(v, &size);
        const unsigned char *r;
        if (size != cg_bytes_size || memcmp(blob, cg_bytes, size) != 0) {
            return;                    /* not the variant last armed: nothing counted */
        }
        r = lv_var_rec(v);
        first = lv_var_out_first(&lv_p, r);
        count = lv_var_out_count(&lv_p, r);
        for (o = first; o < first + count; ++o) {
            const unsigned char *out = lv_p.d + lv_p.o_out + 4u * o;
            if ((int)lv_u16(out) == last) {
                if (out[3] != LV_NONE8 && out[3] < (unsigned int)lv_p.arcs && lv_bind(game)) {
                    lv_bump(lv_arc_base() + out[3]);
                    lv_store();
                }
                return;
            }
        }
        return;
    }
}

/* Start Over or a deleted tribe in `slot`: its history goes. */
static void lv_village_reset(int game, int slot) {
    int g;
    if (game >= 1 && game <= 5 && slot >= 1 && slot <= 5) {
        lv_file_delete(game, slot, NULL);
        for (g = sc_index(game) - 1; g >= 0; --g) {
            lv_file_delete(game, slot, sc_groups[g].name);   /* every group's part */
        }
    }
    if (lv_h.game == game && lv_h.slot == slot) {
        lv_h.loaded = 0;
        lv_h.group_loaded = 0;
    }
}

#ifdef VVFP_TEST
/* ---- Test build only ---------------------------------------------------------------------------------------- */

static int lv_test_has_pack(void) {
    return lv_test_pack != NULL;
}

/* The pack the tests give (`data`, `size` bytes; NULL: none) and a fresh start: no history in memory, no file. */
__declspec(dllexport) void __stdcall VvfpStoryProbeLivingPack(const unsigned char *data, unsigned int size) {
    lv_test_pack = data;
    lv_test_pack_size = size;
    lv_p.d = NULL;
    lv_h.loaded = 0;
    lv_h.group_loaded = 0;
    lv_test_have_file = 0;
    lv_test_have_gfile = 0;
    lv_pending_seed = lv_pending_variant = -1;
    lv_last_variant = -1;
    lv_want_group[0] = '\0';
}

/* Every roll after the list VvfpStoryProbeSetRolls gives is `value` (-1: the game's own again). */
__declspec(dllexport) void __stdcall VvfpStoryProbeSetRollTail(int value) {
    test_roll_tail = value;
}

/* The history forgotten in memory (as at a restart): the next use reads the file. */
__declspec(dllexport) void __stdcall VvfpStoryProbeLivingForget(void) {
    lv_h.loaded = 0;
    lv_h.group_loaded = 0;
}

/* The history file: copies up to `size` bytes into `out`; its size, 0 = none. */
__declspec(dllexport) int __stdcall VvfpStoryProbeLivingFile(void *out, int size) {
    if (!lv_test_have_file) {
        return 0;
    }
    if (out != NULL && size > 0) {
        memcpy(out, lv_test_file, (unsigned int)size < lv_test_file_size ? (unsigned int)size : lv_test_file_size);
    }
    return (int)lv_test_file_size;
}

/* The history file replaced by `data` (`size` bytes; size 0: deleted), the memory's forgotten. */
__declspec(dllexport) void __stdcall VvfpStoryProbeLivingSetFile(const void *data, int size) {
    lv_h.loaded = 0;
    lv_h.group_loaded = 0;
    if (size <= 0) {
        lv_test_have_file = 0;
        return;
    }
    lv_file_write(0, 0, NULL, (const unsigned char *)data, (unsigned int)size);
}

/* The group's history file (VLEG): copies up to `size` bytes into `out`; its size, 0 = none. */
__declspec(dllexport) int __stdcall VvfpStoryProbeLivingGroupFile(void *out, int size) {
    if (!lv_test_have_gfile) {
        return 0;
    }
    if (out != NULL && size > 0) {
        memcpy(out, lv_test_gfile, (unsigned int)size < lv_test_gfile_size ? (unsigned int)size : lv_test_gfile_size);
    }
    return (int)lv_test_gfile_size;
}

/* The group's history file replaced by `data` (`size` bytes; size 0: deleted), the memory's forgotten. */
__declspec(dllexport) void __stdcall VvfpStoryProbeLivingSetGroupFile(const void *data, int size) {
    lv_h.group_loaded = 0;
    if (size <= 0) {
        lv_test_have_gfile = 0;
        return;
    }
    lv_file_write(0, 0, "", (const unsigned char *)data, (unsigned int)size);
}

/* lv_order of pack seed `s` in `game` with the village's history (the rolls VvfpStoryProbeSetRolls gives): the
   variants into `out` (at most `cap`); the count, -1 without a pack or a history. */
__declspec(dllexport) int __stdcall VvfpStoryProbeLivingOrder(int game, int s, int *out, int cap) {
    int order[LV_TRIES], n, k;
    if (!lv_pack_for(game) || s < 0 || s >= lv_p.seeds || !lv_bind(game)) {
        return -1;
    }
    n = lv_order(game, s, order);
    for (k = 0; k < n && k < cap; ++k) {
        out[k] = order[k];
    }
    return n;
}

/* The living row `id` (a pack seed id) armed as the rare roll arms it (origin, cast): the variant queued, -1. */
__declspec(dllexport) int __stdcall VvfpStoryProbeLivingArm(int game, const char *id, int origin, int cast) {
    if (!lv_pack_for(game)) {
        return -1;
    }
    install_state[game] = 1;
    return lv_arm_seed(game, lv_seed_of(id), origin, cast);
}

/* The village's history now (bound to the pack): out[0] ring used, [1] ring head, [2] events armed, [3] the roster
   signature this village would write, [4..6] the moods' draw weights after lv_draw_prepare on the scanned list,
   [7] the count left out by it.  -1 without a pack or a history. */
__declspec(dllexport) int __stdcall VvfpStoryProbeLivingState(int game, int *out) {
    unsigned char *left;
    int i;
    (void)sc_index(game);
    (void)sc_scan_group(game, 0);      /* the manifest the test gave (VvfpStoryProbeCollectionManifest) */
    left = sc_left;
    if (!lv_pack_for(game) || !lv_bind(game)) {
        return -1;
    }
    for (i = 0; i < sc_count; ++i) {
        left[i] = 1;
    }
    out[7] = sc_count > 0 ? lv_draw_prepare(game, left) : 0;
    out[0] = lv_h.ring_used;
    out[1] = lv_h.ring_head;
    out[2] = (int)lv_h.total;
    out[3] = (int)lv_roster_sig(game);
    for (i = 0; i < LV_MOODS; ++i) {
        out[4 + i] = lv_mood_w[i];
    }
    return 0;
}

/* The library's living row `id` loaded and, when `queue`, bought (cg_library_purchase's own steps, no dialog):
   the variant chosen (and recorded when queued), -1 none. */
__declspec(dllexport) int __stdcall VvfpStoryProbeLivingLibrary(int game, const char *id, int queue) {
    char path[MAX_PATH];
    unsigned int planned = 0;
    int v;
    lstrcpynA(path, LV_LIBRARY_TAG, MAX_PATH);
    lstrcatA(path, id);
    if (!lv_library_load(game, path)) {
        return -1;
    }
    v = lv_pending_variant;
    if (queue) {
        install_state[game] = 1;
        cg_cast_now = CG_CAST_PREFER;
        cg_origin_now = CG_ORIGIN_PURCHASE;
        if (cg_refusal(game, &planned) != NULL || !cg_queue(game, planned, 1)) {
            return -1;
        }
        lv_library_armed(game);
    }
    return v;
}

/* Start Over (VvfpStoryVillageReset's step) of `game`'s `slot`. */
__declspec(dllexport) void __stdcall VvfpStoryProbeLivingReset(int game, int slot) {
    lv_village_reset(game, slot);
}
#endif
