import bcrypt
from shared import config


def verify_passcode(passcode: str) -> bool:
    """Verify a plain-text passcode against the stored bcrypt hash."""
    if not config.ADMIN_PASSCODE_HASH:
        return False
    return bcrypt.checkpw(passcode.encode(), config.ADMIN_PASSCODE_HASH.encode())


def hash_passcode(passcode: str) -> str:
    """Return a bcrypt hash of the given passcode."""
    return bcrypt.hashpw(passcode.encode(), bcrypt.gensalt()).decode()
