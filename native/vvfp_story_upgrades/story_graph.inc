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
   exactly as before.

   FORMAT VERSION 6 (the Isola Grand Event Collection, docs/event-collection/cie-v6-binary.md is the contract):
     * pools of text (`{A}`, `{A.2}`, game words `{@chief}`, inline picks compiled to `{_iN}`): each instance drawn
       once a run in the walk -- per node its effects' rolls, then its text's (and a question's labels') instances
       left to right, depth first, then the child draw -- and kept in the run, so pages and a resume show the same
       words; the pages are laid out with the drawn words (names at their longest, as before);
     * alias roles (drawn among their bound members at the run's start), role requirements (max age, skill, the
       special villager, the highest skill) cast STRICT (the rare roll, Pick Island Event) or PREFER (bought: a
       requirement nobody meets is dropped, never the purchase), and the protected filter: a role that can be harmed
       never takes a nursing parent, the Golden Child, the Tribal Chief or New Believers' story villagers;
     * the hard harm guard: a child whose target harms a protected-filtered role carries a `harmable` guard, checked
       at the walk, so a villager who became protected after the cast is never harmed (that branch is not taken);
     * up to seven answers on ONE page, a choice shown only when its `if` holds (the buttons close up: the run keeps
       each question's button-to-choice map), labels up to 95 bytes;
     * new effects: celebrate (each game's own "Celebrating"), action (an action by its words), mood (good: the
       celebration; bad: "Shaking head"), health_change (clamped 1..100, never kills), skill_set and damage (one
       finished structure loses a share of its building work, native/shared/structure_damage.h);
     * A New Home and The Lost Children draw ; ( ) & % only with the Unicode Text companion: without it they become
       , - - "and" " percent" (cg_glyph_fallback).
   The run's file is version 4 (the picks, the aliases, the maps, answers five to seven); a version 3 or 2 file is
   read with them empty. */

#include "../shared/structure_damage.h"   /* the "damage" effect: The Rumblings' structures */

#define CG_HEADER_BYTES 80u
#define CG_HEADER_V6 96u
#define CG_MAX_POOLS 1000
#define CG_MAX_ITEMS 8000
#define CG_MAX_PICKS 256                /* pool instances a run holds */
#define CG_SEG_PICKS 64                 /* ... an answer's segment holds */
#define CG_MAX_INSTANCE 8               /* {A.1} .. {A.8} */
#define CG_POOL_DEPTH 4                 /* a pool's item may hold another pool's token, this deep at most */
#define CG_LABEL_V6 96                  /* a version 6 label, NUL included (95 bytes) */
#define CG_V4_ANSWERS 4                 /* the answers a run file version 3 kept */
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
#define CG_MAX_QUESTIONS 16             /* questions on one history (src/vv_cie_graph.py MAX_QUESTIONS_PER_RUN) */
#define CG_MAX_ANSWERS 7                /* a question's answers: version 6 two to seven, 4 and 5 two to four, before
                                           exactly two */

/* The text lines a question keeps for its answers past two (src/vv_cie_graph.py answer_room): 1.5 button heights
   (3 lines of 20 px) each up to four answers; from five, 1.25 heights apart (vvfp_multi_answer.h ma_step), the
   first answer's height above the game's own first in lines, rounded up. */
static const int CG_ANSWER_LINES[CG_MAX_ANSWERS + 1] = { 0, 0, 0, 3, 6, 7, 10, 12 };

enum { CGD_PAGE = 0, CGD_RESULT = 1, CGD_QUESTION = 2 };

enum { CG_POPUP = 0, CG_QUESTION = 1, CG_BRANCH = 2 };
enum { CGE_FOOD = 1, CGE_TECH = 2, CGE_PAY = 3, CGE_KILL = 4, CGE_VANISH = 5, CGE_STATUS = 6, CGE_HEALTH = 7,
       CGE_PREF = 8, CGE_SKILL = 9, CGE_SICK = 10,
       /* version 6 */
       CGE_CELEBRATE = 11, CGE_ACTION = 12, CGE_MOOD = 13, CGE_HEALTH_CHANGE = 14, CGE_SKILL_SET = 15,
       CGE_DAMAGE = 16 };
enum { CGC_VISITED = 1, CGC_ROLE = 2, CGC_GAME = 3, CGC_PATCH = 4, CGC_NOT = 5, CGC_ALL = 6, CGC_ANY = 7,
       CGC_PUZZLE = 8,                /* version 3: a = the puzzle's name, b = its game (the requirement) */
       /* version 6: the runtime facts */
       CGC_HARMABLE = 9, CGC_SPECIAL_PRESENT = 10, CGC_MIN_POPULATION = 11, CGC_MIN_CHILDREN = 12 };
enum { CG_ROLE_VILLAGER = 0, CG_ROLE_STRANGER = 1, CG_ROLE_ALIAS = 2,
       CG_ROLE_OTHER = 3 };            /* G2: the member of a two-member alias that the alias did not draw */
#define CG_POOL_TRIBE (-2)            /* G5: {@tribe}, built in (no pool): the tribe's name at run time */
#define CG_POOL_TRIBE_CAP (-3)        /* {@Tribe} */
/* The origin of a queued run (story_collection.inc, Pick Island Event, the library) and its casting. */
#define CG_ORIGIN_PURCHASE 0
#define CG_ORIGIN_PICK 1
#define CG_ORIGIN_NATURAL 2
#define CG_CAST_STRICT 0              /* every requirement must hold (the rare roll, Pick Island Event) */
#define CG_CAST_PREFER 1              /* a requirement nobody meets is dropped (bought through the library) */
#define CG_ROLE_ALIAS_ALL 0xFFu       /* an effect's role byte: every living, listed villager (celebrate) */
/* CG_DONE: every page shown, the file kept until a save holds the last page's effects (a crash before it must
   neither lose nor repeat them). */
enum { CG_IDLE = 0, CG_QUEUED = 1, CG_PRE = 2, CG_ASKED = 3, CG_CHAIN = 4, CG_DONE = 5 };
enum { CG_ROLE_OPTIONAL = 1, CG_ROLE_NURSING = 2, CG_ROLE_SPECIAL = 4, CG_ROLE_BELIEVERS = 8,
       CG_ROLE_HARM = 16, CG_ROLE_PROTECTED = 32 };
#define CG_STRANGER_NAMED 1u          /* a stranger's flags: named (cie-v6-binary.md 16) */
#include "story_villager_names.h"     /* each game's first-name lists (scripts/build_cie_villager_names.py) */

/* The pronouns are CG_PH_HE .. CG_PH_MAN and CG_PH_HIMSELF .. CG_PH_SON (cg_pronoun). */
enum { CG_PH_NAME = 0, CG_PH_HE, CG_PH_HIS, CG_PH_HIM, CG_PH_MAN, CG_PH_AWARD, CG_PH_UNIT,
       CG_PH_HIMSELF, CG_PH_WOMAN_MAN, CG_PH_BOY, CG_PH_SON };
enum { CG_EXPAND_AWARD = 0, CG_EXPAND_WORST = 1, CG_EXPAND_REAL = 2 };

/* ---- The .cieg (src/vv_cie_graph.py THE BINARY .cieg) ----------------------------------------------------- */

typedef struct {
    const unsigned char *d;
    unsigned int size;
    unsigned int games;
    int version;                      /* 1; 2: a question may be any node, text may hold "; 3: award ranges,
                                         the puzzle requirement, age gaps between roles */
    int req_cond;                     /* version 3: the requirement's condition (puzzles), CG_NONE */
    int title, start, min_eligible;
    int n_role, n_node, n_child, n_effect, n_cond, n_variant, n_string, n_patch;
    unsigned int o_role, o_node, o_child, o_effect, o_cond, o_variant, o_patch, o_string, o_blob, blob_size;
    /* Version 6: the header's and a role's size, the pools and their items, the flags (bit 0 the guard). */
    unsigned int header_bytes, role_bytes;
    int n_pool, n_item, flags;
    unsigned int o_pool, o_item;
} cg_graph;

static unsigned int cg_u16(const unsigned char *p) {
    return (unsigned int)p[0] | (unsigned int)p[1] << 8;
}

static unsigned int cg_u32(const unsigned char *p) {
    return (unsigned int)p[0] | (unsigned int)p[1] << 8 | (unsigned int)p[2] << 16 | (unsigned int)p[3] << 24;
}

static const unsigned char *cg_role_at(const cg_graph *g, int i) {
    return g->d + g->o_role + g->role_bytes * (unsigned int)i;
}
static const unsigned char *cg_pool_at(const cg_graph *g, int i) { return g->d + g->o_pool + 12u * (unsigned int)i; }
static const unsigned char *cg_item_at(const cg_graph *g, int i) { return g->d + g->o_item + 8u * (unsigned int)i; }
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
    return at >= g->header_bytes && at <= g->size && (unsigned int)count <= (g->size - at) / size;
}

static int cg_str_ok(const cg_graph *g, unsigned int i, int may_be_none) {
    return i == CG_NONE ? may_be_none : (int)i < g->n_string;
}

/* A version 5 food / tech effect's per-game amounts, "<game>:<min>-<max>;..." (src/vv_cie_graph.py per_game_text):
   1 with game `game`'s into *lo / *hi, 0 when it is not listed, -1 when the text is not that shape. */
static int cg_num(const char **p, int *out) {
    int neg = 0, v = 0, digits = 0;
    if (**p == '-') {
        neg = 1;
        ++*p;
    }
    while (**p >= '0' && **p <= '9' && digits < 9) {
        v = v * 10 + (**p - '0');
        ++*p;
        ++digits;
    }
    *out = neg ? -v : v;
    return digits > 0;
}

