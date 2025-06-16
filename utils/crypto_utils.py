from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from typing import Union

# Generate a secure encryption key from environment variable or generate a new one
SECRET_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
SALT = b'some_salt'  # In production, use a unique salt per user/data

def get_cipher_suite(key: str = None):
    """Create a Fernet cipher suite with the provided or default key."""
    key_to_use = key.encode() if key else SECRET_KEY.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(key_to_use))
    return Fernet(key)

def encrypt_data(data: Union[str, bytes], key: str = None) -> str:
    """Encrypt data using Fernet symmetric encryption."""
    if isinstance(data, str):
        data = data.encode()
    cipher_suite = get_cipher_suite(key)
    encrypted_data = cipher_suite.encrypt(data)
    return encrypted_data.decode()

def decrypt_data(encrypted_data: Union[str, bytes], key: str = None) -> str:
    """Decrypt data using Fernet symmetric encryption."""
    if isinstance(encrypted_data, str):
        encrypted_data = encrypted_data.encode()
    cipher_suite = get_cipher_suite(key)
    try:
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        return decrypted_data.decode()
    except Exception as e:
        raise ValueError("Decryption failed. Invalid or corrupted data.") from e

def encrypt_dict(data: dict, fields: list, key: str = None) -> dict:
    """Encrypt specific fields in a dictionary."""
    result = data.copy()
    for field in fields:
        if field in result and result[field] is not None:
            result[field] = encrypt_data(str(result[field]), key)
    return result

def decrypt_dict(data: dict, fields: list, key: str = None) -> dict:
    """Decrypt specific fields in a dictionary."""
    result = data.copy()
    for field in fields:
        if field in result and result[field] is not None:
            try:
                result[field] = decrypt_data(result[field], key)
            except ValueError:
                # If decryption fails, keep the original value
                continue
    return result
