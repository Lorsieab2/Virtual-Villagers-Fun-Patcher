# Translations: does every patch text go through its own key?

Audit of 2026-11-03 for A New Home, The Lost Children, The Secret City, The Tree of Life and New Believers.

The owner's rule: every text a patch adds or changes goes through its OWN translation key and shows the translation
in the game; it is not a copy of a stock string, and generated or patched code does not copy English around the
translation.

Re-run it: `python scripts/audit_translation_keys.py` (counts), `--write` (the per-row list,
[inventory.tsv](inventory.tsv)), `--emulate` (the sentinel proof; needs the stock executables).
The tests: `tests/test_translations_sentinels.py` (helpers: `tests/translations_sentinels.py`).

## 1. How a patch text reaches the screen

There are three ways, and every row of `data/translations/patcher_strings.json` is exactly one of them
(`scripts/scan_patch_text.py` `route_of`; the key rows say `"route": "key"` in the JSON):

| Route | How | Rows |
| --- | --- | --- |
| key | The companion asks `VVFP Translations.dll` for the row by its stem (`vvfp_tr`, `vvfp_trf`, `ce_tr_printf`: `native/shared/vvfp_translate.h`), passing the row's English; the DLL answers only when the key's hash is that English. | 76 |
| patch | An exe patch's own text at an address (`patch/0x<va>`): the DLL writes the translation over the live text there, only at a trusted (address, hash) pair (`tr_patch_sites.inc`). | 42 |
| content | The text is drawn by the game's text routine or put in a Windows dialog, and the DLL finds its row by the English it sees (`VvfpTranslateText` from the Unicode Text draw hooks; the dialog hook on `WM_INITDIALOG`, `WM_SETTEXT`, list and combo adds). | 5,934 |

6,052 rows, 8,777 (row, game) pairs. Per game (rows offered in the "Make a translation" template, after section 3):

| Game | rows | key | patch | content | left out as dead |
| --- | ---: | ---: | ---: | ---: | ---: |
| A New Home | 1,577 | 59 | 5 | 1,513 | 546 |
| The Lost Children | 2,051 | 52 | 5 | 1,994 | 807 |
| The Secret City | 1,806 | 33 | 16 | 1,757 | 681 |
| The Tree of Life | 1,623 | 32 | 15 | 1,576 | 629 |
| New Believers | 1,720 | 32 | 1 | 1,687 | 693 |

By source (rows): Story / Cheat Upgrades 4,274; Origins (five DLLs) 1,621; Repair / last-names cross-check 49;
exe patches 42 `patch/` + 10 `vvfp.exepatch/` (rebuilt executables, found by content); Cause of Death 20;
Change Appearance 19; Story bridge 6; Storytelling 4; dialog kit 3; Show Parents 3; Both Factions 1.

Not patch rows, but patch-changed text that reaches the screen through the game's own slot:

| Patch | Slots | Key |
| --- | ---: | --- |
| Misc text fixes (A New Home) | 4 (`table/319`, `/21`, `/15`, `/3`) | `table/<id>~<hash of the PATCHED English>` |
| Guardians of Isola Rewrite (New Believers) | 247 `sm/<eName>` | `sm/<eName>~<hash of the patched English>` |
| Optional Text Changes (The Tree of Life) | 14 `sm/<eName>` | `sm/<eName>~<hash of the patched English>` |

These keep the game's slot but not its translation: the key's hash is the hash of the English the player's game
shows, the DLL uses a row only when that is the live English, and the template is made from the patched copy. The
translation of the stock sentence therefore never shows on the patched text (proved for the four A New Home slots:
`PatchedSlotTests`; the rule itself: `test_table_lookup_translates_and_falls_back`).

Text that is deliberately not translated (logs, sidecar files, folder names, names written into records) is listed
with a reason in `data/translations/patch_text_exclusions.json`; `tests/test_translations_patch_coverage.py` fails on
any visible string that is neither a row nor excluded.

## 2. Violations found, and what was done

