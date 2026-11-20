"""
Backend del sistema de Cadena de Custodia — Flask.

Corre con:  python app.py
Antes, crea los usuarios iniciales con:  python seed_users.py
"""
import datetime
import json
import os
from functools import wraps

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory, g, redirect, abort
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import or_, inspect, text

from models import (db, Usuario, Registro, Indicio, ServidorPublico, Trazabilidad, CustodiaAsignacion, AsignacionIndicio, MovimientoEtapa, UsuarioPermiso, UsuarioRol, Auditoria, TransferenciaPendiente, DetalleEtapa, IntentoAcceso, SolicitudHTTP, InstitucionFabric, IdentidadFabric, EventoBlockchain, ArchivoCifrado, ClaveEvidencia, SolicitudEscrow)
from utils import save_base64_image

load_dotenv()  # lee el archivo .env si existe (ver .env.example)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
TOKEN_EXP_HOURS = 8

app = Flask(__name__)

# =====================================================================
# CONFIGURACIÓN — para producción, define estas variables de entorno
# en vez de dejarlas con su valor por defecto.
# =====================================================================
APP_ENV = os.environ.get('APP_ENV', 'development').lower()
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or ('dev-only-change-this-key-before-deployment' if APP_ENV != 'production' else None)
if not app.config['SECRET_KEY']:
    raise RuntimeError('Define SECRET_KEY en el entorno antes de iniciar en producción.')
if APP_ENV == 'production' and (len(app.config['SECRET_KEY']) < 32 or 'REEMPLAZA' in app.config['SECRET_KEY'] or 'cambia-esta' in app.config['SECRET_KEY']):
    raise RuntimeError('SECRET_KEY debe ser un secreto aleatorio de al menos 32 caracteres en producción.')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'custodia.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Secret Key de Cloudflare Turnstile (NUNCA la Site Key del frontend).
# Consíguela en dash.cloudflare.com > Turnstile, junto con la Site Key.
TURNSTILE_SECRET_KEY = os.environ.get('TURNSTILE_SECRET_KEY', '')

# La interfaz y la API se sirven desde el mismo origen. No habilitar CORS
# globalmente: si se separan los dominios, declarar únicamente el origen exacto.
if os.environ.get('CORS_ORIGIN'):
    CORS(app, origins=[os.environ['CORS_ORIGIN']])

if os.environ.get('TRUST_PROXY', '0') == '1':
    # Actívalo únicamente si Flask está detrás de un proxy inverso controlado (p. ej. Nginx).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db.init_app(app)

