/* Prove the publisher keeps exactly ONE mapping handle.
 *
 * Codex reported that vv_village_publish opened a new handle on every call and
 * never closed one, while its comment claimed a single process-lifetime handle.
 * That is one leaked kernel handle per save, and the owner plays long sessions
 * with frequent saves.
 *
 * The leak is invisible to a functional test -- publishing and recalling work
 * perfectly either way -- so it is measured directly from the process handle
 * count instead.
 */
#include <stdio.h>
#include <string.h>
#include <windows.h>

#include "village_identity.h"

int main(void) {
    DWORD before = 0;
    DWORD after = 0;
    char out[VV_VILLAGE_NAME_MAX + 32];
    int i;
    int failures = 0;

    printf("village handle harness\n\n");

    /* Publish once first, so the one legitimate handle is already open and is
       not counted as growth. */
    vv_village_publish("Village: Kalahuna Tribe 5 (Save 1)\n");
    GetProcessHandleCount(GetCurrentProcess(), &before);

    /* A long session's worth of saves. */
    for (i = 0; i < 500; ++i) {
        char header[VV_VILLAGE_NAME_MAX + 32];
        sprintf(header, "Village: Kalahuna Tribe 5 (Save %d)\n", (i % 5) + 1);
        vv_village_publish(header);
    }
    GetProcessHandleCount(GetCurrentProcess(), &after);

    printf("  handles before 500 publishes: %lu\n", (unsigned long)before);
    printf("  handles after  500 publishes: %lu\n", (unsigned long)after);

    if (after > before) {
        printf("  FAIL leaked %lu handles over 500 publishes\n",
               (unsigned long)(after - before));
        failures++;
    } else {
        printf("  ok   no handle growth across 500 publishes\n");
    }

    /* And the mapping must still work after all that reuse. */
    if (vv_village_recall(out, sizeof out)
        && strcmp(out, "Village: Kalahuna Tribe 5 (Save 5)\n") == 0) {
        printf("  ok   the reused mapping still carries the latest village\n");
    } else {
        printf("  FAIL the reused mapping lost its contents (got \"%s\")\n", out);
        failures++;
    }

    printf("\n%s (%d failure%s)\n",
           failures == 0 ? "PASS" : "FAIL",
           failures, failures == 1 ? "" : "s");
    return failures != 0;
}
