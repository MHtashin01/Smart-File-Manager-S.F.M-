import tkinter as tk
from tkinter import messagebox

from config import C
from core.auth import login_user
from ui.registration_ui import RegistrationWindow
from ui.admin_ui import AdminDashboard
from ui.dashboard import  UserDashboard

class LoginApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Smart File Manager")
        self._draw()

    def _draw(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=C["bg"])
        self.root.geometry("420x440")

        hdr = tk.Frame(self.root, bg=C["accent"], pady=16)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Smart File Manager", bg=C["accent"], fg="white",
                 font=("Segoe UI", 15, "bold")).pack()
        tk.Label(hdr, text="Organise smarter, not harder", bg=C["accent"], fg="#ddd6fe",
                 font=("Segoe UI", 9)).pack()

        tk.Label(self.root, text="Sign in to your account",
                 bg=C["bg"], fg=C["sub"], font=("Segoe UI", 9)).pack(pady=(18, 6))

        card = tk.Frame(self.root, bg=C["panel"], padx=30, pady=24)
        card.pack(padx=30, pady=4, fill=tk.X)

        def _field(row: int, label: str, show: str = "") -> tk.Entry:
            tk.Label(card, text=label, bg=C["panel"], fg=C["sub"],
                     font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", pady=7)
            e = tk.Entry(card, show=show, width=24,
                         bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                         relief=tk.FLAT, bd=6, font=("Segoe UI", 10))
            e.grid(row=row, column=1, padx=(10, 0), pady=7)
            return e

        self._ent_u = _field(0, "Username")
        self._ent_p = _field(1, "Password", show="*")
        self._ent_u.focus()
        self.root.bind("<Return>", lambda _e: self._handle_login())

        btn_f = tk.Frame(self.root, bg=C["bg"])
        btn_f.pack(pady=18)

        def _btn(text: str, cmd, color: str) -> tk.Button:
            b = tk.Button(btn_f, text=text, command=cmd,
                          bg=color, fg="white", activebackground=color,
                          relief=tk.FLAT, bd=0, padx=12, pady=9,
                          font=("Segoe UI", 9, "bold"), cursor="hand2", width=20)
            b.pack(pady=5)
            return b

        _btn("→  Login",              self._handle_login,  C["green"])
        _btn("✦  Create New Account", self._open_register, C["accent"])

        tk.Label(self.root,
                 bg=C["bg"], fg=C["sub"], font=("Segoe UI", 8)).pack(pady=(4, 0))

    def _handle_login(self) -> None:
        user = login_user(self._ent_u.get().strip(), self._ent_p.get())
        if user:
            self._route(user)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.",
                                 parent=self.root)

    def _route(self, user: dict) -> None:
        role = user["role"]
        dashboard_map = {
            "System Administrator": AdminDashboard,
        }
        cls = dashboard_map.get(role, UserDashboard)
        cls(self.root, user, self._logout)

    def _open_register(self) -> None:
        RegistrationWindow(self.root, self._draw)

    def _logout(self) -> None:
        self.root.unbind("<Return>")
        self._draw()
