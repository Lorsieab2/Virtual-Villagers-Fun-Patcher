/* ---- Procedural island events: composed at draw time from pieces-<group>.pcb (v1.35.97) ----------------------

   The owner (2026-11-15): "so everything has a chance of showing up and can be mixed with anything. procedural
   generation."  docs/event-collection/procedural-pieces.md is the contract: the VPCB v1 piece files the data side
   writes, and the composer's rules and roll order (its Python twin makes exactly the same choices from the same
   rolls).  A composition is written as a version 6 .cieg in memory and queued as every collection event is
   (cg_queue_origin: the engine's own file checks, the strict cast, the protected villagers, No Safeguards and its
   Heathen / totem rules, Guardians of Isola); the run file keeps the graph's bytes, so a quit and a restore resume
   it as any other event.  Nothing is ever stored in the game or its save. */

#define PC_MAGIC "VPCB"
#define PC_HEADER 64u
#define PC_PIECE 64u
#define PC_SLOT 16u
#define PC_EFFECT 16u                     /* VPCB v1's effect record */
#define PC_EFFECT_V2 20u                  /* v2: byte 3 the group selector, and a u32 more (procedural-pieces.md 2.5) */
#define PC_LINK 8u
#define PC_FILE_MAX 0x00100000u           /* a pieces file: 1 MB (a sanity limit; past it the file is skipped) */
#define PC_STR_NONE 0xFFFFFFFFu
#define PC_GROUP_BYTES 32
#define PC_TRIES 8                        /* setups tried in one file before the draw moves on */
#define PC_MAX_APPROACHES 4               /* 2 + random_below(3) */
#define PC_MAX_OUTCOMES 3                 /* 1 + random_below(3) */
#define PC_MAX_SLOTS 64                   /* the slots of one composition, before they merge */
#define PC_MAX_STRINGS 256
#define PC_LIBRARY_TAG "?pieces:"         /* a library path no file can have: "<group>/<setup id>" follows */
#define PC_PROC_BASE SM_PROC_BASE        /* a Pick Island Event list entry's k for procedural row r: + r */

enum { PC_SETUP = 1, PC_APPROACH = 2, PC_OUTCOME = 3, PC_FLAVOUR = 4, PC_FRAME = 5 };
#define PC_F_DEADLY 1u                    /* a piece's flags */
#define PC_F_BELIEVERS 2u
#define PC_F_AUTO_LINES 4u                /* an outcome: its effects told in automatic lines (cie-v6-binary.md 25) */
#define PC_S_OPTIONAL 1u                  /* a slot's flags */
#define PC_S_BELIEVERS 2u
#define PC_S_SPEAKS 4u
#define PC_S_HARM 8u
#define PC_S_CONVERSION 16u
#define PC_S_ANY_BIRTH_SEX 32u
#define PC_SPECIAL_CARRIER 3

/* vv_event_content.NOTE_LABELS, in its order (a piece's note bit k is the k-th). */
static const char *const PC_NOTE_LABELS[] = { "Child death", "Pregnancy loss", "Bereavement", "Serious injury",
                                              "Disappearance", "Historical suffering", "Emotional distress" };

typedef struct {
    const unsigned char *d;
    unsigned int size;
    unsigned int n_piece, o_piece, o_str, n_str_bytes, o_effect, n_effect, o_slot, n_slot, o_link, n_link;
    unsigned int version, effect_bytes;
} pc_file;

typedef struct {
    char name[PC_GROUP_BYTES];
    int weight;
} pc_group;

static unsigned char *pc_buf;             /* the file being composed from (PC_FILE_MAX, allocated once) */
static pc_file pc_f;
static int pc_loaded = -1;                /* the group pc_buf holds */
static pc_group *pc_groups;
static int pc_group_count, pc_group_cap;
static int pc_game;                       /* the game the composition is for */
static int pc_dry;                        /* the Pick list's check: rolls from a private generator, never the game's */
static unsigned int pc_dry_state;
static char pc_note_on;                   /* Content Notes for Island Events installed (set per composition) */
/* Pick Island Event's procedural rows: each row's group and setup piece. */
static int *pc_ref_group, *pc_ref_piece;
static int pc_ref_count, pc_ref_cap;
static char pc_pick_title[SM_TEXT];       /* the row last bought (its message) */
#ifdef VVFP_TEST
static const unsigned char *pc_test_file; /* the one pieces file instead of the folder's */
static unsigned int pc_test_size;
#endif

static unsigned int pc_u16(const unsigned char *p) { return (unsigned int)p[0] | ((unsigned int)p[1] << 8); }
static unsigned int pc_u32(const unsigned char *p) {
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8) | ((unsigned int)p[2] << 16) | ((unsigned int)p[3] << 24);
}
static void pc_put16(unsigned char *p, unsigned int v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); }
static void pc_put32(unsigned char *p, unsigned int v) {
    p[0] = (unsigned char)v;
    p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16);
    p[3] = (unsigned char)(v >> 24);
}

/* ---- The file ------------------------------------------------------------------------------------------------ */

static const unsigned char *pc_piece(int i) { return pc_f.d + pc_f.o_piece + PC_PIECE * (unsigned int)i; }
static const unsigned char *pc_slot(unsigned int i) { return pc_f.d + pc_f.o_slot + PC_SLOT * i; }
static const unsigned char *pc_effect(unsigned int i) { return pc_f.d + pc_f.o_effect + pc_f.effect_bytes * i; }

/* An effect's role byte that is no slot of its piece: every villager (0xFF), a group (0xFE), the villagers the event
   made (0xFD the newest, 0xFC the one before it): kept as it is. */
static int pc_role_kept(unsigned int b) {
    return b == 0xFFu || b == CG_ROLE_GROUP || b == CG_ROLE_NEWEST || b == CG_ROLE_NEWEST2;
}

/* v2: an effect's extra u32 (a group's N or the skill's name string, change_age's cap); v1: 0 / none. */
static unsigned int pc_effect_extra(const unsigned char *e) {
    return pc_f.version >= 2u ? pc_u32(e + 16) : 0u;
}
static const unsigned char *pc_link(unsigned int i) { return pc_f.d + pc_f.o_link + PC_LINK * i; }

/* The string at `off` (NULL for none; the table's last byte is a NUL, so every offset inside it is NUL-ended). */
static const char *pc_str(unsigned int off) {
    return off == PC_STR_NONE || off >= pc_f.n_str_bytes ? NULL : (const char *)pc_f.d + pc_f.o_str + off;
}

static int pc_range(unsigned int at, unsigned int count, unsigned int each, unsigned int size) {
    return at <= size && count <= (size - at) / each;
}

static int pc_deadly_code(unsigned int code) {
    return code == CGE_KILL || code == CGE_VANISH || code == CGE_DIE_UNRECOVERED || code == CGE_BIRTH_THEN_DIE
           || code == CGE_BABY_LOST;
}

