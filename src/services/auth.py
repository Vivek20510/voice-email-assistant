import bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password for secure storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its hashed value."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