static int cg_per_game(const char *text, int game, int *lo, int *hi) {
    const char *p = text;
    int found = 0, last = 0;
    while (*p != '\0') {
        int g, a, b;
        if (*p < '1' || *p > '5' || p[1] != ':') {
            return -1;
        }
        g = *p - '0';
        p += 2;
        if (g <= last || !cg_num(&p, &a) || *p != '-') {
            return -1;
        }
        ++p;
        if (!cg_num(&p, &b) || (*p != ';' && *p != '\0')) {
            return -1;
        }
        if (*p == ';') {
            ++p;
            if (*p == '\0') {
                return -1;
            }
        }
        last = g;
        if (g == game) {
            *lo = a;
            *hi = b;
            found = 1;
        }
    }
    return found;
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

/* Version 6's role shorthand "(Gardener1)": the role whose id is `id` ignoring case, -1 none. */
static int cg_role_by_id_ci(const cg_graph *g, const char *id, int length) {
    int r, k;
    for (r = 0; r < g->n_role; ++r) {
        const char *s = cg_s(g, cg_u16(cg_role_at(g, r) + 4));
        if (lstrlenA(s) != length) {
            continue;
        }
        for (k = 0; k < length; ++k) {
            char x = s[k], y = id[k];
            if (x >= 'A' && x <= 'Z') {
                x = (char)(x - 'A' + 'a');
            }
            if (y >= 'A' && y <= 'Z') {
                y = (char)(y - 'A' + 'a');
            }
            if (x != y) {
                break;
            }
        }
        if (k == length) {
            return r;
        }
    }
    return -1;
}

/* The pool named `name` (`length` bytes), -1 none. */
static int cg_pool_by_name(const cg_graph *g, const char *name, int length) {
    int i;
    for (i = 0; i < g->n_pool; ++i) {
        const char *s = cg_s(g, cg_u16(cg_pool_at(g, i)));
        if (lstrlenA(s) == length && memcmp(s, name, (size_t)length) == 0) {
            return i;
        }
    }
    return -1;
}

/* A pool token at `s` ('{'): "{NAME}" or "{NAME.k}", k 1..8 ("{NAME}" is instance 1).  Its bytes (the braces
   included) with the pool and the instance, or 0 when it is not one. */
static int cg_parse_brace(const cg_graph *g, const char *s, int *pool, int *instance) {
    const char *e = s + 1;
    int n, k = 1;
    while ((*e >= 'A' && *e <= 'Z') || (*e >= 'a' && *e <= 'z') || (*e >= '0' && *e <= '9') || *e == '_'
           || (*e == '@' && e == s + 1)) {
        ++e;
    }
    n = (int)(e - s - 1);
    if (n < 1 || n > 33) {
        return 0;
    }
    if (*e == '.') {
        if (e[1] < '1' || e[1] > '0' + CG_MAX_INSTANCE) {
            return 0;
        }
        k = e[1] - '0';
        e += 2;
    }
    if (*e != '}') {
        return 0;
    }
    *pool = cg_pool_by_name(g, s + 1, n);
    *instance = k;
    if (*pool < 0 && n == 6 && k == 1 && e == s + 7) {
        if (memcmp(s + 1, "@tribe", 6) == 0) {
            *pool = CG_POOL_TRIBE;     /* G5: built in, filled at run time */
        } else if (memcmp(s + 1, "@Tribe", 6) == 0) {
            *pool = CG_POOL_TRIBE_CAP;
        }
    }
    return *pool >= 0 || *pool == CG_POOL_TRIBE || *pool == CG_POOL_TRIBE_CAP ? (int)(e - s) + 1 : 0;
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
    int caps;                         /* version 6: written ALL CAPS ("(NAME1)", "(HE/SHE)"): the word in capitals */
    int hint;                         /* version 6 labels: a name's pronoun hint, (ACCUSED|HE/SHE): its CG_PH_*;
                                         -1 none (the fallback is him/her, cie-v6-binary.md 15) */
} cg_ph;

static int cg_parse_ph_in(const cg_graph *g, const char *tok, int n, cg_ph *ph);

/* A placeholder's inside, a label name's pronoun hint included ("ACCUSED|HE/SHE"). */
static int cg_parse_ph(const cg_graph *g, const char *tok, int n, cg_ph *ph) {
    static const char *const HINTS[4] = { "he/she", "him/her", "his/her", "himself/herself" };
    static const int HINT_PH[4] = { CG_PH_HE, CG_PH_HIM, CG_PH_HIS, CG_PH_HIMSELF };
    int bar, k;
    ph->hint = -1;
    for (bar = 0; bar < n && tok[bar] != '|'; ++bar) {
    }
    if (bar == n) {
        return cg_parse_ph_in(g, tok, n, ph);
    }
    if (g->version < 6 || !cg_parse_ph_in(g, tok, bar, ph) || ph->what != CG_PH_NAME) {
        return 0;
    }
    for (k = 0; k < 4; ++k) {
        if (cg_word_is(tok + bar + 1, n - bar - 1, HINTS[k])) {
            ph->hint = HINT_PH[k];
            return 1;
        }
    }
    return 0;
}

/* A placeholder's inside ("friend.His/Her"), src/vv_cie_graph.py parse_placeholder.  0 when it is not one. */
static int cg_parse_ph_in(const cg_graph *g, const char *tok, int n, cg_ph *ph) {
    static const char *const WORDS[] = { "name", "he/she", "his/her", "him/her", "man/woman", "award", "award_unit",
                                         "himself/herself", "woman/man", "boy/girl", "son/daughter" };
    int words = g->version >= 6 ? 11 : 7;
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
    {
        /* Version 6: ALL CAPS -- at least two letters, none lower case (docs/event-collection/cie-v6-binary.md 5). */
        int letters = 0, lower = 0;
        for (i = 0; i < n; ++i) {
            letters += (tok[i] >= 'A' && tok[i] <= 'Z') || (tok[i] >= 'a' && tok[i] <= 'z');
            lower += tok[i] >= 'a' && tok[i] <= 'z';
        }
        ph->caps = g->version >= 6 && letters >= 2 && lower == 0;
    }
    if (dot > 0) {
        role = ph->caps ? cg_role_by_id_ci(g, tok, dot) : cg_role_by_id(g, tok, dot);
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
        for (i = 0; i < words && !cg_word_is(w, wn, WORDS[i]); ++i) {
        }
        if (i == words) {
            /* Version 6: "(gardener1)" / "(Gardener1)", that role's name (a keyword always wins). */
            if (g->version < 6 || dot >= 0) {
                return 0;
            }
            role = cg_role_by_id_ci(g, w, wn);
            if (role < 0) {
                return 0;
            }
            i = CG_PH_NAME;
        }
        ph->what = i;
        if (i == CG_PH_AWARD || i == CG_PH_UNIT) {
            if (dot > 0) {
                return 0;
            }
            ph->role = -1;
            return 1;
        }
        if (role < 0) {
            role = cg_role_by_id(g, "subject", 7);
            if (role < 0) {
                if (g->n_role < 1) {
                    return 0;          /* version 6: a graph with no roles has no one to name */
                }
                role = 0;
            }
        }
    }
    if (ph->what == CG_PH_NAME && cg_role_at(g, role)[0] == CG_ROLE_STRANGER
        && !(g->version >= 6 && (cg_role_at(g, role)[1] & CG_STRANGER_NAMED))) {
        return 0;                     /* a stranger has no name (version 6: unless named, cie-v6-binary.md 16) */
    }
    ph->role = role;
    return 1;
}

/* Every character allowed (ce_text_char_ok; line breaks when `lines`), parentheses only around placeholders (no
   award in a label: `label`).  Version 6: also ; / & %, the escaped \( \), and pool tokens ({@word} only in a
   label). */
static int cg_text_ok(const cg_graph *g, const char *s, int lines, int label) {
    for (; *s != '\0'; ++s) {
        if (g->version >= 6) {
            if (*s == '\\') {
                if (s[1] != '(' && s[1] != ')') {
                    return 0;
                }
                ++s;
                continue;
            }
            if (*s == '{') {
                int pool, instance, n = cg_parse_brace(g, s, &pool, &instance);
                if (n == 0 || (label && pool >= 0 && cg_s(g, cg_u16(cg_pool_at(g, pool)))[0] != '@')) {
                    return 0;
                }
                s += n - 1;
                continue;
            }
            if (*s == ';' || *s == '/' || *s == '&' || *s == '%') {
                continue;
            }
        }
        if (*s == '(') {
            const char *e = s + 1;
            cg_ph ph;
            while (*e != '\0' && *e != ')' && *e != '(' && *e != '\n') {
                ++e;
            }
            if (*e != ')' || !cg_parse_ph(g, s + 1, (int)(e - s - 1), &ph) || (label && ph.role < 0)
                || (!label && ph.hint >= 0)) {     /* a pronoun hint only in a label (cie-v6-binary.md 15) */
                return 0;
            }
            s = e;
            continue;
        }
        if (*s == '\n' && lines) {
            continue;
        }
        if (*s == '"' && g->version >= 2) {
            continue;                  /* version 2: every game's font draws it (src/vv_font_glyphs.py) */
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

/* VERSION 6 POOLS.  How many pools deep the tokens of pool `p`'s items go (1: none), -1 when they loop back or go
   deeper than CG_POOL_DEPTH. */
static unsigned char cg_pool_level[CG_MAX_POOLS];   /* 0 not known yet, 0xFF being looked at */

static int cg_pool_chain(const cg_graph *g, int p, int depth) {
    const unsigned char *pool = cg_pool_at(g, p);
    int k, best = 0;
    if (depth > CG_POOL_DEPTH || cg_pool_level[p] == 0xFFu) {
        return -1;
    }
    if (cg_pool_level[p] != 0u) {
        return cg_pool_level[p];
    }
    cg_pool_level[p] = 0xFFu;
    for (k = 0; k < (int)cg_u16(pool + 4); ++k) {
        const char *s = cg_s(g, cg_u16(cg_item_at(g, (int)cg_u16(pool + 2) + k)));
        for (; *s != '\0'; ++s) {
            int q, instance, n, level;
            if (*s == '\\' && s[1] != '\0') {
                ++s;
                continue;
            }
            if (*s != '{') {
                continue;
            }
            n = cg_parse_brace(g, s, &q, &instance);
            if (n == 0 || q == p) {
                return -1;
            }
            if (q < 0) {
                s += n - 1;            /* {@tribe}: no pool */
                continue;
            }
            level = cg_pool_chain(g, q, depth + 1);
            if (level < 0) {
                return -1;
            }
            if (level > best) {
                best = level;
            }
            s += n - 1;
        }
    }
    if (best + 1 > CG_POOL_DEPTH) {
        return -1;
    }
    cg_pool_level[p] = (unsigned char)(best + 1);
    return best + 1;
}

/* Every pool and item inside its tables, every item's text one the game can show, no pool reaching itself. */
static int cg_pools_ok(const cg_graph *g) {
    int i;
    if ((g->flags & ~1) != 0) {
        return cg_bad("its flags are not ones this game can read");
    }
    for (i = 0; i < g->n_pool; ++i) {
        const unsigned char *p = cg_pool_at(g, i);
        unsigned int first = cg_u16(p + 2), count = cg_u16(p + 4);
        if (!cg_str_ok(g, cg_u16(p), 0) || cg_s(g, cg_u16(p))[0] == '\0' || count < 1u
            || first + count > (unsigned int)g->n_item || p[6] > 1u || p[7] != 0u
            || !cg_str_ok(g, cg_u16(p + 8), 1) || cg_u16(p + 10) != 0u) {
            return cg_bad("a pool is not one this game can read");
        }
    }
    for (i = 0; i < g->n_item; ++i) {
        const unsigned char *it = cg_item_at(g, i);
        unsigned int cond = cg_u16(it + 4);
        if (!cg_str_ok(g, cg_u16(it), 0) || cg_u16(it + 2) < 1u || cg_u16(it + 2) > 10000u
            || (cond != CG_NONE && (int)cond >= g->n_cond) || cg_u16(it + 6) != 0u
            || !cg_text_ok(g, cg_s(g, cg_u16(it)), 1, 0) || lstrlenA(cg_s(g, cg_u16(it))) > CG_TEXT_MAX) {
            return cg_bad("a pool's text is not one the game can show");
        }
    }
    memset(cg_pool_level, 0, sizeof cg_pool_level);
    for (i = 0; i < g->n_pool; ++i) {
        if (cg_pool_chain(g, i, 1) < 0) {
            return cg_bad("a pool's text goes round in a circle or too deep");
        }
    }
    return 1;
}

/* Read `data` (`size` bytes) as a .cieg into `g` (which points into `data`): 1, or 0 with the reason in cg_why. */
/* A title the game can show (the event's, or -- version 6 -- a node's popup title, docs/event-collection/
   cie-v6-binary.md 14): ce_text_char_ok's characters (version 6: and quotes, G6), one line, under CE_TITLE_BYTES. */
static int cg_title_ok(const cg_graph *g, const char *title) {
    const char *t;
    for (t = title; *t != '\0'; ++t) {
        if (!ce_text_char_ok(*t) && !(*t == '"' && g->version >= 6)) {
            return 0;
        }
    }
    return title[0] != '\0' && lstrlenA(title) < CE_TITLE_BYTES;
}

static int cg_load(cg_graph *g, const unsigned char *data, unsigned int size) {
    const unsigned char *h = data;
    int i, k;
    memset(g, 0, sizeof *g);
    g->d = data;
    g->size = size;
    if (size < CG_HEADER_BYTES || memcmp(h, "CIEG", 4) != 0 || cg_u16(h + 4) < 1u || cg_u16(h + 4) > 6u
        || cg_u16(h + 6) != (cg_u16(h + 4) >= 6u ? CG_HEADER_V6 : CG_HEADER_BYTES) || size < cg_u16(h + 6)
        || cg_u32(h + 8) != size) {
        return cg_bad("it is not a version 1, 2, 3, 4, 5 or 6 .cieg file");
    }
    g->version = (int)cg_u16(h + 4);
    g->header_bytes = cg_u16(h + 6);
    g->role_bytes = g->version >= 6 ? 16u : 8u;
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
    g->req_cond = g->version >= 3 ? (int)cg_u16(h + 42) : (int)CG_NONE;
    g->o_role = cg_u32(h + 44);
    g->o_node = cg_u32(h + 48);
    g->o_child = cg_u32(h + 52);
    g->o_effect = cg_u32(h + 56);
    g->o_cond = cg_u32(h + 60);
    g->o_variant = cg_u32(h + 64);
    g->o_patch = cg_u32(h + 68);
    g->o_string = cg_u32(h + 72);
    if (g->version >= 6) {
        g->o_pool = cg_u32(h + 76);
        g->o_item = cg_u32(h + 80);
        g->n_pool = (int)cg_u16(h + 84);
        g->n_item = (int)cg_u16(h + 86);
        g->flags = (int)cg_u16(h + 88);
        if (g->n_pool > CG_MAX_POOLS || g->n_item > CG_MAX_ITEMS || !cg_section(g, g->o_pool, g->n_pool, 12)
            || !cg_section(g, g->o_item, g->n_item, 8) || cg_u32(h + 92) != 0u) {
            return cg_bad("its pools do not fit in the file");
        }
    }
    if (g->games == 0u || (g->games & ~0x1Fu) != 0u || g->n_role < (g->version >= 6 ? 0 : 1) || g->n_role > CG_MAX_ROLES || g->n_node < 1
        || g->n_node > CG_MAX_NODES || g->n_patch > 8 || g->n_child >= 0xFFFF || g->n_effect >= 0xFFFF
        || g->n_cond >= 0xFFFF || g->n_variant >= 0xFFFF || g->n_string >= 0xFFFF
        || !cg_section(g, g->o_role, g->n_role, g->role_bytes) || !cg_section(g, g->o_node, g->n_node, 28)
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
    if (!cg_title_ok(g, cg_s(g, (unsigned int)g->title))) {
        return cg_bad("its title is not one the game can show");
    }
    for (i = 0; i < g->n_patch; ++i) {
        if (!cg_str_ok(g, cg_u16(data + g->o_patch + 2u * (unsigned int)i), 0)) {
            return cg_bad("a patch name is missing");
        }
    }
    for (i = 0; i < g->n_role; ++i) {
        const unsigned char *r = cg_role_at(g, i);
        if (r[0] > (g->version >= 6 ? 3u : 1u) || !cg_str_ok(g, cg_u16(r + 4), 0)
            || (r[0] == 0 && (r[2] > 2u || r[3] > 80u))
            || (r[0] == 1 && (r[2] < 1u || r[2] > 3u))
            || (r[0] == 1 && g->version >= 6 && (r[1] & ~CG_STRANGER_NAMED) != 0u)
            || (i == 0 && ((r[0] != CG_ROLE_VILLAGER && !(g->version >= 6 && r[0] == CG_ROLE_STRANGER))
                           || (r[0] == CG_ROLE_VILLAGER && (r[1] & CG_ROLE_OPTIONAL))))
            ) {
            return cg_bad("a role is not one this game can read");
        }
        if (g->version >= 6) {
            /* Version 6: max age, the special villager, the skill requirement and its pick; an alias's members (other
               villager roles), and nothing else on an alias. */
            unsigned int members = cg_u16(r + 14);
            if ((r[8] != 0 && (r[8] > 120u || r[8] < r[3])) || r[9] > 3u || !cg_str_ok(g, cg_u16(r + 10), 1)
                || r[13] > 1u || r[12] > 100u) {
                return cg_bad("a role's requirement is not one this game can read");
            }
            if (r[0] == CG_ROLE_OTHER) {
                /* G2: exactly one bit, a two-member alias. */
                int al;
                for (al = 0; al < g->n_role && members != (1u << al); ++al) {
                }
                if (al >= g->n_role || (r[1] & ~CG_ROLE_HARM) != 0 || r[2] != 0 || r[3] != 0 || r[6] != 0
                    || r[8] != 0 || r[9] != 0 || cg_u16(r + 10) != CG_NONE
                    || cg_role_at(g, al)[0] != CG_ROLE_ALIAS) {
                    return cg_bad("an other role is not one this game can read");
                }
                {
                    unsigned int m = cg_u16(cg_role_at(g, al) + 14);
                    int bits = 0;
                    for (; m != 0u; m &= m - 1u) {
                        ++bits;
                    }
                    if (bits != 2) {
                        return cg_bad("an other role follows an alias that does not have two members");
                    }
                }
            } else if (r[0] == CG_ROLE_ALIAS) {
                if (members == 0u || (members >> g->n_role) != 0u || (members & (1u << i))
                    || (r[1] & ~CG_ROLE_HARM) != 0 || r[2] != 0
                    || r[3] != 0 || r[6] != 0 || r[8] != 0 || r[9] != 0 || cg_u16(r + 10) != CG_NONE) {
                    return cg_bad("an alias role is not one this game can read");
                }
                for (k = 0; k < g->n_role; ++k) {
                    if ((members & (1u << k)) && cg_role_at(g, k)[0] != CG_ROLE_VILLAGER) {
                        return cg_bad("an alias role names a role that is not a villager");
                    }
                }
            } else if (members != 0u) {
                return cg_bad("a role is not one this game can read");
            }
        }
        if (r[6] != 0 || r[7] != 0) {
            /* Version 3: at most r[7] years apart from role r[6] - 1, both villagers. */
            int other = (int)r[6] - 1;
            if (g->version < 3 || other < 0 || other >= g->n_role || other == i || r[0] != 0
                || cg_role_at(g, other)[0] != 0 || r[7] > 80u) {
                return cg_bad("a role's age gap is not one this game can read");
            }
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
        case CGC_PUZZLE:
            ok = g->version >= 3 && cg_str_ok(g, a, 0) && cg_u16(c + 4) >= 1u && cg_u16(c + 4) <= 5u;
            break;
        case CGC_HARMABLE: ok = g->version >= 6 && (int)a < g->n_role; break;
        case CGC_SPECIAL_PRESENT: ok = g->version >= 6 && a >= 1u && a <= 2u; break;
        case CGC_MIN_POPULATION: case CGC_MIN_CHILDREN: ok = g->version >= 6 && a <= 1000u; break;
        default: ok = 0; break;
        }
        if (!ok) {
            return cg_bad("a condition is not one this game can read");
        }
    }
    if (g->version >= 6 && !cg_pools_ok(g)) {
        return 0;
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
        int a = (int)cg_u32(e + 4), b = (int)cg_u32(e + 8), lo, hi;
        unsigned int str = cg_u16(e + 12);
        int villager = (e[0] >= CGE_KILL && e[0] <= CGE_SICK) || (e[0] >= CGE_ACTION && e[0] <= CGE_SKILL_SET)
                       || (e[0] == CGE_CELEBRATE && e[1] != CG_ROLE_ALIAS_ALL);
        int ok = e[0] >= CGE_FOOD && e[0] <= (g->version >= 6 ? CGE_DAMAGE : CGE_SICK);
        if (ok && villager) {
            /* A villager role (version 6: or an alias, whose drawn member the effect goes to). */
            ok = e[1] < (unsigned int)g->n_role
                 && (cg_role_at(g, e[1])[0] == CG_ROLE_VILLAGER
                     || (g->version >= 6 && cg_role_at(g, e[1])[0] >= CG_ROLE_ALIAS));
        }
        if (ok) {
            switch (e[0]) {
            case CGE_FOOD: case CGE_TECH:
                /* b: version 3's range top (0: the amount alone), above the amount, the same side of 0. */
                ok = a != 0 && a <= CE_MAX_AMOUNT && a >= -CE_MAX_AMOUNT
                     && (b == 0 || (g->version >= 3 && b > a && b <= CE_MAX_AMOUNT && (b > 0) == (a > 0)));
                /* Version 5: the string is each game's own amount or range ("1:200-1500;5:50-300"), every one
                   valid; before it a food / tech effect has none. */
                if (ok && str != CG_NONE) {
                    int game;
                    ok = g->version >= 5 && cg_str_ok(g, str, 0) && cg_s(g, str)[0] != '\0';
                    for (game = 1; ok && game <= 5; ++game) {
                        int found = cg_per_game(cg_s(g, str), game, &lo, &hi);
                        ok = found >= 0 && (found == 0 || (lo != 0 && hi >= lo && (lo > 0) == (hi > 0)
                                                           && lo >= -CE_MAX_AMOUNT && hi <= CE_MAX_AMOUNT));
                    }
                }
                break;
            case CGE_KILL: {
                const char *cause = cg_s(g, str);
                ok = str != CG_NONE && cause[0] != '\0' && lstrlenA(cause) < CG_CAUSE_BYTES && ce_text_ok(cause, 0);
                break;
            }
            case CGE_STATUS: ok = a == 1; break;
            case CGE_HEALTH: ok = a >= 1 && a <= 100 && b >= a && b <= 100; break;
            case CGE_SKILL:
                /* Version 6: a loss too (both ends -100..-1). */
                ok = (a >= 1 && a <= 100 && b >= a && b <= 100)
                     || (g->version >= 6 && a >= -100 && b >= a && b <= -1);
                break;
            case CGE_CELEBRATE: ok = a == 0 && b == 0 && str == CG_NONE; break;
            case CGE_ACTION: ok = a == 0 && b == 0 && str != CG_NONE && cg_str_ok(g, str, 0); break;
            case CGE_MOOD: ok = (a == 1 || a == -1) && b == 0 && str == CG_NONE; break;
            case CGE_HEALTH_CHANGE: ok = a >= -100 && b >= a && b <= 100 && str == CG_NONE; break;
            case CGE_SKILL_SET: ok = a >= 0 && a <= 100 && b == 0; break;
            case CGE_DAMAGE:
                ok = e[1] == CG_ROLE_ALIAS_ALL && a >= 1 && b >= a && b <= 100 && str != CG_NONE
                     && cg_str_ok(g, str, 0);
                break;
            default: break;
            }
        }
        if (ok && (e[0] == CGE_PREF || e[0] == CGE_SKILL || e[0] == CGE_SKILL_SET || e[0] == CGE_ACTION
                   || e[0] == CGE_DAMAGE)) {
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
        if (g->version >= 6 && cg_u16(n + 26) != CG_NONE
            && (n[0] == CG_BRANCH || !cg_str_ok(g, cg_u16(n + 26), 0) || !cg_title_ok(g, cg_s(g, cg_u16(n + 26))))) {
            return cg_bad("a node's popup title is not one the game can show");
        }
        if (ccount > 256u) {
            return cg_bad("a node has more than 256 children");
        }
        if (n[0] == CG_QUESTION && ((i != g->start && g->version < 2)
                                    || (g->version < 4 ? ccount != 2u
                                                       : ccount < 2u
                                                         || ccount > (g->version >= 6 ? (unsigned int)CG_MAX_ANSWERS
                                                                                      : (unsigned int)CG_V4_ANSWERS))
                                    || els != CG_NONE || (g->version >= 2 && ecount != 0u))) {
            return cg_bad(g->version < 2 ? "a question is not the event's first popup with two choices"
                                         : g->version < 4 ? "a question does not have two choices, or makes changes"
                                         : g->version < 6 ? "a question does not have two to four choices, or makes "
                                                            "changes"
                                                          : "a question does not have two to seven choices, or makes "
                                                            "changes");
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
                if (!cg_str_ok(g, cg_u16(c + 8), 0) || label[0] == '\0'
                    || lstrlenA(label) >= (g->version >= 6 ? CG_LABEL_V6 : CG_LABEL_BYTES)
                    || !cg_text_ok(g, label, 0, 1)) {
                    return cg_bad("a button label is not one the game can show");
                }
                /* Version 6: a choice shown only when its `if` holds. */
                if (g->version >= 6 && cond != CG_NONE && (int)cond >= g->n_cond) {
                    return cg_bad("a choice's condition is not one this game can read");
                }
            } else if (cg_u16(c + 2) < 1u || cg_u16(c + 2) > 10000u || (cond != CG_NONE && (int)cond >= g->n_cond)
                       || (ce != CG_NONE && (int)ce >= g->n_node)) {
                return cg_bad("a child is not one this game can read");
            }
            if (g->version >= 6 && cg_u16(c + 10) != CG_NONE && (int)cg_u16(c + 10) >= g->n_cond) {
                return cg_bad("a child's guard is not one this game can read");
            }
        }
    }
    if (g->req_cond != (int)CG_NONE
        && (g->req_cond >= g->n_cond || cg_cond_at(g, g->req_cond)[0] != CGC_ALL)) {
        return cg_bad("its requirement is not one this game can read");
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

/* One pool instance drawn (version 6): the pool, the instance (1..8), the item within the pool (CG_NONE: none was
   eligible, the empty text). */
typedef struct {
    unsigned short pool;
    unsigned short instance;
    unsigned short item;
} cg_pick;

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
    /* THE HISTORY SO FAR (version 2: a question may be any node).  `path` is every node the run has reached, each
       question included, with every effect's roll; it grows one segment at a time -- from the start, or from an
       answer, up to the next question (included) or the end.  Each question's two segments are walked when it is
       asked (seg[q][button]: the popup can then be sized for the result either button shows, and a question asked
       again after a restore has the same histories), and the one answered is added to `path`. */
    cg_history path;
    int answers;                       /* questions answered */
    int asking;                        /* the display of the question on screen (CG_ASKED) */
    int choice;                        /* the last button answered, -1 */
    cg_history seg[CG_MAX_QUESTIONS][2];
    unsigned char seg_walked[CG_MAX_QUESTIONS];
    unsigned char answer[CG_MAX_QUESTIONS];
    short q_display[CG_MAX_QUESTIONS]; /* question q's display */
    short q_path[CG_MAX_QUESTIONS];    /* path.nodes / path.fx when it was asked (its own node included) */
    short q_fx[CG_MAX_QUESTIONS];
    int q_entry[CG_MAX_QUESTIONS];     /* the log entry's length before its "Choice:" line */
    int jobs_used;
    int display_count;
    int display_next;                  /* the next display to show: every display before it is shown, and its
                                          effects made */
    int display_used;
    int display_off[CG_MAX_DISPLAYS];
    char displays[CG_DISPLAY_BYTES];   /* each page's words, the names filled in (composed when shown) */
    /* Each display: its kind (CGD_*: a page, a question's result -- the first page after an answer -- or a
       question's own popup, display_node its node), the path's nodes whose effects it makes (jobs[job_first .. +
       job_count]), and -- for a quit -- when they were made and who was gone and who each role was just before it. */
    unsigned char display_kind[CG_MAX_DISPLAYS];
    short display_node[CG_MAX_DISPLAYS];
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
    /* Run file version 3 (format version 4: three or four answers): the third and fourth answers' segments, after
       everything version 2 kept (a version 2 file is read with these empty: its questions have two answers). */
    cg_history seg_more[CG_MAX_QUESTIONS][CG_V4_ANSWERS - 2];
    /* Run file version 4 (format version 6), after everything version 3 kept (a version 3 file is read with these
       empty: no picks, no alias, every choice shown, the cast strict): */
    cg_history seg_v6[CG_MAX_QUESTIONS][CG_MAX_ANSWERS - CG_V4_ANSWERS];   /* answers five to seven */
    int origin;                        /* CG_ORIGIN_* */
    int cast_mode;                     /* CG_CAST_* */
    unsigned int relaxed;              /* the roles cast with their requirements dropped (CG_CAST_PREFER) */
    signed char alias[CG_MAX_ROLES];   /* each alias role's member drawn (a role index), -1 none */
    int aliases_drawn;
    int pick_count;                    /* the path's pool picks */
    cg_pick picks[CG_MAX_PICKS];
    short q_picks[CG_MAX_QUESTIONS];   /* pick_count when question q was asked */
    unsigned char seg_pick_count[CG_MAX_QUESTIONS][CG_MAX_ANSWERS];
    cg_pick seg_picks[CG_MAX_QUESTIONS][CG_MAX_ANSWERS][CG_SEG_PICKS];
    /* Each question's buttons: how many are shown and the choice behind each (a choice whose `if` fails is not). */
    unsigned char q_shown[CG_MAX_QUESTIONS];
    unsigned char q_map[CG_MAX_QUESTIONS][CG_MAX_ANSWERS];
    int start_picks;                   /* the picks drawn at the purchase (a start question's own) */
    /* Each display's popup title (cie-v6-binary.md 14): a node title's string index + 1, 0 = the event's title. */
    unsigned short display_title[CG_MAX_DISPLAYS];
} cg_state;


static cg_state cg;
static cg_graph cg_g;
static char cg_labels[CG_MAX_ANSWERS][CG_LABEL_V6];   /* the asked question's button labels, names filled in */

/* The asked question's label for `button` (ce_choice_label, for a graph's question). */
static const char *cg_label(int button) {
    return button >= 0 && button < CG_MAX_ANSWERS ? cg_labels[button] : "";
}
static unsigned char cg_bytes[CG_MAX_FILE];
static unsigned int cg_bytes_size;

/* The choices of question `node` (two before format version 4, two to four from it, two to seven from 6). */
static int cg_answer_count(int node) {
    int n = node >= 0 && node < cg_g.n_node ? (int)cg_u16(cg_node_at(&cg_g, node) + 14) : 2;
    return n < 2 ? 2 : (n > CG_MAX_ANSWERS ? CG_MAX_ANSWERS : n);
}

/* Question `qi`'s segment for choice `b`, and its picks. */
static cg_history *cg_seg(int qi, int b) {
    return b < 2 ? &cg.seg[qi][b] : b < CG_V4_ANSWERS ? &cg.seg_more[qi][b - 2] : &cg.seg_v6[qi][b - CG_V4_ANSWERS];
}

static int cg_holds_cond(int i, int game, int depth);

/* The choices of question `node` shown now (version 6: a choice whose `if` fails is not), in order, into map[];
   their count. */
static int cg_shown_choices(int node, int game, unsigned char *map) {
    int b, n = 0, count = cg_answer_count(node);
    for (b = 0; b < count; ++b) {
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + b);
        if (cg_g.version < 6 || cg_holds_cond((int)cg_u16(c + 4), game, 0)) {
            map[n++] = (unsigned char)b;
        }
    }
    return n;
}

/* The buttons question `node` shows: its map when it is the question asked (or walked) as question `qi`, else as
   they would be now. */
static int cg_buttons(int node, int qi, unsigned char *map) {
    if (qi >= 0 && qi < CG_MAX_QUESTIONS && cg.seg_walked[qi] && cg.q_shown[qi] >= 2) {
        memcpy(map, cg.q_map[qi], CG_MAX_ANSWERS);
        return cg.q_shown[qi];
    }
    return cg_shown_choices(node, cg.game, map);
}

/* The text lines a question's popup keeps for its buttons past two (and its answer's first page, shown in it), in a
   popup laid out as `l`: from five buttons never so many that a page keeps fewer than three lines of text below
   the title the popup leads with (src/vv_cie_graph.py answer_room; the popup then grows past a two-button popup's
   height by the rest: tests/test_multi_answer_popup.py's 800 x 600 render check). */
static int cg_answer_room(int node, const ce_layout *l) {
    unsigned char map[CG_MAX_ANSWERS];
    int n = cg_buttons(node, -1, map);
    int room = CG_ANSWER_LINES[n < 2 ? 2 : n];
    int most = l->lines - (l->with_title ? 5 : 0) - 3;
    if (n > CG_V4_ANSWERS && room > most) {
        room = most > 0 ? most : 0;
    }
    return room;
}

/* G1: question `node` (asked as question `qi`) shows five or more buttons, so its answer's first page starts a fresh
   popup (the notice's: no room for buttons) instead of sharing the question's (docs/event-collection/cie-v6-binary.md
   11).  Two to four: as before. */
static int cg_fresh_after(int node, int qi) {
    unsigned char map[CG_MAX_ANSWERS];
    return cg_g.version >= 6 && node >= 0 && cg_buttons(node, qi, map) > CG_V4_ANSWERS;
}

static int cg_answer_fresh_game;       /* the game whose last answer's page comes in a fresh popup (G1) */

/* The buttons of the question on screen (CG_ASKED), else two. */
static int cg_asked_answers(void) {
    unsigned char map[CG_MAX_ANSWERS];
    return cg.phase == CG_ASKED && cg.asking >= 0 && cg.asking < cg.display_count
               ? cg_buttons(cg.display_node[cg.asking], cg.answers, map) : 2;
}
static story_village cg_village;
static int cg_display_armed;           /* the armed custom event (or question) is this run's next display */
static int cg_purchasing;              /* the purchase arms its first display: not yet busy */
static int cg_dirty;                   /* the run changed since its file was written */
static ce_event cg_stub;               /* the armed event of a display: the title, no text, no change */
static ce_choice cg_choice_stub;       /* ... and its question's (labels filled in when asked) */
static ce_event cg_one;                /* one villager's change, through ce_apply */

#ifdef VVFP_TEST
static int test_graph_patches = -1;    /* the patches on, -1 = as seen */
static int test_graph_scroll = -1;     /* Scrolling Popups installed (1) or not (0), -1 = as its companion says */
static int test_graph_scale = -1;      /* the scale mode, -1 = as the companion says */
static int test_graph_puzzles = -1;    /* the puzzles solved (bit = the adapter's index), -1 = as the game says */
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

/* A villager no harm may reach (version 6, the owner's rule): a nursing parent of either sex (the game's own
   "expecting" field, one state with carrying), a special villager (cg_special); A New Home's and The Lost
   Children's listed() already leave out what is not a villager (The Lost Children's totems). */
static int cg_protected(const ce_adapter *a, int game, const unsigned char *r) {
    return *(const int *)(r + a->off_pregnant) != 0 || cg_special(a, game, r);
}

/* Record `r`'s best value in the skills `list` names (comma separated) that the game has, -1 when it has none. */
static int cg_skill_value(const ce_adapter *a, const unsigned char *r, const char *list) {
    char word[32];
    int best = -1, k, entry;
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            if (lstrcmpiA(a->skill_names[k], word) == 0) {
                int v = a->skills_float ? (int)*(const float *)(r + a->off_skills + 4u * (unsigned int)k)
                                        : *(const int *)(r + a->off_skills + 4u * (unsigned int)k);
                if (v > best) {
                    best = v;
                }
            }
        }
    }
    return best;
}

/* The game has none of the skills `list` names: its requirement does not apply there. */
static int cg_skills_known(const ce_adapter *a, const char *list) {
    char word[32];
    int k, entry;
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            if (lstrcmpiA(a->skill_names[k], word) == 0) {
                return 1;
            }
        }
    }
    return 0;
}

/* The roles whose requirements are dropped for this cast (CG_CAST_PREFER: nobody meets them); the safety rules
   are never dropped. */
static unsigned int cg_relax_mask;
static int cg_cast_now = CG_CAST_STRICT;

/* Whether record `index` may be role `role` (any binding aside). */
static int cg_eligible(const ce_adapter *a, int game, int role, int index) {
    const unsigned char *spec = cg_role_at(&cg_g, role);
    const unsigned char *r = a->record(index);
    int sex;
    if (spec[0] != CG_ROLE_VILLAGER || r == NULL || !a->listed(r)) {
        return 0;
    }
    if (game == 3 && r[0xE94] != 0) {
        return 0;                      /* The Secret City's stand-in record */
    }
    /* Safety: never dropped. */
    if ((spec[1] & CG_ROLE_NURSING) && *(const int *)(r + a->off_pregnant) != 0) {
        return 0;
    }
    if ((spec[1] & CG_ROLE_SPECIAL) && cg_special(a, game, r)) {
        return 0;
    }
    if ((spec[1] & CG_ROLE_BELIEVERS) && cg_heathen(game, r)) {
        return 0;
    }
    if (cg_g.version >= 6 && (spec[1] & CG_ROLE_PROTECTED) && cg_protected(a, game, r)) {
        return 0;
    }
    /* The requirements (version 6: dropped for a role nobody meets when the cast prefers them). */
    if (cg_relax_mask & (1u << role)) {
        return 1;
    }
    if (ce_age(a, r) < 20 * (int)spec[3]) {
        return 0;
    }
    sex = ce_sex(a, r);
    if ((spec[2] == 1 && sex != STORY_SEX_MALE) || (spec[2] == 2 && sex != STORY_SEX_FEMALE)) {
        return 0;
    }
    if (cg_g.version >= 6) {
        unsigned int skills = cg_u16(spec + 10);
        if (spec[8] != 0 && ce_age(a, r) >= 20 * ((int)spec[8] + 1)) {
            return 0;                  /* older than the role's max age in whole years */
        }
        if (skills != CG_NONE && cg_skills_known(a, cg_s(&cg_g, skills))
            && cg_skill_value(a, r, cg_s(&cg_g, skills)) < (int)spec[12]) {
            return 0;
        }
        switch (spec[9]) {
        case 1: if (ce_role(a, r, NULL) != STORY_KIND_GOLDEN_CHILD) { return 0; } break;
        case 2: if (ce_role(a, r, NULL) != STORY_KIND_TRIBAL_CHIEF) { return 0; } break;
        case 3: if (*(const int *)(r + a->off_pregnant) == 0) { return 0; } break;
        default: break;
        }
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

/* VERSION 3: AGE GAPS.  A villager role may be "at most N years apart" from another (the role's bytes 6 and 7:
   that role + 1, N).  The matching above cannot see a rule between two roles, so with a gap the roles are filled
   by a search: each role in turn takes an eligible villager not taken, within every gap of the roles already
   filled (cg_try), until all are filled or none can be (CG_GAP_STEPS bounds it: a village too big to search is
   refused rather than hung).  Ages in the games' own units, 20 a year (ce_age). */
#define CG_GAP_STEPS 400000
static int cg_try[CG_MAX_ROLES];       /* the record each role holds in this search, -1 */
static int cg_gap_steps;

static int cg_has_gaps(void) {
    int r;
    for (r = 0; r < cg_g.n_role; ++r) {
        if (cg_role_at(&cg_g, r)[6] != 0) {
            return 1;
        }
    }
    return 0;
}

static void cg_try_reset(void) {
    int r;
    for (r = 0; r < CG_MAX_ROLES; ++r) {
        cg_try[r] = -1;
    }
}

/* Record `i` as role `r` keeps every age gap with the roles already filled. */
static int cg_gap_ok(const ce_adapter *a, int r, int i) {
    const unsigned char *spec = cg_role_at(&cg_g, r);
    int q;
    for (q = 0; q < cg_g.n_role; ++q) {
        const unsigned char *qs = cg_role_at(&cg_g, q);
        int years, diff;
        if (q == r || cg_try[q] < 0 || (cg_relax_mask & ((1u << r) | (1u << q)))) {
            continue;
        }
        if (spec[6] == (unsigned char)(q + 1)) {
            years = spec[7];
        } else if (qs[6] == (unsigned char)(r + 1)) {
            years = qs[7];
        } else {
            continue;
        }
        diff = ce_age(a, a->record(i)) - ce_age(a, a->record(cg_try[q]));
        if (diff < 0) {
            diff = -diff;
        }
        if (diff > 20 * years) {
            return 0;
        }
    }
    return 1;
}

static int cg_search(const ce_adapter *a, int game, unsigned int roles, unsigned char *used) {
    int r, i;
    if (roles == 0u) {
        return 1;
    }
    if (++cg_gap_steps > CG_GAP_STEPS) {
        return 0;
    }
    for (r = 0; r < cg_g.n_role && !(roles & (1u << r)); ++r) {
    }
    if (r >= cg_g.n_role || cg_role_at(&cg_g, r)[0] != 0) {
        return cg_search(a, game, roles & ~(1u << r), used);
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        int ok;
        if (used[i] || !cg_eligible(a, game, r, i) || !cg_gap_ok(a, r, i)) {
            continue;
        }
        used[i] = 1;
        cg_try[r] = i;
        ok = cg_search(a, game, roles & ~(1u << r), used);
        used[i] = 0;
        cg_try[r] = -1;
        if (ok) {
            return 1;
        }
    }
    return 0;
}

static int cg_matchable(const ce_adapter *a, int game, unsigned int roles, const unsigned char *used) {
    unsigned char seen[CE_MAX_RECORDS];
    int r;
    if (cg_has_gaps()) {
        static unsigned char copy[CE_MAX_RECORDS];
        memcpy(copy, used, sizeof copy);
        cg_gap_steps = 0;
        return cg_search(a, game, roles, copy);
    }
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

/* VERSION 6 CASTING.  STRICT (the rare roll, Pick Island Event): every requirement must hold.  PREFER (bought
   through the library): the requirements are kept where the village can meet them; a role nobody meets has its
   requirements dropped, then -- when the roles still cannot be filled together -- every role's; the safety rules
   (living, listed, the stand-in, Heathens, the protected filter) never.  1 when `roles` can then be filled, the
   dropped roles in cg_relax_mask. */
static int cg_plan_cast(const ce_adapter *a, int game, unsigned int roles, const unsigned char *used) {
    int r, i;
    cg_relax_mask = 0;
    cg_try_reset();
    if (cg_matchable(a, game, roles, used)) {
        return 1;
    }
    if (cg_cast_now != CG_CAST_PREFER || cg_g.version < 6) {
        return 0;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        if (!(roles & (1u << r)) || cg_role_at(&cg_g, r)[0] != CG_ROLE_VILLAGER) {
            continue;
        }
        for (i = 0; i < a->record_count && i < CE_MAX_RECORDS && (used[i] || !cg_eligible(a, game, r, i)); ++i) {
        }
        if (i >= a->record_count || i >= CE_MAX_RECORDS) {
            cg_relax_mask |= 1u << r;
        }
    }
    cg_try_reset();
    if (cg_matchable(a, game, roles, used)) {
        return 1;
    }
    cg_relax_mask |= roles;
    cg_try_reset();
    return cg_matchable(a, game, roles, used);
}

/* Whether the village can fill the planned roles now. */
static int cg_feasible(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char used[CE_MAX_RECORDS];
    if (a == NULL) {
        return 0;
    }
    memset(used, 0, sizeof used);
    cg_try_reset();
    cg_relax_mask = cg.relaxed;
    cg_cast_now = cg.cast_mode;
    if (cg_matchable(a, game, cg.planned, used)) {
        return 1;
    }
    return cg_plan_cast(a, game, cg.planned, used);
}

/* Role `r`'s villager if it is an alias: the member drawn (-1 none), else `r`. */
static int cg_resolve_role(int r) {
    if (r < 0 || r >= cg_g.n_role) {
        return -1;
    }
    return cg_role_at(&cg_g, r)[0] >= CG_ROLE_ALIAS ? cg.alias[r] : r;   /* an alias or an other role */
}

/* Every alias role drawn among its bound (or planned, before the binding) members, in role order, each members[
   ce_random_below(count)] (docs/event-collection/cie-v6-binary.md 6.1); once a run. */
static void cg_draw_aliases(const ce_adapter *a, unsigned int bound) {
    int r, k;
    if (cg.aliases_drawn) {
        return;
    }
    cg.aliases_drawn = 1;
    for (r = 0; r < CG_MAX_ROLES; ++r) {
        cg.alias[r] = -1;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        int members[CG_MAX_ROLES], n = 0;
        if (spec[0] != CG_ROLE_ALIAS) {
            continue;
        }
        for (k = 0; k < cg_g.n_role; ++k) {
            if ((cg_u16(spec + 14) & (1u << k)) && (bound & (1u << k))) {
                members[n++] = k;
            }
        }
        cg.alias[r] = (signed char)(n > 0 ? members[ce_random_below(a, n)] : -1);
    }
    /* G2: each "other" role, with no roll: its alias's member that was not drawn (unbound when that member or the
       alias is). */
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        int al;
        if (spec[0] != CG_ROLE_OTHER) {
            continue;
        }
        for (al = 0; al < cg_g.n_role && cg_u16(spec + 14) != (1u << al); ++al) {
        }
        if (al >= cg_g.n_role || cg.alias[al] < 0) {
            continue;
        }
        for (k = 0; k < cg_g.n_role; ++k) {
            if ((cg_u16(cg_role_at(&cg_g, al) + 14) & (1u << k)) && k != cg.alias[al] && (bound & (1u << k))) {
                cg.alias[r] = (signed char)k;
            }
        }
    }
}

/* ---- Named strangers (docs/event-collection/cie-v6-binary.md 16) ------------------------------------------ */

/* The game's own first-name list of one sex (read where the game keeps it), else the same list built in. */
static const char *cg_names_list(int game, int female) {
    static char list[2048];
    unsigned int n;
    int ok = 1;
    if (game < 1 || game > 5) {
        return "";
    }
    n = CG_NAMES_BYTES[game][female];
    if (n == 0u || n >= sizeof list) {
        return CG_NAMES_TEXT[game][female];
    }
    __try {
        memcpy(list, (const void *)(uintptr_t)CG_NAMES_VA[game][female], n);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 0;
    }
    list[n] = '\0';
    {
        unsigned int i;
        for (i = 0; ok && i < n; ++i) {
            char c = list[i];
            ok = c == ',' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
        }
        ok = ok && list[0] != ',' && list[n - 1] == ',';
    }
    return ok ? list : CG_NAMES_TEXT[game][female];
}

/* `a` and `b` agree in their first `n` bytes, ignoring the case of A-Z. */
static int cg_same_ci(const char *a, const char *b, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        char x = a[i], y = b[i];
        x = (char)(x >= 'a' && x <= 'z' ? x - 'a' + 'A' : x);
        y = (char)(y >= 'a' && y <= 'z' ? y - 'a' + 'A' : y);
        if (x != y) {
            return 0;
        }
    }
    return 1;
}

/* Whether `name` (`n` bytes) is a living, listed villager's first name or a named stranger's bound before role
   `upto`, ignoring case. */
static int cg_name_taken(const ce_adapter *a, int upto, const char *name, int n) {
    char have[CG_NAME_BYTES];
    int i, k;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *rec = a->record(i);
        if (rec == NULL || !a->listed(rec)) {
            continue;
        }
        ce_copy_name(have, CG_NAME_BYTES, rec + a->off_name, a->name_bytes);
        for (k = 0; have[k] != '\0' && have[k] != ' '; ++k) {
        }
        have[k] = '\0';
        if (k == n && cg_same_ci(have, name, n)) {
            return 1;
        }
    }
    for (i = 0; i < upto; ++i) {
        if (cg_role_at(&cg_g, i)[0] == CG_ROLE_STRANGER && lstrlenA(cg.name[i]) == n
            && cg_same_ci(cg.name[i], name, n)) {
            return 1;
        }
    }
    return 0;
}

/* Stranger role `r`'s first name: random_below over the list of its sex's names nobody has (else the whole list). */
static void cg_stranger_name(const ce_adapter *a, int game, int r) {
    const char *list = cg_names_list(game, cg.female[r]);
    int pass, count, pick = -1;
    for (pass = 0; pass < 2 && pick < 0; ++pass) {
        const char *s;
        int k = 0;
        count = 0;
        for (s = list; *s != '\0';) {
            const char *e = s;
            while (*e != '\0' && *e != ',') {
                ++e;
            }
            if (e > s && (pass == 1 || !cg_name_taken(a, r, s, (int)(e - s)))) {
                ++count;
            }
            s = *e == ',' ? e + 1 : e;
        }
        if (count == 0) {
            continue;
        }
        pick = ce_random_below(a, count);
        for (s = list; *s != '\0';) {
            const char *e = s;
            while (*e != '\0' && *e != ',') {
                ++e;
            }
            if (e > s && (pass == 1 || !cg_name_taken(a, r, s, (int)(e - s)))) {
                if (k++ == pick) {
                    int n = (int)(e - s) < CG_NAME_BYTES - 1 ? (int)(e - s) : CG_NAME_BYTES - 1;
                    memcpy(cg.name[r], s, (size_t)n);
                    cg.name[r][n] = '\0';
                    return;
                }
            }
            s = *e == ',' ? e + 1 : e;
        }
    }
}

/* The longest name in the game's two lists: a named stranger's worst case. */
static int cg_stranger_room(int game) {
    int f, best = 0;
    for (f = 0; f < 2 && game >= 1 && game <= 5; ++f) {
        const char *s = CG_NAMES_TEXT[game][f];
        int n = 0;
        for (; *s != '\0'; ++s) {
            n = *s == ',' ? 0 : n + 1;
            if (n > best) {
                best = n;
            }
        }
    }
    return best;
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
    cg_try_reset();
    cg_relax_mask = cg.relaxed;
    cg_cast_now = cg.cast_mode;
    if (!cg_matchable(a, game, left, used)) {
        if (!cg_plan_cast(a, game, left, used)) {
            return 0;
        }
        cg.relaxed = cg_relax_mask;
    }
    cg_try_reset();
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        int n = 0, i, pick;
        cg.record[r] = -1;
        if (spec[0] == CG_ROLE_ALIAS) {
            continue;
        }
        if (spec[0] == 1) {
            cg.female[r] = spec[2] == 2 ? 1 : spec[2] == 1 ? 0 : ce_random_below(a, 2);
            cg.name[r][0] = '\0';
            if (cg_g.version >= 6 && (spec[1] & CG_STRANGER_NAMED)) {
                cg_stranger_name(a, game, r);      /* cie-v6-binary.md 16 */
            }
            continue;
        }
        if (!(left & (1u << r))) {
            continue;
        }
        left &= ~(1u << r);
        for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
            if (used[i] || !cg_eligible(a, game, r, i) || !cg_gap_ok(a, r, i)) {
                continue;
            }
            used[i] = 1;
            cg_try[r] = i;
            if (cg_matchable(a, game, left, used)) {
                candidates[n++] = i;
            }
            cg_try[r] = -1;
            used[i] = 0;
        }
        if (n == 0) {
            return 0;
        }
        if (cg_g.version >= 6 && spec[13] == 1 && cg_u16(spec + 10) != CG_NONE && !(cg_relax_mask & (1u << r))) {
            /* "pick": "highest": only the villagers with the top value of the listed skills, then drawn. */
            const char *skills = cg_s(&cg_g, cg_u16(spec + 10));
            int best = -1, m = 0;
            for (i = 0; i < n; ++i) {
                int v = cg_skill_value(a, a->record(candidates[i]), skills);
                if (v > best) {
                    best = v;
                }
            }
            for (i = 0; i < n; ++i) {
                if (cg_skill_value(a, a->record(candidates[i]), skills) == best) {
                    candidates[m++] = candidates[i];
                }
            }
            n = m;
        }
        pick = candidates[ce_random_below(a, n)];
        used[pick] = 1;
        cg_try[r] = pick;
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

/* Whether `game`'s puzzle `name` is solved: the adapter's puzzle_solved, the flag the game's own Puzzles and
   Statistics screens read (A New Home: the world's byte, The Cave at [world +0x9FA8], story_c1.inc C1_PUZZLES;
   the other games' tables in story_c2..c5.inc).  0 when the game has no puzzle of that name. */
static int cg_puzzle_solved(int game, const char *name) {
    const ce_adapter *a = ce_adapter_for(game);
    int i;
#ifdef VVFP_TEST
    if (test_graph_puzzles >= 0) {
        for (i = 0; a != NULL && i < a->puzzle_count; ++i) {
            if (lstrcmpA(a->puzzles[i].name, name) == 0) {
                return (test_graph_puzzles >> i) & 1;
            }
        }
        return 0;
    }
#endif
    if (a == NULL || a->puzzle_solved == NULL) {
        return 0;
    }
    for (i = 0; i < a->puzzle_count; ++i) {
        if (lstrcmpA(a->puzzles[i].name, name) == 0) {
            return a->puzzle_solved(i) != 0;
        }
    }
    return 0;
}

/* VERSION 6 RUNTIME FACTS. */

/* Living, listed villagers now (New Believers: believers), `children` 1: only those under 14. */
static int cg_population(int game, int children) {
    const ce_adapter *a = ce_adapter_for(game);
    int i, n = 0;
    if (a == NULL) {
        return 0;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        if (r != NULL && a->listed(r) && !cg_heathen(game, r) && (!children || ce_age(a, r) < 20 * 14)) {
            ++n;
        }
    }
    return n;
}

/* The Golden Child (1) or the Tribal Chief (2) is alive and listed. */
static int cg_special_present(int game, int kind) {
    const ce_adapter *a = ce_adapter_for(game);
    int i, want = kind == 1 ? STORY_KIND_GOLDEN_CHILD : STORY_KIND_TRIBAL_CHIEF;
    if (a == NULL) {
        return 0;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        if (r != NULL && a->listed(r) && ce_role(a, r, NULL) == want) {
            return 1;
        }
    }
    return 0;
}

static unsigned char *cg_villager(const ce_adapter *a, int r);

/* Role `r`'s villager (an alias: its member's) is bound, not gone, and not protected now: harm may reach them. */
static int cg_harmable(int r, int game) {
    const ce_adapter *a = ce_adapter_for(game);
    const unsigned char *record;
    r = cg_resolve_role(r);
    if (a == NULL || r < 0) {
        return 0;
    }
    record = cg_villager(a, r);
    return record != NULL && !cg_protected(a, game, record);
}

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
    case CGC_ROLE:
        if (cg_role_at(&cg_g, (int)a)[0] >= CG_ROLE_ALIAS) {
            /* An alias (or other role) holds when it is bound: its member drawn (before the draw: an alias's member
               to be bound; an other role's alias's). */
            const unsigned char *spec = cg_role_at(&cg_g, (int)a);
            unsigned int mask = cg_u16(spec + 14);
            if (cg.aliases_drawn) {
                return cg.alias[a] >= 0;
            }
            if (spec[0] == CG_ROLE_OTHER) {
                int al;
                for (al = 0; al < cg_g.n_role && mask != (1u << al); ++al) {
                }
                mask = al < cg_g.n_role ? cg_u16(cg_role_at(&cg_g, al) + 14) : 0u;
                return (mask & cg.bound) == mask && mask != 0u;
            }
            return (mask & cg.bound) != 0u;
        }
        return (cg.bound >> a) & 1u;
    case CGC_HARMABLE: return cg_harmable((int)a, game);
    case CGC_SPECIAL_PRESENT: return cg_special_present(game, (int)a);
    case CGC_MIN_POPULATION: return cg_population(game, 0) >= (int)a;
    case CGC_MIN_CHILDREN: return cg_population(game, 1) >= (int)a;
    case CGC_GAME: return (a >> (game - 1)) & 1u;
    case CGC_PATCH: return (cg.patches >> a) & 1u;
    case CGC_PUZZLE: return (int)cg_u16(c + 4) != game || cg_puzzle_solved(game, cg_s(&cg_g, a));
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
        /* Version 6: the hard harm guard, as one more condition (a protected villager is never harmed: the
           branch is replaced by its else, or left out). */
        if (cg_holds_cond((int)cg_u16(c + 4), game, 0)
            && (cg_g.version < 6 || cg_holds_cond((int)cg_u16(c + 10), game, 0))) {
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

/* An effect's own roll as its node is reached, into the history (cg_per_game: above the loader). */
static void cg_roll_effect(const ce_adapter *a, int game, const unsigned char *e, cg_history *h) {
    int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
    int va = 0, vb = 0;
    switch (e[0]) {
    case CGE_FOOD: case CGE_TECH:
        /* Version 5: this game's own amount or range, when the effect lists one. */
        if (cg_u16(e + 12) != CG_NONE && cg_per_game(cg_s(&cg_g, cg_u16(e + 12)), game, &lo, &hi) == 1) {
            if (hi == lo) {
                hi = 0;
            }
        }
        if (hi != 0) {
            /* Version 3: a range, each amount equally likely (the game's random routine), then scaled as a fixed
               amount is. */
            lo += ce_random_below(a, hi - lo + 1);
        }
        va = (e[2] & 1u) ? cg_scaled(a, game, e[0] == CGE_FOOD, lo) : lo;
        break;
    case CGE_HEALTH:
        va = lo + ce_random_below(a, hi - lo + 1);
        break;
    case CGE_SKILL: {
        int n = cg_skills(a, e, -1);
        va = n > 0 ? cg_skills(a, e, ce_random_below(a, n)) : -1;
        vb = lo + ce_random_below(a, hi - lo + 1);   /* version 6: a loss too (lo..hi below 0) */
        break;
    }
    case CGE_HEALTH_CHANGE: case CGE_DAMAGE:
        va = lo + ce_random_below(a, hi - lo + 1);
        break;
    case CGE_SKILL_SET: {
        int n = cg_skills(a, e, -1);
        va = n > 0 ? cg_skills(a, e, ce_random_below(a, n)) : -1;
        vb = lo;                       /* the value set: no roll */
        break;
    }
    default:
        break;                         /* celebrate, action, mood: no roll */
    }
    if (h->fx < CG_MAX_FX) {
        h->fx_a[h->fx] = va;
        h->fx_b[h->fx] = vb;
    }
    ++h->fx;
}

/* A node's effects the run makes: none for a question (version 2 refuses them; version 1 never made them). */
static int cg_fx_count(const unsigned char *n) {
    return n[0] == CG_QUESTION ? 0 : (int)cg_u16(n + 20);
}

/* The visited set: the path's first `upto` nodes. */
static void cg_visit_path(int upto) {
    int i;
    memset(cg_visited, 0, sizeof cg_visited);
    for (i = 0; i < upto && i < cg.path.nodes; ++i) {
        cg_visit(cg.path.node[i]);
    }
}

/* ---- Version 6 pools: each instance drawn once a run, in the walk -------------------------------------------- */

/* The picks of the segment being walked (an answer's: kept apart until it is answered), NULL while the path's own
   are drawn. */
static cg_pick *cg_seg_pk;
static unsigned char *cg_seg_pk_count;

/* Instance `instance` of pool `pool` as drawn on the run so far (the path's, then the segment's), or NULL. */
static const cg_pick *cg_find_pick(int pool, int instance) {
    int i;
    for (i = 0; i < cg.pick_count && i < CG_MAX_PICKS; ++i) {
        if (cg.picks[i].pool == (unsigned short)pool && cg.picks[i].instance == (unsigned short)instance) {
            return &cg.picks[i];
        }
    }
    for (i = 0; cg_seg_pk != NULL && i < *cg_seg_pk_count; ++i) {
        if (cg_seg_pk[i].pool == (unsigned short)pool && cg_seg_pk[i].instance == (unsigned short)instance) {
            return &cg_seg_pk[i];
        }
    }
    return NULL;
}

/* Item `item` of `pool` is drawn by another instance already. */
static int cg_item_taken(int pool, int item) {
    int i;
    for (i = 0; i < cg.pick_count && i < CG_MAX_PICKS; ++i) {
        if (cg.picks[i].pool == (unsigned short)pool && cg.picks[i].item == (unsigned short)item) {
            return 1;
        }
    }
    for (i = 0; cg_seg_pk != NULL && i < *cg_seg_pk_count; ++i) {
        if (cg_seg_pk[i].pool == (unsigned short)pool && cg_seg_pk[i].item == (unsigned short)item) {
            return 1;
        }
    }
    return 0;
}

static void cg_scan_pools(const ce_adapter *a, int game, const char *text, int depth);

/* G3: whether `text` is the text of an item drawn so far (the path and the segment) by an instance of a pool that
   `list` names (comma separated). */
static int cg_pick_text_is(const cg_pick *k, const char *list, const char *text) {
    char word[40];
    int entry;
    const char *name;
    const unsigned char *p;
    if (k->item == CG_NONE) {
        return 0;
    }
    p = cg_pool_at(&cg_g, k->pool);
    name = cg_s(&cg_g, cg_u16(p));
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        if (lstrcmpA(word, name) == 0) {
            return lstrcmpA(cg_s(&cg_g, cg_u16(cg_item_at(&cg_g, (int)cg_u16(p + 2) + k->item))), text) == 0;
        }
    }
    return 0;
}

static int cg_text_taken_by(const char *list, const char *text) {
    int i;
    for (i = 0; i < cg.pick_count && i < CG_MAX_PICKS; ++i) {
        if (cg_pick_text_is(&cg.picks[i], list, text)) {
            return 1;
        }
    }
    for (i = 0; cg_seg_pk != NULL && i < *cg_seg_pk_count; ++i) {
        if (cg_pick_text_is(&cg_seg_pk[i], list, text)) {
            return 1;
        }
    }
    return 0;
}

/* Instance `instance` of `pool` drawn, unless the run has it: its eligible items (their conditions hold now; a
   distinct pool's not drawn by its other instances, unless that leaves none), weighted; none: the empty text, no
   roll.  Then the item's own tokens, depth first. */
static void cg_draw_instance(const ce_adapter *a, int game, int pool, int instance, int depth) {
    static int weights[CG_POOL_DEPTH + 1][1024];
    static int items[CG_POOL_DEPTH + 1][1024];
    const unsigned char *p = cg_pool_at(&cg_g, pool);
    int first = (int)cg_u16(p + 2), count = (int)cg_u16(p + 4);
    int n = 0, total = 0, k, pass, item = (int)CG_NONE;
    cg_pick pick;
    if (depth > CG_POOL_DEPTH || cg_find_pick(pool, instance) != NULL) {
        return;
    }
    for (pass = 0; pass < 2 && n == 0; ++pass) {
        total = 0;
        for (k = 0; k < count && n < 1024; ++k) {
            const unsigned char *it = cg_item_at(&cg_g, first + k);
            if (!cg_holds_cond((int)cg_u16(it + 4), game, 0)) {
                continue;
            }
            if (pass == 0 && (p[6] & 1u) && cg_item_taken(pool, k)) {
                continue;
            }
            if (pass == 0 && cg_u16(p + 8) != CG_NONE
                && cg_text_taken_by(cg_s(&cg_g, cg_u16(p + 8)), cg_s(&cg_g, cg_u16(it)))) {
                continue;              /* G3: the text an instance of a listed pool has drawn */
            }
            items[depth][n] = k;
            weights[depth][n] = (int)cg_u16(it + 2);
            total += weights[depth][n++];
        }
        if (!(p[6] & 1u) && cg_u16(p + 8) == CG_NONE) {
            break;                     /* nothing taken out: one pass */
        }
    }
    if (n > 0) {
        item = items[depth][ce_roll_index(weights[depth], n, ce_random_below(a, total))];
    }
    pick.pool = (unsigned short)pool;
    pick.instance = (unsigned short)instance;
    pick.item = (unsigned short)item;
    if (cg_seg_pk != NULL) {
        if (*cg_seg_pk_count < CG_SEG_PICKS) {
            cg_seg_pk[(*cg_seg_pk_count)++] = pick;
        }
    } else if (cg.pick_count < CG_MAX_PICKS) {
        cg.picks[cg.pick_count++] = pick;
    }
    if (item != (int)CG_NONE) {
        cg_scan_pools(a, game, cg_s(&cg_g, cg_u16(cg_item_at(&cg_g, first + item))), depth + 1);
    }
}

/* Every pool token of `text`, left to right, drawn when the run has not drawn it yet. */
static void cg_scan_pools(const ce_adapter *a, int game, const char *text, int depth) {
    const char *s;
    for (s = text; *s != '\0'; ++s) {
        int pool, instance, n;
        if (*s == '\\' && s[1] != '\0') {
            ++s;
            continue;
        }
        if (*s != '{') {
            continue;
        }
        n = cg_parse_brace(&cg_g, s, &pool, &instance);
        if (n == 0) {
            continue;
        }
        if (pool >= 0) {
            cg_draw_instance(a, game, pool, instance, depth);
        }
        s += n - 1;
    }
}

/* A node's pools (version 6): its text's (the variant this run shows), then a question's labels, left to right. */
static const char *cg_node_text(int node, int game);

static void cg_node_pools(const ce_adapter *a, int game, int node) {
    const unsigned char *n = cg_node_at(&cg_g, node);
    int k;
    if (cg_g.version < 6) {
        return;
    }
    cg_scan_pools(a, game, cg_node_text(node, game), 1);
    if (n[0] == CG_QUESTION) {
        for (k = 0; k < (int)cg_u16(n + 14); ++k) {
            cg_scan_pools(a, game, cg_s(&cg_g, cg_u16(cg_child_at(&cg_g, (int)cg_u16(n + 12) + k) + 8)), 1);
        }
    }
}

/* One segment from `from`: the nodes and every effect's roll, up to the next question (included) or the end.
   `game` and the bound roles and patches decide the conditions; the path so far counts as visited.  Per node: its
   effects' rolls, its pools (version 6; into `picks` -- NULL: the path's own), then the child drawn. */
#ifdef VVFP_TEST
static int test_graph_nurse = -1;      /* a record that starts nursing as the next walk begins (the harm guard) */
#endif

static void cg_walk(const ce_adapter *a, int game, int from, cg_history *h, cg_pick *picks, unsigned char *picked) {
    int node = from;
#ifdef VVFP_TEST
    if (test_graph_nurse >= 0 && a->record(test_graph_nurse) != NULL) {
        *(int *)(a->record(test_graph_nurse) + a->off_pregnant) = 1;
        test_graph_nurse = -1;
    }
#endif
    memset(h, 0, sizeof *h);
    cg_seg_pk = picks;
    cg_seg_pk_count = picked;
    if (picked != NULL) {
        *picked = 0;
    }
    cg_visit_path(cg.path.nodes);
    while (node >= 0 && h->nodes < CG_MAX_PATH) {
        const unsigned char *n = cg_node_at(&cg_g, node);
        int k;
        h->node[h->nodes++] = (short)node;
        cg_visit(node);
        for (k = 0; k < cg_fx_count(n); ++k) {
            cg_roll_effect(a, game, cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k), h);
        }
        cg_node_pools(a, game, node);
        if (n[0] == CG_QUESTION) {
            break;
        }
        node = cg_draw(a, node, game);
    }
    cg_seg_pk = NULL;
    cg_seg_pk_count = NULL;
}

