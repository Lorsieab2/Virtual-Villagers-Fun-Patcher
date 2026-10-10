/* VVFP Parentage Export -- Virtual Villagers 1 (A New Home).

   Appends one plain-text record per conception to a log beside the game
   executable, capturing both parents while they are still identifiable.

   WHY CAPTURE AT CONCEPTION RATHER THAN AT BIRTH

   Parentage is not stored anywhere in a villager record. An independent RE
   audit of all four exact builds (data/mask_identity_adapters.json) found the
   inheritance path that writes a child's OWN head and body in each game, but
   no instruction that stores a mother_name, father_name, mother_head,
   father_head, mother_body or father_body into the child. Inheritance computes
   the child's own appearance and discards the parents' values.

   So the parents cannot be recovered from the child afterwards, at any later
   moment, by any amount of reading. They must be recorded at the instant the
   pregnancy begins, which is exactly what the owner's specification asks for
   and the only design that can work.

   WHERE THE DATA COMES FROM

   The hooks sit in VV1's conception routine, sub_43BBC0
   (0x00043BBC0 -> VA 0x0043BBC0), which is the only function in the image that
   increments all three birth counters. Those counter offsets are not guesses:
   they are the ones the shipping statistics companion already reads --

       manager + 0x9E24  Babies Made       inc at 0x43BC1C / 0x43BC5E / 0x43BC9C
       manager + 0x9E44  Twins Birthed     inc at 0x43BCC0
       manager + 0x9E48  Triplets Birthed     at 0x43BCA8 / 0x43BCB0

   Its decompiled form is:

       int __thiscall sub_43BBC0(int *this, int a2, int a3, int a4, int a5)
           v9 = this + 246 * a2;   // 246 * 4 == 0x3D8 == the record stride
           v9[215] = 2 or 3;       // record + 0x35C = litter size

   `246 * 4` reproducing the proven stride exactly is what establishes that
   `this` is the record array and `a2` is the MOTHER's record index.

   The litter size is written LATE, on the twins and triplets branches, which
   is why the hooks sit at the routine's success exits rather than its head --
   see the VV1 row in GAME_LAYOUTS for the full reasoning.

   FIELD OFFSETS

   Per-game offsets live in GAME_LAYOUTS below, each with the instruction that
   proves it. They are deliberately NOT duplicated here: an earlier version of
   this file carried a second copy under the heading "every offset here is
   proven", and when +0x394 was disproven the copy kept asserting it. A reader
   consulting the reference block got the wrong value, and the word "proven"
   made it look checked. One table, or the stale one wins.

   The name buffer start could not be found by the field-displacement audit
   because names are written by bulk string copies (sprintf), which take the
   buffer's ADDRESS and so leave no [reg+disp] access for a scan to see. It is
   0x1C bytes long: nothing at all is referenced between +0x370 and +0x38C, and
   +0x38C is the next field the conception routine itself writes. That also
   explains the warning in vv1_origins_icons.c that +0x374 "was inside the
   villager NAME buffer" -- it is four bytes into this one. */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

/* Internal by default; external under VV_PARENTAGE_TESTABLE so the
   harness can call select_log_file against real files on disk. The
   shipped DLL is built without the macro and keeps static linkage. */
#ifdef VV_PARENTAGE_TESTABLE
#define VV_PARENTAGE_STATIC
#else
#define VV_PARENTAGE_STATIC static
#endif

#include "village_identity.h"
#include "village_rename.h"
#include "villager_lookalike.h"  /* statues, ghosts and stand-ins are no villagers */
#include "save_folder.h"
#include "save_layout.h"
#include "log_words.h"
#include "birth_heading.h"        /* "Birth <n>", or an older log's "Birth" */
#include "special_title.h"
#include "custom_titles.h"
#include "former_heathens_read.h"
#include "mask_line.h"
#include "patcher_files.h"
#include "vv3_villager_table.h"
#include "vv4_villager_table.h"
#include "vv5_villager_table.h"

enum {
    /* The log sits beside the executable, so the path is bounded by the
       executable's own path plus a fixed filename.

       This is deliberately NOT the 32768-wchar_t long-path maximum the
       statistics companion uses. Two such buffers -- one here and one in
       build_log_path -- are live at the same time in this call chain, which
       would put 128 KB on the stack. That companion is called from the save
       handler; this one is called from the conception routine during ordinary
       gameplay, and a frame that large risks STATUS_STACK_OVERFLOW on any
       thread whose stack is smaller than the main one. MAX_PATH plus room for
       the filename costs 1 KB per buffer instead.

       GetModuleFileNameW is checked for truncation against this bound, so an
       executable installed under a genuinely longer path disables the log
       rather than writing to a truncated one. */
    MAX_LOG_PATH = 512,

    /* A fixed local bound for a name, checked against each game's own
       name_capacity before use, so adding a game with a longer name field
       fails the guard rather than overrunning these buffers. */
    MAX_NAME_BYTES = 64,

    /* How a game records the other parent.

       This is not a detail: a game that stores a father ID finds his record
       by scanning the array for it, while VV4 and VV5 store the father's NAME
       directly in the mother's record and keep no id anywhere. Reading one as
       the other interprets a name buffer as an integer, resolves nothing, and
       logs "(unknown)" for every single birth -- a feature that appears to work
       and records nothing useful. */
    FATHER_BY_ID = 0,
    FATHER_BY_NAME = 1,
    /* The game records nothing about the other parent that can be read back
       from the mother. No shipped row uses this any more; VV1, the case it was
       written for, now captures him instead (FATHER_BY_CAPTURE). */
    FATHER_NOT_RECORDED = 2,
    /* The game records nothing that identifies the father in the mother's
       record, but the CALLER hands us his record. VV1 only.

       This is a different situation from FATHER_NOT_RECORDED and collapsing
       the two would be wrong in both directions. There is no father field in
       the mother's record to copy a name from or resolve an id through (+0x394
       holds a copy of his +0x36C, which is not unique -- see the VV1 row). But
       each of the six callers of VV1's conception routine holds his record
       while it conceives, so the success-tail trampolines find him in the
       caller's frame -- by the return address into that caller -- and every
       father field comes from his own record, his name included.

       Nothing is passed through the routine's own arguments: all four are
       read, and the second is the value stored into the mother's +0x394,
       which the game acts on at delivery. An earlier design overwrote that
       argument with his pointer and so changed the game.

       A record is not guaranteed. A caller the trampolines do not recognise
       passes NULL, and the log says the father is unavailable for that birth
       rather than inventing him. */
    FATHER_BY_CAPTURE = 3,

    GAME_VV1 = 1,
    GAME_VV2 = 2,
    GAME_VV3 = 3,
    GAME_VV4 = 4,
    GAME_VV5 = 5,

    /* The owner asked for a roll "past ~256 villagers". One record per
       conception, and VV1's record array itself holds 256 slots, so 256
       records per file keeps a log to roughly one village's worth of births. */
    RECORDS_PER_FILE = 256

};

/* Per-game record geometry.

   Every field is an offset into a villager record, and every one has to be
   established by instruction-level evidence in that game's own executable
   before it is filled in here. A wrong offset does not crash -- it silently
   logs the wrong number, and because parentage cannot be recovered from the
   child afterwards, a wrong record is permanent.

   So the four games whose evidence is not yet in are declared with `supported`
   zero and left at zero. WriteParentageRecord refuses them outright rather
   than reading a plausible-looking guess. */
/* The preference list each game indexes for likes and dislikes.

   The same three lists the population exporter prints from, matching the
   string each executable keeps under eSayLikesList / eSayDislikesList: 47
   entries in VV1, 62 in VV2, 79 in the three later games.  ZERO-BASED: index 0
   is "ants", with no adjustment.  A game must use its own list -- a VV5 index
   read through VV1's 47 entries would silently print the wrong word. */
static const char PREFERENCES_47[] =
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,"
    "the dark,caves,herbs,berries,snakes,wind,rocks,rough wood,the ocean,"
    "playing,exploring,blue,green,red,yellow,drums,bushes,bananas,coconuts,"
    "sand,sunlight,drift wood,crab meat,whale meat,fish,fruit,papaya,flies,"
    "swimming,running,dancing,monkeys,birds,work,lifting,surprises,jokes,"
    "sleeping";

static const char PREFERENCES_62[] =
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,"
    "flowers,bees,the dark,caves,herbs,berries,snakes,wind,rocks,"
    "heights,the ocean,playing,exploring,blue,green,red,yellow,drums,"
    "bushes,bananas,coconuts,sand,sunlight,wood,crab meat,whale meat,"
    "fish,fruit,papaya,flies,swimming,running,learning,dancing,"
    "monkeys,parrots,work,lifting,surprises,jokes,sleeping,jumping,"
    "cooking,fire,eating,dragonflies,owls,dreaming,children,talking,"
    "holidays,vegetables,quiet,clouds,dirt";

/* The Secret City's own: The Tree of Life's and New Believers' list but
   "alchemy" and "potions" at 62 and 63 (its exe's list). */
static const char PREFERENCES_79_VV3[] =
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,"
    "the dark,caves,herbs,berries,snakes,wind,rocks,heights,the ocean,"
    "playing,exploring,blue,green,red,yellow,drums,bushes,bananas,coconuts,"
    "sand,sunlight,wood,crab meat,whale meat,fish,fruit,papaya,flies,"
    "swimming,running,learning,dancing,monkeys,parrots,work,lifting,"
    "surprises,jokes,sleeping,jumping,cooking,fire,eating,dragonflies,owls,"
    "dreaming,children,talking,holidays,vegetables,quiet,clouds,dirt,"
    "alchemy,potions,magic,plants,rain,fog,sitting,sharks,honey,stories,"
    "coral,thunder,lightning,pearls,stars,mango,nature";

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

/* Copy the index-th comma-separated entry of `list` into `out`.  Returns 0
   when the index is outside the list, so an empty slot and a corrupt one are
   both reported as absent rather than as a wrong word. */
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

/* The first filled entry of a preference array, or 0 when every slot is
   empty.  Empty is -1 OR an index past the end of the list; both appear in
   real villages.  The first FILLED slot is what the game's own Details panel
   shows, so it is what the log records. */
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

struct game_layout {
    int supported;
    unsigned int stride;
    int slots;
    /* Where the first record sits relative to the pointer the caller passes.

       This is a CONTAINER HEADER, not a per-record bias: VV4 and VV5 keep the
       villager array inside an object whose first 0x44 bytes are something
       else, so records do NOT carry a 0x44-byte prefix each. Naming it
       record_base rather than record_prefix is deliberate for that reason.

       The caller passes the unbiased container and this subtracts the header,
       rather than the caller passing `container + 0x44` and this being zero.
       Both work, but only one fails safely: with the header recorded here, a
       caller that mistakenly pre-applies it is rejected at slot 0 -- loudly, on
       the very first birth -- while a caller that forgets to pre-apply it in
       the other design is accepted at every slot and silently misindexed. */
    unsigned int record_base;
    unsigned int active;      /* u8, == 1 when the slot is a live villager */
    unsigned int age;         /* i32 */
    unsigned int head;        /* i32 */
    unsigned int body;        /* i32 */
    /* The field a game uses to find one villager from another, when it has
       one at all. Only read when father_kind is FATHER_BY_ID.

       Deliberately not called an "identity": VV1's nearest candidate, +0x36C,
       is NOT unique. It is rand()%50+1 at 0x43C669 with a second writer using
       %99, and it is COPIED from parent to child at 0x43C9E5 alongside gender,
       head and body -- a field that is inherited cannot identify anyone, and
       with around ninety villagers and fifty values, living villagers share it
       routinely. Every reader compares it paired with +0x368, which is
       look-alike avoidance rather than lookup. No game currently sets
       FATHER_BY_ID, so this field is unused; it exists for a game that turns
       out to keep a real one. */
    unsigned int id;
    unsigned int name;        /* char[name_capacity] */
    unsigned int name_capacity;
    int father_kind;          /* FATHER_BY_ID or FATHER_BY_NAME */
    unsigned int father;      /* an i32 id, or a char[father_key_capacity] */
    /* How many bytes of the father's stored NAME the game actually writes.
       Zero means "same as name_capacity".

       This is NOT the same number as name_capacity, and conflating them breaks
       the by-name scan on exactly the villagers it is hardest to notice. A
       villager's own name field is 25 bytes in VV3/VV4/VV5, proven by the
       burial writers' `push 0x19`. But conception copies the father's name
       onto the mother with `push 0x18` -- 24 bytes:

           VV3  0x455B4D  push 0x18 ; ... lea eax,[esi+0xE48]  ; call 0x46F780
           VV5  0x465E9E  push 0x18 ; ... lea eax,[esi+0x1C10] ; call 0x47D7C0

       So byte 25 of the stored key is never supplied by that write. Comparing
       a 25-byte read of a candidate's own name against it would mismatch for
       any father whose name is 24 characters long -- rejecting the correct
       father, or matching stale bytes.

       Reading the key at its own width is also exactly right rather than a
       compromise: the stored key is a prefix of the real name, so comparing
       that many bytes is the strongest test the data supports. It does mean
       two villagers differing only in byte 25 cannot be told apart from the
       key alone -- which the ambiguity guard already handles by resolving to
       NULL rather than guessing. */
    unsigned int father_key_capacity;
    unsigned int litter;      /* i32, babies in this pregnancy */
    /* Some games copy the father's own traits INTO the mother's record at
       conception, by value. Where they do, those copies are the better source:
       they are taken from the father himself at the moment of conception and
       survive his death, while a name scan can fail afterwards and can be
       defeated by two living villagers sharing a name.

       VV2 does this. Its conception routine sub_44B980 takes the father's
       fields as stack arguments and stores them on the mother: the caller at
       0x421FE7 pushes [father+0x54C] then [father+0x548] then a pointer to
       [father+0x564], and the callee writes [esp+0x24] to mother+0x5DC at
       0x44BA24 and [esp+0x20] to mother+0x5E0 at 0x44BA43 while sprintf'ing
       the name into mother+0x5C0. Since +0x548 is head and +0x54C is body on
       a VV2 villager, mother+0x5E0 is the father's head and mother+0x5DC is
       his body. The two other real-conception callers, at 0x464A38 and
       0x464C4D, push the same three fields in the same order; their internal
       branches select a later argument, not these.

       Zero means "this game copies nothing". That was once recorded as every
       game but VV2, and it was wrong: VV3, VV4 and VV5 copy both values too,
       in the same instruction pattern VV2 uses.

           VV3  caller 0x458319 [esi+0DF4h] BODY / 0x458320 [esi+0DF0h] HEAD
                store  0x455B4F -> +0xE64 BODY, 0x455B67 -> +0xE68 HEAD
           VV4  caller 0x460A09 / 0x460A10
                store  0x45E850 -> +0x1C2C BODY, 0x45E868 -> +0x1C30 HEAD
           VV5  caller 0x467D99 / 0x467DA0
                store  0x465EA0 -> +0x1C2C BODY, 0x465EB8 -> +0x1C30 HEAD

       The stored pair is INVERTED relative to address order in all four games
       -- body sits four bytes BEFORE head, exactly as VV2's +0x5DC/+0x5E0 do.
       The order is established from the push sequence rather than from the
       addresses: each caller pushes body then head, and x86 pushes descend, so
       head is the lower argument slot. Pairing these offsets by eye would swap
       every father's appearance in the log.

       Leaving them zero was not a harmless omission. It forced every one of
       those three games down the name-scan path, which resolves a name against
       LIVING villagers only. Measured across 52 of the owner's VV5 saves: of
       394 father-name groups, 362 carry exactly one stored head/body pair, and
       in 8 a living villager sharing a dead father's name has different values
       -- so the scan printed another villager's appearance under the father's
       name, silently. The scan's own ambiguity guard cannot see that case,
       because only one live match exists to find.

       These are write-only fields: +0x1C2C and +0x1C30 have no reader anywhere
       in VV5's image, which is what a value kept solely to be serialised looks
       like.

       His AGE is not among the copied fields in any game -- VV2's neighbouring
       mother+0x5E4 is a hardcoded 1 written at 0x44BA10, a pregnancy flag
       rather than a trait, and reading it as an age would print 1 for every
       father who ever lived. VV3/VV4/VV5 have no age copy either, so "Age at
       conception" still depends on finding his record and can still be
       unavailable when head and body are not. */
    unsigned int father_head_copy;  /* i32 on the MOTHER, 0 when absent */
    unsigned int father_body_copy;  /* i32 on the MOTHER, 0 when absent */
    /* The "no such villager" id sentinel.
       VV1 uses 0xC7: it is written to the father field at 0x42427B and tested
       there at 0x42EF39. An unset father therefore resolves to no record and
       the log says so, rather than printing 199 as if it were a real id. The
       raw id is never written to the log at all -- it exists only to find the
       father's record -- so this guards a lookup, not a printed value. */
    int no_villager;
    /* Both parents' likes and dislikes, printed on the conception record so
       two parents who share a name can be told apart -- the owner's identity
       fields.  Each is an ARRAY of i32 indices into the game's preference
       list ("in general likes and dislikes are arrays for all 5 games"); the
       game's Details panel shows the first filled entry, and so does the log.

       These are the population exporter's measured offsets and lists
       (native/population_export/population_export.c), restated here because
       this companion prints the same word for the same villager; a test reads
       both tables and fails if they ever disagree.  Zero means not established
       for a game, and then no line is printed. */
    unsigned int likes;
    unsigned int dislikes;
    unsigned int preference_slots;
    const char *preference_list;
    /* The child's skills on a birth record.  Restated from the population
       exporter for the same reason the preference offsets above are, and
       covered by the same cross-table test: the two companions must print the
       same numbers for the same villager or the logs contradict each other.

       `skills_are_float` is not decoration -- VV4 and VV5 store these as
       floats where VV1 to VV3 store i32, and reading one as the other yields
       a plausible-looking number rather than an obvious failure. */
    unsigned int skills;
    unsigned int skill_count;
    int skills_are_float;
    const char *const *skill_names;
    const wchar_t *log_name;  /* "<name> <n>.txt" beside the executable */
    /* THE CHILD'S OWN PARENTS, on the child's own record.

       APPENDED HERE ON PURPOSE. The rows below use positional
       initializers, so a member inserted higher up would shift every
       value in all five rows and each game would silently read its
       neighbour's offsets.

       VV1 stores none of this -- it passes its parents in as
       arguments -- so its seven values are 0. VV2-VV5 keep both
       parents' name, head and body on every villager for life, which
       is what lets their Birth records carry the same fields VV1's do
       without any extra mechanism.

       Verified against the running games, not taken on trust from the
       population exporter: 370 living villagers read live, no
       malformed name in any game, and no name resolving as both a
       father and a mother across 96 distinct parents. The nine
       parents with two recorded appearances each have one matching
       that villager's current live looks, which is a birth-time
       snapshot from before an Origins upgrade rather than a bad
       offset. */
    unsigned int parent_father_name;
    unsigned int parent_mother_name;
    unsigned int parent_name_capacity;
    unsigned int parent_father_head;
    unsigned int parent_father_body;
    unsigned int parent_mother_head;
    unsigned int parent_mother_body;
    /* A villager's sex, for the logs' "Sex:" lines (the owner, 2026-10-06:
       "add the sex to all villagers in the logs").  Appended for the same
       reason as the parents above.  The value the game stores for a male and
       for a female: A New Home and The Lost Children 1 / 2, the later games
       0 / 1 -- the population exporter's and the Custom Island Event's
       measured tables. */
    unsigned int sex;
    int sex_male;
    int sex_female;
};

/* MAX_SKILLS and the five skill tables, restated from the population
   exporter.  The comments are its measurements, kept verbatim: they are
   the owner's own evidence for each game's storage order, and a table
   copied without them invites a future reader to "correct" an order that
   was established the hard way.  A cross-table test fails if these ever
   disagree with the population exporter's. */
enum { MAX_SKILLS = 8 };

/* "Male", "Female", or "(unknown)" for a value the game never stores. */
static const char *sex_text(const struct game_layout *g, const unsigned char *record) {
    int value;
    if (record == NULL || g == NULL) {
        return "(unknown)";
    }
    value = *(const int *)(record + g->sex);
    return value == g->sex_male ? "Male" : value == g->sex_female ? "Female" : "(unknown)";
}

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

