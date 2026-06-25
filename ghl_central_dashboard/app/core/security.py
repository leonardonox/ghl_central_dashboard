from cryptography.fernet import Fernet
from app.core.config import get_settings


def encrypt_token(token: str) -> str:
    fernet = Fernet(get_settings().token_encryption_key.encode())
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    fernet = Fernet(get_settings().token_encryption_key.encode())
    return fernet.decrypt(encrypted_token.encode()).decode()
