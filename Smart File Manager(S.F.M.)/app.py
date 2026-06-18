import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import tkinter as tk
from db_init import initialize_db
from ui.login_ui import LoginApp

if __name__ == "__main__":
    initialize_db()
    root = tk.Tk()
    LoginApp(root)
    root.mainloop()
