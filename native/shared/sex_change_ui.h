/* sex_change_ui.h -- Change Appearance's "Change sex..." button, the same in all five games (the owner,
   2026-11-15).  Include after <windows.h> and sex_change.h.

   The per-villager Change Appearance window shows a "Change sex..." button (VVFP_AX_CHANGE_SEX).  Pressing it:
     * a villager the change is refused for gets a message saying why (carrying or nursing a baby; a story
       villager), and nothing is changed;
     * anyone else gets the warning below, about the game's data only, answered Yes or No (No is the default).
       Yes makes the change AT ONCE through vv_sex_change_apply (sex_change.h: the field, the save's log, every
       companion told, the history record) -- not by the window's OK or Cancel, and not by Undo changes: pressing
       the button again changes it back.  The window then redraws its preview, which the game draws from the new
       sex's sheets (the same head and body rows).

   The words are neutral and about the game's data: what changes, what stays, who it is not offered for. */
#ifndef VVFP_SEX_CHANGE_UI_H
#define VVFP_SEX_CHANGE_UI_H

#define VVFP_AX_CHANGE_SEX 3506          /* inside appearance_extras.h's 3500..3539 */
#define VVFP_AX_CHANGE_SEX_LABEL "Change sex..."
#define VVFP_AX_CHANGE_SEX_TITLE "Change sex"

/* The warning for the villager called `name` whose sex is now `female` (1) or male (0), in `out` (at least 1024
   bytes). */
static void vvfp_sex_change_warning(char *out, const char *name, int female) {
    const char *to = female ? "male" : "female";
    wsprintfA(out,
              "Change %s's sex to %s?\n\n"
              "This changes the sex the game keeps for %s. The game then draws %s with the %s heads and "
              "bodies (the same head and body rows).\n\n"
              "It is done at once, not by OK or Cancel, and Undo changes does not undo it. Press Change sex "
              "again to change it back.\n\n"
              "These stay as they are: the name, the head and body rows, the skills, and every parent record. "
              "Children keep %s as the parent recorded at their birth.\n\n"
              "The patcher's own records follow %s: mask, head look, original look, title, last name and logs.\n\n"
              "Not offered for a villager who is carrying or nursing a baby, or for a story villager.",
              name, to, name, name, to, name, name);
}

/* The message for a refusal (sex_change.h VV_SEX_*), in `out` (at least 512 bytes). */
static void vvfp_sex_change_refused_text(char *out, const char *name, int why) {
    if (why == VV_SEX_EXPECTING) {
        wsprintfA(out, "%s is carrying or nursing a baby, so %s's sex cannot be changed now.", name, name);
    } else if (why == VV_SEX_SPECIAL) {
        wsprintfA(out, "%s is a story villager, so %s's sex cannot be changed.", name, name);
    } else {
        wsprintfA(out, "%s's sex could not be changed.", name);
    }
}

#ifndef VVFP_SEX_MESSAGE_BOX
#define VVFP_SEX_MESSAGE_BOX MessageBoxA
#endif

/* The button pressed in window `w` for villager `record` (record index `index`) of `game`: the refusal message,
   or the warning and, on Yes, the change.  1 when the change was made (the caller redraws its preview and
   whatever it shows by the sex), 0 otherwise. */
static int vvfp_ax_change_sex(HWND w, int game, unsigned char *record, int index) {
    char name[64], text[1024];
    int why;
    if (!vv_sex_game_ok(game) || record == NULL) {
        return 0;
    }
    vv_sex_name(game, record, name);
    why = vv_sex_change_refusal(game, record, index);
    if (why != VV_SEX_OK) {
        vvfp_sex_change_refused_text(text, name, why);
        (void)VVFP_SEX_MESSAGE_BOX(w, text, VVFP_AX_CHANGE_SEX_TITLE, MB_OK | MB_ICONINFORMATION);
        return 0;
    }
    vvfp_sex_change_warning(text, name, vv_sex_female(game, record));
    if (VVFP_SEX_MESSAGE_BOX(w, text, VVFP_AX_CHANGE_SEX_TITLE, MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2) != IDYES) {
        return 0;
    }
    why = vv_sex_change_apply(game, record, index);
    if (why != VV_SEX_OK) {
        vvfp_sex_change_refused_text(text, name, why);
        (void)VVFP_SEX_MESSAGE_BOX(w, text, VVFP_AX_CHANGE_SEX_TITLE, MB_OK | MB_ICONINFORMATION);
        return 0;
    }
    return 1;
}

#endif /* VVFP_SEX_CHANGE_UI_H */
