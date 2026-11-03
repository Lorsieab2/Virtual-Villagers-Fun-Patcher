# Translations of the Virtual Villagers games

This is the public folder of translations for the **Virtual Villagers Fun Patcher**. Anyone can download a
translation from here, translate a game, and send a translation back.

One folder per game, one file per language:

| Folder | Game |
| --- | --- |
| `vv1/` | Virtual Villagers - A New Home |
| `vv2/` | Virtual Villagers - The Lost Children |
| `vv3/` | Virtual Villagers - The Secret City |
| `vv4/` | Virtual Villagers - The Tree of Life |
| `vv5/` | Virtual Villagers - New Believers |

Each file is named `<language code>.tsv` (for example `vv3/fr.tsv` or `vv1/pt-br.tsv`; names are lowercase). When a language is
already here from someone else, a new one is named `<code>-<credit>.tsv` (for example `vv3/fr-ana.tsv`; the
credit in lowercase letters, digits and hyphens, then `-2`, `-3` ...), so nobody's file is ever overwritten.
The format is described in [docs/translation-file-format.md](../docs/translation-file-format.md): a plain
UTF-8 text file with tab-separated columns `Key`, `English`, `Translation` (and `Notes`).

Files whose language or credit starts with `(TEST)` are test files: they stay here and can be downloaded, but
never ship with the patcher.

## Download

- **In the patcher:** Tools tab, **Translations...**, **Download from GitHub...**. It lists this folder's files
  for the chosen game (language, credit, when each last changed, and "Update available" when the copy here is
  newer than yours), downloads the ones you select, checks them, and installs them.
- **By hand:** open a file here, press **Download raw file**, then use **Add translation file...** in the
  patcher's Translations window.

## Translate

- **In the patcher (easiest):** Translations window, **Make a translation...**. Pick your language; the
  built-in editor shows every English line of your own game, and of every patch, beside the translation, with
  a preview in the game's letters. It saves by itself.
- **In any editor:** open a downloaded file in a text editor or spreadsheet that keeps tabs and UTF-8, and
  type into the `Translation` column only. Keep `%d`, `%s`, `{name}` and the other placeholders exactly.
  Lines you leave empty stay English. [docs/translating-the-games.md](../docs/translating-the-games.md) is the
  translator's guide.

## Upload

- **In the patcher:** **Share on GitHub...** in the Translations window opens the "Share a translation" form.
- **On this page, without the patcher:** press **Add file**, then **Upload files**, drag your `.tsv` file into
  the right game's folder name (for example `translations/vv3/fr.tsv`), and press **Propose changes**. If you
  do not have write access, GitHub makes a fork and opens a pull request for you; that is all you need to do.

The privacy warning, exactly as the patcher's **Share on GitHub...** button shows it:

> This button allows you to share your game translation to the patcher's Public Github. IF ACCEPTED, everyone who uses this patcher will be able to see your translation in the game and your username will be included in the credits. Please DO NOT put ANY PRIVATE DETAILS YOU DO NOT WANT TO MAKE PUBLIC!
>
> Email addresses are never saved and are rejected from translation files.
>
> This feature is meant to be a community collaboration tool for game modding only.
>
> You will need a Github account to proceed. Continue?

**Every uploaded file is sent to VirusTotal** to be scanned before anyone looks at it, and anything it flags is
refused. That is one more reason never to put private details in a translation file.

### Your credit name

The `@translator` row is the name shown publicly with your translation ("Français, by Ana"). Type the name you
want to be credited as, a nickname is fine, into its `Translation` column (the patcher asks for it when you
share). It must be one line and at most 80 characters. **Email addresses are rejected**: a file with an email
address anywhere in it is refused.

## What happens to an upload

1. **VirusTotal scan** (required, first): the file must be a UTF-8 `.tsv` under `translations/vv1/` ..
   `translations/vv5/`, at most 2 MB. It is looked up on VirusTotal and, when VirusTotal does not know it,
   uploaded and analysed. If any engine reports it as malicious or suspicious, or it could not be scanned, the
   check fails and the pull request gets a comment naming the engines.
2. **Translation check** (after a clean scan): the patcher's own validator checks the format, the keys, every
   placeholder, the gender and plural selects, and that there is no email address.
3. The results are commented on the pull request. The owner accepts it by merging or with the
   `accept-translation` label (the files are scanned and checked again first).
4. Accepted files are recorded in `manifest.json` with their SHA-256 and scan result. The patcher only
   downloads files listed there as clean.
