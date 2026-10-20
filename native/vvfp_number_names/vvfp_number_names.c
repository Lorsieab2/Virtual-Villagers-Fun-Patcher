/* VVFP Number Names -- a baby born with the full name of a living villager
   is numbered at its birth (all five games).

   The owner, 2026-10-20: numbering villagers who share a full name ("Chip
   Kenobi I", "Chip Kenobi II", ...) "must be ON BY DEFAULT" and done
   automatically, "so names are numbered in the game and in every log", as a
   per-village setting.  The patcher's Number Duplicate Names
   (src/vv_number_names.py) numbers everyone the save and the logs know --
   the living, the dead and the gone -- oldest first (in order of
   appearance), and Repair Saves & Logs runs it by itself while the
   village's setting is on.  This companion does the part only the running
   game can do: the moment a baby is named, before its Birth record or
   anything else names it.

   WHAT IT DOES.  Called with the new child's record (VvfpNumberNewName,
   below) by the companion that writes its Birth record -- "VVFP Parentage
   Export.dll" in The Lost Children to New Believers, "VVFP VV1
   Parentage.dll" in A New Home -- right after the player's last-name rule
   has been given (VVFP Last Names.dll's VvfpRuleLastName2), so the name
   numbered is the name the child keeps.  When another living villager of the
   village has that same full name (their own name without the Roman numeral
   Number Duplicate Names gave it -- "Chip Kenobi II" is a Chip Kenobi), the
   child is given the next number after the highest such villager holds, an
   unnumbered one counting as I: a living "Chip Kenobi" makes the baby "Chip
   Kenobi II"; a living "Chip Kenobi I" and "Chip Kenobi III", "Chip Kenobi
   IV".  A name that is no one else's keeps its name (a Roman number only for
   real duplicates, the owner, 2026-10-08).

   WHAT IT LEAVES TO THE PATCHER.  The villager who already had the name is
   never renamed here: while the game runs, renaming a living villager would
   leave every file that names them (the logs, the titles, the last-name
   rules, the statistics roster) behind until the next save.  The next
   Repair Saves & Logs makes them "I" -- in the save and every log at once,
   backed up first -- along with the dead, whom the running game does not
   hold.  Nor is a name numbered that would not fit the game's limit (27
   characters in A New Home, 23 in the other games: src/vv_last_names.py
   ROOM), or a baby whose own name already ends in a numeral: those are left
   as they are, and Repair Saves & Logs shows them to the player.  Villagers
   who join without being born (island events, the Barrel) are not numbered
   here: they are given their own last name at the next Repair Saves & Logs
   (arrivals), which is then numbered if it is still shared.

   WHO IS LIVING.  Every record of the village's table flagged active,
   except the ones each game keeps that are no villagers
   (native/shared/villager_lookalike.h: statues, ghosts, stand-ins), and the
   child itself.  The caller passes the table's geometry (its own layout
   table, which the population exporter measured).

   THE SETTING.  Repair Saves & Logs keeps it per village in
       <save folder>\Virtual Villagers Fun Patcher\Save <slot>\Data\
           Number Names\Virtual Villagers <game> Number Names - Save <slot>.dat
   (or the older layout's "Virtual Villagers Fun Patcher Data\Number Names",
   native/shared/per_save.h): "VVFP NUMBER NAMES v1 game=<game>", then
   "auto\ton" or "auto\toff".  No file is ON.  A birth whose village is not
   known yet (slot 0: the catch-up as a village loads, before its first save
   names it) is numbered only when no save of this game has the setting off.

   Nothing in a save changes shape: the number is part of the name the game
   itself stores.  Every failure leaves the name as the game gave it. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include "../shared/per_save.h"            /* one folder per save */
#include "../shared/villager_lookalike.h"  /* statues, ghosts and stand-ins are no villagers */

#define GAMES 5
#define NAME_MAX_BYTES 64
#define SETTING_MAX 4096
#define SLOTS_KNOWN 5

