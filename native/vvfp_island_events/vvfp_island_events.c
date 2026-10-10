/* VVFP Island Events -- every change an island event makes to a villager,
   logged (all five games).

   The owner, 2026-10-08: one of their A New Home children's head changed in
   an island event ("the red potion") and nothing recorded it, so the Family
   Tree Maker took the child for a villager who had left; "all island event
   changes should be logged. Some events make villagers die, disappear,
   change skills, head etc".

   HOW.  Each game applies an event's effects in a few known routines (the
   SITES table, one row per call site, verified byte for byte before anything
   is installed).  Each site's `call rel32` is pointed at a thunk that copies
   every villager the game holds, runs the game's own routine unchanged, and
   compares: every field that differs is one line, "  <Field>: <old> ->
   <new>", in one numbered "Island event <n>" record per villager, under the
   event's title, in the Island Events log (the Parentage Export DLL's
   WriteVillageRecord, kind 8: held until the next save, like every record
   the save has not caught up with).  A head or body change is also written
   as an "Appearance changed" record, so the Family Tree Maker knows the two
   looks are one villager.  A villager the event removes ("Gone") is named
   from the copy taken before it.

   Nothing in the game changes: the thunk calls the very routine the site
   called, with the same registers and stack, and returns what it returned.
   A site whose bytes are not the stock ones is left alone, and so is every
   site when any one of them differs (the install is all or nothing per
   game).  Without the Parentage Export DLL (no log patch) nothing is
   written. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "../shared/patcher_files.h"

#define GAMES 5
#define KIND_ISLAND_EVENT 8               /* parentage_export.c */
#define KIND_APPEARANCE 7
#define MAX_VILLAGERS 256
#define TITLE_MAX 96
#define TEXT_MAX 96                       /* the item the popup names (item_of) */

/* ---- What is compared ---------------------------------------------------- */

enum {
    F_INT,                                /* a number */
    F_FLOAT,                              /* a number kept as a float (the later games' skills) */
    F_TEXT,                               /* a name, `size` bytes */
    F_FLAG,                               /* an int: 0 "no", anything else "yes" */
    F_BYTE_FLAG,                          /* a byte: 0 "no", anything else "yes" */
    F_SEX12,                              /* 1 Male, 2 Female (A New Home, The Lost Children) */
    F_SEX01,                              /* 0 Male, 1 Female (the later games) */
    F_LIKES, F_DISLIKES,                  /* `size` word indexes, as the logs print them */
    F_BABIES                              /* A New Home's and The Lost Children's litter: 0 one baby,
                                             2 twins, 3 triplets while pregnant (their deliveries
                                             0x42EF39 / 0x43BED6: any non-zero a second baby, 3 a
                                             third); `size` is the Pregnant field's offset */
};
struct field {
    const char *label;                    /* "Head", "Farming", ... */
    unsigned int offset;                  /* from the villager's record */
    int type;
    unsigned int size;                    /* F_TEXT: bytes; F_LIKES / F_DISLIKES: slots; F_BABIES: Pregnant */
    int conception;                       /* written by the conception: printed whole when one starts */
};

/* How a game's villagers are found and read. */
struct game_layout {
    int (*enumerate)(unsigned char **records, int capacity);   /* every present villager's record */
    unsigned int copy_size;               /* bytes copied per villager */
    unsigned int pad;                     /* the record's stride: room after the last copy */
    unsigned int name;                    /* name offset in the record */
    unsigned int head, body;
    const struct field *fields;
    int field_count;
    /* A game that keeps no father on the mother (A New Home): the expected
       father of the pregnancy `record` carries, from where the conception
       recorded him -- name, head and body (-1 when not recorded); 0 when
       there is none to tell.  NULL where the fields above hold him. */
    int (*expected_father)(const unsigned char *record, char *name, size_t size, int *head, int *body);
};

static int g_game;
static const struct game_layout *g_layout;

/* ---- The record writer (VVFP Parentage Export.dll) ---------------------- */

typedef int (__stdcall *write_village_record_fn)(int, int, const void *, int, const char *, const char *, int);
static write_village_record_fn g_write;

static write_village_record_fn writer(void) {
    static int looked;
    if (!looked) {
        HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
        looked = 1;
        if (module != NULL) {
            g_write = (write_village_record_fn)GetProcAddress(module, "WriteVillageRecord");
        }
    }
    return g_write;
}

