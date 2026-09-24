/* VVFP VV1 Parentage -- true parentage for A New Home, kept in a sidecar,
   shown in the Details screen.

   The later games remember, in each villager's own record, the head and body
   values of both parents for life: The Secret City keeps the father's at
   +0xE2C/+0xE30 and the mother's at +0xE34/+0xE38 (read live from the
   owner's village: Morea, daughter of Parai and Poh, carries exactly those
   two pairs).  A New Home keeps nothing of the kind -- its records have no
   parent fields at all, and only +0x33C..+0x3D4 of a record survives a save.

   The owner asked for the same information in A New Home, and asked that it
   live in an external file rather than in spare-looking bytes of a record
   ("instead of corrupting the name buffer again").  So this companion keeps
   one entry per villager record index in

       <My Documents>\LDW\<exe basename>\vv1_parents_<slot>.dat

   bound to the village by its LIVING ROSTER, the way the later games'
   companions identify a village: the file carries, per record index, the
   name, gender and family scalar (+0x36C) of whoever held that slot when it
   was written, and it is the village's when at least one living villager
   still matches its slot.  Births and deaths change a roster, so overlap is
   the test, never an exact match; head and body are left out of the
   fingerprint because the Origins upgrades change them for a whole village
   at once.  A file left by a previous village in a reused slot (Start Over
   keeps the slot) shares nobody with the new founders and is ignored rather
   than handing the new village someone else's parents.

   NOT the "village tag" at state+0x184 the doubler sidecar binds with: that
   dword is record 0's last-update clock (file +0x188, the first dword of
   the per-record block the save keeps), which moves every minute of play
   and by the whole jump on a Time Warp.  Bound to it, this table was thrown
   away and rewritten empty within a minute of every session -- which is why
   the owner never saw a father: the stash stored at conception was gone by
   the birth.

   WHAT IS RECORDED, AND WHEN.

     Conception.  The parentage companion's trampolines already hand its
     VV1 conception handler both the mother's record and the father's -- his
     is captured at the six call sites of sub_43BBC0 because the game itself
     discards it.  That handler calls Vv1ParentageConceived, which stores the
     father's name, head and body against the MOTHER's index as a pregnancy
     stash, the same idea as the later games' copy of the father onto the
     mother.  The stash is in the file too, so a save-and-reload mid-pregnancy
     does not lose him.

     Birth, exactly.  The executable is spliced in the pregnancy tick
     (sub_42E900) right after each of its four child-creation calls --
     sub_43C350 for the first child of every birth (and the extra child of a
     golden-child mother), sub_43C840 for a twin and a triplet -- once the
     child exists and is named: the Origins companion's Vv1Born receives the
     child's record and the mother's and forwards them to Vv1ParentageBorn.
     That tick is where live play, load-time catch-up and a bought Time Warp
     all deliver, so every birth reaches the hook.  (An earlier hook sat
     inside sub_43C840 itself, which only twins go through and where the
     record it took for the mother is the sibling's: a Time Warp birth showed
     no parents, which is how it was found.)

     Birth, inferred (the fallback when the executable is not patched with
     the hook).  The delivery clears the mother's due field (+0x358,
     non-zero throughout a pregnancy) and her litter counter (+0x35C, 2 or 3
     for twins and triplets only) once all her children exist.  The Origins
     companion calls Vv1ParentageTick every frame, and the tick sees the
     delivery in the records themselves -- a mother whose due field went to
     zero this frame (or whose litter counter dropped), and the records with
     a new occupant this frame (unoccupied before, or a different name or
     +0x36C: a slot can be freed and refilled between two frames).  A child
     is NOT a copy of its mother: the game gives a first child random head
     and body and a twin its sibling's, so looks can never pair them.  What
     a child does carry is +0x36C, which sub_43C350 copies from the mother's
     +0x390 (stored against her at conception) unless that is -1.  So a lone
     delivering mother is the mother of every newborn that frame; among
     several, a newborn is hers whose +0x390 equals its +0x36C if exactly one
     does; otherwise the birth is left unknown rather than guessed.  Each
     matched child gets its entry: father from her stash, mother from her own
     record.  A newly occupied record with no delivering mother (founders,
     immigrants, a reused slot), or one that is not a newborn (a child
     becomes its own record at 2 years old; older arrivals are grown), gets
     "unknown" and is not logged: villagers not spawned by a conception have
     no parents (the owner's rule).

     The birth is written to the parentage log THE MOMENT it is seen, before
     the stash is spent and before the sidecar is rewritten -- the owner's
     rule: "the dll must immediately record its data to the parentage log
     before flushing its data".  The line goes through the parentage
     companion's own WriteParentageBirth so it lands in the same numbered,
     village-headed file as the conception records.

   AN ENTRY IS NEVER ERASED.  Villagers can be made younger (the Origins
   "Make Villagers Young Adults" and time-warp rows), and the owner asked that
   the parents come back when a villager drops under 18 again.  So an entry
   outlives the villager: death leaves it in place, and only a NEW occupant of
   the same record index starts it over -- that is a different villager, and
   giving them the previous tenant's parents would be a lie.

   THE DETAILS SCREEN.  sub_437340 draws the portrait as two cells of the
   game's own atlases -- body, then head -- through the engine's scaled draw
   (0x409410 -> 0x408AF0), and the Origins companion's mask hook runs once per
   frame right after the head.  It hands this companion the same gameobj,
   record and renderer, and for a villager under 18 with a known parent two
   small, half-faded, full-body figures are drawn in the portrait frame's
   upper corners: the father on the left facing right, the mother on the
   right facing left, each built from her or his own head and body rows the
   way the portrait is.  0x408AF0 always passes an alpha of 1.0 to the blit
   (0x403D70); this companion repeats its four steps with 0.5.  Hovering a
   figure prints "Son of <name>" / "Daughter of <name>" through the engine's
   centred text draw (0x4094C0) in the lower message bar -- where the game's
   tips appear (the owner's placement) -- and the mouse is read through the very
   SDL_GetMouseState the game feeds its own events from.

   ENCODING.  Each appearance value is stored plus one, so 0 means "unknown":
   head 0 and body 0 are real appearances in these games and can never be a
   sentinel.  Per record index: father head+1, father body+1, mother head+1,
   mother body+1, the pregnancy stash (father head+1, body+1), two spare
   bytes, then the father's, the mother's and the stashed father's names
   (28 bytes each, NUL-terminated).  A 12-byte header -- magic 'VP02', a
   reserved zero, and the slot the file was written for -- is followed by
   the roster (256 occupants of 32 bytes: name, gender, family scalar) and
   then the 256 entries of 92 bytes.  'VP01' files, bound to the clock, are
   not read: nothing in them ever survived a session.

   Everything fails closed.  No village on screen, no slot captured, a file
   from another village, a short or foreign file: the table is cleared and
   nothing is written.  File I/O happens only inside the exports, never in
   DllMain. */
#include <windows.h>
#include <shlobj.h>
#include <string.h>

#define VV1_VILLAGE_STATE_PTR  (*(unsigned char **)0x0048AEDCu)   /* what 0x41D500 returns */
#define VV1_VILLAGERS_PTR      (*(unsigned char **)0x0048B614u)   /* lazily built villager array */
#define VV1_RECORDS_OFFSET     0x0u         /* record 0 is the allocation itself: the population exporter measures record_base 0 for A New Home, and the Details hook indexes records from the same base */
#define VV1_RECORD_STRIDE      0x3D8u
#define VV1_RECORD_COUNT       256
#define VV1_SAVE_SLOT_PTR      (*(unsigned int *)0x004911F4u)     /* .vv1md MASK_SAVE_SLOT, 1..5 */
/* state+0x184 (file +0x188) is record 0's last-update clock, NOT a village identity: see the header. */

