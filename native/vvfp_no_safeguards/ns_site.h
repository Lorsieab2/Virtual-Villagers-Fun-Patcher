/* The site record each game's table uses (ns_vvN.inc), for "VVFP No Safeguards.dll".

   Every site is a plain byte replacement in the game's code, written at start only after ALL of the game's sites
   hold their stock bytes (native/shared/install_sites.h: all of them, or none).  `length` is 1..NS_SITE_MAX; the
   replacement is whole instructions (a conditional jump made unconditional or a run of nops, an immediate changed,
   ...) that leave every register, flag and stack slot the following code reads exactly as the condition's passing
   path would have. */
#ifndef VVFP_NS_SITE_H
#define VVFP_NS_SITE_H

#define NS_SITE_MAX 16

typedef struct {
    unsigned int va;
    unsigned char length;
    unsigned char expect[NS_SITE_MAX];   /* the stock bytes */
    unsigned char bytes[NS_SITE_MAX];    /* what goes there */
} ns_site;

#endif
