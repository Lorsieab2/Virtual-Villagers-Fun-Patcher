/* look_change_log.h -- a change the patcher keeps OUTSIDE the save (the gender presentation, the head look) written
   to the Births and Conceptions log, as a sex change is (native/shared/sex_change.h vv_sex_history).

   The owner, 2026-11-17: "the logs need to keep track of sex and gender presentation changes ... and everything".
   Change Appearance's choice and the Custom Island Event's effect both reach the companion's own Set export, so the
   record is written there, once, whoever made the change: an "Appearance changed" record ("VVFP Parentage
   Export.dll" WriteVillageRecord, kind 7: held until the next save, so the log never runs ahead of the save), the
   head and body the same before and after (the rows never change), with two more lines in the words of the sex
   change's "Old sex" / "New sex":

       Appearance changed
         Name: Ann
         Old head: 3
         Old body: 4
         New head: 3
         New body: 4
         Old gender presentation: Own look
         New gender presentation: Other sex's look

   Nothing is written when that DLL is not part of the game, or when the value did not change.

   Include sex_change.h first (its VV_SEX_LAYOUT gives each game's head and body offsets).  Header-only and
   file-static. */
#ifndef VV_LOOK_CHANGE_LOG_H
#define VV_LOOK_CHANGE_LOG_H

#include <windows.h>
#include "patcher_files.h"

#define VV_LOOK_LOG_KIND_APPEARANCE 7        /* the Parentage Export's "Appearance changed" */

/* The words each kept value is logged with (the Change Appearance window's own). */
#define VV_LOOK_LOG_PRESENTATION "gender presentation"
#define VV_LOOK_LOG_PRESENTATION_OWN "Own look"
#define VV_LOOK_LOG_PRESENTATION_OTHER "Other sex's look"
#define VV_LOOK_LOG_HEAD_LOOK "head look"

typedef int (__stdcall *vv_look_log_write_fn)(int, int, const void *, int, const char *, const char *, int);

/* `label` and then `value` in decimal appended to `out` (kernel32 only: these companions link no user32). */
static void vv_look_log_int(char *out, const char *label, int value) {
    char digits[16];
    int n = 0, k;
    unsigned int v = value < 0 ? 0u - (unsigned int)value : (unsigned int)value;
    lstrcatA(out, label);
    do {
        digits[n++] = (char)('0' + v % 10u);
        v /= 10u;
    } while (v != 0u && n < 12);
    if (value < 0) {
        digits[n++] = '-';
    }
    k = lstrlenA(out);
    while (n > 0) {
        out[k++] = digits[--n];
    }
    out[k] = '\0';
}

/* "  Old <what>: <was>" and "  New <what>: <now>" for the villager in `record` of `game`, after the head and body
   lines.  1 when handed over. */
static int vv_look_log(int game, const unsigned char *record, const char *what, const char *was, const char *now) {
    static vv_look_log_write_fn write_record;
    static int looked;
    char lines[320];
    int head, body;
    if (game < 1 || game > 5 || record == NULL || what == NULL || was == NULL || now == NULL
        || lstrcmpA(was, now) == 0 || lstrlenA(what) + lstrlenA(was) + lstrlenA(now) > 160) {
        return 0;
    }
    if (!looked) {
        HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
        looked = 1;
        write_record = module != NULL
            ? (vv_look_log_write_fn)(void *)GetProcAddress(module, "WriteVillageRecord") : NULL;
    }
    if (write_record == NULL) {
        return 0;
    }
    head = *(const int *)(record + VV_SEX_LAYOUT[game].head);
    body = *(const int *)(record + VV_SEX_LAYOUT[game].body);
    lines[0] = '\0';
    vv_look_log_int(lines, "  Old head: ", head);
    vv_look_log_int(lines, "\n  Old body: ", body);
    vv_look_log_int(lines, "\n  New head: ", head);
    vv_look_log_int(lines, "\n  New body: ", body);
    lstrcatA(lines, "\n  Old ");
    lstrcatA(lines, what);
    lstrcatA(lines, ": ");
    lstrcatA(lines, was);
    lstrcatA(lines, "\n  New ");
    lstrcatA(lines, what);
    lstrcatA(lines, ": ");
    lstrcatA(lines, now);
    lstrcatA(lines, "\n");
    return write_record(game, VV_LOOK_LOG_KIND_APPEARANCE, record, 1, lines, NULL, 0) != 0;
}

#endif /* VV_LOOK_CHANGE_LOG_H */
