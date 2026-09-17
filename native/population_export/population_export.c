/* VVFP Village Population Export -- a roster snapshot of the living village.

   WHAT THIS IS

   The owner asked for "a log of all the villagers in the village with their:
   Name / head and body value / Parents names, head and body value if present /
   Likes and Dislikes / Skill values and fields", titled "Village Population",
   with "text files hold 256 villagers each".

   WHY A SNAPSHOT RATHER THAN A TRACKED LOG

   The request began as "record the resulting children's names for each
   pregnancy", which needed a way to know which children had already been
   logged. No such key exists: scanning every four-byte field across all 91
   villagers in one of the owner's VV5 saves found ZERO offsets unique across
   all of them, 79 distinct names among 91 villagers, and only 5 distinct
   values in the id field. A once-only guard would therefore have required a
   new per-villager flag written into the save, in four games.

   A snapshot needs none of that, because it does not care what it wrote last
   time. It enumerates the array and writes every live slot. The owner's own
   framing is what makes this sufficient: "the logs don't need to be
   complicated. players can match all the parentage and village logs to see
   whos who." Correlation is the reader's job, not the exporter's.

   WHICH GAMES

   VV3, VV4 and VV5. Their villager arrays sit at fixed module RVAs that the
   statistics companion already uses for the Village Elders row, so the array
   is reachable from the save hook with no new plumbing.

   VV1 AND VV2 ARE ABSENT ON PURPOSE. Their arrays are not reachable from any
   existing hook. VV1's conception routine is __thiscall and its `this` IS the
   array -- `array + 0x3E010` reaches the manager, which does not invert -- and
   its statistics hook at 0x41BF63 holds the save-state blob, not the array.
   Neither game has an established array RVA. Guessing one would walk 256
   records of arbitrary memory, so they wait for that measurement rather than
   shipping a plausible wrong base.

   WHAT IS NOT LOGGED, AND WHY

   Likes and dislikes. The strings exist in all five games and are genuine UI
   -- in VV5 they are string-table entries eSayLikes (id 0x1AC) and
   eSayDislikes (0x1AD), both referenced from the Details-panel builder. But
   those references place the LABEL. Disassembling the whole panel builder
   (0x43DC00..0x43DF00) and looking for any memory read with a displacement in
   the villager-record range 0x1000..0x2000 returns zero; its 31 calls are all
   widget construction, string-manager access and allocation, and it stores its
   widgets into [esi+0x74] and [esi+0x78] where esi is the panel, not a
   villager.

   So it is NOT established that a villager record stores a likes or dislikes
   value. The labels are reachable and the panel builder reads nothing from a
   villager record; where the displayed value comes from is unresolved. Those
   two fields are omitted rather than guessed. */

#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

enum {
    GAME_VV1 = 1,
    GAME_VV2 = 2,
    GAME_VV3 = 3,
    GAME_VV4 = 4,
    GAME_VV5 = 5,

    MAX_LONG_PATH = 32768,

    /* A fixed local bound for a name, checked against each game's own
       name_capacity before use, so a game with a longer field fails the guard
       rather than overrunning the buffer. */
    MAX_NAME_BYTES = 64,

    /* The owner asked for "text files hold 256 villagers each". Every
       supported game's array is 150 slots, so in practice one file holds a
       whole village -- but the roll is implemented rather than assumed, so a
       game with a larger array does not silently truncate. */
    VILLAGERS_PER_FILE = 256,

    /* No game has more skills than this. Checked per game below. */
    MAX_SKILLS = 8
};

/* Per-game record geometry.

   Every offset here is already established and in use by a shipped companion,
   with the instruction that proves it recorded at its original site rather
   than restated here -- a second copy is exactly what went stale last time
   this file's sibling carried one.

   The villager array base, record base, stride, slots, active flag and skill
   table all come from the statistics companion's Village Elders row
   (native/statistics_export/statistics_export.c). Name, head and body come
   from the parentage companion's layout table
   (native/parentage_export/parentage_export.c). The father name offset is the
   copy each game makes onto the mother at conception. */
struct game_layout {
    int supported;
    unsigned int villagers_rva;   /* from the module base */
    unsigned int record_base;     /* container header before slot 0 */
    unsigned int stride;
    unsigned int slots;
    unsigned int active;          /* u8, == 1 when the slot is live */
    unsigned int age;             /* i32 */
    unsigned int head;            /* i32 */
    unsigned int body;            /* i32 */
    unsigned int name;            /* char[name_capacity] */
    unsigned int name_capacity;
    /* The father's details, copied onto the MOTHER at conception. Present in
       VV3/VV4/VV5; this is the "if present" the owner's spec allows for.
       Zero means the game copies nothing. */
    unsigned int father_name;
    unsigned int father_name_capacity;
    unsigned int father_head;
    unsigned int father_body;
    unsigned int skills;          /* i32[skill_count] or float[skill_count] */
    unsigned int skill_count;
    int skills_are_float;
    const char *title;
};

