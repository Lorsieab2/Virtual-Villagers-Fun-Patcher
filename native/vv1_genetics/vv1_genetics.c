/* VVFP VV1 Genetics -- "Genetics" for A New Home (the owner, 2026-10-25): a newborn's head comes from its
   parents, by The Lost Children to New Believers' own rule.

   THE STOCK GAME.  A New Home's villager creator 0x43C350 rolls a newborn's head at random by sex --
   rand(19) for a boy (0..18), rand(20) for a girl (0..19), stored at 0x43C647 (mov [esi+0x360], eax) --
   and never reads a parent's looks.  (Head 19 is the last row of the men's pictures: only the Golden
   Child, family 199, gets it, from the creator's own family-199 branch 0x43C7AF.)  The later four games
   (VV2 0x44CBA8, VV3 0x4564A7, VV4 0x45F235, VV5 0x46853A) instead give
       rand(100) < 5 ? any head : (father's head + mother's head) / 2 + rand(3) - 1, clamped.

   WHAT THIS DOES.  At 0x43C647, for the first child of a birth only -- the creator called by the
   pregnancy tick at 0x42EFD0, so returning to 0x42EFD5 (with the patcher's slot guards too: their guard
   enters the creator with that same return address) -- the head stored is:
       rand(100) < 5:  the head the game has just rolled (any head of the baby's sex, as before);
       otherwise:      base + rand(3) - 1, made 0 below 0 and the sex's top above it (a boy 18, a girl 19),
   where base is (father's head + mother's head) / 2, rounded down, when the father is known, and the
   mother's head alone when he is not (the owner's rule for an "Unknown" father).  A New Home keeps no
   father on the mother's record: he is the one "VVFP VV1 Parentage.dll" (Show Parents) stashed against her
   at the conception (Vv1ParentageQueryExpectedFather); without it, or with no father stashed, or with a
   head outside 0..19, the mother's head alone.  rand is the game's own 0x402F10.  A boy is never given
   19: it stays the Golden Child's.  Twins and triplets: the pregnancy tick makes them with 0x43C840
   (0x42F021, 0x42F06D), which copies the first child's head, so they share it as in the later games.
   Bodies stay random, as in every game.  Every other caller of the creator (a new village, island
   events, the Golden Child's birth 0x42EF5F) is the game's own.

   INSTALLING.  VvfpStartup(1, shipped), from "VVFP Startup.dll"'s second word of companions
   (native/shared/startup_companions_2.h).  The head and body rolls 0x43C616..0x43C64C must hold the stock
   bytes -- apart from the three rand calls' targets (Story / Cheat Upgrades may point them at its own
   answer) and the name roll's bound at 0x43C646 (Fix Vanilla Bugs' 0x64 -> 0x65) -- and so must the
   game's rand; then the one detour goes in through the shared all-or-none writer
   (native/shared/install_sites.h), or nothing is written.  Off (the row unticked): the DLL is not shipped
   and the game is stock. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

#define VV1_GAME 1
#define RAND_VA 0x402F10u
#define ROLLS 0x43C616u                 /* the sex test, then body and head rolls */
#define SITE 0x43C647u                  /* mov [esi+0x360], eax */
#define SITE_LEN 6
#define RESUME 0x43C64Du
#define BIRTH_RETURN 0x42EFD5u          /* after the pregnancy tick's call 0x42EFD0 */
#define RECORD_STRIDE 0x3D8u
#define RECORD_COUNT 256u
#define REC_SEX 0x350u
#define REC_HEAD 0x360u
#define HEAD_TOP 19
#define BOY_TOP 18

static const char PARENTAGE_DLL[] = "VVFP VV1 Parentage.dll";

/* 0x43C616..0x43C64C, stock. */
static const unsigned char ROLLS_STOCK[] = {
    0x83, 0xBE, 0x50, 0x03, 0x00, 0x00, 0x01, 0x75, 0x0B, 0x6A, 0x13, 0xE8, 0xEA, 0x68, 0xFC, 0xFF,
    0x6A, 0x13, 0xEB, 0x09, 0x6A, 0x14, 0xE8, 0xDF, 0x68, 0xFC, 0xFF, 0x6A, 0x14, 0x89, 0x86, 0x64,
    0x03, 0x00, 0x00, 0xE8, 0xD2, 0x68, 0xFC, 0xFF, 0x8B, 0x7C, 0x24, 0x4C, 0x83, 0xC4, 0x08, 0x6A,
    0x64, 0x89, 0x86, 0x60, 0x03, 0x00, 0x00,
};
/* The rand calls inside it (their rel32 may be another companion's), and the name bound. */
static const unsigned int RAND_CALLS[] = { 0x43C621u, 0x43C62Cu, 0x43C639u };
#define NAME_BOUND 0x43C646u

/* The game's rand(bound), 0x402F10: its first bytes. */
static const unsigned char RAND_STOCK[] = {
    0x56, 0x8B, 0x74, 0x24, 0x08, 0x85, 0xF6, 0x7E, 0x14, 0x81, 0xFE, 0xFF, 0x7F, 0x00, 0x00, 0x7F, 0x0C,
};

