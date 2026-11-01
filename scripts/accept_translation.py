"""The logic of .github/workflows/accept-translation.yml: from a "Share a translation" issue to a file ready to
commit.  Run by the workflow only after the owner adds the "accept-translation" label.

    python -I scripts/accept_translation.py

Input comes ONLY through environment variables (never through ${{ }} interpolation in a shell script, which
would let an issue's text run as code):

    ISSUE_BODY     the issue's body (the issue form's markdown)
    ISSUE_NUMBER   the issue's number
    WORK           a scratch folder outside the checkout (the workflow passes $RUNNER_TEMP/translation)
    GITHUB_OUTPUT  set by Actions; this script writes exactly one line to it: verdict=accepted|refused

What it does:

1. reads the form's sections (### Game, ### Language (its own name), ...) from the body; each must appear
   exactly once, so text typed into one box cannot pose as another;
2. checks the game is one of the five, the credit is a typed name (not empty, no email address), the
   licence box is checked;
3. finds exactly one attached .txt link in the "Translation file" section, accepted only on
   https://github.com/user-attachments/files/... and downloaded with curl (https only, no automatic
   redirects: each redirect is checked against the host allow-list, objects.githubusercontent.com),
   at most 4 MB (curl --max-filesize, then the size on disk);
4. validates the file with scripts/validate_translation.py (the patcher's own validator), with the form's
   game and the credit as @translator, and checks the form's language and code match the file's;
5. writes translations/<Game title>/<Game title> - <Language>.txt into the checkout and, in WORK, the
   commit message, PR title and PR body; on a refusal, WORK/comment.md with the reasons (emails masked).

The downloaded file is data only: it is decoded as text and parsed, never executed, sourced or evaluated.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
for _path in (SCRIPTS, ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import validate_translation as vt  # noqa: E402
import vv_translation_format as fmt  # noqa: E402

# The five games, exactly as src/vv_translations.py TITLES spells them (tests/test_translation_sharing.py
# keeps the two lists equal).  The folder name under translations/ is the title.
GAME_TITLES = (
    "Virtual Villagers - A New Home",
    "Virtual Villagers - The Lost Children",
    "Virtual Villagers - The Secret City",
    "Virtual Villagers - The Tree of Life",
    "Virtual Villagers - New Believers",
)

# The issue form's field ids -> the labels GitHub prints as "### <label>" in the issue body.  These must
# match .github/ISSUE_TEMPLATE/translation.yml (the tests check it).
FORM_LABELS = {
    "game": "Game",
    "language": "Language (its own name)",
    "code": "Language code",
    "credit": "Credit",
    "coverage": "Coverage",
    "file": "Translation file",
    "licence": "Licence",
}
NO_RESPONSE = "_No response_"

MAX_BYTES = fmt.MAX_FILE_BYTES                      # 4 MB, the same limit the patcher applies
MAX_LANGUAGE_CHARS = 60
ATTACHMENT_RE = re.compile(r"^https://github\.com/user-attachments/files/\d+/[^\s/?#]+\.txt$", re.IGNORECASE)
REDIRECT_HOSTS = frozenset({"objects.githubusercontent.com"})
MAX_REDIRECTS = 3
_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)


class Refused(Exception):
    """The submission cannot be accepted; the message is shown on the issue."""


# ---- the issue body ---------------------------------------------------------------------------------------

def parse_issue_body(body: str) -> dict[str, str]:
    """{field id: value} from the form's markdown; Refused when a section is missing or repeated."""
    wanted = {label.casefold(): fid for fid, label in FORM_LABELS.items()}
    sections: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    current = None
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            fid = wanted.get(heading.group(1).casefold())
            if fid is not None:
                counts[fid] = counts.get(fid, 0) + 1
                current = fid
                sections[fid] = []
                continue
        if current is not None:
            sections[current].append(line)
    repeated = [FORM_LABELS[f] for f, n in counts.items() if n > 1]
    if repeated:
        raise Refused("the issue's text has the heading \"### " + "\", \"### ".join(repeated)
                      + "\" more than once; please send the translation again with a new form")
    missing = [FORM_LABELS[f] for f in FORM_LABELS if f not in sections and f != "coverage"]
    if missing:
        raise Refused("the issue was not sent with the \"Share a translation\" form (missing: "
                      + ", ".join(missing) + ")")
    out = {}
    for fid in FORM_LABELS:
        value = "\n".join(sections.get(fid, [])).strip()
        out[fid] = "" if value == NO_RESPONSE else value
    return out


