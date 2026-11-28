/* VVFP Skin Tones -- each villager's skin tone, kept and handed down (the owner, 2026-11-06 and 2026-11-26:
   "implement the skin tone mod in all 5 games!! with inheritance and mixing"; "babies conceived from two
   parents inherit skin tones same as head rules").  All five games.

   THE DATA.  It keeps every villager's tone in the patcher's own per-save file, gives a tone to whoever
   has none, and answers the other companions.  Nothing is ever written into a villager record.

   THE DRAWS (The Secret City, The Tree of Life and New Believers so far; "the draws" below).  Where the
   game is about to draw a villager's head or body from a sheet, a look at that villager's tone comes
   first, and the sheet drawn from is that tone's copy of it -- a picture file in the game's own Images
   folder, made from the player's own art.  Any sheet that is not there is the game's own.  In A New Home
   and The Lost Children VvfpSkinToneDrawn says 0 and every villager is drawn with the game's own art.

   THE FILE.  "Virtual Villagers Fun Patcher\Save <S>\Data\Skin Tones\Skin Tones - Save <S>.dat", the Head
   Looks' store (native/vvfp_head_look/head_look_store.inc) with its own magic 'VST2' and a second byte per
   villager: the same following of each villager by identity through loads, packs, renames and sex changes,
   the same refusal to write over another village's file, the same atomic write.  The second byte is the
   villager's BIRTH TONE (the owner, 2026-11-26: a "reset to birth tone" option): the tone they were born
   with or first given, never changed by Change Appearance, which VvfpSkinToneReset puts back.  The first
   layout, 'VST1' (one byte per villager), is still read: its villagers' birth tones are the tones they
   had.  Start Over must delete the file (native/shared/save_reset.c lists the per-save folders).

   WHO GETS WHICH TONE (skin_tone_rules.h has the rule itself).  Whenever the village on screen is known,
   every held villager with no tone is given one, the oldest first, so parents come before their children:
     * a villager whose record names a parent (the later four games keep both parents' names): the tone
       rolled for the baby at the conception and kept on the mother (VvfpSkinToneConceived: the head rule
       on both parents' tones as they were then, so a father who died or left before the birth still
       counts, and the held baby and the newborn are the same tone).  With none kept (a pregnancy from
       before the patch, a conception nobody told this DLL of): the head rule now, on the mother's tone
       and that of the villager with the father's name.  A second or third baby of the same pregnancy
       (same parents, same age, given in the same pass) copies the first, as its head does;
     * anyone else -- a founder, an arrival, a villager whose parents are nobody in the village: any tone,
       each as likely; or, with a preferred skin tone chosen in the patcher ("VVFP Skin Tones.txt" beside the
       companions, read at start), that tone for 4 in 5 of them and one of the others for the rest.
   A New Home's records name no parents, so there a newborn's tone is given by VvfpSkinToneBorn (called
   where the birth is logged) before this pass can see it; without that call a newborn there would be
   random like an arrival.
   Every roll is this DLL's own generator, never the game's rand(): the game's own sequence of births and
   events is not disturbed.  NOTHING DEPENDS ON SEX.

   CHOSEN.  Change Appearance keeps a tone with VvfpSkinToneSet / SetMany; each change is an "Appearance
   changed" record with "Old skin tone" and "New skin tone" lines (native/shared/look_change_log.h). */
#include <windows.h>
#include <string.h>
#include "../shared/sidecar_io.h"
#include "../shared/save_folder.h"
#include "../shared/per_save_data.h"
#include "../shared/mask_follow.h"
#include "../shared/foreign_sidecar.h"
#include "../shared/game_save_slot.h"
#include "../shared/install_sites.h"
#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/multiplier_choice.h"
#include "skin_tone_rules.h"

#define HL_MAX 256

/* The record fields a tone is kept by and handed down by: the same offsets as the Head Look's LAYOUT
   (native/vvfp_head_look/vvfp_head_look.c). */
typedef struct {
    unsigned int stride;
    unsigned int present;
    unsigned int name, name_bytes;
    unsigned int sex;
    unsigned int father, mother;    /* the parents' names, 0x19 bytes each (0: none in this game) */
    unsigned int family;            /* A New Home's family number (0: none) */
    unsigned int age;
    unsigned int carrying;          /* not 0 while pregnant or nursing (0: not known in this game) */
} st_layout;

static const st_layout LAYOUT[6] = {
    { 0 },
    { 0x3D8u,  0x28u,   0x370u,  0x1Cu, 0x350u,  0u,      0u,      0x36Cu, 0x348u,  0u },
    { 0xE48Cu, 0x30u,   0x564u,  0x18u, 0x538u,  0x57Du,  0x596u,  0u,     0x530u,  0u },
    { 0x1F8Cu, 0xF10u,  0xDD4u,  0x19u, 0xDC8u,  0xDF8u,  0xE11u,  0u,     0xDC4u,  0u },
    { 0x2E3Cu, 0x1CC4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1B8Cu, 0x1C4Cu },
    { 0x2F44u, 0x1CD4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1B8Cu, 0x1C4Cu },
};
#define ST_PARENT_BYTES 0x19u

static int g_game;
static unsigned int g_records;
static int g_count;
static int g_table_read;

#ifdef VVFP_SKIN_TONE_HARNESS
/* The harness gives the store a village of its own (skin_tone_harness.c). */
static unsigned char *g_harness_records;
static int g_harness_count, g_harness_slot;
static void hl_locate(void) {
}
static int hl_slots(void) {
    return g_harness_count < HL_MAX ? g_harness_count : HL_MAX;
}
static const unsigned char *hl_record(int i) {
    if (g_harness_records == NULL || i < 0 || i >= g_harness_count) {
        return NULL;
    }
    return g_harness_records + (size_t)i * LAYOUT[g_game].stride;
}
static int hl_slot_now(void) {
    return g_harness_slot;
}
#else
static void hl_locate(void) {
    const unsigned char *image = (const unsigned char *)(UINT_PTR)0x400000u;
    unsigned int rva = 0, slots = 0;
    if (g_table_read) {
        return;
    }
    switch (g_game) {
    case 1:
        g_records = *(const unsigned int *)(UINT_PTR)0x48B614u;
        g_count = 256;
        return;
    case 2:
        g_records = *(const unsigned int *)(UINT_PTR)0x499F24u;
        g_count = 256;
        return;
    case 3:
        vv3_villager_table(image, &rva, &slots);
        g_records = 0x400000u + rva + 0x14u;
        break;
    case 4:
        vv4_villager_table(image, &rva, &slots);
        g_records = 0x400000u + rva + 0x44u;
        break;
    case 5:
        vv5_villager_table(image, &rva, &slots);
        g_records = 0x400000u + rva + 0x48u;
        break;
    default:
        g_records = 0;
        g_count = 0;
        return;
    }
    g_count = (int)slots;
    g_table_read = 1;
}