/* Segment `s` added to the path, with its picks (`count` of them). */
static void cg_path_add(const cg_history *s, const cg_pick *picks, int count) {
    int i;
    for (i = 0; i < s->nodes && cg.path.nodes < CG_MAX_PATH; ++i) {
        cg.path.node[cg.path.nodes++] = s->node[i];
    }
    for (i = 0; i < s->fx; ++i, ++cg.path.fx) {
        if (cg.path.fx < CG_MAX_FX) {
            cg.path.fx_a[cg.path.fx] = i < CG_MAX_FX ? s->fx_a[i] : 0;
            cg.path.fx_b[cg.path.fx] = i < CG_MAX_FX ? s->fx_b[i] : 0;
        }
    }
    for (i = 0; picks != NULL && i < count && cg.pick_count < CG_MAX_PICKS; ++i) {
        cg.picks[cg.pick_count++] = picks[i];
    }
}

/* ---- Placeholders, pages, popups ------------------------------------------------------------------------- */

/* The pronouns, (male, female): he/she .. man/woman, then version 6's himself/herself, woman/man, boy/girl,
   son/daughter. */
static const char *const CG_PRONOUNS[8][2] = {
    { "he", "she" }, { "his", "her" }, { "him", "her" }, { "man", "woman" },
    { "himself", "herself" }, { "man", "woman" }, { "boy", "girl" }, { "son", "daughter" } };

