/* VVFP Heathen Aging -- New Believers: Heathens who age, die of old age, are replaced, and (with the tribe row)
   have children.  Four rows share this one companion; each row ships a flag file beside it in the patcher's folder
   (native/shared/patcher_files.h), and the companion reads which are there once, at start:

     "VVFP Heathen Aging Former.txt"     Former Villagers Keep Aging Among the Heathens (the owner, 2026-11-22:
                                         "villagers-converted-heathens continue to age (only applies to our
                                         villagers who converted into heathens)");
     "VVFP Heathen Aging Tribe.txt"      Heathen Tribe Ages, Dies and Has Children: every Heathen, the puzzle
                                         Heathens too (the owner: "PUZZLE HEATHENS TOO (IF THEY DIE ANOTHER ONE
                                         IMMEDIATELY SPAWNS IN"), and Heathen babies;
     "VVFP Heathen Skeletons Former.txt" Former Villagers Among the Heathens Leave Skeletons;
     "VVFP Heathen Skeletons All.txt"    All Heathens Leave Skeletons (the two skeleton rows exclude each other).

   With neither aging flag the companion installs nothing.

   THE STOCK GAME.  A Heathen never ages: the age credit 0x46FE90 (every frame, every living record) adds the
   elapsed age units to +0x1B8C only for a believer (`cmp byte [esi+0x1CEC], bl; mov edi, eax; jne` at 0x470077),
   and the life tick 0x472C90 (one age unit per pass for every believer whose processed age +0x1C3C is behind its
   age; live, in the load-time catch-up, a Time Warp and a time skip -- all of them come through these two)
   skips a Heathen at 0x472CB7: it copies the age into the processed age, clears the sick byte, and nothing else
   runs (no eating, starving, sickness, health, Faith drift, old age or birth).

   WHAT THIS DOES (two run-time splices, all or none, stock bytes checked first: native/shared/install_sites.h):
     0x470077  the age credit's faction test: a believer goes on as before; an AGING Heathen (below) gets the same
               units added to its age (what 0x46F7F0 does) and then takes the Heathen branch the executable has
               there (0x47008D stock, or 0x4700B9 when the Village Statistics rows skip the Oldest Villager maximum
               for Heathens: `jne` 0C or 38 -- both accepted, the branch's own target followed), so a Heathen is
               never the Oldest Villager where the statistics say so; everyone else as the stock game.
               A living believer seen here is remembered by identity; a living Heathen the credit last saw as
               that very believer turned Heathen since -- by any path at all (the Faith drift, The Breaking
               Point, island events such as The Spa and The Cracked Mask, a Custom Island Event, Pick Island
               Event) -- and is written down as a former villager.  A record the Heathen creator fills was never
               seen as a believer, so it never is.  (No call site is spliced for this: the Heathens Keep Their
               Masks companion owns The Spa's and The Cracked Mask's faction calls.)
     0x472CB7  the life tick's Heathen skip: an aging Heathen with an age unit due gets ONE unit, exactly the
               believer's old-age rule (0x472FC6..0x47304A: at each whole year of the processed age past
               1,100 + 160 x (Medicine - 1) units, rand(100) < 10 x years over sets health 0, cause 2 Old age,
               through SetHealth 0x4758B0), and with the tribe row its pregnancy and birth (below); the processed
               age goes up by one and the pass is marked not done (the tick's own [esp+0x12]), as a believer's
               unit is.  Nothing else of the believer's unit runs: a Heathen still never eats, starves, falls
               sick, loses health, drifts in Faith or works.  Any other Heathen: the stock skip.

   WHO IS A FORMER VILLAGER.  The identity (native/shared/custom_titles.h vv_title_identity: name, likes,
   dislikes) of every believer seen turning Heathen, kept per save slot in
       <Documents>\LDW\<game>\Virtual Villagers Fun Patcher\Save <S>\Data\Heathen Aging\
           Heathen Aging - Save <S>.dat
   (native/shared/sidecar_io.h: atomic, an unreadable file never replaced, an invalid one set aside), with the
   Heathen babies this companion delivered (born Heathens, never former villagers).  A Heathen who turned before
   the row was installed is known by the parents on the record (+0x1BC0 / +0x1BD9: born in the village; the camp's
   and the Barrel's Heathens have none) unless the file says they were born a Heathen.  The file is written at most
   once a second from the age credit's throttled pass, never inside the life tick.  Its entries follow their
   villager when the likes or dislikes change in place or the name changes (follow_identities: the repo's
   identity_in_place.h and rename rules), and src/vv_last_names.py's offline renames rekey the file too.

   A DEATH.  The old age's SetHealth makes the body as for a believer when a skeleton row says so for this Heathen
   (All Heathens, or Former Villagers and a former villager): the believers bury it through their own "Burying
   the dead" (a grave, the Cause of Death companion's Death record at the burial; unburied, the game's removal
   after 240 units), a puzzle Heathen's body losing its role so the role finder 0x470690 finds the new one.
   Otherwise no body is made: the activity stops (0x473440), the selection goes if it is theirs, the presence
   byte is cleared (as the game's own removals do) and the Cause of Death companion writes the Death record, Old
   age, "no grave (died among the Heathens: nothing was left)" (VvfpCauseDiedAmongHeathens).  Either way the
   statistics' villager-death counter is put back (Heathens never count: the owner).
   A REPLACEMENT (the owner, 2026-11-23: only for a camp Heathen, or a puzzle Heathen while its puzzle is unsolved;
   never for a former villager, and for nobody once The Last Heathen, puzzle 25, is solved -- the camp then
   empties over time) is made at once, in the same tick, by the game's one Heathen creator 0x46FD20 as the stock
   camp makes one: an ordinary Heathen keeps the dead one's camp role (0..11) and mask (blue, orange or red), age 400,
   random sex, the stock camp's Faith (0x470E60: -38 - rand(30), or the dead one's own when it was one of the
   five easy blue Faiths -5, -9, -16, -23, -30); a puzzle Heathen whose puzzle is not solved yet by a new one in the same role,
   set up exactly as the stock camp sets that role up (the Doctor, Chief with every skill 100, the three Masters;
   the Heathen Mommy with her infant, its father an adult Heathen man when there is one).  Its Faith is written
   after the creator (the creator's own SetFaith would run to-a-Heathen on a record still a believer: its "stopped
   believing" message and the Cause of Death companion's "Left the tribe" record).  The Cause of Death companion
   writes its Arrived record (VvfpCauseHeathenArrived).  A full table: the replacement waits (kept per save slot),
   and is made by the age credit's throttled pass as soon as a record is free.

   HEATHEN BABIES (the tribe row only; no new conception once The Last Heathen is solved).  An adult Heathen woman (14 to 45 years), not expecting, not the Heathen
   Mommy, with a living adult Heathen man in the camp, conceives on 1 age unit in CONCEIVE_IN, 400 (about once in 20 years) through
   the game's conception routine 0x465E00 forced (father: a random adult Heathen man), only while at least
   HA_ROOM_KEPT records stay free for the village's own births.  The Village Statistics' twins and triplets are put
   back as the Story upgrades' Custom Island Event does for a Heathen carrier.  The birth comes as a believer's
   does (40 units after conception): each baby is made by the Heathen creator at age 40 with the parents' names,
   heads and bodies on its record (the head the stock birth's rule: the parents' average +-1 on 95%), Faith
   -38 - rand(30) (the stock camp children's); then the pregnancy and the carry are cleared.  Each baby gets its Birth record (tell_born), marked
   a Heathen, as the conception got its Conception record from the game's own conception routine.  No room: the
   birth waits.  Only a pregnancy this
   companion conceived (its mother kept in the file as expecting) is delivered among the Heathens: one from before a
   believer turned Heathen, and the Heathen Mommy's infant (her puzzle shows her carrying it), wait for them to
   rejoin the tribe, as in the stock game; the expecting entry goes when she is a believer again or dies, so a
   later believer pregnancy is never delivered among the Heathens.

   HEATHEN GRAVES AND START OVER.  A grave keeps no faction, so every Heathen body's Roster of the Dead entry is
   written down at its burial (watch_graves) and kept in the file; "VVFP Statistics Export.dll" asks
   VvfpHeathenAgingGrave so a Heathen's grave is never a Village Elder (Heathens never count).  "VVFP Save
   Reset.dll" calls VvfpHeathenAgingVillageReset at Start Over or a deleted tribe, before it deletes the slot's
   folder: everything kept for that village is forgotten, so none of it is written back into the next one.

   SAFETY.  Our steps run under structured exception handling; a fault leaves the stock behaviour for that
   villager.  No debug output; no text is shown. */
