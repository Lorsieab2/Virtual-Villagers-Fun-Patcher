/* heathen_evo.h -- the shared interface of "Heathen Tribe Expansion and Evolution" (New Believers, v1.35.101).

   docs/heathen-tribe-expansion-design.md section 13 (W-0) and docs/heathen-tribe-expansion-decisions.md (the
   owner's decisions, 2026-11-26, which override the design where they differ).  Three companions share it:

     "VVFP Heathen Aging.dll"     (W-A, native/vvfp_heathen_aging)     tribe life and population;
     "VVFP Heathen Life.dll"      (W-B, native/vvfp_heathen_life)      sickness, show meals, show harvests and
                                                                         facility visits, skill practice;
     "VVFP Heathen Mausoleum.dll" (W-C, native/vvfp_heathen_mausoleum) Heathen graves at the mud hut.

   Everything here is a name, a number or a file layout; nothing here runs on its own.  Header-only and static.
   Every companion finds another one's export with GetModuleHandleA + GetProcAddress (never LoadLibrary: a companion
   that is not shipped is simply absent), and treats a missing export as "that companion is not there".

   ---------------------------------------------------------------------------------------------------------------
   1. THE FILES IN THE PATCHER'S FOLDER (beside the companions: native/shared/patcher_files.h).  W-D writes them.

     HE_FLAG_ROW         "VVFP Heathen Tribe Evolution.txt"   the row's flag.  It stands for the three rows it folds
                         (Heathen Tribe Ages, Dies and Has Children; All Heathens Leave Skeletons; Heathens can be
                         selected in Island Events/Heathen-Exclusive Events), so with it the old three flags are not
                         needed.  The old flags are still read, so an old patch set works until W-D migrates it.
     HE_FILE_BIRTHS      "VVFP Heathen Tribe Births.txt"      the "0.1-10x Heathen Tribe Births" slider, written as
                         the patcher's multiplier_text ("1", "0.5", "2.5"; native/shared/multiplier_choice.h), read
                         as tenths within HE_BIRTHS_MIN..HE_BIRTHS_MAX; missing or unreadable: HE_BIRTHS_DEFAULT (1x).
     HE_FILE_ARRIVALS    "VVFP Heathen Arrivals.txt"          the "0-10x New Heathen Arrivals" slider, tenths within
                         HE_ARRIVALS_MIN..HE_ARRIVALS_MAX ("0" is off); missing or unreadable: HE_ARRIVALS_DEFAULT
                         (0, off).  Decision 3: 0 in Default Patches, 1x in Owner's Defaults.
     HE_FILE_OPTIONS     "VVFP Heathen Options.txt"           optional key=value lines (ASCII, one a line, '#'
                         comments, unknown keys ignored), read by he_option() below; a missing file or key is the
                         default the reader passes.  The keys:
                           mask_orange_percent  (default 7)   decision 7: arrivals and newborns 90% blue,
                           mask_red_percent     (default 3)     7% orange, 3% red;
                           group_max            (default 4)   decision 5: an arrival is a group of 1..group_max;
                           sick_floor           (default 21)  decision 8 (W-B): a sick Heathen's health floor;
                           show_percent         (default 0 = W-B's own choice)  W-B's show-action mix.
                         W-D need not write the file: every default is the owner's decision.

   2. THE SLIDER RATES (W-A; decision 4).  Every roll is drawn from the companion's own xorshift (slider_scale.h's
      rule), never the game's rand 0x403660.  t = the slider in tenths.
        Births:   each eligible woman (an aging Heathen woman 14-45, not expecting, not the Heathen Mommy, in a
                  couple whose man is a living adult Heathen) rolls 1 in HE_BIRTH_ROLL x W / t a unit, W the number
                  of such women: about one conception for the whole tribe every 240 units (24 real hours on
                  Normal) at 1x.
        Arrivals: once a unit of the village's clock (the age credit of the first living record), 1 in
                  HE_ARRIVAL_ROLL / t: about one arrival (a single Heathen or a group) every 480 units (48 real
                  hours on Normal) at 1x; t = 0 none.

   3. THE BRIDGE EXPORTS.

     VvfpHeathenLifeUnit (exported by Heathen Life, called by Heathen Aging's life-tick splice 0x472CB7):
         int __stdcall VvfpHeathenLifeUnit(unsigned char *record, int flags);
       `record` a living aging Heathen.  flags HE_LIFE_UNIT: one age unit was just processed for it (its processed
       age already advanced, old age and births done; it did not die).  flags HE_LIFE_IDLE: no unit is due this
       pass -- only the sick-byte question below is asked (called every pass, so keep it cheap).
       HE_LIFE_ROW is or-ed in when the Heathen Tribe Expansion row is on.
       Returns HE_LIFE_KEEP_SICK (bit 0): keep the record's sick byte this pass (Heathen Aging then skips the stock
       Heathen skip that clears it), and HE_LIFE_HANDLED (bit 1): Heathen Life did its part.  0: the stock rule.
     VvfpHeathenAgingCoupleOf (exported by Heathen Aging):
         int __stdcall VvfpHeathenAgingCoupleOf(int index);
       the record index of the living partner of the Heathen in record `index`, or -1 (none, not installed).
     VvfpHeathenAgingEvolution (exported by Heathen Aging):
         int __stdcall VvfpHeathenAgingEvolution(void);
       1 when Heathen Aging is installed with the Heathen Tribe Expansion row's flag, else 0.
     VvfpHeathenMausoleumIsHeathenGrave (exported by Heathen Mausoleum):
         int __stdcall VvfpHeathenMausoleumIsHeathenGrave(int entry);
     VvfpHeathenMausoleumVillageReset (exported by Heathen Mausoleum, called by "VVFP Save Reset.dll"):
         void __stdcall VvfpHeathenMausoleumVillageReset(int game, int slot);

   4. THE LOG EXPORTS Heathen Aging calls (each optional: a missing export writes nothing).
     WriteParentageRecordWithFather ("VVFP Parentage Export.dll", existing): a forced Heathen conception's
       Conception record (the game's own hook at 0x465F34 skips forced conceptions: `test bl,bl; jnz done`).
     WriteParentageHeathenCouple ("VVFP Parentage Export.dll", NEW -- W-D adds it; decision 16):
         int __stdcall WriteParentageHeathenCouple(int game, const void *records, const void *woman,
                                                   const void *man);
       a "Couple formed" record in the Births and Conceptions log: both names and ages, "Faction: Heathen"
       ("Isolan" with the Guardians of Isola Rewrite).  `records` is the villager manager, as for the Conception.
     VvfpCauseHeathenArrived ("VVFP Cause of Death.dll", existing): an Arrived record, "How:" the words below.
     VvfpCauseHeathenRole ("VVFP Cause of Death.dll", NEW -- decision 16):
         void __stdcall VvfpCauseHeathenRole(int game, int index, int role);
       a "Took the role" record in the Births log for the Heathen in record `index` who has just become the camp's
       `role` (13 Chief, 14 Master Scientist, 15 Master Builder, 16 Master Farmer), marked a Heathen.
     VvfpStorySetCustomTitle ("VVFP Story Upgrades.dll", NEW -- not built yet; Story Upgrades owns the Custom
       Titles file and is its only writer):
         int __stdcall VvfpStorySetCustomTitle(int game, int index, const char *title);
       sets the cosmetic Chief's or Master's custom title (decision 6).  Until it exists no title is set (the
       skills, the mask and the Took the role record still are).

   5. THE DATA FILES (per save slot, beside the saves: Documents\LDW\<exe>\Virtual Villagers Fun Patcher\Save <S>\
      Data\...), each written through native/shared/sidecar_io.h (atomic; an unreadable file is never replaced, an
      invalid one is set aside).  Little-endian u32s throughout.

     Couples (W-A): Data\Heathen Couples\Heathen Couples - Save <S>.dat
         header  HE_COUPLES_MAGIC 'VHC1', HE_COUPLES_VERSION 1, game 5, count, slot   (20 bytes; slot at +16,
                 retagged by Copy / Move Player Slot: src/vv_copy_slot.py)
         count x he_couple (16 bytes): woman identity, man identity, formed (the woman's processed age then),
                 state (HE_COUPLE_ACTIVE; an ended couple is dropped from the file)
       Identities are native/shared/custom_titles.h vv_title_identity (name, likes, dislikes), as the Heathen Aging
       file's; src/vv_last_names.py's offline rename rekeys both identity fields.

     Mausoleum (W-C): Data\Heathen Mausoleum\Heathen Mausoleum - Save <S>.dat
         header  HE_MAUSOLEUM_MAGIC 'VHM1', HE_MAUSOLEUM_VERSION 1, game 5, count, slot   (20 bytes)
         count entries of HE_ROSTER_ENTRY (0x5C) bytes, the stock Roster of the Dead layout (name +0, age +0x1C,
         head +0x20, body +0x24, profession +0x28, skill value +0x2C, flags +0x31..+0x33, cause +0x34, epitaph
         +0x38 char[0x20]), packed with no holes, at most HE_ROSTER_MAX. */
