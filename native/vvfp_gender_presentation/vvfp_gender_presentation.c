/* VVFP Gender Presentation -- a villager drawn with the other sex's heads and bodies, keeping the sex the game
   records for them (the owner, 2026-11-15).  Change Appearance's "Gender presentation: use the other sex's look"
   (all five games) and the Custom Island Event's `presentation` effect (code 23, docs/event-collection/cie-v6-binary.md
   31) set it; native/shared/gender_presentation.h is what they call.

   ONE FEATURE, ONE DLL.  Shipped by each game's "Change Sex and Gender Presentation" row, started by VVFP Startup.dll
   (its second word of companions, native/shared/startup_companions_2.h).

   WHAT IS KEPT.  One value per villager, 0 (the game's own look) or 1 (the other sex's look), in the save's own
   "Virtual Villagers Fun Patcher\Save <S>\Data\Gender Presentation\Gender Presentation - Save <S>.dat": the Head
   Looks' file shape and rules exactly (native/vvfp_head_look/head_look_store.inc, included here with its own magic
   'VGP1', folder and name) -- bound to the living roster, following each villager through deaths, packed reloads,
   reused records, renames (VvfpVillagersRenamed) and sex changes (VvfpVillagerSexChanged, native/shared/
   sex_change.h); another village's file is never replaced; Start Over deletes it (native/shared/save_reset.c).

   THE DRAWS.  Every game picks a villager's head and body sheets from the sex field inside its villager draw
   routines -- the village, the Villager Details portrait, a dialog's figure and (A New Home, The Lost Children) the
   map.  EVERY read of the sex field inside those routines (SITES below; tests/test_gender_presentation.py names each
   routine and checks no other read is there) is spliced to a stub that hands the game the villager's DRAWN sex -- the
   other value when the villager's choice is on, the field's own otherwise -- and goes on at the next instruction:
     * a load (`mov reg, [rec + sex]`): the register gets the drawn sex, every other register and the flags as they
       were;
     * a compare (`cmp [rec + sex], reg`): the same compare of the drawn sex, only the flags differ.
   So each routine draws the villager exactly as it draws a villager of the other sex with the same head and body
   rows -- one consistent sex for the whole draw, a state the stock game draws for every villager of that sex.  The
   record is never written.  A read whose registers do not name a villager record of this game, or a special villager
   (the Golden Child, The Secret City's Tribal Chief and stand-in, New Believers' story villagers), keeps the field.
   Everything else that reads the sex -- breeding, names, pronouns, sounds, the statistics, every companion -- reads
   the record as before.

   THE BIRTH SEX (the owner, 2026-11-15): only villagers born female carry.  The kept value's bits 1 and 2 say the
   villager was born male / female -- written the first time their sex is changed (VvfpVillagerSexChanged: the sex
   of the record `before` it), following them like the presentation (bit 0).  VvfpBornFemale answers from it, else
   from the save's Sex Changes log (sex_change.h vv_sex_born_female_by_log), else the sex now.

   NO CONCEPTION ON THEIR OWN FOR A VILLAGER BORN MALE.  Each game's conception routine is spliced (CONCEPTION
   below): A New Home 0x43BBC0, The Lost Children 0x44B980 and The Secret City 0x455AB0 at their room check (the
   call whose "no room" answer makes the routine return having changed nothing), The Tree of Life 0x45E7B0 and New
   Believers 0x465E00 at their entry (their forced callers pass the room check by).  When the carrier was born male
   the game's own conception does not happen -- the room check answers "no room" (VV1-VV3), or the routine
   returns at once (VV4, VV5), exactly as a full village makes it -- UNLESS the routine was called from outside the
   game's executable: the Custom Island Event's pregnancy with a partner the player chooses (Story / Cheat Upgrades
   calls the routines of The Tree of Life and New Believers; in the other three it writes the fields itself and
   never reaches them), so a player may still give them a baby.

   INSTALLING.  VvfpStartup(game, shipped), on the game's own thread before the title screen: every site must hold its
   stock bytes, then all are written through the shared all-or-none writer (native/shared/install_sites.h), or none;
   then the Change Appearance windows do not offer the checkbox (VvfpGenderPresentationInstalled 0).  The conception
   sites are installed the same way, on their own (all or none): VvfpConceptionGuardInstalled. */
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

