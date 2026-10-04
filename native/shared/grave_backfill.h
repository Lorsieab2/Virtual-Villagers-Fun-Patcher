/* The graves a village holds, handed from "VVFP Cause of Death.dll" to "VVFP
   Parentage Export.dll" so that every grave has a Death record in the
   village's Deaths log -- including the graves dug before that log existed,
   or while the game was catching up on time away, which no hook saw.

   The owner: "two villagers are missing from the deaths log!" -- A New Home's
   Kito and Chika were buried before v1.35.51 introduced the log -- and "make
   sure all the logs are consistent with the current save".

   Cause of Death reads the graves (it knows each game's graveyard) and keeps
   which ones the log already covers; the parentage DLL files the records (it
   knows the logs, their village headers and the records it is still
   holding), decides which graves the log already has a record for, and fills
   in what the grave does not hold from the Village History log.  The call is
   RecordGravesMissingFromLog in parentage_export.c.

   The owner: "the player should be notified first before any fix runs."  So
   the same call first only COUNTS (apply 0): the first-load cross-check asks
   Cause of Death how many graves lack a record (VvfpCauseScanGraves) and lists
   them in its one popup, and only when the player chooses Repair
   (VvfpCauseRepairGraves) are the records written, at the village's next
   save. */
#ifndef VV_GRAVE_BACKFILL_H
#define VV_GRAVE_BACKFILL_H

#define VV_GRAVE_NAME 32
#define VV_GRAVE_LINE 64
#define VV_GRAVE_CAUSE 160
#define VV_GRAVE_EPITAPH 80

/* What became of a grave (vv_grave_fact.outcome). */
enum {
    VV_GRAVE_UNDECIDED = 0,     /* nothing decided: asked again at the next save */
    VV_GRAVE_IN_LOG = 1,        /* the log already has its Death record */
    VV_GRAVE_RECORDED = 2,      /* its Death record is on disk now */
    VV_GRAVE_MISSING = 3,       /* no record: one would be written (apply 0) */
    /* Its record is only held in memory for the next save (Codex, #524): not
       yet durable, so Cause of Death does not keep the grave as covered --
       the next save or load finds it in the log, or records it again. */
    VV_GRAVE_HELD = 4,          /* matched by a record still held for the save */
    VV_GRAVE_QUEUED = 5         /* its record was made now, and is held for the save */
};

typedef struct {
    int place;                      /* the grave's own place: VV1/VV2 grave 0-49, VV3-VV5 entry 0-499 */
    int age;                        /* the age at death the grave holds, in age units */
    int covered;                    /* in: already known to have a record (kept by Cause of Death) */
    int outcome;                    /* out: VV_GRAVE_* */
    int identified;                 /* out (RECORDED/QUEUED): 1 when the Village History
                                       log said who it was -- head and body below */
    int head, body;
    char name[VV_GRAVE_NAME];       /* as the grave holds it, NUL-terminated */
    char grave[VV_GRAVE_LINE];      /* the skill line: a Death record's "Grave:" */
    char cause[VV_GRAVE_CAUSE];     /* a Death record's "Cause of death:" */
    char epitaph[VV_GRAVE_EPITAPH]; /* a Death record's "Epitaph:" */
} vv_grave_fact;

/* RecordGravesMissingFromLog(game, save_buffer, slot, graves, count, apply):
   `save_buffer` and `slot` are the save just made (the village the logs are
   headed with is read from them, as PublishVillageAtSave reads it); with no
   buffer (a village just loaded) the slot's own save file names it ("VVFP Save
   Reset.dll", SavedVillageHeader).  With `apply` 0 nothing is written: each
   grave the log lacks is VV_GRAVE_MISSING and the count of them is returned.
   With 1 their records are written (VV_GRAVE_RECORDED, or VV_GRAVE_QUEUED
   while held for the save) and the count of them is returned.  -1 when nothing could be decided (the village
   unknown, a log unreadable): every outcome is then VV_GRAVE_UNDECIDED. */
typedef int (__stdcall *vv_record_graves_fn)(int game, const void *save_buffer, int slot,
                                             vv_grave_fact *graves, int count, int apply);

#endif /* VV_GRAVE_BACKFILL_H */
