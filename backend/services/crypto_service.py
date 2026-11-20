"""Cifrado autenticado AES-256-GCM para Project CC v6 (prototipo)."""
import base64, hashlib, hmac, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _master_key():
    value = os.environ.get('PROJECTCC_MASTER_KEY_B64', '')
    if not value:
        raise RuntimeError('Falta PROJECTCC_MASTER_KEY_B64; el cifrado falla de forma cerrada.')
    key = base64.b64decode(value, validate=True)
    if len(key) != 32:
        raise RuntimeError('PROJECTCC_MASTER_KEY_B64 debe representar exactamente 32 bytes.')
    return key


def encrypt_bytes(data: bytes, associated_data: bytes = b''):
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, associated_data)
    return key, nonce, ciphertext


def decrypt_bytes(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: bytes = b''):
    return AESGCM(key).decrypt(nonce, ciphertext, associated_data)


def wrap_key(dek: bytes, context: bytes):
    nonce = os.urandom(12)
    wrapped = AESGCM(_master_key()).encrypt(nonce, dek, context)
    return base64.b64encode(nonce).decode(), base64.b64encode(wrapped).decode()


def unwrap_key(nonce_b64: str, wrapped_b64: str, context: bytes):
    return AESGCM(_master_key()).decrypt(base64.b64decode(nonce_b64), base64.b64decode(wrapped_b64), context)


def keyed_digest(data: bytes):
    return hmac.new(_master_key(), data, hashlib.sha256).hexdigest()


def sha256_hex(data: bytes):
    return hashlib.sha256(data).hexdigest()