def licence_agreed(section: str) -> bool:
    return any(re.match(r"^\s*-\s*\[[xX]\]\s+I agree", line) for line in section.splitlines())


def find_attachment(section: str) -> str:
    """The one attached .txt link in the "Translation file" section."""
    urls = []
    for url in _URL_RE.findall(section or ""):
        url = url.rstrip(".,;:!")
        if url not in urls:
            urls.append(url)
    if not urls:
        raise Refused("no file is attached in the \"Translation file\" box. Drag your exported .txt file into "
                      "that box (do not paste its text) and send the form again")
    if len(urls) > 1:
        raise Refused(f"the \"Translation file\" box has {len(urls)} links; attach exactly one .txt file")
    url = urls[0]
    if not ATTACHMENT_RE.match(url):
        raise Refused("the \"Translation file\" box must hold one .txt file dragged into it on GitHub "
                      "(a github.com/user-attachments/files/... link); links to other sites are not used")
    return url


def _allowed_redirect(url: str) -> bool:
    parts = urlsplit(url)
    return (parts.scheme == "https" and parts.hostname in REDIRECT_HOSTS and parts.port is None
            and not parts.username and not parts.password)


def download(url: str, dest: Path, run=subprocess.run) -> None:
    """Fetch `url` into `dest` with curl: https only, every redirect checked against the allow-list, at most
    MAX_BYTES.  `run` is subprocess.run (replaced in tests)."""
    if not ATTACHMENT_RE.match(url):
        raise Refused("the attachment link is not a GitHub file attachment")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        if dest.exists():
            dest.unlink()
        proc = run(["curl", "--silent", "--show-error", "--proto", "=https", "--max-filesize", str(MAX_BYTES),
                    "--max-time", "60", "--user-agent", "accept-translation-workflow",
                    "--output", str(dest), "--write-out", "%{http_code} %{redirect_url}", current],
                   capture_output=True, text=True, check=False)
        if proc.returncode == 63:
            raise Refused(f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")
        if proc.returncode != 0:
            raise Refused(f"the attached file could not be downloaded (curl exit code {proc.returncode})")
        code, _sep, redirect = (proc.stdout or "").strip().partition(" ")
        redirect = redirect.strip()
        if code in ("301", "302", "303", "307", "308"):
            if not _allowed_redirect(redirect):
                raise Refused("GitHub sent the download to a host that is not on the allow-list ("
                              + (urlsplit(redirect).hostname or "unknown") + ")")
            current = redirect
            continue
        if code != "200":
            raise Refused(f"the attached file could not be downloaded (HTTP {code or 'no answer'})")
        if not dest.is_file():
            raise Refused("the attached file could not be downloaded (nothing was received)")
        if dest.stat().st_size > MAX_BYTES:
            dest.unlink()
            raise Refused(f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")
        return
    raise Refused("the download was redirected too many times")


# ---- markdown that cannot ping or link anyone ---------------------------------------------------------------

def md_text(text: str) -> str:
    """`text` safe to show inline in markdown: no formatting, links, @mentions or #references, no emails."""
    text = vt.mask_emails(text)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf") or ch == "‍")
    text = re.sub(r"([\\`*_{}\[\]()<>#+!|~])", r"\\\1", text)
    return text.replace("@", "@⁠")


def plain_line(text: str) -> str:
    """One line of plain text (a title or commit subject): no control characters, emails masked."""
    text = vt.mask_emails(text)
    return " ".join("".join(" " if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") else ch
                            for ch in text).split())


# ---- the whole run ------------------------------------------------------------------------------------------

@dataclass
class Outcome:
    accepted: bool = False
    reasons: list[str] = field(default_factory=list)
    result: vt.Result | None = None
    relative_path: str = ""


def prepare(body: str, number: int, work: Path, repo_root: Path = ROOT, fetch=download) -> Outcome:
    outcome = Outcome()
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    try:
        fields = parse_issue_body(body)
        game = fields["game"].strip()
        if game not in GAME_TITLES:
            raise Refused("the Game box must be one of the five Virtual Villagers games")
        problems = vt.credit_problems(fields["credit"])
        if problems:
            raise Refused("; ".join(problems))
        credit = fields["credit"].strip()
        if not fields["language"].strip() or not fields["code"].strip():
            raise Refused("the Language and Language code boxes must be filled in")
        if not licence_agreed(fields["licence"]):
            raise Refused("the licence box is not checked")
        url = find_attachment(fields["file"])
        submitted = work / "download" / "submitted.txt"
        fetch(url, submitted)
        result = vt.check_file(submitted, game=game, credit=credit, set_translator=credit)
        outcome.result = result
        tf = result.tf
        if tf is not None:
            if tf.language.casefold() != fields["language"].strip().casefold():
                result.refuse("the form's language does not match the file's @language row")
            if tf.code.casefold() != fields["code"].strip().casefold():
                result.refuse("the form's language code does not match the file's @code row")
            if len(tf.language) > MAX_LANGUAGE_CHARS:
                result.refuse(f"the @language name is longer than {MAX_LANGUAGE_CHARS} characters")
        result.accepted = not result.reasons
        if not result.accepted:
            outcome.reasons = list(result.reasons)
            _write_refusal(work, outcome)
            return outcome
        folder = (repo_root / "translations" / game).resolve()
        target = (folder / fmt.file_name(game, tf.language)).resolve()
        if target.parent != folder:
            raise Refused("the file name could not be made safely from the @language row")
        replaces = target.exists()
        final = vt.write_accepted(result, target, game=game)
        outcome.result = final
        if not final.accepted:
            outcome.reasons = list(final.reasons)
            _write_refusal(work, outcome)
            return outcome
        outcome.accepted = True
        outcome.relative_path = target.relative_to(repo_root.resolve()).as_posix()
        _write_acceptance(work, outcome, number, game, final, credit, replaces)
        return outcome
    except Refused as refusal:
        outcome.reasons.append(str(refusal))
        _write_refusal(work, outcome)
        return outcome


def _write_refusal(work: Path, outcome: Outcome) -> None:
    result = outcome.result or vt.Result()
    for reason in outcome.reasons:
        result.refuse(reason)
    result.accepted = False
    text = ["This translation could not be accepted yet. Nothing was added to the repository.", "",
            vt.markdown(result),
            "Please fix the file in the patcher's Translations window (or ask here if a check looks wrong) and "
            "send it again with **Share on GitHub...**, or edit this issue and drag the fixed file into the "
            "Translation file box in place of the old link, then say so here and the maintainer will try again."]
    (work / "comment.md").write_text(vt.mask_emails("\n".join(text)), encoding="utf-8")


def _write_acceptance(work: Path, outcome: Outcome, number: int, game: str, result: vt.Result, credit: str,
                      replaces: bool) -> None:
    tf = result.tf
    language = tf.language
    report = result.report
    title = plain_line(f"Translation: {game} - {language}")
    (work / "pr_title.txt").write_text(title, encoding="utf-8")
    (work / "commit_message.txt").write_text(
        plain_line(f"Translation: {game} - {language}, by {credit}") + "\n\n"
        + f"Shared in issue #{number}; checked by scripts/validate_translation.py.\n", encoding="utf-8")
    body = [
        f"Adds the **{md_text(language)}** translation of *{md_text(game)}*, by **{md_text(credit)}** "
        "(the name typed in the issue form).",
        "",
        f"- File: `{outcome.relative_path.replace('`', chr(39))}`",
        f"- Coverage: {report.coverage:.0f}% ({report.used} of {report.total} lines)",
        f"- Lines with errors (they stay in English): {len(report.errors)}",
        f"- Warnings: {len(report.warnings)}",
    ]
    if replaces:
        body.append("- This **replaces** the translation already in the repository for this game and language.")
    body += [
        "",
        f"Players will see it in the Translations list as \"{md_text(language)}, by {md_text(credit)}\" "
        "after the next release.",
        "",
        "Check the file in **Files changed** before merging.",
        "",
        f"Closes #{number}",
        "",
        "<details><summary>Validation report</summary>",
        "",
        vt.markdown(result),
        "</details>",
    ]
    (work / "pr_body.md").write_text(vt.mask_emails("\n".join(body)) + "\n", encoding="utf-8")


def main() -> int:
    body = os.environ.get("ISSUE_BODY", "")
    number_text = os.environ.get("ISSUE_NUMBER", "")
    work = os.environ.get("WORK", "")
    if not number_text.isdigit() or not work:
        print("ISSUE_NUMBER and WORK must be set", file=sys.stderr)
        return 2
    outcome = prepare(body, int(number_text), Path(work))
    verdict = "accepted" if outcome.accepted else "refused"
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"verdict={verdict}\n")
    message = f"{verdict}: {outcome.relative_path}" if outcome.accepted else \
        verdict + "".join(f"\n  {reason}" for reason in outcome.reasons)
    sys.stdout.buffer.write((vt.mask_emails(message) + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
