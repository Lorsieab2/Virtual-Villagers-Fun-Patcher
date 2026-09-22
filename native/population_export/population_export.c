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
#include "save_folder.h"
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

/* The preference list each game indexes for likes and dislikes.

   One comma-separated list per game, matching the string the executable keeps
   in its own table under eSayLikesList / eSayDislikesList. It grew across the
   series -- 47 entries in VV1, 62 in VV2, 79 in the three later games -- so a
   game must use its own rather than a shared one, and the list is ZERO-BASED:
   index 0 is "ants", with no adjustment.

   Held here rather than read out of the running executable because the address
   differs per game and this companion already receives the game id; reading it
   from the image would add a second thing to keep in step for no benefit. */
static const char PREFERENCES_47[] =
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,"
    "the dark,caves,herbs,berries,snakes,wind,rocks,heights,the ocean,playing,"
    "exploring,blue,green,red,yellow,drums,bushes,bananas,coconuts,sand,"
    "sunlight,rough wood,crab meat,whale meat,fish,fruit,papaya,flies,"
    "swimming,running,learning,dancing,monkeys,parrots,work,lifting,surprises,"
    "jokes";

static const char PREFERENCES_62[] =
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,"
    "flowers,bees,the dark,caves,herbs,berries,snakes,wind,rocks,"
    "heights,the ocean,playing,exploring,blue,green,red,yellow,drums,"
    "bushes,bananas,coconuts,sand,sunlight,wood,crab meat,whale meat,"
    "fish,fruit,papaya,flies,swimming,running,learning,dancing,"
    "monkeys,parrots,work,lifting,surprises,jokes,sleeping,jumping,"
    "cooking,fire,eating,dragonflies,owls,dreaming,children,talking,"
    "holidays,vegetables,quiet,clouds,dirt";

static const char PREFERENCES_79[] =
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,"
    "the dark,caves,herbs,berries,snakes,wind,rocks,heights,the ocean,playing,"
    "exploring,blue,green,red,yellow,drums,bushes,bananas,coconuts,sand,"
    "sunlight,wood,crab meat,whale meat,fish,fruit,papaya,flies,swimming,"
    "running,learning,dancing,monkeys,parrots,work,lifting,surprises,jokes,"
    "sleeping,jumping,cooking,fire,eating,dragonflies,owls,dreaming,children,"
    "talking,holidays,vegetables,quiet,clouds,dirt,frogs,soap,magic,plants,"
    "rain,fog,sitting,sharks,honey,stories,coral,thunder,lightning,pearls,"
    "stars,mango,nature";

/* Copy the index-th comma-separated entry of `list` into `out`.

   Returns 0 when the index is outside the list, which is how an empty slot and
   a corrupt one both end up reported as absent rather than as a wrong name. */
static int preference_name(
    const char *list,
    int index,
    char *out,
    size_t out_size
) {
    const char *start = list;
    int current = 0;
    size_t length;
    if (list == NULL || index < 0) {
        return 0;
    }
    while (current < index) {
        const char *comma = strchr(start, ',');
        if (comma == NULL) {
            return 0;   /* index past the end of the list */
        }
        start = comma + 1;
        ++current;
    }
    {
        const char *comma = strchr(start, ',');
        length = comma == NULL ? strlen(start) : (size_t)(comma - start);
    }
    if (length == 0 || length + 1 > out_size) {
        return 0;
    }
    memcpy(out, start, length);
    out[length] = '\0';
    return 1;
}

/* The first filled entry of a preference array, or 0 when every slot is empty.

   Empty is -1 OR an index past the end of the list; both appear in real
   villages. Scanning for the first filled slot rather than reading slot 0 is
   what matches the game's own Details panel. */