static const struct game_layout GAME_LAYOUTS[6] = {
    /* index 0 is unused so a game id indexes directly. */
    { 0 },

    /* VV1 -- A New Home. Every offset below is proven:
         +0x28   active      vv1_origins_icons.c VV_OCCUPIED_OFFSET
         +0x348  age         vv1_origins_icons.c VV_AGE_OFFSET
         +0x360  head        vv1_origins_icons.c VV_HEAD_OFFSET
         +0x364  body        vv1_origins_icons.c VV_CLOTHING_OFFSET
         +0x36C  appearance variant -- NOT an id, and not read by this file.
                 rand()%50+1 at 0x43C669, a second writer using %99, and
                 copied parent->child at 0x43C9E5 beside gender, head and
                 body. Every reader compares it paired with +0x368, which is
                 look-alike avoidance rather than lookup. The conception
                 routine copies the father's value into the mother's +0x394,
                 and 0xC7 is a sentinel written there at 0x42427B and tested
                 at delivery (0x42EF39) -- none of which makes it an id.
         +0x370  name        sprintf destination at 0x43C696..0x43C6A1, read
                             back as a string at 0x418753..0x418760; bounded at
                             0x1C because nothing is referenced between +0x370
                             and +0x38C, and +0x38C is the next field the
                             conception routine itself writes
         +0x394  a COPY of the father's +0x36C -- not an identity, see below

       VV1 RECORDS NOTHING THAT IDENTIFIES THE FATHER IN THE MOTHER'S RECORD,
       which is why father_kind is FATHER_BY_CAPTURE here and only here: his
       fields come from a record pointer the trampolines find in the frame of
       the routine's CALLER, not from any field of hers.

       An earlier version of this file read +0x394 as a father id, on the
       strength of `mov [esi+0x394], edx` at 0x43BC04. A later one called it a
       skill value. Both were wrong. The routine is __thiscall, ends in
       `ret 0x10`, and with E its entry esp its four arguments are at
       E+0x04..E+0x10. Tracking its own pushes (push edi at 0x43BBC0, push esi
       at 0x43BBF0):

           0x43BBD0  mov eax,[esp+0x10]   esp=E-4 -> E+0x0C  arg3, a skill selector
           0x43BBE2  mov ecx,[esp+0x14]   esp=E-4 -> E+0x10  arg4
           0x43BBE6  mov edx,[esp+0x08]   esp=E-4 -> E+0x04  arg1, the mother's index
           0x43BC00  mov edx,[esp+0x10]   esp=E-8 -> E+0x08  arg2
           0x43BC04  mov [esi+0x394],edx

       0x43BBD0 and 0x43BC00 share a displacement but not an argument. arg2 is
       what every caller loads off the father's record, +0x36C, so +0x394 is a
       copy of that value -- and +0x36C does not identify him: it is
       rand()%50+1 at 0x43C669 (and rand()%99+1 at 0x41C247), it is COPIED from
       parent to child at 0x43C9E5 alongside gender, head and body, and every
       reader compares it paired with +0x368. That is look-alike avoidance --
       with ~90 villagers and 50 possible values, living villagers share it
       routinely.

       The game DOES act on +0x394: delivery compares it with 0xC7 at 0x42EF39.
       So the patcher must never change it, and it does not: all four
       arguments reach the routine exactly as the caller pushed them. (An
       earlier design overwrote arg2 with his record pointer, believing it
       unread, and so wrote a pointer into this field.)

       His record IS in the caller's frame at every one of the six call sites,
       and that is where he now comes from. sub_43BBC0 is called from exactly
       six places and referenced indirectly from none:

           0x43DD33  0x43DD54  0x43DD7B  0x43DD94  0x447031  0x447238

       Each loads one field off his record and passes only that on, e.g.

           0x43DD20  mov edx,[esp+0x1C]      ; his record
           0x43DD24  mov eax,[edx+0x36C]     ; the only field the game wants
           0x43DD2F  push eax                ; arg2

       The trampolines identify the caller by the return address at E and read
       him from that caller's frame: [E+0x2C] for 0x43DD33/0x43DD54, EBP for
       0x43DD7B/0x43DD94, and for the two pairing scans 0x447031/0x447238
       whichever of the scan's two villagers its own `cmp [A+0x350],2` branch
       did not make the mother (A at [E+0x24], or the scan cursor at [E+0x2C]
       less 0x348). scripts/build_vv1_parentage_feature.py has the derivation.
         +0x35C  litter      2 at 0x43BC4E, 3 at 0x43BC8C; cleared per
                             pregnancy by 0x42F0C7, 0x43C722 and 0x43CABE

       Read the name as 28 bytes and force a terminator; the copier at
       0x44B23D is MSVC sprintf with count 0x7FFFFFFF, so it is unbounded and
       guarantees nothing. Anything that WRITES a VV1 name must use 0x18, the
       bound the game's own villager-to-villager copy uses. */
    {
        1, 0x3D8, 256, 0,
        0x28, 0x348, 0x360, 0x364, 0x36C,
        0x370, 0x1C,
        FATHER_BY_CAPTURE, 0, 0, 0x35C,
        0, 0,
        0xC7,
        0x398, 0x3A8, 4, PREFERENCES_47,
        0x3BC, 5, 0, SKILL_NAMES_VV1,
        L"Virtual Villagers 1 Births and Conceptions Log",
        /* the child's own parents -- VV1 stores no parents on the record; the caller supplies them */
        0, 0, 0, 0, 0, 0, 0,
        /* sex: its field, the male and female values */
        0x350, 1, 2,
    },

    /* VV2 -- The Lost Children. Conception is sub_44B980; the mother arrives as
       an INDEX in the first stack argument and is reached by
       `imul eax, 0E48Ch` at 0x44B994 feeding `lea esi,[eax+edi]` at 0x44B99B,
       which is what proves the stride and that ecx holds the array rather than
       a villager.

         +0x30    active
         +0x530   age     gates in sub_44F610 (>= 0x168, < 0x3E8)
         +0x548   head    lower of the appearance pair
         +0x54C   body    higher of the pair
         +0x564   name    sprintf destination in sub_44C600 and its siblings
         +0x5C0   father  sprintf'd from the partner's own +0x564 at 0x44BA49
         +0x544   litter  2 at 0x44BA82, 3 at 0x44BAB6

       VV2 keeps NO father id -- the father's NAME is copied into the mother's
       record, so he is found by name like VV3, VV4 and VV5.

       But the name is NOT the only trace of him. Conception also copies his
       head and body onto the mother by value: sub_44B980 takes them as stack
       arguments and stores them at mother+0x5E0 and mother+0x5DC, which is why
       father_head_copy and father_body_copy are set here and nowhere else.
       Those copies outlive him, so VV2 reports his head and body even when the
       name scan cannot find a record. His AGE is not copied and is not
       recoverable from the mother, so it alone can still read "record not
       found".

       Note the litter field is never written for a single birth: 0 means one
       baby, and the delivery routine clears it at 0x43BF85, so a singleton
       after twins correctly reads 0 rather than a stale 2. That is what makes
       the `< 1 -> 1` fallback safe rather than a guess.

       father_key_capacity is 0 -- "same as the villager's own name" -- and
       that is a checked answer rather than an omission. VV3/VV4/VV5 write the
       key with an explicit `push 0x18` into a 0x19 field, so their key is
       narrower than a name. VV2 has no such count to differ from: the copy at
       0x44BA49 passes only a destination and a source, and its callee
       0x4682BD is a vsprintf-family formatter that sets its own limit to
       0x7FFFFFFF -- unbounded. So VV2's key is bounded by the field, not by a
       count, and reading it at the same 0x18 the name uses is right. */
    {
        1, 0xE48C, 256, 0,
        0x30, 0x530, 0x548, 0x54C, 0,
        0x564, 0x18,
        FATHER_BY_NAME, 0x5C0, 0, 0x544,
        0x5E0, 0x5DC,
        0,
        0x5F0, 0x6E8, 62, PREFERENCES_62,
        0x7E4, 5, 0, SKILL_NAMES_VV2,
        L"Virtual Villagers 2 Births and Conceptions Log",
        /* the child's own parents, live-verified */
        0x57D, 0x596, 0x18, 0x5B0, 0x5B4, 0x5B8, 0x5BC,
        /* sex: its field, the male and female values */
        0x538, 1, 2,
    },

    /* VV3 -- The Secret City. Conception is sub_455AB0, and unlike VV1 and VV2
       the mother arrives as a RECORD POINTER directly in ecx -- `mov esi, ecx`
       at 0x455AB1, with no stride multiply anywhere in the routine. That is why
       a stride scan finds nothing in VV3 and why a hook ported from VV1 or VV2
       would read the wrong object.

         +0xF10   active
         +0xDC4   age     cmp [esi+0DC4h], 118h at nine sites
         +0xDF0   head    lower of the appearance pair
         +0xDF4   body    higher of the pair
         +0xDD4   name    strncpy bound 0x18 at 0x455B6D
         +0xE48   father  strncpy destination at 0x455B6D
         +0xE90   litter  1 at 0x455B7C, 3 at 0x455BBF, 2 at 0x455BDD

       VV3 WRITES the singleton default of 1 at 0x455B7C, where VV1 and VV2
       write nothing for a single birth. The `< 1 -> 1` fallback is therefore
       redundant here rather than load-bearing -- harmless, but the difference
       is why "which exit does a single birth take" has to be asked per game
       instead of assumed from one.

       record_base is 0x14 because the accessor sub_45C840 computes

           imul eax, [esp+4], 0x1F8C     the slot index times the stride
           lea  eax, [eax + ecx + 0x14]  plus the container header

       so record zero sits 0x14 bytes into the container the trampoline passes.
       Declaring it 0 while passing the unbiased container makes the span from
       that pointer to the mother 0x14 larger than a multiple of the stride, and
       the divisibility guard rejects EVERY conception -- a feature that loads,
       hooks, runs, and logs nothing. This was 0 for exactly that reason until
       an automated review caught it.

       The slot count is 150, not 256. data/builds.json declares VV3 with
       villager_slots 150 and absolute_maximum 150, and VV3 is the only game
       where the two disagreed with this table -- VV1 and VV2 really are
       256-slot games, VV4 and VV5 already said 150.

       That mattered because find_record_by_name cannot stop early: it has to
       walk the whole range to detect two active villagers sharing a name,
       which is the ambiguity guard that keeps it from attributing the wrong
       father. So the `active` byte was dereferenced for all 256 slots on every
       conception, and slots 150..255 are past the pool -- 106 slots, 856,056
       bytes at this stride. Whether that faults depends on what happens to sit
       after the pool at runtime, which is the shape of defect that survives
       every test here and crashes on a player's machine.

       The name field is 25 bytes (0x19), not 0x18. The burial writer at
       0x455032 does `push 0x19` before copying it, and
       data/mask_identity_adapters.json records length 25 for +0xDD4; main
       already ships VV3_NAME_LEN 0x19 for the same field. At 0x18 the scan
       compares truncated names, so two villagers differing only in the 25th
       character compare equal -- which does not merely truncate the log, it
       makes the ambiguity guard refuse a father who was actually
       distinguishable. Note this is the READ bound only: the adapter warns
       never to WRITE more than 0x18, and nothing here writes a name. */
    {
        1, 0x1F8C, 150, 0x14,
        0xF10, 0xDC4, 0xDF0, 0xDF4, 0,
        0xDD4, 0x19,
        FATHER_BY_NAME, 0xE48, 0x18, 0xE90,
        0xE68, 0xE64,
        0,
        0xFB4, 0xFC0, 3, PREFERENCES_79_VV3,
        0xEAC, 5, 0, SKILL_NAMES_VV3,
        L"Virtual Villagers 3 Births and Conceptions Log",
        /* the child's own parents, live-verified */
        0xDF8, 0xE11, 0x19, 0xE2C, 0xE30, 0xE34, 0xE38,
        /* sex: its field, the male and female values */
        0xDC8, 0, 1,
    },

    /* VV4 -- The Tree of Life. Verified against the stock binary:
         +0x1B8C  age     cmp ecx, 118h at 0x45EC31 and 0x45EC37
         +0x1B90  sex     cmp [ecx+1B90h], 1 at 0x460990
         +0x1B9C  name    lea edx,[esi+1B9Ch] at 0x460A1E; 14 lea sites and no
                          scalar load, which is what a buffer looks like
         +0x1BB8  head    mov ecx,[esi+1BB8h] at 0x460A10
         +0x1BBC  body    mov edx,[esi+1BBCh] at 0x460A09
         +0x1C50  litter  1 at 0x45E87D, 3 at 0x45E8C0, 2 at 0x45E8D3
         +0x1C10  father  strncpy(esi+1C10h, Source, 0x18) at 0x45E86E

       On head vs body: both offsets have load instructions behind them, and the
       assignment is not inferred -- the owner states head comes first and body
       second in all five games, so the lower offset of the appearance pair is
       head. Static analysis could only ever have narrowed this to "the pair is
       {head, body}", since +0x1BB8 is inherited as (a10+a12)/2 and +0x1BBC is
       rand(29), both clamped 0..29, and neither carries a label. Which is worth
       remembering: when a question is about how the game BEHAVES rather than
       how it is encoded, asking is cheaper and more reliable than deriving.

       There is NO father id field, only the father's name, which is why the
       hook belongs at the role-resolver call site 0x460A2E where both parents
       are live record pointers (ecx/ebp the mother, esi the father) rather than
       at the routine head where the father is only decomposed scalars.

       The `no_villager` sentinel is 0: VV4 stores no father id at all, so the
       id-resolution path is unused here and the field is inert.

       record_base is 0x44 because the accessor sub_466040 computes
       `lea eax, [eax + ecx + 0x44]` after multiplying the index by the stride
       -- the villager array lives inside a container whose first 0x44 bytes are
       something else. The caller passes that container unbiased; the container
       itself is the global 0x50E568, loaded as an immediate by all 55 callers
       of the accessor.

       The name field is 25 bytes (0x19), the same as VV3's. Its burial writer
       proves it with a count operand:

           0x45D4B2  push 0x19
           0x45D4B4  lea  eax, [edi+0x1B9C]
           0x45D4BC  call 0x4724E0            (strncpy)
           0x45D4C1  mov  byte [esi+0x19], 0  (the terminator, at index 25)

       This read 0x18 until it was noticed that safe_write_limit 24 in the
       adapter record is the WRITE bound and says nothing about the read
       length -- the two are orthogonal, and reading 24 truncates the
       comparison find_record_by_name depends on. Two villagers differing only
       in the 25th character then compare equal, so the ambiguity guard refuses
       a father who was actually distinguishable. Nothing here writes a name,
       so the 24-byte write limit is not in play. */
    {
        1, 0x2E3C, 150, 0x44,
        0x1CC4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B98,
        0x1B9C, 0x19,
        FATHER_BY_NAME, 0x1C10, 0x18, 0x1C50,
        0x1C30, 0x1C2C,
        0,
        0x1E60, 0x1E6C, 3, PREFERENCES_79,
        0x1C5C, 5, 1, SKILL_NAMES_VV4,
        L"Virtual Villagers 4 Births and Conceptions Log",
        /* the child's own parents, live-verified */
        0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00,
        /* sex: its field, the male and female values */
        0x1B90, 0, 1,
    },

    /* VV5 -- New Believers. Structurally identical to VV4 at every offset used
       here; the resolver headers are byte-identical. Verified separately:
         +0x1C50  litter  1 at 0x465ECD, 3 at 0x465F10, 2 at 0x465F23
         +0x1C10  father  strncpy at 0x465EBE
       Its resolver call site is 0x467DBE. Same head/body caveat as VV4.

       The container header is 0x48, NOT VV4's 0x44 -- accessor sub_46F950 does
       `lea eax, [eax + ecx + 0x48]`. The two games are structurally identical
       at every record offset and differ here, which is why this was verified
       rather than inherited: carrying VV4's 0x44 across would have put every
       VV5 mother pointer four bytes off a record boundary, the guard would have
       rejected every call, and VV5 would have logged nothing at all without
       any error. The container is the global 0x554148, loaded as an immediate
       at all 445 of its occurrences.

       The name field is 25 bytes, from VV5's own burial writer:

           0x464CB2  push 0x19
           0x464CB4  lea  eax, [edi+0x1B9C]
           0x464CBC  call 0x47D7C0            (strncpy)
           0x464CC1  mov  byte [esi+0x19], 0  (the terminator, at index 25)

       VV5 has a second, independent witness that is worth knowing because it
       looks like a contradiction and is not: 0x420005 copies one villager's
       name to another with `push 0x18`, from +0x1B9C to +0x1B9C. That is the
       WRITE bound, which is why the adapter records safe_write_limit 24
       alongside length 25. Reading 25 and writing at most 24 are both correct,
       and nothing here writes a name. */
    {
        1, 0x2F44, 150, 0x48,
        0x1CD4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B98,
        0x1B9C, 0x19,
        FATHER_BY_NAME, 0x1C10, 0x18, 0x1C50,
        0x1C30, 0x1C2C,
        0,
        0x1F5C, 0x1F68, 3, PREFERENCES_79,
        0x1C5C, 6, 1, SKILL_NAMES_VV5,
        L"Virtual Villagers 5 Births and Conceptions Log",
        /* the child's own parents, live-verified */
        0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00,
        /* sex: its field, the male and female values */
        0x1B90, 0, 1,
    }
};

/* A game's layout, with The Secret City's slot count as the executable states
   it: 150, or 256 with 256 Villagers (Experimental), whose villager table the
   conception and birth trampolines pass in its new place. */
static const struct game_layout *layout_of(int game_id) {
    static struct game_layout vv3;
    static int vv3_ready;
    static struct game_layout vv4;
    static int vv4_ready;
    static struct game_layout vv5;
    static int vv5_ready;
    if (game_id == GAME_VV3) {
        if (!vv3_ready) {
            unsigned int table, slots;
            vv3_villager_table((const unsigned char *)GetModuleHandleW(NULL), &table, &slots);
            vv3 = GAME_LAYOUTS[GAME_VV3];
            vv3.slots = (int)slots;
            vv3_ready = 1;
        }
        return &vv3;
    }
    if (game_id == GAME_VV4) {
        if (!vv4_ready) {
            unsigned int table, slots;
            vv4_villager_table((const unsigned char *)GetModuleHandleW(NULL), &table, &slots);
            vv4 = GAME_LAYOUTS[GAME_VV4];
            vv4.slots = (int)slots;
            vv4_ready = 1;
        }
        return &vv4;
    }
    if (game_id == GAME_VV5) {
        if (!vv5_ready) {
            unsigned int table, slots;
            vv5_villager_table((const unsigned char *)GetModuleHandleW(NULL), &table, &slots);
            vv5 = GAME_LAYOUTS[GAME_VV5];
            vv5.slots = (int)slots;
            vv5_ready = 1;
        }
        return &vv5;
    }
    return &GAME_LAYOUTS[game_id];
}

/* Names are engine-written with sprintf into a fixed 0x1C-byte field, so a
   name that exactly fills the buffer leaves no terminator. Copy into a local
   that is one byte longer and terminate it ourselves rather than trusting the
   buffer, and replace anything unprintable so one corrupt record cannot make
   the whole log unreadable. */
static void copy_name_field(
    const unsigned char *source,
    char *out,
    size_t out_size,
    unsigned int capacity
) {
    size_t index;

    if (out_size == 0) {
        return;
    }
    for (index = 0; index + 1 < out_size && index < capacity; ++index) {
        unsigned char value = source[index];
        if (value == 0) {
            break;
        }
        out[index] = (value >= 0x20 && value < 0x7F) ? (char)value : '?';
    }
    out[index] = '\0';
    if (index == 0) {
        /* An empty name is not an error worth dropping the record over: the
           rest of the row still identifies the villager by id, head and body. */
        if (out_size >= 8) {
            memcpy(out, "(unnamed)", 9 < out_size ? 9 : out_size - 1);
            out[out_size - 1 < 9 ? out_size - 1 : 9] = '\0';
        }
    }
}

static void copy_villager_name(
    const struct game_layout *g,
    const unsigned char *record,
    char *out,
    size_t out_size
) {
    copy_name_field(record + g->name, out, out_size, g->name_capacity);
}

/* How many bytes of the father's stored name a game actually writes.

   Zero in the table means "the same as the villager's own name", which is the
   right default for a game whose conception copy and burial copy use the same
   count. Where they differ -- VV3, VV4 and VV5 write the key with `push 0x18`
   while a villager's own field is 0x19 -- the key's own width is what must be
   read, or byte 25 of the comparison comes from whatever the write never
   supplied. */
static unsigned int father_key_width(const struct game_layout *g) {
    return g->father_key_capacity != 0
        ? g->father_key_capacity
        : g->name_capacity;
}

/* Resolve a villager id to its record by scanning the array.

   The id at +0x36C is not the record index -- the conception routine stores
   the FATHER by id, not by slot, so the father must be looked up. Returns NULL
   when no active record carries the id, which happens legitimately if the
   father died between conception and this call. */
static const unsigned char *find_record_by_id(
    const struct game_layout *g,
    const unsigned char *records,
    int id
) {
    int slot;

    if (records == NULL || id == g->no_villager) {
        return NULL;
    }
    for (slot = 0; slot < g->slots; ++slot) {
        const unsigned char *record =
            records + g->record_base + (size_t)slot * g->stride;
        if (*(const unsigned char *)(record + g->active) != 1 || vv_lookalike(g->stride, record)) {
            continue;
        }
        if (*(const int *)(record + g->id) == id) {
            return record;
        }
    }
    return NULL;
}

/* Build "<exe folder>\Virtual Villagers 1 Births and Conceptions Log <n>.txt".

   Beside the executable, matching where the statistics companion writes, so a
   player finds both logs in the same place. */
/* Set the first time the retired-folder migration runs in this process.
   The table it would otherwise have lived on is const and shared across
   games, and this is a per-launch concern rather than a per-game one. */
static int legacy_logs_migrated;

