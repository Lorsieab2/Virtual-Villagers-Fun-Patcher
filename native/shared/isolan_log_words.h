/* New Believers' log words for the Heathens in the Guardians of Isola wording when the rewrite is on.

   The owner (2026-11-23): "with the Guardians of Isola patch Heathens = Isolans", everywhere -- the logs too.  The
   puzzle Heathens' titles are the rewrite's OWN in-game names (guardians_role_titles.h, generated from its
   sm.xml); every other word follows the owner's pairs (Heathen -> Isolan, Heathens -> Isolans, a Heathen -> an
   Isolan).  The rewrite is seen as the logs' Faction line sees it (heathen_word.h vv5_guardians_of_isola: the
   running game's own string 0x48).  Every reader takes both wordings, old logs included (src/vv_isolan_words.py;
   Revive's puzzle-Heathen check, vv5_puzzle_role_title below).  Header-only and static; New Believers only: the
   caller says so. */
#ifndef VV_ISOLAN_LOG_WORDS_H
#define VV_ISOLAN_LOG_WORDS_H

#include <windows.h>
#include "heathen_word.h"
#include "guardians_role_titles.h"

/* The Arrived record's "How:" of a Heathen who joined the tribe. */
#define VV5_CONVERTED_HEATHENS "Converted from the Heathens"
#define VV5_CONVERTED_ISOLANS "Converted from the Isolans"
/* The Death record's grave line of a Heathen who left nothing. */
#define VV5_NO_GRAVE_HEATHENS "no grave (died among the Heathens: nothing was left)"
#define VV5_NO_GRAVE_ISOLANS "no grave (died among the Isolans: nothing was left)"
/* The Arrived record's "How:" of a camp Heathen made in the place of one who died ("VVFP Heathen Aging.dll"). */
#define VV5_REPLACED_OLD_AGE_HEATHEN "Replaced a Heathen who died of old age"
#define VV5_REPLACED_OLD_AGE_ISOLAN "Replaced an Isolan who died of old age"
#define VV5_REPLACED_EVENT_HEATHEN "Replaced a Heathen lost in an island event"
#define VV5_REPLACED_EVENT_ISOLAN "Replaced an Isolan lost in an island event"
/* The Village Statistics log's row of New Believers' conversions. */
#define VV5_CONVERTED_ROW_HEATHENS "Heathens Converted"
#define VV5_CONVERTED_ROW_ISOLANS "Isolans Converted"

static const char *vv5_word_converted(void) {
    return vv5_guardians_of_isola() ? VV5_CONVERTED_ISOLANS : VV5_CONVERTED_HEATHENS;
}

static const char *vv5_word_no_grave(void) {
    return vv5_guardians_of_isola() ? VV5_NO_GRAVE_ISOLANS : VV5_NO_GRAVE_HEATHENS;
}

static const char *vv5_word_replaced(int island_event) {
    int isolan = vv5_guardians_of_isola();
    return island_event ? (isolan ? VV5_REPLACED_EVENT_ISOLAN : VV5_REPLACED_EVENT_HEATHEN)
                        : (isolan ? VV5_REPLACED_OLD_AGE_ISOLAN : VV5_REPLACED_OLD_AGE_HEATHEN);
}

static const char *vv5_word_converted_row(void) {
    return vv5_guardians_of_isola() ? VV5_CONVERTED_ROW_ISOLANS : VV5_CONVERTED_ROW_HEATHENS;
}

/* A puzzle Heathen's title, role 12..17 (NULL for any other role): the game's own, or the rewrite's. */
static const char *vv5_role_title(int role) {
    if (role < 12 || role > 17) {
        return NULL;
    }
    return vv5_guardians_of_isola() ? VV5_ROLE_TITLES_ISOLAN[role - 12] : VV5_ROLE_TITLES_HEATHEN[role - 12];
}

/* 1 when `title` names a puzzle Heathen in either wording (a log's "Special villager" line, old logs included). */
static int vv5_puzzle_role_title(const char *title) {
    int k;
    if (title == NULL) {
        return 0;
    }
    for (k = 0; k < 6; ++k) {
        if (lstrcmpA(title, VV5_ROLE_TITLES_HEATHEN[k]) == 0 || lstrcmpA(title, VV5_ROLE_TITLES_ISOLAN[k]) == 0) {
            return 1;
        }
    }
    return 0;
}

#endif
