# Shared translations: the maintainer's side

Players make translations in the patcher's Translations window and send them with **Share on GitHub...**.
That opens this repository's **Share a translation** issue form (`.github/ISSUE_TEMPLATE/translation.yml`)
with the title, game, language and language code already filled in. The player drags the exported `.txt`
file into the form, types the name they want to be credited as, checks the licence box and presses Submit.
A GitHub account is needed; nothing else personal is asked for. The file format is in
[translation-file-format.md](translation-file-format.md).

Translations also arrive as **pull requests** into the public folder `translations/` (one folder per game,
`translations/vv1/` .. `translations/vv5/`, one `<language code>.tsv` per language; `translations/README.md`
tells players how): anyone can use GitHub's **Add file -> Upload files** there, which opens a pull request
for people without write access. Players download from the same folder with the patcher's **Download from
GitHub...**.

Nothing is added to the repository until you say so. **Every submitted file is sent to VirusTotal first**
(the owner, 2026-11-02: "PLEASE RUN EVERY SINGLE USER-SUBMITTED FILE THROUGH VIRUSTOTAL AND REJECT ANYTHING
THAT IS FLAGGED"); anything flagged, or not scanned for any reason, is refused.

## One-time setup

1. **Labels.** Create two labels in the repository (Issues -> Labels): `translation` (the form puts it on
   every submission; GitHub only applies a label that already exists) and `accept-translation` (you add it
   to accept).
2. **The VirusTotal key.** The scan needs a VirusTotal API key in the repository secret **`VT_API_KEY`**.
   Without it every submission fails with "not scanned" (never a pass). To add it:
   1. sign in at https://www.virustotal.com (a free account is enough; the free API allows 4 requests a
      minute, which the scan respects), open your profile menu -> **API key**, and copy the key;
   2. in this repository: Settings -> Secrets and variables -> Actions -> **New repository secret**, name
      `VT_API_KEY`, paste the key, **Add secret**.
   The key is only ever read by the scan step from its environment: it is never printed, logged, written to a
   file or put on a command line.
3. **Let the workflow open pull requests.** Settings -> Actions -> General -> Workflow permissions: check
   **Allow GitHub Actions to create and approve pull requests**. Without it the workflow's
   `gh pr create` is refused and the issue gets the "stopped unexpectedly" comment.

## Accepting a translation, step by step

1. Open the issue. Read the credit name (it will be public) and glance at the coverage.
2. Add the label **accept-translation**. The workflow `accept-translation`
   (`.github/workflows/accept-translation.yml`) starts; watch it under Actions if you like (about a minute).
3. **If the file passes**, the workflow:
   - sends the attached file to VirusTotal (flagged or not scanned: refused, with the engines named);
   - writes `translations/vv<N>/<code>.tsv` (from the file's `@code` row; when another translator's file of
     that language is already there, `<code>-<credit slug>.tsv`, so nobody's file is overwritten; the same
     translator's own file is updated) with `@translator` set to the credit typed in the form;
   - commits it on the branch `translation/issue-<N>` as **github-actions[bot]** (never as the player);
   - opens a pull request titled `Translation: <Game title> - <Language>`, crediting the translator by the
     typed name only, with the validation report and `Closes #<N>`;
   - comments on the issue with the pull request's link.
4. Open the pull request and look at **Files changed**: it is one text file. Merge it. Merging closes the
   issue (`Closes #<N>`).

   Pull requests opened with the workflow's own token do not start the `tests` workflow (a GitHub rule that
   stops workflows triggering each other). The file was already checked by the same validator, and the
   release build checks it again (below). If you want the tests to run on it anyway, close and reopen the
   pull request.
5. **If the file is refused**, the workflow comments on the issue with every reason (each problem names its
   line in the file), removes the `accept-translation` label, and the run shows red. Nothing is committed.
   The player can fix the file in the Translations window and send it again, or edit the issue to drag the
   fixed file into the **Translation file** box; then add the label again.

## Pull requests into translations/ (translation-pr.yml)

Every pull request that touches `translations/` runs two required checks, in this order, and comments the
results on the pull request:

1. **scan**: each file must be a UTF-8 `.tsv` at `translations/vv1/` .. `translations/vv5/<code>.tsv` (or
   `<code>-<credit slug>.tsv`), at most 2 MB; `README.md` and `manifest.json` cannot be changed by a
   submission. Each file is looked up on VirusTotal by its SHA-256 (`GET /api/v3/files/{sha256}`); unknown to
   VirusTotal, it is uploaded (`POST /api/v3/files`) and its analysis polled (`/api/v3/analyses/{id}`, up to
   ten minutes, at most 4 requests a minute, waiting longer when VirusTotal says the limit was reached). ANY
   engine reporting malicious or suspicious fails the check, naming the engines. No key, VirusTotal
   unreachable, a timeout: **not scanned**, which fails the same way.
2. **validate** (only after a clean scan): `scripts/validate_translation.py`, as below.

To accept: **merge** the pull request, or add the **accept-translation** label to it. The label runs both
checks again; if they pass the workflow merges the pull request itself and records the files; if not it
removes the label and comments why. After any merge into the default branch, `translation-record.yml` scans
the folder's files again where needed and writes **`translations/manifest.json`** (each clean, valid file's
SHA-256, scan date, verdict, language, code and credit). **Download from GitHub... offers only files listed
clean there, and refuses a download whose SHA-256 is not the one listed.** A file you merge that is flagged is
left out of the manifest (the run names it): delete it.

