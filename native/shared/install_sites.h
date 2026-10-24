/* install_sites.h -- every companion's runtime writes into the game's code:
   all of a feature's sites, or none of them.

   The owner (2026-10-24): "I do not want any half-assed patches."  A feature
   whose sites are written one at a time can end up half-installed: a
   VirtualProtect that fails at the third site, after the first two were
   written, left two detours live and the rest stock -- and an install that
   then reported success (VV1 Number Keys, #607), or reported failure but
   left the first two in place (Island Events, Cause of Death, Chief
   Hospital, Both Factions, VV2 Totems, ...), or "undid" them with more
   writes that can fail the same way.

   vvfp_install_sites() is the one way a companion writes the game's code:

     1. every site is checked first: committed, readable, and holding exactly
        the bytes the companion expects (the stock bytes, or the row's own);
     2. every site is made writable -- and if any VirtualProtect fails, the
        ones already unlocked get their old protection back and NOTHING has
        been written;
     3. only then is every site written (in-process memcpy: it cannot fail
        once the page is writable);
     4. every protection is restored, last first (two sites on one page: the
        second's "old" protection is the first's PAGE_EXECUTE_READWRITE, so
        the first site's restore must come last), and the instruction cache
        flushed for each.

   It returns 1 only when every site was written, 0 when nothing was.  The
   caller sets its "installed" state from that answer and nothing else.

   A companion's own code pages (stubs, trampolines) are built in
   PAGE_READWRITE memory and made PAGE_EXECUTE_READ before any site points at
   them (vvfp_code_page_seal): never writable and executable at once. */
#ifndef VVFP_INSTALL_SITES_H
#define VVFP_INSTALL_SITES_H

#include <windows.h>
#include <string.h>

#define VVFP_SITE_MAX_BYTES 256     /* the longest: a New Believers price block, 180 */

/* A TEST build may make an unlock fail without a real VirtualProtect
   failure (defined before this header is included); never in a shipped
   build. */
#ifndef VVFP_INSTALL_SITES_TEST_FAIL
#define VVFP_INSTALL_SITES_TEST_FAIL() 0
#endif

typedef struct vvfp_site_write {
    unsigned int va;                              /* where, in the game */
    int length;                                   /* 1..VVFP_SITE_MAX_BYTES */
    const unsigned char *expect;                  /* what must be there now */
    unsigned char bytes[VVFP_SITE_MAX_BYTES];     /* what goes there */
    DWORD old;                                    /* (vvfp_install_sites' own) */
} vvfp_site_write;

/* Committed, readable memory at `va` holding exactly `bytes`. */
static int vvfp_site_holds(unsigned int va, const unsigned char *bytes, int length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(UINT_PTR)va;
    if (va == 0 || length <= 0 || bytes == NULL
        || VirtualQuery(at, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0
        || (UINT_PTR)at + (unsigned int)length > (UINT_PTR)info.BaseAddress + info.RegionSize) {
        return 0;
    }
    return memcmp(at, bytes, (size_t)length) == 0;
}

/* A `jmp` (0xE9) or `call` (0xE8) from the site to `to`, nops to `length`. */
static void vvfp_site_branch(vvfp_site_write *w, unsigned int va, int length,
                             const unsigned char *expect, unsigned char opcode, const void *to) {
    unsigned int rel = (unsigned int)((UINT_PTR)to - ((UINT_PTR)va + 5u));
    int i;
    w->va = va;
    w->length = length;
    w->expect = expect;
    w->bytes[0] = opcode;
    memcpy(w->bytes + 1, &rel, 4);
    for (i = 5; i < length && i < VVFP_SITE_MAX_BYTES; ++i) {
        w->bytes[i] = 0x90;
    }
}

/* The site gets `bytes` exactly. */
static void vvfp_site_bytes(vvfp_site_write *w, unsigned int va, int length,
                            const unsigned char *expect, const unsigned char *bytes) {
    w->va = va;
    w->length = length;
    w->expect = expect;
    if (length > 0 && length <= VVFP_SITE_MAX_BYTES) {
        memcpy(w->bytes, bytes, (size_t)length);
    }
}

/* All of `count` sites, or none (see the top of this file). */
static int vvfp_install_sites(vvfp_site_write *w, int count) {
    int i, unlocked;
    if (count <= 0) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (w[i].length <= 0 || w[i].length > VVFP_SITE_MAX_BYTES
            || !vvfp_site_holds(w[i].va, w[i].expect, w[i].length)) {
            return 0;
        }
    }
    for (unlocked = 0; unlocked < count; ++unlocked) {
        if (VVFP_INSTALL_SITES_TEST_FAIL()
            || !VirtualProtect((void *)(UINT_PTR)w[unlocked].va, (SIZE_T)w[unlocked].length,
                               PAGE_EXECUTE_READWRITE, &w[unlocked].old)) {
            while (unlocked-- > 0) {
                DWORD ignored;
                VirtualProtect((void *)(UINT_PTR)w[unlocked].va, (SIZE_T)w[unlocked].length,
                               w[unlocked].old, &ignored);
            }
            return 0;
        }
    }
    for (i = 0; i < count; ++i) {
        memcpy((void *)(UINT_PTR)w[i].va, w[i].bytes, (size_t)w[i].length);
    }
    for (i = count; i-- > 0;) {
        DWORD ignored;
        VirtualProtect((void *)(UINT_PTR)w[i].va, (SIZE_T)w[i].length, w[i].old, &ignored);
    }
    for (i = 0; i < count; ++i) {
        FlushInstructionCache(GetCurrentProcess(), (const void *)(UINT_PTR)w[i].va, (SIZE_T)w[i].length);
    }
    return 1;
}

/* A companion's own code page: allocated read/write, filled by the caller,
   then sealed read/execute.  NULL on failure (nothing allocated stays). */
static unsigned char *vvfp_code_page_alloc(SIZE_T size) {
    return (unsigned char *)VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
}

static int vvfp_code_page_seal(unsigned char *page, SIZE_T size) {
    DWORD old;
    if (page == NULL || !VirtualProtect(page, size, PAGE_EXECUTE_READ, &old)) {
        if (page != NULL) {
            VirtualFree(page, 0, MEM_RELEASE);
        }
        return 0;
    }
    FlushInstructionCache(GetCurrentProcess(), page, size);
    return 1;
}

#endif /* VVFP_INSTALL_SITES_H */
