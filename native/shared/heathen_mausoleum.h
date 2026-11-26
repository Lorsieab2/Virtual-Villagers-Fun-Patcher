/* heathen_mausoleum.h -- the stable interface of "VVFP Heathen Mausoleum.dll" (New Believers, v1.35.101; workstream
   W-C of docs/heathen-tribe-expansion-design.md, section 6, with the owner's decisions 11-14).

   WHAT THE COMPANION KEEPS.  A second Roster of the Dead, the Heathens' own, at the mud hut: an object laid out
   exactly as the game's Roster of the Dead 0x5481A8 (500 entries of HE_ROSTER_ENTRY = 0x5C bytes, then a 500-dword
   burier-id array at +0xB3B0 that is never saved, and a count at +0xBB80; 0xBB84 bytes), filled by the game's own
   roster writer 0x464C70 at a Heathen's burial, shown by the game's own Mausoleum screen.  Like the stock roster
   its entries are packed from entry 0: the first entry whose age (+0x1C) is 0 ends it.

   THE FILE (heathen_evo.h section 5): Documents\LDW\<exe>\Virtual Villagers Fun Patcher\Save <S>\Data\
   Heathen Mausoleum\Heathen Mausoleum - Save <S>.dat:
       header  'VHM1' (HE_MAUSOLEUM_MAGIC), version 1, game 5, count, slot   (five little-endian u32s, 20 bytes;
               the slot at +16, as every per-save .dat: Copy / Move Player Slot retags it)
       count entries of 0x5C bytes in the stock layout (name +0 char[0x19], age +0x1C, head +0x20, body +0x24,
               profession +0x28, skill value +0x2C, flags +0x31..+0x33, cause +0x34, epitaph +0x38 char[0x20]),
               packed with no holes, count <= 500.
   Each entry is checked by the game's own load rules (0x464EF0: the name printable and ended within 0x19 bytes,
   age > 0, profession -1..5, cause -1..4); one bad entry rejects the whole file, which is then set aside, never
   overwritten (sidecar_io.h).  The file is written only when the game saves that slot (so it always matches the
   save), and read when the game loads the slot.

   THE EXPORTS (all __stdcall; GetModuleHandleA("VVFP Heathen Mausoleum.dll") + GetProcAddress -- never
   LoadLibrary; a missing DLL or export means "no Heathen graves at the mud hut").  The entry pointers point into
   the live table, which the game's own writer and the epitaph editor change in place; an entry is valid until the
   next burial, removal, load or new village.

     int VvfpHeathenMausoleumInstalled(void)
         1 when every site is installed (Heathen graves go to the mud hut), else 0.
     int VvfpHeathenMausoleumCount(void)
         the number of Heathen graves (entries before the first empty one), 0..500.
     const unsigned char *VvfpHeathenMausoleumEntry(int place)
         grave `place` (0 .. Count-1): its 0x5C-byte entry in the stock layout, or NULL.
     int VvfpHeathenMausoleumRemove(int place)
         grave `place` taken away as the Revive upgrade takes a believer's grave from the stock roster: the later
         graves move down one place (their burier ids with them), the last is zeroed, the count goes down.  1 done,
         0 not (no such grave).  The change reaches the file at the next save, like every other change.
     const unsigned char *VvfpHeathenMausoleumTable(void)
         the table's first entry (the object's base), or NULL when not installed.
     int VvfpHeathenMausoleumIsHeathenGrave(int entry)
         `entry` is the ADDRESS of a 0x5C-byte roster entry (as an int): 1 when it lies in the Heathens' table
         (a mud-hut grave), else 0.  The Cause of Death companion asks it for the grave the writer just wrote and
         for the grave whose epitaph was just edited.
     void VvfpHeathenMausoleumVillageReset(int game, int slot)
         "VVFP Save Reset.dll", at Start Over or a deleted tribe in `slot`, before it deletes the slot's folder:
         the Heathen graves kept for that village are forgotten (memory and the file gate), so none of it is
         written back into the next village.  Another slot's village is left alone. */
#ifndef VV_HEATHEN_MAUSOLEUM_H
#define VV_HEATHEN_MAUSOLEUM_H