static int build_log_path(
    const struct game_layout *g,
    int file_number,
    wchar_t *destination
) {
    wchar_t folder[MAX_PATH];

    /* THE LOG BELONGS WITH THE SAVE, NOT WITH THE EXECUTABLE.

       This used to strip GetModuleFileNameW to the exe's own directory, so a
       village's parentage log was written beside the .exe while the village it
       describes lives in Documents\LDW\<exe basename>\.  The owner found
       exported logs sitting in install folders.

       vv_save_folder_w resolves the folder the game itself saves into, derived
       from the exe basename so a renamed install follows its own save, and it
       fails rather than falling back to a directory that is not the save.  The
       reserve covers the longest tail appended below: a backslash, the log
       name, a space, the number and the NUL. */
    /* The owner's layout: <save folder>\Virtual Villagers Fun Patcher Logs\Births and Conceptions\.
       The reserve still covers the longest tail appended below. */
    if (!vv_save_subfolder_w(folder, L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions", 64)) {
        return 0;
    }
    /* MOVE ANY LOGS AN OLDER BUILD LEFT IN THE RETIRED FOLDER.

       The folder was renamed from "VVFP Logs" when the owner asked for the
       name to be spelled out. Without this, a village with existing logs
       would have its next conception start a fresh "Log 1.txt" in the new
       folder: the printed numbering would restart at 1 and one village's
       history would be split across two directories.

       Every numbered file is moved, not just the newest, so the run stays
       unbroken -- select_log_file stops walking at the first gap, and a
       hole would make it renumber over records it could no longer see.

       MoveFileW, so nothing is duplicated and an interrupted migration
       cannot leave two copies of one file. A move that fails leaves that
       file where it is and the walk simply stops there. The retired folder
       is never created: GetFileAttributesW says whether it exists, and for
       a player who never had one there is nothing to do. */
    /* ONCE PER PROCESS, not once per record. build_log_path runs for every
       conception and every birth, and the walk no longer terminates early,
       so without this a village that still has a retired folder would pay
       4096 GetFileAttributesW calls on every single record written -- and
       the folder is never removed, so it would pay them forever. One pass
       per launch is enough: nothing creates legacy files while the game is
       running, and a file left behind by a failed move is retried on the
       next launch, which is exactly the resumability this needs. */
    if (!legacy_logs_migrated) {
        wchar_t root[MAX_LOG_PATH];
        wchar_t legacy_dir[MAX_LOG_PATH];
        wchar_t legacy_stem[64];
        /* EVERY LAYOUT THIS PATCHER HAS EVER WRITTEN.

           The folder was renamed twice -- "Tribe Parental Records" to
           "Births and Conceptions", and "VVFP Logs" spelled out at the
           owner's request -- and the file stem travelled with the folder.
           save_reset.c sweeps all four combinations for exactly this
           reason; the migration handled only the newest retired pair, so
           a player upgrading from either older layout kept their records
           in a folder nothing reads while selection started a fresh Log 1
           in the new one. Found in review.

           Index 0 is where the exporter writes now and is not a source.
           No build wrote more than one of these, so the passes never
           contend for the same file. */
        static const wchar_t *const RETIRED[3] = {
            L"VVFP Logs\\Births and Conceptions",
            L"Virtual Villagers Fun Patcher Logs\\Tribe Parental Records",
            L"VVFP Logs\\Tribe Parental Records"
        };
        /* The old stem went with the old folder name. It differs from
           log_name only in the words after the game number, so it is
           derived from that number rather than carried in a second
           per-game table that could drift out of step with the first. */
        static const int OLD_STEM[3] = { 0, 1, 1 };
        int pass;
        legacy_logs_migrated = 1;
        if (vv_save_folder_w(root, 96)) {
            for (pass = 0; pass < 3; ++pass) {
                int moved;
                const wchar_t *stem = g->log_name;
                if (OLD_STEM[pass]) {
                    /* "Virtual Villagers N Births and Conceptions Log"
                       -> "Virtual Villagers N Parentage Log".

                       FIND the digit rather than indexing a fixed offset
                       into the name. [18] is correct for every current
                       name, but it is an index into a string: rename the
                       log and it silently addresses a letter, and this
                       feature would go on quietly migrating nothing while
                       every test that reads the source still passed.

                       If there is no single digit to find, migrate
                       nothing for this pass rather than guessing at a
                       stem -- a wrong stem cannot match anything anyway,
                       and refusing keeps the failure legible. */
                    const wchar_t *scan;
                    wchar_t digit = 0;
                    for (scan = g->log_name; *scan; ++scan) {
                        if (*scan >= L'0' && *scan <= L'9') {
                            if (digit != 0) {
                                digit = 0;      /* more than one: ambiguous */
                                break;
                            }
                            digit = *scan;
                        }
                    }
                    if (digit == 0) {
                        continue;
                    }
                    _snwprintf_s(legacy_stem, 64, _TRUNCATE,
                                 L"Virtual Villagers %c Parentage Log", digit);
                    stem = legacy_stem;
                }
                _snwprintf_s(legacy_dir, MAX_LOG_PATH, _TRUNCATE,
                             L"%ls\\%ls", root, RETIRED[pass]);
                if (GetFileAttributesW(legacy_dir) == INVALID_FILE_ATTRIBUTES) {
                    continue;   /* nothing of that vintage to migrate */
                }
                /* THE WALK MUST BE RESUMABLE, so neither an absent source
                   nor a failed move ends it.

                   A move can fail transiently -- a lock, an antivirus
                   scanner, a sharing violation. Stopping there left the
                   later files behind, and because the earlier ones had
                   already moved, the NEXT attempt found file 1 absent and
                   stopped immediately, treating "already migrated" as
                   "end of run". Those files were then stranded for good,
                   and select_log_file, stopping at the gap they left in
                   the new folder, handed out a number an unmigrated file
                   was still using: one village's history split across two
                   folders with the same conception numbers in both.

                   So an absent source is skipped rather than terminal, and
                   a failed move is simply left for the next launch to
                   retry. Found in review. */
                for (moved = 1; moved <= 4096; ++moved) {   /* select_log_file's own ceiling */
                    wchar_t from[MAX_LOG_PATH];
                    wchar_t to[MAX_LOG_PATH];
                    _snwprintf_s(from, MAX_LOG_PATH, _TRUNCATE,
                                 L"%ls\\%ls %d.txt", legacy_dir, stem, moved);
                    if (GetFileAttributesW(from) == INVALID_FILE_ATTRIBUTES) {
                        continue;   /* already migrated, or never existed */
                    }
                    _snwprintf_s(to, MAX_LOG_PATH, _TRUNCATE,
                                 L"%ls\\%ls %d.txt", folder, g->log_name, moved);
                    if (GetFileAttributesW(to) != INVALID_FILE_ATTRIBUTES) {
                        continue;   /* already migrated: never overwrite */
                    }
                    if (!MoveFileW(from, to)) {
                        /* A FAILED MOVE MUST NOT BE CONSUMED AS A COMPLETE
                           MIGRATION.

                           Migration and selection happen in the same call,
                           so leaving a hole here lets select_log_file hand
                           out the missing number immediately: a brand-new
                           log is created at that number, and on the next
                           launch the destination-exists branch skips the
                           locked legacy file forever. Two files numbered
                           the same in two folders -- exactly the split this
                           migration exists to prevent.

                           Refusing the path build is safe: every caller
                           already treats it as non-fatal and simply does
                           not write this record, and the move is retried on
                           the next launch. Losing one record's log line is
                           a far smaller harm than permanently splitting the
                           village's history. Found in review. */
                        legacy_logs_migrated = 0;   /* retry next time */
                        return 0;
                    }
                }
            }
        }
    }
    return _snwprintf_s(
        destination,
        MAX_LOG_PATH,
        _TRUNCATE,
        L"%ls\\%ls %d.txt",
        folder,
        g->log_name,
        file_number
    ) >= 0;
}

/* ---- The log families -----------------------------------------------------

   This exporter keeps three append-only logs per village, in three folders:

     Births and Conceptions  "Virtual Villagers N Births and Conceptions Log <n>.txt"
     Deaths                  "Virtual Villagers N Deaths Log <n>.txt"
     Unaccounted Villagers   "Virtual Villagers N Unaccounted Villagers Log <n>.txt"

   The owner: "VV1-VV5 should keep track of all deaths (that leave a
   skeleton) along with the age, cause, epitaph and skill ... in a log, like
   how Births are logged!", disappearances in their own records beside them,
   and "for villagers who somehow can't be reconciled by the logs or
   loggers, please put their data and details in a separate log. No villager
   gets unaccounted for!". Each is an event in the village's life, like a
   conception, so each gets the same machinery -- the village header, the
   held records and the tribe check, the numbered roll every
   RECORDS_PER_FILE records, Start Over. Each family has its own numbered
   marker, which is what its files are counted by; the unnumbered records
   ride along like a Birth does (the newest file, never rolling). Neither new
   log ever had a retired folder, so neither has a migration.

   The records' text is rendered by "VVFP Cause of Death.dll", which sees
   the deaths, burials and departures; this exporter files them. */
enum { LOG_BIRTHS = 0, LOG_DEATHS = 1, LOG_UNACCOUNTED = 2, LOG_EVENTS = 3 };

/* What a held or written record is.

     CONCEPTION   births family, numbered "Conception <n>"
     BIRTH        births family, "Birth <n>" (its own running count, like
                  ARRIVED; older logs say just "Birth"), never rolls
     DEATH        deaths family, numbered "Death <n>"
     DISAPPEARED  deaths family, "Disappeared", never rolls
     EPITAPH      deaths family, "Epitaph changed", never rolls
     UNACCOUNTED  unaccounted family, numbered "Unaccounted <n>"
     ARRIVED      births family, "Arrived <n>" (its own running count), never
                  rolls -- a villager who joined without being born here
                  (native/shared/arrival_backfill.h)
     APPEARANCE   births family, "Appearance changed", never rolls -- a
                  villager's head and body changed through Origins' Change
                  Appearance (native/shared/appearance_log.h), so the Family
                  Tree Maker knows the old and the new look are one villager
     ISLAND_EVENT island events family, numbered "Island event <n>" -- what
                  an island event changed in one villager, each change "old
                  -> new", under the event's title ("VVFP Island Events.dll";
                  the owner, 2026-10-08: "all island event changes should be
                  logged"); held until the next save like APPEARANCE
     LOST_BIRTH   births family, "Lost before birth", never rolls -- the
                  babies a pregnant (nursing) mother carried when she died or
                  disappeared: they are never born and get no record of their
                  own, so this closes her open Conception (the owner,
                  2026-10-09: "Nursing mothers who die will only produce a
                  grave for the mother (nursing child just disappears)").
                  "VVFP Cause of Death.dll" renders every line after the
                  heading. */
enum {
    KIND_CONCEPTION = 0, KIND_BIRTH = 1, KIND_DEATH = 2, KIND_DISAPPEARED = 3,
    KIND_EPITAPH = 4, KIND_UNACCOUNTED = 5, KIND_ARRIVED = 6, KIND_APPEARANCE = 7,
    KIND_ISLAND_EVENT = 8, KIND_LOST_BIRTH = 9
};

#define UNACCOUNTED_FOLDER L"Virtual Villagers Fun Patcher Logs\\Unaccounted Villagers"
#define BIRTHS_FOLDER L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions"
#define EVENTS_FOLDER L"Virtual Villagers Fun Patcher Logs\\Island Events"

static const wchar_t *const EVENT_LOG_NAME[6] = {
    NULL,
    L"Virtual Villagers 1 Island Events Log",
    L"Virtual Villagers 2 Island Events Log",
    L"Virtual Villagers 3 Island Events Log",
    L"Virtual Villagers 4 Island Events Log",
    L"Virtual Villagers 5 Island Events Log",
};

static const wchar_t *const DEATH_LOG_NAME[6] = {
    NULL,
    L"Virtual Villagers 1 Deaths Log",
    L"Virtual Villagers 2 Deaths Log",
    L"Virtual Villagers 3 Deaths Log",
    L"Virtual Villagers 4 Deaths Log",
    L"Virtual Villagers 5 Deaths Log",
};

static const wchar_t *const UNACCOUNTED_LOG_NAME[6] = {
    NULL,
    L"Virtual Villagers 1 Unaccounted Villagers Log",
    L"Virtual Villagers 2 Unaccounted Villagers Log",
    L"Virtual Villagers 3 Unaccounted Villagers Log",
    L"Virtual Villagers 4 Unaccounted Villagers Log",
    L"Virtual Villagers 5 Unaccounted Villagers Log",
};

static int log_family_of(int kind) {
    if (kind == KIND_DEATH || kind == KIND_DISAPPEARED || kind == KIND_EPITAPH) {
        return LOG_DEATHS;
    }
    if (kind == KIND_ISLAND_EVENT) {
        return LOG_EVENTS;
    }
    return kind == KIND_UNACCOUNTED ? LOG_UNACCOUNTED : LOG_BIRTHS;
}

/* A record that is numbered and counted toward its file's roll. */
static int kind_is_numbered(int kind) {
    return kind == KIND_CONCEPTION || kind == KIND_DEATH || kind == KIND_UNACCOUNTED
        || kind == KIND_ISLAND_EVENT;
}

/* The marker each family's numbered records begin with, which is what its
   files are counted by. */
static const char *family_marker(int family) {
    return family == LOG_DEATHS ? "Death "
        : family == LOG_UNACCOUNTED ? "Unaccounted "
        : family == LOG_EVENTS ? "Island event " : "Conception ";
}

/* The Deaths logs' folder: "Deaths and Disappearances", or an older build's "Deaths" while only it
   exists -- its logs are written where they are, never moved (native/shared/save_layout.h).  When
   both exist, new records go to the new one, and the readers read both. */
static const wchar_t *deaths_folder(void) {
    wchar_t root[MAX_PATH];
    return vv_save_folder_w(root, 64) ? vv_layout_dir_rel_w(root, VV_DEATHS_LOGS_OLD, VV_DEATHS_LOGS_DIR)
                                      : VV_DEATHS_LOGS_DIR;
}

static const wchar_t *family_folder(int family) {
    return family == LOG_DEATHS ? deaths_folder()
        : family == LOG_UNACCOUNTED ? UNACCOUNTED_FOLDER
        : family == LOG_EVENTS ? EVENTS_FOLDER : BIRTHS_FOLDER;
}

/* The game a layout row belongs to.  layout_of hands out a copy of The
   Secret City's, The Tree of Life's and New Believers' rows (with the slot
   count the executable states: 150, or 256 with 256 Villagers
   (Experimental)), so a row is told by its log name, which the copy shares,
   never by its address in GAME_LAYOUTS. */
static int layout_game(const struct game_layout *g) {
    int game;
    for (game = GAME_VV1; game <= GAME_VV5; ++game) {
        if (g->log_name == GAME_LAYOUTS[game].log_name) {
            return game;
        }
    }
    return 0;
}

static const wchar_t *family_stem(const struct game_layout *g, int family) {
    int game;
    if (family == LOG_BIRTHS) {
        return g->log_name;
    }
    game = layout_game(g);
    if (game < GAME_VV1 || game > GAME_VV5) {
        return NULL;
    }
    return family == LOG_DEATHS ? DEATH_LOG_NAME[game]
        : family == LOG_EVENTS ? EVENT_LOG_NAME[game] : UNACCOUNTED_LOG_NAME[game];
}

/* "<save folder>\Virtual Villagers Fun Patcher Logs\Deaths and Disappearances\Virtual Villagers N Deaths Log <n>.txt"
   (and the Unaccounted Villagers twin), and for the births family exactly
   what build_log_path builds (its retired-folder migration included). */
static int build_family_log_path(
    const struct game_layout *g,
    int family,
    int file_number,
    wchar_t *destination
) {
    wchar_t folder[MAX_PATH];
    const wchar_t *stem;
    if (family == LOG_BIRTHS) {
        return build_log_path(g, file_number, destination);
    }
    stem = family_stem(g, family);
    if (stem == NULL || !vv_save_subfolder_w(folder, family_folder(family), 64)) {
        return 0;
    }
    return _snwprintf_s(destination, MAX_LOG_PATH, _TRUNCATE,
                        L"%ls\\%ls %d.txt", folder, stem, file_number) >= 0;
}

/* Does this log already have something in it?

   NOT ftell. A stream freshly opened with "a" reports position 0 however
   long the file is: the position is not resolved to the end until the
   first write. Measured with this project's own toolchain and the /MT
   runtime the shipped DLL is built with -- ftell said 0 on an 18-byte
   file, and 20 only after one write.

   Each header guard used `ftell(file) == 0` to mean "this file is new",
   so it held for EVERY record and stamped the village header through the
   middle of the log: 10 times in the owner's VV3 file, 10 in VV5, 2 in
   VV2, once before each record written after the village became known.

   CALL THIS BEFORE OPENING THE FILE. Opening with "a" creates it, so a
   measurement taken afterwards always says empty and brings the same bug
   back under a new name.

   A file that cannot be measured counts as empty, which is the same
   answer as "does not exist yet" and is the case that needs a header. */
static int log_file_has_content(const wchar_t *path) {
    WIN32_FILE_ATTRIBUTE_DATA info;
    if (!GetFileAttributesExW(path, GetFileExInfoStandard, &info)) {
        return 0;
    }
    return info.nFileSizeHigh != 0 || info.nFileSizeLow != 0;
}

/* The file's length on disk, 0 when it does not exist. Taken before an append
   so a failed append can be cut back to exactly this. */
static LONGLONG log_file_size(const wchar_t *path) {
    WIN32_FILE_ATTRIBUTE_DATA info;
    if (!GetFileAttributesExW(path, GetFileExInfoStandard, &info)) {
        return 0;
    }
    return ((LONGLONG)info.nFileSizeHigh << 32) | info.nFileSizeLow;
}

/* Undo a failed append: cut the file back to the length it had before.

   Codex (#449 review): a record that fails part-way -- the write, fflush or
   fclose failing on a nearly full disk -- may already have put bytes on disk,
   including its "Conception " marker, which select_log_file counts. The
   record is kept and retried, so without this the retry would add a second,
   misnumbered copy. A file the failed append created is cut to nothing and
   removed, so the retry writes its header again. Returns 0 if the file could
   not be restored. */
static int roll_back_append(const wchar_t *path, LONGLONG size) {
    HANDLE handle;
    LARGE_INTEGER at;
    int restored;

    if (size == 0) {
        return DeleteFileW(path) || GetLastError() == ERROR_FILE_NOT_FOUND;
    }
    handle = CreateFileW(path, GENERIC_WRITE, 0, NULL, OPEN_EXISTING,
                         FILE_ATTRIBUTE_NORMAL, NULL);
    if (handle == INVALID_HANDLE_VALUE) {
        return 0;
    }
    at.QuadPart = size;
    restored = SetFilePointerEx(handle, at, NULL, FILE_BEGIN)
        && SetEndOfFile(handle);
    CloseHandle(handle);
    return restored;
}
/* Count the records already in a file, so a roll happens at the right point
   and a restarted game continues the current file rather than overwriting it.

   Counts the row marker rather than newlines, because a record spans several
   lines and a partially written trailing row must not inflate the count. */
static int count_family_records(const wchar_t *path, int family) {
    FILE *file = _wfopen(path, L"rb");
    int count = 0;
    char line[512];
    const char *marker = family_marker(family);
    size_t marker_length = strlen(marker);

    if (file == NULL) {
        return 0;
    }
    while (fgets(line, (int)sizeof(line), file) != NULL) {
        if (strncmp(line, marker, marker_length) == 0) {
            ++count;
        }
    }
    fclose(file);
    return count;
}

/* Read the village header a log file was opened with, if it has one.

   The header is the first line, written when the file was new, and it names
   the village those records belong to. Recovering it is what lets a log be
   compared against the village currently being played, so records are never
   appended under another village's name.

   Returns 1 and fills `out` when the file starts with a header; returns 0 for
   a file with no header at all, which is a log written before this existed or
   one whose village could not be identified. */
static int read_log_header(const wchar_t *path, char *out, size_t size) {
    FILE *file;
    char line[256];
    size_t length;

    if (out == NULL || size == 0) {
        return 0;
    }
    out[0] = '\0';
    file = _wfopen(path, L"rb");
    if (file == NULL) {
        return 0;
    }
    if (fgets(line, (int)sizeof(line), file) == NULL) {
        fclose(file);
        return 0;
    }

    /* A record marker as the first line means the file has no header. */
    if (strncmp(line, "Conception ", 11) == 0 || strncmp(line, "Death ", 6) == 0
        || strncmp(line, "Unaccounted ", 12) == 0 || strncmp(line, "Disappeared", 11) == 0
        || strncmp(line, "Epitaph changed", 15) == 0 || strncmp(line, "Arrived ", 8) == 0
        || strncmp(line, "Appearance changed", 18) == 0 || vv_is_birth_heading(line)) {
        fclose(file);
        return 0;
    }
    /* Trim the line ending, which is CRLF on disk because the log is written
       in text mode. */
    length = strlen(line);
    while (length > 0 && (line[length - 1] == '\n' || line[length - 1] == '\r')) {
        line[--length] = '\0';
    }
    if (length == 0) {
        fclose(file);
        return 0;
    }
    _snprintf_s(out, size, _TRUNCATE, "%s", line);
    /* A RENAMED TRIBE KEEPS ITS LOG. The patcher's Rename Tribe tool never
       rewrites the header; it appends "Tribe renamed from <old> to <new> on
       <date>", and the header this file stands for follows every such line
       in order (see village_rename.h). Without this the first record after a
       rename would start a new file under the new name.

       Only lines that START at a line start are considered: a line longer
       than the buffer arrives in pieces, and a piece is never a note. */
    {
        int at_line_start = 1;
        while (fgets(line, (int)sizeof(line), file) != NULL) {
            int starts = at_line_start;
            length = strlen(line);
            at_line_start = length > 0 && line[length - 1] == '\n';
            if (!starts || !vv_rename_is_note(line)) {
                continue;
            }
            while (length > 0 && (line[length - 1] == '\n' || line[length - 1] == '\r')) {
                line[--length] = '\0';
            }
            (void)vv_rename_apply(out, size, line);
        }
    }
    fclose(file);
    return 1;
}

/* Whether a log file belongs to the village currently being played.

   `village` is the header for the current village, as published at the last
   save, and carries its own trailing newline. A file matches when its own
   recovered header is the same text.

   A file with NO header always matches. Those are logs written before the
   header existed, and rotating away from one would strand a player's history
   in an old file and restart their numbering for no reason -- the log is
   still theirs, it simply predates the village being recorded.

   Likewise, when the current village is unknown -- nothing has been saved yet
   in this session -- every file matches. Rotating on "I do not know" would
   start a fresh log on every launch. */
static int log_belongs_to_village(const wchar_t *path, const char *village) {
    char existing[256];
    char current[256];
    size_t length;

    if (village == NULL || village[0] == '\0') {
        return 1;
    }
    if (!read_log_header(path, existing, sizeof existing)) {
        return 1;
    }
    _snprintf_s(current, sizeof current, _TRUNCATE, "%s", village);
    length = strlen(current);
    while (length > 0
           && (current[length - 1] == '\n' || current[length - 1] == '\r')) {
        current[--length] = '\0';
    }
    return strcmp(existing, current) == 0;
}

/* The highest numbered log present, or 0 when the folder holds none.

   ASK THE DIRECTORY, DO NOT PREDICT IT. An earlier version walked until
   it had seen a fixed run of missing numbers, on the reasoning that the
   widest run of holes a reset can leave is bounded by what one village
   owned. That was wrong: a reset deletes one village's files, but gaps
   from SEVERAL reset villages coalesce, so no per-village figure bounds
   them. With a leading gap wider than the bound the selector returned no
   path at all and logging stopped; with an earlier survivor it could
   place a new file inside the gap and split numbering from history it had
   never seen. Found in review.

   One enumeration answers it exactly, which is the same fix the reset
   sweep already uses, and costs a single directory scan rather than
   thousands of probes.

   The name filter is the shape this exporter writes -- the stem, a space,
   a number, ".txt" -- so a hand-made or corrupt name cannot raise the
   ceiling and strand real logs above it. */
static int highest_log_number(const wchar_t *stem,
                              const wchar_t *folder) {
    WIN32_FIND_DATAW found;
    HANDLE search;
    wchar_t filter[MAX_LOG_PATH];
    int stem_len;
    int best = 0;
    if (stem == NULL || folder == NULL) {
        return 0;
    }
    stem_len = lstrlenW(stem);
    if (_snwprintf_s(filter, MAX_LOG_PATH, _TRUNCATE,
                     L"%ls\\%ls *.txt", folder, stem) < 0) {
        return 0;
    }
    search = FindFirstFileW(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        const wchar_t *tail;
        int number = 0;
        int digits = 0;
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            continue;
        }
        if (lstrlenW(found.cFileName) <= stem_len + 1) {
            continue;
        }
        tail = found.cFileName + stem_len + 1;
        /* CANONICAL DECIMAL ONLY. The exporter formats the number with
           %d, which never emits a leading zero, so "... Log 04096.txt" is
           not a file this code wrote. Accepting it let one hand-made name
           raise the ceiling to 4096 and reintroduce the per-call probe
           cost this enumeration exists to remove. Found in review. */
        if (*tail == L'0') {
            continue;
        }
        while (*tail >= L'0' && *tail <= L'9') {
            if (digits > 5) {
                break;          /* absurd; not one of ours */
            }
            number = number * 10 + (int)(*tail - L'0');
            ++digits;
            ++tail;
        }
        if (digits == 0 || number < 1 || number > 4096) {
            continue;
        }
        if (lstrcmpiW(tail, L".txt") != 0) {
            continue;
        }
        if (number > best) {
            best = number;
        }
    } while (FindNextFileW(search, &found));
    FindClose(search);
    return best;
}

/* The Death records an older build's "Deaths" folder holds while new records go to "Deaths and
   Disappearances" (both folders there: native/shared/save_layout.h), so a new record's number
   continues after the highest in EITHER folder rather than restarting at "Death 1" beside the
   older folder's own (the owner, 2026-10-09: "recognize old and new paths/folders/files alike").
   0 when only one folder is used.  The older folder is only read, never made or moved. */