#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/sidecar_io.h"
#include "../shared/game_save_slot.h"
#include "../shared/custom_titles.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/identity_in_place.h"

#define HA_GAME 5
#define HA_FLAG_FORMER "VVFP Heathen Aging Former.txt"
#define HA_FLAG_TRIBE "VVFP Heathen Aging Tribe.txt"
#define HA_FLAG_BONES_FORMER "VVFP Heathen Skeletons Former.txt"
#define HA_FLAG_BONES_ALL "VVFP Heathen Skeletons All.txt"
/* "Heathens can be selected in Island Events/Heathen-Exclusive Events" (the owner, 2026-11-23): island events may
   kill, take away or make pregnant an ordinary Heathen; this companion carries their deaths, replacements and
   births (VvfpHeathenAgingEventGone, VvfpHeathenAgingEventPregnancy), whatever aging row is ticked. */
#define HA_FLAG_EVENTS "VVFP Heathen Aging Events.txt"

/* The villager record (vv5). */
#define R_STRIDE 0x2F44u
#define R_AGE 0x1B8Cu
#define R_SEX 0x1B90u            /* 1 the woman */
#define R_LINEAGE 0x1B98u
#define R_NAME 0x1B9Cu
#define R_NAME_CAP 0x19u
#define R_HEAD 0x1BB8u
#define R_BODY 0x1BBCu
#define R_FATHER_NAME 0x1BC0u
#define R_MOTHER_NAME 0x1BD9u
#define R_PARENT_NAME_CAP 0x19u
#define R_FATHER_HEAD 0x1BF4u
#define R_FATHER_BODY 0x1BF8u
#define R_MOTHER_HEAD 0x1BFCu
#define R_MOTHER_BODY 0x1C00u
#define R_BABY_SKILL 0x1C04u
#define R_BABY_VALUE 0x1C08u
#define R_BABY_FATHER_NAME 0x1C10u
#define R_BABY_FATHER_BODY 0x1C2Cu
#define R_BABY_FATHER_HEAD 0x1C30u
#define R_HEALTH_BLOCK 0x1C34u
#define R_PROCESSED 0x1C3Cu
#define R_HEALTH 0x1C40u
#define R_PREGNANT 0x1C4Cu       /* the processed age at conception, 0 none */
#define R_LITTER 0x1C50u
#define R_SKILLS 0x1C5Cu         /* six floats */
#define R_PRESENT 0x1CD4u
#define R_LOOKALIKE 0x1CE1u
#define R_FACTION 0x1CECu
#define R_ORANGE 0x1CEDu
#define R_RED 0x1CEEu
#define R_FAITH 0x1CF0u
#define R_ROLE 0x1CFCu
#define R_LIKES 0x1F5Cu
#define R_DISLIKES 0x1F68u
#define R_PREF_SLOTS 3u

#define ADULT 280                /* 14 years */
#define BIRTH_LAST 900           /* 45 years */
#define DELIVERY 40              /* units from conception to birth (0x4730AF: +0x28) */
#define CONCEIVE_IN 400          /* 1 age unit in 400: about one baby a woman in 20 years, one camp baby
                                    every ~2 years with ~10 young women (the owner, 2026-11-23) */
#define HA_ROOM_KEPT 10          /* records left free for the village's own births */

/* The game. */
#define G_RAND 0x403660u               /* cdecl rand(n) */
#define G_MEDICINE 0x51D5D0u           /* the tech levels 0x51D5CC, Medicine [1] (0x423600(1)) */
#define G_SET_HEALTH 0x4758B0u         /* thiscall on +0x1C34: (value, cause); ret 8 */
#define G_STOP 0x473440u               /* thiscall on the record */
#define G_SELECTED 0x4653D0u           /* thiscall on the record: al */
#define G_DESELECT 0x470800u           /* thiscall on the manager */
#define G_CREATE_HEATHEN 0x46FD20u     /* thiscall on the manager, 9 args; ret 0x24 */
#define G_CONCEIVE 0x465E00u           /* thiscall on the carrier, 7 args; ret 0x1C */
#define G_CARRY 0x466420u              /* thiscall on the record: (item, -1 none); ret 4 */
#define G_TWINS 0x51D380u
#define G_TRIPLETS 0x51D384u
#define G_DEATHS_STAT 0x51D3A0u        /* the Village Statistics' villager deaths (build_statistics_features.py) */
#define G_PUZZLE_PROGRESS 0x51E008u    /* +p*8 */
#define G_PUZZLE_NEEDED 0x51DF30u      /* +p*4 */
#define G_CHIEF_SKILL 0x4980D4u        /* float 100.0 */

#define SITE_CREDIT 0x470077u
#define CREDIT_ADD 0x470081u
#define SITE_TICK 0x472CB7u
#define TICK_BELIEVER 0x472CDBu
#define TICK_HEATHEN 0x472CC0u
#define TICK_NEXT 0x473359u
#define HA_SITES 2

typedef int (__fastcall *tc0_fn)(void *self, void *unused_edx);
typedef int (__fastcall *tc1_fn)(void *self, void *unused_edx, int a);
typedef int (__fastcall *tc2_fn)(void *self, void *unused_edx, int a, int b);
typedef int (__fastcall *tc7_fn)(void *self, void *unused_edx, int a, int b, int c, int d, int e, int f, int g);
typedef int (__fastcall *tc9_fn)(void *self, void *unused_edx, int a, int b, int c, int d, int e, int f, int g,
                                 int h, int i);
typedef int (__cdecl *rand_fn)(int n);
typedef void (__stdcall *cod_died_fn)(int game, int index, int cause);
typedef void (__stdcall *cod_arrived_fn)(int game, int index, const char *how);

static int g_installed;
static int g_former_row, g_tribe_row, g_bones_former, g_bones_all, g_events_row;
static unsigned char *g_manager;
static unsigned char *g_records;
static unsigned int g_slots;
static unsigned int g_skip_target;     /* the credit's own Heathen branch */
static int g_credit_result;
static int g_tick_result;

/* Living believers the age credit has seen, by slot. */
static unsigned int g_seen[256];

static int g_body_count;                   /* the Heathen bodies watched (watch_graves, below) */
static int g_roster_known;                 /* the last roster look (follow_identities, below) */
static void pay_owed(void);
static int owed_count(void);

/* ---- the game, called ------------------------------------------------------------------------------------- */

static int ha_rand(int n) {
    return ((rand_fn)(UINT_PTR)G_RAND)(n);
}

static unsigned char *rec_at(int index) {
    return g_records + (size_t)index * R_STRIDE;
}

static int rec_index(const unsigned char *record) {
    UINT_PTR at = (UINT_PTR)record, base = (UINT_PTR)g_records;
    if (at < base || (at - base) % R_STRIDE != 0 || (at - base) / R_STRIDE >= g_slots) {
        return -1;
    }
    return (int)((at - base) / R_STRIDE);
}

static int i32(const unsigned char *record, unsigned int at) {
    return *(const int *)(record + at);
}

static int living(const unsigned char *record) {
    return record[R_PRESENT] != 0 && record[R_LOOKALIKE] == 0 && i32(record, R_HEALTH) > 0;
}

static unsigned int identity(const unsigned char *record) {
    return vv_title_identity(record, R_NAME, R_NAME_CAP, R_LIKES, R_DISLIKES, R_PREF_SLOTS);
}