/* `data` checked as a VPCB v1 file for `game` (header, CRC, every table and reference inside it) into pc_f. */
static int pc_check(const unsigned char *data, unsigned int size) {
    unsigned int i;
    pc_file f;
    memset(&f, 0, sizeof f);
    if (size < PC_HEADER || size > PC_FILE_MAX || memcmp(data, PC_MAGIC, 4) != 0 || (pc_u16(data + 4) != 1u && pc_u16(data + 4) != 2u)
        || pc_u16(data + 6) != PC_HEADER || pc_u32(data + 8) != size || cg_crc32(data, size, 12) != pc_u32(data + 12)) {
        return 0;
    }
    f.d = data;
    f.size = size;
    f.version = pc_u16(data + 4);
    f.effect_bytes = f.version >= 2u ? PC_EFFECT_V2 : PC_EFFECT;
    f.n_piece = pc_u32(data + 20);
    f.o_piece = pc_u32(data + 24);
    f.o_str = pc_u32(data + 28);
    f.n_str_bytes = pc_u32(data + 32);
    f.o_effect = pc_u32(data + 36);
    f.n_effect = pc_u32(data + 40);
    f.o_slot = pc_u32(data + 44);
    f.n_slot = pc_u32(data + 48);
    f.o_link = pc_u32(data + 52);
    f.n_link = pc_u32(data + 56);
    if (!pc_range(f.o_piece, f.n_piece, PC_PIECE, size) || !pc_range(f.o_str, f.n_str_bytes, 1, size)
        || f.n_str_bytes == 0 || data[f.o_str + f.n_str_bytes - 1] != 0
        || !pc_range(f.o_effect, f.n_effect, f.effect_bytes, size) || !pc_range(f.o_slot, f.n_slot, PC_SLOT, size)
        || !pc_range(f.o_link, f.n_link, PC_LINK, size)) {
        return 0;
    }
    pc_f = f;
    for (i = 0; i < f.n_piece; ++i) {
        const unsigned char *p = pc_piece((int)i);
        unsigned int k, slots = pc_u16(p + 44), first_slot = pc_u32(p + 40);
        unsigned int first_fx = pc_u32(p + 48), fx = pc_u16(p + 52), first_link = pc_u32(p + 56), links = pc_u16(p + 60);
        if (pc_str(pc_u32(p)) == NULL || p[4] < PC_SETUP || p[4] > PC_FRAME || p[5] > 2u
            || (p[6] & ~(PC_F_DEADLY | PC_F_BELIEVERS | PC_F_AUTO_LINES)) != 0u || pc_u16(p + 46) < 1u
            || pc_u16(p + 46) > 1000u || pc_u16(p + 54) > 2u
            || (pc_u32(p + 32) != PC_STR_NONE && pc_str(pc_u32(p + 32)) == NULL)
            || (pc_u32(p + 36) != PC_STR_NONE && pc_str(pc_u32(p + 36)) == NULL)
            || (p[4] == PC_SETUP && (pc_str(pc_u32(p + 32)) == NULL || pc_str(pc_u32(p + 36)) == NULL))
            || (p[4] == PC_APPROACH && pc_str(pc_u32(p + 36)) == NULL)
            || ((p[4] == PC_OUTCOME || p[4] >= PC_FLAVOUR) && pc_str(pc_u32(p + 32)) == NULL)
            || slots > PC_MAX_SLOTS || first_slot > f.n_slot || slots > f.n_slot - first_slot || first_fx > f.n_effect
            || fx > f.n_effect - first_fx || first_link > f.n_link || links > f.n_link - first_link) {
            pc_f.d = NULL;
            return 0;
        }
        for (k = 0; k < slots; ++k) {
            const unsigned char *s = pc_slot(first_slot + k);
            if (pc_str(pc_u32(s)) == NULL || s[4] > 1u || s[5] > 2u || s[6] > 120u || s[7] > 120u
                || (s[7] != 0 && s[7] < s[6]) || s[8] > 3u || (s[9] & 0xC0u) != 0u) {
                pc_f.d = NULL;
                return 0;
            }
        }
        for (k = 0; k < fx; ++k) {
            const unsigned char *e = pc_effect(first_fx + k);
            unsigned int str = pc_u32(e + 12);
            unsigned int extra = pc_effect_extra(e);
            if (e[0] < 1u || e[0] > 40u || e[0] == 25u || (!pc_role_kept(e[1]) && e[1] >= slots)
                || (str != PC_STR_NONE && pc_str(str) == NULL)
                || (e[1] == CG_ROLE_GROUP ? e[3] < 1u || e[3] > 7u : e[3] != 0u)
                || (e[1] == CG_ROLE_GROUP && e[3] == CG_GROUP_SKILL && pc_str(extra) == NULL)
                || (e[1] != CG_ROLE_GROUP && e[0] != CGE_CHANGE_AGE && extra != 0u && pc_f.version >= 2u)) {
                pc_f.d = NULL;
                return 0;
            }
        }
        for (k = 0; k < links; ++k) {
            const unsigned char *l = pc_link(first_link + k);
            if (pc_str(pc_u32(l)) == NULL || pc_u32(l + 4) < 1u || pc_u32(l + 4) > 1000u) {
                pc_f.d = NULL;
                return 0;
            }
        }
    }
    return 1;
}

/* A piece's flags with DEADLY also set by its own effects (the engine never trusts the flag alone). */
static int pc_deadly(const unsigned char *p) {
    unsigned int k, first = pc_u32(p + 48), n = pc_u16(p + 52);
    if (p[6] & PC_F_DEADLY) {
        return 1;
    }
    for (k = 0; k < n; ++k) {
        if (pc_deadly_code(pc_effect(first + k)[0])) {
            return 1;
        }
    }
    return 0;
}

/* Section 3: a piece the composer may use now in `game`. */
static int pc_usable(int game, const unsigned char *p, unsigned int filters) {
    return (p[7] & (1u << (game - 1))) != 0u && (pc_u32(p + 16) & filters) == 0u && !(sc_gate && pc_deadly(p))
           && (game == 5 || !(p[6] & PC_F_BELIEVERS));
}

/* 2.3: neither piece's NEVER WITH meets the other's TAGS. */
static int pc_compatible(const unsigned char *a, const unsigned char *b) {
    return (pc_u32(a + 24) & pc_u32(b + 28)) == 0u && (pc_u32(b + 24) & pc_u32(a + 28)) == 0u;
}