#define VV1_OCCUPIED_OFFSET    0x28u        /* u8 */
#define VV1_AGE_OFFSET         0x348u       /* i32, 20 units per villager year */
#define VV1_GENDER_OFFSET      0x350u       /* i32, 1 = male */
#define VV1_DUE_OFFSET         0x358u       /* i32: non-zero while pregnant (the Details screen's pregnancy test), cleared with +0x35C at delivery (0x42F0B2) */
#define VV1_LITTER_OFFSET      0x35Cu       /* i32: 2 or 3 for twins/triplets (0x43BC4E/0x43BC8C); a single baby leaves it 0 */
#define VV1_HEAD_OFFSET        0x360u
#define VV1_BODY_OFFSET        0x364u
#define VV1_VARIANT_OFFSET     0x36Cu       /* set at creation: a first child gets its mother's +0x390 (sub_43C350 argument 3; random when that is -1), a twin its sibling's */
#define VV1_LEGACY_OFFSET      0x390u       /* stored against the mother at conception (0x43BC10): what sub_43C350 copies into her child's +0x36C */
#define VV1_NAME_OFFSET        0x370u       /* sprintf destination at 0x43C696, bounded at 0x1C */
#define VV1_NAME_CAPACITY      0x1Cu

#define VV1_GENDER_MALE        1
#define VV1_UNITS_PER_YEAR     20
#define VV1_PARENTS_UNTIL_YEARS 18          /* shown while age < 18, again if de-aged */
#define VV1_NEWBORN_YEARS      3            /* a child becomes its own record at 2 (sub_43C350 is called with age 0x28 = 40 units); older than this when it appears, it was not just born */

/* The Details portrait, from sub_437340 and the atlas construction at
   0x43C08E..0x43C158: heads are "female_heads.png"/"male_heads.png", 7 columns
   (facing directions) x 20 rows of 40x65; bodies are "female_bodies%d%d.png"
   over a 2x2 sheet grid, 32 columns (4 directions x 8 frames) x 20 rows of the
   same cell.  The adult portrait draws body column 11 (direction 1, frame 3)
   and head column 2 (three-quarter view facing left) at scale 200. */
#define VV1_FEMALE_BODY_ATLAS  0x3DFE4u
#define VV1_MALE_BODY_ATLAS    0x3DFE8u
#define VV1_FEMALE_HEAD_ATLAS  0x3DFF4u
#define VV1_MALE_HEAD_ATLAS    0x3DFF8u
#define VV1_ATLAS_SHEET        0x4u         /* current sheet object; its first dword is the SDL_Surface */
#define VV1_ADDR_CELL_RECT     0x00409F90u  /* thiscall(atlas; col, row, rect*): selects the sheet, fills {x1,y1,x2,y2} */
#define VV1_ADDR_PLACE_SCALED  0x00407ED0u  /* thiscall(renderer; rect*, x*, y*, scale, flag*) -> al: clip, centre when scaled */
#define VV1_ADDR_BLIT          0x00403D70u  /* thiscall(renderer; surface, x, y, x1, y1, x2, y2, alpha, scale, flag) */
#define VV1_ADDR_TEXT_CENTRED  0x004094C0u  /* thiscall(wrapper; text, cx, y, colour, font) */
#define VV1_RESOURCES_PTR      (*(unsigned char **)0x0048B5F8u)   /* the game's resource singleton (0x433980): +0 the UI font the message bar uses, +4 the string table */
#define VV1_SCALE_TO_FLOAT_PTR ((const float *)0x00457454u)   /* 0.01f: scale 100 = 1.0 */
#define VV1_ADDR_SCALED_DRAW   0x00409410u  /* thiscall(wrapper; atlas, x, y, row, col, scale, flag): the portrait's own draw */
#define VV1_BLINK_OFFSET       0x3E030u     /* the portrait head's column (a random direction now and then) */
#define VV1_ANIM_OFFSET        0x20u        /* record: the child portrait's body frame is this + 11 */
#define VV1_ADULT_AGE          0x118        /* sub_437340: at 280 units (14 years) the portrait is adult-sized */

/* The picture, matched against The Secret City's Details screen (Salote,
   8, daughter of Machu): cell 40x65 figures at about 30% and 70% of the
   frame's width and a quarter of the way down, about 0.8 opaque, drawn BEHIND
   the child -- the child's body and head are drawn again over them -- and the
   hover text in the lower message bar. */
#define VV1_PARENT_SCALE       100
#define VV1_PARENT_ALPHA       0.8f         /* measured on The Secret City's parent figures (Salote, 8) */
#define VV1_CELL_W             40
#define VV1_CELL_H             65
#define VV1_FATHER_CX          102          /* both parents shifted +10 from The Secret City's 92/168 so the child sits centred between them (the owner's placement) */
#define VV1_MOTHER_CX          178          /* was 168; same +10 keeps their spacing, and the rollover uses these same centres so it moves with the figures */
#define VV1_PARENT_CY          208          /* ~a quarter down the frame's inner height (159..389) */
#define VV1_HEAD_LIFT          3            /* the adult portrait's 5px at scale 200, halved */
#define VV1_FATHER_BODY_COL    11           /* the same standing frame as the mother (owner: the frames must match) */
#define VV1_FATHER_HEAD_COL    1            /* three-quarter view facing right, toward the mother (owner) */
#define VV1_MOTHER_BODY_COL    11           /* direction 1, frame 3: facing left (the portrait's own) */
#define VV1_MOTHER_HEAD_COL    2            /* three-quarter view facing left (the portrait's own) */
#define VV1_TEXT_CX            590          /* under the middle of the skill bars (owner); the y is the message-bar label's own, built at (496, 575) in 0x423173..0x423191 */
#define VV1_TEXT_Y             575
#define VV1_TEXT_COLOUR        0xFFFFFFFFu

#define VV1_PARENTS_MAGIC      0x32305056u  /* 'V' 'P' '0' '2' */
/* The fallback father for a genuine but fatherless birth: a female villager
   an event forced to nurse, with no father at all.  VV2 and VV3 use exactly
   this placeholder -- the name "Unknown" and appearance value 0 (a real head
   and body value, stored +1 like every other).  Children SPAWNED by an
   island event or a Barrel of Babies are not delivered by a mother and get
   no parents at all, so this is only ever reached for a real delivery whose
   stash is empty. */
#define VV1_NEW_VILLAGE_STRIKES 30          /* frames of a roster sharing nobody with the table before it is another village's */
#define VV1_APPEARANCE_MAX     253          /* fits in a byte once +1 is added */

typedef struct {
    unsigned char father_head, father_body;   /* +1; 0 = unknown */
    unsigned char mother_head, mother_body;   /* +1; 0 = unknown */
    unsigned char stash_head, stash_body;     /* father, +1, while pregnant */
    unsigned char spare[2];
    char father_name[VV1_NAME_CAPACITY];
    char mother_name[VV1_NAME_CAPACITY];
    char stash_name[VV1_NAME_CAPACITY];       /* father, while pregnant */
} vv1_parent_entry;                           /* 92 bytes */

typedef struct {
    unsigned char gender;                     /* 1 male, 2 female; 0 = the slot was empty */
    unsigned char spare[3];
    int scalar;                               /* +0x36C, set once at creation */
    char name[VV1_NAME_CAPACITY];
} vv1_occupant;                               /* 36 bytes */

typedef struct {
    int child;
    int mother;                               /* -1 when no mother could be told */
} vv1_birth;

static vv1_parent_entry g_entries[VV1_RECORD_COUNT];
static vv1_occupant g_roster[VV1_RECORD_COUNT];   /* who held each slot when the table was last written or loaded */
static int g_loaded_slot;                     /* 0 = nothing loaded */
static int g_strikes;                         /* consecutive frames the live roster shared nobody with g_roster */
static unsigned char g_prev_occupied[VV1_RECORD_COUNT];
static int g_prev_litter[VV1_RECORD_COUNT];
static int g_prev_due[VV1_RECORD_COUNT];
static int g_prev_variant[VV1_RECORD_COUNT];
static char g_prev_name[VV1_RECORD_COUNT][VV1_NAME_CAPACITY];
static unsigned char g_spend[VV1_RECORD_COUNT];   /* a delivery ended this frame: spend the stash after logging */
static int g_have_prev;
static vv1_birth g_births[VV1_RECORD_COUNT];  /* births seen by the last tick */
static int g_birth_count;

/* ---- game state ------------------------------------------------------- */

