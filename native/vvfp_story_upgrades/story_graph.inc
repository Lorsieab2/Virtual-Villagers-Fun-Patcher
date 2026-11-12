/* BRANCHING CUSTOM ISLAND EVENTS, phase 2: the game-side runtime.  Included by vvfp_story_upgrades.c after
   story_queue.inc.

   The owner (v1.35.97): "allow the player to create multiple branching complicated outcome events like I just made
   for Aspiring Adventurer in Custom Island Events".  An event is written in the patcher (src/vv_cie_graph.py: the
   JSON format, every check it must pass, its compiled .cieg and the chances of every outcome) and kept in

       <save folder>\Virtual Villagers Fun Patcher\Custom Island Events\<name>.json + <name>.cieg

   The in-game Custom Island Event dialog's "From the library..." lists the .cieg events made for this game (a
   .cieg with no .json beside it, or an older one, is never offered: the patcher writes both at each save) and
   queues the one picked.  The single-step editor stays as it is.

   READING (cg_load).  A .cieg is read whole (at most CG_MAX_FILE bytes) and checked again here before anything
   uses it: the magic, the version, the header size, the file size, the CRC-32 of the whole file, every section
   inside the file, every index inside its table, every string inside the strings and NUL-ended, every operand of
   a condition after the condition itself (so no condition can loop), the node graph free of cycles, every effect
   one this companion knows with its values in range, and every text made only of the characters the Custom
   Island Event allows (ce_text_char_ok, line breaks) and well-formed placeholders.  A file that fails is refused
   with the reason; it is never partly used.

   ROLES (cg_eligible).  A villager role is filled by a living villager the game lists (the adapter's own test)
   of the role's age or more (20 age units a year in every game), of its sex if it names one, not carrying or
   nursing a baby unless the role allows it (the adapter's own "expecting" field), not one of the game's special
   villagers unless the role allows it -- the ones the shipped Aspiring Adventurer leaves out (native/
   vvfp_more_island_events): A New Home's Golden Child, The Secret City's Tribal Chief (and its stand-in records),
   New Believers' chief, Retired Chief and the puzzles' Heathens (roles 12-17) -- and in New Believers a believer
   unless the role allows Heathens.  Two villager roles are always two villagers: the roles are bound by a
   matching (cg_matchable), so a role is never refused while the village can fill every one.  A stranger has no
   record, only a sex (random when the event says so).  Custom Island Events are exempt from a shipped event's
   natural requirement (the owner): only the roles count.
     * Queueing: when the village cannot fill every role the event needs, the purchase is REFUSED and the message
       says which role and what it needs.  An optional role is planned when the village can fill it then.
     * Delivery: the roles are bound when the event is about to be shown (the game's random routine picks among
       those who fit).  If the village can no longer fill them, the event KEEPS WAITING (ce_held): the island
       event that came is the game's own, and the custom one is made due again once they can be filled
       (ce_opening_tick) -- never run with a role missing.

   THE WALK (cg_walk).  From the start (or each question button), each node's children are resolved as the
   patcher resolves them (a child whose condition fails is its else, or left out; none left: the node's else; no
   children: the end) and one is drawn, weighted, through the adapter's random routine (ce_random_below).
   Conditions: visited, role (bound in this run), game, patch (the patches the companion can see: Guardians of
   Isola's rewrite in New Believers; any other id is off), not / all / any.  Each effect's own roll -- a health in
   its range, which skill and how much -- is made as its node is reached, and a scaled amount is worked out then
   ("Island Events Scale With Population" / "... With Stored Food and Tech Points": their companion's own rule
   when ticked, else the amount as written).  A question's two histories are both walked when it is asked (as the
   shipped event rolls everything when its popup is built), so the popup can be sized for the result it will show.

   EFFECTS WAIT FOR THEIR OWN PAGE (the owner, 2026-11-12).  Each node's effects are made, once, when the page
   showing the end of that node's text is built for the screen -- as the game's own plain island event makes its
   changes while it builds its popup, and as a question's result is built at the click -- so each page says what
   has just happened (cg_layout_history, cg_show): the award with "Your villagers gain ...", a death or a
   disappearance with its ending's last page.  A villager who has died or left by then (old age between pages)
   has that role's later effects skipped; the rest of the event goes on.  Through the adapters: food / tech points through the game's own writers (CE_AMOUNT_ADD / SUBTRACT),
   the award only when paid; "dies" the adapter's death, with the event's cause told to "VVFP Cause of Death.dll"
   ("unknown": nothing, the game's own "Unknown causes"; "custom": VvfpCauseKilled, "Died in a custom island
   event"; the author's words: VvfpCauseKilledBy when that companion has it, else as "custom"); "disappears" the
   adapter's removal with no body, told as VvfpCauseVanishedBy ("Disappeared in <title>") or, with an older
   companion, VvfpCauseVanished -- the Deaths log's Disappeared record; "becomes a Heathen" (New Believers) the
   game's own conversion through the adapter's status 1 (0x4669E0: the bottom bar's line, the Cause of Death
   "Left the tribe" record and the statistics), and counted as a faith conversion: "VVFP Faith Notice.dll"'s
   VvfpFaithNoticeCount adds it to the believers "Popup When Believers Become Heathens" tells of, when that patch
   is on; health, a like or dislike by the game's own word, a skill raised, sickness -- one ce_change each through
   ce_apply, so titles, refusals and their reasons are the plain Custom Island Event's.

   THE POPUPS.  Every popup of a history is laid out in pages that fit the popup it is shown in (the page
   splitting the shipped event uses until the popups can scroll: whole paragraphs where they fit, else whole
   sentences, else words -- never off the screen), measured with the longest names the game holds, so the pages
   are the same whoever the villagers are; each page is then filled with the real names ("(name)" is the record's
   own name, the full name with Last Names on).  A popup that carries villager effects keeps two lines free on each
   page for the "N changes could not be made" lines of that page's own effects.  They are shown one after another,
   each a popup of its own through the game's own trigger:
     * a question: its text's earlier pages first, then the game's two-button popup with the last page;
     * the answer's first page is the result popup the click shows (ce_choice_resolve);
     * every later page through the island-event notice the Time Skip's closing popup uses (story_notice_arm).
   ONE EVENT.  Only the question (or, with no question, the first page) is the island event: it alone counts in
   Island Events Seen; every other page is a notice, whose count is taken back.  The Island Events log
   ("VVFP Island Events.dll") has no event of its own to append to: it writes one numbered record per villager an
   event's popup changed, each headed "Event: <title>", and skips only the Time Skip's notice.  So a later page's
   effects are written as records under the same "Event: <title>" as the first page's (the question's records
   carry its "Choice:" line too); a page that changes nobody writes nothing.  While a run has pages left the event
   slot is its own: no notice, no other custom event comes between.

   A QUIT BETWEEN POPUPS RESUMES, EACH EFFECT EXACTLY ONCE.  The run (where it is, who the roles are, both
   histories, every page with the effects it makes, when each page's were made, and who was gone before it) and
   the .cieg itself are kept beside the queue's file:
       Virtual Villagers N Story Purchases Graph - Save S.dat
   written as the run changes, and kept after its last page until a save holds every page's effects.  It is put
   back, once, for the same village (a majority of its roster) when the slot's save was written after the
   purchase -- the queue's own rule (story_queue.inc) -- from the first page whose effects that save does not hold
   (cg_village_seen): those pages are shown again and make their effects then, the pages the save holds are not.
   The queue file itself never holds a graph's popup (sq_capture leaves it out), so a version 1 queue file is read
   exactly as before. */

#define CG_HEADER_BYTES 80u
#define CG_NONE 0xFFFFu
#define CG_MAX_FILE 0x20000u
#define CG_MAX_ROLES 16
#define CG_MAX_NODES 1000
#define CG_MAX_PATH 128
#define CG_MAX_FX 64
#define CG_MAX_POPUPS 12
#define CG_MAX_PAGES 24
#define CG_NAME_BYTES 32
#define CG_TEXT_MAX 1990                /* a popup's (and a page's) bytes: the later games build theirs in 2,000 */
#define CG_RAW_BYTES 4096
#define CG_PAGE_BYTES 2400
#define CG_DISPLAY_BYTES 49152
#define CG_MAX_DISPLAYS 96
#define CG_CAUSE_BYTES 64
#define CG_LABEL_BYTES CE_BUTTON_BYTES
#define CG_ENTRY_BYTES 8192

enum { CG_POPUP = 0, CG_QUESTION = 1, CG_BRANCH = 2 };
enum { CGE_FOOD = 1, CGE_TECH = 2, CGE_PAY = 3, CGE_KILL = 4, CGE_VANISH = 5, CGE_STATUS = 6, CGE_HEALTH = 7,
       CGE_PREF = 8, CGE_SKILL = 9, CGE_SICK = 10 };
enum { CGC_VISITED = 1, CGC_ROLE = 2, CGC_GAME = 3, CGC_PATCH = 4, CGC_NOT = 5, CGC_ALL = 6, CGC_ANY = 7 };
/* CG_DONE: every page shown, the file kept until a save holds the last page's effects (a crash before it must
   neither lose nor repeat them). */
enum { CG_IDLE = 0, CG_QUEUED = 1, CG_PRE = 2, CG_ASKED = 3, CG_CHAIN = 4, CG_DONE = 5 };
enum { CG_ROLE_OPTIONAL = 1, CG_ROLE_NURSING = 2, CG_ROLE_SPECIAL = 4, CG_ROLE_BELIEVERS = 8 };
enum { CG_PH_NAME = 0, CG_PH_HE, CG_PH_HIS, CG_PH_HIM, CG_PH_MAN, CG_PH_AWARD, CG_PH_UNIT };
enum { CG_EXPAND_AWARD = 0, CG_EXPAND_WORST = 1, CG_EXPAND_REAL = 2 };

/* ---- The .cieg (src/vv_cie_graph.py THE BINARY .cieg) ----------------------------------------------------- */

typedef struct {
    const unsigned char *d;
    unsigned int size;
    unsigned int games;
    int title, start, min_eligible;
    int n_role, n_node, n_child, n_effect, n_cond, n_variant, n_string, n_patch;
    unsigned int o_role, o_node, o_child, o_effect, o_cond, o_variant, o_patch, o_string, o_blob, blob_size;
} cg_graph;

static unsigned int cg_u16(const unsigned char *p) {
    return (unsigned int)p[0] | (unsigned int)p[1] << 8;
}

static unsigned int cg_u32(const unsigned char *p) {
    return (unsigned int)p[0] | (unsigned int)p[1] << 8 | (unsigned int)p[2] << 16 | (unsigned int)p[3] << 24;
}

static const unsigned char *cg_role_at(const cg_graph *g, int i) { return g->d + g->o_role + 8u * (unsigned int)i; }
static const unsigned char *cg_node_at(const cg_graph *g, int i) { return g->d + g->o_node + 28u * (unsigned int)i; }
static const unsigned char *cg_child_at(const cg_graph *g, int i) { return g->d + g->o_child + 12u * (unsigned int)i; }
static const unsigned char *cg_effect_at(const cg_graph *g, int i) { return g->d + g->o_effect + 16u * (unsigned int)i; }
static const unsigned char *cg_cond_at(const cg_graph *g, int i) { return g->d + g->o_cond + 8u * (unsigned int)i; }
static const unsigned char *cg_variant_at(const cg_graph *g, int i) { return g->d + g->o_variant + 4u * (unsigned int)i; }

/* String `i` ("" for NONE; every index was checked by cg_load). */
static const char *cg_s(const cg_graph *g, unsigned int i) {
    if (i == CG_NONE || (int)i >= g->n_string) {
        return "";
    }
    return (const char *)(g->d + g->o_blob + cg_u32(g->d + g->o_string + 4u * i));
}

/* The zlib CRC-32 (src/vv_cie_graph.py writes zlib.crc32 of the file with its own field 0). */
static unsigned int cg_crc_table[256];

