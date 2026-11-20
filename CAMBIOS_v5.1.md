# Project CC v5.1 — cambios funcionales

## Decisiones aplicadas
- Después del análisis, el destino operativo se define mediante una etapa asignada y una persona receptora.
- Un indicio puede tener múltiples análisis; cada uno se conserva como evento independiente.

## Cambios incluidos
1. **Custodia por indicio.** Se incorpora `AsignacionIndicio`; cada indicio tiene responsable vigente y una posible siguiente etapa asignada.
2. **Trazabilidad individual.** `MovimientoEtapa` y `TransferenciaPendiente` se relacionan con `indicio_id`. Los formularios requieren seleccionar el indicio.
3. **Asignación de destino tras análisis.** El analista debe seleccionar la siguiente etapa (`otro análisis`, `traslado`, `almacenamiento` o `juicio`) y una persona receptora. El backend valida los permisos del receptor.
4. **Control de flujo.** Una vez aceptada la entrega, el indicio solo puede continuar por la etapa que se le asignó.
5. **Análisis repetibles.** Cada análisis genera su propio movimiento y detalle; no sobrescribe análisis anteriores.
6. **Administración.** El panel muestra responsables y etapa asignada por indicio; permite consultar la trazabilidad individual.
7. **Migración.** Al iniciar se crean las tablas y columnas necesarias. Se copia el responsable RCC actual a cada indicio. Los movimientos antiguos de RCC con un solo indicio se vinculan a ese indicio. Los de RCC con varios indicios se muestran como eventos históricos compartidos en la trazabilidad de cada indicio, porque la versión anterior no identificaba uno en particular. Las transferencias pendientes antiguas se conservan como entregas del RCC completo y al aceptarse actualizan los responsables de todos sus indicios.

## Flujo de ejemplo

`RCC / procesamiento → traslado → análisis 1 → entrega–recepción → etapa asignada → análisis 2 (si fue asignado) → entrega–recepción → almacenamiento o juicio, según la asignación`

La etapa posterior no se decide por una regla fija del sistema: queda registrada en la asignación del indicio y el backend la valida.

## Validación realizada
- `python -m py_compile backend/app.py backend/models.py backend/generar_usuarios_prueba.py`: correcto.
- `node --check js/stage.js` y `node --check js/admin.js`: correctos.
- No se pudo ejecutar una prueba de integración Flask/SQLite en este entorno porque Flask y las dependencias del proyecto no están instaladas. Se debe realizar la prueba de arranque y migración en Ubuntu antes de usar datos reales.
