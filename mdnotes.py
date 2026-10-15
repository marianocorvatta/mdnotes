"""mdnotes - editor de Markdown estilo Obsidian para la terminal."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

from send2trash import send2trash
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
    OptionList,
    TextArea,
)
from textual.widgets.option_list import Option
from rich.text import Text


DEFAULT_DIR = Path.home() / "Documents" / "notes"


class MdTree(DirectoryTree):
    """Arbol que solo muestra carpetas y archivos .md (sin ocultos)."""

    BINDINGS = [Binding("space", "open_node", "Abrir", show=True)]

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            p
            for p in paths
            if not p.name.startswith(".")
            and (p.is_dir() or p.suffix.lower() in (".md", ".markdown"))
        ]

    def action_open_node(self) -> None:
        node = self.cursor_node
        if node is None or node.data is None:
            return
        path = node.data.path
        if path.is_dir():
            self.cursor_node.toggle()
        else:
            self.post_message(self.FileSelected(node, path))


class NameDialog(ModalScreen[str | None]):
    """Pide el nombre de una nota nueva."""

    BINDINGS = [Binding("escape", "cancel", "Cancelar")]

    def __init__(self, folder: Path, title: str = "✨ Nueva nota",
                 placeholder: str = "nombre-de-la-nota", value: str = "") -> None:
        super().__init__()
        self.folder = folder
        self.title_text = title
        self.placeholder = placeholder
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.title_text, classes="dialog-title")
            yield Label(f"en [b]{self.folder}[/b]", classes="dialog-sub")
            yield Input(self.value, placeholder=self.placeholder, id="name")
            with Horizontal(classes="buttons"):
                yield Button("Crear", variant="success", id="ok")
                yield Button("Cancelar", variant="error", id="cancel")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    @on(Button.Pressed, "#ok")
    def submit(self) -> None:
        name = self.query_one(Input).value.strip()
        self.dismiss(name or None)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmDialog(ModalScreen[str]):
    """Confirmacion al salir con cambios sin guardar."""

    BINDINGS = [
        Binding("escape", "dismiss('cancel')", "Cancelar"),
        Binding("enter", "dismiss('save')", "Guardar", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("⚠  Hay cambios sin guardar", classes="dialog-title")
            yield Label("[#6272a4]Enter = guardar · Esc = cancelar[/]")
            with Horizontal(classes="buttons"):
                yield Button("Guardar", variant="success", id="save")
                yield Button("Descartar", variant="error", id="discard")
                yield Button("Cancelar", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id or "cancel")


class DeleteDialog(ModalScreen[bool]):
    """Confirmar borrado. Enter acepta, Esc cancela."""

    BINDINGS = [
        Binding("escape", "dismiss(False)", "Cancelar"),
        Binding("enter", "dismiss(True)", "Eliminar", priority=True),
    ]

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        kind = "la carpeta" if self.path.is_dir() else "la nota"
        with Vertical(id="dialog"):
            yield Label("🗑  Eliminar", classes="dialog-title")
            yield Label(f"¿Mandar a la papelera {kind} [b]{self.path.name}[/b]?")
            if self.path.is_dir():
                yield Label("[#ff5555]Se borra con todo su contenido.[/]")
            yield Label("[#6272a4]Enter = eliminar · Esc = cancelar[/]")
            with Horizontal(classes="buttons"):
                yield Button("Eliminar", variant="error", id="yes")
                yield Button("Cancelar", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


MAX_RESULTS = 300


def search_notes(root: Path, query: str) -> list[tuple[Path, int, str]]:
    """Busca `query` (sin distinguir mayusculas) en nombres y contenido de las notas."""
    q = query.lower()
    hits: list[tuple[Path, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in (".md", ".markdown") or any(
            part.startswith(".") for part in path.relative_to(root).parts
        ):
            continue
        if q in path.stem.lower():
            hits.append((path, 0, ""))
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            if q in line.lower():
                hits.append((path, i, line.strip()))
                if len(hits) >= MAX_RESULTS:
                    return hits
    return hits


def highlight(text: str, query: str, style: str) -> Text:
    out = Text(text)
    out.highlight_words([query], style=style, case_sensitive=False)
    return out


class SearchDialog(ModalScreen[tuple[Path, int] | None]):
    """Busqueda de texto completo en todas las notas."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cerrar"),
        Binding("down", "focus_results", show=False),
    ]

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root

    def compose(self) -> ComposeResult:
        with Vertical(id="search-dialog"):
            yield Label("🔎 Buscar en todas las notas", classes="dialog-title")
            yield Input(placeholder="escribí para buscar…", id="query")
            yield Label("[#6272a4]↓ = ir a resultados · Enter = abrir · Esc = cerrar[/]",
                        id="search-status", classes="dialog-sub")
            yield OptionList(id="results")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def action_focus_results(self) -> None:
        results = self.query_one(OptionList)
        if results.option_count:
            results.focus()
            results.highlighted = results.highlighted or 0

    @on(Input.Changed)
    def changed(self, event: Input.Changed) -> None:
        self.run_search(event.value.strip())

    @work(exclusive=True, thread=True)
    def run_search(self, query: str) -> None:
        hits = search_notes(self.root, query) if len(query) >= 2 else []
        self.app.call_from_thread(self.show_results, query, hits)

    def show_results(self, query: str, hits: list[tuple[Path, int, str]]) -> None:
        results = self.query_one(OptionList)
        results.clear_options()
        self.hits = hits
        for i, (path, line, snippet) in enumerate(hits):
            rel = str(path.relative_to(self.root))
            label = Text()
            label.append_text(highlight(rel, query, "bold #ff79c6"))
            label.stylize("#8be9fd")
            if snippet:
                label.append(f":{line + 1}  ", style="#6272a4")
                label.append_text(highlight(snippet[:200], query, "bold reverse #f1fa8c"))
            else:
                label.append("  (nombre)", style="#6272a4")
            results.add_option(Option(label, id=str(i)))
        status = self.query_one("#search-status", Label)
        if len(query) < 2:
            status.update("[#6272a4]Escribí al menos 2 letras · Esc = cerrar[/]")
        else:
            extra = "+" if len(hits) >= MAX_RESULTS else ""
            status.update(f"[#50fa7b]{len(hits)}{extra} resultados[/] "
                          "[#6272a4]· ↓ = ir a resultados · Enter = abrir[/]")

    @on(Input.Submitted)
    def submit_first(self) -> None:
        if getattr(self, "hits", None):
            path, line, _ = self.hits[0]
            self.dismiss((path, line))

    @on(OptionList.OptionSelected)
    def picked(self, event: OptionList.OptionSelected) -> None:
        path, line, _ = self.hits[int(event.option.id or 0)]
        self.dismiss((path, line))