static int older_deaths_total(const struct game_layout *g) {
    wchar_t root[MAX_PATH], folder[MAX_PATH], path[MAX_LOG_PATH];
    const wchar_t *stem = family_stem(g, LOG_DEATHS);
    int ceiling, number, total = 0;
    if (stem == NULL || !vv_save_folder_w(root, 64)
        || lstrcmpiW(deaths_folder(), VV_DEATHS_LOGS_DIR) != 0) {
        return 0;               /* writing into the older folder: its records are the ones counted */
    }
    if (_snwprintf_s(folder, MAX_PATH, _TRUNCATE, L"%ls\\%ls", root, VV_DEATHS_LOGS_OLD) < 0
        || vv_layout_probe_w(folder, NULL) != VV_LAYOUT_DIR) {
        return 0;
    }
    ceiling = highest_log_number(stem, folder);
    for (number = 1; number <= ceiling && number <= 4096; ++number) {
        if (_snwprintf_s(path, MAX_LOG_PATH, _TRUNCATE, L"%ls\\%ls %d.txt", folder, stem, number) < 0) {
            continue;
        }
        if (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) {
            total += count_family_records(path, LOG_DEATHS);
        }
    }
    return total;
}

/* Choose the file to append to: the highest-numbered existing file that is not
   yet full, else the next one. Starts at 1 so the first log reads "... 1.txt".

   A file belonging to a DIFFERENT village is treated as full, so the log rolls
   to a new file rather than appending under the previous village's header.
   Codex caught this: the owner keeps several villages per game and switches
   between them, and without the check a conception in the new village would be
   filed under the old village's name and save number. A missing header is a
   cosmetic problem; a record attributed to the wrong village is a wrong record,
   and parentage cannot be recovered afterwards to correct it.

   `existing_records` is the count across EVERY log file, not just the one
   chosen, because it becomes the record's printed number. Counting only the
   chosen file restarted numbering at 1 in each new file, so a village past 256
   births had two records called "Conception 1", two called "Conception 2", and
   nothing to order them by -- which is the one thing a numbered record exists
   to provide. The earlier files are already visited by this loop to find the
   first one that is not full, so accumulating the total costs no extra work.

   Bounded so a corrupt or unwritable directory cannot spin forever; 4096 files
   is far beyond any real playthrough.

   The same selection serves both families (Births and Conceptions, and
   Deaths): `family` picks the folder, the file stem and the record marker the
   files are counted by.  `for_birth` asks for the village's NEWEST existing
   file rather than the next one with room; ensure_parentage_log uses it in
   both families to create a log only when the village has none.
   select_log_file below is the births family's form. */
static int select_family_log_file(
    const struct game_layout *g,
    int family,
    const char *village,
    wchar_t *destination,
    int *existing_records,
    /* A BIRTH DOES NOT ROLL OVER. Births are not counted toward the roll --
       count_records matches only "Conception " -- so a file is full, by that
       count, the instant its 256th conception is written. A birth asking for
       a file at that moment would be handed the NEXT one, landing apart from
       its own conception and ahead of that file's first record. Set for a
       birth, it appends to the file already holding records, which is the one
       its conception went to. Found in review. */
    int for_birth
) {
    int number;
    int total = 0;
    /* For a birth: the newest of this village's files seen so far, and the
       running total at that point. Zero until one is found. */
    int last_match = 0;
    int last_total = 0;
    /* The highest number that exists. A new file goes after it, so the
       printed running total stays monotonic across the whole sequence. */
    int highest = 0;
    /* The highest number the folder actually holds, measured once. The
       walk runs to exactly this, so every hole is crossed and nothing
       above one is missed. */
    int ceiling;
    /* The lowest number with no file. Only used when the folder holds
       NOTHING at all, so a fresh installation still gets file 1. */
    int first_free = 0;
    wchar_t folder[MAX_PATH];

    *existing_records = 0;
    /* MIGRATE BEFORE MEASURING.

       build_log_path performs the retired-folder migration on its first
       call. Measuring the ceiling before that ran meant an upgrading
       player -- new folder empty, legacy folder full of logs -- recorded
       ceiling 0, and the walk then examined only the single file the
       migration had just moved into place. A birth went there even when
       its conception was in a later file, and a conception after a full
       or foreign file 1 took file 2 without checking its header or
       fullness. Found in review.

       One throwaway call does the migration, so the enumeration below
       sees the folder as it will actually be. */
    if (!build_family_log_path(g, family, 1, destination)) {
        return 0;
    }
    if (!vv_save_subfolder_w(folder, family_folder(family), 64)) {
        return 0;
    }
    ceiling = highest_log_number(family_stem(g, family), folder);
    for (number = 1; number <= ceiling + 1 && number <= 4096; ++number) {
        int records;
        if (!build_family_log_path(g, family, number, destination)) {
            return 0;
        }
        if (GetFileAttributesW(destination) == INVALID_FILE_ATTRIBUTES) {
            /* A HOLE IS NOT THE END OF THE WALK.

               The reset deletes only the erased village's numbered logs, so
               it leaves gaps between files other villages still own: delete
               A's 1 and 3 while B keeps 2 and 4. Since the reset started
               enumerating the folder rather than stopping at the first
               absence, it makes those holes reliably.

               Ending the walk here meant village B never saw file 4: its
               cumulative conception count restarted, and a birth took file 2
               as the newest and landed apart from its own conception. Found
               in review, as a consequence of the enumeration fix.

               So skip the hole and keep walking, as far as the ceiling
               highest_log_number measured. An earlier version instead
               stopped after a fixed run of misses, assuming the widest gap
               a reset leaves is bounded by what one village owned; gaps
               from SEVERAL reset villages coalesce, so no per-village
               figure bounds them, and a leading gap wider than the bound
               made this return no path and stop logging. Found in review.
               Enumerating once removes the guess entirely.

               A NEW file still goes after the highest that exists, never
               into a hole: see the tail of this function. */
            if (first_free == 0) {
                first_free = number;
            }
            continue;
        }
        highest = number;       /* the newest file that exists, for the tail */
        records = count_family_records(destination, family);
        total += records;
        if (!log_belongs_to_village(destination, village)) {
            /* Another village's log. Keep walking so this one is never
               appended to, and so `total` still counts it -- the record
               number is a running total across the whole game's logs, and
               skipping these would restart numbering partway through. */
            continue;
        }
        if (for_birth) {
            /* A birth NEVER rolls over and never stops early. It belongs in
               the file its own conception went to, which is this village's
               NEWEST file -- so keep walking and remember the latest match
               rather than taking the first one that has records.

               Stopping at the first non-empty file put every birth after the
               first rollover back into file 1, apart from its conception and
               growing that file without bound. Found in review, after an
               earlier attempt at this very fix introduced it. */
            last_match = number;
            last_total = total;
            continue;
        }
        if (records < RECORDS_PER_FILE) {
            /* Hand the count back rather than making the caller re-derive it.
               Counting again after opening the file for append would rescan
               the whole log on every single birth, and would do it through a
               second handle on a file this call already holds open.

               `total` already includes this file's own records, so it is the
               number of conceptions logged so far and the next one is
               total + 1. */
            *existing_records = total;
            return 1;
        }
    }

    /* The whole range was walked without finding room.

       A birth belongs in this village's newest file wherever that is, even
       when later numbers belong to other villages. */
    if (for_birth && last_match != 0) {
        if (!build_family_log_path(g, family, last_match, destination)) {
            return 0;
        }
        *existing_records = last_total;
        return 1;
    }
    /* Otherwise a new file goes AFTER everything that exists, never into a
       hole an earlier reset left.

       The printed conception number is `existing_records + 1`, a running
       total across every file in order, so dropping a new file into a hole
       below a file that already holds later records would number records out
       of order. Numbering past the highest existing file keeps the sequence
       monotonic; the cost is that a reset's holes are not reused, which is
       only a gap in file NAMES and costs nothing. */
    if (highest != 0 && highest < 4096) {
        if (!build_family_log_path(g, family, highest + 1, destination)) {
            return 0;
        }
        *existing_records = total;
        return 1;
    }
    /* NOTHING EXISTS AT ALL: a fresh installation, or the folder after
       resetting the only village. The first log is file 1, and returning
       failure here meant it could never be created -- the feature simply
       did not work for a new player. Found in review. */
    if (first_free != 0) {
        if (!build_family_log_path(g, family, first_free, destination)) {
            return 0;
        }
        *existing_records = 0;
        return 1;
    }
    return 0;
}

/* The Births and Conceptions log's file: the form every births-family caller
   and the on-disk harnesses use. */
VV_PARENTAGE_STATIC int select_log_file(
    const struct game_layout *g,
    const char *village,
    wchar_t *destination,
    int *existing_records,
    int for_birth
) {
    return select_family_log_file(g, LOG_BIRTHS, village, destination,
                                  existing_records, for_birth);
}

/* Append one conception record.

   `records`  the villager record array base (edi at the hook site).
   `mother`   the mother's record (esi at the hook site).

   The father's id and the litter size are read from the mother's own record
   rather than passed in, because the hook sits at the routine's two SUCCESS
   TAILS -- after the engine has written record+0x35C -- rather than at its
   head. At the head neither is knowable: the litter size has not been chosen,
   and the conception may still be rejected by the capacity predicate.

   Returns 1 when a record was written, 0 otherwise. The caller ignores the
   result -- a failed log must never disturb the game. */
/* Is this layout row self-consistent enough to read a record with?

   The `supported` flag alone is not enough. While every later game is left at
   { 0 } the flag is the only thing that matters, but the moment a row is filled
   in, a single mistyped constant is all that stands between a typo and a
   permanently wrong parentage record -- and a wrong record cannot be corrected
   later, because parentage is not recoverable from the child.

   The specific hazards, each checked below:

     * a zero stride reaches `span % g->stride` and divides by zero;
     * a nonpositive slot count makes the array bound meaningless, so any
       pointer at or above `records` passes the boundary test;
     * a null log_name is passed straight to _snwprintf_s;
     * a field offset at or beyond the stride reads the NEXT villager's record,
       which produces plausible, wrong, and completely undetectable output.

   Every field is checked against the stride with its own width, so a four-byte
   read at stride-2 is rejected rather than straddling the record boundary. */
/* The word the conception record prints for one parent's preference array:
   the first filled entry, or "(none)" when every slot is empty.  Printed
   rather than omitted so every record has the same shape. */
static void preference_text(
    const struct game_layout *g,
    const unsigned char *record,
    unsigned int base,
    char *out,
    size_t out_size
) {
    if (record == NULL || g->likes == 0u
        || !first_preference(record, base, g->preference_slots,
                             g->preference_list, out, out_size)) {
        memcpy(out, "(none)", 7);
    }
}

/* The child's Skills block for a birth record, as a single ready-to-print
   string, or empty when there is nothing to print.

   Rendered exactly as the population exporter renders it -- same "  Skills:"
   header, same "    %-10s %d" row -- because the two companions describe the
   same villager and a reader comparing a birth against the roster should not
   have to notice that one of them formats differently.

   The value is truncated to an integer in both, including for the float
   games: VV4 and VV5 store the same 0..100 scale as the rest, so printing
   88.000000 in two games and 88 in three would be a difference in the log
   that is not a difference in the village.

   Empty on a NULL record or an unestablished table, rather than a header with
   nothing under it. */
static void skill_text(
    const struct game_layout *g,
    const unsigned char *record,
    char *out,
    size_t out_size
) {
    unsigned int skill;
    size_t used;
    out[0] = '\0';
    if (record == NULL || g->skill_count == 0u || g->skill_names == NULL) {
        return;
    }
    if (_snprintf(out, out_size, "  Skills:\n") < 0) {
        out[0] = '\0';
        return;
    }
    out[out_size - 1] = '\0';
    used = strlen(out);
    for (skill = 0; skill < g->skill_count; ++skill) {
        const unsigned char *field = record + g->skills + skill * 4u;
        int value = g->skills_are_float
            ? (int)*(const float *)field
            : *(const int *)field;
        int n = _snprintf(out + used, out_size - used, "    %-10s %d\n",
                          g->skill_names[skill], value);
        if (n < 0) {
            /* Out of room: drop the whole block rather than emit a truncated
               row that would read as a real skill value. */
            out[0] = '\0';
            return;
        }
        used += (size_t)n;
        out[out_size - 1] = '\0';
    }
}

static int layout_is_usable(const struct game_layout *g) {
    static const unsigned int WORD = 4;
    unsigned int stride;

    if (g == NULL || !g->supported) {
        return 0;
    }
    if (g->stride == 0 || g->slots <= 0 || g->log_name == NULL) {
        return 0;
    }
    /* The first record does not always sit at the array base. VV4's accessor
       sub_466040 computes `lea eax, [eax + ecx + 0x44]` after multiplying the
       index by the stride, so record zero is 0x44 bytes in. Without that bias
       the boundary check below would reject every VV4 and VV5 pointer -- the
       span would never be an exact multiple of the stride -- and the feature
       would silently log nothing at all. */
    if (g->record_base >= g->stride) {
        return 0;
    }
    if (g->name_capacity == 0 || g->name_capacity + 1 > MAX_NAME_BYTES) {
        return 0;
    }
    stride = g->stride;

    /* One-byte field. */
    if (g->active >= stride) {
        return 0;
    }
    /* Four-byte fields: the LAST byte read must still be inside the record. */
    if (g->age + WORD > stride) return 0;
    if (g->head + WORD > stride) return 0;
    if (g->body + WORD > stride) return 0;
    /* The preference arrays: every slot read must sit inside the record, and
       a row that names one of the pair must name all of it. */
    if (g->likes != 0u || g->dislikes != 0u) {
        if (g->likes == 0u || g->dislikes == 0u || g->preference_slots == 0u
            || g->preference_list == NULL) {
            return 0;
        }
        if (g->likes + g->preference_slots * WORD > stride) return 0;
        if (g->dislikes + g->preference_slots * WORD > stride) return 0;
    }
    /* The child's skills on a birth record. A row that names the array must
       name all of it, and every element read must sit inside the record --
       both i32 and float are four bytes wide, so one bound covers each. A
       zero offset means the game's table is not established, and then no
       Skills block is printed rather than a guessed offset's contents. */
    if (g->skills != 0u || g->skill_count != 0u) {
        if (g->skills == 0u || g->skill_count == 0u
            || g->skill_names == NULL) {
            return 0;
        }
        if (g->skill_count > MAX_SKILLS) return 0;
        if (g->skills + g->skill_count * WORD > stride) return 0;
    }
    /* The villager-id field is only read when a game records the father BY ID
       and his record has to be found by scanning for it. VV2, VV3, VV4 and VV5
       record the father's name instead and have no proven id field at all, so
       requiring one there would mean inventing an offset -- exactly what the
       unsupported-by-default design exists to prevent. */
    if (g->father_kind == FATHER_BY_ID && g->id + WORD > stride) {
        return 0;
    }
    /* The father's copied traits are read from the MOTHER's record, so they are
       bounded by the same stride as every other field here. Zero means the game
       copies nothing and nothing is read, which is why the guard is conditional
       rather than unconditional -- an unconditional `0 + WORD > stride` would
       pass anyway, but stating the condition keeps the "0 means absent" rule in
       one shape everywhere it appears. */
    if (g->father_head_copy != 0 && g->father_head_copy + WORD > stride) {
        return 0;
    }
    if (g->father_body_copy != 0 && g->father_body_copy + WORD > stride) {
        return 0;
    }
    if (g->father_kind == FATHER_NOT_RECORDED
            || g->father_kind == FATHER_BY_CAPTURE) {
        /* Nothing to validate: neither kind reads a father field out of the
           mother's record, so `father` is unused and its offset means nothing.
           FATHER_BY_CAPTURE reads his own record instead, and that pointer is
           validated at use against the record array -- stride alignment, slot
           range, active flag, and not-the-mother -- which is a stronger check
           than any offset arithmetic here could be. */
        (void)0;
    } else if (g->father_kind == FATHER_BY_ID) {
        if (g->father + WORD > stride) return 0;
    } else if (g->father_kind == FATHER_BY_NAME) {
        /* The stored key is read at its OWN width, which is not always the
           villager's own name width -- see father_key_capacity. It must fit
           whole either way. */
        if (g->father + father_key_width(g) > stride) return 0;
    } else {
        return 0;
    }
    if (g->litter + WORD > stride) return 0;
    /* The whole name buffer must fit. */
    if (g->name + g->name_capacity > stride) {
        return 0;
    }
    return 1;
}

/* Resolve a villager to his record by NAME, for the games that store a father's
   name rather than an id.

   VV2 through VV5 copy the father's name into the mother's record and keep no
   id at all -- in VV2 it arrives at the conception site as a formatted string
   argument, not a record pointer, so there is nothing to capture at the hook.
   Without a lookup his age, head and body would be printed as zeros while the
   feature advertises them, which is worse than useless: a reader cannot tell a
   genuine zero from a missing one.

   The name is not guaranteed unique -- two living villagers may share one --
   so an ambiguous match resolves to NULL rather than to a guess. Reporting no
   values is honest; reporting the wrong father's values is not, and a
   parentage record is permanent with no second source to correct it from.

   Returns NULL when the name matches no active record, which happens
   legitimately if the father died between conception and this call. */
static const unsigned char *find_record_by_name(
    const struct game_layout *g,
    const unsigned char *records,
    const char *name
) {
    const unsigned char *found = NULL;
    int slot;

    if (records == NULL || name == NULL || name[0] == '\0') {
        return NULL;
    }
    for (slot = 0; slot < g->slots; ++slot) {
        const unsigned char *record =
            records + g->record_base + (size_t)slot * g->stride;
        char candidate[MAX_NAME_BYTES];

        if (*(const unsigned char *)(record + g->active) != 1 || vv_lookalike(g->stride, record)) {
            continue;
        }
        /* The candidate is read at the KEY's width, not its own, because that
           is what the stored key can possibly contain. Where a game writes the
           key with fewer bytes than a villager's name field holds -- VV3, VV4
           and VV5 write 0x18 into a 0x19 field -- reading the candidate at
           0x19 and the key at 0x18 makes every 24-character name mismatch.

           Comparing at the key's width is the strongest test the data
           supports rather than a concession: the key IS a prefix of the real
           name. Two villagers differing only past that width are then
           indistinguishable from the key alone, which is precisely the case
           the ambiguity guard below resolves to NULL instead of guessing. */
        copy_name_field(record + g->name, candidate, sizeof(candidate),
                        father_key_width(g));
        if (strcmp(candidate, name) != 0) {
            continue;
        }
        if (found != NULL) {
            /* Two active villagers share this name; neither can be shown to be
               the father, so record none of his values rather than one of
               theirs. */
            return NULL;
        }
        found = record;
    }
    return found;
}

/* Is this pointer one of the array's own record slots?

   The caller hands a record pointer straight from a register, so it is checked
   rather than trusted: it must sit inside the array, land exactly on a record
   boundary once the base bias is removed, and be within the slot count. The
   same test serves the mother and the father, which is the point of factoring
   it out -- a second copy that drifted would be a silent wrong-record read,
   and parentage cannot be recovered from the child afterwards. */
static int is_record_slot(
    const struct game_layout *g,
    const unsigned char *records,
    const unsigned char *record
) {
    size_t span;

    if (records == NULL || record == NULL || record < records) {
        return 0;
    }
    span = (size_t)(record - records);
    if (span < g->record_base) {
        return 0;
    }
    span -= g->record_base;
    if (span % g->stride != 0) {
        return 0;
    }
    if (span / g->stride >= (size_t)g->slots) {
        return 0;
    }
    return 1;
}

/* ---- Records written before the village's first save ---------------------

   The village header is published by the statistics companion, which sits on
   the game's save call -- the only place the village name and slot both exist.
   Until a village has been saved once in this process, nothing is published.

   Two defects came out of writing records in that window, both seen in the
   owner's first v1.35.27 tribes:

   1. A record written then created the log WITHOUT a header, and the header is
      only ever written into an empty file, so that log never got one. VV1's
      and VV3's logs both opened on "Conception 1". A headerless log is also
      attributed to every village by log_belongs_to_village, so a later village
      or Start Over could append to it or sweep it.

   2. VV3 logged seven conceptions between fourteen villagers who are in
      neither of that tribe's saves. Only the two hooked callers reach VV3's
      conception routine, so those villagers were real records in the game's
      table when it ran, and gone by the first save. The game simulates
      villagers before the player's tribe exists (VV5's own ldwLog names two
      who never joined the tribe), and those are what was logged.

   Both are the same window, so one mechanism closes both. While no village is
   known, a finished record is HELD here instead of being written. At the next
   point the village is known -- the first save (EnsureParentageLog, called by
   the population exporter after every save) or the next record written after
   it -- the held records are written in order, under the header, numbered as
   if they had been written live.

   EVERY HELD RECORD IS KEPT. The owner: "no one should be dropped. nothing
   should be dropped." Held records are written, in order, at the next save,
   under that save's village -- including a record written while the game's
   pre-tribe simulation was loaded, or from a tribe that was never saved
   before Start Over; those land in the next saved village's log.

   Earlier versions dropped a held record whose villager or tribe no longer
   matched at the save. Every such test proved wrong in play, because no
   villager field is fixed for life:

     names            the player can rename a villager
     age              goes DOWN through island events, the Gong of Wonder and
                      Origins upgrades
     head, body       change through Origins' Change Appearance
     likes, dislikes  change as a villager grows
     skills           grow; and villagers die, freeing their slots

   (All of that is ordinary game behaviour, per the owner, and one villager
   can have their name, head and body all changed.) v1.35.28 compared one
   villager's fields and so DROPPED A REAL BIRTH: in the owner's VV3 tribe a
   Time Warp with no save delivered Epeli, who took up a like before the save.

   The records are held only while no save can vouch for the loaded tribe, and
   the queue grows as needed rather than refusing a record past a limit.

   A HELD RECORD FROM OTHER VILLAGERS IS LABELLED, NOT DROPPED. The owner asked
   for records the tribe cannot vouch for to be told apart. When a record is
   held, the villager table is snapshotted; at the save, if hardly anyone in
   that snapshot is still in their slot (the loose rule below: not even a
   quarter keep any one of name, looks or parents), the record is written with
   a closing "Note:" line. That is the game's pre-tribe simulation, or a tribe
   left unsaved by Start Over. The loose rule is deliberate: renaming and
   restyling every founder must not label the tribe's own records, and the
   price -- a rare simulated record matching by chance and going unlabelled --
   costs nothing but the label.
   A record still held when the process exits was never followed by a save;
   writing it from DllMain at exit could hang the game's shutdown, so it is
   not attempted.

   WITHOUT A PUBLISHER, NOTHING IS HELD. A player who unticks Village
   Statistics has no publisher at all, and holding would lose every record.
   The patcher deletes a feature's companion DLLs when the feature is removed,
   so the statistics DLL's presence next to the executable is the test. With
   it absent, records are written immediately and unlabelled, as before.

   CAUSE OF DEATH NAMES THE VILLAGE TOO. Codex (#504 review): with Cause of
   Death and this log ticked but Village Statistics not, nothing published
   the village, so the Deaths and Unaccounted Villagers records -- which
   that patch promises are headed with the village and created at its first
   save -- were written unlabelled into files every village then shared, and
   Start Over could not tell which to delete. "VVFP Cause of Death.dll"
   already sits on the game's save call (it reconciles the roster there), so
   at every save it hands this DLL the save buffer and slot
   (PublishVillageAtSave below), which publishes the same header the
   statistics companion would and creates the logs. Its presence beside the
   executable therefore counts as a publisher as well -- unless it is loaded
   and reports that its hooks were refused, in which case it will never name
   a village and records are written at once, as with no publisher. */

