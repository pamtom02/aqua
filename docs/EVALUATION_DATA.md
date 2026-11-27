# Datos de evaluación de AquaBloom

El cargador `apps/api/tools/seed_evaluation.py` es explícito y de ejecución
manual. No forma parte de las migraciones ni se ejecuta al arrancar la API.

Datos sintéticos identificados con `[AQUA-EVAL-V1]` y nombres `EVAL - …`:

- 26 lagos: 24 activos para probar dos páginas de 20 y 2 inactivos para permisos.
- 78 estaciones: tres por lago, dos activas y una inactiva; todas dentro del polígono.
- Tres regiones para búsqueda y filtros: La Araucanía, Los Ríos y Los Lagos.
- Dos organizaciones y dos conjuntos de datos, cada uno con una versión DRAFT.
- Doce referencias de escenas sintéticas sin archivos ráster ni mediciones inventadas.

Los seis lagos principales sirven de referencia visual por nombre; sus polígonos
son aproximaciones sintéticas y no límites oficiales. Los otros lagos también
son ficticios. Ningún dato acredita condiciones ambientales reales.

## Ejecución y conservación

```sh
python apps/api/tools/seed_evaluation.py
python apps/api/tools/seed_evaluation.py --apply --confirm aquabloom-evaluation
```

La primera orden solo valida geometrías y muestra el plan. La segunda utiliza
`DATABASE_URL` del entorno privado, comprueba la base `aquabloom` y ejecuta
inserciones en una transacción. Un conflicto inesperado revierte esa transacción.
No imprime la conexión ni sus credenciales.

Los UUID son deterministas. Repetir la carga omite identificadores existentes,
conservando incluso las ediciones realizadas sobre registros de evaluación.
No crea cuentas, contraseñas, roles globales ni sesiones. Vincula a los
administradores ya activos con el primer equipo sintético, sin cambiar su rol
global ni su segundo factor. Las cuentas y archivos previos se conservan.

Para retirar estos datos, revisar los UUID generados por el cargador y sus
dependencias y solicitar una operación de limpieza específica. No borrar por
coincidencias parciales de nombre ni eliminar la base o sus volúmenes.

## Funcionalidades que se pueden probar

Catálogo, búsqueda por nombre, filtros por región, paginación, mapa de polígonos,
detalle, estaciones y captura de nuevos borradores con ubicación/foto en la app.
La captura autenticada utiliza la cuenta existente; un administrador debe
vincular su propio segundo factor antes de entrar.

La carga no activa workers, modelos, predicciones ni la sincronización de los
borradores móviles. Las rutas científicas incompletas mantienen sus límites.

## Evidencia

Las pruebas locales validan geometrías, contención y referencias. La prueba de
PostgreSQL verifica transacción real, repetición sin duplicados, conservación de
ediciones y de usuarios existentes. La carga en Kubero y la lectura pública se
documentan después de ejecutarlas y comprobarlas.
