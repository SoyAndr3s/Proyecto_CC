# Backend — Project CC v5.1

Flask + SQLAlchemy + SQLite. Ejecuta desde este directorio.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python create_admin.py
python app.py
```

La migración v5.1 se ejecuta al cargar la aplicación. Crea `AsignacionIndicio`, agrega `indicio_id` a movimientos y transferencias y conserva la asignación histórica del RCC como origen para sembrar los responsables individuales. Los movimientos antiguos de RCC con varios indicios no se atribuyen arbitrariamente.

## Endpoints principales
- `POST /api/login`, `GET /api/me`
- `POST/GET /api/registros`
- `GET /api/registros/<id>`
- `GET /api/registros/<id>/movimientos?indicio_id=<id>`
- `POST /api/registros/<id>/movimientos` (requiere `indicioId` en el cuerpo)
- `GET /api/transferencias/pendientes`
- `POST /api/transferencias/<id>/resolver`
- `/api/admin/usuarios`, `/api/admin/usuarios/<id>`, `/api/admin/usuarios/<id>/permisos`
- `/api/admin/registros`, `/api/admin/resumen`, `/api/admin/auditoria`
- `GET /api/uploads/<archivo>` (requiere autenticación y autorización)

Cada análisis crea un movimiento y un `DetalleEtapa` independiente. El análisis exige definir la siguiente etapa y el usuario receptor; el backend valida que ese usuario tenga permiso para ejecutar la etapa asignada. La etapa siguiente queda restringida hasta que se acepte la entrega.
