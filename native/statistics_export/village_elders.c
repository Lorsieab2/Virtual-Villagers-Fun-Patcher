/* Village Elders, tracked in a per-save .dat file.

   THE OWNER'S DEFINITION (docs/village-statistics-directive.md, I.7): a
   Village Elder is ONE villager who has reached Master status in any three
   distinct skills. Count the villager, not the skills: mastering a fourth
   or fifth adds nothing.

   WHY A FILE. The owner: "if the game doesn't keep track of it, make a .dat
   file". The later games keep no lifetime elder list: VV3 and VV5 record the
   verdict only on a villager's grave, and The Tree of Life records only the
   stricter mastered-ALL-FIVE verdict. An earlier revision wrote its own flag
   into VV4 grave byte +0x37; the stock burial writer's dword store at +0x34
   overwrites it, and seeding it pushed +0x34 out of the range the memorial
   loader accepts. Nothing here writes any game memory.

   FILE. "<save folder>\Virtual Villagers Fun Patcher Data\Village Elders\
   Village Elders - Save N.dat", plain text, deterministic:

       VVFP VILLAGE ELDERS v2 game=<1..5>     (v1 had no "open" field and is
                                              never read: moved aside, kept)
       graves_seen=<memorial entries already examined>
       E<TAB>slot<TAB>name<TAB>father<TAB>mother<TAB>gone<TAB>open
       G<TAB>-1<TAB>name<TAB><TAB><TAB>1<TAB>0

   One line per elder. "E" = seen alive holding the status: the slot index in
   the villager array plus the latest name and parents' names seen there.
   "open" = 1 while every save still finds an elder in that slot -- the line
   IS that villager, followed through renames (identity is slot continuity,
   never the name) and through the renumbering a reload does (the packed
   load puts each villager at its rank in the previous save's roster, which
   the statistics companion hands over). "gone" = 1 once that villager has
   been matched to their
   grave. "G" = an elder known only from a grave the game
   flagged. The row prints the number of lines.

   UPDATE, after every successful save:
   1. Living: every active villager with Master (the game's own threshold) in
      three or more skills is added if no E line has the same identity.
   2. Graves: memorials fill the first free slot, stay contiguous and are
      never cleared during play, so entries at index >= graves_seen are new
      burials. A new grave whose own game flag says "elder" is matched to an
      E line of the same name that is no longer alive (marked gone, not
      counted again); otherwise it is added as a G line -- an elder who
      qualified and died between two saves.
   3. On creating the file (no history yet), every flagged grave already in
      the memorial is added as a G line: the retroactive baseline, from data
      the game itself retained. Nothing else is invented.

   SAFETY. Written to a .tmp file and moved over the old one. A missing file
   is an empty history. A file with an unknown header, version or game is
   moved aside to "... .unreadable-<ticks>.dat" and never overwritten, and no
   entries are taken from it.

   KNOWN LIMITS (stated, not hidden):
   - A villager who reaches three masteries and dies before any save is
     found only through a grave flag: VV3 and VV5 flag three-or-more; VV4
     flags only all-five; VV1 graves carry no skills.
   - Identity is slot + name (+ parents). A NEW villager born into the same
     slot with the same name and the same parents as an earlier elder would
     be taken for them.
   - A grave is matched to an E line by name; two dead elders sharing a name
     between two saves could be taken for one. */
#include <windows.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#include "save_folder.h"
#include "per_save_data.h"       /* one folder per save */
#include "village_elders.h"
#include "villager_lookalike.h"  /* statues, ghosts and stand-ins are no villagers */

#define ELDERS_MAX VV_ELDERS_FILE_MAX
#define NAME_MAX_CHARS 40

struct elder {
    char kind;                      /* 'E' or 'G' */
    int slot;
    char name[NAME_MAX_CHARS];
    char father[NAME_MAX_CHARS];
    char mother[NAME_MAX_CHARS];
    int gone;
    int open;                       /* the slot still holds this elder */
    int seen;                       /* working flag for the current save */
};

static struct elder g_elders[ELDERS_MAX];
static int g_count;
static int g_graves_seen;

