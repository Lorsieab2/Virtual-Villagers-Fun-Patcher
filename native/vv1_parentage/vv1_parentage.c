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

   bound to the village the way the doubler sidecar is: by the creation-time
   tag the game stamps into every villager record (state+0x184 in the village
   state that 0x41D500 returns, cached at 0x0048AEDC).  A file left by a
   previous village in a reused slot fails the tag and is ignored rather than
   handing the new village someone else's parents.

   WHAT IS RECORDED, AND WHEN.

     Conception.  The parentage companion's trampolines already hand its
     VV1 conception handler both the mother's record and the father's -- his
     is captured at the six call sites of sub_43BBC0 because the game itself
     discards it.  That handler calls Vv1ParentageConceived, which stores the
     father's name, head and body against the MOTHER's index as a pregnancy
     stash, the same idea as the later games' copy of the father onto the
     mother.  The stash is in the file too, so a save-and-reload mid-pregnancy
     does not lose him.

     Birth.  A New Home creates a child in sub_43C840, called from the
     delivery path once per baby with the mother's index; it copies her head,
     body and look-alike variant (+0x36C) onto the child and clears her litter
     counter (+0x35C, set to 1..3 at conception, 0 after delivery).  No
     executable bytes are spent on a birth hook: the Origins companion calls
     Vv1ParentageTick every frame, and the tick sees the delivery in the
     records themselves -- a mother whose litter counter dropped to zero this
     frame, and the records that became occupied this frame whose head, body
     and +0x36C equal hers.  Each such child gets its entry: father from her
     stash, mother from her own record.  A newly occupied record with no
     delivering mother (founders, immigrants, a reused slot), or one that is
     not a newborn, gets "unknown" and is not logged: villagers not spawned
     by a conception have no parents (the owner's rule).

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
   (28 bytes each, NUL-terminated).  256 entries of 92 bytes follow a 12-byte
   header: magic 'VP01', the village tag, and the slot the file was written
   for.

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
#define VV1_VILLAGE_TAG_OFFSET 0x184u       /* creation-time tag, record 0 inside the state */

#define VV1_OCCUPIED_OFFSET    0x28u        /* u8 */
#define VV1_AGE_OFFSET         0x348u       /* i32, 20 units per villager year */
#define VV1_GENDER_OFFSET      0x350u       /* i32, 1 = male */
#define VV1_LITTER_OFFSET      0x35Cu       /* i32: 1..3 while pregnant, 0 otherwise */
#define VV1_HEAD_OFFSET        0x360u
#define VV1_BODY_OFFSET        0x364u
#define VV1_VARIANT_OFFSET     0x36Cu       /* copied mother -> child at birth */
#define VV1_NAME_OFFSET        0x370u       /* sprintf destination at 0x43C696, bounded at 0x1C */
#define VV1_NAME_CAPACITY      0x1Cu

#define VV1_GENDER_MALE        1
#define VV1_UNITS_PER_YEAR     20
#define VV1_PARENTS_UNTIL_YEARS 18          /* shown while age < 18, again if de-aged */
#define VV1_NEWBORN_YEARS      2            /* a record older than this when it appears was not just born */

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
#define VV1_FATHER_CX          92           /* ~30% across the frame's inner width (37..224), as in The Secret City */
#define VV1_MOTHER_CX          168          /* ~70% across */
#define VV1_PARENT_CY          208          /* ~a quarter down the frame's inner height (159..389) */
#define VV1_HEAD_LIFT          3            /* the adult portrait's 5px at scale 200, halved */
#define VV1_FATHER_BODY_COL    11           /* the same standing frame as the mother (owner: the frames must match) */
#define VV1_FATHER_HEAD_COL    1            /* three-quarter view facing right, toward the mother (owner) */
#define VV1_MOTHER_BODY_COL    11           /* direction 1, frame 3: facing left (the portrait's own) */
#define VV1_MOTHER_HEAD_COL    2            /* three-quarter view facing left (the portrait's own) */
#define VV1_TEXT_CX            496          /* the message-bar label's own spot: built at (496, 575) in 0x423173..0x423191 */
#define VV1_TEXT_Y             575
#define VV1_TEXT_COLOUR        0xFFFFFFFFu

#define VV1_PARENTS_MAGIC      0x31305056u  /* 'V' 'P' '0' '1' */
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
    int child;
    int mother;                               /* -1 when no mother could be told */
} vv1_birth;

static vv1_parent_entry g_entries[VV1_RECORD_COUNT];
static int g_loaded_slot;                     /* 0 = nothing loaded */
static unsigned int g_loaded_tag;
static unsigned char g_prev_occupied[VV1_RECORD_COUNT];
static int g_prev_litter[VV1_RECORD_COUNT];
static int g_have_prev;
static vv1_birth g_births[VV1_RECORD_COUNT];  /* births seen by the last tick */
static int g_birth_count;