/* ---- The snapshot ---------------------------------------------------------- */

struct snapshot {
    int count;
    unsigned char *where[MAX_VILLAGERS];  /* each villager's live record */
    unsigned char *copy;                  /* count * copy_size bytes */
    char title[TITLE_MAX];
    char text[TEXT_MAX];                  /* says which kind: "an oily red vial", "a large crate" */
};

/* The outermost watched call's copy (see before_call). */
static struct snapshot g_snaps[1];
static char g_choice[TITLE_MAX];         /* the answer clicked, when there was one */
static char g_answer[TITLE_MAX];         /* the last two-choice answer clicked (struct site's answer) */
static unsigned int g_answer_self;       /* ...in this dialog */
static int g_answering;                  /* the outermost call is an answer click */
static int g_depth;

static int readable(const void *at, size_t size) {
    MEMORY_BASIC_INFORMATION info;
    if (at == NULL || VirtualQuery(at, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
        return 0;
    }
    return (const unsigned char *)at + size <= (const unsigned char *)info.BaseAddress + info.RegionSize;
}

static void take(struct snapshot *s) {
    int i;
    s->count = g_layout->enumerate(s->where, MAX_VILLAGERS);
    if (s->copy == NULL) {
        /* A removed villager's copy is handed to the log writer as a record,
           which it checks is readable for a whole stride: hence the pad. */
        s->copy = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)MAX_VILLAGERS * g_layout->copy_size + g_layout->pad,
                                                MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    }
    if (s->copy == NULL) {
        s->count = 0;
        return;
    }
    for (i = 0; i < s->count; ++i) {
        if (readable(s->where[i], g_layout->copy_size)) {
            memcpy(s->copy + (size_t)i * g_layout->copy_size, s->where[i], g_layout->copy_size);
        } else {
            s->where[i] = NULL;
        }
    }
}

typedef int (__stdcall *preference_text_fn)(int, const void *, int, char *, int);

static void field_text(const struct field *f, const unsigned char *record, char *out, size_t size) {
    static preference_text_fn preferences;
    static int looked;
    int value = *(const int *)(record + f->offset);
    out[0] = '\0';
    switch (f->type) {
    case F_TEXT: {
        size_t n = 0;
        while (n < f->size && n + 1 < size && record[f->offset + n] != 0) {
            out[n] = (char)record[f->offset + n];
            ++n;
        }
        out[n] = '\0';
        break;
    }
    case F_FLOAT:
        _snprintf(out, size, "%.0f", (double)*(const float *)(record + f->offset));
        break;
    case F_FLAG:
        _snprintf(out, size, "%s", value != 0 ? "yes" : "no");
        break;
    case F_BYTE_FLAG:
        _snprintf(out, size, "%s", record[f->offset] != 0 ? "yes" : "no");
        break;
    case F_SEX12:
        _snprintf(out, size, "%s", value == 1 ? "Male" : value == 2 ? "Female" : "(unknown)");
        break;
    case F_BABIES:
        /* The babies the delivery will make, as the later games store them
           (1, 2 or 3); not pregnant, the field as it is. */
        if (*(const int *)(record + f->size) != 0) {
            value = value == 3 ? 3 : value != 0 ? 2 : 1;
        }
        _snprintf(out, size, "%d", value);
        break;
    case F_SEX01:
        _snprintf(out, size, "%s", value == 0 ? "Male" : value == 1 ? "Female" : "(unknown)");
        break;
    case F_LIKES:
    case F_DISLIKES:
        if (!looked) {
            HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
            looked = 1;
            preferences = module != NULL ? (preference_text_fn)GetProcAddress(module, "VillagePreferenceText") : NULL;
        }
        if (preferences == NULL || !preferences(g_game, record, f->type == F_DISLIKES, out, (int)size)) {
            _snprintf(out, size, "(changed)");
        }
        break;
    default:
        _snprintf(out, size, "%d", value);
        break;
    }
    out[size - 1] = '\0';
}

