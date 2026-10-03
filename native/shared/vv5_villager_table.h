/* New Believers' villager table, found where the executable itself says it is.

   The stock game keeps its villager manager at 0x554148 (records from +0x48,
   150 of 0x2F44 bytes; believers, Heathens and Reanimate stand-ins share
   them).  256 Villagers (Experimental) moves the manager to 0x800000 and
   gives it 256 slots.  Every companion that walks the villagers reads the two
   facts from the running executable's own instructions instead of a
   constant, so one DLL serves either build:

     * the manager: the 32-bit immediate of `mov ecx, MANAGER` at 0x494050,
       the manager's static initialiser (followed by `jmp 0x471DF0`, its
       constructor);
     * the slot count: the 32-bit immediate at 0x41F1E6 (`cmp edi, SLOTS` in
       0x41F170), which the Origins companion and the Cure All sweep already
       read.

   The 256 table is reported only when both say so -- the manager at 0x800000
   and 256 slots.  Anything else (the stock build, an executable that is not
   New Believers such as a test harness's, or bytes that are not the expected
   instructions) answers with the stock table at RVA 0x154148 and 150 slots,
   which is what every companion used before the 256 build existed.

   The 256 build also moves the Origins companion's mask table (a nibble per
   villager) out of the stock .data slack at 0x7B1D20, where 150 villagers'
   75 bytes fit and 256 villagers' 128 do not, to 0x7F1400 in its own
   section. */
#ifndef VV5_VILLAGER_TABLE_H
#define VV5_VILLAGER_TABLE_H

#include <windows.h>

#define VV5_MANAGER_IMM_RVA 0x94051u
#define VV5_SLOTS_IMM_RVA   0x1F1E6u
#define VV5_STOCK_MANAGER_RVA 0x154148u
#define VV5_256_MANAGER     0x800000u
#define VV5_STOCK_MASK_TABLE 0x7B1D20u
#define VV5_256_MASK_TABLE   0x7F1400u

static int vv5_table_bytes_readable(const unsigned char *at, SIZE_T size) {
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
static void vv5_villager_table(const unsigned char *module, unsigned int *manager_rva,
                               unsigned int *slots) {
    unsigned int base = (unsigned int)(UINT_PTR)module;
    *manager_rva = VV5_STOCK_MANAGER_RVA;
    *slots = 150u;
    if (module == NULL
        || !vv5_table_bytes_readable(module + VV5_MANAGER_IMM_RVA - 1u, 6u)
        || !vv5_table_bytes_readable(module + VV5_SLOTS_IMM_RVA, 4u)
        || module[VV5_MANAGER_IMM_RVA - 1u] != 0xB9u
        || module[VV5_MANAGER_IMM_RVA + 4u] != 0xE9u) {
        return;
    }
    if (*(const unsigned int *)(module + VV5_MANAGER_IMM_RVA) == VV5_256_MANAGER
        && *(const unsigned int *)(module + VV5_SLOTS_IMM_RVA) == 256u) {
        *manager_rva = VV5_256_MANAGER - base;
        *slots = 256u;
    }
}

#endif