static const char *const *cg_pronoun(int what) {
    return CG_PRONOUNS[what <= CG_PH_MAN ? what - CG_PH_HE : what - CG_PH_HIMSELF + 4];
}

#ifdef VVFP_TEST
static int test_graph_unicode = -1;    /* the Unicode Text companion loaded (1) or not (0), -1 = as it is */
#endif

/* A New Home and The Lost Children draw ; ( ) & % only through the Unicode Text companion (src/vv_font_glyphs.py):
   without it they are written , - - and " percent" (docs/event-collection/cie-v6-binary.md 9). */
static int cg_fallback_on(void) {
    if (cg.game != 1 && cg.game != 2) {
        return 0;
    }
#ifdef VVFP_TEST
    if (test_graph_unicode >= 0) {
        return !test_graph_unicode;
    }
#endif
    return GetModuleHandleW(L"VVFP Unicode Text.dll") == NULL && GetModuleHandleW(L"VVFP Unicode Font.dll") == NULL;
}

/* `out` (its `n` bytes, `cap` the buffer) with the glyph fallback over it; the new length. */
static int cg_glyph_fallback(char *out, int n, int cap) {
    static char copy[CG_DISPLAY_BYTES / 4];
    int i, o = 0;
    if (n <= 0 || n >= (int)sizeof copy) {
        return n;
    }
    memcpy(copy, out, (size_t)n + 1);
    for (i = 0; i < n && o < cap - 1; ++i) {
        const char *put = NULL;
        char c = copy[i];
        switch (c) {
        case ';': c = ','; break;
        case '(': case ')': c = '-'; break;
        case '&': put = "and"; break;
        case '%': put = " percent"; break;
        default: break;
        }
        if (put == NULL) {
            out[o++] = c;
            continue;
        }
        for (; *put != '\0' && o < cap - 1; ++put) {
            out[o++] = *put;
        }
    }
    out[o] = '\0';
    return o;
}

