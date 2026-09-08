#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

enum {
    GAME_VV1 = 1,
    GAME_VV2 = 2,
    GAME_VV3 = 3,
    GAME_VV4 = 4,
    GAME_VV5 = 5,
    MAX_LONG_PATH = 32768
};

static int read_int(const unsigned char *manager, unsigned int offset) {
    return *(const int *)(manager + offset);
}

static int count_flags(
    const unsigned char *manager,
    const unsigned int *offsets,
    int count
) {
    int total = 0;
    int index;
    for (index = 0; index < count; ++index) {
        if (*(const unsigned char *)(manager + offsets[index]) != 0) {
            ++total;
        }
    }
    return total;
}

/* Count the graves a game is currently holding.

   Each later game keeps its memorial as a flat array reached through a small
   bounds-checked accessor, and those accessors hand over the whole layout.
   VV4's, at 0x45D650, is nine instructions: index bounded by 0x1F3, stride
   0x5C, and a record treated as EMPTY when its dword at +0x1C is zero.  VV5's
   at 0x464E70 is instruction-for-instruction identical.  VV3's at 0x454AD0
   computes the same thing with lea/shl instead of imul, giving stride 0x30 and
   capacity 500, with the occupancy field again at +0x1C.

   That +0x1C field is the villager's age at death, copied out of the record by
   each game's burial writer (VV4 0x45D470, VV3 0x454FF0), which fills the FIRST
   slot whose +0x1C is zero.

   The walk lives here, in the companion DLL, rather than in executable cave
   space.  It runs once per export from a pointer the caller supplies, so the
   patched executable gains no loop, no table and no new cave bytes.

   WHY THIS COUNTS GRAVES AND NOT DEATHS.  Because the writer takes the first
   free slot, a slot is reusable once something clears it.  Nothing has been
   found that clears one, but "nothing found" is not proof, and the array is
   bounded while a village's deaths are not.  The figure is therefore reported
   as graves currently held -- exactly what this function measures -- rather
   than as a lifetime total it cannot support.

   The empty test and the age share one field, so a villager buried at age zero
   would leave its record reading free and the next burial would overwrite it.
   The repository owner confirms that is unreachable in ordinary play and takes
   external memory editing to produce (age forced to zero, then health to
   zero).  The executable agrees: VV4 compares +0x1B8C against 0x118 and 0x168
   at nine sites as a maturity threshold, so it is an age that grows before any
   death path is reached. */
static int count_occupied_graves(
    const unsigned char *graves,
    unsigned int stride,
    unsigned int occupied_offset,
    unsigned int capacity
) {
    unsigned int index;
    int total = 0;
    if (graves == NULL) {
        return 0;
    }
    for (index = 0; index < capacity; ++index) {
        if (read_int(graves + index * stride, occupied_offset) != 0) {
            ++total;
        }
    }
    return total;
}

/* Emit the memorial row, or nothing when a game's array is unlocated.

   Shared by both writers deliberately. The row was first added to
   write_later_game alone, which silently omitted it for New Believers because
   that game has its own writer -- review caught that on #285. One emitter used
   by every caller cannot drift apart that way again. */
static int write_memorial_row(
    FILE *file,
    unsigned int graves_rva,
    unsigned int graves_stride,
    unsigned int graves_capacity
) {
    const unsigned char *module;
    if (graves_rva == 0u) {
        return 1;
    }
    module = (const unsigned char *)GetModuleHandleW(NULL);
    if (module == NULL) {
        return 0;
    }
    return fprintf(
        file,
        "Graves in the Memorial: %d\n",
        count_occupied_graves(
            module + graves_rva, graves_stride, 0x1Cu, graves_capacity)
    ) >= 0;
}

