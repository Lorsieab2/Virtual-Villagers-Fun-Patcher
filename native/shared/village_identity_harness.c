/* Exercise the village identity reader against synthetic save blocks.
 *
 * This validates the CODE PATH, not the offsets -- the offsets were measured
 * against 348 real saves and confirmed by the owner against the running games.
 * What this catches is the class of mistake a harness can catch: a bias applied
 * twice or not at all, a name truncated at the wrong length, a plausibility
 * filter that rejects the real names this owner actually uses, and a header
 * that degrades wrongly when half the identity is missing.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "village_identity.h"

static int failures = 0;

static void check(int condition, const char *what) {
    printf("%s %s\n", condition ? "  ok  " : "  FAIL", what);
    if (!condition) {
        failures++;
    }
}

static void check_str(const char *got, const char *want, const char *what) {
    int same = strcmp(got, want) == 0;
    if (!same) {
        printf("  FAIL %s (got \"%s\", want \"%s\")\n", what, got, want);
        failures++;
    } else {
        printf("  ok   %s -> \"%s\"\n", what, got);
    }
}

/* The largest block any game needs: VV5's buffer is 0x17D78, plus the +8 bias
   and room past the name. */
#define BLOCK_SIZE (0x18000 + 0x100)

/* Build a manager block with `name` planted where game_id keeps it. */
static unsigned char *make_block(int game_id, const char *name) {
    unsigned char *block = (unsigned char *)calloc(BLOCK_SIZE, 1);
    unsigned int offset = vv_village_name_offset(game_id);
    if (block == NULL) {
        return NULL;
    }
    memset(block, 0xAB, BLOCK_SIZE);          /* structural noise around it */
    memcpy(block + 8 + offset, name, strlen(name) + 1);
    return block;
}

int main(void) {
    /* Real names from the owner's own saves, including the awkward ones. A
       filter tuned to tidy names would reject these, which is exactly the
       failure worth guarding against. */
    static const char *NAMES[5] = {
        "Kalahuna Tribe 1",
        "Testificate!!!",
        "Kalahuna Tribe 3: N",
        "KFT 4 2",
        "HeathenParentSave1.0"
    };
    char out[VV_VILLAGE_NAME_MAX];
    char header[VV_VILLAGE_NAME_MAX + 32];
    int game;

    printf("village identity harness\n");

    printf("\nper-game read at the measured offset:\n");
    for (game = 1; game <= 5; ++game) {
        unsigned char *block = make_block(game, NAMES[game - 1]);
        if (block == NULL) {
            printf("  FAIL allocation for VV%d\n", game);
            failures++;
            continue;
        }
        if (!vv_village_name(game, block, out)) {
            printf("  FAIL VV%d did not read a name\n", game);
            failures++;
        } else {
            char label[32];
            sprintf(label, "VV%d", game);
            check_str(out, NAMES[game - 1], label);
        }
        free(block);
    }

    printf("\nthe bias is applied exactly once:\n");
    {
        /* Planting the name at the raw offset WITHOUT the +8 must not read, or
           the reader is missing its bias; planting at +16 must not read either,
           or it is applying the bias twice. */
        /* The probe must be SHORTER than the 8-byte bias, or it overlaps the
           position the reader looks at and the reader legitimately finds its
           own tail -- which is a defect in the probe, not in the reader. An
           earlier 10-byte probe failed here for exactly that reason. */
        unsigned char *block = (unsigned char *)calloc(BLOCK_SIZE, 1);
        memset(block, 0xAB, BLOCK_SIZE);
        memcpy(block + vv_village_name_offset(5), "Wrong", 6);
        check(!vv_village_name(5, block, out),
              "a name at the unbiased offset is not accepted");
        free(block);

        block = (unsigned char *)calloc(BLOCK_SIZE, 1);
        memset(block, 0xAB, BLOCK_SIZE);
        memcpy(block + 16 + vv_village_name_offset(5), "WrongPlace", 11);
        check(!vv_village_name(5, block, out),
              "a name at twice the bias is not accepted");
        free(block);
    }

    printf("\nthe games do not share an offset:\n");
    {
        /* VV3, VV4 and VV5 all keep the name near the end of their buffers, at
           offsets within 0xC60 of each other. Reading one game's save with
           another game's offset must not silently succeed. */
        unsigned char *block = make_block(5, "OnlyInVV5");
        check(vv_village_name(5, block, out) && strcmp(out, "OnlyInVV5") == 0,
              "VV5 reads its own name");
        check(!vv_village_name(4, block, out),
              "VV4's offset does not find VV5's name");
        check(!vv_village_name(3, block, out),
              "VV3's offset does not find VV5's name");
        free(block);
    }

    printf("\nrefusals:\n");
    check(!vv_village_name(0, NULL, out), "game 0 is refused");
    check(!vv_village_name(6, NULL, out), "game 6 is refused");
    check(!vv_village_name(1, NULL, out), "a null manager is refused");
    {
        unsigned char *block = make_block(1, "");
        check(!vv_village_name(1, block, out),
              "an empty name reports nothing rather than an empty header");
        free(block);
    }
    {
        /* Control bytes are what uninitialised memory looks like. */
        unsigned char *block = (unsigned char *)calloc(BLOCK_SIZE, 1);
        memset(block, 0xAB, BLOCK_SIZE);
        memcpy(block + 8 + vv_village_name_offset(1), "Bad\x01Name", 9);
        check(!vv_village_name(1, block, out),
              "a control byte in the name is refused, not printed");
        free(block);
    }

    printf("\nthe name is bounded:\n");
    {
        /* An unterminated run must stop at the buffer, not walk. */
        unsigned char *block = (unsigned char *)calloc(BLOCK_SIZE, 1);
        memset(block, 'A', BLOCK_SIZE);
        check(vv_village_name(1, block, out),
              "an unterminated run still returns");
        check(strlen(out) == VV_VILLAGE_NAME_MAX - 1,
              "an unterminated run is cut at the bound");
        free(block);
    }

    printf("\nheader assembly:\n");
    vv_village_header(header, sizeof header, "KFT 4 2", 3);
    check_str(header, "Village: KFT 4 2 (Save 3)\n", "both halves");
    vv_village_header(header, sizeof header, "KFT 4 2", 0);
    check_str(header, "Village: KFT 4 2\n", "name only");
    vv_village_header(header, sizeof header, "", 2);
    check_str(header, "Save 2\n", "slot only");
    check(!vv_village_header(header, sizeof header, "", 0),
          "neither half gives no header at all");
    check(header[0] == '\0', "and leaves the buffer empty");

    printf("\n%s (%d failure%s)\n",
           failures == 0 ? "PASS" : "FAIL",
           failures, failures == 1 ? "" : "s");
    return failures != 0;
}