@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'geolocation=(self), camera=(), microphone=()')
    # Bitácora técnica de todas las solicitudes API. No se almacena el cuerpo
    # de la petición para evitar registrar contraseñas, firmas u otros datos.
    if request.path.startswith('/api/'):
        current = getattr(g, 'current_user', None)
        payload = request.get_json(silent=True) or {} if request.method in {'POST', 'PUT', 'PATCH'} else {}
        try:
            db.session.add(SolicitudHTTP(
                usuario_id=current.id if current else None,
                usuario_texto=current.usuario if current else str(payload.get('usuario') or 'anónimo')[:100],
                metodo=request.method, ruta=request.path[:300], estado_http=response.status_code,
                ip=request.remote_addr, user_agent=(request.headers.get('User-Agent') or '')[:300]
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('No se pudo guardar la bitácora HTTP')
    return response


# =====================================================================
# TURNSTILE — verificación real contra el servidor de Cloudflare
# =====================================================================
def verify_turnstile(token, remote_ip=None):
    if not TURNSTILE_SECRET_KEY:
        # Solo se omite en desarrollo local; producción falla de forma cerrada.
        return APP_ENV != 'production'
    if not token:
        return False
    try:
        resp = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={'secret': TURNSTILE_SECRET_KEY, 'response': token, 'remoteip': remote_ip},
            timeout=5,
        )
        return bool(resp.json().get('success'))
    except requests.RequestException:
        return False


# =====================================================================
# AUTENTICACIÓN — JWT en el header Authorization: Bearer <token>
# =====================================================================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            audit('auth.token_ausente', resultado='rechazado', detalle='Solicitud protegida sin token')
            db.session.commit()
            return jsonify({'error': 'Falta el token de autenticación'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            audit('auth.token_expirado', resultado='rechazado')
            db.session.commit()
            return jsonify({'error': 'Tu sesión expiró, inicia sesión de nuevo'}), 401
        except jwt.InvalidTokenError:
            audit('auth.token_invalido', resultado='rechazado')
            db.session.commit()
            return jsonify({'error': 'Token inválido'}), 401

        user = Usuario.query.get(int(payload.get('sub')))
        if not user:
            audit('auth.usuario_inexistente', resultado='rechazado', detalle='El identificador del token no corresponde a una cuenta')
            db.session.commit()
            return jsonify({'error': 'Usuario no encontrado'}), 401

        g.current_user = user
        access = UsuarioRol.query.filter_by(usuario_id=user.id).first()
        if access and not access.activo:
            audit('auth.cuenta_desactivada', resultado='rechazado', user=user)
            db.session.commit()
            return jsonify({'error': 'La cuenta está desactivada.'}), 403
        return f(*args, **kwargs)
    return decorated


def user_to_dict(u):
    effective = set(ROLE_PERMISSIONS.get(access_role(u), set()))
    for override in UsuarioPermiso.query.filter_by(usuario_id=u.id).all():
        if override.permitido: effective.add(override.permiso)
        else: effective.discard(override.permiso)
    return {'id': u.id, 'usuario': u.usuario, 'nombre': u.nombre, 'institucion': u.institucion, 'cargo': u.cargo, 'rol': access_role(u), 'permisos': sorted(effective)}


ROLE_PERMISSIONS = {
    'administrador': {'admin.access', 'admin.users', 'admin.permissions', 'audit.read', 'records.read_all', 'trace.read_all', 'evidence.escrow'},
    'perito': {'rcc.create', 'traslado.create', 'entrega.create', 'trace.read_own', 'movimiento.create'},
    'analista': {'rcc.create', 'traslado.create', 'analisis.create', 'entrega.create', 'trace.read_own', 'movimiento.create'},
    'almacenista': {'traslado.create', 'almacenamiento.create', 'entrega.create', 'trace.read_own', 'movimiento.create'},
    'primer_respondiente': {'rcc.create', 'traslado.create', 'entrega.create', 'trace.read_own', 'movimiento.create'},
    'supervisor': {'audit.read', 'entrega.create', 'juicio.create'},
}
VALID_ROLES = set(ROLE_PERMISSIONS)
ALL_PERMISSIONS = set().union(*ROLE_PERMISSIONS.values()) | {'traslado.create', 'analisis.create', 'almacenamiento.create', 'juicio.create', 'entrega.create', 'movimiento.create', 'rcc.create', 'trace.read_own', 'evidence.escrow'}

def access_role(user):
    config = UsuarioRol.query.filter_by(usuario_id=user.id).first()
    return config.rol if config else 'perito'

def has_permission(user, permission):
    config = UsuarioRol.query.filter_by(usuario_id=user.id).first()
    if config and not config.activo:
        return False
    override = UsuarioPermiso.query.filter_by(usuario_id=user.id, permiso=permission).first()
    if override:
        return bool(override.permitido)
    return permission in ROLE_PERMISSIONS.get(access_role(user), set())

def require_permission(permission):
    def decorator(fn):
        @wraps(fn)
        @token_required
        def wrapped(*args, **kwargs):
            if not has_permission(g.current_user, permission):
                audit('permiso.denegado', resultado='rechazado', detalle=f'Permiso requerido: {permission}')
                db.session.commit()
                return jsonify({'error': 'No tienes autorización para realizar esta operación.', 'permiso': permission}), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def audit(event, resultado='exitoso', recurso=None, recurso_id=None, detalle=None, user=None):
    user = user or getattr(g, 'current_user', None)
    row = Auditoria(
        usuario_id=user.id if user else None,
        usuario_texto=user.usuario if user else (request.get_json(silent=True) or {}).get('usuario', 'desconocido'),
        evento=event, recurso=recurso, recurso_id=str(recurso_id) if recurso_id is not None else None,
        resultado=resultado, ip=request.remote_addr,
        user_agent=(request.headers.get('User-Agent') or '')[:300], detalle=(detalle or '')[:4000]
    )
    db.session.add(row)

def active_user_required(fn):
    @wraps(fn)
    @token_required
    def wrapped(*args, **kwargs):
        config = UsuarioRol.query.filter_by(usuario_id=g.current_user.id).first()
        if config and not config.activo:
            return jsonify({'error': 'La cuenta está desactivada. Contacta al administrador.'}), 403
        return fn(*args, **kwargs)
    return wrapped


# =====================================================================
# RUTAS
# =====================================================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    usuario = (data.get('usuario') or '').strip()
    password = data.get('password') or ''
    turnstile_token = data.get('turnstileToken')
    ip_origen = request.remote_addr or 'desconocida'
    limite = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
    intentos_fallidos = IntentoAcceso.query.filter_by(ip=ip_origen, exitoso=False).filter(IntentoAcceso.creado_en >= limite).count()
    if intentos_fallidos >= 8:
        audit('auth.rate_limit', resultado='bloqueado', detalle='Más de 8 intentos fallidos en 15 minutos')
        db.session.commit()
        return jsonify({'error': 'Se limitaron temporalmente los intentos desde esta dirección. Espera 15 minutos.'}), 429

    if not verify_turnstile(turnstile_token, request.remote_addr):
        db.session.add(IntentoAcceso(usuario_intentado=usuario[:80], ip=ip_origen, exitoso=False))
        audit('auth.captcha', resultado='rechazado', detalle='Verificación Turnstile fallida')
        db.session.commit()
        return jsonify({'error': 'No se pudo verificar el captcha. Inténtalo de nuevo.'}), 400

    user = Usuario.query.filter_by(usuario=usuario).first()
    if not user or not check_password_hash(user.password_hash, password):
        db.session.add(IntentoAcceso(usuario_intentado=usuario[:80], ip=ip_origen, exitoso=False))
        audit('auth.login', resultado='rechazado', detalle='Credenciales inválidas', user=user)
        db.session.commit()
        return jsonify({'error': 'Usuario o contraseña incorrectos.'}), 401
    access = UsuarioRol.query.filter_by(usuario_id=user.id).first()
    if access and not access.activo:
        db.session.add(IntentoAcceso(usuario_intentado=usuario[:80], ip=ip_origen, exitoso=False))
        audit('auth.login', resultado='rechazado', detalle='Cuenta desactivada', user=user)
        db.session.commit()
        return jsonify({'error': 'La cuenta está desactivada.'}), 403
    db.session.add(IntentoAcceso(usuario_intentado=usuario[:80], ip=ip_origen, exitoso=True))
    audit('auth.login', user=user)
    db.session.commit()

    payload = {
        'sub': str(user.id),
        'usuario': user.usuario,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXP_HOURS),
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token, 'user': user_to_dict(user)})


@app.route('/api/me', methods=['GET'])
@active_user_required
def me():
    return jsonify(user_to_dict(g.current_user))


@app.route('/api/registros', methods=['POST'])
@require_permission('rcc.create')
def crear_registro():
    data = request.get_json(silent=True) or {}
    coords = data.get('coords') or {}

    registro = Registro(
        usuario_id=g.current_user.id,
        folio=data.get('folio'),
        institucion=data.get('institucion'),
        folio_llamado=data.get('folioLlamado'),
        fecha_hora=data.get('fechaHora'),
        persona_registro=data.get('personaRegistro'),
        lugar_intervencion=data.get('lugarIntervencion'),
        lat=coords.get('lat'),
        lng=coords.get('lng'),
        motivo_inicio=data.get('motivoInicio'),
        documentacion=','.join(data.get('documentacion') or []),
        documentacion_otro=data.get('documentacionOtro'),
        recoleccion_manual=data.get('recoleccionManual'),
        recoleccion_instrumental=data.get('recoleccionInstrumental'),
        empaque_bolsa=data.get('empaqueBolsa'),
        empaque_caja=data.get('empaqueCaja'),
        empaque_recipientes=data.get('empaqueRecipientes'),
        traslado_via=data.get('trasladoVia'),
        condiciones_especiales=data.get('condicionesEspeciales'),
        recomendaciones=data.get('recomendaciones'),
    )
    db.session.add(registro)
    db.session.flush()  # asigna registro.id sin cerrar la transacción todavía

    # El creador queda como responsable vigente hasta que formalice una entrega.
    db.session.add(CustodiaAsignacion(
        registro_id=registro.id, usuario_id=g.current_user.id,
        asignado_por_id=g.current_user.id
    ))
    indicios_creados = []
    for item in data.get('identidad') or []:
        indicio = Indicio(
            registro_id=registro.id,
            identificacion=item.get('identificacion'),
            descripcion=item.get('descripcion'),
            ubicacion=item.get('ubicacion'),
            hora=item.get('hora'),
        )
        db.session.add(indicio)
        indicios_creados.append((indicio, item.get('foto')))
    db.session.flush()
    for indicio, foto_data in indicios_creados:
        indicio.foto_path = save_base64_image(app, foto_data, 'indicios', indicio_id=indicio.id, registro_id=registro.id, user_id=g.current_user.id)
        db.session.add(AsignacionIndicio(
            indicio_id=indicio.id, usuario_id=g.current_user.id,
            asignado_por_id=g.current_user.id
        ))
        db.session.add(MovimientoEtapa(
            registro_id=registro.id, indicio_id=indicio.id, usuario_id=g.current_user.id,
            etapa='procesamiento', actividad='Registro inicial creado'
        ))

    for item in data.get('servidores') or []:
        db.session.add(ServidorPublico(
            registro_id=registro.id,
            nombre=item.get('nombre'),
            institucion=item.get('institucion'),
            etapa=item.get('etapa'),
            firma_path=save_base64_image(app, item.get('firma'), 'firmas', registro_id=registro.id, user_id=g.current_user.id),
        ))

    for item in data.get('trazabilidad') or []:
        db.session.add(Trazabilidad(
            registro_id=registro.id,
            fecha=item.get('fecha'),
            actividad=item.get('actividad'),
            lugar=item.get('lugar'),
            entrega=item.get('entrega'),
            recibe=item.get('recibe'),
            observaciones=item.get('observaciones'),
            firma_entrega_path=save_base64_image(app, item.get('firmaEntrega'), 'firmas', registro_id=registro.id, user_id=g.current_user.id),
            firma_recibe_path=save_base64_image(app, item.get('firmaRecibe'), 'firmas', registro_id=registro.id, user_id=g.current_user.id),
        ))

    from blockchain.outbox import queue_event
    queue_event(actor_user_id=g.current_user.id, event_type='RCC_CREATED', record_id=registro.id,
                minimal_payload={'initialStage':'PROCESAMIENTO'})
    for indicio, foto_data in indicios_creados:
        queue_event(actor_user_id=g.current_user.id, event_type='EVIDENCE_REGISTERED',
                    evidence_id=indicio.id, record_id=registro.id,
                    minimal_payload={'initialStage':'PROCESAMIENTO'})
    for file_row in ArchivoCifrado.query.filter_by(registro_id=registro.id).all():
        queue_event(actor_user_id=g.current_user.id,event_type='ATTACHMENT_REGISTERED',evidence_id=file_row.indicio_id,record_id=registro.id,
                    minimal_payload={'ciphertextHash':file_row.hash_cifrado,'algorithm':file_row.algoritmo})
    audit('rcc.creado', recurso='registro', recurso_id=registro.id, detalle='Registro de cadena de custodia creado')
    db.session.commit()
    return jsonify({'id': registro.id, 'mensaje': 'Registro guardado correctamente'}), 201


@app.route('/api/registros', methods=['GET'])
@token_required
def listar_registros():
    # Los registros se muestran únicamente cuando el usuario tiene asignado al menos un indicio.
    # La asignación por RCC se conserva solo como compatibilidad con registros históricos sin indicios asignados.
    filas = []
    indicios_asignados = (Indicio.query.join(AsignacionIndicio, AsignacionIndicio.indicio_id == Indicio.id)
        .filter(AsignacionIndicio.usuario_id == g.current_user.id).all())
    por_registro = {}
    for item in indicios_asignados:
        por_registro.setdefault(item.registro_id, []).append(item)
    legacy_ids = [a.registro_id for a in CustodiaAsignacion.query.filter_by(usuario_id=g.current_user.id).all()]
    ids = set(por_registro) | set(legacy_ids)
    if has_permission(g.current_user, 'trace.read_all'):
        ids.update(r.id for r in Registro.query.all())
    registros = Registro.query.filter(Registro.id.in_(ids)).order_by(Registro.creado_en.desc()).all() if ids else []
    for r in registros:
        items = list(por_registro.get(r.id, []))
        if not items and not has_permission(g.current_user, 'trace.read_all'):
            # Compatibilidad: asigna indicios históricos solo si aún no tienen custodio individual.
            for item in Indicio.query.filter_by(registro_id=r.id).all():
                asignacion = AsignacionIndicio.query.filter_by(indicio_id=item.id).first()
                if not asignacion:
                    db.session.add(AsignacionIndicio(indicio_id=item.id, usuario_id=g.current_user.id, asignado_por_id=g.current_user.id))
                    items.append(item)
            if items:
                db.session.flush()
        elif has_permission(g.current_user, 'trace.read_all'):
            items = Indicio.query.filter_by(registro_id=r.id).all()
        # Un responsable RCC antiguo no debe ver un indicio que ya fue asignado a otra persona.
        if not items:
            continue
        filas.append({
            'id': r.id, 'folio': r.folio, 'institucion': r.institucion,
            'fechaHora': r.fecha_hora, 'personaRegistro': r.persona_registro,
            'lugarIntervencion': r.lugar_intervencion, 'creadoEn': r.creado_en.isoformat(),
            'indicios': [{'id': i.id, 'identificacion': i.identificacion, 'descripcion': i.descripcion, 'etapaAsignada': i.asignacion_custodia.etapa_asignada if i.asignacion_custodia else None} for i in items]
        })
    audit('registros.lista.consulta', recurso='registro', detalle=f'Resultados: {len(filas)}')
    db.session.commit()
    return jsonify(filas)


@app.route('/api/registros/<int:registro_id>', methods=['GET'])
@token_required
def obtener_registro(registro_id):
    r = Registro.query.get_or_404(registro_id)
    asignaciones_ids = {a.indicio_id for a in AsignacionIndicio.query.join(Indicio).filter(Indicio.registro_id == r.id, AsignacionIndicio.usuario_id == g.current_user.id).all()}
    if not asignaciones_ids and not has_permission(g.current_user, 'trace.read_all'):
        audit('trazabilidad.acceso', resultado='rechazado', recurso='registro', recurso_id=r.id, detalle='Consulta fuera de asignación')
        db.session.commit()
        return jsonify({'error': 'Acceso restringido: solo puedes consultar los indicios que tienes asignados.'}), 403
    audit('trazabilidad.consulta', recurso='registro', recurso_id=r.id)
    db.session.commit()
    return jsonify({
        'id': r.id,
        'folio': r.folio,
        'institucion': r.institucion,
        'folioLlamado': r.folio_llamado,
        'fechaHora': r.fecha_hora,
        'personaRegistro': r.persona_registro,
        'lugarIntervencion': r.lugar_intervencion,
        'coords': {'lat': r.lat, 'lng': r.lng} if r.lat is not None else None,
        'motivoInicio': r.motivo_inicio,
        'documentacion': r.documentacion.split(',') if r.documentacion else [],
        'documentacionOtro': r.documentacion_otro,
        'recoleccionManual': r.recoleccion_manual,
        'recoleccionInstrumental': r.recoleccion_instrumental,
        'empaqueBolsa': r.empaque_bolsa,
        'empaqueCaja': r.empaque_caja,
        'empaqueRecipientes': r.empaque_recipientes,
        'trasladoVia': r.traslado_via,
        'condicionesEspeciales': r.condiciones_especiales,
        'recomendaciones': r.recomendaciones,
        'identidad': [{
            'identificacion': i.identificacion, 'descripcion': i.descripcion,
            'ubicacion': i.ubicacion, 'hora': i.hora,
            'foto': f"/api/uploads/{i.foto_path}" if i.foto_path else None,
        } for i in r.indicios if i.id in asignaciones_ids or has_permission(g.current_user, 'trace.read_all')],
        'servidores': [{
            'nombre': s.nombre, 'institucion': s.institucion, 'etapa': s.etapa,
            'firma': f"/api/uploads/{s.firma_path}" if s.firma_path else None,
        } for s in r.servidores],
        'trazabilidad': [{
            'fecha': t.fecha, 'actividad': t.actividad, 'lugar': t.lugar,
            'entrega': t.entrega, 'recibe': t.recibe, 'observaciones': t.observaciones,
            'firmaEntrega': f"/api/uploads/{t.firma_entrega_path}" if t.firma_entrega_path else None,
            'firmaRecibe': f"/api/uploads/{t.firma_recibe_path}" if t.firma_recibe_path else None,
        } for t in r.trazabilidad],
    })


@app.route('/api/usuarios', methods=['GET'])
@active_user_required
def listar_usuarios():
    """Directorio mínimo para elegir receptor; nunca devuelve contraseñas."""
    audit('usuarios.directorio.consulta', recurso='usuario')
    db.session.commit()
    return jsonify([{**user_to_dict(u)} for u in Usuario.query.filter(Usuario.id != g.current_user.id).order_by(Usuario.nombre).all()
        if not UsuarioRol.query.filter_by(usuario_id=u.id, activo=False).first()])


@app.route('/api/registros/<int:registro_id>/movimientos', methods=['GET'])
@token_required
def listar_movimientos(registro_id):
    indicio_id = request.args.get('indicio_id', type=int)
    if not indicio_id:
        return jsonify({'error': 'Selecciona un indicio para consultar su trazabilidad.'}), 400
    indicio = Indicio.query.filter_by(id=indicio_id, registro_id=registro_id).first_or_404()
    asignacion = AsignacionIndicio.query.filter_by(indicio_id=indicio.id).first()
    if (not asignacion or asignacion.usuario_id != g.current_user.id) and not has_permission(g.current_user, 'trace.read_all'):
        audit('trazabilidad.acceso', resultado='rechazado', recurso='indicio', recurso_id=indicio.id, detalle='Consulta fuera de asignación')
        db.session.commit()
        return jsonify({'error': 'Solo el responsable vigente o un supervisor autorizado puede consultar la trazabilidad del indicio.'}), 403
    # Los eventos antiguos vinculados al RCC completo se muestran como eventos históricos
    # compartidos en cada indicio del registro, sin atribuirlos artificialmente a uno solo.
    rows = MovimientoEtapa.query.filter(or_(MovimientoEtapa.indicio_id == indicio.id,
        (MovimientoEtapa.indicio_id.is_(None)) & (MovimientoEtapa.registro_id == registro_id))
        ).order_by(MovimientoEtapa.fecha_hora.asc(), MovimientoEtapa.id.asc()).all()
    audit('trazabilidad.movimientos.consulta', recurso='indicio', recurso_id=indicio.id)
    db.session.commit()
    historial = []
    etapa_anterior = 'RCC'
    for x in rows:
        transferencia = TransferenciaPendiente.query.filter_by(movimiento_id=x.id).first()
        historial.append({
            'id': x.id, 'etapa': x.etapa, 'etapaOrigen': etapa_anterior, 'etapaDestino': x.etapa,
            'fechaHora': x.fecha_hora.isoformat(), 'usuario': x.usuario.nombre if x.usuario else '',
            'siguienteUsuario': x.siguiente_usuario.nombre if x.siguiente_usuario else '',
            'transferenciaEstado': transferencia.estado if transferencia else None,
            'transferenciaResueltaEn': transferencia.resuelto_en.isoformat() if transferencia and transferencia.resuelto_en else None,
            'observacionesRecepcion': transferencia.observaciones_receptor if transferencia else '',
            'lugar': x.lugar, 'actividad': x.actividad, 'estadoEmbalaje': x.estado_embalaje,
            'observaciones': x.observaciones,
            'detalles': json.loads(x.detalle_especifico.datos_json) if x.detalle_especifico and x.detalle_especifico.datos_json else {}
        })
        etapa_anterior = x.etapa
    return jsonify(historial)


@app.route('/api/registros/<int:registro_id>/movimientos', methods=['POST'])
@token_required
def crear_movimiento(registro_id):
    r = Registro.query.get_or_404(registro_id)
    data = request.get_json(silent=True) or {}
    indicio_id = data.get('indicioId')
    if not indicio_id:
        return jsonify({'error': 'Debes seleccionar el indicio al que corresponde este movimiento.'}), 400
    indicio = Indicio.query.filter_by(id=indicio_id, registro_id=r.id).first()
    if not indicio:
        return jsonify({'error': 'El indicio no pertenece al registro seleccionado.'}), 404
    asignacion = AsignacionIndicio.query.filter_by(indicio_id=indicio.id).first()
    if not asignacion or asignacion.usuario_id != g.current_user.id:
        audit('movimiento.no_autorizado', resultado='rechazado', recurso='indicio', recurso_id=indicio.id, detalle='La cuenta no es responsable vigente')
        db.session.commit()
        return jsonify({'error': 'No eres el responsable vigente de este indicio.'}), 403
    transferencia_pendiente = TransferenciaPendiente.query.filter(
        TransferenciaPendiente.estado == 'pendiente',
        or_(TransferenciaPendiente.indicio_id == indicio.id,
            (TransferenciaPendiente.indicio_id.is_(None)) & (TransferenciaPendiente.registro_id == r.id))
    ).first()
    if transferencia_pendiente:
        return jsonify({'error': 'El indicio tiene una entrega–recepción pendiente. Debe aceptarse o rechazarse antes de registrar otro movimiento.'}), 409
    etapa = (data.get('etapa') or '').strip().lower()
    permission = f'{etapa}.create'
    if etapa not in {'traslado', 'analisis', 'almacenamiento', 'juicio', 'entrega-recepcion', 'nuevo-movimiento'}:
        return jsonify({'error': 'Etapa no válida.'}), 400
    if asignacion.etapa_asignada and etapa != asignacion.etapa_asignada:
        return jsonify({'error': f'Este indicio tiene asignada como siguiente etapa: {asignacion.etapa_asignada}. Registra esa etapa o solicita una reasignación autorizada.'}), 409
    if not has_permission(g.current_user, permission) and not (etapa == 'nuevo-movimiento' and has_permission(g.current_user, 'movimiento.create')):
        audit('permiso.denegado', resultado='rechazado', recurso='indicio', recurso_id=indicio.id, detalle=f'Permiso requerido: {permission}')
        db.session.commit()
        return jsonify({'error': 'Tu rol o permisos no permiten registrar esta etapa.', 'permiso': permission}), 403

    next_id = data.get('siguienteUsuarioId')
    next_user = Usuario.query.get(next_id) if next_id else None
    if next_id and not next_user:
        return jsonify({'error': 'El usuario receptor seleccionado no existe.'}), 400
    if next_user and next_user.id == g.current_user.id:
        return jsonify({'error': 'No puedes transferirte la custodia a ti mismo.'}), 400
    if next_user and not has_permission(next_user, 'entrega.create'):
        return jsonify({'error': 'El receptor seleccionado no tiene permiso para aceptar entregas–recepciones.'}), 400
    if next_user:
        next_access = UsuarioRol.query.filter_by(usuario_id=next_user.id).first()
        if next_access and not next_access.activo:
            return jsonify({'error': 'El usuario receptor está desactivado.'}), 400
    if etapa == 'analisis' and not (data.get('detalles') or {}).get('solicitud'):
        return jsonify({'error': 'Registra el folio de solicitud o referencia del análisis.'}), 400
    destino_etapa = ((data.get('detalles') or {}).get('destinoEtapa') or '').strip().lower()
    if etapa == 'analisis':
        if not (data.get('detalles') or {}).get('solicitud'):
            return jsonify({'error': 'Registra el folio de solicitud o referencia del análisis.'}), 400
        if destino_etapa not in {'analisis', 'traslado', 'almacenamiento', 'juicio'}:
            return jsonify({'error': 'Selecciona la siguiente etapa asignada para el indicio.'}), 400
        if not next_user:
            return jsonify({'error': 'El análisis debe indicar el siguiente responsable asignado para continuar la cadena de custodia.'}), 400
        if not has_permission(next_user, f'{destino_etapa}.create'):
            return jsonify({'error': f'El receptor no tiene permiso para ejecutar la etapa asignada: {destino_etapa}.'}), 400

    fecha_movimiento = datetime.datetime.utcnow()
    movimiento = MovimientoEtapa(
        registro_id=r.id, indicio_id=indicio.id, usuario_id=g.current_user.id,
        siguiente_usuario_id=next_user.id if next_user else None, etapa=etapa,
        fecha_hora=fecha_movimiento, lugar=data.get('lugar'), actividad=data.get('actividad'),
        estado_embalaje=data.get('estadoEmbalaje'), observaciones=data.get('observaciones')
    )
    db.session.add(movimiento)
    db.session.flush()
    asignacion.etapa_asignada = destino_etapa if etapa == 'analisis' else None
    detalles = data.get('detalles') or {}
    if isinstance(detalles, dict) and detalles:
        # Cada análisis es una fila de movimiento distinta: nunca se sobrescriben resultados anteriores.
        db.session.add(DetalleEtapa(movimiento_id=movimiento.id, datos_json=json.dumps(detalles, ensure_ascii=False)))
    if next_user:
        db.session.add(TransferenciaPendiente(
            registro_id=r.id, indicio_id=indicio.id, movimiento_id=movimiento.id,
            entrega_usuario_id=g.current_user.id, recibe_usuario_id=next_user.id, estado='pendiente'
        ))
    from blockchain.outbox import queue_event, actor_ref_for_user
    event_type = {'analisis':'ANALYSIS_RECORDED','almacenamiento':'STORAGE_RECORDED','juicio':'COURT_PRESENTATION'}.get(etapa, 'MOVEMENT_RECORDED')
    queue_event(actor_user_id=g.current_user.id, event_type=event_type, evidence_id=indicio.id, record_id=r.id,
                minimal_payload={'stage':etapa})
    if next_user:
        queue_event(actor_user_id=g.current_user.id, event_type='TRANSFER_PROPOSED', evidence_id=indicio.id, record_id=r.id,
                    minimal_payload={'recipientRef':actor_ref_for_user(next_user.id), 'nextStage':destino_etapa or etapa})
    audit('movimiento.creado', recurso='indicio', recurso_id=indicio.id, detalle=f'Etapa: {etapa}; transferencia pendiente: {bool(next_user)}')
    db.session.commit()
    return jsonify({'mensaje': 'Movimiento guardado. La custodia no cambiará hasta que el receptor confirme la recepción.' if next_user else 'Movimiento guardado correctamente.', 'id': movimiento.id, 'indicioId': indicio.id, 'transferenciaPendiente': bool(next_user)}), 201


@app.route('/api/transferencias/pendientes', methods=['GET'])
@token_required
def transferencias_pendientes():
    rows = TransferenciaPendiente.query.filter_by(recibe_usuario_id=g.current_user.id, estado='pendiente').order_by(TransferenciaPendiente.creado_en.desc()).all()
    return jsonify([{'id': t.id, 'registroId': t.registro_id, 'indicioId': t.indicio_id, 'identificacion': t.indicio.identificacion if t.indicio else 'Todos los indicios del RCC', 'folio': t.movimiento and Registro.query.get(t.registro_id).folio,
        'etapa': t.movimiento.etapa if t.movimiento else '', 'entrega': t.entrega_usuario.nombre if t.entrega_usuario else '',
        'fecha': t.creado_en.isoformat(), 'lugar': t.movimiento.lugar if t.movimiento else ''} for t in rows])


@app.route('/api/transferencias/<int:transferencia_id>/resolver', methods=['POST'])
@token_required
def resolver_transferencia(transferencia_id):
    if not has_permission(g.current_user, 'entrega.create'):
        audit('permiso.denegado', resultado='rechazado', detalle='Se requiere entrega.create')
        db.session.commit()
        return jsonify({'error': 'Tu rol no está autorizado para aceptar o rechazar entregas.'}), 403
    t = TransferenciaPendiente.query.get_or_404(transferencia_id)
    if t.recibe_usuario_id != g.current_user.id or t.estado != 'pendiente':
        audit('transferencia.resolucion_no_autorizada', resultado='rechazado', recurso='registro', recurso_id=t.registro_id)
        db.session.commit()
        return jsonify({'error': 'No puedes resolver esta transferencia.'}), 403
    data = request.get_json(silent=True) or {}
    decision = data.get('decision')
    if decision not in {'aceptar', 'rechazar'}:
        return jsonify({'error': 'Decisión no válida.'}), 400
    if t.indicio_id:
        asignaciones = [AsignacionIndicio.query.filter_by(indicio_id=t.indicio_id).first()]
    else:
        # Transferencias heredadas de v5.0 se aplicaban al RCC completo.
        asignaciones = (AsignacionIndicio.query.join(Indicio, AsignacionIndicio.indicio_id == Indicio.id)
            .filter(Indicio.registro_id == t.registro_id).all())
    if not asignaciones or any(not a or a.usuario_id != t.entrega_usuario_id for a in asignaciones):
        return jsonify({'error': 'La asignación cambió; la transferencia ya no puede resolverse.'}), 409
    t.estado = 'aceptada' if decision == 'aceptar' else 'rechazada'
    t.resuelto_en = datetime.datetime.utcnow()
    t.observaciones_receptor = (data.get('observaciones') or '')[:2000]
    if decision == 'aceptar':
        for asignacion in asignaciones:
            asignacion.usuario_id = g.current_user.id
            asignacion.asignado_por_id = t.entrega_usuario_id
        actividad_resolucion = 'Recepción confirmada por el usuario receptor'
    else:
        for asignacion in asignaciones:
            asignacion.etapa_asignada = None
        actividad_resolucion = 'Entrega rechazada por el usuario receptor'
    for asignacion in asignaciones:
        db.session.add(MovimientoEtapa(registro_id=t.registro_id, indicio_id=asignacion.indicio_id, usuario_id=g.current_user.id, etapa='entrega-recepcion', actividad=actividad_resolucion, observaciones=t.observaciones_receptor))
    from blockchain.outbox import queue_event
    for asignacion in asignaciones:
        if asignacion.indicio_id:
            queue_event(actor_user_id=g.current_user.id,
                event_type='TRANSFER_ACCEPTED' if decision == 'aceptar' else 'TRANSFER_REJECTED',
                evidence_id=asignacion.indicio_id, record_id=t.registro_id,
                minimal_payload={'nextStage': (asignacion.etapa_asignada or '') if decision == 'aceptar' else ''})
    audit('transferencia.' + decision, recurso='indicio' if t.indicio_id else 'registro', recurso_id=t.indicio_id or t.registro_id, detalle=f'Transferencia #{t.id}; indicios afectados: {len(asignaciones)}')
    db.session.commit()
    return jsonify({'mensaje': 'Recepción confirmada.' if decision == 'aceptar' else 'Transferencia rechazada.'})

@app.route('/api/uploads/<path:filename>')
@token_required
def uploaded_file(filename):
    # Los archivos se sirven solo a cuentas autenticadas. Para evitar enumeración,
    # la autorización se comprueba contra rutas referenciadas por registros asignados.
    if has_permission(g.current_user, 'records.read_all'):
        if filename.startswith('enc/'):
            # El acceso administrativo a archivos nuevos debe pasar por el flujo escrow.
            audit('archivo.escrow_requerido', resultado='rechazado', recurso='archivo', detalle='El administrador debe usar la ruta de escrow.')
            db.session.commit()
            abort(404)
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    owned = db.session.query(Indicio.id).join(AsignacionIndicio, AsignacionIndicio.indicio_id == Indicio.id).filter(AsignacionIndicio.usuario_id == g.current_user.id, Indicio.foto_path == filename).first()
    signed = db.session.query(ServidorPublico.id).join(Registro).join(Indicio, Indicio.registro_id == Registro.id).join(AsignacionIndicio, AsignacionIndicio.indicio_id == Indicio.id).filter(AsignacionIndicio.usuario_id == g.current_user.id, ServidorPublico.firma_path == filename).first()
    trace_file = db.session.query(Trazabilidad.id).join(Registro).join(Indicio, Indicio.registro_id == Registro.id).join(AsignacionIndicio, AsignacionIndicio.indicio_id == Indicio.id).filter(AsignacionIndicio.usuario_id == g.current_user.id, or_(Trazabilidad.firma_entrega_path == filename, Trazabilidad.firma_recibe_path == filename)).first()
    if not owned and not signed and not trace_file:
        audit('archivo.acceso_denegado', resultado='rechazado', recurso='archivo', detalle='Archivo no autorizado o inexistente')
        db.session.commit()
        abort(404)
    if filename.startswith('enc/'):
        from services.encrypted_storage import read_file
        from flask import Response
        content,name,mime=read_file(filename.split('/',1)[1])
        safe_name=name.replace('"','')
        return Response(content,mimetype=mime,headers={'Content-Disposition': f'inline; filename="{safe_name}"'})
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =====================================================================
# ADMINISTRACIÓN — operaciones limitadas a permisos explícitos
# =====================================================================
@app.route('/api/admin/usuarios', methods=['GET'])
@require_permission('admin.users')
def admin_usuarios():
    result = []
    for u in Usuario.query.order_by(Usuario.nombre).all():
        cfg = UsuarioRol.query.filter_by(usuario_id=u.id).first()
        overrides = UsuarioPermiso.query.filter_by(usuario_id=u.id).all()
        result.append({'id': u.id, 'usuario': u.usuario, 'nombre': u.nombre, 'institucion': u.institucion, 'cargo': u.cargo,
            'rol': cfg.rol if cfg else 'perito', 'activo': cfg.activo if cfg else True,
            'permisosPersonalizados': [{'permiso': x.permiso, 'permitido': x.permitido} for x in overrides]})
    return jsonify(result)

@app.route('/api/admin/usuarios', methods=['POST'])
@require_permission('admin.users')
def admin_crear_usuario():
    data = request.get_json(silent=True) or {}
    usuario = (data.get('usuario') or '').strip()
    password = data.get('password') or ''
    rol = data.get('rol') or 'perito'
    if not usuario or len(password) < 12 or rol not in VALID_ROLES or rol == 'administrador':
        return jsonify({'error': 'Usuario requerido, contraseña de al menos 12 caracteres y rol válido.'}), 400
    if Usuario.query.filter_by(usuario=usuario).first():
        return jsonify({'error': 'Ese nombre de usuario ya existe.'}), 409
    u = Usuario(usuario=usuario, password_hash=generate_password_hash(password), nombre=(data.get('nombre') or '').strip(),
        institucion=(data.get('institucion') or '').strip(), cargo=(data.get('cargo') or '').strip())
    db.session.add(u); db.session.flush()
    db.session.add(UsuarioRol(usuario_id=u.id, rol=rol, activo=True))
    audit('admin.usuario.creado', recurso='usuario', recurso_id=u.id)
    db.session.commit()
    return jsonify({'mensaje': 'Usuario creado.', 'id': u.id}), 201

@app.route('/api/admin/usuarios/<int:user_id>', methods=['PATCH'])
@require_permission('admin.users')
def admin_actualizar_usuario(user_id):
    u = Usuario.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    cfg = UsuarioRol.query.filter_by(usuario_id=u.id).first()
    if not cfg:
        cfg = UsuarioRol(usuario_id=u.id, rol='perito', activo=True); db.session.add(cfg)
    if 'rol' in data:
        if data['rol'] not in VALID_ROLES: return jsonify({'error': 'Rol no válido.'}), 400
        if u.id == g.current_user.id and data['rol'] != 'administrador': return jsonify({'error': 'No puedes retirar tu propio rol de administrador.'}), 400
        if cfg.rol == 'administrador' and data['rol'] != 'administrador' and UsuarioRol.query.filter_by(rol='administrador', activo=True).count() <= 1: return jsonify({'error': 'No puedes retirar al último administrador activo.'}), 409
        cfg.rol = data['rol']
    if 'activo' in data:
        if u.id == g.current_user.id and not data['activo']: return jsonify({'error': 'No puedes desactivar tu propia cuenta administrativa.'}), 400
        if cfg.rol == 'administrador' and not data['activo'] and UsuarioRol.query.filter_by(rol='administrador', activo=True).count() <= 1: return jsonify({'error': 'No puedes desactivar al último administrador activo.'}), 409
        cfg.activo = bool(data['activo'])
    if 'nombre' in data: u.nombre = (data['nombre'] or '').strip()
    if 'institucion' in data: u.institucion = (data['institucion'] or '').strip()
    if 'cargo' in data: u.cargo = (data['cargo'] or '').strip()
    audit('admin.usuario.actualizado', recurso='usuario', recurso_id=u.id, detalle='Perfil, rol o estado actualizado')
    db.session.commit()
    return jsonify({'mensaje': 'Usuario actualizado.'})

@app.route('/api/admin/usuarios/<int:user_id>/permisos', methods=['PUT'])
@require_permission('admin.permissions')
def admin_permisos_usuario(user_id):
    u = Usuario.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    permission = (data.get('permiso') or '').strip()
    allowed = data.get('permitido')
    if not permission or permission not in ALL_PERMISSIONS or ('permitido' not in data) or (allowed is not None and not isinstance(allowed, bool)):
        return jsonify({'error': 'Permiso no reconocido o acción inválida.'}), 400
    if u.id == g.current_user.id and permission in {'admin.access', 'admin.users', 'admin.permissions'} and allowed is not True:
        return jsonify({'error': 'No puedes retirar ni restablecer tus propios permisos administrativos desde esta sesión.'}), 400
    if permission == 'admin.access' and allowed is not True:
        target_cfg = UsuarioRol.query.filter_by(usuario_id=u.id).first()
        if target_cfg and target_cfg.rol == 'administrador' and UsuarioRol.query.filter_by(rol='administrador', activo=True).count() <= 1:
            return jsonify({'error': 'No puedes retirar el acceso del último administrador activo.'}), 409
    row = UsuarioPermiso.query.filter_by(usuario_id=u.id, permiso=permission).first()
    if allowed is None:
        if row: db.session.delete(row)
        action = 'restablecido al permiso base del rol'
    else:
        if not row:
            row = UsuarioPermiso(usuario_id=u.id, permiso=permission, permitido=allowed); db.session.add(row)
        else: row.permitido = allowed
        action = 'concedido' if allowed else 'denegado'
    audit('admin.permiso.actualizado', recurso='usuario', recurso_id=u.id, detalle=f'{permission}: {action}')
    db.session.commit()
    return jsonify({'mensaje': 'Permiso actualizado.'})

@app.route('/api/admin/auditoria', methods=['GET'])
@require_permission('audit.read')
def admin_auditoria():
    audit('admin.auditoria.consulta', recurso='auditoria')
    db.session.commit()
    limit = min(max(request.args.get('limit', 100, type=int), 1), 500)
    rows = Auditoria.query.order_by(Auditoria.creado_en.desc()).limit(limit).all()
    return jsonify([{'id': x.id, 'fecha': x.creado_en.isoformat(), 'usuario': x.usuario_texto, 'evento': x.evento,
        'recurso': x.recurso, 'recursoId': x.recurso_id, 'resultado': x.resultado, 'ip': x.ip, 'detalle': x.detalle} for x in rows])

@app.route('/api/admin/usuarios/<int:user_id>/asignaciones', methods=['GET'])
@require_permission('records.read_all')
def admin_asignaciones_usuario(user_id):
    user = Usuario.query.get_or_404(user_id)
    rows = (Indicio.query.join(AsignacionIndicio, AsignacionIndicio.indicio_id == Indicio.id)
            .join(Registro, Registro.id == Indicio.registro_id)
            .filter(AsignacionIndicio.usuario_id == user.id).order_by(Registro.creado_en.desc(), Indicio.id.asc()).all())
    audit('admin.asignaciones.consulta', recurso='usuario', recurso_id=user.id)
    db.session.commit()
    return jsonify([{'registroId': i.registro_id, 'folio': i.registro.folio, 'indicioId': i.id,
        'identificacion': i.identificacion, 'descripcion': i.descripcion,
        'etapaAsignada': i.asignacion_custodia.etapa_asignada if i.asignacion_custodia else None,
        'actualizadoEn': i.asignacion_custodia.actualizado_en.isoformat() if i.asignacion_custodia and i.asignacion_custodia.actualizado_en else None} for i in rows])


@app.route('/api/admin/registros', methods=['GET'])
@require_permission('records.read_all')
def admin_registros():
    rows = Registro.query.order_by(Registro.creado_en.desc()).limit(500).all()
    salida = []
    for r in rows:
        indicios = []
        for i in r.indicios:
            asignacion = AsignacionIndicio.query.filter_by(indicio_id=i.id).first()
            responsable = Usuario.query.get(asignacion.usuario_id) if asignacion else None
            indicios.append({'id': i.id, 'identificacion': i.identificacion,
                'responsable': responsable.nombre if responsable else 'Sin asignar',
                'responsableId': responsable.id if responsable else None,
                'etapaAsignada': asignacion.etapa_asignada if asignacion else None})
        salida.append({'id': r.id, 'folio': r.folio, 'lugar': r.lugar_intervencion,
            'creadoEn': r.creado_en.isoformat() if r.creado_en else None,
            'indicios': indicios})
    return jsonify(salida)


@app.route('/api/admin/solicitudes', methods=['GET'])
@require_permission('audit.read')
def admin_solicitudes():
    limit = min(max(request.args.get('limit', 200, type=int), 1), 500)
    rows = SolicitudHTTP.query.order_by(SolicitudHTTP.creado_en.desc()).limit(limit).all()
    return jsonify([{'id': x.id, 'fecha': x.creado_en.isoformat(), 'usuario': x.usuario_texto,
        'metodo': x.metodo, 'ruta': x.ruta, 'estado': x.estado_http, 'ip': x.ip, 'userAgent': x.user_agent} for x in rows])

@app.route('/api/admin/resumen', methods=['GET'])
@require_permission('admin.access')
def admin_resumen():
    return jsonify({'usuarios': Usuario.query.count(), 'usuariosActivos': UsuarioRol.query.filter_by(activo=True).count(),
        'registros': Registro.query.count(), 'transferenciasPendientes': TransferenciaPendiente.query.filter_by(estado='pendiente').count(),
        'eventosAuditoria': Auditoria.query.count()})

# =====================================================================
# SERVIR FRONTEND DESDE LA RAÍZ DEL PROYECTO
# =====================================================================
RAIZ_DIR = os.path.dirname(BASE_DIR)

# Al entrar a la raíz, mostrar primero el login separado.
@app.route('/')
def root():
    return redirect('/login.html')

# Lista explícita de páginas permitidas. Evita exponer archivos arbitrarios.
PAGINAS_FRONTEND = {
    'login.html', 'index.html', 'rcc.html', 'postregistro.html',
    'entrega-recepcion.html', 'traslado.html', 'analisis.html',
    'almacenamiento.html', 'presentacion.html', 'nuevo-movimiento.html', 'admin.html',
}

@app.route('/<path:page>')
def serve_frontend_page(page):
    if page not in PAGINAS_FRONTEND:
        return jsonify({'error': 'Página no encontrada'}), 404
    return send_from_directory(RAIZ_DIR, page)

@app.route('/icon.svg')
def serve_icon():
    return send_from_directory(RAIZ_DIR, 'icon.svg')

# Sirve hojas de estilo, JavaScript y recursos del frontend.
@app.route('/<any(css, js, assets):folder>/<path:filename>')
def serve_frontend_assets(folder, filename):
    target_dir = os.path.join(RAIZ_DIR, folder)
    return send_from_directory(target_dir, filename)



@app.route('/api/blockchain/status', methods=['GET'])
@token_required
def blockchain_status():
    from sqlalchemy import func
    counts = dict(db.session.query(EventoBlockchain.estado, func.count(EventoBlockchain.id)).group_by(EventoBlockchain.estado).all())
    return jsonify({'enabled': bool(os.environ.get('FABRIC_PEER_ENDPOINT')), 'channel': os.environ.get('FABRIC_CHANNEL','no-configurado'), 'chaincode': os.environ.get('FABRIC_CHAINCODE','no-configurado'), 'events': counts})


@app.route('/api/blockchain/outbox', methods=['GET'])
@token_required
@require_permission('audit.read')
def blockchain_outbox():
    rows = EventoBlockchain.query.order_by(EventoBlockchain.creado_en.desc()).limit(100).all()
    return jsonify([{'eventId':x.event_id,'type':x.tipo_evento,'evidenceId':x.indicio_id,'status':x.estado,'txId':x.tx_id,'attempts':x.intentos,'error':x.ultimo_error,'createdAt':x.creado_en.isoformat()} for x in rows])


@app.route('/api/blockchain/test-event', methods=['POST'])
@token_required
@require_permission('admin.access')
def blockchain_test_event():
    from blockchain.outbox import queue_event
    data=request.get_json(silent=True) or {}
    event_type=data.get('eventType','MOVEMENT_RECORDED')
    try:
        row=queue_event(actor_user_id=g.current_user.id,event_type=event_type,evidence_id=data.get('evidenceId'),record_id=data.get('recordId'),minimal_payload={'test':True,'source':'admin-panel'})
        db.session.commit()
        audit('blockchain.evento_en_cola', user=g.current_user, recurso='evento_blockchain', recurso_id=row.event_id)
        db.session.commit()
        return jsonify({'ok':True,'eventId':row.event_id,'status':row.estado}),202
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error':str(exc)}),400


@app.route('/api/admin/escrow/<int:indicio_id>', methods=['POST'])
@require_permission('evidence.escrow')
def create_escrow_request(indicio_id):
    import uuid
    from datetime import timedelta
    indicio = Indicio.query.get_or_404(indicio_id)
    identity = IdentidadFabric.query.filter_by(usuario_id=g.current_user.id, estado='activo').first()
    if not identity:
        return jsonify({'error': 'El administrador no tiene una identidad Fabric activa para escrow.'}), 403
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        cert = x509.load_pem_x509_certificate(identity.certificado_pem.encode())
        ous = {item.value for item in cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)}
        if 'escrow-admin' not in ous:
            return jsonify({'error': 'El certificado no está habilitado para escrow administrativo.'}), 403
    except Exception:
        return jsonify({'error': 'No se pudo validar el certificado de escrow.'}), 403
    data = request.get_json(silent=True) or {}
    reason = (data.get('motivo') or '').strip()
    if len(reason) < 20:
        return jsonify({'error': 'El motivo debe contener al menos 20 caracteres.'}), 400
    solicitud = SolicitudEscrow(
        solicitud_id=str(uuid.uuid4()), indicio_id=indicio.id,
        administrador_id=g.current_user.id, motivo=reason[:2000],
        estado='ACTIVA', expira_en=datetime.datetime.utcnow() + timedelta(minutes=15),
        ip=request.remote_addr
    )
    db.session.add(solicitud)
    audit('escrow.solicitado', recurso='indicio', recurso_id=indicio.id, detalle='Acceso administrativo temporal solicitado; vigencia 15 minutos')
    db.session.commit()
    return jsonify({'solicitudId':solicitud.solicitud_id,'expiraEn':solicitud.expira_en.isoformat(),'estado':solicitud.estado}), 201


