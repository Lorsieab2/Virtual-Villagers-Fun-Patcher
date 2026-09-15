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

static void write_int(unsigned char *manager, unsigned int offset, int value) {
    *(int *)(manager + offset) = value;
}

/* Marker value proving a save's burial counter has been seeded.

   A save created before the counter existed carries graves the counter never
   saw, so reporting the raw counter would show zero for a village with a full
   memorial. The requirements allow a retained-memorial count as a ONE-TIME
   lower-bound baseline and are explicit that it must not be an amount added
   per export, so the seed is gated on a dedicated marker rather than on the
   counter being zero: a genuine save with no burials yet is indistinguishable
   from an unseeded one by value alone, and re-seeding it every export would
   overwrite real pickups once the memorial filled.

   The constant is arbitrary but distinctive, so a slot that happens to hold a
   small integer for some other reason does not read as initialised. */
#define BURIAL_BASELINE_MARKER 0x56425331 /* 'VBS1' */

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

/* Walk a game's living villagers and count the ones the owner calls elders.

   "Village Elders = anyone who reaches Master status in at least 3 or more
   skills. All 5 games."  Counted per villager, so mastering five skills still
   counts once.

   This is a WALK, not a counter.  Elder-ness and chief-ness are states already
   written in each villager's record, so they can be read directly from the
   array whenever the file is written.  No hook, no wrapper, no statistics-block
   slot and no cave space is needed for either row -- which also means neither
   can drift out of step with the game the way a counter seeded once can.

   Every offset below was measured, and each has two independent witnesses.

   THE ARRAY.  Each game reaches its villagers through a bounds-checked
   accessor that hands over the whole layout:

     VV3 0x45C840  imul eax, 0x1F8C / lea eax,[eax+ecx+0x14]   container 0x59E110
     VV4 0x466040  cmp eax,0x95 / imul eax,0x2E3C / lea +0x44  container 0x50E568
     VV5 0x46F950  imul eax, 0x2F44 / lea eax,[eax+ecx+0x48]   container 0x554148

   VV4's accessor rejects an index above 0x95, which is 149 -- confirming the
   150 slots that data/builds.json and parentage_export.c both already declare.
   Those strides, slot counts, record bases and active bytes match
   parentage_export.c exactly; this file and that one measured them separately.

   THE SKILLS.  The two later games store skills as FLOATS and VV3 stores them
   as ints, which is why an integer-only search finds nothing in VV4 and VV5:

     VV3  +0xEAC +0xEB0 +0xEB4 +0xEB8 +0xEBC   int32, five skills
     VV4  +0x1C5C .. +0x1C6C                   float, five skills
     VV5  +0x1C5C .. +0x1C70                   float, SIX skills

   VV3's block is identified by the ladder itself: +0xEAC, +0xEB4, +0xEB8 and
   +0xEBC are each compared against 0x14, 0x32 and 0x58 -- the 20/50/88 rungs --
   at sites including 0x421751, 0x43000F and 0x4214DE.  VV4's and VV5's blocks
   are the only runs of consecutive dwords in the whole stride that the code
   touches with floating-point instructions and never with integer ones, and
   both sit beside the proven age (+0x1B8C) and active (+0x1CC4 / +0x1CD4)
   fields.  VV5 having six is not a typo: New Believers adds a sixth skill, and
   its run is one dword longer in the disassembly.

   THE THRESHOLD.  Master is 88 in VV3, VV4 and VV5.  Measured from each game's
   own ladder rather than assumed from one: VV1's is 90 (cmp eax,0x5A), so the
   value genuinely differs between games and is passed in per game.

   CORROBORATED AGAINST THE OWNER'S OWN SAVES.  The saved (compacted) form of
   the same records was parsed out of 65 of the owner's .ldw files.  In every
   one, each living villager's skills land in 0..100 with no NaN, and every
   Secret City save has exactly one living chief -- never zero, never two, never
   a dead villager.  That is a check on the field identifications, not merely on
   the arithmetic.  It also produced the elder lists the rows should now show
   (Rano, Amaro, Mino and Gin, and so on), which stay identical across different
   save slots of the same village.

   Returns -1 when the array cannot be located, which the callers treat as "omit
   the row" rather than printing a zero that would read as "no elders yet". */