static unsigned int cg_crc32(const unsigned char *data, unsigned int size, unsigned int skip_at) {
    unsigned int crc = 0xFFFFFFFFu;
    unsigned int i;
    if (cg_crc_table[1] == 0u) {
        unsigned int n, k, c;
        for (n = 0; n < 256u; ++n) {
            c = n;
            for (k = 0; k < 8u; ++k) {
                c = (c & 1u) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            }
            cg_crc_table[n] = c;
        }
    }
    for (i = 0; i < size; ++i) {
        unsigned char b = (i >= skip_at && i < skip_at + 4u) ? 0 : data[i];
        crc = cg_crc_table[(crc ^ b) & 0xFFu] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}

static char cg_why[160];

static int cg_bad(const char *why) {
    lstrcpynA(cg_why, why, sizeof cg_why);
    return 0;
}

/* A section of `count` entries of `size` bytes at `at`, inside the file. */
static int cg_section(const cg_graph *g, unsigned int at, int count, unsigned int size) {
    return at >= CG_HEADER_BYTES && at <= g->size && (unsigned int)count <= (g->size - at) / size;
}

static int cg_str_ok(const cg_graph *g, unsigned int i, int may_be_none) {
    return i == CG_NONE ? may_be_none : (int)i < g->n_string;
}

static int cg_role_by_id(const cg_graph *g, const char *id, int length) {
    int r;
    for (r = 0; r < g->n_role; ++r) {
        const char *s = cg_s(g, cg_u16(cg_role_at(g, r) + 4));
        if (lstrlenA(s) == length && memcmp(s, id, (size_t)length) == 0) {
            return r;
        }
    }
    return -1;
}

static int cg_word_is(const char *w, int n, const char *lit) {
    int i;
    for (i = 0; i < n; ++i) {
        char c = w[i];
        if (c >= 'A' && c <= 'Z') {
            c = (char)(c - 'A' + 'a');
        }
        if (lit[i] == '\0' || c != lit[i]) {
            return 0;
        }
    }
    return lit[n] == '\0';
}

typedef struct {
    int role;                         /* -1: the award */
    int what;                         /* CG_PH_* */
    int capital;
} cg_ph;

/* A placeholder's inside ("friend.His/Her"), src/vv_cie_graph.py parse_placeholder.  0 when it is not one. */
static int cg_parse_ph(const cg_graph *g, const char *tok, int n, cg_ph *ph) {
    static const char *const WORDS[] = { "name", "he/she", "his/her", "him/her", "man/woman", "award", "award_unit" };
    int dot = -1;
    int i;
    int role = -1;
    const char *w;
    int wn;
    for (i = 0; i < n; ++i) {
        if (tok[i] == '.') {
            dot = i;
        }
    }
    w = tok + dot + 1;
    wn = n - dot - 1;
    if (dot == 0 || wn <= 0) {
        return 0;
    }
    if (dot > 0) {
        role = cg_role_by_id(g, tok, dot);
        if (role < 0) {
            return 0;
        }
    }
    ph->capital = w[0] >= 'A' && w[0] <= 'Z';
    if (cg_word_is(w, wn, "name1") || cg_word_is(w, wn, "name2")) {
        if (dot > 0) {
            return 0;
        }
        role = w[4] == '1' ? cg_role_by_id(g, "subject", 7) : cg_role_by_id(g, "friend", 6);
        if (role < 0) {
            return 0;
        }
        ph->what = CG_PH_NAME;
    } else {
        for (i = 0; i < 7 && !cg_word_is(w, wn, WORDS[i]); ++i) {
        }
        if (i == 7) {
            return 0;
        }
        ph->what = i;
        if (i >= CG_PH_AWARD) {
            if (dot > 0) {
                return 0;
            }
            ph->role = -1;
            return 1;
        }
        if (role < 0) {
            role = cg_role_by_id(g, "subject", 7);
            if (role < 0) {
                role = 0;
            }
        }
    }
    if (ph->what == CG_PH_NAME && cg_role_at(g, role)[0] != 0) {
        return 0;                     /* a stranger has no name */
    }
    ph->role = role;
    return 1;
}

/* Every character allowed (ce_text_char_ok; line breaks when `lines`), parentheses only around placeholders (no
   award in a label: `label`). */
static int cg_text_ok(const cg_graph *g, const char *s, int lines, int label) {
    for (; *s != '\0'; ++s) {
        if (*s == '(') {
            const char *e = s + 1;
            cg_ph ph;
            while (*e != '\0' && *e != ')' && *e != '(' && *e != '\n') {
                ++e;
            }
            if (*e != ')' || !cg_parse_ph(g, s + 1, (int)(e - s - 1), &ph) || (label && ph.role < 0)) {
                return 0;
            }
            s = e;
            continue;
        }
        if (*s == '\n' && lines) {
            continue;
        }
        if (!ce_text_char_ok(*s)) {
            return 0;
        }
    }
    return 1;
}

/* Every edge of node `i` into `out` (at most 2 per child + 1); the count. */
static int cg_edges(const cg_graph *g, int i, int *out) {
    const unsigned char *n = cg_node_at(g, i);
    int first = (int)cg_u16(n + 12), count = (int)cg_u16(n + 14), k, m = 0;
    for (k = 0; k < count; ++k) {
        const unsigned char *c = cg_child_at(g, first + k);
        out[m++] = (int)cg_u16(c);
        if (n[0] != CG_QUESTION && cg_u16(c + 6) != CG_NONE) {
            out[m++] = (int)cg_u16(c + 6);
        }
    }
    if (cg_u16(n + 16) != CG_NONE) {
        out[m++] = (int)cg_u16(n + 16);
    }
    return m;
}

/* No cycle (Kahn): every node is removed once nothing points at it any more. */
static int cg_acyclic(const cg_graph *g) {
    static unsigned short indegree[CG_MAX_NODES];
    static unsigned short queue[CG_MAX_NODES];
    static int edges[2 * 256 + 2];
    int i, k, m, head = 0, tail = 0, removed = 0;
    memset(indegree, 0, sizeof indegree);
    for (i = 0; i < g->n_node; ++i) {
        m = cg_edges(g, i, edges);
        for (k = 0; k < m; ++k) {
            ++indegree[edges[k]];
        }
    }
    for (i = 0; i < g->n_node; ++i) {
        if (indegree[i] == 0) {
            queue[tail++] = (unsigned short)i;
        }
    }
    while (head < tail) {
        i = queue[head++];
        ++removed;
        m = cg_edges(g, i, edges);
        for (k = 0; k < m; ++k) {
            if (--indegree[edges[k]] == 0) {
                queue[tail++] = (unsigned short)edges[k];
            }
        }
    }
    return removed == g->n_node;
}

/* Read `data` (`size` bytes) as a .cieg into `g` (which points into `data`): 1, or 0 with the reason in cg_why. */
static int cg_load(cg_graph *g, const unsigned char *data, unsigned int size) {
    const unsigned char *h = data;
    int i, k;
    memset(g, 0, sizeof *g);
    g->d = data;
    g->size = size;
    if (size < CG_HEADER_BYTES || memcmp(h, "CIEG", 4) != 0 || cg_u16(h + 4) != 1u || cg_u16(h + 6) != CG_HEADER_BYTES
        || cg_u32(h + 8) != size) {
        return cg_bad("it is not a version 1 .cieg file");
    }
    if (size > CG_MAX_FILE) {
        return cg_bad("it is larger than this game can read (128 KB)");
    }
    if (cg_crc32(data, size, 12) != cg_u32(h + 12)) {
        return cg_bad("the file is damaged (its checksum does not match)");
    }
    g->games = cg_u32(h + 16);
    g->title = (int)cg_u16(h + 20);
    g->start = (int)cg_u16(h + 22);
    g->min_eligible = (int)cg_u16(h + 24);
    g->n_role = (int)cg_u16(h + 26);
    g->n_node = (int)cg_u16(h + 28);
    g->n_child = (int)cg_u16(h + 30);
    g->n_effect = (int)cg_u16(h + 32);
    g->n_cond = (int)cg_u16(h + 34);
    g->n_variant = (int)cg_u16(h + 36);
    g->n_string = (int)cg_u16(h + 38);
    g->n_patch = (int)cg_u16(h + 40);
    g->o_role = cg_u32(h + 44);
    g->o_node = cg_u32(h + 48);
    g->o_child = cg_u32(h + 52);
    g->o_effect = cg_u32(h + 56);
    g->o_cond = cg_u32(h + 60);
    g->o_variant = cg_u32(h + 64);
    g->o_patch = cg_u32(h + 68);
    g->o_string = cg_u32(h + 72);
    if (g->games == 0u || (g->games & ~0x1Fu) != 0u || g->n_role < 1 || g->n_role > CG_MAX_ROLES || g->n_node < 1
        || g->n_node > CG_MAX_NODES || g->n_patch > 8 || g->n_child >= 0xFFFF || g->n_effect >= 0xFFFF
        || g->n_cond >= 0xFFFF || g->n_variant >= 0xFFFF || g->n_string >= 0xFFFF
        || !cg_section(g, g->o_role, g->n_role, 8) || !cg_section(g, g->o_node, g->n_node, 28)
        || !cg_section(g, g->o_child, g->n_child, 12) || !cg_section(g, g->o_effect, g->n_effect, 16)
        || !cg_section(g, g->o_cond, g->n_cond, 8) || !cg_section(g, g->o_variant, g->n_variant, 4)
        || !cg_section(g, g->o_patch, g->n_patch, 2) || !cg_section(g, g->o_string, g->n_string, 4)) {
        return cg_bad("its tables do not fit in the file");
    }
    g->o_blob = g->o_string + 4u * (unsigned int)g->n_string;
    g->blob_size = size - g->o_blob;
    for (i = 0; i < g->n_string; ++i) {
        unsigned int at = cg_u32(data + g->o_string + 4u * (unsigned int)i);
        if (at >= g->blob_size || memchr(data + g->o_blob + at, 0, g->blob_size - at) == NULL) {
            return cg_bad("a string runs past the end of the file");
        }
    }
    if (!cg_str_ok(g, (unsigned int)g->title, 0) || g->start >= g->n_node) {
        return cg_bad("its title or start is missing");
    }
    {
        const char *title = cg_s(g, (unsigned int)g->title);
        if (title[0] == '\0' || lstrlenA(title) >= CE_TITLE_BYTES || !ce_text_ok(title, 0)) {
            return cg_bad("its title is not one the game can show");
        }
    }
    for (i = 0; i < g->n_patch; ++i) {
        if (!cg_str_ok(g, cg_u16(data + g->o_patch + 2u * (unsigned int)i), 0)) {
            return cg_bad("a patch name is missing");
        }
    }
    for (i = 0; i < g->n_role; ++i) {
        const unsigned char *r = cg_role_at(g, i);
        if (r[0] > 1u || !cg_str_ok(g, cg_u16(r + 4), 0) || (r[0] == 0 && (r[2] > 2u || r[3] > 80u))
            || (r[0] == 1 && (r[2] < 1u || r[2] > 3u)) || (i == 0 && (r[0] != 0 || (r[1] & CG_ROLE_OPTIONAL)))) {
            return cg_bad("a role is not one this game can read");
        }
    }
    for (i = 0; i < g->n_cond; ++i) {
        const unsigned char *c = cg_cond_at(g, i);
        unsigned int a = cg_u16(c + 2);
        int ok;
        switch (c[0]) {
        case CGC_VISITED: ok = (int)a < g->n_node; break;
        case CGC_ROLE: ok = (int)a < g->n_role; break;
        case CGC_GAME: ok = a != 0u && (a & ~0x1Fu) == 0u; break;
        case CGC_PATCH: ok = (int)a < g->n_patch; break;
        case CGC_NOT: ok = (int)a > i && (int)a < g->n_cond; break;
        case CGC_ALL: case CGC_ANY: ok = c[1] >= 1u && (int)a > i && (int)a + c[1] <= g->n_cond; break;
        default: ok = 0; break;
        }
        if (!ok) {
            return cg_bad("a condition is not one this game can read");
        }
    }
    for (i = 0; i < g->n_variant; ++i) {
        const unsigned char *v = cg_variant_at(g, i);
        if ((int)cg_u16(v) >= g->n_cond || !cg_str_ok(g, cg_u16(v + 2), 0)
            || !cg_text_ok(g, cg_s(g, cg_u16(v + 2)), 1, 0) || lstrlenA(cg_s(g, cg_u16(v + 2))) > CG_TEXT_MAX) {
            return cg_bad("a variant text is not one the game can show");
        }
    }
    for (i = 0; i < g->n_effect; ++i) {
        const unsigned char *e = cg_effect_at(g, i);
        int a = (int)cg_u32(e + 4), b = (int)cg_u32(e + 8);
        unsigned int str = cg_u16(e + 12);
        int villager = e[0] >= CGE_KILL && e[0] <= CGE_SICK;
        int ok = e[0] >= CGE_FOOD && e[0] <= CGE_SICK;
        if (ok && villager) {
            ok = e[1] < (unsigned int)g->n_role && cg_role_at(g, e[1])[0] == 0;
        }
        if (ok) {
            switch (e[0]) {
            case CGE_FOOD: case CGE_TECH: ok = a != 0 && a <= CE_MAX_AMOUNT && a >= -CE_MAX_AMOUNT; break;
            case CGE_KILL: {
                const char *cause = cg_s(g, str);
                ok = str != CG_NONE && cause[0] != '\0' && lstrlenA(cause) < CG_CAUSE_BYTES && ce_text_ok(cause, 0);
                break;
            }
            case CGE_STATUS: ok = a == 1; break;
            case CGE_HEALTH: case CGE_SKILL: ok = a >= 1 && a <= 100 && b >= a && b <= 100; break;
            default: break;
            }
        }
        if (ok && (e[0] == CGE_PREF || e[0] == CGE_SKILL)) {
            ok = str != CG_NONE && cg_s(g, str)[0] != '\0';
        }
        if (!ok) {
            return cg_bad("an effect is not one this game can make");
        }
    }
    for (i = 0; i < g->n_node; ++i) {
        const unsigned char *n = cg_node_at(g, i);
        unsigned int text = cg_u16(n + 6), vfirst = cg_u16(n + 8), vcount = cg_u16(n + 10);
        unsigned int cfirst = cg_u16(n + 12), ccount = cg_u16(n + 14), els = cg_u16(n + 16);
        unsigned int efirst = cg_u16(n + 18), ecount = cg_u16(n + 20);
        if (n[0] > 2u || n[1] > 1u || n[2] > 1u || !cg_str_ok(g, cg_u16(n + 4), 0) || !cg_str_ok(g, text, 1)
            || (vcount > 0u && vfirst + vcount > (unsigned int)g->n_variant)
            || (ccount > 0u && cfirst + ccount > (unsigned int)g->n_child)
            || (ecount > 0u && efirst + ecount > (unsigned int)g->n_effect)
            || (els != CG_NONE && (int)els >= g->n_node) || !cg_str_ok(g, cg_u16(n + 22), 1)
            || !cg_str_ok(g, cg_u16(n + 24), 1)) {
            return cg_bad("a node is not one this game can read");
        }
        if (ccount > 256u) {
            return cg_bad("a node has more than 256 children");
        }
        if (n[0] == CG_QUESTION && (i != g->start || ccount != 2u || els != CG_NONE)) {
            return cg_bad("a question is not the event's first popup with two choices");
        }
        if (n[0] != CG_BRANCH && (cg_s(g, text)[0] == '\0' || !cg_text_ok(g, cg_s(g, text), 1, 0)
                                  || lstrlenA(cg_s(g, text)) > CG_TEXT_MAX)) {
            return cg_bad("a text is not one the game can show");
        }
        for (k = 0; k < (int)ccount; ++k) {
            const unsigned char *c = cg_child_at(g, (int)cfirst + k);
            unsigned int cond = cg_u16(c + 4), ce = cg_u16(c + 6);
            if ((int)cg_u16(c) >= g->n_node) {
                return cg_bad("a child names no node");
            }
            if (n[0] == CG_QUESTION) {
                const char *label = cg_s(g, cg_u16(c + 8));
                if (!cg_str_ok(g, cg_u16(c + 8), 0) || label[0] == '\0' || lstrlenA(label) >= CG_LABEL_BYTES
                    || !cg_text_ok(g, label, 0, 1)) {
                    return cg_bad("a button label is not one the game can show");
                }
            } else if (cg_u16(c + 2) < 1u || cg_u16(c + 2) > 10000u || (cond != CG_NONE && (int)cond >= g->n_cond)
                       || (ce != CG_NONE && (int)ce >= g->n_node)) {
                return cg_bad("a child is not one this game can read");
            }
        }
    }
    if (!cg_acyclic(g)) {
        return cg_bad("its nodes go round in a circle");
    }
    return 1;
}

/* ---- The run ------------------------------------------------------------------------------------------------ */

typedef struct {
    int nodes;
    short node[CG_MAX_PATH];
    int fx;
    int fx_a[CG_MAX_FX];               /* each effect's roll, in the history's order (see cg_roll_effect) */
    int fx_b[CG_MAX_FX];
} cg_history;

/* Everything the run is, kept in the run's file as it is (no pointer). */
typedef struct {
    int phase;                         /* CG_* */
    int game;
    int slot;
    int question;                      /* the start node is a question */
    int pre_pages;                     /* the question's pages shown before its own popup */
    unsigned int planned;              /* the roles to bind (the needed ones and the optional ones planned) */
    unsigned int bound;
    unsigned int gone;                 /* the roles' villagers the event has killed or taken away */
    unsigned int patches;            /* the patches seen on (bit = the .cieg's patch index) */
    int record[CG_MAX_ROLES];
    unsigned int identity[CG_MAX_ROLES];
    int female[CG_MAX_ROLES];
    char name[CG_MAX_ROLES][CG_NAME_BYTES];
    int walked;                        /* walk[] holds the histories */
    cg_history walk[2];                /* [0] with no question; else one a button */
    int choice;                        /* the button answered, -1 */
    int display_count;
    int display_next;                  /* the next display to show: every display before it is shown, and its
                                          effects made */
    int display_used;
    int display_off[CG_MAX_DISPLAYS];
    char displays[CG_DISPLAY_BYTES];   /* each page's words, the names filled in (composed when shown) */
    /* Each display: its layout (1 a question's result, 0 the plain popup), the history's nodes whose effects it
       makes (jobs[job_first .. + job_count]), and -- for a quit -- when they were made and who was gone and who
       each role was just before it. */
    unsigned char display_result[CG_MAX_DISPLAYS];
    unsigned char display_villager[CG_MAX_DISPLAYS];   /* it makes a villager's effect: refusal lines kept */
    short job_first[CG_MAX_DISPLAYS];
    short job_count[CG_MAX_DISPLAYS];
    short jobs[CG_MAX_PATH];
    unsigned __int64 applied_when[CG_MAX_DISPLAYS];   /* 0: nothing made there (yet) */
    unsigned int gone_at[CG_MAX_DISPLAYS];
    unsigned int identity_at[CG_MAX_DISPLAYS][CG_MAX_ROLES];
    char title[CE_TITLE_BYTES];
    unsigned __int64 when;             /* its purchase: only a later save paid for it */
    /* The Island Events log's ONE entry for the event (the owner, 2026-11-12): "  Event: <title>", "  Choice:
       <label>", then every change in page order; entry_at[k] is its length before display k's changes. */
    int entry_len;
    int entry_head;                    /* the header's length */
    int entry_at[CG_MAX_DISPLAYS];
    int sent_len[CG_MAX_DISPLAYS];     /* the entry's length handed to the log at display k (0: none) */
    char entry[CG_ENTRY_BYTES];
} cg_state;

static cg_state cg;
static cg_graph cg_g;
static unsigned char cg_bytes[CG_MAX_FILE];
static unsigned int cg_bytes_size;
static story_village cg_village;
static int cg_display_armed;           /* the armed custom event (or question) is this run's next display */
static int cg_purchasing;              /* the purchase arms its first display: not yet busy */
static int cg_dirty;                   /* the run changed since its file was written */
static ce_event cg_stub;               /* the armed event of a display: the title, no text, no change */
static ce_choice cg_choice_stub;       /* ... and its question's (labels filled in when asked) */
static ce_event cg_one;                /* one villager's change, through ce_apply */

#ifdef VVFP_TEST
static int test_graph_patches = -1;    /* the patches on, -1 = as seen */
static int test_graph_scale = -1;      /* the scale mode, -1 = as the companion says */
static short test_graph_force[64];     /* nodes a draw picks whenever one of them can be drawn */
static int test_graph_forced;
typedef struct {
    int kind;                          /* 1 killed (words), 2 vanished (words), 3 faith conversion */
    int index;
    char words[96];
} cg_told_entry;
static cg_told_entry test_graph_told[32];
static int test_graph_told_count;

static void cg_test_tell(int kind, int index, const char *words) {
    if (test_graph_told_count < 32) {
        cg_told_entry *t = &test_graph_told[test_graph_told_count++];
        t->kind = kind;
        t->index = index;
        lstrcpynA(t->words, words != NULL ? words : "", sizeof t->words);
    }
}
#endif

static int cg_active(int game) {
    return cg.phase != CG_IDLE && cg.phase != CG_DONE && cg.game == game;
}

/* A run of `game` in the village on screen with popups still to come: the event slot is its own. */
static int cg_busy(int game) {
    return !cg_purchasing && cg_active(game) && story_village_is(game, &cg_village);
}

static int cg_owns_armed(int game) {
    return cg_display_armed && ce_armed && ce_armed_event.game == game && cg_active(game);
}

static int cg_owns_asked(int game) {
    return cg.phase == CG_ASKED && cg.game == game && ce_asked && ce_asked_game == game;
}

/* The question being answered (ce_choice_resolve, which has just taken it off the screen) is this run's. */
static int cg_answering(int game) {
    return cg.phase == CG_ASKED && cg.game == game;
}

/* ---- Who may be who --------------------------------------------------------------------------------------- */

static int cg_heathen(int game, const unsigned char *r) {
    return game == 5 && r[0x1CEC] != 0;
}

/* The special villagers a role leaves out unless it allows them (the shipped Aspiring Adventurer's). */
static int cg_special(const ce_adapter *a, int game, const unsigned char *r) {
    int kind = ce_role(a, r, NULL);
    switch (game) {
    case 1: return kind == STORY_KIND_GOLDEN_CHILD;
    case 3: return kind == STORY_KIND_TRIBAL_CHIEF;
    case 5: {
        int role = *(const int *)(r + 0x1CFC);
        return role >= 12 && role <= 17;
    }
    default: return 0;
    }
}

/* Whether record `index` may be role `role` (any binding aside). */
static int cg_eligible(const ce_adapter *a, int game, int role, int index) {
    const unsigned char *spec = cg_role_at(&cg_g, role);
    const unsigned char *r = a->record(index);
    int sex;
    if (spec[0] != 0 || r == NULL || !a->listed(r)) {
        return 0;
    }
    if (game == 3 && r[0xE94] != 0) {
        return 0;                      /* The Secret City's stand-in record */
    }
    if (ce_age(a, r) < 20 * (int)spec[3]) {
        return 0;
    }
    sex = ce_sex(a, r);
    if ((spec[2] == 1 && sex != STORY_SEX_MALE) || (spec[2] == 2 && sex != STORY_SEX_FEMALE)) {
        return 0;
    }
    if ((spec[1] & CG_ROLE_NURSING) && *(const int *)(r + a->off_pregnant) != 0) {
        return 0;
    }
    if ((spec[1] & CG_ROLE_SPECIAL) && cg_special(a, game, r)) {
        return 0;
    }
    if ((spec[1] & CG_ROLE_BELIEVERS) && cg_heathen(game, r)) {
        return 0;
    }
    return 1;
}

/* Kuhn's matching: the roles in `roles` can each be a different eligible villager, none of `used`. */
static int cg_owner[CE_MAX_RECORDS];

static int cg_augment(const ce_adapter *a, int game, int role, unsigned char *seen, const unsigned char *used) {
    int i;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        if (seen[i] || used[i] || !cg_eligible(a, game, role, i)) {
            continue;
        }
        seen[i] = 1;
        if (cg_owner[i] < 0 || cg_augment(a, game, cg_owner[i], seen, used)) {
            cg_owner[i] = role;
            return 1;
        }
    }
    return 0;
}

