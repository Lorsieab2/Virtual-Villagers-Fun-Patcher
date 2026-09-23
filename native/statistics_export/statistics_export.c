#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

#include "village_identity.h"
#include "save_folder.h"

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
#define ROBING_BASELINE_MARKER 0x56433131 /* 'VC11' */
#define ELDER_BASELINE_MARKER 0x56453431 /* 'VE41' */

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

/* Count Village Elders: villagers who have mastered three or more skills.

   THE OWNER'S DEFINITION, and the games' own. "Village Elders -- anyone who
   reaches Master status in at least 3 or more skills." Each later game
   implements exactly that predicate itself:

       VV3  sub_462570   int32  vs 0x58  over 5 skills, cmp eax,3 / setnl
       VV5  sub_475610   float  vs 88.0  over 6 skills, cmp edx,3 / setnl
       VV4  sub_46AD00   float  vs 88.0  over 5 skills, RETURNS the count

   The threshold is the same number 88 in all three; VV3 stores skills as
   int32 and compares against 0x58 where VV4 and VV5 store float32 and
   compare against 88.0. VV5 has SIX skills where VV3 and VV4 have five.
   Neither difference can be carried across: six slots on VV3 or VV4 reads a
   dword past the skill block, and five on VV5 ignores a skill and undercounts.

   VV4 has no ready-made "three or more" test -- its sub_46AC70 is `cmp edx,5`,
   mastered ALL five, which is a much rarer thing. sub_46AD00 returns the
   count over the same five skills, so the counting stays the game's and only
   the comparison is ours.

   WHY THE ROW READ 0. The statistics field the export used, statistics+0x1C,
   is never written by any of the three games. Counting non-stack references
   in the stock images: VV4's neighbouring statistics fields are written at 7
   to 12 sites each and +0x86C at NONE; VV3's neighbours at 1 to 11 sites and
   +0x508 at NONE. The games allocate the slot and never compute it, so the
   export faithfully reported the zero that was stored.

   RETROACTIVE, at the owner's request: "a retroactive counter for dead
   villagers too would be nice", and more generally "retroactive counters for
   almost everything is good." So the row is living elders PLUS villagers who
   died holding the status, and the dead half comes from what each game
   already persisted at burial rather than from a counter that would start at
   zero on install. */
static int count_living_elders(
    const unsigned char *villagers,
    unsigned int record_base,
    unsigned int stride,
    unsigned int slots,
    unsigned int active_offset,
    unsigned int skills_offset,
    unsigned int skill_count,
    int skills_are_float
) {
    unsigned int index;
    int total = 0;
    if (villagers == NULL) {
        return 0;
    }
    for (index = 0; index < slots; ++index) {
        const unsigned char *record = villagers + record_base + index * stride;
        unsigned int skill;
        int mastered = 0;
        if (*(const unsigned char *)(record + active_offset) != 1) {
            continue;
        }
        for (skill = 0; skill < skill_count; ++skill) {
            const unsigned char *field = record + skills_offset + skill * 4u;
            /* 88 in both encodings. The games compare "not less than", so a
               skill exactly at the threshold counts, which is why this is >=
               rather than >. */
            if (skills_are_float) {
                if (*(const float *)field >= 88.0f) {
                    ++mastered;
                }
            } else if (*(const int *)field >= 0x58) {
                ++mastered;
            }
        }
        if (mastered >= 3) {
            ++total;
        }
    }
    return total;
}