static int count_village_elders(
    const unsigned char *records,
    unsigned int record_base,
    unsigned int stride,
    int slots,
    unsigned int active_offset,
    unsigned int skills_offset,
    int skill_count,
    int skills_are_floats,
    int master_threshold
) {
    int slot;
    int total = 0;
    if (records == NULL || stride == 0 || slots <= 0 || skill_count <= 0) {
        return -1;
    }
    for (slot = 0; slot < slots; ++slot) {
        const unsigned char *record =
            records + record_base + (size_t)slot * stride;
        int mastered = 0;
        int index;
        if (*(const unsigned char *)(record + active_offset) != 1) {
            continue;
        }
        for (index = 0; index < skill_count; ++index) {
            const unsigned char *field =
                record + skills_offset + (unsigned int)index * 4u;
            if (skills_are_floats) {
                float value = *(const float *)field;
                /* NaN fails every comparison, which is the wanted answer. */
                if (value >= (float)master_threshold) {
                    ++mastered;
                }
            } else if (*(const int *)field >= master_threshold) {
                ++mastered;
            }
        }
        if (mastered >= 3) {
            ++total;
        }
    }
    return total;
}

/* Count the villagers currently wearing the chief's robe (The Secret City).

   "Chiefs Robed: everyone who has been made Chief with the robe and bears the
   title Tribal Chief."

   The flag is a dword in the villager's own record.  The owner said so
   directly -- "there is a certain value (byte or 4byte) that makes villagers
   chief, it is set within a villager's array data" -- and the saves agree: in
   all 23 Secret City saves exactly one LIVING villager carries it, chiefs
   differ between villages, and no dead villager ever carries it.

   NOT HOOKED TO THE CHIEF PUZZLE, deliberately.  VV3 tracks chief creation as
   one of its sixteen puzzles, and the puzzle-progress routine at 0x435990 runs
   its completion branch exactly once, on the transition to complete.  A chief
   can die and be replaced many times and none of those replacements re-fires
   it.  The owner flagged this precisely: the counter "shouldn't depend on the
   puzzle since the puzzle only completes upon the first chief being made".  A
   puzzle-hooked counter would read 1 forever and look plausible while being
   wrong.

   WHAT THIS ROW MEANS.  It reports the chiefs the village holds right now,
   which in ordinary play is one once the robe exists and zero before.  It is
   NOT a lifetime total of everyone ever robed: nothing in the record survives a
   chief's death to be counted later, so a lifetime figure cannot be recovered
   from village state alone and is not claimed here.  The same care applies as
   to Villagers Buried, which is reported as graves held for the same reason.

   Why the rank strings were no help: "Tribal Chief", "Esteemed Elder" and
   "Master " live in an inline value/key localization table at 0x499B08 whose
   entries have ZERO code references by address, so the rank "ids" recorded from
   the ladder are row numbers in that table, not operands any instruction
   compares against a villager. */
