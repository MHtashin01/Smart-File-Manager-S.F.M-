import tkinter as tk
from tkinter import ttk, messagebox

from config import C
from core.db import get_db

class AdminDashboard:
    def __init__(self, root: tk.Tk, user: dict, logout_callback) -> None:
        self.root = root
        self.user = user
        self._logout = logout_callback
        self._draw()

    def _draw(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=C["bg"])
        if self.root.winfo_width() < 800:
            self.root.geometry("860x600")
        self.root.update_idletasks()

        hdr = tk.Frame(self.root, bg=C["accent"], pady=9)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=" Admin Dashboard", bg=C["accent"], fg="white",
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT, padx=16)
        tk.Label(hdr, text=f"👤 {self.user['username']}  ·  {self.user['role']}",
                 bg=C["accent"], fg="#ddd6fe",
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(hdr, text="⏻  Logout", command=self._logout,
                  bg=C["red"], fg="white", activebackground=C["red"],
                  relief=tk.FLAT, bd=0, padx=10, pady=6,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side=tk.RIGHT, padx=14)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("A.TNotebook", background=C["bg"], borderwidth=0)
        style.configure("A.TNotebook.Tab", background=C["panel"], foreground=C["sub"],
                        padding=[13, 6], font=("Segoe UI", 9, "bold"))
        style.map("A.TNotebook.Tab",
                  background=[("selected", C["accent"])],
                  foreground=[("selected", "white")])

        nb = ttk.Notebook(self.root, style="A.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))

        user_tab = tk.Frame(nb, bg=C["bg"])
        log_tab  = tk.Frame(nb, bg=C["bg"])
        nb.add(user_tab, text=" 👥  User Management ")
        nb.add(log_tab,  text=" 📋  Activity Logs ")

        self._build_users_tab(user_tab)
        self._build_logs_tab(log_tab)

    @staticmethod
    def _styled_tree(parent: tk.Frame, columns: tuple) -> ttk.Treeview:
        s = ttk.Style()
        s.configure("Adm.Treeview",
                    background=C["panel2"], fieldbackground=C["panel2"],
                    foreground=C["text"], rowheight=24,
                    font=("Segoe UI", 9))
        s.configure("Adm.Treeview.Heading",
                    background=C["panel"], foreground=C["accent2"],
                    font=("Segoe UI", 9, "bold"))
        s.map("Adm.Treeview", background=[("selected", C["sel"])])

        vsb = tk.Scrollbar(parent, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree = ttk.Treeview(parent, columns=columns, show="headings",
                            style="Adm.Treeview", yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        tree.pack(fill=tk.BOTH, expand=True)
        for col in columns:
            tree.heading(col, text=col)
        return tree

    def _build_users_tab(self, parent: tk.Frame) -> None:
        self._user_tree = self._styled_tree(parent, ("ID", "Username", "Role"))
        self._user_tree.column("ID",       width=50,  stretch=False)
        self._user_tree.column("Username", width=200, stretch=False)
        self._user_tree.column("Role",     width=250)

        btn_bar = tk.Frame(parent, bg=C["bg"], pady=8)
        btn_bar.pack(fill=tk.X)

        def _btn(text: str, cmd, color: str) -> None:
            tk.Button(btn_bar, text=text, command=cmd,
                      bg=color, fg="white", activebackground=color,
                      relief=tk.FLAT, bd=0, padx=10, pady=6,
                      font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side=tk.LEFT, padx=8)

        _btn("🗑  Delete Selected User", self._delete_user, C["red"])
        _btn("⟳  Refresh",              self._refresh_users, C["accent2"])
        self._refresh_users()

    def _refresh_users(self) -> None:
        for row in self._user_tree.get_children():
            self._user_tree.delete(row)
        with get_db() as conn:
            rows = conn.execute("SELECT id, username, role FROM users ORDER BY id").fetchall()
        for row in rows:
            self._user_tree.insert("", tk.END, values=row)

    def _delete_user(self) -> None:
        sel = self._user_tree.selection()
        if not sel:
            messagebox.showwarning("Nothing Selected", "Select a user first.", parent=self.root)
            return
        uid, uname, _ = self._user_tree.item(sel[0])["values"]
        if uname == "admin":
            messagebox.showerror("Forbidden", "The admin account cannot be deleted.",
                                 parent=self.root)
            return
        if messagebox.askyesno("Confirm", f"Permanently delete user '{uname}'?",
                               parent=self.root):
            with get_db() as conn:
                conn.execute("DELETE FROM users WHERE id=?", (uid,))
            self._refresh_users()

    def _build_logs_tab(self, parent: tk.Frame) -> None:
        cols = ("Username", "Action", "Path", "Timestamp")
        self._log_tree = self._styled_tree(parent, cols)
        self._log_tree.column("Username",  width=120, stretch=False)
        self._log_tree.column("Action",    width=220, stretch=False)
        self._log_tree.column("Path",      width=340)
        self._log_tree.column("Timestamp", width=140, stretch=False)

        btn_bar = tk.Frame(parent, bg=C["bg"], pady=8)
        btn_bar.pack(fill=tk.X)
        tk.Button(btn_bar, text="⟳  Refresh Logs", command=self._refresh_logs,
                  bg=C["accent2"], fg="white", activebackground=C["accent2"],
                  relief=tk.FLAT, bd=0, padx=10, pady=6,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side=tk.LEFT, padx=8)
        self._refresh_logs()

    def _refresh_logs(self) -> None:
        for row in self._log_tree.get_children():
            self._log_tree.delete(row)
        with get_db() as conn:
            rows = conn.execute("""
                SELECT u.username, l.action, l.target_dir, l.timestamp
                FROM logs l JOIN users u ON l.user_id = u.id
                ORDER BY l.id DESC
            """).fetchall()
        for row in rows:
            self._log_tree.insert("", tk.END, values=row)