static int hl_slots(void) {
    hl_locate();
    return g_count < HL_MAX ? g_count : HL_MAX;
}

static const unsigned char *hl_record(int i) {
    hl_locate();
    if (g_records == 0 || i < 0 || i >= g_count) {
        return NULL;
    }
    return (const unsigned char *)(UINT_PTR)(g_records + (unsigned int)i * LAYOUT[g_game].stride);
}

static int hl_slot_now(void) {
    return vv_game_save_slot(g_game);
}
#endif

static int hl_game(void) {
    return g_game;
}

static int hl_present(const unsigned char *r) {
    const unsigned char held = r[LAYOUT[g_game].present];
    return g_game == 1 ? held == 1 : held != 0;
}

static unsigned int hl_text(unsigned int h, const unsigned char *text, unsigned int capacity) {
    unsigned int k;
    for (k = 0; k < capacity && text[k]; ++k) {
        h = (h ^ text[k]) * 16777619u;
    }
    return h;
}

static unsigned int hl_mix_dword(unsigned int h, const unsigned char *at) {
    int k;
    for (k = 0; k < 4; ++k) {
        h = (h ^ at[k]) * 16777619u;
    }
    return h;
}

static unsigned int hl_stable(const unsigned char *r) {
    const st_layout *l = &LAYOUT[g_game];
    unsigned int h = hl_mix_dword(2166136261u, r + l->sex);
    if (l->family != 0) {
        h = hl_mix_dword(h, r + l->family);
    } else {
        h = hl_text(h, r + l->father, ST_PARENT_BYTES);
        h = (h ^ 0xFEu) * 16777619u;
        h = hl_text(h, r + l->mother, ST_PARENT_BYTES);
        h = (h ^ 0xFDu) * 16777619u;
    }
    return h ? h : 1u;
}

static unsigned int hl_identity(const unsigned char *r) {
    const st_layout *l = &LAYOUT[g_game];
    unsigned int h = hl_text(2166136261u, r + l->name, l->name_bytes);
    h = (h ^ 0xFFu) * 16777619u;
    h = (h ^ hl_stable(r)) * 16777619u;
    return h ? h : 1u;
}

#define HL_MAGIC 0x32545356u            /* 'VST2' */
#define HL_SECOND                       /* g_second: each villager's birth tone, 0 none, 1..COUNT */
#define HL_MAGIC_ONE_BYTE 0x31545356u   /* 'VST1': a tone and no birth tone; still read */
#define HL_SECOND_OF(v) ((((v) & 0x0Fu) >= 1u && ((v) & 0x0Fu) <= (unsigned int)VVFP_SKIN_TONE_COUNT) ? ((v) & 0x0Fu) : 0u)
#define HL_MAGIC_V1 0u
#define HL_READS_V1 0
#define HL_LOOK_MAX 255                 /* both four-bit halves of the kept byte */
#define HL_KIND "Skin Tones"
#define HL_FILE_NAME "Skin Tones - Save 0.dat"
#define HL_FILE_SLOT_AT (sizeof "Skin Tones - Save " - 1)
#include "../vvfp_head_look/head_look_store.inc"
#include "../shared/look_change_log.h"

#define ST_TONE(v) ((int)((v) & 0x0Fu))
#define ST_BABY(v) ((int)(((v) >> 4) & 0x0Fu))     /* a carrying mother's baby's tone */

/* ---- this DLL's own rolls ------------------------------------------------------------------------- */

static unsigned int g_seed;

static unsigned int st_roll(void) {
    if (g_seed == 0) {
        LARGE_INTEGER now;
        QueryPerformanceCounter(&now);
        g_seed = (unsigned int)now.LowPart ^ GetTickCount() ^ 0x9E3779B9u;
        if (g_seed == 0) {
            g_seed = 0x2545F491u;
        }
    }
    g_seed ^= g_seed << 13;
    g_seed ^= g_seed >> 17;
    g_seed ^= g_seed << 5;
    return g_seed >> 8;
}

static int g_preferred;      /* the preferred skin tone: 0 none, 1..COUNT (VVFP_SKIN_TONE_CHOICE_FILE) */

/* A randomly made villager's tone (never a baby's). */
static int st_random_tone(void) {
    unsigned int r100 = st_roll() % 100u;
    return vvfp_skin_tone_random(g_preferred, r100, st_roll());
}

/* ---- who gets which tone -------------------------------------------------------------------------- */

static int st_drawn_tone(unsigned char value) {
    int tone = ST_TONE(value);
    return tone >= 1 && tone <= VVFP_SKIN_TONE_COUNT ? tone : 0;
}

static int st_names_parent(const unsigned char *r, unsigned int at) {
    return at != 0 && r[at] != 0;
}

/* The record of the held villager called `name` (a parent's name field), or -1.  A name two villagers
   share is never guessed at. */
static int st_find_named(const unsigned char *name) {
    const st_layout *l = &LAYOUT[g_game];
    int i, found = -1, slots = hl_slots();
    for (i = 0; i < slots; ++i) {
        const unsigned char *r = hl_record(i);
        if (r != NULL && hl_present(r) && g_roster[i] != 0
            && lstrcmpA((const char *)(r + l->name), (const char *)name) == 0) {
            if (found >= 0) {
                return -1;
            }
            found = i;
        }
    }
    return found;
}

static int st_same_parents(const unsigned char *a, const unsigned char *b) {
    const st_layout *l = &LAYOUT[g_game];
    return lstrcmpA((const char *)(a + l->father), (const char *)(b + l->father)) == 0
           && lstrcmpA((const char *)(a + l->mother), (const char *)(b + l->mother)) == 0
           && *(const int *)(a + l->age) == *(const int *)(b + l->age);
}

static DWORD g_give_tick;
static int g_give_tried;

/* Every held villager with no tone gets one (the rules at the top).  1 when the table is the village's
   (whether or not anyone was given a tone).  Throttled like the store's own look at the village. */