static int puzzle_of_role(int role) {
    switch (role) {
    case 12: return 1;           /* the Heathen Doctor: The Sick Heathen */
    case 16: return 5;           /* the Heathen Farmer: the Hydroponic Farm */
    case 15: return 9;           /* the Heathen Builder */
    case 14: return 13;          /* the Heathen Scientist */
    case 13: return 16;          /* the Heathen Chief */
    case 17: return 17;          /* the Heathen Mommy */
    default: return 0;
    }
}

#define LAST_HEATHEN 25                /* The Last Heathen (CConvertLastHeathenPuzzle) */

static int puzzle_done(int puzzle) {
    return *(const volatile int *)(UINT_PTR)(G_PUZZLE_PROGRESS + (unsigned int)puzzle * 8u)
        >= *(const volatile int *)(UINT_PTR)(G_PUZZLE_NEEDED + (unsigned int)puzzle * 4u);
}

/* ---- the file of former villagers ------------------------------------------------------------------------- */

#define HA_MAGIC 0x31414856u     /* 'VHA1' */
#define HA_VERSION 2u          /* 2: magic, version, game, count, slot (v1 never shipped) */
/* Room for every live entry with room to spare: at most 256 records' born / former / expecting entries (768),
   500 Heathen graves (the Roster of the Dead) and the owed replacements (at most one a record, 256): 1,524.
   Entries of villagers no longer in the village are pruned when the list is full (known_prune), never a
   living villager's, a grave or an owed replacement. */
#define HA_MAX 2048
#define HA_HEADER 20u
#define KIND_BORN 0u             /* born a Heathen (a baby this companion delivered) */
#define KIND_FORMER 1u           /* a believer who turned Heathen */
#define KIND_EXPECTING 2u        /* a Heathen woman expecting a Heathen baby this companion conceived */
#define KIND_GRAVE 3u            /* a Roster of the Dead entry a Heathen's body was buried into (identity = entry + 1) */
#define KIND_OWED 4u             /* a replacement owed (a full table): owed_pack's role, masks, Faith, a number */
#define HA_RESERVE ((int)sizeof(".unreadable-4294967295-999"))
#define HA_WRITE_MS 1000u
#define HA_KEEP_MS 250u          /* the slot looked at, the file kept, at most this often */
static DWORD g_kept_at = 0x80000000u;

static struct { unsigned int identity, kind; } g_known[HA_MAX];
static int g_known_count;
static vv_sidecar_gate g_gate;
static int g_file_slot;
static int g_load_blocked;
static int g_dirty;
static DWORD g_synced_at;
static unsigned int g_buffer[(HA_HEADER + HA_MAX * 8u) / 4u + 1u];

static int known_path(int slot, char *out, int make) {
    static const char *const LEVELS[4] = {
        "\\Virtual Villagers Fun Patcher", "\\Save %d", "\\Data", "\\Heathen Aging"
    };
    char docs[MAX_PATH], exe[MAX_PATH], part[64];
    char *base = exe, *p, *dot = NULL;
    DWORD n;
    int i;
    if (slot < 1 || slot > 5 || !SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    for (p = exe; *p != '\0'; ++p) {
        if (*p == '\\') {
            base = p + 1;
            dot = NULL;
        } else if (*p == '.') {
            dot = p;
        }
    }
    if (dot != NULL) {
        *dot = '\0';
    }
    if (base[0] == '\0' || lstrlenA(docs) + lstrlenA(base) + 160 >= MAX_PATH - HA_RESERVE) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    for (i = 0; i < 4; ++i) {
        wsprintfA(part, LEVELS[i], slot);
        lstrcatA(out, part);
        if (make) {
            CreateDirectoryA(out, NULL);
        }
    }
    wsprintfA(part, "\\Heathen Aging - Save %d.dat", slot);
    lstrcatA(out, part);
    return 1;
}

static int valid_known(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    unsigned int count, i;
    if (len < HA_HEADER || u[0] != HA_MAGIC || u[1] != HA_VERSION || u[2] != HA_GAME
        || u[4] != (unsigned int)*(const int *)ctx) {
        return 0;
    }
    count = u[3];
    if (count > HA_MAX || len != HA_HEADER + count * 8u) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (u[5 + i * 2] == 0u || u[6 + i * 2] > KIND_OWED) {
            return 0;
        }
    }
    return 1;
}

static int known_find(unsigned int who, unsigned int kind) {
    int i;
    for (i = 0; i < g_known_count; ++i) {
        if (g_known[i].identity == who && g_known[i].kind == kind) {
            return i;
        }
    }
    return -1;
}

static void known_drop(unsigned int who, unsigned int kind) {
    int at = known_find(who, kind);
    if (at >= 0) {
        memmove(&g_known[at], &g_known[at + 1], sizeof g_known[0] * (size_t)(g_known_count - at - 1));
        --g_known_count;
        g_dirty = 1;
    }
}

static unsigned int identity(const unsigned char *record);
static unsigned char *rec_at(int index);

/* A full list: the born, former and expecting entries of identities no record of the village holds now (dead and
   gone, buried, left) are dropped.  Graves and owed replacements always stay. */
static void known_prune(void) {
    static unsigned int present[256];
    unsigned int i;
    int n = 0, k;
    for (i = 0; i < g_slots && i < 256u; ++i) {
        const unsigned char *r = rec_at((int)i);
        if (r[R_PRESENT] != 0) {
            present[n++] = identity(r);
        }
    }
    for (k = g_known_count; k-- > 0;) {
        int j, alive = 0;
        if (g_known[k].kind == KIND_GRAVE || g_known[k].kind == KIND_OWED) {
            continue;
        }
        for (j = 0; j < n && !alive; ++j) {
            alive = present[j] == g_known[k].identity;
        }
        if (!alive) {
            memmove(&g_known[k], &g_known[k + 1], sizeof g_known[0] * (size_t)(g_known_count - k - 1));
            --g_known_count;
            g_dirty = 1;
        }
    }
}

static void known_put(unsigned int who, unsigned int kind) {
    if (known_find(who, kind) >= 0) {
        return;
    }
    if (g_known_count >= HA_MAX) {
        known_prune();
    }
    if (g_known_count >= HA_MAX) {
        return;                            /* (cannot happen: see HA_MAX) -- never a live entry evicted */
    }
    g_known[g_known_count].identity = who;
    g_known[g_known_count].kind = kind;
    ++g_known_count;
    g_dirty = 1;
}

static void read_known(int slot) {
    char path[MAX_PATH];
    DWORD got = 0;
    int status;
    unsigned int i;
    vv_sidecar_gate_bind(&g_gate, slot);
    g_load_blocked = 0;
    if (!known_path(slot, path, 0)) {
        vv_sidecar_gate_block(&g_gate);
        g_load_blocked = 1;
        return;
    }
    status = vv_sidecar_load(&g_gate, path, (unsigned char *)g_buffer, sizeof g_buffer, &got, valid_known, &slot);
    g_load_blocked = status == VV_SIDECAR_LOAD_BLOCKED;
    if (status == VV_SIDECAR_LOAD_VALID) {
        /* What this village's catch-up noted before the file was read is kept with it. */
        for (i = 0; i < g_buffer[3]; ++i) {
            if (known_find(g_buffer[5 + i * 2], g_buffer[6 + i * 2]) < 0 && g_known_count < HA_MAX) {
                g_known[g_known_count].identity = g_buffer[5 + i * 2];
                g_known[g_known_count].kind = g_buffer[6 + i * 2];
                ++g_known_count;
            }
        }
    }
    g_synced_at = GetTickCount() - HA_WRITE_MS;
}

