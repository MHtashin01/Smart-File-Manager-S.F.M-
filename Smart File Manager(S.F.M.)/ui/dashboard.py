import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

from config import C
from core.db import get_db
from utils.file_rules import (
    apply_rules, sort_by_date, sort_by_size,
    sort_nested, find_duplicates, delete_duplicates,
)

def _darken(hex_c: str, amount: int = 28) -> str:
    h = hex_c.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(
        max(0, r - amount), max(0, g - amount), max(0, b - amount)
    )

def btn(parent, text: str, cmd, color: str | None = None, **kw) -> tk.Button:
    c = color or C["accent"]
    b = tk.Button(parent, text=text, command=cmd,
                  bg=c, fg="white", activebackground=_darken(c),
                  relief=tk.FLAT, bd=0, padx=10, pady=6,
                  font=("Segoe UI", 9, "bold"), cursor="hand2", **kw)
    b.bind("<Enter>", lambda _e: b.config(bg=_darken(c)))
    b.bind("<Leave>", lambda _e: b.config(bg=c))
    return b

def lbl(parent, text: str, size: int = 9, fg: str | None = None,
        bold: bool = False, **kw) -> tk.Label:
    font = ("Segoe UI", size, "bold") if bold else ("Segoe UI", size)
    return tk.Label(parent, text=text,
                    bg=kw.pop("bg", C["bg"]),
                    fg=fg or C["sub"],
                    font=font, **kw)

def entry(parent, var=None, width: int = 46, **kw) -> tk.Entry:
    return tk.Entry(parent, textvariable=var, width=width,
                    bg=C["panel"], fg=C["text"], insertbackground=C["text"],
                    relief=tk.FLAT, bd=5, font=("Segoe UI", 9), **kw)

def sep(parent) -> None:
    tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X, padx=12, pady=4)