static const struct game_layout GAME_LAYOUTS[6] = {
    /* index 0 unused so a game id indexes directly */
    { 0 },
    /* VV1 -- array not reachable from any existing hook; see the header. */
    { 0 },
    /* VV2 -- same. */
    { 0 },
    /* VV3 -- The Secret City. Skills are INT32 here and the game's own
       predicate compares against 0x58, so the float path must not be used. */
    {
        1, 0x19E110u, 0x14u, 0x1F8Cu, 150u,
        0xF10u, 0xDC4u, 0xDF0u, 0xDF4u,
        0xDD4u, 0x19u,
        0xE48u, 0x18u, 0xE68u, 0xE64u,
        0xEACu, 5u, 0,
        "Virtual Villagers 3"
    },
    /* VV4 -- The Tree of Life. */
    {
        1, 0x10E568u, 0x44u, 0x2E3Cu, 150u,
        0x1CC4u, 0x1B8Cu, 0x1BB8u, 0x1BBCu,
        0x1B9Cu, 0x19u,
        0x1C10u, 0x18u, 0x1C30u, 0x1C2Cu,
        0x1C5Cu, 5u, 1,
        "Virtual Villagers 4"
    },
    /* VV5 -- New Believers. Six skills, one more than VV3 and VV4. */
    {
        1, 0x154148u, 0x48u, 0x2F44u, 150u,
        0x1CD4u, 0x1B8Cu, 0x1BB8u, 0x1BBCu,
        0x1B9Cu, 0x19u,
        0x1C10u, 0x18u, 0x1C30u, 0x1C2Cu,
        0x1C5Cu, 6u, 1,
        "Virtual Villagers 5"
    }
};

/* The skill names, in the order the games store them.

   VV5 has six and the other two have five; VV5's extra slot is last, so the
   first five are shared. These are the names the games' own UI uses. */
static const char *const SKILL_NAMES[MAX_SKILLS] = {
    "Farming", "Building", "Research", "Healing", "Breeding", "Parenting",
    "(skill 7)", "(skill 8)"
};

/* Reject a layout whose geometry is not self-consistent.

   A wrong offset does not crash, it silently logs the wrong number -- and a
   roster of 150 wrong numbers looks exactly like a roster of right ones. So
   every field must fit inside the record before anything is read. */
static int layout_is_sane(const struct game_layout *g) {
    const unsigned int WORD = 4u;
    if (!g->supported || g->stride == 0u || g->slots == 0u) {
        return 0;
    }
    if (g->name_capacity == 0u || g->name_capacity + 1u > MAX_NAME_BYTES) {
        return 0;
    }
    if (g->skill_count == 0u || g->skill_count > MAX_SKILLS) {
        return 0;
    }
    if (g->active + 1u > g->stride) return 0;
    if (g->age + WORD > g->stride) return 0;
    if (g->head + WORD > g->stride) return 0;
    if (g->body + WORD > g->stride) return 0;
    if (g->name + g->name_capacity > g->stride) return 0;
    if (g->skills + g->skill_count * WORD > g->stride) return 0;
    /* The father block is optional, but if any part of it is declared the
       whole of it must be, and must fit. Half a block would print a name
       beside somebody else's appearance. */
    if (g->father_name != 0u || g->father_head != 0u || g->father_body != 0u) {
        if (g->father_name == 0u || g->father_head == 0u
                || g->father_body == 0u || g->father_name_capacity == 0u) {
            return 0;
        }
        if (g->father_name_capacity + 1u > MAX_NAME_BYTES) return 0;
        if (g->father_name + g->father_name_capacity > g->stride) return 0;
        if (g->father_head + WORD > g->stride) return 0;
        if (g->father_body + WORD > g->stride) return 0;
    }
    return 1;
}

/* Copy a fixed-width, possibly unterminated name field and force a
   terminator. The games do not guarantee one: VV1's copier is sprintf with
   count 0x7FFFFFFF, and the conception copy writes 0x18 bytes into a 0x19
   field, so byte 25 can be stale. */
static void copy_name_field(
    const unsigned char *source,
    unsigned int capacity,
    char *destination,
    size_t destination_size
) {
    size_t limit = capacity < destination_size - 1
        ? (size_t)capacity
        : destination_size - 1;
    memcpy(destination, source, limit);
    destination[limit] = '\0';
}

/* Build "<exe folder>\Village Population <n>.txt". */
static int build_log_path(int index, wchar_t *path) {
    wchar_t module_path[MAX_LONG_PATH];
    wchar_t *separator;
    DWORD length = GetModuleFileNameW(NULL, module_path, MAX_LONG_PATH);
    if (length == 0 || length >= MAX_LONG_PATH) {
        return 0;
    }
    separator = wcsrchr(module_path, L'\\');
    if (separator == NULL) {
        return 0;
    }
    *separator = L'\0';
    if (_snwprintf_s(
            path, MAX_LONG_PATH, _TRUNCATE,
            L"%ls\\Village Population %d.txt", module_path, index) < 0) {
        return 0;
    }
    return 1;
}

