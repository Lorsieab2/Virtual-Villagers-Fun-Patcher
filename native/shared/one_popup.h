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

   MULTI-LINE CHOICES (the owner, 2026-11-16: "the choice box can accommodate as many lines as it needs").  A label
   wider than its row is wrapped at its spaces into as many lines as it needs; its row (the game's answer-button
   picture, its ends kept and its middle repeated) grows to hold them, the rows below move down, and each row is
   clicked anywhere on its own height.

   PRACTICALLY UNLIMITED TEXT (the owner, 2026-11-16).  A dialog's text field holds what the game gives it (the later
   three games' island-event dialog 2,000 bytes, A New Home's and The Lost Children's 9,999): a text longer than that
   is kept whole by the companion that shows it, which puts only its first bytes in the field.  Scrolling Popups asks
   for the whole text (VvfpPopupWholeText) wherever it measures or draws the field, and draws that instead.  A label
   longer than op_rows.labels holds is handed over whole the same way (op_rows.label_text).

   Each owning companion exports:
     int __stdcall VvfpOnePopupRows(const void *popup, op_rows *out)
         1 when `popup` is one of its one-popup events (out filled: the choices shown now, 0 while OK is shown, and
         the room below the content its OK keeps), else 0 (the popup is drawn as before).  `out->size` is set by the
         caller: OP_ROWS_V1_BYTES (a Scrolling Popups made before label_text: only the first fields are written) or
         sizeof(op_rows);
     int __stdcall VvfpOnePopupPick(const void *popup, int k)
         choice k (0 the first) was clicked: the companion answers it (the outcome replaces the text, its effects
         made); 1 when taken;
     const char *__stdcall VvfpPopupWholeText(const char *shown)
         when the companion put into a dialog's text field only the first n bytes of a longer text, and `shown` (the
         field as it is now) is exactly those n bytes: the whole text (NUL-ended, kept until the companion shows
         another); else NULL (the field is the whole text). */
#ifndef VVFP_ONE_POPUP_H
#define VVFP_ONE_POPUP_H

#define OP_MAX_ROWS 7
#define OP_LABEL_BYTES 128

typedef struct op_rows {
    int size;                                  /* sizeof(op_rows) or OP_ROWS_V1_BYTES, set by the caller */
    int rows;                                  /* the choices at the end of the text now: 0 to OP_MAX_ROWS */
    int reserve;                               /* pixels kept below the content for the game's OK button */
    char labels[OP_MAX_ROWS][OP_LABEL_BYTES];  /* each choice's words, drawn as written */
    /* Version 2 (size == sizeof(op_rows)): each choice's words whole when they are longer than labels[k] holds,
       kept by the companion until its next choices (NULL: labels[k] is the whole label). */
    const char *label_text[OP_MAX_ROWS];
} op_rows;

#define OP_ROWS_V1_BYTES (3 * 4 + OP_MAX_ROWS * OP_LABEL_BYTES)

/* The caller's struct is one the companion can fill: version 1 or 2. */
#define OP_ROWS_SIZE_OK(r) ((r)->size == (int)OP_ROWS_V1_BYTES || (r)->size == (int)sizeof(op_rows))
#define OP_ROWS_HAS_TEXT(r) ((r)->size == (int)sizeof(op_rows))

typedef int (__stdcall *op_rows_fn)(const void *popup, op_rows *out);
typedef int (__stdcall *op_pick_fn)(const void *popup, int k);
typedef const char *(__stdcall *op_whole_fn)(const char *shown);

/* A companion's whole text (VvfpPopupWholeText): `whole` the text shown, `cut` the bytes of it put in the field
   (0: the field holds all of it). */
typedef struct op_long_text {
    const char *whole;
    int cut;
} op_long_text;

/* What to put in a field of `field_bytes` (NUL included) for `text`: the bytes copied (the whole text when it fits,
   else its first bytes, at a space or a line break when one is near).  `keep` records the cut for
   op_long_text_whole. */
static __inline int op_long_text_put(op_long_text *keep, char *field, int field_bytes, const char *text) {
    int n = 0, cut;
    if (field == NULL || field_bytes <= 0) {
        return 0;
    }
    if (text == NULL) {
        text = "";
    }
    while (text[n] != 0) {
        ++n;
    }
    if (n < field_bytes) {
        for (cut = 0; cut <= n; ++cut) {
            field[cut] = text[cut];
        }
        if (keep != NULL) {
            keep->whole = NULL;
            keep->cut = 0;
        }
        return n;
    }
    cut = field_bytes - 1 > 16 ? field_bytes - 16 : field_bytes - 1;   /* a little short of the field: the game's own
                                                                           copy keeps every byte of it */
    {
        int k;
        for (k = cut; k > cut - 200 && k > 0; --k) {
            if (text[k] == ' ' || text[k] == '\n') {
                cut = k;
                break;
            }
        }
    }
    for (n = 0; n < cut; ++n) {
        field[n] = text[n];
    }
    field[cut] = 0;
    if (keep != NULL) {
        keep->whole = text;
        keep->cut = cut;
    }
    return cut;
}

/* VvfpPopupWholeText's answer from one kept text. */
static __inline const char *op_long_text_whole(const op_long_text *keep, const char *shown) {
    int n;
    if (keep == NULL || keep->whole == NULL || keep->cut <= 0 || shown == NULL) {
        return NULL;
    }
    for (n = 0; n < keep->cut; ++n) {
        if (shown[n] != keep->whole[n] || shown[n] == 0) {
            return NULL;
        }
    }
    return shown[keep->cut] == 0 ? keep->whole : NULL;
}

#endif