static int build_output_paths(
    int save_id,
    wchar_t *temporary,
    wchar_t *destination
) {
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
            temporary,
            MAX_LONG_PATH,
            _TRUNCATE,
            L"%ls\\Village Statistics - Save %d.tmp",
            module_path,
            save_id
        ) < 0) {
        return 0;
    }
    if (_snwprintf_s(
            destination,
            MAX_LONG_PATH,
            _TRUNCATE,
            L"%ls\\Village Statistics - Save %d.txt",
            module_path,
            save_id
        ) < 0) {
        return 0;
    }
    return 1;
}

static int real_hours(int game_id, const unsigned char *manager) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    typedef int (__fastcall *real_hours_function)(const void *, const void *);
    unsigned int rva;
    if (module == NULL) {
        return 0;
    }
    rva = game_id == GAME_VV1 ? 0x1D0E0u : 0x25A90u;
    return ((real_hours_function)(module + rva))(manager, NULL);
}

static int write_vv1(FILE *file, const unsigned char *manager) {
    static const unsigned int puzzle_offsets[16] = {
        0x9FA8, 0x9FB0, 0x9FB8, 0x9FC0,
        0x9FC8, 0x9FD8, 0x9FE0, 0x9FE8,
        0xA000, 0xA008, 0xA050, 0xA058,
        0xA080, 0xA088, 0xA090, 0xA098
    };
    return fprintf(
        file,
        "Virtual Villagers - A New Home\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Maximum Population: %d\n"
        "Villagers Buried: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n"
        "Puzzles Solved: %d of 16\n",
        real_hours(GAME_VV1, manager),
        read_int(manager, 0x9E20),
        read_int(manager, 0x9E24),
        read_int(manager, 0x9E28),
        read_int(manager, 0x9E2C),
        read_int(manager, 0x9E30),
        read_int(manager, 0x9E34),
        read_int(manager, 0x9E38),
        read_int(manager, 0x9E3C),
        read_int(manager, 0x9E40),
        read_int(manager, 0x9E44),
        read_int(manager, 0x9E48),
        count_flags(manager, puzzle_offsets, 16)
    ) >= 0;
}

static int write_vv2(FILE *file, const unsigned char *manager) {
    static const unsigned int puzzle_offsets[16] = {
        0x2E768, 0x2E770, 0x2E778, 0x2E780,
        0x2E788, 0x2E790, 0x2E798, 0x2E7A0,
        0x2E7A8, 0x2E7B0, 0x2E7B8, 0x2E7C0,
        0x2E7C8, 0x2E7D8, 0x2E7E0, 0x2E7E8
    };
    return fprintf(
        file,
        "Virtual Villagers - The Lost Children\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Special Stews Found: %d\n"
        "Triplets Birthed: %d\n"
        "Puzzles Solved: %d of 16\n",
        real_hours(GAME_VV2, manager),
        read_int(manager, 0x2E4FC),
        read_int(manager, 0x2E500),
        read_int(manager, 0x2E504),
        read_int(manager, 0x2E508),
        read_int(manager, 0x2E50C),
        read_int(manager, 0x2E510),
        read_int(manager, 0x2E514),
        read_int(manager, 0x2E518),
        read_int(manager, 0x2E51C),
        read_int(manager, 0x2E520),
        read_int(manager, 0x2E524),
        count_flags(manager, puzzle_offsets, 16)
    ) >= 0;
}

static int later_game_hours(
    const unsigned char *manager,
    unsigned int clock_rva,
    unsigned int statistics_offset
) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    typedef int (__fastcall *clock_function)(const void *, const void *);
    int current;
    int started;

    if (module == NULL) {
        return 0;
    }
    current = ((clock_function)(module + clock_rva))(manager, NULL);
    started = read_int(manager, statistics_offset);
    if (current <= started) {
        return 0;
    }
    return (current - started) / 3600;
}

static int count_later_puzzles(
    unsigned int predicate_rva,
    unsigned int puzzle_manager_rva,
    int first_id,
    int puzzle_total
) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    typedef int (__fastcall *puzzle_function)(
        const void *,
        const void *,
        int
    );
    int solved = 0;
    int index;
    if (module == NULL) {
        return 0;
    }
    for (index = 0; index < puzzle_total; ++index) {
        if (((puzzle_function)(module + predicate_rva))(
                module + puzzle_manager_rva,
                NULL,
                first_id + index
            )) {
            ++solved;
        }
    }
    return solved;
}