static void copy_name(char *dst, const unsigned char *src, unsigned int capacity) {
    unsigned int i;
    unsigned int limit = capacity < NAME_MAX_CHARS - 1 ? capacity : NAME_MAX_CHARS - 1;
    if (src == NULL || capacity == 0u) {
        dst[0] = '\0';
        return;
    }
    for (i = 0; i < limit && src[i] != 0; ++i) {
        /* the file is tab/newline separated: never let a byte break it */
        dst[i] = (src[i] == '\t' || src[i] == '\r' || src[i] == '\n') ? ' ' : (char)src[i];
    }
    dst[i] = '\0';
}

static int mastered_skills(const unsigned char *record, const struct elders_layout *l) {
    unsigned int i;
    int mastered = 0;
    for (i = 0; i < l->skill_count; ++i) {
        const unsigned char *field = record + l->skills + i * 4u;
        if (l->skills_are_float) {
            float value;
            memcpy(&value, field, sizeof(value));
            if (value >= l->master_float) {   /* NaN compares false: not mastered */
                ++mastered;
            }
        } else {
            int value;
            memcpy(&value, field, sizeof(value));
            if (value >= l->master_int) {
                ++mastered;
            }
        }
    }
    return mastered;
}

/* "Village Elders - Save <S><suffix>" beside the slot's ".dat": in the save's own "Virtual Villagers
   Fun Patcher\Save <S>\Data\Village Elders\" now, unless the file is still in the older layout's
   folder (native/shared/per_save_data.h) -- the ".tmp" always beside the ".dat" it replaces. */
static int path_for(int save_id, wchar_t *path, const wchar_t *suffix) {
    wchar_t name[64];
    size_t length;
    if (_snwprintf_s(name, 64, _TRUNCATE, L"Village Elders - Save %d.dat", save_id) <= 0
        || !vv_ps_data_file_w(path, L"Village Elders", name, 64)) {
        return 0;
    }
    length = wcslen(path);
    return length > 4 && _snwprintf_s(path + length - 4, MAX_PATH - (length - 4), _TRUNCATE, L"%ls", suffix) > 0;
}

/* 1 = loaded (or absent: empty history), 0 = unreadable (moved aside),
   -1 = present but cannot be opened (locked by a sync client or scanner):
   neither read nor written this time. */
static int load(int game_id, const wchar_t *path) {
    FILE *f;
    char line[512];
    char header[64];
    errno_t opened;
    g_count = 0;
    g_graves_seen = -1;               /* -1: no history yet */
    opened = _wfopen_s(&f, path, L"rb");
    if (opened != 0 || f == NULL) {
        /* Only a file that is not there is a new, empty history. Anything
           else would start from nothing and then replace the real file. */
        return opened == ENOENT ? 1 : -1;
    }
    _snprintf_s(header, sizeof(header), _TRUNCATE, "VVFP VILLAGE ELDERS v2 game=%d", game_id);
    if (fgets(line, sizeof(line), f) == NULL || strncmp(line, header, strlen(header)) != 0
        || (line[strlen(header)] != '\r' && line[strlen(header)] != '\n')) {
        fclose(f);
        return 0;
    }
    if (fgets(line, sizeof(line), f) == NULL || sscanf_s(line, "graves_seen=%d", &g_graves_seen) != 1
        || g_graves_seen < 0) {
        fclose(f);
        g_count = 0;
        return 0;
    }
    while (fgets(line, sizeof(line), f) != NULL) {
        struct elder e;
        char *fields[7];
        char *cursor = line;
        int n = 0;
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[--len] = '\0';
        }
        if (len == 0) {
            continue;
        }
        fields[n++] = cursor;
        while (*cursor != '\0' && n < 7) {
            if (*cursor == '\t') {
                *cursor = '\0';
                fields[n++] = cursor + 1;
            }
            ++cursor;
        }
        if (n != 7 || (fields[0][0] != 'E' && fields[0][0] != 'G') || fields[0][1] != '\0'
            || g_count >= ELDERS_MAX) {
            fclose(f);
            g_count = 0;
            return 0;
        }
        memset(&e, 0, sizeof(e));
        e.kind = fields[0][0];
        e.slot = atoi(fields[1]);
        strncpy_s(e.name, sizeof(e.name), fields[2], _TRUNCATE);
        strncpy_s(e.father, sizeof(e.father), fields[3], _TRUNCATE);
        strncpy_s(e.mother, sizeof(e.mother), fields[4], _TRUNCATE);
        e.gone = atoi(fields[5]) != 0;
        e.open = atoi(fields[6]) != 0;
        g_elders[g_count++] = e;
    }
    fclose(f);
    return 1;
}

