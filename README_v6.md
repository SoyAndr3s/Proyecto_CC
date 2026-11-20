# Project CC v6 — primera base con Hyperledger Fabric

Esta versión parte de Project CC v5.1. Conserva el frontend y el backend actuales y agrega modelos, cola outbox, cifrado AES-GCM, cliente Fabric Gateway, worker y chaincode inicial.

## Requisitos VM1
- Ubuntu 26.04, Python 3.12+, Node.js 22 LTS, Docker Engine/Compose y binarios Hyperledger Fabric 2.5.x compatibles.
- `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- `cp .env.example .env`; configura `SECRET_KEY` y `PROJECTCC_MASTER_KEY_B64`.
- Genera una clave maestra de 32 bytes: `python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"`. Guarda la clave fuera del repositorio y respáldala de forma segura. Si se pierde, los datos cifrados no podrán recuperarse.
- Crea el directorio de archivos cifrados y dale permisos al usuario del servicio: `sudo install -d -o $USER -g $USER -m 700 /var/lib/projectcc/encrypted`.
- Configura `FABRIC_PEER_ENDPOINT=peer0.org1.projectcc.net:7051` y `FABRIC_TLS_ROOT_CERT` con la ruta al CA TLS del peer Org1 copiado desde VM2. Asegúrate de que VM1 resuelva ese DNS interno.
- Protege el archivo `.env`: `chmod 600 .env`.
- Instala el cliente Gateway: `cd ../fabric/gateway-client && npm install`.

## Requisitos VM2-VM4
Docker Engine/Compose; un peer y CouchDB por VM. Sigue `fabric/network/README.md`.

## Primer arranque Flask
Las tablas nuevas se crean al iniciar por `db.create_all()`. No se borra la base actual. Ejecuta `python app.py`. El endpoint autenticado `GET /api/blockchain/status` muestra estado de configuración.

## Worker
En VM1, dentro de backend y con el mismo entorno: `python -m blockchain.sync_worker`. Manténlo como servicio systemd.

## Registrar identidades institucionales
1. Crea las tres instituciones de laboratorio: `python seed_fabric_institutions.py`.
2. Obtén el identificador seudónimo del usuario: `python show_fabric_actor_ref.py --usuario-id ID`.
3. En la VM de la institución, emite un certificado individual firmado por su CA local. En el laboratorio, `fabric/network/issue-user-cert.sh` genera un certificado cuyo CN es el `actorRef` seudónimo y OU=client. Para el certificado de un administrador con permiso escrow, agrega `EXTRA_OU=escrow-admin`. No copies la clave privada de la CA a VM1.
4. Copia temporalmente el certificado y la clave privada del usuario a VM1 por un canal seguro y registra la identidad: `python register_fabric_identity.py --usuario-id ID --msp-id Org1MSP --cert cert.pem --key key.pem`.

El registro cifra la clave privada antes de guardarla en SQLite. El chaincode compara el CN del certificado con el actorRef seudónimo; para escrow exige OU=escrow-admin. Después de registrarla, elimina las copias temporales de la clave privada. En esta versión la clave individual queda bajo custodia técnica del servidor central; el certificado sí es individual, pero no equivale todavía a una firma desde un dispositivo controlado directamente por el usuario. El script OpenSSL es solo para laboratorio; sustituir por Fabric CA/PKI institucional en etapas posteriores.

## Cliente Gateway
El worker usa `fabric/gateway-client/gateway.mjs` y el endpoint del peer Gateway. Se necesita una fila `IdentidadFabric` activa por usuario, con certificado y clave privada cifrada en AES-GCM usando AAD `fabric-user:<id>`. El endpoint debe usar el nombre DNS del certificado y el TLS root certificate del peer.

## Prueba de cola
Con usuario administrador autenticado, `POST /api/blockchain/test-event` con `{ "eventType": "MOVEMENT_RECORDED" }` crea un evento de prueba. No confirma blockchain hasta que worker y red estén conectados. Revisa `GET /api/blockchain/outbox` (permiso `audit.read`).

## Importante
Esta es una primera iteración ejecutable de la integración, no una red institucional terminada ni apta para evidencia real. Revisa `ARQUITECTURA_FABRIC_v6.md` y `fabric/network/README.md` antes de desplegar.

## Límites que debes conocer antes de probar
- Las imágenes y firmas que se capturen desde esta versión se cifran en disco. Las imágenes históricas de la carpeta `uploads/` permanecen en su formato anterior.
- Los campos de los formularios y los detalles operativos siguen en SQLite en texto claro en esta iteración. La aplicación aplica permisos, pero todavía no se ha completado el cifrado por indicio de todo el contenido.
- El administrador puede consultar formularios mediante permisos heredados; el flujo escrow actual protege la descarga de archivos cifrados nuevos, no todos los campos del formulario.
- La clave privada X.509 individual se conserva cifrada en la base central para el prototipo. En producción deberá moverse a HSM o dispositivo del usuario.
- No se ha validado el despliegue real en cuatro VMs desde este entorno. Las verificaciones realizadas aquí son de sintaxis Python/JavaScript y estructura YAML; Go requiere descargar el módulo oficial para compilar el chaincode.

**No cargues evidencia real ni información personal sensible en esta iteración.** Primero hay que completar cifrado de formularios, política estricta de consulta, enrolamiento/revocación de certificados y pruebas multi-VM.


## Configuración específica de cuatro VMs

Consulta `deploy/4-vms/README.md`. IPs: VM1 10.10.0.11, VM2 10.10.0.12, VM3 10.10.0.13, VM4 10.10.0.14.