static int cg_matchable(const ce_adapter *a, int game, unsigned int roles, const unsigned char *used) {
    unsigned char seen[CE_MAX_RECORDS];
    int r;
    for (r = 0; r < CE_MAX_RECORDS; ++r) {
        cg_owner[r] = -1;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        if (!(roles & (1u << r)) || cg_role_at(&cg_g, r)[0] != 0) {
            continue;
        }
        memset(seen, 0, sizeof seen);
        if (!cg_augment(a, game, r, seen, used)) {
            return 0;
        }
    }
    return 1;
}

/* The villager roles the event needs. */
static unsigned int cg_needed(void) {
    unsigned int roles = 0;
    int r;
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        if (spec[0] == 0 && !(spec[1] & CG_ROLE_OPTIONAL)) {
            roles |= 1u << r;
        }
    }
    return roles;
}

/* Whether the village can fill the planned roles now. */
static int cg_feasible(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char used[CE_MAX_RECORDS];
    if (a == NULL) {
        return 0;
    }
    memset(used, 0, sizeof used);
    return cg_matchable(a, game, cg.planned, used);
}

/* Bind every planned role (the game's random routine among those who keep the rest fillable), and each
   stranger's sex.  1 when bound. */
static int cg_bind(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char used[CE_MAX_RECORDS];
    int candidates[CE_MAX_RECORDS];
    unsigned int left = cg.planned;
    int r;
    if (a == NULL) {
        return 0;
    }
    if (cg.bound != 0u) {
        return 1;
    }
    memset(used, 0, sizeof used);
    if (!cg_matchable(a, game, left, used)) {
        return 0;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        int n = 0, i, pick;
        cg.record[r] = -1;
        if (spec[0] == 1) {
            cg.female[r] = spec[2] == 2 ? 1 : spec[2] == 1 ? 0 : ce_random_below(a, 2);
            continue;
        }
        if (!(left & (1u << r))) {
            continue;
        }
        left &= ~(1u << r);
        for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
            if (used[i] || !cg_eligible(a, game, r, i)) {
                continue;
            }
            used[i] = 1;
            if (cg_matchable(a, game, left, used)) {
                candidates[n++] = i;
            }
            used[i] = 0;
        }
        if (n == 0) {
            return 0;
        }
        pick = candidates[ce_random_below(a, n)];
        used[pick] = 1;
        cg.record[r] = pick;
        cg.identity[r] = ce_identity(a, a->record(pick));
        cg.female[r] = ce_sex(a, a->record(pick)) == STORY_SEX_FEMALE;
        ce_copy_name(cg.name[r], CG_NAME_BYTES, a->record(pick) + a->off_name, a->name_bytes);
        cg.bound |= 1u << r;
    }
    return 1;
}

/* The record of role `r` while it still holds the villager bound (alive, listed), else NULL. */
static unsigned char *cg_villager(const ce_adapter *a, int r) {
    if (r < 0 || r >= CG_MAX_ROLES || !(cg.bound & (1u << r)) || (cg.gone & (1u << r))) {
        return NULL;
    }
    return ce_same_villager(a, cg.record[r], cg.identity[r]);
}

/* ---- Conditions, the walk -------------------------------------------------------------------------------- */

static unsigned char cg_visited[(CG_MAX_NODES + 7) / 8];

static int cg_holds_cond(int i, int game, int depth) {
    const unsigned char *c;
    unsigned int a;
    int k;
    if (i == (int)CG_NONE) {
        return 1;
    }
    if (i < 0 || i >= cg_g.n_cond || depth > 64) {
        return 0;
    }
    c = cg_cond_at(&cg_g, i);
    a = cg_u16(c + 2);
    switch (c[0]) {
    case CGC_VISITED: return (cg_visited[a >> 3] >> (a & 7u)) & 1;
    case CGC_ROLE: return (cg.bound >> a) & 1u;
    case CGC_GAME: return (a >> (game - 1)) & 1u;
    case CGC_PATCH: return (cg.patches >> a) & 1u;
    case CGC_NOT: return !cg_holds_cond((int)a, game, depth + 1);
    case CGC_ALL:
        for (k = 0; k < c[1]; ++k) {
            if (!cg_holds_cond((int)a + k, game, depth + 1)) {
                return 0;
            }
        }
        return 1;
    default:
        for (k = 0; k < c[1]; ++k) {
            if (cg_holds_cond((int)a + k, game, depth + 1)) {
                return 1;
            }
        }
        return 0;
    }
}

static void cg_visit(int node) {
    cg_visited[node >> 3] |= (unsigned char)(1u << (node & 7));
}

/* The node's text: its first variant whose condition holds, else its own. */
static const char *cg_node_text(int node, int game) {
    const unsigned char *n = cg_node_at(&cg_g, node);
    int k;
    for (k = 0; k < (int)cg_u16(n + 10); ++k) {
        const unsigned char *v = cg_variant_at(&cg_g, (int)cg_u16(n + 8) + k);
        if (cg_holds_cond((int)cg_u16(v), game, 0)) {
            return cg_s(&cg_g, cg_u16(v + 2));
        }
    }
    return cg_s(&cg_g, cg_u16(n + 6));
}

/* The child drawn at `node` (src/vv_cie_graph.py _resolved_children), -1 at an end. */
static int cg_draw(const ce_adapter *a, int node, int game) {
    const unsigned char *n = cg_node_at(&cg_g, node);
    int targets[256];
    int weights[256];
    int count = 0, total = 0, k, roll;
    for (k = 0; k < (int)cg_u16(n + 14) && count < 256; ++k) {
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(n + 12) + k);
        if (cg_holds_cond((int)cg_u16(c + 4), game, 0)) {
            targets[count] = (int)cg_u16(c);
        } else if (cg_u16(c + 6) != CG_NONE) {
            targets[count] = (int)cg_u16(c + 6);
        } else {
            continue;
        }
        weights[count] = (int)cg_u16(c + 2);
        total += weights[count++];
    }
    if (count == 0) {
        return cg_u16(n + 16) != CG_NONE ? (int)cg_u16(n + 16) : -1;
    }
#ifdef VVFP_TEST
    for (k = 0; k < count; ++k) {
        int f;
        for (f = 0; f < test_graph_forced; ++f) {
            if (test_graph_force[f] == targets[k]) {
                return targets[k];
            }
        }
    }
#endif
    roll = ce_random_below(a, total);
    return targets[ce_roll_index(weights, count, roll)];
}

/* What "Island Events Scale With Population" (1) or "... With Stored Food and Tech Points" (2) does to an
   amount, as its companion scales the game's own events; 0 = not ticked. */
static int cg_scale_mode(void) {
    typedef int (__stdcall *mode_fn)(void);
    HMODULE module;
    mode_fn mode;
#ifdef VVFP_TEST
    if (test_graph_scale >= 0) {
        return test_graph_scale;
    }
#endif
    module = GetModuleHandleA("VVFP Island Events Scale.dll");
    mode = module != NULL ? (mode_fn)(void *)GetProcAddress(module, "VvfpIslandEventsScaleMode") : NULL;
    return mode != NULL ? mode() : 0;
}

static int cg_scaled(const ce_adapter *a, int game, int food, int amount) {
    long long value = amount < 0 ? -(long long)amount : amount;
    int mode = cg_scale_mode();
    if (mode == 2) {
        int stored = food ? ((a->caps & CAP_FOOD) ? a->food() : 0) : ((a->caps & CAP_TECH) ? a->tech() : 0);
        value += stored > 0 ? stored / 10 : 0;
    } else if (mode == 1) {
        int i, n = 0;
        for (i = 0; i < a->record_count; ++i) {
            const unsigned char *r = a->record(i);
            if (r != NULL && a->listed(r) && !cg_heathen(game, r)) {
                ++n;
            }
        }
        value *= n > 50 ? 3 : (n > 25 ? 2 : 1);
    }
    if (value > CE_MAX_AMOUNT) {
        value = CE_MAX_AMOUNT;
    }
    return amount < 0 ? -(int)value : (int)value;
}

/* The skill names of skill effect `e` this game has: their count; with `pick` >= 0 the adapter's index of the
   pick-th one. */
static int cg_skills(const ce_adapter *a, const unsigned char *e, int pick) {
    const char *list = cg_s(&cg_g, cg_u16(e + 12));
    char word[32];
    int n = 0, k, entry;
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            if (lstrcmpiA(a->skill_names[k], word) == 0) {
                if (n == pick) {
                    return k;
                }
                ++n;
                break;
            }
        }
    }
    return pick >= 0 ? -1 : n;
}

/* An effect's own roll as its node is reached, into the history. */
static void cg_roll_effect(const ce_adapter *a, int game, const unsigned char *e, cg_history *h) {
    int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
    int va = 0, vb = 0;
    switch (e[0]) {
    case CGE_FOOD: case CGE_TECH:
        va = (e[2] & 1u) ? cg_scaled(a, game, e[0] == CGE_FOOD, lo) : lo;
        break;
    case CGE_HEALTH:
        va = lo + ce_random_below(a, hi - lo + 1);
        break;
    case CGE_SKILL: {
        int n = cg_skills(a, e, -1);
        va = n > 0 ? cg_skills(a, e, ce_random_below(a, n)) : -1;
        vb = lo + ce_random_below(a, hi - lo + 1);
        break;
    }
    default:
        break;
    }
    if (h->fx < CG_MAX_FX) {
        h->fx_a[h->fx] = va;
        h->fx_b[h->fx] = vb;
    }
    ++h->fx;
}