static int count_robed_chiefs(
    const unsigned char *records,
    unsigned int record_base,
    unsigned int stride,
    int slots,
    unsigned int active_offset,
    unsigned int chief_offset
) {
    int slot;
    int total = 0;
    if (records == NULL || stride == 0 || slots <= 0) {
        return -1;
    }
    for (slot = 0; slot < slots; ++slot) {
        const unsigned char *record =
            records + record_base + (size_t)slot * stride;
        if (*(const unsigned char *)(record + active_offset) != 1) {
            continue;
        }
        if (*(const int *)(record + chief_offset) == 1) {
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
/* Seed a save's burial counter from its memorial once, then leave it alone.

   Returns the counter's value. The seed takes the larger of the stored counter
   and the current occupied-grave count, so a save that already has pickups
   recorded never loses them to a smaller memorial, and a save predating the
   counter starts from the graves it can still see rather than from zero.

   After seeding, the memorial is never consulted again for this value: the
   cave wrapper on the skeleton-pickup latch clear is what advances it, and
   that keeps counting once every slot is occupied. This is the "count
   occupied graves first, then count buried skeletons past the maximum"
   behaviour the requirements describe. */
static int seeded_burial_total(
    unsigned char *manager,
    unsigned int counter_offset,
    unsigned int marker_offset,
    const unsigned char *graves,
    unsigned int graves_stride,
    unsigned int graves_capacity
) {
    int stored = read_int(manager, counter_offset);
    if (read_int(manager, marker_offset) != (int)BURIAL_BASELINE_MARKER) {
        int baseline = count_occupied_graves(
            graves, graves_stride, 0x1Cu, graves_capacity);
        if (baseline > stored) {
            stored = baseline;
            write_int(manager, counter_offset, stored);
        }
        write_int(manager, marker_offset, (int)BURIAL_BASELINE_MARKER);
    }
    return stored;
}

static int write_memorial_row(
    FILE *file,
    unsigned int graves_rva,
    unsigned int graves_stride,
    unsigned int graves_capacity,
    /* Statistics block of the game, and the offsets within it of the
       patch-added lifetime burial counter and its one-time seeded marker. A
       zero counter offset means the game does not carry one yet. */
    unsigned char *statistics,
    unsigned int buried_offset,
    unsigned int marker_offset
) {
    const unsigned char *module;
    if (graves_rva == 0u) {
        return 1;
    }
    module = (const unsigned char *)GetModuleHandleW(NULL);
    if (module == NULL) {
        return 0;
    }
    if (buried_offset != 0u && statistics != NULL) {
        return fprintf(
            file,
            "Villagers Buried: %d\n",
            seeded_burial_total(
                statistics,
                buried_offset,
                marker_offset,
                module + graves_rva,
                graves_stride,
                graves_capacity
            )
        ) >= 0;
    }
    /* No counter for this game yet: report what the memorial still holds
       rather than nothing. */
    return fprintf(
        file,
        "Villagers Buried: %d\n",
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

static int write_vv1(FILE *file, unsigned char *manager) {
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
        "Tech Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        /* Read from the patch-added lifetime counter at manager+0x9E84, not
           the stock manager+0x9E38. That field has two writers image-wide and
           both are stores -- 0x41C3DF zero-inits it and 0x42F191 stores the
           return of sub_41CF10, an unrolled 5x10 sweep that recounts occupied
           grave slots -- so it stops rising at the 50-slot capacity. The
           counter is incremented by a cave wrapper on the skeleton-pickup
           latch clear at 0x448F65, and sits inside the manager+8 .. +0xABE4
           range that the full save writes at 0x41BF63, so it persists. */
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
        /* Seeded once from the 50-slot memorial at manager+0xA340, then
           advanced only by the pickup wrapper. */
        seeded_burial_total(manager, 0x9E84u, 0x9E88u,
                            manager + 0xA340u, 0x2Cu, 50u),
        read_int(manager, 0x9E3C),
        read_int(manager, 0x9E40),
        read_int(manager, 0x9E44),
        read_int(manager, 0x9E48),
        count_flags(manager, puzzle_offsets, 16)
    ) >= 0;
}

/* The Lost Children's memorial uses a different occupancy field.

   The later games mark a record occupied by a non-zero age at record+0x1C,
   which is what count_occupied_graves tests. VV2's records are stride 0x7C
   with the occupancy dword at record+0x74, so it needs its own walk rather
   than the shared one; passing the shared walk a wrong offset would report
   zero and silently seed a village's whole memorial away. */
static int vv2_seeded_burial_total(unsigned char *manager) {
    int stored = read_int(manager, 0x2E5D4u);
    if (read_int(manager, 0x2E5DCu) != (int)BURIAL_BASELINE_MARKER) {
        int baseline = count_occupied_graves(
            manager + 0x2EB0Cu, 0x7Cu, 0x74u, 50u);
        if (baseline > stored) {
            stored = baseline;
            write_int(manager, 0x2E5D4u, stored);
        }
        write_int(manager, 0x2E5DCu, (int)BURIAL_BASELINE_MARKER);
    }
    return stored;
}

static int write_vv2(FILE *file, unsigned char *manager) {
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
        "Tech Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        /* The Lost Children has no stock burial statistic. This reads the
           patch-added lifetime counter at manager+0x2E5D4, incremented by a
           cave wrapper on the skeleton-pickup latch clear at 0x46503B. The
           slot sits in a 27-dword run with no stock reference, clear of the
           puzzle flags at +0x2E768 and the discovered-recipe set at +0x2EAAC,
           and inside the manager+8 .. +0x30378 range the full save writes at
           0x424BF3, so it persists. */
        "Villagers Buried: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Special Stews Found: %d\n"
        /* The Lost Children counts triplets natively at manager+0x2E524 but
           has no twins counter: its childbirth routine is cumulative, so the
           twins branch at 0x44BA82 sets litter 2 and falls through into the
           triplets test, and a twins-only birth returns without counting.
           This reads the patch-added counter at manager+0x2E5D8, incremented
           by a wrapper on that branch. */
        "Twins Birthed: %d\n"
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
        /* Seeded once from the 50-slot memorial. The Lost Children reaches
           its grave records through a container pointer rather than a fixed
           offset -- the allocator at 0x464CD0 loads [esi+0xE574D4] and then
           indexes +0x2EB0C at stride 0x7C -- and the manager this exporter
           receives IS that container, so the records sit at manager+0x2EB0C
           with the occupancy dword at record+0x74. */
        vv2_seeded_burial_total(manager),
        read_int(manager, 0x2E518),
        read_int(manager, 0x2E51C),
        read_int(manager, 0x2E520),
        read_int(manager, 0x2E5D8),
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
    unsigned char *manager,
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
    unsigned int graves_capacity,
    /* Statistics-block offsets of the patch-added lifetime burial counter
       and its one-time seeded marker. */
    unsigned int buried_offset,
    unsigned int marker_offset,
    /* Statistics-block offsets of up to two game-specific extra counters and
       the labels to print them under. Zero omits a row.

       Two, not one, because The Tree of Life needs both: Villagers Died and
       Debris Cleared. With a single slot the two games sharing this writer
       could each have one row and no more -- The Secret City spent it on
       Villagers Died, The Tree of Life on Debris Cleared -- so adding the
       death counter to The Tree of Life would have silently displaced its
       debris row rather than joining it. New Believers avoids the limit only
       by having a bespoke writer with its rows spelled out. */
    unsigned int extra_offset,
    const char *extra_label,
    unsigned int second_extra_offset,
    const char *second_extra_label,
    /* RVA of the game's LIVE statistics block. The later games keep the block
       at a fixed global and copy it wholesale into the save on write and back
       on load, and the pickup wrapper increments the live copy. Seeding the
       saved copy alone would not stick: the next save overwrites it from the
       still-unseeded live block. Seeding the live block makes both agree, and
       the stock copy then carries the value out. */
    unsigned int live_statistics_rva,
    /* Villager array, for the Village Elders and Chiefs Robed walks: the RVA
       of the container the game's own accessor is called with, plus the
       record layout inside it. count_village_elders records where each of
       these was measured. A zero RVA means "not located". */
    unsigned int villagers_rva,
    unsigned int villager_record_base,
    unsigned int villager_stride,
    int villager_slots,
    unsigned int villager_active,
    unsigned int villager_skills,
    int villager_skill_count,
    int villager_skills_are_floats,
    int villager_master,
    /* Record offset of the chief flag. Zero omits the Chiefs Robed row:
       only The Secret City has a chief. */
    unsigned int villager_chief
) {
    unsigned char *statistics = (unsigned char *)manager + statistics_offset;
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    unsigned char *live = module == NULL
        ? NULL
        : module + live_statistics_rva;
    /* The villager array is reached through the module base, exactly like the
       live statistics block above. Negative means the walk could not run. */
    int elders = (module == NULL || villagers_rva == 0u)
        ? -1
        : count_village_elders(
            module + villagers_rva,
            villager_record_base,
            villager_stride,
            villager_slots,
            villager_active,
            villager_skills,
            villager_skill_count,
            villager_skills_are_floats,
            villager_master);
    if (fprintf(
        file,
        "%s\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Tech Points Earned: %d\n"
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
        /* Was read_int(statistics, 0x1C). That field has ZERO references in
           the executable -- nothing in the stock game ever writes it -- so the
           row printed a dead field. It is now the measured mastery walk. */
        elders < 0 ? 0 : elders,
        read_int(statistics, 0x20),
        read_int(statistics, 0x24),
        read_int(statistics, 0x28),
        read_int(statistics, 0x2C),
        puzzles_solved,
        puzzle_total
    ) < 0) {
        return 0;
    }
    /* Chiefs Robed, for the one game that has a chief. Walked, not counted:
       see count_robed_chiefs for why this must not be hooked to the chief
       puzzle, which fires only for the FIRST chief a village ever has. */
    if (villager_chief != 0u && module != NULL && villagers_rva != 0u) {
        int chiefs = count_robed_chiefs(
            module + villagers_rva,
            villager_record_base,
            villager_stride,
            villager_slots,
            villager_active,
            villager_chief);
        if (chiefs >= 0
            && fprintf(file, "Chiefs Robed: %d\n", chiefs) < 0) {
            return 0;
        }
    }
    /* Read the live block for patch-added counters: the wrapper increments
       it, and the saved copy only catches up on the next stock save. */
    if (extra_offset != 0u
        && fprintf(file, "%s: %d\n", extra_label,
                   read_int(live != NULL ? live : statistics,
                            extra_offset)) < 0) {
        return 0;
    }
    if (second_extra_offset != 0u
        && fprintf(file, "%s: %d\n", second_extra_label,
                   read_int(live != NULL ? live : statistics,
                            second_extra_offset)) < 0) {
        return 0;
    }
    return write_memorial_row(
        file, graves_rva, graves_stride, graves_capacity,
        live != NULL ? live : statistics, buried_offset, marker_offset);
}

/* New Believers' live statistics block, or the saved copy if the module
   handle is unavailable. The patch-added counters are incremented in the
   live block by cave wrappers; the saved copy only catches up on the next
   stock save, so reading it would lag by one save. */
static unsigned char *vv5_live_statistics(unsigned char *saved) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    return module == NULL ? saved : module + 0x11D358u;
}

static int write_vv5(
    FILE *file,
    unsigned char *manager,
    int puzzles_solved,
    int puzzle_total
) {
    unsigned char *statistics = manager + 0x7B4u;
    /* New Believers' villager array, for the Village Elders walk. The
       container is the global 0x554148 (RVA 0x154148), reached through
       accessor sub_46F950 which computes `lea eax,[eax+ecx+0x48]` after
       multiplying by the 0x2F44 stride -- both recorded independently in
       parentage_export.c, whose VV5 row notes the header is 0x48 and NOT
       VV4's 0x44.

       SIX skill floats at +0x1C5C..+0x1C70, one more than The Tree of Life:
       that run is the only sequence of consecutive dwords in the stride the
       code touches with floating-point instructions and never with integer
       ones, and it sits beside the proven age +0x1B8C and active +0x1CD4.
       Passing VV4's five here would silently ignore the sixth skill and
       undercount elders in exactly the game that has the most skills. */
    unsigned char *vv5_module = (unsigned char *)GetModuleHandleW(NULL);
    int elders = vv5_module == NULL ? -1 : count_village_elders(
        vv5_module + 0x154148u,
        0x48u, 0x2F44u, 150,
        0x1CD4u,
        0x1C5Cu, 6, 1,
        88);
    if (fprintf(
        file,
        "Virtual Villagers - New Believers\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Tech Points Earned: %d\n"
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
        /* Villagers Died was removed at the owner's instruction --
           Villagers Buried is the kept statistic, because it stays
           meaningful once the graveyard fills. The counter itself is left
           in place and still incremented by its wrappers; only the row is
           gone. */
        "Puzzles Solved: %d of %d\n",
        later_game_hours(manager, 0x36E0u, 0x7B4u),
        read_int(statistics, 0x04),
        read_int(statistics, 0x08),
        read_int(statistics, 0x0C),
        read_int(statistics, 0x10),
        read_int(statistics, 0x14),
        read_int(statistics, 0x18),
        /* Was read_int(statistics, 0x1C), a field with ZERO references
           anywhere in the executable -- nothing in the stock game writes it.
           Now the measured mastery walk. */
        elders < 0 ? 0 : elders,
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
       500 slots, stride 0x5C, occupancy +0x1C.

       Seeded against the LIVE block at 0x51D358, not the saved copy. The
       pickup wrapper increments the live block, and the stock save copies it
       out wholesale afterwards; seeding the saved copy alone would be
       overwritten by the still-unseeded live values on the next save. */
    {
        unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
        unsigned char *live = module == NULL ? statistics : module + 0x11D358u;
        return write_memorial_row(
            file, 0x1481A8u, 0x5Cu, 500u, live, 0x38u, 0x3Cu);
    }
}

__declspec(dllexport) int __stdcall WriteVillageStatistics(
    int game_id,
    const void *manager_pointer,
    int save_id
) {
    /* The counters this exporter seeds live in the manager, so the pointer
       is used mutably. The seed writes at most one dword per save, once. */
    unsigned char *manager = (unsigned char *)manager_pointer;
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

    /* Text mode, so each \n becomes the CRLF a Windows text viewer expects.
       The statistics file is written and never read back, so nothing depends
       on its byte-for-byte length; a player opening it in Notepad does depend
       on the line breaks being there. */
    file = _wfopen(temporary, L"w");
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
            0x197D64u, 0x30u, 500u,
            /* Lifetime burials counted at the pickup latch clear, seeded
               once from the memorial via the marker at +0x3C. +0x30 is the
               Origins doubler ownership bitmask and must not be touched. */
            0x38u, 0x3Cu,
            /* No extra rows. Villagers Died was removed at the owner's
               instruction -- Villagers Buried is the kept statistic,
               because it stays meaningful once the graveyard fills. The
               counter at +0x40 is left in place and still incremented by
               its wrappers; only the row is gone. The Secret City has no
               debris row either; its stream puzzle differs. */
            0u, NULL,
            0u, NULL,
            /* Live statistics block, which the pickup wrapper increments. */
            0x1824A0u,
            /* Villager array: container 0x59E110, reached through accessor
               sub_45C840 (imul 0x1F8C, lea +0x14) at all 57 of its call
               sites. Skills are INT32 at +0xEAC..+0xEBC, identified by the
               ladder itself -- those offsets are compared against 0x14, 0x32
               and 0x58 (the 20/50/88 rungs) at 0x421751, 0x43000F, 0x4214DE
               and others. Active byte +0xF10, re-confirmed this pass at
               0x41BF52. */
            0x19E110u, 0x14u, 0x1F8Cu, 150,
            0xF10u,
            0xEACu, 5, 0,
            88,
            /* Chief flag +0xAC. In all 23 of the owner's Secret City saves
               exactly one LIVING villager carries it -- never zero, never
               two, never a dead villager -- and chiefs differ per village. */
            0xACu
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
            0x1025C8u, 0x5Cu, 500u,
            /* Lifetime burials counted at the pickup latch clear, seeded
               once from the memorial via the marker at +0x40. +0x30 is the
               Origins doubler ownership bitmask and must not be touched. */
            0x3Cu, 0x40u,
            /* Debris Cleared at +0x44, incremented by the wrapper on the
               stream-clearing action at 0x43965A -- the same event the Civil
               Engineer trophy credits a unit to, without that trophy's
               stop-once-earned cap. */
            /* Villagers Died was removed at the owner's instruction --
               Villagers Buried is the kept statistic, because it stays
               meaningful once the graveyard fills. Its counter at +0x48 is
               left in place and still incremented by its wrappers; only the
               row is gone, so Debris Cleared is now the single extra. */
            0x44u, "Debris Cleared",
            0u, NULL,
            /* Live statistics block, which all three wrappers increment. */
            0xD6DE0u,
            /* Villager array: container 0x50E568, reached through accessor
               sub_466040 at 54 of its 55 call sites. That accessor rejects an
               index above 0x95 -- 149 -- which independently confirms the 150
               slots declared in data/builds.json and parentage_export.c.
               Skills are FLOATS at +0x1C5C..+0x1C6C: the only run of
               consecutive dwords in the whole stride that the code touches
               with floating-point instructions and never with integer ones,
               sitting beside the proven age +0x1B8C and active +0x1CC4. */
            0x10E568u, 0x44u, 0x2E3Cu, 150,
            0x1CC4u,
            0x1C5Cu, 5, 1,
            88,
            /* The Tree of Life has no chief. */
            0u
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