static unsigned char *vv1_records(void) {
    unsigned char *base = VV1_VILLAGERS_PTR;
    return base ? base + VV1_RECORDS_OFFSET : NULL;
}

static int vv1_slot(void) {
    unsigned int slot = VV1_SAVE_SLOT_PTR;
    return (slot >= 1u && slot <= 5u) ? (int)slot : 0;
}

static unsigned char vv1_plus_one(int value);

/* Fill child c's father from mother m's pregnancy stash, or -- when she has
   none, a fatherless delivery -- from the "Unknown" 0/0 fallback.  Never
   called for a spawn, which has no delivering mother. */
static void vv1_set_father(int c, int m) {
    /* The father is the one stashed against the mother at conception.  When
       she has no stash (a delivery with no captured father) the father is
       simply left blank: only the mother is recorded, as the manifest
       promises when Write Parentage Log is off. */
    if (g_entries[m].stash_head || g_entries[m].stash_body || g_entries[m].stash_name[0]) {
        g_entries[c].father_head = g_entries[m].stash_head;
        g_entries[c].father_body = g_entries[m].stash_body;
        memcpy(g_entries[c].father_name, g_entries[m].stash_name, VV1_NAME_CAPACITY);
    }
}

static unsigned char vv1_plus_one(int value) {
    if (value < 0 || value > VV1_APPEARANCE_MAX) {
        return 0;                 /* not an appearance we can encode: unknown */
    }
    return (unsigned char)(value + 1);
}

/* Copy a record's name: at most 27 characters, always NUL-terminated, and
   never past the 28-byte buffer whatever the record holds. */
static void vv1_copy_name(const unsigned char *record, char *out) {
    unsigned int i;
    for (i = 0; i + 1 < VV1_NAME_CAPACITY; ++i) {
        char c = (char)record[VV1_NAME_OFFSET + i];
        if (c == '\0') {
            break;
        }
        out[i] = c;
    }
    out[i] = '\0';
}

/* ---- the village's identity: its living roster ------------------------ */

/* Who occupies each record right now: name, gender and the family scalar,
   the three things a villager keeps for life. */
static void vv1_take_roster(const unsigned char *records, vv1_occupant *out) {
    int i;
    memset(out, 0, sizeof(vv1_occupant) * VV1_RECORD_COUNT);
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        if (!rec[VV1_OCCUPIED_OFFSET]) {
            continue;
        }
        out[i].gender = (*(const int *)(rec + VV1_GENDER_OFFSET) == VV1_GENDER_MALE) ? 1 : 2;
        out[i].scalar = *(const int *)(rec + VV1_VARIANT_OFFSET);
        vv1_copy_name(rec, out[i].name);
    }
}

/* Does the village on screen share a villager with a recorded roster?
   1: at least one living record still matches its slot -- the village is
      the recorded one (births and deaths since are expected).
   0: villagers are on screen, the roster names some, and none match -- a
      different village (Start Over, or another save copied into the slot).
  -1: nothing to compare: the roster is empty, or nobody is on screen (the
      array is being rebuilt; not a verdict either way). */
static int vv1_roster_overlap(const unsigned char *records, const vv1_occupant *roster) {
    int i, recorded = 0, living = 0;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        char name[VV1_NAME_CAPACITY];
        if (roster[i].gender) {
            recorded = 1;
        }
        if (!rec[VV1_OCCUPIED_OFFSET]) {
            continue;
        }
        living = 1;
        if (!roster[i].gender) {
            continue;
        }
        vv1_copy_name(rec, name);
        if (roster[i].gender == ((*(const int *)(rec + VV1_GENDER_OFFSET) == VV1_GENDER_MALE) ? 1 : 2)
            && roster[i].scalar == *(const int *)(rec + VV1_VARIANT_OFFSET)
            && strncmp(roster[i].name, name, VV1_NAME_CAPACITY) == 0) {
            return 1;
        }
    }
    return (recorded && living) ? 0 : -1;
}

/* ---- the sidecar ------------------------------------------------------ */

/* MIGRATE A SIDECAR LEFT BY AN OLDER BUILD.

   The data files moved into "Virtual Villagers Fun Patcher Data" under
   names that say what they hold. A player who upgrades still has the old
   loose file beside their saves, and the new loader would not find it --
   so their masks, doublers and recorded parents would silently vanish on
   the first load even though valid state was sitting on disk.

   Called only when the NEW path is absent. Copies the legacy file into
   place and removes the original, so the migration happens once and the
   old name stops shadowing anything afterwards. A failed copy leaves both
   files untouched and the caller simply finds nothing, which is exactly
   what it would have found without this.

   MoveFileA rather than CopyFile + Delete: it is atomic within a volume,
   so an interrupted migration cannot leave a half-written new file that
   the loader would then read as corrupt state. */
/* 1 to proceed, 0 when a legacy sidecar exists and could NOT be moved.

   The result used to be discarded. A move can fail transiently -- the
   file open without delete sharing, a scanner, a lock -- and the caller
   then reported success pointing at a file that does not exist. The
   loader read nothing, an empty table was eventually committed, and the
   next write published it at the new path; from then on the destination
   existed, migration was skipped forever, and the real records were gone.
   Found in review.

   Refusing is safe: every caller treats a failed path build as "do not
   persist this time", so the state stays on disk under its old name and
   the next launch retries. Losing one save's worth of persistence is a
   far smaller harm than losing the records permanently. */
static int vv_migrate_legacy_sidecar(const char *new_path,
                                      const char *legacy_name,
                                      const char *docs,
                                      const char *base,
                                      int slot) {
    char legacy[MAX_PATH];
    if (new_path == NULL || legacy_name == NULL || docs == NULL
        || base == NULL) {
        return 1;
    }
    /* THE BOUND BELOW ASSUMES ONE DIGIT, so the slot has to be one.
       Every caller validates the slot before reaching here, but this
       function checks four pointers and a length and would be trusting
       exactly one argument it does not own -- and that argument is the one
       formatted with %d into a buffer sized for a single character. A
       negative or multi-digit slot is not a real save slot in any of the
       five games, so refusing is both safe and correct. */
    if (slot < 0 || slot > 9) {
        return 1;
    }
    if (GetFileAttributesA(new_path) != INVALID_FILE_ATTRIBUTES) {
        return 1;               /* already migrated, or never needed it */
    }
    if ((size_t)lstrlenA(docs) + (size_t)lstrlenA(base)
        + sizeof("\\LDW\\\\vv1_doublers_0.dat") > sizeof(legacy)) {
        return 1;
    }
    wsprintfA(legacy, "%s\\LDW\\%s\\%s%d.dat", docs, base, legacy_name, slot);
    if (GetFileAttributesA(legacy) == INVALID_FILE_ATTRIBUTES) {
        return 1;               /* nothing of that vintage to migrate */
    }
    if (!MoveFileA(legacy, new_path)) {
        /* The records are still there under the old name. Say so,
           so the caller does not publish over them. */
        return 0;
    }
    return 1;
}

static int vv1_parents_path(char *out, size_t n, int slot) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    char *dot;
    DWORD exelen;
    if (slot < 1 || slot > 5) {
        return 0;
    }
    if (FAILED(SHGetFolderPathA(NULL, CSIDL_PERSONAL, NULL, 0, docs))) {
        return 0;
    }
    exelen = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (exelen == 0 || exelen >= MAX_PATH) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) {
        *dot = '\0';
    }
    if ((size_t)lstrlenA(docs) + (size_t)lstrlenA(base)
            + sizeof("\\LDW\\\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Parentage Records - Save 0.dat") > n) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    /* The data files live in their own clearly named folder now, so that
       component has to exist before the file is opened. */
    wsprintfA(out, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Data", docs, base);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher Data\\Virtual Villagers 1 Parentage Records - Save %u.dat", docs, base, (unsigned int)slot);
    /* A player upgrading from a build that wrote the loose name still
       has their state under it; move it into place so it is not lost. */
    /* A legacy file that exists and will not move means the parent records
       are still under the old name. Refuse rather than hand back a
       path to a file that does not exist: an empty table published
       there would overwrite them for good. Found in review. */
    if (!vv_migrate_legacy_sidecar(out, "vv1_parents_", docs, base, slot)) {
        return 0;
    }
    return 1;
}

