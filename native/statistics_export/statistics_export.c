#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

#include "village_identity.h"
#include "save_folder.h"
#include "save_layout.h"
#include "patcher_files.h"
#include "village_elders.h"
#include "roster_match.h"
#include "statistics_store.h"
#include "vv3_villager_table.h"
#include "vv4_villager_table.h"
#include "vv5_villager_table.h"
#include "villager_lookalike.h"  /* statues, ghosts and stand-ins are no villagers */

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

/* The patch's own counters -- Villagers Buried, VV2 Twins Birthed, VV3
   Chiefs Robed, VV4 Debris Cleared, VV4/VV5 Food Gathered, VV5 Heathens
   Converted -- and the unique stews are no longer kept in the save. They live
   in per-slot .dat files; see statistics_store.h for how a count travels from
   a hook's pending field into the file, and for the one-time migration of the
   values earlier builds stored in the save (those fields are now frozen and
   never written). */
static vvs_context g_store;
static wchar_t g_store_counters[MAX_PATH];
static wchar_t g_store_stews[MAX_PATH];

/* The value of one of the patch's counters for the save being exported. A
   game without that counter, or a store that cannot be reached, reads 0. */
static int store_counter(int kind) {
    int value = 0;
    if (!vvs_counter_value(&g_store, kind, &value)) {
        return 0;
    }
    return value;
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
            L"%ls\\Village Statistics v2 - Save %d.tmp",
            module_path,
            save_id
        ) < 0) {
        return 0;
    }
    if (_snwprintf_s(
            destination,
            MAX_LONG_PATH,
            _TRUNCATE,
            /* v2: the owner's five-game directive layout. The earlier
               "Village Statistics - Save N.txt" is preserved as it is and
               never written again ("preserve old statistics and logs,
               write new ones"). */
            L"%ls\\Village Statistics v2 - Save %d.txt",
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

/* The save slot being exported, set by the exporter entry before any writer
   runs: the per-save .dat files are keyed by it. */
static int g_save_id;

/* Village Elders for the later games, from the save's Village Elders .dat
   (village_elders.c). Record offsets are the ones the Village Population
   exporter already carries and has verified per game
   (native/population_export/population_export.c GAME_LAYOUTS): name, the
   villager's own parents' names, the skill block. Master thresholds are the
   games' own predicates: VV3 sub_462570 counts int skills >= 0x58; VV4
   sub_46AD00 and VV5 sub_475610 count float skills >= 88.0. Memorials:
   VV3 the Roster of the Dead (0x597D64, stride 0x30, 500; the graveyard is
   only roster entries 0..49, so the roster alone counts each death once),
   elder verdict at +0x29 (0x455075 stores sub_462570's three-or-more);
   VV4 mausoleum 0x5025C8 and VV5 0x5481A8 (stride 0x5C, 500), verdict at
   +0x31 -- three-or-more in VV5 (0x464CFE), but all-FIVE in VV4 (0x45D4FE,
   sub_46AC70 `cmp edx,5`), which is still an elder, only a stricter test. */
/* The elder count for the current save. Computed ONCE per successful save,
   by elders_update_for_save, before the text log is opened -- so a locked or
   unwritable log never skips recording an elder -- and read from here by the
   writers. */
static int g_elders_ready;
static int g_elders_value;

/* Village Elders follows each elder to the record a reload puts them in:
   the games save their occupied records packed and load them into records
   0, 1, 2, ..., so the villager the previous save recorded at record s comes
   back at its rank in that roster.  Built from the roster this save's
   village_changed read (g_roster_was, rows in record order). */
static void elders_ranks(struct elders_layout *l);

static int village_elders_for(int game_id) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    struct elders_layout l;
    if (g_elders_ready) {
        return g_elders_value;
    }
    if (module == NULL) {
        return -1;
    }
    memset(&l, 0, sizeof(l));
    l.name_capacity = 0x19u;
    l.parent_name_capacity = 0x19u;
    l.grave_occupied = 0x1Cu;
    l.grave_name = 0u;
    l.grave_name_capacity = 0x19u;
    l.grave_capacity = 500u;
    if (game_id == GAME_VV3) {
        unsigned int table, slots;
        vv3_villager_table(module, &table, &slots);
        l.villagers = module + table; l.record_base = 0x14u; l.stride = 0x1F8Cu;
        l.slots = slots; l.active = 0xF10u; l.name = 0xDD4u;
        l.father_name = 0xDF8u; l.mother_name = 0xE11u;
        l.skills = 0xEACu; l.skill_count = 5u; l.skills_are_float = 0; l.master_int = 0x58;
        l.graves = module + 0x197D64u; l.grave_stride = 0x30u; l.grave_elder_flag = 0x29u;
    } else if (game_id == GAME_VV4) {
        unsigned int table, slots;
        vv4_villager_table(module, &table, &slots);
        l.villagers = module + table; l.record_base = 0x44u; l.stride = 0x2E3Cu;
        l.slots = slots; l.active = 0x1CC4u; l.name = 0x1B9Cu;
        l.father_name = 0x1BC0u; l.mother_name = 0x1BD9u;
        l.skills = 0x1C5Cu; l.skill_count = 5u; l.skills_are_float = 1; l.master_float = 88.0f;
        l.graves = module + 0x1025C8u; l.grave_stride = 0x5Cu; l.grave_elder_flag = 0x31u;
    } else if (game_id == GAME_VV5) {
        unsigned int table, slots;
        vv5_villager_table(module, &table, &slots);
        l.villagers = module + table; l.record_base = 0x48u; l.stride = 0x2F44u;
        l.slots = slots; l.active = 0x1CD4u; l.name = 0x1B9Cu;
        l.father_name = 0x1BC0u; l.mother_name = 0x1BD9u;
        l.skills = 0x1C5Cu; l.skill_count = 6u; l.skills_are_float = 1; l.master_float = 88.0f;
        l.tribe = 0x1CECu;              /* 0 = believer; heathens (the chief has all 100s) are not villagers */
        l.graves = module + 0x1481A8u; l.grave_stride = 0x5Cu; l.grave_elder_flag = 0x31u;
    } else {
        return -1;
    }
    elders_ranks(&l);
    g_elders_value = vv_village_elders(game_id, g_save_id, &l);
    g_elders_ready = 1;
    return g_elders_value;
}

/* A New Home's Village Elders: the owner's definition -- one villager with
   Master status in any three distinct skills -- applied to A New Home, which
   has no elder mechanism of its own (no title, string or routine).

   Master is the game's own: the Details title code at 0x41FC16 shows
   "Master" (string 0x59) for a skill >= 90 (`cmp ...,0x5A / jl`), and the
   gameplay checks at 0x4243CF, 0x424438, 0x4246B0, 0x43A5DF, 0x43B3A9 and
   0x43F4B0 use the same >= 90. Five int32 skills at record+0x3BC (Parent,
   Builder, Farmer, Doctor, Scientist; mapping from 0x43B520 and the name
   switch at 0x41FC6A), range 0..100 (clamped by 0x437230). No age gate: the
   later games' own elder predicates have none either.

   Records: the villager array is the lazily-allocated singleton behind the
   global at RVA 0x8B614 (null until the game first builds it), stride
   0x3D8, 256 slots, active byte +0x28, name +0x370 (Village Population
   exporter layout). A New Home keeps no parents on the record.

   Graves keep only the name, the single best skill and the age at death
   (0x448F70), so elders who died before this tracking began cannot be
   reconstructed: the count starts from the living and grows from there. */
static int vv1_village_elders(const unsigned char *manager) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    struct elders_layout l;
    (void)manager;
    if (g_elders_ready) {
        return g_elders_value;
    }
    if (module == NULL) {
        return -1;
    }
    memset(&l, 0, sizeof(l));
    l.villagers = *(unsigned char *const *)(module + 0x8B614u);
    l.record_base = 0u;
    l.stride = 0x3D8u;
    l.slots = 256u;
    l.active = 0x28u;
    l.name = 0x370u;
    l.name_capacity = 0x1Cu;
    l.skills = 0x3BCu;
    l.skill_count = 5u;
    l.skills_are_float = 0;
    l.master_int = 90;
    elders_ranks(&l);
    g_elders_value = vv_village_elders(GAME_VV1, g_save_id, &l);
    g_elders_ready = 1;
    return g_elders_value;
}

