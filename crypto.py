"""Obfuscation-grade encryption using Fernet (AES-128-CBC + HMAC-SHA256).

This module provides a static embedded key for encrypt/decrypt operations.
The key is intentionally embedded in source — this is obfuscation-grade
protection to prevent casual inspection of metric CSVs, NOT security-grade
encryption designed to resist a determined adversary with source access.
"""

from cryptography.fernet import Fernet

FERNET_KEY = b"YVrZTl2xyS7QHyqxwaP2xd5gwMUjoctoo8RKUwjNi-8="


def encrypt_blob(data: bytes) -> bytes:
    return Fernet(FERNET_KEY).encrypt(data)


def decrypt_blob(token: bytes) -> bytes:
    return Fernet(FERNET_KEY).decrypt(token)
