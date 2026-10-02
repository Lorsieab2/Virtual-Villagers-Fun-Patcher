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
#define CE_NAME_BYTES 24            /* a villager name (the shortest game field holds 23) */
#define CE_SKILLS 6
#define CE_SPAWN_PREFS 3
#define CE_MAX_SPAWN_GROUPS 8
#define CE_MAX_SPAWN_COUNT 20       /* new villagers of one kind */
#define CE_MAX_CHANGES 256

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

enum { CE_FATE_NONE = 0, CE_FATE_KILL = 1, CE_FATE_VANISH = 2 };
/* ce_change.litter: 0 no change, 1..3 babies, CE_LITTER_CANCEL not pregnant. */
#define CE_LITTER_CANCEL (-1)
#define CE_MAX_VALUES 16
#define CE_MAX_PUZZLES 32
#define CE_MAX_REVIVES 256
enum { CE_AMOUNT_NONE = 0, CE_AMOUNT_ADD = 1, CE_AMOUNT_SUBTRACT = 2, CE_AMOUNT_ZERO = 3 };
enum { CE_TITLE_KEEP = 0, CE_TITLE_SET = 1, CE_TITLE_CLEAR = 2 };
#define CE_MAX_AMOUNT 1000000

/* One kind of new villager.  `count` of them are made. */
typedef struct {
    int count;
    int sex;                         /* STORY_SEX_MALE / STORY_SEX_FEMALE */
    int age;                         /* game age units */
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
} ce_choice;

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
} ce_result;

#endif
