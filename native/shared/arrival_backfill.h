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
         How: <Founder | the island event's title | Barrel of Babies |
               Custom Island Event | Converted from the Heathens | unknown>
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
   version 1, game, slot.  It says the slot's backfill is done: written once
   the backfill has put every missing record on disk.  Start Over deletes it
   with the village (native/shared/save_reset.c).

   BIRTH RECORDS, BACKFILLED (v1.35.58, The Lost Children to New Believers).
   Those four games keep each villager's own parents on the villager's record
   for life, so a living villager with parents there was born in the village;
   one born before the Births log existed has no Birth record.  After the
   first-load prompt's Repair, at the next save, each gets one written FROM
   THE SAVE'S RECORD -- the lines a Birth record prints (the child's name,
   head, body, likes, dislikes and skills; both parents' names, heads and
   bodies as the record keeps them), then

         Note: Recorded afterwards (born before this log existed)

   (RecordBirthsMissingFromLog: the same matching and the same exactly-once
   rule as the Arrived records -- a Birth or Arrived record of the same name,
   head and body, on disk or held, is that villager's).  A New Home keeps no
   parents on the record, so nothing in its save says who was born there: no
   backfill.  The marker is "...Data\Births\Virtual Villagers N Births
   Recorded - Save S.dat", 'VCB1', the same shape; Start Over deletes it. */
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
    VV_ARRIVAL_QUEUED = 5,      /* their record was made now, and is held for the save */
    VV_ARRIVAL_CONTEXT = 6      /* in (set by the caller): a villager of the village who
                                   is not being recorded by this call -- counted for the
                                   names and the records they take, never written */
};

/* RecordArrivalsMissingFromLog's `apply`. */
enum {
    VV_ARRIVAL_COUNT = 0,       /* count the villagers with no record; write nothing */
    VV_ARRIVAL_APPLY = 1        /* the backfill: "How: Founder" for a villager in the
                                   village's first Village History snapshot, else
                                   "How: unknown", and the "Recorded afterwards" note */
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

/* RecordBirthsMissingFromLog(game, save_buffer, slot, facts, count, apply):
   the same contract for Birth records (The Lost Children to New Believers;
   A New Home always 0).  Every living villager of the village is handed
   over; the ones NOT to be recorded by this call come with `outcome`
   VV_ARRIVAL_CONTEXT and are only counted: a name they share decides
   nothing, and a record that matches them is theirs first.
   RecordArrivalsMissingFromLog honours the same mark. */
typedef int (__stdcall *vv_record_births_fn)(int game, const void *save_buffer, int slot,
                                             vv_arrival_fact *facts, int count, int apply);

/* Which backfill a marker is for. */
#define VV_BACKFILL_ARRIVALS 0
#define VV_BACKFILL_BIRTHS   1
#define VV_BIRTH_MARKER_MAGIC 0x31424356u       /* 'VCB1' */

/* The marker's path; 0 when the save folder is unknown. */
static int vv_backfill_marker_path(char *out, int which, int game, int slot) {
    char folder[MAX_PATH];
    const char *sub = which == VV_BACKFILL_BIRTHS ? "Virtual Villagers Fun Patcher Data\\Births"
                                                  : "Virtual Villagers Fun Patcher Data\\Arrivals";
    const char *what = which == VV_BACKFILL_BIRTHS ? "Births" : "Arrivals";
    if (game < 1 || game > 5 || slot < 1 || slot > 5
        || !vv_save_subfolder(folder, sub,
                              (int)sizeof("\\Virtual Villagers 1 Arrivals Recorded - Save 1.dat"))) {
        return 0;
    }
    _snprintf_s(out, MAX_PATH, _TRUNCATE, "%s\\Virtual Villagers %d %s Recorded - Save %d.dat",
                folder, game, what, slot);
    return 1;
}

static unsigned int vv_backfill_marker_magic(int which) {
    return which == VV_BACKFILL_BIRTHS ? VV_BIRTH_MARKER_MAGIC : VV_ARRIVAL_MARKER_MAGIC;
}

/* 1 when the slot's marker is there and is this game's and slot's. */
static int vv_backfill_marker_present(int which, int game, int slot) {
    char path[MAX_PATH];
    HANDLE f;
    unsigned int data[4];
    DWORD got = 0;
    int ok;
    if (!vv_backfill_marker_path(path, which, game, slot)) {
        return 0;
    }
    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(f, data, sizeof data, &got, NULL) && got == sizeof data
        && data[0] == vv_backfill_marker_magic(which) && data[1] == 1u
        && data[2] == (unsigned int)game && data[3] == (unsigned int)slot;
    CloseHandle(f);
    return ok;
}

/* Write the marker (to a temporary name, then moved into place, so a
   half-written marker is never read).  1 when it is there afterwards.  A
   file of that name that is not this marker is preserved, never replaced
   (the owner's rule for every patcher .dat): GetFileAttributesA refuses it,
   and the move is made without MOVEFILE_REPLACE_EXISTING. */
static int vv_backfill_marker_write(int which, int game, int slot) {
    char path[MAX_PATH];
    char temp[MAX_PATH + 8];
    HANDLE f;
    unsigned int data[4];
    DWORD put = 0;
    int ok;
    if (vv_backfill_marker_present(which, game, slot)) {
        return 1;
    }
    if (!vv_backfill_marker_path(path, which, game, slot)) {
        return 0;
    }
    if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) {
        return 0;
    }
    _snprintf_s(temp, sizeof temp, _TRUNCATE, "%s.tmp", path);
    data[0] = vv_backfill_marker_magic(which);
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

static int vv_arrival_marker_present(int game, int slot) {
    return vv_backfill_marker_present(VV_BACKFILL_ARRIVALS, game, slot);
}

static int vv_arrival_marker_write(int game, int slot) {
    return vv_backfill_marker_write(VV_BACKFILL_ARRIVALS, game, slot);
}

#endif /* VV_ARRIVAL_BACKFILL_H */