/* Write the table for the slot, with the roster as it stands.  Temporary-
   then-rename, so a crash mid-write can never leave a half-written file in
   place. */
static int vv1_parents_save(int slot) {
    char path[MAX_PATH];
    char tmp[MAX_PATH];
    HANDLE file;
    DWORD wrote;
    unsigned int header[3];
    const unsigned char *records = vv1_records();
    BOOL ok = TRUE;
    if (records == NULL || !vv1_parents_path(path, sizeof(path), slot)) {
        return 0;
    }
    vv1_take_roster(records, g_roster);
    if (lstrlenA(path) + sizeof(".tmp") > sizeof(tmp)) {
        return 0;
    }
    lstrcpyA(tmp, path);
    lstrcatA(tmp, ".tmp");
    file = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    header[0] = VV1_PARENTS_MAGIC;
    header[1] = 0u;
    header[2] = (unsigned int)slot;
    if (!WriteFile(file, header, sizeof(header), &wrote, NULL) || wrote != sizeof(header)) {
        ok = FALSE;
    }
    if (ok && (!WriteFile(file, g_roster, sizeof(g_roster), &wrote, NULL) || wrote != sizeof(g_roster))) {
        ok = FALSE;
    }
    if (ok && (!WriteFile(file, g_entries, sizeof(g_entries), &wrote, NULL) || wrote != sizeof(g_entries))) {
        ok = FALSE;
    }
    if (ok && !FlushFileBuffers(file)) {
        ok = FALSE;
    }
    if (!CloseHandle(file)) {
        ok = FALSE;
    }
    if (!ok) {
        DeleteFileA(tmp);
        return 0;
    }
    if (!MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp);
        return 0;
    }
    return 1;
}

/* Load the slot's table for the village on screen.  Clears first, so every
   failure -- no file, a short file, wrong magic, another slot's file, a
   roster sharing nobody with the living -- leaves no parents, which is
   exactly what a village never recorded has.  A file whose roster is empty
   has nothing to contradict and is taken. */
static int vv1_parents_load(int slot, const unsigned char *records) {
    char path[MAX_PATH];
    HANDLE file;
    DWORD got;
    unsigned int header[3];
    static vv1_occupant roster[VV1_RECORD_COUNT];
    static vv1_parent_entry buf[VV1_RECORD_COUNT];
    int i;
    int matched = 0;
    /* Nothing is cleared here.  This function is an ATTEMPT: the slot-change
       path calls it every frame while it waits for the village to appear, and
       a failed attempt must leave the table it could not replace exactly as it
       was.  Emptying the table is vv1_parents_reset's job, and the caller does
       it only when it commits to a slot with no matching file. */
    if (!vv1_parents_path(path, sizeof(path), slot)) {
        return 0;
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        /* No file for this slot.  Nothing matched, and the caller must still
           wait for the array to settle before binding a table to this slot:
           a village whose file has not been written yet looks exactly like
           one whose villagers have not loaded yet. */
        return 0;
    }
    if (ReadFile(file, header, sizeof(header), &got, NULL) && got == sizeof(header)
        && header[0] == VV1_PARENTS_MAGIC && header[2] == (unsigned int)slot
        && ReadFile(file, roster, sizeof(roster), &got, NULL) && got == sizeof(roster)
        && ReadFile(file, buf, sizeof(buf), &got, NULL) && got == sizeof(buf)) {
        for (i = 0; i < VV1_RECORD_COUNT; ++i) {
            roster[i].name[VV1_NAME_CAPACITY - 1] = '\0';
        }
        if (vv1_roster_overlap(records, roster) != 0) {
            matched = 1;
            memset(g_entries, 0, sizeof(g_entries));
            memcpy(g_roster, roster, sizeof(g_roster));
            memcpy(g_entries, buf, sizeof(buf));
            /* Names are printed and drawn: whatever the file holds, every
               name ends inside its own buffer. */
            for (i = 0; i < VV1_RECORD_COUNT; ++i) {
                g_entries[i].father_name[VV1_NAME_CAPACITY - 1] = '\0';
                g_entries[i].mother_name[VV1_NAME_CAPACITY - 1] = '\0';
                g_entries[i].stash_name[VV1_NAME_CAPACITY - 1] = '\0';
            }
        }
    }
    CloseHandle(file);
    return matched;
}

/* Empty the table: this slot holds a village we have no record of. */
static void vv1_parents_reset(void) {
    memset(g_entries, 0, sizeof(g_entries));
    memset(g_roster, 0, sizeof(g_roster));
}

/* Make sure the table on hand belongs to the village on screen.  Returns
   the slot (1..5) when a village is identified, 0 when nothing is known.
   The table follows the slot; within a slot it follows the roster: while a
   living villager still matches it, the village is the same one and the
   roster on hand is kept current (and written, so the file's own roster
   never falls behind the deaths).  A roster sharing nobody with the table
   for VV1_NEW_VILLAGE_STRIKES consecutive frames -- not one, because a load
   rebuilds the array over several -- is another village in the same slot
   (Start Over keeps the slot): the table is reloaded, which the old file
   fails for the same reason, leaving the new village's parents unknown.

   While that verdict is still pending -- strikes counting, or nobody on
   screen at all -- the answer is 0, "nothing known", NOT the slot: every
   caller then leaves the table alone.  Returning the slot here let the
   per-frame tick run the delivery inference against the previous village's
   baseline and save, and the save rebinds the roster to whoever is on
   screen -- so the very next frame overlapped, the strikes reset before the
   verdict was in, and the old table was silently mixed into the new
   village.  The inference baseline is dropped for the same reason: a
   snapshot taken before the array was rebuilt must not be compared with the
   array after it. */
/* Is anybody on screen?  An array with no live villager is one the game is
   still rebuilding, and nothing may be concluded from it -- neither that this
   is another village, nor that a sidecar does not match. */
static int vv1_anyone_living(const unsigned char *records) {
    int i;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        if (records[i * VV1_RECORD_STRIDE + VV1_OCCUPIED_OFFSET] == 1) {
            return 1;
        }
    }
    return 0;
}

static int vv1_parents_sync_core(int slot, const unsigned char *records) {
    static vv1_occupant now[VV1_RECORD_COUNT];
    if (!slot || records == NULL) {
        return 0;
    }
    if (slot != g_loaded_slot) {
        /* Wait for the TARGET village, not merely for somebody.  A slot
           changes at a load, and at that instant the array still holds the
           previous village's villagers or a half-rebuilt mixture of the two.
           Reading the sidecar against those finds no match and rejects it --
           and if the slot were marked loaded anyway it would never be retried
           once the real village appeared, so the next birth would save the
           empty table over a good file.

           So the slot is marked loaded only when the file actually matches
           the array in front of us (or there is no file, which has nothing to
           lose).  Until then this answers "nothing known" and tries again next
           frame.  The same strike window the same-slot path uses bounds that:
           a genuinely new village in this slot never matches the old file, and
           after VV1_NEW_VILLAGE_STRIKES frames it is accepted as new with an
           empty table -- which is the correct answer for it. */
        g_have_prev = 0;          /* a different village: no delivery can be inferred yet */
        if (vv1_parents_load(slot, records)) {
            g_loaded_slot = slot;   /* the file is this village's: it is loaded */
            g_strikes = 0;
            return slot;
        }
        if (++g_strikes >= VV1_NEW_VILLAGE_STRIKES) {
            /* Long enough: this slot really does hold a village the file does
               not describe.  Commit to it with an empty table. */
            vv1_parents_reset();
            g_loaded_slot = slot;
            g_strikes = 0;
            return slot;
        }
        return 0;                 /* still settling: the table is untouched */
    }
    switch (vv1_roster_overlap(records, g_roster)) {
    case 0:
        g_have_prev = 0;
        if (++g_strikes < VV1_NEW_VILLAGE_STRIKES) {
            return 0;             /* unsettled: nobody touches the table */
        }
        if (!vv1_parents_load(slot, records)) {
            vv1_parents_reset();  /* another village in this slot: start empty */
        }
        g_strikes = 0;
        break;
    case 1:
        g_strikes = 0;
        vv1_take_roster(records, now);
        if (memcmp(now, g_roster, sizeof(now)) != 0) {
            vv1_parents_save(slot);   /* takes the roster; a death or an arrival is rare */
        }
        break;
    default:
        /* No verdict.  Either nothing is recorded yet (a village with no
           table: recording may begin, so the slot is known) or nobody is
           on screen (the array is being rebuilt: nothing is known, and
           the baseline is dropped with it). */
        g_strikes = 0;
        if (vv1_anyone_living(records)) {
            return slot;
        }
        g_have_prev = 0;
        return 0;
    }
    return slot;
}