/* One rendered record: 13 short lines plus a skills block of at most 512. */
#define RECORD_TEXT_MAX 2048

struct pending_record {
    int game_id;
    int kind;
    int tribe;          /* index into held_tribes; -1 = not snapshotted */
    char *text;
};

static struct pending_record *pending;
static int pending_count;
static int pending_capacity;
static int publisher_state;         /* 0 unknown, 1 present, -1 absent */

static int deaths_recorder_present(void);

static int statistics_publisher_present(void) {
    if (publisher_state != 0) {
        return publisher_state == 1;
    }
    publisher_state = vvfp_patcher_file_exists("VVFP Statistics Export.dll") ? 1 : -1;
    return publisher_state == 1;
}

/* Whether "VVFP Cause of Death.dll" will name the village at each save (see
   above). It says itself: 1 installed, 0 not installed yet, -1 refused. A
   refusal is final. "VVFP Startup.dll" installs it at game start, before
   any village loads; 0 is seen only when that did not happen (the startup
   loader's file is missing), and the Origins companion then installs it
   once a village is shown, after the load-time catch-up, so records wait
   for it.

   Asked before the companion has loaded it, this DLL loads it -- by full
   path from the executable's folder, as the companion does, never from
   DllMain -- rather than assume it will load. Codex (#512 review): a
   shipped file that cannot load, or that lacks the exports, will never name
   a village, and treating it as a publisher held every record until exit,
   where it was lost. Either is final, like a refusal. Loading it early runs
   nothing but its DllMain; the companion's own load later shares the
   module. */
typedef int (__stdcall *cause_names_village_t)(void);
typedef int (__stdcall *cause_arm_save_t)(int game);

static int cause_state;               /* 0 undecided, -1 never */

static int cause_of_death_publishes(int game_id) {
    static cause_names_village_t names;
    static cause_arm_save_t arm_save;
    int state;
    HMODULE module;

    if (cause_state != 0) {
        return 0;
    }
    if (!deaths_recorder_present()) {
        cause_state = -1;
        return 0;
    }
    if (names == NULL) {
        module = vvfp_patcher_dll("VVFP Cause of Death.dll");
        if (module == NULL
            || GetProcAddress(module, "VvfpCauseInstall") == NULL) {
            cause_state = -1;
            return 0;
        }
        names = (cause_names_village_t)GetProcAddress(module, "VvfpCauseNamesVillage");
        arm_save = (cause_arm_save_t)GetProcAddress(module, "VvfpCauseArmSave");
        if (names == NULL || arm_save == NULL) {
            cause_state = -1;
            return 0;
        }
    }
    state = names();
    if (state == -1) {
        cause_state = -1;
        return 0;
    }
    /* Not installed yet (no install at game start): a save may come before
       the install (The Secret City's Origins companion installs it only
       when a villager is first drawn), so its save
       hook is armed now, to name the village at that save (#512 review).
       A hook that cannot be armed can never name it: records go out now. */
    if (state == 0 && game_id >= GAME_VV1 && game_id <= GAME_VV5 && !arm_save(game_id)) {
        cause_state = -1;
        return 0;
    }
    return 1;
}

/* Whether anything will publish the village: the statistics companion, or
   Cause of Death's own save hook. */
static int village_publisher_present(int game_id) {
    return statistics_publisher_present() || cause_of_death_publishes(game_id);
}

/* Whether `size` bytes at `p` can be read without faulting. A held record's
   villager may belong to a table the game has since freed, so it is checked
   before it is re-read rather than trusted. */
static int memory_is_readable(const void *p, size_t size) {
    MEMORY_BASIC_INFORMATION info;
    const unsigned char *at = (const unsigned char *)p;
    const unsigned char *end = at + size;
    const DWORD readable = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY
        | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;

    if (p == NULL || end < at) {
        return 0;
    }
    while (at < end) {
        if (VirtualQuery(at, &info, sizeof info) == 0
            || info.State != MEM_COMMIT
            || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS)) != 0
            || (info.Protect & readable) == 0) {
            return 0;
        }
        at = (const unsigned char *)info.BaseAddress + info.RegionSize;
    }
    return 1;
}

/* ---- The tribe as a whole -------------------------------------------------- */

/* Where each game keeps its villager table, from the executable's base: the
   same addresses the population exporter reads (VV1 and VV2 hold a pointer to
   a lazily built table, VV3-VV5 the table itself). */
static const struct { unsigned int rva; int is_pointer; } VILLAGER_TABLE[6] = {
    { 0, 0 }, { 0x8B614u, 1 }, { 0x99F24u, 1 }, { 0x19E110u, 0 },
    { 0x10E568u, 0 }, { 0x154148u, 0 },
};

/* VV3's, VV4's and VV5's table RVA as the executable names it (see
   vv3_villager_table.h, vv4_villager_table.h and vv5_villager_table.h). */
static unsigned int villager_table_rva(int game_id) {
    unsigned int table = VILLAGER_TABLE[game_id].rva, slots;
    if (game_id == GAME_VV3) {
        vv3_villager_table((const unsigned char *)GetModuleHandleW(NULL), &table, &slots);
    } else if (game_id == GAME_VV4) {
        vv4_villager_table((const unsigned char *)GetModuleHandleW(NULL), &table, &slots);
    } else if (game_id == GAME_VV5) {
        vv5_villager_table((const unsigned char *)GetModuleHandleW(NULL), &table, &slots);
    }
    return table;
}

#define TRIBE_SLOTS 256
#define TRIBES_HELD 8

struct tribe_member {
    int slot;
    char name[MAX_NAME_BYTES];
    int head;
    int body;
    char father_of[MAX_NAME_BYTES];   /* the villager's own parents; empty in VV1 */
    char mother_of[MAX_NAME_BYTES];
    /* A fingerprint of the likes and dislikes arrays, and whether there is
       anything in them. The player cannot edit preferences, so for a founder
       -- no parents on record -- renamed AND restyled before the first save,
       they are what is left to recognise. They do change as villagers grow,
       so they count only toward the label (TRIBE_LOOSE). Codex, #452. */
    unsigned int preferences;
    int has_preferences;
};

struct tribe {
    int game;
    int count;
    struct tribe_member member[TRIBE_SLOTS];
};

static struct tribe *held_tribes;       /* the tables held records were written from */
static int held_tribe_count;
static struct tribe *saved_tribe;       /* the tribe at the last save */
static int saved_valid;
static struct tribe *scratch_tribe;
static const unsigned char *last_table[6];

static const unsigned char *villager_table(int game_id) {
    const unsigned char *module;
    const unsigned char *table;

    if (last_table[game_id] != NULL) {
        return last_table[game_id];
    }
    module = (const unsigned char *)GetModuleHandleW(NULL);
    if (module == NULL || VILLAGER_TABLE[game_id].rva == 0u) {
        return NULL;
    }
    table = module + villager_table_rva(game_id);
    if (VILLAGER_TABLE[game_id].is_pointer) {
        if (!memory_is_readable(table, sizeof(void *))) {
            return NULL;
        }
        table = *(const unsigned char *const *)table;
    }
    return table;
}

/* Snapshot the tribe in `records` (or where the game keeps it). */
static int take_tribe(int game_id, const unsigned char *records, struct tribe *out) {
    const struct game_layout *g = layout_of(game_id);
    unsigned int slot;

    out->game = game_id;
    out->count = 0;
    if (records == NULL) {
        records = villager_table(game_id);
    }
    if (records == NULL
        || !memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride)) {
        return 0;
    }
    last_table[game_id] = records;
    for (slot = 0; slot < g->slots && slot < TRIBE_SLOTS; ++slot) {
        const unsigned char *record = records + g->record_base + slot * g->stride;
        struct tribe_member *m;
        if (*(const unsigned char *)(record + g->active) != 1 || vv_lookalike(g->stride, record)) {
            continue;
        }
        m = &out->member[out->count++];
        m->slot = (int)slot;
        copy_villager_name(g, record, m->name, sizeof(m->name));
        m->head = *(const int *)(record + g->head);
        m->body = *(const int *)(record + g->body);
        m->father_of[0] = '\0';
        m->mother_of[0] = '\0';
        m->preferences = 2166136261u;
        m->has_preferences = 0;
        if (g->likes != 0u && g->dislikes != 0u && g->preference_slots != 0u) {
            unsigned int k;
            for (k = 0; k < 2u * g->preference_slots; ++k) {
                unsigned int base = k < g->preference_slots ? g->likes : g->dislikes;
                int value = *(const int *)(record + base
                                           + (k % g->preference_slots) * 4u);
                if (value < 0) {
                    value = -1;           /* every empty slot alike */
                } else {
                    m->has_preferences = 1;
                }
                m->preferences = (m->preferences ^ (unsigned int)value) * 16777619u;
            }
        }
        /* An empty parent field stays EMPTY here. copy_name_field renders
           it as its "(unnamed)" placeholder, which made every founder "share
           parents" with every other founder and with the pre-tribe
           simulation's villagers. */
        if (g->parent_father_name != 0u && record[g->parent_father_name] != 0) {
            copy_name_field(record + g->parent_father_name, m->father_of,
                            sizeof(m->father_of), g->parent_name_capacity);
        }
        if (g->parent_mother_name != 0u && record[g->parent_mother_name] != 0) {
            copy_name_field(record + g->parent_mother_name, m->mother_of,
                            sizeof(m->mother_of), g->parent_name_capacity);
        }
    }
    return 1;
}

/* How many of name, looks and own parents -- and, for LOOSE only, likes and
   dislikes -- must still match for a villager to count. STRICT decides whether a record may go straight under the last
   saved header (a wrong yes would misfile it). LOOSE decides only the label
   (a wrong no would label the tribe's own record). */
#define TRIBE_STRICT 2
#define TRIBE_LOOSE  1

/* A villager still counts when at least `needed` of name, looks and own
   parents are unchanged (TRIBE_STRICT or TRIBE_LOOSE, below). Parents count
   only for a villager who has them on record: founders, and everyone in VV1,
   have none. */
static int still_counts(const struct tribe_member *then, const struct tribe_member *now,
                        int needed) {
    int same = 0;
    if (strcmp(then->name, now->name) == 0) {
        ++same;
    }
    if (then->head == now->head && then->body == now->body) {
        ++same;
    }
    if ((then->father_of[0] != '\0' || then->mother_of[0] != '\0')
        && strcmp(then->father_of, now->father_of) == 0
        && strcmp(then->mother_of, now->mother_of) == 0) {
        ++same;
    }
    if (needed <= TRIBE_LOOSE && then->has_preferences && now->has_preferences
        && then->preferences == now->preferences) {
        ++same;
    }
    return same >= needed;
}

/* Whether `now` is still the tribe `then` was: at least a quarter of then's
   villagers, and at least one, still count in the same slots -- or in the
   slot a reload puts them in.  Every game saves its occupied records packed
   and loads them into records 0, 1, 2, ..., so after a death and a reload
   within the session each villager behind it is at its RANK among then's
   members (they are taken in record order), not its old record; compared by
   record alone the tribe looked replaced, and its records were held to the
   next save.

   Each villager on screen counts for ONE recorded member at most (Codex,
   #516): a record can be one member's old slot and another member's rank,
   and two lookalikes recorded at both would let one villager count twice --
   enough, in a tribe of eight, for a replaced tribe to pass as the saved
   one and have its records filed under the old village's header. */
static int same_tribe(const struct tribe *then, const struct tribe *now, int needed) {
    static int at[TRIBE_SLOTS];
    static unsigned char used[TRIBE_SLOTS];
    int i;
    int counted = 0;

    if (then->game != now->game || then->count == 0) {
        return 0;
    }
    for (i = 0; i < TRIBE_SLOTS; ++i) {
        at[i] = -1;
        used[i] = 0;
    }
    for (i = 0; i < now->count; ++i) {
        at[now->member[i].slot] = i;
    }
    for (i = 0; i < then->count; ++i) {
        int here = at[then->member[i].slot];
        int reloaded = at[i];
        /* A record taken at its slot cannot have been taken before: only a
           member of lower rank could have, and its rank is its index -- so
           only the rank match needs the check. */
        if (here >= 0 && still_counts(&then->member[i], &now->member[here], needed)) {
            used[here] = 1;
            ++counted;
        } else if (reloaded >= 0 && !used[reloaded]
                   && still_counts(&then->member[i], &now->member[reloaded], needed)) {
            used[reloaded] = 1;
            ++counted;
        }
    }
    return counted >= 1 && counted * 4 >= then->count;
}

static int tribes_ready(void) {
    if (saved_tribe == NULL) {
        held_tribes = (struct tribe *)calloc(TRIBES_HELD, sizeof(*held_tribes));
        saved_tribe = (struct tribe *)calloc(1, sizeof(*saved_tribe));
        scratch_tribe = (struct tribe *)calloc(1, sizeof(*scratch_tribe));
    }
    return held_tribes != NULL && saved_tribe != NULL && scratch_tribe != NULL;
}

/* The table a record held now was written from: the last snapshot if the
   table still holds it, else a new one. -1 when it cannot be read or eight
   tables are already held; such a record is simply written unlabelled. */
static int current_tribe_index(int game_id, const unsigned char *records) {
    if (!tribes_ready() || !take_tribe(game_id, records, scratch_tribe)) {
        return -1;
    }
    if (held_tribe_count > 0
        && same_tribe(&held_tribes[held_tribe_count - 1], scratch_tribe, TRIBE_STRICT)) {
        return held_tribe_count - 1;
    }
    if (held_tribe_count >= TRIBES_HELD) {
        return -1;
    }
    memcpy(&held_tribes[held_tribe_count], scratch_tribe, sizeof(*scratch_tribe));
    return held_tribe_count++;
}

/* ---- Which tribe is loaded ------------------------------------------------

   Codex (#449 review, P1): the published village header outlives the tribe it
   names. After Start Over, or after leaving a tribe for the menu and starting
   or loading another, vv_village_recall still returns the LAST SAVED tribe's
   header until the new one is saved. So a record is written straight under the
   recalled header only while the table is still the tribe of the last save --
   same_tribe above, against a snapshot taken at every save from the table the
   population exporter hands over (EnsureParentageLogForVillage). Otherwise it
   is held, and written at the next save.

   This decides only WHEN and WHERE a record is written, never WHETHER. A
   wrong "not the same tribe" -- say every founder renamed and restyled --
   only holds the record until the next save, which files it under the right
   village. A wrong "the same" would file it in the old tribe's log, so the
   stricter two-of-three rule is the safe direction here. */

static void remember_saved_tribe(int game_id, const unsigned char *records) {
    saved_valid = tribes_ready() && take_tribe(game_id, records, saved_tribe)
        && saved_tribe->count > 0;
}

static int saved_tribe_still_loaded(int game_id) {
    if (!saved_valid || saved_tribe->game != game_id) {
        return 0;
    }
    if (!take_tribe(game_id, NULL, scratch_tribe)) {
        return 0;
    }
    return same_tribe(saved_tribe, scratch_tribe, TRIBE_STRICT);
}

/* The Arrived records (`births` 0) or Birth records (`births` 1) already in
   the game's Births and Conceptions files -- every file, every village, as a
   Conception's number counts them -- so the next one's "Arrived <n>" or
   "Birth <n>" continues the running count.  A Birth is counted whether an
   older build wrote it as plain "Birth" or this one numbered it
   (birth_heading.h), so the first numbered Birth after an older log's 79
   follows them as "Birth 80".

   A BIRTH NUMBER IS NEVER REPEATED (the owner, 2026-10-09).  For Births the
   result is the larger of the count and the HIGHEST number already written:
   a log with gaps, numbers out of order (a record Repair inserted earlier in
   the file with the next unused number), or a hand-edited number goes on
   above every number in it, so the next is always unused.  -1 when a file
   cannot be read. */
static int count_running_records(const struct game_layout *g, int births) {
    wchar_t folder[MAX_PATH];
    wchar_t path[MAX_LOG_PATH];
    char line[512];
    int ceiling;
    int number;
    int total = 0;
    long highest = 0;
    if (!vv_save_subfolder_w(folder, family_folder(LOG_BIRTHS), 64)) {
        return -1;
    }
    ceiling = highest_log_number(family_stem(g, LOG_BIRTHS), folder);
    for (number = 1; number <= ceiling; ++number) {
        FILE *file;
        if (!build_family_log_path(g, LOG_BIRTHS, number, path)) {
            return -1;
        }
        if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) {
            continue;
        }
        file = _wfopen(path, L"rb");
        if (file == NULL) {
            return -1;
        }
        while (fgets(line, (int)sizeof line, file) != NULL) {
            if (births ? vv_is_birth_heading(line)
                       : strncmp(line, "Arrived ", 8) == 0 && line[8] >= '0' && line[8] <= '9') {
                ++total;
                if (births && line[5] == ' ') {
                    long n = strtol(line + 6, NULL, 10);
                    if (n > highest) {
                        highest = n < 0x7FFFFFFEL ? n : 0x7FFFFFFEL;
                    }
                }
            }
        }
        if (ferror(file)) {
            fclose(file);
            return -1;
        }
        fclose(file);
    }
    return highest > total ? (int)highest : total;
}

/* What append_record reports. A record that fails with its file restored is
   safe to retry; one whose file could not be restored is not. */
#define APPEND_WRITTEN        1
#define APPEND_RETRY          0
#define APPEND_UNRECOVERABLE (-1)

/* Append one rendered record to this village's log, heading a new file.
   `text` is everything after the "Conception <n>" line for a conception, and
   the whole block for a birth. `village` may be empty only when there is no
   publisher, in which case the log is unlabelled, as it always was then. */
static int append_record(
    const struct game_layout *g,
    const char *village,
    int kind,
    const char *text
) {
    wchar_t path[MAX_LOG_PATH];
    int existing_records;
    int arrived_before = 0;
    int had_content;
    int written;
    LONGLONG original_size;
    FILE *file;

    if (!select_family_log_file(g, log_family_of(kind), village, path,
                                &existing_records, !kind_is_numbered(kind))) {
        return 0;
    }
    if (kind == KIND_DEATH) {
        /* With an older build's "Deaths" beside "Deaths and Disappearances", the number follows
           the highest in EITHER folder (Death 1-5 in the old and 1-3 in the new: Death 6); the
           record is still written where select_family_log_file chose. */
        int older = older_deaths_total(g);
        if (older > existing_records) {
            existing_records = older;
        }
    }
    if (kind == KIND_ARRIVED || (kind == KIND_BIRTH && strncmp(text, "Birth\n", 6) == 0)) {
        /* Its number: the Arrived (or Birth) records already written, in
           every file. A file that cannot be read leaves the record held for
           a retry -- numbered wrong would be worse than numbered later. */
        arrived_before = count_running_records(g, kind == KIND_BIRTH);
        if (arrived_before < 0) {
            return APPEND_RETRY;
        }
    }
    /* Text mode, so each \n becomes the CRLF Notepad needs; see the note in
       WriteParentageRecordWithFather. Content measured BEFORE the open, which
       would create the file -- see log_file_has_content. */
    had_content = log_file_has_content(path);
    original_size = log_file_size(path);
    vv_log_words_appending((int)(g - GAME_LAYOUTS), path);
    file = _wfopen(path, L"a");
    if (file == NULL) {
        return 0;
    }
    written = 1;
    if (!had_content && village[0] != '\0') {
        if (fprintf(file, "%s", village) < 0) {
            written = 0;
        }
    }
    if (written) {
        if (kind == KIND_ARRIVED) {
            written = fprintf(file, "Arrived %d\n%s", arrived_before + 1, text) >= 0;
        } else if (kind == KIND_BIRTH && strncmp(text, "Birth\n", 6) == 0) {
            /* "Birth <n>", numbered like a Conception when it is written (the
               owner, 2026-10-09): compose_birth's text opens with "Birth". */
            written = fprintf(file, "Birth %d\n%s", arrived_before + 1, text + 6) >= 0;
        } else if (!kind_is_numbered(kind)) {
            written = fprintf(file, "%s", text) >= 0;
        } else {
            /* "Conception <n>", "Death <n>" or "Unaccounted <n>": the running total across the
               family's files, so numbering never restarts in a new file. */
            written = fprintf(file, "%s%d\n%s", family_marker(log_family_of(kind)),
                              existing_records + 1, text) >= 0;
        }
    }
    /* Flushed separately so a failed write is reported rather than hidden in
       fclose; a half-flushed "Conception " marker would be counted. */
    if (fflush(file) != 0) {
        written = 0;
    }
    if (fclose(file) != 0) {
        written = 0;
    }
    if (!written) {
        /* The caller keeps the record and retries it, so whatever part of it
           reached the disk must go, or the retry duplicates it.

           If the file cannot be put back, its state is unknown -- part of
           this record may be on disk -- and a retry could only add a second
           copy. Codex (#449 review) found that failure was being ignored. So
           that case is reported separately, and the caller does NOT retry. */
        if (!roll_back_append(path, original_size)) {
            return APPEND_UNRECOVERABLE;
        }
        return APPEND_RETRY;
    }
    return APPEND_WRITTEN;
}

/* The closing line of a record whose villagers were not in the village when
   it was saved. */
static const char UNVOUCHED_NOTE[] =
    "  Note: Recorded before this village was saved, among villagers who were\n"
    "    not in it when it was -- likely the game's pre-tribe simulation, or a\n"
    "    tribe left unsaved by Start Over.\n";

/* `text` with UNVOUCHED_NOTE before its closing blank line; NULL if out of
   memory, in which case the record is written unlabelled. */
static char *label_record(const char *text) {
    size_t length = strlen(text);
    size_t body = length;
    char *out;

    if (body > 0 && text[body - 1] == '\n') {
        --body;                           /* keep the closing blank line last */
    }
    out = (char *)malloc(length + sizeof(UNVOUCHED_NOTE));
    if (out == NULL) {
        return NULL;
    }
    memcpy(out, text, body);
    memcpy(out + body, UNVOUCHED_NOTE, sizeof(UNVOUCHED_NOTE) - 1);
    memcpy(out + body + sizeof(UNVOUCHED_NOTE) - 1, text + body, length - body + 1);
    return out;
}

