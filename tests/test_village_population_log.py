"""The Village Population roster must agree with the layouts it borrows.

The owner asked for "a log of all the villagers in the village" with name, head
and body, parents where present, likes and dislikes, and skill values -- titled
"Village Population", 256 villagers per file.

Every offset this exporter uses is already established and shipped elsewhere:
the villager array RVA, record base, stride, slot count, active flag and skill
table come from the statistics companion's Village Elders row, and the name,
head and body come from the parentage companion's layout table. So these guards
do not re-derive them. They check that the two copies AGREE, which is the
failure this arrangement actually invites -- a later change to one companion
silently leaving the other reading a stale offset, which does not crash and
does not look wrong, it just logs 150 wrong numbers.
"""

from __future__ import annotations

import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POPULATION = ROOT / "native/population_export/population_export.c"
PARENTAGE = ROOT / "native/parentage_export/parentage_export.c"
STATISTICS = ROOT / "native/statistics_export/statistics_export.c"
STOCK = ROOT / "research/stock-executables"

EXES = {
    1: "Virtual Villagers - A New Home.exe",
    2: "Virtual Villagers - The Lost Children.exe",
    3: "Virtual Villagers - The Secret City.exe",
    4: "Virtual Villagers - The Tree of Life.exe",
    5: "Virtual Villagers - New Believers.exe",
}

# VV1 and VV2 reach their array through a GLOBAL holding a pointer to it,
# lazily allocated; VV3, VV4 and VV5 have the array itself at a fixed RVA.
POINTER_GAMES = {1, 2}


def _population_rows() -> dict[int, dict[str, int]]:
    """Each supported game's row, read from the exporter's own table."""
    source = POPULATION.read_text(encoding="utf-8")
    table = source[source.index("GAME_LAYOUTS[6] = {"):]
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.DOTALL)
    rows: dict[int, dict[str, int]] = {}
    for match in re.finditer(
        # Identifiers are allowed through because each row now names its
        # preference list (PREFERENCES_47 / _62 / _79) or NULL alongside the
        # numeric offsets. The value extraction below still takes only the
        # numbers, so the names do not shift the positional mapping.
        r'\{\s*1,\s*((?:0x[0-9A-Fa-f]+u?|\w+|,|\s)+?)"Virtual Villagers (\d)"',
        table,
        re.DOTALL,
    ):
        values = [
            int(v.rstrip("u"), 0)
            for v in re.findall(r"0x[0-9A-Fa-f]+u?|\b\d+u?\b", match.group(1))
        ]
        names = [
            "villagers_rva", "villagers_rva_is_pointer",
            "record_base", "stride", "slots",
            "active", "age", "head", "body",
            "name", "name_capacity",
            "father_name", "father_name_capacity",
            "father_head", "father_body",
            "skills", "skill_count", "skills_are_float",
            "likes", "dislikes", "preference_slots",
        ]
        rows[int(match.group(2))] = dict(zip(names, values))
    return rows


class VillagePopulationLayoutsAgreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = _population_rows()

    def test_every_game_is_supported(self) -> None:
        """All five, once VV1's and VV2's array globals were located."""
        self.assertEqual(sorted(self.rows), [1, 2, 3, 4, 5])

    def test_only_vv1_and_vv2_go_through_a_pointer(self) -> None:
        """Getting this backwards is silent and total.

        Treating a pointer global as the array walks the pointer variable
        itself and reads 256 records of neighbouring .data; treating the array
        as a pointer dereferences a villager's first four bytes as an address.
        Neither crashes reliably and neither looks wrong in the manifest.
        """
        for game, row in self.rows.items():
            with self.subTest(game=game):
                self.assertEqual(
                    bool(row["villagers_rva_is_pointer"]),
                    game in POINTER_GAMES,
                    "game %d has the wrong array-access kind" % game,
                )

    def test_every_offset_matches_the_parentage_layout(self) -> None:
        """Name, head, body and the father copies are shared with parentage."""
        parentage = PARENTAGE.read_text(encoding="utf-8")
        table = parentage[parentage.index("GAME_LAYOUTS[6] = {"):]
        blocks = dict(
            (int(num), re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL))
            for body, num in re.findall(
                r"\{([^{}]*?)L\"Virtual Villagers (\d) Parentage Log\"",
                table,
                re.DOTALL,
            )
        )
        for game, row in self.rows.items():
            with self.subTest(game=game):
                values = [
                    int(v, 0)
                    for v in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", blocks[game])
                ]
                # supported, stride, slots, record_base, active, age, head,
                # body, id, name, name_capacity, father, ...
                self.assertEqual(row["stride"], values[1], "stride")
                self.assertEqual(row["slots"], values[2], "slots")
                self.assertEqual(row["record_base"], values[3], "record base")
                self.assertEqual(row["active"], values[4], "active flag")
                self.assertEqual(row["age"], values[5], "age")
                self.assertEqual(row["head"], values[6], "head")
                self.assertEqual(row["body"], values[7], "body")
                self.assertEqual(row["name"], values[9], "name")
                self.assertEqual(row["name_capacity"], values[10], "name cap")
                # The father block, which the first version of this guard did
                # not compare at all. A stale or swapped offset here prints
                # another field as the father's name or appearance, and every
                # other guard still passes -- the log just quietly describes
                # the wrong villager.
                #
                # The parentage row's order is father_kind, father,
                # father_key_capacity, litter, father_head_copy,
                # father_body_copy. father_kind is a bare identifier rather
                # than a number, so the numeric list skips it: values[11] is
                # `father`, [12] father_key_capacity, [13] litter, [14] head
                # copy, [15] body copy.
                self.assertEqual(
                    row["father_name"], values[11], "father name")
                # The father block is optional. VV1 declares none at all --
                # it records nothing about the father in the mother's record --
                # so its four father fields are zero here and there is nothing
                # to compare. Parentage still carries a father OFFSET for VV1
                # because its own row uses FATHER_BY_CAPTURE, which reads the
                # father from a captured pointer rather than from her record.
                if row["father_name"] == 0:
                    continue
                # Parentage spells 0 as "same as the villager's own name".
                # This exporter has no such defaulting rule and states the
                # number, so compare against the resolved value.
                expected_cap = values[12] or values[10]
                self.assertEqual(
                    row["father_name_capacity"], expected_cap,
                    "father name capacity")
                self.assertEqual(
                    row["father_head"], values[14], "father head copy")
                self.assertEqual(
                    row["father_body"], values[15], "father body copy")

    def test_every_array_and_skill_offset_matches_the_statistics_row(self) -> None:
        """Compare POSITIONALLY inside each game's own call.

        Two earlier versions of this guard were too weak, and Codex caught
        both. The first gathered every hexadecimal literal in the statistics
        source into one set and asked whether each offset appeared anywhere in
        it, which passes with VV3's and VV4's array bases swapped because both
        literals are still somewhere in the file. The second narrowed that to
        a fixed-size window after the game's title, but the window is wider
        than the call: VV3's reaches VV4's title after 834 characters. Giving
        VV3 the VV4 skill offset 0x1C5C still passed the whole suite.

        Membership is the flaw in both. An offset appearing *somewhere* says
        nothing about it appearing in the *right argument slot*, and a wrong
        layout is exactly the case where the value is real but misplaced. So
        the call's argument list is parsed by matching its parentheses and the
        arguments are compared by position.
        """
        statistics = STATISTICS.read_text(encoding="utf-8")
        stripped = re.sub(r"/\*.*?\*/", "", statistics, flags=re.DOTALL)

        def arguments_of_the_call_naming(title):
            """Every top-level argument of the call that passes `title`."""
            quoted = '"%s"' % title
            self.assertIn(
                quoted, stripped, "cannot locate the call naming %r" % title)
            self.assertEqual(
                stripped.count(quoted), 1,
                "%r must name exactly one call" % title)
            at = stripped.index(quoted)

            # Back up to the '(' that opens the enclosing call, skipping any
            # nested call that closes before it.
            depth, index = 0, at
            while index > 0:
                index -= 1
                if stripped[index] == ")":
                    depth += 1
                elif stripped[index] == "(":
                    if depth == 0:
                        break
                    depth -= 1
            opening = index
            self.assertEqual(
                stripped[opening], "(",
                "unbalanced parentheses before %r" % title)

            # Forward to its match.
            depth, index = 0, opening
            while index < len(stripped):
                if stripped[index] == "(":
                    depth += 1
                elif stripped[index] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                index += 1
            self.assertLess(
                index, len(stripped), "unterminated call naming %r" % title)

            # Split on commas at depth zero, so a nested call stays one
            # argument rather than scattering its own operands into the list.
            body = stripped[opening + 1:index]
            arguments, depth, current = [], 0, ""
            for character in body:
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                if character == "," and depth == 0:
                    arguments.append(current.strip())
                    current = ""
                else:
                    current += character
            arguments.append(current.strip())
            return [argument for argument in arguments if argument]

        def as_number(argument):
            return int(argument.rstrip("uU"), 0)

        # VV3 and VV4 both call the shared write_later_game with the same
        # signature, so the villager-layout arguments sit at fixed positions.
        # Asserted rather than searched for, because a shifted argument list is
        # itself a defect this guard should fail on.
        # Each position is one higher than it was before the village header
        # was added: write_later_game gained a `village` parameter in third
        # place, so every argument after `manager` shifted by one. The count
        # assertion above is what forces this table to be revisited rather
        # than silently reading the neighbouring argument.
        positions = {
            "villagers_rva": 21,
            "stride": 23,
            "slots": 24,
            "skills": 27,
            "skill_count": 28,
        }
        titles = {
            # VV1 and VV2 are absent: the statistics companion has no Village
            # Elders row for either and never walks their villager arrays, so
            # there is no second copy of these offsets to agree with.
            3: "Virtual Villagers - The Secret City",
            4: "Virtual Villagers - The Tree of Life",
        }
        for game, title in sorted(titles.items()):
            with self.subTest(game=game):
                row = self.rows[game]
                arguments = arguments_of_the_call_naming(title)
                self.assertEqual(
                    len(arguments), 33,
                    "game %d's statistics call changed shape; the positional "
                    "offsets below are no longer trustworthy" % game)
                self.assertEqual(
                    arguments[3], '"%s"' % title,
                    "argument 3 must be the title")
                for field, position in sorted(positions.items()):
                    self.assertEqual(
                        row[field], as_number(arguments[position]),
                        "game %d's %s must equal statistics argument %d"
                        % (game, field, position))

        # VV5 has its own writer, so its offsets are not passed as arguments.
        # Its villager RVA is still shared, and is compared against the single
        # literal the statistics source uses for it.
        with self.subTest(game=5):
            self.assertEqual(
                stripped.count("0x154148u"), 1,
                "VV5's villager array RVA must appear exactly once")
            self.assertEqual(self.rows[5]["villagers_rva"], 0x154148)

        # No two games may share a villager array base. Positional equality
        # alone still passes if a row and its call are given the same wrong
        # base, and that reads one game's records for another.
        bases = {}
        for game, row in self.rows.items():
            bases.setdefault(row["villagers_rva"], []).append(game)
        for base, games in sorted(bases.items()):
            with self.subTest(base=base):
                self.assertEqual(
                    len(games), 1,
                    "games %s share the villager array base %#x"
                    % (games, base))

    def test_the_roster_is_exported_on_every_path_past_the_statistics_file(
        self,
    ) -> None:
        """A statistics failure must not suppress the roster.

        The two exports are separate files with separate failure modes. The
        statistics destination can be held open by another process without
        delete sharing, or its temporary can fail to open, while the roster's
        own destination is perfectly writable -- and the game reports the save
        as successful either way, because the executable deliberately ignores
        export failures.

        Before this was fixed, a statistics failure returned early and the
        roster was never attempted, so the player kept a roster describing a
        village that no longer existed: stale in a way that looks current,
        which is the exact failure this exporter exists to prevent. Codex
        caught it.

        Every return after the statistics file is opened must therefore reach
        the roster call first. Checked by walking the function's own text
        rather than by counting call sites, because adding a call somewhere
        harmless would satisfy a count while leaving a path uncovered.
        """
        source = STATISTICS.read_text(encoding="utf-8")
        opening = source.index(
            "__declspec(dllexport) int __stdcall WriteVillageStatistics(")
        brace = source.index(
            "{", source.index(")", source.index("save_id", opening)))

        depth, index = 0, brace
        while index < len(source):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        self.assertLess(index, len(source), "unterminated function body")

        body = re.sub(
            r"/\*.*?\*/", "", source[brace:index + 1], flags=re.DOTALL)

        # Everything before the statistics file is opened is pure argument
        # validation -- nothing has been written and no roster is owed.
        marker = '_wfopen(temporary, L"w")'
        self.assertIn(marker, body, "cannot locate the statistics file open")
        after = body[body.index(marker):]

        # Each return is checked against the statements that IMMEDIATELY
        # precede it, not against everything earlier in the function.
        #
        # The first version of this guard asked whether the call appeared
        # anywhere before the return, which is a cumulative text search rather
        # than a control-flow one: an earlier path's call satisfied a later
        # return that had none, so restoring the original bug still passed.
        # Walking back only to the start of the enclosing block is what makes
        # the difference between "a call exists above" and "this path makes
        # the call".
        # Matched by NAME rather than by its exact argument text. This
        # guard is about control flow -- whether each return path makes
        # the call -- and pinning the arguments here would make it fail
        # for an unrelated signature change while saying nothing about
        # the paths. The argument list is pinned by the positional
        # comparison in test_every_array_and_skill_offset_matches_the_
        # statistics_row, which is where a wrong argument belongs.
        call = "write_village_population("
        returns = list(re.finditer(r"return\s+[^;]+;", after))
        self.assertGreaterEqual(
            len(returns), 4,
            "expected every statistics outcome to have its own return")
        for match in returns:
            with self.subTest(at=match.start()):
                # Back up to the brace that opens this return's own block.
                depth, index = 0, match.start()
                while index > 0:
                    index -= 1
                    if after[index] == "}":
                        depth += 1
                    elif after[index] == "{":
                        if depth == 0:
                            break
                        depth -= 1
                block = after[index:match.start()]
                # A return at function scope walks back to the function's own
                # brace and would see every earlier path's call, so for that
                # case the search starts after the last closing brace instead
                # -- the statements that actually run before this return.
                if block.rstrip().endswith("}") or "}" in block:
                    block = block[block.rindex("}") + 1:]
                self.assertIn(
                    call, block,
                    "this return leaves the roster stale -- the statements "
                    "before it never export it: %s" % match.group(0))

    def test_every_game_declares_a_skill_table(self) -> None:
        """All five games, and the counts the owner gave.

        VV1 and VV2 shipped without a Skills block because their offsets were
        not established -- the statistics companion never walks their villager
        arrays, so there was nothing to carry across. The owner's suggestion
        settled it: the Origins Full Mastery upgrade sets every villager's
        every skill to mastered, so its walker has to know exactly where the
        skills are, and those displacements are the answer.

        The counts are the owner's: "vv1 and vv2 have 5 skills". VV5 is the
        only game with six.
        """
        expected = {1: (0x3BC, 5), 2: (0x7E4, 5), 3: (0xEAC, 5),
                    4: (0x1C5C, 5), 5: (0x1C5C, 6)}
        for game, (offset, count) in expected.items():
            with self.subTest(game=game):
                row = self.rows[game]
                self.assertEqual(row["skills"], offset, "skill offset")
                self.assertEqual(row["skill_count"], count, "skill count")

    def test_no_game_omits_its_skills(self) -> None:
        """A zero count means "not established", which no game is any more."""
        for game, row in self.rows.items():
            with self.subTest(game=game):
                self.assertNotEqual(
                    row["skill_count"], 0,
                    "game %d must declare a skill table" % game)

    def test_the_skill_table_fits_inside_the_record(self) -> None:
        """A skill past the stride reads the NEXT villager's record."""
        for game, row in self.rows.items():
            with self.subTest(game=game):
                end = row["skills"] + row["skill_count"] * 4
                self.assertLessEqual(
                    end, row["stride"],
                    "game %d's skill table runs past the record" % game)

    def test_vv1_and_vv2_skills_match_their_origins_mastery_walkers(
        self,
    ) -> None:
        """Re-derive the offsets from the walker, do not restate them.

        The first version of this guard parsed the manifest and then only
        asserted the JSON was non-empty, comparing the exporter against a
        hard-coded list instead. That is decorative: if a manifest's walker
        changed, the guard would still pass while the exporter read the wrong
        field. Codex caught it.

        So this decodes the walker the offsets actually came from. The Origins
        Full Mastery upgrade sets every villager's every skill to mastered, so
        it compares a run of consecutive dwords against the mastery ceiling
        100 while striding the villager array. Those displacements, recovered
        from the manifest's own payload bytes, must be exactly what this
        exporter declares.
        """
        try:
            import capstone
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("capstone is not installed")

        def walker_skill_offsets(manifest_name):
            """Displacements compared against the mastery ceiling."""
            record = json.loads(
                (ROOT / "data" / manifest_name).read_text(encoding="utf-8"))
            blobs = []
            for patch in record.get("patches", []):
                after = patch.get("after")
                if after and len(after) >= 32:
                    blobs.append(
                        (bytes.fromhex(after), int(patch["offset"], 16)))
            append = record.get("pe_append_transaction") or {}
            for layout in (append.get("layouts") or {}).values():
                if layout.get("append_bytes"):
                    blobs.append((bytes.fromhex(layout["append_bytes"]),
                                  int(layout["virtual_address"], 16)))
            self.assertTrue(blobs, "%s carries no payload" % manifest_name)

            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
            md.detail = True
            found = set()
            for code, address in blobs:
                for instruction in md.disasm(code, address):
                    immediate = None
                    memory = None
                    for operand in instruction.operands:
                        if operand.type == capstone.x86.X86_OP_IMM:
                            immediate = operand.imm
                        elif (operand.type == capstone.x86.X86_OP_MEM
                                and operand.mem.base
                                and not operand.mem.index):
                            memory = operand.mem
                    # 100 is the mastery ceiling. An integer `cmp` against an
                    # immediate is also what establishes these are int32
                    # skills rather than floats, which would have compared
                    # against a loaded constant.
                    if immediate == 100 and memory is not None \
                            and memory.disp > 0:
                        found.add(memory.disp)
            return sorted(found)

        expected = {
            1: "vv1_origins_village_wide_upgrades.json",
            2: "vv2_origins_village_wide_upgrades.json",
            # VV3 is the control: its offsets were already established from
            # another source, so the walker reproducing them is what justifies
            # trusting the same scan for the two games that had no answer.
            3: "vv3_origins_village_wide_upgrades.json",
        }
        for game, manifest in sorted(expected.items()):
            with self.subTest(game=game):
                offsets = walker_skill_offsets(manifest)
                row = self.rows[game]
                self.assertEqual(
                    offsets,
                    [row["skills"] + 4 * step
                     for step in range(row["skill_count"])],
                    "game %d's exporter must read exactly the fields its "
                    "Full Mastery walker writes" % game)
                self.assertEqual(
                    row["skills_are_float"], 0,
                    "an integer cmp against 100 means int32 skills")

    def test_every_game_declares_its_preference_offsets(self) -> None:
        """Measured per game against the running game's own Details screen.

        These are not derivable from each other: the arrays sit at different
        offsets in every game, VV1 has four slots where the later games have
        three, and the preference list itself grew from 47 entries to 62 to 79.
        """
        expected = {
            1: (0x398, 0x3A8, 4),
            2: (0x5F0, 0x6E8, 4),
            3: (0xFB4, 0xFC0, 3),
            4: (0x1E60, 0x1E6C, 3),
            5: (0x1F5C, 0x1F68, 3),
        }
        for game, (likes, dislikes, slots) in expected.items():
            with self.subTest(game=game):
                row = self.rows[game]
                self.assertEqual(row["likes"], likes, "likes offset")
                self.assertEqual(row["dislikes"], dislikes, "dislikes offset")
                self.assertEqual(
                    row["preference_slots"], slots, "slot count")

    def test_the_arrays_fit_inside_the_record(self) -> None:
        """A slot past the stride reads the NEXT villager's taste."""
        for game, row in self.rows.items():
            with self.subTest(game=game):
                for field in ("likes", "dislikes"):
                    end = row[field] + row["preference_slots"] * 4
                    self.assertLessEqual(
                        end, row["stride"],
                        "%s array runs past the record" % field)

    def test_the_array_fits_inside_every_image(self) -> None:
        """A base that ran past the image would walk arbitrary memory.

        Only meaningful for the direct-RVA games: VV1's and VV2's arrays are
        heap allocations, so nothing about their size is bounded by the image.
        What IS checked for those two is that the pointer global itself lies
        inside a writable section, below.
        """
        for game, row in self.rows.items():
            if game in POINTER_GAMES:
                continue
            exe = STOCK / EXES[game]
            if not exe.is_file():
                self.skipTest("%s is not available" % EXES[game])
            blob = exe.read_bytes()
            with self.subTest(game=game):
                pe = struct.unpack_from("<I", blob, 0x3C)[0]
                size_of_image = struct.unpack_from("<I", blob, pe + 24 + 56)[0]
                last = (
                    row["villagers_rva"]
                    + row["record_base"]
                    + (row["slots"] - 1) * row["stride"]
                )
                highest = max(
                    row["active"],
                    row["name"] + row["name_capacity"],
                    row["skills"] + row["skill_count"] * 4,
                )
                self.assertLessEqual(
                    last + highest,
                    size_of_image,
                    "the last record's highest field falls outside the image",
                )

    def test_the_array_lives_in_a_writable_data_section(self) -> None:
        """A villager array in .text or .rdata would be the wrong address.

        For VV1 and VV2 the address is the pointer GLOBAL rather than the
        array, and the same requirement holds for the same reason: the game
        writes it once when it builds the village, so a read-only home would
        mean the address is not the global it was taken for.
        """
        for game, row in self.rows.items():
            exe = STOCK / EXES[game]
            if not exe.is_file():
                self.skipTest("%s is not available" % EXES[game])
            blob = exe.read_bytes()
            with self.subTest(game=game):
                pe = struct.unpack_from("<I", blob, 0x3C)[0]
                count = struct.unpack_from("<H", blob, pe + 6)[0]
                opt = struct.unpack_from("<H", blob, pe + 20)[0]
                rva = row["villagers_rva"]
                for index in range(count):
                    off = pe + 24 + opt + index * 40
                    vsize, vaddr, rsize, _ = struct.unpack_from(
                        "<IIII", blob, off + 8)
                    chars = struct.unpack_from("<I", blob, off + 36)[0]
                    if vaddr <= rva < vaddr + max(vsize, rsize):
                        self.assertTrue(
                            chars & 0x80000000,
                            "the villager array is in a read-only section",
                        )
                        break
                else:
                    self.fail("the array RVA is not inside any section")

    def test_each_game_declares_the_skill_count_it_was_shown_to_have(self) -> None:
        """Every game now has a measured skill table.

        VV1 and VV2 used to declare zero here, meaning "not established" --
        their offsets could not be carried across from the statistics
        companion, which never walks their villager arrays. They were settled
        from the shipped Origins Full Mastery walker, which has to know where
        the skills are in order to master them.

        The counts are the owner's: VV1 and VV2 have five, as do VV3 and VV4;
        VV5 alone has six.
        """
        self.assertEqual(self.rows[1]["skill_count"], 5)
        self.assertEqual(self.rows[2]["skill_count"], 5)
        self.assertEqual(self.rows[3]["skill_count"], 5)
        self.assertEqual(self.rows[4]["skill_count"], 5)
        self.assertEqual(self.rows[5]["skill_count"], 6)

    def test_only_vv4_and_vv5_store_skills_as_floats(self) -> None:
        """Reading int32 skills through the float path yields nonsense.

        VV3's own predicate compares against 0x58, which is 88 as an integer;
        VV4 and VV5 compare against 88.0f. Taking the wrong branch
        reinterprets the bits rather than converting them, so a mastered
        skill of 100 prints as a denormal near zero.

        VV1 and VV2 are asserted here too. Their Origins Full Mastery walkers
        compare [esi+disp] against the immediate 100 with an ordinary `cmp`,
        which is an integer comparison -- a float ceiling would have been a
        loaded constant instead. Before their skills were established these
        two were absent from this guard, so a float flag on either passed.
        """
        self.assertEqual(self.rows[1]["skills_are_float"], 0)
        self.assertEqual(self.rows[2]["skills_are_float"], 0)
        self.assertEqual(self.rows[3]["skills_are_float"], 0)
        self.assertEqual(self.rows[4]["skills_are_float"], 1)
        self.assertEqual(self.rows[5]["skills_are_float"], 1)

    def test_a_game_without_skills_omits_the_block(self) -> None:
        """An empty "Skills:" heading claims the villager has none."""
        source = POPULATION.read_text(encoding="utf-8")
        self.assertIn("if (g->skill_count == 0u) {", source)


class VillagePopulationBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = POPULATION.read_text(encoding="utf-8")

    def test_the_roster_is_published_atomically(self) -> None:
        """Truncating the destination first destroys the last good roster.

        A full disk or a crash between the truncate and the last write would
        leave the player with an empty file where they previously had a
        complete one. The statistics companion already writes a temporary and
        renames; this must too.
        """
        # The call must be REACHABLE, not merely present. Asserting only that
        # the text appears passes when the condition around it is disabled,
        # which strands every roster as a .tmp and never updates the
        # destination at all.
        publish = self.source[self.source.index("static int publish_file"):]
        publish = publish[:publish.index("\n}")]
        self.assertIn("if (!MoveFileExW(temporary, destination,", publish)
        self.assertIn("MOVEFILE_REPLACE_EXISTING", publish)
        self.assertNotIn("if (0", publish)
        self.assertIn('_wfopen(temporary, L"w")', self.source)
        self.assertNotIn('_wfopen(destination', self.source)
        self.assertNotIn('_wfopen(path, L"a")', self.source)

    def test_a_failed_write_removes_the_temporary(self) -> None:
        """A half-written roster must not be left beside the executable."""
        # Every `return 0` that can be reached with the temporary open must
        # remove it first. Counted exactly rather than as a lower bound: a
        # >= check passes when one of several cleanups is deleted, which is
        # precisely the regression this guard exists to catch.
        source = self.source
        body = source[source.index("WriteVillagePopulation("):]
        opened = body.index('_wfopen(temporary, L"w")')
        after = body[opened:]
        # Failure paths after the first open: the header write, the villager
        # write, and the two inside publish_file.
        self.assertEqual(
            after.count("DeleteFileW(temporary)"),
            3,
            "both failure paths after the first open must remove the "
            "temporary, or a half-written roster is left beside the exe",
        )
        self.assertEqual(
            source.count("DeleteFileW(temporary)"),
            6,
            "a cleanup was added or removed; re-check every failure path "
            "that can be reached while the temporary is open",
        )

    def test_an_empty_village_still_replaces_the_roster(self) -> None:
        """Every villager can die, and that is a real state to report.

        Opening lazily on the first live villager meant an extinct village
        kept displaying the villagers it had before -- a file that looks
        current and is not, which is worse than an absent one. Codex raised
        this and was right.

        The check is structural rather than textual: the first open must be
        unconditional and must sit BEFORE the slot loop. An earlier version
        of this guard checked only the explanatory comment and the ordering
        of two strings, and a mutation that restored the lazy open while
        leaving both in place survived it.
        """
        source = self.source
        body = source[source.index("__stdcall WriteVillagePopulation("):]
        loop = body.index("for (index = 0; index < g->slots")
        before_loop = body[:loop]

        # The open itself, unguarded, before the loop.
        self.assertIn(
            'file = _wfopen(temporary, L"w");',
            before_loop,
            "the first roster file must be opened before the slot loop, so "
            "an empty village still replaces the previous snapshot",
        )
        self.assertIn(
            "if (!build_log_paths(file_index, temporary, destination)) {",
            before_loop,
            "the pre-loop open must build its paths unconditionally",
        )
        # And nothing may short-circuit either one. Scoped to after the
        # declarations, because `FILE *file = NULL;` is a legitimate
        # initialiser there.
        executable = before_loop[before_loop.index("villagers = module +"):]
        self.assertNotIn("if (0", executable)
        self.assertNotIn(
            "file = NULL;",
            executable,
            "something reassigns file to NULL before the loop, which is the "
            "lazy open returning by another name",
        )

    def test_a_lazily_allocated_array_is_null_checked(self) -> None:
        """VV1's and VV2's globals read null until the village is first built.

        Dereferencing that null walks address 0 as a villager array, which is
        an access violation on the very first save of a new game -- before the
        player has done anything. The mutation that removes this guard passes
        every other test in this file.
        """
        source = self.source
        deref = source.index("*(const unsigned char *const *)villagers")
        after = source[deref:deref + 200]
        self.assertIn(
            "if (villagers == NULL) {",
            after,
            "the dereference of a pointer-global array must be null-checked "
            "immediately, before anything walks it",
        )
        self.assertIn("return 0;", after)

    def test_each_game_uses_its_own_preference_list(self) -> None:
        """Indexing the wrong list yields a plausible but wrong word.

        The lists share a prefix -- every game starts "ants, crowds, resting"
        -- so a mismatch produces sensible-looking output for low indices and
        silently wrong output for high ones, which is the worst kind of bug to
        find by reading the log.
        """
        source = POPULATION.read_text(encoding="utf-8")
        table = source[source.index("GAME_LAYOUTS[6] = {"):]
        expected = {
            1: "PREFERENCES_47",
            2: "PREFERENCES_62",
            3: "PREFERENCES_79",
            4: "PREFERENCES_79",
            5: "PREFERENCES_79",
        }
        for game, name in expected.items():
            with self.subTest(game=game):
                row_start = table.index('"Virtual Villagers %d"' % game)
                window = table[max(0, row_start - 400):row_start]
                self.assertIn(
                    name, window,
                    "game %d must index %s" % (game, name))

    def test_the_lists_have_the_lengths_they_were_measured_to_have(self) -> None:
        """A truncated list silently shifts nothing but rejects high indices.

        Counted from the C literal rather than asserted as a number in prose,
        so a future edit that drops an entry fails here rather than in a log.
        """
        source = POPULATION.read_text(encoding="utf-8")
        for name, count in (("PREFERENCES_47", 47),
                            ("PREFERENCES_62", 62),
                            ("PREFERENCES_79", 79)):
            with self.subTest(list=name):
                start = source.index("static const char %s[] =" % name)
                end = source.index(";", start)
                literal = "".join(
                    part for part in source[start:end].split('"')[1::2])
                self.assertEqual(
                    len(literal.split(",")), count,
                    "%s should hold %d entries" % (name, count))

    def test_an_empty_slot_is_skipped_rather_than_printed(self) -> None:
        """The panel shows the FIRST FILLED entry, not slot 0.

        Two real villagers prove this matters: one whose first dislike slot is
        empty and whose second holds the value the game displays, and one whose
        slots are all empty and whose panel line is blank. Reading slot 0 gets
        both wrong.
        """
        source = self.source
        self.assertIn("static int first_preference(", source)
        body = source[source.index("static int first_preference("):]
        body = body[:body.index("\n}")]
        self.assertIn("for (slot = 0; slot < slots; ++slot)", body)
        self.assertIn("if (value < 0) {", body)
        self.assertIn("continue;", body)

    def test_an_out_of_range_index_counts_as_empty(self) -> None:
        """Empty reads as -1 OR as a value past the end of the list.

        Both occur in real villages. An early scan discarded the correct
        offsets precisely because it required every value to be in range.
        """
        source = self.source
        body = source[source.index("static int preference_name("):]
        body = body[:body.index("\n}")]
        self.assertIn("return 0;   /* index past the end of the list */", body)

    def test_a_shrinking_village_does_not_leave_stale_files(self) -> None:
        """A village that drops below a file boundary keeps the old files."""
        self.assertIn("DeleteFileW(old_destination)", self.source)

    def test_the_file_rolls_at_the_requested_count(self) -> None:
        """The owner asked for "text files hold 256 villagers each"."""
        self.assertIn("VILLAGERS_PER_FILE = 256", self.source)

    def test_an_absent_father_is_detected_by_name_not_appearance(self) -> None:
        """0 is a valid head and a valid body, so it cannot mean "absent".

        Testing head or body against zero would discard a father genuinely at
        row 0 of the spritesheet, which is a real villager the owner has said
        exists.
        """
        self.assertIn("record[g->father_name] != '\\0'", self.source)
        self.assertNotIn("father_head] != 0", self.source)
        self.assertNotIn("father_body] != 0", self.source)

    def test_only_live_slots_are_written(self) -> None:
        """An empty slot holds stale data that reads as a plausible villager."""
        self.assertIn("(record + g->active) != 1", self.source)

    def test_the_layout_guard_rejects_a_half_declared_father_block(self) -> None:
        """Half a block prints a name beside somebody else's appearance."""
        self.assertIn("g->father_name == 0u || g->father_head == 0u",
                      self.source)


if __name__ == "__main__":
    unittest.main()
