# Isola Grand Event Collection: grammar fixes for the owner

These are the only edits the collection makes to the owner's text, apart from the mapping rules in
[authoring-rules.md](authoring-rules.md) (placeholders, pools, game words, typography). Each is a **glaring** mistake
one of the three inventories found: a broken sentence, a wrong word, a missing placeholder, a pronoun that does not fit.
Nothing stylistic is changed.

Line numbers are the frozen source's
(`docs/more-island-events/Isola_Grand_Event_Collection_V28_Consequences_Claude_Retrofit.txt`, SHA-256 in
`data/event_collection/SOURCE.sha256`). "Before" is the exact text on that line, with the source's curly quotes and
dashes written as plain `"` `'` and ` - `. A collection file may only use a fix listed here (its
`grammar_fixes` entry must match a row exactly); `scripts/collection_check.py` and
`tests/test_event_collection_files.py` enforce that.

Status: **waiting for the owner's approval.** A fix the owner rejects is removed here, and the event files that use it
then fail their checks until they follow the source again.

## Fixes

### Part 1 (lines 1-3519)

Besides the inventories' fixes: placeholders written without their parentheses would show the words "his/her",
"he/she" or "contestant1" instead of the villager's own pronoun or name, and stray full stops sit inside a slash
list or after a quotation that already ends one.

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| L104 | `is.... ` | `is ` | The Cooking Contest | Four stray dots break the sentence "(Name1) is (A) (B)." (twice on the line); the owner said to drop them |
| L135 | `works things out.` | `works things out` | The Cooking Contest, bank B | A full stop in the middle of the sentence the item is inserted into |
| L138 | `has tried, failed and succeeded throughout life` | `who has tried, failed and succeeded throughout life` | The Cooking Contest, bank B | Every other B item starts "that" / "who"; without it the sentence has no verb link |
| L163 | `has reliable friends.` | `has reliable friends` | The Cooking Contest, bank C | Stray full stop mid-sentence |
| L165 | `taught them well` | `taught (him/her) well` | The Cooking Contest, bank C | "them" for one contestant |
| L168 | `taught them some tips` | `taught (him/her) some tips` | The Cooking Contest, bank C | "them" for one contestant |
| L171 | `uses their strong emotions` | `uses (his/her) strong emotions` | The Cooking Contest, bank C | "their" for one contestant |
| L188 | `value their work` | `value (his/her) work` | The Cooking Contest, bank F | "their" for one contestant (inventory part 1 said L189) |
| L189 | `value their purpose` | `value (his/her) purpose` | The Cooking Contest, bank F | "their" for one contestant (inventory part 1 said L190) |
| L263 | `the charismatic crowner` | `the charismatic crooner` | The Cooking Contest, bank G | "crowner" is not a word; a one-letter typo for "crooner" (review R3) (inventory part 1 said L264) |
| L300 | `knows it can't compare to anything else` | `knows nothing else can compare to it` | The Cooking Contest | The sentence says the opposite of what it means |
| L305 | `their initial recipe` | `(his/her) initial recipe` | The Cooking Contest | "their" for one contestant |
| L468 | `brag about their win` | `brag about (his/her) win` | The Cooking Contest, bank P | "their" for one contestant |
| L474 | `teach each other the art of cooking` | `teach others the art of cooking` | The Cooking Contest, bank P | "each other" with one person |
| L476 | `cook in peace.` | `cook in peace` | The Cooking Contest, bank P | Stray full stop mid-sentence |
| L512 | `"Are you kidding me."` | `"Are you kidding me?"` | The Cooking Contest, bank Q | A question ends with a question mark |
| L737 | `(random from:1)` | `(He/she) (random from:1).` | The Child of Legend | The (1) items ("teaches him sign language") have no subject; the teacher is the subject |
| L751 | `smiles (3)` | `smiles, (3)` | The Child of Legend, bank (2) | Every other (2) item ends with a comma before "which ..." |
| L758 | `understanding (3)` | `understanding, (3)` | The Child of Legend, bank (2) | As above |
| L799 | `said. But long ago` | `said. "But long ago` | The Meaning of "Faith" | The teacher's quotation reopens after "said." (it closes with a quote mark at the end) |
| L819 | `There's a lot of things` | `There are a lot of things` | The Meaning of "Faith" | Agreement; line 816 already has the correct form |
| L826 | `on their work` | `on (his/her) work` | The Meaning of "Faith" | "their" for one child |
| L857 | `on their work` | `on (his/her) work` | The Meaning of "Faith" | "their" for one child |
| L2379 | `After checking the records, the mistake is corrected.` | `After the records are checked, the mistake is corrected.` | The Great Woodworking Competition | Dangling modifier: the mistake did not check the records |
| L2470 | `A judge accidentally` | `The judge accidentally` | The Potluck Dispute | One neutral visitor judges (line 2466) |
| L2472 | `The judges announce` | `The judge announces` | The Potluck Dispute | As above |
| L3136 | `Cook1 wins for flavor; Cook2 accepts` | `(Cook1) wins for flavor; (cook2) accepts` | The Breadfruit Breakdown | Placeholders without parentheses would show the words "Cook1" / "Cook2" |
| L3137 | `Cook2 wins for texture; Cook1 requests` | `(Cook2) wins for texture; (cook1) requests` | The Breadfruit Breakdown | As above |
| L171 | `fuel their art.` | `fuel (his/her) art` | The Cooking Contest, bank C | Same line as the inventory's fix: "their" for one contestant and a stray full stop mid-sentence |
| L469 | `all his/her friends his/her skills` | `all (his/her) friends (his/her) skills` | The Cooking Contest, bank P | Placeholders without parentheses |
| L473 | `down his/her experiences` | `down (his/her) experiences` | The Cooking Contest, bank P | Placeholder without parentheses |
| L481 | `showcase his/her award` | `showcase (his/her) award` | The Cooking Contest, bank P | Placeholder without parentheses |
| L482 | `all his/her detractors` | `all (his/her) detractors` | The Cooking Contest, bank P | Placeholder without parentheses |
| L483 | `with his/her food` | `with (his/her) food` | The Cooking Contest, bank P | Placeholder without parentheses |
| L491 | `crosses his/her arms` | `crosses (his/her) arms` | The Cooking Contest, bank Q | Placeholder without parentheses |
| L492 | `nods his/her head` | `nods (his/her) head` | The Cooking Contest, bank Q | Placeholder without parentheses |
| L508 | `pretends he/she did not lose` | `pretends (he/she) did not lose` | The Cooking Contest, bank Q | Placeholder without parentheses |
| L510 | `thankful he/she got` | `thankful (he/she) got` | The Cooking Contest, bank Q | Placeholder without parentheses |
| L561 | `can't continue fighting.)` | `can't continue fighting).` | The Cooking Contest, (5) | The full stop belongs after the list, not inside one option |
| L623 | `can't continue fighting.)` | `can't continue fighting).` | The Cooking Contest, (8) | As above |
| L2835 | `replies, (A).` | `replies, (A)` | The Elder's Favorite Stone | Every (A) reply is a full quotation ending in its own full stop; a second full stop follows the closing quote |
| L1458 | `contestant1` | `(contestant1)` | The Great Beautification Project, (6) | Placeholder without parentheses would show the word "contestant1" |
| L1459 | `contestant2` | `(contestant2)` | The Great Beautification Project, (6) | As above |
| L664 | `/they cancel` | `/They cancel` | The Cooking Contest, add-on 1 (17) | Both options of "(They award ... - 4/they cancel the contest - 8.)" open a sentence |
| L664 | `8.)` | `8).` | The Cooking Contest, add-on 1 (17) | The full stop belongs after the list, not inside one option |
| L2260 | `entries, (6).` | `entries, (6)` | The Great Woodworking Competition | Every (6) interruption is one or more full sentences ending in a full stop; a second full stop follows |
| L3006 | `begins: (A).` | `begins: (A)` | The Chief's Monumental Speech | Every (A) opening is a full quotation ending in its own full stop or ellipsis; a second full stop follows the closing quote |
| L192 | `underestimates themselves` | `underestimates (himself/herself)` | The Cooking Contest, bank F | "themselves" for one contestant, as L188/L189 |
| L194 | `overestimates themselves` | `overestimates (himself/herself)` | The Cooking Contest, bank F | As above |
| L203 | `put their talents` | `put (his/her) talents` | The Cooking Contest, bank F | "their" for one contestant, as L188/L189 |
| L300 | `into a (J, different` | `into (J, different` | The Cooking Contest | Every J item starts with its own article: "into a a pot" |
| L305 | `into a (J, different` | `into (J, different` | The Cooking Contest | As above |
| L2419 | `prefers (B, different)` | `prefers to (B, different)` | The Potluck Dispute | Every B item is a bare verb ("make a compromise") that needs "to" after "prefers" |
| L3300 | `Inside are` | `Inside is` | The Keeper of Little Things | Every option is one object ("a smooth pebble") |

