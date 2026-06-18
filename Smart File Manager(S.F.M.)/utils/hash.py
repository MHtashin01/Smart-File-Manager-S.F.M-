import hashlib
import os

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:

    raw_salt: bytes = (
        bytes.fromhex(salt) if isinstance(salt, str) else (salt or os.urandom(32))
    )
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), raw_salt, 100_000)
    return raw_salt.hex(), key.hex()
