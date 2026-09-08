"""Decrypts the office API key at runtime. Never writes plaintext to disk."""
import base64
import getpass
import sys
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

_cached_key = None  # so the passphrase is only asked once per app run


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def _get_base_dir() -> Path:
    """
    Returns the folder the .exe (or script) actually lives in.
    When PyInstaller bundles as onefile, __file__ points to a temp
    extraction folder, so we use sys.executable instead in that case.
    """
    if getattr(sys, 'frozen', False):
        # Running as a bundled .exe
        return Path(sys.executable).parent
    else:
        # Running as a plain .py script
        return Path(__file__).parent.parent


def load_api_key() -> Optional[str]:
    """
    Decrypts apikey.enc using a passphrase entered by the user.
    Looks for apikey.enc in the same folder as the .exe (or project root
    when running as a script). Caches the decrypted key in memory so the
    passphrase is only asked once per run.

    Returns None if apikey.enc doesn't exist, so callers (classifier.py's
    _setup_claude) fall back to CLIP the same way they do when
    ANTHROPIC_API_KEY isn't set — matching behavior on any machine (dev,
    CI, a fresh office install) where no key has been configured yet at
    all. If apikey.enc DOES exist but the passphrase is wrong three times,
    that's a different situation (a key is configured but inaccessible)
    and still exits, since silently degrading to CLIP there could mask a
    real credential problem.
    """
    global _cached_key
    if _cached_key:
        return _cached_key

    enc_path = _get_base_dir() / "apikey.enc"

    if not enc_path.exists():
        print(f"No apikey.enc found at {enc_path} — falling back to CLIP.")
        return None

    with open(enc_path, "rb") as f:
        data = f.read()
    salt, encrypted = data[:16], data[16:]

    for attempt in range(3):
        passphrase = getpass.getpass("Enter office passphrase: ").strip()
        try:
            key = _derive_key(passphrase, salt)
            api_key = Fernet(key).decrypt(encrypted).decode()
            _cached_key = api_key
            return api_key
        except Exception:
            print("Incorrect passphrase, try again.")

    print("Too many failed attempts. Exiting.")
    sys.exit(1)