/* One history from `from`: the nodes and every effect's roll.  `game` and the bound roles and patches decide
   the conditions; the question (start) node counts as visited. */
static void cg_walk(const ce_adapter *a, int game, int from, cg_history *h) {
    int node = from;
    memset(h, 0, sizeof *h);
    memset(cg_visited, 0, sizeof cg_visited);
    if (cg.question) {
        cg_visit(cg_g.start);
    }
    while (node >= 0 && h->nodes < CG_MAX_PATH) {
        const unsigned char *n = cg_node_at(&cg_g, node);
        int k;
        h->node[h->nodes++] = (short)node;
        cg_visit(node);
        for (k = 0; k < (int)cg_u16(n + 20); ++k) {
            cg_roll_effect(a, game, cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k), h);
        }
        if (n[0] == CG_QUESTION) {
            break;
        }
        node = cg_draw(a, node, game);
    }
}

/* ---- Placeholders, pages, popups ------------------------------------------------------------------------- */

static const char *const CG_PRONOUNS[4][2] = { { "he", "she" }, { "his", "her" }, { "him", "her" }, { "man", "woman" } };

/* `raw` with its placeholders filled into `out` (`cap` bytes): CG_EXPAND_AWARD only the award's (the amount and
   its unit, or nothing when there is none: award_kind -1), CG_EXPAND_WORST the longest names the game holds and
   the longer pronouns, CG_EXPAND_REAL the bound villagers.  Returns the length. */
static int cg_expand(const char *raw, char *out, int cap, int mode, int name_room, int award_kind, int award) {
    int o = 0;
    const char *s = raw;
    while (*s != '\0' && o < cap - 1) {
        char word[CG_NAME_BYTES + 32];
        const char *put = NULL;
        int repeat = 0;
        cg_ph ph;
        const char *e;
        if (*s != '(') {
            out[o++] = *s++;
            continue;
        }
        e = s + 1;
        while (*e != '\0' && *e != ')' && *e != '(' && *e != '\n') {
            ++e;
        }
        if (*e != ')' || !cg_parse_ph(&cg_g, s + 1, (int)(e - s - 1), &ph)
            || (mode == CG_EXPAND_AWARD) != (ph.role < 0)) {
            /* not one this pass fills: copied as it is */
            int n = (int)(e - s) + (*e == ')' ? 1 : 0);
            while (n-- > 0 && o < cap - 1) {
                out[o++] = *s++;
            }
            continue;
        }
        if (ph.what == CG_PH_AWARD) {
            if (award_kind >= 0) {
                wsprintfA(word, "%d", award);
                put = word;
            }
        } else if (ph.what == CG_PH_UNIT) {
            put = award_kind < 0 ? NULL : award_kind == 0 ? "food" : "tech points";
        } else if (mode == CG_EXPAND_WORST) {
            if (ph.what == CG_PH_NAME) {
                repeat = name_room;
            } else {
                const char *const *pair = CG_PRONOUNS[ph.what - CG_PH_HE];
                put = lstrlenA(pair[1]) > lstrlenA(pair[0]) ? pair[1] : pair[0];
            }
        } else if (ph.what == CG_PH_NAME) {
            put = (cg.bound & (1u << ph.role)) ? cg.name[ph.role] : "";
        } else {
            put = CG_PRONOUNS[ph.what - CG_PH_HE][cg.female[ph.role] ? 1 : 0];
        }
        if (put != NULL) {
            int first = 1;
            for (; *put != '\0' && o < cap - 1; ++put) {
                char c = *put;
                if (first && ph.capital && c >= 'a' && c <= 'z') {
                    c = (char)(c - 'a' + 'A');
                }
                first = 0;
                out[o++] = c;
            }
        }
        while (repeat-- > 0 && o < cap - 1) {
            out[o++] = 'W';
        }
        s = e + 1;
    }
    out[o] = '\0';
    return o;
}

typedef struct {
    int count;
    int off[CG_MAX_PAGES];
    int src_end[CG_MAX_PAGES];         /* where in the popup's text each page ends */
    int used;
    char buf[CG_RAW_BYTES + CG_MAX_PAGES];
} cg_pages;

typedef struct {
    const ce_adapter *a;
    const ce_layout *first;            /* page 0 */
    const ce_layout *rest;             /* every later page */
    const char *title;
    int reserve;                       /* lines kept free on every page */
    cg_pages *pages;
    const char *src;                   /* the popup's text being laid out ... */
    int consumed;                      /* ... and how much of it the pages so far hold */
    char page[CG_RAW_BYTES];
} cg_pager;

/* `text` (raw: names not filled) fits page `pages->count` at its widest. */
static int cg_fits(cg_pager *w, const char *text) {
    static char worst[CG_RAW_BYTES + 512];
    const ce_layout *l = w->pages->count == 0 ? w->first : w->rest;
    int n = cg_expand(text, worst, sizeof worst, CG_EXPAND_WORST, w->a->name_room, -1, 0);
    return n <= CG_TEXT_MAX && n < (int)sizeof worst - 1 && ce_lines_used_in(l, w->title, worst) <= l->lines - w->reserve;
}

static void cg_flush(cg_pager *w) {
    cg_pages *p = w->pages;
    int n = lstrlenA(w->page);
    if (n > 0 && p->count < CG_MAX_PAGES && p->used + n + 1 <= (int)sizeof p->buf) {
        p->src_end[p->count] = w->consumed;
        p->off[p->count++] = p->used;
        memcpy(p->buf + p->used, w->page, (size_t)n + 1);
        p->used += n + 1;
    }
    w->page[0] = '\0';
}

/* `piece` (`n` bytes) after `sep` on this page, else alone on the next: 1, or 0 when it fits no page. */
static int cg_put(cg_pager *w, const char *sep, const char *piece, int n) {
    static char trial[CG_RAW_BYTES];
    int have = lstrlenA(w->page);
    int s = have > 0 ? lstrlenA(sep) : 0;
    if (have + s + n + 1 < (int)sizeof trial) {
        memcpy(trial, w->page, (size_t)have);
        memcpy(trial + have, sep, (size_t)s);
        memcpy(trial + have + s, piece, (size_t)n);
        trial[have + s + n] = '\0';
        if (cg_fits(w, trial)) {
            memcpy(w->page, trial, (size_t)(have + s + n + 1));
            w->consumed = (int)(piece - w->src) + n;
            return 1;
        }
    }
    if (have > 0) {
        cg_flush(w);
    }
    if (n + 1 < (int)sizeof trial) {
        memcpy(trial, piece, (size_t)n);
        trial[n] = '\0';
        if (cg_fits(w, trial)) {
            memcpy(w->page, trial, (size_t)n + 1);
            w->consumed = (int)(piece - w->src) + n;
            return 1;
        }
    }
    return 0;
}

/* A sentence no page can hold: word after word, page after page (never off the screen). */
static void cg_put_words(cg_pager *w, const char *s, int n) {
    const char *end = s + n;
    while (s < end) {
        const char *e = s;
        while (e < end && *e != ' ') {
            ++e;
        }
        if (!cg_put(w, " ", s, (int)(e - s))) {
            int have = lstrlenA(w->page);
            if ((int)(e - s) + have + 1 < (int)sizeof w->page) {
                memcpy(w->page + have, s, (size_t)(e - s));     /* one word alone: the popup cuts it, as ce_wrap */
                w->page[have + (int)(e - s)] = '\0';
                w->consumed = (int)(e - w->src);
            }
        }
        s = e;
        while (s < end && *s == ' ') {
            ++s;
        }
    }
}

/* The pages of a popup's raw text: whole paragraphs where they fit, else whole sentences (src/vv_cie_graph.py
   paginate), else words. */
static void cg_paginate(cg_pager *w, const char *text) {
    const char *p = text;
    w->pages->count = 0;
    w->pages->used = 0;
    w->page[0] = '\0';
    w->src = text;
    w->consumed = 0;
    for (;;) {
        const char *end = p;
        while (*end != '\0' && *end != '\n') {
            ++end;
        }
        if (!cg_put(w, "\n", p, (int)(end - p))) {
            const char *s = p;
            while (s < end) {
                const char *e = s;
                while (e < end && !(e > s && *e == ' ' && (e[-1] == '.' || e[-1] == '!' || e[-1] == '?'))) {
                    ++e;
                }
                if (!cg_put(w, " ", s, (int)(e - s))) {
                    cg_put_words(w, s, (int)(e - s));
                }
                s = e;
                while (s < end && *s == ' ') {
                    ++s;
                }
            }
        }
        if (*end == '\0') {
            break;
        }
        p = end + 1;
    }
    cg_flush(w);
}

/* A display's text: the title first where the popup leads with it, the page, and -- with `r` -- the refusal
   lines (with their reasons while they fit, else the count alone); 1 when it fits. */
static int cg_compose_once(const ce_layout *l, const char *title, const char *text, const ce_result *r, int reasons,
                           char *out, int size) {
    ce_writer w;
    memset(&w, 0, sizeof w);
    w.out = out;
    w.size = size;
    w.width = l->width;
    w.max_lines = l->lines - 1;
    out[0] = '\0';
    if (l->with_title) {
        ce_wrap(&w, title);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
    }
    ce_wrap(&w, text);
    if (r != NULL && r->refused > 0) {
        char line[CE_WHY_COUNT * 72 + 48];
        if (!reasons || !ce_why_line(r, line)) {
            if (r->refused == 1) {
                ce_tr_done(line, sizeof line, "vvfp.story/story_custom.ce_compose_in_once.s3",
                           "1 change could not be made.", "1 change could not be made.");
            } else {
                ce_tr_printf(line, sizeof line, "vvfp.story/story_custom.ce_compose_in_once.s4",
                             "%d changes could not be made.", r->refused);
            }
        }
        ce_newline(&w);
        ce_line(&w, line);
    }
    return !w.overflow;
}

static void cg_compose(const ce_layout *l, const char *title, const char *text, const ce_result *r, char *out,
                       int size) {
    if (!cg_compose_once(l, title, text, r, 1, out, size) && !cg_compose_once(l, title, text, r, 0, out, size)) {
        cg_compose_once(l, title, text, NULL, 0, out, size);
    }
}

/* A display: its page's words (names filled in), whether it is a question's result, whether its popup carries a
   villager's effect; its jobs are set by the caller.  Its index, or -1 when there is no room. */
static int cg_add_display(const char *text, int result, int villager) {
    int n = lstrlenA(text);
    int k = cg.display_count;
    if (k >= CG_MAX_DISPLAYS || cg.display_used + n + 1 > CG_DISPLAY_BYTES) {
        return -1;
    }
    cg.display_off[k] = cg.display_used;
    memcpy(cg.displays + cg.display_used, text, (size_t)n + 1);
    cg.display_used += n + 1;
    cg.display_result[k] = (unsigned char)(result != 0);
    cg.display_villager[k] = (unsigned char)(villager != 0);
    cg.job_first[k] = 0;
    cg.job_count[k] = 0;
    cg.applied_when[k] = 0;
    cg.sent_len[k] = 0;
    cg.display_count = k + 1;
    return k;
}

static const char *cg_display(int k) {
    return k >= 0 && k < cg.display_count ? cg.displays + cg.display_off[k] : "";
}

/* ---- The effects ------------------------------------------------------------------------------------------ */

typedef void (__stdcall *cg_told_fn)(int game, int index, const char *words);

static void cg_tell_words(const char *export_name, int game, int index, const char *words, int fallback) {
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    cg_told_fn told = module != NULL ? (cg_told_fn)(void *)GetProcAddress(module, export_name) : NULL;
    if (told != NULL) {
        told(game, index, words);
    } else if (fallback == 1) {
        ce_tell_killed(game, index);
    } else if (fallback == 2) {
        ce_tell_cause_of_death(game, index);
    }
}

static void cg_tell_killed(int game, int index, const char *cause) {
#ifdef VVFP_TEST
    cg_test_tell(1, index, cause);
#endif
    if (lstrcmpA(cause, "unknown") == 0) {
        return;                        /* the game's own "Unknown causes", as the stock island events */
    }
    if (lstrcmpA(cause, "custom") == 0) {
        ce_tell_killed(game, index);   /* "Died in a custom island event" */
        return;
    }
    cg_tell_words("VvfpCauseKilledBy", game, index, cause, 1);
}

static void cg_tell_vanished(int game, int index) {
    char words[CE_TITLE_BYTES + 24];
    wsprintfA(words, "Disappeared in %s", cg.title);
#ifdef VVFP_TEST
    cg_test_tell(2, index, words);
#endif
    cg_tell_words("VvfpCauseVanishedBy", game, index, words, 2);
}

/* A believer the event made a Heathen is a faith conversion (the owner): "VVFP Faith Notice.dll" counts it with
   the drift's (its "other" reason), so "Popup When Believers Become Heathens" tells of it when that patch is on. */
static void cg_tell_faith(int game, int index) {
    typedef void (__stdcall *count_fn)(int game, int reason);
    HMODULE module;
    count_fn count;
#ifdef VVFP_TEST
    cg_test_tell(3, index, "");
#endif
    (void)index;
    module = GetModuleHandleA("VVFP Faith Notice.dll");
    count = module != NULL ? (count_fn)(void *)GetProcAddress(module, "VvfpFaithNoticeCount") : NULL;
    if (count != NULL) {
        count(game, 4);
    }
}

static void cg_merge_result(ce_result *into, const ce_result *r) {
    int k;
    into->refused += r->refused;
    into->died += r->died;
    into->vanished += r->vanished;
    for (k = 0; k < CE_WHY_COUNT; ++k) {
        into->why[k] += r->why[k];
    }
}

