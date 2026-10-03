/* The Tree of Life's villager table, found where the executable itself says it is.

   The stock game keeps its population manager at 0x50E568 (records from +0x44,
   150 of 0x2E3C bytes).  256 Villagers (Experimental) moves the manager to
   0x800000 and gives it 256 slots.  Every companion that walks the villagers
   reads the two facts from the running executable's own instructions instead
   of a constant, so one DLL serves either build:

     * the manager: the 32-bit immediate of `mov ecx, MANAGER` at 0x488D70, the
       manager's static initialiser (followed by `jmp 0x467CE0`, its
       constructor);
     * the slot count: the 32-bit immediate at 0x42001C (`cmp esi, SLOTS` in
       0x41FEF0), which the Origins companion already reads.

   The 256 table is reported only when both say so -- the manager at 0x800000
   and 256 slots.  Anything else (the stock build, an executable that is not
   The Tree of Life such as a test harness's, or bytes that are not the
   expected instructions) answers with the stock table at RVA 0x10E568 and 150
   slots, which is what every companion used before the 256 build existed. */
#ifndef VV4_VILLAGER_TABLE_H
#define VV4_VILLAGER_TABLE_H

#include <windows.h>

#define VV4_MANAGER_IMM_RVA 0x88D71u
#define VV4_SLOTS_IMM_RVA   0x2001Cu
#define VV4_STOCK_MANAGER_RVA 0x10E568u
#define VV4_256_MANAGER     0x800000u

static int vv4_table_bytes_readable(const unsigned char *at, SIZE_T size) {
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
static void vv4_villager_table(const unsigned char *module, unsigned int *manager_rva,
                               unsigned int *slots) {
    unsigned int base = (unsigned int)(UINT_PTR)module;
    *manager_rva = VV4_STOCK_MANAGER_RVA;
    *slots = 150u;
    if (module == NULL
        || !vv4_table_bytes_readable(module + VV4_MANAGER_IMM_RVA - 1u, 6u)
        || !vv4_table_bytes_readable(module + VV4_SLOTS_IMM_RVA, 4u)
        || module[VV4_MANAGER_IMM_RVA - 1u] != 0xB9u
        || module[VV4_MANAGER_IMM_RVA + 4u] != 0xE9u) {
        return;
    }
    if (*(const unsigned int *)(module + VV4_MANAGER_IMM_RVA) == VV4_256_MANAGER
        && *(const unsigned int *)(module + VV4_SLOTS_IMM_RVA) == 256u) {
        *manager_rva = VV4_256_MANAGER - base;
        *slots = 256u;
    }
}

#endif
