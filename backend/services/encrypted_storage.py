"""Almacenamiento cifrado de archivos fuera de Fabric (AES-256-GCM).
La autorización del usuario debe validarse en la ruta/API ANTES de llamar read_file().
"""
import base64, os, uuid
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from models import db, ArchivoCifrado
from services.crypto_service import wrap_key, unwrap_key, keyed_digest, sha256_hex


def _storage_root():
    root=Path(os.environ.get('PROJECTCC_ENCRYPTED_STORAGE','/var/lib/projectcc/encrypted')).resolve()
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    return root


def store_file(content:bytes, user_id:int, original_name:str, mime_type:str='application/octet-stream', indicio_id=None, registro_id=None):
    if not isinstance(content,(bytes,bytearray)) or not content:
        raise ValueError('El archivo está vacío o no es binario.')
    file_id=str(uuid.uuid4())
    dek=os.urandom(32)
    aad=f'projectcc:file:{file_id}:v1'.encode()
    nonce=os.urandom(12)
    ciphertext=AESGCM(dek).encrypt(nonce,bytes(content),aad)
    name_nonce=os.urandom(12)
    encrypted_name=AESGCM(dek).encrypt(name_nonce,original_name.encode('utf-8'),aad+b':name')
    encrypted_name_b64=base64.b64encode(name_nonce+encrypted_name).decode()
    key_nonce_b64,key_wrapped_b64=wrap_key(dek,f'projectcc:filekey:{file_id}'.encode())
    relative=Path(file_id[:2]) / f'{file_id}.bin'
    root=_storage_root(); target=(root/relative).resolve()
    if root not in target.parents: raise ValueError('Ruta de almacenamiento inválida.')
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=target.with_suffix('.tmp')
    tmp.write_bytes(ciphertext); os.chmod(tmp,0o600); tmp.replace(target)
    row=ArchivoCifrado(archivo_id=file_id,indicio_id=indicio_id,registro_id=registro_id,
        ruta_relativa=str(relative),nombre_original_cifrado=encrypted_name_b64,mime_type=mime_type[:120],
        nonce_b64=base64.b64encode(nonce).decode(),hash_cifrado=sha256_hex(ciphertext),hash_hmac=keyed_digest(bytes(content)),
        dek_envuelta_b64=key_wrapped_b64,dek_nonce_b64=key_nonce_b64,version_clave=1,creado_por_id=user_id)
    db.session.add(row); db.session.flush()
    return row


def read_file(archivo_id:str):
    """Devuelve (bytes, nombre, mime). La API debe comprobar custodio/escrow previamente."""
    row=ArchivoCifrado.query.filter_by(archivo_id=archivo_id).first()
    if not row: raise FileNotFoundError('Archivo no encontrado.')
    dek=unwrap_key(row.dek_nonce_b64,row.dek_envuelta_b64,f'projectcc:filekey:{archivo_id}'.encode())
    root=_storage_root(); target=(root/row.ruta_relativa).resolve()
    if root not in target.parents: raise RuntimeError('Ruta de archivo fuera del almacenamiento permitido.')
    ciphertext=target.read_bytes()
    if sha256_hex(ciphertext) != row.hash_cifrado: raise RuntimeError('La integridad del archivo cifrado no coincide.')
    aad=f'projectcc:file:{archivo_id}:v{row.version_clave}'.encode()
    content=AESGCM(dek).decrypt(base64.b64decode(row.nonce_b64),ciphertext,aad)
    if keyed_digest(content) != row.hash_hmac: raise RuntimeError('La verificación HMAC del contenido falló.')
    name_blob=base64.b64decode(row.nombre_original_cifrado)
    name=AESGCM(dek).decrypt(name_blob[:12],name_blob[12:],aad+b':name').decode('utf-8')
    return content,name,row.mime_type