static void cg_amount(const ce_adapter *a, int food, int amount, ce_result *r) {
    unsigned int cap = food ? CAP_FOOD : CAP_TECH;
    if (!(a->caps & cap)) {
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    if (amount > 0) {
        (food ? a->change_food : a->change_tech)(CE_AMOUNT_ADD, amount);
    } else if (amount < 0) {
        (food ? a->change_food : a->change_tech)(CE_AMOUNT_SUBTRACT, -amount);
    }
}

/* The preference's index by the game's own word, -1 when the game has none. */
static int cg_preference(const ce_adapter *a, const char *word) {
    char entry[48];
    int i;
    for (i = 0; ui_list_entry(a->pref_list, i, entry, sizeof entry); ++i) {
        if (lstrcmpiA(entry, word) == 0) {
            return i < a->pref_count ? i : -1;
        }
    }
    return -1;
}

/* Effect `e` with its rolls (va, vb) on the village; the award's state in *award_kind / *award. */
static void cg_effect(const ce_adapter *a, int game, const unsigned char *e, int va, int vb, int *award_kind,
                      int *award, ce_result *r) {
    unsigned char *record;
    ce_result one;
    ce_change *c;
    int index;
    switch (e[0]) {
    case CGE_FOOD: case CGE_TECH:
        if (e[2] & 2u) {
            *award_kind = e[0] == CGE_FOOD ? 0 : 1;
            *award = va;               /* given by a later "pay_award" */
        } else {
            cg_amount(a, e[0] == CGE_FOOD, va, r);
        }
        return;
    case CGE_PAY:
        if (*award_kind >= 0) {
            cg_amount(a, *award_kind == 0, *award, r);
        }
        return;
    default:
        break;
    }
    record = cg_villager(a, e[1]);
    if (record == NULL) {
        /* Gone since the event began (old age, another event between its pages, or this event): that role's
           later effects are skipped -- never someone else in their record -- and the rest of the event goes on. */
        cg.gone |= 1u << e[1];
        return;
    }
    index = cg.record[e[1]];
    if (e[0] == CGE_KILL || e[0] == CGE_VANISH) {
        if (!(a->caps & (e[0] == CGE_KILL ? CAP_KILL : CAP_VANISH))) {
            ce_refuse(r, CE_WHY_OTHER);
        } else if (e[0] == CGE_KILL && a->kill(index)) {
            ++r->died;
            cg_tell_killed(game, index, cg_s(&cg_g, cg_u16(e + 12)));
        } else if (e[0] == CGE_VANISH && a->vanish(index)) {
            ++r->vanished;
            cg_tell_vanished(game, index);
        } else {
            ce_refuse_as(r, CE_WHY_OTHER);
        }
        cg.gone |= 1u << e[1];         /* gone for good: nothing more is done to them (their name stays) */
        return;
    }
    memset(&cg_one, 0, sizeof cg_one);
    cg_one.game = game;
    cg_one.change_count = 1;
    c = &cg_one.changes[0];
    ce_change_init(c);
    c->index = index;
    c->fingerprint = ce_identity(a, record);
    switch (e[0]) {
    case CGE_STATUS:
        if (game != 5 || !(a->caps & CAP_STATUS)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        if (cg_heathen(game, record)) {
            return;                    /* a Heathen already */
        }
        c->status = 1;                 /* "Becomes a Heathen": the game's own 0x4669E0 */
        break;
    case CGE_HEALTH:
        if (a->set_health == NULL) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->health = va;
        break;
    case CGE_PREF: {
        int value = cg_preference(a, cg_s(&cg_g, cg_u16(e + 12)));
        int dislike = (e[2] & 4u) != 0;
        const int *list = (const int *)(record + (dislike ? a->off_dislikes : a->off_likes));
        int k, have = 0, free_slot = 0;
        if (!(a->caps & CAP_PREFS) || value < 0) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        for (k = 0; k < a->pref_slots; ++k) {
            have |= list[k] == value;
            free_slot |= list[k] == -1;
        }
        c->pref_ops[c->pref_op_count++] = CE_PREF_OP(!dislike, 1, value);   /* never liked and disliked at once */
        if (!have && !free_slot && a->pref_slots > 0) {
            /* A full list: the newest takes the last one's place, as the shipped event's "now dislikes running". */
            c->pref_ops[c->pref_op_count++] = CE_PREF_OP(dislike, 1, list[a->pref_slots - 1]);
        }
        c->pref_ops[c->pref_op_count++] = CE_PREF_OP(dislike, 0, value);
        break;
    }
    case CGE_SKILL: {
        int now, value;
        if (!(a->caps & CAP_SKILLS) || va < 0 || va >= a->skill_count) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        now = a->skills_float ? (int)*(const float *)(record + a->off_skills + 4u * (unsigned int)va)
                              : *(const int *)(record + a->off_skills + 4u * (unsigned int)va);
        value = now + vb;
        c->skills[va] = value > 100 ? 100 : (value < 0 ? 0 : value);
        break;
    }
    case CGE_SICK:
        if (!(a->caps & CAP_SICK)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->sick = 1;
        break;
    default:
        return;
    }
    ce_apply(a, &cg_one, &one);
    cg_merge_result(r, &one);
    if (e[0] == CGE_STATUS && cg_heathen(game, record)) {
        cg_tell_faith(game, index);
    }
    record = a->record(index);
    if (record != NULL && a->listed(record)) {
        cg.identity[e[1]] = ce_identity(a, record);   /* the same villager, with what was just changed */
    }
}

/* ---- One history's popups, their pages, and which page makes which effect ------------------------------------

   THE EFFECTS WAIT FOR THEIR OWN PAGE (the owner, 2026-11-12).  Each node's effects are made when the page that
   shows the END of that node's text is built for the screen -- the moment the game's own plain island event
   makes its changes (as it builds its popup: ce_deliver) and the moment a question's result is built after the
   click (ce_choice_resolve) -- so the page says what has just happened: "Your villagers gain 500 food" is the
   page the award lands on, the ending's last page is the one its death or disappearance comes with.  A node with
   no text (a branch) makes its effects with the text shown just before it (or, before any, with the first).
   Each page's "N changes could not be made" lines tell of that page's own effects. */

typedef struct {
    char raw[CG_RAW_BYTES];            /* the award filled in, the names not */
    int effects;                       /* carries villager effects: two lines kept on each page for the refusals */
} cg_popup;

static cg_popup cg_pops[CG_MAX_POPUPS];
static int cg_pop_count;
static short cg_node_pop[CG_MAX_PATH];     /* each history node: the popup its effects are made with ... */
static short cg_node_end[CG_MAX_PATH];     /* ... at the page holding this much of the popup's text */

/* The award's state before history node `upto` (the last deferred one's kind and amount, -1 none) and the index
   of that node's first effect roll. */
static int cg_award_before(const cg_history *h, int upto, int *kind, int *amount) {
    int fx = 0, i, k;
    *kind = -1;
    *amount = 0;
    for (i = 0; i < upto && i < h->nodes; ++i) {
        const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
        for (k = 0; k < (int)cg_u16(n + 20); ++k, ++fx) {
            const unsigned char *e = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k);
            if ((e[0] == CGE_FOOD || e[0] == CGE_TECH) && (e[2] & 2u)) {
                *kind = e[0] == CGE_FOOD ? 0 : 1;
                *amount = fx < CG_MAX_FX ? h->fx_a[fx] : 0;
            }
        }
    }
    return fx;
}

/* The popups of history `h` as the patcher's walk builds them (src/vv_cie_graph.py walk: a node's effects first --
   an award it defers is the (award) of its own text -- then its text, appended or new), and for each node the
   popup and the place in it its effects go with. */
static void cg_group(int game, const cg_history *h) {
    static char text[CG_RAW_BYTES];
    int award_kind = -1, award = 0, fx = 0, k, i, first_text = -1;
    cg_pop_count = 0;
    memset(cg_visited, 0, sizeof cg_visited);
    if (cg.question) {
        cg_visit(cg_g.start);
    }
    for (i = 0; i < h->nodes; ++i) {
        int node = h->node[i];
        const unsigned char *n = cg_node_at(&cg_g, node);
        int villager = 0;
        cg_visit(node);
        for (k = 0; k < (int)cg_u16(n + 20); ++k, ++fx) {
            const unsigned char *e = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k);
            villager |= e[0] >= CGE_KILL;
            if ((e[0] == CGE_FOOD || e[0] == CGE_TECH) && (e[2] & 2u)) {
                award_kind = e[0] == CGE_FOOD ? 0 : 1;
                award = fx < CG_MAX_FX ? h->fx_a[fx] : 0;
            }
        }
        if (n[0] != CG_BRANCH) {
            cg_popup *p = NULL;
            cg_expand(cg_node_text(node, game), text, sizeof text, CG_EXPAND_AWARD, 0, award_kind, award);
            if (n[1] == 0 || cg_pop_count == 0) {
                if (cg_pop_count < CG_MAX_POPUPS) {
                    p = &cg_pops[cg_pop_count++];
                    memset(p, 0, sizeof *p);
                    lstrcpynA(p->raw, text, sizeof p->raw);
                }
            } else {
                p = &cg_pops[cg_pop_count - 1];
                if (lstrlenA(p->raw) + 1 + lstrlenA(text) + 1 < (int)sizeof p->raw) {
                    lstrcatA(p->raw, n[2] ? "\n" : " ");
                    lstrcatA(p->raw, text);
                }
            }
            if (first_text < 0) {
                first_text = i;
            }
        }
        cg_node_pop[i] = (short)(cg_pop_count - 1);
        cg_node_end[i] = (short)(cg_pop_count > 0 ? lstrlenA(cg_pops[cg_pop_count - 1].raw) : 0);
        if (villager && cg_pop_count > 0) {
            cg_pops[cg_pop_count - 1].effects = 1;
        }
    }
    /* Effects before any text: made with the first text's page. */
    for (i = 0; i < h->nodes && first_text >= 0; ++i) {
        if (cg_node_pop[i] < 0) {
            const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
            cg_node_pop[i] = 0;
            cg_node_end[i] = cg_node_end[first_text];
            for (k = 0; k < (int)cg_u16(n + 20); ++k) {
                if (cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k)[0] >= CGE_KILL) {
                    cg_pops[0].effects = 1;
                }
            }
        }
    }
}

/* The layouts: the question's pages; a result's first page (after a question) or a plain event's; every page
   shown through a notice (the plain popup, never taller than the result's: New Believers' result has more
   lines than its plain popup). */
static ce_layout cg_notice_layout(const ce_adapter *a) {
    ce_layout plain = ce_plain_layout(a);
    plain.check_title = 0;
    return plain;
}

/* History `h` laid out as the run's displays (from the first): `after_question` 1 = page 0 is a question's
   result, 0 = a plain event's first popup; each page with the nodes whose effects it makes. */
static void cg_layout_history(const ce_adapter *a, int game, const cg_history *h, int after_question) {
    static cg_pager w;
    static cg_pages pages;
    static char real[CG_PAGE_BYTES];
    ce_layout first = after_question ? ce_result_layout(a) : cg_notice_layout(a);
    ce_layout rest = cg_notice_layout(a);
    int p, k, i, jobs = 0;
    cg_group(game, h);
    cg.display_count = cg.display_next = cg.display_used = 0;
    for (p = 0; p < cg_pop_count; ++p) {
        w.a = a;
        w.first = p == 0 ? &first : &rest;
        w.rest = &rest;
        w.title = cg.title;
        w.reserve = cg_pops[p].effects ? 2 : 0;
        w.pages = &pages;
        cg_paginate(&w, cg_pops[p].raw);
        for (k = 0; k < pages.count; ++k) {
            int d;
            cg_expand(pages.buf + pages.off[k], real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
            d = cg_add_display(real, p == 0 && k == 0 && after_question, cg_pops[p].effects);
            if (d < 0) {
                return;
            }
            cg.job_first[d] = (short)jobs;
            for (i = 0; i < h->nodes; ++i) {
                const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
                int page = 0;
                if (cg_node_pop[i] != p || cg_u16(n + 20) == 0u) {
                    continue;
                }
                while (page + 1 < pages.count && pages.src_end[page] < cg_node_end[i]) {
                    ++page;            /* the page holding the end of the node's text */
                }
                if (page == k && jobs < CG_MAX_PATH) {
                    cg.jobs[jobs++] = (short)i;
                }
            }
            cg.job_count[d] = (short)(jobs - cg.job_first[d]);
        }
    }
}

/* ---- The Island Events log's one entry ("VVFP Island Events.dll", native/vvfp_island_events) ----------------

   The owner (2026-11-12): ONE entry per branching event -- the title, the "Choice:" line, then every change in page
   order as it happens.  Each page that makes effects is bracketed through that companion's own comparison
   (VvfpIslandEventsGraphBegin / End: the same field words, as "  <name>: <Label> <old> -> <new>" lines), appended
   to the entry the run keeps (cg.entry, in the run's file: a quit continues the same entry, and a page shown again
   after a restore first takes its own lines back, entry_at), and the entry so far is handed over after each page
   (VvfpIslandEventsGraphWrite -> the Parentage Export's WriteVillageEventEntry: a held record REPLACED each time,
   whose next save writes what it has gained onto the same on-disk entry), so the log matches the save at every
   save; the event's end closes it.  A run put back after a reload tells the log what the save's log already holds
   (sent_len).  The game's own bracket around each of these popups writes nothing for it (VvfpStoryGraphLogged).
   Without that companion (its row off): nothing. */

typedef int (__stdcall *cg_log_begin_fn)(int game);
typedef int (__stdcall *cg_log_end_fn)(int game, char *out, int cap);
typedef int (__stdcall *cg_log_write_fn)(int game, int key, const char *text, int disk, int final);
static int cg_logged;                  /* the game whose last popup was this run's (asked once by the log) */

#ifdef VVFP_TEST
static int test_graph_log;             /* stands in for the companion: each page's lines "  page <k>" */
static int test_graph_log_page;
static char test_graph_entry[CG_ENTRY_BYTES];   /* the entry handed over as final, last */
static int test_graph_entries;          /* ...and how many times */
static char test_graph_sent[CG_ENTRY_BYTES];    /* the entry handed over last (any) */
static int test_graph_sent_disk, test_graph_sent_final, test_graph_sends;
#endif

static FARPROC cg_log_export(const char *name) {
    HMODULE module = GetModuleHandleA("VVFP Island Events.dll");
    return module != NULL ? GetProcAddress(module, name) : NULL;
}

static void cg_entry_put(const char *text) {
    int n = lstrlenA(text);
    if (cg.entry_len + n + 1 < CG_ENTRY_BYTES) {
        memcpy(cg.entry + cg.entry_len, text, (size_t)n + 1);
        cg.entry_len += n;
    }
}

/* The entry's header: the title, and the button clicked (`label`, or NULL with no question). */
static void cg_entry_start(const char *label) {
    char line[CE_TITLE_BYTES + CE_BUTTON_BYTES + 32];
    cg.entry_len = 0;
    cg.entry[0] = '\0';
    wsprintfA(line, "  Event: %s\n", cg.title);
    cg_entry_put(line);
    if (label != NULL) {
        wsprintfA(line, "  Choice: %s\n", label);
        cg_entry_put(line);
    }
    cg.entry_head = cg.entry_len;
}

static int cg_log_begin(int game) {
    cg_log_begin_fn begin;
#ifdef VVFP_TEST
    if (test_graph_log) {
        test_graph_log_page = cg.display_next;
        return 1;
    }
#endif
    begin = (cg_log_begin_fn)(void *)cg_log_export("VvfpIslandEventsGraphBegin");
    return begin != NULL && begin(game);
}

static void cg_log_end(int game) {
    static char lines[4096];
    cg_log_end_fn end;
    lines[0] = '\0';
#ifdef VVFP_TEST
    if (test_graph_log) {
        wsprintfA(lines, "  page %d\n", test_graph_log_page);
        cg_entry_put(lines);
        return;
    }
#endif
    end = (cg_log_end_fn)(void *)cg_log_export("VvfpIslandEventsGraphEnd");
    if (end != NULL && end(game, lines, (int)sizeof lines) > 0) {
        cg_entry_put(lines);
    }
}

/* The entry as it is now, handed to the log (VvfpIslandEventsGraphWrite -> the Parentage Export's
   WriteVillageEventEntry): its held record replaced, so the next save writes what it has gained onto the same
   entry -- the log matches the save at every save.  `disk`: what the last save's log holds of it (a run put back
   after a reload; -1 when the log already knows), `final` 1 when the event is over. */
static int cg_log_key(void) {
    return (int)((unsigned int)cg.when & 0x7FFFFFFFu) | 1;
}

static void cg_log_send(int game, int disk, int final) {
    cg_log_write_fn write;
    if (cg.entry_head == 0) {
        return;                        /* not started (no answer yet) */
    }
#ifdef VVFP_TEST
    if (test_graph_log) {
        lstrcpynA(test_graph_sent, cg.entry, sizeof test_graph_sent);
        test_graph_sent_disk = disk;
        test_graph_sent_final = final;
        ++test_graph_sends;
        if (final) {
            lstrcpynA(test_graph_entry, cg.entry, sizeof test_graph_entry);
            ++test_graph_entries;
        }
        return;
    }
#endif
    write = (cg_log_write_fn)(void *)cg_log_export("VvfpIslandEventsGraphWrite");
    if (write != NULL) {
        (void)write(game, cg_log_key(), cg.entry, disk, final);
    }
}

/* The event is over: its one entry closed ("Changes: none" when it changed nothing, as every event shown is). */
static void cg_log_write(int game) {
    if (cg.entry_head == 0) {
        return;
    }
    if (cg.entry_len == cg.entry_head) {
        cg_entry_put("  Changes: none\n");
    }
    cg_log_send(game, -1, 1);
}

/* Asked by "VVFP Island Events.dll" as it compares the popup the game just showed: 1 (once) when it was this
   run's page or question -- its changes are the event's one entry's, never a record of their own. */
__declspec(dllexport) int __stdcall VvfpStoryGraphLogged(int game, const char *title) {
    if (cg_logged == 0 || cg_logged != game) {
        return 0;
    }
    if (title != NULL && title[0] != '\0' && lstrcmpA(title, cg.title) != 0) {
        return 0;                      /* another event's popup */
    }
    cg_logged = 0;
    return 1;
}

/* The effects display `k` makes, each once: every node of its jobs, in the history's order, the award's state
   and the rolls as the walk left them. */
static void cg_make_effects(const ce_adapter *a, int game, int k, ce_result *r) {
    const cg_history *h = &cg.walk[cg.choice > 0 ? 1 : 0];
    int j;
    memset(r, 0, sizeof *r);
    cg.gone_at[k] = cg.gone;
    memcpy(cg.identity_at[k], cg.identity, sizeof cg.identity);
    for (j = 0; j < cg.job_count[k]; ++j) {
        int i = cg.jobs[cg.job_first[k] + j];
        const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
        int award_kind, award, fx, e;
        fx = cg_award_before(h, i, &award_kind, &award);
        for (e = 0; e < (int)cg_u16(n + 20); ++e, ++fx) {
            const unsigned char *eff = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + e);
            int va = fx < CG_MAX_FX ? h->fx_a[fx] : 0, vb = fx < CG_MAX_FX ? h->fx_b[fx] : 0;
            cg_effect(a, game, eff, va, vb, &award_kind, &award, r);
        }
    }
    if (cg.job_count[k] > 0) {
        cg.applied_when[k] = sq_clock();
    }
}

