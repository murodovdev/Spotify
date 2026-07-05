import hashlib
import hmac

from cryptography.fernet import Fernet

from bot.config import settings

_fernet = Fernet(settings.fernet_key)


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()


def sign_state(user_id: int) -> str:
    sig = hmac.new(settings.fernet_key, str(user_id).encode(), hashlib.sha256)
    return f"{user_id}.{sig.hexdigest()[:24]}"


def parse_state(state: str) -> int | None:
    """OAuth state ni tekshiradi, to'g'ri bo'lsa telegram user_id qaytaradi."""
    try:
        user_id_str, _ = state.split(".", 1)
        if hmac.compare_digest(sign_state(int(user_id_str)), state):
            return int(user_id_str)
    except (ValueError, TypeError):
        pass
    return None