/* Seed VV4's patch-owned elder flag once, from the stock all-five flag.

   Only the burial hook writes grave+0x37, so every grave in a save created
   before this patch reads zero there. Without this, VV4's dead half would
   report 0 for exactly the long-running villages the owner asked to see
   counted retroactively -- which would contradict the whole point of the
   change rather than merely be incomplete. Codex raised this as a P1 on
   #353 and was right.

   WHAT IS RECOVERABLE. The stock writer stores sub_46AC70's verdict at
   grave+0x31, and that predicate is `cmp edx, 5` -- mastered ALL FIVE. Every
   villager who mastered five also mastered three, so the stock flag is a
   strict SUBSET of the owner's rule. Seeding from it can never overcount; it
   is a true lower bound, and it is exact for any village whose dead elders
   all mastered everything.

   It does NOT recover villagers who died having mastered three or four, and
   nothing in a VV4 save records those -- the game never computed the
   predicate, which is the defect being fixed. So this is the same bargain
   the memorial baseline already makes for Villagers Buried: strictly better
   than zero, never overstated, and exact from the patch forward.

   Gated on its own marker rather than on the field being zero. A save whose
   graves genuinely hold no elders is indistinguishable by value from an
   unseeded one, and re-running the migration every export would be harmless
   only until the burial hook had written a real verdict the stock flag
   disagrees with -- at which point a re-seed would clear it. The marker is
   written once whether or not anything was seeded. */
static void seed_vv4_elder_flags(
    unsigned char *counters,
    unsigned int marker_offset,
    unsigned char *graves,
    unsigned int stride,
    unsigned int capacity,
    unsigned int occupied_offset,
    unsigned int stock_offset,
    unsigned int elder_offset
) {
    unsigned int index;
    if (counters == NULL || graves == NULL) {
        return;
    }
    if (read_int(counters, marker_offset) == (int)ELDER_BASELINE_MARKER) {
        return;
    }
    for (index = 0; index < capacity; ++index) {
        unsigned char *record = graves + index * stride;
        if (read_int(record, occupied_offset) == 0) {
            continue;
        }
        /* Only ever sets, never clears: a verdict the burial hook already
           wrote must survive a seed that runs after it. */
        if (*(const unsigned char *)(record + stock_offset) != 0) {
            *(unsigned char *)(record + elder_offset) = 1;
        }
    }
    write_int(counters, marker_offset, (int)ELDER_BASELINE_MARKER);
}

/* Count villagers who died holding the status, from the flag their game's
   burial writer already stored in the grave record.

   VV3 0x455075 stores sub_462570's result at grave+0x29 and VV5 0x464CFE
   stores sub_475610's at grave+0x31 -- both of those ARE the three-or-more
   rule, so those two games are exactly retroactive from data already on disk
   with no patch involvement at all.

   Runtime evidence rather than inference: across 52 of the owner's VV5 saves
   and 1,820 real grave records, grave+0x31 is a clean boolean, set on 8. A
   value that varies with the data is proof the burial writer -- and so the
   predicate -- actually executes in play.

   VV4 is the exception and is handled by its caller: its burial writer stores
   the ALL-FIVE predicate instead, so its stock flag undercounts and a
   patch-owned flag is used.

   KNOWN BOUND, stated rather than glossed. The memorial holds 500 records
   and each game's burial writer takes the first free slot, returning without
   writing anything once all 500 are occupied (VV4 sub_45D470 scans to 0x1F4
   then returns al = 0). An elder who dies with a full memorial therefore
   leaves the living half without entering this one, and the total can fall.
   Codex raised this as a P2 on #353 and the mechanism is real.

   It is not fixed here, deliberately. count_occupied_graves already reasons
   the same way for Villagers Buried -- "nothing has been found that clears
   one, but 'nothing found' is not proof, and the array is bounded while a
   village's deaths are not" -- and reports graves currently held rather than
   a lifetime total it cannot support. Lifting the bound means uncapped
   patch-owned storage per dead villager in three executables, which is a new
   subsystem rather than the smallest safe change.

   Measured in the owner's saves: the largest memorial occupancy is 36 of 500
   in VV4 and 37 of 500 in VV5, so the bound is nowhere near being reached in
   the villages this was asked for. */
static int count_buried_elders(
    const unsigned char *graves,
    unsigned int stride,
    unsigned int capacity,
    unsigned int occupied_offset,
    unsigned int elder_offset
) {
    unsigned int index;
    int total = 0;
    if (graves == NULL) {
        return 0;
    }
    for (index = 0; index < capacity; ++index) {
        const unsigned char *record = graves + index * stride;
        /* Occupancy first: the terminator slot past the last burial carries
           stale bytes. In the owner's VV5 saves slot 499 holds a garbage name
           and a non-boolean value in the elder byte, which is what made an
           early count report three distinct values for a field that setnl can
           only ever write as 0 or 1. */
        if (read_int(record, occupied_offset) == 0) {
            continue;
        }
        if (*(const unsigned char *)(record + elder_offset) != 0) {
            ++total;
        }
    }
    return total;
}

