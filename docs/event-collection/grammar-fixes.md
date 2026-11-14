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

| Line | Before | After | Event | Why |
|---|---|---|---|---|
| L104 | `is.... ` | `is ` | The Cooking Contest | Four stray dots break the sentence "(Name1) is (A) (B)." (twice on the line) |
| L135 | `works things out.` | `works things out` | The Cooking Contest, bank B | A full stop in the middle of the sentence the item is inserted into |
| L138 | `has tried, failed and succeeded throughout life` | `who has tried, failed and succeeded throughout life` | The Cooking Contest, bank B | Every other B item starts "that" / "who"; without it the sentence has no verb link |
| L163 | `has reliable friends.` | `has reliable friends` | The Cooking Contest, bank C | Stray full stop mid-sentence |
| L165 | `taught them well` | `taught (him/her) well` | The Cooking Contest, bank C | "them" for one contestant |
| L168 | `taught them some tips` | `taught (him/her) some tips` | The Cooking Contest, bank C | "them" for one contestant |
| L171 | `uses their strong emotions` | `uses (his/her) strong emotions` | The Cooking Contest, bank C | "their" for one contestant |
| L188 | `value their work` | `value (his/her) work` | The Cooking Contest, bank F | "their" for one contestant (inventory part 1 said L189) |
| L189 | `value their purpose` | `value (his/her) purpose` | The Cooking Contest, bank F | "their" for one contestant (inventory part 1 said L190) |
| L263 | `the charismatic crowner` | `the charismatic contender` | The Cooking Contest, bank G | "crowner" is not a word; "contender" is the inventory's suggestion (inventory part 1 said L264) |
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
| L4976 | `ARBOR-DAY` | `ARBOR DAY` | The Arbor-Day Festival | Spelling of the title (inventory part 2 also suggests a rename; that is the owner's call) |
| L6986 | `the other contestant for the attempted bribe.` | `the other finalist, who had no part in the bribe.` | V13-A The Judge Who Feared No Dish | As written it says the innocent finalist is not punished "for the attempted bribe" they did not make |
| L7183 | `not a proven resurrection` | `not a proven creation of life` | V13-C "It's Alive!" | Nothing was ever dead, so nothing was resurrected |
| L7684 | `for (him/her): he made it possible to learn` | `for (him/her); he made it possible for (him/her) to learn` | V14-05 The Lesson Nobody Expected | Run-on with a missing object |
| L8206 | `The Children are asked` | `The children are asked` | V17-B The Children's Jury | Stray capital |
| L8589 | `The judges present one question:` | `The judges present one of these questions:` | V18-03 The Great Question | Four questions follow; one is drawn |
| L9434 | `The subject recognizes` | `(Name2), the subject, recognizes` | V21 C2 The Statue That Divided the Village | "(himself/herself)" needs a named villager |
| L9453 | `forgive (him/her).` | `forgive (Name2).` | V21 C2 The Statue That Divided the Village | "(him/her)" refers to nobody named |
| L9592 | `The subject objects` | `(Name2), the subject, objects` | V22-1 The Great Isolan Drawing Competition | "(his/her)" needs a named villager |

### Found while authoring the pilot (not in the inventories)

Placeholders written without their parentheses would show the words "his/her" / "he/she" instead of the villager's
own pronoun; two stray full stops sit inside a slash list or mid-sentence.

| Line | Before | After | Event | Why |
|---|---|---|---|---|
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
| L7851 | `the villager finds a priceless treasure chest!` | An unlabelled fragment: owner question Q10 |
| L8709, L8715 | living or deceased composer | Content: owner question |
| L8747 | the Chief's title in an all-games event | The game-word rule (`{@chief}`) handles it |
| L9679-9680, L9794-9798, L10187-10208 | designer rules inside display text | Ledger notes: never displayed |