Why `pull_request_target`: a pull request from a fork gets no secrets under the plain `pull_request` event, so
every outside submission would fail as "not scanned". `translation-pr.yml` therefore runs as
`pull_request_target`, which runs the workflow **as it is on the pull request's base branch** (this repository's own), and it checks out **only
that base commit**: nothing of the pull request is checked out, installed, imported or run. The submitted
files are read as data through the GitHub API, blob by blob, and only decoded and parsed. Pull request text
never reaches a `run:` script except through environment variables. Its jobs ask only for `contents`,
`pull-requests` and `issues` (write only where needed).

Files whose `@language` or `@translator` starts with `(TEST)` are test files: they stay here (and can be
downloaded), and `scripts/build_release.py` keeps them out of every release. Every other accepted file ships
in the release's `translations/vv<N>/`.

## What the workflow checks

From the issue form:

- the issue has every section of the form exactly once (text typed into one box cannot pose as another);
- the game is one of the five Virtual Villagers titles;
- the credit is not empty, at most 80 characters, one line, and not an email address;
- the language and code are filled in and match the file's `@language` and `@code` rows;
- the licence box is checked;
- the **Translation file** box holds exactly one link, a GitHub file attachment
  (`https://github.com/user-attachments/files/...`) ending in `.txt`.

The file, with `scripts/validate_translation.py`, which runs the patcher's own validator
(`src/vv_translation_format.py`, the same code as the Translations window's **Validate**):

- at most 4 MB; UTF-8 (or UTF-16 with a byte-order mark); the header row; format version 1;
- the `@game` row is the form's game; `@language` and `@code` are present and well formed;
- **no email address anywhere** in the file: credit, `@translator`, any row, any comment. An email refuses
  the whole file ("Email addresses are never saved and are rejected from translation files.");
- every translated line: printf placeholders the same and in the same order, `{variables}` kept, gender and
  plural selects well formed, no stray `%`, no edited Key or English column. A line with an error is listed
  and simply stays English in the game, as it would in the patcher;
- **at least one translated line** must be usable;
- **refusal threshold:** when more than half of the translated lines have errors, the file is refused as
  damaged (usually a spreadsheet that broke the columns or placeholders) rather than shipped half English.

You can run the same check on your computer:

```
python scripts/validate_translation.py "Virtual Villagers - The Secret City - Français.txt" --game "Virtual Villagers - The Secret City" --credit "Ana" --markdown report.md
```

Exit code 0 means accepted, 1 refused; emails are masked in everything it prints.

## How an accepted translation ships

- `scripts/build_release.py` collects every `translations/vv<N>/*.tsv` into `TRANSLATION_FILES` and adds them
  to the release zip automatically, except `(TEST)` files (owner, 2026-11-02: "Only exclude TEST files"),
  which are left out of the release zip and the source zip; nothing to list by hand.
- The release build checks each one again (`_assert_translations_valid`: it must read, be for the game its
  folder names, and contain no email address) and stops if one fails.
- After the next release every player sees it in the game's **Translations** dropdown as
  `<Language>, by <credit>`.

## Rejecting a translation

Do not add the label. Comment on the issue saying why (politely; it is public) and close it as "not
planned". Nothing reaches the repository. If you added the label by mistake and a pull request was opened,
close the pull request without merging and delete its `translation/issue-<N>` branch.

## Updating a translation

A translator sends the updated file with the form like a new one. Accepting it writes the same path
(`translations/vv<N>/<code>.tsv` for the same credit), so the pull request **replaces** that translator's
file and says so; the diff shows exactly which lines changed. If a different person sends a translation for
a language that already exists, it is added beside it as `<code>-<credit slug>.tsv`: both stay, and players
see both in Download from GitHub..., each with its credit. You can also edit the file yourself in a normal commit; the release build checks
it the same way.

To accept a fixed file on the same issue, add the `accept-translation` label again: the workflow replaces
the `translation/issue-<N>` branch and the open pull request picks up the new file.

## Security notes

- The workflow runs only when the `accept-translation` label is added to an issue that also has the
  `translation` label. Only people with triage access or more can add labels, so a stranger cannot start
  it.
- Its token has exactly `contents: write`, `pull-requests: write` and `issues: write`. Its only secrets are
  the workflow's own `GITHUB_TOKEN` and `VT_API_KEY`, which reaches only the step that prepares the file, as an
  environment variable, and is never printed.
- The issue's text is passed to `scripts/accept_translation.py` only through an environment variable. No
  `${{ github.event.issue.* }}` appears inside a `run:` script, so nothing a player types can become shell
  code (script injection). The PR title and body are written to files by the script and read by `gh` from
  those files.
- The file is downloaded with curl over https only, from a `github.com/user-attachments/files/...` link
  only; redirects are not followed automatically: each one is checked against the allow-list
  (`objects.githubusercontent.com`) first. At most 4 MB (`--max-filesize`, then the size on disk), with a
  60-second limit. If GitHub ever moves attachments to another host, the run is refused with the host's
  name; add it to `REDIRECT_HOSTS` in `scripts/accept_translation.py` after checking it is GitHub's.
- The file is only data: it is decoded as text and parsed. Nothing in it, or in the issue, is executed,
  sourced or evaluated. What is committed is re-written by the validator (UTF-8 with a byte-order mark,
  CRLF) and checked again after writing.
- Commits are made as `github-actions[bot] <41898213+github-actions[bot]@users.noreply.github.com>`. The
  translator is credited only by the name they typed, never by their GitHub login (unless that is what they
  typed) and never by an email address. Text from the issue shown in pull requests and comments is escaped
  so it cannot @mention anyone or add links, and email-like text is masked.
- Always look at **Files changed** before merging: the issue's body is read at the moment the label is
  added, and the pull request shows exactly what will ship.