static int count_saved_puzzles(
    const unsigned char *manager,
    unsigned int progress_offset,
    unsigned int threshold_rva,
    int first_id,
    int puzzle_total
) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    int solved = 0;
    int index;
    if (module == NULL) {
        return 0;
    }
    for (index = 0; index < puzzle_total; ++index) {
        int puzzle_id = first_id + index;
        int progress = read_int(manager, progress_offset + puzzle_id * 8u);
        int threshold = *(const int *)(
            module + threshold_rva + puzzle_id * 4u
        );
        if (progress >= threshold) {
            ++solved;
        }
    }
    return solved;
}

static int count_vv5_puzzles(
    const unsigned char *manager,
    const unsigned char *module,
    int *puzzle_total
) {
    int solved = count_saved_puzzles(
        manager,
        0x16D20u,
        0x11DF30u,
        1,
        16
    );
    int bonus_progress = read_int(manager, 0x16D20u + 17u * 8u);
    int bonus_enabled = module != NULL && module[0x8F16u] == 0xE9;

    /*
     * Puzzle 17 is a current-save state, not a lifetime counter.  The
     * restoration patch keeps the same progress slot and completes it at 3.
     * Recognize that slot even when the exporter is attached to an already
     * completed save, so existing saves are reported accurately on the first
     * export rather than being forced to 16/16.
     */
    if (bonus_enabled || bonus_progress >= 3) {
        *puzzle_total = 17;
        if (bonus_progress >= 3) {
            ++solved;
        }
    } else {
        *puzzle_total = 16;
    }
    return solved;
}

static int write_later_game(
    FILE *file,
    const unsigned char *manager,
    const char *title,
    const char *collection_label,
    unsigned int statistics_offset,
    unsigned int clock_rva,
    int puzzles_solved,
    int puzzle_total,
    /* Memorial array: RVA of its base, its record stride, and its capacity.
       A zero RVA omits the row entirely rather than printing a zero that would
       read as "no deaths yet". */
    unsigned int graves_rva,
    unsigned int graves_stride,
    unsigned int graves_capacity
) {
    const unsigned char *statistics = manager + statistics_offset;
    if (fprintf(
        file,
        "%s\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "%s: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        /* +0x28 is Twins Birthed, not a stew count. The field is incremented
           inside the childbirth routine on the twins branch -- VV3 0x455BE7
           after `mov [litter], 2`, VV4 0x45E8DD likewise -- mutually exclusive
           with the +0x2C triplets write that follows `mov [litter], 3`.
           Every neighbouring label matches the shape of the code that writes
           it and only this one did not, in two games with two different
           encodings. The stale "Special Stews Found" string came from the
           enum-name mapping recorded in the research document; the
           requirements ask for Twins Birthed in all five games and for
           Special Stews Found in The Lost Children alone. */
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n"
        "Puzzles Solved: %d of %d\n",
        title,
        later_game_hours(manager, clock_rva, statistics_offset),
        read_int(statistics, 0x04),
        read_int(statistics, 0x08),
        read_int(statistics, 0x0C),
        read_int(statistics, 0x10),
        collection_label,
        read_int(statistics, 0x14),
        read_int(statistics, 0x18),
        read_int(statistics, 0x1C),
        read_int(statistics, 0x20),
        read_int(statistics, 0x24),
        read_int(statistics, 0x28),
        read_int(statistics, 0x2C),
        puzzles_solved,
        puzzle_total
    ) < 0) {
        return 0;
    }
    return write_memorial_row(
        file, graves_rva, graves_stride, graves_capacity);
}