/* Unique stew combinations: VV2 Total Stews Found, VV3 and VV4 Stews Found.

   The number of distinct recipe identities in the slot's
   "Stew Discoveries - Save N.dat" -- the herb multiset, and for The Tree of
   Life the water too -- united with any discovery still pending in memory.
   The identities are recorded at the moment the game completes a stew, by the
   hooks in scripts/build_statistics_features.py; see statistics_store.c for
   the identity mapping and the file format. A village played before this
   build has no record of which stews it made, so its count starts at zero
   rather than at an invented figure. */
static int stews_found(void) {
    int value = 0;
    if (!vvs_stews_value(&g_store, &value)) {
        return 0;
    }
    return value;
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
    /* Rows and their order are the owner's directive
       (docs/village-statistics-directive.md, section II). */
    int buried;
    int elders;
    /* Villagers Buried, from the slot's statistics .dat: started once from
       the larger of the frozen counter +0x9E84 and the 50-slot memorial
       (occupancy dword manager+0xA340+i*0x2C, the field the game's own
       recount 0x41CF10 tests), then advanced by every skeleton pickup the
       wrapper on the latch clear counts. */
    buried = store_counter(VVS_BURIED);
    elders = vv1_village_elders(manager);
    return fprintf(
        file,
        "Virtual Villagers - A New Home\n"
        "Village Statistics\n"
        "%s\n"
        "Real Hours Played: %d\n"
        "Food Gathered: %d\n"
        "Tech Points Earned: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Babies Made: %d\n"
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n"
        "Villagers Buried: %d\n"
        "Puzzles Solved: %d out of 16\n",
        village,
        real_hours(GAME_VV1, manager),
        read_int(manager, 0x9E28),
        read_int(manager, 0x9E20),
        read_int(manager, 0x9E2C),
        read_int(manager, 0x9E30),
        read_int(manager, 0x9E34),
        elders,
        read_int(manager, 0x9E3C),
        read_int(manager, 0x9E40),
        read_int(manager, 0x9E24),
        read_int(manager, 0x9E44),
        read_int(manager, 0x9E48),
        buried,
        count_flags(manager, puzzle_offsets, 16)
    ) >= 0;
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
    /* Rows and their order are the owner's directive
       (docs/village-statistics-directive.md, section III).

       Villagers Buried: The Lost Children has no stock burial statistic.
       This is the slot's statistics .dat total, advanced by the wrapper on
       the skeleton-pickup latch clear at 0x46503B and started once from the
       larger of the frozen counter +0x2E5D4 and the 50-slot memorial (the
       manager this exporter receives IS the container the allocator
       0x464CD0 indexes: records at +0x2EB0C, stride 0x7C, occupancy at
       record+0x74).

       Twins Birthed: The Lost Children counts triplets natively at
       +0x2E524 but has no twins counter (its childbirth routine is
       cumulative: the twins branch at 0x44BA82 falls through into the
       triplets test). This is the .dat total, started from the frozen
       counter +0x2E5D8.

       Special Stews Found: the game's own +0x2E520, +1 the first time each
       of its 18 recipes is cooked (0x4260DC).

       Total Stews Found: the unique herb combinations of every stew the
       cook routine 0x425B90 completes, with no Special Stews restriction. */
    int buried = store_counter(VVS_BURIED);
    return fprintf(
        file,
        "Virtual Villagers - The Lost Children\n"
        "Village Statistics\n"
        "%s\n"
        "Real Hours Played: %d\n"
        "Food Gathered: %d\n"
        "Tech Points Earned: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Babies Made: %d\n"
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n"
        "Villagers Buried: %d\n"
        "Puzzles Solved: %d out of 16\n"
        "Special Stews Found: %d\n"
        "Total Stews Found: %d\n",
        village,
        real_hours(GAME_VV2, manager),
        read_int(manager, 0x2E504),
        read_int(manager, 0x2E4FC),
        read_int(manager, 0x2E508),
        read_int(manager, 0x2E50C),
        read_int(manager, 0x2E510),
        read_int(manager, 0x2E514),
        read_int(manager, 0x2E518),
        read_int(manager, 0x2E51C),
        read_int(manager, 0x2E500),
        store_counter(VVS_TWINS),
        read_int(manager, 0x2E524),
        buried,
        count_flags(manager, puzzle_offsets, 16),
        read_int(manager, 0x2E520),
        stews_found()
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
    /*
     * The owner: "X out of Y" -- 16 puzzles, and 17 when the Heathen Mommy
     * patch is active.
     *
     * Puzzle 17 is the game's own CHeathenMommyPuzzle, registered at
     * 0x439C8E as register(handler, 0x11, 1): its threshold is 1, like most
     * puzzles, and the game's IsComplete (0x43AE80) is the same
     * progress >= threshold test count_saved_puzzles makes. It completes when
     * stat 0xC1 reaches 3 by advancing the puzzle once (0 -> 1); that 3 is a
     * stat counter, not the puzzle's progress, which never exceeds 1. (Until
     * v1.35.40 this required progress >= 3, so puzzle 17 was never counted.)
     *
     * The patch is detected by its own jump at file offset/RVA 0x48F16 (E9
     * with the patch, B9 stock). (Until v1.35.40 this read 0x8F16, which is
     * 0x24 in every build, so the total was always 16.)
     */
    int bonus_enabled = module != NULL && module[0x48F16u] == 0xE9;
    *puzzle_total = bonus_enabled ? 17 : 16;
    return count_saved_puzzles(
        manager,
        0x16D20u,
        0x11DF30u,
        1,
        *puzzle_total
    );
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
    /* The one game-specific counter row this writer prints after Puzzles
       Solved, as a statistics-store counter kind (VVS_*), and its label; a
       negative kind omits the row. The Tree of Life's Debris Cleared. */
    int extra_counter,
    const char *extra_label,
    /* Nonzero for the one game that has a chief: prints Chiefs Robed.

       A LIFETIME counter and not a walk of the living. Counting villagers
       who currently carry the chief flag reports who holds the robe now, so
       it would fall back to 1 -- or 0 -- as chiefs die and are replaced,
       and the requirements forbid reconstructing a lifetime total from
       current state when that loses history. The count is advanced by a
       wrapper on the robing routine itself; see the robing hook in
       scripts/build_statistics_features.py. */
    int has_chiefs,
    /* The villager array. */
    unsigned int villagers_rva,
    unsigned int villager_record_base,
    unsigned int villager_stride,
    int villager_slots,
    unsigned int villager_active,
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
    unsigned int elder_marker_offset,
    /* The game, for its Stews Found row. */
    int game_id
) {
    unsigned char *statistics = (unsigned char *)manager + statistics_offset;
    /* Rows and their order are the owner's directive
       (docs/village-statistics-directive.md, sections IV and V): the
       fourteen common rows, Villagers Buried and Puzzles Solved last among
       them, then the game's own rows.

       +0x28 is Twins Birthed, not a stew count: it is incremented inside the
       childbirth routine on the twins branch -- VV3 0x455BE7 after
       `mov [litter], 2`, VV4 0x45E8DD likewise -- mutually exclusive with
       the +0x2C triplets write that follows `mov [litter], 3`. The games'
       own (unreachable) statistics page labels it "Special Stews Found"
       through the eTwinsBirthed entry; the counting code is the evidence. */
    if (fprintf(
        file,
        "%s\n"
        "Village Statistics\n"
        "%s\n"
        "Real Hours Played: %d\n"
        "Food Gathered: %d\n"
        "Tech Points Earned: %d\n"
        "People Cured: %d\n"
        "%s: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Babies Made: %d\n"
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n",
        title,
        village,
        later_game_hours(manager, clock_rva, statistics_offset),
        /* Food Gathered. The Secret City maintains +0x0C itself; The Tree of
           Life never writes it, so its total is the patch's food hook's, kept
           in the slot's statistics .dat. */
        game_id == GAME_VV4 ? store_counter(VVS_FOOD) : read_int(statistics, 0x0C),
        read_int(statistics, 0x04),
        read_int(statistics, 0x10),
        collection_label,
        read_int(statistics, 0x14),
        read_int(statistics, 0x18),
        /* Village Elders. NOT statistics+0x1C, which has zero non-stack
           references in any of the three executables -- the games allocate
           the field and never compute it, which is why the row reported 0.

           A lifetime count: every villager ever seen with Master in three
           or more skills, kept in the save's Village Elders .dat
           (village_elders.c), plus elders the game itself flagged on their
           graves. */
        village_elders_for(game_id),
        read_int(statistics, 0x20),
        read_int(statistics, 0x24),
        read_int(statistics, 0x08),
        read_int(statistics, 0x28),
        read_int(statistics, 0x2C)
    ) < 0) {
        return 0;
    }
    /* Villagers Buried and the game's own counters come from the slot's
       statistics .dat (see statistics_store.h). */
    if (fprintf(file, "Villagers Buried: %d\n", store_counter(VVS_BURIED)) < 0
        || fprintf(file, "Puzzles Solved: %d out of %d\n",
                   puzzles_solved, puzzle_total) < 0) {
        return 0;
    }
    if (has_chiefs
        && fprintf(file, "Chiefs Robed: %d\n", store_counter(VVS_CHIEFS)) < 0) {
        return 0;
    }
    if (extra_counter >= 0
        && fprintf(file, "%s: %d\n", extra_label, store_counter(extra_counter)) < 0) {
        return 0;
    }
    return fprintf(file, "Stews Found: %d\n", stews_found()) >= 0;
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
    /* Rows and their order are the owner's directive
       (docs/village-statistics-directive.md, section VI). +0x28 is Twins
       Birthed (see write_later_game): New Believers shares the later-game
       block layout, and its own increments sit at 0x465F2D (twins) and
       0x465F1A (triplets). Villagers Died was removed at the owner's
       instruction; its counter is still incremented, only the row is gone. */
    if (fprintf(
        file,
        "Virtual Villagers - New Believers\n"
        "Village Statistics\n"
        "%s\n"
        "Real Hours Played: %d\n"
        "Food Gathered: %d\n"
        "Tech Points Earned: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Babies Made: %d\n"
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n",
        village,
        later_game_hours(manager, 0x36E0u, 0x7B4u),
        /* Food Gathered: New Believers never writes +0x0C; the total is the
           patch's food hook's, kept in the slot's statistics .dat. */
        store_counter(VVS_FOOD),
        read_int(statistics, 0x04),
        read_int(statistics, 0x10),
        read_int(statistics, 0x14),
        read_int(statistics, 0x18),
        /* Village Elders; see village_elders_for. */
        village_elders_for(GAME_VV5),
        read_int(statistics, 0x20),
        read_int(statistics, 0x24),
        read_int(statistics, 0x08),
        read_int(statistics, 0x28),
        read_int(statistics, 0x2C)
    ) < 0) {
        return 0;
    }
    /* Villagers Buried (started once from the larger of the frozen counter
       and the memorial at 0x5481A8: accessor 0x464E70, 500 slots, stride
       0x5C, occupancy +0x1C) and Heathens Converted, from the slot's
       statistics .dat. */
    return fprintf(file, "Villagers Buried: %d\n", store_counter(VVS_BURIED)) >= 0
        && fprintf(file, "Puzzles Solved: %d out of %d\n",
                   puzzles_solved, puzzle_total) >= 0
        && fprintf(file, "Heathens Converted: %d\n",
                   store_counter(VVS_HEATHENS)) >= 0;
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
    /* Already loaded, or by its full path in the patcher's folder -- never
       the bare name, which would search the system folders, the current
       directory and PATH (native/shared/patcher_files.h). */
    HMODULE library = vvfp_patcher_dll("VVFP Population Export.dll");
    population_function write;

    if (library == NULL) {
        return;
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

/* Point the statistics store at one save slot of the running game. A path
   that cannot be built leaves it empty, which the store treats as "nothing
   on disk" for reading and refuses for writing, so pending counts stay in
   memory rather than being zeroed without a record. */
static void bind_store(int game_id, unsigned char *manager, int save_id) {
    g_store.game_id = game_id;
    g_store.manager = manager;
    g_store.module = (unsigned char *)GetModuleHandleW(NULL);
    if (!vvs_build_paths(game_id, save_id, g_store_counters, g_store_stews)) {
        g_store_counters[0] = L'\0';
        g_store_stews[0] = L'\0';
    }
    g_store.counters_path = g_store_counters;
    g_store.stews_path = g_store_stews;
}

/* The first-load reconcile (statistics_reconcile.inc): set by
   SaveVillageStatistics around WriteVillageStatistics when this save is the
   same village's and its counters were flushed -- only then may a counter be
   raised to what the logs prove (a pending count not yet in the file would
   otherwise be added on top of a bound that already holds it). */
static int g_rc_save_ok;
static int rc_apply(int game, int slot, unsigned char *manager);
/* The last primary save this session wrote and exported: its slot and
   manager, and whether the reconcile could have run at it (g_rc_save_ok).
   VvfpStatisticsRepairReconcileNow completes a Repair answered right after
   it -- the quit save -- from exactly that state. */
static struct {
    int slot;
    unsigned char *manager;
    int reconcile_ok;
} g_last_save;

static int write_statistics_file(int game_id, unsigned char *manager, int save_id, const char *village);

__declspec(dllexport) int __stdcall WriteVillageStatistics(
    int game_id,
    const void *manager_pointer,
    int save_id
) {
    /* The log reads the manager; the store's flush before the save is what
       zeroes the pending fields. */
    unsigned char *manager = (unsigned char *)manager_pointer;
    char village_name[VV_VILLAGE_NAME_MAX];
    /* Room for the name plus the fixed wrapper text and the slot. */
    char village[VV_VILLAGE_NAME_MAX + 32];
    int written;

    if (manager == NULL || save_id < 1 || save_id > 5) {
        return 0;
    }
    g_save_id = save_id;
    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    bind_store(game_id, manager, save_id);
    /* Village Elders: update the save's .dat now, before anything that can
       fail (the text log below), so every successful save records it. */
    g_elders_ready = 0;
    if (game_id == GAME_VV1) {
        vv1_village_elders(manager);
    } else if (game_id != GAME_VV2) {
        village_elders_for(game_id);
    }
    /* After Repair: what the save and the logs prove, before the log is
       written so it prints the result. */
    rc_apply(game_id, save_id, manager);
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
    written = write_statistics_file(game_id, manager, save_id, village);
    if (written < 0) {
        return 0;
    }
    write_village_population(game_id, village);
    return written;
}

/* The Village Statistics log of `save_id`, written from the manager and the
   slot's .dat (temporary file, then moved over the log): 1 written, 0 not
   (nothing left behind), -1 the paths could not be built.  From
   WriteVillageStatistics at every save, and again by the reconcile's Repair
   right after the quit save (statistics_reconcile.inc), so the log shows
   the repaired counters. */
static int write_statistics_file(int game_id, unsigned char *manager, int save_id, const char *village) {
    wchar_t temporary[MAX_LONG_PATH];
    wchar_t destination[MAX_LONG_PATH];
    FILE *file;
    int written;
    int closed;
    int vv5_total;
    int vv5_solved;
    unsigned char *module;

    if (!build_output_paths(save_id, temporary, destination)) {
        return -1;
    }

    /* Text mode, so each \n becomes the CRLF a Windows text viewer expects.
       The statistics file is written and never read back, so nothing depends
       on its byte-for-byte length; a player opening it in Notepad does depend
       on the line breaks being there. */
    file = _wfopen(temporary, L"w");
    if (file == NULL) {
        /* The statistics temporary could not be created, but the roster's own
           destination may be perfectly writable, and the game reports the save
           as successful either way (WriteVillageStatistics). */
        return 0;
    }
    if (game_id == GAME_VV1) {
        written = write_vv1(file, manager, village);
    } else if (game_id == GAME_VV2) {
        written = write_vv2(file, manager, village);
    } else if (game_id == GAME_VV3) {
        unsigned int vv3_table, vv3_slots;
        vv3_villager_table((const unsigned char *)GetModuleHandleW(NULL), &vv3_table, &vv3_slots);
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
            /* No extra row. Villagers Died was removed at the owner's
               instruction -- Villagers Buried is the kept statistic,
               because it stays meaningful once the graveyard fills. Its
               wrappers still count into the .dat (villagers_died); only the
               row is gone. The Secret City has no debris row either; its
               stream puzzle differs. */
            -1, NULL,
            /* Chiefs Robed: advanced by the wrapper on the robing routine
               sub_45FBC0 -- the only writer of the chief flag in the image --
               so every replacement chief is counted, including the ones the
               one-shot chief puzzle never fires for. Kept in the slot's
               statistics .dat; the one-time baseline from a living chief
               (active +0xF10, chief flag +0xE80, runtime-confirmed in
               tests/test_vv3_everyone_tries_on_robe.py) is taken there. */
            1,
            /* The villager array: container 0x59E110 (accessor sub_45C840,
               record base 0x14, stride 0x1F8C, 150 slots), active byte
               +0xF10 -- or wherever the executable says it is (0x800000 and
               256 slots with 256 Villagers). */
            vv3_table, 0x14u, 0x1F8Cu, (int)vv3_slots,
            0xF10u,
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
            0u, 0u,
            GAME_VV3
        );
    } else if (game_id == GAME_VV4) {
        unsigned int vv4_table, vv4_slots;
        vv4_villager_table((const unsigned char *)GetModuleHandleW(NULL), &vv4_table, &vv4_slots);
        written = write_later_game(
            file,
            manager,
            village,
            "Virtual Villagers - The Tree of Life",
            /* +0x14 counts mushrooms only (writer 0x414665 on the mushroom
               award path; collectibles never touch it), and the game's own
               name for it is "Mushrooms Found" (sm.xml eCrabsFound). */
            "Mushrooms Found",
            0x850u,
            0x3750u,
            count_later_puzzles(0x38960u, 0xD8BF8u, 0, 16),
            16,
            /* Mausoleum. Accessor 0x45D650: base 0x5025C8, capacity 500,
               stride 0x5C, occupancy +0x1C. Burial writer 0x45D470. */
            0x1025C8u, 0x5Cu, 500u,
            /* Debris Cleared, counted by the wrapper on the stream-clearing
               action at 0x43965A -- the same event the Civil Engineer trophy
               credits a unit to, without that trophy's stop-once-earned cap
               -- into the slot's statistics .dat. Villagers Died was removed
               at the owner's instruction; its wrappers still count into the
               .dat, only the row is gone. */
            VVS_DEBRIS, "Debris Cleared",
            /* The Tree of Life has no chief. */
            0,
            /* The villager array, for Village Elders: container 0x50E568, the
               immediate all 55 of its accessor's callers load, with the
               record base, stride and slot count the parentage layout
               already carries for this game -- or wherever the executable
               says it is (0x800000 and 256 slots with 256 Villagers). */
            vv4_table, 0x44u, 0x2E3Cu, (int)vv4_slots,
            0x1CC4u,
            /* Skills at villager+0x1C5C, from `lea ebx,[edi+1C5Ch]` at
               0x45D4E3 in the burial writer. FLOAT32 against 88.0, five
               skills. */
            0x1C5Cu, 5u, 1,
            /* The grave elder flag the game's own burial writer stores at
               +0x31 (sub_46AC70's all-five-skills verdict). Village Elders
               itself comes from the per-save .dat (village_elders_for), and
               NOTHING is written to any grave: the old patch-owned byte
               +0x37 was overwritten by the stock dword store at +0x34
               (0x45D524), and seeding it pushed +0x34 out of the -1..4 range
               the memorial loader 0x45D6E0 accepts. */
            0x31u,
            0u, 0u,
            GAME_VV4
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

/* The game's full-save writer: __thiscall(manager; buffer, size, slot) with
   `ret 0xC`. __fastcall passes the first argument in ECX and the second in
   EDX, and its callee pops the stack arguments, so a fastcall pointer with an
   unused EDX slot calls it exactly as the game's own `call` does. */
typedef int (__fastcall *save_writer)(void *manager, void *unused,
                                      void *buffer, int size, int slot);

/* The whole primary-slot save, called by the save wrapper in the executable
   in place of the stock `call writer` (see scripts/build_statistics_features.py).

   1. Flush: every pending count and stew bit the hooks recorded since the
      last save goes into this slot's .dat files, and only once they are on
      disk are the pending fields zeroed -- in the live block and in the save
      buffer the writer is about to serialise -- so the save the game writes
      holds nothing patcher-owned.
   2. The stock writer runs with the game's own arguments, and its result is
      what the game sees, unchanged.
   3. After a successful save the statistics log is written from the .dat.

   The wrapper only calls this for slots 1..5 and when this export resolves;
   every other save goes straight to the writer. */
/* A NEW VILLAGE IN THE SAME SLOT.

   The slot's .dat files (statistics counters, stew discoveries, Village
   Elders) belong to one village. Start Over clears them through the reset
   companion, but that companion only ships with the Origins and parentage
   features; without them a new village started in the same slot would carry
   the old village's totals and stews. So the statistics companion checks for
   itself, the way the owner's rule says a village is identified: by its
   LIVING ROSTER, and by overlap -- any villager in common means the same
   village, because births and deaths change the roster during play.

   Each save records the living villagers in "Village Roster - Save N.dat":
   slot, name, and a fingerprint of what renaming does not change -- the
   likes and dislikes arrays and, where the record stores them, the parents'
   names. A recorded villager and a living one are the same when they share
   the slot AND either the name or the fingerprint, so a player renaming
   villagers never looks like a new village. "The slot" is the record the
   villager held when the roster was written OR its rank in that roster:
   the games load a save packed into records 0, 1, 2, ..., so after a
   reload everyone behind a death is at its rank (roster_match.c). If the next save's living
   roster shares no villager with the recorded one, the slot now holds a
   different village. The decision is made before the stock save, but it is
   committed only AFTER the save succeeds: the three .dat files are then
   moved aside as "... .previous-village-<ticks>-<n>.dat" (never deleted,
   never over an existing file) and the new roster is committed; the save
   that detects the change does not flush, so a new village's events can
   never merge into the old village's files, and a failed save changes
   nothing. If a move or the roster commit fails, the old roster stays and
   the next save retries. An empty recorded roster never triggers this. */
struct roster_layout {
    unsigned int villagers_rva;
    int rva_is_pointer;
    unsigned int record_base, stride, slots, active, name, name_capacity;
    /* rename-proof fingerprint: likes[n], dislikes[n] (i32), parents' names */
    unsigned int likes, dislikes, preference_slots;
    unsigned int father_name, mother_name, parent_name_capacity;
};

static const struct roster_layout ROSTER_LAYOUTS[6] = {
    { 0 },
    { 0x8B614u, 1, 0u, 0x3D8u, 256u, 0x28u, 0x370u, 0x1Cu,
      0x398u, 0x3A8u, 4u, 0u, 0u, 0u },                                  /* VV1 */
    { 0x99F24u, 1, 0u, 0xE48Cu, 256u, 0x30u, 0x564u, 0x18u,
      0x5F0u, 0x6E8u, 62u, 0x57Du, 0x596u, 0x18u },                      /* VV2 */
    { 0x19E110u, 0, 0x14u, 0x1F8Cu, 150u, 0xF10u, 0xDD4u, 0x19u,
      0xFB4u, 0xFC0u, 3u, 0xDF8u, 0xE11u, 0x19u },                       /* VV3 */
    { 0x10E568u, 0, 0x44u, 0x2E3Cu, 150u, 0x1CC4u, 0x1B9Cu, 0x19u,
      0x1E60u, 0x1E6Cu, 3u, 0x1BC0u, 0x1BD9u, 0x19u },                   /* VV4 */
    { 0x154148u, 0, 0x48u, 0x2F44u, 150u, 0x1CD4u, 0x1B9Cu, 0x19u,
      0x1F5Cu, 0x1F68u, 3u, 0x1BC0u, 0x1BD9u, 0x19u },                   /* VV5 */
};

#define ROSTER_MAX VV_ROSTER_MAX
#define ROSTER_NAME 32
#define ROSTER_ROW (ROSTER_NAME + 24)
static char g_roster_now[ROSTER_MAX][ROSTER_ROW];
static char g_roster_was[ROSTER_MAX][ROSTER_ROW];

static unsigned int fnv(unsigned int h, const unsigned char *p, unsigned int n) {
    unsigned int i;
    for (i = 0; i < n; ++i) {
        h = (h ^ p[i]) * 16777619u;
    }
    return h;
}

static unsigned int bounded_len(const unsigned char *p, unsigned int capacity) {
    unsigned int n = 0;
    while (n < capacity && p[n] != 0) {
        ++n;
    }
    return n;
}

static int living_roster(int game_id, char rows[ROSTER_MAX][ROSTER_ROW]) {
    struct roster_layout layout = ROSTER_LAYOUTS[game_id];
    const struct roster_layout *r = &layout;
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    const unsigned char *villagers;
    unsigned int slot;
    int count = 0;
    if (module == NULL) {
        return 0;
    }
    if (game_id == GAME_VV3) {
        vv3_villager_table(module, &layout.villagers_rva, &layout.slots);
    } else if (game_id == GAME_VV4) {
        vv4_villager_table(module, &layout.villagers_rva, &layout.slots);
    } else if (game_id == GAME_VV5) {
        vv5_villager_table(module, &layout.villagers_rva, &layout.slots);
    }
    villagers = r->rva_is_pointer ? *(unsigned char *const *)(module + r->villagers_rva)
                                  : module + r->villagers_rva;
    if (villagers == NULL) {
        return 0;
    }
    for (slot = 0; slot < r->slots && count < ROSTER_MAX; ++slot) {
        const unsigned char *record = villagers + r->record_base + slot * r->stride;
        char name[ROSTER_NAME];
        unsigned int i;
        if (record[r->active] != 1 || vv_lookalike(r->stride, record)) {
            continue;
        }
        for (i = 0; i < r->name_capacity && i < ROSTER_NAME - 1 && record[r->name + i] != 0; ++i) {
            name[i] = (record[r->name + i] == '\t' || record[r->name + i] < 0x20) ? ' ' : (char)record[r->name + i];
        }
        name[i] = '\0';
        {
            /* A villager with no likes, no dislikes and no parents has
               nothing to fingerprint: every such villager would share one
               value (21 of the owner's 28 A New Home villagers did), and
               any two villages' would match.  "-" says so; roster_match.c
               then compares the name alone. */
            /* Empty is -1 OR an index past the end of the game's preference
               list -- both occur in real villages (population_export.c,
               first_preference; Codex, #524): 47 entries in A New Home, 62
               in The Lost Children, 79 in the later three. */
            static const int PREFERENCES[6] = { 0, 47, 62, 79, 79, 79 };
            unsigned int h = 2166136261u;
            int any = 0;
            for (i = 0; i < 2u * r->preference_slots; ++i) {
                unsigned int base = i < r->preference_slots ? r->likes : r->dislikes;
                int value = *(const int *)(record + base + (i % r->preference_slots) * 4u);
                if (value >= 0 && value < PREFERENCES[game_id]) {
                    any = 1;
                }
            }
            if (r->father_name != 0u && (record[r->father_name] != 0 || record[r->mother_name] != 0)) {
                any = 1;
            }
            h = fnv(h, record + r->likes, r->preference_slots * 4u);
            h = fnv(h, record + r->dislikes, r->preference_slots * 4u);
            if (r->father_name != 0u) {
                h = fnv(h, record + r->father_name, bounded_len(record + r->father_name, r->parent_name_capacity));
                h = fnv(h, (const unsigned char *)"|", 1u);
                h = fnv(h, record + r->mother_name, bounded_len(record + r->mother_name, r->parent_name_capacity));
            }
            if (any) {
                _snprintf_s(rows[count], ROSTER_ROW, _TRUNCATE, "%u\t%s\t%08X", slot, name, h);
            } else {
                _snprintf_s(rows[count], ROSTER_ROW, _TRUNCATE, "%u\t%s\t-", slot, name);
            }
        }
        ++count;
    }
    return count;
}

/* 1 = moved (or nothing to move), 0 = the file is still in place. Never
   replaces an existing file: tries -0, -1, ... until a name is free. */
static int move_aside(const wchar_t *path, unsigned long long stamp) {
    wchar_t aside[MAX_PATH];
    int n;
    if (path == NULL || path[0] == L'\0' || GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) {
        return 1;
    }
    for (n = 0; n < 1000; ++n) {
        if (_snwprintf_s(aside, MAX_PATH, _TRUNCATE, L"%ls.previous-village-%llu-%d.dat", path, stamp, n) <= 0) {
            return 0;
        }
        if (MoveFileExW(path, aside, 0)) {
            return 1;
        }
        if (GetFileAttributesW(aside) == INVALID_FILE_ATTRIBUTES) {
            return 0;          /* the name was free and the move still failed */
        }
    }
    return 0;
}

static int g_roster_now_count;
static int g_roster_was_count;        /* rows of g_roster_was read by this save's village_changed */

/* "Villagers Counted - Save N.dat" -- "Village Roster - Save N.dat" in older builds, read and
   written under that name, never renamed; under both names, the one written last
   (native/shared/save_layout.h).  The temporary file is in the same folder either way. */
static int roster_paths(int save_id, wchar_t *roster, wchar_t *temporary) {
    wchar_t folder[MAX_PATH], old[MAX_PATH];
    if (!vv_save_subfolder_w(folder, L"Virtual Villagers Fun Patcher Data\\Village Statistics", 64)
        || _snwprintf_s(roster, MAX_PATH, _TRUNCATE, L"%ls\\Villagers Counted - Save %d.dat", folder, save_id) <= 0
        || _snwprintf_s(temporary, MAX_PATH, _TRUNCATE, L"%ls\\Villagers Counted - Save %d.tmp", folder, save_id) <= 0
        || _snwprintf_s(old, MAX_PATH, _TRUNCATE, L"%ls\\Village Roster - Save %d.dat", folder, save_id) <= 0) {
        return 0;
    }
    if (vv_layout_pick_file_w(old, roster)) {
        lstrcpyW(roster, old);
    }
    return 1;
}

/* BEFORE the save: what does the slot hold? Reads only; changes nothing on
   disk.
     ROSTER_SAME     the same village, or nothing to compare yet (the roster
                     file does not exist: the first save with this build)
     ROSTER_NEW      a different village: no living villager is shared. A
                     villager is shared when it has the same slot and the
                     same fingerprint (the owner's rule: any overlap is the
                     same village, so a two-villager village where one died
                     and one was born is still itself). A same-slot NAME
                     alone is weaker -- names come from fixed pools, so a new
                     village's founders coincide with the old roster's names
                     routinely -- and name-only matches decide it only as a
                     strict majority of the smaller roster (a survivor whose
                     likes changed).
     ROSTER_DAMAGED  the roster exists but is not a valid roster: identity is
                     unknown, so it is handled as a new village -- the old
                     files are archived, never merged into
     ROSTER_LOCKED   the roster exists but cannot be opened: identity is
                     unknown and nothing can be committed; this save neither
                     flushes nor commits, and the next save retries */
enum { ROSTER_SAME = 0, ROSTER_NEW = 1, ROSTER_DAMAGED = 2, ROSTER_LOCKED = 3 };

static int village_changed(int game_id, int save_id) {
    wchar_t roster[MAX_PATH], temporary[MAX_PATH];
    FILE *f;
    char line[128];
    int was = 0;
    int i;
    g_roster_was_count = 0;
    g_roster_now_count = living_roster(game_id, g_roster_now);
    if (!roster_paths(save_id, roster, temporary)) {
        return ROSTER_LOCKED;
    }
    if (GetFileAttributesW(roster) == INVALID_FILE_ATTRIBUTES) {
        return ROSTER_SAME;           /* no roster yet: the first save with this build */
    }
    if (_wfopen_s(&f, roster, L"rb") != 0 || f == NULL) {
        return ROSTER_LOCKED;
    }
    if (fgets(line, sizeof(line), f) == NULL || strncmp(line, "VVFP VILLAGE ROSTER v1", 22) != 0) {
        fclose(f);
        return ROSTER_DAMAGED;
    }
    while (was < ROSTER_MAX && fgets(g_roster_was[was], ROSTER_ROW, f) != NULL) {
        size_t len = strlen(g_roster_was[was]);
        int tabs = 0;
        while (len > 0 && (g_roster_was[was][len - 1] == '\n' || g_roster_was[was][len - 1] == '\r')) {
            g_roster_was[was][--len] = '\0';
        }
        if (len == 0) {
            continue;
        }
        for (i = 0; g_roster_was[was][i] != '\0'; ++i) {
            tabs += g_roster_was[was][i] == '\t';
        }
        if (tabs != 2) {              /* every row is slot<TAB>name<TAB>fingerprint */
            fclose(f);
            return ROSTER_DAMAGED;
        }
        ++was;
    }
    fclose(f);
    g_roster_was_count = was;         /* where these villagers come back after a reload: Village Elders */
    if (was == 0 || g_roster_now_count == 0) {
        return ROSTER_SAME;           /* nothing to compare */
    }
    return vv_roster_same_village(&g_roster_was[0][0], was, &g_roster_now[0][0], g_roster_now_count,
                                  ROSTER_ROW) ? ROSTER_SAME : ROSTER_NEW;
}

static void elders_ranks(struct elders_layout *l) {
    static int rank_of_slot[ROSTER_MAX];
    int i;
    for (i = 0; i < ROSTER_MAX; ++i) {
        rank_of_slot[i] = -1;
    }
    for (i = 0; i < g_roster_was_count; ++i) {
        int slot = atoi(g_roster_was[i]);
        if (slot >= 0 && slot < ROSTER_MAX) {     /* the file's own number: never trusted as an index */
            rank_of_slot[slot] = i;
        }
    }
    l->rank_of_slot = rank_of_slot;
    l->rank_slots = ROSTER_MAX;
}

/* AFTER the stock save succeeded: for a new village, move the slot's three
   .dat files aside (never deleted, never over an existing file), then
   commit the living roster. Returns 1 only if everything that had to happen
   did. On failure the old roster stays, so the next save detects the change
   again and retries -- and, because a detected change suppresses that
   save's flush, nothing is ever merged into the wrong village's files or
   reset in a loop. */
static int commit_roster(int save_id, int changed, int damaged) {
    wchar_t roster[MAX_PATH], temporary[MAX_PATH], elders[MAX_PATH], elders_folder[MAX_PATH];
    FILE *f;
    int j;
    int ok = 1;
    if (g_roster_now_count == 0 || !roster_paths(save_id, roster, temporary)) {
        return !changed;
    }
    if (changed) {
        unsigned long long stamp = (unsigned long long)GetTickCount64();
        ok = move_aside(g_store_counters, stamp);
        ok = move_aside(g_store_stews, stamp) && ok;
        if (vv_save_subfolder_w(elders_folder, L"Virtual Villagers Fun Patcher Data\\Village Elders", 64)
            && _snwprintf_s(elders, MAX_PATH, _TRUNCATE, L"%ls\\Village Elders - Save %d.dat",
                            elders_folder, save_id) > 0) {
            ok = move_aside(elders, stamp) && ok;
        } else {
            ok = 0;
        }
        /* A roster that could not be read is moved aside, never overwritten,
           and only once everything else has moved: until then it keeps the
           next save treating the slot as unknown. */
        if (ok && damaged) {
            ok = move_aside(roster, stamp);
        }
        if (!ok) {
            return 0;                 /* keep the recorded roster: retry next save */
        }
    }
    /* Text mode: the C runtime writes the Windows line endings, as for every
       other file this companion writes. */
    if (_wfopen_s(&f, temporary, L"w") != 0 || f == NULL) {
        return 0;
    }
    fputs("VVFP VILLAGE ROSTER v1\n", f);
    for (j = 0; j < g_roster_now_count; ++j) {
        fprintf(f, "%s\n", g_roster_now[j]);
    }
    if (fclose(f) != 0) {
        DeleteFileW(temporary);
        return 0;
    }
    if (!MoveFileExW(temporary, roster, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}

__declspec(dllexport) int __stdcall SaveVillageStatistics(
    int game_id,
    void *manager_pointer,
    int save_id,
    void *writer,
    void *buffer,
    int size
) {
    unsigned char *manager = (unsigned char *)manager_pointer;
    int result;
    int primary = manager != NULL && save_id >= 1 && save_id <= 5
        && game_id >= GAME_VV1 && game_id <= GAME_VV5;
    int changed = 0;
    int flushed = 0;
    if (primary) {
        bind_store(game_id, manager, save_id);
        /* Decided before the save, committed only after it succeeds. When
           the slot holds a new village this save does not flush: its pending
           events stay in memory and in the save it writes, and are flushed
           into fresh files by the next save, once the rollover is committed.
           A failed save therefore changes nothing on disk. */
        changed = village_changed(game_id, save_id);
        if (changed == ROSTER_SAME) {
            flushed = vvs_flush(&g_store);
        }
    }
    result = ((save_writer)writer)(manager_pointer, NULL, buffer, size, save_id);
    if (primary && (result & 0xFF) != 0 && changed != ROSTER_LOCKED) {
        int is_new = changed == ROSTER_NEW || changed == ROSTER_DAMAGED;
        int committed = commit_roster(save_id, is_new, changed == ROSTER_DAMAGED);
        /* After a rollover that did not fully commit, the files on disk may
           still be the previous village's: write nothing (no elder update,
           no log) until the next save completes it. */
        g_last_save.slot = 0;
        if (!is_new || committed) {
            g_rc_save_ok = changed == ROSTER_SAME && (flushed & 1) != 0;
            WriteVillageStatistics(game_id, manager_pointer, save_id);
            g_last_save.slot = save_id;
            g_last_save.manager = manager;
            g_last_save.reconcile_ok = g_rc_save_ok;
            g_rc_save_ok = 0;
        }
    } else if (primary) {
        g_last_save.slot = 0;         /* this save failed: nothing to complete from */
    }
    return result;
}

#include "statistics_reconcile.inc"
