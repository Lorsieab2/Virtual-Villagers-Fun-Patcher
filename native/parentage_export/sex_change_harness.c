/* Runtime harness: a villager's sex changed (native/shared/sex_change.h), and "VVFP Parentage Export.dll" keeps
   the "Appearance changed" records noted for them theirs.  tests/test_sex_change_parentage_export.py builds and
   runs it (32-bit MSVC only).

   The notes (look_notes) are what VVFP Cause of Death's save-time roster asks (AppearanceAlreadyLogged) before it
   writes a look change "Changed by: the game"; they are kept by the villager's name AND sex, so after a change of
   sex a look change already in the log would be written a second time.  VvfpVillagerSexChanged carries them.
   Also: the change's own "Appearance changed" lines (the four look lines, then "Old sex" / "New sex") are read as
   any other (note_appearance_logged and relook_last_name read the four look lines first).

   The companion's source is compiled whole; nothing here reads or writes any file.  Exit code 0 when every check
   passes. */
#include <stdio.h>
#include <string.h>
#include <windows.h>
#include <shlobj.h>

#define main parentage_export_main_unused
#include "../parentage_export/parentage_export.c"
#undef main

static int failures;
static int checks;

static void check(int ok, const char *what) {
    ++checks;
    printf("  %s %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}

int main(void) {
    static unsigned char rec[0xE48C], was[0xE48C], other[0xE48C];
    int game;
    for (game = GAME_VV1; game <= GAME_VV5; ++game) {
        const struct game_layout *g = layout_of(game);
        char what[160];
        int one;
        memset(look_notes, 0, sizeof look_notes);
        look_note_next = 0;
        memset(rec, 0, sizeof rec);
        strcpy((char *)rec + g->name, "Lani");
        *(int *)(rec + g->sex) = g->sex_female;
        *(int *)(rec + g->head) = 5;
        *(int *)(rec + g->body) = 6;
        note_appearance_logged(g, rec, "  Old head: 3\n  Old body: 4\n  New head: 5\n  New body: 6\n");
        memcpy(other, rec, sizeof rec);                     /* a namesake of the other sex, logged nothing */
        *(int *)(other + g->sex) = g->sex_male;
        one = AppearanceAlreadyLogged(game, rec, 3, 4, 5, 6) == 1 && AppearanceAlreadyLogged(game, other, 3, 4, 5, 6) == 0;
        sprintf(what, "game %d: the look change is noted for her, by name and sex", game);
        check(one, what);
        memcpy(was, rec, sizeof rec);
        *(int *)(rec + g->sex) = g->sex_male;
        sprintf(what, "game %d: without the word the note is lost (the control)", game);
        check(AppearanceAlreadyLogged(game, rec, 3, 4, 5, 6) == 0, what);
        sprintf(what, "game %d: the change is carried", game);
        check(VvfpVillagerSexChanged(game, 1, rec, was) == 1, what);
        sprintf(what, "game %d: after the change the note is still theirs: no second record at the save", game);
        check(AppearanceAlreadyLogged(game, rec, 3, 4, 5, 6) == 1, what);
        sprintf(what, "game %d: nothing more to carry, and the same sex is no change", game);
        check(VvfpVillagerSexChanged(game, 1, rec, was) == 0 && VvfpVillagerSexChanged(game, 1, rec, rec) == 0, what);
        /* The change's own record: the four look lines, then the sex lines. */
        note_appearance_logged(g, rec, "  Old head: 5\n  Old body: 6\n  New head: 5\n  New body: 6\n"
                                       "  Old sex: Female\n  New sex: Male\n");
        sprintf(what, "game %d: the change's own record is read as an Appearance changed record", game);
        check(look_notes[1].game == game && look_notes[1].oh == 5 && look_notes[1].nb == 6
              && look_notes[1].sex == g->sex_male && strcmp(look_notes[1].name, "Lani") == 0, what);
    }
    check(VvfpVillagerSexChanged(9, 1, rec, was) == 0 && VvfpVillagerSexChanged(GAME_VV3, 1, NULL, was) == 0,
          "no game, no record: nothing");
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