static int vv1_parents_sync(void) {
    return vv1_parents_sync_core(vv1_slot(), vv1_records());
}

/* ---- the parentage log ------------------------------------------------ */

/* WriteParentageBirth lives in the parentage companion, which owns the log:
   its file numbering, village header and roll-over.  Resolved once, from the
   executable's own directory, outside DllMain. */
typedef int (__stdcall *vv1_write_birth_t)(int game_id,
                                            const char *child_name, int child_head, int child_body,
                                            const char *mother_name, int mother_head, int mother_body,
                                            const char *father_name, int father_head, int father_body,
                                            const void *child_record);
static int g_log_state;           /* 0 = not tried, 1 = resolved, -1 = unavailable */
static vv1_write_birth_t g_write_birth;

static vv1_write_birth_t vv1_log_writer(void) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    HMODULE companion;
    if (g_log_state == 1) {
        return g_write_birth;
    }
    if (g_log_state != 0) {
        return NULL;
    }
    g_log_state = -1;
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return NULL;
    }
    slash = strrchr(path, '\\');
    if (slash == NULL
        || (size_t)(slash + 1 - path) + sizeof("VVFP Parentage Export.dll") > sizeof(path)) {
        return NULL;
    }
    lstrcpyA(slash + 1, "VVFP Parentage Export.dll");
    companion = LoadLibraryA(path);
    if (companion == NULL) {
        return NULL;              /* the log row is off: births are kept, not logged */
    }
    g_write_birth = (vv1_write_birth_t)GetProcAddress(companion, "WriteParentageBirth");
    if (g_write_birth == NULL) {
        return NULL;
    }
    g_log_state = 1;
    return g_write_birth;
}

static int vv1_decode(unsigned char encoded) {
    return encoded ? (int)encoded - 1 : -1;
}

/* One birth, straight to the log, from the live records and the entry just
   filled in.  Nothing here can fail the caller. */
static void vv1_log_birth(const unsigned char *records, const vv1_birth *birth) {
    vv1_write_birth_t write = vv1_log_writer();
    const unsigned char *child;
    const vv1_parent_entry *e;
    char child_name[VV1_NAME_CAPACITY];
    if (write == NULL || birth->child < 0 || birth->child >= VV1_RECORD_COUNT) {
        return;
    }
    child = records + (unsigned int)birth->child * VV1_RECORD_STRIDE;
    e = &g_entries[birth->child];
    vv1_copy_name(child, child_name);
    /* `child` is the live record: the exporter reads the child's own likes,
       dislikes and skills from it, which the name and appearance values
       above cannot supply. */
    write(1, child_name,
          *(const int *)(child + VV1_HEAD_OFFSET), *(const int *)(child + VV1_BODY_OFFSET),
          e->mother_name, vv1_decode(e->mother_head), vv1_decode(e->mother_body),
          e->father_name, vv1_decode(e->father_head), vv1_decode(e->father_body),
          child);
}

/* ---- the logic, over any records array (no file I/O) ------------------ */

/* Stash the father's name, head and body against the mother's index.
   Returns the mother's index, or -1 when the pointers do not describe a
   record pair. */
static int vv1_stash(const unsigned char *records, const unsigned char *mother,
                     const unsigned char *father) {
    unsigned int index;
    if (records == NULL || mother == NULL || father == NULL || mother < records) {
        return -1;
    }
    index = (unsigned int)(mother - records) / VV1_RECORD_STRIDE;
    if (index >= VV1_RECORD_COUNT || records + index * VV1_RECORD_STRIDE != mother) {
        return -1;                /* not a record boundary: not a mother we can key */
    }
    g_entries[index].stash_head = vv1_plus_one(*(const int *)(father + VV1_HEAD_OFFSET));
    g_entries[index].stash_body = vv1_plus_one(*(const int *)(father + VV1_BODY_OFFSET));
    vv1_copy_name(father, g_entries[index].stash_name);
    return (int)index;
}

static void vv1_take_baseline(const unsigned char *records) {
    int i;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        g_prev_occupied[i] = rec[VV1_OCCUPIED_OFFSET];
        g_prev_litter[i] = *(const int *)(rec + VV1_LITTER_OFFSET);
        g_prev_due[i] = *(const int *)(rec + VV1_DUE_OFFSET);
        g_prev_variant[i] = *(const int *)(rec + VV1_VARIANT_OFFSET);
        memcpy(g_prev_name[i], rec + VV1_NAME_OFFSET, VV1_NAME_CAPACITY);
    }
    memset(g_spend, 0, sizeof(g_spend));
    g_have_prev = 1;
}

/* One frame of inference over `records`.  Fills g_births with the records
   that became occupied this frame (each with its mother, or -1) and returns 1
   when an entry changed.  Marks the mothers whose delivery is over in
   g_spend; spending their stashes is vv1_spend_stashes' job, once the
   caller has logged the births. */
static int vv1_tick_over(const unsigned char *records) {
    int i;
    int changed = 0;
    int delivered[VV1_RECORD_COUNT];
    int delivered_count = 0;
    g_birth_count = 0;
    if (!g_have_prev) {
        vv1_take_baseline(records);   /* first sight: infer nothing */
        return 0;
    }
    /* Mothers who delivered this frame.  The signal is the due field
       (+0x358): non-zero for the whole pregnancy -- it is what the Details
       screen tests to show the pregnancy status -- and cleared to zero by
       the delivery routine (0x42F0B2) along with the litter counter.  The
       litter counter alone would miss every single-baby pregnancy, because
       only the twins and triplets branches ever write it.  A drop of the
       litter counter counts too, so a litter that arrived over several
       frames would still give every child the same two parents: the stash
       is only spent once both fields are zero. */
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        int litter = *(const int *)(rec + VV1_LITTER_OFFSET);
        int due = *(const int *)(rec + VV1_DUE_OFFSET);
        if (!rec[VV1_OCCUPIED_OFFSET]) {
            continue;
        }
        if ((g_prev_due[i] != 0 && due == 0)
            || (g_prev_litter[i] > 0 && litter >= 0 && litter < g_prev_litter[i])) {
            delivered[delivered_count++] = i;
        }
    }
    /* Records with a NEW occupant this frame.  "Became occupied" is not
       enough: a death and a new villager in the same slot can both happen
       between two frames, leaving the slot occupied in both snapshots.  So
       a record is new when it is occupied and either was not, or its name
       or look-alike variant changed -- neither changes during a life, and
       a new villager (born or founder) is given both afresh. */
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        if (rec[VV1_OCCUPIED_OFFSET]
            && (!g_prev_occupied[i]
                || g_prev_variant[i] != *(const int *)(rec + VV1_VARIANT_OFFSET)
                || memcmp(g_prev_name[i], rec + VV1_NAME_OFFSET, VV1_NAME_CAPACITY) != 0)) {
            int variant = *(const int *)(rec + VV1_VARIANT_OFFSET);
            int age = *(const int *)(rec + VV1_AGE_OFFSET);
            int mother = -1;
            int matches = 0;
            int k;
            /* Which delivering mother?  The child is NOT a copy of her: the
               game gives a first child random looks (sub_43C350) and a twin
               its sibling's (sub_43C840), so looks can never tell.  What the
               child does carry is its +0x36C, which sub_43C350 copies from
               the mother's +0x390 -- stored against her at conception --
               unless that is -1.  So a lone delivering mother is the mother;
               among several, the child is hers whose +0x390 equals its
               +0x36C if exactly one does; otherwise the birth is left
               unknown rather than guessed.  Only a NEWBORN can match at all:
               a child becomes its own record at 2 years old, so the owner's
               rule that villagers not spawned by a conception have no parents
               keeps a founder or immigrant who happens to appear during a
               delivery from being taken for her child -- they arrive grown,
               a baby does not. */
            if (age < VV1_NEWBORN_YEARS * VV1_UNITS_PER_YEAR) {
                if (delivered_count == 1) {
                    mother = delivered[0];
                    matches = 1;
                } else {
                    for (k = 0; k < delivered_count; ++k) {
                        const unsigned char *mrec = records + (unsigned int)delivered[k] * VV1_RECORD_STRIDE;
                        int legacy = *(const int *)(mrec + VV1_LEGACY_OFFSET);
                        if (legacy != -1 && legacy == variant) {
                            mother = delivered[k];
                            ++matches;
                        }
                    }
                }
            }
            /* A reused slot starts unknown: this is a different villager, and
               the previous tenant's parents are not theirs.  This is the ONLY
               way an entry is ever cleared. */
            memset(&g_entries[i], 0, sizeof(g_entries[i]));
            if (matches == 1) {
                const unsigned char *mrec = records + (unsigned int)mother * VV1_RECORD_STRIDE;
                vv1_set_father(i, mother);
                g_entries[i].mother_head = vv1_plus_one(*(const int *)(mrec + VV1_HEAD_OFFSET));
                g_entries[i].mother_body = vv1_plus_one(*(const int *)(mrec + VV1_BODY_OFFSET));
                vv1_copy_name(mrec, g_entries[i].mother_name);
            } else {
                mother = -1;
            }
            g_births[g_birth_count].child = i;
            g_births[g_birth_count].mother = mother;
            ++g_birth_count;
            changed = 1;
        }
    }
    for (i = 0; i < delivered_count; ++i) {
        const unsigned char *mrec = records + (unsigned int)delivered[i] * VV1_RECORD_STRIDE;
        if (*(const int *)(mrec + VV1_LITTER_OFFSET) == 0 && *(const int *)(mrec + VV1_DUE_OFFSET) == 0) {
            g_spend[delivered[i]] = 1;          /* the delivery is over, until the baseline is retaken */
        }
    }
    return changed;
}

