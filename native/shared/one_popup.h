/* one_popup.h -- ONE popup per island event (the owner, 2026-11-14), the protocol between "VVFP Scrolling Popups.dll"
   and the companions that run new island events in it ("VVFP Story Upgrades.dll": the Isola Grand Event Collection
   and Custom Island Events; "VVFP More Island Events.dll").

   With Scrolling Popups installed, a new island event shows in ONE popup from start to finish: its whole text (never
   split into pages), then its choices at the END of the text, INSIDE the scrolled content -- both scrollbars scroll
   the text and the choices together.  A choice clicked: the outcome replaces the text in the same popup (scrolling
   when long); another question puts its choices at the end again; the game's own OK ends the event.

   Scrolling Popups draws the choices (each a row with the game's own answer-button picture and the label in the
   body text's own font, as written: never upper-cased) after the text and hit-tests them at their scrolled place;
   the companion owning the popup keeps everything else: the text in the dialog's own field, the game's buttons
   (its two answers always hidden, OK hidden while the choices are asked), the keys 1 to 7, the effects and the log.

   Each owning companion exports:
     int __stdcall VvfpOnePopupRows(const void *popup, op_rows *out)
         1 when `popup` is one of its one-popup events (out filled: the choices shown now, 0 while OK is shown, and
         the room below the content its OK keeps), else 0 (the popup is drawn as before);
     int __stdcall VvfpOnePopupPick(const void *popup, int k)
         choice k (0 the first) was clicked: the companion answers it (the outcome replaces the text, its effects
         made); 1 when taken. */
#ifndef VVFP_ONE_POPUP_H
#define VVFP_ONE_POPUP_H

#define OP_MAX_ROWS 7
#define OP_LABEL_BYTES 128

typedef struct op_rows {
    int size;                                  /* sizeof(op_rows), set by the caller */
    int rows;                                  /* the choices at the end of the text now: 0 to OP_MAX_ROWS */
    int reserve;                               /* pixels kept below the content for the game's OK button */
    char labels[OP_MAX_ROWS][OP_LABEL_BYTES];  /* each choice's words, drawn as written */
} op_rows;

typedef int (__stdcall *op_rows_fn)(const void *popup, op_rows *out);
typedef int (__stdcall *op_pick_fn)(const void *popup, int k);

#endif