static int field_same(const struct field *f, const unsigned char *a, const unsigned char *b) {
    unsigned int n = f->type == F_TEXT ? f->size
        : f->type == F_LIKES || f->type == F_DISLIKES ? f->size * 4
        : f->type == F_BYTE_FLAG ? 1 : 4;
    if (f->type == F_FLAG) {
        return (*(const int *)(a + f->offset) != 0) == (*(const int *)(b + f->offset) != 0);
    }
    if (f->type == F_BABIES) {
        char x[16], y[16];
        field_text(f, a, x, sizeof x);
        field_text(f, b, y, sizeof y);
        return strcmp(x, y) == 0;
    }
    if (f->type == F_TEXT) {
        /* the text, not what is left after its terminator */
        return strncmp((const char *)a + f->offset, (const char *)b + f->offset, n) == 0;
    }
    return memcmp(a + f->offset, b + f->offset, n) == 0;
}

static int present_now(const unsigned char *record, unsigned char **now, int count) {
    int i;
    for (i = 0; i < count; ++i) {
        if (now[i] == record) {
            return 1;
        }
    }
    return 0;
}

/* A record slot the event freed and filled with someone else (an event that
   takes one villager away and brings another can put the newcomer at the
   freed address): the name differs AND so does at least one of head, body
   or sex.  A name alone changing is a rename -- The Secret City's Return of
   Biggles, confronted, names its subject "?" -- one villager, "Name: <old> ->
   ?" (Codex, #577). */
static int reused(const unsigned char *old, const unsigned char *live) {
    int k, name_differs = 0, other_differs = 0;
    for (k = 0; k < g_layout->field_count; ++k) {
        const struct field *f = &g_layout->fields[k];
        if (strcmp(f->label, "Name") == 0) {
            name_differs = !field_same(f, old, live);
        } else if (strcmp(f->label, "Sex") == 0) {
            other_differs |= !field_same(f, old, live);
        }
    }
    other_differs |= *(const int *)(old + g_layout->head) != *(const int *)(live + g_layout->head)
                     || *(const int *)(old + g_layout->body) != *(const int *)(live + g_layout->body);
    return name_differs && other_differs;
}

static int copy_of(const struct snapshot *s, const unsigned char *live) {
    int k;
    for (k = 0; k < s->count; ++k) {
        if (s->where[k] == live) {
            return k;
        }
    }
    return -1;
}