/* A delivery is over (due and litter both zero again): the stash has been
   handed to the children.  Returns 1 when a stash was spent.  Runs after the
   births are logged, and retakes the baseline for the next frame. */
static int vv1_spend_stashes(const unsigned char *records) {
    int i;
    int changed = 0;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        if (g_spend[i]) {
            if (g_entries[i].stash_head || g_entries[i].stash_body || g_entries[i].stash_name[0]) {
                g_entries[i].stash_head = 0;
                g_entries[i].stash_body = 0;
                memset(g_entries[i].stash_name, 0, VV1_NAME_CAPACITY);
                changed = 1;
            }
        }
    }
    vv1_take_baseline(records);
    return changed;
}

/* One whole frame: infer, log, spend, in that order.  Returns 1 when the
   table changed and the sidecar should be rewritten. */
static int vv1_frame(const unsigned char *records, int log) {
    int had_prev = g_have_prev;
    int changed = vv1_tick_over(records);
    int b;
    if (!had_prev) {
        return 0;                 /* the baseline was just taken; nothing to spend */
    }
    if (log) {
        for (b = 0; b < g_birth_count; ++b) {
            if (g_births[b].mother >= 0) {   /* an arrival is not a birth: nothing to log */
                vv1_log_birth(records, &g_births[b]);
            }
        }
    }
    if (vv1_spend_stashes(records)) {
        changed = 1;
    }
    return changed;
}

/* The exact birth, from the executable's hook in the pregnancy tick
   sub_42E900, right after the child-creation call (through the Origins
   companion's Vv1Born): the newborn's record, already named, and its
   mother's.  Fills the child's entry -- father from her stash,
   mother from her record -- and updates the frame snapshot for that slot
   so the per-frame inference does not treat the child as an unknown new
   occupant afterwards.  The stash stays until the delivery ends (the tick
   spends it when her due and litter fields are zero again), so twins and
   triplets, born one call each, all get the same father.  Returns the
   child's index, or -1 when the pointers are not two distinct records of
   the array. */
static int vv1_born(const unsigned char *records, const unsigned char *child,
                    const unsigned char *mother) {
    unsigned int c, m;
    if (records == NULL || child == NULL || mother == NULL || child < records || mother < records) {
        return -1;
    }
    c = (unsigned int)(child - records) / VV1_RECORD_STRIDE;
    m = (unsigned int)(mother - records) / VV1_RECORD_STRIDE;
    if (c >= VV1_RECORD_COUNT || m >= VV1_RECORD_COUNT || c == m
        || records + c * VV1_RECORD_STRIDE != child || records + m * VV1_RECORD_STRIDE != mother) {
        return -1;
    }
    memset(&g_entries[c], 0, sizeof(g_entries[c]));
    vv1_set_father((int)c, (int)m);
    g_entries[c].mother_head = vv1_plus_one(*(const int *)(mother + VV1_HEAD_OFFSET));
    g_entries[c].mother_body = vv1_plus_one(*(const int *)(mother + VV1_BODY_OFFSET));
    vv1_copy_name(mother, g_entries[c].mother_name);
    if (g_have_prev) {
        g_prev_occupied[c] = child[VV1_OCCUPIED_OFFSET];
        g_prev_variant[c] = *(const int *)(child + VV1_VARIANT_OFFSET);
        memcpy(g_prev_name[c], child + VV1_NAME_OFFSET, VV1_NAME_CAPACITY);
    }
    return (int)c;
}

static void vv1_entry_out(int index, int *out) {
    out[0] = vv1_decode(g_entries[index].father_head);
    out[1] = vv1_decode(g_entries[index].father_body);
    out[2] = vv1_decode(g_entries[index].mother_head);
    out[3] = vv1_decode(g_entries[index].mother_body);
}

/* ---- the Details screen ----------------------------------------------- */

typedef unsigned int (__cdecl *sdl_get_mouse_state_t)(int *x, int *y);
static sdl_get_mouse_state_t g_mouse;
static int g_mouse_state;         /* 0 = not tried, 1 = resolved, -1 = unavailable */

static int vv1_mouse(int *x, int *y) {
    if (g_mouse_state == 0) {
        HMODULE sdl = GetModuleHandleA("SDL2.dll");   /* the game's own, already loaded */
        g_mouse = sdl ? (sdl_get_mouse_state_t)GetProcAddress(sdl, "SDL_GetMouseState") : NULL;
        g_mouse_state = g_mouse ? 1 : -1;
    }
    if (g_mouse_state != 1) {
        return 0;
    }
    g_mouse(x, y);
    return 1;
}

/* The engine's scaled cell draw (0x408AF0) step by step, with our own alpha.
   `renderer` is what the draw wrapper's first dword points at -- the ECX the
   inner routines receive.  (x, y) is the top-left of the UNSCALED cell; with
   the flag set, a scaled image is centred on that cell's centre, exactly as
   the portrait is placed. */
static void vv1_draw_cell(void *renderer, unsigned char *atlas, int x, int y,
                          int row, int col, int scale, float alpha) {
    int rect[4] = { 0, 0, 0, 0 };
    int flag = 1;
    int px = x, py = y;
    int visible = 0;
    int x1, y1, x2, y2;
    unsigned int alpha_bits, scale_bits;
    float scale_f;
    void *surface;
    void *sheet;
    int *prect = rect, *ppx = &px, *ppy = &py, *pflag = &flag;
    unsigned int f_cell = VV1_ADDR_CELL_RECT;
    unsigned int f_place = VV1_ADDR_PLACE_SCALED;
    unsigned int f_blit = VV1_ADDR_BLIT;
    if (renderer == NULL || atlas == NULL) {
        return;
    }
    scale_f = (float)scale * *VV1_SCALE_TO_FLOAT_PTR;
    memcpy(&alpha_bits, &alpha, 4);
    memcpy(&scale_bits, &scale_f, 4);
    __asm {
        mov  ecx, atlas
        push prect
        push row
        push col
        call f_cell            /* thiscall; ret 0xC */
        mov  ecx, renderer
        push pflag
        push scale
        push ppy
        push ppx
        push prect
        call f_place           /* thiscall; ret 0x14 */
        movzx eax, al
        mov  visible, eax
    }
    if (!visible) {
        return;
    }
    sheet = *(void **)(atlas + VV1_ATLAS_SHEET);
    if (sheet == NULL) {
        return;
    }
    surface = *(void **)sheet;
    if (surface == NULL) {
        return;
    }
    x1 = rect[0]; y1 = rect[1]; x2 = rect[2]; y2 = rect[3];
    __asm {
        mov  ecx, renderer
        push flag
        push scale_bits
        push alpha_bits
        push y2
        push x2
        push y1
        push x1
        push py
        push px
        push surface
        call f_blit            /* thiscall; ret 0x28 */
    }
}