static void write_known(void) {
    unsigned int header[5];
    const void *parts[2];
    DWORD sizes[2];
    char path[MAX_PATH];
    if (!g_dirty || g_file_slot == 0 || g_load_blocked || !vv_sidecar_gate_ready(&g_gate, g_file_slot)
        || GetTickCount() - g_synced_at < HA_WRITE_MS || !known_path(g_file_slot, path, 1)) {
        return;
    }
    g_synced_at = GetTickCount();
    header[0] = HA_MAGIC;
    header[1] = HA_VERSION;
    header[2] = HA_GAME;
    header[3] = (unsigned int)g_known_count;
    header[4] = (unsigned int)g_file_slot;
    parts[0] = header;
    sizes[0] = sizeof header;
    parts[1] = g_known;
    sizes[1] = (DWORD)(g_known_count * 8);
    if (vv_sidecar_publish(&g_gate, path, parts, sizes, g_known_count > 0 ? 2 : 1)) {
        g_dirty = 0;
    }
}

/* The slot's file read when the slot is first seen (a lock retried on the gate's throttle), changes written.  A
   different slot: what was known belongs to that village, and the new slot's file is read. */
static void keep_known(void) {
    int slot = vv_game_save_slot(HA_GAME);
    if (slot == 0) {
        return;
    }
    if (slot != g_file_slot) {
        if (g_file_slot != 0) {
            g_synced_at = GetTickCount() - HA_WRITE_MS;
            write_known();                 /* the last village's file first */
            g_known_count = 0;             /* ...and nothing of it here */
        }                                  /* (noted before any slot was known: this village's, kept) */
        g_dirty = g_known_count > 0;
        g_file_slot = slot;
        g_body_count = 0;                  /* another village's bodies, believers and roster */
        g_roster_known = 0;
        memset(g_seen, 0, sizeof g_seen);
        read_known(slot);
    } else if (g_load_blocked && !vv_sidecar_gate_throttled(&g_gate)) {
        read_known(slot);
    }
    write_known();
}

/* A former villager: written down when they turned, or (turned before the row) born in the village and not one
   of this companion's Heathen babies. */
static int former_villager(const unsigned char *record) {
    unsigned int who = identity(record);
    if (known_find(who, KIND_FORMER) >= 0) {
        return 1;
    }
    if (known_find(who, KIND_BORN) >= 0) {
        return 0;
    }
    return record[R_FATHER_NAME] != 0 || record[R_MOTHER_NAME] != 0;
}

/* ---- Heathen graves (Heathens never count: the Village Statistics' Village Elders asks VvfpHeathenAgingGrave) --

   A grave keeps no faction, so a Heathen's grave is written down here: every Heathen body lying in the camp
   (present, health 0 or less, faction set -- this companion's old-age deaths and any other) is watched with the
   number of Roster of the Dead entries there were then; once its presence byte is cleared (the burial, or the
   game's removal of an unburied body), a new entry with its name and age is its grave.  The entries stay where
   the writer put them (the first free of 500), so the entry number is kept in the file. */
#define G_ROSTER 0x5481A8u              /* 500 entries of 0x5C: name +0, age +0x1C (0: free) */
#define G_ROSTER_STRIDE 0x5Cu
#define G_ROSTER_ENTRIES 500
#define ROSTER_AGE 0x1Cu
#define BODIES_MAX 256                 /* every record (the 256 build) */

static struct { int index; unsigned int who; int age; int graves; char name[R_NAME_CAP + 1]; } g_bodies[BODIES_MAX];
static int g_body_count;

static int roster_used(void) {
    int n = 0;
    while (n < G_ROSTER_ENTRIES
           && *(const volatile int *)(UINT_PTR)(G_ROSTER + (unsigned int)n * G_ROSTER_STRIDE + ROSTER_AGE) != 0) {
        ++n;
    }
    return n;
}

static void watch_body(int index, const unsigned char *record) {
    int i;
    for (i = 0; i < g_body_count; ++i) {
        if (g_bodies[i].index == index) {
            return;
        }
    }
    if (g_body_count >= BODIES_MAX) {
        return;
    }
    g_bodies[g_body_count].index = index;
    g_bodies[g_body_count].who = identity(record);
    g_bodies[g_body_count].age = i32(record, R_AGE);
    g_bodies[g_body_count].graves = roster_used();
    lstrcpynA(g_bodies[g_body_count].name, (const char *)(record + R_NAME), R_NAME_CAP + 1);
    ++g_body_count;
}

static void watch_graves(void) {
    unsigned int i;
    int b;
    for (i = 0; i < g_slots; ++i) {
        const unsigned char *r = rec_at((int)i);
        if (r[R_PRESENT] != 0 && r[R_FACTION] != 0 && i32(r, R_HEALTH) <= 0) {
            watch_body((int)i, r);
        }
    }
    for (b = 0; b < g_body_count;) {
        const unsigned char *r = rec_at(g_bodies[b].index);
        if (r[R_PRESENT] != 0 && identity(r) == g_bodies[b].who) {
            ++b;                                       /* still lying there */
            continue;
        }
        {
            int used = roster_used(), e;
            for (e = g_bodies[b].graves; e < used; ++e) {
                const unsigned char *entry = (const unsigned char *)(UINT_PTR)(G_ROSTER + (unsigned int)e * G_ROSTER_STRIDE);
                if (i32(entry, ROSTER_AGE) == g_bodies[b].age
                    && strncmp((const char *)entry, g_bodies[b].name, R_NAME_CAP) == 0
                    && known_find((unsigned int)e + 1u, KIND_GRAVE) < 0) {
                    known_put((unsigned int)e + 1u, KIND_GRAVE);
                    break;
                }
            }
        }
        g_bodies[b] = g_bodies[--g_body_count];        /* buried, or removed unburied */
    }
}

/* ---- identities follow their villager ----------------------------------------------------------------------

   The entries are kept by name, likes and dislikes, which island events, the Custom Island Event, the Mysterious
   Vial, the Crystal of Reflections and the Origins upgrades change, and a rename changes too.  At each look (the
   age credit's throttled pass) the roster is compared with the last look, by the repo's rules (Former Heathens'
   cod_former.inc former_follow): one record renamed with its likes, dislikes and sex unchanged, or records whose
   identity changed in place (identity_in_place.h: same record, name, sex, an age gone on by at most a year, nobody
   moved) -- and every entry of the old identity is carried to the new one.  An old identity two records carried is
   carried nowhere (nothing guessed). */
static unsigned int g_roster[256], g_roster_stable[256], g_roster_keep[256];
static int g_roster_age[256];
static int g_roster_known;

static unsigned int stable_of(const unsigned char *record) {
    unsigned int h = vv_title_identity(record, R_NAME, 0u, R_LIKES, R_DISLIKES, R_PREF_SLOTS);
    h = (h ^ (unsigned int)i32(record, R_SEX)) * 16777619u;
    return h ? h : 1u;
}

static void rekey(const unsigned int *was, int n, unsigned int from, unsigned int to) {
    int i, carried = 0;
    for (i = 0; i < n; ++i) {
        carried += was[i] == from;
    }
    if (from == to || from == 0u || to == 0u || carried != 1) {
        return;
    }
    for (i = 0; i < g_known_count;) {
        if (g_known[i].kind != KIND_GRAVE && g_known[i].kind != KIND_OWED && g_known[i].identity == from) {
            unsigned int kind = g_known[i].kind;
            known_drop(from, kind);
            known_put(to, kind);
            continue;                              /* the list moved under i */
        }
        ++i;
    }
}

/* The believer the age credit last saw in record index is the same villager under the new identity: one whose
   likes or name changed and who turned Heathen before the next look (a Custom Island Event's change, then its
   "Becomes a Heathen") is still seen turning, so a founder or newcomer with no parents is still a former villager.
   (A look, a title or a mask is no part of the identity.) */
static void follow_seen(int index, unsigned int from, unsigned int to) {
    if (index >= 0 && index < 256 && from != 0u && g_seen[index] == from) {
        g_seen[index] = to;
    }
}