#ifndef VV_HEATHEN_EVO_H
#define VV_HEATHEN_EVO_H

#include <windows.h>
#include "patcher_files.h"

/* ---- 1. files ---------------------------------------------------------------------------------------------- */
#define HE_FLAG_ROW "VVFP Heathen Tribe Evolution.txt"
#define HE_FILE_BIRTHS "VVFP Heathen Tribe Births.txt"
#define HE_FILE_ARRIVALS "VVFP Heathen Arrivals.txt"
#define HE_FILE_OPTIONS "VVFP Heathen Options.txt"

#define HE_BIRTHS_MIN 1u                 /* 0.1x */
#define HE_BIRTHS_MAX 100u               /* 10x */
#define HE_BIRTHS_DEFAULT 10u            /* 1x */
#define HE_ARRIVALS_MIN 0u               /* off */
#define HE_ARRIVALS_MAX 100u             /* 10x */
#define HE_ARRIVALS_DEFAULT 0u           /* off */

#define HE_OPT_MASK_ORANGE "mask_orange_percent"
#define HE_OPT_MASK_RED "mask_red_percent"
#define HE_OPT_GROUP_MAX "group_max"
#define HE_OPT_SICK_FLOOR "sick_floor"
#define HE_OPT_SHOW_PERCENT "show_percent"
#define HE_MASK_ORANGE_DEFAULT 7
#define HE_MASK_RED_DEFAULT 3
#define HE_GROUP_MAX_DEFAULT 4
#define HE_SICK_FLOOR_DEFAULT 21

