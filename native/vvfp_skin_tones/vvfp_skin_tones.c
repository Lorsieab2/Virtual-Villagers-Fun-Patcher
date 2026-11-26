/* VVFP Skin Tones -- each villager's skin tone, kept and handed down (the owner, 2026-11-06 and 2026-11-26:
   "implement the skin tone mod in all 5 games!! with inheritance and mixing"; "babies conceived from two
   parents inherit skin tones same as head rules").  All five games.

   THIS DLL IS THE DATA HALF.  It keeps every villager's tone in the patcher's own per-save file, gives a
   tone to whoever has none, and answers the other companions.  It writes nothing into the game and nothing
   into a villager record.  The draws that show a tone (each game's head and body sheets, swapped per
   villager for that tone's sheet) ask VvfpSkinToneGet; until they are in, VvfpSkinToneDrawn says 0 and
   every villager is drawn with the game's own art.

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
       each as likely.
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
#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"
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
} st_layout;

static const st_layout LAYOUT[6] = {
    { 0 },
    { 0x3D8u,  0x28u,   0x370u,  0x1Cu, 0x350u,  0u,      0u,      0x36Cu, 0x348u },
    { 0xE48Cu, 0x30u,   0x564u,  0x18u, 0x538u,  0x57Du,  0x596u,  0u,     0x530u },
    { 0x1F8Cu, 0xF10u,  0xDD4u,  0x19u, 0xDC8u,  0xDF8u,  0xE11u,  0u,     0xDC4u },
    { 0x2E3Cu, 0x1CC4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1B8Cu },
    { 0x2F44u, 0x1CD4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1B8Cu },
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

static int st_random_tone(void) {
    return (int)(st_roll() % (unsigned int)VVFP_SKIN_TONE_COUNT) + 1;
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

/* A tone as the windows and the logs write it: "Copper", or "Default" for the game's own art.  `out`
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

/* ---- exports ---------------------------------------------------------------------------------------- */

/* Called once at game start by "VVFP Startup.dll", outside DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_game != 0 || game < 1 || game > 5) {
        return;
    }
    g_game = game;
}

/* 1 when this DLL keeps `game`'s tones. */
int __stdcall VvfpSkinToneInstalled(int game) {
    return g_game != 0 && game == g_game;
}

/* 1 when `game`'s head and body draws follow the tone.  The draw companions set it (VvfpSkinToneSetDrawn)
   once their own sites are in; until then every villager is drawn with the game's own art and the Change
   Appearance windows do not offer the row. */
static int g_drawn;

int __stdcall VvfpSkinToneDrawn(int game) {
    return g_game != 0 && game == g_game && g_drawn;
}

void __stdcall VvfpSkinToneSetDrawn(int game, int drawn) {
    if (g_game != 0 && game == g_game) {
        g_drawn = drawn != 0;
    }
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

/* The head rule itself (skin_tone_rules.h), for the tests and for anyone who rolls for themselves. */
int __stdcall VvfpSkinToneInherit(int father, int mother, unsigned int r100, unsigned int r3, unsigned int rn) {
    return vvfp_skin_tone_inherit(father, mother, r100, r3, rn);
}

/* A tone's name into `out` (at least 40 characters): "Copper", or "Default" for the game's own art. */
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