@app.route('/api/admin/escrow/<solicitud_id>/files/<archivo_id>', methods=['GET'])
@require_permission('evidence.escrow')
def escrow_read_file(solicitud_id, archivo_id):
    from flask import Response
    solicitud = SolicitudEscrow.query.filter_by(solicitud_id=solicitud_id).first_or_404()
    if solicitud.administrador_id != g.current_user.id or solicitud.estado not in {'ACTIVA','UTILIZADA'} or solicitud.expira_en < datetime.datetime.utcnow():
        audit('escrow.acceso_denegado', resultado='rechazado', recurso='indicio', recurso_id=solicitud.indicio_id, detalle='Solicitud vencida, ajena o inactiva')
        db.session.commit()
        abort(404)
    archivo = ArchivoCifrado.query.filter_by(archivo_id=archivo_id).first_or_404()
    indicio = Indicio.query.get_or_404(solicitud.indicio_id)
    if archivo.indicio_id != indicio.id and archivo.registro_id != indicio.registro_id:
        abort(404)
    from services.encrypted_storage import read_file
    from blockchain.outbox import queue_event, opaque_ref
    content, name, mime = read_file(archivo_id)
    solicitud.estado='UTILIZADA'; solicitud.utilizada_en=datetime.datetime.utcnow()
    audit('escrow.descifrado', recurso='indicio', recurso_id=indicio.id, detalle='Archivo descifrado mediante escrow administrativo')
    queue_event(actor_user_id=g.current_user.id, event_type='ESCROW_ACCESS', evidence_id=indicio.id,
                record_id=indicio.registro_id, minimal_payload={'action':'decrypt','fileRef':opaque_ref('file',archivo_id)})
    db.session.commit()
    safe_name=name.replace('"','')
    return Response(content,mimetype=mime,headers={'Content-Disposition':f'attachment; filename="{safe_name}"'})


