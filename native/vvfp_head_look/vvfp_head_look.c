/* VVFP Head Look -- the head look Change Appearance chooses for each villager (the owner, 2026-10-28):
   Auto (the game's own rule: the old head from a shown age of 1,100 age units, 55 years), Young (always
   the young head) or Old (always the old, grey head).  So a 30-year-old can have grey hair and a
   70-year-old can keep young hair.  Auto is every villager's look until the player picks another.

   ONE FEATURE, ONE DLL.  The choice is made in each game's Origins Change Appearance window (native/
   shared/head_look.h names the windows), which asks this DLL for the look and hands it the player's
   choice; this DLL keeps the looks (head_look_store.inc: the patcher's own per-save file, following each
   villager) and makes the game's draws follow them.  It is shipped by each game's Origins row and started
   by VVFP Startup.dll (its second word of companions, native/shared/startup_companions_2.h).

   THE DRAWS.  Every place the later games choose between a villager's young and old head compares the
   age the game shows against the constant 1,100 and nothing else.  Each such compare (SITES below; their
   callers are cited in tests/test_head_look.py) is spliced to a stub that makes the same compare against
   the villager's EFFECTIVE age -- the real one under Auto, 0 under Young, 1,100 under Old -- and goes on
   at the next instruction with every register as it was.  Only the flags differ, so the game's own code
   picks the head atlas or column exactly as it would for a villager of that age: nothing else about the
   villager, the record or the head value (+head offset) is changed, so the logs, the Family Tree, the
   genetics and the Origins masks see the same head as before.  A compare whose registers do not name a
   villager record of this game, or whose age is not that record's, keeps the real age.

   A NEW HOME has no old head of its own: its old (grey) heads are Grey Hair at 55's (native/vv1_grey_hair),
   which asks VvfpHeadLookGet for each villager it draws.  Here this DLL writes nothing to the game.

   INSTALLING.  VvfpStartup(game, shipped) from VVFP Startup.dll, on the game's own thread, before the title
   screen: every site must hold its stock bytes, then all of them are written through the shared
   all-or-none writer (native/shared/install_sites.h), or none.  A build where any differs installs
   nothing and every villager is drawn by the game's own rule; the Change Appearance windows then do not
   offer the choice (VvfpHeadLookInstalled). */
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
#include "../shared/vv1_grey_hair.h"

#define HL_MAX 256

/* ---- each game's villager records -------------------------------------------------------------- */

/* The record fields a look is kept by: the masks' identity (name, sex, the parents' names; A New Home has
   no parents' names and keeps the family number instead) and the presence test the masks use.  The same
   offsets as the Story / Cheat Upgrades adapters (native/vvfp_story_upgrades/story_c*.inc). */
typedef struct {
    unsigned int stride;
    unsigned int present;           /* the byte that says a record is held */
    unsigned int name, name_bytes;
    unsigned int sex;
    unsigned int father, mother;    /* the parents' names, 0x19 bytes each (0: none in this game) */
    unsigned int family;            /* A New Home's family number (0: none) */
    unsigned int age;               /* the age the game shows, which the draws compare against 1,100 */
} hl_layout;

static const hl_layout LAYOUT[6] = {
    { 0 },
    { 0x3D8u,  0x28u,   0x370u,  0x1Cu, 0x350u,  0u,      0u,      0x36Cu, 0x348u },
    { 0xE48Cu, 0x30u,   0x564u,  0x18u, 0x538u,  0x57Du,  0x596u,  0u,     0x530u },
    { 0x1F8Cu, 0xF10u,  0xDD4u,  0x19u, 0xDC8u,  0xDF8u,  0xE11u,  0u,     0xDC4u },
    { 0x2E3Cu, 0x1CC4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1B8Cu },
    { 0x2F44u, 0x1CD4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1B8Cu },
};

