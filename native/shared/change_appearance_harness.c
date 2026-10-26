/* Change Appearance reaches every head and body row, in all five games.

   The owner: "all outfits and heads should be selectable in Change Appearance
   regardless" -- the last head row and the last body row of each game's art,
   for both sexes, for a child, an adult and an elder (VV1's Golden Child head
   and body 19 included, and VV3's Tribal Chief body 29).

   Compiled once per game with /DHARNESS_GAME=<1..5>: this file includes that
   game's Origins companion source UNCHANGED and drives its real Change
   Appearance dialog procedure with the arrow buttons' own WM_COMMANDs.  The
   only stand-ins are the Win32 calls a dialog needs a screen for --
   DialogBoxParamA runs the scripted arrow presses and OK against the dialog
   procedure, EndDialog records the result, MessageBoxA answers OK to the head
   genetics warning, and InvalidateRect does nothing -- so nothing is shown and
   no window is touched.

   Where the chooser export needs no game memory (The Lost Children's
   ShowVV2AppearanceChooser, New Believers' ShowAppearanceChooser) the export
   itself is called, so what it WRITES -- the record's head and body, or the
   values it hands back to the exe -- is checked too.  A New Home and The Tree
   of Life write the record from the dialog procedure on every arrow press, so
   the record is checked there.  The Secret City's export reads the mask table
   at the game's fixed addresses first, so its dialog procedure is driven and
   tests/test_change_appearance_all_rows.py checks that the export and the
   exe's cave copy the chosen values through unclamped.

   No file is read or written: no save, no sidecar, no log (the appearance log
   needs the Parentage Export DLL beside the executable, and there is none). */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#ifndef HARNESS_GAME
#error "build with /DHARNESS_GAME=1..5"
#endif

static int h_failures;
static int h_checks;
static INT_PTR h_end_result;
static int h_warnings;
static const UINT *h_script;
static int h_script_len;

static BOOL WINAPI h_EndDialog(HWND window, INT_PTR result) {
    (void)window;
    h_end_result = result;
    return TRUE;
}

static int WINAPI h_MessageBoxA(HWND window, LPCSTR text, LPCSTR caption, UINT flags) {
    (void)window; (void)caption; (void)flags;
    if (text != NULL && strstr(text, "head genetics") != NULL) {
        h_warnings++;
    }
    return IDOK;
}

static BOOL WINAPI h_InvalidateRect(HWND window, const RECT *rect, BOOL erase) {
    (void)window; (void)rect; (void)erase;
    return TRUE;
}

/* Press each scripted button, then OK, against the real dialog procedure.
   Command 0 is no button: it stands for "no second press". */
static INT_PTR h_press(DLGPROC proc, const UINT *script, int len, int press_ok) {
    int i;
    h_end_result = -1;
    for (i = 0; i < len; ++i) {
        proc(NULL, WM_COMMAND, MAKEWPARAM(script[i], BN_CLICKED), 0);
    }
    if (press_ok) {
        proc(NULL, WM_COMMAND, MAKEWPARAM(IDOK, BN_CLICKED), 0);
    }
    return h_end_result;
}

static INT_PTR WINAPI h_DialogBoxParamA(HINSTANCE instance, LPCSTR name, HWND owner,
                                        DLGPROC proc, LPARAM param) {
    (void)instance; (void)name; (void)owner; (void)param;
    return h_press(proc, h_script, h_script_len, 1);
}

#define EndDialog h_EndDialog
#define MessageBoxA h_MessageBoxA
#define InvalidateRect h_InvalidateRect
#define DialogBoxParamA h_DialogBoxParamA

#if HARNESS_GAME == 1
#include "../vv1_origins_icons/vv1_origins_icons.c"
#define H_HEADS 20
#define H_BODIES 20
#elif HARNESS_GAME == 2
#include "../vv2_origins_icons/vv2_origins_icons.c"
#define H_HEADS 30
#define H_BODIES 30
#elif HARNESS_GAME == 3
#include "../vv3_full_mastery_candidate/vv3_full_mastery_candidate.c"
#define H_HEADS 30
#define H_BODIES 30
#elif HARNESS_GAME == 4
#include "../vv4_origins_icons/vv4_origins_icons.c"
#define H_HEADS 30
#define H_BODIES 30
#elif HARNESS_GAME == 5
#include "../vv5_task9_origins/vv5_task9_origins.c"
#define H_HEADS 30
#define H_BODIES 30
#else
#error "HARNESS_GAME must be 1..5"
#endif

#undef EndDialog
#undef MessageBoxA
#undef InvalidateRect
#undef DialogBoxParamA

static void h_check(int ok, const char *what, int sex, int age, int got_head, int got_body,
                    int want_head, int want_body) {
    h_checks++;
    if (!ok) {
        h_failures++;
        printf("FAIL game %d %s sex %d age %d: head %d body %d, wanted head %d body %d\n",
               HARNESS_GAME, what, sex, age, got_head, got_body, want_head, want_body);
    }
}

