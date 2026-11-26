/* skin_tone_rules.h -- the numbers and the one rule of the skin tones, shared by "VVFP Skin Tones.dll"
   (native/vvfp_skin_tones/vvfp_skin_tones.c), its harness and whoever asks it.  src/vv_skin_tones.py holds the
   same numbers for the patcher's Python; tests/test_skin_tones.py holds the two together.

   A TONE.  0: none kept yet (drawn with the game's own art).  1..VVFP_SKIN_TONE_COUNT: light to dark, the
   owner's ten, Porcelain to Ebony (2026-11-26).  15: the game's own art ("Game's own"), chosen in Change
   Appearance.

   THE KEPT BYTES (two per villager, in the Head Looks' file shape with the magic 'VST2').  The second is
   the villager's BIRTH TONE: the tone they were born with or first given (0: none), which "Reset to birth
   tone" puts back.  Of the first, the low four bits
   are the villager's tone; the high four are, on a carrying mother, HER BABY'S tone, rolled once at the
   conception (0: none).  The held baby is drawn with it and the newborn is given it unchanged (the owner:
   "baby sprites need skin tones too", decided at the conception so it never changes).

   INHERITANCE.  The owner, 2026-11-26: "babies conceived from two parents inherit skin tones same as head
   rules."  The later games' creators roll a newborn's head as (The Lost Children 0x44CBAB, The Secret City
   0x4564A7, The Tree of Life 0x45F235, New Believers 0x46853A):
       rand(100) >= 5 and a parent's value not 0:  (father + mother) / 2 + rand(3) - 1, held to the range
       otherwise:                                  any value, each as likely
   vvfp_skin_tone_inherit is that rule on the tone number, held to 1..COUNT.  A New Home's births inherit
   nothing of their own (creator 0x43C350), so its tones use the same rule.  A parent whose tone is not
   known counts as the other parent's; with neither known the tone is random, as the head is. */
#ifndef VVFP_SKIN_TONE_RULES_H
#define VVFP_SKIN_TONE_RULES_H

#define VVFP_SKIN_TONES_DLL "VVFP Skin Tones.dll"
#define VVFP_SKIN_TONE_COUNT 10
#define VVFP_SKIN_TONE_NONE 0
#define VVFP_SKIN_TONE_GAMES_OWN 15
#define VVFP_SKIN_TONE_WORD "skin tone"         /* "Old skin tone" / "New skin tone" in "Appearance changed" */
#define VVFP_SKIN_TONE_GAMES_OWN_NAME "Game's own"

/* Each tone's own name, light to dark (src/vv_skin_tones.py TONE_TABLE). */
#define VVFP_SKIN_TONE_NAMES { \
    "Porcelain", "Fair", "Light golden", "Light olive", "Copper", "Warm brown", "Medium brown", "Deep brown", \
    "Dark", "Ebony" }

/* A newborn's tone.  `father`, `mother`: 1..COUNT, anything else for not known.  r100, r3 and rn are the
   rolls rand(100), rand(3) and rand(COUNT), any unsigned numbers.  Always 1..COUNT. */
static __inline int vvfp_skin_tone_inherit(int father, int mother, unsigned int r100, unsigned int r3,
                                           unsigned int rn) {
    int tone;
    if (father < 1 || father > VVFP_SKIN_TONE_COUNT) {
        father = 0;
    }
    if (mother < 1 || mother > VVFP_SKIN_TONE_COUNT) {
        mother = 0;
    }
    if (r100 % 100u < 5u || (father == 0 && mother == 0)) {
        return (int)(rn % (unsigned int)VVFP_SKIN_TONE_COUNT) + 1;
    }
    if (father == 0) {
        father = mother;
    }
    if (mother == 0) {
        mother = father;
    }
    tone = (father + mother) / 2 + (int)(r3 % 3u) - 1;
    return tone < 1 ? 1 : tone > VVFP_SKIN_TONE_COUNT ? VVFP_SKIN_TONE_COUNT : tone;
}

#endif /* VVFP_SKIN_TONE_RULES_H */