/* Write every held record for this game under `village`, in order. Called once
   the village is known.

   A held record is released only once it is on disk. A write that fails -- a
   locked log, a full disk, a failed flush -- stops the pass and keeps that
   record and every one after it, in order, for the next save to retry. Codex
   (#449 review) found an earlier version freed every entry whether or not it
   had been written, so a transient failure at the first save lost the records
   for good. The one exception is a write whose partial output could not be
   rolled back: retrying it could only duplicate what may already be on disk. */
/* `at_save`: the village has just been saved (or nothing will ever name it). Before that, an
   "Appearance changed" record stays held, and everything behind it with it, in order: the game
   writes the new look into the save only at the save, so a crash before it must not leave the log
   saying the villager changed (Codex, #558). */
static void flush_pending(int game_id, const char *village, int at_save) {
    const struct game_layout *g = layout_of(game_id);
    int i;
    int kept = 0;
    int stopped = 0;
    int now_known = tribes_ready() && take_tribe(game_id, NULL, scratch_tribe);

    for (i = 0; i < pending_count; ++i) {
        struct pending_record *entry = &pending[i];
        int release = 0;
        if (entry->game_id == game_id && !at_save
            && (entry->kind == KIND_APPEARANCE || entry->kind == KIND_ISLAND_EVENT)) {
            stopped = 1;
        }
        if (entry->game_id == game_id && !stopped) {
            const char *text = entry->text;
            char *labelled = NULL;
            int outcome;
            if (now_known && entry->tribe >= 0
                && !same_tribe(&held_tribes[entry->tribe], scratch_tribe, TRIBE_LOOSE)) {
                labelled = label_record(entry->text);
                if (labelled != NULL) {
                    text = labelled;
                }
            }
            outcome = append_record(g, village, entry->kind, text);
            free(labelled);
            if (outcome == APPEND_RETRY) {
                stopped = 1;                  /* keep it and all after it */
            } else {
                release = 1;
            }
        }
        if (release) {
            free(entry->text);
            entry->text = NULL;
        } else {
            pending[kept++] = *entry;
        }
    }
    pending_count = kept;
    if (pending_count == 0) {
        held_tribe_count = 0;             /* no held record refers to them now */
    }
}

/* Queue a finished record behind any already held. */
static int hold_record(int game_id, int kind, const unsigned char *records,
                       const char *text) {
    struct pending_record *entry;
    size_t length;

    if (pending_count >= pending_capacity) {
        int capacity = pending_capacity == 0 ? 64 : pending_capacity * 2;
        struct pending_record *grown = (struct pending_record *)realloc(
            pending, (size_t)capacity * sizeof(*pending));
        if (grown == NULL) {
            return 0;
        }
        pending = grown;
        pending_capacity = capacity;
    }
    length = strlen(text) + 1;
    entry = &pending[pending_count];
    entry->text = (char *)malloc(length);
    if (entry->text == NULL) {
        return 0;
    }
    memcpy(entry->text, text, length);
    entry->game_id = game_id;
    entry->kind = kind;
    entry->tribe = current_tribe_index(game_id, records);
    ++pending_count;
    return 1;
}

/* Write a finished record now, or hold it until the village is known. */
static int emit_record(
    int game_id,
    int kind,
    const unsigned char *records,
    const char *text
) {
    const struct game_layout *g = layout_of(game_id);
    char village[VV_VILLAGE_NAME_MAX + 32];

    if (records != NULL
        && memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride)) {
        last_table[game_id] = records;    /* where the game keeps the tribe */
    }
    if (!vv_village_recall(village, sizeof village)) {
        village[0] = '\0';
    }
    if ((kind == KIND_APPEARANCE || kind == KIND_ISLAND_EVENT) && village_publisher_present(game_id)) {
        return hold_record(game_id, kind, records, text);   /* written at the next save */
    }
    if (village[0] != '\0' && saved_tribe_still_loaded(game_id)) {
        flush_pending(game_id, village, 0);
        /* Written now only when nothing is still waiting and the write works.
           Otherwise it queues BEHIND what is waiting, so a failed write can
           neither lose it nor let it overtake an earlier record. */
        if (pending_count == 0) {
            int outcome = append_record(g, village, kind, text);
            if (outcome == APPEND_WRITTEN) {
                return 1;
            }
            if (outcome == APPEND_UNRECOVERABLE) {
                return 0;             /* never queued: a retry could duplicate */
            }
        }
        return hold_record(game_id, kind, records, text);
    }
    if (village[0] == '\0' && !village_publisher_present(game_id)) {
        /* Records held while a publisher was still expected -- Cause of
           Death shipped, then found unable to hook the save -- go first,
           in order, unlabelled like this one: nothing will name them now. */
        if (pending_count > 0) {
            flush_pending(game_id, village, 1);
            if (pending_count > 0) {
                return hold_record(game_id, kind, records, text);
            }
        }
        return append_record(g, village, kind, text) == APPEND_WRITTEN;
    }
    /* No village yet, or a recalled one the loaded tribe cannot vouch for. */
    return hold_record(game_id, kind, records, text);
}

/* The full entry point. WriteParentageRecord below is the original three
   argument form and forwards here with no father record, so a trampoline that
   has not been rebuilt keeps working exactly as it did. */
/* ---- A New Home: the true-parentage companion ------------------------------

   "VVFP VV1 Parentage.dll" keeps each VV1 villager's parents in a sidecar and
   shows them in the Details screen.  Its conception stash needs exactly what
   this file's VV1 trampolines already capture -- the mother's record and the
   father's -- so the VV1 path hands both on.  Resolved once, from the
   executable's own directory, never from DllMain; when the companion is not
   shipped (its row is off) the call is skipped and this log is unaffected. */
typedef int (__stdcall *vv1_parentage_conceived_t)(const void *records,
                                                    const void *mother,
                                                    const void *father);
static int vv1_parentage_state;   /* 0 = not tried, 1 = resolved, -1 = unavailable */
static vv1_parentage_conceived_t vv1_parentage_conceived;

static void vv1_parentage_bridge(const void *records, const void *mother, const void *father) {
    HMODULE companion;
    if (vv1_parentage_state == 1) {
        vv1_parentage_conceived(records, mother, father);
        return;
    }
    if (vv1_parentage_state != 0) {
        return;
    }
    vv1_parentage_state = -1;
    companion = vvfp_load_patcher_dll("VVFP VV1 Parentage.dll");
    if (companion == NULL) {
        return;
    }
    vv1_parentage_conceived =
        (vv1_parentage_conceived_t)GetProcAddress(companion, "Vv1ParentageConceived");
    if (vv1_parentage_conceived == NULL) {
        return;
    }
    vv1_parentage_state = 1;
    vv1_parentage_conceived(records, mother, father);
}

/* Set only for the length of one WriteParentageConceptionFatherSet call (A
   New Home: a father the Custom Island Event set, with no record of his to
   capture); NULL otherwise. */
static struct {
    const char *name;
    int head, body;
} g_father_set;

/* The father's age, sex, likes and dislikes when the game's own default
   father stands in for one (is_game_default_father): there is no villager to
   read them from. */
#define DEFAULT_FATHER_NONE "(none: game's default father)"

/* 1 when `name`, the father name the game wrote onto the mother at
   conception, is the game's OWN default father rather than a villager's:
   the literal the conception caller passes from the executable's .rdata,
   never a pointer into a record (verified in the stock executables):
     The Lost Children  "?"     0x476290, the Gong of Wonder (caller 0x44EB3E,
                                head 0 and body 0 pushed beside it);
     The Tree of Life   "Joey"  0x4AB360, sub_467B00's island-event babies
                                (0x467C04, head 2 and body 2);
     New Believers      "Joey"  0x4B8E1C, the same event (0x471B5C, 2 and 2).
   A New Home writes no father at all and The Secret City's two conception
   callers always pass a villager.  "Joey Joerson" is how Joey reads once
   Villagers Have Last Names has given him one (the owner, 2026-10-10). */
static int is_game_default_father(int game_id, const char *name) {
    if (name == NULL) {
        return 0;
    }
    if (game_id == GAME_VV2) {
        return strcmp(name, "?") == 0;
    }
    if (game_id == GAME_VV4 || game_id == GAME_VV5) {
        return strcmp(name, "Joey") == 0 || strcmp(name, "Joey Joerson") == 0;
    }
    return 0;
}

__declspec(dllexport) int __stdcall WriteParentageRecordWithFather(
    int game_id,
    const void *records_pointer,
    const void *mother_pointer,
    const void *father_pointer
) {
    const struct game_layout *g;
    const unsigned char *records = (const unsigned char *)records_pointer;
    const unsigned char *mother = (const unsigned char *)mother_pointer;
    const unsigned char *father_supplied =
        (const unsigned char *)father_pointer;
    const unsigned char *father_from_caller = NULL;
    int babies;
    int default_father = 0;           /* the game's own "?" / "Joey" (is_game_default_father) */
    const unsigned char *father;
    /* The rendered record, written now or held until the village is known. */
    char text[RECORD_TEXT_MAX];
    char mother_name[MAX_NAME_BYTES];
    char father_name[MAX_NAME_BYTES];
    /* Rendered rather than printed as %d, so an unavailable field can say so
       instead of printing a 0 that a real villager could also hold. Sized for
       "not recorded by this game" plus its terminator. */
    char father_head[32];
    char father_body[32];
    char father_age[32];
    /* Sized for the longest preference word plus the unavailable wording. */
    char mother_likes[64];
    char mother_dislikes[64];
    char father_likes[64];
    char father_dislikes[64];
    int written;

    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    g = layout_of(game_id);
    /* A game whose record geometry has not been established refuses outright,
       and so does one whose row is filled in but not self-consistent. Logging a
       plausible-looking wrong number would be worse than logging nothing,
       because parentage cannot be recovered from the child later and there is
       no second source to correct the record from. */
    if (!layout_is_usable(g)) {
        return 0;
    }
    if (records == NULL || mother == NULL) {
        return 0;
    }
    if (!is_record_slot(g, records, mother)) {
        return 0;
    }
    if (*(const unsigned char *)(mother + g->active) != 1) {
        return 0;
    }

    /* The father's record, when the caller could supply one.

       Games that record the father BY NAME keep no pointer to his record in
       the mother's, so his age, head and body used to be unavailable on every
       birth -- the whole column read as "not recorded by this game". They are
       not unavailable at the hook site, though: the conception routine holds
       both parent records in registers, so the trampoline can pass the second
       one and these games gain three real fields.

       It is validated exactly like the mother, and additionally rejected if it
       IS the mother: a caller that passed the same record twice would print
       her numbers under his name, which is worse than saying nothing. An
       unusable pointer falls back to the name-only path rather than failing the
       record, so a trampoline that passes rubbish loses three fields instead of
       the whole log. */
    if (father_supplied != NULL
        && father_supplied != mother
        && is_record_slot(g, records, father_supplied)
        && *(const unsigned char *)(father_supplied + g->active) == 1) {
        father_from_caller = father_supplied;
    }

    /* Both are read from the mother's own record, which is why the hook sits at
       the routine's success tails rather than its head: at the head the engine
       has not yet chosen the litter size, so every twin and triplet birth would
       be recorded as a singleton, and a rejected conception would be logged as
       though it happened. */

    babies = *(const int *)(mother + g->litter);
    if (babies < 1) {
        /* A single birth never writes the field -- only the twins branch
           (0x43BC4E) and the triplets branch (0x43BC8C) do -- so it reads zero
           and one is the correct answer.

           Zero, not a stale 2 or 3 from the previous pregnancy: every writer of
           +0x35C in the image was enumerated, and the delivery routine
           sub_42E900 clears it at 0x42F0C7 (xor eax,eax; then 0 into both
           +0x358 and +0x35C), while the two villager-creation routines
           sub_43C350 and sub_43C840 clear it at 0x43C722 and 0x43CABE. So the
           field is reliably zero going into each pregnancy.

           That mattered enough to check: if it had retained the previous
           litter, a single birth following a twin birth would have been logged
           as twins, and there is no second source to correct such a record
           from. */
        babies = 1;
    }

    copy_villager_name(g, mother, mother_name, sizeof(mother_name));
    if (g->father_kind == FATHER_NOT_RECORDED) {
        memcpy(father_name, "(not recorded by this game)", 28);
        father = NULL;
    } else if (g->father_kind == FATHER_BY_CAPTURE) {
        /* Nothing to read from the mother -- the capture is the only source.

           When it is absent the fields are unavailable for THIS birth, which
           is not the same claim as "this game does not record it", so the
           wording deliberately differs from the branch above. A reader who
           sees it on some births and not others learns something true: the
           call site that produced this one did not carry a father. */
        father = father_from_caller;
        if (father == NULL) {
            memcpy(father_name, "(not captured for this birth)", 30);
        } else {
            /* The true-parentage companion stashes him against the mother
               for the birth to come.  Both pointers were validated above
               against the live array; a missing companion is a no-op. */
            vv1_parentage_bridge(records, mother, father);
        }
    } else if (g->father_kind == FATHER_BY_NAME) {
        /* The name is in the mother's record, so it is read from there either
           way -- it is the name the game itself recorded for this conception,
           and it stays authoritative even when a record is also supplied.

           His three numbers come from his record, found in one of two ways,
           and the order matters:

           1. The record the trampoline captured, when it passed one. VV4 and
              VV5 hold both parent records in registers at the conception site,
              so the pointer is the father the engine itself was working with.
           2. Otherwise, a scan for his name. VV1's, VV2's and VV3's hook sites
              have no father record to capture -- in VV2 the name arrives as a
              formatted string argument -- so the scan is the only route there.

           The captured pointer is preferred because the scan cannot resolve a
           name shared by two living villagers, and returns NULL rather than
           guessing. A pointer the engine handed us has no such ambiguity. When
           neither route finds him the log says so rather than printing a 0
           that a real villager could hold. */
        copy_name_field(mother + g->father, father_name, sizeof(father_name),
                        father_key_width(g));
        father = father_from_caller;
        /* The game's OWN default father -- The Lost Children's Gong of Wonder
           "?" 0/0, The Tree of Life's and New Believers' "Joey" 2/2 -- is a
           string in the executable, not a villager, so no record is captured
           and none may be looked for: a living villager who happens to be
           called Joey is not the father of an event's babies. */
        default_father = father == NULL && is_game_default_father(game_id, father_name);
        if (father == NULL && !default_father) {
            father = find_record_by_name(g, records, father_name);
        }
    } else {
        father = find_record_by_id(
            g, records, *(const int *)(mother + g->father));
    }
    if (father != NULL && g->father_kind != FATHER_BY_NAME) {
        /* Not for FATHER_BY_NAME: there the name already came from the
           mother's record, which is what the game recorded for THIS
           conception. The supplied record contributes the numbers only, so a
           father who is later renamed still logs the name he had.

           FATHER_BY_CAPTURE does reach here, and must: VV1 keeps no name for
           him anywhere, so his own record is the only place one exists. */
        copy_villager_name(g, father, father_name, sizeof(father_name));
    } else if (father == NULL && g->father_kind == FATHER_BY_ID) {
        /* The father is recorded by id, and that id may no longer resolve --
           he can die between conception and delivery. Say so plainly rather
           than dropping the record or inventing a name. */
        memcpy(father_name, "(unknown)", 10);
    }

    /* The father's two numbers are rendered as text so an unavailable field
       can say so. They used to print 0 whenever no father record was found,
       and 0 is a value a real villager can hold -- so a reader could not tell
       an unavailable field from a measured one, and the whole column read as a
       village of newborn fathers.

       Two different unavailable cases, kept distinct because they mean
       different things to a reader:

         "not recorded by this game" -- the game keeps no father for this birth
         at all, so nothing was ever looked for. Only VV1 reaches this.

         "(record not found)" -- a father WAS recorded and we went looking for
         his record, and it is not there. He may have died between conception
         and this call, or two living villagers may share his name, in which
         case the scan refuses to guess. Saying "not recorded by this game"
         here would be a false statement about the game rather than about this
         particular birth.

       His AGE prints too, at the owner's later request ("capture the father's
       ages too upon conception").  It is the one field with no copy on the
       mother, so it comes only from the captured record -- read at the
       conception hook, the moment it is reliably his, before he can die or be
       renamed.  When no record was captured it says so rather than falling
       back to a by-name scan (the fragile lookup the owner had this field
       removed over the first time).  Head and body still come from the
       mother's copies below. */
    if (father != NULL) {
        _snprintf(father_head, sizeof(father_head), "%d",
                  *(const int *)(father + g->head));
        _snprintf(father_body, sizeof(father_body), "%d",
                  *(const int *)(father + g->body));
        father_head[sizeof(father_head) - 1] = '\0';
        father_body[sizeof(father_body) - 1] = '\0';
    } else if (g->father_kind == FATHER_NOT_RECORDED) {
        memcpy(father_head, "not recorded by this game", 26);
        memcpy(father_body, "not recorded by this game", 26);
    } else if (g->father_kind == FATHER_BY_CAPTURE) {
        /* No lookup happens for this kind, so "(record not found)" would name
           a search that was never run. The capture simply did not arrive. */
        memcpy(father_head, "(not captured for this birth)", 30);
        memcpy(father_body, "(not captured for this birth)", 30);
    } else {
        memcpy(father_head, "(record not found)", 19);
        memcpy(father_body, "(record not found)", 19);
    }

    /* His age comes from the CAPTURED record only -- the pointer the
       conception hook handed over, read at the one moment it is reliably his:
       he cannot yet have died or been renamed.  No game copies it onto the
       mother, so there is no second source, and the by-name scan above is
       deliberately not one: a hook that supplies no pointer (VV2's batch and
       event callers) would otherwise log whichever living villager happens to
       answer to the stored name -- the "somebody who merely has the same
       name" the owner ruled out.  So the age is either his or honestly
       absent, never a scanned villager's. */
    if (father_from_caller != NULL) {
        _snprintf(father_age, sizeof(father_age), "%d",
                  *(const int *)(father_from_caller + g->age));
        father_age[sizeof(father_age) - 1] = '\0';
    } else if (g->father_kind == FATHER_NOT_RECORDED) {
        memcpy(father_age, "not recorded by this game", 26);
    } else if (default_father) {
        /* No villager stands behind the game's default father, so he has no
           age, sex, likes or dislikes -- and nothing failed to capture them. */
        memcpy(father_age, DEFAULT_FATHER_NONE, sizeof DEFAULT_FATHER_NONE);
    } else {
        memcpy(father_age, "(not captured for this birth)", 30);
    }

    /* Both parents' likes and dislikes -- the owner's identity fields, so
       two villagers who share a name can be told apart in the log.  Each is
       what the Details panel shows: the first filled entry of the array, named
       from this game's own list.  The mother's come from her record, live at
       the hook.  The father's come from the CAPTURED record only, exactly as
       his age does: no game copies them onto the mother, and a by-name scan
       could hand back whichever living villager answers to the stored name.
       With no captured record they say what his age says -- honestly absent,
       never guessed. */
    preference_text(g, mother, g->likes, mother_likes, sizeof mother_likes);
    preference_text(g, mother, g->dislikes, mother_dislikes, sizeof mother_dislikes);
    if (father_from_caller != NULL) {
        preference_text(g, father_from_caller, g->likes, father_likes, sizeof father_likes);
        preference_text(g, father_from_caller, g->dislikes, father_dislikes, sizeof father_dislikes);
    } else {
        memcpy(father_likes, father_age, sizeof father_age);
        memcpy(father_dislikes, father_age, sizeof father_age);
    }

    /* Where the game copied the father's traits onto the mother at conception,
       prefer those copies over anything the name scan produced -- and use them
       even when it produced nothing. They are the same numbers, read from the
       father himself at conception rather than from whoever still answers to
       his name at delivery, so they are correct in the two cases the scan is
       not: he has died in the interval, or a second living villager shares his
       name and the scan rightly refuses to guess.

       Head and body are the only father fields the log prints, and these
       copies are where both now come from whenever the game provides them. */
    if (g->father_head_copy != 0) {
        _snprintf(father_head, sizeof(father_head), "%d",
                  *(const int *)(mother + g->father_head_copy));
        father_head[sizeof(father_head) - 1] = '\0';
    }
    if (g->father_body_copy != 0) {
        _snprintf(father_body, sizeof(father_body), "%d",
                  *(const int *)(mother + g->father_body_copy));
        father_body[sizeof(father_body) - 1] = '\0';
    }
    /* A father the Custom Island Event set (WriteParentageConceptionFatherSet):
       his name, head and body as the player gave them; his age, sex, likes
       and dislikes stay "not captured", as for any father with no record. */
    if (g_father_set.name != NULL && father_from_caller == NULL) {
        lstrcpynA(father_name, g_father_set.name, (int)sizeof(father_name));
        _snprintf(father_head, sizeof(father_head), "%d", g_father_set.head);
        _snprintf(father_body, sizeof(father_body), "%d", g_father_set.body);
        father_head[sizeof(father_head) - 1] = '\0';
        father_body[sizeof(father_body) - 1] = '\0';
    }
    /* Everything after the "Conception <n>" line. The number is assigned when
       the record is actually written, which for a record held until the
       village's first save is later than now -- see emit_record. */
    written = _snprintf(
        text, sizeof(text),
        "  Mother: %s\n"
        "    Age at conception: %d\n"
        "    Sex: %s\n"
        "    Head: %d\n"
        "    Body: %d\n"
        "    Likes: %s\n"
        "    Dislikes: %s\n"
        "  Father: %s\n"
        "    Age at conception: %s\n"
        "    Sex: %s\n"
        "    Head: %s\n"
        "    Body: %s\n"
        "    Likes: %s\n"
        "    Dislikes: %s\n"
        "  Babies nursing: %d\n"
        "%s"
        "\n",
        mother_name,
        *(const int *)(mother + g->age),
        sex_text(g, mother),
        *(const int *)(mother + g->head),
        *(const int *)(mother + g->body),
        mother_likes,
        mother_dislikes,
        father_name,
        father_age,
        /* His sex, like his age, from the captured record only. */
        father_from_caller != NULL ? sex_text(g, father_from_caller) : father_age,
        father_head,
        father_body,
        father_likes,
        father_dislikes,
        babies,
        g_father_set.name != NULL && father_from_caller == NULL
            ? "  Note: Father set by a Custom Island Event\n" : ""
    );
    if (written < 0 || (size_t)written >= sizeof(text)) {
        return 0;
    }
    return emit_record(game_id, 0, records, text);
}

