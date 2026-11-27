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
   age; live and in the load-time catch-up) skips a Heathen at 0x472CB7: it copies the age into the processed age, clears the sick byte, and nothing else
   runs (no eating, starving, sickness, health, Faith drift, old age or birth).  An Origins Time Warp, and Story /
   Cheat Upgrades' time skip that runs it one warp at a time, do NOT go through the age credit: the Origins
   companion (native/vv5_task9_origins vv5_time_warp_apply) writes the ages itself, so it asks this companion's
   VvfpHeathenAgingAges(record) which Heathens it ages and credits those too (#860); their old age then comes
   through the life tick, one unit at a time, as after live aging.

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
   the Heathen Mommy with her infant, its other parent a named adult Heathen of either sex, of her own family when
   there is one: mommy_parent).  Its Faith is written
   after the creator (the creator's own SetFaith would run to-a-Heathen on a record still a believer: its "stopped
   believing" message and the Cause of Death companion's "Left the tribe" record).  The Cause of Death companion
   writes its Arrived record (VvfpCauseHeathenArrived).  A full table: the replacement waits (kept per save slot),
   and is made by the age credit's throttled pass as soon as a record is free.

   HEATHEN BABIES (the tribe row only; no new conception once The Last Heathen is solved).  An adult Heathen woman (14 to 45 years), not expecting, not the Heathen
   Mommy, with a living adult Heathen man in the camp, conceives on 1 age unit in TRIBE_UNITS_PER_BABY (240) x the
   number of such women (about one baby for the whole tribe every 24 real hours on Normal: the owner, 2026-11-25) through
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

   HEATHEN TRIBE EXPANSION AND EVOLUTION (the row's flag "VVFP Heathen Tribe Evolution.txt", v1.35.101;
   docs/heathen-tribe-expansion-design.md and the owner's decisions of 2026-11-26 in
   docs/heathen-tribe-expansion-decisions.md; the shared names in native/shared/heathen_evo.h).  The flag stands
   for the three rows it folds -- every Heathen ages and has children, every Heathen leaves a skeleton, island
   events carry Heathens -- and adds, all drawn from this companion's own xorshift (never the game's rand):
     * THE BIRTHS SLIDER (0.1x-10x, "VVFP Heathen Tribe Births.txt", 1x when missing): each eligible woman (as
       above, in a couple with a man) rolls 1 in 2,400 x W / t a unit (t tenths, W such women), and births go on
       after The Last Heathen while a Heathen woman and man are alive (decisions 1-3);
     * COUPLES (decision 15; the owner, 2026-11-26: "same sex yes"): any two adult Heathens, neither in a couple,
       not kin by their records (parent and child, full or half siblings: the parents' names, heads and bodies),
       pair for life -- until one dies, converts or leaves -- at most one new couple a look and only when the
       village's clock has moved (gradually, never a flood of records on install).  A woman's babies are her
       man's; a couple of the same sex has babies only through island events (VvfpHeathenAgingEventPregnancy
       takes any two).  Kept per save slot in "...\Save <S>\Data\Heathen Couples\Heathen Couples - Save
       <S>.dat" (heathen_evo.h section 5), following their identities as the file above does; each new couple
       gets a "Couple formed" record (WriteParentageHeathenCouple, when that export is there);
     * LITTERS: single, twins 5.25%, triplets 1.75% (the stock odds without the Medicine 3 gate), as many as the
       room allows; every forced conception -- the tribe's, the Heathen Mommy's infant, an island event's -- gets
       its Conception record (WriteParentageRecordWithFather: the game's own hook skips forced conceptions);
     * ARRIVALS (0-10x, "VVFP Heathen Arrivals.txt", off when missing): on 1 unit in 4,800 / t of the village's
       clock (the age credit of the first living record), a group of 1 to 4 joins the camp -- half the groups of
       two or more a couple with 0-2 children of theirs aged 2-12 -- by the game's own Heathen creator (the stock
       camp's spawn point), roles 0-11 as the stock camp's, each with its Arrived record.  Before The Last Heathen
       only while a Heathen is alive (never from nothing while the puzzle can still be solved); after it, whether
       or not anyone is (decision 1 and the design's "arrivals continue after The Last Heathen");
     * MASKS: every arrival and newborn 90% blue, 7% orange, 3% red (decision 7; "VVFP Heathen Options.txt" may
       change the mix); a replacement keeps the dead one's, as before;
     * ROLES (decision 6, and the owner's answers of 2026-11-26): when the Heathen Chief or a Master (13-16) dies
       once that puzzle is solved, the eldest adult ordinary Heathen of either sex takes the role -- the real role
       after The Last Heathen, else for show: the role's stock skills; a Master the purple mask and a Chief the
       Chief's own mask, both through the Origins mask store that "Heathens Keep Their Masks When Converted"
       draws (orange / red without those rows); the title through Story Upgrades when it can set one, a Master's
       the role's, a Chief's at most "Esteemed Elder".  After The Last Heathen a regrown camp of 6 adults or more
       gets a real Chief and Masters, one vacant role a look.  Each with a "Took the role" record
       (VvfpCauseHeathenRole).  While the puzzle is unsolved, today's rule, the new one of either sex;
     * THE RECORD CAP (decision 18 as the owner changed it): Heathens grow normally in every population mode; a
       birth or an arrival only keeps 10 records free, so the game never runs out;
     * THE BRIDGE: "VVFP Heathen Life.dll"'s VvfpHeathenLifeUnit is called for every aging Heathen's unit, and
       asked every pass whether to keep the sick byte (heathen_evo.h section 3).

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
#include "../shared/isolan_log_words.h"   /* "Replaced an Isolan ..." with Guardians of Isola (the owner, 2026-11-23) */
#include "../shared/multiplier_choice.h"
#include "../shared/heathen_evo.h"

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
#define TRIBE_UNITS_PER_BABY 240 /* the owner, 2026-11-25: "1 baby every 24 hours across the entire tribe" --
                                    240 age units (6 real minutes each on Normal: 41 units = 4 h 6 min) for
                                    the whole tribe: each woman who could conceive rolls 1 in 240 x their
                                    number (12 h on Fast, 40 h on Slow) */
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
static int g_walk_installed;            /* the elder walk-pace site (walk_stub) */
static int g_former_row, g_tribe_row, g_bones_former, g_bones_all, g_events_row;
static int g_evo;                      /* Heathen Tribe Expansion and Evolution (HE_FLAG_ROW) */
static unsigned int g_births_tenths = HE_BIRTHS_DEFAULT, g_arrivals_tenths = HE_ARRIVALS_DEFAULT;
static int g_mask_orange = HE_MASK_ORANGE_DEFAULT, g_mask_red = HE_MASK_RED_DEFAULT;
static int g_group_max = HE_GROUP_MAX_DEFAULT;
static unsigned int g_he_seed = 0x6D2B79F5u;
static int g_clock_index = -1;         /* the record whose age credit is the village's clock (arrivals) */
static unsigned int g_clock_units;     /* units it was credited since the last throttled pass */
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

/* The expansion's own numbers (xorshift32, seeded at start): the game's rand is never drawn for them. */
static unsigned int he_next(void) {
    unsigned int x = g_he_seed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_he_seed = x;
    return x;
}

/* 0 .. n - 1 (0 when n < 2). */
static int he_below(unsigned int n) {
    return n < 2u ? 0 : (int)(he_next() % n);
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
#define KIND_ROLE 5u             /* 5..8: the camp's Chief (13) .. Master Farmer (16) for show (decision 6) */
#define KIND_LAST 8u
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

/* <Documents>\LDW\<exe>\Virtual Villagers Fun Patcher\Save <S>\Data\<folder>\<file with %d the slot>. */
static int data_path(int slot, char *out, int make, const char *folder, const char *file) {
    const char *levels[4];
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
    levels[0] = "\\Virtual Villagers Fun Patcher";
    levels[1] = "\\Save %d";
    levels[2] = "\\Data";
    levels[3] = NULL;
    for (i = 0; i < 4; ++i) {
        if (levels[i] != NULL) {
            wsprintfA(part, levels[i], slot);
        } else {
            wsprintfA(part, "\\%s", folder);
        }
        lstrcatA(out, part);
        if (make) {
            CreateDirectoryA(out, NULL);
        }
    }
    lstrcatA(out, "\\");
    wsprintfA(part, file, slot);
    lstrcatA(out, part);
    return 1;
}

static int known_path(int slot, char *out, int make) {
    return data_path(slot, out, make, "Heathen Aging", "Heathen Aging - Save %d.dat");
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
        if (u[5 + i * 2] == 0u || u[6 + i * 2] > KIND_LAST) {
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

/* ---- the couples file (decision 15; heathen_evo.h section 5) ------------------------------------------------ */

static he_couple g_couples[HE_COUPLES_MAX];
static int g_couple_count;
static vv_sidecar_gate g_couple_gate;
static int g_couple_blocked;
static int g_couple_dirty;
static DWORD g_couple_synced_at;
static unsigned int g_couple_buffer[(HE_COUPLES_HEADER + HE_COUPLES_MAX * sizeof(he_couple)) / 4u + 1u];
static void forget_village_evo(void);  /* below, after every per-village piece it clears */

static int couples_path(int slot, char *out, int make) {
    return data_path(slot, out, make, HE_COUPLES_FOLDER, HE_COUPLES_FILE);
}

static int valid_couples(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    unsigned int count, i;
    if (len < HE_COUPLES_HEADER || u[0] != HE_COUPLES_MAGIC || u[1] != HE_COUPLES_VERSION || u[2] != HA_GAME
        || u[4] != (unsigned int)*(const int *)ctx) {
        return 0;
    }
    count = u[3];
    if (count > HE_COUPLES_MAX || len != HE_COUPLES_HEADER + count * (unsigned int)sizeof(he_couple)) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned int *e = u + 5 + i * 4;
        if (e[0] == 0u || e[1] == 0u || e[0] == e[1] || e[3] != HE_COUPLE_ACTIVE) {
            return 0;
        }
    }
    return 1;
}

static void read_couples(int slot) {
    char path[MAX_PATH];
    DWORD got = 0;
    int status;
    vv_sidecar_gate_bind(&g_couple_gate, slot);
    g_couple_blocked = 0;
    if (!couples_path(slot, path, 0)) {
        vv_sidecar_gate_block(&g_couple_gate);
        g_couple_blocked = 1;
        return;
    }
    status = vv_sidecar_load(&g_couple_gate, path, (unsigned char *)g_couple_buffer, sizeof g_couple_buffer, &got,
                             valid_couples, &slot);
    g_couple_blocked = status == VV_SIDECAR_LOAD_BLOCKED;
    if (status == VV_SIDECAR_LOAD_VALID) {
        g_couple_count = (int)g_couple_buffer[3];
        memcpy(g_couples, g_couple_buffer + 5, sizeof(he_couple) * (size_t)g_couple_count);
    }
    g_couple_synced_at = GetTickCount() - HA_WRITE_MS;
}

static void write_couples(int slot) {
    unsigned int header[5];
    const void *parts[2];
    DWORD sizes[2];
    char path[MAX_PATH];
    if (!g_couple_dirty || slot == 0 || g_couple_blocked || !vv_sidecar_gate_ready(&g_couple_gate, slot)
        || GetTickCount() - g_couple_synced_at < HA_WRITE_MS || !couples_path(slot, path, 1)) {
        return;
    }
    g_couple_synced_at = GetTickCount();
    header[0] = HE_COUPLES_MAGIC;
    header[1] = HE_COUPLES_VERSION;
    header[2] = HA_GAME;
    header[3] = (unsigned int)g_couple_count;
    header[4] = (unsigned int)slot;
    parts[0] = header;
    sizes[0] = sizeof header;
    parts[1] = g_couples;
    sizes[1] = (DWORD)(sizeof(he_couple) * (size_t)g_couple_count);
    if (vv_sidecar_publish(&g_couple_gate, path, parts, sizes, g_couple_count > 0 ? 2 : 1)) {
        g_couple_dirty = 0;
    }
}

/* The couple `who` (an identity) is in, or -1. */
static int couple_find(unsigned int who) {
    int i;
    for (i = 0; i < g_couple_count; ++i) {
        if (g_couples[i].first == who || g_couples[i].second == who) {
            return i;
        }
    }
    return -1;
}

static void couple_drop(int at) {
    memmove(&g_couples[at], &g_couples[at + 1], sizeof g_couples[0] * (size_t)(g_couple_count - at - 1));
    --g_couple_count;
    g_couple_dirty = 1;
}

/* Identities follow their villager (follow_identities' rekey). */
static void couples_rekey(unsigned int from, unsigned int to) {
    int i;
    for (i = 0; i < g_couple_count; ++i) {
        if (g_couples[i].first == from) {
            g_couples[i].first = to;
            g_couple_dirty = 1;
        }
        if (g_couples[i].second == from) {
            g_couples[i].second = to;
            g_couple_dirty = 1;
        }
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
            if (g_evo) {
                g_couple_synced_at = GetTickCount() - HA_WRITE_MS;
                write_couples(g_file_slot);
            }
            forget_village_evo();          /* the couples, the partner cache and every other piece of it */
        }                                  /* (noted before any slot was known: this village's, kept) */
        g_dirty = g_known_count > 0;
        g_couple_dirty = g_couple_count > 0;
        g_file_slot = slot;
        g_body_count = 0;                  /* another village's bodies, believers and roster */
        g_roster_known = 0;
        g_clock_index = -1;
        g_clock_units = 0;
        memset(g_seen, 0, sizeof g_seen);
        read_known(slot);
        if (g_evo) {
            read_couples(slot);
        }
    } else if (g_load_blocked && !vv_sidecar_gate_throttled(&g_gate)) {
        read_known(slot);
    }
    if (g_evo && g_couple_blocked && !vv_sidecar_gate_throttled(&g_couple_gate)) {
        read_couples(slot);
    }
    write_known();
    if (g_evo) {
        write_couples(g_file_slot);
    }
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
    couples_rekey(from, to);
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
static void evo_pass(void);

static int __cdecl credit(unsigned char *record, int units) {
    int answer = 1;
    __try {
        int index = rec_index(record);
        if (g_evo && index >= 0 && index == g_clock_index && units > 0) {
            g_clock_units += (unsigned int)units;      /* the village's clock (arrivals) */
        }
        if (GetTickCount() - g_kept_at >= HA_KEEP_MS) {
            g_kept_at = GetTickCount();
            keep_known();
            follow_identities();
            watch_graves();
            if (owed_count() > 0) {
                pay_owed();
            }
            if (g_evo) {
                evo_pass();
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

/* ---- the record cap (decision 18, as the owner changed it on 2026-11-26) ---------------------------------------

   The owner: Heathens "should grow normally" in every population mode ("we're gonna convert everyone so no point
   restricting").  The only limit is the technical one: a birth or an arrival of n Heathens is made only while
   the free records, less n, stay at least HE_ROOM_KEPT (10), so the game's own creator never runs out of
   records. */

/* How many of `wanted` new Heathens fit (0 .. wanted). */
static int heathens_fit(int wanted) {
    int spare = free_records() - HE_ROOM_KEPT;
    return spare <= 0 ? 0 : spare < wanted ? spare : wanted;
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

/* The last name (after the name's last space) into `out` (R_NAME_CAP + 1 bytes); 0 when there is none. */
static int last_name(const unsigned char *r, char *out) {
    unsigned int k, from = 0, n = 0;
    for (k = 0; k < R_NAME_CAP && r[R_NAME + k] != 0; ++k) {
        if (r[R_NAME + k] == ' ') {
            from = k + 1;
        }
    }
    if (from > 0) {
        for (k = from; k < R_NAME_CAP && r[R_NAME + k] != 0; ++k) {
            out[n++] = (char)r[R_NAME + k];
        }
    }
    out[n] = 0;
    return n > 0;
}

/* The Heathen Mommy's infant's other parent (the owner, 2026-11-25: "instead of unknown the parents should have
   names"; villagers are villagers regardless of gender): a living adult Heathen of either sex, never the Mommy --
   one of her own family (the same last name) when there is one, else any, at random.  NULL: nobody else. */
static unsigned char *mommy_parent(const unsigned char *mommy) {
    unsigned char *any[256], *family[256];
    char mine[R_NAME_CAP + 1], theirs[R_NAME_CAP + 1];
    unsigned int i;
    int n = 0, f = 0, named = last_name(mommy, mine);
    for (i = 0; i < g_slots && i < 256; ++i) {
        unsigned char *r = rec_at((int)i);
        if (r != mommy && r[R_FACTION] != 0 && living(r) && i32(r, R_AGE) >= ADULT && r[R_NAME] != 0) {
            any[n++] = r;
            if (named && last_name(r, theirs) && lstrcmpA(mine, theirs) == 0) {
                family[f++] = r;
            }
        }
    }
    return f > 0 ? family[ha_rand(f)] : n > 0 ? any[ha_rand(n)] : NULL;
}

/* The eldest living named Heathen but `not_this` (any age): the Mommy's infant's other parent when no adult is
   there and the dead Mommy left no name (the owner: never "Unknown").  NULL: nobody. */
static unsigned char *eldest_heathen(const unsigned char *not_this) {
    unsigned char *best = NULL;
    unsigned int i;
    for (i = 0; i < g_slots; ++i) {
        unsigned char *r = rec_at((int)i);
        if (r != not_this && r[R_FACTION] != 0 && living(r) && r[R_NAME] != 0
            && (best == NULL || i32(r, R_AGE) > i32(best, R_AGE))) {
            best = r;
        }
    }
    return best;
}

static void tell_arrived(int index, const char *how) {
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    cod_arrived_fn told = module != NULL
        ? (cod_arrived_fn)(void *)GetProcAddress(module, "VvfpCauseHeathenArrived") : NULL;
    if (told != NULL) {
        told(HA_GAME, index, how);
    }
}

/* "VVFP Parentage Export.dll" when its row is in the game: the conception hook at 0x465F34 is no longer the stock
   `test bl, bl; jnz` (Story Upgrades' story_parentage_ticked, the same test); loaded by its full path when no
   conception has loaded it yet (native/shared/patcher_files.h).  NULL: not shipped. */
#define PARENTAGE_SITE 0x465F34u
static const unsigned char PARENTAGE_STOCK[5] = { 0x84, 0xDB, 0x75, 0x0C, 0x8B };

static HMODULE parentage_module(void) {
    HMODULE module = GetModuleHandleA(HE_PARENTAGE_DLL);
    if (module == NULL && !vvfp_site_holds(PARENTAGE_SITE, PARENTAGE_STOCK, 5)) {
        module = vvfp_load_patcher_dll(HE_PARENTAGE_DLL);
    }
    return module;
}

/* The Conception record of a forced Heathen conception (the game's hook skips forced ones): read from the
   mother's own record after its litter is set, the father's record when there is one. */
static void log_conception(const unsigned char *mother, const unsigned char *father) {
    HMODULE module = parentage_module();
    he_conception_fn write = module != NULL
        ? (he_conception_fn)(void *)GetProcAddress(module, HE_CONCEPTION_EXPORT) : NULL;
    if (write != NULL) {
        (void)write(HA_GAME, g_manager, mother, father);
    }
}

/* A "Couple formed" record (decision 16), when Parentage Export has the export. */
static void log_couple(const unsigned char *woman, const unsigned char *man) {
    HMODULE module = parentage_module();
    he_couple_log_fn write = module != NULL
        ? (he_couple_log_fn)(void *)GetProcAddress(module, HE_COUPLE_LOG_EXPORT) : NULL;
    if (write != NULL) {
        (void)write(HA_GAME, g_manager, woman, man);
    }
}

/* A "Took the role" record (decision 16), when Cause of Death has the export. */
static void log_role(int index, int role) {
    HMODULE module = GetModuleHandleA(HE_CAUSE_DLL);
    he_role_fn told = module != NULL ? (he_role_fn)(void *)GetProcAddress(module, HE_ROLE_EXPORT) : NULL;
    if (told != NULL) {
        told(HA_GAME, index, role);
    }
}

/* A new arrival's or newborn's mask (decision 7): orange, red or (the rest) blue. */
static void roll_mask(int *orange, int *red) {
    int roll = he_below(100);
    *orange = roll < g_mask_orange;
    *red = !*orange && roll < g_mask_orange + g_mask_red;
}

/* ---- couples (decision 15) ----------------------------------------------------------------------------------

   A couple is two living adult Heathens of either sex (14 or older; never the Heathen Mommy, whose infant
   is her puzzle's), neither in a couple, not kin.  KIN, by the records alone (never a scan of names for
   parents): one is the other's parent (the child's father or mother name, head and body are the parent's own),
   or they share a mother or a father (the same parent name, head and body on both: full and half siblings).
   Founders, the camp's own, arrivals and the Barrel's Heathens keep no parents, so they are no one's kin.  A
   couple lasts until one of them is no longer a living Heathen here (a death, a conversion, leaving the camp).
   g_partner caches each record's partner for the life tick, rebuilt at each throttled look. */
static int g_partner[256];
static int g_couple_women;             /* the women who could conceive now with a partner (the births' W) */

static int same_name(const unsigned char *a, unsigned int at_a, const unsigned char *b, unsigned int at_b) {
    return a[at_a] != 0 && strncmp((const char *)(a + at_a), (const char *)(b + at_b), R_NAME_CAP) == 0;
}

static int parent_of(const unsigned char *parent, const unsigned char *child) {
    return (same_name(child, R_FATHER_NAME, parent, R_NAME) && i32(child, R_FATHER_HEAD) == i32(parent, R_HEAD)
            && i32(child, R_FATHER_BODY) == i32(parent, R_BODY))
        || (same_name(child, R_MOTHER_NAME, parent, R_NAME) && i32(child, R_MOTHER_HEAD) == i32(parent, R_HEAD)
            && i32(child, R_MOTHER_BODY) == i32(parent, R_BODY));
}

/* One recorded parent of a (name, head, body at the given fields) is the same person as one of b's.  A
   same-sex couple's children can hold their parents in opposite fields (the carrier is the Mother: Codex,
   #883), so every parent of one is compared with both of the other's. */
static int same_parent(const unsigned char *a, unsigned int an, unsigned int ah, unsigned int ab,
                       const unsigned char *b, unsigned int bn, unsigned int bh, unsigned int bb) {
    return same_name(a, an, b, bn) && i32(a, ah) == i32(b, bh) && i32(a, ab) == i32(b, bb);
}

static int kin(const unsigned char *a, const unsigned char *b) {
    static const unsigned int FIELD[2][3] = {
        { R_MOTHER_NAME, R_MOTHER_HEAD, R_MOTHER_BODY },
        { R_FATHER_NAME, R_FATHER_HEAD, R_FATHER_BODY },
    };
    int x, y;
    if (parent_of(a, b) || parent_of(b, a)) {
        return 1;
    }
    for (x = 0; x < 2; ++x) {
        for (y = 0; y < 2; ++y) {
            if (same_parent(a, FIELD[x][0], FIELD[x][1], FIELD[x][2], b, FIELD[y][0], FIELD[y][1], FIELD[y][2])) {
                return 1;
            }
        }
    }
    return 0;
}

static int ages(const unsigned char *record);
static int could_conceive(const unsigned char *woman);

/* An adult Heathen of either sex who may pair (never the Heathen Mommy, whose infant is her puzzle's). */
static int pairable(const unsigned char *r) {
    return r[R_FACTION] != 0 && living(r) && ages(r) && i32(r, R_AGE) >= ADULT && i32(r, R_ROLE) != 17;
}

/* The couples' records found again; a couple one of whom is no longer a living Heathen here ends. */
static void couples_refresh(void) {
    static unsigned int who[256];
    unsigned int i;
    int c;
    for (i = 0; i < 256u; ++i) {
        g_partner[i] = -1;
        who[i] = 0u;
    }
    for (i = 0; i < g_slots && i < 256u; ++i) {
        const unsigned char *r = rec_at((int)i);
        if (r[R_FACTION] != 0 && living(r)) {
            who[i] = identity(r);
        }
    }
    for (c = g_couple_count; c-- > 0;) {
        int a = -1, b = -1;
        for (i = 0; i < g_slots && i < 256u; ++i) {
            if (who[i] == g_couples[c].first) {
                a = (int)i;
            } else if (who[i] == g_couples[c].second) {
                b = (int)i;
            }
        }
        if (a < 0 || b < 0) {
            couple_drop(c);                /* a death, a conversion or leaving: the couple ends */
            continue;
        }
        g_partner[a] = b;
        g_partner[b] = a;
    }
}

static int couple_add(unsigned char *first, unsigned char *second) {
    if (g_couple_count >= HE_COUPLES_MAX) {
        return 0;
    }
    g_couples[g_couple_count].first = identity(first);
    g_couples[g_couple_count].second = identity(second);
    g_couples[g_couple_count].formed = (unsigned int)i32(first, R_PROCESSED);
    g_couples[g_couple_count].state = HE_COUPLE_ACTIVE;
    ++g_couple_count;
    g_couple_dirty = 1;
    g_partner[rec_index(first)] = rec_index(second);
    g_partner[rec_index(second)] = rec_index(first);
    log_couple(first, second);
    return 1;
}

/* At most one new couple a look (gradually: the caller asks only when the village's clock moved): an adult free to
   pair, at random, with another adult free to pair who is not their kin, at random -- of either sex (the owner,
   2026-11-26: "same sex yes"). */
static void pair_one_couple(void) {
    unsigned char *free_ones[256], *partners[256], *one;
    unsigned int i;
    int n = 0, m = 0, k;
    for (i = 0; i < g_slots && i < 256u; ++i) {
        unsigned char *r = rec_at((int)i);
        if (g_partner[i] < 0 && pairable(r)) {
            free_ones[n++] = r;
        }
    }
    if (n < 2) {
        return;
    }
    one = free_ones[he_below((unsigned int)n)];
    for (k = 0; k < n; ++k) {
        if (free_ones[k] != one && !kin(one, free_ones[k])) {
            partners[m++] = free_ones[k];
        }
    }
    if (m > 0) {
        (void)couple_add(one, partners[he_below((unsigned int)m)]);
    }
}

/* The partner of the Heathen in `record` (either sex), a living adult Heathen, or NULL.  The cache is a hint only:
   both records are checked against the couple's own saved identities every time (Codex, #883: a partner who
   vanished in an island event can have their record reused by a replacement before the next look -- the newcomer
   is never taken for the partner). */
static unsigned char *partner_of(const unsigned char *record) {
    int at = rec_index(record), m, c;
    unsigned int me, other;
    unsigned char *partner;
    if (at < 0 || at >= 256 || (m = g_partner[at]) < 0 || (unsigned int)m >= g_slots || m >= 256) {
        return NULL;
    }
    partner = rec_at(m);
    if (record[R_FACTION] == 0 || !living(record) || partner[R_FACTION] == 0 || !living(partner)
        || i32(partner, R_AGE) < ADULT || g_partner[m] != at) {
        return NULL;
    }
    me = identity(record);
    if ((c = couple_find(me)) < 0) {
        return NULL;
    }
    other = g_couples[c].first == me ? g_couples[c].second : g_couples[c].first;
    return identity(partner) == other ? partner : NULL;
}

/* A Heathen in record `index` left the camp (a death, an island event, a conversion): neither they nor their
   partner keeps a cached pairing, whatever comes into the record next. */
static void forget_partner(int index) {
    int m;
    if (index < 0 || index >= 256) {
        return;
    }
    m = g_partner[index];
    g_partner[index] = -1;
    if (m >= 0 && m < 256 && g_partner[m] == index) {
        g_partner[m] = -1;
    }
}

/* Her partner when he is a man (a natural conception is a woman's and a man's), or NULL. */
static unsigned char *partner_man(const unsigned char *woman) {
    unsigned char *partner = partner_of(woman);
    return partner != NULL && i32(partner, R_SEX) != 1 ? partner : NULL;
}

static void count_couple_women(void) {
    unsigned int i;
    g_couple_women = 0;
    for (i = 0; i < g_slots && i < 256u; ++i) {
        const unsigned char *r = rec_at((int)i);
        g_couple_women += r[R_FACTION] != 0 && living(r) && ages(r) && could_conceive(r) && partner_man(r) != NULL;
    }
}

/* ---- the litter --------------------------------------------------------------------------------------------- */

static int roll_litter(void) {
    int roll = he_below(10000);
    return roll < HE_TRIPLETS_IN_10000 ? 3 : roll < HE_TRIPLETS_IN_10000 + HE_TWINS_IN_10000 ? 2 : 1;
}

/* A child's parents on its own record, as the stock birth writes them (deliver), the head the parents' average
   +-1 on 95% (`rnd`: the caller's numbers). */
static void set_parents(unsigned char *child, const unsigned char *mother, const char *father_name, int father_head,
                        int father_body, int (*rnd)(int)) {
    int mh = i32(mother, R_HEAD);
    unsigned int k;
    for (k = 0; k < R_PARENT_NAME_CAP; ++k) {
        child[R_FATHER_NAME + k] = 0;
        child[R_MOTHER_NAME + k] = 0;
    }
    for (k = 0; k + 1 < R_PARENT_NAME_CAP && father_name[k] != 0; ++k) {
        child[R_FATHER_NAME + k] = (unsigned char)father_name[k];
    }
    for (k = 0; k + 1 < R_PARENT_NAME_CAP && mother[R_NAME + k] != 0; ++k) {
        child[R_MOTHER_NAME + k] = mother[R_NAME + k];
    }
    *(int *)(child + R_FATHER_HEAD) = father_head;
    *(int *)(child + R_FATHER_BODY) = father_body;
    *(int *)(child + R_MOTHER_HEAD) = mh;
    *(int *)(child + R_MOTHER_BODY) = i32(mother, R_BODY);
    if (rnd(100) < 95) {
        int h = (father_head + mh) / 2 + rnd(3) - 1;
        *(int *)(child + R_HEAD) = h < 0 ? 0 : h > 29 ? 29 : h;
    }
}

static int he_rnd(int n) {
    return he_below((unsigned int)n);
}

/* ---- arrivals (decisions 4 and 5) ---------------------------------------------------------------------------

   A group of 1 (40%), 2 (30%), 3 (20%) or 4 (10%), at most the options' group_max and as many as the record cap
   lets in (heathens_fit); a group of two or more is a couple on half the arrivals, with the rest (0-2) their
   children aged 2-12.  Adults are 18-40, in a role of the stock camp's ordinary Heathens (0x424AC0: 1 farming, 2
   research, 4 healing, 5 parenting, 6 building, 0 any) with that camp's skill value, the camp's Faith -38 to -67;
   children role 0 as the camp's children.  Each gets its Arrived record. */
static const int ARRIVAL_ROLE[6] = { 0, 1, 2, 4, 5, 6 };
static const int ARRIVAL_SKILL[6] = { -1, 0, 3, 2, 1, 4 };

/* (Each number is drawn in its own statement, so the order they are drawn in is fixed.) */
static int arrival_adult(int sex) {
    int k = he_below(6), orange, red, skill = ARRIVAL_SKILL[k], value = ARRIVAL_ROLE[k] == 5 ? 15 : 25, age, faith;
    if (skill < 0) {
        skill = he_below(6);
        value = 5 + he_below(5);
    }
    roll_mask(&orange, &red);
    age = 360 + he_below(441);
    faith = -38 - he_below(30);
    return create(0, skill, value, sex, age, orange, red, ARRIVAL_ROLE[k], faith);
}

static int arrival_child(const unsigned char *mother, const unsigned char *father) {
    int orange, red, index, sex, age, faith;
    unsigned char *child;
    roll_mask(&orange, &red);
    sex = he_below(2);
    age = 40 + he_below(201);
    faith = -38 - he_below(30);
    index = create(0, 2, 0, sex, age, orange, red, 0, faith);
    if (index < 0) {
        return -1;
    }
    child = rec_at(index);
    set_parents(child, mother, (const char *)(father + R_NAME), i32(father, R_HEAD), i32(father, R_BODY), he_rnd);
    known_put(identity(child), KIND_BORN);          /* born a Heathen: never a former villager */
    return index;
}

static void arrive(void) {
    int made[4], n = 0, size, roll = he_below(100), i, couple;
    char words[64];
    size = roll < 40 ? 1 : roll < 70 ? 2 : roll < 90 ? 3 : 4;
    if (size > g_group_max) {
        size = g_group_max;
    }
    size = heathens_fit(size);
    if (size <= 0) {
        return;
    }
    couple = size >= 2 && he_below(2) == 0;
    for (i = 0; i < size; ++i) {
        int index = couple && i >= 2 ? (n >= 2 ? arrival_child(rec_at(made[0]), rec_at(made[1])) : -1)
                  : arrival_adult(couple ? (i == 0 ? 1 : 0) : he_below(2));
        if (index < 0) {
            break;
        }
        made[n++] = index;
    }
    for (i = 0; i < n; ++i) {
        int isolan = vv5_guardians_of_isola();
        if (n == 1) {
            lstrcpyA(words, isolan ? HE_ARRIVED_ALONE_ISOLAN : HE_ARRIVED_ALONE_HEATHEN);
        } else {
            wsprintfA(words, isolan ? HE_ARRIVED_GROUP_ISOLAN : HE_ARRIVED_GROUP_HEATHEN, n - 1, n - 1 == 1 ? "" : "s");
        }
        tell_arrived(made[i], words);
    }
    if (couple && n >= 2) {
        (void)couple_add(rec_at(made[0]), rec_at(made[1]));
    }
}

/* The arrivals' clock: each unit the village's clock record was credited is one roll of 1 in HE_ARRIVAL_ROLL / t.
   Before The Last Heathen only while a Heathen is alive (the puzzle is solved when none is: never from nothing
   while it can be); after it, whether or not anyone is. */
static void arrivals(void) {
    unsigned int units = g_clock_units, u;
    g_clock_units = 0;
    if (g_arrivals_tenths == 0) {
        return;
    }
    if (units > 100000u) {
        units = 100000u;
    }
    for (u = 0; u < units; ++u) {
        if ((unsigned int)he_below(HE_ARRIVAL_ROLL) < g_arrivals_tenths
            && (puzzle_done(LAST_HEATHEN) || living_heathens() > 0)) {
            arrive();
        }
    }
}

/* ---- roles (decision 6) ---------------------------------------------------------------------------------------

   The role the Heathen in `record` holds for the camp: the real one (13-16), or one for show (a KIND_ROLE entry);
   0 none. */
static int held_role(const unsigned char *record) {
    int role = i32(record, R_ROLE), k;
    unsigned int who;
    if (role >= 13 && role <= 16) {
        return role;
    }
    who = identity(record);
    for (k = 0; k < 4; ++k) {
        if (known_find(who, KIND_ROLE + (unsigned int)k) >= 0) {
            return 13 + k;
        }
    }
    return 0;
}

#define FLOAT_100 0x42C80000u
#define FLOAT_90 0x42B40000u

/* A role for show's mask (the owner, 2026-11-26: "for show masters = purple masks (no puzzles)"): the game draws
   the purple and the Chief's mask only from the puzzle roles (0x4728C6, the table 0x472B60), so for show it is put
   in the Origins mask store ("VVFP Origins Icons.dll" VvfpMaskKeep: 1 blue, 4 purple, 5 the Chief's), which
   "VVFP Heathens Keep Masks.dll" draws on an ordinary Heathen with neither kind byte -- only when both are in the
   game.  1 when the store took it. */
#define MASK_STORE_BLUE 1
#define MASK_STORE_PURPLE 4
#define MASK_STORE_CHIEF 5
typedef int (__stdcall *mask_keep_fn)(void *record, int mask);

static int store_mask(unsigned char *record, int mask) {
    HMODULE origins = GetModuleHandleA("VVFP Origins Icons.dll");
    mask_keep_fn keep = origins != NULL && GetModuleHandleA("VVFP Heathens Keep Masks.dll") != NULL
        ? (mask_keep_fn)(void *)GetProcAddress(origins, "VvfpMaskKeep") : NULL;
    return keep != NULL && keep(record, mask) == 1;
}

/* The Chief or a Master in `role` (13-16) is wanted -- its holder died once its puzzle was solved, or (after The
   Last Heathen) the regrown camp has none: the eldest living adult ordinary Heathen of either sex (roles 0-11,
   holding no role; the owner: every later holder "can be any sex") takes it -- the real role after The Last
   Heathen (its stock set-up: the Chief all six skills 100, a Master 90 in the role's skill; the role's own mask
   art), else for show (the same skills; a Master the purple mask and the Chief the Chief's mask through the
   store above, else orange / red; the title through Story Upgrades when it can set one -- the very title the
   original shows, "Heathen Chief" / "Heathen Master ..." or the Guardians of Isola Rewrite's own (the owner,
   2026-11-26: "while still a Heathen, his title is the same as the original chief"); kept in the file); then its
   "Took the role" record.  1 when someone took it. */
static int elder(const unsigned char *r);   /* the game's elder test 0x46F790 (below) */

static int pass_role(int role, const unsigned char *dead) {
    static const int SKILL_OF[4] = { -1, 3, 4, 0 };     /* 13 all, 14 Research, 15 Building, 16 Farming */
    unsigned char *heir = NULL;
    unsigned int i;
    int k;
    for (i = 0; i < g_slots; ++i) {
        unsigned char *r = rec_at((int)i);
        if (r != dead && r[R_FACTION] != 0 && living(r) && i32(r, R_AGE) >= ADULT && i32(r, R_ROLE) >= 0
            && i32(r, R_ROLE) <= 11 && held_role(r) == 0 && (role == 13 || !elder(r))   /* a Master is never an elder */
            && (heir == NULL || i32(r, R_AGE) > i32(heir, R_AGE))) {
            heir = r;
        }
    }
    if (heir == NULL) {
        return 0;
    }
    for (k = 0; k < 6; ++k) {
        if (SKILL_OF[role - 13] < 0 || SKILL_OF[role - 13] == k) {
            ((unsigned int *)(heir + R_SKILLS))[k] = role == 13 ? FLOAT_100 : FLOAT_90;
        }
    }
    if (puzzle_done(LAST_HEATHEN)) {
        *(int *)(heir + R_ROLE) = role;
        heir[R_ORANGE] = 0;
        heir[R_RED] = 0;
    } else {
        HMODULE story = GetModuleHandleA(HE_STORY_DLL);
        he_set_title_fn title = story != NULL ? (he_set_title_fn)(void *)GetProcAddress(story, HE_TITLE_EXPORT) : NULL;
        if (store_mask(heir, role == 13 ? MASK_STORE_CHIEF : MASK_STORE_PURPLE)) {
            heir[R_ORANGE] = 0;
            heir[R_RED] = 0;
        } else {
            heir[R_ORANGE] = role != 13;
            heir[R_RED] = role == 13;
        }
        known_put(identity(heir), KIND_ROLE + (unsigned int)(role - 13));
        if (title != NULL) {
            (void)title(HA_GAME, rec_index(heir), vv5_role_title(role));   /* the original's own title */
        }
    }
    log_role(rec_index(heir), role);
    return 1;
}

/* A for-show role's title (set by pass_role through Story Upgrades) is taken off when the role is no longer
   held: the holder converted (Codex, #883: a converted show Master kept "Heathen Master ...") or retired.
   Story Upgrades' setter with no title removes it; without Story Upgrades no title was ever set. */
static void clear_show_title(unsigned char *record) {
    HMODULE story = GetModuleHandleA(HE_STORY_DLL);
    he_set_title_fn title = story != NULL ? (he_set_title_fn)(void *)GetProcAddress(story, HE_TITLE_EXPORT) : NULL;
    if (title != NULL) {
        (void)title(HA_GAME, rec_index(record), NULL);
    }
}

/* After The Last Heathen (the owner, 2026-11-26): a regrown camp of REGROWN_ADULTS adult Heathens or more gets a
   real Chief and Masters -- one vacant role (no living Heathen holds it) a look, the Chief first. */
#define REGROWN_ADULTS 6

static void regrown_roles(void) {
    unsigned int i;
    int adults = 0, held[4] = { 0, 0, 0, 0 }, role;
    if (!puzzle_done(LAST_HEATHEN)) {
        return;
    }
    for (i = 0; i < g_slots; ++i) {
        const unsigned char *r = rec_at((int)i);
        if (r[R_FACTION] != 0 && living(r)) {
            adults += i32(r, R_AGE) >= ADULT;
            if (i32(r, R_ROLE) >= 13 && i32(r, R_ROLE) <= 16) {
                held[i32(r, R_ROLE) - 13] = 1;
            }
        }
    }
    if (adults < REGROWN_ADULTS) {
        return;
    }
    for (role = 13; role <= 16; ++role) {
        if (!held[role - 13]) {
            (void)pass_role(role, NULL);
            return;
        }
    }
}

/* A role for show belongs to a living Heathen: one who converted or is gone no longer holds it.  A show Chief who
   joined the tribe becomes a real Retired Chief (the owner, 2026-11-26: "Real role when he converts"): role 13 on
   the believer -- the game then titles them "Retired Chief" and gives them the Retired Chief's actions, Spreading
   the Word among them (the scheduler 0x46F1DD tests the role on each believer) -- and the show title is taken off
   (Story Upgrades' setter with no title).  Every reader of role 13 on a believer reads that one record (the
   panel title 0x442ED2, the grave 0x464D69, the scheduler 0x46F1DD, 0x469EA5); the role finder 0x470690 looks at
   Heathens only, so a second Retired Chief is found by nothing that looks for "the" Chief. */
static void roles_follow(void) {
    int k;
    for (k = g_known_count; k-- > 0;) {
        if (g_known[k].kind >= KIND_ROLE && g_known[k].kind <= KIND_LAST) {
            unsigned int i, who = g_known[k].identity;
            int heathen = 0;
            unsigned char *believer = NULL;
            for (i = 0; i < g_slots && !heathen; ++i) {
                unsigned char *r = rec_at((int)i);
                if (living(r) && identity(r) == who) {
                    heathen = r[R_FACTION] != 0;
                    believer = heathen ? NULL : r;
                }
            }
            if (!heathen) {
                if (believer != NULL) {
                    if (g_known[k].kind == KIND_ROLE) {
                        *(int *)(believer + R_ROLE) = 13;       /* only the show Chief becomes a real role */
                    }
                    clear_show_title(believer);                 /* a show Master's "Heathen Master ..." too */
                }
                known_drop(who, g_known[k].kind);
            }
        }
    }
}

/* ---- the bridge into "VVFP Heathen Life.dll" (heathen_evo.h section 3) ------------------------------------- */
static he_life_unit_fn g_life;

static void retire_elders(void);

/* ---- the throttled look of the expansion (the age credit's, every HA_KEEP_MS) --------------------------------- */
static void evo_pass(void) {
    unsigned int i;
    HMODULE life = GetModuleHandleA(HE_LIFE_DLL);
    g_life = life != NULL ? (he_life_unit_fn)(void *)GetProcAddress(life, HE_LIFE_EXPORT) : NULL;
    if (g_file_slot == 0 || g_couple_blocked) {
        return;                            /* the village's couples are not known yet */
    }
    roles_follow();
    retire_elders();                       /* the elders give their places to younger ones (not the Chief) */
    couples_refresh();
    if (g_clock_units > 0) {
        pair_one_couple();                 /* gradually: at most one a look, as the village's clock moves */
    }
    count_couple_women();
    arrivals();
    regrown_roles();
    g_clock_index = -1;
    for (i = 0; i < g_slots && g_clock_index < 0; ++i) {
        if (living(rec_at((int)i))) {
            g_clock_index = (int)i;
        }
    }
}

/* The dead Heathen Mommy's own infant's other parent (gone() keeps it for her replacement's). */
static char g_mommy_parent_name[R_PARENT_NAME_CAP + 1];
static int g_mommy_parent_head, g_mommy_parent_body;

/* Everything the expansion keeps of one village, forgotten when the village changes (a Change Tribe, a load of
   another slot, Start Over): the couples, the partner cache the life tick asks (rebuilt only by a throttled look,
   which waits while the new slot's couples file is unreadable), the births' W, the dead Mommy's other parent.
   Without this the new village's women could conceive with the old village's pairings (Codex, #883). */
static void forget_village_evo(void) {
    g_couple_count = 0;
    g_couple_dirty = 0;
    memset(g_partner, 0xFF, sizeof g_partner);
    g_couple_women = 0;
    g_mommy_parent_name[0] = 0;
    g_mommy_parent_head = g_mommy_parent_body = 0;
    g_clock_index = -1;
    g_clock_units = 0;
}

/* The Heathen Mommy's infant, as the restored puzzle makes her carry it: one infant by the game's own conception
   (forced), its other parent named -- one of her family or any adult (mommy_parent), else the eldest, else the one
   the dead Mommy's own infant had -- the statistics' twins and triplets put back, the Conception record written. */
static void mommy_infant(unsigned char *r) {
    unsigned char *father;
    int twins = *(volatile int *)(UINT_PTR)G_TWINS, triplets = *(volatile int *)(UINT_PTR)G_TRIPLETS;
    father = mommy_parent(r);
    if (father == NULL && g_mommy_parent_name[0] == 0) {
        father = eldest_heathen(r);      /* never "Unknown" while anyone is there (the owner) */
    }
    if (father != NULL) {
        ((tc7_fn)(UINT_PTR)G_CONCEIVE)(r, NULL, i32(father, R_LINEAGE), 1, 50, (int)(UINT_PTR)(father + R_NAME),
                                       i32(father, R_HEAD), i32(father, R_BODY), 1);
    } else if (g_mommy_parent_name[0] != 0) {
        /* nobody else alive to name: the one the dead Mommy's own infant had */
        ((tc7_fn)(UINT_PTR)G_CONCEIVE)(r, NULL, 1, 1, 50, (int)(UINT_PTR)g_mommy_parent_name,
                                       g_mommy_parent_head, g_mommy_parent_body, 1);
    } else {
        ((tc7_fn)(UINT_PTR)G_CONCEIVE)(r, NULL, 1, 1, 50, (int)(UINT_PTR)"Unknown", 2, 2, 1);
    }
    *(volatile int *)(UINT_PTR)G_TWINS = twins;
    *(volatile int *)(UINT_PTR)G_TRIPLETS = triplets;
    *(int *)(r + R_LITTER) = 1;          /* one infant, as the stock Mommy */
    if (i32(r, R_PREGNANT) == 0) {
        *(int *)(r + R_PREGNANT) = 1;
    }
    log_conception(r, father);           /* the game's hook skips a forced conception */
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
    case 16: return create(0, 0, 90, -1, 540, 0, 0, 16, -74);   /* later holders: either sex (the owner) */
    case 13:
        index = create(0, 2, 90, -1, 1000, 0, 0, 13, -94);   /* a later Chief: either sex (the owner) */
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
            mommy_infant(rec_at(index));
        }
        return index;
    default:
        return -1;
    }
}

/* ---- the elders retire (the owner, 2026-11-26: "above elderly age, heathens will "retire" and go to the
   encampment where younger ones will take their place"; "Puzzle roles too"; "the chief shouldn't retire") -------

   ELDER is the game's own test, 0x46F790 (`age +0x1B8C >= 160 x Medicine + 840`, Medicine from 0x423600(1) on
   0x51D5CC: 1,000 units at Medicine 1, 55 years later at each level; the believers' elder sickness 0x465FE2 and
   recovery 0x472F46 use it, and the walk 0x4659CB).  A living Heathen elder who holds a place in the camp gives it
   up to a younger one, once a look:
     a camp role 1-11 (the stock camp's work: 0x424AC0's roles) -- to the eldest adult Heathen who is not an elder
       and has none (role 0), who keeps their own mask;
     a puzzle role while its puzzle is unsolved -- the Heathen Doctor 12, the three Masters 14-16, the Heathen Mommy
       17 -- to the eldest such younger adult, or with none of them the eldest younger adult of a camp role (the
       puzzle comes first), set up as the stock camp sets that role up (its skill, its Faith; the mask the game
       draws from the role, 0x4728C6; the Mommy carrying her infant with a named other parent, mommy_infant), so
       the role finder 0x470690 finds the successor and the puzzle goes on; the elder Mommy's infant goes with the
       role;
     a Master's role after The Last Heathen, or one for show (decision 6) -- to the heir pass_role picks;
     NEVER the Chief (13), whether the original, a later real one or one for show: they keep the role until death
       or conversion (the owner).
   The elder then has role 0 -- the Heathen AI's default case (0x46EAD9: role - 1 above 0x11 goes to 0x46F007,
   the camp wander at the encampment, walk area 0x39), so they live at the encampment; "VVFP Heathen Life.dll"
   gives an elder no show action away from it.  Their skills stay.  With no younger adult nobody retires: the
   elder keeps the place until one grows up or arrives, so no puzzle is ever left without its Heathen.  Each
   retirement has its "Retired to the encampment" record and the successor's "Took the role" record. */
static int elder(const unsigned char *r) {
    return i32(r, R_AGE) >= 160 * *(const volatile int *)(UINT_PTR)G_MEDICINE + 840;
}

typedef void (__stdcall *he_retired_fn)(int game, int index, int role);

static void log_retired(int index, int role) {
    HMODULE module = GetModuleHandleA(HE_CAUSE_DLL);
    he_retired_fn told = module != NULL ? (he_retired_fn)(void *)GetProcAddress(module, HE_RETIRED_EXPORT) : NULL;
    if (told != NULL) {
        told(HA_GAME, index, role);
    }
}

/* The eldest adult Heathen who is not an elder and holds nothing (role 0, no role for show); with `any_role` a camp
   role 1-11 holder when there is none.  NULL: nobody younger. */
static unsigned char *younger_successor(const unsigned char *elder_one, int any_role) {
    unsigned char *best = NULL, *backup = NULL;
    unsigned int i;
    for (i = 0; i < g_slots; ++i) {
        unsigned char *r = rec_at((int)i);
        int role = i32(r, R_ROLE);
        if (r == elder_one || r[R_FACTION] == 0 || !living(r) || i32(r, R_AGE) < ADULT || elder(r)
            || role < 0 || role > 11 || held_role(r) != 0 || i32(r, R_PREGNANT) != 0) {
            continue;
        }
        if (role == 0) {
            if (best == NULL || i32(r, R_AGE) > i32(best, R_AGE)) {
                best = r;
            }
        } else if (any_role && (backup == NULL || i32(r, R_AGE) > i32(backup, R_AGE))) {
            backup = r;
        }
    }
    return best != NULL ? best : backup;
}

/* The successor of a puzzle role (12, 14-17), set up as create_role sets the role up. */
static void take_puzzle_role(unsigned char *heir, int role) {
    static const int SKILL[6] = { 2, -1, 3, 4, 0, 1 };      /* 12 Healing, -, 14 Research, 15 Building, 16 Farming, 17 */
    static const int FAITH[6] = { -14, 0, -74, -74, -74, -25 };
    static const unsigned int VALUE[6] = { 0x428C0000u, 0, FLOAT_90, FLOAT_90, FLOAT_90, 0x428C0000u };   /* 70 / 90 */
    int k = role - 12;
    *(int *)(heir + R_ROLE) = role;
    heir[R_ORANGE] = 0;
    heir[R_RED] = 0;
    if (SKILL[k] >= 0) {
        ((unsigned int *)(heir + R_SKILLS))[SKILL[k]] = VALUE[k];
    }
    *(int *)(heir + R_FAITH) = FAITH[k];
    if (role == 17) {
        mommy_infant(heir);
    }
}

/* One elder's retirement, when a younger one can take the place: 1 done. */
static int retire(unsigned char *old) {
    int role = i32(old, R_ROLE), show = held_role(old), puzzle;
    unsigned char *heir;
    if (role == 13 || show == 13) {
        return 0;                                   /* the Chief never retires (the owner) */
    }
    if (show >= 14 && show <= 16 && (role < 13 || role > 16)) {           /* a Master for show */
        if (younger_successor(old, 0) == NULL) {
            return 0;
        }
        known_drop(identity(old), KIND_ROLE + (unsigned int)(show - 13));
        clear_show_title(old);                      /* the role's title goes with the role */
        (void)store_mask(old, MASK_STORE_BLUE);
        log_retired(rec_index(old), show);
        return pass_role(show, old);
    }
    if (role >= 14 && role <= 16 && puzzle_done(puzzle_of_role(role))) {   /* a real Master after the puzzle */
        if (younger_successor(old, 0) == NULL) {
            return 0;
        }
        *(int *)(old + R_ROLE) = 0;
        log_retired(rec_index(old), role);
        return pass_role(role, old);
    }
    puzzle = puzzle_of_role(role);
    if (role >= 12 && role <= 17) {
        if (puzzle != 0 && puzzle_done(puzzle)) {
            return 0;                               /* a solved puzzle's Heathen: no place to give up */
        }
        if ((heir = younger_successor(old, 1)) == NULL) {
            return 0;
        }
        *(int *)(old + R_ROLE) = 0;
        if (role == 17) {                           /* her infant goes with the role */
            *(int *)(old + R_PREGNANT) = 0;
            *(int *)(old + R_LITTER) = 0;
            ((tc1_fn)(UINT_PTR)G_CARRY)(old, NULL, -1);
        }
        log_retired(rec_index(old), role);
        take_puzzle_role(heir, role);
        log_role(rec_index(heir), role);
        return 1;
    }
    if (role >= 1 && role <= 11) {
        if ((heir = younger_successor(old, 0)) == NULL) {
            return 0;
        }
        *(int *)(old + R_ROLE) = 0;
        log_retired(rec_index(old), role);
        *(int *)(heir + R_ROLE) = role;
        log_role(rec_index(heir), role);
        return 1;
    }
    return 0;
}

static void retire_elders(void) {
    unsigned int i;
    for (i = 0; i < g_slots; ++i) {
        unsigned char *r = rec_at((int)i);
        if (r[R_FACTION] != 0 && living(r) && ages(r) && elder(r) && (i32(r, R_ROLE) != 0 || held_role(r) != 0)) {
            (void)retire(r);
        }
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
    /* the words in the Guardians of Isola wording with the rewrite on (shared/isolan_log_words.h) */
    tell_arrived(index, vv5_word_replaced(g_replace_words == REPLACED_EVENT));
    return 1;
}

/* An owed replacement, packed into a file entry: bit 31 set, a number 0..255 (bits 20-27) keeping two alike
   apart, how the one replaced was lost (bit 16: an island event, else old age -- its Arrived record says the real
   cause when it is paid), the Faith kept (its negation, bits 8-15; 0: the camp's -38 - rand(30)), red (7), orange
   (6), the role (0-5). */
#define OWED_EVENT 0x10000u
#define OWED_CHILD 0x20000u   /* bit 17: a camp child who grew up, replaced by a child (replace_child) */
static int g_owing_child;

static unsigned int owed_pack(int role, int orange, int red, int faith, int number) {
    return 0x80000000u | ((unsigned int)(number & 0xFF) << 20) | ((unsigned int)(-faith & 0xFF) << 8)
        | ((unsigned int)(red != 0) << 7) | ((unsigned int)(orange != 0) << 6) | (unsigned int)(role & 0x3F)
        | (g_replace_words == REPLACED_EVENT ? OWED_EVENT : 0u) | (g_owing_child ? OWED_CHILD : 0u);
}

/* ---- a camp child who grows up (the owner, 2026-11-26: "if the heathen children age up immediately spawn
   replacements!!! especially the rascal!!!!!!!!!!") --------------------------------------------------------------

   The stock camp (0x424AC0) makes three children, role 0, Healing 0: ages 120 (0x424CF9), 140 in the orange mask
   (0x424D23) and 240 (0x424D4D).  The orange one is THE RASCAL: the Details panel titles a Heathen younger than 280
   (0x4430B2) in the orange mask (+0x1CED, 0x4430C6) "Rascal" (string 0xD2, eSayRascal, 0x4430D1), every other
   Heathen child "Child" (0xC4, 0x4430E3).  An orange Heathen, child or adult, chases a believer it meets (the
   meeting 0x46E2E0: orange at 0x46E32C, its behaviour 0x14 and the believer's 0x15; a red one scares, 0x16) and
   keeps out of the rain only in weather 5 (0x46EA31); no puzzle reads it.  With this row the camp ages, so a camp
   child who reaches 280 units would leave the camp without its child: a new child is made at once by the
   creator, in the same role and mask (the Rascal's replacement is a Rascal again, age 140; a blue one 120 or 240,
   as the stock camp's two), Healing 0, the stock camp's Faith (-38 - rand(30)).  The grown one stays, an adult
   in the same role (the stock children's role 0 is the ordinary camp role, as the stock adult of 0x424F59).
   A CAMP CHILD is one the camp keeps a place for: a Heathen with no recorded parents (the camp's own, their
   replacements, an island event's or the Barrel's), never a former villager's (as at a death) and never a baby
   born of a couple or an arrival's child (they are the tribe's growth, not a place of the camp's).  Only while
   10 records stay free (heathens_fit), else owed; after The Last Heathen only while New Heathen Arrivals is not
   0, as arrivals. */
#define CHILD_AGE_RASCAL 140
#define CHILD_AGE_YOUNG 120
#define CHILD_AGE_OLDER 240

static int camp_child(const unsigned char *r) {
    int role = i32(r, R_ROLE);
    return r[R_FACTION] != 0 && !former_villager(r) && r[R_FATHER_NAME] == 0 && r[R_MOTHER_NAME] == 0
        && role >= 0 && role <= 11;
}

static int children_replaced_now(void) {
    return g_evo && (!puzzle_done(LAST_HEATHEN) || g_arrivals_tenths > 0);
}

static int replace_child(int role, int orange, int red) {
    int age = orange ? CHILD_AGE_RASCAL : (he_below(2) ? CHILD_AGE_OLDER : CHILD_AGE_YOUNG);
    int index = heathens_fit(1) < 1 ? -1 : create(0, 2, 0, -1, age, orange, red, role, camp_faith());
    if (index < 0) {
        return 0;
    }
    tell_arrived(index, vv5_word_replaced_child());
    return 1;
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
    if (living_heathens() == 0) {
        drop_owed();                       /* never from nothing */
        return;
    }
    for (i = g_known_count; i-- > 0;) {
        if (g_known[i].kind == KIND_OWED && (g_known[i].identity & OWED_CHILD) != 0) {
            unsigned int packed = g_known[i].identity;
            if (!children_replaced_now()) {
                known_drop(packed, KIND_OWED);     /* after The Last Heathen with no arrivals: none any more */
            } else if (replace_child((int)(packed & 0x3F), (int)((packed >> 6) & 1), (int)((packed >> 7) & 1))) {
                known_drop(packed, KIND_OWED);
            } else {
                continue;                          /* still no room: kept */
            }
            i = g_known_count;                     /* the list moved */
        }
    }
    if (puzzle_done(LAST_HEATHEN)) {
        for (i = g_known_count; i-- > 0;) {        /* nobody who died is replaced any more */
            if (g_known[i].kind == KIND_OWED && (g_known[i].identity & OWED_CHILD) == 0) {
                known_drop(g_known[i].identity, KIND_OWED);
                i = g_known_count;
            }
        }
        return;
    }
    for (i = g_known_count; i-- > 0 && free_records() > 0;) {
        if (g_known[i].kind == KIND_OWED && (g_known[i].identity & OWED_CHILD) == 0) {
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

/* A camp child in `record` has just reached 280 units: a new child in the same role and mask at once, or owed. */
static void grew_up(const unsigned char *record) {
    int role, orange, red;
    if (!camp_child(record) || !children_replaced_now() || living_heathens() == 0) {
        return;
    }
    role = i32(record, R_ROLE);
    orange = record[R_ORANGE] != 0;
    red = record[R_RED] != 0;
    if (!replace_child(role, orange, red)) {
        g_owing_child = 1;
        owe(role, (unsigned char)orange, (unsigned char)red, 0);
        g_owing_child = 0;
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
static void copy_name(unsigned char *to, const unsigned char *from, unsigned int cap);

static int gone(unsigned char *record, int how, int cause) {
    known_drop(identity(record), KIND_EXPECTING);
    forget_partner(rec_index(record));     /* before a replacement can take the record */
    int role = i32(record, R_ROLE);
    int faith = i32(record, R_FAITH);
    unsigned char orange = record[R_ORANGE], red = record[R_RED];
    int former = former_villager(record);
    int index = rec_index(record);
    int body = how == HA_DIED && keeps_body(record);
    int held = g_evo ? held_role(record) : 0;
    if (held != 0 && (role < 13 || role > 16)) {
        (void)store_mask(record, MASK_STORE_BLUE);   /* a role for show: its stored mask goes with it */
    }
    if (role == 17) {                      /* her replacement's infant is named after her own infant's other parent */
        copy_name((unsigned char *)g_mommy_parent_name, record + R_BABY_FATHER_NAME, R_PARENT_NAME_CAP + 1);
        g_mommy_parent_head = i32(record, R_BABY_FATHER_HEAD);
        g_mommy_parent_body = i32(record, R_BABY_FATHER_BODY);
    }
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
    if (held != 0 && puzzle_done(puzzle_of_role(held))) {
        known_drop(identity(record), KIND_ROLE + (unsigned int)(held - 13));
        (void)pass_role(held, record);           /* decision 6: the role goes on in the camp */
    }
    if (puzzle_done(LAST_HEATHEN) || (former && puzzle_of_role(role) == 0) || living_heathens() == 0) {
        g_mommy_parent_name[0] = 0;
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
    g_mommy_parent_name[0] = 0;
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
    if (g_evo ? heathens_fit(litter) < litter : free_records() < litter + HA_ROOM_KEPT) {
        return;                     /* waits until the village's own births keep their room (decision 18) */
    }
    for (i = 0; i < litter; ++i) {
        int fh = i32(mother, R_BABY_FATHER_HEAD), mh = i32(mother, R_HEAD);
        int orange = 0, red = 0, index;
        if (g_evo) {
            roll_mask(&orange, &red);       /* decision 7: a newborn's own mask, not a parent's */
        }
        index = create(i32(mother, R_LINEAGE), i32(mother, R_BABY_SKILL), i32(mother, R_BABY_VALUE), -1,
                       DELIVERY, orange, red, 0, camp_faith());
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

/* A Heathen woman this companion ages who could conceive now: 14 to 45, not expecting, not the Heathen Mommy. */
static int could_conceive(const unsigned char *woman) {
    return i32(woman, R_SEX) == 1 && i32(woman, R_ROLE) != 17 && i32(woman, R_PREGNANT) == 0
           && i32(woman, R_AGE) >= ADULT && i32(woman, R_AGE) <= BIRTH_LAST;
}

/* How many women of the tribe could conceive now (at least 1: the caller is one). */
static int tribe_women(void) {
    unsigned int i;
    int n = 0;
    for (i = 0; i < g_slots; ++i) {
        const unsigned char *r = rec_at((int)i);
        n += r[R_FACTION] != 0 && living(r) && ages(r) && could_conceive(r);
    }
    return n > 0 ? n : 1;
}

/* The expansion's births (decisions 1-3, 15): a woman who could conceive and has a partner rolls 1 in
   HE_BIRTH_ROLL x W / t (the own numbers), before and after The Last Heathen, while the record cap lets one more
   in; her partner is the father; the litter is the expansion's own roll, as many as the cap lets in; the
   statistics' twins and triplets put back; the Conception record written. */
static void maybe_conceive_evo(unsigned char *woman) {
    unsigned char *man;
    int twins, triplets, babies, women = g_couple_women > 0 ? g_couple_women : 1;
    /* The village's couples not known (no slot yet, or its couples file unreadable): no birth at all -- the
       documented pause of couples, births and arrivals, and never a stale pairing. */
    if (g_file_slot == 0 || g_couple_blocked) {
        return;
    }
    if (!could_conceive(woman) || (man = partner_man(woman)) == NULL
        || (unsigned int)he_below(HE_BIRTH_ROLL * (unsigned int)women) >= g_births_tenths || heathens_fit(1) < 1) {
        return;
    }
    twins = *(volatile int *)(UINT_PTR)G_TWINS;
    triplets = *(volatile int *)(UINT_PTR)G_TRIPLETS;
    ((tc7_fn)(UINT_PTR)G_CONCEIVE)(woman, NULL, i32(man, R_LINEAGE), 0, 0, (int)(UINT_PTR)(man + R_NAME),
                                   i32(man, R_HEAD), i32(man, R_BODY), 1);
    *(volatile int *)(UINT_PTR)G_TWINS = twins;
    *(volatile int *)(UINT_PTR)G_TRIPLETS = triplets;
    if (i32(woman, R_PREGNANT) == 0) {
        *(int *)(woman + R_PREGNANT) = i32(woman, R_PROCESSED) > 0 ? i32(woman, R_PROCESSED) : 1;
    }
    babies = heathens_fit(roll_litter());
    *(int *)(woman + R_LITTER) = babies > 0 ? babies : 1;
    known_put(identity(woman), KIND_EXPECTING);
    log_conception(woman, man);
}

static void maybe_conceive(unsigned char *woman) {
    unsigned char *father;
    int twins, triplets;
    if (g_evo) {
        maybe_conceive_evo(woman);
        return;
    }
    if (!could_conceive(woman) || ha_rand(TRIBE_UNITS_PER_BABY * tribe_women()) != 0
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
    log_conception(woman, father);
}

/* ---- the life tick ----------------------------------------------------------------------------------------- */

/* One age unit for an aging Heathen: 1 done, 0 the stock skip, 2 no unit due and Heathen Life keeps the sick byte
   (the stock skip's only other work, processed age = age, is already so). */
static int __cdecl unit(unsigned char *record) {
    int answer = 0;
    __try {
        int processed, threshold;
        int row = g_evo ? HE_LIFE_ROW : 0;
        if (!ages(record)) {
            return 0;
        }
        if (i32(record, R_PROCESSED) >= i32(record, R_AGE)) {
            return g_life != NULL && (g_life(record, HE_LIFE_IDLE | row) & HE_LIFE_KEEP_SICK) ? 2 : 0;
        }
        if (owed_count() > 0) {
            pay_owed();
        }
        processed = i32(record, R_PROCESSED);
        threshold = 160 * *(const volatile int *)(UINT_PTR)G_MEDICINE + 940;
        *(int *)(record + R_PROCESSED) = processed + 1;
        answer = 1;
        if (processed < ADULT && processed + 1 >= ADULT) {
            grew_up(record);               /* a camp child's place is filled at once */
        }
        if (processed % 20 == 0 && processed > threshold
            && ha_rand(100) < 10 * (processed / 20 - threshold / 20)) {
            died(record);
            return 1;
        }
        if (g_tribe_row || g_events_row) {
            int conceived = i32(record, R_PREGNANT);
            if (conceived != 0 && i32(record, R_ROLE) != 17 && conceived + DELIVERY < processed
                && known_find(identity(record), KIND_EXPECTING) >= 0 && (g_evo || !puzzle_done(LAST_HEATHEN))) {
                deliver(record);           /* (decision 2: with the expansion, after The Last Heathen too) */
            } else if (conceived == 0 && g_tribe_row) {
                maybe_conceive(record);
            }
        }
        if (g_life != NULL) {
            (void)g_life(record, HE_LIFE_UNIT | row);
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
        cmp dword ptr [g_tick_result], 2
        je kept
        mov byte ptr [esp + 0x12], 0
    kept:
        jmp dword ptr [g_tick_next]
    }
}

static const unsigned char CREDIT_STOCK[10] = { 0x38, 0x9E, 0xEC, 0x1C, 0x00, 0x00, 0x8B, 0xF8, 0x75, 0x0C };
static const unsigned char CREDIT_STATS[10] = { 0x38, 0x9E, 0xEC, 0x1C, 0x00, 0x00, 0x8B, 0xF8, 0x75, 0x38 };
static const unsigned char TICK_STOCK[9] = { 0x80, 0xBE, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x74, 0x1B };

/* An elder Heathen keeps their pace (the owner, 2026-11-26: "their speed must not be impacted at elderly age for
   balance reasons").  The walk set-up 0x465980 (esi the villager, edi the walk) gives the walk speed 0x28 (40, the
   slow pace a sick villager walks at) to an elder -- `lea ecx, [esi+0x1B8C]; call 0x46F790` (the game's elder
   test) at 0x4659C5, then `test al, al; jne 0x465A06` (`mov dword [edi], 0x28`) -- and otherwise to one who
   dislikes running (preference 0x26) when not fleeing or chasing (0x4659D4..0x465A04).  A Heathen skips the
   elder test only: the dislike test and everything else run as for anyone, and a believer elder still slows.
   Installed with the expansion's row, apart from the two sites above (all or none of its own). */
#define SITE_WALK 0x4659C5u
#define WALK_AFTER 0x4659D0u            /* the stock `test al, al` after the elder test */
#define WALK_NOT_ELDER 0x4659D4u        /* the stock path of a villager who is not an elder */
#define G_ELDER 0x46F790u
static const unsigned char WALK_STOCK[11] = { 0x8D, 0x8E, 0x8C, 0x1B, 0x00, 0x00, 0xE8, 0xC0, 0x9D, 0x00, 0x00 };
static const unsigned int g_walk_after = WALK_AFTER;
static const unsigned int g_walk_not_elder = WALK_NOT_ELDER;
static const unsigned int g_elder_test = G_ELDER;

__declspec(naked) static void walk_stub(void) {
    __asm {
        cmp byte ptr [esi + 0x1CEC], 0          ; R_FACTION: a Heathen
        jne heathen
        lea ecx, [esi + 0x1B8C]
        call dword ptr [g_elder_test]
        jmp dword ptr [g_walk_after]
    heathen:
        jmp dword ptr [g_walk_not_elder]
    }
}

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
    forget_village_evo();                  /* the couples too (their folder goes with the slot's), the cache */
    memset(g_seen, 0, sizeof g_seen);
}

/* heathen_evo.h section 3: the record index of the living partner of the Heathen in record `index`, or -1. */
int __stdcall VvfpHeathenAgingCoupleOf(int index) {
    int answer = -1;
    if (!g_installed || !g_evo || index < 0 || (unsigned int)index >= g_slots || index >= 256) {
        return -1;
    }
    __try {
        const unsigned char *partner = partner_of(rec_at(index));   /* checked against the couple's identities */
        answer = partner != NULL ? rec_index(partner) : -1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = -1;
    }
    return answer;
}

/* heathen_evo.h section 3: 1 when installed with the Heathen Tribe Expansion row. */
int __stdcall VvfpHeathenAgingEvolution(void) {
    return g_installed && g_evo;
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
    if (woman[R_FACTION] == 0 || !living(woman) || i32(woman, R_PREGNANT) != 0
        || (!g_evo && puzzle_done(LAST_HEATHEN))                 /* decision 2: with the expansion, after it too */
        || (g_evo ? heathens_fit(1) < 1 : free_records() <= HA_ROOM_KEPT)) {   /* the village's own births' room */
        return 0;
    }
    man = father >= 0 && (unsigned int)father < g_slots ? rec_at(father)
        : g_evo && partner_of(woman) != NULL ? partner_of(woman) : random_man(woman);   /* her partner first */
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
        if (g_evo) {
            babies = heathens_fit(babies);
        } else if (babies > free_records() - HA_ROOM_KEPT) {
            babies = free_records() - HA_ROOM_KEPT;
        }
        *(int *)(woman + R_LITTER) = babies;
        known_put(identity(woman), KIND_EXPECTING);
        log_conception(woman, man);                /* the game's hook skips a forced conception */
        if (now) {
            deliver(woman);                    /* (no room: she stays expecting, born later) */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        babies = 0;
    }
    return babies;
}

/* The Origins upgrades' Time Warp (and the Story / Cheat Upgrades' time skip, one Time Warp at a time) write the
   ages themselves, past the age credit, and age only the faction the game ages: they ask this for a Heathen's
   record -- 1 when this companion ages that Heathen (the same rule as the age credit's), so the warp credits
   them too and their old age then comes, unit by unit, through the life tick (live check, #850). */
int __stdcall VvfpHeathenAgingAges(const unsigned char *record) {
    int answer = 0;
    if (!g_installed || record == NULL || rec_index(record) < 0) {
        return 0;
    }
    __try {
        answer = ages(record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = 0;
    }
    return answer;
}

/* 1 when every site is installed, else 0. */
int __stdcall VvfpHeathenAgingInstalled(void) {
    return g_installed;
}

/* Called once by the patcher's start-up chain before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[HA_SITES + 1];
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
    g_evo = vvfp_patcher_file_exists(HE_FLAG_ROW);
    if (g_evo) {
        /* The row folds Heathen Tribe Ages, All Heathens Leave Skeletons and Heathens in Island Events. */
        g_tribe_row = g_bones_all = g_events_row = 1;
        g_bones_former = 0;
        g_births_tenths = vvfp_read_tenths(HE_FILE_BIRTHS, HE_BIRTHS_DEFAULT, HE_BIRTHS_MIN, HE_BIRTHS_MAX);
        g_arrivals_tenths = vvfp_read_tenths(HE_FILE_ARRIVALS, HE_ARRIVALS_DEFAULT, HE_ARRIVALS_MIN, HE_ARRIVALS_MAX);
        g_mask_orange = he_option(HE_OPT_MASK_ORANGE, HE_MASK_ORANGE_DEFAULT, 0, 100);
        g_mask_red = he_option(HE_OPT_MASK_RED, HE_MASK_RED_DEFAULT, 0, 100 - g_mask_orange);
        g_group_max = he_option(HE_OPT_GROUP_MAX, HE_GROUP_MAX_DEFAULT, 1, 4);
        g_he_seed ^= GetTickCount() ^ (GetCurrentProcessId() << 16);
        if (g_he_seed == 0u) {
            g_he_seed = 0x6D2B79F5u;
        }
        memset(g_partner, 0xFF, sizeof g_partner);
    }
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
    if (g_evo) {
        /* the expansion's elder pace site, in the same all-or-none set */
        vvfp_site_branch(&sites[HA_SITES], SITE_WALK, 11, WALK_STOCK, 0xE9, (const void *)walk_stub);
    }
    if (vvfp_install_sites(sites, HA_SITES + (g_evo ? 1 : 0))) {
        g_installed = 1;
        g_walk_installed = g_evo;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