static int st_give(void) {
    static unsigned char was[HL_MAX], was_second[HL_MAX];
    static unsigned int was_id[HL_MAX];
    static int order[HL_MAX], given[HL_MAX], spent[HL_MAX];
    const st_layout *l = &LAYOUT[g_game];
    DWORD now = GetTickCount();
    int i, j, n = 0, ngiven = 0, nspent = 0, slots;
    if (!hl_sync()) {
        return 0;
    }
    if (g_give_tried && (DWORD)(now - g_give_tick) < HL_SYNC_MS) {
        return 1;
    }
    g_give_tick = now;
    g_give_tried = 1;
    slots = hl_slots();
    for (i = 0; i < slots; ++i) {
        const unsigned char *r = hl_record(i);
        if (r != NULL && hl_present(r) && g_roster[i] != 0 && ST_TONE(g_look[i]) == 0) {
            order[n++] = i;
        }
    }
    if (n == 0) {
        return 1;
    }
    for (i = 1; i < n; ++i) {                   /* the oldest first: parents before their children */
        int at = order[i];
        int age = *(const int *)(hl_record(at) + l->age);
        for (j = i; j > 0 && *(const int *)(hl_record(order[j - 1]) + l->age) < age; --j) {
            order[j] = order[j - 1];
        }
        order[j] = at;
    }
    memcpy(was, g_look, sizeof was);
    memcpy(was_id, g_look_id, sizeof was_id);
    memcpy(was_second, g_second, sizeof was_second);
    for (i = 0; i < n; ++i) {
        const unsigned char *r = hl_record(order[i]);
        int tone = 0;
        if (st_names_parent(r, l->father) || st_names_parent(r, l->mother)) {
            int mother = st_names_parent(r, l->mother) ? st_find_named(r + l->mother) : -1;
            int father = st_names_parent(r, l->father) ? st_find_named(r + l->father) : -1;
            int mother_tone = mother >= 0 ? st_drawn_tone(g_look[mother]) : 0;
            int father_tone = father >= 0 ? st_drawn_tone(g_look[father]) : 0;
            int promised = mother >= 0 ? ST_BABY(g_look[mother]) : 0;
            for (j = 0; j < ngiven && tone == 0; ++j) {         /* a twin or triplet copies the first */
                if (st_same_parents(r, hl_record(given[j]))) {
                    tone = ST_TONE(g_look[given[j]]);
                }
            }
            /* The tone rolled at the conception.  (Everyone already in the village has a tone before any
               conception is told, so a villager with none who names a carrying mother is her newborn --
               also when the birth happened in a catch-up and the baby is no longer age 0.)  The promise
               is then spent: cleared below, after any twin has copied the first. */
            if (tone == 0 && promised >= 1 && promised <= VVFP_SKIN_TONE_COUNT) {
                tone = promised;
                spent[nspent++] = mother;
            }
            if (tone == 0 && (mother_tone != 0 || father_tone != 0)) {
                tone = vvfp_skin_tone_inherit(father_tone, mother_tone, st_roll() % 100u, st_roll() % 3u, st_roll());
            }
        }
        if (tone == 0) {
            tone = st_random_tone();
        }
        g_look[order[i]] = (unsigned char)((g_look[order[i]] & 0xF0u) | (unsigned int)tone);
        g_look_id[order[i]] = g_roster[order[i]];
        g_second[order[i]] = (unsigned char)tone;           /* the tone they were born with or first given */
        given[ngiven++] = order[i];
    }
    for (i = 0; i < nspent; ++i) {
        g_look[spent[i]] &= 0x0Fu;
    }
    if (!hl_publish()) {
        memcpy(g_look, was, sizeof was);        /* memory never says what the file does not */
        memcpy(g_look_id, was_id, sizeof was_id);
        memcpy(g_second, was_second, sizeof was_second);
        return 1;
    }
    return 1;
}

/* The kept byte of the villager in `record`, after everyone has a tone; 0 when the village is not known. */
static unsigned char st_value(const unsigned char *record) {
    int i;
    if (record == NULL || !st_give()) {
        return 0;
    }
    i = hl_index(record);
    if (i < 0 || g_roster[i] == 0 || g_roster[i] != hl_identity(record)) {
        return 0;
    }
    return g_look[i];
}

static const char *const ST_NAMES[VVFP_SKIN_TONE_COUNT] = VVFP_SKIN_TONE_NAMES;

/* A tone as the windows and the logs write it: "Copper", or "Game's own" for the game's own art.  `out`
   holds at least 40 characters. */
static void st_name(char *out, int tone) {
    lstrcpyA(out, tone >= 1 && tone <= VVFP_SKIN_TONE_COUNT ? ST_NAMES[tone - 1] : VVFP_SKIN_TONE_GAMES_OWN_NAME);
}

static void st_log_change(const unsigned char *record, int was, int tone) {
    char a[40], b[40];
    if (record == NULL || st_drawn_tone((unsigned char)was) == st_drawn_tone((unsigned char)tone)) {
        return;
    }
    st_name(a, st_drawn_tone((unsigned char)was));
    st_name(b, st_drawn_tone((unsigned char)tone));
    (void)vv_look_log(g_game, record, VVFP_SKIN_TONE_WORD, a, b);
}

static int st_tone_ok(int tone) {
    return (tone >= 1 && tone <= VVFP_SKIN_TONE_COUNT) || tone == VVFP_SKIN_TONE_GAMES_OWN;
}

/* THE HELD BABY'S TONE: the tone of the baby the villager in `carrier` holds -- the one rolled at the
   conception and kept on the carrier (VvfpSkinToneConceived).  With none kept while the carrier is pregnant
   or nursing (a pregnancy from before the patch, a conception nobody told this DLL of) it is chosen the
   first time the baby is seen: the head rule on the carrier's tone (the other parent not known counts as
   the carrier), or, when the carrier has no tone of their own (the game's own chosen), a randomly made
   villager's tone.  It is kept like a conception's, so the newborn is given exactly it (st_give) and a
   twin or triplet held with it is the same.  The carrier may be of either sex.  1..COUNT, or 0: the game's
   own art.  A keep that cannot be written is not tried again for a while (the draw asks every frame). */
static int st_held(const unsigned char *carrier) {
    static DWORD failed_at[HL_MAX];
    static unsigned char failed[HL_MAX];
    const st_layout *l = &LAYOUT[g_game];
    unsigned char value;
    int i, tone, own;
    if (carrier == NULL) {
        return 0;
    }
    value = st_value(carrier);                  /* everyone has a tone first */
    i = hl_index(carrier);
    if (i < 0 || g_roster[i] == 0 || g_roster[i] != hl_identity(carrier)) {
        return 0;
    }
    tone = ST_BABY(value);
    if (tone >= 1 && tone <= VVFP_SKIN_TONE_COUNT) {
        return tone;
    }
    if (l->carrying == 0 || *(const int *)(carrier + l->carrying) == 0) {
        return 0;
    }
    if (failed[i] && (DWORD)(GetTickCount() - failed_at[i]) < HL_SYNC_MS) {
        return 0;
    }
    own = st_drawn_tone(value);
    tone = own != 0 ? vvfp_skin_tone_inherit(0, own, st_roll() % 100u, st_roll() % 3u, st_roll()) : st_random_tone();
    if (!hl_set(carrier, (int)((value & 0x0Fu) | ((unsigned int)tone << 4)))) {
        failed[i] = 1;
        failed_at[i] = GetTickCount();
        return 0;
    }
    failed[i] = 0;
    return tone;
}

