import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import getpass

def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

# Enter your real API key when prompted (input hidden)
api_key = getpass.getpass("Paste your Anthropic API key: ").strip()
passphrase = getpass.getpass("Choose an office passphrase: ").strip()
confirm = getpass.getpass("Confirm passphrase: ").strip()

if passphrase != confirm:
    print("Passphrases didn't match. Try again.")
    exit(1)

salt = os.urandom(16)
key = derive_key(passphrase, salt)
f = Fernet(key)
encrypted = f.encrypt(api_key.encode())

# Save salt + encrypted key together
with open("apikey.enc", "wb") as out:
    out.write(salt + encrypted)

print("Done. Created apikey.enc — delete the old plaintext .txt file now.")