/* Seed a save's Chiefs Robed counter once, then leave it to the hook.

   The wrapper on the robing routine counts every robing from the moment the
   patch is installed. A save created before that has had chiefs the counter
   never saw, so the raw value would read 0 for a village that visibly has a
   chief, and would stay short by every pre-install robing for ever. The
   requirements call for lifetime totals "from creation of the individual
   save", so the field has to be initialised rather than merely zeroed.

   WHAT IS RECOVERABLE. Nothing in a save records chiefs who have died --
   which is the whole reason this row needs a counter and not a walk. The one
   fact still present is whether a chief exists now, and a village with a
   chief has had at least one. So the baseline is 1 when a living villager
   carries the chief flag, and 0 otherwise.

   That is a LOWER BOUND for a village that has already lost a chief, and
   exact for every village that has not. It is strictly better than 0 and
   never overstates, which is the same bargain the memorial baseline makes
   for Villagers Buried.

   Gated on its own marker, not on the counter being zero: a brand-new
   village that has genuinely never had a chief is indistinguishable by
   value from an unseeded one, and re-seeding every export would pin the
   count at 1 for ever. The marker is written once whether or not a chief was
   found, so the seed happens exactly once per save.

   Only ever raises the stored value, so a counter that has already run ahead
   of the baseline is never walked backwards. */
