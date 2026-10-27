import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

_ITERATIONS = 260_000

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _ITERATIONS)
    return f'pbkdf2_sha256${_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}'

def verify_password(password: str, hashed: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = hashed.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def generate_reset_token():
    raw = secrets.token_urlsafe(36)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), datetime.utcnow() + timedelta(hours=1)

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
