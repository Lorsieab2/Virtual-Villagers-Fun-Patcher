/* Runtime harness for "VVFP Parentage Export.dll".  32-bit only.

   Calls the real WriteParentageRecordWithFather -- the export every game's
   conception trampoline calls -- for each of the five games over a synthetic
   villager array laid out exactly like that game's, then reads back the log
   the DLL wrote and checks every field of the conception record against the
   villagers it was given:

     the mother's name, age at conception, head, body, likes, dislikes
     the father's name, age at conception, head, body, likes, dislikes
     the number of babies: 1 (singleton), 2 (twins), 3 (triplets)

   and, for the games that record the father BY NAME, that a conception with
   no captured father record prints his name and the game's own head/body
   copies but says "(not captured for this birth)" for his age, likes and
   dislikes -- never another villager's, even one sharing his name.

   The DLL writes under Documents\LDW\<this exe's basename>\, exactly where a
   game of that name would keep its saves.  The harness starts with that
   folder empty and removes it when done, so nothing is left behind and no
   player's folder is touched.

   Usage:  parentage_export_harness.exe "<path to VVFP Parentage Export.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *write_t)(int, const void *, const void *, const void *);

/* Each game's record geometry, as the export DLL's own layout table has it
   (and as the population exporter measured the preference arrays).  A test
   reads this table against the DLL's and fails if they drift apart. */
struct layout {
    int game;
    unsigned int stride, slots, base;
    unsigned int active, age, head, body, name, name_cap;
    unsigned int father_name, father_key_cap, father_head_copy, father_body_copy;
    unsigned int litter, likes, dislikes, pref_slots;
    int last_preference;          /* the highest valid index in this game's list */
    const char *last_word;        /* ...and the word it names */
    const char *title;
};
static const struct layout LAYOUTS[5] = {
    { 1, 0x3D8,  256, 0,    0x28,   0x348,  0x360,  0x364,  0x370,  0x1C, 0,      0,    0,      0,      0x35C,  0x398,  0x3A8,  4, 46, "jokes",  "Virtual Villagers 1 Births and Conceptions Log" },
    { 2, 0xE48C, 256, 0,    0x30,   0x530,  0x548,  0x54C,  0x564,  0x18, 0x5C0,  0x18, 0x5E0,  0x5DC,  0x544,  0x5F0,  0x6E8, 62, 61, "dirt",   "Virtual Villagers 2 Births and Conceptions Log" },
    { 3, 0x1F8C, 150, 0x14, 0xF10,  0xDC4,  0xDF0,  0xDF4,  0xDD4,  0x19, 0xE48,  0x18, 0xE68,  0xE64,  0xE90,  0xFB4,  0xFC0,  3, 78, "nature", "Virtual Villagers 3 Births and Conceptions Log" },
    { 4, 0x2E3C, 150, 0x44, 0x1CC4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1C10, 0x18, 0x1C30, 0x1C2C, 0x1C50, 0x1E60, 0x1E6C, 3, 78, "nature", "Virtual Villagers 4 Births and Conceptions Log" },
    { 5, 0x2F44, 150, 0x48, 0x1CD4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1C10, 0x18, 0x1C30, 0x1C2C, 0x1C50, 0x1F5C, 0x1F68, 3, 78, "nature", "Virtual Villagers 5 Births and Conceptions Log" },
};

static const struct layout *g;
static unsigned char *records;
static unsigned char *rec(int i) { return records + g->base + i * g->stride; }

static void villager(int i, const char *name, int age, int head, int body) {
    unsigned int s;
    memset(rec(i), 0, g->stride);
    rec(i)[g->active] = 1;
    *(int *)(rec(i) + g->age) = age;
    *(int *)(rec(i) + g->head) = head;
    *(int *)(rec(i) + g->body) = body;
    strncpy((char *)rec(i) + g->name, name, g->name_cap);
    for (s = 0; s < g->pref_slots; ++s) {          /* every slot empty */
        *(int *)(rec(i) + g->likes + s * 4) = -1;
        *(int *)(rec(i) + g->dislikes + s * 4) = -1;
    }
}
static void like(int i, unsigned int slot, int index)    { *(int *)(rec(i) + g->likes + slot * 4) = index; }
static void dislike(int i, unsigned int slot, int index) { *(int *)(rec(i) + g->dislikes + slot * 4) = index; }

/* What the game itself does at conception in VV2..VV5: copies the father's
   name (at the key width), head and body onto the mother. */