| # | Violation | Rows | Fixed? |
| --- | --- | --- | --- |
| V1 | **A key row leaked into the content map.** A row a companion asks for by key was also put in the map the draw and dialog hooks use, so its English translated every other text of that shape. The worst: Show Parents' `%s of %s` (a pattern) turned "Type an amount of food from 1 to 7." and a dozen other patch texts into the parentage translation; "Disease", "Son", "Time Skip" and the rest took over any identical text. | the 76 key rows; found by the sentinel run (about eight other rows of A New Home lost their own sentinel to it) | Yes. `VVFP Translations.dll` keeps a key row out of the content map (`tr_key_stems.inc`, generated from `"route": "key"`). `ContentMapTests.test_a_row_asked_for_by_key_never_translates_other_texts` |
| V2 | **A general pattern hid a specific one.** Of two pattern rows that both match a text, the last-read won: "Each villager the game checks: %s." took the text of its own longer sentence; "... Cancel." took "... Cancel.%s"'s. | a handful per game | Yes. The most specific match (most literal bytes, then fewest conversions) wins, whatever the order. `ContentMapTests.test_the_most_specific_pattern_wins_whatever_the_order` |
| V3 | **Rows that did nothing.** Content text is found by its English and the DLL keeps one translation per English (the first row), so a later row with the same English, or with the same English except `%d` / `%i` / `%u`, or equal to one of the game's own strings, never showed its translation, though a translator was asked to translate it. | 3,356 (row, game) pairs: 546 / 807 / 681 / 629 / 693 | Yes, in the template: `vv_translations.content_shadowed` leaves them out (one row per English; a key or patch row is never left out). The editor shows fewer rows; nothing the game showed changes. `TemplateTests` |
| V4 | **German, Spanish and French "Listening to a story" labels were literals.** A New Home's Storytelling returned `LISTEN_DE` / `_ES` / `_FR` bare (and `LISTEN_EN` when the game's string table was not ready), so the rows `vvfp_storytelling.x.s1..s3` existed in the template and did nothing. | 3 rows (+ the English fallback) | Yes. Each is asked for by its own key; `RouteTests.test_storytelling_labels_in_every_language_are_asked_for_by_key`; `VVFP Storytelling.dll` rebuilt |
| V5 | **Sentinel rejected: `% e` in a label.** The Lost Children's Custom Island Event option labels ("... 20% each ...") contain a printf-looking `% e`; the format check makes a translator keep it. | `VV2_OC_OPTIONS.43/.44/.46/.47` | Proved (the sentinel keeps the `% e`); the English is left as it is |

Found while checking and not fixable in this change:

| # | Finding | Rows | Why not fixed here |
| --- | --- | --- | --- |
| R1 | **Owner-drawn labels are never translated.** "(None)", "(none)", "(no change)" and "No change" are drawn with `DrawTextA` straight to the device context (neither the dialog hook nor the Unicode Text draw hooks see GDI): `vv1_origins_icons.c` 2731, 3329; `vv2_origins_icons.c` 1350, 1475, 2892, 2897 (via `vv2_draw_label`); `vv4_origins_icons.c` 1520, 2718; `vv5_task9_origins.c` 1114, 2001. They are template rows (content) that nothing looks up at the draw. | 11 sites in four DLLs (A New Home / The Lost Children share one), rows `appearance_draw_from.s0`, `forall_draw_one.s0`, `vv2_appearance_draw.s0`, `caf_draw.s0`, `appearance_draw_mask_cell.s0`, `fa_draw_cell.s0`, `vv5_task9_origins.appearance_draw.s0`, `caf_draw.s0` | Each needs `vvfp_tr(stem, english, 0)` at the draw and a rebuild of the Origins DLL, which is pinned by the Origins features, the Expanded Time Warp builds, `build_release.py` and the transparency log: a binary change in files other branches are changing. Do it after they merge. |
| R2 | **Content rows equal to a string of the game** (for example "Farming", "Done", "Buy", "Unknown", "Celebrating") share the game's translation instead of having their own: 104 / 166 / 241 / 202 / 282 (row, game) pairs. The translator sees one row. | 995 pairs | A separate translation would need a `vvfp_tr` key at every such site in the nine companions (about a thousand edits and rebuilds of every DLL); the shown translation is a real translation, only not separable. |
| R3 | **Content rows drawn by the game's own text routine** reach the screen only through the Unicode Text companion's hooks. The Translations patch has no dependency on it. The rows whose text the game draws are all key rows (Cause of Death, Show Parents, Time Skip, Storytelling, Both Factions) and do not need it; no content row is known to be drawn by the game's routine, but the inventory marks every content row "a patcher window" without proof. | unclassified | Needs a per-row look at where each content string goes. |
| R4 | **A button created after the dialog opened** (`story_bridge.h` `vvfp_story_button`, `CreateWindowExA` with the text) is translated only when the dialog hook's `EnumChildWindows` runs after it is created. Not proven. | 2 rows ("Pick Island Event", "Custom Island Event") | Needs a live test. |

