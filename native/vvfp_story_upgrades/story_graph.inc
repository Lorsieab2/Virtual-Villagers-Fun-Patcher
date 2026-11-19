/* BRANCHING CUSTOM ISLAND EVENTS, phase 2: the game-side runtime.  Included by vvfp_story_upgrades.c after
   story_queue.inc.

   The owner (v1.35.97): "allow the player to create multiple branching complicated outcome events like I just made
   for Aspiring Adventurer in Custom Island Events".  An event is written in the patcher (src/vv_cie_graph.py: the
   JSON format, every check it must pass, its compiled .cieg and the chances of every outcome) and kept in

       <save folder>\Virtual Villagers Fun Patcher\Custom Island Events\<name>.json + <name>.cieg

   The in-game Custom Island Event dialog's "From the library..." lists the .cieg events made for this game (a
   .cieg with no .json beside it, or an older one, is never offered: the patcher writes both at each save) and
   queues the one picked.  The single-step editor stays as it is.

   READING (cg_load).  A .cieg is read whole (at most CG_MAX_FILE bytes) and checked again here before anything
   uses it: the magic, the version, the header size, the file size, the CRC-32 of the whole file, every section
   inside the file, every index inside its table, every string inside the strings and NUL-ended, every operand of
   a condition after the condition itself (so no condition can loop), the node graph free of cycles, every effect
   one this companion knows with its values in range, and every text made only of the characters the Custom
   Island Event allows (ce_text_char_ok, line breaks) and well-formed placeholders.  A file that fails is refused
   with the reason; it is never partly used.

   ROLES (cg_eligible).  A villager role is filled by a living villager the game lists (the adapter's own test)
   of the role's age or more (20 age units a year in every game), of its sex if it names one, not carrying or
   nursing a baby unless the role allows it (the adapter's own "expecting" field), not one of the game's special
   villagers unless the role allows it -- the ones the shipped Aspiring Adventurer leaves out (native/
   vvfp_more_island_events): A New Home's Golden Child, The Secret City's Tribal Chief (and its stand-in records),
   New Believers' chief, Retired Chief and the puzzles' Heathens (roles 12-17) -- and in New Believers a believer
   unless the role allows Heathens.  Two villager roles are always two villagers: the roles are bound by a
   matching (cg_matchable), so a role is never refused while the village can fill every one.  A stranger has no
   record, only a sex (random when the event says so).  Custom Island Events are exempt from a shipped event's
   natural requirement (the owner): only the roles count.
     * Queueing: when the village cannot fill every role the event needs, the purchase is REFUSED and the message
       says which role and what it needs.  An optional role is planned when the village can fill it then.
     * Delivery: the roles are bound when the event is about to be shown (the game's random routine picks among
       those who fit).  If the village can no longer fill them, the event KEEPS WAITING (ce_held): the island
       event that came is the game's own, and the custom one is made due again once they can be filled
       (ce_opening_tick) -- never run with a role missing.

   THE WALK (cg_walk).  From the start (or each question button), each node's children are resolved as the
   patcher resolves them (a child whose condition fails is its else, or left out; none left: the node's else; no
   children: the end) and one is drawn, weighted, through the adapter's random routine (ce_random_below).
   Conditions: visited, role (bound in this run), game, patch (the patches the companion can see: Guardians of
   Isola's rewrite in New Believers; any other id is off), not / all / any.  Each effect's own roll -- a health in
   its range, which skill and how much -- is made as its node is reached, and a scaled amount is worked out then
   ("Island Events Scale With Population" / "... With Stored Food and Tech Points": their companion's own rule
   when ticked, else the amount as written).  A question's two histories are both walked when it is asked (as the
   shipped event rolls everything when its popup is built), so the popup can be sized for the result it will show.

   EFFECTS WAIT FOR THEIR OWN PAGE (the owner, 2026-11-12).  Each node's effects are made, once, when the page
   showing the end of that node's text is built for the screen -- as the game's own plain island event makes its
   changes while it builds its popup, and as a question's result is built at the click -- so each page says what
   has just happened (cg_layout_history, cg_show): the award with "Your villagers gain ...", a death or a
   disappearance with its ending's last page.  A villager who has died or left by then (old age between pages)
   has that role's later effects skipped; the rest of the event goes on.  Through the adapters: food / tech points through the game's own writers (CE_AMOUNT_ADD / SUBTRACT),
   the award only when paid; "dies" the adapter's death, with the event's cause told to "VVFP Cause of Death.dll"
   ("unknown": nothing, the game's own "Unknown causes"; "custom": VvfpCauseKilled, "Died in a custom island
   event"; the author's words: VvfpCauseKilledBy when that companion has it, else as "custom"); "disappears" the
   adapter's removal with no body, told as VvfpCauseVanishedBy ("Disappeared in <title>") or, with an older
   companion, VvfpCauseVanished -- the Deaths log's Disappeared record; "becomes a Heathen" (New Believers) the
   game's own conversion through the adapter's status 1 (0x4669E0: the bottom bar's line, the Cause of Death
   "Left the tribe" record and the statistics), and counted as a faith conversion: "VVFP Faith Notice.dll"'s
   VvfpFaithNoticeCount adds it to the believers "Popup When Believers Become Heathens" tells of, when that patch
   is on; health, a like or dislike by the game's own word, a skill raised, sickness -- one ce_change each through
   ce_apply, so titles, refusals and their reasons are the plain Custom Island Event's.

   THE POPUPS.  Every popup of a history is laid out in pages that fit the popup it is shown in (the page
   splitting the shipped event uses until the popups can scroll: whole paragraphs where they fit, else whole
   sentences, else words -- never off the screen), measured with the longest names the game holds, so the pages
   are the same whoever the villagers are; each page is then filled with the real names ("(name)" is the record's
   own name, the full name with Last Names on).  A popup that carries villager effects keeps two lines free on each
   page for the "N changes could not be made" lines of that page's own effects.  They are shown one after another,
   each a popup of its own through the game's own trigger:
     * a question: its text's earlier pages first, then the game's two-button popup with the last page;
     * the answer's first page is the result popup the click shows (ce_choice_resolve);
     * every later page through the island-event notice the Time Skip's closing popup uses (story_notice_arm).
   ONE EVENT.  Only the question (or, with no question, the first page) is the island event: it alone counts in
   Island Events Seen; every other page is a notice, whose count is taken back.  The Island Events log
   ("VVFP Island Events.dll") has no event of its own to append to: it writes one numbered record per villager an
   event's popup changed, each headed "Event: <title>", and skips only the Time Skip's notice.  So a later page's
   effects are written as records under the same "Event: <title>" as the first page's (the question's records
   carry its "Choice:" line too); a page that changes nobody writes nothing.  While a run has pages left the event
   slot is its own: no notice, no other custom event comes between.

   A QUIT BETWEEN POPUPS RESUMES, EACH EFFECT EXACTLY ONCE.  The run (where it is, who the roles are, both
   histories, every page with the effects it makes, when each page's were made, and who was gone before it) and
   the .cieg itself are kept beside the queue's file:
       Virtual Villagers N Story Purchases Graph - Save S.dat
   written as the run changes, and kept after its last page until a save holds every page's effects.  It is put
   back, once, for the same village (a majority of its roster) when the slot's save was written after the
   purchase -- the queue's own rule (story_queue.inc) -- from the first page whose effects that save does not hold
   (cg_village_seen): those pages are shown again and make their effects then, the pages the save holds are not.
   The queue file itself never holds a graph's popup (sq_capture leaves it out), so a version 1 queue file is read
   exactly as before.

   FORMAT VERSION 6 (the Isola Grand Event Collection, docs/event-collection/cie-v6-binary.md is the contract):
     * pools of text (`{A}`, `{A.2}`, game words `{@chief}`, inline picks compiled to `{_iN}`): each instance drawn
       once a run in the walk -- per node its effects' rolls, then its text's (and a question's labels') instances
       left to right, depth first, then the child draw -- and kept in the run, so pages and a resume show the same
       words; the pages are laid out with the drawn words (names at their longest, as before);
     * alias roles (drawn among their bound members at the run's start), role requirements (max age, skill, the
       special villager, the highest skill) cast STRICT (the rare roll, Pick Island Event) or PREFER (bought: a
       requirement nobody meets is dropped, never the purchase), and the protected filter: a role that can be harmed
       never takes a nursing parent, the Golden Child, the Tribal Chief or New Believers' story villagers;
     * the hard harm guard: a child whose target harms a protected-filtered role carries a `harmable` guard, checked
       at the walk, so a villager who became protected after the cast is never harmed (that branch is not taken);
     * up to seven answers on ONE page, a choice shown only when its `if` holds (the buttons close up: the run keeps
       each question's button-to-choice map), labels up to 95 bytes;
     * new effects: celebrate (each game's own "Celebrating"), action (an action by its words), mood (good: the
       celebration; bad: "Shaking head"), health_change (clamped 1..100, never kills), skill_set and damage (one
       finished structure loses a share of its building work, native/shared/structure_damage.h);
     * A New Home and The Lost Children draw ; ( ) & % only with the Unicode Text companion: without it they become
       , - - "and" " percent" (cg_glyph_fallback).
   The run's file is version 4 (the picks, the aliases, the maps, answers five to seven); a version 3 or 2 file is
   read with them empty. */

#include "../shared/structure_damage.h"   /* the "damage" effect: The Rumblings' structures */

#define CG_HEADER_BYTES 80u
#define CG_HEADER_V6 96u
#define CG_MAX_POOLS 1000
#define CG_MAX_ITEMS 8000
#define CG_MAX_PICKS 256                /* pool instances a run holds */
#define CG_SEG_PICKS 64                 /* ... an answer's segment holds */
#define CG_MAX_INSTANCE 8               /* {A.1} .. {A.8} */
#define CG_POOL_DEPTH 4                 /* a pool's item may hold another pool's token, this deep at most */
#define CG_LABEL_V6 96                  /* a version 6 label, NUL included (95 bytes) */
#define CG_V4_ANSWERS 4                 /* the answers a run file version 3 kept */
#define CG_NONE 0xFFFFu
#define CG_MAX_FILE 0x1000000u              /* a player's .cieg (16 MiB): the sanity cap; read into memory of its own,
                                              as large as the file (cg_grow), never a buffer this size */
#define CG_SHIPPED_FILE 0x100000u           /* the collection's and the procedural events' own graphs (1 MiB) */
#define CG_MAX_ROLES 16
#define CG_MAX_NODES 1000
#define CG_MAX_PATH 128
#define CG_MAX_FX 64
#define CG_MAX_POPUPS 12
#define CG_MAX_PAGES 24
#define CG_NAME_BYTES 32
#define CG_TEXT_MAX 1990                /* a popup's (and a page's) bytes: the later games build theirs in 2,000 */
#define CG_TEXT_MAX_12 8000             /* ... A New Home's and The Lost Children's ONE popup (their dialogs hold 9,999;
                                           src/vv_cie_graph.py ONE_POPUP_TEXT_MAX_12) */
#define CG_RAW_BYTES CE_LONG_BUF            /* a popup's raw text: with Scrolling Popups up to CE_LONG_TEXT_MAX */
#define CG_PAGE_BYTES (CG_RAW_BYTES + 8)
#define CG_DISPLAY_BYTES 0x100000           /* every display's words of a run (run file version 5; 4 kept 49,152) */
#define CG_DISPLAY_BYTES_V4 49152
#define CG_MAX_DISPLAYS 96
#define CG_CAUSE_BYTES 64               /* a death's own cause words WITHOUT Scrolling Popups, NUL included */
#define CG_LABEL_BYTES CE_BUTTON_BYTES

/* The bytes (NUL included) a death's own cause words may hold: with Scrolling Popups practically any (the owner,
   2026-11-17: the grave's popup scrolls; "VVFP Cause of Death.dll" keeps them whole, its words file version 2), else
   the old 63 characters (src/vv_cie_graph.py CAUSE_BYTES / LONG_LINE_BYTES). */
static int cg_cause_bytes(void) {
    return cg_scrolls() ? CE_LONG_LINE_BYTES : CG_CAUSE_BYTES;
}
#define CG_ENTRY_BYTES 0x20000             /* the run's Island Events log entry: 16 questions' choices of up to
                                              CE_LONG_LINE_BYTES each and every change (run file 5; 4 kept 8,192) */
#define CG_ENTRY_BYTES_V4 8192
#define CG_MAX_QUESTIONS 16             /* questions on one history (src/vv_cie_graph.py MAX_QUESTIONS_PER_RUN) */
#define CG_MAX_ANSWERS 7                /* a question's answers: version 6 two to seven, 4 and 5 two to four, before
                                           exactly two */

/* The text lines a question keeps for its answers past two (src/vv_cie_graph.py answer_room): 1.5 button heights
   (3 lines of 20 px) each up to four answers; from five, 1.25 heights apart (vvfp_multi_answer.h ma_step), the
   first answer's height above the game's own first in lines, rounded up. */
static const int CG_ANSWER_LINES[CG_MAX_ANSWERS + 1] = { 0, 0, 0, 3, 6, 7, 10, 12 };

enum { CGD_PAGE = 0, CGD_RESULT = 1, CGD_QUESTION = 2 };

enum { CG_POPUP = 0, CG_QUESTION = 1, CG_BRANCH = 2 };
enum { CGE_FOOD = 1, CGE_TECH = 2, CGE_PAY = 3, CGE_KILL = 4, CGE_VANISH = 5, CGE_STATUS = 6, CGE_HEALTH = 7,
       CGE_PREF = 8, CGE_SKILL = 9, CGE_SICK = 10,
       /* version 6 */
       CGE_CELEBRATE = 11, CGE_ACTION = 12, CGE_MOOD = 13, CGE_HEALTH_CHANGE = 14, CGE_SKILL_SET = 15,
       CGE_DAMAGE = 16,
       /* cie-v6-binary.md 22 */
       CGE_APPEARANCE = 17, CGE_DIE_UNRECOVERED = 18, CGE_BABY_LOST = 19,
       /* cie-v6-binary.md 23 */
       CGE_BIRTH_THEN_DIE = 20,
       /* cie-v6-binary.md 27 */
       CGE_OLD_LOOK = 21,
       /* cie-v6-binary.md 29 */
       CGE_SEX_CHANGE = 22,
       /* cie-v6-binary.md 31: the gender presentation, set (a = 1) or cleared (a = 0) */
       CGE_PRESENTATION = 23,
       /* cie-v6-binary.md 30 */
       CGE_DELIVER_EARLY = 24,
       /* cie-v6-binary.md 38: The Tree of Life's cutting tools, soap and cloth bolts (25 was reserved) */
       CGE_SUPPLY = 25,
       /* cie-v6-binary.md 32: a story trait kept for the villager (The Quiet Hands: mute), never a change */
       CGE_TRAIT = 26,
       /* cie-v6-binary.md (the data agent documents it): a new villager -- role 255 a random one, else a duplicate of
          the role's villager (sex, head and body copied; name, likes, dislikes and skills the game's own roll) --
          made by each game's own creator (the adapters' spawn: the Barrel's / stranger's path, its room check), a
          the age class (0 any, 1 child, 2 teen, 3 adult, 4 elder).  No room: nothing, no error. */
       CGE_NEW_VILLAGER = 27,
       /* 28 / 29: the role's villager becomes pregnant by the game's own conception (the Custom Island Event's
          chosen-partner path, a->conceive), the partner role in the first value (255 none); 29 delivers at once
          (a->deliver: nursing a newborn).  Flags bit 0: any birth sex (else the carrier was born female); always 18
          or more, never already expecting; no room: nothing. */
       CGE_PREGNANT = 28, CGE_NURSING = 29,
       /* 30: a copy of the role's villager by the game's own twins' copy routine (room asked first), always with a
          name of its own (the game's own name roll; the owner, 2026-11-15).  New Believers' Heathens are never
          copied. */
       CGE_CLONE = 30,
       /* 31: a mind swap (The Lost Children's Crystal Ball): names, skills, likes and dislikes exchanged between the
          role and the role in the first value; looks, sex and age stay.  32: the name becomes "?" (A Bump On The
          Head, The Return of Biggles).  Both hand the renames to the companions that key villagers by name. */
       CGE_BODY_SWAP = 31, CGE_LOSE_NAME = 32,
       /* 33: a real rename -- a first name drawn from the game's own list (either sex), the villager's last name
          kept -- handed to the companions that key villagers by name.  34: the age set or moved (cg_change_age). */
       CGE_CHANGE_NAME = 33, CGE_CHANGE_AGE = 34,
       /* the owner, 2026-11-15 ("do your best to implement the outcomes"): 35 an illness cured (the game's own sick
          field cleared); 36 the damaged structures repaired (one step from done, the game's own construction
          finishes them: native/shared/structure_damage.h sd_repair, story_structures.inc); 37 the young head look
          (Head Look's file, as old_look) */
       CGE_CURE = 35, CGE_REPAIR = 36, CGE_YOUNG_LOOK = 37,
       /* New Believers' Faith, the game's own way (the owner, 2026-11-16; "VV5 Heathen Events - What Vanilla Does"):
          38 Faith +a (1..35) through FAITH_ADD 0x468020 (a Heathen whose Faith ends above 0 joins, the game's rule);
          39 a Heathen joins: SetFaith 0x467F90(20, 1), then 0x466880(0), as The Defector; 40 a believer becomes a
          Heathen by their own choice: SetFaith(-10, 1), then 0x466880(1), as The Spa / The Cracked Mask.  Only in
          New Believers; elsewhere nothing. */
       CGE_FAITH = 38, CGE_JOIN = 39, CGE_APOSTASY = 40,
       /* cie-v6-binary.md 39-41: a trade, a group behaviour, the village (#813's 26-28 moved: round 6 holds them) */
       CGE_TRADE = 41, CGE_GROUP = 42, CGE_VILLAGE = 43 };
/* 34: the mode (the effect's flags byte): set to a child, a teen 14-17, 18, an adult of 20-49, 50 or an elder, or
   move by a number of years drawn in [a, b] (either may be below 0). */
enum { CG_AGE_CHILD = 0, CG_AGE_TEEN = 1, CG_AGE_18 = 2, CG_AGE_ADULT = 3, CG_AGE_50 = 4, CG_AGE_ELDER = 5,
       CG_AGE_ADD = 6 };
#define CG_FX_ANY_BIRTH_SEX 1u          /* 28 / 29: flags bit 0 */
/* 28 / 29: flags bits 1-2, the babies (the owner, 2026-11-15, "if the game allows"; every game's records hold a
   litter of 1 to 3): bit 1 alone the stock multiple-birth roll whatever the tech gate (every game's: a multiple 7 in
   100, of those triplets 25 in 100 -- VV1 0x43BC41 / 0x43BC7F, VV2 0x44BA6A, VV3 0x455B92 / 0x455BB2, VV4
   0x45E893 / 0x45E8B3, VV5 0x465EE3 / 0x465F03), bit 2 alone twins, both triplets; each baby still only while the
   game's own room predicate says there is room (the adapters' conceive). */
#define CG_FX_LITTER_ROLL 2u
#define CG_FX_LITTER_TWINS 4u
/* 28 / 29: flags bit 3, "the partner may carry" (the owner, 2026-11-16): with a partner role, as often as the player's setting says (0 to 100 percent,
   10 unless moved: cg_partner_carry_percent; the game's random routine) the partner carries instead -- of any birth sex -- when they pass the carrier's checks (18
   or more, not expecting already); else the carrier stays.  The carrier is recorded in the mother's place whatever
   their sex, as every carrier is.  Decided once at the cast, the two roles swapped for the whole run so the pages
   name who carries (the owner, 2026-11-18: cg_partner_carry_decide). */
#define CG_FX_PARTNER_MAY_CARRY 8u
static int cg_partner_carries(const ce_adapter *a);   /* the setting's chance (below) */
#define CG_TRAIT_MUTE 1u              /* 32: the story trait "mute" */
#define CG_MUTE_WORD "talking"        /* the owner (2026-11-17): a villager who dislikes it is story-mute */
static const char *cg_pref_word;      /* a preference effect's word given here instead of the graph's (the mute
                                         trait's own dislike) */
#define CG_ROLE_SPEAKS 0x80u          /* 32: a villager role's byte 13 bit: its words have them speak */
#define CG_ROLE_HEATHEN 0x40u         /* ... bit 6: New Believers: the role is a Heathen's (an Isolan), cast as the game's
                                         own picker 0x471870 casts one with Heathens-only on and special roles off */
#define CG_LOOK_RANDOM (-1)           /* an appearance effect's head / body: any row but the current one */
#define CG_LOOK_KEEP (-2)             /* ... not changed */
#define CG_HEADER_REL 104u            /* a version 6 header with the kinship relations (cie-v6-binary.md 21) */
enum { CG_REL_SPOUSE = 1, CG_REL_PARENT = 2, CG_REL_CHILD = 3, CG_REL_SIBLING = 4,
       /* gap C2: through a living villager in between */
       CG_REL_GRANDPARENT = 5, CG_REL_GRANDCHILD = 6, CG_REL_AUNT = 7, CG_REL_COUSIN = 8 };
#define CG_PREF_RANDOM 8u             /* a preference effect's flags: a random like or dislike (cie-v6-binary.md 24) */
#define CG_PREF_REMOVE 16u            /* ... the like or dislike is taken away (the named one, or with CG_PREF_RANDOM
                                         one the villager holds); held nowhere: nothing (the owner, 2026-11-15) */
#define CG_NODE_AUTO_TEXT 1u          /* a node's flags (byte 3): its effects told in automatic lines (24) */
#define CG_NODE_NEW_PAGE 2u           /* ... 19a: with Scrolling Popups, starts the event's one popup afresh */
#define CG_NODE_SOLIDARITY 12u        /* ... bits 2-3: the page's Village Solidarity tag, any version (patcher-read) */
enum { CGC_VISITED = 1, CGC_ROLE = 2, CGC_GAME = 3, CGC_PATCH = 4, CGC_NOT = 5, CGC_ALL = 6, CGC_ANY = 7,
       CGC_PUZZLE = 8,                /* version 3: a = the puzzle's name, b = its game (the requirement) */
       /* version 6: the runtime facts */
       CGC_HARMABLE = 9, CGC_SPECIAL_PRESENT = 10, CGC_MIN_POPULATION = 11, CGC_MIN_CHILDREN = 12,
       /* cie-v6-binary.md 8: a bound villager's facts, and a pool instance's draw */
       CGC_AGE = 13, CGC_SKILL_AT_LEAST = 14, CGC_HAS_LIVING_CHILD = 15, CGC_DREW = 16,
       CGC_HAS_DEAD_RELATIVE = 17,    /* cie-v6-binary.md 21a */
       CGC_IS_SPECIAL = 18,           /* 37: the role's villager is the game's special one (the Golden Child,
                                         The Secret City's Tribal Chief) */
       CGC_HAS_SUPPLY = 19 };         /* cie-v6-binary.md 39: a = the good's word, the next H = at least */
/* story_graph_village.inc (cie-v6-binary.md 39-41), used by the loader and the walk before it is included. */
static int cg_good_word(const char *word);
static int cg_has_good(int game, const char *word, int n);
static int cg_group_kind_ok(const char *kind, int whole_village);
static int cg_village_ok(const char *s, int a, int b);
/* A role's byte 9 (cie-v6-binary.md 2): 1-3 the role MUST be that villager; 4 and 5 (35) the role PREFERS it: when
   the Golden Child (4) or the Tribal Chief (5) may take the role, they are cast; else any villager the role takes. */
enum { CG_SPECIAL_GOLDEN = 1, CG_SPECIAL_CHIEF = 2, CG_SPECIAL_NURSING = 3, CG_PREFER_GOLDEN = 4,
       CG_PREFER_CHIEF = 5 };
#define CG_POOL_DISTINCT 1u           /* a pool's flags: distinct (cie-v6-binary.md 4) */
#define CG_POOL_LINKED 2u             /* ... 35: a linked pool draws the item number a linked pool drew first */
enum { CG_ROLE_VILLAGER = 0, CG_ROLE_STRANGER = 1, CG_ROLE_ALIAS = 2,
       CG_ROLE_OTHER = 3 };            /* G2: the member of a two-member alias that the alias did not draw */
#define CG_POOL_TRIBE (-2)            /* G5: {@tribe}, built in (no pool): the tribe's name at run time */
#define CG_POOL_TRIBE_CAP (-3)        /* {@Tribe} */
/* The origin of a queued run (story_collection.inc, Pick Island Event, the library) and its casting. */
#define CG_ORIGIN_PURCHASE 0
#define CG_ORIGIN_PICK 1
#define CG_ORIGIN_NATURAL 2
#define CG_CAST_STRICT 0              /* every requirement must hold (the rare roll, Pick Island Event) */
#define CG_CAST_PREFER 1              /* a requirement nobody meets is dropped (bought through the library) */
#define CG_ROLE_ALIAS_ALL 0xFFu       /* an effect's role byte: every living, listed villager (celebrate) */
/* The owner, 2026-11-15: an effect's role byte may also be a GROUP (254: the effect's byte 3 the selector, its last
   H the selector's value) or a villager this event has just made (253 the newest, 252 the one before it: made by a
   new_villager or clone effect earlier on the same page). */
#define CG_ROLE_GROUP 0xFEu
#define CG_ROLE_NEWEST 0xFDu
#define CG_ROLE_NEWEST2 0xFCu
enum { CG_GROUP_ALL = 1,              /* every living, listed villager (New Believers: its believers) */
       CG_GROUP_SKILL = 2,            /* ... whose skill named by the string at the last H is at least 50 */
       CG_GROUP_RANDOM = 3,           /* ... N of them drawn (N at the last H, 1..255; fewer: all there are) */
       CG_GROUP_ELDERS = 4,           /* ... every elder, 55 or more */
       CG_GROUP_CHILDREN = 5,         /* ... every child, under 14 */
       CG_GROUP_TEENS = 6,            /* ... every teen, 14 to 17 */
       CG_GROUP_ADULTS = 7 };         /* ... every adult, 18 or more */
#define CG_GROUP_SKILL_MIN 50
#define CG_SKILL_BEST 32u             /* skill / skill_set flags: the villager's own highest skill, not the list's */
#define CG_NEW_CHILD_OF_NEWEST 1u     /* new_villager flags: its parents are the two newest (253, 252); it does not
                                         become the newest itself, so brothers and sisters share them */
/* CG_DONE: every page shown, the file kept until a save holds the last page's effects (a crash before it must
   neither lose nor repeat them). */
enum { CG_IDLE = 0, CG_QUEUED = 1, CG_PRE = 2, CG_ASKED = 3, CG_CHAIN = 4, CG_DONE = 5 };
enum { CG_ROLE_OPTIONAL = 1, CG_ROLE_NURSING = 2, CG_ROLE_SPECIAL = 4, CG_ROLE_BELIEVERS = 8,
       CG_ROLE_HARM = 16, CG_ROLE_PROTECTED = 32 };
#define CG_STRANGER_NAMED 1u          /* a stranger's flags: named (cie-v6-binary.md 16) */
#define CG_STRANGER_NEW_NAME 2u       /* ... a new name for the villager role in its mask (cie-v6-binary.md 28) */
enum { CG_NEW_SEX_SAME = 4, CG_NEW_SEX_OTHER = 5 };          /* 28: a new name's sex byte beyond 1..3 */
enum { CG_LAST_SAME = 0, CG_LAST_DIFFERENT = 1, CG_LAST_RANDOM = 2 };   /* 28: its byte 3 */
#include "story_villager_names.h"     /* each game's first-name lists (scripts/build_cie_villager_names.py) */
#include "story_title_widths.h"       /* the later games' title font widths (scripts/build_cie_title_widths.py) */

/* The pronouns are CG_PH_HE .. CG_PH_MAN and CG_PH_HIMSELF .. CG_PH_SON (cg_pronoun). */
enum { CG_PH_NAME = 0, CG_PH_HE, CG_PH_HIS, CG_PH_HIM, CG_PH_MAN, CG_PH_AWARD, CG_PH_UNIT,
       CG_PH_HIMSELF, CG_PH_WOMAN_MAN, CG_PH_BOY, CG_PH_SON,
       /* role-sex words (cie-v6-binary.md 5) */
       CG_PH_MOTHER, CG_PH_FATHER, CG_PH_MOM, CG_PH_SISTER, CG_PH_AUNT, CG_PH_GIRL, CG_PH_LADY,
       /* the standalone possessive (the owner's files, 2026-11-16): "his" / "hers" */
       CG_PH_HIS_HERS,
       /* 35: the chief's title "headman" / "headwoman" */
       CG_PH_HEADMAN };
enum { CG_EXPAND_AWARD = 0, CG_EXPAND_WORST = 1, CG_EXPAND_REAL = 2 };

/* ---- The .cieg (src/vv_cie_graph.py THE BINARY .cieg) ----------------------------------------------------- */

typedef struct {
    const unsigned char *d;
    unsigned int size;
    unsigned int games;
    int version;                      /* 1; 2: a question may be any node, text may hold "; 3: award ranges,
                                         the puzzle requirement, age gaps between roles */
    int req_cond;                     /* version 3: the requirement's condition (puzzles), CG_NONE */
    int title, start, min_eligible;
    int n_role, n_node, n_child, n_effect, n_cond, n_variant, n_string, n_patch;
    unsigned int o_role, o_node, o_child, o_effect, o_cond, o_variant, o_patch, o_string, o_blob, blob_size;
    /* Version 6: the header's and a role's size, the pools and their items, the flags (bit 0 the guard). */
    unsigned int header_bytes, role_bytes;
    int n_pool, n_item, flags;
    unsigned int o_pool, o_item;
    /* Version 6 (cie-v6-binary.md 18): the title as the file holds it, and its title variants (header +92 the
       first in the variants table, +94 the count; 0 none).  `title` is the one cg_choose_title picked. */
    int base_title, tv_first, tv_count;
    /* Version 6 (cie-v6-binary.md 21): the kinship relations (a 104-byte header); 0 none. */
    int n_rel;
    unsigned int o_rel;
    /* A text, a title or a label longer than the popups without Scrolling Popups hold (CG_TEXT_MAX bytes, a label
       or a title CG_LABEL_V6): the event is queued only where the popups scroll (cg_refusal). */
    int long_text;
} cg_graph;

static unsigned int cg_u16(const unsigned char *p) {
    return (unsigned int)p[0] | (unsigned int)p[1] << 8;
}

static unsigned int cg_u32(const unsigned char *p) {
    return (unsigned int)p[0] | (unsigned int)p[1] << 8 | (unsigned int)p[2] << 16 | (unsigned int)p[3] << 24;
}

static const unsigned char *cg_role_at(const cg_graph *g, int i) {
    return g->d + g->o_role + g->role_bytes * (unsigned int)i;
}
static const unsigned char *cg_pool_at(const cg_graph *g, int i) { return g->d + g->o_pool + 12u * (unsigned int)i; }
static const unsigned char *cg_item_at(const cg_graph *g, int i) { return g->d + g->o_item + 8u * (unsigned int)i; }
static const unsigned char *cg_node_at(const cg_graph *g, int i) { return g->d + g->o_node + 28u * (unsigned int)i; }
static const unsigned char *cg_child_at(const cg_graph *g, int i) { return g->d + g->o_child + 12u * (unsigned int)i; }
static const unsigned char *cg_effect_at(const cg_graph *g, int i) { return g->d + g->o_effect + 16u * (unsigned int)i; }
static const unsigned char *cg_cond_at(const cg_graph *g, int i) { return g->d + g->o_cond + 8u * (unsigned int)i; }
static const unsigned char *cg_variant_at(const cg_graph *g, int i) { return g->d + g->o_variant + 4u * (unsigned int)i; }

/* String `i` ("" for NONE; every index was checked by cg_load). */
static const char *cg_s(const cg_graph *g, unsigned int i) {
    if (i == CG_NONE || (int)i >= g->n_string) {
        return "";
    }
    return (const char *)(g->d + g->o_blob + cg_u32(g->d + g->o_string + 4u * i));
}

/* The zlib CRC-32 (src/vv_cie_graph.py writes zlib.crc32 of the file with its own field 0). */
static unsigned int cg_crc_table[256];

static unsigned int cg_crc32(const unsigned char *data, unsigned int size, unsigned int skip_at) {
    unsigned int crc = 0xFFFFFFFFu;
    unsigned int i;
    if (cg_crc_table[1] == 0u) {
        unsigned int n, k, c;
        for (n = 0; n < 256u; ++n) {
            c = n;
            for (k = 0; k < 8u; ++k) {
                c = (c & 1u) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            }
            cg_crc_table[n] = c;
        }
    }
    for (i = 0; i < size; ++i) {
        unsigned char b = (i >= skip_at && i < skip_at + 4u) ? 0 : data[i];
        crc = cg_crc_table[(crc ^ b) & 0xFFu] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}

static char cg_why[160];

/* `text` is at most `max` bytes; longer than `paged` marks the graph as needing Scrolling Popups (long_text). */
static int cg_len_ok(const cg_graph *g, const char *text, int paged, int max) {
    int n = lstrlenA(text);
    if (n > paged) {
        ((cg_graph *)g)->long_text = 1;
    }
    return n <= max;
}

static int cg_bad(const char *why) {
    lstrcpynA(cg_why, why, sizeof cg_why);
    return 0;
}

/* A section of `count` entries of `size` bytes at `at`, inside the file. */
static int cg_section(const cg_graph *g, unsigned int at, int count, unsigned int size) {
    return at >= g->header_bytes && at <= g->size && (unsigned int)count <= (g->size - at) / size;
}

static int cg_str_ok(const cg_graph *g, unsigned int i, int may_be_none) {
    return i == CG_NONE ? may_be_none : (int)i < g->n_string;
}

/* A version 5 food / tech effect's per-game amounts, "<game>:<min>-<max>;..." (src/vv_cie_graph.py per_game_text):
   1 with game `game`'s into *lo / *hi, 0 when it is not listed, -1 when the text is not that shape. */
static int cg_num(const char **p, int *out) {
    int neg = 0, v = 0, digits = 0;
    if (**p == '-') {
        neg = 1;
        ++*p;
    }
    while (**p >= '0' && **p <= '9' && digits < 9) {
        v = v * 10 + (**p - '0');
        ++*p;
        ++digits;
    }
    *out = neg ? -v : v;
    return digits > 0;
}

static int cg_per_game(const char *text, int game, int *lo, int *hi) {
    const char *p = text;
    int found = 0, last = 0;
    while (*p != '\0') {
        int g, a, b;
        if (*p < '1' || *p > '5' || p[1] != ':') {
            return -1;
        }
        g = *p - '0';
        p += 2;
        if (g <= last || !cg_num(&p, &a) || *p != '-') {
            return -1;
        }
        ++p;
        if (!cg_num(&p, &b) || (*p != ';' && *p != '\0')) {
            return -1;
        }
        if (*p == ';') {
            ++p;
            if (*p == '\0') {
                return -1;
            }
        }
        last = g;
        if (g == game) {
            *lo = a;
            *hi = b;
            found = 1;
        }
    }
    return found;
}

static int cg_role_by_id(const cg_graph *g, const char *id, int length) {
    int r;
    for (r = 0; r < g->n_role; ++r) {
        const char *s = cg_s(g, cg_u16(cg_role_at(g, r) + 4));
        if (lstrlenA(s) == length && memcmp(s, id, (size_t)length) == 0) {
            return r;
        }
    }
    return -1;
}

/* Version 6's role shorthand "(Gardener1)": the role whose id is `id` ignoring case, -1 none. */
static int cg_role_by_id_ci(const cg_graph *g, const char *id, int length) {
    int r, k;
    for (r = 0; r < g->n_role; ++r) {
        const char *s = cg_s(g, cg_u16(cg_role_at(g, r) + 4));
        if (lstrlenA(s) != length) {
            continue;
        }
        for (k = 0; k < length; ++k) {
            char x = s[k], y = id[k];
            if (x >= 'A' && x <= 'Z') {
                x = (char)(x - 'A' + 'a');
            }
            if (y >= 'A' && y <= 'Z') {
                y = (char)(y - 'A' + 'a');
            }
            if (x != y) {
                break;
            }
        }
        if (k == length) {
            return r;
        }
    }
    return -1;
}

/* The pool named `name` (`length` bytes), -1 none. */
static int cg_pool_by_name(const cg_graph *g, const char *name, int length) {
    int i;
    for (i = 0; i < g->n_pool; ++i) {
        const char *s = cg_s(g, cg_u16(cg_pool_at(g, i)));
        if (lstrlenA(s) == length && memcmp(s, name, (size_t)length) == 0) {
            return i;
        }
    }
    return -1;
}

/* A pool token at `s` ('{'): "{NAME}" or "{NAME.k}", k 1..8 ("{NAME}" is instance 1).  Its bytes (the braces
   included) with the pool and the instance, or 0 when it is not one. */
static int cg_parse_brace(const cg_graph *g, const char *s, int *pool, int *instance) {
    const char *e = s + 1;
    int n, k = 1;
    while ((*e >= 'A' && *e <= 'Z') || (*e >= 'a' && *e <= 'z') || (*e >= '0' && *e <= '9') || *e == '_'
           || (*e == '@' && e == s + 1)) {
        ++e;
    }
    n = (int)(e - s - 1);
    if (n < 1 || n > 33) {
        return 0;
    }
    if (*e == '.') {
        if (e[1] < '1' || e[1] > '0' + CG_MAX_INSTANCE) {
            return 0;
        }
        k = e[1] - '0';
        e += 2;
    }
    if (*e != '}') {
        return 0;
    }
    *pool = cg_pool_by_name(g, s + 1, n);
    *instance = k;
    if (*pool < 0 && n == 6 && k == 1 && e == s + 7) {
        if (memcmp(s + 1, "@tribe", 6) == 0) {
            *pool = CG_POOL_TRIBE;     /* G5: built in, filled at run time */
        } else if (memcmp(s + 1, "@Tribe", 6) == 0) {
            *pool = CG_POOL_TRIBE_CAP;
        }
    }
    return *pool >= 0 || *pool == CG_POOL_TRIBE || *pool == CG_POOL_TRIBE_CAP ? (int)(e - s) + 1 : 0;
}

static int cg_word_is(const char *w, int n, const char *lit) {
    int i;
    for (i = 0; i < n; ++i) {
        char c = w[i];
        if (c >= 'A' && c <= 'Z') {
            c = (char)(c - 'A' + 'a');
        }
        if (lit[i] == '\0' || c != lit[i]) {
            return 0;
        }
    }
    return lit[n] == '\0';
}

typedef struct {
    int role;                         /* -1: the award */
    int what;                         /* CG_PH_* */
    int capital;
    int caps;                         /* version 6: written ALL CAPS ("(NAME1)", "(HE/SHE)"): the word in capitals */
    int hint;                         /* version 6 labels: a name's pronoun hint, (ACCUSED|HE/SHE): its CG_PH_*;
                                         -1 none (the fallback is him/her, cie-v6-binary.md 15) */
} cg_ph;

static int cg_parse_ph_in(const cg_graph *g, const char *tok, int n, cg_ph *ph);

/* A placeholder's inside, a label name's pronoun hint included ("ACCUSED|HE/SHE"). */
static int cg_parse_ph(const cg_graph *g, const char *tok, int n, cg_ph *ph) {
    static const char *const HINTS[4] = { "he/she", "him/her", "his/her", "himself/herself" };
    static const int HINT_PH[4] = { CG_PH_HE, CG_PH_HIM, CG_PH_HIS, CG_PH_HIMSELF };
    int bar, k;
    ph->hint = -1;
    for (bar = 0; bar < n && tok[bar] != '|'; ++bar) {
    }
    if (bar == n) {
        return cg_parse_ph_in(g, tok, n, ph);
    }
    if (g->version < 6 || !cg_parse_ph_in(g, tok, bar, ph) || ph->what != CG_PH_NAME) {
        return 0;
    }
    for (k = 0; k < 4; ++k) {
        if (cg_word_is(tok + bar + 1, n - bar - 1, HINTS[k])) {
            ph->hint = HINT_PH[k];
            return 1;
        }
    }
    return 0;
}

/* A placeholder's inside ("friend.His/Her"), src/vv_cie_graph.py parse_placeholder.  0 when it is not one. */
static int cg_parse_ph_in(const cg_graph *g, const char *tok, int n, cg_ph *ph) {
    static const char *const WORDS[] = { "name", "he/she", "his/her", "him/her", "man/woman", "award", "award_unit",
                                         "himself/herself", "woman/man", "boy/girl", "son/daughter",
                                         "mother/father", "father/mother", "mom/dad", "sister/brother", "aunt/uncle",
                                         "girl/boy", "lady/gentleman", "his/hers", "headman/headwoman" };
    int words = g->version >= 6 ? 20 : 7;
    int dot = -1;
    int i;
    int role = -1;
    const char *w;
    int wn;
    for (i = 0; i < n; ++i) {
        if (tok[i] == '.') {
            dot = i;
        }
    }
    w = tok + dot + 1;
    wn = n - dot - 1;
    if (dot == 0 || wn <= 0) {
        return 0;
    }
    {
        /* Version 6: ALL CAPS -- at least two letters, none lower case (docs/event-collection/cie-v6-binary.md 5). */
        int letters = 0, lower = 0;
        for (i = 0; i < n; ++i) {
            letters += (tok[i] >= 'A' && tok[i] <= 'Z') || (tok[i] >= 'a' && tok[i] <= 'z');
            lower += tok[i] >= 'a' && tok[i] <= 'z';
        }
        ph->caps = g->version >= 6 && letters >= 2 && lower == 0;
    }
    if (dot > 0) {
        role = ph->caps ? cg_role_by_id_ci(g, tok, dot) : cg_role_by_id(g, tok, dot);
        if (role < 0) {
            return 0;
        }
    }
    ph->capital = w[0] >= 'A' && w[0] <= 'Z';
    if (cg_word_is(w, wn, "name1") || cg_word_is(w, wn, "name2")) {
        if (dot > 0) {
            return 0;
        }
        role = w[4] == '1' ? cg_role_by_id(g, "subject", 7) : cg_role_by_id(g, "friend", 6);
        if (role < 0) {
            return 0;
        }
        ph->what = CG_PH_NAME;
    } else {
        for (i = 0; i < words && !cg_word_is(w, wn, WORDS[i]); ++i) {
        }
        if (i == words) {
            /* Version 6: "(gardener1)" / "(Gardener1)", that role's name (a keyword always wins). */
            if (g->version < 6 || dot >= 0) {
                return 0;
            }
            role = cg_role_by_id_ci(g, w, wn);
            if (role < 0) {
                return 0;
            }
            i = CG_PH_NAME;
        }
        ph->what = i;
        if (i == CG_PH_AWARD || i == CG_PH_UNIT) {
            if (dot > 0) {
                return 0;
            }
            ph->role = -1;
            return 1;
        }
        if (role < 0) {
            role = cg_role_by_id(g, "subject", 7);
            if (role < 0) {
                if (g->n_role < 1) {
                    return 0;          /* version 6: a graph with no roles has no one to name */
                }
                role = 0;
            }
        }
    }
    if (ph->what == CG_PH_NAME && cg_role_at(g, role)[0] == CG_ROLE_STRANGER
        && !(g->version >= 6 && (cg_role_at(g, role)[1] & CG_STRANGER_NAMED))) {
        return 0;                     /* a stranger has no name (version 6: unless named, cie-v6-binary.md 16) */
    }
    ph->role = role;
    return 1;
}

/* Every character allowed (ce_text_char_ok; line breaks when `lines`), parentheses only around placeholders (no
   award in a label: `label`).  Version 6: also ; / & %, the escaped \( \), and pool tokens ({@word} only in a
   label). */
/* A count token at `s` ('{'), cie-v6-binary.md 33: "{#babies:a baby|twins|triplets}" or "{#made:one|two|three}" --
   the babies / the villagers the page's effects actually made (or, with none on this page, the last page's that made
   any), the first option for 1 (or none known), the second for 2, the third for 3 or more (fewer options: the last).
   Its bytes, the count kind in *which (0 babies, 1 made), its options in *opts (`*olen` bytes); 0 when it is not
   one.  Options: 1 to 3, each 1 to 160 bytes of the plain text set and placeholders -- the event's own (a name, a
   pronoun, checked against graph `g` when it is not NULL) or (made1) / (made2) -- with no brace, list, line break
   or . ! ?. */
static int cg_parse_ph(const cg_graph *g, const char *tok, int n, cg_ph *ph);

/* The names filled after the page's effects (cie-v6-binary.md 33a), any case at `s`: "(made1)" 1, "(made2)" 2,
   "(renamed)" 3; else 0. */
static int cg_made_ph(const char *s) {
    static const char RENAMED[] = "(renamed)";
    int k;
    if (s[0] == '(' && (s[1] == 'm' || s[1] == 'M') && (s[2] == 'a' || s[2] == 'A') && (s[3] == 'd' || s[3] == 'D')
        && (s[4] == 'e' || s[4] == 'E') && (s[5] == '1' || s[5] == '2') && s[6] == ')') {
        return s[5] - '0';
    }
    for (k = 0; RENAMED[k] != '\0'; ++k) {
        char c = s[k];
        if (c >= 'A' && c <= 'Z') {
            c = (char)(c - 'A' + 'a');
        }
        if (c != RENAMED[k]) {
            return 0;
        }
    }
    return 3;
}

/* Its bytes: 7, "(renamed)" 9. */
static int cg_made_len(int kind) {
    return kind == 3 ? 9 : 7;
}

static int cg_count_token_in(const cg_graph *g, const char *s, int *which, const char **opts, int *olen) {
    static const char *const NAMES[2] = { "babies", "made" };
    const char *p;
    int k, count = 1, run = 0;
    if (s[0] != '{' || s[1] != '#') {
        return 0;
    }
    for (k = 0; k < 2; ++k) {
        int n = lstrlenA(NAMES[k]);
        if (memcmp(s + 2, NAMES[k], (size_t)n) == 0 && s[2 + n] == ':') {
            break;
        }
    }
    if (k == 2) {
        return 0;
    }
    *which = k;
    *opts = s + 3 + lstrlenA(NAMES[k]);
    for (p = *opts; *p != '}'; ++p) {
        if (*p == '|') {
            if (run == 0 || ++count > 3) {
                return 0;
            }
            run = 0;
            continue;
        }
        if (*p == '(') {
            /* a placeholder: (made1) / (made2), or one of the event's own */
            const char *e = p + 1;
            cg_ph ph;
            while (*e != '\0' && *e != ')' && *e != '(' && *e != '\n' && *e != '|' && *e != '}') {
                ++e;
            }
            if (*e != ')' || (!cg_made_ph(p) && g != NULL && (!cg_parse_ph(g, p + 1, (int)(e - p - 1), &ph)
                                                               || ph.hint >= 0))) {
                return 0;
            }
            run += (int)(e - p) + 1;
            if (run > 160) {
                return 0;
            }
            p = e;
            continue;
        }
        /* The plain text set of a version 6 body (cg_text_ok): the Custom Island Event's characters, and " ; / & %
           (cie-v6-binary.md 33). */
        if (*p == '\0' || *p == '{' || *p == ')' || *p == '\n' || *p == '.' || *p == '!' || *p == '?'
            || !(ce_text_char_ok(*p) || *p == '"' || *p == ';' || *p == '/' || *p == '&' || *p == '%')
            || ++run > 160) {
            return 0;
        }
    }
    if (run == 0) {
        return 0;
    }
    *olen = (int)(p - *opts);
    return (int)(p - s) + 1;
}

static int cg_count_token(const char *s, int *which, const char **opts, int *olen) {
    return cg_count_token_in(NULL, s, which, opts, olen);   /* the loader checked its placeholders */
}

/* The option of a count token for `n` (the longest with n < 0: the worst case), into out (`cap` bytes); its
   length. */
static int cg_count_option(const char *opts, int olen, int n, char *out, int cap) {
    int k = 0, want = n <= 1 ? 0 : n == 2 ? 1 : 2, start = 0, i, best = -1, best_len = -1, best_start = 0;
    for (i = 0; i <= olen; ++i) {
        if (i == olen || opts[i] == '|') {
            int len = i - start;
            if (n < 0 ? len > best_len : k <= want) {
                best = k;
                best_len = len;
                best_start = start;
            }
            ++k;
            start = i + 1;
        }
    }
    if (best < 0 || best_len >= cap) {
        return 0;
    }
    memcpy(out, opts + best_start, (size_t)best_len);
    out[best_len] = '\0';
    return best_len;
}

/* The villagers made (story_graph.inc cg_newest, below): (made1) the newest, (made2) the one before it; one made:
   both are that one (so (made2) is never empty); none: "a newcomer". */
static void cg_made_name(int k, char *out, int cap);

/* Option `opt` (`n` bytes) with (made1) / (made2) put in -- the names (`worst` 0) or `room` W's -- into out. */
static void cg_made_fill(const char *opt, int n, int worst, int room, char *out, int cap) {
    int i, o = 0;
    for (i = 0; i < n && o < cap - 1;) {
        int k = cg_made_ph(opt + i);
        if (k > 0 && i + cg_made_len(k) <= n) {
            char name[CG_NAME_BYTES + 16];
            const char *t;
            if (worst) {
                int c;
                for (c = 0; c < room && c < (int)sizeof name - 1; ++c) {
                    name[c] = 'W';
                }
                name[c] = '\0';
            } else {
                cg_made_name(k, name, (int)sizeof name);
            }
            for (t = name; *t != '\0' && o < cap - 1; ++t) {
                out[o++] = *t;
            }
            i += cg_made_len(k);
            continue;
        }
        out[o++] = opt[i++];
    }
    out[o] = '\0';
}

static int cg_text_ok(const cg_graph *g, const char *s, int lines, int label) {
    for (; *s != '\0'; ++s) {
        if (g->version >= 6) {
            if (*s == '\\') {
                if (s[1] != '(' && s[1] != ')') {
                    return 0;
                }
                ++s;
                continue;
            }
            if (*s == '{' && s[1] == '#') {
                const char *opts;
                int which, olen, n = cg_count_token_in(g, s, &which, &opts, &olen);
                if (n == 0 || label) {
                    return 0;          /* 33: a count token, in body text only */
                }
                s += n - 1;
                continue;
            }
            if (*s == '{') {
                int pool, instance, n = cg_parse_brace(g, s, &pool, &instance);
                if (n == 0 || (label && pool >= 0 && cg_s(g, cg_u16(cg_pool_at(g, pool)))[0] != '@')) {
                    return 0;
                }
                s += n - 1;
                continue;
            }
            if (*s == ';' || *s == '/' || *s == '&' || *s == '%') {
                continue;
            }
        }
        if (*s == '(' && g->version >= 6 && cg_made_ph(s)) {
            if (label) {
                return 0;              /* 33: the villagers made, in body text only */
            }
            s += cg_made_len(cg_made_ph(s)) - 1;
            continue;
        }
        if (*s == '(') {
            const char *e = s + 1;
            cg_ph ph;
            while (*e != '\0' && *e != ')' && *e != '(' && *e != '\n') {
                ++e;
            }
            if (*e != ')' || !cg_parse_ph(g, s + 1, (int)(e - s - 1), &ph) || (label && ph.role < 0)
                || (!label && ph.hint >= 0)) {     /* a pronoun hint only in a label (cie-v6-binary.md 15) */
                return 0;
            }
            s = e;
            continue;
        }
        if (*s == '\n' && lines) {
            continue;
        }
        if (*s == '"' && g->version >= 2) {
            continue;                  /* version 2: every game's font draws it (src/vv_font_glyphs.py) */
        }
        if (!ce_text_char_ok(*s)) {
            return 0;
        }
    }
    return 1;
}

/* Every edge of node `i` into `out` (at most 2 per child + 1); the count. */
static int cg_edges(const cg_graph *g, int i, int *out) {
    const unsigned char *n = cg_node_at(g, i);
    int first = (int)cg_u16(n + 12), count = (int)cg_u16(n + 14), k, m = 0;
    for (k = 0; k < count; ++k) {
        const unsigned char *c = cg_child_at(g, first + k);
        out[m++] = (int)cg_u16(c);
        if (n[0] != CG_QUESTION && cg_u16(c + 6) != CG_NONE) {
            out[m++] = (int)cg_u16(c + 6);
        }
    }
    if (cg_u16(n + 16) != CG_NONE) {
        out[m++] = (int)cg_u16(n + 16);
    }
    return m;
}

/* No cycle (Kahn): every node is removed once nothing points at it any more. */
static int cg_acyclic(const cg_graph *g) {
    static unsigned short indegree[CG_MAX_NODES];
    static unsigned short queue[CG_MAX_NODES];
    static int edges[2 * 256 + 2];
    int i, k, m, head = 0, tail = 0, removed = 0;
    memset(indegree, 0, sizeof indegree);
    for (i = 0; i < g->n_node; ++i) {
        m = cg_edges(g, i, edges);
        for (k = 0; k < m; ++k) {
            ++indegree[edges[k]];
        }
    }
    for (i = 0; i < g->n_node; ++i) {
        if (indegree[i] == 0) {
            queue[tail++] = (unsigned short)i;
        }
    }
    while (head < tail) {
        i = queue[head++];
        ++removed;
        m = cg_edges(g, i, edges);
        for (k = 0; k < m; ++k) {
            if (--indegree[edges[k]] == 0) {
                queue[tail++] = (unsigned short)edges[k];
            }
        }
    }
    return removed == g->n_node;
}

/* VERSION 6 POOLS.  How many pools deep the tokens of pool `p`'s items go (1: none), -1 when they loop back or go
   deeper than CG_POOL_DEPTH. */
static unsigned char cg_pool_level[CG_MAX_POOLS];   /* 0 not known yet, 0xFF being looked at */

static int cg_pool_chain(const cg_graph *g, int p, int depth) {
    const unsigned char *pool = cg_pool_at(g, p);
    int k, best = 0;
    if (depth > CG_POOL_DEPTH || cg_pool_level[p] == 0xFFu) {
        return -1;
    }
    if (cg_pool_level[p] != 0u) {
        return cg_pool_level[p];
    }
    cg_pool_level[p] = 0xFFu;
    for (k = 0; k < (int)cg_u16(pool + 4); ++k) {
        const char *s = cg_s(g, cg_u16(cg_item_at(g, (int)cg_u16(pool + 2) + k)));
        for (; *s != '\0'; ++s) {
            int q, instance, n, level;
            if (*s == '\\' && s[1] != '\0') {
                ++s;
                continue;
            }
            if (*s != '{') {
                continue;
            }
            n = cg_parse_brace(g, s, &q, &instance);
            if (n == 0 || q == p) {
                return -1;
            }
            if (q < 0) {
                s += n - 1;            /* {@tribe}: no pool */
                continue;
            }
            level = cg_pool_chain(g, q, depth + 1);
            if (level < 0) {
                return -1;
            }
            if (level > best) {
                best = level;
            }
            s += n - 1;
        }
    }
    if (best + 1 > CG_POOL_DEPTH) {
        return -1;
    }
    cg_pool_level[p] = (unsigned char)(best + 1);
    return best + 1;
}

/* Every pool and item inside its tables, every item's text one the game can show, no pool reaching itself. */
static int cg_pools_ok(const cg_graph *g) {
    int i;
    if ((g->flags & ~1) != 0) {
        return cg_bad("its flags are not ones this game can read");
    }
    for (i = 0; i < g->n_pool; ++i) {
        const unsigned char *p = cg_pool_at(g, i);
        unsigned int first = cg_u16(p + 2), count = cg_u16(p + 4);
        if (!cg_str_ok(g, cg_u16(p), 0) || cg_s(g, cg_u16(p))[0] == '\0' || count < 1u
            || first + count > (unsigned int)g->n_item || (p[6] & ~(CG_POOL_DISTINCT | CG_POOL_LINKED)) != 0u
            || p[7] != 0u
            || !cg_str_ok(g, cg_u16(p + 8), 1) || cg_u16(p + 10) != 0u) {
            return cg_bad("a pool is not one this game can read");
        }
    }
    for (i = 0; i < g->n_item; ++i) {
        const unsigned char *it = cg_item_at(g, i);
        unsigned int cond = cg_u16(it + 4);
        if (!cg_str_ok(g, cg_u16(it), 0) || cg_u16(it + 2) < 1u || cg_u16(it + 2) > 10000u
            || (cond != CG_NONE && (int)cond >= g->n_cond) || cg_u16(it + 6) != 0u
            || !cg_text_ok(g, cg_s(g, cg_u16(it)), 1, 0)
            || !cg_len_ok(g, cg_s(g, cg_u16(it)), CG_TEXT_MAX, CE_LONG_TEXT_MAX)) {
            return cg_bad("a pool's text is not one the game can show");
        }
    }
    memset(cg_pool_level, 0, sizeof cg_pool_level);
    for (i = 0; i < g->n_pool; ++i) {
        if (cg_pool_chain(g, i, 1) < 0) {
            return cg_bad("a pool's text goes round in a circle or too deep");
        }
    }
    return 1;
}

/* Read `data` (`size` bytes) as a .cieg into `g` (which points into `data`): 1, or 0 with the reason in cg_why. */
/* A title the game can show (the event's, or -- version 6 -- a node's popup title, docs/event-collection/
   cie-v6-binary.md 14): ce_text_char_ok's characters (version 6: and quotes, G6), one line, under CE_TITLE_BYTES. */
static int cg_title_ok(const cg_graph *g, const char *title) {
    const char *t;
    for (t = title; *t != '\0'; ++t) {
        if (*t == '(' && g->version >= 6) {
            /* Version 6: a placeholder naming a role (section 17): a name, a pronoun, a name's hint. */
            const char *e = t + 1;
            cg_ph ph;
            while (*e != '\0' && *e != ')' && *e != '(' && *e != '\n') {
                ++e;
            }
            if (*e != ')' || !cg_parse_ph(g, t + 1, (int)(e - t - 1), &ph) || ph.role < 0) {
                return 0;
            }
            t = e;
            continue;
        }
        if (!ce_text_char_ok(*t) && !(*t == '"' && g->version >= 6)) {
            return 0;
        }
    }
    return title[0] != '\0' && (g->version >= 6 ? cg_len_ok(g, title, CG_LABEL_V6 - 1, CE_LONG_LINE_BYTES - 1)
                                             : lstrlenA(title) < CE_TITLE_BYTES);
}

static int cg_fixed_name_ok(const char *name);   /* effect 33's fixed name (below) */

/* What may happen to a Heathen in a new event (vanilla's whole list): Faith raised, joining, being stopped, walked
   or posed (an action), a little health lost (5 to 30) and the sick mark; never a death, a disappearance, an age,
   a skill, a like, a lower Faith or becoming a Heathen again. */
static int cg_health_now(int game, const unsigned char *record);   /* below */

static int cg_heathen_effect_ok(const unsigned char *e) {
    int a = (int)((unsigned int)e[4] | ((unsigned int)e[5] << 8) | ((unsigned int)e[6] << 16)
                  | ((unsigned int)e[7] << 24));
    switch (e[0]) {
    case CGE_FAITH: case CGE_JOIN: case CGE_ACTION: case CGE_SICK: case CGE_TRAIT:
        return 1;
    case CGE_HEALTH_CHANGE:
        return a >= -30;
    default:
        return 0;
    }
}

/* A group effect (role byte 254): the effects a group may take, and its selector. */
static int cg_group_ok(const cg_graph *g, const unsigned char *e) {
    unsigned int value = (unsigned int)e[14] | ((unsigned int)e[15] << 8);
    switch (e[0]) {
    case CGE_HEALTH: case CGE_PREF: case CGE_SKILL: case CGE_SICK: case CGE_ACTION: case CGE_MOOD:
    case CGE_HEALTH_CHANGE: case CGE_SKILL_SET: case CGE_CURE: case CGE_YOUNG_LOOK: case CGE_OLD_LOOK:
    case CGE_CELEBRATE: case CGE_APPEARANCE:
        break;
    default:
        return 0;
    }
    switch (e[3]) {
    case CG_GROUP_ALL: case CG_GROUP_ELDERS: case CG_GROUP_CHILDREN: case CG_GROUP_TEENS: case CG_GROUP_ADULTS:
        return value == 0u;
    case CG_GROUP_SKILL:
        return value != CG_NONE && (int)value < g->n_string
               && cg_s(g, value)[0] != '\0';
    case CG_GROUP_RANDOM: return value >= 1u && value <= 255u;
    default: return 0;
    }
}

static int cg_load(cg_graph *g, const unsigned char *data, unsigned int size) {
    const unsigned char *h = data;
    int i, k;
    memset(g, 0, sizeof *g);
    g->d = data;
    g->size = size;
    if (size < CG_HEADER_BYTES || memcmp(h, "CIEG", 4) != 0 || cg_u16(h + 4) < 1u || cg_u16(h + 4) > 6u
        || (cg_u16(h + 6) != (cg_u16(h + 4) >= 6u ? CG_HEADER_V6 : CG_HEADER_BYTES)
            && !(cg_u16(h + 4) >= 6u && cg_u16(h + 6) == CG_HEADER_REL)) || size < cg_u16(h + 6)
        || cg_u32(h + 8) != size) {
        return cg_bad("it is not a version 1, 2, 3, 4, 5 or 6 .cieg file");
    }
    g->version = (int)cg_u16(h + 4);
    g->header_bytes = cg_u16(h + 6);
    g->role_bytes = g->version >= 6 ? 16u : 8u;
    if (size > CG_MAX_FILE) {
        return cg_bad("it is larger than this game can read (16 MB)");
    }
    if (cg_crc32(data, size, 12) != cg_u32(h + 12)) {
        return cg_bad("the file is damaged (its checksum does not match)");
    }
    g->games = cg_u32(h + 16);
    g->title = (int)cg_u16(h + 20);
    g->start = (int)cg_u16(h + 22);
    g->min_eligible = (int)cg_u16(h + 24);
    g->n_role = (int)cg_u16(h + 26);
    g->n_node = (int)cg_u16(h + 28);
    g->n_child = (int)cg_u16(h + 30);
    g->n_effect = (int)cg_u16(h + 32);
    g->n_cond = (int)cg_u16(h + 34);
    g->n_variant = (int)cg_u16(h + 36);
    g->n_string = (int)cg_u16(h + 38);
    g->n_patch = (int)cg_u16(h + 40);
    g->req_cond = g->version >= 3 ? (int)cg_u16(h + 42) : (int)CG_NONE;
    g->o_role = cg_u32(h + 44);
    g->o_node = cg_u32(h + 48);
    g->o_child = cg_u32(h + 52);
    g->o_effect = cg_u32(h + 56);
    g->o_cond = cg_u32(h + 60);
    g->o_variant = cg_u32(h + 64);
    g->o_patch = cg_u32(h + 68);
    g->o_string = cg_u32(h + 72);
    if (g->version >= 6) {
        g->o_pool = cg_u32(h + 76);
        g->o_item = cg_u32(h + 80);
        g->n_pool = (int)cg_u16(h + 84);
        g->n_item = (int)cg_u16(h + 86);
        g->flags = (int)cg_u16(h + 88);
        if (g->n_pool > CG_MAX_POOLS || g->n_item > CG_MAX_ITEMS || !cg_section(g, g->o_pool, g->n_pool, 12)
            || !cg_section(g, g->o_item, g->n_item, 8)) {
            return cg_bad("its pools do not fit in the file");
        }
        g->tv_first = (int)cg_u16(h + 92);
        g->tv_count = (int)cg_u16(h + 94);
        if (g->header_bytes == CG_HEADER_REL) {
            /* 21: the relations' offset and count, then 0. */
            g->o_rel = cg_u32(h + 96);
            g->n_rel = (int)cg_u16(h + 100);
            if (g->n_rel < 1 || cg_u16(h + 102) != 0u || !cg_section(g, g->o_rel, g->n_rel, 4)) {
                return cg_bad("its kinship relations do not fit in the file");
            }
        }
    }
    if (g->games == 0u || (g->games & ~0x1Fu) != 0u || g->n_role < (g->version >= 6 ? 0 : 1) || g->n_role > CG_MAX_ROLES || g->n_node < 1
        || g->n_node > CG_MAX_NODES || g->n_patch > 32 || g->n_child >= 0xFFFF || g->n_effect >= 0xFFFF
        || g->n_cond >= 0xFFFF || g->n_variant >= 0xFFFF || g->n_string >= 0xFFFF
        || !cg_section(g, g->o_role, g->n_role, g->role_bytes) || !cg_section(g, g->o_node, g->n_node, 28)
        || !cg_section(g, g->o_child, g->n_child, 12) || !cg_section(g, g->o_effect, g->n_effect, 16)
        || !cg_section(g, g->o_cond, g->n_cond, 8) || !cg_section(g, g->o_variant, g->n_variant, 4)
        || !cg_section(g, g->o_patch, g->n_patch, 2) || !cg_section(g, g->o_string, g->n_string, 4)) {
        return cg_bad("its tables do not fit in the file");
    }
    g->o_blob = g->o_string + 4u * (unsigned int)g->n_string;
    g->blob_size = size - g->o_blob;
    for (i = 0; i < g->n_string; ++i) {
        unsigned int at = cg_u32(data + g->o_string + 4u * (unsigned int)i);
        if (at >= g->blob_size || memchr(data + g->o_blob + at, 0, g->blob_size - at) == NULL) {
            return cg_bad("a string runs past the end of the file");
        }
    }
    if (!cg_str_ok(g, (unsigned int)g->title, 0) || g->start >= g->n_node) {
        return cg_bad("its title or start is missing");
    }
    if (!cg_title_ok(g, cg_s(g, (unsigned int)g->title))) {
        return cg_bad("its title is not one the game can show");
    }
    g->base_title = g->title;
    if ((g->tv_count == 0 && g->tv_first != 0) || g->tv_first + g->tv_count > g->n_variant) {
        return cg_bad("its title variants do not fit in the file");
    }
    for (i = 0; i < g->tv_count; ++i) {
        const unsigned char *v = g->d + g->o_variant + 4u * (unsigned int)(g->tv_first + i);
        unsigned int c = cg_u16(v), t = cg_u16(v + 2);
        if ((c != CG_NONE && c >= (unsigned int)g->n_cond) || !cg_str_ok(g, t, 0) || !cg_title_ok(g, cg_s(g, t))) {
            return cg_bad("a title variant is not one the game can show");
        }
    }
    for (i = 0; i < g->n_patch; ++i) {
        if (!cg_str_ok(g, cg_u16(data + g->o_patch + 2u * (unsigned int)i), 0)) {
            return cg_bad("a patch name is missing");
        }
    }
    for (i = 0; i < g->n_role; ++i) {
        const unsigned char *r = cg_role_at(g, i);
        if (r[0] > (g->version >= 6 ? 3u : 1u) || !cg_str_ok(g, cg_u16(r + 4), 0)
            || (r[0] == 0 && (r[2] > 2u || r[3] > 120u))
            || (r[0] == 1 && (r[2] < 1u || r[2] > ((r[1] & CG_STRANGER_NEW_NAME) ? 5u : 3u)))
            || (r[0] == 1 && g->version >= 6 && (r[1] & ~(CG_STRANGER_NAMED | CG_STRANGER_NEW_NAME)) != 0u)
            || (r[0] == 1 && (r[1] & CG_STRANGER_NEW_NAME) && (!(r[1] & CG_STRANGER_NAMED) || r[3] > 2u))
            || (i == 0 && ((r[0] != CG_ROLE_VILLAGER && !(g->version >= 6 && r[0] == CG_ROLE_STRANGER))
                           || (r[0] == CG_ROLE_VILLAGER && (r[1] & CG_ROLE_OPTIONAL))))
            ) {
            return cg_bad("a role is not one this game can read");
        }
        if (g->version >= 6) {
            /* Version 6: max age, the special villager, the skill requirement and its pick; an alias's members (other
               villager roles), and nothing else on an alias. */
            unsigned int members = cg_u16(r + 14);
            if ((r[8] != 0 && (r[8] > 120u || r[8] < r[3])) || r[9] > CG_PREFER_CHIEF || !cg_str_ok(g, cg_u16(r + 10), 1)
                || (r[13] & ~(CG_ROLE_SPEAKS | CG_ROLE_HEATHEN)) > 1u || r[12] > 100u) {
                return cg_bad("a role's requirement is not one this game can read");
            }
            if (r[0] == CG_ROLE_OTHER) {
                /* G2: exactly one bit, a two-member alias. */
                int al;
                for (al = 0; al < g->n_role && members != (1u << al); ++al) {
                }
                if (al >= g->n_role || (r[1] & ~CG_ROLE_HARM) != 0 || r[2] != 0 || r[3] != 0 || r[6] != 0
                    || r[8] != 0 || r[9] != 0 || cg_u16(r + 10) != CG_NONE
                    || cg_role_at(g, al)[0] != CG_ROLE_ALIAS) {
                    return cg_bad("an other role is not one this game can read");
                }
                {
                    unsigned int m = cg_u16(cg_role_at(g, al) + 14);
                    int bits = 0;
                    for (; m != 0u; m &= m - 1u) {
                        ++bits;
                    }
                    if (bits != 2) {
                        return cg_bad("an other role follows an alias that does not have two members");
                    }
                }
            } else if (r[0] == CG_ROLE_ALIAS) {
                if (members == 0u || (members >> g->n_role) != 0u || (members & (1u << i))
                    || (r[1] & ~CG_ROLE_HARM) != 0 || r[2] != 0
                    || r[3] != 0 || r[6] != 0 || r[8] != 0 || r[9] != 0 || cg_u16(r + 10) != CG_NONE) {
                    return cg_bad("an alias role is not one this game can read");
                }
                for (k = 0; k < g->n_role; ++k) {
                    if ((members & (1u << k)) && cg_role_at(g, k)[0] != CG_ROLE_VILLAGER) {
                        return cg_bad("an alias role names a role that is not a villager");
                    }
                }
            } else if (r[0] == CG_ROLE_STRANGER && (r[1] & CG_STRANGER_NEW_NAME)) {
                /* 28: a new name -- exactly one bit, a villager role the event needs. */
                int of;
                for (of = 0; of < g->n_role && members != (1u << of); ++of) {
                }
                if (of >= g->n_role || cg_role_at(g, of)[0] != CG_ROLE_VILLAGER
                    || (cg_role_at(g, of)[1] & CG_ROLE_OPTIONAL)) {
                    return cg_bad("a new name is not for a villager role the event needs");
                }
            } else if (members != 0u) {
                return cg_bad("a role is not one this game can read");
            }
        }
        if (r[6] != 0 || r[7] != 0) {
            /* Version 3: at most r[7] years apart from role r[6] - 1, both villagers. */
            int other = (int)r[6] - 1;
            if (g->version < 3 || other < 0 || other >= g->n_role || other == i || r[0] != 0
                || cg_role_at(g, other)[0] != 0 || r[7] > 80u) {
                return cg_bad("a role's age gap is not one this game can read");
            }
        }
    }
    for (i = 0; i < g->n_rel; ++i) {
        /* 21: two different villager roles, a known kind, one relation a role. */
        const unsigned char *rel = g->d + g->o_rel + 4u * (unsigned int)i;
        if ((int)rel[0] >= g->n_role || (int)rel[2] >= g->n_role || rel[0] == rel[2] || rel[1] < CG_REL_SPOUSE
            || rel[1] > CG_REL_COUSIN || rel[3] != 0 || cg_role_at(g, rel[0])[0] != CG_ROLE_VILLAGER
            || cg_role_at(g, rel[2])[0] != CG_ROLE_VILLAGER) {
            return cg_bad("a kinship relation is not one this game can read");
        }
        for (k = 0; k < i; ++k) {
            if (g->d[g->o_rel + 4u * (unsigned int)k] == rel[0]) {
                return cg_bad("a role has two kinship relations");
            }
        }
    }
    for (i = 0; i < g->n_cond; ++i) {
        const unsigned char *c = cg_cond_at(g, i);
        unsigned int a = cg_u16(c + 2);
        int ok;
        switch (c[0]) {
        case CGC_VISITED: ok = (int)a < g->n_node; break;
        case CGC_ROLE: ok = (int)a < g->n_role; break;
        case CGC_GAME: ok = a != 0u && (a & ~0x1Fu) == 0u; break;
        case CGC_PATCH: ok = (int)a < g->n_patch; break;
        case CGC_NOT: ok = (int)a > i && (int)a < g->n_cond; break;
        case CGC_ALL: case CGC_ANY: ok = c[1] >= 1u && (int)a > i && (int)a + c[1] <= g->n_cond; break;
        case CGC_PUZZLE:
            ok = g->version >= 3 && cg_str_ok(g, a, 0) && cg_u16(c + 4) >= 1u && cg_u16(c + 4) <= 5u;
            break;
        case CGC_HARMABLE: ok = g->version >= 6 && (int)a < g->n_role; break;
        case CGC_SPECIAL_PRESENT: ok = g->version >= 6 && a >= 1u && a <= 2u; break;
        case CGC_MIN_POPULATION: case CGC_MIN_CHILDREN: ok = g->version >= 6 && a <= 1000u; break;
        case CGC_AGE:
            ok = g->version >= 6 && (int)a < g->n_role && cg_u16(c + 4) <= 120u && cg_u16(c + 6) <= 120u
                 && (cg_u16(c + 6) == 0u || cg_u16(c + 4) <= cg_u16(c + 6));
            break;
        case CGC_SKILL_AT_LEAST:
            ok = g->version >= 6 && (int)a < g->n_role && cg_u16(c + 4) >= 1u && cg_u16(c + 4) <= 100u
                 && cg_str_ok(g, cg_u16(c + 6), 0);
            break;
        case CGC_HAS_LIVING_CHILD: case CGC_HAS_DEAD_RELATIVE: case CGC_IS_SPECIAL:
            ok = g->version >= 6 && (int)a < g->n_role;
            break;
        case CGC_HAS_SUPPLY:
            /* 33: a good's word, at least 1..9999 of it */
            ok = g->version >= 6 && cg_str_ok(g, a, 0) && cg_good_word(cg_s(g, a)) && cg_u16(c + 4) >= 1u
                 && cg_u16(c + 4) <= 9999u;
            break;
        case CGC_DREW:
            ok = g->version >= 6 && (int)a < g->n_pool && cg_u16(c + 4) >= 1u && cg_u16(c + 4) <= CG_MAX_INSTANCE
                 && cg_u16(c + 6) < cg_u16(cg_pool_at(g, (int)a) + 4);
            break;
        default: ok = 0; break;
        }
        if (!ok) {
            return cg_bad("a condition is not one this game can read");
        }
    }
    if (g->version >= 6 && !cg_pools_ok(g)) {
        return 0;
    }
    for (i = 0; i < g->n_variant; ++i) {
        const unsigned char *v = cg_variant_at(g, i);
        if ((int)cg_u16(v) >= g->n_cond || !cg_str_ok(g, cg_u16(v + 2), 0)
            || !cg_text_ok(g, cg_s(g, cg_u16(v + 2)), 1, 0)
            || !cg_len_ok(g, cg_s(g, cg_u16(v + 2)), CG_TEXT_MAX, CE_LONG_TEXT_MAX)) {
            return cg_bad("a variant text is not one the game can show");
        }
    }
    for (i = 0; i < g->n_effect; ++i) {
        const unsigned char *e = cg_effect_at(g, i);
        int a = (int)cg_u32(e + 4), b = (int)cg_u32(e + 8), lo, hi;
        unsigned int str = cg_u16(e + 12);
        int villager = (e[0] >= CGE_KILL && e[0] <= CGE_SICK) || (e[0] >= CGE_ACTION && e[0] <= CGE_SKILL_SET)
                       || (e[0] == CGE_CELEBRATE && e[1] != CG_ROLE_ALIAS_ALL)
                       || (e[0] >= CGE_APPEARANCE && e[0] <= CGE_OLD_LOOK) || e[0] == CGE_SEX_CHANGE
                       || e[0] == CGE_DELIVER_EARLY || e[0] == CGE_TRAIT
                       || (e[0] >= CGE_PREGNANT && e[0] <= CGE_CHANGE_AGE)
                       || e[0] == CGE_CURE || e[0] == CGE_YOUNG_LOOK || e[0] == CGE_PRESENTATION
                       || e[0] == CGE_FAITH || e[0] == CGE_JOIN || e[0] == CGE_APOSTASY
                       || (e[0] == CGE_GROUP && e[1] != CG_ROLE_ALIAS_ALL);
        int ok = (e[0] >= CGE_FOOD && e[0] <= (g->version >= 6 ? CGE_OLD_LOOK : CGE_SICK))
                 || (g->version >= 6 && (e[0] == CGE_SEX_CHANGE || e[0] == CGE_PRESENTATION
                                         || e[0] == CGE_DELIVER_EARLY || e[0] == CGE_TRAIT || e[0] == CGE_SUPPLY
                                         || e[0] == CGE_TRADE || e[0] == CGE_GROUP || e[0] == CGE_VILLAGE
                                         || (e[0] >= CGE_NEW_VILLAGER && e[0] <= CGE_APOSTASY)));
        if (ok && e[1] != CG_ROLE_GROUP && e[3] != 0) {
            ok = 0;                    /* byte 3 is a group's selector only */
        }
        if (ok && e[1] != CG_ROLE_GROUP && e[0] != CGE_CHANGE_AGE && cg_u16(e + 14) != 0) {
            ok = 0;                    /* the last H: a group's value, or change_age's cap */
        }
        if (ok && villager && g->version >= 6 && (e[1] == CG_ROLE_NEWEST || e[1] == CG_ROLE_NEWEST2)) {
            /* a villager this event made on the same page */
        } else if (ok && villager && g->version >= 6 && e[1] == CG_ROLE_GROUP) {
            ok = cg_group_ok(g, e);
        } else if (ok && villager) {
            /* A villager role (version 6: or an alias, whose drawn member the effect goes to). */
            ok = e[1] < (unsigned int)g->n_role
                 && (cg_role_at(g, e[1])[0] == CG_ROLE_VILLAGER
                     || (g->version >= 6 && cg_role_at(g, e[1])[0] >= CG_ROLE_ALIAS));
        }
        if (ok) {
            switch (e[0]) {
            case CGE_FOOD: case CGE_TECH:
                /* b: version 3's range top (0: the amount alone), above the amount, the same side of 0. */
                ok = a != 0 && a <= CE_MAX_AMOUNT && a >= -CE_MAX_AMOUNT
                     && (b == 0 || (g->version >= 3 && b > a && b <= CE_MAX_AMOUNT && (b > 0) == (a > 0)));
                /* Version 5: the string is each game's own amount or range ("1:200-1500;5:50-300"), every one
                   valid; before it a food / tech effect has none. */
                if (ok && str != CG_NONE) {
                    int game;
                    ok = g->version >= 5 && cg_str_ok(g, str, 0) && cg_s(g, str)[0] != '\0';
                    for (game = 1; ok && game <= 5; ++game) {
                        int found = cg_per_game(cg_s(g, str), game, &lo, &hi);
                        ok = found >= 0 && (found == 0 || (lo != 0 && hi >= lo && (lo > 0) == (hi > 0)
                                                           && lo >= -CE_MAX_AMOUNT && hi <= CE_MAX_AMOUNT));
                    }
                }
                break;
            case CGE_KILL: case CGE_DIE_UNRECOVERED: case CGE_BIRTH_THEN_DIE: {
                const char *cause = cg_s(g, str);
                /* With Scrolling Popups practically any length (the owner, 2026-11-17: the grave's popup scrolls
                   too), else the old 63 characters. */
                ok = str != CG_NONE && cause[0] != '\0' && lstrlenA(cause) < cg_cause_bytes() && ce_text_ok(cause, 0)
                     && (e[0] == CGE_KILL || (a == 0 && b == 0));
                break;
            }
            case CGE_APPEARANCE:
                /* 22: a row 0..29, random or kept, each; at least one changed. */
                ok = a >= CG_LOOK_KEEP && a <= 29 && b >= CG_LOOK_KEEP && b <= 29
                     && !(a == CG_LOOK_KEEP && b == CG_LOOK_KEEP) && str == CG_NONE;
                break;
            case CGE_BABY_LOST: case CGE_OLD_LOOK: case CGE_SEX_CHANGE: case CGE_CURE: case CGE_YOUNG_LOOK:
                ok = a == 0 && b == 0 && str == CG_NONE;
                break;
            case CGE_REPAIR:
                /* 36: every damaged structure the list names ("any": all) */
                ok = e[1] == CG_ROLE_ALIAS_ALL && a == 0 && b == 0 && str != CG_NONE && cg_str_ok(g, str, 0)
                     && cg_s(g, str)[0] != '\0';
                break;
            case CGE_DELIVER_EARLY:
                /* 30: the newborn's extra health loss, a range -99..-1, or none (0, 0). */
                ok = str == CG_NONE && ((a == 0 && b == 0) || (a >= -99 && a <= b && b <= -1));
                break;
            case CGE_TRAIT: ok = a == (int)CG_TRAIT_MUTE && b == 0 && str == CG_NONE; break;  /* 32: a trait */
            case CGE_NEW_VILLAGER:
                /* a the age class, b the sex (0 random, 1 male, 2 female), flags bit 0 a child of the two newest */
                ok = a >= 0 && a <= 4 && b >= 0 && b <= 2 && str == CG_NONE && (e[2] & ~CG_NEW_CHILD_OF_NEWEST) == 0
                     && (e[1] == CG_ROLE_ALIAS_ALL || e[1] < (unsigned int)g->n_role || e[1] == CG_ROLE_NEWEST
                         || e[1] == CG_ROLE_NEWEST2);
                break;
            case CGE_PREGNANT: case CGE_NURSING:
                ok = (a == 0xFF || a == CG_ROLE_NEWEST || a == CG_ROLE_NEWEST2 || (a >= 0 && a < g->n_role)) && b == 0
                     && str == CG_NONE
                     && (e[2] & ~(CG_FX_ANY_BIRTH_SEX | CG_FX_LITTER_ROLL | CG_FX_LITTER_TWINS
                                  | CG_FX_PARTNER_MAY_CARRY)) == 0;
                break;
            case CGE_BODY_SWAP:
                ok = a >= 0 && a < g->n_role && a != (int)e[1] && b == 0 && str == CG_NONE;
                break;
            case CGE_CLONE:
                ok = a >= 0 && a <= 2 && b == 0 && str == CG_NONE;   /* a: how many copies (0 = 1) */
                break;
            case CGE_LOSE_NAME:
                ok = a == 0 && b == 0 && str == CG_NONE;
                break;
            case CGE_CHANGE_NAME:
                /* the string: NONE (a random first name), or the fixed name to give (cg_fixed_name_ok) */
                ok = a == 0 && b == 0 && (str == CG_NONE || cg_fixed_name_ok(cg_s(g, str)));
                break;
            case CGE_CHANGE_AGE:
                ok = str == CG_NONE && e[2] <= CG_AGE_ADD && cg_u16(e + 14) <= 120u   /* the cap, years (0 none) */
                     && (e[2] == CG_AGE_ADD ? (a >= -120 && b <= 120 && a <= b) : (a == 0 && b == 0));
                break;
            case CGE_PRESENTATION:
                /* 31: a = 1 the other sex's look, 0 the villager's own again. */
                ok = (a == 0 || a == 1) && b == 0 && str == CG_NONE;
                break;
            case CGE_STATUS: ok = a == 1; break;
            case CGE_FAITH: ok = a >= 1 && a <= 35 && b == 0 && str == CG_NONE; break;   /* vanilla: +5..+35 */
            case CGE_JOIN: case CGE_APOSTASY: ok = a == 0 && b == 0 && str == CG_NONE; break;
            case CGE_HEALTH: ok = a >= 1 && a <= 100 && b >= a && b <= 100; break;
            case CGE_SKILL:
                /* Version 6: a loss too (both ends -100..-1). */
                ok = (a >= 1 && a <= 100 && b >= a && b <= 100)
                     || (g->version >= 6 && a >= -100 && b >= a && b <= -1);
                break;
            case CGE_CELEBRATE: ok = a == 0 && b == 0 && str == CG_NONE; break;
            case CGE_ACTION: ok = a == 0 && b == 0 && str != CG_NONE && cg_str_ok(g, str, 0); break;
            case CGE_MOOD: ok = (a == 1 || a == -1) && b == 0 && str == CG_NONE; break;
            case CGE_HEALTH_CHANGE: ok = a >= -100 && b >= a && b <= 100 && str == CG_NONE; break;
            case CGE_SKILL_SET: ok = a >= 0 && a <= 100 && b == 0; break;
            case CGE_DAMAGE:
                ok = e[1] == CG_ROLE_ALIAS_ALL && a >= 1 && b >= a && b <= 100 && str != CG_NONE
                     && cg_str_ok(g, str, 0);
                break;
            case CGE_SUPPLY:
                /* 32, 33: the village's; a..b a gain (1..9999) or a loss (-9999..-1); a good's word (The Tree of
                   Life's three supplies keep 1..99, the patcher's check). */
                ok = e[1] == CG_ROLE_ALIAS_ALL && a <= b && ((a >= 1 && b <= 9999) || (a >= -9999 && b <= -1))
                     && str != CG_NONE && cg_str_ok(g, str, 0) && cg_good_word(cg_s(g, str));
                break;
            case CGE_TRADE:
                /* 33: give a (1..9999) of one good, get b (1..9999) of another: "give,get". */
                ok = e[1] == CG_ROLE_ALIAS_ALL && a >= 1 && a <= 9999 && b >= 1 && b <= 9999 && str != CG_NONE
                     && cg_str_ok(g, str, 0);
                if (ok) {
                    char give[48];
                    int at;
                    lstrcpynA(give, cg_s(g, str), sizeof give);
                    for (at = 0; give[at] != '\0' && give[at] != ','; ++at) {
                    }
                    ok = give[at] == ',' && (give[at] = '\0', cg_good_word(give)) && cg_good_word(give + at + 1)
                         && lstrcmpA(give, give + at + 1) != 0;
                }
                break;
            case CGE_GROUP:
                /* 34: the kind's word; a = the share made sick (1..100, "sick" only), else 0. */
                ok = str != CG_NONE && cg_str_ok(g, str, 0) && cg_group_kind_ok(cg_s(g, str), e[1] == CG_ROLE_ALIAS_ALL)
                     && b == 0 && (lstrcmpA(cg_s(g, str), "sick") == 0 ? a >= 1 && a <= 100 : a == 0);
                break;
            case CGE_VILLAGE:
                /* 35: event_timer, tech_level[:area], construction, weather:<word>. */
                ok = e[1] == CG_ROLE_ALIAS_ALL && str != CG_NONE && cg_str_ok(g, str, 0)
                     && cg_village_ok(cg_s(g, str), a, b);
                break;
            default: break;
            }
        }
        if (ok && e[0] == CGE_PREF && (e[2] & CG_PREF_RANDOM)) {
            ok = g->version >= 6 && str == CG_NONE && a == 0 && b == 0;   /* 24: a random like or dislike */
        } else if (ok && (e[0] == CGE_PREF || e[0] == CGE_SKILL || e[0] == CGE_SKILL_SET || e[0] == CGE_ACTION
                          || e[0] == CGE_DAMAGE || e[0] == CGE_REPAIR)) {
            ok = str != CG_NONE && cg_s(g, str)[0] != '\0';
        }
        if (!ok) {
            return cg_bad("an effect is not one this game can make");
        }
        if (g->version >= 6 && e[1] < (unsigned int)g->n_role && (cg_role_at(g, e[1])[13] & CG_ROLE_HEATHEN)
            && !cg_heathen_effect_ok(e)) {
            /* a Heathen's role: vanilla's own list only, whatever is ticked (No Safeguards too) */
            return cg_bad("an effect is not one a Heathen may have");
        }
    }
    for (i = 0; i < g->n_node; ++i) {
        const unsigned char *n = cg_node_at(g, i);
        unsigned int text = cg_u16(n + 6), vfirst = cg_u16(n + 8), vcount = cg_u16(n + 10);
        unsigned int cfirst = cg_u16(n + 12), ccount = cg_u16(n + 14), els = cg_u16(n + 16);
        unsigned int efirst = cg_u16(n + 18), ecount = cg_u16(n + 20);
        if (n[0] > 2u || n[1] > 1u || n[2] > 1u
            || (n[3] & ~(CG_NODE_AUTO_TEXT | CG_NODE_NEW_PAGE | CG_NODE_SOLIDARITY)) != 0u
            || ((n[3] & CG_NODE_NEW_PAGE) && n[1] != 0u)
            || ((n[3] & ~CG_NODE_SOLIDARITY) != 0u && (g->version < 6 || n[0] != CG_POPUP))   /* 25: auto lines on a v6 popup only */
            || !cg_str_ok(g, cg_u16(n + 4), 0) || !cg_str_ok(g, text, 1)
            || (vcount > 0u && vfirst + vcount > (unsigned int)g->n_variant)
            || (ccount > 0u && cfirst + ccount > (unsigned int)g->n_child)
            || (ecount > 0u && efirst + ecount > (unsigned int)g->n_effect)
            || (els != CG_NONE && (int)els >= g->n_node) || !cg_str_ok(g, cg_u16(n + 22), 1)
            || !cg_str_ok(g, cg_u16(n + 24), 1)) {
            return cg_bad("a node is not one this game can read");
        }
        if (g->version >= 6 && cg_u16(n + 26) != CG_NONE
            && (n[0] == CG_BRANCH || !cg_str_ok(g, cg_u16(n + 26), 0) || !cg_title_ok(g, cg_s(g, cg_u16(n + 26))))) {
            return cg_bad("a node's popup title is not one the game can show");
        }
        if (ccount > 256u) {
            return cg_bad("a node has more than 256 children");
        }
        if (n[0] == CG_QUESTION && ((i != g->start && g->version < 2)
                                    || (g->version < 4 ? ccount != 2u
                                                       : ccount < 2u
                                                         || ccount > (g->version >= 6 ? (unsigned int)CG_MAX_ANSWERS
                                                                                      : (unsigned int)CG_V4_ANSWERS))
                                    || els != CG_NONE || (g->version >= 2 && ecount != 0u))) {
            return cg_bad(g->version < 2 ? "a question is not the event's first popup with two choices"
                                         : g->version < 4 ? "a question does not have two choices, or makes changes"
                                         : g->version < 6 ? "a question does not have two to four choices, or makes "
                                                            "changes"
                                                          : "a question does not have two to seven choices, or makes "
                                                            "changes");
        }
        if (n[0] != CG_BRANCH && (cg_s(g, text)[0] == '\0' || !cg_text_ok(g, cg_s(g, text), 1, 0)
                                  || !cg_len_ok(g, cg_s(g, text), CG_TEXT_MAX, CE_LONG_TEXT_MAX))) {
            return cg_bad("a text is not one the game can show");
        }
        for (k = 0; k < (int)ccount; ++k) {
            const unsigned char *c = cg_child_at(g, (int)cfirst + k);
            unsigned int cond = cg_u16(c + 4), ce = cg_u16(c + 6);
            if ((int)cg_u16(c) >= g->n_node) {
                return cg_bad("a child names no node");
            }
            if (n[0] == CG_QUESTION) {
                const char *label = cg_s(g, cg_u16(c + 8));
                if (!cg_str_ok(g, cg_u16(c + 8), 0) || label[0] == '\0'
                    || (g->version >= 6 ? !cg_len_ok(g, label, CG_LABEL_V6 - 1, CE_LONG_LINE_BYTES - 1)
                                        : lstrlenA(label) >= CG_LABEL_BYTES)
                    || !cg_text_ok(g, label, 0, 1)) {
                    return cg_bad("a button label is not one the game can show");
                }
                /* Version 6: a choice shown only when its `if` holds. */
                if (g->version >= 6 && cond != CG_NONE && (int)cond >= g->n_cond) {
                    return cg_bad("a choice's condition is not one this game can read");
                }
            } else if (cg_u16(c + 2) < 1u || cg_u16(c + 2) > 10000u || (cond != CG_NONE && (int)cond >= g->n_cond)
                       || (ce != CG_NONE && (int)ce >= g->n_node)) {
                return cg_bad("a child is not one this game can read");
            }
            if (g->version >= 6 && cg_u16(c + 10) != CG_NONE && (int)cg_u16(c + 10) >= g->n_cond) {
                return cg_bad("a child's guard is not one this game can read");
            }
        }
    }
    if (g->req_cond != (int)CG_NONE
        && (g->req_cond >= g->n_cond || cg_cond_at(g, g->req_cond)[0] != CGC_ALL)) {
        return cg_bad("its requirement is not one this game can read");
    }
    if (!cg_acyclic(g)) {
        return cg_bad("its nodes go round in a circle");
    }
    return 1;
}

/* ---- The run ------------------------------------------------------------------------------------------------ */

typedef struct {
    int nodes;
    short node[CG_MAX_PATH];
    int fx;
    int fx_a[CG_MAX_FX];               /* each effect's roll, in the history's order (see cg_roll_effect) */
    int fx_b[CG_MAX_FX];
} cg_history;

/* One pool instance drawn (version 6): the pool, the instance (1..8), the item within the pool (CG_NONE: none was
   eligible, the empty text). */
typedef struct {
    unsigned short pool;
    unsigned short instance;
    unsigned short item;
} cg_pick;

/* Everything the run is, kept in the run's file as it is (no pointer). */
typedef struct {
    int phase;                         /* CG_* */
    int game;
    int slot;
    int question;                      /* the start node is a question */
    int pre_pages;                     /* the question's pages shown before its own popup */
    unsigned int planned;              /* the roles to bind (the needed ones and the optional ones planned) */
    unsigned int bound;
    unsigned int gone;                 /* the roles' villagers the event has killed or taken away */
    unsigned int patches;            /* the patches seen on (bit = the .cieg's patch index) */
    int record[CG_MAX_ROLES];
    unsigned int identity[CG_MAX_ROLES];
    int female[CG_MAX_ROLES];
    char name[CG_MAX_ROLES][CG_NAME_BYTES];
    /* THE HISTORY SO FAR (version 2: a question may be any node).  `path` is every node the run has reached, each
       question included, with every effect's roll; it grows one segment at a time -- from the start, or from an
       answer, up to the next question (included) or the end.  Each question's two segments are walked when it is
       asked (seg[q][button]: the popup can then be sized for the result either button shows, and a question asked
       again after a restore has the same histories), and the one answered is added to `path`. */
    cg_history path;
    int answers;                       /* questions answered */
    int asking;                        /* the display of the question on screen (CG_ASKED) */
    int choice;                        /* the last button answered, -1 */
    cg_history seg[CG_MAX_QUESTIONS][2];
    unsigned char seg_walked[CG_MAX_QUESTIONS];
    unsigned char answer[CG_MAX_QUESTIONS];
    short q_display[CG_MAX_QUESTIONS]; /* question q's display */
    short q_path[CG_MAX_QUESTIONS];    /* path.nodes / path.fx when it was asked (its own node included) */
    short q_fx[CG_MAX_QUESTIONS];
    int q_entry[CG_MAX_QUESTIONS];     /* the log entry's length before its "Choice:" line */
    int jobs_used;
    int display_count;
    int display_next;                  /* the next display to show: every display before it is shown, and its
                                          effects made */
    int display_used;
    int display_off[CG_MAX_DISPLAYS];
    char displays[CG_DISPLAY_BYTES];   /* each page's words, the names filled in (composed when shown) */
    /* Each display: its kind (CGD_*: a page, a question's result -- the first page after an answer -- or a
       question's own popup, display_node its node), the path's nodes whose effects it makes (jobs[job_first .. +
       job_count]), and -- for a quit -- when they were made and who was gone and who each role was just before it. */
    unsigned char display_kind[CG_MAX_DISPLAYS];
    short display_node[CG_MAX_DISPLAYS];
    unsigned char display_villager[CG_MAX_DISPLAYS];   /* it makes a villager's effect: refusal lines kept */
    short job_first[CG_MAX_DISPLAYS];
    short job_count[CG_MAX_DISPLAYS];
    short jobs[CG_MAX_PATH];
    unsigned __int64 applied_when[CG_MAX_DISPLAYS];   /* 0: nothing made there (yet) */
    unsigned int gone_at[CG_MAX_DISPLAYS];
    unsigned int identity_at[CG_MAX_DISPLAYS][CG_MAX_ROLES];
    char title[CE_TITLE_BYTES];
    unsigned __int64 when;             /* its purchase: only a later save paid for it */
    /* The Island Events log's ONE entry for the event (the owner, 2026-11-12): "  Event: <title>", "  Choice:
       <label>", then every change in page order; entry_at[k] is its length before display k's changes. */
    int entry_len;
    int entry_head;                    /* the header's length */
    int entry_at[CG_MAX_DISPLAYS];
    int sent_len[CG_MAX_DISPLAYS];     /* the entry's length handed to the log at display k (0: none) */
    char entry[CG_ENTRY_BYTES];
    /* Run file version 3 (format version 4: three or four answers): the third and fourth answers' segments, after
       everything version 2 kept (a version 2 file is read with these empty: its questions have two answers). */
    cg_history seg_more[CG_MAX_QUESTIONS][CG_V4_ANSWERS - 2];
    /* Run file version 4 (format version 6), after everything version 3 kept (a version 3 file is read with these
       empty: no picks, no alias, every choice shown, the cast strict): */
    cg_history seg_v6[CG_MAX_QUESTIONS][CG_MAX_ANSWERS - CG_V4_ANSWERS];   /* answers five to seven */
    int origin;                        /* CG_ORIGIN_* */
    int cast_mode;                     /* CG_CAST_* */
    unsigned int relaxed;              /* the roles cast with their requirements dropped (CG_CAST_PREFER) */
    signed char alias[CG_MAX_ROLES];   /* each alias role's member drawn (a role index), -1 none */
    int aliases_drawn;
    int pick_count;                    /* the path's pool picks */
    cg_pick picks[CG_MAX_PICKS];
    short q_picks[CG_MAX_QUESTIONS];   /* pick_count when question q was asked */
    unsigned char seg_pick_count[CG_MAX_QUESTIONS][CG_MAX_ANSWERS];
    cg_pick seg_picks[CG_MAX_QUESTIONS][CG_MAX_ANSWERS][CG_SEG_PICKS];
    /* Each question's buttons: how many are shown and the choice behind each (a choice whose `if` fails is not). */
    unsigned char q_shown[CG_MAX_QUESTIONS];
    unsigned char q_map[CG_MAX_QUESTIONS][CG_MAX_ANSWERS];
    int start_picks;                   /* the picks drawn at the purchase (a start question's own) */
    /* Each display's popup title (cie-v6-binary.md 14): a node title's string index + 1, 0 = the event's title. */
    unsigned short display_title[CG_MAX_DISPLAYS];
    /* Run file version 6, after everything version 5 kept (an older file is read with it 0: nobody swapped): the
       carrier roles whose partner carries instead (28 / 29 CG_FX_PARTNER_MAY_CARRY, decided once at the cast,
       cg_partner_carry_decide: the two roles' villagers swapped, so every page names who carries). */
    unsigned int carry_swapped;
    /* Run file version 6 (cie-v6-binary.md 35), after everything version 5 kept: each role's words' sex (cg.female)
       just before display k's effects were made, restored with identity_at when a quit rewinds to that page (a
       version 2-5 file is read with every display holding its cg.female). */
    unsigned char female_at[CG_MAX_DISPLAYS][CG_MAX_ROLES];
} cg_state;


static cg_state cg;
static cg_graph cg_g;
static char cg_labels[CG_MAX_ANSWERS][CE_LONG_LINE_BYTES];   /* the asked question's button labels, names filled
                                                                  in (with Scrolling Popups: practically any length) */

static int cg_active(int game);

/* The one popup on screen is the simple editor's question (story_custom.inc ce_op_simple), not a library event's: a
   run of the same game is never going while it is (the event slot is one). */
static int cg_op_is_simple(void) {
    return ce_op_simple != 0 && !cg_active(ce_op_simple);
}

/* The asked question's label for `button` (ce_choice_label, for a graph's question). */
static const char *cg_label(int button) {
    if (cg_op_is_simple()) {
        /* The simple editor's question in one popup (story_custom.inc ce_choice_begin): its own two labels, whole. */
        return button >= 0 && button < 2 ? ce_choice_store[ce_asked_store].labels[button] : "";
    }
    return button >= 0 && button < CG_MAX_ANSWERS ? cg_labels[button] : "";
}
/* A buffer as large as a file needs (at most CG_MAX_FILE), grown in the process heap: NULL when it cannot be. */
static unsigned char *cg_grow(unsigned char **buf, unsigned int *cap, unsigned int need) {
    unsigned int n;
    void *p;
    if (need > CG_MAX_FILE) {
        return NULL;
    }
    if (*buf != NULL && need <= *cap) {
        return *buf;
    }
    n = need < 0x10000u ? 0x10000u : (need + 0xFFFFu) & ~0xFFFFu;
    p = *buf != NULL ? HeapReAlloc(GetProcessHeap(), 0, *buf, n) : HeapAlloc(GetProcessHeap(), 0, n);
    if (p == NULL) {
        return NULL;
    }
    *buf = (unsigned char *)p;
    *cap = n;
    return *buf;
}

static unsigned char *cg_bytes;            /* the run's graph (cg_g.d points into it) */
static unsigned int cg_bytes_cap;

/* cg_bytes able to hold `size` bytes (cg_g is loaded again from it after every copy). */
static int cg_bytes_room(unsigned int size) {
    return cg_grow(&cg_bytes, &cg_bytes_cap, size) != NULL;
}
static unsigned int cg_bytes_size;

/* The choices of question `node` (two before format version 4, two to four from it, two to seven from 6). */
static int cg_answer_count(int node) {
    int n = node >= 0 && node < cg_g.n_node ? (int)cg_u16(cg_node_at(&cg_g, node) + 14) : 2;
    return n < 2 ? 2 : (n > CG_MAX_ANSWERS ? CG_MAX_ANSWERS : n);
}

/* Question `qi`'s segment for choice `b`, and its picks. */
static cg_history *cg_seg(int qi, int b) {
    return b < 2 ? &cg.seg[qi][b] : b < CG_V4_ANSWERS ? &cg.seg_more[qi][b - 2] : &cg.seg_v6[qi][b - CG_V4_ANSWERS];
}

static int cg_holds_cond(int i, int game, int depth);

/* The choices of question `node` shown now (version 6: a choice whose `if` fails is not), in order, into map[];
   their count. */
static int cg_shown_choices(int node, int game, unsigned char *map) {
    int b, n = 0, count = cg_answer_count(node);
    for (b = 0; b < count; ++b) {
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + b);
        if (cg_g.version < 6 || cg_holds_cond((int)cg_u16(c + 4), game, 0)) {
            map[n++] = (unsigned char)b;
        }
    }
    return n;
}

/* The buttons question `node` shows: its map when it is the question asked (or walked) as question `qi`, else as
   they would be now. */
static int cg_buttons(int node, int qi, unsigned char *map) {
    if (qi >= 0 && qi < CG_MAX_QUESTIONS && cg.seg_walked[qi] && cg.q_shown[qi] >= 2) {
        memcpy(map, cg.q_map[qi], CG_MAX_ANSWERS);
        return cg.q_shown[qi];
    }
    return cg_shown_choices(node, cg.game, map);
}

/* The text lines a question's popup keeps for its buttons past two (and its answer's first page, shown in it), in a
   popup laid out as `l`: from five buttons never so many that a page keeps fewer than three lines of text below
   the title the popup leads with (src/vv_cie_graph.py answer_room; the popup then grows past a two-button popup's
   height by the rest: tests/test_multi_answer_popup.py's 800 x 600 render check). */
static int cg_answer_room(int node, const ce_layout *l) {
    unsigned char map[CG_MAX_ANSWERS];
    int n = cg_buttons(node, -1, map);
    int room = CG_ANSWER_LINES[n < 2 ? 2 : n];
    int most = l->lines - (l->with_title ? 5 : 0) - 3;
    if (n > CG_V4_ANSWERS && room > most) {
        room = most > 0 ? most : 0;
    }
    return room;
}

/* G1: question `node` (asked as question `qi`) shows five or more buttons, so its answer's first page starts a fresh
   popup (the notice's: no room for buttons) instead of sharing the question's (docs/event-collection/cie-v6-binary.md
   11).  Two to four: as before. */
static int cg_one_popup(void);

static int cg_fresh_after(int node, int qi) {
    unsigned char map[CG_MAX_ANSWERS];
    return !cg_one_popup() && cg_g.version >= 6 && node >= 0 && cg_buttons(node, qi, map) > CG_V4_ANSWERS;
}

static int cg_answer_fresh_game;       /* the game whose last answer's page comes in a fresh popup (G1) */
static int cg_op_in_place;             /* one popup: a question asked in the popup already on screen (no count) */
static int cg_op_begun;                /* one popup: the game whose event ce_choice_begin just opened (its host takes it) */

/* One popup: whether ce_choice_begin just opened this game's event as a one-popup event (taken once). */
static int cg_op_begun_take(int game) {
    int r = game != 0 && cg_op_begun == game;
    cg_op_begun = 0;
    return r;
}

/* ce_choice_begin just opened the simple editor's question of `game` as a one-popup event (ce_op_simple). */
static void cg_op_begin_simple(int game) {
    cg_op_begun = game;
}

static char cg_shown_title[CE_LONG_LINE_BYTES * 4];   /* (defined below) */

/* One popup: the title in force on the text shown last (the simple editor's question: its own title). */
static const char *cg_op_title(void) {
    if (cg_op_is_simple()) {
        return ce_asked_title;
    }
    return cg_shown_title;
}

/* The buttons of the question on screen (CG_ASKED), else two. */
static int cg_asked_answers(void) {
    unsigned char map[CG_MAX_ANSWERS];
    return cg.phase == CG_ASKED && cg.asking >= 0 && cg.asking < cg.display_count
               ? cg_buttons(cg.display_node[cg.asking], cg.answers, map) : 2;
}
static story_village cg_village;
static int cg_display_armed;           /* the armed custom event (or question) is this run's next display */
static int cg_purchasing;              /* the purchase arms its first display: not yet busy */
static int cg_dirty;                   /* the run changed since its file was written */
static ce_event cg_stub;               /* the armed event of a display: the title, no text, no change */
static ce_choice cg_choice_stub;       /* ... and its question's (labels filled in when asked) */
static ce_event cg_one;                /* one villager's change, through ce_apply */

#ifdef VVFP_TEST
static int test_graph_patches = -1;    /* the patches on, -1 = as seen */
static int test_graph_scroll = -1;     /* Scrolling Popups installed (1) or not (0), -1 = as its companion says */
static int test_graph_scale = -1;      /* the scale mode, -1 = as the companion says */
static int test_graph_puzzles = -1;    /* the puzzles solved (bit = the adapter's index), -1 = as the game says */
static short test_graph_force[64];     /* nodes a draw picks whenever one of them can be drawn */
static int test_graph_forced;
typedef struct {
    int kind;                          /* 1 killed (words), 2 vanished (words), 3 faith conversion, 4 died with no
                                          body (words), 5 a baby lost (words) */
    int index;
    char words[96];
} cg_told_entry;
static cg_told_entry test_graph_told[32];
static int test_graph_told_count;

static void cg_test_tell(int kind, int index, const char *words) {
    if (test_graph_told_count < 32) {
        cg_told_entry *t = &test_graph_told[test_graph_told_count++];
        t->kind = kind;
        t->index = index;
        lstrcpynA(t->words, words != NULL ? words : "", sizeof t->words);
    }
}
#endif

static int cg_active(int game) {
    return cg.phase != CG_IDLE && cg.phase != CG_DONE && cg.game == game;
}

/* A run of `game` in the village on screen with popups still to come: the event slot is its own. */
static int cg_busy(int game) {
    return !cg_purchasing && cg_active(game) && story_village_is(game, &cg_village);
}

static int cg_owns_armed(int game) {
    return cg_display_armed && ce_armed && ce_armed_event.game == game && cg_active(game);
}

static int cg_owns_asked(int game) {
    return cg.phase == CG_ASKED && cg.game == game && ce_asked && ce_asked_game == game;
}

/* The question being answered (ce_choice_resolve, which has just taken it off the screen) is this run's. */
static int cg_answering(int game) {
    return cg.phase == CG_ASKED && cg.game == game;
}

/* ---- Who may be who --------------------------------------------------------------------------------------- */

static int cg_heathen(int game, const unsigned char *r) {
    return game == 5 && r[0x1CEC] != 0;
}

/* The special villagers a role leaves out unless it allows them (the shipped Aspiring Adventurer's). */
/* No Safeguards for Island Events (and Additional Events too), island_events_any_time in the installed patches'
   list (the owner, 2026-11-15, "for masochists"): no villager is protected from a new event -- nursing parents, the
   Golden Child, The Secret City's Tribal Chief, New Believers' story villagers -- and an event's requirement keeps
   only what it needs to make sense (its puzzles, its villagers, the children or the special villager it is about).
   STILL PROTECTED, ALWAYS (inanimate or not a living villager, the owner's rule; or a crash or corruption risk):
   The Lost Children's Esteemed Elder totem statues (never listed, c2_listed), The Secret City's stand-in records
   (+0xE94, not villagers), The Tree of Life's bodies and ghosts and New Believers' Reanimate in progress (never
   listed as living), the dead and the absent, the Golden Child in a sex change ("breaks things"), and New Believers'
   Heathens in a believers-only role (they are not the tribe's).  Defined below (it reads the installed list).
   ONLY FOR THE NATURAL DRAW'S EVENTS (the owner, 2026-11-15): Pick Island Event and Custom Island Events are
   independent of every new-event rule, No Safeguards on or off -- cg_ns_cast asks the cast's origin. */
static int cg_no_safeguards(int game);
static int cg_ns_cast(int game);

/* Record `r` is the game's special villager a role may prefer (35): the Golden Child in A New Home, the Tribal Chief
   in The Secret City -- by the game's own kind, whatever No Safeguards says. */
static int cg_special_kind(const ce_adapter *a, int game, const unsigned char *r) {
    int kind = ce_role(a, r, NULL);
    return (game == 1 && kind == STORY_KIND_GOLDEN_CHILD) || (game == 3 && kind == STORY_KIND_TRIBAL_CHIEF);
}

static int cg_special(const ce_adapter *a, int game, const unsigned char *r) {
    int kind = ce_role(a, r, NULL);
    if (cg_ns_cast(game)) {
        return 0;                      /* No Safeguards: no special villager is kept out */
    }
    switch (game) {
    case 1: return kind == STORY_KIND_GOLDEN_CHILD;
    case 3: return kind == STORY_KIND_TRIBAL_CHIEF;
    case 5: {
        int role = *(const int *)(r + 0x1CFC);
        return role >= 12 && role <= 17;
    }
    default: return 0;
    }
}

/* A villager no harm may reach (version 6, the owner's rule): a nursing parent of either sex (the game's own
   "expecting" field, one state with carrying), a special villager (cg_special); A New Home's and The Lost
   Children's listed() already leave out what is not a villager (The Lost Children's totems). */
static int cg_protected(const ce_adapter *a, int game, const unsigned char *r) {
    if (cg_ns_cast(game)) {
        return 0;                      /* No Safeguards: nobody living is protected */
    }
    return *(const int *)(r + a->off_pregnant) != 0 || cg_special(a, game, r);
}

/* A villager no harm ever reaches, whatever the role's `protected` says (the owner's model of 2026-11-14, cie-v6-
   binary.md 7): The Secret City's stand-in record and New Believers' story villagers (roles 12-17: the chief, the
   Retired Chief, the puzzles' Heathens -- whether harming them is safe is UNCONFIRMED, an owner question).  The Lost
   Children's totems are never listed (c2_listed), so never cast at all. */
static int cg_never_harmed(int game, const unsigned char *r) {
    if (game == 3) {
        return r[0xE94] != 0;
    }
    if (game == 5 && !cg_ns_cast(game)) {
        int role = *(const int *)(r + 0x1CFC);
        return role >= 12 && role <= 17;
    }
    return 0;                          /* (The Secret City's stand-in records above: never, No Safeguards or not) */
}

/* Record `r`'s best value in the skills `list` names (comma separated) that the game has, -1 when it has none. */
static int cg_skill_value(const ce_adapter *a, const unsigned char *r, const char *list) {
    char word[32];
    int best = -1, k, entry;
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            if (lstrcmpiA(a->skill_names[k], word) == 0) {
                int v = a->skills_float ? (int)*(const float *)(r + a->off_skills + 4u * (unsigned int)k)
                                        : *(const int *)(r + a->off_skills + 4u * (unsigned int)k);
                if (v > best) {
                    best = v;
                }
            }
        }
    }
    return best;
}

/* The game has none of the skills `list` names: its requirement does not apply there. */
static int cg_skills_known(const ce_adapter *a, const char *list) {
    char word[32];
    int k, entry;
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            if (lstrcmpiA(a->skill_names[k], word) == 0) {
                return 1;
            }
        }
    }
    return 0;
}

/* The roles whose requirements are dropped for this cast (CG_CAST_PREFER: nobody meets them); the safety rules
   are never dropped. */
static unsigned int cg_relax_mask;
static int cg_cast_now = CG_CAST_STRICT;

/* Is `role` the one a sex_change effect names (cie-v6-binary.md 29)?  Such a role never casts the Golden Child (the
   owner, 2026-11-15: "breaks things"); an alias's member drawn as him is refused when the effect is made. */
static int cg_sex_change_role(int role) {
    int i;
    for (i = 0; i < cg_g.n_effect; ++i) {
        const unsigned char *e = cg_effect_at(&cg_g, i);
        if (e[0] == CGE_SEX_CHANGE && (int)e[1] == role) {
            return 1;
        }
    }
    return 0;
}

/* Is `role` a carrier: a nursing_parent role, or the one a baby_lost effect names (cie-v6-binary.md 22)?  Only a
   villager born female is cast for it (the owner, 2026-11-15; cg_born_female). */
static int cg_carrier_role(int role) {
    const unsigned char *spec = cg_role_at(&cg_g, role);
    int i;
    if (cg_g.version >= 6 && spec[9] == 3) {
        return 1;
    }
    for (i = 0; i < cg_g.n_effect; ++i) {
        const unsigned char *e = cg_effect_at(&cg_g, i);
        if (e[0] == CGE_BABY_LOST && (int)e[1] == role) {
            return 1;
        }
    }
    return 0;
}

#ifdef VVFP_TEST
/* The birth sex as the test build sees it: -1 the real rule; else bit i set: record i was born male. */
static int test_graph_born_male = -1;
static int test_graph_no_deliver;      /* 1: a nursing effect conceives only (VvfpStoryProbeGraphNoDeliver) */
#endif

/* Was the villager in record `r` (record index `index`) born female?  "VVFP Gender Presentation.dll" keeps the birth
   sex (VvfpBornFemale); without it the save's Sex Changes log tells (native/shared/sex_change.h). */
static int cg_born_female(int game, const unsigned char *r, int index) {
    HMODULE dll;
    vvfp_gp_born_female_fn born;
#ifdef VVFP_TEST
    if (test_graph_born_male >= 0) {
        return index < 0 || index >= 31 || !(test_graph_born_male & (1 << index));
    }
#endif
    (void)index;
    dll = GetModuleHandleA(VVFP_GP_DLL);
    born = dll != NULL ? (vvfp_gp_born_female_fn)(void *)GetProcAddress(dll, "VvfpBornFemale") : NULL;
    return born != NULL ? born(game, r) == 1 : vv_sex_born_female_by_log(game, r);
}

#ifdef VVFP_TEST
/* The gender presentation as the test build's words see it (35): -1 the real one; else bit i set: record i is drawn
   with the other sex's look. */
static int test_graph_presented = -1;
#endif

/* 35: the villager in record `r` (index `index`) is drawn with the other sex's look ("VVFP Gender Presentation.dll";
   without it, never). */
static int cg_presented_other(int game, const unsigned char *r, int index) {
    vvfp_gp_api api;
#ifdef VVFP_TEST
    if (test_graph_presented >= 0) {
        return index >= 0 && index < 31 && (test_graph_presented & (1 << index)) != 0;
    }
#endif
    (void)index;
    return r != NULL && vvfp_gp_find(game, &api) && api.get(game, r) == 1;
}

static int cg_carrier_role(int role);

/* 35: whether role `role`'s words (pronouns, role-sex words) are a woman's, for the villager in record `r`: the sex
   the game records -- and for a carrier (a nursing_parent role, or one a baby_lost effect names) and a role that is
   or prefers The Secret City's Tribal Chief (the chief's title "headman" / "headwoman"), the sex they are drawn as
   with Gender Presentation (the owner, 2026-11-16: parent words follow Gender Presentation; without it, the recorded
   sex). */
static int cg_word_female(const ce_adapter *a, int game, int role, const unsigned char *r, int index) {
    const unsigned char *spec = cg_role_at(&cg_g, role);
    int female = ce_sex(a, r) == STORY_SEX_FEMALE;
    if (cg_g.version >= 6 && (cg_carrier_role(role) || spec[9] == CG_SPECIAL_CHIEF || spec[9] == CG_PREFER_CHIEF)
        && cg_presented_other(game, r, index)) {
        female = !female;
    }
    return female;
}

/* Is `role` the one a presentation effect names (cie-v6-binary.md 31)?  Such a role never casts the Golden Child,
   The Secret City's Tribal Chief or stand-in, or New Believers' story villagers (native/shared/sex_change.h
   vv_sex_change_refusal); an alias's member drawn as one of them is refused when the effect is made. */
static int cg_presentation_role(int role) {
    int i;
    for (i = 0; i < cg_g.n_effect; ++i) {
        const unsigned char *e = cg_effect_at(&cg_g, i);
        if (e[0] == CGE_PRESENTATION && (int)e[1] == role) {
            return 1;
        }
    }
    return 0;
}

/* The youngest a nursing parent is cast, in age units (20 a year): children never carry in events (the owner,
   2026-11-15).  baby_lost acts only on a nursing_parent role (the compiler's rule), so it never reaches a child. */
#define CG_NURSING_MIN_AGE (18 * 20)

/* Whether record `index` may be role `role` (any binding aside). */
/* The origin of the cast being made: the one being queued while nothing runs, else the running event's. */
static int cg_origin_now_get(void);
static int cg_casting_origin(void) {
    return cg.phase == CG_IDLE || cg.phase == CG_DONE ? cg_origin_now_get() : cg.origin;
}

/* No Safeguards for the cast being made: installed, and the cast is the natural draw's (never Pick Island Event's
   or a Custom Island Event's). */
static int cg_ns_cast(int game) {
    return cg_casting_origin() == CG_ORIGIN_NATURAL && cg_no_safeguards(game);
}

/* story_traits.inc: the new island events' story traits. */
static int rs_set_trait(int game, int index, unsigned int trait);
static int rs_has_trait(int game, const unsigned char *record, unsigned int trait);

/* The roles a conversion names (a Heathen becomes a believer: a status effect with value 0, the faith change the
   data side defines), an alias's members with it.  With No Safeguards on, only these may take a Heathen. */
static unsigned int cg_conversion_roles(void) {
    unsigned int mask = 0;
    int i;
    for (i = 0; cg_g.d != NULL && i < cg_g.n_effect; ++i) {
        const unsigned char *e = cg_effect_at(&cg_g, i);
        if (e[0] == CGE_STATUS && cg_u32(e + 4) == 0u && e[1] < (unsigned int)cg_g.n_role) {
            mask |= 1u << e[1];
            if (cg_role_at(&cg_g, e[1])[0] >= CG_ROLE_ALIAS) {
                mask |= cg_u16(cg_role_at(&cg_g, e[1]) + 14);
            }
        }
    }
    return mask;
}

static int cg_eligible(const ce_adapter *a, int game, int role, int index) {
    const unsigned char *spec = cg_role_at(&cg_g, role);
    const unsigned char *r = a->record(index);
    int sex;
    if (spec[0] != CG_ROLE_VILLAGER || r == NULL || !a->listed(r)) {
        return 0;
    }
    if (game == 3 && r[0xE94] != 0) {
        return 0;                      /* The Secret City's stand-in record */
    }
    /* Safety: never dropped. */
    if ((spec[1] & CG_ROLE_NURSING) && *(const int *)(r + a->off_pregnant) != 0 && !cg_ns_cast(game)) {
        return 0;
    }
    if ((spec[1] & CG_ROLE_SPECIAL) && cg_special(a, game, r)) {
        return 0;
    }
    if (cg_g.version >= 6 && spec[9] == 3 && ce_age(a, r) < CG_NURSING_MIN_AGE) {
        return 0;                      /* a nursing parent is an adult of 18 or more */
    }
    if (game == 1 && ce_role(a, r, NULL) == STORY_KIND_GOLDEN_CHILD && cg_sex_change_role(role)
        && !vv_sex_gc_draws_follow(game)) {
        return 0;                      /* the Golden Child: a sex change only when his draws follow (option 1) */
    }
    if (game == 5 && cg_g.version >= 6 && (spec[13] & CG_ROLE_HEATHEN)) {
        /* A Heathen's role: as the game's own picker 0x471870 picks one (Heathens-only 1, special roles 0): a
           Heathen, never roles 12-17 (the Heathen Doctor, Chief, the three Masters, the Heathen Mommy), never sick,
           health above 0 (listed: present, not a body or a spirit); carrying or nursing allowed.  The role's own
           ages and sex still apply below. */
        int hrole = *(const int *)(r + 0x1CFC);
        if (!cg_heathen(game, r) || (hrole >= 12 && hrole <= 17) || r[0x1C48] != 0 || cg_health_now(game, r) <= 0) {
            return 0;
        }
    } else if (game == 5 && cg_heathen(game, r) && cg_ns_cast(game) && !((cg_conversion_roles() >> role) & 1u)) {
        /* No Safeguards (the owner, 2026-11-15): a Heathen is cast only in a role whose purpose is a conversion;
           Guardians of Isola's rules and words stay as they are. */
        return 0;
    }
    if (cg_presentation_role(role) && vv_sex_change_refusal(game, r, index) != VV_SEX_OK) {
        return 0;                      /* nor any special villager for a gender presentation */
    }
    if (cg_carrier_role(role) && !cg_born_female(game, r, index)) {
        return 0;                      /* only a villager born female is cast as a carrier */
    }
    if ((spec[1] & CG_ROLE_BELIEVERS) && cg_heathen(game, r) && !(game == 5 && (spec[13] & CG_ROLE_HEATHEN))) {
        return 0;
    }
    if (cg_g.version >= 6 && (spec[1] & CG_ROLE_PROTECTED) && cg_protected(a, game, r)) {
        return 0;
    }
    if (cg_g.version >= 6 && (spec[1] & CG_ROLE_HARM) && cg_never_harmed(game, r)) {
        return 0;                      /* never harmed, even with protected "allow" */
    }
    if (cg_g.version >= 6 && (spec[13] & CG_ROLE_SPEAKS) && rs_has_trait(game, r, CG_TRAIT_MUTE)) {
        return 0;                      /* a story-mute villager never takes a role whose words have them speak */
    }
    /* The requirements (version 6: dropped for a role nobody meets when the cast prefers them). */
    if (cg_relax_mask & (1u << role)) {
        return 1;
    }
    if (ce_age(a, r) < 20 * (int)spec[3]) {
        return 0;
    }
    sex = ce_sex(a, r);
    if ((spec[2] == 1 && sex != STORY_SEX_MALE) || (spec[2] == 2 && sex != STORY_SEX_FEMALE)) {
        return 0;
    }
    if (cg_g.version >= 6) {
        unsigned int skills = cg_u16(spec + 10);
        if (spec[8] != 0 && ce_age(a, r) >= 20 * ((int)spec[8] + 1)) {
            return 0;                  /* older than the role's max age in whole years */
        }
        if (skills != CG_NONE && cg_skills_known(a, cg_s(&cg_g, skills))
            && cg_skill_value(a, r, cg_s(&cg_g, skills)) < (int)spec[12]) {
            return 0;
        }
        switch (spec[9]) {
        case 1: if (ce_role(a, r, NULL) != STORY_KIND_GOLDEN_CHILD) { return 0; } break;
        case 2: if (ce_role(a, r, NULL) != STORY_KIND_TRIBAL_CHIEF) { return 0; } break;
        case 3: if (*(const int *)(r + a->off_pregnant) == 0) { return 0; } break;
        default: break;
        }
    }
    return 1;
}

/* Kuhn's matching: the roles in `roles` can each be a different eligible villager, none of `used`. */
static int cg_owner[CE_MAX_RECORDS];

static int cg_augment(const ce_adapter *a, int game, int role, unsigned char *seen, const unsigned char *used) {
    int i;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        if (seen[i] || used[i] || !cg_eligible(a, game, role, i)) {
            continue;
        }
        seen[i] = 1;
        if (cg_owner[i] < 0 || cg_augment(a, game, cg_owner[i], seen, used)) {
            cg_owner[i] = role;
            return 1;
        }
    }
    return 0;
}

/* VERSION 3: AGE GAPS.  A villager role may be "at most N years apart" from another (the role's bytes 6 and 7:
   that role + 1, N).  The matching above cannot see a rule between two roles, so with a gap the roles are filled
   by a search: each role in turn takes an eligible villager not taken, within every gap of the roles already
   filled (cg_try), until all are filled or none can be (CG_GAP_STEPS bounds it: a village too big to search is
   refused rather than hung).  Ages in the games' own units, 20 a year (ce_age). */
#define CG_GAP_STEPS 400000
static int cg_try[CG_MAX_ROLES];       /* the record each role holds in this search, -1 */
static int cg_gap_steps;

/* ---- Kinship (docs/event-collection/cie-v6-binary.md 21) ----------------------------------------------------

   A villager role may need to be the spouse, parent, child or sibling of another role's villager: a rule between
   two roles, filled by the age gaps' search.  Read from the game's own data, never from a name alone: a child's
   recorded father and mother (name, head and body on its own record in The Lost Children to New Believers; A New
   Home keeps none, so there the patcher's parentage sidecar, "VVFP VV1 Parentage.dll", while it is loaded), and a
   carrier's expected father.  A parent field is villager X when its name, head and body are X's now; a default
   father (The Lost Children's Gong "?", The Tree of Life's and New Believers' "Joey", A New Home's sidecar
   "Unknown") is nobody.  No game keeps a spouse: "spouse" is the two recorded parents of one living villager, or a
   carrier and the expected father of the baby carried. */
typedef struct {
    char name[CG_NAME_BYTES];
    int head, body;                    /* -1 unknown */
} cg_person;

static cg_person cg_kin_me[CE_MAX_RECORDS];        /* each listed villager as a parent field would name them */
static cg_person cg_kin_par[CE_MAX_RECORDS][2];    /* ... their recorded father [0] and mother [1] */
static cg_person cg_kin_exp[CE_MAX_RECORDS];       /* ... the father of the baby they carry */
static short cg_kin_pidx[CE_MAX_RECORDS][2];       /* ... the living villager their father [0] / mother [1] names,
                                                       -1 none (gap C2: links through a living villager) */
static unsigned char cg_kin_live[CE_MAX_RECORDS];
static int cg_kin_game;                /* the game cg_kin_fill read */

#ifdef VVFP_TEST
/* A New Home's parentage sidecar for the test build: a record's father and mother (names empty: none). */
static cg_person test_graph_vv1_par[CE_MAX_RECORDS][2];
static cg_person test_graph_vv1_exp[CE_MAX_RECORDS];
static int test_graph_vv1_parents;     /* 1: the table above stands for the sidecar */
#endif

/* Role `r`'s relation: its kind (0 none) and the other role into *other. */
static int cg_relation(int r, int *other) {
    int i;
    for (i = 0; i < cg_g.n_rel; ++i) {
        const unsigned char *rel = cg_g.d + cg_g.o_rel + 4u * (unsigned int)i;
        if ((int)rel[0] == r) {
            *other = rel[2];
            return rel[1];
        }
    }
    return 0;
}

static void cg_person_unknown(cg_person *p) {
    p->name[0] = '\0';
    p->head = p->body = -1;
}

static void cg_person_field(const ce_adapter *a, cg_person *p, const unsigned char *r, unsigned int name,
                            int capacity, unsigned int head, unsigned int body) {
    ce_copy_name(p->name, CG_NAME_BYTES, r + name, capacity < a->name_bytes ? capacity : a->name_bytes);
    p->head = *(const int *)(r + head);
    p->body = *(const int *)(r + body);
}

/* A New Home: the parentage sidecar's parents and expected father of record `i` (nothing without the companion). */
static void cg_kin_vv1(int i) {
    typedef int (__stdcall *names_fn)(int, char *, char *, int);
    typedef int (__stdcall *looks_fn)(int, int *);
    typedef int (__stdcall *expected_fn)(int, int *, char *, int);
    HMODULE module;
    names_fn names;
    looks_fn looks;
    expected_fn expected;
    int out[4];
#ifdef VVFP_TEST
    if (test_graph_vv1_parents) {
        cg_kin_par[i][0] = test_graph_vv1_par[i][0];
        cg_kin_par[i][1] = test_graph_vv1_par[i][1];
        cg_kin_exp[i] = test_graph_vv1_exp[i];
        return;
    }
#endif
    module = GetModuleHandleA("VVFP VV1 Parentage.dll");
    if (module == NULL) {
        return;
    }
    names = (names_fn)(void *)GetProcAddress(module, "Vv1ParentageQueryNames");
    looks = (looks_fn)(void *)GetProcAddress(module, "Vv1ParentageQuery");
    expected = (expected_fn)(void *)GetProcAddress(module, "Vv1ParentageQueryExpectedFather");
    if (names != NULL && looks != NULL && names(i, cg_kin_par[i][0].name, cg_kin_par[i][1].name, CG_NAME_BYTES)
        && looks(i, out)) {
        cg_kin_par[i][0].head = out[0];
        cg_kin_par[i][0].body = out[1];
        cg_kin_par[i][1].head = out[2];
        cg_kin_par[i][1].body = out[3];
    } else {
        cg_person_unknown(&cg_kin_par[i][0]);
        cg_person_unknown(&cg_kin_par[i][1]);
    }
    if (expected != NULL && expected(i, out, cg_kin_exp[i].name, CG_NAME_BYTES)) {
        cg_kin_exp[i].head = out[0];
        cg_kin_exp[i].body = out[1];
    } else {
        cg_person_unknown(&cg_kin_exp[i]);
    }
}

/* Each listed villager's own name and looks, recorded parents and expected father, read once for a search. */
static int cg_kin_is(int game, const cg_person *p, int x, int father);

/* Each listed villager's own name and looks, recorded parents and expected father, read now (whatever relations
   the graph has: the dead-relative condition reads them too), and the living villager each parent field names. */
static void cg_kin_read(const ce_adapter *a, int game);

static void cg_kin_fill(const ce_adapter *a, int game) {
    if (cg_g.n_rel == 0 || game < 1 || game > 5) {
        return;
    }
    cg_kin_read(a, game);
}

static void cg_kin_read(const ce_adapter *a, int game) {
    /* The expected father on the carrier (VV2-VV5: the conception copies his name, head and body there). */
    static const unsigned int EXP[6][3] = { { 0 }, { 0 }, { 0x5C0u, 0x5E0u, 0x5DCu }, { 0xE48u, 0xE68u, 0xE64u },
                                            { 0x1C10u, 0x1C30u, 0x1C2Cu }, { 0x1C10u, 0x1C30u, 0x1C2Cu } };
    int i, k;
    if (game < 1 || game > 5) {
        return;
    }
    cg_kin_game = game;
    memset(cg_kin_live, 0, sizeof cg_kin_live);
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        cg_kin_live[i] = (unsigned char)(r != NULL && a->listed(r));
        cg_person_unknown(&cg_kin_me[i]);
        cg_person_unknown(&cg_kin_par[i][0]);
        cg_person_unknown(&cg_kin_par[i][1]);
        cg_person_unknown(&cg_kin_exp[i]);
        if (!cg_kin_live[i]) {
            continue;
        }
        cg_person_field(a, &cg_kin_me[i], r, a->off_name, a->name_bytes, a->off_head, a->off_body);
        if (a->off_father_name != 0u) {
            cg_person_field(a, &cg_kin_par[i][0], r, a->off_father_name, a->name_bytes, a->off_father_head,
                            a->off_father_body);
            cg_person_field(a, &cg_kin_par[i][1], r, a->off_mother_name, a->name_bytes, a->off_mother_head,
                            a->off_mother_body);
            if (*(const int *)(r + a->off_pregnant) != 0 && EXP[game][0] != 0u) {
                cg_person_field(a, &cg_kin_exp[i], r, EXP[game][0], 0x18, EXP[game][1], EXP[game][2]);
            }
        } else if (game == 1) {
            cg_kin_vv1(i);
            if (*(const int *)(r + a->off_pregnant) == 0) {
                cg_person_unknown(&cg_kin_exp[i]);
            }
        }
    }
    for (i = 0; i < CE_MAX_RECORDS; ++i) {
        cg_kin_pidx[i][0] = cg_kin_pidx[i][1] = -1;
        for (k = 0; cg_kin_live[i] && k < CE_MAX_RECORDS; ++k) {
            if (k == i || !cg_kin_live[k]) {
                continue;
            }
            if (cg_kin_pidx[i][0] < 0 && cg_kin_is(game, &cg_kin_par[i][0], k, 1)) {
                cg_kin_pidx[i][0] = (short)k;
            }
            if (cg_kin_pidx[i][1] < 0 && cg_kin_is(game, &cg_kin_par[i][1], k, 0)) {
                cg_kin_pidx[i][1] = (short)k;
            }
        }
    }
}

/* A game's default father: nobody (the parentage rules). */
static int cg_default_father(int game, const cg_person *p) {
    if (game == 1) {
        return lstrcmpA(p->name, "Unknown") == 0 && p->head == 0 && p->body == 0;
    }
    if (game == 2) {
        return lstrcmpA(p->name, "?") == 0 && p->head == 0 && p->body == 0;
    }
    if (game == 4 || game == 5) {
        /* New Believers also has the Heathen Mommy's "Unknown" (2, 2) (src/vv_genealogy.py GAME_DEFAULT_FATHERS) */
        return (lstrcmpA(p->name, "Joey") == 0 || lstrcmpA(p->name, "Joey Joerson") == 0
                || (game == 5 && lstrcmpA(p->name, "Unknown") == 0)) && p->head == 2 && p->body == 2;
    }
    return 0;
}

/* Parent field `p` (a father's when `father`) names the villager in record `x`. */
static int cg_kin_is(int game, const cg_person *p, int x, int father) {
    const cg_person *me = &cg_kin_me[x];
    if (p->name[0] == '\0' || me->name[0] == '\0' || (father && cg_default_father(game, p))) {
        return 0;
    }
    return lstrcmpA(p->name, me->name) == 0 && p->head == me->head && p->body == me->body;
}

/* Two parent fields name one person (a real one: never a default father). */
static int cg_kin_same(int game, const cg_person *p, const cg_person *q, int father) {
    if (p->name[0] == '\0' || (father && cg_default_father(game, p))) {
        return 0;
    }
    return lstrcmpA(p->name, q->name) == 0 && p->head == q->head && p->body == q->body;
}

/* Whether the villager in record `x` is relation `kind` of the villager in record `y` (cg_kin_fill first). */
static int cg_kin(int game, int kind, int x, int y) {
    int k;
    if (x < 0 || y < 0 || x >= CE_MAX_RECORDS || y >= CE_MAX_RECORDS || x == y || !cg_kin_live[x]
        || !cg_kin_live[y]) {
        return 0;
    }
    switch (kind) {
    case CG_REL_PARENT:
        return cg_kin_is(game, &cg_kin_par[y][0], x, 1) || cg_kin_is(game, &cg_kin_par[y][1], x, 0);
    case CG_REL_CHILD:
        return cg_kin_is(game, &cg_kin_par[x][0], y, 1) || cg_kin_is(game, &cg_kin_par[x][1], y, 0);
    case CG_REL_SIBLING:
        return cg_kin_same(game, &cg_kin_par[x][1], &cg_kin_par[y][1], 0)
               || cg_kin_same(game, &cg_kin_par[x][0], &cg_kin_par[y][0], 1);
    case CG_REL_GRANDPARENT:
        /* gap C2: x is a recorded parent of a living recorded parent of y */
        for (k = 0; k < 2; ++k) {
            int p = cg_kin_pidx[y][k];
            if (p >= 0 && p != x && (cg_kin_pidx[p][0] == x || cg_kin_pidx[p][1] == x)) {
                return 1;
            }
        }
        return 0;
    case CG_REL_GRANDCHILD:
        return cg_kin(game, CG_REL_GRANDPARENT, y, x);
    case CG_REL_AUNT:
        /* x is a sibling of a living recorded parent of y */
        for (k = 0; k < 2; ++k) {
            int p = cg_kin_pidx[y][k];
            if (p >= 0 && p != x && cg_kin(game, CG_REL_SIBLING, x, p)) {
                return 1;
            }
        }
        return 0;
    case CG_REL_COUSIN: {
        /* a living recorded parent of x and one of y are siblings */
        int j;
        for (k = 0; k < 2; ++k) {
            for (j = 0; j < 2; ++j) {
                int p = cg_kin_pidx[x][k], q = cg_kin_pidx[y][j];
                if (p >= 0 && q >= 0 && p != q && p != y && q != x && cg_kin(game, CG_REL_SIBLING, p, q)) {
                    return 1;
                }
            }
        }
        return 0;
    }
    case CG_REL_SPOUSE:
        if (cg_kin_is(game, &cg_kin_exp[x], y, 1) || cg_kin_is(game, &cg_kin_exp[y], x, 1)) {
            return 1;                  /* one carries the other's baby */
        }
        for (k = 0; k < CE_MAX_RECORDS; ++k) {
            if (k != x && k != y && cg_kin_live[k]
                && ((cg_kin_is(game, &cg_kin_par[k][0], x, 1) && cg_kin_is(game, &cg_kin_par[k][1], y, 0))
                    || (cg_kin_is(game, &cg_kin_par[k][0], y, 1) && cg_kin_is(game, &cg_kin_par[k][1], x, 0)))) {
                return 1;              /* the recorded father and mother of one living villager */
            }
        }
        return 0;
    default:
        return 0;
    }
}

/* cie-v6-binary.md 21a: whether no living, listed villager has the name of parent field `p` (a real one: a default
   father is nobody, an empty field nobody).  By the name alone, so a parent whose look changed is still alive. */
static int cg_kin_lost(int game, const cg_person *p, int father) {
    int k;
    if (p->name[0] == '\0' || (father && cg_default_father(game, p))) {
        return 0;
    }
    for (k = 0; k < CE_MAX_RECORDS; ++k) {
        if (cg_kin_live[k] && lstrcmpA(cg_kin_me[k].name, p->name) == 0) {
            return 0;
        }
    }
    return 1;
}

/* Whether the villager in record `x` lost a recorded parent or a co-parent (cg_kin_read first).  A dead child or
   sibling is on no record the engine reads, so it is never claimed. */
static int cg_dead_relative(int game, int x) {
    int k;
    if (x < 0 || x >= CE_MAX_RECORDS || !cg_kin_live[x]) {
        return 0;
    }
    if (cg_kin_lost(game, &cg_kin_par[x][0], 1) || cg_kin_lost(game, &cg_kin_par[x][1], 0)
        || cg_kin_lost(game, &cg_kin_exp[x], 1)) {
        return 1;                      /* a parent, or the father of the baby carried */
    }
    for (k = 0; k < CE_MAX_RECORDS; ++k) {
        if (k == x || !cg_kin_live[k]) {
            continue;
        }
        if ((cg_kin_is(game, &cg_kin_par[k][0], x, 1) && cg_kin_lost(game, &cg_kin_par[k][1], 0))
            || (cg_kin_is(game, &cg_kin_par[k][1], x, 0) && cg_kin_lost(game, &cg_kin_par[k][0], 1))) {
            return 1;                  /* the other recorded parent of one of their children */
        }
    }
    return 0;
}

static int cg_has_gaps(void) {
    int r;
    if (cg_g.n_rel > 0) {
        return 1;                      /* 21: a kinship relation is a rule between two roles too */
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        if (cg_role_at(&cg_g, r)[6] != 0) {
            return 1;
        }
    }
    return 0;
}

static void cg_try_reset(void) {
    int r;
    for (r = 0; r < CG_MAX_ROLES; ++r) {
        cg_try[r] = -1;
    }
}

/* Record `i` as role `r` keeps every age gap and kinship relation (21) with the roles already filled. */
static int cg_gap_ok(const ce_adapter *a, int r, int i) {
    const unsigned char *spec = cg_role_at(&cg_g, r);
    int q, other = -1, kind = cg_relation(r, &other);
    for (q = 0; q < cg_g.n_role; ++q) {
        const unsigned char *qs = cg_role_at(&cg_g, q);
        int years, diff, qother = -1, qkind;
        if (q == r || cg_try[q] < 0 || (cg_relax_mask & ((1u << r) | (1u << q)))) {
            continue;
        }
        if (kind != 0 && other == q && !cg_kin(cg_kin_game, kind, i, cg_try[q])) {
            return 0;                  /* r's villager must be that relation of q's */
        }
        qkind = cg_relation(q, &qother);
        if (qkind != 0 && qother == r && !cg_kin(cg_kin_game, qkind, cg_try[q], i)) {
            return 0;                  /* q's villager must be that relation of r's */
        }
        if (spec[6] == (unsigned char)(q + 1)) {
            years = spec[7];
        } else if (qs[6] == (unsigned char)(r + 1)) {
            years = qs[7];
        } else {
            continue;
        }
        diff = ce_age(a, a->record(i)) - ce_age(a, a->record(cg_try[q]));
        if (diff < 0) {
            diff = -diff;
        }
        if (diff > 20 * years) {
            return 0;
        }
    }
    return 1;
}

static int cg_search(const ce_adapter *a, int game, unsigned int roles, unsigned char *used) {
    int r, i;
    if (roles == 0u) {
        return 1;
    }
    if (++cg_gap_steps > CG_GAP_STEPS) {
        return 0;
    }
    for (r = 0; r < cg_g.n_role && !(roles & (1u << r)); ++r) {
    }
    if (r >= cg_g.n_role || cg_role_at(&cg_g, r)[0] != 0) {
        return cg_search(a, game, roles & ~(1u << r), used);
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        int ok;
        if (used[i] || !cg_eligible(a, game, r, i) || !cg_gap_ok(a, r, i)) {
            continue;
        }
        used[i] = 1;
        cg_try[r] = i;
        ok = cg_search(a, game, roles & ~(1u << r), used);
        used[i] = 0;
        cg_try[r] = -1;
        if (ok) {
            return 1;
        }
    }
    return 0;
}

static int cg_matchable(const ce_adapter *a, int game, unsigned int roles, const unsigned char *used) {
    unsigned char seen[CE_MAX_RECORDS];
    int r;
    if (cg_has_gaps()) {
        static unsigned char copy[CE_MAX_RECORDS];
        cg_kin_fill(a, game);          /* 21: the families as they are now */
        memcpy(copy, used, sizeof copy);
        cg_gap_steps = 0;
        return cg_search(a, game, roles, copy);
    }
    for (r = 0; r < CE_MAX_RECORDS; ++r) {
        cg_owner[r] = -1;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        if (!(roles & (1u << r)) || cg_role_at(&cg_g, r)[0] != 0) {
            continue;
        }
        memset(seen, 0, sizeof seen);
        if (!cg_augment(a, game, r, seen, used)) {
            return 0;
        }
    }
    return 1;
}

/* The villager roles the event needs. */
static unsigned int cg_needed(void) {
    unsigned int roles = 0;
    int r;
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        if (spec[0] == 0 && !(spec[1] & CG_ROLE_OPTIONAL)) {
            roles |= 1u << r;
        }
    }
    return roles;
}

/* VERSION 6 CASTING.  STRICT (the rare roll, Pick Island Event): every requirement must hold.  PREFER (bought
   through the library): the requirements are kept where the village can meet them; a role nobody meets has its
   requirements dropped, then -- when the roles still cannot be filled together -- every role's; the safety rules
   (living, listed, the stand-in, Heathens, the protected filter) never.  1 when `roles` can then be filled, the
   dropped roles in cg_relax_mask. */
static int cg_plan_cast(const ce_adapter *a, int game, unsigned int roles, const unsigned char *used) {
    int r, i;
    cg_relax_mask = 0;
    cg_try_reset();
    if (cg_matchable(a, game, roles, used)) {
        return 1;
    }
    if (cg_cast_now != CG_CAST_PREFER || cg_g.version < 6) {
        return 0;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        if (!(roles & (1u << r)) || cg_role_at(&cg_g, r)[0] != CG_ROLE_VILLAGER) {
            continue;
        }
        for (i = 0; i < a->record_count && i < CE_MAX_RECORDS && (used[i] || !cg_eligible(a, game, r, i)); ++i) {
        }
        if (i >= a->record_count || i >= CE_MAX_RECORDS) {
            cg_relax_mask |= 1u << r;
        }
    }
    cg_try_reset();
    if (cg_matchable(a, game, roles, used)) {
        return 1;
    }
    cg_relax_mask |= roles;
    cg_try_reset();
    return cg_matchable(a, game, roles, used);
}

/* Whether the village can fill the planned roles now. */
static int cg_feasible(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char used[CE_MAX_RECORDS];
    if (a == NULL) {
        return 0;
    }
    memset(used, 0, sizeof used);
    cg_try_reset();
    cg_relax_mask = cg.relaxed;
    cg_cast_now = cg.cast_mode;
    if (cg_matchable(a, game, cg.planned, used)) {
        return 1;
    }
    return cg_plan_cast(a, game, cg.planned, used);
}

/* Role `r`'s villager if it is an alias: the member drawn (-1 none), else `r`. */
static int cg_resolve_role(int r) {
    if (r < 0 || r >= cg_g.n_role) {
        return -1;
    }
    return cg_role_at(&cg_g, r)[0] >= CG_ROLE_ALIAS ? cg.alias[r] : r;   /* an alias or an other role */
}

/* Every alias role drawn among its bound (or planned, before the binding) members, in role order, each members[
   ce_random_below(count)] (docs/event-collection/cie-v6-binary.md 6.1); once a run. */
static void cg_draw_aliases(const ce_adapter *a, unsigned int bound) {
    int r, k;
    if (cg.aliases_drawn) {
        return;
    }
    cg.aliases_drawn = 1;
    for (r = 0; r < CG_MAX_ROLES; ++r) {
        cg.alias[r] = -1;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        int members[CG_MAX_ROLES], n = 0;
        if (spec[0] != CG_ROLE_ALIAS) {
            continue;
        }
        for (k = 0; k < cg_g.n_role; ++k) {
            if ((cg_u16(spec + 14) & (1u << k)) && (bound & (1u << k))) {
                members[n++] = k;
            }
        }
        cg.alias[r] = (signed char)(n > 0 ? members[ce_random_below(a, n)] : -1);
    }
    /* G2: each "other" role, with no roll: its alias's member that was not drawn (unbound when that member or the
       alias is). */
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        int al;
        if (spec[0] != CG_ROLE_OTHER) {
            continue;
        }
        for (al = 0; al < cg_g.n_role && cg_u16(spec + 14) != (1u << al); ++al) {
        }
        if (al >= cg_g.n_role || cg.alias[al] < 0) {
            continue;
        }
        for (k = 0; k < cg_g.n_role; ++k) {
            if ((cg_u16(cg_role_at(&cg_g, al) + 14) & (1u << k)) && k != cg.alias[al] && (bound & (1u << k))) {
                cg.alias[r] = (signed char)k;
            }
        }
    }
}

/* ---- Named strangers (docs/event-collection/cie-v6-binary.md 16) ------------------------------------------ */

/* The game's own first-name list of one sex (read where the game keeps it), else the same list built in. */
static const char *cg_names_list(int game, int female) {
    static char list[2048];
    unsigned int n;
    int ok = 1;
    if (game < 1 || game > 5) {
        return "";
    }
    n = CG_NAMES_BYTES[game][female];
    if (n == 0u || n >= sizeof list) {
        return CG_NAMES_TEXT[game][female];
    }
    __try {
        memcpy(list, (const void *)(uintptr_t)CG_NAMES_VA[game][female], n);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 0;
    }
    list[n] = '\0';
    {
        unsigned int i;
        for (i = 0; ok && i < n; ++i) {
            char c = list[i];
            ok = c == ',' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
        }
        ok = ok && list[0] != ',' && list[n - 1] == ',';
    }
    return ok ? list : CG_NAMES_TEXT[game][female];
}

/* `a` and `b` agree in their first `n` bytes, ignoring the case of A-Z. */
static int cg_same_ci(const char *a, const char *b, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        char x = a[i], y = b[i];
        x = (char)(x >= 'a' && x <= 'z' ? x - 'a' + 'A' : x);
        y = (char)(y >= 'a' && y <= 'z' ? y - 'a' + 'A' : y);
        if (x != y) {
            return 0;
        }
    }
    return 1;
}

/* Whether `name` (`n` bytes) is a living, listed villager's first name or a named stranger's bound before role
   `upto`, ignoring case. */
static int cg_name_taken(const ce_adapter *a, int upto, const char *name, int n) {
    char have[CG_NAME_BYTES];
    int i, k;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *rec = a->record(i);
        if (rec == NULL || !a->listed(rec)) {
            continue;
        }
        ce_copy_name(have, CG_NAME_BYTES, rec + a->off_name, a->name_bytes);
        for (k = 0; have[k] != '\0' && have[k] != ' '; ++k) {
        }
        have[k] = '\0';
        if (k == n && cg_same_ci(have, name, n)) {
            return 1;
        }
    }
    for (i = 0; i < upto; ++i) {
        if (cg_role_at(&cg_g, i)[0] == CG_ROLE_STRANGER && lstrlenA(cg.name[i]) == n
            && cg_same_ci(cg.name[i], name, n)) {
            return 1;
        }
    }
    return 0;
}

/* Stranger role `r`'s first name: random_below over the list of its sex's names nobody has (else the whole list). */
static void cg_stranger_name(const ce_adapter *a, int game, int r) {
    const char *list = cg_names_list(game, cg.female[r]);
    int pass, count, pick = -1;
    for (pass = 0; pass < 2 && pick < 0; ++pass) {
        const char *s;
        int k = 0;
        count = 0;
        for (s = list; *s != '\0';) {
            const char *e = s;
            while (*e != '\0' && *e != ',') {
                ++e;
            }
            if (e > s && (pass == 1 || !cg_name_taken(a, r, s, (int)(e - s)))) {
                ++count;
            }
            s = *e == ',' ? e + 1 : e;
        }
        if (count == 0) {
            continue;
        }
        pick = ce_random_below(a, count);
        for (s = list; *s != '\0';) {
            const char *e = s;
            while (*e != '\0' && *e != ',') {
                ++e;
            }
            if (e > s && (pass == 1 || !cg_name_taken(a, r, s, (int)(e - s)))) {
                if (k++ == pick) {
                    int n = (int)(e - s) < CG_NAME_BYTES - 1 ? (int)(e - s) : CG_NAME_BYTES - 1;
                    memcpy(cg.name[r], s, (size_t)n);
                    cg.name[r][n] = '\0';
                    return;
                }
            }
            s = *e == ',' ? e + 1 : e;
        }
    }
}

/* The longest name in the game's two lists: a named stranger's worst case. */
static int cg_stranger_room(int game) {
    int f, best = 0;
    for (f = 0; f < 2 && game >= 1 && game <= 5; ++f) {
        const char *s = CG_NAMES_TEXT[game][f];
        int n = 0;
        for (; *s != '\0'; ++s) {
            n = *s == ',' ? 0 : n + 1;
            if (n > best) {
                best = n;
            }
        }
    }
    return best;
}

/* ---- A new name (docs/event-collection/cie-v6-binary.md 28) ---------------------------------------------- */

#ifdef VVFP_TEST
static int test_graph_last_names = -1;  /* "VVFP Last Names.dll" as the test build sees it: -1 real, 0 none, 1 in */
#endif

/* The game's own 50 last names (the list "VVFP Last Names.dll" names from), read where the game keeps them, else
   the same list built in. */
static const char *cg_last_list(int game) {
    static char list[512];
    unsigned int n, i;
    int ok = 1;
    if (game < 1 || game > 5) {
        return "";
    }
    n = CG_LAST_BYTES[game];
    if (n == 0u || n >= sizeof list) {
        return CG_LAST_TEXT[game];
    }
    __try {
        memcpy(list, (const void *)(uintptr_t)CG_LAST_VA[game], n);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 0;
    }
    list[n] = '\0';
    for (i = 0; ok && i < n; ++i) {
        char c = list[i];
        ok = c == ',' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
    }
    ok = ok && list[0] != ',' && list[n - 1] == ',';
    return ok ? list : CG_LAST_TEXT[game];
}

/* The longest last name in the game's list (a new name's worst case adds a space and it). */
static int cg_last_room(int game) {
    const char *s = game >= 1 && game <= 5 ? CG_LAST_TEXT[game] : "";
    int n = 0, best = 0;
    for (; *s != '\0'; ++s) {
        n = *s == ',' ? 0 : n + 1;
        if (n > best) {
            best = n;
        }
    }
    return best;
}

/* Whether the game has last names: "VVFP Last Names.dll" is loaded (as the Custom Island Event's Joey asks). */
static int cg_last_names_on(void) {
#ifdef VVFP_TEST
    if (test_graph_last_names >= 0) {
        return test_graph_last_names;
    }
#endif
    return GetModuleHandleA("VVFP Last Names.dll") != NULL;
}

/* A word of only Roman numeral letters (a numbered name's numeral, "II"). */
static int cg_roman(const char *s, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        if (s[i] != 'I' && s[i] != 'V' && s[i] != 'X' && s[i] != 'L' && s[i] != 'C' && s[i] != 'D' && s[i] != 'M') {
            return 0;
        }
    }
    return n > 0;
}

/* A villager's last name as the Last Names companion reads it: the last word after the first, a trailing Roman
   numeral passed over; none (0) for a one-word name.  Its start in *at. */
static int cg_last_of(const char *name, const char **at) {
    const char *w[8];
    int len[8], words = 0;
    const char *s = name;
    while (*s != '\0' && words < 8) {
        while (*s == ' ') {
            ++s;
        }
        if (*s == '\0') {
            break;
        }
        w[words] = s;
        while (*s != '\0' && *s != ' ') {
            ++s;
        }
        len[words] = (int)(s - w[words]);
        ++words;
    }
    if (words >= 2 && cg_roman(w[words - 1], len[words - 1])) {
        --words;
    }
    if (words < 2) {
        return 0;
    }
    *at = w[words - 1];
    return len[words - 1];
}

/* Role `r`, a new name for the villager role in its mask: a first name of the sex its byte says (the villager's,
   the other, male, female or random) drawn as a named stranger's, and -- with Last Names in the game -- the
   villager's own last name, another one from the game's list, or any one.  Nobody is renamed: the name lives in
   the run (cg.name, kept in the run's file) and is the same on every page. */
static void cg_new_name(const ce_adapter *a, int game, int r) {
    const unsigned char *spec = cg_role_at(&cg_g, r);
    unsigned int mask = cg_u16(spec + 14);
    const char *own = NULL;
    int of, own_n = 0, female_of = 0, mode = spec[3];
    for (of = 0; of < cg_g.n_role && mask != (1u << of); ++of) {
    }
    if (of < cg_g.n_role && (cg.bound & (1u << of))) {
        female_of = cg.female[of];
        own_n = cg_last_of(cg.name[of], &own);
    }
    cg.female[r] = spec[2] == 2 ? 1 : spec[2] == 1 ? 0 : spec[2] == CG_NEW_SEX_SAME ? female_of
                 : spec[2] == CG_NEW_SEX_OTHER ? !female_of : ce_random_below(a, 2);
    cg.name[r][0] = '\0';
    cg_stranger_name(a, game, r);
    if (!cg_last_names_on()) {
        return;
    }
    if (mode != CG_LAST_SAME) {
        const char *list = cg_last_list(game), *s, *skip = own;
        int count = 0, k = 0, pick, skip_n = mode == CG_LAST_DIFFERENT ? own_n : 0;
        for (s = list; *s != '\0';) {
            const char *e = s;
            while (*e != '\0' && *e != ',') {
                ++e;
            }
            if (e > s && !(skip_n == (int)(e - s) && cg_same_ci(skip, s, skip_n))) {
                ++count;
            }
            s = *e == ',' ? e + 1 : e;
        }
        own = NULL;
        own_n = 0;
        pick = count > 0 ? ce_random_below(a, count) : -1;
        for (s = list; *s != '\0' && own == NULL;) {
            const char *e = s;
            while (*e != '\0' && *e != ',') {
                ++e;
            }
            if (e > s && !(skip_n == (int)(e - s) && cg_same_ci(skip, s, skip_n))) {
                if (k++ == pick) {
                    own = s;
                    own_n = (int)(e - s);
                }
            }
            s = *e == ',' ? e + 1 : e;
        }
    }
    if (own_n > 0) {
        int have = lstrlenA(cg.name[r]);
        if (have + 1 + own_n < CG_NAME_BYTES) {
            cg.name[r][have] = ' ';
            memcpy(cg.name[r] + have + 1, own, (size_t)own_n);
            cg.name[r][have + 1 + own_n] = '\0';
        }
    }
}

/* Bind every planned role (the game's random routine among those who keep the rest fillable), and each
   stranger's sex.  1 when bound. */
/* 28 / 29, CG_FX_PARTNER_MAY_CARRY (the owner, 2026-11-18): who carries is decided ONCE, when the run starts (the
   cast made and the aliases drawn -- an alias role is its member -- before any page is written), so every page (names, pronouns, carrier words) names the villager who actually
   carries, and the effect makes the same one carry.  For each such effect with a partner role, in effect order, each
   pair once: the carrier must pass the carrier's checks as the effect does (18 or more, not expecting, born female
   unless any_birth_sex), the partner 18 or more and not expecting; then, at the player's chance
   (cg_partner_carries: one roll, none at 0 or 100), the two roles' villagers change places for the rest of the run
   (record, identity, sex, name) and the carrier role is marked in cg.carry_swapped (the run's file keeps both, so a
   loaded run keeps the choice).  The effect then skips the born-female check for a swapped carrier: the partner may
   carry whatever their birth sex.  Nothing else is rolled at the effect. */
static unsigned char *cg_villager(const ce_adapter *a, int r);

static void cg_partner_carry_decide(const ce_adapter *a, int game) {
    unsigned int decided = 0u;
    int i;
    for (i = 0; i < cg_g.n_effect; ++i) {
        const unsigned char *e = cg_effect_at(&cg_g, i);
        int written = (int)e[1], c, p, t;
        unsigned char *cr, *pr;
        unsigned int id;
        char name[CG_NAME_BYTES];
        if ((e[0] != CGE_PREGNANT && e[0] != CGE_NURSING) || !(e[2] & CG_FX_PARTNER_MAY_CARRY)
            || written >= cg_g.n_role || cg_u32(e + 4) >= (unsigned int)cg_g.n_role) {
            continue;
        }
        /* an alias (or "other") role is its member drawn (Codex on #814: the aliases are drawn before this) */
        c = cg_resolve_role(written);
        p = cg_resolve_role((int)cg_u32(e + 4));
        if (c < 0 || p < 0 || c == p || (decided & ((1u << c) | (1u << p)))) {
            continue;
        }
        decided |= (1u << c) | (1u << p);
        cr = cg_villager(a, c);
        pr = cg_villager(a, p);
        if (cr == NULL || pr == NULL || !(a->caps & CAP_PREGNANT) || a->conceive == NULL
            || ce_age(a, cr) < 18 * 20 || *(const int *)(cr + a->off_pregnant) != 0
            || (!(e[2] & CG_FX_ANY_BIRTH_SEX) && !cg_born_female(game, cr, cg.record[c]))
            || ce_age(a, pr) < 18 * 20 || *(const int *)(pr + a->off_pregnant) != 0
            || !cg_partner_carries(a)) {
            continue;
        }
        t = cg.record[c]; cg.record[c] = cg.record[p]; cg.record[p] = t;
        id = cg.identity[c]; cg.identity[c] = cg.identity[p]; cg.identity[p] = id;
        t = cg.female[c]; cg.female[c] = cg.female[p]; cg.female[p] = t;
        memcpy(name, cg.name[c], sizeof name);
        memcpy(cg.name[c], cg.name[p], sizeof name);
        memcpy(cg.name[p], name, sizeof name);
        cg.carry_swapped |= 1u << c;   /* the role itself (an alias's member): effects resolve their role first */
    }
}

static int cg_bind(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char used[CE_MAX_RECORDS];
    int candidates[CE_MAX_RECORDS];
    unsigned int left = cg.planned;
    int r;
    if (a == NULL) {
        return 0;
    }
    if (cg.bound != 0u) {
        return 1;
    }
    memset(used, 0, sizeof used);
    cg_try_reset();
    cg_relax_mask = cg.relaxed;
    cg_cast_now = cg.cast_mode;
    cg_kin_fill(a, game);
    if (!cg_matchable(a, game, left, used)) {
        if (!cg_plan_cast(a, game, left, used)) {
            return 0;
        }
        cg.relaxed = cg_relax_mask;
    }
    cg_try_reset();
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        int n = 0, i, pick;
        cg.record[r] = -1;
        if (spec[0] == CG_ROLE_ALIAS) {
            continue;
        }
        if (spec[0] == 1 && (spec[1] & CG_STRANGER_NEW_NAME)) {
            continue;                          /* 28: drawn once every villager is bound (below) */
        }
        if (spec[0] == 1) {
            cg.female[r] = spec[2] == 2 ? 1 : spec[2] == 1 ? 0 : ce_random_below(a, 2);
            cg.name[r][0] = '\0';
            if (cg_g.version >= 6 && (spec[1] & CG_STRANGER_NAMED)) {
                cg_stranger_name(a, game, r);      /* cie-v6-binary.md 16 */
            }
            continue;
        }
        if (!(left & (1u << r))) {
            continue;
        }
        left &= ~(1u << r);
        for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
            if (used[i] || !cg_eligible(a, game, r, i) || !cg_gap_ok(a, r, i)) {
                continue;
            }
            used[i] = 1;
            cg_try[r] = i;
            if (cg_matchable(a, game, left, used)) {
                candidates[n++] = i;
            }
            cg_try[r] = -1;
            used[i] = 0;
        }
        if (n == 0) {
            return 0;
        }
        if (cg_g.version >= 6 && (spec[13] & ~(CG_ROLE_SPEAKS | CG_ROLE_HEATHEN)) == 1 && cg_u16(spec + 10) != CG_NONE && !(cg_relax_mask & (1u << r))) {
            /* "pick": "highest": only the villagers with the top value of the listed skills, then drawn. */
            const char *skills = cg_s(&cg_g, cg_u16(spec + 10));
            int best = -1, m = 0;
            for (i = 0; i < n; ++i) {
                int v = cg_skill_value(a, a->record(candidates[i]), skills);
                if (v > best) {
                    best = v;
                }
            }
            for (i = 0; i < n; ++i) {
                if (cg_skill_value(a, a->record(candidates[i]), skills) == best) {
                    candidates[m++] = candidates[i];
                }
            }
            n = m;
        }
        if (cg_g.version >= 6 && (spec[9] == CG_PREFER_GOLDEN || spec[9] == CG_PREFER_CHIEF)) {
            /* 35: the role prefers the Golden Child / the Tribal Chief: cast when they may take it (only one of
               them lives, so no roll), else any villager the role takes. */
            int m = 0;
            for (i = 0; i < n; ++i) {
                if (cg_special_kind(a, game, a->record(candidates[i]))
                    && (game == 1) == (spec[9] == CG_PREFER_GOLDEN)) {
                    candidates[m++] = candidates[i];
                }
            }
            if (m > 0) {
                n = m;
            }
        }
        pick = candidates[ce_random_below(a, n)];
        used[pick] = 1;
        cg_try[r] = pick;
        cg.record[r] = pick;
        cg.identity[r] = ce_identity(a, a->record(pick));
        cg.female[r] = cg_word_female(a, game, r, a->record(pick), pick);
        ce_copy_name(cg.name[r], CG_NAME_BYTES, a->record(pick) + a->off_name, a->name_bytes);
        cg.bound |= 1u << r;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        if (spec[0] == CG_ROLE_STRANGER && (spec[1] & CG_STRANGER_NEW_NAME)) {
            cg_new_name(a, game, r);           /* 28: in role order, after every villager */
        }
    }
    return 1;
}

/* The record of role `r` while it still holds the villager bound (alive, listed), else NULL. */
static unsigned char *cg_villager(const ce_adapter *a, int r) {
    if (r < 0 || r >= CG_MAX_ROLES || !(cg.bound & (1u << r)) || (cg.gone & (1u << r))) {
        return NULL;
    }
    return ce_same_villager(a, cg.record[r], cg.identity[r]);
}

/* ---- Conditions, the walk -------------------------------------------------------------------------------- */

static unsigned char cg_visited[(CG_MAX_NODES + 7) / 8];

/* Whether `game`'s puzzle `name` is solved: the adapter's puzzle_solved, the flag the game's own Puzzles and
   Statistics screens read (A New Home: the world's byte, The Cave at [world +0x9FA8], story_c1.inc C1_PUZZLES;
   the other games' tables in story_c2..c5.inc).  0 when the game has no puzzle of that name. */
static int cg_puzzle_solved(int game, const char *name) {
    const ce_adapter *a = ce_adapter_for(game);
    int i;
#ifdef VVFP_TEST
    if (test_graph_puzzles >= 0) {
        for (i = 0; a != NULL && i < a->puzzle_count; ++i) {
            if (lstrcmpA(a->puzzles[i].name, name) == 0) {
                return (test_graph_puzzles >> i) & 1;
            }
        }
        return 0;
    }
#endif
    if (a == NULL || a->puzzle_solved == NULL) {
        return 0;
    }
    for (i = 0; i < a->puzzle_count; ++i) {
        if (lstrcmpA(a->puzzles[i].name, name) == 0) {
            return a->puzzle_solved(i) != 0;
        }
    }
    return 0;
}

/* VERSION 6 RUNTIME FACTS. */

/* Living, listed villagers now (New Believers: believers), `children` 1: only those under 14. */
static int cg_population(int game, int children) {
    const ce_adapter *a = ce_adapter_for(game);
    int i, n = 0;
    if (a == NULL) {
        return 0;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        if (r != NULL && a->listed(r) && !cg_heathen(game, r) && (!children || ce_age(a, r) < 20 * 14)) {
            ++n;
        }
    }
    return n;
}

/* The Golden Child (1) or the Tribal Chief (2) is alive and listed. */
static int cg_special_present(int game, int kind) {
    const ce_adapter *a = ce_adapter_for(game);
    int i, want = kind == 1 ? STORY_KIND_GOLDEN_CHILD : STORY_KIND_TRIBAL_CHIEF;
    if (a == NULL) {
        return 0;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        if (r != NULL && a->listed(r) && ce_role(a, r, NULL) == want) {
            return 1;
        }
    }
    return 0;
}

static unsigned char *cg_villager(const ce_adapter *a, int r);

/* Role `r`'s villager (an alias: its member's) is bound, not gone, and not protected now: harm may reach them. */
static int cg_harmable(int r, int game) {
    const ce_adapter *a = ce_adapter_for(game);
    const unsigned char *record;
    r = cg_resolve_role(r);
    if (a == NULL || r < 0) {
        return 0;
    }
    record = cg_villager(a, r);
    return record != NULL && !cg_protected(a, game, record) && !cg_never_harmed(game, record);
}

static const cg_pick *cg_find_pick(int pool, int instance);

/* Cond `c` (age, skill_at_least, has_living_child: cie-v6-binary.md 8) on its role's villager (an alias's
   member), who must be bound and not gone. */
static int cg_role_fact(const unsigned char *c, int game) {
    const ce_adapter *a = ce_adapter_for(game);
    const unsigned char *r;
    int role = (int)cg_u16(c + 2);
    if (a == NULL || role >= cg_g.n_role || (r = cg_villager(a, cg_resolve_role(role))) == NULL) {
        return 0;
    }
    if (c[0] == CGC_AGE) {
        int years = ce_age(a, r) / 20;     /* whole years (20 age units a year, as the roles' ages) */
        return years >= (int)cg_u16(c + 4) && (cg_u16(c + 6) == 0u || years <= (int)cg_u16(c + 6));
    }
    if (c[0] == CGC_SKILL_AT_LEAST) {
        return cg_skill_value(a, r, cg_s(&cg_g, cg_u16(c + 6))) >= (int)cg_u16(c + 4);
    }
    if (c[0] == CGC_IS_SPECIAL) {
        /* 35: the Golden Child (A New Home) or The Secret City's Tribal Chief, by the game's own kind */
        return cg_special_kind(a, game, r);
    }
    if (c[0] == CGC_HAS_DEAD_RELATIVE) {
        cg_kin_read(a, game);
        return cg_dead_relative(game, cg.record[cg_resolve_role(role)]);
    }
    /* has_living_child: a living, listed villager whose recorded father OR mother is this one -- by the parent
       field, never by this one's sex now (a parent whose sex changed after the birth is still that child's parent,
       cie-v6-binary.md 29): the kinship table (cg_kin_read: the name, head and body on the child's record; A New
       Home's from its parentage sidecar). */
    {
        int me = cg.record[cg_resolve_role(role)], k;
        cg_kin_read(a, game);
        if (me < 0 || me >= CE_MAX_RECORDS) {
            return 0;
        }
        for (k = 0; k < a->record_count && k < CE_MAX_RECORDS; ++k) {
            if (k != me && cg_kin(game, CG_REL_CHILD, k, me)) {
                return 1;
            }
        }
        return 0;
    }
}

static int cg_holds_cond(int i, int game, int depth) {
    const unsigned char *c;
    unsigned int a;
    int k;
    if (i == (int)CG_NONE) {
        return 1;
    }
    if (i < 0 || i >= cg_g.n_cond || depth > 64) {
        return 0;
    }
    c = cg_cond_at(&cg_g, i);
    a = cg_u16(c + 2);
    switch (c[0]) {
    case CGC_VISITED: return (cg_visited[a >> 3] >> (a & 7u)) & 1;
    case CGC_ROLE:
        if (cg_role_at(&cg_g, (int)a)[0] >= CG_ROLE_ALIAS) {
            /* An alias (or other role) holds when it is bound: its member drawn (before the draw: an alias's member
               to be bound; an other role's alias's). */
            const unsigned char *spec = cg_role_at(&cg_g, (int)a);
            unsigned int mask = cg_u16(spec + 14);
            if (cg.aliases_drawn) {
                return cg.alias[a] >= 0;
            }
            if (spec[0] == CG_ROLE_OTHER) {
                int al;
                for (al = 0; al < cg_g.n_role && mask != (1u << al); ++al) {
                }
                mask = al < cg_g.n_role ? cg_u16(cg_role_at(&cg_g, al) + 14) : 0u;
                return (mask & cg.bound) == mask && mask != 0u;
            }
            return (mask & cg.bound) != 0u;
        }
        return (cg.bound >> a) & 1u;
    case CGC_HARMABLE: return cg_harmable((int)a, game);
    case CGC_SPECIAL_PRESENT: return cg_special_present(game, (int)a);
    case CGC_MIN_POPULATION: return cg_population(game, 0) >= (int)a;
    case CGC_MIN_CHILDREN: return cg_population(game, 1) >= (int)a;
    case CGC_AGE: case CGC_SKILL_AT_LEAST: case CGC_HAS_LIVING_CHILD: case CGC_HAS_DEAD_RELATIVE:
    case CGC_IS_SPECIAL:
        return cg_role_fact(c, game);
    case CGC_HAS_SUPPLY: return cg_has_good(game, cg_s(&cg_g, a), (int)cg_u16(c + 4));
    case CGC_DREW: {
        const cg_pick *pick = cg_find_pick((int)a, (int)cg_u16(c + 4));
        return pick != NULL && pick->item == cg_u16(c + 6);
    }
    case CGC_GAME: return (a >> (game - 1)) & 1u;
    case CGC_PATCH: return (cg.patches >> a) & 1u;
    case CGC_PUZZLE: return (int)cg_u16(c + 4) != game || cg_puzzle_solved(game, cg_s(&cg_g, a));
    case CGC_NOT: return !cg_holds_cond((int)a, game, depth + 1);
    case CGC_ALL:
        for (k = 0; k < c[1]; ++k) {
            if (!cg_holds_cond((int)a + k, game, depth + 1)) {
                return 0;
            }
        }
        return 1;
    default:
        for (k = 0; k < c[1]; ++k) {
            if (cg_holds_cond((int)a + k, game, depth + 1)) {
                return 1;
            }
        }
        return 0;
    }
}

static void cg_visit(int node) {
    cg_visited[node >> 3] |= (unsigned char)(1u << (node & 7));
}

/* The node's text: its first variant whose condition holds, else its own. */
static const char *cg_node_text(int node, int game) {
    const unsigned char *n = cg_node_at(&cg_g, node);
    int k;
    for (k = 0; k < (int)cg_u16(n + 10); ++k) {
        const unsigned char *v = cg_variant_at(&cg_g, (int)cg_u16(n + 8) + k);
        if (cg_holds_cond((int)cg_u16(v), game, 0)) {
            return cg_s(&cg_g, cg_u16(v + 2));
        }
    }
    return cg_s(&cg_g, cg_u16(n + 6));
}

/* The child drawn at `node` (src/vv_cie_graph.py _resolved_children), -1 at an end. */
static int cg_draw(const ce_adapter *a, int node, int game) {
    const unsigned char *n = cg_node_at(&cg_g, node);
    int targets[256];
    int weights[256];
    int count = 0, total = 0, k, roll;
    for (k = 0; k < (int)cg_u16(n + 14) && count < 256; ++k) {
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(n + 12) + k);
        /* Version 6: the hard harm guard, as one more condition (a protected villager is never harmed: the
           branch is replaced by its else, or left out). */
        if (cg_holds_cond((int)cg_u16(c + 4), game, 0)
            && (cg_g.version < 6 || cg_holds_cond((int)cg_u16(c + 10), game, 0))) {
            targets[count] = (int)cg_u16(c);
        } else if (cg_u16(c + 6) != CG_NONE) {
            targets[count] = (int)cg_u16(c + 6);
        } else {
            continue;
        }
        weights[count] = (int)cg_u16(c + 2);
        total += weights[count++];
    }
    if (count == 0) {
        return cg_u16(n + 16) != CG_NONE ? (int)cg_u16(n + 16) : -1;
    }
#ifdef VVFP_TEST
    for (k = 0; k < count; ++k) {
        int f;
        for (f = 0; f < test_graph_forced; ++f) {
            if (test_graph_force[f] == targets[k]) {
                return targets[k];
            }
        }
    }
#endif
    roll = ce_random_below(a, total);
    return targets[ce_roll_index(weights, count, roll)];
}

/* What "Island Events Scale With Population" (1) or "... With Stored Food and Tech Points" (2) does to an
   amount, as its companion scales the game's own events; 0 = not ticked. */
static int cg_scale_mode(void) {
    typedef int (__stdcall *mode_fn)(void);
    HMODULE module;
    mode_fn mode;
#ifdef VVFP_TEST
    if (test_graph_scale >= 0) {
        return test_graph_scale;
    }
#endif
    module = GetModuleHandleA("VVFP Island Events Scale.dll");
    mode = module != NULL ? (mode_fn)(void *)GetProcAddress(module, "VvfpIslandEventsScaleMode") : NULL;
    return mode != NULL ? mode() : 0;
}

static int cg_scaled(const ce_adapter *a, int game, int food, int amount) {
    long long value = amount < 0 ? -(long long)amount : amount;
    int mode = cg_scale_mode();
    if (mode == 2) {
        int stored = food ? ((a->caps & CAP_FOOD) ? a->food() : 0) : ((a->caps & CAP_TECH) ? a->tech() : 0);
        value += stored > 0 ? stored / 10 : 0;
    } else if (mode == 1) {
        int i, n = 0;
        for (i = 0; i < a->record_count; ++i) {
            const unsigned char *r = a->record(i);
            if (r != NULL && a->listed(r) && !cg_heathen(game, r)) {
                ++n;
            }
        }
        value *= n > 50 ? 3 : (n > 25 ? 2 : 1);
    }
    if (value > CE_MAX_AMOUNT) {
        value = CE_MAX_AMOUNT;
    }
    return amount < 0 ? -(int)value : (int)value;
}

/* The skill names of skill effect `e` this game has: their count; with `pick` >= 0 the adapter's index of the
   pick-th one. */
static int cg_skills(const ce_adapter *a, const unsigned char *e, int pick) {
    const char *list = cg_s(&cg_g, cg_u16(e + 12));
    char word[32];
    int n = 0, k, entry;
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            if (lstrcmpiA(a->skill_names[k], word) == 0) {
                if (n == pick) {
                    return k;
                }
                ++n;
                break;
            }
        }
    }
    return pick >= 0 ? -1 : n;
}

/* An effect's own roll as its node is reached, into the history (cg_per_game: above the loader). */
/* cie-v6-binary.md 24: a random like or dislike -- the walk's roll `k` over the game's list, then candidate k % count
   of the game's preferences (in list order) in NEITHER of the villager's lists now; -1 when there is none (or nobody
   bound to read). */
/* One of the likes (or `dislike`: the dislikes) the villager in `role` holds, drawn with the game's own random
   routine; -1 when the list is empty. */
static int cg_held_preference_of(const ce_adapter *a, const unsigned char *r, int dislike);

static int cg_held_preference(const ce_adapter *a, int role, int dislike) {
    return cg_held_preference_of(a, role >= 0 ? cg_villager(a, role) : NULL, dislike);
}

/* A random like (or dislike) this villager holds, to take away; -1 when the list is empty (no roll then). */
static int cg_held_preference_of(const ce_adapter *a, const unsigned char *r, int dislike) {
    const int *list;
    int held[64], n = 0, slot;
    if (r == NULL) {
        return -1;
    }
    list = (const int *)(r + (dislike ? a->off_dislikes : a->off_likes));
    for (slot = 0; slot < a->pref_slots && n < 64; ++slot) {
        if (list[slot] >= 0 && list[slot] < a->pref_count) {
            held[n++] = list[slot];
        }
    }
    return n > 0 ? held[ce_random_below(a, n)] : -1;
}

static int cg_random_preference_of(const ce_adapter *a, const unsigned char *r, int k);

static int cg_random_preference(const ce_adapter *a, int role, int k) {
    return cg_random_preference_of(a, role >= 0 ? cg_villager(a, role) : NULL, k);
}

/* ...the same for villager record `r` (a group's member). */
static int cg_random_preference_of(const ce_adapter *a, const unsigned char *r, int k) {
    const int *likes, *dislikes;
    int i, s, count = 0;
    if (r == NULL || a->pref_count <= 0 || k < 0) {
        return -1;
    }
    likes = (const int *)(r + a->off_likes);
    dislikes = (const int *)(r + a->off_dislikes);
    for (s = 0; s < 2; ++s) {
        for (i = 0; i < a->pref_count; ++i) {
            int slot, held = 0;
            for (slot = 0; slot < a->pref_slots; ++slot) {
                held |= likes[slot] == i || dislikes[slot] == i;
            }
            if (held) {
                continue;
            }
            if (s == 0) {
                ++count;
            } else if (k-- == 0) {
                return i;
            }
        }
        if (count == 0) {
            return -1;
        }
        k %= count;
    }
    return -1;
}

static int sc_population(int game);   /* story_collection.inc: the population the gate counts */

/* Each game's normal food and tech-point range of its own island events (src/vv_cie_graph.py SIZE_TABLE): a size
   word's range is it halved (small), as it is (normal), doubled (large) or tripled (huge). */
static const int CG_SIZE_NORMAL[2][6][2] = {
    { { 0, 0 }, { 200, 1500 }, { 100, 1500 }, { 200, 600 }, { 300, 300 }, { 50, 300 } },      /* food */
    { { 0, 0 }, { 500, 4999 }, { 500, 3000 }, { 1000, 2000 }, { 500, 5000 }, { 500, 3000 } },  /* tech */
};
static const int CG_SIZE_MUL[4][2] = { { 1, 2 }, { 1, 1 }, { 2, 1 }, { 3, 1 } };

/* Whether the loaded event is one of the new events (the collection's: its header names its "collection" block,
   cie-v6-binary.md; the Living Event Engine's variants too). */
static int cg_is_collection_event(void) {
    return cg_g.version >= 6 && cg_g.header_bytes >= CG_HEADER_V6 && cg_u16(cg_g.d + 90) != CG_NONE;
}

static void cg_roll_effect(const ce_adapter *a, int game, const unsigned char *e, cg_history *h) {
    int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
    int va = 0, vb = 0;
    switch (e[0]) {
    case CGE_FOOD: case CGE_TECH:
        if (cg_is_collection_event() && game >= 1 && game <= 5 && sc_population(game) >= 61) {
            /* The owner (2026-11-15): from 61 villagers a new event's food or tech points come in a random size --
               small, normal, large or huge, equally likely -- in the game's own ranges; a gain stays a gain and a
               loss a loss.  Below 61 the size the event names. */
            const int *n = CG_SIZE_NORMAL[e[0] == CGE_TECH][game];
            int size = ce_random_below(a, 4);
            int slo = n[0] * CG_SIZE_MUL[size][0] / CG_SIZE_MUL[size][1];
            int shi = n[1] * CG_SIZE_MUL[size][0] / CG_SIZE_MUL[size][1];
            lo = slo + ce_random_below(a, shi - slo + 1);
            if ((int)cg_u32(e + 4) < 0) {
                lo = -lo;
            }
            va = (e[2] & 1u) ? cg_scaled(a, game, e[0] == CGE_FOOD, lo) : lo;
            break;
        }
        /* Version 5: this game's own amount or range, when the effect lists one. */
        if (cg_u16(e + 12) != CG_NONE && cg_per_game(cg_s(&cg_g, cg_u16(e + 12)), game, &lo, &hi) == 1) {
            if (hi == lo) {
                hi = 0;
            }
        }
        if (hi != 0) {
            /* Version 3: a range, each amount equally likely (the game's random routine), then scaled as a fixed
               amount is. */
            lo += ce_random_below(a, hi - lo + 1);
        }
        va = (e[2] & 1u) ? cg_scaled(a, game, e[0] == CGE_FOOD, lo) : lo;
        break;
    case CGE_HEALTH:
        va = lo + ce_random_below(a, hi - lo + 1);
        break;
    case CGE_SKILL: {
        int n = (e[2] & CG_SKILL_BEST) ? 0 : cg_skills(a, e, -1);
        /* the villager's own highest skill: chosen when the effect is made (-2), no roll here */
        va = (e[2] & CG_SKILL_BEST) ? -2 : n > 0 ? cg_skills(a, e, ce_random_below(a, n)) : -1;
        vb = lo + ce_random_below(a, hi - lo + 1);   /* version 6: a loss too (lo..hi below 0) */
        break;
    }
    case CGE_HEALTH_CHANGE: case CGE_DAMAGE: case CGE_SUPPLY: case CGE_VILLAGE:
        va = lo + ce_random_below(a, hi - lo + 1);   /* 35: a fixed step or weather (lo == hi) takes no roll */
        break;
    case CGE_DELIVER_EARLY:
        /* 30: the newborn's extra loss, rolled only when the effect has one */
        if (lo != 0 || hi != 0) {
            va = lo + ce_random_below(a, hi - lo + 1);
        }
        break;
    case CGE_SKILL_SET: {
        int n = (e[2] & CG_SKILL_BEST) ? 0 : cg_skills(a, e, -1);
        va = (e[2] & CG_SKILL_BEST) ? -2 : n > 0 ? cg_skills(a, e, ce_random_below(a, n)) : -1;
        vb = lo;                       /* the value set: no roll */
        break;
    }
    case CGE_APPEARANCE:
        /* 22: a fixed row is itself, kept -1 (no roll); random the roll k in 0..rows-2, the head's first (k + 1 from
           the current row up when the effect is made). */
        va = lo == CG_LOOK_RANDOM ? ce_random_below(a, a->head_count - 1) : lo == CG_LOOK_KEEP ? -1 : lo;
        vb = hi == CG_LOOK_RANDOM ? ce_random_below(a, a->body_count - 1) : hi == CG_LOOK_KEEP ? -1 : hi;
        break;
    case CGE_PREF:
        if ((e[2] & CG_PREF_RANDOM) && (e[2] & CG_PREF_REMOVE)) {
            /* A random like (or dislike) the villager holds, to take away; -1 when the list is empty. */
            va = cg_held_preference(a, cg_resolve_role(e[1]), (e[2] & 4u) != 0);
        } else if (e[2] & CG_PREF_RANDOM) {
            /* 24: the roll, then the word chosen from the villager as the walk finds them (a fixed word: no roll) */
            int k = ce_random_below(a, a->pref_count);
            va = cg_random_preference(a, cg_resolve_role(e[1]), k);
        }
        break;
    default:
        break;                         /* celebrate, action, mood, die_unrecovered, baby_lost, birth_then_die: no
                                          roll */
    }
    if (h->fx < CG_MAX_FX) {
        h->fx_a[h->fx] = va;
        h->fx_b[h->fx] = vb;
    }
    ++h->fx;
}

/* A node's effects the run makes: none for a question (version 2 refuses them; version 1 never made them). */
static int cg_fx_count(const unsigned char *n) {
    return n[0] == CG_QUESTION ? 0 : (int)cg_u16(n + 20);
}

/* The visited set: the path's first `upto` nodes. */
static void cg_visit_path(int upto) {
    int i;
    memset(cg_visited, 0, sizeof cg_visited);
    for (i = 0; i < upto && i < cg.path.nodes; ++i) {
        cg_visit(cg.path.node[i]);
    }
}

/* ---- Version 6 pools: each instance drawn once a run, in the walk -------------------------------------------- */

/* The picks of the segment being walked (an answer's: kept apart until it is answered), NULL while the path's own
   are drawn. */
static cg_pick *cg_seg_pk;
static unsigned char *cg_seg_pk_count;

/* Instance `instance` of pool `pool` as drawn on the run so far (the path's, then the segment's), or NULL. */
static const cg_pick *cg_find_pick(int pool, int instance) {
    int i;
    for (i = 0; i < cg.pick_count && i < CG_MAX_PICKS; ++i) {
        if (cg.picks[i].pool == (unsigned short)pool && cg.picks[i].instance == (unsigned short)instance) {
            return &cg.picks[i];
        }
    }
    for (i = 0; cg_seg_pk != NULL && i < *cg_seg_pk_count; ++i) {
        if (cg_seg_pk[i].pool == (unsigned short)pool && cg_seg_pk[i].instance == (unsigned short)instance) {
            return &cg_seg_pk[i];
        }
    }
    return NULL;
}

/* Item `item` of `pool` is drawn by another instance already. */
static int cg_item_taken(int pool, int item) {
    int i;
    for (i = 0; i < cg.pick_count && i < CG_MAX_PICKS; ++i) {
        if (cg.picks[i].pool == (unsigned short)pool && cg.picks[i].item == (unsigned short)item) {
            return 1;
        }
    }
    for (i = 0; cg_seg_pk != NULL && i < *cg_seg_pk_count; ++i) {
        if (cg_seg_pk[i].pool == (unsigned short)pool && cg_seg_pk[i].item == (unsigned short)item) {
            return 1;
        }
    }
    return 0;
}

static void cg_scan_pools(const ce_adapter *a, int game, const char *text, int depth);

/* 35: the item number the first linked pool drawn so far (the path's picks, then the segment's) drew, or -1. */
static int cg_linked_item(void) {
    int i;
    for (i = 0; i < cg.pick_count && i < CG_MAX_PICKS; ++i) {
        if ((cg_pool_at(&cg_g, cg.picks[i].pool)[6] & CG_POOL_LINKED) && cg.picks[i].item != CG_NONE) {
            return (int)cg.picks[i].item;
        }
    }
    for (i = 0; cg_seg_pk != NULL && i < *cg_seg_pk_count; ++i) {
        if ((cg_pool_at(&cg_g, cg_seg_pk[i].pool)[6] & CG_POOL_LINKED) && cg_seg_pk[i].item != CG_NONE) {
            return (int)cg_seg_pk[i].item;
        }
    }
    return -1;
}

/* G3: whether `text` is the text of an item drawn so far (the path and the segment) by an instance of a pool that
   `list` names (comma separated). */
static int cg_pick_text_is(const cg_pick *k, const char *list, const char *text) {
    char word[40];
    int entry;
    const char *name;
    const unsigned char *p;
    if (k->item == CG_NONE) {
        return 0;
    }
    p = cg_pool_at(&cg_g, k->pool);
    name = cg_s(&cg_g, cg_u16(p));
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        if (lstrcmpA(word, name) == 0) {
            return lstrcmpA(cg_s(&cg_g, cg_u16(cg_item_at(&cg_g, (int)cg_u16(p + 2) + k->item))), text) == 0;
        }
    }
    return 0;
}

static int cg_text_taken_by(const char *list, const char *text) {
    int i;
    for (i = 0; i < cg.pick_count && i < CG_MAX_PICKS; ++i) {
        if (cg_pick_text_is(&cg.picks[i], list, text)) {
            return 1;
        }
    }
    for (i = 0; cg_seg_pk != NULL && i < *cg_seg_pk_count; ++i) {
        if (cg_pick_text_is(&cg_seg_pk[i], list, text)) {
            return 1;
        }
    }
    return 0;
}

/* Instance `instance` of `pool` drawn, unless the run has it: its eligible items (their conditions hold now; a
   distinct pool's not drawn by its other instances, unless that leaves none), weighted; none: the empty text, no
   roll.  Then the item's own tokens, depth first. */
static void cg_draw_instance(const ce_adapter *a, int game, int pool, int instance, int depth) {
    static int weights[CG_POOL_DEPTH + 1][1024];
    static int items[CG_POOL_DEPTH + 1][1024];
    const unsigned char *p = cg_pool_at(&cg_g, pool);
    int first = (int)cg_u16(p + 2), count = (int)cg_u16(p + 4);
    int n = 0, total = 0, k, pass, item = (int)CG_NONE;
    cg_pick pick;
    if (depth > CG_POOL_DEPTH || cg_find_pick(pool, instance) != NULL) {
        return;
    }
    if (p[6] & CG_POOL_LINKED) {
        /* 35: the item number the first linked pool drawn on the run drew (the chief's one title on every page and
           after a resume), with no roll and no condition asked again */
        int linked = cg_linked_item();
        if (linked >= 0 && linked < count) {
            item = linked;
        }
    }
    for (pass = item != (int)CG_NONE ? 2 : 0; pass < 2 && n == 0; ++pass) {
        total = 0;
        for (k = 0; k < count && n < 1024; ++k) {
            const unsigned char *it = cg_item_at(&cg_g, first + k);
            if (!cg_holds_cond((int)cg_u16(it + 4), game, 0)) {
                continue;
            }
            if (pass == 0 && (p[6] & 1u) && cg_item_taken(pool, k)) {
                continue;
            }
            if (pass == 0 && cg_u16(p + 8) != CG_NONE
                && cg_text_taken_by(cg_s(&cg_g, cg_u16(p + 8)), cg_s(&cg_g, cg_u16(it)))) {
                continue;              /* G3: the text an instance of a listed pool has drawn */
            }
            items[depth][n] = k;
            weights[depth][n] = (int)cg_u16(it + 2);
            total += weights[depth][n++];
        }
        if (!(p[6] & 1u) && cg_u16(p + 8) == CG_NONE) {
            break;                     /* nothing taken out: one pass */
        }
    }
    if (n > 0) {
        item = items[depth][ce_roll_index(weights[depth], n, ce_random_below(a, total))];
    }
    pick.pool = (unsigned short)pool;
    pick.instance = (unsigned short)instance;
    pick.item = (unsigned short)item;
    if (cg_seg_pk != NULL) {
        if (*cg_seg_pk_count < CG_SEG_PICKS) {
            cg_seg_pk[(*cg_seg_pk_count)++] = pick;
        }
    } else if (cg.pick_count < CG_MAX_PICKS) {
        cg.picks[cg.pick_count++] = pick;
    }
    if (item != (int)CG_NONE) {
        cg_scan_pools(a, game, cg_s(&cg_g, cg_u16(cg_item_at(&cg_g, first + item))), depth + 1);
    }
}

/* Every pool token of `text`, left to right, drawn when the run has not drawn it yet. */
static void cg_scan_pools(const ce_adapter *a, int game, const char *text, int depth) {
    const char *s;
    for (s = text; *s != '\0'; ++s) {
        int pool, instance, n;
        if (*s == '\\' && s[1] != '\0') {
            ++s;
            continue;
        }
        if (*s != '{') {
            continue;
        }
        n = cg_parse_brace(&cg_g, s, &pool, &instance);
        if (n == 0) {
            continue;
        }
        if (pool >= 0) {
            cg_draw_instance(a, game, pool, instance, depth);
        }
        s += n - 1;
    }
}

/* A node's pools (version 6): its text's (the variant this run shows), then a question's labels, left to right. */
static const char *cg_node_text(int node, int game);

static void cg_node_pools(const ce_adapter *a, int game, int node) {
    const unsigned char *n = cg_node_at(&cg_g, node);
    int k;
    if (cg_g.version < 6) {
        return;
    }
    cg_scan_pools(a, game, cg_node_text(node, game), 1);
    if (n[0] == CG_QUESTION) {
        for (k = 0; k < (int)cg_u16(n + 14); ++k) {
            cg_scan_pools(a, game, cg_s(&cg_g, cg_u16(cg_child_at(&cg_g, (int)cg_u16(n + 12) + k) + 8)), 1);
        }
    }
}

/* One segment from `from`: the nodes and every effect's roll, up to the next question (included) or the end.
   `game` and the bound roles and patches decide the conditions; the path so far counts as visited.  Per node: its
   effects' rolls, its pools (version 6; into `picks` -- NULL: the path's own), then the child drawn. */
#ifdef VVFP_TEST
static int test_graph_nurse = -1;      /* a record that starts nursing as the next walk begins (the harm guard) */
#endif

static void cg_walk(const ce_adapter *a, int game, int from, cg_history *h, cg_pick *picks, unsigned char *picked) {
    int node = from;
#ifdef VVFP_TEST
    if (test_graph_nurse >= 0 && a->record(test_graph_nurse) != NULL) {
        *(int *)(a->record(test_graph_nurse) + a->off_pregnant) = 1;
        test_graph_nurse = -1;
    }
#endif
    memset(h, 0, sizeof *h);
    cg_seg_pk = picks;
    cg_seg_pk_count = picked;
    if (picked != NULL) {
        *picked = 0;
    }
    cg_visit_path(cg.path.nodes);
    while (node >= 0 && h->nodes < CG_MAX_PATH) {
        const unsigned char *n = cg_node_at(&cg_g, node);
        int k;
        h->node[h->nodes++] = (short)node;
        cg_visit(node);
        for (k = 0; k < cg_fx_count(n); ++k) {
            cg_roll_effect(a, game, cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k), h);
        }
        cg_node_pools(a, game, node);
        if (n[0] == CG_QUESTION) {
            break;
        }
        node = cg_draw(a, node, game);
    }
    cg_seg_pk = NULL;
    cg_seg_pk_count = NULL;
}

/* Segment `s` added to the path, with its picks (`count` of them). */
static void cg_path_add(const cg_history *s, const cg_pick *picks, int count) {
    int i;
    for (i = 0; i < s->nodes && cg.path.nodes < CG_MAX_PATH; ++i) {
        cg.path.node[cg.path.nodes++] = s->node[i];
    }
    for (i = 0; i < s->fx; ++i, ++cg.path.fx) {
        if (cg.path.fx < CG_MAX_FX) {
            cg.path.fx_a[cg.path.fx] = i < CG_MAX_FX ? s->fx_a[i] : 0;
            cg.path.fx_b[cg.path.fx] = i < CG_MAX_FX ? s->fx_b[i] : 0;
        }
    }
    for (i = 0; picks != NULL && i < count && cg.pick_count < CG_MAX_PICKS; ++i) {
        cg.picks[cg.pick_count++] = picks[i];
    }
}

/* ---- Placeholders, pages, popups ------------------------------------------------------------------------- */

/* The pronouns, (male, female): he/she .. man/woman, then version 6's himself/herself, woman/man, boy/girl,
   son/daughter. */
static const char *const CG_PRONOUNS[17][2] = {
    { "he", "she" }, { "his", "her" }, { "him", "her" }, { "man", "woman" },
    { "himself", "herself" }, { "man", "woman" }, { "boy", "girl" }, { "son", "daughter" },
    { "father", "mother" }, { "father", "mother" }, { "dad", "mom" }, { "brother", "sister" }, { "uncle", "aunt" },
    { "boy", "girl" }, { "gentleman", "lady" }, { "his", "hers" }, { "headman", "headwoman" } };

static const char *const *cg_pronoun(int what) {
    return CG_PRONOUNS[what <= CG_PH_MAN ? what - CG_PH_HE : what - CG_PH_HIMSELF + 4];
}

#ifdef VVFP_TEST
static int test_graph_unicode = -1;    /* the Unicode Text companion loaded (1) or not (0), -1 = as it is */
#endif

/* A New Home and The Lost Children draw ; ( ) & % only through the Unicode Text companion (src/vv_font_glyphs.py):
   without it they are written , - - and " percent" (docs/event-collection/cie-v6-binary.md 9). */
static int cg_fallback_on(void) {
    if (cg.game != 1 && cg.game != 2) {
        return 0;
    }
#ifdef VVFP_TEST
    if (test_graph_unicode >= 0) {
        return !test_graph_unicode;
    }
#endif
    return GetModuleHandleW(L"VVFP Unicode Text.dll") == NULL && GetModuleHandleW(L"VVFP Unicode Font.dll") == NULL;
}

/* `out` (its `n` bytes, `cap` the buffer) with the glyph fallback over it; the new length. */
static int cg_glyph_fallback(char *out, int n, int cap) {
    static char copy[CG_DISPLAY_BYTES / 4];
    int i, o = 0;
    if (n <= 0 || n >= (int)sizeof copy) {
        return n;
    }
    memcpy(copy, out, (size_t)n + 1);
    for (i = 0; i < n && o < cap - 1; ++i) {
        const char *put = NULL;
        char c = copy[i];
        if (c == '(' && cg_made_ph(copy + i)) {
            int c2, len = cg_made_len(cg_made_ph(copy + i));
            for (c2 = 0; c2 < len && o < cap - 1; ++c2) {
                out[o++] = copy[i + c2];
            }
            i += len - 1;
            continue;
        }
        if (c == '{' && copy[i + 1] == '#') {
            /* 33: a count token is filled (and falls back) after the page's effects: kept as it is */
            for (; i < n && copy[i] != '}' && o < cap - 1; ++i) {
                out[o++] = copy[i];
            }
            if (i < n && o < cap - 1) {
                out[o++] = copy[i];
            }
            continue;
        }
        switch (c) {
        case ';': c = ','; break;
        case '(': case ')': c = '-'; break;
        case '&': put = "and"; break;
        case '%': put = " percent"; break;
        default: break;
        }
        if (put == NULL) {
            out[o++] = c;
            continue;
        }
        for (; *put != '\0' && o < cap - 1; ++put) {
            out[o++] = *put;
        }
    }
    out[o] = '\0';
    return o;
}

/* G5: THE TRIBE'S NAME ({@tribe} / {@Tribe}), read at run time where every game keeps it: in its save manager (the
   singleton native/shared/game_save_slot.h names), in the block the game hands its own save writer, at that block's
   name offset (native/shared/village_identity.c, measured on 348 saves) -- manager + 8 + offset, the read More Island
   Events' The Troubling Signs makes in The Secret City (troubling_vv3.inc vv3_tribe: +0x12ED4) -- bounded by the
   field after it (the save slot); only bytes a player could type.  No name: "the village" / "The village". */
static const unsigned int CG_TRIBE_MANAGER[6] = { 0, 0x48AEDCu, 0x4997BCu, 0x4B309Cu, 0x4CB51Cu, 0x4DACE0u };
static const unsigned int CG_TRIBE_AT[6] = { 0, 0x10u, 0x10u, 0x12ED4u, 0x170C0u, 0x17D1Cu };
static const int CG_TRIBE_BYTES[6] = { 0, 33, 33, 21, 21, 21 };   /* the name field (src/vv_tribe_rename.py save_field) */
#define CG_TRIBE_MAX 64

/* The tribe's name in `game` into `out` (`cap` bytes): 1 when the game holds one. */
static int cg_tribe_name(int game, char *out, int cap) {
    int ok = 0;
    out[0] = '\0';
    if (game < 1 || game > 5 || cap < 2) {
        return 0;
    }
    __try {
        const unsigned char *manager = *(const unsigned char *const *)(uintptr_t)CG_TRIBE_MANAGER[game];
        int i;
        if (manager != NULL) {
            const unsigned char *name = manager + CG_TRIBE_AT[game];
            for (i = 0; i < CG_TRIBE_BYTES[game] && i < cap - 1 && name[i] != 0; ++i) {
                unsigned char c = name[i];
                if (c < 0x20 || c == 0x7F) {
                    break;
                }
                out[i] = (char)c;
            }
            ok = i > 0 && (i == CG_TRIBE_BYTES[game] || i == cap - 1 || name[i] == 0);
            out[ok ? i : 0] = '\0';
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 0;
        out[0] = '\0';
    }
    return ok;
}

/* The words {@tribe} (`capital` 0) or {@Tribe} stand for now. */
static const char *cg_tribe_words(int capital) {
    static char name[CG_TRIBE_MAX + 1];
    if (cg_tribe_name(cg.game, name, sizeof name)) {
        return name;
    }
    return capital ? "The village" : "the village";
}

/* The text pool token `pool`.`instance` stands for: the item drawn; with none drawn (never on a walked path) the
   longest eligible item for CG_EXPAND_WORST, else the first eligible one. */
static const char *cg_pool_text(int pool, int instance, int mode) {
    const cg_pick *pick = cg_find_pick(pool, instance);
    const unsigned char *p = cg_pool_at(&cg_g, pool);
    const char *best = NULL;
    int k;
    if (pick != NULL) {
        return pick->item == CG_NONE ? "" : cg_s(&cg_g, cg_u16(cg_item_at(&cg_g, (int)cg_u16(p + 2) + pick->item)));
    }
    for (k = 0; k < (int)cg_u16(p + 4); ++k) {
        const unsigned char *it = cg_item_at(&cg_g, (int)cg_u16(p + 2) + k);
        const char *s = cg_s(&cg_g, cg_u16(it));
        if (!cg_holds_cond((int)cg_u16(it + 4), cg.game, 0)) {
            continue;
        }
        if (best == NULL || (mode == CG_EXPAND_WORST && lstrlenA(s) > lstrlenA(best))) {
            best = s;
        }
        if (mode != CG_EXPAND_WORST) {
            break;
        }
    }
    return best != NULL ? best : "";
}

static int cg_pronoun_names;          /* cg_label_text's second pass: names as pronouns (cie-v6-binary.md 15) */

/* cg_expand's work at pool depth `depth`. */
/* ---- Sentence case (cie-v6-binary.md 20; src/vv_cie_graph.py sentence_case / title_case: the same rule) ------

   The owner, 2026-11-14: the entire event text is shown in sentence case; capitals that mean something stay.  Shown
   in sentence case: a label with no lower-case letter, and a story sentence with no lower-case letter and no "!" --
   outside quotations.  Kept: emphasis inside ordinary text ("it was
   HUGE"), speech in quotation marks, shouting ("CLOSE IT!").  In sentence case the letters and the placeholders'
   letters are made lower case, then a capital where a sentence starts, for "I" and for the island's name -- before
   anything is filled in, so names keep their own capitals.  A title in capitals is shown in title case.  The
   graph's text is never changed: each expansion cases its own copy. */

static int cg_up(unsigned char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 0xC0 && c <= 0xDE && c != 0xD7);
}

static int cg_lo(unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 0xDF && c != 0xF7);
}

static int cg_letter(unsigned char c) {
    return cg_up(c) || cg_lo(c);
}

static unsigned char cg_to_lo(unsigned char c) {
    return cg_up(c) ? (unsigned char)(c + 0x20) : c;
}

static unsigned char cg_to_up(unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 0xE0 && c <= 0xFE && c != 0xF7) ? (unsigned char)(c - 0x20) : c;
}

static int cg_id_char(unsigned char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_';
}

/* The token at `t` (src/vv_cie_graph.py _TOKEN_V6: an escape, a placeholder, a pick): its length (*kind 3, 1, 2),
   0 for a plain character. */
static int cg_case_token(const unsigned char *t, unsigned char *kind) {
    const unsigned char *e;
    if (t[0] == '\\' && t[1] != 0 && t[1] != '\n') {
        *kind = 3;
        return 2;
    }
    if (t[0] == '(') {
        for (e = t + 1; *e != 0 && *e != '(' && *e != ')' && *e != '\n'; ++e) {
        }
        if (*e != ')') {
            return 0;
        }
        *kind = 1;
        return (int)(e - t) + 1;
    }
    if (t[0] == '{') {
        for (e = t + 1;;) {
            if (*e == 0 || *e == '\n') {
                return 0;
            }
            if (*e == '}') {
                *kind = 2;
                return (int)(e - t) + 1;
            }
            if (*e == '{') {
                const unsigned char *f = e + 1;
                if (*f++ != '@' || !cg_id_char(*f)) {
                    return 0;
                }
                while (cg_id_char(*f)) {
                    ++f;
                }
                if (*f != '}') {
                    return 0;
                }
                e = f + 1;
                continue;
            }
            ++e;
        }
    }
    return 0;
}

#define CG_CASE_UNITS (CG_RAW_BYTES + 8)
static int cg_cu_at[CG_CASE_UNITS];             /* each unit's first byte */
static int cg_cu_len[CG_CASE_UNITS];
static unsigned char cg_cu_kind[CG_CASE_UNITS]; /* 0 a character, 1 a placeholder, 2 a pick, 3 an escape */
static unsigned char cg_cu_flag[CG_CASE_UNITS]; /* 1 quoted, 8 in sentence case */
static int cg_cu_sent[CG_CASE_UNITS];           /* each unit's sentence */
static unsigned char cg_cs_flag[CG_CASE_UNITS]; /* each sentence: 1 a lower-case letter, 2 a word of two or more
                                                   letters, 4 a "!" */
static int cg_cw_start[CG_CASE_UNITS], cg_cw_end[CG_CASE_UNITS], cg_cw_letters[CG_CASE_UNITS];
static unsigned char cg_cw_lower[CG_CASE_UNITS];
static int cg_case_label;                       /* cg_label_text: the text is a button's label */

static int cg_cu_char(const unsigned char *t, int u, unsigned char c) {
    return cg_cu_kind[u] == 0 && t[cg_cu_at[u]] == c;
}

static int cg_cu_mark(const unsigned char *t, int u) {
    return cg_cu_char(t, u, '.') || cg_cu_char(t, u, '!') || cg_cu_char(t, u, '?');
}

static int cg_cu_alnum(const unsigned char *t, int u) {
    return cg_cu_kind[u] == 0 && (cg_letter(t[cg_cu_at[u]]) || (t[cg_cu_at[u]] >= '0' && t[cg_cu_at[u]] <= '9'));
}

/* A space or a quotation mark (" ' and the cp1252 curly quotes 0x93 0x94). */
static int cg_cu_quote_or_space(const unsigned char *t, int u) {
    unsigned char c = t[cg_cu_at[u]];
    return cg_cu_kind[u] == 0 && (c == ' ' || c == '"' || c == '\'' || c == 0x93 || c == 0x94);
}

/* Where placeholder unit `u`'s word starts (its capital goes there): after its last "." before any "|". */
static int cg_ph_word_at(const unsigned char *t, int u) {
    int b, at = 1;
    for (b = 1; b < cg_cu_len[u] - 1 && t[cg_cu_at[u] + b] != '|'; ++b) {
        if (t[cg_cu_at[u] + b] == '.') {
            at = b + 1;
        }
    }
    return at;
}

static int cg_case_start(const unsigned char *t, int u, int item) {
    int k = u - 1;
    while (k >= 0 && cg_cu_quote_or_space(t, k)) {
        --k;
    }
    if (k < 0) {
        return !item;
    }
    return cg_cu_mark(t, k) || cg_cu_char(t, k, '\n');
}

/* The island's name keeps its capital ("isola", "isolan", and before an apostrophe: "isola's"). */
static int cg_case_proper(const unsigned char *t, int s0, int e0) {
    static const char *const names[] = {"isola", "isolan"};
    int i, b;
    for (i = 0; i < 2; ++i) {
        for (b = 0; s0 + b < e0 && t[cg_cu_at[s0 + b]] != '\'' && (unsigned char)names[i][b] == t[cg_cu_at[s0 + b]];
             ++b) {
        }
        if (names[i][b] == '\0' && (s0 + b == e0 || t[cg_cu_at[s0 + b]] == '\'')) {
            return 1;
        }
    }
    return 0;
}

/* `text` (NUL-ended, changed in place) with its capitals in sentence case where they mean nothing (cie-v6-binary.md
   20); `item`: a pool's item; `label`: a button's label. */
static void cg_sentence_case(char *text, int item, int label) {
    unsigned char *t = (unsigned char *)text;
    int n = 0, words = 0, k, w, u, upper = 0, sents = 0, q = 0, label_lower = 0, label_long = 0;
    for (k = 0; t[k] != 0; ++k) {
        upper |= cg_up(t[k]);
    }
    if (!upper) {
        return;
    }
    for (k = 0; t[k] != 0 && n < CG_CASE_UNITS; ++n) {
        unsigned char kind = 0;
        int len = cg_case_token(t + k, &kind);
        cg_cu_at[n] = k;
        cg_cu_kind[n] = len > 0 ? kind : 0;
        cg_cu_len[n] = len > 0 ? len : 1;
        cg_cu_flag[n] = 0;
        k += cg_cu_len[n];
    }
    if (t[k] != 0) {
        return;                         /* longer than any popup's text: as written */
    }
    for (k = 0; k < n;) {               /* the words */
        if (cg_cu_kind[k] == 0 && cg_letter(t[cg_cu_at[k]])) {
            int start = k, letters = 0, lower = 0;
            while (k < n && cg_cu_kind[k] == 0
                   && (cg_letter(t[cg_cu_at[k]])
                       || (t[cg_cu_at[k]] == '\'' && k > start && k + 1 < n && cg_cu_kind[k + 1] == 0
                           && cg_letter(t[cg_cu_at[k + 1]])))) {
                letters += cg_letter(t[cg_cu_at[k]]);
                lower |= cg_lo(t[cg_cu_at[k]]);
                ++k;
            }
            cg_cw_start[words] = start;
            cg_cw_end[words] = k;
            cg_cw_letters[words] = letters;
            cg_cw_lower[words] = (unsigned char)(lower != 0);
            ++words;
            continue;
        }
        ++k;
    }
    cg_cs_flag[0] = 0;                  /* the quotations and the sentences */
    for (k = 0; k < n; ++k) {
        unsigned char c = cg_cu_kind[k] == 0 ? t[cg_cu_at[k]] : 0;
        if (k > 0 && (cg_cu_char(t, k - 1, '\n') || (cg_cu_mark(t, k - 1) && !cg_cu_mark(t, k)))) {
            cg_cs_flag[++sents] = 0;
        }
        cg_cu_sent[k] = sents;
        if (cg_cu_kind[k] == 0) {
            if (c == '\n') {
                q = 0;
            } else if (q == 0 && (c == '"' || c == 0x93)) {
                q = 1;
            } else if (q == 1 && (c == '"' || c == 0x94)) {
                q = 0;
            } else if (c == '\'') {
                if (q == 0 && (k == 0 || (cg_cu_kind[k - 1] == 0 && !cg_cu_alnum(t, k - 1))) && k + 1 < n
                    && !cg_cu_char(t, k + 1, ' ') && !cg_cu_char(t, k + 1, '\n')) {
                    q = 2;              /* ' opens after no letter, digit, placeholder or pick, with one after it */
                } else if (q == 2 && (k + 1 >= n || !cg_cu_alnum(t, k + 1))) {
                    q = 0;
                }
            } else if (c == '!') {
                cg_cs_flag[sents] |= 4;
            }
        }
        if (q != 0) {
            cg_cu_flag[k] |= 1;
        }
    }
    for (w = 0; w < words; ++w) {
        cg_cs_flag[cg_cu_sent[cg_cw_start[w]]] |= (unsigned char)((cg_cw_lower[w] ? 1 : 0) | (cg_cw_letters[w] >= 2 ? 2 : 0));
        label_lower |= cg_cw_lower[w];
        label_long |= cg_cw_letters[w] >= 2;
    }
    for (u = 0; u < n; ++u) {           /* in sentence case: outside quotations, a label or a sentence */
        int b;
        if ((cg_cu_flag[u] & 1) != 0
            || (label ? (label_lower || !label_long) : (cg_cs_flag[cg_cu_sent[u]] & 7) != 2)) {
            continue;
        }
        cg_cu_flag[u] |= 8;
        for (b = 0; b < (cg_cu_kind[u] == 0 || cg_cu_kind[u] == 1 ? cg_cu_len[u] : 0); ++b) {
            t[cg_cu_at[u] + b] = cg_to_lo(t[cg_cu_at[u] + b]);
        }
    }
    for (u = 0; u < n; ++u) {
        if ((cg_cu_flag[u] & 8) && cg_cu_kind[u] == 1 && cg_cu_len[u] > 2 && cg_case_start(t, u, item)) {
            int at = cg_ph_word_at(t, u);
            t[cg_cu_at[u] + at] = cg_to_up(t[cg_cu_at[u] + at]);
        }
    }
    for (w = 0; w < words; ++w) {
        int s0 = cg_cw_start[w], e0 = cg_cw_end[w];
        unsigned char *c = t + cg_cu_at[s0];
        if ((cg_cu_flag[s0] & 8) == 0) {
            continue;
        }
        if (cg_case_start(t, s0, item)) {
            *c = cg_to_up(*c);
        }
        if ((*c == 'i' || *c == 'I') && (e0 - s0 == 1 || cg_cu_char(t, s0 + 1, '\''))) {
            *c = 'I';
        }
        if (cg_case_proper(t, s0, e0)) {
            *c = cg_to_up(*c);
        }
    }
}

/* `title` (NUL-ended, changed in place) in title case when it is written in capitals. */
static void cg_title_case(char *title) {
    unsigned char *t = (unsigned char *)title;
    int k, letters = 0, longest = 0, begin = 1;
    for (k = 0; t[k] != 0;) {
        unsigned char kind = 0;
        int len = cg_case_token(t + k, &kind);
        if (len > 0) {
            letters = 0;
            k += len;
            continue;
        }
        if (cg_lo(t[k])) {
            return;
        }
        if (cg_letter(t[k]) || t[k] == '\'') {
            letters += cg_letter(t[k]);
            if (letters > longest) {
                longest = letters;
            }
        } else {
            letters = 0;
        }
        ++k;
    }
    if (longest < 2) {
        return;
    }
    for (k = 0; t[k] != 0;) {
        unsigned char kind = 0;
        int len = cg_case_token(t + k, &kind), b;
        if (len > 0) {
            if (kind == 1 && len > 2) {
                int at = 1;
                for (b = 1; b < len; ++b) {
                    t[k + b] = cg_to_lo(t[k + b]);
                }
                for (b = 1; b < len - 1 && t[k + b] != '|'; ++b) {
                    if (t[k + b] == '.') {
                        at = b + 1;
                    }
                }
                t[k + at] = cg_to_up(t[k + at]);      /* "(NAME)": "(Name)", the name as written */
                begin = 0;
            } else {
                begin = 1;
            }
            k += len;
            continue;
        }
        if (cg_letter(t[k])) {
            t[k] = begin ? cg_to_up(t[k]) : cg_to_lo(t[k]);
            begin = 0;
        } else {
            begin = t[k] != '\'';
        }
        ++k;
    }
}

/* 35: the words of a role a sex_change or presentation effect names follow the change on the pages after it.  The
   pages are laid out (and their names filled) before the effects are made, so while cg_late_keep is set those words
   are kept in the page between \1 and \2, and cg_late_fill puts them in as each page is shown: the role's words as
   they were before the change on the page that makes it and the pages before, cg.female's after. */
static int cg_late_keep;
static unsigned int cg_late_mask;
static int cg_late_was[CG_MAX_ROLES];
static int cg_late_at[CG_MAX_ROLES];       /* 1 + the display that changed the role's words (0: none yet) */

/* The roles whose words an effect of the graph may change: those a sex_change or presentation effect names (an
   alias or other role: its members too). */
static unsigned int cg_late_roles(void) {
    unsigned int mask = 0;
    int i;
    for (i = 0; cg_g.d != NULL && cg_g.version >= 6 && i < cg_g.n_effect; ++i) {
        const unsigned char *e = cg_effect_at(&cg_g, i);
        if ((e[0] == CGE_SEX_CHANGE || e[0] == CGE_PRESENTATION) && e[1] < (unsigned int)cg_g.n_role) {
            const unsigned char *spec = cg_role_at(&cg_g, e[1]);
            unsigned int m = cg_u16(spec + 14);
            mask |= 1u << e[1];
            if (spec[0] == CG_ROLE_OTHER) {
                int al;
                for (al = 0; al < cg_g.n_role && m != (1u << al); ++al) {
                }
                m = al < cg_g.n_role ? cg_u16(cg_role_at(&cg_g, al) + 14) : 0u;
            }
            if (spec[0] >= CG_ROLE_ALIAS) {
                mask |= m;
            }
        }
    }
    return mask;
}

static int cg_expand_in(const char *raw, char *out, int cap, int mode, int name_room, int award_kind, int award,
                        int depth) {
    static char cased[CG_POOL_DEPTH + 2][CG_RAW_BYTES];
    int o = 0;
    const char *s = raw;
    if (cg_g.version >= 6 && mode != CG_EXPAND_AWARD && depth >= 0 && depth < CG_POOL_DEPTH + 2
        && lstrlenA(raw) < CG_RAW_BYTES) {
        /* 20: runs in capitals in sentence case, on the text as shown (a popup's whole text: src/vv_cie_graph.py
           cases the joined text too) */
        lstrcpynA(cased[depth], raw, CG_RAW_BYTES);
        cg_sentence_case(cased[depth], depth > 0, cg_case_label);
        s = cased[depth];
    }
    while (*s != '\0' && o < cap - 1) {
        char word[CG_NAME_BYTES + 32];
        const char *put = NULL;
        int repeat = 0, role;
        cg_ph ph;
        const char *e;
        if (cg_g.version >= 6 && *s == '\\' && (s[1] == '(' || s[1] == ')')) {
            /* A literal parenthesis: kept escaped until the text is filled for the screen. */
            if (mode == CG_EXPAND_AWARD) {
                if (o + 2 < cap) {
                    out[o++] = s[0];
                    out[o++] = s[1];
                }
            } else {
                out[o++] = s[1];
            }
            s += 2;
            continue;
        }
        if (cg_g.version >= 6 && *s == '{' && s[1] == '#') {
            /* 33: a count token -- the worst case its longest option; else kept for the page's pass after its
               effects are made (cg_display) */
            const char *opts;
            int which, olen, n = cg_count_token(s, &which, &opts, &olen);
            if (n > 0) {
                if (mode == CG_EXPAND_WORST) {
                    /* each option with its placeholders at their widest; the longest kept */
                    static char opt[CG_PAGE_BYTES], filled[CG_PAGE_BYTES], wide[CG_PAGE_BYTES];
                    int start = 0, i, best = 0;
                    wide[0] = '\0';
                    for (i = 0; i <= olen; ++i) {
                        if (i == olen || opts[i] == '|') {
                            int len;
                            cg_made_fill(opts + start, i - start, 1, name_room, opt, (int)sizeof opt);
                            len = cg_expand_in(opt, filled, (int)sizeof filled, mode, name_room, award_kind, award,
                                               depth + 1);
                            if (len > best) {
                                best = len;
                                lstrcpynA(wide, filled, (int)sizeof wide);
                            }
                            start = i + 1;
                        }
                    }
                    for (i = 0; wide[i] != '\0' && o < cap - 1; ++i) {
                        out[o++] = wide[i];
                    }
                } else {
                    int c;
                    for (c = 0; c < n && o < cap - 1; ++c) {
                        out[o++] = s[c];
                    }
                }
                s += n;
                continue;
            }
        }
        if (cg_g.version >= 6 && *s == '{') {
            int pool, instance, n = cg_parse_brace(&cg_g, s, &pool, &instance);
            if (n > 0 && pool < 0) {
                /* G5: {@tribe} / {@Tribe}: kept for the screen's pass; the worst case W x the longest tribe name
                   the game allows (31 in the first two games, 19 in the later three), else the name now. */
                if (mode == CG_EXPAND_AWARD) {
                    int c;
                    for (c = 0; c < n && o < cap - 1; ++c) {
                        out[o++] = s[c];
                    }
                } else if (mode == CG_EXPAND_WORST) {
                    int c, room = cg.game <= 2 ? 31 : 19;
                    for (c = 0; c < room && o < cap - 1; ++c) {
                        out[o++] = 'W';
                    }
                } else {
                    const char *t = cg_tribe_words(pool == CG_POOL_TRIBE_CAP);
                    int first = 1;
                    for (; *t != '\0' && o < cap - 1; ++t, first = 0) {
                        char c = *t;
                        if (first && pool == CG_POOL_TRIBE_CAP && c >= 'a' && c <= 'z') {
                            c = (char)(c - 'a' + 'A');
                        }
                        out[o++] = c;
                    }
                }
                s += n;
                continue;
            }
            if (n > 0) {
                if (depth < CG_POOL_DEPTH) {
                    int got = cg_expand_in(cg_pool_text(pool, instance, mode), out + o, cap - o, mode, name_room,
                                           award_kind, award, depth + 1);
                    o += got;
                    if (got > 0 && (out[o - 1] == '!' || out[o - 1] == '?') && s[n] == '.') {
                        ++s;    /* cie-v6-binary.md 6, step 5: no "!." / "?." after a pool's item */
                    }
                }
                s += n;
                continue;
            }
        }
        if (*s == '(' && cg_g.version >= 6 && cg_made_ph(s)) {
            /* 33: a made villager's name -- filled after the page's effects (cg_display); the worst case W x room */
            int c;
            if (mode == CG_EXPAND_WORST) {
                for (c = 0; c < name_room && o < cap - 1; ++c) {
                    out[o++] = 'W';
                }
            } else {
                for (c = 0; c < cg_made_len(cg_made_ph(s)) && o < cap - 1; ++c) {
                    out[o++] = s[c];
                }
            }
            s += cg_made_len(cg_made_ph(s));
            continue;
        }
        if (*s != '(') {
            out[o++] = *s++;
            continue;
        }
        e = s + 1;
        while (*e != '\0' && *e != ')' && *e != '(' && *e != '\n') {
            ++e;
        }
        if (*e != ')' || !cg_parse_ph(&cg_g, s + 1, (int)(e - s - 1), &ph)
            || (mode == CG_EXPAND_AWARD) != (ph.role < 0)) {
            /* not one this pass fills: copied as it is */
            int n = (int)(e - s) + (*e == ')' ? 1 : 0);
            while (n-- > 0 && o < cap - 1) {
                out[o++] = *s++;
            }
            continue;
        }
        role = ph.role >= 0 ? cg_resolve_role(ph.role) : -1;     /* an alias: its member drawn */
        if (cg_late_keep && mode == CG_EXPAND_REAL && role >= 0 && role < CG_MAX_ROLES && ph.what != CG_PH_NAME
            && ph.what != CG_PH_AWARD && ph.what != CG_PH_UNIT && ((cg_late_mask >> role) & 1u)) {
            /* 35: a word of a role whose sex or presentation an effect changes: kept (between \1 and \2, out of
               the glyph fallback's way) for the page's pass after its effects are made (cg_late_fill) */
            const char *t;
            if (o < cap - 1) {
                out[o++] = '\x01';
            }
            for (t = s + 1; t < e && o < cap - 1; ++t) {
                out[o++] = *t;
            }
            if (o < cap - 1) {
                out[o++] = '\x02';
            }
            s = e + 1;
            continue;
        }
        if (ph.what == CG_PH_AWARD) {
            if (award_kind >= 0) {
                wsprintfA(word, "%d", award);
                put = word;
            }
        } else if (ph.what == CG_PH_UNIT) {
            put = award_kind < 0 ? NULL : award_kind == 0 ? "food" : "tech points";
        } else if (ph.what == CG_PH_NAME && cg_pronoun_names) {
            /* A label too wide with the names: each name as its role's pronoun (cie-v6-binary.md 15). */
            const char *const *pair = cg_pronoun(ph.hint >= 0 ? ph.hint : CG_PH_HIM);
            put = mode == CG_EXPAND_WORST ? (lstrlenA(pair[1]) > lstrlenA(pair[0]) ? pair[1] : pair[0])
                                          : pair[role >= 0 && cg.female[role] ? 1 : 0];
        } else if (mode == CG_EXPAND_WORST) {
            if (ph.what == CG_PH_NAME && role >= 0 && cg_role_at(&cg_g, role)[0] == CG_ROLE_STRANGER) {
                repeat = cg_stranger_room(cg.game);       /* 16: the longest name in the game's lists */
                if (cg_role_at(&cg_g, role)[1] & CG_STRANGER_NEW_NAME) {
                    repeat += 1 + cg_last_room(cg.game);  /* 28: a space and the longest last name */
                }
            } else if (ph.what == CG_PH_NAME) {
                repeat = name_room;
            } else {
                const char *const *pair = cg_pronoun(ph.what);
                put = lstrlenA(pair[1]) > lstrlenA(pair[0]) ? pair[1] : pair[0];
            }
        } else if (ph.what == CG_PH_NAME) {
            put = role >= 0 && ((cg.bound & (1u << role)) || cg_role_at(&cg_g, role)[0] == CG_ROLE_STRANGER)
                  ? cg.name[role] : "";             /* 16: a named stranger's drawn name */
        } else {
            put = cg_pronoun(ph.what)[role >= 0 && cg.female[role] ? 1 : 0];
        }
        if (put != NULL) {
            int first = 1, from = o;
            for (; *put != '\0' && o < cap - 1; ++put) {
                char c = *put;
                if (first && ph.capital && c >= 'a' && c <= 'z') {
                    c = (char)(c - 'a' + 'A');
                }
                first = 0;
                out[o++] = c;
            }
            if (ph.caps && o > from) {
                CharUpperBuffA(out + from, (DWORD)(o - from));   /* ALL CAPS: the word in capitals */
            }
        }
        while (repeat-- > 0 && o < cap - 1) {
            out[o++] = 'W';
        }
        s = e + 1;
    }
    out[o] = '\0';
    return o;
}

/* `raw` with its placeholders filled into `out` (`cap` bytes): CG_EXPAND_AWARD only the award's (the amount and
   its unit, or nothing when there is none: award_kind -1) and -- version 6 -- the pools' drawn words (the pages
   are laid out with them), CG_EXPAND_WORST the longest names the game holds and the longer pronouns,
   CG_EXPAND_REAL the bound villagers; both of these last two with \( \) as parentheses and the glyph fallback.
   Returns the length. */
static int cg_expand(const char *raw, char *out, int cap, int mode, int name_room, int award_kind, int award) {
    int n = cg_expand_in(raw, out, cap, mode, name_room, award_kind, award, 0);
    if (mode != CG_EXPAND_AWARD && cg_g.version >= 6 && cg_fallback_on()) {
        n = cg_glyph_fallback(out, n, cap);
    }
    return n;
}

/* A button label as the player reads it into `out` (CE_LONG_LINE_BYTES bytes): the real names, or -- when that is
   wider than the screen or longer than a label holds -- each name as its role's pronoun (cie-v6-binary.md 15).  With
   Scrolling Popups a choice is a row that grows to as many lines as its label needs (native/shared/one_popup.h):
   only the sanity cap counts, never the screen's width. */
static void cg_label_text(const ce_adapter *a, const char *raw, char *out) {
    static char real[CE_LONG_LINE_BYTES * 4];
    int n, op = cg_one_popup(), limit = op ? CE_LONG_LINE_BYTES : CG_LABEL_V6;
    cg_case_label = 1;                  /* 20: a label is cased as a whole */
    n = cg_expand(raw, real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
    if (cg_g.version >= 6 && (n >= limit || (!op && ce_label_px(a, real) > ce_label_max_px(a)))) {
        cg_pronoun_names = 1;
        cg_expand(raw, real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
        cg_pronoun_names = 0;
    }
    cg_case_label = 0;
    lstrcpynA(out, real, limit);
}

typedef struct {
    int count;
    int off[CG_MAX_PAGES];
    int src_end[CG_MAX_PAGES];         /* where in the popup's text each page ends */
    int used;
    char buf[CG_RAW_BYTES + CG_MAX_PAGES];
} cg_pages;

typedef struct {
    const ce_adapter *a;
    const ce_layout *first;            /* page 0 */
    const ce_layout *rest;             /* every later page */
    const char *title;
    int reserve;                       /* lines kept free on every page */
    cg_pages *pages;
    int scroll;                        /* Scrolling Popups is installed: a page is as tall as the text (cg_scrolls) */
    const char *src;                   /* the popup's text being laid out ... */
    int consumed;                      /* ... and how much of it the pages so far hold */
    char page[CG_RAW_BYTES];
} cg_pager;

/* Whether "VVFP Scrolling Popups.dll" is installed in the game (VvfpScrollingPopupsInstalled: every one of its sites,
   which include every game's island-event popups): then a popup scrolls, so its text is never split into pages --
   each popup is ONE page, as tall as its text, limited only by the bytes the game's popup holds (CG_TEXT_MAX), as
   the patcher's own fit check counts it with scrolling (src/vv_cie_graph.py).  Without it the text is paged to fit
   the screen, as before. */
static int cg_scrolls(void) {
    typedef int (__stdcall *sp_installed_fn)(void);
    HMODULE module;
    sp_installed_fn installed;
#ifdef VVFP_TEST
    if (test_graph_scroll >= 0) {
        return test_graph_scroll;
    }
#endif
    module = GetModuleHandleA("VVFP Scrolling Popups.dll");
    installed = module != NULL ? (sp_installed_fn)(void *)GetProcAddress(module, "VvfpScrollingPopupsInstalled") : NULL;
    return installed != NULL && installed() != 0;
}

/* ONE popup per island event (the owner, 2026-11-14; native/shared/one_popup.h): with Scrolling Popups the event
   runs in ONE popup from start to finish -- the text from the start (or from an answer) up to and including the
   next question, or the ending, is one text (cg_group), its choices drawn after it by Scrolling Popups; a choice
   clicked shows the next text in the same popup (cg_resolve), OK ends it.  Without Scrolling Popups: pages, as
   before. */
static int cg_one_popup(void) {
    return cg_scrolls();
}

static int ce_game_of(const ce_adapter *a);

/* The bytes one popup's text may hold: with Scrolling Popups practically any (CE_LONG_TEXT_MAX: the dialog's field
   holds its start and Scrolling Popups draws the whole, native/shared/one_popup.h); without it the later games'
   popups hold 2,000. */
static int cg_text_max(const ce_adapter *a) {
    (void)a;
    return cg_one_popup() ? CE_LONG_TEXT_MAX : CG_TEXT_MAX;
}

/* `text` (raw: names not filled) fits page `pages->count` at its widest: its bytes, and -- unless the popup
   scrolls -- its lines. */
static int cg_fits(cg_pager *w, const char *text) {
    static char worst[CG_RAW_BYTES + 512];
    const ce_layout *l = w->pages->count == 0 ? w->first : w->rest;
    int n = cg_expand(text, worst, sizeof worst, CG_EXPAND_WORST, w->a->name_room, -1, 0);
    if (n > cg_text_max(w->a) || n >= (int)sizeof worst - 1) {
        return 0;
    }
    return w->scroll || ce_lines_used_in(l, w->title, worst) <= l->lines - w->reserve;
}

static void cg_flush(cg_pager *w) {
    cg_pages *p = w->pages;
    int n = lstrlenA(w->page);
    if (n > 0 && p->count < CG_MAX_PAGES && p->used + n + 1 <= (int)sizeof p->buf) {
        p->src_end[p->count] = w->consumed;
        p->off[p->count++] = p->used;
        memcpy(p->buf + p->used, w->page, (size_t)n + 1);
        p->used += n + 1;
    }
    w->page[0] = '\0';
}

/* `piece` (`n` bytes) after `sep` on this page, else alone on the next: 1, or 0 when it fits no page. */
static int cg_put(cg_pager *w, const char *sep, const char *piece, int n) {
    static char trial[CG_RAW_BYTES];
    int have = lstrlenA(w->page);
    int s = have > 0 ? lstrlenA(sep) : 0;
    if (have + s + n + 1 < (int)sizeof trial) {
        memcpy(trial, w->page, (size_t)have);
        memcpy(trial + have, sep, (size_t)s);
        memcpy(trial + have + s, piece, (size_t)n);
        trial[have + s + n] = '\0';
        if (cg_fits(w, trial)) {
            memcpy(w->page, trial, (size_t)(have + s + n + 1));
            w->consumed = (int)(piece - w->src) + n;
            return 1;
        }
    }
    if (have > 0) {
        cg_flush(w);
    }
    if (n + 1 < (int)sizeof trial) {
        memcpy(trial, piece, (size_t)n);
        trial[n] = '\0';
        if (cg_fits(w, trial)) {
            memcpy(w->page, trial, (size_t)n + 1);
            w->consumed = (int)(piece - w->src) + n;
            return 1;
        }
    }
    return 0;
}

/* A sentence no page can hold: word after word, page after page (never off the screen). */
static void cg_put_words(cg_pager *w, const char *s, int n) {
    const char *end = s + n;
    while (s < end) {
        const char *e = s;
        while (e < end && *e != ' ') {
            ++e;
        }
        if (!cg_put(w, " ", s, (int)(e - s))) {
            int have = lstrlenA(w->page);
            if ((int)(e - s) + have + 1 < (int)sizeof w->page) {
                memcpy(w->page + have, s, (size_t)(e - s));     /* one word alone: the popup cuts it, as ce_wrap */
                w->page[have + (int)(e - s)] = '\0';
                w->consumed = (int)(e - w->src);
            }
        }
        s = e;
        while (s < end && *s == ' ') {
            ++s;
        }
    }
}

/* The pages of a popup's raw text: whole paragraphs where they fit, else whole sentences (src/vv_cie_graph.py
   paginate), else words. */
static void cg_paginate(cg_pager *w, const char *text) {
    const char *p = text;
    w->pages->count = 0;
    w->pages->used = 0;
    w->page[0] = '\0';
    w->src = text;
    w->consumed = 0;
    for (;;) {
        const char *end = p;
        while (*end != '\0' && *end != '\n') {
            ++end;
        }
        if (!cg_put(w, "\n", p, (int)(end - p))) {
            const char *s = p;
            while (s < end) {
                const char *e = s;
                while (e < end && !(e > s && *e == ' ' && (e[-1] == '.' || e[-1] == '!' || e[-1] == '?'))) {
                    ++e;
                }
                if (!cg_put(w, " ", s, (int)(e - s))) {
                    cg_put_words(w, s, (int)(e - s));
                }
                s = e;
                while (s < end && *s == ' ') {
                    ++s;
                }
            }
        }
        if (*end == '\0') {
            break;
        }
        p = end + 1;
    }
    cg_flush(w);
}

/* A display's text: the title first where the popup leads with it, the page, and -- with `r` -- the refusal
   lines (with their reasons while they fit, else the count alone); 1 when it fits. */
/* One popup (cie-v6-binary.md 19): the choice just picked, as its row showed it (cg_label_text), set by cg_resolve
   while it composes the answer's text: the first line of the text's own words (after a title line and the picture's
   gap the dialog keeps), a blank line after it ("Honesty\n\n...").  Display only: the log's "Choice:" line is the
   record. */
static const char *cg_op_lead;

static int cg_compose_once(const ce_layout *l, const char *title, const char *text, const ce_result *r, int reasons,
                           char *out, int size) {
    ce_writer w;
    memset(&w, 0, sizeof w);
    w.out = out;
    w.size = size;
    w.width = l->width;
    w.max_lines = cg_scrolls() ? 0x7FFFFFFF : l->lines - 1;   /* a scrolling popup has room for every line */
    out[0] = '\0';
    if (l->with_title) {
        ce_wrap(&w, title);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
    }
    if (cg_op_lead != NULL && cg_op_lead[0] != '\0') {
        ce_wrap(&w, cg_op_lead);
        ce_newline(&w);
        ce_newline(&w);
    }
    ce_wrap(&w, text);
    if (r != NULL && r->refused > 0) {
        char line[CE_WHY_COUNT * 72 + 48];
        if (!reasons || !ce_why_line(r, line)) {
            if (r->refused == 1) {
                ce_tr_done(line, sizeof line, "vvfp.story/story_custom.ce_compose_in_once.s3",
                           "1 change could not be made.", "1 change could not be made.");
            } else {
                ce_tr_printf(line, sizeof line, "vvfp.story/story_custom.ce_compose_in_once.s4",
                             "%d changes could not be made.", r->refused);
            }
        }
        ce_newline(&w);
        ce_line(&w, line);
    }
    return !w.overflow;
}

static void cg_compose(const ce_layout *l, const char *title, const char *text, const ce_result *r, char *out,
                       int size) {
    if (!cg_compose_once(l, title, text, r, 1, out, size) && !cg_compose_once(l, title, text, r, 0, out, size)) {
        cg_compose_once(l, title, text, NULL, 0, out, size);
    }
}

/* A display: its page's words (names filled in), whether it is a question's result, whether its popup carries a
   villager's effect; its jobs are set by the caller.  Its index, or -1 when there is no room. */
static int cg_add_display(const char *text, int kind, int villager) {
    int n = lstrlenA(text);
    int k = cg.display_count;
    if (k >= CG_MAX_DISPLAYS || cg.display_used + n + 1 > CG_DISPLAY_BYTES) {
        return -1;
    }
    cg.display_off[k] = cg.display_used;
    memcpy(cg.displays + cg.display_used, text, (size_t)n + 1);
    cg.display_used += n + 1;
    cg.display_kind[k] = (unsigned char)kind;
    cg.display_node[k] = -1;
    cg.display_title[k] = 0;
    cg.display_villager[k] = (unsigned char)(villager != 0);
    cg.job_first[k] = (short)cg.jobs_used;
    cg.job_count[k] = 0;
    cg.applied_when[k] = 0;
    cg.sent_len[k] = 0;
    cg.display_count = k + 1;
    return k;
}

/* 33: what the effects made -- this page's, and the last page's that made any (-1 none known; memory only: after a
   quit and a restore the first option is shown). */
static int cg_count_last[2] = { -1, -1 };
static int cg_count_page[2];
static int cg_count_page_any[2];

static void cg_count_add(int which, int n) {
    if (which >= 0 && which < 2) {
        cg_count_page[which] += n > 0 ? n : 0;
        cg_count_page_any[which] = 1;
    }
}

/* `text` with its count tokens filled (cie-v6-binary.md 33), in a buffer of its own; `text` itself when it has
   none. */
static const char *cg_count_fill(const char *text) {
    static char out[CG_PAGE_BYTES];
    const char *s;
    int o = 0;
    for (s = text; *s != '\0' && !(s[0] == '{' && s[1] == '#') && !cg_made_ph(s); ++s) {
    }
    if (*s == '\0') {
        return text;
    }
    for (s = text; *s != '\0' && o < (int)sizeof out - 1;) {
        const char *opts = NULL;
        int which = 0, olen = 0, n = s[0] == '{' && s[1] == '#' ? cg_count_token(s, &which, &opts, &olen) : 0;
        if (n == 0 && cg_made_ph(s)) {
            char name[CG_NAME_BYTES + 16];
            const char *t;
            cg_made_name(cg_made_ph(s), name, (int)sizeof name);
            for (t = name; *t != '\0' && o < (int)sizeof out - 1; ++t) {
                out[o++] = *t;
            }
            s += cg_made_len(cg_made_ph(s));
            continue;
        }
        if (n > 0) {
            static char raw[CG_PAGE_BYTES], made[CG_PAGE_BYTES], real[CG_PAGE_BYTES];
            const ce_adapter *a = ce_adapter_for(cg.game);
            int len = cg_count_option(opts, olen, cg_count_last[which], raw, (int)sizeof raw), i;
            cg_made_fill(raw, len, 0, 0, made, (int)sizeof made);
            /* the event's own placeholders and the glyph fallback, as the rest of the page had them */
            cg_expand(made, real, (int)sizeof real, CG_EXPAND_REAL, a != NULL ? a->name_room : 0, -1, 0);
            for (i = 0; real[i] != '\0' && o < (int)sizeof out - 1; ++i) {
                out[o++] = real[i];
            }
            s += n;
            continue;
        }
        out[o++] = *s++;
    }
    out[o] = '\0';
    return out;
}

/* 33a: the renames the event made (change_name, lost name, mind swap), each with the display it was made on: a
   later display laid out before it has the old name, and gets the new one (whole words; memory only). */
#define CG_RENAMES 8
static struct {
    char was[CG_NAME_BYTES], now[CG_NAME_BYTES];
    int display;
} cg_renames[CG_RENAMES];
static int cg_rename_count;
static int cg_display_now = -1;           /* the display whose effects are being made */

static int cg_word_char(char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '\'';
}

/* Display `k`'s text with the later renames put in. */
static const char *cg_renames_fill(const char *text, int k) {
    static char out[CG_PAGE_BYTES];
    const char *s;
    int r, o = 0, any = 0;
    for (r = 0; r < cg_rename_count; ++r) {
        any |= cg_renames[r].display < k && cg_renames[r].was[0] != '\0';
    }
    if (!any) {
        return text;
    }
    for (s = text; *s != '\0' && o < (int)sizeof out - 1;) {
        int hit = -1;
        if (s == text || !cg_word_char(s[-1])) {
            for (r = cg_rename_count - 1; r >= 0 && hit < 0; --r) {
                int n = lstrlenA(cg_renames[r].was);
                if (cg_renames[r].display < k && n > 0 && memcmp(s, cg_renames[r].was, (size_t)n) == 0
                    && !cg_word_char(s[n])) {
                    hit = r;
                }
            }
        }
        if (hit >= 0) {
            const char *t;
            for (t = cg_renames[hit].now; *t != '\0' && o < (int)sizeof out - 1; ++t) {
                out[o++] = *t;
            }
            s += lstrlenA(cg_renames[hit].was);
            continue;
        }
        out[o++] = *s++;
    }
    out[o] = '\0';
    return out;
}

/* 35: role `role`'s words are about to change on the display being made: the pages up to it keep the old ones. */
static void cg_late_note(int role) {
    /* The FIRST change on a display keeps the words the page began with: a sex_change and then a presentation on
       the same page must not overwrite them with the in-between value (Codex, #787). */
    if (role >= 0 && role < CG_MAX_ROLES && cg_late_at[role] != cg_display_now + 1) {
        cg_late_was[role] = cg.female[role];
        cg_late_at[role] = cg_display_now + 1;
    }
}

/* 35: display `k`'s text with each kept word (\1 placeholder \2, cg_expand_in) put in: the role's words as they were
   before a change made on display k or later, else as they are now. */
static const char *cg_late_fill(const char *text, int k) {
    static char out[CG_PAGE_BYTES];
    const char *s;
    int o = 0;
    for (s = text; *s != '\0' && *s != '\x01'; ++s) {
    }
    if (*s == '\0') {
        return text;
    }
    for (s = text; *s != '\0' && o < (int)sizeof out - 1;) {
        const char *e = s + 1;
        cg_ph ph;
        if (*s != '\x01') {
            out[o++] = *s++;
            continue;
        }
        while (*e != '\0' && *e != '\x02') {
            ++e;
        }
        if (*e == '\x02' && cg_parse_ph(&cg_g, s + 1, (int)(e - s - 1), &ph) && ph.role >= 0) {
            int role = cg_resolve_role(ph.role), female, first = 1, from = o;
            const char *put;
            female = role >= 0 && role < CG_MAX_ROLES
                     && (cg_late_at[role] > 0 && k < cg_late_at[role] ? cg_late_was[role] : cg.female[role]);
            for (put = cg_pronoun(ph.what)[female ? 1 : 0]; *put != '\0' && o < (int)sizeof out - 1; ++put) {
                char c = *put;
                if (first && ph.capital && c >= 'a' && c <= 'z') {
                    c = (char)(c - 'a' + 'A');
                }
                first = 0;
                out[o++] = c;
            }
            if (ph.caps && o > from) {
                CharUpperBuffA(out + from, (DWORD)(o - from));
            }
        }
        s = *e == '\x02' ? e + 1 : e;
    }
    out[o] = '\0';
    return out;
}

static void cg_display_title(int k, char *out, int cap);

/* `out` (`cap` bytes) = a + b + c, cut at cap (wsprintfA stops at 1,024 characters: a long title or label is not). */
static void cg_join(char *out, int cap, const char *a, const char *b, const char *c) {
    int n;
    lstrcpynA(out, a, cap);
    n = lstrlenA(out);
    lstrcpynA(out + n, b, cap - n);
    n = lstrlenA(out);
    lstrcpynA(out + n, c, cap - n);
}
static char cg_title_rest[CE_LONG_LINE_BYTES * 4];

static const char *cg_display(int k) {
    static char wrapped[CG_PAGE_BYTES + CE_LONG_LINE_BYTES * 4 + 2];
    char title[CE_LONG_LINE_BYTES * 4];
    const char *text;
    if (k < 0 || k >= cg.display_count) {
        return "";
    }
    text = cg_count_fill(cg_late_fill(cg_renames_fill(cg.displays + cg.display_off[k], k), k));
    cg_display_title(k, title, (int)sizeof title);
    if (cg_title_rest[0] == '\0') {
        return text;
    }
    /* the title's second line (a choice's label wider than the title area), then the page */
    cg_join(wrapped, (int)sizeof wrapped, cg_title_rest, "\n", text);
    return wrapped;
}

/* ---- Per-node popup titles (docs/event-collection/cie-v6-binary.md 14) ------------------------------------- */

#define CG_TITLE_CHANGES 16

/* Node `node`'s popup title as display_title holds it (string index + 1), 0 for none (before version 6: none). */
static unsigned short cg_node_title(int node) {
    const unsigned char *n;
    if (cg_g.version < 6 || node < 0 || node >= cg_g.n_node) {
        return 0;
    }
    n = cg_node_at(&cg_g, node);
    return n[0] != CG_BRANCH && cg_u16(n + 26) != CG_NONE ? (unsigned short)(cg_u16(n + 26) + 1u) : 0;
}

/* 17: a title as shown fits the game: under CE_TITLE_BYTES, and the later games' title box in ldwarialbold
   (story_title_widths.h), the first two games' title_width (src/vv_cie_graph.py GAMES). */
static int cg_title_fits(const char *text) {
    static const int TITLE_WIDTH_V12[3] = { 0, 51, 46 };
    int n = lstrlenA(text), op = cg_one_popup();
    if (n >= (op ? CE_LONG_LINE_BYTES : CE_TITLE_BYTES)) {
        return 0;
    }
    if (op && cg.game >= 3 && cg.game <= 5) {
        return 1;                       /* Scrolling Popups wraps a title wider than its box (one_popup.h) */
    }
    if (cg.game >= 3 && cg.game <= 5) {
        int px = 0, i;
        for (i = 0; i < n; ++i) {
            unsigned char c = (unsigned char)text[i];
            px += CG_TITLE_PX[cg.game - 3][(c >= 32 && c < 127 ? c : 'A') - 32];
        }
        px += n > 0 ? CG_TITLE_SPACING[cg.game - 3] * (n - 1) : 0;
        return px <= CG_TITLE_BOX_PX[cg.game - 3];
    }
    return cg.game < 1 || cg.game > 2 || n <= TITLE_WIDTH_V12[cg.game];
}

/* Title `t` (0: the event's own) expanded with `mode` (CG_EXPAND_REAL / CG_EXPAND_WORST) into `out`: its names,
   or -- when that does not fit -- its names as pronouns (cie-v6-binary.md 17). */
static void cg_title_expand(unsigned short t, int mode, char *out, int cap) {
    static char buf[CE_LONG_LINE_BYTES * 4];
    const ce_adapter *a = ce_adapter_for(cg.game);
    const char *raw = cg_s(&cg_g, t == 0 ? (unsigned int)cg_g.title : (unsigned int)t - 1u);
    int room = a != NULL ? a->name_room : 0;
    static char cased[CE_LONG_LINE_BYTES * 4];
    if (cg_g.version < 6) {
        lstrcpynA(out, t == 0 ? cg.title : raw, cap);
        return;
    }
    lstrcpynA(cased, raw, sizeof cased);
    cg_title_case(cased);                               /* 20: a title in capitals in title case */
    raw = cased;
    cg_expand(raw, buf, sizeof buf, mode, room, -1, 0);
    if (!cg_title_fits(buf)) {
        cg_pronoun_names = 1;
        cg_expand(raw, buf, sizeof buf, mode, room, -1, 0);
        cg_pronoun_names = 0;
    }
    lstrcpynA(out, buf, cap);
}

/* The words of title `t` (0: the event's own) as the player reads them, into `out`. */
static void cg_title_text(unsigned short t, char *out, int cap) {
    cg_title_expand(t, CG_EXPAND_REAL, out, cap);
}

/* 17: graph `g`'s title as written (its placeholders kept, as "(Name1)'s No Good, Very Bad Day"): what the lists
   made before anyone is cast show (Pick Island Event, the library, the refusals, "is on its way"); cut to
   CE_TITLE_BYTES - 1. A title written in capitals is in title case (20), as everywhere
   it is shown. */
static const char *cg_readable(const cg_graph *g) {
    static char buf[CE_TITLE_BYTES];
    static char cased[CE_LONG_LINE_BYTES * 4];
    lstrcpynA(cased, cg_s(g, (unsigned int)g->title), sizeof cased);
    cg_title_case(cased);                               /* 20: a title in capitals in title case */
    lstrcpynA(buf, cased, sizeof buf);
    return buf;
}

/* 17: the running event's title with the cast villagers' real names (never pronouns: the log has no title box),
   for the Island Events log's "Event:" line and "Disappeared in ...". */
static void cg_title_logged(char *out, int cap) {
    static char buf[CE_LONG_LINE_BYTES * 4];
    static char cased[CE_LONG_LINE_BYTES * 4];
    const ce_adapter *a = ce_adapter_for(cg.game);
    if (cg_g.version < 6) {
        lstrcpynA(out, cg.title, cap);
        return;
    }
    lstrcpynA(cased, cg_s(&cg_g, (unsigned int)cg_g.title), sizeof cased);
    cg_title_case(cased);                               /* 20: a title in capitals in title case */
    cg_expand(cased, buf, sizeof buf, CG_EXPAND_REAL, a != NULL ? a->name_room : 0, -1, 0);
    lstrcpynA(out, buf, cap);
}

/* The title of display `k`'s popup, into `out`. */
static char cg_title_rest[CE_LONG_LINE_BYTES * 4];   /* the part of the last title shown that did not fit its area */

/* Title `title` (as shown) cut to what fits the title area, at a space; what is left into cg_title_rest. */
static void cg_title_wrap(char *title) {
    static char head[CE_LONG_LINE_BYTES * 4];
    int n = lstrlenA(title), cut = -1, i;
    cg_title_rest[0] = '\0';
    if (n == 0 || cg_title_fits(title)) {
        return;
    }
    for (i = 1; i < n && i < (int)sizeof head - 1; ++i) {
        if (title[i] == ' ') {
            memcpy(head, title, (size_t)i);
            head[i] = '\0';
            if (!cg_title_fits(head)) {
                break;
            }
            cut = i;
        }
    }
    if (cut <= 0) {
        for (cut = n - 1; cut > 1; --cut) {   /* one long word: as many letters as fit */
            memcpy(head, title, (size_t)cut);
            head[cut] = '\0';
            if (cg_title_fits(head)) {
                break;
            }
        }
        lstrcpynA(cg_title_rest, title + cut, (int)sizeof cg_title_rest);
    } else {
        lstrcpynA(cg_title_rest, title + cut + 1, (int)sizeof cg_title_rest);
    }
    title[cut] = '\0';
}

static void cg_display_title(int k, char *out, int cap) {
    static char full[CE_LONG_LINE_BYTES * 4];
    cg_title_text(k >= 0 && k < cg.display_count ? cg.display_title[k] : 0, full, (int)sizeof full);
    cg_title_wrap(full);                /* a choice's label wider than the title area: its rest on the page */
    lstrcpynA(out, full, cap);
}

/* The title in force before history node `upto`: the last titled node's on the way, else the event's. */
static unsigned short cg_title_before(const cg_history *h, int upto) {
    unsigned short t = 0;
    int i;
    for (i = 0; i < upto && i < h->nodes; ++i) {
        unsigned short nt = cg_node_title(h->node[i]);
        if (nt != 0) {
            t = nt;
        }
    }
    return t;
}

/* ---- The effects ------------------------------------------------------------------------------------------ */

typedef void (__stdcall *cg_told_fn)(int game, int index, const char *words);

static void cg_tell_words(const char *export_name, int game, int index, const char *words, int fallback) {
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    cg_told_fn told = module != NULL ? (cg_told_fn)(void *)GetProcAddress(module, export_name) : NULL;
    if (told != NULL) {
        told(game, index, words);
    } else if (fallback == 1) {
        ce_tell_killed(game, index);
    } else if (fallback == 2) {
        ce_tell_cause_of_death(game, index);
    }
}

static void cg_tell_killed(int game, int index, const char *cause) {
#ifdef VVFP_TEST
    cg_test_tell(1, index, cause);
#endif
    if (lstrcmpA(cause, "unknown") == 0) {
        return;                        /* the game's own "Unknown causes", as the stock island events */
    }
    if (lstrcmpA(cause, "custom") == 0) {
        ce_tell_killed(game, index);   /* "Died in a custom island event" */
        return;
    }
    cg_tell_words("VvfpCauseKilledBy", game, index, cause, 1);
}

static void cg_tell_vanished(int game, int index) {
    char words[CE_TITLE_BYTES + 24], title[CE_TITLE_BYTES];
    cg_title_logged(title, sizeof title);
    wsprintfA(words, "Disappeared in %s", title);
#ifdef VVFP_TEST
    cg_test_tell(2, index, words);
#endif
    cg_tell_words("VvfpCauseVanishedBy", game, index, words, 2);
}

/* cie-v6-binary.md 22: "died, no body" -- the villager just taken with no body is a DEATH in the Deaths log, with the
   cause ALWAYS "Unknown causes" (the owner's rule for the new events: no author's words, whatever the file holds)
   and no grave (VvfpCauseDiedUnrecovered).  An older Cause of Death companion without it: told as a
   disappearance. */
static void cg_tell_died_unrecovered(int game, int index) {
    typedef void (__stdcall *died_fn)(int game, int index, const char *words);
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    died_fn died = module != NULL ? (died_fn)(void *)GetProcAddress(module, "VvfpCauseDiedUnrecovered") : NULL;
    const char *words = "Unknown causes";
#ifdef VVFP_TEST
    cg_test_tell(4, index, words);
#endif
    if (died != NULL) {
        died(game, index, words);
    } else {
        cg_tell_vanished(game, index);
    }
}

/* ...and a nursing parent's lost baby, told BEFORE the pregnancy ends (it reads the babies from the record): the
   Births and Conceptions log's "Lost before birth" record closes the open Conception (VvfpCauseBabyLost). */
static void cg_tell_baby_lost(int game, int index) {
    typedef void (__stdcall *lost_fn)(int game, int index, const char *what);
    char what[CE_TITLE_BYTES + 48], title[CE_TITLE_BYTES];
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    lost_fn lost = module != NULL ? (lost_fn)(void *)GetProcAddress(module, "VvfpCauseBabyLost") : NULL;
    cg_title_logged(title, sizeof title);
    wsprintfA(what, "the baby was lost in %s; never born", title);
#ifdef VVFP_TEST
    cg_test_tell(5, index, what);
#endif
    if (lost != NULL) {
        lost(game, index, what);
    }
}

/* cie-v6-binary.md 23: the babies were born just now, so "VVFP Cause of Death.dll" forgets the parent's nursing
   state it copied on the last frame (VvfpCauseDelivered) -- the Death record that follows must not say the babies
   were lost with the parent.  An older companion without it: nothing (its Death record may then say so). */
static void cg_tell_delivered(int game, int index) {
    typedef void (__stdcall *delivered_fn)(int game, int index);
    HMODULE module = GetModuleHandleA("VVFP Cause of Death.dll");
    delivered_fn delivered = module != NULL ? (delivered_fn)(void *)GetProcAddress(module, "VvfpCauseDelivered")
                                            : NULL;
#ifdef VVFP_TEST
    cg_test_tell(6, index, "");
#endif
    if (delivered != NULL) {
        delivered(game, index);
    }
}

/* A believer the event made a Heathen is a faith conversion (the owner): "VVFP Faith Notice.dll" counts it with
   the drift's (its "other" reason), so "Popup When Believers Become Heathens" tells of it when that patch is on. */
static void cg_tell_faith(int game, int index) {
    typedef void (__stdcall *count_fn)(int game, int reason);
    HMODULE module;
    count_fn count;
#ifdef VVFP_TEST
    cg_test_tell(3, index, "");
#endif
    (void)index;
    module = GetModuleHandleA("VVFP Faith Notice.dll");
    count = module != NULL ? (count_fn)(void *)GetProcAddress(module, "VvfpFaithNoticeCount") : NULL;
    if (count != NULL) {
        count(game, 4);
    }
}

static void cg_merge_result(ce_result *into, const ce_result *r) {
    int k;
    into->refused += r->refused;
    into->died += r->died;
    into->vanished += r->vanished;
    for (k = 0; k < CE_WHY_COUNT; ++k) {
        into->why[k] += r->why[k];
    }
}

static void cg_amount(const ce_adapter *a, int food, int amount, ce_result *r) {
    unsigned int cap = food ? CAP_FOOD : CAP_TECH;
    if (!(a->caps & cap)) {
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    if (amount > 0) {
        (food ? a->change_food : a->change_tech)(CE_AMOUNT_ADD, amount);
    } else if (amount < 0) {
        (food ? a->change_food : a->change_tech)(CE_AMOUNT_SUBTRACT, -amount);
    }
}

/* The preference's index by the game's own word, -1 when the game has none. */
static int cg_preference(const ce_adapter *a, const char *word) {
    char entry[48];
    int i;
    for (i = 0; ui_list_entry(a->pref_list, i, entry, sizeof entry); ++i) {
        if (lstrcmpiA(entry, word) == 0) {
            return i < a->pref_count ? i : -1;
        }
    }
    return -1;
}

/* ---- Version 6 effects ---------------------------------------------------------------------------------- */

/* Each game's own "Celebrating" (story_c1.inc .. story_c5.inc): A New Home 0x443FA0 with 9, The Lost Children the
   village celebration place 24 (0x459B60), the later three their action 0x52 / 0x2A / 0x31.  A bad mood is the
   villager shaking their head (every game has it); a good mood is the celebration (the owner's Q8 answer). */
static const char *const CG_CELEBRATE_WORDS[6] = {
    "", "Celebrating", "Celebrating (a new hut, first hut place) [Old Friends]", "Celebrating", "Celebrating",
    "Celebrating" };
#define CG_MOOD_BAD_WORDS "Shaking head"

/* The adapter's behaviour whose label is `words` (ignoring case), -1 none. */
static int cg_behaviour_by_words(const ce_adapter *a, const char *words) {
    int i;
    for (i = 0; a->behaviours != NULL && i < a->behaviour_count; ++i) {
        if (lstrcmpiA(a->behaviours[i].label, words) == 0) {
            return i;
        }
    }
    return -1;
}

/* The behaviour a celebrate, action or mood effect starts in `game`, -1 when the game has none. */
static int cg_behaviour_of(const ce_adapter *a, int game, const unsigned char *e) {
    const char *words;
    if (game < 1 || game > 5) {
        return -1;
    }
    switch (e[0]) {
    case CGE_CELEBRATE: words = CG_CELEBRATE_WORDS[game]; break;
    case CGE_MOOD: words = (int)cg_u32(e + 4) > 0 ? CG_CELEBRATE_WORDS[game] : CG_MOOD_BAD_WORDS; break;
    default: words = cg_s(&cg_g, cg_u16(e + 12)); break;
    }
    return cg_behaviour_by_words(a, words);
}

/* Whether effect `e` harms its villager (docs/event-collection/cie-v6-binary.md 7). */
static int cg_effect_harmful(const ce_adapter *a, int game, const unsigned char *e) {
    int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
    switch (e[0]) {
    case CGE_KILL: case CGE_VANISH: case CGE_SICK: case CGE_DIE_UNRECOVERED: case CGE_BABY_LOST:
    case CGE_BIRTH_THEN_DIE: case CGE_DELIVER_EARLY: case CGE_APOSTASY:
        return 1;
    case CGE_HEALTH: return hi < 100;
    case CGE_HEALTH_CHANGE: return lo < 0;
    case CGE_PREF: return (e[2] & 4u) != 0;
    case CGE_SKILL: return lo < 0;
    case CGE_MOOD: return lo < 0;
    case CGE_ACTION: {
        int b = cg_behaviour_of(a, game, e);
        return b >= 0 && (a->behaviours[b].group == CE_GROUP_MOOD || a->behaviours[b].unsafe != NULL);
    }
    default: return 0;
    }
}

/* A living villager's health now (every game's own field: the one its set_health writes). */
static int cg_health_now(int game, const unsigned char *record) {
    static const unsigned int OFFSET[6] = { 0, 0x344u, 0x52Cu, 0xE78u, 0x1C40u, 0x1C40u };
    return game >= 1 && game <= 5 ? *(const int *)(record + OFFSET[game]) : CE_HEALTH_MAX;
}

/* "celebrate" with "who": "all": every living, listed villager (New Believers: its believers) starts the game's
   own celebration -- children, nursing parents and the protected villagers too (a celebration harms no one). */
static void cg_celebrate_all(const ce_adapter *a, int game, ce_result *r) {
    static const unsigned char CELEBRATE[16] = { CGE_CELEBRATE, CG_ROLE_ALIAS_ALL };
    ce_result one;
    int i, behaviour = cg_behaviour_of(a, game, CELEBRATE);
    if (behaviour < 0) {
        return;
    }
    if (!(a->caps & CAP_BEHAVIOUR)) {
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    memset(&cg_one, 0, sizeof cg_one);
    cg_one.game = game;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS && cg_one.change_count < CE_MAX_CHANGES; ++i) {
        const unsigned char *record = a->record(i);
        ce_change *c;
        if (record == NULL || !a->listed(record) || cg_heathen(game, record) || (game == 3 && record[0xE94] != 0)) {
            continue;
        }
        c = &cg_one.changes[cg_one.change_count++];
        ce_change_init(c);
        c->index = i;
        c->fingerprint = ce_identity(a, record);
        c->behaviour = behaviour;
    }
    if (cg_one.change_count > 0) {
        ce_apply(a, &cg_one, &one);
        cg_merge_result(r, &one);
    }
}

/* The lines a page's effects add to the event's ONE log entry beyond the companion's comparison (a damaged
   structure, as The Rumblings writes it). */
/* What the comparison of the villagers cannot say, for the page's log lines: room for a whole group's (every
   villager's "<name>'s head look is now Old.", a group cure ...), within the entry's own CG_ENTRY_BYTES. */
static char cg_extra_lines[4096];

#ifdef VVFP_TEST
static int test_graph_structures = -1;  /* the finished structures (bit k), -1 = as the game says */
static int test_graph_damaged[SD_MAX_STRUCTURES];   /* each structure's loss the test build recorded */
static int test_graph_supply_cap = -1;  /* "VVFP VV4 Supply Cap.dll" (32): -1 as it is, 0 none, 1 installed */
#endif

#ifdef VVFP_TEST
/* "VVFP Head Look.dll" as the test build sees it (cie-v6-binary.md 27): -1 the real one; 0 none; 1 installed, each
   look set recorded (the record's index, the look). */
static int test_graph_head_look = -1;
static int test_graph_head_look_set[16][2];
static int test_graph_head_looks;
#endif

/* cie-v6-binary.md 27: the villager in record `index` is drawn with the OLD head from now on -- the per-villager
   head look Change Appearance offers, kept in "VVFP Head Look.dll"'s own per-save file (never a record field).
   0 when it cannot be made (the companion is not in the game, its draws do not follow the look, the write failed). */
static int cg_head_look(int game, const unsigned char *record, int index, int look) {
    vvfp_head_look_api api;
#ifdef VVFP_TEST
    if (test_graph_head_look >= 0) {
        if (test_graph_head_look == 0) {
            return 0;
        }
        if (test_graph_head_looks < 16) {
            test_graph_head_look_set[test_graph_head_looks][0] = index;
            test_graph_head_look_set[test_graph_head_looks++][1] = look;
        }
        return 1;
    }
#endif
    (void)index;
    return vvfp_head_look_find(game, &api) && api.set(game, record, look) == 1;
}

static int cg_old_look(int game, const unsigned char *record, int index) {
    return cg_head_look(game, record, index, VVFP_HEAD_LOOK_OLD);
}

#ifdef VVFP_TEST
/* "VVFP Gender Presentation.dll" as the test build sees it (cie-v6-binary.md 31): -1 the real one; 0 none; 1
   installed, each choice set recorded (the record's index, the choice). */
static int test_graph_presentation = -1;
static int test_graph_presentation_set[16][2];
static int test_graph_presentations;
#endif

/* cie-v6-binary.md 31: the villager in record `index` is drawn with the other sex's look (`on` 1) or their own again
   (0) -- the choice Change Appearance's "Gender presentation" offers, kept in "VVFP Gender Presentation.dll"'s own
   per-save file (never a record field; the sex field is not written).  0 when it cannot be made (the companion is
   not in the game, its draws do not follow the choice, a special villager, the write failed). */
static int cg_presentation(int game, const unsigned char *record, int index, int on) {
    vvfp_gp_api api;
    if (vv_sex_change_refusal(game, record, index) != VV_SEX_OK) {
        return 0;
    }
#ifdef VVFP_TEST
    if (test_graph_presentation >= 0) {
        if (test_graph_presentation == 0) {
            return 0;
        }
        if (test_graph_presentations < 16) {
            test_graph_presentation_set[test_graph_presentations][0] = index;
            test_graph_presentation_set[test_graph_presentations++][1] = on;
        }
        if (test_graph_presented >= 0 && index >= 0 && index < 31) {
            test_graph_presented = on ? (test_graph_presented | (1 << index)) : (test_graph_presented & ~(1 << index));
        }
        return 1;
    }
#endif
    return vvfp_gp_find(game, &api) && api.set(game, record, on) == 1;
}

/* ---- The sex field changed (docs/event-collection/cie-v6-binary.md 29) ------------------------------------ */

/* Why villager `record` cannot have their sex changed now (a CE_WHY_*), or -1 when they can: a special villager
   (cg_special, cg_never_harmed: the Golden Child, The Secret City's Tribal Chief and stand-in, New Believers' story
   villagers; native/shared/sex_change.h vv_sex_change_refusal the same).  Carrying or nursing is no refusal (the
   owner, 2026-11-15): no game's delivery depends on the carrier's sex (tests/test_sex_change_carrier_all.py), so
   they go on carrying, the carrying parent on the babies' records.  Every companion that keeps data by the sex
   follows the change (sex_change.h, VvfpVillagerSexChanged). */
static int cg_sex_change_refusal(const ce_adapter *a, int game, const unsigned char *record) {
    if (vv_sex_golden_child(game, record) && vv_sex_gc_draws_follow(game)) {
        return -1;                     /* option 1: his look stays a boy's (the Gender Presentation companion) */
    }
    if (cg_special(a, game, record) || cg_never_harmed(game, record)) {
        return CE_WHY_OTHER;
    }
    return -1;
}

/* One more line for the event's log entry ("  <text>\n"), when it fits. */
static void cg_extra_add(const char *who, const char *what) {
    char line[224];
    wsprintfA(line, "  %s%s\n", who, what);
    if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
        lstrcatA(cg_extra_lines, line);
    }
}

static int cg_structure_finished(int game, int k) {
#ifdef VVFP_TEST
    if (test_graph_structures >= 0) {
        return (test_graph_structures >> k) & 1;
    }
#endif
    return sd_finished(game, k);
}

/* Structure `k` of `game` is one the effect's list names ("any": every one). */
static int cg_structure_listed(int game, const char *list, int k) {
    char word[64];
    int entry;
    if (lstrcmpiA(list, "any") == 0) {
        return 1;
    }
    for (entry = 0; ui_list_entry(list, entry, word, sizeof word); ++entry) {
        if (sd_find(game, word) == k) {
            return 1;
        }
    }
    return 0;
}

/* "damage": one finished structure the effect names (drawn among them by the game's random routine as it is made)
   loses `percent` of its building work -- the states only a normal construction passes through
   (native/shared/structure_damage.h); none finished: nothing.  Nobody is hurt. */
static void cg_damage(const ce_adapter *a, int game, const unsigned char *e, int percent) {
    const char *list = cg_s(&cg_g, cg_u16(e + 12));
    int candidates[SD_MAX_STRUCTURES], n = 0, k;
    char line[160];
    for (k = 0; k < sd_structures(game) && k < SD_MAX_STRUCTURES; ++k) {
        if (cg_structure_finished(game, k) && cg_structure_listed(game, list, k)) {
            candidates[n++] = k;
        }
    }
    if (n == 0 || percent < 1) {
        return;
    }
    k = candidates[ce_random_below(a, n)];
    if (percent > 100) {
        percent = 100;
    }
#ifdef VVFP_TEST
    if (test_graph_structures >= 0) {
        test_graph_damaged[k] = percent;
    } else
#endif
    {
        __try {
            sd_damage(game, k, percent, a->record, a->record_count);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    wsprintfA(line, "  Damaged: %s, %d%% of its building work lost%s\n", sd_name(game, k), percent,
              percent >= 100 ? " (back to unbuilt)" : "");
    if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
        lstrcatA(cg_extra_lines, line);
    }
}

/* The villagers this event made last (new_villager, clone), the newest first: role bytes 253 and 252.  Memory only:
   they are for the effects of the same page (a quit before the next page forgets them, and those effects do
   nothing). */
static int cg_newest[2] = { -1, -1 };
static unsigned int cg_newest_id[2];

static char cg_renamed_now[CG_NAME_BYTES];   /* (renamed): the name the latest rename gave ("" none yet) */
static unsigned char *cg_target(const ce_adapter *a, int who, int *index);

static void cg_made_name(int k, char *out, int cap) {
    const ce_adapter *a = ce_adapter_for(cg.game);
    if (k == 3) {
        int i;
        if (cg_renamed_now[0] != '\0') {
            lstrcpynA(out, cg_renamed_now, cap);
            return;
        }
        /* before any rename: the current name of the villager the event's first change_name is for */
        for (i = 0; i < cg_g.n_effect; ++i) {
            const unsigned char *e = cg_effect_at(&cg_g, i);
            int at = -1;
            unsigned char *r = e[0] == CGE_CHANGE_NAME && a != NULL ? cg_target(a, e[1], &at) : NULL;
            if (r != NULL) {
                ce_copy_name(out, cap, r + a->off_name, a->name_bytes);
                return;
            }
        }
        lstrcpynA(out, "the villager", cap);
        return;
    }
    int pick = k == 2 && cg_newest[1] >= 0 ? 1 : 0;   /* (made1) the newest, (made2) the one before it */
    unsigned char *r = a != NULL && cg_newest[pick] >= 0 ? ce_same_villager(a, cg_newest[pick], cg_newest_id[pick])
                                                         : NULL;
    if (r == NULL) {
        lstrcpynA(out, "a newcomer", cap);
        return;
    }
    ce_copy_name(out, cap, r + a->off_name, a->name_bytes);
}

/* A villager renamed (or their likes changed: a mind swap) by this event: the run's roles that are them keep
   following them (their identity holds the name) and show the new name; the rename kept for the later pages. */
static void cg_renamed_record(const ce_adapter *a, const unsigned char *record, const char *was) {
    int r;
    char now[CG_NAME_BYTES];
    ce_copy_name(now, CG_NAME_BYTES, record + a->off_name, a->name_bytes);
    for (r = 0; r < CG_MAX_ROLES; ++r) {
        if ((cg.bound & (1u << r)) && !(cg.gone & (1u << r)) && a->record(cg.record[r]) == record) {
            cg.identity[r] = ce_identity(a, record);
            lstrcpynA(cg.name[r], now, CG_NAME_BYTES);
        }
    }
    for (r = 0; r < 2; ++r) {
        if (cg_newest[r] >= 0 && a->record(cg_newest[r]) == record) {
            cg_newest_id[r] = ce_identity(a, record);
        }
    }
    if (was != NULL && lstrcmpA(was, now) != 0 && cg_rename_count < CG_RENAMES) {
        lstrcpynA(cg_renames[cg_rename_count].was, was, CG_NAME_BYTES);
        lstrcpynA(cg_renames[cg_rename_count].now, now, CG_NAME_BYTES);
        cg_renames[cg_rename_count++].display = cg_display_now;
    }
}

/* A NAME THE EVENT CHANGED (lose_name, change_name, body_swap), in the Births and Conceptions log as every other
   rename is -- A New Home's parentage companion's and Last Names' "Name changed" record ("VVFP Parentage
   Export.dll" WriteVillageRecord, kind 10: held until the next save), so the Family Tree Maker, Repair Saves & Logs
   and the readers that follow a villager through "Name changed" records know the renamed villager is the same one
   (the owner, 2026-11-17: the logs keep track of everything):
       Name changed
         Name: <the name now>
         Old name: <the name before>
         Age: <game units>
         Changed by: <the event's title> (island event)
         Head / Body / Likes / Dislikes
   Nothing when the name did not change or the log is not part of the game.  A New Home with its parentage companion
   ("VVFP VV1 Parentage.dll", Show Parents) in the game: nothing here either -- that companion writes the same record
   for every name that changes in play, this one included, and it would be in the log twice. */
typedef int (__stdcall *cg_write_record_fn)(int, int, const void *, int, const char *, const char *, int);
#ifdef VVFP_TEST
static int test_graph_name_changes;     /* the records handed over */
#endif

static void cg_log_name_change(const ce_adapter *a, int game, const unsigned char *record, const char *was) {
    static cg_write_record_fn write_record;
    static int looked;
    char now[CG_NAME_BYTES], title[CG_LABEL_V6 * 4], before[CG_NAME_BYTES + CG_LABEL_V6 * 4 + 96];
    if (record == NULL || was == NULL) {
        return;
    }
    ce_copy_name(now, CG_NAME_BYTES, record + a->off_name, a->name_bytes);
    if (lstrcmpA(was, now) == 0 || (game == 1 && GetModuleHandleA("VVFP VV1 Parentage.dll") != NULL)) {
        return;
    }
    if (!looked) {
        HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
        looked = 1;
        write_record = module != NULL ? (cg_write_record_fn)(void *)GetProcAddress(module, "WriteVillageRecord")
                                      : NULL;
    }
#ifdef VVFP_TEST
    ++test_graph_name_changes;
#endif
    if (write_record == NULL) {
        return;
    }
    cg_title_logged(title, sizeof title);
    wsprintfA(before, "  Old name: %s\n  Age: %d\n  Changed by: %s (island event)\n", was, ce_age(a, record),
              title[0] ? title : "an island event");
    (void)write_record(game, 10, record, 1, before, NULL, 1);
}

static void cg_newest_reset(void) {
    cg_newest[0] = cg_newest[1] = -1;
    cg_renamed_now[0] = '\0';
    cg_rename_count = 0;
    cg_count_last[0] = cg_count_last[1] = -1;
    {
        int r;
        for (r = 0; r < CG_MAX_ROLES; ++r) {
            cg_late_at[r] = 0;         /* 35: no role's words changed yet */
        }
    }
}

static void cg_newest_push(const ce_adapter *a, int index) {
    unsigned char *r = a->record(index);
    if (r == NULL) {
        return;
    }
    cg_newest[1] = cg_newest[0];
    cg_newest_id[1] = cg_newest_id[0];
    cg_newest[0] = index;
    cg_newest_id[0] = ce_identity(a, r);
}

/* The villager an effect's role byte `who` names now (a role, an alias's member, or 253 / 252), its record index
   in *index; NULL when nobody (gone, unbound, not made). */
static unsigned char *cg_target(const ce_adapter *a, int who, int *index) {
    unsigned char *rec;
    int role;
    if (who == (int)CG_ROLE_NEWEST || who == (int)CG_ROLE_NEWEST2) {
        int k = who == (int)CG_ROLE_NEWEST ? 0 : 1;
        if (cg_newest[k] < 0) {
            return NULL;
        }
        rec = ce_same_villager(a, cg_newest[k], cg_newest_id[k]);
        if (rec != NULL) {
            *index = cg_newest[k];
        }
        return rec;
    }
    role = cg_resolve_role(who);
    if (role < 0 || (rec = cg_villager(a, role)) == NULL) {
        return NULL;
    }
    *index = cg.record[role];
    return rec;
}

/* cie-v6-binary.md 38: "supply": The Tree of Life's cutting tools, bars of soap or cloth bolts (story_c4.inc
   C4_SUPPLY_*) changed by `delta` (the walk's roll), kept within 0..6 (99 with Up to 99 Cutting Tools/Soap/Cloth;
   soap always 99) and never below 0.  Nothing in another game, and nothing before the supply's own puzzle is solved
   (the event's words are then story only).  The change has one line in the event's log entry. */
static void cg_supply(int game, const unsigned char *e, int delta) {
    int item = c4_supply_item(cg_s(&cg_g, cg_u16(e + 12))), big, before = 0, after = 0;
    int *count;
    char line[96];
    if (game != 4 || item < 0 || delta == 0 || !cg_puzzle_solved(game, C4_SUPPLY_PUZZLES[item])) {
        return;
    }
    big = c4_supply_cap_installed();
#ifdef VVFP_TEST
    if (test_graph_supply_cap >= 0) {
        big = test_graph_supply_cap;
    }
#endif
    count = (int *)(uintptr_t)C4_SUPPLY_AT[item];
    __try {
        before = *count;
        after = c4_supply_after(before, delta, c4_supply_cap(item, big));
        *count = after;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if (after == before) {
        return;
    }
    wsprintfA(line, "  %s: %d -> %d\n", C4_SUPPLY_NAMES[item], before, after);
    if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
        lstrcatA(cg_extra_lines, line);
    }
}

#include "story_graph_village.inc"   /* cie-v6-binary.md 33-35: goods, trades, group behaviours, the village */

/* Effect `e` with its rolls (va, vb) on the village; the award's state in *award_kind / *award. */
/* The age of a new villager of age class `cls` (0 any, 1 child 1..13, 2 teen 14..17, 3 adult 18..54, 4 elder
   55..75), in the games' age units (20 a year), drawn with the game's own random routine. */
static int cg_new_villager_age(const ce_adapter *a, int cls) {
    static const int RANGE[5][2] = { { 1, 75 }, { 1, 13 }, { 14, 17 }, { 18, 54 }, { 55, 75 } };
    int lo, hi;
    if (cls < 0 || cls > 4) {
        cls = 0;
    }
    lo = RANGE[cls][0];
    hi = RANGE[cls][1];
    return 20 * (lo + ce_random_below(a, hi - lo + 1));
}

/* Effect 27: a new villager through the game's own creator (a->spawn: its room check, its free record, its own
   name, likes, dislikes and skills), told as an arrival (ce_tell_arrival: the logs, Cause of Death, Last Names);
   a duplicate takes the cast villager's sex, head and body.  No room (the mode's cap, a full record table): nothing
   and no error -- the effect is skipped. */
static void cg_new_villager(const ce_adapter *a, int game, const unsigned char *e, ce_result *r) {
    ce_spawn s;
    int k, index;
    (void)r;
    if (a == NULL || !(a->caps & CAP_SPAWN) || a->spawn == NULL) {
        return;
    }
    memset(&s, 0, sizeof s);
    s.count = 1;
    s.head = s.body = CE_KEEP;
    s.mask = s.faction = s.health = CE_KEEP;
    for (k = 0; k < CE_SKILLS; ++k) {
        s.skills[k] = CE_KEEP;
    }
    for (k = 0; k < CE_SPAWN_PREFS; ++k) {
        s.likes[k] = s.dislikes[k] = -1;
    }
    s.father_record = s.mother_record = -1;
    s.father_head = s.father_body = s.mother_head = s.mother_body = CE_KEEP;
    {
        int sex = (int)cg_u32(e + 8);  /* b: 0 random (the game's roll), 1 male, 2 female */
        s.sex = sex == 1 ? STORY_SEX_MALE : sex == 2 ? STORY_SEX_FEMALE
                                                     : (ce_random_below(a, 2) ? STORY_SEX_FEMALE : STORY_SEX_MALE);
    }
    if (e[1] != CG_ROLE_ALIAS_ALL) {
        int from = -1;
        const unsigned char *src = cg_target(a, e[1], &from);
        if (src == NULL) {
            return;                    /* the villager to duplicate is gone: nothing */
        }
        s.sex = ce_sex(a, src);
        s.head = *(const int *)(src + a->off_head);
        s.body = *(const int *)(src + a->off_body);
    }
    s.father_kind = s.mother_kind = CE_PARENT_KEEP;
    if (e[2] & CG_NEW_CHILD_OF_NEWEST) {
        /* A family arriving together (the owner, 2026-11-15): the two newest villagers are its parents, recorded as
           a birth records them (the Custom Island Event's own parents' write): a woman the mother, a man the
           father; two of one sex: the first made the father's place. */
        for (k = 1; k >= 0; --k) {
            unsigned char *p = cg_newest[k] >= 0 ? ce_same_villager(a, cg_newest[k], cg_newest_id[k]) : NULL;
            int female, as_mother;
            if (p == NULL) {
                continue;
            }
            female = ce_sex(a, p) == STORY_SEX_FEMALE;
            as_mother = female ? s.mother_kind == CE_PARENT_KEEP : s.father_kind != CE_PARENT_KEEP;
            if (as_mother && s.mother_kind == CE_PARENT_KEEP) {
                ce_copy_name(s.mother_name, CE_NAME_BYTES, p + a->off_name, a->name_bytes);
                s.mother_head = *(const int *)(p + a->off_head);
                s.mother_body = *(const int *)(p + a->off_body);
                s.mother_kind = CE_PARENT_VILLAGER;
                s.mother_record = cg_newest[k];
            } else if (s.father_kind == CE_PARENT_KEEP) {
                ce_copy_name(s.father_name, CE_NAME_BYTES, p + a->off_name, a->name_bytes);
                s.father_head = *(const int *)(p + a->off_head);
                s.father_body = *(const int *)(p + a->off_body);
                s.father_kind = CE_PARENT_VILLAGER;
                s.father_record = cg_newest[k];
            }
        }
        s.parents_set = s.father_kind != CE_PARENT_KEEP || s.mother_kind != CE_PARENT_KEEP;
    }
    s.age = cg_new_villager_age(a, (int)cg_u32(e + 4));
    index = a->spawn(&s);
    cg_count_add(1, index >= 0);       /* 33: the villagers actually made */
    if (index < 0) {
        return;                        /* no room: skipped, no error */
    }
    ce_tell_arrival(game, index, &s);
    if ((a->caps & CAP_PARENTS) && s.parents_set && a->parents_supported()) {
        ce_change parents;
        ce_spawn_parents(&s, &parents);
        (void)a->set_parents(index, &parents);
    }
    if (!(e[2] & CG_NEW_CHILD_OF_NEWEST)) {
        cg_newest_push(a, index);      /* 253 from here on (the one before it 252) */
    }
}


/* The companions that key a villager by an identity holding the name (native/shared/villager_rekey.h): each one
   loaded is handed the renamed records and the names they had, as "VVFP Last Names.dll" hands its renames. */
static const char *const CG_RENAME_OWNERS[] = {
    "VVFP Head Look.dll", "VVFP Original Look.dll", "VVFP Origins Icons.dll", "VVFP VV1 Origins Icons.dll",
    "VVFP VV2 Origins Icons.dll", "VVFP VV4 Origins Icons.dll", "VVFP Cause of Death.dll", "VVFP Faith Loss.dll",
    "VVFP Last Names.dll", "VVFP VV1 Parentage.dll", "VVFP Parentage Export.dll", "VVFP Population Export.dll",
    "VVFP Gender Presentation.dll",
};

int __stdcall VvfpVillagersRenamed(int game, int slot, int count, const void *const *records,
                                   const char *const *old_names);

static void cg_tell_renamed(int game, int count, const void *const *records, const char *const *old_names) {
    int slot = story_current_slot(game);
    size_t k;
    if (slot <= 0 || count <= 0) {
        return;
    }
    (void)VvfpVillagersRenamed(game, slot, count, records, old_names);   /* this DLL's own custom titles */
    for (k = 0; k < sizeof CG_RENAME_OWNERS / sizeof CG_RENAME_OWNERS[0]; ++k) {
        HMODULE owner = GetModuleHandleA(CG_RENAME_OWNERS[k]);
        vv_rekey_export_fn renamed = owner != NULL
            ? (vv_rekey_export_fn)(void *)GetProcAddress(owner, "VvfpVillagersRenamed") : NULL;
        if (renamed != NULL) {
            (void)renamed(game, slot, count, records, old_names);
        }
    }
}

/* Each game's own copy routine (the twins' and triplets'): the new record index, -1 none.  The adapter's room
   predicate is asked first (the routines' own record search has no bound of its own in A New Home and The Lost
   Children). */
static int cg_copy_villager(const ce_adapter *a, int game, int index) {
    unsigned char *src = a->record(index);
    int copy = -1;
    if (src == NULL || a->room == NULL || !a->room()) {
        return -1;
    }
    switch (game) {
    case 1: copy = TC1(0x43C840u, VV1_ARRAY(), index); break;
    case 2: copy = TC1(0x44CEC0u, VV2_POOL(), index); break;
    case 3: copy = TC1(0x45F2D0u, C3_VILLAGE, (int)(uintptr_t)src); break;
    case 4: copy = TC1(0x466310u, C4_MANAGER, (int)(uintptr_t)src); break;
    case 5: copy = TC1(0x46FD70u, C5_MANAGER, (int)(uintptr_t)src); break;
    default: break;
    }
    return copy >= 0 && copy < a->record_count ? copy : -1;
}

/* A first name from the game's own list (either sex, the game's random routine), never the one the record has; with
   `keep_last`, the record's last name kept after it.  1 when the record holds the new name. */
/* Effect 33's fixed name (the owner, 2026-11-15: "CHANGE NAME villager TO Lani"): 1 to 31 characters of letters,
   spaces, apostrophes, hyphens and full stops, starting with a letter; "" (an empty string) counts as none. */
static int cg_fixed_name_ok(const char *name) {
    int k;
    if (name[0] == '\0') {
        return 1;
    }
    if (!((name[0] >= 'A' && name[0] <= 'Z') || (name[0] >= 'a' && name[0] <= 'z'))) {
        return 0;
    }
    for (k = 0; name[k] != '\0'; ++k) {
        char c = name[k];
        if (k >= 31 || !((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == ' ' || c == '\'' || c == '-'
                         || c == '.')) {
            return 0;
        }
    }
    return name[k - 1] != ' ';
}

/* Effect 33 with a fixed name: one word is a first name (the villager's last name kept, as the random pick keeps it),
   a name with a space the whole name; past the room the game holds, the first name alone, then cut to the room.
   Nothing when the villager already has that name.  1 when the name was written. */
static int cg_rename_fixed(const ce_adapter *a, unsigned char *record, const char *fixed) {
    char now[64], full[96];
    const char *last = NULL;
    int n_last = 0, k;
    lstrcpynA(now, (const char *)record + a->off_name, (int)sizeof now);
    for (k = 0; fixed[k] != '\0' && fixed[k] != ' '; ++k) {
    }
    if (fixed[k] == '\0') {
        n_last = cg_last_of(now, &last);
    }
    if (n_last > 0 && lstrlenA(fixed) + 1 + n_last < (int)sizeof full) {
        wsprintfA(full, "%s %.*s", fixed, n_last, last);
    } else {
        lstrcpynA(full, fixed, (int)sizeof full);
    }
    if (lstrlenA(full) > a->name_room) {
        lstrcpynA(full, fixed, (int)sizeof full);
        if (lstrlenA(full) > a->name_room) {
            full[a->name_room > 0 ? a->name_room : 0] = '\0';
        }
    }
    if (full[0] == '\0' || lstrcmpiA(full, now) == 0) {
        return 0;
    }
    return ce_write_name(record + a->off_name, a->name_bytes, full);
}

static int cg_rename_from_list(const ce_adapter *a, int game, unsigned char *record, int keep_last) {
    char now[64], pick[64], full[96];
    const char *last = NULL, *list;
    int tries, n_last = 0;
    lstrcpynA(now, (const char *)record + a->off_name, (int)sizeof now);
    if (keep_last) {
        n_last = cg_last_of(now, &last);
    }
    for (tries = 0; tries < 8; ++tries) {
        int count = 0, k, want, len = 0;
        const char *p;
        list = cg_names_list(game, ce_random_below(a, 2));
        for (p = list; *p != '\0'; ++p) {
            count += *p == ',';
        }
        if (count == 0) {
            return 0;
        }
        want = ce_random_below(a, count);
        for (p = list, k = 0; *p != '\0' && k < want; ++p) {
            k += *p == ',';
        }
        while (p[len] != '\0' && p[len] != ',' && len + 1 < (int)sizeof pick) {
            pick[len] = p[len];
            ++len;
        }
        pick[len] = '\0';
        if (n_last > 0 && len + 1 + n_last < (int)sizeof full) {
            wsprintfA(full, "%s %.*s", pick, n_last, last);
        } else {
            lstrcpynA(full, pick, (int)sizeof full);
        }
        if (lstrlenA(full) > a->name_room) {
            lstrcpynA(full, pick, (int)sizeof full);   /* the room the game holds: the first name alone */
        }
        if (lstrcmpiA(full, now) != 0) {
            return ce_write_name(record + a->off_name, a->name_bytes, full);
        }
    }
    return 0;
}

/* A conception the event made whose carrier is not a woman, or in which the partner carries (flags bit 3, the
   player's setting drew it): one line in the Island Events log entry (the comparison of the records says only
   "Nursing no -> yes" and the expected father), as the Births and Conceptions log's Conception names the carrier as
   the Mother and the partner as the Father (the owner, 2026-11-17: the logs keep track of males carrying babies):
       "  Tane, who is male, carries the babies (the partner carries instead of Mere)."
   `partner` the partner's record index (-1 none); `nursing` 1 for effect 29 (born at once: "nurses the babies"). */
static void cg_carrier_line(const ce_adapter *a, const unsigned char *record, int partner, int swapped, int nursing) {
    char who[CE_NAME_BYTES], mate[CE_NAME_BYTES], what[CE_NAME_BYTES + 96];
    const unsigned char *other = partner >= 0 ? a->record(partner) : NULL;
    const char *verb = nursing ? "nurses" : "carries";
    int male = ce_sex(a, record) != STORY_SEX_FEMALE;
    if (!male && !swapped) {
        return;
    }
    ce_copy_name(who, CE_NAME_BYTES, record + a->off_name, a->name_bytes);
    mate[0] = '\0';
    if (other != NULL) {
        ce_copy_name(mate, CE_NAME_BYTES, other + a->off_name, a->name_bytes);
    }
    if (swapped && mate[0] != '\0') {
        wsprintfA(what, "%s %s the babies (the partner carries instead of %s).", male ? ", who is male," : "", verb,
                  mate);
    } else {
        wsprintfA(what, "%s %s the babies.", male ? ", who is male," : "", verb);
    }
    cg_extra_add(who, what);
}

/* Effect 34: the age (the game's age units, 20 a year) set or moved, with the processed age (the catch-up's cursor,
   ce_birth_layout's second field) moved with it, so the catch-up neither replays the years nor makes them up; a
   carrier's conception mark moves with it too (the delivery stays as far off).  Never below 0; A New Home's Golden
   Child stays five; a carrier is never made a child (nothing then). */
static void cg_change_age(const ce_adapter *a, int game, const unsigned char *e, unsigned char *record) {
    static const unsigned int PROCESSED[6] = { 0, 0x34Cu, 0x534u, 0xE74u, 0x1C3Cu, 0x1C3Cu };
    static const int SET[6][2] = { { 1, 13 }, { 14, 17 }, { 18, 18 }, { 20, 49 }, { 50, 50 }, { 55, 75 } };
    int age = ce_age(a, record), target, years, delta, carrying;
    int *processed, *nursing;
    if (game < 1 || game > 5 || (game == 1 && ce_role(a, record, NULL) == STORY_KIND_GOLDEN_CHILD)) {
        return;
    }
    if (e[2] == CG_AGE_ADD) {
        int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
        years = lo + (hi > lo ? ce_random_below(a, hi - lo + 1) : 0);
        target = age + 20 * years;
    } else {
        years = SET[e[2]][0] + (SET[e[2]][1] > SET[e[2]][0] ? ce_random_below(a, SET[e[2]][1] - SET[e[2]][0] + 1) : 0);
        target = 20 * years;
    }
    if (target < 0) {
        target = 0;
    }
    {
        /* the cap (the last H, years; 0 none): never past it -- one already older stays as old */
        int cap = (int)cg_u16(e + 14) * 20;
        if (cap > 0 && target > cap) {
            target = age > cap ? age : cap;
        }
    }
    carrying = *(const int *)(record + a->off_pregnant) != 0;
    if (carrying && target < 14 * 20) {
        return;                        /* a carrier is never made a child */
    }
    delta = target - age;
    processed = (int *)(record + PROCESSED[game]);
    nursing = (int *)(record + a->off_pregnant);
    *(int *)(record + a->off_age) = target;
    *processed += delta;
    if (*processed < 0) {
        *processed = 0;
    }
    if (carrying) {
        *nursing += delta;             /* the conception mark moves with the processed age */
        if (*nursing <= 0) {
            *nursing = 1;
        }
    }
}

/* Effects 28-34 (the life effects): pregnant, nursing, clone, mind swap, lost name, new name, age. */
static void cg_life_effect(const ce_adapter *a, int game, const unsigned char *e, ce_result *r) {
    int index = -1, k;
    unsigned char *record = cg_target(a, e[1], &index);
    if (record == NULL) {
        return;                        /* gone since the event began (or never made): nothing */
    }
    switch (e[0]) {
    case CGE_PREGNANT: case CGE_NURSING: {
        int partner = -1, early = 0, other = (int)cg_u32(e + 4), litter = 1;
        /* the partner carries (any birth sex): decided at the cast, the roles already swapped
           (cg_partner_carry_decide), so `record` is the partner who carries and `other` the villager the event named
           as the carrier */
        int resolved = cg_resolve_role((int)e[1]);   /* an alias: its member drawn */
        int swapped_role = resolved >= 0 && resolved < 32 && ((cg.carry_swapped >> resolved) & 1u);
        int partner_carries = (e[2] & CG_FX_PARTNER_MAY_CARRY) && swapped_role;
        /* Codex on #814: the swap holds for the whole run, so another outcome's nursing baby for that role (a
           foundling the couple takes in: b247, b356) goes to the villager the page names, whatever their birth sex,
           as the owner's rules let a father care for a baby; an unflagged pregnancy keeps the born-female rule. */
        int swapped_nursing = e[0] == CGE_NURSING && swapped_role;
        /* #784's log: the conception's record and the carrier line say the partner carries (the cast's swap) */
        int swapped = partner_carries || swapped_nursing;
        if (!(a->caps & CAP_PREGNANT) || a->conceive == NULL || ce_age(a, record) < 18 * 20
            || *(const int *)(record + a->off_pregnant) != 0
            || (!(e[2] & CG_FX_ANY_BIRTH_SEX) && !partner_carries && !swapped_nursing
                && !cg_born_female(game, record, index))) {
            return;                    /* not a carrier these events may have, or expecting already: nothing */
        }
        if (other != 0xFF) {
            int at = -1;
            unsigned char *mate = cg_target(a, other, &at);
            if (mate != NULL) {
                partner = at;
            }
        }
        {
            unsigned int kind = e[2] & (CG_FX_LITTER_ROLL | CG_FX_LITTER_TWINS);
            if (kind == (CG_FX_LITTER_ROLL | CG_FX_LITTER_TWINS)) {
                litter = 3;
            } else if (kind == CG_FX_LITTER_TWINS) {
                litter = 2;
            } else if (kind == CG_FX_LITTER_ROLL && ce_random_below(a, 100) < 7) {
                litter = ce_random_below(a, 100) < 25 ? 3 : 2;   /* the stock rolls, the tech gate left out */
            }
        }
        {
            int babies;
            story_partner_carries = swapped;   /* the conception's record says the partner carries */
            babies = a->conceive(index, litter, partner, r);
            story_partner_carries = 0;
            cg_count_add(0, babies);   /* 33: the babies actually on their way */
            if (babies <= 0) {
                return;                /* no room (the game's own predicate): nothing */
            }
        }
        cg_carrier_line(a, record, partner, swapped, e[0] == CGE_NURSING);
#ifdef VVFP_TEST
        if (test_graph_no_deliver) {
            return;                    /* the test build: the game's birth left out (the emulator has no sound) */
        }
#endif
        if (e[0] == CGE_NURSING && a->deliver != NULL && *(const int *)(record + a->off_pregnant) != 0) {
            (void)a->deliver(index, &early);   /* born at once: nursing a newborn (the deliver_early path) */
        }
        return;
    }
    case CGE_CLONE: {
        /* The first value: how many copies, 1 or 2 (0 = 1; the owner, 2026-11-15: "up to TWO clones", as the stock
           events make), each by the same routine with its own room check; only one fits: one. */
        int copy, made, want = (int)cg_u32(e + 4) == 2 ? 2 : 1, first_copy = -1;
        if (game == 5 && cg_heathen(game, record)) {
            return;                    /* New Believers' Heathens are never copied */
        }
        for (made = 0; made < want; ++made) {
            int tries;
            copy = cg_copy_villager(a, game, index);
            cg_count_add(1, copy >= 0);   /* 33: the copies actually made */
            if (copy < 0) {
                return;                /* no room: nothing more */
            }
            /* The copy routine rolls the game's own new name (A New Home 0x43B950, The Lost Children 0x44B710, the
               later games their name rolls); the owner: always a name of its own -- not the villager's, not the
               other copy's -- so one that came out the same is drawn again from the game's own list. */
            for (tries = 0; tries < 8; ++tries) {
                const char *name = (const char *)a->record(copy) + a->off_name;
                if (lstrcmpiA(name, (const char *)a->record(index) + a->off_name) != 0   /* read again after the copy */
                    && (first_copy < 0 || lstrcmpiA(name, (const char *)a->record(first_copy) + a->off_name) != 0)) {
                    break;
                }
                cg_rename_from_list(a, game, a->record(copy), 0);
            }
            ce_tell_arrival(game, copy, NULL);
            cg_newest_push(a, copy);
            first_copy = copy;
        }
        return;
    }
    case CGE_SUPPLY:
        if (c4_supply_item(cg_s(&cg_g, cg_u16(e + 12))) >= 0) {
            cg_supply(game, e, va);        /* 32: The Tree of Life's three supplies, as PR #806 made them */
        } else {
            cg_supply_any(a, game, cg_s(&cg_g, cg_u16(e + 12)), va);   /* 33 */
        }
        return;
    case CGE_TRADE:
        cg_trade(a, game, cg_s(&cg_g, cg_u16(e + 12)), (int)cg_u32(e + 4), (int)cg_u32(e + 8));
        return;
    case CGE_VILLAGE:
        cg_village_fx(a, game, cg_s(&cg_g, cg_u16(e + 12)), va);
        return;
    case CGE_GROUP:
        if (e[1] == CG_ROLE_ALIAS_ALL) {
            cg_group_fx(a, game, cg_s(&cg_g, cg_u16(e + 12)), -1, (int)cg_u32(e + 4), r);
        } else {
            role = cg_resolve_role(e[1]);
            if (role >= 0 && cg_villager(a, role) != NULL) {
                cg_group_fx(a, game, cg_s(&cg_g, cg_u16(e + 12)), cg.record[role], 0, r);
            }
        }
        return;
    case CGE_BODY_SWAP: {
        int orole = cg_resolve_role((int)cg_u32(e + 4));
        unsigned char *other = orole >= 0 ? cg_villager(a, orole) : NULL;
        static char names[2][64];
        const void *recs[2];
        const char *olds[2];
        unsigned char tmp[64];
        if (other == NULL || other == record || a->name_bytes > (int)sizeof tmp) {
            return;
        }
        lstrcpynA(names[0], (const char *)record + a->off_name, (int)sizeof names[0]);
        lstrcpynA(names[1], (const char *)other + a->off_name, (int)sizeof names[1]);
        memcpy(tmp, record + a->off_name, (size_t)a->name_bytes);
        memcpy(record + a->off_name, other + a->off_name, (size_t)a->name_bytes);
        memcpy(other + a->off_name, tmp, (size_t)a->name_bytes);
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            unsigned int *x = (unsigned int *)(record + a->off_skills + 4u * (unsigned int)k);
            unsigned int *y = (unsigned int *)(other + a->off_skills + 4u * (unsigned int)k);
            unsigned int t = *x;
            *x = *y;
            *y = t;
        }
        for (k = 0; k < a->pref_slots; ++k) {
            int *lx = (int *)(record + a->off_likes) + k, *ly = (int *)(other + a->off_likes) + k;
            int *dx = (int *)(record + a->off_dislikes) + k, *dy = (int *)(other + a->off_dislikes) + k;
            int t = *lx;
            *lx = *ly;
            *ly = t;
            t = *dx;
            *dx = *dy;
            *dy = t;
        }
        recs[0] = record;
        recs[1] = other;
        olds[0] = names[0];
        olds[1] = names[1];
        cg_tell_renamed(game, 2, recs, olds);
        cg_renamed_record(a, record, names[0]);
        cg_renamed_record(a, other, names[1]);
        cg_log_name_change(a, game, record, names[0]);
        cg_log_name_change(a, game, other, names[1]);
        return;
    }
    case CGE_CHANGE_NAME: {
        static char was[64];
        const void *recs[1];
        const char *olds[1];
        unsigned int fixed = cg_u16(e + 12);
        lstrcpynA(was, (const char *)record + a->off_name, (int)sizeof was);
        if (fixed != CG_NONE && cg_s(&cg_g, fixed)[0] != '\0' ? !cg_rename_fixed(a, record, cg_s(&cg_g, fixed))
                                                              : !cg_rename_from_list(a, game, record, 1)) {
            return;
        }
        recs[0] = record;
        olds[0] = was;
        cg_tell_renamed(game, 1, recs, olds);
        cg_renamed_record(a, record, was);
        cg_log_name_change(a, game, record, was);
        ce_copy_name(cg_renamed_now, CG_NAME_BYTES, record + a->off_name, a->name_bytes);   /* (renamed) */
        return;
    }
    case CGE_CHANGE_AGE:
        cg_change_age(a, game, e, record);
        return;
    case CGE_LOSE_NAME: {
        static char was[64];
        const void *recs[1];
        const char *olds[1];
        lstrcpynA(was, (const char *)record + a->off_name, (int)sizeof was);
        if (!ce_write_name(record + a->off_name, a->name_bytes, "?")) {
            return;
        }
        recs[0] = record;
        olds[0] = was;
        cg_tell_renamed(game, 1, recs, olds);
        cg_renamed_record(a, record, was);
        cg_log_name_change(a, game, record, was);
        return;
    }
    default:
        return;
    }
}

/* A villager's highest skill (the game's own fields; the first on a tie), -1 none. */
static int cg_best_skill(const ce_adapter *a, const unsigned char *record) {
    int k, best = -1, best_value = -1;
    for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
        int v = a->skills_float ? (int)*(const float *)(record + a->off_skills + 4u * (unsigned int)k)
                                : *(const int *)(record + a->off_skills + 4u * (unsigned int)k);
        if (v > best_value) {
            best = k;
            best_value = v;
        }
    }
    return best;
}

static int sc_sick(int game, const unsigned char *r);   /* story_collection.inc */

/* The illness cured: each game's own sick field (story_c1.inc .. story_c5.inc's sicken) cleared. */
static void cg_cure(int game, unsigned char *record) {
    switch (game) {
    case 1: *(int *)(record + 0x354) = 0; break;
    case 2: *(int *)(record + 0x53C) = 0; break;
    case 3: record[0xE89] = 0; break;
    case 4: case 5: record[0x1C48] = 0; break;
    default: break;
    }
}

static void cg_gone_role(int role) {
    if (role >= 0 && role < CG_MAX_ROLES) {
        cg.gone |= 1u << role;
    }
}

static int st_was_finished(int game, int k);   /* story_structures.inc */

/* 36: every structure the effect's list names that this village had finished and is damaged now, left one step
   from done (sd_repair: the game's own construction finishes it). */
static void cg_repair(const ce_adapter *a, int game, const unsigned char *e) {
    const char *list = cg_s(&cg_g, cg_u16(e + 12));
    char line[160];
    int k;
    (void)a;
    for (k = 0; k < sd_structures(game) && k < SD_MAX_STRUCTURES; ++k) {
        if (cg_structure_finished(game, k) || !st_was_finished(game, k) || !cg_structure_listed(game, list, k)) {
            continue;
        }
#ifdef VVFP_TEST
        if (test_graph_structures >= 0) {
            test_graph_damaged[k] = -1;   /* repaired */
        } else
#endif
        {
            __try {
                sd_repair(game, k);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
        wsprintfA(line, "  Repaired: %s (the builders finish it)\n", sd_name(game, k));
        if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
            lstrcatA(cg_extra_lines, line);
        }
    }
}

static void cg_effect_on(const ce_adapter *a, int game, const unsigned char *e, int va, int vb, ce_result *r,
                         int role, unsigned char *record, int index, const char *name);

/* A group effect (role byte 254): every living, listed villager the selector takes (New Believers: believers only;
   never The Secret City's stand-in; a harmful effect never a protected or never-harmed villager), each changed as
   one cast villager would be, with the same rolls; N random ones drawn by the game's own random routine. */
static void cg_group_effect(const ce_adapter *a, int game, const unsigned char *e, int va, int vb, ce_result *r) {
    static int pick[CE_MAX_RECORDS];
    int n = 0, i, want, harmful = cg_effect_harmful(a, game, e);
    const char *skill = e[3] == CG_GROUP_SKILL ? cg_s(&cg_g, cg_u16(e + 14)) : NULL;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        unsigned char *rec = a->record(i);
        if (rec == NULL || !a->listed(rec) || (game == 3 && rec[0xE94] != 0) || cg_heathen(game, rec)) {
            continue;
        }
        if (harmful && (cg_protected(a, game, rec) || cg_never_harmed(game, rec))) {
            continue;
        }
        if (skill != NULL && (!cg_skills_known(a, skill) || cg_skill_value(a, rec, skill) < CG_GROUP_SKILL_MIN)) {
            continue;
        }
        {
            int years = ce_age(a, rec) / 20;
            if ((e[3] == CG_GROUP_ELDERS && years < 55) || (e[3] == CG_GROUP_CHILDREN && years >= 14)
                || (e[3] == CG_GROUP_TEENS && (years < 14 || years > 17)) || (e[3] == CG_GROUP_ADULTS && years < 18)) {
                continue;
            }
        }
        pick[n++] = i;
    }
    want = e[3] == CG_GROUP_RANDOM ? (int)cg_u16(e + 14) : n;
    if (want > n) {
        want = n;
    }
    if (e[3] == CG_GROUP_RANDOM) {
        for (i = 0; i < want; ++i) {   /* the first `want` drawn without repeats */
            int j = i + ce_random_below(a, n - i), t = pick[i];
            pick[i] = pick[j];
            pick[j] = t;
        }
    }
    for (i = 0; i < want; ++i) {
        unsigned char *rec = a->record(pick[i]);
        char who[CE_NAME_BYTES];
        if (rec == NULL || !a->listed(rec)) {
            continue;
        }
        ce_copy_name(who, CE_NAME_BYTES, rec + a->off_name, a->name_bytes);
        if (e[0] == CGE_PREF && (e[2] & CG_PREF_RANDOM) && (e[2] & CG_PREF_REMOVE)) {
            /* a random like or dislike each member holds, taken away (none held: nothing for them) */
            cg_effect_on(a, game, e, cg_held_preference_of(a, rec, (e[2] & 4u) != 0), vb, r, -1, rec, pick[i], who);
            continue;
        }
        if (e[0] == CGE_PREF && (e[2] & CG_PREF_RANDOM)) {
            /* a random like or dislike each: the roll, then the word chosen from this villager */
            int k = ce_random_below(a, a->pref_count);
            cg_effect_on(a, game, e, cg_random_preference_of(a, rec, k), vb, r, -1, rec, pick[i], who);
            continue;
        }
        if (e[0] == CGE_APPEARANCE) {
            /* a new look each: a random head / body row drawn for every member (the game's random routine) */
            int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
            int ha = lo == CG_LOOK_RANDOM ? ce_random_below(a, a->head_count - 1) : va;
            int hb = hi == CG_LOOK_RANDOM ? ce_random_below(a, a->body_count - 1) : vb;
            cg_effect_on(a, game, e, ha, hb, r, -1, rec, pick[i], who);
            continue;
        }
        cg_effect_on(a, game, e, va, vb, r, -1, rec, pick[i], who);
    }
}

/* One effect on one villager (`record`, record `index`, `name` for the log): a cast role's (`role`), or a group's
   member or a villager this event made (`role` -1). */
static void cg_effect_on(const ce_adapter *a, int game, const unsigned char *e, int va, int vb, ce_result *r,
                         int role, unsigned char *record, int index, const char *name) {
    ce_result one;
    ce_change *c;
    if (cg_g.version >= 6 && record != NULL && cg_heathen(game, record) && !cg_heathen_effect_ok(e)) {
        /* A Heathen however reached (an alias or "other" role standing for a heathen_ok one): vanilla's own list
           only, as the load checks a Heathen's own role (Codex, #771). */
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    if ((role < 0 || (cg_role_at(&cg_g, role)[1] & CG_ROLE_PROTECTED)) && cg_effect_harmful(a, game, e)
        && cg_protected(a, game, record)) {
        /* The hard guard's last word (the walk's guard took the branch out unless they became protected since):
           a protected villager is never harmed. */
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    if (cg_effect_harmful(a, game, e) && cg_never_harmed(game, record)) {
        ce_refuse(r, CE_WHY_OTHER);    /* never harmed, whatever the role allows (cg_never_harmed) */
        return;
    }
    if (e[0] == CGE_KILL || e[0] == CGE_VANISH || e[0] == CGE_DIE_UNRECOVERED) {
        if (!(a->caps & (e[0] == CGE_KILL ? CAP_KILL : CAP_VANISH))) {
            ce_refuse(r, CE_WHY_OTHER);
        } else if (e[0] == CGE_KILL && a->kill(index)) {
            ++r->died;
            cg_tell_killed(game, index, cg_s(&cg_g, cg_u16(e + 12)));
        } else if (e[0] == CGE_VANISH && a->vanish(index)) {
            ++r->vanished;
            cg_tell_vanished(game, index);
        } else if (e[0] == CGE_DIE_UNRECOVERED && a->vanish(index)) {
            /* 22: the stock disappearance (no body, no grave), told as a death; always "Unknown causes". */
            ++r->died;
            cg_tell_died_unrecovered(game, index);
            cg_extra_add(name, " died (Unknown causes); the body was not recovered.");
        } else {
            ce_refuse_as(r, CE_WHY_OTHER);
        }
        cg_gone_role(role);         /* gone for good: nothing more is done to them (their name stays) */
        return;
    }
    if (e[0] == CGE_BIRTH_THEN_DIE) {
        /* 23: the game's own birth now (the adapter's deliver: babies born early get the age the nursing reached and
           a health deficit), then the parent's death with a grave, as kill.  A parent no longer nursing just dies
           (the children are villagers already); a birth the game would not make is a refusal and nobody dies. */
        const char *cause = cg_s(&cg_g, cg_u16(e + 12));
        int babies = 0, early = 0;
        char what[160];
        if (!(a->caps & CAP_KILL) || a->deliver == NULL) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        if (*(const int *)(record + a->off_pregnant) != 0) {
            babies = a->deliver(index, &early);
            if (babies < 0) {
                ce_refuse_as(r, CE_WHY_OTHER);
                return;
            }
            cg_tell_delivered(game, index);
        }
        if (cg_health_now(game, record) > 0) {
            if (!a->kill(index)) {
                ce_refuse_as(r, CE_WHY_OTHER);
                return;
            }
            cg_tell_killed(game, index, cause);
        }
        ++r->died;
        if (babies > 0) {
            wsprintfA(what, "'s %s %s; %s died.", babies > 1 ? "babies were" : "baby was",
                      early ? "born early" : "born", name);
        } else {
            lstrcpyA(what, " died.");
        }
        cg_extra_add(name, what);
        cg_gone_role(role);
        return;
    }
    if (e[0] == CGE_DELIVER_EARLY) {
        /* 30: the game's own birth now, as birth_then_die's (babies born early get the age the nursing reached and
           the health deficit; each loses the roll va more, -99..-1, or nothing), and the parent LIVES.  A parent no
           longer nursing, or a birth the game would not make, is a refusal and nothing changes. */
        int babies, early = 0;
        char what[96];
        if (!(a->caps & CAP_CANCEL) || a->deliver == NULL || *(const int *)(record + a->off_pregnant) == 0) {
            ce_refuse_as(r, CE_WHY_NOT_EXPECTING);
            return;
        }
        ce_birth_extra = va < 0 ? -va : 0;
        babies = a->deliver(index, &early);
        ce_birth_extra = 0;
        if (babies < 0) {
            ce_refuse_as(r, CE_WHY_OTHER);
            return;
        }
        cg_tell_delivered(game, index);
        if (babies > 0) {
            wsprintfA(what, "'s %s %s.", babies > 1 ? "babies were" : "baby was", early ? "born early" : "born");
            cg_extra_add(name, what);
        }
        return;
    }
    if (e[0] == CGE_SEX_CHANGE) {
        /* 29: the game's own sex field, the other value; nothing else (the looks' rows, the parents recorded on
           anyone's record, the names) changes.  The run keeps the villager by their new identity. */
        int why = cg_sex_change_refusal(a, game, record);
        int female = ce_sex(a, record) == STORY_SEX_FEMALE;
        if (why >= 0 || vv_sex_change_apply(game, record, index) != VV_SEX_OK) {
            ce_refuse(r, why >= 0 ? why : CE_WHY_OTHER);
            return;
        }
        if (role >= 0) {
            cg.identity[role] = ce_identity(a, record);
            /* 35: the role's words follow the new sex on the pages still to come (pages are laid out with the
               longer word, so nothing moves) */
            cg_late_note(role);
            cg.female[role] = cg_word_female(a, game, role, record, index);
        }
        cg_extra_add(name, female ? "'s sex is now male." : "'s sex is now female.");
        return;
    }
    if (e[0] == CGE_PRESENTATION) {
        /* 31: the gender presentation, through Gender Presentation's own file (nothing in the save is written) */
        int on = (int)cg_u32(e + 4) == 1;
        if (!cg_presentation(game, record, index, on)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        if (role >= 0) {
            cg_late_note(role);
            cg.female[role] = cg_word_female(a, game, role, record, index);   /* 35: a carrier's words follow it */
        }
        cg_extra_add(name, on ? " is now drawn with the other sex's look." : " is drawn with their own look again.");
        return;
    }
    if (e[0] == CGE_OLD_LOOK) {
        /* 27: the old head look, through Head Look's own file (nothing in the save is written) */
        if (!cg_old_look(game, record, index)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        cg_extra_add(name, "'s head look is now Old.");
        return;
    }
    if (e[0] == CGE_FAITH || e[0] == CGE_JOIN || e[0] == CGE_APOSTASY) {
        /* New Believers' Faith through the game's own routines (never the fields): they convert as the game
           converts, with its message, role, counters and puzzle check (cie-v6-binary.md 33c). */
        int was;
        if (game != 5) {
            return;                    /* only New Believers has Faith: nothing */
        }
        was = cg_heathen(game, record);
        if ((e[0] == CGE_JOIN && !was) || (e[0] == CGE_APOSTASY && was)) {
            return;                    /* a believer already / a Heathen already: nothing */
        }
        __try {
            if (e[0] == CGE_FAITH) {
                TC1(0x468020u, record, (int)cg_u32(e + 4));
            } else if (e[0] == CGE_JOIN) {
                TC2(0x467F90u, record, 20, 1);
                TC1(0x466880u, record, 0);
            } else {
                TC2(0x467F90u, record, -10, 1);
                TC1(0x466880u, record, 1);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        if (was != cg_heathen(game, record)) {
            cg_tell_faith(game, index);
            cg_extra_add(name, was ? " joined the tribe." : " became a Heathen.");
        } else if (e[0] == CGE_FAITH) {
            cg_extra_add(name, "'s Faith grew.");
        }
        if (role >= 0) {
            cg.identity[role] = ce_identity(a, record);
        }
        return;
    }
    if (e[0] == CGE_YOUNG_LOOK) {
        /* 37: the young head look, through Head Look's own file (as old_look) */
        if (!cg_head_look(game, record, index, VVFP_HEAD_LOOK_YOUNG)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        cg_extra_add(name, "'s head look is now Young.");
        return;
    }
    if (e[0] == CGE_CURE) {
        /* 35: the illness cured -- the game's own sick field cleared (the field each game's sicken sets; the
           healers' and Full Heal's cure clears the same one); health is left as it is.  Not sick: nothing. */
        if (!(a->caps & CAP_SICK)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        if (!sc_sick(game, record)) {
            return;
        }
        cg_cure(game, record);
        cg_extra_add(name, " was cured.");
        return;
    }
    if (e[0] == CGE_BABY_LOST) {
        /* 22: the nursing parent's pregnancy ends as the Custom Island Event's "0 babies" ends it (the adapter's
           cancel); the Cause of Death companion is told first, while the record still holds the babies. */
        if (!(a->caps & CAP_CANCEL) || *(const int *)(record + a->off_pregnant) == 0) {
            ce_refuse_as(r, CE_WHY_NOT_EXPECTING);
            return;
        }
        cg_tell_baby_lost(game, index);
        if (!a->cancel(index)) {
            ce_refuse_as(r, CE_WHY_NOT_EXPECTING);
            return;
        }
        cg_extra_add(name, "'s baby was lost.");
        return;
    }
    memset(&cg_one, 0, sizeof cg_one);
    cg_one.game = game;
    cg_one.change_count = 1;
    c = &cg_one.changes[0];
    ce_change_init(c);
    c->index = index;
    c->fingerprint = ce_identity(a, record);
    switch (e[0]) {
    case CGE_STATUS:
        if (game != 5 || !(a->caps & CAP_STATUS)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        if (cg_heathen(game, record)) {
            return;                    /* a Heathen already */
        }
        c->status = 1;                 /* "Becomes a Heathen": the game's own 0x4669E0 */
        break;
    case CGE_HEALTH:
        if (a->set_health == NULL) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->health = va;
        break;
    case CGE_PREF: {
        int random = (e[2] & CG_PREF_RANDOM) != 0;
        int value = random ? va : cg_preference(a, cg_pref_word != NULL ? cg_pref_word : cg_s(&cg_g, cg_u16(e + 12)));
        int dislike = (e[2] & 4u) != 0;
        const int *list = (const int *)(record + (dislike ? a->off_dislikes : a->off_likes));
        int k, have = 0, free_slot = 0;
        if (random && (value < 0 || value >= a->pref_count)) {
            return;                    /* 24: no word left to give (or none held to take): nothing, nothing refused */
        }
        if (!(a->caps & CAP_PREFS) || value < 0) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        for (k = 0; k < a->pref_slots; ++k) {
            have |= list[k] == value;
            free_slot |= list[k] == -1;
        }
        if (e[2] & CG_PREF_REMOVE) {
            /* Taken away through the Custom Island Event's own removal (CE_PREF_REMOVE): the game's own like or
               dislike field, the slot freed.  Not held: nothing changes, nothing is refused. */
            if (have) {
                c->pref_ops[c->pref_op_count++] = CE_PREF_OP(dislike, 1, value);
            }
            break;
        }
        c->pref_ops[c->pref_op_count++] = CE_PREF_OP(!dislike, 1, value);   /* never liked and disliked at once */
        if (!have && !free_slot && a->pref_slots > 0) {
            /* A full list: the newest takes the last one's place, as the shipped event's "now dislikes running". */
            c->pref_ops[c->pref_op_count++] = CE_PREF_OP(dislike, 1, list[a->pref_slots - 1]);
        }
        c->pref_ops[c->pref_op_count++] = CE_PREF_OP(dislike, 0, value);
        break;
    }
    case CGE_SKILL: {
        int now, value;
        if (e[2] & CG_SKILL_BEST) {
            va = cg_best_skill(a, record);   /* the villager's own highest skill */
        }
        if (!(a->caps & CAP_SKILLS) || va < 0 || va >= a->skill_count) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        now = a->skills_float ? (int)*(const float *)(record + a->off_skills + 4u * (unsigned int)va)
                              : *(const int *)(record + a->off_skills + 4u * (unsigned int)va);
        value = now + vb;
        c->skills[va] = value > 100 ? 100 : (value < 0 ? 0 : value);
        break;
    }
    case CGE_SICK:
        if (!(a->caps & CAP_SICK)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->sick = 1;
        break;
    case CGE_CELEBRATE: case CGE_ACTION: case CGE_MOOD: {
        int behaviour = cg_behaviour_of(a, game, e);
        if (behaviour < 0) {
            return;                    /* an action this game does not have: nothing (rule 8) */
        }
        if (!(a->caps & CAP_BEHAVIOUR)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->behaviour = behaviour;
        break;
    }
    case CGE_HEALTH_CHANGE: {
        int value = cg_health_now(game, record) + va;
        if (a->set_health == NULL) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        c->health = value < 1 ? 1 : (value > CE_HEALTH_MAX ? CE_HEALTH_MAX : value);   /* never kills */
        break;
    }
    case CGE_SKILL_SET:
        if (e[2] & CG_SKILL_BEST) {
            va = cg_best_skill(a, record);
        }
        if (!(a->caps & CAP_SKILLS) || va < 0 || va >= a->skill_count) {
            return;                    /* a skill this game does not have: nothing (rule 8) */
        }
        c->skills[va] = vb < 0 ? 0 : (vb > 100 ? 100 : vb);
        break;
    case CGE_APPEARANCE: {
        /* 22: the rows through the Custom Island Event's own head / body write (ce_apply_fields); random: the roll,
           one up from the current row on, so never the row the villager has. */
        int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
        int head = *(const int *)(record + a->off_head), body = *(const int *)(record + a->off_body);
        if (!(a->caps & CAP_APPEARANCE)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        if (lo != CG_LOOK_KEEP && va >= 0) {
            c->head = lo == CG_LOOK_RANDOM && va >= head ? va + 1 : va;
        }
        if (hi != CG_LOOK_KEEP && vb >= 0 && !(game == 3 && ce_role(a, record, NULL) == STORY_KIND_TRIBAL_CHIEF)) {
            c->body = hi == CG_LOOK_RANDOM && vb >= body ? vb + 1 : vb;   /* the Tribal Chief keeps the robe */
        }
        if ((c->head == CE_KEEP || c->head == head) && (c->body == CE_KEEP || c->body == body)) {
            return;                    /* nothing to change (the robe kept, or the row it already has) */
        }
        if ((c->head != CE_KEEP && c->head >= a->head_count) || (c->body != CE_KEEP && c->body >= a->body_count)) {
            ce_refuse(r, CE_WHY_OTHER);   /* a row this game does not have (the patcher refuses it first) */
            return;
        }
        break;
    }
    default:
        return;
    }
    ce_apply(a, &cg_one, &one);
    cg_merge_result(r, &one);
    if (e[0] == CGE_APPEARANCE) {
        cg_extra_add(name, "'s look changed.");
    }
    if (e[0] == CGE_STATUS && cg_heathen(game, record)) {
        cg_tell_faith(game, index);
    }
    record = a->record(index);
    if (role >= 0 && record != NULL && a->listed(record)) {
        cg.identity[role] = ce_identity(a, record);   /* the same villager, with what was just changed */
    }
}

static void cg_effect(const ce_adapter *a, int game, const unsigned char *e, int va, int vb, int *award_kind,
                      int *award, ce_result *r) {
    unsigned char *record;
    int index, role;
    switch (e[0]) {
    case CGE_FOOD: case CGE_TECH:
        if (e[2] & 2u) {
            *award_kind = e[0] == CGE_FOOD ? 0 : 1;
            *award = va;               /* given by a later "pay_award" */
        } else {
            cg_amount(a, e[0] == CGE_FOOD, va, r);
        }
        return;
    case CGE_PAY:
        if (*award_kind >= 0) {
            cg_amount(a, *award_kind == 0, *award, r);
        }
        return;
    case CGE_DAMAGE:
        cg_damage(a, game, e, va);
        return;
    case CGE_REPAIR:
        cg_repair(a, game, e);
        return;
    case CGE_NEW_VILLAGER:
        cg_new_villager(a, game, e, r);
        return;
    case CGE_PREGNANT: case CGE_NURSING: case CGE_CLONE: case CGE_BODY_SWAP: case CGE_LOSE_NAME:
    case CGE_CHANGE_NAME: case CGE_CHANGE_AGE:
        cg_life_effect(a, game, e, r);
        return;
    case CGE_TRAIT:
        /* 32: the villager keeps the story trait (story_traits.inc's file follows them), whatever is ticked; the
           Island Events log says so (the comparison of the records cannot: the trait is kept beside the save). */
        index = -1;
        record = cg_target(a, e[1], &index);   /* a role, or a villager this event made */
        if (record != NULL) {
            if (rs_set_trait(game, index, cg_u32(e + 4))) {
                char who[CE_NAME_BYTES];
                ce_copy_name(who, CE_NAME_BYTES, record + a->off_name, a->name_bytes);
                cg_extra_add(who, " now has the story trait mute.");
            }
            if ((cg_u32(e + 4) & CG_TRAIT_MUTE) && cg_preference(a, CG_MUTE_WORD) >= 0) {
                /* The owner (2026-11-17): a mute villager also dislikes talking where the game has the word (The
                   Lost Children .. New Believers), through the preference effect's own write (24). */
                unsigned char pref[16];
                memset(pref, 0, sizeof pref);
                pref[0] = CGE_PREF;
                pref[1] = e[1];
                pref[2] = 4u;                  /* a dislike */
                cg_pref_word = CG_MUTE_WORD;
                cg_effect(a, game, pref, -1, 0, award_kind, award, r);
                cg_pref_word = NULL;
            }
        }
        return;
    case CGE_CELEBRATE:
        if (e[1] == CG_ROLE_ALIAS_ALL) {
            cg_celebrate_all(a, game, r);
            return;
        }
        break;
    default:
        break;
    }
    if (e[1] == CG_ROLE_GROUP) {
        cg_group_effect(a, game, e, va, vb, r);   /* every villager of the group, one by one */
        return;
    }
    if (e[1] == CG_ROLE_NEWEST || e[1] == CG_ROLE_NEWEST2) {
        char who[CE_NAME_BYTES];
        record = cg_target(a, e[1], &index);
        if (record == NULL) {
            return;                    /* not made (no room), or gone */
        }
        ce_copy_name(who, CE_NAME_BYTES, record + a->off_name, a->name_bytes);
        cg_effect_on(a, game, e, va, vb, r, -1, record, index, who);
        return;
    }
    role = cg_resolve_role(e[1]);      /* an alias: the member drawn */
    if (role < 0) {
        return;                        /* an alias with no member: nobody to change */
    }
    record = cg_villager(a, role);
    if (record == NULL) {
        /* Gone since the event began (old age, another event between its pages, or this event): that role's
           later effects are skipped -- never someone else in their record -- and the rest of the event goes on. */
        cg.gone |= 1u << role;
        return;
    }
    cg_effect_on(a, game, e, va, vb, r, role, record, cg.record[role], cg.name[role]);
}

/* ---- One history's popups, their pages, and which page makes which effect ------------------------------------

   THE EFFECTS WAIT FOR THEIR OWN PAGE (the owner, 2026-11-12).  Each node's effects are made when the page that
   shows the END of that node's text is built for the screen -- the moment the game's own plain island event
   makes its changes (as it builds its popup: ce_deliver) and the moment a question's result is built after the
   click (ce_choice_resolve) -- so the page says what has just happened: "Your villagers gain 500 food" is the
   page the award lands on, the ending's last page is the one its death or disappearance comes with.  A node with
   no text (a branch) makes its effects with the text shown just before it (or, before any, with the first).
   Each page's "N changes could not be made" lines tell of that page's own effects. */

typedef struct {
    char raw[CG_RAW_BYTES];            /* the award filled in, the names not */
    int effects;                       /* carries villager effects: two lines kept on each page for the refusals */
    int question;                      /* a question's own popup: the node, else -1 */
    int tcount;                        /* its titles: the one in force at its start (toff 0), then each titled */
    int toff[CG_TITLE_CHANGES];        /* node's, from where that node's text starts in raw */
    unsigned short ttitle[CG_TITLE_CHANGES];
} cg_popup;

static cg_popup cg_pops[CG_MAX_POPUPS];
static int cg_pop_count;
static short cg_node_pop[CG_MAX_PATH];     /* each history node: the popup its effects are made with ... */
static short cg_node_end[CG_MAX_PATH];     /* ... at the page holding this much of the popup's text */

/* The award's state before history node `upto` (the last deferred one's kind and amount, -1 none) and the index
   of that node's first effect roll. */
static int cg_award_before(const cg_history *h, int upto, int *kind, int *amount) {
    int fx = 0, i, k;
    *kind = -1;
    *amount = 0;
    for (i = 0; i < upto && i < h->nodes; ++i) {
        const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
        for (k = 0; k < cg_fx_count(n); ++k, ++fx) {
            const unsigned char *e = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k);
            if ((e[0] == CGE_FOOD || e[0] == CGE_TECH) && (e[2] & 2u)) {
                *kind = e[0] == CGE_FOOD ? 0 : 1;
                *amount = fx < CG_MAX_FX ? h->fx_a[fx] : 0;
            }
        }
    }
    return fx;
}

/* The popups of history `h` as the patcher's walk builds them (src/vv_cie_graph.py walk: a node's effects first --
   an award it defers is the (award) of its own text -- then its text, appended or new), and for each node the
   popup and the place in it its effects go with. */
static int cg_group_in_question;       /* the first popup is shown in the answered question's own popup (14) */

/* cie-v6-binary.md 25: the automatic outcome lines.  <R> the effect's role's name placeholder, <P> its his/her, <S>
   the skill's name and <W> the preference word as the game lists them.  Pinned equal to src/vv_cie_graph.py
   AUTO_LINES by tests/test_cie_graph_v6.py. */
static const char *const CG_AUTO_LINES[][2] = {
    { "food+", "The village gains food." },
    { "food-", "The village loses food." },
    { "tech+", "The village gains tech points." },
    { "tech-", "The village loses tech points." },
    { "kill", "<R> dies." },
    { "vanish", "<R> disappears." },
    { "status", "<R> becomes a Heathen." },
    { "health", "<R>'s health changes." },
    { "like", "<R> now likes <W>." },
    { "dislike", "<R> now dislikes <W>." },
    { "unlike", "<R> no longer likes <W>." },
    { "undislike", "<R> no longer dislikes <W>." },
    { "skill+", "<R> learns more about <S>." },
    { "skill-", "<R> feels less sure of <P> <S>." },
    { "sick", "<R> falls sick." },
    { "celebrate_all", "The village celebrates." },
    { "celebrate", "<R> celebrates." },
    { "mood+", "<R> is in a good mood." },
    { "mood-", "<R> is in a bad mood." },
    { "health_change+", "<R> feels better." },
    { "health_change-", "<R> feels worse." },
    { "set100", "<R> masters <S>." },
    { "set0", "<R> forgets everything about <S>." },
    { "set", "<R>'s <S> skill changes." },
    { "damage", "Something in the village is damaged." },
    { "hair", "<R>'s hair changes color." },
    { "look", "<R>'s look changes." },
    { "die_unrecovered", "<R> dies; the body is not recovered." },
    { "baby_lost", "<R>'s baby is lost." },
    { "old_look", "<R> looks older and more worn." },
    { "sex_change", "<R>'s sex changes." },
    { "cure", "<R> is cured." },
    { "young_look", "<R> looks younger." },
    { "repair", "The damaged buildings are being repaired." },
    { "skill_best", "<R> gets better at what <P> does best." },
    { "faith", "<R> feels closer to the tribe." },
    { "join", "<R> joins the tribe." },
    { "apostasy", "<R> becomes a Heathen." },
    { "presentation", "<R>'s look changes." },
};

/* Line `key` with the role's placeholders and the words put in, after a line break when `out` has text already. */
static void cg_auto_add(char *out, int cap, const char *key, int role, const char *skill, const char *word) {
    char line[256];
    const char *t = NULL, *id = role >= 0 && role < cg_g.n_role ? cg_s(&cg_g, cg_u16(cg_role_at(&cg_g, role) + 4)) : "";
    int i, n = 0;
    for (i = 0; i < (int)(sizeof CG_AUTO_LINES / sizeof CG_AUTO_LINES[0]); ++i) {
        if (lstrcmpA(CG_AUTO_LINES[i][0], key) == 0) {
            t = CG_AUTO_LINES[i][1];
        }
    }
    if (t == NULL) {
        return;
    }
    for (; *t != '\0' && n < (int)sizeof line - 1; ++t) {
        const char *put = NULL, *tail = "";
        if (t[0] == '<' && t[1] != '\0' && t[2] == '>') {
            put = t[1] == 'R' ? "(" : t[1] == 'P' ? "(" : t[1] == 'S' ? skill : t[1] == 'W' ? word : NULL;
            tail = t[1] == 'R' ? ".Name)" : t[1] == 'P' ? ".his/her)" : "";
        }
        if (put == NULL) {
            line[n++] = *t;
            continue;
        }
        if (n + lstrlenA(put) + lstrlenA(id) + lstrlenA(tail) + 1 >= (int)sizeof line) {
            return;
        }
        lstrcpyA(line + n, put);
        n += lstrlenA(put);
        if (t[1] == 'R' || t[1] == 'P') {
            lstrcpyA(line + n, id);
            n += lstrlenA(id);
            lstrcpyA(line + n, tail);
            n += lstrlenA(tail);
        }
        t += 2;
    }
    line[n] = '\0';
    if (lstrlenA(out) + 1 + n + 1 < cap) {
        if (out[0] != '\0') {
            lstrcatA(out, "\n");
        }
        lstrcatA(out, line);
    }
}

/* Node `n`'s automatic lines after `out` (its text, the award filled in): one for each effect that has one, from the
   walk's rolls (fx index `fx` its first), the award as it stands (src/vv_cie_graph.py auto_line_options). */
static void cg_auto_lines(int game, const cg_history *h, const unsigned char *n, int fx, int award_kind, int award,
                          char *out, int cap) {
    const ce_adapter *a = ce_adapter_for(game);
    int k;
    for (k = 0; k < cg_fx_count(n); ++k, ++fx) {
        const unsigned char *e = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k);
        int va = fx < CG_MAX_FX ? h->fx_a[fx] : 0, vb = fx < CG_MAX_FX ? h->fx_b[fx] : 0;
        int lo = (int)cg_u32(e + 4), hi = (int)cg_u32(e + 8);
        int role = e[1] == CG_ROLE_ALIAS_ALL ? -1 : (int)e[1];
        char word[48];
        if (e[1] == CG_ROLE_GROUP || e[1] == CG_ROLE_NEWEST || e[1] == CG_ROLE_NEWEST2) {
            continue;                  /* no role to name: the author's text tells it */
        }
        const char *skill = a != NULL && va >= 0 && va < a->skill_count ? a->skill_names[va] : NULL;
        switch (e[0]) {
        case CGE_FOOD: case CGE_TECH:
            if (!(e[2] & 2u) && va != 0) {
                cg_auto_add(out, cap, e[0] == CGE_FOOD ? (va > 0 ? "food+" : "food-") : (va > 0 ? "tech+" : "tech-"),
                            -1, "", "");
            }
            break;
        case CGE_PAY:
            if (award_kind >= 0 && award != 0) {
                cg_auto_add(out, cap, award_kind == 0 ? (award > 0 ? "food+" : "food-") : (award > 0 ? "tech+" : "tech-"),
                            -1, "", "");
            }
            break;
        case CGE_KILL: cg_auto_add(out, cap, "kill", role, "", ""); break;
        case CGE_VANISH: cg_auto_add(out, cap, "vanish", role, "", ""); break;
        case CGE_STATUS: cg_auto_add(out, cap, "status", role, "", ""); break;
        case CGE_HEALTH: cg_auto_add(out, cap, "health", role, "", ""); break;
        case CGE_SICK: cg_auto_add(out, cap, "sick", role, "", ""); break;
        case CGE_DIE_UNRECOVERED: cg_auto_add(out, cap, "die_unrecovered", role, "", ""); break;
        case CGE_BABY_LOST: cg_auto_add(out, cap, "baby_lost", role, "", ""); break;
        case CGE_OLD_LOOK: cg_auto_add(out, cap, "old_look", role, "", ""); break;
        case CGE_YOUNG_LOOK: cg_auto_add(out, cap, "young_look", role, "", ""); break;
        case CGE_CURE: cg_auto_add(out, cap, "cure", role, "", ""); break;
        case CGE_FAITH: cg_auto_add(out, cap, "faith", role, "", ""); break;
        case CGE_JOIN: cg_auto_add(out, cap, "join", role, "", ""); break;
        case CGE_APOSTASY: cg_auto_add(out, cap, "apostasy", role, "", ""); break;
        case CGE_REPAIR: cg_auto_add(out, cap, "repair", -1, "", ""); break;
        case CGE_SEX_CHANGE: cg_auto_add(out, cap, "sex_change", role, "", ""); break;
        case CGE_PRESENTATION: cg_auto_add(out, cap, "presentation", role, "", ""); break;
        case CGE_DAMAGE: cg_auto_add(out, cap, "damage", -1, "", ""); break;
        case CGE_CELEBRATE: cg_auto_add(out, cap, role < 0 ? "celebrate_all" : "celebrate", role, "", ""); break;
        case CGE_MOOD: cg_auto_add(out, cap, lo > 0 ? "mood+" : "mood-", role, "", ""); break;
        case CGE_HEALTH_CHANGE:
            if (va != 0) {
                cg_auto_add(out, cap, va > 0 ? "health_change+" : "health_change-", role, "", "");
            }
            break;
        case CGE_APPEARANCE: cg_auto_add(out, cap, hi == CG_LOOK_KEEP ? "hair" : "look", role, "", ""); break;
        case CGE_PREF:
            if (e[2] & CG_PREF_RANDOM) {
                if (a == NULL || va < 0 || !ui_list_entry(a->pref_list, va, word, sizeof word)) {
                    break;
                }
            } else {
                lstrcpynA(word, cg_s(&cg_g, cg_u16(e + 12)), sizeof word);
            }
            cg_auto_add(out, cap, (e[2] & CG_PREF_REMOVE) ? ((e[2] & 4u) ? "undislike" : "unlike")
                                                        : ((e[2] & 4u) ? "dislike" : "like"), role, "", word);
            break;
        case CGE_SKILL:
            if (va == -2 && vb > 0) {
                cg_auto_add(out, cap, "skill_best", role, "", "");
            } else if (skill != NULL && vb != 0) {
                cg_auto_add(out, cap, vb > 0 ? "skill+" : "skill-", role, skill, "");
            }
            break;
        case CGE_SKILL_SET:
            if (skill != NULL) {
                cg_auto_add(out, cap, vb == 100 ? "set100" : vb == 0 ? "set0" : "set", role, skill, "");
            }
            break;
        default:
            break;                     /* action: no line */
        }
    }
}

static void cg_group(int game, const cg_history *h, int from) {
    static char text[CG_RAW_BYTES];
    int award_kind = -1, award = 0, fx, k, i, first_text = -1;
    unsigned short title = cg_title_before(h, from);
    cg_pop_count = 0;
    fx = cg_award_before(h, from, &award_kind, &award);
    cg_visit_path(from);
    for (i = 0; i < from && i < CG_MAX_PATH; ++i) {
        cg_node_pop[i] = -2;           /* an earlier segment's: laid out already */
    }
    for (i = from; i < h->nodes; ++i) {
        int node = h->node[i];
        const unsigned char *n = cg_node_at(&cg_g, node);
        int villager = 0, fx0 = fx;
        cg_visit(node);
        for (k = 0; k < cg_fx_count(n); ++k, ++fx) {
            const unsigned char *e = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k);
            villager |= e[0] >= CGE_KILL;
            if ((e[0] == CGE_FOOD || e[0] == CGE_TECH) && (e[2] & 2u)) {
                award_kind = e[0] == CGE_FOOD ? 0 : 1;
                award = fx < CG_MAX_FX ? h->fx_a[fx] : 0;
            }
        }
        if (n[0] != CG_BRANCH) {
            cg_popup *p = NULL;
            int start = 0;
            unsigned short nt = cg_node_title(node);
            cg_expand(cg_node_text(node, game), text, sizeof text, CG_EXPAND_AWARD, 0, award_kind, award);
            if (n[3] & CG_NODE_AUTO_TEXT) {
                cg_auto_lines(game, h, n, fx0, award_kind, award, text, sizeof text);   /* 25 */
            }
            if (cg_one_popup() && cg_pop_count > 0 && cg_pops[cg_pop_count - 1].question < 0
                && !(n[3] & CG_NODE_NEW_PAGE)) {
                /* ONE popup: every node up to the question (or the ending) joins the segment's one text; what was
                   a popup of its own (a question, a new popup) after a blank line (src/vv_cie_graph.py one_popup) */
                p = &cg_pops[cg_pop_count - 1];
                if (lstrlenA(p->raw) + 2 + lstrlenA(text) + 1 < (int)sizeof p->raw) {
                    start = lstrlenA(p->raw) + (p->raw[0] != '\0' ? (n[0] == CG_QUESTION || n[1] == 0 ? 2 : 1) : 0);
                    if (p->raw[0] != '\0') {
                        lstrcatA(p->raw, n[0] == CG_QUESTION || n[1] == 0 ? "\n\n" : n[2] ? "\n" : " ");
                    }
                    lstrcatA(p->raw, text);
                }
                if (n[0] == CG_QUESTION) {
                    p->question = node;
                }
            } else if (n[0] == CG_QUESTION || n[1] == 0 || cg_pop_count == 0
                       || cg_pops[cg_pop_count - 1].question >= 0) {
                if (cg_pop_count < CG_MAX_POPUPS) {
                    p = &cg_pops[cg_pop_count++];
                    memset(p, 0, sizeof *p);
                    p->question = n[0] == CG_QUESTION ? node : -1;
                    lstrcpynA(p->raw, text, sizeof p->raw);
                    p->tcount = 1;     /* the title in force at its start */
                    p->ttitle[0] = title;
                }
            } else {
                p = &cg_pops[cg_pop_count - 1];
                if (lstrlenA(p->raw) + 1 + lstrlenA(text) + 1 < (int)sizeof p->raw) {
                    start = lstrlenA(p->raw) + 1;
                    lstrcatA(p->raw, n[2] ? "\n" : " ");
                    lstrcatA(p->raw, text);
                }
            }
            if (nt != 0) {
                if (p != NULL && start == 0 && p->tcount == 1 && !(cg_group_in_question && p == &cg_pops[0])) {
                    p->ttitle[0] = nt;         /* a new popup starting with a titled node: only that title */
                } else if (p != NULL && p->tcount < CG_TITLE_CHANGES) {
                    p->toff[p->tcount] = start;   /* from the page this node's text starts on */
                    p->ttitle[p->tcount++] = nt;
                }
                title = nt;
            }
            if (first_text < 0) {
                first_text = i;
            }
        }
        cg_node_pop[i] = (short)(cg_pop_count - 1);
        cg_node_end[i] = (short)(cg_pop_count > 0 ? lstrlenA(cg_pops[cg_pop_count - 1].raw) : 0);
        if (villager && cg_pop_count > 0) {
            cg_pops[cg_pop_count - 1].effects = 1;
        }
    }
    /* Effects before any text: made with the first text's page. */
    for (i = from; i < h->nodes && first_text >= 0; ++i) {
        if (cg_node_pop[i] == -1) {
            const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
            cg_node_pop[i] = 0;
            cg_node_end[i] = cg_node_end[first_text];
            for (k = 0; k < cg_fx_count(n); ++k) {
                if (cg_effect_at(&cg_g, (int)cg_u16(n + 18) + k)[0] >= CGE_KILL) {
                    cg_pops[0].effects = 1;
                }
            }
        }
    }
}

/* The layouts: the question's pages; a result's first page (after a question) or a plain event's; every page
   shown through a notice (the plain popup, never taller than the result's: New Believers' result has more
   lines than its plain popup). */
static ce_layout cg_notice_layout(const ce_adapter *a) {
    ce_layout plain = ce_plain_layout(a);
    plain.check_title = 0;
    return plain;
}

/* The path from node `from` (a segment: the start's, or an answer's) laid out as more of the run's displays:
   `after_question` 1 = its first page is a question's result, 0 = a plain event's first popup (or the start
   question's); each page with the nodes whose effects it makes.  A question's text is laid out for the question
   popup: its earlier pages shown first (notices, through the plain popup, which is never smaller), its last page
   the two-button popup itself. */
/* 14: the popup's WIDEST title (of those in force on it, the one that wraps into the most lines in `l`; the first
   on a tie) into `out`: its pages are laid out with it. */
static void cg_widest_title(const cg_popup *p, const ce_layout *l, char *out, int cap) {
    static char t[CE_TITLE_BYTES + 64];
    int j, most = -1;
    cg_title_expand(0, CG_EXPAND_WORST, out, cap);
    for (j = 0; j < p->tcount; ++j) {
        int lines;
        cg_title_expand(p->ttitle[j], CG_EXPAND_WORST, t, sizeof t);    /* 17: at its widest as shown */
        lines = ce_lines_used_in(l, t, "");
        if (lines > most) {
            most = lines;
            lstrcpynA(out, t, cap);
        }
    }
}

/* 14: the title page `k` of popup `p` shows: the last change that starts before the page's end. */
static unsigned short cg_page_title(const cg_popup *p, const cg_pages *pages, int k) {
    unsigned short t = p->tcount > 0 ? p->ttitle[0] : 0;
    int j;
    for (j = 1; j < p->tcount; ++j) {
        if (p->toff[j] < pages->src_end[k]) {
            t = p->ttitle[j];
        }
    }
    return t;
}

/* The owner (2026-11-16): after the player clicks a choice, the popups that follow take that choice's label as their
   title (until the next choice), unless a node there has a title of its own.  The label of the choice that led to
   path node `from` (the node after a question), as a title (its string index + 1); 0 none.  Always the label, never
   the event's title instead: one wider than the title area wraps, its rest the page's first line (cg_display_title,
   cg_display: "should not be a problem with the scrollbars"). */
static int cg_layout_choice = -1;     /* the choice cg_take_answer lays out the pages of (-1: none known) */

static unsigned short cg_choice_title(const cg_history *h, int from) {
    static char worst[CE_LONG_LINE_BYTES * 4];
    const unsigned char *q;
    int k, count, first;
    if (cg_g.version < 6 || from <= 0 || from >= h->nodes) {
        return 0;
    }
    q = cg_node_at(&cg_g, h->node[from - 1]);
    if (q[0] != CG_QUESTION) {
        return 0;
    }
    first = (int)cg_u16(q + 12);
    count = (int)cg_u16(q + 14);
    if (cg_layout_choice >= 0 && cg_layout_choice < count) {
        /* the choice the player picked (several choices may lead to the same node: its own label, Codex P2) */
        unsigned int label = cg_u16(cg_child_at(&cg_g, first + cg_layout_choice) + 8);
        (void)worst;
        return label != CG_NONE ? (unsigned short)(label + 1u) : 0;
    }
    for (k = 0; k < count; ++k) {
        const unsigned char *c = cg_child_at(&cg_g, first + k);
        unsigned int label = cg_u16(c + 8);
        if ((int)cg_u16(c) != h->node[from] || label == CG_NONE) {
            continue;
        }
        (void)worst;
        return (unsigned short)(label + 1u);   /* always (the owner): a label wider than the title area wraps */
    }
    return 0;
}

static void cg_layout_from(const ce_adapter *a, int game, int from, int after_question) {
    static cg_pager w;
    static cg_pages pages;
    static char real[CG_PAGE_BYTES];
    static char widest[CE_TITLE_BYTES + 64];
    const cg_history *h = &cg.path;
    int fresh = after_question && from > 0 && cg_fresh_after(h->node[from - 1], cg.answers);
    ce_layout first = after_question && !fresh ? ce_result_layout(a) : cg_notice_layout(a);
    ce_layout rest = cg_notice_layout(a);
    ce_layout q = ce_question_layout(a);
    int p, k, i, jobs = cg.jobs_used;
    q.check_title = 0;
    cg_group_in_question = after_question && from > 0 && !fresh;
    cg_group(game, h, from);
    cg_group_in_question = 0;
    if (after_question && from > 0) {
        /* the choice's label as the title of what follows, where no node of this part set one (cg_choice_title);
           set before the pages are laid out, so the title area is measured with it */
        unsigned short choice = cg_choice_title(h, from), before = cg_title_before(h, from);
        if (from < h->nodes && cg_node_title(h->node[from]) != 0) {
            choice = 0;                /* the next node has a title of its own: it keeps it */
        }
        for (p = 0; choice != 0 && p < cg_pop_count; ++p) {
            int j;
            if (cg_pops[p].tcount == 0) {
                cg_pops[p].tcount = 1;
                cg_pops[p].toff[0] = 0;
                cg_pops[p].ttitle[0] = choice;
                continue;
            }
            for (j = 0; j < cg_pops[p].tcount; ++j) {
                if (cg_pops[p].ttitle[j] == before) {
                    cg_pops[p].ttitle[j] = choice;
                }
            }
        }
    }
    for (p = 0; p < cg_pop_count; ++p) {
        int question = cg_pops[p].question >= 0;
        w.a = a;
        w.first = question ? &q : (p == 0 ? &first : &rest);
        w.rest = question ? &q : &rest;
        cg_widest_title(&cg_pops[p], w.first, widest, sizeof widest);
        w.title = widest;
        w.reserve = cg_pops[p].effects ? 2 : 0;
        if (question) {
            w.reserve += cg_answer_room(cg_pops[p].question, &q);
        } else if (p == 0 && after_question && from > 0 && !fresh) {
            w.reserve += cg_answer_room(h->node[from - 1], &first);   /* shown in the answered question's popup */
        }
        w.pages = &pages;
        w.scroll = cg_scrolls();
        if (!w.scroll) {
            /* A title wider than its area shows its rest as the page's first lines (cg_display): those lines kept
               free on every page, so the text is paged around them, never cut (Codex, #771). */
            static char probe[CG_LABEL_V6 * 4];
            ce_layout bare = *w.first;
            bare.with_title = 0;
            lstrcpynA(probe, widest, (int)sizeof probe);
            cg_title_wrap(probe);
            if (cg_title_rest[0] != '\0') {
                w.reserve += ce_lines_used_in(&bare, "", cg_title_rest);
            }
            cg_title_rest[0] = '\0';
        }
        cg_paginate(&w, cg_pops[p].raw);
        for (k = 0; k < pages.count; ++k) {
            int d, kind = CGD_PAGE;
            if (question && k + 1 == pages.count) {
                kind = CGD_QUESTION;
            } else if (p == 0 && k == 0 && after_question && !fresh) {
                kind = CGD_RESULT;     /* G1: after five or more buttons, a page of its own (a notice) */
            }
            cg_late_mask = cg_late_roles();
            cg_late_keep = cg_late_mask != 0u;     /* 35: those roles' words filled as the page is shown */
            cg_expand(pages.buf + pages.off[k], real, sizeof real, CG_EXPAND_REAL, a->name_room, -1, 0);
            cg_late_keep = 0;
            d = cg_add_display(real, kind, cg_pops[p].effects);
            if (d < 0) {
                cg.jobs_used = jobs;
                return;
            }
            cg.display_node[d] = (short)(kind == CGD_QUESTION ? cg_pops[p].question : -1);
            /* 14: a page shown in the question's own popup keeps that popup's title. */
            cg.display_title[d] = kind == CGD_RESULT ? cg_pops[p].ttitle[0] : cg_page_title(&cg_pops[p], &pages, k);
            cg.job_first[d] = (short)jobs;
            for (i = from; i < h->nodes; ++i) {
                const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
                int page = 0;
                if (cg_node_pop[i] != p || cg_fx_count(n) == 0) {
                    continue;
                }
                while (page + 1 < pages.count && pages.src_end[page] < cg_node_end[i]) {
                    ++page;            /* the page holding the end of the node's text */
                }
                if (page == k && jobs < CG_MAX_PATH) {
                    cg.jobs[jobs++] = (short)i;
                }
            }
            cg.job_count[d] = (short)(jobs - cg.job_first[d]);
        }
    }
    cg.jobs_used = jobs;
}

/* The displays from `count` on taken away (a question answered again, a restore). */
static void cg_displays_cut(int count) {
    if (count < 0) {
        count = 0;
    }
    if (count >= cg.display_count) {
        return;
    }
    cg.display_count = count;
    cg.display_used = count > 0 ? cg.display_off[count - 1] + lstrlenA(cg.displays + cg.display_off[count - 1]) + 1 : 0;
    cg.jobs_used = count > 0 ? cg.job_first[count - 1] + cg.job_count[count - 1] : 0;
    if (cg.display_next > count) {
        cg.display_next = count;
    }
}

static void cg_entry_start(const char *label);

/* The run's first segment, from the start: walked, added to the path and laid out (the roles are bound). */
static void cg_start_run(const ce_adapter *a, int game) {
    static cg_history first;
    memset(&cg.path, 0, sizeof cg.path);
    cg.pick_count = cg.start_picks;    /* the start question's, drawn at the purchase (cg_queue) */
    cg.display_count = cg.display_next = cg.display_used = cg.jobs_used = 0;
    cg.answers = 0;
    cg.choice = -1;
    cg_draw_aliases(a, cg.bound);      /* version 6: before the first node (at the purchase for a question) */
    cg_partner_carry_decide(a, game);  /* who carries: the cast and the aliases made, no page yet written */
    cg_walk(a, game, cg_g.start, &first, NULL, NULL);   /* its picks are the path's own */
    cg_path_add(&first, NULL, 0);
    cg_layout_from(a, game, 0, 0);
    if (!cg.question) {
        cg_entry_start(NULL);
    }
    cg.phase = CG_CHAIN;
}

/* ---- The Island Events log's one entry ("VVFP Island Events.dll", native/vvfp_island_events) ----------------

   The owner (2026-11-12): ONE entry per branching event -- the title, the "Choice:" line, then every change in page
   order as it happens.  Each page that makes effects is bracketed through that companion's own comparison
   (VvfpIslandEventsGraphBegin / End: the same field words, as "  <name>: <Label> <old> -> <new>" lines), appended
   to the entry the run keeps (cg.entry, in the run's file: a quit continues the same entry, and a page shown again
   after a restore first takes its own lines back, entry_at), and the entry so far is handed over after each page
   (VvfpIslandEventsGraphWrite -> the Parentage Export's WriteVillageEventEntry: a held record REPLACED each time,
   whose next save writes what it has gained onto the same on-disk entry), so the log matches the save at every
   save; the event's end closes it.  A run put back after a reload tells the log what the save's log already holds
   (sent_len).  The game's own bracket around each of these popups writes nothing for it (VvfpStoryGraphLogged).
   Without that companion (its row off): nothing. */

typedef int (__stdcall *cg_log_begin_fn)(int game);
typedef int (__stdcall *cg_log_end_fn)(int game, char *out, int cap);
typedef int (__stdcall *cg_log_write_fn)(int game, int key, const char *text, int disk, int final);
static int cg_logged;                  /* the game whose last popup was this run's (asked once by the log) */
static char cg_shown_title[CE_LONG_LINE_BYTES * 4];   /* the title of the run's popup shown last (14: a node's may
                                                         differ) */

#ifdef VVFP_TEST
static int test_graph_log;             /* stands in for the companion: each page's lines "  page <k>" */
static int test_graph_log_page;
static char test_graph_entry[CG_ENTRY_BYTES];   /* the entry handed over as final, last */
static int test_graph_entries;          /* ...and how many times */
static char test_graph_sent[CG_ENTRY_BYTES];    /* the entry handed over last (any) */
static int test_graph_sent_disk, test_graph_sent_final, test_graph_sends;
#endif

static FARPROC cg_log_export(const char *name) {
    HMODULE module = GetModuleHandleA("VVFP Island Events.dll");
    return module != NULL ? GetProcAddress(module, name) : NULL;
}

static void cg_entry_put(const char *text) {
    int n = lstrlenA(text);
    if (cg.entry_len + n + 1 < CG_ENTRY_BYTES) {
        memcpy(cg.entry + cg.entry_len, text, (size_t)n + 1);
        cg.entry_len += n;
    }
}

/* The entry's header: the title, and the button clicked (`label`, or NULL with no question). */
static void cg_entry_start(const char *label) {
    static char line[CE_LONG_LINE_BYTES * 8 + 32], title[CE_LONG_LINE_BYTES * 4];
    cg.entry_len = 0;
    cg.entry[0] = '\0';
    cg_title_logged(title, sizeof title);
    cg_join(line, (int)sizeof line, "  Event: ", title, "\n");
    cg_entry_put(line);
    if (label != NULL) {
        cg_join(line, (int)sizeof line, "  Choice: ", label, "\n");
        cg_entry_put(line);
    }
    cg.entry_head = cg.entry_len;
}

static int cg_log_begin(int game) {
    cg_log_begin_fn begin;
#ifdef VVFP_TEST
    if (test_graph_log) {
        test_graph_log_page = cg.display_next;
        return 1;
    }
#endif
    begin = (cg_log_begin_fn)(void *)cg_log_export("VvfpIslandEventsGraphBegin");
    return begin != NULL && begin(game);
}

static void cg_log_end(int game) {
    static char lines[4096];
    cg_log_end_fn end;
    lines[0] = '\0';
#ifdef VVFP_TEST
    if (test_graph_log) {
        wsprintfA(lines, "  page %d\n", test_graph_log_page);
        cg_entry_put(lines);
        return;
    }
#endif
    end = (cg_log_end_fn)(void *)cg_log_export("VvfpIslandEventsGraphEnd");
    if (end != NULL && end(game, lines, (int)sizeof lines) > 0) {
        cg_entry_put(lines);
    }
}

/* The entry as it is now, handed to the log (VvfpIslandEventsGraphWrite -> the Parentage Export's
   WriteVillageEventEntry): its held record replaced, so the next save writes what it has gained onto the same
   entry -- the log matches the save at every save.  `disk`: what the last save's log holds of it (a run put back
   after a reload; -1 when the log already knows), `final` 1 when the event is over. */
static int cg_log_key(void) {
    return (int)((unsigned int)cg.when & 0x7FFFFFFFu) | 1;
}

static void cg_log_send(int game, int disk, int final) {
    cg_log_write_fn write;
    if (cg.entry_head == 0) {
        return;                        /* not started (no answer yet) */
    }
#ifdef VVFP_TEST
    if (test_graph_log) {
        lstrcpynA(test_graph_sent, cg.entry, sizeof test_graph_sent);
        test_graph_sent_disk = disk;
        test_graph_sent_final = final;
        ++test_graph_sends;
        if (final) {
            lstrcpynA(test_graph_entry, cg.entry, sizeof test_graph_entry);
            ++test_graph_entries;
        }
        return;
    }
#endif
    write = (cg_log_write_fn)(void *)cg_log_export("VvfpIslandEventsGraphWrite");
    if (write != NULL) {
        (void)write(game, cg_log_key(), cg.entry, disk, final);
    }
}

/* The event is over: its one entry closed ("Changes: none" when it changed nothing, as every event shown is). */
static void cg_log_write(int game) {
    if (cg.entry_head == 0) {
        return;
    }
    if (cg.entry_len == cg.entry_head) {
        cg_entry_put("  Changes: none\n");
    }
    cg_log_send(game, -1, 1);
}

/* Asked by "VVFP Island Events.dll" as it compares the popup the game just showed: 1 (once) when it was this
   run's page or question -- its changes are the event's one entry's, never a record of their own. */
__declspec(dllexport) int __stdcall VvfpStoryGraphLogged(int game, const char *title) {
    if (cg_logged == 0 || cg_logged != game) {
        return 0;
    }
    if (title != NULL && title[0] != '\0' && lstrcmpA(title, cg.title) != 0 && lstrcmpA(title, cg_shown_title) != 0) {
        return 0;                      /* another event's popup */
    }
    cg_logged = 0;
    return 1;
}

/* The effects display `k` makes, each once: every node of its jobs, in the history's order, the award's state
   and the rolls as the walk left them. */
static void cg_make_effects(const ce_adapter *a, int game, int k, ce_result *r) {
    const cg_history *h = &cg.path;
    int j;
    memset(r, 0, sizeof *r);
    cg_display_now = k;
    cg_count_page[0] = cg_count_page[1] = 0;
    cg_count_page_any[0] = cg_count_page_any[1] = 0;
    cg.gone_at[k] = cg.gone;
    memcpy(cg.identity_at[k], cg.identity, sizeof cg.identity);
    {
        int role;
        for (role = 0; role < CG_MAX_ROLES; ++role) {
            cg.female_at[k][role] = (unsigned char)(cg.female[role] != 0);   /* 35: the words before its effects */
        }
    }
    for (j = 0; j < cg.job_count[k]; ++j) {
        int i = cg.jobs[cg.job_first[k] + j];
        const unsigned char *n = cg_node_at(&cg_g, h->node[i]);
        int award_kind, award, fx, e;
        fx = cg_award_before(h, i, &award_kind, &award);
        for (e = 0; e < cg_fx_count(n); ++e, ++fx) {
            const unsigned char *eff = cg_effect_at(&cg_g, (int)cg_u16(n + 18) + e);
            int va = fx < CG_MAX_FX ? h->fx_a[fx] : 0, vb = fx < CG_MAX_FX ? h->fx_b[fx] : 0;
            cg_effect(a, game, eff, va, vb, &award_kind, &award, r);
        }
    }
    if (cg.job_count[k] > 0) {
        cg.applied_when[k] = sq_clock();
    }
    for (j = 0; j < 2; ++j) {
        if (cg_count_page_any[j]) {
            cg_count_last[j] = cg_count_page[j];   /* 33: this page's count, for this page and the next */
        }
    }
}

/* Show display `k` (the next one): its effects made, then its words composed for its popup with that page's
   refusal lines, into `text`. */
static void cg_show(const ce_adapter *a, int game, int k, char *text, int size) {
    ce_result r;
    ce_layout l = cg.display_kind[k] == CGD_RESULT ? ce_result_layout(a) : cg_notice_layout(a);
    int logging;
    cg.entry_at[k] = cg.entry_len;
    logging = cg.job_count[k] > 0 && cg_log_begin(game);
    cg_extra_lines[0] = '\0';
    cg_make_effects(a, game, k, &r);
    if (logging) {
        cg_log_end(game);              /* this page's changes, appended to the event's one entry ... */
        cg_entry_put(cg_extra_lines);  /* ... with what the comparison of the villagers cannot say (damage) ... */
        if (cg.display_next + 1 < cg.display_count || cg.phase != CG_CHAIN) {
            cg_log_send(game, -1, 0);  /* ... and the entry so far held for the next save (the last page's: final) */
            cg.sent_len[k] = cg.entry_len;
        }
    }
    cg_logged = game;                  /* the game's own bracket around this popup is not a record of its own */
    cg_display_title(k, cg_shown_title, sizeof cg_shown_title);   /* 14: the title in force on this page */
    lstrcpynA(ce_armed_event.title, cg_shown_title, sizeof ce_armed_event.title);   /* the later games draw it */
    su_title_whole = cg_shown_title;   /* ... whole (story_objects.inc ce_deliver_object) */
    cg_compose(&l, cg_shown_title, cg_display(k), r.refused > 0 ? &r : NULL, text, size);
    cg.display_next = k + 1;
}

/* The question's text (the start node, its variant for this run) laid out in pages for the question popup; the
   pages before the last are shown first (through a plain popup, which is never smaller). */
static void cg_question_pages(const ce_adapter *a, int game, cg_pages *pages) {
    static cg_pager w;
    static char raw[CG_RAW_BYTES];
    static char title[CE_TITLE_BYTES];
    ce_layout q = ce_question_layout(a);
    memset(cg_visited, 0, sizeof cg_visited);
    cg_visit(cg_g.start);
    cg_expand(cg_node_text(cg_g.start, game), raw, sizeof raw, CG_EXPAND_AWARD, 0, -1, 0);
    q.check_title = 0;
    w.a = a;
    w.first = &q;
    w.rest = &q;
    cg_title_expand(cg_node_title(cg_g.start), CG_EXPAND_WORST, title, sizeof title);   /* 14, 17 */
    w.title = title;
    w.reserve = cg_answer_room(cg_g.start, &q);
    w.pages = pages;
    w.scroll = cg_scrolls();
    cg_paginate(&w, raw);
}

/* ---- Arming each display ----------------------------------------------------------------------------------- */

/* The next display is a question's own popup (its earlier pages shown, or none): the start's, before the run is
   laid out, or any question's (version 2) once it is; a question asked again after a restore. */
static int cg_start_may_ask(void);

static int cg_next_is_question(void) {
    switch (cg.phase) {
    case CG_QUEUED: return (cg.question && cg.pre_pages == 0) || (cg_one_popup() && cg_start_may_ask());
    case CG_ASKED: return 1;
    case CG_CHAIN:
        return cg.display_next < cg.display_count && cg.display_kind[cg.display_next] == CGD_QUESTION;
    default: return 0;
    }
}

/* The node of the question to ask next (or being asked). */
static int cg_question_node(void) {
    if (cg.phase == CG_QUEUED) {
        return cg_g.start;
    }
    if (cg.phase == CG_ASKED) {
        return cg.asking >= 0 && cg.asking < cg.display_count ? cg.display_node[cg.asking] : -1;
    }
    return cg.display_next < cg.display_count ? cg.display_node[cg.display_next] : -1;
}

/* Arm the run's next display in `game`: the island event made due as the purchase makes it (`due`), or only
   remembered (a restore: the save holds the timer).  The question and the event's first popup are the island
   event (counted); every other page a notice.  1 when armed. */
static int cg_arm(int game, int due) {
    int question = cg_next_is_question();
    int notice = cg.phase != CG_QUEUED && !question;
    memset(&cg_stub, 0, sizeof cg_stub);
    cg_stub.game = game;
    /* 14: the title in force on the display armed (a run not laid out yet: its start's, else the event's; the
       first page's own is put in place as it is delivered, cg_show). */
    if (cg.phase == CG_QUEUED) {
        cg_title_text(cg_node_title(cg_g.start), cg_stub.title, sizeof cg_stub.title);
    } else {
        cg_display_title(cg.phase == CG_ASKED ? cg.asking : cg.display_next, cg_stub.title, sizeof cg_stub.title);
    }
    if (question) {
        int b, node = cg_question_node();
        if (node < 0 || node >= cg_g.n_node) {
            return 0;
        }
        /* (Only its own fields: the stub's outcomes stay zero, never written.) */
        cg_choice_stub.enabled = 1;
        cg_choice_stub.featured_record = 0;
        cg_choice_stub.featured_identity = 0;
        for (b = 0; b < 2; ++b) {
            const unsigned char *n = cg_node_at(&cg_g, node);
            const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(n + 12) + b);
            /* One popup: the start may be a page before the question (its labels come when it is asked). */
            lstrcpynA(cg_choice_stub.labels[b], n[0] == CG_QUESTION ? cg_s(&cg_g, cg_u16(c + 8)) : "",
                      CE_BUTTON_BYTES);
            cg_choice_stub.outcome_count[b] = 1;
            cg_choice_stub.outcomes[b][0].chance = 1;
        }
    }
    if (due) {
        if (!ce_arm_with(game, &cg_stub, question ? &cg_choice_stub : NULL, notice)) {
            return 0;
        }
    } else {
        ce_armed_event = cg_stub;
        ce_store_choice(game, question ? &cg_choice_stub : NULL);
        ce_armed = 1;
        ce_armed_is_notice = notice;
        ce_wait_arm = 0;
        ce_armed_village = story_village_now(game);
    }
    cg_display_armed = 1;
    return 1;
}

/* Whether the run has a display still to show (and none armed or asked). */
static int cg_wants_display(void) {
    if (cg.phase == CG_IDLE || cg.phase == CG_DONE || cg_display_armed || (ce_asked && cg.phase == CG_ASKED)) {
        return 0;
    }
    switch (cg.phase) {
    case CG_QUEUED: case CG_ASKED: return 1;
    default: return cg.display_next < cg.display_count;
    }
}

/* The slot is free for a display: nothing else armed or on its way, and the game's trigger could show it. */
static int cg_slot_free(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL || !story_installed(game) || ce_armed || ce_asked || pick_slot >= 0 || GAMES[game].island_pending()
        || time_skip_event_open()) {
        return 0;
    }
    ce_refusal_for_choice = cg_next_is_question();
    {
        const char *refused = a->arm_refusal();
        ce_refusal_for_choice = 0;
        return refused == NULL;
    }
}

/* Every page shown: done -- its file kept (CG_DONE) until a save holds the effects of its last pages
   (cg_flush_file), so a crash before that save brings back exactly the pages whose effects the save lacks. */
static void cg_finish(void) {
    int k;
    lv_on_finish(cg.game);             /* a Living Event Engine variant: the archetype reached (story_living.inc) */
    cg_log_write(cg.game);             /* the Island Events log's one entry, now whole */
    if (cg.display_count > 0 && cg.entry_head > 0) {
        cg.sent_len[cg.display_count - 1] = cg.entry_len;
    }
    cg.phase = CG_IDLE;
    for (k = 0; k < cg.display_count; ++k) {
        if (cg.applied_when[k] != 0) {
            cg.phase = CG_DONE;
        }
    }
    cg_display_armed = 0;
    cg_dirty = 1;
}

/* ---- The hooks story_custom.inc calls ------------------------------------------------------------------- */

/* ce_held: a run not yet shown waits while the village cannot fill its roles; the island event is made due again
   once it can (ce_opening_tick). */
static int cg_holds(int game) {
    if (!cg_owns_armed(game) || cg.phase != CG_QUEUED || cg.bound != 0u || cg_feasible(game)) {
        return 0;
    }
    ce_wait_arm = 1;
    return 1;
}

/* The roles bound before the first display (the rolls that pick them are the game's own). */
static int cg_prepare(int game) {
    if (cg.phase != CG_QUEUED || cg.bound != 0u) {
        return 1;
    }
    if (!cg_bind(game)) {
        ce_wait_arm = 1;
        return 0;
    }
    cg_dirty = 1;
    return 1;
}

/* Whether the display ce_deliver is about to show is the island event itself (a plain event's first page), not a
   notice page. */
static int cg_counted_next(void) {
    return cg.phase == CG_QUEUED && !cg.question;
}

/* The display ce_deliver shows: *counted 1 when it is the event itself (a plain event's first page), 0 for a
   notice page.  1 when `text` holds it. */
static int cg_deliver(int game, char *text, int size, int *counted) {
    const ce_adapter *a = ce_adapter_for(game);
    *counted = 0;
    if (a == NULL) {
        return 0;
    }
    cg_display_armed = 0;
    if (cg.phase == CG_QUEUED) {
        *counted = !cg.question;
        cg_start_run(a, game);         /* the start question's earlier pages, or the event's first popup */
    }
    if (cg.display_next < cg.display_count) {
        cg_show(a, game, cg.display_next, text, size);
    } else if (size > 0) {
        text[0] = '\0';
    }
    if (cg.phase == CG_CHAIN && cg.display_next >= cg.display_count) {
        cg_finish();
    }
    cg_dirty = 1;
    return 1;
}

/* The question `cg.answers` (asked at display `k`, its node the path's last): both answers' segments walked
   (once: asked again after a restore, the same histories). */
static void cg_walk_answers(const ce_adapter *a, int game, int k) {
    int qi = cg.answers, b;
    int node = cg.display_node[k];
    if (qi < 0 || qi >= CG_MAX_QUESTIONS || node < 0) {
        return;
    }
    if (!cg.seg_walked[qi]) {
        /* The buttons shown (version 6: a choice whose `if` fails is not, and is never walked), then each shown
           choice's segment, in the choices' order. */
        unsigned char map[CG_MAX_ANSWERS];
        int shown = cg_shown_choices(node, game, map);
        memcpy(cg.q_map[qi], map, sizeof map);
        cg.q_shown[qi] = (unsigned char)shown;
        for (b = 0; b < shown; ++b) {
            int choice = map[b];
            const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + choice);
            cg_walk(a, game, (int)cg_u16(c), cg_seg(qi, choice), cg.seg_picks[qi][choice],
                    &cg.seg_pick_count[qi][choice]);
        }
        cg.seg_walked[qi] = 1;
        cg.q_display[qi] = (short)k;
        cg.q_path[qi] = (short)cg.path.nodes;
        cg.q_fx[qi] = (short)cg.path.fx;
        cg.q_picks[qi] = (short)cg.pick_count;
    }
}

/* The question (ce_choice_begin): its own page (the last of its text) into `text`, both answers' segments walked,
   its labels with the names filled in.  Only the start's question is the island event: a later one's count is
   taken back (Island Events Seen counts the event once). */
static void cg_begin_question(int game, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    static char real[CG_PAGE_BYTES];
    ce_layout q;
    int b, k, node, counted;
    if (a == NULL) {
        return;
    }
    cg_display_armed = 0;
    if (cg_one_popup() && !cg_op_in_place) {
        cg_op_begun = game;            /* the host shows the whole event in this popup */
    }
    if (cg.phase == CG_QUEUED) {
        cg_start_run(a, game);         /* a start question with no earlier page */
    }
    k = cg.phase == CG_ASKED ? cg.asking : cg.display_next;
    if (cg_one_popup() && k >= 0 && k < cg.display_count && cg.display_kind[k] != CGD_QUESTION) {
        /* One popup: the event's text before any question (a start whose walk asked none) -- shown with its
           effects, OK ends it. */
        cg_show(a, game, k, text, size);
        if (cg.display_next >= cg.display_count) {
            cg_finish();
        }
        cg_dirty = 1;
        return;
    }
    if (k < 0 || k >= cg.display_count || cg.display_kind[k] != CGD_QUESTION) {
        if (size > 0) {
            text[0] = '\0';
        }
        return;
    }
    /* The start's question (one popup: the event's first text) is the island event itself; a later question's
       popup is a notice's count (one popup: only after a reload, which brings its question back in a popup). */
    counted = cg_one_popup() ? k == 0 : cg.question && cg.answers == 0;
    if (!counted && !cg_op_in_place) {
        ce_uncount_notice(game);
    }
    node = cg.display_node[k];
    if (cg.job_count[k] > 0 && cg.applied_when[k] == 0) {
        /* (Never from a checked graph: a question makes no changes and the ones before it have a page.  Made here
           all the same, rather than lost.) */
        ce_result r;
        int logging = cg_log_begin(game);
        cg.entry_at[k] = cg.entry_len;
        cg_extra_lines[0] = '\0';
        cg_make_effects(a, game, k, &r);
        if (logging) {
            cg_log_end(game);
            cg_entry_put(cg_extra_lines);
            cg_log_send(game, -1, 0);
            cg.sent_len[k] = cg.entry_len;
        }
    }
    q = ce_question_layout(a);
    q.check_title = 0;
    cg_display_title(k, cg_shown_title, sizeof cg_shown_title);   /* 14: the title in force on the question */
    lstrcpynA(ce_asked_title, cg_shown_title, sizeof ce_asked_title);
    cg_compose(&q, cg_shown_title, cg_display(k), NULL, text, size);
    cg_walk_answers(a, game, k);
    {
        unsigned char map[CG_MAX_ANSWERS];
        int shown = cg_buttons(node, cg.answers, map);
        for (b = 0; b < CG_MAX_ANSWERS; ++b) {
            real[0] = '\0';
            if (b < shown) {
                const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + map[b]);
                cg_label_text(a, cg_s(&cg_g, cg_u16(c + 8)), real);
            }
            lstrcpynA(cg_labels[b], real, CE_LONG_LINE_BYTES);
            if (b < 2) {
                lstrcpynA(ce_choice_store[ce_asked_store].labels[b], real, CE_BUTTON_BYTES);
            }
        }
    }
    cg.phase = CG_ASKED;
    cg.asking = k;
    cg.display_next = k + 1;
    cg_answer_fresh_game = 0;
    cg_logged = game;                  /* the question's own popup: the entry's, never a record of its own */
    cg_dirty = 1;
}

/* Choice `choice` of the asked question added to the run: the path back to the question, that choice's segment
   on it, its pages laid out after the question's.  0 when nothing is asked. */
static int cg_take_answer(const ce_adapter *a, int game, int choice) {
    int qi = cg.answers;
    if (cg.phase != CG_ASKED || qi < 0 || qi >= CG_MAX_QUESTIONS || !cg.seg_walked[qi]) {
        return 0;
    }
    cg_displays_cut(cg.q_display[qi] + 1);
    cg.path.nodes = cg.q_path[qi];
    cg.path.fx = cg.q_fx[qi];
    cg.pick_count = cg.q_picks[qi];
    cg_path_add(cg_seg(qi, choice), cg.seg_picks[qi][choice], cg.seg_pick_count[qi][choice]);
    cg_layout_choice = choice;
    cg_layout_from(a, game, cg.q_path[qi], 1);
    cg_layout_choice = -1;
    return 1;
}

/* The answer (ce_choice_resolve): that button's segment laid out in pages, and its first page shown -- with the
   effects that page makes (the rest wait for their own pages).  The log entry gets the button clicked: its
   header's "Choice:" line for the start's question, another "Choice:" line for each later one. */
static int cg_resolve(int game, int button, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    static char label[CE_LONG_LINE_BYTES];
    unsigned char map[CG_MAX_ANSWERS];
    int qi = cg.answers, node, first, choice;
    if (a == NULL || button < 0 || button >= CG_MAX_ANSWERS || qi >= CG_MAX_QUESTIONS || cg.asking < 0) {
        return 0;
    }
    node = cg.display_node[cg.asking];
    if (node < 0 || button >= cg_buttons(node, qi, map)) {
        return 0;
    }
    choice = map[button];              /* the buttons close up over a choice not shown */
    if (!cg_take_answer(a, game, choice)) {
        return 0;
    }
    first = cg.q_display[qi] + 1;
    cg.answer[qi] = (unsigned char)choice;
    cg.answers = qi + 1;
    cg.choice = button;
    {
        const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(cg_node_at(&cg_g, node) + 12) + choice);
        static char line[CE_LONG_LINE_BYTES + 16];
        cg_label_text(a, cg_s(&cg_g, cg_u16(c + 8)), label);
        cg.q_entry[qi] = cg.entry_len;
        if (cg.entry_head == 0) {
            cg_entry_start(label);     /* the title and the start question's answer */
            cg.q_entry[qi] = 0;
        } else {
            cg_join(line, (int)sizeof line, "  Choice: ", label, "\n");
            cg_entry_put(line);
        }
    }
    cg.phase = CG_CHAIN;
    cg.asking = -1;
    cg.display_next = first;
    cg_answer_fresh_game = 0;
    if (cg_fresh_after(node, qi) && first < cg.display_count) {
        /* G1: the question's popup closes at the click (cg_answer_closes); the answer's first page is the next
           display, a popup of its own, with its effects. */
        cg_answer_fresh_game = game;
        if (size > 0) {
            text[0] = '\0';
        }
        cg_dirty = 1;
        return 1;
    }
    if (cg_one_popup() && first < cg.display_count && cg.display_kind[first] == CGD_QUESTION) {
        /* One popup: the answer's text ends in another question -- asked in the same popup, its choices after
           its text (its effects with it). */
        cg_op_in_place = 1;
        cg_op_lead = label;            /* 19: the choice picked starts the answer's text */
        cg_begin_question(game, text, size);
        cg_op_lead = NULL;
        cg_op_in_place = 0;
        ce_asked = 1;
        ce_asked_game = game;
        lstrcpynA(ce_asked_title, cg_shown_title, sizeof ce_asked_title);
        cg_dirty = 1;
        return 1;
    }
    if (first < cg.display_count) {
        cg_op_lead = cg_one_popup() ? label : NULL;   /* 19: the choice picked starts the answer's text */
        cg_show(a, game, first, text, size);
        cg_op_lead = NULL;
    } else if (size > 0) {
        lstrcpynA(text, cg_one_popup() ? label : "", size);
    }
    if (cg.display_next >= cg.display_count) {
        cg_finish();
    }
    cg_dirty = 1;
    return 1;
}

/* One popup: the game's OK on the event's popup.  When the run has a text still to show (a text longer than the
   popup holds, split: never otherwise), it replaces the one shown, in the same popup, and 1 is returned (the
   popup stays); 0 when the event is over (OK closes the popup, as the game's). */
static int cg_op_ok(int game, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL || !cg_one_popup() || cg.game != game || cg.phase != CG_CHAIN
        || cg.display_next >= cg.display_count) {
        return 0;
    }
    if (cg.display_kind[cg.display_next] == CGD_QUESTION) {
        cg_op_in_place = 1;
        cg_begin_question(game, text, size);
        cg_op_in_place = 0;
        ce_asked = 1;
        ce_asked_game = game;
        lstrcpynA(ce_asked_title, cg_shown_title, sizeof ce_asked_title);
    } else {
        cg_show(a, game, cg.display_next, text, size);
        if (cg.display_next >= cg.display_count) {
            cg_finish();
        }
    }
    cg_dirty = 1;
    return 1;
}

/* One popup: the choices the popup shows now (0 while OK shows), their words cg_label(0..). */
static int cg_op_rows(int game) {
    unsigned char map[CG_MAX_ANSWERS];
    if (game != 0 && ce_op_simple == game && cg_op_is_simple()) {
        /* The simple editor's question: its two choices while it is asked, then OK (its result shown). */
        return cg_one_popup() && ce_choice_asked(game) ? 2 : 0;
    }
    if (!cg_one_popup() || cg.game != game || cg.phase != CG_ASKED || cg.asking < 0 || cg.asking >= cg.display_count) {
        return 0;
    }
    return cg_buttons(cg.display_node[cg.asking], cg.answers, map);
}

/* One popup: whether the start's segment can ask a question -- a question reachable from the start through
   pages and branches (every child, every else) -- so the run is armed as a question and its one popup is the
   game's question popup, which shows choices.  (A start whose walk then asks none shows its text with OK.) */
static int cg_start_may_ask(void) {
    static short stack[CG_MAX_NODES];
    static unsigned char seen[CG_MAX_NODES];
    int top = 0, k;
    if (cg_g.start < 0 || cg_g.start >= cg_g.n_node || cg_g.n_node > CG_MAX_NODES) {
        return 0;
    }
    memset(seen, 0, (size_t)cg_g.n_node);
    stack[top++] = (short)cg_g.start;
    seen[cg_g.start] = 1;
    while (top > 0) {
        int node = stack[--top];
        const unsigned char *n = cg_node_at(&cg_g, node);
        int next[2];
        if (n[0] == CG_QUESTION) {
            return 1;
        }
        for (k = 0; k < (int)cg_u16(n + 14); ++k) {
            const unsigned char *c = cg_child_at(&cg_g, (int)cg_u16(n + 12) + k);
            int j;
            next[0] = (int)cg_u16(c);
            next[1] = (int)cg_u16(c + 6);
            for (j = 0; j < 2; ++j) {
                if (next[j] >= 0 && next[j] < cg_g.n_node && next[j] != (int)CG_NONE && !seen[next[j]]) {
                    seen[next[j]] = 1;
                    stack[top++] = (short)next[j];
                }
            }
        }
        k = (int)cg_u16(n + 16);
        if (k != (int)CG_NONE && k >= 0 && k < cg_g.n_node && !seen[k]) {
            seen[k] = 1;
            stack[top++] = (short)k;
        }
    }
    return 0;
}

/* ce_choice_tallest: the result `button` will show first, with room for its refusal lines when that page makes a
   villager's effect.  (Laid out and set aside: nothing is made, the run stays asked.) */
static int cg_tallest(int game, int button, char *out, int size) {
    static cg_history keep_path;
    static char shown[CE_TITLE_BYTES];
    const ce_adapter *a = ce_adapter_for(game);
    ce_layout first;
    ce_result most;
    unsigned char map[CG_MAX_ANSWERS];
    int lines = 0, count, used, jobs, k, picks;
    if (a == NULL || button < 0 || cg.phase != CG_ASKED || cg.asking < 0
        || button >= cg_buttons(cg.display_node[cg.asking], cg.answers, map)) {
        return 0;
    }
    if (cg_fresh_after(cg.display_node[cg.asking], cg.answers)) {
        if (size > 0) {
            out[0] = '\0';            /* G1: the answer's page is a popup of its own, never this one's */
        }
        return 0;
    }
    keep_path = cg.path;
    count = cg.display_count;
    used = cg.display_used;
    jobs = cg.jobs_used;
    picks = cg.pick_count;
    if (cg_take_answer(a, game, map[button])) {
        k = cg.q_display[cg.answers] + 1;
        if (k < cg.display_count) {
            first = ce_result_layout(a);
            memset(&most, 0, sizeof most);
            most.refused = 999;
            cg_display_title(k, shown, sizeof shown);
            cg_compose(&first, shown, cg_display(k), cg.display_villager[k] && cg.job_count[k] > 0 ? &most : NULL,
                       out, size);
            lines = ce_text_lines(out);
        }
    }
    cg.path = keep_path;
    cg.display_count = count;
    cg.display_used = used;
    cg.jobs_used = jobs;
    cg.pick_count = picks;
    return lines;
}

/* The question popup on screen should close at the answer's click (G1: its page is a popup of its own). */
static int cg_answer_closes(int game) {
    return game != 0 && cg_answer_fresh_game == game;
}

/* ce_choice_featured: the subject, the villager the question is about. */
static int cg_featured(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    int r, i;
    if (a == NULL || !cg_prepare(game)) {
        return -1;
    }
    /* The first villager role bound (version 6: the first role may be a stranger, G7) ... */
    for (r = 0; r < cg_g.n_role; ++r) {
        if (cg_role_at(&cg_g, r)[0] == CG_ROLE_VILLAGER && cg_villager(a, r) != NULL) {
            return cg.record[r];
        }
    }
    /* ... else, with no villager in the event, the first living villager the game lists (the later three games'
       question popup shows someone; no roll is taken). */
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *rec = a->record(i);
        if (rec != NULL && a->listed(rec) && !cg_heathen(game, rec)
            && (a->featurable == NULL || a->featurable(rec))) {
            return i;
        }
    }
    return -1;
}

/* ---- Queueing ----------------------------------------------------------------------------------------------- */

static int cg_guardians_on(void);

/* What role `r` needs, in words. */
static void cg_role_words(int game, int r, char *out, int size) {
    const unsigned char *spec = cg_role_at(&cg_g, r);
    char part[96];
    wsprintfA(out, "a %svillager", spec[2] == 1 ? "male " : spec[2] == 2 ? "female " : "");
    if (spec[3] != 0) {
        wsprintfA(part, " of %d or more", (int)spec[3]);
        lstrcatA(out, part);
    }
    if (spec[1] & CG_ROLE_NURSING) {
        lstrcatA(out, ", not carrying or nursing a baby");
    }
    if (spec[1] & CG_ROLE_SPECIAL) {
        const char *who = game == 1 ? "the Golden Child" : game == 3 ? "the Tribal Chief"
                        : game == 5 ? (cg_guardians_on() ? "a chief, the Retired Chief or a puzzle's Isolan"
                                                         : "a chief, the Retired Chief or a puzzle's Heathen") : NULL;
        if (who != NULL) {
            wsprintfA(part, ", not %s", who);
            lstrcatA(out, part);
        }
    }
    if ((spec[1] & CG_ROLE_BELIEVERS) && game == 5) {
        lstrcatA(out, ", a believer");
    }
    if (cg_g.version >= 6) {
        const ce_adapter *a = ce_adapter_for(game);
        if (spec[8] != 0) {
            wsprintfA(part, ", %d or younger", (int)spec[8]);
            lstrcatA(out, part);
        }
        if (cg_u16(spec + 10) != CG_NONE && a != NULL && cg_skills_known(a, cg_s(&cg_g, cg_u16(spec + 10)))) {
            wsprintfA(part, ", %s %d or more", cg_s(&cg_g, cg_u16(spec + 10)), (int)spec[12]);
            if (lstrlenA(out) + lstrlenA(part) < size) {
                lstrcatA(out, part);
            }
        }
        if (spec[9] >= 1 && spec[9] <= 3) {
            static const char *const WHO[4] = { "", ", the Golden Child", ", the Tribal Chief", ", a nursing parent" };
            lstrcatA(out, WHO[spec[9]]);
        }
        if (spec[1] & CG_ROLE_PROTECTED) {
            lstrcatA(out, ", not a protected villager");
        }
    }
}

/* ---- The installed patches (v1.35.97) ----------------------------------------------------------------------

   The patcher writes the ids of the patches it installed into this game -- every fun patch, the game build's own id
   (a "#" line is a note) -- one per line, into "<game folder>\Virtual Villagers Fun Patcher Files\VVFP Installed
   Patches.txt" (src/vv_fun_patcher.py _write_installed_patches), at every patch, so the list always describes the
   installed build (a re-patch rewrites it; an unpatched game has none).  It is read once a run: the patches never
   change while the game runs.  An event's patch id is its short name: the line itself, or the line without its
   "vv<N>_" game prefix in game N ("guardians_of_isola" matches "vv5_guardians_of_isola..."; a build id's "_rewrite"
   ending too). */
#define CG_INSTALLED_LEAF "VVFP Installed Patches.txt"
#define CG_INSTALLED_BYTES 16384
static int cg_installed_state = -1;    /* -1 not read yet, 0 no list (an older patch), 1 read */
static char cg_installed[CG_INSTALLED_BYTES];

static void cg_installed_load(void) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    HANDLE file;
    DWORD got = 0;
    if (cg_installed_state >= 0) {
        return;
    }
    cg_installed_state = 0;
    cg_installed[0] = '\0';
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, CG_INSTALLED_LEAF) == 0) {
        return;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (ReadFile(file, cg_installed, CG_INSTALLED_BYTES - 1, &got, NULL)) {
        cg_installed[got] = '\0';
        cg_installed_state = 1;
    }
    CloseHandle(file);
}

/* Whether the short name `id` names an installed patch of `game` (cg_installed_state 1). */
static int cg_installed_has(int game, const char *id) {
    const char *p = cg_installed;
    int n = lstrlenA(id);
    while (*p != '\0') {
        const char *end = p, *at = p;
        int len;
        while (*end != '\0' && *end != '\n' && *end != '\r') {
            ++end;
        }
        if (*at != '#') {
            if (end - at > 4 && at[0] == 'v' && at[1] == 'v' && at[2] == (char)('0' + game) && at[3] == '_') {
                at += 4;                /* the game's prefix */
            }
            len = (int)(end - at);
            if (len >= n && memcmp(at, id, (size_t)n) == 0
                && (len == n || (len == n + 8 && memcmp(at + n, "_rewrite", 8) == 0))) {
                return 1;
            }
        }
        p = end;
        while (*p == '\n' || *p == '\r') {
            ++p;
        }
    }
    return 0;
}

/* The player's "a man may carry the baby by chance" setting (the patcher writes "# partner_carry_percent=N" in the
   installed patches' list; the owner, 2026-11-16): 0 to 100, 10 when the list has none. */
static int cg_partner_carry_percent(void) {
    static const char KEY[] = "# partner_carry_percent=";
    const char *p;
    int n = lstrlenA(KEY), value = 0, digits = 0;
    cg_installed_load();
    if (cg_installed_state != 1) {
        return 10;
    }
    for (p = cg_installed; *p != '\0'; ++p) {
        if ((p == cg_installed || p[-1] == '\n') && memcmp(p, KEY, (size_t)n) == 0) {
            for (p += n; *p >= '0' && *p <= '9' && digits < 3; ++p, ++digits) {
                value = value * 10 + (*p - '0');
            }
            return digits > 0 && value <= 100 ? value : 10;
        }
    }
    return 10;
}

/* Whether the partner carries this time: the setting's chance (no roll at 0 or 100). */
static int cg_partner_carries(const ce_adapter *a) {
    int percent = cg_partner_carry_percent();
    if (percent <= 0) {
        return 0;
    }
    return percent >= 100 || ce_random_below(a, 100) < percent;
}

static int cg_no_safeguards(int game) {
    cg_installed_load();
    return cg_installed_state == 1 && cg_installed_has(game, "island_events_any_time");
}

/* Whether the patches named by the event are on: the installed patches' list when the patcher wrote one; without
   it (a game patched by an older patcher) only Guardians of Isola's rewrite (New Believers), seen in the game's own
   text as the Faith popup sees it -- which is also asked with the list, as before. */
static unsigned int cg_patches_on(int game) {
    unsigned int on = 0;
    int i;
#ifdef VVFP_TEST
    if (test_graph_patches >= 0) {
        return (unsigned int)test_graph_patches;
    }
#endif
    cg_installed_load();
    for (i = 0; i < cg_g.n_patch; ++i) {
        const char *id = cg_s(&cg_g, cg_u16(cg_g.d + cg_g.o_patch + 2u * (unsigned int)i));
        if ((cg_installed_state == 1 && cg_installed_has(game, id))
            || (game == 5 && lstrcmpA(id, "guardians_of_isola") == 0 && faith_notice_left_the_tribe())) {
            on |= 1u << i;
        }
    }
    return on;
}

/* New Believers with Guardians of Isola's rewrite on (the installed patches' list, or the game's own text as the
   Faith popup sees it): the engine's own words then say "Isolan" for "Heathen" (the owner, 2026-11-14). */
static int cg_guardians_on(void) {
    cg_installed_load();
    return (cg_installed_state == 1 && cg_installed_has(5, "guardians_of_isola")) || faith_notice_left_the_tribe();
}

/* The loaded event's title in `game` (cie-v6-binary.md 18): the first title variant whose condition (game and patch
   conditions only) holds with the patches on now, else the file's own title.  Into cg_g.title, so every later use
   -- the popups, the log, the refusals -- shows it. */
static void cg_choose_title(int game) {
    unsigned int keep = cg.patches;
    int k;
    cg_g.title = cg_g.base_title;
    if (cg_g.tv_count == 0) {
        return;
    }
    cg.patches = cg_patches_on(game);
    for (k = 0; k < cg_g.tv_count; ++k) {
        const unsigned char *v = cg_variant_at(&cg_g, cg_g.tv_first + k);
        if (cg_holds_cond((int)cg_u16(v), game, 0)) {
            cg_g.title = (int)cg_u16(v + 2);
            break;
        }
    }
    cg.patches = keep;
}

/* The roles a refusal planned with their requirements dropped (CG_CAST_PREFER), for the run cg_queue makes. */
static unsigned int cg_plan_relaxed;

/* VERSION 6, STRICT (the rare roll, Pick Island Event): the event's own requirement -- its condition beyond the
   puzzles (the header's `all`, docs/event-collection/cie-v6-binary.md 1) with the roles it will bind, and at least
   `min_eligible` villagers who could take one of its villager roles (an event with no villager role: at least
   `min_eligible` villagers, as cg_population counts them). */
static int cg_eligible_count(const ce_adapter *a, int game, unsigned int needed) {
    int i, n = 0, r;
    if (needed == 0u) {
        return cg_population(game, 0);
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        for (r = 0; r < cg_g.n_role; ++r) {
            if ((needed & (1u << r)) && cg_eligible(a, game, r, i)) {
                ++n;
                break;
            }
        }
    }
    return n;
}

static int cg_requirement_holds(int game, unsigned int needed) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned int keep_bound = cg.bound, keep_patches = cg.patches;
    int keep_drawn = cg.aliases_drawn, holds = 1, k;
    if (a == NULL) {
        return 0;
    }
    if (cg_g.req_cond != (int)CG_NONE) {
        const unsigned char *all = cg_cond_at(&cg_g, cg_g.req_cond);
        cg.bound = needed;
        cg.patches = cg_patches_on(game);
        cg.aliases_drawn = 0;
        memset(cg_visited, 0, sizeof cg_visited);
        for (k = 0; k < all[1] && holds; ++k) {
            int c = (int)cg_u16(all + 2) + k;
            if (cg_cond_at(&cg_g, c)[0] != CGC_PUZZLE
                && !(cg_cond_at(&cg_g, c)[0] == CGC_MIN_POPULATION && cg_ns_cast(game))) {
                holds = cg_holds_cond(c, game, 0);
            }
        }
        cg.bound = keep_bound;
        cg.patches = keep_patches;
        cg.aliases_drawn = keep_drawn;
    }
    if (holds && cg_g.min_eligible > 0 && !cg_ns_cast(game)) {
        holds = cg_eligible_count(a, game, needed) >= cg_g.min_eligible;
    }
    return holds;
}

static void cg_role_words(int game, int r, char *out, int size);

/* Whether condition `i` names a content filter (island_event_filter_*: src/vv_event_content.py) anywhere in it. */
static int cg_cond_names_filter(int i, int depth) {
    const unsigned char *c;
    unsigned int a;
    int k;
    if (i < 0 || i >= cg_g.n_cond || depth > 8) {
        return 0;
    }
    c = cg_cond_at(&cg_g, i);
    a = cg_u16(c + 2);
    switch (c[0]) {
    case CGC_PATCH: {
        const char *id = cg_s(&cg_g, cg_u16(cg_g.d + cg_g.o_patch + 2u * a));
        return lstrlenA(id) > 20 && memcmp(id, "island_event_filter_", 20) == 0;
    }
    case CGC_NOT:
        return cg_cond_names_filter((int)a, depth + 1);
    case CGC_ALL: case CGC_ANY:
        for (k = 0; k < c[1]; ++k) {
            if (cg_cond_names_filter((int)a + k, depth + 1)) {
                return 1;
            }
        }
        return 0;
    default:
        return 0;
    }
}

/* Whether the parts of the event's requirement that name a content filter (the skip src/vv_event_content.py writes)
   hold with the patches on now: a bought event is never kept out by its other requirements, but always by these. */
static int cg_filters_allow(int game) {
    const unsigned char *all;
    unsigned int keep = cg.patches;
    int k, holds = 1;
    if (cg_g.req_cond == (int)CG_NONE) {
        return 1;
    }
    all = cg_cond_at(&cg_g, cg_g.req_cond);
    cg.patches = cg_patches_on(game);
    for (k = 0; k < all[1] && holds; ++k) {
        int c = (int)cg_u16(all + 2) + k;
        if (cg_cond_names_filter(c, 0)) {
            holds = cg_holds_cond(c, game, 0);
        }
    }
    cg.patches = keep;
    return holds;
}

/* What requirement condition `i` asks for, in plain words, into `out` (after "it needs "): the first part that does
   not hold now.  0 when it holds.  (A requirement never holds a villager fact: src/vv_cie_graph.py refuses it; never a
   role's id, a code label the player does not see.) */
static int cg_cond_words(int i, int game, int depth, char *out, int cap) {
    const unsigned char *c;
    unsigned int a;
    char part[200];
    int k;
    if (i == (int)CG_NONE || i < 0 || i >= cg_g.n_cond || depth > 8 || cg_holds_cond(i, game, 0)) {
        return 0;
    }
    c = cg_cond_at(&cg_g, i);
    a = cg_u16(c + 2);
    part[0] = '\0';
    switch (c[0]) {
    case CGC_MIN_POPULATION:
        wsprintfA(part, "at least %d %s", (int)a, game == 5 ? "believers" : "villagers");
        break;
    case CGC_MIN_CHILDREN:
        wsprintfA(part, "at least %d %s under 14", (int)a, a == 1u ? "child" : "children");
        break;
    case CGC_SPECIAL_PRESENT:
        lstrcpynA(part, a == 1u ? "the Golden Child in the village" : "the Tribal Chief in the village", sizeof part);
        break;
    case CGC_GAME:
        lstrcpynA(part, "another game: it is not made for this one", sizeof part);
        break;
    case CGC_PATCH:
        lstrcpynA(part, "a patch that is not installed in this game", sizeof part);
        break;
    case CGC_PUZZLE:
        wsprintfA(part, "%s solved", cg_s(&cg_g, a));
        break;
    case CGC_ALL:
        for (k = 0; k < c[1]; ++k) {
            if (cg_cond_words((int)a + k, game, depth + 1, out, cap)) {
                return 1;
            }
        }
        break;
    case CGC_ANY:
        for (k = 0; k < c[1]; ++k) {
            char one[200];
            if (cg_cond_words((int)a + k, game, depth + 1, one, sizeof one)) {
                if (part[0] != '\0' && lstrlenA(part) + lstrlenA(one) + 5 < (int)sizeof part) {
                    lstrcatA(part, " or ");
                    lstrcatA(part, one);
                } else if (part[0] == '\0') {
                    lstrcpynA(part, one, sizeof part);
                }
            }
        }
        break;
    case CGC_NOT: {
        const unsigned char *n = cg_cond_at(&cg_g, (int)a);
        unsigned int na = cg_u16(n + 2);
        if (n[0] == CGC_MIN_POPULATION) {
            wsprintfA(part, "fewer than %d %s", (int)na, game == 5 ? "believers" : "villagers");
        } else if (n[0] == CGC_MIN_CHILDREN) {
            wsprintfA(part, "fewer than %d children under 14", (int)na);
        } else if (n[0] == CGC_SPECIAL_PRESENT) {
            lstrcpynA(part, na == 1u ? "no Golden Child in the village" : "no Tribal Chief in the village",
                      sizeof part);
        } else if (cg_cond_names_filter((int)a, 0)) {
            lstrcpynA(part, "the island event content filters to allow it", sizeof part);
        } else if (n[0] == CGC_PATCH) {
            lstrcpynA(part, "a patch installed in this game to be taken off", sizeof part);
        } else if (n[0] == CGC_PUZZLE) {
            wsprintfA(part, "%s not solved yet", cg_s(&cg_g, na));
        }
        break;
    }
    default:
        break;
    }
    if (part[0] == '\0') {
        lstrcpynA(part, "the village to change first (a condition of the event does not hold now)", sizeof part);
    }
    lstrcpynA(out, part, cap);
    return 1;
}

/* Why the event's own requirement (cg_requirement_holds) fails now, in plain words, into `out` (360 bytes): its
   condition's first part that does not hold, else a needed role nobody can be, else too few villagers who could
   take part. */
static void cg_requirement_words(int game, unsigned int needed, char *out) {
    const ce_adapter *a = ce_adapter_for(game);
    unsigned int keep_bound = cg.bound, keep_patches = cg.patches;
    int keep_drawn = cg.aliases_drawn, said = 0, k, r, i;
    char words[CE_TITLE_BYTES + 24];
    lstrcpynA(words, cg_readable(&cg_g), sizeof words);
    if (a == NULL) {
        wsprintfA(out, "\"%s\" can not happen in this game.", words);
        return;
    }
    if (cg_g.req_cond != (int)CG_NONE) {
        const unsigned char *all = cg_cond_at(&cg_g, cg_g.req_cond);
        char part[220];
        cg.bound = needed;
        cg.patches = cg_patches_on(game);
        cg.aliases_drawn = 0;
        memset(cg_visited, 0, sizeof cg_visited);
        for (k = 0; k < all[1] && !said; ++k) {
            int c = (int)cg_u16(all + 2) + k;
            if (cg_cond_at(&cg_g, c)[0] != CGC_PUZZLE && cg_cond_words(c, game, 0, part, sizeof part)) {
                wsprintfA(out, "\"%s\" can not happen in this village right now: it needs %s.", words, part);
                said = 1;
            }
        }
        cg.bound = keep_bound;
        cg.patches = keep_patches;
        cg.aliases_drawn = keep_drawn;
        if (said) {
            return;
        }
    }
    if (needed == 0u) {
        wsprintfA(out, "\"%s\" can not happen in this village right now: it needs at least %d %s.", words,
                  (int)cg_g.min_eligible, game == 5 ? "believers" : (cg_g.min_eligible == 1 ? "villager" : "villagers"));
        return;
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        if (!(needed & (1u << r))) {
            continue;
        }
        for (i = 0; i < a->record_count && !cg_eligible(a, game, r, i); ++i) {
        }
        if (i >= a->record_count) {
            char one[200];
            cg_role_words(game, r, one, sizeof one);
            wsprintfA(out, "Nobody in the village can take part now: it needs %s.", one);
            return;
        }
    }
    {
        /* Each different kind of villager the roles take, once. */
        char kinds[200], one[200];
        int n = cg_eligible_count(a, game, needed);
        kinds[0] = '\0';
        for (r = 0; r < cg_g.n_role; ++r) {
            if (!(needed & (1u << r))) {
                continue;
            }
            cg_role_words(game, r, one, sizeof one);
            if (kinds[0] == '\0') {
                lstrcpynA(kinds, one, sizeof kinds);
            } else {
                const char *at = kinds;
                int found = 0, len = lstrlenA(one);
                for (; lstrlenA(at) >= len && !found; ++at) {
                    found = memcmp(at, one, (size_t)len) == 0 && (at[len] == '\0' || at[len] == ';');
                }
                if (!found && lstrlenA(kinds) + len + 6 < (int)sizeof kinds) {
                    lstrcatA(kinds, "; or ");
                    lstrcatA(kinds, one);
                }
            }
        }
        wsprintfA(out, "Too few villagers can take part in \"%s\" now: it needs %d, each %s; %d can.", words,
                  (int)cg_g.min_eligible, kinds, n);
    }
}

/* The roles in `needed` can not all be filled at once: one different villager each. */
static const char *cg_too_few_roles(unsigned int needed) {
    static char reason[200];
    int n = 0;
    for (; needed != 0u; needed &= needed - 1u) {
        ++n;
    }
    wsprintfA(reason, "The village does not have enough different villagers for the event's roles now: it needs %d, "
              "one for each role. Nothing has been queued.", n);
    return reason;
}

/* Why the loaded event cannot be queued in `game` now, or NULL; `planned` the roles it will bind. */
static const char *cg_refusal(int game, unsigned int *planned) {
    static char reason[400];
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char used[CE_MAX_RECORDS];
    unsigned int needed;
    int question, r, i;
    if (a == NULL) {
        return "Custom Island Event is not available in this game.";
    }
    cg_choose_title(game);
    if (!(cg_g.games & (1u << (game - 1)))) {
        wsprintfA(reason, "\"%s\" is not made for %s.", cg_readable(&cg_g), a->game_name);
        return reason;
    }
    if (cg_g.long_text && !cg_one_popup()) {
        /* A text longer than the popups hold without scrollbars (the owner, 2026-11-16: practically unlimited text
           needs Scrolling Popups). */
        wsprintfA(reason, "\"%s\" has text longer than this game's popups hold without the Scrolling Popups patch. "
                  "Nothing has been queued.", cg_readable(&cg_g));
        return reason;
    }
    question = cg_node_at(&cg_g, cg_g.start)[0] == CG_QUESTION;
    if (question && !ce_choice_available(a)) {
        return "This game can not ask a question with two choices yet.";
    }
    ce_refusal_for_choice = question;
    {
        const char *why = a->arm_refusal();
        ce_refusal_for_choice = 0;
        if (why != NULL) {
            return why;
        }
    }
    if (cg_g.req_cond != (int)CG_NONE) {
        /* Version 3: "only after a puzzle is solved" -- every puzzle the event lists for this game. */
        const unsigned char *all = cg_cond_at(&cg_g, cg_g.req_cond);
        int k;
        for (k = 0; k < all[1]; ++k) {
            const unsigned char *c = cg_cond_at(&cg_g, (int)cg_u16(all + 2) + k);
            if (c[0] == CGC_PUZZLE && (int)cg_u16(c + 4) == game && !cg_puzzle_solved(game, cg_s(&cg_g, cg_u16(c + 2)))) {
                wsprintfA(reason, "\"%s\" can only happen once %s is solved. Nothing has been queued.",
                          cg_readable(&cg_g), cg_s(&cg_g, cg_u16(c + 2)));
                return reason;
            }
        }
    }
    memset(used, 0, sizeof used);
    cg_try_reset();
    needed = cg_needed();
    cg_relax_mask = 0;
    if (cg_g.version >= 6 && cg_cast_now == CG_CAST_STRICT && !cg_requirement_holds(game, needed)) {
        static char why[360];
        cg_requirement_words(game, needed, why);
        wsprintfA(reason, "%s Nothing has been queued.", why);
        return reason;
    }
    if (cg_g.version >= 6 && cg_cast_now != CG_CAST_STRICT && !cg_filters_allow(game)) {
        /* Bought too: the island event content filters the player ticked keep it out (src/vv_event_content.py). */
        wsprintfA(reason, "\"%s\" is kept out by the island event content filters. Nothing has been queued.",
                  cg_readable(&cg_g));
        return reason;
    }
    if (cg_g.version >= 6 && cg_cast_now == CG_CAST_PREFER) {
        /* Bought: a requirement nobody meets is dropped, never the purchase (only "no villager at all"). */
        if (!cg_plan_cast(a, game, needed, used)) {
            return cg_too_few_roles(needed);
        }
    }
    for (r = 0; r < cg_g.n_role; ++r) {
        if (!(needed & (1u << r))) {
            continue;
        }
        for (i = 0; i < a->record_count && !cg_eligible(a, game, r, i); ++i) {
        }
        if (i >= a->record_count) {
            char words[200];
            cg_role_words(game, r, words, sizeof words);
            wsprintfA(reason, "Nobody in the village can take part now: it needs %s. Nothing has been queued.",
                      words);
            return reason;
        }
    }
    if (!cg_matchable(a, game, needed, used)) {
        if (cg_has_gaps()) {
            /* Version 3: no villagers fit the roles together (an age gap); version 6: or a kinship relation. */
            int q;
            for (q = 0; q < cg_g.n_role; ++q) {
                static const char *const KIN[9] = { "", "spouses", "a parent and child", "a parent and child",
                                                    "siblings", "a grandparent and grandchild",
                                                    "a grandparent and grandchild",
                                                    "an aunt or uncle and a niece or nephew", "cousins" };
                int other = -1, kind = cg_relation(q, &other);
                if (kind != 0 && (needed & (1u << q)) && (needed & (1u << other))) {
                    wsprintfA(reason, "No villagers in the village can take part together now: it needs two who are "
                              "%s. Nothing has been queued.", KIN[kind]);
                    return reason;
                }
            }
            for (q = 0; q < cg_g.n_role; ++q) {
                const unsigned char *qs = cg_role_at(&cg_g, q);
                if (qs[6] != 0 && (needed & (1u << q)) && (needed & (1u << (qs[6] - 1)))) {
                    wsprintfA(reason, "No two villagers in the village can take part together now: they must be "
                              "at most %d years apart. Nothing has been queued.", (int)qs[7]);
                    return reason;
                }
            }
        }
        return cg_too_few_roles(needed);
    }
    *planned = needed;
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        cg_try_reset();
        if (spec[0] == 0 && (spec[1] & CG_ROLE_OPTIONAL) && cg_matchable(a, game, *planned | (1u << r), used)) {
            *planned |= 1u << r;       /* an optional role the village can fill now */
        }
    }
    cg_plan_relaxed = cg_relax_mask;
    return NULL;
}

/* A role that may be a special villager: the purchase warns before it is made. */
static const char *cg_risk(int game) {
    int r;
    for (r = 0; r < cg_g.n_role; ++r) {
        const unsigned char *spec = cg_role_at(&cg_g, r);
        if (spec[0] == 0 && !(spec[1] & CG_ROLE_SPECIAL) && (game == 1 || game == 3 || game == 5)) {
            return game == 1 ? "This event may choose the Golden Child, whom the game's puzzles need."
                 : game == 3 ? "This event may choose the Tribal Chief."
                 : cg_guardians_on() ? "This event may choose a chief, the Retired Chief or a puzzle's Isolan, whom "
                                       "the game's story needs."
                             : "This event may choose a chief, the Retired Chief or a puzzle's Heathen, whom the "
                               "game's story needs.";
        }
    }
    return NULL;
}

static int cg_origin_now = CG_ORIGIN_PURCHASE;   /* the next cg_queue's origin */

static int cg_origin_now_get(void) {
    return cg_origin_now;
}

/* Queue the loaded event in `game` (the checks made: cg_refusal), its first display made due as the purchase does.
   1 on success. */
static int cg_queue(int game, unsigned int planned, int due) {
    cg_newest_reset();
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL) {
        return 0;
    }
    memset(&cg, 0, sizeof cg);
    cg.game = game;
    cg.slot = story_current_slot(game);
    cg.question = cg_node_at(&cg_g, cg_g.start)[0] == CG_QUESTION;
    cg.planned = planned;
    cg.patches = cg_patches_on(game);
    cg.choice = -1;
    cg.asking = -1;
    cg.origin = cg_origin_now;
    cg.cast_mode = cg_cast_now;
    cg.relaxed = cg_plan_relaxed;
    {
        int r;
        for (r = 0; r < CG_MAX_ROLES; ++r) {
            cg.alias[r] = -1;
        }
    }
    cg_choose_title(game);
    lstrcpynA(cg.title, cg_readable(&cg_g), sizeof cg.title);
    if (cg.question) {
        static cg_pages pages;
        unsigned int keep = cg.bound;
        cg.bound = planned;            /* the conditions see the roles it will bind */
        if (cg_g.version >= 6) {
            /* The start question's words are laid out now (its pages before its popup): its aliases and its pools
               are drawn here, the walk's first draws (the binding's rolls come after them, at the delivery). */
            cg_draw_aliases(a, planned);
            memset(cg_visited, 0, sizeof cg_visited);
            cg_visit(cg_g.start);
            cg_node_pools(a, game, cg_g.start);
            cg.start_picks = cg.pick_count;
        }
        cg_question_pages(a, game, &pages);
        cg.bound = keep;
        cg.pre_pages = pages.count > 0 ? pages.count - 1 : 0;
    }
    cg.phase = CG_QUEUED;
    cg_village = story_village_now(game);
    cg_purchasing = 1;                 /* not busy while the purchase checks what waits */
    if (!cg_arm(game, due)) {
        cg_purchasing = 0;
        memset(&cg, 0, sizeof cg);
        cg_display_armed = 0;
        return 0;
    }
    cg_purchasing = 0;
    cg.when = sq_clock();
    cg_dirty = 1;
    return 1;
}

/* Every frame (VvfpStoryInstall): the next display armed once the slot is free; a run of another village set
   aside (its file waits for it). */
static void cg_tick(int game) {
    if (cg.phase == CG_IDLE || cg.phase == CG_DONE) {
        return;
    }
    if (cg.game == game && !story_village_is(game, &cg_village)) {
        cg.phase = CG_IDLE;            /* another village: memory only, the file stays its village's */
        cg_display_armed = 0;
        cg_dirty = 0;
        return;
    }
    if (cg_display_armed && !(ce_armed && ce_armed_event.game == cg.game)) {
        cg_display_armed = 0;          /* dropped (another village, a reset) */
    }
    if (cg.game != game || !cg_wants_display() || !cg_slot_free(game)) {
        return;
    }
    if (cg.phase == CG_QUEUED && !cg_feasible(game)) {
        return;                        /* still waiting for the roles */
    }
    (void)cg_arm(game, 1);
}

/* ---- The run's file ---------------------------------------------------------------------------------------- */

#define CG_FILE_MAGIC 0x31474356u      /* 'V' 'C' 'G' '1' */
#define CG_FILE_VERSION 6u                 /* 2: the run keeps its path and every question's answers; 3: and a
                                              question's third and fourth answers (cg_state.seg_more); 4 (format
                                              version 6): answers five to seven, the pool picks, the aliases, each
                                              question's buttons, the origin and the cast; 5: the displays' words
                                              in CG_DISPLAY_BYTES (practically unlimited text), not 49,152; 6: the
                                              partner-carry swaps (cg_state.carry_swapped) and each display's words'
                                              sex (female_at, cie-v6-binary.md 35) */
/* Versions 2 to 4 kept CG_DISPLAY_BYTES_V4 bytes of displays: every field after them sits that much nearer. */
#define CG_DISPLAY_GROWTH ((unsigned int)(CG_DISPLAY_BYTES - CG_DISPLAY_BYTES_V4))
#define CG_ENTRY_GROWTH ((unsigned int)(CG_ENTRY_BYTES - CG_ENTRY_BYTES_V4))
#define CG_FILE_GROWTH (CG_DISPLAY_GROWTH + CG_ENTRY_GROWTH)
#define CG_FILE_V2_STATE ((unsigned int)offsetof(cg_state, seg_more) - CG_FILE_GROWTH)   /* a version 2 file's state
                                                                                           bytes */
#define CG_FILE_V3_STATE ((unsigned int)offsetof(cg_state, seg_v6) - CG_FILE_GROWTH)     /* a version 3 file's */
#define CG_FILE_V5_STATE ((unsigned int)offsetof(cg_state, carry_swapped))               /* a version 5 file's */

#define CG_FILE_V4_STATE (CG_FILE_V5_STATE - CG_FILE_GROWTH)                             /* a version 4 file's */

typedef struct {
    unsigned int magic;
    unsigned int version;
    unsigned int game;
    unsigned int slot;
    unsigned int state_bytes;          /* sizeof(cg_state) */
    unsigned int graph_bytes;          /* the .cieg after the state */
    unsigned int roster[256];
} cg_file_head;

static cg_file_head cg_head;
static unsigned char *cg_read_buf;
static unsigned int cg_read_cap;
static cg_state cg_read_state;

/* The state's bytes a run file of the header's version holds: version 4 the whole state, version 3 everything before
   version 4's fields, version 2 everything before the third and fourth answers' segments (read with what it lacks
   empty: cg_file_upgrade); 0 for any other. */
static unsigned int cg_file_state_bytes(void) {
    return cg_head.version == CG_FILE_VERSION ? (unsigned int)sizeof(cg_state)
         : cg_head.version == 5u ? CG_FILE_V5_STATE
         : cg_head.version == 4u ? CG_FILE_V4_STATE
         : cg_head.version == 3u ? CG_FILE_V3_STATE
         : cg_head.version == 2u ? CG_FILE_V2_STATE : 0u;
}

/* A state read from a file before version 5: its fields moved to their places now -- the displays' words grew by
   CG_DISPLAY_GROWTH and the log entry by CG_ENTRY_GROWTH -- the room they gained empty. */
static void cg_file_widen(cg_state *st) {
    unsigned char *b = (unsigned char *)st;
    unsigned int words = (unsigned int)offsetof(cg_state, displays), kind = (unsigned int)offsetof(cg_state, display_kind);
    unsigned int entry = (unsigned int)offsetof(cg_state, entry), after = entry + CG_ENTRY_BYTES;
    unsigned int bytes = cg_file_state_bytes();
    unsigned int old_after = after - CG_FILE_GROWTH, old_kind = kind - CG_DISPLAY_GROWTH;
    if (cg_head.version >= 5u || bytes < old_after || kind != words + CG_DISPLAY_BYTES
        || (unsigned int)offsetof(cg_state, seg_more) != after) {
        return;
    }
    /* from the far end: what follows the entry, then the displays' kinds up to the old entry's end */
    memmove(b + after, b + old_after, bytes - old_after);
    memmove(b + kind, b + old_kind, (entry + CG_ENTRY_BYTES_V4) - kind);
    memset(b + words + CG_DISPLAY_BYTES_V4, 0, CG_DISPLAY_GROWTH);
    memset(b + entry + CG_ENTRY_BYTES_V4, 0, CG_ENTRY_GROWTH);
}

/* A run read from an older file: what it lacks as a run of its own version had it (no alias drawn, every choice
   shown as its version shows them, the cast strict).  Version 4 holds them all (5 only widened the words; 6 added
   carry_swapped, read 0 from an older file: nobody swapped, and female_at). */

static void cg_file_upgrade(cg_state *st) {
    int r, k;
    if (cg_head.version >= CG_FILE_VERSION) {
        return;
    }
    for (k = 0; k < CG_MAX_DISPLAYS; ++k) {
        for (r = 0; r < CG_MAX_ROLES; ++r) {
            st->female_at[k][r] = (unsigned char)(st->female[r] != 0);   /* 35: before version 6 */
        }
    }
    if (cg_head.version >= 4u) {
        return;                        /* version 4's fields are there (a version 4 or 5 file: carry_swapped read 0) */
    }
    for (r = 0; r < CG_MAX_ROLES; ++r) {
        st->alias[r] = -1;
    }
    st->aliases_drawn = 1;
    st->origin = CG_ORIGIN_PURCHASE;
    st->cast_mode = CG_CAST_STRICT;
}

static int cg_file_state_ok(void) {
    return cg_file_state_bytes() != 0u && cg_head.state_bytes == cg_file_state_bytes();
}

#ifdef VVFP_TEST
static unsigned char cg_test_file[sizeof(cg_file_head) + sizeof(cg_state) + CG_SHIPPED_FILE];
static unsigned int cg_test_size;

static int cg_file_read(int game, int slot) {
    (void)game;
    (void)slot;
    unsigned int state;
    if (cg_test_size < sizeof cg_head) {
        return 0;
    }
    memcpy(&cg_head, cg_test_file, sizeof cg_head);
    state = cg_file_state_bytes();
    memset(&cg_read_state, 0, sizeof cg_read_state);
    if (state == 0u || cg_head.graph_bytes > CG_SHIPPED_FILE
        || cg_test_size != sizeof cg_head + state + cg_head.graph_bytes
        || cg_grow(&cg_read_buf, &cg_read_cap, cg_head.graph_bytes ? cg_head.graph_bytes : 1u) == NULL) {
        return 0;
    }
    memcpy(&cg_read_state, cg_test_file + sizeof cg_head, state);
    memcpy(cg_read_buf, cg_test_file + sizeof cg_head + state, cg_head.graph_bytes);
    cg_file_widen(&cg_read_state);
    return 1;
}

static int cg_file_write(int game, int slot) {
    (void)game;
    (void)slot;
    if (cg_bytes_size > CG_SHIPPED_FILE) {
        return 0;
    }
    memcpy(cg_test_file, &cg_head, sizeof cg_head);
    memcpy(cg_test_file + sizeof cg_head, &cg, sizeof cg);
    memcpy(cg_test_file + sizeof cg_head + sizeof cg, cg_bytes, cg_bytes_size);
    cg_test_size = (unsigned int)(sizeof cg_head + sizeof cg) + cg_bytes_size;
    return 1;
}

static void cg_file_remove(int game, int slot) {
    (void)game;
    (void)slot;
    cg_test_size = 0;
}
#else
static int cg_file_read(int game, int slot) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0, more = 0, graph = 0;
    BOOL ok;
    if (!vv_paid_named_path(game, slot, "Story Purchases Graph", path, 0)) {
        return 0;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    memset(&cg_read_state, 0, sizeof cg_read_state);
    ok = ReadFile(h, &cg_head, sizeof cg_head, &got, NULL) && got == sizeof cg_head && cg_file_state_bytes() != 0u
        && ReadFile(h, &cg_read_state, cg_file_state_bytes(), &more, NULL) && more == cg_file_state_bytes()
        && cg_head.graph_bytes <= CG_MAX_FILE
        && cg_grow(&cg_read_buf, &cg_read_cap, cg_head.graph_bytes ? cg_head.graph_bytes : 1u) != NULL
        && ReadFile(h, cg_read_buf, cg_head.graph_bytes, &graph, NULL) && graph == cg_head.graph_bytes;
    CloseHandle(h);
    if (ok) {
        cg_file_widen(&cg_read_state);
    }
    return ok ? 1 : 0;
}

static int cg_file_write(int game, int slot) {
    char path[MAX_PATH];
    const void *parts[3];
    DWORD sizes[3];
    if (!vv_paid_named_path(game, slot, "Story Purchases Graph", path, 1)) {
        return 0;
    }
    parts[0] = &cg_head;
    sizes[0] = sizeof cg_head;
    parts[1] = &cg;
    sizes[1] = sizeof cg;
    parts[2] = cg_bytes;
    sizes[2] = cg_bytes_size;
    return vv_paid_write_parts(path, parts, sizes, 3);
}

static void cg_file_remove(int game, int slot) {
    char path[MAX_PATH];
    if (vv_paid_named_path(game, slot, "Story Purchases Graph", path, 0)) {
        DeleteFileA(path);
    }
}
#endif

/* A village came on screen (story_queue.inc sq_sync, the first time it is seen, on the tick or where the game
   asks for an armed event): a run of another village is set aside, and this slot's run put back when the save
   paid for it. */
static void cg_village_seen(int game, int slot, const unsigned int *roster) {
    unsigned __int64 saved = 0;
    static cg_graph check;
    if (cg.phase != CG_IDLE && !(cg.game == game && story_village_is(game, &cg_village))) {
        cg.phase = CG_IDLE;
        cg_display_armed = 0;
        cg_dirty = 0;
    }
    if (cg.phase != CG_IDLE || !cg_file_read(game, slot)) {
        return;
    }
    if (cg_head.magic != CG_FILE_MAGIC || !cg_file_state_ok() || cg_head.game != (unsigned int)game
        || cg_head.slot != (unsigned int)slot
        || cg_read_state.game != game || cg_read_state.phase == CG_IDLE
        || !cg_load(&check, cg_read_buf, cg_head.graph_bytes) || !sq_same_village(cg_head.roster, roster)) {
        return;
    }
    if (!sq_save_time(game, slot, &saved) || cg_read_state.when > saved) {
        cg_file_remove(game, slot);    /* newer than the save: the save never held it */
        return;
    }
    cg_file_upgrade(&cg_read_state);
    if (!cg_bytes_room(cg_head.graph_bytes)) {
        return;
    }
    memcpy(cg_bytes, cg_read_buf, cg_head.graph_bytes);
    cg_bytes_size = cg_head.graph_bytes;
    cg_g = check;                      /* checked above: the same bytes, now in the run's own buffer */
    cg_g.d = cg_bytes;
    cg = cg_read_state;
    {
        /* 35: the word-change notes belong to the run that made them (process-wide, not saved): a run loaded from
           a file starts with none, so another save slot's run never lends its words here (Codex, #787). */
        int r;
        for (r = 0; r < CG_MAX_ROLES; ++r) {
            cg_late_at[r] = 0;
        }
    }
    cg_choose_title(game);             /* 18: the title variant in force, as when it was queued */
    cg_village = story_village_now(game);
    cg_display_armed = 0;
    {
        /* EXACTLY ONCE.  The save holds the effects of every page made before it, and none after: the pages from
           the first whose effects the save lacks are shown again (their effects made then), the roles as they were
           just before that page.  A question whose answer the save lacks is asked again (the same histories). */
        int k, rewind = -1;
        int shown = cg.phase == CG_DONE ? cg.display_count : cg.display_next;
        for (k = 0; k < shown && k < CG_MAX_DISPLAYS; ++k) {
            if (cg.applied_when[k] != 0 && cg.applied_when[k] > saved) {
                rewind = k;
                break;
            }
        }
        if (rewind >= 0) {
            /* The first page the save lacks.  Is it an answer's first page?  Then that answer is not in the save
               either: the question is asked again.  Every question answered after it is taken back too (its pages
               are laid out again from its answer when it is answered again: the same histories). */
            int again = cg.display_kind[rewind] == CGD_RESULT ? rewind - 1 : -1;
            int qi;
            cg.gone = cg.gone_at[rewind];
            memcpy(cg.identity, cg.identity_at[rewind], sizeof cg.identity);
            {
                int r;
                for (r = 0; r < CG_MAX_ROLES; ++r) {
                    cg.female[r] = cg.female_at[rewind][r];   /* 35: the words as the page first read them */
                }
            }
            for (qi = 0; qi < cg.answers && cg.q_display[qi] < (again >= 0 ? again : rewind); ++qi) {
            }
            /* The entry continues from that page: its own lines are taken back, made again as it is shown (or,
               for a question asked again, from before its "Choice:" line). */
            cg.entry_len = again >= 0 && qi < cg.answers ? cg.q_entry[qi] : cg.entry_at[rewind];
            if (cg.entry_len == 0) {
                cg.entry_head = 0;
            }
            cg.entry[cg.entry_len] = '\0';
            for (k = rewind; k < cg.display_count; ++k) {
                cg.applied_when[k] = 0;
                cg.sent_len[k] = 0;
            }
            if (qi < cg.answers) {
                cg_displays_cut(cg.q_display[qi] + 1);
                cg.path.nodes = cg.q_path[qi];
                cg.path.fx = cg.q_fx[qi];
                cg.pick_count = cg.q_picks[qi];
                cg.answers = qi;
            }
            if (again >= 0 && cg.display_kind[again] == CGD_QUESTION) {
                cg.phase = CG_ASKED;
                cg.asking = again;
                cg.display_next = again + 1;
                cg.choice = -1;
            } else {
                cg.phase = CG_CHAIN;
                cg.display_next = rewind;
            }
        } else if (cg.phase == CG_DONE) {
            memset(&cg, 0, sizeof cg);     /* over, and the save holds it all */
            cg_file_remove(game, slot);
            return;
        }
    }

    {
        /* The log is told what of the entry this save already holds: the entry as it was handed over at the last
           page before the save, so the next save continues that same entry (append_event_entry). */
        int k, disk = 0;
        for (k = 0; k < cg.display_count && k < CG_MAX_DISPLAYS; ++k) {
            if (cg.sent_len[k] > disk) {
                disk = cg.sent_len[k];
            }
        }
        if (cg.entry_head > 0) {
            cg_log_send(game, disk, 0);
        }
    }
    if (!ce_armed && !ce_asked) {
        /* The display due at the quit, again: the save's timer is due for the first one; every later one is made
           due now (its notice may have been armed after the save). */
        if (cg_arm(game, 0) && cg.phase != CG_QUEUED) {
#ifndef VVFP_TEST
            if (!GAMES[game].island_pending()) {
                (void)GAMES[game].arm();
            }
#endif
        }
    }
}

/* The tick's write (story_queue.inc sq_sync): the run's file kept what the run is, deleted when it is over. */
static void cg_flush_file(int game, int slot, const unsigned int *roster) {
    if (cg.game != game || cg.slot != slot) {
        return;
    }
    if (cg.phase == CG_DONE) {
        /* Over: the file goes once a save holds every page's effects. */
        unsigned __int64 saved = 0, last = 0;
        int k;
        for (k = 0; k < cg.display_count; ++k) {
            if (cg.applied_when[k] > last) {
                last = cg.applied_when[k];
            }
        }
        if (sq_save_time(game, slot, &saved) && saved >= last) {
            cg.phase = CG_IDLE;
            cg_dirty = 1;
        }
    }
    if (!cg_dirty) {
        return;
    }
    cg_dirty = 0;
    if (cg.phase == CG_IDLE) {
        cg_file_remove(game, slot);
        return;
    }
    memset(&cg_head, 0, sizeof cg_head);
    cg_head.magic = CG_FILE_MAGIC;
    cg_head.version = CG_FILE_VERSION;
    cg_head.game = (unsigned int)game;
    cg_head.slot = (unsigned int)slot;
    cg_head.state_bytes = sizeof(cg_state);
    cg_head.graph_bytes = cg_bytes_size;
    memcpy(cg_head.roster, roster, sizeof cg_head.roster);
    if (!cg_file_write(game, slot)) {
        cg_dirty = 1;
    }
}

/* Start Over or a deleted tribe in `slot`: the run was that village's. */
static void cg_village_reset(int game, int slot) {
    if (game >= 1 && game <= 5 && slot >= 1 && slot <= 5) {
        cg_file_remove(game, slot);
    }
    if (cg.game == game && cg.slot == slot) {
        memset(&cg, 0, sizeof cg);
        cg_display_armed = 0;
        cg_dirty = 0;
    }
}

/* ---- The library (the in-game "From the library..." picker) ----------------------------------------------- */

#define CG_LIBRARY_MAX STORY_TABLE_LIMIT             /* the player's library and the Isola Grand Event Collection's group (its events and
                                           its Living Event Engine rows: about 380 in a game) */
enum { IDD_CE_LIBRARY = 312, IDC_LB_LIST = 3801, IDC_LB_NOTE = 3802 };

static struct {
    int game;
    int count;
    int chosen;
    int cap;                            /* entries the two arrays hold (cg_lib_room) */
    char (*path)[MAX_PATH];
    char (*label)[320];                 /* a living row's label carries its sentence */
    char problems[1600];
} cg_lib;

/* Room for one more library entry (the arrays grown as needed, up to CG_LIBRARY_MAX); 1 when there is. */
static int cg_lib_room(void) {
    int cap = cg_lib.cap, c1 = cg_lib.cap;
    if (cg_lib.count < cg_lib.cap) {
        return 1;
    }
    if (!story_grow((void **)&cg_lib.path, &cap, cg_lib.count + 1, MAX_PATH)
        || !story_grow((void **)&cg_lib.label, &c1, cg_lib.count + 1, 320)) {
        return 0;
    }
    cg_lib.cap = cap;
    return 1;
}

static cg_graph cg_lib_graph;
static unsigned char *cg_lib_bytes;
static unsigned int cg_lib_cap;

static int cg_read_whole(const char *path, unsigned char *buf, unsigned int cap, unsigned int *size) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0, high = 0, length;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    length = GetFileSize(h, &high);
    ok = high == 0 && length != INVALID_FILE_SIZE && length <= cap && ReadFile(h, buf, length, &got, NULL) && got == length;
    CloseHandle(h);
    *size = got;
    return ok;
}

/* A file read whole into *buf, grown to its size (at most CG_MAX_FILE). */
static int cg_read_grow(const char *path, unsigned char **buf, unsigned int *cap, unsigned int *size) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0, high = 0, length;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    length = GetFileSize(h, &high);
    ok = high == 0 && length != INVALID_FILE_SIZE && length <= CG_MAX_FILE
         && cg_grow(buf, cap, length ? length : 1u) != NULL && ReadFile(h, *buf, length, &got, NULL) && got == length;
    CloseHandle(h);
    *size = got;
    return ok;
}

/* "<save folder>\Virtual Villagers Fun Patcher\Custom Island Events" (src/vv_cie_graph.py LIBRARY_FOLDER). */
static int cg_library_folder(char *out) {
    if (!vv_save_folder(out, 160)) {
        return 0;
    }
    lstrcatA(out, "\\Virtual Villagers Fun Patcher\\Custom Island Events");
    return 1;
}

static void cg_library_note(const char *file, const char *why) {
    char line[MAX_PATH + 200];
    wsprintfA(line, "%s: %s\r\n", file, why);
    if (lstrlenA(cg_lib.problems) + lstrlenA(line) < (int)sizeof cg_lib.problems) {
        lstrcatA(cg_lib.problems, line);
    }
}

/* Every .cieg of the library made for `game`, with its .json beside it and no older than it (the patcher writes
   both at each save), read and checked; the others are named with the reason. */
static void cg_library_scan(int game) {
    char folder[MAX_PATH], pattern[MAX_PATH], path[MAX_PATH], json[MAX_PATH];
    WIN32_FIND_DATAA found;
    WIN32_FILE_ATTRIBUTE_DATA info;
    HANDLE find;
    memset(&cg_lib, 0, sizeof cg_lib);
    cg_lib.game = game;
    cg_lib.chosen = -1;
    if (!cg_library_folder(folder)) {
        sc_library_add(game);
        return;
    }
    wsprintfA(pattern, "%s\\*.cieg", folder);
    find = FindFirstFileA(pattern, &found);
    if (find == INVALID_HANDLE_VALUE) {
        sc_library_add(game);
        return;
    }
    do {
        unsigned int size = 0;
        int n;
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            continue;
        }
        if (lstrlenA(folder) + lstrlenA(found.cFileName) + 8 >= MAX_PATH) {
            continue;
        }
        wsprintfA(path, "%s\\%s", folder, found.cFileName);
        lstrcpyA(json, path);
        n = lstrlenA(json);
        lstrcpyA(json + n - 5, ".json");
        if (!GetFileAttributesExA(json, GetFileExInfoStandard, &info)) {
            cg_library_note(found.cFileName, "its .json is missing: save it again in the patcher");
            continue;
        }
        if (CompareFileTime(&info.ftLastWriteTime, &found.ftLastWriteTime) > 0) {
            cg_library_note(found.cFileName, "its .json is newer: save it again in the patcher");
            continue;
        }
        if (!cg_read_grow(path, &cg_lib_bytes, &cg_lib_cap, &size) || !cg_load(&cg_lib_graph, cg_lib_bytes, size)) {
            cg_library_note(found.cFileName, cg_why[0] != '\0' ? cg_why : "it cannot be read");
            cg_why[0] = '\0';
            continue;
        }
        if (!(cg_lib_graph.games & (1u << (game - 1)))) {
            continue;                  /* made for other games */
        }
        if (cg_lib_room()) {
            lstrcpyA(cg_lib.path[cg_lib.count], path);
            wsprintfA(cg_lib.label[cg_lib.count], "%s   (%s)", cg_readable(&cg_lib_graph),
                      found.cFileName);
            ++cg_lib.count;
        }
    } while (FindNextFileA(find, &found));
    FindClose(find);
    sc_library_add(game);             /* the Isola Grand Event Collection's group (story_collection.inc) */
}

static INT_PTR CALLBACK cg_library_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    INT_PTR handled;
    if (vk_dialog_hook(window, message, wparam, lparam, &handled)) {
        return handled;
    }
    if (message == WM_INITDIALOG) {
        int i;
        cg_library_scan((int)lparam);
        for (i = 0; i < cg_lib.count; ++i) {
            SendDlgItemMessageA(window, IDC_LB_LIST, LB_ADDSTRING, 0, (LPARAM)cg_lib.label[i]);
        }
        if (cg_lib.count > 0) {
            SendDlgItemMessageA(window, IDC_LB_LIST, LB_SETCURSEL, 0, 0);
        }
        if (cg_lib.problems[0] != '\0') {
            char note[sizeof cg_lib.problems + 80];
            wsprintfA(note, "Not offered:\r\n%s", cg_lib.problems);
            SetDlgItemTextA(window, IDC_LB_NOTE, note);
        } else if (cg_lib.count == 0) {
            SetDlgItemTextA(window, IDC_LB_NOTE,
                            "No event for this game is in the library yet. Make one in the patcher's Custom Island "
                            "Event Library and save it; it appears here.");
        }
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        if (id == IDOK || (id == IDC_LB_LIST && HIWORD(wparam) == LBN_DBLCLK)) {
            int sel = (int)SendDlgItemMessageA(window, IDC_LB_LIST, LB_GETCURSEL, 0, 0);
            if (sel < 0 || sel >= cg_lib.count) {
                MessageBoxA(window, "Choose an event in the list first.", "Custom Island Events",
                            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
                return TRUE;
            }
            cg_lib.chosen = sel;
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* The event picked in the library, bought (story_custom_island_event): read and checked again, refused with the
   reason, confirmed (with the warning a risky role needs), and queued.  1 when it is on its way. */
static int cg_library_purchase(int game, HWND owner) {
    char prompt[600];
    const char *refusal;
    const char *risk;
    unsigned int planned = 0;
    unsigned int size = 0;
    int displaces;
    if (cg_lib.game != game || cg_lib.chosen < 0 || cg_lib.chosen >= cg_lib.count) {
        return 0;
    }
    if (pc_library_path(cg_lib.path[cg_lib.chosen])) {
        /* A procedural event: composed now, left in cg_bytes (story_procedural.inc). */
        if (!pc_library_load(game, cg_lib.path[cg_lib.chosen])) {
            wsprintfA(prompt, "That event can not happen right now: %s. Nothing has been queued.", cg_why);
            ui_message(owner, prompt);
            return 0;
        }
    } else if (lv_library_path(cg_lib.path[cg_lib.chosen])) {
        /* A Living Event Engine seed: the variant the library's cast can cast, in cg_bytes (story_living.inc). */
        if (!lv_library_load(game, cg_lib.path[cg_lib.chosen])) {
            wsprintfA(prompt, "That event can not happen right now: %s. Nothing has been queued.", cg_why);
            ui_message(owner, prompt);
            return 0;
        }
    } else if (!cg_read_grow(cg_lib.path[cg_lib.chosen], &cg_bytes, &cg_bytes_cap, &size)
        || !cg_load(&cg_g, cg_bytes, size)) {
        wsprintfA(prompt, "That event can not be used: %s. Nothing has been queued.", cg_why);
        ui_message(owner, prompt);
        cg_bytes_size = 0;
        return 0;
    } else {
        cg_bytes_size = size;
    }
    cg_cast_now = CG_CAST_PREFER;      /* bought: a requirement nobody meets is dropped, never the purchase */
    cg_origin_now = CG_ORIGIN_PURCHASE;
    refusal = cg_refusal(game, &planned);
    if (refusal != NULL) {
        ui_message(owner, refusal);
        return 0;
    }
    risk = cg_risk(game);
    if (risk != NULL && !ui_risk(owner, risk)) {
        return 0;
    }
    wsprintfA(prompt, vvfp_tr("vvfp.story/story_custom_ui.story_custom_island_event.s3",
                              "Do you want to buy Custom Island Event for %s tech points?\r\nPress OK to confirm, or Cancel.",
                              400), story_price_text(game));
    if (MessageBoxA(owner, prompt, "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND)
        != IDOK) {
        return 0;
    }
    cg_cast_now = CG_CAST_PREFER;
    cg_origin_now = CG_ORIGIN_PURCHASE;
    refusal = cg_refusal(game, &planned);          /* the village may have moved on while the boxes were open */
    if (refusal == NULL && ce_purchase_locked(game, &displaces)) {
        refusal = "Your last custom island event is still on its way.";
    }
    if (refusal != NULL || !cg_queue(game, planned, 1)) {
        ui_message(owner, refusal != NULL ? refusal
                                          : "The event can not happen right now. No tech points have been deducted.");
        return 0;
    }
    lv_library_armed(game);
    wsprintfA(prompt, "\"%s\" is on its way.", cg.title);
    ui_message(owner, prompt);
    return 1;
}

/* ---- Queueing from the other paths (the rare roll, Pick Island Event: story_collection.inc,
   story_more_events.inc) ------------------------------------------------------------------------------------- */

static char cg_queue_why[400];

/* Why the last cg_queue_origin did not queue its event ("" when it did). */
static const char *cg_queue_refusal(void) {
    return cg_queue_why;
}

/* Queue the .cieg `file` (`size` bytes) in `game` with `origin` (CG_ORIGIN_PURCHASE / PICK / NATURAL) and its cast
   (CG_CAST_STRICT: every requirement and the event's own requirement must hold; CG_CAST_PREFER: a requirement
   nobody meets is dropped).  Nothing is charged here.  1 when queued; 0 with the reason in cg_queue_refusal() --
   among them: another branching event is still running (one at a time), the file is refused, the village cannot
   fill the roles. */
static int cg_queue_origin(int game, const unsigned char *file, unsigned size, int origin, int cast_mode) {
    unsigned int planned = 0;
    const char *refusal;
    cg_queue_why[0] = '\0';
    if (game < 1 || game > 5 || file == NULL || size == 0u || size > CG_MAX_FILE) {
        lstrcpynA(cg_queue_why, "The event file can not be read.", sizeof cg_queue_why);
        return 0;
    }
    if (cg.phase != CG_IDLE && cg.phase != CG_DONE) {
        lstrcpynA(cg_queue_why, "Another branching island event is still running.", sizeof cg_queue_why);
        return 0;
    }
    if (file != cg_bytes) {
        if (!cg_bytes_room(size)) {
            lstrcpynA(cg_queue_why, "The event file can not be read.", sizeof cg_queue_why);
            return 0;
        }
        memcpy(cg_bytes, file, size);
    }
    cg_bytes_size = size;
    if (!cg_load(&cg_g, cg_bytes, size)) {
        wsprintfA(cg_queue_why, "That event can not be used: %s.", cg_why);
        cg_bytes_size = 0;
        return 0;
    }
    cg_cast_now = cast_mode == CG_CAST_PREFER ? CG_CAST_PREFER : CG_CAST_STRICT;
    cg_origin_now = origin;
    refusal = cg_refusal(game, &planned);
    if (refusal != NULL) {
        lstrcpynA(cg_queue_why, refusal, sizeof cg_queue_why);
        cg_origin_now = CG_ORIGIN_PURCHASE;
        return 0;
    }
    if (!cg_queue(game, planned, 1)) {
        lstrcpynA(cg_queue_why, "The event can not happen right now.", sizeof cg_queue_why);
        cg_origin_now = CG_ORIGIN_PURCHASE;
        return 0;
    }
    cg_origin_now = CG_ORIGIN_PURCHASE;
    return 1;
}

#ifdef VVFP_TEST
/* ---- Test build only --------------------------------------------------------------------------------------- */

/* "A man may carry the baby by chance": the percent the installed patches' list gives (-1 in the high half of
   nothing), and one draw of cg_partner_carries with the rolls VvfpStoryProbeSetRolls gives: percent | carries << 8. */
__declspec(dllexport) int __stdcall VvfpStoryProbePartnerCarries(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL) {
        return -1;
    }
    return cg_partner_carry_percent() | (cg_partner_carries(a) << 8);
}

/* Queue the .cieg `data` (`size` bytes) in `game` as the library's purchase does, without any dialog: NULL when
   queued, else the refusal.  `due` 1 makes the island event due (ce_arm_with), 0 only arms it. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphQueue(int game, const unsigned char *data,
                                                                     unsigned int size, int due) {
    unsigned int planned = 0;
    const char *refusal;
    if (size > CG_MAX_FILE) {
        return "too large";
    }
    install_state[game] = 1;
    if (!cg_bytes_room(size)) {
        return "too large";
    }
    memcpy(cg_bytes, data, size);
    cg_bytes_size = size;
    if (!cg_load(&cg_g, cg_bytes, size)) {
        return cg_why;
    }
    /* due's bit 8: the cast is strict (the rare roll / Pick), else prefer (a purchase); bits 9-10 the origin. */
    cg_cast_now = (due & 0x100) ? CG_CAST_STRICT : CG_CAST_PREFER;
    cg_origin_now = (due >> 9) & 3;
    due &= 0xFF;
    refusal = cg_refusal(game, &planned);
    if (refusal != NULL) {
        cg_origin_now = CG_ORIGIN_PURCHASE;
        return refusal;
    }
    /* due 0: armed without making the island event due (the engine tests drive the entry points). */
    refusal = cg_queue(game, planned, due) ? NULL : "not armed";
    cg_origin_now = CG_ORIGIN_PURCHASE;
    return refusal;
}

/* Record `record` starts nursing just before the next walk (after the roles are cast), -1 none. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphNurseAtWalk(int record) {
    test_graph_nurse = record;
}

/* "VVFP Head Look.dll" as the test build sees it (26): `mode` -1 the real one, 0 none, 1 installed (and the record
   cleared); returns the looks set so far, each (record index, look) into `out` (at most `cap` pairs). */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphHeadLook(int mode, int *out, int cap) {
    int i;
    if (mode >= -1 && mode <= 1) {
        test_graph_head_look = mode;
        test_graph_head_looks = 0;
        return 0;
    }
    for (i = 0; i < test_graph_head_looks && i < cap && out != NULL; ++i) {
        out[2 * i] = test_graph_head_look_set[i][0];
        out[2 * i + 1] = test_graph_head_look_set[i][1];
    }
    return test_graph_head_looks;
}

/* The birth sex as the test build sees it: `born_male` -1 the real rule, else bit i: record i was born male. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphBornMale(int born_male) {
    test_graph_born_male = born_male;
}

/* A nursing effect's birth left out (`on` 1): the conception alone, which the emulator can run. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphNoDeliver(int on) {
    test_graph_no_deliver = on;
}

/* The word-change note of role `role` (35): 1 + the display that changed its words, 0 none (test build only). */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphLateAt(int role) {
    return role >= 0 && role < CG_MAX_ROLES ? cg_late_at[role] : -1;
}

/* The gender presentation the words see (35): `mask` -1 the real one, else bit i: record i drawn with the other
   sex's look.  Returns the mask now (a presentation effect sets and clears its bit). */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphPresented(int mask) {
    if (mask != -2) {
        test_graph_presented = mask;
    }
    return test_graph_presented;
}

/* "VVFP Gender Presentation.dll" as the test build sees it (29): `mode` -1 the real one, 0 none, 1 installed (and the
   record cleared); returns the choices set so far, each (record index, on) into `out` (at most `cap` pairs). */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphPresentation(int mode, int *out, int cap) {
    int i;
    if (mode >= -1 && mode <= 1) {
        test_graph_presentation = mode;
        test_graph_presentations = 0;
        return 0;
    }
    for (i = 0; i < test_graph_presentations && i < cap && out != NULL; ++i) {
        out[2 * i] = test_graph_presentation_set[i][0];
        out[2 * i + 1] = test_graph_presentation_set[i][1];
    }
    return test_graph_presentations;
}

/* "VVFP Last Names.dll" (27) as the test build sees it: -1 the real check, 0 none, 1 in.  Returns how many sex
   changes (28) told the companions and wrote the history record so far: told * 1000 + history. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphSexLast(int unused, int last_names) {
    (void)unused;
    test_graph_last_names = last_names;
    return test_graph_sex_told * 1000 + test_graph_sex_history;
}

/* A New Home's parentage sidecar as the test build sees it (cie-v6-binary.md 21): record `record`'s father (which 0)
   or mother (1), or the father of the baby it carries (2); an empty name: none. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphVv1Parent(int record, int which, const char *name, int head,
                                                                   int body) {
    cg_person *p;
    if (record < 0 || record >= CE_MAX_RECORDS || which < 0 || which > 2) {
        return;
    }
    test_graph_vv1_parents = 1;
    p = which == 2 ? &test_graph_vv1_exp[record] : &test_graph_vv1_par[record][which];
    lstrcpynA(p->name, name != NULL ? name : "", CG_NAME_BYTES);
    p->head = head;
    p->body = body;
}

/* The run file's layout: out[0] a version 3 file's state bytes, [1] the header's bytes, [2] the whole state's, [3] where
   the displays' words start in it, [4] their bytes, [5] the bytes versions 2 to 4 kept for them, [6] where version
   3's state ends now (the third and fourth answers' segments end), [7] a version 4 file's state bytes. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphFileLayout(int *out) {
    out[0] = (int)CG_FILE_V3_STATE;
    out[1] = (int)sizeof(cg_file_head);
    out[2] = (int)sizeof(cg_state);
    out[3] = (int)offsetof(cg_state, displays);
    out[4] = (int)CG_DISPLAY_BYTES;
    out[5] = (int)CG_DISPLAY_BYTES_V4;
    out[6] = (int)offsetof(cg_state, seg_v6);
    out[7] = (int)CG_FILE_V4_STATE;
    out[8] = (int)offsetof(cg_state, entry);           /* [8] the log entry's start, [9] its bytes, [10] version 4's */
    out[9] = (int)CG_ENTRY_BYTES;
    out[10] = (int)CG_ENTRY_BYTES_V4;
}

/* cg_queue_origin as story_collection.inc calls it: 1 queued, else 0 with the reason copied to `why` (200 bytes). */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphQueueOrigin(int game, const unsigned char *data,
                                                                    unsigned int size, int origin, int cast_mode,
                                                                    char *why) {
    int ok;
    install_state[game] = 1;
    ok = cg_queue_origin(game, data, size, origin, cast_mode);
    if (why != NULL) {
        lstrcpynA(why, cg_queue_refusal(), 200);
    }
    return ok;
}

/* The version 6 run: out[0] picks, then (pool, instance, item) for each of the first `cap` picks; out[1 + 3 cap ..]:
   the aliases' members (16), the relaxed roles, the cast, the origin, the asked question's buttons and its map (7),
   the path's effect count and its rolls (a, b; at most 64).  The count of ints written. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphPicks(int *out, int cap) {
    int i, o = 1;
    out[0] = cg.pick_count;
    for (i = 0; i < cap; ++i) {
        out[o++] = i < cg.pick_count ? cg.picks[i].pool : -1;
        out[o++] = i < cg.pick_count ? cg.picks[i].instance : -1;
        out[o++] = i < cg.pick_count ? (cg.picks[i].item == CG_NONE ? -1 : cg.picks[i].item) : -1;
    }
    for (i = 0; i < CG_MAX_ROLES; ++i) {
        out[o++] = cg.alias[i];
    }
    out[o++] = (int)cg.relaxed;
    out[o++] = cg.cast_mode;
    out[o++] = cg.origin;
    {
        unsigned char map[CG_MAX_ANSWERS];
        int n = cg.phase == CG_ASKED && cg.asking >= 0 ? cg_buttons(cg.display_node[cg.asking], cg.answers, map) : 0;
        out[o++] = n;
        for (i = 0; i < CG_MAX_ANSWERS; ++i) {
            out[o++] = i < n ? map[i] : -1;
        }
    }
    out[o++] = cg.path.fx;             /* then the path's effect rolls (a, b), at most 64 */
    for (i = 0; i < cg.path.fx && i < 64 && i < CG_MAX_FX; ++i) {
        out[o++] = cg.path.fx_a[i];
        out[o++] = cg.path.fx_b[i];
    }
    return o;
}

/* The Unicode Text companion seen as loaded (1) or not (0), -1 as it is; the finished structures for "damage"
   (bit k; -1 as the game says: then nothing is recorded), and what the last damage did into `damaged`
   (SD_MAX_STRUCTURES ints, each structure's loss). */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphFacts(int unicode, int structures, int *damaged) {
    int k;
    test_graph_unicode = unicode;
    if (structures != -2) {
        test_graph_structures = structures;
        memset(test_graph_damaged, 0, sizeof test_graph_damaged);
    }
    if (damaged != NULL) {
        for (k = 0; k < SD_MAX_STRUCTURES; ++k) {
            damaged[k] = test_graph_damaged[k];
        }
    }
}

/* Read `data` as a .cieg: NULL when it passes, else why not. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphCheck(const unsigned char *data, unsigned int size) {
    static cg_graph g;
    static unsigned char *copy;
    static unsigned int copy_cap;
    if (size > CG_MAX_FILE || cg_grow(&copy, &copy_cap, size ? size : 1u) == NULL) {
        return "too large";
    }
    memcpy(copy, data, size);
    return cg_load(&g, copy, size) ? NULL : cg_why;
}

/* The nodes (indexes) a draw picks whenever one of them can be drawn; the patches on (-1 as seen) and the scale
   mode (-1 as its companion says). */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphForce(const int *nodes, int count, int patches, int scale) {
    int i;
    test_graph_forced = count < 0 ? 0 : (count > 64 ? 64 : count);
    for (i = 0; i < test_graph_forced; ++i) {
        test_graph_force[i] = (short)nodes[i];
    }
    test_graph_patches = patches;
    test_graph_scale = scale;
}

/* Scrolling Popups installed (1) or not (0) for the layout of the pages, -1 = as its companion says. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphScroll(int on) {
    test_graph_scroll = on;
}

/* One popup (native/shared/one_popup.h): the choices the popup shows now; OK on it (1: another text replaced the
   shown one, written to `text`); whether ce_choice_begin just opened `game`'s event as one popup (taken once). */
__declspec(dllexport) int __stdcall VvfpStoryProbeOnePopupRows(int game) {
    return cg_op_rows(game);
}

__declspec(dllexport) int __stdcall VvfpStoryProbeOnePopupOk(int game, char *text, int size) {
    return cg_op_ok(game, text, size);
}

__declspec(dllexport) int __stdcall VvfpStoryProbeOnePopupBegun(int game) {
    return cg_op_begun_take(game);
}

/* 20: `text` (changed in place) in sentence case (kind 0; `item` a pool's item), title case (kind 1) or as a
   button's label (kind 2). */
__declspec(dllexport) void __stdcall VvfpStoryProbeSentenceCase(char *text, int item, int kind) {
    if (kind == 1) {
        cg_title_case(text);
    } else {
        cg_sentence_case(text, item, kind == 2);
    }
}

/* The installed patches' list as the patcher would write it (NULL: none, as an older patch), then the patches the
   loaded graph names that are on in `game` (cg_patches_on), as a bit mask. */
__declspec(dllexport) unsigned int __stdcall VvfpStoryProbeInstalledPatches(int game, const char *text) {
    test_graph_patches = -1;
    cg_installed_state = text != NULL ? 1 : 0;
    lstrcpynA(cg_installed, text != NULL ? text : "", CG_INSTALLED_BYTES);
    return cg_patches_on(game);
}

/* The puzzles solved for the graph's checks (bit = the adapter's puzzle index; -1 = as the game says). */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphPuzzles(int solved) {
    test_graph_puzzles = solved;
}

/* "VVFP VV4 Supply Cap.dll" as the "supply" effect sees it (cie-v6-binary.md 32): -1 the real check, 0 none, 1 in. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphSupplyCap(int mode) {
    test_graph_supply_cap = mode;
}

/* "has_supply" (cie-v6-binary.md 33): -1 the village's own goods, 0 / 1 forced. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphGoods(int mode) {
    test_graph_goods = mode;
}

/* The weather (35): `call` 0 records the type without calling the game's starter; returns the last type started
   (-1 none) and clears it. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphWeather(int call) {
    int last = test_graph_weather;
    test_graph_weather_call = call;
    test_graph_weather = -1;
    return last;
}

/* The run: out[0] phase, [1] display_next, [2] display_count, [3] display armed, [4] choice, [5] bound roles,
   [6] planned, [7..10] the first four roles' records, [11] pre_pages, [12] the path's nodes, [13] answers,
   [14] the told count, [15..18] the first four roles' female flags. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphState(int *out) {
    int i;
    for (i = 0; i < 4; ++i) {
        out[15 + i] = cg.female[i];
    }
    out[0] = cg.phase;
    out[1] = cg.display_next;
    out[2] = cg.display_count;
    out[3] = cg_display_armed;
    out[4] = cg.choice;
    out[5] = (int)cg.bound;
    out[6] = (int)cg.planned;
    for (i = 0; i < 4; ++i) {
        out[7 + i] = (cg.bound & (1u << i)) ? cg.record[i] : -1;
    }
    out[11] = cg.pre_pages;
    out[12] = cg.path.nodes;
    out[13] = cg.answers;
    out[14] = test_graph_told_count;
}

/* The path's nodes (which 0) or the asked question's answer `which - 1` segment, into out (at most `cap`); the
   count. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphPath(int which, int *out, int cap) {
    int i;
    const cg_history *h = which <= 0 || cg.answers >= CG_MAX_QUESTIONS ? &cg.path
                          : cg_seg(cg.answers, which - 1 < CG_MAX_ANSWERS ? which - 1 : CG_MAX_ANSWERS - 1);
    for (i = 0; i < h->nodes && i < cap; ++i) {
        out[i] = h->node[i];
    }
    return h->nodes;
}

/* The Island Events log stood in for (`on`: each page's lines "  page <k>"); then: the entry as it is now into
   `now`, the last one filed into `filed` (each up to `cap` bytes), and how many were filed. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphLog(int on, char *now, char *filed, int cap) {
    if (on >= 0) {
        test_graph_log = on;
        test_graph_entries = 0;
        test_graph_entry[0] = '\0';
        test_graph_sends = 0;
        test_graph_sent[0] = '\0';
    }
    if (now != NULL && cap > 0) {
        lstrcpynA(now, cg.entry, cap);
    }
    if (filed != NULL && cap > 0) {
        lstrcpynA(filed, test_graph_entry, cap);
    }
    return test_graph_entries;
}

/* The entry as last handed to the log (into `out`, `cap` bytes), with out_info[0] its `disk`, [1] `final`; how
   many times it was handed over. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphSent(char *out, int cap, int *out_info) {
    if (out != NULL && cap > 0) {
        lstrcpynA(out, test_graph_sent, cap);
    }
    if (out_info != NULL) {
        out_info[0] = test_graph_sent_disk;
        out_info[1] = test_graph_sent_final;
    }
    return test_graph_sends;
}

/* Display `k`'s text, or NULL. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphDisplay(int k) {
    return k >= 0 && k < cg.display_count ? cg_display(k) : NULL;
}

/* Display `k`'s popup title (cie-v6-binary.md 14), or NULL. */
__declspec(dllexport) const char *__stdcall VvfpStoryProbeGraphTitle(int k) {
    static char title[CE_LONG_LINE_BYTES * 4];
    if (k < 0 || k >= cg.display_count) {
        return NULL;
    }
    cg_display_title(k, title, sizeof title);
    return title;
}

/* What "VVFP Cause of Death.dll" / "VVFP Faith Notice.dll" were told, entry `k`: its kind (1 killed, 2 vanished, 3
   a faith conversion; 0 none), its record in *index, its words copied to `words`. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphTold(int k, int *index, char *words) {
    if (k < 0 || k >= test_graph_told_count) {
        return 0;
    }
    *index = test_graph_told[k].index;
    lstrcpyA(words, test_graph_told[k].words);
    return test_graph_told[k].kind;
}

/* Arm the run's next display without making it due (the slot's checks aside); 1 when armed. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphArmNext(int game) {
    if (!cg_active(game) || !cg_wants_display()) {
        return 0;
    }
    return cg_arm(game, 0);
}

/* The run's file as the test build keeps it: copied to `out` (up to `size` bytes); its size. */
__declspec(dllexport) int __stdcall VvfpStoryProbeGraphFile(void *out, int size) {
    if (out != NULL && size > 0) {
        memcpy(out, cg_test_file, (unsigned int)size < cg_test_size ? (unsigned int)size : cg_test_size);
    }
    return (int)cg_test_size;
}

/* A new process: the run's file from an earlier one (size 0 = none), the run in memory forgotten, the told list
   emptied. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGraphSession(const void *file, int size) {
    cg_test_size = 0;
    if (file != NULL && size > 0 && (unsigned int)size <= sizeof cg_test_file) {
        memcpy(cg_test_file, file, (unsigned int)size);
        cg_test_size = (unsigned int)size;
    }
    memset(&cg, 0, sizeof cg);
    cg_display_armed = 0;
    cg_dirty = 0;
    test_graph_told_count = 0;
    test_graph_structures = -1;
    test_graph_unicode = -1;
    test_graph_nurse = -1;
}
#endif