def _sz(b: int) -> str:
    for unit, threshold in [("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)]:
        if b >= threshold:
            return f"{b / threshold:.1f} {unit}"
    return f"{b} B"

# ─────────────────────────────────────────────────────────────────────────────
#  Shared sort-variant widget
# ─────────────────────────────────────────────────────────────────────────────

_SORT_VARIANTS: list[tuple[str, str]] = [
    ("name_asc",      "Name  A → Z"),
    ("name_desc",     "Name  Z → A"),
    ("extension",     "Extension (then name)"),
    ("date_modified", "Date Modified  (oldest first)"),
    ("date_created",  "Date Created   (oldest first)"),
    ("size_asc",      "File Size  (smallest first)"),
    ("size_desc",     "File Size  (largest first)"),
]
_SORT_LABELS   = [label for _, label in _SORT_VARIANTS]
_SORT_KEY_MAP  = {label: key for key, label in _SORT_VARIANTS}

def _make_sort_row(parent: tk.Frame) -> tk.StringVar:
    """Add a labelled sort-variant drop-down; return the StringVar."""
    row = tk.Frame(parent, bg=C["bg"])
    row.pack(fill=tk.X, padx=12, pady=(2, 4))
    lbl(row, "Sort files by:", bg=C["bg"], fg=C["sub"]).pack(side=tk.LEFT, padx=(0, 6))
    var = tk.StringVar(value=_SORT_LABELS[0])
    om = tk.OptionMenu(row, var, *_SORT_LABELS)
    om.config(bg=C["panel"], fg=C["text"], activebackground=C["panel"],
              relief=tk.FLAT, font=("Segoe UI", 9), width=28)
    om["menu"].config(bg=C["panel"], fg=C["text"])
    om.pack(side=tk.LEFT)
    return var

# ─────────────────────────────────────────────────────────────────────────────
#  GenericDashboard
# ─────────────────────────────────────────────────────────────────────────────

class GenericDashboard:

    def __init__(self, root: tk.Tk, user: dict,
                 logout_callback, title_text: str) -> None:
        self.root = root
        self.user = user
        self._logout = logout_callback
        self._title  = title_text
        self._dup_groups: dict = {}
        self._draw()

    def _draw(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=C["bg"])
        if self.root.winfo_width() < 900:
            self.root.geometry("1150x820")
        self.root.minsize(960, 680)
        self.root.resizable(True, True)
        self.root.update_idletasks()
        self._build_header()
        self._build_notebook()

    def _build_header(self) -> None:
        h = tk.Frame(self.root, bg=C["accent"], pady=9)
        h.pack(fill=tk.X)
        lbl(h, f"  {self._title}", 13, fg="white", bold=True,
            bg=C["accent"]).pack(side=tk.LEFT, padx=16)
        lbl(h, f"👤 {self.user['username']}  ·  {self.user['role']}", 9,
            fg="#ddd6fe", bg=C["accent"]).pack(side=tk.LEFT, padx=4)
        btn(h, "⏻  Logout", self._logout, color=C["red"]).pack(side=tk.RIGHT, padx=14)

    def _build_notebook(self) -> None:
        s = ttk.Style()
        s.theme_use("default")
        s.configure("D.TNotebook", background=C["bg"], borderwidth=0)
        s.configure("D.TNotebook.Tab", background=C["panel"], foreground=C["sub"],
                    padding=[13, 6], font=("Segoe UI", 9, "bold"))
        s.map("D.TNotebook.Tab",
              background=[("selected", C["accent"])],
              foreground=[("selected", "white")])

        nb = ttk.Notebook(self.root, style="D.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))

        # ── Sorting tabs
        for label, builder in [
            ("📁  Rule Sort",   self._tab_rule),
            ("📅  Date Sort",   self._tab_date),
            ("📦  Size Sort",   self._tab_size),
            ("🗂  Nested Sort", self._tab_nested),
        ]:
            frame = tk.Frame(nb, bg=C["bg"])
            frame.pack_propagate(False)
            nb.add(frame, text=label)
            builder(frame)

        # ── Separator-style visual split: Duplicates & Rules Manager
        for label, builder in [
            ("🔍  Duplicates",  self._tab_dupes),
            ("⚙️  Rules Mgr",  self._tab_rules_mgr),
        ]:
            frame = tk.Frame(nb, bg=C["bg"])
            frame.pack_propagate(False)
            # Add a thin colour band at top of each "special" tab frame
            tk.Frame(frame, bg=C["accent2"], height=3).pack(fill=tk.X)
            nb.add(frame, text=label)
            builder(frame)

    # ── helper: file selection panel ──────────────────────────────────────────

    def _make_file_panel(self, parent: tk.Frame) -> dict:
        state: dict = {"files": [], "selected": []}

        outer = tk.LabelFrame(
            parent,
            text=" 📋 Select Files  (leave empty = ALL files) ",
            bg=C["bg"], fg=C["accent2"],
            font=("Segoe UI", 9, "bold"),
            bd=1, relief=tk.GROOVE, padx=8, pady=6,
        )
        outer.pack(fill=tk.BOTH, expand=True, pady=5, padx=2)

        ctrl = tk.Frame(outer, bg=C["bg"])
        ctrl.pack(fill=tk.X, pady=(0, 3))
        info_lbl = lbl(ctrl, "No folder loaded", fg=C["sub"], bg=C["bg"])
        info_lbl.pack(side=tk.RIGHT)

        vsb = tk.Scrollbar(outer)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(
            outer, selectmode=tk.MULTIPLE, yscrollcommand=vsb.set,
            bg=C["panel2"], fg=C["text"],
            selectbackground=C["sel"], selectforeground="white",
            font=("Segoe UI", 9), relief=tk.FLAT, bd=0,
            activestyle="none", height=7,
        )
        lb.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=lb.yview)

        def _upd() -> None:
            n, t = len(state["selected"]), len(state["files"])
            if n == 0:
                info_lbl.config(text=f"All {t} files will be processed" if t else "No files")
            else:
                info_lbl.config(text=f"{n} / {t} selected")

        def on_sel(_=None) -> None:
            state["selected"] = [
                state["files"][i]
                for i in lb.curselection()
                if i < len(state["files"])
            ]
            _upd()

        def sel_all() -> None:
            lb.select_set(0, tk.END)
            state["selected"] = list(state["files"])
            _upd()

        def sel_clr() -> None:
            lb.selection_clear(0, tk.END)
            state["selected"] = []
            _upd()

        btn(ctrl, "Select All", sel_all, color=C["accent"]).pack(side=tk.LEFT, padx=2)
        btn(ctrl, "Clear",      sel_clr, color=C["orange"]).pack(side=tk.LEFT, padx=2)
        lb.bind("<<ListboxSelect>>", on_sel)

        def load(folder: str) -> None:
            lb.delete(0, tk.END)
            state["files"] = []
            if folder and os.path.isdir(folder):
                for f in sorted(os.listdir(folder)):
                    fp = os.path.join(folder, f)
                    if os.path.isfile(fp):
                        state["files"].append(f)
                        lb.insert(tk.END, f"  {f}  ({_sz(os.path.getsize(fp))})")
            state["selected"] = []
            _upd()

        state["load"]    = load
        state["targets"] = lambda: state["selected"] if state["selected"] else None
        return state

    def _pick_row(self, parent: tk.Frame, path_var: tk.StringVar,
                  on_pick=None) -> None:
        row = tk.Frame(parent, bg=C["panel"], pady=9, padx=12)
        row.pack(fill=tk.X, pady=(0, 3))
        lbl(row, "Folder:", bg=C["panel"]).pack(side=tk.LEFT)
        entry(parent=row, var=path_var, width=50).pack(side=tk.LEFT, padx=8)

        def pick() -> None:
            d = filedialog.askdirectory()
            if d:
                path_var.set("")
                path_var.set(d)
                if on_pick:
                    on_pick(d)

        btn(row, "Browse…", pick, color=C["accent2"]).pack(side=tk.LEFT)

    # ── Tab: Rule Sort ────────────────────────────────────────────────────────

    def _tab_rule(self, p: tk.Frame) -> None:
        lbl(p, "Move files into folders based on extension rules you define in Rules Mgr.",
            bg=C["bg"]).pack(anchor="w", padx=12, pady=(10, 2))

        path_var = tk.StringVar()
        fs = self._make_file_panel(p)
        self._pick_row(p, path_var, on_pick=fs["load"])

        # ── Sort-variant section ──────────────────────────────
        sv_frame = tk.LabelFrame(
            p, text=" 🔀 Sort Variant – processing order ",
            bg=C["bg"], fg=C["accent2"],
            font=("Segoe UI", 9, "bold"),
            bd=1, relief=tk.GROOVE, padx=10, pady=6,
        )
        sv_frame.pack(fill=tk.X, padx=12, pady=(4, 2))

        sort_var = tk.StringVar(value=_SORT_LABELS[0])
        sv_desc  = lbl(sv_frame, "", 8, fg=C["sub"], bg=C["bg"])

        _SV_DESCRIPTIONS = {
            "name_asc":      "Files are processed A → Z by filename.",
            "name_desc":     "Files are processed Z → A by filename.",
            "extension":     "Files are grouped by extension, then sorted by name within each group.",
            "date_modified": "Files are processed oldest-modified first.",
            "date_created":  "Files are processed oldest-created first.",
            "size_asc":      "Files are processed smallest-first.",
            "size_desc":     "Files are processed largest-first.",
        }

        def _refresh_sv_desc(*_) -> None:
            key = _SORT_KEY_MAP.get(sort_var.get(), "name_asc")
            sv_desc.config(text=_SV_DESCRIPTIONS.get(key, ""))

        cols_frame = tk.Frame(sv_frame, bg=C["bg"])
        cols_frame.pack(fill=tk.X, pady=(0, 4))
        for i, (key, label) in enumerate(_SORT_VARIANTS):
            tk.Radiobutton(
                cols_frame, text=label, variable=sort_var, value=label,
                command=_refresh_sv_desc,
                bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                activebackground=C["bg"], font=("Segoe UI", 9),
            ).grid(row=i // 4, column=i % 4, sticky="w", padx=8, pady=2)

        sv_desc.pack(anchor="w", padx=4)
        _refresh_sv_desc()

        def run() -> None:
            path = path_var.get()
            if not path:
                messagebox.showwarning("Missing", "Select a folder first.")
                return
            with get_db() as conn:
                rules = conn.execute(
                    "SELECT extension, folder_name FROM rules WHERE user_id=?",
                    (self.user["id"],),
                ).fetchall()
            if not rules:
                messagebox.showwarning("No Rules", "Add rules in the Rules Manager tab first.")
                return
            sv_key = _SORT_KEY_MAP.get(sort_var.get(), "name_asc")
            count, msg = apply_rules(path, rules, fs["targets"](), sort_variant=sv_key)
            self._log(f"Rule-sorted {count} files [{sv_key}]", path)
            messagebox.showinfo("Done", f"Moved {count} files.\nStatus: {msg}")
            path_var.set("")
            fs["load"]("")

        btn(p, "▶  Run Rule Sort", run, color=C["green"]).pack(pady=8)

    # ── Tab: Date Sort ────────────────────────────────────────────────────────

    def _tab_date(self, p: tk.Frame) -> None:
        lbl(p, "Organise files into  Year ▸ Month  sub-folders by file date.",
            bg=C["bg"]).pack(anchor="w", padx=12, pady=(10, 2))
        path_var = tk.StringVar()
        fs = self._make_file_panel(p)
        self._pick_row(p, path_var, on_pick=fs["load"])

        opt_f = tk.Frame(p, bg=C["bg"])
        opt_f.pack(fill=tk.X, padx=12, pady=4)
        lbl(opt_f, "Date source:", bg=C["bg"]).pack(side=tk.LEFT)
        date_mode = tk.StringVar(value="modified")
        for v, t in [("modified", "Last Modified"), ("created", "Date Created")]:
            tk.Radiobutton(opt_f, text=t, variable=date_mode, value=v,
                           bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                           activebackground=C["bg"],
                           font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=6)

        sep(p)
        nest_f = tk.Frame(p, bg=C["bg"])
        nest_f.pack(fill=tk.X, padx=12, pady=2)
        nest_size = tk.BooleanVar(value=False)
        tk.Checkbutton(nest_f, text="📦  Also nest by Size Tier  (Year ▸ Month ▸ Size)",
                       variable=nest_size,
                       bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                       activebackground=C["bg"],
                       font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        preview = lbl(p, "", 8, fg=C["accent2"], bg=C["bg"])
        preview.pack(anchor="w", padx=16)

        def update_preview(*_) -> None:
            extra = " ▸ 📁 Size Tier" if nest_size.get() else ""
            preview.config(text=f"Structure: 📁 Year ▸ 📁 Month{extra} ▸ 📄 file")

        nest_size.trace_add("write", update_preview)
        update_preview()

        def run() -> None:
            path = path_var.get()
            if not path:
                messagebox.showwarning("Missing", "Select a folder first.")
                return
            count, msg = sort_by_date(path, date_mode.get(), fs["targets"](), nest_size.get())
            self._log(f"Date-sorted {count} files", path)
            messagebox.showinfo("Done", f"Sorted {count} files.\nStatus: {msg}")
            path_var.set("")
            fs["load"]("")

        btn(p, "▶  Run Date Sort", run, color=C["green"]).pack(pady=8)

    # ── Tab: Size Sort ────────────────────────────────────────────────────────

    def _tab_size(self, p: tk.Frame) -> None:
        lbl(p, "Group files into size-tier sub-folders.",
            bg=C["bg"]).pack(anchor="w", padx=12, pady=(10, 2))

        leg = tk.Frame(p, bg=C["panel"], padx=10, pady=6)
        leg.pack(fill=tk.X, padx=12, pady=3)
        lbl(leg, "Tiers:", bg=C["panel"]).pack(side=tk.LEFT, padx=(0, 6))
        for name, color in [("Micro", "#64748b"), ("Tiny", "#0ea5e9"),
                             ("Small", C["green"]), ("Medium", C["orange"]),
                             ("Large", C["red"])]:
            lbl(leg, f"● {name}", bg=C["panel"], fg=color, size=8).pack(side=tk.LEFT, padx=5)

        path_var = tk.StringVar()
        fs = self._make_file_panel(p)
        self._pick_row(p, path_var, on_pick=fs["load"])

        sep(p)
        nest_f = tk.Frame(p, bg=C["bg"])
        nest_f.pack(fill=tk.X, padx=12, pady=2)
        nest_date = tk.BooleanVar(value=False)
        tk.Checkbutton(nest_f, text="📅  Also nest by Date  (Size ▸ Year ▸ Month)",
                       variable=nest_date,
                       bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                       activebackground=C["bg"],
                       font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        date_mode = tk.StringVar(value="modified")
        for v, t in [("modified", "Modified"), ("created", "Created")]:
            tk.Radiobutton(nest_f, text=t, variable=date_mode, value=v,
                           bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                           activebackground=C["bg"],
                           font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)

        preview = lbl(p, "", 8, fg=C["accent2"], bg=C["bg"])
        preview.pack(anchor="w", padx=16)

        def update_preview(*_) -> None:
            extra = " ▸ 📁 Year ▸ 📁 Month" if nest_date.get() else ""
            preview.config(text=f"Structure: 📁 Size Tier{extra} ▸ 📄 file")

        nest_date.trace_add("write", update_preview)
        update_preview()

        def run() -> None:
            path = path_var.get()
            if not path:
                messagebox.showwarning("Missing", "Select a folder first.")
                return
            count, msg = sort_by_size(path, fs["targets"](), nest_date.get(), date_mode.get())
            self._log(f"Size-sorted {count} files", path)
            messagebox.showinfo("Done", f"Sorted {count} files into size tiers.\nStatus: {msg}")
            path_var.set("")
            fs["load"]("")

        btn(p, "▶  Run Size Sort", run, color=C["green"]).pack(pady=8)

    # ── Tab: Nested Sort ──────────────────────────────────────────────────────

    def _tab_nested(self, p: tk.Frame) -> None:
        lbl(p, "Build a fully custom multi-level folder hierarchy.",
            bg=C["bg"]).pack(anchor="w", padx=12, pady=(10, 2))

        path_var = tk.StringVar()
        fs = self._make_file_panel(p)
        self._pick_row(p, path_var, on_pick=fs["load"])

        OPTS: list[tuple[str, str]] = [
            ("extension",     "File Type (Extension)"),
            ("date_modified", "Date Modified  (Year ▸ Month)"),
            ("date_created",  "Date Created   (Year ▸ Month)"),
            ("size",          "File Size Tier"),
        ]
        LABEL_TO_KEY = {label: key for key, label in OPTS}
        LABELS       = [label for _, label in OPTS]
        KEY_TO_LABEL = dict(OPTS)

        level_keys: list[str] = []

        bldr = tk.LabelFrame(p, text=" 🗂  Level Builder ",
                             bg=C["bg"], fg=C["accent2"],
                             font=("Segoe UI", 9, "bold"),
                             bd=1, relief=tk.GROOVE, padx=10, pady=8)
        bldr.pack(fill=tk.X, padx=12, pady=5)

        level_lb = tk.Listbox(bldr, height=4,
                              bg=C["panel2"], fg=C["text"],
                              selectbackground=C["sel"],
                              font=("Segoe UI", 9),
                              relief=tk.FLAT, bd=0, activestyle="none")
        level_lb.pack(fill=tk.X, pady=3)

        preview = lbl(p, "", 8, fg=C["accent2"], bg=C["bg"])

        def refresh() -> None:
            level_lb.delete(0, tk.END)
            for i, k in enumerate(level_keys):
                level_lb.insert(tk.END, f"  Level {i + 1}:  {KEY_TO_LABEL.get(k, k)}")
            if level_keys:
                parts = ["📁 root"] + [f"📁 {KEY_TO_LABEL.get(k, k)}" for k in level_keys] + ["📄 file"]
                preview.config(text="  →  ".join(parts))
            else:
                preview.config(text="Add a level to begin.")

        add_var = tk.StringVar(value=LABELS[0])
        om = tk.OptionMenu(bldr, add_var, *LABELS)
        om.config(bg=C["panel"], fg=C["text"], activebackground=C["panel"],
                  relief=tk.FLAT, font=("Segoe UI", 9), width=32)
        om["menu"].config(bg=C["panel"], fg=C["text"])
        om.pack(side=tk.LEFT, padx=(0, 6), pady=4)

        def add() -> None:
            level_keys.append(LABEL_TO_KEY[add_var.get()])
            refresh()

        def remove() -> None:
            sel = level_lb.curselection()
            if sel:
                level_keys.pop(sel[0])
                refresh()

        def move(delta: int) -> None:
            sel = level_lb.curselection()
            if not sel:
                return
            i, j = sel[0], sel[0] + delta
            if 0 <= j < len(level_keys):
                level_keys[i], level_keys[j] = level_keys[j], level_keys[i]
                refresh()
                level_lb.select_set(j)

        btn_row = tk.Frame(bldr, bg=C["bg"])
        btn_row.pack(side=tk.LEFT, padx=2)
        for text, color, cmd in [
            ("+ Add",  C["accent"], add),
            ("Remove", C["red"],    remove),
            ("▲",      C["orange"], lambda: move(-1)),
            ("▼",      C["orange"], lambda: move(1)),
        ]:
            btn(btn_row, text, cmd, color=color).pack(side=tk.LEFT, padx=2)

        preview.pack(anchor="w", padx=12, pady=2)
        refresh()

        def run() -> None:
            path = path_var.get()
            if not path:
                messagebox.showwarning("Missing", "Select a folder first.")
                return
            if not level_keys:
                messagebox.showwarning("Missing", "Add at least one level.")
                return
            count, msg = sort_nested(path, level_keys, fs["targets"]())
            self._log(f"Nested-sorted {count} files ({'+'.join(level_keys)})", path)
            messagebox.showinfo("Done", f"Sorted {count} files.\nStatus: {msg}")
            path_var.set("")
            fs["load"]("")

        btn(p, "▶  Run Nested Sort", run, color=C["green"]).pack(pady=8)

    # ── Tab: Duplicates ───────────────────────────────────────────────────────

    def _tab_dupes(self, p: tk.Frame) -> None:
        # Title banner
        banner = tk.Frame(p, bg=C["accent2"], pady=6, padx=12)
        banner.pack(fill=tk.X)
        lbl(banner, "🔍  Duplicate File Scanner", 11, fg="white", bold=True,
            bg=C["accent2"]).pack(side=tk.LEFT)
        lbl(banner, "Find and remove identical or similarly-named files",
            9, fg="#e0e7ff", bg=C["accent2"]).pack(side=tk.LEFT, padx=12)

        # ── Folder picker
        dup_path = tk.StringVar()
        row = tk.Frame(p, bg=C["panel"], pady=9, padx=12)
        row.pack(fill=tk.X, pady=(6, 3))
        lbl(row, "Folder:", bg=C["panel"]).pack(side=tk.LEFT)
        entry(parent=row, var=dup_path, width=46).pack(side=tk.LEFT, padx=8)

        def pick() -> None:
            d = filedialog.askdirectory()
            if d:
                dup_path.set("")
                dup_path.set(d)

        btn(row, "Browse…", pick, color=C["accent2"]).pack(side=tk.LEFT)

        # ── Options row (recursive + keep policy)
        opt = tk.Frame(p, bg=C["bg"])
        opt.pack(fill=tk.X, padx=12, pady=4)
        recursive = tk.BooleanVar(value=False)
        tk.Checkbutton(opt, text="🔁  Scan sub-folders too",
                       variable=recursive,
                       bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                       activebackground=C["bg"],
                       font=("Segoe UI", 9)).pack(side=tk.LEFT)
        keep_policy = tk.StringVar(value="first")
        lbl(opt, "  Keep:", bg=C["bg"], fg=C["text"]).pack(side=tk.LEFT, padx=(20, 4))
        for v, t in [("first", "First found"), ("last", "Last found")]:
            tk.Radiobutton(opt, text=t, variable=keep_policy, value=v,
                           bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                           activebackground=C["bg"],
                           font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)

        sep(p)

        # ── Scan Mode section  (NEW)
        sm_frame = tk.LabelFrame(
            p, text=" 🔎 Scan Mode – duplicate detection method ",
            bg=C["bg"], fg=C["accent2"],
            font=("Segoe UI", 9, "bold"),
            bd=1, relief=tk.GROOVE, padx=12, pady=8,
        )
        sm_frame.pack(fill=tk.X, padx=12, pady=(2, 4))

        scan_mode = tk.StringVar(value="hash")
        _SM_OPTIONS = [
            ("hash",      "🔐  Content Hash  (MD5)",
             "Compares the actual file bytes — catches true duplicates regardless of filename."),
            ("name",      "🏷️  Filename Only",
             "Matches files with the same name (case-insensitive). Fast, but may flag unrelated files."),
            ("name_size", "📐  Filename + Size",
             "Files must share the same name AND the same byte-size. A balanced middle ground."),
        ]

        sm_desc_var = tk.StringVar()
        sm_desc_lbl = lbl(sm_frame, "", 8, fg=C["sub"], bg=C["bg"])

        def _refresh_sm_desc(*_) -> None:
            for key, _, desc in _SM_OPTIONS:
                if key == scan_mode.get():
                    sm_desc_lbl.config(text=desc)
                    break

        rb_row = tk.Frame(sm_frame, bg=C["bg"])
        rb_row.pack(fill=tk.X, pady=(0, 4))
        for key, label, _ in _SM_OPTIONS:
            tk.Radiobutton(
                rb_row, text=label, variable=scan_mode, value=key,
                command=_refresh_sm_desc,
                bg=C["bg"], fg=C["text"], selectcolor=C["panel"],
                activebackground=C["bg"], font=("Segoe UI", 9),
            ).pack(side=tk.LEFT, padx=12)

        sm_desc_lbl.pack(anchor="w", padx=4)
        _refresh_sm_desc()

        sep(p)

        btn(p, "🔍  Scan for Duplicates",
            lambda: self._scan_dupes(dup_path, recursive, keep_policy, scan_mode),
            color=C["accent"]).pack(pady=6)

        self._dup_stat = lbl(p, "No scan run yet.", fg=C["sub"], bg=C["bg"])
        self._dup_stat.pack(anchor="w", padx=12)

        self._dup_sel_lbl = lbl(p, "", 8, fg=C["accent2"], bg=C["bg"])
        self._dup_sel_lbl.pack(anchor="w", padx=12)
        sep(p)

        # ── Results tree
        tree_f = tk.Frame(p, bg=C["bg"])
        tree_f.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        cols = ("Group", "File", "Size", "Path")
        ts = ttk.Style()
        ts.configure("Dup.Treeview",
                     background=C["panel2"], fieldbackground=C["panel2"],
                     foreground=C["text"], rowheight=22, font=("Segoe UI", 9))
        ts.configure("Dup.Treeview.Heading",
                     background=C["panel"], foreground=C["accent2"],
                     font=("Segoe UI", 9, "bold"))
        ts.map("Dup.Treeview", background=[("selected", C["sel"])])

        vsb = tk.Scrollbar(tree_f, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._dup_tree = ttk.Treeview(tree_f, columns=cols, show="headings",
                                      style="Dup.Treeview",
                                      yscrollcommand=vsb.set, height=10,
                                      selectmode="extended")
        vsb.config(command=self._dup_tree.yview)
        for col, w in [("Group", 60), ("File", 200), ("Size", 90), ("Path", 500)]:
            self._dup_tree.heading(col, text="Filename" if col == "File" else col)
            self._dup_tree.column(col, width=w, stretch=(col == "Path"))
        self._dup_tree.pack(fill=tk.BOTH, expand=True)
        self._dup_tree.tag_configure("keep", foreground=C["green"])
        self._dup_tree.tag_configure("del",  foreground="#f87171")

        def _on_tree_select(_event=None) -> None:
            n = len(self._dup_tree.selection())
            if n == 0:
                self._dup_sel_lbl.config(text="")
            else:
                self._dup_sel_lbl.config(
                    text=f"✔  {n} row{'s' if n != 1 else ''} selected  "
                         "(Ctrl+click to add/remove · Shift+click for range)"
                )
        self._dup_tree.bind("<<TreeviewSelect>>", _on_tree_select)

        lbl(p, "💡 Ctrl+click or Shift+click rows to select specific files, "
               "then use 'Delete Selected'.",
            8, fg=C["sub"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(0, 2))

        # ── Action buttons
        action_f = tk.Frame(p, bg=C["bg"])
        action_f.pack(pady=6)
        btn(action_f, "🗑 Delete All Duplicates (keeps one per group)",
            lambda: self._delete_dupes(dup_path, keep_policy),
            color=C["red"]).pack(side=tk.LEFT, padx=6)
        btn(action_f, "✂  Delete Selected Rows Only",
            lambda: self._delete_selected_dupes(dup_path),
            color=C["orange"]).pack(side=tk.LEFT, padx=6)
        btn(action_f, "⟳  Clear Results",
            self._clear_dupe_results,
            color=C["accent2"]).pack(side=tk.LEFT, padx=6)

    # ── Tab: Rules Manager  (now a distinct section) ──────────────────────────

    def _tab_rules_mgr(self, p: tk.Frame) -> None:

        # Title banner
        banner = tk.Frame(p, bg="#4f3fff", pady=6, padx=12)
        banner.pack(fill=tk.X)
        lbl(banner, "⚙️  Rules Manager", 11, fg="white", bold=True,
            bg="#4f3fff").pack(side=tk.LEFT)
        lbl(banner, "Define extension → folder rules used by Rule Sort",
            9, fg="#c7d2fe", bg="#4f3fff").pack(side=tk.LEFT, padx=12)

        lbl(p, "Click any row to load it into the fields for review or deletion.",
            bg=C["bg"]).pack(anchor="w", padx=12, pady=(8, 4))

        # ── Input row
        inp = tk.Frame(p, bg=C["panel"], pady=9, padx=12)
        inp.pack(fill=tk.X, padx=12)

        lbl(inp, "Extension:", bg=C["panel"], fg=C["text"]).pack(side=tk.LEFT)
        self._e_ext = entry(inp, width=9)
        self._e_ext.pack(side=tk.LEFT, padx=6)
        lbl(inp, "→  Folder:", bg=C["panel"], fg=C["text"]).pack(side=tk.LEFT)
        self._e_fol = entry(inp, width=22)
        self._e_fol.pack(side=tk.LEFT, padx=6)
        btn(inp, "+ Add Rule",      self._add_rule,    color=C["accent"]).pack(side=tk.LEFT, padx=8)
        btn(inp, "✕  Clear Fields", self._clear_rule_fields, color=C["orange"]).pack(side=tk.LEFT, padx=2)
        btn(inp, "🗑  Delete Selected", self._delete_rule, color=C["red"]).pack(side=tk.RIGHT, padx=4)

        # ── Filter + count bar
        bar = tk.Frame(p, bg=C["bg"])
        bar.pack(fill=tk.X, padx=12, pady=(6, 2))

        lbl(bar, "🔎  Filter:", bg=C["bg"], fg=C["sub"]).pack(side=tk.LEFT)
        self._rule_filter = tk.StringVar()
        filter_entry = tk.Entry(bar, textvariable=self._rule_filter, width=20,
                                bg=C["panel"], fg=C["text"], insertbackground=C["text"],
                                relief=tk.FLAT, bd=4, font=("Segoe UI", 9))
        filter_entry.pack(side=tk.LEFT, padx=6)

        # Bulk-import hint
        lbl(bar, "💡 Tip: set a rule per extension, e.g.  .pdf → PDFs",
            8, fg=C["sub"], bg=C["bg"]).pack(side=tk.LEFT, padx=12)

        self._rule_count_lbl = lbl(bar, "", fg=C["accent2"], bg=C["bg"])
        self._rule_count_lbl.pack(side=tk.RIGHT, padx=4)

        # ── Rules tree
        tree_f = tk.Frame(p, bg=C["bg"])
        tree_f.pack(fill=tk.BOTH, expand=True, padx=12, pady=(2, 8))

        rs = ttk.Style()
        rs.configure("Rules.Treeview",
                      background=C["panel2"], fieldbackground=C["panel2"],
                      foreground=C["text"], rowheight=26,
                      font=("Segoe UI", 10))
        rs.configure("Rules.Treeview.Heading",
                      background=C["panel"], foreground=C["accent2"],
                      font=("Segoe UI", 9, "bold"), relief="flat")
        rs.map("Rules.Treeview",
               background=[("selected", C["sel"])],
               foreground=[("selected", "white")])

        vsb = tk.Scrollbar(tree_f, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._rule_tree = ttk.Treeview(
            tree_f,
            columns=("#", "Extension", "Folder"),
            show="headings",
            style="Rules.Treeview",
            yscrollcommand=vsb.set,
            selectmode="browse",
        )
        vsb.config(command=self._rule_tree.yview)

        self._rule_tree.heading("#",         text="#")
        self._rule_tree.heading("Extension", text="Extension")
        self._rule_tree.heading("Folder",    text="Destination Folder")
        self._rule_tree.column("#",         width=40,  stretch=False, anchor="center")
        self._rule_tree.column("Extension", width=130, stretch=False, anchor="center")
        self._rule_tree.column("Folder",    width=500, stretch=True,  anchor="w")

        self._rule_tree.tag_configure("odd",  background=C["panel2"])
        self._rule_tree.tag_configure("even", background="#252538")

        self._rule_tree.pack(fill=tk.BOTH, expand=True)

        def _on_select(_event=None) -> None:
            sel = self._rule_tree.selection()
            if not sel:
                return
            _, ext, folder = self._rule_tree.item(sel[0])["values"]
            self._e_ext.delete(0, tk.END)
            self._e_ext.insert(0, ext)
            self._e_fol.delete(0, tk.END)
            self._e_fol.insert(0, folder)

        self._rule_tree.bind("<<TreeviewSelect>>", _on_select)
        self._rule_filter.trace_add("write", lambda *_: self._refresh_rules())
        self._refresh_rules()

    # ─────────────────────────────────────────────
    #  Rules Manager helpers
    # ─────────────────────────────────────────────

    def _clear_rule_fields(self) -> None:
        self._e_ext.delete(0, tk.END)
        self._e_fol.delete(0, tk.END)
        self._rule_tree.selection_remove(*self._rule_tree.selection())

    def _add_rule(self) -> None:
        ext = self._e_ext.get().strip()
        fol = self._e_fol.get().strip()
        if not ext or not fol:
            messagebox.showwarning("Missing", "Both Extension and Folder are required.")
            return
        if not ext.startswith("."):
            ext = "." + ext
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM rules WHERE user_id=? AND extension=?",
                (self.user["id"], ext),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE rules SET folder_name=? WHERE id=?",
                    (fol, existing[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO rules (user_id, extension, folder_name) VALUES (?, ?, ?)",
                    (self.user["id"], ext, fol),
                )
        self._refresh_rules()
        self._clear_rule_fields()
        self._e_ext.focus()

    def _delete_rule(self) -> None:
        sel = self._rule_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Click a rule row to select it first.")
            return
        _, ext, folder = self._rule_tree.item(sel[0])["values"]
        if not messagebox.askyesno("Confirm",
                                   f"Delete rule:  {ext}  →  {folder}?",
                                   parent=self.root):
            return
        with get_db() as conn:
            conn.execute(
                "DELETE FROM rules WHERE user_id=? AND extension=?",
                (self.user["id"], ext),
            )
        self._refresh_rules()
        self._clear_rule_fields()

    def _refresh_rules(self) -> None:
        if not hasattr(self, "_rule_tree"):
            return
        self._rule_tree.delete(*self._rule_tree.get_children())
        with get_db() as conn:
            rows = conn.execute(
                "SELECT extension, folder_name FROM rules WHERE user_id=? ORDER BY extension",
                (self.user["id"],),
            ).fetchall()

        q = self._rule_filter.get().strip().lower() if hasattr(self, "_rule_filter") else ""
        visible = [(ext, folder) for ext, folder in rows
                   if not q or q in ext.lower() or q in folder.lower()]

        for i, (ext, folder) in enumerate(visible, start=1):
            tag = "odd" if i % 2 else "even"
            self._rule_tree.insert("", "end", values=(i, ext, folder), tags=(tag,))

        if hasattr(self, "_rule_count_lbl"):
            total = len(rows)
            shown = len(visible)
            if q and shown != total:
                self._rule_count_lbl.config(
                    text=f"Showing {shown} of {total} rule{'s' if total != 1 else ''}",
                    fg=C["yellow"],
                )
            else:
                self._rule_count_lbl.config(
                    text=f"{total} rule{'s' if total != 1 else ''} defined",
                    fg=C["accent2"],
                )

    # ─────────────────────────────────────────────
    #  Duplicate helpers
    # ─────────────────────────────────────────────

    def _delete_selected_dupes(self, dup_path: tk.StringVar) -> None:
        sel_items = self._dup_tree.selection()
        if not sel_items:
            messagebox.showwarning("Nothing Selected",
                                   "Select one or more rows first.\n"
                                   "Use Ctrl+click or Shift+click to pick rows.")
            return

        to_delete: list[str] = []
        skipped_keep = 0
        for iid in sel_items:
            tags  = self._dup_tree.item(iid, "tags")
            fp    = self._dup_tree.item(iid, "values")[3]
            fname = self._dup_tree.item(iid, "values")[1]
            if "keep" in tags or fname.startswith("✔ KEEP"):
                skipped_keep += 1
                continue
            to_delete.append(fp)

        if not to_delete:
            msg = "All selected rows are marked KEEP — nothing to delete."
            if skipped_keep:
                msg += f"\n({skipped_keep} KEEP row{'s' if skipped_keep != 1 else ''} skipped)"
            messagebox.showinfo("Nothing to Delete", msg)
            return

        preview_names = [os.path.basename(p) for p in to_delete[:5]]
        preview = "\n  • " + "\n  • ".join(preview_names)
        if len(to_delete) > 5:
            preview += f"\n  … and {len(to_delete) - 5} more"

        warn = ""
        if skipped_keep:
            warn = (f"\n\nNote: {skipped_keep} KEEP row"
                    f"{'s were' if skipped_keep != 1 else ' was'} skipped automatically.")

        if not messagebox.askyesno(
            "Confirm Delete Selected",
            f"Permanently delete {len(to_delete)} selected file(s)?{preview}"
            f"{warn}\n\nThis cannot be undone.",
        ):
            return

        deleted, freed, errors = 0, 0, []
        for fp in to_delete:
            try:
                freed += os.path.getsize(fp)
                os.remove(fp)
                deleted += 1
            except Exception as exc:
                errors.append(f"{fp}: {exc}")

        self._log(
            f"Manually deleted {deleted} selected duplicate file(s), freed {_sz(freed)}",
            dup_path.get(),
        )

        for iid in sel_items:
            fp = self._dup_tree.item(iid, "values")[3]
            if fp in to_delete and iid in self._dup_tree.get_children(""):
                self._dup_tree.delete(iid)

        deleted_set = set(to_delete)
        for h in list(self._dup_groups.keys()):
            self._dup_groups[h] = [p for p in self._dup_groups[h] if p not in deleted_set]
            if len(self._dup_groups[h]) < 2:
                del self._dup_groups[h]

        self._dup_sel_lbl.config(text="")
        result_msg = f"Deleted {deleted} file(s), freed {_sz(freed)}."
        if errors:
            result_msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
        messagebox.showinfo("Done", result_msg)

    def _scan_dupes(self, dup_path: tk.StringVar,
                    recursive: tk.BooleanVar,
                    keep_policy: tk.StringVar,
                    scan_mode: tk.StringVar) -> None:
        path = dup_path.get()
        if not path:
            messagebox.showwarning("Missing", "Select a folder first.")
            return
        if not os.path.isdir(path):
            messagebox.showerror("Invalid Path",
                                 f"The folder does not exist or is not accessible:\n{path}")
            return
        mode_label = {"hash": "Content Hash", "name": "Filename",
                      "name_size": "Filename + Size"}.get(scan_mode.get(), scan_mode.get())
        self._dup_stat.config(text=f"⏳ Scanning  [{mode_label}]…", fg=C["yellow"])
        self.root.update_idletasks()
        try:
            groups = find_duplicates(path, recursive=recursive.get(),
                                     scan_mode=scan_mode.get())
        except Exception as exc:
            self._dup_stat.config(text=f"❌  Scan error: {exc}", fg=C["red"])
            return
        self._dup_groups = groups
        self._dup_tree.delete(*self._dup_tree.get_children())

        if not groups:
            self._dup_stat.config(text=f"✅  No duplicates found!  [{mode_label}]",
                                   fg=C["green"])
            return

        keep = keep_policy.get()
        total_files = sum(len(v) for v in groups.values())
        wasted = sum(
            os.path.getsize(p)
            for paths in groups.values()
            for i, p in enumerate(paths)
            if i != (0 if keep == "first" else len(paths) - 1)
        )

        for gi, (_, paths) in enumerate(groups.items()):
            keep_idx = 0 if keep == "first" else len(paths) - 1
            for fi, fp in enumerate(paths):
                is_kept = fi == keep_idx
                mark = "✔ KEEP" if is_kept else "✖ DELETE"
                self._dup_tree.insert("", "end",
                    values=(f"G{gi + 1}", f"{mark}  {os.path.basename(fp)}",
                            _sz(os.path.getsize(fp)), fp),
                    tags=("keep" if is_kept else "del",))

        self._dup_stat.config(
            text=(f"⚠  Found {len(groups)} duplicate group(s)  ·  "
                  f"{total_files} total files  ·  "
                  f"{_sz(wasted)} can be freed  ·  [{mode_label}]"),
            fg=C["orange"],
        )

    def _delete_dupes(self, dup_path: tk.StringVar,
                      keep_policy: tk.StringVar) -> None:
        if not self._dup_groups:
            messagebox.showinfo("Nothing to do", "Run a scan first.")
            return
        n = len(self._dup_groups)
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete duplicates from {n} group(s)?\n"
            "One file per group will be kept.\nThis cannot be undone.",
        ):
            return
        deleted, freed, errors = delete_duplicates(
            self._dup_groups, keep=keep_policy.get()
        )
        self._log(f"Deleted {deleted} duplicate files, freed {_sz(freed)}", dup_path.get())
        dup_path.set("")
        self._clear_dupe_results()
        msg = f"Deleted {deleted} file(s), freed {_sz(freed)}."
        if errors:
            msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
        messagebox.showinfo("Done", msg)

    def _clear_dupe_results(self) -> None:
        self._dup_tree.delete(*self._dup_tree.get_children())
        self._dup_groups = {}
        self._dup_stat.config(text="No scan run yet.", fg=C["sub"])
        self._dup_sel_lbl.config(text="")

    # ─────────────────────────────────────────────
    #  Activity log
    # ─────────────────────────────────────────────

    def _log(self, action: str, path: str) -> None:
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO logs (user_id, action, target_dir, timestamp) VALUES (?, ?, ?, ?)",
                    (self.user["id"], action, path,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
        except Exception as exc:
            import sys
            print(f"[WARNING] Activity log write failed: {exc}", file=sys.stderr)

class UserDashboard(GenericDashboard):
    def __init__(self, root, user, logout_callback):
        super().__init__(root, user, logout_callback, "User Workspace")