static int first_preference(
    const unsigned char *record,
    unsigned int base,
    unsigned int slots,
    const char *list,
    char *out,
    size_t out_size
) {
    unsigned int slot;
    if (base == 0u || list == NULL) {
        return 0;
    }
    for (slot = 0; slot < slots; ++slot) {
        int value = *(const int *)(record + base + slot * 4u);
        if (value < 0) {
            continue;
        }
        if (preference_name(list, value, out, out_size)) {
            return 1;
        }
    }
    return 0;
}

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
    /* How villagers_rva reaches the array.
       0: the RVA IS the array (VV3, VV4, VV5).
       1: the RVA is a GLOBAL holding a pointer to it (VV1, VV2).

       Kept as its own field rather than folded into the RVA, because the two
       cases differ in a way that must not be lost: VV1's and VV2's arrays are
       allocated LAZILY, so the global reads null until the game first builds
       one. Treating such an RVA as the array walks the pointer variable
       itself and reads 256 records of neighbouring .data. */
    int villagers_rva_is_pointer;
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
    /* The villager's likes and dislikes.

       Each is an ARRAY of consecutive i32 indices into the game's own
       preference list, not a single field -- the owner's rule: "in general
       likes and dislikes are arrays for all 5 games". A slot is empty when it
       reads -1 or a value at or past the end of the list; both markers occur
       in real villages and mean the same thing.

       The game's Details panel shows the FIRST FILLED entry of each array, so
       that is what this reports. Two villagers made that structure visible:
       one whose first dislike slot was empty and whose second held the value
       the panel displayed, and one whose three dislike slots were all empty
       and whose panel line was blank.

       Zero when the offsets are not established for a game. */
    unsigned int likes;
    unsigned int dislikes;
    unsigned int preference_slots;
    /* Which preference list this game's indices refer to. The list length
       differs per game, so indexing VV1's 47 entries with a VV5 index would
       silently produce the wrong word rather than fail. */
    const char *preference_list;
    const char *title;
};