/* ---- 2. rates ---------------------------------------------------------------------------------------------- */
#define HE_BIRTH_ROLL 2400u              /* 240 units x 10 tenths */
#define HE_ARRIVAL_ROLL 4800u            /* 480 units x 10 tenths */
#define HE_ROOM_KEPT 10                  /* decision 18: records always left free, beside the believers' room */
/* The litter (the stock odds without the Medicine 3 gate, 0x465ECD..0x465F2D): rolled out of 10,000. */
#define HE_TRIPLETS_IN_10000 175         /* 1.75% */
#define HE_TWINS_IN_10000 525            /* 5.25% */

/* ---- 3. bridge exports ------------------------------------------------------------------------------------- */
#define HE_LIFE_DLL "VVFP Heathen Life.dll"
#define HE_LIFE_EXPORT "VvfpHeathenLifeUnit"
#define HE_LIFE_IDLE 0
#define HE_LIFE_UNIT 1
#define HE_LIFE_ROW 0x100
#define HE_LIFE_KEEP_SICK 1
#define HE_LIFE_HANDLED 2
typedef int (__stdcall *he_life_unit_fn)(unsigned char *record, int flags);

#define HE_AGING_DLL "VVFP Heathen Aging.dll"
#define HE_AGING_COUPLE_EXPORT "VvfpHeathenAgingCoupleOf"
#define HE_AGING_EVOLUTION_EXPORT "VvfpHeathenAgingEvolution"
typedef int (__stdcall *he_couple_of_fn)(int index);
typedef int (__stdcall *he_evolution_fn)(void);

#define HE_MAUSOLEUM_DLL "VVFP Heathen Mausoleum.dll"
#define HE_MAUSOLEUM_GRAVE_EXPORT "VvfpHeathenMausoleumIsHeathenGrave"
#define HE_MAUSOLEUM_RESET_EXPORT "VvfpHeathenMausoleumVillageReset"
typedef int (__stdcall *he_is_heathen_grave_fn)(int entry);
typedef void (__stdcall *he_village_reset_fn)(int game, int slot);

/* ---- 4. log exports ---------------------------------------------------------------------------------------- */
#define HE_PARENTAGE_DLL "VVFP Parentage Export.dll"
#define HE_CONCEPTION_EXPORT "WriteParentageRecordWithFather"
#define HE_COUPLE_LOG_EXPORT "WriteParentageHeathenCouple"
typedef int (__stdcall *he_conception_fn)(int game, const void *records, const void *mother, const void *father);
typedef int (__stdcall *he_couple_log_fn)(int game, const void *records, const void *woman, const void *man);

#define HE_CAUSE_DLL "VVFP Cause of Death.dll"
#define HE_ARRIVED_EXPORT "VvfpCauseHeathenArrived"
#define HE_ROLE_EXPORT "VvfpCauseHeathenRole"
typedef void (__stdcall *he_arrived_fn)(int game, int index, const char *how);
typedef void (__stdcall *he_role_fn)(int game, int index, int role);