/* Show display `k` (the next one): its effects made, then its words composed for its popup with that page's
   refusal lines, into `text`. */
static void cg_show(const ce_adapter *a, int game, int k, char *text, int size) {
    ce_result r;
    ce_layout l = cg.display_result[k] ? ce_result_layout(a) : cg_notice_layout(a);
    int logging;
    cg.entry_at[k] = cg.entry_len;
    logging = cg.job_count[k] > 0 && cg_log_begin(game);
    cg_make_effects(a, game, k, &r);
    if (logging) {
        cg_log_end(game);              /* this page's changes, appended to the event's one entry ... */
        if (cg.display_next + 1 < cg.display_count || cg.phase != CG_CHAIN) {
            cg_log_send(game, -1, 0);  /* ... and the entry so far held for the next save (the last page's: final) */
            cg.sent_len[k] = cg.entry_len;
        }
    }
    cg_logged = game;                  /* the game's own bracket around this popup is not a record of its own */
    cg_compose(&l, cg.title, cg_display(k), r.refused > 0 ? &r : NULL, text, size);
    cg.display_next = k + 1;
}

/* The question's text (the start node, its variant for this run) laid out in pages for the question popup; the
   pages before the last are shown first (through a plain popup, which is never smaller). */
static void cg_question_pages(const ce_adapter *a, int game, cg_pages *pages) {
    static cg_pager w;
    static char raw[CG_RAW_BYTES];
    ce_layout q = ce_question_layout(a);
    memset(cg_visited, 0, sizeof cg_visited);
    cg_visit(cg_g.start);
    cg_expand(cg_node_text(cg_g.start, game), raw, sizeof raw, CG_EXPAND_AWARD, 0, -1, 0);
    q.check_title = 0;
    w.a = a;
    w.first = &q;
    w.rest = &q;
    w.title = cg.title;
    w.reserve = 0;
    w.pages = pages;
    cg_paginate(&w, raw);
}

/* ---- Arming each display ----------------------------------------------------------------------------------- */

/* The next display is the question (its earlier pages shown, or none). */
static int cg_next_is_question(void) {
    return cg.question && (cg.phase == CG_ASKED || (cg.phase == CG_QUEUED && cg.pre_pages == 0)
                           || (cg.phase == CG_PRE && cg.display_next >= cg.display_count));
}

/* Arm the run's next display in `game`: the island event made due as the purchase makes it (`due`), or only
   remembered (a restore: the save holds the timer).  The question and the event's first popup are the island
   event (counted); every other page a notice.  1 when armed. */
static int cg_arm(int game, int due) {
    int question = cg_next_is_question();
    int notice = cg.phase != CG_QUEUED && !question;
    memset(&cg_stub, 0, sizeof cg_stub);
    cg_stub.game = game;
    lstrcpynA(cg_stub.title, cg.title, sizeof cg_stub.title);
    if (question) {
        int b;
        /* (Only its own fields: the stub's outcomes stay zero, never written.) */
        cg_choice_stub.enabled = 1;
        cg_choice_stub.featured_record = 0;
        cg_choice_stub.featured_identity = 0;
        for (b = 0; b < 2; ++b) {
            const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, cg_g.start) + 12) + b);
            lstrcpynA(cg_choice_stub.labels[b], cg_s(&cg_g, cg_u16(c + 8)), CE_BUTTON_BYTES);
            cg_choice_stub.outcome_count[b] = 1;
            cg_choice_stub.outcomes[b][0].chance = 1;
        }
    }
    if (due) {
        if (!ce_arm_with(game, &cg_stub, question ? &cg_choice_stub : NULL, notice)) {
            return 0;
        }
    } else {
        ce_armed_event = cg_stub;
        ce_store_choice(game, question ? &cg_choice_stub : NULL);
        ce_armed = 1;
        ce_armed_is_notice = notice;
        ce_wait_arm = 0;
        ce_armed_village = story_village_now(game);
    }
    cg_display_armed = 1;
    return 1;
}

/* Whether the run has a display still to show (and none armed or asked). */
static int cg_wants_display(void) {
    if (cg.phase == CG_IDLE || cg.phase == CG_DONE || cg_display_armed || (ce_asked && cg.phase == CG_ASKED)) {
        return 0;
    }
    switch (cg.phase) {
    case CG_QUEUED: case CG_ASKED: return 1;
    case CG_PRE: return 1;
    default: return cg.display_next < cg.display_count;
    }
}

/* The slot is free for a display: nothing else armed or on its way, and the game's trigger could show it. */
static int cg_slot_free(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL || !story_installed(game) || ce_armed || ce_asked || pick_slot >= 0 || GAMES[game].island_pending()
        || time_skip_event_open()) {
        return 0;
    }
    ce_refusal_for_choice = cg_next_is_question();
    {
        const char *refused = a->arm_refusal();
        ce_refusal_for_choice = 0;
        return refused == NULL;
    }
}

/* Every page shown: done -- its file kept (CG_DONE) until a save holds the effects of its last pages
   (cg_flush_file), so a crash before that save brings back exactly the pages whose effects the save lacks. */
static void cg_finish(void) {
    int k;
    cg_log_write(cg.game);             /* the Island Events log's one entry, now whole */
    if (cg.display_count > 0 && cg.entry_head > 0) {
        cg.sent_len[cg.display_count - 1] = cg.entry_len;
    }
    cg.phase = CG_IDLE;
    for (k = 0; k < cg.display_count; ++k) {
        if (cg.applied_when[k] != 0) {
            cg.phase = CG_DONE;
        }
    }
    cg_display_armed = 0;
    cg_dirty = 1;
}

/* ---- The hooks story_custom.inc calls ------------------------------------------------------------------- */

/* ce_held: a run not yet shown waits while the village cannot fill its roles; the island event is made due again
   once it can (ce_opening_tick). */
static int cg_holds(int game) {
    if (!cg_owns_armed(game) || cg.phase != CG_QUEUED || cg.bound != 0u || cg_feasible(game)) {
        return 0;
    }
    ce_wait_arm = 1;
    return 1;
}

/* The roles bound before the first display (the rolls that pick them are the game's own). */
static int cg_prepare(int game) {
    if (cg.phase != CG_QUEUED || cg.bound != 0u) {
        return 1;
    }
    if (!cg_bind(game)) {
        ce_wait_arm = 1;
        return 0;
    }
    cg_dirty = 1;
    return 1;
}

/* Whether the display ce_deliver is about to show is the island event itself (a plain event's first page), not a
   notice page. */
static int cg_counted_next(void) {
    return cg.phase == CG_QUEUED && !cg.question;
}

/* The display ce_deliver shows: *counted 1 when it is the event itself (a plain event's first page), 0 for a
   notice page.  1 when `text` holds it. */
static int cg_deliver(int game, char *text, int size, int *counted) {
    const ce_adapter *a = ce_adapter_for(game);
    *counted = 0;
    if (a == NULL) {
        return 0;
    }
    cg_display_armed = 0;
    if (cg.phase == CG_QUEUED) {
        cg.display_count = cg.display_next = cg.display_used = 0;
        if (cg.question) {
            static cg_pages pages;
            static char real[CG_PAGE_BYTES];
            int k;
            cg_question_pages(a, game, &pages);
            for (k = 0; k + 1 < pages.count; ++k) {
                cg_expand(pages.buf + pages.off[k], real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
                (void)cg_add_display(real, 0, 0);
            }
            cg.phase = CG_PRE;
        } else {
            cg_walk(a, game, cg_g.start, &cg.walk[0]);
            cg.walked = 1;
            cg.choice = -1;
            cg_layout_history(a, game, &cg.walk[0], 0);
            cg_entry_start(NULL);
            cg.phase = CG_CHAIN;
            *counted = 1;
        }
    }
    if (cg.display_next < cg.display_count) {
        cg_show(a, game, cg.display_next, text, size);
    } else if (size > 0) {
        text[0] = '\0';
    }
    if (cg.phase == CG_CHAIN && cg.display_next >= cg.display_count) {
        cg_finish();
    }
    cg_dirty = 1;
    return 1;
}

/* The question (ce_choice_begin): both histories walked now, the last page of its text into `text`, its labels
   with the names filled in. */
static void cg_begin_question(int game, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    static cg_pages pages;
    static char real[CG_PAGE_BYTES];
    ce_layout q;
    int b;
    if (a == NULL) {
        return;
    }
    cg_display_armed = 0;
    q = ce_question_layout(a);
    q.check_title = 0;
    cg_question_pages(a, game, &pages);
    cg_expand(pages.count > 0 ? pages.buf + pages.off[pages.count - 1] : "", real, sizeof real, CG_EXPAND_REAL,
              a->name_room, -1, 0);
    cg_compose(&q, cg.title, real, NULL, text, size);
    if (!cg.walked) {
        for (b = 0; b < 2; ++b) {
            const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, cg_g.start) + 12) + b);
            cg_walk(a, game, (int)cg_u16(c), &cg.walk[b]);
        }
        cg.walked = 1;
    }
    for (b = 0; b < 2; ++b) {
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, cg_g.start) + 12) + b);
        cg_expand(cg_s(&cg_g, cg_u16(c + 8)), real, CE_BUTTON_BYTES, CG_EXPAND_REAL, a->name_room, -1, 0);
        lstrcpynA(ce_choice_store[ce_asked_store].labels[b], real, CE_BUTTON_BYTES);
    }
    cg.phase = CG_ASKED;
    cg.display_count = cg.display_next = cg.display_used = 0;
    cg_logged = game;                  /* the question's own popup: the entry's, written when the event is over */
    cg_dirty = 1;
}

/* The answer (ce_choice_resolve): that button's history laid out in pages, and its first page shown -- with the
   effects that page makes (the rest wait for their own pages). */
static int cg_resolve(int game, int button, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL || button < 0 || button > 1 || !cg.walked) {
        return 0;
    }
    cg.choice = button;
    cg_layout_history(a, game, &cg.walk[button], 1);
    {
        /* The entry's header: the title and the button clicked, as the game showed it. */
        static char label[CE_BUTTON_BYTES];
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, cg_g.start) + 12) + button);
        cg_expand(cg_s(&cg_g, cg_u16(c + 8)), label, CE_BUTTON_BYTES, CG_EXPAND_REAL, a->name_room, -1, 0);
        cg_entry_start(label);
    }
    cg.phase = CG_CHAIN;
    if (cg.display_count > 0) {
        cg_show(a, game, 0, text, size);
    } else if (size > 0) {
        text[0] = '\0';
    }
    if (cg.display_next >= cg.display_count) {
        cg_finish();
    }
    cg_dirty = 1;
    return 1;
}

/* ce_choice_tallest: the result `button` will show first, with room for its refusal lines when that page makes a
   villager's effect.  (Laid out and set aside: nothing is made, the run stays asked.) */
static int cg_tallest(int game, int button, char *out, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    ce_layout first;
    ce_result most;
    int lines;
    if (a == NULL || button < 0 || button > 1 || !cg.walked) {
        return 0;
    }
    cg_layout_history(a, game, &cg.walk[button], 1);
    if (cg.display_count == 0) {
        return 0;
    }
    first = ce_result_layout(a);
    memset(&most, 0, sizeof most);
    most.refused = 999;
    cg_compose(&first, cg.title, cg_display(0), cg.display_villager[0] && cg.job_count[0] > 0 ? &most : NULL, out,
               size);
    lines = ce_text_lines(out);
    cg.display_count = cg.display_next = cg.display_used = 0;
    return lines;
}

/* ce_choice_featured: the subject, the villager the question is about. */
static int cg_featured(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL || !cg_prepare(game)) {
        return -1;
    }
    return cg_villager(a, 0) != NULL ? cg.record[0] : -1;
}

/* ---- Queueing ----------------------------------------------------------------------------------------------- */

