# Isola Grand Event Collection: grammar fixes for the owner

These are the only edits the collection makes to the owner's text, apart from the mapping rules in
[authoring-rules.md](authoring-rules.md) (placeholders, pools, game words, typography). Each is a **glaring** mistake
one of the three inventories found: a broken sentence, a wrong word, a missing placeholder, a pronoun that does not fit.
Nothing stylistic is changed.

Line numbers are the frozen source's
(`docs/more-island-events/Virtual_Villagers_Isola_Grand_Event_Collection_v26_user_source_credited.txt`, SHA-256 in
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

### Part 3b (lines 8490-10571: V18-V26)

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