/* The game's two sexes as its record stores them. */
#if HARNESS_GAME == 1
static const int H_SEXES[2] = { 1, 0 };      /* VV_GENDER_MALE = 1 */
#elif HARNESS_GAME == 2
static const int H_SEXES[2] = { 1, 2 };      /* 1 male, 2 female */
#else
static const int H_SEXES[2] = { 0, 1 };
#endif
/* A child (5), an adult (30) and an elder (60): 20 age units a year. */
static const int H_AGES[3] = { 100, 600, 1200 };

#if HARNESS_GAME == 1 || HARNESS_GAME == 4
/* The dialog writes the live record on every arrow press. */
static unsigned char h_record[0x4000];

static void h_open(int sex, int age, int head, int body) {
    memset(h_record, 0, sizeof h_record);
#if HARNESS_GAME == 1
    *(int *)(h_record + VV_GENDER_OFFSET) = sex;
    *(int *)(h_record + VV_AGE_OFFSET) = age;
#else
    *(int *)(h_record + VV_SEX_OFFSET) = sex;
    *(int *)(h_record + VV_DISPLAY_AGE_OFFSET) = age;
#endif
    *(int *)(h_record + VV_HEAD_OFFSET) = head;
    *(int *)(h_record + VV_CLOTHING_OFFSET) = body;
    /* What ShowOriginsAppearancePicker sets before it opens the dialog; the
       mask is left at (None), which the arrows below never touch. */
    appearance_state.villager = h_record;
    appearance_state.original_head = head;
    appearance_state.original_body = body;
    appearance_state.original_mask = 0;
#if HARNESS_GAME == 1
    appearance_state.male = sex == VV_GENDER_MALE;
    appearance_state.valid_count = 20;           /* as the export sets it */
    appearance_state.head_warned = 0;
#else
    appearance_state.head_count = VV_HEAD_COUNT;  /* as the export sets them */
    appearance_state.body_count = VV_BODY_COUNT;
    appearance_state.sex = sex;
    appearance_state.is_old = age >= VV_OLD_AGE_THRESHOLD;
#endif
}

static void h_case(const char *what, int sex, int age, int head, int body,
                   UINT head_cmd, UINT body_cmd, int want_head, int want_body) {
    UINT script[2];
    int got_head, got_body;
    script[0] = head_cmd;
    script[1] = body_cmd;
    h_open(sex, age, head, body);
    h_press(appearance_dialog, script, 2, 0);
    got_head = *(int *)(h_record + VV_HEAD_OFFSET);
    got_body = *(int *)(h_record + VV_CLOTHING_OFFSET);
    h_check(got_head == want_head && got_body == want_body, what, sex, age,
            got_head, got_body, want_head, want_body);
}

static void h_run(int sex, int age) {
    h_case("left arrow from row 0 writes the last rows", sex, age, 0, 0,
           ID_HEAD_PREV, ID_BODY_PREV, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow reaches the last rows", sex, age, H_HEADS - 2, H_BODIES - 2,
           ID_HEAD_NEXT, ID_BODY_NEXT, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow past the last rows wraps to 0", sex, age, H_HEADS - 1, H_BODIES - 1,
           ID_HEAD_NEXT, ID_BODY_NEXT, 0, 0);
    h_case("left arrow from the last rows steps back one", sex, age, H_HEADS - 1, H_BODIES - 1,
           ID_HEAD_PREV, ID_BODY_PREV, H_HEADS - 2, H_BODIES - 2);
}

#elif HARNESS_GAME == 2
static unsigned char *h_record;
static unsigned char *h_player;

/* The export end to end: it reads the record, runs the chooser, charges and
   writes the record's head and body. */
static void h_case(const char *what, int sex, int age, int head, int body,
                   UINT head_cmd, UINT body_cmd, int want_head, int want_body) {
    UINT script[2];
    int result, got_head, got_body, tech;
    script[0] = head_cmd;
    script[1] = body_cmd;
    memset(h_record, 0, 0x10000);
    *(int *)(h_record + VV2_SEX_OFFSET) = sex;
    *(int *)(h_record + VV_AGE_OFFSET) = age;
    *(int *)(h_record + VV2_HEAD_OFFSET) = head;
    *(int *)(h_record + VV2_BODY_OFFSET) = body;
    *(int *)(h_player + VV2_TECH_BALANCE_OFFSET) = 10000;
    vv2_mask_table_state = -1;     /* no .mtab here: no mask is read or written */
    h_script = script;
    h_script_len = 2;
    result = ShowVV2AppearanceChooser(h_player, h_record, 0);
    got_head = *(int *)(h_record + VV2_HEAD_OFFSET);
    got_body = *(int *)(h_record + VV2_BODY_OFFSET);
    tech = *(int *)(h_player + VV2_TECH_BALANCE_OFFSET);
    h_check(result == 1 && got_head == want_head && got_body == want_body && tech == 5000,
            what, sex, age, got_head, got_body, want_head, want_body);
}