static void follow_identities(void) {
    static unsigned int now[256], now_stable[256], now_keep[256];
    static int now_age[256];
    static unsigned char same[256];
    int n = (int)g_slots, i, at = -1, renames = 0, anyone = 0;
    for (i = 0; i < n; ++i) {
        const unsigned char *r = rec_at(i);
        now[i] = now_stable[i] = now_keep[i] = 0u;
        now_age[i] = 0;
        if (r[R_PRESENT] != 0 && r[R_LOOKALIKE] == 0) {
            now[i] = identity(r);
            now_stable[i] = stable_of(r);
            now_keep[i] = vv_identity_keep(r, R_NAME, R_NAME_CAP, R_SEX);
            now_age[i] = i32(r, R_AGE);
            anyone = 1;
        }
    }
    if (g_roster_known && anyone) {
        for (i = 0; i < n; ++i) {
            if (g_roster[i] != now[i] && g_roster[i] != 0u && now[i] != 0u) {
                ++renames;
                at = i;
            }
        }
        if (renames == 1 && g_roster_stable[at] != 0u && g_roster_stable[at] == now_stable[at]) {
            rekey(g_roster, n, g_roster[at], now[at]);
            follow_seen(at, g_roster[at], now[at]);
        } else if (vv_roster_changed_in_place(n, g_roster, g_roster_keep, g_roster_age, now, now_keep, now_age,
                                              same) > 0) {
            for (i = 0; i < n; ++i) {
                if (same[i]) {
                    rekey(g_roster, n, g_roster[i], now[i]);
                    follow_seen(i, g_roster[i], now[i]);
                }
            }
        }
    }
    memcpy(g_roster, now, sizeof(unsigned int) * (size_t)n);
    memcpy(g_roster_stable, now_stable, sizeof(unsigned int) * (size_t)n);
    memcpy(g_roster_keep, now_keep, sizeof(unsigned int) * (size_t)n);
    memcpy(g_roster_age, now_age, sizeof(int) * (size_t)n);
    g_roster_known = anyone;
}

/* ---- who ages ---------------------------------------------------------------------------------------------- */

static int ages(const unsigned char *record) {
    if (record[R_FACTION] == 0 || !living(record)) {
        return 0;
    }
    return g_tribe_row || (g_former_row && former_villager(record))
        || (g_events_row && known_find(identity(record), KIND_EXPECTING) >= 0);   /* an event's pregnancy: until
                                                                                   the birth, as a believer's */
}

/* The age credit, for a living record: 1 a believer (the stock add), 2 an aging Heathen (add here, then the
   executable's own Heathen branch), 0 any other Heathen (that branch alone). */