static int seeded_robing_total(
    unsigned char *counters,
    unsigned int counter_offset,
    unsigned int marker_offset,
    const unsigned char *records,
    unsigned int record_base,
    unsigned int stride,
    int slots,
    unsigned int active_offset,
    unsigned int chief_offset
) {
    int stored = read_int(counters, counter_offset);
    if (read_int(counters, marker_offset) != (int)ROBING_BASELINE_MARKER) {
        int baseline = 0;
        if (records != NULL && stride != 0 && slots > 0) {
            int slot;
            for (slot = 0; slot < slots; ++slot) {
                const unsigned char *record =
                    records + record_base + (size_t)slot * stride;
                if (*(const unsigned char *)(record + active_offset) != 1) {
                    continue;
                }
                if (*(const unsigned char *)(record + chief_offset) != 0) {
                    baseline = 1;
                    break;
                }
            }
        }
        if (baseline > stored) {
            stored = baseline;
            write_int(counters, counter_offset, stored);
        }
        write_int(counters, marker_offset, (int)ROBING_BASELINE_MARKER);
    }
    return stored;
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
    /* The export belongs with the SAVE, not with the executable.
       See native/shared/save_folder.h: this used to strip to the exe's own
       directory, which put exported logs in the install folder while the
       village they describe lives under Documents\LDW\<exe basename>\.

       It also belongs in its OWN folder under Virtual Villagers Fun Patcher Logs, beside Tribe
       Population and Births and Conceptions, rather than loose in the save
       folder next to the .ldw files. vv_save_subfolder_w creates every
       missing component and leaves `reserve` bytes for the caller's own
       append, which here is the longer of the two tails below. */
    if (!vv_save_subfolder_w(module_path, L"Virtual Villagers Fun Patcher Logs\\Village Statistics", 64)) {
        return 0;
    }
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

static int write_vv1(
    FILE *file,
    unsigned char *manager,
    const char *village
) {
    static const unsigned int puzzle_offsets[16] = {
        0x9FA8, 0x9FB0, 0x9FB8, 0x9FC0,
        0x9FC8, 0x9FD8, 0x9FE0, 0x9FE8,
        0xA000, 0xA008, 0xA050, 0xA058,
        0xA080, 0xA088, 0xA090, 0xA098
    };
    return fprintf(
        file,
        "Virtual Villagers - A New Home\n"
        "Village Statistics\n"
        "%s\n"
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
        village,
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

static int write_vv2(
    FILE *file,
    unsigned char *manager,
    const char *village
) {
    static const unsigned int puzzle_offsets[16] = {
        0x2E768, 0x2E770, 0x2E778, 0x2E780,
        0x2E788, 0x2E790, 0x2E798, 0x2E7A0,
        0x2E7A8, 0x2E7B0, 0x2E7B8, 0x2E7C0,
        0x2E7C8, 0x2E7D8, 0x2E7E0, 0x2E7E8
    };
    return fprintf(
        file,
        "Virtual Villagers - The Lost Children\n"
        "Village Statistics\n"
        "%s\n"
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
        village,
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
    const char *village,
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
    /* Statistics-block offset of the patch-added lifetime Chiefs Robed
       counter, or zero for the games that have no chief.

       A LIFETIME counter and not a walk of the living. Counting villagers
       who currently carry the chief flag reports who holds the robe now, so
       it would fall back to 1 -- or 0 -- as chiefs die and are replaced,
       and the requirements forbid reconstructing a lifetime total from
       current state when that loses history. The counter is advanced by a
       wrapper on the robing routine itself; see the robing hook in
       scripts/build_statistics_features.py. */
    unsigned int chiefs_offset,
    /* Statistics-block offset of the Chiefs Robed one-time seed marker, and
       the villager array the baseline is read from. Zero omits the seed. */
    unsigned int chiefs_marker_offset,
    unsigned int villagers_rva,
    unsigned int villager_record_base,
    unsigned int villager_stride,
    int villager_slots,
    unsigned int villager_active,
    unsigned int villager_chief,
    /* Village Elders: the villager skill block, and the grave field its
       game's burial writer already stores the elder verdict in.

       The row is living elders PLUS villagers who died holding the status,
       at the owner's request that counters be retroactive. The living half
       is evaluated here from the skill block; the dead half is read from a
       flag the game persisted at burial, so a village that predates this
       patch still reports its full history rather than starting at zero.

       skill_count differs per game -- VV5 has six skills where VV3 and VV4
       have five -- and skills_are_float separates VV3's int32 encoding from
       VV4's and VV5's float32. Neither can be carried across: six slots on a
       five-skill game reads past the block, and the wrong encoding compares
       a float bit pattern against an integer threshold. */
    unsigned int villager_skills,
    unsigned int villager_skill_count,
    int villager_skills_are_float,
    unsigned int grave_elder_offset,
    /* VV4 only: the stock grave field its patch-owned elder flag is seeded
       from, and the statistics-block marker that makes the seed one-time.
       Zero for the games whose burial writer already stores the owner's
       predicate, which need no migration. */
    unsigned int grave_elder_seed_offset,
    unsigned int elder_marker_offset
) {
    unsigned char *statistics = (unsigned char *)manager + statistics_offset;
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    unsigned char *live = module == NULL
        ? NULL
        : module + live_statistics_rva;
    if (grave_elder_seed_offset != 0 && module != NULL) {
        seed_vv4_elder_flags(
            statistics, elder_marker_offset,
            module + graves_rva, graves_stride, graves_capacity,
            0x1Cu, grave_elder_seed_offset, grave_elder_offset);
    }
    if (fprintf(
        file,
        "%s\n"
        "Village Statistics\n"
        "%s\n"
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
        village,
        later_game_hours(manager, clock_rva, statistics_offset),
        read_int(statistics, 0x04),
        read_int(statistics, 0x08),
        read_int(statistics, 0x0C),
        read_int(statistics, 0x10),
        collection_label,
        read_int(statistics, 0x14),
        read_int(statistics, 0x18),
        /* Village Elders. NOT statistics+0x1C, which has zero non-stack
           references in any of the three executables -- the games allocate
           the field and never compute it, which is why the row reported 0.

           The objection recorded here previously was that a walk of the
           living roster is not a lifetime total and counts DOWN as elders
           die. That is right, and it is why this adds the buried half: the
           living evaluation is paired with the flag each game's burial
           writer already stored, so the figure only ever grows and covers
           villages that predate the patch. The owner asked for exactly
           that -- "a retroactive counter for dead villagers too". */
        count_living_elders(
            villagers_rva == 0 || module == NULL
                ? NULL
                : module + villagers_rva,
            villager_record_base, villager_stride,
            (unsigned int)villager_slots, villager_active,
            villager_skills, villager_skill_count,
            villager_skills_are_float)
        + count_buried_elders(
            module == NULL ? NULL : module + graves_rva,
            graves_stride, graves_capacity, 0x1Cu, grave_elder_offset),
        read_int(statistics, 0x20),
        read_int(statistics, 0x24),
        read_int(statistics, 0x28),
        read_int(statistics, 0x2C),
        puzzles_solved,
        puzzle_total
    ) < 0) {
        return 0;
    }
    /* Chiefs Robed, for the one game that has a chief.

       Read from the LIVE block for the same reason as every other
       patch-added counter: the wrapper increments the live copy and the
       saved copy only catches up on the next stock save, so reading the
       saved one would lag by a save. */
    if (chiefs_offset != 0u) {
        unsigned char *counters = live != NULL ? live : statistics;
        int chiefs = chiefs_marker_offset == 0u || module == NULL
            ? read_int(counters, chiefs_offset)
            : seeded_robing_total(
                counters, chiefs_offset, chiefs_marker_offset,
                module + villagers_rva,
                villager_record_base, villager_stride, villager_slots,
                villager_active, villager_chief);
        if (fprintf(file, "Chiefs Robed: %d\n", chiefs) < 0) {
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
    const char *village,
    int puzzles_solved,
    int puzzle_total
) {
    unsigned char *statistics = manager + 0x7B4u;
    /* Village Elders reads the villager container and the memorial, both of
       which are fixed globals rather than reachable from the manager. */
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    if (fprintf(
        file,
        "Virtual Villagers - New Believers\n"
        "Village Statistics\n"
        "%s\n"
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
        village,
        later_game_hours(manager, 0x36E0u, 0x7B4u),
        read_int(statistics, 0x04),
        read_int(statistics, 0x08),
        read_int(statistics, 0x0C),
        read_int(statistics, 0x10),
        read_int(statistics, 0x14),
        read_int(statistics, 0x18),
        /* Village Elders; see the note in write_later_game. Living elders
           plus those who died holding the status.

           Container 0x554148 (the immediate all 445 of its accessor's
           occurrences load), record base 0x48, stride 0x2F44, 150 slots,
           active byte +0x1CD4 -- the geometry the parentage layout already
           carries for this game. Skills at villager+0x1C5C, from
           `lea ebx,[edi+1C5Ch]` at 0x464CE3 in the burial writer.

           SIX skills here, not five: sub_475610 compares [ecx+0x00] through
           [ecx+0x14]. VV3 and VV4 have five, and carrying either count
           across would be wrong in both directions.

           Buried elders at grave+0x31, where 0x464CFE stores sub_475610's
           result -- the three-or-more rule itself. Measured across 52 of the
           owner's saves: 562 occupied graves, 8 of them elders. */
        count_living_elders(
            module == NULL ? NULL : module + 0x154148u,
            0x48u, 0x2F44u, 150u, 0x1CD4u, 0x1C5Cu, 6u, 1)
        + count_buried_elders(
            module == NULL ? NULL : module + 0x1481A8u,
            0x5Cu, 500u, 0x1Cu, 0x31u),
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

/* Invoke the Village Population companion, if it is present.

   THE CALL IS HERE RATHER THAN IN THE EXECUTABLE, deliberately. The roster
   wants exactly this moment -- a save that has just succeeded -- and this
   companion is already resolved and running at it. Putting the call between
   the two DLLs means the game executable needs NO new bytes for it: no
   appended section, no composition overlay against every other appending
   feature, no code cave.

   That matters more than convenience here. Executable space in these games is
   scarce and contested: the statistics cave is full, what looks free in a
   stock file is often claimed at apply time, free bytes repeatedly turned out
   to be in non-executable sections, and giving the roster its own page would
   have needed five append layouts and eight composition overlays -- one
   against every other feature that appends, in every game. A DLL-to-DLL call
   has none of that. The owner's standing rule is "dll over cave space
   always".

   FAILURE IS NEVER FATAL. The roster is a log, and a save that succeeded must
   keep reporting success whether or not the log was written. A missing DLL, a
   missing export, or a refusal from the roster itself all leave this silent.

   The module is resolved on every call rather than cached. It is one
   GetModuleHandleW on a save, which is not a path that needs optimising, and
   caching a handle across a save that may have unloaded it is a worse trade.
   Nothing here unloads the library: the roster stays loaded for the process's
   life, exactly as this companion does. */
static void write_village_population(int game_id, const char *village) {
    typedef int(__stdcall * population_function)(
        int, const void *, const char *);
    HMODULE library = GetModuleHandleW(L"VVFP Population Export.dll");
    population_function write;

    if (library == NULL) {
        library = LoadLibraryW(L"VVFP Population Export.dll");
        if (library == NULL) {
            return;
        }
    }
    write = (population_function)GetProcAddress(
        library, "WriteVillagePopulation");
    if (write == NULL) {
        return;
    }
    /* NULL module: the roster resolves the executable itself, which it must do
       anyway for its own array arithmetic. */
    /* The roster opens with the same identifying line as this log, so the
       two can be matched to each other and to the same village. */
    write(game_id, NULL, village);
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
    char village_name[VV_VILLAGE_NAME_MAX];
    /* Room for the name plus the fixed wrapper text and the slot. */
    char village[VV_VILLAGE_NAME_MAX + 32];
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
    /* Identify the village at the top of the log. The owner keeps several
       villages per game, so a log naming only the game cannot be matched to
       the village it describes, and these logs are meant to be
       cross-referenced against each other.

       Both halves are already in hand at this point -- save_id is the slot
       the game pushed at its own save call, and the manager is the block
       whose +8 is the save buffer holding the name -- so nothing is read
       from disk and the save folder is neither located nor touched.

       A name that cannot be read leaves an empty string, and the header
       falls back to the slot alone rather than printing a guess. */
    if (!vv_village_name(game_id, manager, village_name)) {
        village_name[0] = '\0';
    }
    if (!vv_village_header(
            village, sizeof village, village_name, save_id)) {
        village[0] = '\0';
    }
    /* Hand it to the exports that are NOT on the save call. The parentage log
       is written at conception, where there is no save buffer and no slot, so
       this is the only moment in the process at which the village is known. */
    vv_village_publish(village);

    if (!build_output_paths(save_id, temporary, destination)) {
        return 0;
    }

    /* Text mode, so each \n becomes the CRLF a Windows text viewer expects.
       The statistics file is written and never read back, so nothing depends
       on its byte-for-byte length; a player opening it in Notepad does depend
       on the line breaks being there. */
    file = _wfopen(temporary, L"w");
    if (file == NULL) {
        /* The statistics temporary could not be created, but the roster's own
           destination may be perfectly writable, and the game reports the save
           as successful either way. See the note below the writers: neither
           file's failure may suppress the other. */
        write_village_population(game_id, village);
        return 0;
    }
    if (game_id == GAME_VV1) {
        written = write_vv1(file, manager, village);
    } else if (game_id == GAME_VV2) {
        written = write_vv2(file, manager, village);
    } else if (game_id == GAME_VV3) {
        written = write_later_game(
            file,
            manager,
            village,
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
            /* Chiefs Robed at +0x44, the first free per-save reserve dword
               after burials (+0x38/+0x3C) and deaths (+0x40). Advanced by the
               wrapper on the robing routine sub_45FBC0 -- the only writer of
               the chief flag in the image -- so every replacement chief is
               counted, including the ones the one-shot chief puzzle never
               fires for. */
            0x44u,
            /* Seed marker at +0x48, and the villager array the one-time
               baseline is read from: container 0x59E110 (accessor sub_45C840,
               record base 0x14, stride 0x1F8C, 150 slots), active byte +0xF10,
               chief flag +0xE80.

               +0xE80 is the chief flag in the IN-MEMORY record. It is the only
               field the robing routine sets, and it is runtime-confirmed in
               tests/test_vv3_everyone_tries_on_robe.py, where with two chiefs
               present it was set on exactly those two villagers and clear on
               the other 147. */
            0x48u,
            0x19E110u, 0x14u, 0x1F8Cu, 150,
            0xF10u, 0xE80u,
            /* Village Elders. Skills at villager+0xEAC, from the burial
               writer's `lea ebx,[ebp+0EACh]` at 0x455057 -- the pointer it
               moves into ECX for both sub_462460 and sub_462570 two
               instructions later. VV3 stores skills as INT32 and its
               predicate compares against 0x58, so the float path must not be
               used here. Five skills.

               Buried elders at grave+0x29, where 0x455075 stores
               sub_462570's result -- and sub_462570 IS the three-or-more
               rule (cmp eax,3 / setnl), so VV3's dead half is exactly
               retroactive from stock data. */
            0xEACu, 5u, 0,
            0x29u,
            /* The Secret City's burial writer already stores the
               three-or-more verdict, so there is nothing to migrate. */
            0u, 0u
        );
    } else if (game_id == GAME_VV4) {
        written = write_later_game(
            file,
            manager,
            village,
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
            /* The Tree of Life has no chief, so no row and no seed. */
            0u,
            0u,
            /* The villager array is still needed for Village Elders even
               though there is no chief seed: container 0x50E568, the
               immediate all 55 of its accessor's callers load, with the
               record base, stride and slot count the parentage layout
               already carries for this game. */
            0x10E568u, 0x44u, 0x2E3Cu, 150,
            0x1CC4u,
            /* No chief flag in this game. */
            0u,
            /* Skills at villager+0x1C5C, from `lea ebx,[edi+1C5Ch]` at
               0x45D4E3 in the burial writer. FLOAT32 against 88.0, five
               skills.

               Buried elders at grave+0x37, which is PATCH-OWNED rather than
               stock. VV4 is the only one of the three whose burial writer
               does not persist the owner's predicate: 0x45D4FE stores
               sub_46AC70's result, and that is `cmp edx,5` -- mastered ALL
               five -- which undercounts three-and-four-skill elders. The
               hook in scripts/build_statistics_features.py stores the real
               verdict at +0x37, verified free: always zero across 701 of the
               owner's real grave records, and the only two [reg+0x37] forms
               image-wide are `lea` address arithmetic at 0x444382 and
               0x460790, neither in the burial writer nor the grave
               accessor. */
            0x1C5Cu, 5u, 1,
            0x37u,
            /* Seed +0x37 once from the stock all-five flag at +0x31, marked
               at statistics+0x4C (0x4D6E2C, zero references image-wide). */
            0x31u, 0x4Cu
        );
    } else {
        module = (unsigned char *)GetModuleHandleW(NULL);
        vv5_solved = count_vv5_puzzles(manager, module, &vv5_total);
        written = write_vv5(
            file,
            manager,
            village,
            vv5_solved,
            vv5_total
        );
    }
    closed = fclose(file) == 0;

    /* The roster is exported independently of the statistics outcome.

       These are two separate files with two separate failure modes: the
       statistics destination can be held open by another process without
       delete sharing while the roster destination is perfectly writable.
       Returning early on a statistics failure used to skip the roster
       entirely, so a save that the game reports as successful left the
       roster describing a village that no longer exists -- stale in a way
       that looks current, which is the failure this exporter exists to
       avoid. Neither file's failure is actionable from inside the game, so
       neither is allowed to suppress the other. */
    if (!written || !closed) {
        DeleteFileW(temporary);
        write_village_population(game_id, village);
        return 0;
    }
    if (!MoveFileExW(
            temporary,
            destination,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
        )) {
        DeleteFileW(temporary);
        write_village_population(game_id, village);
        return 0;
    }
    write_village_population(game_id, village);
    return 1;
}