def rename_path(app: App, path: Path) -> None:
    """Pide un nombre nuevo y renombra la nota/carpeta (actualiza pestañas abiertas)."""
    is_dir = path.is_dir()
    current = path.name if is_dir else path.stem

    def done(name: str | None) -> None:
        if not name or name == current:
            return
        if not is_dir and not name.lower().endswith((".md", ".markdown")):
            name += path.suffix or ".md"
        target = path.parent / name
        if target.exists():
            app.notify(f"Ya existe {target.name}", title="Error", severity="error")
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
        except OSError as e:
            app.notify(str(e), title="Error", severity="error")
            return
        app.workspace.paths_moved(path, target)
        if isinstance(app.screen, PickerScreen):
            app.screen.action_reload()
        app.notify(f"{path.name} → {target.name}", title="✏️ Renombrado")

    title = "✏️ Renombrar carpeta" if is_dir else "✏️ Renombrar nota"
    app.push_screen(NameDialog(path.parent, title, "nuevo-nombre", current), done)


class PickerScreen(Screen):
    """Explorador de notas."""

    BINDINGS = [
        Binding("n", "new_note", "Nueva nota"),
        Binding("c", "new_folder", "Nueva carpeta"),
        Binding("d,delete", "delete", "Eliminar"),
        Binding("slash,ctrl+f", "search", "Buscar"),
        Binding("f2,m", "rename", "Renombrar"),
        Binding("backspace", "go_up", "Subir carpeta"),
        Binding("r", "reload", "Recargar"),
        Binding("p", "toggle_preview", "Vista previa"),
        Binding("t", "app.show_tabs", "Pestañas abiertas"),
        Binding("q", "app.request_quit", "Salir"),
    ]

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="side"):
                yield Static("📁 " + str(self.root), id="path")
                yield MdTree(self.root, id="tree")
            with Vertical(id="preview-pane"):
                yield Static("👁  Vista previa", id="preview-title")
                yield Markdown(
                    "# mdnotes\n\nMové el cursor sobre una nota para verla acá.\n\n"
                    "- **Espacio / Enter** → abrir\n- **n** → nueva nota\n"
                    "- **c** → nueva carpeta\n- **d / Supr** → eliminar\n"
                    "- **/** → buscar en todas las notas\n- **F2 / m** → renombrar\n"
                    "- **Backspace** → carpeta superior",
                    id="preview",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#preview-pane").display = False
        self.query_one(MdTree).focus()

    def action_toggle_preview(self) -> None:
        pane = self.query_one("#preview-pane")
        pane.display = not pane.display
        node = self.query_one(MdTree).cursor_node
        if pane.display and node is not None and node.data is not None:
            self._preview(node.data.path)

    @on(DirectoryTree.NodeHighlighted)
    def show_preview(self, event: DirectoryTree.NodeHighlighted) -> None:
        data = event.node.data
        if data is not None and self.query_one("#preview-pane").display:
            self._preview(data.path)

    def _preview(self, path: Path) -> None:
        if path.is_dir():
            return
        try:
            text = path.read_text(encoding="utf-8")[:20000]
        except OSError as e:
            text = f"*No se pudo leer:* `{e}`"
        self.query_one("#preview-title", Static).update("👁  " + path.name)
        self.query_one("#preview", Markdown).update(text)

    @on(DirectoryTree.FileSelected)
    def open_file(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        self.app.open_note(event.path)

    def _current_folder(self) -> Path:
        node = self.query_one(MdTree).cursor_node
        if node is not None and node.data is not None:
            p = node.data.path
            return p if p.is_dir() else p.parent
        return self.root

    def action_new_note(self) -> None:
        folder = self._current_folder()

        def created(name: str | None) -> None:
            if not name:
                return
            path = create_note(folder, name)
            self.action_reload()
            self.app.open_note(path)

        self.app.push_screen(NameDialog(folder), created)

    def action_new_folder(self) -> None:
        folder = self._current_folder()

        def created(name: str | None) -> None:
            if not name:
                return
            path = folder / name
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self.notify(str(e), title="Error", severity="error")
                return
            self.action_reload()
            self.notify(f"Carpeta creada: {path.name}", title="📁")

        self.app.push_screen(
            NameDialog(folder, "📁 Nueva carpeta", "nombre-de-la-carpeta"), created
        )

    def action_delete(self) -> None:
        node = self.query_one(MdTree).cursor_node
        if node is None or node.data is None:
            return
        path = node.data.path
        if path == self.root:
            self.notify("No se puede borrar la carpeta raíz", severity="warning")
            return

        def confirmed(ok: bool | None) -> None:
            if not ok:
                return
            try:
                send2trash(path)
            except Exception as e:
                self.notify(str(e), title="Error", severity="error")
                return
            self.action_reload()
            self.notify(f"{path.name} enviado a la papelera", title="🗑")

        self.app.push_screen(DeleteDialog(path), confirmed)

    def action_search(self) -> None:
        self.app.action_search()

    def action_rename(self) -> None:
        node = self.query_one(MdTree).cursor_node
        if node is None or node.data is None or node.data.path == self.root:
            return
        rename_path(self.app, node.data.path)

    def _set_root(self, root: Path) -> None:
        self.root = root
        self.query_one(MdTree).path = root
        self.query_one("#path", Static).update("📁 " + str(root))

    def action_go_up(self) -> None:
        if self.root.parent != self.root:
            self._set_root(self.root.parent)

    def action_reload(self) -> None:
        self.query_one(MdTree).reload()


class NoteEditor(Vertical):
    """Una nota abierta (contenido de una pestaña)."""

    def __init__(self, path: Path, **kw) -> None:
        super().__init__(**kw)
        self.path = path
        self.saved_text = path.read_text(encoding="utf-8") if path.exists() else ""

    def compose(self) -> ComposeResult:
        with Vertical(classes="editor-pane"):
            yield Static(classes="file-title")
            yield TextArea(
                self.saved_text,
                language="markdown",
                theme="dracula",
                soft_wrap=True,
                show_line_numbers=True,
                tab_behavior="indent",
                classes="editor",
            )
        with Vertical(classes="live-pane"):
            yield Static("👁  Modo lectura", classes="live-title")
            yield Markdown(self.saved_text, classes="live")

    def on_mount(self) -> None:
        self.query_one(".live-pane").display = False
        self.refresh_title()

    @property
    def text_area(self) -> TextArea:
        return self.query_one(TextArea)

    @property
    def dirty(self) -> bool:
        return self.text_area.text != self.saved_text

    def refresh_title(self) -> None:
        mark = "  [b #ff79c6]● sin guardar[/]" if self.dirty else "  [#50fa7b]✓ guardado[/]"
        self.query_one(".file-title", Static).update(f"📝 [b]{self.path.name}[/b]{mark}")

    @on(TextArea.Changed)
    def changed(self) -> None:
        self.refresh_title()
        self.screen.update_tab_label(self)

    def save(self) -> None:
        text = self.text_area.text
        self.path.write_text(text, encoding="utf-8")
        self.saved_text = text
        self.refresh_title()
        self.screen.update_tab_label(self)
        self.notify(f"Guardado {self.path.name}", title="💾")

    def toggle_reading(self) -> None:
        editor = self.query_one(".editor-pane")
        live = self.query_one(".live-pane")
        reading = editor.display
        editor.display = not reading
        live.display = reading
        self.query_one(".live", Markdown).update(self.text_area.text)
        (live if reading else self.text_area).focus()

    def goto_line(self, line: int) -> None:
        if self.query_one(".live-pane").display:
            self.toggle_reading()
        self.text_area.move_cursor((line, 0))
        self.text_area.scroll_cursor_visible(center=True)

    def focus_editor(self) -> None:
        if self.query_one(".editor-pane").display:
            self.text_area.focus()


class OpenNoteDialog(ModalScreen[Path | None]):
    """Elegir (o crear) una nota para abrir en una pestaña nueva."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancelar"),
        Binding("ctrl+n", "new_note", "Nueva nota", priority=True),
    ]

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root

    def compose(self) -> ComposeResult:
        with Vertical(id="open-dialog"):
            yield Label("🗂  Abrir en pestaña nueva", classes="dialog-title")
            yield Label(
                "[#6272a4]Espacio/Enter = abrir · Ctrl+N = nota nueva · Esc = cancelar[/]",
                classes="dialog-sub",
            )
            yield MdTree(self.root, id="tree")

    def on_mount(self) -> None:
        self.query_one(MdTree).focus()

    @on(DirectoryTree.FileSelected)
    def picked(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        self.dismiss(event.path)

    def action_new_note(self) -> None:
        node = self.query_one(MdTree).cursor_node
        folder = self.root
        if node is not None and node.data is not None:
            folder = node.data.path if node.data.path.is_dir() else node.data.path.parent

        def created(name: str | None) -> None:
            if name:
                self.dismiss(create_note(folder, name))

        self.app.push_screen(NameDialog(folder), created)


def create_note(folder: Path, name: str) -> Path:
    if not name.lower().endswith((".md", ".markdown")):
        name += ".md"
    path = folder / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {Path(name).stem}\n\n", encoding="utf-8")
    return path


class EditorScreen(Screen):
    """Editor con pestañas."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Guardar", priority=True),
        Binding("ctrl+t", "new_tab", "Nueva pestaña", priority=True),
        Binding("ctrl+w", "close_tab", "Cerrar pestaña", priority=True),
        Binding("alt+right", "next_tab", "Pestaña →", priority=True),
        Binding("alt+left", "prev_tab", "← Pestaña", priority=True),
        Binding("ctrl+r", "reading_mode", "Modo lectura", priority=True),
        Binding("ctrl+f", "app.search", "Buscar", priority=True),
        Binding("f2", "rename", "Renombrar", priority=True),
        Binding("escape", "back", "Explorador", priority=True),
    ] + [
        Binding(f"alt+{i}", f"goto_tab({i})", show=False, priority=True)
        for i in range(1, 10)
    ]

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self._counter = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield TabbedContent(id="tabs")
        yield Footer()

    # --- helpers -------------------------------------------------------
    @property
    def tabs(self) -> TabbedContent:
        return self.query_one(TabbedContent)

    def editors(self) -> list[NoteEditor]:
        return list(self.query(NoteEditor))

    def current(self) -> NoteEditor | None:
        pane = self.tabs.active_pane
        if pane is None:
            return None
        found = pane.query(NoteEditor)
        return found.first() if found else None

    def _pane_id(self, ed: NoteEditor) -> str:
        return ed.parent.id  # type: ignore[union-attr]

    def update_tab_label(self, ed: NoteEditor) -> None:
        label = ("● " if ed.dirty else "") + ed.path.stem
        self.tabs.get_tab(self._pane_id(ed)).label = label

    def _on_switch(self) -> None:
        ed = self.current()
        if ed:
            self.app.sub_title = str(ed.path)
            self.call_after_refresh(ed.focus_editor)

    @on(TabbedContent.TabActivated)
    def tab_activated(self) -> None:
        self._on_switch()

    # --- open / close --------------------------------------------------
    def open_note(self, path: Path) -> None:
        path = path.resolve()
        for ed in self.editors():
            if ed.path == path:
                self.tabs.active = self._pane_id(ed)
                self._on_switch()
                return
        self._counter += 1
        pane_id = f"tab-{self._counter}"
        ed = NoteEditor(path)
        self.tabs.add_pane(TabPane(path.stem, ed, id=pane_id))
        self.tabs.active = pane_id
        self.call_after_refresh(self._on_switch)

    @work(exclusive=True)
    async def _remove(self, ed: NoteEditor) -> None:
        await self.tabs.remove_pane(self._pane_id(ed))
        if self.editors():
            self._on_switch()
        elif self.app.screen is self:
            self.action_back()

    # --- actions -------------------------------------------------------
    def action_save(self) -> None:
        if ed := self.current():
            ed.save()

    def action_reading_mode(self) -> None:
        if ed := self.current():
            ed.toggle_reading()

    def action_new_tab(self) -> None:
        def picked(path: Path | None) -> None:
            if path:
                self.open_note(path)
            else:
                self._on_switch()

        self.app.push_screen(OpenNoteDialog(self.root), picked)

    def action_close_tab(self) -> None:
        ed = self.current()
        if ed is None:
            return
        if not ed.dirty:
            self._remove(ed)
            return

        def decide(choice: str) -> None:
            if choice == "save":
                ed.save()
                self._remove(ed)
            elif choice == "discard":
                self._remove(ed)

        self.app.push_screen(ConfirmDialog(), decide)

    def _cycle(self, step: int) -> None:
        panes = [self._pane_id(e) for e in self.editors()]
        if len(panes) > 1 and self.tabs.active in panes:
            i = panes.index(self.tabs.active)
            self.tabs.active = panes[(i + step) % len(panes)]

    def action_next_tab(self) -> None:
        self._cycle(1)

    def action_prev_tab(self) -> None:
        self._cycle(-1)

    def action_goto_tab(self, n: int) -> None:
        panes = [self._pane_id(e) for e in self.editors()]
        if n <= len(panes):
            self.tabs.active = panes[n - 1]

    def action_rename(self) -> None:
        if ed := self.current():
            if ed.dirty:
                ed.save()
            rename_path(self.app, ed.path)

    def paths_moved(self, old: Path, new: Path) -> None:
        """Actualiza las pestañas cuyo archivo se renombro/movio."""
        if not self.is_mounted:
            return
        old, new = old.resolve(), new.resolve()
        for ed in self.editors():
            if ed.path == old or old in ed.path.parents:
                ed.path = new / ed.path.relative_to(old) if ed.path != old else new
                ed.refresh_title()
                self.update_tab_label(ed)
        if (ed := self.current()) and self.app.screen is self:
            self.app.sub_title = str(ed.path)

    def action_back(self) -> None:
        """Vuelve al explorador; las pestañas quedan abiertas."""
        self.app.sub_title = "Notas Markdown"
        self.app.pop_screen()
        self.app.screen.query_one(MdTree).reload()