static const struct game_layout GAME_LAYOUTS[6] = {
    /* index 0 unused so a game id indexes directly */
    { 0 },
    /* VV1 -- A New Home.
       The array is a lazily-allocated singleton behind the global at
       0x48B614 (RVA 0x8B614): the game loads it, and on the null path
       allocates 0x3E034 bytes, constructs, and stores the result back.
       Three checks agree that this allocation is the villager array --
       256 * 0x3D8 = 0x3D800 fits inside it with a 0x834 trailer, the
       manager field the conception routine reads with
       `mov edi,[edi+0x3E010]` falls inside that trailer rather than past
       the end, and the global is in .data with the WRITE bit, read once and
       written twice, which is the shape of a lazily-built singleton.

       VV1 copies nothing about the father onto the mother, so the father
       block is zero here and those lines are simply absent from its roster.
       Its skill table comes from the shipped Origins Full Mastery
       walker, which sets every villager's every skill to mastered and so
       has to know exactly where they are: it compares [esi+0x3BC] through
       [esi+0x3CC] against 100 while striding esi by 0x3D8. That is the
       same stride this row already carries, and the five fields sit just
       above the likes and dislikes arrays at 0x398 and 0x3A8. */
    {
        1, 0x8B614u, 1,
        0u, 0x3D8u, 256u,
        0x28u, 0x348u, 0x360u, 0x364u,
        0x370u, 0x1Cu,
        0u, 0u, 0u, 0u,
        0x3BCu, 5u, 0,
        0x398u, 0x3A8u, 4u,
        PREFERENCES_47,
        "Virtual Villagers 1"
    },
    /* VV2 -- The Lost Children. The same singleton shape as VV1: the global
       at 0x499F24 (RVA 0x99F24), allocation 0xE57500, and the manager field
       the shipped statistics companion already reads at +0xE574D4 falls
       inside the 0xE900 trailer after 256 * 0xE48C = 0xE48C00.

       That manager offset is what located the allocation. Searching for
       0xE48C * slots found nothing at any slot count, because the object is
       larger than its slots; searching at or above the manager field's own
       offset returned exactly one candidate.

       VV2 copies the father's head and body onto the mother at conception
       (+0x5E0 and +0x5DC, body four bytes BEFORE head as in every game), and
       his name at +0x5C0. */
    {
        1, 0x99F24u, 1,
        0u, 0xE48Cu, 256u,
        0x30u, 0x530u, 0x548u, 0x54Cu,
        0x564u, 0x18u,
        0x5C0u, 0x18u, 0x5E0u, 0x5DCu,  /* capacity spelled out; parentage
           declares 0 for this, meaning "same as the villager's own name",
           which for VV2 is 0x18 -- the same number, stated rather than
           implied, because this exporter has no such defaulting rule */
        /* Five int32 skills, from the shipped Origins Full Mastery
           walker: it compares [esi+0x7E4] through [esi+0x7F4] against
           100 while striding esi by 0xE48C, the stride this row already
           carries. The standalone Full Mastery candidate agrees in both
           of its build modes and additionally compares against 0x58,
           the game's own mastery predicate. */
        0x7E4u, 5u, 0,
        /* Confirmed from two independent sources rather than the game's own
           Details panel: VV2's stock executable crashes on startup on the
           owner's machine (0xC0000005 at 0x44C823, an unbounded villager-array
           walk), so no screen was available to read. The offsets were derived
           from a save file and, separately, from live memory in the owner's
           fixed modded build, and the two agree villager by villager. */
        /* 62 slots, not 4: 0x6E8 - 0x5F0 is exactly 62 dwords, the VV2
           Origins companion declares likes[62]/dislikes[62] and walks all
           of them, and dislikes[62] ends at 0x7E0 where the skills begin
           at 0x7E4.  A count of 4 reported "(none)" for any villager
           whose first filled entry sat in slots 4..61. */
        0x5F0u, 0x6E8u, 62u,
        PREFERENCES_62,
        "Virtual Villagers 2"
    },
    /* VV3 -- The Secret City. Skills are INT32 here and the game's own
       predicate compares against 0x58, so the float path must not be used. */
    {
        1, 0x19E110u, 0,
        0x14u, 0x1F8Cu, 150u,
        0xF10u, 0xDC4u, 0xDF0u, 0xDF4u,
        0xDD4u, 0x19u,
        0xE48u, 0x18u, 0xE68u, 0xE64u,
        0xEACu, 5u, 0,
        0xFB4u, 0xFC0u, 3u,
        PREFERENCES_79,
        "Virtual Villagers 3"
    },
    /* VV4 -- The Tree of Life. */
    {
        1, 0x10E568u, 0,
        0x44u, 0x2E3Cu, 150u,
        0x1CC4u, 0x1B8Cu, 0x1BB8u, 0x1BBCu,
        0x1B9Cu, 0x19u,
        0x1C10u, 0x18u, 0x1C30u, 0x1C2Cu,
        0x1C5Cu, 5u, 1,
        0x1E60u, 0x1E6Cu, 3u,
        PREFERENCES_79,
        "Virtual Villagers 4"
    },
    /* VV5 -- New Believers. Six skills, one more than VV3 and VV4. */
    {
        1, 0x154148u, 0,
        0x48u, 0x2F44u, 150u,
        0x1CD4u, 0x1B8Cu, 0x1BB8u, 0x1BBCu,
        0x1B9Cu, 0x19u,
        0x1C10u, 0x18u, 0x1C30u, 0x1C2Cu,
        0x1C5Cu, 6u, 1,
        0x1F5Cu, 0x1F68u, 3u,
        PREFERENCES_79,
        "Virtual Villagers 5"
    }
};

/* The skill names, per game, in the order EACH GAME STORES THEM.

   A game's Details screen lists the skills in one order and the record
   stores them in another, and the orders differ BETWEEN games too, so one
   game's answer must never be assumed for another.  VV1 and VV2 hold
   Building at index 1; VV3, VV4 and VV5 hold it at index 4.

   Every order below is measured against the owner's running game, each
   slot named by a villager whose own Details screen showed that bar.  The
   table immediately below is the original, kept for any game not yet
   checked against its own screen. */
static const char *const SKILL_NAMES_UNVERIFIED[MAX_SKILLS] = {
    "Farming", "Building", "Research", "Healing", "Breeding", "Parenting",
    "(skill 7)", "(skill 8)"
};

/* VV1 -- A New Home.  Storage order, measured:
     Yepa, a child with one non-zero skill, holds it at index 4 and her
     screen shows Research; Rongo's five distinct values (29, 39, 50, 59,
     78) rank shortest to longest Breeding, Building, Farming, Healing,
     Research. */
static const char *const SKILL_NAMES_VV1[MAX_SKILLS] = {
    "Breeding", "Building", "Farming", "Healing", "Research", "(skill 6)",
    "(skill 7)", "(skill 8)"
};