/* The font the lower message bar's own label was built with (0x423173: the
   first dword of the resource singleton), so the text looks like the tips
   that appear there.  NULL falls back to the renderer's default. */
static void *vv1_message_bar_font(void) {
    unsigned char *resources = VV1_RESOURCES_PTR;
    return resources ? *(void **)resources : NULL;
}

static void vv1_draw_text_centred(void *wrapper, const char *text, int centre_x, int y) {
    void *font = vv1_message_bar_font();
    /* No local here may be named like a register: in inline asm "push cx" pushes
       the 16-bit CX register, misaligning the stack -- that was a crash. */
    unsigned int f_text = VV1_ADDR_TEXT_CENTRED;
    unsigned int colour = VV1_TEXT_COLOUR;
    if (wrapper == NULL || text == NULL) {
        return;
    }
    __asm {
        mov  ecx, wrapper
        push font              /* the message bar's font, or 0 for the default */
        push colour
        push y
        push centre_x
        push text
        call f_text            /* thiscall; ret 0x14 */
    }
}

/* The stock portrait draw (0x409410) with the stock seven arguments, so the
   child can be drawn again over the parents exactly as sub_437340 drew them. */
static void vv1_replay_draw(void *wrapper, void *atlas, int x, int y, int row, int col, int scale, int flag) {
    unsigned int f_draw = VV1_ADDR_SCALED_DRAW;
    if (wrapper == NULL || atlas == NULL) {
        return;
    }
    __asm {
        mov  ecx, wrapper
        push flag
        push scale
        push col
        push row
        push y
        push x
        push atlas
        call f_draw            /* thiscall; ret 0x1C */
    }
}

/* sub_437340's body draw, recomputed from the record: children grow with
   age (scale 100 + 2*(age/7), frame +0x20 + 11, y 253), adults are fixed
   (scale 200, frame 11, y 233); x 120, flag 1; the atlas by gender. */
static void vv1_replay_body(void *wrapper, unsigned char *gameobj, const unsigned char *rec) {
    int age = *(const int *)(rec + VV1_AGE_OFFSET);
    int male = *(const int *)(rec + VV1_GENDER_OFFSET) == VV1_GENDER_MALE;
    void *atlas = *(void **)(gameobj + (male ? VV1_MALE_BODY_ATLAS : VV1_FEMALE_BODY_ATLAS));
    int row = *(const int *)(rec + VV1_BODY_OFFSET);
    if (age < VV1_ADULT_AGE) {
        vv1_replay_draw(wrapper, atlas, 0x78, 0xFD, row, *(const int *)(rec + VV1_ANIM_OFFSET) + 0xB, 2 * (age / 7) + 100, 1);
    } else {
        vv1_replay_draw(wrapper, atlas, 0x78, 0xE9, row, 0xB, 0xC8, 1);
    }
}

/* One parent figure: body cell then head cell, faded, at its spot. */
static void vv1_draw_parent(void *renderer, unsigned char *gameobj, int male,
                            int head_row, int body_row, int cx) {
    unsigned char *body_atlas = *(unsigned char **)(gameobj + (male ? VV1_MALE_BODY_ATLAS : VV1_FEMALE_BODY_ATLAS));
    unsigned char *head_atlas = *(unsigned char **)(gameobj + (male ? VV1_MALE_HEAD_ATLAS : VV1_FEMALE_HEAD_ATLAS));
    int x = cx - VV1_CELL_W / 2;
    int y = VV1_PARENT_CY - VV1_CELL_H / 2;
    vv1_draw_cell(renderer, body_atlas, x, y, body_row,
                  male ? VV1_FATHER_BODY_COL : VV1_MOTHER_BODY_COL, VV1_PARENT_SCALE, VV1_PARENT_ALPHA);
    vv1_draw_cell(renderer, head_atlas, x, y - VV1_HEAD_LIFT, head_row,
                  male ? VV1_FATHER_HEAD_COL : VV1_MOTHER_HEAD_COL, VV1_PARENT_SCALE, VV1_PARENT_ALPHA);
}

static int vv1_over(int mx, int my, int cx) {
    return mx >= cx - VV1_CELL_W / 2 && mx < cx + VV1_CELL_W / 2
        && my >= VV1_PARENT_CY - VV1_CELL_H / 2 && my < VV1_PARENT_CY + VV1_CELL_H / 2;
}

/* ---- exports (the game) ----------------------------------------------- */

/* From the parentage companion's VV1 conception handler: the live records
   array, the mother's record and the father's record the trampolines
   captured.  Returns 1 when stored and persisted. */
__declspec(dllexport) int __stdcall Vv1ParentageConceived(const void *records_pointer,
                                                          const void *mother_pointer,
                                                          const void *father_pointer) {
    const unsigned char *records = (const unsigned char *)records_pointer;
    int slot;
    if (records == NULL || records != vv1_records()) {
        return 0;                 /* a records array that is not the live one */
    }
    slot = vv1_parents_sync();
    if (!slot) {
        return 0;
    }
    if (vv1_stash(records, (const unsigned char *)mother_pointer,
                  (const unsigned char *)father_pointer) < 0) {
        return 0;
    }
    return vv1_parents_save(slot);
}

/* From the executable's birth hook, through the Origins companion's Vv1Born:
   the child (named) and the mother.  Records the parents, writes the birth
   to the parentage log at once, then persists.  Returns 1 when recorded. */
__declspec(dllexport) int __stdcall Vv1ParentageBorn(void *child_pointer, void *mother_pointer) {
    const unsigned char *records = vv1_records();
    int slot;
    int c;
    vv1_birth birth;
    if (records == NULL) {
        return 0;
    }
    slot = vv1_parents_sync();
    if (!slot) {
        return 0;
    }
    c = vv1_born(records, (const unsigned char *)child_pointer, (const unsigned char *)mother_pointer);
    if (c < 0) {
        return 0;
    }
    birth.child = c;
    birth.mother = (int)(((const unsigned char *)mother_pointer - records) / VV1_RECORD_STRIDE);
    vv1_log_birth(records, &birth);   /* the log first, before anything is flushed */
    vv1_parents_save(slot);
    return 1;
}

/* Per frame, from the Origins companion.  Returns 1 when a village is on
   screen and the table corresponds to it, 0 when nothing is known. */
__declspec(dllexport) int __stdcall Vv1ParentageTick(void) {
    int slot = vv1_parents_sync();
    if (!slot) {
        return 0;
    }
    if (vv1_frame(vv1_records(), 1)) {
        vv1_parents_save(slot);
    }
    return 1;
}

/* From the Origins companion's Details portrait hook, once per frame after
   the head is drawn: gameobj is the villager manager, record the villager on
   screen, draw_wrapper the ECX 0x409410 received, args its seven untouched
   arguments (replayed over the parents).  Returns 1 when a figure was drawn. */