/* The longest name each game's records keep whole (src/vv_last_names.py ROOM). */
static const unsigned int ROOM[GAMES + 1] = { 0, 27, 23, 23, 23, 23 };

/* "<My Documents>\LDW\<exe name>": the game's save folder, as every companion
   finds it.  0 when it cannot be named. */
static int save_folder(char *out, size_t size) {
    char docs[MAX_PATH], exe[MAX_PATH];
    char *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)
        || GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) {
        return 0;
    }
    exe[MAX_PATH - 1] = '\0';
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) {
        *dot = '\0';
    }
    if (_snprintf(out, size, "%s\\LDW\\%s", docs, base) <= 0) {
        return 0;
    }
    out[size - 1] = '\0';
    return 1;
}

/* The setting of `slot`: 1 on, 0 off.  No file, a file of another kind or
   without an "auto" line: on. */
static int slot_is_on(int game, int slot) {
    char folder[MAX_PATH], path[MAX_PATH * 2], text[SETTING_MAX + 1], header[48];
    const char *line;
    HANDLE h;
    DWORD got = 0;
    if (!save_folder(folder, sizeof folder)
        || _snprintf(path, sizeof path, "%s\\Virtual Villagers Fun Patcher Data\\Number Names\\"
                     "Virtual Villagers %d Number Names - Save %d.dat", folder, game, slot) <= 0) {
        return 1;
    }
    path[sizeof path - 1] = '\0';
    (void)vv_ps_route_a(path, MAX_PATH - 16, 0);
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 1;
    }
    if (!ReadFile(h, text, SETTING_MAX, &got, NULL)) {
        got = 0;
    }
    CloseHandle(h);
    text[got] = '\0';
    _snprintf(header, sizeof header, "VVFP NUMBER NAMES v1 game=%d", game);
    header[sizeof header - 1] = '\0';
    if (strncmp(text, header, strlen(header)) != 0
        || (text[strlen(header)] != '\n' && text[strlen(header)] != '\r')) {
        return 1;
    }
    for (line = text; line != NULL; line = strchr(line, '\n') ? strchr(line, '\n') + 1 : NULL) {
        size_t n = strcspn(line, "\r\n");
        if (n == 8 && strncmp(line, "auto\toff", 8) == 0) {
            return 0;
        }
        if (n == 7 && strncmp(line, "auto\ton", 7) == 0) {
            return 1;
        }
    }
    return 1;
}

static int numbering_is_on(int game, int slot) {
    int s;
    if (slot >= 1 && slot <= 9) {
        return slot_is_on(game, slot);
    }
    for (s = 1; s <= SLOTS_KNOWN; ++s) {      /* village not known yet: only when no save says off */
        if (!slot_is_on(game, s)) {
            return 0;
        }
    }
    return 1;
}

/* The value of a Roman numeral word of `n` letters (I V X L C D M only); 0
   when it is not one. */
static int roman_value(const char *word, size_t n) {
    static const char letters[] = "IVXLCDM";
    static const int values[] = { 1, 5, 10, 50, 100, 500, 1000 };
    int total = 0;
    size_t i;
    if (n == 0) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        const char *at = strchr(letters, word[i]);
        const char *next = i + 1 < n ? strchr(letters, word[i + 1]) : NULL;
        int v;
        if (word[i] == '\0' || at == NULL || (i + 1 < n && next == NULL)) {
            return 0;
        }
        v = values[at - letters];
        total += (next != NULL && values[next - letters] > v) ? -v : v;
    }
    return total > 0 ? total : 0;
}

static void roman(int n, char *out) {
    static const int values[] = { 1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1 };
    static const char *const letters[] = { "M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I" };
    int k;
    out[0] = '\0';
    for (k = 0; k < 13; ++k) {
        while (n >= values[k]) {
            strcat(out, letters[k]);
            n -= values[k];
        }
    }
}

/* `name` without the numeral Number Duplicate Names gives (its last word, of
   a name of two words or more, when that word is all I V X L C D M):
   vv_genealogy.unnumbered.  The base goes to `base`; the numeral's value is
   returned (0 for none). */