static void game_copies_father_onto_mother(int mother, int father) {
    if (g->father_name == 0) return;
    memset(rec(mother) + g->father_name, 0, g->father_key_cap);
    strncpy((char *)rec(mother) + g->father_name, (const char *)rec(father) + g->name, g->father_key_cap);
    *(int *)(rec(mother) + g->father_head_copy) = *(int *)(rec(father) + g->head);
    *(int *)(rec(mother) + g->father_body_copy) = *(int *)(rec(father) + g->body);
}

/* ---- the log on disk ---- */
static char folder[MAX_PATH];
static int locate_folder(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return 0;
    base = strrchr(exe, '\\'); base = base ? base + 1 : exe;
    dot = strrchr(base, '.'); if (dot) *dot = 0;
    /* The exporter writes into a subfolder, not the save folder itself. This
       harness was left addressing the save folder when that layout was
       introduced, so every lookup missed and all 37 checks failed in a way
       indistinguishable from the DLL writing nothing at all. Nothing caught
       it because the harness does not run in CI. */
    _snprintf(folder, MAX_PATH, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Logs\\Births and Conceptions",
              docs, base);
    folder[MAX_PATH - 1] = '\0';
    return 1;
}
static void remove_logs(void) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f; HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*.txt", folder);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do { _snprintf(path, MAX_PATH, "%s\\%s", folder, f.cFileName); DeleteFileA(path); }
        while (FindNextFileA(h, &f));
        FindClose(h);
    }
    RemoveDirectoryA(folder);
}
static char logtext[1 << 16];
static int read_log(void) {
    char path[MAX_PATH]; FILE *f; size_t n;
    _snprintf(path, MAX_PATH, "%s\\%s 1.txt", folder, g->title);
    f = fopen(path, "rb");
    if (f == NULL) { logtext[0] = 0; return 0; }
    n = fread(logtext, 1, sizeof logtext - 1, f);
    logtext[n] = 0;
    fclose(f);
    return 1;
}
/* How many conception records the log currently holds. */
static int n_records(const struct layout *g) {
    int n = 0;
    const char *p = logtext;
    (void)g;
    while ((p = strstr(p, "Conception ")) != NULL) { ++n; p += 11; }
    return n;
}

/* The n-th conception record (1-based) as the text between its marker and the
   next one. */
static const char *conception(int n) {
    const char *p = logtext; char marker[32];
    _snprintf(marker, sizeof marker, "Conception %d\r\n", n);
    p = strstr(p, marker);
    return p;
}
static int record_has(const char *record, const char *line) {
    const char *end = strstr(record + 1, "Conception ");
    char wanted[128]; const char *hit;
    _snprintf(wanted, sizeof wanted, "%s\r\n", line);
    hit = strstr(record, wanted);
    return hit != NULL && (end == NULL || hit < end);
}
/* The next line indented by exactly two spaces: the start of the next block
   (a field line is indented by four, which also begins with two). */
static const char *next_block(const char *from) {
    const char *p = from;
    while ((p = strstr(p, "\r\n  ")) != NULL) {
        if (p[4] != ' ') return p;
        p += 4;
    }
    return NULL;
}
/* A field under a specific parent block: "  Mother: ..." or "  Father: ..." */
static int parent_has(const char *record, const char *parent, const char *line) {
    const char *block = strstr(record, parent);
    const char *end;
    char wanted[128]; const char *hit;
    if (block == NULL) return 0;
    end = next_block(block + 1);
    _snprintf(wanted, sizeof wanted, "    %s\r\n", line);
    hit = strstr(block, wanted);
    return hit != NULL && (end == NULL || hit < end);
}