#include <windows.h>

/* (The same names as heathen_evo.h, so a reader -- the Cause of Death, the statistics -- need not take that whole
   header.) */
#ifndef HE_MAUSOLEUM_DLL
#define HE_MAUSOLEUM_DLL "VVFP Heathen Mausoleum.dll"
#define HE_MAUSOLEUM_GRAVE_EXPORT "VvfpHeathenMausoleumIsHeathenGrave"
#define HE_MAUSOLEUM_RESET_EXPORT "VvfpHeathenMausoleumVillageReset"
typedef int (__stdcall *he_is_heathen_grave_fn)(int entry);
typedef void (__stdcall *he_village_reset_fn)(int game, int slot);
#endif

#define HM_TABLE_BYTES 0xBB84u
#define HM_BURIERS 0xB3B0u
#define HM_COUNT 0xBB80u

#define HM_INSTALLED_EXPORT "VvfpHeathenMausoleumInstalled"
#define HM_COUNT_EXPORT "VvfpHeathenMausoleumCount"
#define HM_ENTRY_EXPORT "VvfpHeathenMausoleumEntry"
#define HM_REMOVE_EXPORT "VvfpHeathenMausoleumRemove"
#define HM_TABLE_EXPORT "VvfpHeathenMausoleumTable"

typedef int (__stdcall *hm_installed_fn)(void);
typedef int (__stdcall *hm_count_fn)(void);
typedef const unsigned char *(__stdcall *hm_entry_fn)(int place);
typedef int (__stdcall *hm_remove_fn)(int place);
typedef const unsigned char *(__stdcall *hm_table_fn)(void);

/* The Death record's "Grave:" words for a grave at the mud hut ("the Shrine to the Ancestors (Master Builder)")
   and for a full table -- in-game the Heathen Mausoleum is the Shrine to the Ancestors (the owner, 2026-11-26),
   with or without the Guardians of Isola rewrite.  Readers (the Village Statistics' Villagers Buried,
   src/vv_log_additions.py) know such a grave by HM_GRAVE_PREFIX. */
#define HM_GRAVE_PREFIX "the Shrine to the Ancestors"
#define HM_GRAVE_FULL "no grave (the Shrine to the Ancestors was full)"

/* 1 when the Roster of the Dead entry at `entry` is a Heathen's grave at the mud hut (the companion asked when it
   is loaded, else 0). */
static __inline int hm_is_heathen_grave(const void *entry) {
    HMODULE module = GetModuleHandleA(HE_MAUSOLEUM_DLL);
    he_is_heathen_grave_fn is_grave = module != NULL
        ? (he_is_heathen_grave_fn)(void *)GetProcAddress(module, HE_MAUSOLEUM_GRAVE_EXPORT) : NULL;
    return is_grave != NULL && is_grave((int)(UINT_PTR)entry) != 0;
}

/* 1 when the companion is loaded and installed (a Heathen's burial goes to the mud hut). */
static __inline int hm_installed(void) {
    HMODULE module = GetModuleHandleA(HE_MAUSOLEUM_DLL);
    hm_installed_fn installed = module != NULL
        ? (hm_installed_fn)(void *)GetProcAddress(module, HM_INSTALLED_EXPORT) : NULL;
    return installed != NULL && installed() != 0;
}

/* The Heathens' table and its number of graves (NULL and 0 when the companion is not loaded or not installed). */
static __inline const unsigned char *hm_graves(int *count) {
    HMODULE module = GetModuleHandleA(HE_MAUSOLEUM_DLL);
    hm_table_fn table = module != NULL ? (hm_table_fn)(void *)GetProcAddress(module, HM_TABLE_EXPORT) : NULL;
    hm_count_fn counted = module != NULL ? (hm_count_fn)(void *)GetProcAddress(module, HM_COUNT_EXPORT) : NULL;
    const unsigned char *at = table != NULL && counted != NULL ? table() : NULL;
    *count = at != NULL ? counted() : 0;
    return at;
}

#endif /* VV_HEATHEN_MAUSOLEUM_H */
