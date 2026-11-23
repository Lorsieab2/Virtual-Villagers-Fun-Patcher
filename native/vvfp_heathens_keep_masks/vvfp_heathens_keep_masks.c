/* VVFP Heathens Keep Masks -- "Heathens Keep Their Masks When Converted", New Believers.

   The owner (2026-11-08): "Heathens keep their masks when converted -- when a heathen converts their mask stays
   on their head (as if the player manually set it using Change Appearance)."  "Oh and the player can always
   Change Appearance to change it or take it off if they want to."  And: "Reset to original" gives the Heathen
   mask back -- a convert's original look is the head and body they had with the mask they wore.

   THE STOCK GAME.  A Heathen joins the tribe through the conversion 0x4668B0 (what SetFaith 0x467F90 calls when
   a Heathen's Faith rises above 0 -- preaching, Spreading the Word, the Earthquake, the puzzle rewards, island
   events -- and what the Story / Cheat Upgrades' Custom Island Event "Becomes a believer" calls).  It clears the
   role +0x1CFC unless it is 13, the Heathen Chief's (0x466966; he stays the tribe's Retired Chief), then the
   faction byte +0x1CEC (0x46697D, through the setter 0x466880(0)).  The game draws a Heathen's mask only while
   that byte is set (0x4728C6), so the mask is gone.  The one other way a Heathen becomes a believer is The
   Defector's "welcome" (0x416970): SetFaith(+20) -- which converts through 0x4668B0 when the Faith rises above
   0 -- and then the setter 0x466880(0) directly (0x41699F), which makes a Heathen whose Faith stayed at 0 or
   below a believer without the conversion.

   THE MASK THEY WORE is the game's own choice (0x4728C6, native/shared/former_heathens.h vv_former_kind_of):
   purple for the roles 12 and 14-16 (the Heathen Doctor and the three Masters), the Chief's for role 13, else
   orange (+0x1CED), red (+0x1CEE) or blue -- or, for a Heathen who went back to the Heathens (below), the mask
   this companion draws on them.

   WHAT THIS COMPANION DOES.  At both places -- inside the conversion just before the role is cleared
   (0x466966, the `cmp dword [esi+0x1CFC], 13`), and at The Defector's direct call of the setter (0x41699F) --
   while the record is still a Heathen:
     * the mask they wear (1 Blue, 2 Orange, 3 Red, 4 Purple, 5 the Tribal Chief's) is handed to the Origins
       companion's VvfpMaskKeep, which puts it in the store Change Appearance keeps a believer's mask in (its
       mask table and Village Masks file) -- at once, or, while that slot's file has not loaded yet (held by
       another program a moment), as soon as the load settles.  So the convert is drawn with the mask exactly as
       a believer whose mask the player chose (the Origins render, 0x472481), Change Appearance shows it as
       their mask, and the player can change it or take it off as with any other;
     * "VVFP Original Look.dll" is told (VvfpOriginalLookConverted): their original look, kept while they were a
       Heathen with no mask, takes the mask, so Reset to original gives it back (original_look_store.inc
       ol_converted has the rule).  Without that companion nothing is told: Reset to original then has the
       original it has.
   Nothing is charged and no "Appearance changed" is logged: the villager's look did not change.

   GOING BACK TO THE HEATHENS.  The owner (2026-11-22): "a villager who goes back to the Heathens gets back
   exactly the mask they wore as a Heathen before -- blue, orange, red, purple, or the Chief's mask -- whatever it
   was; behaviour is always an ordinary blue Heathen (listens, convertible; never the puzzle role again: not a
   Master, not the Chief)."  (The owner's "yellow" is the game's orange.)  The Heathen Doctor (cured: 0x468DA0's
   drop-cure converts him) and the Heathen Mommy (her puzzle sets her Faith to 50-59) can join and go back, and
   are treated the same way: their own mask, a blue Heathen's behaviour.
     * THE STOCK GAME.  Every way a believer becomes a Heathen ends in the faction setter 0x466880 with 1: from
       0x4669E0 (SetFaith 0x467F90 at Faith 0 or below -- the Faith drift and The Breaking Point, every island
       event's Faith, The Spa and The Cracked Mask first, the Custom Island Event's and the Story / Cheat
       Upgrades' "Becomes a Heathen", the events Pick Island Event starts), which clears the role first
       (0x4669F5); The Spa's own call at 0x415D0C and The Cracked Mask's at 0x416C5B, which make a believer whose
       Faith their SetFaith(-10) did not take to 0 a Heathen without 0x4669E0, the role kept (cod_arrivals.inc
       lists all seven callers of the setter).  The conversion leaves the kind bytes +0x1CED (orange) and +0x1CEE
       (red), so a convert from orange goes back an orange Heathen in look and behaviour (the drop test 0x443D4D
       turns them away; the chasers' AI reads the same byte); "New Heathens Get a Heathen's Faith" clears both
       bytes for the drift's conversions (blue in look and behaviour); a convert from purple goes back blue; the
       Retired Chief through The Spa's own call goes back the Heathen Chief, puzzle role and all.
     * WHAT THIS COMPANION DOES.  At those three places, while the record is still a believer (at 0x4669F5 just
       before the role is cleared, so the Retired Chief is still seen): the mask they wore as a Heathen is found
       -- the Former Heathens file's entry for them ("VVFP Cause of Death.dll", VvfpCauseFormerKind: filed at
       their conversion, kept by the villager, never by the record), else the Retired Chief's role 13, else the
       orange or red byte the conversion left -- and put in the Origins store as their mask (VvfpMaskKeep 1..5);
       then both kind bytes and the role are cleared, so the game itself treats them as a Heathen in the blue
       mask everywhere it asks.  A believer whose Heathen mask is not known (never a Heathen, or converted before
       anything recorded it) and whose Change Appearance mask is orange, red, purple or the Chief's has it set to
       blue: a mask chosen for a believer is never taken for one they wore.  Without the store (or when it
       refuses) nothing is touched: the stock game.
     * THE DRAWING.  The game picks a Heathen's mask art from the kind bytes at four places in the villager
       render, 0x472732 and 0x472758 (the head) and 0x4728EB and 0x472903 (the mask), and from the role at
       0x4728C6 (12 and 14-16 purple, 13 the Chief's, the table 0x472B60) -- all drawing only.  Each is spliced:
       for an ordinary Heathen (no puzzle role 12-17) with neither byte whose Origins mask is orange, red, purple or the Chief's, the
       orange (red) test answers "set" and the role read answers 14 (13) for that one draw; everyone else gets the
       game's own answer.  The bytes and the role the behaviour reads stay 0.  The blue mask needs nothing: the
       game's blue is the only blue it draws.
     * JOINING AGAIN.  When such a Heathen converts, the mask kept is the one drawn on them (not the blue the bytes
       say), and an orange or red one's kind byte is put back as the stock conversion leaves a convert's.  The
       logs' Mask line and the Former Heathens file name the mask drawn (native/shared/former_heathens.h
       vv_former_drawn_kind asks VvfpHeathensKeepMasksLook).

   ONLY WITH THE ORIGINS COMPANION.  The store belongs to "VVFP Origins Icons.dll" (Enable Origins-Exclusive
   Features, this row's dependency).  When it is not loaded or has no VvfpMaskKeep, nothing is kept: the convert
   loses the mask as in the stock game, and a believer going back is as in the stock game.

   HOW.  All ten sites are spliced at run time, after their stock bytes are checked, all or none
   (native/shared/install_sites.h); no executable byte is patched.  A conversion splice saves every register and
   flag, does the above under structured exception handling (a fault keeps nothing and the conversion goes on),
   then makes the very instruction it replaced and goes on where the game would, the setter seeing its stock
   return address.  A drawing splice keeps every register (but eax at the role read, which the game loads
   there) and sets the zero flag as the compare it replaced would, for the jump after it.  Started by VVFP
   Startup.dll (its second word, native/shared/startup_companions_2.h).  No debug output, no text shown. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/former_heathens.h"
#include "../shared/original_look.h"
#include "../shared/sidecar_io.h"
#include "../shared/save_folder.h"
#include "../shared/per_save_data.h"
#include "../shared/mask_follow.h"
#include "../shared/foreign_sidecar.h"
#include "../shared/game_save_slot.h"
#include "../shared/vv5_villager_table.h"

#define HK_GAME 5
#define HK_ORIGINS "VVFP Origins Icons.dll"
#define HK_CAUSE "VVFP Cause of Death.dll"

/* The conversion's role test: cmp dword [esi+0x1CFC], 0xD -- then je 0x466979. */
#define HK_CONVERT_SITE 0x466966u
#define HK_CONVERT_NEXT 0x46696Du
/* The Defector's call of the setter with 0: call 0x466880, returning to 0x4169A4. */
#define HK_DEFECTOR_SITE 0x41699Fu
#define HK_DEFECTOR_NEXT 0x4169A4u
#define HK_FACTION_SETTER 0x466880u
/* 0x4669E0 (to a Heathen) clearing the role: mov dword [esi+0x1CFC], 0 -- then its call of the setter. */
#define HK_ROLE_CLEAR_SITE 0x4669F5u
#define HK_ROLE_CLEAR_NEXT 0x4669FFu
/* The Spa's and The Cracked Mask's own calls of the setter with 1 (pushed; ecx the record). */
#define HK_SPA_SITE 0x415D0Cu
#define HK_SPA_NEXT 0x415D11u
#define HK_CRACKED_SITE 0x416C5Bu
#define HK_CRACKED_NEXT 0x416C60u
/* The render's kind tests: cmp byte [esi+0x1CED], 0 (orange) and cmp byte [esi+0x1CEE], 0 (red). */
#define HK_HEAD_ORANGE_SITE 0x472732u
#define HK_HEAD_ORANGE_NEXT 0x472739u
#define HK_HEAD_RED_SITE 0x472758u
#define HK_HEAD_RED_NEXT 0x47275Fu
#define HK_MASK_ORANGE_SITE 0x4728EBu
#define HK_MASK_ORANGE_NEXT 0x4728F2u
#define HK_MASK_RED_SITE 0x472903u
#define HK_MASK_RED_NEXT 0x47290Au
/* The render's role read for the mask art: mov eax, [esi+0x1CFC]. */
#define HK_MASK_ROLE_SITE 0x4728C6u
#define HK_MASK_ROLE_NEXT 0x4728CCu
#define HK_SITES 10