/* ---- the draws -----------------------------------------------------------------------------------

   A TONE'S SHEET is "vvfp_skin_<NN>_<the game's own name>" in the game's Images folder, NN the tone 01..10
   (vvfp_skin_05_male_heads00.png, ..._bigbodies.png, ..._female_heads_old.png): the same grid, built by
   the game's own sheet constructor from the game's own description of the sheet.  It is loaded the first
   time a villager of that tone is drawn from it, and only when every file of it is there; otherwise the
   game's own sheet is drawn, for that sheet only.

   THE TREE OF LIFE AND NEW BELIEVERS.  The draw asks one of two routines for the sheet: the BODY fetcher
   (pose, sex, body) and the HEAD fetcher (head turn, sex, head).  Each looks the sheet's number up in the
   animation table, gets the sheet from the game's sprite registry (one object per sheet for the whole
   game) and writes it through a pointer the caller gave; the caller then draws from it.  So the one place
   a villager's own sheet can be chosen is right after the fetch.  THE SITES: the `call` of a fetcher in
   the village draw, the Villager Details big figure and the small figure of each game (three head
   fetches, three body fetches).  Each `call` (5 bytes) is pointed at a stub that calls the game's own
   fetcher with the same arguments and then puts the tone's sheet in the place of the one fetched.

   THE SECRET CITY keeps its eight villager sheets in the village manager and hands one to a draw as its
   first argument.  THE SITES: the entry of the village's draw 0x42E5E0 (called for a villager's body at
   0x460C53 and head at 0x460C7F), and the entry of the thunk 0x409FB0 that the Villager Details portrait
   and an island event's figure call (and the village's draw itself, after it).  At each the sheet is
   the first argument on the stack, and it is changed there before the game's own code goes on.

   THE VILLAGER.  The record is in ESI at every site (the Head Look's compares in the same routines read
   it there); anything else in ESI -- the renderer, when the village's draw reaches the thunk -- is no
   villager and changes nothing.  A sheet that is not one of the eight villager sheets (a mask, the
   skeleton) is never changed.  The memorial list's figures (the dead: no record) and the Villager Details
   parents' small figures (drawn from the child's record) keep the game's own art.

   THE HELD BABY (The Tree of Life and New Believers).  A carrier's baby is cell 3 of carrying.png, drawn in
   the baby's own tone (st_held) from that tone's copy of the sheet, "vvfp_skin_<NN>_carrying.png"; nothing
   else on the sheet is ever drawn from the copy.  THE SITES: (1) the entry of the village's carried-item draw
   (VV4 0x466770, VV5 0x4701C0; thiscall on the sprite manager, the record its first argument, the item at
   the record's carry field: 3 is the baby).  While it runs, the manager's carrying sheet (+0x24) is the
   tone's copy, put back when it returns -- the entry, not its draw calls, because "VVFP Cloth Sacks.dll"
   owns The Tree of Life's first draw call 0x4667B4.  (2) The Villager Details big and small figures' draws
   of cell 3 (the baby and any twin or triplet: three calls each, ESI the record), whose sheet is their
   first argument, changed there.  A sheet that is not the game's own carrying sheet is never changed. */
#ifndef VVFP_SKIN_TONE_HARNESS

#define ST_SHEETS 8

typedef struct {
    unsigned int alloc;                 /* the game's operator new */
    unsigned int grid_ctor;             /* thiscall (name, extension, files across, down, columns, rows), ret 0x18 */
    unsigned int one_ctor;              /* thiscall (file name, columns, rows), ret 0xC */
    unsigned int sheets;                /* the first of the eight sheet descriptions, 0x30 bytes each */
    unsigned int slots;                 /* where the game keeps the eight loaded sheets (0: in each description, +0x2C) */
    unsigned char slot_at[ST_SHEETS];   /* ... each sheet's dword there, as an offset */
    unsigned int object_bytes;          /* what is allocated for a sheet */
    int clip;                           /* 1: the clip bounds at +0x60 are opened (see st_toned_sheet) */
    unsigned int head_fetch, body_fetch;
    unsigned int head_sites[3], body_sites[3];
    unsigned int carry_desc;            /* carrying.png's description (0: no held baby is toned) */
    unsigned int carry_entry;           /* the village's carried-item draw: thiscall(record, ...) */
    unsigned int carry_item;            /* the record's carried item: -1 none, 3 the baby */
    unsigned int detail_draw;           /* the Details figures' draw: thiscall(sheet, x, y, cell, scale, 0) */
    unsigned int detail_sites[6];
} st_draws;

#define ST_CARRY ST_SHEETS              /* the toned sheets' number for carrying.png */
#define ST_BABY_CELL 3
#define ST_MANAGER_CARRYING 0x24u       /* the sprite manager's carrying sheet (VV4 0x465F70 loads id 0x100 there) */

/* A sheet description (the game's own: The Secret City's resource table 0x4A95A0, read by its cache 0x42E750;
   the registries VV4 0x44C9B0 / VV5 0x44F870): +4 the name, +8 columns, +0xC rows, +0x10 the extension,
   +0x14 files across (0: one file, named in full), +0x18 files down. */
static const st_draws VV3_DRAWS = {
    0x46EC93u, 0x40AF90u, 0x40AF10u, 0x4AAE60u,
    /* ids 0x84..0x8B in the manager 0x59E110 (the loader 0x45C730): the women's heads, old heads, bodies,
       actions, then the men's. */
    0x59E110u + 0x127C20u, { 0x10, 0x18, 0x00, 0x08, 0x14, 0x1C, 0x04, 0x0C },
    0x34u, 0, 0u, 0u, { 0u, 0u, 0u }, { 0u, 0u, 0u },
};
static const st_draws VV4_DRAWS = {
    0x470C5Cu, 0x40ABA0u, 0x40AB10u, 0x4C3B88u, 0u, { 0 }, 0x70u, 1, 0x44EA00u, 0x44E960u,
    { 0x467F36u, 0x45F6BAu, 0x45F99Cu }, { 0x4681C7u, 0x45F616u, 0x45F917u },
    0x4C37C8u, 0x466770u, 0x1CDCu, 0x409AD0u,
    { 0x45F75Eu, 0x45F787u, 0x45F7AFu, 0x45FA4Eu, 0x45FA73u, 0x45FA99u },
};
static const st_draws VV5_DRAWS = {
    0x47BBDCu, 0x40B0A0u, 0x40B010u, 0x4D1DA8u, 0u, { 0 }, 0x70u, 1, 0x451DA0u, 0x451D00u,
    { 0x47233Bu, 0x466DB7u, 0x4670CCu }, { 0x472683u, 0x466D17u, 0x467047u },
    0x4D1A78u, 0x4701C0u, 0x1D0Cu, 0x409D00u,
    { 0x466E81u, 0x466EAAu, 0x466ED3u, 0x46717Eu, 0x4671A3u, 0x4671C9u },
};
#define VV3_VILLAGE_DRAW 0x42E5E0u      /* fild dword [esp+8]; push ebx  (5 bytes), then 0x42E5E5 */
#define VV3_DRAW_THUNK 0x409FB0u        /* mov ecx, [ecx]; jmp 0x4093A0  (7 bytes) */
#define VV3_DRAW_ENTRY 0x4093A0u