static int g_game;                  /* the game this process is (VvfpStartup), 0 before */
static int g_installed;             /* the draws follow the look */
static unsigned int g_records;      /* record 0 */
static int g_count;                 /* records in this build: 150 or 256 */

/* Record 0 and the record count of the running executable: A New Home and The Lost Children keep a
   pointer to their array ([0x48B614], [0x499F24], 256 records); The Secret City, The Tree of Life and New
   Believers a manager the executable itself names (150 records, or 256 in the 256 Villagers build). */
static int g_table_read;            /* The Secret City to New Believers: the table is read once */

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

/* What a rename leaves of a villager's identity: the sex and the parents' names (A New Home: the sex and
   the family).  Never 0. */
static unsigned int hl_stable(const unsigned char *r) {
    const hl_layout *l = &LAYOUT[g_game];
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

/* A held record's identity: the name and hl_stable's part.  Never 0. */
static unsigned int hl_identity(const unsigned char *r) {
    const hl_layout *l = &LAYOUT[g_game];
    unsigned int h = hl_text(2166136261u, r + l->name, l->name_bytes);
    h = (h ^ 0xFFu) * 16777619u;
    h = (h ^ hl_stable(r)) * 16777619u;
    return h ? h : 1u;
}

/* The slot the game itself saves to (native/shared/game_save_slot.h). */
static int hl_slot_now(void) {
    return vv_game_save_slot(g_game);
}

#include "head_look_store.inc"

/* ---- the draws ------------------------------------------------------------------------------------- */

/* Register numbers as x86 encodes them; HL_NONE for no second register. */
enum { R_EAX, R_ECX, R_EDX, R_EBX, R_ESP, R_EBP, R_ESI, R_EDI, HL_NONE = 0xFF };

/* A compare of the shown age against 1,100.  `age_reg` HL_NONE: `cmp dword [rec + age], 1100`, the
   record in `rec_a`; else `cmp age_reg, 1100`, the record `rec_a` + `rec_b` (the age already read from it,
   and checked against it again here). */
typedef struct {
    unsigned int va;
    unsigned char length;
    unsigned char age_reg;
    unsigned char rec_a;
    unsigned char rec_b;
    unsigned char stock[10];
} hl_site;

#define CMP_MEM_ESI(va) { va, 10, HL_NONE, R_ESI, HL_NONE, { 0x81, 0xBE, 0x8C, 0x1B, 0x00, 0x00, 0x4C, 0x04, 0x00, 0x00 } }

/* New Believers (callers: tests/test_head_look.py): the village 0x4720E0, the villager figure 0x466C40
   and the portrait 0x466EF0. */
static const hl_site VV5_SITES[] = {
    CMP_MEM_ESI(0x4722A2u), CMP_MEM_ESI(0x466DC1u), CMP_MEM_ESI(0x466FE6u),
};

/* The Tree of Life: the village 0x467DA0, the villager figure 0x45F550 (the Villager Details portrait,
   through 0x460BF0) and the portrait 0x45F7C0 -- the same shapes as New Believers'. */
static const hl_site VV4_SITES[] = {
    CMP_MEM_ESI(0x467E89u), CMP_MEM_ESI(0x45F6C4u), CMP_MEM_ESI(0x45F8B6u),
};

/* `cmp eax, 1100` (5 bytes) and `cmp ecx, 1100` (6 bytes), the age read from [record + age] a few
   instructions before. */
#define CMP_EAX(va, rec_a, rec_b) { va, 5, R_EAX, rec_a, rec_b, { 0x3D, 0x4C, 0x04, 0x00, 0x00 } }
#define CMP_ECX(va, rec_a, rec_b) { va, 6, R_ECX, rec_a, rec_b, { 0x81, 0xF9, 0x4C, 0x04, 0x00, 0x00 } }

/* The Secret City (record in ESI, the age in EAX or ECX): the village 0x4605F0 (two compares, one per
   faction branch), the Villager Details portrait 0x4568E0, and a villager's figure 0x456CA0 (the island
   event dialog 0x418460, and 0x41BDD0). */
static const hl_site VV3_SITES[] = {
    CMP_EAX(0x46086Du, R_ESI, HL_NONE), CMP_EAX(0x4608AEu, R_ESI, HL_NONE),
    CMP_ECX(0x456A15u, R_ESI, HL_NONE), CMP_ECX(0x456DCBu, R_ESI, HL_NONE),
};

/* The Lost Children: the Villager Details portrait 0x445540 (record in EDI), a villager's strip figure
   0x445950 (EDI; the island-event and puzzle dialogs), the village 0x445B50 (EAX), and the map 0x4478E0
   (ECX, or EDX + ESI -- the pool plus the record's offset). */
static const hl_site VV2_SITES[] = {
    CMP_ECX(0x445694u, R_EDI, HL_NONE), CMP_ECX(0x445A77u, R_EDI, HL_NONE), CMP_ECX(0x4469BAu, R_EAX, HL_NONE),
    CMP_EAX(0x4481D9u, R_ECX, HL_NONE), CMP_EAX(0x448210u, R_ECX, HL_NONE), CMP_EAX(0x4482DCu, R_ECX, HL_NONE),
    CMP_EAX(0x448390u, R_ECX, HL_NONE), CMP_EAX(0x448481u, R_ECX, HL_NONE), CMP_EAX(0x44851Cu, R_ECX, HL_NONE),
    CMP_EAX(0x44868Au, R_ECX, HL_NONE), CMP_EAX(0x44872Bu, R_EDX, R_ESI), CMP_EAX(0x44887Eu, R_EDX, R_ESI),
    CMP_EAX(0x448969u, R_ECX, HL_NONE), CMP_EAX(0x448A23u, R_ECX, HL_NONE), CMP_EAX(0x448AD1u, R_ECX, HL_NONE),
    CMP_EAX(0x448BF4u, R_EDX, R_ESI), CMP_EAX(0x448CFAu, R_ECX, HL_NONE), CMP_EAX(0x448DB4u, R_ECX, HL_NONE),
    CMP_EAX(0x448F1Cu, R_ECX, HL_NONE), CMP_EAX(0x448FC6u, R_EDX, R_ESI),
};

static const hl_site *g_sites;
static int g_site_count;

/* The age the compare at site `n` makes, for the registers in `frame`: [0..7] pushad (edi, esi, ebp, esp,
   ebx, edx, ecx, eax).  The villager's look decides it; anything that is not plainly a villager record of
   this game keeps the real age. */
static int hl_effective_age(const hl_site *s, const unsigned int *frame) {
    const hl_layout *l = &LAYOUT[g_game];
    unsigned int rec = frame[7 - s->rec_a] + (s->rec_b != HL_NONE ? frame[7 - s->rec_b] : 0u);
    int age = s->age_reg == HL_NONE ? *(const int *)(UINT_PTR)(rec + l->age) : (int)frame[7 - s->age_reg];
    int look;
    hl_locate();
    if (g_records == 0 || rec < g_records || (rec - g_records) % l->stride != 0
        || (rec - g_records) / l->stride >= (unsigned int)g_count
        || *(const int *)(UINT_PTR)(rec + l->age) != age) {
        return age;
    }
    look = hl_get((const unsigned char *)(UINT_PTR)rec);
    return look == 1 ? 0 : look == 2 ? 1100 : age;
}

/* `frame` as above, [8] the site's number, replaced with where the game goes on. */
static int __cdecl hl_site_age(unsigned int *frame) {
    const hl_site *s = &g_sites[frame[8]];
    frame[8] = s->va + s->length;
    return hl_effective_age(s, frame);
}

static __declspec(naked) void hl_site_common(void) {
    __asm {
        pushad
        push esp
        call hl_site_age
        add esp, 4
        cmp eax, 0x44C                      ; the game's own compare, of the effective age
        popad                               ; (popad and ret leave the flags alone)
        ret                                 ; to the instruction after the site
    }
}

#define HL_STUB(n) static __declspec(naked) void hl_stub_##n(void) { __asm push n __asm jmp hl_site_common }
HL_STUB(0) HL_STUB(1) HL_STUB(2) HL_STUB(3) HL_STUB(4) HL_STUB(5) HL_STUB(6) HL_STUB(7) HL_STUB(8) HL_STUB(9)
HL_STUB(10) HL_STUB(11) HL_STUB(12) HL_STUB(13) HL_STUB(14) HL_STUB(15) HL_STUB(16) HL_STUB(17) HL_STUB(18)
HL_STUB(19)

/* One per site of the game with the most (The Lost Children's 20). */
static void (*const HL_STUBS[])(void) = {
    hl_stub_0, hl_stub_1, hl_stub_2, hl_stub_3, hl_stub_4, hl_stub_5, hl_stub_6, hl_stub_7, hl_stub_8, hl_stub_9,
    hl_stub_10, hl_stub_11, hl_stub_12, hl_stub_13, hl_stub_14, hl_stub_15, hl_stub_16, hl_stub_17, hl_stub_18,
    hl_stub_19,
};

static void hl_install(const hl_site *sites, int count) {
    vvfp_site_write w[sizeof HL_STUBS / sizeof HL_STUBS[0]];
    int i;
    if (count > (int)(sizeof HL_STUBS / sizeof HL_STUBS[0])) {
        return;
    }
    for (i = 0; i < count; ++i) {
        vvfp_site_branch(&w[i], sites[i].va, sites[i].length, sites[i].stock, 0xE9, (const void *)HL_STUBS[i]);
    }
    g_sites = sites;
    g_site_count = count;
    g_installed = vvfp_install_sites(w, count);
}

/* ---- exports ------------------------------------------------------------------------------------- */

/* Called once at game start by "VVFP Startup.dll" (its second word), outside DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_game != 0 || game < 1 || game > 5) {
        return;
    }
    g_game = game;
    switch (game) {
    case 5:
        hl_install(VV5_SITES, (int)(sizeof VV5_SITES / sizeof VV5_SITES[0]));
        break;
    case 4:
        hl_install(VV4_SITES, (int)(sizeof VV4_SITES / sizeof VV4_SITES[0]));
        break;
    case 3:
        hl_install(VV3_SITES, (int)(sizeof VV3_SITES / sizeof VV3_SITES[0]));
        break;
    case 2:
        hl_install(VV2_SITES, (int)(sizeof VV2_SITES / sizeof VV2_SITES[0]));
        break;
    default:
        break;
    }
}

/* 1 when `game`'s head draws follow the look: this DLL's splices are in -- or, in A New Home, Grey Hair at
   55's (native/vv1_grey_hair), which draws the old heads there and asks VvfpHeadLookGet. */
int __stdcall VvfpHeadLookInstalled(int game) {
    if (g_game == 0 || game != g_game) {
        return 0;
    }
    if (game == 1) {
        HMODULE grey = GetModuleHandleA(VV1_GREY_HAIR_DLL);
        int (__stdcall *grey_installed)(void) = grey != NULL
            ? (int (__stdcall *)(void))GetProcAddress(grey, "VvfpGreyHairInstalled") : NULL;
        return grey_installed != NULL && grey_installed();
    }
    return g_installed;
}

int __stdcall VvfpHeadLookGet(int game, const void *record) {
    if (game != g_game || g_game == 0) {
        return 0;
    }
    return hl_get((const unsigned char *)record);
}

int __stdcall VvfpHeadLookSet(int game, const void *record, int look) {
    if (game != g_game || g_game == 0) {
        return 0;
    }
    return hl_set((const unsigned char *)record, look);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