## 3. The sentinel proof

`tests/test_translations_sentinels.py`, `SentinelTests` (needs unicorn, pefile, the stock executables, the built DLL;
skips without them, as `test_translations_runtime.py` does):

1. The game's template patch rows (`patcher_rows_of_template`, the same filter the editor uses) each get a UNIQUE
   sentinel (`Z0042`, then the English's placeholders and variables, so the row checks pass; short enough for an exe
   patch's own bytes).
2. They are written as a `Translation.txt` in the emulated game (the stock executable, the real
   `VVFP Translations.dll`), and the DLL starts as `VvfpStartup` does.
3. Each row is asked for the way its route asks: **key** by `VvfpTranslateKey` / `VvfpTranslateKeyText` with its stem
   and English (what `vvfp_tr` / `vvfp_trf` / `ce_tr_printf` call); **patch** by writing the English at its address
   first and reading the text back there; **content** by `VvfpTranslateText` with the English as the game prints it
   (placeholders filled, `%%` as `%`), which is what the draw hooks and the dialog hook call.
4. A row is PROVEN when what comes back is its own sentinel. The other tests prove that the draw and fill paths are
   there: every text routine the Unicode Text companion hooks offers its text to `VvfpTranslateText`; the dialog
   hook handles `WM_INITDIALOG`, `WM_SETTEXT`, list and combo adds; every key lookup in the sources passes its row's
   stem and exactly its row's English; `tr_patch_sites.inc` and `tr_key_stems.inc` are what the generator makes.

Result of the final run (`python scripts/audit_translation_keys.py --emulate`):

| Game | key proven | patch proven | content proven | unproven |
| --- | ---: | ---: | ---: | ---: |
| A New Home | 59 | 5 | 967 | 0 |
| The Lost Children | 52 | 5 | 1,187 | 0 |
| The Secret City | 33 | 16 | 1,076 | 0 |
| The Tree of Life | 32 | 15 | 947 | 0 |
| New Believers | 32 | 1 | 994 | 0 |

Before the fixes in section 2 the same run left 14 (A New Home), 22 (The Lost Children), 9 (The Secret City), 12
(The Tree of Life) and 7 (New Believers) rows without their sentinel: V1, V2, the `%d` / `%u` twins of V3 and the
two harness cases below. The exe patches that rewrite the same bytes in two builds of The Tree of Life (the Origins
patch and the Expanded Time Warp build; never in one game) are proved one build at a time.

Also proved: the four A New Home slot rewrites (`PatchedSlotTests`), key rows never answering for other text and
the most specific pattern winning (`ContentMapTests`).

## 4. What remains, and what cannot be proven

**Unprovable by this harness: 0 rows in the emulated layer.** Every offered row of every game shows its own
sentinel. What no row can be proven for here, and why:

- the Windows-dialog and game-draw step itself (no game window, no GDI in the emulator): static checks only;
- R1: the 11 owner-drawn `DrawTextA` literals, whose rows are proven in the DLL but never looked up by the code
  that draws them (found by reading the sources, not by the sentinel);
- R2: 995 (row, game) pairs equal to the game's own strings share the game string's row;
- R3 and R4 as above.

- **The last step is not emulated.** The sentinel reaches `VvfpTranslateText`, `VvfpTranslateKey` or the patched
  address; that the game's own draw routine then prints it, and that a Windows dialog's controls are filled by the
  hook, rests on the static checks above and on the owner's live play. The harness has no game window and no GDI.
- R1 to R4 above.
- The French (TEST) files in `translations/` were made on the older template; rows the template no longer offers
  (V3) are ignored as "no such line" by the validator, which is what the DLL already did.