/* G5: THE TRIBE'S NAME ({@tribe} / {@Tribe}), read at run time where every game keeps it: in its save manager (the
   singleton native/shared/game_save_slot.h names), in the block the game hands its own save writer, at that block's
   name offset (native/shared/village_identity.c, measured on 348 saves) -- manager + 8 + offset, the read More Island
   Events' The Troubling Signs makes in The Secret City (troubling_vv3.inc vv3_tribe: +0x12ED4) -- bounded by the
   field after it (the save slot); only bytes a player could type.  No name: "the village" / "The village". */
static const unsigned int CG_TRIBE_MANAGER[6] = { 0, 0x48AEDCu, 0x4997BCu, 0x4B309Cu, 0x4CB51Cu, 0x4DACE0u };
static const unsigned int CG_TRIBE_AT[6] = { 0, 0x10u, 0x10u, 0x12ED4u, 0x170C0u, 0x17D1Cu };
static const int CG_TRIBE_BYTES[6] = { 0, 33, 33, 21, 21, 21 };   /* the name field (src/vv_tribe_rename.py save_field) */
#define CG_TRIBE_MAX 64

/* The tribe's name in `game` into `out` (`cap` bytes): 1 when the game holds one. */
static int cg_tribe_name(int game, char *out, int cap) {
    int ok = 0;
    out[0] = '\0';
    if (game < 1 || game > 5 || cap < 2) {
        return 0;
    }
    __try {
        const unsigned char *manager = *(const unsigned char *const *)(uintptr_t)CG_TRIBE_MANAGER[game];
        int i;
        if (manager != NULL) {
            const unsigned char *name = manager + CG_TRIBE_AT[game];
            for (i = 0; i < CG_TRIBE_BYTES[game] && i < cap - 1 && name[i] != 0; ++i) {
                unsigned char c = name[i];
                if (c < 0x20 || c == 0x7F) {
                    break;
                }
                out[i] = (char)c;
            }
            ok = i > 0 && (i == CG_TRIBE_BYTES[game] || i == cap - 1 || name[i] == 0);
            out[ok ? i : 0] = '\0';
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 0;
        out[0] = '\0';
    }
    return ok;
}

/* The words {@tribe} (`capital` 0) or {@Tribe} stand for now. */
static const char *cg_tribe_words(int capital) {
    static char name[CG_TRIBE_MAX + 1];
    if (cg_tribe_name(cg.game, name, sizeof name)) {
        return name;
    }
    return capital ? "The village" : "the village";
}

/* The text pool token `pool`.`instance` stands for: the item drawn; with none drawn (never on a walked path) the
   longest eligible item for CG_EXPAND_WORST, else the first eligible one. */
static const char *cg_pool_text(int pool, int instance, int mode) {
    const cg_pick *pick = cg_find_pick(pool, instance);
    const unsigned char *p = cg_pool_at(&cg_g, pool);
    const char *best = NULL;
    int k;
    if (pick != NULL) {
        return pick->item == CG_NONE ? "" : cg_s(&cg_g, cg_u16(cg_item_at(&cg_g, (int)cg_u16(p + 2) + pick->item)));
    }
    for (k = 0; k < (int)cg_u16(p + 4); ++k) {
        const unsigned char *it = cg_item_at(&cg_g, (int)cg_u16(p + 2) + k);
        const char *s = cg_s(&cg_g, cg_u16(it));
        if (!cg_holds_cond((int)cg_u16(it + 4), cg.game, 0)) {
            continue;
        }
        if (best == NULL || (mode == CG_EXPAND_WORST && lstrlenA(s) > lstrlenA(best))) {
            best = s;
        }
        if (mode != CG_EXPAND_WORST) {
            break;
        }
    }
    return best != NULL ? best : "";
}

static int cg_pronoun_names;          /* cg_label_text's second pass: names as pronouns (cie-v6-binary.md 15) */

/* cg_expand's work at pool depth `depth`. */
static int cg_expand_in(const char *raw, char *out, int cap, int mode, int name_room, int award_kind, int award,
                        int depth) {
    int o = 0;
    const char *s = raw;
    while (*s != '\0' && o < cap - 1) {
        char word[CG_NAME_BYTES + 32];
        const char *put = NULL;
        int repeat = 0, role;
        cg_ph ph;
        const char *e;
        if (cg_g.version >= 6 && *s == '\\' && (s[1] == '(' || s[1] == ')')) {
            /* A literal parenthesis: kept escaped until the text is filled for the screen. */
            if (mode == CG_EXPAND_AWARD) {
                if (o + 2 < cap) {
                    out[o++] = s[0];
                    out[o++] = s[1];
                }
            } else {
                out[o++] = s[1];
            }
            s += 2;
            continue;
        }
        if (cg_g.version >= 6 && *s == '{') {
            int pool, instance, n = cg_parse_brace(&cg_g, s, &pool, &instance);
            if (n > 0 && pool < 0) {
                /* G5: {@tribe} / {@Tribe}: kept for the screen's pass; the worst case W x the longest tribe name
                   the game allows (31 in the first two games, 19 in the later three), else the name now. */
                if (mode == CG_EXPAND_AWARD) {
                    int c;
                    for (c = 0; c < n && o < cap - 1; ++c) {
                        out[o++] = s[c];
                    }
                } else if (mode == CG_EXPAND_WORST) {
                    int c, room = cg.game <= 2 ? 31 : 19;
                    for (c = 0; c < room && o < cap - 1; ++c) {
                        out[o++] = 'W';
                    }
                } else {
                    const char *t = cg_tribe_words(pool == CG_POOL_TRIBE_CAP);
                    int first = 1;
                    for (; *t != '\0' && o < cap - 1; ++t, first = 0) {
                        char c = *t;
                        if (first && pool == CG_POOL_TRIBE_CAP && c >= 'a' && c <= 'z') {
                            c = (char)(c - 'a' + 'A');
                        }
                        out[o++] = c;
                    }
                }
                s += n;
                continue;
            }
            if (n > 0) {
                if (depth < CG_POOL_DEPTH) {
                    o += cg_expand_in(cg_pool_text(pool, instance, mode), out + o, cap - o, mode, name_room,
                                      award_kind, award, depth + 1);
                }
                s += n;
                continue;
            }
        }
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
        role = ph.role >= 0 ? cg_resolve_role(ph.role) : -1;     /* an alias: its member drawn */
        if (ph.what == CG_PH_AWARD) {
            if (award_kind >= 0) {
                wsprintfA(word, "%d", award);
                put = word;
            }
        } else if (ph.what == CG_PH_UNIT) {
            put = award_kind < 0 ? NULL : award_kind == 0 ? "food" : "tech points";
        } else if (ph.what == CG_PH_NAME && cg_pronoun_names) {
            /* A label too wide with the names: each name as its role's pronoun (cie-v6-binary.md 15). */
            const char *const *pair = cg_pronoun(ph.hint >= 0 ? ph.hint : CG_PH_HIM);
            put = mode == CG_EXPAND_WORST ? (lstrlenA(pair[1]) > lstrlenA(pair[0]) ? pair[1] : pair[0])
                                          : pair[role >= 0 && cg.female[role] ? 1 : 0];
        } else if (mode == CG_EXPAND_WORST) {
            if (ph.what == CG_PH_NAME && role >= 0 && cg_role_at(&cg_g, role)[0] == CG_ROLE_STRANGER) {
                repeat = cg_stranger_room(cg.game);       /* 16: the longest name in the game's lists */
            } else if (ph.what == CG_PH_NAME) {
                repeat = name_room;
            } else {
                const char *const *pair = cg_pronoun(ph.what);
                put = lstrlenA(pair[1]) > lstrlenA(pair[0]) ? pair[1] : pair[0];
            }
        } else if (ph.what == CG_PH_NAME) {
            put = role >= 0 && ((cg.bound & (1u << role)) || cg_role_at(&cg_g, role)[0] == CG_ROLE_STRANGER)
                  ? cg.name[role] : "";             /* 16: a named stranger's drawn name */
        } else {
            put = cg_pronoun(ph.what)[role >= 0 && cg.female[role] ? 1 : 0];
        }
        if (put != NULL) {
            int first = 1, from = o;
            for (; *put != '\0' && o < cap - 1; ++put) {
                char c = *put;
                if (first && ph.capital && c >= 'a' && c <= 'z') {
                    c = (char)(c - 'a' + 'A');
                }
                first = 0;
                out[o++] = c;
            }
            if (ph.caps && o > from) {
                CharUpperBuffA(out + from, (DWORD)(o - from));   /* ALL CAPS: the word in capitals */
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

/* `raw` with its placeholders filled into `out` (`cap` bytes): CG_EXPAND_AWARD only the award's (the amount and
   its unit, or nothing when there is none: award_kind -1) and -- version 6 -- the pools' drawn words (the pages
   are laid out with them), CG_EXPAND_WORST the longest names the game holds and the longer pronouns,
   CG_EXPAND_REAL the bound villagers; both of these last two with \( \) as parentheses and the glyph fallback.
   Returns the length. */
static int cg_expand(const char *raw, char *out, int cap, int mode, int name_room, int award_kind, int award) {
    int n = cg_expand_in(raw, out, cap, mode, name_room, award_kind, award, 0);
    if (mode != CG_EXPAND_AWARD && cg_g.version >= 6 && cg_fallback_on()) {
        n = cg_glyph_fallback(out, n, cap);
    }
    return n;
}

/* A button label as the player reads it into `out` (CG_LABEL_V6 bytes): the real names, or -- when that is wider
   than the screen or longer than a label holds -- each name as its role's pronoun (cie-v6-binary.md 15). */
static void cg_label_text(const ce_adapter *a, const char *raw, char *out) {
    static char real[CG_LABEL_V6 * 4];
    int n = cg_expand(raw, real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
    if (cg_g.version >= 6 && (n >= CG_LABEL_V6 || ce_label_px(a, real) > ce_label_max_px(a))) {
        cg_pronoun_names = 1;
        cg_expand(raw, real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
        cg_pronoun_names = 0;
    }
    lstrcpynA(out, real, CG_LABEL_V6);
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
    int scroll;                        /* Scrolling Popups is installed: a page is as tall as the text (cg_scrolls) */
    const char *src;                   /* the popup's text being laid out ... */
    int consumed;                      /* ... and how much of it the pages so far hold */
    char page[CG_RAW_BYTES];
} cg_pager;

/* Whether "VVFP Scrolling Popups.dll" is installed in the game (VvfpScrollingPopupsInstalled: every one of its sites,
   which include every game's island-event popups): then a popup scrolls, so its text is never split into pages --
   each popup is ONE page, as tall as its text, limited only by the bytes the game's popup holds (CG_TEXT_MAX), as
   the patcher's own fit check counts it with scrolling (src/vv_cie_graph.py).  Without it the text is paged to fit
   the screen, as before. */
static int cg_scrolls(void) {
    typedef int (__stdcall *sp_installed_fn)(void);
    HMODULE module;
    sp_installed_fn installed;
#ifdef VVFP_TEST
    if (test_graph_scroll >= 0) {
        return test_graph_scroll;
    }
#endif
    module = GetModuleHandleA("VVFP Scrolling Popups.dll");
    installed = module != NULL ? (sp_installed_fn)(void *)GetProcAddress(module, "VvfpScrollingPopupsInstalled") : NULL;
    return installed != NULL && installed() != 0;
}

/* `text` (raw: names not filled) fits page `pages->count` at its widest: its bytes, and -- unless the popup
   scrolls -- its lines. */
static int cg_fits(cg_pager *w, const char *text) {
    static char worst[CG_RAW_BYTES + 512];
    const ce_layout *l = w->pages->count == 0 ? w->first : w->rest;
    int n = cg_expand(text, worst, sizeof worst, CG_EXPAND_WORST, w->a->name_room, -1, 0);
    if (n > CG_TEXT_MAX || n >= (int)sizeof worst - 1) {
        return 0;
    }
    return w->scroll || ce_lines_used_in(l, w->title, worst) <= l->lines - w->reserve;
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
    w.max_lines = cg_scrolls() ? 1000 : l->lines - 1;     /* a scrolling popup has room for every line */
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
static int cg_add_display(const char *text, int kind, int villager) {
    int n = lstrlenA(text);
    int k = cg.display_count;
    if (k >= CG_MAX_DISPLAYS || cg.display_used + n + 1 > CG_DISPLAY_BYTES) {
        return -1;
    }
    cg.display_off[k] = cg.display_used;
    memcpy(cg.displays + cg.display_used, text, (size_t)n + 1);
    cg.display_used += n + 1;
    cg.display_kind[k] = (unsigned char)kind;
    cg.display_node[k] = -1;
    cg.display_title[k] = 0;
    cg.display_villager[k] = (unsigned char)(villager != 0);
    cg.job_first[k] = (short)cg.jobs_used;
    cg.job_count[k] = 0;
    cg.applied_when[k] = 0;
    cg.sent_len[k] = 0;
    cg.display_count = k + 1;
    return k;
}

static const char *cg_display(int k) {
    return k >= 0 && k < cg.display_count ? cg.displays + cg.display_off[k] : "";
}

/* ---- Per-node popup titles (docs/event-collection/cie-v6-binary.md 14) ------------------------------------- */

#define CG_TITLE_CHANGES 16

/* Node `node`'s popup title as display_title holds it (string index + 1), 0 for none (before version 6: none). */
static unsigned short cg_node_title(int node) {
    const unsigned char *n;
    if (cg_g.version < 6 || node < 0 || node >= cg_g.n_node) {
        return 0;
    }
    n = cg_node_at(&cg_g, node);
    return n[0] != CG_BRANCH && cg_u16(n + 26) != CG_NONE ? (unsigned short)(cg_u16(n + 26) + 1u) : 0;
}

/* The words of title `t` (0: the event's own) into `out`. */
static void cg_title_text(unsigned short t, char *out, int cap) {
    lstrcpynA(out, t == 0 ? cg.title : cg_s(&cg_g, (unsigned int)t - 1u), cap);
}

/* The title of display `k`'s popup, into `out`. */
static void cg_display_title(int k, char *out, int cap) {
    cg_title_text(k >= 0 && k < cg.display_count ? cg.display_title[k] : 0, out, cap);
}

/* The title in force before history node `upto`: the last titled node's on the way, else the event's. */
static unsigned short cg_title_before(const cg_history *h, int upto) {
    unsigned short t = 0;
    int i;
    for (i = 0; i < upto && i < h->nodes; ++i) {
        unsigned short nt = cg_node_title(h->node[i]);
        if (nt != 0) {
            t = nt;
        }
    }
    return t;
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

/* ---- Version 6 effects ---------------------------------------------------------------------------------- */

/* Each game's own "Celebrating" (story_c1.inc .. story_c5.inc): A New Home 0x443FA0 with 9, The Lost Children the
   village celebration place 24 (0x459B60), the later three their action 0x52 / 0x2A / 0x31.  A bad mood is the
   villager shaking their head (every game has it); a good mood is the celebration (the owner's Q8 answer). */
static const char *const CG_CELEBRATE_WORDS[6] = {
    "", "Celebrating", "Celebrating (a new hut, first hut place) [Old Friends]", "Celebrating", "Celebrating",
    "Celebrating" };
#define CG_MOOD_BAD_WORDS "Shaking head"

/* The adapter's behaviour whose label is `words` (ignoring case), -1 none. */
static int cg_behaviour_by_words(const ce_adapter *a, const char *words) {
    int i;
    for (i = 0; a->behaviours != NULL && i < a->behaviour_count; ++i) {
        if (lstrcmpiA(a->behaviours[i].label, words) == 0) {
            return i;
        }
    }
    return -1;
}

/* The behaviour a celebrate, action or mood effect starts in `game`, -1 when the game has none. */
static int cg_behaviour_of(const ce_adapter *a, int game, const unsigned char *e) {
    const char *words;
    if (game < 1 || game > 5) {
        return -1;
    }
    switch (e[0]) {
    case CGE_CELEBRATE: words = CG_CELEBRATE_WORDS[game]; break;
    case CGE_MOOD: words = (int)cg_u32(e + 4) > 0 ? CG_CELEBRATE_WORDS[game] : CG_MOOD_BAD_WORDS; break;
    default: words = cg_s(&cg_g, cg_u16(e + 12)); break;
    }
    return cg_behaviour_by_words(a, words);
}

/* Whether effect `e` harms its villager (docs/event-collection/cie-v6-binary.md 7). */
static int cg_effect_harmful(const ce_adapter *a, int game, const unsigned char *e) {
    int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
    switch (e[0]) {
    case CGE_KILL: case CGE_VANISH: case CGE_SICK: return 1;
    case CGE_HEALTH: return hi < 100;
    case CGE_HEALTH_CHANGE: return lo < 0;
    case CGE_PREF: return (e[2] & 4u) != 0;
    case CGE_SKILL: return lo < 0;
    case CGE_MOOD: return lo < 0;
    case CGE_ACTION: {
        int b = cg_behaviour_of(a, game, e);
        return b >= 0 && (a->behaviours[b].group == CE_GROUP_MOOD || a->behaviours[b].unsafe != NULL);
    }
    default: return 0;
    }
}

/* A living villager's health now (every game's own field: the one its set_health writes). */
static int cg_health_now(int game, const unsigned char *record) {
    static const unsigned int OFFSET[6] = { 0, 0x344u, 0x52Cu, 0xE78u, 0x1C40u, 0x1C40u };
    return game >= 1 && game <= 5 ? *(const int *)(record + OFFSET[game]) : CE_HEALTH_MAX;
}

/* "celebrate" with "who": "all": every living, listed villager (New Believers: its believers) starts the game's
   own celebration -- children, nursing parents and the protected villagers too (a celebration harms no one). */
static void cg_celebrate_all(const ce_adapter *a, int game, ce_result *r) {
    static const unsigned char CELEBRATE[16] = { CGE_CELEBRATE, CG_ROLE_ALIAS_ALL };
    ce_result one;
    int i, behaviour = cg_behaviour_of(a, game, CELEBRATE);
    if (behaviour < 0) {
        return;
    }
    if (!(a->caps & CAP_BEHAVIOUR)) {
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    memset(&cg_one, 0, sizeof cg_one);
    cg_one.game = game;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS && cg_one.change_count < CE_MAX_CHANGES; ++i) {
        const unsigned char *record = a->record(i);
        ce_change *c;
        if (record == NULL || !a->listed(record) || cg_heathen(game, record) || (game == 3 && record[0xE94] != 0)) {
            continue;
        }
        c = &cg_one.changes[cg_one.change_count++];
        ce_change_init(c);
        c->index = i;
        c->fingerprint = ce_identity(a, record);
        c->behaviour = behaviour;
    }
    if (cg_one.change_count > 0) {
        ce_apply(a, &cg_one, &one);
        cg_merge_result(r, &one);
    }
}

/* The lines a page's effects add to the event's ONE log entry beyond the companion's comparison (a damaged
   structure, as The Rumblings writes it). */
static char cg_extra_lines[512];

#ifdef VVFP_TEST
static int test_graph_structures = -1;  /* the finished structures (bit k), -1 = as the game says */
static int test_graph_damaged[SD_MAX_STRUCTURES];   /* each structure's loss the test build recorded */
#endif

static int cg_structure_finished(int game, int k) {
#ifdef VVFP_TEST
    if (test_graph_structures >= 0) {
        return (test_graph_structures >> k) & 1;
    }
#endif
    return sd_finished(game, k);
}

/* Structure `k` of `game` is one the effect's list names ("any": every one). */
static int cg_structure_listed(int game, const char *list, int k) {
    char word[64];
    int entry;
    if (lstrcmpiA(list, "any") == 0) {
        return 1;
    }
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        if (sd_find(game, word) == k) {
            return 1;
        }
    }
    return 0;
}

/* "damage": one finished structure the effect names (drawn among them by the game's random routine as it is made)
   loses `percent` of its building work -- the states only a normal construction passes through
   (native/shared/structure_damage.h); none finished: nothing.  Nobody is hurt. */
static void cg_damage(const ce_adapter *a, int game, const unsigned char *e, int percent) {
    const char *list = cg_s(&cg_g, cg_u16(e + 12));
    int candidates[SD_MAX_STRUCTURES], n = 0, k;
    char line[160];
    for (k = 0; k < sd_structures(game) && k < SD_MAX_STRUCTURES; ++k) {
        if (cg_structure_finished(game, k) && cg_structure_listed(game, list, k)) {
            candidates[n++] = k;
        }
    }
    if (n == 0 || percent < 1) {
        return;
    }
    k = candidates[ce_random_below(a, n)];
    if (percent > 100) {
        percent = 100;
    }
#ifdef VVFP_TEST
    if (test_graph_structures >= 0) {
        test_graph_damaged[k] = percent;
    } else
#endif
    {
        __try {
            sd_damage(game, k, percent, a->record, a->record_count);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    wsprintfA(line, "  Damaged: %s, %d%% of its building work lost%s\n", sd_name(game, k), percent,
              percent >= 100 ? " (back to unbuilt)" : "");
    if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
        lstrcatA(cg_extra_lines, line);
    }
}

/* Effect `e` with its rolls (va, vb) on the village; the award's state in *award_kind / *award. */
static void cg_effect(const ce_adapter *a, int game, const unsigned char *e, int va, int vb, int *award_kind,
                      int *award, ce_result *r) {
    unsigned char *record;
    ce_result one;
    ce_change *c;
    int index, role;
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
    case CGE_DAMAGE:
        cg_damage(a, game, e, va);
        return;
    case CGE_CELEBRATE:
        if (e[1] == CG_ROLE_ALIAS_ALL) {
            cg_celebrate_all(a, game, r);
            return;
        }
        break;
    default:
        break;
    }
    role = cg_resolve_role(e[1]);      /* an alias: the member drawn */
    if (role < 0) {
        return;                        /* an alias with no member: nobody to change */
    }
    record = cg_villager(a, role);
    if (record == NULL) {
        /* Gone since the event began (old age, another event between its pages, or this event): that role's
           later effects are skipped -- never someone else in their record -- and the rest of the event goes on. */
        cg.gone |= 1u << role;
        return;
    }
    if ((cg_role_at(&cg_g, role)[1] & CG_ROLE_PROTECTED) && cg_effect_harmful(a, game, e)
        && cg_protected(a, game, record)) {
        /* The hard guard's last word (the walk's guard took the branch out unless they became protected since):
           a protected villager is never harmed. */
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    index = cg.record[role];
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
        cg.gone |= 1u << role;         /* gone for good: nothing more is done to them (their name stays) */
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
    case CGE_CELEBRATE: case CGE_ACTION: case CGE_MOOD: {
        int behaviour = cg_behaviour_of(a, game, e);
        if (behaviour < 0) {
            return;                    /* an action this game does not have: nothing (rule 8) */
        }
        if (!(a->caps & CAP_BEHAVIOUR)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->behaviour = behaviour;
        break;
    }
    case CGE_HEALTH_CHANGE: {
        int value = cg_health_now(game, record) + va;
        if (a->set_health == NULL) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->health = value < 1 ? 1 : (value > CE_HEALTH_MAX ? CE_HEALTH_MAX : value);   /* never kills */
        break;
    }
    case CGE_SKILL_SET:
        if (!(a->caps & CAP_SKILLS) || va < 0 || va >= a->skill_count) {
            return;                    /* a skill this game does not have: nothing (rule 8) */
        }
        c->skills[va] = vb < 0 ? 0 : (vb > 100 ? 100 : vb);
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
        cg.identity[role] = ce_identity(a, record);   /* the same villager, with what was just changed */
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
    int question;                      /* a question's own popup: the node, else -1 */
    int tcount;                        /* its titles: the one in force at its start (toff 0), then each titled */
    int toff[CG_TITLE_CHANGES];        /* node's, from where that node's text starts in raw */
    unsigned short ttitle[CG_TITLE_CHANGES];
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
        for (k = 0; k < cg_fx_count(n); ++k, ++fx) {
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
static int cg_group_in_question;       /* the first popup is shown in the answered question's own popup (14) */

static void cg_group(int game, const cg_history *h, int from) {
    static char text[CG_RAW_BYTES];
    int award_kind = -1, award = 0, fx, k, i, first_text = -1;
    unsigned short title = cg_title_before(h, from);
    cg_pop_count = 0;
    fx = cg_award_before(h, from, &award_kind, &award);
    cg_visit_path(from);
    for (i = 0; i < from && i < CG_MAX_PATH; ++i) {
        cg_node_pop[i] = -2;           /* an earlier segment's: laid out already */
    }
    for (i = from; i < h->nodes; ++i) {
        int node = h->node[i];
        const unsigned char *n = cg_node_at(&cg_g, node);
        int villager = 0;
        cg_visit(node);
        for (k = 0; k < cg_fx_count(n); ++k, ++fx) {
            const unsigned char *e = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k);
            villager |= e[0] >= CGE_KILL;
            if ((e[0] == CGE_FOOD || e[0] == CGE_TECH) && (e[2] & 2u)) {
                award_kind = e[0] == CGE_FOOD ? 0 : 1;
                award = fx < CG_MAX_FX ? h->fx_a[fx] : 0;
            }
        }
        if (n[0] != CG_BRANCH) {
            cg_popup *p = NULL;
            int start = 0;
            unsigned short nt = cg_node_title(node);
            cg_expand(cg_node_text(node, game), text, sizeof text, CG_EXPAND_AWARD, 0, award_kind, award);
            if (n[0] == CG_QUESTION || n[1] == 0 || cg_pop_count == 0 || cg_pops[cg_pop_count - 1].question >= 0) {
                if (cg_pop_count < CG_MAX_POPUPS) {
                    p = &cg_pops[cg_pop_count++];
                    memset(p, 0, sizeof *p);
                    p->question = n[0] == CG_QUESTION ? node : -1;
                    lstrcpynA(p->raw, text, sizeof p->raw);
                    p->tcount = 1;     /* the title in force at its start */
                    p->ttitle[0] = title;
                }
            } else {
                p = &cg_pops[cg_pop_count - 1];
                if (lstrlenA(p->raw) + 1 + lstrlenA(text) + 1 < (int)sizeof p->raw) {
                    start = lstrlenA(p->raw) + 1;
                    lstrcatA(p->raw, n[2] ? "\n" : " ");
                    lstrcatA(p->raw, text);
                }
            }
            if (nt != 0) {
                if (p != NULL && start == 0 && p->tcount == 1 && !(cg_group_in_question && p == &cg_pops[0])) {
                    p->ttitle[0] = nt;         /* a new popup starting with a titled node: only that title */
                } else if (p != NULL && p->tcount < CG_TITLE_CHANGES) {
                    p->toff[p->tcount] = start;   /* from the page this node's text starts on */
                    p->ttitle[p->tcount++] = nt;
                }
                title = nt;
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
    for (i = from; i < h->nodes && first_text >= 0; ++i) {
        if (cg_node_pop[i] == -1) {
            const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
            cg_node_pop[i] = 0;
            cg_node_end[i] = cg_node_end[first_text];
            for (k = 0; k < cg_fx_count(n); ++k) {
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

/* The path from node `from` (a segment: the start's, or an answer's) laid out as more of the run's displays:
   `after_question` 1 = its first page is a question's result, 0 = a plain event's first popup (or the start
   question's); each page with the nodes whose effects it makes.  A question's text is laid out for the question
   popup: its earlier pages shown first (notices, through the plain popup, which is never smaller), its last page
   the two-button popup itself. */
/* 14: the popup's WIDEST title (of those in force on it, the one that wraps into the most lines in `l`; the first
   on a tie) into `out`: its pages are laid out with it. */
static void cg_widest_title(const cg_popup *p, const ce_layout *l, char *out, int cap) {
    static char t[CE_TITLE_BYTES + 64];
    int j, most = -1;
    cg_title_text(0, out, cap);
    for (j = 0; j < p->tcount; ++j) {
        int lines;
        cg_title_text(p->ttitle[j], t, sizeof t);
        lines = ce_lines_used_in(l, t, "");
        if (lines > most) {
            most = lines;
            lstrcpynA(out, t, cap);
        }
    }
}

/* 14: the title page `k` of popup `p` shows: the last change that starts before the page's end. */
static unsigned short cg_page_title(const cg_popup *p, const cg_pages *pages, int k) {
    unsigned short t = p->tcount > 0 ? p->ttitle[0] : 0;
    int j;
    for (j = 1; j < p->tcount; ++j) {
        if (p->toff[j] < pages->src_end[k]) {
            t = p->ttitle[j];
        }
    }
    return t;
}

static void cg_layout_from(const ce_adapter *a, int game, int from, int after_question) {
    static cg_pager w;
    static cg_pages pages;
    static char real[CG_PAGE_BYTES];
    static char widest[CE_TITLE_BYTES + 64];
    const cg_history *h = &cg.path;
    int fresh = after_question && from > 0 && cg_fresh_after(h->node[from - 1], cg.answers);
    ce_layout first = after_question && !fresh ? ce_result_layout(a) : cg_notice_layout(a);
    ce_layout rest = cg_notice_layout(a);
    ce_layout q = ce_question_layout(a);
    int p, k, i, jobs = cg.jobs_used;
    q.check_title = 0;
    cg_group_in_question = after_question && from > 0 && !fresh;
    cg_group(game, h, from);
    cg_group_in_question = 0;
    for (p = 0; p < cg_pop_count; ++p) {
        int question = cg_pops[p].question >= 0;
        w.a = a;
        w.first = question ? &q : (p == 0 ? &first : &rest);
        w.rest = question ? &q : &rest;
        cg_widest_title(&cg_pops[p], w.first, widest, sizeof widest);
        w.title = widest;
        w.reserve = cg_pops[p].effects ? 2 : 0;
        if (question) {
            w.reserve += cg_answer_room(cg_pops[p].question, &q);
        } else if (p == 0 && after_question && from > 0 && !fresh) {
            w.reserve += cg_answer_room(h->node[from - 1], &first);   /* shown in the answered question's popup */
        }
        w.pages = &pages;
        w.scroll = cg_scrolls();
        cg_paginate(&w, cg_pops[p].raw);
        for (k = 0; k < pages.count; ++k) {
            int d, kind = CGD_PAGE;
            if (question && k + 1 == pages.count) {
                kind = CGD_QUESTION;
            } else if (p == 0 && k == 0 && after_question && !fresh) {
                kind = CGD_RESULT;     /* G1: after five or more buttons, a page of its own (a notice) */
            }
            cg_expand(pages.buf + pages.off[k], real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
            d = cg_add_display(real, kind, cg_pops[p].effects);
            if (d < 0) {
                cg.jobs_used = jobs;
                return;
            }
            cg.display_node[d] = (short)(kind == CGD_QUESTION ? cg_pops[p].question : -1);
            /* 14: a page shown in the question's own popup keeps that popup's title. */
            cg.display_title[d] = kind == CGD_RESULT ? cg_pops[p].ttitle[0] : cg_page_title(&cg_pops[p], &pages, k);
            cg.job_first[d] = (short)jobs;
            for (i = from; i < h->nodes; ++i) {
                const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
                int page = 0;
                if (cg_node_pop[i] != p || cg_fx_count(n) == 0) {
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
    cg.jobs_used = jobs;
}

/* The displays from `count` on taken away (a question answered again, a restore). */
static void cg_displays_cut(int count) {
    if (count < 0) {
        count = 0;
    }
    if (count >= cg.display_count) {
        return;
    }
    cg.display_count = count;
    cg.display_used = count > 0 ? cg.display_off[count - 1] + lstrlenA(cg.displays + cg.display_off[count - 1]) + 1 : 0;
    cg.jobs_used = count > 0 ? cg.job_first[count - 1] + cg.job_count[count - 1] : 0;
    if (cg.display_next > count) {
        cg.display_next = count;
    }
}

static void cg_entry_start(const char *label);

/* The run's first segment, from the start: walked, added to the path and laid out (the roles are bound). */
static void cg_start_run(const ce_adapter *a, int game) {
    static cg_history first;
    memset(&cg.path, 0, sizeof cg.path);
    cg.pick_count = cg.start_picks;    /* the start question's, drawn at the purchase (cg_queue) */
    cg.display_count = cg.display_next = cg.display_used = cg.jobs_used = 0;
    cg.answers = 0;
    cg.choice = -1;
    cg_draw_aliases(a, cg.bound);      /* version 6: before the first node (at the purchase for a question) */
    cg_walk(a, game, cg_g.start, &first, NULL, NULL);   /* its picks are the path's own */
    cg_path_add(&first, NULL, 0);
    cg_layout_from(a, game, 0, 0);
    if (!cg.question) {
        cg_entry_start(NULL);
    }
    cg.phase = CG_CHAIN;
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
static char cg_shown_title[CE_TITLE_BYTES];   /* the title of the run's popup shown last (14: a node's may differ) */

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
    if (title != NULL && title[0] != '\0' && lstrcmpA(title, cg.title) != 0 && lstrcmpA(title, cg_shown_title) != 0) {
        return 0;                      /* another event's popup */
    }
    cg_logged = 0;
    return 1;
}

/* The effects display `k` makes, each once: every node of its jobs, in the history's order, the award's state
   and the rolls as the walk left them. */
static void cg_make_effects(const ce_adapter *a, int game, int k, ce_result *r) {
    const cg_history *h = &cg.path;
    int j;
    memset(r, 0, sizeof *r);
    cg.gone_at[k] = cg.gone;
    memcpy(cg.identity_at[k], cg.identity, sizeof cg.identity);
    for (j = 0; j < cg.job_count[k]; ++j) {
        int i = cg.jobs[cg.job_first[k] + j];
        const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
        int award_kind, award, fx, e;
        fx = cg_award_before(h, i, &award_kind, &award);
        for (e = 0; e < cg_fx_count(n); ++e, ++fx) {
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
    ce_layout l = cg.display_kind[k] == CGD_RESULT ? ce_result_layout(a) : cg_notice_layout(a);
    int logging;
    cg.entry_at[k] = cg.entry_len;
    logging = cg.job_count[k] > 0 && cg_log_begin(game);
    cg_extra_lines[0] = '\0';
    cg_make_effects(a, game, k, &r);
    if (logging) {
        cg_log_end(game);              /* this page's changes, appended to the event's one entry ... */
        cg_entry_put(cg_extra_lines);  /* ... with what the comparison of the villagers cannot say (damage) ... */
        if (cg.display_next + 1 < cg.display_count || cg.phase != CG_CHAIN) {
            cg_log_send(game, -1, 0);  /* ... and the entry so far held for the next save (the last page's: final) */
            cg.sent_len[k] = cg.entry_len;
        }
    }
    cg_logged = game;                  /* the game's own bracket around this popup is not a record of its own */
    cg_display_title(k, cg_shown_title, sizeof cg_shown_title);   /* 14: the title in force on this page */
    lstrcpynA(ce_armed_event.title, cg_shown_title, sizeof ce_armed_event.title);   /* the later games draw it */
    cg_compose(&l, cg_shown_title, cg_display(k), r.refused > 0 ? &r : NULL, text, size);
    cg.display_next = k + 1;
}

/* The question's text (the start node, its variant for this run) laid out in pages for the question popup; the
   pages before the last are shown first (through a plain popup, which is never smaller). */
static void cg_question_pages(const ce_adapter *a, int game, cg_pages *pages) {
    static cg_pager w;
    static char raw[CG_RAW_BYTES];
    static char title[CE_TITLE_BYTES];
    ce_layout q = ce_question_layout(a);
    memset(cg_visited, 0, sizeof cg_visited);
    cg_visit(cg_g.start);
    cg_expand(cg_node_text(cg_g.start, game), raw, sizeof raw, CG_EXPAND_AWARD, 0, -1, 0);
    q.check_title = 0;
    w.a = a;
    w.first = &q;
    w.rest = &q;
    cg_title_text(cg_node_title(cg_g.start), title, sizeof title);   /* 14: the start question's own */
    w.title = title;
    w.reserve = cg_answer_room(cg_g.start, &q);
    w.pages = pages;
    w.scroll = cg_scrolls();
    cg_paginate(&w, raw);
}

/* ---- Arming each display ----------------------------------------------------------------------------------- */

/* The next display is a question's own popup (its earlier pages shown, or none): the start's, before the run is
   laid out, or any question's (version 2) once it is; a question asked again after a restore. */
static int cg_next_is_question(void) {
    switch (cg.phase) {
    case CG_QUEUED: return cg.question && cg.pre_pages == 0;
    case CG_ASKED: return 1;
    case CG_CHAIN:
        return cg.display_next < cg.display_count && cg.display_kind[cg.display_next] == CGD_QUESTION;
    default: return 0;
    }
}

/* The node of the question to ask next (or being asked). */
static int cg_question_node(void) {
    if (cg.phase == CG_QUEUED) {
        return cg_g.start;
    }
    if (cg.phase == CG_ASKED) {
        return cg.asking >= 0 && cg.asking < cg.display_count ? cg.display_node[cg.asking] : -1;
    }
    return cg.display_next < cg.display_count ? cg.display_node[cg.display_next] : -1;
}

/* Arm the run's next display in `game`: the island event made due as the purchase makes it (`due`), or only
   remembered (a restore: the save holds the timer).  The question and the event's first popup are the island
   event (counted); every other page a notice.  1 when armed. */
static int cg_arm(int game, int due) {
    int question = cg_next_is_question();
    int notice = cg.phase != CG_QUEUED && !question;
    memset(&cg_stub, 0, sizeof cg_stub);
    cg_stub.game = game;
    /* 14: the title in force on the display armed (a run not laid out yet: its start's, else the event's; the
       first page's own is put in place as it is delivered, cg_show). */
    if (cg.phase == CG_QUEUED) {
        cg_title_text(cg_node_title(cg_g.start), cg_stub.title, sizeof cg_stub.title);
    } else {
        cg_display_title(cg.phase == CG_ASKED ? cg.asking : cg.display_next, cg_stub.title, sizeof cg_stub.title);
    }
    if (question) {
        int b, node = cg_question_node();
        if (node < 0 || node >= cg_g.n_node) {
            return 0;
        }
        /* (Only its own fields: the stub's outcomes stay zero, never written.) */
        cg_choice_stub.enabled = 1;
        cg_choice_stub.featured_record = 0;
        cg_choice_stub.featured_identity = 0;
        for (b = 0; b < 2; ++b) {
            const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + b);
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
        *counted = !cg.question;
        cg_start_run(a, game);         /* the start question's earlier pages, or the event's first popup */
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

/* The question `cg.answers` (asked at display `k`, its node the path's last): both answers' segments walked
   (once: asked again after a restore, the same histories). */
static void cg_walk_answers(const ce_adapter *a, int game, int k) {
    int qi = cg.answers, b;
    int node = cg.display_node[k];
    if (qi < 0 || qi >= CG_MAX_QUESTIONS || node < 0) {
        return;
    }
    if (!cg.seg_walked[qi]) {
        /* The buttons shown (version 6: a choice whose `if` fails is not, and is never walked), then each shown
           choice's segment, in the choices' order. */
        unsigned char map[CG_MAX_ANSWERS];
        int shown = cg_shown_choices(node, game, map);
        memcpy(cg.q_map[qi], map, sizeof map);
        cg.q_shown[qi] = (unsigned char)shown;
        for (b = 0; b < shown; ++b) {
            int choice = map[b];
            const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + choice);
            cg_walk(a, game, (int)cg_u16(c), cg_seg(qi, choice), cg.seg_picks[qi][choice],
                    &cg.seg_pick_count[qi][choice]);
        }
        cg.seg_walked[qi] = 1;
        cg.q_display[qi] = (short)k;
        cg.q_path[qi] = (short)cg.path.nodes;
        cg.q_fx[qi] = (short)cg.path.fx;
        cg.q_picks[qi] = (short)cg.pick_count;
    }
}

/* The question (ce_choice_begin): its own page (the last of its text) into `text`, both answers' segments walked,
   its labels with the names filled in.  Only the start's question is the island event: a later one's count is
   taken back (Island Events Seen counts the event once). */
static void cg_begin_question(int game, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    static char real[CG_PAGE_BYTES];
    ce_layout q;
    int b, k, node, counted;
    if (a == NULL) {
        return;
    }
    cg_display_armed = 0;
    if (cg.phase == CG_QUEUED) {
        cg_start_run(a, game);         /* a start question with no earlier page */
    }
    k = cg.phase == CG_ASKED ? cg.asking : cg.display_next;
    if (k < 0 || k >= cg.display_count || cg.display_kind[k] != CGD_QUESTION) {
        if (size > 0) {
            text[0] = '\0';
        }
        return;
    }
    counted = cg.question && cg.answers == 0;   /* the start's question: the island event itself */
    if (!counted) {
        ce_uncount_notice(game);       /* a later question: a notice's count */
    }
    node = cg.display_node[k];
    if (cg.job_count[k] > 0 && cg.applied_when[k] == 0) {
        /* (Never from a checked graph: a question makes no changes and the ones before it have a page.  Made here
           all the same, rather than lost.) */
        ce_result r;
        int logging = cg_log_begin(game);
        cg.entry_at[k] = cg.entry_len;
        cg_extra_lines[0] = '\0';
        cg_make_effects(a, game, k, &r);
        if (logging) {
            cg_log_end(game);
            cg_entry_put(cg_extra_lines);
            cg_log_send(game, -1, 0);
            cg.sent_len[k] = cg.entry_len;
        }
    }
    q = ce_question_layout(a);
    q.check_title = 0;
    cg_display_title(k, cg_shown_title, sizeof cg_shown_title);   /* 14: the title in force on the question */
    lstrcpynA(ce_asked_title, cg_shown_title, sizeof ce_asked_title);
    cg_compose(&q, cg_shown_title, cg_display(k), NULL, text, size);
    cg_walk_answers(a, game, k);
    {
        unsigned char map[CG_MAX_ANSWERS];
        int shown = cg_buttons(node, cg.answers, map);
        for (b = 0; b < CG_MAX_ANSWERS; ++b) {
            real[0] = '\0';
            if (b < shown) {
                const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + map[b]);
                cg_label_text(a, cg_s(&cg_g, cg_u16(c + 8)), real);
            }
            lstrcpynA(cg_labels[b], real, CG_LABEL_V6);
            if (b < 2) {
                lstrcpynA(ce_choice_store[ce_asked_store].labels[b], real, CE_BUTTON_BYTES);
            }
        }
    }
    cg.phase = CG_ASKED;
    cg.asking = k;
    cg.display_next = k + 1;
    cg_answer_fresh_game = 0;
    cg_logged = game;                  /* the question's own popup: the entry's, never a record of its own */
    cg_dirty = 1;
}

/* Choice `choice` of the asked question added to the run: the path back to the question, that choice's segment
   on it, its pages laid out after the question's.  0 when nothing is asked. */
static int cg_take_answer(const ce_adapter *a, int game, int choice) {
    int qi = cg.answers;
    if (cg.phase != CG_ASKED || qi < 0 || qi >= CG_MAX_QUESTIONS || !cg.seg_walked[qi]) {
        return 0;
    }
    cg_displays_cut(cg.q_display[qi] + 1);
    cg.path.nodes = cg.q_path[qi];
    cg.path.fx = cg.q_fx[qi];
    cg.pick_count = cg.q_picks[qi];
    cg_path_add(cg_seg(qi, choice), cg.seg_picks[qi][choice], cg.seg_pick_count[qi][choice]);
    cg_layout_from(a, game, cg.q_path[qi], 1);
    return 1;
}

/* The answer (ce_choice_resolve): that button's segment laid out in pages, and its first page shown -- with the
   effects that page makes (the rest wait for their own pages).  The log entry gets the button clicked: its
   header's "Choice:" line for the start's question, another "Choice:" line for each later one. */
static int cg_resolve(int game, int button, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    static char label[CG_LABEL_V6];
    unsigned char map[CG_MAX_ANSWERS];
    int qi = cg.answers, node, first, choice;
    if (a == NULL || button < 0 || button >= CG_MAX_ANSWERS || qi >= CG_MAX_QUESTIONS || cg.asking < 0) {
        return 0;
    }
    node = cg.display_node[cg.asking];
    if (node < 0 || button >= cg_buttons(node, qi, map)) {
        return 0;
    }
    choice = map[button];              /* the buttons close up over a choice not shown */
    if (!cg_take_answer(a, game, choice)) {
        return 0;
    }
    first = cg.q_display[qi] + 1;
    cg.answer[qi] = (unsigned char)choice;
    cg.answers = qi + 1;
    cg.choice = button;
    {
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + choice);
        char line[CG_LABEL_V6 + 16];
        cg_label_text(a, cg_s(&cg_g, cg_u16(c + 8)), label);
        cg.q_entry[qi] = cg.entry_len;
        if (cg.entry_head == 0) {
            cg_entry_start(label);     /* the title and the start question's answer */
            cg.q_entry[qi] = 0;
        } else {
            wsprintfA(line, "  Choice: %s\n", label);
            cg_entry_put(line);
        }
    }
    cg.phase = CG_CHAIN;
    cg.asking = -1;
    cg.display_next = first;
    cg_answer_fresh_game = 0;
    if (cg_fresh_after(node, qi) && first < cg.display_count) {
        /* G1: the question's popup closes at the click (cg_answer_closes); the answer's first page is the next
           display, a popup of its own, with its effects. */
        cg_answer_fresh_game = game;
        if (size > 0) {
            text[0] = '\0';
        }
        cg_dirty = 1;
        return 1;
    }
    if (first < cg.display_count) {
        cg_show(a, game, first, text, size);
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
    static cg_history keep_path;
    static char shown[CE_TITLE_BYTES];
    const ce_adapter *a = ce_adapter_for(game);
    ce_layout first;
    ce_result most;
    unsigned char map[CG_MAX_ANSWERS];
    int lines = 0, count, used, jobs, k, picks;
    if (a == NULL || button < 0 || cg.phase != CG_ASKED || cg.asking < 0
        || button >= cg_buttons(cg.display_node[cg.asking], cg.answers, map)) {
        return 0;
    }
    if (cg_fresh_after(cg.display_node[cg.asking], cg.answers)) {
        if (size > 0) {
            out[0] = '\0';            /* G1: the answer's page is a popup of its own, never this one's */
        }
        return 0;
    }
    keep_path = cg.path;
    count = cg.display_count;
    used = cg.display_used;
    jobs = cg.jobs_used;
    picks = cg.pick_count;
    if (cg_take_answer(a, game, map[button])) {
        k = cg.q_display[cg.answers] + 1;
        if (k < cg.display_count) {
            first = ce_result_layout(a);
            memset(&most, 0, sizeof most);
            most.refused = 999;
            cg_display_title(k, shown, sizeof shown);
            cg_compose(&first, shown, cg_display(k), cg.display_villager[k] && cg.job_count[k] > 0 ? &most : NULL,
                       out, size);
            lines = ce_text_lines(out);
        }
    }
    cg.path = keep_path;
    cg.display_count = count;
    cg.display_used = used;
    cg.jobs_used = jobs;
    cg.pick_count = picks;
    return lines;
}

/* The question popup on screen should close at the answer's click (G1: its page is a popup of its own). */
static int cg_answer_closes(int game) {
    return game != 0 && cg_answer_fresh_game == game;
}

/* ce_choice_featured: the subject, the villager the question is about. */
static int cg_featured(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    int r, i;
    if (a == NULL || !cg_prepare(game)) {
        return -1;
    }
    /* The first villager role bound (version 6: the first role may be a stranger, G7) ... */
    for (r = 0; r < cg_g.n_role; ++r) {
        if (cg_role_at(&cg_g, r)[0] == CG_ROLE_VILLAGER && cg_villager(a, r) != NULL) {
            return cg.record[r];
        }
    }
    /* ... else, with no villager in the event, the first living villager the game lists (the later three games'
       question popup shows someone; no roll is taken). */
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *rec = a->record(i);
        if (rec != NULL && a->listed(rec) && !cg_heathen(game, rec)
            && (a->featurable == NULL || a->featurable(rec))) {
            return i;
        }
    }
    return -1;
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
    if (cg_g.version >= 6) {
        const ce_adapter *a = ce_adapter_for(game);
        if (spec[8] != 0) {
            wsprintfA(part, ", %d or younger", (int)spec[8]);
            lstrcatA(out, part);
        }
        if (cg_u16(spec + 10) != CG_NONE && a != NULL && cg_skills_known(a, cg_s(&cg_g, cg_u16(spec + 10)))) {
            wsprintfA(part, ", %s %d or more", cg_s(&cg_g, cg_u16(spec + 10)), (int)spec[12]);
            if (lstrlenA(out) + lstrlenA(part) < size) {
                lstrcatA(out, part);
            }
        }
        if (spec[9] >= 1 && spec[9] <= 3) {
            static const char *const WHO[4] = { "", ", the Golden Child", ", the Tribal Chief", ", a nursing parent" };
            lstrcatA(out, WHO[spec[9]]);
        }
        if (spec[1] & CG_ROLE_PROTECTED) {
            lstrcatA(out, ", not a protected villager");
        }
    }
}

/* ---- The installed patches (v1.35.97) ----------------------------------------------------------------------

   The patcher writes the ids of the patches it installed into this game -- every fun patch, the game build's own id
   (a "#" line is a note) -- one per line, into "<game folder>\Virtual Villagers Fun Patcher Files\VVFP Installed
   Patches.txt" (src/vv_fun_patcher.py _write_installed_patches), at every patch, so the list always describes the
   installed build (a re-patch rewrites it; an unpatched game has none).  It is read once a run: the patches never
   change while the game runs.  An event's patch id is its short name: the line itself, or the line without its
   "vv<N>_" game prefix in game N ("guardians_of_isola" matches "vv5_guardians_of_isola..."; a build id's "_rewrite"
   ending too). */
#define CG_INSTALLED_LEAF "VVFP Installed Patches.txt"
#define CG_INSTALLED_BYTES 16384
static int cg_installed_state = -1;    /* -1 not read yet, 0 no list (an older patch), 1 read */
static char cg_installed[CG_INSTALLED_BYTES];

static void cg_installed_load(void) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    HANDLE file;
    DWORD got = 0;
    if (cg_installed_state >= 0) {
        return;
    }
    cg_installed_state = 0;
    cg_installed[0] = '\0';
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, CG_INSTALLED_LEAF) == 0) {
        return;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (ReadFile(file, cg_installed, CG_INSTALLED_BYTES - 1, &got, NULL)) {
        cg_installed[got] = '\0';
        cg_installed_state = 1;
    }
    CloseHandle(file);
}

/* Whether the short name `id` names an installed patch of `game` (cg_installed_state 1). */
static int cg_installed_has(int game, const char *id) {
    const char *p = cg_installed;
    int n = lstrlenA(id);
    while (*p != '\0') {
        const char *end = p, *at = p;
        int len;
        while (*end != '\0' && *end != '\n' && *end != '\r') {
            ++end;
        }
        if (*at != '#') {
            if (end - at > 4 && at[0] == 'v' && at[1] == 'v' && at[2] == (char)('0' + game) && at[3] == '_') {
                at += 4;                /* the game's prefix */
            }
            len = (int)(end - at);
            if (len >= n && memcmp(at, id, (size_t)n) == 0
                && (len == n || (len == n + 8 && memcmp(at + n, "_rewrite", 8) == 0))) {
                return 1;
            }
        }
        p = end;
        while (*p == '\n' || *p == '\r') {
            ++p;
        }
    }
    return 0;
}

/* Whether the patches named by the event are on: the installed patches' list when the patcher wrote one; without
   it (a game patched by an older patcher) only Guardians of Isola's rewrite (New Believers), seen in the game's own
   text as the Faith popup sees it -- which is also asked with the list, as before. */
static unsigned int cg_patches_on(int game) {
    unsigned int on = 0;
    int i;
#ifdef VVFP_TEST
    if (test_graph_patches >= 0) {
        return (unsigned int)test_graph_patches;
    }
#endif
    cg_installed_load();
    for (i = 0; i < cg_g.n_patch; ++i) {
        const char *id = cg_s(&cg_g, cg_u16(cg_g.d + cg_g.o_patch + 2u * (unsigned int)i));
        if ((cg_installed_state == 1 && cg_installed_has(game, id))
            || (game == 5 && lstrcmpA(id, "guardians_of_isola") == 0 && faith_notice_left_the_tribe())) {
            on |= 1u << i;
        }
    }
    return on;
}

/* The roles a refusal planned with their requirements dropped (CG_CAST_PREFER), for the run cg_queue makes. */
static unsigned int cg_plan_relaxed;

/* VERSION 6, STRICT (the rare roll, Pick Island Event): the event's own requirement -- its condition beyond the
   puzzles (the header's `all`, docs/event-collection/cie-v6-binary.md 1) with the roles it will bind, and at least
   `min_eligible` villagers who could take one of its villager roles. */
static int cg_requirement_holds(int game, unsigned int needed) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned int keep_bound = cg.bound, keep_patches = cg.patches;
    int keep_drawn = cg.aliases_drawn, holds = 1, k;
    if (a == NULL) {
        return 0;
    }
    if (cg_g.req_cond != (int)CG_NONE) {
        const unsigned char *all = cg_cond_at(&cg_g, cg_g.req_cond);
        cg.bound = needed;
        cg.patches = cg_patches_on(game);
        cg.aliases_drawn = 0;
        memset(cg_visited, 0, sizeof cg_visited);
        for (k = 0; k < all[1] && holds; ++k) {
            int c = (int)cg_u16(all + 2) + k;
            if (cg_cond_at(&cg_g, c)[0] != CGC_PUZZLE) {
                holds = cg_holds_cond(c, game, 0);
            }
        }
        cg.bound = keep_bound;
        cg.patches = keep_patches;
        cg.aliases_drawn = keep_drawn;
    }
    if (holds && cg_g.min_eligible > 0) {
        int i, n = 0, r;
        for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
            for (r = 0; r < cg_g.n_role; ++r) {
                if ((needed & (1u << r)) && cg_eligible(a, game, r, i)) {
                    ++n;
                    break;
                }
            }
        }
        holds = n >= cg_g.min_eligible;
    }
    return holds;
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
    if (cg_g.req_cond != (int)CG_NONE) {
        /* Version 3: "only after a puzzle is solved" -- every puzzle the event lists for this game. */
        const unsigned char *all = cg_cond_at(&cg_g, cg_g.req_cond);
        int k;
        for (k = 0; k < all[1]; ++k) {
            const unsigned char *c = cg_cond_at(&cg_g, (int)cg_u16(all + 2) + k);
            if (c[0] == CGC_PUZZLE && (int)cg_u16(c + 4) == game && !cg_puzzle_solved(game, cg_s(&cg_g, cg_u16(c + 2)))) {
                wsprintfA(reason, "\"%s\" can only happen once %s is solved. Nothing has been queued.",
                          cg_s(&cg_g, (unsigned int)cg_g.title), cg_s(&cg_g, cg_u16(c + 2)));
                return reason;
            }
        }
    }
    memset(used, 0, sizeof used);
    cg_try_reset();
    needed = cg_needed();
    cg_relax_mask = 0;
    if (cg_g.version >= 6 && cg_cast_now == CG_CAST_STRICT && !cg_requirement_holds(game, needed)) {
        wsprintfA(reason, "\"%s\" can not happen in this village right now. Nothing has been queued.",
                  cg_s(&cg_g, (unsigned int)cg_g.title));
        return reason;
    }
    if (cg_g.version >= 6 && cg_cast_now == CG_CAST_PREFER) {
        /* Bought: a requirement nobody meets is dropped, never the purchase (only "no villager at all"). */
        if (!cg_plan_cast(a, game, needed, used)) {
            return "The village does not have enough different villagers for the event's roles now. "
                   "Nothing has been queued.";
        }
    }
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
        if (cg_has_gaps()) {
            /* Version 3: no villagers fit the roles together (an age gap). */
            int q;
            for (q = 0; q < cg_g.n_role; ++q) {
                const unsigned char *qs = cg_role_at(&cg_g, q);
                if (qs[6] != 0 && (needed & (1u << q)) && (needed & (1u << (qs[6] - 1)))) {
                    wsprintfA(reason, "No two villagers in the village can be the event's %s and %s now: they must be "
                              "at most %d years apart. Nothing has been queued.",
                              cg_s(&cg_g, cg_u16(cg_role_at(&cg_g, qs[6] - 1) + 4)), cg_s(&cg_g, cg_u16(qs + 4)),
                              (int)qs[7]);
                    return reason;
                }
            }
        }
        return "The village does not have enough different villagers for the event's roles now. "
               "Nothing has been queued.";
    }
    *planned = needed;
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        cg_try_reset();
        if (spec[0] == 0 && (spec[1] & CG_ROLE_OPTIONAL) && cg_matchable(a, game, *planned | (1u << r), used)) {
            *planned |= 1u << r;       /* an optional role the village can fill now */
        }
    }
    cg_plan_relaxed = cg_relax_mask;
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

static int cg_origin_now = CG_ORIGIN_PURCHASE;   /* the next cg_queue's origin */

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
    cg.asking = -1;
    cg.origin = cg_origin_now;
    cg.cast_mode = cg_cast_now;
    cg.relaxed = cg_plan_relaxed;
    {
        int r;
        for (r = 0; r < CG_MAX_ROLES; ++r) {
            cg.alias[r] = -1;
        }
    }
    lstrcpynA(cg.title, cg_s(&cg_g, (unsigned int)cg_g.title), sizeof cg.title);
    if (cg.question) {
        static cg_pages pages;
        unsigned int keep = cg.bound;
        cg.bound = planned;            /* the conditions see the roles it will bind */
        if (cg_g.version >= 6) {
            /* The start question's words are laid out now (its pages before its popup): its aliases and its pools
               are drawn here, the walk's first draws (the binding's rolls come after them, at the delivery). */
            cg_draw_aliases(a, planned);
            memset(cg_visited, 0, sizeof cg_visited);
            cg_visit(cg_g.start);
            cg_node_pools(a, game, cg_g.start);
            cg.start_picks = cg.pick_count;
        }
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
#define CG_FILE_VERSION 4u                 /* 2: the run keeps its path and every question's answers; 3: and a
                                              question's third and fourth answers (cg_state.seg_more); 4 (format
                                              version 6): answers five to seven, the pool picks, the aliases, each
                                              question's buttons, the origin and the cast */
#define CG_FILE_V2_STATE ((unsigned int)offsetof(cg_state, seg_more))   /* a version 2 file's state bytes */
#define CG_FILE_V3_STATE ((unsigned int)offsetof(cg_state, seg_v6))     /* a version 3 file's */

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

/* The state's bytes a run file of the header's version holds: version 4 the whole state, version 3 everything before
   version 4's fields, version 2 everything before the third and fourth answers' segments (read with what it lacks
   empty: cg_file_upgrade); 0 for any other. */
static unsigned int cg_file_state_bytes(void) {
    return cg_head.version == CG_FILE_VERSION ? (unsigned int)sizeof(cg_state)
         : cg_head.version == 3u ? CG_FILE_V3_STATE
         : cg_head.version == 2u ? CG_FILE_V2_STATE : 0u;
}

/* A run read from an older file: what it lacks as a run of its own version had it (no alias drawn, every choice
   shown as its version shows them, the cast strict). */
static void cg_file_upgrade(cg_state *st) {
    int r;
    if (cg_head.version >= CG_FILE_VERSION) {
        return;
    }
    for (r = 0; r < CG_MAX_ROLES; ++r) {
        st->alias[r] = -1;
    }
    st->aliases_drawn = 1;
    st->origin = CG_ORIGIN_PURCHASE;
    st->cast_mode = CG_CAST_STRICT;
}

static int cg_file_state_ok(void) {
    return cg_file_state_bytes() != 0u && cg_head.state_bytes == cg_file_state_bytes();
}

#ifdef VVFP_TEST
static unsigned char cg_test_file[sizeof(cg_file_head) + sizeof(cg_state) + CG_MAX_FILE];
static unsigned int cg_test_size;

static int cg_file_read(int game, int slot) {
    (void)game;
    (void)slot;
    unsigned int state;
    if (cg_test_size < sizeof cg_head) {
        return 0;
    }
    memcpy(&cg_head, cg_test_file, sizeof cg_head);
    state = cg_file_state_bytes();
    memset(&cg_read_state, 0, sizeof cg_read_state);
    if (state == 0u || cg_head.graph_bytes > CG_MAX_FILE || cg_test_size != sizeof cg_head + state + cg_head.graph_bytes) {
        return 0;
    }
    memcpy(&cg_read_state, cg_test_file + sizeof cg_head, state);
    memcpy(cg_read_buf, cg_test_file + sizeof cg_head + state, cg_head.graph_bytes);
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
    memset(&cg_read_state, 0, sizeof cg_read_state);
    ok = ReadFile(h, &cg_head, sizeof cg_head, &got, NULL) && got == sizeof cg_head && cg_file_state_bytes() != 0u
        && ReadFile(h, &cg_read_state, cg_file_state_bytes(), &more, NULL) && more == cg_file_state_bytes()
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
    if (cg_head.magic != CG_FILE_MAGIC || !cg_file_state_ok() || cg_head.game != (unsigned int)game
        || cg_head.slot != (unsigned int)slot
        || cg_read_state.game != game || cg_read_state.phase == CG_IDLE
        || !cg_load(&check, cg_read_buf, cg_head.graph_bytes) || !sq_same_village(cg_head.roster, roster)) {
        return;
    }
    if (!sq_save_time(game, slot, &saved) || cg_read_state.when > saved) {
        cg_file_remove(game, slot);    /* newer than the save: the save never held it */
        return;
    }
    cg_file_upgrade(&cg_read_state);
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
            /* The first page the save lacks.  Is it an answer's first page?  Then that answer is not in the save
               either: the question is asked again.  Every question answered after it is taken back too (its pages
               are laid out again from its answer when it is answered again: the same histories). */
            int again = cg.display_kind[rewind] == CGD_RESULT ? rewind - 1 : -1;
            int qi;
            cg.gone = cg.gone_at[rewind];
            memcpy(cg.identity, cg.identity_at[rewind], sizeof cg.identity);
            for (qi = 0; qi < cg.answers && cg.q_display[qi] < (again >= 0 ? again : rewind); ++qi) {
            }
            /* The entry continues from that page: its own lines are taken back, made again as it is shown (or,
               for a question asked again, from before its "Choice:" line). */
            cg.entry_len = again >= 0 && qi < cg.answers ? cg.q_entry[qi] : cg.entry_at[rewind];
            if (cg.entry_len == 0) {
                cg.entry_head = 0;
            }
            cg.entry[cg.entry_len] = '\0';
            for (k = rewind; k < cg.display_count; ++k) {
                cg.applied_when[k] = 0;
                cg.sent_len[k] = 0;
            }
            if (qi < cg.answers) {
                cg_displays_cut(cg.q_display[qi] + 1);
                cg.path.nodes = cg.q_path[qi];
                cg.path.fx = cg.q_fx[qi];
                cg.pick_count = cg.q_picks[qi];
                cg.answers = qi;
            }
            if (again >= 0 && cg.display_kind[again] == CGD_QUESTION) {
                cg.phase = CG_ASKED;
                cg.asking = again;
                cg.display_next = again + 1;
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
    cg_cast_now = CG_CAST_PREFER;      /* bought: a requirement nobody meets is dropped, never the purchase */
    cg_origin_now = CG_ORIGIN_PURCHASE;
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
    cg_cast_now = CG_CAST_PREFER;
    cg_origin_now = CG_ORIGIN_PURCHASE;
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

/* ---- Queueing from the other paths (the rare roll, Pick Island Event: story_collection.inc,
   story_more_events.inc) ------------------------------------------------------------------------------------- */

static char cg_queue_why[400];

/* Why the last cg_queue_origin did not queue its event ("" when it did). */
static const char *cg_queue_refusal(void) {
    return cg_queue_why;
}

/* Queue the .cieg `file` (`size` bytes) in `game` with `origin` (CG_ORIGIN_PURCHASE / PICK / NATURAL) and its cast
   (CG_CAST_STRICT: every requirement and the event's own requirement must hold; CG_CAST_PREFER: a requirement
   nobody meets is dropped).  Nothing is charged here.  1 when queued; 0 with the reason in cg_queue_refusal() --
   among them: another branching event is still running (one at a time), the file is refused, the village cannot
   fill the roles. */
static int cg_queue_origin(int game, const unsigned char *file, unsigned size, int origin, int cast_mode) {
    unsigned int planned = 0;
    const char *refusal;
    cg_queue_why[0] = '\0';
    if (game < 1 || game > 5 || file == NULL || size == 0u || size > CG_MAX_FILE) {
        lstrcpynA(cg_queue_why, "The event file can not be read.", sizeof cg_queue_why);
        return 0;
    }
    if (cg.phase != CG_IDLE && cg.phase != CG_DONE) {
        lstrcpynA(cg_queue_why, "Another branching island event is still running.", sizeof cg_queue_why);
        return 0;
    }
    if (file != cg_bytes) {
        memcpy(cg_bytes, file, size);
    }
    cg_bytes_size = size;
    if (!cg_load(&cg_g, cg_bytes, size)) {
        wsprintfA(cg_queue_why, "That event can not be used: %s.", cg_why);
        cg_bytes_size = 0;
        return 0;
    }
    cg_cast_now = cast_mode == CG_CAST_PREFER ? CG_CAST_PREFER : CG_CAST_STRICT;
    cg_origin_now = origin;
    refusal = cg_refusal(game, &planned);
    if (refusal != NULL) {
        lstrcpynA(cg_queue_why, refusal, sizeof cg_queue_why);
        cg_origin_now = CG_ORIGIN_PURCHASE;
        return 0;
    }
    if (!cg_queue(game, planned, 1)) {
        lstrcpynA(cg_queue_why, "The event can not happen right now.", sizeof cg_queue_why);
        cg_origin_now = CG_ORIGIN_PURCHASE;
        return 0;
    }
    cg_origin_now = CG_ORIGIN_PURCHASE;
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
    /* due's bit 8: the cast is strict (the rare roll / Pick), else prefer (a purchase); bits 9-10 the origin. */
    cg_cast_now = (due & 0x100) ? CG_CAST_STRICT : CG_CAST_PREFER;
    cg_origin_now = (due >> 9) & 3;
    due &= 0xFF;
    refusal = cg_refusal(game, &planned);
    if (refusal != NULL) {
        cg_origin_now = CG_ORIGIN_PURCHASE;
        return refusal;
    }
    /* due 0: armed without making the island event due (the engine tests drive the entry points). */
    refusal = cg_queue(game, planned, due) ? NULL : "not armed";
    cg_origin_now = CG_ORIGIN_PURCHASE;
    return refusal;
}

/* Record `record` starts nursing just before the next walk (after the roles are cast), -1 none. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphNurseAtWalk(int record) {
    test_graph_nurse = record;
}

/* The run file's layout: out[0] a version 3 file's state bytes, [1] the header's bytes, [2] the whole state's. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphFileLayout(int *out) {
    out[0] = (int)CG_FILE_V3_STATE;
    out[1] = (int)sizeof(cg_file_head);
    out[2] = (int)sizeof(cg_state);
}

/* cg_queue_origin as story_collection.inc calls it: 1 queued, else 0 with the reason copied to `why` (200 bytes). */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphQueueOrigin(int game, const unsigned char *data,
                                                                    unsigned int size, int origin, int cast_mode,
                                                                    char *why) {
    int ok;
    install_state[game] = 1;
    ok = cg_queue_origin(game, data, size, origin, cast_mode);
    if (why != NULL) {
        lstrcpynA(why, cg_queue_refusal(), 200);
    }
    return ok;
}

/* The version 6 run: out[0] picks, then (pool, instance, item) for each of the first `cap` picks; out[1 + 3 cap ..]:
   the aliases' members (16), the relaxed roles, the cast, the origin, the asked question's buttons and its map (7),
   the path's effect count and its rolls (a, b; at most 64).  The count of ints written. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphPicks(int *out, int cap) {
    int i, o = 1;
    out[0] = cg.pick_count;
    for (i = 0; i < cap; ++i) {
        out[o++] = i < cg.pick_count ? cg.picks[i].pool : -1;
        out[o++] = i < cg.pick_count ? cg.picks[i].instance : -1;
        out[o++] = i < cg.pick_count ? (cg.picks[i].item == CG_NONE ? -1 : cg.picks[i].item) : -1;
    }
    for (i = 0; i < CG_MAX_ROLES; ++i) {
        out[o++] = cg.alias[i];
    }
    out[o++] = (int)cg.relaxed;
    out[o++] = cg.cast_mode;
    out[o++] = cg.origin;
    {
        unsigned char map[CG_MAX_ANSWERS];
        int n = cg.phase == CG_ASKED && cg.asking >= 0 ? cg_buttons(cg.display_node[cg.asking], cg.answers, map) : 0;
        out[o++] = n;
        for (i = 0; i < CG_MAX_ANSWERS; ++i) {
            out[o++] = i < n ? map[i] : -1;
        }
    }
    out[o++] = cg.path.fx;             /* then the path's effect rolls (a, b), at most 64 */
    for (i = 0; i < cg.path.fx && i < 64 && i < CG_MAX_FX; ++i) {
        out[o++] = cg.path.fx_a[i];
        out[o++] = cg.path.fx_b[i];
    }
    return o;
}

/* The Unicode Text companion seen as loaded (1) or not (0), -1 as it is; the finished structures for "damage"
   (bit k; -1 as the game says: then nothing is recorded), and what the last damage did into `damaged`
   (SD_MAX_STRUCTURES ints, each structure's loss). */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphFacts(int unicode, int structures, int *damaged) {
    int k;
    test_graph_unicode = unicode;
    if (structures != -2) {
        test_graph_structures = structures;
        memset(test_graph_damaged, 0, sizeof test_graph_damaged);
    }
    if (damaged != NULL) {
        for (k = 0; k < SD_MAX_STRUCTURES; ++k) {
            damaged[k] = test_graph_damaged[k];
        }
    }
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

/* Scrolling Popups installed (1) or not (0) for the layout of the pages, -1 = as its companion says. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphScroll(int on) {
    test_graph_scroll = on;
}

/* The installed patches' list as the patcher would write it (NULL: none, as an older patch), then the patches the
   loaded graph names that are on in `game` (cg_patches_on), as a bit mask. */
__declspec(dllexport) unsigned int __stdcall VvfpStoryProbeInstalledPatches(int game, const char *text) {
    test_graph_patches = -1;
    cg_installed_state = text != NULL ? 1 : 0;
    lstrcpynA(cg_installed, text != NULL ? text : "", CG_INSTALLED_BYTES);
    return cg_patches_on(game);
}

/* The puzzles solved for the graph's checks (bit = the adapter's puzzle index; -1 = as the game says). */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphPuzzles(int solved) {
    test_graph_puzzles = solved;
}

/* The run: out[0] phase, [1] display_next, [2] display_count, [3] display armed, [4] choice, [5] bound roles,
   [6] planned, [7..10] the first four roles' records, [11] pre_pages, [12] the path's nodes, [13] answers,
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
    out[12] = cg.path.nodes;
    out[13] = cg.answers;
    out[14] = test_graph_told_count;
}

/* The path's nodes (which 0) or the asked question's answer `which - 1` segment, into out (at most `cap`); the
   count. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphPath(int which, int *out, int cap) {
    int i;
    const cg_history *h = which <= 0 || cg.answers >= CG_MAX_QUESTIONS ? &cg.path
                          : cg_seg(cg.answers, which - 1 < CG_MAX_ANSWERS ? which - 1 : CG_MAX_ANSWERS - 1);
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

/* Display `k`'s popup title (cie-v6-binary.md 14), or NULL. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphTitle(int k) {
    static char title[CE_TITLE_BYTES + 64];
    if (k < 0 || k >= cg.display_count) {
        return NULL;
    }
    cg_display_title(k, title, sizeof title);
    return title;
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
    test_graph_structures = -1;
    test_graph_unicode = -1;
    test_graph_nurse = -1;
}
#endif