#define HE_STORY_DLL "VVFP Story Upgrades.dll"
#define HE_TITLE_EXPORT "VvfpStorySetCustomTitle"
typedef int (__stdcall *he_set_title_fn)(int game, int index, const char *title);

/* The Arrived record's "How:" of a new arrival (decision 5), in both wordings (the Guardians of Isola Rewrite:
   native/shared/isolan_log_words.h; every reader takes both).  "%d" is the number of the others (1..3). */
#define HE_ARRIVED_ALONE_HEATHEN "Arrived at the Heathen camp"
#define HE_ARRIVED_ALONE_ISOLAN "Arrived at the Isolan camp"
#define HE_ARRIVED_GROUP_HEATHEN "Arrived at the Heathen camp with %d other%s"
#define HE_ARRIVED_GROUP_ISOLAN "Arrived at the Isolan camp with %d other%s"

/* ---- 5. data files ----------------------------------------------------------------------------------------- */
#define HE_COUPLES_MAGIC 0x31434856u     /* 'VHC1' */
#define HE_COUPLES_VERSION 1u
#define HE_COUPLES_HEADER 20u
#define HE_COUPLES_MAX 128               /* 256 records: at most 128 couples */
#define HE_COUPLE_ACTIVE 0u
#define HE_COUPLES_FOLDER "Heathen Couples"
#define HE_COUPLES_FILE "Heathen Couples - Save %d.dat"
typedef struct {
    unsigned int woman;                  /* identities (vv_title_identity) */
    unsigned int man;
    unsigned int formed;                 /* the woman's processed age when they paired */
    unsigned int state;                  /* HE_COUPLE_ACTIVE */
} he_couple;

#define HE_MAUSOLEUM_MAGIC 0x314D4856u   /* 'VHM1' */
#define HE_MAUSOLEUM_VERSION 1u
#define HE_MAUSOLEUM_HEADER 20u
#define HE_ROSTER_ENTRY 0x5Cu
#define HE_ROSTER_MAX 500
#define HE_MAUSOLEUM_FOLDER "Heathen Mausoleum"
#define HE_MAUSOLEUM_FILE "Heathen Mausoleum - Save %d.dat"

/* ---- the options reader ------------------------------------------------------------------------------------ */

/* The value of `key` in HE_FILE_OPTIONS ("key=value", spaces around either ignored, a decimal integer, '-'
   allowed), kept within [minimum, maximum]; `fallback` when the file, the key or a number is missing.  Only the
   first 4 KB are read; nothing is written. */
static int he_option(const char *key, int fallback, int minimum, int maximum) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    char text[4096];
    DWORD got = 0, i = 0;
    HANDLE file;
    int key_length = lstrlenA(key);
    if (key_length <= 0 || vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, HE_FILE_OPTIONS) == 0) {
        return fallback;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return fallback;
    }
    if (!ReadFile(file, text, (DWORD)(sizeof text - 1), &got, NULL)) {
        got = 0;
    }
    CloseHandle(file);
    text[got] = '\0';
    while (i < got) {
        DWORD start, k;
        while (i < got && (text[i] == ' ' || text[i] == '\t' || text[i] == '\r' || text[i] == '\n')) {
            ++i;
        }
        start = i;
        while (i < got && text[i] != '\n') {
            ++i;
        }
        if (text[start] == '#' || i - start <= (DWORD)key_length) {
            continue;
        }
        for (k = 0; k < (DWORD)key_length && text[start + k] == key[k]; ++k) {
        }
        if (k == (DWORD)key_length) {
            DWORD p = start + k;
            int negative = 0, digits = 0, value = 0;
            while (p < i && (text[p] == ' ' || text[p] == '\t')) {
                ++p;
            }
            if (p >= i || text[p] != '=') {
                continue;
            }
            ++p;
            while (p < i && (text[p] == ' ' || text[p] == '\t')) {
                ++p;
            }
            if (p < i && text[p] == '-') {
                negative = 1;
                ++p;
            }
            for (; p < i && text[p] >= '0' && text[p] <= '9'; ++p) {
                if (value < 100000) {
                    value = value * 10 + (text[p] - '0');
                }
                ++digits;
            }
            if (digits == 0) {
                return fallback;
            }
            value = negative ? -value : value;
            return value < minimum ? minimum : value > maximum ? maximum : value;
        }
    }
    return fallback;
}

#endif /* VV_HEATHEN_EVO_H */