/* Compare and write: one record per villager the event changed. */
static void compare(struct snapshot *s) {
    unsigned char *now[MAX_VILLAGERS];
    int count, i, k, conceived;
    char before[2 * TITLE_MAX + TEXT_MAX + 64];
    char changes[2048];
    size_t at;
    if (writer() == NULL || s->count == 0) {
        return;
    }
    count = g_layout->enumerate(now, MAX_VILLAGERS);
    /* The owner (2026-10-09): name the kind of vial, crate and so on -- the
       item as the popup words it ("a watery red vial", "a large weathered crate"). */
    at = (size_t)_snprintf(before, sizeof before, "  Event: %s\n", s->title[0] ? s->title : "(an island event)");
    if (s->text[0] && at < sizeof before) {
        at += (size_t)_snprintf(before + at, sizeof before - at, "  Item: %s\n", s->text);
    }
    if (g_choice[0] && at < sizeof before) {
        _snprintf(before + at, sizeof before - at, "  Choice: %s\n", g_choice);
    }
    before[sizeof before - 1] = '\0';
    for (i = 0; i < s->count; ++i) {
        const unsigned char *old = s->copy + (size_t)i * g_layout->copy_size;
        unsigned char *live = s->where[i];
        size_t used = 0;
        if (live == NULL) {
            continue;
        }
        changes[0] = '\0';
        /* The record's slot decides who is who, unless it was reused for
           someone else (reused): a rename alone is one villager. */
        if (!present_now(live, now, count) || reused(old, live)) {
            /* Gone (died without a body, disappeared, left), or its record
               reused for someone else: named from the copy. */
            used += (size_t)_snprintf(changes + used, sizeof changes - used, "  Gone: yes\n");
            g_write(g_game, KIND_ISLAND_EVENT, old, 0, before, changes, 0);
            continue;
        }
        /* A conception the event started (Pregnant no -> yes): what it wrote
           on the mother -- the babies, and the expected father's name, head
           and body -- is printed whole, as the Births and Conceptions log
           words a conception, even where it equals what the last pregnancy
           left there (the same father again, or the same number of babies),
           in all five games alike.  What was there before belongs to an
           earlier pregnancy, so it is not printed as a "before". */
        conceived = 0;
        for (k = 0; k < g_layout->field_count; ++k) {
            const struct field *f = &g_layout->fields[k];
            if (f->type == F_FLAG && strcmp(f->label, "Pregnant") == 0) {
                conceived = *(const int *)(old + f->offset) == 0 && *(const int *)(live + f->offset) != 0;
            }
        }
        for (k = 0; k < g_layout->field_count; ++k) {
            const struct field *f = &g_layout->fields[k];
            char a[64], b[64];
            if (conceived && f->conception) {
                char name[64];
                int head, body;
                field_text(f, live, b, sizeof b);
                if (used < sizeof changes) {
                    int n = _snprintf(changes + used, sizeof changes - used, "  %s: %s\n", f->label, b);
                    used = n < 0 ? sizeof changes : used + (size_t)n;
                }
                /* A New Home keeps no father on the mother: the expected
                   father comes from where its conception recorded him
                   (expected_father), right after the babies, as the later
                   games' table order prints him. */
                if (g_layout->expected_father != NULL && strcmp(f->label, "Babies in pregnancy") == 0
                    && g_layout->expected_father(live, name, sizeof name, &head, &body) && used < sizeof changes) {
                    char head_text[32], body_text[32];
                    int n;
                    if (head >= 0) _snprintf(head_text, sizeof head_text, "%d", head);
                    else _snprintf(head_text, sizeof head_text, "(not recorded)");
                    if (body >= 0) _snprintf(body_text, sizeof body_text, "%d", body);
                    else _snprintf(body_text, sizeof body_text, "(not recorded)");
                    head_text[sizeof head_text - 1] = body_text[sizeof body_text - 1] = '\0';
                    n = _snprintf(changes + used, sizeof changes - used,
                                  "  Expected father: %s\n  Expected father's head: %s\n"
                                  "  Expected father's body: %s\n", name, head_text, body_text);
                    used = n < 0 ? sizeof changes : used + (size_t)n;
                }
                continue;
            }
            if (field_same(f, old, live)) {
                continue;
            }
            field_text(f, old, a, sizeof a);
            field_text(f, live, b, sizeof b);
            if (used < sizeof changes) {
                int n = _snprintf(changes + used, sizeof changes - used, "  %s: %s -> %s\n", f->label, a, b);
                used = n < 0 ? sizeof changes : used + (size_t)n;
            }
        }
        if (changes[0] == '\0') {
            continue;
        }
        changes[sizeof changes - 1] = '\0';
        g_write(g_game, KIND_ISLAND_EVENT, live, 1, before, changes, 0);
        {
            int oh = *(const int *)(old + g_layout->head), ob = *(const int *)(old + g_layout->body);
            int nh = *(const int *)(live + g_layout->head), nb = *(const int *)(live + g_layout->body);
            if (oh != nh || ob != nb) {
                char look[256 + TEXT_MAX];
                int n = _snprintf(look, sizeof look,
                                  "  Old head: %d\n  Old body: %d\n  New head: %d\n  New body: %d\n"
                                  "  Changed by: %s (island event)\n",
                                  oh, ob, nh, nb, s->title[0] ? s->title : "an island event");
                if (s->text[0] && n > 0 && (size_t)n < sizeof look) {
                    _snprintf(look + n, sizeof look - (size_t)n, "  Item: %s\n", s->text);   /* "a watery red vial" */
                }
                look[sizeof look - 1] = '\0';
                g_write(g_game, KIND_APPEARANCE, live, 1, look, NULL, 0);
            }
        }
    }
    /* Villagers the event brought (a barrel, a canoe, a copy, a newcomer): each
       is named with its looks, likes and skills, as the logs print a villager. */
    for (i = 0; i < count; ++i) {
        /* present before, in the same slot, and not reused for someone else */
        int k2 = copy_of(s, now[i]);
        int was = k2 >= 0 && !reused(s->copy + (size_t)k2 * g_layout->copy_size, now[i]);
        if (!was) {
            g_write(g_game, KIND_ISLAND_EVENT, now[i], 1, before, "  New villager: yes\n", 2);
        }
    }
}

/* ---- The sites ----------------------------------------------------------- */