def migrate_v51():
    """Migración incremental v5.1: asignación y trazabilidad por indicio.

    Conserva los datos previos. Los movimientos históricos de RCC con un solo
    indicio se vinculan automáticamente; los de RCC con varios indicios quedan
    sin atribución individual para no inventar a cuál correspondían.
    """
    db.create_all()
    inspector = inspect(db.engine)
    for table, column, ddl in (
        ('movimiento_etapa', 'indicio_id', 'ALTER TABLE movimiento_etapa ADD COLUMN indicio_id INTEGER'),
        ('transferencia_pendiente', 'indicio_id', 'ALTER TABLE transferencia_pendiente ADD COLUMN indicio_id INTEGER'),
        ('asignacion_indicio', 'etapa_asignada', 'ALTER TABLE asignacion_indicio ADD COLUMN etapa_asignada VARCHAR(40)'),
    ):
        if table in inspector.get_table_names() and column not in {c['name'] for c in inspector.get_columns(table)}:
            db.session.execute(text(ddl))
    db.session.flush()
    # Semilla de responsables individuales usando la asignación vigente del RCC.
    for indicio in Indicio.query.all():
        if not AsignacionIndicio.query.filter_by(indicio_id=indicio.id).first():
            legacy = CustodiaAsignacion.query.filter_by(registro_id=indicio.registro_id).first()
            if legacy:
                db.session.add(AsignacionIndicio(indicio_id=indicio.id, usuario_id=legacy.usuario_id, asignado_por_id=legacy.asignado_por_id))
    # Solo se atribuyen movimientos/transferencias antiguas cuando el RCC contiene un único indicio.
    for registro in Registro.query.all():
        items = Indicio.query.filter_by(registro_id=registro.id).all()
        if len(items) == 1:
            db.session.execute(text('UPDATE movimiento_etapa SET indicio_id = :iid WHERE registro_id = :rid AND indicio_id IS NULL'), {'iid': items[0].id, 'rid': registro.id})
            db.session.execute(text('UPDATE transferencia_pendiente SET indicio_id = :iid WHERE registro_id = :rid AND indicio_id IS NULL'), {'iid': items[0].id, 'rid': registro.id})
    db.session.commit()


# La migración se ejecuta al cargar la aplicación, tanto con python app.py como con WSGI.
with app.app_context():
    migrate_v51()

if __name__ == '__main__':
    with app.app_context():
        for u in Usuario.query.all():
            if not UsuarioRol.query.filter_by(usuario_id=u.id).first():
                db.session.add(UsuarioRol(usuario_id=u.id, rol='perito', activo=True))
        db.session.commit()
    app.run(debug=(APP_ENV == 'development' and os.environ.get('FLASK_DEBUG') == '1'), host='127.0.0.1' if APP_ENV == 'development' else '0.0.0.0', port=int(os.environ.get('PORT', '8080')))