/* VV2 -- The Lost Children.  Storage order, measured:
     Jade [61, 0, 0, 100, 0] names Parenting and Healing; Buru
     [0, 91, 0, 0, 0] names Building; Dodo [0, 0, 93, 0, 100] names Farming
     and Research; Tatau [0, 0, 0, 46, 0] names Healing. */
static const char *const SKILL_NAMES_VV2[MAX_SKILLS] = {
    "Parenting", "Building", "Farming", "Healing", "Research", "(skill 6)",
    "(skill 7)", "(skill 8)"
};

/* VV3 -- The Secret City.  Storage order, measured:
     Vinapu names Farming, Yasawa names Building and Parenting, Dino
     names Healing, Totolo names Research. */
static const char *const SKILL_NAMES_VV3[MAX_SKILLS] = {
    "Farming", "Parenting", "Healing", "Research", "Building", "(skill 6)",
    "(skill 7)", "(skill 8)"
};

/* VV4 -- The Tree of Life.  Storage order, measured:
     Tapa names Farming, Pai names Healing and Parenting, Dodi names
     Research, Piko names Building.  Stored as floats. */
static const char *const SKILL_NAMES_VV4[MAX_SKILLS] = {
    "Farming", "Parenting", "Healing", "Research", "Building", "(skill 6)",
    "(skill 7)", "(skill 8)"
};

/* VV5 -- New Believers.  Storage order, measured:
     Six skills, Devotion last.  Pari names Farming, Apatoa names
     Healing, Turuki names Research, Moti names Devotion; all four
     corroborate Parenting at index 1 and Building at index 4. */
static const char *const SKILL_NAMES_VV5[MAX_SKILLS] = {
    "Farming", "Parenting", "Healing", "Research", "Building", "Devotion",
    "(skill 7)", "(skill 8)"
};

static const char *const *skill_names_for(int game_id) {
    if (game_id == GAME_VV1) { return SKILL_NAMES_VV1; }
    if (game_id == GAME_VV2) { return SKILL_NAMES_VV2; }
    if (game_id == GAME_VV3) { return SKILL_NAMES_VV3; }
    if (game_id == GAME_VV4) { return SKILL_NAMES_VV4; }
    if (game_id == GAME_VV5) { return SKILL_NAMES_VV5; }
    return SKILL_NAMES_UNVERIFIED;
}

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
    /* A zero skill count means "this game's skill table is not established",
       which VV1 and VV2 legitimately are. Their rosters omit the Skills block
       entirely rather than printing a guessed offset's contents. */
    if (g->skill_count > MAX_SKILLS) {
        return 0;
    }
    if (g->active + 1u > g->stride) return 0;
    if (g->age + WORD > g->stride) return 0;
    if (g->head + WORD > g->stride) return 0;
    if (g->body + WORD > g->stride) return 0;
    if (g->name + g->name_capacity > g->stride) return 0;
    if (g->skill_count != 0u
            && g->skills + g->skill_count * WORD > g->stride) {
        return 0;
    }
    /* Both preference arrays, when declared, must fit whole. A slot reaching
       past the stride would read the NEXT villager's record and report one
       villager's taste as another's. */
    if (g->likes != 0u || g->dislikes != 0u) {
        if (g->likes == 0u || g->dislikes == 0u || g->preference_slots == 0u) {
            return 0;
        }
        if (g->likes + g->preference_slots * WORD > g->stride) return 0;
        if (g->dislikes + g->preference_slots * WORD > g->stride) return 0;
    }
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

/* Build "<exe folder>\Village Population <n>.txt" and its .tmp sibling.

   Two paths, because the roster is published by writing the temporary and
   renaming over the destination. Truncating the destination up front would
   destroy the last good snapshot before a single villager had been written,
   so a full disk or a crash mid-write would leave the player with an empty
   roster where they previously had a complete one. The statistics companion
   already publishes this way; this follows it. */