/* One routine that applies events, detoured at its first instruction(s):
   `stolen` stock bytes (whole instructions, no relative operand) are checked,
   then run from a trampoline before the routine goes on.  `frame` below is
   pushad's eight registers (edi first; ecx, the `this` of a thiscall, is
   frame[6]), then the return address, then the routine's arguments
   (frame[9], frame[10], ...).

   `watch` says whether this call can change anything (a click handler runs
   for every mouse message; only a click on an answer applies), `before`
   reads what the event says before it runs and `after` what it says once it
   has (A New Home's island events write their title only as they run). */
struct snapshot_text {
    char *title;
    char *choice;
    size_t size;
    char *text;                           /* the item it names (item_of) */
    size_t text_size;
};
struct site {
    unsigned int entry;
    unsigned char stolen[8];
    unsigned int length;
    int (*watch)(const unsigned int *frame);
    void (*before)(const unsigned int *frame, struct snapshot_text *out);
    void (*after)(unsigned int self, struct snapshot_text *out);
    /* A two-choice dialog's answer click, read whatever is watched: the
       clicked button's label into `out` (empty when this call is no answer
       click).  The later games apply a stock two-choice event on the OK that
       follows the answer, so the answer is kept for the record that OK (or
       the presenter around both) writes. */
    void (*answer)(const unsigned int *frame, char *out, size_t size);
};

/* The first line of `text` with its padding taken off, at most size - 1 bytes. */
static void first_line(const char *text, size_t cap, char *out, size_t size) {
    size_t i = 0, n = 0;
    out[0] = '\0';
    if (text == NULL || !readable(text, 1)) {
        return;
    }
    while (i < cap && readable(text + i, 1) && (text[i] == ' ' || text[i] == '\n' || text[i] == '\r'
                                              || text[i] == '\t')) {
        ++i;
    }
    while (i < cap && readable(text + i, 1) && text[i] != '\0' && text[i] != '\n' && text[i] != '\r'
           && n + 1 < size) {
        out[n++] = text[i++];
    }
    while (n > 0 && (out[n - 1] == ' ' || out[n - 1] == '.')) {
        --n;                              /* "Drink the liquid." -> "Drink the liquid" */
    }
    out[n] = '\0';
}

/* The item an event's wording names, when the game words it more than one
   way: A New Home's and The Lost Children's vials ("what appears to be | ~
   liquid": "a watery," / "an oily," and the colour), crates ("It was | ~
   crate": "a small" / "a large" and the kind) and sacks.  The phrase from its
   article to the noun, commas dropped, a vial's liquid called a vial: "an
   oily red vial", "a large weathered crate".  The later games word each event
   one way: nothing is found and nothing written. */
static void item_of(const char *body, char *out, size_t size) {
    static const char *const nouns[] = { " liquid", " crate", " sack" };
    const char *best = NULL, *start, *p;
    const char *noun = NULL;
    size_t i, n = 0;
    out[0] = '\0';
    for (i = 0; i < sizeof nouns / sizeof nouns[0]; ++i) {
        for (p = strstr(body, nouns[i]); p != NULL; p = strstr(p + 1, nouns[i])) {
            const char *after = p + strlen(nouns[i]);
            if (*after == '.' || *after == ' ' || *after == '\0' || *after == ',' || *after == '!') {
                if (best == NULL || p > best) {
                    best = p;
                    noun = nouns[i];
                }
            }
        }
    }
    if (best == NULL) {
        return;
    }
    /* back to the nearest " a " / " an " at most five words before the noun */
    for (start = best, i = 0; start > body && i < 6; --start) {
        if (start[-1] == ' ') {
            ++i;
            if ((strncmp(start, "a ", 2) == 0 || strncmp(start, "an ", 3) == 0)) {
                break;
            }
        }
    }
    if (!(strncmp(start, "a ", 2) == 0 || strncmp(start, "an ", 3) == 0)) {
        return;
    }
    for (p = start; p < best && n + 1 < size; ++p) {
        if (*p != ',') {
            out[n++] = *p;
        }
    }
    _snprintf(out + n, size - n, "%s", strcmp(noun, " liquid") == 0 ? " vial" : noun);
    out[size - 1] = '\0';
}

/* An event's popup: its title is the first line; the wording after it, joined
   onto one line, names the item (item_of). */