static int write_vv5(
    FILE *file,
    const unsigned char *manager,
    int puzzles_solved,
    int puzzle_total
) {
    const unsigned char *statistics = manager + 0x7B4u;
    if (fprintf(
        file,
        "Virtual Villagers - New Believers\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        /* +0x28 is Twins Birthed. See the note in write_later_game: New
           Believers shares the later-game block layout, and its own
           increments sit at 0x465F2D (twins) and 0x465F1A (triplets). */
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n"
        "Heathens Converted: %d\n"
        "Puzzles Solved: %d of %d\n",
        later_game_hours(manager, 0x36E0u, 0x7B4u),
        read_int(statistics, 0x04),
        read_int(statistics, 0x08),
        read_int(statistics, 0x0C),
        read_int(statistics, 0x10),
        read_int(statistics, 0x14),
        read_int(statistics, 0x18),
        read_int(statistics, 0x1C),
        read_int(statistics, 0x20),
        read_int(statistics, 0x24),
        read_int(statistics, 0x28),
        read_int(statistics, 0x2C),
        read_int(statistics, 0x34),
        puzzles_solved,
        puzzle_total
    ) < 0) {
        return 0;
    }
    /* New Believers: memorial at 0x5481A8, accessor 0x464E70,
       500 slots, stride 0x5C, occupancy +0x1C. */
    return write_memorial_row(file, 0x1481A8u, 0x5Cu, 500u);
}

__declspec(dllexport) int __stdcall WriteVillageStatistics(
    int game_id,
    const void *manager_pointer,
    int save_id
) {
    const unsigned char *manager = (const unsigned char *)manager_pointer;
    wchar_t temporary[MAX_LONG_PATH];
    wchar_t destination[MAX_LONG_PATH];
    FILE *file;
    int written;
    int closed;
    int vv5_total;
    int vv5_solved;
    unsigned char *module;

    if (manager == NULL || save_id < 1 || save_id > 5) {
        return 0;
    }
    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    if (!build_output_paths(save_id, temporary, destination)) {
        return 0;
    }

    file = _wfopen(temporary, L"wb");
    if (file == NULL) {
        return 0;
    }
    if (game_id == GAME_VV1) {
        written = write_vv1(file, manager);
    } else if (game_id == GAME_VV2) {
        written = write_vv2(file, manager);
    } else if (game_id == GAME_VV3) {
        written = write_later_game(
            file,
            manager,
            "Virtual Villagers - The Secret City",
            "Mushrooms Found",
            0x4ECu,
            0x3330u,
            count_saved_puzzles(
                manager,
                0x11ED8u,
                0x9D230u,
                0,
                16
            ),
            16,
            /* Roster Of The Dead. Accessor 0x454AD0 computes the record with
               lea/shl rather than imul: base = container 0x5973F0 + 0x974, so
               the array begins at 0x597D64; capacity 500, stride 0x30, and the
               occupancy dword at +0x1C. Corroborated by the burial writer
               0x454FF0 and the clear at 0x4549F0, which both step by 0x30 for
               0x1F4 records. */
            0x197D64u, 0x30u, 500u
        );
    } else if (game_id == GAME_VV4) {
        written = write_later_game(
            file,
            manager,
            "Virtual Villagers - The Tree of Life",
            "Collectibles Found",
            0x850u,
            0x3750u,
            count_later_puzzles(0x38960u, 0xD8BF8u, 0, 16),
            16,
            /* Mausoleum. Accessor 0x45D650: base 0x5025C8, capacity 500,
               stride 0x5C, occupancy +0x1C. Burial writer 0x45D470. */
            0x1025C8u, 0x5Cu, 500u
        );
    } else {
        module = (unsigned char *)GetModuleHandleW(NULL);
        vv5_solved = count_vv5_puzzles(manager, module, &vv5_total);
        written = write_vv5(
            file,
            manager,
            vv5_solved,
            vv5_total
        );
    }
    closed = fclose(file) == 0;
    if (!written || !closed) {
        DeleteFileW(temporary);
        return 0;
    }
    if (!MoveFileExW(
            temporary,
            destination,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
        )) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}
