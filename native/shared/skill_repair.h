/* RESET OBVIOUSLY CORRUPTED SKILL VALUES (A New Home, The Lost Children,
   The Secret City).

   The owner (2026-10-11): "Can you reset obviously-corrupted skill values?"
   These three games keep each skill as a 32-bit int that their own skill
   writers clamp to 0..100 (A New Home 0x437230, The Lost Children 0x445430,
   The Secret City 0x455740).  A value outside that range can only come from
   outside the game (a memory editor, a damaged save); the skill upgrades
   reset it before they read the skills:

       below 0  -> 0
       above 100 -> 100

   Every value from 0 to 100 is valid and is never touched.  (The Tree of Life
   and New Believers keep float skills and have their own NaN / infinity
   handling in their companions.)

   Called only after the player has confirmed a purchase, on the villagers
   that purchase acts on, so Cancel changes nothing. */
#ifndef VV_SKILL_REPAIR_H
#define VV_SKILL_REPAIR_H

#define VV_SKILL_INT_MAX 100

/* Resets the out-of-range values among `count` contiguous int skills at
   rec + first_offset.  Returns how many values were reset. */
static int vv_repair_int_skills(unsigned char *rec, int first_offset, int count) {
    int reset = 0, s;
    for (s = 0; s < count; ++s) {
        int *value = (int *)(rec + first_offset + 4 * s);
        if (*value < 0) {
            *value = 0;
            ++reset;
        } else if (*value > VV_SKILL_INT_MAX) {
            *value = VV_SKILL_INT_MAX;
            ++reset;
        }
    }
    return reset;
}

/* "\r\n\r\nReset N corrupted skill value(s)." appended to a result message,
   only when something was reset. */
static void vv_append_skill_repairs(char *message, int reset) {
    char line[96];
    if (reset <= 0) {
        return;
    }
    wsprintfA(line, "\r\n\r\nReset %d corrupted skill %s.", reset,
              reset == 1 ? "value" : "values");
    lstrcatA(message, line);
}

#endif