static void event_text(const char *text, size_t cap, struct snapshot_text *out) {
    char body[1024];
    size_t i = 0, n = 0;
    first_line(text, cap, out->title, out->size);
    out->text[0] = '\0';
    if (text == NULL) {
        return;
    }
    while (i < cap && readable(text + i, 1) && (text[i] == ' ' || text[i] == '\n' || text[i] == '\r'
                                              || text[i] == '\t')) {
        ++i;
    }
    while (i < cap && readable(text + i, 1) && text[i] != '\0' && text[i] != '\n' && text[i] != '\r') {
        ++i;                              /* past the title */
    }
    for (; i < cap && readable(text + i, 1) && text[i] != '\0' && n + 1 < sizeof body; ++i) {
        char c = text[i] == '\n' || text[i] == '\r' || text[i] == '\t' ? ' ' : text[i];
        if (c == ' ' && (n == 0 || body[n - 1] == ' ')) {
            continue;
        }
        body[n++] = c;
    }
    body[n] = '\0';
    item_of(body, out->text, out->text_size);
}

#include "island_event_games.inc"         /* the five games' layouts and sites */

#define MAX_SITES 16
#define RETURNS 256                       /* far beyond any nesting the games make */
static const struct site *g_sites[MAX_SITES];
static unsigned char *g_trampolines[MAX_SITES];
static unsigned int g_returns[RETURNS];
static unsigned int g_selves[RETURNS];    /* each call's `this` */
static const struct site *g_called[RETURNS];
static int g_watching;                    /* the outermost call is being compared */

static void fill_text(struct snapshot_text *text) {
    text->title = g_snaps[0].title;
    text->choice = g_choice;
    text->size = sizeof g_snaps[0].title;
    text->text = g_snaps[0].text;
    text->text_size = sizeof g_snaps[0].text;
}

/* Called by the thunk before the routine.  Only the outermost watched call
   is compared: a routine reached inside another's changes nothing the outer
   comparison does not see, and watching both would log each change twice.
   An inner routine still names the event when the outer one cannot (The
   Tree of Life's dialog constructor, inside its event presenter). */
static void __cdecl before_call(const unsigned int *frame, int index) {
    const struct site *site = g_sites[index];
    struct snapshot_text text;
    fill_text(&text);
    if (g_depth == 0) {
        g_answering = 0;
    }
    if (site->answer != NULL) {
        char label[TITLE_MAX];
        label[0] = '\0';
        site->answer(frame, label, sizeof label);
        if (label[0] != '\0') {
            g_answering = g_depth == 0;   /* the answer itself is the outermost call */
            memcpy(g_answer, label, sizeof g_answer);
            g_answer_self = frame[6];
            if (g_depth > 0 && g_watching) {
                memcpy(g_choice, label, sizeof g_choice);   /* inside the presenter's bracket */
            }
        }
    }
    if (g_depth == 0) {
        g_watching = site->watch == NULL || site->watch(frame);
        if (g_watching) {
            g_snaps[0].title[0] = '\0';
            g_snaps[0].text[0] = '\0';
            g_choice[0] = '\0';
            if (site->answer != NULL && g_answer[0] != '\0' && g_answer_self == frame[6]) {
                /* this dialog's OK (or its answer itself): the answer clicked in it */
                memcpy(g_choice, g_answer, sizeof g_choice);
            }
            if (site->before != NULL) {
                site->before(frame, &text);
            }
            take(&g_snaps[0]);
        }
    } else if (g_watching && g_snaps[0].title[0] == '\0' && site->before != NULL
               && (site->watch == NULL || site->watch(frame))) {
        site->before(frame, &text);
    }
    if (g_depth < RETURNS) {
        g_returns[g_depth] = frame[8];
        g_selves[g_depth] = frame[6];
        g_called[g_depth] = site;
    }
    ++g_depth;
}

static unsigned int __cdecl after_call(void) {
    struct snapshot_text text;
    --g_depth;
    fill_text(&text);
    if (g_depth < RETURNS && g_watching && g_called[g_depth]->after != NULL
        && (g_depth == 0 || g_snaps[0].title[0] == '\0')) {
        g_called[g_depth]->after(g_selves[g_depth], &text);
    }
    if (g_depth == 0 && g_watching) {
        compare(&g_snaps[0]);
        g_watching = 0;
        if (!g_answering) {
            /* told: never carried to a later dialog at the same address.  An
               answer that was itself the call compared (New Believers' click
               on a custom event's answer) is kept for the OK that follows. */
            g_answer[0] = '\0';
            g_answer_self = 0;
        }
    }
    return g_depth < RETURNS ? g_returns[g_depth] : 0;
}
/* One stub per site pushes its index and jumps here. */
static unsigned int g_index_scratch;
static unsigned int g_back_scratch;
static unsigned int g_target_scratch;

