/* Custom Island Event: the event the player builds, and what each game
   offers.  Included by vvfp_story_upgrades.c.

   The owner: "Custom Island Event -- Allows the player to create and trigger
   a custom Island Event for storytelling, testing, sandbox play, or cheats.
   ... available options must be determined separately for VV1, VV2, VV3,
   VV4, and VV5 from each game's actual executable/data structures ...
   Unsupported properties should be omitted or disabled rather than
   approximated."

   So every option is a capability bit that a game's adapter sets only for
   what that game's own code was traced to support (see the story_c*.inc
   files and docs/story-cheat-upgrades.md); the dialogs disable everything
   else and say why. */
#ifndef VVFP_STORY_CUSTOM_H
#define VVFP_STORY_CUSTOM_H

/* "No change" for an integer field. */
#define CE_KEEP (-1000000)

#define CE_TITLE_BYTES 48           /* the event's own title */
#define CE_TEXT_BYTES 600           /* the event's description */
#define CE_NAME_BYTES 28            /* a villager name: the longest game field (A New Home's
                                       0x1C, NUL included); each game takes its own */
#define CE_SKILLS 6
#define CE_SPAWN_PREFS 3
#define CE_MAX_SPAWN_GROUPS 8
#define CE_MAX_CHANGES 256
#define CE_MAX_RECORDS 256          /* the most villager records any build has */

/* Capabilities. */
#define CAP_FOOD        0x00000001u
#define CAP_TECH        0x00000002u
#define CAP_REFILL      0x00000004u
#define CAP_SPAWN       0x00000008u
#define CAP_KILL        0x00000010u
#define CAP_VANISH      0x00000020u
#define CAP_SICK        0x00000040u
#define CAP_PREGNANT    0x00000080u
#define CAP_PREFS       0x00000100u
#define CAP_APPEARANCE  0x00000200u
#define CAP_SKILLS      0x00000400u
#define CAP_PARENTS     0x00000800u
#define CAP_TITLE       0x00001000u
#define CAP_MASK        0x00002000u
#define CAP_STATUS      0x00004000u   /* faction / special status list */
#define CAP_BEHAVIOUR   0x00008000u
#define CAP_VILLAGE     0x00010000u   /* village / puzzle state list */
#define CAP_SPAWN_NAME  0x00020000u
#define CAP_SPAWN_FACTION 0x00040000u
#define CAP_MALE_PREGNANCY 0x00080000u
#define CAP_VALUES      0x00100000u   /* food sources and stores set to an amount */
#define CAP_PUZZLES     0x00200000u   /* puzzles marked solved / unsolved */
#define CAP_CANCEL      0x00400000u   /* "0 babies": a pregnancy ends */
#define CAP_RELITTER    0x00800000u   /* an existing pregnancy's babies changed */
#define CAP_UNBORN      0x01000000u   /* the unborn baby's father */
#define CAP_REVIVE      0x02000000u   /* skeletons revived */
#define CAP_CHOICE      0x04000000u   /* a question with two choices (the game's own
                                         two-button popup is hooked) */
#define CAP_FAITH       0x08000000u   /* a villager's faith set (New Believers) */
#define CE_FAITH_MIN (-100)           /* the range the game's own SetFaith keeps */
#define CE_FAITH_MAX 100

enum { CE_FATE_NONE = 0, CE_FATE_KILL = 1, CE_FATE_VANISH = 2 };
/* ce_change.litter: 0 no change, 1..3 babies, CE_LITTER_CANCEL not pregnant. */
#define CE_LITTER_CANCEL (-1)
#define CE_MAX_VALUES 16
#define CE_MAX_PUZZLES 32
#define CE_MAX_REVIVES 256
enum { CE_AMOUNT_NONE = 0, CE_AMOUNT_ADD = 1, CE_AMOUNT_SUBTRACT = 2, CE_AMOUNT_ZERO = 3 };
enum { CE_TITLE_KEEP = 0, CE_TITLE_SET = 1, CE_TITLE_CLEAR = 2 };
/* Food and tech points are the game's own 32-bit stores.  An amount, and
   every store or lifetime total the event writes, stays CE_AMOUNT_HEADROOM
   below the 32-bit ceiling, so the game's own gains after the event can
   never wrap it. */
#define CE_AMOUNT_HEADROOM 1000000
#define CE_MAX_AMOUNT (0x7FFFFFFF - CE_AMOUNT_HEADROOM)

/* Health (the owner, 2026-10-10, the simplest method): above 0 alive, 0
   kills -- the game's own death, as "Dies" (a skeleton). */
#define CE_HEALTH_MAX 100

