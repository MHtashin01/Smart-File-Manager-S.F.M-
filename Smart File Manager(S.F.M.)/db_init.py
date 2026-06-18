from core.db import get_db
from utils.hash import hash_password

def initialize_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                salt     TEXT NOT NULL,
                role     TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                extension   TEXT NOT NULL,
                folder_name TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                action     TEXT NOT NULL,
                target_dir TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        _seed_admin(conn)

def _seed_admin(conn) -> None:
    if conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        return
    salt, key = hash_password("admin123")
    conn.execute(
        "INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, ?)",
        ("admin", key, salt, "System Administrator"),
    )
    print("System: Admin account created (user: admin, pass: admin123).")