static const st_draws *g_draws;
static void *g_toned[VVFP_SKIN_TONE_COUNT + 1][ST_SHEETS + 1];
static unsigned char g_toned_tried[VVFP_SKIN_TONE_COUNT + 1][ST_SHEETS + 1];
static char g_toned_name[VVFP_SKIN_TONE_COUNT + 1][ST_SHEETS + 1][64];

/* The game's description of sheet `k`: one of the eight villager sheets, or ST_CARRY. */
static const unsigned int *st_sheet_desc(int k) {
    if (k == ST_CARRY) {
        return (const unsigned int *)(UINT_PTR)g_draws->carry_desc;
    }
    return (const unsigned int *)(UINT_PTR)(g_draws->sheets + (unsigned int)k * 0x30u);
}

/* The game's own loaded sheet number `k`. */
static void *st_own_sheet(int k) {
    if (g_draws->slots != 0 && k != ST_CARRY) {
        return *(void **)(UINT_PTR)(g_draws->slots + g_draws->slot_at[k]);
    }
    return (void *)(UINT_PTR)st_sheet_desc(k)[11];
}

/* 1 when "<the game's folder>\Images\<name><suffix>" is a file. */
static int st_picture_there(const char *name, const char *suffix) {
    char path[MAX_PATH];
    DWORD n = GetModuleFileNameA(NULL, path, MAX_PATH), attrs;
    while (n > 0 && path[n - 1] != '\\') {
        --n;
    }
    if (n == 0 || n + 8 + (DWORD)lstrlenA(name) + (DWORD)lstrlenA(suffix) >= MAX_PATH) {
        return 0;
    }
    path[n] = '\0';
    lstrcatA(path, "Images\\");
    lstrcatA(path, name);
    lstrcatA(path, suffix);
    attrs = GetFileAttributesA(path);
    return attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

/* The sheet of `tone` (1..COUNT) for the game's sheet number `k` (0..7, ST_CARRY), or NULL when it is not all there
   (tried once: a picture added while the game runs shows after a restart). */
static void *st_toned_sheet(int tone, int k) {
    const unsigned int *desc = st_sheet_desc(k);
    const char *own, *ext;
    char *name = g_toned_name[tone][k];
    unsigned int across, down, cols, rows, a, d;
    unsigned int alloc = g_draws->alloc, ctor, bytes = g_draws->object_bytes, i;
    unsigned int *obj;
    if (g_toned_tried[tone][k]) {
        return g_toned[tone][k];
    }
    g_toned_tried[tone][k] = 1;
    if (desc == NULL) {
        return NULL;
    }
    own = (const char *)(UINT_PTR)desc[1];
    ext = (const char *)(UINT_PTR)desc[4];
    across = desc[5];
    down = desc[6];
    cols = desc[2];
    rows = desc[3];
    if (own == NULL || lstrlenA(own) > 40 || cols == 0 || rows == 0) {
        return NULL;
    }
    lstrcpyA(name, "vvfp_skin_");
    name[10] = (char)('0' + tone / 10);
    name[11] = (char)('0' + tone % 10);
    name[12] = '_';
    lstrcpyA(name + 13, own);
    if (across != 0) {
        char suffix[16];
        if (ext == NULL || lstrlenA(ext) > 8 || across > 9 || down > 9) {
            return NULL;
        }
        for (a = 0; a < across; ++a) {
            for (d = 0; d < down; ++d) {
                suffix[0] = (char)('0' + a);
                suffix[1] = (char)('0' + d);
                lstrcpyA(suffix + 2, ext);
                if (!st_picture_there(name, suffix)) {
                    return NULL;
                }
            }
        }
    } else if (!st_picture_there(name, "")) {
        return NULL;
    }
    /* Built as each game's Origins mask atlas is (The Secret City: VV3GetMaskAtlas, 0x34 bytes; the later
       two: vv_ensure_mask_atlas, which draws in these same routines -- room for the clip bounds the scaled
       draw reads there, zeroed), then the game's own constructor. */
    obj = ((unsigned int *(__cdecl *)(unsigned int))(UINT_PTR)alloc)(bytes);
    if (obj == NULL) {
        return NULL;
    }
    for (i = 0; i < bytes / 4u; ++i) {
        obj[i] = 0;
    }
    if (across != 0) {
        ctor = g_draws->grid_ctor;
        __asm {
            push rows
            push cols
            push down
            push across
            push ext
            push name
            mov  ecx, obj
            call ctor
        }
    } else {
        ctor = g_draws->one_ctor;
        __asm {
            push rows
            push cols
            push name
            mov  ecx, obj
            call ctor
        }
    }
    if (g_draws->clip) {
        obj[0x18] = (unsigned int)-30000;   /* +0x60 the clip's left */
        obj[0x19] = (unsigned int)-30000;   /* +0x64 top */
        obj[0x1A] = 30000u;                 /* +0x68 right */
        obj[0x1B] = 30000u;                 /* +0x6C bottom */
    }
    if (obj[4] == 0) {                  /* +0x10 the cell width: 0 after a load that failed */
        return NULL;
    }
    g_toned[tone][k] = obj;
    return obj;
}

/* What a stub hands over (the game draws on one thread, and neither a fetch nor a draw's entry re-enters). */
static unsigned int g_swap_ret;
static void **g_swap_out;
static const unsigned char *g_swap_rec;
static unsigned int g_fetch_head, g_fetch_body;

/* *g_swap_out is the sheet the game is about to draw the villager in g_swap_rec from. */
static void __cdecl st_swap(void) {
    void **out = g_swap_out;
    void *sheet;
    int k, tone;
    if (out == NULL || *out == NULL || g_draws == NULL) {
        return;
    }
    for (k = 0; k < ST_SHEETS && st_own_sheet(k) != *out; ++k) {
    }
    if (k == ST_SHEETS) {
        return;                             /* not a villager sheet (a mask, the skeleton): the game's own */
    }
    tone = st_drawn_tone(st_value(g_swap_rec));     /* 0 unless ESI is a held villager of this village */
    if (tone == 0) {
        return;
    }
    sheet = st_toned_sheet(tone, k);
    if (sheet != NULL) {
        *out = sheet;
    }
}

/* The head fetcher's sixth argument and the body fetcher's seventh are where the sheet is written. */
static __declspec(naked) void st_head_stub(void) {
    __asm {
        mov  eax, [esp + 0x18]
        mov  g_swap_out, eax
        mov  g_swap_rec, esi
        pop  eax                            ; the site's return address; the arguments are the fetcher's again
        mov  g_swap_ret, eax
        call dword ptr [g_fetch_head]       ; the game's own fetcher, which pops its arguments
        push eax
        call st_swap
        pop  eax                            ; the fetcher's own answer
        jmp  dword ptr [g_swap_ret]
    }
}

static __declspec(naked) void st_body_stub(void) {
    __asm {
        mov  eax, [esp + 0x1C]
        mov  g_swap_out, eax
        mov  g_swap_rec, esi
        pop  eax
        mov  g_swap_ret, eax
        call dword ptr [g_fetch_body]
        push eax
        call st_swap
        pop  eax
        jmp  dword ptr [g_swap_ret]
    }
}

/* The Secret City: at both entries the sheet is the first argument, [esp + 4].  Every register and the
   flags are as the game had them when its own code goes on. */
static __declspec(naked) void st_vv3_village_stub(void) {
    __asm {
        pushfd
        pushad
        lea  eax, [esp + 0x28]              ; past the registers, the flags and the return address
        mov  g_swap_out, eax
        mov  g_swap_rec, esi
        call st_swap
        popad
        popfd
        fild dword ptr [esp + 8]            ; the entry's own two instructions
        push ebx
        push VV3_VILLAGE_DRAW + 5
        ret
    }
}

static __declspec(naked) void st_vv3_thunk_stub(void) {
    __asm {
        pushfd
        pushad
        lea  eax, [esp + 0x28]
        mov  g_swap_out, eax
        mov  g_swap_rec, esi
        call st_swap
        popad
        popfd
        mov  ecx, [ecx]                     ; the thunk's own two instructions
        push VV3_DRAW_ENTRY
        ret
    }
}

/* ---- the held baby -------------------------------------------------------------------------------- */

static const unsigned char *g_carry_rec;
static unsigned int g_carry_manager, g_carry_ret, g_carry_resume, g_carry_after, g_detail_call;
static void *g_carry_saved;
static int g_carry_swapped, g_detail_cell;

/* The tone's copy of carrying.png for the baby `carrier` holds, or NULL for the game's own. */
static void *st_carry_sheet(const unsigned char *carrier) {
    int tone;
    if (g_draws == NULL || g_draws->carry_desc == 0) {
        return NULL;
    }
    tone = st_held(carrier);
    return tone == 0 ? NULL : st_toned_sheet(tone, ST_CARRY);
}

/* The carried-item draw entered for g_carry_rec on the manager g_carry_manager: when it is holding the baby,
   the manager's carrying sheet is the baby's tone's copy until the draw returns (st_carry_end). */
static void __cdecl st_carry_begin(void) {
    void **slot;
    void *own, *sheet;
    g_carry_swapped = 0;
    if (g_draws == NULL || g_draws->carry_desc == 0 || g_carry_rec == NULL || g_carry_manager == 0
        || *(const int *)(g_carry_rec + g_draws->carry_item) != ST_BABY_CELL) {
        return;
    }
    slot = (void **)(UINT_PTR)(g_carry_manager + ST_MANAGER_CARRYING);
    own = st_own_sheet(ST_CARRY);
    if (own == NULL || *slot != own) {
        return;
    }
    sheet = st_carry_sheet(g_carry_rec);
    if (sheet == NULL) {
        return;
    }
    g_carry_saved = own;
    *slot = sheet;
    g_carry_swapped = 1;
}

static void __cdecl st_carry_end(void) {
    if (g_carry_swapped) {
        *(void **)(UINT_PTR)(g_carry_manager + ST_MANAGER_CARRYING) = g_carry_saved;
        g_carry_swapped = 0;
    }
}

/* The Details figures' draw of a cell: the sheet (*g_swap_out) is the baby's tone's copy when it is the
   game's own carrying sheet and the cell is the baby. */
static void __cdecl st_detail_swap(void) {
    void *sheet;
    if (g_draws == NULL || g_draws->carry_desc == 0 || g_detail_cell != ST_BABY_CELL || g_swap_out == NULL
        || *g_swap_out == NULL || *g_swap_out != st_own_sheet(ST_CARRY)) {
        return;
    }
    sheet = st_carry_sheet(g_swap_rec);
    if (sheet != NULL) {
        *g_swap_out = sheet;
    }
}

/* The entry of the carried-item draw (its own first two instructions: mov eax, [esp+4]; push esi).  When the
   sheet was changed, the draw returns here first (st_carry_after_stub) to put it back. */
static __declspec(naked) void st_carry_entry_stub(void) {
    __asm {
        pushfd
        pushad
        mov  eax, [esp + 0x28]              ; the record: the first argument, past the registers, flags, return
        mov  g_carry_rec, eax
        mov  g_carry_manager, ecx
        call st_carry_begin
        popad
        popfd
        cmp  g_carry_swapped, 0
        je   own_return
        pop  eax                            ; the caller's return address: kept, the draw returns to us
        mov  g_carry_ret, eax
        push dword ptr [g_carry_after]
    own_return:
        mov  eax, [esp + 4]
        push esi
        jmp  dword ptr [g_carry_resume]
    }
}

static __declspec(naked) void st_carry_after_stub(void) {
    __asm {
        push eax
        push ecx
        push edx
        call st_carry_end
        pop  edx
        pop  ecx
        pop  eax
        jmp  dword ptr [g_carry_ret]
    }
}

/* A Details figure's `call` of the draw: the sheet is the first argument, the cell the fourth, ESI the
   record.  Every register and the flags are as the game had them when the draw is entered. */
static __declspec(naked) void st_detail_stub(void) {
    __asm {
        pushfd
        pushad
        lea  eax, [esp + 0x28]              ; the sheet: past the registers, the flags and the return address
        mov  g_swap_out, eax
        mov  g_swap_rec, esi
        mov  eax, [esp + 0x34]              ; the cell
        mov  g_detail_cell, eax
        call st_detail_swap
        popad
        popfd
        jmp  dword ptr [g_detail_call]
    }
}

static int g_drawn;

/* Every site must hold the game's own bytes; then all of a game's sites are written, or none. */
static void st_install_draws(const st_draws *draws) {
    static const unsigned char VILLAGE_STOCK[5] = { 0xDB, 0x44, 0x24, 0x08, 0x53 };
    static const unsigned char THUNK_STOCK[7] = { 0x8B, 0x09, 0xE9, 0xE9, 0xF3, 0xFF, 0xFF };
    static const unsigned char CARRY_STOCK[5] = { 0x8B, 0x44, 0x24, 0x04, 0x56 };  /* mov eax, [esp+4]; push esi */
    vvfp_site_write w[13];
    unsigned char stock[12][5];
    int i;
    g_draws = draws;
    if (draws == &VV3_DRAWS) {
        vvfp_site_branch(&w[0], VV3_VILLAGE_DRAW, 5, VILLAGE_STOCK, 0xE9, (const void *)st_vv3_village_stub);
        vvfp_site_branch(&w[1], VV3_DRAW_THUNK, 7, THUNK_STOCK, 0xE9, (const void *)st_vv3_thunk_stub);
        g_drawn = vvfp_install_sites(w, 2);
        return;
    }
    g_fetch_head = draws->head_fetch;
    g_fetch_body = draws->body_fetch;
    for (i = 0; i < 6; ++i) {
        unsigned int va = i < 3 ? draws->head_sites[i] : draws->body_sites[i - 3];
        unsigned int rel = (i < 3 ? draws->head_fetch : draws->body_fetch) - (va + 5u);
        stock[i][0] = 0xE8;
        memcpy(stock[i] + 1, &rel, 4);
        vvfp_site_branch(&w[i], va, 5, stock[i], 0xE8, (const void *)(i < 3 ? st_head_stub : st_body_stub));
    }
    /* The held baby: the carried-item draw's entry and the Details figures' six draws of cell 3. */
    g_carry_resume = draws->carry_entry + 5u;
    g_carry_after = (unsigned int)(UINT_PTR)st_carry_after_stub;
    g_detail_call = draws->detail_draw;
    vvfp_site_branch(&w[6], draws->carry_entry, 5, CARRY_STOCK, 0xE9, (const void *)st_carry_entry_stub);
    for (i = 0; i < 6; ++i) {
        unsigned int va = draws->detail_sites[i];
        unsigned int rel = draws->detail_draw - (va + 5u);
        stock[6 + i][0] = 0xE8;
        memcpy(stock[6 + i] + 1, &rel, 4);
        vvfp_site_branch(&w[7 + i], va, 5, stock[6 + i], 0xE8, (const void *)st_detail_stub);
    }
    g_drawn = vvfp_install_sites(w, 13);
}
#else
static int g_drawn;
#endif

/* ---- exports ---------------------------------------------------------------------------------------- */

/* Called once at game start by "VVFP Startup.dll", outside DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_game != 0 || game < 1 || game > 5) {
        return;
    }
    g_game = game;
#ifndef VVFP_SKIN_TONE_HARNESS
    /* "0".."10" (read as tenths: 0..100); anything else is no preference. */
    g_preferred = (int)(vvfp_read_tenths(VVFP_SKIN_TONE_CHOICE_FILE, 0u, 0u, VVFP_SKIN_TONE_COUNT * 10u) / 10u);
    if (game == 3) {
        st_install_draws(&VV3_DRAWS);
    } else if (game == 4) {
        st_install_draws(&VV4_DRAWS);
    } else if (game == 5) {
        st_install_draws(&VV5_DRAWS);
    }
#endif
}

