/* Runtime harness: the parents follow their sex (the owner, 2026-11-27).  tests/test_parents_follow_sex.py builds
   and runs it (32-bit MSVC only).

   The Lost Children to New Believers copy the villager who carried into the newborn's Mother fields and the
   carrier's expected other parent into its Father fields.  "VVFP Parentage Export.dll" parents_follow_sex, at the
   birth splice: a man who carried a woman's baby is its Father and she its Mother, each with their own name, head and
   body; two of one sex keep the carrier as the Mother; anything not certain keeps the game's record.  Then the Birth
   record (compose_birth) prints the parents as the record now holds them, with the "Carried by" note every reader
   pairs the carrier's Conception with (birth_carried_by).

   The companion's source is compiled whole over a villager table laid out as each game's; nothing here reads or
   writes any file.  Exit code 0 when every check passes. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
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

static unsigned char *g_table;

static unsigned char *slot_of(const struct game_layout *g, int index) {
    return g_table + g->record_base + (size_t)index * g->stride;
}

static unsigned char *villager(const struct game_layout *g, int index, const char *name, int sex, int head, int body,
                               int carrying) {
    unsigned char *r = slot_of(g, index);
    memset(r, 0, g->stride);
    r[g->active] = 1;
    strcpy((char *)r + g->name, name);
    *(int *)(r + g->sex) = sex;
    *(int *)(r + g->head) = head;
    *(int *)(r + g->body) = body;
    if (carrying) {
        *(int *)(r + g->litter - 4u) = 300;     /* the pregnancy field: still set at the birth splice */
        *(int *)(r + g->litter) = 1;
    }
    return r;
}

/* A newborn as the game makes it: the carrier in the Mother fields, the expected other parent in the Father's. */
static unsigned char *newborn(const struct game_layout *g, int index, const char *carrier, int ch, int cb,
                              const char *other, int oh, int ob) {
    unsigned char *r = villager(g, index, "Coral Siutiti", g->sex_female, 2, 4, 0);
    strcpy((char *)r + g->parent_mother_name, carrier);
    *(int *)(r + g->parent_mother_head) = ch;
    *(int *)(r + g->parent_mother_body) = cb;
    strcpy((char *)r + g->parent_father_name, other);
    *(int *)(r + g->parent_father_head) = oh;
    *(int *)(r + g->parent_father_body) = ob;
    return r;
}

static int parents_are(const struct game_layout *g, const unsigned char *child, const char *father, int fh, int fb,
                       const char *mother, int mh, int mb) {
    return strcmp((const char *)child + g->parent_father_name, father) == 0
        && *(const int *)(child + g->parent_father_head) == fh && *(const int *)(child + g->parent_father_body) == fb
        && strcmp((const char *)child + g->parent_mother_name, mother) == 0
        && *(const int *)(child + g->parent_mother_head) == mh && *(const int *)(child + g->parent_mother_body) == mb;
}

