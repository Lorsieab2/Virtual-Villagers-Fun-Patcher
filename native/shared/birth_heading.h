/* A Birth record's first line in the Births and Conceptions log.

   From v1.35.66 Birth records are numbered like Conceptions: "Birth <n>", the
   running count across every numbered file of the game's log (the owner,
   2026-10-09: "for convenience like conceptions"). Older logs say just
   "Birth", and Repair Saves & Logs numbers those only when the player asks
   (src/vv_log_additions.py), so every reader takes both.

   `line` may still carry its line ending ("\r\n" or "\n"); nothing else may
   follow the number. Header-only and CRT-free, so both the Parentage Export
   and the VV1 Parentage companion can include it. */
#ifndef VVFP_BIRTH_HEADING_H
#define VVFP_BIRTH_HEADING_H

static int vv_is_birth_heading(const char *line) {
    const char *p;
    if (line == 0 || line[0] != 'B' || line[1] != 'i' || line[2] != 'r' || line[3] != 't'
        || line[4] != 'h') {
        return 0;
    }
    p = line + 5;
    if (*p == ' ') {
        ++p;
        if (*p < '0' || *p > '9') {
            return 0;
        }
        while (*p >= '0' && *p <= '9') {
            ++p;
        }
    }
    if (*p == '\r') {
        ++p;
    }
    if (*p == '\n') {
        ++p;
    }
    return *p == '\0';
}

#endif