/* What role `r` needs, in words. */
static void cg_role_words(int game, int r, char *out, int size) {
    const unsigned char *spec = cg_role_at(&cg_g, r);
    char part[96];
    wsprintfA(out, "a %svillager of %d or more", spec[2] == 1 ? "male " : spec[2] == 2 ? "female " : "", (int)spec[3]);
    if (spec[1] & CG_ROLE_NURSING) {
        lstrcatA(out, ", not carrying or nursing a baby");
    }
    if (spec[1] & CG_ROLE_SPECIAL) {
        const char *who = game == 1 ? "the Golden Child" : game == 3 ? "the Tribal Chief"
                        : game == 5 ? "a chief, the Retired Chief or a puzzle's Heathen" : NULL;
        if (who != NULL) {
            wsprintfA(part, ", not %s", who);
            lstrcatA(out, part);
        }
    }
    if ((spec[1] & CG_ROLE_BELIEVERS) && game == 5) {
        lstrcatA(out, ", a believer");
    }
    (void)size;
}

/* Whether the patches named by the event are on: Guardians of Isola's rewrite (New Believers) is seen in the
   game's own text, as the Faith popup sees it; any other patch is off. */
static unsigned int cg_patches_on(int game) {
    unsigned int on = 0;
    int i;
#ifdef VVFP_TEST
    if (test_graph_patches >= 0) {
        return (unsigned int)test_graph_patches;
    }
#endif
    for (i = 0; i < cg_g.n_patch; ++i) {
        const char *id = cg_s(&cg_g, cg_u16(cg_g.d + cg_g.o_patch + 2u * (unsigned int)i));
        if (game == 5 && lstrcmpA(id, "guardians_of_isola") == 0 && faith_notice_left_the_tribe()) {
            on |= 1u << i;
        }
    }
    return on;
}

/* Why the loaded event cannot be queued in `game` now, or NULL; `planned` the roles it will bind. */
static const char *cg_refusal(int game, unsigned int *planned) {
    static char reason[400];
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char used[CE_MAX_RECORDS];
    unsigned int needed;
    int question, r, i;
    if (a == NULL) {
        return "Custom Island Event is not available in this game.";
    }
    if (!(cg_g.games & (1u << (game - 1)))) {
        wsprintfA(reason, "\"%s\" is not made for %s.", cg_s(&cg_g, (unsigned int)cg_g.title), a->game_name);
        return reason;
    }
    question = cg_node_at(&cg_g, cg_g.start)[0] == CG_QUESTION;
    if (question && !ce_choice_available(a)) {
        return "This game can not ask a question with two choices yet.";
    }
    ce_refusal_for_choice = question;
    {
        const char *why = a->arm_refusal();
        ce_refusal_for_choice = 0;
        if (why != NULL) {
            return why;
        }
    }
    memset(used, 0, sizeof used);
    needed = cg_needed();
    for (r = 0; r < cg_g.n_role; ++r) {
        if (!(needed & (1u << r))) {
            continue;
        }
        for (i = 0; i < a->record_count && !cg_eligible(a, game, r, i); ++i) {
        }
        if (i >= a->record_count) {
            char words[200];
            cg_role_words(game, r, words, sizeof words);
            wsprintfA(reason, "Nobody in the village can be the event's %s now: it needs %s. Nothing has been queued.",
                      cg_s(&cg_g, cg_u16(cg_role_at(&cg_g, r) + 4)), words);
            return reason;
        }
    }
    if (!cg_matchable(a, game, needed, used)) {
        return "The village does not have enough different villagers for the event's roles now. "
               "Nothing has been queued.";
    }
    *planned = needed;
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        if (spec[0] == 0 && (spec[1] & CG_ROLE_OPTIONAL) && cg_matchable(a, game, *planned | (1u << r), used)) {
            *planned |= 1u << r;       /* an optional role the village can fill now */
        }
    }
    return NULL;
}

/* A role that may be a special villager: the purchase warns before it is made. */
static const char *cg_risk(int game) {
    int r;
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        if (spec[0] == 0 && !(spec[1] & CG_ROLE_SPECIAL) && (game == 1 || game == 3 || game == 5)) {
            return game == 1 ? "This event may choose the Golden Child, whom the game's puzzles need."
                 : game == 3 ? "This event may choose the Tribal Chief."
                             : "This event may choose a chief, the Retired Chief or a puzzle's Heathen, whom the "
                               "game's story needs.";
        }
    }
    return NULL;
}

/* Queue the loaded event in `game` (the checks made: cg_refusal), its first display made due as the purchase does.
   1 on success. */
static int cg_queue(int game, unsigned int planned, int due) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL) {
        return 0;
    }
    memset(&cg, 0, sizeof cg);
    cg.game = game;
    cg.slot = story_current_slot(game);
    cg.question = cg_node_at(&cg_g, cg_g.start)[0] == CG_QUESTION;
    cg.planned = planned;
    cg.patches = cg_patches_on(game);
    cg.choice = -1;
    lstrcpynA(cg.title, cg_s(&cg_g, (unsigned int)cg_g.title), sizeof cg.title);
    if (cg.question) {
        static cg_pages pages;
        unsigned int keep = cg.bound;
        cg.bound = planned;            /* the conditions see the roles it will bind */
        cg_question_pages(a, game, &pages);
        cg.bound = keep;
        cg.pre_pages = pages.count > 0 ? pages.count - 1 : 0;
    }
    cg.phase = CG_QUEUED;
    cg_village = story_village_now(game);
    cg_purchasing = 1;                 /* not busy while the purchase checks what waits */
    if (!cg_arm(game, due)) {
        cg_purchasing = 0;
        memset(&cg, 0, sizeof cg);
        cg_display_armed = 0;
        return 0;
    }
    cg_purchasing = 0;
    cg.when = sq_clock();
    cg_dirty = 1;
    return 1;
}

/* Every frame (VvfpStoryInstall): the next display armed once the slot is free; a run of another village set
   aside (its file waits for it). */
static void cg_tick(int game) {
    if (cg.phase == CG_IDLE || cg.phase == CG_DONE) {
        return;
    }
    if (cg.game == game && !story_village_is(game, &cg_village)) {
        cg.phase = CG_IDLE;            /* another village: memory only, the file stays its village's */
        cg_display_armed = 0;
        cg_dirty = 0;
        return;
    }
    if (cg_display_armed && !(ce_armed && ce_armed_event.game == cg.game)) {
        cg_display_armed = 0;          /* dropped (another village, a reset) */
    }
    if (cg.game != game || !cg_wants_display() || !cg_slot_free(game)) {
        return;
    }
    if (cg.phase == CG_QUEUED && !cg_feasible(game)) {
        return;                        /* still waiting for the roles */
    }
    (void)cg_arm(game, 1);
}

/* ---- The run's file ---------------------------------------------------------------------------------------- */

#define CG_FILE_MAGIC 0x31474356u      /* 'V' 'C' 'G' '1' */
#define CG_FILE_VERSION 1u

typedef struct {
    unsigned int magic;
    unsigned int version;
    unsigned int game;
    unsigned int slot;
    unsigned int state_bytes;          /* sizeof(cg_state) */
    unsigned int graph_bytes;          /* the .cieg after the state */
    unsigned int roster[256];
} cg_file_head;

static cg_file_head cg_head;
static unsigned char cg_read_buf[CG_MAX_FILE];
static cg_state cg_read_state;

#ifdef VVFP_TEST
static unsigned char cg_test_file[sizeof(cg_file_head) + sizeof(cg_state) + CG_MAX_FILE];
static unsigned int cg_test_size;

static int cg_file_read(int game, int slot) {
    (void)game;
    (void)slot;
    if (cg_test_size < sizeof cg_head + sizeof cg_read_state) {
        return 0;
    }
    memcpy(&cg_head, cg_test_file, sizeof cg_head);
    memcpy(&cg_read_state, cg_test_file + sizeof cg_head, sizeof cg_read_state);
    if (cg_head.graph_bytes > CG_MAX_FILE
        || cg_test_size != sizeof cg_head + sizeof cg_read_state + cg_head.graph_bytes) {
        return 0;
    }
    memcpy(cg_read_buf, cg_test_file + sizeof cg_head + sizeof cg_read_state, cg_head.graph_bytes);
    return 1;
}

static int cg_file_write(int game, int slot) {
    (void)game;
    (void)slot;
    memcpy(cg_test_file, &cg_head, sizeof cg_head);
    memcpy(cg_test_file + sizeof cg_head, &cg, sizeof cg);
    memcpy(cg_test_file + sizeof cg_head + sizeof cg, cg_bytes, cg_bytes_size);
    cg_test_size = (unsigned int)(sizeof cg_head + sizeof cg) + cg_bytes_size;
    return 1;
}

static void cg_file_remove(int game, int slot) {
    (void)game;
    (void)slot;
    cg_test_size = 0;
}
#else
static int cg_file_read(int game, int slot) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0, more = 0, graph = 0;
    BOOL ok;
    if (!vv_paid_named_path(game, slot, "Story Purchases Graph", path, 0)) {
        return 0;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(h, &cg_head, sizeof cg_head, &got, NULL) && got == sizeof cg_head
        && ReadFile(h, &cg_read_state, sizeof cg_read_state, &more, NULL) && more == sizeof cg_read_state
        && cg_head.graph_bytes <= CG_MAX_FILE
        && ReadFile(h, cg_read_buf, cg_head.graph_bytes, &graph, NULL) && graph == cg_head.graph_bytes;
    CloseHandle(h);
    return ok ? 1 : 0;
}

static int cg_file_write(int game, int slot) {
    char path[MAX_PATH];
    const void *parts[3];
    DWORD sizes[3];
    if (!vv_paid_named_path(game, slot, "Story Purchases Graph", path, 1)) {
        return 0;
    }
    parts[0] = &cg_head;
    sizes[0] = sizeof cg_head;
    parts[1] = &cg;
    sizes[1] = sizeof cg;
    parts[2] = cg_bytes;
    sizes[2] = cg_bytes_size;
    return vv_paid_write_parts(path, parts, sizes, 3);
}

static void cg_file_remove(int game, int slot) {
    char path[MAX_PATH];
    if (vv_paid_named_path(game, slot, "Story Purchases Graph", path, 0)) {
        DeleteFileA(path);
    }
}
#endif

/* A village came on screen (story_queue.inc sq_sync, the first time it is seen, on the tick or where the game
   asks for an armed event): a run of another village is set aside, and this slot's run put back when the save
   paid for it. */
static void cg_village_seen(int game, int slot, const unsigned int *roster) {
    unsigned __int64 saved = 0;
    static cg_graph check;
    if (cg.phase != CG_IDLE && !(cg.game == game && story_village_is(game, &cg_village))) {
        cg.phase = CG_IDLE;
        cg_display_armed = 0;
        cg_dirty = 0;
    }
    if (cg.phase != CG_IDLE || !cg_file_read(game, slot)) {
        return;
    }
    if (cg_head.magic != CG_FILE_MAGIC || cg_head.version != CG_FILE_VERSION || cg_head.game != (unsigned int)game
        || cg_head.slot != (unsigned int)slot || cg_head.state_bytes != sizeof(cg_state)
        || cg_read_state.game != game || cg_read_state.phase == CG_IDLE
        || !cg_load(&check, cg_read_buf, cg_head.graph_bytes) || !sq_same_village(cg_head.roster, roster)) {
        return;
    }
    if (!sq_save_time(game, slot, &saved) || cg_read_state.when > saved) {
        cg_file_remove(game, slot);    /* newer than the save: the save never held it */
        return;
    }
    memcpy(cg_bytes, cg_read_buf, cg_head.graph_bytes);
    cg_bytes_size = cg_head.graph_bytes;
    cg_g = check;                      /* checked above: the same bytes, now in the run's own buffer */
    cg_g.d = cg_bytes;
    cg = cg_read_state;
    cg_village = story_village_now(game);
    cg_display_armed = 0;
    {
        /* EXACTLY ONCE.  The save holds the effects of every page made before it, and none after: the pages from
           the first whose effects the save lacks are shown again (their effects made then), the roles as they were
           just before that page.  A question whose answer the save lacks is asked again (the same histories). */
        int k, rewind = -1;
        int shown = cg.phase == CG_DONE ? cg.display_count : cg.display_next;
        for (k = 0; k < shown && k < CG_MAX_DISPLAYS; ++k) {
            if (cg.applied_when[k] != 0 && cg.applied_when[k] > saved) {
                rewind = k;
                break;
            }
        }
        if (rewind >= 0) {
            cg.gone = cg.gone_at[rewind];
            memcpy(cg.identity, cg.identity_at[rewind], sizeof cg.identity);
            /* The entry continues from that page: its own lines are taken back, made again as it is shown. */
            cg.entry_len = cg.question && rewind == 0 ? 0 : cg.entry_at[rewind];
            if (cg.entry_len == 0) {
                cg.entry_head = 0;
            }
            cg.entry[cg.entry_len] = '\0';
            for (k = rewind; k < cg.display_count; ++k) {
                cg.applied_when[k] = 0;
                cg.sent_len[k] = 0;
            }
            if (cg.question && rewind == 0) {
                cg.phase = CG_ASKED;
                cg.choice = -1;
            } else {
                cg.phase = CG_CHAIN;
                cg.display_next = rewind;
            }
        } else if (cg.phase == CG_DONE) {
            memset(&cg, 0, sizeof cg);     /* over, and the save holds it all */
            cg_file_remove(game, slot);
            return;
        }
    }
    if (cg.phase == CG_ASKED) {
        cg.display_count = cg.display_next = 0;   /* asked again, with the same histories */
    }
    {
        /* The log is told what of the entry this save already holds: the entry as it was handed over at the last
           page before the save, so the next save continues that same entry (append_event_entry). */
        int k, disk = 0;
        for (k = 0; k < cg.display_count && k < CG_MAX_DISPLAYS; ++k) {
            if (cg.sent_len[k] > disk) {
                disk = cg.sent_len[k];
            }
        }
        if (cg.entry_head > 0) {
            cg_log_send(game, disk, 0);
        }
    }
    if (!ce_armed && !ce_asked) {
        /* The display due at the quit, again: the save's timer is due for the first one; every later one is made
           due now (its notice may have been armed after the save). */
        if (cg_arm(game, 0) && cg.phase != CG_QUEUED) {
#ifndef VVFP_TEST
            if (!GAMES[game].island_pending()) {
                (void)GAMES[game].arm();
            }
#endif
        }
    }
}

