"""
Modelos de base de datos — SQLite vía SQLAlchemy.
Cada Registro (un formulario de cadena de custodia) tiene indicios,
servidores públicos y bloques de trazabilidad relacionados.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(150))
    institucion = db.Column(db.String(200))
    cargo = db.Column(db.String(150))


class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

    folio = db.Column(db.String(50))
    institucion = db.Column(db.String(200))
    folio_llamado = db.Column(db.String(100))
    fecha_hora = db.Column(db.String(100))
    persona_registro = db.Column(db.String(200))
    lugar_intervencion = db.Column(db.Text)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)

    motivo_inicio = db.Column(db.String(50))
    documentacion = db.Column(db.String(300))
    documentacion_otro = db.Column(db.String(300))
    recoleccion_manual = db.Column(db.Text)
    recoleccion_instrumental = db.Column(db.Text)
    empaque_bolsa = db.Column(db.Text)
    empaque_caja = db.Column(db.Text)
    empaque_recipientes = db.Column(db.Text)
    traslado_via = db.Column(db.String(50))
    condiciones_especiales = db.Column(db.String(10))
    recomendaciones = db.Column(db.Text)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    indicios = db.relationship('Indicio', backref='registro', cascade='all, delete-orphan')
    servidores = db.relationship('ServidorPublico', backref='registro', cascade='all, delete-orphan')
    trazabilidad = db.relationship('Trazabilidad', backref='registro', cascade='all, delete-orphan')


class Indicio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'))
    identificacion = db.Column(db.String(50))
    descripcion = db.Column(db.Text)
    ubicacion = db.Column(db.Text)
    hora = db.Column(db.String(50))
    foto_path = db.Column(db.String(300), nullable=True)  # ruta relativa dentro de /uploads


class ServidorPublico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'))
    nombre = db.Column(db.String(200))
    institucion = db.Column(db.String(200))
    etapa = db.Column(db.String(100))
    firma_path = db.Column(db.String(300), nullable=True)


class Trazabilidad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'))
    fecha = db.Column(db.String(100))
    actividad = db.Column(db.String(300))
    lugar = db.Column(db.Text)
    entrega = db.Column(db.String(300))
    recibe = db.Column(db.String(300))
    observaciones = db.Column(db.Text)
    firma_entrega_path = db.Column(db.String(300), nullable=True)
    firma_recibe_path = db.Column(db.String(300), nullable=True)


class CustodiaAsignacion(db.Model):
    """Responsable vigente del RCC completo en v5; pendiente migrar a nivel de indicio individual."""
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'), unique=True, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    asignado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    asignado_por = db.relationship('Usuario', foreign_keys=[asignado_por_id])


class AsignacionIndicio(db.Model):
    """Responsable vigente por indicio; un RCC puede contener indicios con custodios distintos."""
    id = db.Column(db.Integer, primary_key=True)
    indicio_id = db.Column(db.Integer, db.ForeignKey('indicio.id'), unique=True, nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    asignado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    etapa_asignada = db.Column(db.String(40), nullable=True)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    indicio = db.relationship('Indicio', backref=db.backref('asignacion_custodia', uselist=False))
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    asignado_por = db.relationship('Usuario', foreign_keys=[asignado_por_id])


class MovimientoEtapa(db.Model):
    """Historial append-only de movimientos operativos asociados a un indicio."""
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'), nullable=False)
    indicio_id = db.Column(db.Integer, db.ForeignKey('indicio.id'), nullable=True, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    siguiente_usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    etapa = db.Column(db.String(40), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    lugar = db.Column(db.Text)
    actividad = db.Column(db.Text)
    estado_embalaje = db.Column(db.String(200))
    observaciones = db.Column(db.Text)
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    siguiente_usuario = db.relationship('Usuario', foreign_keys=[siguiente_usuario_id])

class UsuarioPermiso(db.Model):
    """Permisos explícitos por cuenta; permiten excepciones sin alterar el rol base."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    permiso = db.Column(db.String(100), nullable=False)
    permitido = db.Column(db.Boolean, nullable=False, default=True)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('usuario_id', 'permiso', name='uq_usuario_permiso'),)


class UsuarioRol(db.Model):
    """Rol principal y estado de acceso de una cuenta."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), unique=True, nullable=False)
    rol = db.Column(db.String(40), nullable=False, default='perito')
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario = db.relationship('Usuario', backref=db.backref('configuracion_acceso', uselist=False))


class Auditoria(db.Model):
    """Bitácora de seguridad y operaciones. No expone una ruta de edición/borrado."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    usuario_texto = db.Column(db.String(100))
    evento = db.Column(db.String(80), nullable=False, index=True)
    recurso = db.Column(db.String(120))
    recurso_id = db.Column(db.String(80))
    resultado = db.Column(db.String(30), nullable=False, default='exitoso')
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(300))
    detalle = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    usuario = db.relationship('Usuario')