/* Where a parent the player chose comes from (the Parents dialog).  KEEP: no
   change (Villager changes only); UNKNOWN: no parent recorded (a parent the
   villager had is cleared); VILLAGER: a villager of the village, living or a
   body awaiting burial, read when the dialog closes (frozen, as a birth
   records its parents once); JOEY: the default father The Tree of Life and
   New Believers give their seeded pregnancies ("Joey", head 2, body 2: VV4
   0x467C00..0x467C04, VV5 0x471B58..0x471B5C push 2, 2 and the string
   "Joey" before the conception routine); CUSTOM: a typed name and looks. */
enum { CE_PARENT_KEEP = 0, CE_PARENT_UNKNOWN = 1, CE_PARENT_VILLAGER = 2, CE_PARENT_JOEY = 3,
       CE_PARENT_CUSTOM = 4 };
#define CE_JOEY_NAME "Joey"
#define CE_JOEY_FULL_NAME "Joey Joerson"   /* with Last Names (the owner) */
#define CE_JOEY_HEAD 2
#define CE_JOEY_BODY 2

/* One kind of new villager.  `count` of them are made (0 up to the room the
   village has: ce_room_left; the delivery still stops at the game's own room
   predicate). */
typedef struct {
    int count;
    int sex;                         /* STORY_SEX_MALE / STORY_SEX_FEMALE */
    int age;                         /* game age units, 0 .. ce_oldest_age */
    char name[CE_NAME_BYTES];        /* "" = the game's own choice */
    int head;                        /* CE_KEEP = the game's own choice */
    int body;
    int prefs_set;                   /* 1 = likes/dislikes replaced by the lists */
    int likes[CE_SPAWN_PREFS];       /* -1 = none */
    int dislikes[CE_SPAWN_PREFS];
    int skills[CE_SKILLS];           /* CE_KEEP = the game's own choice */
    char title[32];                  /* "" = none */
    int mask;                        /* CE_KEEP = none */
    int faction;                     /* CE_KEEP = the game's own */
    int health;                      /* CE_KEEP = the game's own; 0 = dies at once */
    /* The parents (CAP_PARENTS), recorded as a birth records them: 1 when
       either is chosen.  A name "" with CE_KEEP looks is no parent. */
    int parents_set;
    char father_name[CE_NAME_BYTES];
    char mother_name[CE_NAME_BYTES];
    int father_head;
    int father_body;
    int mother_head;
    int mother_body;
    int father_kind;                 /* CE_PARENT_*, for the dialog when the entry is edited */
    int mother_kind;
    int father_record;               /* CE_PARENT_VILLAGER: the record index chosen, else -1 */
    int mother_record;
} ce_spawn;

/* The changes for one villager. */
typedef struct {
    int index;                       /* the game's record index */
    unsigned int fingerprint;        /* ce_identity of the villager, when queued */
    int fate;                        /* CE_FATE_* */
    int sick;                        /* 1 = falls sick */
    int litter;                      /* 0 = no pregnancy, 1..3 babies */
    int father;                      /* record index of the father, -1 = unknown */
    unsigned int father_fingerprint;
    int head;                        /* CE_KEEP */
    int body;
    int like_add;                    /* -1 = none */
    int like_remove;
    int dislike_add;
    int dislike_remove;
    int skills[CE_SKILLS];           /* CE_KEEP */
    int title_op;                    /* CE_TITLE_* */
    char title[32];
    int mask;                        /* CE_KEEP */
    int status;                      /* CE_KEEP, else an index into the game's status list */
    int behaviour;                   /* CE_KEEP, else an index into the game's behaviour list */
    int parents_set;                 /* 1 = the fields below (those not blank/CE_KEEP) */
    char father_name[CE_NAME_BYTES];
    char mother_name[CE_NAME_BYTES];
    int father_head;
    int father_body;
    int mother_head;
    int mother_body;
    /* The unborn baby's father (CAP_UNBORN), written on a carrier who is
       pregnant once the pregnancies are made: blank / CE_KEEP = no change. */
    int unborn_set;
    char unborn_name[CE_NAME_BYTES];
    int unborn_head;
    int unborn_body;
    int unborn_skill;                /* CE_KEEP, 0 = none, else the game's skill i + 1 */
    int unborn_skill_value;
    int faith;                       /* CAP_FAITH: CE_KEEP, else CE_FAITH_MIN..CE_FAITH_MAX,
                                        written as it is (the faction stays) */
    int health;                      /* CE_KEEP, else 0..CE_HEALTH_MAX: 0 kills */
    int father_kind;                 /* CE_PARENT_*: UNKNOWN clears that parent; KEEP with a
                                        name or looks given sets them (as before) */
    int mother_kind;
    int father_record;               /* CE_PARENT_VILLAGER: the record index chosen, else -1 */
    int mother_record;
} ce_change;

/* A food source or store set to an amount: the adapter's values[which]. */
typedef struct {
    int which;
    int amount;
} ce_value;

/* A puzzle marked solved (1) or unsolved (0): the adapter's puzzles[which]. */
typedef struct {
    int which;
    int solved;
} ce_puzzle;

