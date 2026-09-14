"""Render a pytest run as a GitHub Actions job summary.

The suite's real size lives in its subtests, not its test functions:
pytest-subtests reports thousands of cases (2908 against 1384 functions at
the time of writing) because most guards sweep a game, a mode, or a patch
row per case. ``pytest -q`` prints one tail line for all of that, so the
Actions UI shows none of it unless something fails.

Two things are surfaced here that the raw run does not give you, and each
has a trap in it that the obvious implementation falls into.

**The counts.** pytest-subtests does *not* emit a ``<testcase>`` per
subtest. A passing subtest is folded into its parent, while the suite's own
``tests`` attribute still counts every one, so a report whose header says
``tests="37"`` can hold thirteen ``<testcase>`` elements. Counting elements
undercounts the run badly. The suite attributes are the authoritative
totals and are what this reads; elements are used only to name failures.

**The parameters.** A failing subtest is reported under its parent
function's name, so the log says which test broke but not which game or
mode. That detail is *not* recoverable from the JUnit report -- pytest
writes neither the subtest parameters nor unittest's ``(mode='...')``
header into the XML, so a summariser reading only the XML can never show
them. They do appear in pytest's own short summary, as

    SUBFAILED(mode='collection_progression') tests/test_x.py::Class::test

which is why this takes the terse output as a second input and matches the
two up by test id. Without it the table can say what failed but not which
case of it, which on a sweep of five games is most of the question.

Both inputs are optional and the script degrades rather than failing: no
XML at all still prints a heading, and no terse log just leaves the
parameters blank.

The exit status is deliberately always 0. This script reports, it does not
judge -- pytest's own exit code decides whether the job passes, and a
summariser that could fail an otherwise green run would be worse than no
summariser at all.
"""

from __future__ import annotations

import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# `SUBFAILED(mode='x') path::Class::test` and the plain `FAILED path::...`
# that pytest prints under `-rf`. The parenthesised group is what unittest
# was given in subTest(...), and is absent for a non-subtest failure.
# One level of nesting is allowed inside the parameter text, because a
# repr routinely contains parentheses -- `path=PosixPath('a/b')` and
# `pair=(1, 2)` both appear in this suite. A flat `[^)]*` stops at the
# inner `)`, the following whitespace assertion then fails, and the whole
# line is skipped, which shows the failure with no parameters at all.
_TERSE_FAILURE = re.compile(
    r"^(?:SUB)?(?:FAILED|ERROR)"
    r"(?:\((?P<params>(?:[^()]|\([^()]*\))*)\))?"
    r"\s+(?P<test>\S+)",
    re.MULTILINE,
)

_MAX_FAILURES_LISTED = 50


def _suites(root: ET.Element) -> list[ET.Element]:
    if root.tag == "testsuite":
        return [root]
    return list(root.iter("testsuite"))


def _int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _params_by_test(terse: Path | None) -> dict[str, list[str]]:
    """Map ``Class::test`` to the subtest parameters that failed under it."""
    found: dict[str, list[str]] = {}
    if terse is None or not terse.is_file():
        return found
    text = terse.read_text(encoding="utf-8", errors="replace")
    for match in _TERSE_FAILURE.finditer(text):
        params = (match.group("params") or "").strip()
        if not params:
            continue
        # `tests/test_x.py::Class::test` -> `Class::test`, which is the form
        # the JUnit classname/name pair reconstructs to.
        tail = "::".join(match.group("test").split("::")[-2:])
        found.setdefault(tail, []).append(params)
    return found


def _cell(text: str, limit: int = 160) -> str:
    text = (text or "").strip()
    text = text.splitlines()[0] if text else ""
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    # The pipe must be escaped before HTML-escaping, or the backslash lands
    # on an entity instead of the character.
    return html.escape(text.replace("|", "\\|"))


def main(argv: list[str]) -> int:
    out = sys.stdout
    if len(argv) < 2:
        print("usage: summarise_test_run.py <junit.xml> [terse.log]", file=sys.stderr)
        return 0

    report = Path(argv[1])
    terse = Path(argv[2]) if len(argv) > 2 else None

    if not report.is_file():
        # A missing report means pytest died before it could write one. The
        # job log already says so; do not add a confusing second story.
        print("## Tests\n\nNo JUnit report was produced.", file=out)
        return 0

    try:
        root = ET.parse(report).getroot()
    except ET.ParseError as exc:
        print(f"## Tests\n\nThe JUnit report could not be parsed: {exc}", file=out)
        return 0

    suites = _suites(root)
    total = sum(_int(s.get("tests")) for s in suites)
    failed = sum(_int(s.get("failures")) + _int(s.get("errors")) for s in suites)
    skipped = sum(_int(s.get("skipped")) for s in suites)
    passed = max(total - failed - skipped, 0)

    cases = [case for suite in suites for case in suite.iter("testcase")]
    functions = len({(c.get("classname", ""), c.get("name", "")) for c in cases})
    # Every test function reports at least one case of its own; the surplus
    # the suite counted beyond that is the subtest population.
    subtests = max(total - functions, 0)

    failing = [c for c in cases if any(k.tag in ("failure", "error") for k in c)]
    params_for = _params_by_test(terse)

    verdict = "All green" if not failed else f"{failed} failing"
    print("## Tests", file=out)
    print(file=out)
    print(f"**{verdict}** - {total} cases from {functions} test functions.", file=out)
    print(file=out)
    print("| | count |", file=out)
    print("|---|---:|", file=out)
    print(f"| Passed | {passed} |", file=out)
    print(f"| Failed | {failed} |", file=out)
    print(f"| Skipped | {skipped} |", file=out)
    print(f"| Subtest cases | {subtests} |", file=out)
    print(file=out)
    print(
        "Skips are expected here: the stock game executables are gitignored, "
        "so every fixture-dependent case skips in CI. A green run is green "
        "over the subset that does not need them.",
        file=out,
    )

    if failing:
        print(file=out)
        print("### Failures", file=out)
        print(file=out)
        print("| test | failing case | message |", file=out)
        print("|---|---|---|", file=out)
        rows = 0
        for case in failing:
            name = case.get("name", "")
            where = case.get("classname", "")
            if where.startswith("tests."):
                where = where[len("tests.") :]
            key = f"{where.rsplit('.', 1)[-1]}::{name}"
            # pytest-subtests puts one <failure> per failing subtest inside
            # the SAME <testcase>, so a method with two bad modes carries two
            # sibling elements. One row each, paired positionally with the
            # parameters the terse log listed for this test in the same order,
            # or the rows would say which cases failed but not which message
            # belonged to which -- and every failure after the first would be
            # dropped entirely.
            details = [k for k in case if k.tag in ("failure", "error")]
            listed = params_for.get(key, [])
            for index, detail in enumerate(details):
                if rows >= _MAX_FAILURES_LISTED:
                    break
                params = listed[index] if index < len(listed) else ""
                print(
                    f"| `{where}::{name}` "
                    f"| {('`' + _cell(params, 80) + '`') if params else '-'} "
                    f"| {_cell(detail.get('message'))} |",
                    file=out,
                )
                rows += 1
        if len(failing) > _MAX_FAILURES_LISTED:
            print(file=out)
            print(
                f"...and {len(failing) - _MAX_FAILURES_LISTED} more; "
                "see the uploaded JUnit report.",
                file=out,
            )

    # Report only. pytest's exit code is what decides the job.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
