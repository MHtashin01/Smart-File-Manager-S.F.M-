import sqlite3
from core.db import get_db
from utils.hash import hash_password

def login_user(username: str, password: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password, salt, role FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if not row:
        return None
    user_id, uname, stored_hash, stored_salt, role = row
    _, attempt_hash = hash_password(password, stored_salt)
    if attempt_hash == stored_hash:
        return {"id": user_id, "username": uname, "role": role}
    return None

def register_user(username: str, password: str, role: str = "User") -> bool:
    salt, key = hash_password(password)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, ?)",
                (username, key, salt, role),
            )
        return True
    except sqlite3.IntegrityError:
        return False