/* 1 when this DLL keeps `game`'s tones. */
int __stdcall VvfpSkinToneInstalled(int game) {
    return g_game != 0 && game == g_game;
}

/* 1 when `game`'s head and body draws follow the tone (the draws above are in); otherwise every villager
   is drawn with the game's own art and the Change Appearance windows do not offer the row. */
int __stdcall VvfpSkinToneDrawn(int game) {
    return g_game != 0 && game == g_game && g_drawn;
}

int __stdcall VvfpSkinToneCount(void) {
    return VVFP_SKIN_TONE_COUNT;
}

/* The tone the villager in `record` is drawn with: 1..COUNT, or 0 for the game's own art (chosen, or the
   village not known yet).  A villager with no tone is given one first. */
int __stdcall VvfpSkinToneGet(int game, const void *record) {
    if (game != g_game || g_game == 0) {
        return 0;
    }
    return st_drawn_tone(st_value((const unsigned char *)record));
}

/* The record's number when it is a held villager of the village on screen, else -1. */
static int st_at(const unsigned char *record) {
    int i;
    if (record == NULL || !hl_sync()) {
        return -1;
    }
    i = hl_index(record);
    return i >= 0 && g_roster[i] != 0 && g_roster[i] == hl_identity(record) ? i : -1;
}