/* A skeleton brought back to life with `health`, cured when `cure`. */
typedef struct {
    int index;
    unsigned int identity;           /* ce_identity of the skeleton, when queued */
    int health;
    int cure;
} ce_revive;

typedef struct {
    int game;
    char title[CE_TITLE_BYTES];
    char text[CE_TEXT_BYTES];
    int food_op;
    int food_amount;
    int tech_op;
    int tech_amount;
    int refill;
    unsigned int village;            /* bit i = the game's village change i */
    int spawn_groups;
    ce_spawn spawns[CE_MAX_SPAWN_GROUPS];
    int change_count;
    ce_change changes[CE_MAX_CHANGES];
    int value_count;
    ce_value values[CE_MAX_VALUES];
    int puzzle_count;
    ce_puzzle puzzles[CE_MAX_PUZZLES];
    int revive_count;
    ce_revive revives[CE_MAX_REVIVES];
} ce_event;

/* ---- Two-choice events ------------------------------------------------------

   The owner: "I want the player to be able to choose the outcomes.  Some
   buttons should have a chance of multiple outcomes too."

   The event's own ce_event holds the title and the QUESTION (its text) and
   no changes.  Each of the two buttons has a label and 1..CE_MAX_OUTCOMES
   outcomes; when the button is clicked one outcome is rolled, weighted by
   the chances, and its ce_event (`effects`: its text is the RESULT text, its
   title is unused) is applied exactly as a plain custom event is.  Kept in
   static storage only: a ce_choice is about half a megabyte. */
#define CE_MAX_OUTCOMES 4
#define CE_BUTTON_BYTES 40              /* a button label, NUL included (New Believers: 38) */
#define CE_MAX_CHANCE 100               /* chances are weights 1..CE_MAX_CHANCE */
#define CE_LABEL_DEFAULT_WIDTH 12       /* a label's characters when the adapter sets none */

typedef struct {
    int chance;                          /* 1..CE_MAX_CHANCE, a weight */
    ce_event effects;                    /* effects.text = the result text */
} ce_outcome;

typedef struct {
    int enabled;                         /* 1 = the event asks the question */
    char labels[2][CE_BUTTON_BYTES];
    int outcome_count[2];                /* 1..CE_MAX_OUTCOMES each */
    ce_outcome outcomes[2][CE_MAX_OUTCOMES];
    /* The villager in the popup's picture: record index + 1 (0 = a random
       living villager) and that villager's ce_identity, taken when the event
       is queued; the pick is shown only while the record still holds them. */
    int featured_record;
    unsigned int featured_identity;
} ce_choice;

/* Why a change could not be made, for the popup's closing lines: every
   refusal is counted under one of these (ce_refuse), worded by ce_why_words. */
enum {
    CE_WHY_OTHER = 0,          /* the game's own rules did not allow it */
    CE_WHY_PREFS_FULL,         /* a likes or dislikes list was full */
    CE_WHY_EXPECTING,          /* already expecting */
    CE_WHY_NOT_EXPECTING,      /* not expecting */
    CE_WHY_HEATHEN,            /* a Heathen is never sick and never conceives */
    CE_WHY_CHIEF,              /* a Tribal Chief already lives */
    CE_WHY_TOTEMS,             /* no totem or record left for another Esteemed Elder */
    CE_WHY_PUZZLE,             /* a puzzle could not be changed that way now */
    CE_WHY_AMOUNT,             /* a food source or store could not be set now */
    CE_WHY_VILLAGE,            /* a village change was not possible now */
    CE_WHY_REVIVE,             /* a skeleton could not be brought back */
    CE_WHY_TITLE,              /* a custom title could not be saved */
    CE_WHY_PARENTS,            /* parents could not be changed */
    CE_WHY_SHOW_PARENTS,       /* A New Home: parents need Show Parents in Details Screen */
    CE_WHY_MASK,               /* a mask could not be set */
    CE_WHY_BEHAVIOUR,          /* the villager could not do that now */
    CE_WHY_COUNT
};

/* What the delivery did, for the popup's closing lines and the tests. */
typedef struct {
    int changed;          /* villagers changed */
    int skipped;          /* villagers gone or replaced since the event was queued */
    int died;
    int vanished;
    int conceived;        /* babies conceived */
    int no_room_babies;   /* babies refused: the village is full */
    int born;             /* new villagers made */
    int no_room_spawns;   /* new villagers refused: the village is full */
    int refused;          /* individual changes refused by the game's own rules */
    int food_before;
    int food_after;
    int tech_before;
    int tech_after;
    int revived;          /* skeletons brought back */
    int no_room_revives;  /* revivals refused: the village is full */
    int why[CE_WHY_COUNT]; /* `refused`, by reason (CE_WHY_*) */
} ce_result;

#endif