/* A New Home: the Conception record of a pregnancy whose father the Custom
   Island Event's "unborn baby's father" just changed.

   The Lost Children to New Believers keep the father on the mother, and the
   birth takes him from there.  A New Home keeps him only in the VV1
   Parentage companion's pregnancy stash, and every reader of this log -- the
   companion's first-load check, the Family Tree Maker, Repair Saves & Logs --
   takes a pregnancy's father from her LAST Conception record.  So the change
   is recorded as one, by the one function that renders a conception
   (WriteParentageRecordWithFather, through g_father_set): the mother as she
   is now, the father as the player set him -- his name, head and body;
   nothing else of his was captured -- the babies she carries, and a note
   saying how it came about.  VV1 only; 1 when written or held for the next
   save. */
__declspec(dllexport) int __stdcall WriteParentageConceptionFatherSet(
    int game_id,
    const void *records_pointer,
    const void *mother_pointer,
    const char *father_name,
    int father_head,
    int father_body
) {
    int result;
    if (game_id != GAME_VV1 || father_name == NULL || father_name[0] == '\0'
        || father_head < 0 || father_body < 0) {
        return 0;
    }
    g_father_set.name = father_name;
    g_father_set.head = father_head;
    g_father_set.body = father_body;
    result = WriteParentageRecordWithFather(game_id, records_pointer, mother_pointer, NULL);
    g_father_set.name = NULL;
    return result;
}

/* One birth record, written by the VV1 parentage companion the moment it sees
   a child appear -- before it spends its pregnancy stash or rewrites its
   sidecar.  Same file, same village header and roll-over as the conception
   records above; "Birth" rows are not counted toward the roll (count_records
   counts "Conception " markers), so a file still holds RECORDS_PER_FILE
   conceptions plus their births.

   Appearance values arrive as -1 when the companion does not know them (an
   immigrant, a founder, a birth whose father was never captured), and are
   printed as "(unknown)" rather than as a number a real villager could hold. */
/* `child_record` is the child's live villager record, or NULL when the caller
   has none to give. It is what the child's own likes, dislikes and skills are
   read from -- they are not derivable from the name and appearance values the
   other arguments carry. A NULL record simply omits those lines, so a caller
   that cannot supply one still logs a complete birth. */
static void tell_cause_of_death_birth(int game_id, const void *child_record);

/* How many babies the delivery that is creating this child holds, read from
   the mother's own litter field (VV2-VV5: the exe's birth splice calls
   WriteParentageBirth at the creation, between the litter compares that
   guard the twin and triplet creations, so the field is this delivery's).
   The mother is the one living female villager with this name, head and
   body; none, or two, and the count is not known (-1).  The games write
   nothing for a single birth in VV1/VV2 (0 = one baby). */
static int delivery_litter(int game_id, const struct game_layout *g, const char *mother_name,
                           int mother_head, int mother_body) {
    const unsigned char *records = villager_table(game_id);
    int index, found = -1;
    char name[MAX_NAME_BYTES], want[MAX_NAME_BYTES];
    if (records == NULL || g->litter == 0u || mother_name == NULL || mother_name[0] == '\0'
        || !memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride)) {
        return -1;
    }
    copy_name_field((const unsigned char *)mother_name, want, sizeof want, g->name_capacity);
    for (index = 0; index < g->slots; ++index) {
        const unsigned char *r = records + g->record_base + (size_t)index * g->stride;
        if (*(const unsigned char *)(r + g->active) != 1 || vv_lookalike(g->stride, r)
            || *(const int *)(r + g->sex) != g->sex_female
            || (mother_head >= 0 && *(const int *)(r + g->head) != mother_head)
            || (mother_body >= 0 && *(const int *)(r + g->body) != mother_body)) {
            continue;
        }
        copy_name_field(r + g->name, name, sizeof name, g->name_capacity);
        if (strcmp(name, want) != 0) {
            continue;
        }
        if (found >= 0) {
            return -1;
        }
        found = index;
    }
    if (found < 0) {
        return -1;
    }
    index = *(const int *)(records + g->record_base + (size_t)found * g->stride + g->litter);
    return index < 1 ? 1 : index > 3 ? -1 : index;
}

/* The Birth record's "  Born as:" line for a delivery of `litter` babies
   (the owner, 2026-10-06: twins and triplets in the logs); empty when not
   known. */
static const char *born_as_line(int litter) {
    return litter == 1 ? "  Born as: Single birth\n"
         : litter == 2 ? "  Born as: Twin\n"
         : litter == 3 ? "  Born as: Triplet\n"
         : litter == 4 ? "  Born as: Golden Child\n  Age at birth: 100 (5 years old)\n"
         : "";     /* 4: A New Home's Golden Child (vv1_parentage), born at and kept at exactly 5 years (the owner, 2026-10-08; the owner's log: Lulu, 100) */
}

/* The Birth record's text (WriteParentageBirth's arguments), with `note`
   -- a whole "  Note: ...\n" line, or NULL -- after the parents: the
   backfill's "Recorded afterwards" (arrival_backfill.inc).  `litter` is the
   delivery's babies (1-3), 0 to read them from the mother now (a birth
   written at its creation), or -1 when not known (a backfilled birth).
   1 when composed. */
static int compose_birth(
    int game_id,
    const char *child_name, int child_head, int child_body,
    const char *mother_name, int mother_head, int mother_body,
    const char *father_name, int father_head, int father_body,
    const void *child_record,
    const char *note,
    int litter,
    char *text,
    size_t text_size
) {
    const struct game_layout *g;
    char child[MAX_NAME_BYTES];
    char mother[MAX_NAME_BYTES];
    char father[MAX_NAME_BYTES];
    char mh[32], mb[32], fh[32], fb[32];
    char child_likes[64], child_dislikes[64];
    char skills[512];
    const unsigned char *rec = (const unsigned char *)child_record;
    int written;

    /* EVERY GAME, not just VV1.

       This used to refuse anything but A New Home, on the reasoning
       that only VV1 needs a companion to recover parentage: VV2-VV5
       store both parents on the child's own record, and their
       Population log already prints them.

       That is true and beside the point. The owner's requirement is
       that all five games ship the same log format, so a Birth record
       VV1 writes has to be written by the other four as well. The
       facts being recoverable from another log is not a reason for
       this one to differ between games.

       The difference in where the parents come from is absorbed
       below: VV1 takes them from its arguments, VV2-VV5 read them
       from the child record the caller already supplies. */
    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    g = layout_of(game_id);
    if (!layout_is_usable(g)) {
        return 0;
    }

    /* THE CHILD'S OWN FIELDS, from its record when the caller has none.

       VV1 passes a real name and real values and is unchanged: an
       explicit argument always wins, and the record path engages only
       when the caller supplies nothing.

       It exists so a birth hook can pass just the game id and the
       child's record. Extracting the name and two integers in the
       hook instead would mean hand-written assembly inside a cave's
       byte budget, in four games, to produce facts this function is
       already holding a pointer to. */
    if (rec != NULL && (child_name == NULL || child_name[0] == '\0')) {
        child_name = (const char *)(rec + g->name);
        if (child_head < 0) {
            child_head = *(const int *)(rec + g->head);
        }
        if (child_body < 0) {
            child_body = *(const int *)(rec + g->body);
        }
    }
    if (child_name == NULL || child_name[0] == '\0') {
        return 0;         /* no name from either source: not a villager */
    }
    copy_name_field((const unsigned char *)child_name, child, sizeof(child), g->name_capacity);

    /* WHERE THE PARENTS COME FROM, per game.

       VV1 stores none on the record, so parent_father_name is 0 there
       and its caller's arguments are the only source -- unchanged.

       VV2-VV5 keep both parents on the CHILD's own record for life.
       When the caller names no parent, they are read from `rec`,
       which is the child record the caller already passes for the
       likes, dislikes and skills below. An explicit argument still
       wins, so a future caller that knows better is not overridden.

       The offsets were verified against all four running games over
       370 living villagers: no malformed name, and no name resolving
       as both a father and a mother across 96 distinct parents. */
    if (rec != NULL && g->parent_father_name != 0u) {
        if (mother_name == NULL || mother_name[0] == '\0') {
            mother_name = (const char *)(rec + g->parent_mother_name);
            if (mother_head < 0) {
                mother_head = *(const int *)(rec + g->parent_mother_head);
            }
            if (mother_body < 0) {
                mother_body = *(const int *)(rec + g->parent_mother_body);
            }
        }
        if (father_name == NULL || father_name[0] == '\0') {
            father_name = (const char *)(rec + g->parent_father_name);
            if (father_head < 0) {
                father_head = *(const int *)(rec + g->parent_father_head);
            }
            if (father_body < 0) {
                father_body = *(const int *)(rec + g->parent_father_body);
            }
        }
    }

    if (mother_name != NULL && mother_name[0] != '\0') {
        copy_name_field((const unsigned char *)mother_name, mother, sizeof(mother), g->name_capacity);
    } else {
        memcpy(mother, "(unknown)", 10);
    }
    if (father_name != NULL && father_name[0] != '\0') {
        copy_name_field((const unsigned char *)father_name, father, sizeof(father), g->name_capacity);
    } else {
        memcpy(father, "(unknown)", 10);
    }
#define VV1_BIRTH_FIELD(out, value) do { \
        if ((value) < 0) { memcpy((out), "(unknown)", 10); } \
        else { _snprintf((out), sizeof(out), "%d", (value)); (out)[sizeof(out) - 1] = '\0'; } \
    } while (0)
    VV1_BIRTH_FIELD(mh, mother_head);
    VV1_BIRTH_FIELD(mb, mother_body);
    VV1_BIRTH_FIELD(fh, father_head);
    VV1_BIRTH_FIELD(fb, father_body);
#undef VV1_BIRTH_FIELD

    /* The child's own preferences and skills, read from its live record. A
       caller with no record to give passes NULL, and then these read as
       "(none)" and the Skills block is empty rather than the birth being
       dropped. */
    preference_text(g, rec, g->likes, child_likes, sizeof child_likes);
    preference_text(g, rec, g->dislikes, child_dislikes, sizeof child_dislikes);
    skill_text(g, rec, skills, sizeof skills);
    if (litter == 0) {
        litter = delivery_litter(game_id, g, mother_name, mother_head, mother_body);
    }

    written = _snprintf(
        text, text_size,
        "Birth\n"
        "  Child: %s\n"
        "    Sex: %s\n"
        "    Head: %d\n"
        "    Body: %d\n"
        "    Likes: %s\n"
        "    Dislikes: %s\n"
        "%s"
        "  Mother: %s\n"
        "    Head: %s\n"
        "    Body: %s\n"
        "  Father: %s\n"
        "    Head: %s\n"
        "    Body: %s\n"
        "%s"
        "%s"
        "\n",
        child, sex_text(g, rec), child_head, child_body, child_likes, child_dislikes, skills,
        mother, mh, mb,
        father, fh, fb,
        born_as_line(litter),
        note != NULL ? note : ""
    );
    if (written < 0 || (size_t)written >= text_size) {
        return 0;
    }
    return 1;
}

/* The village's save slot for VVFP Last Names: the " (Save N)" the village
   was last saved under, or 0 -- named only once it is saved; a birth in the
   catch-up as it loads comes first, and the DLL then finds the slot from the
   names. */
static int last_names_slot(void) {
    char village[VV_VILLAGE_NAME_MAX + 32];
    const char *at = NULL, *scan;
    if (vv_village_recall(village, sizeof village)) {
        for (scan = village; (scan = strstr(scan, " (Save ")) != NULL; ++scan) {
            at = scan;
        }
    }
    return at != NULL && at[7] >= '1' && at[7] <= '9' && at[8] == ')' ? at[7] - '0' : 0;
}

typedef int (__stdcall *rule_last_name_t)(char *name, unsigned int room, const char *father, int father_head,
                                           int father_body, const char *mother, int mother_head,
                                           int mother_body, int slot);

/* The Lost Children to New Believers, at the child's creation: its name made
   its first name and the last name the player's rule gives (Repair Saves &
   Logs' "Last names come from", and a parent's own rule; VVFP Last Names'
   VvfpRuleLastName2), from the parents the game keeps on its record -- their
   names, heads and bodies, as the Birth record shows them -- before the Birth
   record or anything else names it (the owner, 2026-10-08: babies named for
   their mother's family number, not by the rule -- "fix it").  A New Home's
   companion does the same at its own birth hook, with the parents it
   recorded. */
static void rule_last_name(int game_id, unsigned char *rec) {
    static int state;             /* 0 not tried, 1 resolved, -1 unavailable */
    static rule_last_name_t rule;
    const struct game_layout *g;
    char father[MAX_NAME_BYTES], mother[MAX_NAME_BYTES];
    if (game_id < GAME_VV2 || game_id > GAME_VV5 || rec == NULL) {
        return;
    }
    if (state == 0) {
        HMODULE dll = GetModuleHandleA("VVFP Last Names.dll");
        rule = dll ? (rule_last_name_t)GetProcAddress(dll, "VvfpRuleLastName2") : NULL;
        state = rule ? 1 : -1;
    }
    g = layout_of(game_id);
    if (state != 1 || !layout_is_usable(g) || g->parent_father_name == 0u) {
        return;
    }
    copy_name_field(rec + g->parent_father_name, father, sizeof father, g->name_capacity);
    copy_name_field(rec + g->parent_mother_name, mother, sizeof mother, g->name_capacity);
    rule((char *)(rec + g->name), g->name_capacity,
         father, *(const int *)(rec + g->parent_father_head), *(const int *)(rec + g->parent_father_body),
         mother, *(const int *)(rec + g->parent_mother_head), *(const int *)(rec + g->parent_mother_body),
         last_names_slot());
}

typedef int (__stdcall *relook_last_name_t)(const char *name, int male, int old_head, int old_body, int new_head,
                                             int new_body, int slot);

/* An "Appearance changed" record (Change Appearance, the Island Events log --
   a Custom Island Event's change too): the villager's own last-name rule,
   kept by name, head, body and sex, follows them to the new looks at once
   (VVFP Last Names' VvfpRelookLastName), so the births before the next
   Repair still find it.  `before` is the record's own "  Old head: ..\n  Old
   body: ..\n  New head: ..\n  New body: ..\n" lines.  Nothing happens without
   the Last Names DLL. */
static void relook_last_name(const struct game_layout *g, const unsigned char *record, const char *before) {
    static int state;             /* 0 not tried, 1 resolved, -1 unavailable */
    static relook_last_name_t relook;
    char name[MAX_NAME_BYTES];
    int oh, ob, nh, nb, male;
    if (state == 0) {
        HMODULE dll = GetModuleHandleA("VVFP Last Names.dll");
        relook = dll ? (relook_last_name_t)GetProcAddress(dll, "VvfpRelookLastName") : NULL;
        state = relook ? 1 : -1;
    }
    if (state != 1 || before == NULL
        || sscanf_s(before, "  Old head: %d\n  Old body: %d\n  New head: %d\n  New body: %d", &oh, &ob, &nh, &nb) != 4) {
        return;
    }
    male = strcmp(sex_text(g, record), "Male") == 0;
    if (!male && strcmp(sex_text(g, record), "Female") != 0) {
        return;
    }
    copy_villager_name(g, record, name, sizeof name);
    (void)relook(name, male, oh, ob, nh, nb, last_names_slot());
}

/* WriteParentageBirth with the delivery's babies given: 1-3, or -1 when not
   known (no "Born as" line). */
__declspec(dllexport) int __stdcall WriteParentageBirthLitter(
    int game_id,
    const char *child_name, int child_head, int child_body,
    const char *mother_name, int mother_head, int mother_body,
    const char *father_name, int father_head, int father_body,
    const void *child_record,
    int litter
) {
    char text[RECORD_TEXT_MAX];
    if (child_name == NULL || child_name[0] == '\0') {   /* the record is the name: the exe's splices */
        rule_last_name(game_id, (unsigned char *)child_record);
    }
    if (!compose_birth(game_id, child_name, child_head, child_body, mother_name, mother_head,
                       mother_body, father_name, father_head, father_body, child_record, NULL,
                       litter, text, sizeof text)) {
        return 0;
    }
    /* The Unaccounted Villagers reconciliation counts this child as a known
       arrival, whether or not the record could be filed now. */
    tell_cause_of_death_birth(game_id, child_record);
    /* The child is the villager a held birth is re-checked against. */
    return emit_record(game_id, KIND_BIRTH, NULL, text);
}

/* A New Home: the Birth record of a villager the Births log has none for,
   written afterwards by the VV1 Parentage companion's cross-check from its
   parentage file (vv1_crosscheck.inc) -- the record The Lost Children to New
   Believers write from the save (arrival_backfill.inc), with the same
   "Note: Recorded afterwards (born before this log existed)" and no
   "Born as" line (how many came together is not known).  1 when written or
   held for the next save. */
__declspec(dllexport) int __stdcall WriteParentageBirthAfterwards(
    int game_id,
    const char *child_name, int child_head, int child_body,
    const char *mother_name, int mother_head, int mother_body,
    const char *father_name, int father_head, int father_body,
    const void *child_record
) {
    char text[RECORD_TEXT_MAX];
    /* Every game compose_birth accepts: only A New Home's companion calls it,
       but the record is the one all five write. */
    if (!compose_birth(game_id, child_name, child_head, child_body, mother_name, mother_head,
                          mother_body, father_name, father_head, father_body, child_record,
                          /* arrival_backfill.inc's BIRTH_BACKFILL_NOTE, word for word */
                          "  Note: Recorded afterwards (born before this log existed)\n",
                          -1, text, sizeof text)) {
        return 0;
    }
    return emit_record(game_id, KIND_BIRTH, NULL, text);
}

__declspec(dllexport) int __stdcall WriteParentageBirth(
    int game_id,
    const char *child_name, int child_head, int child_body,
    const char *mother_name, int mother_head, int mother_body,
    const char *father_name, int father_head, int father_body,
    const void *child_record
) {
    /* The Lost Children to New Believers call this from the executable's
       birth splice, at the child's creation: the mother's litter field is
       this delivery's (0 = read it).  A New Home's companion writes a frame
       later, after the delivery cleared it (0x42F0C7), and passes the count
       it saw through WriteParentageBirthLitter instead. */
    return WriteParentageBirthLitter(game_id, child_name, child_head, child_body, mother_name,
                                     mother_head, mother_body, father_name, father_head,
                                     father_body, child_record, game_id == 1 ? -1 : 0);
}

/* The villager's custom title (Story / Cheat Upgrades' Custom Island Event),
   for the "  Custom title:" line the Village Population and History pages
   print under the name.  The owner (2026-10-06): custom titles belong in the
   villager logs too.

   The titles are kept per save slot (native/shared/custom_titles.h); the
   slot is the one the village header names ("... (Save <n>)", its LAST such
   marker, as every reader takes it).  A title belongs to the villager whose
   name, likes and dislikes hash to its identity: the one entry with this
   record's identity is used -- by identity alone, since a departed
   villager's record is a rebuilt copy with no index -- and none when two
   entries, or two living villagers, carry that identity (the villager panel
   shows it on neither).  No file, an unreadable file, no header or no
   match: no line. */
static int record_custom_title(int game_id, const struct game_layout *g,
                               const unsigned char *record, const unsigned char *records,
                               int departed, char *out, size_t out_size) {
    static unsigned char data[VV_TITLES_FILE_MAX];
    static vv_custom_title titles[VV_TITLES_MAX];
    char village[VV_VILLAGE_NAME_MAX + 32];
    char folder[MAX_PATH];
    char path[MAX_PATH];
    const char *at = NULL;
    const char *scan;
    vv_titles_check check;
    unsigned int identity;
    HANDLE h;
    DWORD got = 0;
    int count, i, found = -1, slot;
    out[0] = '\0';
    if (g->likes == 0u || g->dislikes == 0u || g->preference_slots == 0u
        || !vv_village_recall(village, sizeof village)) {
        return 0;
    }
    for (scan = village; (scan = strstr(scan, " (Save ")) != NULL; ++scan) {
        at = scan;
    }
    if (at == NULL || at[7] < '1' || at[7] > '5' || at[8] != ')') {
        return 0;
    }
    slot = at[7] - '0';
    if (!vv_save_folder(folder, (int)sizeof("\\" VV_TITLES_SUBFOLDER "\\Custom Titles - Save 0.dat"))) {
        return 0;
    }
    lstrcatA(folder, "\\" VV_TITLES_SUBFOLDER);
    if (!vv_titles_file_name(path, MAX_PATH, folder, slot)) {
        return 0;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!ReadFile(h, data, sizeof data, &got, NULL)) {
        got = 0;
    }
    CloseHandle(h);
    check.game = game_id;
    check.slots = (unsigned int)g->slots;
    if (got == 0 || !vv_titles_validate(data, got, &check)) {
        return 0;
    }
    count = vv_titles_parse(data, titles);
    identity = vv_title_identity(record, g->name, g->name_capacity, g->likes, g->dislikes,
                                 g->preference_slots);
    for (i = 0; i < count; ++i) {
        if (titles[i].fingerprint == identity) {
            if (found >= 0) {
                return 0;
            }
            found = i;
        }
    }
    if (found < 0) {
        return 0;
    }
    /* A rebuilt copy of a departed villager (`departed`) is in no live
       record, so ANY living carrier of its identity may be the title's
       owner (Codex, #553); a live record is one carrier itself.  With no
       readable live table a departed copy cannot be checked: no title. */
    if (departed && records == NULL) {
        return 0;
    }
    if (records != NULL) {
        int carriers = departed ? 1 : 0, index;
        for (index = 0; index < g->slots; ++index) {
            const unsigned char *other = records + g->record_base + (size_t)index * g->stride;
            if (*(const unsigned char *)(other + g->active) == 1 && !vv_lookalike(g->stride, other)
                && vv_title_identity(other, g->name, g->name_capacity, g->likes, g->dislikes,
                                     g->preference_slots) == identity
                && ++carriers > 1) {
                return 0;
            }
        }
    }
    _snprintf_s(out, out_size, _TRUNCATE, "  Custom title: %s\n", titles[found].title);
    return 1;
}

/* The villager's Special villager title (native/shared/special_title.h),
   with New Believers' Former Heathens file for the village's slot: who was
   converted from the Heathens and which mask they wore. */
static const char *record_special_title(int game_id, const struct game_layout *g,
                                        const unsigned char *record) {
    static unsigned char former[VV_FORMER_FILE_MAX];
    char village[VV_VILLAGE_NAME_MAX + 32];
    int kind = -1;
    if (game_id == GAME_VV5 && g->likes != 0u && vv_village_recall(village, sizeof village)
        && vv_former_load(vv_former_header_slot(village), former)) {
        unsigned int identity = vv_title_identity(record, g->name, g->name_capacity, g->likes,
                                                  g->dislikes, g->preference_slots);
        const unsigned char *records = villager_table(game_id);
        kind = vv_former_lookup(former, identity);
        /* An identity another living villager carries too is nobody's (Codex, #553): the
           title is shown on neither, as a custom title is not. */
        if (kind >= 0 && records != NULL
            && memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride)) {
            int index, carriers = 0;
            for (index = 0; index < g->slots; ++index) {
                const unsigned char *other = records + g->record_base + (size_t)index * g->stride;
                if (other != record && *(const unsigned char *)(other + g->active) == 1
                    && !vv_lookalike(g->stride, other)
                    && vv_title_identity(other, g->name, g->name_capacity, g->likes, g->dislikes,
                                         g->preference_slots) == identity) {
                    ++carriers;
                }
            }
            if (carriers > 0) {
                kind = -1;
            }
        }
    }
    return vv_special_title_former(game_id, record, kind);
}

