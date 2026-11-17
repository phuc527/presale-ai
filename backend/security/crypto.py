import base64
import hashlib
import hmac
import os
import secrets
from cryptography.fernet import Fernet, InvalidToken
from backend.config import settings


def _derive_fernet_key(master_key: bytes) -> bytes:
    digest = hashlib.sha256(master_key).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET = Fernet(_derive_fernet_key(settings.master_key))


def encrypt_secret(plaintext: str) -> str:
    """Encrypts sensitive credentials (API keys, OAuth tokens) at rest using AES-128-CBC + HMAC-SHA256 (Fernet)."""
    if not plaintext:
        return ""
    token = _FERNET.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypts stored credentials safely."""
    if not ciphertext:
        return ""
    try:
        return _FERNET.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_secret(secret: str) -> str:
    """Returns a masked display string so full keys are never exposed to the UI or logs."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "••••••••"
    return f"{secret[:4]}••••••{secret[-4:]}"


def hash_password(password: str) -> str:
    """Hashes user passwords with PBKDF2-HMAC-SHA256 (310,000 iterations) and random 16-byte salt."""
    salt = os.urandom(16)
    iterations = 310_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time password verification."""
    try:
        algo, iter_str, salt_b64, hash_b64 = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
        salt = base64.b64decode(salt_b64)
        expected_dk = base64.b64decode(hash_b64)
        actual_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_dk, expected_dk)
    except Exception:
        return False


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