static int split_numbered(const char *name, char *base, size_t size) {
    const char *space = strrchr(name, ' ');
    size_t n = strlen(name);
    int value = 0;
    if (space != NULL && space != name) {
        size_t word = n - (size_t)(space + 1 - name);
        size_t k;
        int all = word > 0;
        for (k = 0; k < word; ++k) {
            if (strchr("IVXLCDM", space[1 + k]) == NULL) {
                all = 0;
            }
        }
        if (all) {
            value = roman_value(space + 1, word);
            if (value == 0) {
                value = 1;                  /* a numeral the rule did not write: counted, as the patcher does */
            }
            n = (size_t)(space - name);
        }
    }
    if (n + 1 > size) {
        n = size - 1;
    }
    memcpy(base, name, n);
    base[n] = '\0';
    return value;
}

/* A record's name, terminated within its field. */
static void name_of(const unsigned char *record, unsigned int at, unsigned int capacity, char *out) {
    unsigned int k;
    for (k = 0; k < capacity && k + 1 < NAME_MAX_BYTES && record[at + k] != 0; ++k) {
        out[k] = (char)record[at + k];
    }
    out[k] = '\0';
}

static int readable(const void *at, size_t size) {
    MEMORY_BASIC_INFORMATION info;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
        return 0;
    }
    return (const unsigned char *)at + size <= (const unsigned char *)info.BaseAddress + info.RegionSize;
}

/* The baby `child` (a record of the table whose first record is `first`:
   `slots` records of `stride` bytes, each with its active byte at `active`
   and its name of `capacity` bytes at `name`) given the next number when a
   living villager has its full name.  `slot`: the village's save slot, 0 when
   not known yet.  Returns 1 when the name changed. */
__declspec(dllexport) int __stdcall VvfpNumberNewName(int game, unsigned char *child, const unsigned char *first,
                                                      unsigned int stride, int slots, unsigned int active,
                                                      unsigned int name, unsigned int capacity, int slot) {
    char mine[NAME_MAX_BYTES], other[NAME_MAX_BYTES], base[NAME_MAX_BYTES], numeral[32];
    char numbered[NAME_MAX_BYTES + 32];
    int i, highest = 0;
    size_t span;
    if (game < 1 || game > GAMES || child == NULL || first == NULL || stride == 0 || slots <= 0 || slots > 4096
        || capacity == 0 || capacity >= NAME_MAX_BYTES || name + capacity > stride || active >= stride
        || child < first) {
        return 0;
    }
    span = (size_t)(child - first);
    if (span % stride != 0 || span / stride >= (size_t)slots || !readable(first, (size_t)slots * stride)) {
        return 0;                               /* not one of the table's own records */
    }
    if (memchr(child + name, '\0', capacity) == NULL) {
        return 0;
    }
    name_of(child, name, capacity, mine);
    if (mine[0] == '\0' || split_numbered(mine, base, sizeof base) != 0) {
        return 0;                               /* no name, or one already numbered: left as it is */
    }
    for (i = 0; i < slots; ++i) {
        const unsigned char *r = first + (size_t)i * stride;
        int value;
        if (r == child || r[active] != 1 || vv_lookalike(stride, r)) {
            continue;
        }
        name_of(r, name, capacity, other);
        value = split_numbered(other, base, sizeof base);
        if (strcmp(base, mine) == 0 && (value ? value : 1) > highest) {
            highest = value ? value : 1;
        }
    }
    if (highest == 0 || highest >= 3999 || !numbering_is_on(game, slot)) {
        return 0;                               /* no living namesake, or the village's setting is off */
    }
    roman(highest + 1, numeral);
    if (_snprintf(numbered, sizeof numbered, "%s %s", mine, numeral) <= 0
        || strlen(numbered) > ROOM[game] || strlen(numbered) + 1 > capacity) {
        return 0;                               /* no room: left for Repair Saves & Logs to show */
    }
    memset(child + name, 0, capacity);
    memcpy(child + name, numbered, strlen(numbered));
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