class TransferenciaPendiente(db.Model):
    """Entrega propuesta por indicio; la asignación cambia únicamente cuando el receptor acepta."""
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'), nullable=False, index=True)
    indicio_id = db.Column(db.Integer, db.ForeignKey('indicio.id'), nullable=True, index=True)
    movimiento_id = db.Column(db.Integer, db.ForeignKey('movimiento_etapa.id'), nullable=False)
    entrega_usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    recibe_usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    estado = db.Column(db.String(20), nullable=False, default='pendiente', index=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resuelto_en = db.Column(db.DateTime)
    observaciones_receptor = db.Column(db.Text)
    entrega_usuario = db.relationship('Usuario', foreign_keys=[entrega_usuario_id])
    recibe_usuario = db.relationship('Usuario', foreign_keys=[recibe_usuario_id])
    movimiento = db.relationship('MovimientoEtapa')
    indicio = db.relationship('Indicio')


class DetalleEtapa(db.Model):
    """Datos específicos de una intervención; evita añadir campos de análisis/bodega al formulario RCC."""
    id = db.Column(db.Integer, primary_key=True)
    movimiento_id = db.Column(db.Integer, db.ForeignKey('movimiento_etapa.id'), unique=True, nullable=False)
    datos_json = db.Column(db.Text, nullable=False, default='{}')
    movimiento = db.relationship('MovimientoEtapa', backref=db.backref('detalle_especifico', uselist=False, cascade='all, delete-orphan'))


class IntentoAcceso(db.Model):
    """Intentos de autenticación para limitar fuerza bruta por IP."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_intentado = db.Column(db.String(80))
    ip = db.Column(db.String(64), nullable=False, index=True)
    exitoso = db.Column(db.Boolean, nullable=False, default=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

class SolicitudHTTP(db.Model):
    """Registro técnico de cada petición API sin guardar contraseñas ni cuerpos."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    usuario_texto = db.Column(db.String(100))
    metodo = db.Column(db.String(10), nullable=False)
    ruta = db.Column(db.String(300), nullable=False)
    estado_http = db.Column(db.Integer, nullable=False)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(300))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class InstitucionFabric(db.Model):
    """Organización participante de la red Fabric."""
    __tablename__ = 'institucion_fabric'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(40), unique=True, nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    msp_id = db.Column(db.String(100), unique=True, nullable=False)
    peer_endpoint = db.Column(db.String(255))
    activa = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class IdentidadFabric(db.Model):
    """Certificado individual. La clave privada se conserva cifrada, nunca en claro."""
    __tablename__ = 'identidad_fabric'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), unique=True, nullable=False, index=True)
    institucion_id = db.Column(db.Integer, db.ForeignKey('institucion_fabric.id'), nullable=False)
    msp_id = db.Column(db.String(100), nullable=False)
    certificado_pem = db.Column(db.Text, nullable=False)
    clave_privada_cifrada = db.Column(db.Text, nullable=False)
    huella_sha256 = db.Column(db.String(64), nullable=False, unique=True)
    numero_serie = db.Column(db.String(160))
    estado = db.Column(db.String(20), nullable=False, default='activo')
    emitido_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revocado_en = db.Column(db.DateTime)
    usuario = db.relationship('Usuario')
    institucion = db.relationship('InstitucionFabric')


class EventoBlockchain(db.Model):
    """Outbox transaccional y confirmación de eventos de cadena de custodia."""
    __tablename__ = 'evento_blockchain'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'), nullable=True, index=True)
    indicio_id = db.Column(db.Integer, db.ForeignKey('indicio.id'), nullable=True, index=True)
    actor_usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    tipo_evento = db.Column(db.String(60), nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    payload_hash = db.Column(db.String(64), nullable=False)
    estado = db.Column(db.String(24), nullable=False, default='PENDIENTE', index=True)
    intentos = db.Column(db.Integer, nullable=False, default=0)
    tx_id = db.Column(db.String(128), unique=True)
    block_number = db.Column(db.String(40))
    validation_code = db.Column(db.String(40))
    ultimo_error = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmado_en = db.Column(db.DateTime)
    actor = db.relationship('Usuario')


class ArchivoCifrado(db.Model):
    """Metadatos de archivos cifrados almacenados fuera del ledger."""
    __tablename__ = 'archivo_cifrado'
    id = db.Column(db.Integer, primary_key=True)
    archivo_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    indicio_id = db.Column(db.Integer, db.ForeignKey('indicio.id'), nullable=True, index=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'), nullable=True, index=True)
    ruta_relativa = db.Column(db.String(500), nullable=False)
    nombre_original_cifrado = db.Column(db.Text)
    mime_type = db.Column(db.String(120))
    algoritmo = db.Column(db.String(40), nullable=False, default='AES-256-GCM')
    nonce_b64 = db.Column(db.String(64), nullable=False)
    hash_cifrado = db.Column(db.String(64), nullable=False)
    hash_hmac = db.Column(db.String(64), nullable=False)
    dek_envuelta_b64 = db.Column(db.Text, nullable=False)
    dek_nonce_b64 = db.Column(db.String(64), nullable=False)
    version_clave = db.Column(db.Integer, nullable=False, default=1)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ClaveEvidencia(db.Model):
    """DEK envuelta por la KEK del servidor; solo accesible a servicios autorizados."""
    __tablename__ = 'clave_evidencia'
    id = db.Column(db.Integer, primary_key=True)
    indicio_id = db.Column(db.Integer, db.ForeignKey('indicio.id'), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    dek_envuelta_b64 = db.Column(db.Text, nullable=False)
    nonce_b64 = db.Column(db.String(64), nullable=False)
    algoritmo = db.Column(db.String(40), nullable=False, default='AES-256-GCM')
    activa = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('indicio_id', 'version', name='uq_clave_indicio_version'),)


class SolicitudEscrow(db.Model):
    """Acceso administrativo excepcional mediante escrow de un solo administrador."""
    __tablename__ = 'solicitud_escrow'
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    indicio_id = db.Column(db.Integer, db.ForeignKey('indicio.id'), nullable=False, index=True)
    administrador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(24), nullable=False, default='SOLICITADA')
    expira_en = db.Column(db.DateTime, nullable=False)
    creada_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    utilizada_en = db.Column(db.DateTime)
    ip = db.Column(db.String(64))
    administrador = db.relationship('Usuario')