__declspec(dllexport) int __stdcall Vv1ParentageDrawPortrait(void *gameobj, void *record,
                                                             void *draw_wrapper, const int *args) {
    unsigned char *g = (unsigned char *)gameobj;
    unsigned char *rec = (unsigned char *)record;
    size_t delta;
    int index;
    const vv1_parent_entry *e;
    void *renderer;
    int father_known, mother_known;
    int male_child;
    int mx = -1, my = -1;
    char text[16 + VV1_NAME_CAPACITY];
    if (g == NULL || rec == NULL || rec < g || draw_wrapper == NULL) {
        return 0;
    }
    delta = (size_t)(rec - g);
    if (delta % VV1_RECORD_STRIDE != 0) {
        return 0;
    }
    index = (int)(delta / VV1_RECORD_STRIDE);
    if (index < 0 || index >= VV1_RECORD_COUNT) {
        return 0;
    }
    if (!vv1_parents_sync()) {
        return 0;
    }
    if (*(const int *)(rec + VV1_AGE_OFFSET) >= VV1_PARENTS_UNTIL_YEARS * VV1_UNITS_PER_YEAR) {
        return 0;                 /* grown up: the parents step out of the frame */
    }
    e = &g_entries[index];
    father_known = e->father_head != 0 && e->father_body != 0;
    mother_known = e->mother_head != 0 && e->mother_body != 0;
    if (!father_known && !mother_known) {
        return 0;
    }
    renderer = *(void **)draw_wrapper;
    if (renderer == NULL) {
        return 0;
    }
    if (father_known) {
        vv1_draw_parent(renderer, g, 1, (int)e->father_head - 1, (int)e->father_body - 1, VV1_FATHER_CX);
    }
    if (mother_known) {
        vv1_draw_parent(renderer, g, 0, (int)e->mother_head - 1, (int)e->mother_body - 1, VV1_MOTHER_CX);
    }
    /* The parents stand behind the child, as in the later games: the stock
       body and head are drawn again over them with the stock arguments (the
       head's are the seven the hook handed over untouched). */
    vv1_replay_body(draw_wrapper, g, rec);
    if (args != NULL) {
        vv1_replay_draw(draw_wrapper, (void *)args[0], args[1], args[2], args[3], args[4], args[5], args[6]);
    }
    male_child = *(const int *)(rec + VV1_GENDER_OFFSET) == VV1_GENDER_MALE;
    if (vv1_mouse(&mx, &my)) {
#ifdef VV1_PROBE
        wsprintfA(text, "mouse %d,%d", mx, my);
        vv1_draw_text_centred(draw_wrapper, text, VV1_TEXT_CX, VV1_TEXT_Y - 22);
#endif
        const char *parent = NULL;
        if (father_known && vv1_over(mx, my, VV1_FATHER_CX) && e->father_name[0] != '\0') {
            parent = e->father_name;
        } else if (mother_known && vv1_over(mx, my, VV1_MOTHER_CX) && e->mother_name[0] != '\0') {
            parent = e->mother_name;
        }
        if (parent != NULL) {
            wsprintfA(text, "%s of %s", male_child ? "Son" : "Daughter", parent);
            vv1_draw_text_centred(draw_wrapper, text, VV1_TEXT_CX, VV1_TEXT_Y);
        }
    }
    return 1;
}

/* Read access for the exporters: out[4] = father head, father body, mother
   head, mother body, each -1 when unknown.  Returns 1 when a village is
   identified and index is in range. */
__declspec(dllexport) int __stdcall Vv1ParentageQuery(int index, int *out) {
    if (out == NULL || index < 0 || index >= VV1_RECORD_COUNT || !vv1_parents_sync()) {
        return 0;
    }
    vv1_entry_out(index, out);
    return 1;
}

/* The parents' names, each into a caller buffer of `capacity` bytes (empty
   when unknown).  Returns 1 when a village is identified and index is in
   range. */
__declspec(dllexport) int __stdcall Vv1ParentageQueryNames(int index, char *father, char *mother,
                                                           int capacity) {
    if (father == NULL || mother == NULL || capacity < 1
        || index < 0 || index >= VV1_RECORD_COUNT || !vv1_parents_sync()) {
        return 0;
    }
    lstrcpynA(father, g_entries[index].father_name, capacity);
    lstrcpynA(mother, g_entries[index].mother_name, capacity);
    return 1;
}

/* ---- exports (test seams: same logic, caller-supplied records, no files) */

__declspec(dllexport) int __stdcall Vv1ParentageProbeReset(void) {
    memset(g_entries, 0, sizeof(g_entries));
    g_have_prev = 0;
    g_birth_count = 0;
    return 1;
}

__declspec(dllexport) int __stdcall Vv1ParentageProbeConceive(const void *records,
                                                              const void *mother,
                                                              const void *father) {
    return vv1_stash((const unsigned char *)records, (const unsigned char *)mother,
                     (const unsigned char *)father);
}

/* The exact birth without the log or the file. */
__declspec(dllexport) int __stdcall Vv1ParentageProbeBorn(const void *records, const void *child,
                                                          const void *mother) {
    return vv1_born((const unsigned char *)records, (const unsigned char *)child,
                    (const unsigned char *)mother);
}

/* A whole frame without the log: infer, spend the stashes. */
__declspec(dllexport) int __stdcall Vv1ParentageProbeTick(const void *records) {
    if (records == NULL) {
        return -1;
    }
    return vv1_frame((const unsigned char *)records, 0);
}

__declspec(dllexport) int __stdcall Vv1ParentageProbeEntry(int index, int *out) {
    if (out == NULL || index < 0 || index >= VV1_RECORD_COUNT) {
        return 0;
    }
    vv1_entry_out(index, out);
    return 1;
}

__declspec(dllexport) int __stdcall Vv1ParentageProbeNames(int index, char *father, char *mother,
                                                           int capacity) {
    if (father == NULL || mother == NULL || capacity < 1 || index < 0 || index >= VV1_RECORD_COUNT) {
        return 0;
    }
    lstrcpynA(father, g_entries[index].father_name, capacity);
    lstrcpynA(mother, g_entries[index].mother_name, capacity);
    return 1;
}

/* The births the last probe tick saw: out[2*i] = child index, out[2*i+1] =
   mother index or -1.  Returns the count. */
__declspec(dllexport) int __stdcall Vv1ParentageProbeBirths(int *out, int capacity) {
    int i;
    if (out == NULL) {
        return g_birth_count;
    }
    for (i = 0; i < g_birth_count && 2 * i + 1 < capacity; ++i) {
        out[2 * i] = g_births[i].child;
        out[2 * i + 1] = g_births[i].mother;
    }
    return g_birth_count;
}

/* The village identity, for the harness: the roster fingerprint of a records
   array (256 occupants into `out`), and the overlap verdict between a records
   array and a roster (1 same village, 0 another, -1 nothing to compare). */
__declspec(dllexport) int __stdcall Vv1ParentageProbeRoster(const void *records, void *out) {
    if (records == NULL || out == NULL) {
        return 0;
    }
    vv1_take_roster((const unsigned char *)records, (vv1_occupant *)out);
    return (int)sizeof(vv1_occupant);
}

/* The sync over a caller-supplied slot and array, so the harness can drive
   the strike window without the game's globals. */
__declspec(dllexport) int __stdcall Vv1ParentageProbeSync(int slot, const void *records) {
    return vv1_parents_sync_core(slot, (const unsigned char *)records);
}

/* Bind the table to the array's occupants in memory -- what a save does
   minus the file -- so the harness can set up "the village this table
   belongs to" without touching disk. */
__declspec(dllexport) int __stdcall Vv1ParentageProbeBind(const void *records) {
    vv1_take_roster((const unsigned char *)records, g_roster);
    return 1;
}

__declspec(dllexport) int __stdcall Vv1ParentageProbeOverlap(const void *records, const void *roster) {
    if (records == NULL || roster == NULL) {
        return -2;
    }
    return vv1_roster_overlap((const unsigned char *)records, (const vv1_occupant *)roster);
}

/* The sidecar entry size and header, so a test can check the file format
   without reading the source. */
__declspec(dllexport) int __stdcall Vv1ParentageProbeLayout(int *entry_bytes, int *entries,
                                                            unsigned int *magic) {
    if (entry_bytes) *entry_bytes = (int)sizeof(vv1_parent_entry);
    if (entries) *entries = VV1_RECORD_COUNT;
    if (magic) *magic = VV1_PARENTS_MAGIC;
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
