# =============================================================
# seeds.py — Generación y verificación de seed phrases (6 palabras)
# =============================================================
#
# Usamos SHA-256 con salt en vez de bcrypt porque:
# - Las seed phrases tienen ~69 bits de entropía (6 palabras de 3130)
# - No necesitan el key stretching de bcrypt
# - Evita problemas de compatibilidad bcrypt/passlib
#

import secrets
import hashlib
import os
from typing import Optional

from app.auth.wordlist import WORDS

SEED_WORD_COUNT = 6
SALT_SIZE = 16  # 128 bits de salt


def generate_seed_phrase() -> list[str]:
    """Genera 6 palabras aleatorias de la wordlist española."""
    indices = secrets.SystemRandom().sample(range(len(WORDS)), SEED_WORD_COUNT)
    return [WORDS[i] for i in indices]


def _normalize(phrase: list[str]) -> str:
    """Normaliza una seed phrase: minúsculas, sin espacios extra."""
    return " ".join(word.strip().lower() for word in phrase)


def hash_seed_phrase(phrase: list[str]) -> str:
    """Hashea una seed phrase con SHA-256 + salt.
    Retorna formato: salt_hex:hash_hex"""
    normalized = _normalize(phrase)
    salt = os.urandom(SALT_SIZE)
    h = hashlib.sha256(salt + normalized.encode()).hexdigest()
    return salt.hex() + ":" + h


def verify_seed_phrase(phrase: list[str], hashed: str) -> bool:
    """Verifica una seed phrase contra su hash (formato salt:hash)."""
    try:
        salt_hex, expected_hash = hashed.split(":", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, KeyError):
        return False

    normalized = _normalize(phrase)
    actual_hash = hashlib.sha256(salt + normalized.encode()).hexdigest()
    return actual_hash == expected_hash


def validate_words(words: list[str]) -> Optional[str]:
    """Valida que todas las palabras existan en la wordlist.
    Retorna None si son válidas, o un mensaje de error."""
    if len(words) != SEED_WORD_COUNT:
        return f"Deben ser exactamente {SEED_WORD_COUNT} palabras (recibidas {len(words)})"

    word_set = set(WORDS)
    for i, w in enumerate(words):
        if w.lower() not in word_set:
            return f"Palabra inválida en posición {i + 1}: '{w}'"

    return None