/* The tick's write (story_queue.inc sq_sync): the run's file kept what the run is, deleted when it is over. */
static void cg_flush_file(int game, int slot, const unsigned int *roster) {
    if (cg.game != game || cg.slot != slot) {
        return;
    }
    if (cg.phase == CG_DONE) {
        /* Over: the file goes once a save holds every page's effects. */
        unsigned __int64 saved = 0, last = 0;
        int k;
        for (k = 0; k < cg.display_count; ++k) {
            if (cg.applied_when[k] > last) {
                last = cg.applied_when[k];
            }
        }
        if (sq_save_time(game, slot, &saved) && saved >= last) {
            cg.phase = CG_IDLE;
            cg_dirty = 1;
        }
    }
    if (!cg_dirty) {
        return;
    }
    cg_dirty = 0;
    if (cg.phase == CG_IDLE) {
        cg_file_remove(game, slot);
        return;
    }
    memset(&cg_head, 0, sizeof cg_head);
    cg_head.magic = CG_FILE_MAGIC;
    cg_head.version = CG_FILE_VERSION;
    cg_head.game = (unsigned int)game;
    cg_head.slot = (unsigned int)slot;
    cg_head.state_bytes = sizeof(cg_state);
    cg_head.graph_bytes = cg_bytes_size;
    memcpy(cg_head.roster, roster, sizeof cg_head.roster);
    if (!cg_file_write(game, slot)) {
        cg_dirty = 1;
    }
}

/* Start Over or a deleted tribe in `slot`: the run was that village's. */
static void cg_village_reset(int game, int slot) {
    if (game >= 1 && game <= 5 && slot >= 1 && slot <= 5) {
        cg_file_remove(game, slot);
    }
    if (cg.game == game && cg.slot == slot) {
        memset(&cg, 0, sizeof cg);
        cg_display_armed = 0;
        cg_dirty = 0;
    }
}

/* ---- The library (the in-game "From the library..." picker) ----------------------------------------------- */

#define CG_LIBRARY_MAX 64
enum { IDD_CE_LIBRARY = 312, IDC_LB_LIST = 3801, IDC_LB_NOTE = 3802 };

static struct {
    int game;
    int count;
    int chosen;
    char path[CG_LIBRARY_MAX][MAX_PATH];
    char label[CG_LIBRARY_MAX][CE_TITLE_BYTES + 80];
    char problems[1600];
} cg_lib;

static cg_graph cg_lib_graph;
static unsigned char cg_lib_bytes[CG_MAX_FILE];

static int cg_read_whole(const char *path, unsigned char *buf, unsigned int cap, unsigned int *size) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0, high = 0, length;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    length = GetFileSize(h, &high);
    ok = high == 0 && length != INVALID_FILE_SIZE && length <= cap && ReadFile(h, buf, length, &got, NULL) && got == length;
    CloseHandle(h);
    *size = got;
    return ok;
}

/* "<save folder>\Virtual Villagers Fun Patcher\Custom Island Events" (src/vv_cie_graph.py LIBRARY_FOLDER). */
static int cg_library_folder(char *out) {
    if (!vv_save_folder(out, 160)) {
        return 0;
    }
    lstrcatA(out, "\\Virtual Villagers Fun Patcher\\Custom Island Events");
    return 1;
}

static void cg_library_note(const char *file, const char *why) {
    char line[MAX_PATH + 200];
    wsprintfA(line, "%s: %s\r\n", file, why);
    if (lstrlenA(cg_lib.problems) + lstrlenA(line) < (int)sizeof cg_lib.problems) {
        lstrcatA(cg_lib.problems, line);
    }
}

/* Every .cieg of the library made for `game`, with its .json beside it and no older than it (the patcher writes
   both at each save), read and checked; the others are named with the reason. */
static void cg_library_scan(int game) {
    char folder[MAX_PATH], pattern[MAX_PATH], path[MAX_PATH], json[MAX_PATH];
    WIN32_FIND_DATAA found;
    WIN32_FILE_ATTRIBUTE_DATA info;
    HANDLE find;
    memset(&cg_lib, 0, sizeof cg_lib);
    cg_lib.game = game;
    cg_lib.chosen = -1;
    if (!cg_library_folder(folder)) {
        return;
    }
    wsprintfA(pattern, "%s\\*.cieg", folder);
    find = FindFirstFileA(pattern, &found);
    if (find == INVALID_HANDLE_VALUE) {
        return;
    }
    do {
        unsigned int size = 0;
        int n;
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            continue;
        }
        if (lstrlenA(folder) + lstrlenA(found.cFileName) + 8 >= MAX_PATH) {
            continue;
        }
        wsprintfA(path, "%s\\%s", folder, found.cFileName);
        lstrcpyA(json, path);
        n = lstrlenA(json);
        lstrcpyA(json + n - 5, ".json");
        if (!GetFileAttributesExA(json, GetFileExInfoStandard, &info)) {
            cg_library_note(found.cFileName, "its .json is missing: save it again in the patcher");
            continue;
        }
        if (CompareFileTime(&info.ftLastWriteTime, &found.ftLastWriteTime) > 0) {
            cg_library_note(found.cFileName, "its .json is newer: save it again in the patcher");
            continue;
        }
        if (!cg_read_whole(path, cg_lib_bytes, sizeof cg_lib_bytes, &size) || !cg_load(&cg_lib_graph, cg_lib_bytes, size)) {
            cg_library_note(found.cFileName, cg_why[0] != '\0' ? cg_why : "it cannot be read");
            cg_why[0] = '\0';
            continue;
        }
        if (!(cg_lib_graph.games & (1u << (game - 1)))) {
            continue;                  /* made for other games */
        }
        if (cg_lib.count < CG_LIBRARY_MAX) {
            lstrcpyA(cg_lib.path[cg_lib.count], path);
            wsprintfA(cg_lib.label[cg_lib.count], "%s   (%s)", cg_s(&cg_lib_graph, (unsigned int)cg_lib_graph.title),
                      found.cFileName);
            ++cg_lib.count;
        }
    } while (FindNextFileA(find, &found));
    FindClose(find);
}

static INT_PTR CALLBACK cg_library_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    INT_PTR handled;
    if (vk_dialog_hook(window, message, wparam, lparam, &handled)) {
        return handled;
    }
    if (message == WM_INITDIALOG) {
        int i;
        cg_library_scan((int)lparam);
        for (i = 0; i < cg_lib.count; ++i) {
            SendDlgItemMessageA(window, IDC_LB_LIST, LB_ADDSTRING, 0, (LPARAM)cg_lib.label[i]);
        }
        if (cg_lib.count > 0) {
            SendDlgItemMessageA(window, IDC_LB_LIST, LB_SETCURSEL, 0, 0);
        }
        if (cg_lib.problems[0] != '\0') {
            char note[sizeof cg_lib.problems + 80];
            wsprintfA(note, "Not offered:\r\n%s", cg_lib.problems);
            SetDlgItemTextA(window, IDC_LB_NOTE, note);
        } else if (cg_lib.count == 0) {
            SetDlgItemTextA(window, IDC_LB_NOTE,
                            "No event for this game is in the library yet. Make one in the patcher's Custom Island "
                            "Event Library and save it; it appears here.");
        }
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        if (id == IDOK || (id == IDC_LB_LIST && HIWORD(wparam) == LBN_DBLCLK)) {
            int sel = (int)SendDlgItemMessageA(window, IDC_LB_LIST, LB_GETCURSEL, 0, 0);
            if (sel < 0 || sel >= cg_lib.count) {
                MessageBoxA(window, "Choose an event in the list first.", "Custom Island Events",
                            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
                return TRUE;
            }
            cg_lib.chosen = sel;
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* The event picked in the library, bought (story_custom_island_event): read and checked again, refused with the
   reason, confirmed (with the warning a risky role needs), and queued.  1 when it is on its way. */
static int cg_library_purchase(int game, HWND owner) {
    char prompt[600];
    const char *refusal;
    const char *risk;
    unsigned int planned = 0;
    unsigned int size = 0;
    int displaces;
    if (cg_lib.game != game || cg_lib.chosen < 0 || cg_lib.chosen >= cg_lib.count) {
        return 0;
    }
    if (!cg_read_whole(cg_lib.path[cg_lib.chosen], cg_bytes, sizeof cg_bytes, &size)
        || !cg_load(&cg_g, cg_bytes, size)) {
        wsprintfA(prompt, "That event can not be used: %s. Nothing has been queued.", cg_why);
        ui_message(owner, prompt);
        cg_bytes_size = 0;
        return 0;
    }
    cg_bytes_size = size;
    refusal = cg_refusal(game, &planned);
    if (refusal != NULL) {
        ui_message(owner, refusal);
        return 0;
    }
    risk = cg_risk(game);
    if (risk != NULL && !ui_risk(owner, risk)) {
        return 0;
    }
    wsprintfA(prompt, vvfp_tr("vvfp.story/story_custom_ui.story_custom_island_event.s3",
                              "Do you want to buy Custom Island Event for %s tech points?\r\nPress OK to confirm, or Cancel.",
                              400), story_price_text(game));
    if (MessageBoxA(owner, prompt, "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND)
        != IDOK) {
        return 0;
    }
    refusal = cg_refusal(game, &planned);          /* the village may have moved on while the boxes were open */
    if (refusal == NULL && ce_purchase_locked(game, &displaces)) {
        refusal = "Your last custom island event is still on its way.";
    }
    if (refusal != NULL || !cg_queue(game, planned, 1)) {
        ui_message(owner, refusal != NULL ? refusal
                                          : "The event can not happen right now. No tech points have been deducted.");
        return 0;
    }
    wsprintfA(prompt, "\"%s\" is on its way.", cg.title);
    ui_message(owner, prompt);
    return 1;
}

#ifdef VVFP_TEST
/* ---- Test build only --------------------------------------------------------------------------------------- */

/* Queue the .cieg `data` (`size` bytes) in `game` as the library's purchase does, without any dialog: NULL when
   queued, else the refusal.  `due` 1 makes the island event due (ce_arm_with), 0 only arms it. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphQueue(int game, const unsigned char *data,
                                                                     unsigned int size, int due) {
    unsigned int planned = 0;
    const char *refusal;
    if (size > CG_MAX_FILE) {
        return "too large";
    }
    install_state[game] = 1;
    memcpy(cg_bytes, data, size);
    cg_bytes_size = size;
    if (!cg_load(&cg_g, cg_bytes, size)) {
        return cg_why;
    }
    refusal = cg_refusal(game, &planned);
    if (refusal != NULL) {
        return refusal;
    }
    /* due 0: armed without making the island event due (the engine tests drive the entry points). */
    return cg_queue(game, planned, due) ? NULL : "not armed";
}

/* Read `data` as a .cieg: NULL when it passes, else why not. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphCheck(const unsigned char *data, unsigned int size) {
    static cg_graph g;
    static unsigned char copy[CG_MAX_FILE];
    if (size > CG_MAX_FILE) {
        return "too large";
    }
    memcpy(copy, data, size);
    return cg_load(&g, copy, size) ? NULL : cg_why;
}

/* The nodes (indexes) a draw picks whenever one of them can be drawn; the patches on (-1 as seen) and the scale
   mode (-1 as its companion says). */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphForce(const int *nodes, int count, int patches, int scale) {
    int i;
    test_graph_forced = count < 0 ? 0 : (count > 64 ? 64 : count);
    for (i = 0; i < test_graph_forced; ++i) {
        test_graph_force[i] = (short)nodes[i];
    }
    test_graph_patches = patches;
    test_graph_scale = scale;
}

/* The run: out[0] phase, [1] display_next, [2] display_count, [3] display armed, [4] choice, [5] bound roles,
   [6] planned, [7..10] the first four roles' records, [11] pre_pages, [12] walk[0] nodes, [13] walk[1] nodes,
   [14] the told count, [15..18] the first four roles' female flags. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphState(int *out) {
    int i;
    for (i = 0; i < 4; ++i) {
        out[15 + i] = cg.female[i];
    }
    out[0] = cg.phase;
    out[1] = cg.display_next;
    out[2] = cg.display_count;
    out[3] = cg_display_armed;
    out[4] = cg.choice;
    out[5] = (int)cg.bound;
    out[6] = (int)cg.planned;
    for (i = 0; i < 4; ++i) {
        out[7 + i] = (cg.bound & (1u << i)) ? cg.record[i] : -1;
    }
    out[11] = cg.pre_pages;
    out[12] = cg.walk[0].nodes;
    out[13] = cg.walk[1].nodes;
    out[14] = test_graph_told_count;
}

/* History `which`'s nodes into out (at most `cap`); the count. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphPath(int which, int *out, int cap) {
    int i;
    const cg_history *h = &cg.walk[which != 0];
    for (i = 0; i < h->nodes && i < cap; ++i) {
        out[i] = h->node[i];
    }
    return h->nodes;
}

/* The Island Events log stood in for (`on`: each page's lines "  page <k>"); then: the entry as it is now into
   `now`, the last one filed into `filed` (each up to `cap` bytes), and how many were filed. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphLog(int on, char *now, char *filed, int cap) {
    if (on >= 0) {
        test_graph_log = on;
        test_graph_entries = 0;
        test_graph_entry[0] = '\0';
        test_graph_sends = 0;
        test_graph_sent[0] = '\0';
    }
    if (now != NULL && cap > 0) {
        lstrcpynA(now, cg.entry, cap);
    }
    if (filed != NULL && cap > 0) {
        lstrcpynA(filed, test_graph_entry, cap);
    }
    return test_graph_entries;
}

/* The entry as last handed to the log (into `out`, `cap` bytes), with out_info[0] its `disk`, [1] `final`; how
   many times it was handed over. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphSent(char *out, int cap, int *out_info) {
    if (out != NULL && cap > 0) {
        lstrcpynA(out, test_graph_sent, cap);
    }
    if (out_info != NULL) {
        out_info[0] = test_graph_sent_disk;
        out_info[1] = test_graph_sent_final;
    }
    return test_graph_sends;
}

/* Display `k`'s text, or NULL. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphDisplay(int k) {
    return k >= 0 && k < cg.display_count ? cg_display(k) : NULL;
}

/* What "VVFP Cause of Death.dll" / "VVFP Faith Notice.dll" were told, entry `k`: its kind (1 killed, 2 vanished, 3
   a faith conversion; 0 none), its record in *index, its words copied to `words`. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphTold(int k, int *index, char *words) {
    if (k < 0 || k >= test_graph_told_count) {
        return 0;
    }
    *index = test_graph_told[k].index;
    lstrcpyA(words, test_graph_told[k].words);
    return test_graph_told[k].kind;
}

/* Arm the run's next display without making it due (the slot's checks aside); 1 when armed. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphArmNext(int game) {
    if (!cg_active(game) || !cg_wants_display()) {
        return 0;
    }
    return cg_arm(game, 0);
}

/* The run's file as the test build keeps it: copied to `out` (up to `size` bytes); its size. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphFile(void *out, int size) {
    if (out != NULL && size > 0) {
        memcpy(out, cg_test_file, (unsigned int)size < cg_test_size ? (unsigned int)size : cg_test_size);
    }
    return (int)cg_test_size;
}

/* A new process: the run's file from an earlier one (size 0 = none), the run in memory forgotten, the told list
   emptied. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphSession(const void *file, int size) {
    cg_test_size = 0;
    if (file != NULL && size > 0 && (unsigned int)size <= sizeof cg_test_file) {
        memcpy(cg_test_file, file, (unsigned int)size);
        cg_test_size = (unsigned int)size;
    }
    memset(&cg, 0, sizeof cg);
    cg_display_armed = 0;
    cg_dirty = 0;
    test_graph_told_count = 0;
}
#endif
