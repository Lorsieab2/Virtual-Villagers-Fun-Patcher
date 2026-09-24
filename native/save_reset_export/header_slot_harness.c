/* Does the reset's header check actually reject the wrong village?
 *
 * The header the sweep uses is whatever the statistics companion last
 * published -- the village most recently SAVED, not necessarily the one being
 * deleted. Passing a stale header would delete the logs of the village the
 * player was playing while leaving the deleted village's intact, which is
 * unrecoverable. Review caught that; this pins it.
 *
 * The function under test is copied rather than linked because the companion
 * it lives in is a DLL with no test entry point, and the copy is kept honest
 * by test_village_history_and_log_folders, which asserts the real one still
 * contains the same checks.
 *
 * Build: scripts/build_header_slot_harness.ps1
 */
#include <windows.h>
#include <string.h>
#include <stdio.h>
static int header_is_for_slot(const char *header, int slot) {
    const char *marker = " (Save ";
    const char *found;
    int value = 0;
    int digits = 0;

    if (header == NULL || slot < 1 || slot > 9) {
        return 0;
    }
    /* The LAST occurrence, so a village whose own name contains the marker
       cannot shadow the real one. */
    found = NULL;
    {
        const char *scan = header;
        for (;;) {
            const char *hit = strstr(scan, marker);
            if (hit == NULL) {
                break;
            }
            found = hit;
            scan = hit + 1;
        }
    }
    if (found == NULL) {
        return 0;
    }
    found += lstrlenA(marker);
    while (*found >= '0' && *found <= '9') {
        value = value * 10 + (*found - '0');
        ++found;
        ++digits;
        if (digits > 2) {
            return 0;       /* not a save number this game can produce */
        }
    }
    if (digits == 0 || *found != ')') {
        return 0;
    }
    return value == slot;
}
int main(void) {
    struct { const char *h; int slot; int want; const char *why; } T[] = {
      {"Village: Kalahuna (Save 1)\n",1,1,"ordinary match"},
      {"Village: Kalahuna (Save 1)\n",2,0,"different slot refused"},
      {"Village: Trick (Save 2) (Save 3)\n",3,1,"LAST marker wins"},
      {"Village: Trick (Save 2) (Save 3)\n",2,0,"shadowing name refused"},
      {"Village: X (Save )\n",1,0,"no digits"},
      {"Village: X (Save 123)\n",1,0,"too many digits"},
      {"Village: X (Save 1\n",1,0,"unterminated"},
      {"Village: X\n",1,0,"no marker"},
      {"",1,0,"empty"},
      {"Village: X (Save 01)\n",1,1,"leading zero still slot 1"},
      {"Village: X (Save 10)\n",1,0,"10 is not 1"},
    };
    int fail=0;
    for (int i=0;i<(int)(sizeof(T)/sizeof(T[0]));++i) {
        int got = header_is_for_slot(T[i].h, T[i].slot);
        if (got != T[i].want) { printf("  FAIL %-28s got %d want %d\n", T[i].why, got, T[i].want); fail++; }
        else printf("  ok   %-28s -> %d\n", T[i].why, got);
    }
    printf("\n%s\n", fail ? "FAILURES" : "all cases pass");
    return fail;
}
