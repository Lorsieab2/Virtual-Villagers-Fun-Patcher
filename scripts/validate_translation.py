"""Check a shared translation file before it is accepted into the repository.

    python scripts/validate_translation.py FILE [--game TITLE] [--credit NAME] [--markdown OUT]
                                                [--set-translator NAME --write OUT]

Exit 0 when the file is accepted, 1 when it is refused.  The rules are the patcher's own: this script runs
src/vv_translation_format.py (the module the Translations window uses) on the file alone, and adds only what a
file shared with everyone needs on top of it:

- the whole file must read (size, encoding, header, format version, @language, @code, @game): `check_info`
  and `validate` decide, exactly as in the patcher;
- an email address ANYWHERE in the file refuses it (the owner, 2026-11-01: "Email addresses are never saved
  and are rejected from translation files"), including in a translated line, where the patcher would only
  make that line fall back;
- the credit (--credit, --set-translator) must be a typed name: not empty, at most 80 characters, one line,
  no email address;
- at least one translated line must be usable;
- REFUSAL THRESHOLD: when more than half of the translated lines have errors the file is refused as broken
  (a wrong column, a spreadsheet that mangled the placeholders...).  Below that, lines with errors are listed
  and simply fall back to English in the game, as they would in the patcher.

Nothing in the file is ever executed or evaluated; it is read as bytes and decoded as text.  No email address
is ever printed back: every output (console and markdown) has them masked.
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import vv_translation_format as fmt  # noqa: E402  (the patcher's own validator)

MAX_CREDIT_CHARS = 80               # the same limit check_info applies to @translator
REFUSE_ERROR_SHARE = 0.5            # more than this share of translated lines with errors: the file is refused
MAX_LISTED_ERRORS = 100             # an issue comment has a size limit; the rest are counted
MAX_LISTED_WARNINGS = 30
EMAIL_MASK = "[email address removed]"


def mask_emails(text: str) -> str:
    """`text` with every email-like string replaced, so a report never repeats one."""
    return fmt.EMAIL_RE.sub(EMAIL_MASK, text or "")


def credit_problems(name: str | None) -> list[str]:
    """Why `name` cannot be the public credit (empty list: it can)."""
    if name is None:
        return []
    name = name.strip()
    if not name:
        return ["the credit (the name you wish to be credited as) is empty"]
    problems = []
    if fmt.find_emails(name):
        problems.append(f"the credit is an email address or contains one. {fmt.EMAIL_SENTENCE} "
                        "Type the name you wish to be credited as.")
    if len(name) > MAX_CREDIT_CHARS:
        problems.append(f"the credit is longer than {MAX_CREDIT_CHARS} characters")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") and ch != "‍" for ch in name):
        problems.append("the credit contains line breaks, tabs or invisible control characters")
    return problems


@dataclass
class Result:
    accepted: bool = False
    reasons: list[str] = field(default_factory=list)       # why the whole file is refused
    report: fmt.Report | None = None
    tf: fmt.TranslationFile | None = None

    def refuse(self, reason: str) -> None:
        if reason not in self.reasons:
            self.reasons.append(reason)


def check_file(path: Path, game: str | None = None, credit: str | None = None,
               set_translator: str | None = None) -> Result:
    """The verdict on the file at `path` (read as data only)."""
    result = Result()
    path = Path(path)
    for problem in credit_problems(credit) + credit_problems(set_translator):
        result.refuse(problem)
    try:
        size = path.stat().st_size
    except OSError:
        result.refuse("the file could not be read")
        return result
    if size > fmt.MAX_FILE_BYTES:
        result.refuse(f"the file is larger than {fmt.MAX_FILE_BYTES // (1024 * 1024)} MB")
        return result
    try:
        text = fmt.decode_bytes(path.read_bytes())
        tf = fmt.parse(text)
    except fmt.FormatError as error:
        result.refuse(str(error))
        return result
    result.tf = tf
    # Emails anywhere at all: rows the parser skipped, extra columns, unknown information rows included.
    for number, line in enumerate(text.splitlines(), start=1):
        if fmt.find_emails(line):
            result.refuse(f"line {number} contains an email address. {fmt.EMAIL_SENTENCE}")
    if set_translator is not None:
        english = tf.info.get("@translator", ("", ""))[0]
        if fmt.find_emails(english):
            english = ""
        tf.set_info("@translator", english, set_translator.strip())
    if game is not None and not tf.game:
        result.refuse(f"the @game row is missing; this file must be for {game!r}")
    report = fmt.validate(tf, game_title=game)
    result.report = report
    for problem in report.file_errors:
        result.refuse(problem)
    if tf.translator:
        for problem in credit_problems(tf.translator):
            result.refuse("@translator: " + problem)
    if report.used < 1:
        result.refuse("no line is translated (or every translated line has an error); at least one "
                      "translated line is needed")
    elif report.translated and (report.translated - report.used) > REFUSE_ERROR_SHARE * report.translated:
        result.refuse(f"{report.translated - report.used} of the {report.translated} translated lines have "
                      f"errors (more than {REFUSE_ERROR_SHARE:.0%}); the file looks damaged. Open it in the "
                      "patcher's Translations window, fix the lines it marks, and export it again")
    result.accepted = not result.reasons
    return result


def write_accepted(result: Result, out: Path, game: str | None = None) -> Result:
    """Write the accepted file to `out` (UTF-8 with a BOM, CRLF) and check the written file again; on a
    refusal of the written file it is removed and the returned Result says why."""
    if not result.accepted or result.tf is None:
        raise ValueError("only an accepted file is written")
    out = Path(out)
    fmt.write_file(out, result.tf)
    again = check_file(out, game=game, credit=result.tf.translator or None)
    if not again.accepted:
        try:
            out.unlink()
        except OSError:
            pass
    return again


# ---- reports -----------------------------------------------------------------------------------------------

def _fence(lines: list[str]) -> list[str]:
    """Lines shown verbatim in an issue comment: no markdown, links or @mentions are interpreted."""
    body = [mask_emails(line).replace("~~~", "~ ~ ~") for line in lines]
    return ["~~~text", *body, "~~~"]


def markdown(result: Result, name: str = "") -> str:
    out = []
    shown = mask_emails(name).replace("`", "'")
    if result.accepted:
        out.append(f"**The translation file{' `' + shown + '`' if shown else ''} passed the checks.**")
    else:
        out.append(f"**The translation file{' `' + shown + '`' if shown else ''} could not be accepted.**")
        out.append("")
        out.append("Why:")
        out.extend(_fence([f"- {reason}" for reason in result.reasons]))
    report = result.report
    if report is not None:
        out.append("")
        out.append(f"Coverage: **{report.coverage:.0f}%** ({report.used} of {report.total} lines translated "
                   "and usable).")
        if report.errors:
            out.append("")
            out.append(f"{len(report.errors)} line(s) with errors (in the game these lines stay in English):")
            listed = [str(issue) for issue in report.errors[:MAX_LISTED_ERRORS]]
            if len(report.errors) > MAX_LISTED_ERRORS:
                listed.append(f"... and {len(report.errors) - MAX_LISTED_ERRORS} more")
            out.extend(_fence(listed))
        if report.warnings:
            out.append("")
            out.append(f"{len(report.warnings)} warning(s) (these lines are used; worth a look):")
            listed = [str(issue) for issue in report.warnings[:MAX_LISTED_WARNINGS]]
            if len(report.warnings) > MAX_LISTED_WARNINGS:
                listed.append(f"... and {len(report.warnings) - MAX_LISTED_WARNINGS} more")
            out.extend(_fence(listed))
    out.append("")
    out.append("The patcher's Translations window shows the same checks line by line (Validate). "
               + fmt.EMAIL_SENTENCE)
    return mask_emails("\n".join(out)) + "\n"


def console(result: Result) -> str:
    lines = ["ACCEPTED" if result.accepted else "REFUSED"]
    lines += [f"  refused: {reason}" for reason in result.reasons]
    if result.report is not None:
        lines.append("  " + result.report.summary())
        lines += [f"  error: {issue}" for issue in result.report.errors]
        lines += [f"  warning: {issue}" for issue in result.report.warnings]
    return mask_emails("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a shared translation file (exit 0: accepted).")
    parser.add_argument("file", type=Path)
    parser.add_argument("--game", help="the game title the file must be for")
    parser.add_argument("--credit", help="the name typed in the issue form's credit field")
    parser.add_argument("--markdown", type=Path, help="write a markdown report here (for the issue comment)")
    parser.add_argument("--set-translator", help="set @translator to this name (checked like --credit)")
    parser.add_argument("--write", type=Path, help="write the accepted file here (with --set-translator applied)")
    args = parser.parse_args(argv)

    result = check_file(args.file, game=args.game, credit=args.credit, set_translator=args.set_translator)
    if result.accepted and args.write is not None:
        result = write_accepted(result, args.write, game=args.game)
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(result, args.file.name), encoding="utf-8")
    out = console(result) + "\n"
    sys.stdout.buffer.write(out.encode("utf-8", "replace"))
    return 0 if result.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
