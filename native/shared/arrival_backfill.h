/* "Arrived" records: every villager who joins a village without being born
   into it, in the Births and Conceptions log, in all five games -- and the
   one-time backfill for the villagers who arrived before that record existed.

   The owner (2026-10-04): grown villagers who join (island events, the Custom
   Island Event, the Barrel O' Babies, ...) get an "Arrived" record in the
   Births and Conceptions log; the ones already in a village get one
   backfilled, but only after the first-load prompt's Repair.

   "VVFP Cause of Death.dll" sees the arrivals (the game's own villager
   creators, cod_arrivals.inc) and the village's villagers; "VVFP Parentage
   Export.dll" files the records and knows the log (RecordArrivalsMissingFromLog,
   native/parentage_export/arrival_backfill.inc).

   THE RECORD (one format, all five games):

       Arrived <n>
         Name: <name>
         Age at arrival: <age units>          (backfill: "(unknown)")
         Age when recorded: <age units>        (backfill only)
         Sex: <Male | Female>
         Head: <n>
         Body: <n>
         Likes: <word | (none)>
         Dislikes: <word | (none)>
         Skills:
           <skill>    <n>                      (the game's own skills)
         Parents:                              (only when the record keeps any)
           Father: <name | (none)>
           Mother: <name | (none)>
         How: <Custom Island Event | Converted from the Heathens | unknown>
         Note: Recorded afterwards (arrived before this log existed)   (backfill only)
       <blank line>

   <n> is a running count of Arrived records across the game's Births and
   Conceptions files.  Arrived records do not count toward a file's roll (only
   Conception records do) and go into the village's newest file, as Birth
   records do.

   WHICH VILLAGERS THE LOG ALREADY HAS.  A villager is in the log when one of
   the village's Birth records ("  Child:" with its "    Head:" and
   "    Body:") or Arrived records ("  Name:", "  Head:", "  Body:") has the
   same name, head and body -- on disk, or still held for the next save.  It
   is a count, not a lookup: two villagers with the same three need two
   records.  So a record already there -- hand-appended, or written by an
   earlier run -- is never written again.

   THE MARKER.  "<save folder>\Virtual Villagers Fun Patcher Data\Arrivals\
   Virtual Villagers N Arrivals Recorded - Save S.dat": 16 bytes, 'VCA1',
   version 1, game, slot.  It says the slot needs no backfill: written once
   the backfill has put every missing record on disk, and when a village's
   Births and Conceptions log is first created (a new village, or after Start
   Over: its founders are not arrivals and nothing predates the log).  Start
   Over deletes it with the village (native/shared/save_reset.c). */
#ifndef VV_ARRIVAL_BACKFILL_H
#define VV_ARRIVAL_BACKFILL_H

#include <windows.h>
#include <stdio.h>
#include "save_folder.h"

#define VV_ARRIVAL_BEFORE 160
#define VV_ARRIVAL_MARKER_MAGIC 0x31414356u     /* 'VCA1' */

/* What became of a villager (vv_arrival_fact.outcome). */
enum {
    VV_ARRIVAL_UNDECIDED = 0,   /* nothing decided */
    VV_ARRIVAL_IN_LOG = 1,      /* a Birth or Arrived record on disk is theirs */
    VV_ARRIVAL_RECORDED = 2,    /* their Arrived record is on disk now */
    VV_ARRIVAL_MISSING = 3,     /* no record: one would be written (apply 0) */
    VV_ARRIVAL_HELD = 4,        /* matched by a record still held for the save */
    VV_ARRIVAL_QUEUED = 5       /* their record was made now, and is held for the save */
};

typedef struct {
    const void *record;             /* in: the villager's live record */
    char before[VV_ARRIVAL_BEFORE]; /* in: the lines after "Name:" (age, sex) */
    int outcome;                    /* out: VV_ARRIVAL_* */
} vv_arrival_fact;

/* RecordArrivalsMissingFromLog(game, save_buffer, slot, facts, count, apply):
   the village is named as RecordGravesMissingFromLog names it (the save just
   made, or with no buffer the slot's own save file).  A village with no
   Births and Conceptions file yet has nothing to backfill: 0.  With `apply`
   0 nothing is written and the count of villagers with no record is
   returned; with 1 each gets an Arrived record (the backfill's own "How" and
   "Note" lines) and the count written is returned.  -1 when nothing could be
   decided. */
typedef int (__stdcall *vv_record_arrivals_fn)(int game, const void *save_buffer, int slot,
                                               vv_arrival_fact *facts, int count, int apply);

/* The marker's path; 0 when the save folder is unknown. */
static int vv_arrival_marker_path(char *out, int game, int slot) {
    char folder[MAX_PATH];
    if (game < 1 || game > 5 || slot < 1 || slot > 5
        || !vv_save_subfolder(folder, "Virtual Villagers Fun Patcher Data\\Arrivals",
                              (int)sizeof("\\Virtual Villagers 1 Arrivals Recorded - Save 1.dat"))) {
        return 0;
    }
    _snprintf_s(out, MAX_PATH, _TRUNCATE, "%s\\Virtual Villagers %d Arrivals Recorded - Save %d.dat",
                folder, game, slot);
    return 1;
}

/* 1 when the slot's marker is there and is this game's and slot's. */
static int vv_arrival_marker_present(int game, int slot) {
    char path[MAX_PATH];
    HANDLE f;
    unsigned int data[4];
    DWORD got = 0;
    int ok;
    if (!vv_arrival_marker_path(path, game, slot)) {
        return 0;
    }
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(f, data, sizeof data, &got, NULL) && got == sizeof data
        && data[0] == VV_ARRIVAL_MARKER_MAGIC && data[1] == 1u
        && data[2] == (unsigned int)game && data[3] == (unsigned int)slot;
    CloseHandle(f);
    return ok;
}

/* Write the marker (to a temporary name, then moved into place, so a
   half-written marker is never read).  1 when it is there afterwards. */
static int vv_arrival_marker_write(int game, int slot) {
    char path[MAX_PATH];
    char temp[MAX_PATH + 8];
    HANDLE f;
    unsigned int data[4];
    DWORD put = 0;
    int ok;
    if (vv_arrival_marker_present(game, slot)) {
        return 1;
    }
    if (!vv_arrival_marker_path(path, game, slot)) {
        return 0;
    }
    /* A file of that name that is not this marker is preserved, never
       replaced (the owner's rule for every patcher .dat). */
    if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) {
        return 0;
    }
    _snprintf_s(temp, sizeof temp, _TRUNCATE, "%s.tmp", path);
    data[0] = VV_ARRIVAL_MARKER_MAGIC;
    data[1] = 1u;
    data[2] = (unsigned int)game;
    data[3] = (unsigned int)slot;
    f = CreateFileA(temp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = WriteFile(f, data, sizeof data, &put, NULL) && put == sizeof data && FlushFileBuffers(f);
    CloseHandle(f);
    if (!ok || !MoveFileExA(temp, path, MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(temp);
        return 0;
    }
    return 1;
}

#endif /* VV_ARRIVAL_BACKFILL_H */