static int save(int game_id, const wchar_t *path, const wchar_t *temporary) {
    FILE *f;
    int i;
    /* Text mode: the C runtime writes the Windows line endings. */
    if (_wfopen_s(&f, temporary, L"w") != 0 || f == NULL) {
        return 0;
    }
    fprintf(f, "VVFP VILLAGE ELDERS v2 game=%d\ngraves_seen=%d\n", game_id, g_graves_seen);
    for (i = 0; i < g_count; ++i) {
        const struct elder *e = &g_elders[i];
        fprintf(f, "%c\t%d\t%s\t%s\t%s\t%d\t%d\n", e->kind, e->slot, e->name, e->father, e->mother, e->gone,
                e->open);
    }
    if (fflush(f) != 0 || fclose(f) != 0) {
        DeleteFileW(temporary);
        return 0;
    }
    if (!MoveFileExW(temporary, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}

static int add(char kind, int slot, const char *name, const char *father, const char *mother, int gone) {
    struct elder *e;
    if (g_count >= ELDERS_MAX) {
        return 0;
    }
    e = &g_elders[g_count++];
    memset(e, 0, sizeof(*e));
    e->kind = kind;
    e->slot = slot;
    strncpy_s(e->name, sizeof(e->name), name, _TRUNCATE);
    strncpy_s(e->father, sizeof(e->father), father, _TRUNCATE);
    strncpy_s(e->mother, sizeof(e->mother), mother, _TRUNCATE);
    e->gone = gone;
    return 1;
}

/* Has a line already been given to the elder in this record during this
   save (a line takes the record it was matched in)? */
static int slot_claimed(int slot) {
    int i;
    for (i = 0; i < g_count; ++i) {
        if (g_elders[i].kind == 'E' && g_elders[i].seen && g_elders[i].slot == slot) {
            return 1;
        }
    }
    return 0;
}

#define ELDERS_RECORDS_MAX 256u

/* Could open line `e` be the elder in record `slot` now?  Its own record or the record a reload
   puts it in; `level` 0: and the elder's fingerprint is the one the previous save found for the
   line's villager; 1: and the same name; 2: the record alone. */
static int elder_fits(const struct elders_layout *l, const struct elder *e, unsigned int slot, int level,
                      const char *name) {
    int at_reload;
    if (e->kind != 'E' || !e->open || e->seen || e->slot < 0) {
        return 0;
    }
    at_reload = l->rank_of_slot != NULL && (unsigned int)e->slot < l->rank_slots
        && l->rank_of_slot[e->slot] == (int)slot;
    if (e->slot != (int)slot && !at_reload) {
        return 0;
    }
    if (level == 0) {
        return l->fp_was != NULL && l->fp_now != NULL && (unsigned int)e->slot < l->fp_slots && slot < l->fp_slots
            && l->fp_was[e->slot] != 0u && l->fp_was[e->slot] == l->fp_now[slot];
    }
    return level == 2 || strcmp(e->name, name) == 0;
}

/* Did the previous save find a villager in record `slot`?  (Only when its roster is known.) */
static int elder_record_was_held(const struct elders_layout *l, unsigned int slot) {
    return l->rank_of_slot != NULL && slot < l->rank_slots && l->rank_of_slot[slot] >= 0;
}

static int grave_occupied(const struct elders_layout *l, unsigned int index) {
    int occupancy;
    memcpy(&occupancy, l->graves + index * l->grave_stride + l->grave_occupied, sizeof(occupancy));
    return occupancy != 0;
}

/* The update itself, on explicit paths (the harness passes a temp folder). */
int vv_village_elders_file(int game_id, const wchar_t *path, const wchar_t *temporary,
                           const struct elders_layout *l) {
    wchar_t aside[MAX_PATH];
    unsigned int index;
    unsigned int occupied = 0;
    int fresh;
    int loaded;
    if (l == NULL || path == NULL || temporary == NULL) {
        return -1;
    }
    loaded = load(game_id, path);
    if (loaded < 0) {
        return -1;                    /* locked: leave it untouched, retry next save */
    }
    if (loaded == 0) {
        /* Unreadable: keep it, never overwrite it, take nothing from it. */
        int n;
        int moved = 0;
        for (n = 0; n < 1000 && !moved; ++n) {
            if (_snwprintf_s(aside, MAX_PATH, _TRUNCATE, L"%ls.unreadable-%llu-%d.dat", path,
                             (unsigned long long)GetTickCount64(), n) <= 0) {
                break;
            }
            moved = MoveFileExW(path, aside, 0);   /* never replaces an existing file */
        }
        if (!moved) {
            return -1;                /* cannot preserve it: leave it and report nothing */
        }
        g_count = 0;
        g_graves_seen = -1;
    }
    fresh = g_graves_seen < 0;

    /* The memorial's occupied prefix. */
    if (l->graves != NULL) {
        while (occupied < l->grave_capacity && grave_occupied(l, occupied)) {
            ++occupied;
        }
    }

    /* 1. Living elders, identified by SLOT CONTINUITY, not by name (players
       rename villagers). An E line stays "open" while every save finds an
       elder in its slot; that is the same villager, whatever it is now
       called, so the line follows the new name. A slot is only reused after
       its occupant dies, and a newborn cannot master three skills before the
       next save, so a save always sees the slot empty or holding a
       non-elder in between: the line closes then, and a later elder in that
       slot is a new villager. */
    /* A RELOAD MOVES THEM.  The games save only their occupied records,
       packed, and load them into records 0, 1, 2, ...: after a death and a
       reload every villager behind the dead one is in a lower record (A New
       Home, seen live).  Followed by record alone, an elder who moved from
       record 16 to 15 took over the line of whoever had held 15 -- renamed to
       them -- and an elder moving into a record with no open line was
       counted a second time.  So a line also follows its villager to the
       record the packed load puts it in (l->rank_of_slot, from the roster
       the previous save recorded).  Matching runs in two passes over all the
       living elders: first the same record or that reload record WITH the
       same name, so nobody's line is taken by a neighbour; then the same
       record or reload record alone, which keeps a renamed elder's line. */
    /* ONE TO ONE, NEVER THE FIRST THAT FITS (the identity audit, case 5).  Two elders of one
       name, one renamed and both moved by a reload, swapped lines: the first line in the file
       that fitted a record by its old record and name took it, the renamed elder was added as a
       third, and the other line was closed.  Now a line and an elder are paired only when the
       pairing is the only one possible: first by the roster's fingerprint (what a rename does not
       change: likes, dislikes, the parents' names), then by the name, then by the record alone --
       each time only when the elder fits that one line and the line that one elder, or the elder
       is in a record nobody held at the previous save (a reload put them there: a newborn is
       never an elder by the next save).  What is still not certain is neither added as a new
       elder nor closed: the lines wait for a save that tells them apart. */
    if (l->villagers != NULL) {
        static unsigned char is_elder[ELDERS_RECORDS_MAX];
        static char names[ELDERS_RECORDS_MAX][NAME_MAX_CHARS];
        static char fathers[ELDERS_RECORDS_MAX][NAME_MAX_CHARS];
        static char mothers[ELDERS_RECORDS_MAX][NAME_MAX_CHARS];
        static signed char taken[ELDERS_RECORDS_MAX];
        unsigned int slot;
        unsigned int records = l->slots < ELDERS_RECORDS_MAX ? l->slots : ELDERS_RECORDS_MAX;
        int i;
        int level;
        int progress;
        for (i = 0; i < g_count; ++i) {
            g_elders[i].seen = 0;
        }
        for (slot = 0; slot < records; ++slot) {
            const unsigned char *record = l->villagers + l->record_base + slot * l->stride;
            is_elder[slot] = 0;
            taken[slot] = 0;
            if (record[l->active] != 1 || vv_lookalike(l->stride, record)
                || mastered_skills(record, l) < 3 || slot_claimed((int)slot)) {
                continue;
            }
            /* Only the player's own villagers: New Believers keeps its
               heathens in the same array, and the Heathen Chief is born with
               every skill at 100 -- a live read showed him as the village's
               only "elder". A converted heathen joins the tribe and counts. */
            if (l->tribe != 0u && record[l->tribe] != 0) {
                continue;
            }
            is_elder[slot] = 1;
            copy_name(names[slot], record + l->name, l->name_capacity);
            copy_name(fathers[slot], l->father_name ? record + l->father_name : NULL, l->parent_name_capacity);
            copy_name(mothers[slot], l->mother_name ? record + l->mother_name : NULL, l->parent_name_capacity);
        }
        do {
            progress = 0;
            for (level = 0; level < 3 && !progress; ++level) {
                for (slot = 0; slot < records; ++slot) {
                    int line = -1, count = 0, back = 0;
                    if (!is_elder[slot] || taken[slot]) {
                        continue;
                    }
                    for (i = 0; i < g_count; ++i) {
                        if (elder_fits(l, &g_elders[i], slot, level, names[slot])) {
                            line = i;
                            ++count;
                        }
                    }
                    if (count != 1) {
                        continue;
                    }
                    /* ...and that line fits no other elder, unless this record was nobody's at the
                       previous save (a reload put this elder here). */
                    if (!(l->rank_of_slot != NULL && slot < l->rank_slots && !elder_record_was_held(l, slot))) {
                        unsigned int other;
                        for (other = 0; other < records; ++other) {
                            if (other != slot && is_elder[other] && !taken[other]
                                && elder_fits(l, &g_elders[line], other, level, names[other])) {
                                ++back;
                            }
                        }
                        if (back != 0) {
                            continue;
                        }
                    }
                    /* the same villager: keep the line current through renames and the record it
                       is in now */
                    g_elders[line].slot = (int)slot;
                    strncpy_s(g_elders[line].name, sizeof(g_elders[line].name), names[slot], _TRUNCATE);
                    strncpy_s(g_elders[line].father, sizeof(g_elders[line].father), fathers[slot], _TRUNCATE);
                    strncpy_s(g_elders[line].mother, sizeof(g_elders[line].mother), mothers[slot], _TRUNCATE);
                    g_elders[line].seen = 1;
                    taken[slot] = 1;
                    progress = 1;
                }
            }
        } while (progress);
        /* An elder no open line could be is a new elder; one some open line could still be is
           not certain, and waits. */
        for (slot = 0; slot < records; ++slot) {
            int maybe = 0;
            if (!is_elder[slot] || taken[slot]) {
                continue;
            }
            for (i = 0; i < g_count && !maybe; ++i) {
                maybe = elder_fits(l, &g_elders[i], slot, 2, names[slot]);
            }
            if (maybe) {
                taken[slot] = -1;
            } else if (add('E', (int)slot, names[slot], fathers[slot], mothers[slot], 0)) {
                g_elders[g_count - 1].open = 1;
                g_elders[g_count - 1].seen = 1;
                taken[slot] = 1;
            }
        }
        for (i = 0; i < g_count; ++i) {
            if (g_elders[i].kind == 'E' && g_elders[i].open && !g_elders[i].seen) {
                int waits = 0;
                for (slot = 0; slot < records && !waits; ++slot) {
                    waits = taken[slot] == -1 && elder_fits(l, &g_elders[i], slot, 2, names[slot]);
                }
                if (!waits) {
                    g_elders[i].open = 0;   /* the slot no longer holds this elder */
                }
            }
        }
    }

    /* 2./3. Graves the game flagged as elders. */
    if (l->graves != NULL && l->grave_elder_flag != 0u) {
        unsigned int first = fresh ? 0u : (unsigned int)g_graves_seen;
        for (index = first; index < occupied; ++index) {
            const unsigned char *grave = l->graves + index * l->grave_stride;
            char name[NAME_MAX_CHARS];
            int i;
            int matched = 0;
            if (grave[l->grave_elder_flag] == 0) {
                continue;
            }
            copy_name(name, grave + l->grave_name, l->grave_name_capacity);
            if (!fresh) {
                for (i = 0; i < g_count && !matched; ++i) {
                    struct elder *e = &g_elders[i];
                    if (e->kind == 'E' && !e->gone && !e->open && strcmp(e->name, name) == 0) {
                        e->gone = 1;
                        matched = 1;
                    }
                }
            }
            if (!matched) {
                add('G', -1, name, "", "", 1);
            }
        }
    }
    if (l->graves != NULL) {
        g_graves_seen = (int)occupied;
    } else if (g_graves_seen < 0) {
        g_graves_seen = 0;
    }
    if (!save(game_id, path, temporary)) {
        return -1;
    }
    return g_count;
}

int vv_village_elders(int game_id, int save_id, const struct elders_layout *l) {
    wchar_t path[MAX_PATH];
    wchar_t temporary[MAX_PATH];
    if (!path_for(save_id, path, L".dat") || !path_for(save_id, temporary, L".tmp")) {
        return -1;
    }
    return vv_village_elders_file(game_id, path, temporary, l);
}