### Part 2 (lines 3520-6836)

Each V10 "goes wrong when:" item ends the page's sentence, so it needs its full stop (review r1, minor 1).

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| L4976 | `ARBOR-DAY` | `ARBOR DAY` | The Arbor-Day Festival | Spelling of the title (inventory part 2 also suggests a rename; that is the owner's call) |
| L5696 | `cannot answer` | `cannot answer.` | V10 The Teacher Who Failed | The page's sentence has no closing full stop |
| L5697 | `rotten wood` | `rotten wood.` | V10 The Teacher Who Failed | As above |
| L5698 | `the wrong notes` | `the wrong notes.` | V10 The Teacher Who Failed | As above |
| L5699 | `than expected` | `than expected.` | V10 The Teacher Who Failed | As above |
| L5701 | `(himself/herself)` | `(himself/herself).` | V10 The Teacher Who Failed | As above |
| L5703 | `everyone's attention` | `everyone's attention.` | V10 The Teacher Who Failed | As above |

### Part 3a (lines 6837-8489: V13, V14, the game-exclusive events, V17)

Outcome pages and drawn bank items that would show as fragments: a missing full stop, a missing article, or a drawn
word with no sentence around it (review r2, M8, M18, M19).

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| L6907 | `praise; use the original contest's winner` | `praise.` | V13-A The Judge Who Feared No Dish, A2 | The page closes with a full stop once the routing note is cut (decision 7) |
| L6875 | `thunderous, theatrical, and almost impossible to impress` | `(He/she) is thunderous, theatrical, and almost impossible to impress.` | V13-A The Judge Who Feared No Dish | The temperament bank (JUDGE TEMPERAMENT, no lead-in in the source) would show as a bare fragment with no subject or full stop; the judge is the subject |
| L6876 | `quiet and devastating, speaking in a whisper that frightens everyone` | `(He/she) is quiet and devastating, speaking in a whisper that frightens everyone.` | V13-A The Judge Who Feared No Dish | As above |
| L6877 | `warm toward earnest apprentices, merciless toward boastful masters` | `(He/she) is warm toward earnest apprentices, merciless toward boastful masters.` | V13-A The Judge Who Feared No Dish | As above |
| L6878 | `astonishingly fair, but prone to comparisons involving dead fish` | `(He/she) is astonishingly fair, but prone to comparisons involving dead fish.` | V13-A The Judge Who Feared No Dish | As above |
| L6879 | `perpetually furious at wasted food and unhygienic preparation` | `(He/she) is perpetually furious at wasted food and unhygienic preparation.` | V13-A The Judge Who Feared No Dish | As above |
| L8206 | `The Children are asked` | `The children are asked` | V17-B The Children's Jury | Stray capital |
| L7660 | `the same subject` | `the same subject, (subject),` | V14-02 The World's Simplest Explanation | The drawn subject is named inside the source's sentence instead of as a bare word |
| L7739 | `something the adults overlooked.` | `something the adults overlooked: (discovery).` | V14-13 The Curious Little Explorer | The drawn discovery is named inside the source's sentence |
| L7740 | `unusual beetle` | `an unusual beetle` | V14-13 | The list's items are shown one at a time; each needs its article |
| L7740 | `patterned fungus` | `a patterned fungus` | V14-13 | As above |
| L7740 | `unfamiliar mushroom` | `an unfamiliar mushroom` | V14-13 | As above |
| L7740 | `mushroom, hidden` | `mushroom, a hidden` | V14-13 | As above ("a hidden clearing") |
| L7741 | `odd stone` | `an odd stone` | V14-13 | As above |
| L7741 | `animal track` | `an animal track` | V14-13 | As above |
| L8417 | `honest coincidence,` | `honest coincidence.` | V17-E Who Owns a Discovery? | Each ending is a page of its own; it ends with a full stop |
| L8418 | `misremembered teaching,` | `misremembered teaching.` | V17-E Who Owns a Discovery? | As above |
| L8418 | `proved by evidence,` | `proved by evidence.` | V17-E Who Owns a Discovery? | As above |
| L8429 | `rejected or redesigned;` | `rejected or redesigned.` | V17-E The Two Faces of Isola | The designer rule after the semicolon is never shown; the sentence ends here |
| L8441 | `festival legend,` | `festival legend.` | V17-E Who Gets to Tell Isola's History? | As above: the designer rule after the comma is never shown |
| L8459 | `joint celebration;` | `joint celebration.` | V17-E The Children's Peace, the Adults' Quarrel | Each outcome is a page of its own; it ends with a full stop |
| L8459 | `sincere apology;` | `sincere apology.` | V17-E The Children's Peace, the Adults' Quarrel | As above |
| L8460 | `adult disagreement;` | `adult disagreement.` | V17-E The Children's Peace, the Adults' Quarrel | As above |

### Part 3b (lines 8490-10431: V18-V24)

The compact medical crises (V20 D6-D12) list each choice's outcomes as "the patient recovers; or dies; or ...". Each
outcome is its own page, so an outcome without its subject would read "Dies". Each fix restores the subject the line
already names (approved by the lead as glaring, 2026-11-14).

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| L8589 | `The judges present one question:` | `The judges present one of these questions:` | V18-03 The Great Question | Four questions follow; one is drawn |
| L9434 | `The subject recognizes` | `(Name2), the subject, recognizes` | V21 C2 The Statue That Divided the Village | "(himself/herself)" needs a named villager |
| L9453 | `forgive (him/her).` | `forgive (Name2).` | V21 C2 The Statue That Divided the Village | "(him/her)" refers to nobody named |
| L9592 | `The subject objects` | `(Name2), the subject, objects` | V22-1 The Great Isolan Drawing Competition | "(his/her)" needs a named villager |
| L9034 | `or dies;` | `or the patient dies;` | V20 D6 The Physician Who Refused | The outcome has no subject |
| L9036 | `fails; or is wisely` | `the procedure fails; or the procedure is wisely` | V20 D6 The Physician Who Refused | As above (two outcomes) |
| L9038 | `argue too long; or hear a` | `they argue too long; or they hear a` | V20 D6 The Physician Who Refused | As above (two outcomes) |
| L9045 | `it works; fails; or` | `it works; it fails; or` | V20 D7 The Patient Who Knew Too Much | As above |
| L9058 | `forgives; demands accountability;` | `forgives; the patient demands accountability;` | V20 D9 The Healer's Secret | As above |
| L9065 | `right; mistaken but thoughtful; or notices` | `right; the apprentice is mistaken but thoughtful; or the apprentice notices` | V20 D10 The Child Who Corrected the Masters | As above (two outcomes) |
| L9086 | `well; conflict` | `well; they conflict` | V20 D12 The Doctor Who Could Not Save Everyone | As above |

Closing full stops (decision 7, review r1 minor 1, M8):

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| L9034 | `;` | `.` | V20 The Physician Who Refused | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9036 | `;` | `.` | V20 The Physician Who Refused | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9038 | `;` | `.` | V20 The Physician Who Refused | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9043 | `;` | `.` | V20 The Patient Who Knew Too Much | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9045 | `;` | `.` | V20 The Patient Who Knew Too Much | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9050 | `;` | `.` | V20 The Medicine That Works Too Well | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9051 | `;` | `.` | V20 The Medicine That Works Too Well | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9052 | `;` | `.` | V20 The Medicine That Works Too Well | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9053 | `;` | `.` | V20 The Medicine That Works Too Well | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9058 | `;` | `.` | V20 The Healer's Secret | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9060 | `;` | `.` | V20 The Healer's Secret | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9065 | `;` | `.` | V20 The Child Who Corrected the Masters | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9067 | `;` | `.` | V20 The Child Who Corrected the Masters | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9068 | `;` | `.` | V20 The Child Who Corrected the Masters | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9073 | `;` | `.` | V20 The Ancient Oath | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9075 | `;` | `.` | V20 The Ancient Oath | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9082 | `;` | `.` | V20 The Doctor Who Could Not Save Everyone | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9083 | `;` | `.` | V20 The Doctor Who Could Not Save Everyone | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9084 | `;` | `.` | V20 The Doctor Who Could Not Save Everyone | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9086 | `;` | `.` | V20 The Doctor Who Could Not Save Everyone | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9087 | `;` | `.` | V20 The Doctor Who Could Not Save Everyone | Each outcome of the list is its own page and ends with a full stop (decision 7); the list's "or" is a separator |
| L9584 | `; the contest` | `; The contest` | V22-1 The Great Isolan Drawing Competition | After the cut reward instruction the sentence starts here (review M8) |
| L10008 | `retaliation; unlock` | `retaliation.` | V23-1 The Practical Joke | The page closes with a full stop once the sequel instruction is cut (decision 7) |
| L10372 | `reputation, if` | `reputation.` | V24 The Revolutionary Invention, reaction R6 | The reaction closes with a full stop once the designer note is cut (decision 7) |

### V27 (lines 10433-10945: the 57 short events of the V28 source)

None. The V27 lines needed no glaring grammar fix. Their designer words inside an outcome ("if eligible", "grant a
small appropriate skill gain", "no grave is created and a search/missing-person state persists", "selected by weighted
sub-branch" and the like) are ledger cuts, never shown, not grammar fixes (scripts/collection_v27.py lists each).

### Companion Anthology (its own lines)

The second source, `docs/more-island-events/Isola_COMPLETE_Master_Companion_Anthology_749_Events.txt` (SHA-256 in
`data/event_collection/COMPANION.sha256`), has its own line numbers. Its rows start with `companion L<line>` instead
of `L<line>` (for example a row for line 7542 starts `| companion L7542 |`); `grammar_doc_fixes("companion")` in
`scripts/collection_check.py` reads only those, and a companion file may use only them. The owner's rule of 2026-11-14 is the same:
verbatim apart from glaring grammar.

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| companion L2875 | `villager dies` | `the villager dies` | c5dn023_false_delicacy (Part 4 N023, outcome 2) | a missing article: with the designer tag "RARE FATAL:" and the instruction "if the fatal branch is enabled" cut, the line reads "Villager dies." |
| companion L3286 | `diffuses it` | `defuses it` | c5dn067_argument (Part 4 N067, outcome 1) | the wrong word: a joke defuses (calms) a quarrel; "diffuses" means spreads it |
| companion L7122 | `believes its a` | `believes its` | cat002_catfish (Living Catalogue 002, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7134 | `believes its a` | `believes its` | cat003_arrowfish (Living Catalogue 003, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7146 | `believes its a` | `believes its` | cat004_snout (Living Catalogue 004, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7158 | `believes its a` | `believes its` | cat005_fatfish (Living Catalogue 005, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7182 | `believes its a` | `believes its` | cat007_goldshark (Living Catalogue 007, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7194 | `believes its a` | `believes its` | cat008_fire_arrow (Living Catalogue 008, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7206 | `believes its a` | `believes its` | cat009_fruitfish (Living Catalogue 009, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7218 | `believes its a` | `believes its` | cat010_flashfish (Living Catalogue 010, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7242 | `believes its a` | `believes its` | cat012_comet (Living Catalogue 012, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7254 | `believes its a` | `believes its` | cat013_stickfish (Living Catalogue 013, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7266 | `believes its a` | `believes its` | cat014_grouper (Living Catalogue 014, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7278 | `believes its a` | `believes its` | cat015_leaffish (Living Catalogue 015, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7302 | `believes its a` | `believes its` | cat017_beta (Living Catalogue 017, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7314 | `believes its a` | `believes its` | cat018_pigmy (Living Catalogue 018, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7326 | `believes its a` | `believes its` | cat019_bananafish (Living Catalogue 019, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7338 | `believes its a` | `believes its` | cat020_quicksilver (Living Catalogue 020, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7362 | `believes its a` | `believes its` | cat022_clownfish (Living Catalogue 022, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7374 | `believes its a` | `believes its` | cat023_discus (Living Catalogue 023, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7386 | `believes its a` | `believes its` | cat024_bicolor (Living Catalogue 024, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7398 | `believes its a` | `believes its` | cat025_trigger (Living Catalogue 025, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7422 | `believes its a` | `believes its` | cat027_tang (Living Catalogue 027, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7434 | `believes its a` | `believes its` | cat028_idle (Living Catalogue 028, premise) | a stray article: the template's "its <trait>" (as in 001's "its unusual feeding habits") with "a" left in |
| companion L7542 | `that a Orange` | `that an Orange` | cat037_orange_fin (Living Catalogue 037, premise) | "a" before a vowel |
| companion L7554 | `that a Oriental` | `that an Oriental` | cat038_oriental_fin (Living Catalogue 038, premise) | "a" before a vowel |
| companion L7722 | `that a Angel` | `that an Angel` | cat052_angel_fin (Living Catalogue 052, premise) | "a" before a vowel |
| companion L7902 | `a Arthurium` | `an Arthurium` | cat067_lemonbush (Living Catalogue 067, premise) | "an" before a vowel sound |
| companion L8022 | `a Anagallis` | `an Anagallis` | cat077_weeper (Living Catalogue 077, premise) | "an" before a vowel sound |
| companion L8034 | `a Indigoberry` | `an Indigoberry` | cat078_multiflora (Living Catalogue 078, premise) | "an" before a vowel sound |
| companion L8538 | `a Oriental` | `an Oriental` | cat120_growth (Living Catalogue 120, premise) | "an" before a vowel sound |
| companion L8550 | `a Orange` | `an Orange` | cat121_health (Living Catalogue 121, premise) | "an" before a vowel sound |
| companion L8574 | `the The Golden Guppy` | `the Golden Guppy` | cat123_golden_guppy (Living Catalogue 123, premise) | a doubled article ("with the The Golden Guppy") |
| companion L8622 | `a Aureus` | `an Aureus` | cat127_golden_berries (Living Catalogue 127, premise) | "an" before a vowel sound |

Wave 1 chunk 1 (Vol 1 Part 1, Part 3 001-030) needed none. Known candidates for the later chunks (inventory, the
Living Catalogue templates): "believes its a startling" (22 times), "a Orange / a Oriental / a Angel / a Arthurium /
a Anagallis / a Indigoberry / a Aureus" (9 times: companion L7542, 7554, 7722, 7902, 8022, 8034, 8538, 8550, 8622) and
"with the The Golden Guppy" (L8574). The chunk that builds them adds its rows here. Chunk K10 (Living Catalogue
001-056) added the 22 "believes its a" rows and L7542, L7554, L7722 above; the rest belong to K11 and K9.

### Living Event Engine fixed event volumes (the third source; rows `| living L<line> |`)

LV-A (MED-01..31, LIFE-01..45, CIRCLE-01..31, living L20219-21645): none. Not fixed (not glaring): MED-19's "A Magic
practitioner" (living L20454) keeps the source's capital, the volume's name for one of its four ways of knowing.

LV-B (PEOPLES-01..37, UNSEEN-01..39, WAYS-01..38, AUTH-01..30, living L21665-23809): none. Not fixed (not glaring):
WAYS' and UNSEEN's capitalised ways of knowing ("a Magic adept", "the Nature master", "the Science master", "Nature
knowledge") keep the source's capitals, as MED-19.

### The approved drafts, group B (each file its own source; rows `| draft_<x> L<line> |`)

The format has no "his/hers" placeholder (it would show the words "his/hers"), so the drafts' nine `(his/hers)` become
`(his/her) own` ("his own" / "her own"), and HON-25's "It wasn't (his/hers) to mention" becomes "(his/her) place",
where "own" would not read. Nothing else is fixed.

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| draft_hum L425 | `(his/hers)` | `(his/her) own` | HUM-35 | no his/hers placeholder: "his own" / "her own" |
| draft_hon L59 | `(his/hers)` | `(his/her) own` | HON-05 | no his/hers placeholder: "his own" / "her own" |
| draft_hon L158 | `(his/hers)` | `(his/her) own` | HON-13 | no his/hers placeholder: "his own" / "her own" |
| draft_hon L209 | `(his/hers)` | `(his/her) own` | HON-17 | no his/hers placeholder: "his own" / "her own" |
| draft_jus L17 | `(his/hers)` | `(his/her) own` | JUS-01 | no his/hers placeholder: "his own" / "her own" |
| draft_jus L185 | `(his/hers)` | `(his/her) own` | JUS-15 | no his/hers placeholder: "his own" / "her own" |
| draft_jus L239 | `(his/hers)` | `(his/her) own` | JUS-20 | no his/hers placeholder: "his own" / "her own" |
| draft_jus L245 | `(his/hers)` | `(his/her) own` | JUS-20 | no his/hers placeholder: "his own" / "her own" |
| draft_hon L305 | `(his/hers) to mention` | `(his/her) place to mention` | HON-25 | no his/hers placeholder; "his own to mention" would not read |

### The approved drafts, group C (each file its own source; rows `| draft_<x> L<line> |`)

The same format limit: the ten `(his/hers)` of DIV, HIS and LIF become `(his/her) own` (one row covers every
`(his/hers)` of its line), and DIV-39's "it isn't (his/hers)" becomes "(his/her) fault", where "own" would not read.
Nothing else is fixed.

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| draft_div L53 | `(his/hers)` | `(his/her) own` | DIV-04 | no his/hers placeholder: "his own" / "her own" |
| draft_div L455 | `(his/hers)` | `(his/her) own` | DIV-38 | no his/hers placeholder: "his own" / "her own" |
| draft_div L467 | `(his/hers)` | `(his/her) fault` | DIV-39 | no his/hers placeholder; "it isn't his own" would not read |
| draft_his L287 | `(his/hers)` | `(his/her) own` | HIS-24 | no his/hers placeholder: "his own" / "her own" |
| draft_his L530 | `(his/hers)` | `(his/her) own` | HIS-44 | no his/hers placeholder (twice on the line) |
| draft_his L533 | `(his/hers)` | `(his/her) own` | HIS-44 | no his/hers placeholder (twice on the line) |
| draft_lif L470 | `(his/hers)` | `(his/her) own` | LIF-40 | no his/hers placeholder (twice on the line) |

### Likes and dislikes that match the games (the owner, 2026-11-16)

The owner asked that every like or dislike an event gives match what it does in each game, and that the outcome name the thing liked or disliked (never a job), with minimal edits (docs/event-collection/likes-dislikes-fix.md).

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| companion L2678 | `enjoy it.` | `enjoy the work.` | `c5dn002_wrong` e2 | like work (works more: VV2-VV5); the outcome names the work, not the trade |
| companion L2696 | `medicinal botany.` | `medicinal herbs.` | `c5dn004_reluctant` e2 | like herbs (no behaviour in any game, so the text names the herbs themselves) |
| companion L4535 | `enjoy leisure` | `enjoy resting` | `lbl056_retirement` e2 | like resting (no behaviour in any game, so the text names resting itself) |
| living L20687 | `use the arm well.` | `use the arm well, though heavy lifting stays hard.` | `lvlife04_crooked_arm` b1 | dislike lifting (no rubble or debris work: VV3, VV4); the outcome names the lifting |
| living L20274 | `adjustment to daily life.` | `adjustment to daily life without running.` | `lvmed05_limb_might` a1 | dislike running (every game); the outcome names the running |
| living L20281 | `in a new craft.` | `in a new craft, though running is now hard.` | `lvmed05_limb_might` c2 | dislike running (every game); the outcome names the running |

## Not applied (found by the inventories, but not a glaring grammar mistake, or not a grammar question)

These stay as the owner wrote them. Some are handled another way; the rest are listed for the owner's information.

| Line | Text | Why it is not a fix here |
|---|---|---|
| L300, L813 | double spaces | Spacing never shows; text is laid out word by word |
| L764-766, L824-830 | `(he/she)` at a sentence start | A role token is capitalised by the author (`(teacher.He/She)`): no change to the owner's words |
| L731 | `(name), the schoolteacher` | The teacher is its own role (`(teacher)`): a mapping, not an edit |
| L830 | `Oh well, live and learn, I guess.` | The narrator's voice: stylistic |
| L428 / L442 | bank O's "for (his/her)" frame | The frame is the event's structure, not grammar |
| L619-626 | (8) items start "they burst out laughing" | Routing: the authoring rules reach (8) through a lead-in page, as (3) does |
| L2152 | `the judge announces` with plural JUDGE items | Needs the owner's choice of singular judges or "the judges announce" |
| L2626-2627 | missing "(5)" route | Structural: the graph routes it |
| L2742 | `The topic is (A).` with questions in (A) | Needs a rewrite, not a fix: owner question |
| L3307-3309 | listener / baby continuity | Content: owner question |
| L4001 | `"Does it."` | Probably deliberate deadpan |
| L4913-4914 | coconut retort | Logic, not grammar: owner question |
| L5401 and others | "Go to (5)." vs "(5)" | Structural markers, never shown |
| L6522-6523 | `none of which have occurred` | Both forms are accepted English |
| L6985-6986 | `the judges do not punish the other contestant for the attempted bribe` | Reads correctly (the innocent finalist is not punished); wording only |
| L7183 | `not a proven resurrection` | Word choice ("creation of life" was suggested), not grammar |
| L7684 | `for (him/her): he made it possible to learn` | The colon is correct and "possible to learn" needs no object: not a glaring mistake |
| L7851 | `the villager finds a priceless treasure chest!` | An unlabelled fragment: owner question Q10. Shipped as a fifth "Investigate" outcome of The Secret Behind the Waterfall (its first letter capitalised, which the rules allow), with a huge tech reward (the owner's answer) |
| L8709, L8715 | living or deceased composer | Content: owner question |
| L8747 | the Chief's title in an all-games event | The game-word rule (`{@chief}`) handles it |
| L9679-9680, L9794-9798, L10187-10208 | designer rules inside display text | Ledger notes: never displayed |

## Living Event Engine

A separate source: `docs/more-island-events/Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt` (SHA-256 in
`data/living_events/SOURCE.sha256`). Line numbers in this section are that file's, so the rows below are written
"Living L..." and are not V28 fixes. The bank is described in [living-events.md](living-events.md).

Status: **waiting for the owner's approval** (the names themselves were the owner's request, 2026-11-14).

### Fix `living-frame-article`: the frame sentence with names

The 60 MIX SETUP lines (Living L24096, L24113, ... one per MIX) share one frame, for example Living L24096:

> `A warm a master parent and a private a teenager disagree about what should happen next. Their status alone does not settle the matter.`

Shipped, with the two villagers' names (owner, 2026-11-14):

> `(first), a warm master parent, and (second), a private teenager, disagree about what should happen next. Their status alone does not settle the matter.`

| Case | Before | After | Why |
|---|---|---|---|
| Living L24096 (all 60 MIX) | `A warm a master parent` | `(first), a warm master parent,` | The source doubles the article ("A warm a master parent"). The first villager's name now leads, followed by a comma; the role keeps its words without its own article (role bank, Living L23980); the comma closes the description |
| Living L24096 (all 60 MIX) | `and a private a teenager` | `, and (second), a private teenager,` | The same doubled article for the second villager; a comma before "and" because a name and its description precede it, and a comma after the description before the verb |
| Living L24130 and others | `A ambitious a caretaker` | `(first), an ambitious caretaker,` | The article follows the personality's first sound: "an" before ambitious, impatient, insecure, observant (the source always writes "A ... a") |
| Living L24113 and others | `a cautious a cook` | `(second), a cautious cook,` | "a" before a consonant: every other personality |
| Every shipped variant | `disagree about what should happen next. Their status alone does not settle the matter.` | unchanged | The owner's words, kept exactly |

### Joining words and pronouns (owner-approved, 2026-11-14)

- The only words the engine adds are the two names, `a` / `an`, the commas above and single spaces. The seed
  sentence, the personality, the role, the choices and the outcomes are the owner's lines, unchanged.
- Names appear once, in the frame. A later mention of either villager in the same event uses the role pronoun
  tokens `(first.he/she)`, `(first.him/her)`, `(first.his/her)` (or `(second. ...)`), and the name instead where a
  pronoun would be ambiguous (both villagers the same sex), as in the owner's own events. The owner's words "the
  central villager", "the novice", "the master" in the archetype lines are kept, never swapped for a name. Today's
  archetype lines mention neither villager, so no pronoun is inserted yet.
- Outside VV3 the seeds that name the chief (CEL-01, GOV-01, GOV-09, ODD-01, EMO-07) use the collection's game word
  (`{@chief}`), as in [authoring-rules.md](authoring-rules.md) section 10; VV3 shows the owner's words.
- The approach "Ask the chief to decide" (Living L23988) and MC TRA-08 ("the village chief", Living L25530, and "the
  chief" in two of its outcomes) use the same game words outside VV3.

### Fix `living-doubled-word`: a personality that repeats the role (MIX-050, MIX-054)

| Case | Before | After | Why |
|---|---|---|---|
| MIX-050 | `A confident a confident novice` | `(first), a confident novice,` | The personality repeats the role's own word; the repeat is dropped (lead decision, 2026-11-14) |
| MIX-054 | `A skeptical a skeptical observer` | `(first), a skeptical observer,` | The same |

### The owner-approved drafts, set A (2026-11-15; each file its own source)

Each draft file (`collection_lib.DRAFTS_A`) has its own line numbers; its rows start with its source id, e.g.
`| da_il07 L123 |`. `(his/hers)` has no placeholder (the engine knows `his/her`, not `his/hers`): such a line's
smallest fix that reads the same is listed here.

#### Group 1 (Inner Life II-V)

| Line | Before | After | Event | Why |
|---|---|---|---|---|

#### Group 2 (Inner Life VI-IX)

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| da_il06 L221 | `(name1) tips (his/hers) too` | `(name1) tips (his/her) own too` | il119_how_do_i_look | `(his/hers)` has no placeholder; `(his/her) own` reads the same |
| da_il07 L185 | `moves (his/hers)` | `moves (his/her) flower` | il135_matching_flower | `(his/hers)` has no placeholder; the noun it stands for reads the same |
| da_il07 L218 | `drops all of (his/hers) too` | `drops all of (his/her) coconuts too` | il138_carrying_contest | `(his/hers)` has no placeholder; the noun it stands for reads the same |
| da_il08 L167 | `This one is (his/hers), knots and all.` | `This one is (his/her) own, knots and all.` | il154_work_i_might | `(his/hers)` has no placeholder; `(his/her) own` reads the same |
| da_il09 L125 | `It's (his/hers).` | `It's (his/her) own.` | il170_shortcut | `(his/hers)` has no placeholder; `(his/her) own` reads the same |
| da_il09 L170 | `falls out of (his/hers) too` | `falls out of (his/her) canoe too` | il174_canoe_race | `(his/hers)` has no placeholder; the noun it stands for reads the same |

#### Group 3 (Inner Life X, What's That Doing Here)

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| da_wd L326 | `(his/hers)` | `(his/her) bowl` | wd27_what_bowl_fruit | `(his/hers)` has no placeholder; the noun it stands for reads the same |

#### Group 4 (Luck, Omens and Lavastones)

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| da_lo L590 | `It's still (his/hers).` | `It's still (his/her) own.` | lo48_stone_went_cold | `(his/hers)` has no placeholder; `(his/her) own` reads the same |
### Fix `living-title-ampersand`: the MC category titles

The six MC headings (Living L25161 and the five after it) use `&`, which no game's title can show. The event
title writes it `and`: "ISLAND BUSINESSES & MARKETS" is shown "Island Businesses and Markets".
