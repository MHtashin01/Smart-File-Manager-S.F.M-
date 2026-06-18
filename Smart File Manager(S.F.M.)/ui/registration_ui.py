import tkinter as tk
from tkinter import messagebox

from config import C
from core.auth import register_user

class RegistrationWindow:
    def __init__(self, root: tk.Tk, on_close_callback) -> None:
        self.root = root
        self._on_close = on_close_callback
        self._draw()

    def _draw(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=C["bg"])
        self.root.geometry("420x380")
        self.root.title("Smart File Manager – Register")

        hdr = tk.Frame(self.root, bg=C["accent"], pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="✦  Create New Account", bg=C["accent"], fg="white",
                 font=("Segoe UI", 13, "bold")).pack()

        tk.Label(self.root, text="No role required — just pick a username and password.",
                 bg=C["bg"], fg=C["sub"], font=("Segoe UI", 9)).pack(pady=(14, 4))

        card = tk.Frame(self.root, bg=C["panel"], padx=30, pady=24)
        card.pack(padx=30, pady=6, fill=tk.X)

        def _field(row: int, label: str, show: str = "") -> tk.Entry:
            tk.Label(card, text=label, bg=C["panel"], fg=C["sub"],
                     font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", pady=6)
            e = tk.Entry(card, show=show, width=24,
                         bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                         relief=tk.FLAT, bd=6, font=("Segoe UI", 10))
            e.grid(row=row, column=1, padx=(10, 0), pady=6)
            return e

        self._ent_u  = _field(0, "Username")
        self._ent_p  = _field(1, "Password",         show="*")
        self._ent_p2 = _field(2, "Confirm Password", show="*")

        btn_row = tk.Frame(self.root, bg=C["bg"])
        btn_row.pack(pady=14)

        def _btn(text: str, cmd, color: str) -> tk.Button:
            b = tk.Button(btn_row, text=text, command=cmd,
                          bg=color, fg="white", activebackground=color,
                          relief=tk.FLAT, bd=0, padx=16, pady=8,
                          font=("Segoe UI", 9, "bold"), cursor="hand2")
            b.pack(side=tk.LEFT, padx=8)
            return b

        _btn("✔  Register",     self._handle_register, C["green"])
        _btn("← Back to Login", self._on_close,        C["accent"])

    def _handle_register(self) -> None:
        u  = self._ent_u.get().strip()
        p  = self._ent_p.get()
        p2 = self._ent_p2.get()
        if not u or not p:
            messagebox.showwarning("Missing", "Username and password cannot be empty.",
                                   parent=self.root)
            return
        if len(p) < 4:
            messagebox.showwarning("Weak Password", "Password must be at least 4 characters.",
                                   parent=self.root)
            return
        if p != p2:
            messagebox.showerror("Mismatch", "Passwords do not match.", parent=self.root)
            return
        if register_user(u, p, role="User"):
            messagebox.showinfo("Success", f"Account '{u}' created!\nYou can now log in.",
                                parent=self.root)
            self._on_close()
        else:
            messagebox.showerror("Username Taken", "That username is already taken.",
                                 parent=self.root)
