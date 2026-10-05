/* Village rename notes -- how a log keeps following a renamed tribe.
 *
 * WHY THIS EXISTS
 * ---------------
 * The patcher's Rename Tribe tool (src/vv_tribe_rename.py) changes the tribe
 * name inside a closed game's save. Several logs are bound to their village
 * by the header line the exporter wrote when the file was new:
 *
 *     Village: <name> (Save <n>)
 *
 * The Births and Conceptions, Deaths and Unaccounted Villagers logs are
 * appended to only while that header names the village being played
 * (parentage_export.c, log_belongs_to_village), and Start Over / the tribe
 * delete removes exactly the files whose header names the village being erased
 * (save_reset.c, log_line_matches). A plain rename would therefore make the
 * next record start a NEW log file under the new name, and a later Start Over
 * leave the old files behind.
 *
 * Old records are never rewritten (the owner's rule), so the header line is
 * left exactly as it was. Instead the tool APPENDS one line to each of the
 * village's logs:
 *
 *     Tribe renamed from <old> to <new> on YYYY-MM-DD
 *
 * and both readers apply such lines, in order, to the header they recovered:
 * a file headed "Village: Old (Save 1)" that later says "Tribe renamed from
 * Old to New on 2026-10-04" belongs to "Village: New (Save 1)". A second
 * rename chains ("... from New to Newer ..."). A line whose <old> is not the
 * name the file currently stands for is ignored, so a stray or hand-typed line
 * can never move a log to some other village.
 *
 * The line is parsed with the current name already known, so a name that
 * itself contains " to " or " on " is never ambiguous: the prefix is
 * "Tribe renamed from <current> to " exactly, and the date is the fixed
 * 10-character tail " on YYYY-MM-DD".
 *
 * Header-only and static, so it is compiled into exactly the two companions
 * that read the headers and no other DLL changes.
 */
#ifndef VV_VILLAGE_RENAME_H
#define VV_VILLAGE_RENAME_H

#include <string.h>

#define VV_RENAME_PREFIX "Tribe renamed from "
#define VV_RENAME_PREFIX_LENGTH (sizeof(VV_RENAME_PREFIX) - 1)
#define VV_RENAME_HEADER_PREFIX "Village: "
#define VV_RENAME_HEADER_PREFIX_LENGTH (sizeof(VV_RENAME_HEADER_PREFIX) - 1)
/* " on YYYY-MM-DD" */
#define VV_RENAME_DATE_TAIL 14u
/* No game accepts a longer name (the index fields are 33 and 21 bytes). */
#define VV_RENAME_NAME_MAX 63u

/* Does `line` (no line ending) start with the rename marker? */
static int vv_rename_is_note(const char *line) {
    return line != NULL
        && strncmp(line, VV_RENAME_PREFIX, VV_RENAME_PREFIX_LENGTH) == 0;
}

/* Apply one rename note to a header.

   `header` is "Village: <name>" or "Village: <name> (Save <n>)" with no line
   ending; `line` is one log line with its line ending removed. When the line
   is "Tribe renamed from <name> to <new> on YYYY-MM-DD" for the header's own
   <name>, the header becomes "Village: <new>" plus the same " (Save <n>)"
   and 1 is returned. Anything else leaves the header untouched and returns
   0. `size` is the capacity of `header`. */
static int vv_rename_apply(char *header, size_t size, const char *line) {
    const char *name;
    const char *suffix;
    const char *scan;
    const char *rest;
    const char *date;
    size_t name_length;
    size_t rest_length;
    size_t new_length;
    size_t suffix_length;
    size_t i;
    char updated[VV_RENAME_HEADER_PREFIX_LENGTH + VV_RENAME_NAME_MAX + 32];

    if (header == NULL || line == NULL || size == 0 || !vv_rename_is_note(line)) {
        return 0;
    }
    if (strncmp(header, VV_RENAME_HEADER_PREFIX, VV_RENAME_HEADER_PREFIX_LENGTH) != 0) {
        return 0;
    }
    name = header + VV_RENAME_HEADER_PREFIX_LENGTH;
    /* The LAST " (Save " marker, as every other reader of the header finds
       the slot, so a name containing "(Save 2)" cannot shadow the real one. */
    suffix = NULL;
    scan = name;
    for (;;) {
        const char *hit = strstr(scan, " (Save ");
        if (hit == NULL) {
            break;
        }
        suffix = hit;
        scan = hit + 1;
    }
    if (suffix != NULL
        && !(suffix[7] >= '1' && suffix[7] <= '9' && suffix[8] == ')' && suffix[9] == '\0')) {
        suffix = NULL;          /* not a slot marker after all */
    }
    if (suffix == NULL) {
        suffix = name + strlen(name);
    }
    name_length = (size_t)(suffix - name);
    suffix_length = strlen(suffix);
    if (name_length == 0) {
        return 0;
    }
    /* "Tribe renamed from " <name> " to " */
    rest = line + VV_RENAME_PREFIX_LENGTH;
    if (strncmp(rest, name, name_length) != 0 || strncmp(rest + name_length, " to ", 4) != 0) {
        return 0;
    }
    rest += name_length + 4;
    rest_length = strlen(rest);
    if (rest_length <= VV_RENAME_DATE_TAIL) {
        return 0;               /* no new name, or no date */
    }
    date = rest + rest_length - VV_RENAME_DATE_TAIL;
    if (strncmp(date, " on ", 4) != 0) {
        return 0;
    }
    for (i = 4; i < VV_RENAME_DATE_TAIL; ++i) {
        char c = date[i];
        if (i == 8 || i == 11) {
            if (c != '-') {
                return 0;
            }
        } else if (c < '0' || c > '9') {
            return 0;
        }
    }
    new_length = rest_length - VV_RENAME_DATE_TAIL;
    if (new_length == 0 || new_length > VV_RENAME_NAME_MAX) {
        return 0;
    }
    for (i = 0; i < new_length; ++i) {
        unsigned char c = (unsigned char)rest[i];
        if (c < 0x20 || c > 0x7E) {
            return 0;           /* only a name a player could have typed */
        }
    }
    if (VV_RENAME_HEADER_PREFIX_LENGTH + new_length + suffix_length + 1 > sizeof(updated)
        || VV_RENAME_HEADER_PREFIX_LENGTH + new_length + suffix_length + 1 > size) {
        return 0;
    }
    memcpy(updated, VV_RENAME_HEADER_PREFIX, VV_RENAME_HEADER_PREFIX_LENGTH);
    memcpy(updated + VV_RENAME_HEADER_PREFIX_LENGTH, rest, new_length);
    memcpy(updated + VV_RENAME_HEADER_PREFIX_LENGTH + new_length, suffix, suffix_length + 1);
    memcpy(header, updated, VV_RENAME_HEADER_PREFIX_LENGTH + new_length + suffix_length + 1);
    return 1;
}

#endif /* VV_VILLAGE_RENAME_H */