/* A villager's likes (`dislikes` 0) or dislikes (1) as the logs print them,
   from a record or a copy of one at the record's own offsets -- for "VVFP
   Island Events.dll", which shows a change as "old -> new".  0 when the game
   or the record cannot be read. */
__declspec(dllexport) int __stdcall VillagePreferenceText(int game_id, const void *record_pointer, int dislikes,
                                                          char *out, int out_size) {
    const struct game_layout *g;
    if (game_id < GAME_VV1 || game_id > GAME_VV5 || record_pointer == NULL || out == NULL || out_size <= 0) {
        return 0;
    }
    g = layout_of(game_id);
    if (!layout_is_usable(g) || !memory_is_readable(record_pointer, g->stride)) {
        return 0;
    }
    preference_text(g, (const unsigned char *)record_pointer, dislikes ? g->dislikes : g->likes, out,
                    (size_t)out_size);
    return 1;
}

/* Every like (`dislikes` 0) or dislike (1) a villager has, in the words the
   logs print them (the first filled slot is what the Births log's "Likes:"
   shows; this names each filled slot in order, ", " between them), or
   "(none)" -- for "VVFP Island Events.dll", whose "Likes: old -> new" line
   must show a change in any slot, not only the first.  0 when the game or
   the record cannot be read. */
__declspec(dllexport) int __stdcall VillagePreferenceListText(int game_id, const void *record_pointer, int dislikes,
                                                              char *out, int out_size) {
    const struct game_layout *g;
    const unsigned char *record = (const unsigned char *)record_pointer;
    unsigned int base, slot;
    size_t used = 0;
    if (game_id < GAME_VV1 || game_id > GAME_VV5 || record == NULL || out == NULL || out_size <= 0) {
        return 0;
    }
    g = layout_of(game_id);
    if (!layout_is_usable(g) || !memory_is_readable(record, g->stride)) {
        return 0;
    }
    out[0] = '\0';
    base = dislikes ? g->dislikes : g->likes;
    if (base != 0u && g->preference_list != NULL) {
        for (slot = 0; slot < g->preference_slots; ++slot) {
            char word[64];
            int value = *(const int *)(record + base + slot * 4u);
            if (value < 0 || !preference_name(g->preference_list, value, word, sizeof word)) {
                continue;
            }
            if (used + strlen(word) + 3 >= (size_t)out_size) {
                break;
            }
            used += (size_t)_snprintf(out + used, (size_t)out_size - used, "%s%s", used ? ", " : "", word);
        }
    }
    if (used == 0) {
        _snprintf(out, (size_t)out_size, "(none)");
    }
    out[out_size - 1] = '\0';
    return 1;
}

/* A living villager's custom title as the villager logs print it (the
   "  Custom title:" line's value), for "VVFP Island Events.dll", which shows
   a Custom Island Event's title change as "old -> new".  `out` gets the
   title, or "" when the villager has none.  0 when the game, the record or
   the titles cannot be read (then nothing is compared). */
__declspec(dllexport) int __stdcall VillageCustomTitle(int game_id, const void *record_pointer, char *out,
                                                        int out_size) {
    const struct game_layout *g;
    const unsigned char *records;
    char line[96];
    const char *start;
    size_t n;
    if (game_id < GAME_VV1 || game_id > GAME_VV5 || record_pointer == NULL || out == NULL || out_size <= 0) {
        return 0;
    }
    out[0] = '\0';
    g = layout_of(game_id);
    records = villager_table(game_id);
    if (!layout_is_usable(g) || records == NULL
        || !memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride)
        || !is_record_slot(g, records, (const unsigned char *)record_pointer)) {
        return 0;
    }
    if (!record_custom_title(game_id, g, (const unsigned char *)record_pointer, records, 0, line, sizeof line)) {
        return 1;                         /* no title */
    }
    start = strstr(line, ": ");
    start = start != NULL ? start + 2 : line;
    n = strcspn(start, "\n");              /* the title ends at its line's end; a CR before it is not part of it */
    if (n > 0 && start[n - 1] == '\r') {
        --n;
    }
    if (n >= (size_t)out_size) {
        n = (size_t)out_size - 1;
    }
    memcpy(out, start, n);
    out[n] = '\0';
    return 1;
}

/* A village-wide island event record ("VVFP Island Events.dll": the food,
   tech points, food stores, puzzles and weather an event changed), filed in
   the Island Events log as every "Island event <n>" record is -- held until
   the next save like the villagers' -- with no villager of its own.  `text`
   is the record's lines after its heading, each "  Label: value\n". */
__declspec(dllexport) int __stdcall WriteVillageEventRecord(int game_id, const char *text) {
    const struct game_layout *g;
    char record[RECORD_TEXT_MAX];
    int written;
    if (game_id < GAME_VV1 || game_id > GAME_VV5 || text == NULL || text[0] == '\0') {
        return 0;
    }
    g = layout_of(game_id);
    if (!layout_is_usable(g)) {
        return 0;
    }
    written = _snprintf(record, sizeof record, "%s\n", text);
    if (written < 0 || (size_t)written >= sizeof record) {
        return 0;
    }
    return emit_record(game_id, KIND_ISLAND_EVENT, villager_table(game_id), record);
}

/* The Deaths and Unaccounted Villagers records, filed for "VVFP Cause of
   Death.dll", which sees the deaths, burials, removals and arrivals and
   decides what each record says.  One format in all five games:

       Death <n>                       (numbered; the Deaths log)
         Name: <name>
         <before: Age at death, Cause of death, Grave, Epitaph>
         Head / Body / Likes / Dislikes
         <after>

       Disappeared                     (the Deaths log; never rolls)
       Epitaph changed                 (the Deaths log; never rolls)
       Unaccounted <n>                 (numbered; the Unaccounted Villagers log)
       Lost before birth               (the Births and Conceptions log; never
                                        rolls; every line is `before`)

   The caller renders the lines that are its own (`before`, `after`; each
   line "  Label: value\n"); this exporter prints the heading, the name and
   with `detail` 1 the identity fields a Birth record prints (head, body,
   likes, dislikes), and with 2 also the skills block and the villager's own
   parents, from `record`.  `detail` 0 prints the name alone (an epitaph
   change, whose villager has no record any more).

   `record` is the villager's own record, checked to be one of the game's
   villager records when `check` is set -- so a wrong pointer can never
   print a plausible stranger.  A departed villager no longer has one: the
   caller then passes `check` 0 and a copy rebuilt at the record's own
   offsets from what it kept. */
__declspec(dllexport) int __stdcall WriteVillageRecord(
    int game_id,
    int kind,
    const void *record_pointer,
    int check,
    const char *before,
    const char *after,
    int detail
) {
    const struct game_layout *g;
    const unsigned char *record = (const unsigned char *)record_pointer;
    const unsigned char *records;
    const char *heading = "";
    char name[MAX_NAME_BYTES];
    char likes[64], dislikes[64];
    char skills[512];
    char parents[256];
    char special[128];
    char custom[64];
    char text[RECORD_TEXT_MAX];
    int written;

    if (game_id < GAME_VV1 || game_id > GAME_VV5 || record == NULL
        || kind < KIND_DEATH || kind > KIND_LOST_BIRTH) {
        return 0;
    }
    g = layout_of(game_id);
    if (!layout_is_usable(g)) {
        return 0;
    }
    records = villager_table(game_id);
    if (check
        && (records == NULL
            || !memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride)
            || !is_record_slot(g, records, record))) {
        return 0;
    }
    if (!check && !memory_is_readable(record, g->stride)) {
        return 0;
    }
    if (kind == KIND_LOST_BIRTH) {
        /* Every line is the caller's (`before`): the mother, the father and
           the babies, as a Conception names them.  `record` is the mother's,
           only checked and used to file the record under her tribe. */
        if (before == NULL || before[0] == '\0') {
            return 0;
        }
        written = _snprintf(text, sizeof(text), "Lost before birth\n%s\n", before);
        if (written < 0 || (size_t)written >= sizeof(text)) {
            return 0;
        }
        return emit_record(game_id, kind, check ? records : NULL, text);
    }
    if (kind == KIND_DISAPPEARED) {
        heading = "Disappeared\n";
    } else if (kind == KIND_EPITAPH) {
        heading = "Epitaph changed\n";
    } else if (kind == KIND_APPEARANCE) {
        heading = "Appearance changed\n";
        relook_last_name(g, record, before);
    }
    copy_villager_name(g, record, name, sizeof name);
    preference_text(g, record, g->likes, likes, sizeof likes);
    preference_text(g, record, g->dislikes, dislikes, sizeof dislikes);
    skills[0] = '\0';
    parents[0] = '\0';
    special[0] = '\0';
    custom[0] = '\0';
    if (detail >= 1) {
        const unsigned char *live = records != NULL
                                        && (check || memory_is_readable(records, g->record_base
                                                                        + (size_t)g->slots * g->stride))
                                        ? records : NULL;
        (void)record_custom_title(game_id, g, record, live, !check, custom, sizeof custom);
    }
    if (detail >= 1 && record_special_title(game_id, g, record) != NULL) {
        /* The villager's title (native/shared/special_title.h). */
        _snprintf_s(special, sizeof special, _TRUNCATE, "  Special villager: %s\n",
                    record_special_title(game_id, g, record));
    }
    if (detail >= 1) {
        /* The mask (native/shared/mask_line.h): a cosmetic one is known only
           for a live record (the Origins companion keys it by the record's
           place); a rebuilt copy keeps New Believers' own Heathen mask. */
        const char *mask = check || (game_id == GAME_VV5 && record[VV5_FACTION] != 0)
                               ? vv_mask_name(game_id, record) : NULL;
        if (mask != NULL) {
            size_t used = strlen(special);
            _snprintf_s(special + used, sizeof special - used, _TRUNCATE, "  Mask: %s\n", mask);
        }
    }
    if (detail >= 2) {
        skill_text(g, record, skills, sizeof skills);
        /* A caller that hands its own "Parents:" block (the Custom Island
           Event's Arrived record: the chosen parents with their looks) has
           the only one: never a second, names-only block above it. */
        if (g->parent_father_name != 0u
            && (after == NULL || strstr(after, "  Parents:\n") == NULL)
            && (record[g->parent_father_name] != 0 || record[g->parent_mother_name] != 0)) {
            char pf[MAX_NAME_BYTES], pm[MAX_NAME_BYTES];
            pf[0] = pm[0] = '\0';
            if (record[g->parent_father_name] != 0) {
                copy_name_field(record + g->parent_father_name, pf, sizeof pf,
                                g->parent_name_capacity);
            }
            if (record[g->parent_mother_name] != 0) {
                copy_name_field(record + g->parent_mother_name, pm, sizeof pm,
                                g->parent_name_capacity);
            }
            _snprintf_s(parents, sizeof parents, _TRUNCATE,
                        "  Parents:\n    Father: %s\n    Mother: %s\n",
                        pf[0] ? pf : "(none)", pm[0] ? pm : "(none)");
        }
    }
    if (detail <= 0) {
        written = _snprintf(text, sizeof(text), "%s  Name: %s\n%s%s\n",
                            heading, name, before != NULL ? before : "",
                            after != NULL ? after : "");
    } else {
        written = _snprintf(
            text, sizeof(text),
            "%s"
            "  Name: %s\n"
            "%s"
            "%s"
            "%s"
            "  Head: %d\n"
            "  Body: %d\n"
            "  Likes: %s\n"
            "  Dislikes: %s\n"
            "%s%s%s"
            "\n",
            heading, name, custom, special, before != NULL ? before : "",
            *(const int *)(record + g->head),
            *(const int *)(record + g->body),
            likes, dislikes, skills, parents, after != NULL ? after : "");
    }
    if (written < 0 || (size_t)written >= sizeof(text)) {
        return 0;
    }
    return emit_record(game_id, kind, check ? records : NULL, text);
}

#include "grave_backfill.inc"
#include "arrival_backfill.inc"

/* Whether this install records deaths: "VVFP Cause of Death.dll" ships only
   with its row, so its presence beside the executable is the test, exactly as
   the statistics publisher's is. Without it no Deaths log is created empty. */
static int deaths_recorder_present(void) {
    static int state;                 /* 0 unknown, 1 present, -1 absent */

    if (state != 0) {
        return state == 1;
    }
    state = vvfp_patcher_file_exists("VVFP Cause of Death.dll") ? 1 : -1;
    return state == 1;
}

/* Whether this install logs island events ("VVFP Island Events.dll" ships),
   so a new village gets its Island Events log at creation like the others
   (the owner: every log is made with the village). */
static int events_recorder_present(void) {
    static int state;                 /* 0 unknown, 1 present, -1 absent */

    if (state != 0) {
        return state == 1;
    }
    state = vvfp_patcher_file_exists("VVFP Island Events.dll") ? 1 : -1;
    return state == 1;
}

/* Tell "VVFP Cause of Death.dll" a child this log has recorded arrived, so
   its save-time reconciliation never reports the child as an unaccounted
   arrival.  That companion is installed from the first village frame, after
   the first village's load-time catch-up has already run its births, so it
   is loaded here, by full path beside the executable, when it is not yet:
   its export only notes the child's record.  Absent (its row off): nothing. */
static void tell_cause_of_death_birth(int game_id, const void *child_record) {
    typedef void (__stdcall *note_fn)(int, const void *);
    HMODULE module;
    note_fn note;

    if (child_record == NULL || !deaths_recorder_present()) {
        return;
    }
    module = vvfp_patcher_dll("VVFP Cause of Death.dll");
    if (module == NULL) {
        return;
    }
    note = (note_fn)GetProcAddress(module, "VvfpCauseNoteArrival");
    if (note != NULL) {
        note(game_id, child_record);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}


/* The original three argument entry point, kept so that a trampoline built
   before the father record was carried keeps working unchanged. It forwards
   with no father, which is exactly the behaviour it had. */
/* Create this village's log now, empty but headed, if it does not exist.

   The owner asked for the logs to appear as soon as a village exists rather
   than only when something happens in it. A brand-new village has had no
   conception yet, so without this its Births and Conceptions folder sits
   empty and a player cannot tell whether the feature is working or simply
   has nothing to say. The same applies after Start Over, which deliberately
   deletes the previous village's files.

   CREATE-IF-ABSENT, never a write. The logs are append-only and a record,
   once written, is never modified -- so this opens the selected file in
   append mode and writes only the header, and only when the file is empty.
   An existing log for an existing village is left exactly as it was.

   The header matters beyond presentation: Start Over identifies which files
   belong to the village being erased by that first line, so a headerless
   file could never be attributed to any village and would survive a reset
   that was meant to clear it.

   Returns 1 when the log exists afterwards, 0 if it could not be created.
   Failure is not fatal to anything: the next real record creates the file
   the same way it always did. */
static int ensure_parentage_log(int game_id, const char *village,
                                const void *records);

/* The form the population exporter calls after every save: the village just
   saved, and the villager table the roster was written from, which becomes
   the tribe records are checked against until the next save. */
__declspec(dllexport) int __stdcall EnsureParentageLogForVillage(
    int game_id,
    const char *village,
    const void *records
) {
    return ensure_parentage_log(game_id, village, records);
}

/* The village identity at a save, from Cause of Death's own hook on the save
   call, for an install without Village Statistics (see "CAUSE OF DEATH NAMES
   THE VILLAGE TOO" above).

   `save_buffer` is the block the game is saving -- the statistics hook's
   manager + 8 -- and `slot` the save slot, so the header is the one the
   statistics companion would have published, byte for byte: the same
   vv_village_name read, the same vv_village_header format. It is published
   for the records written later, and the logs are created exactly as the
   population exporter's call after a save creates them, with the villager
   table this DLL finds itself.

   With the statistics companion present this does nothing: it has already
   published this save's village and created the logs, from the same call. */
__declspec(dllexport) int __stdcall PublishVillageAtSave(
    int game_id,
    const void *save_buffer,
    int slot
) {
    char name[VV_VILLAGE_NAME_MAX];
    char header[VV_VILLAGE_NAME_MAX + 32];

    if (game_id < GAME_VV1 || game_id > GAME_VV5 || save_buffer == NULL
        || slot < 1 || slot > 5) {
        return 0;
    }
    if (statistics_publisher_present()) {
        return 0;
    }
    if (!vv_village_name(game_id, (const unsigned char *)save_buffer - 8, name)) {
        name[0] = '\0';
    }
    if (!vv_village_header(header, sizeof header, name, slot)) {
        return 0;
    }
    vv_village_publish(header);
    return ensure_parentage_log(game_id, header, villager_table(game_id));
}

/* Cause of Death's install was refused (Codex, #512 review): its save hook
   will never name a village, so records held for it would otherwise wait for
   a later record to notice -- and with none, be lost at exit. It calls this at
   the moment of refusal: with no publisher left, every held record of this
   game is written now, unlabelled and in order, exactly as a record with no
   publisher is. With the statistics companion present they keep waiting for
   its save. Returns 1 when nothing of this game is still held. */
__declspec(dllexport) int __stdcall ReleaseHeldRecords(int game_id) {
    int i;
    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    if (village_publisher_present(game_id)) {
        return 0;
    }
    flush_pending(game_id, "", 1);
    for (i = 0; i < pending_count; ++i) {
        if (pending[i].game_id == game_id) {
            return 0;
        }
    }
    return 1;
}

/* The original two-argument form, kept for a population exporter that has not
   been rebuilt. With no table it cannot vouch for the tribe, so records keep
   being held and are written here at each save instead of at once. */
__declspec(dllexport) int __stdcall EnsureParentageLog(
    int game_id,
    const char *village
) {
    return ensure_parentage_log(game_id, village, NULL);
}

static int create_extra_log(const struct game_layout *g, int family, const char *village);

static int ensure_parentage_log(
    int game_id,
    const char *village,
    const void *records
) {
    const struct game_layout *g;
    wchar_t path[MAX_LOG_PATH];
    int existing = 0;
    FILE *file;
    int had_content;

    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    g = layout_of(game_id);
    if (!layout_is_usable(g)) {
        return 0;
    }
    if (village == NULL || village[0] == '\0') {
        /* Without the header the file could not be attributed to a village,
           and an unattributable log is worse than an absent one. */
        return 0;
    }
    /* The village has just been saved, so it is known: remember the tribe it
       holds, then write any records held since before this save under its
       header. See emit_record. */
    if (records != NULL) {
        remember_saved_tribe(game_id, (const unsigned char *)records);
    }
    flush_pending(game_id, village, 1);
    /* ASK FOR THE FILE A BIRTH WOULD USE, NOT THE ONE A CONCEPTION WOULD.

       for_birth = 1 returns the village's NEWEST EXISTING file; for_birth = 0
       returns the next one to write into, which after the 256th conception is
       a file that does not exist yet. Creating that one here would leave a
       header-only rollover sitting ahead of any conception -- and
       WriteParentageBirth picks the newest matching file, so a birth from the
       pregnancy still in flight would be written into it, apart from its own
       conception. That is the defect this feature exists alongside, not one
       to reintroduce. Found in review.

       With for_birth = 1 this creates a file only when the village has no
       matching log at all, which is exactly the case the owner asked for: a
       brand-new village, or one restarted after Start Over.

       The Deaths log is created the same way, when this install records
       deaths. Its result does not decide this function's: the births log is
       the one the callers have always asked about. */
    if (deaths_recorder_present()) {
        (void)create_extra_log(g, LOG_DEATHS, village);
        (void)create_extra_log(g, LOG_UNACCOUNTED, village);
    }
    if (events_recorder_present()) {
        (void)create_extra_log(g, LOG_EVENTS, village);
    }
    if (!select_log_file(g, village, path, &existing, 1)) {
        return 0;
    }
    if (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) {
        return 1;               /* this village already has a log */
    }
    /* Measured BEFORE the open, which would create the file. */
    had_content = log_file_has_content(path);
    vv_log_words_appending((int)(g - GAME_LAYOUTS), path);
    file = _wfopen(path, L"a");
    if (file == NULL) {
        return 0;
    }
    /* Brand new means nothing on disk -- measured before the open, since
       opening creates the file. See log_file_has_content. */
    if (!had_content) {
        if (fprintf(file, "%s", village) < 0) {
            fclose(file);
            return 0;
        }
    }
    return fclose(file) == 0;
}

/* The Deaths log's counterpart of the above: created empty but headed, and
   only when the village has none. 1 when it exists afterwards. */
static int create_extra_log(const struct game_layout *g, int family, const char *village) {
    wchar_t path[MAX_LOG_PATH];
    int existing = 0;
    FILE *file;
    int had_content;

    if (!select_family_log_file(g, family, village, path, &existing, 1)) {
        return 0;
    }
    if (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) {
        return 1;               /* this village already has a log */
    }
    /* Measured BEFORE the open, which would create the file. */
    had_content = log_file_has_content(path);
    vv_log_words_appending((int)(g - GAME_LAYOUTS), path);
    file = _wfopen(path, L"a");
    if (file == NULL) {
        return 0;
    }
    /* Brand new means nothing on disk -- measured before the open, since
       opening creates the file. See log_file_has_content. */
    if (!had_content) {
        if (fprintf(file, "%s", village) < 0) {
            fclose(file);
            return 0;
        }
    }
    return fclose(file) == 0;
}

__declspec(dllexport) int __stdcall WriteParentageRecord(
    int game_id,
    const void *records_pointer,
    const void *mother_pointer
) {
    return WriteParentageRecordWithFather(
        game_id, records_pointer, mother_pointer, NULL);
}

#ifdef VV_PARENTAGE_TESTABLE
/* Accessors for native/parentage_export/select_holes_harness.c.

   select_log_file's behaviour around the holes a reset leaves cannot be
   established by reading the source: the question is what it RETURNS when
   village A's files 1 and 3 are gone and village B still owns 2 and 4. The
   harness builds that layout on disk and asks. These exist only under this
   macro, so the shipped DLL is unchanged. */
const struct game_layout *vv_parentage_layout(int game) {
    if (game < 1 || game > 5) {
        return NULL;
    }
    return layout_of(game);
}

int vv_parentage_log_folder(wchar_t *out) {
    return vv_save_subfolder_w(
        out, L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions", 64);
}
#endif
