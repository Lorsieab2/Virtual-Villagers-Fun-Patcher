/* New Believers' word for a Heathen in the logs: "Heathen", or "Isolan" with the Guardians of Isola rewrite
   (the owner, 2026-11-22: every log records the Heathens, clearly marked as Heathens, in the Guardians of Isola
   wording when that patch is on).

   Guardians of Isola rewrites the game's own text (sm.xml), so the running game says which wording it has: its
   eSayStoppedBelieving (string 0x48 of the string table at 0x5240A8) says "left the tribe" only with the rewrite --
   the same test Popup When Believers Become Heathens (story_faith_notice.inc), More Island Events (adv_vv345.inc
   vv5_joins_key) and the Fog of Doom notice (vvfp_fog_listening.c fl_isola) make.  The table is read at the
   executable's own base (the stock 0x400000), every byte checked readable first (VirtualQuery, never a fault), so
   a process with no game image -- the native harnesses -- reads "Heathen" unless it maps a table there itself.

   The word is what a log's "Faction:" line says of a Heathen ("  Faction: Heathen" / "  Faction: Isolan"; a
   believer is "  Faction: Believer" either way), and every reader takes both (src/vv_log_additions.py
   is_heathen_faction, native/statistics_export/statistics_reconcile.inc).  Header-only and static. */
#ifndef VV_HEATHEN_WORD_H
#define VV_HEATHEN_WORD_H

#include <windows.h>

#define VV5_STRING_TABLE_RVA 0x1240A8u   /* 0x5240A8 in the stock image */
#define VV5_STOPPED_BELIEVING 0x48u
#define VV5_STOPPED_TEXT_SCAN 256

/* Every byte of [p, p + n) committed and readable. */
static int vv_heathen_word_readable(const void *p, SIZE_T n) {
    const unsigned char *at = (const unsigned char *)p;
    const unsigned char *end = at + n;
    if (p == NULL || end < at) {
        return 0;
    }
    while (at < end) {
        MEMORY_BASIC_INFORMATION info;
        const unsigned char *region_end;
        if (VirtualQuery(at, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
            || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0
            || (info.Protect & (PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READ
                                | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)) == 0) {
            return 0;
        }
        region_end = (const unsigned char *)info.BaseAddress + info.RegionSize;
        if (region_end <= at) {
            return 0;
        }
        at = region_end;
    }
    return 1;
}

/* 1 when the running New Believers has Guardians of Isola's words ("left the tribe" in string 0x48). */
static int vv5_guardians_of_isola(void) {
    static const char WORDS[] = "left the tribe";
    const unsigned char *base = (const unsigned char *)GetModuleHandleA(NULL);
    const unsigned int *const *slot;
    const unsigned int *entry;
    const char *text;
    int i, k, n;
    if (base == NULL) {
        return 0;
    }
    slot = (const unsigned int *const *)(base + VV5_STRING_TABLE_RVA + 4u * VV5_STOPPED_BELIEVING);
    if (!vv_heathen_word_readable(slot, sizeof *slot)) {
        return 0;
    }
    entry = *slot;
    if (!vv_heathen_word_readable(entry, 4u * sizeof *entry) || entry[0] != VV5_STOPPED_BELIEVING) {
        return 0;
    }
    text = (const char *)(UINT_PTR)(entry[3] != 0 ? entry[3] : entry[2]);
    {
        /* The bytes readable from `text` on, at most the scan and the words: one region looked up, not each byte. */
        MEMORY_BASIC_INFORMATION info;
        SIZE_T room;
        if (!vv_heathen_word_readable(text, 1) || VirtualQuery(text, &info, sizeof info) != sizeof info) {
            return 0;
        }
        room = (SIZE_T)((const char *)info.BaseAddress + info.RegionSize - text);
        if (room > VV5_STOPPED_TEXT_SCAN + sizeof WORDS) {
            room = VV5_STOPPED_TEXT_SCAN + sizeof WORDS;
        }
        n = (int)room;
    }
    for (i = 0; i < VV5_STOPPED_TEXT_SCAN && i < n; ++i) {
        if (text[i] == '\0') {
            return 0;
        }
        for (k = 0; WORDS[k] != '\0'; ++k) {
            char c;
            if (i + k >= n) {
                return 0;
            }
            c = text[i + k];
            if (c >= 'A' && c <= 'Z') {
                c = (char)(c - 'A' + 'a');
            }
            if (c != WORDS[k]) {
                break;
            }
        }
        if (WORDS[k] == '\0') {
            return 1;
        }
    }
    return 0;
}

/* "Heathen", or "Isolan" with Guardians of Isola. */
static const char *vv5_heathen_word(void) {
    return vv5_guardians_of_isola() ? "Isolan" : "Heathen";
}

#endif /* VV_HEATHEN_WORD_H */
