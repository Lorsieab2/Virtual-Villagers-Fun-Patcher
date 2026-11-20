/* ONE popup per island event (the owner, 2026-11-14; native/shared/one_popup.h) for every More Island Events question
   event.  Included by vvfp_more_island_events.c after adv_log.inc.

   With "VVFP Scrolling Popups.dll" installed (adv_scrolls), a question event runs whole in the popup the game builds
   for it: its question's text (all its pages, one text, never split) with its answers drawn by Scrolling Popups at
   the END of the text, inside the scrolled content (VvfpOnePopupRows / VvfpOnePopupPick, vvfp_more_island_events.c);
   an answer (a row, or the keys 1 to 7) shows its outcome in place of the text -- the next question's text with its
   answers again (The Cave Explorers), or the ending's text -- and the game's own OK ends the event.  The game's own
   two answer buttons are never shown (vvfp_multi_answer_12.h mb_*_op in A New Home and The Lost Children,
   vvfp_multi_answer.h ma_op_* in the later three).

   This is the flow's run, the same in every game (each game's file writes `mop.text` into its dialog's own text
   field): the answer is its flow's own choose, and the ending's effects (adv_log_effects: the Island Events log's ONE
   entry, with a "Choice:" line for each answer) are made when the text that ends the ending is shown -- at the answer
   when it all fits in one text, as it does (a text holds every page of it while the bytes allow; the rest, a fault
   of a translation's length, comes with OK in the same popup).  Without Scrolling Popups nothing here runs.

   The Secret City, The Tree of Life and New Believers (the owner, v1.35.97: one scrolling popup, never pages with
   OK): their texts are never limited by the dialog's 2,000-byte field -- mop_begin is given MOP_TEXT_BYTES, so a
   text holds every page, and the field gets only its start (adv_vv345.inc t_op_put: one_popup.h op_long_text_put),
   Scrolling Popups drawing the whole (VvfpPopupWholeText). */

#define MOP_TEXT_BYTES (ADV_MAX_PAGES * ADV_PAGE_BYTES + 1024)   /* every page of a text, a line apart, and the
                                                                    answer's words before them */

static struct {
    const adv_flow *flow;
    int active;                        /* an event runs in one popup */
    int node;                          /* the question asked (or last asked) */
    int ending;                        /* the ending reached, -1 none */
    int asking;                        /* the question's answers come once its text is all shown */
    const adv_pages *pages;            /* the pages the text shows */
    int next_page;                     /* the first page not yet shown */
    int effects_due;                   /* the ending's effects, made when its last page is shown */
    int cap;                           /* the dialog's text room */
    const char *lead;                  /* the answer just picked, its row's words: the next text's first line */
    char text[MOP_TEXT_BYTES];         /* the text shown now */
} mop;

/* The text: the pages from the next one on, a line apart, as many as the room holds (always one). */
static void mop_fill(void) {
    int first = 1, cap = mop.cap > 0 && mop.cap <= MOP_TEXT_BYTES ? mop.cap : MOP_TEXT_BYTES;
    mop.text[0] = '\0';
    if (mop.lead != NULL && mop.lead[0] != '\0') {
        /* cie-v6-binary.md 19: the choice picked starts its outcome, a blank line after it (display only: the
           log's "Choice:" line is the record) */
        adv_cat(mop.text, cap, mop.lead);
        if (mop.pages != NULL && mop.next_page < mop.pages->count) {
            adv_cat(mop.text, cap, "\n\n");
        }
    }
    mop.lead = NULL;
    while (mop.pages != NULL && mop.next_page < mop.pages->count) {
        const char *page = mop.pages->text[mop.next_page];
        if (!first && adv_len(mop.text) + 1 + adv_len(page) >= cap) {
            break;
        }
        if (!first) {
            adv_cat(mop.text, cap, "\n");
        }
        adv_cat(mop.text, cap, page);
        ++mop.next_page;
        first = 0;
    }
    if (mop.effects_due && (mop.pages == NULL || mop.next_page >= mop.pages->count)) {
        mop.effects_due = 0;
        adv_log_effects(mop.flow->effects, mop.ending);
    }
}

/* The event (composed, its log entry begun) starts in one popup: its first question's text. */
static void mop_begin(const adv_flow *flow, int cap) {
    memset(&mop, 0, sizeof mop);
    mop.flow = flow;
    mop.active = flow != NULL;
    mop.ending = -1;
    mop.asking = 1;
    mop.cap = cap;
    mop.pages = flow != NULL ? flow->question(0) : NULL;
    mop_fill();
}

/* The answers shown now (0 while OK is shown), their words in `out` when given. */
static int mop_rows(op_rows *out) {
    int k, n = 0;
    if (mop.active && mop.asking && mop.pages != NULL && mop.next_page >= mop.pages->count) {
        n = adv_answers(mop.flow, mop.node);
    }
    if (out != NULL) {
        out->rows = n;
        for (k = 0; k < n && k < OP_MAX_ROWS; ++k) {
            out->labels[k][0] = '\0';
            mop.flow->label(mop.node, k, out->labels[k], OP_LABEL_BYTES);
        }
    }
    return n;
}

/* Answer k (0 the first): logged, its flow's own choose, its outcome's text (the next question's, or the ending's,
   with the ending's effects as its last page is shown).  1 when taken. */
static int mop_pick(int k) {
    static char label[OP_LABEL_BYTES];
    int next;
    if (k < 0 || k >= mop_rows(NULL)) {
        return 0;
    }
    label[0] = '\0';
    mop.flow->label(mop.node, k, label, sizeof label);
    adv_log_choice(label);
    next = mop.flow->choose(mop.node, k);
    mop.next_page = 0;
    if (next < 0) {
        mop.ending = -1 - next;
        mop.asking = 0;
        mop.pages = mop.flow->ending(mop.ending);
        mop.effects_due = 1;
    } else {
        mop.node = next;
        mop.pages = mop.flow->question(next);
    }
    mop.lead = label;
    mop_fill();
    return 1;
}

/* OK: 1 when another text took the shown one's place (the popup stays). */
static int mop_ok(void) {
    if (!mop.active || mop.pages == NULL || mop.next_page >= mop.pages->count) {
        return 0;
    }
    mop_fill();
    return 1;
}

/* The popup closes: the event is over (its effects never left unmade: a page count that changed is a fault). */
static void mop_end(void) {
    if (mop.active && mop.effects_due) {
        mop.effects_due = 0;
        adv_log_effects(mop.flow->effects, mop.ending);
    }
    mop.active = 0;
}