static int __cdecl credit(unsigned char *record, int units) {
    int answer = 1;
    __try {
        int index = rec_index(record);
        if (GetTickCount() - g_kept_at >= HA_KEEP_MS) {
            g_kept_at = GetTickCount();
            keep_known();
            follow_identities();
            watch_graves();
            if (owed_count() > 0) {
                pay_owed();
            }
        }
        if (record[R_FACTION] == 0) {
            if (index >= 0) {
                g_seen[index] = identity(record);
                known_drop(g_seen[index], KIND_EXPECTING);   /* a believer now: any pregnancy is hers */
            }
        } else if (index >= 0 && g_seen[index] != 0 && g_seen[index] == identity(record)) {
            known_put(g_seen[index], KIND_FORMER);       /* turned Heathen since the last look */
            g_seen[index] = 0;
        }
        if (record[R_FACTION] == 0) {
            /* the stock add */
        } else if (ages(record)) {
            *(int *)(record + R_AGE) += units;
            answer = 2;
        } else {
            answer = 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = record[R_FACTION] == 0 ? 1 : 0;
    }
    return answer;
}

/* ---- the Heathen creator ----------------------------------------------------------------------------------- */

static int living_heathens(void) {
    unsigned int i;
    int n = 0;
    for (i = 0; i < g_slots; ++i) {
        const unsigned char *r = rec_at((int)i);
        n += r[R_FACTION] != 0 && living(r);
    }
    return n;
}

static int free_records(void) {
    unsigned int i;
    int n = 0;
    for (i = 0; i < g_slots; ++i) {
        n += rec_at((int)i)[R_PRESENT] == 0;
    }
    return n;
}

/* A new Heathen by the game's creator; its Faith written afterwards (the top of this file).  -1: no room. */
static int create(int lineage, int skill, int value, int sex, int age, int orange, int red, int role, int faith) {
    int index = ((tc9_fn)(UINT_PTR)G_CREATE_HEATHEN)(g_manager, NULL, lineage, skill, value, sex, age, orange, red,
                                                      role, 1);
    if (index < 0 || (unsigned int)index >= g_slots) {
        return -1;
    }
    *(int *)(rec_at(index) + R_FAITH) = faith;
    return index;
}

static int camp_faith(void) {
    return -38 - ha_rand(30);
}

static unsigned char *random_man(const unsigned char *not_this) {
    unsigned char *men[256];
    unsigned int i;
    int n = 0;
    for (i = 0; i < g_slots; ++i) {
        unsigned char *r = rec_at((int)i);
        if (r != not_this && r[R_FACTION] != 0 && living(r) && i32(r, R_SEX) != 1 && i32(r, R_AGE) >= ADULT) {
            men[n++] = r;
        }
    }
    return n > 0 ? men[ha_rand(n)] : NULL;
}

static void tell_arrived(int index, const char *how) {
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    cod_arrived_fn told = module != NULL
        ? (cod_arrived_fn)(void *)GetProcAddress(module, "VvfpCauseHeathenArrived") : NULL;
    if (told != NULL) {
        told(HA_GAME, index, how);
    }
}

/* The stock camp's set-up of each puzzle role (0x424AC0; the Heathen Mommy as the restored puzzle makes her). */
static int create_role(int role) {
    int index;
    unsigned char *r;
    int i;
    switch (role) {
    case 12: return create(0, 2, 70, -1, 400, 0, 0, 12, -14);
    case 14: return create(0, 3, 90, -1, 540, 0, 0, 14, -74);
    case 15: return create(0, 4, 90, -1, 540, 0, 0, 15, -74);
    case 16: return create(0, 0, 90, 0, 540, 0, 0, 16, -74);
    case 13:
        index = create(0, 2, 90, 0, 1000, 0, 0, 13, -94);
        if (index >= 0) {
            r = rec_at(index);
            for (i = 0; i < 6; ++i) {
                ((float *)(r + R_SKILLS))[i] = *(const float *)(UINT_PTR)G_CHIEF_SKILL;
            }
        }
        return index;
    case 17:
        index = create(0, 1, 70, -1, 400, 0, 0, 17, -25);
        if (index >= 0) {
            unsigned char *father;
            int twins = *(volatile int *)(UINT_PTR)G_TWINS, triplets = *(volatile int *)(UINT_PTR)G_TRIPLETS;
            r = rec_at(index);
            father = random_man(r);
            if (father != NULL) {
                ((tc7_fn)(UINT_PTR)G_CONCEIVE)(r, NULL, i32(father, R_LINEAGE), 1, 50, (int)(UINT_PTR)(father + R_NAME),
                                               i32(father, R_HEAD), i32(father, R_BODY), 1);
            } else {
                ((tc7_fn)(UINT_PTR)G_CONCEIVE)(r, NULL, 1, 1, 50, (int)(UINT_PTR)"Unknown", 2, 2, 1);
            }
            *(volatile int *)(UINT_PTR)G_TWINS = twins;
            *(volatile int *)(UINT_PTR)G_TRIPLETS = triplets;
            *(int *)(r + R_LITTER) = 1;          /* one infant, as the stock Mommy */
            if (i32(r, R_PREGNANT) == 0) {
                *(int *)(r + R_PREGNANT) = 1;
            }
        }
        return index;
    default:
        return -1;
    }
}

/* The stock camp's Faith (0x470E60): five blue Heathens get -5, -9, -16, -23 and -30, every other ordinary one
   -38 - rand(30).  A replacement of one of those five keeps that Faith, so the camp is never harder to convert
   than the stock game's; any other gets -38 - rand(30). */
static int g_replace_faith;
static const char *g_replace_words;   /* the Arrived record's words (NULL: old age) */
static const char *const REPLACED_OLD_AGE = "Replaced a Heathen who died of old age";
static const char *const REPLACED_EVENT = "Replaced a Heathen lost in an island event";

static int create_ordinary(int role, int orange, int red) {
    int faith = g_replace_faith;
    return create(0, ha_rand(6), 5 + ha_rand(5), -1, 400, orange, red, role, faith != 0 ? faith : camp_faith());
}

/* One owed replacement made if there is room: 1 made. */
static int replace(int role, unsigned char orange, unsigned char red) {
    int index;
    int puzzle = puzzle_of_role(role);
    if (puzzle != 0 && !puzzle_done(puzzle)) {
        index = create_role(role);
    } else {
        index = create_ordinary(puzzle != 0 ? 0 : role, orange, red);
    }
    if (index < 0) {
        return 0;
    }
    tell_arrived(index, g_replace_words != NULL ? g_replace_words : REPLACED_OLD_AGE);
    return 1;
}

/* An owed replacement, packed into a file entry: bit 31 set, a number 0..255 (bits 20-27) keeping two alike
   apart, how the one replaced was lost (bit 16: an island event, else old age -- its Arrived record says the real
   cause when it is paid), the Faith kept (its negation, bits 8-15; 0: the camp's -38 - rand(30)), red (7), orange
   (6), the role (0-5). */
#define OWED_EVENT 0x10000u

static unsigned int owed_pack(int role, int orange, int red, int faith, int number) {
    return 0x80000000u | ((unsigned int)(number & 0xFF) << 20) | ((unsigned int)(-faith & 0xFF) << 8)
        | ((unsigned int)(red != 0) << 7) | ((unsigned int)(orange != 0) << 6) | (unsigned int)(role & 0x3F)
        | (g_replace_words == REPLACED_EVENT ? OWED_EVENT : 0u);
}

static int owed_count(void) {
    int i, n = 0;
    for (i = 0; i < g_known_count; ++i) {
        n += g_known[i].kind == KIND_OWED;
    }
    return n;
}

static void owe(int role, unsigned char orange, unsigned char red, int faith) {
    int number;
    for (number = 0; number < 256; ++number) {
        unsigned int packed = owed_pack(role, orange, red, faith, number);
        if (known_find(packed, KIND_OWED) < 0) {
            known_put(packed, KIND_OWED);  /* in the slot's file: kept across a quit and a Change Tribe */
            return;
        }
    }
}

static void drop_owed(void) {
    int i;
    for (i = g_known_count; i-- > 0;) {
        if (g_known[i].kind == KIND_OWED) {
            known_drop(g_known[i].identity, KIND_OWED);
        }
    }
}

static int living_heathens(void);

static void pay_owed(void) {
    int i;
    if (puzzle_done(LAST_HEATHEN) || living_heathens() == 0) {
        drop_owed();                       /* nobody is replaced any more, and never from nothing */
        return;
    }
    for (i = g_known_count; i-- > 0 && free_records() > 0;) {
        if (g_known[i].kind == KIND_OWED) {
            unsigned int packed = g_known[i].identity;
            g_replace_faith = -(int)((packed >> 8) & 0xFF);
            g_replace_words = (packed & OWED_EVENT) ? REPLACED_EVENT : REPLACED_OLD_AGE;   /* the real cause */
            if (!replace((int)(packed & 0x3F), (unsigned char)((packed >> 6) & 1), (unsigned char)((packed >> 7) & 1))) {
                g_replace_faith = 0;
                g_replace_words = NULL;
                return;
            }
            g_replace_faith = 0;
            g_replace_words = NULL;
            known_drop(packed, KIND_OWED);
            i = g_known_count;             /* the list moved */
        }
    }
}

/* ---- a death ----------------------------------------------------------------------------------------------- */

static int keeps_body(const unsigned char *record) {
    return g_bones_all || (g_bones_former && former_villager(record));
}

static void tell_died(int index, int cause) {
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    cod_died_fn told = module != NULL
        ? (cod_died_fn)(void *)GetProcAddress(module, "VvfpCauseDiedAmongHeathens") : NULL;
    if (told != NULL) {
        told(HA_GAME, index, cause);
    }
}

/* The Heathen in `record` is gone (health not yet touched): `how` HA_DIED (a death with the game's `cause`: a body
   when a skeleton row covers them, else a Death record and nothing left) or HA_TAKEN (taken with no body, the
   caller's own record: an island event's disappearance).  Then the replacement.  2 a body was made, 1 not. */
#define HA_DIED 0
#define HA_TAKEN 1
static int gone(unsigned char *record, int how, int cause) {
    known_drop(identity(record), KIND_EXPECTING);
    int role = i32(record, R_ROLE);
    int faith = i32(record, R_FAITH);
    unsigned char orange = record[R_ORANGE], red = record[R_RED];
    int former = former_villager(record);
    int index = rec_index(record);
    int body = how == HA_DIED && keeps_body(record);
    if (body) {
        int deaths = *(volatile int *)(UINT_PTR)G_DEATHS_STAT;
        /* the game's own causes are 0..4 and -1; an island event's (Cause of Death's 5) is told by the event */
        ((tc2_fn)(UINT_PTR)G_SET_HEALTH)(record + R_HEALTH_BLOCK, NULL, 0, cause >= -1 && cause <= 4 ? cause : -1);
        *(volatile int *)(UINT_PTR)G_DEATHS_STAT = deaths;     /* Heathens never count */
        if (puzzle_of_role(role) != 0) {
            *(int *)(record + R_ROLE) = 0;                       /* the role finder finds the new one */
        }
    } else {
        ((tc0_fn)(UINT_PTR)G_STOP)(record, NULL);
        if ((((tc0_fn)(UINT_PTR)G_SELECTED)(record, NULL) & 0xFF) != 0) {
            ((tc0_fn)(UINT_PTR)G_DESELECT)(g_manager, NULL);
        }
        record[R_PRESENT] = 0;
        if (index >= 0 && how == HA_DIED) {
            tell_died(index, cause);
        }
    }
    /* The owner (2026-11-23): once The Last Heathen is solved nobody is replaced (the camp empties over time);
       otherwise a camp Heathen is, and a puzzle Heathen while its puzzle is unsolved (replace), never a former
       villager -- a defection must not grow the camp. */
    if (puzzle_done(LAST_HEATHEN) || (former && puzzle_of_role(role) == 0) || living_heathens() == 0) {
        return body ? 2 : 1;               /* (the last Heathen: none is ever made from nothing) */
    }
    if (puzzle_of_role(role) != 0) {
        /* the same role (replace: a new one while the puzzle is unsolved) */
    } else if (role < 0 || role > 11) {
        role = 0;
    }
    g_replace_faith = !former && (faith == -5 || faith == -9 || faith == -16 || faith == -23 || faith == -30)
        ? faith : 0;
    if (how == HA_TAKEN || !replace(role, orange, red)) {
        /* An island event's disappearance (Codex on #852): its record is the caller's to log next, and the Cause of
           Death companion needs it as it was left -- the presence byte cleared -- so the replacement is owed, made
           at the next look (pay_owed), never in the record before the Disappeared record is written. */
        owe(role, orange, red, g_replace_faith);
    }
    g_replace_faith = 0;
    return body ? 2 : 1;
}

/* Old age took the Heathen in `record` (the roll said so). */
static void died(unsigned char *record) {
    (void)gone(record, HA_DIED, 2);
}

/* ---- babies (the tribe row) -------------------------------------------------------------------------------- */

static int clamp_head(int h) {
    return h < 0 ? 0 : h > 29 ? 29 : h;
}

static void copy_name(unsigned char *to, const unsigned char *from, unsigned int cap) {
    unsigned int i;
    for (i = 0; i + 1 < cap && from[i] != 0; ++i) {
        to[i] = from[i];
    }
    for (; i < cap; ++i) {
        to[i] = 0;
    }
}

/* A baby born among the Heathens, in the logs as every birth (the owner, 2026-11-22: the logs record the Heathens
   too): its Birth record in the Births and Conceptions log ("VVFP Parentage Export.dll" WriteParentageBirthLitter,
   the parents from the baby's own record, marked "Faction: Heathen" by that DLL), and the Cause of Death
   companion told it is a birth, never an arrival (VvfpCauseNoteArrival) -- each only when that companion is
   already in the game (GetModuleHandleA never loads one).  The name is handed over, so the Births log's own
   last-name rules (the believers' births) are never applied to it. */
typedef int (__stdcall *pe_birth_fn)(int game, const char *child, int child_head, int child_body,
                                     const char *mother, int mother_head, int mother_body,
                                     const char *father, int father_head, int father_body,
                                     const void *child_record, int litter);
typedef void (__stdcall *cod_note_fn)(int game, const void *record);

static void tell_born(unsigned char *baby, int litter) {
    HMODULE cause = GetModuleHandleA("VVFP Cause of Death.dll");
    HMODULE parentage = GetModuleHandleA("VVFP Parentage Export.dll");
    cod_note_fn note = cause != NULL ? (cod_note_fn)(void *)GetProcAddress(cause, "VvfpCauseNoteArrival") : NULL;
    pe_birth_fn birth = parentage != NULL
        ? (pe_birth_fn)(void *)GetProcAddress(parentage, "WriteParentageBirthLitter") : NULL;
    if (note != NULL) {
        note(HA_GAME, baby);
    }
    if (birth != NULL && baby[R_NAME] != 0) {
        (void)birth(HA_GAME, (const char *)(baby + R_NAME), i32(baby, R_HEAD), i32(baby, R_BODY), NULL, -1, -1, NULL,
                    -1, -1, baby, litter);
    }
}

/* The birth, 40 units after conception, when there is room for every baby. */
static void deliver(unsigned char *mother) {
    int litter = i32(mother, R_LITTER), i;
    if (litter < 1) {
        litter = 1;
    } else if (litter > 3) {
        litter = 3;
    }
    if (free_records() < litter + HA_ROOM_KEPT) {
        return;                     /* waits until the village's own births keep their HA_ROOM_KEPT records */
    }
    for (i = 0; i < litter; ++i) {
        int fh = i32(mother, R_BABY_FATHER_HEAD), mh = i32(mother, R_HEAD);
        int index = create(i32(mother, R_LINEAGE), i32(mother, R_BABY_SKILL), i32(mother, R_BABY_VALUE), -1,
                           DELIVERY, 0, 0, 0, camp_faith());
        unsigned char *baby;
        if (index < 0) {
            break;
        }
        baby = rec_at(index);
        copy_name(baby + R_FATHER_NAME, mother + R_BABY_FATHER_NAME, R_PARENT_NAME_CAP);
        copy_name(baby + R_MOTHER_NAME, mother + R_NAME, R_PARENT_NAME_CAP);
        *(int *)(baby + R_FATHER_HEAD) = fh;
        *(int *)(baby + R_FATHER_BODY) = i32(mother, R_BABY_FATHER_BODY);
        *(int *)(baby + R_MOTHER_HEAD) = mh;
        *(int *)(baby + R_MOTHER_BODY) = i32(mother, R_BODY);
        if (ha_rand(100) < 95) {
            *(int *)(baby + R_HEAD) = clamp_head((fh + mh) / 2 + ha_rand(3) - 1);
        }
        known_put(identity(baby), KIND_BORN);
        tell_born(baby, litter);
    }
    *(int *)(mother + R_PREGNANT) = 0;
    *(int *)(mother + R_LITTER) = 0;
    ((tc1_fn)(UINT_PTR)G_CARRY)(mother, NULL, -1);
    known_drop(identity(mother), KIND_EXPECTING);
}

static void maybe_conceive(unsigned char *woman) {
    unsigned char *father;
    int twins, triplets;
    if (i32(woman, R_SEX) != 1 || i32(woman, R_ROLE) == 17 || i32(woman, R_PREGNANT) != 0
        || i32(woman, R_AGE) < ADULT || i32(woman, R_AGE) > BIRTH_LAST || ha_rand(CONCEIVE_IN) != 0
        || free_records() <= HA_ROOM_KEPT || puzzle_done(LAST_HEATHEN) || (father = random_man(woman)) == NULL) {
        return;
    }
    twins = *(volatile int *)(UINT_PTR)G_TWINS;
    triplets = *(volatile int *)(UINT_PTR)G_TRIPLETS;
    ((tc7_fn)(UINT_PTR)G_CONCEIVE)(woman, NULL, i32(father, R_LINEAGE), 0, 0, (int)(UINT_PTR)(father + R_NAME),
                                   i32(father, R_HEAD), i32(father, R_BODY), 1);
    *(volatile int *)(UINT_PTR)G_TWINS = twins;
    *(volatile int *)(UINT_PTR)G_TRIPLETS = triplets;
    if (i32(woman, R_PREGNANT) == 0) {
        *(int *)(woman + R_PREGNANT) = 1;
    }
    known_put(identity(woman), KIND_EXPECTING);
}

/* ---- the life tick ----------------------------------------------------------------------------------------- */

/* One age unit for an aging Heathen: 1 done, 0 the stock skip. */
static int __cdecl unit(unsigned char *record) {
    int answer = 0;
    __try {
        int processed, threshold;
        if (!ages(record) || i32(record, R_PROCESSED) >= i32(record, R_AGE)) {
            return 0;
        }
        if (owed_count() > 0) {
            pay_owed();
        }
        processed = i32(record, R_PROCESSED);
        threshold = 160 * *(const volatile int *)(UINT_PTR)G_MEDICINE + 940;
        *(int *)(record + R_PROCESSED) = processed + 1;
        answer = 1;
        if (processed % 20 == 0 && processed > threshold
            && ha_rand(100) < 10 * (processed / 20 - threshold / 20)) {
            died(record);
            return 1;
        }
        if (g_tribe_row || g_events_row) {
            int conceived = i32(record, R_PREGNANT);
            if (conceived != 0 && i32(record, R_ROLE) != 17 && conceived + DELIVERY < processed
                && known_find(identity(record), KIND_EXPECTING) >= 0 && !puzzle_done(LAST_HEATHEN)) {
                deliver(record);
            } else if (conceived == 0 && g_tribe_row) {
                maybe_conceive(record);
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return answer;
}

/* ---- the splices ------------------------------------------------------------------------------------------- */

static const unsigned int g_credit_add = CREDIT_ADD;
static const unsigned int g_tick_believer = TICK_BELIEVER;
static const unsigned int g_tick_heathen = TICK_HEATHEN;
static const unsigned int g_tick_next = TICK_NEXT;

/* In place of 0x470077's `cmp byte [esi+0x1CEC], bl; mov edi, eax; jne`. */
__declspec(naked) static void credit_stub(void) {
    __asm {
        mov edi, eax
        pushad
        push edi
        push esi
        call credit
        add esp, 8
        mov dword ptr [g_credit_result], eax
        popad
        cmp dword ptr [g_credit_result], 1
        jne not_believer
        jmp dword ptr [g_credit_add]
    not_believer:
        jmp dword ptr [g_skip_target]
    }
}

/* In place of 0x472CB7's `cmp byte [esi+0xB0], 0; je 0x472CDB` (esi = record + 0x1C3C). */
__declspec(naked) static void tick_stub(void) {
    __asm {
        cmp byte ptr [esi + 0xB0], 0
        jne heathen
        jmp dword ptr [g_tick_believer]
    heathen:
        pushad
        lea eax, [esi - 0x1C3C]
        push eax
        call unit
        add esp, 4
        mov dword ptr [g_tick_result], eax
        popad
        cmp dword ptr [g_tick_result], 0
        jne aged
        jmp dword ptr [g_tick_heathen]
    aged:
        mov byte ptr [esp + 0x12], 0
        jmp dword ptr [g_tick_next]
    }
}

static const unsigned char CREDIT_STOCK[10] = { 0x38, 0x9E, 0xEC, 0x1C, 0x00, 0x00, 0x8B, 0xF8, 0x75, 0x0C };
static const unsigned char CREDIT_STATS[10] = { 0x38, 0x9E, 0xEC, 0x1C, 0x00, 0x00, 0x8B, 0xF8, 0x75, 0x38 };
static const unsigned char TICK_STOCK[9] = { 0x80, 0xBE, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x74, 0x1B };

/* "VVFP Statistics Export.dll" (Village Elders): 1 when Roster of the Dead entry `entry` of `game` is a Heathen's
   grave (written down above), else 0 -- a Heathen never counts. */
int __stdcall VvfpHeathenAgingGrave(int game, int entry) {
    if (game != HA_GAME || entry < 0 || entry >= G_ROSTER_ENTRIES) {
        return 0;
    }
    __try {
        watch_graves();                    /* a burial since the last throttled look (a save right after it) */
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return known_find((unsigned int)entry + 1u, KIND_GRAVE) >= 0;
}

/* "VVFP Save Reset.dll" (Start Over or a deleted tribe in `slot`, before it deletes the slot's folder): the former
   villagers, Heathen babies, expecting mothers and Heathen graves kept for that village are forgotten, the owed
   replacements and watched bodies with them, and the slot's file is read afresh when next seen (gone with the
   folder), so none of it is written back into the new village.  Another slot's village is left alone. */
void __stdcall VvfpHeathenAgingVillageReset(int game, int slot) {
    if (game != HA_GAME || slot < 1 || slot > 5) {
        return;
    }
    if (g_file_slot != 0 && slot != g_file_slot) {
        return;
    }
    g_known_count = 0;
    g_dirty = 0;
    g_file_slot = 0;
    g_body_count = 0;
    g_roster_known = 0;
    memset(g_seen, 0, sizeof g_seen);
}

/* ---- island events (the owner, 2026-11-23: "Heathens CAN die, vanish and get pregnant from events") ------------

   "VVFP Story Upgrades.dll" hands an island event's death or disappearance of an ordinary Heathen here, so it follows
   the Heathens' own rules: a body only when a skeleton row covers them (else nothing is left, a Death record says so),
   the statistics' death counter put back, and the replacement (a camp Heathen only, never a former villager, nobody
   once The Last Heathen is solved, never from nothing).  `how` 0 a death (the game's `cause`), 1 taken with no body
   (a disappearance or a death whose body is not recovered: the event's own record).  2 a body was made (the event
   then tells its cause as for any villager), 1 taken, 0 not this companion's (not installed, not a living Heathen). */
int __stdcall VvfpHeathenAgingEventGone(int game, int index, int how, int cause) {
    int answer = 0;
    unsigned char *record;
    if (!g_installed || !g_events_row || game != HA_GAME || index < 0 || (unsigned int)index >= g_slots) {
        return 0;
    }
    record = rec_at(index);
    if (record[R_FACTION] == 0 || !living(record)) {
        return 0;
    }
    __try {
        g_replace_words = REPLACED_EVENT;
        answer = gone(record, how == 1 ? HA_TAKEN : HA_DIED, cause);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = 0;
    }
    g_replace_words = NULL;
    return answer;
}

/* An island event's pregnancy of the ordinary Heathen in record `mother` -- only ever with a Heathen father (the
   owner: never a Heathen and a believer): `father` a Heathen's record, or -1 for a random adult Heathen man of the
   camp.  The game's own conception 0x465E00 (the twins counters put back: Heathens never count), the litter as the
   event asks (1-3, as many as there is room for beside the village's own HA_ROOM_KEPT), and the mother kept as expecting a Heathen baby this companion
   delivers 40 units later (she ages until then); `now` 1: born at once (a nursing baby).  Nothing once The Last
   Heathen is solved (no Heathen baby is born then), with no room, no father or a pregnancy already.  The babies on
   their way (or born), 0 none. */
int __stdcall VvfpHeathenAgingEventPregnancy(int game, int mother, int father, int litter, int now) {
    unsigned char *woman, *man;
    int twins, triplets, babies = 0;
    if (!g_installed || !g_events_row || game != HA_GAME || mother < 0 || (unsigned int)mother >= g_slots) {
        return 0;
    }
    woman = rec_at(mother);
    if (woman[R_FACTION] == 0 || !living(woman) || i32(woman, R_PREGNANT) != 0 || puzzle_done(LAST_HEATHEN)
        || free_records() <= HA_ROOM_KEPT) {      /* the village's own births keep their records, as for the tribe's */
        return 0;
    }
    man = father >= 0 && (unsigned int)father < g_slots ? rec_at(father) : random_man(woman);
    if (man == NULL || man == woman || man[R_FACTION] == 0 || !living(man)) {
        return 0;
    }
    __try {
        twins = *(volatile int *)(UINT_PTR)G_TWINS;
        triplets = *(volatile int *)(UINT_PTR)G_TRIPLETS;
        ((tc7_fn)(UINT_PTR)G_CONCEIVE)(woman, NULL, i32(man, R_LINEAGE), 0, 0, (int)(UINT_PTR)(man + R_NAME),
                                       i32(man, R_HEAD), i32(man, R_BODY), 1);
        *(volatile int *)(UINT_PTR)G_TWINS = twins;
        *(volatile int *)(UINT_PTR)G_TRIPLETS = triplets;
        if (i32(woman, R_PREGNANT) == 0) {
            *(int *)(woman + R_PREGNANT) = i32(woman, R_PROCESSED) > 0 ? i32(woman, R_PROCESSED) : 1;
        }
        babies = litter < 1 ? 1 : litter > 3 ? 3 : litter;
        if (babies > free_records() - HA_ROOM_KEPT) {
            babies = free_records() - HA_ROOM_KEPT;
        }
        *(int *)(woman + R_LITTER) = babies;
        known_put(identity(woman), KIND_EXPECTING);
        if (now) {
            deliver(woman);                    /* (no room: she stays expecting, born later) */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        babies = 0;
    }
    return babies;
}

/* 1 when every site is installed, else 0. */
int __stdcall VvfpHeathenAgingInstalled(void) {
    return g_installed;
}

/* Called once by the patcher's start-up chain before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[HA_SITES];
    const unsigned char *credit_bytes;
    unsigned int manager_rva;
    (void)shipped;
    if (g_installed || game != HA_GAME) {
        return;
    }
    g_former_row = vvfp_patcher_file_exists(HA_FLAG_FORMER);
    g_tribe_row = vvfp_patcher_file_exists(HA_FLAG_TRIBE);
    g_bones_all = vvfp_patcher_file_exists(HA_FLAG_BONES_ALL);
    g_bones_former = !g_bones_all && vvfp_patcher_file_exists(HA_FLAG_BONES_FORMER);
    g_events_row = vvfp_patcher_file_exists(HA_FLAG_EVENTS);
    if (!g_former_row && !g_tribe_row && !g_events_row) {
        return;
    }
    vv5_villager_table((const unsigned char *)GetModuleHandleA(NULL), &manager_rva, &g_slots);
    g_manager = (unsigned char *)GetModuleHandleA(NULL) + manager_rva;
    g_records = g_manager + 0x48;
    if (g_slots > 256u) {
        return;
    }
    if (vvfp_site_holds(SITE_CREDIT, CREDIT_STOCK, 10)) {
        credit_bytes = CREDIT_STOCK;
    } else if (vvfp_site_holds(SITE_CREDIT, CREDIT_STATS, 10)) {
        credit_bytes = CREDIT_STATS;
    } else {
        return;
    }
    g_skip_target = SITE_CREDIT + 10u + (unsigned int)(signed char)credit_bytes[9];
    vvfp_site_branch(&sites[0], SITE_CREDIT, 10, credit_bytes, 0xE9, (const void *)credit_stub);
    vvfp_site_branch(&sites[1], SITE_TICK, 9, TICK_STOCK, 0xE9, (const void *)tick_stub);
    if (vvfp_install_sites(sites, HA_SITES)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
