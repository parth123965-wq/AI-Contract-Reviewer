from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password=password)

def verify_password(password: str, password_hash_value: str) -> bool:
    return password_hash.verify(
        password=password,
        hash=password_hash_value
    )