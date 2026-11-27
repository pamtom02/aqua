# Estado de validación

Actualizado el 27 de noviembre de 2026.

## Publicación y autoría comprobadas

- Rama de entrega: `deploy/kubero-api`, publicada por Git sin force push.
- Commit preparado original: `5853957`; historial conservado.
- Autor y committer: `Pamtom21`, usando la configuración Git existente.
- La credencial Git autentica como `Pamtom21`; GitHub devuelve `push=true` y
  `admin=false`. El 403 anterior del conector no probaba falta de colaboración.
  El push de terminal ahora funciona.

## Evidencia de GitHub Actions

- [Ejecución inicial](https://github.com/pamtom02/aqua/actions/runs/45952157365):
  139 pruebas correctas y tres fallos. Se corrigieron dos fixtures sin base simulada
  y una aserción que confundía «incorrectos» con una contraseña filtrada.
- [Validación de los tres servicios](https://github.com/pamtom02/aqua/actions/runs/45952382707):
  pruebas e imágenes correctas antes de los cambios adicionales de seguridad.
- [Seguridad y dependencias fijadas](https://github.com/pamtom02/aqua/actions/runs/45953463391),
  commit `d6370dd`: 153 pruebas de API, 23 satelitales y 25 científicas correctas;
  tres imágenes construidas y sus dependencias instaladas auditadas correctamente.
- La integración ejecutó migraciones dos veces sobre PostgreSQL 17.6 real y comprobó
  roles, aislamiento, GeoJSON, rotación y revocación de sesiones. Verificó MFA en modo
  production, almacenamiento cifrado, exclusión de TOTP concurrentes, recuperación
  de un solo uso, inactividad, plazo absoluto y reautenticación reciente.

## Comprobaciones locales

- TestClient ya funciona en Windows; no persiste el bloqueo de sockets.
- Última suite de API: 153 correctas y una omitida por ausencia de PostgreSQL local.
  La integración real se ejecuta en Actions; no se presenta la omisión como éxito.
- 23 pruebas satelitales y 25 científicas correctas localmente.
- Auditoría del entorno Python actualizado: sin vulnerabilidades conocidas ni
  conflictos. La evidencia de imágenes Linux está en Actions.
- YAML, espacios y búsqueda de patrones de secretos en archivos controlados por Git
  correctos. Esta búsqueda no prueba ausencia absoluta de secretos.

## Estado externo pendiente

- Integrado por fast-forward en `main`: release `a7e17c598ef465ecea06450e66a3eea6208bcd3d`,
  conservando autoría e historial. El último commit de documentación/configuración
  puede ser posterior al SHA de la imagen; no debe confundirse con una nueva release.
- [Build y publicación en main](https://github.com/pamtom02/aqua/actions/runs/45954233390):
  154 pruebas de API, 23 satelitales y 25 científicas correctas: 202 en total.
  Las tres imágenes se construyeron, auditaron y publicaron con `latest` y SHA.
- Se verificó acceso anónimo HTTP 200 a los tres manifiestos de GHCR. Digest API:
  `sha256:7ca71bcbec965dd838b98a7e71d3c50c7029744662473301fe3aa97c64d90c6d`.
- Variables guardadas y verificadas en GitHub: `KUBERO_PIPELINE=facu`, `KUBERO_APPS=api`
  y `API_BASE_URL=https://api-aquabloom.inf.uct.cl`.
- [Primer autodeploy](https://github.com/pamtom02/aqua/actions/runs/45954445421):
  falló explícitamente por ausencia de `KUBERO_TOKEN`; no se envió un restart a UCT.

- App `api` y complemento PostgreSQL creados en `facu/production`.
  URL real: https://api-aquabloom.inf.uct.cl; puerto 8000, SSL, UID/GID 10001,
  raíz de solo lectura, sin escalada, una réplica web y cero workers, perfil Small,
  health `/health/live` con startup 120 s y timeout 5 s, volumen `/app/data` de 8Gi
  con `csi-cephfs-sc` y `ReadWriteOnce`. Arranque real correcto con ese usuario.
- PostgreSQL 17.12 confirmado en los registros del complemento: instancia `postgres`,
  base/usuario `aquabloom`, host `api-postgres`, recursos 50m/500m y 128Mi/512Mi,
  almacenamiento 8Gi CephFS RWO. La API aplicó sus migraciones y pudo consultar la base.
- Comprobaciones HTTPS reales con validación del certificado: `/health/live`,
  `/api/v1/health`, `/docs`, `/openapi.json` y `/api/v1/lakes` responden 200.
  El health confirma PostgreSQL disponible y revisión
  `a7e17c598ef465ecea06450e66a3eea6208bcd3d`. OpenAPI publica 44 rutas y servidor relativo.
- Login de la primera cuenta correcto; devuelve `mfa_required=true`. Acceso privado
  administrativo sin MFA rechazado con 403. Se cerraron las sesiones de comprobación.
- Variables BOOTSTRAP retiradas después de verificar la creación de la cuenta.
  El pod cambió de `web-f87fd4756-576hm` a `web-594d99744c-x8thf` y volvió a estar
  listo. Health y login siguen correctos: cuenta persistente tras el redespliegue.
- Frontera HTTP real: carga anónima 401, origen ajeno en escritura 403 y solicitud
  comprimida 415. Cabeceras nosniff, DENY, CSP y HSTS presentes; el ingress añade
  includeSubDomains al HSTS del host de la API.
- Credenciales entregadas por petición expresa del propietario en Markdown local
  privado fuera del repositorio. La contraseña de conexión fue elegida por él para
  esta evaluación; no se publica aquí ni se incorpora en imágenes o comandos.
- Pendiente `KUBERO_TOKEN`: formulario preparado con nombre
  `aquabloom-github-actions` y vencimiento el 4 de diciembre de 2026 a las 23:59
  (America/Santiago). Falta autorizar la creación de esa credencial persistente,
  guardarla como secret de Actions y ejecutar el workflow de autodeploy.
- El SHA incorporado en cada imagen permite distinguir una API antigua de la revisión
  esperada. Un restart aceptado o una construcción correcta no prueban el despliegue.
- MFA está implementado y probado con cuentas sintéticas; el propietario debe vincular
  y confirmar su autenticador real y custodiar sus códigos.
- No se han importado datos, cuentas ni archivos de Supabase.

La comprobación de revisión ya pasó directamente sobre la API real. El workflow
de autodeploy aún debe ejecutarse con su token. En un disparo manual, indicar el
SHA completo de la release publicada, no el de un commit posterior que solo cambie
documentación. Quedan pendientes la vinculación personal de MFA, las operaciones
administrativas posteriores y un archivo real a través de ese flujo; no se declara
la persistencia de archivos comprobada solo por ver el volumen montado.

## Datos de evaluación — 27 de noviembre de 2026

La carga explícita e idempotente y su evidencia están en
[Datos de evaluación](EVALUATION_DATA.md). Se verificaron catálogo, filtros,
paginación, geometrías y estaciones contra la API pública con los adaptadores
reales de la app móvil. Los límites de los servicios científicos se conservan.