/* THE REVIVE SNAPSHOT'S READ: what is kept for the villager in `record`, as one number to hand back to
   VvfpSkinToneGive -- the tone (0 none, 1..COUNT, 15 the game's own, chosen) in the low byte and the birth
   tone (0 none, 1..COUNT) in the next -- without giving anyone a tone. */
int __stdcall VvfpSkinToneOf(int game, const void *record) {
    int i;
    if (game != g_game || g_game == 0) {
        return 0;
    }
    i = st_at((const unsigned char *)record);
    return i < 0 ? 0 : ST_TONE(g_look[i]) | ((int)g_second[i] << 8);
}

/* The birth tone of the villager in `record`: 1..COUNT, or 0 for none kept. */
int __stdcall VvfpSkinToneBirth(int game, const void *record) {
    int i;
    if (game != g_game || g_game == 0) {
        return 0;
    }
    i = st_at((const unsigned char *)record);
    return i >= 0 && g_second[i] >= 1 && g_second[i] <= VVFP_SKIN_TONE_COUNT ? (int)g_second[i] : 0;
}

/* Keep `tone` for the villager in `record`; `birth` not 0: that birth tone too (0: the one kept stays, and
   a villager with none gets `tone` when it is a tone).  1 when the file says so; otherwise nothing changed. */
static int st_keep(const unsigned char *record, int tone, int birth) {
    unsigned char value = st_value(record), was;
    int i = st_at(record);
    if (i < 0) {
        return 0;
    }
    was = g_second[i];
    if (birth != 0) {
        g_second[i] = (unsigned char)birth;
    } else if (was == 0 && tone >= 1 && tone <= VVFP_SKIN_TONE_COUNT) {
        g_second[i] = (unsigned char)tone;
    }
    if (!hl_set(record, (int)((value & 0xF0u) | (unsigned int)tone))) {
        g_second[i] = was;                      /* memory never says what the file does not */
        return 0;
    }
    return 1;
}

/* THE REVIVE SNAPSHOT'S WRITE, and a tone given from outside: keep what VvfpSkinToneOf returned -- the
   tone (1..COUNT or 15) in the low byte, the birth tone (0: not known) in the next -- for the villager
   in `record`, with no log record (nothing was changed by the player).  1 when the file says so. */
int __stdcall VvfpSkinToneGive(int game, const void *record, int kept) {
    int tone = kept & 0xFF, birth = (kept >> 8) & 0xFF;
    if (game != g_game || g_game == 0 || record == NULL || !st_tone_ok(tone) || birth > VVFP_SKIN_TONE_COUNT
        || (kept & ~0xFFFF) != 0) {
        return 0;
    }
    return st_keep((const unsigned char *)record, tone, birth);
}

/* Change Appearance: keep `tone` (1..COUNT, or 15 for the game's own art) and log the change.  1 when the
   file says so. */
int __stdcall VvfpSkinToneSet(int game, const void *record, int tone) {
    int was;
    if (game != g_game || g_game == 0 || record == NULL || !st_tone_ok(tone)) {
        return 0;
    }
    was = ST_TONE(st_value((const unsigned char *)record));
    if (!st_keep((const unsigned char *)record, tone, 0)) {
        return 0;
    }
    st_log_change((const unsigned char *)record, was, tone);
    return 1;
}

/* Change Appearance's "Reset to birth tone": the villager's birth tone again, logged like any change.
   1 when the file says so; 0 when no birth tone is kept. */
int __stdcall VvfpSkinToneReset(int game, const void *record) {
    int birth = VvfpSkinToneBirth(game, record);
    return birth != 0 && VvfpSkinToneSet(game, record, birth);
}