/* Write one villager's block. Returns 0 on any write failure. */
static int write_villager(
    FILE *file,
    const struct game_layout *g,
    const unsigned char *record,
    int number
) {
    char name[MAX_NAME_BYTES];
    unsigned int skill;

    copy_name_field(record + g->name, g->name_capacity, name, sizeof(name));

    if (fprintf(file, "Villager %d\n", number) < 0) return 0;
    if (fprintf(file, "  Name: %s\n", name) < 0) return 0;
    if (fprintf(file, "  Age: %d\n", *(const int *)(record + g->age)) < 0) {
        return 0;
    }
    if (fprintf(file, "  Head: %d\n", *(const int *)(record + g->head)) < 0) {
        return 0;
    }
    if (fprintf(file, "  Body: %d\n", *(const int *)(record + g->body)) < 0) {
        return 0;
    }

    /* Parents, where the game recorded them.

       Only the FATHER's details are stored on a villager, and only on a
       mother carrying his child -- the games copy his name, head and body
       onto her at conception and never store a mother's own parents. So this
       block is a pregnancy's father, present on some records and absent on
       others, which is exactly the "if present" the request allows for.

       An all-zero name means nothing was ever copied: a real name always has
       a first byte, and zero there cannot be a name. Head and body are NOT
       used for that test -- 0 is a valid head and a valid body, so a father
       genuinely at row 0 would be discarded by a zero check on them. */
    if (g->father_name != 0u && record[g->father_name] != '\0') {
        char father[MAX_NAME_BYTES];
        copy_name_field(record + g->father_name, g->father_name_capacity,
                        father, sizeof(father));
        if (fprintf(file, "  Father: %s\n", father) < 0) return 0;
        if (fprintf(file, "    Head: %d\n",
                    *(const int *)(record + g->father_head)) < 0) {
            return 0;
        }
        if (fprintf(file, "    Body: %d\n",
                    *(const int *)(record + g->father_body)) < 0) {
            return 0;
        }
    }

    if (fprintf(file, "  Skills:\n") < 0) return 0;
    for (skill = 0; skill < g->skill_count; ++skill) {
        const unsigned char *field = record + g->skills + skill * 4u;
        /* Rendered as an integer either way. The float games store a 0..100
           scale and the int game stores the same range, so truncating keeps
           one column shape across all three rather than printing 88 in one
           game and 88.000000 in another. */
        int value = g->skills_are_float
            ? (int)*(const float *)field
            : *(const int *)field;
        if (fprintf(file, "    %-10s %d\n", SKILL_NAMES[skill], value) < 0) {
            return 0;
        }
    }

    return fprintf(file, "\n") >= 0;
}

/* Write every living villager, rolling to a new file every 256.

   Returns the number of villagers written, or 0 on failure. Zero is also the
   honest answer for an empty village, which cannot be distinguished from a
   failure by the return value alone -- the caller treats both the same way,
   because neither is actionable from inside the game. */
__declspec(dllexport) int __stdcall WriteVillagePopulation(
    int game_id,
    const void *module_pointer
) {
    const struct game_layout *g;
    const unsigned char *module = (const unsigned char *)module_pointer;
    const unsigned char *villagers;
    unsigned int index;
    int written = 0;
    int file_index = 1;
    int in_file = 0;
    FILE *file = NULL;
    wchar_t path[MAX_LONG_PATH];

    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    g = &GAME_LAYOUTS[game_id];
    if (!layout_is_sane(g)) {
        return 0;
    }
    if (module == NULL) {
        module = (const unsigned char *)GetModuleHandleW(NULL);
    }
    if (module == NULL) {
        return 0;
    }
    villagers = module + g->villagers_rva;

    for (index = 0; index < g->slots; ++index) {
        const unsigned char *record =
            villagers + g->record_base + index * g->stride;
        if (*(const unsigned char *)(record + g->active) != 1) {
            continue;
        }
        if (file == NULL) {
            if (!build_log_path(file_index, path)) {
                return 0;
            }
            /* Truncating, not appending: this is a SNAPSHOT of the village as
               it stands, so the previous snapshot is superseded rather than
               accumulated. Appending would grow without bound across saves
               and would make the file describe several different moments at
               once, which is the opposite of what a roster is for. */
            file = _wfopen(path, L"w");
            if (file == NULL) {
                return 0;
            }
            if (fprintf(file, "%s Village Population\n\n", g->title) < 0) {
                fclose(file);
                return 0;
            }
        }
        if (!write_villager(file, g, record, written + 1)) {
            fclose(file);
            return 0;
        }
        ++written;
        ++in_file;
        if (in_file >= VILLAGERS_PER_FILE) {
            /* Flush before closing so a write error is seen while it can
               still fail the whole call, rather than being swallowed by
               fclose and leaving a truncated file reported as complete. */
            if (fflush(file) != 0 || fclose(file) != 0) {
                return 0;
            }
            file = NULL;
            in_file = 0;
            ++file_index;
        }
    }

    if (file != NULL) {
        if (fflush(file) != 0) {
            fclose(file);
            return 0;
        }
        if (fclose(file) != 0) {
            return 0;
        }
    }
    return written;
}
