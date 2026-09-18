/* Exercise the publish/recall handoff that carries the village to the
 * parentage log.
 *
 * This is the part of the feature that can silently do nothing: publish and
 * recall both return void or a flag, both fail quietly by design, and the two
 * run at completely different times in a real game. A handoff that never
 * connects would look exactly like a village that was never saved, and the
 * parentage log would simply keep printing no header while every other check
 * stayed green.
 */
#include <stdio.h>
#include <string.h>

#include "village_identity.h"

static int failures = 0;

static void check(int condition, const char *what) {
    printf("%s %s\n", condition ? "  ok  " : "  FAIL", what);
    if (!condition) {
        failures++;
    }
}

int main(void) {
    char out[VV_VILLAGE_NAME_MAX + 32];

    printf("village share harness\n\n");

    /* Nothing published yet. This must be a clean "no", not a stale hit from
       another run -- the block is scoped to this process, so a previous run
       cannot leak into this one. */
    check(!vv_village_recall(out, sizeof out),
          "recall before any publish reports nothing");
    check(out[0] == '\0', "and leaves the buffer empty");

    vv_village_publish("Village: Testificate!!! (Save 3)\n");
    check(vv_village_recall(out, sizeof out),
          "recall after publish recovers a header");
    check(strcmp(out, "Village: Testificate!!! (Save 3)\n") == 0,
          "and it is the exact header that was published");
    if (strcmp(out, "Village: Testificate!!! (Save 3)\n") != 0) {
        printf("       got \"%s\"\n", out);
    }

    /* Saving a different village must replace the first, not append to it or
       leave the old one visible. The owner switches between villages in one
       sitting, so a stale header would mislabel the next village's log. */
    vv_village_publish("Village: HeathenParentSave1.0 (Save 5)\n");
    vv_village_recall(out, sizeof out);
    check(strcmp(out, "Village: HeathenParentSave1.0 (Save 5)\n") == 0,
          "a later publish replaces the earlier village");

    /* A shorter header must not leave the tail of a longer one behind. */
    vv_village_publish("Save 2\n");
    vv_village_recall(out, sizeof out);
    check(strcmp(out, "Save 2\n") == 0,
          "a shorter header does not leave the previous tail behind");
    if (strcmp(out, "Save 2\n") != 0) {
        printf("       got \"%s\"\n", out);
    }

    /* Publishing nothing is how an unidentified village is represented. */
    vv_village_publish("");
    check(!vv_village_recall(out, sizeof out),
          "an empty publish reads back as nothing to print");

    /* A caller that hands over a null must not fault inside the game's save. */
    vv_village_publish(NULL);
    check(1, "a null publish does not fault");

    /* A small destination must be bounded, not overrun. */
    {
        char small[8];
        vv_village_publish("Village: Kalahuna Tribe 4 (Save 1)\n");
        vv_village_recall(small, sizeof small);
        check(strlen(small) == 7, "a small destination is filled to its bound");
        check(strncmp(small, "Village", 7) == 0, "with the leading bytes");
    }

    printf("\n%s (%d failure%s)\n",
           failures == 0 ? "PASS" : "FAIL",
           failures, failures == 1 ? "" : "s");
    return failures != 0;
}
