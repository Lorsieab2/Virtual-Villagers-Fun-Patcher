"""The repository side of "Share a translation": the issue form, the accept-translation workflow, and the
scripts it runs (scripts/validate_translation.py, scripts/accept_translation.py).

The workflow itself cannot run here; these tests pin what can be checked offline: the form's fields, the
workflow's permissions / trigger / injection safety / identity, and the scripts' verdicts on real files.
PyYAML is not a project dependency, so the YAML is checked as text and, when PyYAML happens to be installed,
also parsed.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_translation_format as fmt  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


vt = _load("validate_translation")
at = _load("accept_translation")

FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "translation.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "accept-translation.yml"
GAME = "Virtual Villagers - The Secret City"


# ---- a translation file -------------------------------------------------------------------------------------

def make_file(path: Path, *, game=GAME, translator="Ana", translations=None, comments=None,
              language="Français", code="fr") -> Path:
    english = ["New Game", "%s has learned %d new skills!", "Welcome to {village}", "Quit"]
    rows = [fmt.Row(fmt.make_key("menu", f"item{i}", e), e) for i, e in enumerate(english)]
    tf = fmt.template_file(rows, game, language, code, translator)
    if comments is not None:
        tf.comments = comments
    values = translations if translations is not None else \
        ["Nouvelle partie", "%s a appris %d nouvelles compétences !", "Bienvenue à {village}", ""]
    for row, value in zip(tf.rows, values):
        row.translation = value
    fmt.write_file(path, tf)
    return path


def test_good_file_is_accepted(tmp_path):
    path = make_file(tmp_path / "good.txt")
    result = vt.check_file(path, game=GAME, credit="Ana")
    assert result.accepted, result.reasons
    assert result.report.used == 3
    assert vt.main([str(path), "--game", GAME, "--credit", "Ana"]) == 0


@pytest.mark.parametrize("where", ["credit", "translator", "translation", "comment"])
def test_an_email_anywhere_refuses_the_file(tmp_path, where):
    email = "someone@example.com"
    kwargs = {}
    if where == "translator":
        kwargs["translator"] = email
    elif where == "translation":
        kwargs["translations"] = ["Nouvelle partie " + email, "%s a appris %d !", "Bienvenue à {village}", "Q"]
    elif where == "comment":
        kwargs["comments"] = ["# made by " + email]
    path = make_file(tmp_path / "f.txt", **kwargs)
    credit = email if where == "credit" else "Ana"
    result = vt.check_file(path, game=GAME, credit=credit)
    assert not result.accepted
    assert any("email" in reason for reason in result.reasons)
    report = vt.markdown(result, path.name)
    assert email not in report and "email" in report
    assert email not in vt.console(result)
    assert vt.main([str(path), "--game", GAME, "--credit", credit]) == 1


def test_markdown_masks_emails(tmp_path):
    email = "translator.name@mail.example.org"
    path = make_file(tmp_path / "f.txt", translations=["Partie " + email, "", "", ""])
    out = tmp_path / "report.md"
    assert vt.main([str(path), "--game", GAME, "--markdown", str(out)]) == 1
    text = out.read_text(encoding="utf-8")
    assert email not in text and "mail.example" not in text
    assert vt.EMAIL_MASK in text


def test_wrong_game_is_refused(tmp_path):
    path = make_file(tmp_path / "f.txt", game="Virtual Villagers - New Believers")
    result = vt.check_file(path, game=GAME, credit="Ana")
    assert not result.accepted and any("not" in r and GAME in r for r in result.reasons)


def test_non_utf8_file_is_refused(tmp_path):
    path = tmp_path / "latin1.txt"
    path.write_bytes("Key\tEnglish\tTranslation\tNotes\r\n@language\tEnglish\tFrançais\r\n".encode("latin-1"))
    result = vt.check_file(path, game=GAME)
    assert not result.accepted and any("UTF-8" in r for r in result.reasons)


def test_oversized_file_is_refused_unread(tmp_path):
    path = tmp_path / "big.txt"
    path.write_bytes(b"#" * (fmt.MAX_FILE_BYTES + 1))
    result = vt.check_file(path, game=GAME)
    assert not result.accepted and any("4 MB" in r for r in result.reasons)


def test_file_with_no_translated_line_is_refused(tmp_path):
    path = make_file(tmp_path / "f.txt", translations=["", "", "", ""])
    result = vt.check_file(path, game=GAME)
    assert not result.accepted and any("translated line" in r for r in result.reasons)


def test_mostly_broken_file_is_refused_a_few_errors_are_not(tmp_path):
    broken = make_file(tmp_path / "broken.txt", translations=["Partie", "%d a appris", "Bienvenue", "50 %"])
    assert not vt.check_file(broken, game=GAME).accepted
    some = make_file(tmp_path / "some.txt", translations=["Partie", "%d a appris", "Bienvenue à {village}", "Q"])
    result = vt.check_file(some, game=GAME)
    assert result.accepted, result.reasons
    assert any(issue.line for issue in result.report.errors)       # the error names its line
    assert "line " in vt.markdown(result)


def test_set_translator_writes_the_typed_name(tmp_path):
    path = make_file(tmp_path / "f.txt", translator="old name")
    out = tmp_path / "out" / "written.txt"
    assert vt.main([str(path), "--game", GAME, "--credit", "Zoë K.", "--set-translator", "Zoë K.",
                    "--write", str(out)]) == 0
    tf = fmt.read_file(out)
    assert tf.translator == "Zoë K."
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")


def test_set_translator_refuses_an_email_and_writes_nothing(tmp_path):
    path = make_file(tmp_path / "f.txt")
    out = tmp_path / "written.txt"
    assert vt.main([str(path), "--game", GAME, "--set-translator", "me@example.com", "--write", str(out)]) == 1
    assert not out.exists()


@pytest.mark.parametrize("credit", ["", "   ", "a\nb", "x" * 81])
def test_bad_credits(credit):
    assert vt.credit_problems(credit)


# ---- the issue form -------------------------------------------------------------------------------------------

def _form_text() -> str:
    return FORM.read_text(encoding="utf-8")


def test_form_has_the_fields_as_text():
    text = _form_text()
    ids = re.findall(r"^\s+id:\s*(\S+)\s*$", text, re.M)
    assert ids == ["game", "language", "code", "credit", "coverage", "file", "licence"]
    assert re.search(r"^name:\s*Share a translation\s*$", text, re.M)
    assert re.search(r"^labels:\s*\[translation\]\s*$", text, re.M)
    assert re.search(r'^title:\s*"Translation: "\s*$', text, re.M)
    assert "https://github.com/signup" in text
    assert fmt.EMAIL_SENTENCE in " ".join(text.split())
    assert "Drag your exported .txt file into this box" in text
    assert "I agree this translation can be shared under the patcher's licence" in text
    for title in at.GAME_TITLES:
        assert f"- {title}" in text
    for fid in ids:      # no field is about email
        assert "mail" not in fid.lower()
    for label in re.findall(r"^\s+label:\s*(.+)$", text, re.M):
        assert "mail" not in label.lower()


def test_form_parses_as_yaml():
    yaml = pytest.importorskip("yaml")
    form = yaml.safe_load(_form_text())
    assert form["name"] == "Share a translation"
    assert form["labels"] == ["translation"]
    assert form["title"] == "Translation: "
    fields = {item["id"]: item for item in form["body"] if "id" in item}
    assert set(fields) == {"game", "language", "code", "credit", "coverage", "file", "licence"}
    required = {fid for fid, item in fields.items() if item.get("validations", {}).get("required")}
    assert required == {"game", "language", "code", "credit", "file"}
    assert fields["game"]["type"] == "dropdown"
    assert fields["game"]["attributes"]["options"] == list(at.GAME_TITLES)
    assert fields["file"]["type"] == "textarea"
    assert "Drag your exported .txt file into this box" in fields["file"]["attributes"]["description"]
    credit = fields["credit"]["attributes"]["description"]
    assert "name you wish to be credited as" in credit and "public" in credit and fmt.EMAIL_SENTENCE in credit
    options = fields["licence"]["attributes"]["options"]
    assert fields["licence"]["type"] == "checkboxes" and options[0]["required"] is True
    assert options[0]["label"] == "I agree this translation can be shared under the patcher's licence"
    # The labels the accept script reads back out of the issue body are the form's labels.
    for fid, label in at.FORM_LABELS.items():
        assert fields[fid]["attributes"]["label"] == label
    intro = form["body"][0]["attributes"]["value"]
    assert "https://github.com/signup" in intro and "Press Submit" in intro and "Check the box" in intro
    for item in form["body"]:
        if "id" in item:
            assert "mail" not in item["id"] and "mail" not in item["attributes"].get("label", "").lower()


def test_form_labels_match_the_accept_script_as_text():
    text = _form_text()
    for label in at.FORM_LABELS.values():
        assert re.search(r"^\s+label:\s*" + re.escape(label) + r"\s*$", text, re.M), label


def test_game_titles_match_the_patcher():
    import vv_translations
    assert tuple(vv_translations.TITLES[n] for n in sorted(vv_translations.TITLES)) == at.GAME_TITLES


# ---- the workflow -----------------------------------------------------------------------------------------------

def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _run_blocks(text: str) -> list[str]:
    """The body of every run: script (block or one-line)."""
    blocks = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*)$", lines[i])
        if m:
            indent = len(m.group(1))
            rest = m.group(2)
            if rest.startswith(("|", ">")):
                body = []
                i += 1
                while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
                    body.append(lines[i])
                    i += 1
                blocks.append("\n".join(body))
                continue
            blocks.append(rest)
        i += 1
    return blocks


def test_workflow_permissions_are_exactly_three():
    text = _workflow_text()
    m = re.search(r"^permissions:\n((?:  \S.*\n)+)", text, re.M)
    assert m
    perms = dict(line.strip().split(": ") for line in m.group(1).splitlines())
    assert perms == {"contents": "write", "pull-requests": "write", "issues": "write"}
    assert len(re.findall(r"^\s*permissions:", text, re.M)) == 1      # no job widens them
    assert "secrets." not in text                                    # only GITHUB_TOKEN


def test_workflow_triggers_only_on_the_label():
    text = _workflow_text()
    on = re.search(r"^on:\n((?:  .*\n)+)", text, re.M).group(1)
    assert re.fullmatch(r"  issues:\n    types: \[labeled\]\n", on)
    assert "github.event.label.name == 'accept-translation'" in text
    assert "contains(github.event.issue.labels.*.name, 'translation')" in text


def test_workflow_never_interpolates_issue_text_in_a_script():
    blocks = _run_blocks(_workflow_text())
    assert blocks and any("accept_translation.py" in b for b in blocks)
    for block in blocks:
        assert "${{" not in block, block


def test_workflow_parses_as_yaml():
    yaml = pytest.importorskip("yaml")
    flow = yaml.safe_load(_workflow_text())
    on = flow.get("on", flow.get(True))          # PyYAML reads the key `on` as True
    assert on == {"issues": {"types": ["labeled"]}}
    assert flow["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "write"}
    for job in flow["jobs"].values():
        assert "permissions" not in job
        for step in job["steps"]:
            assert "${{" not in step.get("run", "")
            uses = step.get("uses", "")
            if uses:
                assert uses.split("@")[0] in ("actions/checkout", "actions/setup-python")


def test_workflow_commits_as_the_bot_and_matches_the_other_workflows_actions():
    text = _workflow_text()
    assert 'git config user.name "github-actions[bot]"' in text
    assert 'git config user.email "41898213+github-actions[bot]@users.noreply.github.com"' in text
    assert "--author" not in text
    tests_yml = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    for action in ("actions/checkout", "actions/setup-python"):
        ours = re.search(re.escape(action) + r"@(\S+)", text).group(1)
        theirs = re.search(re.escape(action) + r"@(\S+)", tests_yml).group(1)
        assert ours == theirs


def test_workflow_download_has_the_size_limit_and_host_allow_list():
    source = (ROOT / "scripts" / "accept_translation.py").read_text(encoding="utf-8")
    assert '"--max-filesize"' in source and '"=https"' in source
    assert "--location" not in source and '"-L"' not in source      # redirects are followed by hand, checked
    assert at.MAX_BYTES == 4 * 1024 * 1024
    assert at.REDIRECT_HOSTS == {"objects.githubusercontent.com"}


# ---- the accept script -------------------------------------------------------------------------------------------

def issue_body(**over) -> str:
    values = {
        "game": GAME, "language": "Français", "code": "fr", "credit": "Ana", "coverage": "75",
        "file": "[Virtual Villagers - The Secret City - Français.txt]"
                "(https://github.com/user-attachments/files/17654321/Virtual.Villagers.-.The.Secret.City.-.Francais.txt)",
        "licence": "- [X] I agree this translation can be shared under the patcher's licence",
    }
    values.update(over)
    return "\n\n".join(f"### {at.FORM_LABELS[fid]}\n\n{value or '_No response_'}" for fid, value in values.items())


def test_issue_body_is_read_by_section():
    fields = at.parse_issue_body(issue_body(coverage=""))
    assert fields["game"] == GAME and fields["credit"] == "Ana" and fields["coverage"] == ""
    assert at.licence_agreed(fields["licence"])
    assert at.find_attachment(fields["file"]).startswith("https://github.com/user-attachments/files/17654321/")


def test_a_repeated_heading_is_refused():
    body = issue_body(file="### Credit\n\nsomeone else")
    with pytest.raises(at.Refused):
        at.parse_issue_body(body)


@pytest.mark.parametrize("section", [
    "",
    "https://example.com/evil.txt",
    "https://github.com/user-attachments/files/1/a.exe",
    "https://github.com/user-attachments/files/1/a.txt https://github.com/user-attachments/files/2/b.txt",
    "http://github.com/user-attachments/files/1/a.txt",
])
def test_only_one_github_attachment_is_accepted(section):
    with pytest.raises(at.Refused):
        at.find_attachment(section)


class FakeCurl:
    """Stands in for subprocess.run: answers each URL from a table, writing the body to --output."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, argv, **kwargs):
        url = argv[-1]
        self.calls.append(argv)
        code, redirect, body, rc = self.answers[url]
        if body is not None:
            Path(argv[argv.index("--output") + 1]).write_bytes(body)

        class Proc:
            returncode = rc
            stdout = f"{code} {redirect}"
            stderr = ""
        return Proc()


