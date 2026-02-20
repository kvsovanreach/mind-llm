def hash_password(password: str) -> str:
    """Hash a password for storing in config"""
    # Generate a random salt and hash with PBKDF2-SHA256
    import secrets
    import hashlib
    salt = secrets.token_hex(16)
    hash_value = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"sha256:{salt}:{hash_value}"

print(hash_password('testing new pass'))