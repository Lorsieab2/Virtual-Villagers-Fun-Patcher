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

   WHAT THIS DOES (five run-time splices, all or none, stock bytes checked first: native/shared/install_sites.h):
     0x470077  the age credit's faction test: a believer goes on as before; an AGING Heathen (below) gets the same
               units added to its age (what 0x46F7F0 does) and then takes the Heathen branch the executable has
               there (0x47008D stock, or 0x4700B9 when the Village Statistics rows skip the Oldest Villager maximum
               for Heathens: `jne` 0C or 38 -- both accepted, the branch's own target followed), so a Heathen is
               never the Oldest Villager where the statistics say so; everyone else as the stock game.
               A living believer seen here is remembered by identity (who turned Heathen from our village).
     0x472CB7  the life tick's Heathen skip: an aging Heathen with an age unit due gets ONE unit, exactly the
               believer's old-age rule (0x472FC6..0x47304A: at each whole year of the processed age past
               1,100 + 160 x (Medicine - 1) units, rand(100) < 10 x years over sets health 0, cause 2 Old age,
               through SetHealth 0x4758B0), and with the tribe row its pregnancy and birth (below); the processed
               age goes up by one and the pass is marked not done (the tick's own [esp+0x12]), as a believer's
               unit is.  Nothing else of the believer's unit runs: a Heathen still never eats, starves, falls
               sick, loses health, drifts in Faith or works.  Any other Heathen: the stock skip.
     0x4669E0  to-a-Heathen (SetFaith's conversion at Faith 0 or below: the Faith drift, The Breaking Point,
               preaching gone wrong, island events, The Spa, The Cracked Mask, a Custom Island Event's "Becomes a
               Heathen", Pick Island Event) -- its first instructions, replayed exactly;
     0x415D0C, 0x416C5B  The Spa's and The Cracked Mask's direct `call 0x466880` (faction 1).
               At these three a believer the age credit has seen alive (so never a record the Heathen creator is
               filling: its SetFaith runs before any frame sees it) is written down as a former villager.

   WHO IS A FORMER VILLAGER.  The identity (native/shared/custom_titles.h vv_title_identity: name, likes,
   dislikes) of every believer seen turning Heathen, kept per save slot in
       <Documents>\LDW\<game>\Virtual Villagers Fun Patcher\Save <S>\Data\Heathen Aging\
           Heathen Aging - Save <S>.dat
   (native/shared/sidecar_io.h: atomic, an unreadable file never replaced, an invalid one set aside), with the
   Heathen babies this companion delivered (born Heathens, never former villagers).  A Heathen who turned before
   the row was installed is known by the parents on the record (+0x1BC0 / +0x1BD9: born in the village; the camp's
   and the Barrel's Heathens have none) unless the file says they were born a Heathen.  The file is written at most
   once a second from the age credit's first record, never inside the life tick.

   A DEATH.  The old age's SetHealth makes the body as for a believer when a skeleton row says so for this Heathen
   (All Heathens, or Former Villagers and a former villager): the believers bury it through their own "Burying
   the dead" (a grave, the Cause of Death companion's Death record at the burial; unburied, the game's removal
   after 240 units), a puzzle Heathen's body losing its role so the role finder 0x470690 finds the new one.
   Otherwise no body is made: the activity stops (0x473440), the selection goes if it is theirs, the presence
   byte is cleared (as the game's own removals do) and the Cause of Death companion writes the Death record, Old
   age, "no grave (died among the Heathens: nothing was left)" (VvfpCauseDiedAmongHeathens).  Either way the
   statistics' villager-death counter is put back (Heathens never count: the owner).
   A REPLACEMENT is made at once, in the same tick, by the game's one Heathen creator 0x46FD20 as the stock camp
   makes one: an ordinary Heathen keeps the dead one's camp role (0..11) and mask (blue, orange or red), age 400,
   random sex, Faith -38 - rand(30); a former villager is replaced by an ordinary blue, orange or red (13 : 7 : 3,
   the camp's own mix) with role 0; a puzzle Heathen whose puzzle is not solved yet by a new one in the same role,
   set up exactly as the stock camp sets that role up (the Doctor, Chief with every skill 100, the three Masters;
   the Heathen Mommy with her infant, its father an adult Heathen man when there is one).  Its Faith is written
   after the creator (the creator's own SetFaith would run to-a-Heathen on a record still a believer: its "stopped
   believing" message and the Cause of Death companion's "Left the tribe" record).  The Cause of Death companion
   writes its Arrived record (VvfpCauseHeathenArrived).  A full table: the replacement waits, and is made at the
   next age unit that has room.

   HEATHEN BABIES (the tribe row only).  An adult Heathen woman (14 to 45 years), not expecting, not the Heathen
   Mommy, with a living adult Heathen man in the camp, conceives on 1 age unit in 400 (about 1 year in 20) through
   the game's conception routine 0x465E00 forced (father: a random adult Heathen man), only while at least
   HA_ROOM_KEPT records stay free for the village's own births.  The Village Statistics' twins and triplets are put
   back as the Story upgrades' Custom Island Event does for a Heathen carrier.  The birth comes as a believer's
   does (40 units after conception): each baby is made by the Heathen creator at age 40 with the parents' names,
   heads and bodies on its record (the head the stock birth's rule: the parents' average +-1 on 95%), Faith
   -38 - rand(30); then the pregnancy and the carry are cleared.  No room: the birth waits.  Only a pregnancy this
   companion conceived (its mother kept in the file as expecting) is delivered among the Heathens: one from before a
   believer turned Heathen, and the Heathen Mommy's infant (her puzzle shows her carrying it), wait for them to
   rejoin the tribe, as in the stock game.

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

#define HA_GAME 5
#define HA_FLAG_FORMER "VVFP Heathen Aging Former.txt"
#define HA_FLAG_TRIBE "VVFP Heathen Aging Tribe.txt"
#define HA_FLAG_BONES_FORMER "VVFP Heathen Skeletons Former.txt"
#define HA_FLAG_BONES_ALL "VVFP Heathen Skeletons All.txt"

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
#define CONCEIVE_IN 400          /* 1 age unit in 400 */
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
#define SITE_TO_HEATHEN 0x4669E0u
#define TO_HEATHEN_ON 0x4669E5u
#define SITE_SPA 0x415D0Cu
#define SITE_MASK 0x416C5Bu
#define G_FACTION_SET 0x466880u
#define HA_SITES 5

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
static int g_former_row, g_tribe_row, g_bones_former, g_bones_all;
static unsigned char *g_manager;
static unsigned char *g_records;
static unsigned int g_slots;
static unsigned int g_skip_target;     /* the credit's own Heathen branch */
static int g_credit_result;
static int g_tick_result;

/* Living believers the age credit has seen, by slot. */
static unsigned int g_seen[256];

/* Replacements still owed (a full table): the kind, and the role / masks. */
#define OWED_MAX 32
static struct { int role; unsigned char orange, red; } g_owed[OWED_MAX];
static int g_owed_count;

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

static int puzzle_done(int puzzle) {
    return *(const volatile int *)(UINT_PTR)(G_PUZZLE_PROGRESS + (unsigned int)puzzle * 8u)
        >= *(const volatile int *)(UINT_PTR)(G_PUZZLE_NEEDED + (unsigned int)puzzle * 4u);
}

/* ---- the file of former villagers ------------------------------------------------------------------------- */

#define HA_MAGIC 0x31414856u     /* 'VHA1' */
#define HA_VERSION 1u
#define HA_MAX 1024
#define HA_HEADER 20u
#define KIND_BORN 0u             /* born a Heathen (a baby this companion delivered) */
#define KIND_FORMER 1u           /* a believer who turned Heathen */
#define KIND_EXPECTING 2u        /* a Heathen woman expecting a Heathen baby this companion conceived */
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
        || u[3] != (unsigned int)*(const int *)ctx) {
        return 0;
    }
    count = u[4];
    if (count > HA_MAX || len != HA_HEADER + count * 8u) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (u[5 + i * 2] == 0u || u[6 + i * 2] > KIND_EXPECTING) {
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

static void known_put(unsigned int who, unsigned int kind) {
    if (known_find(who, kind) >= 0) {
        return;
    }
    if (g_known_count >= HA_MAX) {
        memmove(&g_known[0], &g_known[1], sizeof g_known[0] * (HA_MAX - 1));   /* the oldest goes */
        g_known_count = HA_MAX - 1;
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
        for (i = 0; i < g_buffer[4]; ++i) {
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
    header[3] = (unsigned int)g_file_slot;
    header[4] = (unsigned int)g_known_count;
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
        g_known_count = 0;
        g_dirty = 0;
        g_file_slot = slot;
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

/* ---- who ages ---------------------------------------------------------------------------------------------- */

static int ages(const unsigned char *record) {
    if (record[R_FACTION] == 0 || !living(record)) {
        return 0;
    }
    return g_tribe_row || (g_former_row && former_villager(record));
}

/* A believer about to become a Heathen, at one of the three sites. */
static void __cdecl turning(unsigned char *record) {
    __try {
        int index = rec_index(record);
        if (index >= 0 && record[R_FACTION] == 0 && living(record) && g_seen[index] != 0
            && g_seen[index] == identity(record)) {
            known_put(g_seen[index], KIND_FORMER);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
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
        }
        if (record[R_FACTION] == 0) {
            if (index >= 0) {
                g_seen[index] = identity(record);
            }
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

static int create_ordinary(int role, int orange, int red) {
    return create(0, ha_rand(6), 5 + ha_rand(5), -1, 400, orange, red, role, camp_faith());
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
    tell_arrived(index, "Replaced a Heathen who died of old age");
    return 1;
}

static void owe(int role, unsigned char orange, unsigned char red) {
    if (g_owed_count < OWED_MAX) {
        g_owed[g_owed_count].role = role;
        g_owed[g_owed_count].orange = orange;
        g_owed[g_owed_count].red = red;
        ++g_owed_count;
    }
}

static void pay_owed(void) {
    while (g_owed_count > 0 && free_records() > 0) {
        --g_owed_count;
        if (!replace(g_owed[g_owed_count].role, g_owed[g_owed_count].orange, g_owed[g_owed_count].red)) {
            ++g_owed_count;
            return;
        }
    }
}

/* ---- a death ----------------------------------------------------------------------------------------------- */

static int keeps_body(const unsigned char *record) {
    return g_bones_all || (g_bones_former && former_villager(record));
}

static void tell_died(int index) {
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    cod_died_fn told = module != NULL
        ? (cod_died_fn)(void *)GetProcAddress(module, "VvfpCauseDiedAmongHeathens") : NULL;
    if (told != NULL) {
        told(HA_GAME, index, 2);
    }
}

/* Old age took the Heathen in `record` (the roll said so; health not yet touched). */
static void died(unsigned char *record) {
    int role = i32(record, R_ROLE);
    unsigned char orange = record[R_ORANGE], red = record[R_RED];
    int former = former_villager(record);
    int index = rec_index(record);
    if (keeps_body(record)) {
        int deaths = *(volatile int *)(UINT_PTR)G_DEATHS_STAT;
        ((tc2_fn)(UINT_PTR)G_SET_HEALTH)(record + R_HEALTH_BLOCK, NULL, 0, 2);
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
        if (index >= 0) {
            tell_died(index);
        }
    }
    if (puzzle_of_role(role) != 0) {
        /* the same role (replace: a new one while the puzzle is unsolved) */
    } else if (former) {
        role = 0;                                              /* a former villager: an ordinary newcomer */
        switch (ha_rand(23)) {
        default: orange = 0; red = 0; break;
        case 13: case 14: case 15: case 16: case 17: case 18: case 19: orange = 1; red = 0; break;
        case 20: case 21: case 22: orange = 0; red = 1; break;
        }
    } else if (role < 0 || role > 11) {
        role = 0;
    }
    if (!replace(role, orange, red)) {
        owe(role, orange, red);
    }
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

/* The birth, 40 units after conception, when there is room for every baby. */
static void deliver(unsigned char *mother) {
    int litter = i32(mother, R_LITTER), i;
    if (litter < 1) {
        litter = 1;
    } else if (litter > 3) {
        litter = 3;
    }
    if (free_records() < litter) {
        return;                                                /* waits for room */
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
        || free_records() <= HA_ROOM_KEPT || (father = random_man(woman)) == NULL) {
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
        if (g_owed_count > 0) {
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
        if (g_tribe_row) {
            int conceived = i32(record, R_PREGNANT);
            if (conceived != 0 && i32(record, R_ROLE) != 17 && conceived + DELIVERY < processed
                && known_find(identity(record), KIND_EXPECTING) >= 0) {
                deliver(record);
            } else if (conceived == 0) {
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
static const unsigned int g_to_heathen_on = TO_HEATHEN_ON;
static const unsigned int g_faction_set = G_FACTION_SET;

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

/* In place of 0x4669E0's `push esi; push -1; mov esi, ecx`. */
__declspec(naked) static void to_heathen_stub(void) {
    __asm {
        pushad
        push ecx
        call turning
        add esp, 4
        popad
        push esi
        push -1
        mov esi, ecx
        jmp dword ptr [g_to_heathen_on]
    }
}

/* In place of The Spa's and The Cracked Mask's `call 0x466880`. */
__declspec(naked) static void faction_stub(void) {
    __asm {
        pushad
        push ecx
        call turning
        add esp, 4
        popad
        jmp dword ptr [g_faction_set]
    }
}

static const unsigned char CREDIT_STOCK[10] = { 0x38, 0x9E, 0xEC, 0x1C, 0x00, 0x00, 0x8B, 0xF8, 0x75, 0x0C };
static const unsigned char CREDIT_STATS[10] = { 0x38, 0x9E, 0xEC, 0x1C, 0x00, 0x00, 0x8B, 0xF8, 0x75, 0x38 };
static const unsigned char TICK_STOCK[9] = { 0x80, 0xBE, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x74, 0x1B };
static const unsigned char TO_HEATHEN_STOCK[5] = { 0x56, 0x6A, 0xFF, 0x8B, 0xF1 };
static unsigned char g_spa_stock[5], g_mask_stock[5];

static void call_bytes(unsigned char *out, unsigned int va, unsigned int target) {
    unsigned int rel = target - (va + 5u);
    out[0] = 0xE8;
    memcpy(out + 1, &rel, 4);
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
    if (!g_former_row && !g_tribe_row) {
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
    call_bytes(g_spa_stock, SITE_SPA, G_FACTION_SET);
    call_bytes(g_mask_stock, SITE_MASK, G_FACTION_SET);
    vvfp_site_branch(&sites[0], SITE_CREDIT, 10, credit_bytes, 0xE9, (const void *)credit_stub);
    vvfp_site_branch(&sites[1], SITE_TICK, 9, TICK_STOCK, 0xE9, (const void *)tick_stub);
    vvfp_site_branch(&sites[2], SITE_TO_HEATHEN, 5, TO_HEATHEN_STOCK, 0xE9, (const void *)to_heathen_stub);
    vvfp_site_branch(&sites[3], SITE_SPA, 5, g_spa_stock, 0xE8, (const void *)faction_stub);
    vvfp_site_branch(&sites[4], SITE_MASK, 5, g_mask_stock, 0xE8, (const void *)faction_stub);
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
