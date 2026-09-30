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

       VVFP VILLAGE ELDERS v1 game=<1..5>
       graves_seen=<memorial entries already examined>
       E<TAB>slot<TAB>name<TAB>father<TAB>mother<TAB>gone
       G<TAB>-1<TAB>name<TAB><TAB><TAB>1

   One line per elder. "E" = seen alive holding the status (slot index in the
   villager array, the villager's name, and -- where the record stores them --
   both parents' names; none of these change during a life, unlike age,
   skills, appearance or likes). "gone" = 1 once that villager has been
   matched to their grave. "G" = an elder known only from a grave the game
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
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#include "save_folder.h"
#include "village_elders.h"

#define ELDERS_MAX 4096
#define NAME_MAX_CHARS 40

struct elder {
    char kind;                      /* 'E' or 'G' */
    int slot;
    char name[NAME_MAX_CHARS];
    char father[NAME_MAX_CHARS];
    char mother[NAME_MAX_CHARS];
    int gone;
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

static int same_identity(const struct elder *e, int slot, const char *name,
                         const char *father, const char *mother) {
    return e->kind == 'E' && e->slot == slot && strcmp(e->name, name) == 0
        && strcmp(e->father, father) == 0 && strcmp(e->mother, mother) == 0;
}

static int path_for(int save_id, wchar_t *path, const wchar_t *suffix) {
    wchar_t folder[MAX_PATH];
    if (!vv_save_subfolder_w(folder, L"Virtual Villagers Fun Patcher Data\\Village Elders", 64)) {
        return 0;
    }
    return _snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%ls\\Village Elders - Save %d%ls",
                        folder, save_id, suffix) > 0;
}

/* 1 = loaded (or absent: empty history), 0 = unreadable (moved aside). */
static int load(int game_id, const wchar_t *path) {
    FILE *f;
    char line[512];
    char header[64];
    g_count = 0;
    g_graves_seen = -1;               /* -1: no history yet */
    if (_wfopen_s(&f, path, L"rb") != 0 || f == NULL) {
        return 1;                     /* missing file: new, empty history */
    }
    _snprintf_s(header, sizeof(header), _TRUNCATE, "VVFP VILLAGE ELDERS v1 game=%d", game_id);
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
        char *fields[6];
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
        while (*cursor != '\0' && n < 6) {
            if (*cursor == '\t') {
                *cursor = '\0';
                fields[n++] = cursor + 1;
            }
            ++cursor;
        }
        if (n != 6 || (fields[0][0] != 'E' && fields[0][0] != 'G') || fields[0][1] != '\0'
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
        g_elders[g_count++] = e;
    }
    fclose(f);
    return 1;
}

static int save(int game_id, const wchar_t *path, const wchar_t *temporary) {
    FILE *f;
    int i;
    if (_wfopen_s(&f, temporary, L"wb") != 0 || f == NULL) {
        return 0;
    }
    fprintf(f, "VVFP VILLAGE ELDERS v1 game=%d\r\ngraves_seen=%d\r\n", game_id, g_graves_seen);
    for (i = 0; i < g_count; ++i) {
        const struct elder *e = &g_elders[i];
        fprintf(f, "%c\t%d\t%s\t%s\t%s\t%d\r\n", e->kind, e->slot, e->name, e->father, e->mother, e->gone);
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

/* Is the villager an E line describes still alive in its slot? */
static int still_alive(const struct elder *e, const struct elders_layout *l) {
    const unsigned char *record;
    char name[NAME_MAX_CHARS];
    if (l->villagers == NULL || e->slot < 0 || (unsigned int)e->slot >= l->slots) {
        return 0;
    }
    record = l->villagers + l->record_base + (unsigned int)e->slot * l->stride;
    if (record[l->active] != 1) {
        return 0;
    }
    copy_name(name, record + l->name, l->name_capacity);
    return strcmp(name, e->name) == 0;
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
    if (l == NULL || path == NULL || temporary == NULL) {
        return -1;
    }
    if (!load(game_id, path)) {
        /* Unreadable: keep it, never overwrite it, take nothing from it. */
        if (_snwprintf_s(aside, MAX_PATH, _TRUNCATE, L"%ls.unreadable-%llu.dat", path,
                         (unsigned long long)GetTickCount64()) <= 0
            || !MoveFileExW(path, aside, 0)) {
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

    /* 1. Living elders. */
    if (l->villagers != NULL) {
        unsigned int slot;
        for (slot = 0; slot < l->slots; ++slot) {
            const unsigned char *record = l->villagers + l->record_base + slot * l->stride;
            char name[NAME_MAX_CHARS];
            char father[NAME_MAX_CHARS];
            char mother[NAME_MAX_CHARS];
            int i;
            int known = 0;
            if (record[l->active] != 1 || mastered_skills(record, l) < 3) {
                continue;
            }
            copy_name(name, record + l->name, l->name_capacity);
            copy_name(father, l->father_name ? record + l->father_name : NULL, l->parent_name_capacity);
            copy_name(mother, l->mother_name ? record + l->mother_name : NULL, l->parent_name_capacity);
            for (i = 0; i < g_count && !known; ++i) {
                known = same_identity(&g_elders[i], (int)slot, name, father, mother);
            }
            if (!known) {
                add('E', (int)slot, name, father, mother, 0);
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
                    if (e->kind == 'E' && !e->gone && strcmp(e->name, name) == 0 && !still_alive(e, l)) {
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