/* The group `g` (pieces-<name>.pcb) read into pc_buf and checked; 1 when it is there. */
static int pc_load(int g) {
    unsigned int size = 0;
    if (g < 0 || g >= pc_group_count) {
        return 0;
    }
    if (pc_loaded == g && pc_f.d != NULL) {
        return 1;
    }
    pc_loaded = -1;
    pc_f.d = NULL;
#ifdef VVFP_TEST
    if (pc_test_file != NULL) {
        if (!pc_check(pc_test_file, pc_test_size)) {
            return 0;
        }
        pc_loaded = g;
        return 1;
    }
#endif
    if (pc_buf == NULL) {
        pc_buf = (unsigned char *)VirtualAlloc(NULL, PC_FILE_MAX, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (pc_buf == NULL) {
            sc_problem("The procedural events' pieces could not be read: not enough memory.");
            return 0;
        }
    }
    {
        char leaf[PC_GROUP_BYTES + 16];
        wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
        wsprintfA(leaf, "pieces-%s.pcb", pc_groups[g].name);
        if (sc_path(path, leaf) == 0 || !sc_read_w(path, pc_buf, PC_FILE_MAX, &size)) {
            sc_problem("A procedural events' pieces file could not be read (or is past 1 MB): skipped.");
            return 0;
        }
    }
    if (!pc_check(pc_buf, size)) {
        sc_problem("A procedural events' pieces file is damaged or of another version: skipped.");
        return 0;
    }
    pc_loaded = g;
    return 1;
}

/* The usable setups of the loaded file in `game`. */
static int pc_setups(int game, unsigned int filters) {
    unsigned int i;
    int n = 0;
    for (i = 0; i < pc_f.n_piece; ++i) {
        const unsigned char *p = pc_piece((int)i);
        n += p[4] == PC_SETUP && pc_str(pc_u32(p + 36)) != NULL && pc_usable(game, p, filters);
    }
    return n;
}

/* Every pieces-<group>.pcb of the collection's folder, each weighed by its usable setups (section 4).  The count. */
static int pc_index(int game) {
    unsigned int filters = sc_filters_on(game);
    int g;
    pc_group_count = 0;
    pc_loaded = -1;
    if (!sc_collection_on(game)) {
        return 0;
    }
#ifdef VVFP_TEST
    if (pc_test_file != NULL) {
        if (story_grow((void **)&pc_groups, &pc_group_cap, 1, sizeof(pc_group))) {
            lstrcpyA(pc_groups[0].name, "test");
            pc_group_count = 1;
        }
        goto weigh;
    }
#endif
    {
        wchar_t pattern[VVFP_PATCHER_FILES_PATH_CAP];
        WIN32_FIND_DATAW found;
        HANDLE find;
        if (sc_path(pattern, "pieces-*.pcb") == 0
            || (find = FindFirstFileW(pattern, &found)) == INVALID_HANDLE_VALUE) {
            return 0;
        }
        do {
            char name[PC_GROUP_BYTES];
            int n = 0, ok = 1, k;
            const wchar_t *w = found.cFileName + 7;          /* past "pieces-" */
            for (k = 0; w[k] != L'\0' && !(w[k] == L'.' && lstrcmpiW(w + k, L".pcb") == 0); ++k) {
                wchar_t c = w[k];
                if (n + 1 >= 25 || !((c >= L'a' && c <= L'z') || (c >= L'0' && c <= L'9') || c == L'_')) {
                    ok = 0;
                    break;
                }
                name[n++] = (char)c;
            }
            name[n] = '\0';
            if (!ok || n == 0 || (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                sc_problem("A procedural events' pieces file's name is not pieces-<letters, digits or _>.pcb: skipped.");
                continue;
            }
            if (!story_grow((void **)&pc_groups, &pc_group_cap, pc_group_count + 1, sizeof(pc_group))) {
                sc_problem("The procedural events' index could not grow: not enough memory. Some files were left out.");
                break;
            }
            lstrcpynA(pc_groups[pc_group_count].name, name, PC_GROUP_BYTES);
            pc_groups[pc_group_count++].weight = 0;
        } while (FindNextFileW(find, &found));
        FindClose(find);
    }
#ifdef VVFP_TEST
weigh:
#endif
    for (g = 0; g < pc_group_count; ++g) {
        pc_groups[g].weight = pc_load(g) ? pc_setups(game, filters) : 0;
    }
    return pc_group_count;
}

/* ---- The composer (procedural-pieces.md section 3) --------------------------------------------------------- */

/* random_below(n): the game's own routine (no roll when n <= 1); the Pick list's check a private generator. */
static int pc_roll(int n) {
    if (n <= 1) {
        return 0;
    }
    if (pc_dry) {
        pc_dry_state ^= pc_dry_state << 13;
        pc_dry_state ^= pc_dry_state >> 17;
        pc_dry_state ^= pc_dry_state << 5;
        return (int)(pc_dry_state % (unsigned int)n);
    }
    return sc_rand(pc_game, n);
}

/* A weighted pick among `count` candidates (their weights): the first, in their order, whose running sum passes
   r = random_below(total).  -1 when there is none. */
static int pc_weighted(const int *weight, int count) {
    int total = 0, k, r;
    for (k = 0; k < count; ++k) {
        total += weight[k];
    }
    if (count <= 0 || total <= 0) {
        return -1;
    }
    r = pc_roll(total);
    for (k = 0; k < count; ++k) {
        if (r < weight[k]) {
            return k;
        }
        r -= weight[k];
    }
    return count - 1;
}

/* One composition: the pieces chosen (indices into the file). */
typedef struct {
    int setup;
    int approaches;
    int approach[PC_MAX_APPROACHES];
    int outcomes[PC_MAX_APPROACHES];
    int outcome[PC_MAX_APPROACHES][PC_MAX_OUTCOMES];
    int weight[PC_MAX_APPROACHES][PC_MAX_OUTCOMES];   /* each outcome's link weight for its approach */
    int flavour, frame;
} pc_pick;

/* A merged role (2.4). */
typedef struct {
    const char *name;
    unsigned char kind, sex, min_age, max_age, special, flags, all_optional, harm, speaks;
} pc_role;

static pc_role pc_roles[CG_MAX_ROLES];
static int pc_role_count;
static int pc_chosen[2 + PC_MAX_APPROACHES * (1 + PC_MAX_OUTCOMES) + 2];
static int pc_chosen_count;

static int pc_compatible_all(const unsigned char *p) {
    int k;
    for (k = 0; k < pc_chosen_count; ++k) {
        if (!pc_compatible(p, pc_piece(pc_chosen[k]))) {
            return 0;
        }
    }
    return 1;
}

/* The approach piece `a`'s link weight in outcome `o` (0: `o` does not answer it). */
static int pc_link_weight(const unsigned char *o, const unsigned char *a) {
    unsigned int k, first = pc_u32(o + 56), n = pc_u16(o + 60);
    const char *id = pc_str(pc_u32(a));
    for (k = 0; k < n; ++k) {
        if (lstrcmpA(pc_str(pc_u32(pc_link(first + k))), id) == 0) {
            return (int)pc_u32(pc_link(first + k) + 4);
        }
    }
    return 0;
}

/* Whether approach `a` has a usable outcome linking it in the file. */
static int pc_answered(int game, const unsigned char *a, unsigned int filters) {
    unsigned int i;
    for (i = 0; i < pc_f.n_piece; ++i) {
        const unsigned char *o = pc_piece((int)i);
        if (o[4] == PC_OUTCOME && pc_usable(game, o, filters) && pc_link_weight(o, a) > 0) {
            return 1;
        }
    }
    return 0;
}

/* Steps 1-5 with the setup `fixed` (-1: drawn; `skip[i]` setups left out by earlier tries).  1 when the pieces are
   chosen. */
static int pc_choose(int game, unsigned int filters, int fixed, const unsigned char *skip, pc_pick *c) {
    static int *cand, *weight;
    static int cand_cap, weight_cap;
    int i, k, n, count, want;
    const unsigned char *setup;
    memset(c, 0, sizeof *c);
    c->setup = c->flavour = c->frame = -1;
    pc_chosen_count = 0;
    if (!story_grow((void **)&cand, &cand_cap, (int)pc_f.n_piece + 1, sizeof(int))
        || !story_grow((void **)&weight, &weight_cap, (int)pc_f.n_piece + 1, sizeof(int))) {
        return 0;
    }
    /* 1. The setup. */
    if (fixed >= 0) {
        c->setup = fixed;
    } else {
        count = 0;
        for (i = 0; i < (int)pc_f.n_piece; ++i) {
            const unsigned char *p = pc_piece(i);
            if (p[4] == PC_SETUP && !skip[i] && pc_str(pc_u32(p + 36)) != NULL && pc_usable(game, p, filters)) {
                cand[count] = i;
                weight[count++] = (int)pc_u16(p + 46);
            }
        }
        k = pc_weighted(weight, count);
        if (k < 0) {
            return 0;
        }
        c->setup = cand[k];
    }
    setup = pc_piece(c->setup);
    pc_chosen[pc_chosen_count++] = c->setup;
    /* 2. The approaches: n rolled first, then each weighted, without replacement, compatible with every piece so
       far. */
    want = 2 + pc_roll(3);
    for (n = 0; n < want; ++n) {
        count = 0;
        for (i = 0; i < (int)pc_f.n_piece; ++i) {
            const unsigned char *p = pc_piece(i);
            int taken = 0;
            for (k = 0; k < c->approaches; ++k) {
                taken |= c->approach[k] == i;
            }
            if (p[4] == PC_APPROACH && !taken && pc_u32(p + 12) == pc_u32(setup + 12) && pc_u32(p + 36) != PC_STR_NONE
                && pc_usable(game, p, filters) && pc_compatible_all(p) && pc_answered(game, p, filters)) {
                cand[count] = i;
                weight[count++] = (int)pc_u16(p + 46);
            }
        }
        k = pc_weighted(weight, count);
        if (k < 0) {
            break;
        }
        c->approach[c->approaches++] = cand[k];
        pc_chosen[pc_chosen_count++] = cand[k];
    }
    if (c->approaches < 2) {
        return 0;
    }
    /* 3. The outcomes of each approach, in the order picked: m rolled first, then each by its link weight, without
       replacement, compatible with the setup and that approach. */
    for (n = 0; n < c->approaches; ++n) {
        const unsigned char *a = pc_piece(c->approach[n]);
        int m = 1 + pc_roll(3), j;
        for (j = 0; j < m; ++j) {
            count = 0;
            for (i = 0; i < (int)pc_f.n_piece; ++i) {
                const unsigned char *o = pc_piece(i);
                int taken = 0, w;
                for (k = 0; k < c->outcomes[n]; ++k) {
                    taken |= c->outcome[n][k] == i;
                }
                if (o[4] != PC_OUTCOME || taken || !pc_usable(game, o, filters) || (w = pc_link_weight(o, a)) <= 0
                    || !pc_compatible(o, setup) || !pc_compatible(o, a)) {
                    continue;
                }
                cand[count] = i;
                weight[count++] = w;
            }
            k = pc_weighted(weight, count);
            if (k < 0) {
                break;
            }
            c->outcome[n][c->outcomes[n]] = cand[k];
            c->weight[n][c->outcomes[n]++] = weight[k];
        }
    }
    for (n = 0; n < c->approaches; ++n) {
        for (k = 0; k < c->outcomes[n]; ++k) {
            pc_chosen[pc_chosen_count++] = c->outcome[n][k];
        }
    }
    /* 4. The flavour line (half the time), of the setup's mood; 5. the frame (three times in ten). */
    for (n = 0; n < 2; ++n) {
        int kind = n == 0 ? PC_FLAVOUR : PC_FRAME;
        if (pc_roll(100) >= (n == 0 ? 50 : 30)) {
            continue;
        }
        count = 0;
        for (i = 0; i < (int)pc_f.n_piece; ++i) {
            const unsigned char *p = pc_piece(i);
            if (p[4] == kind && (kind != PC_FLAVOUR || p[5] == setup[5]) && pc_u32(p + 32) != PC_STR_NONE
                && pc_usable(game, p, filters) && pc_compatible_all(p)) {
                cand[count] = i;
                weight[count++] = (int)pc_u16(p + 46);
            }
        }
        k = pc_weighted(weight, count);
        if (k >= 0) {
            if (n == 0) {
                c->flavour = cand[k];
            } else {
                c->frame = cand[k];
            }
            pc_chosen[pc_chosen_count++] = cand[k];
        }
    }
    return 1;
}

/* A role by its name among the merged ones, -1 none. */
static int pc_role_of(const char *name) {
    int r;
    for (r = 0; r < pc_role_count; ++r) {
        if (lstrcmpA(pc_roles[r].name, name) == 0) {
            return r;
        }
    }
    return -1;
}

static int pc_harmful(const unsigned char *e) {
    int a = (int)pc_u32(e + 4), b = (int)pc_u32(e + 8);
    switch (e[0]) {
    case CGE_KILL: case CGE_VANISH: case CGE_DIE_UNRECOVERED: case CGE_BABY_LOST: case CGE_BIRTH_THEN_DIE:
    case CGE_DELIVER_EARLY: case CGE_SICK:
    case CGE_APOSTASY:                 /* a believer made a Heathen, as cg_effect_harmful (Codex, #771) */
        return 1;
    case CGE_HEALTH: return b < 100;
    case CGE_HEALTH_CHANGE: case CGE_SKILL: case CGE_MOOD: return a < 0;
    case CGE_PREF: return (e[2] & 4u) && !(e[2] & CG_PREF_REMOVE);
    default: return 0;
    }
}

/* Piece `pi`'s slots merged into pc_roles (2.4), each slot's role into map[]; `optional_new` makes the roles it adds
   optional (an outcome's own).  0 when a merge cannot hold or there are more than CG_MAX_ROLES roles. */
static int pc_merge(int pi, int optional_new, unsigned char *map) {
    const unsigned char *p = pc_piece(pi);
    unsigned int k, first = pc_u32(p + 40), n = pc_u16(p + 44), band = pc_u16(p + 54);
    for (k = 0; k < n; ++k) {
        const unsigned char *s = pc_slot(first + k);
        const char *name = pc_str(pc_u32(s));
        unsigned char min_age = s[6], max_age = s[7], sex = s[5], special = s[8];
        int r = pc_role_of(name);
        pc_role *role;
        if (special == PC_SPECIAL_CARRIER) {
            min_age = min_age < 18 ? 18 : min_age;          /* a carrier: 18 or more, born female unless flag bit 5 */
            if (!(s[9] & PC_S_ANY_BIRTH_SEX)) {
                sex = 2;
            }
            special = 0;
        }
        if (band == 1u) {
            min_age = min_age < 18 ? 18 : min_age;          /* romance: every role 18 or more */
        } else if (band == 2u) {
            min_age = min_age < 14 ? 14 : min_age;          /* ... or every role 14-17 */
            max_age = max_age == 0 || max_age > 17 ? 17 : max_age;
        }
        if (r < 0) {
            if (pc_role_count >= CG_MAX_ROLES) {
                return 0;
            }
            r = pc_role_count++;
            role = &pc_roles[r];
            memset(role, 0, sizeof *role);
            role->name = name;
            role->kind = s[4];
            role->sex = sex;
            role->min_age = min_age;
            role->max_age = max_age;
            role->special = special;
            role->flags = s[9];
            role->all_optional = (unsigned char)(optional_new || (s[9] & PC_S_OPTIONAL));
        } else {
            role = &pc_roles[r];
            if (role->kind != s[4] || (role->sex != 0 && sex != 0 && role->sex != sex)
                || (role->special != 0 && special != 0 && role->special != special)) {
                return 0;
            }
            role->sex = role->sex != 0 ? role->sex : sex;
            role->special = role->special != 0 ? role->special : special;
            role->min_age = min_age > role->min_age ? min_age : role->min_age;
            if (max_age != 0 && (role->max_age == 0 || max_age < role->max_age)) {
                role->max_age = max_age;
            }
            role->flags |= s[9];
            /* optional only when every slot merged into it is (2.4); an outcome's never makes a needed role
               optional */
            role->all_optional = (unsigned char)(role->all_optional && (optional_new || (s[9] & PC_S_OPTIONAL)));
        }
        if (role->max_age != 0 && role->max_age < role->min_age) {
            return 0;
        }
        map[k] = (unsigned char)r;
    }
    return 1;
}

/* Whether piece `pi` declares a slot `name` that is not optional (-1: no piece). */
static int pc_declares(int pi, const char *name) {
    const unsigned char *p;
    unsigned int k, first, n;
    if (pi < 0) {
        return 0;
    }
    p = pc_piece(pi);
    first = pc_u32(p + 40);
    n = pc_u16(p + 44);
    for (k = 0; k < n; ++k) {
        const unsigned char *s = pc_slot(first + k);
        if (!(s[9] & PC_S_OPTIONAL) && lstrcmpA(pc_str(pc_u32(s)), name) == 0) {
            return 1;
        }
    }
    return 0;
}

/* Whether every slot of outcome `pi` is a needed slot of the setup, of its own approach `ai`, of the flavour line or
   of the frame (a "plain" outcome: it can be cast whenever its approach can). */
static int pc_plain(const pc_pick *c, int pi, int ai) {
    const unsigned char *p = pc_piece(pi);
    unsigned int k, first = pc_u32(p + 40), n = pc_u16(p + 44);
    for (k = 0; k < n; ++k) {
        const char *name = pc_str(pc_u32(pc_slot(first + k)));
        if (!pc_declares(c->setup, name) && !pc_declares(ai, name) && !pc_declares(c->flavour, name)
            && !pc_declares(c->frame, name)) {
            return 0;
        }
    }
    return 1;
}

/* ---- The graph writer: a version 6 .cieg in memory (cie-v6-binary.md) ---------------------------------------- */

typedef struct {
    unsigned char *out;
    unsigned int cap;
    const char *str[PC_MAX_STRINGS];
    int n_str;
    int bad;
} pc_writer;

static unsigned int pc_s(pc_writer *w, const char *s) {
    int k;
    if (s == NULL) {
        return CG_NONE;
    }
    for (k = 0; k < w->n_str; ++k) {
        if (lstrcmpA(w->str[k], s) == 0) {
            return (unsigned int)k;
        }
    }
    if (w->n_str >= PC_MAX_STRINGS) {
        w->bad = 1;
        return CG_NONE;
    }
    w->str[w->n_str] = s;
    return (unsigned int)w->n_str++;
}

/* The composition `c` as a .cieg into `out` (at most `cap` bytes): its size, 0 when it cannot be written.  `group`
   names the file in the graph's collection block. */
static unsigned int pc_write(const pc_pick *c, const char *group, unsigned char *out, unsigned int cap) {
    static char start_text[CG_TEXT_MAX + 2];
    static char node_id[1 + PC_MAX_APPROACHES * (1 + PC_MAX_OUTCOMES)][16];
    static char block[PC_GROUP_BYTES + 160];
    static unsigned char map[2 + PC_MAX_APPROACHES * (1 + PC_MAX_OUTCOMES) + 2][PC_MAX_SLOTS];
    pc_writer w;
    const unsigned char *setup = pc_piece(c->setup);
    unsigned int notes = 0, at, size, o_role, o_node, o_child, o_effect, o_cond, o_str, blob;
    int n, k, r, n_node, n_child = 0, n_effect = 0, n_cond = 0, child, effect, piece_at = 0;
    int kept[PC_MAX_APPROACHES], n_kept = 0;
    unsigned char *h = out;
    int out_base;
    memset(&w, 0, sizeof w);
    pc_role_count = 0;
    /* 6. An approach is kept when one of its outcomes is plain (can be cast whenever the approach can); at least
       two are kept. */
    for (n = 0; n < c->approaches; ++n) {
        for (k = 0; k < c->outcomes[n] && !pc_plain(c, c->outcome[n][k], c->approach[n]); ++k) {
        }
        if (k < c->outcomes[n]) {
            kept[n_kept++] = n;
        }
    }
    if (n_kept < 2) {
        return 0;
    }
    /* The needed roles: the setup's, the kept approaches', the flavour's and the frame's slots. */
    if (!pc_merge(c->setup, 0, map[piece_at++])) {
        return 0;
    }
    for (k = 0; k < n_kept; ++k) {
        if (!pc_merge(c->approach[kept[k]], 0, map[piece_at++])) {
            return 0;
        }
    }
    if ((c->flavour >= 0 && !pc_merge(c->flavour, 0, map[piece_at++]))
        || (c->frame >= 0 && !pc_merge(c->frame, 0, map[piece_at++]))) {
        return 0;
    }
    out_base = piece_at;               /* the outcomes' maps from here, in the kept approaches' order */
    /* The kept approaches' outcomes: their own roles optional (a branch child holds only when they are cast). */
    for (k = 0; k < n_kept; ++k) {
        for (n = 0; n < c->outcomes[kept[k]]; ++n) {
            if (!pc_merge(c->outcome[kept[k]][n], 1, map[piece_at++])) {
                return 0;
            }
            n_effect += (int)pc_u16(pc_piece(c->outcome[kept[k]][n]) + 52);
        }
    }
    /* The first role: a villager the event needs, or a stranger (G7). */
    for (r = 0; r < pc_role_count && !(pc_roles[r].kind == 0 && !pc_roles[r].all_optional); ++r) {
    }
    if (r == pc_role_count) {
        for (r = 0; r < pc_role_count && pc_roles[r].kind != 1; ++r) {
        }
    }
    if (pc_role_count > 0 && r == pc_role_count) {
        return 0;
    }
    if (r > 0 && r < pc_role_count) {
        /* swap role r to the front, and every map with it */
        pc_role t = pc_roles[0];
        int i;
        pc_roles[0] = pc_roles[r];
        pc_roles[r] = t;
        for (i = 0; i < piece_at; ++i) {
            for (k = 0; k < PC_MAX_SLOTS; ++k) {
                map[i][k] = map[i][k] == 0 ? (unsigned char)r : map[i][k] == (unsigned char)r ? 0 : map[i][k];
            }
        }
    }
    /* Harm (cie-v6-binary.md 7): a role a harmful effect acts on. */
    {
        int i = out_base;
        for (k = 0; k < n_kept; ++k) {
            for (n = 0; n < c->outcomes[kept[k]]; ++n, ++i) {
                const unsigned char *o = pc_piece(c->outcome[kept[k]][n]);
                unsigned int e, first = pc_u32(o + 48), count = pc_u16(o + 52);
                for (e = 0; e < count; ++e) {
                    const unsigned char *fx = pc_effect(first + e);
                    if (!pc_role_kept(fx[1]) && pc_harmful(fx)) {
                        pc_roles[map[i][fx[1]]].harm = 1;
                    }
                }
            }
        }
        for (r = 0; r < pc_role_count; ++r) {
            pc_roles[r].harm |= (pc_roles[r].flags & PC_S_HARM) != 0;
        }
    }
    /* The start text: the content note, the flavour line, the setup's text and the frame line, each its own
       paragraph. */
    start_text[0] = '\0';
    /* the notes of the pieces the event holds (a dropped approach's are not) */
    notes = pc_u32(setup + 20) | (c->flavour >= 0 ? pc_u32(pc_piece(c->flavour) + 20) : 0u)
            | (c->frame >= 0 ? pc_u32(pc_piece(c->frame) + 20) : 0u);
    for (k = 0; k < n_kept; ++k) {
        notes |= pc_u32(pc_piece(c->approach[kept[k]]) + 20);
        for (n = 0; n < c->outcomes[kept[k]]; ++n) {
            notes |= pc_u32(pc_piece(c->outcome[kept[k]][n]) + 20);
        }
    }
    if (pc_note_on && (notes & 0x7Fu) != 0u) {
        lstrcpyA(start_text, "Content note: ");
        for (k = 0, n = 0; k < 7; ++k) {
            if (notes & (1u << k)) {
                if (n++ > 0) {
                    lstrcatA(start_text, ", ");
                }
                lstrcatA(start_text, PC_NOTE_LABELS[k]);
            }
        }
        lstrcatA(start_text, "\n");
    }
    {
        const char *parts[3];
        parts[0] = c->flavour >= 0 ? pc_str(pc_u32(pc_piece(c->flavour) + 32)) : NULL;
        parts[1] = pc_str(pc_u32(setup + 32));
        parts[2] = c->frame >= 0 ? pc_str(pc_u32(pc_piece(c->frame) + 32)) : NULL;
        if (parts[1] == NULL) {
            return 0;
        }
        for (k = 0, n = 0; k < 3; ++k) {
            if (parts[k] == NULL) {
                continue;
            }
            if (lstrlenA(start_text) + lstrlenA(parts[k]) + 2 > CG_TEXT_MAX) {
                return 0;
            }
            if (n++ > 0) {
                lstrcatA(start_text, "\n");
            }
            lstrcatA(start_text, parts[k]);
        }
    }
    if (lstrlenA(group) >= PC_GROUP_BYTES || lstrlenA(pc_str(pc_u32(setup))) > 100) {
        return 0;
    }
    wsprintfA(block, "{\"procedural\":\"%s/%s\"}", group, pc_str(pc_u32(setup)));
    /* The counts. */
    n_node = 1;
    for (k = 0; k < n_kept; ++k) {
        n_node += 1 + c->outcomes[kept[k]];
        n_child += 1 + c->outcomes[kept[k]];
    }
    /* Conditions: per outcome child, its optional roles (op 2) and, when more than one, their `all`; its guard: the
       protected harmed roles (op 9) and their `all`. */
    {
        int i = out_base;
        for (k = 0; k < n_kept; ++k) {
            for (n = 0; n < c->outcomes[kept[k]]; ++n, ++i) {
                const unsigned char *o = pc_piece(c->outcome[kept[k]][n]);
                unsigned int s, opt = 0, harmed = 0, e, first = pc_u32(o + 48), count = pc_u16(o + 52);
                int bits;
                for (s = 0; s < pc_u16(o + 44); ++s) {
                    if (pc_roles[map[i][s]].all_optional) {
                        opt |= 1u << map[i][s];
                    }
                }
                for (e = 0; e < count; ++e) {
                    const unsigned char *fx = pc_effect(first + e);
                    if (!pc_role_kept(fx[1]) && pc_harmful(fx) && pc_roles[map[i][fx[1]]].special == 0) {
                        harmed |= 1u << map[i][fx[1]];
                    }
                }
                for (bits = 0; opt != 0u; opt &= opt - 1u) {
                    ++bits;
                }
                n_cond += bits + (bits > 1);
                for (bits = 0; harmed != 0u; harmed &= harmed - 1u) {
                    ++bits;
                }
                n_cond += bits + (bits > 1);
            }
        }
    }
    /* The layout: header, roles, nodes, children, effects, conds, (variants, patches, pools, items: none),
       strings. */
    o_role = CG_HEADER_V6;
    o_node = o_role + 16u * (unsigned int)pc_role_count;
    o_child = o_node + 28u * (unsigned int)n_node;
    o_effect = o_child + 12u * (unsigned int)n_child;
    o_cond = o_effect + 16u * (unsigned int)n_effect;
    o_str = o_cond + 8u * (unsigned int)n_cond;
    if (o_str > cap || n_node > CG_MAX_NODES) {
        return 0;
    }
    memset(out, 0, o_str);
    /* Roles. */
    for (r = 0; r < pc_role_count; ++r) {
        unsigned char *rr = out + o_role + 16u * (unsigned int)r;
        const pc_role *role = &pc_roles[r];
        pc_put16(rr + 4, pc_s(&w, role->name));
        pc_put16(rr + 10, CG_NONE);
        if (role->kind == 1) {
            rr[0] = CG_ROLE_STRANGER;
            rr[1] = CG_STRANGER_NAMED;
            rr[2] = role->sex != 0 ? role->sex : 3;
            continue;
        }
        rr[0] = CG_ROLE_VILLAGER;
        rr[1] = (unsigned char)((role->all_optional ? CG_ROLE_OPTIONAL : 0)
                                | ((role->flags & PC_S_CONVERSION) ? 0 : CG_ROLE_BELIEVERS));
        if (role->harm) {
            /* harm-capable: kept from the protected villagers -- a special role (it MUST be that villager) is the
               author's "allow" (cie-v6-binary.md 7) */
            rr[1] |= role->special != 0 ? CG_ROLE_HARM
                                        : (unsigned char)(CG_ROLE_HARM | CG_ROLE_PROTECTED | CG_ROLE_NURSING
                                                          | CG_ROLE_SPECIAL);
        }
        rr[2] = role->sex;
        rr[3] = role->min_age;          /* 0..120 (story_graph.inc cg_load; elders of 90 and more exist) */
        rr[8] = role->max_age;
        rr[9] = role->special;
        rr[13] = (role->flags & PC_S_SPEAKS) ? (unsigned char)CG_ROLE_SPEAKS : 0;
    }
    /* Nodes, children, effects, conditions. */
    child = 0;
    effect = 0;
    {
        int i = out_base;
        int cond_at = 0, next_node = 1;
        unsigned char *q = out + o_node;
        lstrcpyA(node_id[0], "start");
        q[0] = CG_QUESTION;
        pc_put16(q + 4, pc_s(&w, node_id[0]));
        pc_put16(q + 6, pc_s(&w, start_text));
        pc_put16(q + 8, 0);
        pc_put16(q + 12, 0);
        pc_put16(q + 14, (unsigned int)n_kept);
        pc_put16(q + 16, CG_NONE);
        pc_put16(q + 18, 0);
        pc_put16(q + 22, CG_NONE);
        pc_put16(q + 24, CG_NONE);
        pc_put16(q + 26, CG_NONE);
        child = n_kept;                /* the question's choices come first */
        for (k = 0; k < n_kept; ++k) {
            const unsigned char *a = pc_piece(c->approach[kept[k]]);
            unsigned char *ch = out + o_child + 12u * (unsigned int)k;
            unsigned char *an = out + o_node + 28u * (unsigned int)next_node;
            int a_node = next_node++, j;
            pc_put16(ch, (unsigned int)a_node);
            pc_put16(ch + 2, 1);
            pc_put16(ch + 4, CG_NONE);
            pc_put16(ch + 6, CG_NONE);
            pc_put16(ch + 8, pc_s(&w, pc_str(pc_u32(a + 36))));
            pc_put16(ch + 10, CG_NONE);
            wsprintfA(node_id[a_node], "a%d", k + 1);
            /* an approach with no text of its own is a silent branch to its outcomes */
            an[0] = pc_str(pc_u32(a + 32)) != NULL ? (unsigned char)CG_POPUP : (unsigned char)CG_BRANCH;
            pc_put16(an + 4, pc_s(&w, node_id[a_node]));
            pc_put16(an + 6, an[0] == CG_POPUP ? pc_s(&w, pc_str(pc_u32(a + 32))) : CG_NONE);
            pc_put16(an + 12, (unsigned int)child);
            pc_put16(an + 14, (unsigned int)c->outcomes[kept[k]]);
            pc_put16(an + 16, CG_NONE);
            pc_put16(an + 22, CG_NONE);
            pc_put16(an + 24, CG_NONE);
            pc_put16(an + 26, CG_NONE);
            for (j = 0; j < c->outcomes[kept[k]]; ++j, ++i) {
                const unsigned char *o = pc_piece(c->outcome[kept[k]][j]);
                unsigned char *ochild = out + o_child + 12u * (unsigned int)child++;
                unsigned char *on = out + o_node + 28u * (unsigned int)next_node;
                unsigned int s, opt = 0, harmed = 0, e, first = pc_u32(o + 48), count = pc_u16(o + 52);
                int o_node_i = next_node++, pass;
                pc_put16(ochild, (unsigned int)o_node_i);
                pc_put16(ochild + 2, (unsigned int)c->weight[kept[k]][j]);
                pc_put16(ochild + 6, CG_NONE);
                pc_put16(ochild + 8, CG_NONE);
                for (s = 0; s < pc_u16(o + 44); ++s) {
                    if (pc_roles[map[i][s]].all_optional) {
                        opt |= 1u << map[i][s];
                    }
                }
                for (e = 0; e < count; ++e) {
                    const unsigned char *fx = pc_effect(first + e);
                    if (!pc_role_kept(fx[1]) && pc_harmful(fx) && pc_roles[map[i][fx[1]]].special == 0) {
                        harmed |= 1u << map[i][fx[1]];
                    }
                }
                /* pass 0: the child's cond (its optional roles cast), pass 1: its guard (harmable) */
                for (pass = 0; pass < 2; ++pass) {
                    unsigned int mask = pass == 0 ? opt : harmed, m;
                    int bits = 0, base = cond_at;
                    for (m = mask; m != 0u; m &= m - 1u) {
                        ++bits;
                    }
                    if (bits == 0) {
                        pc_put16(ochild + (pass == 0 ? 4 : 10), CG_NONE);
                        continue;
                    }
                    pc_put16(ochild + (pass == 0 ? 4 : 10), (unsigned int)base);
                    if (bits > 1) {
                        /* an `all` comes before its operands (the loader: operands after it) */
                        unsigned char *cd = out + o_cond + 8u * (unsigned int)cond_at++;
                        cd[0] = CGC_ALL;
                        cd[1] = (unsigned char)bits;
                        pc_put16(cd + 2, (unsigned int)cond_at);
                    }
                    for (r = 0; r < pc_role_count; ++r) {
                        if (mask & (1u << r)) {
                            unsigned char *cd = out + o_cond + 8u * (unsigned int)cond_at++;
                            cd[0] = pass == 0 ? CGC_ROLE : CGC_HARMABLE;
                            cd[1] = 0;
                            pc_put16(cd + 2, (unsigned int)r);
                            pc_put16(cd + 4, 0);
                        }
                    }
                }
                wsprintfA(node_id[o_node_i], "a%do%d", k + 1, j + 1);
                on[0] = CG_POPUP;
                on[1] = an[0] == CG_POPUP; /* the outcome continues the approach's popup */
                on[2] = an[0] == CG_POPUP; /* ... as a paragraph of its own */
                on[3] = (o[6] & PC_F_AUTO_LINES) ? (unsigned char)CG_NODE_AUTO_TEXT : 0;
                pc_put16(on + 4, pc_s(&w, node_id[o_node_i]));
                pc_put16(on + 6, pc_s(&w, pc_str(pc_u32(o + 32))));
                pc_put16(on + 12, 0);
                pc_put16(on + 14, 0);
                pc_put16(on + 16, CG_NONE);
                pc_put16(on + 18, (unsigned int)effect);
                pc_put16(on + 20, count);
                pc_put16(on + 22, CG_NONE);
                pc_put16(on + 24, CG_NONE);
                pc_put16(on + 26, CG_NONE);
                for (e = 0; e < count; ++e) {
                    const unsigned char *fx = pc_effect(first + e);
                    unsigned char *ef = out + o_effect + 16u * (unsigned int)effect++;
                    unsigned int a_value = pc_u32(fx + 4);
                    memcpy(ef, fx, 12);
                    ef[1] = pc_role_kept(fx[1]) ? fx[1] : map[i][fx[1]];
                    if ((fx[0] == CGE_PREGNANT || fx[0] == CGE_NURSING || fx[0] == CGE_BODY_SWAP)
                        && a_value != 255u && !pc_role_kept(a_value)) {
                        /* the partner / the other role: a local slot too */
                        if (a_value >= pc_u16(o + 44)) {
                            return 0;
                        }
                        pc_put32(ef + 4, map[i][a_value]);
                    }
                    pc_put16(ef + 12, pc_u32(fx + 12) == PC_STR_NONE ? CG_NONE : pc_s(&w, pc_str(pc_u32(fx + 12))));
                    {
                        /* the last H: a group's N, its skill's name (a string), change_age's cap (v2) */
                        unsigned int extra = pc_effect_extra(fx);
                        pc_put16(ef + 14, fx[1] == CG_ROLE_GROUP && fx[3] == CG_GROUP_SKILL ? pc_s(&w, pc_str(extra))
                                                                                         : extra);
                    }
                }
            }
        }
        if (cond_at != n_cond || child != n_child || next_node != n_node || effect != n_effect) {
            return 0;
        }
    }
    /* The header. */
    memcpy(h, "CIEG", 4);
    pc_put16(h + 4, 6);
    pc_put16(h + 6, CG_HEADER_V6);
    pc_put32(h + 16, 1u << (pc_game - 1));
    pc_put16(h + 20, pc_s(&w, pc_str(pc_u32(setup + 36))));
    pc_put16(h + 22, 0);
    pc_put16(h + 24, 0);
    pc_put16(h + 26, (unsigned int)pc_role_count);
    pc_put16(h + 28, (unsigned int)n_node);
    pc_put16(h + 30, (unsigned int)n_child);
    pc_put16(h + 32, (unsigned int)n_effect);
    pc_put16(h + 34, (unsigned int)n_cond);
    pc_put16(h + 36, 0);
    pc_put16(h + 40, 0);
    pc_put16(h + 42, CG_NONE);
    pc_put32(h + 44, o_role);
    pc_put32(h + 48, o_node);
    pc_put32(h + 52, o_child);
    pc_put32(h + 56, o_effect);
    pc_put32(h + 60, o_cond);
    pc_put32(h + 64, o_str);       /* no variants */
    pc_put32(h + 68, o_str);       /* no patches */
    pc_put32(h + 76, o_str);       /* no pools */
    pc_put32(h + 80, o_str);       /* no items */
    pc_put16(h + 84, 0);
    pc_put16(h + 86, 0);
    pc_put16(h + 88, 1);           /* the protected guard is on */
    pc_put16(h + 90, pc_s(&w, block));
    pc_put16(h + 92, 0);
    pc_put16(h + 94, 0);
    if (w.bad) {
        return 0;
    }
    /* The strings: the offsets, then the NUL-ended texts. */
    pc_put16(h + 38, (unsigned int)w.n_str);
    pc_put32(h + 72, o_str);
    blob = o_str + 4u * (unsigned int)w.n_str;
    if (blob > cap) {
        return 0;
    }
    at = 0;
    for (k = 0; k < w.n_str; ++k) {
        unsigned int len = (unsigned int)lstrlenA(w.str[k]) + 1u;
        if (blob + at + len > cap) {
            return 0;
        }
        pc_put32(out + o_str + 4u * (unsigned int)k, at);
        memcpy(out + blob + at, w.str[k], len);
        at += len;
    }
    size = blob + at;
    pc_put32(h + 8, size);
    pc_put32(h + 12, 0);
    pc_put32(h + 12, cg_crc32(out, size, 12));
    return size;
}

/* ---- Composing and queueing -------------------------------------------------------------------------------- */

static unsigned char pc_graph[CG_SHIPPED_FILE];

/* A composition from the loaded group `g` in `game`, with the setup `fixed` (-1: drawn, up to PC_TRIES setups),
   written into pc_graph and handed to `arm` (which queues or checks it).  1 when `arm` took one. */
static int pc_compose(int game, int g, int fixed, int (*arm)(int game, unsigned int size)) {
    static unsigned char *skip;
    static int skip_cap;
    unsigned int filters = sc_filters_on(game);
    int tries;
    pc_pick c;
    if (!pc_load(g) || !story_grow((void **)&skip, &skip_cap, (int)pc_f.n_piece + 1, 1)) {
        return 0;
    }
    memset(skip, 0, (size_t)pc_f.n_piece + 1);
    pc_game = game;
    cg_installed_load();
    pc_note_on = (char)(cg_installed_state == 1 && cg_installed_has(game, "island_event_content_notes"));
    for (tries = 0; tries < PC_TRIES; ++tries) {
        unsigned int size;
        if (!pc_choose(game, filters, fixed, skip, &c)) {
            if (c.setup < 0) {
                return 0;              /* no setup left */
            }
        } else if ((size = pc_write(&c, pc_groups[g].name, pc_graph, sizeof pc_graph)) != 0u && arm(game, size)) {
            return 1;
        }
        if (fixed >= 0) {
            continue;                  /* the same setup again: other approaches and outcomes */
        }
        skip[c.setup] = 1;             /* 8: that setup left out */
    }
    return 0;
}

static int pc_arm_natural(int game, unsigned int size) {
    return cg_queue_origin(game, pc_graph, size, CG_ORIGIN_NATURAL, CG_CAST_STRICT);
}

static int pc_arm_pick(int game, unsigned int size) {
    return cg_queue_origin(game, pc_graph, size, CG_ORIGIN_PICK, CG_CAST_STRICT);
}

static const char *pc_last_refusal;

/* The Pick list's check: the graph loaded and its cast checked (strict), nothing queued. */
static int pc_arm_check(int game, unsigned int size) {
    unsigned int planned = 0;
    int keep_cast = cg_cast_now, keep_origin = cg_origin_now;
    const char *refusal;
    if (cg.phase != CG_IDLE && cg.phase != CG_DONE) {
        pc_last_refusal = "another branching island event is still running";
        return 0;
    }
    if (!cg_bytes_room(size)) {
        return 0;
    }
    memcpy(cg_bytes, pc_graph, size);
    cg_bytes_size = size;
    if (!cg_load(&cg_g, cg_bytes, size)) {
        cg_bytes_size = 0;
        pc_last_refusal = "its pieces can not be read: install the patch again";
        return 0;
    }
    cg_cast_now = CG_CAST_STRICT;
    cg_origin_now = CG_ORIGIN_PICK;
    refusal = cg_refusal(game, &planned);
    cg_cast_now = keep_cast;
    cg_origin_now = keep_origin;
    cg_bytes_size = 0;
    if (refusal != NULL) {
        pc_last_refusal = refusal;
        return 0;
    }
    return 1;
}

/* The library's purchase: the graph left in cg_bytes / cg_g as cg_library_purchase reads a file there. */
static int pc_arm_library(int game, unsigned int size) {
    unsigned int planned = 0;
    const char *refusal;
    int keep_cast = cg_cast_now, keep_origin = cg_origin_now;
    if (!cg_bytes_room(size)) {
        return 0;
    }
    memcpy(cg_bytes, pc_graph, size);
    cg_bytes_size = size;
    if (!cg_load(&cg_g, cg_bytes, size)) {
        cg_bytes_size = 0;
        return 0;
    }
    cg_cast_now = CG_CAST_PREFER;
    cg_origin_now = CG_ORIGIN_PURCHASE;
    refusal = cg_refusal(game, &planned);
    cg_cast_now = keep_cast;
    cg_origin_now = keep_origin;
    if (refusal != NULL) {
        lstrcpynA(cg_why, refusal, sizeof cg_why);
        cg_bytes_size = 0;
        return 0;
    }
    return 1;
}

/* The index's file `g`'s draw weight (its usable setups; pc_index). */
static int pc_weight(int g) {
    return g >= 0 && g < pc_group_count ? pc_groups[g].weight : 0;
}

/* The natural draw's file `g` (sc_choose_and_arm): 1 when a composition from it was armed. */
static int pc_draw_group(int game, int g) {
    return pc_compose(game, g, -1, pc_arm_natural);
}

/* The setup piece `id` in the loaded file, -1 none. */
static int pc_setup_of(const char *id) {
    unsigned int i;
    for (i = 0; i < pc_f.n_piece; ++i) {
        const unsigned char *p = pc_piece((int)i);
        if (p[4] == PC_SETUP && lstrcmpA(pc_str(pc_u32(p)), id) == 0) {
            return (int)i;
        }
    }
    return -1;
}

/* ---- Pick Island Event ------------------------------------------------------------------------------------- */

/* "<title> (varies)" into `out` (`cap` bytes; a title is cut to fit). */
static void pc_varies(const char *title, char *out, int cap) {
    char cut[SM_TEXT];
    char text[SM_TEXT + 200];
    lstrcpynA(cut, title, SM_TEXT - 40);
    wsprintfA(text, vvfp_tr("vvfp.story/story_procedural.pc_pick_fill.s1", "%s (varies)", 100), cut);
    lstrcpynA(out, text, cap);
}

/* Appends each usable setup of every pieces file to the Pick Island Event list, "<title> (varies)"; possible when a
   composition with it (from the private generator) casts now.  The count added. */
static int pc_pick_fill(int game) {
    unsigned int filters;
    int g, groups, added = 0;
    if ((groups = pc_index(game)) == 0) {
        return 0;
    }
    filters = sc_filters_on(game);
    pc_ref_count = 0;
    for (g = 0; g < groups; ++g) {
        unsigned int i;
        if (!pc_load(g)) {
            continue;
        }
        for (i = 0; i < pc_f.n_piece; ++i) {
            const unsigned char *p = pc_piece((int)i);
            int m = sm_list.count, c1 = pc_ref_cap, ok;
            if (p[4] != PC_SETUP || pc_str(pc_u32(p + 36)) == NULL || !pc_usable(game, p, filters)) {
                continue;
            }
            if (!sm_reserve(sm_list.count + 1)
                || !story_grow((void **)&pc_ref_group, &pc_ref_cap, pc_ref_count + 1, sizeof(int))
                || !story_grow((void **)&pc_ref_piece, &c1, pc_ref_count + 1, sizeof(int))) {
                sc_problem("The Pick Island Event list could not hold every event: not enough memory.");
                return added;
            }
            pc_ref_group[pc_ref_count] = g;
            pc_ref_piece[pc_ref_count] = (int)i;
            pc_varies(pc_str(pc_u32(p + 36)), sm_list.title[m], SM_TEXT);
            lstrcpynA(sm_list.description[m],
                      vvfp_tr("vvfp.story/story_procedural.pc_pick_fill.s0",
                              "A new island event, put together each time from the collection's pieces.", 200), SM_TEXT);
            sm_list.k[m] = PC_PROC_BASE + pc_ref_count++;
            pc_dry = 1;
            pc_dry_state = 0x9E3779B9u ^ (i * 2654435761u) ^ (unsigned int)g;
            pc_last_refusal = NULL;
            ok = pc_compose(game, g, (int)i, pc_arm_check);
            pc_dry = 0;
            sm_list.possible[m] = ok;
            if (ok) {
                sm_list.needs[m][0] = '\0';
            } else {
                int len;
                lstrcpynA(sm_list.needs[m], pc_last_refusal != NULL ? pc_last_refusal
                                            : "the village to have the villagers it needs", SM_TEXT);
                len = lstrlenA(sm_list.needs[m]);
                if (len > 25 && lstrcmpA(sm_list.needs[m] + len - 25, " Nothing has been queued.") == 0) {
                    sm_list.needs[m][len - 25] = '\0';
                }
            }
            ++sm_list.count;
            ++added;
            if (!pc_load(g)) {         /* the check may have read another file: this one again */
                break;
            }
        }
    }
    return added;
}

/* Procedural row `ref` bought with Pick Island Event: confirmed, composed with the game's rolls and queued (strict
   cast, origin Pick Island Event).  1 when it is on its way. */
static int pc_pick_buy(int game, HWND owner, int ref) {
    char message[1800];
    if (ref < 0 || ref >= pc_ref_count || pc_index(game) <= pc_ref_group[ref] || !pc_load(pc_ref_group[ref])
        || pc_ref_piece[ref] >= (int)pc_f.n_piece) {
        return 0;
    }
    lstrcpynA(pc_pick_title, pc_str(pc_u32(pc_piece(pc_ref_piece[ref]) + 36)), sizeof pc_pick_title);
    wsprintfA(message,
              vvfp_tr("vvfp.story/vvfp_story_upgrades.story_pick_island_event.s6",
                      "Do you want to buy Pick Island Event (%s) for %s tech points?%s%s\r\n\r\nPress OK to confirm, or Cancel.",
                      400), pc_pick_title, story_price_text(game), "", "");
    if (vvfp_message_box(owner, message, "Origins Upgrades",
                         MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    if (ce_armed || GAMES[game].island_pending()) {
        MessageBoxA(owner, "That island event can not happen right now. No tech points have been deducted.",
                    "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if (!pc_compose(game, pc_ref_group[ref], pc_ref_piece[ref], pc_arm_pick)) {
        wsprintfA(message, vvfp_tr("vvfp.story/story_collection.sc_pick_buy.s0",
                                   "%s can not happen right now: %s No tech points have been deducted.", 200),
                  pc_pick_title, cg_queue_refusal()[0] != '\0' ? cg_queue_refusal() : "it can not happen right now.");
        vvfp_message_box(owner, message, "Pick Island Event", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    wsprintfA(message, vvfp_tr("vvfp.story/vvfp_story_upgrades.story_pick_island_event.s9", "%s is on its way.", 200),
              pc_pick_title);
    vvfp_message_box(owner, message, "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}

/* ---- The library ------------------------------------------------------------------------------------------- */

static int pc_library_path(const char *path) {
    int i;
    for (i = 0; PC_LIBRARY_TAG[i] != '\0'; ++i) {
        if (path[i] != PC_LIBRARY_TAG[i]) {
            return 0;
        }
    }
    return 1;
}

/* Each usable setup of every pieces file in the library list ("?pieces:<group>/<setup id>"). */
static void pc_library_add(int game) {
    unsigned int filters;
    int g, groups;
    if ((groups = pc_index(game)) == 0) {
        return;
    }
    filters = sc_filters_on(game);
    for (g = 0; g < groups; ++g) {
        unsigned int i;
        if (!pc_load(g)) {
            continue;
        }
        for (i = 0; i < pc_f.n_piece && cg_lib_room(); ++i) {
            const unsigned char *p = pc_piece((int)i);
            char title[SM_TEXT], label[SM_TEXT + 120];
            if (p[4] != PC_SETUP || pc_str(pc_u32(p + 36)) == NULL || !pc_usable(game, p, filters)
                || lstrlenA(PC_LIBRARY_TAG) + lstrlenA(pc_groups[g].name) + 1 + lstrlenA(pc_str(pc_u32(p)))
                       >= MAX_PATH) {
                continue;
            }
            wsprintfA(cg_lib.path[cg_lib.count], "%s%s/%s", PC_LIBRARY_TAG, pc_groups[g].name, pc_str(pc_u32(p)));
            pc_varies(pc_str(pc_u32(p + 36)), title, SM_TEXT);
            wsprintfA(label,
                      vvfp_tr("vvfp.story/story_collection.sc_library_add.s0", "Isola Grand Event Collection: %s", 100),
                      title);
            lstrcpynA(cg_lib.label[cg_lib.count], label, sizeof cg_lib.label[0]);
            ++cg_lib.count;
        }
    }
}

/* The library's procedural row `path`: composed (the game's rolls) and left in cg_bytes / cg_g as
   cg_library_purchase reads a file there.  1 when it can be cast (PREFER); else 0 with the reason in cg_why. */
static int pc_library_load(int game, const char *path) {
    char group[PC_GROUP_BYTES];
    const char *rest = path + lstrlenA(PC_LIBRARY_TAG), *slash;
    int g, groups, s;
    for (slash = rest; *slash != '\0' && *slash != '/'; ++slash) {
    }
    if (*slash != '/' || slash - rest >= PC_GROUP_BYTES) {
        lstrcpynA(cg_why, "its pieces can not be read: install the patch again", sizeof cg_why);
        return 0;
    }
    lstrcpynA(group, rest, (int)(slash - rest) + 1);
    groups = pc_index(game);
    for (g = 0; g < groups && lstrcmpA(pc_groups[g].name, group) != 0; ++g) {
    }
    if (g >= groups || !pc_load(g) || (s = pc_setup_of(slash + 1)) < 0) {
        lstrcpynA(cg_why, "its pieces can not be read: install the patch again", sizeof cg_why);
        return 0;
    }
    cg_why[0] = '\0';
    if (!pc_compose(game, g, s, pc_arm_library)) {
        if (cg_why[0] == '\0') {
            lstrcpynA(cg_why, "it can not happen right now", sizeof cg_why);
        }
        return 0;
    }
    return 1;
}

#ifdef VVFP_TEST
/* ---- Test build only ---------------------------------------------------------------------------------------- */

/* The one pieces file the index and the composer use (NULL: the folder's own). */
/* Whether a piece's effect `e` (its 20 bytes) counts as harmful: the harm guard's and the protected flag's test. */
__declspec(dllexport) int __stdcall VvfpStoryProbeProceduralHarmful(const unsigned char *e) {
    return pc_harmful(e);
}

__declspec(dllexport) void __stdcall VvfpStoryProbeProceduralFile(const unsigned char *data, unsigned int size) {
    pc_test_file = data;
    pc_test_size = size;
    pc_loaded = -1;
    pc_f.d = NULL;
}

/* One composition from that file in `game` (the game's own rolls: VvfpStoryProbeSetRolls), the setup `fixed` (-1
   drawn), `gate` the 61-villager gate, `notes` Content Notes on: the .cieg written into `out` (at most `cap` bytes),
   nothing queued.  Its size, 0 when nothing could be composed. */
__declspec(dllexport) unsigned int __stdcall VvfpStoryProbeProceduralCompose(int game, int fixed, int gate, int notes,
                                                                             unsigned char *out, unsigned int cap) {
    static unsigned char skip[4096];
    unsigned int size;
    pc_pick c;
    pc_group_count = 0;
    if (!story_grow((void **)&pc_groups, &pc_group_cap, 1, sizeof(pc_group))) {
        return 0;
    }
    lstrcpyA(pc_groups[0].name, "test");
    pc_group_count = 1;
    pc_loaded = -1;
    if (game < 1 || game > 5 || !pc_load(0) || pc_f.n_piece > sizeof skip) {
        return 0;
    }
    memset(skip, 0, sizeof skip);
    pc_game = game;
    pc_note_on = (char)(notes != 0);
    sc_gate = gate;
    size = pc_choose(game, sc_filters_on(game), fixed, skip, &c) ? pc_write(&c, "test", pc_graph, sizeof pc_graph) : 0u;
    sc_gate = 0;
    if (size == 0u || size > cap) {
        return 0;
    }
    memcpy(out, pc_graph, size);
    return size;
}
#endif