/* ---- game state ------------------------------------------------------- */

static unsigned char *vv1_records(void) {
    unsigned char *base = VV1_VILLAGERS_PTR;
    return base ? base + VV1_RECORDS_OFFSET : NULL;
}

static int vv1_village_tag(unsigned int *out) {
    unsigned char *state = VV1_VILLAGE_STATE_PTR;
    if (state == NULL) {
        return 0;
    }
    *out = *(unsigned int *)(state + VV1_VILLAGE_TAG_OFFSET);
    return *out != 0u;
}

static int vv1_slot(void) {
    unsigned int slot = VV1_SAVE_SLOT_PTR;
    return (slot >= 1u && slot <= 5u) ? (int)slot : 0;
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

/* ---- the sidecar ------------------------------------------------------ */

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
    if ((size_t)lstrlenA(docs) + (size_t)lstrlenA(base) + 5 + 32 + 1 > n) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\vv1_parents_%u.dat", docs, base, (unsigned int)slot);
    return 1;
}

/* Write the table for (slot, tag).  Temporary-then-rename, so a crash mid-
   write can never leave a half-written file in place. */
static int vv1_parents_save(int slot, unsigned int tag) {
    char path[MAX_PATH];
    char tmp[MAX_PATH];
    HANDLE file;
    DWORD wrote;
    unsigned int header[3];
    BOOL ok = TRUE;
    if (!vv1_parents_path(path, sizeof(path), slot)) {
        return 0;
    }
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
    header[1] = tag;
    header[2] = (unsigned int)slot;
    if (!WriteFile(file, header, sizeof(header), &wrote, NULL) || wrote != sizeof(header)) {
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

/* Load the table for (slot, tag).  Clears first, so every failure -- no file,
   a short file, wrong magic, another village's tag, another slot's file --
   leaves no parents, which is exactly what a village never recorded has. */
static void vv1_parents_load(int slot, unsigned int tag) {
    char path[MAX_PATH];
    HANDLE file;
    DWORD got;
    unsigned int header[3];
    vv1_parent_entry buf[VV1_RECORD_COUNT];
    int i;
    memset(g_entries, 0, sizeof(g_entries));
    if (!vv1_parents_path(path, sizeof(path), slot)) {
        return;
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (ReadFile(file, header, sizeof(header), &got, NULL) && got == sizeof(header)
        && header[0] == VV1_PARENTS_MAGIC && header[1] == tag && header[2] == (unsigned int)slot
        && ReadFile(file, buf, sizeof(buf), &got, NULL) && got == sizeof(buf)) {
        memcpy(g_entries, buf, sizeof(buf));
        /* Names are printed and drawn: whatever the file holds, every name
           ends inside its own buffer. */
        for (i = 0; i < VV1_RECORD_COUNT; ++i) {
            g_entries[i].father_name[VV1_NAME_CAPACITY - 1] = '\0';
            g_entries[i].mother_name[VV1_NAME_CAPACITY - 1] = '\0';
            g_entries[i].stash_name[VV1_NAME_CAPACITY - 1] = '\0';
        }
    }
    CloseHandle(file);
}

/* Make sure the table on hand belongs to the village on screen.  Returns
   the slot (1..5) when a village is identified, 0 when nothing is known. */
static int vv1_parents_sync(unsigned int *tag_out) {
    int slot = vv1_slot();
    unsigned int tag;
    if (!slot || !vv1_village_tag(&tag) || vv1_records() == NULL) {
        return 0;
    }
    if (slot != g_loaded_slot || tag != g_loaded_tag) {
        vv1_parents_load(slot, tag);
        g_loaded_slot = slot;
        g_loaded_tag = tag;
        g_have_prev = 0;          /* a different village: no delivery can be inferred yet */
    }
    *tag_out = tag;
    return slot;
}

/* ---- the parentage log ------------------------------------------------ */

/* WriteParentageBirth lives in the parentage companion, which owns the log:
   its file numbering, village header and roll-over.  Resolved once, from the
   executable's own directory, outside DllMain. */
typedef int (__stdcall *vv1_write_birth_t)(int game_id,
                                            const char *child_name, int child_head, int child_body,
                                            const char *mother_name, int mother_head, int mother_body,
                                            const char *father_name, int father_head, int father_body);
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
    write(1, child_name,
          *(const int *)(child + VV1_HEAD_OFFSET), *(const int *)(child + VV1_BODY_OFFSET),
          e->mother_name, vv1_decode(e->mother_head), vv1_decode(e->mother_body),
          e->father_name, vv1_decode(e->father_head), vv1_decode(e->father_body));
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
    }
    g_have_prev = 1;
}

/* One frame of inference over `records`.  Fills g_births with the records
   that became occupied this frame (each with its mother, or -1) and returns 1
   when an entry changed.  Marks the mothers who delivered by setting their
   remembered litter to -1; spending their stashes is vv1_spend_stashes' job,
   once the caller has logged the births. */
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
    /* Mothers whose litter counter went to zero this frame. */
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        int litter = *(const int *)(rec + VV1_LITTER_OFFSET);
        if (g_prev_litter[i] > 0 && litter == 0 && rec[VV1_OCCUPIED_OFFSET]) {
            delivered[delivered_count++] = i;
        }
    }
    /* Records that became occupied this frame. */
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        const unsigned char *rec = records + (unsigned int)i * VV1_RECORD_STRIDE;
        if (rec[VV1_OCCUPIED_OFFSET] && !g_prev_occupied[i]) {
            int head = *(const int *)(rec + VV1_HEAD_OFFSET);
            int body = *(const int *)(rec + VV1_BODY_OFFSET);
            int variant = *(const int *)(rec + VV1_VARIANT_OFFSET);
            int age = *(const int *)(rec + VV1_AGE_OFFSET);
            int mother = -1;
            int matches = 0;
            int k;
            /* The child is a copy of its mother at this instant: head, body
               and the look-alike variant all came from her record in
               sub_43C840.  Among the mothers who delivered this frame,
               exactly one should match; if none or several do, the birth is
               left unknown rather than guessed.  Only a NEWBORN can match at
               all: the owner's rule is that villagers not spawned by a
               conception have no parents, so a founder or immigrant who
               happens to appear during a delivery with the same look is never
               taken for her child -- they arrive grown, a baby does not. */
            for (k = 0; age < VV1_NEWBORN_YEARS * VV1_UNITS_PER_YEAR && k < delivered_count; ++k) {
                const unsigned char *mrec = records + (unsigned int)delivered[k] * VV1_RECORD_STRIDE;
                if (*(const int *)(mrec + VV1_HEAD_OFFSET) == head
                    && *(const int *)(mrec + VV1_BODY_OFFSET) == body
                    && *(const int *)(mrec + VV1_VARIANT_OFFSET) == variant) {
                    mother = delivered[k];
                    ++matches;
                }
            }
            /* A reused slot starts unknown: this is a different villager, and
               the previous tenant's parents are not theirs.  This is the ONLY
               way an entry is ever cleared. */
            memset(&g_entries[i], 0, sizeof(g_entries[i]));
            if (matches == 1) {
                const unsigned char *mrec = records + (unsigned int)mother * VV1_RECORD_STRIDE;
                g_entries[i].father_head = g_entries[mother].stash_head;
                g_entries[i].father_body = g_entries[mother].stash_body;
                memcpy(g_entries[i].father_name, g_entries[mother].stash_name, VV1_NAME_CAPACITY);
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
        g_prev_litter[delivered[i]] = -1;   /* "delivered this frame", until the baseline is retaken */
    }
    return changed;
}