static __declspec(naked) void thunk_body(void) {
    /* stack: [index][return into the caller][args...] */
    __asm {
        pop dword ptr [g_index_scratch]
        pushad
        push dword ptr [g_index_scratch]
        lea eax, [esp + 4]
        push eax
        call before_call
        add esp, 8
        mov eax, dword ptr [g_index_scratch]
        mov eax, dword ptr [g_trampolines + eax * 4]
        mov dword ptr [g_target_scratch], eax
        popad
        add esp, 4                        /* the caller's return: after_call gives it back */
        call dword ptr [g_target_scratch] /* the routine, through its trampoline */
        pushad
        call after_call
        mov dword ptr [g_back_scratch], eax
        popad
        jmp dword ptr [g_back_scratch]
    }
}

#define STUB_SIZE 16                      /* push imm32; jmp rel32 -- and the trampoline below it */
#define TRAMPOLINE_SIZE 16                /* stolen bytes; jmp rel32 back */
static unsigned char *g_code;

static void put_jmp(unsigned char *at, const void *to) {
    int rel = (int)((const unsigned char *)to - (at + 5));
    at[0] = 0xE9;
    memcpy(at + 1, &rel, 4);
}

static int install(int game) {
    const struct site *sites;
    int count, i;
    DWORD old;
    if (game < 1 || game > GAMES || GAME_SITES[game] == NULL || GAME_LAYOUTS[game] == NULL
        || writer() == NULL) {
        return 0;                         /* nothing to write to: nothing installed */
    }
    sites = GAME_SITES[game];
    for (count = 0; sites[count].entry != 0; ++count) {
        const unsigned char *at = (const unsigned char *)(uintptr_t)sites[count].entry;
        if (count >= MAX_SITES || sites[count].length < 5 || sites[count].length > 8
            || !readable(at, sites[count].length) || memcmp(at, sites[count].stolen, sites[count].length) != 0) {
            return 0;                     /* not the stock bytes: nothing is installed */
        }
    }
    g_code = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)count * (STUB_SIZE + TRAMPOLINE_SIZE),
                                           MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (g_code == NULL) {
        return 0;
    }
    g_game = game;
    g_layout = GAME_LAYOUTS[game];
    for (i = 0; i < count; ++i) {
        unsigned char *stub = g_code + i * (STUB_SIZE + TRAMPOLINE_SIZE);
        unsigned char *trampoline = stub + STUB_SIZE;
        unsigned char *at = (unsigned char *)(uintptr_t)sites[i].entry;
        g_sites[i] = &sites[i];
        g_trampolines[i] = trampoline;
        stub[0] = 0x68;                   /* push imm32 (the site's index) */
        memcpy(stub + 1, &i, 4);
        put_jmp(stub + 5, (const void *)(uintptr_t)thunk_body);
        memcpy(trampoline, sites[i].stolen, sites[i].length);
        put_jmp(trampoline + sites[i].length, at + sites[i].length);
    }
    FlushInstructionCache(GetCurrentProcess(), g_code, (SIZE_T)count * (STUB_SIZE + TRAMPOLINE_SIZE));
    for (i = 0; i < count; ++i) {
        unsigned char *at = (unsigned char *)(uintptr_t)sites[i].entry;
        unsigned char bytes[8];
        if (!VirtualProtect(at, sites[i].length, PAGE_EXECUTE_READWRITE, &old)) {
            continue;
        }
        /* The jump is relative to where it will sit, the routine's entry -- not
           to this buffer it is assembled in. */
        memset(bytes, 0x90, sizeof bytes);
        bytes[0] = 0xE9;
        {
            int rel = (int)(g_code + i * (STUB_SIZE + TRAMPOLINE_SIZE) - (at + 5));
            memcpy(bytes + 1, &rel, 4);
        }
        memcpy(at, bytes, sites[i].length);
        VirtualProtect(at, sites[i].length, old, &old);
        FlushInstructionCache(GetCurrentProcess(), at, sites[i].length);
    }
    return 1;
}

/* Called once by "VVFP Startup.dll" as the game opens. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static int done;
    (void)shipped;
    if (!done) {
        done = 1;
        (void)install(game);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