/* Change Appearance for All: every tone in ONE write; 1 when the file says so for all of them. */
int __stdcall VvfpSkinToneSetMany(int game, const void *const *records, const int *tones, int count) {
    static int was[HL_MAX], values[HL_MAX];
    int k;
    if (game != g_game || g_game == 0 || records == NULL || tones == NULL || count <= 0 || count > HL_MAX) {
        return 0;
    }
    for (k = 0; k < count; ++k) {
        unsigned char value;
        if (records[k] == NULL || !st_tone_ok(tones[k])) {
            return 0;
        }
        value = st_value((const unsigned char *)records[k]);
        was[k] = ST_TONE(value);
        values[k] = (int)((value & 0xF0u) | (unsigned int)tones[k]);
    }
    if (!hl_set_many((const unsigned char *const *)records, values, count)) {
        return 0;
    }
    for (k = 0; k < count; ++k) {
        st_log_change((const unsigned char *)records[k], was[k], tones[k]);
    }
    return 1;
}

/* A CONCEPTION: the baby's tone is rolled now, by the head rule on its parents' tones as they are now
   (`father` NULL: not known), and kept on the mother.  The held baby is drawn with it (VvfpSkinTonePending)
   and the newborn is given it unchanged.  The tone rolled, or 0 when it could not be kept. */
int __stdcall VvfpSkinToneConceived(int game, const void *mother, const void *father) {
    unsigned char value;
    int tone;
    if (game != g_game || g_game == 0 || mother == NULL) {
        return 0;
    }
    value = st_value((const unsigned char *)mother);
    tone = vvfp_skin_tone_inherit(father != NULL ? st_drawn_tone(st_value((const unsigned char *)father)) : 0,
                                  st_drawn_tone(value), st_roll() % 100u, st_roll() % 3u, st_roll());
    return hl_set((const unsigned char *)mother, (int)((value & 0x0Fu) | ((unsigned int)tone << 4))) ? tone : 0;
}

/* The tone of the baby `mother` is carrying, as rolled at the conception: 1..COUNT, or 0 for none kept. */
int __stdcall VvfpSkinTonePending(int game, const void *mother) {
    int i, tone;
    if (game != g_game || g_game == 0 || mother == NULL || !hl_sync()) {
        return 0;
    }
    i = hl_index((const unsigned char *)mother);
    if (i < 0 || g_roster[i] == 0 || g_roster[i] != hl_identity((const unsigned char *)mother)) {
        return 0;
    }
    tone = ST_BABY(g_look[i]);
    return tone >= 1 && tone <= VVFP_SKIN_TONE_COUNT ? tone : 0;
}

/* The tone the baby `carrier` holds is drawn with (st_held: chosen and kept the first time it is seen when
   no conception kept one): 1..COUNT, or 0 for the game's own art. */
int __stdcall VvfpSkinToneHeld(int game, const void *carrier) {
    if (game != g_game || g_game == 0) {
        return 0;
    }
    return st_held((const unsigned char *)carrier);
}

/* A BIRTH, told at once (A New Home's records name no parents, so there this is the only way a newborn
   inherits): the child gets the tone kept on `mother` at the conception; with none kept, the head rule on
   her tone alone.  `first` not NULL: a second or third baby, which copies `first`.  `last` not 0: the
   pregnancy is over and what was kept on the mother is cleared.  The tone given, or 0. */
int __stdcall VvfpSkinToneBorn(int game, const void *child, const void *mother, const void *first, int last) {
    unsigned char mine;
    int tone = 0, i;
    if (game != g_game || g_game == 0 || child == NULL || !hl_sync()) {
        return 0;
    }
    if (first != NULL) {
        tone = st_drawn_tone((unsigned char)(VvfpSkinToneOf(game, first) & 0xFF));
    }
    if (tone == 0) {
        tone = VvfpSkinTonePending(game, mother);
    }
    if (tone == 0) {
        unsigned char hers = 0;
        i = mother != NULL ? hl_index((const unsigned char *)mother) : -1;
        if (i >= 0 && g_roster[i] != 0 && g_roster[i] == hl_identity((const unsigned char *)mother)) {
            hers = g_look[i];
        }
        tone = vvfp_skin_tone_inherit(0, st_drawn_tone(hers), st_roll() % 100u, st_roll() % 3u, st_roll());
    }
    g_sync_tick = GetTickCount() - HL_SYNC_MS;  /* the newborn is in the village now */
    if (!hl_sync()) {
        return 0;
    }
    i = hl_index((const unsigned char *)child);
    mine = i >= 0 ? g_look[i] : 0;
    if (i < 0) {
        return 0;
    }
    g_second[i] = (unsigned char)tone;          /* born with it */
    if (!hl_set((const unsigned char *)child, (int)((mine & 0xF0u) | (unsigned int)tone))) {
        g_second[i] = 0;
        return 0;
    }
    if (last && mother != NULL) {
        i = hl_index((const unsigned char *)mother);
        if (i >= 0 && ST_BABY(g_look[i]) != 0) {
            (void)hl_set((const unsigned char *)mother, (int)(g_look[i] & 0x0Fu));
        }
    }
    return tone;
}

/* A randomly made villager's tone by the preferred-tone rule (skin_tone_rules.h), for the tests. */
int __stdcall VvfpSkinToneRandom(int preferred, unsigned int r100, unsigned int rn) {
    return vvfp_skin_tone_random(preferred, r100, rn);
}

/* The preferred skin tone this DLL read at start: 0 none, 1..COUNT. */
int __stdcall VvfpSkinTonePreferred(void) {
    return g_preferred;
}

/* The head rule itself (skin_tone_rules.h), for the tests and for anyone who rolls for themselves. */
int __stdcall VvfpSkinToneInherit(int father, int mother, unsigned int r100, unsigned int r3, unsigned int rn) {
    return vvfp_skin_tone_inherit(father, mother, r100, r3, rn);
}

/* A tone's name into `out` (at least 40 characters): "Copper", or "Game's own" for the game's own art. */
void __stdcall VvfpSkinToneName(int tone, char *out) {
    if (out != NULL) {
        st_name(out, tone);
    }
}

int __stdcall VvfpVillagersRenamed(int game, int slot, int count, const void *const *records,
                                   const char *const *old_names) {
    if (game < 1 || game > 5 || game != g_game) {
        return 0;
    }
    return hl_renamed(slot, count, records, old_names, LAYOUT[game].stride, LAYOUT[game].name,
                      LAYOUT[game].name_bytes);
}

int __stdcall VvfpVillagerSexChanged(int game, int slot, const void *record, const void *before) {
    if (game < 1 || game > 5 || game != g_game || record == NULL || before == NULL) {
        return 0;
    }
    return hl_sex_changed(slot, (const unsigned char *)record, (const unsigned char *)before);
}

#ifndef VVFP_SKIN_TONE_HARNESS
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
#endif
