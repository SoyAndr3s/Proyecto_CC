"""Utilidades de recepción de imágenes para Project CC v6."""
import base64
from services.encrypted_storage import store_file


def save_base64_image(app, data_url, subfolder, indicio_id=None, registro_id=None, user_id=None):
    """Decodifica una imagen y la almacena cifrada; devuelve `enc/<archivo_id>`."""
    if not data_url or not isinstance(data_url, str) or not data_url.startswith('data:image'):
        return None
    try:
        header, encoded = data_url.split(',', 1)
        content=base64.b64decode(encoded,validate=True)
    except (ValueError, base64.binascii.Error):
        return None
    mime=header[5:].split(';',1)[0] or 'application/octet-stream'
    ext='jpg' if 'jpeg' in mime or 'jpg' in mime else ('webp' if 'webp' in mime else 'png')
    row=store_file(content,user_id or 0,f'{subfolder}-{row_name_placeholder(ext)}',mime,indicio_id,registro_id)
    return f'enc/{row.archivo_id}'


def row_name_placeholder(ext):
    # El nombre original es metadato cifrado; no contiene el nombre del usuario.
    return f'captura.{ext}'