#define HL_MAX 256

/* ---- each game's villager records (the Head Look's LAYOUT, native/vvfp_head_look/vvfp_head_look.c) ---------- */

typedef struct {
    unsigned int stride;
    unsigned int present;
    unsigned int name, name_bytes;
    unsigned int sex;
    unsigned int father, mother;
    unsigned int family;
} gp_layout;

static const gp_layout LAYOUT[6] = {
    { 0 },
    { 0x3D8u,  0x28u,   0x370u,  0x1Cu, 0x350u,  0u,      0u,      0x36Cu },
    { 0xE48Cu, 0x30u,   0x564u,  0x18u, 0x538u,  0x57Du,  0x596u,  0u     },
    { 0x1F8Cu, 0xF10u,  0xDD4u,  0x19u, 0xDC8u,  0xDF8u,  0xE11u,  0u     },
    { 0x2E3Cu, 0x1CC4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u     },
    { 0x2F44u, 0x1CD4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u     },
};

static int g_game;
static int g_installed;
static unsigned int g_records;
static int g_count;
static int g_table_read;

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

static int hl_game(void) {
    return g_game;
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

/* What a rename leaves of a villager's identity: the sex and the parents' names (A New Home: the family). */
static unsigned int hl_stable(const unsigned char *r) {
    const gp_layout *l = &LAYOUT[g_game];
    unsigned int h = hl_mix_dword(2166136261u, r + l->sex);
    if (l->family != 0) {
        h = hl_mix_dword(h, r + l->family);
    } else {
        h = hl_text(h, r + l->father, 0x19u);
        h = (h ^ 0xFEu) * 16777619u;
        h = hl_text(h, r + l->mother, 0x19u);
        h = (h ^ 0xFDu) * 16777619u;
    }
    return h ? h : 1u;
}

static unsigned int hl_identity(const unsigned char *r) {
    const gp_layout *l = &LAYOUT[g_game];
    unsigned int h = hl_text(2166136261u, r + l->name, l->name_bytes);
    h = (h ^ 0xFFu) * 16777619u;
    h = (h ^ hl_stable(r)) * 16777619u;
    return h ? h : 1u;
}

static int hl_slot_now(void) {
    return vv_game_save_slot(g_game);
}

/* The Head Looks' store, as this DLL's own file. */
#define HL_MAGIC 0x31504756u            /* 'VGP1' */
#define HL_MAGIC_V1 0u
#define HL_READS_V1 0
#define HL_LOOK_MAX 5                   /* bit 0 the other sex's look; bit 1 born male, bit 2 born female */
#define HL_KIND "Gender Presentation"
#define HL_FILE_NAME "Gender Presentation - Save 0.dat"
#define HL_FILE_SLOT_AT (sizeof "Gender Presentation - Save " - 1)
#include "../vvfp_head_look/head_look_store.inc"

/* A special villager the choice never reaches: the Golden Child, The Secret City's Tribal Chief and stand-in, New
   Believers' story villagers (native/shared/sex_change.h, the same rule as a sex change). */
static int gp_special(const unsigned char *record) {
    return vv_sex_change_refusal(g_game, record, -1) != VV_SEX_OK;
}

int __stdcall VvfpVillagersRenamed(int game, int slot, int count, const void *const *records,
                                   const char *const *old_names) {
    if (game < 1 || game > 5 || game != g_game) {
        return 0;
    }
    return hl_renamed(slot, count, records, old_names, LAYOUT[game].stride, LAYOUT[game].name,
                      LAYOUT[game].name_bytes);
}

#define GP_ON 1
#define GP_BORN_MALE 2
#define GP_BORN_FEMALE 4

int __stdcall VvfpVillagerSexChanged(int game, int slot, const void *record, const void *before) {
    int carried, v;
    if (game < 1 || game > 5 || game != g_game || record == NULL || before == NULL) {
        return 0;
    }
    carried = hl_sex_changed(slot, (const unsigned char *)record, (const unsigned char *)before);
    /* The first change keeps the sex they were born with (the record before it). */
    v = hl_get((const unsigned char *)record);
    if ((v & (GP_BORN_MALE | GP_BORN_FEMALE)) == 0) {
        (void)hl_set((const unsigned char *)record,
                     v | (vv_sex_female(game, (const unsigned char *)before) ? GP_BORN_FEMALE : GP_BORN_MALE));
    }
    return carried;
}

/* 1 when the villager in `record` was born female. */
static int gp_born_female(const unsigned char *record) {
    int v = hl_get(record);
    if (v & GP_BORN_MALE) {
        return 0;
    }
    if (v & GP_BORN_FEMALE) {
        return 1;
    }
    return vv_sex_born_female_by_log(g_game, record);
}

/* ---- the draws ------------------------------------------------------------------------------------------- */

enum { R_EAX, R_ECX, R_EDX, R_EBX, R_ESP, R_EBP, R_ESI, R_EDI, GP_NONE = 0xFF };
enum { GP_LOAD = 0, GP_CMP = 1 };

/* A read of the sex field: `mov reg, [rec_a (+ rec_b) + sex]` (GP_LOAD) or `cmp [rec_a + sex], reg` (GP_CMP). */
typedef struct {
    unsigned int va;
    unsigned char length;
    unsigned char kind;
    unsigned char reg;
    unsigned char rec_a;
    unsigned char rec_b;
    unsigned char stock[7];
} gp_site;

/* A New Home: the Villager Details portrait 0x437340, a dialog's figure 0x4375F0, the village 0x437790 and the map
   0x4388E0 (the routines Grey Hair at 55 reads the head sheets in, native/vv1_grey_hair). */
static const gp_site VV1_SITES[] = {
    { 0x437380u, 6, GP_LOAD, R_EAX, R_EDI, GP_NONE, { 0x8B, 0x87, 0x50, 0x03, 0x00, 0x00 } },
    { 0x43763Eu, 6, GP_LOAD, R_EAX, R_EDI, GP_NONE, { 0x8B, 0x87, 0x50, 0x03, 0x00, 0x00 } },
    { 0x437C12u, 7, GP_LOAD, R_EAX, R_EDX, R_ESI, { 0x8B, 0x84, 0x32, 0x50, 0x03, 0x00, 0x00 } },
    { 0x437D91u, 6, GP_CMP, R_ECX, R_EAX, GP_NONE, { 0x39, 0x88, 0x50, 0x03, 0x00, 0x00 } },
    { 0x4380FDu, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x50, 0x03, 0x00, 0x00 } },
    { 0x4381DFu, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x50, 0x03, 0x00, 0x00 } },
    { 0x4382FCu, 6, GP_LOAD, R_ECX, R_EAX, GP_NONE, { 0x8B, 0x88, 0x50, 0x03, 0x00, 0x00 } },
    { 0x43850Cu, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x50, 0x03, 0x00, 0x00 } },
    { 0x4386EEu, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x50, 0x03, 0x00, 0x00 } },
    { 0x438AB6u, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x50, 0x03, 0x00, 0x00 } },
    { 0x438C2Fu, 7, GP_LOAD, R_EAX, R_ECX, R_ESI, { 0x8B, 0x84, 0x31, 0x50, 0x03, 0x00, 0x00 } },
    { 0x438C97u, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x50, 0x03, 0x00, 0x00 } },
    { 0x438DF5u, 6, GP_LOAD, R_EAX, R_ECX, GP_NONE, { 0x8B, 0x81, 0x50, 0x03, 0x00, 0x00 } },
    { 0x438FB4u, 7, GP_LOAD, R_EAX, R_EDX, R_ESI, { 0x8B, 0x84, 0x32, 0x50, 0x03, 0x00, 0x00 } },
    { 0x439141u, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x50, 0x03, 0x00, 0x00 } },
};

