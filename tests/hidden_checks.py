"""The checks every game's "Hidden keys, clicks and cheats" test runs (tests/test_game_mechanics_hidden_vv<N>.py mix this
into a unittest.TestCase and set the class attributes below).

  * every entry, its label and its sub-lines' labels are pinned (PINNED), the tip lists' labels counted (TIP_COUNTS),
    and every DEAD item pinned by name (DEAD) so it can never turn into a player-facing claim;
  * every key each input slot tests, read from the stock exe's own compares and jump tables, is the module's own list,
    and every key a live slot tests is named by a Key entry;
  * the event pump makes exactly the 23 keys the page names;
  * every tip in the game's string table is quoted, word for word, and the random-tip pickers draw what the page says;
  * the patcher's patches are on or off by default as the patcher has them;
  * the words: no vague wording, every length of time says real-life (the units rule)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_hidden as hidden  # noqa: E402
import island_event_exe as exe_reader  # noqa: E402

E, C, U, O, D = "VERIFIED-E", "VERIFIED-C", "UNCONFIRMED", "OWNER", "DEAD"


class HiddenChecks:
    MODULE = None                 # the game's vv_game_mechanics_hidden_vv<N> module
    GAME = 0
    PINNED: tuple = ()            # (kind, name, label, (sub-line labels, ...)) for every entry but the tip lists
    TIP_COUNTS: dict = {}         # tip list name -> {label: count}
    DEAD: tuple = ()              # every DEAD item: an entry's name, or a sub-line's first words
    PICKERS: tuple = ()           # (start, end, n, base): the random-tip pickers
    SPOT: tuple | None = None     # (constructor start, end, first field offset): the tip spot's rectangle
    TEXT_BOX = 0                  # the name boxes' input slot (its characters are named by "Typing in a name box")
    BANNED = r"probabl|perhaps|presumab|(?<!equally )likely|\betc\b|some effect|not (yet )?worked out"

    # ------------------------------------------------------------------ the page's own entries
    def entries(self):
        return self.MODULE.entries()

    def test_every_entry_and_its_label(self) -> None:
        got = tuple((e.kind, e.name, hidden.label(e),
                     tuple(hidden.label_of(v, t.startswith(hidden.DEAD_MARK)) for t, v in e.subs))
                    for e in self.entries() if e.name not in self.TIP_COUNTS)
        self.assertEqual(got, self.PINNED)

    def test_tip_lists_and_their_labels(self) -> None:
        got = {}
        for e in self.entries():
            if e.name in self.TIP_COUNTS:
                counts: dict[str, int] = {}
                for _t, v in e.subs:
                    counts[hidden.label_of(v)] = counts.get(hidden.label_of(v), 0) + 1
                got[e.name] = counts
        self.assertEqual(got, self.TIP_COUNTS)

    def test_dead_items_stay_dead(self) -> None:
        found = [e.name for e in self.entries() if e.dead]
        for e in self.entries():
            found += [t[len(hidden.DEAD_MARK):][:40] for t, _v in e.subs if t.startswith(hidden.DEAD_MARK)]
        self.assertEqual(tuple(found), self.DEAD)
        facts = self.MODULE.hidden_facts()
        dead = [f for f in facts if hidden.label(f) == D]
        self.assertEqual(len(dead), len(self.DEAD))
        for fact in dead:
            self.assertTrue(fact.text.startswith(hidden.DEAD_MARK), fact.text)
            self.assertEqual(fact.verified, gm.CODE)          # traced in the code; never shown as UNCONFIRMED

    def test_the_facts_carry_the_labels(self) -> None:
        facts = self.MODULE.hidden_facts()
        self.assertTrue(facts)
        self.assertTrue(all(f.group == hidden.HIDDEN == self.MODULE.HIDDEN for f in facts))
        self.assertEqual(self.MODULE.HIDDEN, "Hidden keys, clicks and cheats")
        rendered = gm.render(facts)
        for fact in facts:
            self.assertIn(hidden.label(fact), (E, C, U, O, D))
            self.assertEqual(hidden.label(fact) == U, not fact.confirmed)
        self.assertEqual(rendered.count(gm.UNCONFIRMED + "  "), sum(1 for f in facts if hidden.label(f) == U))
        self.assertEqual(len([f for f in facts if not f.sub]), len(self.entries()))

    def test_the_words(self) -> None:
        for fact in self.MODULE.hidden_facts():
            text = fact.text
            quoted_tip = re.match(r"\d+: \"", text)                # a tip, quoted as the game words it
            with self.subTest(text=text[:70]):
                if not quoted_tip:
                    self.assertNotRegex(text.lower(), self.BANNED)
                self.assertNotRegex(text, r"game (hours?|minutes?|seconds?)\b|\bclock (seconds|units)\b")
                for m in re.finditer(r"\b\d[\d,.]* (seconds?|minutes?|hours?)\b", text):
                    self.assertRegex(text[max(0, m.start() - 40):m.end() + 40], r"real-life|in-game|of play")
                self.assertNotIn("{", text)

    def test_default_off_matches_the_patcher(self) -> None:
        self.assertTrue(set(self.MODULE.DEFAULT_OFF) <= set(self.MODULE.PATCHES))
        for feature in self.MODULE.PATCHES:
            self.assertNotEqual(gm.feature_name(feature), feature, f"{feature} has no name in the catalog")
            self.assertIn(feature, {e.feature for e in self.entries()})
        try:
            import vv_fun_patcher_gui as gui
        except Exception as exc:  # noqa: BLE001 -- no display or Tk: the GUI module cannot be imported here
            self.skipTest(f"vv_fun_patcher_gui could not be imported: {exc}")
        for feature in self.MODULE.PATCHES:
            self.assertEqual(feature in self.MODULE.DEFAULT_OFF, not gui.default_fun_patch_selection(feature), feature)

    def test_a_village_says_whether_the_patch_is_in(self) -> None:
        village = exe_reader.village(self.GAME, installed=frozenset(self.MODULE.PATCHES[:1]))
        text = gm.render(self.MODULE.hidden_facts(village))
        self.assertIn("by default; in this game)", text)
        self.assertIn("by default; not in this game)", text)
        self.assertNotIn("in this game)", gm.render(self.MODULE.hidden_facts()))

    # ------------------------------------------------------------------ read from the stock exe
    def need_exe(self) -> None:
        if not exe_reader.available(self.GAME):
            self.skipTest("the stock exe or capstone/pefile is absent")

    def test_every_key_each_slot_tests(self) -> None:
        self.need_exe()
        import hidden_keys_exe as keys
        handlers = dict(self.MODULE.KEY_HANDLERS)
        handlers.update(getattr(self.MODULE, "DEAD_HANDLERS", {}))
        for start, (end, listed) in handlers.items():
            with self.subTest(slot=hex(start)):
                self.assertEqual(keys.keys_tested(self.GAME, start, end), listed)

    def test_every_key_a_live_slot_tests_is_named(self) -> None:
        names = " | ".join(e.name for e in self.entries() if e.kind == hidden.KEY)
        for start, (_end, listed) in self.MODULE.KEY_HANDLERS.items():
            for key in listed:
                with self.subTest(slot=hex(start), key=key):
                    if key >= 1000:
                        self.assertRegex(names, rf"\b{re.escape(hidden.COMMAND_KEYS[key])}\b")
                    elif start == self.TEXT_BOX:
                        self.assertIn("Typing in a name box", names)
                    elif chr(key).isdigit():
                        self.assertIn("1 to 9", names)
                    elif key == 32:
                        self.assertIn("Space", names)
                    else:
                        self.assertRegex(names, rf"(^|[ (,]){re.escape(chr(key).upper() if chr(key) != 'g' else 'g')}"
                                                rf"([ ,)]|$)")

    def test_the_pump_makes_the_keys_the_page_names(self) -> None:
        self.need_exe()
        import hidden_keys_exe as keys
        start, end = self.MODULE.PUMP
        self.assertEqual(keys.commands_made(self.GAME, start, end), frozenset(hidden.COMMAND_KEYS))
        self.assertEqual(self.entries()[0].name, "Which keys reach the game")
        self.assertIn(f"{start:#x}", self.entries()[0].text)

    def test_every_tip_is_quoted(self) -> None:
        self.need_exe()
        import hidden_keys_exe as keys
        m = self.MODULE
        strings = exe_reader._strings(self.GAME)
        random_ids = tuple(range(m.RANDOM_BASE, m.RANDOM_BASE + m.RANDOM_COUNT))
        self.assertEqual(tuple(i for i, _t in m.RANDOM_TIPS), random_ids)
        for tip_id, text in m.RANDOM_TIPS:
            self.assertEqual(text, keys.fold(strings[tip_id]))
        popup = {tip[0]: tip for tip in m.POPUP_TIPS}
        if self.GAME >= 3:
            names = keys.string_names(self.GAME)
            randoms = sorted((int(n[10:]), i) for i, (n, t) in names.items() if re.fullmatch(r"eRandomTip\d+", n))
            self.assertEqual(tuple(i for _n, i in randoms), random_ids)
            wanted = {i for i, (n, t) in names.items() if re.match(r"eT?Tip", n) and keys.fold(t)}
            for i in wanted:
                self.assertEqual(popup[i][1], names[i][0])
        else:
            first, last = m.POPUP_TIPS[0][0], m.POPUP_TIPS[-1][0]
            wanted = {i for i in range(first, last + 1) if keys.fold(strings.get(i, ""))}
        self.assertEqual(set(popup), wanted)
        for tip_id, tip in popup.items():
            self.assertEqual(tip[-1], keys.fold(strings[tip_id]))
        # Every quoted tip is on the page, word for word.
        text = gm.render(m.hidden_facts())
        for tip in tuple(m.RANDOM_TIPS) + tuple(m.POPUP_TIPS):
            self.assertIn(f"{tip[0]}: \"{gm.tidy(tip[-1])}\"", text)

    def test_the_tip_pickers(self) -> None:
        self.need_exe()
        import hidden_keys_exe as keys
        for start, end, n, base in self.PICKERS:
            with self.subTest(picker=hex(start)):
                self.assertIn((n, base), keys.random_picks(self.GAME, start, end))
                self.assertIn(f"rand({n}) + {base}", gm.render(self.MODULE.hidden_facts()))

    def test_no_store_slot_rerolls(self) -> None:
        """The store-like screens' slots draw no random number, so nothing there can redraw what is offered."""
        self.need_exe()
        listed = " ".join(e.text for e in self.entries() if e.name == "Store screens: no redraw or reroll key").lower()
        self.assertIn(f"({self.MODULE.RAND:#x})", listed)
        for start, end in self.MODULE.STORE_SLOTS:
            with self.subTest(slot=hex(start)):
                calls = [o for _a, m, o in exe_reader.exe(self.GAME).disasm(start, end) if m == "call"]
                self.assertNotIn(f"{self.MODULE.RAND:#x}", calls)
                self.assertIn(f"{start:#x}", listed)

    def test_the_tip_spot(self) -> None:
        if self.SPOT is None:
            return
        self.need_exe()
        import hidden_keys_exe as keys
        start, end, offset = self.SPOT
        stores = keys.dword_stores(self.GAME, start, end)
        x0, y0, x1, y1 = getattr(self.MODULE, "MASK", None) or self.MODULE.SPOT
        self.assertEqual((stores[offset], stores[offset + 4], stores[offset + 8], stores[offset + 12]), (x0, y0, x1, y1))
