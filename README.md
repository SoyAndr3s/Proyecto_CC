# Project CC — versión 5.1 (prototipo de tesis)

Sistema web de demostración para registro y seguimiento de indicios/evidencias. Frontend HTML/CSS/JavaScript, API Flask y SQLite. No es una carpeta de investigación ni sustituye los formatos, firmas o controles jurídicos que determine la institución.

## Cambios principales de esta versión
- La asignación de custodia y el historial operativo ahora se administran por indicio; un mismo RCC puede contener indicios con responsables y recorridos distintos.
- Cada formulario de etapa exige seleccionar el indicio concreto; la consulta de trazabilidad devuelve únicamente el historial de ese indicio.
- Después de cada análisis se debe asignar una siguiente etapa y una persona receptora con permisos compatibles. El backend impide registrar una etapa distinta a la asignada hasta completar la entrega–recepción.
- Un indicio puede tener múltiples análisis: cada análisis genera un movimiento y un detalle independientes, conservando solicitudes, métodos, resultados y destino posterior.
- Se retiró del RCC la captura manual duplicada de traslado y continuidad: el apartado 08 ahora explica que la trazabilidad se genera desde los movimientos posteriores.
- Traslado, análisis y almacenamiento tienen campos específicos; los detalles se guardan en `DetalleEtapa`, separados del RCC.
- La etapa se fija por página (no se elige libremente en cada formulario), salvo `nuevo-movimiento`, que es una operación excepcional validada por permisos en backend.
- Se incorporaron roles, excepciones de permisos por usuario, activación/desactivación de cuentas y panel administrativo.
- Las entregas se proponen como pendientes: el responsable no cambia hasta que el receptor autorizado acepta.
- Se añadió auditoría de accesos y operaciones, registro de IP/User-Agent y límite temporal de intentos de login.
- Las fotos y firmas ya no se sirven por una ruta pública `/uploads`; requieren autenticación y autorización.
- Se unificó el tema oscuro/claro en las páginas del portal y etapas.

## Estructura
- `login.html`: acceso separado con Turnstile configurable.
- `index.html`: panel de inicio.
- `rcc.html`: registro inicial.
- `traslado.html`, `analisis.html`, `almacenamiento.html`, `presentacion.html`: formularios especializados.
- `entrega-recepcion.html`: bandeja para aceptar/rechazar entregas pendientes.
- `admin.html`: administración de usuarios, roles, permisos, registros y auditoría.
- `backend/app.py`: API, autenticación y autorización.
- `backend/models.py`: modelos SQLite/SQLAlchemy.

## Instalación local (Windows o Ubuntu)
1. Instala Python 3.10 o posterior.
2. Entra a `backend/`. Crea y activa un entorno virtual.
3. Instala dependencias: `pip install -r requirements.txt`.
4. Copia `.env.example` como `.env`. Para desarrollo local puedes mantener `APP_ENV=development`; cambia `SECRET_KEY` por una cadena aleatoria propia.
5. Si la base de datos aún no tiene administrador, crea la primera cuenta con `python create_admin.py`. Usa una contraseña única de al menos 14 caracteres.
6. Inicia el servidor: `python app.py`.
7. Abre `http://127.0.0.1:8080/login.html`.
8. Desde Administración crea las cuentas operativas y asigna sus roles.

No se crean cuentas automáticamente al iniciar. Para poblar un entorno de prueba usa el script descrito en `USUARIOS_PRUEBA.md`; sus contraseñas son deliberadamente débiles y solo sirven para pruebas locales.

## Roles base
- `perito`: RCC, traslado y entrega/recepción.
- `analista`: RCC, traslado, análisis y entrega/recepción.
- `almacenista`: traslado, almacenamiento y entrega/recepción.
- `primer_respondiente`: RCC, traslado y entrega/recepción.
- `supervisor`: consulta de auditoría y registros; puede aceptar entregas y registrar la etapa de juicio/presentación cuando le sea asignada.
- `administrador`: gestión de usuarios/permisos, supervisión de registros y auditoría.

Los permisos individuales pueden concederse o denegarse desde el panel. Los roles son una propuesta configurable para el prototipo; deben validarse con los perfiles institucionales y los protocolos aplicables.

## Migración desde v5.0 y versiones anteriores
- Haz una copia de `backend/custodia.db` y de `backend/uploads/` antes de actualizar.
- Conserva `backend/custodia.db` y `backend/uploads/`; la migración v5.1 añade las tablas y columnas necesarias al iniciar.
- Ejecuta `python create_admin.py` para crear una cuenta administrativa nueva.
- Inicia `python app.py`; la migración v5.1 se ejecuta al cargar la aplicación, también si se inicia mediante WSGI.
- Los responsables actuales del RCC se copian como responsables iniciales de cada indicio. En RCC históricos con un solo indicio, los movimientos anteriores se vinculan automáticamente. En RCC con varios indicios, los movimientos antiguos se muestran como eventos históricos compartidos en cada trazabilidad individual, porque la versión anterior no identificaba a cuál indicio correspondían. Las transferencias pendientes antiguas se conservan como entregas del RCC completo. Los movimientos nuevos sí quedan vinculados al indicio seleccionado.

## Limitaciones importantes
1. La entrega/recepción requiere aceptación explícita del receptor, pero todavía no integra firma electrónica institucional certificada ni validación jurídica de identidad.
2. En RCC históricos con varios indicios, los movimientos previos a v5.1 se muestran como eventos compartidos y no se atribuyen artificialmente a un solo indicio; los eventos nuevos se registran individualmente.
3. La ubicación geográfica exacta del dispositivo no está activada. Se registra la IP de origen; la geolocalización por IP solo es aproximada.
4. La bitácora de aplicación no equivale a un registro inmutable. Se requieren respaldos y controles institucionales adicionales para un uso real.
5. El contenido del análisis es un resumen de captura; no sustituye el dictamen pericial formal.

## Seguridad y uso local
No publiques `custodia.db`, `.env`, firmas, fotografías ni respaldos. Usa una `SECRET_KEY` aleatoria, protege el equipo Ubuntu con cuenta de usuario y firewall local, limita el acceso al puerto de desarrollo a `127.0.0.1` y realiza respaldos cifrados. Consulta `DEPLOY_UBUNTU.md` para la instalación local.


## Usuarios ficticios para pruebas

Consulta `USUARIOS_PRUEBA.md`. Desde `backend`, ejecuta `python generar_usuarios_prueba.py` para crear dos administradores y doce cuentas operativas.


## Nueva línea de trabajo v6 — Hyperledger Fabric
Consulta `README_v6.md` y `ARQUITECTURA_FABRIC_v6.md`. La integración es una base de laboratorio y no debe utilizarse todavía con indicios reales.