static int build_log_paths(
    int index,
    wchar_t *temporary,
    wchar_t *destination
) {
    wchar_t module_path[MAX_LONG_PATH];
    /* The export belongs with the SAVE, not with the executable.
       See native/shared/save_folder.h: this used to strip to the exe's own
       directory, which put exported logs in the install folder while the
       village they describe lives under Documents\LDW\<exe basename>\. */
    /* The owner's layout: every exported log lives under
       <save folder>\VVFP Logs\, one subfolder per kind. The roster is
       "Tribe Population". */
    if (!vv_save_subfolder_w(module_path, L"VVFP Logs\\Tribe Population", 64)) {
        return 0;
    }
    if (_snwprintf_s(
            temporary, MAX_LONG_PATH, _TRUNCATE,
            L"%ls\\Village Population %d.tmp", module_path, index) < 0) {
        return 0;
    }
    if (_snwprintf_s(
            destination, MAX_LONG_PATH, _TRUNCATE,
            L"%ls\\Village Population %d.txt", module_path, index) < 0) {
        return 0;
    }
    return 1;
}

/* Close the temporary and rename it over the destination.

   Returns 0 on any failure, having removed the temporary so a half-written
   roster is never left lying beside the executable. */
static int publish_file(FILE *file, const wchar_t *temporary,
                        const wchar_t *destination) {
    /* Flushed separately from the close so a write error is seen while it can
       still fail the call, rather than being swallowed by fclose and leaving
       a truncated file published as complete. */
    if (fflush(file) != 0) {
        fclose(file);
        DeleteFileW(temporary);
        return 0;
    }
    if (fclose(file) != 0) {
        DeleteFileW(temporary);
        return 0;
    }
    if (!MoveFileExW(temporary, destination,
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}

/* Write one villager's block. Returns 0 on any write failure. */
/* ---- A New Home: the villager's OWN parents -----------------------------

   Every other game records only the father of a pregnancy on the mother,
   which is what the "Father:" block below prints.  A New Home records
   nothing -- but "VVFP VV1 Parentage.dll" (Show Parents in Details Screen)
   keeps each villager's own mother and father in a sidecar, and hands them
   back by record index.  Resolved once, from the executable's own directory,
   never from DllMain; absent companion, absent block. */
typedef int (__stdcall *vv1_parents_query_t)(int index, int *out);
typedef int (__stdcall *vv1_parents_names_t)(int index, char *father, char *mother, int capacity);
static int vv1_parents_state;     /* 0 = not tried, 1 = resolved, -1 = unavailable */
static vv1_parents_query_t vv1_parents_query;
static vv1_parents_names_t vv1_parents_names;

static int vv1_parents_resolve(void) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    HMODULE companion;
    if (vv1_parents_state != 0) {
        return vv1_parents_state == 1;
    }
    vv1_parents_state = -1;
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    slash = strrchr(path, '\\');
    if (slash == NULL
        || (size_t)(slash + 1 - path) + sizeof("VVFP VV1 Parentage.dll") > sizeof(path)) {
        return 0;
    }
    lstrcpyA(slash + 1, "VVFP VV1 Parentage.dll");
    companion = LoadLibraryA(path);
    if (companion == NULL) {
        return 0;
    }
    vv1_parents_query = (vv1_parents_query_t)GetProcAddress(companion, "Vv1ParentageQuery");
    vv1_parents_names = (vv1_parents_names_t)GetProcAddress(companion, "Vv1ParentageQueryNames");
    if (vv1_parents_query == NULL || vv1_parents_names == NULL) {
        return 0;
    }
    vv1_parents_state = 1;
    return 1;
}

/* The block, when at least one parent is known.  Returns 0 only on a write
   failure. */
static int write_vv1_own_parents(FILE *file, int index) {
    int parents[4];
    char father[MAX_NAME_BYTES];
    char mother[MAX_NAME_BYTES];
    int father_known, mother_known;
    if (!vv1_parents_resolve()
        || !vv1_parents_query(index, parents)
        || !vv1_parents_names(index, father, mother, (int)sizeof(father))) {
        return 1;
    }
    father_known = parents[0] >= 0 && parents[1] >= 0;
    mother_known = parents[2] >= 0 && parents[3] >= 0;
    if (!father_known && !mother_known) {
        return 1;
    }
    if (fprintf(file, "  Parents:\n") < 0) return 0;
    if (father_known) {
        if (fprintf(file, "    Father: %s\n      Head: %d\n      Body: %d\n",
                    father[0] ? father : "(unnamed)", parents[0], parents[1]) < 0) return 0;
    }
    if (mother_known) {
        if (fprintf(file, "    Mother: %s\n      Head: %d\n      Body: %d\n",
                    mother[0] ? mother : "(unnamed)", parents[2], parents[3]) < 0) return 0;
    }
    return 1;
}

static int write_villager(
    FILE *file,
    const struct game_layout *g,
    const unsigned char *record,
    int number,
    int game_id,
    int index
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

    /* Likes and dislikes, where the offsets are established.

       Printed only when a preference is actually present. A villager with no
       like recorded gets no Likes line at all, rather than a line saying
       "none" -- the game's own panel leaves it blank, and an empty line in a
       roster reads as a value rather than an absence. */
    if (g->likes != 0u) {
        const char *list = g->preference_list;
        char preference[64];
        if (first_preference(record, g->likes, g->preference_slots, list,
                             preference, sizeof(preference))) {
            if (fprintf(file, "  Likes: %s\n", preference) < 0) return 0;
        }
        if (first_preference(record, g->dislikes, g->preference_slots, list,
                             preference, sizeof(preference))) {
            if (fprintf(file, "  Dislikes: %s\n", preference) < 0) return 0;
        }
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
    if (game_id == GAME_VV1 && !write_vv1_own_parents(file, index)) {
        return 0;
    }

    /* Omitted entirely when the game's skill table is not established,
       rather than printing an empty heading that reads as "this villager
       has no skills" -- a different and false claim. VV1 and VV2 are in
       that position: their arrays are now reachable but their skill
       offsets are not measured. */
    if (g->skill_count == 0u) {
        return fprintf(file, "\n") >= 0;
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
        if (fprintf(file, "    %-10s %d\n",
                    skill_names_for(game_id)[skill], value) < 0) {
            return 0;
        }
    }

    return fprintf(file, "\n") >= 0;
}

/* "<save folder>\Village History.txt" -- the permanent log.

   One path, not two: the history is APPENDED, so there is no temporary to
   publish and nothing to rename over. A partial append at the end of the file
   is visibly partial, where a truncated roster would look complete. */
static int build_history_path(wchar_t *destination) {
    wchar_t module_path[MAX_LONG_PATH];
    if (!vv_save_subfolder_w(module_path, L"VVFP Logs\\Tribe History", 64)) {
        return 0;
    }
    return _snwprintf_s(
        destination, MAX_LONG_PATH, _TRUNCATE,
        L"%ls\\Village History.txt", module_path) >= 0;
}

/* Append this save's roster to the history.

   Failure is deliberately not fatal to the export: the roster is the feature
   the player relies on, and a history that could not be written must not stop
   it being published. Returns 1 on success, 0 on any write failure, and the
   caller ignores it for that reason. */
static int append_history(
    const struct game_layout *g,
    const unsigned char *villagers,
    int game_id,
    const char *village
) {
    wchar_t path[MAX_LONG_PATH];
    FILE *file;
    unsigned int index;
    int written = 0;
    SYSTEMTIME now;
    if (!build_history_path(path)) {
        return 0;
    }
    file = _wfopen(path, L"a");
    if (file == NULL) {
        return 0;
    }
    GetLocalTime(&now);
    if (fprintf(file,
                "=== %s -- %04d-%02d-%02d %02d:%02d:%02d ===\n%s\n",
                g->title,
                now.wYear, now.wMonth, now.wDay,
                now.wHour, now.wMinute, now.wSecond,
                village) < 0) {
        fclose(file);
        return 0;
    }
    for (index = 0; index < g->slots; ++index) {
        const unsigned char *record =
            villagers + g->record_base + index * g->stride;
        if (*(const unsigned char *)(record + g->active) != 1) {
            continue;
        }
        if (!write_villager(file, g, record, written + 1, game_id, (int)index)) {
            fclose(file);
            return 0;
        }
        ++written;
    }
    if (fprintf(file, "\n") < 0) {
        fclose(file);
        return 0;
    }
    return fclose(file) == 0;
}

/* Write every living villager, rolling to a new file every 256.

   Returns the number of villagers written, or 0 on failure. Zero is also the
   honest answer for an empty village, which cannot be distinguished from a
   failure by the return value alone -- the caller treats both the same way,
   because neither is actionable from inside the game. */
__declspec(dllexport) int __stdcall WriteVillagePopulation(
    int game_id,
    const void *module_pointer,
    /* "Village: <name> (Save <n>)\n", already assembled by the caller, or
       an empty string when the village could not be identified. The
       statistics companion builds it because it is the one hooked onto the
       save call, where the name and the slot are both in registers. */
    const char *village
) {
    const struct game_layout *g;
    const unsigned char *module = (const unsigned char *)module_pointer;
    const unsigned char *villagers;
    unsigned int index;
    int written = 0;
    int file_index = 1;
    int in_file = 0;
    FILE *file = NULL;
    wchar_t temporary[MAX_LONG_PATH];
    wchar_t destination[MAX_LONG_PATH];

    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    if (village == NULL) {
        village = "";
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
    if (g->villagers_rva_is_pointer) {
        /* Lazily allocated: null until the game first builds the village, so
           an export before that point must decline rather than walk zero. */
        villagers = *(const unsigned char *const *)villagers;
        if (villagers == NULL) {
            return 0;
        }
    }

    /* The first file is opened unconditionally, not lazily on the first live
       villager.

       An empty village is a real state -- every villager can die -- and it
       must produce an empty roster rather than leaving the previous one in
       place. Opening lazily meant a village that had just gone extinct kept
       displaying the villagers it had before, which is worse than saying
       nothing: the file looks current and is not. */
    if (!build_log_paths(file_index, temporary, destination)) {
        return 0;
    }
    file = _wfopen(temporary, L"w");
    if (file == NULL) {
        return 0;
    }
    if (fprintf(file, "%s Village Population\n%s\n", g->title, village) < 0) {
        fclose(file);
        DeleteFileW(temporary);
        return 0;
    }

    for (index = 0; index < g->slots; ++index) {
        const unsigned char *record =
            villagers + g->record_base + index * g->stride;
        if (*(const unsigned char *)(record + g->active) != 1) {
            continue;
        }
        if (file == NULL) {
            if (!build_log_paths(file_index, temporary, destination)) {
                return 0;
            }
            file = _wfopen(temporary, L"w");
            if (file == NULL) {
                return 0;
            }
            if (fprintf(file, "%s Village Population\n%s\n", g->title, village) < 0) {
                fclose(file);
                DeleteFileW(temporary);
                return 0;
            }
        }
        if (!write_villager(file, g, record, written + 1, game_id, (int)index)) {
            fclose(file);
            DeleteFileW(temporary);
            return 0;
        }
        ++written;
        ++in_file;
        if (in_file >= VILLAGERS_PER_FILE) {
            if (!publish_file(file, temporary, destination)) {
                return 0;
            }
            file = NULL;
            in_file = 0;
            ++file_index;
        }
    }

    if (file != NULL && !publish_file(file, temporary, destination)) {
        return 0;
    }

    /* The permanent history, appended AFTER the roster is safely
       published so a history failure can never cost the player their
       roster. Its return is ignored for the same reason. */
    (void)append_history(g, villagers, game_id, village);

    /* Remove any roster files a LARGER village left behind.

       A village that shrinks below a file boundary would otherwise keep the
       old higher-numbered files, and those describe villagers who are no
       longer there. Deleting them is the same reasoning as truncating the
       first file for an empty village: a stale roster that looks current is
       worse than an absent one.

       Bounded by the slot count rather than looping until a delete fails, so
       a permission error on one file cannot spin forever. */
    {
        int stale = file_index + 1;
        int limit = (int)(g->slots / VILLAGERS_PER_FILE) + 2;
        while (stale <= limit) {
            wchar_t old_temporary[MAX_LONG_PATH];
            wchar_t old_destination[MAX_LONG_PATH];
            if (!build_log_paths(stale, old_temporary, old_destination)) {
                break;
            }
            DeleteFileW(old_destination);
            ++stale;
        }
    }
    return written;
}