def test_download_follows_only_allowed_redirects(tmp_path):
    first = "https://github.com/user-attachments/files/1/a.txt"
    good = "https://objects.githubusercontent.com/github-production-repository-file/1/a.txt?x=1"
    fake = FakeCurl({first: ("302", good, None, 0), good: ("200", "", b"hello", 0)})
    at.download(first, tmp_path / "a.txt", run=fake)
    assert (tmp_path / "a.txt").read_bytes() == b"hello"
    assert all("--max-filesize" in call and "--proto" in call for call in fake.calls)
    evil = FakeCurl({first: ("302", "https://evil.example.com/a.txt", None, 0)})
    with pytest.raises(at.Refused, match="allow-list"):
        at.download(first, tmp_path / "b.txt", run=evil)
    too_big = FakeCurl({first: ("", "", None, 63)})
    with pytest.raises(at.Refused, match="4 MB"):
        at.download(first, tmp_path / "c.txt", run=too_big)


def _fetch_copy(source: Path):
    def fetch(url, dest):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(source.read_bytes())
    return fetch


def test_prepare_accepts_and_credits_the_typed_name(tmp_path):
    source = make_file(tmp_path / "sent.txt", translator="someone else")
    repo = tmp_path / "repo"
    work = tmp_path / "work"
    outcome = at.prepare(issue_body(credit="Ana"), 42, work, repo_root=repo, fetch=_fetch_copy(source))
    assert outcome.accepted, outcome.reasons
    assert outcome.relative_path == f"translations/{GAME}/{GAME} - Français.txt"
    assert fmt.read_file(repo / outcome.relative_path).translator == "Ana"
    body = (work / "pr_body.md").read_text(encoding="utf-8")
    assert "Closes #42" in body and "Ana" in body
    assert (work / "pr_title.txt").read_text(encoding="utf-8") == f"Translation: {GAME} - Français"


def test_prepare_refuses_and_explains(tmp_path):
    source = make_file(tmp_path / "sent.txt")
    work = tmp_path / "work"
    outcome = at.prepare(issue_body(credit="me@example.com"), 7, work, repo_root=tmp_path / "repo",
                         fetch=_fetch_copy(source))
    assert not outcome.accepted
    comment = (work / "comment.md").read_text(encoding="utf-8")
    assert "me@example.com" not in comment and "email" in comment
    assert not (tmp_path / "repo" / "translations").exists()
    wrong = at.prepare(issue_body(game="Virtual Villagers - New Believers"), 8, tmp_path / "w2",
                       repo_root=tmp_path / "repo", fetch=_fetch_copy(source))
    assert not wrong.accepted


def test_markdown_cannot_mention_or_link():
    text = at.md_text("@owner [x](https://e.com) #12 a@b.com")
    assert "@owner" not in text and "](" not in text and "a@b.com" not in text