/* The Lost Children: the Villager Details portrait 0x445540, a villager's strip figure 0x445950, the village
   0x445B50 and the map 0x4478E0 (the Head Look's routines). */
static const gp_site VV2_SITES[] = {
    { 0x445580u, 6, GP_LOAD, R_EAX, R_EDI, GP_NONE, { 0x8B, 0x87, 0x38, 0x05, 0x00, 0x00 } },
    { 0x44599Eu, 6, GP_LOAD, R_EAX, R_EDI, GP_NONE, { 0x8B, 0x87, 0x38, 0x05, 0x00, 0x00 } },
    { 0x445F64u, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x38, 0x05, 0x00, 0x00 } },
    { 0x4460F8u, 6, GP_LOAD, R_EAX, R_ECX, GP_NONE, { 0x8B, 0x81, 0x38, 0x05, 0x00, 0x00 } },
    { 0x4462EEu, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x38, 0x05, 0x00, 0x00 } },
    { 0x4465E7u, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x38, 0x05, 0x00, 0x00 } },
    { 0x4469C0u, 6, GP_LOAD, R_ECX, R_EAX, GP_NONE, { 0x8B, 0x88, 0x38, 0x05, 0x00, 0x00 } },
    { 0x446ACAu, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x446C41u, 6, GP_LOAD, R_ECX, R_EAX, GP_NONE, { 0x8B, 0x88, 0x38, 0x05, 0x00, 0x00 } },
    { 0x446E88u, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x446F81u, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x44711Bu, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x447520u, 7, GP_LOAD, R_ECX, R_EDX, R_ESI, { 0x8B, 0x8C, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x4479D0u, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x38, 0x05, 0x00, 0x00 } },
    { 0x447B41u, 6, GP_LOAD, R_EAX, R_ECX, GP_NONE, { 0x8B, 0x81, 0x38, 0x05, 0x00, 0x00 } },
    { 0x4481BEu, 7, GP_LOAD, R_EAX, R_ECX, R_ESI, { 0x8B, 0x84, 0x31, 0x38, 0x05, 0x00, 0x00 } },
    { 0x448267u, 6, GP_CMP, R_EBX, R_ECX, GP_NONE, { 0x39, 0x99, 0x38, 0x05, 0x00, 0x00 } },
    { 0x448413u, 6, GP_LOAD, R_EAX, R_ECX, GP_NONE, { 0x8B, 0x81, 0x38, 0x05, 0x00, 0x00 } },
    { 0x44860Eu, 7, GP_LOAD, R_EAX, R_EDX, R_ESI, { 0x8B, 0x84, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x448803u, 7, GP_LOAD, R_EAX, R_EDX, R_ESI, { 0x8B, 0x84, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x448B79u, 7, GP_LOAD, R_EAX, R_EDX, R_ESI, { 0x8B, 0x84, 0x32, 0x38, 0x05, 0x00, 0x00 } },
    { 0x448EA2u, 7, GP_LOAD, R_EAX, R_EDX, R_ESI, { 0x8B, 0x84, 0x32, 0x38, 0x05, 0x00, 0x00 } },
};

/* The Secret City: the Villager Details portrait 0x4568E0, a villager's figure 0x456CA0, the village 0x4605F0. */
static const gp_site VV3_SITES[] = {
    { 0x456910u, 6, GP_LOAD, R_EAX, R_ESI, GP_NONE, { 0x8B, 0x86, 0xC8, 0x0D, 0x00, 0x00 } },
    { 0x456CDFu, 6, GP_LOAD, R_EAX, R_ESI, GP_NONE, { 0x8B, 0x86, 0xC8, 0x0D, 0x00, 0x00 } },
    { 0x46085Du, 6, GP_LOAD, R_EAX, R_ESI, GP_NONE, { 0x8B, 0x86, 0xC8, 0x0D, 0x00, 0x00 } },
};

/* The Tree of Life: the villager figure 0x45F550, the portrait 0x45F7C0, the village 0x467DA0 (`cmp [esi+0x1B90],
   reg` with the register 0, then setne: the sheet flag the routine passes to every head and body draw). */
static const gp_site VV4_SITES[] = {
    { 0x45F5CFu, 6, GP_CMP, R_EBP, R_ESI, GP_NONE, { 0x39, 0xAE, 0x90, 0x1B, 0x00, 0x00 } },
    { 0x45F8A9u, 6, GP_CMP, R_EAX, R_ESI, GP_NONE, { 0x39, 0x86, 0x90, 0x1B, 0x00, 0x00 } },
    { 0x467E60u, 6, GP_CMP, R_EDX, R_ESI, GP_NONE, { 0x39, 0x96, 0x90, 0x1B, 0x00, 0x00 } },
};

/* New Believers: the villager figure 0x466C40, the portrait 0x466EF0, the village 0x4720E0 (the same shapes). */
static const gp_site VV5_SITES[] = {
    { 0x466CC3u, 6, GP_CMP, R_EBP, R_ESI, GP_NONE, { 0x39, 0xAE, 0x90, 0x1B, 0x00, 0x00 } },
    { 0x466FD9u, 6, GP_CMP, R_EAX, R_ESI, GP_NONE, { 0x39, 0x86, 0x90, 0x1B, 0x00, 0x00 } },
    { 0x472286u, 6, GP_CMP, R_EBX, R_ESI, GP_NONE, { 0x39, 0x9E, 0x90, 0x1B, 0x00, 0x00 } },
};

static const gp_site *g_sites;

/* The sex the read at site `s` hands the game, for the registers in `frame` ([0..7] pushad: edi, esi, ebp, esp,
   ebx, edx, ecx, eax): the villager's drawn sex; the field itself for anything that is not plainly a villager record
   of this game, or a special villager. */
static int gp_drawn_sex(const gp_site *s, const unsigned int *frame) {
    const gp_layout *l = &LAYOUT[g_game];
    unsigned int rec = frame[7 - s->rec_a] + (s->rec_b != GP_NONE ? frame[7 - s->rec_b] : 0u);
    int sex = *(const int *)(UINT_PTR)(rec + l->sex);
    int male = g_game <= 2 ? 1 : 0, female = g_game <= 2 ? 2 : 1;
    hl_locate();
    if (g_records == 0 || rec < g_records || (rec - g_records) % l->stride != 0
        || (rec - g_records) / l->stride >= (unsigned int)g_count || (sex != male && sex != female)
        || gp_special((const unsigned char *)(UINT_PTR)rec)) {
        return sex;
    }
    if ((hl_get((const unsigned char *)(UINT_PTR)rec) & GP_ON) == 0) {
        return sex;
    }
    return sex == male ? female : male;
}

/* A compare: `frame` [0..7] pushad, [8] the site's number, replaced with where the game goes on.  Returns the drawn
   sex in the low half and the compared register in the high half. */
static unsigned __int64 __cdecl gp_cmp_operands(unsigned int *frame) {
    const gp_site *s = &g_sites[frame[8]];
    unsigned int other = frame[7 - s->reg];
    frame[8] = s->va + s->length;
    return ((unsigned __int64)other << 32) | (unsigned int)gp_drawn_sex(s, frame);
}

static __declspec(naked) void gp_cmp_common(void) {
    __asm {
        pushad
        push esp
        call gp_cmp_operands
        add esp, 4
        cmp eax, edx                        ; the game's own compare, of the drawn sex
        popad                               ; (popad and ret leave the flags alone)
        ret                                 ; to the instruction after the site
    }
}

/* A load: `frame` [0..7] pushad, [8] the flags (pushfd), [9] the site's number, replaced with where the game goes
   on.  The destination register gets the drawn sex. */
static void __cdecl gp_load_sex(unsigned int *frame) {
    const gp_site *s = &g_sites[frame[9]];
    frame[9] = s->va + s->length;
    frame[7 - s->reg] = (unsigned int)gp_drawn_sex(s, frame);
}

static __declspec(naked) void gp_load_common(void) {
    __asm {
        pushfd
        pushad
        push esp
        call gp_load_sex
        add esp, 4
        popad
        popfd
        ret
    }
}

#define GP_STUB(n) static __declspec(naked) void gp_stub_##n(void) { __asm push n __asm jmp gp_cmp_common } \
    static __declspec(naked) void gp_lstub_##n(void) { __asm push n __asm jmp gp_load_common }
GP_STUB(0) GP_STUB(1) GP_STUB(2) GP_STUB(3) GP_STUB(4) GP_STUB(5) GP_STUB(6) GP_STUB(7) GP_STUB(8) GP_STUB(9)
GP_STUB(10) GP_STUB(11) GP_STUB(12) GP_STUB(13) GP_STUB(14) GP_STUB(15) GP_STUB(16) GP_STUB(17) GP_STUB(18)
GP_STUB(19) GP_STUB(20) GP_STUB(21)

static void (*const GP_STUBS[])(void) = {
    gp_stub_0, gp_stub_1, gp_stub_2, gp_stub_3, gp_stub_4, gp_stub_5, gp_stub_6, gp_stub_7, gp_stub_8, gp_stub_9,
    gp_stub_10, gp_stub_11, gp_stub_12, gp_stub_13, gp_stub_14, gp_stub_15, gp_stub_16, gp_stub_17, gp_stub_18,
    gp_stub_19, gp_stub_20, gp_stub_21,
};
static void (*const GP_LSTUBS[])(void) = {
    gp_lstub_0, gp_lstub_1, gp_lstub_2, gp_lstub_3, gp_lstub_4, gp_lstub_5, gp_lstub_6, gp_lstub_7, gp_lstub_8,
    gp_lstub_9, gp_lstub_10, gp_lstub_11, gp_lstub_12, gp_lstub_13, gp_lstub_14, gp_lstub_15, gp_lstub_16,
    gp_lstub_17, gp_lstub_18, gp_lstub_19, gp_lstub_20, gp_lstub_21,
};

#define GP_N(a) (sizeof a / sizeof a[0])
typedef char gp_enough_stubs[(GP_N(VV1_SITES) <= GP_N(GP_STUBS) && GP_N(VV2_SITES) <= GP_N(GP_STUBS)
                              && GP_N(VV3_SITES) <= GP_N(GP_STUBS) && GP_N(VV4_SITES) <= GP_N(GP_STUBS)
                              && GP_N(VV5_SITES) <= GP_N(GP_STUBS)) ? 1 : -1];

/* The draw sites' writes into `w`. */
static void gp_fill(const gp_site *sites, int count, vvfp_site_write *w) {
    int i;
    for (i = 0; i < count; ++i) {
        vvfp_site_branch(&w[i], sites[i].va, sites[i].length, sites[i].stock, 0xE9,
                         (const void *)(sites[i].kind == GP_LOAD ? GP_LSTUBS[i] : GP_STUBS[i]));
    }
    g_sites = sites;
}

/* ---- CONCEPTION --------------------------------------------------------------------------------------------- */

/* Each game's conception routine, its site and how its carrier is found:
     VV1 0x43BBC0  thiscall on the records (edi = ecx), the carrier's index the first argument; the room check
                   `call 0x43A1A0` at 0x43BBC3 (after `push edi`).
     VV2 0x44B980  the same shape: `call 0x44B310` at 0x44B983.
     VV3 0x455AB0  thiscall on the carrier (esi = ecx); `call 0x45FE30` at 0x455AB8 (after `push esi`).
     VV4 0x45E7B0  thiscall on the carrier, ret 0x1C; its entry `push ebx / mov bl, [esp+0x20]` (5 bytes).
     VV5 0x465E00  the same. */
typedef struct {
    unsigned int va;
    unsigned char stock[5];
    unsigned int target;            /* the room check (VV1-VV3), 0: an entry site */
    unsigned int stride;            /* VV1, VV2: the records' stride (the carrier = edi + index * stride) */
} gp_conception;

static const gp_conception CONCEPTION[6] = {
    { 0 },
    { 0x43BBC3u, { 0xE8, 0xD8, 0xE5, 0xFF, 0xFF }, 0x43A1A0u, 0x3D8u },
    { 0x44B983u, { 0xE8, 0x88, 0xF9, 0xFF, 0xFF }, 0x44B310u, 0xE48Cu },
    { 0x455AB8u, { 0xE8, 0x73, 0xA3, 0x00, 0x00 }, 0x45FE30u, 0u },
    { 0x45E7B0u, { 0x53, 0x8A, 0x5C, 0x24, 0x20 }, 0u, 0u },
    { 0x465E00u, { 0x53, 0x8A, 0x5C, 0x24, 0x20 }, 0u, 0u },
};

static int g_guard_installed;
static unsigned int g_guard_target;     /* VV1-VV3: the room check; VV4, VV5: the entry's next instruction */
static unsigned int g_image_end;        /* the executable's image: 0x400000 .. here */

/* A caller inside the game's own executable: the game's conception, not the Custom Island Event's. */
static int gp_from_game(unsigned int return_address) {
    return return_address >= 0x400000u && return_address < g_image_end;
}

/* 1 when the conception must not happen: a carrier born male, the game's own call. */
static int gp_conception_refused(const unsigned char *carrier, unsigned int routine_return) {
    if (!gp_from_game(routine_return) || carrier == NULL) {
        return 0;
    }
    hl_locate();
    if (g_records == 0 || (unsigned int)(UINT_PTR)carrier < g_records
        || ((unsigned int)(UINT_PTR)carrier - g_records) % LAYOUT[g_game].stride != 0
        || ((unsigned int)(UINT_PTR)carrier - g_records) / LAYOUT[g_game].stride >= (unsigned int)g_count) {
        return 0;
    }
    return !gp_born_female(carrier);
}

/* The room check (VV1-VV3): `frame` [0..7] pushad, [8] the return into the routine, [9] the register the routine
   pushed, [10] the routine's return, [11] its first argument.  Returns the room check to go to, or 0: "no room". */
static unsigned int __cdecl gp_room_decide(unsigned int *frame) {
    const gp_conception *c = &CONCEPTION[g_game];
    const unsigned char *carrier = c->stride != 0
        ? (const unsigned char *)(UINT_PTR)(frame[7 - R_EDI] + frame[11] * c->stride)
        : (const unsigned char *)(UINT_PTR)frame[7 - R_ESI];
    if (gp_conception_refused(carrier, frame[10])) {
        frame[7 - R_EAX] = 0;
        return 0;
    }
    return g_guard_target;
}

static void __cdecl gp_room_frame(unsigned int *regs, unsigned int *ret_at);

static __declspec(naked) void gp_room_stub(void) {
    __asm {
        push 0                              ; the room check to go to (0: none)
        pushad
        lea eax, [esp + 0x24]               ; the return into the routine
        push eax
        lea eax, [esp + 4]
        push eax
        call gp_room_frame
        add esp, 8
        popad
        cmp dword ptr [esp], 0
        je refused
        ret                                 ; to the room check, which returns into the routine
    refused:
        add esp, 4
        ret                                 ; "no room": al = 0
    }
}

/* `regs` pushad, `ret_at` the return into the routine (the frame above it). */
static void __cdecl gp_room_frame(unsigned int *regs, unsigned int *ret_at) {
    unsigned int frame[12];
    int k;
    for (k = 0; k < 8; ++k) {
        frame[k] = regs[k];
    }
    frame[8] = ret_at[0];
    frame[9] = ret_at[1];
    frame[10] = ret_at[2];
    frame[11] = ret_at[3];
    regs[8] = gp_room_decide(frame);        /* the slot pushed first */
    regs[7 - R_EAX] = frame[7 - R_EAX];
}

/* The entry (VV4, VV5): `regs` pushad, `ret_at` the routine's return.  1 when refused. */
static int __cdecl gp_entry_frame(unsigned int *regs, unsigned int *ret_at) {
    return gp_conception_refused((const unsigned char *)(UINT_PTR)regs[7 - R_ECX], ret_at[0]);
}

static __declspec(naked) void gp_entry_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 0x20]               ; the routine's return
        push eax
        lea eax, [esp + 4]
        push eax
        call gp_entry_frame
        add esp, 8
        test eax, eax
        popad
        jne refused
        push ebx                            ; the displaced entry
        mov bl, byte ptr [esp + 0x20]
        jmp dword ptr [g_guard_target]
    refused:
        ret 0x1C                            ; returns at once, nothing written (as when there is no room)
    }
}