typedef int (__cdecl *rand_fn)(int bound);
typedef int (__stdcall *expected_father_fn)(int index, int *out, char *name, int capacity);

static int installed;

static int game_rand(int bound) {
    return ((rand_fn)(UINT_PTR)RAND_VA)(bound);
}

/* The father's head Show Parents knows for the baby the mother in record `index` carries; -1 when
   it is not there or does not know him. */
static int father_head(int index) {
    HMODULE parentage = GetModuleHandleA(PARENTAGE_DLL);
    expected_father_fn query;
    int out[2] = { -1, -1 };
    char name[32];
    if (parentage == NULL) {
        return -1;
    }
    query = (expected_father_fn)GetProcAddress(parentage, "Vv1ParentageQueryExpectedFather");
    if (query == NULL) {
        return -1;
    }
    __try {
        if (!query(index, out, name, (int)sizeof name)) {
            return -1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return -1;
    }
    return out[0] >= 0 && out[0] <= HEAD_TOP ? out[0] : -1;
}

/* The head the baby gets.  `frame` is the stub's pushad frame: [1] ESI the child's record, [3] the ESP
   at the site (the creator's: [+4] the caller's EDI, the mother's byte offset in the records, and
   [+0x44] the creator's return address), [4] EBX the records, [7] EAX the head the game rolled. */
static int __cdecl genetics_head(const unsigned int *frame) {
    const unsigned char *child = (const unsigned char *)(UINT_PTR)frame[1];
    const unsigned int *site_esp = (const unsigned int *)(UINT_PTR)frame[3];
    const unsigned char *records = (const unsigned char *)(UINT_PTR)frame[4];
    int rolled = (int)frame[7];
    unsigned int mother_offset;
    int top, mother, father, base, head;
    if (site_esp[0x44 / 4] != BIRTH_RETURN || records == NULL || child == NULL) {
        return rolled;
    }
    mother_offset = site_esp[1];
    if (mother_offset % RECORD_STRIDE != 0 || mother_offset >= RECORD_STRIDE * RECORD_COUNT) {
        return rolled;
    }
    mother = *(const int *)(records + mother_offset + REC_HEAD);
    if (mother < 0 || mother > HEAD_TOP) {
        return rolled;
    }
    top = *(const int *)(child + REC_SEX) == 1 ? BOY_TOP : HEAD_TOP;
    father = father_head((int)(mother_offset / RECORD_STRIDE));
    base = father >= 0 ? (father + mother) / 2 : mother;
    if (game_rand(100) < 5) {
        return rolled;
    }
    head = base + game_rand(3) - 1;
    if (head < 0) {
        head = 0;
    }
    if (head > top) {
        head = top;
    }
    return head;
}

/* At 0x43C647: store the head genetics_head gives, then go on at 0x43C64D. */
static __declspec(naked) void head_stub(void) {
    __asm {
        pushad
        push esp
        call genetics_head
        add esp, 4
        mov dword ptr [esp + 28], eax
        popad
        mov dword ptr [esi + 0x360], eax
        push RESUME
        ret
    }
}

/* ---- installing ------------------------------------------------------------------------------- */

static int readable(unsigned int va, size_t length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(UINT_PTR)va;
    if (VirtualQuery(at, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
        return 0;
    }
    return (UINT_PTR)at + length <= (UINT_PTR)info.BaseAddress + info.RegionSize;
}

/* The rolls hold the stock bytes but for the rand calls' targets and the name roll's bound. */
static int rolls_hold(void) {
    const unsigned char *at = (const unsigned char *)(UINT_PTR)ROLLS;
    size_t i, k;
    if (!readable(ROLLS, sizeof ROLLS_STOCK)) {
        return 0;
    }
    for (i = 0; i < sizeof ROLLS_STOCK; ++i) {
        unsigned int va = ROLLS + (unsigned int)i;
        int free_byte = 0;
        for (k = 0; k < sizeof RAND_CALLS / sizeof RAND_CALLS[0]; ++k) {
            if (va > RAND_CALLS[k] && va < RAND_CALLS[k] + 5u) {
                free_byte = 1;
            }
        }
        if (va == NAME_BOUND) {
            free_byte = at[i] == 0x64 || at[i] == 0x65;
            if (!free_byte) {
                return 0;
            }
        }
        if (!free_byte && at[i] != ROLLS_STOCK[i]) {
            return 0;
        }
    }
    return 1;
}

static void install_vv1(void) {
    vvfp_site_write w;
    if (!rolls_hold() || !readable(RAND_VA, sizeof RAND_STOCK)
        || memcmp((const void *)(UINT_PTR)RAND_VA, RAND_STOCK, sizeof RAND_STOCK) != 0) {
        return;
    }
    vvfp_site_branch(&w, SITE, SITE_LEN, ROLLS_STOCK + (SITE - ROLLS), 0xE9, (const void *)head_stub);
    if (vvfp_install_sites(&w, 1)) {
        installed = 1;
    }
}

/* Called once at game start by "VVFP Startup.dll" (its second word), outside DllMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (installed || game != VV1_GAME) {
        return;
    }
    install_vv1();
}

/* Whether the detour is in (tests). */
int __stdcall VvfpGeneticsInstalled(void) {
    return installed;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