/* A delivery is over: the stash has been handed to the children.  Returns 1
   when a stash was spent.  Runs after the births are logged, and retakes the
   baseline for the next frame. */
static int vv1_spend_stashes(const unsigned char *records) {
    int i;
    int changed = 0;
    for (i = 0; i < VV1_RECORD_COUNT; ++i) {
        if (g_prev_litter[i] == -1) {
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
    unsigned int tag;
    int slot;
    if (records == NULL || records != vv1_records()) {
        return 0;                 /* a records array that is not the live one */
    }
    slot = vv1_parents_sync(&tag);
    if (!slot) {
        return 0;
    }
    if (vv1_stash(records, (const unsigned char *)mother_pointer,
                  (const unsigned char *)father_pointer) < 0) {
        return 0;
    }
    return vv1_parents_save(slot, tag);
}

/* Per frame, from the Origins companion.  Returns 1 when a village is on
   screen and the table corresponds to it, 0 when nothing is known. */
__declspec(dllexport) int __stdcall Vv1ParentageTick(void) {
    unsigned int tag;
    int slot = vv1_parents_sync(&tag);
    if (!slot) {
        return 0;
    }
    if (vv1_frame(vv1_records(), 1)) {
        vv1_parents_save(slot, tag);
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
    unsigned int tag;
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
    if (!vv1_parents_sync(&tag)) {
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
    unsigned int tag;
    if (out == NULL || index < 0 || index >= VV1_RECORD_COUNT || !vv1_parents_sync(&tag)) {
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
    unsigned int tag;
    if (father == NULL || mother == NULL || capacity < 1
        || index < 0 || index >= VV1_RECORD_COUNT || !vv1_parents_sync(&tag)) {
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
