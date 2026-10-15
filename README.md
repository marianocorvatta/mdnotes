<div align="center">

# ✦ mdnotes

**An Obsidian-style Markdown notes editor that lives in your terminal.**

Browse your notes, open them in tabs, write with syntax highlighting, and switch to a rendered reading view without leaving the terminal.

[![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Built with Textual](https://img.shields.io/badge/built%20with-Textual-5a4fcf)](https://textual.textualize.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-ff79c6.svg)](#contributing)

</div>

---

## Why mdnotes?

`nano` and `vim` are great at editing text, but they don't know what a note is. mdnotes is a notes app first:

- 📁 **A colorful note browser.** It shows only folders and `.md` files, with no hidden-file noise.
- 📝 **A Markdown editor**, with syntax highlighting, line numbers, soft wrap and familiar shortcuts (`Ctrl+S` saves; no modes to learn).
- 👁 **Reading mode.** One keystroke renders the note: headings, lists, tables, code blocks.
- 🗂 **Tabs**, so you can keep several notes open and jump between them.
- 🗑 **Safe deletes.** Notes and folders go to the system trash, not into the void.
- 🎨 **Dracula theme** out of the box.

> [!NOTE]
> The interface is currently in **Spanish** 🇦🇷. Translations are welcome. See [Contributing](#contributing).

## Installation

mdnotes needs **Python 3.12+**. The easiest way to install it is with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/marianocorvatta/mdnotes
```

Or with [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/marianocorvatta/mdnotes
```

Either way you get an `mdnotes` command on your `PATH`.

## Usage

```bash
mdnotes                 # opens ~/Documents/notes (created if missing)
mdnotes ~/work/notes    # opens a specific folder
mdnotes idea.md         # opens a note straight away
```

## Keyboard shortcuts

> `^` in the footer means **Ctrl**. For example, `^s` is `Ctrl+S`.

### Browser

| Key | Action |
|---|---|
| `↑` `↓` | Move |
| `Space` / `Enter` | Open note · expand/collapse folder |
| `n` | New note in the current folder |
| `c` | New folder (nested paths like `a/b` work) |
| `d` / `Delete` | Move note or folder to the trash |
| `p` | Toggle the preview pane |
| `t` | Go back to your open tabs |
| `Backspace` | Go to the parent folder |
| `r` | Reload |
| `q` | Quit (asks first if you have unsaved changes) |

### Editor

| Key | Action |
|---|---|
| `Ctrl+S` | Save |
| `Ctrl+R` | Toggle reading mode |
| `Ctrl+T` | Open a note in a new tab (`Ctrl+N` inside creates a new one) |
| `Ctrl+W` | Close tab |
| `Alt+←` / `Alt+→` | Previous / next tab |
| `Alt+1` … `Alt+9` | Jump to tab N |
| `Esc` | Back to the browser (tabs stay open) |

In dialogs, `Enter` confirms and `Esc` cancels.

## Development

```bash
git clone https://github.com/marianocorvatta/mdnotes
cd mdnotes
uv sync
uv run mdnotes
```

To install your local checkout as a global command, with live edits:

```bash
uv tool install --editable .
```

The whole app is a single file, [`mdnotes.py`](mdnotes.py), built on [Textual](https://textual.textualize.io/).

## Roadmap

Ideas for future work. Contributions are very welcome:

- [ ] `[[wikilinks]]` between notes and backlinks
- [ ] Full-text search across notes
- [ ] Rename / move notes
- [ ] English UI and i18n
- [ ] Configurable notes directory and theme
- [ ] Tags and front-matter support

## Contributing

Issues and pull requests are welcome!

1. Fork the repo and create a branch: `git checkout -b feature/my-idea`
2. Make your changes and try them with `uv run mdnotes`
3. Open a pull request describing what you changed and why

If you find a bug, please open an issue with your terminal emulator, your OS, and the steps to reproduce it.

## License

[MIT](LICENSE) © Mariano Corvatta