/* The conception site's write into `w`; 1 when there is one. */
static int gp_guard_fill(vvfp_site_write *w) {
    const gp_conception *c = &CONCEPTION[g_game];
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)(UINT_PTR)0x400000u;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)(UINT_PTR)(0x400000u + (unsigned int)dos->e_lfanew);
    if (c->va == 0) {
        return 0;
    }
    g_image_end = 0x400000u + nt->OptionalHeader.SizeOfImage;
    if (c->target != 0) {
        g_guard_target = c->target;
        vvfp_site_branch(&w[0], c->va, 5, c->stock, 0xE8, (const void *)gp_room_stub);
    } else {
        g_guard_target = c->va + 5;
        vvfp_site_branch(&w[0], c->va, 5, c->stock, 0xE9, (const void *)gp_entry_stub);
    }
    return 1;
}

/* ---- exports ---------------------------------------------------------------------------------------------- */

void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[GP_N(GP_STUBS) + 1];
    static const struct { const gp_site *sites; int count; } TABLE[6] = {
        { NULL, 0 }, { VV1_SITES, (int)GP_N(VV1_SITES) }, { VV2_SITES, (int)GP_N(VV2_SITES) },
        { VV3_SITES, (int)GP_N(VV3_SITES) }, { VV4_SITES, (int)GP_N(VV4_SITES) }, { VV5_SITES, (int)GP_N(VV5_SITES) },
    };
    int count;
    (void)shipped;
    if (g_game != 0 || game < 1 || game > 5) {
        return;
    }
    g_game = game;
    count = TABLE[game].count;
    gp_fill(TABLE[game].sites, count, w);
    count += gp_guard_fill(&w[count]);
    /* One all-or-none install: the draws and the conception guard together. */
    g_installed = g_guard_installed = vvfp_install_sites(w, count);
}

int __stdcall VvfpConceptionGuardInstalled(int game) {
    return g_game != 0 && game == g_game && g_guard_installed;
}

int __stdcall VvfpBornFemale(int game, const void *record) {
    if (game != g_game || g_game == 0 || record == NULL) {
        return vv_sex_game_ok(game) && record != NULL ? vv_sex_born_female_by_log(game, record) : 0;
    }
    return gp_born_female((const unsigned char *)record);
}

int __stdcall VvfpGenderPresentationInstalled(int game) {
    return g_game != 0 && game == g_game && g_installed;
}

int __stdcall VvfpGenderPresentationGet(int game, const void *record) {
    if (game != g_game || g_game == 0 || record == NULL) {
        return 0;
    }
    return (hl_get((const unsigned char *)record) & GP_ON) != 0;
}

int __stdcall VvfpGenderPresentationSet(int game, const void *record, int on) {
    if (game != g_game || g_game == 0 || record == NULL || (on != 0 && on != 1)
        || gp_special((const unsigned char *)record)) {
        return 0;
    }
    return hl_set((const unsigned char *)record, (hl_get((const unsigned char *)record) & ~GP_ON) | on);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
