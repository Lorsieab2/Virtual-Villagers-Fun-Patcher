/* The Secret City's villager table, found where the executable itself says it is.

   The stock game keeps its population manager at 0x59E110 (records from +0x14,
   150 of 0x1F8C bytes).  256 Villagers (Experimental) moves the manager to
   0x800000 and gives it 256 slots.  Every companion that walks the villagers
   reads the two facts from the running executable's own instructions instead
   of a constant, so one DLL serves either build:

     * the manager: the 32-bit immediate of `mov ecx, MANAGER` at 0x4279B3, the
       call that loads the villager sprites (0x4279B8 call 0x45C730);
     * the slot count: the 32-bit immediate at 0x42883A, the save-state
       constructor's count, which the Origins companion and the robe wrapper
       already read.

   The 256 table is reported only when both say so -- the manager at 0x800000
   and 256 slots.  Anything else (the stock build, an executable that is not
   The Secret City such as a test harness's, or bytes that are not the
   expected instruction) answers with the stock table at RVA 0x19E110 and 150
   slots, which is what every companion used before the 256 build existed. */
#ifndef VV3_VILLAGER_TABLE_H
#define VV3_VILLAGER_TABLE_H

#include <windows.h>

#define VV3_MANAGER_IMM_RVA 0x279B4u
#define VV3_SLOTS_IMM_RVA   0x2883Au
#define VV3_STOCK_MANAGER_RVA 0x19E110u
#define VV3_256_MANAGER     0x800000u

static int vv3_table_bytes_readable(const unsigned char *at, SIZE_T size) {
    MEMORY_BASIC_INFORMATION info;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT) {
        return 0;
    }
    if (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) {
        return 0;
    }
    return (SIZE_T)((const unsigned char *)info.BaseAddress + info.RegionSize - at) >= size;
}

/* The manager's address relative to `module` (the RVA the companions'
   descriptors carry) and the slot count. */
static void vv3_villager_table(const unsigned char *module, unsigned int *manager_rva,
                               unsigned int *slots) {
    unsigned int base = (unsigned int)(UINT_PTR)module;
    *manager_rva = VV3_STOCK_MANAGER_RVA;
    *slots = 150u;
    if (module == NULL
        || !vv3_table_bytes_readable(module + VV3_MANAGER_IMM_RVA - 1u, 5u)
        || !vv3_table_bytes_readable(module + VV3_SLOTS_IMM_RVA, 4u)
        || module[VV3_MANAGER_IMM_RVA - 1u] != 0xB9u) {
        return;
    }
    if (*(const unsigned int *)(module + VV3_MANAGER_IMM_RVA) == VV3_256_MANAGER
        && *(const unsigned int *)(module + VV3_SLOTS_IMM_RVA) == 256u) {
        *manager_rva = VV3_256_MANAGER - base;
        *slots = 256u;
    }
}

#endif