int main(void) {
    int game;
    for (game = GAME_VV2; game <= GAME_VV5; ++game) {
        const struct game_layout *g = layout_of(game);
        size_t size = g->record_base + (size_t)g->slots * g->stride;
        char what[200], carrier[MAX_NAME_BYTES], text[RECORD_TEXT_MAX], note[256];
        unsigned char *child;
        g_table = (unsigned char *)calloc(1, size);
        if (g_table == NULL) {
            check(0, "the table");
            return 1;
        }

        /* 1. A man carried a woman's baby (New Believers' Ahi Mashudu and Vaihi Salongo, 2026-11-27). */
        villager(g, 0, "Ahi Mashudu", g->sex_male, 5, 6, 1);
        villager(g, 1, "Vaihi Salongo", g->sex_female, 8, 3, 0);
        villager(g, 2, "Tane Peponi", g->sex_male, 11, 12, 0);
        child = newborn(g, 3, "Ahi Mashudu", 5, 6, "Vaihi Salongo", 8, 3);
        carrier[0] = '\0';
        sprintf(what, "game %d: a male carrier and a female other parent trade places", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 1, what);
        sprintf(what, "game %d: Mother Vaihi Salongo (head 8, body 3), Father Ahi Mashudu (head 5, body 6)", game);
        check(parents_are(g, child, "Ahi Mashudu", 5, 6, "Vaihi Salongo", 8, 3), what);
        sprintf(what, "game %d: the carrier is named for the note", game);
        check(strcmp(carrier, "Ahi Mashudu") == 0, what);
        sprintf(what, "game %d: done once, a second look changes nothing (no carrier answers to the Mother now)", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 0
              && parents_are(g, child, "Ahi Mashudu", 5, 6, "Vaihi Salongo", 8, 3), what);

        /* 2. The Birth record prints them as the record holds them, with the note. */
        carried_by_father_note("Ahi Mashudu", "Vaihi Salongo", note, sizeof note);
        sprintf(what, "game %d: the Birth record names Vaihi as the Mother and Ahi as the Father, each their own looks",
                game);
        check(compose_birth(game, NULL, -1, -1, NULL, -1, -1, NULL, -1, -1, child, note, 1, text, sizeof text)
              && strstr(text, "  Mother: Vaihi Salongo\n    Head: 8\n    Body: 3\n"
                               "  Father: Ahi Mashudu\n    Head: 5\n    Body: 6\n") != NULL, what);
        sprintf(what, "game %d: ...and says who carried, as the readers pair it", game);
        check(strstr(text, "  Note: Carried by Ahi Mashudu, who is male (named as the Father; Vaihi Salongo is named "
                           "as the Mother)\n") != NULL
              && birth_carried_by(text, "Ahi Mashudu") && !birth_carried_by(text, "Vaihi Salongo"), what);

        /* 3. Two men: the carrier stays the Mother. */
        child = newborn(g, 4, "Ahi Mashudu", 5, 6, "Tane Peponi", 11, 12);
        sprintf(what, "game %d: two men: the carrier stays the Mother", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 0
              && parents_are(g, child, "Tane Peponi", 11, 12, "Ahi Mashudu", 5, 6), what);

        /* 4. Two women: the carrier stays the Mother. */
        villager(g, 5, "Moana Peponi", g->sex_female, 14, 15, 1);
        child = newborn(g, 6, "Moana Peponi", 14, 15, "Vaihi Salongo", 8, 3);
        sprintf(what, "game %d: two women: the carrier stays the Mother", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 0
              && parents_are(g, child, "Vaihi Salongo", 8, 3, "Moana Peponi", 14, 15), what);

        /* 5. A woman carried a man's baby: as ever. */
        villager(g, 7, "Lani Peponi", g->sex_female, 9, 9, 1);
        child = newborn(g, 8, "Lani Peponi", 9, 9, "Tane Peponi", 11, 12);
        sprintf(what, "game %d: a woman carried: unchanged", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 0
              && parents_are(g, child, "Tane Peponi", 11, 12, "Lani Peponi", 9, 9), what);

        /* 6. Not certain: the other parent gone, or two who answer to her; the carrier not carrying. */
        slot_of(g, 1)[g->active] = 0;
        child = newborn(g, 9, "Ahi Mashudu", 5, 6, "Vaihi Salongo", 8, 3);
        sprintf(what, "game %d: the woman gone (not in the village): the game's record kept", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 0
              && parents_are(g, child, "Vaihi Salongo", 8, 3, "Ahi Mashudu", 5, 6), what);
        slot_of(g, 1)[g->active] = 1;
        villager(g, 10, "Vaihi Salongo", g->sex_female, 8, 3, 0);
        sprintf(what, "game %d: two women of her name and looks: the game's record kept", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 0
              && parents_are(g, child, "Vaihi Salongo", 8, 3, "Ahi Mashudu", 5, 6), what);
        slot_of(g, 10)[g->active] = 0;
        *(int *)(slot_of(g, 0) + g->litter - 4u) = 0;
        sprintf(what, "game %d: nobody of the Mother's fields carrying: the game's record kept", game);
        check(parents_follow_sex(g, g_table, child, carrier, sizeof carrier) == 0
              && parents_are(g, child, "Vaihi Salongo", 8, 3, "Ahi Mashudu", 5, 6), what);
        free(g_table);
        g_table = NULL;
    }
    check(parents_follow_sex(layout_of(GAME_VV1), NULL, NULL, NULL, 0) == 0, "A New Home: no parents on the record here");
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