class MdNotes(App):
    TITLE = "✦ mdnotes"
    SUB_TITLE = "Notas Markdown"
    CSS = """
    Screen { background: #1e1f29; }
    Header { background: #44475a; color: #f8f8f2; }
    Footer { background: #282a36; }

    #side { width: 1fr; max-width: 100%; border: round #bd93f9; margin: 0 1; }
    #path { color: #8be9fd; text-style: bold; padding: 0 1; height: 1; }
    #tree { background: transparent; scrollbar-size-vertical: 1; }
    #tree > .directory-tree--folder { color: #bd93f9; text-style: bold; }
    #tree > .directory-tree--file { color: #f8f8f2; }
    #tree > .directory-tree--extension { color: #50fa7b; }
    #tree > .tree--cursor { background: #ff79c6 40%; text-style: bold; }
    #tree:focus > .tree--cursor { background: #ff79c6 60%; }

    #preview-title, .live-title, .file-title {
        height: 1; padding: 0 1; color: #f1fa8c; text-style: bold;
    }
    Markdown { background: transparent; padding: 0 2; }

    #preview-pane, .live-pane { border: round #50fa7b; margin: 0 1; }
    .editor-pane { border: round #bd93f9; margin: 0 1; }
    .editor-pane:focus-within { border: round #ff79c6; }
    .editor { border: none; background: #282a36; }
    #tabs { height: 1fr; }
    #tabs TabPane { padding: 0; height: 1fr; }
    NoteEditor { height: 1fr; }
    Tab { color: #6272a4; }
    Tab.-active { color: #f8f8f2; text-style: bold; }
    Underline > .underline--bar { color: #ff79c6; background: #44475a; }

    #open-dialog {
        width: 70%; height: 80%; padding: 1 2;
        border: thick #bd93f9; background: #282a36;
    }

    #search-dialog {
        width: 85%; height: 85%; padding: 1 2;
        border: thick #8be9fd; background: #282a36;
    }
    #query { margin-bottom: 0; }
    #results { height: 1fr; background: #1e1f29; border: round #44475a; }
    #results:focus { border: round #8be9fd; }

    NameDialog, ConfirmDialog, DeleteDialog, OpenNoteDialog, SearchDialog { align: center middle; background: black 60%; }
    #dialog {
        width: 60; height: auto; padding: 1 2;
        border: thick #ff79c6; background: #282a36;
    }
    .dialog-title { color: #ff79c6; text-style: bold; width: 100%; content-align: center middle; }
    .dialog-sub { color: #6272a4; margin-bottom: 1; }
    .buttons { height: auto; align: center middle; margin-top: 1; }
    .buttons Button { margin: 0 1; }
    """

    def __init__(self, target: Path) -> None:
        super().__init__()
        self.target = target

    def on_mount(self) -> None:
        self.theme = "dracula"
        is_note = self.target.is_file() or self.target.suffix.lower() == ".md"
        root = self.target.parent if is_note else self.target
        self.workspace = EditorScreen(root)
        self.install_screen(self.workspace, "workspace")  # persiste las pestañas
        self.push_screen(PickerScreen(root))
        if is_note:
            self.open_note(self.target)

    def open_note(self, path: Path) -> None:
        if self.screen is not self.workspace:
            self.push_screen("workspace")
        self.call_after_refresh(self.workspace.open_note, path)

    def action_search(self) -> None:
        def picked(result: tuple[Path, int] | None) -> None:
            if result is None:
                return
            path, line = result
            self.open_note(path)
            self.call_after_refresh(
                lambda: self.call_after_refresh(self._goto, path, line)
            )

        self.push_screen(SearchDialog(self.workspace.root), picked)

    def _goto(self, path: Path, line: int) -> None:
        for ed in self.workspace.editors():
            if ed.path == path.resolve():
                ed.goto_line(line)
                ed.focus_editor()

    def action_show_tabs(self) -> None:
        if self.workspace.is_mounted and self.workspace.editors():
            self.push_screen("workspace")
        else:
            self.notify("No hay pestañas abiertas", severity="warning")

    def action_request_quit(self) -> None:
        dirty = self.workspace.is_mounted and any(e.dirty for e in self.workspace.editors())
        if not dirty:
            self.exit()
            return

        def decide(choice: str) -> None:
            if choice == "save":
                for e in self.workspace.editors():
                    if e.dirty:
                        e.save()
                self.exit()
            elif choice == "discard":
                self.exit()

        self.push_screen(ConfirmDialog(), decide)


def main() -> None:
    if len(sys.argv) > 1:
        target = Path(sys.argv[1]).expanduser().resolve()
    else:
        target = DEFAULT_DIR
        target.mkdir(parents=True, exist_ok=True)
    MdNotes(target).run()


if __name__ == "__main__":
    main()