static void run_game(write_t write, const struct layout *layout) {
    const char *r; char line[128];
    int ok;
    g = layout;
    printf("== VV%d: %s ==\n", g->game, g->title);
    remove_logs();
    records = (unsigned char *)calloc(1, g->base + g->slots * g->stride);

    /* Aisha, 22, likes turnips (slot 0); her first dislike slot holds an index
       past the end of the list (a corrupt/empty marker real villages carry)
       and her second holds snakes -- the record must show snakes. */
    villager(3, "Aisha", 22 * 20, 4, 9);
    like(3, 0, 5); dislike(3, 0, g->last_preference + 1); dislike(3, 1, 13);
    /* Goro, 30, no likes at all, dislikes the LAST word of this game's list --
       which proves the right list is in use for this game. */
    villager(7, "Goro", 30 * 20, 7, 2);
    dislike(7, 0, g->last_preference);

    /* --- twins, father record captured --- */
    *(int *)(rec(3) + g->litter) = 2;
    game_copies_father_onto_mother(3, 7);
    ok = write(g->game, records, rec(3), rec(7));
    CHECK(ok == 1, "the DLL accepts the conception (returned %d)", ok);
    CHECK(read_log(), "the log exists at %s\\%s 1.txt", folder, g->title);
    r = conception(1);
    CHECK(r != NULL, "Conception 1 is in the log");
    if (r) {
        const char *stop = strstr(r + 1, "Conception ");
        printf("---- the record as written ----\n%.*s---- end ----\n",
               (int)(stop ? stop - r : (long)strlen(r)), r);
        CHECK(record_has(r, "  Mother: Aisha"), "mother's name");
        _snprintf(line, sizeof line, "Age at conception: %d", 22 * 20);
        CHECK(parent_has(r, "  Mother:", line), "mother's age at conception");
        CHECK(parent_has(r, "  Mother:", "Head: 4"), "mother's head");
        CHECK(parent_has(r, "  Mother:", "Body: 9"), "mother's body");
        CHECK(parent_has(r, "  Mother:", "Likes: turnips"), "mother's likes (index 5, zero-based)");
        CHECK(parent_has(r, "  Mother:", "Dislikes: snakes"), "mother's dislikes: the first FILLED slot, skipping an out-of-range one");
        CHECK(record_has(r, "  Father: Goro"), "father's name");
        _snprintf(line, sizeof line, "Age at conception: %d", 30 * 20);
        CHECK(parent_has(r, "  Father:", line), "father's age at conception, from his own record");
        CHECK(parent_has(r, "  Father:", "Head: 7"), "father's head");
        CHECK(parent_has(r, "  Father:", "Body: 2"), "father's body");
        CHECK(parent_has(r, "  Father:", "Likes: (none)"), "father with every like slot empty prints (none)");
        _snprintf(line, sizeof line, "Dislikes: %s", g->last_word);
        CHECK(parent_has(r, "  Father:", line), "father's dislikes: index %d names '%s' in THIS game's list", g->last_preference, g->last_word);
        CHECK(record_has(r, "  Babies in pregnancy: 2"), "twins: 2 babies");
    }

    /* --- triplets, no father record passed --- */
    *(int *)(rec(3) + g->litter) = 3;
    ok = write(g->game, records, rec(3), NULL);
    CHECK(ok == 1, "a conception with no captured father record is still logged (returned %d)", ok);
    read_log();
    r = conception(n_records(g));       /* the record just written */
    CHECK(r != NULL, "the twins-and-triplets record is in the log");
    if (r) {
        CHECK(record_has(r, "  Babies in pregnancy: 3"), "triplets: 3 babies");
        CHECK(parent_has(r, "  Mother:", "Likes: turnips"), "mother's fields do not depend on the father");
        if (g->father_name != 0) {
            /* VV2..VV5: the game recorded his name and head/body on her, so
               those are real; his age, likes and dislikes need his record,
               which was not captured -- so they say so rather than being
               read from whoever answers to his name. */
            CHECK(record_has(r, "  Father: Goro"), "father's name comes from the mother's record");
            CHECK(parent_has(r, "  Father:", "Head: 7"), "father's head from the game's copy on the mother");
            CHECK(parent_has(r, "  Father:", "Body: 2"), "father's body from the game's copy on the mother");
            CHECK(parent_has(r, "  Father:", "Age at conception: (not captured for this birth)"), "no captured record: his age is not scanned for");
            CHECK(parent_has(r, "  Father:", "Likes: (not captured for this birth)"), "no captured record: his likes are not scanned for");
            CHECK(parent_has(r, "  Father:", "Dislikes: (not captured for this birth)"), "no captured record: his dislikes are not scanned for");
        } else {
            /* VV1 keeps nothing about him: the record says so, and never guesses. */
            CHECK(record_has(r, "  Father: (not captured for this birth)"), "VV1 with no capture: the father is not captured");
            CHECK(parent_has(r, "  Father:", "Likes: (not captured for this birth)"), "...and his likes say the same");
            CHECK(parent_has(r, "  Father:", "Dislikes: (not captured for this birth)"), "...and his dislikes say the same");
        }
    }

    /* --- the LAST slot of each array must be scanned ---

       A preference sitting in the final slot is only found if the scan covers
       the whole array.  This is what catches a slot count that is too small:
       VV2 declares 62 slots and an earlier revision of this table said 4, so
       every villager whose first filled entry sat past slot 3 was logged as
       "(none)" -- permanently, since a conception record is never rewritten.
       The harness must not take the count on trust from the same table it is
       testing, which is exactly why it failed to notice. */
    villager(5, "Ndidi", 33 * 20, 5, 6);
    like(5, g->pref_slots - 1, 5);                 /* turnips, in the very last slot */
    dislike(5, g->pref_slots - 1, g->last_preference);
    *(int *)(rec(5) + g->litter) = 0;
    game_copies_father_onto_mother(5, 7);
    ok = write(g->game, records, rec(5), rec(7));
    CHECK(ok == 1, "a conception whose preferences sit in the last slot is logged");
    read_log();
    {
        const char *last = conception(n_records(g));
        CHECK(last != NULL, "that record is in the log");
        if (last) {
            CHECK(parent_has(last, "  Mother:", "Likes: turnips"),
                  "a like in the FINAL slot (%u) is found: a short scan would say (none)", g->pref_slots - 1);
            _snprintf(line, sizeof line, "Dislikes: %s", g->last_word);
            CHECK(parent_has(last, "  Mother:", line),
                  "...and so is a dislike in the final slot");
        }
    }

    /* --- singleton: the litter field is 0 when the engine chose one baby --- */
    *(int *)(rec(3) + g->litter) = 0;
    ok = write(g->game, records, rec(3), rec(7));
    read_log();
    r = conception(n_records(g));       /* the record just written */
    CHECK(r != NULL && record_has(r, "  Babies in pregnancy: 1"), "singleton: litter 0 is logged as 1 baby");

    /* --- a namesake: only the ONE living Goro left is the other one --- */
    if (g->father_name != 0) {
        /* The real Goro dies; a different Goro, who likes ants, is the only
           living villager by that name.  A by-name scan would find him and
           print his likes under the father.  Without a captured record the
           log must not. */
        rec(7)[g->active] = 0;
        villager(9, "Goro", 40 * 20, 1, 1);
        like(9, 0, 0);
        *(int *)(rec(3) + g->litter) = 0;
        ok = write(g->game, records, rec(3), NULL);
        read_log();
        r = conception(n_records(g));   /* the record just written */
        CHECK(r != NULL, "the namesake record is in the log");
        if (r) {
            CHECK(record_has(r, "  Father: Goro"), "the name the game recorded is still printed");
            CHECK(parent_has(r, "  Father:", "Head: 7"), "head still comes from the game's own copy on the mother");
            CHECK(parent_has(r, "  Father:", "Body: 2"), "body still comes from the game's own copy on the mother");
            CHECK(parent_has(r, "  Father:", "Age at conception: (not captured for this birth)"), "the namesake's age is not printed as his");
            CHECK(!parent_has(r, "  Father:", "Likes: ants"), "the namesake's likes are never printed under him");
            CHECK(parent_has(r, "  Father:", "Likes: (not captured for this birth)"), "...his likes are honestly absent instead");
        }
        /* With the namesake's record captured, it IS the father the engine
           worked with, and his own fields are printed. */
        game_copies_father_onto_mother(3, 9);
        ok = write(g->game, records, rec(3), rec(9));
        read_log();
        r = conception(n_records(g));   /* the record just written */
        CHECK(r != NULL && parent_has(r, "  Father:", "Likes: ants"), "a captured record is printed whoever else shares the name");
        CHECK(r != NULL && parent_has(r, "  Father:", "Head: 1"), "...with the head the game copied for THIS conception");
    }

    free(records);
    remove_logs();
}

int main(int argc, char **argv) {
    HMODULE dll; write_t write; int i;
    if (argc < 2) { fprintf(stderr, "usage: %s <VVFP Parentage Export.dll>\n", argv[0]); return 2; }
    if (!locate_folder()) { fprintf(stderr, "cannot resolve Documents\\LDW\n"); return 2; }
    dll = LoadLibraryA(argv[1]);
    if (dll == NULL) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 2; }
    write = (write_t)GetProcAddress(dll, "WriteParentageRecordWithFather");
    if (write == NULL) { fprintf(stderr, "WriteParentageRecordWithFather not exported\n"); return 2; }
    printf("log folder: %s\n", folder);
    for (i = 0; i < 5; ++i) {
        run_game(write, &LAYOUTS[i]);
    }
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