static void h_run(int sex, int age) {
    h_case("left arrow from row 0 writes the last rows", sex, age, 0, 0,
           IDC_HEAD_PREV, IDC_BODY_PREV, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow reaches the last rows", sex, age, H_HEADS - 2, H_BODIES - 2,
           IDC_HEAD_NEXT, IDC_BODY_NEXT, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow past the last rows wraps to 0", sex, age, H_HEADS - 1, H_BODIES - 1,
           IDC_HEAD_NEXT, IDC_BODY_NEXT, 0, 0);
    h_case("opening on the last rows keeps them (one body step back)", sex, age, H_HEADS - 1, H_BODIES - 1,
           IDC_BODY_PREV, 0, H_HEADS - 1, H_BODIES - 2);
}

#elif HARNESS_GAME == 3
/* What ShowVV3AppearanceChooser sets before it opens the dialog. */
static void h_case(const char *what, int sex, int age, int head, int body,
                   UINT head_cmd, UINT body_cmd, int want_head, int want_body) {
    UINT script[2];
    script[0] = head_cmd;
    script[1] = body_cmd;
    vv3_appearance_sex = sex ? 1 : 0;
    vv3_appearance_old = age >= 1100 ? 1 : 0;
    vv3_appearance_head = (head >= 0 && head < VV3_HEAD_COUNT) ? head : 0;
    vv3_appearance_body = (body >= 0 && body < VV3_BODY_COUNT) ? body : 0;
    vv3_appearance_mask = 0;
    h_press(vv3_appearance_dialog, script, 2, 1);
    h_check(h_end_result == 1 && vv3_appearance_head == want_head && vv3_appearance_body == want_body,
            what, sex, age, vv3_appearance_head, vv3_appearance_body, want_head, want_body);
}

static void h_run(int sex, int age) {
    h_case("left arrow from row 0 chooses the last rows", sex, age, 0, 0,
           IDC_HEAD_PREV, IDC_BODY_PREV, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow reaches the last rows", sex, age, H_HEADS - 2, H_BODIES - 2,
           IDC_HEAD_NEXT, IDC_BODY_NEXT, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow past the last rows wraps to 0", sex, age, H_HEADS - 1, H_BODIES - 1,
           IDC_HEAD_NEXT, IDC_BODY_NEXT, 0, 0);
    h_case("opening on the last rows keeps them (one body step back)", sex, age, H_HEADS - 1, H_BODIES - 1,
           IDC_BODY_PREV, 0, H_HEADS - 1, H_BODIES - 2);
}

#else /* HARNESS_GAME == 5 */
/* The export end to end: it hands the chosen rows back to the exe, which
   writes them into the record (build_vv5_task9_native_actions.py). */
static void h_case(const char *what, int sex, int age, int head, int body,
                   UINT head_cmd, UINT body_cmd, int want_head, int want_body) {
    UINT script[2];
    int result, h = head, b = body, m = 0;
    script[0] = head_cmd;
    script[1] = body_cmd;
    h_script = script;
    h_script_len = 2;
    result = ShowAppearanceChooser(sex, age, &h, &b, &m);
    h_check(result == 1 && h == want_head && b == want_body && m == 0,
            what, sex, age, h, b, want_head, want_body);
}

static void h_run(int sex, int age) {
    h_case("left arrow from row 0 hands back the last rows", sex, age, 0, 0,
           IDC_HEAD_PREV, IDC_BODY_PREV, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow reaches the last rows", sex, age, H_HEADS - 2, H_BODIES - 2,
           IDC_HEAD_NEXT, IDC_BODY_NEXT, H_HEADS - 1, H_BODIES - 1);
    h_case("right arrow past the last rows wraps to 0", sex, age, H_HEADS - 1, H_BODIES - 1,
           IDC_HEAD_NEXT, IDC_BODY_NEXT, 0, 0);
    h_case("opening on the last rows keeps them (one body step back)", sex, age, H_HEADS - 1, H_BODIES - 1,
           IDC_BODY_PREV, 0, H_HEADS - 1, H_BODIES - 2);
}
#endif

int main(void) {
    int s, a;
    setvbuf(stdout, NULL, _IONBF, 0);
#if HARNESS_GAME == 2
    h_record = (unsigned char *)VirtualAlloc(NULL, 0x10000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    h_player = (unsigned char *)VirtualAlloc(NULL, 0x40000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (h_record == NULL || h_player == NULL) {
        printf("cannot allocate the record\n");
        return 2;
    }
#endif
    for (s = 0; s < 2; ++s) {
        for (a = 0; a < 3; ++a) {
            h_run(H_SEXES[s], H_AGES[a]);
        }
    }
    printf("game %d: %d heads, %d bodies; %d checks, %d failures, %d head-genetics warnings\n",
           HARNESS_GAME, H_HEADS, H_BODIES, h_checks, h_failures, h_warnings);
    if (h_checks == 0) {
        return 2;
    }
    return h_failures == 0 ? 0 : 1;
}