static const unsigned char CONVERT_STOCK[7] = { 0x83, 0xBE, 0xFC, 0x1C, 0x00, 0x00, 0x0D };
static const unsigned char DEFECTOR_STOCK[5] = { 0xE8, 0xDC, 0xFE, 0x04, 0x00 };
static const unsigned char ROLE_CLEAR_STOCK[10] = { 0xC7, 0x86, 0xFC, 0x1C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
static const unsigned char SPA_STOCK[5] = { 0xE8, 0x6F, 0x0B, 0x05, 0x00 };
static const unsigned char CRACKED_STOCK[5] = { 0xE8, 0x20, 0xFC, 0x04, 0x00 };
static const unsigned char ORANGE_TEST_STOCK[7] = { 0x80, 0xBE, 0xED, 0x1C, 0x00, 0x00, 0x00 };
static const unsigned char RED_TEST_STOCK[7] = { 0x80, 0xBE, 0xEE, 0x1C, 0x00, 0x00, 0x00 };
static const unsigned char ROLE_READ_STOCK[6] = { 0x8B, 0x86, 0xFC, 0x1C, 0x00, 0x00 };

#define HK_MASK_BLUE 1                  /* the Origins store's masks: 1 Blue .. 5 the Tribal Chief's */
#define HK_MASK_CHIEF 5
#define HK_ROLE_MASTER 14               /* a Master's role: the purple mask art (0x472B60) */
#define HK_ROLE_CHIEF 13
/* The puzzle Heathens' roles (the Heathen Doctor 12, Chief 13, three Masters 14-16, Mommy 17).  Every other role a
   Heathen has (1..11: the camp's own jobs, the save holds them) is an ordinary Heathen's. */
#define HK_ROLE_FIRST_PUZZLE 12
#define HK_ROLE_LAST_PUZZLE 17

static int g_installed;
static unsigned int g_kept;             /* masks handed to the store this session (the tests read it) */
static unsigned int g_returned;         /* masks given back to a villager going back (the tests read it) */

/* ---- THE MASKS WORN: this companion's own per-villager file ---------------------------------------------------
   The owner (2026-11-22): Keep Masks remembers the mask each convert wore as a Heathen ITSELF, so it is known when
   they go back whatever other patch is on (the Former Heathens file is Log Every Death's).  The Head Looks' store
   (native/vvfp_head_look/head_look_store.inc), as this DLL's own file -- the pattern of the Origins masks: the save's
   own "Virtual Villagers Fun Patcher\Save <S>\Data\Heathens Keep Masks\Masks Worn - Save <S>.dat", following each
   villager by identity (name, sex and the parents' names) through deaths, births, packed loads, renames in play
   and at a load (VvfpVillagersRenamed, from "VVFP Last Names.dll") and a slot another village reuses (never
   inherited).  The value: 1 Blue, 2 Orange, 3 Red, 4 Purple, 5 the Tribal Chief's (VV_FORMER_* + 1); 0 none.
   Kept at every conversion while this row is installed (hk_keep), read first when they go back (hk_wore). */
#define HL_MAX 256
static unsigned int g_hk_records;
static int g_hk_count;

static void hl_locate(void) {
    unsigned int rva = 0, slots = 0;
    if (g_hk_records != 0) {
        return;
    }
    vv5_villager_table((const unsigned char *)(UINT_PTR)0x400000u, &rva, &slots);
    g_hk_records = 0x400000u + rva + 0x48u;
    g_hk_count = (int)slots;
}

static int hl_game(void) {
    return HK_GAME;
}

static int hl_slots(void) {
    hl_locate();
    return g_hk_count < HL_MAX ? g_hk_count : HL_MAX;
}

static const unsigned char *hl_record(int i) {
    hl_locate();
    if (g_hk_records == 0 || i < 0 || i >= g_hk_count) {
        return NULL;
    }
    return (const unsigned char *)(UINT_PTR)(g_hk_records + (unsigned int)i * 0x2F44u);
}

static int hl_present(const unsigned char *r) {
    return r[0x1CD4] != 0;
}

static unsigned int hl_text(unsigned int h, const unsigned char *text, unsigned int capacity) {
    unsigned int k;
    for (k = 0; k < capacity && text[k]; ++k) {
        h = (h ^ text[k]) * 16777619u;
    }
    return h;
}

/* What a rename leaves of a villager's identity: the sex and the parents' names. */
static unsigned int hl_stable(const unsigned char *r) {
    unsigned int h = 2166136261u;
    int k;
    for (k = 0; k < 4; ++k) {
        h = (h ^ r[0x1B90 + k]) * 16777619u;
    }
    h = hl_text(h, r + 0x1BC0, 0x19u);
    h = (h ^ 0xFEu) * 16777619u;
    h = hl_text(h, r + 0x1BD9, 0x19u);
    h = (h ^ 0xFDu) * 16777619u;
    return h ? h : 1u;
}

static unsigned int hl_identity(const unsigned char *r) {
    unsigned int h = hl_text(2166136261u, r + 0x1B9C, 0x19u);
    h = (h ^ 0xFFu) * 16777619u;
    h = (h ^ hl_stable(r)) * 16777619u;
    return h ? h : 1u;
}

static int hl_slot_now(void) {
    return vv_game_save_slot(HK_GAME);
}

#define HL_MAGIC 0x314D4B56u            /* 'VKM1' */
#define HL_MAGIC_V1 0u
#define HL_READS_V1 0
#define HL_LOOK_MAX 5                   /* VV_FORMER_CHIEF + 1 */
#define HL_KIND "Heathens Keep Masks"
#define HL_FILE_NAME "Masks Worn - Save 0.dat"
#define HL_FILE_SLOT_AT (sizeof "Masks Worn - Save " - 1)
#include "../vvfp_head_look/head_look_store.inc"

/* The mask the villager in `record` wore as a Heathen, as this companion kept it (VV_FORMER_*), or -1.  The
   village is looked at now, not a moment ago. */
static int hk_worn_get(const unsigned char *record) {
    int v;
    g_sync_tick = GetTickCount() - HL_SYNC_MS;
    v = hl_get(record);
    return v >= 1 && v <= HL_LOOK_MAX ? v - 1 : -1;
}

/* Keep `kind` (VV_FORMER_*) as the mask the villager in `record` wore as a Heathen. */
static void hk_worn_set(const unsigned char *record, int kind) {
    if (kind >= VV_FORMER_BLUE && kind <= VV_FORMER_CHIEF) {
        (void)hl_set(record, kind + 1);
    }
}

/* Villagers renamed as the village loaded ("VVFP Last Names.dll" names Heathens with no last name): their masks
   worn stay theirs (native/shared/villager_rekey.h). */
int __stdcall VvfpVillagersRenamed(int game, int slot, int count, const void *const *records,
                                   const char *const *old_names) {
    if (game != HK_GAME || !g_installed) {
        return 0;
    }
    return hl_renamed(slot, count, records, old_names, 0x2F44u, 0x1B9Cu, 0x19u);
}

/* Start Over or a deleted tribe ("VVFP Save Reset.dll", before the slot's folder -- the Masks Worn file with it --
   is deleted): the masks worn held for that slot are dropped, so nothing of the erased village is written into the
   new one; the next look reads the slot's file afresh (gone: nobody has one). */
void __stdcall VvfpHeathensKeepMasksVillageReset(int game, int slot) {
    if (game != HK_GAME || slot < 1 || slot > 5 || (g_slot != 0 && g_slot != slot)) {
        return;
    }
    memset(g_look, 0, sizeof g_look);
    memset(g_look_id, 0, sizeof g_look_id);
    memset(g_roster, 0, sizeof g_roster);
    memset(g_stable, 0, sizeof g_stable);
    g_have_roster = 0;
    g_sync_tried = 0;
    g_slot = 0;
}

/* A villager's sex changed (native/shared/sex_change.h): their mask worn stays theirs. */
int __stdcall VvfpVillagerSexChanged(int game, int slot, const void *record, const void *before) {
    if (game != HK_GAME || !g_installed) {
        return 0;
    }
    return hl_sex_changed(slot, (const unsigned char *)record, (const unsigned char *)before);
}

typedef int (__stdcall *hk_keep_fn)(void *record, int mask);
typedef int (__stdcall *hk_mask_of_fn)(void *record);
typedef int (__stdcall *hk_converted_fn)(int game, const void *record, int mask);
typedef int (__stdcall *hk_former_fn)(const void *record);

static hk_keep_fn hk_keep_export(void) {
    HMODULE origins = GetModuleHandleA(HK_ORIGINS);
    return origins != NULL ? (hk_keep_fn)GetProcAddress(origins, "VvfpMaskKeep") : NULL;
}

/* The Origins store's reader, found once (the render asks it for every Heathen it draws). */
static hk_mask_of_fn hk_mask_of_export(void) {
    static hk_mask_of_fn mask_of;
    if (mask_of == NULL) {
        HMODULE origins = GetModuleHandleA(HK_ORIGINS);
        mask_of = origins != NULL ? (hk_mask_of_fn)GetProcAddress(origins, "VvfpMaskOf") : NULL;
    }
    return mask_of;
}

/* The mask a Heathen who went back to the Heathens is drawn with: VV_FORMER_ORANGE..VV_FORMER_CHIEF for a
   ordinary Heathen (no puzzle role 12-17) with neither kind byte whose Origins mask is orange, red, purple or the Chief's; -1 for
   anyone else (the game's own choice stands). */
static int hk_look(const unsigned char *record) {
    hk_mask_of_fn mask_of;
    int mask, role;
    if (record == NULL || record[VV5_FACTION] == 0 || record[VV5_ORANGE] != 0 || record[VV5_RED] != 0) {
        return -1;
    }
    role = *(const int *)(record + VV5_TYPE);
    if (role >= HK_ROLE_FIRST_PUZZLE && role <= HK_ROLE_LAST_PUZZLE) {
        return -1;                      /* a puzzle Heathen: their role draws their mask */
    }
    mask_of = hk_mask_of_export();
    if (mask_of == NULL) {
        return -1;
    }
    mask = mask_of((void *)record);
    return mask > HK_MASK_BLUE && mask <= HK_MASK_CHIEF ? mask - 1 : -1;
}

/* The mask the believer in `record` wore as a Heathen (VV_FORMER_*), or -1 when it is not known: the Former
   Heathens file's entry, else the Retired Chief's role, else the kind byte the conversion left. */
static int hk_wore(const unsigned char *record) {
    HMODULE cause;
    hk_former_fn former;
    int kind = hk_worn_get(record), role;          /* this companion's own file first */
    if (kind >= VV_FORMER_BLUE && kind <= VV_FORMER_CHIEF) {
        return kind;
    }
    cause = GetModuleHandleA(HK_CAUSE);
    former = cause != NULL ? (hk_former_fn)GetProcAddress(cause, "VvfpCauseFormerKind") : NULL;
    kind = former != NULL ? former(record) : -1;
    if (kind >= VV_FORMER_BLUE && kind <= VV_FORMER_CHIEF) {
        return kind;
    }
    role = *(const int *)(record + VV5_TYPE);
    if (role == HK_ROLE_CHIEF) {
        return VV_FORMER_CHIEF;
    }
    if (record[VV5_ORANGE] != 0) {
        return VV_FORMER_ORANGE;
    }
    return record[VV5_RED] != 0 ? VV_FORMER_RED : -1;
}

/* The Heathen in `record` is joining the tribe: the mask they wear becomes their Change Appearance mask, and
   part of their original look. */
static void hk_keep(unsigned char *record) {
    HMODULE looks;
    hk_keep_fn keep;
    hk_converted_fn converted;
    int mask, look;
    if (record == NULL || record[VV5_FACTION] == 0) {
        return;                         /* already a believer: nothing to keep */
    }
    keep = hk_keep_export();
    if (keep == NULL) {
        return;                         /* no New Believers Origins companion: the stock loss */
    }
    look = hk_look(record);
    mask = vv_former_kind_of(record) + 1;           /* VV_FORMER_BLUE..CHIEF -> 1..5 */
    if (look >= 0) {
        /* Went back to the Heathens and comes again: the mask drawn on them; an orange or red one's kind byte
           put back as the stock conversion leaves a convert's. */
        mask = look + 1;
        if (look == VV_FORMER_ORANGE || look == VV_FORMER_RED) {
            record[look == VV_FORMER_ORANGE ? VV5_ORANGE : VV5_RED] = 1;
        }
    }
    hk_worn_set(record, mask - 1);      /* remembered by this companion for when they go back */
    if (keep(record, mask) <= 0) {
        return;                         /* refused: not a villager record the store knows */
    }
    ++g_kept;
    looks = GetModuleHandleA(VVFP_ORIGINAL_LOOK_DLL);
    converted = looks != NULL ? (hk_converted_fn)GetProcAddress(looks, VVFP_ORIGINAL_LOOK_CONVERTED) : NULL;
    if (converted != NULL) {
        (void)converted(HK_GAME, record, mask);
    }
}

/* The believer in `record` is going back to the Heathens (the setter is about to write 1): the mask they wore
   as a Heathen is put in the Origins store, and the kind bytes and the role cleared -- drawn in their own
   mask, treated by the game as an ordinary Heathen in the blue mask. */
static void hk_return(unsigned char *record) {
    hk_keep_fn keep;
    hk_mask_of_fn mask_of;
    int wore;
    if (record == NULL || record[VV5_FACTION] != 0) {
        return;                         /* a Heathen already (The Spa's second call): no change */
    }
    keep = hk_keep_export();
    if (keep == NULL) {
        return;                         /* no store to keep the mask in: the stock game */
    }
    wore = hk_wore(record);
    if (wore < 0) {
        /* Not known to have worn a mask: one chosen for them as a believer is not one they wore. */
        mask_of = hk_mask_of_export();
        if (mask_of != NULL) {
            int mask = mask_of(record);
            if (mask > HK_MASK_BLUE && mask <= HK_MASK_CHIEF) {
                (void)keep(record, HK_MASK_BLUE);
            }
        }
        return;
    }
    if (keep(record, wore + 1) <= 0) {
        return;                         /* refused: the stock game */
    }
    record[VV5_ORANGE] = 0;
    record[VV5_RED] = 0;
    *(int *)(record + VV5_TYPE) = 0;    /* never the puzzle role again */
    ++g_returned;
}

static void __stdcall hk_converting(unsigned char *record) {
    __try {
        hk_keep(record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

static void __stdcall hk_returning(unsigned char *record) {
    __try {
        hk_return(record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The render's kind tests: 1 when the orange (red) mask is drawn on `record`. */
static int __stdcall hk_drawn_orange(const unsigned char *record) {
    __try {
        (void)hl_sync();                /* the masks worn follow the village (throttled, HL_SYNC_MS) */
        return record[VV5_ORANGE] != 0 || hk_look(record) == VV_FORMER_ORANGE;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

static int __stdcall hk_drawn_red(const unsigned char *record) {
    __try {
        return record[VV5_RED] != 0 || hk_look(record) == VV_FORMER_RED;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

/* The render's role read for the mask art: the record's role, or a Master's (purple) or the Chief's for one
   drawn in that mask. */
static int __stdcall hk_drawn_role(const unsigned char *record) {
    int role = *(const int *)(record + VV5_TYPE), look;
    __try {
        look = hk_look(record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        look = -1;
    }
    return look == VV_FORMER_MASTER ? HK_ROLE_MASTER : look == VV_FORMER_CHIEF ? HK_ROLE_CHIEF : role;
}

/* In place of the conversion's role test: esi is the record. */
__declspec(naked) static void hk_convert_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call hk_converting
        popad
        popfd
        cmp dword ptr [esi + 0x1CFC], 0x0D
        push HK_CONVERT_NEXT
        ret
    }
}

/* In place of The Defector's `call 0x466880` (its argument 0 already pushed): ecx is the record. */
__declspec(naked) static void hk_defector_stub(void) {
    __asm {
        pushfd
        pushad
        push ecx
        call hk_converting
        popad
        popfd
        push HK_DEFECTOR_NEXT
        push HK_FACTION_SETTER
        ret
    }
}

/* In place of 0x4669E0's `mov dword [esi+0x1CFC], 0`: esi is the record, its role still there. */
__declspec(naked) static void hk_role_clear_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call hk_returning
        popad
        popfd
        mov dword ptr [esi + 0x1CFC], 0
        push HK_ROLE_CLEAR_NEXT
        ret
    }
}

/* In place of The Spa's / The Cracked Mask's `call 0x466880` with 1 (already pushed): ecx is the record; the
   setter returns where the stock call would (the Cause of Death companion's splice of the setter reads it). */
__declspec(naked) static void hk_spa_stub(void) {
    __asm {
        pushfd
        pushad
        push ecx
        call hk_returning
        popad
        popfd
        push HK_SPA_NEXT
        push HK_FACTION_SETTER
        ret
    }
}

__declspec(naked) static void hk_cracked_stub(void) {
    __asm {
        pushfd
        pushad
        push ecx
        call hk_returning
        popad
        popfd
        push HK_CRACKED_NEXT
        push HK_FACTION_SETTER
        ret
    }
}

/* In place of a render kind test: ZF set when the mask is NOT drawn, as `cmp byte [esi+..], 0` sets it.  popad,
   push and ret leave the flags as `test` made them. */
__declspec(naked) static void hk_head_orange_stub(void) {
    __asm {
        pushad
        push esi
        call hk_drawn_orange
        test eax, eax
        popad
        push HK_HEAD_ORANGE_NEXT
        ret
    }
}

__declspec(naked) static void hk_head_red_stub(void) {
    __asm {
        pushad
        push esi
        call hk_drawn_red
        test eax, eax
        popad
        push HK_HEAD_RED_NEXT
        ret
    }
}

__declspec(naked) static void hk_mask_orange_stub(void) {
    __asm {
        pushad
        push esi
        call hk_drawn_orange
        test eax, eax
        popad
        push HK_MASK_ORANGE_NEXT
        ret
    }
}

__declspec(naked) static void hk_mask_red_stub(void) {
    __asm {
        pushad
        push esi
        call hk_drawn_red
        test eax, eax
        popad
        push HK_MASK_RED_NEXT
        ret
    }
}

/* In place of the render's `mov eax, [esi+0x1CFC]` (the next instruction sets the flags itself): eax the role
   drawn, every other register kept. */
__declspec(naked) static void hk_mask_role_stub(void) {
    __asm {
        push ecx
        push edx
        push esi
        call hk_drawn_role
        pop edx
        pop ecx
        push HK_MASK_ROLE_NEXT
        ret
    }
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpHeathensKeepMasksInstalled(void) {
    return g_installed;
}

/* How many masks were handed to the store this session (for the tests' emulation). */
unsigned int __stdcall VvfpHeathensKeepMasksKept(void) {
    return g_kept;
}

/* How many villagers going back to the Heathens had their mask given back this session (the tests). */
unsigned int __stdcall VvfpHeathensKeepMasksReturned(void) {
    return g_returned;
}

/* int __stdcall VvfpHeathensKeepMasksFaction(void *record, int faction): a companion is about to call the faction
   setter 0x466880 itself with `faction` -- the Story / Cheat Upgrades' Custom Island Event "Becomes a Heathen"
   (1) and "Becomes a believer" (0) after their SetFaith, which convert through the spliced routines unless the
   villager's Faith was already past 0 (story_graph.inc cg_keep_masks_faction).  Does what the splices do at the
   game's own calls: 1, a believer going back, gets their own mask and an ordinary blue Heathen's bytes and role;
   0, a Heathen joining, keeps their mask.  1 when installed (done, or nothing to do), 0 when not. */
int __stdcall VvfpHeathensKeepMasksFaction(void *record, int faction) {
    if (!g_installed) {
        return 0;
    }
    if (faction != 0) {
        hk_returning((unsigned char *)record);
    } else {
        hk_converting((unsigned char *)record);
    }
    return 1;
}

/* int __stdcall VvfpHeathensKeepMasksLook(const void *record): the mask this companion draws on a Heathen who
   went back to the Heathens -- VV_FORMER_ORANGE (1), VV_FORMER_RED (2), VV_FORMER_MASTER (3, purple) or
   VV_FORMER_CHIEF (4) -- or -1 (not installed, not such a Heathen: the game's own mask choice stands).  For
   the logs and the Former Heathens file (native/shared/former_heathens.h vv_former_drawn_kind). */
int __stdcall VvfpHeathensKeepMasksLook(const void *record) {
    if (!g_installed) {
        return -1;
    }
    __try {
        return hk_look((const unsigned char *)record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return -1;
    }
}

/* Called once by VVFP Startup.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[HK_SITES];
    (void)shipped;
    if (g_installed || game != HK_GAME) {
        return;
    }
    vvfp_site_branch(&sites[0], HK_CONVERT_SITE, (int)sizeof CONVERT_STOCK, CONVERT_STOCK, 0xE9,
                     (const void *)hk_convert_stub);
    vvfp_site_branch(&sites[1], HK_DEFECTOR_SITE, (int)sizeof DEFECTOR_STOCK, DEFECTOR_STOCK, 0xE9,
                     (const void *)hk_defector_stub);
    vvfp_site_branch(&sites[2], HK_ROLE_CLEAR_SITE, (int)sizeof ROLE_CLEAR_STOCK, ROLE_CLEAR_STOCK, 0xE9,
                     (const void *)hk_role_clear_stub);
    vvfp_site_branch(&sites[3], HK_SPA_SITE, (int)sizeof SPA_STOCK, SPA_STOCK, 0xE9, (const void *)hk_spa_stub);
    vvfp_site_branch(&sites[4], HK_CRACKED_SITE, (int)sizeof CRACKED_STOCK, CRACKED_STOCK, 0xE9,
                     (const void *)hk_cracked_stub);
    vvfp_site_branch(&sites[5], HK_HEAD_ORANGE_SITE, (int)sizeof ORANGE_TEST_STOCK, ORANGE_TEST_STOCK, 0xE9,
                     (const void *)hk_head_orange_stub);
    vvfp_site_branch(&sites[6], HK_HEAD_RED_SITE, (int)sizeof RED_TEST_STOCK, RED_TEST_STOCK, 0xE9,
                     (const void *)hk_head_red_stub);
    vvfp_site_branch(&sites[7], HK_MASK_ORANGE_SITE, (int)sizeof ORANGE_TEST_STOCK, ORANGE_TEST_STOCK, 0xE9,
                     (const void *)hk_mask_orange_stub);
    vvfp_site_branch(&sites[8], HK_MASK_RED_SITE, (int)sizeof RED_TEST_STOCK, RED_TEST_STOCK, 0xE9,
                     (const void *)hk_mask_red_stub);
    vvfp_site_branch(&sites[9], HK_MASK_ROLE_SITE, (int)sizeof ROLE_READ_STOCK, ROLE_READ_STOCK, 0xE9,
                     (const void *)hk_mask_role_stub);
    if (vvfp_install_sites(sites, HK_SITES)) {
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
